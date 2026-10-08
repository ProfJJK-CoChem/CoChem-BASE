#!/usr/bin/env bash
# Prepare the Codespaces interface without local calculation authority.
set -euo pipefail

calculation_environment="${COCHEM_CALCULATION_ENVIRONMENT:-github-actions}"
licensed_engines="${COCHEM_INSTALL_LICENSED_ENGINES:-none}"
case "$calculation_environment" in
  github-actions|local) ;;
  *) echo 'COCHEM_CALCULATION_ENVIRONMENT must be github-actions or local.' >&2; exit 2 ;;
esac
case "$licensed_engines" in
  none|false|0|'') ;;
  orca|cfour|both)
    if [ "$calculation_environment" != local ]; then
      echo 'Local licensed-engine installation requires COCHEM_CALCULATION_ENVIRONMENT=local; use private Actions staging for the Actions interface.' >&2
      exit 2
    fi
    ;;
  *) echo 'COCHEM_INSTALL_LICENSED_ENGINES must be none, orca, cfour, or both.' >&2; exit 2 ;;
esac

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$repo_root"
artifact_root="$(python3 -c 'import os; from pathlib import Path; print(Path(os.environ.get("COCHEM_ARTIFACT_DIR", "~/CoChem_Artifacts")).expanduser().resolve())')"
case "$artifact_root" in
  /|"$repo_root"|"$repo_root"/*)
    echo 'COCHEM_ARTIFACT_DIR must be outside the source checkout.' >&2
    exit 2
    ;;
esac

# PySide/VTK wheels need these system libraries even for an offscreen dashboard.
# The stock Python devcontainer does not include them.
sudo --preserve-env=http_proxy,https_proxy,no_proxy,HTTP_PROXY,HTTPS_PROXY,NO_PROXY apt-get update
sudo --preserve-env=http_proxy,https_proxy,no_proxy,HTTP_PROXY,HTTPS_PROXY,NO_PROXY apt-get install --no-install-recommends --yes \
  libegl1 libopengl0 libgl1 libdbus-1-3 libxkbcommon-x11-0 libxcb-cursor0
sudo mkdir -p -- "$artifact_root"
sudo chown "$(id -u):$(id -g)" "$artifact_root"
case "$licensed_engines" in
  none|false|0|'') ;;
  orca|cfour|both)
    python3 scripts/setup_licensed_engines.py --engine "$licensed_engines" \
      --artifacts "$artifact_root" --no-refresh-stage0
    ;;
esac
python3 scripts/hosted_dashboard.py setup --calculation-environment "$calculation_environment" --min-disk-space-gb 1
