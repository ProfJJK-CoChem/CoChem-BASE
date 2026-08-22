"""
CoChem Setup Phase 1: Environment Gatekeeper.
Production-grade, zero-mock gatekeeping engine for host OS validation, WSL2 9P mount trap detection,
Linux kernel/virtual memory limits probing, toolchain interrogation, and atomic state serialization.

SRS Document 2 Part 2 & Document 5 Compliant.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

# =============================================================================
# 1. EXCEPTIONS
# =============================================================================


class WSL9PMountError(RuntimeError):
    """
    Raised when the workspace or target path is located on a WSL2 9P / drvfs mount.
    9P mounts cause POSIX lock failures, lack atomic rename guarantees, and trigger
    wave-function segmentation faults during high-performance quantum chemistry calculations.
    """


class Phase1AuditError(RuntimeError):
    """Raised when critical phase 1 environment prerequisites fail fatally."""


# =============================================================================
# 2. PYDANTIC V2 DATA MODELS
# =============================================================================


class PhaseStatus(str, Enum):
    """Status enumeration for setup phase execution."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"


class ToolchainItem(BaseModel):
    """Structured inspection record for a toolchain/compiler binary."""

    name: str = Field(..., description="Binary name (e.g. gcc, make, git)")
    path: Optional[str] = Field(default=None, description="Absolute filesystem path to binary")
    version: Optional[str] = Field(default=None, description="Reported version string")
    is_available: bool = Field(
        default=False, description="Whether binary is available and executable"
    )
    error_detail: Optional[str] = Field(
        default=None, description="Diagnostic error detail if unavailable"
    )


class OSProfile(BaseModel):
    """Operating system profile capturing kernel and virtualization characteristics."""

    system: str = Field(..., description="Host OS system name (e.g. Linux, Windows, Darwin)")
    release: str = Field(..., description="Kernel release version")
    version: str = Field(..., description="OS build/version detail")
    machine: str = Field(..., description="Host CPU architecture")
    is_wsl: bool = Field(default=False, description="Whether execution is running under WSL/WSL2")
    is_windows: bool = Field(default=False, description="Whether execution is native Windows NT")
    is_posix: bool = Field(default=False, description="Whether host conforms to POSIX semantics")


class FilesystemAudit(BaseModel):
    """Filesystem topology audit and POSIX compliance record."""

    target_path: str = Field(..., description="Target working directory or workspace path")
    mount_point: Optional[str] = Field(default=None, description="Detected mount point root")
    fs_type: Optional[str] = Field(
        default=None, description="Filesystem type (ext4, xfs, 9p, drvfs, NTFS)"
    )
    is_9p_mount: bool = Field(default=False, description="Whether target is mounted on 9P/drvfs")
    is_posix_compliant: bool = Field(
        default=True, description="Whether filesystem supports full POSIX semantics"
    )


class KernelLimitsAudit(BaseModel):
    """Linux kernel and Windows PE virtual memory limits record."""

    vm_max_map_count: Optional[int] = Field(
        default=None, description="Value of /proc/sys/vm/max_map_count"
    )
    stack_limit_bytes: Optional[int] = Field(
        default=None, description="Stack limit in bytes (-1 for unlimited)"
    )
    stack_unlimited: bool = Field(default=False, description="Whether RLIMIT_STACK is unlimited")
    degraded_mode: bool = Field(
        default=False, description="Whether environment must run in degraded/safe mode"
    )
    recommended_flags: List[str] = Field(
        default_factory=list, description="Recommended compiler/linker flags"
    )


class Phase1AuditReport(BaseModel):
    """Comprehensive serialized audit report for Phase 1 Environment Gatekeeper."""

    phase_id: str = Field(
        default="PHASE_1_ENVIRONMENT_GATEKEEPER", description="Unique phase identifier"
    )
    status: PhaseStatus = Field(..., description="Overall gatekeeper status")
    timestamp_utc: str = Field(..., description="UTC ISO-8601 audit timestamp")
    os_profile: OSProfile = Field(..., description="Host OS profile")
    filesystem: FilesystemAudit = Field(..., description="Filesystem audit details")
    toolchains: Dict[str, ToolchainItem] = Field(..., description="Inspected toolchains")
    kernel_limits: KernelLimitsAudit = Field(..., description="Kernel and stack limits")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal environment warnings")
    errors: List[str] = Field(default_factory=list, description="Fatal environment errors")
    artifact_path: Optional[str] = Field(
        default=None, description="Destination path of p1.json artifact"
    )


