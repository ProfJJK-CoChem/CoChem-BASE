#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Comprehensive Unit & Integration Test Suite for hetero_config.py.
Mandated by Method Matrix v4/v5 §8A (Concurrency & Scout-and-Anchor Heterogeneous Pipeline).
"""

import json
import math
import os
import tempfile
from pathlib import Path
from typing import List

import numpy as np
import pytest
import scipy.linalg

import hetero_config
from hetero_config import (
    ContentionBudget,
    G7ProvenanceRecord,
    HessianValidationResult,
    IntegrityGuardViolation,
    SetupType,
    SlurmResourceOptions,
    TaskAuthority,
    WorkerModelCache,
    build_hetero_config,
    build_worker_init_scripts,
    calculate_contention_budget,
    compute_kabsch_rmsd,
    compute_molecular_center_of_mass,
    detect_hardware_topology,
    get_atomic_mass_amu,
    get_atomic_masses_for_symbols,
    log_g7_provenance_event,
    main,
    provision_mps_environment,
    read_orca_carthess,
    validate_carthess_eigenvalues,
    verify_g1_authority,
    verify_g2_high_level_hessian,
    verify_g3_basin_identity,
    verify_g4_rank_inversion,
    verify_g5_uncertainty_gate,
    verify_g6_abort_guide,
    write_orca_carthess,
)


# ===========================================================================
# 1. Physical Constants & Unit Conversions
# ===========================================================================
def test_physical_constants_and_factors() -> None:
    """Verify exactness of CODATA physical constants and Hessian conversion factor."""
    assert hetero_config.PLANCK_CONSTANT_J_S == pytest.approx(6.62607015e-34, rel=1e-9)
    assert hetero_config.SPEED_OF_LIGHT_CM_S == pytest.approx(2.99792458e10, rel=1e-9)
    assert hetero_config.SPEED_OF_LIGHT_M_S == pytest.approx(2.99792458e8, rel=1e-9)
    assert hetero_config.ATOMIC_MASS_UNIT_KG == pytest.approx(1.66053906660e-27, rel=1e-9)
    assert hetero_config.BOHR_TO_ANGSTROM == pytest.approx(0.529177210903, rel=1e-9)
    assert hetero_config.HARTREE_TO_EV == pytest.approx(27.211386245988, rel=1e-9)
    assert hetero_config.HARTREE_TO_KCAL_MOL == pytest.approx(627.509474, rel=1e-6)

    # Conversion factor check: ~5140.487 cm^-1
    expected_factor = (
        math.sqrt(hetero_config.HARTREE_TO_JOULE / ((hetero_config.BOHR_TO_METER ** 2) * hetero_config.ATOMIC_MASS_UNIT_KG))
        / (2.0 * math.pi * hetero_config.SPEED_OF_LIGHT_CM_S)
    )
    assert hetero_config.HESSIAN_EIG_TO_CM_INV_FACTOR == pytest.approx(expected_factor, rel=1e-9)


# ===========================================================================
# 2. Dynamic Mendeleev Mass Retrieval & Isotopes
# ===========================================================================
def test_mendeleev_masses_and_isotopes() -> None:
    """Verify dynamic mass retrieval for standard elements and D/T isotopes."""
    mass_h = get_atomic_mass_amu("H")
    mass_c = get_atomic_mass_amu("C")
    mass_o = get_atomic_mass_amu("O")
    mass_d = get_atomic_mass_amu("D")
    mass_t = get_atomic_mass_amu("T")

    assert mass_h == pytest.approx(1.008, rel=1e-2)
    assert mass_c == pytest.approx(12.011, rel=1e-2)
    assert mass_o == pytest.approx(15.999, rel=1e-2)
    assert mass_d == pytest.approx(2.014, rel=1e-2)
    assert mass_t == pytest.approx(3.016, rel=1e-2)

    arr = get_atomic_masses_for_symbols(["C", "H", "O", "D"])
    assert len(arr) == 4
    assert arr.dtype == np.float64
    assert arr[0] == pytest.approx(mass_c)
    assert arr[3] == pytest.approx(mass_d)


# ===========================================================================
# 3. Pydantic Models & Contention Budget
# ===========================================================================
def test_contention_budget_model() -> None:
    """Verify hardware contention budgeting according to Method Matrix §8A.1."""
    budget = calculate_contention_budget(
        total_physical_cores=16,
        total_ram_gb=64.0,
        gpu_scout_workers=3,
        anchor_ranks=7,
    )
    assert budget.total_physical_cores == 16
    assert budget.p_cores_anchor == 7
    assert budget.p_cores_scout_feeder == 1
    assert budget.e_cores_orchestrator == 8
    assert budget.gpu_scout_workers == 3
    assert budget.anchor_mem_per_worker_gb == 28.0
    assert budget.estimated_cpu_slowdown_factor == pytest.approx(1.20)
    assert budget.real_parallelism_efficiency == pytest.approx(0.85)

    # Test small core fallback
    small_budget = calculate_contention_budget(
        total_physical_cores=4,
        total_ram_gb=16.0,
        gpu_scout_workers=1,
    )
    assert small_budget.p_cores_anchor == 3
    assert small_budget.p_cores_scout_feeder == 1
    assert small_budget.e_cores_orchestrator == 0


def test_slurm_resource_options() -> None:
    """Verify Slurm resource options model."""
    opt = SlurmResourceOptions(
        partition="gpu_prod",
        account="chem_project",
        gres_gpu="gpu:1",
        cpus_per_task=8,
    )
    assert opt.partition == "gpu_prod"
    assert opt.cpus_per_task == 8
    assert opt.gres_gpu == "gpu:1"


# ===========================================================================
# 4. NVIDIA MPS Provisioning & Worker Init Scripts
# ===========================================================================
def test_mps_provisioning_and_worker_init() -> None:
    """Verify MPS environment provisioning and worker initialization script generation."""
    with tempfile.TemporaryDirectory() as td:
        env = provision_mps_environment(
            ephemeral_root=td,
            active_thread_pct=33,
            pinned_mem_limit="0=6G",
            gpu_device=0,
            user="testuser",
        )
        assert env["CUDA_VISIBLE_DEVICES"] == "0"
        assert env["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] == "33"
        assert env["CUDA_MPS_PINNED_DEVICE_MEM_LIMIT"] == "0=6G"
        assert Path(env["CUDA_MPS_PIPE_DIRECTORY"]).exists()
        assert Path(env["CUDA_MPS_LOG_DIRECTORY"]).exists()

        cpu_init, gpu_init, orch_init = build_worker_init_scripts(
            mps_pipe_dir=Path(env["CUDA_MPS_PIPE_DIRECTORY"]),
            mps_log_dir=Path(env["CUDA_MPS_LOG_DIRECTORY"]),
            mps_thread_pct=33,
            mps_pinned_mem="0=6G",
            gpu_device_id=0,
        )
        assert "OMP_NUM_THREADS=1" in cpu_init
        assert "KMP_HW_SUBSET=8c:intel_core,1t" in cpu_init
        assert "CUDA_VISIBLE_DEVICES=0" in gpu_init
        assert "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=33" in gpu_init
        assert "CUDA_MPS_PINNED_DEVICE_MEM_LIMIT='0=6G'" in gpu_init
        assert "ulimit -n 16384" in gpu_init
        assert "PYTHONUNBUFFERED=1" in orch_init


# ===========================================================================
# 5. Parsl Heterogeneous Configuration Builder
# ===========================================================================
def test_build_hetero_config_workstation() -> None:
    """Verify build_hetero_config for Setup 2 (Workstation)."""
    with tempfile.TemporaryDirectory() as td:
        cfg = build_hetero_config(
            setup=SetupType.WORKSTATION,
            cpu_workers=1,
            cpu_cores_per_worker=7,
            gpu_workers=3,
            ephemeral_dir=td,
        )
        if hasattr(cfg, "executors"):
            labels = [e.label for e in cfg.executors]
            assert "cpu" in labels
            assert "gpu" in labels
            assert cfg.retries == 2
        else:
            assert cfg["setup"] == "workstation"
            assert "cpu" in cfg["executors"]
            assert "gpu" in cfg["executors"]


def test_build_hetero_config_teaching() -> None:
    """Verify build_hetero_config degrades to CPU-only for Setup 1 (Teaching)."""
    with tempfile.TemporaryDirectory() as td:
        cfg = build_hetero_config(
            setup=SetupType.TEACHING,
            cpu_workers=1,
            cpu_cores_per_worker=4,
            ephemeral_dir=td,
        )
        if hasattr(cfg, "executors"):
            labels = [e.label for e in cfg.executors]
            assert "cpu" in labels
            assert "gpu" not in labels
        else:
            assert cfg["setup"] == "teaching"


def test_build_hetero_config_slurm() -> None:
    """Verify build_hetero_config for Setup 3 (Slurm/HPC)."""
    with tempfile.TemporaryDirectory() as td:
        slurm_opts = SlurmResourceOptions(
            partition="gpu_queue",
            gres_gpu="gpu:1",
            cpus_per_task=8,
        )
        cfg = build_hetero_config(
            setup=SetupType.SLURM,
            cpu_workers=1,
            cpu_cores_per_worker=7,
            gpu_workers=3,
            slurm_options=slurm_opts,
            ephemeral_dir=td,
        )
        if hasattr(cfg, "executors"):
            labels = [e.label for e in cfg.executors]
            assert "cpu" in labels
            assert "gpu" in labels


# ===========================================================================
# 6. ORCA Cartesian Hessian Writer, Reader & Eigenvalue Validation
# ===========================================================================
def test_orca_carthess_roundtrip() -> None:
    """Verify exact roundtrip I/O for ORCA .carthess format with multi-block columns."""
    dim = 27  # 9 atoms (exceeds 5-column block limit)
    np.random.seed(42)
    raw_h = np.random.randn(dim, dim)
    h_sym = 0.5 * (raw_h + raw_h.T)

    with tempfile.TemporaryDirectory() as td:
        carthess_file = Path(td) / "test_9atom.carthess"
        written_path = write_orca_carthess(h_sym, carthess_file)
        assert written_path.exists()

        read_h = read_orca_carthess(written_path)
        assert read_h.shape == (dim, dim)
        assert np.allclose(h_sym, read_h, atol=1e-7)


def test_validate_carthess_eigenvalues() -> None:
    """Verify Cartesian Hessian eigenvalue invariance assertion (Method Matrix §8A.3)."""
    dim = 18  # 6 atoms
    np.random.seed(123)
    # Construct a synthetic Hessian with exactly 6 zero eigenvalues
    diag_eigs = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0] + [float(i + 1) * 0.05 for i in range(dim - 6)])
    # Orthogonal transformation
    q, _ = scipy.linalg.qr(np.random.randn(dim, dim))
    h_matrix = q @ np.diag(diag_eigs) @ q.T

    res = validate_carthess_eigenvalues(h_matrix, tolerance=1e-4, is_linear=False)
    assert res.is_valid is True
    assert res.zero_eigenvalue_count == 6
    assert len(res.lowest_eigenvalues_eh_bohr2) == 6
    assert res.lowest_eigenvalues_eh_bohr2[0] < 1e-4
    assert res.softest_force_constant > 0.0

    # With atomic symbols
    symbols = ["C", "C", "H", "H", "H", "H"]
    res_mw = validate_carthess_eigenvalues(h_matrix, tolerance=1e-4, is_linear=False, atomic_symbols=symbols)
    assert res_mw.is_valid is True
    assert len(res_mw.harmonic_frequencies_cm_inv) > 0


# ===========================================================================
# 7. Kabsch RMSD & Molecular Center of Mass with 3D Rotation
# ===========================================================================
def test_compute_kabsch_rmsd_invariance() -> None:
    """Verify Kabsch RMSD is exactly zero under arbitrary 3D rotation and translation."""
    np.random.seed(999)
    coords_ref = np.random.randn(8, 3) * 3.0

    # Euler rotation matrix (yaw, pitch, roll)
    alpha, beta, gamma = 0.8, -0.5, 1.2
    rz = np.array([[np.cos(alpha), -np.sin(alpha), 0], [np.sin(alpha), np.cos(alpha), 0], [0, 0, 1]])
    ry = np.array([[np.cos(beta), 0, np.sin(beta)], [0, 1, 0], [-np.sin(beta), 0, np.cos(beta)]])
    rx = np.array([[1, 0, 0], [0, np.cos(gamma), -np.sin(gamma)], [0, np.sin(gamma), np.cos(gamma)]])
    rot = rz @ ry @ rx

    translation = np.array([12.5, -45.2, 8.8])
    coords_transformed = coords_ref @ rot.T + translation

    rmsd = compute_kabsch_rmsd(coords_transformed, coords_ref)
    assert rmsd == pytest.approx(0.0, abs=1e-12)


def test_molecular_center_of_mass() -> None:
    """Verify COM calculation using dynamic Mendeleev masses."""
    coords = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.128]], dtype=np.float64)
    symbols = ["C", "O"]
    com = compute_molecular_center_of_mass(coords, symbols)

    m_c = get_atomic_mass_amu("C")
    m_o = get_atomic_mass_amu("O")
    expected_z = (m_o * 1.128) / (m_c + m_o)
    assert com[0] == pytest.approx(0.0)
    assert com[1] == pytest.approx(0.0)
    assert com[2] == pytest.approx(expected_z, rel=1e-6)


# ===========================================================================
# 8. Integrity Guards (G1–G7) Engine Verification
# ===========================================================================
def test_g1_authority_guard() -> None:
    """G1: Advisory guide streams cannot assert authoritative status."""
    assert verify_g1_authority({"authority": "advisory_only"}) is True
    assert verify_g1_authority({"authority": "scout"}) is True

    with pytest.raises(IntegrityGuardViolation, match="G1 Integrity Violation"):
        verify_g1_authority({"authority": "authoritative"})

    with pytest.raises(IntegrityGuardViolation, match="G1 Integrity Violation"):
        verify_g1_authority({"authority": "authoritative_final"})


def test_g2_high_level_hessian_guard() -> None:
    """G2: Assert presence and non-saddle character of final high-level Hessian."""
    assert verify_g2_high_level_hessian({"imaginary_frequencies_count": 0}) is True
    assert verify_g2_high_level_hessian({"imag_freq_count": 0}) is True

    # Transition state check (max_imaginary_frequencies=1)
    assert verify_g2_high_level_hessian({"imaginary_frequencies_count": 1}, max_imaginary_frequencies=1) is True

    with pytest.raises(IntegrityGuardViolation, match="lacks high-level Hessian"):
        verify_g2_high_level_hessian({})

    with pytest.raises(IntegrityGuardViolation, match="Possible saddle point"):
        verify_g2_high_level_hessian({"imaginary_frequencies_count": 2}, max_imaginary_frequencies=0)


def test_g3_basin_identity_guard() -> None:
    """G3: Heavy-atom RMSD <= 0.25 A and Delta R <= 0.20 A."""
    c1 = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.128]])
    c2 = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.135]])
    symbols = ["C", "O"]

    same_b, rmsd, dr, msg = verify_g3_basin_identity(c1, c2, symbols, max_rmsd=0.25, max_dr=0.20)
    assert same_b is True
    assert rmsd < 0.25
    assert "SAME BASIN" in msg

    # Exceeding threshold
    c3 = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.800]])
    same_b2, rmsd2, dr2, msg2 = verify_g3_basin_identity(c1, c3, symbols, max_rmsd=0.25, max_dr=0.20)
    assert same_b2 is False
    assert "BASIN CHANGE DETECTED" in msg2

    # Monomer-specific Delta R
    # Dimer of CO: monomer A is [0, 1], monomer B is [2, 3]
    c_dimer_scout = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.13], [0.0, 0.0, 4.0], [0.0, 0.0, 5.13]])
    c_dimer_anchor = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.13], [0.0, 0.0, 4.1], [0.0, 0.0, 5.23]])
    symbols_dimer = ["C", "O", "C", "O"]
    same_dimer, rmsd_dim, dr_dim, msg_dim = verify_g3_basin_identity(
        c_dimer_scout,
        c_dimer_anchor,
        symbols_dimer,
        monomer_a_indices=[0, 1],
        monomer_b_indices=[2, 3],
    )
    assert same_dimer is True
    assert dr_dim == pytest.approx(0.1, abs=1e-3)


def test_g4_rank_inversion_guard() -> None:
    """G4: Spearman rho >= 0.90 required to cull."""
    scout_e = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    anchor_e = [1.05, 2.10, 2.95, 4.05, 5.12, 5.95, 7.08]

    passes, rho, msg = verify_g4_rank_inversion(scout_e, anchor_e, rho_threshold=0.90)
    assert passes is True
    assert rho >= 0.90
    assert "CULLING PERMITTED" in msg

    # Rank inversion
    anchor_inverted = [7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
    passes_inv, rho_inv, msg_inv = verify_g4_rank_inversion(scout_e, anchor_inverted, rho_threshold=0.90)
    assert passes_inv is False
    assert rho_inv < 0.0
    assert "CULLING PROHIBITED" in msg_inv

    # Small sample (< 3)
    passes_small, _, msg_small = verify_g4_rank_inversion([1.0, 2.0], [1.1, 2.1])
    assert passes_small is False
    assert "Sample too small" in msg_small


def test_g5_and_g6_guards() -> None:
    """G5: Uncertainty gate & G6: Abort guide threshold."""
    assert verify_g5_uncertainty_gate(4.5, threshold_sigma_mev=10.0) is True
    assert verify_g5_uncertainty_gate(12.5, threshold_sigma_mev=10.0) is False

    assert verify_g6_abort_guide(2, max_failures=5) is True
    assert verify_g6_abort_guide(5, max_failures=5) is False
    assert verify_g6_abort_guide(6, max_failures=5) is False


def test_g7_provenance_logging_and_validation() -> None:
    """G7: Cryptographic audit logging to provenance.jsonl and Pydantic validation."""
    with tempfile.TemporaryDirectory() as td:
        record = G7ProvenanceRecord(
            stage="mlff_preopt",
            decision="seed_dft_optimisation",
            guide={"code": "mace-torch", "model_key": "MACE-OFF24-medium"},
            input={"structure_id": "iso_001"},
            output={"E_guide_eV": -1200.5, "fmax_eV_A": 0.015},
            gates={"G4_spearman_rho": 0.95},
            consumer={"anchor_job": "iso_001_opt.inp"},
            authority=TaskAuthority.ADVISORY_ONLY,
        )
        log_file = log_g7_provenance_event(record, log_dir=td, filename="test_provenance.jsonl")
        assert log_file.exists()

        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["stage"] == "mlff_preopt"
        assert entry["authority"] == "advisory_only"

        # Model validation: reject authoritative authority for guide stage
        with pytest.raises(Exception):
            G7ProvenanceRecord(
                stage="mlff_preopt",
                decision="seed_dft_optimisation",
                authority=TaskAuthority.AUTHORITATIVE,
            )


# ===========================================================================
# 9. CLI Execution Verification
# ===========================================================================
def test_cli_execution() -> None:
    """Verify hetero_config CLI commands."""
    assert main(["--dump-config", "--setup", "workstation"]) == 0
    assert main(["--run-guards-test"]) == 0
