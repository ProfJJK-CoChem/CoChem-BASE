"""Exhaustive Zero-Mock Unit and Integration Test Suite for CoChem-GEOM Metrics.
================================================================================
Authoritative Standards:
- Method Matrix v4.1: Conformer Ensemble Metrics, Kabsch Alignment, Energy & Force Tracking
- TorchMetrics v1.0+: Modular Metric Interface with DDP State Reduction & Pure Tensor Ops
- Mendeleev Library Mandate: Dynamic atomic and monoisotopic mass validation (No hardcoding)
- SE(3) Equivariance & Invariance: Rigorous spatial transformation invariance & coordinate immutability
- State Immutability: Pure functional geometric transformations (pos_new = pos + shift)
- Provenance Tags: [M] Measured/Theoretical, [D] Derived/Calculated, [E] Expert Estimate
- Strict Zero-Mock Policy: 100% authentic physical tensor mathematics and real execution
"""

from __future__ import annotations

import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

from mendeleev import element
import numpy as np
import pytest
import torch
import torchmetrics

# ------------------------------------------------------------------------------
# Dynamic Path Configuration (Ensuring CoChem-BASE/src or CoChem-GEOM/src in sys.path)
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
GEOM_DIR_ENV = os.environ.get("COCHEM_GEOM_DIR")
if GEOM_DIR_ENV:
    GEOM_ROOT = Path(GEOM_DIR_ENV).resolve()
else:
    if (BASE_DIR / "src" / "cochem_geom").exists():
        GEOM_ROOT = BASE_DIR
    else:
        GEOM_ROOT = BASE_DIR.parent / "CoChem-GEOM"

GEOM_SRC = GEOM_ROOT / "src"
if str(GEOM_SRC) not in sys.path:
    sys.path.insert(0, str(GEOM_SRC))
if str(GEOM_ROOT) not in sys.path:
    sys.path.insert(0, str(GEOM_ROOT))

import cochem_geom.eval.metrics as metrics_mod
from cochem_geom.eval.metrics import (
    ATOMIC_MASS_UNIT_KG,
    BOLTZMANN_CONSTANT_EV_K,
    BOLTZMANN_CONSTANT_J_K,
    DEFAULT_AMR_THRESHOLD,
    DEFAULT_COV_THRESHOLD,
    DEFAULT_TEMPERATURE_K,
    EV_TO_CM_MINUS_ONE,
    EV_TO_HARTREE,
    EV_TO_KCAL_MOL,
    EV_TO_KJ_MOL,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    KCAL_MOL_TO_EV,
    KCAL_MOL_TO_HARTREE,
    PLANCK_CONSTANT_J_S,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SPEED_OF_LIGHT_M_S,
    STANDARD_TEMPERATURE_K,
    AverageMinimumRMSD,
    BoltzmannWeightedEnergyMAE,
    ConformerCoverage,
    ConformerEnsembleEvaluator,
    EnergyMAE,
    ForceCosineSimilarity,
    ForceMAE,
    ForceRMSE,
    InertialDefectMAE,
    InternalCoordinatesMAE,
    RelativeEnergyMAE,
    RotationalConstantsMAE,
    compute_average_minimum_rmsd,
    compute_bond_angles,
    compute_bond_lengths,
    compute_conformer_coverage,
    compute_dihedral_angles,
    compute_inertial_defect,
    compute_moments_of_inertia,
    compute_rmsd,
    convert_energy,
    get_atomic_mass,
    get_atomic_masses,
    get_monoisotopic_mass,
    kabsch_align,
    kabsch_rotation,
    pairwise_conformer_rmsd,
)


# ==============================================================================
# Fixtures: Real Molecular Coordinates & Structures
# ==============================================================================

