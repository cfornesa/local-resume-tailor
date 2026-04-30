# Windows Installer — Setup Notes

This document covers the steps to build `Resume Tailor Setup.exe` using Inno Setup when working on a Windows machine.

## Tool

[Inno Setup](https://jrsoftware.org/isinfo.php) — free, no account required.

## What to create

A file named `setup.iss` in the repo root. Inno Setup compiles it into `Resume Tailor Setup.exe`.

## What the installer should do

1. Check that Ollama is installed (`where ollama`) — show an error dialog and abort if missing
2. Check that Python is installed (`where python`) — show an error dialog and abort if missing
3. Copy `src\` files to `%LOCALAPPDATA%\Resume Tailor\src\`
4. Copy `Resume Tailor.vbs` to `%LOCALAPPDATA%\Resume Tailor\`
5. Create a Desktop shortcut pointing to `Resume Tailor.vbs`
6. Register an uninstaller so the app appears in Add/Remove Programs

## Rough `setup.iss` structure

```ini
[Setup]
AppName=Resume Tailor
AppVersion=1.0
DefaultDirName={localappdata}\Resume Tailor
DisableProgramGroupPage=yes
OutputBaseFilename=Resume Tailor Setup
Compression=lzma
SolidCompression=yes

[Files]
Source: "src\*"; DestDir: "{app}\src"; Flags: recursesubdirs
Source: "Resume Tailor.vbs"; DestDir: "{app}"

[Icons]
Name: "{userdesktop}\Resume Tailor"; Filename: "{app}\Resume Tailor.vbs"

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  // Check Ollama
  if not Exec('cmd.exe', '/c where ollama', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
  begin
    MsgBox('Ollama is not installed.' + #13#10 + #13#10 + 'Download it from https://ollama.com, then run this installer again.', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  // Check Python
  if not Exec('cmd.exe', '/c where python', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
  begin
    MsgBox('Python is not installed.' + #13#10 + #13#10 + 'Download it from https://python.org, then run this installer again.', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  Result := True;
end;
```

## Build step

1. Install Inno Setup
2. Open `setup.iss` in the Inno Setup compiler
3. Click **Build** → produces `Resume Tailor Setup.exe` in the repo root
4. Add `Resume Tailor Setup.exe` to `.gitignore` (build artifact)

## Distribution

Share `Resume Tailor Setup.exe` — the Windows equivalent of `Resume Tailor.dmg` on Mac.
