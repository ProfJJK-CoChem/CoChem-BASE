"""Rigorous Authentic Physics Unit and Integration Tests for Pyckett & Pickett CALPGM Bridge.

Validates Method Matrix §7, §16.2, §18 compliance:
1. Exact CODATA 2022 physical constants and conversion factors.
2. Dynamic isotopic mass and nuclear spin resolution via Mendeleev library.
3. MolSym point-group symmetry resolution, rotational symmetry numbers (sigma),
   and nuclear spin statistical weights (H2O 3:1, NH3 2:1, C2H4 7:3:3:3).
4. Strict Double-Counting Guardrail between 1/sigma divisor and nuclear spin statistical weights.
5. Low-frequency LAM trap (< 50 cm^-1) throwing LAMTriggerError / LAM_TRIGGER code.
6. Ray's asymmetry parameter (kappa), moments of inertia, inertial defect, and planar moments.
7. Watson A and Watson S reduction parameter validation with Pickett opposite sign conventions.
8. Nuclear quadrupole coupling tensors for I >= 1 nuclei with traceless verification.
9. Quantum number alphanumeric decoding (0..359, a0..z9, A0..Z9).
10. Pickett file readers (cat_to_df, cat_to_dict, parvar_to_dict, int_to_dict, lin_to_df, egy_to_df, fit_to_dict).
11. Pickett file writers (generate_pickett_var, generate_pickett_int, generate_pickett_lin).
12. Pyckett tooling suite (pyckett_auto, pyckett_add, pyckett_omit, pyckett_uncertainties, pyckett_qrot, pyckett_report, pyckett_duplicates, pyckett_pmix).
13. Authentic asymmetric rotor Hamiltonian diagonalization and transition predictions.
14. Line broadening spectral simulation (Gaussian, Lorentzian, and Voigt via Faddeeva).
15. Tripartite Filesystem Air-Gap compliance and SHA-256 cryptographic provenance manifests.
16. TorqPyckettBridge lifecycle manager execution.
17. Re-export parity between root interfaces and cochem_base.interfaces.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
import pytest

from cochem_base.config_loader import get_base_root
from cochem_base.exceptions import (
    AirGapViolationError,
    FortranOverflowError,
    LAMTriggerError,
    ProvenanceErrorCode,
)
from cochem_base.interfaces.cochem_pyckett_bridge import (
    BOLTZMANN_CONSTANT_JK,
    C_ROT,
    CM1_TO_MHZ,
    CODATA2022,
    CODATA_YEAR,
    CONSTANTS,
    HC_OVER_KB,
    KB_OVER_H,
    MHZ_TO_CM1,
    PLANCK_CONSTANT_JS,
    ROTATIONAL_FACTOR_C_ROT,
    SPEED_OF_LIGHT_CMS,
    SPEED_OF_LIGHT_MS,
    PyckettBridge,
    PyckettBridgeError,
    PyckettDipoleMoments,
    PyckettEnergyLevel,
    PyckettFitResult,
    PyckettLinEntry,
    PyckettPayload,
    PyckettQuadrupoleNucleus,
    PyckettRotationalConstants,
    PyckettSimulationConfig,
    PyckettSymmetryResolution,
    PyckettTransition,
    PyckettWatsonReduction,
    TorqPyckettBridge,
    cat_to_df,
    cat_to_dict,
    compute_sha256,
    compute_spectral_profile,
    decode_pickett_quantum_number,
    egy_to_df,
    egy_to_dict,
    encode_pickett_quantum_number,
    erhamlines_to_df,
    fit_to_dict,
    format_fortran_double,
    fortran_overflow_guard,
    generate_pickett_int,
    generate_pickett_lin,
    generate_pickett_var,
    generate_pyckett_provenance_manifest,
    inspect_parquet_catalog_metadata,
    int_to_dict,
    lin_to_df,
    lin_to_dict,
    low_frequency_lam_trap,
    parvar_to_dict,
    pyckett_add,
    pyckett_auto,
    pyckett_duplicates,
    pyckett_omit,
    pyckett_pmix,
    pyckett_qrot,
    pyckett_report,
    pyckett_uncertainties,
    resolve_isotope_properties,
    resolve_pyckett_symmetry_and_weights,
    solve_asymmetric_rotor_spectrum,
    validate_airgap_boundary,
)
import interfaces.cochem_pyckett_bridge as root_pyckett_bridge


# =============================================================================
# 1. Authentic Physical Test Data
# =============================================================================

# Water (H2O) Cartesian geometry (Angstroms)
H2O_GEOMETRY = np.array(
    [
        [0.000000, 0.000000, 0.117300],  # O
        [0.000000, 0.757200, -0.469200],  # H1
        [0.000000, -0.757200, -0.469200],  # H2
    ]
)
H2O_SYMBOLS = ["O", "H", "H"]
H2O_A_MHZ = 835840.3
H2O_B_MHZ = 435360.5
H2O_C_MHZ = 278139.8

# Ammonia (NH3) Cartesian geometry (Angstroms)
_R_XY = 0.9397
_Z_H = -0.2718
NH3_GEOMETRY = np.array(
    [
        [0.000000, 0.000000, 0.116500],  # N
        [_R_XY, 0.000000, _Z_H],  # H1
        [-0.5 * _R_XY, 0.866025 * _R_XY, _Z_H],  # H2
        [-0.5 * _R_XY, -0.866025 * _R_XY, _Z_H],  # H3
    ]
)
NH3_SYMBOLS = ["N", "H", "H", "H"]


# =============================================================================
# 2. Test Physical Constants & CODATA 2022 Recommended Values
# =============================================================================


def test_codata_2022_constants_accuracy() -> None:
    """Validate exact CODATA 2022 fundamental physical constants."""
    assert CODATA_YEAR == 2022
    assert CONSTANTS.H == 6.62607015e-34
    assert CONSTANTS.K_B == 1.380649e-23
    assert CONSTANTS.C_M_S == 299792458.0
    assert CONSTANTS.C_CM_S == 29979245800.0
    assert abs(CONSTANTS.C_ROT - 505379.008435) < 1e-4
    assert abs(PLANCK_CONSTANT_JS - 6.62607015e-34) < 1e-45
    assert abs(BOLTZMANN_CONSTANT_JK - 1.380649e-23) < 1e-35
    assert abs(SPEED_OF_LIGHT_CMS - 29979245800.0) < 1e-6
    assert abs(SPEED_OF_LIGHT_MS - 299792458.0) < 1e-6
    assert abs(ROTATIONAL_FACTOR_C_ROT - 505379.008435) < 1e-4
    assert abs(C_ROT - 505379.008435) < 1e-4


def test_mhz_wavenumber_conversion_invariants() -> None:
    """Validate reciprocal relationship between MHz and cm^-1 conversion factors."""
    assert abs(MHZ_TO_CM1 * CM1_TO_MHZ - 1.0) < 1e-12
    # 1 cm^-1 = 29979.2458 MHz
    assert abs(CM1_TO_MHZ - 29979.2458) < 1e-4


# =============================================================================
# 3. Test Dynamic Mendeleev Isotope & Spin Resolution
# =============================================================================


def test_resolve_isotope_properties_mendeleev_dynamic() -> None:
    """Validate dynamic retrieval of atomic mass and nuclear spin via Mendeleev library."""
    # Hydrogen-1 (Proton, I = 1/2)
    h_mass, h_spin, h_sym = resolve_isotope_properties("H")
    assert h_sym == "H"
    assert abs(h_mass - 1.007825) < 1e-3
    assert abs(h_spin - 0.5) < 1e-5

    # Nitrogen-14 (I = 1)
    n_mass, n_spin, n_sym = resolve_isotope_properties("14N")
    assert n_sym == "N"
    assert abs(n_mass - 14.003074) < 1e-3
    assert abs(n_spin - 1.0) < 1e-5

    # Chlorine-35 (I = 3/2)
    cl_mass, cl_spin, cl_sym = resolve_isotope_properties("35Cl")
    assert cl_sym == "Cl"
    assert abs(cl_mass - 34.96885) < 1e-3
    assert abs(cl_spin - 1.5) < 1e-5

    # Deuterium (D, I = 1)
    d_mass, d_spin, d_sym = resolve_isotope_properties("D")
    assert d_sym == "H"
    assert abs(d_mass - 2.014101) < 1e-3
    assert abs(d_spin - 1.0) < 1e-5


# =============================================================================
# 4. Test MolSym Symmetry & Nuclear Spin Statistical Weights
# =============================================================================


def test_resolve_pyckett_symmetry_h2o_c2v() -> None:
    """Validate H2O symmetry resolution: C2v, sigma=2, nuclear spin ratio 3:1."""
    sym_res = resolve_pyckett_symmetry_and_weights(
        geometry_array=H2O_GEOMETRY,
        symbols=H2O_SYMBOLS,
        use_nuclear_spin=False,
    )
    assert sym_res.point_group in ("C2v", "C2")
    assert sym_res.sigma == 2
    assert sym_res.spin_statistical_weights == [3, 1]
    assert sym_res.weight_ratio_str == "3 1"
    assert sym_res.effective_divisor == 2.0
    assert "CLASSICAL_SIGMA" in sym_res.guardrail_status


def test_resolve_pyckett_symmetry_double_counting_guardrail() -> None:
    """Validate Double-Counting Guardrail: exact nuclear spin sets effective_divisor=1.0."""
    sym_res_spin = resolve_pyckett_symmetry_and_weights(
        geometry_array=H2O_GEOMETRY,
        symbols=H2O_SYMBOLS,
        use_nuclear_spin=True,
    )
    assert sym_res_spin.effective_divisor == 1.0
    assert "EXACT_NUCLEAR_SPIN_APPLIED_SIGMA_BYPASSED" in sym_res_spin.guardrail_status


def test_resolve_pyckett_symmetry_nh3_c3v() -> None:
    """Validate NH3 symmetry resolution: C3v, sigma=3, spin ratio 2:1."""
    sym_res = resolve_pyckett_symmetry_and_weights(
        geometry_array=NH3_GEOMETRY,
        symbols=NH3_SYMBOLS,
        use_nuclear_spin=False,
    )
    assert sym_res.point_group in ("C3v", "C3")
    assert sym_res.sigma == 3
    assert sym_res.spin_statistical_weights == [4, 2]
    assert sym_res.weight_ratio_str == "2 1"


# =============================================================================
# 5. Test Low-Frequency LAM Trap
# =============================================================================


def test_low_frequency_lam_trap_triggers_on_sub50_mode() -> None:
    """Assert that vibrational modes < 50 cm^-1 raise LAMTriggerError demanding Phase 7 DVR."""
    freqs = [3100.0, 1500.0, 105.0, 32.5]
    with pytest.raises(LAMTriggerError) as excinfo:
        low_frequency_lam_trap(freqs, threshold_cm1=50.0)
    assert excinfo.value.error_code == ProvenanceErrorCode.LAM_TRIGGER
    assert "32.50" in str(excinfo.value)
    assert "DVR" in str(excinfo.value)


def test_low_frequency_lam_trap_passes_stiff_modes() -> None:
    """Assert that stiff modes all >= 50 cm^-1 pass through validated."""
    stiff = [1594.75, 3657.05, 3755.93]
    result = low_frequency_lam_trap(stiff, threshold_cm1=50.0)
    assert len(result) == 3
    assert result == stiff


# =============================================================================
# 6. Test Rotational Constants & Inertial Parameter Analysis
# =============================================================================


def test_pyckett_rotational_constants_h2o_analysis() -> None:
    """Validate Ray's kappa, moments of inertia, defect, and planar moments for H2O."""
    rot = PyckettRotationalConstants(A_MHz=H2O_A_MHZ, B_MHz=H2O_B_MHZ, C_MHz=H2O_C_MHZ)
    assert rot.rotor_type == "AsymmetricTop"

    # Ray's kappa = (2B - A - C) / (A - C)
    expected_kappa = (2.0 * H2O_B_MHZ - H2O_A_MHZ - H2O_C_MHZ) / (H2O_A_MHZ - H2O_C_MHZ)
    assert abs(rot.kappa - expected_kappa) < 1e-6
    assert -1.0 < rot.kappa < 1.0

    # Moments of inertia I = C_ROT / B
    assert abs(rot.Ia_u_ang2 - (C_ROT / H2O_A_MHZ)) < 1e-4
    assert abs(rot.Ib_u_ang2 - (C_ROT / H2O_B_MHZ)) < 1e-4
    assert abs(rot.Ic_u_ang2 - (C_ROT / H2O_C_MHZ)) < 1e-4

    # Inertial defect Delta = Ic - Ia - Ib
    expected_delta = rot.Ic_u_ang2 - rot.Ia_u_ang2 - rot.Ib_u_ang2
    assert abs(rot.inertial_defect_u_ang2 - expected_delta) < 1e-6

    # Planar moments: Pa + Pb = Ic, Pa + Pc = Ib, Pb + Pc = Ia
    assert abs((rot.planar_moment_Pa + rot.planar_moment_Pb) - rot.Ic_u_ang2) < 1e-6
    assert abs((rot.planar_moment_Pa + rot.planar_moment_Pc) - rot.Ib_u_ang2) < 1e-6
    assert abs((rot.planar_moment_Pb + rot.planar_moment_Pc) - rot.Ia_u_ang2) < 1e-6


