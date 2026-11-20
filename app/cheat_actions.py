"""给"邪恶"人设动手的能力：往 g_cheat 写入请求位，让游戏执行作弊动作。

原理：游戏每帧读取 g_cheat.request 的位标志并执行，执行后清零。
我们只需写入正确的字段组合 + 置位 request，游戏自己会处理。

只写 g_cheat 这一个结构体，不碰游戏代码或其它数据。
"""
import ctypes
import ctypes.wintypes as wt
import struct
import time

from game_state import GameState, G_CHEAT_ADDR, find_pid, k32

PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

# CheatState 字段偏移
OFF_GIVE_ID = 16
OFF_GIVE_COUNT = 20
OFF_SPAWN_IDX = 36
OFF_DROP_SLOT = 40
OFF_REQUEST = 44
OFF_HP = 48
OFF_INV = 72
OFF_RESULT = 120

# request 位
CHEAT_GIVE = 1
CHEAT_TELEPORT = 2
CHEAT_HEAL = 4
CHEAT_SPAWN = 8
CHEAT_DROP = 16
CHEAT_BOX = 64

# 物品 id。这些不是猜的 —— 是运行时从游戏的 g_cheat.names[] 表里读出来的，
# 与屏幕上显示的名字一一对应。
WEAPONS = {
    "rocket_launcher": (1, "Rocket Launcher"),
    "assault_rifle": (2, "Assault Rifle"),
    "sniper": (3, "Sniper Rifle"),
    "shotgun": (4, "Shotgun"),
    "handgun": (5, "Handgun"),
    "grenade_launcher": (6, "Grenade Launcher"),
    "crossbow": (7, "Bow Gun"),
    "knife": (8, "Combat Knife"),
    "custom_handgun": (10, "Custom Handgun"),
    "linear_launcher": (11, "Linear Launcher"),
    "magnum": (32, "Magnum"),
    "gold_lugers": (33, "Gold Lugers"),
    "submachine_gun": (34, "Sub Machine Gun"),
}

SUPPLIES = {
    "handgun_ammo": (12, "Handgun Bullets"),
    "magnum_ammo": (13, "Magnum Bullets"),
    "shotgun_ammo": (14, "Shotgun Shells"),
    "grenade_rounds": (15, "Grenade Rounds"),
    "acid_rounds": (16, "Acid Rounds"),
    "flame_rounds": (17, "Flame Rounds"),
    "bow_arrows": (18, "Bow Gun Arrows"),
    "rifle_ammo": (40, "Rifle Bullets"),
    "assault_ammo": (42, "A.Rifle Bullets"),
    "first_aid": (20, "F. Aid Spray"),
    "green_herb": (21, "Green Herb"),
    "red_herb": (22, "Red Herb"),
    "blue_herb": (23, "Blue Herb"),
    "mixed_herb": (24, "Mixed Herb"),
    "ink_ribbon": (31, "Ink Ribbon"),
}

# 敌人（spawn 列表里的序号，取自 spawn_glue.c 的 extra[] 与常见敌人）
ENEMIES = {
    "zombie": (0, "Zombie"),
    "zombie_dog": (4, "Zombie Dog"),
    "bandersnatch": (14, "Bandersnatch"),
    "hunter": (18, "Hunter"),
    "ant_small": (21, "Ant (Small)"),
    "alexia_baby": (30, "Alexia's Baby"),
    "tentacle": (29, "Tentacle"),
    "armored_knight": (54, "Armored Knight (Sword)"),
}


