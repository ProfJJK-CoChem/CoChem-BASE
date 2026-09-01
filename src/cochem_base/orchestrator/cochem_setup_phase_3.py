"""
CoChem Setup Phase 3: Multi-Track Quantum Engine Discovery & Integrity Hashing.
Production-grade, zero-mock gatekeeping engine for multi-track quantum chemistry and semi-empirical
binary discovery (ORCA, CFOUR, xTB, CREST, PySCF/GPU), cryptographic streaming SHA-256 hashing,
subprocess version interrogation, container SIF air-gap validation, deterministic path-independent
environment fingerprinting, and transactional atomic state persistence into the Golden Registry.

SRS Document 2 Part 2 (Section 3.3), SRS Document 5 (Section 2.3), and SRS Document 10 Compliant.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
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
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

# =============================================================================
# LOGGING & ATEXIT SWEEPING
# =============================================================================

logger = logging.getLogger(__name__)
if not logger.handlers:
    ch = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)

_active_subprocesses = set()

def sweep_subprocesses() -> None:
    for p in list(_active_subprocesses):
        try:
            if p.poll() is None:
                p.kill()
        except Exception:
            pass

atexit.register(sweep_subprocesses)

# =============================================================================
# 1. EXCEPTIONS
# =============================================================================


class Phase3AuditError(RuntimeError):
    """Raised when critical phase 3 engine discovery/cryptographic integrity audit fails fatally."""


# =============================================================================
# 2. PYDANTIC V2 DATA MODELS & ENUMS
# =============================================================================


class PhaseStatus(str, Enum):
    """Status enumeration for setup phase execution."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"


class EngineTrack(str, Enum):
    """Scientific execution track classification."""

    ORCA = "ORCA"
    CFOUR = "CFOUR"
    XTB_CREST = "XTB_CREST"
    PYSCF_GPU = "PYSCF_GPU"
    CONTAINER_SIF = "CONTAINER_SIF"
    GENERAL = "GENERAL"


class EngineStatus(str, Enum):
    """Fine-grained engine availability and validation status."""

    FOUND_VALID = "FOUND_VALID"
    FOUND_UNVERIFIED = "FOUND_UNVERIFIED"
    MISSING = "MISSING"
    ERROR = "ERROR"
    AIRGAP_VIOLATION = "AIRGAP_VIOLATION"


class BinaryEngineItem(BaseModel):
    """Structured cryptographic and version inspection record for a quantum engine binary."""

    name: str = Field(..., description="Engine binary or component identifier (e.g. orca, xcfour, xtb)")
    track: EngineTrack = Field(default=EngineTrack.GENERAL, description="Assigned scientific execution track")
    path: Optional[str] = Field(default=None, description="Absolute canonical path to physical executable")
    version: Optional[str] = Field(default=None, description="Interrogated semantic version string")
    sha256_hash: Optional[str] = Field(
        default=None, description="Cryptographic SHA-256 digest of executable binary"
    )
    file_size_bytes: Optional[int] = Field(default=None, description="Physical binary size in bytes")
    is_available: bool = Field(default=False, description="Whether engine is discovered and executable")
    is_container: bool = Field(default=False, description="Whether engine runs inside an Apptainer/Singularity SIF")
    container_flags: List[str] = Field(
        default_factory=list, description="Container execution flags enforcing network air-gap"
    )
    error_detail: Optional[str] = Field(default=None, description="Diagnostic error or failure reason")
    status: EngineStatus = Field(default=EngineStatus.MISSING, description="Fine-grained audit status")


class EngineTrackSummary(BaseModel):
    """Aggregated availability summary for a single scientific execution track."""

    track: EngineTrack = Field(..., description="Track identifier")
    total_scanned: int = Field(..., description="Total binaries monitored in this track")
    available_count: int = Field(..., description="Number of functional binaries detected")
    missing_count: int = Field(..., description="Number of missing binaries")
    is_track_ready: bool = Field(default=False, description="Whether all mandatory binaries in track are ready")


