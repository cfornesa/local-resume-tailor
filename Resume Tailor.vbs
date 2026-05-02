Set WShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WShell.CurrentDirectory = ScriptDir

' Phase 1: Find the Ollama binary (PATH first, then known install location)
ollamaExe = ""
If WShell.Run("cmd /c where ollama", 0, True) = 0 Then
    ollamaExe = "ollama"
Else
    Dim fallbackPath
    fallbackPath = WShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
    If FSO.FileExists(fallbackPath) Then
        ollamaExe = Chr(34) & fallbackPath & Chr(34)
    End If
End If

If ollamaExe = "" Then
    MsgBox "Ollama is not installed." & vbNewLine & vbNewLine & "Download it from https://ollama.com, then try again.", vbCritical, "Resume Tailor"
    WScript.Quit
End If

' Phase 2: Confirm the Ollama service is running; auto-start it if not
If WShell.Run(ollamaExe & " list", 0, True) <> 0 Then
    WShell.Run ollamaExe, 0, False
    WScript.Sleep 4000
    If WShell.Run(ollamaExe & " list", 0, True) <> 0 Then
        MsgBox "Ollama is installed but not running." & vbNewLine & vbNewLine & "Please open Ollama from the taskbar and try again.", vbCritical, "Resume Tailor"
        WScript.Quit
    End If
End If

' Check Python
If WShell.Run("cmd /c where python", 0, True) <> 0 Then
    MsgBox "Python is not installed." & vbNewLine & vbNewLine & "Download it from https://python.org, then try again.", vbCritical, "Resume Tailor"
    WScript.Quit
End If

' Install dependencies — visible window with a friendly title
pipResult = WShell.Run("cmd /c title Resume Tailor -- Installing dependencies... & pip install -q -r src\requirements.txt", 1, True)
If pipResult <> 0 Then
    MsgBox "Failed to install dependencies." & vbNewLine & vbNewLine & "Please check your internet connection and try again.", vbCritical, "Resume Tailor"
    WScript.Quit
End If

' Launch the app — capture output to log file so failures are diagnosable
Dim logPath
logPath = ScriptDir & "\launch_error.log"
appResult = WShell.Run("cmd /c python src\resume.py > " & Chr(34) & logPath & Chr(34) & " 2>&1", 0, True)
If appResult <> 0 Then
    Dim errMsg
    errMsg = "Resume Tailor could not start."
    If FSO.FileExists(logPath) Then
        Dim logFile
        Set logFile = FSO.OpenTextFile(logPath, 1)
        If Not logFile.AtEndOfStream Then
            errMsg = errMsg & vbNewLine & vbNewLine & Left(logFile.ReadAll(), 800)
        End If
        logFile.Close
    End If
    MsgBox errMsg, vbCritical, "Resume Tailor"
End If
