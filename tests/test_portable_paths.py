import os
import platform
from pathlib import Path

from cochem_base.config_loader import (
    get_mps_directories,
    get_runtime_dir,
    get_state_file_path,
    get_telemetry_socket_path,
    get_telemetry_transport,
    get_telemetry_udp_address,
    prepend_executable_directory,
    resolve_conda_executable,
    resolve_executable,
    resolve_mapped_path,
    resolve_wsl_executable,
)


def test_relative_paths_use_explicit_anchor(tmp_path: Path) -> None:
    assert resolve_mapped_path("nested/data", tmp_path) == (tmp_path / "nested" / "data").resolve()


def test_runtime_state_and_socket_mappings(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    artifact_dir = tmp_path / "artifacts"
    monkeypatch.setenv("COCHEM_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(artifact_dir))

    assert get_runtime_dir() == runtime_dir.resolve()
    assert get_telemetry_socket_path() == runtime_dir.resolve() / "cochem_telemetry.sock"
    assert get_state_file_path() == artifact_dir.resolve() / "cochem_state.h5"
    assert get_mps_directories() == (
        runtime_dir.resolve() / "nvidia-mps",
        runtime_dir.resolve() / "nvidia-log",
    )


def test_telemetry_transport_mapping(monkeypatch) -> None:
    monkeypatch.setenv("COCHEM_TELEMETRY_TRANSPORT", "udp")
    monkeypatch.setenv("COCHEM_TELEMETRY_HOST", "127.0.0.2")
    monkeypatch.setenv("COCHEM_TELEMETRY_PORT", "9876")
    assert get_telemetry_transport() == "udp"
    assert get_telemetry_udp_address() == ("127.0.0.2", 9876)


def test_directory_and_environment_executable_mapping(monkeypatch, tmp_path: Path) -> None:
    executable_suffix = ".exe" if platform.system() == "Windows" else ""
    tool_dir = tmp_path / "tools"
    tool_dir.mkdir()
    orca = tool_dir / f"orca{executable_suffix}"
    conda = tool_dir / f"conda{executable_suffix}"
    orca.touch()
    conda.touch()

    assert resolve_executable(str(tool_dir), candidates=("orca",)) == str(orca.resolve())
    monkeypatch.setenv("COCHEM_CONDA_EXE", str(conda))
    assert resolve_conda_executable() == str(conda.resolve())


def test_child_path_injection_is_idempotent(tmp_path: Path) -> None:
    executable = tmp_path / "bin" / "tool"
    executable.parent.mkdir()
    executable.touch()
    env = {"PATH": os.pathsep.join(("existing-a", "existing-b"))}

    prepend_executable_directory(env, executable)
    prepend_executable_directory(env, executable)

    assert env["PATH"].split(os.pathsep) == [
        str(executable.parent.resolve()),
        "existing-a",
        "existing-b",
    ]


def test_state_file_can_be_mapped_relative_to_artifacts(monkeypatch, tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(artifact_dir))
    monkeypatch.setenv("COCHEM_STATE_FILE", "state/registry.h5")
    assert get_state_file_path() == (artifact_dir / "state" / "registry.h5").resolve()


def test_optional_wsl_mapping_reports_missing_command(monkeypatch) -> None:
    monkeypatch.delenv("COCHEM_WSL_EXE", raising=False)
    monkeypatch.setattr("cochem_base.config_loader.shutil.which", lambda _: None)
    assert resolve_wsl_executable(required=False) == ""
