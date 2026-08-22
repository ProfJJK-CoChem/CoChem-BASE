"""
Unit test suite for CoChem Setup Phase 4: Dynamic Silo Generation & Dependency Isolation Gatekeeper.
Strict Zero-Mock Mandate: Real filesystem operations, live venv provisioning,
deterministic Pydantic V2 schema validations, real stack/memory flags injection,
real dynamic version walking, real Mendeleev authority hooks, and real rollback mechanics.

SRS Document 2 Part 2 (Section 3), SRS Document 4, and SRS Document 5 (Section 3) Compliant.
"""

from __future__ import annotations

import json
import platform
from pathlib import Path

import pytest
from pydantic import ValidationError

from orchestrator.cochem_setup_phase_4 import (
    DependencyManager,
    DynamicVersionWalkingResult,
    DynamicVersionWalkStep,
    IPCSecurityAudit,
    ManifestFilterAudit,
    MendeleevMassRecord,
    Phase4AuditError,
    Phase4AuditReport,
    PhaseStatus,
    SiloAuditItem,
    SiloConfig,
    SiloProvisioningError,
    SiloStatus,
    SiloType,
    VersionWalkingError,
    audit_ipc_and_mps_security,
    audit_micro_silos,
    enforce_python_version,
    execute_dynamic_version_walking,
    filter_silos_by_manifest,
    get_default_silo_configs,
    get_native_memory_env_vars,
    get_native_stack_flags,
    get_silo_executable_path,
    inject_silo_stack_and_env_flags,
    load_deployment_manifest,
    main,
    provision_micro_silo,
    resolve_p4_registry_path,
    resolve_silo_base_directory,
    run_phase_4_audit,
    scan_local_fallback_binaries,
    verify_mendeleev_authority,
)

# =============================================================================
# 1. PYDANTIC V2 SCHEMA & ENUM VALIDATION TESTS
# =============================================================================


def test_custom_exception_hierarchy() -> None:
    """Verify custom Phase 4 exception classes inherit properly from RuntimeError."""
    err1 = Phase4AuditError("Phase 4 fatal")
    assert isinstance(err1, RuntimeError)
    err2 = SiloProvisioningError("Provisioning failed")
    assert isinstance(err2, RuntimeError)
    err3 = VersionWalkingError("Version walking failed")
    assert isinstance(err3, RuntimeError)


def test_get_default_silo_configs(tmp_path: Path) -> None:
    """Verify get_default_silo_configs generates expected specifications for all 4 micro-silos."""
    manifest_filter = ManifestFilterAudit(
        manifest_loaded=True,
        heavy_silos_requested=False,
        skipped_silos=["cochem_calc_silo", "cochem_mace_silo"],
        disk_space_saved_estimated_mb=9000.0,
    )
    configs = get_default_silo_configs(tmp_path, manifest_filter)
    assert SiloType.CORE.value in configs
    assert SiloType.UI.value in configs
    assert SiloType.CALC.value in configs
    assert SiloType.MACE.value in configs
    assert configs[SiloType.CORE.value].is_mandatory is True
    assert configs[SiloType.CALC.value].is_requested is False
    assert configs[SiloType.MACE.value].is_requested is False


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


def test_silo_type_enum() -> None:
    """Verify SiloType enum definitions."""
    assert SiloType.CORE.value == "cochem_core_silo"
    assert SiloType.UI.value == "cochem_ui_silo"
    assert SiloType.CALC.value == "cochem_calc_silo"
    assert SiloType.MACE.value == "cochem_mace_silo"


def test_silo_status_enum() -> None:
    """Verify SiloStatus enum definitions."""
    assert SiloStatus.PROVISIONED.value == "PROVISIONED"
    assert SiloStatus.EXISTS_VALID.value == "EXISTS_VALID"
    assert SiloStatus.BYPASSED.value == "BYPASSED"
    assert SiloStatus.FALLBACK_RECOVERY.value == "FALLBACK_RECOVERY"
    assert SiloStatus.ERROR.value == "ERROR"
    assert SiloStatus.MISSING.value == "MISSING"


