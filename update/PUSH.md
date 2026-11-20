# 推送到 GitHub

仓库已经在本地建好了（`E:\vera-companion`），提交也做完了。
剩下创建远程仓库并推送，三步。

## 步骤

### 1. 在 GitHub 上创建空仓库

打开 <https://github.com/new>

- **Repository name**：`vera-companion`（或你喜欢的名字）
- **Description**：可选，比如 `生化危机：代号维罗妮卡 X 的 AI 语音陪玩助手`
- **Public / Private**：自己选
- ⚠️ **不要**勾选 "Add a README file"、"Add .gitignore"、"Choose a license"
  （本地已经有这些文件，勾了会冲突）

点 **Create repository**。

### 2. 关联远程并推送

创建完 GitHub 会显示一段命令。用下面这个：

```bash
cd E:\vera-companion

git remote add origin https://github.com/你的用户名/vera-companion.git
git branch -M main
git push -u origin main
```

第一次 push 会要求登录。**用 Personal Access Token，不要用密码**
（GitHub 2021 年起就不接受密码了）：

1. 打开 <https://github.com/settings/tokens>
2. **Generate new token (classic)**
3. Note 随便填，Expiration 选 90 天
4. 勾选 **repo** 整个大项
5. 生成后复制那串 `ghp_...`
6. push 时密码框里粘贴这个 token

Windows 上 git 会记住凭据，之后不用再输。

### 3. 验证

```bash
git remote -v
git log --oneline
```

应该看到 `origin` 指向你的仓库，以及两条提交记录。

## 之后怎么维护

### 改了代码

```bash
cd E:\vera-companion
git add -A
git commit -m "说明改了什么"
git push
```

### 上游游戏更新了

```bash
python tools\sync_upstream.py --check     # 看看有没有新版
python tools\sync_upstream.py --update    # 拉下来
```

这**不会**产生 git 提交——游戏本体不进这个仓库。

### 上游改了 CheatState 结构体（助手读不到状态了）

```bash
python tools\relocate_gcheat.py --exe "E:\RE-CodeVeronica-PC\recvx.exe"
```

它会输出新的地址，改 `app/game_state.py` 顶部那行 `G_CHEAT_ADDR =`，
然后提交。

### 想发新版本

```bash
packaging\build_all.bat
```

会生成 `packaging\output\VeraCompanion-Setup-x.y.z.exe`。
发到 GitHub Releases 当附件（exe 太大，不进 git）。

## 常见问题

**Q: push 报 `Connection was reset`**

GitHub 直连不稳。用镜像代理：

```bash
git config --global http.proxy http://127.0.0.1:7890   # 换成你自己的代理端口
```

或者用 SSH（需要配密钥）：

```bash
git remote set-url origin git@github.com:你的用户名/vera-companion.git
```

**Q: 不小心把 settings.json 提交了**

里面有你的 API Key，**立刻去 DeepSeek 平台作废那个 key**，然后：

```bash
git rm --cached settings.json
git commit -m "移除误提交的配置"
git push
```

注意：历史里还有，要彻底清除得用 `git filter-repo`。反正先换 key。

**Q: 想让别人也能用**

把安装包 `VeraCompanion-Setup-x.y.z.exe` 发给他就行。
他需要：
1. 自己的 DeepSeek API Key
2. 自己拥有的 PS2 美版镜像（SLUS-20184）
3. 跑一次 `sync_upstream.py --update` 拿游戏本体
