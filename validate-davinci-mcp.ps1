[CmdletBinding()]
param([switch]$Live)
$ProjectDir = $PSScriptRoot
$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Error "Missing $VenvPython. Run setup-davinci-mcp.ps1 first."
    exit 1
}
$Script = if ($Live) { "scripts\live_validate.py" } else { "scripts\offline_validate.py" }
Write-Host $(if ($Live) {
    "Running read-only live validation. Resolve Studio must be open."
} else {
    "Running offline validation. Use -Live only while Resolve Studio is open."
})
Write-Host "Resolve Free external scripting may be unsupported; that is not an MCP defect."
& $VenvPython (Join-Path $ProjectDir $Script)
exit $LASTEXITCODE
