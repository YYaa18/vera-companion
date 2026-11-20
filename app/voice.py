"""DeepSeek 语音能力封装：ASR（听）与 TTS（说）。

两者都是同步 HTTP，放在后台线程里调用。
"""
import io
import json
import os
import queue
import threading
import time
import urllib.error
import urllib.request
import wave

import numpy as np

TTS_URL = "/v1/tools/tts"
ASR_URL = "/v1/tools/asr"


# ------------------------------------------------------------------ recording

class Recorder:
    """Records mic audio into a thread-safe queue at 16 kHz mono.

    音频回调跑在 PortAudio 自己的线程里，不能在回调里拿锁、也不能让回调
    里抛异常——那会把 PortAudio 的线程卡死（表现为整个程序失去响应）。
    这里用 queue.Queue（内部自带锁且无阻塞写）收集数据，
    停止时先让回调自己看到 _want=False 退出，再关流。
    """

    RATE = 16000

    def __init__(self, device=None):
        self.device = device
        self.stream = None
        self._q = queue.Queue()
        self._want = False        # 回调看到 False 就丢弃数据
        self._stopping = False

    def start(self):
        import sounddevice as sd

        if self.stream is not None:
            return
        # 丢掉上一轮残留
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break
        self._want = True
        self._stopping = False
        stream = sd.InputStream(
            samplerate=self.RATE, channels=1, dtype="int16",
            device=self.device, blocksize=1024,
            callback=self._cb,
        )
        stream.start()
        self.stream = stream

    def _cb(self, indata, _frames, _time, status):
        # 绝不能在回调里抛异常：PortAudio 会让整条音频线程失效。
        # Queue.put_nowait 不加外部锁，安全。
        try:
            if self._want and not self._stopping:
                self._q.put_nowait(indata.copy())
        except Exception:
            pass

    def stop(self):
        """Stop and return WAV bytes, or None if nothing was captured."""
        stream, self.stream = self.stream, None
        if stream is None:
            return None

        self._want = False          # 先让回调放弃新数据
        self._stopping = True

        frames = []
        while True:
            try:
                frames.append(self._q.get_nowait())
            except queue.Empty:
                break

        # 关流放到后台，最多等 1.5 秒；卡住也不拖住界面
        def _shutdown():
            try:
                stream.stop()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass

        t = threading.Thread(target=_shutdown, daemon=True)
        t.start()
        t.join(timeout=1.5)

        if not frames:
            return None
        try:
            audio = np.concatenate(frames, axis=0)
        except Exception:
            return None
        if len(audio) < self.RATE * 0.25:
            return None
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.RATE)
            w.writeframes(audio.tobytes())
        return buf.getvalue()

    def level(self):
        """Rough current input level 0..1, for the listening animation.

        Peeks at the newest chunk without consuming it, so stop() still gets it.
        """
        try:
            q = self._q.queue
            if not q:
                return 0.0
            last = q[-1]
        except Exception:
            return 0.0
        a = np.abs(last.astype(np.int32))
        return float(min(1.0, a.mean() / 6000.0))


# ------------------------------------------------------------------ ASR / TTS

def transcribe(wav_bytes, key, base, timeout=120):
    """POST the WAV to DeepSeek ASR, return the transcript text."""
    boundary = "----recvxasr"
    parts = [
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="file"; filename="speech.wav"\r\n',
        b"Content-Type: audio/wav\r\n\r\n",
        wav_bytes,
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    data = b"".join(parts)
    req = urllib.request.Request(base + ASR_URL, data=data, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    return (d.get("text") or "").strip()


def synthesize(text, key, base, voice="stella", timeout=120):
    """Return WAV bytes for the given text."""
    payload = {"text": text, "voice_id": voice, "format": "wav", "filter_markdown": True}
    req = urllib.request.Request(base + TTS_URL,
                                 data=json.dumps(payload).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ------------------------------------------------------------------ playback

class Player:
    """Plays WAV bytes in a background thread, so the UI never blocks."""

    def __init__(self, device=None):
        self.device = device
        self.q = queue.Queue()
        self._stop = threading.Event()
        self._busy = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    @property
    def busy(self):
        return self._busy or not self.q.empty()

    def play(self, wav_bytes):
        self.stop()
        self._stop.clear()
        self.q.put(wav_bytes)

    def stop(self):
        """Drop whatever is queued and interrupt playback."""
        try:
            while True:
                self.q.get_nowait()
        except queue.Empty:
            pass
        self._stop.set()
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass

    def _run(self):
        import sounddevice as sd

        while True:
            wav = self.q.get()
            if self._stop.is_set():
                self._stop.clear()
                continue
            self._busy = True
            try:
                with wave.open(io.BytesIO(wav)) as w:
                    rate = w.getframerate()
                    ch = w.getnchannels()
                    raw = w.readframes(w.getnframes())
                data = np.frombuffer(raw, dtype=np.int16)
                if ch > 1:
                    data = data.reshape(-1, ch)[:, 0]
                sd.play(data, rate, device=self.device)
                while sd.get_stream().active:
                    if self._stop.is_set():
                        sd.stop()
                        break
                    time.sleep(0.05)
            except Exception:
                pass
            finally:
                self._busy = False


def duck_volume():
    """Best-effort: nothing to do on Windows without a mixer API; kept for clarity."""
    return None