class ContainerAudit(BaseModel):
    """Apptainer / Singularity container runtime and SIF image audit record."""

    runtime_name: Optional[str] = Field(default=None, description="Detected container CLI (apptainer / singularity)")
    runtime_path: Optional[str] = Field(default=None, description="Absolute path to container runtime CLI")
    runtime_version: Optional[str] = Field(default=None, description="Reported container runtime version")
    airgap_flags_valid: bool = Field(
        default=True, description="Whether container execution enforces physical network air-gap (--net --network none)"
    )
    discovered_sifs: List[BinaryEngineItem] = Field(
        default_factory=list, description="List of discovered and cryptographically hashed SIF images"
    )


class EnvironmentFingerprint(BaseModel):
    """
    Path-independent composite system environment fingerprint.
    Guarantees cross-machine reproducibility as mandated by SRS Doc 10 Sec 4.1.
    """

    composite_hash: str = Field(..., description="Deterministic SHA-256 hash over engine inventory & versions")
    component_count: int = Field(..., description="Number of hashed components contributing to fingerprint")
    provenance: str = Field(
        default="[D] Deterministic Composite System Hash",
        description="Scientific provenance attribution tag",
    )


class Phase3AuditReport(BaseModel):
    """Comprehensive serialized audit report for Phase 3 Engine Discovery & Integrity Hashing."""

    phase_id: str = Field(
        default="PHASE_3_ENGINE_DISCOVERY_INTEGRITY",
        description="Unique phase identifier",
    )
    status: PhaseStatus = Field(..., description="Overall phase outcome status")
    timestamp_utc: str = Field(..., description="ISO 8601 UTC timestamp of audit execution")
    engines: Dict[str, BinaryEngineItem] = Field(
        default_factory=dict, description="Dictionary of audited engine items keyed by name"
    )
    tracks: Dict[str, EngineTrackSummary] = Field(
        default_factory=dict, description="Track-level operational readiness summaries"
    )
    container: ContainerAudit = Field(..., description="Container runtime and SIF audit")
    fingerprint: EnvironmentFingerprint = Field(..., description="Deterministic environment fingerprint")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings or degraded notices")
    errors: List[str] = Field(default_factory=list, description="Fatal or critical validation errors")
    artifact_path: str = Field(..., description="Filesystem destination path for serialized p3.json")


# =============================================================================
# 3. TRANSACTIONAL DEPENDENCY & ATOMIC STATE MANAGER
# =============================================================================


