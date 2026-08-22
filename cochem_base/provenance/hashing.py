"""Cryptographic Provenance, Environmental Fingerprinting, and Topological Source Locking.

Provides deterministic SHA-256 state tracking for physical execution environments
and immutable topological source locks across the CoChem repository to enforce the
Anti-Spoofing, Zero-Fabrication, and Method Matrix mandates.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import logging
import os
import platform
import re
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    import psutil  # type: ignore[import-untyped]

    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

from cochem_base.config_loader import get_base_root, get_repo_root

logger = logging.getLogger(__name__)


class SourceIntegrityError(Exception):
    """Raised when repository source code integrity check fails or source tampering is detected."""


@dataclass
class EnvironmentHashRecord:
    """Deterministic cryptographic record of the physical execution host environment."""

    sha256_hash: str
    python_version: str
    python_implementation: str
    os_system: str
    os_release: str
    cpu_count: int
    total_ram_bytes: int
    core_dependencies: dict[str, str] = field(default_factory=dict)
    engine_versions: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnvironmentHashRecord:
        return cls(
            sha256_hash=data["sha256_hash"],
            python_version=data["python_version"],
            python_implementation=data["python_implementation"],
            os_system=data["os_system"],
            os_release=data["os_release"],
            cpu_count=data["cpu_count"],
            total_ram_bytes=data["total_ram_bytes"],
            core_dependencies=data.get("core_dependencies", {}),
            engine_versions=data.get("engine_versions", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TopologicalLockRecord:
    """Cryptographic lock manifest of all Python source files in the repository."""

    repository_sha256: str
    file_count: int
    file_hashes: dict[str, str]  # Relative path (POSIX) -> SHA256
    generated_at: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TopologicalLockRecord:
        return cls(
            repository_sha256=data["repository_sha256"],
            file_count=data["file_count"],
            file_hashes=data["file_hashes"],
            generated_at=data["generated_at"],
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, json_str_or_path: str | Path) -> TopologicalLockRecord:
        if isinstance(json_str_or_path, Path):
            p = json_str_or_path.resolve()
            if not p.is_file():
                raise FileNotFoundError(f"Lock manifest file not found: {p}")
            data = json.loads(p.read_text(encoding="utf-8"))
        elif isinstance(json_str_or_path, str):
            stripped = json_str_or_path.strip()
            if stripped.startswith("{"):
                data = json.loads(stripped)
            else:
                p = Path(json_str_or_path).resolve()
                if not p.is_file():
                    raise FileNotFoundError(f"Lock manifest file not found: {p}")
                data = json.loads(p.read_text(encoding="utf-8"))
        else:
            raise TypeError(
                f"Expected str or Path for json_str_or_path, got {type(json_str_or_path).__name__}"
            )
        return cls.from_dict(data)


def compute_file_sha256(filepath: str | Path, normalize_newlines: bool = True) -> str:
    """Computes a deterministic SHA-256 checksum of a file.

    For text/source files, normalizes newline endings (\r\n -> \n, \r -> \n)
    so checksums remain invariant across Windows and POSIX checkouts.
    """
    p = Path(filepath).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"File not found: {p}")

    hasher = hashlib.sha256()

    text_suffixes = {".py", ".json", ".md", ".yaml", ".yml", ".toml", ".txt", ".bib"}
    if normalize_newlines and p.suffix.lower() in text_suffixes:
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            normalized = content.replace("\r\n", "\n").replace("\r", "\n")
            hasher.update(normalized.encode("utf-8"))
            return hasher.hexdigest()
        except (UnicodeDecodeError, OSError) as e:
            logger.debug(
                "Falling back to binary hashing for %s due to read error: %s", p, e
            )

    # Binary fallback with 64KB chunking
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)

    return hasher.hexdigest()


def _sanitize_path_leakages(payload_str: str) -> str:
    r"""Sanitizes local absolute directory paths from serialized JSON environment payloads.

    Removes Windows drive roots (C:\, D:/), POSIX system hierarchies (/home/, /Users/, /tmp/),
    and UNC network shares (\\server\share).
    """
    # 1. Windows drive letters with backslashes (single or escaped) or forward slashes
    p1 = r'[A-Za-z]:(?:\\\\|\\|/)[^",}\]\r\n]*'
    sanitized = re.sub(p1, "[SANITIZED_PATH]", payload_str)

    # 2. POSIX absolute directory paths
    p2 = r'/(?:home|Users|root|tmp|var|opt|usr|etc|Volumes)/[^",}\]\r\n]*'
    sanitized = re.sub(p2, "[SANITIZED_PATH]", sanitized)

    # 3. UNC network paths
    p3 = r'(?:\\\\\\\\|//|\\\\)[^",}\]\r\n]*'
    sanitized = re.sub(p3, "[SANITIZED_PATH]", sanitized)

    # 4. Standalone Users directories
    p4 = r'(?:\\\\|/)?(?:Users|AppData|Documents|Desktop)(?:\\\\|/)[^",}\]\r\n]*'
    sanitized = re.sub(p4, "[SANITIZED_PATH]", sanitized)

    return sanitized


def hash_environment(
    exclude_paths: bool = True,
    tracked_packages: Sequence[str] | None = None,
    tracked_engines: Sequence[str] | dict[str, str] | None = None,
) -> EnvironmentHashRecord:
    """Generates a deterministic cryptographic SHA-256 fingerprint of the execution host environment.

    Concatenates hashed physical host limits (RAM, CPU), Python version,
    dependency package versions, OS kernel version, architecture, and computational engine versions.
    Absolute local directory paths are strictly excluded to guarantee cross-host reproducibility.
    """
    py_ver = platform.python_version()
    py_impl = platform.python_implementation()
    os_sys = platform.system()
    os_rel = platform.release()
    os_arch = platform.machine()

    cpu_cnt = os.cpu_count() or 1
    total_ram = 0

    if _PSUTIL_AVAILABLE:
        try:
            mem = psutil.virtual_memory()
            total_ram = mem.total
        except (AttributeError, OSError, RuntimeError):
            total_ram = 0

    # Collect Python dependency versions deterministically
    default_packages = [
        "cochem-base",
        "pydantic",
        "numpy",
        "scipy",
        "pytest",
        "parsl",
        "torch",
        "pyscf",
        "ase",
        "rdkit",
    ]
    check_packages = sorted(set(tracked_packages or default_packages))
    dep_dict: dict[str, str] = {}

    for pkg in check_packages:
        try:
            ver = importlib.metadata.version(pkg)
            dep_dict[pkg] = ver
        except importlib.metadata.PackageNotFoundError:
            dep_dict[pkg] = "not-installed"
        except (OSError, ValueError, RuntimeError, AttributeError) as e:
            dep_dict[pkg] = f"unknown ({e})"

    # Collect computational engine versions deterministically
    engine_dict: dict[str, str] = {}
    if isinstance(tracked_engines, dict):
        for eng_name, eng_ver in sorted(tracked_engines.items()):
            engine_dict[eng_name] = str(eng_ver)
    else:
        default_engines = ["orca", "xtb", "cfour", "crest", "gpu4pyscf", "mrcc"]
        check_engines = sorted(set(tracked_engines or default_engines))
        for eng in check_engines:
            # Check if package version exists for Python-wrapped engines
            try:
                ver = importlib.metadata.version(eng)
                engine_dict[eng] = ver
            except importlib.metadata.PackageNotFoundError:
                engine_dict[eng] = "unregistered"
            except (OSError, ValueError, RuntimeError, AttributeError) as e:
                engine_dict[eng] = f"unknown ({e})"

    # Build canonical deterministic payload
    canonical_payload = {
        "python_version": py_ver,
        "python_implementation": py_impl,
        "os_system": os_sys,
        "os_release": os_rel,
        "os_architecture": os_arch,
        "cpu_count": cpu_cnt,
        "total_ram_bytes": total_ram,
        "core_dependencies": dep_dict,
        "engine_versions": engine_dict,
    }

    # Strict exclusion check: ensure no absolute path substrings exist in payload
    serialized = json.dumps(canonical_payload, sort_keys=True)
    if exclude_paths:
        serialized = _sanitize_path_leakages(serialized)
        sanitized_data = json.loads(serialized)
        dep_dict = sanitized_data.get("core_dependencies", dep_dict)
        engine_dict = sanitized_data.get("engine_versions", engine_dict)

    env_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    return EnvironmentHashRecord(
        sha256_hash=env_hash,
        python_version=py_ver,
        python_implementation=py_impl,
        os_system=os_sys,
        os_release=os_rel,
        cpu_count=cpu_cnt,
        total_ram_bytes=total_ram,
        core_dependencies=dep_dict,
        engine_versions=engine_dict,
        metadata={"os_architecture": os_arch},
    )


def compute_repository_source_hash(
    repo_dir: str | Path | None = None,
    exclude_dirs: Sequence[str] | None = None,
) -> tuple[str, dict[str, str]]:
    """Computes a unified SHA-256 hash of all Python source code in the repository.

    Returns:
        A tuple of (overall_repo_sha256, dict_of_relative_path_to_file_sha256).
    """
    if repo_dir is not None:
        root = Path(repo_dir).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Repository directory not found: {root}")
    else:
        try:
            root = get_base_root()
        except (AttributeError, RuntimeError, OSError):
            root = get_repo_root()

    default_excludes = {
        ".git",
        ".venv",
        "venv",
        ".conda",
        ".agents",
        ".system_generated",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".trash",
        "build",
        "dist",
        ".egg-info",
        "cochem_base.egg-info",
        "scratch",
    }
    excludes = (
        set(exclude_dirs) | default_excludes if exclude_dirs else default_excludes
    )

    file_hashes: dict[str, str] = {}
    master_hasher = hashlib.sha256()

    py_files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in-place
        dirnames[:] = [
            d for d in dirnames if d not in excludes and not d.endswith(".egg-info")
        ]

        for fname in filenames:
            fname_lower = fname.lower()
            if fname_lower.endswith(".py") and not fname_lower.endswith(".pyc"):
                full_path = Path(dirpath) / fname
                py_files.append(full_path)

    # Sort deterministically by relative POSIX path
    sorted_files = sorted(py_files, key=lambda p: p.relative_to(root).as_posix())

    for fpath in sorted_files:
        rel_posix = fpath.relative_to(root).as_posix()
        f_hash = compute_file_sha256(fpath, normalize_newlines=True)
        file_hashes[rel_posix] = f_hash
        # Feed relative path + file hash into master hasher
        master_hasher.update(f"{rel_posix}:{f_hash}\n".encode())

    repo_hash = master_hasher.hexdigest()
    return repo_hash, file_hashes


def generate_topological_source_lock(
    repo_dir: str | Path | None = None,
    output_path: str | Path | None = None,
    exclude_dirs: Sequence[str] | None = None,
    timestamp: float | None = None,
) -> TopologicalLockRecord:
    """Generates a TopologicalLockRecord for the repository and optionally saves it to disk."""
    if repo_dir is not None:
        root = Path(repo_dir).resolve()
    else:
        try:
            root = get_base_root()
        except (AttributeError, RuntimeError, OSError):
            root = get_repo_root()

    repo_hash, file_hashes = compute_repository_source_hash(
        root, exclude_dirs=exclude_dirs
    )

    record = TopologicalLockRecord(
        repository_sha256=repo_hash,
        file_count=len(file_hashes),
        file_hashes=file_hashes,
        generated_at=timestamp if timestamp is not None else time.time(),
    )

    if output_path is not None:
        p = Path(output_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
        logger.info(f"[TopologicalLock] Saved lock manifest to {p}")

    return record


def verify_source_code_integrity(
    repo_dir: str | Path | None = None,
    expected_hash: str | None = None,
    lock_record: TopologicalLockRecord | None = None,
    exclude_dirs: Sequence[str] | None = None,
) -> tuple[bool, list[str]]:
    """Verifies that no Python source files have been altered, added, or deleted.

    Returns:
        (is_valid, list_of_discrepancies)
    """
    if expected_hash is None and lock_record is None:
        raise ValueError(
            "Integrity verification requires either 'expected_hash' or 'lock_record' to be specified."
        )

    if repo_dir is not None:
        root = Path(repo_dir).resolve()
    else:
        try:
            root = get_base_root()
        except (AttributeError, RuntimeError, OSError):
            root = get_repo_root()

    current_hash, current_file_hashes = compute_repository_source_hash(
        root, exclude_dirs=exclude_dirs
    )
    discrepancies: list[str] = []

    # Check overall repository master SHA-256 if expected_hash was explicitly provided
    if expected_hash is not None and current_hash != expected_hash:
        discrepancies.append(
            f"Repository master hash mismatch: expected '{expected_hash}', got '{current_hash}'"
        )

    # Detailed per-file audit against manifest
    if lock_record is not None:
        expected_files = lock_record.file_hashes

        # Check for missing or tampered files
        for rel_path, exp_fhash in expected_files.items():
            if rel_path not in current_file_hashes:
                discrepancies.append(f"Missing source file: {rel_path}")
            elif current_file_hashes[rel_path] != exp_fhash:
                discrepancies.append(
                    f"Tampered source file: {rel_path} (expected {exp_fhash}, got {current_file_hashes[rel_path]})"
                )

        # Check for unauthorized added files
        for rel_path in current_file_hashes:
            if rel_path not in expected_files:
                discrepancies.append(f"Untracked/added source file: {rel_path}")

        # If expected_hash was not explicitly passed, but lock_record master hash mismatches
        # and no file-level discrepancies were detected (e.g., tampered record manifest hash):
        if (
            expected_hash is None
            and not discrepancies
            and current_hash != lock_record.repository_sha256
        ):
            discrepancies.append(
                f"Repository master hash mismatch: expected '{lock_record.repository_sha256}', got '{current_hash}'"
            )

    return (len(discrepancies) == 0, discrepancies)


def assert_topological_lock(
    repo_dir: str | Path | None = None,
    lock_record: TopologicalLockRecord | None = None,
    expected_hash: str | None = None,
    exclude_dirs: Sequence[str] | None = None,
) -> None:
    """Asserts that repository source code strictly matches the lock. Raises SourceIntegrityError on failure."""
    is_valid, issues = verify_source_code_integrity(
        repo_dir=repo_dir,
        expected_hash=expected_hash,
        lock_record=lock_record,
        exclude_dirs=exclude_dirs,
    )
    if not is_valid:
        error_msg = (
            f"[TopologicalLock] Integrity check failed with {len(issues)} violations:\n"
            + "\n".join(f"  - {iss}" for iss in issues)
        )
        logger.error(error_msg)
        raise SourceIntegrityError(error_msg)


__all__ = [
    "EnvironmentHashRecord",
    "SourceIntegrityError",
    "TopologicalLockRecord",
    "assert_topological_lock",
    "compute_file_sha256",
    "compute_repository_source_hash",
    "generate_topological_source_lock",
    "hash_environment",
    "verify_source_code_integrity",
]
