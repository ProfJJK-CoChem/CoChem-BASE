"""
Unit Test Suite for CoChem-BASE: setup/calc_wsl.py (Mirrored in test_suite)
Verifies all auditor remediations:
1. EngineInfo model handling, SiloPathsSchema synchronization, and SHA-256 checksum update.
2. OpenMPI version parsing supporting Debian/Ubuntu outputs and robust exception shielding.
3. Safe tar/zip archive extraction preventing directory traversal and out-of-bounds symlinks.
4. Robust WSL kernel and environment detection across env vars, uname, and /proc.
"""

import io
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import pytest

import setup.calc_wsl as calc_wsl_mod
from cochem_base.config_loader import (
    get_default_cochem_config,
    load_system_config,
    resolve_config_path,
    update_config,
)
from core_engine.cochem_core_registry_schema import (
    CoChemConfig,
    EngineInfo,
    EnginePaths,
    HardwareSchema,
    HPCConfig,
    OSTarget,
    SiloConfig,
    SiloPathsSchema,
)
from setup.calc_wsl import (
    _available_executable,
    _find_staged_orca,
    _safe_extract,
    check_openmpi_version,
    cleanup_zombies,
    locate_orca,
    provision_openmpi,
    provision_orca,
    register_calculation_state,
    run_calculation_setup,
    verify_wsl_kernel,
)


def test_verify_wsl_kernel_env_vars(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    assert verify_wsl_kernel() is True

    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.setenv("WSL_INTEROP", "/run/WSL/1_interop")
    assert verify_wsl_kernel() is True


def test_verify_wsl_kernel_platform_release(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.delenv("WSL_INTEROP", raising=False)
    monkeypatch.setattr(platform, "release", lambda: "5.15.153.1-microsoft-standard-WSL2")
    assert verify_wsl_kernel() is True


def test_verify_wsl_kernel_platform_version(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.delenv("WSL_INTEROP", raising=False)
    monkeypatch.setattr(platform, "release", lambda: "5.15.0-generic")
    monkeypatch.setattr(platform, "version", lambda: "#1 SMP Microsoft WSL2")
    assert verify_wsl_kernel() is True


def test_verify_wsl_kernel_not_wsl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.delenv("WSL_INTEROP", raising=False)
    monkeypatch.setattr(platform, "release", lambda: "6.5.0-44-generic")
    monkeypatch.setattr(platform, "version", lambda: "#44-Ubuntu SMP PREEMPT_DYNAMIC")
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    assert verify_wsl_kernel() is False


@pytest.mark.parametrize(
    "raw_stdout, expected_version",
    [
        ("mpirun (Open MPI) 4.1.2\nReport bugs to...", "4.1.2"),
        ("mpirun (Open MPI) 4.1.6\n", "4.1.6"),
        ("mpirun (Open MPI) v4.1.2\n", "4.1.2"),
        ("Open MPI: 4.1.2\n", "4.1.2"),
        ("Open MPI 4.1.2a1\n", "4.1.2"),
        ("mpirun (Open MPI) 5.0.3\n", "5.0.3"),
        ("v4.1.2\n", "4.1.2"),
        ("v4.1\n", "4.1"),
        ("mpirun 4.1.2\n", "4.1.2"),
    ],
)
def test_check_openmpi_version_formats(raw_stdout: str, expected_version: str, monkeypatch: pytest.MonkeyPatch):
    class DummyProcess:
        stdout = raw_stdout
        returncode = 0

    monkeypatch.setattr(calc_wsl_mod, "safe_subprocess_run", lambda *args, **kwargs: DummyProcess())
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: DummyProcess())
    assert check_openmpi_version("/usr/bin/mpirun") == expected_version


def test_check_openmpi_version_parse_failure(monkeypatch: pytest.MonkeyPatch):
    class DummyProcess:
        stdout = "No digits or recognized version tokens here whatsoever"
        returncode = 0

    monkeypatch.setattr(calc_wsl_mod, "safe_subprocess_run", lambda *args, **kwargs: DummyProcess())
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: DummyProcess())
    with pytest.raises(RuntimeError, match="Command to check OpenMPI version failed"):
        check_openmpi_version("/usr/bin/mpirun")


def test_check_openmpi_version_subprocess_errors(monkeypatch: pytest.MonkeyPatch):
    def raise_called_process(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["mpirun", "--version"])

    monkeypatch.setattr(calc_wsl_mod, "safe_subprocess_run", raise_called_process)
    monkeypatch.setattr(subprocess, "run", raise_called_process)
    with pytest.raises(RuntimeError, match="Command to check OpenMPI version failed"):
        check_openmpi_version("/usr/bin/mpirun")


def test_provision_openmpi_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_mpi = tmp_path / "mpirun"
    fake_mpi.write_text("mpi binary")
    monkeypatch.setenv("MPI_CMD", str(fake_mpi))

    class DummyProcess:
        stdout = "mpirun (Open MPI) 4.1.2\n"
        returncode = 0

    monkeypatch.setattr(calc_wsl_mod, "safe_subprocess_run", lambda *args, **kwargs: DummyProcess())
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: DummyProcess())
    path = provision_openmpi()
    assert path == str(fake_mpi.resolve())


