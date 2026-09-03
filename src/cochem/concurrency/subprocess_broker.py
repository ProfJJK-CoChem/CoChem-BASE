"""Deterministic Subprocess Broker & Fault Ladder.
Physics-aware error recovery, race-free subprocess execution, and Job Object lifecycle management.
Strictly adheres to Zero-Mock mandate and authentic subprocess execution.
"""

from __future__ import annotations

import atexit
import ctypes
import dataclasses
import enum
import logging
import os
import pathlib
import signal
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from cochem.core.context import assert_writable_path
from cochem.core.hardware.topology import TopologyDiscoveryEngine

logger = logging.getLogger("cochem.concurrency.subprocess_broker")


class FailureCategory(enum.Enum):
    """Classification of quantum chemistry driver computational failures."""

    SCF_NON_CONVERGENCE = "SCF_NON_CONVERGENCE"
    GRID_INTEGRATION_FAILURE = "GRID_INTEGRATION_FAILURE"
    GEOMETRY_OPTIMIZATION_STAGNATION = "GEOMETRY_OPTIMIZATION_STAGNATION"
    CONFORMER_SEARCH_FAILURE = "CONFORMER_SEARCH_FAILURE"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"


@dataclasses.dataclass(slots=True, frozen=True)
class SubprocessExecutionResult:
    """Immutable execution report from the Subprocess Broker."""

    success: bool
    stdout: str
    stderr: str
    returncode: int
    retries_attempted: int
    final_params: Dict[str, Any]


class DiagnosticTriageEngine:
    """Diagnostic Triage and Solver Remediation Matrix."""

    def triage_failure(
        self,
        engine: str,
        log_output: str,
        exit_code: int,
        current_state: Dict[str, Any],
    ) -> Tuple[FailureCategory, Dict[str, Any]]:
        """Diagnose computational failure from log output and escalate parameters along solver ladders."""
        upper_log = log_output.upper()
        engine_upper = engine.upper()
        new_state = dict(current_state)

        # 1. SCF Non-Convergence Escalation
        if "SCF NOT CONVERGED" in upper_log or "CONVERGENCE FAILED" in upper_log or "NOT CONVERGE" in upper_log:
            if engine_upper == "ORCA":
                orca_ladder = ["PModel", "Auto", "HCore"]
                current_guess = str(current_state.get("guess", "PModel"))
                next_idx = orca_ladder.index(current_guess) + 1 if current_guess in orca_ladder else 1
                new_state["guess"] = orca_ladder[min(next_idx, len(orca_ladder) - 1)]
                return FailureCategory.SCF_NON_CONVERGENCE, new_state

            elif engine_upper == "CFOUR":
                cfour_ladder = ["CORE", "SOCORE", "OLD"]
                current_guess = str(current_state.get("guess", "CORE"))
                next_idx = cfour_ladder.index(current_guess) + 1 if current_guess in cfour_ladder else 1
                new_state["guess"] = cfour_ladder[min(next_idx, len(cfour_ladder) - 1)]
                return FailureCategory.SCF_NON_CONVERGENCE, new_state

            elif engine_upper == "PYSCF":
                pyscf_ladder = ["minao", "1e", "atom"]
                current_guess = str(current_state.get("init_guess", "minao"))
                next_idx = pyscf_ladder.index(current_guess) + 1 if current_guess in pyscf_ladder else 1
                new_state["init_guess"] = pyscf_ladder[min(next_idx, len(pyscf_ladder) - 1)]
                return FailureCategory.SCF_NON_CONVERGENCE, new_state

        # 2. Grid Integration Failure Escalation
        if "GRID" in upper_log or "DEFGRID" in upper_log or "INTEGRATION ERROR" in upper_log:
            grid_ladder = ["defgrid1", "defgrid2", "defgrid3"]
            current_grid = str(current_state.get("grid", "defgrid1"))
            next_idx = grid_ladder.index(current_grid) + 1 if current_grid in grid_ladder else 1
            new_state["grid"] = grid_ladder[min(next_idx, len(grid_ladder) - 1)]
            return FailureCategory.GRID_INTEGRATION_FAILURE, new_state

        # 3. Geometry Optimization Stagnation
        if "GEOMETRY OPTIMIZATION" in upper_log or "TRUST RADIUS" in upper_log or "LINE SEARCH" in upper_log:
            hessian_ladder = ["Lindh", "GFN2-xTB", "r2SCAN-3c"]
            current_hess = str(current_state.get("model_hessian", "Lindh"))
            next_idx = hessian_ladder.index(current_hess) + 1 if current_hess in hessian_ladder else 1
            new_state["model_hessian"] = hessian_ladder[min(next_idx, len(hessian_ladder) - 1)]
            return FailureCategory.GEOMETRY_OPTIMIZATION_STAGNATION, new_state

        # 4. CREST / Conformer Search Failure
        if "CREST" in upper_log or "GOAT" in upper_log or "INTERATOMIC DISTANCE" in upper_log:
            method_ladder = ["GFN2-xTB", "GFN-FF"]
            current_method = str(current_state.get("method", "GFN2-xTB"))
            next_idx = method_ladder.index(current_method) + 1 if current_method in method_ladder else 1
            new_state["method"] = method_ladder[min(next_idx, len(method_ladder) - 1)]
            return FailureCategory.CONFORMER_SEARCH_FAILURE, new_state

        return FailureCategory.UNKNOWN_FAILURE, new_state


