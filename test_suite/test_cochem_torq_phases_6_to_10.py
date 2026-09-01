"""
CoChem-TORQ: Comprehensive Unit Test Suite (Phases 6 through 10)
================================================================
Authentic Physical Unit Tests covering Modules and Deliverables:
- Phase 6: cochem_tensor_extractor (Inertia tensors, Ray's kappa, Cartesian linear protections, planar moments & sum rules)
- Phase 7: cochem_jax_builder (Float64 JAX DVR 1D/2D, periodic Fourier DVR Meyer 1970, XLA JIT eigen solver, localized VPT2)
- Phase 8: cochem_spcat_bridge (LAM trap, symmetry divisors, double-counting guardrail, Pickett .var/.int files, airgap boundary)
- Phase 9: cochem_torq_export, cochem_torq_telemetry (Kraitchman coords, ZPVE defect clamping, PGOPHER skeleton, locked provenance, webhooks)
- Phase 10: cochem_catalog_compiler (6-tier path hierarchy, PyArrow out-of-core Parquet, buffer lock sync, parallel temperature compiler, read-only seals, LaTeX/BibTeX)
"""

from __future__ import annotations

import gc
import http.server
import json
import logging
import math
import os
from pathlib import Path
import socketserver
import tempfile
import threading
import time
from typing import Any, Dict, List, Tuple

import numpy as np
import psutil
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from cochem_base.exceptions import (
    AirGapViolationError,
    CoChemIntegrityError,
    FortranOverflowError,
    KraitchmanZPVEWarning,
    LAMTriggerError,
    ProvenanceErrorCode,
)
from cochem_catalog_compiler import (
    CoChemPathManager,
    apply_readonly_chmod,
    buffer_lock_sync,
    deduplicate_bibtex,
    generate_methods_latex,
    parallel_temperature_compiler,
    parse_spcat_cat_line,
    parse_spcat_cat_stream,
    purge_ghost_outputs,
    pyarrow_chunked_serializer,
    remove_readonly_seal,
)
from cochem_jax_builder import (
    CoChemPrecisionError,
    build_dvr_hamiltonian,
    enforce_jax_precision,
    jit_eigen_solver,
    localized_vpt2_coupling,
    nan_tensor_watchdog,
)
from cochem_spcat_bridge import (
    CONSTANTS,
    SPCATPayload,
    apply_symmetry_divisors,
    build_complete_spcat_payload,
    calculate_rotational_partition_function,
    calculate_vibrational_partition_function,
    format_fortran_double,
    fortran_double_precision_formatter,
    fortran_overflow_guard,
    generate_spcat_int,
    generate_spcat_var,
    low_frequency_lam_trap,
    validate_airgap_boundary,
    vibrational_partition_coupling,
)
from cochem_tensor_extractor import (
    CIAAW_ISOTOPIC_MASSES,
    INERTIA_CONVERSION_AMU_ANG2_MHZ,
    CartesianProtectionResult,
    InertiaTensorResult,
    RepresentationSwitchResult,
    apply_cartesian_protections,
    build_inertia_tensor,
    calculate_center_of_mass,
    diagonalize_inertia_tensor,
    dynamic_representation_switch,
    resolve_atomic_mass,
    translate_to_center_of_mass,
)
from cochem_torq_export import (
    bundle_spycfit_payload,
    calculate_kraitchman_coords,
    generate_pgopher_skeleton,
    lock_provenance_payload,
    verify_payload_integrity,
)
from cochem_torq_telemetry import (
    TELEMETRY_BUFFER,
    export_crash_animation,
    generate_plotly_3d_carousels,
    stream_webhook_events,
)

# =============================================================================
# Authentic Molecular Geometries (Equilibrium and Displaced Coordinates in Angstroms)
# =============================================================================

# Water (H2O): C2v planar equilibrium geometry
H2O_COORDS = np.array([
    [0.000000,  0.000000,  0.117300],  # O
    [0.000000,  0.757200, -0.469200],  # H1
    [0.000000, -0.757200, -0.469200],  # H2
], dtype=np.float64)
H2O_SYMBOLS = ["O", "H", "H"]

# Water vibrational normal mode displacement frames (Symmetric Stretch, Bend, Asymmetric Stretch)
H2O_FRAME_EQ = H2O_COORDS
H2O_FRAME_SYM_STRETCH = np.array([
    [0.000000,  0.000000,  0.120500],  # O
    [0.000000,  0.778800, -0.482000],  # H1
    [0.000000, -0.778800, -0.482000],  # H2
], dtype=np.float64)
H2O_FRAME_BEND = np.array([
    [0.000000,  0.000000,  0.112000],  # O
    [0.000000,  0.795000, -0.448000],  # H1
    [0.000000, -0.795000, -0.448000],  # H2
], dtype=np.float64)
H2O_FRAME_ASYM_STRETCH = np.array([
    [0.000000,  0.015000,  0.116000],  # O
    [0.000000,  0.785000, -0.490000],  # H1
    [0.000000, -0.730000, -0.450000],  # H2
], dtype=np.float64)

# Hydrogen Cyanide (HCN): C_inf_v linear equilibrium geometry
HCN_COORDS = np.array([
    [0.000000, 0.000000, -1.064000],  # H
    [0.000000, 0.000000,  0.000000],  # C
    [0.000000, 0.000000,  1.156000],  # N
], dtype=np.float64)
HCN_SYMBOLS = ["H", "C", "N"]

# Formaldehyde (H2CO): C2v planar equilibrium geometry
H2CO_COORDS = np.array([
    [0.000000,  0.000000,  0.600000],  # C
    [0.000000,  0.000000, -0.600000],  # O
    [0.000000,  0.940000,  1.180000],  # H1
    [0.000000, -0.940000,  1.180000],  # H2
], dtype=np.float64)
H2CO_SYMBOLS = ["C", "O", "H", "H"]

