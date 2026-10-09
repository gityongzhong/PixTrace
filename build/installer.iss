; Inno Setup 安装包脚本
;
; 编译（一般不要直接调 ISCC，用 scripts/build.py --installer，它会带上版本号）：
;   ISCC /DAppVersion=0.1.0 installer.iss
;
; 支持两种安装范围：用户安装（免管理员，装到 %LOCALAPPDATA%\Programs）
; 与机器安装（Program Files），由安装向导让用户选择。
;
; 说明：向导文案用 Inno 默认英文。第三方中文 .isl 属于可执行脚本
; （可以带 [Code] 段），没有经过审计之前不放进构建链。

#define AppName "PixTrace"
#define AppExeName "PixTrace.exe"

#ifndef AppVersion
#define AppVersion "0.0.0"
#endif

[Setup]
AppId={{D4A8F2C1-6E37-4B8A-9C55-1F2E7D9B3A64}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion} - batch background remover
DefaultDirName={autopf}\{#AppName}
PrivilegesRequiredOverridesAllowed=dialog commandline
OutputBaseFilename=PixTrace-{#AppVersion}-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
UninstallDisplayIcon={app}\{#AppExeName}
LicenseFile=..\LICENSE
SetupIconFile=..\assets\pixtrace.ico
DisableProgramGroupPage=yes
DisableDirPage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; \
    GroupDescription: "Additional icons:"

[Files]
; onedir 全量拷贝。_internal 目录里的模型、许可文件随包带上。
Source: "..\dist\PixTrace\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; \
    Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "&Launch {#AppName}"; \
    Flags: nowait postinstall skipifsilent

[UninstallRun]
; 没有需要清理的服务或注册表项；模型缓存留在 %LOCALAPPDATA%\pixtrace，
; 属于用户数据，卸载不删（重装可复用，避免重新下载 171MB 的高精档）。

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
