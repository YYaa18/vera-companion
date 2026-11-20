"""人设（人格）管理：列出、读取、切换。

每个人设是 personas/ 下的一个 txt 文件。想加新的，扔个 txt 进去就行，
启动器的下拉框会自动列出来。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(_HERE) not in sys.path:
    sys.path.insert(0, os.path.dirname(_HERE))

import config

FOLDER = os.path.join(config.BUNDLE, "personas")
if not os.path.isdir(FOLDER):
    FOLDER = _HERE

# 显示名 -> 文件名（不含扩展名）。顺序就是下拉框顺序。
PRESETS = [
    ("温柔", "gentle"),
    ("呆萌", "cute"),
    ("鬼灵精怪", "mischief"),
    ("邪恶", "evil"),
]

DEFAULT = "gentle"

_DESC = {
    "gentle": "像朋友一样，轻松、有点俏皮，会紧张也会陪你",
    "cute": "有点笨但很努力，经常想歪，被纠正会恍然大悟",
    "mischief": "嘴快脑子快，爱逗你、爱抢答、爱给东西起外号",
    "evil": "在旁边看戏还想推你一把，语气慢，带点刺",
}


def _path(key):
    return os.path.join(FOLDER, f"{key}.txt")


def available():
    """[(display_name, key, description), ...] for every persona that exists."""
    out = []
    seen = set()
    for name, key in PRESETS:
        if os.path.exists(_path(key)):
            out.append((name, key, _DESC.get(key, "")))
            seen.add(key)
    # any extra files the user dropped in
    if os.path.isdir(FOLDER):
        for fn in sorted(os.listdir(FOLDER)):
            if not fn.lower().endswith(".txt"):
                continue
            key = fn[:-4]
            if key in seen:
                continue
            out.append((key, key, ""))
    return out


def key_for_name(display_name):
    for name, key, _ in available():
        if name == display_name:
            return key
    return DEFAULT


def name_for_key(key):
    for name, k, _ in available():
        if k == key:
            return name
    return key


def load(key=None):
    """Return the persona text; falls back to the default and then to a builtin."""
    key = key or DEFAULT
    p = _path(key)
    if not os.path.exists(p):
        p = _path(DEFAULT)
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                t = f.read().strip()
            if t:
                return t
        except Exception:
            pass
    # last resort: the old single-file locations
    for legacy in ("persona_voice.txt", "persona.txt"):
        lp = config.resource(legacy)
        if os.path.exists(lp):
            try:
                with open(lp, encoding="utf-8") as f:
                    t = f.read().strip()
                if t:
                    return t
            except Exception:
                pass
    return "你是「小蓝」，一条陪玩家玩《生化危机：代号维罗妮卡 X》的蓝色小鲸鱼。说话简短口语化，用中文。"
