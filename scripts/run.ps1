# Inky Dash launcher. Activates the venv and runs python -m app.
# Run install.ps1 first to set up the venv.
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
  Write-Host "No .venv found. Run scripts\install.ps1 first." -ForegroundColor Red
  exit 1
}
& $VenvPy -m app @args