def test_silo_config_model_valid_and_extra_forbid() -> None:
    """Test SiloConfig model validation, round-trip serialization, and extra='forbid'."""
    cfg = SiloConfig(
        name="cochem_core_silo",
        silo_type=SiloType.CORE,
        target_path="/tmp/silos/cochem_core_silo",
        python_version="3.11",
        is_mandatory=True,
        is_requested=True,
        is_heavy=False,
        packages=["pydantic", "h5py", "psutil"],
        pip_packages=["pydantic>=2", "h5py"],
        env_vars={"OMP_STACKSIZE": "64M"},
        stack_flags=["-Wl,-z,stack-size=67108864"],
        description="Core silo",
    )
    assert cfg.name == "cochem_core_silo"
    assert cfg.silo_type is SiloType.CORE
    assert cfg.is_mandatory is True

    dumped = cfg.model_dump()
    assert dumped["name"] == "cochem_core_silo"
    restored = SiloConfig.model_validate(dumped)
    assert restored == cfg

    # Test extra='forbid' constraint
    with pytest.raises(ValidationError):
        SiloConfig(
            name="invalid",
            silo_type=SiloType.CORE,
            target_path="/tmp",
            hallucinated_extra_key="forbidden_value",  # type: ignore
        )


def test_silo_config_field_validators() -> None:
    """Test SiloConfig field validators for name and python_version."""
    with pytest.raises(ValidationError):
        SiloConfig(
            name="",  # Empty name
            silo_type=SiloType.CORE,
            target_path="/tmp",
        )

    with pytest.raises(ValidationError):
        SiloConfig(
            name="valid_name",
            silo_type=SiloType.CORE,
            target_path="/tmp",
            python_version="invalid_ver_string",
        )


def test_silo_audit_item_model_valid() -> None:
    """Test SiloAuditItem model initialization and serialization."""
    item = SiloAuditItem(
        name="cochem_calc_silo",
        silo_type=SiloType.CALC,
        path="/tmp/silos/cochem_calc_silo",
        python_executable="/tmp/silos/cochem_calc_silo/bin/python",
        python_version="3.11.8",
        status=SiloStatus.PROVISIONED,
        is_available=True,
        is_heavy=True,
        stack_flags_injected=["/STACK:67108864"],
        env_vars_injected={"OMP_STACKSIZE": "64M"},
        error_detail=None,
        packages_verified=["pyscf", "xtb"],
        created_at="2026-08-21T00:00:00Z",
    )
    assert item.name == "cochem_calc_silo"
    assert item.status is SiloStatus.PROVISIONED
    assert item.is_available is True
    assert item.is_heavy is True

    json_str = item.model_dump_json()
    assert "cochem_calc_silo" in json_str
    parsed = SiloAuditItem.model_validate_json(json_str)
    assert parsed == item


def test_dynamic_version_walking_models() -> None:
    """Test DynamicVersionWalkStep and DynamicVersionWalkingResult models."""
    step1 = DynamicVersionWalkStep(
        attempted_version="3.11",
        success=False,
        error_summary="C++ ABI compilation failure",
    )
    step2 = DynamicVersionWalkStep(
        attempted_version="3.10",
        success=True,
        fallback_wheel_found="/path/to/wheel.whl",
    )
    res = DynamicVersionWalkingResult(
        initial_version="3.11",
        target_version="3.11",
        version_chain=["3.11", "3.10", "3.9"],
        resolved_version="3.10",
        used_local_fallback=True,
        fallback_binary_path="/path/to/wheel.whl",
        steps=[step1, step2],
        status="PASSED",
    )
    assert res.resolved_version == "3.10"
    assert res.used_local_fallback is True
    assert len(res.steps) == 2

    dumped = res.model_dump()
    restored = DynamicVersionWalkingResult.model_validate(dumped)
    assert restored == res


def test_mendeleev_mass_record_model() -> None:
    """Test MendeleevMassRecord model defaults and validation."""
    record = MendeleevMassRecord(
        symbol="C",
        atomic_number=6,
        monoisotopic_mass=12.00000,
        c13_mass=13.00335,
        h1_mass=1.007825,
        o16_mass=15.994915,
        authority="mendeleev",
        is_exact_carbon12=True,
        c13_mass_verified=True,
    )
    assert record.is_exact_carbon12 is True
    assert record.c13_mass_verified is True
    assert record.monoisotopic_mass == 12.00000


