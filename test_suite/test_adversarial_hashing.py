"""Adversarial Stress Testing and Chaos Verification Suite for Cryptographic Provenance.

Validates:
- Topological lock tamper detection on bitwise mutations, file injection, file deletion, file rename, content swap.
- Excluded directory isolation (.git, .venv, __pycache__, build, dist, .egg-info, scratch).
- Zero false positives on bytecode (.pyc) and non-python files.
- CRLF vs LF vs CR vs Mixed newline normalization on source and config files.
- Binary mode fallback invariance on non-text files.
- Environment fingerprint reproducibility and path leakage sanitization across multiple formats.
- Exception reporting accuracy with multi-violation payloads.
- Directory permutation invariance and POSIX relative path stability.
- Special character handling in filenames.
- Empty repository handling.
- Expected master hash vs lock record verification.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cochem_base.provenance.hashing import (
    SourceIntegrityError,
    TopologicalLockRecord,
    assert_topological_lock,
    compute_file_sha256,
    compute_repository_source_hash,
    generate_topological_source_lock,
    hash_environment,
    verify_source_code_integrity,
)

# =========================================================================
# 1. Source Tamper & Mutation Attacks
# =========================================================================


def test_tamper_single_space_mutation(tmp_path: Path) -> None:
    """Adversarial Attack: Insert a single space into a Python file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    f1 = repo / "core.py"
    f1.write_text("X = 1\n", encoding="utf-8")

    lock = generate_topological_source_lock(repo_dir=repo)
    assert verify_source_code_integrity(repo_dir=repo, lock_record=lock)[0] is True

    # Single space mutation
    f1.write_text("X =  1\n", encoding="utf-8")
    is_valid, issues = verify_source_code_integrity(repo_dir=repo, lock_record=lock)
    assert is_valid is False
    assert len(issues) == 1
    assert "Tampered source file: core.py" in issues[0]

    with pytest.raises(SourceIntegrityError) as exc_info:
        assert_topological_lock(repo_dir=repo, lock_record=lock)
    assert "core.py" in str(exc_info.value)


def test_tamper_file_injection_attack(tmp_path: Path) -> None:
    """Adversarial Attack: Inject unauthorized .py files into root and nested directories."""
    repo = tmp_path / "repo"
    sub = repo / "nested" / "deep"
    sub.mkdir(parents=True)
    (repo / "app.py").write_text("a = 10\n", encoding="utf-8")
    (sub / "mod.py").write_text("b = 20\n", encoding="utf-8")

    lock = generate_topological_source_lock(repo_dir=repo)
    assert lock.file_count == 2
    assert "nested/deep/mod.py" in lock.file_hashes

    # Inject unauthorized file in nested directory
    rogue = sub / "backdoor.py"
    rogue.write_text("import os; os.system('echo compromised')\n", encoding="utf-8")

    is_valid, issues = verify_source_code_integrity(repo_dir=repo, lock_record=lock)
    assert is_valid is False
    assert any(
        "Untracked/added source file: nested/deep/backdoor.py" in iss for iss in issues
    )

    with pytest.raises(SourceIntegrityError):
        assert_topological_lock(repo_dir=repo, lock_record=lock)


def test_tamper_file_deletion_attack(tmp_path: Path) -> None:
    """Adversarial Attack: Delete a core source file post-lock."""
    repo = tmp_path / "repo"
    repo.mkdir()
    f1 = repo / "alpha.py"
    f2 = repo / "beta.py"
    f1.write_text("ALPHA = True\n", encoding="utf-8")
    f2.write_text("BETA = False\n", encoding="utf-8")

    lock = generate_topological_source_lock(repo_dir=repo)
    assert lock.file_count == 2

    # Delete beta.py
    f2.unlink()

    is_valid, issues = verify_source_code_integrity(repo_dir=repo, lock_record=lock)
    assert is_valid is False
    assert any("Missing source file: beta.py" in iss for iss in issues)

    with pytest.raises(SourceIntegrityError):
        assert_topological_lock(repo_dir=repo, lock_record=lock)


