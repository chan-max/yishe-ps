Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c ""cd /d """ & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\dist\server"" && server.exe && pause""", 1, False
Set WshShell = Nothing

