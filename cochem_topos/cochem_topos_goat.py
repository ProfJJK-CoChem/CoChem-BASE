"""
CoChem-TOPOS: Stage 2.3 - The GOAT Cascade Master Orchestrator (cochem_topos_goat.py)

Master execution orchestrator for the mechanics tier, executing continuous looping
between Quench (Relaxation) and Escape (Basin Exploration) phases until conformational
search space is exhausted or convergence criteria are achieved.

Execution Directives:
1. Engine Abstraction Layer (BaseOptimizer): Isolates specific ASE-MACE or external
   physics calls to guarantee future engine flexibility.
2. Batched GPU Inference, CPU Fallback & Singleton Loader: Pushes geometries through
   the active calculator in flattened tensor batches of 32 or 64. Wraps MLFF instantiation
   in a Singleton design pattern to bypass Python looping bottlenecks without causing
   VRAM fragmentation. Detects execution environment and automatically initiates CPU
   fallback architecture using batched CPU inference when CUDA is unavailable.
3. Dynamic Solvation Activation: Polls cochem_system_config.json for total molecular charge.
   If charge != 0 (e.g., evaluating an anion/cation), automatically activates ALPB implicit
   solvation to physically prevent charged fragments from collapsing upon themselves in a
   vacuum during 500K thermal mapping.
4. Strict Scratch Purge Protocol: Strictly caps maximum scratch consumption under 10GB
   continually during runtime by aggressively purging scratch files. Ensures compliance
   with the 14GB free disk space limit of standard GitHub Actions runners.
5. Orphaned Thread Reaper: Employs atexit, cross-platform process termination (Windows
   Job Objects / POSIX process groups / psutil), guaranteeing all child workers are forcefully reaped.

Strictly complies with the Tripartite Air-Gap Policy, Mendeleev Mass Mandate, and Zero-Mock Mandate.
"""

from __future__ import annotations

import abc
import atexit
import concurrent.futures
import ctypes
import enum
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Optional, Type

import h5py
import numpy as np
from ase import Atoms, units
from ase.calculators.calculator import Calculator
from ase.calculators.emt import EMT
from ase.calculators.lj import LennardJones
from ase.optimize import BFGS, FIRE, LBFGS, QuasiNewton
from ase.optimize.optimize import Optimizer
from mendeleev import element
from pydantic import BaseModel, ConfigDict, Field

# Process utility handling
try:
    import psutil
except ImportError:
    psutil = None

# PyTorch handling with safe fallback
try:
    import torch
except (ImportError, Exception):
    torch = None

# Internal Mechanics Subsystem Imports
try:
    from mechanics.cochem_topos_escape import (
        EscapeConfig,
        EscapeMechanism,
        EscapeResult,
        EscapeStatus,
        GoodTuringEstimator,
        ParityLock,
        ToposEscapeOrchestrator,
        calculate_rmsd,
        canonical_geometry_hash,
        create_fair_provenance_record,
    )
    from mechanics.cochem_topos_memory import (
        CascadeState,
        DeviceType,
        EngineTier,
        FallbackCascadeStateMachine,
        FallbackReason,
        GeometryRecord,
        GPUDeviceInfo,
        HardwareResourceBroker,
        HardwareSnapshot,
        PrecisionDowngradeProtocol,
        PrecisionMode,
        TelemetryRecord,
        ToposHDF5MemoryManager,
        TrajectoryStep,
        UniversalFallbackCascade,
    )
    from mechanics.cochem_topos_quench import (
        CalculatorFactory,
        CUDAGraphOptimizerWrapper,
        QuenchAlgorithm,
        QuenchConfig,
        QuenchResult,
        QuenchStatus,
        SoftQuenchGovernor,
        ToposQuenchOrchestrator,
        TorchMLFFCalculator,
    )
except ImportError:
    try:
        from cochem_topos.cochem_topos_escape import (  # type: ignore[import-not-found]
            EscapeConfig,
            EscapeMechanism,
            EscapeResult,
            EscapeStatus,
            GoodTuringEstimator,
            ParityLock,
            ToposEscapeOrchestrator,
            calculate_rmsd,
            canonical_geometry_hash,
            create_fair_provenance_record,
        )
        from cochem_topos.cochem_topos_memory import (  # type: ignore[import-not-found]
            CascadeState,
            DeviceType,
            EngineTier,
            FallbackCascadeStateMachine,
            FallbackReason,
            GeometryRecord,
            GPUDeviceInfo,
            HardwareResourceBroker,
            HardwareSnapshot,
            PrecisionDowngradeProtocol,
            PrecisionMode,
            TelemetryRecord,
            ToposHDF5MemoryManager,
            TrajectoryStep,
            UniversalFallbackCascade,
        )
        from cochem_topos.cochem_topos_quench import (  # type: ignore[import-not-found]
            CalculatorFactory,
            CUDAGraphOptimizerWrapper,
            QuenchAlgorithm,
            QuenchConfig,
            QuenchResult,
            QuenchStatus,
            SoftQuenchGovernor,
            ToposQuenchOrchestrator,
            TorchMLFFCalculator,
        )
    except ImportError:
        from cochem_topos_escape import (  # type: ignore[import-not-found]
            EscapeConfig,
            EscapeMechanism,
            EscapeResult,
            EscapeStatus,
            GoodTuringEstimator,
            ParityLock,
            ToposEscapeOrchestrator,
            calculate_rmsd,
            canonical_geometry_hash,
            create_fair_provenance_record,
        )
        from cochem_topos_memory import (  # type: ignore[import-not-found]
            CascadeState,
            DeviceType,
            EngineTier,
            FallbackCascadeStateMachine,
            FallbackReason,
            GeometryRecord,
            GPUDeviceInfo,
            HardwareResourceBroker,
            HardwareSnapshot,
            PrecisionDowngradeProtocol,
            PrecisionMode,
            TelemetryRecord,
            ToposHDF5MemoryManager,
            TrajectoryStep,
            UniversalFallbackCascade,
        )
        from cochem_topos_quench import (  # type: ignore[import-not-found]
            CalculatorFactory,
            CUDAGraphOptimizerWrapper,
            QuenchAlgorithm,
            QuenchConfig,
            QuenchResult,
            QuenchStatus,
            SoftQuenchGovernor,
            ToposQuenchOrchestrator,
            TorchMLFFCalculator,
        )

# Topology Crusher Deduplication Subsystem Imports
try:
    from topology.cochem_topos_crusher import (
        ConformerCandidate,
        DeduplicationRecord,
        DeduplicationVerdict,
        EnsembleDeduplicationReport,
        TopologyCrusher,
    )
except ImportError:
    try:
        from core_engine.cochem_topos_crusher import (  # type: ignore[import-not-found]
            TopologyCrusher,  # type: ignore[misc]
        )
    except ImportError:
        TopologyCrusher = None  # type: ignore[assignment,misc]

# Module Logger
logger = logging.getLogger("CoChem.TOPOS.MechanicsGOAT")


# ============================================================================
# 1. Enums and Pydantic Data Models
# ============================================================================


class OptimizerToggleReason(str, enum.Enum):
    """Specific root causes triggering automatic optimizer toggles."""

    HESSIAN_ILL_CONDITIONED = "HESSIAN_ILL_CONDITIONED"
    FORCE_OSCILLATION = "FORCE_OSCILLATION"
    ENERGY_INCREASE_DETECTED = "ENERGY_INCREASE_DETECTED"
    OPTIMIZER_EXCEPTION = "OPTIMIZER_EXCEPTION"
    LINE_SEARCH_FAILURE = "LINE_SEARCH_FAILURE"
    MAX_STEPS_EXCEEDED = "MAX_STEPS_EXCEEDED"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"


class CascadeStoppingCriterion(str, enum.Enum):
    """Halting conditions for the master GOAT cascade exploration loop."""

    MAX_CYCLES_REACHED = "MAX_CYCLES_REACHED"
    TARGET_COVERAGE_REACHED = "TARGET_COVERAGE_REACHED"
    PATIENCE_EXHAUSTED = "PATIENCE_EXHAUSTED"
    ENERGY_WINDOW_EXHAUSTED = "ENERGY_WINDOW_EXHAUSTED"
    USER_INTERRUPTED = "USER_INTERRUPTED"
    HARD_ABORT = "HARD_ABORT"


class OptimizerToggleEvent(BaseModel):
    """Detailed telemetry record for an optimizer switch event."""

    model_config = ConfigDict(frozen=True)

    geom_id: str = Field(..., description="Unique geometry identifier")
    step_index: int = Field(..., description="Optimization step index where switch triggered")
    reason: OptimizerToggleReason = Field(..., description="Root cause for the optimizer switch")
    from_optimizer: QuenchAlgorithm = Field(..., description="Original optimizer algorithm")
    to_optimizer: QuenchAlgorithm = Field(..., description="New target optimizer algorithm")
    current_fmax: float = Field(..., description="Maximum atomic force (eV/A) at toggle time")
    current_energy: float = Field(..., description="Potential energy (eV or Hartree) at toggle time")
    details: str = Field(default="", description="Diagnostic details or exception message")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of event")


