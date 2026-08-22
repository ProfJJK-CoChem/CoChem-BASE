"""
Unit test suite for CoChem Setup Phase 6: Database & Bifurcated Storage Provisioning.
Strict Zero-Mock Mandate: Real filesystem operations, real HDF5 SWMR & QCSchema archival
database scaffolding, real SQLite WAL companion provisioning, lossless filter validation
(gzip+shuffle+fletcher32, scaleoffset banned), real byte-range file locking checks, and
transactional atomic state persistence into the Golden Registry.

SRS Document 2 Part 2 (Section 3.6), SRS Document 5 (Section 3/4), SRS Document 6 (Section 1-3),
Method Matrix v4 §8C, and CoChem User Manual v4.1 §6.4.3-6.4.4 Compliant.
"""

from __future__ import annotations

import json
import os
import platform
import sqlite3
import stat
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import h5py
import pytest
from pydantic import ValidationError

from orchestrator.cochem_setup_phase_6 import (
    ArchiveSchemaAudit,
    DatabaseBackend,
    DatabaseProvisioningError,
    DependencyManager,
    DiskQuotaError,
    HDF5FilterProfile,
    LockingVerificationError,
    Phase6AuditError,
    Phase6AuditReport,
    PhaseStatus,
    StorageMode,
    StoragePathProfile,
    SWMRRuntimeAudit,
    enforce_storage_permissions,
    main,
    probe_swmr_locking_capabilities,
    provision_archive_pes_db,
    provision_runtime_active_db,
    resolve_databases_directory,
    resolve_p6_registry_path,
    resolve_scratch_directory,
    run_phase_6_audit,
    verify_disk_quota,
)

# Helper for Windows temp directory cleanup
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
    """Verify custom Phase 6 exception classes inherit from RuntimeError."""
    err1 = Phase6AuditError("Phase 6 fatal error")
    assert isinstance(err1, RuntimeError)
    err2 = DatabaseProvisioningError("Database provisioning failed")
    assert isinstance(err2, RuntimeError)
    err3 = DiskQuotaError("Disk space insufficient")
    assert isinstance(err3, RuntimeError)
    err4 = LockingVerificationError("Byte-range lock verification failed")
    assert isinstance(err4, RuntimeError)


def test_phase_status_enum() -> None:
    """Verify PhaseStatus enum values and validation."""
    assert PhaseStatus.PASSED.value == "PASSED"
    assert PhaseStatus.FAILED.value == "FAILED"
    assert PhaseStatus.DEGRADED.value == "DEGRADED"
    assert PhaseStatus.BYPASSED.value == "BYPASSED"
    assert PhaseStatus("PASSED") is PhaseStatus.PASSED

    with pytest.raises(ValueError):
        PhaseStatus("INVALID_STATUS")


def test_storage_mode_enum() -> None:
    """Verify StorageMode enum values and validation."""
    assert StorageMode.BIFURCATED.value == "BIFURCATED"
    assert StorageMode.SQLITE_FALLBACK.value == "SQLITE_FALLBACK"
    assert StorageMode.DEGRADED_POSIX.value == "DEGRADED_POSIX"
    assert StorageMode("BIFURCATED") is StorageMode.BIFURCATED


def test_database_backend_enum() -> None:
    """Verify DatabaseBackend enum values and validation."""
    assert DatabaseBackend.HDF5_SWMR.value == "HDF5_SWMR"
    assert DatabaseBackend.SQLITE_WAL.value == "SQLITE_WAL"
    assert DatabaseBackend.HDF5_STANDARD.value == "HDF5_STANDARD"
    assert DatabaseBackend("HDF5_SWMR") is DatabaseBackend.HDF5_SWMR


# =============================================================================
# 2. PYDANTIC V2 SCHEMA VALIDATION TESTS
# =============================================================================


def test_hdf5_filter_profile_valid_and_scaleoffset_ban() -> None:
    """Test HDF5FilterProfile defaults, constraints, and scaleoffset strict ban."""
    profile = HDF5FilterProfile()
    assert profile.compression == "gzip"
    assert profile.compression_opts == 4
    assert profile.shuffle is True
    assert profile.fletcher32 is True
    assert profile.scaleoffset is None
    assert profile.chunk_pts == 512

    # Scaleoffset is banned to prevent lossy truncation of PES surfaces
    with pytest.raises(ValidationError):
        HDF5FilterProfile(scaleoffset=3)

    # Valid custom compression options
    custom = HDF5FilterProfile(compression="gzip", compression_opts=6, chunk_pts=256)
    assert custom.compression_opts == 6
    assert custom.chunk_pts == 256

    # Invalid compression level
    with pytest.raises(ValidationError):
        HDF5FilterProfile(compression_opts=10)

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        HDF5FilterProfile(unauthorized_field=True)  # type: ignore[call-arg]


