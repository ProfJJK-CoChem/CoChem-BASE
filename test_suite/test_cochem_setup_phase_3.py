"""
Unit test suite for CoChem Setup Phase 3: Multi-Track Quantum Engine Discovery & Integrity Hashing.
Strict Zero-Mock Mandate: Real filesystem operations, live subprocess interrogations,
deterministic Pydantic V2 schema validations, real streaming SHA-256 chunked hashing,
real synthetic executable fixtures (Python / batch scripts), real atomic I/O, and real rollback mechanics.

SRS Document 2 Part 2 (Section 3.3) & Document 5 (Section 2.3) Compliant.
"""

from __future__ import annotations

import hashlib
import json
import platform
import stat
import sys
from pathlib import Path
from typing import Dict

import pytest

from orchestrator.cochem_setup_phase_3 import (
    BinaryEngineItem,
    ContainerAudit,
    DependencyManager,
    EngineStatus,
    EngineTrack,
    EngineTrackSummary,
    EnvironmentFingerprint,
    Phase3AuditReport,
    PhaseStatus,
    audit_all_engines,
    audit_container_sifs,
    audit_single_binary,
    compute_environment_fingerprint,
    compute_file_sha256,
    discover_binary_path,
    extract_semantic_version,
    interrogate_binary_version,
    main,
    resolve_binary_search_paths,
    resolve_p3_registry_path,
    run_phase_3_audit,
)

# =============================================================================
# 1. PYDANTIC V2 SCHEMA & ENUM VALIDATION TESTS
# =============================================================================


def test_phase_status_enum() -> None:
    """Verify PhaseStatus enum definitions and string representations."""
    assert PhaseStatus.PASSED.value == "PASSED"
    assert PhaseStatus.FAILED.value == "FAILED"
    assert PhaseStatus.DEGRADED.value == "DEGRADED"
    assert PhaseStatus("PASSED") is PhaseStatus.PASSED
    assert PhaseStatus("FAILED") is PhaseStatus.FAILED
    assert PhaseStatus("DEGRADED") is PhaseStatus.DEGRADED

    with pytest.raises(ValueError):
        PhaseStatus("INVALID_STATUS")


def test_engine_track_enum() -> None:
    """Verify EngineTrack enum definitions."""
    assert EngineTrack.ORCA.value == "ORCA"
    assert EngineTrack.CFOUR.value == "CFOUR"
    assert EngineTrack.XTB_CREST.value == "XTB_CREST"
    assert EngineTrack.PYSCF_GPU.value == "PYSCF_GPU"
    assert EngineTrack.CONTAINER_SIF.value == "CONTAINER_SIF"
    assert EngineTrack.GENERAL.value == "GENERAL"


def test_engine_status_enum() -> None:
    """Verify EngineStatus enum definitions."""
    assert EngineStatus.FOUND_VALID.value == "FOUND_VALID"
    assert EngineStatus.FOUND_UNVERIFIED.value == "FOUND_UNVERIFIED"
    assert EngineStatus.MISSING.value == "MISSING"
    assert EngineStatus.ERROR.value == "ERROR"
    assert EngineStatus.AIRGAP_VIOLATION.value == "AIRGAP_VIOLATION"


def test_binary_engine_item_model_valid() -> None:
    """Test BinaryEngineItem model serialization and round-trip validation."""
    item = BinaryEngineItem(
        name="orca",
        track=EngineTrack.ORCA,
        path="/opt/orca/orca",
        version="6.1.1",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        file_size_bytes=1048576,
        is_available=True,
        is_container=False,
        container_flags=[],
        error_detail=None,
        status=EngineStatus.FOUND_VALID,
    )
    assert item.name == "orca"
    assert item.track is EngineTrack.ORCA
    assert item.version == "6.1.1"
    assert item.is_available is True
    assert item.status is EngineStatus.FOUND_VALID

    dumped = item.model_dump()
    assert dumped["name"] == "orca"
    restored = BinaryEngineItem.model_validate(dumped)
    assert restored == item


