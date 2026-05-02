[Setup]
AppName=Resume Tailor
AppVersion=1.0
AppPublisher=Christopher Fornesa
DefaultDirName={localappdata}\Resume Tailor
DisableProgramGroupPage=yes
OutputBaseFilename=Resume Tailor
SetupIconFile=AppIcon.ico
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern

[Files]
Source: "src\resume.py"; DestDir: "{app}\src"
Source: "src\resume_core.py"; DestDir: "{app}\src"
Source: "src\requirements.txt"; DestDir: "{app}\src"
Source: "src\image.png"; DestDir: "{app}\src"
Source: "Resume Tailor.vbs"; DestDir: "{app}"
Source: "AppIcon.ico"; DestDir: "{app}"

[Icons]
Name: "{userdesktop}\Resume Tailor"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\Resume Tailor.vbs"""; WorkingDir: "{app}"; IconFilename: "{app}\AppIcon.ico"

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  if not Exec('cmd.exe', '/c where ollama', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
  begin
    if not FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe')) then
    begin
      MsgBox('Ollama is not installed.' + #13#10 + #13#10 + 'Download it from https://ollama.com, then run this installer again.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;
  if not Exec('cmd.exe', '/c where python', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
  begin
    MsgBox('Python is not installed.' + #13#10 + #13#10 + 'Download it from https://python.org, then run this installer again.', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  Result := True;
end;
