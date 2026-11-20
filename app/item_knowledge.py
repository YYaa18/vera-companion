"""物品用途速查表 —— 我们自己的攻略笔记。

这里只写「这个东西是干什么用的」，不复制游戏内的任何描述文本。
这些是事实性信息（谁都能从游戏中观察到），不是 Capcom 的原创表达。

用途：
  · 注入给 AI，避免它瞎编物品作用
  · 玩家问"这个能干什么"时，AI 有据可依

id 与游戏内存物品表一致（0..155）。名字用英文，和游戏内显示一致。
"""

# id -> (显示名, 一句话用途, 类别)
# 类别: weapon / ammo / heal / key / tool / file / other
ITEMS = {
    # ---- 武器 ----
    1:  ("Rocket Launcher", "一发必杀的重武器，弹药极少，留着打 Boss", "weapon"),
    2:  ("Assault Rifle", "连发步枪，弹匣大，适合对付成群敌人", "weapon"),
    3:  ("Sniper Rifle", "远距离狙杀，可以穿透多个敌人", "weapon"),
    4:  ("Shotgun", "近距离威力大，一枪能放倒多个", "weapon"),
    5:  ("Handgun", "初始手枪，弹药多但威力低", "weapon"),
    6:  ("Grenade Launcher", "可换多种弹头的榴弹枪，对付特定敌人很有效", "weapon"),
    7:  ("Bow Gun", "弩，箭可以回收，安静", "weapon"),
    8:  ("Combat Knife", "近战武器，不耗弹药，但伤害低", "weapon"),
    9:  ("Handgun", "另一把小手枪", "weapon"),
    10: ("Custom Handgun", "强化版手枪，有连射能力", "weapon"),
    11: ("Linear Launcher", "线性发射器，后期强力武器", "weapon"),
    32: ("Magnum", "大口径左轮，威力极高，弹药稀少", "weapon"),
    33: ("Gold Lugers", "金色鲁格手枪，成对使用", "weapon"),
    34: ("Sub Machine Gun", "冲锋枪，射速快", "weapon"),

    # ---- 弹药 ----
    12: ("Handgun Bullets", "手枪弹药，最常见，可以捡很多", "ammo"),
    13: ("Magnum Bullets", "马格南弹药，很稀有，留给强敌", "ammo"),
    14: ("Shotgun Shells", "霰弹，散布伤害", "ammo"),
    15: ("Grenade Rounds", "榴弹，爆炸范围伤害", "ammo"),
    16: ("Acid Rounds", "酸液弹，对某些敌人有特效", "ammo"),
    17: ("Flame Rounds", "燃烧弹，持续伤害", "ammo"),
    18: ("Bow Gun Arrows", "弩箭，射出后可以回收", "ammo"),
    30: ("Magnum Bullets", "马格南弹药（另一种）", "ammo"),
    39: ("Rifle Bullets", "步枪弹药", "ammo"),
    42: ("A.Rifle Bullets", "突击步枪弹药", "ammo"),

    # ---- 回复 ----
    20: ("F. Aid Spray", "急救喷雾，立刻回满血，比草药方便", "heal"),
    21: ("Green Herb", "绿草药，回复少量血，可以和别的草药混合", "heal"),
    22: ("Red Herb", "红草药，单独用无效，和绿草药混合能放大回复量", "heal"),
    23: ("Blue Herb", "蓝草药，解毒用，单独不回复血量", "heal"),
    24: ("Mixed Herb", "混合草药（绿+绿），回复量比单个高", "heal"),
    25: ("Mixed Herb", "混合草药（绿+红），回复量更高", "heal"),
    26: ("Mixed Herb", "混合草药（绿+蓝），回复兼解毒", "heal"),
    27: ("Mixed Herb", "混合草药（绿+绿+绿），大量回复", "heal"),
    28: ("Mixed Herb", "混合草药（绿+绿+蓝），回复兼解毒", "heal"),
    29: ("Mixed Herb", "混合草药（绿+红+蓝），高回复兼解毒", "heal"),

    # ---- 存档 ----
    31: ("Ink Ribbon", "色带，打字机存档时消耗，用完就存不了档", "tool"),

    # ---- 关键道具（按游戏内顺序，用途照实描述）----
    43: ("Alexander's Pierce", "关键道具，和宫殿的机关有关", "key"),
    44: ("Alexander's Jewel", "关键道具", "key"),
    45: ("Alfred's Ring", "关键道具", "key"),
    46: ("Alfred's Jewel", "关键道具", "key"),
    47: ("Prisoner's Diary", "文件，读它了解背景故事和线索", "file"),
    48: ("Director's Memo", "文件，可能含密码或机关提示", "file"),
    49: ("Instructions", "说明书类文件", "file"),
    50: ("Lockpick", "开锁工具，能打开某些锁住的门或柜子", "tool"),
    51: ("Glass Eye", "关键道具，用于特定机关", "key"),
    52: ("Piano Roll", "钢琴谱，用在钢琴上触发机关", "key"),
    53: ("Steering Wheel", "方向盘，装在交通工具上", "key"),
    54: ("Crane Key", "吊车钥匙", "key"),
    55: ("Lighter", "打火机，点燃东西用，也是早期就能拿到的道具", "tool"),
    56: ("Eagle Plate", "鹰形饰板，装在特定位置", "key"),
    57: ("Side Pack", "扩容背包，增加携带格数", "tool"),
    58: ("Map", "地图，显示区域布局", "tool"),
    59: ("Hawk Emblem", "鹰徽章，开门用", "key"),
    60: ("Queen Ant Object", "蚁后物件，成对使用的机关道具", "key"),
    61: ("King Ant Object", "蚁王物件，和蚁后物件配套", "key"),
    62: ("Biohazard Card", "生物危害卡，权限门卡", "key"),
    63: ("Duralumin Case", "硬铝箱，装特殊物品", "key"),
    64: ("Detonator", "引爆器，炸开障碍", "key"),
    65: ("Control Lever", "操纵杆部件", "key"),
    66: ("Gold Dragonfly", "金蜻蜓，机关道具", "key"),
    67: ("Silver Key", "银钥匙", "key"),
    68: ("Gold Key", "金钥匙", "key"),
    69: ("Army Proof", "军籍证明，剧情道具", "key"),
    145: ("Playing Manual", "游戏说明书，开局自带，读它了解基本操作", "file"),
}

