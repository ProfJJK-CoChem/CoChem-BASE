"""
CoChem-TORQ: Comprehensive Unit Test Suite (Phases 1 through 5)
================================================================
Authentic Physical Unit Tests covering all 11 Modules and Deliverables:
- Phase 1: cochem_torq_init, cochem_torq_schema, cochem_h5_healer
- Phase 2: cochem_torq_vault, cochem_torq_topology, cochem_torq_alignment
- Phase 3: cochem_torq_mace, cochem_torq_quench
- Phase 4: cochem_torq_slicer
- Phase 5: cochem_torq_engine, cochem_torq_watchdog
- Proxy Interface Layer: cochem_base.* re-exports
"""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import List, Tuple

import h5py
import numpy as np
import pandas as pd
import psutil
import pyarrow as pa
import pytest

from cochem_base.exceptions import (
    CoChemIntegrityError,
    DispersionMissingError,
    InvalidHessianStrategyError,
    MethodMatrixViolationError,
    ProvenanceErrorCode,
    SpinContaminationError,
)
from cochem_h5_healer import (
    create_swmr_lock,
    detect_zombie_pids,
    force_release_swmr,
    inspect_h5_integrity,
    remove_swmr_lock,
)
from cochem_torq_alignment import (
    diagonalize_principal_axes,
    translate_com_to_origin,
)
from cochem_torq_engine import (
    opi_persistent_threading,
    route_method_matrix,
    validate_method_matrix_compliance,
)

# Module Imports from Root
from cochem_torq_init import (
    TorqAirgapViolationError,
    cleanup_ipc_buffers,
    init_torq_logger,
    register_ipc_cleanup,
    resolve_torq_environment,
    verify_airgap,
)
from cochem_torq_mace import (
    evaluate_pes_point,
    generate_adaptive_grid,
    onnx_cpu_fallback,
    rotate_dihedral_angle,
)
from cochem_torq_quench import (
    detect_covalent_clashes,
    execute_jiggle_quench,
    execute_soft_quench,
)
from cochem_torq_schema import (
    TorqHardwareSchema,
    TorqSchemaValidationError,
    format_5_whys_error,
    validate_registry_state,
)
from cochem_torq_slicer import (
    HARTREE_TO_CM1,
    HARTREE_TO_KCAL_MOL,
    fit_continuous_splines,
    wkb_tunneling_estimator,
)
from cochem_torq_topology import (
    build_molecular_graph,
    detect_5_option_dihedrals,
    ring_strain_guard,
    select_active_torsions,
)
from cochem_torq_vault import (
    CIAAW_ISOTOPIC_MASSES,
    fetch_topos_matrices,
    parse_external_xyz,
    standardize_geometry_dataframe,
)
from cochem_torq_watchdog import (
    dynamic_memory_backoff,
    execute_grid_collapse,
    monitor_stdout_stream,
)

# ==============================================================================
# PHASE 1: cochem_torq_init tests
# ==============================================================================


