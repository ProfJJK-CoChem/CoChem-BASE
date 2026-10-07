"""Prepare and execute geometry-analysis handoffs for installed modules."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modules", nargs="+", required=True)
    parser.add_argument("--xyz-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args(argv)
    from cochem_base.interfaces.artifact_handoff import prepare_module_handoff
    from cochem_base.interfaces.module_execution import execute_module_handoff
    from scripts.manage_modules import DEFAULT_MANIFEST, load_manifest
    specs = load_manifest(DEFAULT_MANIFEST)["modules"]
    names = list(dict.fromkeys(args.modules))
    for name in names:
        if name not in specs or "geometry_analysis" not in specs[name]["operations"]:
            parser.error(f"{name!r} has no reviewed geometry-analysis adapter")
    for name in names:
        package = args.output / name / "handoff"
        prepare_module_handoff(name, args.xyz_file, package, operation="geometry_analysis")
        result = execute_module_handoff(package / "handoff.json", args.output / name / "execution", root=args.root)
        print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