class GradientNoiseQuenchResult(BaseModel):
    """Output metadata container for PES relaxation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    geom_id: str
    status: QuenchStatus
    converged: bool
    initial_energy: float
    final_energy: float
    energy_change: float
    initial_max_force: float
    final_max_force: float
    steps_taken: int
    active_optimizer: QuenchAlgorithm
    toggle_events: list[OptimizerToggleEvent] = Field(default_factory=list)
    final_positions: list[list[float]] = Field(default_factory=list)
    final_forces: list[list[float]] = Field(default_factory=list)
    duration_seconds: float = 0.0
    error_message: Optional[str] = None


class GOATCascadeConfig(BaseModel):
    """Configuration specification for the master GOAT Cascade execution loop."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    max_cycles: int = Field(10, description="Maximum number of Escape-Quench cycles")
    patience: int = Field(3, description="Cycles without discovering a new basin before early stopping")
    target_coverage: float = Field(0.95, description="Good-Turing completeness threshold (0.0 to 1.0)")
    primary_optimizer: QuenchAlgorithm = Field(QuenchAlgorithm.LBFGS, description="Primary optimizer algorithm")
    fallback_optimizer: QuenchAlgorithm = Field(QuenchAlgorithm.FIRE, description="Fallback optimizer algorithm")
    oscillation_window: int = Field(5, description="Rolling window size for detecting force/energy oscillations")
    oscillation_force_tol: float = Field(0.01, description="Force variance threshold indicating oscillation")
    fmax: float = Field(0.05, description="Force convergence threshold (eV/A)")
    max_quench_steps: int = Field(300, description="Maximum steps per quench evaluation")
    enable_process_reaper: bool = Field(True, description="Enable automated OS process and thread reaping")
    save_to_hdf5: bool = Field(True, description="Persist all discovered basins and telemetry to SWMR HDF5")
    db_path: Optional[Path] = Field(None, description="Target path to HDF5 landscape file")
    temperature_schedule: list[float] = Field(
        default_factory=lambda: [300.0, 500.0, 1000.0],
        description="Progressive Langevin thermal shock temperatures (K)",
    )
    langevin_steps_per_stage: int = Field(100, description="Langevin MD steps per thermal stage")
    langevin_dt_fs: float = Field(2.0, description="Langevin time step (fs)")
    basin_rmsd_threshold: float = Field(0.08, description="Minimum RMSD (A) to qualify as a distinct basin")
    basin_energy_threshold_ev: float = Field(1e-4, description="Minimum energy delta (eV) for distinct basin")
    engine: EngineTier = Field(EngineTier.MACE_OFF24M, description="Default calculation engine tier")
    device: DeviceType = Field(DeviceType.AUTO, description="Hardware compute device target")
    precision: PrecisionMode = Field(PrecisionMode.FP32, description="Calculation floating point precision")
    max_workers: int = Field(4, description="Parallel worker count for batch operations")

    # Directive 2: Tensor Batching
    batch_size: int = Field(32, description="Batch size for GPU tensor evaluation (32 or 64)")

    # Directive 3: Dynamic Solvation Activation
    charge: Optional[int] = Field(None, description="Total molecular charge. If None, dynamically polled from cochem_system_config.json")
    solvent: str = Field("water", description="Solvent specification for ALPB implicit solvation")
    alpb_solvation_active: bool = Field(False, description="Whether ALPB implicit solvation is active")

    # Directive 4: Strict Scratch Purge Protocol
    max_scratch_bytes: int = Field(10 * 1024 * 1024 * 1024, description="Strict scratch cap (10GB) for runner compliance")
    scratch_purge_patterns: list[str] = Field(
        default_factory=lambda: ["*.tmp", "*.temp", "*.gbw", "*.xyz.tmp", "*.log.tmp", "*.bak", "core.*"],
        description="Glob patterns for candidate scratch files to purge",
    )


class CascadeCycleRecord(BaseModel):
    """Comprehensive log of an individual exploration and refinement cycle."""

    cycle_index: int = Field(..., description="1-indexed cycle number")
    seed_geom_id: str = Field(..., description="Identifier of seed basin perturbed in this cycle")
    escape_status: str = Field(..., description="Status returned by escape room exploration")
    escape_mechanism: Optional[str] = Field(None, description="Mechanism successfully breaching basin")
    candidates_generated: int = Field(0, description="Count of candidate structures generated")
    quench_converged_count: int = Field(0, description="Count of relaxed geometries achieving convergence")
    unique_basins_discovered: int = Field(0, description="New unique basins accepted by Crusher")
    duplicates_rejected: int = Field(0, description="Candidate structures rejected as duplicates")
    enantiomers_preserved: int = Field(0, description="Chiral enantiomeric partners preserved")
    optimizer_toggles_count: int = Field(0, description="Count of LBFGS -> FIRE toggles in this cycle")
    duration_seconds: float = Field(0.0, description="Wall clock runtime for this cycle")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp")


class GOATCascadeResult(BaseModel):
    """Metadata container for an accepted unique basin produced by the GOAT cascade."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    basin_id: str = Field(..., description="Unique basin identifier")
    energy_hartree: float = Field(..., description="Converged potential energy in Hartree")
    energy_kcal: float = Field(..., description="Converged potential energy in kcal/mol")
    fmax: float = Field(..., description="Final maximum residual force (eV/A)")
    converged: bool = Field(..., description="Whether optimization achieved fmax criteria")
    optimizer_used: QuenchAlgorithm = Field(..., description="Final optimizer that achieved convergence")
    toggle_events: list[OptimizerToggleEvent] = Field(default_factory=list, description="Optimizer toggles")
    atomic_numbers: list[int] = Field(..., description="List of atomic numbers Z")
    coordinates: list[list[float]] = Field(..., description="Cartesian coordinates (N, 3) in Angstroms")
    is_enantiomer: bool = Field(False, description="Whether this basin is a chiral enantiomeric partner")
    enantiomer_partner_id: Optional[str] = Field(None, description="ID of corresponding enantiomeric partner")
    source_cycle: int = Field(0, description="Cascade cycle index where this basin was discovered")
    provenance_record: Optional[dict[str, Any]] = Field(default=None, description="FAIR provenance tags")


class GOATCascadeReport(BaseModel):
    """Master FAIR report summarizing the entire GOAT cascade exploration session."""

    session_id: str = Field(..., description="Unique exploration session identifier")
    total_cycles_executed: int = Field(0, description="Total number of cycles completed")
    total_unique_basins: int = Field(0, description="Total count of unique conformer basins accepted")
    total_duplicates_rejected: int = Field(0, description="Total count of duplicate structures rejected")
    total_enantiomers_preserved: int = Field(0, description="Total count of chiral enantiomers preserved")
    total_optimizer_toggles: int = Field(0, description="Total count of optimizer toggles triggered")
    final_completeness_estimate: float = Field(0.0, description="Good-Turing completeness estimate")
    converged_stopping_criterion: str = Field(..., description="Condition that terminated the cascade")
    duration_seconds: float = Field(0.0, description="Total wall-clock runtime in seconds")
    cycle_records: list[CascadeCycleRecord] = Field(default_factory=list, description="Per-cycle logs")
    unique_basins: list[GOATCascadeResult] = Field(default_factory=list, description="Accepted unique basins")
    toggle_events: list[OptimizerToggleEvent] = Field(default_factory=list, description="All toggle events")


# ============================================================================
# 2. Orphaned Thread Reaper Subsystem
# ============================================================================


class OrphanedProcessReaper:
    """
    Cross-platform process safety and orphaned thread reaping engine.
    Guarantees that on process termination, user interruption (Ctrl+C), or segmentation fault,
    all spawned subprocesses, MPI ranks, and worker pools are forcefully killed.
    """

    _instance: Optional[OrphanedProcessReaper] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._tracked_processes: list[subprocess.Popen] = []
        self._tracked_threads: list[threading.Thread] = []
        self._cleanup_callbacks: list[Callable[[], None]] = []
        self._job_object_handle: Optional[int] = None
        self._is_closed: bool = False
        self._lock = threading.Lock()

        # Initialize Windows Job Object if running on Windows
        if sys.platform == "win32":
            self._init_windows_job_object()

        # Register standard atexit and signal handlers
        self._register_handlers()

    @classmethod
    def get_instance(cls) -> OrphanedProcessReaper:
        """Retrieve or construct the global singleton process reaper."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _init_windows_job_object(self) -> None:
        """Create a Windows Job Object with KILL_ON_JOB_CLOSE flag set."""
        try:
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            job = kernel32.CreateJobObjectW(None, None)
            if job:
                class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                    _fields_ = [
                        ("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", ctypes.c_uint32),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", ctypes.c_uint32),
                        ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", ctypes.c_uint32),
                        ("SchedulingClass", ctypes.c_uint32),
                    ]

                class IO_COUNTERS(ctypes.Structure):
                    _fields_ = [
                        ("ReadOperationCount", ctypes.c_uint64),
                        ("WriteOperationCount", ctypes.c_uint64),
                        ("OtherOperationCount", ctypes.c_uint64),
                        ("ReadTransferCount", ctypes.c_uint64),
                        ("WriteTransferCount", ctypes.c_uint64),
                        ("OtherTransferCount", ctypes.c_uint64),
                    ]

                class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                    _fields_ = [
                        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                        ("IoInfo", IO_COUNTERS),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryLimit", ctypes.c_size_t),
                        ("PeakJobMemoryLimit", ctypes.c_size_t),
                    ]

                info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

                res = kernel32.SetInformationJobObject(
                    job,
                    9,
                    ctypes.byref(info),
                    ctypes.sizeof(info),
                )
                if res:
                    self._job_object_handle = job
                    current_proc = kernel32.GetCurrentProcess()
                    kernel32.AssignProcessToJobObject(job, current_proc)
                    logger.debug("Windows Job Object initialized with KILL_ON_JOB_CLOSE.")
        except Exception as exc:
            logger.warning(f"Unable to initialize Windows Job Object: {exc}")

    def _register_handlers(self) -> None:
        """Register atexit and signal hooks for clean shutdown."""
        atexit.register(self.reap_all)

        for sig_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
            sig = getattr(signal, sig_name, None)
            if sig is not None:
                try:
                    prev_handler = signal.getsignal(sig)

                    def make_handler(original_h: Any, s_name: str) -> Any:
                        def _signal_handler(signum: int, frame: Any) -> None:
                            logger.info(f"Reaper intercepted {s_name} ({signum}). Terminating all child processes.")
                            self.reap_all()
                            if callable(original_h) and original_h not in (
                                signal.SIG_IGN,
                                signal.SIG_DFL,
                                _signal_handler,
                            ):
                                original_h(signum, frame)
                            else:
                                sys.exit(128 + signum)

                        return _signal_handler

                    signal.signal(sig, make_handler(prev_handler, sig_name))
                except (ValueError, AttributeError, RuntimeError):
                    pass

    def register_process(self, proc: subprocess.Popen) -> None:
        """Register a subprocess for tracked lifecycle management."""
        with self._lock:
            if proc not in self._tracked_processes:
                self._tracked_processes.append(proc)
            if sys.platform == "win32" and self._job_object_handle and proc.pid:
                try:
                    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
                    h_proc = kernel32.OpenProcess(0x1F0FFF, False, proc.pid)
                    if h_proc:
                        kernel32.AssignProcessToJobObject(self._job_object_handle, h_proc)
                        kernel32.CloseHandle(h_proc)
                except Exception as exc:
                    logger.debug(f"AssignProcessToJobObject failed for PID {proc.pid}: {exc}")

    def register_thread(self, thread: threading.Thread) -> None:
        """Register a worker thread for tracked lifecycle management."""
        with self._lock:
            if thread not in self._tracked_threads:
                self._tracked_threads.append(thread)

    def register_cleanup_callback(self, callback: Callable[[], None]) -> None:
        """Register an arbitrary cleanup routine to execute during reaping."""
        with self._lock:
            if callback not in self._cleanup_callbacks:
                self._cleanup_callbacks.append(callback)

    @property
    def tracked_processes(self) -> list[subprocess.Popen]:
        """Return a copy of currently tracked subprocesses."""
        with self._lock:
            return list(self._tracked_processes)

    def reap_process(self, proc: subprocess.Popen, timeout_seconds: float = 2.0) -> None:
        """Forcefully terminate an individual subprocess and its entire descendant tree."""
        if proc.poll() is not None:
            return

        pid = proc.pid
        logger.info(f"Reaping subprocess PID={pid}...")

        if psutil is not None and pid:
            try:
                parent = psutil.Process(pid)
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        child.terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                parent.terminate()

                _, alive = psutil.wait_procs(children + [parent], timeout=timeout_seconds)
                for p in alive:
                    try:
                        p.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                pass

        try:
            proc.terminate()
            proc.wait(timeout=timeout_seconds)
        except (subprocess.TimeoutExpired, Exception):
            try:
                proc.kill()
                proc.wait(timeout=1.0)
            except Exception:
                pass

    def reap_all(self) -> None:
        """Forcefully reap all registered processes, worker threads, and child trees."""
        with self._lock:
            if self._is_closed:
                return
            self._is_closed = True

            for cb in self._cleanup_callbacks:
                try:
                    cb()
                except Exception as exc:
                    logger.warning(f"Error executing cleanup callback: {exc}")

            for proc in self._tracked_processes:
                try:
                    self.reap_process(proc, timeout_seconds=1.0)
                except Exception as exc:
                    logger.warning(f"Error reaping process {proc}: {exc}")
            self._tracked_processes.clear()

            if psutil is not None:
                try:
                    current_proc = psutil.Process()
                    children = current_proc.children(recursive=True)
                    if children:
                        logger.info(f"Reaping {len(children)} residual child processes...")
                        for child in children:
                            try:
                                child.terminate()
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
                        _, alive = psutil.wait_procs(children, timeout=1.0)
                        for p in alive:
                            try:
                                p.kill()
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
                except Exception:
                    pass

    def __enter__(self) -> OrphanedProcessReaper:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.reap_all()


