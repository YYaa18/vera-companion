"""人设的视觉主题：配色、配饰、表情风格、动作节奏。

改这个文件就能调整每个角色长什么样，不需要动绘制逻辑。

四种人设的视觉语言：
  温柔   浅蓝、软围巾、下垂眼角、慢呼吸
  呆萌   亮青、呆毛 + 围嘴、大而无神的眼、晃脑袋
  鬼灵精怪 青绿、护目镜、单边挑眉、弹性跳动
  邪恶   暗紫蓝、小角 + 项圈、竖瞳、低伏静止
"""
from PySide6.QtGui import QColor

THEMES = {
    "gentle": {
        "label": "温柔",
        "body_light": QColor("#B2EAFF"),
        "body_mid": QColor("#79CDEF"),
        "body_deep": QColor("#4A9EC6"),
        "fin_light": QColor("#A4E2FA"),
        "fin_dark": QColor("#63B4D9"),
        "belly": QColor("#EAF9FF"),
        "blush": QColor("#FFB3C6"),
        "blush_alpha": 105,
        "line": QColor("#2A5A72"),
        "eye_style": "soft",
        "mouth_style": "smile",
        "accessory": "scarf",
        "breathe_hz": 2.0,      # 呼吸频率
        "breathe_amp": 0.018,
        "tilt": 0.0,            # 身体倾斜（度）
        "bounce": 0.0,          # 弹跳幅度
    },

    "cute": {
        "label": "呆萌",
        "body_light": QColor("#A8F0FF"),
        "body_mid": QColor("#63D2F7"),
        "body_deep": QColor("#38A3CC"),
        "fin_light": QColor("#9DE8FF"),
        "fin_dark": QColor("#54BCE0"),
        "belly": QColor("#F0FCFF"),
        "blush": QColor("#FFA8BD"),
        "blush_alpha": 130,
        "line": QColor("#1E4C63"),
        "eye_style": "blank",
        "mouth_style": "small_o",
        "accessory": "tuft",
        "breathe_hz": 2.6,
        "breathe_amp": 0.024,
        "tilt": 4.0,
        "bounce": 0.4,
    },

    "mischief": {
        "label": "鬼灵精怪",
        "body_light": QColor("#9FF5E4"),
        "body_mid": QColor("#54D9C4"),
        "body_deep": QColor("#2E9A93"),
        "fin_light": QColor("#8FEFE0"),
        "fin_dark": QColor("#45B8AE"),
        "belly": QColor("#E6FFF9"),
        "blush": QColor("#FFB07A"),
        "blush_alpha": 110,
        "line": QColor("#175055"),
        "eye_style": "sly",
        "mouth_style": "smirk",
        "accessory": "goggles",
        "breathe_hz": 3.2,
        "breathe_amp": 0.020,
        "tilt": -3.0,
        "bounce": 0.8,
    },

    "evil": {
        "label": "邪恶",
        "body_light": QColor("#8FA8D8"),
        "body_mid": QColor("#5A72A8"),
        "body_deep": QColor("#2C3A63"),
        "fin_light": QColor("#7E96C8"),
        "fin_dark": QColor("#3E5285"),
        "belly": QColor("#B8C4E0"),
        "blush": QColor("#8A5A78"),
        "blush_alpha": 70,
        "line": QColor("#0B1020"),
        "eye_style": "evil",
        "mouth_style": "flat",
        "accessory": "horns",
        "breathe_hz": 1.4,
        "breathe_amp": 0.012,
        "tilt": 0.0,
        "bounce": 0.0,
    },
}

DEFAULT = "gentle"


def get(key):
    return THEMES.get(key or DEFAULT, THEMES[DEFAULT])