def test_storage_path_profile_valid_and_forbidden_extras() -> None:
    """Test StoragePathProfile construction and validation."""
    with make_temp_dir() as tmpdir:
        tmp_path = Path(tmpdir)
        profile = StoragePathProfile(
            databases_directory=str(tmp_path / "Databases"),
            scratch_directory=str(tmp_path / "Scratch"),
            runtime_active_db_path=str(tmp_path / "Databases" / "runtime_active.h5"),
            archive_pes_db_path=str(tmp_path / "Databases" / "archive_pes.h5"),
            sqlite_wal_db_path=str(tmp_path / "Databases" / "runtime_active.db"),
            is_git_ignored=True,
            filesystem_type="NTFS" if platform.system() == "Windows" else "ext4",
            free_disk_space_gb=120.5,
            min_disk_space_required_gb=50.0,
            is_disk_quota_sufficient=True,
        )
        assert profile.is_git_ignored is True
        assert profile.is_disk_quota_sufficient is True
        assert profile.free_disk_space_gb == 120.5

        # Extra fields forbidden
        with pytest.raises(ValidationError):
            StoragePathProfile(
                databases_directory=str(tmp_path / "Databases"),
                scratch_directory=str(tmp_path / "Scratch"),
                runtime_active_db_path=str(tmp_path / "Databases" / "runtime_active.h5"),
                archive_pes_db_path=str(tmp_path / "Databases" / "archive_pes.h5"),
                sqlite_wal_db_path=str(tmp_path / "Databases" / "runtime_active.db"),
                free_disk_space_gb=100.0,
                extra_param="forbidden",  # type: ignore[call-arg]
            )


def test_swmr_runtime_audit_schema() -> None:
    """Test SWMRRuntimeAudit model validation."""
    audit = SWMRRuntimeAudit(
        swmr_supported=True,
        lock_test_passed=True,
        backend_selected=DatabaseBackend.HDF5_SWMR,
        lock_file_path="/tmp/cochem.lock",
        error_detail=None,
    )
    assert audit.swmr_supported is True
    assert audit.backend_selected == DatabaseBackend.HDF5_SWMR
    assert audit.lock_test_passed is True

    # Test degraded fallback configuration
    audit_degraded = SWMRRuntimeAudit(
        swmr_supported=False,
        lock_test_passed=False,
        backend_selected=DatabaseBackend.SQLITE_WAL,
        error_detail="NFS mount detected; byte-range locking unstable.",
    )
    assert audit_degraded.swmr_supported is False
    assert audit_degraded.backend_selected == DatabaseBackend.SQLITE_WAL


def test_archive_schema_audit_and_report_json_serialization() -> None:
    """Test ArchiveSchemaAudit and full Phase6AuditReport serialization/deserialization."""
    with make_temp_dir() as tmpdir:
        tmp_path = Path(tmpdir)
        paths = StoragePathProfile(
            databases_directory=str(tmp_path / "Databases"),
            scratch_directory=str(tmp_path / "Scratch"),
            runtime_active_db_path=str(tmp_path / "Databases" / "runtime_active.h5"),
            archive_pes_db_path=str(tmp_path / "Databases" / "archive_pes.h5"),
            sqlite_wal_db_path=str(tmp_path / "Databases" / "runtime_active.db"),
            free_disk_space_gb=250.0,
        )
        swmr_audit = SWMRRuntimeAudit(
            swmr_supported=True,
            lock_test_passed=True,
            backend_selected=DatabaseBackend.HDF5_SWMR,
        )
        archive_audit = ArchiveSchemaAudit(
            qcschema_version="1.0",
            groups_created=["/meta", "/methods", "/points", "/grids", "/hessians", "/telemetry"],
            filters_applied=HDF5FilterProfile(),
            scaleoffset_banned=True,
            file_size_bytes=4096,
        )
        report = Phase6AuditReport(
            phase_id="cochem_setup_phase_6",
            status=PhaseStatus.PASSED,
            storage_mode=StorageMode.BIFURCATED,
            timestamp_utc="2026-08-22T04:30:00Z",
            artifact_path=str(tmp_path / "p6.json"),
            storage_paths=paths,
            swmr_audit=swmr_audit,
            archive_audit=archive_audit,
            warnings=[],
            errors=[],
        )

        json_data = report.model_dump_json(indent=2)
        assert "cochem_setup_phase_6" in json_data
        assert "archive_pes.h5" in json_data
        assert "PASSED" in json_data

        # Roundtrip deserialization
        parsed = Phase6AuditReport.model_validate_json(json_data)
        assert parsed.phase_id == report.phase_id
        assert parsed.status == PhaseStatus.PASSED
        assert parsed.archive_audit.scaleoffset_banned is True


