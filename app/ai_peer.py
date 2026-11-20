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


def _advertise_ip():
    """The address the host should tell the other player to connect to."""
    try:
        import net_adapters
        ip, _alias = net_adapters.guess_virtual_lan()
        if ip:
            return ip
        return net_adapters.best_local_ip() or "0.0.0.0"
    except Exception:
        return "0.0.0.0"

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
            try:
                s.bind((self.host, self.port))
            except OSError as e:
                self.on_status(f"端口 {self.port} 绑定失败（{e}）——换个端口，或关掉占用它的程序")
                return
            s.listen(1)
            s.settimeout(1.0)
            self.sock = s
            # 告诉玩家自己该被连的地址，虚拟局域网下就是 UU 分配的那个
            shown = self.host if self.host not in ("0.0.0.0", "") else _advertise_ip()
            self.on_status(f"等待连接 — 让对方填 {shown}:{self.port}")
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

# ---------------------------------------------------------------- 局域网发现

DISCOVER_MAGIC = b"VERA_AI_DISCOVER"
REPLY_MAGIC = b"VERA_AI_HERE"


def _subnet_broadcasts(ip):
    """Broadcast addresses for the /24 the given IP sits in.

    Sending to 255.255.255.255 goes out of every interface at once, which on a
    machine with VMware or similar virtual adapters lands on the wrong one.
    Targeting the /24 broadcast of a specific adapter keeps it on that line.
    """
    try:
        parts = ip.split(".")
        if len(parts) == 4:
            return [f"{parts[0]}.{parts[1]}.{parts[2]}.255"]
    except Exception:
        pass
    return []


def discover_host(port=DEFAULT_PORT, timeout=2.0, local_ip="", room="",
                  on_status=None):
    """Look for another assistant on the same network.

    local_ip picks which adapter to broadcast on (the UU one). room, when set,
    filters out assistants from a different co-op session.
    Returns the host's IP, or None.
    """
    targets = _subnet_broadcasts(local_ip) if local_ip else []
    targets.append("255.255.255.255")

    payload = DISCOVER_MAGIC
    if room:
        payload += b"|" + room.encode("utf-8", "replace")[:40]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    try:
        if local_ip:
            try:
                sock.bind((local_ip, 0))
            except OSError:
                pass
        for target in targets:
            try:
                sock.sendto(payload, (target, port + 1))
                if on_status:
                    on_status(f"正在 {target} 上找队友…")
            except OSError:
                continue
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data, addr = sock.recvfrom(512)
            except socket.timeout:
                break
            except OSError:
                break
            if not data.startswith(REPLY_MAGIC):
                continue
            # 回应格式：MAGIC|ip|port|room
            try:
                body = data.decode("utf-8", "replace").split("|")
                if room and len(body) >= 4 and body[3] and body[3] != room:
                    continue        # 不是同一个房间的
                return body[1] if len(body) >= 2 and body[1] else addr[0]
            except Exception:
                return addr[0]
    finally:
        sock.close()
    return None


def answer_discovery(port=DEFAULT_PORT, local_ip="", room="", on_found=None,
                     stop_flag=None):
    """Listen for discovery probes and answer with our own address.

    Runs until stop_flag() returns True (or forever when not given).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    bind_ip = local_ip or "0.0.0.0"
    try:
        sock.bind((bind_ip, port + 1))
    except OSError:
        try:
            sock.bind(("0.0.0.0", port + 1))
        except OSError:
            return None
    sock.settimeout(1.0)

    def loop():
        while True:
            if stop_flag and stop_flag():
                break
            try:
                data, addr = sock.recvfrom(512)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data.startswith(DISCOVER_MAGIC):
                continue
            want_room = ""
            if b"|" in data:
                want_room = data.split(b"|", 1)[1].decode("utf-8", "replace")
            if want_room and room and want_room != room:
                continue            # 不是同一个房间，不答
            reply = (REPLY_MAGIC + b"|" + (local_ip or "").encode() + b"|" +
                     str(port).encode() + b"|" + room.encode("utf-8", "replace"))
            try:
                sock.sendto(reply, addr)
            except OSError:
                pass
            if on_found:
                try:
                    on_found(addr[0])
                except Exception:
                    pass
        try:
            sock.close()
        except Exception:
            pass

    threading.Thread(target=loop, daemon=True).start()
    return sock

