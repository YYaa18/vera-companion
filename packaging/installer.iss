; 维罗妮卡 X 助手 —— 安装包脚本
;
; 编译:
;   "C:\Users\<你>\AppData\Local\Programs\Inno Setup 7\ISCC.exe" packaging\installer.iss
;
; 产物: packaging\output\VeraCompanion-Setup-<版本>.exe
;
; 这个安装包装的是「助手 + 启动器」，不含游戏本体：
; 游戏是上游 recvx-enhanced-port 的产物，用 tools/sync_upstream.py 拉，
; 而且需要用户自备 PS2 美版镜像。

#define AppName        "维罗妮卡 X 助手"
#define AppNameEn      "Vera Companion"
#define AppVersion     "1.0.0"
#define AppPublisher   "vera-companion"
#define AppExe         "VeraLauncher.exe"
#define UpstreamRepo   "aikatore/recvx-enhanced-port"

[Setup]
AppId={{8F3A7C21-4B6E-4D95-9A2C-7E1F5B83D604}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\VeraCompanion
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=VeraCompanion-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
LicenseFile=..\LICENSE

[Languages]
Name: "chs"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"
Name: "launchafter"; Description: "安装完成后启动"; GroupDescription: "附加任务:"; Flags: unchecked

[Files]
; 主程序（单文件 exe，含启动器与助手）
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
; 游戏程序本体（MIT 开源的 recvx-enhanced-port，不含任何游戏数据）
Source: "..\vendor\game\recvx.exe"; DestDir: "{app}\game"; Flags: ignoreversion
Source: "..\vendor\LICENSE-recvx-enhanced-port.txt"; DestDir: "{app}\game"; Flags: ignoreversion
; mods 目录（可选扩展：HD 材质包、自制房间等）。附中英双语说明。
Source: "..\vendor\game\mods\README_MODS_中英.txt"; DestDir: "{app}\game\mods"; Flags: ignoreversion
Source: "..\vendor\game\mods\textures\README_HD材质包_中英.txt"; DestDir: "{app}\game\mods\textures"; Flags: ignoreversion
; 人设文本，用户可以自己改
Source: "..\app\personas\*.txt"; DestDir: "{app}\personas"; Flags: ignoreversion
; 同步上游的工具
Source: "..\tools\sync_upstream.py"; DestDir: "{app}\tools"; Flags: ignoreversion
Source: "..\tools\relocate_gcheat.py"; DestDir: "{app}\tools"; Flags: ignoreversion
; 文档
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "..\update\UU_LANPLAY.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\update\UPSTREAM.md"; DestDir: "{app}\docs"; Flags: ignoreversion

[Dirs]
; 用户数据目录（安装时就要存在，方便放配置）
Name: "{app}\personas"; Permissions: users-modify
; 游戏的可选扩展目录。游戏不会自己创建，缺失时 HD 材质包没处放。
Name: "{app}\game\mods"; Permissions: users-modify
Name: "{app}\game\mods\textures"; Permissions: users-modify
; 存档目录（游戏也会自己建，这里先建好省得用户找）
Name: "{app}\game\save"; Permissions: users-modify

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent; Tasks: launchafter

[UninstallDelete]
; 卸载时清理生成的缓存，但不动用户配置
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
{ 安装完成后告诉用户游戏本体和镜像要自己准备 }
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    MsgBox(
      '助手已安装。' + #13#10 + #13#10 +
      '还需要两步才能玩：' + #13#10 +
      '1. 游戏本体：在「开始菜单 → 维罗妮卡 X 助手 → 同步工具」里，' +
      '或运行 tools\sync_upstream.py --update 拉取最新版。' + #13#10 +
      '2. 游戏镜像：需要你自己拥有的 PS2 美版（SLUS-20184）ISO，' +
      '在启动器里指定路径。' + #13#10 + #13#10 +
      '首次启动请填 DeepSeek API Key，不填也能玩游戏，只是没有 AI 陪玩。',
      mbInformation, MB_OK);
  end;
end;
