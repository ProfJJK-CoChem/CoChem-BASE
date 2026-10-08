#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

case "${1:-}" in
    --help)
        [[ $# -eq 1 ]] || { echo "Use --help or --check without additional arguments." >&2; exit 2; }
        echo "Usage: Launch_CoChem_Mac_Linux.sh [--check | --help]"
        echo "--check reads the real Python bootstrap help without installing or launching."
        exit 0
        ;;
    --check)
        [[ $# -eq 1 ]] || { echo "Use --check without additional arguments." >&2; exit 2; }
        python3 "$SCRIPT_DIR/scripts/bootstrap_environment.py" --help
        echo "Launcher prerequisites verified; GUI dependencies and chemistry were not tested."
        exit 0
        ;;
    "") ;;
    *) echo "Invalid launcher arguments. Use --help for supported options." >&2; exit 2 ;;
esac

echo "========================================================"
echo " Launching CoChem Graphical Interface (No-Code Mode)"
echo "========================================================"
echo "Please wait while the environment starts..."
echo "If you are on GitHub Codespaces, VS Code will prompt you"
echo "to 'Open in Browser' once the server starts on port 8866."
echo ""

# The bootstrap resolves its own repository path, including when invoked elsewhere.
if [[ "${CODESPACES:-false}" == "true" ]]; then
    exec python3 "$SCRIPT_DIR/scripts/bootstrap_environment.py" --launch --no-browser
else
    exec python3 "$SCRIPT_DIR/scripts/bootstrap_environment.py" --launch
fi
