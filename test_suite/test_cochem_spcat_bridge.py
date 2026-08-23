"""Rigorous Authentic Physics Unit and Integration Tests for Stage 5.1: Statistical Mechanics & SPCAT Bridge.

Tests validate:
1. Low-Frequency LAM Trap (< 50 cm^-1) throwing LAMTriggerError / LAM_TRIGGER code.
2. MolSym point-group symmetry resolution (C2v, sigma=2) and nuclear spin statistical weights ('3 1').
3. Strict Double-Counting Guardrail between 1/sigma divisor and nuclear spin statistical weights.
4. Vibrational partition coupling across temperature gradients with automatic LAM mode dropping.
5. Exact CODATA 2022 fundamental physical constants.
6. Fortran Double Precision overflow guard (|val| > 1e308) raising FortranOverflowError.
7. Rigid character alignment and 'D' exponent formatting for parameter lines.
8. Complete Pickett SPCAT .var and .int ASCII file generation.
9. Tripartite Filesystem Air-Gap compliance and SHA-256 cryptographic provenance manifests.
"""

from __future__ import annotations

import json
import math
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
from cochem_spcat_bridge import (
    CONSTANTS,
    PartitionFunctionResult,
    SPCATPayload,
    TorqSpcatBridge,
    apply_symmetry_divisors,
    build_complete_spcat_payload,
    calculate_rotational_partition_function,
    calculate_vibrational_partition_function,
    compute_coupled_partition_functions,
    format_fortran_double,
    fortran_double_precision_formatter,
    fortran_overflow_guard,
    generate_spcat_int,
    generate_spcat_var,
    low_frequency_lam_trap,
    low_frequency_trap,
    route_3tier_abinitio_payload,
    validate_airgap_boundary,
    vibrational_partition_coupling,
)

# =============================================================================
# 1. Authentic Physical Test Data (Water H2O & Ammonia NH3)
# =============================================================================

# Real experimental / ab initio Cartesian geometry for Water (H2O in Angstroms)
H2O_GEOMETRY = np.array(
    [
        [0.000000, 0.000000, 0.117300],  # Oxygen (O)
        [0.000000, 0.757200, -0.469200],  # Hydrogen (H1)
        [0.000000, -0.757200, -0.469200],  # Hydrogen (H2)
    ],
    dtype=np.float64,
)
H2O_SYMBOLS = ["O", "H", "H"]

# Real rotational constants for H2O (MHz)
H2O_A_MHZ = 825360.0  # ~ 27.877 cm^-1
H2O_B_MHZ = 435360.0  # ~ 14.522 cm^-1
H2O_C_MHZ = 278130.0  # ~ 9.277 cm^-1

# Real normal mode harmonic vibrational frequencies for H2O (cm^-1)
H2O_HARMONIC_FREQUENCIES = [1594.75, 3657.05, 3755.93]  # Bend, sym stretch, asym stretch

# Real dipole moment for H2O in Debye (directed along b-axis in standard orientation)
H2O_DIPOLES = {"mu_a": 0.0, "mu_b": 1.8546, "mu_c": 0.0}

# Quartic centrifugal distortion constants for H2O (Watson A-reduction in MHz)
H2O_WATSON_A = {
    "DJ": 1.567e-5,
    "DJK": -5.230e-5,
    "DK": 2.890e-4,
    "d1": 3.450e-6,
    "d2": 1.120e-5,
}


# =============================================================================
# 2. Test Low-Frequency LAM Trap (Physical Guardrail against RRHO Failure)
# =============================================================================


def test_low_frequency_lam_trap_triggers_on_low_mode() -> None:
    """Pass test frequency array containing [3100.0, 1500.0, 105.0, 24.5] cm^-1 to low_frequency_lam_trap.

    Assert that the function correctly identifies 24.5 cm^-1, halts the standard RRHO flow,
    and raises a LAMTriggerError with error_code LAM_TRIGGER indicating that DVR treatment
    is physically required.
    """
    frequencies = [3100.0, 1500.0, 105.0, 24.5]

    with pytest.raises(LAMTriggerError) as exc_info:
        low_frequency_lam_trap(frequencies)

    err = exc_info.value
    assert err.error_code == ProvenanceErrorCode.LAM_TRIGGER or str(err.error_code) == "LAM_TRIGGER"
    assert "24.50 cm^-1" in err.message or "24.5" in str(err.details.get("flagged_frequencies", []))
    assert err.details["threshold_cm1"] == 50.0
    assert 24.5 in err.details["flagged_frequencies"]
    assert "DVR" in err.message