def test_provision_openmpi_install_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    installed_mpi = tmp_path / "installed_mpirun"
    monkeypatch.delenv("MPI_CMD", raising=False)
    monkeypatch.setattr(shutil, "which", lambda x: None)

    commands_executed = []

    def fake_runner(cmd, *args, **kwargs):
        commands_executed.append(cmd)
        if "install" in cmd:
            installed_mpi.write_text("installed binary")
            monkeypatch.setenv("MPI_CMD", str(installed_mpi))
            monkeypatch.setattr(shutil, "which", lambda x: str(installed_mpi) if "mpi" in str(x) else None)
        class DummyProc:
            stdout = "mpirun (Open MPI) 4.1.2\n"
            returncode = 0
        return DummyProc()

    monkeypatch.setattr(calc_wsl_mod, "safe_subprocess_run", fake_runner)
    monkeypatch.setattr(subprocess, "run", fake_runner)
    path = provision_openmpi()
    assert path == str(installed_mpi.resolve())


def test_available_executable(tmp_path: Path):
    assert _available_executable(None) is None
    assert _available_executable("") is None
    exe = tmp_path / "test_cmd"
    exe.write_text("dummy")
    assert _available_executable(str(exe)) == str(exe.resolve())


def test_safe_extract_zip_valid_and_invalid(tmp_path: Path):
    valid_zip = tmp_path / "valid.zip"
    with zipfile.ZipFile(valid_zip, "w") as zf:
        zf.writestr("orca/orca.txt", "orca binary data")

    dest_valid = tmp_path / "dest_valid"
    _safe_extract(valid_zip, dest_valid)
    assert (dest_valid / "orca" / "orca.txt").read_text() == "orca binary data"

    unsafe_zip = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(unsafe_zip, "w") as zf:
        zf.writestr("../evil.txt", "evil data")

    dest_unsafe = tmp_path / "dest_unsafe"
    with pytest.raises(ValueError, match="Archive contains an unsafe path"):
        _safe_extract(unsafe_zip, dest_unsafe)


