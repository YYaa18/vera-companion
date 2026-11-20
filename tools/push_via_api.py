"""当 git push 被墙时，用 GitHub Contents API 逐文件上传。

git 的传输层走不通（RPC failed），但 gh api 走的是不同的路径，通常可用。
这个脚本把指定提交里改动的文件，通过 API 写到目标分支。

用法:
    python tools/push_via_api.py --repo YYaa18/vera-companion --branch main
"""
import argparse
import base64
import json
import os
import subprocess
import sys

GH = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                  "GitHub CLI", "gh.exe")


def gh(*args, input_data=None):
    """Run gh and return parsed JSON."""
    cmd = [GH if os.path.exists(GH) else "gh"] + list(args)
    r = subprocess.run(cmd, capture_output=True, input=input_data, timeout=120,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip()[:400])
    out = r.stdout.decode("utf-8", "replace").strip()
    return json.loads(out) if out.startswith(("{", "[")) else out


def changed_files(commit="HEAD"):
    r = subprocess.run(["git", "show", "--name-status", "--format=", commit],
                       capture_output=True)
    rows = []
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            status, path = parts[0].strip(), parts[-1].strip()
            if path:
                rows.append((status, path))
    return rows


def get_sha(repo, path, branch):
    try:
        d = gh("api", f"repos/{repo}/contents/{path}?ref={branch}")
        return d.get("sha")
    except Exception:
        return None


def put_file(repo, path, local, branch, message, sha=None):
    with open(local, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    payload = {"message": message, "content": content, "branch": branch}
    if sha:
        payload["sha"] = sha
    return gh("api", "-X", "PUT", f"repos/{repo}/contents/{path}",
              "--input", "-", input_data=json.dumps(payload).encode())


def delete_file(repo, path, branch, message, sha):
    payload = {"message": message, "sha": sha, "branch": branch}
    return gh("api", "-X", "DELETE", f"repos/{repo}/contents/{path}",
              "--input", "-", input_data=json.dumps(payload).encode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--branch", default="main")
    ap.add_argument("--commit", default="HEAD")
    ap.add_argument("--message", default="sync via API")
    args = ap.parse_args()

    rows = changed_files(args.commit)
    if not rows:
        print("没有待推送的文件")
        return 0

    print(f"共 {len(rows)} 个文件：")
    ok = fail = 0
    for status, path in rows:
        if not os.path.exists(path) and status != "D":
            print(f"  跳过 {path}（本地不存在）")
            continue
        try:
            sha = get_sha(args.repo, path, args.branch)
            if status == "D":
                if sha:
                    delete_file(args.repo, path, args.branch, args.message, sha)
                    print(f"  删除 {path}")
                    ok += 1
                continue
            put_file(args.repo, path, path, args.branch, args.message, sha)
            action = "更新" if sha else "新建"
            print(f"  {action} {path}")
            ok += 1
        except Exception as e:
            print(f"  失败 {path}: {e}")
            fail += 1

    print(f"\n完成：{ok} 成功，{fail} 失败")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
