"""
CoChem Stage 0 Orchestration: DependencyManager & Dynamic Silo Provisioning Engine.
Production-grade dependency management, pip/conda subprocess brokering,
idempotent transactional staging, automated rollback protocol, Dynamic Version Walking,
local wheel fallback resolution, and workspace sterility enforcement.

SRS Document 2 Part 2, SRS Document 4, and SRS Document 5 Compliant.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Configure internal module logger
logger = logging.getLogger("CoChem-DependencyManager")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# =============================================================================
# 1. EXCEPTIONS
# =============================================================================


class DependencyManagerError(RuntimeError):
    """Base exception for all DependencyManager execution failures."""


class RollbackError(DependencyManagerError):
    """Raised when an error occurs while attempting to rollback staged resources."""


class PipExecutionError(DependencyManagerError):
    """Raised when a pip subprocess execution fails under strict check mode."""


class CondaExecutionError(DependencyManagerError):
    """Raised when a conda/mamba subprocess execution fails under strict check mode."""


class VersionWalkingError(DependencyManagerError):
    """Raised when Dynamic Version Walking fails to resolve a working Python environment."""


# =============================================================================
# 2. PYDANTIC V2 DATA MODELS
# =============================================================================


class SubprocessExecutionRecord(BaseModel):
    """Structured record of a subprocess execution."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    command: List[str] = Field(..., description="Executed command line arguments")
    returncode: int = Field(..., description="Subprocess return code")
    stdout: str = Field(default="", description="Captured standard output")
    stderr: str = Field(default="", description="Captured standard error")
    duration_seconds: float = Field(default=0.0, description="Wall-clock duration in seconds")
    success: bool = Field(default=False, description="Whether command succeeded (returncode == 0)")
    executable_path: Optional[str] = Field(default=None, description="Resolved executable path")


class PipExecutionResult(SubprocessExecutionRecord):
    """Execution record specific to pip subprocess calls."""


class CondaExecutionResult(SubprocessExecutionRecord):
    """Execution record specific to conda/mamba subprocess calls."""


class DynamicVersionWalkStep(BaseModel):
    """Audit record for a single step in the Dynamic Version Walking resolution chain."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    attempted_version: str = Field(..., description="Python minor version evaluated (e.g. '3.11')")
    success: bool = Field(..., description="Whether version evaluation or compilation succeeded")
    fallback_wheel_found: Optional[str] = Field(
        default=None, description="Path to local fallback wheel/tarball if discovered"
    )
    error_summary: Optional[str] = Field(
        default=None, description="Diagnostic error summary if unsuccessful"
    )
    duration_seconds: float = Field(default=0.0, description="Step evaluation duration in seconds")

    @field_validator("attempted_version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        if not re.match(r"^\d+\.\d+(\.\d+)?$", v.strip()):
            raise ValueError(f"Invalid Python version format: {v}")
        return v.strip()


class DynamicVersionWalkingResult(BaseModel):
    """Aggregated result of Dynamic Version Walking and local wheel fallback resolution."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    initial_version: str = Field(default="3.11", description="Initial target Python version")
    target_version: str = Field(default="3.11", description="Target version requested")
    version_chain: List[str] = Field(
        default_factory=lambda: ["3.12", "3.11", "3.10", "3.9"],
        description="Evaluation sequence for minor Python versions",
    )
    resolved_version: Optional[str] = Field(
        default=None, description="Resolved compatible Python version"
    )
    used_local_fallback: bool = Field(
        default=False, description="Whether a local fallback wheel/archive was utilized"
    )
    fallback_binary_path: Optional[str] = Field(
        default=None, description="Path to local fallback package if used"
    )
    steps: List[DynamicVersionWalkStep] = Field(
        default_factory=list, description="Step-by-step resolution trail"
    )
    status: str = Field(default="PASSED", description="Outcome status of version walking")


# =============================================================================
# 3. COMPILATION & ABI ERROR PATTERN RECOGNITION
# =============================================================================

