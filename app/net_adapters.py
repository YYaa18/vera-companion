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


def _adapter_names_powershell():
    """Map ip -> adapter alias via PowerShell (the fast path)."""
    out = {}
    try:
        import subprocess
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetIPAddress -AddressFamily IPv4 | "
             "Select-Object IPAddress,InterfaceAlias | "
             "ForEach-Object { $_.IPAddress + '|' + $_.InterfaceAlias }"],
            capture_output=True, timeout=12,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if r.returncode != 0:
            return {}
        text = r.stdout.decode("mbcs", "replace")
        for line in text.splitlines():
            if "|" in line:
                ip, alias = line.split("|", 1)
                out[ip.strip()] = alias.strip()
    except Exception:
        pass
    return out


def _adapter_names_ctypes():
    """Fallback: enumerate adapters through the Windows IP Helper API.

    Works inside a frozen exe where spawning PowerShell may be blocked or too
    slow. Returns the same shape as the PowerShell path.
    """
    import ctypes
    from ctypes import wintypes

    out = {}
    iphlp = ctypes.WinDLL("iphlpapi", use_last_error=True)

    class SOCKADDR(ctypes.Structure):
        _fields_ = [("sa_family", wintypes.USHORT), ("sa_data", ctypes.c_ubyte * 14)]

    class SOCKET_ADDRESS(ctypes.Structure):
        _fields_ = [("lpSockaddr", ctypes.POINTER(SOCKADDR)),
                    ("iSockaddrLength", ctypes.c_int)]

    class IP_ADAPTER_UNICAST_ADDRESS(ctypes.Structure):
        pass

    IP_ADAPTER_UNICAST_ADDRESS._fields_ = [
        ("Length", wintypes.ULONG),
        ("Flags", wintypes.DWORD),
        ("Next", ctypes.POINTER(IP_ADAPTER_UNICAST_ADDRESS)),
        ("Address", SOCKET_ADDRESS),
        ("PrefixOrigin", ctypes.c_int),
        ("SuffixOrigin", ctypes.c_int),
        ("DadState", ctypes.c_int),
        ("ValidLifetime", wintypes.ULONG),
        ("PreferredLifetime", wintypes.ULONG),
        ("LeaseLifetime", wintypes.ULONG),
        ("OnLinkPrefixLength", ctypes.c_ubyte),
    ]

    class IP_ADAPTER_ADDRESSES(ctypes.Structure):
        pass

    IP_ADAPTER_ADDRESSES._fields_ = [
        ("Length", wintypes.ULONG),
        ("IfIndex", wintypes.DWORD),
        ("Next", ctypes.POINTER(IP_ADAPTER_ADDRESSES)),
        ("AdapterName", ctypes.c_char_p),
        ("FirstUnicastAddress", ctypes.POINTER(IP_ADAPTER_UNICAST_ADDRESS)),
        ("FirstAnycastAddress", ctypes.c_void_p),
        ("FirstMulticastAddress", ctypes.c_void_p),
        ("FirstDnsServerAddress", ctypes.c_void_p),
        ("DnsSuffix", ctypes.c_wchar_p),
        ("Description", ctypes.c_wchar_p),
        ("FriendlyName", ctypes.c_wchar_p),
        ("PhysicalAddress", ctypes.c_ubyte * 8),
        ("PhysicalAddressLength", wintypes.DWORD),
        ("Flags", wintypes.DWORD),
        ("Mtu", wintypes.DWORD),
        ("IfType", wintypes.DWORD),
        ("OperStatus", ctypes.c_int),
        ("Ipv6IfIndex", wintypes.DWORD),
        ("ZoneIndices", wintypes.DWORD * 16),
        ("FirstPrefix", ctypes.c_void_p),
    ]

    flags = 0x0080      # GAA_FLAG_SKIP_ANYCAST | SKIP_MULTICAST | SKIP_DNS_SERVER
    size = wintypes.ULONG(16384)
    buf = ctypes.create_string_buffer(size.value)
    for _ in range(3):
        ret = iphlp.GetAdaptersAddresses(0, flags, None, buf, ctypes.byref(size))
        if ret == 0:
            break
        if ret == 111:      # ERROR_BUFFER_OVERFLOW
            buf = ctypes.create_string_buffer(size.value)
            continue
        return {}
    if ret != 0:
        return {}

    ptr = ctypes.cast(buf, ctypes.POINTER(IP_ADAPTER_ADDRESSES))
    while ptr:
        ad = ptr.contents
        name = ad.FriendlyName or ""
        ua = ad.FirstUnicastAddress
        while ua:
            sa = ua.contents.Address
            if sa.lpSockaddr and sa.iSockaddrLength >= 8:
                # sockaddr_in: family(2) + port(2) + addr(4)
                raw = ctypes.string_at(sa.lpSockaddr, sa.iSockaddrLength)
                if len(raw) >= 8 and raw[0] == 2:      # AF_INET
                    ip = ".".join(str(b) for b in raw[4:8])
                    out[ip] = name
            ua = ua.contents.Next
        ptr = ad.Next
    return out