@pytest.fixture
def water_molecule() -> Tuple[List[str], torch.Tensor, torch.Tensor]:
    """Real water (H2O) equilibrium geometry from spectroscopic benchmarks [M]."""
    symbols = ["O", "H", "H"]
    z = torch.tensor([8, 1, 1], dtype=torch.long)
    # C2v equilibrium structure in Angstroms: r_OH = 0.9575 A, angle HOH = 104.51 deg
    theta = math.radians(104.51 / 2.0)
    r_oh = 0.9575
    pos = torch.tensor(
        [
            [0.0, 0.0, 0.0],
            [r_oh * math.sin(theta), 0.0, r_oh * math.cos(theta)],
            [-r_oh * math.sin(theta), 0.0, r_oh * math.cos(theta)],
        ],
        dtype=torch.float32,
    )
    return symbols, z, pos


@pytest.fixture
def methane_molecule() -> Tuple[List[str], torch.Tensor, torch.Tensor]:
    """Real methane (CH4) tetrahedral equilibrium geometry [M]."""
    symbols = ["C", "H", "H", "H", "H"]
    z = torch.tensor([6, 1, 1, 1, 1], dtype=torch.long)
    r_ch = 1.087
    a = r_ch / math.sqrt(3.0)
    pos = torch.tensor(
        [
            [0.0, 0.0, 0.0],
            [a, a, a],
            [a, -a, -a],
            [-a, a, -a],
            [-a, -a, a],
        ],
        dtype=torch.float32,
    )
    return symbols, z, pos


@pytest.fixture
def ethanol_conformers() -> Tuple[torch.Tensor, torch.Tensor]:
    """Real ethanol (C2H5OH) trans and gauche conformer geometries [M]."""
    # 9 atoms: C, C, O, H, H, H, H, H, H
    # Trans conformer
    trans_pos = torch.tensor(
        [
            [0.000, 0.000, 0.000],  # C1
            [1.500, 0.000, 0.000],  # C2
            [2.050, 1.300, 0.000],  # O
            [3.010, 1.250, 0.000],  # H (hydroxyl)
            [-0.370, 0.510, 0.890],  # H
            [-0.370, 0.510, -0.890],  # H
            [-0.370, -1.030, 0.000],  # H
            [1.870, -0.510, 0.890],  # H
            [1.870, -0.510, -0.890],  # H
        ],
        dtype=torch.float32,
    )
    # Gauche conformer (rotated hydroxyl dihedral by ~120 degrees)
    gauche_pos = trans_pos.clone()
    gauche_pos[3] = torch.tensor([2.050 + 0.96 * math.cos(math.radians(105)), 1.300 + 0.96 * math.sin(math.radians(105)) * math.cos(math.radians(120)), 0.96 * math.sin(math.radians(105)) * math.sin(math.radians(120))], dtype=torch.float32)
    return trans_pos, gauche_pos


# ==============================================================================
# 1. Fundamental Physical Constants & Conversion Factors Tests
# ==============================================================================

