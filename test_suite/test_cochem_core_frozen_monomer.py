# -*- coding: utf-8 -*-
"""Comprehensive Authentic Test Suite for CoChem-CORE Composite and Frozen-Monomer Protocol.

Module: test_suite/test_cochem_core_frozen_monomer.py
Authoritative Target: core_engine/cochem_core_frozen_monomer.py

Verifies Method Matrix v4 §9 & Conference 2 §9A (§9A.1–§9A.7), §4.4, §4.5, §3.0–§3.3, §6.10, §8B.4:
1. Dynamic Mendeleev Mass Resolution (Mendeleev Mandate: ZERO hardcoded masses).
2. Exact Rigid-Rotor Inertial Tensor Diagonalization, Rotational Constants, Planar Moments,
   Inertial Defect, and Ray's Asymmetry.
3. Coordinate Sensitivity & Non-Linear Error Propagation (§4.5): Monomer bond error vs
   intermolecular separation and break-even equivalence.
4. Kabsch SVD Rigid Superposition and Monomer Geometry Substitution.
5. Optimization Spec & Mandatory §4.4 %geom Block with Tight Thresholds & Monomer Constraints.
6. Residual Gradient Gatekeeper (§9A.1 & §9A.7 Rule 8) and Deformation Strain Warning.
7. 3-Leg & 4-Leg Counterpoise Decomposition, BSSE, Half-CP, and Deformation Energy (§9A.7).
8. Trimer 3-Body Non-Additive Energy Decomposition (§9A.5 Prohibition 3 & §9A.7 Rule 12).
9. Nano-LEGO Template Scaling (§9A.4 / Recipe R5) with Strict B3LYP Prohibition Enforced.
10. ChS Composite Geometry (CBS+CV) with n^-3 Parameter-Wise Extrapolation (§9A.4 / Recipe R4).
11. Focal-Point Composite Energy and Gradient Combination (§9A.3 / Recipe R7).
12. Method Matrix Prohibitions Enforcer (§9A.5 & §9A.7 Rules 1–2).
13. Recipe Menu R1 – R9 Definitions, Execution Plans, and Structured Reports (§9A.6).
14. Free Isotopologue Force Field / Mass Substitution Engine (§6.10 / §8B.4).
15. Standalone CLI Parsing and Execution.
"""

from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent if '__file__' in locals() else Path(r'D:\__CoChem\GitHub-Repo\CoChem-BASE')
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cochem_base.exceptions import (
    CoChemError,
    FrozenMonomerViolationError,
    MethodMatrixViolationError,
    ProvenanceErrorCode,
)
from core_engine.cochem_core_frozen_monomer import (
    ANGSTROM_TO_BOHR,
    BOHR_TO_ANGSTROM,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    INERTIA_CONV_MHZ_U_ANG2,
    STANDARD_TEMPLATE_PARAMETERS,
    TOL_E_DEFAULT,
    TOL_MAXD_DEFAULT,
    TOL_MAXG_DEFAULT,
    TOL_RMSG_DEFAULT,
    TOL_RMSD_DEFAULT,
    CompositeGeometryResult,
    CompositeScheme,
    CounterpoiseDecomposition,
    FrozenMonomerFlag,
    FrozenMonomerOptimizationSpec,
    MonomerPartition,
    RecipeExecutionPlan,
    RecipeReport,
    ResidualGradientCheck,
    RotationalConstantsResult,
    SensitivityResult,
    TemplateScalingParameter,
    TemplateScalingResult,
    analyze_rotational_sensitivity,
    apply_template_scaling,
    build_cli_parser,
    check_frozen_residual_gradients,
    compute_chs_composite_geometry,
    compute_focal_point_energy,
    compute_focal_point_gradient,
    compute_isotopologue_rotational_constants,
    compute_rotational_constants,
    decompose_counterpoise_energy,
    decompose_manybody_trimer,
    evaluate_recipe_result,
    format_xyz_string,
    generate_frozen_monomer_optimization_spec,
    get_dynamic_atomic_mass,
    get_recipe_plan,
    kabsch_superimpose,
    main as cli_main,
    parse_xyz_string,
    replace_monomer_geometry_in_complex,
    validate_composite_protocol,
)

# 1. Authentic Water Monomer H2O
H2O_SYMBOLS = ["O", "H", "H"]
H2O_COORDS = np.array([
    [0.000000, 0.000000,  0.117215],
    [0.000000, 0.757049, -0.468860],
    [0.000000, -0.757049, -0.468860],
], dtype=np.float64)

