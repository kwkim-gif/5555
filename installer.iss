; AI STT Studio — Inno Setup 스크립트
; Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
; 컴파일: ISCC.exe installer.iss

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
; 설치 중 진행 표시
DisableProgramGroupPage=no
; 언인스톨러 아이콘
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";   Description: "바탕화면에 바로가기 생성"; GroupDescription: "추가 아이콘"; Flags: unchecked
Name: "quicklaunch";   Description: "작업 표시줄 고정"; GroupDescription: "추가 아이콘"; Flags: unchecked

[Files]
; 메인 런처 exe
Source: "{#MyAppDir}\{#MyAppExeName}";  DestDir: "{app}"; Flags: ignoreversion

; 소스 코드
Source: "{#MyAppDir}\app.py";           DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyAppDir}\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion

; 패키지 디렉토리 (재귀)
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
; 시작 메뉴
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\제거"; Filename: "{uninstallexe}"

; 바탕화면
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; 설치 완료 후 실행 옵션
Filename: "{app}\{#MyAppExeName}"; \
  Description: "지금 AI STT Studio 실행"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 언인스톨 시 venv 폴더도 제거
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\error_logs"

[Code]
// 설치 전 Python 3.11+ 존재 여부 확인
function IsPython311Installed(): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('python', '--version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
    and (ResultCode = 0);
end;

function InitializeSetup(): Boolean;
begin
  if not IsPython311Installed() then begin
    if MsgBox(
      'Python 3.11 이상이 필요합니다.'  + #13#10 +
      'https://www.python.org 에서 설치 후 다시 실행하세요.' + #13#10#13#10 +
      '계속 진행하시겠습니까? (나중에 Python 설치 후 AISTTStudio.exe를 실행하면 자동으로 패키지가 설치됩니다)',
      mbConfirmation, MB_YESNO) = IDNO then begin
      Result := False;
      Exit;
    end;
  end;
  Result := True;
end;