class CheatWriter:
    """Writes to g_cheat. Only active when the 'evil' persona is chosen."""

    def __init__(self):
        self.pid = None
        self.handle = None

    def connect(self):
        pid = find_pid("recvx.exe")
        if pid is None:
            self.close()
            return False
        if pid == self.pid and self.handle:
            return True
        self.close()
        self.pid = pid
        h = k32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ |
            PROCESS_VM_WRITE | PROCESS_VM_OPERATION,
            False, pid)
        if not h:
            return False
        self.handle = h
        return True

    def close(self):
        if self.handle:
            try:
                k32.CloseHandle(self.handle)
            except Exception:
                pass
        self.handle = None
        self.pid = None

    def _read(self, addr, size):
        if not self.handle:
            return None
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t(0)
        ok = k32.ReadProcessMemory(self.handle, ctypes.c_void_p(addr), buf, size,
                                   ctypes.byref(got))
        return buf.raw if ok else None

    def _write(self, addr, data):
        if not self.handle:
            return False
        buf = ctypes.create_string_buffer(data, len(data))
        done = ctypes.c_size_t(0)
        return bool(k32.WriteProcessMemory(self.handle, ctypes.c_void_p(addr),
                                           buf, len(data), ctypes.byref(done)))

    def _set_int(self, offset, value):
        return self._write(G_CHEAT_ADDR + offset, struct.pack("<i", int(value)))

    def _request(self, bit):
        return self._set_int(OFF_REQUEST, bit)

    # ------------------------------------------------------------ actions
    def give_item(self, item_id, count=1):
        """Put an item in the inventory."""
        if not self.connect():
            return False, "游戏没运行"
        self._set_int(OFF_GIVE_ID, item_id)
        self._set_int(OFF_GIVE_COUNT, count)
        if not self._request(CHEAT_GIVE):
            return False, "写入失败"
        time.sleep(0.25)
        res = self._read(G_CHEAT_ADDR + OFF_RESULT, 8)
        return True, "已放入背包"

    def spawn_enemy(self, spawn_index):
        """Drop an enemy in front of the player.

        The game refuses while a menu, the inventory, a cutscene or a raised
        weapon is active, so report that clearly instead of a silent failure.
        """
        if not self.connect():
            return False, "游戏没运行"
        self._set_int(OFF_SPAWN_IDX, spawn_index)
        if not self._request(CHEAT_SPAWN):
            return False, "写入失败"
        time.sleep(0.3)
        result = self.full_status() or ""
        if "Finish the current action" in result:
            return False, "现在不能刷怪：请关掉菜单/物品栏，放下武器，回到能自由走动再试"
        if "unavailable" in result.lower():
            return False, f"这个敌人不可用（{result}）"
        if result:
            return True, result
        return True, "已召唤"

    def heal(self):
        if not self.connect():
            return False, "游戏没运行"
        self._request(CHEAT_HEAL)
        return True, "已治疗"

    # ------------------------------------------------------------ 删除
    def inventory_slots(self):
        """Read the inventory: list of (slot_index, item_id, count).

        Slot 0 holds the equipped slot number, slot 1 the knife; real items
        start at index 2. The game's own drop check accepts 1..1+slots.
        """
        if not self.connect():
            return []
        raw = self._read(G_CHEAT_ADDR + OFF_INV, 12 * 4)
        if not raw:
            return []
        inv = struct.unpack("<12I", raw)
        out = []
        for i, v in enumerate(inv):
            if i < 2:
                continue
            iid = v >> 16
            if iid:
                out.append((i, iid, v & 0xFFFF))
        return out

    def drop_slot(self, slot):
        """Empty one inventory slot by index."""
        if not self.connect():
            return False, "游戏没运行"
        if not self._set_int(OFF_DROP_SLOT, slot):
            return False, "写入失败"
        if not self._request(CHEAT_DROP):
            return False, "写入失败"
        time.sleep(0.35)
        result = self.full_status() or ""
        if "Cannot remove the weapon" in result:
            return False, "手上正拿着这把武器，先放下（收枪）再删"
        if "Item removed" in result:
            return True, "已删除"
        return False, result or "没删掉"

    def drop_item(self, name):
        """Remove an item by its in-game name. Returns (ok, message)."""
        if not self.connect():
            return False, "游戏没运行"
        target = (name or "").strip().lower()
        if not target:
            return False, "没说删什么"
        hits = [s for s, iid, cnt in self.inventory_slots()
                if self.item_name(iid).lower() == target]
        if not hits:
            # 允许模糊匹配，比如 "shotgun" 命中 "Shotgun"
            hits = [s for s, iid, cnt in self.inventory_slots()
                    if target in self.item_name(iid).lower()]
        if not hits:
            return False, f"背包里没有「{name}」"
        ok, msg = self.drop_slot(hits[0])
        return ok, msg

    def drop_all_named(self, name):
        """Remove every stack of that item (ammo often sits in one stack)."""
        removed = 0
        for _ in range(12):
            ok, _msg = self.drop_item(name)
            if not ok:
                # 可能是手上拿着，试下一格
                break
            removed += 1
        return removed > 0, f"删了 {removed} 组" if removed else "没删掉"

    def item_name(self, iid):
        """Look up an item id in the game's own name table."""
        try:
            from game_state import GameState
            if not hasattr(self, "_names_cache"):
                gs = GameState()
                gs.read()
                self._names_cache = dict(gs._names)
                gs.close()
            return self._names_cache.get(iid, f"item #{iid}")
        except Exception:
            return f"item #{iid}"

    def list_inventory(self):
        """[(name, count), ...] using the game's names."""
        return [(self.item_name(iid), cnt) for _s, iid, cnt in self.inventory_slots()]

    def full_status(self):
        """Read the last action's result text the game wrote back."""
        if not self.connect():
            return None
        raw = self._read(G_CHEAT_ADDR + OFF_RESULT, 4)
        if not raw:
            return None
        ptr = struct.unpack("<I", raw)[0]
        if not ptr:
            return None
        s = self._read(ptr, 96)
        if not s:
            return None
        end = s.find(b"\x00")
        return s[:end if end >= 0 else len(s)].decode("cp1252", "replace")


if __name__ == "__main__":
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    w = CheatWriter()
    print("连接:", w.connect())
    if w.connect():
        gs = GameState()
        s = gs.read()
        print("当前状态:", gs.describe(s) if s else "读不到")
        print("上次操作结果:", w.full_status())
        gs.close()
    w.close()
