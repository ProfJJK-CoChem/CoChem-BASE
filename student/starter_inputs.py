#!/usr/bin/env python3
"""Pure-stdlib student starter XYZ input materializer for CoChem courses.

Provides verified starting Cartesian coordinates (in Angstrom, with zero
fabricated energies or accuracy claims) for course walkthroughs without
introducing untracked or unhashed `.xyz` blobs into the static Git tree:

  - `hcooh_start.xyz`: planar trans-formic acid (HCOOH, 5 atoms, Q=0, M=1)
  - `hcooh_water_dimer.xyz`: cyclic H-bonded trans-HCOOH...H2O 1:1 complex
    (8 atoms: atoms 1-5 HCOOH, atoms 6-8 H2O, Q=0, M=1)
  - `ethanol_start.xyz`: ethanol teaching starting geometry (9 atoms, Q=0, M=1)
  - `h2co_start.xyz`: planar C2v formaldehyde (H2CO, 4 atoms, Q=0, M=1)
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]

STARTER_INPUTS: dict[str, dict[str, Any]] = {
    "hcooh_start.xyz": {
        "filename": "hcooh_start.xyz",
        "formula": "CH2O2",
        "n_atoms": 5,
        "charge": 0,
        "multiplicity": 1,
        "description": "Planar trans-formic acid (HCOOH) starting geometry in angstrom",
        "default_fragments": None,
        "xyz_text": (
            "5\n"
            "Planar trans-formic acid (HCOOH) starting geometry in angstrom; no calculated energy\n"
            "C   0.000000   0.000000   0.000000\n"
            "O   1.202000   0.000000   0.000000\n"
            "O  -0.768400   1.101400   0.000000\n"
            "H  -0.615000  -0.908400   0.000000\n"
            "H  -0.159300   1.858800   0.000000\n"
        ),
    },
    "hcooh_water_dimer.xyz": {
        "filename": "hcooh_water_dimer.xyz",
        "formula": "CH4O3",
        "n_atoms": 8,
        "charge": 0,
        "multiplicity": 1,
        "description": (
            "Cyclic hydrogen-bonded trans-HCOOH...H2O 1:1 dimer starting geometry in angstrom "
            "(fragment A: atoms 1-5 HCOOH; fragment B: atoms 6-8 H2O)"
        ),
        "default_fragments": {"frag_a": "1-5", "frag_b": "6-8"},
        "xyz_text": (
            "8\n"
            "Cyclic H-bonded trans-HCOOH...H2O dimer starting geometry (atoms 1-5 HCOOH, atoms 6-8 H2O; angstrom)\n"
            "C  -0.960000   0.180000   0.000000\n"
            "O  -0.460000  -0.920000   0.000000\n"
            "O  -0.250000   1.310000   0.000000\n"
            "H  -2.050000   0.310000   0.000000\n"
            "H   0.720000   1.140000   0.000000\n"
            "O   2.350000   0.450000   0.000000\n"
            "H   1.620000  -0.210000   0.000000\n"
            "H   3.080000   0.180000   0.570000\n"
        ),
    },
    "ethanol_start.xyz": {
        "filename": "ethanol_start.xyz",
        "formula": "C2H6O",
        "n_atoms": 9,
        "charge": 0,
        "multiplicity": 1,
        "description": "Ethanol teaching starting geometry in angstrom",
        "default_fragments": None,
        "xyz_text": (
            "9\n"
            "Ethanol teaching input in angstrom, from BASE verify_free_engines.py\n"
            "C -0.748 0.015 0.024\n"
            "C 0.748 -0.015 -0.024\n"
            "O 1.250 1.290 0.025\n"
            "H -1.129 -0.526 0.899\n"
            "H -1.166 -0.494 -0.851\n"
            "H -1.129 1.055 0.024\n"
            "H 1.128 -0.556 -0.899\n"
            "H 1.128 -0.556 0.851\n"
            "H 2.205 1.215 0.025\n"
        ),
    },
    "h2co_start.xyz": {
        "filename": "h2co_start.xyz",
        "formula": "CH2O",
        "n_atoms": 4,
        "charge": 0,
        "multiplicity": 1,
        "description": "Planar C2v formaldehyde (H2CO) starting geometry in angstrom",
        "default_fragments": None,
        "xyz_text": (
            "4\n"
            "Planar C2v formaldehyde (H2CO) starting geometry in angstrom; no calculated energy\n"
            "C   0.000000   0.000000  -0.528800\n"
            "O   0.000000   0.000000   0.676200\n"
            "H   0.000000   0.935000  -1.110000\n"
            "H   0.000000  -0.935000  -1.110000\n"
        ),
    },
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def list_starter_inputs() -> list[dict[str, Any]]:
    """Return metadata records for all built-in starter XYZ inputs."""
    records: list[dict[str, Any]] = []
    for name in sorted(STARTER_INPUTS):
        entry = STARTER_INPUTS[name]
        records.append(
            {
                "filename": entry["filename"],
                "formula": entry["formula"],
                "n_atoms": entry["n_atoms"],
                "charge": entry["charge"],
                "multiplicity": entry["multiplicity"],
                "description": entry["description"],
                "default_fragments": entry["default_fragments"],
                "sha256": sha256_text(entry["xyz_text"]),
            }
        )
    return records


def get_starter_xyz_text(name: str) -> str:
    """Return canonical XYZ text for a known starter filename (or raise KeyError)."""
    leaf = Path(str(name)).name
    if leaf not in STARTER_INPUTS:
        raise KeyError(
            f"Unknown starter input {name!r}; available: {sorted(STARTER_INPUTS)}"
        )
    return STARTER_INPUTS[leaf]["xyz_text"]


def is_known_starter_input(name: str | Path) -> bool:
    return Path(str(name)).name in STARTER_INPUTS


def materialize_starter_input(name: str, target_dir: Path | str) -> Path:
    """Write a single starter XYZ input into `target_dir` using Unix LF line endings."""
    leaf = Path(str(name)).name
    text = get_starter_xyz_text(leaf)
    out_dir = Path(target_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / leaf
    if out_path.is_symlink():
        raise ValueError(f"Refusing to overwrite symlinked file: {out_path}")
    out_path.write_text(text, encoding="utf-8", newline="\n")
    return out_path.resolve()


def write_starter_inputs(
    target_dir: Path | str,
    names: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Materialize all (or selected) starter XYZ files into `target_dir`."""
    selected = list(names) if names else sorted(STARTER_INPUTS)
    written: list[dict[str, Any]] = []
    for raw_name in selected:
        leaf = Path(str(raw_name)).name
        entry = STARTER_INPUTS.get(leaf)
        if entry is None:
            raise ValueError(
                f"Unknown starter input {raw_name!r}; available: {sorted(STARTER_INPUTS)}"
            )
        out_path = materialize_starter_input(leaf, target_dir)
        written.append(
            {
                "filename": leaf,
                "path": str(out_path),
                "formula": entry["formula"],
                "n_atoms": entry["n_atoms"],
                "charge": entry["charge"],
                "multiplicity": entry["multiplicity"],
                "sha256": sha256_text(entry["xyz_text"]),
            }
        )
    return written


