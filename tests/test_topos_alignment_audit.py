#!/usr/bin/env python3
"""
Adversarial QA & Physical Compliance Test Suite for intake/topos_alignment.py.
Module: tests/test_topos_alignment_audit.py
"""

import json
import math
import os
import sys
from pathlib import Path

import mendeleev
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import intake.topos_alignment as topos

# Water (H2O) - Asymmetric top (C2v, planar)
WATER_SYMBOLS = ["O", "H", "H"]
WATER_COORDS = np.array([
    [0.000000, 0.000000, 0.117300],
    [0.000000, 0.757200, -0.469200],
    [0.000000, -0.757200, -0.469200],
], dtype=np.float64)

# Carbon Dioxide (CO2) - Linear (Dinfh)
CO2_SYMBOLS = ["C", "O", "O"]
CO2_COORDS = np.array([
    [0.000000, 0.000000, 0.000000],
    [0.000000, 0.000000, 1.160000],
    [0.000000, 0.000000, -1.160000],
], dtype=np.float64)

# Methane (CH4) - Spherical top (Td)
METHANE_SYMBOLS = ["C", "H", "H", "H", "H"]
d = 1.087 / np.sqrt(3.0)
METHANE_COORDS = np.array([
    [0.0, 0.0, 0.0],
    [d, d, d],
    [d, -d, -d],
    [-d, d, -d],
    [-d, -d, d],
], dtype=np.float64)

# Ammonia (NH3) - Oblate symmetric top (C3v)
AMMONIA_SYMBOLS = ["N", "H", "H", "H"]
r_nh = 1.012
theta = np.radians(106.7)
h_z = r_nh * np.cos(theta / 2.0)
r_xy = r_nh * np.sin(theta / 2.0)
AMMONIA_COORDS = np.array([
    [0.0, 0.0, 0.38],
    [0.0, r_xy, -0.1],
    [r_xy * np.sqrt(3) / 2.0, -r_xy / 2.0, -0.1],
    [-r_xy * np.sqrt(3) / 2.0, -r_xy / 2.0, -0.1],
], dtype=np.float64)

# Methyl Chloride (CH3Cl) - Prolate symmetric top (C3v)
CH3CL_SYMBOLS = ["C", "Cl", "H", "H", "H"]
CH3CL_COORDS = np.array([
    [0.000000, 0.000000, 0.650000],
    [0.000000, 0.000000, -1.130000],
    [1.030000, 0.000000, 1.030000],
    [-0.515000, 0.892006, 1.030000],
    [-0.515000, -0.892006, 1.030000],
], dtype=np.float64)

# Benzene (C6H6) - Planar oblate symmetric top (D6h)
BENZENE_SYMBOLS = ["C", "C", "C", "C", "C", "C", "H", "H", "H", "H", "H", "H"]
r_cc, r_ch = 1.397, 1.084
angles = [np.radians(60 * i) for i in range(6)]
c_coords = [[r_cc * np.cos(a), r_cc * np.sin(a), 0.0] for a in angles]
h_coords = [[(r_cc + r_ch) * np.cos(a), (r_cc + r_ch) * np.sin(a), 0.0] for a in angles]
BENZENE_COORDS = np.array(c_coords + h_coords, dtype=np.float64)


