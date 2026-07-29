[CmdletBinding()]
param()
$ProjectDir = Split-Path -Parent $PSScriptRoot
$Target = Join-Path $ProjectDir "run-davinci-mcp.ps1"
$ShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Run DaVinci MCP.lnk"
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$Target`""
$Shortcut.WorkingDirectory = $ProjectDir
$Shortcut.Save()
Write-Host "Created: $ShortcutPath"
