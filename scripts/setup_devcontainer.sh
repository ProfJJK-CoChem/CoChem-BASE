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

# Ensure login and non-login Codespace/SSH shells automatically resolve binaries
# (xtb, crest, spfit, spcat, cochem-* CLIs) and the managed CoChem ui-env python.
artifact_bin="$artifact_root/bin"
ui_env_bin="$artifact_root/ui-env/bin"
mkdir -p -- "$artifact_bin"
profile_snippet="$(cat <<EOF
# CoChem-BASE managed Python & chemistry binaries (cochem-ui-env)
if [ -d "$ui_env_bin" ]; then
  case ":\$PATH:" in
    *":$ui_env_bin:"*) ;;
    *) export PATH="$ui_env_bin:\$PATH" ;;
  esac
fi
if [ -d "$artifact_bin" ]; then
  case ":\$PATH:" in
    *":$artifact_bin:"*) ;;
    *) export PATH="$artifact_bin:\$PATH" ;;
  esac
fi
if [ -d "$artifact_root/free-engines/xtb/xtb-dist/share/xtb" ] && [ -z "\${XTBPATH:-}" ]; then
  export XTBPATH="$artifact_root/free-engines/xtb/xtb-dist/share/xtb"
fi
EOF
)"
printf '%s\n' "$profile_snippet" | sudo tee /etc/profile.d/cochem-ui-env.sh >/dev/null
sudo chmod 0644 /etc/profile.d/cochem-ui-env.sh
for rc_file in /home/vscode/.bashrc "${HOME}/.bashrc"; do
  rc_dir="$(dirname "$rc_file")"
  if [ -d "$rc_dir" ] && [ -w "$rc_dir" ] && ! grep -q "cochem-ui-env" "$rc_file" 2>/dev/null; then
    printf '\n%s\n' "$profile_snippet" >> "$rc_file"
  fi
done
export PATH="$artifact_bin:$ui_env_bin:$PATH"

# PySide/VTK wheels need these system libraries even for an offscreen dashboard,
# and gcc/make compile pinned JPL calpgm (spfit/spcat) for rotational spectroscopy.
sudo rm -f /etc/apt/sources.list.d/yarn*.list
sudo --preserve-env=http_proxy,https_proxy,no_proxy,HTTP_PROXY,HTTPS_PROXY,NO_PROXY apt-get update
sudo --preserve-env=http_proxy,https_proxy,no_proxy,HTTP_PROXY,HTTPS_PROXY,NO_PROXY apt-get install --no-install-recommends --yes \
  libegl1 libopengl0 libgl1 libdbus-1-3 libxkbcommon-x11-0 libxcb-cursor0 gcc make
# Every student gets the default ecosystem through BASE, without a terminal.
# Optional provider failures are retained for the GUI's Retry setup control.
export COCHEM_STUDENT_AUTO_SETUP="${COCHEM_STUDENT_AUTO_SETUP:-true}"
export COCHEM_MODULES="${COCHEM_MODULES:-topos torq}"
python3 scripts/hosted_dashboard.py setup --min-disk-space-gb 1

# Expose verified open-source binaries (xtb, crest) on Codespace PATH.
for candidate in \
  "$artifact_root/free-engines/xtb/xtb-dist/bin/xtb" \
  "$artifact_root/free-engines/native/bin/xtb" \
  "$artifact_root/free/xtb/bin/xtb"; do
  if [ -x "$candidate" ]; then
    ln -sf "$candidate" "$artifact_bin/xtb"
    break
  fi
done
for candidate in \
  "$artifact_root/free-engines/crest/crest/crest" \
  "$artifact_root/free-engines/native/bin/crest" \
  "$artifact_root/free/crest/crest"; do
  if [ -x "$candidate" ]; then
    ln -sf "$candidate" "$artifact_bin/crest"
    break
  fi
done

