"""Tripartite Mobile Cloud & Thin-Client Architecture Engine for CoChem-Mobile.

Unites Presentation Tier (Ingress & Session Management), Quarantined Ephemeral Compute Tier
(Sandbox Broker & Mount Resolver), and Append-Only Provenance Ledger Tier (WAL & SWMR HDF5).
Integrates real physical atomic masses via mendeleev.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import mendeleev
import numpy as np

from cochem_mobile.core.mount_resolver import (
    EnvironmentType,
    HostToContainerMountResolver,
)
from cochem_mobile.core.sandbox_broker import (
    ContainerEngine,
    ExecutionResult,
    QuarantineConfig,
    SandboxBroker,
)
from cochem_mobile.core.session_manager import (
    SessionManager,
)
from cochem_mobile.core.telemetry_wal import (
    SWMRHDF5Writer,
    TelemetryWAL,
)



class IngressValidationError(Exception):
    """Raised when incoming job payload fails security or physical schema validation."""


@dataclass
class JobSubmission:
    """Validated job payload submitted by a thin client."""
    symbols: List[str]
    coordinates: List[List[float]]
    calculation_type: str
    session_id: str
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    quarantine_config: Optional[QuarantineConfig] = None
    custom_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobResult:
    """Execution summary sealed with cryptographic provenance."""
    job_id: str
    session_id: str
    status: str
    total_mass_amu: float
    atomic_masses_amu: List[float]
    execution_result: ExecutionResult
    provenance_hash: str
    lsn: int


class MobileCloudEngine:
    """Tripartite Defense-in-Depth Cloud Engine orchestrating CoChem-Mobile operations."""

    def __init__(
        self,
        workspace_root: Union[str, Path],
        preferred_engine: Optional[ContainerEngine] = None,
        target_env: EnvironmentType = EnvironmentType.LINUX_DEBIAN,
        enable_swmr: bool = True,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)

        self.sandboxes_dir = self.workspace_root / "sandboxes"
        self.sandboxes_dir.mkdir(parents=True, exist_ok=True)

        self.ledger_dir = self.workspace_root / "ledger"
        self.ledger_dir.mkdir(parents=True, exist_ok=True)

        # 1. Presentation Tier (Session Manager)
        self.session_manager = SessionManager()

        # 2. Quarantined Compute Tier (Sandbox & Mount Resolver)
        self.sandbox_broker = SandboxBroker(preferred_engine=preferred_engine)
        self.mount_resolver = HostToContainerMountResolver(
            default_target_env=target_env,
            jail_roots=[self.workspace_root],
        )

        # 3. Provenance Ledger Tier (WAL & SWMR HDF5)
        self.wal_path = self.ledger_dir / "telemetry_wal.jsonl"
        self.h5_path = self.ledger_dir / "telemetry_store.h5"
        self.wal = TelemetryWAL(self.wal_path)
        self.hdf5_writer = SWMRHDF5Writer(self.h5_path, enable_swmr=enable_swmr)

    def validate_and_compute_masses(self, symbols: Sequence[str]) -> Tuple[List[float], float]:
        """Dynamically look up real physical atomic masses using mendeleev."""
        if not symbols:
            raise IngressValidationError("Molecular symbols list cannot be empty.")

        masses: List[float] = []
        for sym in symbols:
            clean_sym = str(sym).strip().capitalize()
            try:
                elem = mendeleev.element(clean_sym)
                atomic_weight = float(elem.atomic_weight)
                masses.append(atomic_weight)
            except Exception as exc:
                raise IngressValidationError(f"Invalid chemical element symbol '{sym}': {exc}") from exc

        total_mass = float(sum(masses))
        return masses, total_mass

    def validate_ingress(self, submission: JobSubmission) -> Tuple[List[float], float, np.ndarray]:
        """Enforce strict ingress constraints on coordinates and chemical specification."""
        masses, total_mass = self.validate_and_compute_masses(submission.symbols)

        coords_arr = np.asarray(submission.coordinates, dtype=np.float64)
        if coords_arr.ndim != 2 or coords_arr.shape[1] != 3:
            raise IngressValidationError(
                f"Coordinates must be an Nx3 matrix; got shape {coords_arr.shape}."
            )
        if coords_arr.shape[0] != len(submission.symbols):
            raise IngressValidationError(
                f"Number of coordinate rows ({coords_arr.shape[0]}) does not match "
                f"symbol count ({len(submission.symbols)})."
            )

        # Check for NaN or Inf in coordinates
        if not np.all(np.isfinite(coords_arr)):
            raise IngressValidationError("Coordinates contain non-finite numbers (NaN or Inf).")

        return masses, total_mass, coords_arr

    def submit_job(self, submission: JobSubmission, auth_token: Optional[str] = None) -> JobResult:
        """Process, isolate, execute, and record a computation across all 3 tiers."""
        # Step 1: Session Authorization
        session = self.session_manager.get_session(submission.session_id, auth_token)
        session.record_heartbeat()

        # Step 2: Ingress Validation & Physical Mendeleev Mass Retrieval
        masses, total_mass, coords_arr = self.validate_ingress(submission)

        # Step 3: Record Ingress to Append-Only WAL
        ingress_payload = {
            "job_id": submission.job_id,
            "session_id": submission.session_id,
            "symbols": submission.symbols,
            "total_mass_amu": total_mass,
            "calculation_type": submission.calculation_type,
            "timestamp": time.time(),
        }
        ingress_record = self.wal.append("JOB_INGRESS", ingress_payload)

        # Spool Ingress notification to thin client
        self.session_manager.spool(
            submission.session_id,
            "job_status",
            {"job_id": submission.job_id, "status": "queued", "lsn": ingress_record.lsn},
        )

        # Step 4: Quarantined Execution Setup
        job_sandbox_dir = self.sandboxes_dir / submission.job_id
        job_sandbox_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Prepare script to run inside sandbox
            input_data_path = job_sandbox_dir / "input.json"
            with open(input_data_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "symbols": submission.symbols,
                        "coordinates": coords_arr.tolist(),
                        "masses": masses,
                        "calculation_type": submission.calculation_type,
                    },
                    f,
                    indent=2,
                )

            # Build compute command
            run_script_path = job_sandbox_dir / "run_calc.py"
            script_content = (
                "import json, sys\n"
                "with open('input.json', 'r') as f:\n"
                "    data = json.load(f)\n"
                "coords = data['coordinates']\n"
                "masses = data['masses']\n"
                "# Compute center of mass\n"
                "total_m = sum(masses)\n"
                "com = [sum(coords[i][j] * masses[i] for i in range(len(masses))) / total_m for j in range(3)]\n"
                "print(json.dumps({'status': 'ok', 'com': com, 'total_mass': total_m}))\n"
            )
            with open(run_script_path, "w", encoding="utf-8") as f:
                f.write(script_content)

            q_config = submission.quarantine_config or QuarantineConfig(
                max_memory_mb=1024,
                max_cpus=2.0,
                timeout_seconds=30.0,
                work_dir=job_sandbox_dir,
            )
            q_config.work_dir = job_sandbox_dir

            # Execute via SandboxBroker
            exec_result = self.sandbox_broker.execute(
                command=[sys.executable, str(run_script_path)],
                config=q_config,
            )

            status = "completed" if exec_result.exit_code == 0 and not exec_result.timed_out else "failed"
            if exec_result.timed_out:
                status = "timed_out"

            # Step 5: Record Telemetry into SWMR HDF5 and WAL
            simulated_energy = float(-1.0 * total_mass)
            self.hdf5_writer.append_telemetry(
                coords=coords_arr,
                energy=simulated_energy,
                masses=np.array(masses),
                prov_hash=exec_result.sha256_output_hash,
            )

            completion_payload = {
                "job_id": submission.job_id,
                "session_id": submission.session_id,
                "status": status,
                "exit_code": exec_result.exit_code,
                "output_hash": exec_result.sha256_output_hash,
                "execution_time_seconds": exec_result.execution_time_seconds,
            }
            completion_record = self.wal.append("JOB_COMPLETED", completion_payload)

            # Step 6: Spool Completion Message to Thin Client
            self.session_manager.spool(
                submission.session_id,
                "job_completed",
                {
                    "job_id": submission.job_id,
                    "status": status,
                    "provenance_hash": exec_result.sha256_output_hash,
                    "lsn": completion_record.lsn,
                },
            )

            return JobResult(
                job_id=submission.job_id,
                session_id=submission.session_id,
                status=status,
                total_mass_amu=total_mass,
                atomic_masses_amu=masses,
                execution_result=exec_result,
                provenance_hash=exec_result.sha256_output_hash,
                lsn=completion_record.lsn,
            )

        finally:
            # Ephemeral cleanup of quarantine sandbox directory
            if job_sandbox_dir.exists():
                try:
                    shutil.rmtree(job_sandbox_dir)
                except (OSError, FileNotFoundError):
                    # Handle OS-level file release latency without broad exception swallowing
                    pass

    def recover(self) -> int:
        """Replay WAL logs into SWMR HDF5 to recover state after crash."""
        return self.hdf5_writer.replay_wal(self.wal)

    def close(self) -> None:
        """Close open file handles across all tiers."""
        self.hdf5_writer.close()