def test_mendeleev_mass_record_field_validators() -> None:
    """Test MendeleevMassRecord field validators for positive masses and atomic numbers."""
    with pytest.raises(ValidationError):
        MendeleevMassRecord(atomic_number=0)

    with pytest.raises(ValidationError):
        MendeleevMassRecord(atomic_number=-5)

    with pytest.raises(ValidationError):
        MendeleevMassRecord(monoisotopic_mass=-1.0)

    with pytest.raises(ValidationError):
        MendeleevMassRecord(c13_mass=0.0)


def test_phase4_audit_report_field_validators(tmp_path: Path) -> None:
    """Test Phase4AuditReport field validator for phase_id."""
    with pytest.raises(ValidationError):
        Phase4AuditReport(
            phase_id="INVALID_PHASE_IDENTIFIER",
            status=PhaseStatus.PASSED,
            timestamp_utc="2026-08-21T00:00:00Z",
            version_walking=DynamicVersionWalkingResult(),
            mendeleev_authority=MendeleevMassRecord(),
            ipc_security=IPCSecurityAudit(),
            manifest_filter=ManifestFilterAudit(),
            artifact_path=str(tmp_path / "p4.json"),
        )


def test_ipc_security_audit_model() -> None:
    """Test IPCSecurityAudit model initialization."""
    audit = IPCSecurityAudit(
        socket_path="/tmp/nvidia-mps",
        socket_permissions="0o700",
        is_permission_secure=True,
        pid_namespace_isolated=True,
        mps_service_available=False,
        ipc_spoofing_shielded=True,
        details="Socket restricted to 0700",
    )
    assert audit.is_permission_secure is True
    assert audit.ipc_spoofing_shielded is True


def test_manifest_filter_audit_model() -> None:
    """Test ManifestFilterAudit model fields."""
    mfa = ManifestFilterAudit(
        manifest_path="/tmp/manifest.json",
        manifest_loaded=True,
        selected_repositories=["CoChem-CORE", "CoChem-TOPOS"],
        heavy_silos_requested=False,
        skipped_silos=["cochem_calc_silo", "cochem_mace_silo"],
        disk_space_saved_estimated_mb=9000.0,
    )
    assert mfa.manifest_loaded is True
    assert mfa.heavy_silos_requested is False
    assert len(mfa.skipped_silos) == 2
    assert mfa.disk_space_saved_estimated_mb == 9000.0


def test_phase4_audit_report_full_roundtrip_serialization(tmp_path: Path) -> None:
    """Test full Phase4AuditReport model serialization and deserialization."""
    core_item = SiloAuditItem(
        name="cochem_core_silo",
        silo_type=SiloType.CORE,
        path=str(tmp_path / "core"),
        python_executable=str(tmp_path / "core" / "bin" / "python"),
        python_version="3.11.0",
        status=SiloStatus.PROVISIONED,
        is_available=True,
        is_heavy=False,
    )
    report = Phase4AuditReport(
        phase_id="PHASE_4_MICRO_SILO_PROVISIONING",
        status=PhaseStatus.PASSED,
        timestamp_utc="2026-08-21T00:00:00Z",
        silos={"cochem_core_silo": core_item},
        version_walking=DynamicVersionWalkingResult(
            initial_version="3.11",
            target_version="3.11",
            resolved_version="3.11",
        ),
        mendeleev_authority=MendeleevMassRecord(),
        ipc_security=IPCSecurityAudit(),
        manifest_filter=ManifestFilterAudit(),
        warnings=["Test warning"],
        errors=[],
        artifact_path=str(tmp_path / "p4.json"),
    )
    assert report.status is PhaseStatus.PASSED
    assert report.phase_id == "PHASE_4_MICRO_SILO_PROVISIONING"

    json_text = report.model_dump_json(indent=2)
    restored = Phase4AuditReport.model_validate_json(json_text)
    assert restored == report