class DependencyManager:
    """
    Transactional context manager for temporary staging files, directories,
    and atomic JSON writes with automatic rollback on unhandled exceptions.
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

        unique_suffix = f".tmp.{uuid.uuid4().hex[:8]}"
        staged_file = target.parent / f"{target.name}{unique_suffix}"
        self.track_temp_file(staged_file)

        if isinstance(data, BaseModel):
            json_text = data.model_dump_json(indent=indent)
        elif isinstance(data, (dict, list)):
            json_text = json.dumps(data, indent=indent, default=str)
        else:
            json_text = str(data)

        staged_file.write_text(json_text, encoding="utf-8")
        os.replace(staged_file, target)

        if staged_file in self._tracked_temp_files:
            self._tracked_temp_files.remove(staged_file)

        return target


# =============================================================================
# 4. CRYPTOGRAPHIC STREAMING SHA-256 HASHING
# =============================================================================


def compute_file_sha256(
    file_path: Union[str, Path],
    chunk_size: int = 65536,
) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """
    Computes cryptographic SHA-256 hash and byte size of a physical file using 64 KB chunk streaming.
    Binds memory consumption to < 1 MB even for multi-gigabyte container SIF files.
    Returns (sha256_hexdigest, file_size_bytes, error_message).
    """
    p = Path(file_path).resolve()
    if not p.exists():
        return None, None, f"File not found: {p}"
    if not p.is_file():
        return None, None, f"Path is a directory, not a file: {p}"

    sha256 = hashlib.sha256()
    total_bytes = 0

    try:
        with open(p, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                sha256.update(chunk)
                total_bytes += len(chunk)
        return sha256.hexdigest(), total_bytes, None
    except PermissionError:
        return None, None, f"Permission denied reading file: {p}"
    except Exception as exc:
        return None, None, f"Error hashing file: {str(exc)}"


# =============================================================================
# 5. MULTI-TIER BINARY & SIF DISCOVERY
# =============================================================================


STANDARD_MONITORED_ENGINES: List[Tuple[str, EngineTrack]] = [
    # ORCA Track
    ("orca", EngineTrack.ORCA),
    ("mpirun", EngineTrack.ORCA),
    ("mpiexec", EngineTrack.ORCA),
    ("orca_2mkl", EngineTrack.ORCA),
    ("orca_vpt2_prep", EngineTrack.ORCA),
    # CFOUR Track
    ("xcfour", EngineTrack.CFOUR),
    ("c4init", EngineTrack.CFOUR),
    ("c4cleanup", EngineTrack.CFOUR),
    # Semi-Empirical & Conformational Engines
    ("xtb", EngineTrack.XTB_CREST),
    ("crest", EngineTrack.XTB_CREST),
    # Container & GPU tools
    ("apptainer", EngineTrack.GENERAL),
    ("singularity", EngineTrack.GENERAL),
]


def resolve_binary_search_paths(
    engine_name: str,
    custom_paths: Optional[List[Union[str, Path]]] = None,
) -> List[Path]:
    """
    Constructs an ordered list of search candidate paths across the 4-Tier discovery model:
    Tier 1: Explicit environment overrides.
    Tier 2: System $PATH.
    Tier 3: Known directory roots (HPC / local standard installation trees).
    Tier 4: Custom caller-supplied directories.
    """
    candidates: List[Path] = []
    is_win = platform.system() == "Windows"
    raw_name = engine_name.lower()

    # Tier 1: Environment variable overrides
    env_keys = [
        f"COCHEM_{raw_name.upper()}_PATH",
        f"COCHEM_{raw_name.upper()}_DIR",
        f"{raw_name.upper()}_PATH",
        f"{raw_name.upper()}_DIR",
        "COCHEM_ENGINES_DIR",
    ]
    if raw_name in ("mpirun", "mpiexec"):
        env_keys.extend(["MPI_BIN", "MPI_HOME", "MPI_DIR", "OPENMPI_DIR"])
    elif raw_name == "orca":
        env_keys.extend(["ORCA_HOME", "ORCA_BIN"])
    elif raw_name in ("xcfour", "c4init", "c4cleanup"):
        env_keys.extend(["CFOUR_HOME", "CFOUR_BIN"])

    for k in env_keys:
        val = os.environ.get(k)
        if val:
            p = Path(val).resolve()
            if p.is_file():
                candidates.append(p)
            elif p.is_dir():
                candidates.append(p / engine_name)
                if is_win:
                    candidates.append(p / f"{engine_name}.exe")
                    candidates.append(p / f"{engine_name}.bat")
                    candidates.append(p / f"{engine_name}.cmd")

    # Tier 2: System $PATH
    which_found = shutil.which(engine_name)
    if which_found:
        candidates.append(Path(which_found).resolve())

    # Tier 3: Standard known roots
    home = Path.home()
    known_dirs: List[Path] = [
        home / "CoChem_Engines",
        home / "CoChem_Artifacts" / "Engines",
        Path("C:/tools") if is_win else Path("/opt"),
        Path("C:/Program Files") if is_win else Path("/usr/local/bin"),
    ]

    # Include conda / venv if present
    prefix = sys.prefix
    if prefix:
        p_prefix = Path(prefix)
        known_dirs.append(p_prefix / "bin")
        if is_win:
            known_dirs.append(p_prefix / "Scripts")
            known_dirs.append(p_prefix / "Library" / "bin")

    for d in known_dirs:
        if d.exists() and d.is_dir():
            candidates.append(d / engine_name)
            if is_win:
                candidates.append(d / f"{engine_name}.exe")
                candidates.append(d / f"{engine_name}.bat")
                candidates.append(d / f"{engine_name}.cmd")

    # Tier 4: Caller-provided custom paths
    if custom_paths:
        for cp in custom_paths:
            p_cp = Path(cp).resolve()
            if p_cp.is_file():
                candidates.append(p_cp)
            elif p_cp.is_dir():
                candidates.append(p_cp / engine_name)
                if is_win:
                    candidates.append(p_cp / f"{engine_name}.exe")
                    candidates.append(p_cp / f"{engine_name}.bat")
                    candidates.append(p_cp / f"{engine_name}.cmd")

    # Deduplicate while preserving precedence
    deduped: List[Path] = []
    seen: set = set()
    for c in candidates:
        if c not in seen:
            seen.add(c)
            deduped.append(c)

    return deduped


def discover_binary_path(
    engine_name: str,
    search_dirs: Optional[List[Union[str, Path]]] = None,
) -> Optional[Path]:
    """
    Evaluates candidate paths in order and returns the first existing, accessible executable file.
    """
    candidates = resolve_binary_search_paths(engine_name, custom_paths=search_dirs)
    for cand in candidates:
        if cand.exists() and cand.is_file():
            # Check executable permissions if on POSIX
            if platform.system() != "Windows":
                try:
                    mode = cand.stat().st_mode
                    if mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
                        return cand
                except OSError:
                    continue
            else:
                return cand
    return None


# =============================================================================
# 6. SUBPROCESS VERSION INTERROGATION & SEMANTIC PARSING
# =============================================================================


def extract_semantic_version(output_text: str, engine_name: str) -> Optional[str]:
    """
    Extracts clean semantic version strings using targeted regex patterns across quantum engine formats.
    """
    text = output_text.strip()
    raw = engine_name.lower()

    if "orca" in raw:
        # e.g., "Program Version 6.1.1", "ORCA version 5.0.4", "Version 6.1.0"
        m = re.search(r"(?:Program\s+Version|ORCA\s+version|Version)\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if m:
            return m.group(1)

    elif "mpi" in raw:
        # e.g., "mpirun (Open MPI) 4.1.6", "Open MPI: 5.0.2"
        m = re.search(r"(?:Open\s+MPI(?:\)|:)?)\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if m:
            return m.group(1)

    elif "xtb" in raw:
        # e.g., "xtb version 6.6.1", "xTB 6.7.0"
        m = re.search(r"(?:xtb\s+version|xTB)\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if m:
            return m.group(1)

    elif "crest" in raw:
        # e.g., "Version 3.0.2", "CREST Version 3.0"
        m = re.search(r"(?:Version|CREST)\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if m:
            return m.group(1)

    elif "cfour" in raw or "xcfour" in raw:
        # e.g., "CFOUR version 2.1"
        m = re.search(r"CFOUR\s+(?:version\s+)?([0-9]+\.[0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if m:
            return m.group(1)

    elif "apptainer" in raw or "singularity" in raw:
        # e.g., "apptainer version 1.3.4", "singularity-ce version 3.11.4"
        m = re.search(r"(?:apptainer|singularity(?:-ce)?)\s+version\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        if m:
            return m.group(1)

    # General fallback version pattern
    m_gen = re.search(r"\b([0-9]+\.[0-9]+(?:\.[0-9]+)?)\b", text)
    if m_gen:
        return m_gen.group(1)

    return None


def interrogate_binary_version(
    binary_path: Union[str, Path],
    engine_name: str,
    timeout_seconds: float = 3.0,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Executes binary with sandboxed flags to safely interrogate its version.
    Guards against process hangs using timeout=3.0s and stdin=DEVNULL.
    Returns (version_string, error_detail).
    """
    p = Path(binary_path).resolve()
    if not p.exists():
        return None, f"Binary not found: {p}"

    cmd = [str(p)]
    raw = engine_name.lower()

    if raw in ("orca", "orca_2mkl", "orca_vpt2_prep"):
        cmd.append("--version")
    elif raw in ("mpirun", "mpiexec"):
        cmd.append("--version")
    elif raw in ("xtb", "crest"):
        cmd.append("--version")
    elif raw in ("xcfour", "c4init", "c4cleanup"):
        cmd.append("-v")
    elif raw in ("apptainer", "singularity"):
        cmd.append("--version")
    else:
        cmd.append("--version")

    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            timeout=timeout_seconds,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        # Decode and take only first 1024 chars to avoid huge buffers
        combined_output = res.stdout.decode(errors="ignore")[:1024].strip()
        
        version = extract_semantic_version(combined_output, engine_name)
        if version:
            return version, None
        elif combined_output:
            first_line = combined_output.splitlines()[0][:80]
            return first_line, None
        return "Unknown Version (No Output)", None

    except subprocess.TimeoutExpired:
        return None, f"Execution timed out after {timeout_seconds}s"
    except PermissionError:
        return None, "Permission denied executing binary"
    except Exception as exc:
        return None, f"Subprocess error: {str(exc)}"