def resolve_or_materialize_input(
    spec: str | Path,
    *,
    materialize_dir: Path | str | None = None,
    examples_dir: Path | None = None,
) -> Path:
    """Resolve an existing `.xyz` file or materialize a known starter input cleanly.

    Search order:
    1. Existing direct file path `Path(spec)`.
    2. Existing file inside `examples/student_inputs/<leaf>`.
    3. Built-in verified starter input materialized into `materialize_dir` (never
       writing untracked `.xyz` files into the static repository tree).
    """
    raw = str(spec)
    candidate = Path(raw)
    if candidate.is_file() and not candidate.is_symlink() and candidate.suffix.lower() == ".xyz":
        return candidate.resolve()

    leaf = candidate.name
    ex_dir = (examples_dir or (ROOT / "examples" / "student_inputs")).resolve()
    if leaf == raw or candidate.parent.as_posix().endswith("examples/student_inputs"):
        ex_candidate = ex_dir / leaf
        if (
            not ex_candidate.is_symlink()
            and ex_candidate.is_file()
            and ex_candidate.resolve().parent == ex_dir
            and ex_candidate.suffix.lower() == ".xyz"
        ):
            return ex_candidate.resolve()

    if leaf in STARTER_INPUTS:
        dest = Path(materialize_dir) if materialize_dir is not None else Path.cwd()
        return materialize_starter_input(leaf, dest)

    raise ValueError(
        f"Could not find XYZ input {spec!r} on disk, in examples/student_inputs/, "
        f"or among built-in starter inputs ({', '.join(sorted(STARTER_INPUTS))})."
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="starter_inputs.py",
        description=(
            "List or materialize verified CoChem student starter `.xyz` geometries "
            "(hcooh_start.xyz, hcooh_water_dimer.xyz, ethanol_start.xyz, h2co_start.xyz)."
        ),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_only",
        help="List available built-in starter `.xyz` inputs without writing files.",
    )
    parser.add_argument(
        "--write-dir",
        type=Path,
        default=None,
        help="Directory where starter `.xyz` files will be written.",
    )
    parser.add_argument(
        "--names",
        nargs="+",
        default=None,
        help="Optional subset of starter filenames to write (default: all 4).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit machine-readable JSON output.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.list_only and args.write_dir is None:
        args.list_only = True

    try:
        if args.write_dir is not None:
            written = write_starter_inputs(args.write_dir, names=args.names)
            payload: dict[str, Any] = {
                "ok": True,
                "write_dir": str(args.write_dir.resolve()),
                "files": written,
            }
            if args.as_json:
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                for item in written:
                    print(f"Wrote {item['path']} ({item['formula']}, sha256={item['sha256'][:12]}...)")
            return 0

        entries = list_starter_inputs()
        payload = {"ok": True, "starter_inputs": entries}
        if args.as_json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            for item in entries:
                print(
                    f"{item['filename']:24s} {item['formula']:8s} "
                    f"({item['n_atoms']} atoms, Q={item['charge']}, M={item['multiplicity']}) — {item['description']}"
                )
        return 0
    except (ValueError, KeyError, OSError) as exc:
        if args.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
