' Chat Extractor - Silent Launcher
' This script launches run.py without showing a command prompt window.
' Useful for mapping to a desktop shortcut with a hotkey.

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Get the directory where this VBScript is located
strScriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
strPythonScript = strScriptDir & "\run.py"

' Command to execute: python "path\to\run.py"
' Using 0 as the second argument hides the window entirely.
' Set the third argument to False to not wait for completion.
objShell.Run "python """ & strPythonScript & """", 0, False
