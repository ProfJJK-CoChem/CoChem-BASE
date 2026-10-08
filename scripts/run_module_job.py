"""Execute typed TOPOS requests or legacy geometry operations through BASE."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from scripts.module_request import execution_timeout, handoff_options


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modules", nargs="+", required=True)
    parser.add_argument("--xyz-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--registry", type=Path, help="Fresh audited BASE registry for scientific provider operations")
    parser.add_argument("--topos-request", type=Path, help="TOPOS request JSON; its purpose selects the operation")
    parser.add_argument("--timeout", type=float, default=180, help="Total receiver timeout including verification")
    args = parser.parse_args(argv)
    from cochem_base.interfaces.artifact_handoff import prepare_module_handoff
    from cochem_base.interfaces.module_execution import execute_module_handoff
    from scripts.manage_modules import DEFAULT_MANIFEST, load_manifest
    specs = load_manifest(args.manifest or DEFAULT_MANIFEST)["modules"]
    names = list(dict.fromkeys(args.modules))
    if args.topos_request and "topos" not in names:
        parser.error("TOPOS request JSON requires selecting TOPOS")
    requests = {}
    for name in names:
        if (name == "topos" and args.topos_request is None
                and name in specs and specs[name].get("adapter") == "topos_provider"):
            operation, options = "geometry_analysis", {}
        else:
            operation, options = handoff_options(name, args.topos_request if name == "topos" else None)
        if name not in specs or operation not in specs[name]["operations"]:
            parser.error(f"{name!r} has no reviewed {operation!r} operation")
        requests[name] = operation, options, execution_timeout(args.timeout, options)
    failures = []
    for name in names:
        operation, options, timeout = requests[name]
        package = args.output / name / "handoff"
        try:
            prepare_module_handoff(name, args.xyz_file, package, operation=operation, options=options)
            result = execute_module_handoff(package / "handoff.json", args.output / name / "execution",
                                            root=args.root, manifest=args.manifest, timeout=timeout,
                                            registry=args.registry)
            print(json.dumps(result, allow_nan=False))
            if result.get("status") != "completed":
                failures.append(name)
        except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
            from scripts.manage_modules import _redact
            failures.append(name)
            print(json.dumps({"module_id": name, "status": "failed", "error": _redact(str(exc))}))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