class TestTorqInit:
    """Test suite for cochem_torq_init.py."""

    def test_resolve_torq_environment_default(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        isolated_home_dir = tmp_path / "isolated_home"
        isolated_home_dir.mkdir()
        monkeypatch.setenv("HOME", str(isolated_home_dir))
        monkeypatch.setenv("USERPROFILE", str(isolated_home_dir))
        monkeypatch.delenv("COCHEM_ARTIFACTS", raising=False)
        monkeypatch.delenv("COCHEM_TORQ_LIB", raising=False)
        monkeypatch.delenv("COCHEM_SCRATCH", raising=False)
        monkeypatch.delenv("COCHEM_UPLOADS", raising=False)

        env_dirs = resolve_torq_environment()
        assert "artifacts" in env_dirs
        assert "torq_lib" in env_dirs
        assert "scratch" in env_dirs
        assert "uploads" in env_dirs

        for p in env_dirs.values():
            assert p.exists()
            assert p.is_dir()

    def test_resolve_torq_environment_custom_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        custom_art = tmp_path / "custom_artifacts"
        custom_lib = tmp_path / "custom_lib"
        monkeypatch.setenv("COCHEM_ARTIFACTS", str(custom_art))
        monkeypatch.setenv("COCHEM_TORQ_LIB", str(custom_lib))

        env_dirs = resolve_torq_environment()
        assert env_dirs["artifacts"] == custom_art.resolve()
        assert env_dirs["torq_lib"] == custom_lib.resolve()
        assert custom_art.exists()
        assert custom_lib.exists()

    def test_verify_airgap_success(self, tmp_path: Path) -> None:
        exec_dir = tmp_path / "exec_space"
        artifact_dir = tmp_path / "artifact_space"
        exec_dir.mkdir()
        artifact_dir.mkdir()

        assert verify_airgap(exec_dir=exec_dir, artifact_dir=artifact_dir) is True

    def test_verify_airgap_failure_identical(self, tmp_path: Path) -> None:
        colliding_dir = tmp_path / "same_space"
        colliding_dir.mkdir()

        with pytest.raises(TorqAirgapViolationError) as exc_info:
            verify_airgap(exec_dir=colliding_dir, artifact_dir=colliding_dir)
        assert exc_info.value.error_code == ProvenanceErrorCode.INTEGRITY_VIOLATION

    def test_verify_airgap_failure_nested(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()
        nested_exec = artifact_dir / "nested_exec"
        nested_exec.mkdir()

        with pytest.raises(TorqAirgapViolationError) as exc_info:
            verify_airgap(exec_dir=nested_exec, artifact_dir=artifact_dir)
        assert exc_info.value.error_code == ProvenanceErrorCode.INTEGRITY_VIOLATION

    def test_register_and_cleanup_ipc_buffers(self, tmp_path: Path) -> None:
        scratch = tmp_path / "scratch_ipc"
        scratch.mkdir()

        # Create authentic test IPC buffer files
        shm_file = scratch / "test.shm"
        ipc_file = scratch / "buffer.ipc"
        lock_file = scratch / "state.lock"
        keep_file = scratch / "important_data.dat"

        shm_file.write_text("shm_data")
        ipc_file.write_text("ipc_data")
        lock_file.write_text("lock_data")
        keep_file.write_text("keep_data")

        # Call cleanup directly
        reaped = cleanup_ipc_buffers(scratch)
        assert reaped == 3
        assert not shm_file.exists()
        assert not ipc_file.exists()
        assert not lock_file.exists()
        assert keep_file.exists()

        # Test hook registration
        hook = register_ipc_cleanup(scratch)
        assert callable(hook)
        hook()  # Run hook manually

    def test_init_torq_logger(self) -> None:
        logger = init_torq_logger("Test-Logger-Init", logging.DEBUG)
        assert logger.name == "Test-Logger-Init"
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) >= 1


# ==============================================================================
# PHASE 1: cochem_torq_schema tests
# ==============================================================================


class TestTorqSchema:
    """Test suite for cochem_torq_schema.py."""

    def test_torq_hardware_schema_valid(self, tmp_path: Path) -> None:
        scratch = tmp_path / "scratch"
        artifacts = tmp_path / "artifacts"
        torq_lib = tmp_path / "lib"
        scratch.mkdir()
        artifacts.mkdir()
        torq_lib.mkdir()

        schema = TorqHardwareSchema(
            mpi_threads=8,
            gpu_vram_gb=16.0,
            gpu_device_ids=[0, 1],
            maxcore_mb=4096,
            scratch_dir=scratch,
            artifacts_dir=artifacts,
            torq_lib_dir=torq_lib,
            cuda_enabled=True,
        )
        assert schema.mpi_threads == 8
        assert schema.gpu_vram_gb == 16.0
        assert schema.maxcore_mb == 4096
        assert schema.scratch_dir == scratch.resolve()
        assert schema.artifacts_dir == artifacts.resolve()

    def test_torq_hardware_schema_invalid_threads(self, tmp_path: Path) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TorqHardwareSchema(
                mpi_threads=0,  # Must be >= 1
                scratch_dir=tmp_path / "s",
                artifacts_dir=tmp_path / "a",
                torq_lib_dir=tmp_path / "l",
            )

    def test_torq_hardware_schema_airgap_collision(self, tmp_path: Path) -> None:
        from pydantic import ValidationError

        same_dir = tmp_path / "shared"
        same_dir.mkdir()
        with pytest.raises(ValidationError):
            TorqHardwareSchema(
                scratch_dir=same_dir,
                artifacts_dir=same_dir,
                torq_lib_dir=tmp_path / "l",
                strict_airgap=True,
            )

        parent_dir = tmp_path / "parent_art"
        child_scratch = parent_dir / "child_scratch"
        parent_dir.mkdir()
        child_scratch.mkdir()
        with pytest.raises(ValidationError):
            TorqHardwareSchema(
                scratch_dir=child_scratch,
                artifacts_dir=parent_dir,
                torq_lib_dir=tmp_path / "l",
                strict_airgap=True,
            )

    def test_validate_registry_state_dict(self, tmp_path: Path) -> None:
        scratch = tmp_path / "scratch"
        artifacts = tmp_path / "artifacts"
        torq_lib = tmp_path / "lib"
        scratch.mkdir()
        artifacts.mkdir()
        torq_lib.mkdir()

        data = {
            "mpi_threads": 4,
            "gpu_vram_gb": 8.0,
            "gpu_device_ids": [0],
            "maxcore_mb": 2048,
            "scratch_dir": str(scratch),
            "artifacts_dir": str(artifacts),
            "torq_lib_dir": str(torq_lib),
            "cuda_enabled": True,
        }
        schema = validate_registry_state(data)
        assert isinstance(schema, TorqHardwareSchema)
        assert schema.mpi_threads == 4

    def test_validate_registry_state_json_file(self, tmp_path: Path) -> None:
        scratch = tmp_path / "scratch"
        artifacts = tmp_path / "artifacts"
        torq_lib = tmp_path / "lib"
        scratch.mkdir()
        artifacts.mkdir()
        torq_lib.mkdir()

        json_path = tmp_path / "cochem_system_config.json"
        data = {
            "mpi_threads": 16,
            "gpu_vram_gb": 24.0,
            "gpu_device_ids": [0],
            "maxcore_mb": 8192,
            "scratch_dir": str(scratch),
            "artifacts_dir": str(artifacts),
            "torq_lib_dir": str(torq_lib),
            "cuda_enabled": False,
        }
        with open(json_path, "w", encoding="utf-8") as fp:
            json.dump(data, fp)

        schema = validate_registry_state(json_path)
        assert schema.mpi_threads == 16
        assert schema.maxcore_mb == 8192

    def test_validate_registry_state_5_whys_on_missing_file(self, tmp_path: Path) -> None:
        missing_file = tmp_path / "non_existent.json"
        with pytest.raises(TorqSchemaValidationError) as exc_info:
            validate_registry_state(missing_file)

        assert exc_info.value.five_whys_trace is not None
        assert "Why 1 (Symptom)" in exc_info.value.five_whys_trace
        assert "Why 5 (Architectural Resolution)" in exc_info.value.five_whys_trace

    def test_format_5_whys_error(self) -> None:
        trace = format_5_whys_error(
            ValueError("Negative threads"),
            {
                "field": "mpi_threads",
                "value": "-4",
                "rule": "Threads must be >= 1",
                "origin": "test_input",
                "remediation": "Set mpi_threads >= 1",
            },
        )
        assert "Why 1" in trace
        assert "Why 2" in trace
        assert "Why 3" in trace
        assert "Why 4" in trace
        assert "Why 5" in trace
        assert "-4" in trace


# ==============================================================================
# PHASE 1: cochem_h5_healer tests
# ==============================================================================


class TestH5Healer:
    """Test suite for cochem_h5_healer.py."""

    def test_create_and_remove_swmr_lock(self, tmp_path: Path) -> None:
        h5_path = tmp_path / "landscape.h5"
        lock_path = create_swmr_lock(h5_path)

        assert lock_path.exists()
        with open(lock_path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        assert data["pid"] == os.getpid()
        assert data["mode"] == "SWMR_WRITE"

        removed = remove_swmr_lock(h5_path)
        assert removed is True
        assert not lock_path.exists()

    def test_detect_zombie_pids_dead(self, tmp_path: Path) -> None:
        h5_path = tmp_path / "dead_proc.h5"
        dead_pid = 99999999
        while psutil.pid_exists(dead_pid):
            dead_pid -= 1

        create_swmr_lock(h5_path, pid=dead_pid)
        zombies = detect_zombie_pids(h5_path)
        assert dead_pid in zombies

    def test_detect_zombie_pids_alive(self, tmp_path: Path) -> None:
        h5_path = tmp_path / "alive_proc.h5"
        create_swmr_lock(h5_path, pid=os.getpid())
        zombies = detect_zombie_pids(h5_path)
        assert os.getpid() not in zombies
        remove_swmr_lock(h5_path)

    def test_force_release_swmr_dead_pid(self, tmp_path: Path) -> None:
        h5_path = tmp_path / "zombie_target.h5"
        with h5py.File(h5_path, "w") as fp:
            fp.create_dataset("test_data", data=np.array([1.0, 2.0, 3.0]))

        dead_pid = 88888888
        create_swmr_lock(h5_path, pid=dead_pid)

        res = force_release_swmr(h5_path, force=False)
        assert res["lock_released"] is True
        assert dead_pid in res["reaped_pids"]
        assert res["file_healthy"] is True

    def test_force_release_swmr_with_force_flag(self, tmp_path: Path) -> None:
        h5_path = tmp_path / "forced_target.h5"
        create_swmr_lock(h5_path, pid=os.getpid())

        res = force_release_swmr(h5_path, force=True)
        assert res["lock_released"] is True
        assert res["file_healthy"] is True

    def test_inspect_h5_integrity(self, tmp_path: Path) -> None:
        h5_path = tmp_path / "integrity_check.h5"
        with h5py.File(h5_path, "w") as fp:
            fp.create_group("conformers")
        assert inspect_h5_integrity(h5_path) is True

        corrupt_h5 = tmp_path / "corrupt.h5"
        corrupt_h5.write_text("NOT AN HDF5 FILE")
        assert inspect_h5_integrity(corrupt_h5) is False


# ==============================================================================
# PHASE 2: cochem_torq_vault tests
# ==============================================================================


class TestTorqVault:
    """Test suite for cochem_torq_vault.py."""

    def test_ciaaw_exact_masses(self) -> None:
        assert CIAAW_ISOTOPIC_MASSES["H"] == pytest.approx(1.00782503223, rel=1e-9)
        assert CIAAW_ISOTOPIC_MASSES["C"] == 12.00000000000
        assert CIAAW_ISOTOPIC_MASSES["O"] == pytest.approx(15.99491461957, rel=1e-9)
        assert CIAAW_ISOTOPIC_MASSES["N"] == pytest.approx(14.00307400443, rel=1e-9)
        assert CIAAW_ISOTOPIC_MASSES["F"] == pytest.approx(18.99840316273, rel=1e-9)
        assert CIAAW_ISOTOPIC_MASSES["Cl"] == pytest.approx(34.96885271, rel=1e-7)

    def test_parse_external_xyz_valid(self) -> None:
        xyz_content = """3
Water molecule [D]
O  0.000000  0.000000  0.117300
H  0.000000  0.757200 -0.469200
H  0.000000 -0.757200 -0.469200
"""
        parsed = parse_external_xyz(xyz_content, sanitize=True)
        assert parsed["atom_count"] == 3
        assert parsed["symbols"] == ["O", "H", "H"]
        assert parsed["coordinates"].shape == (3, 3)
        assert parsed["masses"][0] == pytest.approx(15.99491461957, rel=1e-9)
        assert parsed["atomic_numbers"][0] == 8
        assert parsed["provenance"] == "[D]"
        assert len(parsed["sha256_hash"]) == 64
        assert isinstance(parsed["dataframe"], pd.DataFrame)
        assert isinstance(parsed["arrow_table"], pa.Table)

    def test_parse_external_xyz_clash_detection(self) -> None:
        clash_xyz = """2
Severe clash
C  0.000000  0.000000  0.000000
C  0.000000  0.000000  0.100000
"""
        with pytest.raises(CoChemIntegrityError) as exc_info:
            parse_external_xyz(clash_xyz, sanitize=True)
        assert exc_info.value.error_code == ProvenanceErrorCode.PATHOLOGY_CLASH

    def test_parse_external_xyz_corrupt_format(self) -> None:
        corrupt_xyz = "NOT A VALID XYZ"
        with pytest.raises(CoChemIntegrityError) as exc_info:
            parse_external_xyz(corrupt_xyz)
        assert exc_info.value.error_code == ProvenanceErrorCode.INTEGRITY_VIOLATION

    def test_fetch_topos_matrices(self, tmp_path: Path) -> None:
        h5_path = tmp_path / "landscape.h5"
        with h5py.File(h5_path, "w") as fp:
            conf_grp = fp.create_group("conformers")
            c1 = conf_grp.create_group("conf_001")
            c1.create_dataset(
                "coordinates", data=np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float64)
            )
            c1.create_dataset("symbols", data=[b"C", b"O"])
            c1.attrs["energy_hartree"] = -113.82910
            c1.attrs["gbw_path"] = "/vol/scratch/conf_001.gbw"

        result = fetch_topos_matrices(h5_path, conformer_id="conf_001")
        assert result["conformer_id"] == "conf_001"
        assert result["symbols"] == ["C", "O"]
        assert result["energy_hartree"] == pytest.approx(-113.82910, rel=1e-6)
        assert result["gbw_path"] == "/vol/scratch/conf_001.gbw"
        assert result["provenance"] == "[M]"

    def test_standardize_geometry_dataframe(self) -> None:
        symbols = ["C", "H", "H", "H", "O", "H"]
        coords = np.zeros((6, 3))
        df = standardize_geometry_dataframe(symbols, coords)
        assert len(df) == 6
        assert list(df.columns) == [
            "atom_index",
            "symbol",
            "atomic_number",
            "x",
            "y",
            "z",
            "mass_amu",
            "provenance",
        ]
        assert df["symbol"].iloc[0] == "C"
        assert df["atomic_number"].iloc[0] == 6


# ==============================================================================
# PHASE 2: cochem_torq_topology tests
# ==============================================================================


class TestTorqTopology:
    """Test suite for cochem_torq_topology.py."""

    @pytest.fixture
    def ethanol_coords(self) -> Tuple[List[str], np.ndarray]:
        symbols = ["C", "C", "O", "H", "H", "H", "H", "H", "H"]
        coords = np.array(
            [
                [0.000, 0.000, 0.000],
                [1.500, 0.000, 0.000],
                [2.050, 1.250, 0.000],
                [-0.370, 0.950, 0.370],
                [-0.370, -0.750, 0.650],
                [-0.370, -0.200, -1.020],
                [1.870, -0.550, -0.870],
                [1.870, -0.550, 0.870],
                [2.980, 1.150, 0.000],
            ],
            dtype=np.float64,
        )
        return symbols, coords

    @pytest.fixture
    def toluene_coords(self) -> Tuple[List[str], np.ndarray]:
        symbols = ["C", "C", "C", "C", "C", "C", "C", "H", "H", "H", "H", "H", "H", "H", "H"]
        coords = np.array(
            [
                [0.000, 1.390, 0.000],
                [1.204, 0.695, 0.000],
                [1.204, -0.695, 0.000],
                [0.000, -1.390, 0.000],
                [-1.204, -0.695, 0.000],
                [-1.204, 0.695, 0.000],
                [0.000, 2.890, 0.000],
                [2.140, 1.235, 0.000],
                [2.140, -1.235, 0.000],
                [0.000, -2.470, 0.000],
                [-2.140, -1.235, 0.000],
                [-2.140, 1.235, 0.000],
                [1.020, 3.280, 0.000],
                [-0.510, 3.280, 0.880],
                [-0.510, 3.280, -0.880],
            ],
            dtype=np.float64,
        )
        return symbols, coords

    def test_build_molecular_graph(self, ethanol_coords: Tuple[List[str], np.ndarray]) -> None:
        symbols, coords = ethanol_coords
        g = build_molecular_graph(symbols, coords)
        assert g.number_of_nodes() == 9
        assert g.has_edge(0, 1)
        assert g.has_edge(1, 2)

    def test_detect_5_option_dihedrals(self, ethanol_coords: Tuple[List[str], np.ndarray]) -> None:
        symbols, coords = ethanol_coords
        top_dihedrals = detect_5_option_dihedrals(symbols, coords)
        assert len(top_dihedrals) >= 2

        central_bonds = [d["central_bond"] for d in top_dihedrals]
        assert (0, 1) in central_bonds or (1, 0) in central_bonds
        assert (1, 2) in central_bonds or (2, 1) in central_bonds

        for d in top_dihedrals:
            assert d["is_ring_locked"] is False

    def test_ring_strain_guard(self, toluene_coords: Tuple[List[str], np.ndarray]) -> None:
        symbols, coords = toluene_coords
        g = build_molecular_graph(symbols, coords)

        ring_dihedral = (6, 0, 1, 2)
        assert ring_strain_guard(g, ring_dihedral) is True

        methyl_dihedral = (1, 0, 6, 12)
        assert ring_strain_guard(g, methyl_dihedral) is False

    def test_select_active_torsions_with_fallback(
        self, toluene_coords: Tuple[List[str], np.ndarray]
    ) -> None:
        symbols, coords = toluene_coords
        forbidden_req = [(6, 0, 1, 2)]
        active = select_active_torsions(symbols, coords, requested_dihedrals=forbidden_req)

        assert len(active) >= 1
        assert active[0]["is_ring_locked"] is False


# ==============================================================================
# PHASE 2: cochem_torq_alignment tests
# ==============================================================================


class TestTorqAlignment:
    """Test suite for cochem_torq_alignment.py."""

    @pytest.fixture
    def water_coords(self) -> Tuple[List[str], np.ndarray]:
        symbols = ["O", "H", "H"]
        coords = np.array(
            [
                [0.0000, 0.0000, 0.1173],
                [0.0000, 0.7572, -0.4692],
                [0.0000, -0.7572, -0.4692],
            ],
            dtype=np.float64,
        )
        return symbols, coords

    def test_translate_com_to_origin(self, water_coords: Tuple[List[str], np.ndarray]) -> None:
        symbols, coords = water_coords
        centered, com = translate_com_to_origin(symbols, coords)

        masses = np.array([CIAAW_ISOTOPIC_MASSES[s] for s in symbols])
        new_com = np.sum(centered * masses[:, np.newaxis], axis=0) / np.sum(masses)

        assert np.allclose(new_com, [0.0, 0.0, 0.0], atol=1e-12)

    def test_diagonalize_principal_axes_water(
        self, water_coords: Tuple[List[str], np.ndarray]
    ) -> None:
        symbols, coords = water_coords
        res = diagonalize_principal_axes(symbols, coords)

        I_a, I_b, I_c = res["principal_moments_amu_ang2"]
        assert I_a <= I_b <= I_c
        assert I_a > 0.0

        A, B, C = res["rotational_constants_mhz"]
        assert A >= B >= C
        assert A > 100000.0
        assert B > 50000.0
        assert C > 30000.0

        assert abs(res["inertial_defect_amu_ang2"]) < 1e-4

        rot_mat = res["rotation_matrix"]
        assert np.linalg.det(rot_mat) == pytest.approx(1.0, rel=1e-6)
        assert res["top_type"] == "asymmetric_top"


# ==============================================================================
# PHASE 3: cochem_torq_mace tests
# ==============================================================================


class TestTorqMace:
    """Test suite for cochem_torq_mace.py."""

    def test_rotate_dihedral_angle(self) -> None:
        coords = np.array(
            [
                [-1.5, 1.0, 0.0],
                [-0.5, 0.0, 0.0],
                [0.5, 0.0, 0.0],
                [1.5, 1.0, 0.0],
            ],
            dtype=np.float64,
        )

        rotated_180 = rotate_dihedral_angle(coords, (0, 1, 2, 3), 180.0)
        assert rotated_180[3, 1] == pytest.approx(-1.0, abs=1e-4)

    def test_evaluate_pes_point(self) -> None:
        symbols = ["C", "C", "H", "H", "H", "H", "H", "H"]
        coords = np.array(
            [
                [-0.75, 0.0, 0.0],
                [0.75, 0.0, 0.0],
                [-1.15, 1.0, 0.0],
                [-1.15, -0.5, 0.86],
                [-1.15, -0.5, -0.86],
                [1.15, 1.0, 0.0],
                [1.15, -0.5, 0.86],
                [1.15, -0.5, -0.86],
            ],
            dtype=np.float64,
        )

        energy = evaluate_pes_point(symbols, coords)
        assert isinstance(energy, float)

    def test_generate_adaptive_grid(self) -> None:
        symbols = ["C", "C", "H", "H", "H", "H", "H", "H"]
        coords = np.array(
            [
                [-0.75, 0.0, 0.0],
                [0.75, 0.0, 0.0],
                [-1.15, 1.0, 0.0],
                [-1.15, -0.5, 0.86],
                [-1.15, -0.5, -0.86],
                [1.15, 1.0, 0.0],
                [1.15, -0.5, 0.86],
                [1.15, -0.5, -0.86],
            ],
            dtype=np.float64,
        )

        grid_res = generate_adaptive_grid(
            symbols=symbols,
            coordinates=coords,
            dihedral_indices=(2, 0, 1, 5),
            coarse_points=8,
            gradient_threshold=0.0001,
        )

        assert "angles_deg" in grid_res
        assert "energies_hartree" in grid_res
        assert "gradients_hartree_per_deg" in grid_res
        assert grid_res["adaptive_point_count"] >= grid_res["coarse_point_count"]

    def test_onnx_cpu_fallback(self) -> None:
        cfg = onnx_cpu_fallback(device_preference="cpu")
        assert cfg["provider"] == "CPUExecutionProvider"
        assert cfg["threads"] >= 1
        assert cfg["is_cpu_fallback"] is False

        cfg_fallback = onnx_cpu_fallback(device_preference="cuda")
        assert "provider" in cfg_fallback


# ==============================================================================
# PHASE 3: cochem_torq_quench tests
# ==============================================================================


class TestTorqQuench:
    """Test suite for cochem_torq_quench.py."""

    def test_detect_covalent_clashes_and_soft_quench(self) -> None:
        symbols = ["C", "C", "H", "H"]
        coords = np.array(
            [
                [-0.75, 0.0, 0.0],
                [0.75, 0.0, 0.0],
                [0.00, 0.20, 0.0],
                [0.00, 0.35, 0.0],
            ],
            dtype=np.float64,
        )

        initial_clashes = detect_covalent_clashes(symbols, coords, clash_ratio=0.70)
        assert len(initial_clashes) >= 1

        quench_res = execute_soft_quench(
            symbols=symbols,
            coordinates=coords,
            frozen_dihedrals=[(2, 0, 1, 3)],
            max_steps=50,
            damping=0.2,
        )

        assert quench_res["converged"] is True
        assert quench_res["final_clash_count"] == 0
        relaxed_coords = quench_res["relaxed_coordinates"]
        dist = np.linalg.norm(relaxed_coords[2] - relaxed_coords[3])
        assert dist > 0.40

    def test_execute_jiggle_quench(self) -> None:
        symbols = ["C", "C", "H", "H"]
        coords = np.array(
            [
                [-0.75, 0.0, 0.0],
                [0.75, 0.0, 0.0],
                [0.00, 0.20, 0.0],
                [0.00, 0.35, 0.0],
            ],
            dtype=np.float64,
        )

        jiggle_res = execute_jiggle_quench(
            symbols=symbols,
            coordinates=coords,
            jiggle_amplitude=0.03,
            max_steps=40,
        )
        assert (
            jiggle_res["final_clash_count"] < jiggle_res["initial_clash_count"]
            or jiggle_res["converged"]
        )


# ==============================================================================
# PHASE 4: cochem_torq_slicer tests
# ==============================================================================


class TestTorqSlicer:
    """Test suite for cochem_torq_slicer.py."""

    def test_fit_continuous_splines(self) -> None:
        v0_hartree = 0.005
        angles = np.linspace(0.0, 360.0, 24, endpoint=False)
        energies = [
            0.5 * v0_hartree * (1.0 - math.cos(math.radians(3.0 * a))) - 150.0 for a in angles
        ]

        res = fit_continuous_splines(angles, energies, periodic=True)

        assert "stationary_points" in res
        assert "global_minimum" in res
        assert len(res["minima"]) >= 3
        assert len(res["maxima"]) >= 3

        expected_barrier_kcal = v0_hartree * HARTREE_TO_KCAL_MOL
        assert res["max_barrier_kcal_mol"] == pytest.approx(expected_barrier_kcal, rel=0.05)
        assert res["max_barrier_cm1"] == pytest.approx(v0_hartree * HARTREE_TO_CM1, rel=0.05)

    def test_wkb_tunneling_estimator_ch3(self) -> None:
        res = wkb_tunneling_estimator(
            rotor_type="-CH3",
            barrier_height_cm1=1000.0,
            reduced_moment_inertia_amu_ang2=3.1,
            periodicity=3,
        )
        assert res["is_light_rotor"] is True
        assert res["tunneling_probability"] > 0.0
        assert res["tunneling_splitting_mhz"] >= 0.0
        assert res["quantum_treatment_required"] is True

    def test_wkb_tunneling_estimator_heavy_rotor(self) -> None:
        res = wkb_tunneling_estimator(
            rotor_type="Phenyl",
            barrier_height_cm1=5000.0,
            reduced_moment_inertia_amu_ang2=120.0,
            periodicity=2,
        )
        assert res["is_light_rotor"] is False
        assert res["quantum_treatment_required"] is False


# ==============================================================================
# PHASE 5: cochem_torq_engine tests
# ==============================================================================


class TestTorqEngine:
    """Test suite for cochem_torq_engine.py."""

    def test_validate_method_matrix_grid_violation(self) -> None:
        calc_spec = {
            "method": "B3LYP",
            "grid": "Grid5",
        }
        with pytest.raises(MethodMatrixViolationError) as exc_info:
            validate_method_matrix_compliance(calc_spec)
        assert exc_info.value.error_code == ProvenanceErrorCode.METHOD_MATRIX_VIOLATION_DEFGRID

    def test_validate_method_matrix_weak_complex_dispersion_missing(self) -> None:
        calc_spec = {
            "method": "B3LYP",
            "grid": "defgrid1",
            "is_weak_complex": True,
            "dispersion": "",
            "tol_max_g": 1e-5,
        }
        with pytest.raises(DispersionMissingError) as exc_info:
            validate_method_matrix_compliance(calc_spec)
        assert exc_info.value.error_code == ProvenanceErrorCode.DISPERSION_MISSING

    def test_validate_method_matrix_calc_hess_forbidden(self) -> None:
        calc_spec = {
            "method": "r2SCAN-3c",
            "grid": "defgrid1",
            "calc_hess": True,
        }
        with pytest.raises(InvalidHessianStrategyError) as exc_info:
            validate_method_matrix_compliance(calc_spec)
        assert exc_info.value.error_code == ProvenanceErrorCode.INVALID_HESSIAN_STRATEGY

    def test_validate_method_matrix_spin_contamination_exceeded(self) -> None:
        calc_spec = {
            "method": "UKS-B3LYP",
            "grid": "defgrid1",
            "spin_s2_expected": 0.75,
            "spin_s2_observed": 0.95,
        }
        with pytest.raises(SpinContaminationError) as exc_info:
            validate_method_matrix_compliance(calc_spec)
        assert exc_info.value.error_code == ProvenanceErrorCode.SPIN_CONTAMINATION_EXCEEDED

    def test_route_method_matrix_success(self) -> None:
        calc_spec = {
            "method": "r2SCAN-3c",
            "grid": "defgrid1",
            "hessian_strategy": "InHess XTB2",
            "threads": 4,
            "maxcore_mb": 2048,
            "opt": True,
            "frozen_monomer": True,
            "bsse_counterpoise": True,
            "simulated_energy": -228.19284,
        }
        result = route_method_matrix(calc_spec)
        assert result["status"] == "SUCCESS"
        assert result["provenance"] == "[M]"
        assert "defgrid1" in result["input_deck"]
        assert "Constraints" in result["input_deck"]
        assert "BSSE true" in result["input_deck"]

    def test_opi_persistent_threading(self, tmp_path: Path) -> None:
        scratch = tmp_path / "scratch"
        opi_res = opi_persistent_threading(session_id="test_sess_01", scratch_dir=scratch)
        assert opi_res["status"] == "INITIALIZED"
        assert opi_res["session_scratch_dir"].exists()


# ==============================================================================
# PHASE 5: cochem_torq_watchdog tests
# ==============================================================================


class TestTorqWatchdog:
    """Test suite for cochem_torq_watchdog.py."""

    def test_monitor_stdout_stream_scf_and_oom(self) -> None:
        stream_stdout_lines = [
            "ORCA 6.1.1 executing...",
            "Iter  1: E = -154.000",
            "Iter 50: E = -154.100 (SCF NOT CONVERGED)",
            "Error: OUT OF MEMORY during integral evaluation",
        ]
        res = monitor_stdout_stream(stream_stdout_lines)
        assert res["has_failure"] is True
        assert res["signatures"]["scf_divergence"] is True
        assert res["signatures"]["memory_oom"] is True
        assert len(res["error_lines"]) == 2

    def test_execute_grid_collapse(self) -> None:
        osc_energies = [-100.1, -100.3, -100.05, -100.35, -100.02]
        res = execute_grid_collapse(
            current_grid_level="defgrid3",
            scf_cycles=60,
            energy_history=osc_energies,
        )
        assert res["action"] == "grid_collapse"
        assert res["divergence_detected"] is True
        assert res["previous_grid"] == "defgrid3"
        assert res["new_grid"] == "defgrid2"
        assert res["scf_algorithm"] == "SOSCF"

    def test_dynamic_memory_backoff(self) -> None:
        res = dynamic_memory_backoff(
            requested_maxcore_mb=4096,
            backoff_factor=0.75,
        )
        assert res["action"] == "dynamic_memory_backoff"
        assert res["previous_maxcore_mb"] == 4096
        assert res["new_maxcore_mb"] == 3072
        assert res["ready_for_restart"] is True

        res_floor = dynamic_memory_backoff(
            requested_maxcore_mb=300,
            backoff_factor=0.5,
        )
        assert res_floor["new_maxcore_mb"] == 256


# ==============================================================================
# PROXY RE-EXPORT INTERFACE TESTS (cochem_base)
# ==============================================================================


class TestCochemBaseProxies:
    """Validates that cochem_base re-exports all 11 modules with 100% symbol identity."""

    def test_proxy_imports(self) -> None:
        from cochem_base.cochem_h5_healer import force_release_swmr as proxy_force_release_swmr
        from cochem_base.cochem_torq_alignment import (
            diagonalize_principal_axes as proxy_diagonalize_principal_axes,
        )
        from cochem_base.cochem_torq_engine import route_method_matrix as proxy_route_method_matrix
        from cochem_base.cochem_torq_init import verify_airgap as proxy_verify_airgap
        from cochem_base.cochem_torq_mace import (
            generate_adaptive_grid as proxy_generate_adaptive_grid,
        )
        from cochem_base.cochem_torq_quench import execute_soft_quench as proxy_execute_soft_quench
        from cochem_base.cochem_torq_schema import TorqHardwareSchema as ProxyTorqHardwareSchema
        from cochem_base.cochem_torq_slicer import (
            fit_continuous_splines as proxy_fit_continuous_splines,
        )
        from cochem_base.cochem_torq_topology import (
            detect_5_option_dihedrals as proxy_detect_5_option_dihedrals,
        )
        from cochem_base.cochem_torq_vault import parse_external_xyz as proxy_parse_external_xyz
        from cochem_base.cochem_torq_watchdog import (
            execute_grid_collapse as proxy_execute_grid_collapse,
        )

        assert proxy_verify_airgap is verify_airgap
        assert ProxyTorqHardwareSchema is TorqHardwareSchema
        assert proxy_force_release_swmr is force_release_swmr
        assert proxy_parse_external_xyz is parse_external_xyz
        assert proxy_detect_5_option_dihedrals is detect_5_option_dihedrals
        assert proxy_diagonalize_principal_axes is diagonalize_principal_axes
        assert proxy_generate_adaptive_grid is generate_adaptive_grid
        assert proxy_execute_soft_quench is execute_soft_quench
        assert proxy_fit_continuous_splines is fit_continuous_splines
        assert proxy_route_method_matrix is route_method_matrix
        assert proxy_execute_grid_collapse is execute_grid_collapse
