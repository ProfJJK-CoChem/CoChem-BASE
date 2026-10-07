"""Execute configured multireference recovery in an isolated PySCF interpreter.

The active space is scientific input. It is never inferred from contamination or
replaced by a canned CAS(2,2). Recovery evaluates the original input geometry;
its single-point evidence does not certify an interrupted optimization or Hessian.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import time
import uuid
from typing import Any, Callable, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from cochem_base.analysis.electronic_sanitizer import ElectronicSanitizer
from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
from cochem_base.exceptions import SpinContaminationError
from cochem_base.physics.isotopes import get_element_mass_and_abundance


class T9FallbackConfig(BaseModel):
    """An explicit electronic state and orbital selection for automatic recovery."""

    model_config = ConfigDict(extra="forbid")
    python_executable: Path
    pyscf_version: str = "2.14.0"
    method: Literal["CASSCF", "NEVPT2"] = "NEVPT2"
    basis: str = Field(min_length=1)
    active_electrons: StrictInt = Field(ge=1)
    active_orbitals: list[StrictInt] = Field(min_length=1)
    active_space_rationale: str = Field(min_length=1)
    threads: StrictInt = Field(default=1, ge=1)
    memory_mb: StrictInt = Field(default=1024, ge=64)
    timeout_seconds: float = Field(default=600, gt=0, allow_inf_nan=False)
    max_cycle: StrictInt = Field(default=200, ge=1)

    @field_validator("python_executable")
    @classmethod
    def explicit_interpreter(cls, value: Path) -> Path:
        # Do not resolve symlinks: a venv's python may point to the base binary.
        if not value.is_absolute():
            raise ValueError("T9 python_executable must be an absolute micro-silo interpreter path")
        return value

    @field_validator("basis", "pyscf_version", "active_space_rationale")
    @classmethod
    def nonempty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("T9 scientific configuration cannot contain blank values")
        return value.strip()

    @model_validator(mode="after")
    def valid_active_space(self) -> "T9FallbackConfig":
        if len(set(self.active_orbitals)) != len(self.active_orbitals) or min(self.active_orbitals) < 0:
            raise ValueError("Active orbitals must be distinct zero-based MO indices")
        if self.active_electrons > 2 * len(self.active_orbitals):
            raise ValueError("The active space has more electrons than available spin orbitals")
        return self


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run_t9_fallback(
    config: T9FallbackConfig,
    *,
    elements: Sequence[str],
    coordinates: Sequence[Sequence[float]],
    charge: int,
    multiplicity: int,
    directory: Path,
    trigger: SpinContaminationError,
    cancellation_event: Any = None,
    registry_path: Path | None = None,
    nuclides: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Run and validate CASSCF/NEVPT2 after an already terminated primary job."""
    from cochem.core.context import assert_writable_path
    from cochem_base.core_engine.hardware_profiler import profile_hardware
    from cochem_base.core_engine.execution_authority import authorize_engine_execution
    from cochem_base.geometry.nuclide_geometry import resolve_nuclear_identity
    nuclear_identity = resolve_nuclear_identity(nuclides if nuclides is not None else elements)
    if nuclear_identity.elements != tuple(elements):
        raise ValueError("T9 nuclide assignments must match its ordered electronic elements")

    directory = Path(directory).expanduser().resolve()
    assert_writable_path(directory)
    if not elements or len(elements) != len(coordinates) or any(
        len(xyz) != 3 or any(not math.isfinite(float(value)) for value in xyz) for xyz in coordinates
    ):
        raise ValueError("T9 requires finite coordinates matching the input elements")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (charge, multiplicity)) or multiplicity < 1:
        raise ValueError("T9 charge and multiplicity must be physical integers")
    electrons = sum(get_element_mass_and_abundance(symbol)[2] for symbol in elements) - charge
    spin = multiplicity - 1
    inactive = electrons - config.active_electrons
    if inactive < 0 or inactive % 2 or (config.active_electrons - spin) % 2 or spin > config.active_electrons:
        raise ValueError("Configured active electrons cannot represent the molecular charge and spin")
    if (config.active_electrons + spin) // 2 > len(config.active_orbitals):
        raise ValueError("Active space cannot accommodate the requested spin multiplicity")
    if not config.python_executable.is_file() or not os.access(config.python_executable, os.X_OK):
        raise FileNotFoundError(f"T9 PySCF micro-silo interpreter is unavailable: {config.python_executable}")
    hardware = profile_hardware()
    if config.threads > len(hardware.available_cpu_ids) or config.memory_mb * 1024**2 > hardware.available_ram_bytes:
        raise ValueError("T9 requested resources exceed measured available CPU or memory")
    authorization = authorize_engine_execution(
        "pyscf", registry_path=registry_path, executable=str(config.python_executable), cores=config.threads,
        maxcore_mb=math.ceil(config.memory_mb / config.threads),
    )
    directory.mkdir(parents=True, exist_ok=False)
    input_payload = {
        "configuration": config.model_dump(mode="json"), "elements": list(elements),
        "nuclides": list(nuclear_identity.nuclides), "nuclear_identity": nuclear_identity.metadata,
        "coordinates_angstrom": [list(xyz) for xyz in coordinates],
        "charge": charge, "multiplicity": multiplicity,
    }
    input_path = directory / "t9_input.json"
    _write_json(input_path, input_payload)
    from dataclasses import asdict
    _write_json(directory / "execution_authority.json", asdict(authorization))
    _write_json(directory / "rejected_single_reference.json", {
        "status": "REJECTED", "exception_type": type(trigger).__name__,
        "error": str(trigger), "details": trigger.details,
        "recovery_geometry": "original_input", "routing_tier": "T9",
    })
    worker = directory / "t9_worker.py"
    shutil.copyfile(Path(__file__).with_name("t9_worker.py"), worker)
    started = time.monotonic()
    result = safe_subprocess_run(
        [str(config.python_executable), "-I", str(worker), str(input_path)],
        cwd=directory, timeout=config.timeout_seconds, check=False,
        capture_output=True, text=True, required_disk_gb=0.1,
        env={**os.environ, "OMP_NUM_THREADS": str(config.threads),
             "MKL_NUM_THREADS": str(config.threads), "OPENBLAS_NUM_THREADS": str(config.threads)},
        cancellation_event=cancellation_event,
        cpu_affinity=list(authorization.cpu_affinity) or None,
    )
    (directory / "stdout.log").write_text(result.stdout or "", encoding="utf-8")
    (directory / "stderr.log").write_text(result.stderr or "", encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"T9 {config.method} failed (exit {result.returncode}); evidence retained in {directory}")
    payload = json.loads((directory / "t9_result.json").read_text(encoding="utf-8"))
    if payload.get("scf_converged") is not True or payload.get("casscf_converged") is not True:
        raise RuntimeError("T9 recovery did not establish SCF and CASSCF convergence")
    if payload.get("input_sha256") != hashlib.sha256(input_path.read_bytes()).hexdigest():
        raise RuntimeError("T9 result does not match the submitted calculation")
    if payload.get("method") != config.method or payload.get("pyscf_version") != config.pyscf_version:
        raise RuntimeError("T9 result has unexpected method or engine version")
    for key in ("energy_hartree", "casscf_energy_hartree", "spin_square"):
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise RuntimeError(f"T9 result is missing finite {key}")
    if config.method == "NEVPT2":
        correction = payload.get("nevpt2_correction_hartree")
        if isinstance(correction, bool) or not isinstance(correction, (float, int)) or not math.isfinite(correction):
            raise RuntimeError("NEVPT2 must return a finite measured correlation correction")
        if not math.isclose(payload["energy_hartree"], payload["casscf_energy_hartree"] + correction, abs_tol=1e-12):
            raise RuntimeError("NEVPT2 total energy does not match its computed components")
    ElectronicSanitizer.diagnose_spin_contamination(payload["spin_square"], multiplicity)
    payload.update(status="T9_FALLBACK_VERIFIED", tier="T9", operation="single_point",
                   wall_seconds=time.monotonic() - started,
                   worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest())
    from cochem_base.core_engine.scientific_telemetry import append_scientific_result
    telemetry_id = f"t9_{uuid.uuid4().hex}"
    telemetry_path = append_scientific_result(
        telemetry_id, nuclear_identity.nuclides, coordinates, payload["energy_hartree"],
        metadata={"engine": "pyscf", "method": config.method, "tier": "T9",
                  "operation": "single_point", "spin_square": payload["spin_square"],
                  "input_sha256": payload["input_sha256"], "scf_converged": True, "casscf_converged": True},
    )
    payload.update(telemetry_path=str(telemetry_path), telemetry_job_id=telemetry_id,
                   nuclides=list(nuclear_identity.nuclides), nuclear_identity=nuclear_identity.metadata)
    _write_json(directory / "t9_verified.json", payload)
    return payload


def execute_with_t9_fallback(
    primary: Callable[[], Any], config: T9FallbackConfig | None, **kwargs: Any,
) -> dict[str, Any] | None:
    """Only a typed contamination failure invokes multireference recovery."""
    try:
        primary()
    except SpinContaminationError as exc:
        if config is None:
            # The typed failure is preserved; absence of scientific input is not success.
            raise
        try:
            return run_t9_fallback(config, trigger=exc, **kwargs)
        except Exception as recovery_error:
            details = {**(exc.details or {}), "fallback_status": "FAILED",
                       "fallback_error_type": type(recovery_error).__name__,
                       "fallback_error": str(recovery_error)}
            raise SpinContaminationError(
                "The single-reference result was rejected and configured T9 recovery failed.", details=details,
            ) from recovery_error
    return None