# =============================================================================
# 2. DEPENDENCY MANAGER & ROLLBACK MECHANICS TESTS
# =============================================================================


def test_dependency_manager_tracking_and_untracking(tmp_path: Path) -> None:
    """Test DependencyManager tracking, untracking, and lifecycle."""
    dm = DependencyManager()
    f = tmp_path / "tracked_file.tmp"
    f.write_text("temporary data")
    d = tmp_path / "tracked_dir"
    d.mkdir()

    dm.track_temp_file(f)
    dm.track_temp_dir(d)

    assert f in dm._tracked_temp_files
    assert d in dm._tracked_temp_dirs

    dm.untrack_file(f)
    dm.untrack_dir(d)

    assert f not in dm._tracked_temp_files
    assert d not in dm._tracked_temp_dirs


def test_dependency_manager_rollback_on_exception(tmp_path: Path) -> None:
    """Test DependencyManager automatically rolls back tracked items on unhandled exception."""
    temp_file = tmp_path / "staged_artifact.tmp"
    temp_file.write_text("staging data")
    temp_dir = tmp_path / "staged_silo_dir"
    temp_dir.mkdir()
    (temp_dir / "child.txt").write_text("child data")

    assert temp_file.exists()
    assert temp_dir.exists()

    with pytest.raises(RuntimeError):
        with DependencyManager() as dm:
            dm.track_temp_file(temp_file)
            dm.track_temp_dir(temp_dir)
            raise RuntimeError("Transactional rollback verification exception")

    # Assert tracked items were purged upon exception rollback
    assert not temp_file.exists()
    assert not temp_dir.exists()


def test_dependency_manager_atomic_write_json(tmp_path: Path) -> None:
    """Test DependencyManager atomic JSON write operation."""
    target = tmp_path / "nested" / "output.json"
    payload = {"status": "PASSED", "phase": 4, "value": 42.0}

    with DependencyManager() as dm:
        out_path = dm.atomic_write_json(target, payload)

    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["status"] == "PASSED"
    assert data["value"] == 42.0


# =============================================================================
# 3. DEPLOYMENT MANIFEST PARSING & DYNAMIC SILO FILTERING TESTS
# =============================================================================


def test_load_deployment_manifest_real_file(tmp_path: Path) -> None:
    """Test load_deployment_manifest on a real manifest file."""
    manifest_file = tmp_path / "cochem_deployment_manifest.json"
    data = {
        "schema_version": "1.0.0",
        "selected_repositories": ["CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"],
    }
    manifest_file.write_text(json.dumps(data), encoding="utf-8")

    loaded, path_str = load_deployment_manifest(manifest_path=manifest_file)
    assert loaded["schema_version"] == "1.0.0"
    assert "CoChem-CORE" in loaded["selected_repositories"]
    assert path_str == str(manifest_file)


def test_load_deployment_manifest_missing_file() -> None:
    """Test load_deployment_manifest handles non-existent manifest gracefully."""
    loaded, path_str = load_deployment_manifest(manifest_path="/nonexistent/manifest.json")
    # Returns empty dict if not found
    assert isinstance(loaded, dict)


def test_filter_silos_by_manifest_heavy_requested() -> None:
    """Test filter_silos_by_manifest detects heavy spectroscopic modules."""
    manifest_data = {
        "selected_repositories": ["CoChem-CORE", "CoChem-SpycFit", "CoChem-TORQ"],
    }
    audit = filter_silos_by_manifest(manifest_data)
    assert audit.heavy_silos_requested is True
    assert len(audit.skipped_silos) == 0
    assert audit.disk_space_saved_estimated_mb == 0.0


def test_filter_silos_by_manifest_lightweight_only_saves_disk() -> None:
    """Test filter_silos_by_manifest skips heavy silos when only core repos are selected."""
    manifest_data = {
        "selected_repositories": ["CoChem-CORE", "CoChem-TOPOS"],
    }
    audit = filter_silos_by_manifest(manifest_data)
    assert audit.heavy_silos_requested is False
    assert "cochem_calc_silo" in audit.skipped_silos
    assert "cochem_mace_silo" in audit.skipped_silos
    assert audit.disk_space_saved_estimated_mb == 9000.0


