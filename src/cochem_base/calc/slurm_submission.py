"""Validated single-node Slurm staging and canonical BASE execution.

Staging is input validation, not scheduler or chemistry acceptance. Each compute
job performs its own Stage 0 audit before invoking the native calculation service.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any

SLURM_PARAM_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.:@/]+$")
SLURM_WALLTIME_REGEX = re.compile(r"^(?:(\d+)-)?(\d{1,2}):(\d{2}):(\d{2})$")


def sanitize_slurm_parameter(param_name: str, value: str) -> str:
    cleaned = str(value).strip()
    if not cleaned or not SLURM_PARAM_REGEX.fullmatch(cleaned):
        raise ValueError(f"Shell injection detected in {param_name}: expected one valid Slurm parameter")
    return cleaned


def validate_slurm_walltime(walltime_str: str) -> str:
    value = walltime_str.strip()
    match = SLURM_WALLTIME_REGEX.fullmatch(value)
    if not match:
        raise ValueError("Invalid walltime format; expected [days-]hours:minutes:seconds")
    days, hours, minutes, seconds = match.groups()
    if int(minutes) >= 60 or int(seconds) >= 60 or days is not None and int(hours) >= 24:
        raise ValueError("Invalid walltime component bounds")
    total = int(days or 0) * 86400 + int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    if total <= 0:
        raise ValueError("Walltime must be strictly greater than zero")
    if total > 48 * 3600:
        raise ValueError("Walltime exceeds maximum allowable limit of 48:00:00")
    return value


def memory_megabytes(value: str) -> int:
    match = re.fullmatch(r"([1-9][0-9]*)(M(?:i?B)?|G(?:i?B)?)", str(value), re.I)
    if not match:
        raise ValueError("Memory must be a positive integer with MB or GB units")
    return int(match[1]) * (1024 if match[2].upper().startswith("G") else 1)


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    from cochem_base.core.cochem_core_registry_manager import atomic_write_json
    atomic_write_json(path, data)


def _load_manifest(path: Path) -> dict[str, Any]:
    path = path.resolve(strict=True)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "cochem.slurm-job/1":
        raise ValueError("Unknown Slurm job manifest")
    for name, record in manifest["inputs"].items():
        candidate = path.parent / name
        if (Path(name).is_absolute() or ".." in Path(name).parts or candidate.is_symlink()
                or not candidate.resolve(strict=True).is_relative_to(path.parent)
                or _sha256(candidate) != record["sha256"]):
            raise ValueError("Staged Slurm scientific inputs were altered or escaped their package")
    return manifest


def stage_calculation(
    config: dict[str, Any], destination: Path, *, registry_path: Path | None = None,
    job_name: str = "cochem_job", partition: str = "standard", nodes: int = 1,
    ntasks_per_node: int = 1, cpus_per_task: int = 1, mem: str = "1GB",
    walltime: str = "04:00:00", email: str | None = None,
) -> Path:
    """Stage validated scientific input and a declared future allocation.

    A submitting login node's hardware is not the compute-node resource budget.
    The executable and full deck receive fresh authority inside the allocation.
    """
    from cochem_base.calc.calculation_service import CalculationMatrixConfig, _external_run_path, parse_run_geometry
    from cochem_base.calc.molecular_input import build_molecular_input
    from cochem_base.calc.xtb_execution import validate_xtb_config
    from cochem_base.calc.slurm_generator import SlurmGenerator, SlurmSubmissionSpec
    from cochem_base.config_loader import resolve_config_path
    from cochem_base.core.cochem_core_registry_manager import load_system_config
    from cochem_base.interfaces.scientific_jobs import calculation_capability, validate_job_configuration

    if type(nodes) is not int or nodes != 1:
        raise ValueError("BASE Slurm jobs require exactly one node; MPI ranks share the audited node")
    if any(type(value) is not int or value < 1 for value in (ntasks_per_node, cpus_per_task)):
        raise ValueError("Slurm CPU requests must be positive integers")
    cores = ntasks_per_node * cpus_per_task
    walltime = validate_slurm_walltime(walltime)
    memory_mb = memory_megabytes(mem)
    model = CalculationMatrixConfig.model_validate(config)
    validate_job_configuration(model)
    if calculation_capability(model).adapter_status != "connected" or model.engine not in {"orca", "xtb", "pyscf"}:
        raise ValueError("This Slurm path requires a connected native molecular execution adapter")
    if any(getattr(model, field) is not None for field in ("hessian_file", "r2_reference_manifest", "t9_fallback", "periodic")):
        raise ValueError("Stage external scientific dependencies through their ecosystem workflow before Slurm execution")
    if model.engine in {"orca", "pyscf"}:
        build_molecular_input(model, basin_id="slurm_input_validation")
    else:
        elements, _ = parse_run_geometry(model.geometry)
        validate_xtb_config(model, elements)
    registry_path = resolve_config_path(registry_path)
    registry = load_system_config(registry_path)
    if registry.stage0 is None:
        raise ValueError("Complete eleven-phase Stage 0 authority is required before Slurm staging")
    maxcore_mb = int(memory_mb * 0.75) // cores
    if maxcore_mb < 1:
        raise ValueError("The requested memory must provide at least 1 MB per process")
    destination = _external_run_path(destination)
    spec = SlurmSubmissionSpec(job_name=job_name, partition=partition, cores=cores, mem_mb=memory_mb,
                               walltime=walltime, solver=model.engine,
                               scratch_dir=str(destination / "runtime"), artifact_dir=str(destination / "results"))
    if email is not None:
        email = sanitize_slurm_parameter("email", email)
    destination.mkdir(parents=True, exist_ok=False)
    config_file = destination / "calculation.json"
    _write_json(config_file, model.model_dump(mode="json"))
    inputs = {"calculation.json": {"sha256": _sha256(config_file)}}
    manifest = {"schema_version": "cochem.slurm-job/1", "status": "STAGED_INPUT_ONLY",
                "scientific_execution_performed": False, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "job_name": job_name, "partition": partition, "engine": model.engine, "cores": cores,
                "maxcore_mb": maxcore_mb, "memory_mb": memory_mb, "inputs": inputs,
                "registry_path": str(registry_path), "registry_sha256": _sha256(registry_path),
                "allocation_authority": "declared_request_only; compute-node Stage 0 required",
                "deck_generation": "deferred_until_compute_node_authorization",
                "runtime": str(destination / "runtime"), "results": str(destination / "results")}
    manifest_path = destination / "job_manifest.json"
    _write_json(manifest_path, manifest)
    argv = [sys.executable, "-m", "cochem_base.calc.slurm_submission", "--manifest", str(manifest_path)]
    payload = shlex.join(argv) + " > " + shlex.quote(str(destination / "execution.stdout.log")) + " 2> " + shlex.quote(str(destination / "execution.stderr.log"))
    script = SlurmGenerator().generate_submission_script(spec, payload_command=payload,
                                                         configure_fabric=False, copy_scratch=False, clamp_to_host=False)
    output_prefix = str(destination).replace("%", "%%")
    scheduler_logs = (f"\n#SBATCH --output={shlex.quote(output_prefix + '/scheduler-%j.stdout.log')}"
                      f"\n#SBATCH --error={shlex.quote(output_prefix + '/scheduler-%j.stderr.log')}")
    if email:
        scheduler_logs += f"\n#SBATCH --mail-user={email}\n#SBATCH --mail-type=END,FAIL"
    script = script.replace("\n\n", scheduler_logs + "\n\n", 1)
    script = script.replace("set -euo pipefail", "set -euo pipefail\n"
        ': "${SLURM_JOB_ID:?A real Slurm allocation is required; no local fallback is performed}"', 1)
    script_path = destination / "submit.sh"
    script_path.write_text(script, encoding="utf-8")
    _write_json(destination / "script-integrity.json", {"sha256": _sha256(script_path), "manifest_sha256": _sha256(manifest_path)})
    return script_path


def submit_slurm_job(script_path: Path) -> str:
    """Submit only the reviewed staged script; acceptance remains separate."""
    from cochem_base.core.cochem_core_registry_manager import load_system_config

    script_path = Path(script_path).resolve(strict=True)
    manifest_path = script_path.parent / "job_manifest.json"
    manifest = _load_manifest(manifest_path)
    integrity = json.loads((script_path.parent / "script-integrity.json").read_text())
    if _sha256(script_path) != integrity["sha256"] or _sha256(manifest_path) != integrity["manifest_sha256"]:
        raise ValueError("The staged Slurm script or manifest changed after validation")
    registry_path = Path(manifest["registry_path"])
    if _sha256(registry_path) != manifest["registry_sha256"]:
        raise ValueError("Submitting registry changed after Slurm staging; stage a fresh job")
    registry = load_system_config(registry_path)
    if registry.hpc.scheduler != "slurm":
        return f"PENDING_CLUSTER_CONFIGURATION: Validated inputs are staged at {script_path.parent}; configure and audit Slurm before submission."
    sbatch = shutil.which("sbatch")
    if sbatch is None:
        return f"PENDING_CLUSTER_CONFIGURATION: Validated inputs are staged at {script_path.parent}; sbatch is unavailable."
    completed = subprocess.run([sbatch, "--parsable", str(script_path)], capture_output=True, text=True, check=False, timeout=30)
    (script_path.parent / "submission.stdout.log").write_text(completed.stdout or "")
    (script_path.parent / "submission.stderr.log").write_text(completed.stderr or "")
    if completed.returncode != 0:
        raise RuntimeError(f"sbatch failed with exit code {completed.returncode}; submission diagnostics retained")
    match = re.fullmatch(r"([0-9]+)(?:;[A-Za-z0-9_.-]+)?\s*", completed.stdout)
    if not match:
        raise RuntimeError("sbatch did not return a valid job identifier; no submission success is claimed")
    _write_json(script_path.parent / "submission.json", {"status": "SUBMITTED", "job_id": match[1],
                "scientific_execution_performed": False, "script_sha256": integrity["sha256"]})
    return match[1]


def execute_staged_calculation(manifest_path: Path, *, validate_only: bool = False) -> dict[str, Any]:
    """Reaudit the allocated compute node and run the staged canonical calculation."""
    from cochem_base.calc.calculation_service import run_calculation
    from cochem_base.core_engine.execution_authority import authorize_engine_execution
    from cochem_base.core.cochem_core_registry_manager import load_system_config
    from cochem_base.orchestrator.bootstrap_service import run_setup

    manifest_path = manifest_path.resolve(strict=True)
    manifest = _load_manifest(manifest_path)
    registry = Path(manifest["registry_path"])
    if _sha256(registry) != manifest["registry_sha256"]:
        raise ValueError("Submitting registry changed after Slurm staging; stage a fresh job")
    submitting_registry = load_system_config(registry)
    if validate_only:
        # The planned allocation is explicitly unmeasured until the scheduler
        # supplies a compute node. This is not an engine-execution permit.
        from cochem_base.calc.calculation_service import CalculationMatrixConfig
        from cochem_base.interfaces.scientific_jobs import validate_job_configuration
        config = CalculationMatrixConfig.model_validate_json((manifest_path.parent / "calculation.json").read_text())
        validate_job_configuration(config)
        return {"status": "VALIDATED_INPUT_ONLY", "scientific_execution_performed": False,
                "allocation_authority": manifest["allocation_authority"]}
    if submitting_registry.hpc.scheduler != "slurm":
        raise RuntimeError("The registry does not configure Slurm; no local fallback is performed")
    if not re.fullmatch(r"[0-9]+", os.environ.get("SLURM_JOB_ID", "")):
        raise RuntimeError("A real Slurm allocation is required; no local fallback is performed")
    allocated = os.environ.get("SLURM_CPUS_PER_TASK", "")
    if not allocated.isdigit() or int(allocated) < manifest["cores"]:
        raise RuntimeError("Slurm CPU allocation is smaller than the validated job request")
    runtime = Path(manifest["runtime"])
    runtime.mkdir(parents=True, exist_ok=True)
    artifact_dir = runtime / ("allocation-" + os.environ["SLURM_JOB_ID"])
    if artifact_dir.exists():
        raise FileExistsError("Slurm allocation evidence already exists; use a fresh staged job")
    artifact_dir.mkdir()
    os.environ.update(COCHEM_ARTIFACT_DIR=str(artifact_dir), COCHEM_ARTIFACTS=str(artifact_dir),
                      COCHEM_CONFIG=str(artifact_dir / "Registry/cochem_system_config.json"))
    report: dict[str, Any] = {"status": "failed", "scientific_execution_performed": False,
                              "slurm_job_id": os.environ["SLURM_JOB_ID"]}
    try:
        setup = run_setup(artifact_dir, skip_heavy=True)
        report["setup"] = setup
        registry = Path(os.environ["COCHEM_CONFIG"])
        node_authority = authorize_engine_execution(manifest["engine"], registry_path=registry,
                            cores=manifest["cores"], maxcore_mb=manifest["maxcore_mb"])
        report.update(engine_path=node_authority.executable, engine_sha256=node_authority.binary_sha256,
                      allocation_authority="measured_compute_node", registry_path=str(registry))
        result = run_calculation(manifest_path.parent / "calculation.json", registry_path=registry,
                                 threads=manifest["cores"], maxcore_mb=manifest["maxcore_mb"], device="cpu",
                                 scratch=artifact_dir / "Scratch", output=Path(manifest["results"]) / "calculation")
        report["execution"] = result
        if result["status"] != "EXECUTION_VERIFIED":
            raise RuntimeError("The scheduled scientific operation did not complete")
        report.update(status="passed", scientific_execution_performed=True)
        return report
    except Exception as error:
        report.update(error=str(error), error_type=type(error).__name__)
        raise
    finally:
        _write_json(manifest_path.parent / "calculation-report.json", report)


class SlurmSubmissionController:
    def __init__(self, default_partition: str = "standard") -> None:
        self.default_partition = default_partition
        self.last_submitted_job_id: str | None = None

    def stage_calculation(self, config: dict[str, Any], destination: Path, **kwargs: Any) -> Path:
        kwargs.setdefault("partition", self.default_partition)
        return stage_calculation(config, destination, **kwargs)

    def validate_and_generate(self, **kwargs: Any) -> str:
        return generate_slurm_script(**kwargs)

    def dispatch(self, script_path: Path) -> str:
        result = submit_slurm_job(script_path)
        self.last_submitted_job_id = result if result.isdigit() else None
        return result


def generate_slurm_script(*, config_path: str | Path | None = None,
                          staging_dir: str | Path | None = None, **kwargs: Any) -> str:
    """Compatibility entry point requiring a real validated configuration package."""
    if config_path is None or staging_dir is None:
        raise ValueError("Slurm generation requires config_path JSON and an external staging_dir; raw unstaged input decks are not accepted")
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    script = stage_calculation(config, Path(staging_dir), **kwargs)
    return script.read_text(encoding="utf-8")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(execute_staged_calculation(args.manifest, validate_only=args.validate_only), indent=2))
        return 0
    except Exception as error:
        print(f"Slurm calculation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
