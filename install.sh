#!/usr/bin/env bash
# RAPP one-click Copilot Studio deployer — bootstrap.
# Usage:  curl -fsSL https://kody-w.github.io/rapp-oneclick-deploy/install.sh | bash
set -euo pipefail

RAW="https://raw.githubusercontent.com/kody-w/rapp-oneclick-deploy/main"

command -v python3 >/dev/null 2>&1 || { echo "✗ python3 is required (https://www.python.org/downloads/)"; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
echo "↓ Fetching deployer…"
curl -fsSL "$RAW/agent.py" -o "$TMP/agent.py"

# Run with the terminal attached so device-code sign-in + env selection work.
exec python3 "$TMP/agent.py" "$@" < /dev/tty