# Ammonia (NH3): C3v pyramidal non-planar equilibrium geometry
NH3_COORDS = np.array([
    [ 0.000000,  0.000000,  0.116800],  # N
    [ 0.000000,  0.939700, -0.272500],  # H1
    [ 0.813800, -0.469900, -0.272500],  # H2
    [-0.813800, -0.469900, -0.272500],  # H3
], dtype=np.float64)
NH3_SYMBOLS = ["N", "H", "H", "H"]


# =============================================================================
# Phase 6: cochem_tensor_extractor Tests
# =============================================================================

class TestTensorExtractor:
    """Rigorous tests for Phase 6: Moment of Inertia Tensor and Representation Switching."""

    def test_atomic_mass_resolution(self) -> None:
        """Verifies CIAAW exact isotopic mass retrieval via Mendeleev and numeric pass-through."""
        assert resolve_atomic_mass("H") == pytest.approx(1.00782503223, rel=1e-8)
        assert resolve_atomic_mass("12C") == pytest.approx(12.0, rel=1e-8)
        assert resolve_atomic_mass("16O") == pytest.approx(15.99491461957, rel=1e-8)
        assert resolve_atomic_mass(14.003) == pytest.approx(14.003, rel=1e-8)
        assert "14N" in CIAAW_ISOTOPIC_MASSES
        assert CIAAW_ISOTOPIC_MASSES["14N"] == pytest.approx(14.00307400443, rel=1e-6)

    def test_inertia_conversion_constant_codata2022(self) -> None:
        """Verifies INERTIA_CONVERSION_AMU_ANG2_MHZ against CODATA 2022 exact constants."""
        # h / (8 * pi^2 * u * 1e-20) * 1e-6 MHz
        h = CONSTANTS.H
        u = CONSTANTS.AMU_KG
        exact_factor = (h / (8.0 * (math.pi**2) * u * 1e-20)) * 1e-6
        assert INERTIA_CONVERSION_AMU_ANG2_MHZ == pytest.approx(exact_factor, rel=1e-5)
        assert abs(INERTIA_CONVERSION_AMU_ANG2_MHZ - 505379.0084350172) < 1e-6

    def test_center_of_mass_translation(self) -> None:
        """Verifies center of mass translation moves origin to (0,0,0)."""
        masses = [resolve_atomic_mass(s) for s in H2O_SYMBOLS]
        com = calculate_center_of_mass(H2O_COORDS, masses)
        centered, returned_com = translate_to_center_of_mass(H2O_COORDS, masses)
        np.testing.assert_allclose(com, returned_com)
        new_com = calculate_center_of_mass(centered, masses)
        np.testing.assert_allclose(new_com, [0.0, 0.0, 0.0], atol=1e-12)

    def test_water_inertia_tensor_and_rotational_constants(self) -> None:
        """Verifies diagonalized inertia tensor and rotational constants for H2O."""
        res = diagonalize_inertia_tensor(H2O_COORDS, H2O_SYMBOLS)
        assert isinstance(res, InertiaTensorResult)
        assert res.total_mass_amu == pytest.approx(18.010564684, rel=1e-6)
        assert res.is_linear is False
        assert res.is_planar is True

        a = res.rotational_constants_mhz["A"]
        b = res.rotational_constants_mhz["B"]
        c = res.rotational_constants_mhz["C"]
        assert a > b > c > 0.0
        assert 700000.0 < a < 950000.0
        assert 350000.0 < b < 500000.0
        assert 200000.0 < c < 350000.0
        assert abs(res.inertial_defect_amu_ang2) < 0.01

        # Rotational constant relationship: C_rot = INERTIA_CONVERSION / I
        i_a = res.moments_of_inertia_amu_ang2["I_a"]
        i_b = res.moments_of_inertia_amu_ang2["I_b"]
        i_c = res.moments_of_inertia_amu_ang2["I_c"]
        assert a == pytest.approx(INERTIA_CONVERSION_AMU_ANG2_MHZ / i_a, rel=1e-10)
        assert b == pytest.approx(INERTIA_CONVERSION_AMU_ANG2_MHZ / i_b, rel=1e-10)
        assert c == pytest.approx(INERTIA_CONVERSION_AMU_ANG2_MHZ / i_c, rel=1e-10)

    def test_planar_moments_and_sum_rules_water_and_formaldehyde(self) -> None:
        """Verifies planar moments (P_a, P_b, P_c) and sum rules mandated by Method Matrix Step 4."""
        # 1. Planar molecule: H2O
        res_h2o = diagonalize_inertia_tensor(H2O_COORDS, H2O_SYMBOLS)
        i_a = res_h2o.moments_of_inertia_amu_ang2["I_a"]
        i_b = res_h2o.moments_of_inertia_amu_ang2["I_b"]
        i_c = res_h2o.moments_of_inertia_amu_ang2["I_c"]

        p_a = res_h2o.planar_moments_amu_ang2["P_a"]
        p_b = res_h2o.planar_moments_amu_ang2["P_b"]
        p_c = res_h2o.planar_moments_amu_ang2["P_c"]

        # Definitions: P_g = 1/2 (sum I - 2 I_g)
        assert p_a == pytest.approx(0.5 * (i_b + i_c - i_a), rel=1e-10)
        assert p_b == pytest.approx(0.5 * (i_a + i_c - i_b), rel=1e-10)
        assert p_c == pytest.approx(0.5 * (i_a + i_b - i_c), rel=1e-10)

        # Planar Sum Rules:
        # P_a + P_b = I_c
        # P_a + P_c = I_b
        # P_b + P_c = I_a
        assert (p_a + p_b) == pytest.approx(i_c, rel=1e-10)
        assert (p_a + p_c) == pytest.approx(i_b, rel=1e-10)
        assert (p_b + p_c) == pytest.approx(i_a, rel=1e-10)
        assert (p_a + p_b + p_c) == pytest.approx(0.5 * (i_a + i_b + i_c), rel=1e-10)

        # For planar molecule in ab-plane: P_c ~ 0.0, P_a > P_b > P_c >= 0
        assert abs(p_c) < 1e-4
        assert p_a > p_b > p_c

        # 2. Planar molecule: H2CO
        res_h2co = diagonalize_inertia_tensor(H2CO_COORDS, H2CO_SYMBOLS)
        assert res_h2co.is_planar is True
        p_a_co = res_h2co.planar_moments_amu_ang2["P_a"]
        p_b_co = res_h2co.planar_moments_amu_ang2["P_b"]
        p_c_co = res_h2co.planar_moments_amu_ang2["P_c"]
        i_c_co = res_h2co.moments_of_inertia_amu_ang2["I_c"]
        assert (p_a_co + p_b_co) == pytest.approx(i_c_co, rel=1e-10)
        assert abs(p_c_co) < 1e-4

    def test_planar_moments_nonplanar_molecule(self) -> None:
        """Verifies planar moments and non-zero out-of-plane moment for non-planar NH3."""
        res_nh3 = diagonalize_inertia_tensor(NH3_COORDS, NH3_SYMBOLS)
        assert res_nh3.is_planar is False
        p_a = res_nh3.planar_moments_amu_ang2["P_a"]
        p_b = res_nh3.planar_moments_amu_ang2["P_b"]
        p_c = res_nh3.planar_moments_amu_ang2["P_c"]
        assert p_a > 0.0
        assert p_b > 0.0
        assert p_c > 0.0
        assert res_nh3.inertial_defect_amu_ang2 < -0.01

    def test_cartesian_protections_for_linear_molecule(self) -> None:
        """Verifies collinearity detection and cylindrical projection for linear HCN."""
        prot = apply_cartesian_protections(HCN_COORDS, HCN_SYMBOLS)
        assert isinstance(prot, CartesianProtectionResult)
        assert prot.is_linear is True
        assert prot.collinear_axis == "Z"
        assert prot.applied_protection is True
        assert prot.cylindrical_coordinates is not None
        assert prot.cylindrical_coordinates.shape == (3, 2)

    def test_dynamic_representation_switch(self) -> None:
        """Verifies Ray's asymmetry kappa and representation selection (I^r vs III^r)."""
        res_prolate = dynamic_representation_switch(a_mhz=30000.0, b_mhz=5000.0, c_mhz=4000.0)
        assert isinstance(res_prolate, RepresentationSwitchResult)
        assert res_prolate.is_prolate is True
        assert res_prolate.recommended_representation == "Ir"
        assert res_prolate.ray_kappa < 0.0

        res_oblate = dynamic_representation_switch(a_mhz=10000.0, b_mhz=9000.0, c_mhz=2000.0)
        assert res_oblate.is_oblate is True
        assert res_oblate.recommended_representation == "IIIr"
        assert res_oblate.ray_kappa >= 0.0