# Authentic error signatures for C++ compilation, linker errors, and Python ABI mismatches
ABI_COMPILATION_PATTERNS: List[Tuple[str, str]] = [
    (r"command\s+['\"].*?(gcc|g\+\+|clang|clang\+\+|cl\.exe)['\"]\s+failed", "COMPILATION_ERROR"),
    (r"gcc:\s+error:", "COMPILATION_ERROR"),
    (r"fatal error:\s+Python\.h:\s+No such file or directory", "MISSING_PYTHON_HEADER"),
    (r"Microsoft Visual C\+\+\s+\d+\.\d+.*?\s+is required", "COMPILATION_ERROR"),
    (r"error:\s+command\s+['\"].*?['\"]\s+failed with exit status", "COMPILATION_ERROR"),
    (r"error:\s+command\s+['\"].*?['\"]\s+failed with exit code", "COMPILATION_ERROR"),
    (r"ABI\s+tag\s+mismatch", "ABI_TAG_MISMATCH"),
    (r"undefined symbol:\s+_Py", "ABI_TAG_MISMATCH"),
    (r"incompatible\s+C\+\+\s+ABI", "ABI_TAG_MISMATCH"),
    (r"GLIBCXX_\d+\.\d+(\.\d+)?\s+not found", "GLIBCXX_MISMATCH"),
    (r"GLIBC_\d+\.\d+(\.\d+)?\s+not found", "GLIBC_MISMATCH"),
    (r"Failed building wheel for", "WHEEL_BUILD_FAILURE"),
    (r"Could not build wheels for", "WHEEL_BUILD_FAILURE"),
    (r"Unsupported\s+Python\s+version", "UNSUPPORTED_VERSION"),
    (r"Requires-Python\s+[><=!~]+", "UNSUPPORTED_VERSION"),
    (r"no matching distribution found for", "NO_DISTRIBUTION_FOUND"),
]


def is_abi_or_compilation_error(error_log: str) -> Tuple[bool, str]:
    """
    Parse error output for C++ compiler errors, linker failures, and ABI mismatches.
    Returns (is_error: bool, category: str).
    """
    if not error_log:
        return False, "NONE"

    for pattern, category in ABI_COMPILATION_PATTERNS:
        if re.search(pattern, error_log, re.IGNORECASE | re.MULTILINE):
            return True, category

    return False, "NONE"


# =============================================================================
# 4. FILESYSTEM SAFETY & ROBUST REMOVAL HELPERS
# =============================================================================


def _handle_remove_readonly(func: Any, path: str, exc_info: Any) -> None:
    """Error handler for shutil.rmtree to handle Windows read-only files."""
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        func(path)
    except OSError as exc:
        logger.debug(f"Failed to clear read-only flag on {path}: {exc}")


def safe_remove_file(path: Union[str, Path], retries: int = 3, delay: float = 0.1) -> bool:
    """
    Safely delete a file, handling read-only attributes and transient Windows locks.
    """
    target = Path(path).resolve()
    if not target.exists():
        return True

    for attempt in range(retries):
        try:
            if target.is_file() or target.is_symlink():
                try:
                    target.chmod(stat.S_IWRITE | stat.S_IREAD)
                except OSError as _e:
                    logger.debug(f"Ignored exception: {_e}")
                target.unlink()
                return True
        except (PermissionError, OSError) as exc:
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
            else:
                logger.warning(f"Unable to delete file {target}: {exc}")
                return False
    return not target.exists()


def safe_remove_dir(path: Union[str, Path], retries: int = 3, delay: float = 0.1) -> bool:
    """
    Safely delete a directory tree, handling Windows read-only attributes and kernel locks.
    """
    target = Path(path).resolve()
    if not target.exists():
        return True

    for attempt in range(retries):
        try:
            if target.is_dir():
                shutil.rmtree(target, onerror=_handle_remove_readonly)
                return True
        except (PermissionError, OSError) as exc:
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
            else:
                logger.warning(f"Unable to delete directory tree {target}: {exc}")
                return False
    return not target.exists()


def sweep_intermediate_tmp_files(
    root_dir: Union[str, Path],
    patterns: Optional[List[str]] = None,
) -> List[Path]:
    """
    Purge orphaned intermediate temporary files and directories to ensure workspace sterility.
    """
    target_root = Path(root_dir).resolve()
    if not target_root.exists() or not target_root.is_dir():
        return []

    target_patterns = patterns or ["*.tmp*", "*_stage_*", "*cochem_tmp_*"]
    purged: List[Path] = []

    for pattern in target_patterns:
        for p in target_root.rglob(pattern):
            try:
                if p.is_file() or p.is_symlink():
                    if safe_remove_file(p):
                        purged.append(p)
                elif p.is_dir():
                    if safe_remove_dir(p):
                        purged.append(p)
            except OSError as exc:
                logger.debug(f"Failed to purge {p}: {exc}")

    return purged


# =============================================================================
# 5. BINARY & WHEEL RESOLUTION HELPERS
# =============================================================================


def resolve_conda_binary(custom_path: Optional[Union[str, Path]] = None) -> Optional[str]:
    """
    Probe host environment for conda, mamba, or micromamba executable.
    """
    if custom_path:
        p = Path(custom_path).resolve()
        if p.exists() and p.is_file():
            return str(p)

    # Check environment variables
    for env_var in ("CONDA_EXE", "MAMBA_EXE", "MICROMAMBA_EXE"):
        val = os.environ.get(env_var)
        if val and Path(val).exists():
            return str(Path(val).resolve())

    # Probe PATH candidates
    candidates = ["conda", "mamba", "micromamba", "conda.exe", "mamba.exe", "micromamba.exe"]
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return str(Path(found).resolve())

    return None