# Compile SHA-256-verified pinned JPL calpgm spfit and spcat into artifact_bin (fail-soft if offline).
if [ ! -x "$artifact_bin/spcat" ] || [ ! -x "$artifact_bin/spfit" ]; then
  (
    set -euo pipefail
    CALPGM_SHA="f5af2ff0f1acb1eb11ecffe7ef3b55d457801f7b"
    CALPGM_SRC_DIGEST="479840d1bd19dc2e45612e49a950aee3b72256ef6748d80117c856ab4084c361"
    calpgm_dir="$artifact_root/scratch/calpgm-build"
    rm -rf -- "$calpgm_dir"
    mkdir -p -- "$calpgm_dir"
    git -C "$calpgm_dir" init -q
    git -C "$calpgm_dir" fetch -q --depth 1 https://github.com/laserkelvin/Pickett.git "$CALPGM_SHA"
    git -C "$calpgm_dir" checkout -q --detach FETCH_HEAD
    test "$(git -C "$calpgm_dir" rev-parse HEAD)" = "$CALPGM_SHA"
    python3 - "$calpgm_dir" "$CALPGM_SRC_DIGEST" <<'PY'
import hashlib, pathlib, sys
root = pathlib.Path(sys.argv[1])
expected = sys.argv[2]
c_files = ['calcat.c', 'sortsub.c', 'spinv.c', 'spinit.c', 'ulib.c', 'cnjj.c', 'slibgcc.c', 'catutil.c', 'lsqfit.c', 'dblas.c']
h = hashlib.sha256()
for name in c_files:
    h.update(f"{name}:{hashlib.sha256((root / name).read_bytes()).hexdigest()}\n".encode("ascii"))
actual = h.hexdigest()
if actual != expected:
    raise RuntimeError(f"calpgm C source digest mismatch: expected {expected}, got {actual}")
PY
    make -C "$calpgm_dir" spcat spfit
    install -m 0755 "$calpgm_dir/spcat" "$artifact_bin/spcat"
    install -m 0755 "$calpgm_dir/spfit" "$artifact_bin/spfit"
    rm -rf -- "$calpgm_dir"
  ) || echo "Warning: JPL calpgm (spfit/spcat) build skipped; continuing setup." >&2
fi

# Provision CHEM 490 research modules and PySCF in Codespace ui-env (never modifying CoChem-BASE pyproject.toml or cochem_calc_silo).
ui_python="$ui_env_bin/python"
if [ -x "$ui_python" ]; then
  "$ui_python" -m pip install --no-input --quiet "pyscf==2.14.0" "geometric==1.1.1" \
    || echo "Warning: PySCF/geomeTRIC install into ui-env skipped." >&2
  "$ui_python" -m pip install --no-input --quiet \
    "git+https://github.com/ProfJJK-CoChem/CoChem-BENCH.git@cb874d8f20723c70b26b805329cb873ebe1c463f" \
    "git+https://github.com/ProfJJK-CoChem/CoChem-SCRIBE.git@85216dd12c998c1f879b6bb73ab74a44fc98f4bc" \
    || echo "Warning: CoChem-BENCH/SCRIBE install into ui-env skipped." >&2
  "$ui_python" -m pip install --no-input --quiet "jax[cpu]" \
    "git+https://github.com/ProfJJK-CoChem/CoChem-SpycFit.git@aebe6fd8d5939ed617dad72e1392230e3979faf9" \
    || echo "Warning: CoChem-SpycFit (CPU-only) install into ui-env skipped." >&2
fi

# Install CoChem-GEOM into an isolated venv to avoid namespace collision with BASE's internal src/cochem_geom/.
geom_env="$artifact_root/Modules/geom-env"
if [ ! -x "$geom_env/bin/cochem-geom" ]; then
  (
    set -euo pipefail
    python3 -m venv "$geom_env"
    "$geom_env/bin/python" -m pip install --no-input --quiet --upgrade pip
    "$geom_env/bin/python" -m pip install --no-input --quiet \
      "git+https://github.com/ProfJJK-CoChem/CoChem-GEOM.git@ae8f1e7d56a4030e377d36ca7c9516cd0da16851"
  ) || echo "Warning: isolated CoChem-GEOM env install skipped." >&2
fi

# Expose CHEM 490 CLI wrappers and symlinks on Codespace PATH ($artifact_bin).
[ -x "$ui_env_bin/cochem-bench" ] && ln -sf "$ui_env_bin/cochem-bench" "$artifact_bin/cochem-bench"
[ -x "$ui_env_bin/cochem-scribe" ] && ln -sf "$ui_env_bin/cochem-scribe" "$artifact_bin/cochem-scribe"
[ -x "$geom_env/bin/cochem-geom" ] && ln -sf "$geom_env/bin/cochem-geom" "$artifact_bin/cochem-geom"
if [ -x "$ui_python" ]; then
  cat > "$artifact_bin/cochem-spycfit" <<EOF
#!/usr/bin/env bash
exec "$ui_python" -m cochem_spycfit "\$@"
EOF
  chmod 0755 "$artifact_bin/cochem-spycfit"
fi

topos_cli="$(find "$artifact_root/Modules/topos" -maxdepth 4 -type f -path '*/bin/cochem-topos' 2>/dev/null | head -n 1 || true)"
if [ -n "$topos_cli" ] && [ -x "$topos_cli" ]; then
  ln -sf "$topos_cli" "$artifact_bin/cochem-topos"
  ln -sf "$topos_cli" "$artifact_bin/topos"
fi
torq_cli="$(find "$artifact_root/Modules/torq" -maxdepth 4 -type f -path '*/bin/cochem-torq' 2>/dev/null | head -n 1 || true)"
if [ -n "$torq_cli" ] && [ -x "$torq_cli" ]; then
  ln -sf "$torq_cli" "$artifact_bin/cochem-torq"
fi

python3 scripts/hosted_dashboard.py start --ensure-setup
