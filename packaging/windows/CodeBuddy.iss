; CodeBuddy Setup for Windows (Inno Setup 6). packaging/build.py runs:
;   ISCC.exe /DVersion=0.2.0 /DSource=<package dir> /DAssets=<assets dir> /DOut=<dist> CodeBuddy.iss
; Per-user install, no admin rights: %LOCALAPPDATA%\Programs\CodeBuddy.

#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppId={{7B1E2C4D-8F3A-4C6B-9D2E-C0DEB0DD1E50}
AppName=CodeBuddy
AppVersion={#Version}
AppPublisher=CodeBuddy
AppPublisherURL=https://github.com/TheNemesis47/CodeBuddy
DefaultDirName={localappdata}\Programs\CodeBuddy
DefaultGroupName=CodeBuddy
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#Out}
OutputBaseFilename=CodeBuddy-Setup-{#Version}
SetupIconFile={#Assets}\codebuddy.ico
UninstallDisplayIcon={app}\codebuddy.ico
WizardStyle=modern
WizardImageFile={#Assets}\wizard.bmp
WizardSmallImageFile={#Assets}\wizard-small.bmp
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
italian.StartWithWindows=Avvia CodeBuddy all'accesso a Windows
english.StartWithWindows=Start CodeBuddy when I sign in to Windows
italian.OpenFolder=Apri la cartella del plugin PyCharm
english.OpenFolder=Open the PyCharm plugin folder

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "{cm:StartWithWindows}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#Source}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs
Source: "{#Assets}\codebuddy.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\CodeBuddy"; Filename: "{app}\overlay\codebuddy-overlay.exe"; Parameters: "--start-brain ""\""{app}\brain\buddy.exe\"" serve"""; IconFilename: "{app}\codebuddy.ico"
Name: "{group}\{cm:UninstallProgram,CodeBuddy}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\CodeBuddy"; Filename: "{app}\overlay\codebuddy-overlay.exe"; Parameters: "--start-brain ""\""{app}\brain\buddy.exe\"" serve"""; IconFilename: "{app}\codebuddy.ico"; Tasks: desktopicon
Name: "{userstartup}\CodeBuddy"; Filename: "{app}\overlay\codebuddy-overlay.exe"; Parameters: "--start-brain ""\""{app}\brain\buddy.exe\"" serve"""; IconFilename: "{app}\codebuddy.ico"; Tasks: autostart

[Run]
Filename: "{app}\overlay\codebuddy-overlay.exe"; Parameters: "--start-brain ""\""{app}\brain\buddy.exe\"" serve"""; Description: "{cm:LaunchProgram,CodeBuddy}"; Flags: nowait postinstall skipifsilent
Filename: "{app}"; Description: "{cm:OpenFolder}"; Flags: postinstall shellexec skipifsilent unchecked

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM codebuddy-overlay.exe"; Flags: runhidden; RunOnceId: "StopOverlay"
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM buddy.exe"; Flags: runhidden; RunOnceId: "StopBrain"

[Messages]
italian.FinishedLabel=CodeBuddy è installato. Il pannello compare in alto al centro dello schermo.%n%nUltimo passo: in PyCharm, Settings → Plugins → ⚙ → Install Plugin from Disk… e scegli il file codebuddy-pycharm nella cartella di CodeBuddy.
english.FinishedLabel=CodeBuddy is installed. The panel shows at the top centre of the screen.%n%nLast step: in PyCharm, Settings → Plugins → ⚙ → Install Plugin from Disk… and pick the codebuddy-pycharm file in the CodeBuddy folder.