def scan_for_local_wheel_fallback(
    package_name: str,
    search_dirs: Optional[List[Union[str, Path]]] = None,
    target_python: Optional[str] = None,
) -> Optional[Path]:
    """
    Scan configured directories for local pre-compiled wheels (.whl) or archives (.tar.gz, .zip).
    Strictly adheres to PEP 427 and PEP 440 package boundary naming to avoid substring prefix collisions.
    """
    clean_name = re.sub(r"[-_.]+", "_", package_name).lower()
    hyphen_name = re.sub(r"[-_.]+", "-", package_name).lower()

    # In PEP 427 wheels, the distribution name is terminated by '-' before the version string.
    wheel_pattern = rf"^(?:{re.escape(clean_name)}|{re.escape(hyphen_name)})-(?=[0-9])"
    # In source distributions (.tar.gz/.zip), distribution name is terminated by '-' or '_' before version.
    archive_pattern = rf"^(?:{re.escape(clean_name)}|{re.escape(hyphen_name)})[-_](?=[0-9])"

    # Build list of directories to probe
    probe_dirs: List[Path] = []
    if search_dirs:
        probe_dirs.extend([Path(d).resolve() for d in search_dirs if Path(d).exists()])

    # Add default CoChem artifact search paths
    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        wheel_dir = Path(env_art).resolve() / "wheels"
        if wheel_dir.exists() and wheel_dir not in probe_dirs:
            probe_dirs.append(wheel_dir)

    cwd_art = Path.cwd() / ".agent_artifacts" / "wheels"
    if cwd_art.exists() and cwd_art not in probe_dirs:
        probe_dirs.append(cwd_art)

    cwd_dist = Path.cwd() / "dist"
    if cwd_dist.exists() and cwd_dist not in probe_dirs:
        probe_dirs.append(cwd_dist)

    # Search for matching wheel / archive packages
    py_tag = f"cp{target_python.replace('.', '')}" if target_python else None

    # First pass: look for exact matching wheel with python tag (e.g. cp311)
    if py_tag:
        for d in probe_dirs:
            for item in d.glob("*.whl"):
                stem_lower = item.name.lower()
                if re.search(wheel_pattern, stem_lower) and py_tag in stem_lower:
                    return item.resolve()

    # Second pass: universal wheels (py3-none-any / py2.py3-none-any)
    for d in probe_dirs:
        for item in d.glob("*.whl"):
            stem_lower = item.name.lower()
            if re.search(wheel_pattern, stem_lower) and (
                "py3-none-any" in stem_lower or "py2.py3-none-any" in stem_lower
            ):
                return item.resolve()

    # Third pass: if no target_python was specified, any matching wheel
    if not target_python:
        for d in probe_dirs:
            for item in d.glob("*.whl"):
                stem_lower = item.name.lower()
                if re.search(wheel_pattern, stem_lower):
                    return item.resolve()

    # Fourth pass: source archives (.tar.gz, .zip)
    for d in probe_dirs:
        for ext in ("*.tar.gz", "*.zip"):
            for item in d.glob(ext):
                stem_lower = item.name.lower()
                if re.search(archive_pattern, stem_lower):
                    return item.resolve()

    return None


# =============================================================================
# 6. TRANSACTIONAL DEPENDENCY MANAGER CLASS
# =============================================================================


