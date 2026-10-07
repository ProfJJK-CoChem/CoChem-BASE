"""Compatibility entrypoint for the canonical BASE source-integrity gate.

Historical self-issued hash baselines are retired. The canonical runner records
actual source snapshots and compares them across test execution; these records
are change detection evidence, not publisher signatures or external attestations.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ci_tools.base_ci import main as base_ci_main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path(os.environ.get("COCHEM_ARTIFACT_DIR", tempfile.gettempdir())) / "cochem-integrity-evidence")
    arguments = parser.parse_args(argv)
    return base_ci_main(["audit", "--output", str(arguments.output)])


if __name__ == "__main__":
    raise SystemExit(main())