# =============================================================================
# 3. PATH RESOLUTION, DISK QUOTA & PERMISSIONS TESTS
# =============================================================================


def test_resolve_directories_with_custom_and_defaults() -> None:
    """Test resolution of databases, scratch, and registry directories."""
    with make_temp_dir() as tmpdir:
        tmp_path = Path(tmpdir)
        db_dir = resolve_databases_directory(tmp_path / "CustomDBs")
        assert db_dir == (tmp_path / "CustomDBs").resolve()

        scratch_dir = resolve_scratch_directory(tmp_path / "CustomScratch")
        assert scratch_dir == (tmp_path / "CustomScratch").resolve()

        p6_path = resolve_p6_registry_path(tmp_path / "Registry")
        assert p6_path == (tmp_path / "Registry" / "p6.json").resolve()


def test_verify_disk_quota_normal_and_failure() -> None:
    """Test physical disk quota checking with shutil.disk_usage."""
    with make_temp_dir() as tmpdir:
        free_gb, is_sufficient = verify_disk_quota(tmpdir, min_gb=0.001)
        assert free_gb > 0.0
        assert is_sufficient is True

        # Test failure condition when required space is unrealistically massive
        free_gb2, is_sufficient2 = verify_disk_quota(tmpdir, min_gb=999999999.0)
        assert is_sufficient2 is False


def test_enforce_storage_permissions() -> None:
    """Test setting cross-platform directory permissions."""
    with make_temp_dir() as tmpdir:
        test_dir = Path(tmpdir) / "secure_db"
        test_dir.mkdir(parents=True, exist_ok=True)
        success = enforce_storage_permissions(test_dir, mode=0o755)
        assert success is True
        assert test_dir.exists()


# =============================================================================
# 4. LOCKING & SWMR PROBING TESTS
# =============================================================================


def test_probe_swmr_locking_capabilities() -> None:
    """Test byte-range locking and HDF5 SWMR support probing on physical disk."""
    with make_temp_dir() as tmpdir:
        swmr_supported, lock_passed, detail = probe_swmr_locking_capabilities(tmpdir)
        assert lock_passed is True
        assert swmr_supported is True
        assert "Locking verified" in detail or "SWMR" in detail


# =============================================================================
# 5. REAL HDF5 SWMR & SQLITE WAL PROVISIONING TESTS
# =============================================================================


def test_provision_runtime_active_db_swmr_and_sqlite_wal() -> None:
    """Test physical provisioning of runtime_active.h5 and SQLite WAL companion."""
    with make_temp_dir() as tmpdir:
        target_h5 = Path(tmpdir) / "runtime_active.h5"
        result = provision_runtime_active_db(target_h5, swmr_enabled=True)

        assert target_h5.exists()
        assert result["h5_created"] is True
        assert result["swmr_enabled"] is True

        # Verify HDF5 internal datasets and groups
        with h5py.File(target_h5, "r", libver="latest", swmr=True) as h5:
            assert "/telemetry" in h5
            assert "/active_coordinates" in h5
            assert "/state" in h5
            assert h5.attrs.get("storage_tier") == "Persistent_Data_Tier_Active"

        # Verify companion SQLite WAL database was created and WAL mode is active
        target_db = target_h5.with_suffix(".db")
        assert target_db.exists()
        conn = sqlite3.connect(str(target_db))
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode;")
            mode = cursor.fetchone()[0]
            assert mode.lower() == "wal"
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='live_telemetry';")
            assert cursor.fetchone() is not None
        finally:
            conn.close()


# =============================================================================
# 6. REAL HDF5 QCSCHEMA ARCHIVE_PES.H5 PROVISIONING TESTS
# =============================================================================


