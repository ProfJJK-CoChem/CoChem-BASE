"""
Unit test suite for CoChem Setup Phase X: Abstract Base & Extensible Micro-Silo Driver.
Strict Zero-Mock Mandate: Real filesystem operations, live environment checks,
deterministic Pydantic V2 schema validations, real stack/memory flags injection,
real dynamic version walking, real Mendeleev mass authority integration, and transactional rollback mechanics.

Mandated by SRS Document 5 §1.1 and Generation Roadmap (L60).
"""

from __future__ import annotations

import json
import os
import platform
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from orchestrator.cochem_setup_phase_X import (
    BaseSetupPhase,
    DependencyManager,
    DynamicVersionWalkingResult,
    DynamicVersionWalkStep,
    ExecutionMode,
    MendeleevAuthorityError,
    MendeleevMassRecord,
    OSProfile,
    PhaseAuditItem,
    PhaseStatus,
    PhaseTelemetry,
    PhaseXAuditError,
    PhaseXAuditReport,
    PhaseXConfig,
    PhaseXDriver,
    PhaseXError,
    PreFlightValidationError,
    SiloAuditItem,
    SiloConfig,
    SiloProvisioningError,
    SiloStatus,
    SiloType,
    StatePersistenceError,
    VersionWalkingError,
    WSL9PMountError,
    audit_wsl_mount_traps,
    execute_dynamic_version_walking,
    get_native_memory_env_vars,
    get_native_stack_flags,
    get_silo_executable_path,
    inject_silo_stack_and_env_flags,
    interrogate_host_os,
    main,
    provision_micro_silo,
    resolve_pX_registry_path,
    resolve_silo_base_directory,
    run_phase_x_audit,
    verify_mendeleev_authority,
)


# =============================================================================
# 1. ENUM & PYDANTIC V2 SCHEMA VALIDATIONS
# =============================================================================


def test_phase_status_enum_values():
    assert PhaseStatus.PASSED == "PASSED"
    assert PhaseStatus.FAILED == "FAILED"
    assert PhaseStatus.DEGRADED == "DEGRADED"
    assert PhaseStatus.BYPASSED == "BYPASSED"


def test_silo_type_and_status_enums():
    assert SiloType.CORE == "cochem_core_silo"
    assert SiloType.UI == "cochem_ui_silo"
    assert SiloType.CALC == "cochem_calc_silo"
    assert SiloType.MACE == "cochem_mace_silo"
    assert SiloType.CUSTOM == "cochem_custom_silo"

    assert SiloStatus.PROVISIONED == "PROVISIONED"
    assert SiloStatus.EXISTS_VALID == "EXISTS_VALID"
    assert SiloStatus.BYPASSED == "BYPASSED"
    assert SiloStatus.MISSING == "MISSING"


def test_silo_config_valid():
    cfg = SiloConfig(
        name="test_silo",
        silo_type=SiloType.CUSTOM,
        target_path="/tmp/test_silo",
        python_version="3.11",
        packages=["pydantic"],
    )
    assert cfg.name == "test_silo"
    assert cfg.python_version == "3.11"
    assert cfg.is_mandatory is False


def test_silo_config_invalid_name():
    with pytest.raises(ValidationError):
        SiloConfig(
            name="   ",
            silo_type=SiloType.CUSTOM,
            target_path="/tmp/test_silo",
        )


def test_silo_config_invalid_python_version():
    with pytest.raises(ValidationError):
        SiloConfig(
            name="test_silo",
            silo_type=SiloType.CUSTOM,
            target_path="/tmp/test_silo",
            python_version="python3-invalid",
        )


def test_mendeleev_mass_record_valid():
    rec = MendeleevMassRecord(
        symbol="C",
        atomic_number=6,
        monoisotopic_mass=12.011,
        c13_mass=13.00335,
        h1_mass=1.007825,
        o16_mass=15.994915,
        authority="mendeleev",
    )
    assert rec.symbol == "C"
    assert rec.atomic_number == 6
    assert rec.monoisotopic_mass == 12.011


def test_mendeleev_mass_record_invalid_atomic_number():
    with pytest.raises(ValidationError):
        MendeleevMassRecord(
            symbol="C",
            atomic_number=-1,
            monoisotopic_mass=12.011,
            c13_mass=13.00335,
            h1_mass=1.007825,
            o16_mass=15.994915,
        )


# =============================================================================
# 2. TRANSACTIONAL DEPENDENCY MANAGER TESTS
# =============================================================================


def test_dependency_manager_atomic_write_json(tmp_path: Path):
    dm = DependencyManager()
    target_json = tmp_path / "registry" / "pX.json"
    data = {"status": "PASSED", "phase": "phase_x", "value": 42}

    with dm:
        written = dm.atomic_write_json(target_json, data)

    assert written.exists()
    loaded = json.loads(written.read_text(encoding="utf-8"))
    assert loaded["status"] == "PASSED"
    assert loaded["value"] == 42


def test_dependency_manager_rollback_on_exception(tmp_path: Path):
    dm = DependencyManager()
    temp_dir = None
    temp_file = None

    with pytest.raises(RuntimeError, match="Simulated crash"):
        with dm:
            temp_dir = dm.create_temp_dir(directory=tmp_path)
            temp_file = dm.create_temp_file(directory=tmp_path)
            assert temp_dir.exists()
            assert temp_file.exists()
            raise RuntimeError("Simulated crash")

    # Assert rollback purged artifacts
    assert not temp_dir.exists()
    assert not temp_file.exists()


