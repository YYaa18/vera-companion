# 上游同步说明

## 为什么不 fork

上游 [aikatore/recvx-enhanced-port](https://github.com/aikatore/recvx-enhanced-port) 是
C 语言写的 PS2 游戏反编译+重编译项目，和我们的 Python 助手是**两个独立代码库**。
我们的代码里没有一行属于上游，硬套 fork 只会让两个仓库的历史纠缠在一起。

所以采用「独立仓库 + 定期拉取上游产物」的方式：

```
上游仓库 (C 代码)
    │  发布 release（编译好的 recvx.exe）
    ▼
tools/sync_upstream.py  ← 本仓库
    │  下载 + SHA256 校验 + 解压
    ▼
游戏安装目录
```

## 同步命令

```bash
# 看有没有新版
python tools/sync_upstream.py --check

# 下载并安装最新版
python tools/sync_upstream.py --update

# 装到别的目录
python tools/sync_upstream.py --update --dir "D:\Games\RE-CVX"
```

脚本会：
1. 查上游 release 列表（自动走 GitHub 镜像，直连被墙时也能用）
2. 下载 Windows 包
3. **校验 SHA256**（对照上游的 SHA256SUMS）
4. 解压覆盖，但**跳过** `save/` `mods/` `assistant/` 这些用户数据

## 如果你想让 git 也跟踪上游源码

上游源码在墙内 git 拉不动（`Connection was reset`）。真有需要时：

```bash
# 用镜像克隆
git clone https://ghfast.top/https://github.com/aikatore/recvx-enhanced-port.git

# 或者只加远程，用镜像 fetch
git remote add upstream https://ghfast.top/https://github.com/aikatore/recvx-enhanced-port.git
git fetch upstream --tags
```

注意：上游是 C 项目，自己编译需要 mingw-w64 i686 交叉工具链
（**不支持 MSVC**）。详见上游的 `docs/BUILDING.md`。

我们只消费它的 release 产物，不参与它的源码开发。

## 上游更新时要留意什么

我们的助手依赖两处上游实现细节：

| 依赖 | 位置 | 上游改了会怎样 |
|---|---|---|
| `g_cheat` 结构体地址 `0x30674840` | `app/game_state.py` 顶部 | 读不到血量/背包，助手只会说"游戏没运行" |
| `g_cheat` 字段布局 | 同上 | 数据错位，可能显示错误的血量 |

`g_cheat` 的地址来自上游 Windows 构建的固定 ImageBase（0x30000000）+ 关闭 ASLR。
上游如果改了 `CheatState` 结构体（`pc/src/host/cheat.h`），需要重新定位。

### 上游大版本后的检查步骤

1. 跑 `python tools/sync_upstream.py --update`
2. 启动游戏进到能走动的状态
3. 运行助手，问它"我在哪"
4. 如果它说"游戏没运行"或位置明显不对，说明地址变了

重新定位的方法（在 `app/` 目录）：

```python
from game_state import find_pid
# 用 tools/relocate_gcheat.py（如果存在）或参考下面的思路
```
