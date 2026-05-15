#!/usr/bin/env bash
# Install Inky Dash as a systemd service on Linux.
#
# Run AFTER scripts/install.sh so the venv, deps, and settings.json exist.
# The unit runs ``python -m app`` from this repo, as the user you specify
# (defaults to the invoking user — i.e. the one who owns the venv).
#
# Usage (from anywhere):
#   ./scripts/install-service.sh              # install + enable + start
#   ./scripts/install-service.sh --uninstall  # stop + remove the unit file
#
# Set ``INKY_DASH_SERVICE_USER`` to override the user the service runs as.

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

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

SERVICE_NAME="inky-dash"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

# --- Platform guard -------------------------------------------------

if [ "$(uname -s)" != "Linux" ]; then
  fail "This script is Linux-only (systemd). Detected: $(uname -s)."
fi
if ! command -v systemctl >/dev/null 2>&1; then
  fail "systemctl not found — this script needs systemd.
       Alpine/OpenRC, runit, etc. aren't supported here."
fi

# --- sudo helper ----------------------------------------------------
# Use sudo only when actually needed (writing /etc, systemctl). If we're
# already root, run the commands directly. We prompt for the password
# once up-front so the rest of the script doesn't pause mid-stream.

if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
else
  if ! command -v sudo >/dev/null 2>&1; then
    fail "sudo not found and not running as root — can't write $UNIT_PATH."
  fi
  SUDO="sudo"
  step "Requesting sudo (needed to write $UNIT_PATH and call systemctl)"
  sudo -v || fail "sudo authentication failed"
  ok "sudo cached"
fi

# --- --uninstall ----------------------------------------------------

if [ "${1:-}" = "--uninstall" ]; then
  step "Uninstalling ${SERVICE_NAME}.service"
  if $SUDO systemctl is-enabled "$SERVICE_NAME" >/dev/null 2>&1 \
       || $SUDO systemctl is-active "$SERVICE_NAME" >/dev/null 2>&1; then
    $SUDO systemctl disable --now "$SERVICE_NAME" || true
    ok "disabled + stopped"
  else
    ok "not running"
  fi
  if [ -f "$UNIT_PATH" ]; then
    $SUDO rm -f "$UNIT_PATH"
    $SUDO systemctl daemon-reload
    ok "removed $UNIT_PATH"
  else
    ok "no unit file at $UNIT_PATH"
  fi
  echo
  echo "${GREEN}${BOLD}Uninstalled.${RESET} ${DIM}Repo + data/ are untouched.${RESET}"
  exit 0
fi

# --- Pre-flight: venv must exist ------------------------------------

step "Checking the repo is ready"
if [ ! -x "$ROOT/.venv/bin/python" ]; then
  fail "No .venv at $ROOT/.venv. Run ./scripts/install.sh first."
fi
ok "venv at $ROOT/.venv"

# --- Pick the service user ------------------------------------------
#
# The unit needs to run as the user who owns the venv (so Playwright's
# browser cache, the data dir, etc. all line up). Default precedence:
#   INKY_DASH_SERVICE_USER env var > SUDO_USER (if sudo'd) > $USER.

step "Choosing the user the service will run as"
if [ -n "${INKY_DASH_SERVICE_USER:-}" ]; then
  SERVICE_USER="$INKY_DASH_SERVICE_USER"
elif [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
  SERVICE_USER="$SUDO_USER"
else
  SERVICE_USER="${USER:-$(id -un)}"
fi

if [ "$SERVICE_USER" = "root" ]; then
  warn "service would run as root — this is rarely what you want."
  warn "Set INKY_DASH_SERVICE_USER=<youruser> and rerun, or continue at your own risk."
fi
if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
  fail "User '$SERVICE_USER' doesn't exist on this system."
fi
SERVICE_GROUP="$(id -gn "$SERVICE_USER")"
ok "user=$SERVICE_USER group=$SERVICE_GROUP"

# Sanity: that user must be able to read the repo + write to data/.
if ! $SUDO -u "$SERVICE_USER" test -r "$ROOT/.venv/bin/python"; then
  fail "$SERVICE_USER can't read $ROOT/.venv — check permissions."
fi
if ! $SUDO -u "$SERVICE_USER" test -w "$ROOT/data" 2>/dev/null; then
  warn "$SERVICE_USER may not be able to write $ROOT/data — pushes/history will fail."
fi

# --- Generate + install the unit file -------------------------------

step "Writing $UNIT_PATH"

# Build the unit body. We point at the venv python directly (no shell
# wrapper) so systemd sees the actual process. WorkingDirectory is the
# repo root so Path(__file__).parent.parent resolves the same as it
# does under run.sh.
UNIT_BODY=$(cat <<EOF
[Unit]
Description=Inky Dash — e-ink dashboard renderer
Documentation=https://github.com/dmellok/inky-dash
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${ROOT}
ExecStart=${ROOT}/.venv/bin/python -m app
Restart=on-failure
RestartSec=5
# Give the renderer + scheduler time to shut down cleanly.
TimeoutStopSec=15
# Send stdout/stderr to the journal — view with: journalctl -u ${SERVICE_NAME} -f
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
)

# Write via tee so we only need one sudo invocation for the file itself.
if ! printf '%s\n' "$UNIT_BODY" | $SUDO tee "$UNIT_PATH" >/dev/null; then
  fail "failed to write $UNIT_PATH"
fi
$SUDO chmod 0644 "$UNIT_PATH"
ok "unit installed"

# --- Reload + enable + start ----------------------------------------

step "Reloading systemd + starting the service"
$SUDO systemctl daemon-reload
ok "daemon-reload"

if $SUDO systemctl enable --now "$SERVICE_NAME"; then
  ok "enabled + started"
else
  fail "systemctl enable --now failed — check 'journalctl -u $SERVICE_NAME' for details"
fi

# Brief pause then a status snapshot so the user sees if it crashed
# immediately (most common failure: missing system lib for Chromium).
sleep 1
echo
if $SUDO systemctl is-active --quiet "$SERVICE_NAME"; then
  ok "${GREEN}${BOLD}${SERVICE_NAME} is active${RESET}"
else
  warn "${YELLOW}${BOLD}${SERVICE_NAME} is NOT active${RESET} — recent logs:"
  $SUDO journalctl -u "$SERVICE_NAME" -n 20 --no-pager || true
fi

# --- Done -----------------------------------------------------------

PORT_VALUE="$(tr -d '[:space:]' < "$ROOT/data/core/.port" 2>/dev/null || echo 5555)"

echo
echo "${GREEN}${BOLD}Service installed.${RESET}"
echo
echo "${BOLD}Useful commands${RESET}"
echo "  ${DIM}status:${RESET}   sudo systemctl status $SERVICE_NAME"
echo "  ${DIM}logs:${RESET}     sudo journalctl -u $SERVICE_NAME -f"
echo "  ${DIM}restart:${RESET}  sudo systemctl restart $SERVICE_NAME"
echo "  ${DIM}stop:${RESET}     sudo systemctl stop $SERVICE_NAME"
echo "  ${DIM}uninstall:${RESET} ./scripts/install-service.sh --uninstall"
echo
echo "Open ${BOLD}http://localhost:${PORT_VALUE}${RESET} once the service is healthy."
