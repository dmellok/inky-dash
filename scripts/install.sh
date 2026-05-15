#!/usr/bin/env bash
# Inky Dash install helper for macOS + Linux.
#
# Sets up:
#   - Python virtualenv at .venv
#   - Python deps (pip install -e ".[dev]")
#   - Playwright + Chromium for the renderer
#   - JS deps + admin bundle (bun preferred, npm fallback)
#   - data/core/settings.json seeded from env vars + sensible defaults
#
# Usage (from the repo root):
#   ./scripts/install.sh
#
# Optionally pre-seed config so settings.json lands ready to run:
#   MQTT_HOST=192.168.1.50 COMPANION_BASE_URL=http://192.168.1.10:5555 \
#     INKY_DASH_PORT=5556 ./scripts/install.sh
#
# Skip interactive prompts by setting ``NONINTERACTIVE=1``.

set -euo pipefail

# --- Pretty output --------------------------------------------------

if [ -t 1 ]; then
  BOLD=$(tput bold); DIM=$(tput dim); RED=$(tput setaf 1)
  GREEN=$(tput setaf 2); YELLOW=$(tput setaf 3); CYAN=$(tput setaf 6); RESET=$(tput sgr0)
else
  BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; CYAN=""; RESET=""
fi

step()  { echo; echo "${CYAN}${BOLD}→ $*${RESET}"; }
ok()    { echo "  ${GREEN}✓${RESET} $*"; }
warn()  { echo "  ${YELLOW}!${RESET} $*"; }
fail()  { echo "${RED}${BOLD}✗ $*${RESET}" >&2; exit 1; }

# Resolve repo root from this script's location so the user can run it
# from anywhere — not just the repo root.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$ROOT"

echo "${BOLD}Inky Dash install${RESET}"
echo "  repo: $ROOT"

# --- Python (3.11+) --------------------------------------------------