def test_safe_extract_tar_with_relative_symlinks_and_hardlinks(tmp_path: Path):
    tar_path = tmp_path / "test_orca.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        orca_data = b"binary content"
        ti_file = tarfile.TarInfo(name="orca_dir/orca")
        ti_file.size = len(orca_data)
        tar.addfile(ti_file, io.BytesIO(orca_data))

        lib_data = b"lib content"
        ti_lib = tarfile.TarInfo(name="orca_dir/lib/liborca.so")
        ti_lib.size = len(lib_data)
        tar.addfile(ti_lib, io.BytesIO(lib_data))

        ti_sym = tarfile.TarInfo(name="orca_dir/lib/liborca.so.6")
        ti_sym.type = tarfile.SYMTYPE
        ti_sym.linkname = "liborca.so"
        tar.addfile(ti_sym)

        ti_lnk = tarfile.TarInfo(name="orca_dir/orca_alias")
        ti_lnk.type = tarfile.LNKTYPE
        ti_lnk.linkname = "orca_dir/orca"
        tar.addfile(ti_lnk)

    dest_dir = tmp_path / "extracted_orca"
    _safe_extract(tar_path, dest_dir)
    assert (dest_dir / "orca_dir" / "orca").exists()


def test_safe_extract_tar_rejects_unsafe_symlinks(tmp_path: Path):
    tar_path = tmp_path / "evil_sym.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        ti_evil = tarfile.TarInfo(name="orca_dir/lib/escape")
        ti_evil.type = tarfile.SYMTYPE
        ti_evil.linkname = "../../../../../etc/passwd"
        tar.addfile(ti_evil)

    dest_dir = tmp_path / "extracted_evil"
    with pytest.raises(ValueError, match="Archive contains an unsafe symlink"):
        _safe_extract(tar_path, dest_dir)


def test_safe_extract_tar_rejects_absolute_symlinks(tmp_path: Path):
    tar_path = tmp_path / "evil_abs_sym.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        ti_evil = tarfile.TarInfo(name="orca_dir/lib/escape_abs")
        ti_evil.type = tarfile.SYMTYPE
        ti_evil.linkname = "/etc/shadow"
        tar.addfile(ti_evil)

    dest_dir = tmp_path / "extracted_abs"
    with pytest.raises(ValueError, match="Archive contains an unsafe symlink"):
        _safe_extract(tar_path, dest_dir)


def test_safe_extract_tar_rejects_unsafe_hardlinks(tmp_path: Path):
    tar_path = tmp_path / "evil_hard.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        ti_evil = tarfile.TarInfo(name="orca_dir/escape_hard")
        ti_evil.type = tarfile.LNKTYPE
        ti_evil.linkname = "../../outside"
        tar.addfile(ti_evil)

    dest_dir = tmp_path / "extracted_hard"
    with pytest.raises(ValueError, match="Archive contains an unsafe hardlink"):
        _safe_extract(tar_path, dest_dir)