def test_low_frequency_lam_trap_passes_on_stiff_modes() -> None:
    """Verify that authentic stiff vibrational frequencies (>= 50 cm^-1) pass cleanly."""
    stiff_modes = low_frequency_lam_trap(H2O_HARMONIC_FREQUENCIES)
    assert len(stiff_modes) == 3
    assert stiff_modes == H2O_HARMONIC_FREQUENCIES


def test_low_frequency_lam_trap_multiple_lam_modes() -> None:
    """Verify detection when multiple low torsional frequencies are present."""
    frequencies = [2800.0, 1200.0, 42.1, 15.3, 0.0]
    with pytest.raises(LAMTriggerError) as exc_info:
        low_frequency_lam_trap(frequencies, threshold_cm1=50.0)

    flagged = exc_info.value.details["flagged_frequencies"]
    assert 15.3 in flagged
    assert 42.1 in flagged
    assert 0.0 not in flagged


# =============================================================================
# 3. Test MolSym Point-Group & Nuclear Spin Statistical Weights
# =============================================================================


def test_molsym_spin_and_divisor_validation_h2o() -> None:
    """Feed aligned Cartesian coordinates of Water (H2O) to apply_symmetry_divisors().

    Assert that MolSym correctly identifies the C2v point group.
    Assert the returned divisor is exactly sigma = 2.
    Assert the returned spin statistical weight string correctly evaluates to the
    Ortho/Para ratio of '3 1'.
    """
    res = apply_symmetry_divisors(geometry_array=H2O_GEOMETRY, symbols=H2O_SYMBOLS)

    assert res.point_group == "C2v"
    assert res.sigma == 2
    assert res.spin_statistical_weights == [3, 1]
    assert res.spin_weight_ratio_str == "3 1"
    assert res.effective_divisor == 2.0
    assert "GUARDRAIL_ENFORCED" in res.guardrail_status


def test_symmetry_double_counting_guardrail_selection() -> None:
    """Enforce strict Double-Counting Guardrail between 1/sigma divisor and nuclear spin weights.

    When nuclear spin weights are explicitly applied, classical 1/sigma divisor must be bypassed
    (effective_divisor = 1.0) to prevent double-deflating the state density.
    """
    res_classical = apply_symmetry_divisors(H2O_GEOMETRY, H2O_SYMBOLS, use_nuclear_spin=False)
    assert res_classical.sigma == 2
    assert res_classical.effective_divisor == 2.0
    assert res_classical.guardrail_status == "GUARDRAIL_ENFORCED_CLASSICAL_SIGMA_APPLIED"

    res_spin = apply_symmetry_divisors(H2O_GEOMETRY, H2O_SYMBOLS, use_nuclear_spin=True)
    assert res_spin.sigma == 2
    assert res_spin.effective_divisor == 1.0
    assert (
        res_spin.guardrail_status == "GUARDRAIL_ENFORCED_EXACT_NUCLEAR_SPIN_APPLIED_SIGMA_BYPASSED"
    )


def test_molsym_symmetry_ammonia_c3v() -> None:
    """Verify symmetry and spin weights for Ammonia (NH3) in C3v."""
    r_nh = 1.012
    theta_hnh = math.radians(106.68)
    sin_beta = math.sqrt(2.0 / 3.0 * (1.0 - math.cos(theta_hnh)))
    cos_beta = math.sqrt(1.0 - sin_beta**2)
    r_xy = r_nh * sin_beta
    z_h = -r_nh * cos_beta
    coords_nh3 = np.array(
        [
            [0.0, 0.0, 0.0],
            [r_xy, 0.0, z_h],
            [-r_xy * 0.5, r_xy * math.sqrt(3) / 2.0, z_h],
            [-r_xy * 0.5, -r_xy * math.sqrt(3) / 2.0, z_h],
        ],
        dtype=float,
    )
    symbols_nh3 = ["N", "H", "H", "H"]

    res = apply_symmetry_divisors(coords_nh3, symbols_nh3)
    assert res.point_group == "C3v"
    assert res.sigma == 3
    assert res.spin_weight_ratio_str in ("2 1", "4 2")