class DependencyManager:
    """
    Transactional dependency management context manager.
    Wraps pip and conda subprocess calls, manages staged intermediate files,
    guarantees atomic JSON writes, and provides automated rollback on failures
    to preserve workspace sterility.
    """

    def __init__(
        self,
        auto_rollback: bool = True,
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
        self._auto_rollback: bool = auto_rollback
        self._logger: logging.Logger = logger_instance or logger
        self._tracked_temp_files: List[Path] = []
        self._tracked_temp_dirs: List[Path] = []
        self._tracked_virtualenvs: List[Path] = []
        self._tracked_conda_envs: List[str] = []

    # -------------------------------------------------------------------------
    # Context Manager Protocol
    # -------------------------------------------------------------------------

    def __enter__(self) -> DependencyManager:
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        if exc_type is not None and self._auto_rollback:
            self._logger.warning(
                f"[ROLLBACK TRIGGERED] Exception caught during execution: {exc_val}. "
                f"Wiping staged virtual environments and intermediate artifacts..."
            )
            self.rollback()

    # -------------------------------------------------------------------------
    # Tracking & State Properties
    # -------------------------------------------------------------------------

    @property
    def tracked_temp_files(self) -> List[Path]:
        """Return a copy of all tracked temporary files."""
        return list(self._tracked_temp_files)

    @property
    def tracked_temp_dirs(self) -> List[Path]:
        """Return a copy of all tracked temporary directories."""
        return list(self._tracked_temp_dirs)

    @property
    def tracked_virtualenvs(self) -> List[Path]:
        """Return a copy of all tracked virtual environment paths."""
        return list(self._tracked_virtualenvs)

    @property
    def tracked_conda_envs(self) -> List[str]:
        """Return a copy of all tracked conda environment identifiers."""
        return list(self._tracked_conda_envs)

    def track_temp_file(self, path: Union[str, Path]) -> Path:
        """Register a temporary file to be purged during rollback."""
        p = Path(path).resolve()
        if p not in self._tracked_temp_files:
            self._tracked_temp_files.append(p)
        return p

    def track_temp_dir(self, path: Union[str, Path]) -> Path:
        """Register a temporary directory to be purged during rollback."""
        p = Path(path).resolve()
        if p not in self._tracked_temp_dirs:
            self._tracked_temp_dirs.append(p)
        return p

    def track_virtualenv(self, path: Union[str, Path]) -> Path:
        """Register a virtual environment root directory for rollback removal."""
        p = Path(path).resolve()
        if p not in self._tracked_virtualenvs:
            self._tracked_virtualenvs.append(p)
        return p

    def track_conda_env(self, name_or_prefix: str) -> str:
        """Register a conda environment name or prefix for rollback removal."""
        ident = str(name_or_prefix).strip()
        if ident not in self._tracked_conda_envs:
            self._tracked_conda_envs.append(ident)
        return ident

    def untrack_file(self, path: Union[str, Path]) -> None:
        """Remove a file from rollback tracking once successfully committed."""
        p = Path(path).resolve()
        if p in self._tracked_temp_files:
            self._tracked_temp_files.remove(p)

    def untrack_dir(self, path: Union[str, Path]) -> None:
        """Remove a directory from rollback tracking once successfully committed."""
        p = Path(path).resolve()
        if p in self._tracked_temp_dirs:
            self._tracked_temp_dirs.remove(p)

    def untrack_virtualenv(self, path: Union[str, Path]) -> None:
        """Remove a virtualenv from rollback tracking once successfully committed."""
        p = Path(path).resolve()
        if p in self._tracked_virtualenvs:
            self._tracked_virtualenvs.remove(p)

    def untrack_conda_env(self, name_or_prefix: str) -> None:
        """Remove a conda environment from rollback tracking once successfully committed."""
        ident = str(name_or_prefix).strip()
        if ident in self._tracked_conda_envs:
            self._tracked_conda_envs.remove(ident)

    # -------------------------------------------------------------------------
    # Staging & Factory Utilities
    # -------------------------------------------------------------------------

    def create_temp_file(
        self,
        suffix: str = ".tmp",
        prefix: str = "cochem_tmp_",
        directory: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Create and track an ephemeral temporary file."""
        dir_path = Path(directory) if directory else None
        if dir_path:
            dir_path.mkdir(parents=True, exist_ok=True)

        fd, temp_path_str = tempfile.mkstemp(
            suffix=suffix,
            prefix=prefix,
            dir=str(dir_path) if dir_path else None,
        )
        os.close(fd)
        temp_path = Path(temp_path_str).resolve()
        self.track_temp_file(temp_path)
        return temp_path

    def create_temp_dir(
        self,
        prefix: str = "cochem_stage_",
        directory: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Create and track an ephemeral temporary directory."""
        dir_path = Path(directory) if directory else None
        if dir_path:
            dir_path.mkdir(parents=True, exist_ok=True)

        temp_dir_str = tempfile.mkdtemp(
            prefix=prefix,
            dir=str(dir_path) if dir_path else None,
        )
        temp_dir = Path(temp_dir_str).resolve()
        self.track_temp_dir(temp_dir)
        return temp_dir

    # -------------------------------------------------------------------------
    # Rollback & Sterility Execution
    # -------------------------------------------------------------------------

    def rollback(self) -> None:
        """
        Execute atomic rollback protocol. Safely erases all tracked temporary files,
        staging directories, incomplete virtual environments, and conda environments.
        """
        # 1. Purge tracked temporary files
        for temp_file in list(self._tracked_temp_files):
            try:
                safe_remove_file(temp_file)
            except Exception as exc:
                self._logger.error(f"Failed to remove tracked temp file {temp_file}: {exc}")
        self._tracked_temp_files.clear()

        # 2. Purge tracked temporary directories
        for temp_dir in list(self._tracked_temp_dirs):
            try:
                safe_remove_dir(temp_dir)
            except Exception as exc:
                self._logger.error(f"Failed to remove tracked temp directory {temp_dir}: {exc}")
        self._tracked_temp_dirs.clear()

        # 3. Purge tracked virtual environments
        for venv_path in list(self._tracked_virtualenvs):
            try:
                safe_remove_dir(venv_path)
            except Exception as exc:
                self._logger.error(f"Failed to remove tracked virtualenv {venv_path}: {exc}")
        self._tracked_virtualenvs.clear()

        # 4. Purge tracked conda environments
        for conda_ident in list(self._tracked_conda_envs):
            try:
                conda_bin = resolve_conda_binary()
                if conda_bin:
                    if Path(conda_ident).is_absolute() or "/" in conda_ident or "\\" in conda_ident:
                        cmd = [conda_bin, "env", "remove", "-y", "-p", conda_ident]
                    else:
                        cmd = [conda_bin, "env", "remove", "-y", "-n", conda_ident]
                    subprocess.run(cmd, capture_output=True, timeout=120.0, check=False)
            except Exception as exc:
                self._logger.error(f"Failed to remove tracked conda env {conda_ident}: {exc}")
        self._tracked_conda_envs.clear()

    # -------------------------------------------------------------------------
    # Atomic State Persistence
    # -------------------------------------------------------------------------

    def atomic_write_json(
        self,
        target_path: Union[str, Path],
        data: Union[BaseModel, Dict[str, Any], Sequence[Any], Any],
        indent: int = 2,
    ) -> Path:
        """
        Atomically write JSON content to target_path using a staged temporary file and os.replace.
        Guarantees destination file is never left in a partially written or corrupted state.
        """
        target = Path(target_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        # Stage in same parent directory to ensure single-filesystem atomic replace
        unique_suffix = f".tmp.{uuid.uuid4().hex[:8]}"
        staged_file = target.parent / f"{target.name}{unique_suffix}"
        self.track_temp_file(staged_file)

        try:
            if isinstance(data, BaseModel):
                payload = data.model_dump_json(indent=indent)
            elif isinstance(data, (dict, list, tuple)):
                payload = json.dumps(data, indent=indent)
            elif isinstance(data, (str, int, float, bool)) or data is None:
                payload = json.dumps(data, indent=indent)
            else:
                payload = json.dumps(data, indent=indent)

            with open(staged_file, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())

            if target.exists():
                try:
                    target.chmod(stat.S_IWRITE | stat.S_IREAD)
                except OSError as _e:
                    logger.debug(f"Ignored exception: {_e}")

            os.replace(staged_file, target)
            self.untrack_file(staged_file)
            return target
        except Exception:
            # Clean up staged file if serialization or write failed
            safe_remove_file(staged_file)
            self.untrack_file(staged_file)
            raise

    # -------------------------------------------------------------------------
    # PIP Subprocess Brokering
    # -------------------------------------------------------------------------

    def run_pip_command(
        self,
        args: List[str],
        python_executable: Optional[Union[str, Path]] = None,
        cwd: Optional[Union[str, Path]] = None,
        timeout: float = 300.0,
        env: Optional[Dict[str, str]] = None,
        check: bool = False,
    ) -> PipExecutionResult:
        """
        Execute a pip command using the specified Python binary or system python.
        """
        py_exe = str(Path(python_executable).resolve()) if python_executable else sys.executable
        cmd = [py_exe, "-m", "pip"] + args

        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)

        start_time = time.perf_counter()
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(cwd) if cwd else None,
                timeout=timeout,
                env=exec_env,
                check=False,
            )
            duration = round(time.perf_counter() - start_time, 3)
            success = res.returncode == 0
            stdout_str = res.stdout or ""
            stderr_str = res.stderr or ""

            result = PipExecutionResult(
                command=cmd,
                returncode=res.returncode,
                stdout=stdout_str,
                stderr=stderr_str,
                duration_seconds=duration,
                success=success,
                executable_path=py_exe,
            )

            if check and not success:
                raise PipExecutionError(
                    f"pip command failed with exit code {res.returncode}:\n"
                    f"CMD: {' '.join(cmd)}\nSTDERR: {stderr_str}\nSTDOUT: {stdout_str}"
                )

            return result

        except subprocess.TimeoutExpired as exc:
            duration = round(time.perf_counter() - start_time, 3)
            stdout_str = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout.decode() if exc.stdout else "")
            stderr_str = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr.decode() if exc.stderr else "")
            stderr_str += f"\n[ERROR] Command timed out after {timeout} seconds."

            result = PipExecutionResult(
                command=cmd,
                returncode=-1,
                stdout=stdout_str,
                stderr=stderr_str,
                duration_seconds=duration,
                success=False,
                executable_path=py_exe,
            )
            if check:
                raise PipExecutionError(f"pip command timed out after {timeout}s: {' '.join(cmd)}") from exc
            return result

    def pip_install(
        self,
        packages: Union[str, List[str]],
        python_executable: Optional[Union[str, Path]] = None,
        flags: Optional[List[str]] = None,
        find_links: Optional[Union[str, Path]] = None,
        index_url: Optional[str] = None,
        extra_index_urls: Optional[List[str]] = None,
        upgrade: bool = False,
        no_deps: bool = False,
        timeout: float = 600.0,
        check: bool = False,
    ) -> PipExecutionResult:
        """
        Execute `pip install` with configurable repository links and safety flags.
        """
        pkg_list = [packages] if isinstance(packages, str) else packages
        args = ["install"]

        if upgrade:
            args.append("--upgrade")
        if no_deps:
            args.append("--no-deps")
        if find_links:
            args.extend(["--find-links", str(find_links)])
        if index_url:
            args.extend(["--index-url", index_url])
        if extra_index_urls:
            for extra_url in extra_index_urls:
                args.extend(["--extra-index-url", extra_url])
        if flags:
            args.extend(flags)

        args.extend(pkg_list)
        return self.run_pip_command(
            args=args,
            python_executable=python_executable,
            timeout=timeout,
            check=check,
        )

    def pip_uninstall(
        self,
        packages: Union[str, List[str]],
        python_executable: Optional[Union[str, Path]] = None,
        yes: bool = True,
        timeout: float = 120.0,
        check: bool = False,
    ) -> PipExecutionResult:
        """Execute `pip uninstall` with automatic confirmation."""
        pkg_list = [packages] if isinstance(packages, str) else packages
        args = ["uninstall"]
        if yes:
            args.append("-y")
        args.extend(pkg_list)
        return self.run_pip_command(
            args=args,
            python_executable=python_executable,
            timeout=timeout,
            check=check,
        )

    def pip_list(
        self,
        python_executable: Optional[Union[str, Path]] = None,
        format_type: str = "json",
        timeout: float = 60.0,
        check: bool = False,
    ) -> PipExecutionResult:
        """Execute `pip list` and optionally format as JSON."""
        args = ["list"]
        if format_type:
            args.extend(["--format", format_type])
        return self.run_pip_command(
            args=args,
            python_executable=python_executable,
            timeout=timeout,
            check=check,
        )

    def pip_check(
        self,
        python_executable: Optional[Union[str, Path]] = None,
        timeout: float = 60.0,
        check: bool = False,
    ) -> PipExecutionResult:
        """Execute `pip check` to verify installed packages have compatible dependencies."""
        return self.run_pip_command(
            args=["check"],
            python_executable=python_executable,
            timeout=timeout,
            check=check,
        )

    # -------------------------------------------------------------------------
    # CONDA Subprocess Brokering
    # -------------------------------------------------------------------------

    def run_conda_command(
        self,
        args: List[str],
        conda_executable: Optional[Union[str, Path]] = None,
        cwd: Optional[Union[str, Path]] = None,
        timeout: float = 600.0,
        env: Optional[Dict[str, str]] = None,
        check: bool = False,
    ) -> CondaExecutionResult:
        """
        Execute a conda/mamba command with output capture and error wrapping.
        """
        conda_bin = conda_executable or resolve_conda_binary()
        if not conda_bin:
            raise FileNotFoundError(
                "Conda binary not found in PATH or environment (CONDA_EXE / MAMBA_EXE)."
            )

        cmd = [str(conda_bin)] + args
        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)

        start_time = time.perf_counter()
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(cwd) if cwd else None,
                timeout=timeout,
                env=exec_env,
                check=False,
            )
            duration = round(time.perf_counter() - start_time, 3)
            success = res.returncode == 0

            result = CondaExecutionResult(
                command=cmd,
                returncode=res.returncode,
                stdout=res.stdout or "",
                stderr=res.stderr or "",
                duration_seconds=duration,
                success=success,
                executable_path=str(conda_bin),
            )

            if check and not success:
                raise CondaExecutionError(
                    f"conda command failed with exit code {res.returncode}:\n"
                    f"CMD: {' '.join(cmd)}\nSTDERR: {res.stderr}\nSTDOUT: {res.stdout}"
                )

            return result

        except subprocess.TimeoutExpired as exc:
            duration = round(time.perf_counter() - start_time, 3)
            stdout_str = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout.decode() if exc.stdout else "")
            stderr_str = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr.decode() if exc.stderr else "")
            stderr_str += f"\n[ERROR] Conda command timed out after {timeout} seconds."

            result = CondaExecutionResult(
                command=cmd,
                returncode=-1,
                stdout=stdout_str,
                stderr=stderr_str,
                duration_seconds=duration,
                success=False,
                executable_path=str(conda_bin),
            )
            if check:
                raise CondaExecutionError(
                    f"conda command timed out after {timeout}s: {' '.join(cmd)}"
                ) from exc
            return result

    def conda_create_env(
        self,
        name_or_prefix: str,
        python_version: str = "3.11",
        packages: Optional[List[str]] = None,
        channels: Optional[List[str]] = None,
        conda_executable: Optional[Union[str, Path]] = None,
        timeout: float = 600.0,
        check: bool = False,
    ) -> CondaExecutionResult:
        """Create a new conda environment with specified python version and packages."""
        args = ["create", "-y"]
        if Path(name_or_prefix).is_absolute() or "/" in name_or_prefix or "\\" in name_or_prefix:
            args.extend(["-p", str(Path(name_or_prefix).resolve())])
        else:
            args.extend(["-n", name_or_prefix])

        if channels:
            for ch in channels:
                args.extend(["-c", ch])

        args.append(f"python={python_version}")
        if packages:
            args.extend(packages)

        res = self.run_conda_command(
            args=args,
            conda_executable=conda_executable,
            timeout=timeout,
            check=check,
        )
        if res.success:
            self.track_conda_env(name_or_prefix)
        return res

    def conda_install(
        self,
        name_or_prefix: str,
        packages: Union[str, List[str]],
        channels: Optional[List[str]] = None,
        conda_executable: Optional[Union[str, Path]] = None,
        timeout: float = 600.0,
        check: bool = False,
    ) -> CondaExecutionResult:
        """Install packages into an existing conda environment."""
        pkg_list = [packages] if isinstance(packages, str) else packages
        args = ["install", "-y"]

        if Path(name_or_prefix).is_absolute() or "/" in name_or_prefix or "\\" in name_or_prefix:
            args.extend(["-p", str(Path(name_or_prefix).resolve())])
        else:
            args.extend(["-n", name_or_prefix])

        if channels:
            for ch in channels:
                args.extend(["-c", ch])

        args.extend(pkg_list)
        return self.run_conda_command(
            args=args,
            conda_executable=conda_executable,
            timeout=timeout,
            check=check,
        )

    def conda_env_create(
        self,
        environment_file: Union[str, Path],
        name_or_prefix: Optional[str] = None,
        conda_executable: Optional[Union[str, Path]] = None,
        timeout: float = 900.0,
        check: bool = False,
    ) -> CondaExecutionResult:
        """Create a conda environment from an environment.yml file."""
        env_file_path = Path(environment_file).resolve()
        args = ["env", "create", "-f", str(env_file_path)]

        if name_or_prefix:
            if Path(name_or_prefix).is_absolute() or "/" in name_or_prefix or "\\" in name_or_prefix:
                args.extend(["-p", str(Path(name_or_prefix).resolve())])
            else:
                args.extend(["-n", name_or_prefix])

        res = self.run_conda_command(
            args=args,
            conda_executable=conda_executable,
            timeout=timeout,
            check=check,
        )
        if res.success and name_or_prefix:
            self.track_conda_env(name_or_prefix)
        return res

    def conda_remove_env(
        self,
        name_or_prefix: str,
        conda_executable: Optional[Union[str, Path]] = None,
        timeout: float = 300.0,
        check: bool = False,
    ) -> CondaExecutionResult:
        """Remove a conda environment."""
        args = ["env", "remove", "-y"]
        if Path(name_or_prefix).is_absolute() or "/" in name_or_prefix or "\\" in name_or_prefix:
            args.extend(["-p", str(Path(name_or_prefix).resolve())])
        else:
            args.extend(["-n", name_or_prefix])

        res = self.run_conda_command(
            args=args,
            conda_executable=conda_executable,
            timeout=timeout,
            check=check,
        )
        if res.success:
            self.untrack_conda_env(name_or_prefix)
        return res

    # -------------------------------------------------------------------------
    # Dynamic Version Walking & Fallback Engine
    # -------------------------------------------------------------------------

    def walk_python_versions(
        self,
        package_name: str,
        initial_version: str = "3.11",
        version_chain: Optional[List[str]] = None,
        wheel_search_dirs: Optional[List[Union[str, Path]]] = None,
        install_action: Optional[Callable[[str, Optional[Path]], Tuple[bool, str]]] = None,
        timeout_per_step: float = 300.0,
    ) -> DynamicVersionWalkingResult:
        """
        Execute Dynamic Version Walking by iteratively stepping down minor Python versions
        (e.g., 3.12 -> 3.11 -> 3.10 -> 3.9) if compilation, linker, or ABI failures occur.
        Scans for local pre-compiled wheel/tarball fallbacks before failing.
        """
        chain = version_chain or ["3.12", "3.11", "3.10", "3.9"]
        if initial_version not in chain:
            chain = [initial_version] + [v for v in chain if v != initial_version]

        steps: List[DynamicVersionWalkStep] = []
        resolved_version: Optional[str] = None
        used_local_fallback: bool = False
        fallback_path_str: Optional[str] = None

        self._logger.info(
            f"[DYNAMIC VERSION WALKING] Initiating version walk for '{package_name}'. "
            f"Chain: {' -> '.join(chain)}"
        )

        for ver in chain:
            step_start = time.perf_counter()
            self._logger.info(f"[VERSION WALK STEP] Evaluating Python version '{ver}' for '{package_name}'...")

            # 1. Check for local wheel / archive fallback for this version
            local_wheel = scan_for_local_wheel_fallback(
                package_name=package_name,
                search_dirs=wheel_search_dirs,
                target_python=ver,
            )

            # 2. Execute installation callback
            success = False
            error_summary: Optional[str] = None

            if install_action is not None:
                try:
                    success, error_log = install_action(ver, local_wheel)
                    if not success:
                        is_abi_err, cat = is_abi_or_compilation_error(error_log)
                        error_summary = f"[{cat}] {error_log.splitlines()[0] if error_log else 'Unknown failure'}"
                    else:
                        error_summary = None
                except Exception as exc:
                    success = False
                    error_summary = f"[EXCEPTION] {str(exc)}"
            else:
                # Default behavior: report local wheel if found
                if local_wheel:
                    success = True
                    error_summary = None
                else:
                    success = False
                    error_summary = f"No compiler or wheel available for version {ver}"

            duration = round(time.perf_counter() - step_start, 3)

            step_record = DynamicVersionWalkStep(
                attempted_version=ver,
                success=success,
                fallback_wheel_found=str(local_wheel) if local_wheel else None,
                error_summary=error_summary,
                duration_seconds=duration,
            )
            steps.append(step_record)

            if success:
                resolved_version = ver
                if local_wheel is not None:
                    used_local_fallback = True
                    fallback_path_str = str(local_wheel)
                self._logger.info(
                    f"[VERSION WALK RESOLVED] Resolved '{package_name}' on Python {ver} "
                    f"(Local Fallback: {used_local_fallback})."
                )
                break
            else:
                self._logger.warning(
                    f"[VERSION WALK STEP FAILED] Python {ver} failed: {error_summary}. "
                    f"Stepping down to next minor version..."
                )

        status_str = "PASSED" if resolved_version is not None else "FAILED"

        return DynamicVersionWalkingResult(
            initial_version=initial_version,
            target_version=initial_version,
            version_chain=chain,
            resolved_version=resolved_version,
            used_local_fallback=used_local_fallback,
            fallback_binary_path=fallback_path_str,
            steps=steps,
            status=status_str,
        )


