"""Legacy fast-pass CLI migrated to validated native BASE calculation configs.

The removed wrapper advertised unsupported remote lookups and engine options.
Use the BASE GUI molecule builder to prepare a configuration before execution.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cochem_unity_fast_pass_widget import FastPassOptConfig, FastPassWidget, run_fast_pass_optimization

run_fast_pass = run_fast_pass_optimization
run_triage = run_fast_pass_optimization
triage_geometry = run_fast_pass_optimization
fast_pass_triage = run_fast_pass_optimization


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--scratch", type=Path)
    parser.add_argument("--threads", type=int)
    args = parser.parse_args(argv)
    result = run_fast_pass_optimization(args.config, output=args.output,
                                       scratch=args.scratch, threads=args.threads)
    print(json.dumps(result, indent=2))
    return 0


__all__ = ["FastPassOptConfig", "FastPassWidget", "run_fast_pass_optimization",
           "run_fast_pass", "run_triage", "triage_geometry", "fast_pass_triage", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
