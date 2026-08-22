"""
Unit test suite for CoChem Setup Phase 10: State-Chain Recovery & Ephemeral Quarantined Sandbox Verifier.
Strict Zero-Mock Mandate: Real filesystem sandbox scaffolding, real 10 MB unbuffered storage IOPS benchmark,
real ORCA (.gbw), PySCF (.chk), and xTB (.xtbw) checkpoint file validation, real state-chain continuity
verification across p1.json through p9.json, real temporary directory persistence, real environment
variable injection dictionaries, and transactional atomic state persistence into the Golden Registry (p10.json).

SRS Document 2 Part 2 (Section 3.10), Method Matrix v4 (§8A-8C), SRS Document 1 (Section 2),
SRS Document 5 (Section 1-4), SRS Document 6 (Section 1-3), SRS Document 7 (Section 2),
and CoChem User Manual v4.1 Compliant.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pytest
from pydantic import ValidationError

from orchestrator.cochem_setup_phase_10 import (
    CheckpointFormat,
    CheckpointStatus,
    CheckpointValidationError,
    CheckpointValidationItem,
    CheckpointValidationReport,
    DependencyManager,
    EphemeralSandboxError,
    EphemeralSandboxProfile,
    IOPSBenchmarkError,
    IOPSBenchmarkProfile,
    IOPSBenchmarkStatus,
    Phase10AuditError,
    Phase10AuditReport,
    PhaseStatus,
    StateChainRecoveryError,
    StateChainRecoveryProfile,
    audit_state_chain_recovery,
    cleanup_ephemeral_sandbox,
    compute_file_sha256,
    find_repository_root,
    generate_environment_injection_dict,
    main,
    resolve_p10_registry_path,
    resolve_sandbox_base_directory,
    run_phase_10_audit,
    run_unbuffered_iops_benchmark,
    scaffold_ephemeral_sandbox,
    scan_and_validate_checkpoints,
    validate_checkpoint_file,
    validate_orca_gbw_checkpoint,
    validate_pyscf_chk_checkpoint,
    validate_xtb_xtbw_checkpoint,
)

try:
    import h5py
    _HAS_H5PY = True
except ImportError:
    h5py = None  # type: ignore
    _HAS_H5PY = False


def make_temp_dir() -> tempfile.TemporaryDirectory:
    """Create a temporary directory with Windows cleanup resilience."""
    if hasattr(tempfile.TemporaryDirectory, "_ignore_cleanup_errors") or platform.system() == "Windows":
        try:
            return tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        except TypeError:
            pass
    return tempfile.TemporaryDirectory()


# =============================================================================
# 1. CUSTOM EXCEPTION & ENUM TESTS
# =============================================================================


def test_custom_exception_hierarchy() -> None:
    """Verify custom Phase 10 exception classes inherit from Phase10AuditError and RuntimeError."""
    err1 = Phase10AuditError("Phase 10 fatal error")
    assert isinstance(err1, RuntimeError)

    err2 = EphemeralSandboxError("Ephemeral sandbox error")
    assert isinstance(err2, Phase10AuditError)
    assert isinstance(err2, RuntimeError)

    err3 = IOPSBenchmarkError("IOPS benchmark error")
    assert isinstance(err3, Phase10AuditError)
    assert isinstance(err3, RuntimeError)

    err4 = CheckpointValidationError("Checkpoint validation error")
    assert isinstance(err4, Phase10AuditError)
    assert isinstance(err4, RuntimeError)

    err5 = StateChainRecoveryError("State-chain recovery error")
    assert isinstance(err5, Phase10AuditError)
    assert isinstance(err5, RuntimeError)


def test_phase_status_enum() -> None:
    """Verify PhaseStatus enum values and validation."""
    assert PhaseStatus.PASSED.value == "PASSED"
    assert PhaseStatus.FAILED.value == "FAILED"
    assert PhaseStatus.DEGRADED.value == "DEGRADED"
    assert PhaseStatus.BYPASSED.value == "BYPASSED"
    assert PhaseStatus("PASSED") is PhaseStatus.PASSED

    with pytest.raises(ValueError):
        PhaseStatus("INVALID_STATUS")


def test_checkpoint_format_enum() -> None:
    """Verify CheckpointFormat enum values."""
    assert CheckpointFormat.ORCA_GBW.value == "ORCA_GBW"
    assert CheckpointFormat.PYSCF_CHK.value == "PYSCF_CHK"
    assert CheckpointFormat.XTB_XTBW.value == "XTB_XTBW"
    assert CheckpointFormat.UNKNOWN.value == "UNKNOWN"

    with pytest.raises(ValueError):
        CheckpointFormat("UNKNOWN_FORMAT")


def test_checkpoint_status_enum() -> None:
    """Verify CheckpointStatus enum values."""
    assert CheckpointStatus.VALID.value == "VALID"
    assert CheckpointStatus.CORRUPT.value == "CORRUPT"
    assert CheckpointStatus.TRUNCATED.value == "TRUNCATED"
    assert CheckpointStatus.INVALID_FORMAT.value == "INVALID_FORMAT"
    assert CheckpointStatus.NOT_FOUND.value == "NOT_FOUND"

    with pytest.raises(ValueError):
        CheckpointStatus("UNKNOWN_STATUS")


def test_iops_benchmark_status_enum() -> None:
    """Verify IOPSBenchmarkStatus enum values."""
    assert IOPSBenchmarkStatus.OPTIMAL.value == "OPTIMAL"
    assert IOPSBenchmarkStatus.ACCEPTABLE.value == "ACCEPTABLE"
    assert IOPSBenchmarkStatus.DEGRADED.value == "DEGRADED"
    assert IOPSBenchmarkStatus.FAILED.value == "FAILED"

    with pytest.raises(ValueError):
        IOPSBenchmarkStatus("UNKNOWN_IOPS_STATUS")


# =============================================================================
# 2. PYDANTIC V2 MODEL VALIDATION TESTS
# =============================================================================


def test_ephemeral_sandbox_profile_model() -> None:
    """Verify EphemeralSandboxProfile schema validation and serialization."""
    prof = EphemeralSandboxProfile(
        sandbox_path="/tmp/cochem_exec_12345678",
        sandbox_uuid="12345678",
        base_directory="/tmp",
        is_created=True,
        is_writable=True,
        is_isolated=True,
        permissions_octal="0o700",
        cleanup_verified=True,
        active_pid=os.getpid(),
    )
    assert prof.sandbox_uuid == "12345678"
    assert prof.is_created is True
    assert prof.active_pid >= 1

    dump = prof.model_dump()
    assert dump["permissions_octal"] == "0o700"

    with pytest.raises(ValidationError):
        EphemeralSandboxProfile(
            sandbox_path="/tmp/cochem_exec_123",
            sandbox_uuid="123",
            base_directory="/tmp",
            is_created=True,
            is_writable=True,
            is_isolated=True,
            active_pid=1,
            unauthorized_field=True,  # type: ignore
        )


def test_iops_benchmark_profile_model() -> None:
    """Verify IOPSBenchmarkProfile schema validation and constraints."""
    prof = IOPSBenchmarkProfile(
        target_directory="/tmp/cochem_exec_test",
        file_size_bytes=10485760,
        block_size_bytes=65536,
        total_blocks=160,
        write_duration_seconds=0.05,
        write_throughput_mb_s=200.0,
        write_iops=3200.0,
        read_duration_seconds=0.04,
        read_throughput_mb_s=250.0,
        read_iops=4000.0,
        sync_latency_ms=1.2,
        status=IOPSBenchmarkStatus.OPTIMAL,
        is_unbuffered=True,
        is_performance_sufficient=True,
    )
    assert prof.total_blocks == 160
    assert prof.write_throughput_mb_s == 200.0
    assert prof.status == IOPSBenchmarkStatus.OPTIMAL

    with pytest.raises(ValidationError):
        IOPSBenchmarkProfile(
            target_directory="/tmp",
            file_size_bytes=100,
            block_size_bytes=65536,
            total_blocks=0,
            write_duration_seconds=-1.0,
            write_throughput_mb_s=-5.0,
            write_iops=0.0,
            read_duration_seconds=0.0,
            read_throughput_mb_s=0.0,
            read_iops=0.0,
            sync_latency_ms=0.0,
        )


def test_checkpoint_models_validation() -> None:
    """Verify CheckpointValidationItem and CheckpointValidationReport schema."""
    item = CheckpointValidationItem(
        file_path="/data/sample.gbw",
        format=CheckpointFormat.ORCA_GBW,
        status=CheckpointStatus.VALID,
        size_bytes=1048576,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        is_resumable=True,
        metadata={"wavefunction": "RHF", "basis": "def2-TZVP"},
    )
    assert item.is_resumable is True
    assert item.format == CheckpointFormat.ORCA_GBW

    report = CheckpointValidationReport(
        scanned_count=1,
        valid_count=1,
        corrupt_count=0,
        resumable_checkpoints=[item],
        validation_enabled=True,
    )
    assert report.scanned_count == 1
    assert report.valid_count == 1
    assert len(report.resumable_checkpoints) == 1


def test_state_chain_recovery_profile_model() -> None:
    """Verify StateChainRecoveryProfile schema validation."""
    sc = StateChainRecoveryProfile(
        registry_directory="/Registry",
        verified_phases=["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9"],
        missing_phases=[],
        chain_intact=True,
        recoverable_jobs=[{"job_id": "job_001", "checkpoint": "calc.gbw"}],
        orphaned_sandboxes=["/tmp/cochem_exec_old1"],
    )
    assert sc.chain_intact is True
    assert len(sc.verified_phases) == 9
    assert len(sc.orphaned_sandboxes) == 1


def test_phase_10_audit_report_model() -> None:
    """Verify Phase10AuditReport complete model serialization."""
    sb = EphemeralSandboxProfile(
        sandbox_path="/tmp/cochem_exec_123",
        sandbox_uuid="123",
        base_directory="/tmp",
        is_created=True,
        is_writable=True,
        is_isolated=True,
        permissions_octal="0o700",
        cleanup_verified=True,
        active_pid=os.getpid(),
    )
    iops = IOPSBenchmarkProfile(
        target_directory="/tmp/cochem_exec_123",
        file_size_bytes=10485760,
        block_size_bytes=65536,
        total_blocks=160,
        write_duration_seconds=0.05,
        write_throughput_mb_s=200.0,
        write_iops=3200.0,
        read_duration_seconds=0.04,
        read_throughput_mb_s=250.0,
        read_iops=4000.0,
        sync_latency_ms=1.0,
        status=IOPSBenchmarkStatus.OPTIMAL,
        is_unbuffered=True,
        is_performance_sufficient=True,
    )
    chk = CheckpointValidationReport(
        scanned_count=0,
        valid_count=0,
        corrupt_count=0,
        resumable_checkpoints=[],
        validation_enabled=True,
    )
    sc = StateChainRecoveryProfile(
        registry_directory="/Registry",
        verified_phases=["p1", "p2"],
        missing_phases=[],
        chain_intact=True,
        recoverable_jobs=[],
        orphaned_sandboxes=[],
    )

    report = Phase10AuditReport(
        phase_id="cochem_setup_phase_10",
        status=PhaseStatus.PASSED,
        timestamp_utc="2026-08-22T00:00:00Z",
        artifact_path="/Registry/p10.json",
        sandbox_profile=sb,
        iops_profile=iops,
        checkpoint_report=chk,
        state_chain_profile=sc,
        injected_env_vars={"COCHEM_EPHEMERAL_SANDBOX": "/tmp/cochem_exec_123"},
        warnings=[],
        errors=[],
    )
    assert report.phase_id == "cochem_setup_phase_10"
    assert report.status == PhaseStatus.PASSED

    raw_json = report.model_dump_json(indent=2)
    parsed = json.loads(raw_json)
    assert parsed["phase_id"] == "cochem_setup_phase_10"
    assert parsed["status"] == "PASSED"


# =============================================================================
# 3. EPHEMERAL SANDBOX ENGINE TESTS
# =============================================================================


def test_resolve_sandbox_base_directory() -> None:
    """Test resolution of sandbox base directory under various environments."""
    with make_temp_dir() as td:
        resolved = resolve_sandbox_base_directory(custom_dir=td)
        assert resolved == Path(td).resolve()

        env = {"COCHEM_SANDBOX_BASE": td}
        resolved_env = resolve_sandbox_base_directory(env=env)
        assert resolved_env == Path(td).resolve()

        resolved_def = resolve_sandbox_base_directory()
        assert resolved_def.exists()


def test_scaffold_ephemeral_sandbox_and_cleanup() -> None:
    """Test real scaffolding of ephemeral sandbox with isolation sentinel and cleanup."""
    with make_temp_dir() as td:
        custom_uuid = "test_uuid_abcdef12"
        profile = scaffold_ephemeral_sandbox(base_dir=td, custom_uuid=custom_uuid)

        assert profile.is_created is True
        assert profile.is_writable is True
        assert profile.is_isolated is True
        assert profile.sandbox_uuid == custom_uuid
        assert Path(profile.sandbox_path).exists()
        assert profile.active_pid == os.getpid()

        test_file = Path(profile.sandbox_path) / "test_calc.inp"
        test_file.write_text("! B3LYP def2-SVP Opt\n* xyz 0 1\nO 0.0 0.0 0.0\n*\n", encoding="utf-8")
        assert test_file.exists()

        cleaned = cleanup_ephemeral_sandbox(profile.sandbox_path)
        assert cleaned is True
        assert not Path(profile.sandbox_path).exists()
        assert cleanup_ephemeral_sandbox(profile.sandbox_path) is True


# =============================================================================
# 4. 10 MB UNBUFFERED IOPS BENCHMARK TESTS
# =============================================================================


def test_run_unbuffered_iops_benchmark() -> None:
    """Test executing real unbuffered IOPS benchmark in temporary directory."""
    with make_temp_dir() as td:
        prof = run_unbuffered_iops_benchmark(target_dir=td, file_size_mb=2.0, block_size_kb=64)

        assert prof.file_size_bytes == 2 * 1024 * 1024
        assert prof.block_size_bytes == 64 * 1024
        assert prof.total_blocks == 32
        assert prof.write_duration_seconds > 0.0
        assert prof.write_throughput_mb_s > 0.0
        assert prof.write_iops > 0.0
        assert prof.read_duration_seconds > 0.0
        assert prof.read_throughput_mb_s > 0.0
        assert prof.read_iops > 0.0
        assert prof.sync_latency_ms >= 0.0
        assert prof.is_unbuffered is True
        assert prof.status in (
            IOPSBenchmarkStatus.OPTIMAL,
            IOPSBenchmarkStatus.ACCEPTABLE,
            IOPSBenchmarkStatus.DEGRADED,
        )


def test_run_unbuffered_iops_benchmark_full_10mb() -> None:
    """Test executing full 10 MB unbuffered IOPS benchmark."""
    with make_temp_dir() as td:
        prof = run_unbuffered_iops_benchmark(target_dir=td, file_size_mb=10.0, block_size_kb=64)
        assert prof.file_size_bytes == 10 * 1024 * 1024
        assert prof.total_blocks == 160
        assert prof.write_throughput_mb_s > 0.0


# =============================================================================
# 5. QUANTUM CHECKPOINT VALIDATION TESTS
# =============================================================================


def test_compute_file_sha256() -> None:
    """Test cryptographic SHA-256 calculation."""
    with make_temp_dir() as td:
        f_path = Path(td) / "sample.bin"
        payload = b"ORCA_BINARY_WAVEFUNCTION_COEFFICIENTS_2026"
        f_path.write_bytes(payload)

        expected = hashlib.sha256(payload).hexdigest()
        actual = compute_file_sha256(f_path)
        assert actual == expected


def test_validate_orca_gbw_checkpoint() -> None:
    """Test validation of real ORCA .gbw binary checkpoint file."""
    with make_temp_dir() as td:
        valid_gbw = Path(td) / "water_opt.gbw"
        gbw_data = b"ORCA-GBW-BINARY-V6.1.1\x00\x01" + b"\x00" * 200
        valid_gbw.write_bytes(gbw_data)

        item_valid = validate_orca_gbw_checkpoint(valid_gbw)
        assert item_valid.format == CheckpointFormat.ORCA_GBW
        assert item_valid.status == CheckpointStatus.VALID
        assert item_valid.is_resumable is True
        assert item_valid.size_bytes == len(gbw_data)
        assert item_valid.sha256_hash is not None

        trunc_gbw = Path(td) / "empty.gbw"
        trunc_gbw.write_bytes(b"")
        item_trunc = validate_orca_gbw_checkpoint(trunc_gbw)
        assert item_trunc.status == CheckpointStatus.TRUNCATED
        assert item_trunc.is_resumable is False

        corrupt_gbw = Path(td) / "corrupt.gbw"
        corrupt_gbw.write_bytes(b"ORCA")
        item_corrupt = validate_orca_gbw_checkpoint(corrupt_gbw)
        assert item_corrupt.status == CheckpointStatus.CORRUPT
        assert item_corrupt.is_resumable is False

        item_nf = validate_orca_gbw_checkpoint(Path(td) / "missing.gbw")
        assert item_nf.status == CheckpointStatus.NOT_FOUND
        assert item_nf.is_resumable is False


def test_validate_pyscf_chk_checkpoint() -> None:
    """Test validation of real PySCF .chk HDF5 checkpoint file."""
    with make_temp_dir() as td:
        chk_path = Path(td) / "pyscf_mol.chk"

        if _HAS_H5PY and h5py is not None:
            with h5py.File(str(chk_path), "w") as h5:
                scf_grp = h5.create_group("scf")
                scf_grp.create_dataset("e_tot", data=-76.4215)
                scf_grp.create_dataset("mo_coeff", data=[[1.0, 0.0], [0.0, 1.0]])
                h5.create_group("mol")

            item = validate_pyscf_chk_checkpoint(chk_path)
            assert item.format == CheckpointFormat.PYSCF_CHK
            assert item.status == CheckpointStatus.VALID
            assert item.is_resumable is True
            assert item.metadata.get("has_scf_group") is True
            assert item.metadata.get("has_mol_group") is True
            assert item.metadata.get("e_tot") == pytest.approx(-76.4215)
        else:
            chk_path.write_bytes(b"\x89HDF\r\n\x1a\n" + b"\x00" * 100)
            item = validate_pyscf_chk_checkpoint(chk_path)
            assert item.format == CheckpointFormat.PYSCF_CHK
            assert item.status == CheckpointStatus.VALID
            assert item.is_resumable is True

        invalid_chk = Path(td) / "invalid.chk"
        invalid_chk.write_bytes(b"PLAIN_TEXT_NOT_HDF5_DATA")
        item_inv = validate_pyscf_chk_checkpoint(invalid_chk)
        assert item_inv.status == CheckpointStatus.INVALID_FORMAT
        assert item_inv.is_resumable is False

        trunc_chk = Path(td) / "empty.chk"
        trunc_chk.write_bytes(b"")
        item_trunc = validate_pyscf_chk_checkpoint(trunc_chk)
        assert item_trunc.status == CheckpointStatus.TRUNCATED


def test_validate_xtb_xtbw_checkpoint() -> None:
    """Test validation of xTB restart file (.xtbw)."""
    with make_temp_dir() as td:
        xtbw_path = Path(td) / "xtb_restart.xtbw"
        xtbw_path.write_bytes(b"XTB-RESTART-CHARGES-MULTIPOLE\x00\x01\x02\x03")

        item = validate_xtb_xtbw_checkpoint(xtbw_path)
        assert item.format == CheckpointFormat.XTB_XTBW
        assert item.status == CheckpointStatus.VALID
        assert item.is_resumable is True

        trunc_xtbw = Path(td) / "empty.xtbw"
        trunc_xtbw.write_bytes(b"")
        item_trunc = validate_xtb_xtbw_checkpoint(trunc_xtbw)
        assert item_trunc.status == CheckpointStatus.TRUNCATED


def test_validate_checkpoint_file_polymorphic() -> None:
    """Test polymorphic checkpoint file router."""
    with make_temp_dir() as td:
        f1 = Path(td) / "calc.gbw"
        f1.write_bytes(b"ORCA_DATA_" + b"\x00" * 100)
        assert validate_checkpoint_file(f1).format == CheckpointFormat.ORCA_GBW
        
        f2 = Path(td) / "calc.chk"
        if _HAS_H5PY and h5py is not None:
            with h5py.File(str(f2), "w") as h5:
                h5.create_group("scf")
        else:
            f2.write_bytes(b"\x89HDF\r\n\x1a\n" + b"\x00" * 100)
        assert validate_checkpoint_file(f2).format == CheckpointFormat.PYSCF_CHK

        f3 = Path(td) / "calc.xtbw"
        f3.write_bytes(b"XTB_RESTART_DATA")
        assert validate_checkpoint_file(f3).format == CheckpointFormat.XTB_XTBW

        f4 = Path(td) / "calc.txt"
        f4.write_text("hello", encoding="utf-8")
        assert validate_checkpoint_file(f4).format == CheckpointFormat.UNKNOWN


def test_scan_and_validate_checkpoints() -> None:
    """Test directory scanning and aggregate reporting."""
    with make_temp_dir() as td:
        d1 = Path(td) / "dir1"
        d1.mkdir()
        (d1 / "job1.gbw").write_bytes(b"ORCA_BINARY_DATA_" + b"\x00" * 100)
        
        chk2 = d1 / "job2.chk"
        if _HAS_H5PY and h5py is not None:
            with h5py.File(str(chk2), "w") as h5:
                h5.create_group("scf")
        else:
            chk2.write_bytes(b"\x89HDF\r\n\x1a\n" + b"\x00" * 100)
            
        (d1 / "job3_corrupt.gbw").write_bytes(b"")

        report = scan_and_validate_checkpoints([d1])
        assert report.scanned_count == 3
        assert report.valid_count == 2
        assert report.corrupt_count == 1
        assert len(report.resumable_checkpoints) == 3


# =============================================================================
# 6. STATE-CHAIN CONTINUITY & RECOVERY TESTS
# =============================================================================


def test_resolve_p10_registry_path() -> None:
    """Test resolution of p10.json Golden Registry artifact path."""
    with make_temp_dir() as td:
        p1 = resolve_p10_registry_path(output_dir=td)
        assert p1 == Path(td).resolve() / "p10.json"

        p2 = resolve_p10_registry_path(output_dir=str(Path(td) / "custom_p10.json"))
        assert p2 == Path(td).resolve() / "custom_p10.json"

        env = {"COCHEM_REGISTRY_DIR": td}
        p3 = resolve_p10_registry_path(env=env)
        assert p3 == Path(td).resolve() / "p10.json"


def test_audit_state_chain_recovery_all_present() -> None:
    """Test state-chain recovery when all previous phases p1-p9 exist."""
    with make_temp_dir() as td:
        reg_dir = Path(td) / "Registry"
        reg_dir.mkdir()

        for i in range(1, 10):
            p_file = reg_dir / f"p{i}.json"
            p_file.write_text(json.dumps({"phase_id": f"cochem_setup_phase_{i}", "status": "PASSED"}), encoding="utf-8")

        s_base = Path(td) / "sandboxes"
        s_base.mkdir()
        orphaned = s_base / "cochem_exec_interrupted_job"
        orphaned.mkdir()
        (orphaned / "resume.gbw").write_bytes(b"ORCA_BINARY_RESTART_" + b"\x00" * 100)

        sc = audit_state_chain_recovery(registry_dir=reg_dir, sandbox_base_dir=s_base)

        assert sc.chain_intact is True
        assert len(sc.verified_phases) == 9
        assert len(sc.missing_phases) == 0
        assert len(sc.orphaned_sandboxes) == 1
        assert len(sc.recoverable_jobs) == 1


def test_audit_state_chain_recovery_missing_phases() -> None:
    """Test state-chain recovery when some previous phases are missing."""
    with make_temp_dir() as td:
        reg_dir = Path(td) / "Registry"
        reg_dir.mkdir()

        (reg_dir / "p1.json").write_text(json.dumps({"status": "PASSED"}), encoding="utf-8")
        (reg_dir / "p2.json").write_text(json.dumps({"status": "PASSED"}), encoding="utf-8")

        sc = audit_state_chain_recovery(registry_dir=reg_dir, sandbox_base_dir=td)

        assert sc.chain_intact is False
        assert len(sc.verified_phases) == 2
        assert len(sc.missing_phases) == 7
        assert "p3" in sc.missing_phases
        assert "p9" in sc.missing_phases


# =============================================================================
# 7. ENVIRONMENT INJECTION & DEPENDENCY MANAGER TESTS
# =============================================================================


def test_generate_environment_injection_dict() -> None:
    """Test environment variable injection generation."""
    sb = EphemeralSandboxProfile(
        sandbox_path="/tmp/cochem_exec_xyz",
        sandbox_uuid="xyz",
        base_directory="/tmp",
        is_created=True,
        is_writable=True,
        is_isolated=True,
        permissions_octal="0o700",
        cleanup_verified=True,
        active_pid=os.getpid(),
    )
    iops = IOPSBenchmarkProfile(
        target_directory="/tmp/cochem_exec_xyz",
        file_size_bytes=10485760,
        block_size_bytes=65536,
        total_blocks=160,
        write_duration_seconds=0.05,
        write_throughput_mb_s=200.0,
        write_iops=3200.0,
        read_duration_seconds=0.04,
        read_throughput_mb_s=250.0,
        read_iops=4000.0,
        sync_latency_ms=1.0,
        status=IOPSBenchmarkStatus.OPTIMAL,
        is_unbuffered=True,
        is_performance_sufficient=True,
    )
    chk = CheckpointValidationReport(
        scanned_count=2,
        valid_count=2,
        corrupt_count=0,
        resumable_checkpoints=[],
        validation_enabled=True,
    )
    sc = StateChainRecoveryProfile(
        registry_directory="/Registry",
        verified_phases=["p1", "p2"],
        missing_phases=[],
        chain_intact=True,
        recoverable_jobs=[],
        orphaned_sandboxes=[],
    )

    env_vars = generate_environment_injection_dict(sb, iops, chk, sc)
    assert env_vars["COCHEM_EPHEMERAL_SANDBOX"] == "/tmp/cochem_exec_xyz"
    assert env_vars["COCHEM_SANDBOX_UUID"] == "xyz"
    assert env_vars["COCHEM_IOPS_WRITE_MBPS"] == "200.0"
    assert env_vars["COCHEM_CHECKPOINT_VALID_COUNT"] == "2"
    assert env_vars["COCHEM_STATE_CHAIN_INTACT"] == "1"
    assert env_vars["COCHEM_PHASE_10_STATUS"] == "PASSED"


def test_dependency_manager_atomic_and_rollback() -> None:
    """Test transactional atomic write and rollback behavior of DependencyManager."""
    with make_temp_dir() as td:
        target_file = Path(td) / "p10.json"

        with DependencyManager(target_file) as dm:
            dm.write_payload({"phase_id": "cochem_setup_phase_10", "status": "PASSED"})

        assert target_file.exists()
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["status"] == "PASSED"

        target_file2 = Path(td) / "p10_fail.json"
        try:
            with DependencyManager(target_file2) as dm2:
                dm2.write_payload({"status": "SHOULD_NOT_EXIST"})
                raise RuntimeError("Simulated unhandled failure")
        except RuntimeError:
            pass

        assert not target_file2.exists()


# =============================================================================
# 8. MASTER AUDIT ORCHESTRATOR & CLI TESTS
# =============================================================================


def test_run_phase_10_audit_full_flow() -> None:
    """Test master run_phase_10_audit execution in dry_run and write modes."""
    with make_temp_dir() as td:
        reg_dir = Path(td) / "Registry"
        reg_dir.mkdir()
        sb_dir = Path(td) / "sandboxes"
        sb_dir.mkdir()

        for i in range(1, 10):
            (reg_dir / f"p{i}.json").write_text(json.dumps({"status": "PASSED"}), encoding="utf-8")

        report_dry = run_phase_10_audit(
            output_dir=reg_dir,
            sandbox_base_dir=sb_dir,
            skip_iops=False,
            benchmark_size_mb=1.0,
            registry_dir=reg_dir,
            dry_run=True,
        )
        assert report_dry.phase_id == "cochem_setup_phase_10"
        assert report_dry.status == PhaseStatus.PASSED
        assert not (reg_dir / "p10.json").exists()

        report_live = run_phase_10_audit(
            output_dir=reg_dir,
            sandbox_base_dir=sb_dir,
            skip_iops=False,
            benchmark_size_mb=1.0,
            registry_dir=reg_dir,
            dry_run=False,
        )
        assert report_live.status == PhaseStatus.PASSED
        assert (reg_dir / "p10.json").exists()

        with open(reg_dir / "p10.json", "r", encoding="utf-8") as f:
            persisted = json.load(f)
            assert persisted["phase_id"] == "cochem_setup_phase_10"
            assert persisted["status"] == "PASSED"


def test_main_cli_execution() -> None:
    """Test main CLI entrypoint with various flag permutations."""
    with make_temp_dir() as td:
        exit_code = main(["--dry-run", "--json", "--skip-iops", "--output-dir", td])
        assert exit_code == 0

        exit_code2 = main(["--dry-run", "--skip-iops", "--output-dir", td, "--sandbox-dir", td])
        assert exit_code2 == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
