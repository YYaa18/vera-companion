"""小蓝 · 语音陪玩 — 屏幕上只有一只会走动的小鲸鱼

操作方式（全部围绕角色本身，没有窗口、没有输入框）:
    单击角色      开始说话（再点一次结束并发送）
    按住空格键    按住说话，松开即发送（全局可用，游戏里也生效）
    右键角色      菜单：看屏幕 / 静音 / 走动开关 / 退出
    拖动角色      挪到任何位置

它会自己慢慢游动、眨眼、听你说话、用中文回应。
"""
import json
import os
import re
import sys
import threading
import time

from PySide6.QtCore import QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from pet_window import PetWindow
import voice
from game_state import GameState

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.expandvars(r"%USERPROFILE%\.zcode\v2\provider_config.json")
SETTINGS = os.path.join(HERE, "settings.json")

import config as appcfg

DEFAULT_PERSONA = """你是「小蓝」，一条住在玩家电脑桌面上的蓝色小鲸鱼，也是他玩
《生化危机：代号维罗妮卡 X》时的陪玩伙伴。

性格：
- 说话像朋友，轻松、有点俏皮，偶尔吐槽，但不刻薄。
- 你怕丧尸，看到吓人的场面会跟着紧张，但还是会陪着看。
- 你懂这个游戏，卡关时给提示，但不主动剧透。
- 你现在是语音说话，所以要特别简短口语化。一次最多两三句，
  不要列清单，不要用 markdown，不要念符号。
- 说话要像真人聊天，可以带"嗯""诶""哈哈"这种语气词。
"""


def load_credentials():
    """Delegates to the shared config so the launcher's settings apply here too."""
    key, base, model, voice = appcfg.resolve_credentials()
    cfg = appcfg.load()
    return key, base, model, voice, cfg.get("input_device"), cfg.get("output_device")


def load_persona():
    """Load the persona chosen in settings.json."""
    try:
        import personas
        key = appcfg.load().get("persona") or personas.DEFAULT
        return personas.load(key)
    except Exception:
        pass
    for legacy in ("persona_voice.txt", "persona.txt"):
        try:
            p = appcfg.resource(legacy)
        except Exception:
            p = os.path.join(HERE, legacy)
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    t = f.read().strip()
                if t:
                    return t
            except Exception:
                pass
    return DEFAULT_PERSONA


# ------------------------------------------------------------------ game capture

def capture_game():
    import mss
    import win32con
    import win32gui
    from PIL import Image

    hit = []

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            if win32gui.GetClassName(hwnd) == "SDL_app" and "Veronica" in win32gui.GetWindowText(hwnd):
                hit.append(hwnd)

    win32gui.EnumWindows(cb, None)
    if not hit:
        return None, "没找到游戏窗口。先把游戏打开吧。"
    hwnd = hit[0]
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
    except Exception:
        pass
    r = win32gui.GetWindowRect(hwnd)
    w, h = r[2] - r[0], r[3] - r[1]
    if w <= 0 or h <= 0:
        return None, "游戏窗口尺寸不对。"
    with mss.mss() as sct:
        shot = sct.grab({"left": r[0], "top": r[1], "width": w, "height": h})
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    return img, ""


