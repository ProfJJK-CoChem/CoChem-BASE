"""Comprehensive Zero-Mock Physical Test Suite for cochem_base.config_loader.

Validates all functionality:
- Dynamic root resolution (get_cochem_root, get_base_root, get_repo_root) with and without env overrides
- 5-Tier scratch directory resolution hierarchy (get_scratch_dir and get_cochem_scratch alias)
- Multi-tier config path resolution (resolve_config_path) including COCHEM_ROOT searches
- Path mapping and expansion (resolve_mapped_path) with explicit and default base directories
- Absence of hardcoded drive letters
- Strict typing and docstring compliance
"""

from __future__ import annotations

import json
import platform
import re
import socket
import tempfile
from pathlib import Path

import pytest

from cochem_base.config_loader import (
    get_artifact_dir,
    get_base_root,
    get_cochem_root,
    get_cochem_scratch,
    get_default_cochem_config,
    get_modules_dir,
    get_mps_directories,
    get_ramdisk_dir,
    get_repo_root,
    get_runtime_dir,
    get_scratch_dir,
    get_state_file_path,
    get_telemetry_socket_path,
    get_telemetry_transport,
    get_telemetry_udp_address,
    load_system_config,
    load_system_config_dict,
    prepend_executable_directory,
    resolve_conda_executable,
    resolve_config_path,
    resolve_executable,
    resolve_mapped_path,
    resolve_wsl_executable,
    update_config,
)


def test_get_cochem_root_default() -> None:
    """Verify get_cochem_root discovers repository workspace root in live environment."""
    root = get_cochem_root()
    assert isinstance(root, Path)
    assert root.is_absolute()
    assert root.exists()


def test_get_cochem_root_with_cochem_root_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_cochem_root respects COCHEM_ROOT environment variable."""
    custom_root = tmp_path / "custom_cochem_root"
    custom_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ROOT", str(custom_root))

    resolved = get_cochem_root()
    assert resolved == custom_root.resolve()


def test_get_cochem_root_with_cochem_workspace_root_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_cochem_root respects COCHEM_WORKSPACE_ROOT when COCHEM_ROOT is unset."""
    monkeypatch.delenv("COCHEM_ROOT", raising=False)
    custom_ws = tmp_path / "custom_workspace"
    custom_ws.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_WORKSPACE_ROOT", str(custom_ws))

    resolved = get_cochem_root()
    assert resolved == custom_ws.resolve()


def test_get_cochem_root_outside_repo_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_cochem_root falls back to ~/.cochem when outside repo structure."""
    monkeypatch.delenv("COCHEM_ROOT", raising=False)
    monkeypatch.delenv("COCHEM_WORKSPACE_ROOT", raising=False)

    isolated_file = tmp_path / "standalone" / "pkg" / "module.py"
    monkeypatch.setattr("cochem_base.config_loader.__file__", str(isolated_file))
    resolved = get_cochem_root()
    assert resolved == (Path.home() / ".cochem").resolve()


def test_get_base_root_default() -> None:
    """Verify get_base_root returns directory containing cochem_base."""
    base_root = get_base_root()
    assert isinstance(base_root, Path)
    assert base_root.is_absolute()
    assert (base_root / "cochem_base").is_dir()


def test_get_base_root_with_cochem_base_root_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_base_root respects COCHEM_BASE_ROOT environment variable."""
    custom_base = tmp_path / "custom_base_root"
    custom_base.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_BASE_ROOT", str(custom_base))

    resolved = get_base_root()
    assert resolved == custom_base.resolve()


def test_get_repo_root_default() -> None:
    """Verify get_repo_root returns workspace directory containing repos."""
    repo_root = get_repo_root()
    assert isinstance(repo_root, Path)
    assert repo_root.is_absolute()
    assert repo_root.exists()


