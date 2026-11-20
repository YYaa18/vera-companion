"""读取 recvx-enhanced-port 的实时游戏状态（不截图、不花钱）。

原理：Windows 构建固定 ImageBase 0x30000000 且关闭 ASLR，
`CheatState g_cheat` 在 .data 段地址固定为 0x30674840。
结构定义见 pc/src/host/cheat.h，字段布局见下方偏移常量。

只读，不写任何内存。
"""
import ctypes
import ctypes.wintypes as wt
import struct
import subprocess

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

# g_cheat 在 .data 段的虚拟地址（由 PE 文件里初始字节模式定位得出）
G_CHEAT_ADDR = 0x30674840
STRUCT_SIZE = 5572

# CheatState 字段偏移（32 位）
OFF_HP = 48
OFF_STG = 52
OFF_ROM = 56
OFF_POS = 60
OFF_PLAYER = 64
OFF_SLOTS = 68
OFF_INV = 72
OFF_NAMES = 124
OFF_ROOMS = 5116
NAMES_COUNT = 156
NAMES_STRIDE = 32
ROOMS_COUNT = 19
ROOMS_STRIDE = 24

# 房间名表（来自 pc/src/host/teleport.c 的 labels[]），g_cheat.rooms 只覆盖前 18 个
STAGE_NAMES = {
    0: "Prison", 1: "Palace", 2: "Residence", 3: "Military Training Facility",
    4: "Airport", 5: "Transport plane", 6: "Antarctic", 7: "Antarctic (Chris)",
    8: "Antarctic 2", 9: "Battle Game",
}

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.argtypes = [wt.HANDLE, wt.LPCVOID, wt.LPVOID,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]


def find_pid(name="recvx.exe"):
    """Find the process id via the Win32 snapshot API.

    Spawning tasklist on a timer flashes a console window every time; this
    stays in-process and is also much cheaper.
    """
    import ctypes
    import ctypes.wintypes as wt

    TH32CS_SNAPPROCESS = 0x00000002

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wt.DWORD),
            ("cntUsage", wt.DWORD),
            ("th32ProcessID", wt.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wt.DWORD),
            ("cntThreads", wt.DWORD),
            ("th32ParentProcessID", wt.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wt.DWORD),
            ("szExeFile", ctypes.c_char * 260),
        ]

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateToolhelp32Snapshot.restype = wt.HANDLE
    k.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
    k.Process32First.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
    k.Process32Next.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32)]

    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == wt.HANDLE(-1).value:
        return None
    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if not k.Process32First(snap, ctypes.byref(entry)):
            return None
        target = name.lower().encode()
        while True:
            if entry.szExeFile.lower() == target:
                return int(entry.th32ProcessID)
            if not k.Process32Next(snap, ctypes.byref(entry)):
                break
        return None
    finally:
        k.CloseHandle(snap)


def _cstr(b):
    e = b.find(b"\x00")
    return b[:e if e >= 0 else len(b)].decode("utf-8", "replace").strip()