# 类别 -> 给 AI 的提示
CATEGORY_HINT = {
    "weapon": "武器",
    "ammo": "弹药",
    "heal": "回复道具",
    "key": "关键道具（解谜或开门用，通常不能丢）",
    "tool": "工具",
    "file": "文件（读它可能有线索）",
    "other": "其它",
}


def lookup(item_id):
    """Return (name, purpose, category) or None."""
    return ITEMS.get(item_id)


def describe_item(item_id):
    """One line like 'Green Herb（回复道具）：绿草药，回复少量血…'"""
    hit = ITEMS.get(item_id)
    if not hit:
        return None
    name, purpose, cat = hit
    return f"{name}（{CATEGORY_HINT.get(cat, cat)}）：{purpose}"


def knowledge_block(item_ids):
    """Build a prompt block describing the items the player currently carries."""
    lines = []
    seen = set()
    for iid in item_ids:
        if iid in seen:
            continue
        seen.add(iid)
        d = describe_item(iid)
        if d:
            lines.append("· " + d)
    if not lines:
        return ""
    return "【你背包里这些东西的用途（供参考）】\n" + "\n".join(lines)


def count_known():
    return len(ITEMS)


if __name__ == "__main__":
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print(f"已整理 {count_known()} 件物品的用途")
    for iid in (21, 31, 4, 57):
        print(" ", describe_item(iid))
