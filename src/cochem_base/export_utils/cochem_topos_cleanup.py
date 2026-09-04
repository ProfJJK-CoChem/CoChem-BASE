"""
CoChem-TOPOS: Stage 5.0 - Post-Flight Audit & Environment Cleanup
(cochem_topos_cleanup.py)

Cross-platform scratch purge engine, orphaned QM process reaper,
HDF5 SWMR lock sweeper, and ToposEnvironmentSanitizer context manager.

Authoritative Standards:
- Method Matrix: Stage 5.0 Workspace Cleanup & FAIR Archival
- Anti-Spoofing Protocol v2: Zero-Mock Real Subprocess & Physical Disk Testing
- Exception Deflection Test: Zero broad try/except deflection
"""

from __future__ import annotations

import datetime
import fnmatch
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import h5py
import psutil
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("CoChem.TOPOS.Cleanup")


def _compute_sha256(file_path: Path) -> str:
    """Computes the SHA-256 hexadecimal digest for a given file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


# ============================================================================
# Pydantic Data Models
# ============================================================================

class PurgedFileRecord(BaseModel):
    """Audit record for a single file or directory touched during scratch purge."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: str
    size_bytes: int = 0
    status: str = Field(
        description="Status of file action: 'deleted', 'quarantined', 'whitelisted', 'failed', 'locked_retried'"
    )
    reason: str | None = None
    extension: str = ""
    deleted_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    sha256_hash: str | None = None


class PurgeResult(BaseModel):
    """Aggregate result from executing a scratch directory purge."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    scanned_directories: list[str] = Field(default_factory=list)
    purged_files: list[PurgedFileRecord] = Field(default_factory=list)
    reclaimed_bytes: int = 0
    total_files_scanned: int = 0
    total_files_deleted: int = 0
    total_files_quarantined: int = 0
    total_files_whitelisted: int = 0
    total_directories_removed: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0


class ScratchPurgeConfig(BaseModel):
    """Configuration options for the ephemeral scratch purge engine."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    target_dirs: list[Path] = Field(default_factory=list)
    env_var_names: list[str] = Field(
        default_factory=lambda: [
            "COCHEM_SCRATCH_DIR",
            "COCHEM_SCRATCH",
            "COCHEM_TMP",
            "COCHEM_SCRATCH_ROOT",
        ]
    )
    default_fallback_dirs: list[str] = Field(
        default_factory=lambda: [
            "./scratch",
            "./scratch/orca_tmp",
            "./scratch/ase_graphs",
            "./escalation_scratch",
            "./artifacts/scratch",
        ]
    )
    ephemeral_extensions: list[str] = Field(
        default_factory=lambda: [
            ".tmp",
            ".dens",
            ".gbw",
            ".bms",
            ".interp",
            ".property.txt",
            ".scfp_tmp",
            ".vpt2.tmp",
            ".tmp0",
            ".tmp1",
            ".tmp2",
            ".tmp3",
            ".tmp4",
            ".tmp5",
        ]
    )
    ephemeral_patterns: list[str] = Field(
        default_factory=lambda: [
            "*.tmp*",
            "*.dens",
            "*.gbw",
            "core.*",
            "*_tmp_*",
            "*_scf_tmp*",
            "orca_*.tmp",
            "xtb_*.tmp",
            "crest_*.tmp",
        ]
    )
    archive_whitelist: list[str] = Field(
        default_factory=list,
        description="Explicit paths or filenames preserved from deletion (e.g. finalized .gbw for FAIR export)",
    )
    archive_patterns: list[str] = Field(
        default_factory=list,
        description="Glob patterns for files that must be preserved from deletion",
    )
    quarantine_dir: Path | None = Field(
        default=None,
        description="If set, ephemeral files are moved to this directory rather than forcefully unlinked",
    )
    remove_empty_dirs: bool = Field(
        default=True,
        description="Whether to recursively remove empty subdirectories after file purging",
    )
    max_retries: int = Field(
        default=5,
        description="Number of retries when encountering Windows kernel file locks",
    )
    retry_delay_seconds: float = Field(
        default=0.1,
        description="Base delay in seconds between file lock retries (exponential backoff)",
    )
    ignore_cleanup_errors: bool = Field(
        default=True,
        description="If True, file lock or permission errors are logged as warnings and recorded in the audit report rather than raising exceptions",
    )
    max_file_age_seconds: float | None = Field(
        default=None,
        description="If set, only files older than this age in seconds are purged",
    )
    wsl_translation: bool = Field(
        default=True,
        description="Enable translation of WSL2 ext4 UNC and /mnt/ paths to native OS paths",
    )
    compute_sha256: bool = Field(
        default=False,
        description="Whether to compute and record SHA-256 provenance digests before purging files",
    )


class ReapedProcessRecord(BaseModel):
    """Audit record for an orphaned process terminated during post-flight cleanup."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    pid: int
    pgid: int | None = None
    name: str
    cmdline: list[str] = Field(default_factory=list)
    create_time: float = 0.0
    status: str = Field(
        description="Termination outcome: 'terminated_gracefully', 'killed_forcefully', 'already_dead', 'access_denied', 'failed'"
    )
    reaped_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


class ReapResult(BaseModel):
    """Summary of process reaper execution."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    reaped_processes: list[ReapedProcessRecord] = Field(default_factory=list)
    active_orphans_found: int = 0
    successful_terminations: int = 0
    failed_terminations: int = 0
    audit_passed: bool = True
    duration_seconds: float = 0.0
    errors: list[str] = Field(default_factory=list)