def test_filter_silos_by_manifest_explicit_skip_heavy_flag() -> None:
    """Test filter_silos_by_manifest with skip_heavy_flag=True overrides manifest selections."""
    manifest_data = {
        "selected_repositories": ["CoChem-CORE", "CoChem-SpycFit", "CoChem-BENCH"],
    }
    audit = filter_silos_by_manifest(manifest_data, skip_heavy_flag=True)
    assert audit.heavy_silos_requested is False
    assert "cochem_calc_silo" in audit.skipped_silos
    assert audit.disk_space_saved_estimated_mb >= 4500.0


# =============================================================================
# 4. PYTHON 3.11 ENFORCEMENT & DYNAMIC VERSION WALKING TESTS
# =============================================================================


def test_enforce_python_version_matching() -> None:
    """Test enforce_python_version with matching version tuple."""
    ok, msg = enforce_python_version(target_version="3.11", current_version=(3, 11))
    assert ok is True
    assert "compliant" in msg


def test_enforce_python_version_mismatch() -> None:
    """Test enforce_python_version with mismatched version tuple."""
    ok, msg = enforce_python_version(target_version="3.11", current_version=(3, 12))
    assert ok is False
    assert "running Python 3.12" in msg


def test_scan_local_fallback_binaries_with_fixtures(tmp_path: Path) -> None:
    """Test scan_local_fallback_binaries finds real wheel and tarball packages on disk."""
    wheel_dir = tmp_path / "wheelhouse"
    wheel_dir.mkdir()
    (wheel_dir / "pyscf-2.4.0-cp311-cp311-win_amd64.whl").write_bytes(b"PK\x03\x04binary_wheel_payload")
    (wheel_dir / "mace_torch-0.3.0-cp311-cp311-linux_x86_64.tar.gz").write_bytes(b"\x1f\x8bbinary_targz_archive")
    (wheel_dir / "unrelated_doc.pdf").write_bytes(b"%PDF-1.4")

    found = scan_local_fallback_binaries(search_dirs=[wheel_dir])
    found_names = [p.name for p in found]
    assert "pyscf-2.4.0-cp311-cp311-win_amd64.whl" in found_names
    assert "mace_torch-0.3.0-cp311-cp311-linux_x86_64.tar.gz" in found_names
    assert "unrelated_doc.pdf" not in found_names


def test_dynamic_version_walking_chain_progression() -> None:
    """Test execute_dynamic_version_walking steps down versions gracefully."""
    # Force failure on 3.11 to test stepping down to 3.10
    result = execute_dynamic_version_walking(
        target_version="3.11",
        version_chain=["3.11", "3.10", "3.9"],
        force_failure_for_version="3.11",
    )
    assert result.initial_version == "3.11"
    assert result.resolved_version == "3.10"
    assert len(result.steps) == 2
    assert result.steps[0].attempted_version == "3.11"
    assert result.steps[0].success is False
    assert result.steps[1].attempted_version == "3.10"
    assert result.steps[1].success is True


def test_dynamic_version_walking_with_fallback_wheel(tmp_path: Path) -> None:
    """Test execute_dynamic_version_walking locates and binds local fallback wheel."""
    wheel_dir = tmp_path / "wheelhouse"
    wheel_dir.mkdir()
    wheel_file = wheel_dir / "pyscf-2.4.0-cp310-cp310-win_amd64.whl"
    wheel_file.write_bytes(b"PK\x03\x04binary_wheel_data")

    result = execute_dynamic_version_walking(
        target_version="3.11",
        version_chain=["3.11", "3.10", "3.9"],
        fallback_search_dirs=[wheel_dir],
        force_failure_for_version="3.11",
    )
    assert result.resolved_version == "3.10"
    assert result.used_local_fallback is True
    assert result.fallback_binary_path == str(wheel_file)


# =============================================================================
# 5. CROSS-PLATFORM STACK & MEMORY CONFIGURATION INJECTION TESTS
# =============================================================================