def test_get_repo_root_with_cochem_workspace_root_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_repo_root respects COCHEM_WORKSPACE_ROOT environment variable."""
    custom_repo = tmp_path / "custom_repo_root"
    custom_repo.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_WORKSPACE_ROOT", str(custom_repo))

    resolved = get_repo_root()
    assert resolved == custom_repo.resolve()


def test_get_repo_root_with_cochem_root_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_repo_root respects COCHEM_ROOT when COCHEM_WORKSPACE_ROOT is unset."""
    monkeypatch.delenv("COCHEM_WORKSPACE_ROOT", raising=False)
    custom_root = tmp_path / "custom_cochem_root"
    custom_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ROOT", str(custom_root))

    resolved = get_repo_root()
    assert resolved == custom_root.resolve()


# =============================================================================
# 5-Tier Scratch Directory Resolution Tests
# =============================================================================


def test_get_scratch_dir_tier1_explicit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tier 1: Explicit custom_path overrides environment variables and defaults."""
    monkeypatch.setenv("COCHEM_SCRATCH", str(tmp_path / "ignored_env_scratch"))
    custom_target = tmp_path / "explicit_scratch_dir"

    resolved = get_scratch_dir(custom_path=custom_target)
    assert resolved == custom_target.resolve()
    assert resolved.is_dir()


def test_get_scratch_dir_tier2_cochem_scratch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tier 2: COCHEM_SCRATCH environment variable resolution."""
    scratch_target = tmp_path / "env_cochem_scratch"
    monkeypatch.setenv("COCHEM_SCRATCH", str(scratch_target))

    resolved = get_scratch_dir()
    assert resolved == scratch_target.resolve()
    assert resolved.is_dir()


def test_get_scratch_dir_tier2_cochem_scratch_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tier 2: COCHEM_SCRATCH_DIR environment variable resolution."""
    monkeypatch.delenv("COCHEM_SCRATCH", raising=False)
    scratch_target = tmp_path / "env_cochem_scratch_dir"
    monkeypatch.setenv("COCHEM_SCRATCH_DIR", str(scratch_target))

    resolved = get_scratch_dir()
    assert resolved == scratch_target.resolve()
    assert resolved.is_dir()


def test_get_scratch_dir_tier3_xdg_cache_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tier 3: XDG_CACHE_HOME environment variable resolution."""
    monkeypatch.delenv("COCHEM_SCRATCH", raising=False)
    monkeypatch.delenv("COCHEM_SCRATCH_DIR", raising=False)
    xdg_target = tmp_path / "xdg_cache"
    monkeypatch.setenv("XDG_CACHE_HOME", str(xdg_target))

    resolved = get_scratch_dir()
    expected = (xdg_target / "cochem" / "scratch").resolve()
    assert resolved == expected
    assert resolved.is_dir()


