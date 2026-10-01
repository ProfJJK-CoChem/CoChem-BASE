#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================================"
echo " Launching CoChem Graphical Interface (No-Code Mode)"
echo "========================================================"
echo "Please wait while the environment starts..."
echo "If you are on GitHub Codespaces, VS Code will prompt you"
echo "to 'Open in Browser' once the server starts on port 8866."
echo ""

exec python3 "$SCRIPT_DIR/scripts/bootstrap_environment.py" --launch