def test_binary_engine_item_missing_defaults() -> None:
    """Test BinaryEngineItem default state for unavailable binaries."""
    item = BinaryEngineItem(
        name="xcfour",
        track=EngineTrack.CFOUR,
    )
    assert item.name == "xcfour"
    assert item.track is EngineTrack.CFOUR
    assert item.path is None
    assert item.version is None
    assert item.sha256_hash is None
    assert item.is_available is False
    assert item.status is EngineStatus.MISSING
    assert item.error_detail is None


def test_container_audit_model_valid() -> None:
    """Test ContainerAudit model serialization and validation."""
    sif_item = BinaryEngineItem(
        name="cochem_orca.sif",
        track=EngineTrack.CONTAINER_SIF,
        path="/opt/sif/cochem_orca.sif",
        version="6.1.1-sif",
        sha256_hash="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        file_size_bytes=2147483648,
        is_available=True,
        is_container=True,
        container_flags=["--net", "--network", "none"],
        status=EngineStatus.FOUND_VALID,
    )
    ca = ContainerAudit(
        runtime_name="apptainer",
        runtime_path="/usr/bin/apptainer",
        runtime_version="1.3.0",
        airgap_flags_valid=True,
        discovered_sifs=[sif_item],
    )
    assert ca.runtime_name == "apptainer"
    assert ca.airgap_flags_valid is True
    assert len(ca.discovered_sifs) == 1
    assert ca.discovered_sifs[0].is_container is True

    dumped = ca.model_dump()
    restored = ContainerAudit.model_validate(dumped)
    assert restored == ca


def test_environment_fingerprint_model() -> None:
    """Test EnvironmentFingerprint model initialization."""
    fp = EnvironmentFingerprint(
        composite_hash="11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
        component_count=5,
    )
    assert fp.component_count == 5
    assert len(fp.composite_hash) == 64
    assert "[D]" in fp.provenance


# =============================================================================
# 2. CRYPTOGRAPHIC STREAMING SHA-256 HASHING TESTS
# =============================================================================


def test_compute_file_sha256_real_file(tmp_path: Path) -> None:
    """Test compute_file_sha256 on a real generated file on disk."""
    test_file = tmp_path / "test_bin.dat"
    content = b"Quantum Chemistry Binary Data Payload 12345\n" * 1000
    test_file.write_bytes(content)

    expected_hash = hashlib.sha256(content).hexdigest()
    expected_size = len(content)

    sha256_hash, file_size, err = compute_file_sha256(test_file)
    assert err is None
    assert sha256_hash == expected_hash
    assert file_size == expected_size


def test_compute_file_sha256_empty_file(tmp_path: Path) -> None:
    """Test compute_file_sha256 on empty file returns standard empty SHA-256 hash."""
    empty_file = tmp_path / "empty.dat"
    empty_file.write_bytes(b"")

    empty_sha256 = hashlib.sha256(b"").hexdigest()
    sha256_hash, file_size, err = compute_file_sha256(empty_file)
    assert err is None
    assert sha256_hash == empty_sha256
    assert file_size == 0


def test_compute_file_sha256_nonexistent_file(tmp_path: Path) -> None:
    """Test compute_file_sha256 on nonexistent file gracefully returns error."""
    missing_file = tmp_path / "missing_file.exe"
    sha256_hash, file_size, err = compute_file_sha256(missing_file)
    assert sha256_hash is None
    assert file_size is None
    assert err is not None
    assert "not found" in err.lower() or "no such file" in err.lower()


def test_compute_file_sha256_directory(tmp_path: Path) -> None:
    """Test compute_file_sha256 on a directory path returns appropriate error."""
    test_dir = tmp_path / "somedir"
    test_dir.mkdir()
    sha256_hash, file_size, err = compute_file_sha256(test_dir)
    assert sha256_hash is None
    assert file_size is None
    assert err is not None
    assert "directory" in err.lower()


# =============================================================================
# 3. MULTI-TIER BINARY DISCOVERY TESTS
# =============================================================================


