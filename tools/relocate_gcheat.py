"""上游更新后，重新定位 g_cheat 结构体地址。

原理：游戏启动时 g_cheat 的原始值就是「除了 offset 20 的 give_count=1，
其余全零」。这个 5572 字节的模式在 exe 文件的 .data 段里是唯一的，
在文件里找到它就能算出运行时地址：

    VA = ImageBase + (文件偏移 - 该段文件偏移) + 该段 RVA

用法（游戏没开也能跑）：
    python tools/relocate_gcheat.py --exe "E:\\RE-CodeVeronica-PC\\recvx.exe"

输出新的地址后，改 app/game_state.py 顶部的 G_CHEAT_ADDR。
"""
import argparse
import struct
import sys

STRUCT_SIZE = 5572          # CheatState 总字节数
GIVE_COUNT_OFF = 20         # give_count 字段偏移


def parse_sections(data):
    if data[:2] != b"MZ":
        raise SystemExit("不是 PE 文件")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise SystemExit("PE 签名不对")

    machine = struct.unpack_from("<H", data, pe + 4)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    opt = pe + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    pe32plus = magic == 0x20B

    image_base = struct.unpack_from("<Q" if pe32plus else "<I", data,
                                    opt + (24 if pe32plus else 28))[0]

    sec = opt + opt_size
    sections = []
    for i in range(nsec):
        o = sec + i * 40
        name = data[o:o + 8].rstrip(b"\0").decode("ascii", "replace")
        vsize, va, rsize, roff = struct.unpack_from("<IIII", data, o + 8)
        sections.append({
            "name": name, "va": va, "vsize": vsize,
            "roff": roff, "rsize": rsize,
        })
    return {
        "machine": machine, "image_base": image_base,
        "pe32plus": pe32plus, "sections": sections,
    }


def find_gcheat(data, info):
    # 初始值：offset 20 是 1，其余到 STRUCT_SIZE 全零
    pattern = b"\x00" * GIVE_COUNT_OFF + b"\x01\x00\x00\x00"
    # 全局变量只会落在可写数据段；资源段里出现同样的字节是巧合。
    SKIP = {".rsrc", ".reloc", ".text", ".rdata", ".idata", ".CRT", ".tls"}
    hits = []
    for s in info["sections"]:
        if s["rsize"] == 0 or s["name"] in SKIP:
            continue
        blob = data[s["roff"]:s["roff"] + s["rsize"]]
        start = 0
        while True:
            i = blob.find(pattern, start)
            if i < 0:
                break
            start = i + 1
            if i + STRUCT_SIZE > len(blob):
                continue
            body = blob[i:i + STRUCT_SIZE]
            if any(body[GIVE_COUNT_OFF + 4:]):
                continue
            if any(body[:GIVE_COUNT_OFF]):
                continue
            va = info["image_base"] + s["va"] + i
            hits.append((s["name"], va, s["roff"] + i))
    return hits


def main():
    ap = argparse.ArgumentParser(description="重新定位 g_cheat 地址")
    ap.add_argument("--exe", required=True, help="recvx.exe 路径")
    args = ap.parse_args()

    with open(args.exe, "rb") as f:
        data = f.read()

    info = parse_sections(data)
    print(f"PE: {'PE32+' if info['pe32plus'] else 'PE32'}  "
          f"ImageBase 0x{info['image_base']:X}")
    print(f"段: {', '.join(s['name'] for s in info['sections'])}\n")

    hits = find_gcheat(data, info)
    if not hits:
        print("没找到。可能上游改了 CheatState 的结构或初始值。")
        print("去看上游的 pc/src/host/cheat.h 里的 CheatState 定义，")
        print("更新本脚本的 STRUCT_SIZE / GIVE_COUNT_OFF 再试。")
        return 1

    if len(hits) > 1:
        print(f"找到 {len(hits)} 个候选（理论上应该只有 1 个）：")
    for name, va, roff in hits:
        print(f"  段 {name:<8} 文件偏移 0x{roff:X}  →  运行时地址 0x{va:08X}")

    best = hits[0]
    addr = best[1]
    print(f"\n改 app/game_state.py 第 20 行左右：")
    print(f"    G_CHEAT_ADDR = 0x{addr:08X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
