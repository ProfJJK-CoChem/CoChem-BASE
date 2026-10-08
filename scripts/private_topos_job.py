"""Exact TOPOS request and source intent for a private personal Actions runner.

This is a transport/allocation gate. The installed TOPOS model and BASE provider
perform their own complete chemistry and native-evidence checks before execution.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

WORKFLOW = ".github/workflows/topos_calculation.yml"
INTENT_KEYS = {"kind", "job_file", "input_sha256", "cores", "maxcore_mb", "memory_mb",
               "budget_seconds", "receiver_timeout", "source_pins", "kit_sha256"}
HOSTED_BUDGET_KEYS = {"schema_version", "request_sha256", "repository", "repository_id", "owner_id",
                     "source_sha", "ref", "workflow_path", "run_id", "run_attempt", "workflow_created_at"}


def load_hosted_budget(path: Path, request: dict, environment: Mapping[str, str]) -> dict:
    """Recheck source/run/request binding across the credential-free child boundary."""
    from scripts.private_engine_assets import _json, _private_output

    source = _private_output(path)
    if not source.is_file() or not 0 < source.stat().st_size <= 8192:
        raise ValueError("A bounded external authenticated hosted budget control is required")
    raw = source.read_bytes()
    value = _json(raw)
    if (not isinstance(value, dict) or set(value) != HOSTED_BUDGET_KEYS
            or value["schema_version"] != "cochem.topos-hosted-budget/1"
            or value["workflow_path"] != WORKFLOW or request.get("include_queue_in_budget") is not True
            or value["request_sha256"] != hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False).encode()).hexdigest()
            or any(type(value[key]) is not int or value[key] < 1 for key in ("repository_id", "owner_id", "run_id", "run_attempt"))
            or environment.get("GITHUB_ACTIONS") != "true"
            or any(environment.get(variable) != str(value[key]) for variable, key in (
                ("GITHUB_REPOSITORY", "repository"), ("GITHUB_REPOSITORY_ID", "repository_id"),
                ("GITHUB_REPOSITORY_OWNER_ID", "owner_id"), ("GITHUB_SHA", "source_sha"),
                ("GITHUB_REF", "ref"), ("GITHUB_RUN_ID", "run_id"), ("GITHUB_RUN_ATTEMPT", "run_attempt")))
            or environment.get("GITHUB_WORKFLOW_REF") != f"{value['repository']}/{WORKFLOW}@{value['ref']}"):
        raise ValueError("Hosted budget controls differ from the exact executing source/run/request")
    if source.read_bytes() != raw:
        raise ValueError("Hosted budget controls changed across the execution boundary")
    return value


def validate_intent(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != INTENT_KEYS or value.get("kind") != "topos/1":
        raise ValueError("TOPOS staging requires its exact typed request, allocation, kit and source intent")
    name = value["job_file"]
    if (not isinstance(name, str) or len(name) > 200 or not name.endswith(".json")
            or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", name)
            or any(part in {".", ".."} for part in name.split("/"))):
        raise ValueError("The TOPOS request must have a safe committed JSON path")
    for field in ("input_sha256", "kit_sha256"):
        if not isinstance(value[field], str) or not re.fullmatch(r"[0-9a-f]{64}", value[field]) or value[field] == "0" * 64:
            raise ValueError("TOPOS request and kit need genuine nonzero SHA-256 identities")
    pins = value["source_pins"]
    if (not isinstance(pins, dict) or set(pins) != {"base", "topos", "torq"}
            or any(not isinstance(pin, str) or not re.fullmatch(r"[0-9a-f]{40}", pin) or pin == "0" * 40
                   for pin in pins.values())):
        raise ValueError("The mandatory package requires exact BASE, TOPOS and TORQ source pins")
    if (type(value["cores"]) is not int or value["cores"] not in {1, 2}
            or type(value["memory_mb"]) is not int or not 64 <= value["memory_mb"] <= 4096
            or type(value["maxcore_mb"]) is not int
            or value["maxcore_mb"] != math.ceil(value["memory_mb"] / value["cores"])):
        raise ValueError("TOPOS hosting permits 1–2 CPU threads and an explicit 64–4096 MiB allocation")
    for field in ("budget_seconds", "receiver_timeout"):
        if (isinstance(value[field], bool) or not isinstance(value[field], (int, float))
                or not math.isfinite(value[field]) or not 0 < value[field] <= 14400):
            raise ValueError("TOPOS workflow and receiver budgets must be finite and at most 14400 seconds")
    if value["receiver_timeout"] < value["budget_seconds"]:
        raise ValueError("The receiver timeout must cover the exact TOPOS workflow budget")
    return value


def validate_bound_request(checkout: Path, intent: dict[str, Any], environment: Mapping[str, str]) -> dict[str, Any]:
    from scripts.module_request import read_topos_request, repository_member

    validate_intent(intent)
    if any(environment.get(variable) != str(intent[field]) for variable, field in (
        ("JOB_FILE", "job_file"), ("JOB_CORES", "cores"), ("JOB_MAXCORE_MB", "maxcore_mb")
    )):
        raise ValueError("Actual TOPOS job and resource controls differ from their approved intent")
    source = repository_member(checkout, intent["job_file"])
    if hashlib.sha256(source.read_bytes()).hexdigest() != intent["input_sha256"]:
        raise ValueError("Actual committed TOPOS input differs from its approved SHA-256")
    request = read_topos_request(source)
    if (request["threads"] != intent["cores"] or request["memory_mb"] != intent["memory_mb"]
            or request["budget_seconds"] != intent["budget_seconds"]
            or request.get("calculation_environment", "local") != "local"
            or request.get("device", "cpu") != "cpu"):
        raise ValueError("The TOPOS request must execute locally on the exact approved CPU runner allocation")
    json.dumps(request, allow_nan=False)
    return request