def test_get_native_stack_flags_windows_and_posix() -> None:
    """Test get_native_stack_flags returns correct platform-specific compiler flags."""
    win_flags = get_native_stack_flags("Windows")
    assert "/STACK:67108864" in win_flags

    linux_flags = get_native_stack_flags("Linux")
    assert "-Wl,-z,stack-size=67108864" in linux_flags

    darwin_flags = get_native_stack_flags("Darwin")
    assert "-Wl,-z,stack-size=67108864" in darwin_flags


def test_get_native_memory_env_vars() -> None:
    """Test get_native_memory_env_vars includes all required runtime stack/memory variables."""
    ev = get_native_memory_env_vars()
    assert ev["OMP_STACKSIZE"] == "64M"
    assert ev["PYTHONSTACKSIZE"] == "67108864"
    assert ev["KMP_STACKSIZE"] == "64M"
    assert ev["GFORTRAN_UNBUFFERED_ALL"] == "y"


def test_inject_silo_stack_and_env_flags_creates_files(tmp_path: Path) -> None:
    """Test inject_silo_stack_and_env_flags writes metadata and activation scripts."""
    silo_dir = tmp_path / "test_silo"
    silo_dir.mkdir()
    scripts_dir = silo_dir / "Scripts"
    scripts_dir.mkdir()

    stack_flags = ["/STACK:67108864"]
    env_vars = {"OMP_STACKSIZE": "64M", "PYTHONSTACKSIZE": "67108864"}

    ok = inject_silo_stack_and_env_flags(silo_dir, stack_flags, env_vars)
    assert ok is True

    # Verify JSON metadata file
    meta_path = silo_dir / "cochem_silo_env.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["stack_flags"] == stack_flags
    assert meta["env_vars"]["OMP_STACKSIZE"] == "64M"

    # Verify batch hook
    bat_hook = scripts_dir / "cochem_activate_env.bat"
    assert bat_hook.exists()
    bat_text = bat_hook.read_text(encoding="utf-8")
    assert "set OMP_STACKSIZE=64M" in bat_text

    # Verify shell hook
    sh_hook = scripts_dir / "cochem_activate_env.sh"
    assert sh_hook.exists()
    sh_text = sh_hook.read_text(encoding="utf-8")
    assert 'export OMP_STACKSIZE="64M"' in sh_text


# =============================================================================
# 6. MENDELEEV AUTHORITY HOOK TESTS
# =============================================================================


def test_verify_mendeleev_authority_carbon12_exact() -> None:
    """Test verify_mendeleev_authority validates Carbon-12 is exactly 12.00000."""
    rec = verify_mendeleev_authority()
    assert rec.symbol == "C"
    assert rec.atomic_number == 6
    assert rec.monoisotopic_mass == 12.00000
    assert rec.is_exact_carbon12 is True


def test_verify_mendeleev_authority_carbon13_standard() -> None:
    """Test verify_mendeleev_authority validates Carbon-13 mass matches 13.00335."""
    rec = verify_mendeleev_authority()
    assert abs(rec.c13_mass - 13.00335) < 1e-3
    assert rec.c13_mass_verified is True
    assert "mendeleev" in rec.authority


# =============================================================================
# 7. IPC SECURITY & NVIDIA MPS SOCKET AUDITING TESTS
# =============================================================================


def test_audit_ipc_and_mps_security_clean_environment() -> None:
    """Test audit_ipc_and_mps_security in clean environment without active MPS."""
    audit = audit_ipc_and_mps_security()
    assert audit.is_permission_secure is True
    assert audit.pid_namespace_isolated is True
    assert audit.ipc_spoofing_shielded is True


def test_audit_ipc_and_mps_security_with_synthetic_socket_dir(tmp_path: Path) -> None:
    """Test audit_ipc_and_mps_security on real synthetic socket directory."""
    sock_dir = tmp_path / "nvidia_mps_test"
    sock_dir.mkdir()
    (sock_dir / "control").write_bytes(b"control_pipe")

    audit = audit_ipc_and_mps_security(socket_dir=sock_dir)
    assert audit.socket_path == str(sock_dir)
    assert audit.mps_service_available is True
    assert audit.is_permission_secure is True


