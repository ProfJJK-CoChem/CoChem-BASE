"""Deterministic environment fingerprints and verifiable Python source manifests.

A digest detects changes against a trusted manifest. It is not an auditor
signature or a scientific accuracy certificate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import tempfile
import time
from typing import Any, Iterable, Mapping

from filelock import FileLock
import psutil


class SourceIntegrityError(RuntimeError):
    """The source cannot be verified against the supplied manifest."""


@dataclass
class EnvironmentHashRecord:
    sha256_hash: str
    python_version: str
    python_implementation: str
    os_system: str
    os_release: str
    cpu_count: int
    total_ram_bytes: int
    core_dependencies: dict[str, str]
    engine_versions: dict[str, str]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> EnvironmentHashRecord:
        return cls(**dict(value))


@dataclass
class TopologicalLockRecord:
    repository_sha256: str
    file_count: int
    file_hashes: dict[str, str]
    generated_at: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> TopologicalLockRecord:
        return cls(**dict(value))

    @classmethod
    def from_json(cls, json_str_or_path: str | Path) -> TopologicalLockRecord:
        if not isinstance(json_str_or_path, (str, Path)):
            raise TypeError("Expected str or Path for json_str_or_path")
        if isinstance(json_str_or_path, str) and json_str_or_path.lstrip().startswith(("{", "[")):
            text = json_str_or_path
        else:
            path = Path(json_str_or_path)
            if not path.is_file():
                raise FileNotFoundError(f"Lock manifest file not found: {path}")
            text = path.read_text(encoding="utf-8")
        return cls.from_dict(json.loads(text))


_TEXT_EXTENSIONS = {".py", ".pyi", ".json", ".md", ".yaml", ".yml", ".toml", ".txt", ".bib"}
_EXCLUDED_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
                  ".ruff_cache", ".trash", "build", "dist", "scratch", "node_modules"}


def compute_file_sha256(path: str | Path, normalize_newlines: bool = True) -> str:
    """Hash bytes, normalizing line endings only for recognized text formats."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        pending = b""
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            if normalize_newlines and path.suffix.lower() in _TEXT_EXTENSIONS:
                chunk = pending + chunk
                # CRLF can straddle the read boundary.
                pending = b"\r" if chunk.endswith(b"\r") else b""
                if pending:
                    chunk = chunk[:-1]
                chunk = chunk.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            digest.update(chunk)
        if pending:
            digest.update(b"\n")
        after = os.fstat(stream.fileno())
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
    ):
        raise SourceIntegrityError(f"Source changed while being hashed: {path}")
    return digest.hexdigest()


def _private_path(value: str) -> bool:
    return bool(re.search(r"(?:[A-Za-z]:[\\/]|\\\\|(?:^|\s)/|~[/\\])", value))