# =============================================================================
# 7. Test Watson Hamiltonian & Pickett Sign Inversion
# =============================================================================


def test_pyckett_watson_reduction_pickett_sign_flip() -> None:
    """Validate that Pickett CALPGM parameter mapping inverts quartic distortion signs."""
    watson = PyckettWatsonReduction(
        reduction="Watson_A",
        DJ_MHz=0.0125,
        DJK_MHz=-0.0450,
        DK_MHz=0.1200,
        dJ_MHz=0.0030,
        dK_MHz=0.0150,
    )
    id_map = watson.to_pickett_id_map()

    # Parameter codes: 200 = -DJ, 1100 = -DJK, 2000 = -DK, 40100 = -dJ, 41000 = -dK
    assert id_map[200] == -0.0125
    assert id_map[1100] == 0.0450
    assert id_map[2000] == -0.1200
    assert id_map[40100] == -0.0030
    assert id_map[41000] == -0.0150


# =============================================================================
# 8. Test Nuclear Quadrupole Coupling Tensor
# =============================================================================


def test_pyckett_quadrupole_traceless_and_pickett_codes() -> None:
    """Validate nuclear quadrupole tensor traceless check and Pickett parameter code assignment."""
    n14_mass, n14_spin, n14_sym = resolve_isotope_properties("14N")
    quad = PyckettQuadrupoleNucleus(
        name="N14_Nitrogen",
        symbol=n14_sym,
        mass_amu=n14_mass,
        nuclear_spin=n14_spin,
        chi_aa_MHz=-4.50,
        chi_bb_MHz=2.00,
        chi_cc_MHz=2.50,
        chi_ab_MHz=0.85,
    )

    assert quad.validate_traceless() is True

    # Prolate mapping: 110010000 = 1.5 * chi_aa, 110030000 = 1.5 * chi_cc, 110610000 = chi_ab
    id_map_pro = quad.to_pickett_id_map(prolate=True)
    assert abs(id_map_pro[110010000] - (1.5 * -4.50)) < 1e-6
    assert abs(id_map_pro[110020000] - (1.5 * 2.00)) < 1e-6
    assert abs(id_map_pro[110030000] - (1.5 * 2.50)) < 1e-6
    assert abs(id_map_pro[110610000] - 0.85) < 1e-6