class GameState:
    """Reusable reader; keeps the process handle open between polls."""

    def __init__(self, exe_name="recvx.exe"):
        self.exe = exe_name
        self.pid = None
        self.handle = None
        self._names = {}
        self._rooms = {}

    # ---------------------------------------------------------------- handle
    def connect(self):
        pid = find_pid(self.exe)
        if pid is None:
            self.close()
            return False
        if pid == self.pid and self.handle:
            return True
        self.close()
        self.pid = pid
        self.handle = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not self.handle:
            self.handle = None
            return False
        return True

    def close(self):
        if self.handle:
            try:
                k32.CloseHandle(self.handle)
            except Exception:
                pass
        self.handle = None
        self.pid = None
        self._names.clear()
        self._rooms.clear()

    @property
    def connected(self):
        return self.handle is not None

    # ---------------------------------------------------------------- read
    def _read(self, addr, size):
        if not self.handle:
            return None
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t(0)
        ok = k32.ReadProcessMemory(self.handle, ctypes.c_void_p(addr), buf, size,
                                   ctypes.byref(got))
        if not ok or got.value < size:
            return None
        return buf.raw

    def read(self):
        """Return a snapshot dict, or None if the game is not running."""
        if not self.connect():
            return None
        blob = self._read(G_CHEAT_ADDR, STRUCT_SIZE)
        if blob is None:
            # the game may have restarted; retry once after reconnecting
            self.close()
            if not self.connect():
                return None
            blob = self._read(G_CHEAT_ADDR, STRUCT_SIZE)
            if blob is None:
                return None

        hp, stg, rom, pos, player, slots = struct.unpack_from("<6i", blob, OFF_HP)
        inv = struct.unpack_from("<12I", blob, OFF_INV)
        equipped = inv[0]
        knife = inv[1]
        items = [(r >> 16, r & 0xFFFF) for r in inv[2:] if r]

        # cache the name tables; they load once the game's messages are up
        if not self._names:
            for i in range(NAMES_COUNT):
                s = _cstr(blob[OFF_NAMES + i * NAMES_STRIDE:
                               OFF_NAMES + (i + 1) * NAMES_STRIDE])
                if s:
                    self._names[i] = s
        if not self._rooms:
            for i in range(ROOMS_COUNT):
                s = _cstr(blob[OFF_ROOMS + i * ROOMS_STRIDE:
                               OFF_ROOMS + (i + 1) * ROOMS_STRIDE])
                if s:
                    self._rooms[i] = s

        item_list = []
        for iid, cnt in items:
            item_list.append({
                "id": iid,
                "count": cnt,
                "name": self._names.get(iid, f"item #{iid}"),
                "equipped": iid == (equipped >> 16) if equipped else False,
            })

        return {
            "hp": hp,
            "stage": stg,
            "room": rom,
            "pos": pos,
            "character": "Chris" if player else "Claire",
            "slots": slots,
            "items": item_list,
            "knife": knife >> 16 if knife else 0,
            "room_label": self.room_label(stg, rom),
            "stage_name": STAGE_NAMES.get(stg, f"Stage {stg}"),
            "in_game": hp > 0,
        }

    # ---------------------------------------------------------------- help
    def room_label(self, stg, rom):
        """A readable room name, from the port's own room table."""
        try:
            from room_map import ROOM_LABELS
        except Exception:
            ROOM_LABELS = {}
        name = ROOM_LABELS.get((stg, rom))
        if name:
            return name
        if 0 <= rom < ROOMS_COUNT:
            own = self._rooms.get(rom)
            if own:
                return f"{STAGE_NAMES.get(stg, stg)}: {own}"
        return f"{STAGE_NAMES.get(stg, f'Stage {stg}')} room {rom}"

    def item_name(self, iid):
        return self._names.get(iid, f"item #{iid}")

    # ---------------------------------------------------------------- summary
    def describe(self, state=None):
        """A compact Chinese one-liner for the assistant's prompt."""
        s = state or self.read()
        if not s:
            return None
        if not s["in_game"]:
            return "游戏正在运行，但还没开始（在标题或菜单画面）。"
        parts = [f"当前角色：{s['character']}",
                 f"位置：{s['room_label']}",
                 f"血量：{s['hp']}"]
        if s["items"]:
            inv = "、".join(f"{it['name']}x{it['count']}" for it in s["items"][:10])
            extra = f" 等{len(s['items'])}件" if len(s["items"]) > 10 else ""
            parts.append(f"背包：{inv}{extra}")
        else:
            parts.append("背包：空")
        return "；".join(parts) + "。"


if __name__ == "__main__":
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    gs = GameState()
    s = gs.read()
    if not s:
        print("游戏没在运行")
    else:
        print(f"角色   : {s['character']}")
        print(f"位置   : {s['room_label']}  (stage {s['stage']} / room {s['room']})")
        print(f"血量   : {s['hp']}")
        print(f"槽位   : {s['slots']}")
        print(f"背包   : {[(i['name'], i['count']) for i in s['items']] or '空'}")
        print()
        print(gs.describe(s))
    gs.close()
