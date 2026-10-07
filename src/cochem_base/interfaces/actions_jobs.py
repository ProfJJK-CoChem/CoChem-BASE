"""Shared Classroom50 Actions request limits for the GUI and calculation runner.

Only embedded molecular ORCA requests are accepted: at most 50 atoms, one or two
CPU processes, 1024 MB per process and 30 minutes of chemistry execution. External
checkpoints and downstream-only operations require separate ecosystem workflows.
Imports remain standard-library only until full scientific validation is called.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

MAX_JOB_BYTES = 256 * 1024
MAX_ATOMS = 50
MAX_TIMEOUT_SECONDS = 1800
# A single electronic-method keyword prevents operation/resource/file keywords
# from being smuggled into the canonical input builder's method line.
ORCA_METHODS = frozenset({
    "HF", "RHF", "UHF", "ROHF", "B3LYP", "B3LYP-D3BJ", "B3LYP-D4",
    "PBE", "PBE-D4", "PBE0", "PBE0-D3BJ", "PBE0-D4", "WB97M-V",
    "WB97X-V", "WB97X-D4", "R2SCAN-3C", "B97-3C", "PWPB95-D4",
    "B2PLYP-D3", "MP2", "SCS-MP2", "RI-MP2", "CCSD", "CCSD(T)",
    "DLPNO-CCSD(T)", "DLPNO-CCSD(T1)",
})


def decode_configuration(contents: bytes) -> dict[str, Any]:
    """Parse strict finite JSON without ambiguous duplicate fields."""
    if len(contents) > MAX_JOB_BYTES:
        raise ValueError("Job JSON exceeds the 256 KiB limit")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON field: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(f"Nonfinite JSON value is prohibited: {value}")

    data = json.loads(contents.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=reject_constant)
    if not isinstance(data, dict):
        raise ValueError("Job JSON must contain one flat calculation configuration object")
    return data


def validate_resources(cores: int, maxcore_mb: int) -> None:
    if type(cores) is not int or cores not in (1, 2):
        raise ValueError("Classroom calculations require 1 or 2 CPU cores")
    if type(maxcore_mb) is not int or not 1 <= maxcore_mb <= 1024:
        raise ValueError("maxcore_mb must be an integer from 1 through 1024 MB per process")


def preflight_configuration(data: dict[str, Any]) -> None:
    """Cheap limits before downloading the licensed engine; full validation follows."""
    if data.get("engine", "orca") != "orca":
        raise ValueError("The ORCA calculation workflow requires engine='orca'")
    for field in ("hessian_file", "r2_reference_manifest", "t9_fallback", "periodic"):
        if data.get(field) is not None:
            raise ValueError(f"Classroom jobs do not accept external dependencies or recovery inputs: {field}")
    if data.get("initial_hessian", "XTB2") == "READ" or data.get("recipe") == "R2":
        raise ValueError("This job requires external scientific inputs; use the ecosystem workflow for those inputs")
    if data.get("initial_hessian", "XTB2") not in {"XTB2", "Lindh"}:
        raise ValueError("Classroom optimization requires the supported XTB2 or Lindh initial Hessian")
    if data.get("recipe") not in {None, "R1"}:
        raise ValueError("Unsupported molecular recipe for this self-contained classroom workflow")
    if data.get("recipe") == "R1" and str(data.get("method", "wB97M-V")).upper() != "R2SCAN-3C":
        raise ValueError("Recipe R1 requires r2SCAN-3c")
    if data.get("is_vpt2", False) is not False:
        raise ValueError("VPT2 requires its downstream scientific adapter; this workflow cannot certify VPT2")
    if data.get("is_freq") is True and data.get("grid_stage") not in (None, 3):
        raise ValueError("Harmonic frequency calculations require DEFGRID3")
    timeout = data.get("timeout_seconds", 3600)
    if (type(timeout) not in (int, float) or not math.isfinite(timeout)
            or not 0 < timeout <= MAX_TIMEOUT_SECONDS):
        raise ValueError("Set timeout_seconds to a positive number no greater than 1800")
    if not isinstance(data.get("geometry"), str):
        raise ValueError("Embed the molecular geometry in the geometry JSON field")
    if str(data.get("method", "wB97M-V")).upper() not in ORCA_METHODS:
        raise ValueError("Use one supported ORCA electronic-method keyword; raw ORCA keywords/decks are not accepted")
    basis = data.get("basis_set", "def2-TZVP")
    if basis is not None and (not isinstance(basis, str) or not re.fullmatch(
            r"(?:def2-[A-Za-z0-9]+|(?:aug-|jun-)?cc-p[A-Za-z0-9]+|STO-3G|MINI|MINIX|ANO[0-9]+|mTZVP|built-in|default)", basis)):
        raise ValueError("basis_set must be one supported orbital-basis name; operation/resource/file keywords are prohibited")
    solvation = data.get("implicit_solvation")
    if solvation is not None and (not isinstance(solvation, str) or not re.fullmatch(r"CPCM\([A-Za-z0-9_-]+\)", solvation)):
        raise ValueError("Classroom solvation accepts a single CPCM(solvent) expression")


def validate_configuration(contents: bytes, data: dict[str, Any]) -> Any:
    from cochem_base.calc.calculation_service import CalculationMatrixConfig, parse_run_geometry
    from cochem_base.calc.molecular_input import build_molecular_input
    from cochem_base.interfaces.scientific_jobs import calculation_capability, validate_job_configuration

    parsed = decode_configuration(contents)
    if parsed != data:
        raise ValueError("Parsed job fields differ from the submitted JSON bytes")
    preflight_configuration(parsed)
    config = CalculationMatrixConfig.model_validate_json(contents, strict=True)
    elements, _ = parse_run_geometry(config.geometry)
    if len(elements) > MAX_ATOMS:
        raise ValueError("Classroom calculations are limited to 50 atoms")
    validate_job_configuration(config)
    capability = calculation_capability(config)
    if capability.adapter_status != "connected":
        raise ValueError(f"{capability.operation} is pending scientific integration: {capability.reason}")
    build_molecular_input(config)
    return config