class SubprocessBroker:
    """Broker managing child process lifecycle, Win32 Job Objects, and remediation ladders."""

    def __init__(
        self,
        engine_name: str,
        initial_params: Optional[Dict[str, Any]] = None,
        scratch_dir: Optional[Union[pathlib.Path, str]] = None,
        max_retries: int = 3,
    ) -> None:
        self.engine_name: str = engine_name
        self.current_params: Dict[str, Any] = dict(initial_params or {})
        self.max_retries: int = max(1, int(max_retries))
        self.triage: DiagnosticTriageEngine = DiagnosticTriageEngine()
        self.topology_engine: TopologyDiscoveryEngine = TopologyDiscoveryEngine()

        if scratch_dir is not None:
            self.scratch_dir: pathlib.Path = pathlib.Path(scratch_dir).resolve()
            assert_writable_path(self.scratch_dir)
            self.scratch_dir.mkdir(parents=True, exist_ok=True)
        else:
            default_scratch = pathlib.Path.cwd() / "scratch"
            assert_writable_path(default_scratch)
            default_scratch.mkdir(parents=True, exist_ok=True)
            self.scratch_dir = default_scratch

        self._job_handle: Optional[Any] = None
        self._init_process_group_guard()
        atexit.register(self.cleanup)

    def _init_process_group_guard(self) -> None:
        """Initialize Windows Job Object with KILL_ON_JOB_CLOSE or configure POSIX process group."""
        if sys.platform == "win32":
            try:
                # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
                job_handle = ctypes.windll.kernel32.CreateJobObjectW(None, None)
                if job_handle:
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
                    info.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

                    JobObjectExtendedLimitInformation = 9
                    ctypes.windll.kernel32.SetInformationJobObject(
                        job_handle,
                        JobObjectExtendedLimitInformation,
                        ctypes.byref(info),
                        ctypes.sizeof(info),
                    )
                    self._job_handle = job_handle
            except Exception as job_err:
                logger.debug("Windows Job Object initialization bypassed: %s", job_err)

    def assign_to_job(self, proc: subprocess.Popen[Any]) -> None:
        """Assign subprocess handle to Win32 Job Object."""
        if sys.platform == "win32" and self._job_handle is not None:
            try:
                # Open process handle with PROCESS_SET_QUOTA | PROCESS_TERMINATE
                PROCESS_ALL_ACCESS = 0x1F0FFF
                p_handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, proc.pid)
                if p_handle:
                    ctypes.windll.kernel32.AssignProcessToJobObject(self._job_handle, p_handle)
                    ctypes.windll.kernel32.CloseHandle(p_handle)
            except Exception as assign_err:
                logger.debug("Could not assign PID %d to Job Object: %s", proc.pid, assign_err)

    def execute_with_remediation(
        self,
        command: List[str],
        timeout_sec: float = 60.0,
    ) -> SubprocessExecutionResult:
        """Execute command under deterministic fault ladder with up to MAX_RETRIES remediation cycles."""
        retries = 0
        last_stdout = ""
        last_stderr = ""
        last_code = 1

        while retries < self.max_retries:
            env = self.topology_engine.get_worker_env()
            kwargs: Dict[str, Any] = {
                "cwd": str(self.scratch_dir),
                "env": env,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
            }

            if sys.platform != "win32":
                kwargs["start_new_session"] = True

            try:
                proc = subprocess.Popen(command, **kwargs)
                self.assign_to_job(proc)

                try:
                    out, err = proc.communicate(timeout=timeout_sec)
                    code = proc.returncode
                except subprocess.TimeoutExpired:
                    self.terminate_process_tree(proc)
                    out, err = "", "Subprocess execution timed out"
                    code = -1

                last_stdout = out
                last_stderr = err
                last_code = code

                if code == 0:
                    return SubprocessExecutionResult(
                        success=True,
                        stdout=last_stdout,
                        stderr=last_stderr,
                        returncode=0,
                        retries_attempted=retries,
                        final_params=self.current_params,
                    )

                # Execute diagnostic triage on error output
                cat, updated_params = self.triage.triage_failure(
                    engine=self.engine_name,
                    log_output=f"{last_stdout}\n{last_stderr}",
                    exit_code=last_code,
                    current_state=self.current_params,
                )

                self.current_params = updated_params
                retries += 1
                logger.warning(
                    "Subprocess failure (attempt %d/%d) classified as %s. Escalated parameters: %s",
                    retries,
                    self.max_retries,
                    cat.value,
                    self.current_params,
                )

            except Exception as exec_err:
                last_stderr = str(exec_err)
                last_code = 1
                retries += 1

        return SubprocessExecutionResult(
            success=False,
            stdout=last_stdout,
            stderr=last_stderr,
            returncode=last_code,
            retries_attempted=retries,
            final_params=self.current_params,
        )

    def terminate_process_tree(self, proc: subprocess.Popen[Any], grace_timeout: float = 3.0) -> None:
        """Recursively terminate worker process tree with SIGTERM escalated to SIGKILL."""
        pid = proc.pid
        if sys.platform != "win32":
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
                start = time.time()
                while time.time() - start < grace_timeout:
                    if proc.poll() is not None:
                        return
                    time.sleep(0.1)
                os.killpg(pgid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
        else:
            try:
                proc.terminate()
                proc.wait(timeout=grace_timeout)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def cleanup(self) -> None:
        """Close Job Object handle and release scratch resources."""
        if sys.platform == "win32" and self._job_handle is not None:
            try:
                ctypes.windll.kernel32.CloseHandle(self._job_handle)
            except Exception:
                pass
            self._job_handle = None