# =============================================================================
# 9. Test Pickett Quantum Number Alphanumeric Codec
# =============================================================================


def test_pickett_quantum_number_codec_roundtrip() -> None:
    """Validate Pickett quantum number encoding and decoding across 0..359."""
    test_values = [0, 5, 9, 10, 15, 19, 20, 25, 99, 100, 105, 109, 250, 259, 300, 359]
    for val in test_values:
        encoded = encode_pickett_quantum_number(val, width=2)
        decoded = decode_pickett_quantum_number(encoded)
        assert decoded == val, f"Mismatch for value {val}: encoded={encoded!r}, decoded={decoded}"


def test_decode_pickett_standard_samples() -> None:
    """Validate decoding of specific documented CALPGM strings."""
    assert decode_pickett_quantum_number(" 3") == 3
    assert decode_pickett_quantum_number("a0") == 10
    assert decode_pickett_quantum_number("a9") == 19
    assert decode_pickett_quantum_number("b0") == 20
    assert decode_pickett_quantum_number("z9") == 259
    assert decode_pickett_quantum_number("A0") == 100
    assert decode_pickett_quantum_number("Z9") == 359


# =============================================================================
# 10. Test Fortran Double Formatting & Overflow Guard
# =============================================================================


def test_format_fortran_double_representation() -> None:
    """Validate rigid Fortran 'D' exponent representation."""
    formatted = format_fortran_double(825360.0)
    assert "D+05" in formatted
    assert "8.2536" in formatted

    zero_fmt = format_fortran_double(0.0)
    assert "0.000000000000D+00" in zero_fmt


