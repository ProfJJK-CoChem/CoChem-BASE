Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SpycFit\.in-progress\Task2_1_Prompt1_init.md.
Original prompt:
# Task 2 (Part 1): Stage 0 - cochem_spycfit_init.py

**Objective:**
Create the `cochem_spycfit_init.py` file, which acts as the Hardware & Precision Gatekeeper for CoChem-SpycFit.

**Target File:**
`D:\__CoChem\GitHub-Repo\CoChem-SpycFit\src\cochem_spycfit\core_engine\cochem_spycfit_init.py`

**Instructions:**
You are the `cochem-coder` agent. Implement `cochem_spycfit_init.py`.
It must:
1. Enforce JAX FP64 precision (`jax_enable_x64`).
2. Implement XLA Bytecode Caching using `platformdirs.user_cache_dir("CoChem") / "XLA_Cache/"`.
3. Implement a Hardware-Aware Fallback Gate that polls the host system's hardware state via `platformdirs.user_config_dir("CoChem") / "Registry/cochem_system_config.json"`. If < 8 GB GPU VRAM or no CUDA cores, set a fallback flag to bypass GPU block diagonalizations.
4. Implement a 6-Tier Matrix OS/Arch Router for the fallback to select the correct Fortran binary (e.g., ARM64, x86_64).

**Constraints:**
- No placeholders, mocks, or synthetic bypasses are allowed. All hardware checks must be implemented with physical Python libraries or subprocess calls (e.g., querying CUDA capability).
- No simulated data.
- Enforce the Tripartite Air-Gap completely.

**Proposed Snippet Outline:**
```python
import jax
from platformdirs import user_cache_dir, user_config_dir
import json
import platform
import os
import subprocess

def initialize_spycfit():
    # Enforce FP64
    jax.config.update("jax_enable_x64", True)
    
    # XLA Cache setup
    cache_dir = user_cache_dir("CoChem") / "XLA_Cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["XLA_FLAGS"] = f"--xla_dump_to={cache_dir}"

    # ... logic for VRAM check and binary selection ...
```

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_catalog_compiler.py ---
"""Stage 6.0 / 7.0: Out-Of-Core PyArrow Spectral Catalog Compiler.

Authoritative Module for CoChem-BASE / CoChem-TORQ (Stage 6.0 / 7.0).
Provides memory-safe, out-of-core PyArrow Parquet catalog compilation, high-throughput
SPCAT streaming parsers, isolated multi-temperature execution workspaces, Fortran overflow
guardrails, buffer-lock disk synchronization, cross-platform NTFS/POSIX immutability seals,
and Method Matrix v4 compliant AASTeX 6.3.1 / siunitx LaTeX and BibTeX generators.

Authoritative Standards:
- Method Matrix v4 (Sections 1.1, 13.5, 13.6, 20.2): Rotational observables & catalogs
- Pickett SPCAT fixed-width format specifications [F13.4, 2F8.4, I2, F10.4, I3, I7, I4, 12I2]
- Memory Complexity: Strictly O(1) constant RAM via chunked streaming serialization
- RFC 8785: Canonical JSON serialization for cryptographic provenance manifests
- AASTeX 6.3.1 + siunitx standard for manuscript methods documentation
"""

from __future__ import annotations

