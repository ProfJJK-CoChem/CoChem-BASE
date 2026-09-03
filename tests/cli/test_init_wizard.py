"""Physical Unit Verification Suite for Interactive CLI Scaffolding Wizard.

Module: tests.cli.test_init_wizard
Authoritative Reference: SRS Chunk 02 BASE UI & Web (Part 2), Prompt 2.

Invariants:
- Zero-Mock Protocol: Real filesystem operations, genuine disk metrics, real SHA-256 digests.
- Strict directory layout verification: data/raw, data/processed, models/checkpoints, telemetry/logs, config/methods.
- Atomic rollback validation on interrupted filesystem operations.
- Method Matrix v4 template generation and integrity seal validation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.cochem.cli.init_wizard import (
    STANDARD_DIRECTORIES,
    ExistingProjectError,
    InitWizardError,
    InsufficientDiskSpaceError,
    ProjectManifest,
    audit_all_quantum_binaries,
    check_disk_space,
    run_init_wizard,
    verify_project_integrity,
)


class TestInitWizard:
    """Test suite validating CLI workspace scaffolding wizard."""

    def test_run_init_wizard_success(self, tmp_path: Path) -> None:
        """Verify successful scaffolding of all standard directories and manifest."""
        target_dir = tmp_path / "test_workspace"
        result_path = run_init_wizard(target_dir, interactive=False, min_free_bytes=1024)

        assert result_path == target_dir
        assert target_dir.is_dir()

        # Verify all standard directories exist
        for rel_dir in STANDARD_DIRECTORIES:
            assert (target_dir / rel_dir).is_dir(), f"Missing standard directory: {rel_dir}"

        # Verify Method Matrix v4 configuration templates
        methods_dir = target_dir / "config" / "methods"
        assert (methods_dir / "orca_v4_template.json").is_file()
        assert (methods_dir / "crest_goat_template.json").is_file()
        assert (methods_dir / "xtb_gfn2_template.json").is_file()

        # Verify manifest file
        manifest_file = target_dir / ".cochem_project.json"
        assert manifest_file.is_file()

        # Verify integrity seal
        manifest = verify_project_integrity(target_dir)
        assert isinstance(manifest, ProjectManifest)
        assert manifest.project_name == "test_workspace"
        assert manifest.schema_version == "4.0.0"
        assert len(manifest.integrity_seal) == 64

    def test_manifest_integrity_tampering_detection(self, tmp_path: Path) -> None:
        """Verify that tampering with .cochem_project.json causes verify_project_integrity to fail."""
        target_dir = tmp_path / "tamper_workspace"
        run_init_wizard(target_dir, min_free_bytes=1024)

        manifest_file = target_dir / ".cochem_project.json"
        data = json.loads(manifest_file.read_text(encoding="utf-8"))

        # Tamper with project name
        data["project_name"] = "tampered_name"
        manifest_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with pytest.raises(InitWizardError) as exc_info:
            verify_project_integrity(target_dir)

        assert "integrity seal mismatch" in str(exc_info.value).lower()

    def test_insufficient_disk_space_rejection(self, tmp_path: Path) -> None:
        """Verify InsufficientDiskSpaceError is raised when disk space requirement cannot be met."""
        target_dir = tmp_path / "no_space_workspace"
        # Require 10 Petabytes
        unreasonable_bytes = 10 * 1024 * 1024 * 1024 * 1024 * 1024

        with pytest.raises(InsufficientDiskSpaceError) as exc_info:
            run_init_wizard(target_dir, min_free_bytes=unreasonable_bytes)

        assert "free space" in str(exc_info.value).lower()
        # Verify no orphan directories or files were left behind
        assert not target_dir.exists()

    def test_existing_project_error_and_overwrite(self, tmp_path: Path) -> None:
        """Verify ExistingProjectError prevents accidental re-initialization unless overwrite is set."""
        target_dir = tmp_path / "existing_workspace"
        run_init_wizard(target_dir, min_free_bytes=1024)

        # Second attempt without overwrite must fail
        with pytest.raises(ExistingProjectError) as exc_info:
            run_init_wizard(target_dir, min_free_bytes=1024, overwrite_existing=False)

        assert "already an initialized cochem workspace" in str(exc_info.value).lower()

        # Second attempt with overwrite succeeds
        re_init_path = run_init_wizard(target_dir, min_free_bytes=1024, overwrite_existing=True)
        assert re_init_path == target_dir

    def test_binary_audit_records(self) -> None:
        """Verify that audit_all_quantum_binaries returns valid structured records for all targets."""
        records = audit_all_quantum_binaries()
        for b_name in ("orca", "crest", "xtb", "obabel"):
            assert b_name in records
            rec = records[b_name]
            assert rec.name == b_name
            assert isinstance(rec.is_available, bool)
            if rec.is_available:
                assert rec.path is not None
                assert Path(rec.path).is_file()

    def test_check_disk_space_metrics(self, tmp_path: Path) -> None:
        """Verify genuine disk capacity calculation."""
        info = check_disk_space(tmp_path)
        assert info.total_bytes > 0
        assert info.free_bytes > 0
        assert info.total_gb > 0.0
        assert info.free_gb > 0.0
