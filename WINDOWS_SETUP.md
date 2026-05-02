# Windows Installer — Build & Troubleshooting

This document covers building `Resume Tailor.exe` from source and diagnosing launch failures on Windows.

## Tool

[Inno Setup](https://jrsoftware.org/isinfo.php) — free, no account required.

## Installer script

The installer is defined in `build_exe.iss` in the repo root. Inno Setup compiles it into `Resume Tailor.exe`.

### What the installer does

1. Checks that Ollama is installed (`where ollama`; falls back to checking `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` directly in case Ollama is installed but not yet on PATH) — shows an error dialog and aborts if missing
2. Checks that Python is installed (`where python`) — shows an error dialog and aborts if missing
3. Copies `src\` files to `%LOCALAPPDATA%\Resume Tailor\src\`
4. Copies `Resume Tailor.vbs` and `AppIcon.ico` to `%LOCALAPPDATA%\Resume Tailor\`
5. Creates a Desktop shortcut that explicitly calls `wscript.exe` with `Resume Tailor.vbs` as the argument (see [Why wscript.exe is explicit](#why-wscriptexe-is-explicit))

### What the launcher (`Resume Tailor.vbs`) does on each launch

1. **Finds the Ollama binary** — checks PATH first, then `%LOCALAPPDATA%\Programs\Ollama\ollama.exe`
2. **Confirms the Ollama service is running** — runs `ollama list`; if it fails, attempts to auto-start Ollama and retries after 4 seconds; shows a dialog if still unresponsive
3. **Checks Python** — runs `where python`
4. **Installs dependencies** — runs `pip install -q -r src\requirements.txt` in a visible window titled "Resume Tailor -- Installing dependencies…"; shows an error dialog if pip fails
5. **Launches the app** — runs `python src\resume.py` with output redirected to `launch_error.log`; if Python exits non-zero, shows the log contents in an error dialog

## Build steps

1. Install Inno Setup
2. Open `build_exe.iss` in Inno Setup
3. Click **Build → Compile** — produces `Resume Tailor.exe` in the repo root
4. `Resume Tailor.exe` is a build artifact; do not commit it

## Distribution

Share `Resume Tailor.exe` — the Windows equivalent of `Resume Tailor.dmg` on Mac.

---

## Troubleshooting

### Shortcut does nothing after install

The Desktop shortcut explicitly calls `wscript.exe` to run `Resume Tailor.vbs`. If clicking it still does nothing, run the VBScript directly from a terminal to see any errors:

```powershell
cscript "$env:LOCALAPPDATA\Resume Tailor\Resume Tailor.vbs"
```

### "Ollama is not installed" even though Ollama is installed

Ollama installs to `%LOCALAPPDATA%\Programs\Ollama\` and adds itself to the **user** PATH. If the PATH update has not propagated to the current session (common immediately after installation), the launcher falls back to checking the known install path directly. If both checks fail, reinstalling Ollama or restarting the machine resolves it.

### "Ollama is installed but not running"

Ollama must be running as a background service before the app can query it. Open Ollama from the Start menu or system tray, wait a few seconds, then try again. If the service starts successfully the next launch will skip this step automatically.

### App fails to start — checking the error log

If Python crashes on startup, the error is written to:

```
%LOCALAPPDATA%\Resume Tailor\launch_error.log
```

Open that file to see the full Python traceback. Common causes:
- A Python dependency failed to install (check pip output)
- `ollama.list()` failed because the Ollama service stopped after the launcher's check
- pywebview failed to initialise (usually a missing WebView2 runtime — install [Microsoft Edge WebView2](https://developer.microsoft.com/en-us/microsoft-edge/webview2/))

### "Installing dependencies" window appears but the app never opens

The pip install succeeded but Python exited with an error. Check `launch_error.log` as described above.

### Testing the launcher without reinstalling

To test a locally edited `Resume Tailor.vbs` without rebuilding the installer:

```powershell
Copy-Item "f:\Code\local-resume-tailor\Resume Tailor.vbs" "$env:LOCALAPPDATA\Resume Tailor\Resume Tailor.vbs" -Force
```

Then click the Desktop shortcut or run `cscript "$env:LOCALAPPDATA\Resume Tailor\Resume Tailor.vbs"`.

---

## Why wscript.exe is explicit

The shortcut uses `{sys}\wscript.exe` as the executable with the `.vbs` path as a parameter, rather than pointing directly to the `.vbs` file. A shortcut that targets a `.vbs` file directly depends on the Windows file association for `.vbs` → `wscript.exe`. On some systems this association is blocked by policy or registry state, causing the shortcut to silently do nothing. Calling `wscript.exe` directly is immune to this — it mirrors the behaviour of running `cscript Resume Tailor.vbs` from a terminal.
