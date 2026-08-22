"""Unit and Integration Tests for Cryptographic Provenance and Hashing.

Validates:
- Strict integrity compliance (real hashing on physical files and environment metrics).
- SHA-256 calculation with deterministic line-ending normalization.
- Environment fingerprinting (CPU, RAM, Python version, OS kernel, dependencies).
- Strict exclusion of local paths from environment fingerprints.
- Repository source code topological locking and hash calculation.
- Source code tamper detection (raising SourceIntegrityError on modifications).
"""

import json
from pathlib import Path

import pytest

from cochem_base.provenance.hashing import (
    SourceIntegrityError,
    assert_topological_lock,
    compute_file_sha256,
    generate_topological_source_lock,
    hash_environment,
    verify_source_code_integrity,
)


def test_compute_file_sha256_normalization(tmp_path: Path) -> None:
    """Verifies that compute_file_sha256 yields identical hashes across CRLF and LF."""
    f_crlf = tmp_path / "test_crlf.py"
    f_lf = tmp_path / "test_lf.py"

    content = "def calculate_energy():\n    return 42.0\n"
    f_lf.write_bytes(content.encode("utf-8"))
    f_crlf.write_bytes(content.replace("\n", "\r\n").encode("utf-8"))

    hash_lf = compute_file_sha256(f_lf, normalize_newlines=True)
    hash_crlf = compute_file_sha256(f_crlf, normalize_newlines=True)

    assert hash_lf == hash_crlf
    assert len(hash_lf) == 64


def test_hash_environment_deterministic() -> None:
    """Verifies that environment hashing is deterministic and contains valid hardware/OS metrics."""
    record1 = hash_environment()
    record2 = hash_environment()

    assert record1.sha256_hash == record2.sha256_hash
    assert len(record1.sha256_hash) == 64
    assert record1.cpu_count >= 1
    assert record1.python_version != ""
    assert record1.os_system != ""

    # Ensure no drive letters or local paths leaked into the canonical payload
    record_dict = record1.to_dict()
    serialized = json.dumps(record_dict)
    assert ":\\" not in serialized, (
        "Absolute Windows drive path detected in environment record"
    )
    assert "/home/" not in serialized, (
        "Absolute POSIX home path detected in environment record"
    )


def test_topological_source_lock_lifecycle(tmp_path: Path) -> None:
    """Tests the full generation, verification, and tamper-detection lifecycle of source locking."""
    repo_dir = tmp_path / "isolated_repo"
    repo_dir.mkdir()

    file_a = repo_dir / "module_a.py"
    file_b = repo_dir / "module_b.py"
    file_a.write_text("def func_a(): pass\n", encoding="utf-8")
    file_b.write_text("def func_b(): pass\n", encoding="utf-8")

    # Generate initial lock
    lock_file = tmp_path / "topological_lock.json"
    lock_record = generate_topological_source_lock(
        repo_dir=repo_dir, output_path=lock_file
    )

    assert lock_file.exists()
    assert lock_record.file_count == 2
    assert "module_a.py" in lock_record.file_hashes
    assert "module_b.py" in lock_record.file_hashes

    # Verification should pass initially
    is_valid, issues = verify_source_code_integrity(
        repo_dir=repo_dir, lock_record=lock_record
    )
    assert is_valid is True
    assert len(issues) == 0

    # Tamper with file_a
    file_a.write_text("def func_a(): return 'tampered'\n", encoding="utf-8")

    is_valid_tampered, issues_tampered = verify_source_code_integrity(
        repo_dir=repo_dir, lock_record=lock_record
    )
    assert is_valid_tampered is False
    assert any("Tampered source file: module_a.py" in iss for iss in issues_tampered)

    # assert_topological_lock should raise SourceIntegrityError
    with pytest.raises(SourceIntegrityError):
        assert_topological_lock(repo_dir=repo_dir, lock_record=lock_record)