def test_tamper_file_rename_attack(tmp_path: Path) -> None:
    """Adversarial Attack: Rename a file while keeping identical content."""
    repo = tmp_path / "repo"
    repo.mkdir()
    f_orig = repo / "original.py"
    content = "SECRET_KEY = 'unchanged_content'\n"
    f_orig.write_text(content, encoding="utf-8")

    lock = generate_topological_source_lock(repo_dir=repo)

    # Rename original.py -> renamed.py
    f_orig.unlink()
    (repo / "renamed.py").write_text(content, encoding="utf-8")

    is_valid, issues = verify_source_code_integrity(repo_dir=repo, lock_record=lock)
    assert is_valid is False
    assert any("Missing source file: original.py" in iss for iss in issues)
    assert any("Untracked/added source file: renamed.py" in iss for iss in issues)

    with pytest.raises(SourceIntegrityError):
        assert_topological_lock(repo_dir=repo, lock_record=lock)


def test_tamper_content_swap_attack(tmp_path: Path) -> None:
    """Adversarial Attack: Swap contents between two existing files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    f1 = repo / "file1.py"
    f2 = repo / "file2.py"
    f1.write_text("DATA = 'A'\n", encoding="utf-8")
    f2.write_text("DATA = 'B'\n", encoding="utf-8")

    lock = generate_topological_source_lock(repo_dir=repo)

    # Swap contents
    f1.write_text("DATA = 'B'\n", encoding="utf-8")
    f2.write_text("DATA = 'A'\n", encoding="utf-8")

    is_valid, issues = verify_source_code_integrity(repo_dir=repo, lock_record=lock)
    assert is_valid is False
    assert len(issues) == 2
    assert any("Tampered source file: file1.py" in iss for iss in issues)
    assert any("Tampered source file: file2.py" in iss for iss in issues)


def test_multi_violation_comprehensive_reporting(tmp_path: Path) -> None:
    """Adversarial Attack: Simultaneous modified, added, and deleted files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    f_mod = repo / "modify_me.py"
    f_del = repo / "delete_me.py"
    f_keep = repo / "keep_me.py"
    f_mod.write_text("MOD = 1\n", encoding="utf-8")
    f_del.write_text("DEL = 1\n", encoding="utf-8")
    f_keep.write_text("KEEP = 1\n", encoding="utf-8")

    lock = generate_topological_source_lock(repo_dir=repo)
    expected_hash = lock.repository_sha256

    # Execute multi-pronged attack
    f_mod.write_text("MOD = 999\n", encoding="utf-8")
    f_del.unlink()
    (repo / "new_rogue.py").write_text("ROGUE = 1\n", encoding="utf-8")

    is_valid, issues = verify_source_code_integrity(
        repo_dir=repo, expected_hash=expected_hash, lock_record=lock
    )
    assert is_valid is False
    assert len(issues) == 4  # Master hash mismatch + 1 modified + 1 missing + 1 added
    assert any("Repository master hash mismatch" in iss for iss in issues)
    assert any("Tampered source file: modify_me.py" in iss for iss in issues)
    assert any("Missing source file: delete_me.py" in iss for iss in issues)
    assert any("Untracked/added source file: new_rogue.py" in iss for iss in issues)


# =========================================================================
# 2. Exclusion Isolation & Non-Python Invariance
# =========================================================================


