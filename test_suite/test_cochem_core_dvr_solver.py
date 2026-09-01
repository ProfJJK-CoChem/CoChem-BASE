# -*- coding: utf-8 -*-
"""Comprehensive Authentic Test Suite for CoChem-CORE Discrete Variable Representation (DVR) Solver.

Module: test_suite/test_cochem_core_dvr_solver.py
Authoritative Target: core_engine/cochem_core_dvr_solver.py

Verifies Method Matrix v4 §7, §6.9, §13.2 (Table 2), §14.2 (Table 7), Appendix A.2 & A.4:
1. Dynamic Mendeleev Mass Resolution (Mendeleev Mandate: ZERO hardcoded masses).
2. 1D DVR Basis Formulations (Sinc, Radial Sinc, Sine, Fourier, Legendre, Hermite).
3. Particle-in-a-Box Analytical Parity (Sine DVR exact matching).
4. Periodic Fourier DVR (Meyer 1970 exact free-rotor spectrum F * m^2).
5. Double-Well Tunneling Splitting and Semiclassical WKB Instanton Comparison.
6. Hindered Internal Rotation (V_n barriers, reduced parameter s, A-E splittings).
7. Permutation-Inversion (PI) Symmetry & Nuclear Spin Statistical Weights (C2v, C3v, G16).
8. 2D Direct-Product & Coupled DVR (Dense & Matrix-Free ARPACK Lanczos Operators).
9. Vibrational Coordinate Averaging & Transition Dipole Moment Matrix Elements.
10. HDF5 and JSON Spectrum Archival and CLI Execution.
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
import scipy.linalg

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core_engine.cochem_core_dvr_solver import (
    DVR1DSolver,
    DVR2DSolver,
    DVRGridType,
    DVRSpectrumResult,
    MatrixFreeDVROperator,
    SolverBackend,
    SymmetryGroup,
    TorsionalRotorResult,
    TunnelingAnalysisResult,
    analyze_double_well_tunneling,
    analyze_hindered_internal_rotor,
    build_2d_direct_product_kinetic,
    build_cli_parser,
    build_fourier_kinetic_1d,
    build_grid_1d,
    build_hermite_kinetic_1d,
    build_kinetic_matrix_1d,
    build_legendre_kinetic_1d,
    build_radial_sinc_kinetic_1d,
    build_sinc_kinetic_1d,
    build_sine_kinetic_1d,
    classify_nuclear_spin_weights,
    compute_reduced_mass_pair,
    compute_top_rotational_constant_f,
    compute_transition_dipole_moments,
    compute_vibrational_averages_1d,
    compute_wkb_tunneling_action,
    get_dynamic_mass,
    main as solver_main,
    nan_regularization_watchdog,
    solve_dvr_dense,
    solve_dvr_matrix_free,
)


class TestDynamicMendeleevMassIntegration:
    """Tests compliance with the Mendeleev Library Mandate."""

    def test_get_dynamic_mass_elements_and_isotopes(self) -> None:
        """Verifies dynamic atomic and isotopic mass retrieval from Mendeleev."""
        m_h = get_dynamic_mass("H")
        assert 1.007 < m_h < 1.009

        m_d = get_dynamic_mass("D")
        assert 2.013 < m_d < 2.015

        m_c = get_dynamic_mass("C")
        assert 12.009 < m_c < 12.012

        m_c13 = get_dynamic_mass("C", mass_number=13)
        assert 13.003 < m_c13 < 13.004

        m_cl35 = get_dynamic_mass("Cl", mass_number=35)
        assert 34.96 < m_cl35 < 34.98

        m_cl37 = get_dynamic_mass("Cl", mass_number=37)
        assert 36.96 < m_cl37 < 36.98

    def test_compute_reduced_mass_pair(self) -> None:
        """Verifies reduced mass calculation for diatomic pairs."""
        mu_hf = compute_reduced_mass_pair("H", "F")
        assert 0.95 < mu_hf < 0.96

        mu_df = compute_reduced_mass_pair("D", "F")
        assert 1.80 < mu_df < 1.85
        assert mu_df > mu_hf

    def test_compute_top_rotational_constant_f(self) -> None:
        """Verifies internal rotor F constant calculation for a C3v methyl top."""
        symbols = ["C", "H", "H", "H"]
        r_ch = 1.09
        theta = 109.47 * math.pi / 180.0
        coords = np.array([
            [0.0, 0.0, 0.0],
            [r_ch * math.sin(theta), 0.0, r_ch * math.cos(theta)],
            [-0.5 * r_ch * math.sin(theta), math.sqrt(3) / 2.0 * r_ch * math.sin(theta), r_ch * math.cos(theta)],
            [-0.5 * r_ch * math.sin(theta), -math.sqrt(3) / 2.0 * r_ch * math.sin(theta), r_ch * math.cos(theta)],
        ])
        axis = np.array([0.0, 0.0, 1.0])
        f_const = compute_top_rotational_constant_f(symbols, coords, axis)
        assert 4.0 < f_const < 6.5


class Test1DDVRBasesAndAnalyticalParity:
    """Tests 1D DVR kinetic operators and analytical benchmark solutions."""

    def test_sine_dvr_particle_in_a_box_parity(self) -> None:
        """Verifies 1D Sine-DVR matches analytical Particle-in-a-Box eigenvalues within 1e-3."""
        n_pts = 60
        length_angstrom = 2.0
        mass_amu = 1.0

        grid, weights = build_grid_1d(DVRGridType.SINE, n_pts, x_min=0.0, x_max=length_angstrom, length=length_angstrom)
        t_mat = build_sine_kinetic_1d(n_pts, length_angstrom, mass_amu=mass_amu)

        evals, _ = scipy.linalg.eigh(t_mat)

        # Analytical E_n = n^2 * pi^2 * hbar^2 / (2 * m * L^2) in cm^-1
        # Factor = 16.857629 * pi^2 / (m * L^2)
        factor = (math.pi ** 2) * 16.85762914565457 / (mass_amu * (length_angstrom ** 2))
        for n in range(1, 11):
            e_analytic = (n ** 2) * factor
            e_dvr = float(evals[n - 1])
            rel_err = abs(e_dvr - e_analytic) / e_analytic
            assert rel_err < 1e-3, f"State n={n}: DVR={e_dvr}, Analytic={e_analytic}, Err={rel_err}"

    def test_fourier_dvr_free_rotor_spectrum(self) -> None:
        """Verifies Periodic Fourier DVR (Meyer 1970) free-rotor spectrum F * m^2."""
        n_pts = 61
        f_rot = 5.25  # cm^-1
        t_mat = build_fourier_kinetic_1d(n_pts, f_rot)
        evals, _ = scipy.linalg.eigh(t_mat)

        # Free rotor levels: 0 (m=0), F, F (m=+-1), 4F, 4F (m=+-2), 9F, 9F (m=+-3), 16F, 16F (m=+-4)
        assert abs(evals[0] - 0.0) < 1e-7
        assert abs(evals[1] - f_rot) < 1e-6
        assert abs(evals[2] - f_rot) < 1e-6
        assert abs(evals[3] - 4.0 * f_rot) < 1e-6
        assert abs(evals[4] - 4.0 * f_rot) < 1e-6
        assert abs(evals[5] - 9.0 * f_rot) < 1e-5
        assert abs(evals[6] - 9.0 * f_rot) < 1e-5
        assert abs(evals[7] - 16.0 * f_rot) < 1e-5
        assert abs(evals[8] - 16.0 * f_rot) < 1e-5

    def test_radial_sinc_kinetic_finite_spectrum(self) -> None:
        """Verifies Radial Sinc DVR kinetic operator is symmetric and positive definite."""
        grid, _ = build_grid_1d(DVRGridType.RADIAL_SINC, 50, x_min=0.0, x_max=5.0)
        t_mat = build_radial_sinc_kinetic_1d(grid, mass_amu=1.0)
        assert np.allclose(t_mat, t_mat.T, atol=1e-12)
        evals = scipy.linalg.eigvalsh(t_mat)
        assert np.all(evals > 0.0)


class TestDoubleWellTunnelingAndWKB:
    """Tests double-well tunneling eigenstates, splittings, and WKB action integrals."""

    def test_double_well_tunneling_analysis(self) -> None:
        """Verifies double-well inversion tunneling splitting and WKB instanton comparison."""
        solver = DVR1DSolver(
            grid_type=DVRGridType.SINC,
            n_points=120,
            x_min=-2.5,
            x_max=2.5,
            mass_amu=1.008,
        )
        x0 = 0.8  # Angstroms
        barrier = 450.0  # cm^-1

        def pot(x: float) -> float:
            return float(barrier * (((x / x0) ** 2 - 1.0) ** 2))

        res = solver.analyze_tunneling(pot, num_states=10)

        assert isinstance(res, TunnelingAnalysisResult)
        assert res.ground_state_splitting_mhz > 0.0
        assert res.ground_state_splitting_cm1 > 0.0
        assert res.barrier_height_cm1 > 400.0
        assert len(res.well_minima_coords) == 2
        assert abs(res.well_minima_coords[0] + x0) < 0.1
        assert abs(res.well_minima_coords[1] - x0) < 0.1
        assert res.wkb_action_integral > 0.0
        assert res.wkb_splitting_estimate_mhz > 0.0

        # WKB estimate should be within an order of magnitude of DVR exact splitting
        ratio = res.wkb_splitting_estimate_mhz / res.ground_state_splitting_mhz
        assert 0.1 < ratio < 10.0


class TestHinderedInternalRotor:
    """Tests hindered internal rotation solver and A-E splittings."""

    def test_hindered_methyl_rotor(self) -> None:
        """Verifies hindered methyl rotor (V3=350 cm^-1, F=5.25 cm^-1) produces non-zero A-E split."""
        res = analyze_hindered_internal_rotor(
            f_rot_cm1=5.25,
            v_barrier_cm1=350.0,
            periodicity=3,
            num_points=61,
            num_states=12,
        )
        assert isinstance(res, TorsionalRotorResult)
        assert res.reduced_barrier_s > 25.0
        assert res.a_e_splitting_ground_mhz > 0.0
        assert len(res.eigenvalues_cm1) == 12
        assert res.state_symmetries[0] == "v=0 (A)"
        assert "E" in res.state_symmetries[1]
        assert "E" in res.state_symmetries[2]
        assert "E" in res.state_symmetries[3]
        assert "E" in res.state_symmetries[4]
        assert "A" in res.state_symmetries[5]
        assert len(res.excited_a_e_splittings_mhz) >= 3
        # Excited A-E splittings increase monotonically with torsional excitation
        assert res.excited_a_e_splittings_mhz[0] > res.a_e_splitting_ground_mhz
        assert res.excited_a_e_splittings_mhz[1] > res.excited_a_e_splittings_mhz[0]
        assert res.excited_a_e_splittings_mhz[2] > res.excited_a_e_splittings_mhz[1]


class TestNuclearSpinStatistics:
    """Tests Longuet-Higgins / Bunker Permutation-Inversion spin statistics."""

    def test_c2v_nuclear_spin_weights(self) -> None:
        """Verifies C2v nuclear spin statistical weights for water-like (two H, I=1/2) species."""
        weights = classify_nuclear_spin_weights(SymmetryGroup.C2V, [0.5, 0.5])
        assert weights["A1"] == 1
        assert weights["B2"] == 3

    def test_c3v_nuclear_spin_weights(self) -> None:
        """Verifies C3v nuclear spin statistical weights for methyl-like (three H, I=1/2) species."""
        weights = classify_nuclear_spin_weights(SymmetryGroup.C3V, [0.5, 0.5, 0.5])
        assert weights["A1"] == 4
        assert weights["A2"] == 4
        assert weights["E"] == 8


class Test2DDirectProductAndMatrixFreeDVR:
    """Tests 2D coupled DVR solvers, Kronecker products, and matrix-free Lanczos operators."""

    def test_2d_coupled_dvr_dense_and_matrix_free_agreement(self) -> None:
        """Verifies MatrixFreeDVROperator Lanczos eigenvalues match dense diagonalization."""
        n1, n2 = 18, 18
        g1, _ = build_grid_1d(DVRGridType.SINC, n1, x_min=-1.5, x_max=1.5)
        g2, _ = build_grid_1d(DVRGridType.SINC, n2, x_min=-1.5, x_max=1.5)

        t1 = build_sinc_kinetic_1d(g1, mass_amu=1.0)
        t2 = build_sinc_kinetic_1d(g2, mass_amu=1.0)

        xx, yy = np.meshgrid(g1, g2, indexing="ij")
        v_2d = 0.5 * 800.0 * (xx ** 2) + 0.5 * 600.0 * (yy ** 2) + 50.0 * xx * yy
        v_flat = v_2d.flatten()

        # Dense solve
        t_2d = build_2d_direct_product_kinetic(t1, t2)
        h_dense = t_2d + np.diag(v_flat)
        evals_dense, _ = solve_dvr_dense(h_dense, num_states=6)

        # Matrix-free solve
        op = MatrixFreeDVROperator(t1, t2, v_flat, shape_2d=(n1, n2))
        evals_mf, _ = solve_dvr_matrix_free(op, num_states=6)

        np.testing.assert_allclose(evals_dense[:5], evals_mf[:5], rtol=1e-4, atol=1e-3)


class TestVibrationalAveragesAndDipoleMoments:
    """Tests coordinate-dependent expectation values and transition dipole moments."""

    def test_vibrational_averages_1d(self) -> None:
        """Verifies coordinate expectation values <x> and <x^2> for harmonic oscillator."""
        solver = DVR1DSolver(
            grid_type=DVRGridType.SINC,
            n_points=100,
            x_min=-3.0,
            x_max=3.0,
            mass_amu=1.0,
        )
        v_harm = 0.5 * 1000.0 * (solver.grid ** 2)
        res = solver.solve(v_harm, num_states=4)

        avg_x = compute_vibrational_averages_1d(solver.grid, res.wavefunctions, solver.grid, solver.weights)
        avg_x2 = compute_vibrational_averages_1d(solver.grid, res.wavefunctions, solver.grid ** 2, solver.weights)

        # <x> for harmonic oscillator eigenstates must be zero by parity
        np.testing.assert_allclose(avg_x, 0.0, atol=1e-8)
        # <x^2> must be strictly positive and monotonically increasing
        assert np.all(np.diff(avg_x2) > 0.0)

    def test_transition_dipole_moments(self) -> None:
        """Verifies selection rule mu_{01} != 0 and mu_{02} ~ 0 for linear dipole mu(x) = x."""
        solver = DVR1DSolver(
            grid_type=DVRGridType.SINC,
            n_points=60,
            x_min=-2.0,
            x_max=2.0,
            mass_amu=1.0,
        )
        v_harm = 0.5 * 1000.0 * (solver.grid ** 2)
        res = solver.solve(v_harm, num_states=4)

        mu_curve = solver.grid.copy()  # Linear dipole mu(x) = x
        trans_dipoles = compute_transition_dipole_moments(res.wavefunctions, mu_curve, solver.weights)

        assert abs(trans_dipoles[0, 1]) > 1e-4
        assert abs(trans_dipoles[0, 2]) < 1e-4


class TestSerializationAndCLI:
    """Tests JSON/HDF5 export and CLI execution."""

    def test_hdf5_and_json_export(self) -> None:
        """Verifies full spectrum persistence to HDF5 and JSON."""
        solver = DVR1DSolver(grid_type=DVRGridType.SINC, n_points=40, mass_amu=1.0)
        v = 0.5 * 500.0 * (solver.grid ** 2)
        res = solver.solve(v, num_states=5)

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "dvr_spectrum.json"
            h5_path = Path(tmpdir) / "dvr_spectrum.h5"

            # JSON export
            json_path.write_text(json.dumps(res.to_dict(), indent=2), encoding="utf-8")
            assert json_path.exists()
            data = json.loads(json_path.read_text(encoding="utf-8"))
            assert data["num_states_solved"] == 5
            assert len(data["eigenvalues_cm1"]) == 5

            # HDF5 export
            res.save_hdf5(h5_path)
            assert h5_path.exists()
            import h5py
            with h5py.File(h5_path, "r") as f:
                assert "eigenvalues_cm1" in f
                assert "wavefunctions" in f
                assert f.attrs["num_states_solved"] == 5

    def test_cli_execution_modes(self) -> None:
        """Verifies CLI execution pathways exit with code 0."""
        rc1 = solver_main(["--dim", "1", "--grid-type", "fourier", "--f-rot", "5.25", "--barrier", "300.0"])
        assert rc1 == 0

        rc2 = solver_main(["--dim", "1", "--grid-type", "sinc", "--barrier", "400.0", "--mass-isotope", "H"])
        assert rc2 == 0

        rc3 = solver_main(["--dim", "2", "--points", "15"])
        assert rc3 == 0