# =============================================================================
# 8. REAL VIRTUAL ENVIRONMENT PROVISIONING & AUDIT TESTS
# =============================================================================


def test_get_silo_executable_path_platform(tmp_path: Path) -> None:
    """Test get_silo_executable_path returns platform-correct executable name."""
    silo_dir = tmp_path / "my_silo"
    exe = get_silo_executable_path(silo_dir)
    if platform.system() == "Windows":
        assert exe.name == "python.exe"
        assert exe.parent.name == "Scripts"
    else:
        assert exe.name == "python"
        assert exe.parent.name == "bin"


def test_provision_micro_silo_real_venv_creation(tmp_path: Path) -> None:
    """Test real virtual environment micro-silo provisioning in temporary directory."""
    target_silo = tmp_path / "cochem_core_silo"
    cfg = SiloConfig(
        name="cochem_core_silo",
        silo_type=SiloType.CORE,
        target_path=str(target_silo),
        python_version="3.11",
        is_mandatory=True,
        is_requested=True,
        is_heavy=False,
        packages=["pydantic", "h5py"],
        env_vars={"OMP_STACKSIZE": "64M"},
        stack_flags=get_native_stack_flags(),
        description="Test core silo",
    )

    with DependencyManager() as dm:
        item = provision_micro_silo(cfg, dm=dm, dry_run=False)

    assert item.status is SiloStatus.PROVISIONED
    assert item.is_available is True
    assert target_silo.exists()
    assert (target_silo / "pyvenv.cfg").exists()
    assert item.python_executable is not None
    assert Path(item.python_executable).exists()
    assert (target_silo / "cochem_silo_env.json").exists()


def test_provision_micro_silo_idempotency_existing_venv(tmp_path: Path) -> None:
    """Test provision_micro_silo is idempotent when venv already exists."""
    target_silo = tmp_path / "existing_silo"
    cfg = SiloConfig(
        name="cochem_ui_silo",
        silo_type=SiloType.UI,
        target_path=str(target_silo),
        python_version="3.11",
        is_mandatory=False,
        is_requested=True,
        is_heavy=False,
    )

    # 1. First run creates venv
    item1 = provision_micro_silo(cfg, dry_run=False)
    assert item1.status is SiloStatus.PROVISIONED

    # 2. Second run detects existing valid venv
    item2 = provision_micro_silo(cfg, dry_run=False)
    assert item2.status is SiloStatus.EXISTS_VALID
    assert item2.is_available is True


def test_provision_micro_silo_bypassed_unrequested(tmp_path: Path) -> None:
    """Test provision_micro_silo marks unrequested silo as BYPASSED without creating venv."""
    target_silo = tmp_path / "unrequested_calc_silo"
    cfg = SiloConfig(
        name="cochem_calc_silo",
        silo_type=SiloType.CALC,
        target_path=str(target_silo),
        python_version="3.11",
        is_mandatory=False,
        is_requested=False,  # Unrequested
        is_heavy=True,
    )

    item = provision_micro_silo(cfg, dry_run=False)
    assert item.status is SiloStatus.BYPASSED
    assert item.is_available is False
    assert not target_silo.exists()


def test_audit_micro_silos_full_suite(tmp_path: Path) -> None:
    """Test audit_micro_silos provisions and audits all 4 silos correctly."""
    silos_dir = tmp_path / "silos"
    manifest_filter = ManifestFilterAudit(
        manifest_loaded=True,
        heavy_silos_requested=False,
        skipped_silos=["cochem_calc_silo", "cochem_mace_silo"],
        disk_space_saved_estimated_mb=9000.0,
    )

    silos = audit_micro_silos(silos_dir, manifest_filter=manifest_filter, dry_run=False)
    assert len(silos) == 4
    assert silos["cochem_core_silo"].is_available is True
    assert silos["cochem_core_silo"].status is SiloStatus.PROVISIONED
    assert silos["cochem_calc_silo"].status is SiloStatus.BYPASSED
    assert silos["cochem_mace_silo"].status is SiloStatus.BYPASSED


# =============================================================================
# 9. FULL PIPELINE AUDIT & REGISTRY PERSISTENCE TESTS
# =============================================================================