def test_provision_archive_pes_db_qcschema_hierarchy_and_filters() -> None:
    """Test physical provisioning of archive_pes.h5 with MolSSI QCSchema layout and lossless filters."""
    with make_temp_dir() as tmpdir:
        target_archive = Path(tmpdir) / "archive_pes.h5"
        symbols = ["O", "H", "H"]
        filter_profile = HDF5FilterProfile(compression="gzip", compression_opts=4, shuffle=True, fletcher32=True)

        audit = provision_archive_pes_db(
            target_path=target_archive,
            complex_name="Water_Monomer_Benchmark",
            symbols=symbols,
            filter_profile=filter_profile,
        )

        assert target_archive.exists()
        assert audit.scaleoffset_banned is True
        assert "/meta" in audit.groups_created
        assert "/methods" in audit.groups_created
        assert "/points" in audit.groups_created
        assert "/grids" in audit.groups_created
        assert "/hessians" in audit.groups_created
        assert "/telemetry" in audit.groups_created

        # Physical HDF5 structure inspection
        with h5py.File(target_archive, "r") as h5:
            # Check /meta
            meta = h5["/meta"]
            assert meta.attrs.get("schema_name") == "QC_JSON"
            assert meta.attrs.get("schema_version") == "1.0"
            assert meta.attrs.get("complex") == "Water_Monomer_Benchmark"
            assert meta.attrs.get("n_atoms") == 3
            assert [s if isinstance(s, str) else s.decode("utf-8") for s in meta.attrs.get("symbols")] == ["O", "H", "H"]

            # Check /points resizable datasets and compression filters
            points = h5["/points"]
            coords_dset = points["coordinates"]
            energy_dset = points["energy"]
            gradient_dset = points["gradient"]

            assert coords_dset.shape == (0, 3, 3)
            assert coords_dset.maxshape == (None, 3, 3)
            assert coords_dset.compression == "gzip"
            assert coords_dset.compression_opts == 4
            assert coords_dset.shuffle is True
            assert coords_dset.fletcher32 is True
            assert coords_dset.scaleoffset is None

            assert energy_dset.shape == (0,)
            assert energy_dset.maxshape == (None,)
            assert energy_dset.compression == "gzip"
            assert energy_dset.fletcher32 is True
            assert energy_dset.scaleoffset is None

            assert gradient_dset.shape == (0, 3, 3)
            assert gradient_dset.maxshape == (None, 3, 3)

            # Check /hessians
            hess = h5["/hessians"]
            hess_dset = hess["cartesian_hessian"]
            assert hess_dset.shape == (0, 9, 9)
            assert hess_dset.maxshape == (None, 9, 9)
            assert hess_dset.fletcher32 is True


def test_archive_pes_point_append_and_checksum_integrity() -> None:
    """Test appending real points to archive_pes.h5 and verifying Fletcher32 checksum reading."""
    import numpy as np

    with make_temp_dir() as tmpdir:
        target_archive = Path(tmpdir) / "archive_pes.h5"
        provision_archive_pes_db(
            target_path=target_archive,
            complex_name="H2O_PES",
            symbols=["O", "H", "H"],
        )

        # Append 5 real test points
        with h5py.File(target_archive, "a") as h5:
            points = h5["/points"]
            coords_dset = points["coordinates"]
            energy_dset = points["energy"]
            grad_dset = points["gradient"]
            conv_dset = points["converged"]
            wall_dset = points["wall_s"]

            n_existing = coords_dset.shape[0]
            n_new = 5
            coords_dset.resize(n_existing + n_new, axis=0)
            energy_dset.resize(n_existing + n_new, axis=0)
            grad_dset.resize(n_existing + n_new, axis=0)
            conv_dset.resize(n_existing + n_new, axis=0)
            wall_dset.resize(n_existing + n_new, axis=0)

            sample_coords = np.zeros((n_new, 3, 3), dtype=np.float64)
            sample_coords[:, 0, :] = [0.0, 0.0, 0.1173]
            sample_coords[:, 1, :] = [0.0, 0.7572, -0.4692]
            sample_coords[:, 2, :] = [0.0, -0.7572, -0.4692]

            sample_energies = np.array([-76.438912, -76.438915, -76.438910, -76.438920, -76.438905], dtype=np.float64)
            sample_grads = np.zeros((n_new, 3, 3), dtype=np.float64)
            sample_conv = np.array([True, True, True, True, True], dtype=bool)
            sample_wall = np.array([1.25, 1.10, 1.35, 1.15, 1.20], dtype=np.float64)

            coords_dset[n_existing:] = sample_coords
            energy_dset[n_existing:] = sample_energies
            grad_dset[n_existing:] = sample_grads
            conv_dset[n_existing:] = sample_conv
            wall_dset[n_existing:] = sample_wall

        # Re-open and verify data and checksum integrity
        with h5py.File(target_archive, "r") as h5:
            points = h5["/points"]
            assert points["coordinates"].shape == (5, 3, 3)
            assert points["energy"].shape == (5,)
            assert float(points["energy"][0]) == pytest.approx(-76.438912, rel=1e-6)
            assert bool(points["converged"][0]) is True