def walk_python_versions(
    package_name: str,
    initial_version: str = "3.11",
    version_chain: Optional[List[str]] = None,
    wheel_search_dirs: Optional[List[Union[str, Path]]] = None,
    install_action: Optional[Callable[[str, Optional[Path]], Tuple[bool, str]]] = None,
    timeout_per_step: float = 300.0,
) -> DynamicVersionWalkingResult:
    """
    Convenience functional interface for Dynamic Version Walking.
    """
    dm = DependencyManager()
    return dm.walk_python_versions(
        package_name=package_name,
        initial_version=initial_version,
        version_chain=version_chain,
        wheel_search_dirs=wheel_search_dirs,
        install_action=install_action,
        timeout_per_step=timeout_per_step,
    )


# =============================================================================
# 7. TOP-LEVEL MODULE EXPORTS
# =============================================================================

__all__ = [
    "DependencyManager",
    "DependencyManagerError",
    "RollbackError",
    "PipExecutionError",
    "CondaExecutionError",
    "VersionWalkingError",
    "PipExecutionResult",
    "CondaExecutionResult",
    "DynamicVersionWalkStep",
    "DynamicVersionWalkingResult",
    "is_abi_or_compilation_error",
    "scan_for_local_wheel_fallback",
    "sweep_intermediate_tmp_files",
    "safe_remove_file",
    "safe_remove_dir",
    "resolve_conda_binary",
    "walk_python_versions",
]