@pytest.mark.parametrize(
    "archive_name, tar_mode",
    [
        ("orca-6.1.1.tar.gz", "w:gz"),
        ("ORCA-6.1.1.tar.bz2", "w:bz2"),
        ("orca-6.1.1.tar.xz", "w:xz"),
        ("orca-6.1.1.tar", "w:"),
        ("orca-6.1.1.tgz", "w:gz"),
    ],
)
def test_locate_orca_with_tar_archives(archive_name: str, tar_mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ORCA_CMD", raising=False)
    monkeypatch.setattr(shutil, "which", lambda x: None)
    engine_dir = tmp_path / f"Engines_{archive_name}"
    engine_dir.mkdir(parents=True, exist_ok=True)

    archive_path = engine_dir / archive_name
    with tarfile.open(archive_path, tar_mode) as tar:
        orca_name = "orca_6_1_1/orca"
        orca_data = b"executable payload"
        ti = tarfile.TarInfo(name=orca_name)
        ti.size = len(orca_data)
        tar.addfile(ti, io.BytesIO(orca_data))

    discovered = locate_orca(engine_dir)
    assert discovered is not None
    assert Path(discovered).is_file()


def test_locate_orca_with_zip_archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ORCA_CMD", raising=False)
    monkeypatch.setattr(shutil, "which", lambda x: None)
    engine_dir = tmp_path / "Engines_zip"
    engine_dir.mkdir(parents=True, exist_ok=True)

    archive_path = engine_dir / "orca-6.1.1.zip"
    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.writestr("orca_6_1_1/orca", "executable payload")

    discovered = locate_orca(engine_dir)
    assert discovered is not None
    assert Path(discovered).is_file()


def test_provision_orca_missing_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ORCA_CMD", raising=False)
    monkeypatch.setattr(shutil, "which", lambda x: None)
    engine_dir = tmp_path / "Engines_empty"
    engine_dir.mkdir(parents=True, exist_ok=True)

    with pytest.raises(RuntimeError, match="ORCA engine missing"):
        provision_orca(engine_dir)


def test_register_calculation_state_full_remediation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / "cochem_system_config.json"
    monkeypatch.setenv("COCHEM_CONFIG", str(config_file))

    initial_config = get_default_cochem_config()
    update_config(initial_config, config_file)

    fake_orca = str((tmp_path / "opt" / "orca" / "orca").resolve())
    fake_mpi = str((tmp_path / "usr" / "bin" / "mpirun").resolve())

    saved_path = register_calculation_state(
        mpi_path=fake_mpi,
        orca_path=fake_orca,
        environment="Local-Windows (WSL)",
    )
    assert saved_path == config_file

    loaded = load_system_config(config_file)
    assert isinstance(loaded.engines, dict)
    assert loaded.engines["orca"].status == "ready"
    assert loaded.engines["orca"].path == fake_orca
    assert loaded.engines["mpirun"].status == "ready"
    assert loaded.engines["mpirun"].path == fake_mpi

    assert loaded.silo_paths.orca_path == fake_orca
    assert loaded.silo_paths.orca_binary_path == fake_orca
    assert loaded.silo_paths.mpirun_path == fake_mpi
    assert loaded.silo_paths.mpirun_binary_path == fake_mpi

    assert loaded.hpc.execution_mode == "Local-Windows (WSL)"

    assert loaded.registry_checksum is not None
    assert len(loaded.registry_checksum) == 64
    assert loaded.verify_checksum() is True


def test_register_calculation_state_flexible_signatures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / "cochem_system_config.json"
    monkeypatch.setenv("COCHEM_CONFIG", str(config_file))
    update_config(get_default_cochem_config(), config_file)

    fake_orca = str((tmp_path / "orca").resolve())
    fake_mpi = str((tmp_path / "mpirun").resolve())

    register_calculation_state(fake_mpi, fake_orca)
    cfg1 = load_system_config(config_file)
    assert cfg1.engines["orca"].path == fake_orca
    assert cfg1.engines["mpirun"].path == fake_mpi
    assert cfg1.hpc.execution_mode == "Local-Windows (WSL)"
    assert cfg1.verify_checksum() is True

    register_calculation_state("Local-Windows (WSL)", fake_orca, fake_mpi)
    cfg2 = load_system_config(config_file)
    assert cfg2.engines["orca"].path == fake_orca
    assert cfg2.engines["mpirun"].path == fake_mpi
    assert cfg2.verify_checksum() is True


def test_register_calculation_state_with_enginepaths_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / "cochem_system_config.json"
    monkeypatch.setenv("COCHEM_CONFIG", str(config_file))

    hw = HardwareSchema(
        cpu_physical_cores=8,
        physical_cpu_cores=8,
        logical_cpu_cores=16,
        ram_gb=32.0,
        os_target=OSTarget.LOCAL_WINDOWS,
    )
    config = CoChemConfig(
        hardware=hw,
        engines=EnginePaths(
            orca=EngineInfo(status="missing", path=None),
            mpirun=EngineInfo(status="missing", path=None),
        ),
    )
    update_config(config, config_file)

    fake_orca = str((tmp_path / "orca").resolve())
    fake_mpi = str((tmp_path / "mpirun").resolve())

    register_calculation_state(fake_mpi, fake_orca)

    loaded = load_system_config(config_file)
    assert loaded.hpc.execution_mode == "Local-Windows (WSL)"
    assert loaded.verify_checksum() is True


def test_verify_wsl_kernel_uname(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.delenv("WSL_INTEROP", raising=False)
    monkeypatch.setattr(platform, "release", lambda: "6.5.0-generic")
    monkeypatch.setattr(platform, "version", lambda: "#44-Ubuntu")
    monkeypatch.setattr(Path, "is_file", lambda self: False)

    class DummyUname:
        release = "5.15.153.1-microsoft-standard-WSL2"
        version = "#1 SMP Microsoft WSL2"

    monkeypatch.setattr(os, "uname", lambda: DummyUname(), raising=False)
    assert verify_wsl_kernel() is True


def test_verify_wsl_kernel_proc_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.delenv("WSL_INTEROP", raising=False)
    monkeypatch.setattr(platform, "release", lambda: "generic")
    monkeypatch.setattr(platform, "version", lambda: "generic")

    proc_file = tmp_path / "proc_version"
    raw_content = "Linux version 5.15.153.1-microsoft-standard-WSL2 (gcc version 11.2.0)"
    proc_file.write_text(raw_content)

    original_is_file = Path.is_file

    def mock_is_file(self):
        if "proc" in str(self):
            return True
        return original_is_file(self)

    monkeypatch.setattr(Path, "is_file", mock_is_file)
    monkeypatch.setattr(Path, "read_text", lambda self, *args, **kwargs: raw_content)
    assert verify_wsl_kernel() is True


def test_register_calculation_state_none_silo_and_hpc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / "cochem_system_config.json"
    monkeypatch.setenv("COCHEM_CONFIG", str(config_file))

    class MockCustomConfig:
        def __init__(self):
            self.engines = {}
            self.silo_paths = None
            self.hpc = None
            self.registry_checksum = None

        def update_checksum(self):
            self.registry_checksum = "dummy_checksum"

    mock_cfg = MockCustomConfig()
    monkeypatch.setattr(calc_wsl_mod, "load_system_config", lambda *a, **kw: mock_cfg)
    monkeypatch.setattr(calc_wsl_mod, "update_config", lambda cfg, path: None)

    fake_orca = str((tmp_path / "orca").resolve())
    fake_mpi = str((tmp_path / "mpirun").resolve())

    register_calculation_state(fake_mpi, fake_orca)

    assert mock_cfg.silo_paths is not None
    assert mock_cfg.silo_paths.orca_path == fake_orca
    assert mock_cfg.silo_paths.mpirun_path == fake_mpi
    assert mock_cfg.hpc is not None
    assert mock_cfg.hpc.execution_mode == "Local-Windows (WSL)"


def test_cli_help_flag_handling(capsys: pytest.CaptureFixture):
    """Verify --help flag prints usage and exits cleanly with 0."""
    orig_argv = sys.argv
    try:
        sys.argv = ["calc_wsl.py", "--help"]
        with pytest.raises(SystemExit) as exc_info:
            run_calculation_setup()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Usage: python calc_wsl.py" in captured.out
    finally:
        sys.argv = orig_argv


def test_run_calculation_setup_non_wsl_guard(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.delenv("WSL_INTEROP", raising=False)
    monkeypatch.setattr(platform, "release", lambda: "generic_macos")
    monkeypatch.setattr(platform, "version", lambda: "Darwin Kernel")
    monkeypatch.setattr(Path, "is_file", lambda self: False)

    with pytest.raises(RuntimeError, match="FATAL: Target environment is not WSL"):
        run_calculation_setup()


def test_cleanup_zombies_shielding():
    """Verify cleanup_zombies executes safely without raising unexpected exceptions."""
    cleanup_zombies()


def test_calc_wsl_all_exports():
    import setup.calc_wsl as mod
    assert hasattr(mod, "__all__")
    for symbol in mod.__all__:
        assert hasattr(mod, symbol)
