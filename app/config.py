"""统一配置：API 密钥、语音设置、路径、进度记录。

所有设置存在 settings.json，由启动器和助手共同读写。
打包成 exe 后，settings.json 放在 exe 同目录（可写），资源从 exe 内部读。
"""
import json
import os
import sys
import time

FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    # exe 所在目录
    HERE = os.path.dirname(os.path.abspath(sys.executable))
    # 资源目录：PyInstaller 解包后的临时目录
    BUNDLE = getattr(sys, "_MEIPASS", HERE)
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
    BUNDLE = HERE


def _find_game_root(start):
    """Walk upwards looking for recvx.exe, so the app works wherever it is unpacked."""
    cur = os.path.abspath(start)
    for _ in range(4):
        if os.path.exists(os.path.join(cur, "recvx.exe")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.dirname(os.path.abspath(start))


GAME_ROOT = _find_game_root(HERE)


def _data_dir():
    """Where settings.json / progress.json live.

    The exe sits in the game root next to a source checkout; prefer that
    checkout's assistant folder so both builds share one config. Falls back
    to the exe's own directory when there is no checkout.
    """
    if FROZEN:
        sibling = os.path.join(GAME_ROOT, "assistant")
        if os.path.isdir(sibling) and os.path.exists(
                os.path.join(sibling, "config.py")):
            return sibling
    return HERE


DATA = _data_dir()
SETTINGS_PATH = os.path.join(DATA, "settings.json")
PROGRESS_PATH = os.path.join(DATA, "progress.json")

# ZCode 的 provider 配置，只在用户没填自己的 key 时作为后备
ZCODE_CONFIG = os.path.expandvars(r"%USERPROFILE%\.zcode\v2\provider_config.json")


def resource(name):
    """Path to a bundled read-only asset (persona, room_map...)."""
    bundled = os.path.join(BUNDLE, name)
    if os.path.exists(bundled):
        return bundled
    return os.path.join(HERE, name)

DEFAULTS = {
    "api_key": "",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-flash",
    "voice": "stella",
    "persona": "gentle",
    # AI 辅助程度：full / guide / none
    "help_level": "guide",
    "input_device": None,
    "output_device": None,
    # 游戏目录（含 recvx.exe）。空 = 自动探测。
    "game_dir": "",
    "iso_path": "",
    # 游戏联机的 8 位加入码（COPY JOIN ADDRESS 里 # 后面那串），用来拼完整地址
    "game_room_code": "",
    "auto_launch_assistant": True,
    "record_progress": True,
    "bubble_size": "normal",
    # 说话时把游戏音量压低（类似 Discord 的语音激活）
    "duck_game_audio": True,
    "duck_level": 0.22,
    # AI 之间的对话
    "peer_enabled": False,
    "peer_is_host": True,
    "peer_remote": "",
    "peer_port": 7150,
    # 房主监听的网卡 IP。空 = 所有网卡（0.0.0.0）。
    # 虚拟局域网下建议显式指定，避免广播落到 VMware 之类的虚拟网卡上。
    "peer_local_ip": "",
    "peer_name": "小蓝",
}


def load():
    cfg = dict(DEFAULTS)
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg.update({k: v for k, v in data.items() if k in DEFAULTS or k == "api_key"})
        except Exception:
            pass

    # 自动找 ISO
    if not cfg.get("iso_path") or not os.path.exists(cfg["iso_path"]):
        found = find_iso()
        if found:
            cfg["iso_path"] = found
    return cfg


def save(cfg):
    clean = {k: cfg.get(k, DEFAULTS[k]) for k in DEFAULTS}
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def find_game_dir():
    """Locate the folder holding recvx.exe.

    The installer puts the assistant somewhere like Program Files while the
    game lives wherever the user unpacked it, so guessing from our own path
    usually fails. Check the obvious places, then let the caller ask.
    """
    candidates = []

    cfg = load_cached() if "load_cached" in globals() else None
    try:
        cfg = cfg or load()
        if cfg.get("game_dir"):
            candidates.append(cfg["game_dir"])
    except Exception:
        pass

    # 安装包把 recvx.exe 放在 app 目录下的 game 子目录里
    if FROZEN:
        candidates.append(os.path.join(HERE, "game"))
    # 我们自己的位置（绿色版：exe 就在游戏目录里）
    candidates.append(GAME_ROOT)
    candidates.append(HERE)
    if FROZEN:
        candidates.append(os.path.dirname(os.path.abspath(sys.executable)))

    # 常见安装位置
    for drive in ("C", "D", "E", "F"):
        for name in ("RE-CodeVeronica-PC", "RE-CVX", "recvx-enhanced-port",
                     "ResidentEvilCVX"):
            candidates.append(os.path.join(drive + ":\\", name))
            candidates.append(os.path.join(drive + ":\\", "Games", name))

    for c in candidates:
        try:
            if c and os.path.exists(os.path.join(c, "recvx.exe")):
                return c
        except Exception:
            continue
    return ""


def resolve_game_dir():
    """The game folder to use right now."""
    try:
        cfg = load()
        if cfg.get("game_dir") and os.path.exists(
                os.path.join(cfg["game_dir"], "recvx.exe")):
            return cfg["game_dir"]
    except Exception:
        pass
    return find_game_dir()


def find_iso():
    """Look for a PS2 US image in the expected places."""
    candidates = [
        os.path.join(GAME_ROOT, "game"),
        os.path.join(GAME_ROOT, "assistant"),
        GAME_ROOT,
    ]
    for folder in candidates:
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if name.lower().endswith((".iso", ".bin", ".img")):
                return os.path.join(folder, name)
    return ""


def resolve_credentials(cfg=None):
    """Return (key, base_url, model, voice). Falls back to ZCode's config."""
    cfg = cfg or load()
    if cfg.get("api_key"):
        return (cfg["api_key"], cfg.get("base_url") or DEFAULTS["base_url"],
                cfg.get("model") or DEFAULTS["model"], cfg.get("voice") or DEFAULTS["voice"])

    if os.path.exists(ZCODE_CONFIG):
        try:
            with open(ZCODE_CONFIG, encoding="utf-8") as f:
                z = json.load(f)
            for rule in z["config"]["providerConfigRules"]["providerRules"]:
                api = rule.get("config", {}).get("api", {})
                if "deepseek" in str(api.get("baseUrl", "")):
                    return (rule["config"]["access"]["apiKey"],
                            api.get("baseUrl", "").rstrip("/"),
                            cfg.get("model") or DEFAULTS["model"],
                            cfg.get("voice") or DEFAULTS["voice"])
        except Exception:
            pass
    return None, cfg.get("base_url") or DEFAULTS["base_url"], \
           cfg.get("model") or DEFAULTS["model"], cfg.get("voice") or DEFAULTS["voice"]


def has_api_key(cfg=None):
    key, *_ = resolve_credentials(cfg)
    return bool(key)


# ---------------------------------------------------------------- progress

def load_progress():
    if not os.path.exists(PROGRESS_PATH):
        return {"rooms": {}, "sessions": 0, "first_seen": None}
    try:
        with open(PROGRESS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("rooms", {})
        data.setdefault("sessions", 0)
        data.setdefault("first_seen", None)
        return data
    except Exception:
        return {"rooms": {}, "sessions": 0, "first_seen": None}


def save_progress(p):
    try:
        with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def record_room(stage, room, label):
    """Note that the player has been in this room; returns True if it is new."""
    p = load_progress()
    key = f"{stage}:{room}"
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    if p["first_seen"] is None:
        p["first_seen"] = now
    seen = p["rooms"].get(key)
    if seen:
        p["rooms"][key] = {
            "label": label,
            "visits": seen.get("visits", 1) + 1,
            "last": now,
        }
        save_progress(p)
        return False
    p["rooms"][key] = {"label": label, "visits": 1, "last": now}
    save_progress(p)
    return True