def hash_environment(tracked_packages: Iterable[str] | None = None,
                     tracked_engines: Mapping[str, str] | Iterable[str] | None = None,
                     exclude_paths: bool = True) -> EnvironmentHashRecord:
    """Fingerprint observed stable hardware/package data, never credentials.

    Explicit engine version strings remain caller declarations, not proof that
    their executables ran. Volatile load measurements are not fingerprinted.
    """
    dependencies = {}
    for package in sorted(set(tracked_packages if tracked_packages is not None else
                              ("cochem-base", "numpy", "pydantic", "h5py", "filelock", "mendeleev"))):
        try:
            dependencies[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            dependencies[package] = "not-installed"
    if isinstance(tracked_engines, Mapping):
        engines = {str(key): str(value) for key, value in tracked_engines.items()}
        engine_source = "caller-declared versions"
    else:
        engines = {}
        for name in tracked_engines or ():
            try:
                engines[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                engines[name] = "unregistered"
        engine_source = "installed distribution metadata"
    if exclude_paths:
        dependencies = {("[SANITIZED_PATH]" if _private_path(k) else k):
                        ("[SANITIZED_PATH]" if _private_path(v) else v) for k, v in dependencies.items()}
        engines = {("[SANITIZED_PATH]" if _private_path(k) else k):
                   ("[SANITIZED_PATH]" if _private_path(v) else v) for k, v in engines.items()}
    cpu_count = os.cpu_count()
    if cpu_count is None or cpu_count < 1:
        raise RuntimeError("CPU topology is unavailable for environment fingerprinting")
    payload = dict(python_version=platform.python_version(), python_implementation=platform.python_implementation(),
                   os_system=platform.system(), os_release=platform.release(), cpu_count=cpu_count,
                   total_ram_bytes=int(psutil.virtual_memory().total), core_dependencies=dependencies,
                   engine_versions=engines, metadata={"os_architecture": platform.machine(), "engine_version_source": engine_source})
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return EnvironmentHashRecord(sha256_hash=digest, **payload)


def _repository(repo_dir: str | Path | None) -> Path:
    if repo_dir is None:
        source = Path(__file__).resolve()
        path = next((p for p in source.parents if (p / ".git").exists()), None)
        if path is None:
            raise FileNotFoundError("Repository directory not found; provide repo_dir for an installed wheel")
    else:
        path = Path(repo_dir).expanduser().resolve()
    if not path.is_dir():
        raise FileNotFoundError(f"Repository directory not found: {path}")
    return path


def _source_files(root: Path, exclude_dirs: Iterable[str] | None) -> list[Path]:
    excluded = _EXCLUDED_DIRS | set(exclude_dirs or ())
    files = []
    for directory, names, filenames in os.walk(root, followlinks=False):
        names[:] = sorted(name for name in names if name not in excluded and not name.endswith(".egg-info"))
        for name in names:
            if (Path(directory) / name).is_symlink():
                raise SourceIntegrityError(f"Symlinked source directory cannot be attested: {Path(directory) / name}")
        for name in filenames:
            if name.endswith(".py"):
                path = Path(directory) / name
                if path.is_symlink():
                    raise SourceIntegrityError(f"Symlinked source file cannot be attested: {path}")
                files.append(path)
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def _manifest_digest(hashes: Mapping[str, str]) -> str:
    digest = hashlib.sha256()
    for name in sorted(hashes):
        digest.update(f"{name}:{hashes[name]}\n".encode("utf-8"))
    return digest.hexdigest()


def compute_repository_source_hash(repo_dir: str | Path | None = None,
                                   exclude_dirs: Iterable[str] | None = None) -> tuple[str, dict[str, str]]:
    root = _repository(repo_dir)
    paths = _source_files(root, exclude_dirs)
    hashes = {path.relative_to(root).as_posix(): compute_file_sha256(path) for path in paths}
    if paths != _source_files(root, exclude_dirs):
        raise SourceIntegrityError("Source membership changed while creating the manifest")
    return _manifest_digest(hashes), hashes


def generate_topological_source_lock(repo_dir: str | Path | None = None,
                                     output_path: str | Path | None = None,
                                     exclude_dirs: Iterable[str] | None = None) -> TopologicalLockRecord:
    excluded = sorted(set(exclude_dirs or ()))
    digest, hashes = compute_repository_source_hash(repo_dir, excluded)
    record = TopologicalLockRecord(digest, len(hashes), hashes, time.time(),
                                  {"scope": "Python source files", "exclude_dirs": excluded, "newline_normalization": True})
    if output_path is not None:
        from cochem.core.context import assert_writable_path

        target = Path(output_path).expanduser().resolve()
        assert_writable_path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(target) + ".lock", timeout=10.0):
            descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
            temporary = Path(name)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump(record.to_dict(), stream, sort_keys=True, indent=2, allow_nan=False)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
    return record


def verify_source_code_integrity(repo_dir: str | Path | None = None,
                                 lock_record: TopologicalLockRecord | str | Path | None = None,
                                 expected_hash: str | None = None,
                                 exclude_dirs: Iterable[str] | None = None) -> tuple[bool, list[str]]:
    if lock_record is None and expected_hash is None:
        raise ValueError("Integrity verification requires either 'expected_hash' or 'lock_record'")
    if isinstance(lock_record, (str, Path)):
        lock_record = TopologicalLockRecord.from_json(lock_record)
    if lock_record is not None and not isinstance(lock_record, TopologicalLockRecord):
        raise TypeError("lock_record must be a TopologicalLockRecord or manifest path")
    if exclude_dirs is None and lock_record is not None:
        exclude_dirs = lock_record.metadata.get("exclude_dirs", ())
    current, files = compute_repository_source_hash(repo_dir, exclude_dirs)
    issues = []
    if expected_hash is not None and current != expected_hash:
        issues.append(f"Repository master hash mismatch: expected '{expected_hash}', observed '{current}'")
    if lock_record is not None:
        expected_files = lock_record.file_hashes
        if lock_record.file_count != len(expected_files):
            issues.append("Lock manifest file_count differs from its file hashes")
        for path in sorted(expected_files.keys() - files.keys()):
            issues.append(f"Missing source file: {path}")
        for path in sorted(files.keys() - expected_files.keys()):
            issues.append(f"Untracked/added source file: {path}")
        for path in sorted(files.keys() & expected_files.keys()):
            if files[path] != expected_files[path]:
                issues.append(f"Tampered source file: {path}")
        if lock_record.repository_sha256 != _manifest_digest(expected_files):
            issues.append(f"Repository master hash mismatch: expected '{lock_record.repository_sha256}', "
                          "manifest file hashes do not match that digest")
    return not issues, issues


def assert_topological_lock(**kwargs: Any) -> None:
    valid, issues = verify_source_code_integrity(**kwargs)
    if not valid:
        raise SourceIntegrityError(f"[TopologicalLock] Integrity check failed with {len(issues)} violations: " + "; ".join(issues))


__all__ = ["EnvironmentHashRecord", "SourceIntegrityError", "TopologicalLockRecord", "assert_topological_lock",
           "compute_file_sha256", "compute_repository_source_hash", "generate_topological_source_lock",
           "hash_environment", "verify_source_code_integrity"]