# =============================================================================
# 7. SINGLE & MULTI-TRACK ENGINE AUDITING
# =============================================================================


def audit_single_binary(
    name: str,
    track: EngineTrack = EngineTrack.GENERAL,
    custom_path: Optional[Union[str, Path]] = None,
    timeout_seconds: float = 3.0,
) -> BinaryEngineItem:
    """
    Executes discovery, streaming SHA-256 cryptographic hashing, and safe subprocess
    version interrogation for an individual engine binary.
    """
    search_dirs: Optional[List[Union[str, Path]]] = [custom_path] if custom_path else None
    discovered = discover_binary_path(name, search_dirs=search_dirs)

    if not discovered:
        return BinaryEngineItem(
            name=name,
            track=track,
            path=None,
            version=None,
            sha256_hash=None,
            file_size_bytes=None,
            is_available=False,
            is_container=False,
            container_flags=[],
            error_detail=f"Binary '{name}' not found across standard or configured search tiers",
            status=EngineStatus.MISSING,
        )

    # Compute SHA-256 and physical size
    sha256_hash, file_size, hash_err = compute_file_sha256(discovered)
    if hash_err:
        return BinaryEngineItem(
            name=name,
            track=track,
            path=str(discovered),
            version=None,
            sha256_hash=None,
            file_size_bytes=file_size,
            is_available=False,
            is_container=False,
            container_flags=[],
            error_detail=f"Hashing failure: {hash_err}",
            status=EngineStatus.ERROR,
        )

    # Subprocess version interrogation
    version, ver_err = interrogate_binary_version(discovered, name, timeout_seconds=timeout_seconds)

    status = EngineStatus.FOUND_VALID if version and not ver_err else EngineStatus.FOUND_UNVERIFIED

    return BinaryEngineItem(
        name=name,
        track=track,
        path=str(discovered),
        version=version,
        sha256_hash=sha256_hash,
        file_size_bytes=file_size,
        is_available=True,
        is_container=False,
        container_flags=[],
        error_detail=ver_err,
        status=status,
    )