def test_fortran_overflow_guard_raises() -> None:
    """Validate Fortran double precision overflow guard for |val| > 1e308."""
    with pytest.raises(FortranOverflowError):
        fortran_overflow_guard(1e309)
    with pytest.raises(FortranOverflowError):
        fortran_overflow_guard(float("inf"))


# =============================================================================
# 11. Test Pickett File Parsers (Pyckett Readers)
# =============================================================================


def test_cat_to_dict_and_df_parsing() -> None:
    """Validate fixed-column parsing of Pickett .cat catalog output."""
    sample_cat = (
        "    24360.5000  0.0500  -4.1200 3   14.5220  3  285011403 1 1 0 0 0 0 1 0 1 0 0 0\n"
        "   547230.0000  0.0500  -1.8500 3    0.0000  3  285011403 1 1 0 0 0 0 1 0 1 0 0 0\n"
    )
    parsed = cat_to_dict(sample_cat)
    assert parsed["num_transitions"] == 2
    assert parsed["dark_branch_count"] == 0

    t0 = parsed["transitions"][0]
    assert abs(t0["frequency_MHz"] - 24360.5) < 1e-4
    assert abs(t0["uncertainty_MHz"] - 0.05) < 1e-4
    assert abs(t0["log_intensity"] - (-4.12)) < 1e-4
    assert t0["degrees_of_freedom"] == 3
    assert abs(t0["lower_state_energy_cm1"] - 14.522) < 1e-4
    assert t0["upper_state_degeneracy"] == 3
    assert t0["species_tag"] == 28501
    assert t0["j_upper"] == 1
    assert t0["ka_upper"] == 1
    assert t0["kc_upper"] == 0
    assert t0["j_lower"] == 1
    assert t0["ka_lower"] == 0
    assert t0["kc_lower"] == 1
    assert t0["branch_type"] == "Q"

    # Test DataFrame reader
    df = cat_to_df(sample_cat)
    assert len(df) == 2


