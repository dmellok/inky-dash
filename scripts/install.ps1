# Inky Dash install helper for Windows (PowerShell 5.1+).
#
# Sets up:
#   - Python virtualenv at .venv
#   - Python deps (pip install -e ".[dev]")
#   - Playwright + Chromium for the renderer
#   - JS deps + admin bundle (bun preferred, npm fallback)
#   - data\core\settings.json seeded from env vars + sensible defaults
#
# Usage (from the repo root):
#   powershell.exe -ExecutionPolicy Bypass -File scripts\install.ps1
#
# Optionally pre-seed config:
#   $env:MQTT_HOST = "192.168.1.50"
#   $env:COMPANION_BASE_URL = "http://192.168.1.10:5555"
#   $env:INKY_DASH_PORT = "5556"
#   .\scripts\install.ps1
#
# Skip interactive prompts by setting $env:NONINTERACTIVE = "1".

$ErrorActionPreference = "Stop"

function Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  ! $msg" -ForegroundColor Yellow }
function Fail($msg) {
  Write-Host "ERROR: $msg" -ForegroundColor Red
  exit 1
}

# Resolve repo root from this script's location so the user can run it
# from anywhere -- not just the repo root.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

Write-Host "Inky Dash install" -ForegroundColor White
Write-Host "  repo: $Root"

# --- Python (3.11+) -------------------------------------------------

Step "Finding Python 3.11+"
$PyExe = $null
$PyArgs = @()
# Try the Windows launcher with specific versions first; fall back to plain `python`.
$candidates = @(
  @("py", "-3.13"),
  @("py", "-3.12"),
  @("py", "-3.11"),
  @("python", $null),
  @("python3", $null)
)
foreach ($c in $candidates) {
  $cmd = $c[0]
  $arg = $c[1]
  try {
    $cmdInfo = Get-Command $cmd -ErrorAction Stop
  } catch {
    continue
  }
  $callArgs = @()
  if ($arg) { $callArgs += $arg }
  $callArgs += @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")
  try {
    $version = & $cmd @callArgs 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $version) { continue }
    if ([version]$version -ge [version]"3.11") {
      $PyExe = $cmd
      $PyArgs = @()
      if ($arg) { $PyArgs += $arg }
      Ok "$cmd $arg (Python $version)"
      break
    }
  } catch {
    continue
  }
}
if (-not $PyExe) {
  Fail "Python 3.11+ not found. Install from https://python.org or via winget:
       winget install Python.Python.3.13"
}

# --- venv -----------------------------------------------------------

Step "Setting up Python virtualenv at .venv"
if (Test-Path .venv) {
  Ok ".venv already present -- reusing"
} else {
  & $PyExe @PyArgs -m venv .venv
  Ok ".venv created"
}
$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
  Fail ".venv created but .venv\Scripts\python.exe missing -- venv setup failed"
}

# --- Python deps ----------------------------------------------------

Step "Installing Python dependencies (pip install -e `".[dev]`")"
& $VenvPy -m pip install --quiet --upgrade pip
& $VenvPy -m pip install --quiet -e ".[dev]"
Ok "deps installed"

# --- Playwright + Chromium ------------------------------------------

Step "Installing Playwright Chromium (~200MB, one-time)"
& $VenvPy -m playwright install chromium
if ($LASTEXITCODE -eq 0) { Ok "Chromium ready" } else { Warn "Playwright install reported errors -- check the output above" }

# --- JS deps + bundle -----------------------------------------------

Step "Installing JS deps + building the admin bundle"
$bun = Get-Command bun -ErrorAction SilentlyContinue
$npm = Get-Command npm -ErrorAction SilentlyContinue
if ($bun) {
  & bun install
  & bun run build
  Ok "built with bun"
} elseif ($npm) {
  Warn "bun not found, falling back to npm (slower)"
  & npm install --silent
  & npm run --silent build
  Ok "built with npm"
} else {
  Fail "Neither bun nor npm found.
       Install bun:   powershell -c `"irm bun.sh/install.ps1 | iex`"
       Or install Node from https://nodejs.org for npm."
}

# --- Pick listen port -----------------------------------------------

Step "Choosing the HTTP port"
$dataDir = Join-Path $Root "data\core"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
$portFile = Join-Path $dataDir ".port"

# Precedence: env var > existing sidecar > prompt (default 5555).
$portDefault = $null
if ($env:INKY_DASH_PORT) {
  $portDefault = $env:INKY_DASH_PORT
} elseif (Test-Path $portFile) {
  $portDefault = (Get-Content $portFile -Raw).Trim()
}
if (-not $portDefault) { $portDefault = "5555" }

