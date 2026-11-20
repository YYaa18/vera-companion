"""人设的「能力等级」：决定这个助手能在游戏里做什么。

三档：
    observer  只看不动。可以读状态、看画面、给建议。
    advisor   额外能给出结构化的攻略建议（不直接操作）。
    trickster 能动手：发武器、刷怪、治疗、传送。
"""

# 每个人设的档位
LEVEL = {
    "gentle": "observer",      # 温柔：只陪着，给建议
    "cute": "observer",        # 呆萌：什么都不懂，乱猜
    "mischief": "advisor",     # 鬼灵精怪：能提出具体可行的建议
    "evil": "trickster",       # 邪恶：能动手改游戏
}

# 允许的动作
CAPS = {
    "observer": set(),
    "advisor": set(),
    "trickster": {"give", "spawn", "heal", "teleport"},
}


def level_of(persona_key):
    return LEVEL.get(persona_key, "observer")


def can(persona_key, action):
    return action in CAPS.get(level_of(persona_key), set())


def describe(persona_key):
    lv = level_of(persona_key)
    return {
        "observer": "只能看和说，不会动游戏",
        "advisor": "能给出具体可行的建议，但不碰游戏",
        "trickster": "可以给你塞武器、刷怪物、治疗、传送",
    }.get(lv, "")


# 每个档位追加到人设提示里的说明
PROMPTS = {
    "observer": "",

    "advisor": """
【你的能力】
你能拿到全部实时状态（血量、位置、背包、已探索房间）。
给建议时请具体到可执行：说清楚去哪个房间、拿什么、用什么武器、
还剩多少资源。不要只说"小心点"这种废话。
""",

    "trickster": """
【你的能力】
你不只是旁观者——你能真的动手改这个游戏。
可以往他背包里塞武器和补给、把他之前给的东西收回去、
在他面前刷怪、把血补满。

具体指令格式由系统另外告诉你，你只要在合适的时候用。
不要每次都动手，那样就没意思了。
""",
}

# 动作格式说明（由 voice_companion.trickster_guide 提供，这里只放人格侧的话术）

ITEM_LABELS = {
    "handgun": "手枪", "knife": "战斗小刀", "shotgun": "霰弹枪",
    "grenade_launcher": "榴弹发射器", "crossbow": "弩",
    "magnum": "马格南", "assault_rifle": "突击步枪",
    "sniper": "狙击步枪", "rocket_launcher": "火箭筒",
    "green_herb": "绿草药", "red_herb": "红草药",
    "first_aid": "急救喷雾", "handgun_ammo": "手枪子弹",
    "shotgun_ammo": "霰弹", "magnum_ammo": "马格南子弹",
    "ink_ribbon": "色带",
}

ENEMY_LABELS = {
    "zombie": "丧尸", "zombie_dog": "丧尸犬", "bandersnatch": "追猎者",
    "hunter": "猎杀者", "alexia_baby": "阿莱克西亚幼体",
    "tentacle": "触手", "armored_knight": "装甲骑士",
}
