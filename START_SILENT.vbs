' Silent Gesture Control System Launcher
' Double-click this to start with NO CMD window

Dim shell, fso, scriptDir

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the folder where this script lives
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Kill any existing python/flask instances
shell.Run "taskkill /f /im python.exe", 0, False
shell.Run "taskkill /f /im pythonw.exe", 0, False

' Wait a moment
WScript.Sleep 1000

' Start Flask silently (0 = hidden window)
shell.Run "cmd /c cd /d """ & scriptDir & """ && python app.py > flask.log 2>&1", 0, False

' Wait for Flask to initialize
WScript.Sleep 4000

' Open Chrome
shell.Run "chrome.exe http://localhost:5000", 0, False

Set shell = Nothing
Set fso = Nothing