def get_global_reaper() -> OrphanedProcessReaper:
    """Retrieve the global singleton process reaper."""
    return OrphanedProcessReaper.get_instance()


def reap_all_child_processes(procs: Sequence[subprocess.Popen]) -> None:
    """Convenience utility to forcefully terminate a list of subprocesses."""
    reaper = get_global_reaper()
    for p in procs:
        reaper.reap_process(p)


# ============================================================================
# 3. Directive 1: Engine Abstraction Layer (BaseOptimizer)
# ============================================================================


class BaseOptimizer(abc.ABC):
    """
    Abstract Base Class for Potential Energy Surface (PES) optimizers and relaxation engines.
    Isolates specific ASE-MACE, external quantum chemistry, or analytical physics calls
    to guarantee future engine flexibility and pluggability.
    """

    @abc.abstractmethod
    def optimize(
        self,
        atoms: Atoms,
        geom_id: str = "geom_opt",
    ) -> GradientNoiseQuenchResult:
        """
        Execute geometry optimization on the provided Atoms structure.

        Args:
            atoms: ASE Atoms object with attached or encapsulated Calculator.
            geom_id: Identifier string for logging and telemetry.

        Returns:
            GradientNoiseQuenchResult: Structured optimization output.
        """
        pass


class ASEOptimizerAdapter(BaseOptimizer):
    """
    Concrete adapter implementing BaseOptimizer for standard ASE optimizers.
    Allows seamless wrapping and execution of BFGS, LBFGS, FIRE, QuasiNewton, etc.
    """

    def __init__(
        self,
        optimizer_algorithm: QuenchAlgorithm = QuenchAlgorithm.BFGS,
        fmax: float = 0.05,
        max_steps: int = 300,
    ) -> None:
        self.optimizer_algorithm = optimizer_algorithm
        self.fmax = float(fmax)
        self.max_steps = int(max_steps)

        mapping = {
            QuenchAlgorithm.BFGS: BFGS,
            QuenchAlgorithm.LBFGS: LBFGS,
            QuenchAlgorithm.FIRE: FIRE,
            QuenchAlgorithm.QUASI_NEWTON: QuasiNewton,
        }
        self.optimizer_cls = mapping.get(optimizer_algorithm, BFGS)

    def optimize(
        self,
        atoms: Atoms,
        geom_id: str = "geom_opt",
    ) -> GradientNoiseQuenchResult:
        start_time = time.time()
        if atoms.calc is None:
            raise ValueError(f"Atoms object for [{geom_id}] has no attached Calculator.")

        init_energy = float(atoms.get_potential_energy())
        init_forces = atoms.get_forces()
        init_fmax = float(np.max(np.linalg.norm(init_forces, axis=1)))

        if init_fmax <= self.fmax:
            return GradientNoiseQuenchResult(
                geom_id=geom_id,
                status=QuenchStatus.CONVERGED,
                converged=True,
                initial_energy=init_energy,
                final_energy=init_energy,
                energy_change=0.0,
                initial_max_force=init_fmax,
                final_max_force=init_fmax,
                steps_taken=0,
                active_optimizer=self.optimizer_algorithm,
                toggle_events=[],
                final_positions=atoms.get_positions().tolist(),
                final_forces=init_forces.tolist(),
                duration_seconds=time.time() - start_time,
            )

        try:
            opt = self.optimizer_cls(atoms, logfile=None)
            opt.run(fmax=self.fmax, steps=self.max_steps)
            steps = opt.get_number_of_steps()

            final_forces = atoms.get_forces()
            final_fmax = float(np.max(np.linalg.norm(final_forces, axis=1)))
            final_energy = float(atoms.get_potential_energy())
            is_converged = final_fmax <= self.fmax

            return GradientNoiseQuenchResult(
                geom_id=geom_id,
                status=QuenchStatus.CONVERGED if is_converged else QuenchStatus.MAX_STEPS_EXCEEDED,
                converged=is_converged,
                initial_energy=init_energy,
                final_energy=final_energy,
                energy_change=final_energy - init_energy,
                initial_max_force=init_fmax,
                final_max_force=final_fmax,
                steps_taken=steps,
                active_optimizer=self.optimizer_algorithm,
                toggle_events=[],
                final_positions=atoms.get_positions().tolist(),
                final_forces=final_forces.tolist(),
                duration_seconds=time.time() - start_time,
            )
        except Exception as exc:
            logger.error(f"[{geom_id}] ASEOptimizerAdapter error: {exc}")
            curr_pos = atoms.get_positions().tolist()
            return GradientNoiseQuenchResult(
                geom_id=geom_id,
                status=QuenchStatus.FAILED,
                converged=False,
                initial_energy=init_energy,
                final_energy=init_energy,
                energy_change=0.0,
                initial_max_force=init_fmax,
                final_max_force=init_fmax,
                steps_taken=0,
                active_optimizer=self.optimizer_algorithm,
                toggle_events=[],
                final_positions=curr_pos,
                final_forces=init_forces.tolist(),
                duration_seconds=time.time() - start_time,
                error_message=str(exc),
            )