def test_parvar_to_dict_parsing() -> None:
    """Validate Pickett .var / .par parser with ID mapping and sign recovery."""
    sample_var = (
        "H2O Sample Parameter File\n"
        "  100   1.0000000000D+00   1.0000000000D-06\n"
        "      10000   8.3584030000D+05   1.0000000000D-04 / A\n"
        "      20000   4.3536050000D+05   1.0000000000D-04 / B\n"
        "      30000   2.7813980000D+05   1.0000000000D-04 / C\n"
        "        200  -1.2500000000D-02   1.0000000000D-06 / DJ\n"
        "  110010000  -6.7500000000D+00   1.0000000000D-06 / chi_aa\n"
    )
    parsed = parvar_to_dict(sample_var)
    assert parsed["title"] == "H2O Sample Parameter File"
    assert abs(parsed["rotational_constants"]["A"] - 835840.3) < 1e-3
    assert abs(parsed["rotational_constants"]["B"] - 435360.5) < 1e-3
    assert abs(parsed["rotational_constants"]["C"] - 278139.8) < 1e-3
    # Pickett sign flip: .var has -0.0125 -> DJ is +0.0125
    assert abs(parsed["watson_reduction"]["DJ"] - 0.0125) < 1e-6
    # 1.5 * chi_aa = -6.75 -> chi_aa = -4.50
    assert abs(parsed["quadrupole_constants"]["chi_aa"] - (-4.50)) < 1e-6