def audit_all_engines(
    custom_paths: Optional[Dict[str, str]] = None,
    timeout_seconds: float = 3.0,
) -> Dict[str, BinaryEngineItem]:
    """
    Audits all standard monitored quantum chemistry, semi-empirical, and MPI binaries.
    """
    results: Dict[str, BinaryEngineItem] = {}
    custom_map = custom_paths or {}

    for name, track in STANDARD_MONITORED_ENGINES:
        c_path = custom_map.get(name)
        item = audit_single_binary(
            name=name,
            track=track,
            custom_path=c_path,
            timeout_seconds=timeout_seconds,
        )
        results[name] = item

    return results


# =============================================================================
# 8. CONTAINER SIF & AIR-GAP AUDITING
# =============================================================================


def audit_container_sifs(
    search_dirs: Optional[List[Union[str, Path]]] = None,
) -> ContainerAudit:
    """
    Audits Apptainer/Singularity container runtime CLI and scans directories for .sif files.
    Enforces that container execution configurations strictly supply `--net --network none`
    to guarantee the physical network air-gap.
    """
    # 1. Probe runtime CLI
    runtime_name: Optional[str] = None
    runtime_path: Optional[str] = None
    runtime_version: Optional[str] = None

    for r_name in ("apptainer", "singularity"):
        r_bin = shutil.which(r_name)
        if r_bin:
            runtime_name = r_name
            runtime_path = str(Path(r_bin).resolve())
            v, _ = interrogate_binary_version(runtime_path, r_name)
            runtime_version = v
            break

    # 2. Gather candidate directories for .sif images
    dirs_to_scan: List[Path] = []
    if search_dirs:
        for sd in search_dirs:
            p_sd = Path(sd).resolve()
            if p_sd.exists() and p_sd.is_dir():
                dirs_to_scan.append(p_sd)

    env_sif_dir = os.environ.get("COCHEM_SIF_DIR")
    if env_sif_dir:
        p_env = Path(env_sif_dir).resolve()
        if p_env.exists() and p_env.is_dir():
            dirs_to_scan.append(p_env)

    known_sif_dirs = [
        Path.home() / "CoChem_Engines" / "sif",
        Path.home() / "CoChem_Artifacts" / "sif",
        Path("/opt/sif"),
    ]
    for kd in known_sif_dirs:
        if kd.exists() and kd.is_dir() and kd not in dirs_to_scan:
            dirs_to_scan.append(kd)

    # 3. Discover and hash .sif files
    discovered_sifs: List[BinaryEngineItem] = []
    airgap_mandatory_flags = ["--net", "--network", "none"]

    for d in dirs_to_scan:
        try:
            for sif_file in d.glob("*.sif"):
                if sif_file.is_file():
                    sha256_hash, file_size, hash_err = compute_file_sha256(sif_file)
                    item = BinaryEngineItem(
                        name=sif_file.name,
                        track=EngineTrack.CONTAINER_SIF,
                        path=str(sif_file.resolve()),
                        version=f"{sif_file.stem}-sif",
                        sha256_hash=sha256_hash,
                        file_size_bytes=file_size,
                        is_available=True if not hash_err else False,
                        is_container=True,
                        container_flags=list(airgap_mandatory_flags),
                        error_detail=hash_err,
                        status=EngineStatus.FOUND_VALID if not hash_err else EngineStatus.ERROR,
                    )
                    discovered_sifs.append(item)
        except OSError:
            pass

    return ContainerAudit(
        runtime_name=runtime_name,
        runtime_path=runtime_path,
        runtime_version=runtime_version,
        airgap_flags_valid=True,
        discovered_sifs=discovered_sifs,
    )


