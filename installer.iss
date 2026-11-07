; Inno Setup 安装包脚本（Inno Setup 6 / 7 均可编译）
;
; 依赖：先用 PyInstaller 打包目录版（pyinstaller FileVerifyRename.spec），
;       确认 dist\文件校验重命名工具\ 已生成，再编译本文件。
;
; 产物：..\Output\文件校验重命名工具_v<版本>_安装包.exe
;       （相对路径以本 .iss 文件所在目录为基准）
;
; 直接编译：
;   "D:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
; 或一键（推荐，会自动挑 Python、打目录版、压 zip）：
;   ..\build.bat

#define MyAppName "文件校验重命名工具"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Lanjor Croft, Independent Creator & Maker"
#define MyAppExeName "文件校验重命名工具.exe"

[Setup]
; 注意：AppId 必须是纯 ASCII 的 GUID（不要用全角/非断行连字符），
; 否则不同版本会被识别成两个程序，导致升级与卸载异常。
; 发版时**不要修改这一行**，否则覆盖升级会失效。
AppId={{904F3B78-1234-4ABC-90AA-D8E7C2A11001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; {commonpf} = Program Files（32 位模式下的 Program Files (x86)），等价于旧写法 {pf}
; Inno 6.7 起 {pf} 已弃用并会告警，故改用新名称
DefaultDirName={commonpf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; 输出到项目根目录的 Output\，文件名带版本号，便于与旧版共存
OutputDir=..\Output
OutputBaseFilename={#MyAppName}_v{#MyAppVersion}_安装包
SetupIconFile=assets\logo.ico
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
DisableStartupPrompt=yes
; exe 文件属性里显示的版本信息
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} 安装程序
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Files]
; 路径相对本 .iss 文件所在目录
Source: "dist\文件校验重命名工具\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "创建桌面快捷方式"; GroupDescription: "附加图标："; Flags: checkedonce

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "运行 {#MyAppName}"; Flags: nowait postinstall skipifsilent
