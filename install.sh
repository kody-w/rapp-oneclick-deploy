#!/usr/bin/env bash
# RAPP one-click Copilot Studio deployer — bootstrap.
#   curl -fsSL https://kody-w.github.io/rapp-oneclick-deploy/install.sh | bash
#   ... | bash -s -- --source https://raw.githubusercontent.com/<user>/<repo>/main/agents/x.py
set -euo pipefail

RAW="https://raw.githubusercontent.com/kody-w/rapp-oneclick-deploy/main"
command -v python3 >/dev/null 2>&1 || { echo "✗ python3 is required (https://www.python.org/downloads/)"; exit 1; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/pipeline"
echo "↓ Fetching deployer…"
for f in agent.py convert.py brainstem_llm.py; do
  curl -fsSL "$RAW/$f" -o "$TMP/$f"
done
# pipeline asset for --source conversion (best-effort; only needed for convert path)
curl -fsSL "$RAW/pipeline/skeleton.zip" -o "$TMP/pipeline/skeleton.zip" 2>/dev/null || true

exec python3 "$TMP/agent.py" "$@" < /dev/tty