# 2. Authentic Carbon Dioxide Monomer CO2
CO2_SYMBOLS = ["O", "C", "O"]
CO2_COORDS = np.array([
    [0.0, 0.0, -1.160000],
    [0.0, 0.0,  0.000000],
    [0.0, 0.0,  1.160000],
], dtype=np.float64)

# 3. Authentic T-Shaped CO2...H2O van der Waals Complex
CO2_H2O_SYMBOLS = ["O", "C", "O", "O", "H", "H"]
CO2_H2O_COORDS = np.array([
    [0.0000, 0.0000, -1.1600],  # CO2 O1
    [0.0000, 0.0000,  0.0000],  # CO2 C2
    [0.0000, 0.0000,  1.1600],  # CO2 O3
    [2.8360, 0.0000,  0.0000],  # H2O O4
    [3.3500, 0.7570,  0.0000],  # H2O H5
    [3.3500, -0.7570, 0.0000],  # H2O H6
], dtype=np.float64)

CO2_INDICES = [0, 1, 2]
H2O_INDICES = [3, 4, 5]


class TestDynamicMendeleevMass:
    """Verifies compliance with CoChem Mendeleev Library Mandate."""

    def test_dynamic_atomic_masses_elements(self) -> None:
        m_h = get_dynamic_atomic_mass("H")
        m_c = get_dynamic_atomic_mass("C")
        m_o = get_dynamic_atomic_mass("O")
        m_n = get_dynamic_atomic_mass("N")

        assert 1.007 < m_h < 1.009
        assert 12.010 < m_c < 12.012
        assert 15.998 < m_o < 16.001
        assert 14.005 < m_n < 14.008

    def test_dynamic_isotopic_masses(self) -> None:
        m_d = get_dynamic_atomic_mass("D")
        m_t = get_dynamic_atomic_mass("T")
        m_c13 = get_dynamic_atomic_mass("C", mass_number=13)
        m_o18 = get_dynamic_atomic_mass("O", mass_number=18)

        assert 2.013 < m_d < 2.015
        assert 3.015 < m_t < 3.017
        assert 13.003 < m_c13 < 13.004
        assert 17.999 < m_o18 < 18.000

    def test_atomic_number_resolution(self) -> None:
        m_c_int = get_dynamic_atomic_mass(6)
        m_c_str = get_dynamic_atomic_mass("6")
        assert math.isclose(m_c_int, m_c_str, rel_tol=1e-9)

    def test_dynamic_mass_unknown_element_raises(self) -> None:
        with pytest.raises(Exception):
            get_dynamic_atomic_mass("XxFakeElement")
        with pytest.raises(ValueError):
            get_dynamic_atomic_mass("C", mass_number=999)


class TestRotationalConstantsEngine:
    """Verifies rigid-rotor inertial tensor diagonalization and constants."""

    def test_water_monomer_constants(self) -> None:
        res = compute_rotational_constants(H2O_SYMBOLS, H2O_COORDS)
        assert res.A_MHz > res.B_MHz > res.C_MHz
        assert res.A_MHz > 700000.0
        assert res.Paa_uA2 > 0.0
        assert abs(res.Pcc_uA2) < 1e-4
        assert abs(res.inertial_defect_uA2) < 1e-4

    def test_linear_molecule_constants(self) -> None:
        res = compute_rotational_constants(CO2_SYMBOLS, CO2_COORDS)
        assert math.isclose(res.B_MHz, res.C_MHz, rel_tol=1e-5)
        assert res.B_MHz > 0.0

    def test_co2_h2o_complex_constants(self) -> None:
        res = compute_rotational_constants(CO2_H2O_SYMBOLS, CO2_H2O_COORDS)
        assert res.A_MHz > res.B_MHz >= res.C_MHz
        assert 10000.0 < res.A_MHz < 15000.0
        assert 3000.0 < res.B_MHz < 6000.0

    def test_planar_moments_and_inertial_defect_invariants(self) -> None:
        res = compute_rotational_constants(H2O_SYMBOLS, H2O_COORDS)
        assert math.isclose(res.inertial_defect_uA2, -2.0 * res.Pcc_uA2, rel_tol=1e-7, abs_tol=1e-9)
        assert math.isclose(res.Ia_uA2 + res.Ib_uA2 + res.inertial_defect_uA2, res.Ic_uA2, rel_tol=1e-7, abs_tol=1e-9)

    def test_asymmetry_parameter_prolate_oblate_limits(self) -> None:
        res_co2 = compute_rotational_constants(CO2_SYMBOLS, CO2_COORDS)
        assert math.isclose(res_co2.ray_kappa, -1.0, rel_tol=1e-4)