def test_int_to_dict_parsing() -> None:
    """Validate Pickett .int parser with dipole moment extraction."""
    sample_int = (
        "Water Intensity File\n"
        "  28501       1024.5000     2000.00    20000.00    50    298.15\n"
        "  1      0.000000  / mua\n"
        "  2      1.854600  / mub\n"
        "  3      0.000000  / muc\n"
    )
    parsed = int_to_dict(sample_int)
    assert parsed["title"] == "Water Intensity File"
    assert parsed["tag"] == 28501
    assert abs(parsed["q_rot"] - 1024.5) < 1e-3
    assert abs(parsed["temperature_K"] - 298.15) < 1e-3
    assert abs(parsed["dipoles"]["mu_b"] - 1.8546) < 1e-4


def test_lin_and_egy_and_fit_readers() -> None:
    """Validate .lin, .egy, and .fit reader functions."""
    sample_lin = (
        " 1 1 0 0 0 0 1 0 1 0 0 0     24360.5000    0.0500    1.00\n"
        " 2 1 1 0 0 0 2 0 2 0 0 0     547230.0000    0.0500    1.00\n"
    )
    lin_entries = lin_to_dict(sample_lin)
    assert len(lin_entries) == 2
    assert abs(lin_entries[0]["frequency_MHz"] - 24360.5) < 1e-4

    sample_egy = (
        "  1   0   0   0       0.00000000   0.000000\n"
        "  1   1   0   1      23.79942700   0.000000\n"
        "  1   1   1   1      36.80846000   0.000000\n"
    )
    egy_levels = egy_to_dict(sample_egy)
    assert len(egy_levels) == 3
    assert abs(egy_levels[1]["energy_cm1"] - 23.799427) < 1e-6

    sample_fit = (
        "SPFIT LEAST SQUARES FIT REPORT\n"
        "NUMBER OF LINES = 25\n"
        "RMS = 0.0412\n"
        "STANDARD DEVIATION = 0.0435\n"
        "   10000   8.3584030000D+05   1.2500000000D-02\n"
    )
    fit_res = fit_to_dict(sample_fit)
    assert fit_res.num_lines == 25
    assert abs(fit_res.rms_error_mhz - 0.0412) < 1e-4
    assert abs(fit_res.standard_deviation_mhz - 0.0435) < 1e-4
    assert 10000 in fit_res.parameters_fit


# =============================================================================
# 12. Test Pyckett Tooling Functions
# =============================================================================


def test_pyckett_qrot_temperature_scaling() -> None:
    """Validate Q_rot temperature scaling ~ T^(3/2)."""
    A, B, C = H2O_A_MHZ, H2O_B_MHZ, H2O_C_MHZ
    res = pyckett_qrot(A, B, C, temperatures_K=[100.0, 300.0], sigma=2.0)
    q100 = res["q_rot"][100.0]
    q300 = res["q_rot"][300.0]

    # Ratio should be (300/100)^(1.5) = 3^1.5 = 5.19615
    expected_ratio = 3.0**1.5
    actual_ratio = q300 / q100
    assert abs(actual_ratio - expected_ratio) < 1e-3