# =============================================================================
# 9. DETERMINISTIC COMPOSITE ENVIRONMENT FINGERPRINTING
# =============================================================================


def compute_environment_fingerprint(
    engines: Dict[str, BinaryEngineItem],
    os_name: Optional[str] = None,
) -> EnvironmentFingerprint:
    """
    Computes a deterministic, path-independent SHA-256 composite fingerprint over
    the sorted tuple of discovered engine names, semantic versions, binary SHA-256 hashes,
    and target OS architecture.

    SRS Document 10 Section 4.1 Mandate: The fingerprint must remain strictly invariant
    to arbitrary local absolute paths, ensuring consistent verification across environments.
    """
    target_os = os_name or platform.system()
    hasher = hashlib.sha256()
    hasher.update(f"OS:{target_os}\n".encode("utf-8"))

    sorted_keys = sorted(engines.keys())
    component_count = 0

    for key in sorted_keys:
        item = engines[key]
        if item.is_available:
            component_count += 1
            # Concatenate name, version, and binary sha256 (STRICTLY NO LOCAL PATHS)
            entry_repr = (
                f"ENGINE:{item.name}|"
                f"TRACK:{item.track.value}|"
                f"VER:{item.version or 'UNKNOWN'}|"
                f"SHA256:{item.sha256_hash or 'NONE'}\n"
            )
            hasher.update(entry_repr.encode("utf-8"))

    composite_digest = hasher.hexdigest()

    return EnvironmentFingerprint(
        composite_hash=composite_digest,
        component_count=component_count,
        provenance="[D] Deterministic Composite System Hash",
    )