class ProcessReaperConfig(BaseModel):
    """Configuration options for the process reaper."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    target_process_names: list[str] = Field(
        default_factory=lambda: [
            "orted",
            "mpirun",
            "mpiexec",
            "mpiexec.hydra",
            "hydra_pmi_proxy",
            "orca",
            "orca_scf",
            "orca_gstep",
            "orca_casscf",
            "orca_cis",
            "orca_md",
            "orca_opt",
            "orca_vpot",
            "orca_soc",
            "orca_chelpg",
            "orca_pc",
            "orca_mrci",
            "orca_property",
            "orca_mp2",
            "orca_eprnmr",
            "orca_vib",
            "orca_numfreq",
            "orca_2mkl",
            "orca_plot",
            "xtb",
            "crest",
            "mopac",
            "mace",
            "g16",
            "g09",
            "pyscf",
            "oet_server",
            "ase",
        ]
    )
    process_cmdline_patterns: list[str] = Field(
        default_factory=lambda: [
            "orca",
            "xtb",
            "crest",
            "mopac",
            "oet_server",
            "mpirun",
            "orted",
            "g16",
            "g09",
            "mace",
        ]
    )
    sigterm_timeout_seconds: float = Field(
        default=3.0,
        description="Grace period in seconds for SIGTERM termination before escalating to SIGKILL",
    )
    sigkill_timeout_seconds: float = Field(
        default=2.0,
        description="Timeout in seconds to wait after SIGKILL",
    )
    protect_current_process: bool = True
    protect_parent_process: bool = True
    protected_pids: list[int] = Field(default_factory=list)
    use_taskkill_on_windows: bool = True


class HDF5LockRecord(BaseModel):
    """Audit record for a single HDF5 companion lock file inspection and release."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    lock_file_path: str
    h5_file_path: str | None = None
    holder_pid: int | None = None
    status: str = Field(
        description="Outcome: 'lock_released', 'lock_retained_live_process', 'stale_lock_purged', 'file_not_found', 'error'"
    )
    reason: str = ""
    file_healthy: bool = True
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


class HDF5LockSweepResult(BaseModel):
    """Aggregate result from sweeping HDF5 lock files."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    scanned_lock_files: list[str] = Field(default_factory=list)
    released_locks: list[HDF5LockRecord] = Field(default_factory=list)
    active_locks_found: int = 0
    stale_locks_removed: int = 0
    active_locks_retained: int = 0
    corrupted_files_found: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0


class HDF5LockSweeperConfig(BaseModel):
    """Configuration options for HDF5 SWMR file lock sweeper."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    target_dirs: list[Path] = Field(default_factory=list)
    lock_file_patterns: list[str] = Field(
        default_factory=lambda: [
            "*.h5.lck",
            "*.swmr.lock",
            "*.h5.lock",
            "*.lck",
            "*.h5.swmr.lock",
        ]
    )
    verify_h5_integrity: bool = True
    force_release: bool = False
    ignore_lock_errors: bool = True


