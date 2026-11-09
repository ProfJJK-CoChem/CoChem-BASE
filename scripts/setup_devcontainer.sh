#!/usr/bin/env bash
# Prepare the Linux dashboard image without requiring licensed engines.
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$repo_root"
artifact_root="$(python3 -c 'import os; from pathlib import Path; print(Path(os.environ.get("COCHEM_ARTIFACT_DIR", "~/CoChem_Artifacts")).expanduser().resolve())')"
case "$artifact_root" in
  /|"$repo_root"|"$repo_root"/*)
    echo 'COCHEM_ARTIFACT_DIR must be outside the source checkout.' >&2
    exit 2
    ;;
esac

sudo mkdir -p -- "$artifact_root"
sudo chown "$(id -u):$(id -g)" "$artifact_root"

# PySide/VTK wheels need these system libraries even for an offscreen dashboard.
# The stock Python devcontainer does not include them.
sudo rm -f /etc/apt/sources.list.d/yarn*.list
sudo --preserve-env=http_proxy,https_proxy,no_proxy,HTTP_PROXY,HTTPS_PROXY,NO_PROXY apt-get update
sudo --preserve-env=http_proxy,https_proxy,no_proxy,HTTP_PROXY,HTTPS_PROXY,NO_PROXY apt-get install --no-install-recommends --yes \
  libegl1 libopengl0 libgl1 libdbus-1-3 libxkbcommon-x11-0 libxcb-cursor0
# Every student gets the default ecosystem through BASE, without a terminal.
# Optional provider failures are retained for the GUI's Retry setup control.
export COCHEM_STUDENT_AUTO_SETUP="${COCHEM_STUDENT_AUTO_SETUP:-true}"
export COCHEM_MODULES="${COCHEM_MODULES:-topos torq}"
python3 scripts/hosted_dashboard.py setup --min-disk-space-gb 1
python3 scripts/hosted_dashboard.py start --ensure-setup