# =============================================================================
# 4. Test Fortran Double Precision Formatter & String Alignment
# =============================================================================


def test_fortran_string_alignment_and_type() -> None:
    """Pass quartic centrifugal distortion parameter (DJ = 0.00001567 MHz) to fortran_double_precision_formatter().

    Assert that the output string strictly uses the 'D' identifier (e.g. 1.567D-05)
    and that the parameter identifier code (e.g. 20000) is right-aligned to exactly
    the correct column index (width 10) without a single space of deviation.
    """
    dj_val = 0.00001567
    param_id = 20000

    compact_str = fortran_double_precision_formatter(dj_val, compact=True)
    assert "D-05" in compact_str
    assert "1.567" in compact_str
    assert "e" not in compact_str
    assert "E" not in compact_str

    line = fortran_double_precision_formatter(
        val_or_id=param_id,
        val=dj_val,
        uncertainty=1.0e-7,
        label="DJ",
        width=22,
        precision=15,
        compact=False,
    )

    assert line[:10] == "     20000", f"Expected '     20000', got '{line[:10]}'"
    assert "D-05" in line
    assert "D-07" in line
    assert "/ DJ" in line


def test_format_fortran_double_various_scales() -> None:
    """Verify Fortran Double Precision scientific string formatting across orders of magnitude."""
    assert format_fortran_double(0.0, compact=True) == "0.000D+00"
    assert "D+05" in format_fortran_double(825360.0, compact=True)
    assert "D-09" in format_fortran_double(1.234e-9, compact=True)
    assert "D+00" in format_fortran_double(1.0, compact=True)


# =============================================================================
# 5. Test Fortran Double Precision Overflow Guard
# =============================================================================


def test_fortran_overflow_guard_intercepts_unphysical_value() -> None:
    """Intentionally feed an unphysically massive parameter (1.5e310) representing a failed perturbation calculation.

    Assert that fortran_overflow_guard() intercepts the value before formatting,
    logs the critical error, and raises FortranOverflowError / blocks corrupted parameters.
    """
    corrupt_params = {
        "A": 825360.0,
        "B": 435360.0,
        "C": 278130.0,
        "DJ": 1.5e310,  # Exceeds IEEE 754 Double Precision limit (1e308)
    }

    with pytest.raises(FortranOverflowError) as exc_info:
        fortran_overflow_guard(corrupt_params)

    err = exc_info.value
    assert (
        err.error_code == ProvenanceErrorCode.FORTRAN_OVERFLOW
        or str(err.error_code) == "FORTRAN_OVERFLOW"
    )
    assert "DJ" in str(err.details.get("parameter", ""))
    val_str = str(err.details.get("value", "")).lower()
    assert "inf" in val_str or "310" in val_str or "1.5" in val_str


def test_fortran_overflow_guard_valid_dictionary() -> None:
    """Verify that physically realistic parameters pass the overflow guard untouched."""
    valid_params = {
        "A": 825360.0,
        "B": 435360.0,
        "C": 278130.0,
        "DJ": 1.567e-5,
        "DJK": -5.23e-5,
    }
    checked = fortran_overflow_guard(valid_params)
    assert checked["A"] == 825360.0
    assert checked["DJ"] == 1.567e-5


# =============================================================================
# 6. Test Partition Functions & Vibrational Partition Coupling
# =============================================================================


def test_exact_codata_2022_constants() -> None:
    """Validate exact CODATA 2022 constants used throughout the bridge."""
    assert CONSTANTS.H == 6.62607015e-34
    assert CONSTANTS.K_B == 1.380649e-23
    assert CONSTANTS.C_CM_S == 29979245800.0
    assert abs(CONSTANTS.C_ROT - 505379.008435) < 1e-4
    assert abs(CONSTANTS.HC_OVER_KB - 1.4387768775) < 1e-6


def test_rotational_partition_function_water() -> None:
    """Calculate rotational partition function Q_rot(T) for H2O at 298.15 K."""
    temp = 298.15
    q_rot = calculate_rotational_partition_function(
        a_mhz=H2O_A_MHZ,
        b_mhz=H2O_B_MHZ,
        c_mhz=H2O_C_MHZ,
        temp_k=temp,
        sigma=2.0,
    )
    # For H2O at 298.15 K with sigma=2, classical Q_rot ~ 43-45
    assert 40.0 < q_rot < 50.0


