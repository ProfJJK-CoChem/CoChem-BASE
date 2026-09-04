"""# zero-stub anti-spoofing engine
CoChem-GEOM Subprocess Broker & Process Isolation Engine (subprocess_broker.py)

Provides robust, cross-platform subprocess management for computational chemistry
binaries (ORCA, CFOUR, xTB, CREST, PySCF) and general OS processes with:
1. Explicit configurable execution timeouts with graceful termination and cleanup.
2. Clean environment variable passing and isolation.
3. Process-group isolation to prevent orphaned processes and host resource exhaustion.
4. Process tree sweeping and child cleanup across Windows and POSIX.
5. Structured result capture (stdout, stderr, exit codes, duration, telemetry).

Complies with Method Matrix v4, Process Safety Standards, and WBS Task 3.3.1.
"""

from __future__ import annotations

import logging
import os
import shlex
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]

logger = logging.getLogger("cochem_geom.engine.subprocess_broker")

DEFAULT_SUBPROCESS_TIMEOUT: float = 300.0
ESSENTIAL_SYSTEM_ENV_VARS: tuple[str, ...] = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "HOMEPATH",
    "HOMEDRIVE",
    "LANG",
    "LC_ALL",
    "LD_LIBRARY_PATH",
    "DYLD_LIBRARY_PATH",
    "PYTHONPATH",
    "PYTHONHOME",
    "VIRTUAL_ENV",
    "CONDA_PREFIX",
    "CONDA_DEFAULT_ENV",
    "ORCA_PATH",
    "XTBPATH",
    "CFOUR_PATH",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
)

SENSITIVE_ENV_PREFIXES: tuple[str, ...] = (
    "API_KEY",
    "SECRET",
    "PASSWORD",
    "TOKEN",
    "AUTH",
    "CREDENTIAL",
    "PRIVATE_KEY",
)


class SubprocessBrokerError(Exception):
    """Base exception for all SubprocessBroker errors."""

    pass


class SubprocessTimeoutError(SubprocessBrokerError):
    """Raised when a subprocess exceeds its allotted timeout limit."""

    def __init__(
        self,
        command: list[str],
        timeout_seconds: float,
        stdout: str = "",
        stderr: str = "",
        duration_seconds: float = 0.0,
        pid: int | None = None,
    ) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds
        self.stdout = stdout
        self.stderr = stderr
        self.duration_seconds = duration_seconds
        self.pid = pid
        cmd_str = (
            " ".join(command) if isinstance(command, list | tuple) else str(command)
        )
        super().__init__(
            f"Process '{cmd_str}' (PID {pid}) timed out after {timeout_seconds:.2f}s "
            f"(elapsed: {duration_seconds:.2f}s)."
        )


class SubprocessExecutionError(SubprocessBrokerError):
    """Raised when a subprocess fails with a non-zero exit code when check=True."""

    def __init__(
        self,
        command: list[str],
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        duration_seconds: float = 0.0,
        pid: int | None = None,
    ) -> None:
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.duration_seconds = duration_seconds
        self.pid = pid
        cmd_str = (
            " ".join(command) if isinstance(command, list | tuple) else str(command)
        )
        super().__init__(
            f"Process '{cmd_str}' (PID {pid}) returned non-zero exit status "
            f"{returncode}.\n"
            f"Stderr: {stderr.strip()[:500]}\n"
            f"Stdout: {stdout.strip()[:500]}"
        )