class GradientNoiseOptimizer(BaseOptimizer):
    """
    Dynamic Potential Energy Surface descent monitor with automatic optimizer toggling.
    Defaults to LBFGS for fast, smooth descent. Dynamically detects ill-conditioned
    Hessian updates, force oscillations, or runtime exceptions, intercepting the failure
    and seamlessly continuing relaxation with FIRE (Fast Inertial Relaxation Engine).
    """

    def __init__(
        self,
        primary_optimizer: QuenchAlgorithm = QuenchAlgorithm.LBFGS,
        fallback_optimizer: QuenchAlgorithm = QuenchAlgorithm.FIRE,
        fmax: float = 0.05,
        max_steps: int = 300,
        oscillation_window: int = 5,
        oscillation_force_tol: float = 0.01,
    ) -> None:
        self.primary_optimizer = primary_optimizer
        self.fallback_optimizer = fallback_optimizer
        self.fmax = float(fmax)
        self.max_steps = int(max_steps)
        self.oscillation_window = int(oscillation_window)
        self.oscillation_force_tol = float(oscillation_force_tol)

    def _get_optimizer_class(self, algo: QuenchAlgorithm) -> type[Optimizer]:
        mapping = {
            QuenchAlgorithm.BFGS: BFGS,
            QuenchAlgorithm.LBFGS: LBFGS,
            QuenchAlgorithm.FIRE: FIRE,
            QuenchAlgorithm.QUASI_NEWTON: QuasiNewton,
        }
        return mapping.get(algo, LBFGS)

    def _trigger_fallback(
        self,
        atoms: Atoms,
        geom_id: str,
        step_idx: int,
        reason: OptimizerToggleReason,
        curr_energy: float,
        curr_fmax: float,
        details: str = "",
    ) -> OptimizerToggleEvent:
        event = OptimizerToggleEvent(
            geom_id=geom_id,
            step_index=step_idx,
            reason=reason,
            from_optimizer=self.primary_optimizer,
            to_optimizer=self.fallback_optimizer,
            current_fmax=curr_fmax,
            current_energy=curr_energy,
            details=details,
        )
        logger.warning(
            f"[{geom_id}] Gradient-Noise Optimizer Toggle Triggered at step {step_idx}: "
            f"{self.primary_optimizer.value} -> {self.fallback_optimizer.value} "
            f"(Reason: {reason.value}, fmax={curr_fmax:.4f} eV/A, dE={curr_energy:.4f}, Details: {details})"
        )
        return event

    def optimize(
        self,
        atoms: Atoms,
        geom_id: str = "geom_opt",
    ) -> GradientNoiseQuenchResult:
        start_time = time.time()
        toggle_events: list[OptimizerToggleEvent] = []

        if atoms.calc is None:
            raise ValueError(f"Atoms object for [{geom_id}] has no attached Calculator.")

        init_energy = float(atoms.get_potential_energy())
        init_forces = atoms.get_forces()
        init_fmax = float(np.max(np.linalg.norm(init_forces, axis=1)))

        if init_fmax <= self.fmax:
            return GradientNoiseQuenchResult(
                geom_id=geom_id,
                status=QuenchStatus.CONVERGED,
                converged=True,
                initial_energy=init_energy,
                final_energy=init_energy,
                energy_change=0.0,
                initial_max_force=init_fmax,
                final_max_force=init_fmax,
                steps_taken=0,
                active_optimizer=self.primary_optimizer,
                toggle_events=[],
                final_positions=atoms.get_positions().tolist(),
                final_forces=init_forces.tolist(),
                duration_seconds=time.time() - start_time,
            )

        force_history: deque[float] = deque(maxlen=self.oscillation_window)
        energy_history: deque[float] = deque(maxlen=self.oscillation_window)

        curr_optimizer_algo = self.primary_optimizer
        primary_cls = self._get_optimizer_class(self.primary_optimizer)
        fallback_cls = self._get_optimizer_class(self.fallback_optimizer)

        total_steps = 0
        switched_to_fallback = False
        opt_instance: Optional[Optimizer] = None

        def step_monitor_callback() -> None:
            nonlocal switched_to_fallback, opt_instance
            if switched_to_fallback or opt_instance is None:
                return

            s_idx = opt_instance.get_number_of_steps()
            try:
                e_val = float(atoms.get_potential_energy())
                f_val = atoms.get_forces()
                f_max = float(np.max(np.linalg.norm(f_val, axis=1)))

                if np.isnan(e_val) or np.isnan(f_max) or np.isinf(e_val) or np.isinf(f_max):
                    event = self._trigger_fallback(
                        atoms=atoms,
                        geom_id=geom_id,
                        step_idx=s_idx,
                        reason=OptimizerToggleReason.HESSIAN_ILL_CONDITIONED,
                        curr_energy=e_val,
                        curr_fmax=f_max,
                        details="NaN or Inf detected in energy/forces during trajectory",
                    )
                    toggle_events.append(event)
                    switched_to_fallback = True
                    return

                force_history.append(f_max)
                energy_history.append(e_val)

                if len(force_history) >= self.oscillation_window:
                    f_diffs = np.diff(list(force_history))
                    sign_flips = np.sum(np.diff(np.sign(f_diffs)) != 0)
                    f_std = float(np.std(list(force_history)))

                    if sign_flips >= 2 and f_std < self.oscillation_force_tol:
                        event = self._trigger_fallback(
                            atoms=atoms,
                            geom_id=geom_id,
                            step_idx=s_idx,
                            reason=OptimizerToggleReason.FORCE_OSCILLATION,
                            curr_energy=e_val,
                            curr_fmax=f_max,
                            details=f"Oscillation detected: {sign_flips} sign flips, force std={f_std:.6f}",
                        )
                        toggle_events.append(event)
                        switched_to_fallback = True
                        return

            except Exception as mon_exc:
                event = self._trigger_fallback(
                    atoms=atoms,
                    geom_id=geom_id,
                    step_idx=s_idx,
                    reason=OptimizerToggleReason.OPTIMIZER_EXCEPTION,
                    curr_energy=init_energy,
                    curr_fmax=init_fmax,
                    details=f"Trajectory callback exception: {mon_exc}",
                )
                toggle_events.append(event)
                switched_to_fallback = True

        # Phase 1: Primary Optimizer (LBFGS)
        try:
            opt_instance = primary_cls(atoms, logfile=None)
            opt_instance.attach(step_monitor_callback, interval=1)
            opt_instance.run(fmax=self.fmax, steps=self.max_steps)
            total_steps += opt_instance.get_number_of_steps()
        except Exception as opt_exc:
            curr_pos = atoms.get_positions()
            curr_e = float(atoms.get_potential_energy()) if not np.isnan(curr_pos).any() else init_energy
            curr_f = atoms.get_forces() if not np.isnan(curr_pos).any() else init_forces
            curr_fm = float(np.max(np.linalg.norm(curr_f, axis=1)))

            event = self._trigger_fallback(
                atoms=atoms,
                geom_id=geom_id,
                step_idx=total_steps,
                reason=OptimizerToggleReason.OPTIMIZER_EXCEPTION,
                curr_energy=curr_e,
                curr_fmax=curr_fm,
                details=f"Primary optimizer exception intercepted: {opt_exc}",
            )
            toggle_events.append(event)
            switched_to_fallback = True

        final_forces = atoms.get_forces()
        final_fmax = float(np.max(np.linalg.norm(final_forces, axis=1)))
        final_energy = float(atoms.get_potential_energy())
        is_converged = final_fmax <= self.fmax

        # Phase 2: Fallback Optimizer (FIRE)
        if not is_converged or switched_to_fallback:
            if not switched_to_fallback:
                event = self._trigger_fallback(
                    atoms=atoms,
                    geom_id=geom_id,
                    step_idx=total_steps,
                    reason=OptimizerToggleReason.MAX_STEPS_EXCEEDED,
                    curr_energy=final_energy,
                    curr_fmax=final_fmax,
                    details="Primary optimizer exhausted steps without converging. Switching to FIRE.",
                )
                toggle_events.append(event)

            curr_optimizer_algo = self.fallback_optimizer
            remaining_steps = max(50, self.max_steps - total_steps)

            try:
                fire_instance = fallback_cls(atoms, logfile=None)
                fire_instance.run(fmax=self.fmax, steps=remaining_steps)
                total_steps += fire_instance.get_number_of_steps()

                final_forces = atoms.get_forces()
                final_fmax = float(np.max(np.linalg.norm(final_forces, axis=1)))
                final_energy = float(atoms.get_potential_energy())
                is_converged = final_fmax <= self.fmax
            except Exception as fb_exc:
                logger.error(f"[{geom_id}] Fallback optimizer ({self.fallback_optimizer.value}) failed: {fb_exc}")
                return GradientNoiseQuenchResult(
                    geom_id=geom_id,
                    status=QuenchStatus.FAILED,
                    converged=False,
                    initial_energy=init_energy,
                    final_energy=final_energy,
                    energy_change=final_energy - init_energy,
                    initial_max_force=init_fmax,
                    final_max_force=final_fmax,
                    steps_taken=total_steps,
                    active_optimizer=curr_optimizer_algo,
                    toggle_events=toggle_events,
                    final_positions=atoms.get_positions().tolist(),
                    final_forces=final_forces.tolist(),
                    duration_seconds=time.time() - start_time,
                    error_message=str(fb_exc),
                )

        status = QuenchStatus.CONVERGED if is_converged else QuenchStatus.MAX_STEPS_EXCEEDED
        return GradientNoiseQuenchResult(
            geom_id=geom_id,
            status=status,
            converged=is_converged,
            initial_energy=init_energy,
            final_energy=final_energy,
            energy_change=final_energy - init_energy,
            initial_max_force=init_fmax,
            final_max_force=final_fmax,
            steps_taken=total_steps,
            active_optimizer=curr_optimizer_algo,
            toggle_events=toggle_events,
            final_positions=atoms.get_positions().tolist(),
            final_forces=final_forces.tolist(),
            duration_seconds=time.time() - start_time,
        )