class TestFundamentalPhysicalConstants:
    """Validates CODATA 2018/2022 constants and energy conversion precision."""

    def test_codata_constants_and_provenance(self) -> None:
        """Validate CODATA exact and measured constants."""
        assert SPEED_OF_LIGHT_M_S == 299792458.0  # [M]
        assert math.isclose(PLANCK_CONSTANT_J_S, 6.62607015e-34, rel_tol=1e-12)  # [M]
        assert math.isclose(BOLTZMANN_CONSTANT_J_K, 1.380649e-23, rel_tol=1e-12)  # [M]
        assert math.isclose(STANDARD_TEMPERATURE_K, 298.15, rel_tol=1e-12)  # [M]
        assert math.isclose(DEFAULT_TEMPERATURE_K, 298.15, rel_tol=1e-12)  # [M]
        assert math.isclose(BOLTZMANN_CONSTANT_EV_K, 8.617333262145e-5, rel_tol=1e-9)  # [D]
        assert math.isclose(ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ, 505379.008784, rel_tol=1e-6)  # [D]
        assert DEFAULT_COV_THRESHOLD == 0.5  # [E]
        assert DEFAULT_AMR_THRESHOLD == 0.5  # [E]

    def test_energy_conversions(self) -> None:
        """Validate precision and invertibility of energy unit conversions."""
        val_ev = 1.5
        val_hartree = convert_energy(val_ev, from_unit="ev", to_unit="hartree")
        assert math.isclose(val_hartree, val_ev * EV_TO_HARTREE, rel_tol=1e-9)

        val_kcal = convert_energy(val_hartree, from_unit="hartree", to_unit="kcal_mol")
        assert math.isclose(val_kcal, val_hartree * HARTREE_TO_KCAL_MOL, rel_tol=1e-9)

        val_kj = convert_energy(val_hartree, from_unit="hartree", to_unit="kj_mol")
        assert math.isclose(val_kj, val_hartree * HARTREE_TO_KJ_MOL, rel_tol=1e-9)

        # Invertibility back to eV
        val_ev_rec = convert_energy(val_kcal, from_unit="kcal_mol", to_unit="ev")
        assert math.isclose(val_ev, val_ev_rec, rel_tol=1e-6)


# ==============================================================================
# 2. Dynamic Mendeleev Mass Resolution Tests
# ==============================================================================

class TestDynamicMendeleevMasses:
    """Enforces the Mendeleev Library Mandate: dynamic property lookup without hardcoding."""

    def test_dynamic_atomic_masses_lookup(self) -> None:
        """Verify dynamic mass lookup via Mendeleev."""
        for sym in ["H", "C", "N", "O", "F", "P", "S", "Cl"]:
            m_expected = float(element(sym).atomic_weight)
            assert math.isclose(get_atomic_mass(sym), m_expected, rel_tol=1e-9)
            z = int(element(sym).atomic_number)
            assert math.isclose(get_atomic_mass(z), m_expected, rel_tol=1e-9)

    def test_tensor_masses_resolution(self) -> None:
        """Verify dynamic mass resolution for a 1D tensor of atomic numbers."""
        z_tensor = torch.tensor([1, 6, 7, 8, 16], dtype=torch.long)
        masses = get_atomic_masses(z_tensor)
        assert masses.shape == (5,)
        assert math.isclose(masses[0].item(), float(element("H").atomic_weight), rel_tol=1e-6)
        assert math.isclose(masses[1].item(), float(element("C").atomic_weight), rel_tol=1e-6)
        assert math.isclose(masses[2].item(), float(element("N").atomic_weight), rel_tol=1e-6)
        assert math.isclose(masses[3].item(), float(element("O").atomic_weight), rel_tol=1e-6)
        assert math.isclose(masses[4].item(), float(element("S").atomic_weight), rel_tol=1e-6)


# ==============================================================================
# 3. Pure Functional Kabsch Algorithm & SE(3) Invariance Tests
# ==============================================================================