def test_resolve_p4_registry_path_custom_and_default(tmp_path: Path) -> None:
    """Test resolve_p4_registry_path with explicit directory and filename."""
    custom_dir = tmp_path / "Registry"
    p4 = resolve_p4_registry_path(output_dir=custom_dir)
    assert p4.name == "p4.json"
    assert p4.parent == custom_dir.resolve()

    explicit_file = tmp_path / "custom_p4.json"
    p4_file = resolve_p4_registry_path(output_dir=explicit_file)
    assert p4_file == explicit_file.resolve()


def test_resolve_silo_base_directory(tmp_path: Path) -> None:
    """Test resolve_silo_base_directory creates and resolves silo root directory."""
    silo_root = tmp_path / "CustomSilos"
    resolved = resolve_silo_base_directory(custom_dir=silo_root)
    assert resolved.exists()
    assert resolved == silo_root.resolve()


def test_run_phase_4_audit_e2e_dry_run(tmp_path: Path) -> None:
    """Test run_phase_4_audit end-to-end in dry-run mode."""
    out_dir = tmp_path / "reg"
    silo_dir = tmp_path / "silos"

    report = run_phase_4_audit(
        output_dir=out_dir,
        silo_dir=silo_dir,
        dry_run=True,
    )
    assert report.status in (PhaseStatus.PASSED, PhaseStatus.DEGRADED)
    assert report.phase_id == "PHASE_4_MICRO_SILO_PROVISIONING"
    assert len(report.silos) == 4
    assert Path(report.artifact_path).exists()

    # Validate saved JSON is identical
    saved_data = json.loads(Path(report.artifact_path).read_text(encoding="utf-8"))
    assert saved_data["phase_id"] == "PHASE_4_MICRO_SILO_PROVISIONING"


def test_run_phase_4_audit_e2e_real_venv_provisioning(tmp_path: Path) -> None:
    """Test run_phase_4_audit end-to-end with real micro-silo provisioning and p4.json output."""
    out_dir = tmp_path / "reg"
    silo_dir = tmp_path / "silos"

    report = run_phase_4_audit(
        output_dir=out_dir,
        silo_dir=silo_dir,
        skip_heavy=True,
        dry_run=False,
    )
    assert report.status is PhaseStatus.PASSED
    assert Path(report.artifact_path).exists()
    assert report.silos["cochem_core_silo"].is_available is True
    assert report.silos["cochem_calc_silo"].status is SiloStatus.BYPASSED


# =============================================================================
# 10. CLI ENTRYPOINT TESTS
# =============================================================================


def test_main_cli_dry_run_success(tmp_path: Path) -> None:
    """Test CLI main() with --dry-run and custom output directory."""
    out_dir = tmp_path / "reg"
    silo_dir = tmp_path / "silos"
    argv = ["--output-dir", str(out_dir), "--silo-dir", str(silo_dir), "--dry-run"]
    code = main(argv)
    assert code == 0
    assert (out_dir / "p4.json").exists()


def test_main_cli_json_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI main() with --json outputs valid JSON to stdout."""
    out_dir = tmp_path / "reg"
    silo_dir = tmp_path / "silos"
    argv = ["--output-dir", str(out_dir), "--silo-dir", str(silo_dir), "--dry-run", "--json"]
    code = main(argv)
    assert code == 0

    captured = capsys.readouterr()
    stdout = captured.out.strip()
    data = json.loads(stdout)
    assert data["phase_id"] == "PHASE_4_MICRO_SILO_PROVISIONING"
    assert data["status"] in ("PASSED", "DEGRADED")


def test_main_cli_custom_manifest_and_skip_heavy(tmp_path: Path) -> None:
    """Test CLI main() with --manifest and --skip-heavy."""
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps({"selected_repositories": ["CoChem-CORE"]}), encoding="utf-8")

    out_dir = tmp_path / "reg"
    silo_dir = tmp_path / "silos"
    argv = [
        "--output-dir", str(out_dir),
        "--silo-dir", str(silo_dir),
        "--manifest", str(manifest_file),
        "--skip-heavy",
        "--dry-run",
    ]
    code = main(argv)
    assert code == 0