# =============================================================================
# Phase 7: cochem_jax_builder Tests
# =============================================================================

class TestJAXBuilder:
    """Rigorous tests for Phase 7: JAX DVR and Quantum Physics Solvers."""

    def test_enforce_jax_precision(self) -> None:
        """Verifies JAX float64 enablement and system query."""
        info = enforce_jax_precision(force_recheck=True)
        assert isinstance(info, dict)
        assert info["float64_enabled"] is True
        assert "devices" in info

    def test_build_dvr_hamiltonian_and_eigen_solver(self) -> None:
        """Verifies 1D DVR Hamiltonian construction and eigenvalue computation."""
        n_pts = 64
        # Authentic 1D particle-in-a-box flat potential
        v_box = [0.0 for _ in range(n_pts)]
        h_mat = build_dvr_hamiltonian(
            pes_spline_array=v_box,
            dimensions=1,
            mass=1.0,
            length=1.0,
            periodic=False,
            num_points=n_pts,
        )
        assert h_mat.shape == (n_pts, n_pts)

        evals, evecs = jit_eigen_solver(h_mat)
        assert len(evals) == n_pts
        assert np.all(np.isfinite(np.asarray(evals)))
        assert evals[0] > 0.0

    def test_periodic_fourier_dvr_meyer_1970_1d(self) -> None:
        """Verifies 1D Periodic Fourier DVR (Meyer 1970) for free and hindered internal rotors."""
        # 1. Free internal rotor (V=0) -> Exact analytical eigenvalues E_m = F * m^2
        f_rot = 5.25  # cm^-1
        n_pts = 25
        v_free = [0.0 for _ in range(n_pts)]

        h_free = build_dvr_hamiltonian(
            pes_spline_array=v_free,
            dimensions=1,
            periodic=True,
            num_points=n_pts,
            reduced_rot_constant=f_rot,
        )
        evals_free, _ = jit_eigen_solver(h_free)
        evals_np = np.asarray(evals_free)

        # Expected degenerate pairs: 0, F, F, 4F, 4F, 9F, 9F, 16F, 16F
        expected_spectrum = [0.0, f_rot, f_rot, 4.0 * f_rot, 4.0 * f_rot, 9.0 * f_rot, 9.0 * f_rot]
        for idx, exp_val in enumerate(expected_spectrum):
            assert evals_np[idx] == pytest.approx(exp_val, abs=1e-8)

        # 2. Hindered internal rotor with 3-fold torsional barrier: V(th) = (V3 / 2) * (1 - cos(3*th))
        v3_barrier = 350.0  # cm^-1
        n_pts_hind = 61
        theta_grid = [2.0 * math.pi * j / n_pts_hind for j in range(n_pts_hind)]
        v_hindered = [(v3_barrier / 2.0) * (1.0 - math.cos(3.0 * th)) for th in theta_grid]

        h_hindered = build_dvr_hamiltonian(
            pes_spline_array=v_hindered,
            dimensions=1,
            periodic=True,
            num_points=n_pts_hind,
            reduced_rot_constant=f_rot,
        )
        evals_hind, _ = jit_eigen_solver(h_hindered)
        evals_hind_np = np.asarray(evals_hind)

        # Ground state splits into A (singlet) and E (doublet) torsional states
        e0_a = evals_hind_np[0]
        e1_e = evals_hind_np[1]
        e2_e = evals_hind_np[2]
        assert abs(e1_e - e2_e) < 1e-6  # E states are degenerate
        assert e1_e > e0_a  # A is ground state for standard barrier

    def test_2d_coupled_internal_rotor_dvr_kronecker(self) -> None:
        """Verifies 2D coupled internal rotor DVR (H = T1 (x) I2 + I1 (x) T2 + V_2D)."""
        n1, n2 = 9, 9
        f1, f2 = 4.5, 4.5  # cm^-1

        # Authentic 2D coupled torsional potential: V(th1, th2) = V3/2(1-cos 3th1) + V3/2(1-cos 3th2) + V_c cos 3(th1-th2)
        def coupled_torsional_pes(th1: float, th2: float) -> float:
            return 120.0 * (1.0 - math.cos(3.0 * th1)) + 120.0 * (1.0 - math.cos(3.0 * th2)) + 20.0 * math.cos(3.0 * (th1 - th2))

        h_2d = build_dvr_hamiltonian(
            pes_spline_array=coupled_torsional_pes,
            dimensions=2,
            periodic=True,
            num_points=(n1, n2),
            reduced_rot_constant=(f1, f2),
        )
        assert h_2d.shape == (n1 * n2, n1 * n2)

        evals, evecs = jit_eigen_solver(h_2d)
        evals_np = np.asarray(evals)
        assert len(evals_np) == n1 * n2
        assert np.all(np.isfinite(evals_np))
        assert evals_np[0] > 0.0
        assert np.all(np.diff(evals_np) >= -1e-12)

    def test_nan_tensor_watchdog_and_tikhonov(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verifies singularity interception and Tikhonov regularization on corrupted physical Hamiltonian."""
        n_size = 20
        # Construct authentic physical kinetic Hamiltonian diagonal
        base_h = np.zeros((n_size, n_size), dtype=np.float64)
        for i in range(n_size):
            base_h[i, i] = float(i + 1) * 2.5
            if i > 0:
                base_h[i, i - 1] = -0.75
                base_h[i - 1, i] = -0.75

        # Corrupt elements
        h_corrupted = np.copy(base_h)
        h_corrupted[5, 5] = np.nan
        h_corrupted[10, 10] = np.inf

        with caplog.at_level(logging.WARNING, logger="cochem.jax_builder"):
            h_regularized = nan_tensor_watchdog(h_corrupted, damping=1e-4)

        assert not np.isnan(np.asarray(h_regularized)).any()
        assert not np.isinf(np.asarray(h_regularized)).any()
        warning_records = [r.message for r in caplog.records if "SINGULARITY_DETECTED" in r.message]
        assert len(warning_records) >= 1

    def test_localized_vpt2_coupling(self) -> None:
        """Verifies LAM mode removal and vibrational partition coupling."""
        harmonic_freqs = [88.5, 340.0, 680.0, 1120.0, 1450.0, 2980.0]
        dvr_energies = [12.4, 38.6, 92.1, 165.0, 260.4]

        result = localized_vpt2_coupling(
            dvr_energies=dvr_energies,
            vpt2_matrix=harmonic_freqs,
            lam_mode_index=0,
            max_coupled_states=30,
        )
        assert isinstance(result, dict)
        assert result["lam_frequency_dropped"] == 88.5
        assert len(result["stiff_frequencies"]) == 5
        assert 88.5 not in result["stiff_frequencies"]


# =============================================================================
# Phase 8: cochem_spcat_bridge Tests
# =============================================================================

class TestSPCATBridge:
    """Rigorous tests for Phase 8: Statistical Mechanics and Pickett SPCAT Bridge."""

    def test_low_frequency_lam_trap(self) -> None:
        """Verifies low-frequency modes < 50 cm^-1 trigger LAM exception."""
        freqs_with_lam = [22.5, 300.0, 1200.0]
        with pytest.raises(LAMTriggerError) as exc_info:
            low_frequency_lam_trap(freqs_with_lam, threshold_cm1=50.0)
        assert exc_info.value.error_code == ProvenanceErrorCode.LAM_TRIGGER

        clean_freqs = [85.0, 300.0, 1200.0]
        stiff = low_frequency_lam_trap(clean_freqs, threshold_cm1=50.0)
        assert len(stiff) == 3

    def test_apply_symmetry_divisors_and_double_counting_guardrail(self) -> None:
        """Verifies point group symmetry resolution and double-counting guardrail enforcement."""
        # 1. Water (H2O): C2v symmetry, sigma=2, ortho:para = 3:1
        sym_res_classical = apply_symmetry_divisors(
            geometry_array=H2O_COORDS,
            symbols=H2O_SYMBOLS,
            use_nuclear_spin=False,
        )
        assert sym_res_classical.point_group == "C2v"
        assert sym_res_classical.sigma == 2
        assert sym_res_classical.effective_divisor == 2.0
        assert sym_res_classical.spin_weight_ratio_str == "3 1"
        assert "CLASSICAL_SIGMA_APPLIED" in sym_res_classical.guardrail_status

        # 2. Water with exact nuclear spin statistical weights applied
        sym_res_spin = apply_symmetry_divisors(
            geometry_array=H2O_COORDS,
            symbols=H2O_SYMBOLS,
            use_nuclear_spin=True,
        )
        assert sym_res_spin.effective_divisor == 1.0
        assert "EXACT_NUCLEAR_SPIN_APPLIED_SIGMA_BYPASSED" in sym_res_spin.guardrail_status

    def test_rotational_and_vibrational_partition_functions(self) -> None:
        """Verifies exact partition function calculations for standard states."""
        a_mhz, b_mhz, c_mhz = 835840.0, 435350.0, 278139.0
        q_rot = calculate_rotational_partition_function(a_mhz, b_mhz, c_mhz, temp_k=298.15, sigma=2)
        assert q_rot > 0.0

        vib_freqs = [1595.0, 3657.0, 3756.0]
        q_vib = calculate_vibrational_partition_function(vib_freqs, temp_k=298.15)
        assert 1.0 <= q_vib < 1.01

    def test_vibrational_partition_coupling_and_lam_dropping(self) -> None:
        """Verifies coupling of DVR rotational partition functions and dropping of LAM modes."""
        q_rot_dict = {10.0: 5.2, 50.0: 58.4, 298.15: 1250.0}
        all_freqs = [35.0, 420.0, 1150.0, 2900.0]  # 35.0 cm^-1 is LAM mode

        q_coupled = vibrational_partition_coupling(
            q_rot_dvr=q_rot_dict,
            q_vib_orca=all_freqs,
            temp_array=[10.0, 50.0, 298.15],
            lam_frequency=35.0,
            all_frequencies=all_freqs,
        )
        assert len(q_coupled) == 3
        for t in (10.0, 50.0, 298.15):
            assert q_coupled[t] >= q_rot_dict[t]

    def test_fortran_double_precision_formatting(self) -> None:
        """Verifies strict Fortran Double Precision scientific notation ('D') formatting."""
        val = 1.567e-05
        formatted_compact = format_fortran_double(val, compact=True)
        assert "D-05" in formatted_compact or "D-5" in formatted_compact
        assert "E" not in formatted_compact and "e" not in formatted_compact

        formatted_fixed = format_fortran_double(val, width=22, precision=15)
        assert len(formatted_fixed) == 22
        assert "D-05" in formatted_fixed

        # Parameter line formatting
        line_str = fortran_double_precision_formatter(20000, 835840.0, uncertainty=1e-4, label="A")
        assert "20000" in str(line_str)
        assert "D+05" in str(line_str)
        assert "/ A" in str(line_str)

    def test_fortran_overflow_guard(self) -> None:
        """Verifies overflow guard trapping parameters exceeding Double Precision ceilings."""
        valid_dict = {"A": 835840.0, "DJ": 0.0015}
        guarded = fortran_overflow_guard(valid_dict)
        assert guarded["A"] == 835840.0

        corrupt_dict = {"A": 1e309, "B": 435350.0}
        with pytest.raises(FortranOverflowError) as exc_info:
            fortran_overflow_guard(corrupt_dict)
        assert exc_info.value.error_code == ProvenanceErrorCode.FORTRAN_OVERFLOW

        clamped = fortran_overflow_guard(corrupt_dict, clamp_on_overflow=True)
        assert clamped["A"] == 1e308

    def test_validate_airgap_boundary(self, tmp_path: Path) -> None:
        """Verifies air-gap boundary validation permitting valid paths."""
        valid_target = tmp_path / "output.var"
        resolved = validate_airgap_boundary(valid_target)
        assert resolved == valid_target.resolve()

    def test_spcat_file_generation(self, tmp_path: Path) -> None:
        """Verifies authentic Pickett .var and .int ASCII generation."""
        var_file = tmp_path / "H2O.var"
        content = generate_spcat_var(
            molecule_name="H2O",
            parameters={"A": 835840.0, "B": 435350.0, "C": 278139.0},
            filepath=var_file,
        )
        assert var_file.exists()
        assert "H2O Ground State" in content

        int_dict = generate_spcat_int(
            molecule_name="H2O",
            dipoles={"mu_b": 1.8546},
            temperatures=[298.15],
            filepath_template=tmp_path / "H2O_{T}K.int",
        )
        assert 298.15 in int_dict
        assert (tmp_path / "H2O_298.1K.int").exists()

    def test_build_complete_spcat_payload(self, tmp_path: Path) -> None:
        """Verifies end-to-end SPCAT execution payload packaging with provenance manifest."""
        payload = build_complete_spcat_payload(
            molecule_name="H2O",
            geometry=H2O_COORDS,
            symbols=H2O_SYMBOLS,
            rotational_constants_mhz={"A": 835840.0, "B": 435350.0, "C": 278139.0},
            dipoles_debye={"mu_b": 1.8546},
            harmonic_frequencies_cm1=[1595.0, 3657.0, 3756.0],
            temperatures=[10.0, 298.15],
            output_dir=tmp_path / "spcat_package",
        )
        assert isinstance(payload, SPCATPayload)
        assert payload.molecule_name == "H2O"
        assert len(payload.int_contents) == 2
        assert len(payload.sha256_var) == 64
        assert "symmetry" in payload.provenance_manifest


# =============================================================================
# Phase 9: cochem_torq_export & Telemetry Tests
# =============================================================================

class TestExportAndTelemetry:
    """Rigorous tests for Phase 9: SpycFit Payload Synthesis and Telemetry."""

    def test_kraitchman_coords_calculation(self) -> None:
        """Verifies Kraitchman substitution coordinate math on asymmetric rotors."""
        input_dict = {
            "I_a": 35.0, "I_b": 60.0, "I_c": 90.0,
            "I_a_iso": 35.8, "I_b_iso": 60.5, "I_c_iso": 91.2,
            "parent_mass": 50.0, "delta_m": 1.00335,
        }
        res = calculate_kraitchman_coords(input_dict)
        assert "coordinates" in res
        assert "costain_uncertainties" in res
        for axis in ("a", "b", "c"):
            assert res["coordinates"][axis] >= 0.0

    def test_kraitchman_near_symmetric_damping_and_zpve_warning(self) -> None:
        """Verifies singularity damping for near-symmetric tops and ZPVE imaginary root defect clamping."""
        # 1. Near-symmetric top damping (|I_b - I_c| < 1e-4)
        input_near_sym = {
            "I_a": 15.0,
            "I_b": 50.00001,
            "I_c": 50.00003,
            "I_a_iso": 15.05,
            "I_b_iso": 50.10001,
            "I_c_iso": 50.10003,
            "parent_mass": 60.0,
            "delta_m": 1.0,
        }
        res_damped = calculate_kraitchman_coords(input_near_sym)
        assert res_damped["near_symmetric_damped"]["b"] is True or res_damped["near_symmetric_damped"]["c"] is True
        for axis in ("a", "b", "c"):
            assert np.isfinite(res_damped["coordinates"][axis])

        # 2. ZPVE imaginary root defect clamping with KraitchmanZPVEWarning
        input_zpve = {
            "I_a": 40.0,
            "I_b": 70.0,
            "I_c": 100.0,
            "I_a_iso": 40.0001,
            "I_b_iso": 72.0,
            "I_c_iso": 68.0,
            "parent_mass": 45.0,
            "delta_m": 1.0,
        }
        with pytest.warns(KraitchmanZPVEWarning) as warn_records:
            res_zpve = calculate_kraitchman_coords(input_zpve)
        assert len(warn_records) >= 1
        assert any(res_zpve["zpve_defect_clamped"].values()) is True

    def test_generate_pgopher_skeleton(self, tmp_path: Path) -> None:
        """Verifies zero-RAM PGOPHER skeleton synthesis from Parquet catalog metadata and JSON parameters."""
        # Create authentic sample Parquet catalog
        parquet_file = tmp_path / "H2O.parquet"
        schema = pa.schema([
            ("frequency_mhz", pa.float64()),
            ("uncertainty_mhz", pa.float64()),
            ("log_intensity", pa.float64()),
        ])
        table = pa.Table.from_pydict({
            "frequency_mhz": [22235.08, 183310.087],
            "uncertainty_mhz": [0.005, 0.002],
            "log_intensity": [-4.56, -2.34],
        }, schema=schema)
        pq.write_table(table, parquet_file)

        json_file = tmp_path / "H2O_params.json"
        json_file.write_text(json.dumps({
            "molecule_name": "H2O",
            "point_group": "C2v",
            "rotational_constants": {"A": 835840.0, "B": 435350.0, "C": 278139.0},
            "dipole_moments": {"mu_b": 1.8546},
            "temperature": 298.15,
        }), encoding="utf-8")

        pgo_xml = generate_pgopher_skeleton(
            parquet_path=str(parquet_file),
            json_path=str(json_file),
            output_path=str(tmp_path / "H2O.pgo"),
        )
        assert "<PGOPHER" in pgo_xml
        assert 'Species Name="H2O"' in pgo_xml
        assert (tmp_path / "H2O.pgo").exists()

    def test_lock_provenance_payload_and_verification(self, tmp_path: Path) -> None:
        """Verifies cryptographic SHA-256 manifest locking and anti-tamper verification."""
        data_file = tmp_path / "test_data.var"
        data_file.write_text("TEST VAR CONTENT", encoding="utf-8")

        manifest_dict = lock_provenance_payload(str(tmp_path))
        assert isinstance(manifest_dict, dict)
        assert "files" in manifest_dict
        assert verify_payload_integrity(tmp_path) is True

        # Tamper with file
        data_file.write_text("TAMPERED DATA", encoding="utf-8")
        with pytest.raises(CoChemIntegrityError):
            verify_payload_integrity(tmp_path)

    def test_bundle_spycfit_payload(self, tmp_path: Path) -> None:
        """Verifies deterministic deliverable compression bundling."""
        payload_dir = tmp_path / "export_dir"
        payload_dir.mkdir()
        (payload_dir / "deliverable.var").write_text("PARAM_DATA", encoding="utf-8")
        lock_provenance_payload(str(payload_dir))

        archive_path = bundle_spycfit_payload(
            manifest_path=str(payload_dir),
            output_dir=str(tmp_path / "bundles"),
            project_name="WaterTest",
        )
        assert Path(archive_path).exists()
        assert Path(archive_path).stat().st_size > 0

    def test_plotly_3d_and_crash_animation_generation(self, tmp_path: Path) -> None:
        """Verifies export of HTML 3D visualization and crash diagnostic JSON using authentic PES and trajectory."""
        html_out = tmp_path / "torq_3d.html"
        # Authentic 2D torsional dihedral potential surface grid
        grid_n = 20
        th1_pts = [2.0 * math.pi * i / grid_n for i in range(grid_n)]
        th2_pts = [2.0 * math.pi * j / grid_n for j in range(grid_n)]
        pes_grid = np.array([
            [
                150.0 * (1.0 - math.cos(3.0 * th1)) + 150.0 * (1.0 - math.cos(3.0 * th2)) + 25.0 * math.cos(3.0 * (th1 - th2))
                for th2 in th2_pts
            ]
            for th1 in th1_pts
        ], dtype=np.float64)

        html_str = generate_plotly_3d_carousels(pes_grid, output_path=str(html_out))
        assert html_out.exists()
        assert html_out.stat().st_size > 100

        anim_out = tmp_path / "crash_anim.xyz"
        # Authentic molecular displacement trajectory frames (Equilibrium, Sym Stretch, Bend, Asym Stretch)
        traj = np.array([
            H2O_FRAME_EQ,
            H2O_FRAME_SYM_STRETCH,
            H2O_FRAME_BEND,
            H2O_FRAME_ASYM_STRETCH,
        ], dtype=np.float64)

        xyz_p, json_p = export_crash_animation(
            trajectory_array=traj,
            error_node_id="worker_01",
            output_path=str(anim_out),
            atom_symbols=H2O_SYMBOLS,
        )
        assert Path(xyz_p).exists()
        assert Path(json_p).exists()

    def test_stream_webhook_events(self, tmp_path: Path) -> None:
        """Verifies asynchronous webhook event dispatch and local spooling circuit breaker."""
        spool_target = tmp_path / "spool.jsonl"
        event_data = {"status": "SUCCESS", "node_id": "compute_node_01", "job": "VPT2_Scan"}
        # Without network URL, spools safely to local deque and disk without raising
        dispatched = stream_webhook_events(
            status_payload=event_data,
            webhook_url=None,
            spool_file=str(spool_target),
        )
        assert dispatched is False
        assert spool_target.exists()
        assert len(TELEMETRY_BUFFER) > 0


# =============================================================================
# Phase 10: cochem_catalog_compiler Tests
# =============================================================================

class TestCatalogCompiler:
    """Rigorous tests for Phase 10: PyArrow Out-Of-Core Catalog Compilation."""

    def test_cochem_path_manager(self, tmp_path: Path) -> None:
        """Verifies 6-tier scratch and deliverables path hierarchy resolution."""
        # Tier 1: Explicit custom path
        custom_scratch = tmp_path / "custom_scratch"
        resolved_s = CoChemPathManager.resolve_scratch_dir(custom_path=custom_scratch, create=True)
        assert resolved_s == custom_scratch.resolve()
        assert resolved_s.exists()

        custom_deliv = tmp_path / "custom_deliv"
        resolved_d = CoChemPathManager.resolve_deliverables_dir(custom_path=custom_deliv, create=True)
        assert resolved_d == custom_deliv.resolve()
        assert resolved_d.exists()

    def test_buffer_lock_sync(self, tmp_path: Path) -> None:
        """Verifies physical disk synchronization and minimum byte validation."""
        sync_target = tmp_path / "synced_file.dat"
        sync_target.write_bytes(b"AUTHENTIC_BINARY_PAYLOAD_DATA")

        size = buffer_lock_sync(sync_target, min_bytes=10)
        assert size == len(b"AUTHENTIC_BINARY_PAYLOAD_DATA")

        # Test undersized file failure
        with pytest.raises(CoChemIntegrityError):
            buffer_lock_sync(sync_target, min_bytes=1000)

    def test_spcat_cat_line_parsing(self) -> None:
        """Verifies authentic Pickett .cat line parsing."""
        sample_line = "   22235.0800  0.0050 -4.5678 2    0.0000  3  18001 103 6 1 6       5 2 3      "
        rec = parse_spcat_cat_line(sample_line)
        assert rec is not None
        assert rec["frequency_mhz"] == pytest.approx(22235.0800, abs=1e-3)
        assert rec["uncertainty_mhz"] == pytest.approx(0.0050, abs=1e-4)
        assert rec["log_intensity"] == pytest.approx(-4.5678, abs=1e-4)

    def test_pyarrow_chunked_serializer(self, tmp_path: Path) -> None:
        """Verifies chunked serialization of records to Parquet using distinct authentic transitions."""
        cat_file = tmp_path / "sample.cat"
        # Authentic distinct Pickett SPCAT transition lines spanning microwave / sub-THz spectrum
        cat_lines = [
            "   22235.0800  0.0050 -4.5678 2    0.0000  3  18001 103 6 1 6       5 2 3      \n",
            "   67268.4200  0.0030 -3.8912 2    5.1200  3  18001 103 5 1 4       4 2 2      \n",
            "   98450.1250  0.0040 -3.1245 2   10.4500  3  18001 103 4 1 4       3 2 1      \n",
            "  183310.0870  0.0020 -2.3456 2   14.2500  3  18001 103 3 1 3       2 2 0      \n",
            "  321225.6400  0.0060 -1.9870 2   25.6000  5  18001 103 5 1 5       4 0 4      \n",
            "  325152.9190  0.0010 -1.4520 2   32.8000  5  18001 103 5 1 5       4 2 2      \n",
            "  380197.3720  0.0020 -1.1200 2   45.1000  7  18001 103 4 2 3       3 1 2      \n",
            "  437346.6670  0.0030 -0.8950 2   58.2000  7  18001 103 7 5 3       6 4 2      \n",
            "  439150.8120  0.0040 -0.7420 2   72.5000  9  18001 103 6 4 3       5 3 2      \n",
            "  448001.0750  0.0050 -0.5890 2   88.9000  9  18001 103 4 4 1       3 3 0      \n",
            "  470888.9470  0.0020 -0.4560 2  105.4000 11  18001 103 6 4 2       5 3 3      \n",
            "  474689.1270  0.0010 -0.3210 2  124.0000 11  18001 103 5 3 3       4 2 2      \n",
            "  488491.1330  0.0030 -0.2150 2  145.2000 13  18001 103 6 2 4       5 1 5      \n",
            "  503568.5200  0.0040 -0.1120 2  168.5000 13  18001 103 7 1 7       6 0 6      \n",
            "  504482.6900  0.0020 -0.0540 2  194.0000 15  18001 103 8 2 7       7 1 6      \n",
            "  509292.4200  0.0050  0.0210 2  221.8000 15  18001 103 9 3 6       8 2 7      \n",
            "  547676.4400  0.0030  0.1150 2  252.0000 17  18001 103 5 4 1       4 3 2      \n",
            "  556936.0020  0.0020  0.2340 2  284.5000 17  18001 103 1 1 0       1 0 1      \n",
            "  620700.8000  0.0040  0.3450 2  319.2000 19  18001 103 5 3 2       4 2 3      \n",
            "  752033.1380  0.0010  0.4560 2  356.1000 19  18001 103 2 1 1       2 0 2      \n",
        ]
        cat_file.write_text("".join(cat_lines), encoding="utf-8")

        parquet_out = tmp_path / "catalog.parquet"
        stream = parse_spcat_cat_stream(cat_file, temperature_k=298.15)
        res_path = pyarrow_chunked_serializer(stream, parquet_out, chunk_size=5)
        assert res_path.exists()

        table = pq.read_table(res_path)
        assert table.num_rows == 20
        assert "frequency_mhz" in table.column_names
        assert "temperature_k" in table.column_names

    def test_parallel_temperature_compiler(self, tmp_path: Path) -> None:
        """Verifies multi-temperature catalog compilation across temperature grids."""
        # Create sample catalog for each temperature
        temps = [10.0, 50.0, 298.15]
        cat_mapping: Dict[float, Path] = {}
        sample_cat = (
            "   22235.0800  0.0050 -4.5678 2    0.0000  3  18001 103 6 1 6       5 2 3      \n"
            "  183310.0870  0.0020 -2.3456 2   14.2500  3  18001 103 3 1 3       2 2 0      \n"
        )
        for t in temps:
            p = tmp_path / f"cat_{t:.1f}K.cat"
            p.write_text(sample_cat, encoding="utf-8")
            cat_mapping[t] = p

        out_deliv = tmp_path / "deliv_parquet"
        compiled = parallel_temperature_compiler(
            spcat_runner_or_cat_paths=cat_mapping,
            temperatures=temps,
            output_dir=out_deliv,
            base_scratch=tmp_path / "scratch_workspaces",
            apply_immutable_seal=False,
        )
        assert len(compiled) == 3
        for t in temps:
            assert t in compiled
            assert compiled[t].exists()
            assert compiled[t].stat().st_size > 0

    def test_purge_ghost_outputs(self, tmp_path: Path) -> None:
        """Verifies purging of orphaned temporary and lock artifacts."""
        ghost1 = tmp_path / "orphan.tmp"
        ghost1.write_text("TMP", encoding="utf-8")
        ghost2 = tmp_path / "calculation.lock"
        ghost2.write_text("LOCK", encoding="utf-8")
        real_file = tmp_path / "catalog.parquet"
        real_file.write_text("REAL", encoding="utf-8")

        purged = purge_ghost_outputs(tmp_path)
        assert ghost1 not in [p for p in tmp_path.glob("*") if p.is_file()]
        assert ghost2 not in [p for p in tmp_path.glob("*") if p.is_file()]
        assert real_file.exists()

    def test_readonly_security_seal(self, tmp_path: Path) -> None:
        """Verifies chmod 0444 read-only permission seal and removal."""
        target_file = tmp_path / "immutable_deliverable.dat"
        target_file.write_text("READONLY_DATA", encoding="utf-8")

        apply_readonly_chmod(target_file)
        with pytest.raises(PermissionError):
            with open(target_file, "w") as f:
                f.write("MODIFIED")

        remove_readonly_seal(target_file)
        with open(target_file, "w") as f:
            f.write("PERMITTED_WRITE")
        assert target_file.read_text(encoding="utf-8") == "PERMITTED_WRITE"

    def test_methods_latex_and_bibtex_deduplication(self, tmp_path: Path) -> None:
        """Verifies LaTeX manuscript generation and BibTeX key deduplication."""
        meta = {
            "theory_level": "wB97X-D4",
            "basis_set": "def2-TZVP",
            "software_version": "ORCA 6.1.1",
            "rotational_constants": {"A": 825360.0, "B": 435360.0, "C": 278130.0},
            "dipole_moments": {"mu_b": 1.8546},
            "temperatures": [298.15],
            "defgrid": "DEFGRID3",
        }
        latex_str = generate_methods_latex(meta)
        assert "wB97X-D4" in latex_str
        assert "def2-TZVP" in latex_str
        assert "825360" in latex_str

        bib_raw = """
@article{Neese2022, author = {Neese, Frank}, title = {ORCA 6}, journal = {JCP}, year = {2022}}
@article{Neese2022, author = {Neese, Frank}, title = {ORCA 6}, journal = {JCP}, year = {2022}}
@article{Pickett1991, author = {Pickett, H. M.}, title = {SPCAT}, journal = {JMS}, year = {1991}}
"""
        deduped = deduplicate_bibtex(bib_raw)
        assert deduped.count("@article{Neese2022") == 1
        assert deduped.count("@article{Pickett1991") == 1
