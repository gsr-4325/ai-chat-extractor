' Chat Extractor - Silent Launcher
' This script launches run.py. It automatically detects if initial setup is needed.
' If setup is needed, it shows the window; otherwise, it runs silently.

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Get the directory where this VBScript is located
strScriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
strPythonScript = strScriptDir & "\run.py"

' Check for configuration file (Local or AppData)
strLocalConfig = strScriptDir & "\config.yaml"
strAppData = objShell.ExpandEnvironmentStrings("%APPDATA%")
strAppDataConfig = strAppData & "\ai-chat-extractor\config.yaml"

' Determine window style: 1 (Normal) if config missing, 0 (Hidden) if config exists
intWindowStyle = 0
If Not objFSO.FileExists(strLocalConfig) And Not objFSO.FileExists(strAppDataConfig) Then
    intWindowStyle = 1
End If

' Command to execute: python "path\to\run.py"
' Set the third argument to False to not wait for completion.
objShell.Run "python """ & strPythonScript & """", intWindowStyle, False
