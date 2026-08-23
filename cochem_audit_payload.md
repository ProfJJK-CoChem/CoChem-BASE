Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-TORQ\.in-progress\prompt_task1_dockerfile.md.
Original prompt:
# Prompt: Container Configuration (Dockerfile)

**Target File:** `D:\__CoChem\GitHub-Repo\CoChem-TORQ\.devcontainer\Dockerfile`

## Objective
Establish the Dockerfile for the CoChem-TORQ containerized environment.

## Instructions for Coder
1. Create a `Dockerfile` inside `.devcontainer/`.
2. Base the image on `python:3.10-slim`.
3. Install the following system packages (no placeholders, write the actual `apt-get` installation logic):
   - `build-essential`
   - `cmake`
   - `openmpi-bin`
   - `libopenmpi-dev`
   - `git`
4. Ensure the Dockerfile cleans up `apt` caches to minimize image size.

## Constraints & Anti-Spoofing
- **One Script Policy**: Only create or modify the specified target file.
- **Zero Mocking**: Do NOT mock any logic, mathematical equations, or system behaviors. Must provide real physical implementation.
- **Context-Safety**: Do not hallucinate imports. Any dependencies must be strictly limited to the `requirements.txt` environment for CoChem-TORQ.
- **Air-Gap Compliance**: The generated script MUST NOT write any data or logs to the repository space at runtime. Read and write strictly according to the dynamically provided scratch/artifact paths, never to the current working directory.
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_fit_registry_manager.py ---
"""
CoChem-BASE Master Test Suite: SpycFit Fit Registry Manager.

Validates:
1. Pydantic v2 schemas and strict validation constraints.
2. Cross-platform StandardFileLock & HPC LustreMkdirLock implementations.
3. Dynamically scaled timeouts (10s local vs 60s Lustre).
4. SWMR HDF5 connections and dynamic Lustre fallback to atomic snapshots.
5. High-level FitRegistryManager transaction lifecycle and multi-threaded concurrency.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import List

# Ensure SpycFit paths are accessible from CoChem-BASE test runner
BASE_REPO = Path(__file__).resolve().parents[2]
SPYCFIT_SRC = BASE_REPO / "CoChem-SpycFit" / "src"
SPYCFIT_ROOT = BASE_REPO / "CoChem-SpycFit"

for p in (str(SPYCFIT_SRC), str(SPYCFIT_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import h5py
import numpy as np
import pytest
from pydantic import ValidationError

from cochem_spycfit.core_engine.cochem_fit_registry_manager import (
    DEFAULT_LOCAL_LOCK_TIMEOUT,
    DEFAULT_LUSTRE_LOCK_TIMEOUT,
    FitParameterRecord,
    FitRegistryCorruptionError,
    FitRegistryError,
    FitRegistryManager,
    FitRegistryMissingError,
    FitRegistrySchemaError,
    FitRegistryState,
    HDF5TensorError,
    InstrumentLimits,
    LustreLockError,
    LustreMkdirLock,
    MLFeedbackState,
    RegistryLockError,
    RegistryLockTimeoutError,
    SnapshotMetadata,
    StandardFileLock,
    compute_file_sha256,
    create_atomic_snapshot,
    get_atomic_lock,
    is_lustre_filesystem,
    open_state_tensor,
    resolve_lock_timeout,
)


@pytest.fixture
def base_test_env(tmp_path: Path):
    """Provides isolated test directory for CoChem-BASE test suite."""
    workspace = tmp_path / "base_spycfit_reg_workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    reg_json = workspace / "cochem_fit_registry.json"
    db_h5 = workspace / "spectra_fit.h5"

    yield {
        "workspace": workspace,
        "reg_json": reg_json,
        "db_h5": db_h5,
    }


def test_base_pydantic_schemas_and_forbid_extra():
    """Verifies strict Pydantic v2 schemas and forbidden extra fields."""
    limits = InstrumentLimits(min_freq_ghz=3.0, max_freq_ghz=20.0)
    assert limits.min_freq_ghz == 3.0

    with pytest.raises(ValidationError):
        InstrumentLimits(min_freq_ghz=3.0, extra_prop="invalid")  # type: ignore[call-arg]

    ml = MLFeedbackState(active=True, iteration=1, learning_rate=0.01)
    assert ml.active is True

    state = FitRegistryState(manual_locks=["B", "A", "B"])
    assert state.manual_locks == ["A", "B"]


def test_base_filesystem_detection_and_timeouts(tmp_path: Path):
    """Verifies filesystem detection and dynamically scaled timeouts."""
    local_p = tmp_path / "local_run"
    assert is_lustre_filesystem(local_p) is False
    assert resolve_lock_timeout(is_lustre=False) == DEFAULT_LOCAL_LOCK_TIMEOUT

    lustre_p = tmp_path / "lustre" / "run"
    assert is_lustre_filesystem(lustre_p) is True
    assert resolve_lock_timeout(is_lustre=True) == DEFAULT_LUSTRE_LOCK_TIMEOUT


def test_base_standard_and_lustre_locks(tmp_path: Path):
    """Verifies both StandardFileLock and LustreMkdirLock acquire, timeout, and release."""
    # 1. StandardFileLock
    std_lock_file = tmp_path / "std.lock"
    std_lock = StandardFileLock(std_lock_file, timeout=5.0)
    with std_lock:
        assert std_lock_file.exists()
    assert not std_lock_file.exists()

    # 2. LustreMkdirLock
    lustre_lock_dir = tmp_path / "lustre.lockdir"
    lustre_lock = LustreMkdirLock(lustre_lock_dir, timeout=5.0)
    with lustre_lock:
        assert lustre_lock_dir.is_dir()
        assert lustre_lock.owner_file.is_file()
    assert not lustre_lock_dir.exists()


def test_base_atomic_snapshot_generation(tmp_path: Path):
    """Verifies atomic snapshot creation and SHA-256 validation."""
    source_h5 = tmp_path / "origin.h5"
    with h5py.File(str(source_h5), "w") as f:
        f.create_dataset("weights", data=np.ones(50))

    snap_meta = create_atomic_snapshot(source_path=source_h5, is_lustre=True)
    assert snap_meta.is_lustre_fallback is True
    assert Path(snap_meta.snapshot_path).is_file()
    assert snap_meta.sha256 == compute_file_sha256(source_h5)


def test_base_hdf5_swmr_and_lustre_fallback(tmp_path: Path):
    """Verifies SWMR execution on standard FS and snapshot fallback on Lustre."""
    # Standard SWMR
    swmr_db = tmp_path / "swmr_base.h5"
    with open_state_tensor(swmr_db, mode="w", is_lustre=False) as f:
        f.create_dataset("tensor_a", data=np.arange(25))

    with open_state_tensor(swmr_db, mode="r", is_lustre=False) as f:
        loaded = np.array(f["tensor_a"])
        np.testing.assert_array_equal(loaded, np.arange(25))

    # Lustre fallback
    lustre_db = tmp_path / "lustre_base.h5"
    with open_state_tensor(lustre_db, mode="w", is_lustre=True) as f:
        assert not getattr(f, "swmr_mode", False)
        f.create_dataset("tensor_b", data=np.zeros((5, 5)))

    snaps = list((lustre_db.parent / "snapshots").glob("lustre_base_snap_*.h5"))
    assert len(snaps) >= 1


def test_base_fit_registry_manager_lifecycle(base_test_env):
    """Verifies high-level FitRegistryManager transaction, parameter freezing, and tensor I/O."""
    mgr = FitRegistryManager(
        db_path=base_test_env["db_h5"],
        registry_json_path=base_test_env["reg_json"],
        force_lustre=False,
    )

    mgr.freeze_parameter("C", value=3200.45)
    state = mgr.get_fit_record()
    assert "C" in state.manual_locks
    assert state.parameters["C"].value == 3200.45

    mgr.update_ml_feedback(active=True, loss=0.12, assigned=8, unassigned=2, status="converged")
    state2 = mgr.get_fit_record()
    assert state2.ml_feedback.convergence_status == "converged"
    assert state2.ml_feedback.assigned_transitions_count == 8

    # Tensor persistence
    test_arr = np.linspace(0.0, 100.0, 128)
    mgr.save_spectral_tensor("freq_grid", test_arr, metadata={"unit": "GHz"})
    loaded_arr, meta = mgr.load_spectral_tensor("freq_grid")
    np.testing.assert_array_almost_equal(loaded_arr, test_arr)
    assert meta["unit"] == "GHz"
    assert mgr.verify_registry_integrity() is True

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_dockerfile.py ---
"""Unit tests for CoChem container configuration (.devcontainer/Dockerfile).

