Set WShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WShell.CurrentDirectory = ScriptDir

ollamaCheck = WShell.Run("cmd /c where ollama", 0, True)
If ollamaCheck <> 0 Then
    MsgBox "Ollama is not installed." & vbNewLine & vbNewLine & "Download it from https://ollama.com, then try again.", vbCritical, "Resume Tailor"
    WScript.Quit
End If

pythonCheck = WShell.Run("cmd /c where python", 0, True)
If pythonCheck <> 0 Then
    MsgBox "Python is not installed." & vbNewLine & vbNewLine & "Download it from https://python.org, then try again.", vbCritical, "Resume Tailor"
    WScript.Quit
End If

WShell.Run "cmd /c pip install -q -r src\requirements.txt", 0, True

WShell.Run "python src\resume.py", 0, False
