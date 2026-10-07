#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

exec "$SCRIPT_DIR/Launch_CoChem_Mac_Linux.sh" "$@"
