[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot
Set-Location -LiteralPath $ProjectDir

$Python = $null
$PythonPrefix = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.12 -c "import sys; raise SystemExit(sys.version_info < (3, 12))"
    if ($LASTEXITCODE -eq 0) { $Python = "py"; $PythonPrefix = @("-3.12") }
}
if (-not $Python -and (Get-Command python -ErrorAction SilentlyContinue)) {
    & python -c "import sys; raise SystemExit(sys.version_info < (3, 12))"
    if ($LASTEXITCODE -eq 0) { $Python = "python" }
}
if (-not $Python) {
    throw "Python 3.12+ was not found. Install Python, including the py launcher, and retry."
}

$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Creating .venv with Python 3.12..."
    & $Python @PythonPrefix -m venv (Join-Path $ProjectDir ".venv")
}
& $VenvPython -m pip install -e ".[dev]"
$ConfigPath = & $VenvPython (Join-Path $ProjectDir "scripts\platform_info.py") --create-config
$OutputPath = & $VenvPython (Join-Path $ProjectDir "scripts\platform_info.py") --value output
& $VenvPython -m pytest
& $VenvPython -m ruff check .
& $VenvPython (Join-Path $ProjectDir "scripts\offline_validate.py")
Write-Host "Setup complete."
Write-Host "Config: $ConfigPath"
Write-Host "Output: $OutputPath"
Write-Host "Resolve Studio must be open for live validation; no preferences were changed."