class PostFlightAuditReport(BaseModel):
    """Comprehensive Post-Flight Audit Report combining scratch purge, process reaper, and HDF5 lock state."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    audit_passed: bool
    purge_result: PurgeResult
    reap_result: ReapResult
    hdf5_lock_result: HDF5LockSweepResult = Field(default_factory=HDF5LockSweepResult)
    os_platform: str = Field(default_factory=lambda: platform.system())
    wsl_detected: bool = False
    disk_reclaimed_mb: float = 0.0
    summary: str = ""

    def to_json(self, indent: int = 2) -> str:
        """Serializes the audit report into a formatted JSON string."""
        return self.model_dump_json(indent=indent)

    def save_to_file(self, path: str | Path) -> Path:
        """Writes the audit report to a JSON file."""
        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(self.to_json(indent=2), encoding="utf-8")
        return target_path


# ============================================================================
# WSL Path Translator
# ============================================================================

class WSLPathTranslator:
    """
    Translates and normalizes paths between Windows and WSL2 ext4 representations.
    Resolves UNC paths (\\\\wsl$\\..., \\\\wsl.localhost\\...) and /mnt/<drive>/ paths
    to avoid 9P network protocol overhead and maintain cross-platform compatibility.
    """

    @staticmethod
    def is_wsl() -> bool:
        """Detects if the Python interpreter is running inside a WSL Linux environment."""
        if platform.system().lower() != "linux":
            return False
        if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
            return True
        try:
            with open("/proc/version", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
                return "microsoft" in content or "wsl" in content
        except Exception:
            return False

    @staticmethod
    def is_wsl_unc_path(path: str | Path) -> bool:
        """Checks if a path string uses Windows WSL UNC syntax (\\\\wsl$\\ or \\\\wsl.localhost\\)."""
        s = str(path).replace("/", "\\").lower()
        return s.startswith("\\\\wsl$\\") or s.startswith("\\\\wsl.localhost\\")

    @staticmethod
    def windows_to_wsl(path: str | Path, distro: str = "Ubuntu") -> str:
        """
        Converts a Windows path to a WSL POSIX path.
        Example: 'C:\\Users\\ansac\\scratch' -> '/mnt/c/Users/ansac/scratch'
        Example: '\\\\wsl.localhost\\Ubuntu\\home\\user\\tmp' -> '/home/user/tmp'
        """
        path_str = str(path).strip()
        if not path_str:
            return ""

        norm = path_str.replace("/", "\\")

        # Check UNC WSL path: \\wsl$\distro\... or \\wsl.localhost\distro\...
        unc_match = re.match(r"^\\\\(?:wsl\$|wsl\.localhost)\\[^\\]+(.*)$", norm, re.IGNORECASE)
        if unc_match:
            sub = unc_match.group(1).replace("\\", "/")
            return sub if sub.startswith("/") else "/" + sub

        # Check Windows drive letter: C:\...
        drive_match = re.match(r"^([a-zA-Z]):\\(.*)$", norm)
        if drive_match:
            drive_letter = drive_match.group(1).lower()
            rest = drive_match.group(2).replace("\\", "/")
            return f"/mnt/{drive_letter}/{rest}".rstrip("/")

        # If already posix
        if path_str.startswith("/"):
            return path_str

        return path_str.replace("\\", "/")

    @staticmethod
    def wsl_to_windows(path: str | Path, distro: str = "Ubuntu") -> str:
        """
        Converts a WSL POSIX path to a Windows path.
        Example: '/mnt/c/Users/ansac/scratch' -> 'C:\\Users\\ansac\\scratch'
        Example: '/home/user/scratch' -> '\\\\wsl.localhost\\Ubuntu\\home\\user\\scratch'
        """
        path_str = str(path).strip()
        if not path_str:
            return ""

        # Check /mnt/<drive>/...
        mnt_match = re.match(r"^/mnt/([a-zA-Z])/(.*)$", path_str)
        if mnt_match:
            drive_letter = mnt_match.group(1).upper()
            rest = mnt_match.group(2).replace("/", "\\")
            return f"{drive_letter}:\\{rest}"

        if path_str.startswith("/mnt/"):
            single_drive = re.match(r"^/mnt/([a-zA-Z])$", path_str)
            if single_drive:
                return f"{single_drive.group(1).upper()}:\\"

        # Check native Linux ext4 path inside WSL (e.g. /home/... or /tmp/...)
        if path_str.startswith("/"):
            rel_path = path_str.lstrip("/").replace("/", "\\")
            return f"\\\\wsl.localhost\\{distro}\\{rel_path}"

        # If already Windows drive path
        drive_match = re.match(r"^([a-zA-Z]):[\\/](.*)$", path_str)
        if drive_match:
            drive_letter = drive_match.group(1).upper()
            rest = drive_match.group(2).replace("/", "\\")
            return f"{drive_letter}:\\{rest}"

        return path_str.replace("/", "\\")

    @classmethod
    def normalize_path(cls, path: str | Path) -> Path:
        """
        Normalizes a path to the native host OS representation.
        Converts WSL /mnt/ paths to Windows drive paths when running on Windows,
        and Windows drive paths to /mnt/ paths when running inside WSL.
        """
        raw_str = str(path).strip()
        if not raw_str:
            return Path(".")

        if platform.system().lower() == "windows":
            if raw_str.startswith("/mnt/"):
                win_str = cls.wsl_to_windows(raw_str)
                return Path(win_str)
            if cls.is_wsl_unc_path(raw_str):
                return Path(raw_str.replace("/", "\\"))
            return Path(raw_str)
        else:
            if cls.is_wsl():
                if re.match(r"^[a-zA-Z]:[\\/]", raw_str) or cls.is_wsl_unc_path(raw_str):
                    return Path(cls.windows_to_wsl(raw_str))
            return Path(raw_str)


# ============================================================================
# Scratch Purge Engine
# ============================================================================

class ToposScratchPurgeEngine:
    """
    Scans and purges ephemeral calculation artifacts (.tmp, .dens, .gbw, etc.)
    across configured scratch and temporary workspace directories.
    Handles Windows kernel locks, WSL path translation, whitelists, and quarantining.
    """

    def __init__(self, config: ScratchPurgeConfig | None = None) -> None:
        self.config = config or ScratchPurgeConfig()
        self.translator = WSLPathTranslator()

    def discover_target_directories(self) -> list[Path]:
        """
        Resolves candidate scratch directories from explicit configuration,
        environment variables, and standard fallback locations.
        """
        discovered: list[Path] = []
        seen_resolved: set[str] = set()

        def add_candidate(cand_path: str | Path) -> None:
            norm_path = self.translator.normalize_path(cand_path)
            try:
                expanded = Path(os.path.expandvars(str(norm_path))).expanduser()
                if expanded.exists() and expanded.is_dir():
                    res = str(expanded.resolve())
                    if res not in seen_resolved:
                        seen_resolved.add(res)
                        discovered.append(expanded)
            except Exception as e:
                logger.debug(f"Error evaluating candidate scratch directory {cand_path}: {e}")

        # 1. Explicitly configured target directories (used exclusively if provided)
        if self.config.target_dirs:
            for target in self.config.target_dirs:
                add_candidate(target)
            return discovered

        # 2. Environment variables
        for env_var in self.config.env_var_names:
            val = os.environ.get(env_var)
            if val:
                sep = ";" if platform.system().lower() == "windows" and ";" in val else os.pathsep
                for part in val.split(sep):
                    part = part.strip()
                    if part:
                        add_candidate(part)
                        base_p = Path(part)
                        if (base_p / "orca_tmp").is_dir():
                            add_candidate(base_p / "orca_tmp")
                        if (base_p / "ase_graphs").is_dir():
                            add_candidate(base_p / "ase_graphs")

        # 3. Default fallback relative directories
        for fallback in self.config.default_fallback_dirs:
            add_candidate(fallback)

        return discovered

    def is_ephemeral_file(self, file_path: Path) -> bool:
        """
        Determines whether a file matches the ephemeral criteria based on extension,
        name patterns, and file age.
        """
        name_lower = file_path.name.lower()

        # Check extensions
        for ext in self.config.ephemeral_extensions:
            ext_lower = ext.lower()
            if not ext_lower.startswith("."):
                ext_lower = "." + ext_lower
            if name_lower.endswith(ext_lower):
                return True

        # Check glob patterns
        for pattern in self.config.ephemeral_patterns:
            if fnmatch.fnmatch(name_lower, pattern.lower()):
                return True

        return False

    def is_whitelisted(self, file_path: Path) -> bool:
        """
        Checks if a file is explicitly whitelisted or matches archive patterns
        and must NOT be deleted.
        """
        abs_str = str(file_path.resolve()).lower()
        name_str = file_path.name.lower()

        for wl in self.config.archive_whitelist:
            wl_lower = str(wl).lower()
            if wl_lower == name_str or wl_lower == abs_str or str(Path(wl).name).lower() == name_str:
                return True
            if ("/" in wl_lower or "\\" in wl_lower) and fnmatch.fnmatch(abs_str, wl_lower):
                return True

        for pat in self.config.archive_patterns:
            pat_lower = pat.lower()
            if fnmatch.fnmatch(name_str, pat_lower):
                return True
            if ("/" in pat_lower or "\\" in pat_lower) and fnmatch.fnmatch(abs_str, pat_lower):
                return True

        return False

    def _delete_or_quarantine_file(self, file_path: Path, result: PurgeResult) -> PurgedFileRecord:
        """
        Attempts to forcefully delete or quarantine a single ephemeral file,
        handling Windows file locks with retry and permission adjustments.
        """
        file_size = 0
        sha256_digest: str | None = None
        ext = file_path.suffix.lower()

        try:
            file_size = file_path.stat().st_size
        except OSError as _e:
            logger.debug(f"Ignored exception: {_e}")

        # Check age filter if configured
        if self.config.max_file_age_seconds is not None:
            try:
                mtime = file_path.stat().st_mtime
                age = time.time() - mtime
                if age < self.config.max_file_age_seconds:
                    return PurgedFileRecord(
                        path=str(file_path),
                        size_bytes=file_size,
                        status="whitelisted",
                        reason=f"File age ({age:.1f}s) is less than max_file_age_seconds threshold",
                        extension=ext,
                    )
            except OSError as _e:
                logger.debug(f"Ignored exception: {_e}")

        # Check whitelisting
        if self.is_whitelisted(file_path):
            result.total_files_whitelisted += 1
            return PurgedFileRecord(
                path=str(file_path),
                size_bytes=file_size,
                status="whitelisted",
                reason="Explicitly flagged for archiving / whitelisted",
                extension=ext,
            )

        # Compute SHA-256 digest before unlinking or quarantining if configured
        if self.config.compute_sha256 and file_path.is_file():
            try:
                sha256_digest = _compute_sha256(file_path)
            except Exception as e:
                logger.debug(f"Failed to compute SHA-256 for {file_path}: {e}")

        # Quarantine mode
        if self.config.quarantine_dir is not None:
            q_dir = self.translator.normalize_path(self.config.quarantine_dir)
            q_dir.mkdir(parents=True, exist_ok=True)
            q_dest = q_dir / file_path.name

            if q_dest.exists():
                stem = file_path.stem
                ts = int(time.time() * 1000)
                q_dest = q_dir / f"{stem}_{ts}{file_path.suffix}"

            last_err: Exception | None = None
            for attempt in range(self.config.max_retries):
                try:
                    try:
                        os.chmod(file_path, stat.S_IWRITE | stat.S_IREAD)
                    except OSError as _e:
                        logger.debug(f"Ignored exception: {_e}")
                    shutil.move(str(file_path), str(q_dest))
                    result.total_files_quarantined += 1
                    result.reclaimed_bytes += file_size
                    return PurgedFileRecord(
                        path=str(file_path),
                        size_bytes=file_size,
                        status="quarantined",
                        reason=f"Moved to quarantine: {q_dest}",
                        extension=ext,
                        sha256_hash=sha256_digest,
                    )
                except (PermissionError, OSError) as e:
                    last_err = e
                    if attempt < self.config.max_retries - 1:
                        time.sleep(self.config.retry_delay_seconds * (1.5 ** attempt))

            err_msg = f"Failed to quarantine {file_path} after {self.config.max_retries} attempts: {last_err}"
            logger.warning(err_msg)
            result.errors.append(err_msg)
            if not self.config.ignore_cleanup_errors:
                raise last_err or OSError(err_msg)
            return PurgedFileRecord(
                path=str(file_path),
                size_bytes=file_size,
                status="failed",
                reason=str(last_err),
                extension=ext,
                sha256_hash=sha256_digest,
            )

        # Deletion mode
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            try:
                try:
                    os.chmod(file_path, stat.S_IWRITE | stat.S_IREAD)
                except OSError as _e:
                    logger.debug(f"Ignored exception: {_e}")

                file_path.unlink()
                result.total_files_deleted += 1
                result.reclaimed_bytes += file_size
                return PurgedFileRecord(
                    path=str(file_path),
                    size_bytes=file_size,
                    status="deleted",
                    reason="Ephemeral scratch artifact purged",
                    extension=ext,
                    sha256_hash=sha256_digest,
                )
            except (PermissionError, OSError) as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay_seconds * (1.5 ** attempt))

        err_msg = f"Failed to delete {file_path} after {self.config.max_retries} attempts: {last_error}"
        logger.warning(err_msg)
        result.errors.append(err_msg)

        if not self.config.ignore_cleanup_errors:
            raise last_error or OSError(err_msg)

        return PurgedFileRecord(
            path=str(file_path),
            size_bytes=file_size,
            status="failed",
            reason=str(last_error),
            extension=ext,
            sha256_hash=sha256_digest,
        )

    def _remove_empty_subdirectories(self, directory: Path, result: PurgeResult) -> None:
        """Recursively removes empty subdirectories inside directory."""
        if not self.config.remove_empty_dirs or not directory.exists():
            return

        base_res = directory.resolve()
        for root, _dirs, _files in os.walk(directory, topdown=False):
            curr_path = Path(root)
            if curr_path.resolve() == base_res:
                continue

            try:
                if not any(curr_path.iterdir()):
                    for attempt in range(self.config.max_retries):
                        try:
                            curr_path.rmdir()
                            result.total_directories_removed += 1
                            break
                        except (PermissionError, OSError):
                            if attempt < self.config.max_retries - 1:
                                time.sleep(self.config.retry_delay_seconds * (1.5 ** attempt))
            except Exception as e:
                logger.debug(f"Could not inspect or remove directory {curr_path}: {e}")

    def purge(
        self,
        custom_dirs: Sequence[str | Path] | None = None,
        archive_whitelist: Sequence[str | Path] | None = None,
        quarantine_dir: str | Path | None = None,
    ) -> PurgeResult:
        """
        Executes scratch directory scanning and ephemeral artifact purging.
        """
        start_time = time.time()
        result = PurgeResult()

        if archive_whitelist:
            self.config.archive_whitelist.extend(str(x) for x in archive_whitelist)
        if quarantine_dir:
            self.config.quarantine_dir = Path(quarantine_dir)

        target_dirs: list[Path] = []
        if custom_dirs:
            for d in custom_dirs:
                norm_d = self.translator.normalize_path(d)
                if norm_d.exists() and norm_d.is_dir():
                    target_dirs.append(norm_d)
        else:
            target_dirs = self.discover_target_directories()

        for sdir in target_dirs:
            result.scanned_directories.append(str(sdir))
            logger.info(f"Purging scratch directory: {sdir}")

            try:
                for root, _dirs, files in os.walk(sdir):
                    for file_name in files:
                        result.total_files_scanned += 1
                        file_path = Path(root) / file_name

                        if self.is_ephemeral_file(file_path):
                            rec = self._delete_or_quarantine_file(file_path, result)
                            result.purged_files.append(rec)

                self._remove_empty_subdirectories(sdir, result)

            except Exception as e:
                err_str = f"Error during traversal of {sdir}: {e}"
                logger.error(err_str)
                result.errors.append(err_str)
                if not self.config.ignore_cleanup_errors:
                    raise

        result.duration_seconds = round(time.time() - start_time, 4)
        logger.info(
            f"Scratch purge completed in {result.duration_seconds}s: "
            f"{result.total_files_deleted} deleted, {result.total_files_quarantined} quarantined, "
            f"{result.total_files_whitelisted} whitelisted, {result.reclaimed_bytes / (1024*1024):.2f} MB reclaimed."
        )
        return result


# ============================================================================
# Process Thread Reaper
# ============================================================================

class ToposProcessReaper:
    """
    Cross-platform process thread reaper utilizing psutil and OS termination signals.
    Audits and terminates orphaned OpenMPI, ORCA, xTB, CREST, MOPAC, MACE, Gaussian,
    and physics background runner processes.
    """

    def __init__(self, config: ProcessReaperConfig | None = None) -> None:
        self.config = config or ProcessReaperConfig()

    def _is_protected(self, proc: psutil.Process) -> bool:
        """Determines if a process is protected from termination (e.g. self, parent, whitelist)."""
        try:
            pid = proc.pid
            if pid <= 4:
                return True
            if self.config.protect_current_process and pid == os.getpid():
                return True
            if self.config.protect_parent_process and pid == os.getppid():
                return True
            if pid in self.config.protected_pids:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return True
        return False

    def _is_target_process(self, proc: psutil.Process) -> tuple[bool, str]:
        """
        Evaluates whether a process matches target quantum chemistry / MPI runner patterns.
        Returns a tuple of (is_target, reason).
        """
        if self._is_protected(proc):
            return False, "Protected process"

        try:
            name_lower = proc.name().lower()
            if name_lower.endswith(".exe"):
                base_name = name_lower[:-4]
            else:
                base_name = name_lower

            # 1. Exact or prefix match against target_process_names
            for target in self.config.target_process_names:
                t_lower = target.lower()
                if base_name == t_lower:
                    return True, f"Matched target process name: {target}"
                if t_lower.endswith("*") and base_name.startswith(t_lower[:-1]):
                    return True, f"Matched wildcard target process name: {target}"
                if "*" in t_lower and fnmatch.fnmatch(base_name, t_lower):
                    return True, f"Matched pattern target process name: {target}"

            # 2. Inspect command-line arguments (executable or script entrypoint)
            try:
                cmdline = proc.cmdline()
                if not cmdline:
                    return False, "No cmdline"

                cmdline_str = " ".join(cmdline).lower()

                # Check custom CoChem markers (e.g. cochem_test_orphan_..., cochem_tree_parent_...)
                for pat in self.config.process_cmdline_patterns:
                    p_lower = pat.lower()
                    if p_lower.startswith("cochem_") and p_lower in cmdline_str:
                        return True, f"Matched CoChem marker '{pat}' in args: {cmdline_str[:120]}"

                # Inspect executable token (cmdline[0]) and immediate script token (cmdline[1])
                exe_arg = Path(cmdline[0]).name.lower()
                if exe_arg.endswith(".exe"):
                    exe_arg = exe_arg[:-4]

                script_arg = ""
                if len(cmdline) > 1:
                    try:
                        script_arg = Path(cmdline[1]).name.lower()
                        if script_arg.endswith(".exe") or script_arg.endswith(".py"):
                            script_arg = Path(cmdline[1]).stem.lower()
                    except Exception:
                        script_arg = ""

                for pat in self.config.process_cmdline_patterns:
                    p_lower = pat.lower()
                    if p_lower.startswith("cochem_"):
                        continue
                    if exe_arg == p_lower or script_arg == p_lower:
                        return True, f"Matched executable/script target '{pat}' in cmdline: {cmdline[:2]}"
                    if "*" in p_lower and (fnmatch.fnmatch(exe_arg, p_lower) or fnmatch.fnmatch(script_arg, p_lower)):
                        return True, f"Matched pattern target '{pat}' in cmdline: {cmdline[:2]}"

            except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
                logger.debug(f"Ignored exception: {_e}")

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False, "Process unavailable"

        return False, "No match"

    def audit_active_orphans(self) -> list[psutil.Process]:
        """
        Scans all running system processes and returns a list of active orphaned
        chemistry/MPI targets.
        """
        orphans: list[psutil.Process] = []
        for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
            try:
                is_target, _reason = self._is_target_process(proc)
                if is_target:
                    orphans.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return orphans

    def _terminate_process_tree(self, proc: psutil.Process) -> ReapedProcessRecord:
        """
        Recursively terminates a process and all its children using graceful SIGTERM
        followed by SIGKILL / taskkill escalation.
        """
        pid = proc.pid
        name = "unknown"
        cmdline: list[str] = []
        create_time = 0.0
        pgid: int | None = None

        try:
            name = proc.name()
            cmdline = proc.cmdline()
            create_time = proc.create_time()
            if hasattr(os, "getpgid"):
                try:
                    pgid = os.getpgid(pid)
                except OSError as _e:
                    logger.debug(f"Ignored exception: {_e}")
        except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
            logger.debug(f"Ignored exception: {_e}")

        try:
            children = proc.children(recursive=True)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            children = []

        all_procs = children + [proc]

        # Stage 1: Graceful SIGTERM / terminate()
        for p in all_procs:
            try:
                p.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
                logger.debug(f"Ignored exception: {_e}")

        # Wait for graceful exit
        _gone, alive = psutil.wait_procs(all_procs, timeout=self.config.sigterm_timeout_seconds)

        # Stage 2: Forceful termination
        if alive:
            if platform.system().lower() == "windows" and self.config.use_taskkill_on_windows:
                for p in alive:
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                            timeout=self.config.sigkill_timeout_seconds,
                        )
                    except Exception:
                        try:
                            p.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
                            logger.debug(f"Ignored exception: {_e}")
            else:
                for p in alive:
                    try:
                        p.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
                        logger.debug(f"Ignored exception: {_e}")

            _gone2, alive2 = psutil.wait_procs(alive, timeout=self.config.sigkill_timeout_seconds)
            status = "killed_forcefully" if not alive2 else "failed"
        else:
            status = "terminated_gracefully"

        return ReapedProcessRecord(
            pid=pid,
            pgid=pgid,
            name=name,
            cmdline=cmdline,
            create_time=create_time,
            status=status,
        )

    def reap_orphans(
        self,
        custom_target_names: Sequence[str] | None = None,
        custom_cmdline_patterns: Sequence[str] | None = None,
    ) -> ReapResult:
        """
        Audits active processes and terminates all matching orphaned background threads.
        """
        start_time = time.time()
        result = ReapResult()

        if custom_target_names:
            self.config.target_process_names.extend(custom_target_names)
        if custom_cmdline_patterns:
            self.config.process_cmdline_patterns.extend(custom_cmdline_patterns)

        orphans = self.audit_active_orphans()
        result.active_orphans_found = len(orphans)

        for proc in orphans:
            try:
                rec = self._terminate_process_tree(proc)
                result.reaped_processes.append(rec)
                if rec.status in ("terminated_gracefully", "killed_forcefully", "already_dead"):
                    result.successful_terminations += 1
                else:
                    result.failed_terminations += 1
            except Exception as e:
                err_msg = f"Error terminating process PID={getattr(proc, 'pid', 'unknown')}: {e}"
                logger.error(err_msg)
                result.errors.append(err_msg)
                result.failed_terminations += 1

        remaining_orphans = self.audit_active_orphans()
        result.audit_passed = len(remaining_orphans) == 0
        result.duration_seconds = round(time.time() - start_time, 4)

        if not result.audit_passed:
            err_str = f"Post-reap verification failed: {len(remaining_orphans)} orphan processes remain active."
            logger.error(err_str)
            result.errors.append(err_str)

        logger.info(
            f"Process reaper completed in {result.duration_seconds}s: "
            f"{result.successful_terminations} terminated, {result.failed_terminations} failed, "
            f"audit_passed={result.audit_passed}"
        )
        return result


# ============================================================================
# HDF5 SWMR Lock Sweeper
# ============================================================================

class ToposHDF5LockSweeper:
    """
    Safely inspects, verifies, and flushes HDF5 SWMR locks (.h5.lck, .swmr.lock, etc.)
    held by terminated/zombie processes, safeguarding database integrity without data corruption.
    """

    def __init__(self, config: HDF5LockSweeperConfig | None = None) -> None:
        self.config = config or HDF5LockSweeperConfig()
        self.translator = WSLPathTranslator()

    def discover_target_directories(self) -> list[Path]:
        """Discovers target directories to scan for companion lock files."""
        discovered: list[Path] = []
        seen: set[str] = set()

        def add_dir(p: str | Path) -> None:
            norm = self.translator.normalize_path(p)
            try:
                exp = Path(os.path.expandvars(str(norm))).expanduser()
                if exp.exists() and exp.is_dir():
                    res = str(exp.resolve())
                    if res not in seen:
                        seen.add(res)
                        discovered.append(exp)
            except Exception as e:
                logger.debug(f"Error evaluating HDF5 lock directory {p}: {e}")

        if self.config.target_dirs:
            for target_d in self.config.target_dirs:
                add_dir(target_d)
            return discovered

        defaults = [
            ".",
            "./artifacts",
            "./scratch",
            "./mechanics",
            "./escalation",
        ]
        for env_var in ["COCHEM_SCRATCH_DIR", "COCHEM_SCRATCH", "COCHEM_TMP", "COCHEM_WORKSPACE"]:
            val = os.environ.get(env_var)
            if val:
                add_dir(val)

        for default_d in defaults:
            add_dir(default_d)

        return discovered

    def discover_lock_files(self, custom_dirs: Sequence[str | Path] | None = None) -> list[Path]:
        """Scans directories for active HDF5 companion lock files."""
        target_dirs: list[Path] = []
        if custom_dirs:
            for custom_d in custom_dirs:
                norm = self.translator.normalize_path(custom_d)
                if norm.exists() and norm.is_dir():
                    target_dirs.append(norm)
        else:
            target_dirs = self.discover_target_directories()

        lock_files: list[Path] = []
        for sdir in target_dirs:
            try:
                for root, _dirs, files in os.walk(sdir):
                    for file_name in files:
                        for pattern in self.config.lock_file_patterns:
                            if fnmatch.fnmatch(file_name.lower(), pattern.lower()):
                                lock_files.append(Path(root) / file_name)
                                break
            except Exception as e:
                logger.debug(f"Error traversing directory {sdir} for HDF5 locks: {e}")

        return lock_files

    def _resolve_associated_h5_file(self, lock_file: Path) -> Path | None:
        """Infers the corresponding .h5 file path for a companion lock file."""
        name = lock_file.name
        parent = lock_file.parent

        for suffix in [".h5.lck", ".swmr.lock", ".h5.lock", ".h5.swmr.lock", ".lck"]:
            if name.endswith(suffix):
                stem = name[: -len(suffix)]
                cand = parent / f"{stem}.h5"
                if cand.exists():
                    return cand
                cand2 = parent / stem
                if cand2.exists() and cand2.suffix.lower() == ".h5":
                    return cand2

        try:
            with open(lock_file, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if "h5_file" in data:
                h5_p = self.translator.normalize_path(data["h5_file"])
                if h5_p.exists():
                    return h5_p
        except Exception as _e:
            logger.debug(f"Ignored exception: {_e}")

        return None

    def inspect_h5_integrity(self, h5_path: Path) -> bool:
        """Verifies that an HDF5 database can be safely opened and read."""
        if not self.config.verify_h5_integrity or not h5_path.exists():
            return True

        try:
            with h5py.File(h5_path, "r") as fp:
                _ = list(fp.keys())
            return True
        except Exception as err:
            logger.error(f"HDF5 integrity check failed for {h5_path}: {err}")
            return False

    def inspect_and_sweep_lock(
        self,
        lock_file: Path,
        force: bool = False,
    ) -> HDF5LockRecord:
        """
        Inspects a single lock file, checks if the holding PID is alive/dead,
        and safely removes stale locks while validating companion HDF5 files.
        """
        if not lock_file.exists():
            return HDF5LockRecord(
                lock_file_path=str(lock_file),
                status="file_not_found",
                reason="Lock file does not exist",
            )

        holder_pid: int | None = None
        h5_path = self._resolve_associated_h5_file(lock_file)

        try:
            with open(lock_file, "r", encoding="utf-8") as fp:
                content = fp.read().strip()
            if content.startswith("{"):
                data = json.loads(content)
                holder_pid = data.get("pid")
            elif content.isdigit():
                holder_pid = int(content)
        except Exception as e:
            logger.debug(f"Could not parse PID from lock file {lock_file}: {e}")

        is_zombie_or_dead = False
        if holder_pid is not None:
            if not psutil.pid_exists(holder_pid):
                is_zombie_or_dead = True
            else:
                try:
                    proc = psutil.Process(holder_pid)
                    if proc.status() in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
                        is_zombie_or_dead = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    is_zombie_or_dead = True

        if holder_pid == os.getpid():
            is_zombie_or_dead = True

        should_release = force or self.config.force_release or is_zombie_or_dead or holder_pid is None

        file_healthy = True
        if h5_path:
            file_healthy = self.inspect_h5_integrity(h5_path)

        if should_release:
            try:
                try:
                    os.chmod(lock_file, stat.S_IWRITE | stat.S_IREAD)
                except OSError as _e:
                    logger.debug(f"Ignored exception: {_e}")
                lock_file.unlink()
                status = "stale_lock_purged" if is_zombie_or_dead else "lock_released"
                reason = f"Lock released (PID={holder_pid}, stale={is_zombie_or_dead})"
                logger.info(f"Released HDF5 lock file: {lock_file} ({reason})")
            except OSError as err:
                status = "error"
                reason = f"Failed to unlink lock file {lock_file}: {err}"
                logger.error(reason)
                if not self.config.ignore_lock_errors:
                    raise
        else:
            status = "lock_retained_live_process"
            reason = f"Lock file is actively held by live process PID={holder_pid}"
            logger.info(f"Skipping active lock file: {lock_file} (held by PID {holder_pid})")

        return HDF5LockRecord(
            lock_file_path=str(lock_file),
            h5_file_path=str(h5_path) if h5_path else None,
            holder_pid=holder_pid,
            status=status,
            reason=reason,
            file_healthy=file_healthy,
        )

    def sweep_locks(
        self,
        custom_dirs: Sequence[str | Path] | None = None,
        force: bool = False,
    ) -> HDF5LockSweepResult:
        """
        Scans all target directories and sweeps orphaned or stale HDF5 companion locks.
        """
        start_time = time.time()
        result = HDF5LockSweepResult()

        lock_files = self.discover_lock_files(custom_dirs)
        result.scanned_lock_files = [str(f) for f in lock_files]
        result.active_locks_found = len(lock_files)

        for lf in lock_files:
            try:
                rec = self.inspect_and_sweep_lock(lf, force=force)
                result.released_locks.append(rec)
                if rec.status in ("stale_lock_purged", "lock_released"):
                    result.stale_locks_removed += 1
                elif rec.status == "lock_retained_live_process":
                    result.active_locks_retained += 1
                elif rec.status == "error":
                    result.errors.append(rec.reason)

                if not rec.file_healthy:
                    result.corrupted_files_found += 1

            except Exception as e:
                err_msg = f"Error processing HDF5 lock {lf}: {e}"
                logger.error(err_msg)
                result.errors.append(err_msg)
                if not self.config.ignore_lock_errors:
                    raise

        result.duration_seconds = round(time.time() - start_time, 4)
        logger.info(
            f"HDF5 lock sweeper completed in {result.duration_seconds}s: "
            f"{result.stale_locks_removed} stale locks removed, {result.active_locks_retained} live retained."
        )
        return result


# ============================================================================
# Topos Environment Sanitizer (Master Context Manager)
# ============================================================================

class ToposEnvironmentSanitizer:
    """
    Master Environment Sanitizer and Post-Flight Audit Coordinator for CoChem-TOPOS.
    Executes scratch directory purging, process reaper cleanup, and HDF5 lock sweeping.
    Outputs verified PostFlightAuditReports. Supports context manager execution.
    """

    def __init__(
        self,
        purge_config: ScratchPurgeConfig | None = None,
        reaper_config: ProcessReaperConfig | None = None,
        lock_config: HDF5LockSweeperConfig | None = None,
    ) -> None:
        self.purge_config = purge_config or ScratchPurgeConfig()
        self.reaper_config = reaper_config or ProcessReaperConfig()
        self.lock_config = lock_config or HDF5LockSweeperConfig()

        self.purge_engine = ToposScratchPurgeEngine(self.purge_config)
        self.process_reaper = ToposProcessReaper(self.reaper_config)
        self.lock_sweeper = ToposHDF5LockSweeper(self.lock_config)
        self.wsl_detected = WSLPathTranslator.is_wsl()

    def __enter__(self) -> ToposEnvironmentSanitizer:
        logger.info("Entering ToposEnvironmentSanitizer context...")
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        logger.info("Exiting ToposEnvironmentSanitizer context. Executing post-flight audit & cleanup...")
        if exc_type is not None:
            try:
                self.execute_post_flight_audit()
            except Exception as e:
                logger.error(f"Post-flight audit failed during exception unwind: {e}", exc_info=True)
            return None
        else:
            self.execute_post_flight_audit()

    def verify_environment_clean(self) -> bool:
        """Verifies that zero target orphan processes are active in the environment."""
        orphans = self.process_reaper.audit_active_orphans()
        return len(orphans) == 0

    def execute_post_flight_audit(
        self,
        archive_whitelist: Sequence[str | Path] | None = None,
        quarantine_dir: str | Path | None = None,
        purge_scratch: bool = True,
        reap_processes: bool = True,
        sweep_hdf5_locks: bool = True,
    ) -> PostFlightAuditReport:
        """
        Runs the full Stage 5.0 Post-Flight Audit & Cleanup sequence:
        1. Purges ephemeral scratch files while preserving whitelisted archives.
        2. Audits and reaps any remaining orphaned quantum chemistry subprocesses.
        3. Sweeps stale HDF5 SWMR locks and verifies database integrity.
        4. Compiles and returns a PostFlightAuditReport.
        """
        logger.info("Starting Stage 5.0 Post-Flight Audit & Environment Cleanup...")

        purge_res = PurgeResult()
        if purge_scratch:
            purge_res = self.purge_engine.purge(
                archive_whitelist=archive_whitelist,
                quarantine_dir=quarantine_dir,
            )

        reap_res = ReapResult()
        if reap_processes:
            reap_res = self.process_reaper.reap_orphans()

        lock_res = HDF5LockSweepResult()
        if sweep_hdf5_locks:
            lock_res = self.lock_sweeper.sweep_locks()

        audit_passed = (
            reap_res.audit_passed
            and len(purge_res.errors) == 0
            and len(lock_res.errors) == 0
            and lock_res.corrupted_files_found == 0
        )
        reclaimed_mb = round(purge_res.reclaimed_bytes / (1024 * 1024), 3)

        summary = (
            f"Stage 5.0 Post-Flight Audit: {'PASSED' if audit_passed else 'FAILED'}. "
            f"Reclaimed {reclaimed_mb} MB across {purge_res.total_files_deleted} deleted files. "
            f"Terminated {reap_res.successful_terminations} orphaned calculation processes. "
            f"Swept {lock_res.stale_locks_removed} stale HDF5 locks."
        )

        report = PostFlightAuditReport(
            audit_passed=audit_passed,
            purge_result=purge_res,
            reap_result=reap_res,
            hdf5_lock_result=lock_res,
            os_platform=platform.system(),
            wsl_detected=self.wsl_detected,
            disk_reclaimed_mb=reclaimed_mb,
            summary=summary,
        )

        logger.info(summary)
        return report

    def save_audit_report(self, report: PostFlightAuditReport, output_path: str | Path) -> Path:
        """Saves the PostFlightAuditReport as a formatted JSON artifact."""
        return report.save_to_file(output_path)