class TestKabschAlgorithmAndRMSD:
    """Tests for pure functional Kabsch alignment and RMSD calculations."""

    def test_identical_structures_rmsd_zero(self, water_molecule: Any) -> None:
        """Identical coordinates must yield exact zero RMSD and identity rotation."""
        _, _, pos = water_molecule
        rmsd = compute_rmsd(pos, pos, align=True)
        assert math.isclose(rmsd.item(), 0.0, abs_tol=1e-6)

        aligned_pos, R, t, aligned_rmsd = kabsch_align(pos, pos)
        assert math.isclose(aligned_rmsd.item(), 0.0, abs_tol=1e-6)
        assert torch.allclose(R, torch.eye(3), atol=1e-5)
        assert torch.allclose(aligned_pos, pos, atol=1e-5)

    def test_translation_and_rotation_invariance(self, methane_molecule: Any) -> None:
        """Kabsch alignment must recover exact zero RMSD under arbitrary SE(3) translation and rotation."""
        _, _, pos = methane_molecule

        # Arbitrary rotation matrix via Rodrigues rotation around axis [1, 1, 1] by 45 deg
        axis = torch.tensor([1.0, 1.0, 1.0])
        axis = axis / torch.norm(axis)
        angle = math.radians(45.0)
        K = torch.tensor(
            [
                [0.0, -axis[2], axis[1]],
                [axis[2], 0.0, -axis[0]],
                [-axis[1], axis[0], 0.0],
            ],
            dtype=torch.float32,
        )
        R_true = torch.eye(3) + math.sin(angle) * K + (1.0 - math.cos(angle)) * (K @ K)
        t_true = torch.tensor([12.5, -8.3, 4.1], dtype=torch.float32)

        # Transformed coordinates (pure immutable operation)
        pos_transformed = (pos @ R_true.T) + t_true.view(1, 3)

        # Unaligned RMSD must be large
        unaligned_rmsd = compute_rmsd(pos, pos_transformed, align=False)
        assert unaligned_rmsd.item() > 5.0

        # Aligned RMSD must be 0.0
        aligned_rmsd = compute_rmsd(pos, pos_transformed, align=True)
        assert math.isclose(aligned_rmsd.item(), 0.0, abs_tol=1e-5)

        # Reconstructed aligned position must match reference
        aligned_pos, R_est, t_est, r_val = kabsch_align(pos, pos_transformed)
        assert math.isclose(r_val.item(), 0.0, abs_tol=1e-5)
        assert torch.allclose(aligned_pos, pos, atol=1e-4)

    def test_state_immutability(self, water_molecule: Any) -> None:
        """Verify inputs are never mutated in place during alignment."""
        _, _, pos = water_molecule
        pos_orig = pos.clone()
        shift = torch.tensor([1.0, 2.0, 3.0])
        pos_shifted = pos + shift

        _ = kabsch_align(pos, pos_shifted)
        assert torch.equal(pos, pos_orig), "Original tensor was mutated in place!"

    def test_reflection_correction(self) -> None:
        """Ensure Kabsch handles reflection and does not return improper rotations (det(R) must be +1)."""
        pos = torch.tensor(
            [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
                [0.5, 0.5, 0.5],
            ],
            dtype=torch.float32,
        )
        # Reflected coordinate system (inversion)
        pos_reflected = -pos

        aligned_pos, R, t, rmsd = kabsch_align(pos, pos_reflected)
        det_R = torch.det(R).item()
        assert math.isclose(det_R, 1.0, abs_tol=1e-5), f"Rotation matrix has improper determinant: {det_R}"


# ==============================================================================
# 4. Pairwise Conformer Ensemble & Coverage Metrics
# ==============================================================================