class TestRotationalSensitivity:
    """Verifies non-linear error propagation and Method Matrix §4.5 headline."""

    def test_co2_h2o_sensitivity_propagation(self) -> None:
        sens = analyze_rotational_sensitivity(
            symbols=CO2_H2O_SYMBOLS,
            coordinates_angstrom=CO2_H2O_COORDS,
            monomer_a_indices=CO2_INDICES,
            monomer_b_indices=H2O_INDICES,
            delta_r_angstrom=0.001,
            delta_R_angstrom=0.002,
        )
        assert abs(sens.delta_A_pct) > abs(sens.delta_B_pct)
        assert abs(sens.delta_B_MHz) > 1.0
        assert sens.break_even_monomer_bond_error_mAngstrom > 0.0


class TestKabschSuperposition:
    def test_identity_superposition(self) -> None:
        aligned, R, trans, rmsd = kabsch_superimpose(H2O_COORDS, H2O_COORDS)
        assert rmsd < 1e-12
        assert np.allclose(aligned, H2O_COORDS, atol=1e-9)

    def test_replace_monomer_geometry(self) -> None:
        high_level_h2o = H2O_COORDS * 0.99
        new_complex, rmsd = replace_monomer_geometry_in_complex(
            complex_symbols=CO2_H2O_SYMBOLS,
            complex_coords=CO2_H2O_COORDS,
            monomer_indices=H2O_INDICES,
            isolated_monomer_coords=high_level_h2o,
        )
        assert np.allclose(new_complex[CO2_INDICES], CO2_H2O_COORDS[CO2_INDICES], atol=1e-12)
        assert not np.allclose(new_complex[H2O_INDICES], CO2_H2O_COORDS[H2O_INDICES])

    def test_kabsch_superposition_arbitrary_3d_rotation(self) -> None:
        theta = 0.45
        phi = 0.78
        R_z = np.array([[np.cos(theta), -np.sin(theta), 0], [np.sin(theta), np.cos(theta), 0], [0, 0, 1]], dtype=np.float64)
        R_x = np.array([[1, 0, 0], [0, np.cos(phi), -np.sin(phi)], [0, np.sin(phi), np.cos(phi)]], dtype=np.float64)
        R_rot = np.dot(R_z, R_x)
        trans = np.array([1.5, -2.3, 4.1], dtype=np.float64)
        target_coords = np.dot(H2O_COORDS, R_rot.T) + trans

        aligned, R_est, trans_est, rmsd = kabsch_superimpose(H2O_COORDS, target_coords)
        assert rmsd < 1e-10
        assert np.allclose(aligned, target_coords, atol=1e-8)


class TestOptimizationSpecGenerator:
    def test_generate_frozen_iso_spec(self) -> None:
        part_co2 = MonomerPartition(fragment_id="CO2", name="CO2", atom_indices=CO2_INDICES)
        part_h2o = MonomerPartition(fragment_id="H2O", name="H2O", atom_indices=H2O_INDICES)
        spec = generate_frozen_monomer_optimization_spec(
            symbols=CO2_H2O_SYMBOLS,
            coordinates_angstrom=CO2_H2O_COORDS,
            partitions=[part_co2, part_h2o],
            frozen_monomer_flag=FrozenMonomerFlag.FROZEN_ISO,
            method_name="wB97M-V",
            basis_set="def2-QZVPP",
        )
        assert spec.frozen_monomer_flag == FrozenMonomerFlag.FROZEN_ISO
        assert "InHess   XTB2" in spec.orca_geom_block
        assert f"TolE     {TOL_E_DEFAULT:.1e}" in spec.orca_geom_block
        assert f"TolMaxG  {TOL_MAXG_DEFAULT:.1e}" in spec.orca_geom_block
        assert "Constraints" in spec.orca_geom_block
        assert spec.free_dofs == 6

    def test_generate_relaxed_optimization_spec(self) -> None:
        part_co2 = MonomerPartition(fragment_id="CO2", name="CO2", atom_indices=CO2_INDICES)
        part_h2o = MonomerPartition(fragment_id="H2O", name="H2O", atom_indices=H2O_INDICES)
        spec = generate_frozen_monomer_optimization_spec(
            symbols=CO2_H2O_SYMBOLS,
            coordinates_angstrom=CO2_H2O_COORDS,
            partitions=[part_co2, part_h2o],
            frozen_monomer_flag=FrozenMonomerFlag.RELAXED,
        )
        assert spec.frozen_monomer_flag == FrozenMonomerFlag.RELAXED
        assert spec.frozen_atom_count == 0
        assert "Fully relaxed" in spec.orca_constraints_block

    def test_generate_frozen_inc_optimization_spec(self) -> None:
        part_co2 = MonomerPartition(fragment_id="CO2", name="CO2", atom_indices=CO2_INDICES)
        part_h2o = MonomerPartition(fragment_id="H2O", name="H2O", atom_indices=H2O_INDICES)
        spec = generate_frozen_monomer_optimization_spec(
            symbols=CO2_H2O_SYMBOLS,
            coordinates_angstrom=CO2_H2O_COORDS,
            partitions=[part_co2, part_h2o],
            frozen_monomer_flag=FrozenMonomerFlag.FROZEN_INC,
        )
        assert spec.frozen_monomer_flag == FrozenMonomerFlag.FROZEN_INC
        assert spec.frozen_atom_count == 6