def test_resolve_binary_search_paths_with_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test Tier 1 search paths via environment variable overrides."""
    custom_bin_dir = tmp_path / "custom_orca_dir"
    custom_bin_dir.mkdir()
    custom_orca = custom_bin_dir / ("orca.exe" if platform.system() == "Windows" else "orca")
    custom_orca.write_bytes(b"synthetic_binary_payload")

    monkeypatch.setenv("COCHEM_ORCA_PATH", str(custom_orca))

    paths = resolve_binary_search_paths("orca")
    assert any(str(custom_orca) in str(p) or p == custom_orca for p in paths)


def test_discover_binary_path_found(tmp_path: Path) -> None:
    """Test discover_binary_path finds a real executable in custom paths."""
    bin_name = "test_xtb"
    exe_name = f"{bin_name}.exe" if platform.system() == "Windows" else bin_name
    real_exe = tmp_path / exe_name
    real_exe.write_bytes(b"test binary content")
    if platform.system() != "Windows":
        real_exe.chmod(real_exe.stat().st_mode | stat.S_IEXEC)

    found = discover_binary_path(bin_name, search_dirs=[tmp_path])
    assert found is not None
    assert found.resolve() == real_exe.resolve()


def test_discover_binary_path_missing(tmp_path: Path) -> None:
    """Test discover_binary_path returns None when binary does not exist."""
    found = discover_binary_path("completely_absent_binary_xyz_999", search_dirs=[tmp_path])
    assert found is None


# =============================================================================
# 4. SUBPROCESS VERSION INTERROGATION TESTS
# =============================================================================


def test_extract_semantic_version_patterns() -> None:
    """Test version regex extraction across supported quantum engine formats."""
    # ORCA formats
    assert extract_semantic_version("Program Version 6.1.1 -  RELEASE  -", "orca") == "6.1.1"
    assert extract_semantic_version("ORCA version 5.0.4, Release", "orca") == "5.0.4"
    assert extract_semantic_version("An Ab Initio, DFT and Semiempirical Electronic Structure Package\nVersion 6.1.0", "orca") == "6.1.0"

    # OpenMPI formats
    assert extract_semantic_version("mpirun (Open MPI) 4.1.6\nReport bugs...", "mpirun") == "4.1.6"
    assert extract_semantic_version("Open MPI: 5.0.2\nOpen RTE: 5.0.2", "openmpi") == "5.0.2"

    # xTB formats
    assert extract_semantic_version(" * xtb version 6.6.1 (87a4192) compiled by ...", "xtb") == "6.6.1"
    assert extract_semantic_version("xTB 6.7.0 standalone", "xtb") == "6.7.0"

    # CREST formats
    assert extract_semantic_version("========================================\n|                 CREST                |\n|             Version 3.0.2            |\n========================================", "crest") == "3.0.2"

    # CFOUR formats
    assert extract_semantic_version("CFOUR version 2.1 (Release)\nCoupled Cluster techniques...", "xcfour") == "2.1"

    # Apptainer / Singularity formats
    assert extract_semantic_version("apptainer version 1.3.4", "apptainer") == "1.3.4"
    assert extract_semantic_version("singularity-ce version 3.11.4", "singularity") == "3.11.4"


def test_interrogate_binary_version_with_synthetic_executable(tmp_path: Path) -> None:
    """Test live subprocess version interrogation with a real executable script."""
    is_win = platform.system() == "Windows"
    script_name = "synthetic_orca.bat" if is_win else "synthetic_orca.sh"
    script_path = tmp_path / script_name

    if is_win:
        script_path.write_text("@echo off\necho Program Version 6.1.1 - RELEASE\n", encoding="utf-8")
    else:
        script_path.write_text("#!/bin/sh\necho 'Program Version 6.1.1 - RELEASE'\n", encoding="utf-8")
        script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    version, err = interrogate_binary_version(script_path, "orca", timeout_seconds=5.0)
    assert err is None
    assert version == "6.1.1"


def test_interrogate_binary_version_timeout(tmp_path: Path) -> None:
    """Test timeout protection during binary interrogation."""
    is_win = platform.system() == "Windows"
    py_sleeper = tmp_path / "sleeper.py"
    py_sleeper.write_text("import time\ntime.sleep(10)\n", encoding="utf-8")

    wrapper_name = "sleep_bin.bat" if is_win else "sleep_bin.sh"
    wrapper_path = tmp_path / wrapper_name

    if is_win:
        wrapper_path.write_text(f'@echo off\n"{sys.executable}" "{py_sleeper}"\n', encoding="utf-8")
    else:
        wrapper_path.write_text(f'#!/bin/sh\n"{sys.executable}" "{py_sleeper}"\n', encoding="utf-8")
        wrapper_path.chmod(wrapper_path.stat().st_mode | stat.S_IEXEC | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    version, err = interrogate_binary_version(wrapper_path, "orca", timeout_seconds=0.5)
    assert version is None
    assert err is not None
    assert "timed out" in err.lower()


# =============================================================================
# 5. CONTAINER SIF & AIR-GAP AUDIT TESTS
# =============================================================================


def test_audit_container_sifs_with_real_sif(tmp_path: Path) -> None:
    """Test discovery and validation of SIF container image on disk."""
    sif_dir = tmp_path / "sif_storage"
    sif_dir.mkdir()
    orca_sif = sif_dir / "cochem_orca_6.1.1.sif"
    orca_sif.write_bytes(b"Apptainer SIF container image binary header and data")

    audit = audit_container_sifs(search_dirs=[sif_dir])
    assert len(audit.discovered_sifs) == 1
    sif_entry = audit.discovered_sifs[0]
    assert sif_entry.name == "cochem_orca_6.1.1.sif"
    assert sif_entry.track is EngineTrack.CONTAINER_SIF
    assert sif_entry.is_container is True
    assert "--net" in sif_entry.container_flags
    assert "--network" in sif_entry.container_flags
    assert "none" in sif_entry.container_flags
    assert audit.airgap_flags_valid is True
    assert sif_entry.sha256_hash == hashlib.sha256(b"Apptainer SIF container image binary header and data").hexdigest()


def test_audit_container_sifs_empty(tmp_path: Path) -> None:
    """Test audit_container_sifs when no SIF images exist."""
    empty_dir = tmp_path / "no_sifs"
    empty_dir.mkdir()

    audit = audit_container_sifs(search_dirs=[empty_dir])
    assert len(audit.discovered_sifs) == 0


# =============================================================================
# 6. DETERMINISTIC PATH-INDEPENDENT ENVIRONMENT HASHING TESTS
# =============================================================================


def test_compute_environment_fingerprint_path_invariance() -> None:
    """
    SRS Doc 10 Sec 4.1 Mandate: The environment fingerprint must be invariant to
    arbitrary local absolute paths. Renaming directories or moving machines with identical
    binary content/versions MUST produce the exact same composite SHA-256 fingerprint.
    """
    engines_host_a: Dict[str, BinaryEngineItem] = {
        "orca": BinaryEngineItem(
            name="orca",
            track=EngineTrack.ORCA,
            path="/usr/local/opt/orca_6_1_1/orca",
            version="6.1.1",
            sha256_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            is_available=True,
            status=EngineStatus.FOUND_VALID,
        ),
        "xtb": BinaryEngineItem(
            name="xtb",
            track=EngineTrack.XTB_CREST,
            path="/home/user/miniconda3/envs/cochem/bin/xtb",
            version="6.6.1",
            sha256_hash="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            is_available=True,
            status=EngineStatus.FOUND_VALID,
        ),
    }

    # Host B has different installation paths, but identical binary hashes and versions
    engines_host_b: Dict[str, BinaryEngineItem] = {
        "orca": BinaryEngineItem(
            name="orca",
            track=EngineTrack.ORCA,
            path="C:\\Program Files\\ORCA\\orca.exe",
            version="6.1.1",
            sha256_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            is_available=True,
            status=EngineStatus.FOUND_VALID,
        ),
        "xtb": BinaryEngineItem(
            name="xtb",
            track=EngineTrack.XTB_CREST,
            path="D:\\tools\\xtb\\bin\\xtb.exe",
            version="6.6.1",
            sha256_hash="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            is_available=True,
            status=EngineStatus.FOUND_VALID,
        ),
    }

    fp_a = compute_environment_fingerprint(engines_host_a, os_name="Linux")
    fp_b = compute_environment_fingerprint(engines_host_b, os_name="Linux")

    assert fp_a.composite_hash == fp_b.composite_hash
    assert fp_a.component_count == 2
    assert fp_b.component_count == 2


def test_compute_environment_fingerprint_sensitivity_to_hash_change() -> None:
    """Test that altering a binary's SHA-256 hash strictly changes the environment fingerprint."""
    engines_orig: Dict[str, BinaryEngineItem] = {
        "orca": BinaryEngineItem(
            name="orca",
            track=EngineTrack.ORCA,
            version="6.1.1",
            sha256_hash="1111111111111111111111111111111111111111111111111111111111111111",
            is_available=True,
        )
    }
    engines_modified: Dict[str, BinaryEngineItem] = {
        "orca": BinaryEngineItem(
            name="orca",
            track=EngineTrack.ORCA,
            version="6.1.1",
            sha256_hash="2222222222222222222222222222222222222222222222222222222222222222",
            is_available=True,
        )
    }

    fp_orig = compute_environment_fingerprint(engines_orig, os_name="Linux")
    fp_mod = compute_environment_fingerprint(engines_modified, os_name="Linux")

    assert fp_orig.composite_hash != fp_mod.composite_hash


