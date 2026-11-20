"""两个 AI 助手之间的对话通道。

设计要点：
  · 独立于游戏的联机通道 —— 游戏走 UDP 7140 且端到端加密，不能碰
  · 互联网场景：一方当「中继」，另一方连它（手动填地址）
  · 自由闲聊，但有硬性刹车，见 Limits

协议：一行一个 JSON，UTF-8，以 \\n 结尾。
"""
import json
import queue
import socket
import threading
import time

DEFAULT_PORT = 7150

# ---------------------------------------------------------------- 防失控

class Limits:
    """Hard brakes so two AIs can't bill the user into ruin overnight.

    Two budgets: event messages (blood, deaths, room changes) get their own
    small quota so chatter can never starve them.
    """

    MAX_MSGS_PER_MIN = 6          # 闲聊：每分钟最多 6 条
    MAX_EVENT_PER_MIN = 4         # 事件：独立额度，不会被闲聊挤掉
    MAX_CHARS_TOTAL = 20000       # 整个会话累计 2 万字符
    IDLE_STOP_SEC = 180           # 双方都 3 分钟没动，暂停
    MAX_HOURS = 2.0               # 单次会话最长 2 小时

    def __init__(self):
        self.window = []          # 闲聊时间戳
        self.events = []          # 事件时间戳
        self.chars = 0
        self.started = time.time()
        self.last_activity = time.time()

    def allow(self, text, kind="chat"):
        now = time.time()
        if now - self.started > self.MAX_HOURS * 3600:
            return False, "会话超时"
        if self.chars + len(text) > self.MAX_CHARS_TOTAL:
            return False, "字数上限"
        if now - self.last_activity > self.IDLE_STOP_SEC:
            return False, "闲置太久"

        if kind == "event":
            self.events = [t for t in self.events if now - t < 60]
            if len(self.events) >= self.MAX_EVENT_PER_MIN:
                return False, "事件太频繁"
            self.events.append(now)
        else:
            self.window = [t for t in self.window if now - t < 60]
            if len(self.window) >= self.MAX_MSGS_PER_MIN:
                return False, "太频繁"
            self.window.append(now)

        self.chars += len(text)
        self.last_activity = now
        return True, ""

    def note(self):
        self.last_activity = time.time()

    def stats(self):
        now = time.time()
        return {
            "msgs_last_min": len([t for t in self.window if now - t < 60]),
            "events_last_min": len([t for t in self.events if now - t < 60]),
            "chars": self.chars,
            "elapsed_min": (now - self.started) / 60,
        }


# ---------------------------------------------------------------- transport

class Peer:
    """One TCP channel to the other player's assistant.

    Host mode (is_host=True) listens; client mode connects. Either side may
    send at any time, so the link is symmetric after establishment.
    """

    def __init__(self, is_host=True, host="0.0.0.0", port=DEFAULT_PORT,
                 remote="", on_message=None, on_status=None):
        self.is_host = is_host
        self.host = host
        self.port = port
        self.remote = remote
        self.on_message = on_message or (lambda m: None)
        self.on_status = on_status or (lambda s: None)

        self.sock = None
        self.conn = None
        self.connected = False
        self.running = False
        self.send_q = queue.Queue()
        self._threads = []
        self._lock = threading.Lock()

    # -------------------------------------------------- public
    def start(self):
        self.running = True
        if self.is_host:
            self._threads.append(threading.Thread(target=self._listen, daemon=True))
        else:
            self._threads.append(threading.Thread(target=self._connect, daemon=True))
        self._threads.append(threading.Thread(target=self._sender, daemon=True))
        for t in self._threads:
            t.start()

    def stop(self):
        self.running = False
        self.connected = False
        for s in (self.conn, self.sock):
            try:
                if s:
                    s.close()
            except Exception:
                pass
        self.conn = self.sock = None

    def send(self, payload):
        if not self.connected:
            return False
        try:
            self.send_q.put_nowait(payload)
            return True
        except Exception:
            return False

    # -------------------------------------------------- internals
    def _listen(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen(1)
            s.settimeout(1.0)
            self.sock = s
            self.on_status(f"等待对方连接（端口 {self.port}）")
            while self.running:
                try:
                    conn, addr = s.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                with self._lock:
                    if self.conn:
                        try:
                            conn.close()
                        except Exception:
                            pass
                        continue
                    self.conn = conn
                    self.connected = True
                self.on_status(f"已连接 {addr[0]}")
                self._reader(conn)
                with self._lock:
                    self.conn = None
                    self.connected = False
                self.on_status("对方已断开")
        except OSError as e:
            self.on_status(f"监听失败：{e}")
        finally:
            try:
                if self.sock:
                    self.sock.close()
            except Exception:
                pass

    def _connect(self):
        while self.running:
            try:
                self.on_status(f"正在连接 {self.remote}…")
                s = socket.create_connection((self.remote, self.port), timeout=8)
                with self._lock:
                    self.conn = s
                    self.connected = True
                self.on_status("已连接")
                self._reader(s)
            except Exception as e:
                self.on_status(f"连接失败（{type(e).__name__}），5 秒后重试")
            with self._lock:
                self.conn = None
                self.connected = False
            for _ in range(50):
                if not self.running:
                    return
                time.sleep(0.1)

    def _reader(self, conn):
        conn.settimeout(1.0)
        buf = b""
        while self.running:
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line.decode("utf-8", "replace"))
                except Exception:
                    continue
                self.on_message(msg)

    def _sender(self):
        while self.running:
            try:
                payload = self.send_q.get(timeout=0.5)
            except queue.Empty:
                continue
            conn = self.conn
            if not conn:
                continue
            try:
                data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
                conn.sendall(data)
            except OSError:
                with self._lock:
                    self.connected = False


# ---------------------------------------------------------------- LAN discovery

def discover_host(port=DEFAULT_PORT, timeout=2.0):
    """Broadcast on the LAN and return the first assistant that answers."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.settimeout(timeout)
    try:
        s.sendto(b"VERA_AI_DISCOVER", ("255.255.255.255", port + 1))
        data, addr = s.recvfrom(256)
        if data.startswith(b"VERA_AI_HERE"):
            return addr[0]
    except Exception:
        pass
    finally:
        s.close()
    return None


def answer_discovery(port=DEFAULT_PORT, on_found=None):
    """Reply to LAN discovery broadcasts so the other side can find us."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", port + 1))
    except Exception:
        return None
    s.settimeout(1.0)

    def loop():
        while True:
            try:
                data, addr = s.recvfrom(256)
                if data.startswith(b"VERA_AI_DISCOVER"):
                    s.sendto(b"VERA_AI_HERE", addr)
                    if on_found:
                        on_found(addr[0])
            except socket.timeout:
                continue
            except OSError:
                break

    threading.Thread(target=loop, daemon=True).start()
    return s