def test_vibrational_partition_coupling_drops_lam_frequency() -> None:
    """Verify vibrational_partition_coupling drops LAM frequency (< 50 cm^-1) when coupled with DVR.

    Demonstrates prevention of thermodynamic double-counting when DVR solves the low-frequency mode.
    """
    temps = [2.0, 10.0, 50.0, 298.15]
    all_freqs = [3100.0, 1500.0, 105.0, 24.5]  # Contains LAM mode 24.5 cm^-1
    lam_mode = 24.5

    # DVR rotational partition functions across temperature grid
    q_rot_dvr = {2.0: 1.05, 10.0: 4.8, 50.0: 35.2, 298.15: 185.0}

    # Coupled calculation with LAM mode dropped
    q_total_coupled = vibrational_partition_coupling(
        q_rot_dvr=q_rot_dvr,
        q_vib_orca=all_freqs,
        temp_array=temps,
        lam_frequency=lam_mode,
    )

    q_vib_with_lam = calculate_vibrational_partition_function(all_freqs, 298.15)
    q_vib_without_lam = calculate_vibrational_partition_function(
        all_freqs, 298.15, exclude_frequencies=[lam_mode]
    )

    assert q_vib_without_lam < q_vib_with_lam
    expected_q_total_298 = q_rot_dvr[298.15] * q_vib_without_lam
    assert math.isclose(q_total_coupled[298.15], expected_q_total_298, rel_tol=1e-6)


# =============================================================================
# 7. Test Pickett SPCAT .var and .int ASCII Generation
# =============================================================================


def test_generate_spcat_var_content(tmp_path: Path) -> None:
    """Verify complete Pickett SPCAT .var file formatting, parameter codes, and control cards."""
    var_file = tmp_path / "H2O.var"
    params = {
        "A": H2O_A_MHZ,
        "B": H2O_B_MHZ,
        "C": H2O_C_MHZ,
        "DJ": 1.567e-5,
    }

    content = generate_spcat_var(
        molecule_name="H2O",
        parameters=params,
        filepath=var_file,
    )

    assert var_file.exists()
    lines = content.strip().split("\n")
    assert len(lines) >= 6

    # Line 1: Header title
    assert "H2O Ground State - CoChem SPCAT Bridge" in lines[0]

    # Line 2: Control line (NPAR, NLINE, NOPT, NWARN, ERPAR, WTFAC, SCALE, MAXIT)
    control_parts = lines[1].split()
    assert control_parts[0] == "4"
    assert "D+00" in lines[1]

    # Parameter lines
    assert any("20000" in line and "D+05" in line for line in lines)
    assert any("200" in line and "1.567" in line and "D-05" in line for line in lines)


def test_generate_spcat_int_content(tmp_path: Path) -> None:
    """Verify complete Pickett SPCAT .int file generation with temperature as 9th parameter on Line 2."""
    temps = [2.0, 298.15]
    tpl = tmp_path / "H2O_{T}K.int"

    int_dict = generate_spcat_int(
        molecule_name="H2O",
        dipoles=H2O_DIPOLES,
        temperatures=temps,
        filepath_template=tpl,
    )

    assert 2.0 in int_dict
    assert 298.15 in int_dict

    f_298 = tmp_path / "H2O_298.1K.int"
    assert f_298.exists()

    content_298 = int_dict[298.15]
    lines = content_298.strip().split("\n")
    assert len(lines) == 5

    # Line 2: Control line with 298.15 as 9th parameter
    ctrl = lines[1].split()
    assert len(ctrl) == 9
    assert ctrl[8] == "298.15"

    # Line 3, 4, 5: Dipole moments
    assert "1" in lines[2] and "0.000000" in lines[2] and "/ mua" in lines[2]
    assert "2" in lines[3] and "1.854600" in lines[3] and "/ mub" in lines[3]
    assert "3" in lines[4] and "0.000000" in lines[4] and "/ muc" in lines[4]


# =============================================================================
# 8. Test Tripartite Air-Gap Compliance & Provenance Manifest
# =============================================================================