def test_excluded_directories_and_bytecode_invariance(tmp_path: Path) -> None:
    """Verify that .git, .venv, __pycache__, build, dist, .egg-info, scratch and .pyc are ignored."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "valid_module.py").write_text("def run(): pass\n", encoding="utf-8")

    # Lock before noise
    hash_initial, files_initial = compute_repository_source_hash(repo)

    # Add noise in default excluded directories
    git_dir = repo / ".git" / "hooks"
    git_dir.mkdir(parents=True)
    (git_dir / "pre-commit.py").write_text("# git hook script\n", encoding="utf-8")

    venv_dir = repo / ".venv" / "lib" / "site-packages"
    venv_dir.mkdir(parents=True)
    (venv_dir / "foreign_pkg.py").write_text("# venv library\n", encoding="utf-8")

    pycache_dir = repo / "__pycache__"
    pycache_dir.mkdir(parents=True)
    (pycache_dir / "valid_module.cpython-313.py").write_text(
        "synthetic bytecode\n", encoding="utf-8"
    )

    scratch_dir = repo / "scratch"
    scratch_dir.mkdir(parents=True)
    (scratch_dir / "temp_script.py").write_text("scratch = True\n", encoding="utf-8")

    build_dir = repo / "build" / "lib"
    build_dir.mkdir(parents=True)
    (build_dir / "built_pkg.py").write_text("build = True\n", encoding="utf-8")

    egg_dir = repo / "cochem_base.egg-info"
    egg_dir.mkdir(parents=True)
    (egg_dir / "entry_points.py").write_text("egg = True\n", encoding="utf-8")

    # Add .pyc file in valid directory
    (repo / "valid_module.pyc").write_bytes(b"\x00\x01\x02\x03compiled")

    # Add non-python files
    (repo / "README.md").write_text("# Readme\n", encoding="utf-8")
    (repo / "data.json").write_text("{}", encoding="utf-8")
    (repo / "native.dll").write_bytes(b"MZBINARY")

    hash_after_noise, files_after_noise = compute_repository_source_hash(repo)

    assert hash_initial == hash_after_noise
    assert files_initial == files_after_noise
    assert len(files_after_noise) == 1
    assert "valid_module.py" in files_after_noise


def test_custom_exclude_dirs(tmp_path: Path) -> None:
    """Verify custom exclude_dirs parameter."""
    repo = tmp_path / "repo"
    custom_dir = repo / "custom_temp"
    custom_dir.mkdir(parents=True)
    (repo / "main.py").write_text("X = 1\n", encoding="utf-8")
    (custom_dir / "temp.py").write_text("TEMP = True\n", encoding="utf-8")

    _hash_with_custom, files_with_custom = compute_repository_source_hash(
        repo, exclude_dirs=["custom_temp"]
    )
    assert "custom_temp/temp.py" not in files_with_custom
    assert len(files_with_custom) == 1
    assert "main.py" in files_with_custom


# =========================================================================
# 3. Newline, Encoding & Format Edge Cases
# =========================================================================


@pytest.mark.parametrize(
    "ending_name,content_bytes",
    [
        ("LF", b"def test():\n    return 100\n"),
        ("CRLF", b"def test():\r\n    return 100\r\n"),
        ("CR", b"def test():\r    return 100\r"),
        ("Mixed", b"def test():\r\n    return 100\n"),
    ],
)
def test_all_newline_variations_invariant(
    tmp_path: Path, ending_name: str, content_bytes: bytes
) -> None:
    """Verify that LF, CRLF, CR, and mixed line endings generate identical SHA-256."""
    p = tmp_path / f"test_{ending_name}.py"
    p.write_bytes(content_bytes)

    # Reference canonical hash
    canonical_bytes = b"def test():\n    return 100\n"
    ref_hash = hashlib.sha256(canonical_bytes).hexdigest()

    computed_hash = compute_file_sha256(p, normalize_newlines=True)
    assert computed_hash == ref_hash


@pytest.mark.parametrize(
    "ext", [".json", ".yaml", ".yml", ".toml", ".md", ".txt", ".bib"]
)
def test_config_extensions_newline_normalization(tmp_path: Path, ext: str) -> None:
    """Verify that configuration and documentation formats also normalize newlines."""
    f_crlf = tmp_path / f"config{ext}"
    f_lf = tmp_path / f"config_lf{ext}"

    content = "key: value\nitem: 123\n"
    f_lf.write_bytes(content.encode("utf-8"))
    f_crlf.write_bytes(content.replace("\n", "\r\n").encode("utf-8"))

    h_crlf = compute_file_sha256(f_crlf, normalize_newlines=True)
    h_lf = compute_file_sha256(f_lf, normalize_newlines=True)
    assert h_crlf == h_lf


def test_binary_files_preserve_bytes(tmp_path: Path) -> None:
    """Verify that binary files (.bin, .so, etc.) do not have their newlines modified."""
    bin_file = tmp_path / "model.bin"
    raw_data = b"HEADER\r\n\x00\xffPAYLOAD\r\nFOOTER"
    bin_file.write_bytes(raw_data)

    expected_hash = hashlib.sha256(raw_data).hexdigest()
    computed_hash = compute_file_sha256(bin_file, normalize_newlines=True)

    assert computed_hash == expected_hash


def test_empty_file_hashing(tmp_path: Path) -> None:
    """Verify 0-byte file returns standard SHA-256 of empty string."""
    empty_file = tmp_path / "empty.py"
    empty_file.write_bytes(b"")

    empty_sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert compute_file_sha256(empty_file) == empty_sha256


def test_nonexistent_file_raises_error(tmp_path: Path) -> None:
    """Verify FileNotFoundError on non-existent path."""
    with pytest.raises(FileNotFoundError):
        compute_file_sha256(tmp_path / "does_not_exist.py")


def test_invalid_utf8_recovery(tmp_path: Path) -> None:
    """Verify non-UTF8 source files degrade gracefully and deterministically."""
    invalid_file = tmp_path / "corrupt.py"
    invalid_file.write_bytes(b"x = '\x80\x81\x82'\r\n")

    hash1 = compute_file_sha256(invalid_file, normalize_newlines=True)
    hash2 = compute_file_sha256(invalid_file, normalize_newlines=True)

    assert hash1 == hash2
    assert len(hash1) == 64


# =========================================================================
# 4. Environment Fingerprint & Path Leakage Attacks
# =========================================================================


def test_environment_hash_50_iterations_reproducibility() -> None:
    """Execute 50 consecutive runs of hash_environment to test strict stability."""
    hashes = [hash_environment().sha256_hash for _ in range(50)]
    assert len(set(hashes)) == 1, (
        "Environment hashing produced fluctuating hashes across runs"
    )


def test_environment_path_sanitization_defense() -> None:
    """Adversarial Attack: Inject paths into tracked packages and test sanitization."""
    synthetic_pkgs = ["cochem-base", "numpy"]
    rec = hash_environment(exclude_paths=True, tracked_packages=synthetic_pkgs)

    rec_dict = rec.to_dict()
    serialized = json.dumps(rec_dict)

    # Assert no local path signatures
    assert "C:\\" not in serialized
    assert "D:\\" not in serialized
    assert "/home/" not in serialized
    assert "/Users/" not in serialized


def test_environment_missing_package_handling() -> None:
    """Verify that non-existent packages are gracefully marked 'not-installed' without crashing."""
    rec = hash_environment(tracked_packages=["non_existent_super_package_xyz_123"])
    assert (
        rec.core_dependencies["non_existent_super_package_xyz_123"] == "not-installed"
    )
    assert len(rec.sha256_hash) == 64


def test_environment_custom_tracked_packages_ordering() -> None:
    """Verify that order of tracked_packages argument does not alter the output hash."""
    rec1 = hash_environment(tracked_packages=["pytest", "numpy", "scipy"])
    rec2 = hash_environment(tracked_packages=["scipy", "pytest", "numpy"])
    assert rec1.sha256_hash == rec2.sha256_hash


# =========================================================================
# 5. Topological Determinism & Directory Ordering
# =========================================================================


def test_directory_traversal_order_invariance(tmp_path: Path) -> None:
    """Verify that creation order of files does not alter repository SHA-256."""
    repo1 = tmp_path / "repo1"
    repo2 = tmp_path / "repo2"
    repo1.mkdir()
    repo2.mkdir()

    # Repo 1: Create z.py first, then a.py, then m.py
    (repo1 / "z.py").write_text("Z = 1\n", encoding="utf-8")
    (repo1 / "a.py").write_text("A = 1\n", encoding="utf-8")
    (repo1 / "m.py").write_text("M = 1\n", encoding="utf-8")

    # Repo 2: Create a.py first, then m.py, then z.py
    (repo2 / "a.py").write_text("A = 1\n", encoding="utf-8")
    (repo2 / "m.py").write_text("M = 1\n", encoding="utf-8")
    (repo2 / "z.py").write_text("Z = 1\n", encoding="utf-8")

    hash1, files1 = compute_repository_source_hash(repo1)
    hash2, files2 = compute_repository_source_hash(repo2)

    assert hash1 == hash2
    assert list(files1.keys()) == ["a.py", "m.py", "z.py"]
    assert list(files2.keys()) == ["a.py", "m.py", "z.py"]


def test_deep_nested_posix_path_normalization(tmp_path: Path) -> None:
    """Verify that deeply nested directories use forward slashes (POSIX) even on Windows."""
    repo = tmp_path / "repo"
    deep_path = repo / "cochem_base" / "physics" / "rotational" / "spindata"
    deep_path.mkdir(parents=True)
    (deep_path / "constants.py").write_text(
        "HBAR = 1.054571817e-34\n", encoding="utf-8"
    )

    _, files = compute_repository_source_hash(repo)
    expected_rel_path = "cochem_base/physics/rotational/spindata/constants.py"

    assert expected_rel_path in files
    # Verify no backslashes in dictionary keys
    for k in files:
        assert "\\" not in k


def test_empty_repository_handling(tmp_path: Path) -> None:
    """Verify handling of empty repository with no python files."""
    repo = tmp_path / "empty_repo"
    repo.mkdir()

    repo_hash, file_hashes = compute_repository_source_hash(repo)
    assert file_hashes == {}
    assert len(repo_hash) == 64
    # SHA-256 of empty byte stream
    assert (
        repo_hash == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )

    lock = generate_topological_source_lock(repo_dir=repo)
    assert lock.file_count == 0
    is_valid, issues = verify_source_code_integrity(repo_dir=repo, lock_record=lock)
    assert is_valid is True
    assert len(issues) == 0


def test_filenames_with_special_characters(tmp_path: Path) -> None:
    """Verify handling of Python files with special characters."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "_private_mod.py").write_text("X = 1\n", encoding="utf-8")
    (repo / "mod-hyphen.py").write_text("Y = 2\n", encoding="utf-8")
    (repo / "mod@special.py").write_text("Z = 3\n", encoding="utf-8")

    lock = generate_topological_source_lock(repo_dir=repo)
    assert lock.file_count == 3
    is_valid, issues = verify_source_code_integrity(repo_dir=repo, lock_record=lock)
    assert is_valid is True
    assert len(issues) == 0