$portValue = $null
if ($env:INKY_DASH_PORT -or $env:NONINTERACTIVE -eq "1" -or [Console]::IsInputRedirected) {
  $portValue = $portDefault
} else {
  while (-not $portValue) {
    $entered = Read-Host "  Listen on port [$portDefault]"
    if (-not $entered) { $entered = $portDefault }
    $parsed = 0
    if ([int]::TryParse($entered, [ref]$parsed) -and $parsed -ge 1 -and $parsed -le 65535) {
      $portValue = "$parsed"
    } else {
      Warn "must be an integer between 1 and 65535"
    }
  }
}
Set-Content -Path $portFile -Value $portValue -Encoding ascii -NoNewline
Ok "port $portValue (written to $portFile)"

# --- Pick base URL --------------------------------------------------
#
# base_url is what the Pi listener fetches PNGs from + what HA image
# entities point at -- has to be a host the Pi can reach, NOT localhost.

Step "Choosing the companion base URL"
# UDP-socket-to-non-routable trick: kernel picks the interface the
# default route would use, no packet actually sent. Cross-platform.
$lanIp = ""
try {
  $lanIp = & $VenvPy -c @"
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(('10.255.255.255', 1))
    print(s.getsockname()[0])
except OSError:
    pass
finally:
    s.close()
"@ 2>$null
  if ($lanIp) { $lanIp = $lanIp.Trim() }
} catch { $lanIp = "" }

if ($env:COMPANION_BASE_URL) {
  $baseUrl = $env:COMPANION_BASE_URL
  Ok "base URL $baseUrl (from COMPANION_BASE_URL)"
} else {
  if ($lanIp) {
    $baseUrlDefault = "http://${lanIp}:${portValue}"
  } else {
    $baseUrlDefault = "http://localhost:$portValue"
    Warn "couldn't auto-detect LAN IP -- defaulting to localhost"
  }
  if ($env:NONINTERACTIVE -eq "1" -or [Console]::IsInputRedirected) {
    $baseUrl = $baseUrlDefault
  } else {
    $entered = Read-Host "  Base URL the Pi/HA will reach this host on [$baseUrlDefault]"
    if (-not $entered) { $entered = $baseUrlDefault }
    $baseUrl = $entered
  }
  Ok "base URL $baseUrl"
}

# --- Seed settings.json ---------------------------------------------

Step "Seeding data\core\settings.json"
$settingsPath = Join-Path $dataDir "settings.json"
if (Test-Path $settingsPath) {
  Ok "$settingsPath already exists -- leaving it alone"
} else {
  $mqttHost = if ($env:MQTT_HOST) { $env:MQTT_HOST } else { "" }
  $mqttUser = if ($env:MQTT_USERNAME) { $env:MQTT_USERNAME } else { "" }
  $mqttPass = if ($env:MQTT_PASSWORD) { $env:MQTT_PASSWORD } else { "" }
  $mqttPort = if ($env:MQTT_PORT) { $env:MQTT_PORT } else { "1883" }
  $settings = @"
{
  "appearance": {"accent": "", "theme": "auto"},
  "base_url": "$baseUrl",
  "ha": {"enabled": false},
  "mqtt": {
    "client_id": "inky-dash-companion",
    "host": "$mqttHost",
    "password": "$mqttPass",
    "port": $mqttPort,
    "topic_status": "inky/status",
    "topic_update": "inky/update",
    "username": "$mqttUser"
  },
  "panel": {"model": "spectra_6_13_3", "orientation": "landscape", "underscan": 0}
}
"@
  $settings | Out-File -FilePath $settingsPath -Encoding utf8
  Ok "$settingsPath seeded"
}

# --- Done -----------------------------------------------------------

Write-Host ""
Write-Host "Install complete." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. MQTT broker -- Inky Dash pushes to topic inky/update."
Write-Host "     If you don't already run one, install Mosquitto for Windows:"
Write-Host "       https://mosquitto.org/download/"
Write-Host ""
Write-Host "  2. Configure -- edit data\core\settings.json (MQTT host, base URL),"
Write-Host "     or rerun this script with `$env:MQTT_HOST + `$env:COMPANION_BASE_URL set."
Write-Host ""
Write-Host "  3. Pi-side listener -- clone dmellok/inky-dash-listener onto your"
Write-Host "     Pi and point it at the same broker."
Write-Host ""
Write-Host "  4. Run:"
Write-Host "       .\scripts\run.ps1"
Write-Host "     Open http://localhost:$portValue in a browser."
Write-Host ""
Write-Host "Heads up -- this is a hobby project. On first visit, /setup will" -ForegroundColor DarkGray
Write-Host "ask you to pick an admin password. The gate is a fence for a home" -ForegroundColor DarkGray
Write-Host "LAN, not internet-grade security -- run on a private network only." -ForegroundColor DarkGray