# =============================================================================
# 7. DEPENDENCY MANAGER & ATOMIC PERSISTENCE TESTS
# =============================================================================


def test_dependency_manager_atomic_write(tmp_path: Path) -> None:
    """Test DependencyManager atomic JSON writes and file creation."""
    target_json = tmp_path / "sub" / "p3.json"
    payload_data = {"phase": 3, "status": "PASSED", "entries": [1, 2, 3]}

    with DependencyManager() as dm:
        written_path = dm.atomic_write_json(target_json, payload_data)
        assert written_path.exists()

    assert target_json.exists()
    content = json.loads(target_json.read_text(encoding="utf-8"))
    assert content["phase"] == 3
    assert content["status"] == "PASSED"


def test_dependency_manager_rollback_on_exception(tmp_path: Path) -> None:
    """Test DependencyManager purges tracked temporary files when an exception occurs."""
    temp_tracked_file = tmp_path / "temp_file_to_rollback.tmp"
    temp_tracked_file.write_text("temporary data", encoding="utf-8")

    with pytest.raises(RuntimeError):
        with DependencyManager() as dm:
            dm.track_temp_file(temp_tracked_file)
            assert temp_tracked_file.exists()
            raise RuntimeError("Simulated failure during Stage 0 Phase 3 orchestration")

    assert not temp_tracked_file.exists()


