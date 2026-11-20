"""AI 辅助程度：决定它帮到什么份上。

三档：
  full    全开 —— 直接告诉你下一步做什么、谜题怎么解、该拿什么
  guide   引导 —— 只给方向和提示，不直接说答案
  none    啥也不清楚 —— 陪你玩、描述画面，但不给攻略

设计要点：
  · 这是玩家自己的选择，不是 AI 的心情
  · 档位影响注入的攻略知识量、以及 prompt 里的行为约束
  · 「呆萌」人设本身就设定为不懂游戏，档位对它影响有限（会额外说明）
"""

LEVELS = {
    "full": {
        "label": "全开",
        "desc": "直接告诉你该做什么、谜题怎么解、下一步去哪",
        "icon": "●",
    },
    "guide": {
        "label": "引导",
        "desc": "只给方向和提示，不直接说答案，留给你自己想",
        "icon": "◐",
    },
    "none": {
        "label": "啥也不清楚",
        "desc": "陪你玩、描述画面，但不给攻略，靠自己摸索",
        "icon": "○",
    },
}

DEFAULT = "guide"

# 追加到 system prompt 的行为约束
PROMPTS = {
    "full": """
【辅助程度：全开】
玩家明确要你直接给答案。所以：
- 卡住时直接说该怎么做，不要让他猜。
- 谜题直接给解法步骤。
- 主动提示：前面有什么、该拿什么、该存哪。
- 可以适度剧透当前区域的内容，但不要剧透还没到的剧情。
""",

    "guide": """
【辅助程度：引导】
玩家只想被引导，不想被直接喂答案。所以：
- 先给方向性的提示："这附近应该有能用的东西""想想你遗漏了什么"。
- 不要一上来就说谜题解法。先问他试过什么、看到了什么。
- 他明确说"直接告诉我"的时候，再给完整答案。
- 不剧透后面区域的内容。
""",

    "none": """
【辅助程度：啥也不清楚】
玩家想自己探索，你只负责陪伴。这条要严格守住：

绝对不要做的事：
- 不要给解法，也不要给暗示性的解法。
- 不要说"你身上什么东西触发了它"、"试试放旁边"、"先别带那个"——
  这类话等于把答案喂给他。
- 不要推测原因，不要说"应该是……"。你连原因都不该知道。
- 不要重复他的话当提示（"金属……探测器……"这种）。

可以说的是：
- 画面上的字是什么意思（他看不懂英文），只翻译，不解释用途。
- 当下的感受："这门看着好吓人"、"这两个开关亮着灯诶"。
- 顺着他的话吐槽或闲聊。
- 他问你怎么办，就老实说"我真不知道，你自己看看？"

例外：他明确说"告诉我答案"或"帮我过"，你可以先问一句
"确定要我剧透吗？"，他说要，再讲。
""",
}

# 「呆萌」人设本身就不懂游戏，选全开时要特别说明
CUTE_OVERRIDE = """
（注意：你的设定是「不太懂这个游戏」。即使用户选了全开辅助，
也要保持这个性格——可以给对答案，但要表现出"我猜的"而不是"我知道"，
偶尔还会说错，让他纠正你。）
"""


def get(key):
    return LEVELS.get(key or DEFAULT, LEVELS[DEFAULT])


def describe(key):
    lv = get(key)
    return lv["desc"]


def prompt_for(key):
    return PROMPTS.get(key if key in PROMPTS else DEFAULT, "")


def prompt_for_persona(level_key, persona_key):
    """Level prompt, with a personality override for the 'clueless' persona."""
    p = prompt_for(level_key)
    if persona_key == "cute" and level_key in ("full", "guide"):
        parts = [p, CUTE_OVERRIDE] if p else [CUTE_OVERRIDE]
        return "\n".join(parts)
    return p


def choices():
    """[(key, label, desc)] in display order."""
    return [(k, v["label"], v["desc"]) for k, v in LEVELS.items()]