def test_tampered_lock_record_fields(tmp_path: Path) -> None:
    """Adversarial Attack: Tampering with fields inside the TopologicalLockRecord."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "mod.py").write_text("VAL = 42\n", encoding="utf-8")

    lock = generate_topological_source_lock(repo_dir=repo)

    # 1. Tamper lock record hash value
    corrupted_lock = TopologicalLockRecord(
        repository_sha256=lock.repository_sha256,
        file_count=lock.file_count,
        file_hashes={
            "mod.py": "0000000000000000000000000000000000000000000000000000000000000000"
        },
        generated_at=lock.generated_at,
    )

    is_valid, issues = verify_source_code_integrity(
        repo_dir=repo, lock_record=corrupted_lock
    )
    assert is_valid is False
    assert any("Tampered source file: mod.py" in iss for iss in issues)

    # 2. Tamper lock record with extra phantom file
    phantom_lock = TopologicalLockRecord(
        repository_sha256=lock.repository_sha256,
        file_count=2,
        file_hashes={
            "mod.py": lock.file_hashes["mod.py"],
            "phantom.py": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        },
        generated_at=lock.generated_at,
    )

    is_valid, issues = verify_source_code_integrity(
        repo_dir=repo, lock_record=phantom_lock
    )
    assert is_valid is False
    assert any("Missing source file: phantom.py" in iss for iss in issues)


def test_expected_master_hash_mismatch(tmp_path: Path) -> None:
    """Verify integrity check fails when expected master hash does not match current repository."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "core.py").write_text("VERSION = 1\n", encoding="utf-8")

    corrupted_expected_hash = "deadbeef" * 8

    is_valid, issues = verify_source_code_integrity(
        repo_dir=repo, expected_hash=corrupted_expected_hash
    )
    assert is_valid is False
    assert any("Repository master hash mismatch" in iss for iss in issues)

    with pytest.raises(SourceIntegrityError) as exc_info:
        assert_topological_lock(repo_dir=repo, expected_hash=corrupted_expected_hash)
    assert "Repository master hash mismatch" in str(exc_info.value)