# =============================================================================
# 3. IDEMPOTENCY & ROLLBACK CONTEXT MANAGER
# =============================================================================


class DependencyManager:
    """
    Idempotent transactional context manager for managing temporary filesystem
    artifacts and executing atomic JSON state persistence.
    Rolls back staged temporary files/directories if an exception occurs during execution.
    """

    def __init__(self) -> None:
        self._tracked_temp_files: List[Path] = []
        self._tracked_temp_dirs: List[Path] = []

    def __enter__(self) -> DependencyManager:
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        if exc_type is not None:
            # Exception occurred -> clean up staged temp artifacts
            self.rollback()

    def track_temp_file(self, path: Union[str, Path]) -> Path:
        """Register a temporary file to be rolled back on failure."""
        p = Path(path).resolve()
        if p not in self._tracked_temp_files:
            self._tracked_temp_files.append(p)
        return p

    def track_temp_dir(self, path: Union[str, Path]) -> Path:
        """Register a temporary directory to be rolled back on failure."""
        p = Path(path).resolve()
        if p not in self._tracked_temp_dirs:
            self._tracked_temp_dirs.append(p)
        return p

    def create_temp_file(
        self,
        suffix: str = ".tmp",
        prefix: str = "cochem_p1_",
        directory: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Create a tracked temporary file."""
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
        prefix: str = "cochem_p1_stage_",
        directory: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Create a tracked temporary directory."""
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

    def rollback(self) -> None:
        """Explicitly purge all tracked temporary files and directories."""
        for temp_file in self._tracked_temp_files:
            try:
                if temp_file.exists() and temp_file.is_file():
                    temp_file.unlink()
            except OSError:
                pass
        self._tracked_temp_files.clear()

        for temp_dir in self._tracked_temp_dirs:
            try:
                if temp_dir.exists() and temp_dir.is_dir():
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except OSError:
                pass
        self._tracked_temp_dirs.clear()

    def atomic_write_json(
        self,
        target_path: Union[str, Path],
        data: Union[BaseModel, Dict[str, Any], Any],
        indent: int = 2,
    ) -> Path:
        """
        Atomically write JSON content to target_path using a staged temporary file and os.replace.
        """
        target = Path(target_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        # Create staged temporary file in the same directory for atomic replace guarantees
        unique_suffix = f".tmp.{uuid.uuid4().hex[:8]}"
        staged_file = target.parent / f"{target.name}{unique_suffix}"
        self.track_temp_file(staged_file)

        # Format JSON payload
        if isinstance(data, BaseModel):
            payload = data.model_dump_json(indent=indent)
        elif isinstance(data, (dict, list)):
            payload = json.dumps(data, indent=indent, default=str)
        else:
            payload = json.dumps(data, indent=indent, default=str)

        # Write to staged file
        with open(staged_file, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())

        # Atomic rename replacing destination
        os.replace(staged_file, target)

        # Remove from tracked temp files now that it is permanently committed
        if staged_file in self._tracked_temp_files:
            self._tracked_temp_files.remove(staged_file)

        return target


# =============================================================================
# 4. OS & WSL2 INTERROGATION
# =============================================================================


def is_wsl_environment() -> bool:
    """
    Detect whether the current process is running inside Windows Subsystem for Linux (WSL).
    """
    if platform.system() != "Linux":
        return False

    # Check /proc/version
    try:
        proc_ver = Path("/proc/version")
        if proc_ver.exists():
            content = proc_ver.read_text(encoding="utf-8", errors="ignore").lower()
            if "microsoft" in content or "wsl" in content:
                return True
    except OSError:
        pass

    # Check release string
    release_str = platform.release().lower()
    if "microsoft" in release_str or "wsl" in release_str:
        return True

    # Check environment variables
    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
        return True

    # Check binfmt_misc
    if Path("/proc/sys/fs/binfmt_misc/WSLInterop").exists():
        return True

    return False


def interrogate_os() -> OSProfile:
    """
    Programmatically interrogate host operating system details.
    """
    sys_name = platform.system()
    rel = platform.release()
    ver = platform.version()
    mach = platform.machine()
    is_windows = os.name == "nt" or sys_name.lower() == "windows"
    is_posix = os.name == "posix"
    is_wsl = is_wsl_environment()

    return OSProfile(
        system=sys_name,
        release=rel,
        version=ver,
        machine=mach,
        is_wsl=is_wsl,
        is_windows=is_windows,
        is_posix=is_posix,
    )


# =============================================================================
# 5. WSL2 9P MOUNT TRAP & FILESYSTEM AUDIT
# =============================================================================


def parse_mount_table_entry(line: str) -> Optional[Tuple[str, str, str, str]]:
    """
    Parse a single line from /proc/mounts into (device, mount_point, fs_type, options).
    A valid Linux mount table entry contains 6 fields: spec, file, vfstype, mntops, freq, passno.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    parts = line.split()
    if len(parts) < 6:
        return None

    # Verify passno/freq are numeric digits as required by /proc/mounts format
    if not (parts[4].isdigit() and parts[5].isdigit()):
        return None

    device = parts[0]
    mount_point = parts[1]
    fs_type = parts[2]
    options = parts[3]
    return device, mount_point, fs_type, options


def check_wsl_9p_mount(
    target_path: Union[str, Path],
    mount_table_content: Optional[str] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Inspect filesystem mounts to determine if target_path is on a 9P / drvfs mount.
    Returns (is_9p_mount, mount_point, fs_type).
    """
    # Normalize input path for cross-platform comparison
    raw_path_str = str(target_path).replace("\\", "/")
    # Strip Windows drive letter prefix if simulating POSIX paths (e.g. D:/mnt/c -> /mnt/c)
    if len(raw_path_str) >= 2 and raw_path_str[1] == ":" and raw_path_str[2:].startswith("/mnt/"):
        posix_candidate = raw_path_str[2:]
    else:
        posix_candidate = raw_path_str

    if not posix_candidate.startswith("/"):
        posix_candidate = "/" + posix_candidate.lstrip("/")

    # Read mount table
    lines: List[str] = []
    if mount_table_content is not None:
        lines = mount_table_content.splitlines()
    else:
        mounts_path = Path("/proc/mounts")
        if mounts_path.exists():
            try:
                lines = mounts_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                lines = []

    # Find longest matching mount point
    matched_mount: Optional[str] = None
    matched_fs_type: Optional[str] = None
    matched_options: Optional[str] = None

    for line in lines:
        entry = parse_mount_table_entry(line)
        if not entry:
            continue
        dev, mount_pt, fs_type, opts = entry
        norm_mount = mount_pt.rstrip("/") if mount_pt != "/" else "/"

        matches = (
            posix_candidate == norm_mount
            or posix_candidate.startswith(norm_mount + "/")
            or (norm_mount == "/" and posix_candidate.startswith("/"))
        )

        if matches:
            if matched_mount is None or len(norm_mount) >= len(matched_mount):
                matched_mount = norm_mount
                matched_fs_type = fs_type
                matched_options = opts

    # Determine 9p / drvfs status
    is_9p = False
    if matched_fs_type:
        fs_lower = matched_fs_type.lower()
        if "9p" in fs_lower or "drvfs" in fs_lower:
            is_9p = True
    if matched_options and (
        "drvfs" in matched_options.lower() or "aname=drvfs" in matched_options.lower()
    ):
        is_9p = True

    # Fallback heuristic for WSL /mnt/<drive>
    if not is_9p and (
        posix_candidate.startswith("/mnt/")
        and (len(posix_candidate) == 6 or (len(posix_candidate) > 6 and posix_candidate[6] == "/"))
    ):
        is_9p = True
        if matched_fs_type is None:
            matched_fs_type = "drvfs"
        if matched_mount is None:
            matched_mount = posix_candidate[:6]

    return is_9p, matched_mount, matched_fs_type


def audit_filesystem(target_path: Optional[Union[str, Path]] = None) -> FilesystemAudit:
    """
    Audit filesystem at target_path for 9P mounts and POSIX compliance.
    Raises WSL9PMountError if running in WSL and target is on a 9P/drvfs mount.
    """
    path_obj = Path(target_path).resolve() if target_path else Path.cwd().resolve()
    target_str = str(path_obj)
    is_wsl = is_wsl_environment()
    is_windows = (os.name == "nt" or platform.system().lower() == "windows") and not is_wsl

    if is_windows:
        return FilesystemAudit(
            target_path=target_str,
            mount_point=str(path_obj.anchor) if path_obj.anchor else None,
            fs_type="NTFS",
            is_9p_mount=False,
            is_posix_compliant=False,
        )

    # POSIX / Linux / WSL audit
    is_9p, mount_point, fs_type = check_wsl_9p_mount(path_obj)

    if is_wsl and is_9p:
        error_msg = (
            f"CRITICAL: WSL2 9P Mount Trap Detected! Target path '{target_str}' is mounted on "
            f"'{mount_point}' (type: '{fs_type}'). 9P drvfs mounts lack POSIX file-locking, atomic "
            f"rename fidelity, and high-throughput memory-mapping required for quantum wave-function calculations. "
            f"REMEDIATION: Move your workspace to native Linux ext4/xfs storage (e.g. /home/<user>/... or ~)."
        )
        raise WSL9PMountError(error_msg)

    is_posix = not is_9p and not is_windows

    return FilesystemAudit(
        target_path=target_str,
        mount_point=mount_point,
        fs_type=fs_type or ("ext4" if not is_windows else "NTFS"),
        is_9p_mount=is_9p,
        is_posix_compliant=is_posix,
    )


# =============================================================================
# 6. LINUX KERNEL & VIRTUAL MEMORY LIMITS AUDIT
# =============================================================================


def audit_kernel_limits(os_profile: OSProfile) -> KernelLimitsAudit:
    """
    Inspect virtual memory limits and stack depth constraints across operating systems.
    On Windows PE, avoids POSIX ulimit modifications and recommends compile/link stack flags.
    """
    recommended_flags: List[str] = []
    vm_max_map_count: Optional[int] = None
    stack_limit_bytes: Optional[int] = None
    stack_unlimited: bool = False
    degraded_mode: bool = False

    if os_profile.is_windows:
        # Windows PE environment
        degraded_mode = True
        recommended_flags = ["/STACK:67108864", "-Wl,--stack,67108864"]
        return KernelLimitsAudit(
            vm_max_map_count=None,
            stack_limit_bytes=None,
            stack_unlimited=False,
            degraded_mode=degraded_mode,
            recommended_flags=recommended_flags,
        )

    # POSIX / Linux environment
    # 1. Inspect vm.max_map_count
    max_map_file = Path("/proc/sys/vm/max_map_count")
    if max_map_file.exists():
        try:
            val_str = max_map_file.read_text(encoding="utf-8").strip()
            vm_max_map_count = int(val_str)
            if vm_max_map_count < 262144:
                recommended_flags.append("sysctl -w vm.max_map_count=262144")
        except (OSError, ValueError):
            pass

    # 2. Interrogate RLIMIT_STACK
    try:
        import resource  # Available on POSIX

        rlim_infinity = resource.RLIM_INFINITY  # type: ignore[attr-defined]
        rlimit_stack = resource.RLIMIT_STACK  # type: ignore[attr-defined]
        soft, hard = resource.getrlimit(rlimit_stack)  # type: ignore[attr-defined]
        if soft == rlim_infinity:
            stack_unlimited = True
            stack_limit_bytes = -1
        else:
            stack_limit_bytes = soft
            # Target 64MB = 67,108,864 bytes
            target_stack = 64 * 1024 * 1024
            if soft < target_stack:
                # Attempt non-privileged soft limit expansion up to hard limit
                new_soft = min(hard, target_stack) if hard != rlim_infinity else target_stack
                try:
                    resource.setrlimit(rlimit_stack, (new_soft, hard))  # type: ignore[attr-defined]
                    soft_updated, _ = resource.getrlimit(rlimit_stack)  # type: ignore[attr-defined]
                    stack_limit_bytes = soft_updated
                    if soft_updated < target_stack:
                        degraded_mode = True
                        recommended_flags.append("-Wl,-z,stack-size=67108864")
                except (OSError, ValueError, PermissionError):
                    degraded_mode = True
                    recommended_flags.append("-Wl,-z,stack-size=67108864")
    except (ImportError, AttributeError):
        degraded_mode = True

    return KernelLimitsAudit(
        vm_max_map_count=vm_max_map_count,
        stack_limit_bytes=stack_limit_bytes,
        stack_unlimited=stack_unlimited,
        degraded_mode=degraded_mode,
        recommended_flags=recommended_flags,
    )


# =============================================================================
# 7. TOOLCHAIN & COMPILER AUDIT
# =============================================================================


def audit_toolchain_binary(name: str, timeout_seconds: float = 5.0) -> ToolchainItem:
    """
    Probe presence and version of a specific compiler or system utility.
    """
    binary_path = shutil.which(name)
    if not binary_path:
        return ToolchainItem(
            name=name,
            path=None,
            version=None,
            is_available=False,
            error_detail=f"Binary '{name}' not found in PATH",
        )

    try:
        res = subprocess.run(
            [binary_path, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        output = res.stdout if res.stdout else res.stderr
        version_line = output.splitlines()[0].strip() if output else "Version output empty"
        return ToolchainItem(
            name=name,
            path=str(Path(binary_path).resolve()),
            version=version_line,
            is_available=True,
            error_detail=None,
        )
    except subprocess.TimeoutExpired:
        return ToolchainItem(
            name=name,
            path=str(Path(binary_path).resolve()),
            version=None,
            is_available=False,
            error_detail=f"Execution timed out after {timeout_seconds}s",
        )
    except Exception as exc:
        return ToolchainItem(
            name=name,
            path=str(Path(binary_path).resolve()),
            version=None,
            is_available=False,
            error_detail=f"Probe failure: {str(exc)}",
        )


def audit_toolchains(tools: Optional[List[str]] = None) -> Dict[str, ToolchainItem]:
    """
    Audit all standard or specified toolchains (default: gcc, make, git).
    """
    target_tools = tools if tools is not None else ["gcc", "make", "git"]
    results: Dict[str, ToolchainItem] = {}
    for tool in target_tools:
        results[tool] = audit_toolchain_binary(tool)
    return results


# =============================================================================
# 8. ARTIFACT & REGISTRY RESOLUTION
# =============================================================================


def resolve_p1_registry_path(output_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve destination path for p1.json intermediate state artifact.
    """
    if output_dir:
        out_path = Path(output_dir).resolve()
        if out_path.name == "p1.json":
            return out_path
        return out_path / "p1.json"

    # Dynamic resolution via cochem_base.config_loader if available
    try:
        from cochem_base.config_loader import get_artifact_dir

        return get_artifact_dir() / "Registry" / "p1.json"
    except ImportError:
        pass

    # Standard fallback paths
    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        return Path(env_art).resolve() / "Registry" / "p1.json"

    repo_root = Path.cwd()
    agent_artifacts = repo_root / ".agent_artifacts"
    if agent_artifacts.exists():
        return agent_artifacts / "Registry" / "p1.json"

    home_artifacts = Path.home() / "CoChem_Artifacts"
    return home_artifacts / "Registry" / "p1.json"


# =============================================================================
# 9. PROGRAMMATIC AUDIT PIPELINE ENTRYPOINT
# =============================================================================


def run_phase_1_audit(
    output_dir: Optional[Union[str, Path]] = None,
    target_path: Optional[Union[str, Path]] = None,
) -> Phase1AuditReport:
    """
    Execute full Phase 1 Environment Gatekeeper audit pipeline.
    Validates host OS, detects 9P mount trap, inspects kernel limits, audits toolchains,
    and atomically serializes p1.json to the Registry directory.
    """
    timestamp_utc = datetime.now(timezone.utc).isoformat()
    warnings: List[str] = []
    errors: List[str] = []

    # 1. OS Profile
    os_profile = interrogate_os()

    # 2. Filesystem Audit (raises WSL9PMountError on 9P trap in WSL)
    fs_audit = audit_filesystem(target_path)

    # 3. Kernel Limits Audit
    kernel_limits = audit_kernel_limits(os_profile)
    if os_profile.is_windows:
        warnings.append(
            "Host is Windows PE: dynamic stack expansion via ulimit unavailable. Using compiler stack flags."
        )
    elif kernel_limits.degraded_mode:
        warnings.append(
            "Host Linux stack limit could not be raised to >= 64MB. Large wave-functions may segfault."
        )

    if kernel_limits.vm_max_map_count is not None and kernel_limits.vm_max_map_count < 262144:
        warnings.append(
            f"vm.max_map_count is {kernel_limits.vm_max_map_count} (recommended >= 262144)."
        )

    # 4. Toolchain Audit
    toolchains = audit_toolchains(["gcc", "make", "git"])
    for name, item in toolchains.items():
        if not item.is_available:
            warnings.append(
                f"Toolchain binary '{name}' not found or inaccessible: {item.error_detail}"
            )

    # 5. Determine Overall Status
    if errors:
        status = PhaseStatus.FAILED
    elif kernel_limits.degraded_mode or any(not t.is_available for t in toolchains.values()):
        status = PhaseStatus.DEGRADED
    else:
        status = PhaseStatus.PASSED

    # 6. Destination Artifact Path
    p1_path = resolve_p1_registry_path(output_dir)

    # 7. Construct Initial Report
    report = Phase1AuditReport(
        phase_id="PHASE_1_ENVIRONMENT_GATEKEEPER",
        status=status,
        timestamp_utc=timestamp_utc,
        os_profile=os_profile,
        filesystem=fs_audit,
        toolchains=toolchains,
        kernel_limits=kernel_limits,
        warnings=warnings,
        errors=errors,
        artifact_path=str(p1_path),
    )

    # 8. Idempotent Atomic Persistence
    with DependencyManager() as dm:
        dm.atomic_write_json(p1_path, report)

    return report


# =============================================================================
# 10. CLI ENTRYPOINT
# =============================================================================


def main(argv: Optional[List[str]] = None) -> int:
    """
    Command-line entrypoint for CoChem Setup Phase 1: Environment Gatekeeper.
    Returns 0 on PASSED/DEGRADED, non-zero on FAILED or unhandled WSL9PMountError.
    """
    parser = argparse.ArgumentParser(
        description="CoChem Setup Phase 1: Environment Gatekeeper CLI",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help="Custom output directory for Registry/p1.json",
    )
    parser.add_argument(
        "--target-path",
        "-t",
        type=str,
        default=None,
        help="Target workspace directory to audit (defaults to CWD)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON report to stdout",
    )

    args = parser.parse_args(argv)

    try:
        report = run_phase_1_audit(
            output_dir=args.output_dir,
            target_path=args.target_path,
        )

        if args.json:
            print(report.model_dump_json(indent=2))
        else:
            print("=" * 70)
            print("COCHEM SETUP PHASE 1: ENVIRONMENT GATEKEEPER AUDIT")
            print("=" * 70)
            print(f"Phase ID:        {report.phase_id}")
            print(f"Status:          {report.status.value}")
            print(f"Timestamp UTC:   {report.timestamp_utc}")
            print(f"OS Target:       {report.os_profile.system} ({report.os_profile.machine})")
            print(f"WSL Detected:    {report.os_profile.is_wsl}")
            print(
                f"Filesystem:      {report.filesystem.fs_type} (POSIX Compliant: {report.filesystem.is_posix_compliant})"
            )
            print(f"Artifact Path:   {report.artifact_path}")
            print("-" * 70)
            print("Toolchains:")
            for name, item in report.toolchains.items():
                avail = "AVAILABLE" if item.is_available else "MISSING"
                ver = f" - {item.version}" if item.version else ""
                print(f"  [{avail}] {name}: {item.path or item.error_detail}{ver}")
            print("-" * 70)
            print(f"Warnings: {len(report.warnings)}")
            for w in report.warnings:
                print(f"  - {w}")
            print(f"Errors:   {len(report.errors)}")
            for e in report.errors:
                print(f"  - {e}")
            print("=" * 70)

        if report.status is PhaseStatus.FAILED:
            return 1
        return 0

    except WSL9PMountError as wsl_err:
        sys.stderr.write(f"\n[FATAL WSL 9P MOUNT ERROR]\n{wsl_err}\n\n")
        return 2
    except Exception as exc:
        sys.stderr.write(f"\n[FATAL PHASE 1 ERROR]\n{exc}\n\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
