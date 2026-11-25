#!/usr/bin/env bash
# Optional add-on installer for CoChem-SPYFY (NOT installed by default in Codespaces).
# Installs CPU-only JAX and pinned CoChem-SPYFY into $COCHEM_ARTIFACT_DIR/ui-env
# and exposes $COCHEM_ARTIFACT_DIR/bin/cochem-spyfy on PATH.
set -euo pipefail

SPYFY_REPO="https://github.com/ProfJJK-CoChem/CoChem-SPYFY.git"
SPYFY_REV="4372dbf448471d8bc7b51feb0bbf7d7a53f400d5"

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
artifact_root="$(python3 -c 'import os; from pathlib import Path; print(Path(os.environ.get("COCHEM_ARTIFACT_DIR", "~/CoChem_Artifacts")).expanduser().resolve())')"
case "$artifact_root" in
  /|"$repo_root"|"$repo_root"/*)
    echo 'COCHEM_ARTIFACT_DIR must be outside the source checkout.' >&2
    exit 2
    ;;
esac

artifact_bin="$artifact_root/bin"
ui_env="$artifact_root/ui-env"
ui_env_bin="$ui_env/bin"
ui_python="${COCHEM_SPYFY_PYTHON:-$ui_env_bin/python}"

mkdir -p -- "$artifact_bin"

if [ ! -x "$ui_python" ]; then
  echo "Error: CoChem ui-env Python not found at $ui_python." >&2
  echo "Run 'bash scripts/setup_devcontainer.sh' (or set COCHEM_SPYFY_PYTHON) first." >&2
  exit 1
fi

echo "Installing optional add-on CoChem-SPYFY (${SPYFY_REV:0:12}) + jax[cpu] into $ui_env..."
"$ui_python" -m pip install --no-input --quiet \
  "jax[cpu]" \
  "git+${SPYFY_REPO}@${SPYFY_REV}"

{
  printf '#!%s\n' "$ui_python"
  cat <<'PY'
"""Standalone CLI wrapper for optional CoChem-SPYFY provider operations."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _emit(payload: object, out_path: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, allow_nan=False)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cochem-spyfy",
        description="CoChem-SPYFY optional add-on CLI dispatching to cochem_spyfy.module_provider.",
    )
    sub = parser.add_subparsers(dest="command")

    p_info = sub.add_parser("info", help="Print CoChem-SPYFY provider capabilities, profiles, and operations.")
    p_info.add_argument("--check-compat", action="store_true", help="Verify GruLab SURF profile compatibility metadata.")
    p_info.add_argument("--out", type=Path, default=None, help="Optional JSON output path.")

    p_parse = sub.add_parser("parse", help="Parse a Pickett .var, .par, .fit, or .cat file.")
    p_parse.add_argument("input_file", type=Path, help="Path to Pickett .var/.par/.fit/.cat file.")
    p_parse.add_argument("--kind", choices=("var", "par", "fit", "cat"), default=None, help="Explicit file kind.")
    p_parse.add_argument("--out", type=Path, default=None, help="Optional JSON output path.")

    p_pred = sub.add_parser("predict", help="Predict rotational spectrum via Pickett SPCAT.")
    p_pred.add_argument("--var", dest="var_file", type=Path, required=True, help="Path to Pickett .var file.")
    p_pred.add_argument("--int", dest="int_file", type=Path, required=True, help="Path to Pickett .int file.")
    p_pred.add_argument("--stem", default="cochem_spcat", help="Run stem name.")
    p_pred.add_argument("--out", type=Path, default=None, help="Optional JSON output path.")

    p_fit = sub.add_parser("fit", help="Fit rotational constants via Pickett SPFIT.")
    p_fit.add_argument("--par", dest="par_file", type=Path, required=True, help="Path to Pickett .par file.")
    p_fit.add_argument("--lin", dest="lin_file", type=Path, required=True, help="Path to Pickett .lin file.")
    p_fit.add_argument("--stem", default="cochem_spfit", help="Run stem name.")
    p_fit.add_argument("--out", type=Path, default=None, help="Optional JSON output path.")

    p_plan = sub.add_parser("plan-surf", help="Plan a GruLab SURF scan region and export validated TOMLs.")
    p_plan.add_argument("--output-dir", type=Path, required=True, help="Directory for exported SURF TOML files.")
    p_plan.add_argument("--start-freq", type=float, default=None, help="Explicit scan start frequency (MHz).")
    p_plan.add_argument("--end-freq", type=float, default=None, help="Explicit scan end frequency (MHz).")
    p_plan.add_argument("--step-size", type=float, default=None, help="Scan step size (MHz).")
    p_plan.add_argument("--acq-num", type=int, default=None, help="Acquisitions per step.")
    p_plan.add_argument("--molecule", default="HCOOH_DME", help="Molecule identifier for SURF metadata.")
    p_plan.add_argument("--gas", default="Ne", help="Backing gas name (e.g., Ne, Ar, He).")
    p_plan.add_argument("--profile", default="grulab_surf", help="Instrument profile name.")
    p_plan.add_argument("--mode", choices=("explicit", "survey", "targeted"), default=None, help="Planner mode.")
    p_plan.add_argument("--payload-json", type=Path, default=None, help="Optional JSON file of keyword arguments.")
    p_plan.add_argument("--out", type=Path, default=None, help="Optional JSON output path.")

    p_ingest = sub.add_parser("ingest-surf", help="Ingest a GruLab SURF run directory and pick PROPOSED candidates.")
    p_ingest.add_argument("run_dir", type=Path, help="Path to SURF run directory containing scan_settings.toml and CavityFiles/.")
    p_ingest.add_argument("--snr-threshold", type=float, default=5.0, help="Doppler doublet SNR threshold.")
    p_ingest.add_argument("--gas", default=None, help="Optional backing gas override.")
    p_ingest.add_argument("--no-reconcile", action="store_true", help="Skip finalized CSV reconciliation.")
    p_ingest.add_argument("--no-ledger", action="store_true", help="Do not write surf_ingest_provenance.jsonl.")
    p_ingest.add_argument("--out", type=Path, default=None, help="Optional JSON output path.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    try:
        from cochem_spyfy import module_provider as spyfy_mod
    except ImportError as exc:
        print(
            f"cochem-spyfy error: optional CoChem-SPYFY add-on is not installed ({exc}). "
            "Install with: bash scripts/install_optional_spyfy.sh",
            file=sys.stderr,
        )
        return 1

    if args.command == "info":
        payload = spyfy_mod.spyfy_provider()
        if args.check_compat:
            if payload.get("default_instrument_profile") != "grulab_surf":
                print(
                    f"cochem-spyfy compat error: expected default_instrument_profile='grulab_surf', "
                    f"got {payload.get('default_instrument_profile')!r}",
                    file=sys.stderr,
                )
                return 2
        _emit(payload, args.out)
        return 0

    if args.command == "parse":
        kind = args.kind or args.input_file.suffix.lstrip(".").lower()
        if kind not in {"var", "par", "fit", "cat"}:
            print(f"cochem-spyfy error: unsupported kind {kind!r}; specify --kind var|par|fit|cat", file=sys.stderr)
            return 2
        text = args.input_file.read_text(encoding="utf-8")
        _emit(spyfy_mod.parse_pickett(kind, text), args.out)
        return 0

    if args.command == "predict":
        var_text = args.var_file.read_text(encoding="utf-8")
        int_text = args.int_file.read_text(encoding="utf-8")
        _emit(spyfy_mod.predict_spectrum(var_text, int_text, stem=args.stem), args.out)
        return 0

    if args.command == "fit":
        par_text = args.par_file.read_text(encoding="utf-8")
        lin_text = args.lin_file.read_text(encoding="utf-8")
        _emit(spyfy_mod.fit_pickett(par_text, lin_text, stem=args.stem), args.out)
        return 0

    if args.command == "plan-surf":
        kwargs: dict[str, object] = {}
        if args.payload_json is not None:
            loaded = json.loads(args.payload_json.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                print("cochem-spyfy error: --payload-json must contain a JSON object", file=sys.stderr)
                return 2
            kwargs.update(loaded)
        kwargs["output_dir"] = args.output_dir
        if args.start_freq is not None:
            kwargs["start_freq_mhz"] = args.start_freq
        if args.end_freq is not None:
            kwargs["end_freq_mhz"] = args.end_freq
        if args.step_size is not None:
            kwargs["step_size_mhz"] = args.step_size
        if args.acq_num is not None:
            kwargs["acq_num"] = args.acq_num
        if args.mode is not None:
            kwargs["mode"] = args.mode
        kwargs.setdefault("molecule_name", args.molecule)
        kwargs.setdefault("gas_name", args.gas)
        kwargs.setdefault("instrument_profile", args.profile)
        _emit(spyfy_mod.plan_surf_scan(**kwargs), args.out)
        return 0

    if args.command == "ingest-surf":
        payload = spyfy_mod.ingest_surf_run(
            args.run_dir,
            snr_threshold=args.snr_threshold,
            gas_name=args.gas,
            reconcile=not args.no_reconcile,
            write_provenance_ledger=not args.no_ledger,
        )
        _emit(payload, args.out)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY
} > "$artifact_bin/cochem-spyfy"
chmod 0755 "$artifact_bin/cochem-spyfy"

echo "Verifying cochem-spyfy info (checking default_instrument_profile == 'grulab_surf')..."
spyfy_info="$("$artifact_bin/cochem-spyfy" info --check-compat)"
"$ui_python" - "$spyfy_info" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
profile = data.get("default_instrument_profile")
if profile != "grulab_surf":
    raise SystemExit(f"Expected default_instrument_profile='grulab_surf', got {profile!r}")
print(f"Verified CoChem-SPYFY add-on: distribution={data.get('distribution')} default_instrument_profile={profile!r}")
PY