def test_tripartite_airgap_boundary_enforcement() -> None:
    """Assert validate_airgap_boundary blocks direct runtime writes to Ring 1 static repository root."""
    base_root = get_base_root().resolve()
    forbidden_target = base_root / "corrupt_scratch.tmp"

    with pytest.raises(AirGapViolationError) as exc_info:
        validate_airgap_boundary(forbidden_target)

    err = exc_info.value
    assert (
        err.error_code == ProvenanceErrorCode.AIRGAP_VIOLATION
        or str(err.error_code) == "AIRGAP_VIOLATION"
    )
    assert "Ring 1" in str(err.details.get("ring", "")) or "Air-Gap violation" in err.message


def test_build_complete_spcat_payload_end_to_end(tmp_path: Path) -> None:
    """Execute end-to-end payload synthesis for authentic H2O and verify complete bundle."""
    payload = build_complete_spcat_payload(
        molecule_name="H2O",
        geometry=H2O_GEOMETRY,
        symbols=H2O_SYMBOLS,
        rotational_constants_mhz={"A": H2O_A_MHZ, "B": H2O_B_MHZ, "C": H2O_C_MHZ},
        dipoles_debye=H2O_DIPOLES,
        harmonic_frequencies_cm1=H2O_HARMONIC_FREQUENCIES,
        temperatures=[2.0, 10.0, 50.0, 298.15],
        quartic_distortion=H2O_WATSON_A,
        output_dir=tmp_path,
    )

    assert isinstance(payload, SPCATPayload)
    assert payload.molecule_name == "H2O"
    assert (tmp_path / "H2O.var").exists()
    assert (tmp_path / "H2O_2.0K.int").exists()
    assert (tmp_path / "H2O_298.1K.int").exists()
    assert (tmp_path / "H2O_spcat_provenance.json").exists()

    prov_data = json.loads((tmp_path / "H2O_spcat_provenance.json").read_text(encoding="utf-8"))
    assert prov_data["stage"] == "Stage 5.1 (Statistical Mechanics & SPCAT Bridge)"
    assert prov_data["symmetry"]["point_group"] == "C2v"
    assert prov_data["symmetry"]["sigma"] == 2
    assert prov_data["symmetry"]["spin_weight_ratio_str"] == "3 1"
    assert prov_data["cryptographic_hashes"]["sha256_var"] == payload.sha256_var
    assert len(prov_data["partition_functions"]) == 4


def test_linear_rotor_partition_function() -> None:
    """Validate linear rotor partition function formula Q_rot = k_B * T / (sigma * h * B)."""
    # Carbon monoxide (CO, linear, B ~ 57635.968 MHz, sigma=1)
    b_co_mhz = 57635.968
    temp = 298.15
    q_rot_co = calculate_rotational_partition_function(
        a_mhz=0.0,
        b_mhz=b_co_mhz,
        c_mhz=b_co_mhz,
        temp_k=temp,
        sigma=1.0,
        is_linear=True,
    )
    # Expected: (k_B / (h * 1e6)) * 298.15 / 57635.968 ~ 107.78
    expected = (CONSTANTS.K_B / (CONSTANTS.H * 1e6)) * temp / b_co_mhz
    assert math.isclose(q_rot_co, expected, rel_tol=1e-6)
    assert 105.0 < q_rot_co < 110.0


def test_cochem_base_reexport_parity() -> None:
    """Verify that cochem_base.cochem_spcat_bridge re-exports all core functions and constants."""
    import cochem_base.cochem_spcat_bridge as csb

    assert hasattr(csb, "low_frequency_lam_trap")
    assert hasattr(csb, "low_frequency_trap")
    assert hasattr(csb, "apply_symmetry_divisors")
    assert hasattr(csb, "calculate_rotational_partition_function")
    assert hasattr(csb, "calculate_vibrational_partition_function")
    assert hasattr(csb, "vibrational_partition_coupling")
    assert hasattr(csb, "compute_coupled_partition_functions")
    assert hasattr(csb, "fortran_overflow_guard")
    assert hasattr(csb, "fortran_double_precision_formatter")
    assert hasattr(csb, "generate_spcat_var")
    assert hasattr(csb, "generate_spcat_int")
    assert hasattr(csb, "generate_spcat_provenance_manifest")
    assert hasattr(csb, "build_complete_spcat_payload")
    assert hasattr(csb, "route_3tier_abinitio_payload")
    assert csb.CONSTANTS.H == CONSTANTS.H
    assert csb.PLANCK_CONSTANT_JS == CONSTANTS.H
    assert csb.BOLTZMANN_CONSTANT_JK == CONSTANTS.K_B
    assert csb.SPEED_OF_LIGHT_CMS == CONSTANTS.C_CM_S
    assert csb.C_ROT == CONSTANTS.C_ROT


