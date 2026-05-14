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
# Optionally pre-seed broker config so settings.json lands ready to run:
#   MQTT_HOST=192.168.1.50 COMPANION_BASE_URL=http://192.168.1.10:5555 \
#     ./scripts/install.sh

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

step "Installing Playwright Chromium (~200MB, one-time)"
if python -m playwright install chromium; then
  ok "Chromium ready"
else
  warn "Chromium install reported errors — on Linux you may need system libs:"
  warn "  sudo python -m playwright install-deps chromium"
fi

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

# --- Seed settings.json ---------------------------------------------

step "Seeding data/core/settings.json"
mkdir -p data/core
SETTINGS=data/core/settings.json
if [ -f "$SETTINGS" ]; then
  ok "$SETTINGS already exists — leaving it alone"
else
  cat > "$SETTINGS" <<EOF
{
  "appearance": {"accent": "", "theme": "auto"},
  "base_url": "${COMPANION_BASE_URL:-http://localhost:5555}",
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
echo "     Open ${BOLD}http://localhost:5555${RESET} in a browser."
echo
echo "${DIM}Heads up — this is a hobby project. On first visit, /setup will"
echo "ask you to pick an admin password. The gate is a fence for a home"
echo "LAN, not internet-grade security — run on a private network only.${RESET}"
