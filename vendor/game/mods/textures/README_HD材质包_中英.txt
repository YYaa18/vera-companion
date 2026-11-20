════════════════════════════════════════════════════════════
  HD TEXTURES / HD 材质包目录
════════════════════════════════════════════════════════════

【中文】

想让画面更清晰？把 PCSX2 的 HD 材质包放进这个文件夹。

  要求：材质包必须是给 PS2 美版做的（游戏编号 SLUS-20184）
  不需要转换，直接放进来就能用。

目录结构（三种都行）：
  textures/SLUS-20184/replacements/...   ← PCSX2 原始布局
  textures/replacements/...              ← 只放 replacements 里面
  textures/你的包名/...                  ← 自己建个文件夹

装了多个包：
  每个包放一个文件夹，名字前面加数字，例如
    1_细节增强/
    2_基础包/
  同名的贴图，名字排在前面的优先（1_ 会盖过 2_）。

怎么确认生效：
  游戏启动后看日志，会有一行
    hd textures: 1234 replacements in <文件夹>
  数字是你实际加载的贴图数量。

注意：
  · 材质包会让首次进入每个房间稍微变慢（检查贴图），之后就正常了
  · 换了材质包之后，删掉 save/hd_textures.txt 让它重新检查

────────────────────────────────────────────────────────────

【English】

Want sharper visuals? Put a PCSX2 HD texture pack in this folder.

  Requirement: the pack must be for the PS2 US release (SLUS-20184).
  No conversion needed — drop it in and the game loads it.

Accepted layouts (any of these):
  textures/SLUS-20184/replacements/...   <- PCSX2's own layout
  textures/replacements/...              <- just the replacements content
  textures/your-pack-name/...            <- your own folder

Multiple packs:
  One folder per pack, numbered by priority, e.g.
    1_detail/
    2_base/
  When two packs replace the same texture, the earlier folder name wins.

How to confirm it loaded:
  After launching, the log prints a line like
    hd textures: 1234 replacements in <folder>
  That number is how many textures were replaced.

Notes:
  · The first visit to each room is slightly slower while textures are checked
  · After changing packs, delete save/hd_textures.txt to force a re-check

════════════════════════════════════════════════════════════