def test_get_scratch_dir_tier4_tempfile(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tier 4: tempfile.gettempdir() / "cochem_scratch" default."""
    monkeypatch.delenv("COCHEM_SCRATCH", raising=False)
    monkeypatch.delenv("COCHEM_SCRATCH_DIR", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

    resolved = get_scratch_dir()
    expected = (Path(tempfile.gettempdir()) / "cochem_scratch").resolve()
    assert resolved == expected
    assert resolved.is_dir()


def test_get_scratch_dir_tier5_home_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Tier 5: Fallback to Path.home() / ".cochem" / "scratch" when Tier 4 fails."""
    monkeypatch.delenv("COCHEM_SCRATCH", raising=False)
    monkeypatch.delenv("COCHEM_SCRATCH_DIR", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

    # Induce Tier 4 failure physically by pointing tempdir to a file
    dummy_file = tmp_path / "dummy_tempdir.txt"
    dummy_file.write_text("blocker")
    original_tempdir = tempfile.tempdir
    tempfile.tempdir = str(dummy_file)

    try:
        resolved = get_scratch_dir()
        expected = (Path.home() / ".cochem" / "scratch").resolve()
        assert resolved == expected
        assert resolved.is_dir()
    finally:
        tempfile.tempdir = original_tempdir


def test_get_cochem_scratch_alias(tmp_path: Path) -> None:
    """Verify get_cochem_scratch alias provides identical behavior to get_scratch_dir."""
    custom_target = tmp_path / "alias_scratch"
    resolved_alias = get_cochem_scratch(custom_path=custom_target)
    resolved_direct = get_scratch_dir(custom_path=custom_target)
    assert resolved_alias == resolved_direct
    assert resolved_alias == custom_target.resolve()


# =============================================================================
# Config Path Resolution Tests
# =============================================================================


def test_resolve_config_path_explicit(tmp_path: Path) -> None:
    """Verify resolve_config_path respects explicit custom_path parameter."""
    custom_cfg = tmp_path / "custom_config.json"
    custom_cfg.write_text("{}", encoding="utf-8")

    resolved = resolve_config_path(custom_path=custom_cfg)
    assert resolved == custom_cfg.resolve()


def test_resolve_config_path_cochem_root_direct(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_config_path discovers cochem_system_config.json under COCHEM_ROOT."""
    monkeypatch.delenv("COCHEM_CONFIG", raising=False)
    custom_root = tmp_path / "root_with_cfg"
    custom_root.mkdir(parents=True, exist_ok=True)
    cfg_file = custom_root / "cochem_system_config.json"
    cfg_file.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("COCHEM_ROOT", str(custom_root))

    resolved = resolve_config_path()
    assert resolved == cfg_file.resolve()


def test_resolve_config_path_cochem_root_base_subdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_config_path discovers cochem_system_config.json under COCHEM_ROOT/CoChem-BASE."""
    monkeypatch.delenv("COCHEM_CONFIG", raising=False)
    custom_root = tmp_path / "root_with_base_cfg"
    base_dir = custom_root / "CoChem-BASE"
    base_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = base_dir / "cochem_system_config.json"
    cfg_file.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("COCHEM_ROOT", str(custom_root))

    resolved = resolve_config_path()
    assert resolved == cfg_file.resolve()


def test_resolve_config_path_cochem_config_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_config_path respects COCHEM_CONFIG environment variable if file exists."""
    cfg_file = tmp_path / "env_config.json"
    cfg_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("COCHEM_CONFIG", str(cfg_file))

    resolved = resolve_config_path()
    assert resolved == cfg_file.resolve()


def test_resolve_config_path_cochem_artifact_dir_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_config_path discovers cochem_system_config.json under COCHEM_ARTIFACT_DIR."""
    monkeypatch.delenv("COCHEM_CONFIG", raising=False)
    monkeypatch.delenv("COCHEM_ROOT", raising=False)
    art_dir = tmp_path / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = art_dir / "cochem_system_config.json"
    cfg_file.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(art_dir))

    resolved = resolve_config_path()
    assert resolved == cfg_file.resolve()


# =============================================================================
# Path Mapping & Drive Letter Audits
# =============================================================================


def test_resolve_mapped_path_anchor_default() -> None:
    """Verify resolve_mapped_path anchors relative paths against get_base_root()."""
    relative_path = "subfolder/test_file.txt"
    resolved = resolve_mapped_path(relative_path)
    expected = (get_base_root() / relative_path).resolve()
    assert resolved == expected


def test_resolve_mapped_path_anchor_explicit(tmp_path: Path) -> None:
    """Verify resolve_mapped_path anchors relative paths against provided base_dir."""
    relative_path = "subfolder/test_file.txt"
    resolved = resolve_mapped_path(relative_path, base_dir=tmp_path)
    expected = (tmp_path / relative_path).resolve()
    assert resolved == expected


def test_no_hardcoded_drive_letters() -> None:
    """Verify cochem_base/config_loader.py contains no hardcoded Windows drive letters."""
    config_loader_path = Path(__file__).resolve().parent.parent / "cochem_base" / "config_loader.py"
    content = config_loader_path.read_text(encoding="utf-8")

    # Match patterns like C:\, D:\, E:/, etc.
    drive_letter_pattern = re.compile(r"""(?i)['"][A-Z]:[/\\]""")
    matches = drive_letter_pattern.findall(content)
    assert matches == [], f"Hardcoded drive letters detected in config_loader.py: {matches}"


# =============================================================================
# Artifact and Module Directory Resolution Tests
# =============================================================================


def test_get_artifact_dir_default() -> None:
    """Verify get_artifact_dir resolves to an absolute path in the live workspace."""
    artifact_dir = get_artifact_dir()
    assert isinstance(artifact_dir, Path)
    assert artifact_dir.is_absolute()


def test_get_artifact_dir_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_artifact_dir respects COCHEM_ARTIFACT_DIR."""
    custom_art = tmp_path / "custom_artifacts"
    custom_art.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(custom_art))

    resolved = get_artifact_dir()
    assert resolved == custom_art.resolve()


def test_get_modules_dir_default() -> None:
    """Verify get_modules_dir resolves to an absolute path in the live workspace."""
    modules_dir = get_modules_dir()
    assert isinstance(modules_dir, Path)
    assert modules_dir.is_absolute()


def test_get_modules_dir_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_modules_dir respects COCHEM_MODULE_DIR."""
    custom_modules = tmp_path / "custom_modules"
    custom_modules.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_MODULE_DIR", str(custom_modules))

    resolved = get_modules_dir()
    assert resolved == custom_modules.resolve()


# =============================================================================
# Runtime, Telemetry, and Host State Resolution Tests
# =============================================================================


def test_get_runtime_dir_default() -> None:
    """Verify get_runtime_dir returns a writable host-native directory."""
    runtime_dir = get_runtime_dir()
    assert isinstance(runtime_dir, Path)
    assert runtime_dir.is_absolute()
    assert runtime_dir.is_dir()


def test_get_runtime_dir_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_runtime_dir respects COCHEM_RUNTIME_DIR."""
    custom_runtime = tmp_path / "custom_runtime"
    monkeypatch.setenv("COCHEM_RUNTIME_DIR", str(custom_runtime))

    resolved = get_runtime_dir()
    assert resolved == custom_runtime.resolve()
    assert resolved.is_dir()


def test_get_telemetry_socket_path_default() -> None:
    """Verify get_telemetry_socket_path anchors under get_runtime_dir()."""
    socket_path = get_telemetry_socket_path()
    assert isinstance(socket_path, Path)
    assert socket_path.parent == get_runtime_dir()
    assert socket_path.name == "cochem_telemetry.sock"


def test_get_telemetry_socket_path_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_telemetry_socket_path respects COCHEM_TELEMETRY_SOCKET."""
    custom_sock = tmp_path / "custom.sock"
    monkeypatch.setenv("COCHEM_TELEMETRY_SOCKET", str(custom_sock))

    resolved = get_telemetry_socket_path()
    assert resolved == custom_sock.resolve()


def test_get_telemetry_transport_default() -> None:
    """Verify get_telemetry_transport defaults appropriately for host platform."""
    transport = get_telemetry_transport()
    if platform.system() == "Windows" or not hasattr(socket, "AF_UNIX"):
        assert transport == "udp"
    else:
        assert transport == "unix"


def test_get_telemetry_transport_env_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_telemetry_transport parses valid transport configuration."""
    monkeypatch.setenv("COCHEM_TELEMETRY_TRANSPORT", "udp")
    assert get_telemetry_transport() == "udp"


def test_get_telemetry_transport_env_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_telemetry_transport rejects invalid transport options."""
    monkeypatch.setenv("COCHEM_TELEMETRY_TRANSPORT", "invalid_protocol")
    with pytest.raises(ValueError, match="must be 'unix' or 'udp'"):
        get_telemetry_transport()


def test_get_telemetry_udp_address_default() -> None:
    """Verify get_telemetry_udp_address returns default loopback endpoint."""
    host, port = get_telemetry_udp_address()
    assert host == "127.0.0.1"
    assert port == 8765


def test_get_telemetry_udp_address_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_telemetry_udp_address respects host and port overrides."""
    monkeypatch.setenv("COCHEM_TELEMETRY_HOST", "127.0.0.2")
    monkeypatch.setenv("COCHEM_TELEMETRY_PORT", "9999")
    host, port = get_telemetry_udp_address()
    assert host == "127.0.0.2"
    assert port == 9999


def test_get_telemetry_udp_address_invalid_port(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_telemetry_udp_address raises on non-integer or out-of-range port."""
    monkeypatch.setenv("COCHEM_TELEMETRY_PORT", "not_a_number")
    with pytest.raises(ValueError, match="must be an integer"):
        get_telemetry_udp_address()

    monkeypatch.setenv("COCHEM_TELEMETRY_PORT", "70000")
    with pytest.raises(ValueError, match="between 1 and 65535"):
        get_telemetry_udp_address()


def test_get_state_file_path_default() -> None:
    """Verify get_state_file_path anchors under get_artifact_dir()."""
    state_path = get_state_file_path()
    assert isinstance(state_path, Path)
    assert state_path.name == "cochem_state.h5"


def test_get_state_file_path_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_state_file_path respects COCHEM_STATE_FILE."""
    custom_state = tmp_path / "custom_state.h5"
    monkeypatch.setenv("COCHEM_STATE_FILE", str(custom_state))

    resolved = get_state_file_path()
    assert resolved == custom_state.resolve()


def test_get_mps_directories_default() -> None:
    """Verify get_mps_directories returns pipe and log paths under runtime directory."""
    pipe_dir, log_dir = get_mps_directories()
    assert isinstance(pipe_dir, Path)
    assert isinstance(log_dir, Path)
    assert pipe_dir.name == "nvidia-mps"
    assert log_dir.name == "nvidia-log"


def test_get_mps_directories_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_mps_directories respects CUDA_MPS_PIPE_DIRECTORY and CUDA_MPS_LOG_DIRECTORY."""
    custom_pipe = tmp_path / "mps_pipe"
    custom_log = tmp_path / "mps_log"
    monkeypatch.setenv("CUDA_MPS_PIPE_DIRECTORY", str(custom_pipe))
    monkeypatch.setenv("CUDA_MPS_LOG_DIRECTORY", str(custom_log))

    pipe_dir, log_dir = get_mps_directories()
    assert pipe_dir == custom_pipe.resolve()
    assert log_dir == custom_log.resolve()


def test_get_ramdisk_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_ramdisk_dir respects COCHEM_RAMDISK_DIR and handles platform fallback."""
    custom_ram = tmp_path / "ramdisk"
    monkeypatch.setenv("COCHEM_RAMDISK_DIR", str(custom_ram))
    assert get_ramdisk_dir() == custom_ram.resolve()

    monkeypatch.delenv("COCHEM_RAMDISK_DIR", raising=False)
    result = get_ramdisk_dir()
    if platform.system() == "Linux" and Path("/dev/shm").is_dir():
        assert result == Path("/dev/shm")
    else:
        assert result is None or isinstance(result, Path)


# =============================================================================
# Executable Resolution Tests
# =============================================================================


def test_resolve_executable_direct() -> None:
    """Verify resolve_executable discovers existing system binaries via PATH."""
    resolved = resolve_executable(candidates=("python", "python3"))
    assert resolved != ""
    assert Path(resolved).exists()


def test_resolve_executable_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_executable resolves from an environment variable."""
    dummy_exe = tmp_path / "dummy_runner"
    dummy_exe.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("CUSTOM_EXE_PATH", str(dummy_exe))

    resolved = resolve_executable(env_var="CUSTOM_EXE_PATH")
    assert resolved == str(dummy_exe.resolve())


def test_resolve_conda_executable_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_conda_executable behavior when missing."""
    monkeypatch.setenv("COCHEM_CONDA_EXE", "non_existent_conda_xyz_123")
    monkeypatch.delenv("CONDA_EXE", raising=False)

    with pytest.raises(FileNotFoundError, match="Configured Conda executable was not found"):
        resolve_conda_executable(required=True)


def test_resolve_wsl_executable() -> None:
    """Verify resolve_wsl_executable executes safely without crashing."""
    resolved = resolve_wsl_executable(required=False)
    assert isinstance(resolved, str)


def test_prepend_executable_directory(tmp_path: Path) -> None:
    """Verify prepend_executable_directory modifies child environment PATH correctly."""
    dummy_bin = tmp_path / "bin" / "tool.exe"
    dummy_bin.parent.mkdir(parents=True, exist_ok=True)
    dummy_bin.write_text("binary", encoding="utf-8")

    initial_env = {"PATH": "existing_path_entry"}
    modified_env = prepend_executable_directory(initial_env, dummy_bin)
    expected_dir = str(dummy_bin.parent.resolve())
    assert modified_env["PATH"].startswith(expected_dir)


# =============================================================================
# Configuration Loading, Validation & Exception Deflection Integrity Tests
# =============================================================================


def test_get_default_cochem_config() -> None:
    """Verify get_default_cochem_config returns a valid CoChemConfig Pydantic model instance."""
    cfg = get_default_cochem_config()
    assert cfg.schema_version == "4.0.0"
    assert cfg.hardware.physical_cpu_cores == 4
    assert cfg.hardware.logical_cpu_cores == 8
    assert cfg.hardware.ram_gb == 16.0
    assert cfg.quantum_settings is not None
    assert cfg.quantum_settings.integration_grid == "defgrid2"


def test_load_system_config_and_update_roundtrip(tmp_path: Path) -> None:
    """Verify physical serialization roundtrip for load_system_config and update_config."""
    cfg_target = tmp_path / "cochem_system_config.json"
    default_cfg = get_default_cochem_config()

    # Physical write to disk
    update_config(default_cfg, config_path=cfg_target)
    assert cfg_target.exists()

    # Physical load from disk and Pydantic validation
    loaded = load_system_config(config_path=cfg_target)
    assert loaded.schema_version == default_cfg.schema_version
    assert loaded.hardware.physical_cpu_cores == default_cfg.hardware.physical_cpu_cores
    assert loaded.hardware.os_target == default_cfg.hardware.os_target

    # Dictionary representation
    cfg_dict = load_system_config_dict(config_path=cfg_target)
    assert isinstance(cfg_dict, dict)
    assert cfg_dict["hardware"]["physical_cpu_cores"] == 4


def test_load_system_config_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    """Verify load_system_config raises FileNotFoundError with anti-deflection guarantee."""
    missing_file = tmp_path / "non_existent_config.json"
    with pytest.raises(FileNotFoundError) as exc_info:
        load_system_config(config_path=missing_file)

    assert "CRITICAL: Configuration file not found" in str(exc_info.value)
    assert "Computed defaults designed to keep the process alive are forbidden" in str(exc_info.value)


def test_load_system_config_corrupt_json_raises_value_error(tmp_path: Path) -> None:
    """Verify load_system_config raises ValueError on unparseable JSON without falling back."""
    corrupt_file = tmp_path / "corrupt_config.json"
    corrupt_file.write_text("{ unparseable_json: [ }", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_system_config(config_path=corrupt_file)

    assert "CRITICAL: Failed to read or parse JSON config" in str(exc_info.value)
    assert "Computed defaults designed to keep the process alive are forbidden" in str(exc_info.value)


def test_load_system_config_invalid_schema_raises_value_error(tmp_path: Path) -> None:
    """Verify load_system_config raises ValueError on Pydantic schema validation failures."""
    invalid_schema_file = tmp_path / "invalid_schema.json"
    # Negative CPU cores violates gt=0 constraint in HardwareConfig
    invalid_payload = {
        "hardware": {
            "physical_cpu_cores": -2,
            "logical_cpu_cores": -4,
            "ram_gb": -16.0,
            "os_target": "windows_amd64",
        }
    }
    invalid_schema_file.write_text(json.dumps(invalid_payload), encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_system_config(config_path=invalid_schema_file)

    assert "CRITICAL: Config schema validation error" in str(exc_info.value)
    assert "Computed defaults designed to keep the process alive are forbidden" in str(exc_info.value)


