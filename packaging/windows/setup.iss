; DDE Windows complete installer (Inno Setup 6)
; Bundles DDE Code (Electron) + Core appliance + first-run wizard.
; Build: powershell.exe -File packaging/windows/scripts/Build-Installer.ps1

#define MyAppName "DDE"
#ifndef MyAppVersion
  #define MyAppVersion GetEnv("DDE_INSTALLER_VERSION")
#endif
#if MyAppVersion == ""
  #define MyAppVersion "0.1.0"
#endif
#define MyAppPublisher "DDE"
#define MyAppURL "https://github.com/Vanguduza/dde"

#ifndef RepoRoot
  #define RepoRoot GetEnv("DDE_REPO_ROOT")
#endif
#if RepoRoot == ""
  #define RepoRoot "..\.."
#endif

#ifndef DistDir
  #define DistDir GetEnv("DDE_DIST_WINDOWS")
#endif
#if DistDir == ""
  #define DistDir "..\..\dist\windows"
#endif

#ifndef DesktopUnpacked
  #define DesktopUnpacked GetEnv("DDE_DESKTOP_UNPACKED")
#endif
#if DesktopUnpacked == ""
  #define DesktopUnpacked "..\..\interfaces\dde-studio\desktop\dist\win-unpacked"
#endif

#ifndef CoreImageTag
  #define CoreImageTag GetEnv("DDE_CORE_IMAGE_TAG")
#endif
#if CoreImageTag == ""
  #define CoreImageTag "dde-core:0.1.0"
#endif

[Setup]
AppId={{8F3C2A11-6B4E-4D9A-9C21-DDE000000001}
AppVersion={#MyAppVersion}
AppName={#MyAppName}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\DDE
DefaultGroupName=DDE
DisableProgramGroupPage=yes
OutputDir={#DistDir}
OutputBaseFilename=DDE-Complete-Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
SetupLogging=yes
UninstallDisplayIcon={app}\dde-code\DDE Code.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut to DDE Code"; GroupDescription: "Additional icons:"
Name: "runapp"; Description: "Launch DDE Code after install"; GroupDescription: "Setup:"; Flags: checkedonce
Name: "runwizard"; Description: "Launch Core setup wizard after install (Docker, Claude Code CLI, credentials)"; GroupDescription: "Setup:"; Flags: unchecked

[Files]
Source: "{#RepoRoot}\packaging\windows\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\packaging\windows\config.example.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\packaging\windows\docker-compose.appliance.yml"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\packaging\windows\scripts\*"; DestDir: "{app}\scripts"; Flags: ignoreversion recursesubdirs
Source: "{#DistDir}\DdeSetupWizard.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#DistDir}\payload\dde-core.tar"; DestDir: "{app}\payload"; Flags: ignoreversion
Source: "{#DistDir}\VERSION"; DestDir: "{app}"; Flags: ignoreversion
; DDE Code desktop (Electron unpacked) — primary UI
Source: "{#DesktopUnpacked}\*"; DestDir: "{app}\dde-code"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{commonappdata}\DDE"
Name: "{commonappdata}\DDE\artifacts"
Name: "{commonappdata}\DDE\logs"

[Icons]
Name: "{group}\DDE Code"; Filename: "{app}\dde-code\DDE Code.exe"; WorkingDir: "{app}\dde-code"
Name: "{group}\DDE Setup Wizard"; Filename: "{app}\DdeSetupWizard.exe"; WorkingDir: "{app}"
Name: "{group}\Start DDE Local"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\Start-DdeLocal.ps1"""; WorkingDir: "{app}"
Name: "{group}\Stop DDE Local"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\Stop-DdeLocal.ps1"""; WorkingDir: "{app}"
Name: "{autodesktop}\DDE Code"; Filename: "{app}\dde-code\DDE Code.exe"; WorkingDir: "{app}\dde-code"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\Install-DdeServices.ps1"" -InstallRoot ""{app}"" -Version ""{#MyAppVersion}"" -CoreImageTag ""{#CoreImageTag}"""; StatusMsg: "Registering DDE install metadata..."; Flags: runhidden waituntilterminated
Filename: "{app}\DdeSetupWizard.exe"; Description: "Launch Core setup wizard (Docker, credentials, migrate, start Core)"; Flags: postinstall nowait skipifsilent; Tasks: runwizard
Filename: "{app}\dde-code\DDE Code.exe"; Description: "Launch DDE Code"; Flags: postinstall nowait skipifsilent; Tasks: runapp

[Code]
procedure InitializeWizard();
begin
  WizardForm.WelcomeLabel2.Caption :=
    'This installer is the complete Windows DDE product:' + #13#10 +
    '  • DDE Code — desktop UI (Hermes / Claude Code / DeepSeek dashboards)' + #13#10 +
    '  • DDE Core image + Postgres + Redis + migrations (Docker appliance)' + #13#10 +
    '  • First-run wizard for Docker, credentials, Claude Code CLI + auth, and stack startup' + #13#10 + #13#10 +
    'After install, open DDE Code. On first run it will offer the setup wizard' + #13#10 +
    'if Core is not configured yet, then Start local Core when ready.' + #13#10 + #13#10 +
    'Worker execution requires Docker Desktop (WSL2).' + #13#10 +
    'Subscription auth requires the official Claude Code CLI (`claude` on PATH);' + #13#10 +
    'the wizard installs it with consent (Ensure-ClaudeCli.ps1).';
end;