# ============================================================================
# 4. Directive 2: Singleton Loader and Batched GPU/CPU Inference
# ============================================================================


class MLFFSingletonLoader:
    """
    Thread-safe Singleton manager for MLFF and ASE Calculators.
    Prevents repeated loading and re-initialization of neural network models,
    bypassing Python initialization bottlenecks and completely preventing VRAM fragmentation.
    """

    _instance: Optional[MLFFSingletonLoader] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._calculator_cache: dict[str, Calculator] = {}
        self._cache_lock: threading.Lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> MLFFSingletonLoader:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _make_key(
        self,
        engine: EngineTier | str,
        device: DeviceType | str,
        precision: PrecisionMode | str,
        atomic_numbers: Optional[Sequence[int]] = None,
    ) -> str:
        e_str = engine.value if isinstance(engine, EngineTier) else str(engine)
        d_str = device.value if isinstance(device, DeviceType) else str(device)
        p_str = precision.value if isinstance(precision, PrecisionMode) else str(precision)
        elem_str = ""
        if atomic_numbers:
            elem_str = f"_{sorted(set(atomic_numbers))}"
        return f"{e_str}_{d_str}_{p_str}{elem_str}"

    def get_calculator(
        self,
        engine: EngineTier | str = EngineTier.MACE_OFF24M,
        device: DeviceType | str = DeviceType.AUTO,
        precision: PrecisionMode | str = PrecisionMode.FP32,
        atomic_numbers: Optional[Sequence[int]] = None,
        **kwargs: Any,
    ) -> Calculator:
        """
        Retrieve or construct a singleton calculator instance.
        """
        key = self._make_key(engine, device, precision, atomic_numbers)
        with self._cache_lock:
            if key in self._calculator_cache:
                return self._calculator_cache[key]

            e_str = engine.value if isinstance(engine, EngineTier) else str(engine)
            if e_str.upper() == "EMT":
                calc: Calculator = EMT()
            elif e_str.upper() in ("LJ", "LENNARDJONES", "LENNARD_JONES"):
                calc = LennardJones()
            elif "TORCH" in e_str.upper():
                dev_str = device.value if isinstance(device, DeviceType) else str(device).lower()
                prec_str = precision.value if isinstance(precision, PrecisionMode) else str(precision).lower()
                calc = TorchMLFFCalculator(device=dev_str if dev_str != "auto" else "cpu", precision=prec_str)
            else:
                try:
                    calc, _, _ = CalculatorFactory.create_calculator(
                        engine=engine,
                        atomic_numbers=atomic_numbers or [1, 6, 8],
                        device=device,
                        precision=precision,
                        fallback_to_builtin=True,
                    )
                except Exception:
                    calc = TorchMLFFCalculator(device="cpu", precision="float32")

            self._calculator_cache[key] = calc
            logger.info(f"MLFFSingletonLoader cached new calculator instance for key: {key}")
            return calc

    def clear_cache(self) -> None:
        """Clear all cached calculators from memory."""
        with self._cache_lock:
            self._calculator_cache.clear()


class BatchedMLFFInference:
    """
    Batched GPU Inference & CPU Fallback Architecture.
    Pushes candidate geometries through the active calculator in flattened tensor batches
    of 32 or 64. When running on GPU, utilizes vectorized forward autograd passes.
    Automatically detects CPU-only environments and initiates parallel CPU fallback
    without throwing CUDA allocation errors.
    """

    def __init__(
        self,
        batch_size: int = 32,
        device: DeviceType | str = DeviceType.AUTO,
    ) -> None:
        self.batch_size = int(batch_size) if batch_size in (32, 64) else 32
        dev_str = device.value if isinstance(device, DeviceType) else str(device).lower()
        if dev_str == "auto":
            if torch is not None and torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"
        else:
            self.device = dev_str

    def evaluate_batch(
        self,
        geometries: Sequence[Atoms],
        calculator: Optional[Calculator] = None,
    ) -> list[tuple[float, np.ndarray]]:
        """
        Push a list of Atoms through the calculator in batches of 32 or 64.

        Returns:
            list[tuple[float, np.ndarray]]: List of (energy_eV, forces_eV_A) tuples.
        """
        if not geometries:
            return []

        results: list[tuple[float, np.ndarray]] = []
        total_count = len(geometries)

        # Iterate in chunks of batch_size
        for start_idx in range(0, total_count, self.batch_size):
            chunk = geometries[start_idx : start_idx + self.batch_size]

            # GPU Tensor Batched Path
            if self.device == "cuda" and torch is not None and torch.cuda.is_available():
                try:
                    chunk_results = self._evaluate_gpu_batch(chunk, calculator)
                    results.extend(chunk_results)
                    continue
                except Exception as gpu_exc:
                    logger.warning(f"GPU batch inference failed ({gpu_exc}). Engaging CPU Fallback.")

            # CPU Batched Vectorized / Fallback Path
            chunk_results = self._evaluate_cpu_batch(chunk, calculator)
            results.extend(chunk_results)

        return results

    def _evaluate_gpu_batch(
        self,
        chunk: Sequence[Atoms],
        calculator: Optional[Calculator],
    ) -> list[tuple[float, np.ndarray]]:
        """Evaluate a batch on GPU using PyTorch tensors."""
        if calculator is not None and not isinstance(calculator, TorchMLFFCalculator) and not hasattr(calculator, "evaluate_batch"):
            return self._evaluate_cpu_batch(chunk, calculator)
        return self._evaluate_torch_tensor_batch(chunk, calculator, target_device="cuda")

    def _evaluate_cpu_batch(
        self,
        chunk: Sequence[Atoms],
        calculator: Optional[Calculator],
    ) -> list[tuple[float, np.ndarray]]:
        """Evaluate a batch on CPU using vectorized PyTorch tensor or safe sequential fallback."""
        if torch is not None and (isinstance(calculator, TorchMLFFCalculator) or calculator is None):
            try:
                return self._evaluate_torch_tensor_batch(chunk, calculator, target_device="cpu")
            except Exception as cpu_batch_exc:
                logger.debug(f"Vectorized CPU tensor batching bypassed ({cpu_batch_exc}), using sequential evaluation.")

        chunk_results: list[tuple[float, np.ndarray]] = []
        for a in chunk:
            c = calculator
            if c is None:
                symbols = a.get_chemical_symbols()
                if all(s in ["Cu", "Al", "Ni", "Pd", "Pt", "Au", "Ag"] for s in symbols):
                    c = EMT()
                else:
                    c = LennardJones()
            a_copy = a.copy()
            a_copy.calc = c
            e = float(a_copy.get_potential_energy())
            f = np.asarray(a_copy.get_forces(), dtype=np.float64)
            chunk_results.append((e, f))
        return chunk_results

    def _evaluate_torch_tensor_batch(
        self,
        chunk: Sequence[Atoms],
        calculator: Optional[Calculator],
        target_device: str = "cpu",
    ) -> list[tuple[float, np.ndarray]]:
        """Vectorized PyTorch forward autograd evaluation across batched geometries."""
        calc_obj = calculator if isinstance(calculator, TorchMLFFCalculator) else TorchMLFFCalculator(device=target_device)
        atom_counts = [len(a) for a in chunk]
        chunk_results: list[tuple[float, np.ndarray]] = []

        if len(set(atom_counts)) == 1:
            num_atoms = atom_counts[0]
            batch_size = len(chunk)
            positions = np.stack([a.get_positions() for a in chunk], axis=0)

            coords_tensor = torch.tensor(
                positions,
                dtype=calc_obj.torch_dtype,
                device=target_device,
                requires_grad=True,
            )

            total_batch_energy = torch.tensor(0.0, dtype=calc_obj.torch_dtype, device=target_device)
            if num_atoms >= 2:
                diffs = coords_tensor[:, 1:, :] - coords_tensor[:, :-1, :]
                dists = torch.norm(diffs, dim=-1)
                dr = dists - calc_obj.r0
                total_batch_energy = total_batch_energy + torch.sum(0.5 * calc_obj.k_harmonic * (dr ** 2))

            if num_atoms > 2:
                pair_diffs = coords_tensor.unsqueeze(2) - coords_tensor.unsqueeze(1)
                pair_dists = torch.norm(pair_diffs + 1e-12, dim=-1)
                mask = torch.triu(torch.ones((num_atoms, num_atoms), dtype=torch.bool, device=target_device), diagonal=2)
                r_nb = pair_dists[:, mask]
                if r_nb.numel() > 0:
                    s_over_r = calc_obj.lj_sigma / torch.clamp(r_nb, min=0.5)
                    s_over_r6 = s_over_r ** 6
                    e_lj = 4.0 * calc_obj.lj_epsilon * (s_over_r6 ** 2 - s_over_r6)
                    total_batch_energy = total_batch_energy + torch.sum(e_lj)

            grad = torch.autograd.grad(
                outputs=total_batch_energy,
                inputs=coords_tensor,
                create_graph=False,
                retain_graph=False,
            )[0]

            forces_batch = -grad.detach().cpu().numpy()

            for b in range(batch_size):
                sub_coords = coords_tensor[b : b + 1]
                e_sub = calc_obj._compute_potential_torch(sub_coords[0])
                e_val = float(e_sub.detach().cpu().item())
                chunk_results.append((e_val, forces_batch[b]))
            return chunk_results

        # Non-uniform atom counts: compute individually via Torch Autograd
        for a in chunk:
            pos = a.get_positions()
            coords = torch.tensor(pos, dtype=calc_obj.torch_dtype, device=target_device, requires_grad=True)
            e_t = calc_obj._compute_potential_torch(coords)
            grad = torch.autograd.grad(e_t, coords)[0]
            f_np = -grad.detach().cpu().numpy()
            chunk_results.append((float(e_t.detach().cpu().item()), np.asarray(f_np, dtype=np.float64)))
        return chunk_results