def test_resolve_p3_registry_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test resolution of p3.json target registry file path."""
    # 1. Custom output dir
    custom_dir = tmp_path / "my_custom_registry"
    p3_res = resolve_p3_registry_path(output_dir=custom_dir)
    assert p3_res == custom_dir / "p3.json"

    # 2. Custom exact file path
    custom_exact = tmp_path / "exact_p3.json"
    p3_res_exact = resolve_p3_registry_path(output_dir=custom_exact)
    assert p3_res_exact == custom_exact

    # 3. Environment variable override
    env_art_dir = tmp_path / "env_artifacts"
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(env_art_dir))
    p3_env = resolve_p3_registry_path()
    assert p3_env == env_art_dir / "Registry" / "p3.json"


# =============================================================================
# 8. FULL PHASE 3 AUDIT & CLI INTEGRATION TESTS
# =============================================================================


def test_run_phase_3_audit_execution(tmp_path: Path) -> None:
    """Test execution of run_phase_3_audit producing a validated Phase3AuditReport and p3.json."""
    output_dir = tmp_path / "Registry"
    report = run_phase_3_audit(output_dir=output_dir)

    assert isinstance(report, Phase3AuditReport)
    assert report.phase_id == "PHASE_3_ENGINE_DISCOVERY_INTEGRITY"
    assert report.status in [PhaseStatus.PASSED, PhaseStatus.DEGRADED, PhaseStatus.FAILED]
    assert report.fingerprint.composite_hash is not None
    assert len(report.fingerprint.composite_hash) == 64
    assert Path(report.artifact_path).exists()

    # Verify serialized JSON matches report model
    loaded_json = json.loads(Path(report.artifact_path).read_text(encoding="utf-8"))
    assert loaded_json["phase_id"] == "PHASE_3_ENGINE_DISCOVERY_INTEGRITY"
    assert "engines" in loaded_json
    assert "tracks" in loaded_json
    assert "container" in loaded_json
    assert "fingerprint" in loaded_json


def test_main_cli_json_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI main entrypoint with --json flag."""
    out_dir = tmp_path / "cli_reg"
    exit_code = main(["--output-dir", str(out_dir), "--json"])

    assert exit_code in (0, 1)
    captured = capsys.readouterr()
    stdout_parsed = json.loads(captured.out)
    assert stdout_parsed["phase_id"] == "PHASE_3_ENGINE_DISCOVERY_INTEGRITY"
    assert (out_dir / "p3.json").exists()


