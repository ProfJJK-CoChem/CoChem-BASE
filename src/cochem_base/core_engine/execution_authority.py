"""Bind scientific engine commands and resource requests to Golden Registry evidence."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
from typing import Sequence

from filelock import FileLock


class RegistryAuthorityViolationError(RuntimeError):
    """A scientific execution contradicts or lacks audited registry authority."""


@dataclass(frozen=True)
class ExecutionAuthorization:
    engine: str
    executable: str
    cores: int
    maxcore_mb: int
    total_memory_mb: int
    registry_path: str
    binary_sha256: str
    cpu_affinity: tuple[int, ...] = ()
    cpu_budget_unit: str = "physical_core"
    runtime_seal_sha256: str | None = None

    def command(self, arguments: Sequence[str] = ()) -> list[str]:
        return [self.executable, *arguments]


def authorize_engine_execution(
    engine: str,
    *,
    registry_path: str | Path | None = None,
    executable: str | Path | None = None,
    command: Sequence[str] | None = None,
    cores: int | None = None,
    maxcore_mb: int | None = None,
) -> ExecutionAuthorization:
    """Require the audited executable itself and bounded resources.

    Generic subprocess jobs do not call this scientific-engine gate. An explicit
    engine identity cannot be attached to Python/shell/wrapper commands instead
    of that engine. MPI launchers require their own separately audited adapter.
    """
    from cochem_base.config_loader import resolve_config_path
    from cochem_base.cochem_core_registry_schema import CoChemSystemConfig

    path = resolve_config_path(registry_path)
    try:
        with FileLock(str(path) + ".lock", timeout=10):
            config = CoChemSystemConfig.model_validate_json(path.read_text(encoding="utf-8"))
        if config.status not in {"LOCKED", "ACTIVE", "PASSED", "DEGRADED_OPERATIONAL"}:
            raise ValueError(f"Registry status {config.status!r} does not authorize execution")
        if not config.verify_checksum():
            raise ValueError("Missing or invalid Golden Registry checksum")
        raw = config.model_dump(mode="json")
        name = engine.lower()
        record = raw.get("engines", {}).get(name)
        if not isinstance(record, dict) or record.get("status") not in {"found", "ready"}:
            raise ValueError(f"Engine {name!r} is not available in the Golden Registry")
        audited = record.get("path")
        if not audited or not Path(audited).is_absolute():
            raise ValueError("Engine requires an audited absolute executable path")
        binary = Path(audited)
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise ValueError(f"Audited executable is unavailable: {binary}")
        with binary.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if not record.get("hash") or digest != record["hash"]:
            raise ValueError("Engine executable does not match its audited SHA-256 digest")
        native_components = record.get("native_components", {})
        if name == "psi4" and not native_components:
            raise ValueError("Psi4 requires a successful native compiled-core audit, not launcher metadata alone")
        for component, expected in native_components.items():
            component_path = Path(component)
            if not component_path.is_absolute() or not component_path.is_file():
                raise ValueError("Audited native engine component is unavailable")
            with component_path.open("rb") as handle:
                if hashlib.file_digest(handle, "sha256").hexdigest() != expected:
                    raise ValueError("Native engine component does not match its audited SHA-256 digest")
        requested = list(command) if command is not None else None
        if requested is not None:
            if not requested or any(
                not isinstance(item, str) or not item or "\0" in item for item in requested
            ):
                raise ValueError("Scientific command must be a nonempty argument vector")
            if (
                executable is not None
                and Path(executable).absolute() != Path(requested[0]).absolute()
            ):
                raise ValueError("Explicit executable and command disagree")
            executable = requested[0]
        if executable is not None:
            candidate = Path(executable)
            # Distinct venv launchers can resolve to the same host executable;
            # samefile() alone would permit escaping the audited interpreter silo.
            if (
                not candidate.is_absolute()
                or not candidate.is_file()
                or candidate.absolute() != binary.absolute()
            ):
                raise ValueError(f"Command executable contradicts audited {name} binary")
        if name == "cfour":
            from .cfour_runtime import verify_cfour_runtime
            runtime = verify_cfour_runtime(binary)
            if not record.get("runtime_seal_sha256"):
                raise ValueError("CFOUR runtime lacks complete Stage 0 authority; repeat setup")
            if runtime["runtime_seal_sha256"] != record["runtime_seal_sha256"]:
                raise ValueError("CFOUR runtime no longer matches its Stage 0 integrity seal")
        if name in {"pyscf", "mace", "aimnet2"}:
            from cochem_base.orchestrator.micro_silo_manager import MicroSiloValidationError, verify_micro_silo
            silo_name = {"pyscf": "cochem_calc_silo", "mace": "cochem_mace_silo",
                         "aimnet2": "cochem_aimnet2_silo"}[name]
            silo = config.stage0.micro_silos.get(silo_name) if config.stage0 is not None else None
            if (silo is None or Path(silo.python_executable).absolute() != binary.absolute()
                    or record.get("track") != silo_name or not silo.packages):
                raise ValueError(f"{name.upper()} requires its complete matching Stage 0 micro-silo authority; repeat setup")
            imports = {"pyscf": ["pyscf", "numpy", "scipy"], "mace": ["mace", "torch", "numpy"],
                       "aimnet2": ["aimnet", "torch", "warp", "nvalchemiops"]}[name]
            try:
                verify_micro_silo(silo.root, python_version=silo.python_version,
                    requirements=[f"{package}=={version}" for package, version in sorted(silo.packages.items())], imports=imports)
            except MicroSiloValidationError as error:
                raise ValueError(f"{name.upper()} micro-silo no longer satisfies its audited isolation and dependency contract: {error}") from error
        hardware = config.hardware
        from .cpu_allocation import audited_cpu_capacity
        limit, budget_unit = audited_cpu_capacity(hardware.model_dump(), config.execution)
        if not isinstance(limit, int) or limit < 1:
            raise ValueError("No audited CPU allocation is available")
        requested_cores = limit if cores is None else cores
        if (
            isinstance(requested_cores, bool)
            or not isinstance(requested_cores, int)
            or not 1 <= requested_cores <= limit
        ):
            raise ValueError(f"Requested core count exceeds audited allocation ({limit})")
        ram = hardware.ram_gb * 1024
        if not math.isfinite(ram) or ram <= 0:
            raise ValueError("No audited RAM allocation is available")
        maximum = hardware.maxcore_mb
        if maximum is None or maximum <= 0:
            raise ValueError("No audited per-core memory budget is available")
        requested_memory = maximum if maxcore_mb is None else maxcore_mb
        if (
            isinstance(requested_memory, bool)
            or not isinstance(requested_memory, int)
            or not 1 <= requested_memory <= maximum
        ):
            raise ValueError(f"Requested per-core memory exceeds audited budget ({maximum} MB)")
        if requested_cores * requested_memory > ram:
            raise ValueError("Requested memory exceeds audited total RAM")
        affinity = tuple(hardware.audited_cpu_ids or ())
        if affinity:
            import psutil

            if hasattr(psutil.Process(), "cpu_affinity"):
                current = set(psutil.Process().cpu_affinity())
                if not set(affinity).issubset(current):
                    raise ValueError("The current CPU affinity contradicts the audited allocation")
            numa_groups = [
                tuple(cpu for cpu in node if cpu in affinity)
                for node in hardware.numa_cpu_ids.values()
            ]
            if numa_groups:
                fitting = [node for node in numa_groups if len(node) >= requested_cores]
                if not fitting:
                    raise ValueError("Requested cores cannot fit within one audited NUMA node")
                affinity = fitting[0]
            if len(affinity) < requested_cores:
                raise ValueError("Audited CPU identifiers do not cover the requested cores")
            affinity = affinity[:requested_cores]
        return ExecutionAuthorization(
            name,
            str(binary.absolute()),
            requested_cores,
            requested_memory,
            requested_memory * requested_cores,
            str(path),
            digest,
            affinity,
            budget_unit,
            runtime_seal_sha256=record.get("runtime_seal_sha256"),
        )
    except Exception as exc:
        if isinstance(exc, RegistryAuthorityViolationError):
            raise
        raise RegistryAuthorityViolationError(
            f"Execution authority denied by {path}: {exc}"
        ) from exc