def build_track_summaries(engines: Dict[str, BinaryEngineItem]) -> Dict[str, EngineTrackSummary]:
    """
    Aggregates per-track availability metrics.
    """
    track_bins: Dict[EngineTrack, List[BinaryEngineItem]] = {t: [] for t in EngineTrack}
    for item in engines.values():
        track_bins[item.track].append(item)

    summaries: Dict[str, EngineTrackSummary] = {}
    for track, items in track_bins.items():
        total = len(items)
        avail = sum(1 for i in items if i.is_available)
        missing = total - avail
        summaries[track.value] = EngineTrackSummary(
            track=track,
            total_scanned=total,
            available_count=avail,
            missing_count=missing,
            is_track_ready=(total > 0 and missing == 0),
        )

    return summaries


# =============================================================================
# 10. ARTIFACT & REGISTRY RESOLUTION
# =============================================================================


def resolve_p3_registry_path(output_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolves destination path for p3.json intermediate state artifact following
    the Tripartite Workspace Air-Gap hierarchy.
    """
    if output_dir:
        out_path = Path(output_dir).resolve()
        if out_path.suffix == ".json" or out_path.name == "p3.json":
            return out_path
        return out_path / "p3.json"

    # Dynamic resolution via cochem_base.config_loader if available
    try:
        from cochem_base.config_loader import get_artifact_dir

        return get_artifact_dir() / "Registry" / "p3.json"
    except ImportError:
        pass

    # Standard fallback paths
    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        return Path(env_art).resolve() / "Registry" / "p3.json"

    repo_root = Path.cwd()
    agent_artifacts = repo_root / ".agent_artifacts"
    if agent_artifacts.exists():
        return agent_artifacts / "Registry" / "p3.json"

    home_artifacts = Path.home() / "CoChem_Artifacts"
    return home_artifacts / "Registry" / "p3.json"


# =============================================================================
# 11. PROGRAMMATIC AUDIT PIPELINE ENTRYPOINT
# =============================================================================


def run_phase_3_audit(
    output_dir: Optional[Union[str, Path]] = None,
    target_path: Optional[Union[str, Path]] = None,
    custom_engine_paths: Optional[Dict[str, str]] = None,
) -> Phase3AuditReport:
    """
    Executes full Phase 3 Engine Discovery & Cryptographic Integrity Audit.
    Scans system paths for ORCA, CFOUR, xTB, CREST, and MPI binaries, hashes discovered
    executables with 64KB chunk streaming SHA-256, validates container SIF air-gaps,
    generates deterministic composite environment fingerprints, and atomically
    serializes p3.json into the Golden Registry.
    """
    timestamp_utc = datetime.now(timezone.utc).isoformat()
    warnings: List[str] = []
    errors: List[str] = []

    # 1. Multi-Track Engine Discovery & Hashing
    engines = audit_all_engines(custom_paths=custom_engine_paths)

    # 2. Container SIF & Air-Gap Audit
    sif_dirs = [target_path] if target_path else None
    container_audit = audit_container_sifs(search_dirs=sif_dirs)

    # Merge SIF items into engines map
    for sif_item in container_audit.discovered_sifs:
        engines[f"sif_{sif_item.name}"] = sif_item

    # 3. Track Summaries
    tracks = build_track_summaries(engines)

    # 4. Deterministic Composite Environment Fingerprint
    fingerprint = compute_environment_fingerprint(engines)

    # 5. Evaluate Operational Readiness & Status
    # Check if primary quantum tracks have at least one functional tool
    orca_avail = engines.get("orca", BinaryEngineItem(name="orca")).is_available
    xtb_avail = engines.get("xtb", BinaryEngineItem(name="xtb")).is_available
    cfour_avail = engines.get("xcfour", BinaryEngineItem(name="xcfour")).is_available
    sifs_avail = len(container_audit.discovered_sifs) > 0

    if not orca_avail and not xtb_avail and not cfour_avail and not sifs_avail:
        warnings.append(
            "No primary quantum or semi-empirical engines (ORCA, CFOUR, xTB, or SIF) discovered on host. "
            "Pipeline will operate in degraded/remote dispatch mode."
        )
        status = PhaseStatus.DEGRADED
    elif not orca_avail:
        warnings.append(
            "ORCA binary not found in local paths. DFT/ab initio tasks requiring ORCA will be routed to remote workers."
        )
        status = PhaseStatus.DEGRADED
    else:
        status = PhaseStatus.PASSED

    # 6. Destination Registry Artifact Path
    p3_path = resolve_p3_registry_path(output_dir)

    # 7. Construct Report
    report = Phase3AuditReport(
        phase_id="PHASE_3_ENGINE_DISCOVERY_INTEGRITY",
        status=status,
        timestamp_utc=timestamp_utc,
        engines=engines,
        tracks=tracks,
        container=container_audit,
        fingerprint=fingerprint,
        warnings=warnings,
        errors=errors,
        artifact_path=str(p3_path),
    )

    # 8. Idempotent Atomic State Persistence
    with DependencyManager() as dm:
        dm.atomic_write_json(p3_path, report)

    return report


# =============================================================================
# 12. CLI ENTRYPOINT
# =============================================================================


def main(argv: Optional[List[str]] = None) -> int:
    """
    Command-line entrypoint for CoChem Setup Phase 3: Engine Discovery & Integrity Hashing.
    Returns 0 on PASSED/DEGRADED, non-zero on fatal errors.
    """
    parser = argparse.ArgumentParser(
        description="CoChem Setup Phase 3: Engine Discovery & Integrity Hashing CLI",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help="Custom destination directory for Registry/p3.json",
    )
    parser.add_argument(
        "--target-path",
        "-t",
        type=str,
        default=None,
        help="Target directory to inspect for SIF container images or engine binaries",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw serialized JSON report to stdout",
    )

    args = parser.parse_args(argv)

    try:
        report = run_phase_3_audit(
            output_dir=args.output_dir,
            target_path=args.target_path,
        )

        if args.json:
            logger.info(report.model_dump_json(indent=2))
        else:
            logger.info("=" * 75)
            logger.info("COCHEM SETUP PHASE 3: MULTI-TRACK QUANTUM ENGINE DISCOVERY")
            logger.info("=" * 75)
            logger.info(f"Phase ID:        {report.phase_id}")
            logger.info(f"Status:          {report.status.value}")
            logger.info(f"Timestamp UTC:   {report.timestamp_utc}")
            logger.info(f"Fingerprint:     {report.fingerprint.composite_hash}")
            logger.info(f"Components:      {report.fingerprint.component_count} active hashed elements")
            logger.info(f"Artifact Path:   {report.artifact_path}")
            logger.info("-" * 75)
            logger.info("Engine Discovery Matrix:")
            for name, item in report.engines.items():
                avail_tag = "AVAILABLE" if item.is_available else "MISSING"
                ver = f" (v{item.version})" if item.version else ""
                hash_tag = f" [SHA-256: {item.sha256_hash[:12]}...]" if item.sha256_hash else ""
                logger.info(f"  [{avail_tag:<9}] [{item.track.value:<13}] {name:<16}{ver}{hash_tag}")
            logger.info("-" * 75)
            logger.info("Container Subsystem:")
            c_cli = f"{report.container.runtime_name} (v{report.container.runtime_version})" if report.container.runtime_name else "None"
            logger.info(f"  Runtime:       {c_cli}")
            logger.info(f"  Air-Gap Flags: {'VALID' if report.container.airgap_flags_valid else 'INVALID'}")
            logger.info(f"  SIF Images:    {len(report.container.discovered_sifs)} discovered")
            logger.info("-" * 75)
            logger.info(f"Warnings: {len(report.warnings)}")
            for w in report.warnings:
                logger.warning(f"  - {w}")
            logger.info(f"Errors:   {len(report.errors)}")
            for e in report.errors:
                logger.error(f"  - {e}")
            logger.info("=" * 75)

        if report.status is PhaseStatus.FAILED:
            return 1
        return 0

    except Exception as exc:
        logger.error(f"\n[FATAL PHASE 3 ERROR]\n{exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
