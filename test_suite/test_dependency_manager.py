"""
Unit tests for CoChem Stage 0 DependencyManager (orchestrator/dependency_manager.py).
Adheres strictly to the physical validation mandate. Real filesystem entities,
virtual environments, subprocess invocations, and Pydantic schemas are validated directly.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import venv
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest
from pydantic import BaseModel, Field

# Import the module under test
from orchestrator.dependency_manager import (
    DependencyManager,
    DynamicVersionWalkStep,
    DynamicVersionWalkingResult,
    PipExecutionResult,
    CondaExecutionResult,
    is_abi_or_compilation_error,
    scan_for_local_wheel_fallback,
    sweep_intermediate_tmp_files,
    safe_remove_file,
    safe_remove_dir,
    resolve_conda_binary,
    walk_python_versions,
    DependencyManagerError,
    RollbackError,
    PipExecutionError,
    CondaExecutionError,
    VersionWalkingError,
)


class Stage0ExecutionMetadata(BaseModel):
    name: str = Field(..., description="Stage identifier name")
    count: int = Field(default=42, description="Execution counter")
    flags: List[str] = Field(default_factory=lambda: ["opt", "dft"])


# =============================================================================
# 1. CONTEXT MANAGER & TRACKING TESTS
# =============================================================================


def test_dependency_manager_initialization() -> None:
    dm = DependencyManager()
    assert len(dm.tracked_temp_files) == 0
    assert len(dm.tracked_temp_dirs) == 0
    assert len(dm.tracked_virtualenvs) == 0
    assert len(dm.tracked_conda_envs) == 0


def test_track_and_untrack_temp_file(tmp_path: Path) -> None:
    dm = DependencyManager()
    f1 = tmp_path / "test1.tmp"
    f1.write_text("temporary data", encoding="utf-8")

    tracked = dm.track_temp_file(f1)
    assert tracked == f1.resolve()
    assert tracked in dm.tracked_temp_files

    # Duplicate track should not double add
    dm.track_temp_file(f1)
    assert len(dm.tracked_temp_files) == 1

    dm.untrack_file(f1)
    assert f1.resolve() not in dm.tracked_temp_files


def test_track_and_untrack_temp_dir(tmp_path: Path) -> None:
    dm = DependencyManager()
    d1 = tmp_path / "stage_dir"
    d1.mkdir(parents=True, exist_ok=True)

    tracked = dm.track_temp_dir(d1)
    assert tracked == d1.resolve()
    assert tracked in dm.tracked_temp_dirs

    dm.untrack_dir(d1)
    assert d1.resolve() not in dm.tracked_temp_dirs


def test_create_temp_file_and_dir(tmp_path: Path) -> None:
    with DependencyManager() as dm:
        t_file = dm.create_temp_file(suffix=".tmp", prefix="test_cochem_", directory=tmp_path)
        assert t_file.exists()
        assert t_file.is_file()
        assert t_file in dm.tracked_temp_files

        t_dir = dm.create_temp_dir(prefix="test_stage_", directory=tmp_path)
        assert t_dir.exists()
        assert t_dir.is_dir()
        assert t_dir in dm.tracked_temp_dirs

        # Explicitly untrack so they aren't deleted on clean exit
        dm.untrack_file(t_file)
        dm.untrack_dir(t_dir)

    assert t_file.exists()
    assert t_dir.exists()


def test_rollback_on_exception(tmp_path: Path) -> None:
    t_file = None
    t_dir = None

    with pytest.raises(ValueError, match="Expected phase failure for testing"):
        with DependencyManager() as dm:
            t_file = dm.create_temp_file(suffix=".tmp", directory=tmp_path)
            t_dir = dm.create_temp_dir(prefix="fail_stage_", directory=tmp_path)

            assert t_file.exists()
            assert t_dir.exists()

            # Trigger exception inside context to test rollback
            raise ValueError("Expected phase failure for testing")

    # After rollback, tracked temporary files and directories must be destroyed
    assert t_file is not None and not t_file.exists()
    assert t_dir is not None and not t_dir.exists()


def test_no_rollback_on_successful_exit(tmp_path: Path) -> None:
    target_file = tmp_path / "permanent.txt"
    with DependencyManager() as dm:
        t_file = dm.create_temp_file(suffix=".tmp", directory=tmp_path)
        t_file.write_text("staged content", encoding="utf-8")
        # Commit by moving and untracking
        os.replace(t_file, target_file)
        dm.untrack_file(t_file)

    assert target_file.exists()
    assert target_file.read_text(encoding="utf-8") == "staged content"


# =============================================================================
# 2. ATOMIC STATE SERIALIZATION TESTS
# =============================================================================


def test_atomic_write_json_pydantic_and_dict(tmp_path: Path) -> None:
    dm = DependencyManager()
    target_json = tmp_path / "Registry" / "p1.json"

    model_data = Stage0ExecutionMetadata(name="Phase1Report", count=100, flags=["orca", "xtb"])
    result_path = dm.atomic_write_json(target_json, model_data)

    assert result_path.exists()
    assert result_path == target_json.resolve()

    loaded = json.loads(result_path.read_text(encoding="utf-8"))
    assert loaded["name"] == "Phase1Report"
    assert loaded["count"] == 100
    assert loaded["flags"] == ["orca", "xtb"]

    # Write dictionary
    dict_target = tmp_path / "Registry" / "dict_state.json"
    dict_data = {"phase": "p4", "status": "PASSED", "silos": 4}
    dm.atomic_write_json(dict_target, dict_data)

    loaded_dict = json.loads(dict_target.read_text(encoding="utf-8"))
    assert loaded_dict["status"] == "PASSED"


def test_atomic_write_json_cleans_temporary_on_error(tmp_path: Path) -> None:
    dm = DependencyManager()
    target = tmp_path / "corrupted.json"

    class NonSerializableObject:
        pass

    with pytest.raises(Exception):
        dm.atomic_write_json(target, NonSerializableObject())

    # Ensure no lingering .tmp files remain in directory
    tmp_files = list(tmp_path.glob("*.tmp*"))
    assert len(tmp_files) == 0
    assert not target.exists()


# =============================================================================
# 3. VIRTUAL ENVIRONMENT TRACKING & ROLLBACK
# =============================================================================


def test_virtualenv_tracking_and_rollback(tmp_path: Path) -> None:
    venv_dir = tmp_path / "test_silo_env"

    with pytest.raises(RuntimeError, match="Compilation failure encountered"):
        with DependencyManager() as dm:
            # Create a real physical venv without pip for execution speed
            venv.create(venv_dir, with_pip=False, clear=True)
            assert venv_dir.exists()

            dm.track_virtualenv(venv_dir)
            assert venv_dir.resolve() in dm.tracked_virtualenvs

            # Trigger downstream failure to test rollback
            raise RuntimeError("Compilation failure encountered")

    # Post-rollback: venv directory must be completely erased
    assert not venv_dir.exists()


# =============================================================================
# 4. PIP & CONDA SUBPROCESS CALL WRAPPER TESTS
# =============================================================================


def test_pip_command_execution_real() -> None:
    dm = DependencyManager()

    # Execute real python -m pip --version via current sys.executable
    result: PipExecutionResult = dm.run_pip_command(
        ["--version"],
        python_executable=sys.executable,
        timeout=30.0,
    )

    assert result.success is True
    assert result.returncode == 0
    assert "pip" in result.stdout.lower()
    assert result.duration_seconds >= 0.0


def test_pip_list_real() -> None:
    dm = DependencyManager()
    result = dm.pip_list(python_executable=sys.executable, timeout=30.0)

    assert result.success is True
    assert result.returncode == 0
    assert len(result.stdout) > 0


def test_pip_failure_handling() -> None:
    dm = DependencyManager()
    # Attempt to run with invalid non-existent argument
    result = dm.run_pip_command(
        ["--non-existent-pip-flag-xyz"],
        python_executable=sys.executable,
        timeout=15.0,
    )

    assert result.success is False
    assert result.returncode != 0
    assert len(result.stderr) > 0 or len(result.stdout) > 0


def test_pip_check_real() -> None:
    dm = DependencyManager()
    result = dm.pip_check(python_executable=sys.executable, timeout=30.0)
    assert isinstance(result, PipExecutionResult)
    assert result.duration_seconds >= 0.0
    assert result.executable_path is not None


def test_pip_install_uninstall_dry_run_args(tmp_path: Path) -> None:
    dm = DependencyManager()
    # Test pip install argument formatting with dry-run/no-deps
    result = dm.pip_install(
        packages=["pip"],
        python_executable=sys.executable,
        flags=["--dry-run"],
        upgrade=True,
        no_deps=True,
        timeout=30.0,
    )
    assert isinstance(result, PipExecutionResult)
    assert result.success is True
    assert "--dry-run" in result.command
    assert "--upgrade" in result.command
    assert "--no-deps" in result.command


def test_pip_check_raise_on_error() -> None:
    dm = DependencyManager()
    with pytest.raises(PipExecutionError):
        dm.run_pip_command(
            ["--invalid-flag-that-triggers-error"],
            python_executable=sys.executable,
            timeout=10.0,
            check=True,
        )


def test_conda_resolution_and_execution() -> None:
    dm = DependencyManager()
    conda_bin = resolve_conda_binary()
    if conda_bin:
        result = dm.run_conda_command(["--version"], timeout=15.0)
        assert result.returncode == 0
        assert "conda" in result.stdout.lower() or "mamba" in result.stdout.lower()
    else:
        with pytest.raises(FileNotFoundError):
            dm.run_conda_command(["--version"], conda_executable="non_existent_conda_binary_xyz")


def test_conda_env_tracking_and_rollback() -> None:
    dm = DependencyManager()
    dm.track_conda_env("test_env_staging")
    assert "test_env_staging" in dm.tracked_conda_envs
    dm.untrack_conda_env("test_env_staging")
    assert "test_env_staging" not in dm.tracked_conda_envs


# =============================================================================
# 5. DYNAMIC VERSION WALKING & COMPILATION / ABI ERROR DETECTION
# =============================================================================


def test_abi_compilation_error_detector() -> None:
    gcc_error = (
        "gcc: error: unrecognized command-line option '-mavx512f'\n"
        "error: command '/usr/bin/gcc' failed with exit code 1"
    )
    is_err, cat = is_abi_or_compilation_error(gcc_error)
    assert is_err is True
    assert cat == "COMPILATION_ERROR"

    msvc_error = "error: Microsoft Visual C++ 14.0 or greater is required. Get it with Microsoft C++ Build Tools"
    is_err, cat = is_abi_or_compilation_error(msvc_error)
    assert is_err is True
    assert cat == "COMPILATION_ERROR"

    abi_error = "RuntimeError: ABI tag mismatch between PyTorch C++ extension and Python runtime"
    is_err, cat = is_abi_or_compilation_error(abi_error)
    assert is_err is True
    assert cat == "ABI_TAG_MISMATCH"

    clean_log = "Successfully installed mace-torch-0.3.5"
    is_err, cat = is_abi_or_compilation_error(clean_log)
    assert is_err is False
    assert cat == "NONE"


def test_all_abi_compilation_error_categories() -> None:
    test_cases = [
        ("gcc: error: unrecognized option", "COMPILATION_ERROR"),
        ("fatal error: Python.h: No such file or directory", "MISSING_PYTHON_HEADER"),
        ("Microsoft Visual C++ 14.0 or greater is required", "COMPILATION_ERROR"),
        ("ABI tag mismatch between extensions", "ABI_TAG_MISMATCH"),
        ("undefined symbol: _Py_NoneStruct", "ABI_TAG_MISMATCH"),
        ("incompatible C++ ABI detected", "ABI_TAG_MISMATCH"),
        ("GLIBCXX_3.4.29 not found", "GLIBCXX_MISMATCH"),
        ("GLIBC_2.34 not found", "GLIBC_MISMATCH"),
        ("Failed building wheel for scikit-learn", "WHEEL_BUILD_FAILURE"),
        ("Could not build wheels for scipy", "WHEEL_BUILD_FAILURE"),
        ("Unsupported Python version 3.14", "UNSUPPORTED_VERSION"),
        ("Requires-Python >=3.8, <3.12", "UNSUPPORTED_VERSION"),
        ("No matching distribution found for nonexistent", "NO_DISTRIBUTION_FOUND"),
    ]

    for log_snippet, expected_cat in test_cases:
        is_err, cat = is_abi_or_compilation_error(log_snippet)
        assert is_err is True, f"Failed on snippet: {log_snippet}"
        assert cat == expected_cat, f"Category mismatch for {log_snippet}: got {cat}, expected {expected_cat}"


def test_local_wheel_fallback_scanner(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheel_cache"
    wheel_dir.mkdir(parents=True, exist_ok=True)

    # Create physical wheel filename
    test_whl = wheel_dir / "molsym-1.0.0-cp311-cp311-win_amd64.whl"
    test_whl.write_bytes(b"PK\x03\x04")  # Zip header bytes

    test_tar = wheel_dir / "pyscf-2.6.0.tar.gz"
    test_tar.write_bytes(b"\x1f\x8b")  # Gzip magic bytes

    found_whl = scan_for_local_wheel_fallback("molsym", [wheel_dir], target_python="3.11")
    assert found_whl is not None
    assert found_whl.name == "molsym-1.0.0-cp311-cp311-win_amd64.whl"

    found_tar = scan_for_local_wheel_fallback("pyscf", [wheel_dir], target_python="3.11")
    assert found_tar is not None
    assert found_tar.name == "pyscf-2.6.0.tar.gz"

    not_found = scan_for_local_wheel_fallback("nonexistent_pkg", [wheel_dir])
    assert not_found is None


def test_dynamic_version_walking_workflow(tmp_path: Path) -> None:
    dm = DependencyManager()
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir(parents=True, exist_ok=True)

    fallback_whl = wheel_dir / "mace_torch-0.3.4-cp310-cp310-win_amd64.whl"
    fallback_whl.write_bytes(b"PK\x03\x04")

    # Installer callback testing version stepdown to 3.10 where wheel is found
    def stepdown_installer(version: str, wheel_path: Path | None) -> Tuple[bool, str]:
        if version in ("3.12", "3.11") and wheel_path is None:
            return False, "fatal error: Python.h: No such file or directory. command 'gcc' failed"
        if version == "3.10" or wheel_path is not None:
            return True, "Successfully installed"
        return False, "Unsupported version"

    result: DynamicVersionWalkingResult = dm.walk_python_versions(
        package_name="mace_torch",
        initial_version="3.12",
        version_chain=["3.12", "3.11", "3.10"],
        wheel_search_dirs=[wheel_dir],
        install_action=stepdown_installer,
    )

    assert result.status == "PASSED"
    assert result.resolved_version == "3.10"
    assert result.used_local_fallback is True
    assert result.fallback_binary_path is not None
    assert len(result.steps) == 3
    assert result.steps[0].attempted_version == "3.12"
    assert result.steps[0].success is False
    assert result.steps[1].attempted_version == "3.11"
    assert result.steps[1].success is False
    assert result.steps[2].attempted_version == "3.10"
    assert result.steps[2].success is True


def test_dynamic_version_walk_step_validation() -> None:
    # Valid step
    step = DynamicVersionWalkStep(
        attempted_version="3.11",
        success=True,
        fallback_wheel_found="/path/to/wheel.whl",
        duration_seconds=1.23,
    )
    assert step.attempted_version == "3.11"
    assert step.success is True

    # Invalid version should raise ValueError
    with pytest.raises(ValueError, match="Invalid Python version format"):
        DynamicVersionWalkStep(attempted_version="python3_invalid", success=False)


def test_top_level_walk_python_versions_function(tmp_path: Path) -> None:
    result = walk_python_versions(
        package_name="test_pkg",
        initial_version="3.11",
        version_chain=["3.11", "3.10"],
        wheel_search_dirs=[tmp_path],
    )
    assert isinstance(result, DynamicVersionWalkingResult)
    assert len(result.steps) == 2


# =============================================================================
# 6. STERILITY & SWEEP PROTOCOL TESTS
# =============================================================================


def test_workspace_sterility_sweep(tmp_path: Path) -> None:
    # Create persistent configuration files
    real_cfg = tmp_path / "config.json"
    real_cfg.write_text("{}", encoding="utf-8")

    # Create intermediate .tmp files and directories
    tmp_file1 = tmp_path / "p1.json.tmp.a1b2c3"
    tmp_file1.write_text("partial", encoding="utf-8")

    tmp_file2 = tmp_path / "sub" / "p2.tmp"
    tmp_file2.parent.mkdir(parents=True, exist_ok=True)
    tmp_file2.write_text("partial2", encoding="utf-8")

    purged = sweep_intermediate_tmp_files(tmp_path)
    assert len(purged) == 2
    assert not tmp_file1.exists()
    assert not tmp_file2.exists()
    assert real_cfg.exists()


def test_safe_remove_helpers(tmp_path: Path) -> None:
    f = tmp_path / "to_delete.txt"
    f.write_text("content", encoding="utf-8")
    assert safe_remove_file(f) is True
    assert not f.exists()
    # Deleting non-existent should succeed idempotently
    assert safe_remove_file(f) is True

    d = tmp_path / "to_delete_dir"
    d.mkdir(parents=True, exist_ok=True)
    (d / "inner.txt").write_text("inner", encoding="utf-8")
    assert safe_remove_dir(d) is True
    assert not d.exists()
    assert safe_remove_dir(d) is True


def test_atomic_write_json_overwrites_readonly_target(tmp_path: Path) -> None:
    import stat
    dm = DependencyManager()
    target_json = tmp_path / "readonly_target.json"
    target_json.write_text("{\"old\": true}", encoding="utf-8")
    # Make target read-only
    target_json.chmod(stat.S_IREAD)

    new_data = {"new_value": 42, "status": "OVERWRITTEN"}
    res = dm.atomic_write_json(target_json, new_data)

    assert res.exists()
    loaded = json.loads(res.read_text(encoding="utf-8"))
    assert loaded["new_value"] == 42
    assert loaded["status"] == "OVERWRITTEN"


def test_local_wheel_fallback_no_prefix_collisions(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheels"
    wheel_dir.mkdir(parents=True, exist_ok=True)

    # Create prefix collision files
    (wheel_dir / "torchvision-0.15.0-cp311-cp311-win_amd64.whl").write_bytes(b"PK\x03\x04")
    (wheel_dir / "torch_geometric-2.0.0-py3-none-any.whl").write_bytes(b"PK\x03\x04")
    (wheel_dir / "torch_sparse-0.6.17.tar.gz").write_bytes(b"\x1f\x8b")

    # Scanning for 'torch' should not match torchvision, torch_geometric, or torch_sparse
    found = scan_for_local_wheel_fallback("torch", [wheel_dir], target_python="3.11")
    assert found is None

    # Create exact torch wheel
    (wheel_dir / "torch-2.1.0-cp311-cp311-win_amd64.whl").write_bytes(b"PK\x03\x04")
    found_exact = scan_for_local_wheel_fallback("torch", [wheel_dir], target_python="3.11")
    assert found_exact is not None
    assert found_exact.name == "torch-2.1.0-cp311-cp311-win_amd64.whl"


def test_dynamic_version_walking_complete_failure(tmp_path: Path) -> None:
    dm = DependencyManager()

    def always_fails(version: str, wheel_path: Path | None) -> Tuple[bool, str]:
        return False, f"gcc: error: compilation failed for Python {version}"

    result = dm.walk_python_versions(
        package_name="unresolvable_pkg",
        initial_version="3.12",
        version_chain=["3.12", "3.11"],
        wheel_search_dirs=[tmp_path],
        install_action=always_fails,
    )

    assert result.status == "FAILED"
    assert result.resolved_version is None
    assert result.used_local_fallback is False
    assert len(result.steps) == 2
    assert result.steps[0].success is False
    assert "COMPILATION_ERROR" in (result.steps[0].error_summary or "")
    assert result.steps[1].success is False