def test_low_frequency_trap_alias() -> None:
    """Verify low_frequency_trap is a direct alias of low_frequency_lam_trap."""
    assert low_frequency_trap is low_frequency_lam_trap
    stiff = low_frequency_trap([100.0, 500.0, 1000.0])
    assert stiff == [100.0, 500.0, 1000.0]

    with pytest.raises(LAMTriggerError) as exc_info:
        low_frequency_trap([49.9, 1000.0])
    assert exc_info.value.error_code == ProvenanceErrorCode.LAM_TRIGGER


def test_vibrational_partition_coupling_gradient_forms() -> None:
    """Verify vibrational_partition_coupling with callable, dict, and sequence q_rot_dvr across T gradient."""
    temps = [5.0, 50.0, 150.0, 300.0]
    freqs = [1595.0, 3657.0, 3756.0]

    # Form 1: Callable q_rot_dvr
    def dvr_func(t: float) -> float:
        return float(0.5 * (t**1.5))

    res_callable = vibrational_partition_coupling(dvr_func, freqs, temps)
    assert len(res_callable) == 4
    for t in temps:
        expected_rot = dvr_func(t)
        expected_vib = calculate_vibrational_partition_function(freqs, t)
        assert math.isclose(res_callable[t], expected_rot * expected_vib, rel_tol=1e-6)

    # Form 2: Sequence q_rot_dvr
    rot_seq = [dvr_func(t) for t in temps]
    res_seq = vibrational_partition_coupling(rot_seq, freqs, temps)
    for t in temps:
        assert math.isclose(res_seq[t], res_callable[t], rel_tol=1e-6)


def test_route_3tier_abinitio_payload_hierarchy() -> None:
    """Verify 3-Tier Ab Initio Routing Protocol prioritizes MPQC primary and ORCA for analytic VPT2."""
    mpqc_payload = {
        "energy_hartree": -76.438512,
        "frequencies": [1600.0, 3660.0, 3760.0],
        "dipoles": {"mu_a": 0.0, "mu_b": 1.85, "mu_c": 0.0},
    }
    orca_payload = {
        "energy_hartree": -76.425000,
        "frequencies": [1595.0, 3655.0, 3755.0],
        "dipoles": {"mu_a": 0.0, "mu_b": 1.85, "mu_c": 0.0},
        "x_matrix": [[-15.0, -5.0, -2.0], [-5.0, -40.0, -10.0], [-2.0, -10.0, -45.0]],
    }
    cfour_payload = {
        "energy_hartree": -76.410000,
        "frequencies": [1590.0, 3650.0, 3750.0],
        "dipoles": {"mu_a": 0.0, "mu_b": 1.84, "mu_c": 0.0},
    }

    # Tier 1 selected when standard energy benchmark
    res_t1 = route_3tier_abinitio_payload(mpqc_data=mpqc_payload, orca_data=orca_payload)
    assert res_t1.selected_tier == 1
    assert res_t1.primary_engine == "MPQC"
    assert res_t1.electronic_energy_hartree == -76.438512

    # Tier 2 selected when analytic VPT2 is strictly required
    res_t2 = route_3tier_abinitio_payload(
        mpqc_data=mpqc_payload, orca_data=orca_payload, require_analytic_vpt2=True
    )
    assert res_t2.selected_tier == 2
    assert res_t2.primary_engine == "ORCA"
    assert res_t2.is_analytic_vpt2_active is True
    assert res_t2.vpt2_x_matrix is not None

    # Tier 3 selected when only CFOUR is available
    res_t3 = route_3tier_abinitio_payload(cfour_data=cfour_payload)
    assert res_t3.selected_tier == 3
    assert res_t3.primary_engine == "CFOUR"