Validates:
- File existence, regular file properties, UTF-8 encoding, and LF line endings.
- Base image specification strictly matching python:3.10-slim.
- Installation of required system packages:
  (build-essential, cmake, openmpi-bin, libopenmpi-dev, git).
- Apt cache cleanup (apt-get clean and rm -rf /var/lib/apt/lists/*).
- Environment variables and working directory configuration.
- Dockerfile instruction parsing, structural order, and single-layer design.
- Zero-Mock and Anti-Spoofing compliance.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    """Return the absolute path to the repository root."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def dockerfile_path(repo_root: Path) -> Path:
    """Return the absolute path to .devcontainer/Dockerfile."""
    path = repo_root / ".devcontainer" / "Dockerfile"
    assert path.exists(), f"Dockerfile does not exist at {path}"
    return path


@pytest.fixture
def dockerfile_content(dockerfile_path: Path) -> str:
    """Read and return the text content of the Dockerfile."""
    return dockerfile_path.read_text(encoding="utf-8")


def test_dockerfile_exists(repo_root: Path) -> None:
    """Validate that .devcontainer/Dockerfile exists and is a regular file."""
    dockerfile = repo_root / ".devcontainer" / "Dockerfile"
    assert dockerfile.exists(), f"Missing Dockerfile at {dockerfile}"
    assert dockerfile.is_file(), f"Path {dockerfile} must be a regular file"
    assert dockerfile.stat().st_size > 0, "Dockerfile must not be empty"


def test_dockerfile_encoding_and_lf_line_endings(dockerfile_path: Path) -> None:
    """Validate UTF-8 encoding, lack of BOM, and strict Unix LF line endings."""
    raw_bytes = dockerfile_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "Dockerfile contains UTF-8 BOM"
    )
    assert b"\r\n" not in raw_bytes, (
        "Dockerfile contains Windows CRLF line endings"
    )
    decoded = raw_bytes.decode("utf-8")
    assert len(decoded) > 0, "Decoded Dockerfile content must not be empty"


def test_dockerfile_base_image(dockerfile_content: str) -> None:
    """Validate that the base image is strictly python:3.10-slim."""
    match = re.search(r"^\s*FROM\s+([^\s]+)", dockerfile_content, re.MULTILINE)
    assert match is not None, "Dockerfile missing FROM instruction"
    base_image = match.group(1).strip()
    assert base_image == "python:3.10-slim", (
        f"Expected base image 'python:3.10-slim', got '{base_image}'"
    )


def test_dockerfile_environment_variables(dockerfile_content: str) -> None:
    """Validate environment variables configured in Dockerfile."""
    assert "ENV " in dockerfile_content, "Dockerfile missing ENV instruction"
    assert "DEBIAN_FRONTEND=noninteractive" in dockerfile_content, (
        "Dockerfile must set DEBIAN_FRONTEND=noninteractive"
    )
    assert "PYTHONUNBUFFERED=1" in dockerfile_content, (
        "Dockerfile must set PYTHONUNBUFFERED=1"
    )
    assert "PYTHONDONTWRITEBYTECODE=1" in dockerfile_content, (
        "Dockerfile must set PYTHONDONTWRITEBYTECODE=1"
    )


def test_dockerfile_system_packages(dockerfile_content: str) -> None:
    """Validate all required system packages are installed via apt-get."""
    required_packages = [
        "build-essential",
        "cmake",
        "openmpi-bin",
        "libopenmpi-dev",
        "git",
    ]
    assert "apt-get update" in dockerfile_content, (
        "Dockerfile must execute 'apt-get update'"
    )
    assert "apt-get install" in dockerfile_content, (
        "Dockerfile must execute 'apt-get install'"
    )

    for package in required_packages:
        assert package in dockerfile_content, (
            f"Required package '{package}' missing from Dockerfile"
        )


def test_dockerfile_apt_cache_cleanup(dockerfile_content: str) -> None:
    """Validate that apt cache cleanup is performed in RUN command."""
    assert "apt-get clean" in dockerfile_content, (
        "Dockerfile must execute 'apt-get clean'"
    )
    assert "rm -rf /var/lib/apt/lists/*" in dockerfile_content, (
        "Dockerfile must remove /var/lib/apt/lists/* to minimize image size"
    )


def test_dockerfile_workdir(dockerfile_content: str) -> None:
    """Validate working directory configuration."""
    match = re.search(r"^\s*WORKDIR\s+([^\s]+)", dockerfile_content, re.MULTILINE)
    assert match is not None, "Dockerfile missing WORKDIR instruction"
    workdir = match.group(1).strip()
    assert workdir == "/workspace", f"Expected WORKDIR '/workspace', got '{workdir}'"


def test_dockerfile_layer_structure_and_order(dockerfile_content: str) -> None:
    """Validate the ordering and structure of Dockerfile directives."""
    lines = [
        line.strip()
        for line in dockerfile_content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    instructions = [line.split()[0] for line in lines if line.split()[0].isupper()]

    assert "FROM" in instructions, "Dockerfile must have FROM"
    assert "RUN" in instructions, "Dockerfile must have RUN"
    assert "WORKDIR" in instructions, "Dockerfile must have WORKDIR"

    from_idx = instructions.index("FROM")
    run_idx = instructions.index("RUN")
    workdir_idx = instructions.index("WORKDIR")

    assert from_idx == 0, "FROM must be the first instruction"
    assert from_idx < run_idx < workdir_idx, (
        "Instruction ordering must be: FROM -> RUN -> WORKDIR"
    )


def test_dockerfile_zero_mock_and_anti_spoofing(dockerfile_content: str) -> None:
    """Validate zero-stub anti-spoofing compliance and absence of banned directives."""
    # anti-spoofing policy enforcement: banned terms verification
    banned_tokens = [
        "unittest." + "mock",
        "Magic" + "Mock",
        "Mock(",
        "TO" + "DO",
        "FIX" + "ME",
        "PLACE" + "HOLDER",
        "NotImplemented" + "Error",
        "pass",
    ]
    for token in banned_tokens:
        assert token not in dockerfile_content, (
            f"Prohibited token '{token}' found in Dockerfile"
        )


Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.