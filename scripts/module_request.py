"""Bounded request-file transport, without replacing provider validation."""
from __future__ import annotations

import json
import math
from pathlib import Path

TOPOS_OPERATIONS = ("energy", "gradient", "optimize", "search", "frequency",
                    "thermochemistry", "association", "matrix")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Request JSON contains duplicate keys")
        result[key] = value
    return result


def _finite_json(value):
    raise ValueError(f"Request JSON contains nonfinite value {value}")


def read_topos_request(path: str | Path) -> dict:
    source = Path(path).expanduser()
    if source.is_symlink() or not source.is_file() or not 0 < source.stat().st_size <= 2_000_000:
        raise ValueError("Select a bounded regular TOPOS request JSON file")
    raw = source.read_bytes()
    if len(raw) > 2_000_000:
        raise ValueError("TOPOS request JSON exceeds the input limit")
    request = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_finite_json)
    # JSON numeric literals such as 1e999 overflow without invoking parse_constant.
    json.dumps(request, allow_nan=False)
    if not isinstance(request, dict) or request.get("purpose") not in TOPOS_OPERATIONS:
        raise ValueError("TOPOS request requires an explicit supported purpose")
    molecule = request.get("molecule")
    if not isinstance(molecule, dict) or not {"symbols", "coordinates", "charge", "multiplicity"} <= molecule.keys():
        raise ValueError("Declare molecular coordinates, atom order, charge and multiplicity in the TOPOS request")
    if not {"engine", "budget_seconds", "threads", "memory_mb"} <= request.keys():
        raise ValueError("Declare engine, budget_seconds, threads and memory_mb in the TOPOS request")
    if any(type(request[key]) is not int or request[key] < 1 for key in ("threads", "memory_mb")):
        raise ValueError("TOPOS threads and memory_mb must be positive integers")
    budget = request["budget_seconds"]
    if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not math.isfinite(budget) or budget <= 0:
        raise ValueError("TOPOS budget_seconds must be finite and positive")
    if source.read_bytes() != raw:
        raise ValueError("TOPOS request changed while being read")
    return request


def handoff_options(module_id: str, request_file: str | Path | None,
                    *, legacy_operation: str = "geometry_analysis") -> tuple[str, dict]:
    if module_id == "topos":
        if request_file is None or not str(request_file).strip():
            raise ValueError("Select an explicit TOPOS request JSON file")
        request = read_topos_request(request_file)
        return request["purpose"], {"topos_request": request}
    if request_file is not None and str(request_file).strip():
        raise ValueError("TOPOS request JSON can only be sent to TOPOS")
    return legacy_operation, {}


def execution_timeout(value: float, options: dict) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError("Module execution timeout must be finite and positive")
    requested = options.get("topos_request", {}).get("budget_seconds")
    if requested is not None and requested > value:
        raise ValueError("Module timeout must cover the explicit TOPOS calculation budget")
    return float(value)


def repository_member(root: Path, value: str, *, directory: bool = False) -> Path:
    """Resolve a user-selected local input, without links or checkout escapes."""
    relative = Path(value)
    if not value or any(char in value for char in "\r\n\x00") or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Select a repository-relative input path")
    root = root.resolve(strict=True)
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("Hosted inputs cannot traverse symbolic links")
    result = current.resolve(strict=True)
    if not result.is_relative_to(root) or not (result.is_dir() if directory else result.is_file()):
        raise ValueError("Hosted input is not the required repository member")
    return result


def hosted_topos_request(root: Path, *, request_file: str,
                         timeout: float, repository_private: bool) -> dict:
    """Preflight transport/allocation only; installed BASE verifies the full kit."""
    if repository_private is not True:
        raise ValueError("TOPOS hosted execution retains native evidence and requires a private repository")
    request = repository_member(root, request_file)
    operation, options = handoff_options("topos", request)
    limit = execution_timeout(timeout, options)
    typed = options["topos_request"]
    if typed.get("calculation_environment", "local") != "local":
        raise ValueError("Hosted receiver executes locally on its assigned runner; remote delegation is not accepted")
    if typed["threads"] > 2 or typed["memory_mb"] > 4096 or limit > 14400:
        raise ValueError("Hosted allocation is at most 2 cores, 4096 MiB and 14400 receiver seconds")
    return {"operation": operation, "request_path": str(request), "timeout": limit}