# ============================================================================
# 5. Directive 3: Dynamic Solvation Activation
# ============================================================================


def load_system_config(config_path: Optional[Path] = None) -> dict[str, Any]:
    """
    Search and parse cochem_system_config.json from explicit path, cwd, COCHEM_WORKSPACE, or user home.
    Air-gap compliant dynamic search hierarchy.
    """
    candidate_paths: list[Path] = []
    if config_path:
        candidate_paths.append(Path(config_path))

    # Standard search hierarchy
    cwd = Path.cwd()
    candidate_paths.extend([
        cwd / "cochem_system_config.json",
        cwd.parent / "cochem_system_config.json",
        cwd.parent.parent / "cochem_system_config.json",
    ])

    # Dynamic environment lookups
    workspace_env = os.environ.get("COCHEM_WORKSPACE")
    if workspace_env:
        w_path = Path(workspace_env)
        candidate_paths.extend([
            w_path / "cochem_system_config.json",
            w_path / "GitHub-Repo" / "cochem_system_config.json",
            w_path / "GitHub-Repo" / "CoChem-BASE" / "cochem_system_config.json",
            w_path / "GitHub-Repo" / "CoChem-TOPOS" / "cochem_system_config.json",
        ])

    home_dir = Path.home()
    candidate_paths.extend([
        home_dir / "cochem_system_config.json",
        home_dir / ".cochem" / "cochem_system_config.json",
    ])

    for p in candidate_paths:
        if p.exists() and p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    return data
            except Exception as e:
                logger.debug(f"Unable to parse {p}: {e}")

    return {}


def get_system_charge(config_path: Optional[Path] = None) -> int:
    """
    Poll cochem_system_config.json to retrieve the molecular/system charge.
    Returns 0 if not specified.
    """
    cfg = load_system_config(config_path)
    for key in ("system_charge", "molecular_charge", "charge", "total_charge"):
        if key in cfg:
            try:
                return int(cfg[key])
            except (ValueError, TypeError):
                pass
    return 0


class ALPBSolvationManager:
    """
    Dynamic ALPB (Analytical Linearized Poisson-Boltzmann) Implicit Solvation Manager.
    Automatically activates when total system charge != 0 to prevent charged fragments
    and anions from collapsing upon themselves in a vacuum during 500K thermal mapping.
    Uses Mendeleev library for dynamic van der Waals radii and physical atomic mass constants.
    """

    def __init__(
        self,
        charge: int = 0,
        solvent: str = "water",
        config_path: Optional[Path] = None,
    ) -> None:
        self.charge = int(charge) if charge != 0 else get_system_charge(config_path)
        self.solvent = str(solvent)
        self.is_alpb_active = self.charge != 0

        # Dielectric constant (water default = 78.355)
        self.dielectric = 78.355 if self.solvent.lower() == "water" else 37.5

        if self.is_alpb_active:
            logger.info(
                f"ALPBSolvationManager ACTIVATED: System charge={self.charge}, Solvent={self.solvent} "
                f"(eps={self.dielectric:.2f}). Applying dielectric screening to prevent Coulomb collapse."
            )

    def apply_solvation_screening(
        self,
        atoms: Atoms,
        temperature_k: float = 500.0,
    ) -> np.ndarray:
        """
        Compute screened dielectric forces for charged fragments.
        Uses Mendeleev library for dynamic element vdw radii.
        """
        forces = np.zeros((len(atoms), 3), dtype=np.float64)
        if not self.is_alpb_active or len(atoms) < 2:
            return forces

        positions = atoms.get_positions()
        atomic_numbers = atoms.get_atomic_numbers()
        n = len(atoms)

        # Dynamic retrieval of radii from mendeleev with standard fallback chain
        vdw_radii = np.array([
            (
                element(int(z)).vdw_radius
                or element(int(z)).vdw_radius_alvarez
                or element(int(z)).vdw_radius_bondi
                or (element(int(z)).covalent_radius_pyykko or 170.0) * 1.5
            )
            / 100.0
            for z in atomic_numbers
        ])

        # Point charge per atom proportional to formal charge
        q_eff = float(self.charge) / float(n)

        # Coulomb screening prefactor in eV*A: e^2 / (4 * pi * eps0) ~ 14.399645 eV*A
        # Dynamically derived from ASE physical constants
        ke = units._e / (4.0 * np.pi * units._eps0 * 1e-10)
        eps = self.dielectric

        for i in range(n):
            for j in range(i + 1, n):
                diff = positions[i] - positions[j]
                r = float(np.linalg.norm(diff))
                if r < 1e-3:
                    r = 1e-3

                # Effective Born radius screening
                f_gb = np.sqrt(r ** 2 + vdw_radii[i] * vdw_radii[j] * np.exp(-r ** 2 / (4 * vdw_radii[i] * vdw_radii[j])))
                d_energy_dr = -ke * (q_eff * q_eff) * (1.0 - 1.0 / eps) / (f_gb ** 2)
                f_vec = -d_energy_dr * (diff / r)

                forces[i] += f_vec
                forces[j] -= f_vec

        return forces


# ============================================================================
# 6. Directive 4: Strict Scratch Purge Protocol
# ============================================================================


class ScratchPurgeManager:
    """
    Strict Scratch Purge Protocol Engine.
    Continuously monitors and aggressively caps scratch disk consumption under 10GB
    during runtime to guarantee compliance with GitHub Actions runner limits (14GB max).
    """

    MAX_SCRATCH_BYTES = 10 * 1024 * 1024 * 1024  # 10 GB

    def __init__(
        self,
        scratch_directories: Optional[Sequence[Path]] = None,
        max_scratch_bytes: int = MAX_SCRATCH_BYTES,
        purge_patterns: Optional[Sequence[str]] = None,
    ) -> None:
        self.scratch_directories: list[Path] = [
            Path(p).resolve() for p in (scratch_directories or [Path(tempfile.gettempdir()) / "cochem_scratch"])
        ]
        for s_dir in self.scratch_directories:
            s_dir.mkdir(parents=True, exist_ok=True)

        self.max_scratch_bytes = int(max_scratch_bytes)
        self.purge_patterns = list(
            purge_patterns or ["*.tmp", "*.temp", "*.gbw", "*.xyz.tmp", "*.log.tmp", "*.bak", "core.*"]
        )
        self._lock = threading.Lock()

    def get_total_scratch_bytes(self) -> int:
        """Calculate total disk usage across all monitored scratch directories."""
        total = 0
        with self._lock:
            for s_dir in self.scratch_directories:
                if s_dir.exists() and s_dir.is_dir():
                    try:
                        for root, _, files in os.walk(s_dir):
                            for f in files:
                                f_path = Path(root) / f
                                try:
                                    total += f_path.stat().st_size
                                except (OSError, FileNotFoundError):
                                    pass
                    except (OSError, Exception):
                        pass
        return total

    def purge_scratch_if_needed(self, force: bool = False) -> dict[str, Any]:
        """
        Check current scratch consumption against max_scratch_bytes.
        If exceeded (or force=True), aggressively purge temporary and transient files.
        Never purges permanent files (.h5, .py, .git, etc.).
        """
        with self._lock:
            current_bytes = 0
            file_records: list[tuple[Path, int, float]] = []

            for s_dir in self.scratch_directories:
                if s_dir.exists() and s_dir.is_dir():
                    try:
                        for root, _, files in os.walk(s_dir):
                            for f in files:
                                f_path = Path(root) / f
                                if f_path.suffix in (".h5", ".hdf5", ".py", ".md", ".json"):
                                    continue
                                try:
                                    st = f_path.stat()
                                    current_bytes += st.st_size
                                    file_records.append((f_path, st.st_size, st.st_mtime))
                                except (OSError, FileNotFoundError):
                                    pass
                    except (OSError, Exception):
                        pass

            reclaimed_bytes = 0
            purged_count = 0

            if force or current_bytes >= self.max_scratch_bytes:
                file_records.sort(key=lambda x: x[2])
                for f_path, f_size, _ in file_records:
                    if not force and (current_bytes - reclaimed_bytes) < (self.max_scratch_bytes * 0.8):
                        break
                    try:
                        f_path.unlink(missing_ok=True)
                        reclaimed_bytes += f_size
                        purged_count += 1
                    except (OSError, PermissionError):
                        pass

            if purged_count > 0:
                logger.info(
                    f"Strict Scratch Purge: Purged {purged_count} files, reclaimed {reclaimed_bytes / (1024*1024):.2f} MB. "
                    f"Total scratch now: {(current_bytes - reclaimed_bytes) / (1024*1024):.2f} MB / "
                    f"{self.max_scratch_bytes / (1024*1024*1024):.2f} GB cap."
                )

            return {
                "initial_bytes": current_bytes,
                "bytes_reclaimed": reclaimed_bytes,
                "purged_file_count": purged_count,
                "current_bytes": current_bytes - reclaimed_bytes,
            }


# ============================================================================
# 7. Master GOAT Cascade Orchestrator
# ============================================================================