class TestResidualGradientGatekeeper:
    def test_clean_gradient_passes(self) -> None:
        grad = np.array([
            [1e-6, -2e-6, 1e-6],
            [2e-6,  1e-6, 3e-6],
            [1e-6,  0e-0, -1e-6],
            [1e-4,  1e-4, 1e-4],
            [1e-4,  1e-4, 1e-4],
            [1e-4,  1e-4, 1e-4],
        ], dtype=np.float64)
        res = check_frozen_residual_gradients(grad, frozen_atom_indices=CO2_INDICES, tol_max_g=TOL_MAXG_DEFAULT)
        assert res.passes_gate is True
        assert res.deformation_channel_flag is False

    def test_strained_gradient_triggers_warning(self) -> None:
        grad = np.array([
            [5e-5, -2e-5, 1e-5],
            [2e-5,  1e-5, 3e-5],
            [1e-5,  0e-0, -1e-5],
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
        ], dtype=np.float64)
        res = check_frozen_residual_gradients(grad, frozen_atom_indices=CO2_INDICES, tol_max_g=TOL_MAXG_DEFAULT)
        assert res.passes_gate is False
        assert res.deformation_channel_flag is True
        assert "DEFORMATION_CHANNEL_ACTIVE" in res.warning_message


class TestCounterpoiseDecomposition:
    def test_counterpoise_decomposition_values(self) -> None:
        res = decompose_counterpoise_energy(
            E_AB_AB=-264.100,
            E_A_AB=-188.048,
            E_B_AB=-76.048,
            E_A_A=-188.045,
            E_B_B=-76.046,
        )
        assert math.isclose(res.delta_E_CP_hartree, -0.004, rel_tol=1e-9)
        assert math.isclose(res.delta_E_CP_kcal_mol, -0.004 * HARTREE_TO_KCAL_MOL, rel_tol=1e-9)
        assert math.isclose(res.delta_E_noCP_hartree, -0.009, rel_tol=1e-9)
        assert math.isclose(res.E_BSSE_hartree, 0.005, rel_tol=1e-9)
        assert math.isclose(res.delta_E_halfCP_hartree, -0.0065, rel_tol=1e-9)

    def test_counterpoise_4leg_deformation_energies(self) -> None:
        res = decompose_counterpoise_energy(
            E_AB_AB=-264.100,
            E_A_AB=-188.048,
            E_B_AB=-76.048,
            E_A_A=-188.050,
            E_B_B=-76.050,
        )
        assert res.monomer_A_def_kcal_mol is not None
        assert math.isclose(res.monomer_A_def_kcal_mol, 0.002 * HARTREE_TO_KCAL_MOL, rel_tol=1e-9)
        assert math.isclose(res.monomer_B_def_kcal_mol, 0.002 * HARTREE_TO_KCAL_MOL, rel_tol=1e-9)
        assert math.isclose(res.E_def_total_kcal_mol, 0.004 * HARTREE_TO_KCAL_MOL, rel_tol=1e-9)