class TestCenterOfMassAndMasses:
    def test_ghost_atom_detection(self):
        assert topos.is_ghost_symbol("Gh") is True
        assert topos.is_ghost_symbol("gh") is True
        assert topos.is_ghost_symbol("GhO") is True
        assert topos.is_ghost_symbol("Gh_C") is True
        assert topos.is_ghost_symbol("Bq") is True
        assert topos.is_ghost_symbol("bq") is True
        assert topos.is_ghost_symbol("X") is True
        assert topos.is_ghost_symbol("x") is True
        assert topos.is_ghost_symbol("X_N") is True
        assert topos.is_ghost_symbol("Xe") is False
        assert topos.is_ghost_symbol("xe") is False
        assert topos.is_ghost_symbol("C") is False
        assert topos.is_ghost_symbol("H") is False

    def test_physical_mass_retrieval(self):
        m_c = topos.get_physical_mass("C")
        m_o = topos.get_physical_mass("O")
        m_h = topos.get_physical_mass("H")
        m_xe = topos.get_physical_mass("Xe")

        assert abs(m_c - float(mendeleev.element("C").mass)) < 1e-6
        assert abs(m_o - float(mendeleev.element("O").mass)) < 1e-6
        assert abs(m_h - float(mendeleev.element("H").mass)) < 1e-6
        assert abs(m_xe - float(mendeleev.element("Xe").mass)) < 1e-6

        assert topos.get_physical_mass("Gh") == 0.0
        assert topos.get_physical_mass("GhO") == 0.0
        assert topos.get_physical_mass("Bq") == 0.0
        assert topos.get_physical_mass("X") == 0.0

    def test_com_translation_exact_zero(self):
        shifted_water = WATER_COORDS + np.array([12.34, -56.78, 90.12])
        trans_coords, shift_vec = topos.translate_to_center_of_mass(shifted_water, symbols=WATER_SYMBOLS)
        masses = topos.resolve_atomic_masses(shifted_water, symbols=WATER_SYMBOLS)

        new_com = np.sum(trans_coords * masses[:, np.newaxis], axis=0) / np.sum(masses)
        assert np.all(np.abs(new_com) < 1e-14)

        orig_dist = np.linalg.norm(shifted_water[0] - shifted_water[1])
        new_dist = np.linalg.norm(trans_coords[0] - trans_coords[1])
        assert abs(orig_dist - new_dist) < 1e-14

    def test_ghost_atom_bsse_protection(self):
        monomer_a = WATER_COORDS
        ghost_b = WATER_COORDS + np.array([0.0, 0.0, 3.0])
        dimer_coords = np.vstack([monomer_a, ghost_b])
        dimer_symbols = ["O", "H", "H", "GhO", "GhH", "GhH"]

        com_dimer = topos.compute_center_of_mass(dimer_coords, symbols=dimer_symbols)
        com_monomer = topos.compute_center_of_mass(monomer_a, symbols=WATER_SYMBOLS)

        np.testing.assert_allclose(com_dimer, com_monomer, atol=1e-14)

    def test_com_error_on_all_ghost_or_negative_mass(self):
        coords = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])
        with pytest.raises(ValueError, match="Total non-ghost molecular mass"):
            topos.compute_center_of_mass(coords, symbols=["Gh", "Gh"])

        with pytest.raises(ValueError, match="non-negative"):
            topos.compute_center_of_mass(coords, masses=[-1.0, 2.0])


class TestMomentOfInertiaEngine:
    def test_water_planar_asymmetric_top_and_inertial_defect(self):
        engine = topos.MomentOfInertiaEngine()
        res = engine.align_to_principal_axes(WATER_COORDS, symbols=WATER_SYMBOLS)

        assert res.top_type == "asymmetric_top"
        Ia, Ib, Ic = res.eigenvalues_amu_angstrom2
        assert Ia <= Ib <= Ic

        A, B, C = res.rotational_constants_mhz
        assert A > B > C
        assert abs(res.inertial_defect) < 1e-10
        assert -1.0 < res.rays_kappa < 1.0

        Pa, Pb, Pc = res.planar_moments
        assert abs(2.0 * (Pa + Pb + Pc) - (Ia + Ib + Ic)) < 1e-10
        assert abs(np.linalg.det(res.rotation_matrix) - 1.0) < 1e-12

    def test_carbon_dioxide_linear_rotor(self):
        engine = topos.MomentOfInertiaEngine()
        res = engine.align_to_principal_axes(CO2_COORDS, symbols=CO2_SYMBOLS)

        assert res.top_type == "linear"
        Ia, Ib, Ic = res.eigenvalues_amu_angstrom2
        assert abs(Ia) < 1e-8
        assert abs(Ib - Ic) < 1e-8
        assert math.isinf(res.rotational_constants_mhz[0])
        assert abs(res.rotational_constants_mhz[1] - res.rotational_constants_mhz[2]) < 1e-4
        assert res.rays_kappa == -1.0

    def test_methane_spherical_top(self):
        engine = topos.MomentOfInertiaEngine()
        res = engine.align_to_principal_axes(METHANE_COORDS, symbols=METHANE_SYMBOLS)

        assert res.top_type == "spherical_top"
        Ia, Ib, Ic = res.eigenvalues_amu_angstrom2
        assert abs(Ia - Ib) / Ib < 1e-4
        assert abs(Ib - Ic) / Ic < 1e-4
        assert res.rays_kappa == 0.0

    def test_benzene_planar_oblate_symmetric_top(self):
        engine = topos.MomentOfInertiaEngine()
        res = engine.align_to_principal_axes(BENZENE_COORDS, symbols=BENZENE_SYMBOLS)

        assert res.top_type == "oblate_symmetric_top"
        Ia, Ib, Ic = res.eigenvalues_amu_angstrom2
        assert abs(Ia - Ib) / Ib < 1e-4
        assert Ic > Ib
        assert abs(res.inertial_defect) < 1e-8
        assert abs(res.rays_kappa - 1.0) < 1e-4

    def test_methyl_chloride_prolate_symmetric_top(self):
        engine = topos.MomentOfInertiaEngine()
        res = engine.align_to_principal_axes(CH3CL_COORDS, symbols=CH3CL_SYMBOLS)

        assert res.top_type == "prolate_symmetric_top"
        Ia, Ib, Ic = res.eigenvalues_amu_angstrom2
        assert Ia < Ib
        assert abs(Ib - Ic) / Ic < 1e-4
        assert abs(res.rays_kappa - (-1.0)) < 1e-4


