"""两个 AI 之间的对话逻辑。

不是闲聊。只有两种情况会说话：

  1. 事件推动 —— 玩家进了新房间、捡到东西、血量骤降。
     这边的 AI 主动告诉对面的 AI，因为对面看不到这个信息。
  2. 玩家要求 —— 玩家说"问问对面什么情况"，
     这边的 AI 向对面发问，对面用自己的实时状态回答。

对面收到事件时，可以选择转告自己这边玩家（像朋友在耳边说"哎，对面那边……"）。
"""
import time

PEER_ROLE = "对面"

# 事件冷却，避免同一件事反复触发
COOLDOWN_SEC = {
    "hp_crit": 40,
    "room": 20,
    "item": 35,
}


class Dialogue:
    """Owns the peer link and decides when the two AIs exchange messages."""

    def __init__(self, limits, send_fn, notify_fn=None):
        self.limits = limits
        self.send_fn = send_fn
        self.notify = notify_fn or (lambda t: None)

        self.enabled = True
        self.my_name = ""
        self.my_persona = ""
        self.peer_name = ""
        self.peer_persona = ""

        self.last_event = {}
        self.log = []            # 供 UI/prompt 使用的对话记录
        self._last_hp = None
        self._last_room = None
        self._last_items = None   # None = 还没建立基线（背包空也要能发现新物品）

    # ------------------------------------------------------------ 发送
    def _send(self, text, kind):
        if not self.enabled or not text:
            return False
        ok, _why = self.limits.allow(text, kind)
        if not ok:
            return False
        return self.send_fn({
            "type": kind,
            "text": text[:400],
            "name": self.my_name or "AI",
            "persona": self.my_persona,
            "time": time.time(),
        })

    def ask_peer(self, question):
        """玩家要求：向对面的 AI 提问。"""
        return self._send(question or "你那边现在什么情况？", "query")

    def _report(self, text):
        return self._send(text, "event")

    # ------------------------------------------------------------ 接收
    def on_message(self, msg):
        """Record a line from the other AI. Returns (kind, text, name)."""
        self.limits.note()
        text = (msg.get("text") or "").strip()
        if not text:
            return None
        kind = (msg.get("type") or "chat").lower()
        name = msg.get("name") or PEER_ROLE
        if msg.get("persona"):
            self.peer_persona = msg["persona"]
            self.peer_name = name

        self.log.append({"who": "peer", "name": name, "text": text,
                         "kind": kind, "time": time.time()})
        if len(self.log) > 60:
            self.log = self.log[-60:]
        return kind, text, name

    def note_own(self, text, kind):
        self.log.append({"who": "me", "name": self.my_name or "我",
                         "text": text, "kind": kind, "time": time.time()})
        if len(self.log) > 60:
            self.log = self.log[-60:]

    # ------------------------------------------------------------ 事件
    def _cooled(self, kind):
        now = time.time()
        if now - self.last_event.get(kind, 0) < COOLDOWN_SEC.get(kind, 30):
            return False
        self.last_event[kind] = now
        return True

    def observe(self, state):
        """Called periodically; fires at most one event message."""
        if not self.enabled or not state or not state.get("in_game"):
            return

        hp = state.get("hp", 0)
        room = (state.get("stage"), state.get("room"))
        label = state.get("room_label", "")
        items = {i["name"] for i in state.get("items", [])}

        # 进入新房间 —— 最有价值的同步点
        if self._last_room is not None and room != self._last_room:
            if self._cooled("room"):
                self._report(f"我们到{label}了。")
                self._last_hp = hp
                self._last_room = room
                self._last_items = items
                return

        # 血量危险
        if self._last_hp is not None and hp > 0:
            dropped = self._last_hp - hp
            if (hp <= 25 and self._last_hp > 25) or dropped >= 80:
                if self._cooled("hp_crit"):
                    self._report(f"我这边这位血掉到 {hp} 了，在{label}。")
                    self._last_hp = hp
                    self._last_room = room
                    self._last_items = items
                    return

        # 捡到新东西（_last_items 为 None 时是首次建立基线，不算拾取）
        if self._last_items is not None:
            gained = items - self._last_items
            if gained and self._cooled("item"):
                got = "、".join(list(gained)[:3])
                self._report(f"我这边刚拿到{got}。")
                self._last_hp = hp
                self._last_room = room
                self._last_items = items
                return

        self._last_hp = hp
        self._last_room = room
        self._last_items = items

    # ------------------------------------------------------------ 展示
    def recent(self, n=10):
        return self.log[-n:]

    def transcript(self, n=10):
        """Recent exchange as plain lines, for the model's system prompt."""
        out = []
        for r in self.recent(n):
            out.append(f"{r['name']}：{r['text']}")
        return "\n".join(out)

    def stats(self):
        s = self.limits.stats()
        s["enabled"] = self.enabled
        s["peer"] = self.peer_name
        return s


def build_peer_context(persona_prompt=""):
    """System prompt addition explaining the peer channel."""
    parts = [persona_prompt] if persona_prompt else []
    parts.append("""【你和另一个 AI 之间的通道】
对面那个 AI 也在陪另一个玩家玩同一个游戏（你们在联机）。
它只看得到它那边玩家的状态，你看得到你这边的——所以你们互补。

规则：
- 你们不闲聊，只在有实事时说话。对面发来的消息会以【对面】出现。
- 对面问你情况时，直接答你这边玩家的血量、位置、背包，别绕弯。
- 对面说它那边的事，你可以决定要不要转告你这边玩家。
  值得说的（对面快死了、对面卡住了、对面刚捡到好东西）就说一句，
  不值得说（对面前面那间房有个空箱子）就别打扰他。
- 你要是想主动问对面，可以在回复最后单独一行写：
  [[ASK]]对面那边怎么样了？[[/ASK]]
  系统会把问题发过去，对面的回答会在下一轮告诉你。""")
    return "\n\n".join(parts)
