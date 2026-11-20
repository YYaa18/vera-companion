# 维罗妮卡 X 助手 · Vera Companion

《生化危机：代号维罗妮卡 X》PC 重编译版的 AI 语音陪玩助手。

游戏本体来自 [aikatore/recvx-enhanced-port](https://github.com/aikatore/recvx-enhanced-port)（MIT），
本项目只做助手部分，不包含任何游戏数据。

![四个可切换的人设、会走动的桌面角色、实时读取游戏状态](docs/preview.png)

## 它是什么

一条住在你桌面上的小鲸鱼，陪你玩维罗妮卡：

- **会说话**：DeepSeek TTS 语音 + 文字气泡，静音也看得见
- **听得懂**：按住空格说话，ASR 转文字后交给模型
- **看得见**：说「看看屏幕」它才截图，不主动烧钱
- **知道你在哪**：直接读游戏进程内存（只读），拿到血量、位置、背包
- **有人设**：温柔 / 呆萌 / 鬼灵精怪 / 邪恶，四种性格，能力各不相同
- **能联机**：两个玩家的 AI 可以互通状态

## 四个人设的差别

| 人设 | 语气 | 懂游戏吗 | 能做什么 |
|---|---|---|---|
| **温柔** | 像朋友，会紧张 | 懂 | 只能看和说 |
| **呆萌** | 有点笨，经常想歪 | **真的不懂** | 只能看和说 |
| **鬼灵精怪** | 嘴快，爱逗你 | 懂，给具体建议 | 只能看和说 |
| **邪恶** | 慢，带刺，看戏 | 懂 | **能改游戏**：塞武器、刷怪、补血、收回物品 |

「邪恶」是真的能动手——它通过游戏内置的作弊接口给你背包塞东西。
不想被它乱来，就换别的人设。

## 安装

### 方式一：安装包（推荐）

下载 `VeraCompanion-Setup-x.y.z.exe` 双击安装。

### 方式二：绿色版

解压 `VeraLauncher.exe` 到任意目录，双击运行。

### 还需要两步

1. **游戏本体**：本项目不含游戏。运行 `tools/sync_upstream.py --update`
   自动拉取上游最新版（会校验 SHA256）。
2. **游戏镜像**：需要你自己拥有的 PS2 **美版** 光盘镜像，
   **SLUS-20184**。其他区版（日版/欧版/GC/DC）都不支持。
   镜像放哪都行，在启动器里指定。

## 配置

启动器里填 DeepSeek API Key：

1. 打开 [platform.deepseek.com](https://platform.deepseek.com)
2. 左侧「API Keys」→「创建 API Key」
3. 复制 `sk-` 开头的密钥，粘进启动器的 API Key 框
4. 点「测试连接」

**不填也能玩游戏**，只是没有 AI 陪玩。

配置存在 `settings.json`，和启动器同目录。

## 操作

| 动作 | 效果 |
|---|---|
| 单击小鲸鱼 | 开始说话，再点一次发送 |
| 游戏里按住空格 | 按住说话（只在游戏窗口聚焦时生效） |
| 右键小鲸鱼 | 菜单：看屏幕 / 静音 / 自由走动 / 退出 |
| 拖动小鲸鱼 | 挪位置 |

## 费用

用的是你自己的 DeepSeek 账户，按实际用量计费。

| 功能 | 大致成本 |
|---|---|
| 聊天 | 每次 1-2 分钱 |
| 看屏幕 | 每次 3-5 分钱 |
| 语音识别 | 约 $0.058/小时（限时折扣价） |
| 语音合成 | 约 10 万字符/元 |

**读游戏状态完全免费**——那是本地内存读取，不联网。

两个 AI 联机对话有硬性刹车：每分钟最多 4 条事件消息，
累计 2 万字自动静默，2 小时自动断。

## 联机

游戏本身的联机照常用（UDP 7140，端到端加密）。

AI 之间的对话走**独立通道**（TCP 7150），不影响游戏联机：

1. 启动器 → AI 之间对话 → 勾选启用
2. 选角色：房主 / 加入方
3. 房主选好自己的**网卡**，启动器会显示「把这句发给对方 → 172.19.163.2:7150」
4. 加入方填对方那个地址

两个 AI 只在换房间、捡东西、血量骤降时互通消息，不闲聊。

### 推荐用 UU 加速器的虚拟局域网

不需要公网 IP，不需要路由器端口转发：

1. 双方开 UU 加速器，进同一个虚拟局域网房间
2. 双方都会多出一块 `UU Lanplay` 网卡
3. 启动器会自动识别并选中它
4. 游戏联机时把 JOIN ADDRESS 里的公网 IP 换成你的 UU IP 即可

详细步骤和排查见 [update/UU_LANPLAY.md](update/UU_LANPLAY.md)。

## 同步上游更新

```bash
python tools/sync_upstream.py --check    # 看有没有新版
python tools/sync_upstream.py --update   # 下载并安装
```

默认安装到 `E:\RE-CodeVeronica-PC`，用 `--dir` 改。
脚本会校验 SHA256，直连失败自动走镜像。
**不会覆盖** `save/`、`mods/`、`assistant/` 这些用户数据。

## 从源码运行

```bash
pip install -r requirements.txt
python app/main.py               # 启动器
python app/main.py --assistant   # 只要助手
```

打包：

```bash
pyinstaller app/build.spec --noconfirm
```

## 技术说明

- **读游戏状态**：`game_state.py` 通过 `ReadProcessMemory` 读 `g_cheat`
  结构体。上游 Windows 构建 ImageBase 固定 0x30000000 且关闭 ASLR，
  地址稳定。纯只读，不写。
- **改游戏**（仅「邪恶」人设）：写 `g_cheat.request` 标志位，
  由游戏自己执行。只碰这一个结构体。
- **版本敏感**：`g_cheat` 地址在 `game_state.py` 顶部。
  上游大版本更新后可能需要重新定位。

## 许可

本仓库代码 MIT（见 [LICENSE](LICENSE)）。

游戏本体及其数据版权归 Capcom 所有。本项目不附带任何游戏资源，
不提供镜像下载。请使用你自己合法拥有的游戏。

参与者：
- [recvx-enhanced-port](https://github.com/aikatore/recvx-enhanced-port) — AshfordFamily 与贡献者的反编译工作
- [recvx-decomp](https://github.com/AshfordFamily/recvx-decomp) — 底层反编译（MIT）