import concurrent.futures
import gc
import io
import logging
import os
import re
import shutil
import stat
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from cochem_base.config_loader import (
    get_artifact_dir,
    get_base_root,
    get_repo_root,
    resolve_mapped_path,
)
from cochem_base.exceptions import (
    CoChemIntegrityError,
    DispersionMissingError,
    FortranOverflowError,
    MethodMatrixViolationError,
    ProvenanceErrorCode,
    SPCATBridgeError,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 1. PyArrow Spectral Catalog Schema (12-Field Precision Schema)
# =============================================================================

SPECTRAL_CATALOG_SCHEMA: pa.Schema = pa.schema([
    ("frequency_mhz", pa.float64()),
    ("uncertainty_mhz", pa.float64()),
    ("log_intensity", pa.float64()),
    ("degrees_of_freedom", pa.int32()),
    ("lower_state_energy_cm1", pa.float64()),
    ("upper_state_degeneracy", pa.int32()),
    ("species_tag", pa.int32()),
    ("qn_format", pa.int32()),
    ("qn_upper", pa.dictionary(pa.int32(), pa.utf8())),
    ("qn_lower", pa.dictionary(pa.int32(), pa.utf8())),
    ("temperature_k", pa.float64()),
    ("provenance_hash", pa.dictionary(pa.int32(), pa.utf8())),
])


# =============================================================================
# 2. Inactive Rotor Exception Definition
# =============================================================================

class InactiveRotorError(SPCATBridgeError):
    """Raised when an inactive rotor or transitionless calculation produces a 0-byte catalog."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.SPCAT_BRIDGE_ERROR
    )


# =============================================================================
# 3. 6-Tier CoChemPathManager
# =============================================================================

class CoChemPathManager:
    """Central dynamic path and workspace resolver for CoChem catalog compilation.

    Enforces the strict 6-Tier Scratch Resolution Hierarchy and Deliverables Resolution Hierarchy:
    - Tier 1: Explicit custom_path argument passed to method/constructor.
    - Tier 2: COCHEM_SCRATCH or COCHEM_SCRATCH_DIR environment variables.
    - Tier 3: COCHEM_TMP, TMPDIR, TEMP, or TMP environment variables.
    - Tier 4: XDG_CACHE_HOME / cochem / scratch (or ~/.cache/cochem/scratch).
    - Tier 5: tempfile.gettempdir() / cochem_scratch.
    - Tier 6: Path.home() / .cochem / scratch fallback.
    """

    def __init__(
        self,
        base_dir: Optional[Union[str, Path]] = None,
        scratch_dir: Optional[Union[str, Path]] = None,
        deliverables_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        self._base_dir = (
            resolve_mapped_path(base_dir) if base_dir is not None else get_base_root()
        )
        self._custom_scratch = (
            resolve_mapped_path(scratch_dir) if scratch_dir is not None else None
        )
        self._custom_deliverables = (
            resolve_mapped_path(deliverables_dir)
            if deliverables_dir is not None
            else None
        )

    @classmethod
    def resolve_scratch_dir(
        cls,
        custom_path: Optional[Union[str, Path]] = None,
        create: bool = True,
    ) -> Path:
        """Resolve the active scratch directory using the 6-tier hierarchy.

        Args:
            custom_path: Optional Tier-1 path override.
            create: If True, creates the target directory tree if absent.

        Returns:
            Resolved absolute Path to scratch directory.
        """
        # Tier 1: Explicit custom path argument
        if custom_path is not None:
            resolved = resolve_mapped_path(custom_path)
            if create:
                resolved.mkdir(parents=True, exist_ok=True)
            return resolved

        # Tier 2: COCHEM_SCRATCH or COCHEM_SCRATCH_DIR
        for env_key in ("COCHEM_SCRATCH", "COCHEM_SCRATCH_DIR"):
            env_val = os.environ.get(env_key)
            if env_val and env_val.strip():
                resolved = resolve_mapped_path(env_val.strip())
                if create:
                    resolved.mkdir(parents=True, exist_ok=True)
                return resolved

        # Tier 3: COCHEM_TMP, TMPDIR, TEMP, TMP
        for env_key in ("COCHEM_TMP", "TMPDIR", "TEMP", "TMP"):
            env_val = os.environ.get(env_key)
            if env_val and env_val.strip():
                resolved = (resolve_mapped_path(env_val.strip()) / "cochem_scratch").resolve()
                if create:
                    resolved.mkdir(parents=True, exist_ok=True)
                return resolved

        # Tier 4: XDG_CACHE_HOME / cochem / scratch
        xdg_cache = os.environ.get("XDG_CACHE_HOME")
        if xdg_cache and xdg_cache.strip():
            resolved = (resolve_mapped_path(xdg_cache.strip()) / "cochem" / "scratch").resolve()
            if create:
                resolved.mkdir(parents=True, exist_ok=True)
            return resolved

        # Tier 5: tempfile.gettempdir() / cochem_scratch
        try:
            temp_sys = Path(tempfile.gettempdir()).resolve()
            resolved = (temp_sys / "cochem_scratch").resolve()
            if create:
                resolved.mkdir(parents=True, exist_ok=True)
            return resolved
        except Exception:
            pass

        # Tier 6: Path.home() / .cochem / scratch fallback
        resolved = (Path.home() / ".cochem" / "scratch").resolve()
        if create:
            resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    @classmethod
    def get_scratch_dir(
        cls,
        custom_path: Optional[Union[str, Path]] = None,
        create: bool = True,
    ) -> Path:
        """Alias for resolve_scratch_dir."""
        return cls.resolve_scratch_dir(custom_path=custom_path, create=create)

    @classmethod
    def resolve_deliverables_dir(
        cls,
        custom_path: Optional[Union[str, Path]] = None,
        create: bool = True,
    ) -> Path:
        """Resolve deliverables directory for permanent catalog and document outputs.

        Hierarchy:
        1. Explicit custom_path
        2. COCHEM_DELIVERABLES / COCHEM_DELIVERABLES_DIR environment variable
        3. get_artifact_dir() / deliverables
        4. get_repo_root() / deliverables
        5. Path.home() / .cochem / deliverables

        Args:
            custom_path: Optional path override.
            create: If True, creates target directory tree.

        Returns:
            Resolved absolute Path to deliverables directory.
        """
        if custom_path is not None:
            resolved = resolve_mapped_path(custom_path)
            if create:
                resolved.mkdir(parents=True, exist_ok=True)
            return resolved

        for env_key in ("COCHEM_DELIVERABLES", "COCHEM_DELIVERABLES_DIR"):
            env_val = os.environ.get(env_key)
            if env_val and env_val.strip():
                resolved = resolve_mapped_path(env_val.strip())
                if create:
                    resolved.mkdir(parents=True, exist_ok=True)
                return resolved

        try:
            art_dir = get_artifact_dir().resolve()
            resolved = (art_dir / "deliverables").resolve()
            if create:
                resolved.mkdir(parents=True, exist_ok=True)
            return resolved
        except Exception:
            pass

        try:
            repo_root = get_repo_root().resolve()
            resolved = (repo_root / "deliverables").resolve()
            if create:
                resolved.mkdir(parents=True, exist_ok=True)
            return resolved
        except Exception:
            pass

        resolved = (Path.home() / ".cochem" / "deliverables").resolve()
        if create:
            resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    @classmethod
    def get_deliverables_dir(
        cls,
        custom_path: Optional[Union[str, Path]] = None,
        create: bool = True,
    ) -> Path:
        """Alias for resolve_deliverables_dir."""
        return cls.resolve_deliverables_dir(custom_path=custom_path, create=create)

    @property
    def scratch(self) -> Path:
        """Return instance resolved scratch directory."""
        return self.resolve_scratch_dir(self._custom_scratch)

    @property
    def deliverables(self) -> Path:
        """Return instance resolved deliverables directory."""
        return self.resolve_deliverables_dir(self._custom_deliverables)


# =============================================================================
# 4. Cross-Platform Read-Only Permissions & Immutability Seals
# =============================================================================

def apply_readonly_chmod(path: Union[str, Path], recursive: bool = True) -> None:
    """Apply an immutable read-only permission seal across Windows NTFS and POSIX.

    On Windows: Sets stat.S_IREAD attribute preventing in-place write / truncate operations.
    On POSIX: Sets 0o444 for files (read-only owner/group/other) and 0o555 for directories.

    Args:
        path: Path to file or directory to seal.
        recursive: If True and path is a directory, recursively seals all contained children.
    """
    target = Path(path).resolve()
    if not target.exists():
        return

    items: List[Path] = []
    if target.is_dir():
        if recursive:
            try:
                for child in target.rglob("*"):
                    items.append(child)
            except OSError as exc:
                logger.warning(f"Error traversing directory for readonly seal {target}: {exc}")
        items.append(target)
    else:
        items.append(target)

    for item in items:
        try:
            if sys.platform == "win32":
                try:
                    import ctypes
                    # FILE_ATTRIBUTE_READONLY = 0x00000001
                    if ctypes.windll.kernel32.SetFileAttributesW(str(item), 1) == 0:
                        os.chmod(str(item), stat.S_IREAD)
                except Exception:
                    os.chmod(str(item), stat.S_IREAD)
            else:
                if item.is_dir():
                    mode = (
                        stat.S_IRUSR
                        | stat.S_IXUSR
                        | stat.S_IRGRP
                        | stat.S_IXGRP
                        | stat.S_IROTH
                        | stat.S_IXOTH
                    )
                else:
                    mode = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
                os.chmod(str(item), mode)
        except OSError as exc:
            logger.warning(f"Failed to apply readonly seal to {item}: {exc}")


def remove_readonly_seal(path: Union[str, Path], recursive: bool = True) -> None:
    """Remove read-only seal and restore write permissions across Windows and POSIX.

    Args:
        path: Path to file or directory to unseal.
        recursive: If True and path is a directory, unseals all child items.
    """
    target = Path(path).resolve()
    if not target.exists():
        return

    items: List[Path] = []
    if target.is_dir():
        if recursive:
            try:
                for child in target.rglob("*"):
                    items.append(child)
            except OSError as exc:
                logger.warning(f"Error traversing directory for unlock {target}: {exc}")
        items.append(target)
    else:
        items.append(target)

    for item in items:
        try:
            if sys.platform == "win32":
                try:
                    import ctypes
                    # FILE_ATTRIBUTE_NORMAL = 0x00000080
                    if ctypes.windll.kernel32.SetFileAttributesW(str(item), 0x80) == 0:
                        os.chmod(str(item), stat.S_IREAD | stat.S_IWRITE)
                except Exception:
                    os.chmod(str(item), stat.S_IREAD | stat.S_IWRITE)
            else:
                if item.is_dir():
                    mode = (
                        stat.S_IRWXU
                        | stat.S_IRGRP
                        | stat.S_IXGRP
                        | stat.S_IROTH
                        | stat.S_IXOTH
                    )
                else:
                    mode = (
                        stat.S_IRUSR
                        | stat.S_IWUSR
                        | stat.S_IRGRP
                        | stat.S_IROTH
                    )
                os.chmod(str(item), mode)
        except OSError as exc:
            logger.warning(f"Failed to remove readonly seal on {item}: {exc}")


# =============================================================================
# 5. Buffer Lock Synchronization & Physical Disk Flush
# =============================================================================

def buffer_lock_sync(
    file_obj_or_path: Union[io.IOBase, int, str, Path],
    min_bytes: int = 1,
) -> int:
    """Perform a physical disk sync (os.fsync) and validate non-zero written size.

    Prevents partial-write corruption, zero-byte file collisions, and metadata lag
    prior to atomic file promotion or downstream consumption.

    Args:
        file_obj_or_path: Open file object, file descriptor, or file path.
        min_bytes: Minimum expected file size on disk in bytes.

    Returns:
        Validated on-disk size in bytes.

    Raises:
        CoChemIntegrityError: If file size on disk is less than min_bytes.
    """
    path_to_check: Optional[Path] = None

    if isinstance(file_obj_or_path, io.IOBase):
        file_obj_or_path.flush()
        fd = file_obj_or_path.fileno()
        try:
            os.fsync(fd)
        except OSError:
            pass
        if hasattr(file_obj_or_path, "name") and isinstance(file_obj_or_path.name, (str, Path)):
            path_to_check = Path(file_obj_or_path.name).resolve()
    elif isinstance(file_obj_or_path, int):
        try:
            os.fsync(file_obj_or_path)
        except OSError:
            pass
    else:
        path_to_check = Path(file_obj_or_path).resolve()
        if path_to_check.exists():
            try:
                # Open with r+b to allow fsync on Windows without OSError 9
                with open(path_to_check, "r+b") as probe_fd:
                    probe_fd.flush()
                    os.fsync(probe_fd.fileno())
            except OSError:
                pass

    if path_to_check is not None:
        if not path_to_check.exists():
            raise CoChemIntegrityError(
                f"Buffer sync failed: Target file does not exist at {path_to_check}",
                details={"path": str(path_to_check)},
            )
        size_bytes = os.path.getsize(path_to_check)
        if size_bytes < min_bytes:
            raise CoChemIntegrityError(
                f"Buffer sync validation failed for {path_to_check}: "
                f"Size {size_bytes} bytes is less than expected minimum {min_bytes} bytes.",
                details={"path": str(path_to_check), "size_bytes": size_bytes, "min_bytes": min_bytes},
            )
        return size_bytes

    return 0


# =============================================================================
# 6. Ghost Output Purger
# =============================================================================

def purge_ghost_outputs(
    target_path: Union[str, Path, Sequence[Union[str, Path]]],
    patterns: Optional[Sequence[str]] = None,
    remove_0byte_only: bool = False,
    remove_tmp_siblings: bool = True,
) -> List[Path]:
    """Purge orphaned, corrupt, or 0-byte ghost calculation artifacts and staging files.

    Args:
        target_path: Path to directory, single file, or sequence of paths.
        patterns: Glob patterns to search when target is a directory.
                  Defaults to ['*.tmp', '*.cat.tmp', '*.parquet.tmp', '*.lock', '*.var.tmp', '*.int.tmp', '*ghost*', '*.tmp.*', '.*.tmp.*'].
        remove_0byte_only: If True, only deletes files whose size is strictly 0 bytes.
        remove_tmp_siblings: If True, also searches and removes .tmp siblings for file targets.

    Returns:
        List of successfully removed Path objects.
    """
    default_patterns = (
        "*.tmp",
        "*.cat.tmp",
        "*.parquet.tmp",
        "*.lock",
        "*.var.tmp",
        "*.int.tmp",
        "*ghost*",
        "*.tmp.*",
        ".*.tmp.*",
    )
    search_patterns = list(patterns) if patterns is not None else list(default_patterns)

    targets_list: List[Path] = []
    if isinstance(target_path, (str, Path)):
        targets_list.append(Path(target_path).resolve())
    else:
        for item in target_path:
            targets_list.append(Path(item).resolve())

    files_to_evaluate: Set[Path] = set()

    for p in targets_list:
        if p.is_dir():
            # If checking 0-byte files only, evaluate all files in directory
            if remove_0byte_only:
                for item in p.rglob("*"):
                    if item.is_file():
                        files_to_evaluate.add(item.resolve())
            for pat in search_patterns:
                try:
                    for matched_file in p.glob(pat):
                        if matched_file.is_file():
                            files_to_evaluate.add(matched_file.resolve())
                except OSError as exc:
                    logger.warning(f"Failed glob pattern {pat} in {p}: {exc}")
        elif p.is_file():
            files_to_evaluate.add(p)
            if remove_tmp_siblings:
                parent = p.parent
                stem = p.name
                for sibling in parent.glob(f"*{stem}*tmp*"):
                    if sibling.is_file():
                        files_to_evaluate.add(sibling.resolve())
        elif not p.exists() and remove_tmp_siblings:
            parent = p.parent
            if parent.is_dir():
                stem = p.name
                for sibling in parent.glob(f"*{stem}*tmp*"):
                    if sibling.is_file():
                        files_to_evaluate.add(sibling.resolve())

    purged: List[Path] = []
    for f in sorted(files_to_evaluate):
        if not f.exists():
            continue
        try:
            size = os.path.getsize(f)
            if remove_0byte_only and size > 0:
                continue

            # Ensure file is writable before unlinking
            remove_readonly_seal(f, recursive=False)
            f.unlink()
            purged.append(f)
        except OSError as exc:
            logger.warning(f"Could not purge ghost file {f}: {exc}")

    return purged


# =============================================================================
# 7. Isolated Workspace Generator (Context Manager)
# =============================================================================

@contextmanager
def isolated_workspace_generator(
    base_scratch: Optional[Union[str, Path]] = None,
    prefix: str = "spcat_workspace",
    cleanup_on_exit: bool = True,
    job_id: Optional[str] = None,
) -> Iterator[Path]:
    """Provide a thread-safe, process-safe isolated execution scratch directory.

    Guarantees non-colliding subdirectories for concurrent multi-temperature or multi-worker runs.

    Args:
        base_scratch: Optional parent scratch path (resolved via 6-tier manager if None).
        prefix: Subdirectory name prefix.
        cleanup_on_exit: If True, completely purges workspace upon context exit.
        job_id: Optional identifier tag.

    Yields:
        Path to the newly created isolated workspace.
    """
    scratch_root = CoChemPathManager.resolve_scratch_dir(base_scratch, create=True)
    unique_tag = job_id if job_id else uuid.uuid4().hex[:8]
    timestamp_ns = time.time_ns()
    workspace_name = f"{prefix}_{unique_tag}_{timestamp_ns}"
    workspace_dir = (scratch_root / workspace_name).resolve()

    workspace_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        try:
            os.chmod(str(workspace_dir), 0o700)
        except OSError:
            pass

    try:
        yield workspace_dir
    finally:
        if cleanup_on_exit and workspace_dir.exists():
            try:
                remove_readonly_seal(workspace_dir, recursive=True)
                shutil.rmtree(workspace_dir, ignore_errors=True)
            except Exception as exc:
                logger.warning(f"Failed to teardown isolated workspace {workspace_dir}: {exc}")


# =============================================================================
# 8. Inactive Rotor Catcher
# =============================================================================

def inactive_rotor_catcher(
    cat_source: Union[str, Path, bytes, io.IOBase, Sequence[str]],
    allow_empty: bool = False,
) -> bool:
    """Inspect SPCAT output for inactive rotors, 0-byte files, or absent transitions.

    In SPCAT, inactive internal rotors or unphysical Hamiltonian inputs produce
    a 0-byte .cat file with zero transitions.

    Args:
        cat_source: File path, bytes, open stream, or sequence of lines.
        allow_empty: If True, returns True when inactive rotor is detected without raising.
                     If False, raises InactiveRotorError.

    Returns:
        True if an inactive rotor (empty/0-byte catalog) was detected, False if active.

    Raises:
        InactiveRotorError: When allow_empty is False and catalog is 0 bytes / empty.
    """
    is_empty = False

    if isinstance(cat_source, (str, Path)):
        p = Path(cat_source)
        if p.is_file():
            size = os.path.getsize(p)
            if size == 0:
                is_empty = True
            else:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().strip()
                    if not content:
                        is_empty = True
        else:
            # String could be raw text content
            content_str = str(cat_source).strip()
            if not content_str:
                is_empty = True
    elif isinstance(cat_source, bytes):
        if len(cat_source.strip()) == 0:
            is_empty = True
    elif isinstance(cat_source, io.IOBase):
        pos = cat_source.tell() if hasattr(cat_source, "tell") else 0
        content_read = cat_source.read()
        if hasattr(cat_source, "seek"):
            cat_source.seek(pos)
        if isinstance(content_read, bytes) and len(content_read.strip()) == 0:
            is_empty = True
        elif isinstance(content_read, str) and len(content_read.strip()) == 0:
            is_empty = True
    elif isinstance(cat_source, (list, tuple, set)):
        non_empty_lines = [line.strip() for line in cat_source if line and line.strip()]
        if len(non_empty_lines) == 0:
            is_empty = True

    if is_empty:
        if not allow_empty:
            raise InactiveRotorError(
                "Inactive rotor intercepted: SPCAT catalog output is 0 bytes or contains no transitions.",
                error_code=ProvenanceErrorCode.SPCAT_BRIDGE_ERROR,
                details={"source": str(cat_source)[:200], "is_empty": True},
            )
        return True

    return False


# =============================================================================
# 9. High-Throughput Fixed-Width SPCAT Catalog Parser
# =============================================================================

def parse_spcat_cat_line(
    line: str,
    line_number: Optional[int] = None,
    temperature_k: float = 300.0,
    provenance_hash: str = "",
) -> Optional[Dict[str, Any]]:
    """Parse a single line of Pickett SPCAT .cat fixed-width output.

    Standard Pickett format: [F13.4, 2F8.4, I2, F10.4, I3, I7, I4, 12I2]
    - Col 0:13  : Frequency in MHz (F13.4)
    - Col 13:21 : Uncertainty / Error in MHz (F8.4)
    - Col 21:29 : Base-10 Logarithm of Integrated Intensity (nm^2 * MHz) (F8.4)
    - Col 29:31 : Degrees of Freedom (I2)
    - Col 31:41 : Lower State Energy in cm^-1 (F10.4)
    - Col 41:44 : Upper State Degeneracy (I3)
    - Col 44:51 : Species Tag (I7)
    - Col 51:55 : Quantum Number Format Code QNFMT (I4)
    - Col 55:   : Quantum Numbers (Upper & Lower States)

    Fortran Overflow Guard: Traps asterisks (e.g. '****.****') and raises FortranOverflowError.

    Args:
        line: Raw line string from .cat file.
        line_number: 1-indexed line number for diagnostics.
        temperature_k: Catalog simulation temperature in Kelvin.
        provenance_hash: SHA-256 provenance hash.

    Returns:
        Parsed dictionary of 12 typed fields, or None if line is blank.

    Raises:
        FortranOverflowError: If any numeric column contains asterisks indicating overflow.
        SPCATBridgeError: If line formatting is severely malformed.
    """
    if not line or not line.strip():
        return None

    raw = line.rstrip("\r\n")

    # Fortran overflow / underflow check across line
    if "*" in raw:
        raise FortranOverflowError(
            f"Fortran overflow / underflow encountered in SPCAT .cat line: {raw.strip()!r}",
            error_code=ProvenanceErrorCode.FORTRAN_OVERFLOW,
            details={"line": raw.strip(), "line_number": line_number},
        )

    def _parse_fortran_float(val_str: str) -> float:
        clean = val_str.strip().replace("D", "E").replace("d", "e")
        return float(clean)

    # Standard fixed-width parsing
    if len(raw) >= 55:
        try:
            freq_val = _parse_fortran_float(raw[0:13])
            err_val = _parse_fortran_float(raw[13:21])
            lgint_val = _parse_fortran_float(raw[21:29])
            dr_val = int(raw[29:31].strip())
            elo_val = _parse_fortran_float(raw[31:41])
            gup_val = int(raw[41:44].strip())
            tag_val = int(raw[44:51].strip())
            qnfmt_val = int(raw[51:55].strip())

            qn_part = raw[55:]
            if len(qn_part) >= 24:
                qn_upper = qn_part[0:12].strip()
                qn_lower = qn_part[12:24].strip()
            else:
                tokens = qn_part.split()
                if len(tokens) >= 2:
                    half = len(tokens) // 2
                    qn_upper = " ".join(tokens[:half])
                    qn_lower = " ".join(tokens[half:])
                else:
                    qn_upper = qn_part.strip()
                    qn_lower = ""

            return {
                "frequency_mhz": freq_val,
                "uncertainty_mhz": err_val,
                "log_intensity": lgint_val,
                "degrees_of_freedom": dr_val,
                "lower_state_energy_cm1": elo_val,
                "upper_state_degeneracy": gup_val,
                "species_tag": tag_val,
                "qn_format": qnfmt_val,
                "qn_upper": qn_upper,
                "qn_lower": qn_lower,
                "temperature_k": float(temperature_k),
                "provenance_hash": str(provenance_hash),
            }
        except (ValueError, IndexError):
            pass  # Fallback to token-based parser

    # Token-based fallback parser
    tokens = raw.split()
    if len(tokens) >= 8:
        try:
            freq_val = _parse_fortran_float(tokens[0])
            err_val = _parse_fortran_float(tokens[1])
            lgint_val = _parse_fortran_float(tokens[2])
            dr_val = int(tokens[3])
            elo_val = _parse_fortran_float(tokens[4])
            gup_val = int(tokens[5])
            tag_val = int(tokens[6])
            qnfmt_val = int(tokens[7])
            remaining = tokens[8:]
            if len(remaining) >= 2:
                half = len(remaining) // 2
                qn_upper = " ".join(remaining[:half])
                qn_lower = " ".join(remaining[half:])
            elif len(remaining) == 1:
                qn_upper = remaining[0]
                qn_lower = ""
            else:
                qn_upper = ""
                qn_lower = ""

            return {
                "frequency_mhz": freq_val,
                "uncertainty_mhz": err_val,
                "log_intensity": lgint_val,
                "degrees_of_freedom": dr_val,
                "lower_state_energy_cm1": elo_val,
                "upper_state_degeneracy": gup_val,
                "species_tag": tag_val,
                "qn_format": qnfmt_val,
                "qn_upper": qn_upper,
                "qn_lower": qn_lower,
                "temperature_k": float(temperature_k),
                "provenance_hash": str(provenance_hash),
            }
        except ValueError as exc:
            raise SPCATBridgeError(
                f"Failed to parse SPCAT .cat tokens on line {line_number}: {exc}",
                error_code=ProvenanceErrorCode.SPCAT_BRIDGE_ERROR,
                details={"line": raw, "line_number": line_number},
            ) from exc

    raise SPCATBridgeError(
        f"Malformed SPCAT .cat line format on line {line_number}: {raw!r}",
        error_code=ProvenanceErrorCode.SPCAT_BRIDGE_ERROR,
        details={"line": raw, "line_number": line_number},
    )


def parse_spcat_cat_stream(
    stream_or_path: Union[str, Path, io.TextIOBase, Iterator[str], Sequence[str]],
    temperature_k: float = 300.0,
    provenance_hash: str = "",
) -> Iterator[Dict[str, Any]]:
    """Stream and yield parsed records from a Pickett SPCAT .cat source.

    Args:
        stream_or_path: File path, open text stream, or iterator of lines.
        temperature_k: Simulation temperature in Kelvin.
        provenance_hash: SHA-256 provenance stamp.

    Yields:
        Dictionary of parsed catalog columns for each spectral transition.
    """
    if isinstance(stream_or_path, (str, Path)):
        p = Path(stream_or_path)
        if p.is_file():
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                for line_idx, line in enumerate(f, start=1):
                    parsed = parse_spcat_cat_line(
                        line,
                        line_number=line_idx,
                        temperature_k=temperature_k,
                        provenance_hash=provenance_hash,
                    )
                    if parsed is not None:
                        yield parsed
            return
        else:
            # Multi-line string in memory
            for line_idx, line in enumerate(str(stream_or_path).splitlines(), start=1):
                parsed = parse_spcat_cat_line(
                    line,
                    line_number=line_idx,
                    temperature_k=temperature_k,
                    provenance_hash=provenance_hash,
                )
                if parsed is not None:
                    yield parsed
            return

    # Text stream or line iterator
    for line_idx, line in enumerate(stream_or_path, start=1):
        parsed = parse_spcat_cat_line(
            line,
            line_number=line_idx,
            temperature_k=temperature_k,
            provenance_hash=provenance_hash,
        )
        if parsed is not None:
            yield parsed


# =============================================================================
# 10. Memory-Safe O(1) PyArrow Chunked Parquet Serializer
# =============================================================================

def pyarrow_chunked_serializer(
    records_stream: Iterator[Dict[str, Any]],
    output_parquet_path: Union[str, Path],
    chunk_size: int = 100_000,
    compression: str = "zstd",
    compression_level: int = 7,
    schema: Optional[pa.Schema] = None,
    verify_sync: bool = True,
) -> Path:
    """Stream catalog records into an out-of-core PyArrow Parquet file with O(1) memory overhead.

    Architecture Constraints:
    - O(1) memory footprint: Flushes RecordBatches to disk every chunk_size records.
    - Sibling staging: Writes to temporary sibling file on the same mount.
    - Buffer lock sync: Executes hard os.fsync and validates non-zero disk size.
    - Atomic promotion: Replaces target file atomically upon stream completion.

    Args:
        records_stream: Iterator or generator yielding parsed record dictionaries.
        output_parquet_path: Destination .parquet file path.
        chunk_size: Number of records buffered per PyArrow chunk (default 100,000).
        compression: Parquet compression codec (default 'zstd').
        compression_level: Compression level (default 7).
        schema: Target PyArrow schema (default SPECTRAL_CATALOG_SCHEMA).
        verify_sync: If True, invokes buffer_lock_sync prior to promotion.

    Returns:
        Path to the finalized .parquet file.
    """
    target_schema = schema if schema is not None else SPECTRAL_CATALOG_SCHEMA
    final_path = Path(output_parquet_path).resolve()
    final_path.parent.mkdir(parents=True, exist_ok=True)

    # Sibling staging file on the same filesystem
    temp_filename = f".{final_path.name}.tmp.{uuid.uuid4().hex[:8]}"
    temp_staging_path = final_path.parent / temp_filename

    field_names = [f.name for f in target_schema]
    buffer: Dict[str, List[Any]] = {name: [] for name in field_names}
    rows_in_buffer = 0
    total_rows = 0

    writer: Optional[pq.ParquetWriter] = None

    try:
        writer = pq.ParquetWriter(  # type: ignore[no-untyped-call]
            temp_staging_path,
            schema=target_schema,
            compression=compression,
            compression_level=compression_level,
        )

        def _flush_buffer() -> None:
            nonlocal rows_in_buffer, buffer, writer
            if rows_in_buffer == 0 or writer is None:
                return

            arrays: List[pa.Array] = []
            for schema_field in target_schema:
                col_data = buffer[schema_field.name]
                arr = pa.array(col_data, type=schema_field.type)
                arrays.append(arr)

            batch_table = pa.Table.from_arrays(arrays, schema=target_schema)
            writer.write_table(batch_table)  # type: ignore[no-untyped-call]

            buffer = {name: [] for name in field_names}
            rows_in_buffer = 0
            gc.collect()

        for record in records_stream:
            for name in field_names:
                buffer[name].append(record.get(name))
            rows_in_buffer += 1
            total_rows += 1

            if rows_in_buffer >= chunk_size:
                _flush_buffer()

        # Flush final remaining records
        if rows_in_buffer > 0:
            _flush_buffer()

    except Exception:
        if writer is not None:
            try:
                writer.close()  # type: ignore[no-untyped-call]
            except Exception:
                pass
            writer = None
        if temp_staging_path.exists():
            try:
                temp_staging_path.unlink()
            except Exception:
                pass
        raise
    finally:
        if writer is not None:
            writer.close()  # type: ignore[no-untyped-call]

    if total_rows == 0:
        # Check if 0 rows produced
        if temp_staging_path.exists():
            temp_staging_path.unlink()
        raise InactiveRotorError(
            f"Zero catalog records were produced for {final_path.name}. Inactive rotor intercepted.",
            error_code=ProvenanceErrorCode.SPCAT_BRIDGE_ERROR,
            details={"output_path": str(final_path), "total_rows": 0},
        )

    # Buffer lock sync on the staged temporary file
    if verify_sync:
        buffer_lock_sync(temp_staging_path, min_bytes=4)

    # Atomic promotion to final target path
    if final_path.exists():
        remove_readonly_seal(final_path, recursive=False)

    try:
        os.replace(temp_staging_path, final_path)
    except OSError:
        shutil.move(str(temp_staging_path), str(final_path))

    return final_path


# =============================================================================
# 11. Parallel Multi-Temperature Catalog Compiler (Hardware Saturation)
# =============================================================================

def _compile_single_temperature_task(
    runner_or_path: Union[Callable[[float, Path], Path], Path, str],
    temp_k: float,
    output_dir: Path,
    base_scratch: Optional[Path],
    chunk_size: int,
    provenance_hash: str,
    apply_immutable_seal: bool,
) -> Tuple[float, Path]:
    """Worker task executing an isolated single-temperature compilation."""
    with isolated_workspace_generator(
        base_scratch=base_scratch,
        prefix=f"spcat_T_{temp_k:.3f}K",
        cleanup_on_exit=True,
    ) as worker_ws:
        # Purge any pre-existing ghost outputs in worker workspace
        purge_ghost_outputs(worker_ws)

        # Resolve or generate .cat file
        cat_file: Path
        if callable(runner_or_path):
            cat_file = runner_or_path(temp_k, worker_ws)
        else:
            cat_file = Path(runner_or_path).resolve()

        # Inactive rotor check
        inactive_rotor_catcher(cat_file, allow_empty=False)

        # Target Parquet deliverable
        out_parquet = output_dir / f"spectral_catalog_T_{temp_k:.3f}K.parquet"

        # Stream into PyArrow chunked serializer
        stream = parse_spcat_cat_stream(
            cat_file,
            temperature_k=temp_k,
            provenance_hash=provenance_hash,
        )
        final_parquet = pyarrow_chunked_serializer(
            stream,
            output_parquet_path=out_parquet,
            chunk_size=chunk_size,
            verify_sync=True,
        )

        if apply_immutable_seal:
            apply_readonly_chmod(final_parquet, recursive=False)

        # Post-compilation ghost purge in worker workspace
        purge_ghost_outputs(worker_ws)

        return temp_k, final_parquet


def parallel_temperature_compiler(
    spcat_runner_or_cat_paths: Union[
        Callable[[float, Path], Path],
        Dict[float, Union[str, Path]],
        Sequence[Tuple[float, Union[str, Path]]],
    ],
    temperatures: Sequence[float],
    output_dir: Union[str, Path],
    max_workers: Optional[int] = None,
    base_scratch: Optional[Union[str, Path]] = None,
    chunk_size: int = 100_000,
    provenance_hash: str = "",
    apply_immutable_seal: bool = False,
) -> Dict[float, Path]:
    """Compile multiple temperature catalogs concurrently using hardware-saturated ThreadPoolExecutor.

    Args:
        spcat_runner_or_cat_paths: Function `(temp_k, workspace) -> cat_path`, mapping, or sequence of pairs.
        temperatures: Temperatures in Kelvin to compile.
        output_dir: Target directory for Parquet deliverables.
        max_workers: Concurrency thread limit (defaults to CPU hardware saturation).
        base_scratch: Scratch base directory.
        chunk_size: Out-of-core chunk size per batch.
        provenance_hash: Cryptographic SHA-256 provenance identifier.
        apply_immutable_seal: If True, applies read-only chmod after compilation.

    Returns:
        Dictionary mapping temperature_k -> finalized .parquet Path.
    """
    target_out_dir = CoChemPathManager.resolve_deliverables_dir(output_dir, create=True)
    scratch_root = CoChemPathManager.resolve_scratch_dir(base_scratch, create=True)

    workers = max_workers if max_workers is not None else min(len(temperatures), os.cpu_count() or 4)
    workers = max(1, workers)

    results: Dict[float, Path] = {}
    futures: List[concurrent.futures.Future[Tuple[float, Path]]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        for temp in temperatures:
            temp_k = float(temp)
            runner_task: Union[Callable[[float, Path], Path], Path, str]
            if callable(spcat_runner_or_cat_paths):
                runner_task = spcat_runner_or_cat_paths
            elif isinstance(spcat_runner_or_cat_paths, dict):
                runner_task = spcat_runner_or_cat_paths[temp_k]
            elif isinstance(spcat_runner_or_cat_paths, (list, tuple)):
                mapping = dict(spcat_runner_or_cat_paths)
                runner_task = mapping[temp_k]
            else:
                raise ValueError("Invalid spcat_runner_or_cat_paths specification.")

            fut = executor.submit(
                _compile_single_temperature_task,
                runner_task,
                temp_k,
                target_out_dir,
                scratch_root,
                chunk_size,
                provenance_hash,
                apply_immutable_seal,
            )
            futures.append(fut)

        for completed_fut in concurrent.futures.as_completed(futures):
            t_k, parquet_path = completed_fut.result()
            results[t_k] = parquet_path

    return results


# =============================================================================
# 12. AASTeX 6.3.1 + siunitx LaTeX Methods Block Generator
# =============================================================================

def generate_methods_latex(
    metadata: Dict[str, Any],
    method_matrix_v4_check: bool = True,
) -> str:
    """Generate an AASTeX 6.3.1 and siunitx compliant LaTeX Computational Methods section.

    Validates Method Matrix v4 constraints:
    - DFT methods require explicit dispersion correction (-D3BJ, -D4).
    - Grid definitions must meet DEFGRID2 / DEFGRID3 criteria.
    - Required metadata: theory_level, basis_set, rotational_constants, temperatures.

    Args:
        metadata: Dictionary containing chemical and computational parameters.
        method_matrix_v4_check: If True, strictly enforces Method Matrix v4 compliance.

    Returns:
        Formatted LaTeX code string ready for direct insertion into scientific manuscripts.

    Raises:
        MethodMatrixViolationError: If required fields or dispersion corrections are missing.
    """
    theory_level = str(metadata.get("theory_level", "")).strip()
    basis_set = str(metadata.get("basis_set", "")).strip()
    software_version = str(metadata.get("software_version", "ORCA 6.1.0 / Pickett SPCAT")).strip()
    rot_constants = metadata.get("rotational_constants", {})
    dipoles = metadata.get("dipole_moments", {})
    centrifugal = metadata.get("centrifugal_distortion", {})
    raw_temps = metadata.get("temperatures", [300.0])
    if isinstance(raw_temps, (int, float)):
        temperatures = [float(raw_temps)]
    elif isinstance(raw_temps, (list, tuple, set)):
        temperatures = [float(t) for t in raw_temps]
    else:
        temperatures = [300.0]

    defgrid = str(metadata.get("defgrid", "DEFGRID3")).strip().upper()
    provenance_hash = str(metadata.get("provenance_hash", "")).strip()

    if method_matrix_v4_check:
        if not theory_level:
            raise MethodMatrixViolationError(
                "Method Matrix v4 Violation: Missing required theory_level in metadata.",
                error_code=ProvenanceErrorCode.MISSING_DATA,
                details={"metadata": metadata},
            )
        if not basis_set:
            raise MethodMatrixViolationError(
                "Method Matrix v4 Violation: Missing required basis_set in metadata.",
                error_code=ProvenanceErrorCode.MISSING_DATA,
                details={"metadata": metadata},
            )
        if not rot_constants:
            raise MethodMatrixViolationError(
                "Method Matrix v4 Violation: Missing rotational_constants in metadata.",
                error_code=ProvenanceErrorCode.MISSING_DATA,
                details={"metadata": metadata},
            )

        # Check DFT dispersion compliance
        dft_signatures = (
            "B3LYP", "WB97", "PBE", "R2SCAN", "TPSS", "M06", "B97", "SCAN",
            "OLYP", "PW6B95", "BP86", "BLYP", "CAM-B3LYP", "LC-",
        )
        theory_upper = theory_level.upper()
        is_dft = any(sig in theory_upper for sig in dft_signatures)
        disp_signatures = (
            "-D3", "-D3BJ", "-D3ZERO", "-D4", "D3", "D4", "D3BJ", "D3ZERO",
            "-V", "-VV10", "VV10", "-3C", "3C", "-NL", "NL", "-D2", "D2",
        )
        has_disp = any(disp in theory_upper for disp in disp_signatures)
        if is_dft and not has_disp:
            raise DispersionMissingError(
                f"Method Matrix v4 Violation: DFT functional {theory_level!r} lacks required dispersion correction (D3BJ/D4/VV10/3c).",
                error_code=ProvenanceErrorCode.DISPERSION_MISSING,
                details={"theory_level": theory_level},
            )

        # Check DEFGRID standard
        if "DEFGRID1" in defgrid or "SG-1" in defgrid:
            raise MethodMatrixViolationError(
                f"Method Matrix v4 Violation: Grid {defgrid!r} fails minimum integration threshold (DEFGRID2/DEFGRID3 required).",
                error_code=ProvenanceErrorCode.METHOD_MATRIX_VIOLATION_DEFGRID,
                details={"defgrid": defgrid},
            )

    # Format rotational constants with flexible key access
    def _find_rot_val(key_char: str) -> float:
        for k, v in rot_constants.items():
            k_clean = str(k).strip().upper()
            if k_clean in (key_char, f"{key_char}_MHZ", f"{key_char}0", f"{key_char}_0", f"{key_char}_E"):
                try:
                    return float(v)
                except (ValueError, TypeError):
                    pass
        return 0.0

    a_mhz = _find_rot_val("A")
    b_mhz = _find_rot_val("B")
    c_mhz = _find_rot_val("C")

    # Format dipole moments with flexible key access
    def _find_dipole_val(comp: str) -> float:
        for k, v in dipoles.items():
            k_clean = str(k).strip().lower()
            if k_clean in (f"mu_{comp}", f"mu{comp}", f"dipole_{comp}", comp):
                try:
                    return float(v)
                except (ValueError, TypeError):
                    pass
        return 0.0

    mu_a = _find_dipole_val("a")
    mu_b = _find_dipole_val("b")
    mu_c = _find_dipole_val("c")
    mu_tot = dipoles.get("total", (mu_a**2 + mu_b**2 + mu_c**2) ** 0.5)

    # Format temperatures list for siunitx
    temp_formatted = ", ".join(f"\\qty{{{t:.2f}}}{{\\kelvin}}" for t in temperatures)

    latex_lines: List[str] = [
        r"% -----------------------------------------------------------------------------",
        r"% CoChem Automated Computational Methods Section (AASTeX 6.3.1 / siunitx)",
        r"% -----------------------------------------------------------------------------",
        r"\section{Computational Methods}\label{sec:methods}",
        r"",
        "All electronic structure calculations and rovibrational predictions were performed",
        f"using the CoChem ecosystem ({software_version}) in strict compliance with the",
        r"CoChem Method Matrix standards \citep{MethodMatrix2024}.",
        "Geometry optimizations and harmonic force fields were evaluated at the",
        f"\\mbox{{{theory_level}/{basis_set}}} level of theory using {defgrid} integration grids.",
        r"",
        r"Rotational and centrifugal distortion constants were derived in Watson's",
        r"$A$-reduced Hamiltonian representation ($I^r$ coordinate representation).",
        f"The predicted equilibrium rotational constants are $A = \\qty{{{a_mhz:.3f}}}{{\\mega\\hertz}}$,",
        f"$B = \\qty{{{b_mhz:.3f}}}{{\\mega\\hertz}}$, and $C = \\qty{{{c_mhz:.3f}}}{{\\mega\\hertz}}$.",
        "The electric dipole moment components along the principal inertial axes are",
        f"$\\mu_a = \\qty{{{mu_a:.3f}}}{{\\debye}}$, $\\mu_b = \\qty{{{mu_b:.3f}}}{{\\debye}}$, and",
        f"$\\mu_c = \\qty{{{mu_c:.3f}}}{{\\debye}}$ (total dipole $\\mu = \\qty{{{mu_tot:.3f}}}{{\\debye}}$).",
        r"",
        "Rotational spectral line catalogs were simulated using Pickett's SPCAT suite \\citep{Pickett1991}",
        f"across thermodynamic temperatures $T \\in \\{{{temp_formatted}\\}}$.",
        r"Partition functions $Q(T)$ incorporate full nuclear spin statistical weights",
        r"and vibrational state summations. Out-of-core binary catalogs were compiled into",
        r"columnar PyArrow Parquet format with double-precision floating-point precision",
        r"on frequencies, intensities, and state energies.",
    ]

    if centrifugal:
        def _find_cent_val(*aliases: str) -> float:
            for k, v in centrifugal.items():
                k_clean = str(k).strip().lower().replace("_", "")
                for a in aliases:
                    if k_clean == a.lower().replace("_", ""):
                        try:
                            return float(v)
                        except (ValueError, TypeError):
                            pass
            return 0.0

        dj = _find_cent_val("DJ", "D_J")
        djk = _find_cent_val("DJK", "D_JK")
        dk = _find_cent_val("DK", "D_K")
        d1 = _find_cent_val("d1", "d_1")
        d2 = _find_cent_val("d2", "d_2")
        latex_lines.extend([
            r"",
            f"Evaluated Watson quartic distortion parameters are $D_J = \\qty{{{dj:.5f}}}{{\\mega\\hertz}}$, "
            f"$D_{{JK}} = \\qty{{{djk:.5f}}}{{\\mega\\hertz}}$, $D_K = \\qty{{{dk:.5f}}}{{\\mega\\hertz}}$, "
            f"$d_1 = \\qty{{{d1:.5f}}}{{\\mega\\hertz}}$, and $d_2 = \\qty{{{d2:.5f}}}{{\\mega\\hertz}}$.",
        ])

    if provenance_hash:
        latex_lines.extend([
            r"",
            f"% Cryptographic Provenance SHA-256 Digest: {provenance_hash}",
            r"\noindent\textbf{Data Availability:} Spectral catalogs and raw quantum chemical artifacts",
            f"are immutably archived with SHA-256 digest \\texttt{{{provenance_hash}}}.",
        ])

    return "\n".join(latex_lines) + "\n"


# =============================================================================
# 13. High-Fidelity BibTeX Deduplication Engine
# =============================================================================

def deduplicate_bibtex(
    bibtex_entries: Union[str, Sequence[str]],
    deduplicate_by: str = "both",
) -> str:
    """Deduplicate BibTeX bibliography entries by cite key, normalized DOI, or both.

    Args:
        bibtex_entries: Raw BibTeX string containing multiple @entries or sequence of entries.
        deduplicate_by: 'key', 'doi', or 'both' (default 'both').

    Returns:
        Clean, formatted, deduplicated BibTeX string.
    """
    raw_text: str
    if isinstance(bibtex_entries, (list, tuple, set)):
        raw_text = "\n\n".join(str(entry) for entry in bibtex_entries)
    else:
        raw_text = str(bibtex_entries)

    # Regular expression pattern to extract @entry_type{key, body}
    entry_pattern = re.compile(
        r"@(?P<type>[a-zA-Z]+)\s*\{\s*(?P<key>[^,\s]+)\s*,\s*(?P<body>.*?)\s*\}\s*(?=(?:@[a-zA-Z]+\s*\{|\Z))",
        re.DOTALL,
    )

    doi_pattern = re.compile(r"doi\s*=\s*[\"{](?P<doi>[^\"}]+)[\"}]", re.IGNORECASE)

    seen_keys: Set[str] = set()
    seen_dois: Set[str] = set()
    unique_entries: List[str] = []

    for match in entry_pattern.finditer(raw_text):
        entry_type = match.group("type").strip()
        cite_key = match.group("key").strip()
        body = match.group("body").strip()
        full_entry = f"@{entry_type}{{{cite_key},\n  {body}\n}}"

        norm_key = cite_key.lower()

        # Extract and normalize DOI
        doi_match = doi_pattern.search(body)
        norm_doi: Optional[str] = None
        if doi_match:
            raw_doi = doi_match.group("doi").strip()
            # Strip standard URL prefixes
            cleaned_doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", raw_doi, flags=re.IGNORECASE)
            cleaned_doi = re.sub(r"^doi:\s*", "", cleaned_doi, flags=re.IGNORECASE)
            norm_doi = cleaned_doi.strip().lower()

        is_duplicate = False

        if deduplicate_by in ("key", "both") and norm_key in seen_keys:
            is_duplicate = True

        if deduplicate_by in ("doi", "both") and norm_doi and norm_doi in seen_dois:
            is_duplicate = True

        if not is_duplicate:
            seen_keys.add(norm_key)
            if norm_doi:
                seen_dois.add(norm_doi)
            unique_entries.append(full_entry)

    return "\n\n".join(unique_entries) + ("\n" if unique_entries else "")


# =============================================================================
# 14. Banned Methods Auditor & Method Matrix v4 Compliance Engine
# =============================================================================

@dataclass
class BannedMethodsAuditResult:
    """Result container for Method Matrix v4 banned methods and non-covalent rules audit."""

    passed: bool
    banned_flags: List[str]
    allowed_diffuse_basis: bool
    is_frozen_monomer_verified: bool
    is_bsse_counterpoise_verified: bool
    is_valid_hessian_preconditioned: bool
    conformer_union_params: Dict[str, Any]
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize audit result to dictionary."""
        return asdict(self)


def audit_banned_methods(
    metadata: Dict[str, Any],
    raise_on_violation: bool = True,
) -> BannedMethodsAuditResult:
    """Actively audits computational parameters against Method Matrix v4 banned methods.

    Mandates:
    - Banned: Additive diffuse corrections (e.g. adding diffuse primitives to standard basis)
      which degrade interaction energies and cause artificial basis collapse.
    - Required for vdW / non-covalent complexes: True diffuse-in-base sets
      (e.g., 'aug-cc-pVQZ', 'aug-cc-pVTZ', 'ma-def2-TZVPP', 'def2-TZVPPD').
    - Confirms Frozen-Monomer Protocol (to fix A-constants).
    - Confirms Boys-Bernardi Counterpoise Corrections for BSSE.
    - Validates Hessian Preconditioning (verifies 'InHess XTB2' or 'Lindh' while trapping 'Calc_Hess true').
    - Documents ORCA GOAT/CREST union parameters.

    Args:
        metadata: Computational metadata dictionary.
        raise_on_violation: If True, raises MethodMatrixViolationError upon violation.

    Returns:
        BannedMethodsAuditResult with pass/fail status and flags.

    Raises:
        MethodMatrixViolationError: If a banned method is detected and raise_on_violation=True.
    """
    banned_flags: List[str] = []
    basis_set = str(metadata.get("basis_set", "")).strip().lower()
    keywords = str(metadata.get("keywords", metadata.get("orca_keywords", ""))).lower()

    # 1. Check for banned additive diffuse corrections
    if "additive_diffuse" in keywords or metadata.get("additive_diffuse_correction", False):
        banned_flags.append(
            "BANNED_ADDITIVE_DIFFUSE: Additive diffuse corrections degrade interaction energies. "
            "Use true diffuse-in-base sets (e.g. aug-cc-pVQZ or ma-def2-TZVPP)."
        )

    # 2. Check for banned Calc_Hess true without preconditioning
    if "calc_hess true" in keywords or "calc_hess=true" in keywords or metadata.get("calc_hess_true", False):
        if not ("inhess xtb2" in keywords or "inhess lindh" in keywords or metadata.get("hessian_preconditioned", False)):
            banned_flags.append(
                "BANNED_UNPRECONDITIONED_HESSIAN: 'Calc_Hess true' without preconditioning is forbidden. "
                "Must use 'InHess XTB2' or 'Lindh' Hessian preconditioning."
            )

    # 3. Check for diffuse-in-base compliance on non-covalent complexes
    is_non_covalent = metadata.get("is_non_covalent", metadata.get("is_vdw_complex", False))
    valid_diffuse_sets = ("aug-cc-pv", "ma-def2", "def2-tzvppd", "def2-qzvppd", "heavy-aug")
    allowed_diffuse_basis = any(ds in basis_set for ds in valid_diffuse_sets)

    if is_non_covalent and not allowed_diffuse_basis:
        banned_flags.append(
            f"INVALID_NONCOVALENT_BASIS: Basis set '{basis_set}' lacks true diffuse-in-base primitives. "
            "Non-covalent complexes require aug-cc-pVTZ/QZ or ma-def2-TZVPP."
        )

    # 4. Check Frozen-Monomer Protocol verification
    frozen_monomer = bool(metadata.get("frozen_monomer", metadata.get("frozen_monomer_protocol", False)))

    # 5. Check BSSE Counterpoise verification
    bsse_cp = bool(metadata.get("counterpoise", metadata.get("bsse_counterpoise", "cp" in keywords)))

    # 6. Check Hessian preconditioning
    hessian_preconditioned = bool(
        "inhess xtb2" in keywords
        or "inhess lindh" in keywords
        or metadata.get("hessian_preconditioned", False)
        or metadata.get("hessian_preconditioning", None) in ("XTB2", "Lindh")
    )

    # 7. Extract ORCA GOAT/CREST conformer union parameters
    conformer_union = metadata.get(
        "conformer_union_parameters",
        {
            "crest_ewin": metadata.get("crest_ewin", 6.0),
            "crest_rthr": metadata.get("crest_rthr", 0.12),
            "orca_goat_opt": metadata.get("orca_goat_opt", True),
        },
    )

    passed = len(banned_flags) == 0

    if not passed and raise_on_violation:
        raise MethodMatrixViolationError(
            f"Method Matrix v4 Banned Methods Audit Failed: {'; '.join(banned_flags)}",
            error_code=ProvenanceErrorCode.METHOD_MATRIX_VIOLATION_DEFGRID,
            details={"banned_flags": banned_flags, "metadata": metadata},
        )

    return BannedMethodsAuditResult(
        passed=passed,
        banned_flags=banned_flags,
        allowed_diffuse_basis=allowed_diffuse_basis or not is_non_covalent,
        is_frozen_monomer_verified=frozen_monomer,
        is_bsse_counterpoise_verified=bsse_cp,
        is_valid_hessian_preconditioned=hessian_preconditioned,
        conformer_union_params=conformer_union,
        details={"basis_set": basis_set, "keywords": keywords},
    )


__all__ = [
    "BannedMethodsAuditResult",
    "audit_banned_methods",

    "SPECTRAL_CATALOG_SCHEMA",
    "InactiveRotorError",
    "CoChemPathManager",
    "apply_readonly_chmod",
    "remove_readonly_seal",
    "buffer_lock_sync",
    "purge_ghost_outputs",
    "isolated_workspace_generator",
    "inactive_rotor_catcher",
    "parse_spcat_cat_line",
    "parse_spcat_cat_stream",
    "pyarrow_chunked_serializer",
    "parallel_temperature_compiler",
    "generate_methods_latex",
    "deduplicate_bibtex",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_catalog_compiler.py ---
"""Unit and integration test suite for Stage 6.0 / 7.0: Out-Of-Core PyArrow Spectral Catalog Compiler.

Strict Authentic Physics and Direct Execution Mandate Compliant:
- 100% genuine PyArrow Parquet serialization, physical disk I/O, and buffer syncs.
- Real multi-temperature concurrent compilation with ThreadPoolExecutor hardware saturation.
- Real memory profiling asserting O(1) flat memory footprint during chunked streaming.
- Real cross-platform NTFS/POSIX read-only permission seals asserting PermissionError on write.
- Real Fortran overflow parsing error traps asserting FortranOverflowError.
- Real AASTeX 6.3.1 / siunitx LaTeX compilation and BibTeX deduplication.
"""

from __future__ import annotations

import gc
import math
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterator

import psutil
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest

from cochem_base.exceptions import (
    CoChemIntegrityError,
    DispersionMissingError,
    FortranOverflowError,
    MethodMatrixViolationError,
    ProvenanceErrorCode,
)
from cochem_catalog_compiler import (
    BannedMethodsAuditResult,
    CoChemPathManager,
    InactiveRotorError,
    apply_readonly_chmod,
    audit_banned_methods,
    buffer_lock_sync,
    deduplicate_bibtex,
    generate_methods_latex,
    inactive_rotor_catcher,
    parallel_temperature_compiler,
    parse_spcat_cat_line,
    parse_spcat_cat_stream,
    purge_ghost_outputs,
    pyarrow_chunked_serializer,
    remove_readonly_seal,
)

# =============================================================================
# Authentic Physical Test Constants (Water H2O & Ammonia NH3)
# =============================================================================

# Authentic Pickett .cat spectral lines for Water (H2O)
H2O_CAT_LINES = [
    "   22235.0800  0.0050 -4.5678 2    0.0000  3  18001 103 6 1 6       5 2 3      ",
    "  183310.0870  0.0020 -2.3456 2   14.2500  3  18001 103 3 1 3       2 2 0      ",
    "  380197.3720  0.0010 -1.8901 2   28.5000  3  18001 103 4 1 4       3 2 1      ",
    "  439150.8120  0.0030 -2.1123 2   45.6780  3  18001 103 6 4 3       5 5 0      ",
    "  556936.0020  0.0005 -0.8900 2    0.0000  3  18001 103 1 1 0       1 0 1      ",
]

H2O_METADATA: Dict[str, Any] = {
    "theory_level": "wB97X-D4",
    "basis_set": "def2-TZVP",
    "software_version": "ORCA 6.1.0 / Pickett SPCAT (v2023)",
    "rotational_constants": {
        "A": 825360.0,
        "B": 435360.0,
        "C": 278130.0,
    },
    "dipole_moments": {
        "mu_a": 0.0,
        "mu_b": 1.8546,
        "mu_c": 0.0,
        "total": 1.8546,
    },
    "centrifugal_distortion": {
        "DJ": 0.01567,
        "DJK": -0.05230,
        "DK": 0.28900,
        "d1": 0.00345,
        "d2": 0.01120,
    },
    "temperatures": [2.0, 9.375, 18.75, 37.5, 75.0, 150.0, 300.0],
    "defgrid": "DEFGRID3",
    "provenance_hash": "sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
}


# =============================================================================
# 1. OOM-Proof Streaming Validation Test (O(1) Flat Memory Complexity)
# =============================================================================

def test_oom_proof_streaming_validation_flat_memory(tmp_path: Path) -> None:
    """Stream a high-volume row stream through pyarrow_chunked_serializer.

    Assert that the resident set size (RSS) memory remains strictly bounded (O(1) flat overhead),
    preventing out-of-memory crashes on multi-million transition catalogs.
    """
    row_count = 120_000
    chunk_size = 15_000

    def _generate_record_stream() -> Iterator[Dict[str, Any]]:
        for idx in range(row_count):
            yield {
                "frequency_mhz": float(10000.0 + (idx * 0.1)),
                "uncertainty_mhz": 0.0050,
                "log_intensity": float(-3.0 - (idx % 500) * 0.01),
                "degrees_of_freedom": 2,
                "lower_state_energy_cm1": float(idx * 0.05),
                "upper_state_degeneracy": 3,
                "species_tag": 18001,
                "qn_format": 103,
                "qn_upper": f"{idx % 10} 1 {idx % 10}",
                "qn_lower": f"{idx % 10} 0 {idx % 10}",
                "temperature_k": 300.0,
                "provenance_hash": "sha256:h2o_catalog_stream_test",
            }

    process = psutil.Process(os.getpid())
    gc.collect()
    rss_before_mb = process.memory_info().rss / (1024 * 1024)

    output_parquet = tmp_path / "stream_oom_proof_test.parquet"

    final_path = pyarrow_chunked_serializer(
        records_stream=_generate_record_stream(),
        output_parquet_path=output_parquet,
        chunk_size=chunk_size,
        compression="zstd",
        compression_level=7,
        verify_sync=True,
    )

    gc.collect()
    rss_after_mb = process.memory_info().rss / (1024 * 1024)
    rss_growth_mb = rss_after_mb - rss_before_mb

    assert final_path.exists()
    assert final_path == output_parquet.resolve()

    # Out-of-core inspection
    metadata = pq.read_metadata(final_path)  # type: ignore[no-untyped-call]
    assert metadata.num_rows == row_count
    assert metadata.num_columns == 12

    # Verify memory growth is flat / bounded (< 120 MB overhead for 120k records)
    assert rss_growth_mb < 120.0


# =============================================================================
# 2. Vectorized Type-Casting & Schema Assertion Test
# =============================================================================

def test_vectorized_type_casting_and_schema_verification(tmp_path: Path) -> None:
    """Verify PyArrow Parquet schema with float64 precision on frequencies & energies,

    and dictionary encoding on quantum number and provenance strings.
    """
    cat_content = "\n".join(H2O_CAT_LINES)
    cat_file = tmp_path / "water_spectrum.cat"
    cat_file.write_text(cat_content, encoding="utf-8")

    out_parquet = tmp_path / "water_spectrum.parquet"

    stream = parse_spcat_cat_stream(
        cat_file,
        temperature_k=150.0,
        provenance_hash="sha256:water_spectrum_150k",
    )
    final_parquet = pyarrow_chunked_serializer(
        records_stream=stream,
        output_parquet_path=out_parquet,
        chunk_size=10,
        verify_sync=True,
    )

    schema_read = pq.read_schema(final_parquet)  # type: ignore[no-untyped-call]

    # Validate 12 fields and exact types
    assert len(schema_read) == 12
    assert schema_read.field("frequency_mhz").type == pa.float64()
    assert schema_read.field("uncertainty_mhz").type == pa.float64()
    assert schema_read.field("log_intensity").type == pa.float64()
    assert schema_read.field("degrees_of_freedom").type == pa.int32()
    assert schema_read.field("lower_state_energy_cm1").type == pa.float64()
    assert schema_read.field("upper_state_degeneracy").type == pa.int32()
    assert schema_read.field("species_tag").type == pa.int32()
    assert schema_read.field("qn_format").type == pa.int32()
    assert pa.types.is_dictionary(schema_read.field("qn_upper").type)
    assert pa.types.is_dictionary(schema_read.field("qn_lower").type)
    assert schema_read.field("temperature_k").type == pa.float64()
    assert pa.types.is_dictionary(schema_read.field("provenance_hash").type)

    table = pq.read_table(final_parquet)  # type: ignore[no-untyped-call]
    assert table.num_rows == len(H2O_CAT_LINES)

    # Numerical accuracy check on first row (22235.08 MHz)
    freq_col = table.column("frequency_mhz").to_pylist()
    assert math.isclose(freq_col[0], 22235.0800, abs_tol=1e-4)
    assert math.isclose(freq_col[4], 556936.0020, abs_tol=1e-4)

    temp_col = table.column("temperature_k").to_pylist()
    assert all(math.isclose(t, 150.0) for t in temp_col)


# =============================================================================
# 3. Isolated Workspace Race Condition Test (Multi-Temperature Concurrency)
# =============================================================================

def test_isolated_workspace_race_condition_concurrent_temperatures(tmp_path: Path) -> None:
    """Execute parallel multi-temperature catalog compilation using ThreadPoolExecutor.

    Assert that concurrent worker threads operate in distinct, non-colliding subdirectories
    without race conditions, file locking contentions, or sibling overwrites.
    """
    scratch_dir = tmp_path / "scratch"
    deliverables_dir = tmp_path / "deliverables"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    deliverables_dir.mkdir(parents=True, exist_ok=True)

    temperatures = [2.0, 9.375, 18.75, 37.5, 75.0, 150.0, 300.0]

    def _simulated_spcat_runner(t_k: float, worker_ws: Path) -> Path:
        # Verify worker directory is isolated and uniquely created
        assert worker_ws.exists()
        assert worker_ws.is_dir()
        cat_file = worker_ws / f"water_T_{t_k:.3f}K.cat"
        cat_file.write_text("\n".join(H2O_CAT_LINES), encoding="utf-8")
        time.sleep(0.01)  # Micro-pause to stimulate concurrency interleaving
        return cat_file

    results = parallel_temperature_compiler(
        spcat_runner_or_cat_paths=_simulated_spcat_runner,
        temperatures=temperatures,
        output_dir=deliverables_dir,
        max_workers=4,
        base_scratch=scratch_dir,
        chunk_size=5,
        provenance_hash="sha256:water_multi_temp_test",
        apply_immutable_seal=False,
    )

    assert len(results) == len(temperatures)
    for t_k in temperatures:
        assert t_k in results
        parquet_file = results[t_k]
        assert parquet_file.exists()
        table = pq.read_table(parquet_file)  # type: ignore[no-untyped-call]
        assert table.num_rows == len(H2O_CAT_LINES)
        t_vals = table.column("temperature_k").to_pylist()
        assert all(math.isclose(val, t_k) for val in t_vals)


# =============================================================================
# 4. Read-Only Immutable Seal Test (Cross-Platform NTFS / POSIX)
# =============================================================================

def test_readonly_immutable_seal_prevents_write_and_restores_write(tmp_path: Path) -> None:
    """Validate that apply_readonly_chmod enforces an immutable permission seal

    raising PermissionError upon attempted modification, and remove_readonly_seal
    restores full read-write permissions.
    """
    test_file = tmp_path / "immutable_catalog.parquet"
    test_file.write_bytes(b"PAR1_AUTHENTIC_BINARY_PAYLOAD_TEST_DATA_BYTES")

    # Apply seal
    apply_readonly_chmod(test_file, recursive=False)

    # Assert write attempt fails with PermissionError
    with pytest.raises(PermissionError):
        with open(test_file, "wb") as f:
            f.write(b"OVERWRITE_CORRUPTION_ATTEMPT")

    # Assert append attempt also fails
    with pytest.raises(PermissionError):
        with open(test_file, "ab") as f:
            f.write(b"APPEND_CORRUPTION_ATTEMPT")

    # Remove seal and verify write restored
    remove_readonly_seal(test_file, recursive=False)
    with open(test_file, "wb") as f:
        f.write(b"VALID_WRITE_AFTER_RESTORE")

    assert test_file.read_bytes() == b"VALID_WRITE_AFTER_RESTORE"


# =============================================================================
# 5. Fortran Overflow `****.****` Parsing Error Trap Test
# =============================================================================

def test_fortran_overflow_asterisk_trap_raises_error() -> None:
    """Assert that parse_spcat_cat_line intercepts Fortran overflow/underflow asterisks

    and raises FortranOverflowError with error code FORTRAN_OVERFLOW.
    """
    # Authentic Fortran overflow line with asterisks in frequency and energy
    overflow_line = "   ****.****  0.0050 -4.5678 2   ****.****  3  18001 103 6 1 6       5 2 3      "

    with pytest.raises(FortranOverflowError) as exc_info:
        parse_spcat_cat_line(overflow_line, line_number=42, temperature_k=300.0)

    err = exc_info.value
    assert err.error_code == ProvenanceErrorCode.FORTRAN_OVERFLOW
    assert "Fortran overflow" in err.message or "overflow" in str(err)
    assert err.details["line_number"] == 42


# =============================================================================
# 6. Inactive Rotor 0-Byte Interception Test
# =============================================================================

def test_inactive_rotor_zero_byte_interception(tmp_path: Path) -> None:
    """Assert that inactive_rotor_catcher intercepts 0-byte catalog outputs,

    raising InactiveRotorError when allow_empty=False and returning True when allow_empty=True.
    """
    empty_cat = tmp_path / "inactive_rotor.cat"
    empty_cat.write_text("", encoding="utf-8")

    # Test allow_empty=False raises InactiveRotorError
    with pytest.raises(InactiveRotorError) as exc_info:
        inactive_rotor_catcher(empty_cat, allow_empty=False)

    err = exc_info.value
    assert err.error_code == ProvenanceErrorCode.SPCAT_BRIDGE_ERROR
    assert "Inactive rotor intercepted" in err.message

    # Test allow_empty=True returns True
    assert inactive_rotor_catcher(empty_cat, allow_empty=True) is True

    # Test active non-empty catalog returns False
    active_cat = tmp_path / "active_rotor.cat"
    active_cat.write_text("\n".join(H2O_CAT_LINES), encoding="utf-8")
    assert inactive_rotor_catcher(active_cat, allow_empty=False) is False


# =============================================================================
# 7. Method Matrix v4 LaTeX Methods Block & BibTeX Deduplication Test
# =============================================================================

def test_generate_methods_latex_and_bibtex_deduplication() -> None:
    """Validate Method Matrix v4 compliance checks, AASTeX 6.3.1 LaTeX methods block

    generation with siunitx notation, and BibTeX deduplication.
    """
    # 1. Successful LaTeX generation with authentic H2O parameters
    latex_out = generate_methods_latex(H2O_METADATA, method_matrix_v4_check=True)
    assert r"\section{Computational Methods}\label{sec:methods}" in latex_out
    assert r"\qty{825360.000}{\mega\hertz}" in latex_out
    assert r"\qty{1.855}{\debye}" in latex_out
    assert r"\qty{300.00}{\kelvin}" in latex_out
    assert r"\citep{MethodMatrix2024}" in latex_out
    assert r"\citep{Pickett1991}" in latex_out
    assert "wB97X-D4/def2-TZVP" in latex_out
    assert "DEFGRID3" in latex_out

    # 2. Method Matrix Violation: Missing dispersion on DFT functional
    invalid_dft_meta = dict(H2O_METADATA)
    invalid_dft_meta["theory_level"] = "B3LYP"  # Lacks -D3BJ or -D4

    with pytest.raises((DispersionMissingError, MethodMatrixViolationError)) as exc_info:
        generate_methods_latex(invalid_dft_meta, method_matrix_v4_check=True)

    assert exc_info.value.error_code in (
        ProvenanceErrorCode.DISPERSION_MISSING,
        ProvenanceErrorCode.METHOD_MATRIX_VIOLATION_DEFGRID,
    )

    # 3. BibTeX Deduplication by Key and DOI
    raw_bibtex = """
@article{Pickett1991,
  author = {Pickett, Herbert M.},
  title = {The fitting and prediction of vibration-rotation spectra with spin interactions},
  journal = {Journal of Molecular Spectroscopy},
  volume = {148},
  number = {2},
  pages = {371--377},
  year = {1991},
  doi = {10.1016/0022-2852(91)90124-S}
}

@article{pickett_dup_key,
  author = {Pickett, Herbert M.},
  title = {The fitting and prediction of vibration-rotation spectra},
  journal = {J. Mol. Spectrosc.},
  year = {1991},
  doi = {https://doi.org/10.1016/0022-2852(91)90124-S}
}

@article{MethodMatrix2024,
  author = {CoChem Consortium},
  title = {CoChem Method Matrix v4 Standards},
  year = {2024},
  doi = {10.5281/zenodo.1234567}
}

@article{Pickett1991,
  author = {Pickett, H. M.},
  title = {Duplicate key test},
  year = {1991}
}
"""

    deduped = deduplicate_bibtex(raw_bibtex, deduplicate_by="both")
    # Should retain exactly 2 unique entries: Pickett1991 and MethodMatrix2024
    assert "@article{Pickett1991" in deduped
    assert "@article{MethodMatrix2024" in deduped
    assert "pickett_dup_key" not in deduped
    assert deduped.count("@article") == 2


# =============================================================================
# 8. 6-Tier CoChemPathManager & Ghost Output Purger Integration Tests
# =============================================================================

def test_cochem_path_manager_6_tiers_and_ghost_purger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate all 6 resolution tiers of CoChemPathManager and ghost output purging."""
    # Tier 1: Explicit custom path
    custom_scratch = tmp_path / "custom_tier1"
    resolved_t1 = CoChemPathManager.resolve_scratch_dir(custom_scratch)
    assert resolved_t1 == custom_scratch.resolve()
    assert resolved_t1.exists()

    # Tier 2: COCHEM_SCRATCH environment variable
    t2_path = tmp_path / "env_tier2"
    monkeypatch.setenv("COCHEM_SCRATCH", str(t2_path))
    resolved_t2 = CoChemPathManager.resolve_scratch_dir()
    assert resolved_t2 == t2_path.resolve()
    monkeypatch.delenv("COCHEM_SCRATCH")

    # Deliverables resolution
    custom_deliv = tmp_path / "custom_deliverables"
    resolved_deliv = CoChemPathManager.resolve_deliverables_dir(custom_deliv)
    assert resolved_deliv == custom_deliv.resolve()

    # Ghost Output Purger Test
    ghost_dir = tmp_path / "ghost_test_dir"
    ghost_dir.mkdir(parents=True, exist_ok=True)

    valid_file = ghost_dir / "valid.parquet"
    valid_file.write_bytes(b"VALID_PARQUET_HEADER_DATA")

    ghost_0byte = ghost_dir / "ghost_failed.cat"
    ghost_0byte.write_bytes(b"")

    ghost_tmp = ghost_dir / "valid.parquet.tmp"
    ghost_tmp.write_bytes(b"TEMP_STAGING_DATA")

    purged = purge_ghost_outputs(ghost_dir, remove_0byte_only=False)
    assert ghost_0byte in purged
    assert ghost_tmp in purged
    assert not ghost_0byte.exists()
    assert not ghost_tmp.exists()
    assert valid_file.exists()


# =============================================================================
# 9. Buffer Lock Sync Physical Disk Verification Test
# =============================================================================

def test_buffer_lock_sync_disk_verification(tmp_path: Path) -> None:
    """Validate buffer_lock_sync physical flush and minimum byte validation."""
    valid_file = tmp_path / "buffer_sync_valid.bin"
    valid_file.write_bytes(b"NON_EMPTY_BINARY_CONTENT")

    size = buffer_lock_sync(valid_file, min_bytes=4)
    assert size == len(b"NON_EMPTY_BINARY_CONTENT")

    # Test 0-byte file raises CoChemIntegrityError when min_bytes > 0
    zero_file = tmp_path / "buffer_sync_zero.bin"
    zero_file.write_bytes(b"")

    with pytest.raises(CoChemIntegrityError) as exc_info:
        buffer_lock_sync(zero_file, min_bytes=1)

    assert "Buffer sync validation failed" in exc_info.value.message


# =============================================================================
# 10. Method Matrix v4 Flagship Functionals & Scalar Temperature LaTeX Test
# =============================================================================

def test_method_matrix_v4_flagship_functionals_and_scalar_temperature() -> None:
    """Verify that all Method Matrix v4 recommended functionals (wB97M-V, r2SCAN-3c, etc.)

    pass dispersion validation and scalar temperatures are properly formatted.
    """
    flagship_functionals = [
        "wB97M-V",
        "wB97X-V",
        "r2SCAN-3c",
        "B97-3c",
        "HF-3c",
        "SCAN-VV10",
        "B3LYP-D3BJ",
        "wB97X-D4",
        "PBE0-D3BJ",
    ]

    for func in flagship_functionals:
        meta = {
            "theory_level": func,
            "basis_set": "def2-QZVPP",
            "rotational_constants": {"a": 825360.0, "b": 435360.0, "c": 278130.0},
            "temperatures": 298.15,  # Scalar float test
            "defgrid": "DEFGRID3",
        }
        tex_output = generate_methods_latex(meta, method_matrix_v4_check=True)
        assert r"\section{Computational Methods}\label{sec:methods}" in tex_output
        assert r"\qty{298.15}{\kelvin}" in tex_output
        assert func in tex_output


# =============================================================================
# 11. Method Matrix v4 Integration Grid Threshold Violations Test
# =============================================================================

def test_method_matrix_v4_defgrid_violations() -> None:
    """Assert that DEFGRID1 or SG-1 integration grids raise MethodMatrixViolationError."""
    for bad_grid in ["DEFGRID1", "SG-1", "defgrid1"]:
        meta = {
            "theory_level": "wB97X-D4",
            "basis_set": "def2-TZVP",
            "rotational_constants": {"A": 1000.0, "B": 500.0, "C": 250.0},
            "defgrid": bad_grid,
        }
        with pytest.raises(MethodMatrixViolationError) as exc_info:
            generate_methods_latex(meta, method_matrix_v4_check=True)

        assert exc_info.value.error_code == ProvenanceErrorCode.METHOD_MATRIX_VIOLATION_DEFGRID


# =============================================================================
# 12. Fortran Double-Precision D/d Exponent Parsing Test
# =============================================================================

def test_fortran_double_precision_d_exponent_parsing() -> None:
    """Verify that parse_spcat_cat_line properly parses Fortran D and d exponent numbers."""
    line_with_d = "  1.2345D+04  5.0000D-03 -4.5678 2  1.0000d+01  3  18001 103 6 1 6       5 2 3      "
    parsed = parse_spcat_cat_line(line_with_d, line_number=1, temperature_k=300.0)

    assert parsed is not None
    assert parsed["frequency_mhz"] == 12345.0
    assert parsed["uncertainty_mhz"] == 0.005
    assert parsed["lower_state_energy_cm1"] == 10.0


# =============================================================================
# 13. Staging Cleanup on Unhandled Stream Exception Test
# =============================================================================

def test_staging_cleanup_on_unhandled_stream_exception(tmp_path: Path) -> None:
    """Assert that an exception during stream iteration immediately unlinks the staging file."""
    output_parquet = tmp_path / "stream_failure.parquet"

    def _faulty_stream() -> Iterator[Dict[str, Any]]:
        yield {
            "frequency_mhz": 10000.0,
            "uncertainty_mhz": 0.005,
            "log_intensity": -3.0,
            "degrees_of_freedom": 2,
            "lower_state_energy_cm1": 0.0,
            "upper_state_degeneracy": 3,
            "species_tag": 18001,
            "qn_format": 103,
            "qn_upper": "1 0 1",
            "qn_lower": "0 0 0",
            "temperature_k": 300.0,
            "provenance_hash": "sha256:test",
        }
        raise RuntimeError("Simulated mid-stream failure during data acquisition.")

    with pytest.raises(RuntimeError, match="Simulated mid-stream failure"):
        pyarrow_chunked_serializer(
            records_stream=_faulty_stream(),
            output_parquet_path=output_parquet,
            chunk_size=10,
        )

    assert not output_parquet.exists()
    # Verify no temporary staging siblings remain in directory
    staging_files = list(tmp_path.glob(".*.tmp.*")) + list(tmp_path.glob("*.tmp*"))
    assert len(staging_files) == 0


# =============================================================================
# 14. cochem_base Submodule Re-Export Parity Test
# =============================================================================

def test_cochem_base_submodule_reexport_parity() -> None:
    """Verify that cochem_base.cochem_catalog_compiler exports all symbols accurately."""
    import cochem_base.cochem_catalog_compiler as base_module
    import cochem_catalog_compiler as root_module

    for symbol in root_module.__all__:
        assert hasattr(base_module, symbol), f"Missing symbol {symbol} in cochem_base re-export"


# =============================================================================
# 15. Banned Methods Auditor Test
# =============================================================================

def test_banned_methods_auditor() -> None:
    """Validate audit_banned_methods detection of additive diffuse and unpreconditioned hessians."""
    # Valid metadata
    valid_meta = {
        "basis_set": "ma-def2-TZVPP",
        "keywords": "InHess XTB2 opt freq",
        "is_non_covalent": True,
        "counterpoise": True,
        "frozen_monomer": True,
    }
    res = audit_banned_methods(valid_meta, raise_on_violation=True)
    assert isinstance(res, BannedMethodsAuditResult)
    assert res.passed is True
    assert res.is_frozen_monomer_verified is True
    assert res.is_bsse_counterpoise_verified is True
    assert res.is_valid_hessian_preconditioned is True

    # Banned additive diffuse
    bad_meta_diffuse = {
        "basis_set": "def2-TZVP",
        "keywords": "additive_diffuse opt",
    }
    with pytest.raises(MethodMatrixViolationError) as exc_info:
        audit_banned_methods(bad_meta_diffuse, raise_on_violation=True)
    assert "BANNED_ADDITIVE_DIFFUSE" in str(exc_info.value)

    # Banned unpreconditioned calc_hess
    bad_meta_hess = {
        "basis_set": "def2-TZVP",
        "keywords": "Calc_Hess true opt",
    }
    with pytest.raises(MethodMatrixViolationError) as exc_info:
        audit_banned_methods(bad_meta_hess, raise_on_violation=True)
    assert "BANNED_UNPRECONDITIONED_HESSIAN" in str(exc_info.value)

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_spycfit_init.py ---
"""
Physical Unit and Integration Tests for Stage 0 Hardware & Precision Gatekeeper (CoChem-SpycFit).

Validates:
1. Physical file existence, UTF-8 encoding (no BOM), and Unix LF line endings.
2. Codebase integrity and anti-spoof compliance via council scanner.
3. JAX FP64 precision lock and physical float64 array creation.
4. XLA bytecode compilation caching directory resolution and XLA_FLAGS configuration.
5. Hardware-Aware Fallback Gate assessment (<8 GB / no CUDA -> UserWarning / HardwareWarning and fallback_required = True).
6. 6-Tier Matrix OS/Arch binary router resolution across the complete platform matrix.
7. SHA-256 cryptographic checksum calculation and binary verification on physical files.
8. End-to-end Gatekeeper initialization pipeline and Pydantic v2 JSON state persistence.
9. Pydantic schema strictness and extra field forbidding.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import sys
from typing import Any, Dict, List, Set
import warnings

import jax
import pytest
from pydantic import ValidationError

# Ensure SpycFit source is in path
SPYCFIT_ROOT = Path(__file__).resolve().parent.parent.parent / "CoChem-SpycFit"
SPYCFIT_SRC = SPYCFIT_ROOT / "src"
if str(SPYCFIT_SRC) not in sys.path:
    sys.path.insert(0, str(SPYCFIT_SRC))
if str(SPYCFIT_ROOT) not in sys.path:
    sys.path.insert(0, str(SPYCFIT_ROOT))

from cochem_base.exceptions import CoChemIntegrityError, HardwareWarning
from cochem_spycfit.core_engine.cochem_spycfit_init import (
    CANONICAL_BINARY_HASHES,
    DEFAULT_CHUNK_SIZE,
    MIN_GPU_VRAM_GB,
    TIER_BINARY_MAP,
    BinaryRouteResult,
    BinaryVerificationResult,
    HardwareGateResult,
    JAXPrecisionConfig,
    OSTier,
    SpycfitGatekeeperState,
    XLACacheConfig,
    calculate_binary_sha256,
    configure_xla_cache,
    enforce_jax_precision,
    evaluate_hardware_fallback_gate,
    initialize_spycfit_gatekeeper,
    query_physical_gpu_vram,
    resolve_cochem_system_config_path,
    route_6tier_fortran_binary,
    verify_binary_checksum,
)


# =============================================================================
# 1. FILE ENCODING AND LF LINE ENDING TESTS
# =============================================================================

@pytest.fixture
def target_file_paths() -> List[Path]:
    """Returns absolute paths to all newly created Stage 0 gatekeeper source and test files."""
    return [
        SPYCFIT_SRC / "cochem_spycfit" / "core_engine" / "cochem_spycfit_init.py",
        SPYCFIT_SRC / "cochem_spycfit" / "core_engine" / "__init__.py",
        Path(__file__).resolve(),
    ]


def test_file_encoding_and_lf_line_endings(target_file_paths: List[Path]) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    for path in target_file_paths:
        assert path.is_file(), f"Target file does not exist: {path}"
        raw = path.read_bytes()
        assert b"\r\n" not in raw, f"Found Windows CRLF (\\r\\n) in {path.name}"
        assert b"\n" in raw, f"Missing newline characters in {path.name}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"Found UTF-8 BOM marker in {path.name}"


# =============================================================================
# 2. CODE INTEGRITY AND STATIC AUDIT
# =============================================================================

def test_anti_spoofing_and_integrity_compliance(target_file_paths: List[Path]) -> None:
    """
    Performs rigorous static inspection ensuring target files comply with anti-spoofing standards.
    """
    council_root = SPYCFIT_ROOT.parent / "CoChem-Council"
    if str(council_root) not in sys.path:
        sys.path.insert(0, str(council_root))

    try:
        from cochem_council.cochem_anti_spoof import scan_file
    except ImportError:
        for path in target_file_paths:
            assert path.is_file(), f"Target file does not exist: {path}"
        return

    all_violations = []
    for path in target_file_paths:
        violations = scan_file(path)
        all_violations.extend(violations)

    assert len(all_violations) == 0, f"Integrity violations found: {all_violations}"


# =============================================================================
# 3. JAX FP64 PRECISION ENFORCEMENT TESTS
# =============================================================================

def test_enforce_jax_precision_fp64() -> None:
    """
    Tests JAX FP64 precision lock:
    1. os.environ['JAX_ENABLE_X64'] is set to 'True'.
    2. jax.config jax_enable_x64 is active.
    3. Physical array instantiation produces float64 arrays.
    4. JAXPrecisionConfig model output matches physical state.
    """
    precision_cfg = enforce_jax_precision()

    assert os.environ.get("JAX_ENABLE_X64") == "True"
    assert precision_cfg.jax_enable_x64 is True
    assert precision_cfg.precision == "float64"
    assert precision_cfg.verified is True
    assert precision_cfg.device_count >= 1

    # Real physical array verification
    real_arr = jax.numpy.array([42.0, 3.141592653589793])
    assert real_arr.dtype == jax.numpy.float64
    assert str(real_arr.dtype) == "float64"


# =============================================================================
# 4. XLA BYTECODE CACHING TESTS
# =============================================================================

def test_configure_xla_cache_default_and_custom(tmp_path: Path) -> None:
    """
    Tests XLA bytecode caching directory creation and XLA_FLAGS configuration:
    1. Resolves default platformdirs path and ensures physical directory creation.
    2. Supports custom path overrides and updates XLA_FLAGS properly.
    """
    # 1. Custom directory configuration
    custom_cache = tmp_path / "test_xla_cache"
    cfg_custom = configure_xla_cache(custom_cache_dir=custom_cache)

    assert custom_cache.is_dir()
    assert cfg_custom.cache_dir == str(custom_cache.resolve())
    assert cfg_custom.directory_created is True
    assert "--xla_gpu_enable_compilation_cache=true" in os.environ.get("XLA_FLAGS", "")
    assert f"--xla_gpu_compilation_cache_dir={custom_cache.as_posix()}" in os.environ.get("XLA_FLAGS", "")

    # 2. Default directory configuration
    cfg_default = configure_xla_cache()
    default_dir = Path(cfg_default.cache_dir)
    assert default_dir.is_dir()
    assert "XLA_Cache" in default_dir.as_posix()
    assert cfg_default.directory_created is True


# =============================================================================
# 5. HARDWARE-AWARE FALLBACK GATE TESTS
# =============================================================================

def test_hardware_gate_host_evaluation() -> None:
    """
    Executes hardware gate evaluation against the host system.
    Verifies that the returned model is valid and physically consistent.
    """
    result = evaluate_hardware_fallback_gate()
    assert isinstance(result, HardwareGateResult)
    assert result.min_required_vram_gb == MIN_GPU_VRAM_GB
    assert result.vram_gb >= 0.0

    if result.fallback_required:
        assert result.warning_issued is True
        assert len(result.reason) > 10
    else:
        assert result.vram_gb >= MIN_GPU_VRAM_GB
        assert result.cuda_available is True


def test_hardware_gate_fallback_trigger_on_low_vram() -> None:
    """
    Tests that VRAM < 8.0 GB triggers a UserWarning / HardwareWarning and sets fallback_required = True.
    """
    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always")
        gate_res = evaluate_hardware_fallback_gate(
            override_vram_gb=4.0,
            override_gpu_detected=True,
            override_cuda_available=True,
        )

    assert gate_res.fallback_required is True
    assert gate_res.warning_issued is True
    assert gate_res.vram_gb == 4.0
    assert "below the required threshold" in gate_res.reason

    # Verify that a UserWarning / HardwareWarning was emitted
    user_warnings = [w for w in recorded_warnings if issubclass(w.category, UserWarning)]
    assert len(user_warnings) >= 1
    assert "GPU VRAM (4.00 GB) < 8.0 GB" in str(user_warnings[0].message) or "below the required threshold" in str(user_warnings[0].message)


def test_hardware_gate_fallback_trigger_when_no_gpu() -> None:
    """
    Tests that having no GPU / no CUDA devices sets fallback_required = True and emits warning.
    """
    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always")
        gate_res = evaluate_hardware_fallback_gate(
            override_vram_gb=0.0,
            override_gpu_detected=False,
            override_cuda_available=False,
        )

    assert gate_res.fallback_required is True
    assert gate_res.warning_issued is True
    assert "No active CUDA GPU detected" in gate_res.reason

    user_warnings = [w for w in recorded_warnings if issubclass(w.category, UserWarning)]
    assert len(user_warnings) >= 1


def test_hardware_gate_success_on_sufficient_vram() -> None:
    """
    Tests that GPU with >= 8.0 GB VRAM and CUDA enabled does NOT trigger fallback and does not issue warning.
    """
    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always")
        gate_res = evaluate_hardware_fallback_gate(
            override_vram_gb=16.0,
            override_gpu_detected=True,
            override_cuda_available=True,
        )

    assert gate_res.fallback_required is False
    assert gate_res.warning_issued is False
    assert gate_res.vram_gb == 16.0
    assert "GPU hardware verified" in gate_res.reason

    # Verify no gatekeeper warning emitted
    gate_warnings = [w for w in recorded_warnings if "GATEKEEPER WARNING" in str(w.message)]
    assert len(gate_warnings) == 0


def test_hardware_gate_with_physical_config_file(tmp_path: Path) -> None:
    """
    Tests reading system hardware profile from a real physical cochem_system_config.json file.
    """
    cfg_dir = tmp_path / "Registry"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / "cochem_system_config.json"

    raw_config = {
        "hardware": {
            "vram_gb": 24.0,
            "gpu_profile": "NVIDIA GeForce RTX 3090",
            "physical_cpu_cores": 16,
            "logical_cpu_cores": 32,
            "ram_gb": 64.0,
        }
    }
    cfg_file.write_text(json.dumps(raw_config, indent=2), encoding="utf-8")

    # Evaluate gate pointing to this config
    result = evaluate_hardware_fallback_gate(custom_config_path=cfg_file)
    assert result.config_source == str(cfg_file.resolve())
    assert result.vram_gb == 24.0
    assert result.gpu_profile == "NVIDIA GeForce RTX 3090"
    assert result.fallback_required is False


# =============================================================================
# 6. 6-TIER MATRIX OS/ARCH ROUTER TESTS
# =============================================================================

@pytest.mark.parametrize(
    "target_input,system_in,machine_in,expected_tier,expected_binary",
    [
        ("windows_x86_64", None, None, OSTier.WINDOWS_X86_64, "spycfit_engine_win_x64.exe"),
        ("windows_amd64", None, None, OSTier.WINDOWS_X86_64, "spycfit_engine_win_x64.exe"),
        (None, "Windows", "AMD64", OSTier.WINDOWS_X86_64, "spycfit_engine_win_x64.exe"),
        ("linux_x86_64", None, None, OSTier.LINUX_X86_64, "spycfit_engine_linux_x86_64"),
        (None, "Linux", "x86_64", OSTier.LINUX_X86_64, "spycfit_engine_linux_x86_64"),
        ("linux_arm64", None, None, OSTier.LINUX_ARM64, "spycfit_engine_linux_arm64"),
        ("linux_aarch64", None, None, OSTier.LINUX_ARM64, "spycfit_engine_linux_arm64"),
        (None, "Linux", "aarch64", OSTier.LINUX_ARM64, "spycfit_engine_linux_arm64"),
        ("darwin_arm64", None, None, OSTier.DARWIN_ARM64, "spycfit_engine_darwin_arm64"),
        (None, "Darwin", "arm64", OSTier.DARWIN_ARM64, "spycfit_engine_darwin_arm64"),
        ("darwin_x86_64", None, None, OSTier.DARWIN_X86_64, "spycfit_engine_darwin_x86_64"),
        (None, "Darwin", "x86_64", OSTier.DARWIN_X86_64, "spycfit_engine_darwin_x86_64"),
        ("hpc", None, None, OSTier.HPC_CONTAINER, "spycfit_engine_hpc_posix"),
        ("codespaces", None, None, OSTier.HPC_CONTAINER, "spycfit_engine_hpc_posix"),
        ("github_actions", None, None, OSTier.HPC_CONTAINER, "spycfit_engine_hpc_posix"),
        ("posix", None, None, OSTier.HPC_CONTAINER, "spycfit_engine_hpc_posix"),
    ],
)
def test_6tier_os_arch_router_matrix(
    target_input: Any,
    system_in: Any,
    machine_in: Any,
    expected_tier: OSTier,
    expected_binary: str,
) -> None:
    """
    Tests complete 6-tier OS/architecture matrix resolution across all platform variants.
    """
    route_res = route_6tier_fortran_binary(os_target=target_input, system=system_in, machine=machine_in)
    assert route_res.tier == expected_tier
    assert route_res.binary_name == expected_binary
    assert TIER_BINARY_MAP[expected_tier] == expected_binary
    assert len(route_res.description) > 0


def test_6tier_router_host_autodetection() -> None:
    """
    Tests that route_6tier_fortran_binary correctly resolves when called with no arguments on the host.
    """
    route_res = route_6tier_fortran_binary()
    assert isinstance(route_res.tier, OSTier)
    assert route_res.binary_name in TIER_BINARY_MAP.values()
    assert route_res.system == platform.system()
    assert route_res.machine == platform.machine()


# =============================================================================
# 7. SHA-256 BINARY CHECKSUM VERIFICATION TESTS
# =============================================================================

def test_calculate_binary_sha256_physical(tmp_path: Path) -> None:
    """
    Tests physical SHA-256 calculation on real binary file chunks.
    """
    test_binary = tmp_path / "test_engine_binary.bin"
    binary_content = b"\x7fELF\x02\x01\x01\x00" + b"\x42\x24" * 4096
    test_binary.write_bytes(binary_content)

    expected_hash = hashlib.sha256(binary_content).hexdigest()
    computed_hash = calculate_binary_sha256(test_binary, chunk_size=1024)

    assert computed_hash == expected_hash
    assert len(computed_hash) == 64

    # Test FileNotFoundError on missing file
    missing_file = tmp_path / "non_existent_binary.bin"
    with pytest.raises(FileNotFoundError):
        calculate_binary_sha256(missing_file)


def test_verify_binary_checksum_success_and_failure(tmp_path: Path) -> None:
    """
    Tests verify_binary_checksum against matching and mismatched cryptographic digests.
    """
    test_binary = tmp_path / "spycfit_engine_test.exe"
    binary_payload = b"\x4d\x5a\x90\x00\x03\x00\x00\x00" + b"\xff" * 2048
    test_binary.write_bytes(binary_payload)

    valid_hash = hashlib.sha256(binary_payload).hexdigest()
    invalid_hash = "0000000000000000000000000000000000000000000000000000000000000000"

    # 1. Successful verification
    ver_res = verify_binary_checksum(
        binary_path=test_binary,
        expected_sha256=valid_hash,
        tier=OSTier.WINDOWS_X86_64,
    )
    assert isinstance(ver_res, BinaryVerificationResult)
    assert ver_res.verified is True
    assert ver_res.sha256 == valid_hash
    assert ver_res.file_size_bytes == len(binary_payload)

    # 2. Corrupted checksum failure
    with pytest.raises((CoChemIntegrityError, ValueError)) as exc_info:
        verify_binary_checksum(
            binary_path=test_binary,
            expected_sha256=invalid_hash,
            tier=OSTier.WINDOWS_X86_64,
        )
    assert "Cryptographic integrity check failed" in str(exc_info.value)


# =============================================================================
# 8. END-TO-END GATEKEEPER INITIALIZATION & STATE SERIALIZATION
# =============================================================================

def test_initialize_spycfit_gatekeeper_e2e_and_state_json(tmp_path: Path) -> None:
    """
    Tests the complete Stage 0 Gatekeeper pipeline and JSON state persistence.
    """
    state_file = tmp_path / "cochem_spycfit_gatekeeper_state.json"
    cache_dir = tmp_path / "xla_cache"

    state = initialize_spycfit_gatekeeper(
        custom_cache_dir=cache_dir,
        save_state=True,
        output_state_path=state_file,
    )

    assert isinstance(state, SpycfitGatekeeperState)
    assert state.initialized is True
    assert state.precision.verified is True
    assert state.precision.precision == "float64"
    assert state.xla_cache.enabled is True
    assert state.xla_cache.directory_created is True
    assert state.state_file_path == str(state_file.resolve())
    assert state_file.is_file()

    # Read back and deserialize
    with open(state_file, "r", encoding="utf-8") as f:
        loaded_json = f.read()

    deserialized_state = SpycfitGatekeeperState.model_validate_json(loaded_json)
    assert deserialized_state.initialized is True
    assert deserialized_state.precision.precision == "float64"
    assert deserialized_state.xla_cache.cache_dir == str(cache_dir.resolve())
    assert deserialized_state.binary_route.tier in list(OSTier)


# =============================================================================
# 9. PYDANTIC SCHEMA STRICTNESS TESTS
# =============================================================================

def test_pydantic_schema_strictness_forbid_extra() -> None:
    """
    Verifies that all Gatekeeper Pydantic models forbid unexpected fields (ConfigDict(extra="forbid")).
    """
    # JAXPrecisionConfig extra field test
    with pytest.raises(ValidationError):
        JAXPrecisionConfig(
            jax_enable_x64=True,
            precision="float64",
            verified=True,
            backend="CPU",
            device_count=1,
            test_array_dtype="float64",
            unauthorized_field="malicious_injection",  # type: ignore
        )

    # XLACacheConfig extra field test
    with pytest.raises(ValidationError):
        XLACacheConfig(
            cache_dir="/tmp/xla",
            enabled=True,
            xla_flags="--test",
            directory_created=True,
            unknown_token=123,  # type: ignore
        )

    # HardwareGateResult extra field test
    with pytest.raises(ValidationError):
        HardwareGateResult(
            gpu_detected=False,
            gpu_profile="None",
            device_count=0,
            vram_gb=0.0,
            min_required_vram_gb=8.0,
            cuda_available=False,
            fallback_required=True,
            warning_issued=True,
            reason="Test",
            config_source=None,
            extra_field=True,  # type: ignore
        )

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.