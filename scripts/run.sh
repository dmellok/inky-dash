#!/usr/bin/env bash
# Inky Dash launcher. Activates the venv and runs ``python -m app``.
# Run install.sh first to set up the venv.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$ROOT"

if [ ! -d .venv ]; then
  echo "No .venv found. Run ./scripts/install.sh first." >&2
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate
exec python -m app "$@"
