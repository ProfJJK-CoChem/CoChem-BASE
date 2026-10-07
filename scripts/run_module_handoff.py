"""Run an integrity-checked artifact through a reviewed, installed module adapter."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    from cochem_base.interfaces.module_execution import execute_module_handoff
    result = execute_module_handoff(args.handoff, args.output, root=args.root, manifest=args.manifest)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