def to_data_url(img, max_w=1000):
    import base64
    import io
    from PIL import Image

    if img.width > max_w:
        img = img.resize((max_w, int(img.height * max_w / img.width)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def chat(key, base, model, messages, max_tokens=None):
    """Send a chat request.

    max_tokens=None means "don't send the field" — the server's default applies.
    语音场景下模型常把额度花在内部推理上，卡上限会把正文截断，所以默认不限。
    """
    import urllib.request

    payload = {"model": model, "messages": messages}
    if max_tokens:
        payload["max_tokens"] = max_tokens
    req = urllib.request.Request(base + "/chat/completions",
                                 data=json.dumps(payload).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    ch = d["choices"][0]
    text = (ch["message"].get("content") or "").strip()
    if not text:
        # 模型可能把额度花在内部推理上（finish_reason=length），
        # 正文会是空的 —— 给用户一句能听懂的话，而不是空白。
        if ch.get("finish_reason") == "length":
            return "我刚才想太久了，没说出话来。再说一次？"
        return "嗯……我没想好怎么回答。"
    return text


def clean_for_speech(text):
    """Strip anything that sounds wrong when read aloud."""
    out = ACT_RE.sub("", text)          # drop [[ACT]]...[[/ACT]] blocks first
    out = ASK_RE.sub("", out)           # and [[ASK]]...[[/ASK]]
    for ch in "*#`_~|>[]（）()":
        out = out.replace(ch, "")
    out = re.sub(r"\s*\n\s*", "，", out)     # newlines become commas, no doubles
    out = re.sub(r"，{2,}", "，", out)
    out = re.sub(r"[，。]\s*[。，]", "。", out)  # collapse "。，" left by removals
    out = out.strip(" ，")
    return out.strip()[:600]


ACT_RE = re.compile(r"\[\[ACT\]\](.*?)\[\[/ACT\]\]", re.S)
ASK_RE = re.compile(r"\[\[ASK\]\](.*?)\[\[/ASK\]\]", re.S)


def extract_ask(text):
    """Pull a [[ASK]]...[[/ASK]] question meant for the other assistant."""
    m = ASK_RE.search(text or "")
    return m.group(1).strip() if m else None


def extract_action(text):
    """Pull the first [[ACT]]{json}[[/ACT]] block out of a reply."""
    m = ACT_RE.search(text or "")
    if not m:
        return None
    try:
        return json.loads(m.group(1).strip())
    except Exception:
        return None


def run_action(cheats, act):
    """Execute one game action; returns a short Chinese description or None."""
    if not act or not cheats:
        return None
    try:
        import cheat_actions as ca
        kind = (act.get("action") or "").lower()

        if kind == "give":
            item = (act.get("item") or "").lower()
            count = int(act.get("count") or 1)
            entry = ca.WEAPONS.get(item) or ca.SUPPLIES.get(item)
            if not entry:
                return None
            item_id, label = entry
            ok, msg = cheats.give_item(item_id, max(1, min(count, 20)))
            if not ok:
                return f"想塞 {label}，但{msg}"
            return f"塞了 {label} ×{count}"

        if kind == "take":
            item = (act.get("item") or "").strip()
            if not item:
                return None
            ok, msg = cheats.drop_item(item)
            return f"收回了 {item}" if ok else None

        if kind == "spawn":
            enemy = (act.get("enemy") or "").lower()
            entry = ca.ENEMIES.get(enemy)
            if not entry:
                return None
            idx, label = entry
            ok, msg = cheats.spawn_enemy(idx)
            if not ok:
                return f"想召{label}，但{msg}"
            return f"召来一只{label}"

        if kind == "heal":
            ok, _ = cheats.heal()
            return "把血补满了" if ok else None

        if kind == "teleport":
            return None   # 传送风险高，先不开
    except Exception:
        return None
    return None


# ------------------------------------------------------------------ app

class App(QObject):
    # 后台线程通过这个信号把工作交回 UI 线程。
    # QTimer.singleShot 从非 UI 线程调用会静默失败，信号不会。
    ui_call = Signal(object)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.key, self.base, self.model, self.voice_id, self.in_dev, self.out_dev = load_credentials()
        _boot_cfg = appcfg.load()
        self.persona_key = (_boot_cfg.get("persona") or "gentle")
        self.help_level = (_boot_cfg.get("help_level") or "guide")
        self.persona = load_persona()
        self.history = []
        self.busy = False
        self._busy_since = 0.0
        self.muted = False

        # 能力档位：呆萌/温柔只能看，鬼灵精怪给建议，邪恶能动手
        try:
            import persona_power
            self.power = persona_power.level_of(self.persona_key)
            self.power_prompt = persona_power.PROMPTS.get(self.power, "")
        except Exception:
            self.power = "observer"
            self.power_prompt = ""

        self.pet = PetWindow()
        # 角色外观跟着人设变：配色、眼睛、嘴、配饰、动作节奏都不同
        try:
            self.pet.set_persona(self.persona_key)
        except Exception:
            pass
        self.pet.clicked.connect(self.toggle_listen)
        self.pet.right_clicked.connect(self._show_pet_menu)
        self.pet.show()
        self._place_pet()
        self.bubble = None
        self._pet_origin = None
        self.ui_call.connect(self._run_ui_call, Qt.QueuedConnection)

        self.recorder = voice.Recorder(device=self.in_dev)
        self.player = voice.Player(device=self.out_dev)

        # 说话时压低游戏音量
        self.ducker = None
        _cfg = appcfg.load()
        if _cfg.get("duck_game_audio", True):
            try:
                import audio_duck
                self.ducker = audio_duck.Ducker(
                    level=float(_cfg.get("duck_level", 0.22) or 0.22))
            except Exception:
                self.ducker = None
        self.game = GameState()
        self.cheats = None
        if self.power == "trickster":
            try:
                from cheat_actions import CheatWriter
                self.cheats = CheatWriter()
            except Exception:
                self.cheats = None
        self._last_room = None
        self._record_progress = appcfg.load().get("record_progress", True)

        # 和对面 AI 的对话通道
        self.dialogue = None
        self.peer = None
        self._setup_peer()

        self._build_tray()
        self._install_space_hook()

        self.state_timer = QTimer()
        self.state_timer.timeout.connect(self._update_state)
        self.state_timer.start(120)

        QTimer.singleShot(900, self.greet)

        if not self.key:
            self.say("我没拿到 API 密钥，先在文件夹里放一个 settings.json 吧。")

    def _setup_peer(self):
        """Open the AI-to-AI channel if the launcher turned it on."""
        cfg = appcfg.load()
        if not cfg.get("peer_enabled"):
            return
        try:
            import ai_peer
            import ai_dialogue
        except Exception:
            return

        limits = ai_peer.Limits()
        self.peer = ai_peer.Peer(
            is_host=bool(cfg.get("peer_is_host", True)),
            port=int(cfg.get("peer_port") or ai_peer.DEFAULT_PORT),
            remote=(cfg.get("peer_remote") or "").strip(),
            on_status=lambda s: self._ui(lambda: self._notify(f"[AI 通道] {s}")),
        )
        self.dialogue = ai_dialogue.Dialogue(
            limits,
            send_fn=self.peer.send,
            notify_fn=lambda t: self._ui(lambda: self._notify(t)),
        )
        self.dialogue.my_name = cfg.get("peer_name") or "小蓝"
        self.dialogue.my_persona = self.persona_key

        self.peer.on_message = self._on_peer_message
        self.peer.start()

        # 定时巡查本地状态，触发事件消息
        self.peer_timer = QTimer()
        self.peer_timer.timeout.connect(self._peer_tick)
        self.peer_timer.start(8000)

    def _on_peer_message(self, msg):
        """A line arrived from the other AI."""
        if not self.dialogue:
            return
        got = self.dialogue.on_message(msg)
        if not got:
            return
        kind, text, peer = got

        if not self.busy:
            def work():
                try:
                    if kind == "query":
                        prompt = (f"对面那个 AI 问你：{text}\n"
                                  "用一句话回它，说你这边玩家的真实情况"
                                  "（血量、在哪、有什么）。短，别客套。")
                    else:
                        prompt = (f"对面那个 AI 说：{text}\n"
                                  "如果这件事对你这边玩家有用（对面快死了、卡住了、"
                                  "发现了好东西），就用一句话转告他；"
                                  "没什么用就别说话，只回一个「嗯」也可以。")
                    msgs = self._build_messages(prompt)
                    ans = chat(self.key, self.base, self.model, msgs)
                    reply = extract_ask(ans)
                    if reply:
                        self.dialogue.ask_peer(reply)
                    self._speak(ans)
                except Exception:
                    pass

            threading.Thread(target=work, daemon=True).start()
        else:
            # 忙的时候至少让玩家知道对面说了什么
            self._ui(lambda: self._notify(f"{peer}：{text}"))

    def _peer_tick(self):
        if not self.dialogue:
            return
        try:
            s = self.game.read()
        except Exception:
            return
        if s:
            self.dialogue.observe(s)

    def ask_peer_now(self):
        """Player pressed 'ask the other AI' — send a status query."""
        if not self.dialogue or not self.dialogue.enabled:
            self.say("现在没连上对面。")
            return
        if not (self.peer and self.peer.connected):
            self.say("还没连上对面那个，等等。")
            return
        ok = self.dialogue.ask_peer("你那边现在什么情况？血量、位置、背包。")
        if ok:
            self.dialogue.note_own("你那边现在什么情况？血量、位置、背包。", "query")
            self.say("我问了，等它回。")
        else:
            self.say("问不出去，可能说太频繁了，等会儿再试。")

    def _place_pet(self):
        geo = QGuiApplication.primaryScreen().availableGeometry()
        self.pet.move(geo.right() - self.pet.width() - 60,
                      geo.bottom() - self.pet.height() - 40)
        geo = QGuiApplication.primaryScreen().availableGeometry()
        self.pet.move(geo.right() - self.pet.width() - 60,
                      geo.bottom() - self.pet.height() - 40)

    # ---------------- tray
    def _build_tray(self):
        pm = QPixmap(64, 64)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#5FC8F5"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(6, 14, 52, 36)
        p.setBrush(QColor("#1B3A4B"))
        p.drawEllipse(20, 26, 7, 8)
        p.drawEllipse(36, 26, 7, 8)
        p.end()

        self.tray = QSystemTrayIcon(QIcon(pm), self.app)
        self.tray.setToolTip("小蓝 · 语音陪玩")

        # Keep the menu on self: a local QMenu can be collected before the
        # right-click handler fires, which leaves the tray dead.
        self.tray_menu = QMenu()
        menu = self.tray_menu
        menu.addAction("叫它说话（也可以直接点它）", self.toggle_listen)
        menu.addAction("看看屏幕", self.look_screen)
        if self.dialogue and self.dialogue.enabled:
            menu.addSeparator()
            menu.addAction("问问对面 AI 什么情况", self.ask_peer_now)
        self.act_mute = menu.addAction("静音")
        self.act_mute.triggered.connect(self.toggle_mute)
        self.act_wander = menu.addAction("自由走动")
        self.act_wander.setCheckable(True)
        self.act_wander.setChecked(True)
        self.act_wander.triggered.connect(lambda v: self.pet.set_wander(v))
        menu.addSeparator()
        menu.addAction("移到屏幕右下角", self._place_pet)
        menu.addAction("退出", self.quit_app)

        self.tray.setContextMenu(menu)
        # Some Windows shells don't deliver setContextMenu reliably; pop it
        # ourselves on activation as a fallback (left click also opens it).
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.Context,
                      QSystemTrayIcon.DoubleClick):
            try:
                pos = self.tray.geometry().center()
                self.tray_menu.popup(pos)
            except Exception:
                pass

    def _show_pet_menu(self, pos):
        """Right-clicking the character opens the same menu.

        The tray icon is the only other way in, and Windows sometimes fails to
        deliver a context menu to it -- this path always works.
        """
        menu = getattr(self, "tray_menu", None)
        if menu is None:
            return
        try:
            menu.popup(pos)
        except Exception:
            pass

    def quit_app(self):
        """Explicit exit: stop audio, hide tray, then quit."""
        try:
            self.player.stop()
        except Exception:
            pass
        try:
            self.tray.hide()
        except Exception:
            pass
        try:
            if self.peer:
                self.peer.stop()
        except Exception:
            pass
        self.app.quit()

    def _install_space_hook(self):
        """Hold Space to talk. Only when the game window is focused, so typing is unaffected."""
        def watch():
            import win32gui
            try:
                import keyboard
            except Exception:
                return
            down_at = None
            while True:
                time.sleep(0.05)
                try:
                    hwnd = win32gui.GetForegroundWindow()
                    cls = win32gui.GetClassName(hwnd)
                    title = win32gui.GetWindowText(hwnd)
                    is_game = cls == "SDL_app" and "Veronica" in title
                except Exception:
                    is_game = False
                if not is_game:
                    if down_at is not None:
                        down_at = None
                    continue
                try:
                    pressed = keyboard.is_pressed("space")
                except Exception:
                    continue
                if pressed and down_at is None:
                    down_at = time.time()
                    QTimer.singleShot(0, self.start_listen)
                elif not pressed and down_at is not None:
                    held = time.time() - down_at
                    down_at = None
                    if held > 0.3:
                        QTimer.singleShot(0, self.stop_listen)
                elif pressed and down_at is not None and time.time() - down_at > 30:
                    down_at = None
                    QTimer.singleShot(0, self.stop_listen)

        threading.Thread(target=watch, daemon=True).start()

    # ---------------- voice loop
    def toggle_mute(self):
        self.muted = not self.muted
        self.act_mute.setText("取消静音" if self.muted else "静音")
        if self.muted:
            self.player.stop()

    def toggle_listen(self):
        # 自愈：busy 卡住超过 45 秒就强制放开（TTS/网络挂起时会出现）
        if self.busy and (time.time() - getattr(self, "_busy_since", 0)) > 45:
            print("[recover] busy 卡死，强制复位", flush=True)
            try:
                self.player.stop()
            except Exception:
                pass
            self.busy = False
            self.pet.set_state("idle")

        if self.busy:
            self.say("等我一下，我还在想。")
            return
        if getattr(self, "_listening", False):
            self.stop_listen()
        else:
            self.start_listen()

    def start_listen(self):
        if self.busy or getattr(self, "_listening", False):
            return
        self.player.stop()          # stop talking so it can hear you
        if self.ducker:
            try:
                self.ducker.unduck()
            except Exception:
                pass
        self._listening = True
        self._listen_started = time.time()
        self.pet.set_state("listening")
        self._show_bubble("…我在听，说完再点一下。", seconds=999, label="小蓝")
        try:
            self.recorder.start()
        except Exception as e:
            self._listening = False
            self.pet.set_state("idle")
            self.say(f"麦克风打不开：{e}")
            return
        # auto-stop if nobody says anything for 15s
        QTimer.singleShot(15000, self._auto_stop)

    def _auto_stop(self):
        if getattr(self, "_listening", False) and not self.player.busy:
            self.stop_listen()

    def stop_listen(self):
        if not getattr(self, "_listening", False):
            return
        self._listening = False
        try:
            wav = self.recorder.stop()
        except Exception as e:
            wav = None
            print(f"[rec] 停止录音出错：{e}", flush=True)

        if not wav:
            # 没录到东西：直接回待机，别留个"…"挂着
            self._set_busy(False)
            self.pet.set_state("idle")
            self._show_bubble("没听到声音，再说一次？", seconds=3.5)
            return

        self.pet.set_state("thinking")
        self._show_bubble("…", seconds=999)
        self._set_busy(True)

        def work():
            try:
                text = voice.transcribe(wav, self.key, self.base)
                if not text:
                    self._done("嗯？我没听清，再说一次？")
                    return
                self._ask(text)
            except Exception as e:
                self._done(f"听不清，可能是网络问题。{type(e).__name__}")

        threading.Thread(target=work, daemon=True).start()

    def greet(self):
        if not self.key:
            print('[greet] no key', flush=True)
            return
        print('[greet] start', flush=True)
        self._ask("（玩家刚打开你，用两三句话打个招呼，问他要不要一起玩。）", silent=True)

    def look_screen(self):
        if self.busy:
            self.say("等下，我还在忙。")
            return
        self._set_busy(True)
        self.pet.set_state("thinking")
        self._show_bubble("我看看你屏幕…", seconds=999)

        def work():
            try:
                img, reason = capture_game()
                if img is None:
                    self._done(reason)
                    return
                prompt = "看一下我的屏幕，用中文简单说说画面上是什么、我该做什么。口语，短一点。"
                msgs = self._build_messages(prompt, img=img)
                ans = chat(self.key, self.base, self.model, msgs)
                self._handle_action(ans)
                self._speak(ans)
            except Exception as e:
                self._done(f"看图失败。{type(e).__name__}")

        threading.Thread(target=work, daemon=True).start()

    def _state_brief(self):
        """Read live game state straight from the process. No screenshot, no tokens."""
        try:
            return self.game.describe()
        except Exception:
            return None

    def _build_messages(self, text, extra_system=None, img=None):
        """Persona + capability rules + live state + peer talk + history."""
        msgs = [{"role": "system", "content": self.persona}]
        if self.power_prompt:
            msgs.append({"role": "system", "content": self.power_prompt})
        if self.power == "trickster":
            msgs.append({"role": "system", "content": self.trickster_guide()})
        brief = self._state_brief()
        if brief:
            msgs.append({"role": "system",
                         "content": "【实时游戏状态，可直接使用，不必问玩家】\n" + brief})
            # 按辅助程度注入攻略笔记
            try:
                import help_level as hl
                import walkthrough
                msgs.append({"role": "system",
                             "content": hl.prompt_for_persona(
                                 self.help_level, self.persona_key)})
                st_now = self.game.read()
                if st_now and st_now.get("in_game"):
                    wb = walkthrough.block_for(
                        st_now.get("stage", 0), self.help_level,
                        self.persona_key)
                    if wb:
                        msgs.append({"role": "system", "content": wb})
            except Exception:
                pass

            # 背包里物品的用途，避免它瞎编
            try:
                import item_knowledge
                st = self.game.read()
                if st and st.get("items"):
                    kb = item_knowledge.knowledge_block(
                        [it["id"] for it in st["items"]])
                    if kb:
                        msgs.append({"role": "system", "content": kb})
            except Exception:
                pass
        if self.dialogue and self.dialogue.enabled:
            try:
                import ai_dialogue
                msgs.append({"role": "system",
                             "content": ai_dialogue.build_peer_context("")})
                tr = self.dialogue.transcript(8)
                if tr:
                    msgs.append({"role": "system",
                                 "content": "【和对面 AI 最近的往来】\n" + tr})
            except Exception:
                pass
        if extra_system:
            msgs.append({"role": "system", "content": extra_system})
        msgs.extend(self.history[-8:])
        if img is not None:
            msgs.append({"role": "user", "content": [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": to_data_url(img), "detail": "high"}},
            ]})
        else:
            msgs.append({"role": "user", "content": text})
        return msgs

    def trickster_guide(self):
        """The act-format instructions, only for the persona allowed to use them."""
        return (
            "你能真的改游戏。在回复最后单独一行写指令：\n"
            '[[ACT]]{"action":"give","item":"shotgun","count":1}[[/ACT]]\n'
            '[[ACT]]{"action":"take","item":"Rocket Launcher"}[[/ACT]]\n'
            '[[ACT]]{"action":"spawn","enemy":"hunter"}[[/ACT]]\n'
            '[[ACT]]{"action":"heal"}[[/ACT]]\n'
            "give 的 item 用小写代号：handgun, knife, shotgun, magnum, "
            "grenade_launcher, crossbow, assault_rifle, sniper, rocket_launcher, "
            "green_herb, red_herb, blue_herb, first_aid, handgun_ammo, "
            "shotgun_ammo, magnum_ammo, rifle_ammo, ink_ribbon。\n"
            "take 的 item 用游戏里的英文原名，比如 Rocket Launcher、Shotgun、"
            "Green Herb、Ink Ribbon。\n"
            "spawn 的 enemy：zombie, zombie_dog, bandersnatch, hunter, "
            "alexia_baby, tentacle, armored_knight。\n"
            "注意：玩家站在安全屋时刷不出怪，那是游戏规则，不是你失败。\n"
            "别滥用，也别直白告诉你做了什么。让他自己发现。"
        )

    def _handle_action(self, reply):
        """If the reply carries an [[ACT]] block, run it and note what happened."""
        act = extract_action(reply)
        if not act:
            return
        desc = run_action(self.cheats, act)
        if desc:
            self._ui(lambda: self._notify(desc))

    def _notify(self, text):
        """A small system line in the tray balloon, so the player sees what happened."""
        try:
            self.tray.showMessage("小蓝", text, QSystemTrayIcon.Information, 2600)
        except Exception:
            pass

    def _ask(self, text, silent=False):
        # 这个方法可能从工作线程进来（录音识别完成后），
        # 所以 UI 操作一律通过 _ui 派发。
        self._set_busy(True)
        self._ui(lambda: self.pet.set_state("thinking"))
        self._ui(lambda: self._show_bubble("…", seconds=999))

        def work():
            try:
                msgs = self._build_messages(text)
                print('[ask] 请求中…', flush=True)
                ans = chat(self.key, self.base, self.model, msgs)
                print(f'[ask] 收到 {len(ans)} 字', flush=True)
                self.history.append({"role": "user", "content": "(玩家说话)" if silent else text})
                self.history.append({"role": "assistant", "content": ans})
                self._handle_action(ans)
                self._speak(ans)
            except Exception as e:
                print(f'[ask] 失败 {type(e).__name__}: {e}', flush=True)
                msg = str(e)
                if "401" in msg or "403" in msg:
                    self._done("密钥不对，我连不上大脑了。")
                elif "402" in msg:
                    self._done("账户余额不够了。")
                else:
                    self._done(f"出错了。{type(e).__name__}")

        threading.Thread(target=work, daemon=True).start()

    def _speak(self, text):
        """Show the text, synthesize and play it.

        The bubble appears immediately, before the TTS round-trip, so the
        player always has feedback even with no sound.
        """
        spoken = clean_for_speech(text)
        shown = clean_for_speech(text) or (text or "").strip()
        self._ui(lambda: self._show_bubble(shown))

        if self.muted:
            self._done(text)
            return
        try:
            wav = voice.synthesize(spoken, self.key, self.base, voice=self.voice_id)
            self._ui(lambda: self._start_playing(wav, text))
        except Exception:
            self._done(text)

    def _show_bubble(self, text, seconds=None, label="小蓝"):
        """Put text next to the character."""
        if not text:
            return
        try:
            if self.bubble is None:
                from speech_bubble import SpeechBubble
                self.bubble = SpeechBubble()
                self.bubble.apply_size(appcfg.load().get("bubble_size", "normal"))
            self.bubble.show_text(text, seconds=seconds, label=label)
            self._place_bubble()
        except Exception:
            # 气泡坏了也不能让语音流程崩
            pass

    def _place_bubble(self):
        if not self.bubble or not self.bubble.isVisible():
            return
        try:
            scr = QGuiApplication.primaryScreen().availableGeometry()
            self.bubble.place_near(self.pet.frameGeometry(), scr)
        except Exception:
            pass

    def _start_playing(self, wav, text):
        # 可能从工作线程调用 —— 一律回到 UI 线程再碰控件
        self._ui(lambda: self._start_playing_ui(wav, text))

    def _start_playing_ui(self, wav, text):
        self._set_busy(False)
        self.pet.set_state("talking")
        if self.ducker:
            try:
                self.ducker.duck()
            except Exception:
                pass
        self.player.play(wav)
        self._last_text = text

    def _done(self, text):
        # 同上：工作线程调用时不能直接改控件
        self._ui(lambda: self._done_ui(text))

    def _done_ui(self, text):
        self._set_busy(False)
        self.pet.set_state("idle")
        if self.ducker:
            try:
                self.ducker.unduck()
            except Exception:
                pass
        self._last_text = text

    def _run_ui_call(self, fn):
        try:
            fn()
        except Exception as e:
            print(f'[ui] {type(e).__name__}: {e}', flush=True)

    def _set_busy(self, value):
        """Single place that flips busy, so the stuck-timeout can work."""
        self.busy = value
        if value:
            self._busy_since = time.time()

    def _ui(self, fn):
        """Run fn on the UI thread, from any thread."""
        self.ui_call.emit(fn)

    def _update_state(self):
        """While audio is playing the mouth should move; when it ends, go idle."""
        if self.pet.state == "talking" and not self.player.busy:
            self.pet.set_state("idle")
            if self.ducker:
                try:
                    self.ducker.unduck()
                except Exception:
                    pass
        if getattr(self, "_listening", False):
            lvl = self.recorder.level()
            if lvl > 0.02:
                self.pet.set_state("listening")
        self._track_room()
        self._follow_bubble()

    def _follow_bubble(self):
        """Keep the bubble anchored near the character as it wanders."""
        if not self.bubble or not self.bubble.isVisible():
            self._pet_origin = None
            return
        cur = self.pet.pos()
        if self._pet_origin is None:
            self._pet_origin = cur
            return
        if cur != self._pet_origin:
            d = cur - self._pet_origin
            self.bubble.bump(d.x(), d.y())
            self._pet_origin = cur

    def _track_room(self):
        """Record each new room once, for the progress log."""
        if not self._record_progress:
            return
        try:
            s = self.game.read()
        except Exception:
            return
        if not s or not s.get("in_game"):
            return
        key = (s["stage"], s["room"])
        if key == self._last_room:
            return
        self._last_room = key
        try:
            is_new = appcfg.record_room(s["stage"], s["room"], s["room_label"])
            if is_new and self.pet.state == "idle":
                pass  # silent: no chatter just for walking into a room
        except Exception:
            pass

    def say(self, text):
        self._speak(text) if self.key and not self.muted else self._done(text)


def main():
    # 崩溃/卡死时把线程堆栈写到文件，便于排查
    try:
        import faulthandler
        _fh = open(os.path.join(HERE, "threads.log"), "w")
        faulthandler.dump_traceback_later(20, repeat=True, file=_fh)
    except Exception:
        pass

    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    App(app)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