class TestTrimerManyBodyDecomposition:
    def test_trimer_decomposition(self) -> None:
        res = decompose_manybody_trimer(
            E_ABC=-228.150,
            E_AB=-152.095,
            E_BC=-152.095,
            E_AC=-152.095,
            E_A=-76.045,
            E_B=-76.045,
            E_C=-76.045,
        )
        assert "delta_E_3body_nonadditive_kcal_mol" in res
        assert "ratio_3body_pct" in res


class TestTemplateScalingEngine:
    def test_template_scaling_revdsd(self) -> None:
        res = apply_template_scaling(
            symbols=H2O_SYMBOLS,
            coordinates_angstrom=H2O_COORDS,
            starting_method="revDSD-PBEP86-D4",
        )
        assert len(res.applied_bond_corrections) > 0
        assert res.rotational_constants_scaled.A_MHz > 0.0

    def test_template_scaling_b3lyp_prohibition(self) -> None:
        with pytest.raises(MethodMatrixViolationError) as exc_info:
            apply_template_scaling(
                symbols=H2O_SYMBOLS,
                coordinates_angstrom=H2O_COORDS,
                starting_method="B3LYP-D4",
            )
        assert "strictly forbids template scaling on B3LYP" in str(exc_info.value)


class TestChSCompositeGeometry:
    def test_chs_composite_geometry(self) -> None:
        base_coords = H2O_COORDS
        mp2_tz = H2O_COORDS * 1.002
        mp2_qz = H2O_COORDS * 1.001
        mp2_cv_ae = H2O_COORDS * 0.999
        mp2_cv_fc = H2O_COORDS * 1.000

        res = compute_chs_composite_geometry(
            symbols=H2O_SYMBOLS,
            coords_fcccsdt_tz=base_coords,
            coords_mp2_tz=mp2_tz,
            coords_mp2_qz=mp2_qz,
            coords_mp2_cv_ae=mp2_cv_ae,
            coords_mp2_cv_fc=mp2_cv_fc,
            extrapolation_power=3.0,
        )
        assert res.scheme == CompositeScheme.R4_CHS_CBS_CV
        assert res.rotational_constants.A_MHz > 0.0
        assert "[M] 0.13 %" in res.provenance_tags["MAE_Be"]


class TestFocalPointAnalysis:
    def test_focal_point_energy(self) -> None:
        e_mp2_large = -76.350
        e_cc_small = -76.280
        e_mp2_small = -76.250
        e_fp = compute_focal_point_energy(e_mp2_large, e_cc_small, e_mp2_small)
        assert math.isclose(e_fp, -76.380, rel_tol=1e-9)

    def test_focal_point_gradient(self) -> None:
        g_mp2_large = np.full((3, 3), 0.005)
        g_cc_small = np.full((3, 3), 0.002)
        g_mp2_small = np.full((3, 3), 0.003)
        g_fp = compute_focal_point_gradient(g_mp2_large, g_cc_small, g_mp2_small)
        assert np.allclose(g_fp, 0.004, atol=1e-9)


class TestMethodMatrixProhibitions:
    def test_prohibit_additive_diffuse(self) -> None:
        with pytest.raises(MethodMatrixViolationError) as exc_info:
            validate_composite_protocol(
                scheme=CompositeScheme.R4_CHS_CBS_CV,
                functional_or_method="CCSD(T)",
                basis_set="cc-pVXZ",
                has_additive_diffuse_correction=True,
            )
        assert "Additive diffuse-function corrections" in str(exc_info.value)

    def test_prohibit_oniom_on_small_complexes(self) -> None:
        with pytest.raises(MethodMatrixViolationError) as exc_info:
            validate_composite_protocol(
                scheme=CompositeScheme.R9_ONIOM_REJECTED,
                functional_or_method="ONIOM",
                basis_set="mixed",
                is_oniom_partition=True,
                atom_count=6,
            )
        assert "ONIOM / QM-QM2 is rejected" in str(exc_info.value)

    def test_prohibit_d4_on_vv10_or_3c(self) -> None:
        with pytest.raises(MethodMatrixViolationError) as exc_info:
            validate_composite_protocol(
                scheme=CompositeScheme.R2_WB97MV_QZ_CP,
                functional_or_method="wB97M-V",
                basis_set="def2-QZVPP",
                has_d4_dispersion=True,
            )
        assert "Never add D4 dispersion to wB97M-V" in str(exc_info.value)