def test_fortran_overflow_guard_clamp_mode() -> None:
    """Verify fortran_overflow_guard clamp mode for arrays and scalars."""
    unphysical_arr = np.array([1.0, 1.5e310, -2.0e310])
    clamped_arr = fortran_overflow_guard(unphysical_arr, max_limit=1e308, clamp_on_overflow=True)
    assert clamped_arr[0] == 1.0
    assert clamped_arr[1] == 1e308
    assert clamped_arr[2] == -1e308

    clamped_scalar = fortran_overflow_guard(5e315, max_limit=1e308, clamp_on_overflow=True)
    assert clamped_scalar == 1e308


def test_molsym_symmetry_ethylene_d2h() -> None:
    """Verify point group detection and rotational symmetry divisor for Ethylene (C2H4, D2h, sigma=4)."""
    # Planar Ethylene (C2H4) geometry in Angstroms
    c2h4_coords = np.array(
        [
            [0.0000, 0.0000, 0.6695],  # C1
            [0.0000, 0.0000, -0.6695],  # C2
            [0.0000, 0.9289, 1.2321],  # H1
            [0.0000, -0.9289, 1.2321],  # H2
            [0.0000, 0.9289, -1.2321],  # H3
            [0.0000, -0.9289, -1.2321],  # H4
        ],
        dtype=float,
    )
    c2h4_symbols = ["C", "C", "H", "H", "H", "H"]

    res = apply_symmetry_divisors(c2h4_coords, c2h4_symbols)
    assert res.point_group in ("D2h", "D2")
    assert res.sigma == 4


def test_compute_coupled_partition_functions_dataclass() -> None:
    """Verify compute_coupled_partition_functions populates PartitionFunctionResult structure cleanly."""
    res = compute_coupled_partition_functions(
        a_mhz=H2O_A_MHZ,
        b_mhz=H2O_B_MHZ,
        c_mhz=H2O_C_MHZ,
        frequencies_cm1=[1594.75, 3657.05, 3755.93, 30.0],
        temp_array=[10.0, 100.0, 298.15],
        sigma=2.0,
        lam_frequency=30.0,
        is_dvr=True,
    )
    assert isinstance(res, PartitionFunctionResult)
    assert res.is_dvr_coupled is True
    assert 30.0 in res.dropped_lam_frequencies
    assert len(res.stiff_frequencies) == 3
    assert len(res.temperatures) == 3
    assert res.q_total[298.15] == res.q_rot[298.15] * res.q_vib[298.15]
    as_d = res.to_dict()
    assert "q_total" in as_d


def test_torq_spcat_bridge_lifecycle(tmp_path: Path) -> None:
    """Verify TorqSpcatBridge class initialization, parsing, partition functions, and export."""
    tensor_data = {
        "point_id": "001",
        "is_linear": False,
        "symbols": ["O", "H", "H"],
        "coordinates": H2O_GEOMETRY.tolist(),
        "tensors": {
            "rotational_constants_MHz": {
                "A": H2O_A_MHZ,
                "B": H2O_B_MHZ,
                "C": H2O_C_MHZ,
            }
        },
    }
    tensor_file = tmp_path / "tensor.json"
    tensor_file.write_text(json.dumps(tensor_data), encoding="utf-8")

    mpqc_content = (
        "Total Dipole Moment : 0.0000 1.8546 0.0000\n\n"
        "VIBRATIONAL FREQUENCIES\n"
        "-----------------------\n"
        "  1: 1594.75 cm**-1\n"
        "  2: 3657.05 cm**-1\n"
        "  3: 3755.93 cm**-1\n"
    )
    mpqc_file = tmp_path / "mpqc.out"
    mpqc_file.write_text(mpqc_content, encoding="utf-8")

    bridge = TorqSpcatBridge(tensor_file, mpqc_file, temperature_k=298.15)
    assert bridge.point_id == "001"
    assert bridge.sigma == 2
    assert bridge.rot_A_MHz == H2O_A_MHZ

    bridge.parse_mpqc_observables()
    assert len(bridge.frequencies_cm1) == 3
    assert bridge.dipole_moments["b"] == 1.8546

    q_rot, q_vib, q_total = bridge.calculate_partition_functions()
    assert 40.0 < q_rot < 50.0
    assert q_vib >= 1.0
    assert q_total == q_rot * q_vib
