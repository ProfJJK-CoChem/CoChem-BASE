"""Verify committed infrastructure-ring and publisher bytes before execution.

The reviewed ring is authenticated by the selected Git commit. It is never
generated or refreshed by this checker and is not a Council signature.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path(os.environ.get("COCHEM_ARTIFACT_DIR", tempfile.gettempdir())) / "cochem-integrity-evidence")
    parser.add_argument("--expected-revision", help="Immutable publisher/approved canonical worker Git revision")
    parser.add_argument("--development", action="store_true", help="Local checks only; cannot qualify a release")
    arguments = parser.parse_args(argv)
    forwarded = ["audit", "--output", str(arguments.output)]
    if arguments.expected_revision:
        forwarded.extend(["--expected-revision", arguments.expected_revision])
    if arguments.development:
        forwarded.append("--development")
    from ci_tools.base_ci import main as base_ci_main
    return base_ci_main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