class TestRecipeMenuEngine:
    def test_get_all_recipe_plans(self) -> None:
        for r_id in ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9"]:
            plan = get_recipe_plan(r_id)
            assert plan.recipe_id == r_id
            assert len(plan.steps) > 0

    def test_evaluate_recipe_r2_report(self) -> None:
        report = evaluate_recipe_result(
            recipe_id="R2",
            Be_MHz=4650.0,
            delta_B_vib_MHz=-25.0,
            residual_gradient_max=5e-6,
            softest_mode_cm1=35.0,
            interaction_energy_kcal_mol=-3.2,
        )
        assert report.recipe_id == "R2"
        assert report.B0_MHz == 4625.0
        assert report.search_window_halfwidth_MHz == 0.005 * 4625.0
        assert "Recipe R2 executed in compliance" in report.compliance_verdict

    def test_recipe_r1_unapplied_vib_note(self) -> None:
        report = evaluate_recipe_result(recipe_id="R1", Be_MHz=5200.0)
        assert report.recipe_id == "R1"
        assert report.B0_MHz is None
        assert any("ΔB_vib is unapplied" in note for note in report.notes)

    def test_recipe_r8_energy_only_plan(self) -> None:
        plan = get_recipe_plan("R8")
        assert "ZERO improvement in B" in plan.expected_accuracy_Be
        assert any("energy-only" in p.lower() for p in plan.prohibitions)

    def test_unknown_recipe_id_raises(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            get_recipe_plan("R99")
        assert "Unknown recipe ID 'R99'" in str(exc_info.value)


class TestIsotopologueEngine:
    def test_isotopologue_water_deuteration(self) -> None:
        h2o = compute_rotational_constants(H2O_SYMBOLS, H2O_COORDS)
        hdo = compute_isotopologue_rotational_constants(H2O_SYMBOLS, H2O_COORDS, isotopic_substitutions={1: 2})
        d2o = compute_isotopologue_rotational_constants(H2O_SYMBOLS, H2O_COORDS, isotopic_substitutions={1: 2, 2: 2})
        assert h2o.B_MHz > hdo.B_MHz > d2o.B_MHz
        assert h2o.total_mass_u < hdo.total_mass_u < d2o.total_mass_u


class TestFrozenMonomerCLI:
    def test_parse_and_format_xyz(self) -> None:
        xyz_str = format_xyz_string(H2O_SYMBOLS, H2O_COORDS, comment="Test water")
        symbols, coords = parse_xyz_string(xyz_str)
        assert symbols == H2O_SYMBOLS
        assert np.allclose(coords, H2O_COORDS, atol=1e-8)

    def test_cli_rotational_constants(self, tmp_path: Path) -> None:
        xyz_file = tmp_path / "water.xyz"
        xyz_file.write_text(format_xyz_string(H2O_SYMBOLS, H2O_COORDS), encoding="utf-8")

        ret = cli_main(["rotational-constants", "--xyz", str(xyz_file), "--json"])
        assert ret == 0

    def test_cli_sensitivity(self, tmp_path: Path) -> None:
        xyz_file = tmp_path / "dimer.xyz"
        xyz_file.write_text(format_xyz_string(CO2_H2O_SYMBOLS, CO2_H2O_COORDS), encoding="utf-8")

        ret = cli_main([
            "sensitivity",
            "--xyz", str(xyz_file),
            "--monomer-a", "0,1,2",
            "--monomer-b", "3,4,5",
        ])
        assert ret == 0

    def test_cli_counterpoise(self) -> None:
        ret = cli_main([
            "counterpoise",
            "--e-ab-ab", "-264.100",
            "--e-a-ab", "-188.048",
            "--e-b-ab", "-76.048",
            "--e-a-a", "-188.045",
            "--e-b-b", "-76.046",
        ])
        assert ret == 0

    def test_cli_generate_spec(self, tmp_path: Path) -> None:
        xyz_file = tmp_path / "dimer.xyz"
        xyz_file.write_text(format_xyz_string(CO2_H2O_SYMBOLS, CO2_H2O_COORDS), encoding="utf-8")

        ret = cli_main([
            "generate-spec",
            "--xyz", str(xyz_file),
            "--monomer-a", "0,1,2",
            "--monomer-b", "3,4,5",
            "--flag", "frozen-iso",
        ])
        assert ret == 0

    def test_cli_recipe(self) -> None:
        ret = cli_main(["recipe", "--id", "R2", "--be", "4650.0", "--delta-b-vib", "-25.0"])
        assert ret == 0