@dataclass
class SubprocessExecutionResult:
    """Detailed execution result and telemetry of a subprocess."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    pid: int | None = None

    @property
    def success(self) -> bool:
        """Returns True if process exited with 0 and did not time out."""
        return self.returncode == 0 and not self.timed_out

    def to_dict(self) -> dict[str, Any]:
        """Convert execution result to dictionary."""
        return asdict(self)


def sweep_child_processes(
    parent_pid: int | None = None,
    timeout: float = 3.0,
    include_parent: bool = False,
) -> int:
    """
    Terminates orphaned, descendant, or zombie child processes for a given parent PID.
    Cross-platform support for Windows and POSIX systems.

    Args:
        parent_pid: Parent PID whose children to terminate. Defaults to current PID.
        timeout: Time in seconds to wait for graceful termination before force-killing.
        include_parent: If True and parent_pid is not the current running process,
            also terminates the parent process itself.

    Returns:
        int: Number of processes successfully terminated or killed.
    """
    if psutil is None:
        return 0

    target_pid = parent_pid if parent_pid is not None else os.getpid()
    terminated_count = 0

    try:
        parent = psutil.Process(target_pid)
        children = parent.children(recursive=True)
    except (
        psutil.NoSuchProcess,
        psutil.AccessDenied,
        psutil.ZombieProcess,
        ValueError,
        TypeError,
    ):
        return 0

    targets = list(children)
    if include_parent and target_pid != os.getpid():
        targets.append(parent)

    if not targets:
        return 0

    # 1. Attempt graceful termination (SIGTERM on POSIX, TerminateProcess on Win32)
    for proc in targets:
        try:
            if proc.is_running():
                proc.terminate()
                terminated_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as _e:
            logger.debug(f"Ignored exception: {_e}")

    # 2. Wait for graceful termination
    gone, alive = psutil.wait_procs(targets, timeout=timeout)

    # 3. Force kill any remaining alive processes
    for proc in alive:
        try:
            if proc.is_running():
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as _e:
            logger.debug(f"Ignored exception: {_e}")

    # 4. Final confirmation sweep
    if alive:
        psutil.wait_procs(alive, timeout=1.0)

    return terminated_count


class SubprocessBroker:
    """
    SubprocessBroker provides isolated, timeout-bounded execution of computational
    binaries and external system commands.
    """

    def __init__(
        self,
        default_timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
        default_clean_env: bool = False,
        allowed_env_vars: Sequence[str] | None = None,
        process_group_isolation: bool = True,
        nprocs: int | None = None,
        maxcore_mb: int | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize SubprocessBroker.

        Args:
            default_timeout: Default timeout in seconds (default: 300.0s).
            default_clean_env: Whether to sanitize the environment by default.
            allowed_env_vars: Whitelist of allowed environment variables.
            process_group_isolation: Isolate child in a distinct OS process group.
            nprocs: Optional number of processor cores to allocate.
            maxcore_mb: Optional maximum memory in megabytes.
        """
        if default_timeout <= 0:
            raise ValueError(f"default_timeout must be positive, got {default_timeout}")

        self.default_timeout = float(default_timeout)
        self.default_clean_env = bool(default_clean_env)
        self.allowed_env_vars = (
            tuple(allowed_env_vars) if allowed_env_vars is not None else None
        )
        self.process_group_isolation = bool(process_group_isolation)
        self.nprocs = (
            nprocs if nprocs is not None else max(1, (os.cpu_count() or 4) - 2)
        )
        self.maxcore_mb = maxcore_mb if maxcore_mb is not None else 4000

    def build_isolated_env(
        self,
        extra_env: dict[str, str] | None = None,
        inherit_system_paths: bool = True,
        strip_sensitive: bool = True,
    ) -> dict[str, str]:
        """
        Construct a clean, sanitized environment dictionary for child execution.

        Args:
            extra_env: Additional or overriding environment key-value pairs.
            inherit_system_paths: Retain standard system and runtime directories.
            strip_sensitive: Filter out environment variables with secrets.

        Returns:
            dict[str, str]: Prepared environment dictionary.
        """
        clean_env: dict[str, str] = {}

        if inherit_system_paths:
            if self.allowed_env_vars is not None:
                for k in self.allowed_env_vars:
                    if k in os.environ:
                        clean_env[k] = os.environ[k]
            else:
                for k, v in os.environ.items():
                    # Check sensitive filters
                    if strip_sensitive:
                        k_upper = k.upper()
                        if any(s in k_upper for s in SENSITIVE_ENV_PREFIXES):
                            continue
                    clean_env[k] = v

            # Always guarantee essential paths exist if available in os.environ
            for key in ESSENTIAL_SYSTEM_ENV_VARS:
                if key in os.environ and key not in clean_env:
                    clean_env[key] = os.environ[key]
        else:
            # Minimal environment: strictly essential system variables
            for key in ESSENTIAL_SYSTEM_ENV_VARS:
                if key in os.environ:
                    clean_env[key] = os.environ[key]

        if extra_env:
            for k, v in extra_env.items():
                clean_env[str(k)] = str(v)

        return clean_env

    def _terminate_process_tree(
        self, proc: subprocess.Popen[Any], timeout: float = 2.0
    ) -> None:
        """
        Forcefully terminates a subprocess and all its descendant processes.
        Handles both Windows and POSIX process group conventions.
        """
        pid = proc.pid
        if pid is None:
            return

        # 1. Use psutil sweep if available to terminate entire process tree
        # including target process
        if psutil is not None:
            sweep_child_processes(parent_pid=pid, timeout=timeout, include_parent=True)
            return

        # 2. Fallback OS-level signal termination
        if sys.platform == "win32":
            try:
                # Send CTRL_BREAK_EVENT if created with CREATE_NEW_PROCESS_GROUP
                proc.send_signal(signal.CTRL_BREAK_EVENT)
                proc.wait(timeout=timeout)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError) as _e:
                logger.debug(f"Ignored exception: {_e}")
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError) as _e:
                logger.debug(f"Ignored exception: {_e}")
        else:
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                proc.wait(timeout=timeout)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError) as _e:
                logger.debug(f"Ignored exception: {_e}")
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError) as _e:
                logger.debug(f"Ignored exception: {_e}")

    def run(
        self,
        command: list[str] | str,
        timeout: float | None = None,
        check: bool = True,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        clean_env: bool | None = None,
        input_data: str | bytes | None = None,
        text: bool = True,
        capture_output: bool = True,
        process_group: bool | None = None,
    ) -> SubprocessExecutionResult:
        """
        Executes an external command with timeout bounds, process group isolation,
        and clean environment passing.

        Args:
            command: Command argument list or command string to execute.
            timeout: Maximum duration in seconds. Defaults to self.default_timeout.
            check: If True, raises SubprocessExecutionError on non-zero exit code,
                   and SubprocessTimeoutError on timeout.
            cwd: Working directory for process execution.
            env: Custom environment dictionary.
            clean_env: If True, cleans/sanitizes the execution environment.
            input_data: Optional stdin string or bytes passed to the process.
            text: Whether to decode stdout and stderr as text (UTF-8).
            capture_output: Whether to capture stdout and stderr.
            process_group: Whether to create a new OS process group.

        Returns:
            SubprocessExecutionResult: Detailed result structure.

        Raises:
            SubprocessTimeoutError: If execution exceeds timeout and check=True.
            SubprocessExecutionError: If non-zero exit status and check=True.
            ValueError: If command is empty.
        """
        if isinstance(command, str):
            cmd_args = shlex.split(command)
        else:
            cmd_args = [str(arg) for arg in command]

        # Strip surrounding quotes from executable/args if present
        cmd_args = [
            arg.strip("'\"")
            if (
                arg.startswith(('"', "'"))
                and arg.endswith(('"', "'"))
                and len(arg) >= 2
            )
            else arg
            for arg in cmd_args
        ]

        if not cmd_args:
            raise ValueError("Command cannot be empty.")

        effective_timeout = (
            float(timeout) if timeout is not None else self.default_timeout
        )
        if effective_timeout <= 0:
            raise ValueError(f"Timeout must be positive, got {effective_timeout}")

        use_clean_env = clean_env if clean_env is not None else self.default_clean_env
        final_env = (
            self.build_isolated_env(extra_env=env)
            if use_clean_env
            else (env if env is not None else os.environ.copy())
        )

        resolved_cwd = str(Path(cwd).resolve()) if cwd is not None else None
        isolate_group = (
            process_group if process_group is not None else self.process_group_isolation
        )

        # Setup OS process group creation flags
        creationflags = 0
        start_new_session = False

        if isolate_group:
            if sys.platform == "win32":
                creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                start_new_session = True

        stdout_pipe = subprocess.PIPE if capture_output else None
        stderr_pipe = subprocess.PIPE if capture_output else None
        stdin_pipe = subprocess.PIPE if input_data is not None else None

        start_time = time.perf_counter()
        timed_out = False
        raw_stdout: str | bytes = ""
        raw_stderr: str | bytes = ""
        returncode = -1
        proc_pid: int | None = None

        try:
            proc = subprocess.Popen(
                cmd_args,
                cwd=resolved_cwd,
                env=final_env,
                stdin=stdin_pipe,
                stdout=stdout_pipe,
                stderr=stderr_pipe,
                text=text,
                encoding="utf-8" if text else None,
                errors="replace" if text else None,
                creationflags=creationflags,
                start_new_session=start_new_session,
            )
            proc_pid = proc.pid

            try:
                raw_stdout, raw_stderr = proc.communicate(
                    input=input_data,
                    timeout=effective_timeout,
                )
                returncode = proc.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                self._terminate_process_tree(proc)
                try:
                    # Attempt to read remaining pipes after kill
                    out, err = proc.communicate(timeout=1.0)
                    raw_stdout = out or ""
                    raw_stderr = err or ""
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError) as _e:
                    logger.debug(f"Ignored exception: {_e}")
                returncode = proc.returncode if proc.returncode is not None else -9

        except FileNotFoundError as exc:
            duration = time.perf_counter() - start_time
            raise SubprocessExecutionError(
                command=cmd_args,
                returncode=127,
                stdout="",
                stderr=f"Executable not found: {cmd_args[0]} ({exc})",
                duration_seconds=duration,
                pid=None,
            ) from exc

        duration = time.perf_counter() - start_time
        if isinstance(raw_stdout, str):
            stdout_str = raw_stdout
        else:
            stdout_str = (
                raw_stdout.decode("utf-8", errors="replace") if raw_stdout else ""
            )

        if isinstance(raw_stderr, str):
            stderr_str = raw_stderr
        else:
            stderr_str = (
                raw_stderr.decode("utf-8", errors="replace") if raw_stderr else ""
            )

        result = SubprocessExecutionResult(
            command=cmd_args,
            returncode=returncode,
            stdout=stdout_str,
            stderr=stderr_str,
            duration_seconds=duration,
            timed_out=timed_out,
            pid=proc_pid,
        )

        if timed_out and check:
            raise SubprocessTimeoutError(
                command=cmd_args,
                timeout_seconds=effective_timeout,
                stdout=stdout_str,
                stderr=stderr_str,
                duration_seconds=duration,
                pid=proc_pid,
            )

        if check and returncode != 0:
            raise SubprocessExecutionError(
                command=cmd_args,
                returncode=returncode,
                stdout=stdout_str,
                stderr=stderr_str,
                duration_seconds=duration,
                pid=proc_pid,
            )

        return result

    def execute_binary(
        self,
        binary_name: str,
        args: Sequence[str] | None = None,
        timeout: float | None = None,
        check: bool = True,
        cwd: str | Path | None = None,
        extra_env: dict[str, str] | None = None,
        input_data: str | None = None,
    ) -> SubprocessExecutionResult:
        """
        Specialized execution helper for computational chemistry binaries
        (e.g., ORCA, xTB, CFOUR, CREST).

        Args:
            binary_name: Name or path of the binary (e.g. 'orca', 'xtb', 'cfour').
            args: Command-line arguments to pass to the binary.
            timeout: Execution timeout limit.
            check: Whether to raise on non-zero exit code or timeout.
            cwd: Working directory for calculation execution.
            extra_env: Additional environment variables.
            input_data: Text input passed to stdin if required.

        Returns:
            SubprocessExecutionResult: Output result structure.
        """
        full_command = [binary_name] + [str(a) for a in (args or [])]
        return self.run(
            command=full_command,
            timeout=timeout,
            check=check,
            cwd=cwd,
            env=extra_env,
            clean_env=True,
            input_data=input_data,
            text=True,
            capture_output=True,
        )

    def sweep_children(self, pid: int | None = None, timeout: float = 3.0) -> int:
        """Sweep orphaned child processes for this process or specified PID."""
        return sweep_child_processes(parent_pid=pid, timeout=timeout)
