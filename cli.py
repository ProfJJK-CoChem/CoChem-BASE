#!/usr/bin/env python3
"""Compatibility launcher for the canonical installed CoChem-BASE CLI."""
from pathlib import Path
import sys

# A source checkout uses src/; an installed wheel already has its package on path.
source = Path(__file__).resolve().parent / "src"
if (source / "cochem_base" / "cli.py").is_file():
    sys.path.insert(0, str(source))

from cochem_base.cli import *  # noqa: E402,F403
from cochem_base.cli import _accept_orca_result, _parse_run_geometry, entrypoint  # noqa: E402,F401


if __name__ == "__main__":
    raise SystemExit(entrypoint())
