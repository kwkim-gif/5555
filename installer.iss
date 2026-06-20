; AI STT Studio - Inno Setup Script
; Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
; Compile: ISCC.exe installer.iss

#define MyAppName      "AI STT Studio"
#define MyAppVersion   "1.0.0"
#define MyAppPublisher "AI STT Studio"
#define MyAppExeName   "AISTTStudio.exe"
#define MyAppDir       "dist\AISTTStudio_Package"

[Setup]
AppId={{8F3A2B1C-4D5E-6F7A-8B9C-0D1E2F3A4B5C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=dist\installer
OutputBaseFilename=AISTTStudio_Setup_v{#MyAppVersion}
SetupIconFile=assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0.17763
DisableProgramGroupPage=no
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#MyAppDir}\{#MyAppExeName}";  DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyAppDir}\app.py";           DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyAppDir}\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyAppDir}\engines\*";   DestDir: "{app}\engines";   Flags: ignoreversion recursesubdirs
Source: "{#MyAppDir}\audio\*";     DestDir: "{app}\audio";     Flags: ignoreversion recursesubdirs
Source: "{#MyAppDir}\subtitle\*";  DestDir: "{app}\subtitle";  Flags: ignoreversion recursesubdirs
Source: "{#MyAppDir}\ui\*";        DestDir: "{app}\ui";        Flags: ignoreversion recursesubdirs
Source: "{#MyAppDir}\workers\*";   DestDir: "{app}\workers";   Flags: ignoreversion recursesubdirs
Source: "{#MyAppDir}\benchmark\*"; DestDir: "{app}\benchmark"; Flags: ignoreversion recursesubdirs
Source: "{#MyAppDir}\config\*";    DestDir: "{app}\config";    Flags: ignoreversion recursesubdirs

[Dirs]
Name: "{app}\logs"
Name: "{app}\error_logs"
Name: "{app}\output"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall";    Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; \
  Description: "Launch AI STT Studio now"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\error_logs"

[Code]
function IsPythonInstalled(): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('python', '--version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
    and (ResultCode = 0);
end;

function InitializeSetup(): Boolean;
begin
  if not IsPythonInstalled() then begin
    if MsgBox(
      'Python 3.11 or later is required.' + #13#10 +
      'Please install it from https://www.python.org and rerun this installer.' + #13#10#13#10 +
      'Continue anyway? (You can install Python later and run AISTTStudio.exe directly.)',
      mbConfirmation, MB_YESNO) = IDNO then begin
      Result := False;
      Exit;
    end;
  end;
  Result := True;
end;
