"""原创攻略笔记 —— 我们自己打的流程整理，不是游戏原文。

================== 重要 ==================
这里所有文字都是我们自己写的。不包含：
  · 游戏内的对话、文件、物品描述原文
  · 任何 Capcom 的剧本或文案
只记录事实：哪个区域有什么、谜题怎么解、Boss 用什么打。
这类事实性信息可以自由共享。
=========================================

数据按游戏进度组织，每段包含：
  area     区域名（英文，与游戏内一致）
  goal     这个区域的主要目标
  find     关键物品和位置
  puzzle   谜题解法（步骤）
  boss     Boss 打法
  tip      实用提示

用法：
  · 辅助程度「全开」时注入当前区域的完整内容
  · 「引导」时只注入 goal 和 tip，不给 puzzle 答案
  · 「啥也不清楚」时不注入
"""

STAGES = {
    "prison": {
        "area": "Prison",
        "range": (0, 0, 0, 16),          # stage, room 范围
        "goal": "从牢房出去，穿过监狱区，找到通往宫殿的路",
        "find": [
            "牢房里先拿 Playing Manual（游戏手册）",
            "淋浴间、医务室一带通常有绿草药和手枪子弹",
            "墓园方向有石阶，通往主门",
            "刑具房附近能拿到开锁工具",
        ],
        "puzzle": [
            "监狱大门的金钥匙在刑具房，要先处理掉那里的机关",
            "金属探测器房间需要把武器放进储物柜再通过，"
            "或者提前用别的方式绕开",
            "墓园的墓碑上有数字，对应后面某个密码",
        ],
        "boss": [],
        "tip": [
            "这段敌人以丧尸为主，用手枪点射腿部能放倒再补刀，省子弹",
            "别在安全屋外面磨蹭，丧尸会一直刷",
            "打字机存档要消耗色带，前期色带不多，省着用",
        ],
    },

    "palace": {
        "area": "Palace",
        "range": (1, 1, 0, 14),
        "goal": "探索宫殿，拿到通往下一区域的凭证",
        "find": [
            "主厅有钢琴，需要钢琴谱才能用",
            "肖像间、金色鲁格房间有武器或关键道具",
            "办公室的电脑可能需要密码",
        ],
        "puzzle": [
            "钢琴谜题：拿到 Piano Roll 后在钢琴上使用，"
            "会触发暗门或给出线索",
            "金蜻蜓、鹰形饰板这类东西要装到对应的凹槽上",
            "投影室需要按顺序操作才能看到影像线索",
        ],
        "boss": [
            "第一次遇到 Alfred 是剧情战，打不死，撑到他跑掉就行",
        ],
        "tip": [
            "宫殿的走廊有好几条分支，先都走一遍再决定往哪深入",
            "这里开始出现猎杀者一类的快速敌人，霰弹枪比手枪好用",
        ],
    },

    "residence": {
        "area": "Residence",
        "range": (2, 2, 0, 7),
        "goal": "穿过官邸，找到通往训练设施的路",
        "find": [
            "前花园、玄关大厅是主要通路",
            "Alfred 和 Alexia 的房间各有线索",
            "阁楼游戏室有重要道具",
        ],
        "puzzle": [
            "大玩偶走廊要注意，某些门会随剧情变化",
            "蚁王/蚁后两个物件要成对使用",
        ],
        "boss": [],
        "tip": [
            "官邸里敌人不多，适合整理背包、合并草药",
            "红草药单独无效，一定要和绿草药混着用",
        ],
    },

    "training": {
        "area": "Military Training Facility",
        "range": (3, 3, 0, 24),
        "goal": "穿过训练设施，拿到生物危害卡，前往机场",
        "find": [
            "升降梯大厅是入口",
            "更衣室有储物柜，能拿到装备",
            "游泳池、安检办公室一带有关键物品",
            "储藏室有榴弹发射器",
        ],
        "puzzle": [
            "靛蓝卡和银卡要按顺序拿，卡的颜色决定能开哪些门",
            "转盘控制室需要调整到正确角度",
            "人脸浮雕房要按提示顺序按下",
            "电脑终端有多种功能，密码在不同房间的文件里",
        ],
        "boss": [
            "这段会遇到带触手的敌人，榴弹发射器的燃烧弹效果好",
        ],
        "tip": [
            "训练设施很大，容易迷路，建议先把地图走全",
            "这里敌人密度最高，多备弹药和回复",
            "通风管道里能爬到平时去不了的地方",
        ],
    },

    "airport": {
        "area": "Airport",
        "range": (4, 4, 0, 6),
        "goal": "找到飞机，离开这座岛",
        "find": [
            "办公室、机库是关键房间",
            "潜艇码头有剧情",
        ],
        "puzzle": [
            "需要方向盘（Steering Wheel）装到相应位置",
            "吊车钥匙能操作吊车",
        ],
        "boss": [],
        "tip": [
            "机场这段比较短，主要是剧情推进",
            "上飞机前确认背包里有足够回复道具，后面有一段没有补给",
        ],
    },

    "plane": {
        "area": "Transport plane",
        "range": (5, 5, 0, 1),
        "goal": "在飞机上活下来",
        "find": [],
        "puzzle": [],
        "boss": [
            "飞机上的战斗是限时性质，用强力武器尽快解决",
            "推荐用榴弹发射器或马格南",
        ],
        "tip": [
            "飞机战之前一定要存好档",
            "这段没有回复机会，血量低的话先治",
        ],
    },

    "antarctic": {
        "area": "Antarctic Base",
        "range": (6, 9, 0, 38),
        "goal": "在南极基地探索，最终面对 Alexia",
        "find": [
            "停机库、工人宿舍是入口区",
            "武器库有强力装备",
            "电脑房、实验室是关键房间",
            "洋馆部分有大量关键道具",
        ],
        "puzzle": [
            "虎像房间的机关要按特定顺序",
            "电脑房的密码通常在前面的文件里",
            "冷冻走廊、水池房要处理环境机关",
            "运输电梯可以往返不同层",
        ],
        "boss": [
            "Alexia 第一形态：用重武器，注意躲她的火",
            "Alexia 第二形态：会飞，需要打弱点",
            "最终形态：火箭筒或线性发射器是最优解",
        ],
        "tip": [
            "南极基地是最后一章，物资相对充足",
            "最终 Boss 战前会有一段无法返回的流程，提前备好",
            "这里能拿到线性发射器，别漏了",
        ],
    },
}