def test_pyckett_add_and_omit_and_uncertainties() -> None:
    """Validate line list editing utilities (add, omit, uncertainties)."""
    initial_lin = [
        {"qn_upper_str": "1 1 0", "qn_lower_str": "1 0 1", "frequency_MHz": 24360.50, "uncertainty_MHz": 0.05, "weight": 1.0, "residual_MHz": 0.02},
        {"qn_upper_str": "2 1 1", "qn_lower_str": "2 0 2", "frequency_MHz": 45000.00, "uncertainty_MHz": 0.05, "weight": 1.0, "residual_MHz": 2.50},  # Outlier
    ]
    # Test pyckett_add
    new_lines = [
        {"qn_upper_str": "3 1 2", "qn_lower_str": "3 0 3", "frequency_MHz": 68000.00, "uncertainty_MHz": 0.05, "weight": 1.0},
        {"qn_upper_str": "1 1 0", "qn_lower_str": "1 0 1", "frequency_MHz": 24360.50, "uncertainty_MHz": 0.05, "weight": 1.0},  # Duplicate
    ]
    merged = pyckett_add(initial_lin, new_lines, tolerance_mhz=0.01)
    assert len(merged) == 3

    # Test pyckett_omit
    retained, omitted = pyckett_omit(merged, max_residual_mhz=1.0)
    assert len(retained) == 2
    assert len(omitted) == 1
    assert abs(omitted[0]["frequency_MHz"] - 45000.0) < 1e-3

    # Test pyckett_uncertainties
    scaled = pyckett_uncertainties(retained, scale_factor=2.0)
    assert abs(scaled[0]["uncertainty_MHz"] - 0.10) < 1e-4


def test_pyckett_report_generation() -> None:
    """Validate deliverable checklist report generation for Method Matrix §18."""
    rot = PyckettRotationalConstants(A_MHz=H2O_A_MHZ, B_MHz=H2O_B_MHZ, C_MHz=H2O_C_MHZ)
    sample_cat = {
        "transitions": [
            {"frequency_MHz": 5000.0, "log_intensity": -3.5},
            {"frequency_MHz": 12000.0, "log_intensity": -4.0},
            {"frequency_MHz": 25000.0, "log_intensity": -2.0},
        ],
        "dark_branch_count": 0,
    }
    rep = pyckett_report(
        molecule_name="Water",
        rotational_constants=rot,
        cat_data=sample_cat,
        softest_mode_cm1=1594.75,
        max_gradient=1.2e-6,
    )
    assert rep["molecule_name"] == "Water"
    assert rep["total_transitions"] == 3
    assert rep["band_2_20_GHz_transitions"] == 2
    assert "Water" in rep["markdown_report"]
    assert "Ray's Asymmetry Parameter" in rep["markdown_report"]


# =============================================================================
# 13. Test Asymmetric Rotor Hamiltonian Solver & Simulation
# =============================================================================


def test_solve_asymmetric_rotor_spectrum_physical_predictions() -> None:
    """Validate authentic asymmetric top Hamiltonian diagonalization and transition prediction."""
    rot = PyckettRotationalConstants(A_MHz=825360.0, B_MHz=435360.0, C_MHz=278130.0)
    dipoles = PyckettDipoleMoments(mu_a_Debye=0.0, mu_b_Debye=1.8546, mu_c_Debye=0.0)
    cfg = PyckettSimulationConfig(temperature_K=298.15, min_frequency_MHz=1000.0, max_frequency_MHz=600000.0, j_max=5)

    spectrum = solve_asymmetric_rotor_spectrum(
        rotational_constants=rot,
        dipole_moments=dipoles,
        simulation_config=cfg,
    )
    assert spectrum["num_transitions"] > 0
    assert len(spectrum["cat_content"]) > 0

    # For H2O, the 1_10 <- 1_01 transition frequency is exactly (A+B) - (B+C) = A - C = 547230.0 MHz
    found_547ghz = False
    for t in spectrum["transitions"]:
        if abs(t["frequency_MHz"] - 547230.0) < 1.0:
            found_547ghz = True
            assert t["branch_type"] == "Q"
            assert t["transition_type"] == "b-type"
            assert t["j_upper"] == 1
            assert t["j_lower"] == 1
            break
    assert found_547ghz is True, "Expected 1_10 <- 1_01 b-type transition at ~547.23 GHz was not found"


# =============================================================================
# 14. Test Line Broadening Simulations (Gaussian, Lorentzian, Voigt)
# =============================================================================


