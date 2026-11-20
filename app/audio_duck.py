"""说话时自动压低游戏音量（类似 Discord 的语音激活降噪）。

用 Windows Core Audio 的 per-app 音量控制，只动 recvx.exe 那一路，
不影响系统音量、不影响别的程序。

pycaw 不可用时静默降级：什么都不做，游戏音量保持原样。
"""
import threading
import time

GAME_EXE = "recvx.exe"
DUCK_LEVEL = 0.22          # 说话时压到 22%
FADE_STEPS = 6
FADE_MS = 45               # 淡入淡出，避免突然跳变

_available = None


def available():
    """Is per-app volume control usable on this machine?"""
    global _available
    if _available is None:
        try:
            from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume  # noqa: F401
            _available = True
        except Exception:
            _available = False
    return _available


def _game_sessions():
    """Audio sessions belonging to the game process."""
    try:
        from pycaw.pycaw import AudioUtilities
    except Exception:
        return []
    out = []
    try:
        for s in AudioUtilities.GetAllSessions():
            proc = s.Process
            if proc is None:
                continue
            try:
                name = proc.name()
            except Exception:
                continue
            if name.lower() == GAME_EXE:
                out.append(s)
    except Exception:
        pass
    return out


def game_volume():
    """Current volume of the game's audio session, or None if unknown."""
    sess = _game_sessions()
    if not sess:
        return None
    try:
        return float(sess[0].SimpleAudioVolume.GetMasterVolume())
    except Exception:
        return None


class Ducker:
    """Lowers the game volume while the assistant speaks, then restores it."""

    def __init__(self, level=DUCK_LEVEL):
        self.level = level
        self._saved = {}          # session id -> 原始音量
        self._lock = threading.Lock()
        self._active = False

    def duck(self):
        """Lower the game now. Fading runs in the background."""
        if not available():
            return False
        with self._lock:
            if self._active:
                return True
            sessions = _game_sessions()
            if not sessions:
                return False
            self._saved.clear()
            for s in sessions:
                try:
                    cur = float(s.SimpleAudioVolume.GetMasterVolume())
                    self._saved[id(s)] = (s, cur)
                except Exception:
                    continue
            self._active = True
        threading.Thread(target=self._fade_to, args=(self.level,), daemon=True).start()
        return True

    def unduck(self):
        """Restore the volume saved by duck()."""
        if not available():
            return
        with self._lock:
            if not self._active:
                return
            saved = list(self._saved.values())
            self._saved.clear()
            self._active = False
        for sess, vol in saved:
            try:
                sess.SimpleAudioVolume.SetMasterVolume(float(vol), None)
            except Exception:
                pass

    def _fade_to(self, target):
        with self._lock:
            items = list(self._saved.values())
        if not items:
            return
        for i in range(1, FADE_STEPS + 1):
            for sess, start in items:
                v = start + (target - start) * (i / FADE_STEPS)
                try:
                    sess.SimpleAudioVolume.SetMasterVolume(
                        float(max(0.0, min(1.0, v))), None)
                except Exception:
                    pass
            time.sleep(FADE_MS / 1000.0)

    @property
    def active(self):
        return self._active


if __name__ == "__main__":
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("pycaw 可用:", available())
    print(f"游戏当前音量: {game_volume()}")
    d = Ducker()
    print("压低…")
    ok = d.duck()
    print(f"  结果: {ok}, 现在 {game_volume()}")
    time.sleep(1.5)
    print("恢复…")
    d.unduck()
    time.sleep(0.3)
    print(f"  现在 {game_volume()}")