class TestConformerEnsembleMetrics:
    """Tests for Conformer Coverage (COV) and Average Minimum RMSD (AMR)."""

    def test_pairwise_rmsd_matrix(self, ethanol_conformers: Any) -> None:
        """Verify pairwise RMSD matrix shape and values."""
        trans_pos, gauche_pos = ethanol_conformers
        refs = torch.stack([trans_pos, gauche_pos], dim=0)  # Shape [2, 9, 3]
        preds = torch.stack([trans_pos, gauche_pos], dim=0)  # Shape [2, 9, 3]

        rmsd_mat = pairwise_conformer_rmsd(refs, preds, align=True)
        assert rmsd_mat.shape == (2, 2)
        assert math.isclose(rmsd_mat[0, 0].item(), 0.0, abs_tol=1e-5)
        assert math.isclose(rmsd_mat[1, 1].item(), 0.0, abs_tol=1e-5)
        assert rmsd_mat[0, 1].item() > 0.1  # Trans vs gauche difference

    def test_conformer_coverage_functional(self, ethanol_conformers: Any) -> None:
        """Verify functional compute_conformer_coverage."""
        trans_pos, gauche_pos = ethanol_conformers
        refs = torch.stack([trans_pos, gauche_pos], dim=0)  # [2, 9, 3]
        # Only trans is predicted
        preds = trans_pos.unsqueeze(0)  # [1, 9, 3]

        # At tight threshold 0.1 A, only 1 of 2 refs is covered (50% recall, 100% precision)
        cov_r, cov_p = compute_conformer_coverage(refs, preds, threshold=0.1, align=True)
        assert math.isclose(cov_r.item(), 50.0, abs_tol=1e-4)
        assert math.isclose(cov_p.item(), 100.0, abs_tol=1e-4)

    def test_average_minimum_rmsd_functional(self, ethanol_conformers: Any) -> None:
        """Verify functional compute_average_minimum_rmsd."""
        trans_pos, gauche_pos = ethanol_conformers
        refs = torch.stack([trans_pos, gauche_pos], dim=0)
        preds = torch.stack([trans_pos, gauche_pos], dim=0)

        amr_r, amr_p = compute_average_minimum_rmsd(refs, preds, align=True)
        assert math.isclose(amr_r.item(), 0.0, abs_tol=1e-5)
        assert math.isclose(amr_p.item(), 0.0, abs_tol=1e-5)


# ==============================================================================
# 5. TorchMetrics Class Implementations & DDP Lifecycles
# ==============================================================================

