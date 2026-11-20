"""本机网卡枚举 —— 给虚拟局域网（UU / Tailscale / ZeroTier）用。

一台机器常有好几块网卡（物理网卡 + VMware + 蓝牙 + 各种虚拟网卡）。
广播式自动发现会发错网卡，所以这里列出全部，让用户明确选一块。

只枚举，不修改任何网络设置。
"""
import socket
import struct


def _is_private(ip):
    """RFC1918 + CGNAT，虚拟局域网分配的地址都落在这里面。"""
    try:
        octets = [int(x) for x in ip.split(".")]
    except Exception:
        return False
    if len(octets) != 4:
        return False
    a, b = octets[0], octets[1]
    if a == 10:
        return True
    if a == 172 and 16 <= b <= 31:
        return True
    if a == 192 and b == 168:
        return True
    if a == 100 and 64 <= b <= 127:      # CGNAT，Tailscale 也用这个段
        return True
    return False


def _is_link_local(ip):
    return ip.startswith("169.254.")


def _adapter_names():
    """Map ip -> adapter alias via PowerShell (no extra deps). Windows only."""
    out = {}
    try:
        import subprocess
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetIPAddress -AddressFamily IPv4 | "
             "Select-Object IPAddress,InterfaceAlias | "
             "ForEach-Object { $_.IPAddress + '|' + $_.InterfaceAlias }"],
            capture_output=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        text = r.stdout.decode("mbcs", "replace")
        for line in text.splitlines():
            if "|" in line:
                ip, alias = line.split("|", 1)
                out[ip.strip()] = alias.strip()
    except Exception:
        pass
    return out


def list_adapters():
    """[(ip, alias, kind)] — every usable IPv4 on this machine.

    kind: "lan" (私有地址，虚拟局域网也是这个) / "public" / "link-local"
    """
    hosts = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            hosts.add(info[4][0])
    except Exception:
        pass

    # getaddrinfo 有时漏掉虚拟网卡，用 UDP 连外部地址问出默认出口
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        hosts.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass

    aliases = _adapter_names()
    rows = []
    for ip in hosts:
        if ip.startswith("127."):
            continue
        if _is_link_local(ip):
            kind = "link-local"
        elif _is_private(ip):
            kind = "lan"
        else:
            kind = "public"
        rows.append((ip, aliases.get(ip, "未知网卡"), kind))

    # 私有地址排前面，其余按 IP 排
    order = {"lan": 0, "public": 1, "link-local": 2}
    rows.sort(key=lambda r: (order.get(r[2], 3), r[0]))
    return rows


def best_local_ip():
    """A sensible default: the first private address, else the default route one."""
    rows = [r for r in list_adapters() if r[2] == "lan"]
    return rows[0][0] if rows else ""


def guess_virtual_lan():
    """Heuristically pick the adapter a virtual LAN tool most likely created.

    UU / Tailscale / ZeroTier adapters usually carry a name hint, and their
    addresses are private. Returns (ip, alias) or (None, None).
    """
    HINTS = ("uu", "tailscale", "zerotier", "虚拟", "virtual", "tap", "tun", "radmin", "hamachi")
    rows = list_adapters()
    for ip, alias, kind in rows:
        if kind != "lan":
            continue
        low = alias.lower()
        if any(h in low for h in HINTS):
            return ip, alias
    return None, None


def describe_all():
    """Human-readable summary for the launcher."""
    rows = list_adapters()
    if not rows:
        return "没找到可用网卡"
    lines = []
    for ip, alias, kind in rows:
        tag = {"lan": "局域网", "public": "公网", "link-local": "未配置"}[kind]
        lines.append(f"{ip}  ({alias}, {tag})")
    return "\n".join(lines)


if __name__ == "__main__":
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("=== 本机网卡 ===")
    print(describe_all())
    print()
    ip, alias = guess_virtual_lan()
    if ip:
        print(f"疑似虚拟局域网网卡: {ip}  ({alias})")
    else:
        print("没识别出虚拟局域网网卡（UU 未启动时正常）")
    print(f"建议默认地址: {best_local_ip()}")
