"""Zero-Mock test suite for TOPOS Tripartite Execution and Process Lifecycle (test_topos_tripartite_execution.py).

Validates Suggestions #41 and #43:
- Pydantic v2 validation constraints (negative threshold rejection, nonexistent path rejection)
- Real physical water monomer XYZ structure configuration
- Decoupled background subprocess spawn with SHA-256 state serialization
- OS PID lockfile generation and active PID validation
- Graceful process-tree cancellation and PID file cleanup via psutil
"""

import os
import time
from pathlib import Path
import psutil
import pytest
from pydantic import ValidationError

from frontend.cochem_topos_ui import (
    ToposRuntimeConfig,
    cancel_topos_search,
    execute_topos_search,
    serialize_topos_runtime_config,
)


def test_topos_runtime_config_validation(tmp_path: Path):
    """Assert Pydantic v2 rejects invalid RMSD, negative parameters, and nonexistent files."""
    valid_xyz = tmp_path / "water.xyz"
    valid_xyz.write_text(
        "3\nWater monomer\nO 0.000 0.000 0.117\nH 0.000 0.757 -0.469\nH 0.000 -0.757 -0.469\n",
        encoding="utf-8",
    )
    hdf5_out = tmp_path / "conformers.h5"

    # 1. Nonexistent structure path rejection
    nonexistent = tmp_path / "nonexistent.xyz"
    with pytest.raises(ValidationError):
        ToposRuntimeConfig(
            structure_path=nonexistent,
            output_hdf5_path=hdf5_out,
            workspace_dir=tmp_path,
        )

    # 2. Negative or out-of-bounds RMSD threshold rejection (ge=0.05)
    with pytest.raises(ValidationError):
        ToposRuntimeConfig(
            structure_path=valid_xyz,
            output_hdf5_path=hdf5_out,
            workspace_dir=tmp_path,
            rmsd_threshold_angstrom=-0.15,
        )

    # 3. Energy window out of bounds (< 0.5 kcal)
    with pytest.raises(ValidationError):
        ToposRuntimeConfig(
            structure_path=valid_xyz,
            output_hdf5_path=hdf5_out,
            workspace_dir=tmp_path,
            energy_window_kcal=0.1,
        )

    # 4. Valid configuration instantiation on authentic water structure
    config = ToposRuntimeConfig(
        structure_path=valid_xyz,
        output_hdf5_path=hdf5_out,
        workspace_dir=tmp_path,
        conformer_engine="CREST_NCI",
        energy_window_kcal=6.0,
        rmsd_threshold_angstrom=0.15,
        rotational_constant_threshold=0.005,
        max_conformers=20,
        num_workers=1,
    )
    assert config.structure_path == valid_xyz
    assert config.rmsd_threshold_angstrom == 0.15


def test_topos_process_lifecycle_and_cancellation(tmp_path: Path):
    """Assert dry-run subprocess creation, active PID verification, and graceful cancellation."""
    water_xyz = tmp_path / "water_monomer.xyz"
    water_xyz.write_text(
        "3\nWater Monomer benchmark\nO 0.000000 0.000000 0.117400\nH 0.000000 0.757000 -0.469600\nH 0.000000 -0.757000 -0.469600\n",
        encoding="utf-8",
    )
    hdf5_out = tmp_path / "landscape.h5"
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    config = ToposRuntimeConfig(
        structure_path=water_xyz,
        output_hdf5_path=hdf5_out,
        workspace_dir=workspace_dir,
    )

    # Validate state serialization with SHA-256 digest
    state_file, digest = serialize_topos_runtime_config(config)
    assert state_file.exists()
    assert len(digest) == 64

    # Spawn decoupled background subprocess in dry-run mode
    proc = execute_topos_search(config, dry_run=True)
    pid_file = workspace_dir / "topos_run.pid"

    try:
        # Verify PID file exists and contains a running OS process
        time.sleep(0.5)
        assert pid_file.exists(), "PID lockfile was not generated."
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        assert psutil.pid_exists(pid), f"PID {pid} recorded in lockfile is not active."

        # Verify cancellation shuts down process tree and removes lockfile
        cancelled = cancel_topos_search(workspace_dir)
        assert cancelled is True, "cancel_topos_search failed to execute."

        # Allow OS time to reap process
        time.sleep(0.5)
        assert not pid_file.exists(), "topos_run.pid lockfile was not cleaned up after cancellation."
        assert not psutil.pid_exists(pid), f"Process {pid} remained alive after cancellation."
    finally:
        # Fallback safeguard in case assertion failed prior to cancellation
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.kill()
            except Exception:
                pass
        if pid_file.exists():
            pid_file.unlink(missing_ok=True)