# 通用技巧，任何阶段都适用
GENERAL_TIPS = [
    "绿+红草药混合后回复量最大，值得攒着混",
    "手枪打腿让丧尸倒地再补刀，比直接打头省子弹",
    "遇到打不过的敌人，跑比打划算",
    "背包满了就把暂时不用的东西放物品箱，物品箱是全局共享的",
    "打字机存档消耗色带，色带不够时优先在 Boss 战前存",
]


def stage_for(stage_id):
    """Find the guide entry covering a stage number."""
    for key, s in STAGES.items():
        lo, hi = s["range"][0], s["range"][1]
        if lo <= stage_id <= hi:
            return key, s
    return None, None


def block_for(stage_id, level="guide", persona_key=""):
    """Prompt text for the current area, scaled by help level.

    full  -> goal + find + puzzle + boss + tip
    guide -> goal + tip only (no puzzle answers)
    none  -> nothing
    """
    if level == "none":
        return ""
    key, s = stage_for(stage_id)
    if not s:
        return ""

    lines = [f"【{s['area']} 区攻略笔记（我们自己整理的，不是游戏原文）】"]
    lines.append(f"目标：{s['goal']}")

    if level == "full":
        if s["find"]:
            lines.append("关键物品位置：")
            lines.extend("  · " + x for x in s["find"])
        if s["puzzle"]:
            lines.append("谜题解法：")
            lines.extend("  · " + x for x in s["puzzle"])
        if s["boss"]:
            lines.append("Boss 提示：")
            lines.extend("  · " + x for x in s["boss"])

    if s["tip"]:
        lines.append("实用提示：")
        lines.extend("  · " + x for x in s["tip"])

    if level == "full":
        lines.append("通用技巧：")
        lines.extend("  · " + x for x in GENERAL_TIPS[:3])

    lines.append("（这些是参考，不必逐条念给玩家，按他的问题取用。）")
    return "\n".join(lines)


def area_names():
    return [(k, v["area"]) for k, v in STAGES.items()]


if __name__ == "__main__":
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print(f"共 {len(STAGES)} 个区域\n")
    for key, area in area_names():
        print(f"  {key:<12} {area}")
    print()
    print("=== stage 0（监狱）全开 ===")
    print(block_for(0, "full")[:600])
    print()
    print("=== stage 0 引导（应该没有谜题解法）===")
    b = block_for(0, "guide")
    print(b[:400])
    print("含'谜题解法':", "谜题解法" in b)