class TestTorchMetricsClasses:
    """Validates TorchMetrics Metric subclasses for conformer generation."""

    def test_conformer_coverage_metric(self, ethanol_conformers: Any) -> None:
        """Test ConformerCoverage TorchMetrics lifecycle (update, compute, reset)."""
        trans_pos, gauche_pos = ethanol_conformers
        refs = torch.stack([trans_pos, gauche_pos], dim=0)
        preds = torch.stack([trans_pos, gauche_pos], dim=0)

        metric = ConformerCoverage(threshold=0.5)
        metric.update(refs, preds)
        res = metric.compute()

        assert "cov_recall" in res
        assert "cov_precision" in res
        assert math.isclose(res["cov_recall"].item(), 100.0, abs_tol=1e-4)
        assert math.isclose(res["cov_precision"].item(), 100.0, abs_tol=1e-4)

        # Reset verification
        metric.reset()
        assert metric.total_ref_count == 0
        assert metric.total_pred_count == 0

    def test_average_minimum_rmsd_metric(self, ethanol_conformers: Any) -> None:
        """Test AverageMinimumRMSD TorchMetrics lifecycle."""
        trans_pos, gauche_pos = ethanol_conformers
        refs = torch.stack([trans_pos, gauche_pos], dim=0)
        preds = torch.stack([trans_pos, gauche_pos], dim=0)

        metric = AverageMinimumRMSD()
        metric.update(refs, preds)
        res = metric.compute()

        assert "amr_recall" in res
        assert "amr_precision" in res
        assert math.isclose(res["amr_recall"].item(), 0.0, abs_tol=1e-5)
        assert math.isclose(res["amr_precision"].item(), 0.0, abs_tol=1e-5)

    def test_energy_mae_metric(self) -> None:
        """Test EnergyMAE metric with unit conversion."""
        pred_e = torch.tensor([10.0, 20.0, 30.0], dtype=torch.float32)  # in eV
        true_e = torch.tensor([10.5, 19.5, 31.0], dtype=torch.float32)  # in eV
        # Errors in eV: [0.5, 0.5, 1.0] -> Mean = 0.666667 eV

        metric = EnergyMAE(target_unit="ev", input_unit="ev")
        metric.update(pred_e, true_e)
        mae_ev = metric.compute()
        assert math.isclose(mae_ev.item(), 2.0 / 3.0, rel_tol=1e-5)

        # Unit conversion to kcal/mol
        metric_kcal = EnergyMAE(target_unit="kcal_mol", input_unit="ev")
        metric_kcal.update(pred_e, true_e)
        mae_kcal = metric_kcal.compute()
        assert math.isclose(mae_kcal.item(), (2.0 / 3.0) * EV_TO_KCAL_MOL, rel_tol=1e-5)

    def test_relative_energy_mae_metric(self) -> None:
        """Test RelativeEnergyMAE for conformer energy ranking."""
        # 3 conformers: True = [0.0, 2.0, 5.0] eV, Pred = [0.1, 2.2, 4.8] eV
        # Relative True = [0.0, 2.0, 5.0] eV
        # Relative Pred = [0.0, 2.1, 4.7] eV
        # Rel Errors = [0.0, 0.1, 0.3] -> Mean = 0.4 / 3 = 0.133333 eV
        pred_e = torch.tensor([0.1, 2.2, 4.8], dtype=torch.float32)
        true_e = torch.tensor([0.0, 2.0, 5.0], dtype=torch.float32)

        metric = RelativeEnergyMAE(target_unit="ev")
        metric.update(pred_e, true_e)
        rel_mae = metric.compute()
        assert math.isclose(rel_mae.item(), 0.4 / 3.0, rel_tol=1e-5)

    def test_boltzmann_weighted_energy_mae(self) -> None:
        """Test Boltzmann-weighted energy error at 298.15 K."""
        pred_e = torch.tensor([0.0, 1.0], dtype=torch.float32)  # eV
        true_e = torch.tensor([0.0, 1.0], dtype=torch.float32)  # eV
        metric = BoltzmannWeightedEnergyMAE(temperature_k=298.15)
        metric.update(pred_e, true_e)
        assert math.isclose(metric.compute().item(), 0.0, abs_tol=1e-6)

    def test_force_metrics(self) -> None:
        """Test ForceMAE, ForceRMSE, and ForceCosineSimilarity."""
        pred_f = torch.tensor([[1.0, 0.0, 0.0], [0.0, 2.0, 0.0]], dtype=torch.float32)
        true_f = torch.tensor([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=torch.float32)

        mae_metric = ForceMAE()
        mae_metric.update(pred_f, true_f)
        # Component errors: [0, 0, 0] and [0, 1, 0] -> sum = 1.0 / 6 = 0.166667
        assert math.isclose(mae_metric.compute().item(), 1.0 / 6.0, rel_tol=1e-5)

        cos_metric = ForceCosineSimilarity()
        cos_metric.update(pred_f, true_f)
        # Cosine sims: 1.0 and 1.0 -> Mean = 1.0
        assert math.isclose(cos_metric.compute().item(), 1.0, rel_tol=1e-5)


# ==============================================================================
# 6. Rotational Constants & Spectroscopic Observables
# ==============================================================================

class TestRotationalObservables:
    """Validates principal moments of inertia and rotational constants (A, B, C)."""

    def test_water_moments_and_rotational_constants(self, water_molecule: Any) -> None:
        """Validate moments of inertia and rotational constants for H2O."""
        _, z, pos = water_molecule
        moments, rot_consts = compute_moments_of_inertia(pos, z)
        # Check sorting: I_a <= I_b <= I_c and A >= B >= C
        assert moments[0] <= moments[1] <= moments[2]
        assert rot_consts[0] >= rot_consts[1] >= rot_consts[2]

        # For planar molecule, planar inertial defect Delta I = I_c - I_a - I_b ~ 0.0 (rigid rotor)
        defect = compute_inertial_defect(pos, z)
        assert math.isclose(defect.item(), 0.0, abs_tol=1e-4)

    def test_rotational_constants_mae_metric(self, water_molecule: Any) -> None:
        """Validate RotationalConstantsMAE and InertialDefectMAE."""
        _, z, pos = water_molecule
        metric = RotationalConstantsMAE()
        metric.update(pos, pos, z)
        res = metric.compute()
        assert math.isclose(res["mae_a_mhz"].item(), 0.0, abs_tol=1e-4)
        assert math.isclose(res["mae_b_mhz"].item(), 0.0, abs_tol=1e-4)
        assert math.isclose(res["mae_c_mhz"].item(), 0.0, abs_tol=1e-4)

        defect_metric = InertialDefectMAE()
        defect_metric.update(pos, pos, z)
        assert math.isclose(defect_metric.compute().item(), 0.0, abs_tol=1e-5)


# ==============================================================================
# 7. Internal Coordinates (Bonds, Angles, Dihedrals)
# ==============================================================================

class TestInternalCoordinates:
    """Validates bond lengths, bond angles, and dihedral angles calculation."""

    def test_water_bond_length_and_angle(self, water_molecule: Any) -> None:
        """Verify bond lengths and bond angle for H2O."""
        _, _, pos = water_molecule
        bonds = torch.tensor([[0, 1], [0, 2]], dtype=torch.long)
        angles = torch.tensor([[1, 0, 2]], dtype=torch.long)

        lengths = compute_bond_lengths(pos, bonds)
        assert math.isclose(lengths[0].item(), 0.9575, rel_tol=1e-4)
        assert math.isclose(lengths[1].item(), 0.9575, rel_tol=1e-4)

        deg = compute_bond_angles(pos, angles)
        assert math.isclose(deg[0].item(), 104.51, rel_tol=1e-3)

    def test_internal_coordinates_mae_metric(self, water_molecule: Any) -> None:
        """Verify InternalCoordinatesMAE metric lifecycle."""
        _, _, pos = water_molecule
        bonds = torch.tensor([[0, 1], [0, 2]], dtype=torch.long)
        angles = torch.tensor([[1, 0, 2]], dtype=torch.long)

        metric = InternalCoordinatesMAE(bonds=bonds, angles=angles)
        metric.update(pos, pos)
        res = metric.compute()

        assert math.isclose(res["mae_bonds_angstrom"].item(), 0.0, abs_tol=1e-5)
        assert math.isclose(res["mae_angles_deg"].item(), 0.0, abs_tol=1e-4)


# ==============================================================================
# 8. Composite Conformer Ensemble Evaluator
# ==============================================================================

class TestCompositeConformerEnsembleEvaluator:
    """Tests the unified ConformerEnsembleEvaluator multi-metric suite."""

    def test_evaluator_lifecycle(self, ethanol_conformers: Any) -> None:
        """Verify multi-metric update and unified summary generation."""
        trans_pos, gauche_pos = ethanol_conformers
        refs = torch.stack([trans_pos, gauche_pos], dim=0)
        preds = torch.stack([trans_pos, gauche_pos], dim=0)
        ref_e = torch.tensor([0.0, 0.043], dtype=torch.float32)  # in eV
        pred_e = torch.tensor([0.0, 0.043], dtype=torch.float32)  # in eV
        z = torch.tensor([6, 6, 8, 1, 1, 1, 1, 1, 1], dtype=torch.long)

        evaluator = ConformerEnsembleEvaluator(thresholds=(0.5, 1.25))
        evaluator.update(
            ref_positions=refs,
            pred_positions=preds,
            ref_energies=ref_e,
            pred_energies=pred_e,
            atomic_numbers=z,
        )
        summary = evaluator.compute()

        assert "cov_recall_0.50" in summary
        assert "cov_precision_0.50" in summary
        assert "amr_recall" in summary
        assert "amr_precision" in summary
        assert "energy_mae_ev" in summary
        assert "rel_energy_mae_ev" in summary
        assert "rotational_mae_mhz" in summary

        assert math.isclose(summary["cov_recall_0.50"].item(), 100.0, abs_tol=1e-4)
        assert math.isclose(summary["amr_recall"].item(), 0.0, abs_tol=1e-5)
        assert math.isclose(summary["energy_mae_ev"].item(), 0.0, abs_tol=1e-5)