class TestLegacyPAFAligner:
    def test_paf_align_single(self):
        aligner = topos.LegacyPAFAligner()
        res = aligner.align_single(WATER_COORDS, symbols=WATER_SYMBOLS)

        assert isinstance(res, topos.PAFAlignmentResult)
        assert res.top_type == "asymmetric_top"
        assert abs(np.linalg.det(res.rotation_matrix) - 1.0) < 1e-12

    def test_paf_align_conformation_pair_sign_permutations(self):
        aligner = topos.LegacyPAFAligner()
        R_flip = np.diag([1.0, -1.0, -1.0])
        target_coords = WATER_COORDS @ R_flip + np.array([2.0, 3.0, -1.0])

        res = aligner.align_conformation_pair(target_coords, WATER_COORDS, symbols=WATER_SYMBOLS)
        assert res.rmsd_to_reference is not None
        assert res.rmsd_to_reference < 1e-10
        assert abs(np.linalg.det(res.rotation_matrix) - 1.0) < 1e-12


class TestEckartFrameAligner:
    def test_eckart_rigid_rotation_and_translation(self):
        theta = np.radians(37.5)
        R_z = np.array([
            [np.cos(theta), -np.sin(theta), 0],
            [np.sin(theta), np.cos(theta), 0],
            [0, 0, 1],
        ])
        target_coords = WATER_COORDS @ R_z.T + np.array([5.0, -2.0, 8.0])

        res = topos.EckartFrameAligner.align(target_coords, WATER_COORDS, symbols=WATER_SYMBOLS)
        assert res.rmsd < 1e-10
        assert res.translational_residual_norm < 1e-12
        assert res.residual_rotational_norm < 1e-12
        assert abs(np.linalg.det(res.rotation_matrix) - 1.0) < 1e-12

    def test_eckart_svd_reflection_protection(self):
        R_ref = np.diag([1.0, 1.0, -1.0])
        target_coords = WATER_COORDS @ R_ref

        res = topos.EckartFrameAligner.align(target_coords, WATER_COORDS, symbols=WATER_SYMBOLS)
        assert abs(np.linalg.det(res.rotation_matrix) - 1.0) < 1e-12


class TestVibrationalProjector:
    def test_vibrational_projector_water_algebraic_invariants(self):
        proj = topos.VibrationalProjector()
        P_vib = proj.construct_vibrational_projector(WATER_COORDS, symbols=WATER_SYMBOLS, is_linear=False)

        assert P_vib.shape == (9, 9)
        np.testing.assert_allclose(P_vib.T, P_vib, atol=1e-14)
        np.testing.assert_allclose(P_vib @ P_vib, P_vib, atol=1e-14)
        assert abs(np.trace(P_vib) - 3.0) < 1e-12

    def test_vibrational_projector_linear_co2(self):
        proj = topos.VibrationalProjector()
        P_vib = proj.construct_vibrational_projector(CO2_COORDS, symbols=CO2_SYMBOLS, is_linear=True)

        assert P_vib.shape == (9, 9)
        assert abs(np.trace(P_vib) - 4.0) < 1e-12
        np.testing.assert_allclose(P_vib @ P_vib, P_vib, atol=1e-14)

    def test_project_hessian_zeroing_rigid_modes(self):
        proj = topos.VibrationalProjector()
        N = len(WATER_COORDS)
        np.random.seed(42)
        A = np.random.randn(3 * N, 3 * N)
        H_mw = A.T @ A

        H_proj = proj.project_mass_weighted_hessian(H_mw, WATER_COORDS, symbols=WATER_SYMBOLS)
        eigvals = np.linalg.eigvalsh(H_proj)

        zero_modes = eigvals[:6]
        assert np.all(np.abs(zero_modes) < 1e-10)
        vib_modes = eigvals[6:]
        assert np.all(vib_modes > 1e-6)

    def test_project_cartesian_hessian_with_ghost_atoms_no_nan(self):
        proj = topos.VibrationalProjector()
        dimer_coords = np.vstack([WATER_COORDS, WATER_COORDS + np.array([0.0, 0.0, 3.0])])
        dimer_symbols = ["O", "H", "H", "GhO", "GhH", "GhH"]
        N = len(dimer_coords)

        H_cart = np.eye(3 * N, dtype=np.float64)
        H_cart_proj = proj.project_cartesian_hessian(H_cart, dimer_coords, symbols=dimer_symbols)

        assert not np.any(np.isnan(H_cart_proj))
        assert not np.any(np.isinf(H_cart_proj))


