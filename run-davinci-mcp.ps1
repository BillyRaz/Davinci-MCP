[CmdletBinding()]
param()
$ProjectDir = $PSScriptRoot
$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Error "Missing $VenvPython. Run setup-davinci-mcp.ps1 first."
    if ($Host.Name -eq "ConsoleHost") { Read-Host "Press Enter to close" }
    exit 1
}
$OutputPath = & $VenvPython (Join-Path $ProjectDir "scripts\platform_info.py") --value output
$LogDir = Join-Path $OutputPath "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogPath = Join-Path $LogDir ("davinci-mcp-{0}.log" -f (Get-Date -Format "yyyyMMddTHHmmssZ"))
Write-Host "Starting DaVinci Resolve MCP"
Write-Host "Server: $(Join-Path $ProjectDir 'server.py')"
Write-Host "Output: $OutputPath"
Write-Host "Log: $LogPath"
try {
    & $VenvPython (Join-Path $ProjectDir "server.py") 2>> $LogPath
    if ($LASTEXITCODE -ne 0) { throw "Server exited with status $LASTEXITCODE" }
} catch {
    $_ | Out-File -Append -FilePath $LogPath
    Write-Error "$_ See $LogPath"
    if ($Host.Name -eq "ConsoleHost") { Read-Host "Press Enter to close" }
    exit 1
}