# =============================================================================
# 7. DEPENDENCY MANAGER & ATOMIC REGISTRY SERIALIZATION TESTS
# =============================================================================


def test_dependency_manager_atomic_write_and_rollback() -> None:
    """Test DependencyManager transactional writing to p6.json and rollback on exception."""
    with make_temp_dir() as tmpdir:
        p6_target = Path(tmpdir) / "Registry" / "p6.json"
        dep_mgr = DependencyManager(p6_target)

        # Successful atomic write
        with dep_mgr as dm:
            dm.write_payload({"phase": "p6", "status": "PASSED"})

        assert p6_target.exists()
        with open(p6_target, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["status"] == "PASSED"

        # Failed block triggering rollback
        p6_target_fail = Path(tmpdir) / "Registry" / "p6_fail.json"
        dep_mgr_fail = DependencyManager(p6_target_fail)
        with pytest.raises(ValueError):
            with dep_mgr_fail as dm_fail:
                dm_fail.write_payload({"phase": "p6_fail", "status": "INCOMPLETE"})
                raise ValueError("Simulated unexpected failure during phase execution")

        # Confirm partially written file was safely rolled back / cleaned up
        assert not p6_target_fail.exists()
        assert not Path(str(p6_target_fail) + ".tmp").exists()


# =============================================================================
# 8. FULL RUN_PHASE_6_AUDIT END-TO-END TESTS
# =============================================================================


def test_run_phase_6_audit_full_workflow() -> None:
    """Test complete Phase 6 audit execution in a sterile environment."""
    with make_temp_dir() as tmpdir:
        tmp_path = Path(tmpdir)
        output_dir = tmp_path / "Registry"
        db_dir = tmp_path / "Databases"
        scratch_dir = tmp_path / "Scratch"

        report = run_phase_6_audit(
            output_dir=output_dir,
            databases_dir=db_dir,
            scratch_dir=scratch_dir,
            min_disk_space_gb=0.001,
            complex_name="Test_Complex",
            symbols=["C", "H", "4"],
            dry_run=False,
        )

        assert report.phase_id == "cochem_setup_phase_6"
        assert report.status == PhaseStatus.PASSED
        assert report.storage_mode == StorageMode.BIFURCATED
        assert report.swmr_audit.swmr_supported is True
        assert report.archive_audit.scaleoffset_banned is True

        # Assert physical files exist
        assert Path(report.storage_paths.runtime_active_db_path).exists()
        assert Path(report.storage_paths.archive_pes_db_path).exists()
        assert Path(report.storage_paths.sqlite_wal_db_path).exists()
        assert Path(report.artifact_path).exists()

        # Check p6.json registry file contents
        with open(report.artifact_path, "r", encoding="utf-8") as f:
            registry_data = json.load(f)
            assert registry_data["phase_id"] == "cochem_setup_phase_6"
            assert registry_data["status"] == "PASSED"


def test_run_phase_6_audit_dry_run() -> None:
    """Test dry-run execution does not modify filesystem."""
    with make_temp_dir() as tmpdir:
        tmp_path = Path(tmpdir)
        db_dir = tmp_path / "Databases_Dry"

        report = run_phase_6_audit(
            output_dir=tmp_path / "Registry",
            databases_dir=db_dir,
            scratch_dir=tmp_path / "Scratch",
            min_disk_space_gb=0.001,
            dry_run=True,
        )

        assert report.phase_id == "cochem_setup_phase_6"
        assert report.status == PhaseStatus.PASSED
        assert not db_dir.exists()
        assert not Path(report.storage_paths.runtime_active_db_path).exists()


def test_run_phase_6_audit_disk_quota_fatal_error() -> None:
    """Test audit handles and reports fatal disk quota exhaustion."""
    with make_temp_dir() as tmpdir:
        tmp_path = Path(tmpdir)
        report = run_phase_6_audit(
            output_dir=tmp_path / "Registry",
            databases_dir=tmp_path / "Databases",
            scratch_dir=tmp_path / "Scratch",
            min_disk_space_gb=999999999.0,  # Impossible threshold
            dry_run=False,
        )

        assert report.status == PhaseStatus.FAILED
        assert len(report.errors) > 0
        assert any("Disk quota insufficient" in e for e in report.errors)


# =============================================================================
# 9. CLI ENTRYPOINT TESTS
# =============================================================================


def test_cli_entrypoint_help_and_execution() -> None:
    """Test CLI argument parsing, flags, and return codes."""
    with make_temp_dir() as tmpdir:
        tmp_path = Path(tmpdir)

        # Help exit code
        with pytest.raises(SystemExit) as exc:
            main(["--help"])
        assert exc.value.code == 0

        # Successful CLI dry-run with --json
        rc = main([
            "--output-dir", str(tmp_path / "Registry"),
            "--databases-dir", str(tmp_path / "Databases"),
            "--scratch-dir", str(tmp_path / "Scratch"),
            "--min-disk-gb", "0.001",
            "--dry-run",
            "--json",
        ])
        assert rc == 0

        # Successful physical execution without --json
        rc_live = main([
            "--output-dir", str(tmp_path / "Registry"),
            "--databases-dir", str(tmp_path / "Databases"),
            "--scratch-dir", str(tmp_path / "Scratch"),
            "--min-disk-gb", "0.001",
        ])
        assert rc_live == 0
        assert (tmp_path / "Registry" / "p6.json").exists()


def test_directory_resolution_with_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test resolution of directories using environment variables."""
    with make_temp_dir() as tmpdir:
        tmp_path = Path(tmpdir)
        monkeypatch.setenv("COCHEM_DATABASE_DIR", str(tmp_path / "EnvDBs"))
        assert resolve_databases_directory() == (tmp_path / "EnvDBs").resolve()

        monkeypatch.delenv("COCHEM_DATABASE_DIR")
        monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(tmp_path / "Artifacts"))
        assert resolve_databases_directory() == (tmp_path / "Artifacts" / "Databases").resolve()
        assert resolve_p6_registry_path() == (tmp_path / "Artifacts" / "Registry" / "p6.json").resolve()

        monkeypatch.setenv("COCHEM_SCRATCH_DIR", str(tmp_path / "EnvScratch"))
        assert resolve_scratch_directory() == (tmp_path / "EnvScratch").resolve()

        monkeypatch.delenv("COCHEM_SCRATCH_DIR")
        monkeypatch.setenv("SLURM_TMPDIR", str(tmp_path / "SlurmScratch"))
        assert resolve_scratch_directory() == (tmp_path / "SlurmScratch").resolve()

        monkeypatch.delenv("SLURM_TMPDIR")
        monkeypatch.setenv("TMPDIR", str(tmp_path / "PbsScratch"))
        assert resolve_scratch_directory() == (tmp_path / "PbsScratch").resolve()

        monkeypatch.setenv("COCHEM_REGISTRY_DIR", str(tmp_path / "CustomReg"))
        assert resolve_p6_registry_path() == (tmp_path / "CustomReg" / "p6.json").resolve()


def test_run_phase_6_audit_force_sqlite() -> None:
    """Test run_phase_6_audit with force_sqlite=True enables SQLite WAL mode."""
    with make_temp_dir() as tmpdir:
        tmp_path = Path(tmpdir)
        report = run_phase_6_audit(
            output_dir=tmp_path / "Registry",
            databases_dir=tmp_path / "Databases",
            scratch_dir=tmp_path / "Scratch",
            min_disk_space_gb=0.001,
            force_sqlite=True,
            dry_run=False,
        )

        assert report.status == PhaseStatus.PASSED
        assert report.swmr_audit.backend_selected == DatabaseBackend.SQLITE_WAL
        assert Path(report.storage_paths.sqlite_wal_db_path).exists()


def test_enforce_storage_permissions_nonexistent() -> None:
    """Test enforce_storage_permissions returns False on non-existent path."""
    assert enforce_storage_permissions("/nonexistent/path/for/cochem/test") is False
