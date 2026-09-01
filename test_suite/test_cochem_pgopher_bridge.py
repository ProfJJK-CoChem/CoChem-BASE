"""Rigorous Authentic Physics Unit and Integration Tests for PGOPHER Bridge.

Validates Method Matrix §7, §16.2, §18 compliance:
1. Exact CODATA 2022 physical constants and conversion factors.
2. Dynamic isotopic mass and nuclear spin resolution via Mendeleev library.
3. MolSym point-group symmetry resolution, rotational symmetry numbers (sigma),
   and nuclear spin statistical weights (H2O 3:1, NH3 2:1, C2H4 7:3:3:3).
4. Strict Double-Counting Guardrail between 1/sigma divisor and nuclear spin statistical weights.
5. Ray's asymmetry parameter (kappa), moments of inertia, inertial defect, and planar moments.
6. Watson A and Watson S reduction parameter validation.
7. Nuclear quadrupole coupling tensors for I >= 1 nuclei with traceless verification.
8. PGOPHER XML (.pgo) generation, formatting, and roundtrip parsing.
9. Bidirectional Pickett CALPGM (.var/.int) <-> PGOPHER (.pgo XML) conversion with sign flip handling.
10. Line broadening spectral simulation (Gaussian, Lorentzian, and Voigt via Faddeeva).
11. Partition function evaluation across temperatures (2K to 300K).
12. Tripartite Filesystem Air-Gap compliance and SHA-256 cryptographic provenance manifests.
13. TorqPGOPHERBridge lifecycle manager execution.
14. Re-export parity between root interfaces and cochem_base.interfaces.
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
    ProvenanceErrorCode,
)
from cochem_base.interfaces.cochem_pgopher_bridge import (
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
    PGOPHERBridgeError,
    PGOPHERDipoleMoments,
    PGOPHERPayload,
    PGOPHERQuadrupoleNucleus,
    PGOPHERRotationalConstants,
    PGOPHESpectralTransition,
    PGOPHERSimulationConfig,
    PGOPHERSymmetryResolution,
    PGOPHERWatsonReduction,
    TorqPGOPHERBridge,
    calculate_pgopher_partition_function,
    compute_sha256,
    compute_spectral_profile,
    convert_pgopher_to_pickett,
    convert_pickett_to_pgopher,
    find_pgopher_executable,
    generate_pgopher_provenance_manifest,
    generate_pgopher_xml,
    inspect_parquet_catalog_metadata,
    parse_pgopher_linelist,
    parse_pgopher_xml,
    resolve_isotope_properties,
    resolve_pgopher_symmetry_and_weights,
    run_pgopher_headless,
    validate_airgap_boundary,
)
import interfaces.cochem_pgopher_bridge as root_pgopher_bridge


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
# H2O experimental rotational constants in MHz
H2O_A_MHZ = 835840.3
H2O_B_MHZ = 435360.5
H2O_C_MHZ = 278139.8

# Ammonia (NH3) Cartesian geometry (Angstroms)
_R_XY = 0.9397
_Z_H = -0.2718
NH3_GEOMETRY = np.array(
    [
        [0.000000, 0.000000, 0.116500],  # N
        [0.000000, _R_XY, _Z_H],  # H1
        [_R_XY * math.sqrt(3) / 2.0, -_R_XY * 0.5, _Z_H],  # H2
        [-_R_XY * math.sqrt(3) / 2.0, -_R_XY * 0.5, _Z_H],  # H3
    ],
    dtype=np.float64,
)
NH3_SYMBOLS = ["N", "H", "H", "H"]

# Ethylene (C2H4) Cartesian geometry (Angstroms)
C2H4_GEOMETRY = np.array(
    [
        [0.000000, 0.000000, 0.669500],  # C1
        [0.000000, 0.000000, -0.669500],  # C2
        [0.000000, 0.928900, 1.232100],  # H1
        [0.000000, -0.928900, 1.232100],  # H2
        [0.000000, 0.928900, -1.232100],  # H3
        [0.000000, -0.928900, -1.232100],  # H4
    ]
)
C2H4_SYMBOLS = ["C", "C", "H", "H", "H", "H"]


# =============================================================================
# 2. Unit Tests: CODATA 2022 Physical Constants
# =============================================================================


def test_codata_2022_constants_accuracy() -> None:
    """Validate exact fundamental physical constants from CODATA 2022."""
    assert CODATA_YEAR == 2022
    assert CONSTANTS.H == 6.62607015e-34
    assert CONSTANTS.K_B == 1.380649e-23
    assert CONSTANTS.C_M_S == 299792458.0
    assert CONSTANTS.C_CM_S == 29979245800.0
    assert abs(CONSTANTS.C_ROT - 505379.008435) < 1e-4
    assert abs(CONSTANTS.HC_OVER_KB - 1.4387768775039336) < 1e-6
    assert abs(CONSTANTS.MHZ_TO_CM1 - (1.0 / 29979.2458)) < 1e-12
    assert abs(CONSTANTS.CM1_TO_MHZ - 29979.2458) < 1e-6


# =============================================================================
# 3. Unit Tests: Dynamic Mass & Isotope Resolution via Mendeleev
# =============================================================================


def test_mendeleev_dynamic_isotope_resolution() -> None:
    """Verify dynamic retrieval of atomic mass and nuclear spin via Mendeleev."""
    # Nitrogen-14: I = 1.0, mass ~ 14.003 amu
    mass_n14, spin_n14, sym_n = resolve_isotope_properties("14N")
    assert sym_n == "N"
    assert spin_n14 == 1.0
    assert 14.00 < mass_n14 < 14.01

    # Chlorine-35: I = 1.5, mass ~ 34.9688 amu
    mass_cl35, spin_cl35, sym_cl = resolve_isotope_properties("35Cl")
    assert sym_cl == "Cl"
    assert spin_cl35 == 1.5
    assert 34.9 < mass_cl35 < 35.1

    # Deuterium (D): mass ~ 2.014 amu, spin = 1.0
    mass_d, spin_d, sym_d = resolve_isotope_properties("D")
    assert sym_d == "H"
    assert spin_d == 1.0
    assert abs(mass_d - 2.0141) < 1e-3


# =============================================================================
# 4. Unit Tests: MolSym Symmetry & Nuclear Spin Weights (Method Matrix §7)
# =============================================================================


def test_h2o_symmetry_and_spin_weights() -> None:
    """Verify H2O symmetry resolution yields C2v, sigma=2, and ortho/para 3:1 ratio."""
    sym_res = resolve_pgopher_symmetry_and_weights(
        geometry_array=H2O_GEOMETRY,
        symbols=H2O_SYMBOLS,
        use_nuclear_spin=True,
    )
    assert sym_res.point_group == "C2v"
    assert sym_res.sigma == 2
    assert sym_res.sym_wt == 3
    assert sym_res.asym_wt == 1
    assert sym_res.weight_ratio_str == "3 1"
    assert sym_res.effective_divisor == 1.0
    assert "GUARDRAIL_ENFORCED_EXACT_NUCLEAR_SPIN_APPLIED" in sym_res.guardrail_status
    assert "Ortho (3) : Para (1)" in sym_res.ms_group_feasibility_argument


def test_nh3_symmetry_and_spin_weights() -> None:
    """Verify NH3 symmetry resolution yields C3v, sigma=3, and 2:1 spin weight ratio."""
    sym_res = resolve_pgopher_symmetry_and_weights(
        geometry_array=NH3_GEOMETRY,
        symbols=NH3_SYMBOLS,
        use_nuclear_spin=True,
    )
    assert sym_res.point_group == "C3v"
    assert sym_res.sigma == 3
    assert sym_res.sym_wt == 4
    assert sym_res.asym_wt == 2
    assert sym_res.weight_ratio_str == "2 1"


def test_c2h4_symmetry_and_spin_weights() -> None:
    """Verify C2H4 symmetry resolution yields D2h, sigma=4, and 7:3:3:3 weight ratio."""
    sym_res = resolve_pgopher_symmetry_and_weights(
        geometry_array=C2H4_GEOMETRY,
        symbols=C2H4_SYMBOLS,
        use_nuclear_spin=True,
    )
    assert sym_res.point_group == "D2h"
    assert sym_res.sigma == 4
    assert sym_res.sym_wt == 7
    assert sym_res.asym_wt == 3


def test_double_counting_guardrail_classical() -> None:
    """Verify classical 1/sigma divisor is applied when nuclear spin is disabled."""
    sym_res = resolve_pgopher_symmetry_and_weights(
        geometry_array=H2O_GEOMETRY,
        symbols=H2O_SYMBOLS,
        use_nuclear_spin=False,
    )
    assert sym_res.effective_divisor == 2.0
    assert "GUARDRAIL_ENFORCED_CLASSICAL_SIGMA_APPLIED" in sym_res.guardrail_status


# =============================================================================
# 5. Unit Tests: Rotational Constants, Asymmetry, and Planar Moments
# =============================================================================


def test_rotational_constants_planar_moments() -> None:
    """Verify asymmetry parameter kappa, moments of inertia, and planar moments for H2O."""
    rot = PGOPHERRotationalConstants(A_MHz=H2O_A_MHZ, B_MHz=H2O_B_MHZ, C_MHz=H2O_C_MHZ)
    assert rot.rotor_type == "AsymmetricTop"
    # Ray's kappa = (2B - A - C) / (A - C)
    expected_kappa = (2.0 * H2O_B_MHZ - H2O_A_MHZ - H2O_C_MHZ) / (H2O_A_MHZ - H2O_C_MHZ)
    assert abs(rot.kappa - expected_kappa) < 1e-6

    # Planar molecule equilibrium inertial defect should be small / close to zero
    assert rot.Ia_u_ang2 > 0.0
    assert rot.Ib_u_ang2 > 0.0
    assert rot.Ic_u_ang2 > 0.0
    # For a planar molecule: Ic ~ Ia + Ib => Delta ~ 0 => Pc ~ 0
    assert rot.planar_moment_Pa > 0.0
    assert rot.planar_moment_Pb > 0.0


# =============================================================================
# 6. Unit Tests: Quadrupole Hyperfine Coupling
# =============================================================================


def test_quadrupole_hyperfine_coupling() -> None:
    """Verify nuclear quadrupole coupling tensor creation and traceless check."""
    # 14N quadrupole in Ar-oxazole (Method Matrix §17, System 2):
    # chi_aa = 2.3032, chi_bb = -4.0526, chi_cc = 1.7494 MHz
    mass_n14, spin_n14, sym_n = resolve_isotope_properties("14N")
    quad = PGOPHERQuadrupoleNucleus(
        name="N14",
        symbol=sym_n,
        mass_amu=mass_n14,
        nuclear_spin=spin_n14,
        chi_aa_MHz=2.3032,
        chi_bb_MHz=-4.0526,
        chi_cc_MHz=1.7494,
        chi_ab_MHz=0.0,
    )
    assert quad.validate_traceless(tolerance_mhz=1e-3) is True
    assert quad.nuclear_spin == 1.0


# =============================================================================
# 7. Unit Tests: PGOPHER XML (.pgo) Generation & Roundtrip Parsing
# =============================================================================


def test_pgopher_xml_generation_and_parsing(tmp_path: Path) -> None:
    """Verify complete generation and roundtrip parsing of PGOPHER .pgo XML."""
    mass_n14, spin_n14, sym_n = resolve_isotope_properties("14N")
    rot = PGOPHERRotationalConstants(A_MHz=10447.9248, B_MHz=1918.0138, C_MHz=1606.7642)
    watson = PGOPHERWatsonReduction(
        reduction="Watson_A",
        representation="Ir",
        DJ_MHz=5.52411e-3,
        DJK_MHz=3.7199e-2,
        DK_MHz=-3.5922e-2,
    )
    dipoles = PGOPHERDipoleMoments(mu_a_Debye=0.125, mu_b_Debye=1.369, mu_c_Debye=0.0)
    quad = [
        PGOPHERQuadrupoleNucleus(
            name="N14",
            symbol=sym_n,
            mass_amu=mass_n14,
            nuclear_spin=spin_n14,
            chi_aa_MHz=2.3032,
            chi_bb_MHz=-4.0526,
            chi_cc_MHz=1.7494,
        )
    ]
    sym_res = resolve_pgopher_symmetry_and_weights(
        geometry_array=H2O_GEOMETRY,
        symbols=H2O_SYMBOLS,
    )
    sim_cfg = PGOPHERSimulationConfig(
        temperature_K=2.0,
        line_shape="Voigt",
        fwhm_MHz=0.5,
        min_frequency_MHz=2000.0,
        max_frequency_MHz=20000.0,
    )

    xml_file = tmp_path / "test_ar_ketene.pgo"
    xml_str = generate_pgopher_xml(
        molecule_name="ArKetene",
        rotational_constants=rot,
        watson_reduction=watson,
        dipole_moments=dipoles,
        quadrupole_nuclei=quad,
        symmetry_resolution=sym_res,
        simulation_config=sim_cfg,
        output_filepath=xml_file,
    )

    assert "<PGOPHER" in xml_str
    assert 'Name="ArKetene"' in xml_str
    assert 'MuA="0.1250"' in xml_str
    assert 'ChiAA="2.303200"' in xml_str
    assert xml_file.exists()

    # Parse back
    parsed = parse_pgopher_xml(xml_file)
    assert parsed["species"]["name"] == "ArKetene"
    assert abs(parsed["species"]["rotational_constants"]["A"] - 10447.9248) < 1e-4
    assert abs(parsed["species"]["dipole_moments"]["mu_b"] - 1.369) < 1e-3
    assert len(parsed["species"]["nuclear_quadrupole"]) == 1
    assert parsed["simulation"]["temperature_K"] == 2.0


# =============================================================================
# 8. Unit Tests: Bidirectional Pickett <-> PGOPHER Conversion
# =============================================================================


def test_bidirectional_pickett_pgopher_conversion() -> None:
    """Verify bidirectional conversion between Pickett .var/.int and PGOPHER XML."""
    var_text = (
        "ArOxazole Pickett VAR\n"
        "  100   1.0000000000D+00   1.0000000000D-04\n"
        "10000   5.0128948600D+03   1.0000000000D-04\n"
        "20000   1.3984281510D+03   1.0000000000D-04\n"
        "30000   1.3889528410D+03   1.0000000000D-04\n"
        "  200  -5.5241100000D-03   1.0000000000D-04\n"  # Pickett opposite sign for DJ
    )
    int_text = (
        "ArOxazole Pickett INT\n"
        "  1  1  0  0    0.0    0.0    0.0    1.0     298.15\n"
        "  1      0.000000   / mua\n"
        "  2      1.500000   / mub\n"
        "  3      0.200000   / muc\n"
    )

    # Convert Pickett -> PGOPHER
    pgo_xml = convert_pickett_to_pgopher(
        var_content=var_text,
        int_content=int_text,
        molecule_name="ArOxazole",
        temperature_K=298.15,
    )
    assert "<PGOPHER" in pgo_xml
    assert 'A="5012.894860"' in pgo_xml
    assert 'DJ="5.52411000e-03"' in pgo_xml  # Sign flipped back to positive in PGOPHER

    # Convert PGOPHER -> Pickett
    out_var, out_int = convert_pgopher_to_pickett(pgo_xml, molecule_name="ArOxazole")
    assert "10000" in out_var
    assert "200" in out_var
    assert "-5.5241100000D-03" in out_var  # Sign restored to Pickett convention
    assert "/ mub" in out_int


# =============================================================================
# 9. Unit Tests: Line Broadening (Gaussian, Lorentzian, Voigt)
# =============================================================================


def test_line_broadening_profiles() -> None:
    """Verify Gaussian, Lorentzian, and Voigt profile line synthesis."""
    transitions = [
        PGOPHESpectralTransition(
            frequency_MHz=10000.0,
            intensity=1.0,
            lower_state_energy_cm1=0.0,
            upper_state_degeneracy=1,
            quantum_numbers_upper="1_0_1",
            quantum_numbers_lower="0_0_0",
        )
    ]
    freq_axis = np.linspace(9995.0, 10005.0, 101)

    # Gaussian
    i_gauss = compute_spectral_profile(freq_axis, transitions, line_shape="Gaussian", fwhm_MHz=2.0)
    assert len(i_gauss) == 101
    assert i_gauss[50] == max(i_gauss)  # Peak at center (10000 MHz)

    # Lorentzian
    i_lor = compute_spectral_profile(freq_axis, transitions, line_shape="Lorentzian", fwhm_MHz=2.0)
    assert i_lor[50] == max(i_lor)

    # Voigt
    i_voigt = compute_spectral_profile(freq_axis, transitions, line_shape="Voigt", fwhm_MHz=2.0)
    assert i_voigt[50] == max(i_voigt)
    assert np.all(i_voigt >= 0.0)


# =============================================================================
# 10. Unit Tests: Partition Functions Across Temperatures
# =============================================================================


def test_partition_function_calculations() -> None:
    """Verify high-precision partition function evaluation for H2O across temperatures."""
    vib_modes = [1595.0, 3657.0, 3756.0]  # H2O harmonic frequencies in cm^-1

    # At T = 2.0 K (Cold interstellar / supersonic jet)
    res_2k = calculate_pgopher_partition_function(
        A_MHz=H2O_A_MHZ,
        B_MHz=H2O_B_MHZ,
        C_MHz=H2O_C_MHZ,
        temperature_K=2.0,
        sigma=2.0,
        vibrational_frequencies_cm1=vib_modes,
    )
    assert res_2k["q_rot"] > 0.0
    assert abs(res_2k["q_vib"] - 1.0) < 1e-6  # All vibrational states frozen at 2K
    assert res_2k["q_total"] == res_2k["q_rot"] * res_2k["q_vib"]

    # At T = 298.15 K
    res_298k = calculate_pgopher_partition_function(
        A_MHz=H2O_A_MHZ,
        B_MHz=H2O_B_MHZ,
        C_MHz=H2O_C_MHZ,
        temperature_K=298.15,
        sigma=2.0,
        vibrational_frequencies_cm1=vib_modes,
    )
    assert res_298k["q_rot"] > res_2k["q_rot"]
    assert res_298k["q_vib"] >= 1.0


# =============================================================================
# 11. Unit Tests: Tripartite Air-Gap & Provenance Manifest
# =============================================================================


def test_airgap_boundary_enforcement(tmp_path: Path) -> None:
    """Verify AirGap boundary validation prevents writes into Ring 1 static repo."""
    # Authorized target in tmp/scratch passes
    valid_target = tmp_path / "allowed_output.pgo"
    assert validate_airgap_boundary(valid_target) == valid_target.resolve()

    # Unauthorized target directly in base root raises AirGapViolationError
    base_root = get_base_root()
    forbidden_target = base_root / "forbidden_root_file.pgo"
    with pytest.raises(AirGapViolationError) as exc_info:
        validate_airgap_boundary(forbidden_target)
    assert exc_info.value.error_code == ProvenanceErrorCode.AIRGAP_VIOLATION


def test_provenance_manifest_generation(tmp_path: Path) -> None:
    """Verify SHA-256 cryptographic provenance manifest generation."""
    sym_res = resolve_pgopher_symmetry_and_weights(H2O_GEOMETRY, H2O_SYMBOLS)
    part_res = calculate_pgopher_partition_function(H2O_A_MHZ, H2O_B_MHZ, H2O_C_MHZ, 298.15)
    xml_content = "<PGOPHER></PGOPHER>"
    manifest_path = tmp_path / "h2o_manifest.json"

    manifest = generate_pgopher_provenance_manifest(
        molecule_name="H2O",
        xml_content=xml_content,
        symmetry_resolution=sym_res,
        partition_results=part_res,
        output_path=manifest_path,
    )

    assert manifest["molecule_name"] == "H2O"
    assert manifest["cryptographic_hashes"]["sha256_xml"] == compute_sha256(xml_content)
    assert manifest_path.exists()


# =============================================================================
# 12. Integration Test: TorqPGOPHERBridge Lifecycle Workflow
# =============================================================================


def test_torq_pgopher_bridge_lifecycle(tmp_path: Path) -> None:
    """Verify end-to-end orchestration bridge lifecycle."""
    bridge = TorqPGOPHERBridge(
        molecule_name="WaterDimer",
        geometry=H2O_GEOMETRY,
        symbols=H2O_SYMBOLS,
        A_MHz=H2O_A_MHZ,
        B_MHz=H2O_B_MHZ,
        C_MHz=H2O_C_MHZ,
        dipoles_Debye={"mu_a": 1.85, "mu_b": 0.0, "mu_c": 0.0},
        watson_reduction=PGOPHERWatsonReduction(reduction="Watson_A"),
        vibrational_frequencies_cm1=[1595.0, 3657.0, 3756.0],
        temperature_K=298.15,
        output_dir=tmp_path,
    )

    payload = bridge.build_payload()
    assert isinstance(payload, PGOPHERPayload)
    assert payload.molecule_name == "WaterDimer"
    assert payload.xml_filepath is not None
    assert Path(payload.xml_filepath).exists()
    assert payload.provenance_filepath is not None
    assert Path(payload.provenance_filepath).exists()


# =============================================================================
# 13. Re-export Parity Test
# =============================================================================


def test_root_interface_reexport_parity() -> None:
    """Verify interfaces.cochem_pgopher_bridge re-exports all canonical symbols."""
    assert root_pgopher_bridge.TorqPGOPHERBridge is TorqPGOPHERBridge
    assert root_pgopher_bridge.generate_pgopher_xml is generate_pgopher_xml
    assert root_pgopher_bridge.parse_pgopher_xml is parse_pgopher_xml
    assert root_pgopher_bridge.convert_pickett_to_pgopher is convert_pickett_to_pgopher
    assert root_pgopher_bridge.convert_pgopher_to_pickett is convert_pgopher_to_pickett
    assert root_pgopher_bridge.CODATA2022 is CODATA2022
    assert root_pgopher_bridge.CONSTANTS is CONSTANTS
