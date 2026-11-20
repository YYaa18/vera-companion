"""从上游 recvx-enhanced-port 同步游戏本体更新。

这个仓库只包含 AI 助手，游戏本体是上游的 C 重编译项目。本脚本负责：
  1. 查询上游最新 release
  2. 下载 Windows 包（走镜像回退）
  3. 校验 SHA256
  4. 解压覆盖到游戏目录

用法:
    python tools/sync_upstream.py --check          # 只看有没有新版
    python tools/sync_upstream.py --update         # 下载并安装最新版
    python tools/sync_upstream.py --update --dir "E:\\games\\RE-CVX"
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

UPSTREAM_REPO = "aikatore/recvx-enhanced-port"
# /releases/latest 只返回正式版；这个项目的发布常被标成 pre-release，
# 所以取列表里的第一条。
API = f"https://api.github.com/repos/{UPSTREAM_REPO}/releases?per_page=5"

# 直连失败时依次尝试的 GitHub 镜像前缀
MIRRORS = [
    "",
    "https://ghfast.top/",
    "https://gh-proxy.com/",
    "https://ghproxy.net/",
]

ASSET_FILTER = "windows-x86.zip"      # 排除 -debug 与 linux 包


def http_json(url, timeout=30):
    """GET JSON, falling back through mirrors when the direct call is blocked."""
    last = None
    for prefix in MIRRORS:
        real = url if not prefix else prefix + url
        try:
            req = urllib.request.Request(real, headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "vera-companion-sync",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            continue
    raise RuntimeError(f"所有镜像都取不到 {url}：{last}")


def http_text(url, timeout=60):
    last = None
    for prefix in MIRRORS:
        real = url if not prefix else prefix + url
        try:
            req = urllib.request.Request(real, headers={"User-Agent": "vera-companion-sync"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            continue
    raise RuntimeError(f"所有镜像都取不到 {url}：{last}")


def latest_release():
    releases = http_json(API)
    if not releases:
        raise RuntimeError("上游没有发布任何 release")
    d = releases[0]
    assets = {}
    for a in d.get("assets", []):
        n = a["name"]
        if n.endswith(ASSET_FILTER) and "debug" not in n:
            assets["windows"] = a
        if n == "SHA256SUMS":
            assets["sums"] = a
    return d.get("tag_name", "?"), d.get("published_at", ""), assets


def download(url, dest, timeout=1800):
    """Try the URL directly, then through mirrors."""
    for prefix in MIRRORS:
        real = url if not prefix else prefix + url
        try:
            req = urllib.request.Request(real, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                got = 0
                while True:
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    if total:
                        pct = got * 100 // total
                        print(f"\r  {got/1048576:6.1f} / {total/1048576:.1f} MB  {pct}%",
                              end="", flush=True)
            print()
            if total and got != total:
                print(f"  ! 大小不符（{got} vs {total}），换镜像重试")
                os.remove(dest)
                continue
            return True
        except Exception as e:
            print(f"  ! {prefix or '直连'} 失败：{type(e).__name__}")
            if os.path.exists(dest):
                try:
                    os.remove(dest)
                except OSError:
                    pass
    return False


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def installed_version(game_dir):
    """Ask the installed exe for its version."""
    exe = os.path.join(game_dir, "recvx.exe")
    if not os.path.exists(exe):
        return None
    try:
        out = subprocess.run([exe, "--version"], capture_output=True,
                             timeout=20,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        text = (out.stdout or b"").decode("utf-8", "replace").strip()
        return text or None
    except Exception:
        return None


def cmd_check(game_dir):
    tag, when, assets = latest_release()
    print(f"上游最新: {tag}  ({when[:10]})")
    cur = installed_version(game_dir)
    print(f"本地已装: {cur or '（未安装）'}")
    if cur and tag.strip("v") in cur:
        print("\n已是最新。")
        return 0
    print(f"\n有新版可更新。运行：python tools/sync_upstream.py --update")
    return 1


def cmd_update(game_dir):
    tag, when, assets = latest_release()
    print(f"上游最新: {tag}  ({when[:10]})")

    if "windows" not in assets:
        print("！这个 release 没有 Windows 包")
        return 2
    asset = assets["windows"]
    print(f"下载: {asset['name']}  ({asset['size']/1048576:.1f} MB)")

    tmpdir = tempfile.mkdtemp(prefix="vera_upd_")
    zip_path = os.path.join(tmpdir, asset["name"])
    try:
        if not download(asset["browser_download_url"], zip_path):
            print("下载失败（所有镜像都不通）")
            return 3

        # 校验
        if "sums" in assets:
            try:
                sums = http_text(assets["sums"]["browser_download_url"])
                want = None
                for line in sums.splitlines():
                    parts = line.split()
                    if len(parts) == 2 and parts[1].lstrip("*") == asset["name"]:
                        want = parts[0]
                        break
                if want:
                    got = sha256_of(zip_path)
                    if got.lower() != want.lower():
                        print(f"！校验失败\n  期望 {want}\n  实际 {got}")
                        return 4
                    print("SHA256 校验通过")
                else:
                    print("（校验文件里没有这个包的记录，跳过）")
            except Exception as e:
                print(f"（校验下载失败：{type(e).__name__}，跳过）")
        else:
            print("（这个 release 没提供 SHA256SUMS，跳过校验）")

        # 解压：找出含 recvx.exe 的那层
        with zipfile.ZipFile(zip_path) as z:
            names = z.namelist()
            roots = {n.split("/")[0] for n in names if "/" in n}
            z.extractall(tmpdir)

        src = None
        for root in roots:
            cand = os.path.join(tmpdir, root)
            if os.path.exists(os.path.join(cand, "recvx.exe")):
                src = cand
                break
        if not src:
            if os.path.exists(os.path.join(tmpdir, "recvx.exe")):
                src = tmpdir
            else:
                print("！解压结果里找不到 recvx.exe")
                return 5

        os.makedirs(game_dir, exist_ok=True)
        replaced = 0
        for name in os.listdir(src):
            s = os.path.join(src, name)
            d = os.path.join(game_dir, name)
            if name.lower() in ("save", "mods", "assistant"):   # 用户数据，绝不覆盖
                print(f"  跳过 {name}/（用户数据）")
                continue
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
            replaced += 1
        print(f"已更新 {replaced} 项到 {game_dir}")
        print(f"现在版本: {installed_version(game_dir) or '?'}")
        return 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="同步上游游戏本体")
    ap.add_argument("--dir", default=r"E:\RE-CodeVeronica-PC",
                    help="游戏安装目录（含 recvx.exe）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="只检查版本")
    g.add_argument("--update", action="store_true", help="下载并安装最新版")
    args = ap.parse_args()
    return cmd_check(args.dir) if args.check else cmd_update(args.dir)


if __name__ == "__main__":
    sys.exit(main())
