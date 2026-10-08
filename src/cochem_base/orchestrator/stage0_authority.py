"""Publish the Golden Registry only after one complete, measured Stage 0 run."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

from cochem_base.cochem_core_registry_schema import (
    CoChemSystemConfig,
    EngineInfo,
    EnvironmentSchema,
    HardwareSchema,
    SiloConfig,
    SiloPathsSchema,
    Stage0Authority,
    Stage0PhaseEvidence,
    MicroSiloAuthority,
)
from cochem_base.core.cochem_core_registry_manager import save_system_config
from cochem_base.core_engine.hardware_profiler import profile_hardware
from cochem_base.orchestrator.micro_silo_manager import verify_micro_silo
from cochem_base.orchestrator.silo_dependency_pins import DEFAULT_PINS


class Stage0AuthorityError(RuntimeError):
    """The observed setup evidence is incomplete or cannot authorize execution."""


def build_stage0_authority(summary: dict[str, Any]) -> CoChemSystemConfig:
    """Aggregate reports from this invocation, never unrelated historic files.

    Revalidate executable digests and dependency locks at the publication boundary.
    Absent optional engines and accelerators stay explicitly unavailable.
    """
    if summary.get("dry_run"):
        raise Stage0AuthorityError("A dry run cannot publish execution authority")
    entries = summary.get("phases_executed", [])
    numbers = [entry["phase_number"] for entry in entries]
    if sorted(numbers) != list(range(1, 12)):
        raise Stage0AuthorityError("All eleven current phase reports are required")
    reports = {entry["phase_number"]: entry["report"] for entry in entries}
    evidence = []
    for entry in entries:
        report = entry["report"]
        if entry["status"] not in {"PASSED", "DEGRADED"} or report.get("errors"):
            raise Stage0AuthorityError(f"Phase {entry['phase_number']} has unresolved audit errors")
        if str(report.get("status")) != entry["status"]:
            raise Stage0AuthorityError("Phase summary disagrees with its report")
        evidence.append(
            Stage0PhaseEvidence(
                phase_number=entry["phase_number"],
                status=entry["status"],
                sha256=hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest(),
            )
        )
    root = Path(summary["artifact_dir"]).resolve()
    from cochem.core.context import assert_writable_path

    assert_writable_path(root)
    profile = profile_hardware()
    p2, p11 = reports[2], reports[11]
    quota = p2.get("cpu", {}).get("cgroup_effective_cpus")
    cores = profile.allocatable_compute_cores
    if quota is not None:
        if not math.isfinite(float(quota)) or float(quota) <= 0:
            raise Stage0AuthorityError("Invalid CPU quota observation")
        cores = min(cores, max(1, math.floor(float(quota))))
    memory = p11.get("host_memory", {}).get("bounded_total_ram_mb")
    if memory is None or not math.isfinite(float(memory)) or float(memory) <= 0:
        raise Stage0AuthorityError("Phase 11 omitted measured bounded RAM")
    ram_gb = min(profile.allocatable_ram_bytes / 1024**3, float(memory) / 1024)
    maxcore = int(ram_gb * 1024 / cores * 0.75)
    hardware = HardwareSchema(
        ram_gb=ram_gb,
        cpu_physical_cores=profile.physical_cores,
        physical_cpu_cores=profile.physical_cores,
        logical_cpu_cores=profile.logical_cores,
        allocatable_compute_cores=cores,
        maxcore_mb=maxcore,
        audited_cpu_ids=list(profile.available_cpu_ids),
        numa_cpu_ids={
            str(n["node_id"]): n["cpu_core_ids"]
            for n in p11.get("numa_profile", {}).get("numa_nodes", [])
        },
        avx_512_capable=profile.avx512 is True,
        vram_gb=(profile.vram_bytes or 0) / 1024**3,
        gpu_profile="NVIDIA" if profile.gpu_probe_status == "measured" else "Unavailable",
        os_target=profile.environment.os_target,
    )
    capabilities = {
        "cuda": reports[5].get("is_cuda_available") is True,
        "mps": reports[5].get("mps_daemon", {}).get("is_daemon_active") is True,
        "hdf5_swmr": reports[6].get("swmr_audit", {}).get("swmr_supported") is True,
        "alignment": reports[10].get("alignment_engine_ready") is True,
    }
    engines = {}
    silo_paths = {}
    for name, record in reports[3].get("engines", {}).items():
        available = record.get("is_available") is True
        path = record.get("path")
        if available:
            if (
                not path
                or not Path(path).is_absolute()
                or not Path(path).is_file()
                or not os.access(path, os.X_OK)
            ):
                raise Stage0AuthorityError(f"Audited executable is no longer available: {name}")
            with Path(path).open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            if digest != record.get("sha256_hash"):
                raise Stage0AuthorityError(f"Audited executable changed since phase 3: {name}")
            if name in {"xcfour", "cfour"}:
                from cochem_base.core_engine.cfour_runtime import verify_cfour_runtime
                runtime = verify_cfour_runtime(path)
                if runtime["runtime_seal_sha256"] != record.get("runtime_seal_sha256"):
                    raise Stage0AuthorityError("CFOUR runtime changed since phase 3")
        else:
            path = None
            digest = None
        canonical = "cfour" if name == "xcfour" else name
        engines[canonical] = EngineInfo(
            status="found" if available else "missing",
            path=path,
            version=record.get("version") if available else None,
            hash=digest,
            track=record.get("track"),
            runtime_seal_sha256=record.get("runtime_seal_sha256") if available else None,
            runtime_metadata=record.get("runtime_metadata", {}) if available else {},
        )
        capabilities[canonical] = available
        if canonical in {"orca", "cfour", "xtb", "mpirun"}:
            silo_paths[f"{canonical}_binary_path"] = path
    silos = {}
    lock_groups = {
        "cochem_core_silo": "core",
        "cochem_ui_silo": "ui",
        "cochem_calc_silo": "calc",
        "cochem_mace_silo": "mace",
    }
    for name, record in reports[4].get("silos", {}).items():
        capabilities[name] = record.get("is_available") is True
        if not capabilities[name]:
            continue
        if name not in lock_groups:
            raise Stage0AuthorityError(f"No exact dependency lock is defined for {name}")
        checked = verify_micro_silo(
            record["path"],
            python_version=record["python_version"],
            requirements=DEFAULT_PINS[lock_groups[name]],
        )
        silos[name] = MicroSiloAuthority(
            root=record["path"],
            python_executable=record["python_executable"],
            python_version=checked["python_version"],
            packages=checked["packages"],
        )
    # Python engine records retain the silo launcher path rather than resolving
    # its symlink to the host interpreter. Package pins remain in Stage 0 evidence.
    for engine_name, silo_name, package in [
        ("pyscf", "cochem_calc_silo", "pyscf"),
        ("mace", "cochem_mace_silo", "mace-torch"),
    ]:
        silo = silos.get(silo_name)
        capabilities[engine_name] = silo is not None
        if silo is not None:
            with Path(silo.python_executable).open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            engines[engine_name] = EngineInfo(
                status="found",
                path=silo.python_executable,
                version=silo.packages[package],
                hash=digest,
                track=silo_name,
            )
        else:
            engines[engine_name] = EngineInfo(status="missing")
    if not capabilities.get("cochem_core_silo") or not capabilities["hdf5_swmr"]:
        raise Stage0AuthorityError("Core interpreter isolation and HDF5 SWMR are mandatory")
    unavailable = sorted(name for name, available in capabilities.items() if not available)
    storage = reports[6].get("storage_paths", {})
    silo_paths["hdf5_pes_store_path"] = storage.get("runtime_active_db_path")
    injected = {}
    for number in [7, 8, 9, 10, 11]:
        injected.update(reports[number].get("injected_env_vars", {}))
    # Runtime authority is bounded by the measured allocation, regardless of
    # legacy stage-specific recommendations for larger physical hosts.
    injected.update(
        {
            "OMP_NUM_THREADS": str(cores),
            "MKL_NUM_THREADS": str(cores),
            "OPENBLAS_NUM_THREADS": str(cores),
        }
    )
    cfg = CoChemSystemConfig(
        status="DEGRADED_OPERATIONAL"
        if unavailable or any(e.status == "DEGRADED" for e in evidence)
        else "LOCKED",
        hardware=hardware,
        execution={"cpu_allocation": {
            "policy": profile.cpu_allocation_policy.value,
            "budget_unit": profile.cpu_allocation_policy.budget_unit,
            "allocatable_process_slots": cores,
            "physical_cores": profile.physical_cores,
            "logical_cores": profile.logical_cores,
            "audited_cpu_ids": list(profile.available_cpu_ids),
            "cgroup_effective_cpus": quota,
        }},
        engines=engines,
        orca_version=engines.get("orca").version if engines.get("orca") else None,
        environment=EnvironmentSchema(
            os_target=profile.environment.os_target,
            artifacts_dir=str(root),
            scratch_dir=str(root / "Scratch"),
            codata_version="2022",
            env_vars=injected,
            strict_path_resolution=True,
        ),
        silo_paths=SiloPathsSchema(**silo_paths, strict_resolution=True),
        silos=SiloConfig(
            gpu_silo_active=capabilities["cuda"] and capabilities.get("cochem_mace_silo", False)
        ),
        alignment_engine_ready=capabilities["alignment"],
        stage0=Stage0Authority(
            completed_at=datetime.now(timezone.utc).isoformat(),
            phases=evidence,
            micro_silos=silos,
            capabilities=capabilities,
            unavailable_capabilities=unavailable,
        ),
    )
    cfg.update_checksum()
    return cfg


def publish_stage0_authority(summary: dict[str, Any]) -> CoChemSystemConfig:
    config = build_stage0_authority(summary)
    path = Path(summary["artifact_dir"]).resolve() / "Registry" / "cochem_system_config.json"
    save_system_config(config, path)
    path.chmod(0o444)
    return config
