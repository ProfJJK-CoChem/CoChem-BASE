"""
Unit test suite for CoChem Setup Phase 1: Environment Gatekeeper.
Strict Zero-Mock Mandate: Real filesystem operations, live OS interrogations,
deterministic Pydantic V2 schema validations, real atomic I/O, and real rollback mechanics.
"""

from __future__ import annotations

import json
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from orchestrator.cochem_setup_phase_1 import (
    DependencyManager,
    FilesystemAudit,
    KernelLimitsAudit,
    OSProfile,
    Phase1AuditReport,
    PhaseStatus,
    ToolchainItem,
    WSL9PMountError,
    audit_filesystem,
    audit_kernel_limits,
    audit_toolchain_binary,
    audit_toolchains,
    check_wsl_9p_mount,
    interrogate_os,
    is_wsl_environment,
    main,
    parse_mount_table_entry,
    resolve_p1_registry_path,
    run_phase_1_audit,
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


def test_toolchain_item_model_valid() -> None:
    """Test ToolchainItem model initialization and validation with valid fields."""
    item = ToolchainItem(
        name="gcc",
        path="/usr/bin/gcc",
        version="gcc (Ubuntu 11.4.0) 11.4.0",
        is_available=True,
        error_detail=None,
    )
    assert item.name == "gcc"
    assert item.path == "/usr/bin/gcc"
    assert item.version == "gcc (Ubuntu 11.4.0) 11.4.0"
    assert item.is_available is True
    assert item.error_detail is None

    # Test serialization & deserialization
    dumped = item.model_dump()
    assert dumped["name"] == "gcc"
    restored = ToolchainItem.model_validate(dumped)
    assert restored == item


def test_toolchain_item_model_unavailable() -> None:
    """Test ToolchainItem model with unavailable binary and error detail."""
    item = ToolchainItem(
        name="nonexistent_compiler",
        path=None,
        version=None,
        is_available=False,
        error_detail="Binary not found in PATH",
    )
    assert item.is_available is False
    assert item.path is None
    assert item.error_detail == "Binary not found in PATH"


def test_os_profile_model() -> None:
    """Test OSProfile model field constraints and validations."""
    profile = OSProfile(
        system="Linux",
        release="5.15.153.1-microsoft-standard-WSL2",
        version="#1 SMP Fri Mar 29 23:14:13 UTC 2024",
        machine="x86_64",
        is_wsl=True,
        is_windows=False,
        is_posix=True,
    )
    assert profile.system == "Linux"
    assert profile.is_wsl is True
    assert profile.is_windows is False
    assert profile.is_posix is True

    # Validate JSON serialization round-trip
    json_str = profile.model_dump_json()
    assert "WSL2" in json_str
    parsed = OSProfile.model_validate_json(json_str)
    assert parsed == profile


def test_filesystem_audit_model() -> None:
    """Test FilesystemAudit model field constraints."""
    fs_audit = FilesystemAudit(
        target_path="/home/user/workspace",
        mount_point="/home",
        fs_type="ext4",
        is_9p_mount=False,
        is_posix_compliant=True,
    )
    assert fs_audit.target_path == "/home/user/workspace"
    assert fs_audit.mount_point == "/home"
    assert fs_audit.fs_type == "ext4"
    assert fs_audit.is_9p_mount is False
    assert fs_audit.is_posix_compliant is True


def test_kernel_limits_audit_model() -> None:
    """Test KernelLimitsAudit model with and without flags."""
    limits = KernelLimitsAudit(
        vm_max_map_count=262144,
        stack_limit_bytes=67108864,
        stack_unlimited=False,
        degraded_mode=False,
        recommended_flags=["-Wl,-z,stack-size=67108864"],
    )
    assert limits.vm_max_map_count == 262144
    assert limits.stack_limit_bytes == 67108864
    assert limits.stack_unlimited is False
    assert limits.degraded_mode is False
    assert "-Wl,-z,stack-size=67108864" in limits.recommended_flags


def test_phase1_audit_report_full_schema(tmp_path: Path) -> None:
    """Test Phase1AuditReport end-to-end Pydantic validation and serialization."""
    report = Phase1AuditReport(
        phase_id="PHASE_1_ENVIRONMENT_GATEKEEPER",
        status=PhaseStatus.PASSED,
        timestamp_utc="2026-08-21T00:00:00Z",
        os_profile=OSProfile(
            system="Windows",
            release="10.0.26100",
            version="10.0.26100.1",
            machine="AMD64",
            is_wsl=False,
            is_windows=True,
            is_posix=False,
        ),
        filesystem=FilesystemAudit(
            target_path=str(tmp_path),
            mount_point="D:\\",
            fs_type="NTFS",
            is_9p_mount=False,
            is_posix_compliant=False,
        ),
        toolchains={
            "git": ToolchainItem(
                name="git",
                path="C:\\Program Files\\Git\\cmd\\git.exe",
                version="git version 2.44.0",
                is_available=True,
            ),
        },
        kernel_limits=KernelLimitsAudit(
            vm_max_map_count=None,
            stack_limit_bytes=None,
            stack_unlimited=False,
            degraded_mode=True,
            recommended_flags=["/STACK:67108864"],
        ),
        warnings=["Windows PE environment: dynamic stack expansion unavailable"],
        errors=[],
        artifact_path=str(tmp_path / "Registry" / "p1.json"),
    )

    json_data = report.model_dump_json(indent=2)
    assert "PHASE_1_ENVIRONMENT_GATEKEEPER" in json_data
    assert "Windows PE" in json_data

    # Reconstruct from JSON
    restored = Phase1AuditReport.model_validate_json(json_data)
    assert restored.phase_id == report.phase_id
    assert restored.status == PhaseStatus.PASSED
    assert restored.os_profile.is_windows is True
    assert restored.kernel_limits.degraded_mode is True


def test_invalid_phase1_audit_report_validation() -> None:
    """Verify ValidationError is raised when required fields are missing."""
    with pytest.raises(ValidationError):
        Phase1AuditReport(  # type: ignore[call-arg]
            phase_id="PHASE_1",
            status=PhaseStatus.PASSED,
            timestamp_utc="2026-08-21T00:00:00Z",
        )


# =============================================================================
# 2. LIVE OS INTERROGATION & KERNEL AUDIT TESTS
# =============================================================================


def test_is_wsl_environment_live() -> None:
    """Verify is_wsl_environment returns boolean on live machine."""
    is_wsl = is_wsl_environment()
    assert isinstance(is_wsl, bool)


def test_interrogate_os_live() -> None:
    """Interrogate live operating system and verify attributes against platform module."""
    profile = interrogate_os()
    assert isinstance(profile, OSProfile)
    assert profile.system == platform.system()
    assert profile.release == platform.release()
    assert profile.version == platform.version()
    assert profile.machine == platform.machine()

    if sys.platform.startswith("win"):
        assert profile.is_windows is True
        assert profile.is_posix is False
    else:
        assert profile.is_windows is False
        assert profile.is_posix is True


def test_audit_filesystem_live(tmp_path: Path) -> None:
    """Perform live filesystem audit on a real temporary directory."""
    fs_audit = audit_filesystem(tmp_path)
    assert isinstance(fs_audit, FilesystemAudit)
    assert Path(fs_audit.target_path).resolve() == tmp_path.resolve()
    assert isinstance(fs_audit.is_9p_mount, bool)
    assert isinstance(fs_audit.is_posix_compliant, bool)


def test_audit_filesystem_default_cwd() -> None:
    """Perform live filesystem audit without passing target_path (defaults to cwd)."""
    fs_audit = audit_filesystem(None)
    assert isinstance(fs_audit, FilesystemAudit)
    assert Path(fs_audit.target_path).resolve() == Path.cwd().resolve()


def test_audit_kernel_limits_live() -> None:
    """Audit kernel limits on the live host environment."""
    profile = interrogate_os()
    kernel_audit = audit_kernel_limits(profile)
    assert isinstance(kernel_audit, KernelLimitsAudit)

    if profile.is_windows:
        assert kernel_audit.degraded_mode is True
        assert (
            "/STACK:67108864" in kernel_audit.recommended_flags
            or "-Wl,--stack,67108864" in kernel_audit.recommended_flags
        )
    elif profile.system == "Linux":
        assert isinstance(kernel_audit.degraded_mode, bool)


def test_audit_kernel_limits_posix_profile() -> None:
    """Audit kernel limits with a simulated POSIX profile on non-POSIX hosts."""
    profile = OSProfile(
        system="Linux",
        release="6.1.0-generic",
        version="#1 SMP",
        machine="x86_64",
        is_wsl=False,
        is_windows=False,
        is_posix=True,
    )
    kernel_audit = audit_kernel_limits(profile)
    assert isinstance(kernel_audit, KernelLimitsAudit)
    # If resource module not present (e.g. on Windows), degraded_mode is set to True gracefully
    assert isinstance(kernel_audit.degraded_mode, bool)


# =============================================================================
# 3. TOOLCHAIN INSPECTION TESTS
# =============================================================================


def test_audit_toolchains_live() -> None:
    """Audit standard toolchains (gcc, make, git) on live host without crashes."""
    toolchains = audit_toolchains()
    assert isinstance(toolchains, dict)
    assert "git" in toolchains
    assert "gcc" in toolchains
    assert "make" in toolchains

    for name, item in toolchains.items():
        assert isinstance(item, ToolchainItem)
        assert item.name == name
        if item.is_available:
            assert item.path is not None
            assert Path(item.path).exists()
            assert item.version is not None
            assert len(item.version.strip()) > 0
        else:
            assert item.error_detail is not None


def test_audit_toolchains_custom_missing_binary() -> None:
    """Audit a custom list with a guaranteed non-existent binary."""
    bogus_tool = "__cochem_bogus_binary_99999_xyz__"
    toolchains = audit_toolchains([bogus_tool])
    assert bogus_tool in toolchains
    item = toolchains[bogus_tool]
    assert item.is_available is False
    assert item.path is None
    assert item.version is None
    assert item.error_detail is not None
    assert "not found" in item.error_detail.lower()


def test_audit_toolchain_binary_timeout() -> None:
    """Verify toolchain probing timeout handling with extremely small timeout."""
    # Find any executable on PATH, e.g. python or git
    py_path = sys.executable
    item = audit_toolchain_binary(py_path, timeout_seconds=0.000001)
    assert isinstance(item, ToolchainItem)
    # Either it completes instantly or times out gracefully without raising an unhandled exception
    assert item.name == py_path


# =============================================================================
# 4. WSL2 9P MOUNT TRAP LOGIC & PARSING TESTS
# =============================================================================


def test_wsl9p_mount_error_exception() -> None:
    """Test WSL9PMountError exception properties and remediation text."""
    err = WSL9PMountError(
        "WSL2 9P Mount Trap Detected! Target path '/mnt/c/workspace' is on a 9p/drvfs mount."
    )
    assert isinstance(err, RuntimeError)
    assert "WSL2 9P Mount Trap Detected" in str(err)


def test_parse_mount_table_entry() -> None:
    """Test deterministic parsing of mount table strings."""
    # Test 9p / drvfs entry
    drvfs_line = "C:\\ /mnt/c 9p rw,noatime,dirsync,aname=drvfs;path=C:\\;uid=1000;gid=1000;symlinkroot=/mnt/ 0 0"
    entry = parse_mount_table_entry(drvfs_line)
    assert entry is not None
    dev, mount_point, fs_type, opts = entry
    assert mount_point == "/mnt/c"
    assert fs_type == "9p"
    assert "drvfs" in opts

    # Test ext4 entry
    ext4_line = "/dev/sdb /home/user ext4 rw,relatime,discard,errors=remount-ro,data=ordered 0 0"
    entry = parse_mount_table_entry(ext4_line)
    assert entry is not None
    dev, mount_point, fs_type, opts = entry
    assert mount_point == "/home/user"
    assert fs_type == "ext4"

    # Test invalid / malformed entry
    assert parse_mount_table_entry("") is None
    assert parse_mount_table_entry("invalid line without tokens") is None
    assert parse_mount_table_entry("# this is a comment line 0 0") is None


def test_check_wsl_9p_mount_simulation() -> None:
    """Test 9P detection against mount table configurations without mocking."""
    sample_mounts_table = """rootfs / rootfs rw 0 0
none /dev tmpfs rw,nosuid,relatime,mode=755 0 0
/dev/sdc / ext4 rw,relatime,discard,errors=remount-ro,data=ordered 0 0
C:\\ /mnt/c 9p rw,noatime,dirsync,aname=drvfs;path=C:\\;uid=1000;gid=1000 0 0
D:\\ /mnt/d drvfs rw,noatime,dirsync 0 0
"""
    # Check path inside /mnt/c
    is_9p, mount_pt, fs_type = check_wsl_9p_mount(
        "/mnt/c/Users/test/repo", mount_table_content=sample_mounts_table
    )
    assert is_9p is True
    assert mount_pt == "/mnt/c"
    assert fs_type == "9p"

    # Check path inside /mnt/d
    is_9p, mount_pt, fs_type = check_wsl_9p_mount(
        "/mnt/d/workspace", mount_table_content=sample_mounts_table
    )
    assert is_9p is True
    assert mount_pt == "/mnt/d"

    # Check path inside native ext4 /home/user/workspace
    is_9p, mount_pt, fs_type = check_wsl_9p_mount(
        "/home/user/workspace", mount_table_content=sample_mounts_table
    )
    assert is_9p is False
    assert mount_pt == "/"
    assert fs_type == "ext4"


# =============================================================================
# 5. DEPENDENCY MANAGER & ROLLBACK CONTEXT MANAGER TESTS
# =============================================================================


def test_dependency_manager_atomic_write_json(tmp_path: Path) -> None:
    """Test DependencyManager atomic JSON write for both dict and Pydantic model."""
    target_file = tmp_path / "subdir" / "audit.json"
    item = ToolchainItem(name="git", path="/bin/git", version="2.0", is_available=True)

    with DependencyManager() as dm:
        written_path = dm.atomic_write_json(target_file, item)
        assert written_path == target_file
        assert target_file.exists()

    with open(target_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["name"] == "git"
    assert data["version"] == "2.0"
    assert data["is_available"] is True

    # Test writing a raw dict / list
    dict_file = tmp_path / "subdir" / "dict_test.json"
    with DependencyManager() as dm:
        dm.atomic_write_json(dict_file, {"key": "val", "list": [1, 2, 3]})
        assert dict_file.exists()

    with open(dict_file, "r", encoding="utf-8") as f:
        data_dict = json.load(f)
    assert data_dict["key"] == "val"
    assert data_dict["list"] == [1, 2, 3]


def test_dependency_manager_rollback_on_exception(tmp_path: Path) -> None:
    """Test that staged files and temp files are cleanly deleted when an error occurs."""
    staged_file = tmp_path / "staged_file.tmp"
    staged_dir = tmp_path / "staged_dir_temp"

    assert not staged_file.exists()
    assert not staged_dir.exists()

    with pytest.raises(RuntimeError, match="Simulated crash during audit"):
        with DependencyManager() as dm:
            staged_file.write_text("temporary staged state", encoding="utf-8")
            staged_dir.mkdir(parents=True, exist_ok=True)
            (staged_dir / "nested.tmp").write_text("nested data", encoding="utf-8")

            dm.track_temp_file(staged_file)
            dm.track_temp_dir(staged_dir)

            assert staged_file.exists()
            assert staged_dir.exists()

            raise RuntimeError("Simulated crash during audit")

    # After exception, DependencyManager.__exit__ should have cleaned up the registered temp paths
    assert not staged_file.exists(), "Staged temp file was not rolled back"
    assert not staged_dir.exists(), "Staged temp directory was not rolled back"


def test_dependency_manager_create_temp_helpers(tmp_path: Path) -> None:
    """Test create_temp_file and create_temp_dir helper methods in DependencyManager."""
    with DependencyManager() as dm:
        temp_f = dm.create_temp_file(suffix=".dat", directory=tmp_path)
        temp_d = dm.create_temp_dir(prefix="test_stage_", directory=tmp_path)

        # Also test default directory creation
        temp_f_def = dm.create_temp_file()
        temp_d_def = dm.create_temp_dir()

        assert temp_f.exists()
        assert temp_d.exists()
        assert temp_f_def.exists()
        assert temp_d_def.exists()

        # Clean up explicitly via dm.rollback()
        dm.rollback()

        assert not temp_f.exists()
        assert not temp_d.exists()
        assert not temp_f_def.exists()
        assert not temp_d_def.exists()


# =============================================================================
# 6. REGISTRY RESOLUTION & END-TO-END AUDIT TESTS
# =============================================================================


def test_resolve_p1_registry_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test resolution of p1.json output path under explicit and default paths."""
    explicit_out = tmp_path / "CustomRegistry"
    p1_path = resolve_p1_registry_path(explicit_out)
    assert p1_path.name == "p1.json"
    assert p1_path.parent == explicit_out.resolve()

    # When output_dir already includes p1.json
    direct_file = tmp_path / "CustomRegistry" / "p1.json"
    p1_path_direct = resolve_p1_registry_path(direct_file)
    assert p1_path_direct == direct_file.resolve()

    # With COCHEM_ARTIFACT_DIR set
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(tmp_path))
    env_resolved = resolve_p1_registry_path()
    assert env_resolved.name == "p1.json"
    assert str(tmp_path) in str(env_resolved)


def test_run_phase_1_audit_end_to_end(tmp_path: Path) -> None:
    """Run full Phase 1 audit end-to-end and verify output report and p1.json artifact."""
    output_dir = tmp_path / "Registry"
    report = run_phase_1_audit(output_dir=output_dir, target_path=tmp_path)

    assert isinstance(report, Phase1AuditReport)
    assert report.phase_id == "PHASE_1_ENVIRONMENT_GATEKEEPER"
    assert report.status in (PhaseStatus.PASSED, PhaseStatus.DEGRADED)
    assert report.artifact_path is not None

    artifact_file = Path(report.artifact_path)
    assert artifact_file.exists()
    assert artifact_file.is_file()

    # Read the serialized JSON artifact and validate against Pydantic schema
    with open(artifact_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    validated_report = Phase1AuditReport.model_validate(data)
    assert validated_report.phase_id == report.phase_id
    assert validated_report.status == report.status
    assert validated_report.os_profile.system == report.os_profile.system
    assert "git" in validated_report.toolchains


def test_main_cli_execution_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test CLI main() execution returning exit code 0 and printing human-readable summary."""
    output_dir = tmp_path / "Registry"
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(tmp_path))

    exit_code = main(argv=["--output-dir", str(output_dir), "--target-path", str(tmp_path)])
    assert exit_code == 0
    assert (output_dir / "p1.json").exists()

    captured = capsys.readouterr()
    assert "COCHEM SETUP PHASE 1: ENVIRONMENT GATEKEEPER AUDIT" in captured.out
    assert "Phase ID:" in captured.out


def test_main_cli_execution_json_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI main() with --json flag emitting valid JSON to stdout."""
    output_dir = tmp_path / "Registry"
    exit_code = main(
        argv=["--output-dir", str(output_dir), "--target-path", str(tmp_path), "--json"]
    )
    assert exit_code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["phase_id"] == "PHASE_1_ENVIRONMENT_GATEKEEPER"
    assert "status" in data


@pytest.mark.skipif(
    not is_wsl_environment(),
    reason="Requires WSL environment to test 9P mount trap",
)
def test_audit_filesystem_wsl_9p_trap_raises_exception(tmp_path: Path) -> None:
    """Verify audit_filesystem raises WSL9PMountError when running under WSL on a 9P mount."""
    with pytest.raises(WSL9PMountError) as exc_info:
        # /mnt/c is typically a 9p/drvfs mount in WSL
        audit_filesystem("/mnt/c")

    assert "CRITICAL: WSL2 9P Mount Trap Detected" in str(exc_info.value)
    assert "REMEDIATION: Move your workspace to native Linux ext4/xfs storage" in str(
        exc_info.value
    )


@pytest.mark.skipif(
    platform.system() != "Linux" or is_wsl_environment(),
    reason="Requires native Linux environment",
)
def test_audit_filesystem_linux_native_ext4(tmp_path: Path) -> None:
    """Verify audit_filesystem succeeds on native Linux non-9P filesystems."""
    audit = audit_filesystem(tmp_path)
    assert audit.is_9p_mount is False
    assert audit.is_posix_compliant is True
    # Can't guarantee ext4 specifically, but it shouldn't be 9p
    assert audit.fs_type != "9p"


@pytest.mark.skipif(
    not is_wsl_environment(),
    reason="This test requires WSL environment to test 9P mounts",
)
def test_main_cli_wsl_mount_error_exit_code_2(
    capsys: pytest.CaptureFixture[str]
) -> None:
    """Test CLI main() returns exit code 2 when WSL9PMountError is triggered."""
    # /mnt/c is nearly universally a 9p/drvfs mount in WSL
    exit_code = main(argv=["--target-path", "/mnt/c"])
    assert exit_code == 2

    captured = capsys.readouterr()
    assert "[FATAL WSL 9P MOUNT ERROR]" in captured.err


def test_main_cli_fatal_exception_exit_code_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test CLI main() returns exit code 1 when an unhandled exception occurs."""
    # Create a read-only directory to cause a PermissionError during atomic write
    read_only_dir = tmp_path / "readonly"
    read_only_dir.mkdir()
    read_only_dir.chmod(0o555)  # Read and execute only, no write

    # Make the target file a directory so writes to it always fail (even on Windows)
    target_file = read_only_dir / "p1.json"
    target_file.mkdir()

    exit_code = main(argv=["--output-dir", str(read_only_dir), "--target-path", str(tmp_path)])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "[FATAL PHASE 1 ERROR]" in captured.err


def test_main_cli_degraded_status_exit_code_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test CLI main() returns exit code 0 when audit report has status DEGRADED."""
    # Induce degraded status by clearing PATH so toolchains cannot be found
    monkeypatch.setenv("PATH", "")

    exit_code = main(argv=["--output-dir", str(tmp_path), "--target-path", str(tmp_path)])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "Status:          DEGRADED" in captured.out


def test_audit_toolchain_binary_generic_exception() -> None:
    """Test audit_toolchain_binary graceful error capture on missing/invalid binary."""
    item = audit_toolchain_binary("nonexistent_binary_xyz_12345")
    assert item.is_available is False
    assert item.error_detail is not None
    assert "not found in PATH" in item.error_detail


def test_parse_mount_table_entry_non_digits() -> None:
    """Verify parse_mount_table_entry rejects entries with non-numeric freq/passno."""
    assert parse_mount_table_entry("dev /mnt ext4 rw not_digit 0") is None
    assert parse_mount_table_entry("dev /mnt ext4 rw 0 not_digit") is None


def test_check_wsl_9p_mount_bare_drive_heuristic() -> None:
    """Verify check_wsl_9p_mount detects bare drive path /mnt/c."""
    is_9p, mount_pt, fs_type = check_wsl_9p_mount("/mnt/c", mount_table_content="")
    assert is_9p is True
    assert mount_pt == "/mnt/c"
    assert fs_type == "drvfs"


def test_resolve_p1_registry_path_fallbacks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify resolve_p1_registry_path fallbacks through .agent_artifacts and home directory."""

    monkeypatch.delenv("COCHEM_ARTIFACT_DIR", raising=False)
    monkeypatch.setitem(sys.modules, "cochem_base.config_loader", None)

    # Case 1: .agent_artifacts exists in cwd
    agent_art = tmp_path / ".agent_artifacts"
    agent_art.mkdir(parents=True, exist_ok=True)
    import os
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        p1_path = resolve_p1_registry_path()
        assert p1_path == (agent_art / "Registry" / "p1.json").resolve()

        # Case 2: No .agent_artifacts in cwd, falls back to home / CoChem_Artifacts
        shutil.rmtree(agent_art)
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("USERPROFILE", str(fake_home))

        p1_path_home = resolve_p1_registry_path()
        assert p1_path_home == (fake_home / "CoChem_Artifacts" / "Registry" / "p1.json").resolve()
    finally:
        os.chdir(original_cwd)


def test_dependency_manager_rollback_os_error_resilience(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify DependencyManager rollback suppresses OSError when unlinking files or rmtree."""
    test_file = tmp_path / "locked_file.tmp"
    test_file.write_text("test content", encoding="utf-8")
    test_dir = tmp_path / "locked_dir"
    test_dir.mkdir(parents=True, exist_ok=True)

    with DependencyManager() as dm:
        dm.track_temp_file(test_file)
        dm.track_temp_dir(test_dir)

        # Delete file and dir beforehand so unlink/rmtree raise OSError or encounter missing targets
        test_file.unlink()
        shutil.rmtree(test_dir)
        dm.rollback()  # Must not raise exception


def test_dependency_manager_atomic_write_scalar(tmp_path: Path) -> None:
    """Verify atomic_write_json handles raw scalar values."""
    scalar_file = tmp_path / "scalar.json"
    with DependencyManager() as dm:
        dm.atomic_write_json(scalar_file, "simple string value")

    with open(scalar_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data == "simple string value"





def test_parse_mount_table_entry_octal_unescaping() -> None:
    """Verify parse_mount_table_entry unescapes octal sequences in paths."""
    line = "/dev/sda1 /mnt/my\\040workspace ext4 rw,relatime 0 0"
    entry = parse_mount_table_entry(line)
    assert entry is not None
    dev, mount_pt, fs_type, opts = entry
    assert mount_pt == "/mnt/my workspace"
    assert fs_type == "ext4"


def test_audit_toolchain_binary_nonzero_returncode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify audit_toolchain_binary flags binary as unavailable if returncode != 0."""
    import os
    import sys
    from orchestrator import cochem_setup_phase_1 as p1

    if sys.platform == "win32":
        cmd_file = tmp_path / "broken_tool.cmd"
        cmd_file.write_text("@echo off\necho broken_tool: error while loading shared libraries: libmpc.so.3 1>&2\nexit /b 127\n")
    else:
        cmd_file = tmp_path / "broken_tool.sh"
        cmd_file.write_text("#!/bin/sh\necho 'broken_tool: error while loading shared libraries: libmpc.so.3' >&2\nexit 127\n")
        cmd_file.chmod(0o755)

    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}")
    item = p1.audit_toolchain_binary(cmd_file.name)
    assert item.is_available is False
    assert "exit code 127" in (item.error_detail or "")


def test_check_wsl_9p_mount_ext4_under_mnt() -> None:
    """Verify that ext4 partition mounted under /mnt/ is NOT falsely flagged as 9P."""
    mount_table = (
        "rootfs / rootfs rw 0 0\n"
        "/dev/sdb /mnt/c/fast ext4 rw,relatime 0 0\n"
        "C:\\134 /mnt/c 9p rw,relatime,dir_mode=0777,file_mode=0777,aname=drvfs 0 0\n"
    )
    is_9p, mount_pt, fs_type = check_wsl_9p_mount("/mnt/c/fast/subproject", mount_table_content=mount_table)
    assert is_9p is False
    assert mount_pt == "/mnt/c/fast"
    assert fs_type == "ext4"