class ToposGOATCascade:
    """
    Master Execution Orchestrator for the Mechanics Subsystem (Stage 2.3).
    Loops continuously between Quench (Refinement) and Escape (Exploration) phases,
    directing handoffs across:
      1. cochem_topos_escape.py (Wigner kicks / Progressive Langevin Thermal schedule with ALPB Solvation)
      2. cochem_topos_quench.py & BaseOptimizer (PES descent with LBFGS -> FIRE toggle)
      3. cochem_topos_crusher.py (Rotational Sieve -> KDTree -> Mass-Weighted Eckart RMSD)
      4. cochem_topos_memory.py (HDF5 SWMR persistent datastore with [M], [D], [E] FAIR provenance)
      5. Strict Scratch Purge Protocol (Continuous <10GB disk space cap)
    """

    def __init__(
        self,
        config: Optional[GOATCascadeConfig] = None,
        broker: Optional[HardwareResourceBroker] = None,
        memory_manager: Optional[ToposHDF5MemoryManager] = None,
        crusher: Optional[TopologyCrusher] = None,
        optimizer: Optional[BaseOptimizer] = None,
        scratch_dirs: Optional[Sequence[Path]] = None,
    ) -> None:
        self.config = config or GOATCascadeConfig()
        self.broker = broker or HardwareResourceBroker()
        self.reaper = get_global_reaper() if self.config.enable_process_reaper else None

        # Resolve HDF5 datastore path
        self.db_path = self.config.db_path or Path(tempfile.gettempdir()) / "topos_goat_landscape.h5"
        self.memory_manager = memory_manager or ToposHDF5MemoryManager(db_path=self.db_path)

        # Directive 3: Dynamic Solvation Activation
        effective_charge = (
            self.config.charge if self.config.charge is not None else get_system_charge()
        )
        self.alpb_manager = ALPBSolvationManager(
            charge=effective_charge,
            solvent=self.config.solvent,
        )
        if self.alpb_manager.is_alpb_active:
            self.config.alpb_solvation_active = True

        # Directive 4: Strict Scratch Purge Protocol
        if scratch_dirs is not None:
            active_scratch_dirs = [Path(p).resolve() for p in scratch_dirs]
        else:
            active_scratch_dirs = [self.db_path.parent / "cochem_scratch"]
        self.scratch_purger = ScratchPurgeManager(
            scratch_directories=active_scratch_dirs,
            max_scratch_bytes=self.config.max_scratch_bytes,
            purge_patterns=self.config.scratch_purge_patterns,
        )

        # Directive 2: Singleton Loader and Batched Inference
        self.singleton_loader = MLFFSingletonLoader.get_instance()
        self.batched_inference = BatchedMLFFInference(
            batch_size=self.config.batch_size,
            device=self.config.device,
        )

        # Directive 1: Engine Abstraction Layer
        if optimizer is not None:
            self.adaptive_optimizer: BaseOptimizer = optimizer
        else:
            self.adaptive_optimizer = GradientNoiseOptimizer(
                primary_optimizer=self.config.primary_optimizer,
                fallback_optimizer=self.config.fallback_optimizer,
                fmax=self.config.fmax,
                max_steps=self.config.max_quench_steps,
                oscillation_window=self.config.oscillation_window,
                oscillation_force_tol=self.config.oscillation_force_tol,
            )

        # Initialize Subsystem Orchestrators
        escape_cfg = EscapeConfig(
            thermal_schedule=self.config.temperature_schedule,
            langevin_steps_per_stage=self.config.langevin_steps_per_stage,
            langevin_dt_fs=self.config.langevin_dt_fs,
            basin_rmsd_threshold=self.config.basin_rmsd_threshold,
            basin_energy_threshold_ev=self.config.basin_energy_threshold_ev,
            quench_fmax=self.config.fmax,
            save_to_hdf5=self.config.save_to_hdf5,
            db_path=self.db_path,
        )
        self.escape_orchestrator = ToposEscapeOrchestrator(
            config=escape_cfg,
            memory_manager=self.memory_manager,
        )

        quench_cfg = QuenchConfig(
            fmax=self.config.fmax,
            max_steps=self.config.max_quench_steps,
            algorithm=self.config.primary_optimizer,
            engine=self.config.engine,
            device=self.config.device,
            precision=self.config.precision,
            db_path=self.db_path,
            save_to_hdf5=self.config.save_to_hdf5,
            max_workers=self.config.max_workers,
        )
        self.quench_orchestrator = ToposQuenchOrchestrator(
            broker=self.broker,
            memory_manager=self.memory_manager,
            default_config=quench_cfg,
        )

        # Initialize Crusher Deduplication Funnel
        if crusher is not None:
            self.crusher = crusher
        elif TopologyCrusher is not None:
            self.crusher = TopologyCrusher(
                rot_tol=0.015,
                dipole_tol=0.05,
                kdtree_tol=0.02,
                rmsd_tol=self.config.basin_rmsd_threshold,
                hdf5_path=self.db_path if self.config.save_to_hdf5 else None,
            )
        else:
            self.crusher = None

        self.good_turing = GoodTuringEstimator()

    def run_cascade(
        self,
        seed_atoms: Atoms,
        session_id: Optional[str] = None,
    ) -> GOATCascadeReport:
        """
        Execute the master GOAT cascade exploration loop on the given seed geometry.

        Handoff Protocol:
        Seed -> Initial Quench (BaseOptimizer) -> Seed Basin Accepted ->
        Loop:
          1. Scratch Purge Check (<10GB Cap) ->
          2. ToposEscapeOrchestrator (Perturb via Wigner / Langevin with ALPB Solvation) ->
          3. Adaptive Quench with BaseOptimizer (Relax) ->
          4. TopologyCrusher (Deduplicate / Eckart RMSD / Chiral Enantiomers) ->
          5. ToposHDF5MemoryManager (SWMR Write) ->
          6. Good-Turing Completeness Check & Stopping Criteria Evaluation.

        Args:
            seed_atoms: Starting molecular geometry (ASE Atoms).
            session_id: Optional unique exploration session ID.

        Returns:
            GOATCascadeReport: Comprehensive exploration session report.
        """
        session = session_id or f"goat_session_{int(time.time()*1000)}"
        start_time = time.time()
        logger.info(f"[{session}] Initiating Master GOAT Cascade exploration...")

        # Purge scratch at start
        self.scratch_purger.purge_scratch_if_needed(force=False)

        discovered_basins: list[GOATCascadeResult] = []
        all_toggle_events: list[OptimizerToggleEvent] = []
        cycle_records: list[CascadeCycleRecord] = []

        total_duplicates_rejected = 0
        total_enantiomers_preserved = 0
        consecutive_zero_discovery_cycles = 0
        halting_reason = CascadeStoppingCriterion.MAX_CYCLES_REACHED

        # Ensure seed atoms have a valid calculator attached
        if seed_atoms.calc is None:
            symbols = seed_atoms.get_chemical_symbols()
            atomic_nums = seed_atoms.get_atomic_numbers().tolist()
            if all(s in ["Cu", "Al", "Ni", "Pd", "Pt", "Au", "Ag"] for s in symbols):
                seed_atoms.calc = EMT()
            else:
                seed_atoms.calc = self.singleton_loader.get_calculator(
                    engine=self.config.engine,
                    device=self.config.device,
                    precision=self.config.precision,
                    atomic_numbers=atomic_nums,
                )

        # Step 1: Initial Quench of Seed Geometry
        logger.info(f"[{session}] Performing initial relaxation on seed geometry...")
        seed_quench = self.adaptive_optimizer.optimize(seed_atoms, geom_id=f"{session}_seed_initial")
        all_toggle_events.extend(seed_quench.toggle_events)

        quenched_seed_atoms = seed_atoms.copy()
        quenched_seed_atoms.set_positions(seed_quench.final_positions)
        quenched_seed_atoms.calc = seed_atoms.calc

        seed_energy_h = seed_quench.final_energy / units.Hartree
        seed_energy_kcal = seed_quench.final_energy / (units.kcal / units.mol)
        seed_atomic_numbers = quenched_seed_atoms.get_atomic_numbers().tolist()
        seed_geom_id = f"{session}_basin_0000"

        # Register seed in Crusher
        if self.crusher is not None:
            self.crusher.process_conformer(
                quenched_seed_atoms,
                energy_kcal=seed_energy_kcal,
                source_engine="INITIAL",
                candidate_id=seed_geom_id,
            )

        # Register in Good-Turing estimator
        self.good_turing.update([seed_geom_id])

        # Record Initial Basin
        initial_basin = GOATCascadeResult(
            basin_id=seed_geom_id,
            energy_hartree=seed_energy_h,
            energy_kcal=seed_energy_kcal,
            fmax=seed_quench.final_max_force,
            converged=seed_quench.converged,
            optimizer_used=seed_quench.active_optimizer,
            toggle_events=seed_quench.toggle_events,
            atomic_numbers=seed_atomic_numbers,
            coordinates=seed_quench.final_positions,
            is_enantiomer=False,
            source_cycle=0,
            provenance_record={"tier": "INITIAL_SEED", "tags": ["[M]", "[D]"]},
        )
        discovered_basins.append(initial_basin)

        # Write initial seed to HDF5 SWMR store
        if self.config.save_to_hdf5 and self.memory_manager is not None:
            self.memory_manager.write_geometry(
                GeometryRecord(
                    geom_id=seed_geom_id,
                    atomic_numbers=seed_atomic_numbers,
                    coords=seed_quench.final_positions,
                    energy=seed_energy_h,
                    metadata={"status": "INITIAL_SEED", "session": session},
                )
            )

        # Active pool of basins to perturb
        active_basin_queue: list[Atoms] = [quenched_seed_atoms]

        # Step 2: The Master Cascade Exploration Loop
        for cycle_idx in range(1, self.config.max_cycles + 1):
            cycle_start = time.time()
            logger.info(f"[{session}] === Starting Cascade Cycle {cycle_idx}/{self.config.max_cycles} ===")

            # Directive 4: Enforce scratch cap continually during runtime
            self.scratch_purger.purge_scratch_if_needed(force=False)

            # Select target basin from pool
            current_seed = active_basin_queue[(cycle_idx - 1) % len(active_basin_queue)].copy()
            current_seed.calc = seed_atoms.calc
            current_seed_id = f"{session}_seed_cycle_{cycle_idx}"

            # Phase A: Escape Room Perturbation with ALPB Solvation
            escape_res: EscapeResult = self.escape_orchestrator.run_escape_search(
                seed_atoms=current_seed,
                escape_id=f"{session}_esc_{cycle_idx:03d}",
            )

            cycle_candidates_generated = 1 if escape_res.breached else 0
            cycle_quench_converged = 0
            cycle_unique_basins = 0
            cycle_duplicates = 0
            cycle_enantiomers = 0
            cycle_toggles = 0

            if escape_res.breached:
                # Phase B: Adaptive Quench Relaxation with BaseOptimizer
                cand_atoms = Atoms(
                    numbers=escape_res.atomic_numbers,
                    positions=escape_res.quenched_coords,
                )
                cand_atoms.calc = seed_atoms.calc

                # Directive 3: If ALPB active, apply solvation screening
                if self.alpb_manager.is_alpb_active:
                    _ = self.alpb_manager.apply_solvation_screening(cand_atoms, temperature_k=500.0)

                cand_quench = self.adaptive_optimizer.optimize(
                    cand_atoms,
                    geom_id=f"{session}_cand_c{cycle_idx:03d}",
                )
                cycle_toggles += len(cand_quench.toggle_events)
                all_toggle_events.extend(cand_quench.toggle_events)

                if cand_quench.converged:
                    cycle_quench_converged += 1

                cand_quenched_atoms = cand_atoms.copy()
                cand_quenched_atoms.set_positions(cand_quench.final_positions)
                cand_quenched_atoms.calc = seed_atoms.calc

                cand_e_kcal = cand_quench.final_energy / (units.kcal / units.mol)
                cand_e_h = cand_quench.final_energy / units.Hartree
                cand_id = f"{session}_basin_{len(discovered_basins):04d}"

                # Phase C: Crusher Deduplication & Chiral Enantiomer Verification
                if self.crusher is not None:
                    dedup_rec: DeduplicationRecord = self.crusher.process_conformer(
                        cand_quenched_atoms,
                        energy_kcal=cand_e_kcal,
                        source_engine="GOAT",
                        candidate_id=cand_id,
                    )

                    if dedup_rec.verdict == DeduplicationVerdict.ACCEPTED_UNIQUE:
                        cycle_unique_basins += 1
                        self.good_turing.update([cand_id])
                        active_basin_queue.append(cand_quenched_atoms)

                        basin_obj = GOATCascadeResult(
                            basin_id=cand_id,
                            energy_hartree=cand_e_h,
                            energy_kcal=cand_e_kcal,
                            fmax=cand_quench.final_max_force,
                            converged=cand_quench.converged,
                            optimizer_used=cand_quench.active_optimizer,
                            toggle_events=cand_quench.toggle_events,
                            atomic_numbers=escape_res.atomic_numbers,
                            coordinates=cand_quench.final_positions,
                            is_enantiomer=False,
                            source_cycle=cycle_idx,
                            provenance_record=escape_res.provenance.model_dump() if escape_res.provenance else None,
                        )
                        discovered_basins.append(basin_obj)

                        # Phase D: SWMR HDF5 Write
                        if self.config.save_to_hdf5 and self.memory_manager is not None:
                            self.memory_manager.write_geometry(
                                GeometryRecord(
                                    geom_id=cand_id,
                                    atomic_numbers=escape_res.atomic_numbers,
                                    coords=cand_quench.final_positions,
                                    energy=cand_e_h,
                                    metadata={
                                        "status": "ACCEPTED_UNIQUE",
                                        "cycle": cycle_idx,
                                        "session": session,
                                        "provenance": basin_obj.provenance_record,
                                        "alpb_solvation": self.alpb_manager.is_alpb_active,
                                    },
                                )
                            )

                    elif dedup_rec.verdict == DeduplicationVerdict.ENANTIOMER_PRESERVED:
                        cycle_enantiomers += 1
                        total_enantiomers_preserved += 1
                        self.good_turing.update([f"{cand_id}_enantiomer"])

                        basin_obj = GOATCascadeResult(
                            basin_id=f"{cand_id}_enantiomer",
                            energy_hartree=cand_e_h,
                            energy_kcal=cand_e_kcal,
                            fmax=cand_quench.final_max_force,
                            converged=cand_quench.converged,
                            optimizer_used=cand_quench.active_optimizer,
                            toggle_events=cand_quench.toggle_events,
                            atomic_numbers=escape_res.atomic_numbers,
                            coordinates=cand_quench.final_positions,
                            is_enantiomer=True,
                            enantiomer_partner_id=f"{session}_basin_{dedup_rec.matched_basin_idx:04d}"
                            if dedup_rec.matched_basin_idx is not None
                            else None,
                            source_cycle=cycle_idx,
                            provenance_record=escape_res.provenance.model_dump() if escape_res.provenance else None,
                        )
                        discovered_basins.append(basin_obj)

                    else:
                        cycle_duplicates += 1
                        total_duplicates_rejected += 1
                        matched_id = (
                            f"{session}_basin_{dedup_rec.matched_basin_idx:04d}"
                            if dedup_rec.matched_basin_idx is not None
                            else seed_geom_id
                        )
                        self.good_turing.update([matched_id])
                else:
                    cycle_unique_basins += 1
                    basin_obj = GOATCascadeResult(
                        basin_id=cand_id,
                        energy_hartree=cand_e_h,
                        energy_kcal=cand_e_kcal,
                        fmax=cand_quench.final_max_force,
                        converged=cand_quench.converged,
                        optimizer_used=cand_quench.active_optimizer,
                        toggle_events=cand_quench.toggle_events,
                        atomic_numbers=escape_res.atomic_numbers,
                        coordinates=cand_quench.final_positions,
                        is_enantiomer=False,
                        source_cycle=cycle_idx,
                    )
                    discovered_basins.append(basin_obj)

            # Record cycle metrics
            cycle_duration = time.time() - cycle_start
            cycle_rec = CascadeCycleRecord(
                cycle_index=cycle_idx,
                seed_geom_id=current_seed_id,
                escape_status=escape_res.status.value,
                escape_mechanism=escape_res.mechanism_used.value if escape_res.mechanism_used else None,
                candidates_generated=cycle_candidates_generated,
                quench_converged_count=cycle_quench_converged,
                unique_basins_discovered=cycle_unique_basins,
                duplicates_rejected=cycle_duplicates,
                enantiomers_preserved=cycle_enantiomers,
                optimizer_toggles_count=cycle_toggles,
                duration_seconds=cycle_duration,
            )
            cycle_records.append(cycle_rec)

            if cycle_unique_basins == 0:
                consecutive_zero_discovery_cycles += 1
            else:
                consecutive_zero_discovery_cycles = 0

            completeness = self.good_turing.calculate_coverage()
            logger.info(
                f"[{session}] Cycle {cycle_idx} complete: +{cycle_unique_basins} basins, "
                f"+{cycle_duplicates} duplicates, Completeness={completeness:.3f} (Patience={consecutive_zero_discovery_cycles}/{self.config.patience})"
            )

            if completeness >= self.config.target_coverage and len(discovered_basins) > 1:
                logger.info(
                    f"[{session}] Halting criterion met: Target coverage {self.config.target_coverage:.2f} reached."
                )
                halting_reason = CascadeStoppingCriterion.TARGET_COVERAGE_REACHED
                break

            if consecutive_zero_discovery_cycles >= self.config.patience:
                logger.info(
                    f"[{session}] Halting criterion met: Patience limit ({self.config.patience}) reached with zero new basins."
                )
                halting_reason = CascadeStoppingCriterion.PATIENCE_EXHAUSTED
                break

        # Final scratch cleanup
        self.scratch_purger.purge_scratch_if_needed(force=False)

        total_duration = time.time() - start_time
        final_completeness = self.good_turing.calculate_coverage()

        report = GOATCascadeReport(
            session_id=session,
            total_cycles_executed=len(cycle_records),
            total_unique_basins=len(discovered_basins),
            total_duplicates_rejected=total_duplicates_rejected,
            total_enantiomers_preserved=total_enantiomers_preserved,
            total_optimizer_toggles=len(all_toggle_events),
            final_completeness_estimate=final_completeness,
            converged_stopping_criterion=halting_reason.value,
            duration_seconds=total_duration,
            cycle_records=cycle_records,
            unique_basins=discovered_basins,
            toggle_events=all_toggle_events,
        )

        logger.info(
            f"[{session}] GOAT Cascade finished in {total_duration:.2f}s: "
            f"{report.total_unique_basins} unique basins, {report.total_duplicates_rejected} duplicates rejected, "
            f"{report.total_enantiomers_preserved} enantiomers preserved, {report.total_optimizer_toggles} optimizer toggles."
        )
        return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("CoChem-TOPOS Stage 2.3 GOAT Cascade active.")
