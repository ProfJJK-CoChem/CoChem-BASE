"""
Unit Test Suite for CoChem-BASE: setup/calc_native.py (Mirrored in test_suite)
Verifies all auditor remediations:
1. EngineInfo model handling, SiloPathsSchema synchronization, and SHA-256 checksum update.
2. OpenMPI version parsing supporting Debian/Ubuntu outputs and robust exception shielding.
3. Safe tar/zip archive extraction preventing directory traversal and out-of-bounds symlinks while allowing safe internal symlinks.
4. locate_orca extended archive extensions (.tar.xz, .tar.gz, .tar.bz2, .tar, .tgz, .zip).
5. Robust calculation_environment detection across platforms and env vars.
6. Flexible signature, CLI help, and __all__ exports.
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

import setup.calc_native as calc_native_mod
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
from setup.calc_native import (
    _available_executable,
    _find_staged_orca,
    _safe_extract,
    calculation_environment,
    check_openmpi_version,
    cleanup_zombies,
    locate_orca,
    parse_openmpi_version_string,
    register_calculation_state,
    run_calculation_setup,
)


def test_calculation_environment_github_actions(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert calculation_environment() == "GitHub Actions"


def test_calculation_environment_platforms(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    assert calculation_environment() == "Local-MacOS (OrbStack)"

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    assert calculation_environment() == "Local-Linux (Deb)"

    monkeypatch.setattr(platform, "system", lambda: "Windows")
    with pytest.raises(RuntimeError, match="Native calculation setup does not support host platform"):
        calculation_environment()


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
def test_parse_openmpi_version_formats(raw_stdout: str, expected_version: str):
    assert parse_openmpi_version_string(raw_stdout) == expected_version


def test_parse_openmpi_version_parse_failure():
    with pytest.raises(ValueError, match="Could not parse OpenMPI version from"):
        parse_openmpi_version_string("No digits or recognized version tokens here whatsoever")


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
        environment="Local-MacOS (OrbStack)",
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

    assert loaded.hpc.execution_mode == "Local-MacOS (OrbStack)"

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
    assert cfg1.verify_checksum() is True

    register_calculation_state("Local-Linux (Deb)", fake_orca, fake_mpi)
    cfg2 = load_system_config(config_file)
    assert cfg2.engines["orca"].path == fake_orca
    assert cfg2.engines["mpirun"].path == fake_mpi
    assert cfg2.hpc.execution_mode == "Local-Linux (Deb)"
    assert cfg2.verify_checksum() is True


def test_register_calculation_state_with_enginepaths_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / "cochem_system_config.json"
    monkeypatch.setenv("COCHEM_CONFIG", str(config_file))

    hw = HardwareSchema(
        cpu_physical_cores=8,
        physical_cpu_cores=8,
        logical_cpu_cores=16,
        ram_gb=32.0,
        os_target=OSTarget.LOCAL_LINUX,
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
    assert loaded.verify_checksum() is True


def test_register_calculation_state_with_empty_enginepaths_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / "cochem_system_config.json"
    monkeypatch.setenv("COCHEM_CONFIG", str(config_file))

    hw = HardwareSchema(
        cpu_physical_cores=8,
        physical_cpu_cores=8,
        logical_cpu_cores=16,
        ram_gb=32.0,
        os_target=OSTarget.LOCAL_LINUX,
    )
    config = CoChemConfig(
        hardware=hw,
        engines=EnginePaths(),  # orca=None, mpirun=None
    )
    update_config(config, config_file)

    fake_orca = str((tmp_path / "orca").resolve())
    fake_mpi = str((tmp_path / "mpirun").resolve())

    register_calculation_state(fake_mpi, fake_orca)

    loaded = load_system_config(config_file)
    assert loaded.verify_checksum() is True
    assert loaded.engines["orca"].path == fake_orca
    assert loaded.engines["mpirun"].path == fake_mpi


def test_cleanup_zombies_shielding():
    """Verify cleanup_zombies executes safely without raising unexpected exceptions."""
    cleanup_zombies()


def test_calc_native_all_exports():
    import setup.calc_native as mod
    assert hasattr(mod, "__all__")
    for symbol in mod.__all__:
        assert hasattr(mod, symbol)