class TestStandardizationPipeline:
    def test_standardize_molecular_topology_dict(self):
        mol_dict = {
            "coords": WATER_COORDS.tolist(),
            "symbols": WATER_SYMBOLS,
        }
        res = topos.standardize_molecular_topology(mol_dict)

        assert isinstance(res, topos.ToposAlignmentResult)
        assert res.n_atoms == 3
        assert res.n_ghost_atoms == 0
        assert res.top_type == "asymmetric_top"
        assert abs(np.linalg.det(res.rotation_matrix) - 1.0) < 1e-12

        json_data = res.model_dump_json()
        loaded = json.loads(json_data)
        assert loaded["top_type"] == "asymmetric_top"
        assert len(loaded["aligned_coords"]) == 3

    def test_standardize_with_eckart_reference(self):
        ref_coords = WATER_COORDS
        target_coords = WATER_COORDS + np.array([0.05, -0.02, 0.01])

        res = topos.standardize_molecular_topology(
            mol=target_coords,
            symbols=WATER_SYMBOLS,
            ref_coords=ref_coords,
        )
        assert res.eckart_alignment_result is not None
        assert res.eckart_alignment_result.rmsd < 0.1
        assert res.eckart_alignment_result.residual_rotational_norm < 1e-12


class TestFileIOAndCLI:
    def test_xyz_parse_and_write_roundtrip(self, tmp_path):
        xyz_str = topos.format_aligned_xyz(WATER_SYMBOLS, WATER_COORDS, comment="Test Water")
        coords_parsed, symbols_parsed, comment = topos.parse_xyz_text(xyz_str)

        np.testing.assert_allclose(coords_parsed, WATER_COORDS, atol=1e-8)
        assert symbols_parsed == WATER_SYMBOLS
        assert "Test Water" in comment

        out_file = tmp_path / "water_aligned.xyz"
        topos.write_aligned_xyz(out_file, symbols_parsed, coords_parsed)
        assert out_file.is_file()

    def test_cli_execution_standardize_mode(self, tmp_path):
        in_xyz = tmp_path / "water.xyz"
        out_xyz = tmp_path / "water_aligned.xyz"
        out_json = tmp_path / "water_report.json"

        in_xyz.write_text(topos.format_aligned_xyz(WATER_SYMBOLS, WATER_COORDS), encoding="utf-8")

        exit_code = topos.main([
            str(in_xyz),
            "--mode", "standardize",
            "--output-xyz", str(out_xyz),
            "--output-json", str(out_json),
        ])
        assert exit_code == 0
        assert out_xyz.is_file()
        assert out_json.is_file()

        report = json.loads(out_json.read_text(encoding="utf-8"))
        assert report["top_type"] == "asymmetric_top"
        assert len(report["aligned_coords"]) == 3

    def test_cli_execution_paf_mode(self, tmp_path):
        in_xyz = tmp_path / "water.xyz"
        ref_xyz = tmp_path / "water_ref.xyz"
        out_json = tmp_path / "paf_report.json"

        in_xyz.write_text(topos.format_aligned_xyz(WATER_SYMBOLS, WATER_COORDS), encoding="utf-8")
        ref_xyz.write_text(topos.format_aligned_xyz(WATER_SYMBOLS, WATER_COORDS), encoding="utf-8")

        exit_code = topos.main([
            str(in_xyz),
            "--ref", str(ref_xyz),
            "--mode", "paf",
            "--output-json", str(out_json),
        ])
        assert exit_code == 0
        assert out_json.is_file()

        report = json.loads(out_json.read_text(encoding="utf-8"))
        assert report["rmsd_to_reference"] is not None
        assert report["rmsd_to_reference"] < 1e-10