def test_main_cli_standard_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI main entrypoint with formatted stdout reporting."""
    out_dir = tmp_path / "cli_reg_std"
    exit_code = main(["--output-dir", str(out_dir)])

    assert exit_code in (0, 1)
    captured = capsys.readouterr()
    assert "COCHEM SETUP PHASE 3: MULTI-TRACK QUANTUM ENGINE DISCOVERY" in captured.out
    assert "Fingerprint:" in captured.out
    assert (out_dir / "p3.json").exists()


# =============================================================================
# 9. LEGACY PHASE_3.PY SHIM COMPATIBILITY TESTS
# =============================================================================


def test_legacy_phase_3_module_exports() -> None:
    """Verify orchestrator.phase_3 re-exports all canonical and legacy alias symbols."""
    import orchestrator.phase_3 as legacy_p3

    # Verify canonical models and enums
    assert legacy_p3.PhaseStatus is PhaseStatus
    assert legacy_p3.EngineTrack is EngineTrack
    assert legacy_p3.EngineStatus is EngineStatus
    assert legacy_p3.BinaryEngineItem is BinaryEngineItem
    assert legacy_p3.EngineTrackSummary is EngineTrackSummary
    assert legacy_p3.ContainerAudit is ContainerAudit
    assert legacy_p3.EnvironmentFingerprint is EnvironmentFingerprint
    assert legacy_p3.Phase3AuditReport is Phase3AuditReport
    assert legacy_p3.DependencyManager is DependencyManager

    # Verify function aliases
    assert legacy_p3.run_phase_3 is run_phase_3_audit
    assert legacy_p3.run_audit is run_phase_3_audit
    assert legacy_p3.execute_phase_3 is run_phase_3_audit
    assert legacy_p3.execute_audit is run_phase_3_audit
    assert legacy_p3.phase_3_audit is run_phase_3_audit

    assert legacy_p3.audit_engines is audit_all_engines
    assert legacy_p3.audit_engine is audit_single_binary
    assert legacy_p3.audit_binary is audit_single_binary
    assert legacy_p3.audit_containers is audit_container_sifs
    assert legacy_p3.audit_sifs is audit_container_sifs
    assert legacy_p3.audit_sif is audit_container_sifs

    assert legacy_p3.compute_fingerprint is compute_environment_fingerprint
    assert legacy_p3.compute_sha256 is compute_file_sha256
    assert legacy_p3.hash_file is compute_file_sha256
    assert legacy_p3.discover_binary is discover_binary_path
    assert legacy_p3.interrogate_version is interrogate_binary_version
    assert legacy_p3.extract_version is extract_semantic_version
    assert legacy_p3.resolve_registry_path is resolve_p3_registry_path

    assert legacy_p3.main is main
    assert legacy_p3.phase_3_main is main

    # Check __all__ consistency
    for item in legacy_p3.__all__:
        assert hasattr(legacy_p3, item), f"Exported symbol {item} missing from legacy phase_3"


def test_legacy_phase_3_cli_execution(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify executing orchestrator.phase_3 via main function runs full phase 3 audit."""
    import orchestrator.phase_3 as legacy_p3

    out_dir = tmp_path / "legacy_cli_reg"
    exit_code = legacy_p3.main(["--output-dir", str(out_dir), "--json"])

    assert exit_code in (0, 1)
    captured = capsys.readouterr()
    stdout_parsed = json.loads(captured.out)
    assert stdout_parsed["phase_id"] == "PHASE_3_ENGINE_DISCOVERY_INTEGRITY"
    assert (out_dir / "p3.json").exists()