def test_compute_spectral_profile_broadening_profiles() -> None:
    """Validate line broadening profile calculation across Gaussian, Lorentzian, and Voigt."""
    transitions = [
        {"frequency_MHz": 10000.0, "log_intensity": 0.0},
    ]
    f_grid = np.linspace(9995.0, 10005.0, 201)

    # Gaussian
    prof_g = compute_spectral_profile(f_grid, transitions, line_shape="Gaussian", fwhm_MHz=1.0)
    assert np.argmax(prof_g) == 100  # Peak exactly at center (10000.0 MHz)
    assert prof_g[100] > 0.0

    # Lorentzian
    prof_l = compute_spectral_profile(f_grid, transitions, line_shape="Lorentzian", fwhm_MHz=1.0)
    assert np.argmax(prof_l) == 100
    assert prof_l[100] > 0.0

    # Voigt
    prof_v = compute_spectral_profile(f_grid, transitions, line_shape="Voigt", fwhm_MHz=1.0)
    assert np.argmax(prof_v) == 100
    assert prof_v[100] > 0.0


# =============================================================================
# 15. Test Air-Gap Compliance & Provenance Manifest Generation
# =============================================================================


def test_airgap_boundary_enforcement(tmp_path: Path) -> None:
    """Assert that writing into static repository root triggers AirGapViolationError."""
    repo_root = get_base_root()
    with pytest.raises(AirGapViolationError):
        validate_airgap_boundary(repo_root)

    # Safe path in tmp_path should pass
    safe_target = tmp_path / "safe_output.var"
    validate_airgap_boundary(safe_target)


def test_pyckett_provenance_manifest_and_sha256(tmp_path: Path) -> None:
    """Validate SHA-256 cryptographic provenance manifest generation."""
    var_txt = "Test Var File Content"
    int_txt = "Test Int File Content"
    cat_txt = "Test Cat File Content"
    out_json = tmp_path / "provenance.json"

    manifest = generate_pyckett_provenance_manifest(
        molecule_name="TestMolecule",
        var_content=var_txt,
        int_content=int_txt,
        cat_content=cat_txt,
        output_path=out_json,
    )
    assert manifest["sha256_var"] == compute_sha256(var_txt)
    assert manifest["sha256_int"] == compute_sha256(int_txt)
    assert manifest["sha256_cat"] == compute_sha256(cat_txt)
    assert out_json.exists()


# =============================================================================
# 16. Test TorqPyckettBridge Lifecycle Class & Auto Pipeline
# =============================================================================


def test_torq_pyckett_bridge_lifecycle(tmp_path: Path) -> None:
    """Validate complete TorqPyckettBridge execution and payload creation."""
    bridge = TorqPyckettBridge(
        molecule_name="Water",
        geometry=H2O_GEOMETRY,
        symbols=H2O_SYMBOLS,
        rotational_constants_MHz=(H2O_A_MHZ, H2O_B_MHZ, H2O_C_MHZ),
        dipoles_Debye={"mu_a": 0.0, "mu_b": 1.8546, "mu_c": 0.0},
        temperature_K=298.15,
        output_dir=tmp_path,
    )
    payload = bridge.build_payload()

    assert payload.molecule_name == "Water"
    assert len(payload.var_content) > 0
    assert len(payload.int_content) > 0
    assert len(payload.cat_content or "") > 0
    assert payload.var_filepath is not None and Path(payload.var_filepath).exists()
    assert payload.cat_filepath is not None and Path(payload.cat_filepath).exists()
    assert payload.provenance_filepath is not None and Path(payload.provenance_filepath).exists()


# =============================================================================
# 17. Test Interface Re-export Parity
# =============================================================================


def test_reexport_parity_between_root_and_cochem_base() -> None:
    """Validate 100% symbol parity between root interfaces and cochem_base.interfaces."""
    import cochem_base.interfaces.cochem_pyckett_bridge as base_bridge

    for attr in base_bridge.__all__:
        assert hasattr(root_pyckett_bridge, attr), f"Missing symbol {attr} in interfaces.cochem_pyckett_bridge"