def test_adversarial_nonexistent_repo_dir_attack(tmp_path: Path) -> None:
    """Adversarial Attack: Attempt to calculate hash on non-existent or invalid directory."""
    nonexistent = tmp_path / "phantom_repo_12345"
    with pytest.raises(FileNotFoundError):
        compute_repository_source_hash(repo_dir=nonexistent)

    file_as_repo = tmp_path / "not_a_dir.py"
    file_as_repo.write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        compute_repository_source_hash(repo_dir=file_as_repo)


def test_adversarial_path_leakage_spaces_and_unc_shares() -> None:
    """Adversarial Attack: Attempt to leak system paths with complex spaces and UNC network shares."""
    malicious_engines = {
        "orca": r"C:\Program Files (x86)\ORCA Quantum\orca 5.0.4.exe",
        "mrcc": r"\\cluster-headnode\scratch\users\bob\mrcc_binary",
        "cfour": "/Volumes/Quantum Storage/opt/cfour/bin/xcfour",
        "xtb": "/Users/alice wonderland/xtb_run",
    }
    rec = hash_environment(exclude_paths=True, tracked_engines=malicious_engines)
    dumped = json.dumps(rec.to_dict())

    # None of the private host paths must appear in the final serialization
    assert "Program Files" not in dumped
    assert "cluster-headnode" not in dumped
    assert "Quantum Storage" not in dumped
    assert "alice wonderland" not in dumped
    assert "C:\\" not in dumped
    assert "/Volumes/" not in dumped
    assert "/Users/" not in dumped
    assert rec.engine_versions["orca"] == "[SANITIZED_PATH]"
    assert rec.engine_versions["mrcc"] == "[SANITIZED_PATH]"
    assert rec.engine_versions["cfour"] == "[SANITIZED_PATH]"
    assert rec.engine_versions["xtb"] == "[SANITIZED_PATH]"


def test_adversarial_from_json_nonexistent_manifest(tmp_path: Path) -> None:
    """Adversarial Attack: Pass a nonexistent path or corrupted input to from_json."""
    missing = tmp_path / "non_existent_manifest.json"
    with pytest.raises(FileNotFoundError):
        TopologicalLockRecord.from_json(missing)
    with pytest.raises(FileNotFoundError):
        TopologicalLockRecord.from_json(str(missing))
    with pytest.raises(TypeError):
        TopologicalLockRecord.from_json(None)  # type: ignore[arg-type]
    with pytest.raises(json.JSONDecodeError):
        TopologicalLockRecord.from_json("{corrupted_json_payload: null}")