# =============================================================================
# 3. ENVIRONMENT & OS INTERROGATION TESTS
# =============================================================================


def test_interrogate_host_os_live():
    profile = interrogate_host_os()
    assert isinstance(profile, OSProfile)
    assert profile.system in ("Linux", "Windows", "Darwin")
    assert profile.python_executable
    assert profile.python_version


def test_audit_wsl_mount_traps_live(tmp_path: Path):
    is_trap, msg = audit_wsl_mount_traps(tmp_path)
    assert isinstance(is_trap, bool)
    assert isinstance(msg, str)


def test_resolve_silo_base_directory_custom(tmp_path: Path):
    custom_silos = tmp_path / "CustomSilos"
    resolved = resolve_silo_base_directory(custom_dir=custom_silos)
    assert resolved == custom_silos.resolve()
    assert resolved.exists()


def test_resolve_pX_registry_path_custom(tmp_path: Path):
    resolved = resolve_pX_registry_path(output_dir=tmp_path, phase_id="phase_x")
    assert resolved == (tmp_path / "phase_x.json").resolve()


# =============================================================================
# 4. MENDELEEV AUTHORITY TESTS (ZERO-MOCK MANDATE)
# =============================================================================


def test_verify_mendeleev_authority_live():
    rec = verify_mendeleev_authority()
    assert isinstance(rec, MendeleevMassRecord)
    assert rec.symbol == "C"
    assert rec.atomic_number == 6
    assert abs(rec.monoisotopic_mass - 12.011) < 0.05
    assert abs(rec.c13_mass - 13.00335) < 0.01
    assert abs(rec.h1_mass - 1.007825) < 0.01
    assert abs(rec.o16_mass - 15.994915) < 0.01
    assert rec.authority == "mendeleev"


# =============================================================================
# 5. DYNAMIC VERSION WALKING & STACK FLAGS TESTS
# =============================================================================


def test_execute_dynamic_version_walking_live():
    res = execute_dynamic_version_walking(target_version="3.11")
    assert isinstance(res, DynamicVersionWalkingResult)
    assert res.resolved_version is not None
    assert len(res.steps) > 0


def test_get_native_stack_flags_and_env_vars():
    flags = get_native_stack_flags()
    assert isinstance(flags, list)

    env_vars = get_native_memory_env_vars()
    assert "OMP_STACKSIZE" in env_vars
    assert env_vars["OMP_STACKSIZE"] == "64M"
    assert env_vars["PYTHONUNBUFFERED"] == "1"


def test_inject_silo_stack_and_env_flags():
    cfg = SiloConfig(
        name="custom_silo",
        silo_type=SiloType.CUSTOM,
        target_path="/tmp/custom",
        stack_flags=["-Wl,-extra-flag"],
        env_vars={"CUSTOM_VAR": "TEST"},
    )
    s_flags, env_vars = inject_silo_stack_and_env_flags(cfg)
    assert "-Wl,-extra-flag" in s_flags
    assert env_vars["CUSTOM_VAR"] == "TEST"
    assert "OMP_STACKSIZE" in env_vars


# =============================================================================
# 6. MICRO-SILO PROVISIONING & EXTENSIBLE DRIVER TESTS
# =============================================================================


def test_provision_micro_silo_dry_run(tmp_path: Path):
    cfg = SiloConfig(
        name="test_silo_dry",
        silo_type=SiloType.CORE,
        target_path=str(tmp_path / "test_silo_dry"),
        python_version="3.11",
    )
    audit = provision_micro_silo(cfg, dry_run=True)
    assert isinstance(audit, SiloAuditItem)
    assert audit.name == "test_silo_dry"
    assert audit.status == SiloStatus.BYPASSED
    assert audit.is_available is True


def test_phase_x_driver_execution_dry_run(tmp_path: Path):
    config = PhaseXConfig(
        phase_id="PHASE_X_TEST",
        phase_number=0,
        phase_name="Test Extensible Phase Driver",
        output_dir=str(tmp_path),
        dry_run=True,
    )
    driver = PhaseXDriver(config=config)
    report = driver.run()

    assert isinstance(report, PhaseXAuditReport)
    assert report.phase_id == "PHASE_X_TEST"
    assert report.status in (PhaseStatus.PASSED, PhaseStatus.DEGRADED)
    assert report.os_profile is not None
    assert report.mendeleev_authority is not None
    assert len(report.audit_items) > 0


def test_run_phase_x_audit_callable_with_persistence(tmp_path: Path):
    out_dir = tmp_path / "registry"
    report = run_phase_x_audit(output_dir=out_dir, dry_run=False)

    assert isinstance(report, PhaseXAuditReport)
    assert report.status in (PhaseStatus.PASSED, PhaseStatus.DEGRADED)

    # Verify JSON artifact was written to disk
    art_path = Path(report.artifact_path)
    assert art_path.exists()
    saved = json.loads(art_path.read_text(encoding="utf-8"))
    assert saved["phase_id"] == report.phase_id
    assert saved["status"] == report.status.value


def test_main_cli_dry_run_and_json(tmp_path: Path, capsys):
    ret = main(["--output-dir", str(tmp_path), "--dry-run", "--json"])
    assert ret == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["phase_id"] == "PHASE_X_MICRO_SILO_DRIVER"
    assert data["status"] in ("PASSED", "DEGRADED")
