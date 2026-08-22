"""Comprehensive Physical Unit and Integration Tests for Cryptographic Provenance.

Validates:
1. Strict verification mandate: Real cryptographic hashes (hashlib.sha256), genuine OS calls,
   real temporary files on physical disk via tmp_path, real importlib.metadata, and physical hardware stats.
2. File SHA-256 hashing with CRLF/LF newline normalization and binary fallback.
3. Deterministic environment fingerprinting excluding local absolute paths.
4. Repository source code hashing with sorted POSIX relative paths and exclusion filtering.
5. TopologicalLockRecord disk persistence, serialization, and deserialization.
6. Real-time integrity verification: detecting modifications, deletions, and untracked additions.
7. assert_topological_lock behavior and SourceIntegrityError raising.
8. Dual-layout symbol parity between cochem_base.provenance.hashing and src.cochem_base.provenance.hashing.

Authoritative Standards:
- Method_Matrix.md
- CoChem_User_Manual.md
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import re
import sys
from pathlib import Path

import pytest

# Ensure repository root is in sys.path for direct import resilience across all execution environments
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import cochem_base.provenance.hashing as direct_hashing  # noqa: E402
import src.cochem_base.provenance.hashing as src_hashing  # noqa: E402
from cochem_base.provenance.hashing import (  # noqa: E402
    EnvironmentHashRecord,
    SourceIntegrityError,
    TopologicalLockRecord,
    assert_topological_lock,
    compute_file_sha256,
    compute_repository_source_hash,
    generate_topological_source_lock,
    hash_environment,
    verify_source_code_integrity,
)

# =============================================================================
# 1. File SHA-256 Checksum and Normalization Tests
# =============================================================================


def test_compute_file_sha256(tmp_path: Path) -> None:
    """Validates compute_file_sha256 with CRLF/LF normalization, binary fallback, and missing file error."""
    # 1. CRLF vs LF normalization equality on physical files across supported extensions
    text_extensions = [".py", ".json", ".md", ".yaml", ".yml", ".toml", ".txt", ".bib"]
    base_text = "def compute_energy(mol: str) -> float:\n    # Physical calculation\n    return 3.14159\n"

    for ext in text_extensions:
        f_lf = tmp_path / f"source_lf{ext}"
        f_crlf = tmp_path / f"source_crlf{ext}"
        f_cr = tmp_path / f"source_cr{ext}"

        f_lf.write_bytes(base_text.encode("utf-8"))
        f_crlf.write_bytes(base_text.replace("\n", "\r\n").encode("utf-8"))
        f_cr.write_bytes(base_text.replace("\n", "\r").encode("utf-8"))

        hash_lf = compute_file_sha256(f_lf, normalize_newlines=True)
        hash_crlf = compute_file_sha256(f_crlf, normalize_newlines=True)
        hash_cr = compute_file_sha256(f_cr, normalize_newlines=True)

        assert hash_lf == hash_crlf, f"CRLF normalization mismatch for {ext}"
        assert hash_lf == hash_cr, f"CR normalization mismatch for {ext}"
        assert len(hash_lf) == 64
        assert re.fullmatch(r"[0-9a-f]{64}", hash_lf) is not None

    # Verify that without normalization, CRLF and LF produce different checksums
    raw_lf_hash = compute_file_sha256(
        tmp_path / "source_lf.py", normalize_newlines=False
    )
    raw_crlf_hash = compute_file_sha256(
        tmp_path / "source_crlf.py", normalize_newlines=False
    )
    assert raw_lf_hash != raw_crlf_hash, (
        "Raw binary hash must differ between CRLF and LF"
    )

    # 2. Binary fallback without conversion for non-text extensions
    binary_data = b"\x00\xff\xfe\r\n\x00\x01\x02\r\n\xaa\xbb\xcc\xdd"
    bin_file = tmp_path / "quantum_orbitals.bin"
    bin_file.write_bytes(binary_data)

    expected_binary_sha256 = hashlib.sha256(binary_data).hexdigest()
    computed_bin_hash = compute_file_sha256(bin_file, normalize_newlines=True)

    assert computed_bin_hash == expected_binary_sha256
    assert len(computed_bin_hash) == 64

    # Another binary format: .dat
    dat_file = tmp_path / "trajectory.dat"
    dat_file.write_bytes(binary_data)
    assert (
        compute_file_sha256(dat_file, normalize_newlines=True) == expected_binary_sha256
    )

    # 3. FileNotFoundError on non-existent files
    non_existent = tmp_path / "non_existent_module.py"
    with pytest.raises(FileNotFoundError, match="File not found"):
        compute_file_sha256(non_existent)

    nested_missing = tmp_path / "missing_subdir" / "target.py"
    with pytest.raises(FileNotFoundError, match="File not found"):
        compute_file_sha256(nested_missing)


# =============================================================================
# 2. Environmental Fingerprinting Tests
# =============================================================================


def test_hash_environment() -> None:
    """Validates deterministic environment hashing, path sanitization, and hardware metrics extraction."""
    # 1. Deterministic SHA-256 fingerprint on consecutive physical calls
    record1 = hash_environment()
    record2 = hash_environment()

    assert isinstance(record1, EnvironmentHashRecord)
    assert isinstance(record2, EnvironmentHashRecord)
    assert record1.sha256_hash == record2.sha256_hash
    assert len(record1.sha256_hash) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", record1.sha256_hash) is not None

    # 2. Strict exclusion/sanitization of absolute drive paths ('C:\', '/home/', '/Users/', '\\Users\\')
    serialized_dict = record1.to_dict()
    serialized_json = json.dumps(serialized_dict)

    assert ":\\" not in serialized_json, (
        "Unsanitized Windows drive path leaked into environment record"
    )
    assert "/home/" not in serialized_json, (
        "Unsanitized POSIX /home/ path leaked into environment record"
    )
    assert "/Users/" not in serialized_json, (
        "Unsanitized macOS /Users/ path leaked into environment record"
    )
    assert "\\Users\\" not in serialized_json, (
        "Unsanitized Windows Users path leaked into environment record"
    )

    # 3. Dependency version dictionary extraction
    assert isinstance(record1.core_dependencies, dict)
    assert len(record1.core_dependencies) > 0

    # Test with explicitly tracked packages including installed and non-installed packages
    custom_packages = ["pytest", "pydantic", "completely_non_existent_cochem_pkg_12345"]
    custom_record = hash_environment(tracked_packages=custom_packages)

    assert (
        custom_record.core_dependencies["completely_non_existent_cochem_pkg_12345"]
        == "not-installed"
    )
    assert custom_record.core_dependencies["pytest"] == importlib.metadata.version(
        "pytest"
    )
    assert custom_record.core_dependencies["pydantic"] == importlib.metadata.version(
        "pydantic"
    )

    # 4. Graceful execution with physical hardware and platform metrics
    assert isinstance(record1.cpu_count, int)
    assert record1.cpu_count >= 1
    assert isinstance(record1.total_ram_bytes, int)
    assert record1.total_ram_bytes >= 0
    assert record1.python_version == platform.python_version()
    assert record1.python_implementation == platform.python_implementation()
    assert record1.os_system == platform.system()
    assert record1.os_release == platform.release()
    assert record1.metadata.get("os_architecture") == platform.machine()


# =============================================================================
# 3. Repository Source Code Hashing Tests
# =============================================================================


def test_compute_repository_source_hash(tmp_path: Path) -> None:
    """Validates unified repository hashing over physical directories with POSIX sorting and exclusions."""
    repo_dir = tmp_path / "physical_cochem_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Construct genuine nested module hierarchy
    pkg_core = repo_dir / "cochem_base" / "core"
    pkg_utils = repo_dir / "cochem_base" / "utils"
    scripts = repo_dir / "scripts"

    pkg_core.mkdir(parents=True, exist_ok=True)
    pkg_utils.mkdir(parents=True, exist_ok=True)
    scripts.mkdir(parents=True, exist_ok=True)

    (repo_dir / "cochem_base" / "__init__.py").write_text(
        '"""Init."""\n', encoding="utf-8"
    )
    (pkg_core / "__init__.py").write_text('"""Core init."""\n', encoding="utf-8")
    (pkg_core / "engine.py").write_text(
        'def run_engine():\n    return "converged"\n', encoding="utf-8"
    )
    (pkg_utils / "helpers.py").write_text(
        "def helper():\n    return 42\n", encoding="utf-8"
    )
    (scripts / "entrypoint.py").write_text(
        'print("Starting pipeline")\n', encoding="utf-8"
    )

    # Add non-Python files that must NOT be indexed in file_hashes
    (repo_dir / "README.md").write_text("# CoChem Base\n", encoding="utf-8")
    (repo_dir / "config.json").write_text('{"mode": "production"}\n', encoding="utf-8")
    (repo_dir / "dataset.csv").write_text("energy,force\n0.1,0.2\n", encoding="utf-8")

    # Add excluded directories and their contents (.git, .venv, __pycache__, scratch, build, dist)
    excluded_dirs = [
        repo_dir / ".git" / "hooks",
        repo_dir / ".venv" / "lib",
        repo_dir / "venv" / "lib",
        repo_dir / "__pycache__",
        repo_dir / ".pytest_cache",
        repo_dir / ".mypy_cache",
        repo_dir / ".ruff_cache",
        repo_dir / ".trash",
        repo_dir / "build" / "lib",
        repo_dir / "dist",
        repo_dir / "scratch" / "temp",
        repo_dir / "cochem_base.egg-info",
        repo_dir / "custom_temp",
    ]

    for edir in excluded_dirs:
        edir.mkdir(parents=True, exist_ok=True)
        (edir / "ignored_module.py").write_text(
            'print("Should be ignored")\n', encoding="utf-8"
        )

    # Also add .pyc compiled files inside tracked packages
    (pkg_core / "engine.cpython-313.pyc").write_bytes(b"\x00\x01\x02\x03\x04")

    # Compute repository source hash with default + custom exclusions
    repo_hash, file_hashes = compute_repository_source_hash(
        repo_dir=repo_dir, exclude_dirs=["custom_temp"]
    )

    # 1. Sorted POSIX relative path verification
    expected_tracked_files = [
        "cochem_base/__init__.py",
        "cochem_base/core/__init__.py",
        "cochem_base/core/engine.py",
        "cochem_base/utils/helpers.py",
        "scripts/entrypoint.py",
    ]

    assert sorted(file_hashes.keys()) == expected_tracked_files
    for key in file_hashes:
        assert "\\" not in key, f"Path key '{key}' must use POSIX slashes (/)"
        assert len(file_hashes[key]) == 64

    # 2. Excluded directories must NOT be in file_hashes
    for key in file_hashes:
        assert not key.startswith(".git")
        assert not key.startswith(".venv")
        assert not key.startswith("venv")
        assert not key.startswith("__pycache__")
        assert not key.startswith(".pytest_cache")
        assert not key.startswith(".mypy_cache")
        assert not key.startswith(".ruff_cache")
        assert not key.startswith(".trash")
        assert not key.startswith("build")
        assert not key.startswith("dist")
        assert not key.startswith("scratch")
        assert not key.startswith("custom_temp")
        assert not key.endswith(".pyc")
        assert not key.endswith(".md")
        assert not key.endswith(".json")

    # 3. Verify manual deterministic SHA-256 hash chaining
    manual_hasher = hashlib.sha256()
    for rel_posix in sorted(expected_tracked_files):
        f_hash = compute_file_sha256(repo_dir / rel_posix, normalize_newlines=True)
        assert file_hashes[rel_posix] == f_hash
        manual_hasher.update(f"{rel_posix}:{f_hash}\n".encode())

    expected_master_hash = manual_hasher.hexdigest()
    assert repo_hash == expected_master_hash
    assert len(repo_hash) == 64


# =============================================================================
# 4. Topological Source Lock Record Generation and Persistence Tests
# =============================================================================


def test_generate_topological_source_lock(tmp_path: Path) -> None:
    """Validates TopologicalLockRecord creation, disk JSON serialization, and round-trip deserialization."""
    repo_dir = tmp_path / "lock_test_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    (repo_dir / "mod_alpha.py").write_text("ALPHA = 1.0\n", encoding="utf-8")
    (repo_dir / "mod_beta.py").write_text("BETA = 2.0\n", encoding="utf-8")

    lock_output_file = tmp_path / "locks" / "topological_source_lock.json"

    # 1. Creation of TopologicalLockRecord
    lock_record = generate_topological_source_lock(
        repo_dir=repo_dir, output_path=lock_output_file
    )

    assert isinstance(lock_record, TopologicalLockRecord)
    assert lock_record.file_count == 2
    assert "mod_alpha.py" in lock_record.file_hashes
    assert "mod_beta.py" in lock_record.file_hashes
    assert len(lock_record.repository_sha256) == 64
    assert isinstance(lock_record.generated_at, float)

    # 2. Disk JSON serialization and verification
    assert lock_output_file.is_file()
    raw_json_str = lock_output_file.read_text(encoding="utf-8")
    lock_dict = json.loads(raw_json_str)

    assert lock_dict["repository_sha256"] == lock_record.repository_sha256
    assert lock_dict["file_count"] == 2
    assert lock_dict["file_hashes"] == lock_record.file_hashes
    assert lock_dict["generated_at"] == lock_record.generated_at

    # 3. Deserialization from dictionary
    deserialized_record = TopologicalLockRecord(
        repository_sha256=lock_dict["repository_sha256"],
        file_count=lock_dict["file_count"],
        file_hashes=lock_dict["file_hashes"],
        generated_at=lock_dict["generated_at"],
        metadata=lock_dict.get("metadata", {}),
    )

    assert deserialized_record.to_dict() == lock_record.to_dict()


# =============================================================================
# 5. Real-Time Source Code Integrity Verification Tests
# =============================================================================


def test_verify_source_code_integrity(tmp_path: Path) -> None:
    """Validates detection of clean states, tampered files, deleted files, and untracked additions."""
    repo_dir = tmp_path / "integrity_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    file_1 = repo_dir / "calc_hf.py"
    file_2 = repo_dir / "calc_dft.py"
    file_3 = repo_dir / "calc_ccsd.py"

    file_1.write_text("def run_hf(): return 'hf_energy'\n", encoding="utf-8")
    file_2.write_text("def run_dft(): return 'dft_energy'\n", encoding="utf-8")
    file_3.write_text("def run_ccsd(): return 'ccsd_energy'\n", encoding="utf-8")

    lock_record = generate_topological_source_lock(repo_dir=repo_dir)

    # 1. Unmodified repository verification
    is_valid, discrepancies = verify_source_code_integrity(
        repo_dir=repo_dir,
        lock_record=lock_record,
        expected_hash=lock_record.repository_sha256,
    )
    assert is_valid is True
    assert discrepancies == []

    # 2. Detection of tampered (modified) .py files
    original_hf_content = file_1.read_text(encoding="utf-8")
    file_1.write_text(
        "def run_hf(): return 'tampered_malicious_code'\n", encoding="utf-8"
    )

    is_valid_tampered, discrepancies_tampered = verify_source_code_integrity(
        repo_dir=repo_dir, lock_record=lock_record
    )
    assert is_valid_tampered is False
    assert any("Tampered source file: calc_hf.py" in d for d in discrepancies_tampered)

    # Revert modification
    file_1.write_text(original_hf_content, encoding="utf-8")
    is_valid_restored, _ = verify_source_code_integrity(
        repo_dir=repo_dir, lock_record=lock_record
    )
    assert is_valid_restored is True

    # 3. Detection of deleted .py files
    file_3_backup = file_3.read_text(encoding="utf-8")
    file_3.unlink()

    is_valid_deleted, discrepancies_deleted = verify_source_code_integrity(
        repo_dir=repo_dir, lock_record=lock_record
    )
    assert is_valid_deleted is False
    assert any("Missing source file: calc_ccsd.py" in d for d in discrepancies_deleted)

    # Recreate deleted file
    file_3.write_text(file_3_backup, encoding="utf-8")
    is_valid_recreated, _ = verify_source_code_integrity(
        repo_dir=repo_dir, lock_record=lock_record
    )
    assert is_valid_recreated is True

    # 4. Detection of newly added untracked .py files
    injected_file = repo_dir / "backdoor.py"
    injected_file.write_text(
        "print('Unauthorized untracked script')\n", encoding="utf-8"
    )

    is_valid_added, discrepancies_added = verify_source_code_integrity(
        repo_dir=repo_dir, lock_record=lock_record
    )
    assert is_valid_added is False
    assert any(
        "Untracked/added source file: backdoor.py" in d for d in discrepancies_added
    )

    # Clean up untracked file
    injected_file.unlink()
    is_valid_cleaned, _ = verify_source_code_integrity(
        repo_dir=repo_dir, lock_record=lock_record
    )
    assert is_valid_cleaned is True

    # 5. Detection of master hash mismatch
    is_valid_bad_hash, discrepancies_bad_hash = verify_source_code_integrity(
        repo_dir=repo_dir,
        expected_hash="0000000000000000000000000000000000000000000000000000000000000000",
    )
    assert is_valid_bad_hash is False
    assert any("Repository master hash mismatch" in d for d in discrepancies_bad_hash)


# =============================================================================
# 6. Topological Lock Assertion and Error Enforcement Tests
# =============================================================================


def test_assert_topological_lock(tmp_path: Path) -> None:
    """Validates assert_topological_lock passing on clean repo and raising SourceIntegrityError on tamper."""
    repo_dir = tmp_path / "assertion_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    module_file = repo_dir / "pipeline.py"
    module_file.write_text("def run(): pass\n", encoding="utf-8")

    lock_record = generate_topological_source_lock(repo_dir=repo_dir)

    # 1. Clean repo validation (must execute cleanly without raising)
    assert_topological_lock(
        repo_dir=repo_dir,
        lock_record=lock_record,
        expected_hash=lock_record.repository_sha256,
    )

    # 2. Tampered file validation (must raise SourceIntegrityError with details)
    module_file.write_text(
        "def run(): raise RuntimeError('Injected defect')\n", encoding="utf-8"
    )

    with pytest.raises(SourceIntegrityError) as exc_info:
        assert_topological_lock(repo_dir=repo_dir, lock_record=lock_record)

    error_message = str(exc_info.value)
    assert "[TopologicalLock] Integrity check failed with 1 violations" in error_message
    assert "Tampered source file: pipeline.py" in error_message


# =============================================================================
# 7. Dual-Layout Import and Symbol Parity Tests
# =============================================================================


def test_dual_layout_imports() -> None:
    """Confirms identical symbol export and object identity across standard and src layouts."""
    expected_symbols = [
        "EnvironmentHashRecord",
        "TopologicalLockRecord",
        "SourceIntegrityError",
        "compute_file_sha256",
        "hash_environment",
        "compute_repository_source_hash",
        "generate_topological_source_lock",
        "verify_source_code_integrity",
        "assert_topological_lock",
    ]

    for symbol in expected_symbols:
        assert hasattr(direct_hashing, symbol), (
            f"direct layout missing symbol '{symbol}'"
        )
        assert hasattr(src_hashing, symbol), f"src layout missing symbol '{symbol}'"

        direct_obj = getattr(direct_hashing, symbol)
        src_obj = getattr(src_hashing, symbol)
        assert direct_obj is src_obj, f"Symbol identity mismatch for '{symbol}'"

    # Verify __all__ declarations match across direct and mirror layouts
    assert hasattr(direct_hashing, "__all__")
    assert sorted(direct_hashing.__all__) == sorted(expected_symbols)
    assert hasattr(src_hashing, "__all__")
    assert sorted(src_hashing.__all__) == sorted(expected_symbols)


# =============================================================================
# 8. Record Serialization, Deserialization and Edge Case Tests
# =============================================================================


def test_environment_hash_record_from_dict() -> None:
    """Validates EnvironmentHashRecord round-trip from_dict conversion."""
    rec = hash_environment(
        tracked_packages=["pytest"],
        tracked_engines={"orca": "5.0.4", "xtb": "6.6.1"},
    )
    rec_dict = rec.to_dict()
    restored = EnvironmentHashRecord.from_dict(rec_dict)

    assert restored.sha256_hash == rec.sha256_hash
    assert restored.python_version == rec.python_version
    assert restored.python_implementation == rec.python_implementation
    assert restored.os_system == rec.os_system
    assert restored.os_release == rec.os_release
    assert restored.cpu_count == rec.cpu_count
    assert restored.total_ram_bytes == rec.total_ram_bytes
    assert restored.core_dependencies == rec.core_dependencies
    assert restored.engine_versions == {"orca": "5.0.4", "xtb": "6.6.1"}
    assert restored.metadata == rec.metadata
    assert restored.to_dict() == rec_dict


def test_topological_lock_record_from_json_and_from_dict(tmp_path: Path) -> None:
    """Validates TopologicalLockRecord from_dict, from_json file path, and from_json raw string."""
    repo_dir = tmp_path / "repo_from_json"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "mod_x.py").write_text("X = 100\n", encoding="utf-8")

    lock_file = tmp_path / "topological_lock.json"
    rec = generate_topological_source_lock(repo_dir=repo_dir, output_path=lock_file)

    # 1. from_dict
    from_dict_rec = TopologicalLockRecord.from_dict(rec.to_dict())
    assert from_dict_rec.repository_sha256 == rec.repository_sha256
    assert from_dict_rec.file_hashes == rec.file_hashes

    # 2. from_json via Path
    from_path_rec = TopologicalLockRecord.from_json(lock_file)
    assert from_path_rec.repository_sha256 == rec.repository_sha256
    assert from_path_rec.file_hashes == rec.file_hashes

    # 3. from_json via JSON string
    json_str = json.dumps(rec.to_dict())
    from_str_rec = TopologicalLockRecord.from_json(json_str)
    assert from_str_rec.repository_sha256 == rec.repository_sha256
    assert from_str_rec.file_hashes == rec.file_hashes


def test_verify_integrity_value_error(tmp_path: Path) -> None:
    """Validates ValueError is raised when neither expected_hash nor lock_record is supplied."""
    with pytest.raises(
        ValueError,
        match="Integrity verification requires either 'expected_hash' or 'lock_record'",
    ):
        verify_source_code_integrity(repo_dir=tmp_path)


def test_verify_integrity_tampered_manifest_master_hash(tmp_path: Path) -> None:
    """Validates discrepancy reported when lock_record has tampered repository_sha256 but valid file_hashes."""
    repo_dir = tmp_path / "repo_tamper_manifest"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "clean.py").write_text("CLEAN = True\n", encoding="utf-8")

    rec = generate_topological_source_lock(repo_dir=repo_dir)
    tampered_rec = TopologicalLockRecord(
        repository_sha256="deadbeef" * 8,
        file_count=rec.file_count,
        file_hashes=rec.file_hashes,
        generated_at=rec.generated_at,
    )

    is_valid, issues = verify_source_code_integrity(
        repo_dir=repo_dir, lock_record=tampered_rec
    )
    assert is_valid is False
    assert any(
        "Repository master hash mismatch: expected 'deadbeefdeadbeef" in iss
        for iss in issues
    )


def test_default_repo_dir_resolution() -> None:
    """Validates that compute_repository_source_hash, generate_topological_source_lock, and verify_source_code_integrity resolve real repo root when repo_dir=None."""
    repo_hash, file_hashes = compute_repository_source_hash()
    assert len(repo_hash) == 64
    assert len(file_hashes) > 0

    lock_record = generate_topological_source_lock()
    assert lock_record.repository_sha256 == repo_hash
    assert lock_record.file_count == len(file_hashes)

    is_valid, issues = verify_source_code_integrity(lock_record=lock_record)
    assert is_valid is True
    assert issues == []


def test_tracked_engines_registered_and_unregistered() -> None:
    """Validates tracked_engines with installed Python packages and unregistered standalone engines."""
    record = hash_environment(tracked_engines=["pytest", "non_existent_engine_abc_999"])
    assert record.engine_versions["pytest"] == importlib.metadata.version("pytest")
    assert record.engine_versions["non_existent_engine_abc_999"] == "unregistered"
    assert len(record.sha256_hash) == 64


def test_compute_repository_source_hash_nonexistent_dir(tmp_path: Path) -> None:
    """Validates compute_repository_source_hash raises FileNotFoundError for non-existent directory."""
    non_existent = tmp_path / "does_not_exist_repo_dir_12345"
    with pytest.raises(FileNotFoundError, match="Repository directory not found"):
        compute_repository_source_hash(repo_dir=non_existent)


def test_topological_lock_record_from_json_nonexistent_file(tmp_path: Path) -> None:
    """Validates TopologicalLockRecord.from_json raises FileNotFoundError for non-existent file."""
    non_existent = tmp_path / "missing_lock.json"
    with pytest.raises(FileNotFoundError, match="Lock manifest file not found"):
        TopologicalLockRecord.from_json(non_existent)

    with pytest.raises(FileNotFoundError, match="Lock manifest file not found"):
        TopologicalLockRecord.from_json(str(non_existent))


def test_topological_lock_record_from_json_invalid_type() -> None:
    """Validates TopologicalLockRecord.from_json raises TypeError when given invalid argument type."""
    with pytest.raises(TypeError, match="Expected str or Path for json_str_or_path"):
        TopologicalLockRecord.from_json(12345)  # type: ignore[arg-type]


def test_environment_record_object_airgap_sanitization() -> None:
    """Validates that EnvironmentHashRecord object fields and to_dict are sanitized of paths with spaces and drives."""
    record = hash_environment(
        exclude_paths=True,
        tracked_engines={
            "orca": r"C:\Program Files\ORCA 5.0\orca.exe",
            "xtb": "/home/user with space/bin/xtb",
        },
    )
    assert record.engine_versions["orca"] == "[SANITIZED_PATH]"
    assert record.engine_versions["xtb"] == "[SANITIZED_PATH]"

    dumped = record.to_dict()
    assert dumped["engine_versions"]["orca"] == "[SANITIZED_PATH]"
    assert dumped["engine_versions"]["xtb"] == "[SANITIZED_PATH]"
    assert "C:\\" not in json.dumps(dumped)
    assert "/home/" not in json.dumps(dumped)