def _adapter_names():
    """Map ip -> adapter alias. PowerShell first, ctypes API as fallback."""
    out = _adapter_names_powershell()
    if out:
        return out
    try:
        return _adapter_names_ctypes()
    except Exception:
        return {}


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


# ============================================================
# 以下给启动器用：把技术细节翻译成人话
# ============================================================

# 明确值得推荐的虚拟局域网工具（按优先级）
VLAN_HINTS = [
    ("uu", "UU 加速器的联机房间"),
    ("uu lanplay", "UU 加速器的联机房间"),
    ("tailscale", "Tailscale 虚拟局域网"),
    ("zerotier", "ZeroTier 虚拟局域网"),
    ("hamachi", "Hamachi 虚拟局域网"),
    ("radmin", "Radmin VPN 虚拟局域网"),
    ("游戏加加", "游戏加加组网"),
]

IGNORE_HINTS = ("vmware", "vmnet", "virtualbox", "vbox", "hyper-v",
                "vethernet", "docker", "wsl", "loopback", "wi-fi direct",
                "蓝牙", "bluetooth")


def friendly_rows():
    """Like list_adapters(), but each row explains itself in plain language.

    Returns [(ip, alias, kind, label, recommended)] sorted with the best
    candidate first. label is what a non-technical user should read.
    """
    rows = list_adapters()
    out = []
    vlan_ip, vlan_alias = guess_virtual_lan()

    for ip, alias, kind in rows:
        low = alias.lower()

        # 明确该忽略的（虚拟机、Docker 之类）
        if any(h in low for h in IGNORE_HINTS):
            out.append((ip, alias, kind, "（虚拟机用，一般不用选）", False))
            continue

        # 识别虚拟局域网工具
        matched = None
        for hint, human in VLAN_HINTS:
            if hint in low:
                matched = human
                break
        if matched:
            out.append((ip, alias, kind, f"{matched} — 联机时选这个", True))
            continue

        # 物理网卡
        if kind == "lan":
            out.append((ip, alias, kind, "家里的路由器 / WiFi", False))
        elif kind == "public":
            out.append((ip, alias, kind, "直接连公网", False))
        else:
            out.append((ip, alias, kind, "（没连上网络）", False))

    # 推荐的排最前
    out.sort(key=lambda r: (not r[4], r[0]))
    return out


def best_guess():
    """(ip, human_label) — what to preselect, in plain words.

    Priority: a recognised virtual-LAN adapter > any private address >
    whatever the default route uses.
    """
    rows = friendly_rows()
    for ip, alias, kind, label, rec in rows:
        if rec:
            return ip, label
    for ip, alias, kind, label, rec in rows:
        if kind == "lan":
            return ip, label
    if rows:
        return rows[0][0], rows[0][3]
    return "", ""


def status_summary():
    """One sentence for the launcher: what did we find, what should the user do."""
    rows = friendly_rows()
    vlan = [r for r in rows if r[4]]
    if vlan:
        ip, alias, kind, label, _ = vlan[0]
        return ("ok", f"已找到 {label}，地址 {ip}。把这个地址发给队友就行。")

    has_router = any(r[2] == "lan" and not r[4] and "虚拟机" not in r[3]
                     for r in rows)
    if has_router:
        return ("warn",
                "没找到 UU 的联机网卡。如果你们用 UU 联机，"
                "请先在 UU 里进同一个房间，然后重启这个启动器。")
    return ("warn", "没检测到可用的网络连接，请先连上网。")