step "Finding Python 3.11+"
PY=""
for candidate in python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    v=$("$candidate" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)
    if [ -n "$v" ]; then
      major=${v%.*}
      minor=${v#*.}
      if [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; then
        PY="$candidate"
        break
      fi
    fi
  fi
done
if [ -z "$PY" ]; then
  fail "Python 3.11+ not found. Install one of:
       macOS:  brew install python@3.13
       Debian: sudo apt install python3.13 python3.13-venv
       Arch:   sudo pacman -S python"
fi
ok "$PY ($("$PY" --version 2>&1))"

# --- venv ------------------------------------------------------------

step "Setting up Python virtualenv at .venv"
if [ -d .venv ]; then
  ok ".venv already present — reusing"
else
  "$PY" -m venv .venv
  ok ".venv created"
fi
# shellcheck disable=SC1091
source .venv/bin/activate
ok "activated"

# --- Python deps ----------------------------------------------------

step "Installing Python dependencies (pip install -e \".[dev]\")"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -e ".[dev]"
ok "deps installed"

# --- Playwright + Chromium ------------------------------------------
#
# Failure modes are messy enough that we capture status here and do the
# remediation (prompting, sudo apt, sidecar persistence) at the END of
# the script. Buried-mid-output warnings get missed.

step "Installing Playwright Chromium (~200MB, one-time)"
PLAYWRIGHT_LOG=$(mktemp)
CHROMIUM_STATUS="ok"  # ok | missing-prebuilt | other-error
if python -m playwright install chromium 2>&1 | tee "$PLAYWRIGHT_LOG"; then
  ok "Chromium ready"
elif grep -qE "does not support chromium|not.*available" "$PLAYWRIGHT_LOG"; then
  CHROMIUM_STATUS="missing-prebuilt"
  warn "no Playwright prebuilt for this OS+arch — will set up system Chromium at the end"
else
  CHROMIUM_STATUS="other-error"
  warn "Chromium install reported errors — see Chromium fallback at the end"
fi
rm -f "$PLAYWRIGHT_LOG"

# --- JS deps + admin bundle -----------------------------------------

step "Installing JS deps + building the admin bundle"
if command -v bun >/dev/null 2>&1; then
  bun install
  bun run build
  ok "built with bun"
elif command -v npm >/dev/null 2>&1; then
  warn "bun not found, falling back to npm (slower)"
  npm install --silent
  npm run --silent build
  ok "built with npm"
else
  fail "Neither bun nor npm found.
       Install bun:   curl -fsSL https://bun.sh/install | bash
       Or install Node from https://nodejs.org for npm."
fi

# --- Pick listen port -----------------------------------------------

step "Choosing the HTTP port"
mkdir -p data/core
PORT_FILE=data/core/.port

# Precedence: env var > existing sidecar > prompt (default 5555).
PORT_DEFAULT="${INKY_DASH_PORT:-}"
if [ -z "$PORT_DEFAULT" ] && [ -f "$PORT_FILE" ]; then
  PORT_DEFAULT=$(tr -d '[:space:]' < "$PORT_FILE" || true)
fi
PORT_DEFAULT="${PORT_DEFAULT:-5555}"

PORT_VALUE=""
if [ -n "${INKY_DASH_PORT:-}" ] || [ "${NONINTERACTIVE:-}" = "1" ] || [ ! -t 0 ]; then
  PORT_VALUE="$PORT_DEFAULT"
else
  while true; do
    read -r -p "  Listen on port [${PORT_DEFAULT}]: " PORT_VALUE
    PORT_VALUE="${PORT_VALUE:-$PORT_DEFAULT}"
    if [[ "$PORT_VALUE" =~ ^[0-9]+$ ]] && [ "$PORT_VALUE" -ge 1 ] && [ "$PORT_VALUE" -le 65535 ]; then
      break
    fi
    warn "must be an integer between 1 and 65535"
  done
fi
echo "$PORT_VALUE" > "$PORT_FILE"
ok "port $PORT_VALUE (written to $PORT_FILE)"

# --- Pick base URL --------------------------------------------------
#
# base_url is what the Pi listener fetches PNGs from + what HA image
# entities point at — it has to be a host the Pi can reach, NOT
# localhost. Detect the host's LAN IP and offer it as the default.

step "Choosing the companion base URL"
# Open a UDP socket to a non-routable destination and read back the
# local socket address — no packet is actually sent, but the kernel
# picks the interface the default route would use. Cross-platform,
# works without parsing ifconfig/ip output.
LAN_IP=$(python -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(('10.255.255.255', 1))
    print(s.getsockname()[0])
except OSError:
    pass
finally:
    s.close()
" 2>/dev/null || true)

if [ -n "${COMPANION_BASE_URL:-}" ]; then
  BASE_URL="$COMPANION_BASE_URL"
  ok "base URL $BASE_URL (from COMPANION_BASE_URL)"
else
  if [ -n "$LAN_IP" ]; then
    BASE_URL_DEFAULT="http://${LAN_IP}:${PORT_VALUE}"
  else
    BASE_URL_DEFAULT="http://localhost:${PORT_VALUE}"
    warn "couldn't auto-detect LAN IP — defaulting to localhost"
  fi
  if [ "${NONINTERACTIVE:-}" = "1" ] || [ ! -t 0 ]; then
    BASE_URL="$BASE_URL_DEFAULT"
  else
    read -r -p "  Base URL the Pi/HA will reach this host on [${BASE_URL_DEFAULT}]: " BASE_URL
    BASE_URL="${BASE_URL:-$BASE_URL_DEFAULT}"
  fi
  ok "base URL $BASE_URL"
fi

# --- Seed settings.json ---------------------------------------------

step "Seeding data/core/settings.json"
SETTINGS=data/core/settings.json
if [ -f "$SETTINGS" ]; then
  ok "$SETTINGS already exists — leaving it alone"
else
  cat > "$SETTINGS" <<EOF
{
  "appearance": {"accent": "", "theme": "auto"},
  "base_url": "${BASE_URL}",
  "ha": {"enabled": false},
  "mqtt": {
    "client_id": "inky-dash-companion",
    "host": "${MQTT_HOST:-}",
    "password": "${MQTT_PASSWORD:-}",
    "port": ${MQTT_PORT:-1883},
    "topic_status": "inky/status",
    "topic_update": "inky/update",
    "username": "${MQTT_USERNAME:-}"
  },
  "panel": {"model": "spectra_6_13_3", "orientation": "landscape", "underscan": 0}
}
EOF
  ok "$SETTINGS seeded"
fi

# --- Chromium fallback (deferred from earlier) ----------------------
#
# Persists to data/core/.chromium so the path survives reboots without
# touching the user's shell rc. The renderer reads this sidecar at
# launch — see app/renderer.py:_chromium_launch_kwargs.

find_system_chromium() {
  for candidate in chromium chromium-browser google-chrome-stable google-chrome; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

if [ "$CHROMIUM_STATUS" = "missing-prebuilt" ]; then
  step "Setting up system Chromium (Playwright has no prebuilt for this OS+arch)"

  SYS_CHROMIUM="$(find_system_chromium || true)"

  if [ -z "$SYS_CHROMIUM" ] && command -v apt-get >/dev/null 2>&1; then
    NONINTERACTIVE_RUN=0
    if [ "${NONINTERACTIVE:-}" = "1" ] || [ ! -t 0 ]; then
      NONINTERACTIVE_RUN=1
    fi
    if [ "$NONINTERACTIVE_RUN" = "1" ]; then
      warn "no system chromium found; non-interactive run, skipping apt install"
    else
      read -r -p "  Install chromium via 'sudo apt install -y chromium'? [Y/n] " yn
      case "${yn:-Y}" in
        [Nn]*)
          warn "skipped — install manually then rerun this script"
          ;;
        *)
          if sudo apt-get update && sudo apt-get install -y chromium 2>/dev/null \
              || sudo apt-get install -y chromium-browser; then
            ok "apt install succeeded"
            SYS_CHROMIUM="$(find_system_chromium || true)"
          else
            warn "apt install failed — install chromium manually then rerun"
          fi
          ;;
      esac
    fi
  fi

  CHROMIUM_FILE=data/core/.chromium
  if [ -n "$SYS_CHROMIUM" ] && [ -x "$SYS_CHROMIUM" ]; then
    mkdir -p data/core
    echo "$SYS_CHROMIUM" > "$CHROMIUM_FILE"
    ok "using $SYS_CHROMIUM (path persisted to $CHROMIUM_FILE)"
  else
    echo
    warn "${BOLD}Chromium still not configured.${RESET} Install it manually:"
    warn "  Debian/Ubuntu:  sudo apt install chromium"
    warn "  Arch:           sudo pacman -S chromium"
    warn "  Fedora:         sudo dnf install chromium"
    warn "Then either rerun this script, or write the binary path to:"
    warn "  $ROOT/data/core/.chromium"
  fi
elif [ "$CHROMIUM_STATUS" = "other-error" ]; then
  step "Chromium install reported errors"
  warn "On Linux you may need system libs:"
  warn "  sudo python -m playwright install-deps chromium"
  warn "Then rerun ./scripts/install.sh."
fi

# --- Done -----------------------------------------------------------

echo
echo "${GREEN}${BOLD}Install complete.${RESET}"
echo
echo "${BOLD}Next steps${RESET}"
echo "  1. ${BOLD}MQTT broker${RESET} — Inky Dash pushes to topic ${DIM}inky/update${RESET}."
echo "     If you don't already run one, install Mosquitto:"
echo "       macOS:  brew install mosquitto && brew services start mosquitto"
echo "       Debian: sudo apt install mosquitto && sudo systemctl enable --now mosquitto"
echo
echo "  2. ${BOLD}Configure${RESET} — edit ${DIM}data/core/settings.json${RESET} (MQTT host, base URL)"
echo "     or rerun this script with env vars: MQTT_HOST=... COMPANION_BASE_URL=..."
echo
echo "  3. ${BOLD}Pi-side listener${RESET} — clone ${DIM}dmellok/inky-dash-listener${RESET} onto"
echo "     your Pi and point it at the same broker."
echo
echo "  4. ${BOLD}Run${RESET}:"
echo "       ./scripts/run.sh"
echo "     Open ${BOLD}http://localhost:${PORT_VALUE}${RESET} in a browser."
echo
echo "${DIM}Heads up — this is a hobby project. On first visit, /setup will"
echo "ask you to pick an admin password. The gate is a fence for a home"
echo "LAN, not internet-grade security — run on a private network only.${RESET}"
