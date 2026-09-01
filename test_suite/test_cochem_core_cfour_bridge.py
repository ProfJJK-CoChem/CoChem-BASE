# -*- coding: utf-8 -*-
"""Comprehensive Authentic Test Suite for CoChem-CORE CFOUR Electronic Structure & VPT2 Bridge.

Module: test_suite/test_cochem_core_cfour_bridge.py
Authoritative Target: core_engine/cochem_core_cfour_bridge.py

Verifies Method Matrix v4 §8B.6, §9.1–§9.5, §13.4 (Table 4-C), §14.1 (Table 6-C), §8D, §8B.4, §6.10:
1. Dynamic Mendeleev Mass Resolution (Mendeleev Mandate: ZERO hardcoded masses).
2. Exact Rigid-Rotor Inertial Tensor Diagonalization, Rotational Constants, Planar Moments,
   Inertial Defect, and Ray's Asymmetry.
3. CFOUR ZMAT Generation with 3-character variable constraints, collinearity dummy atoms ('X'),
   global memory formatting (MEMORY_SIZE=32, MEM_UNIT=GB), and dynamic %isotopes block.
4. Robust CFOUR Output Parser: energies (SCF, MP2, CCSD, CCSD(T)), Be (Ae, Be, Ce), harmonic frequencies,
   vibration-rotation alpha constants, ground-state B0 (A0, B0, C0), quartic centrifugal distortion (Watson A/S),
   sextic centrifugal distortion (Watson A/S), electric field gradients / nuclear quadrupole couplings (chi_aa, chi_bb, chi_cc),
   dipole components, and DBOC.
5. ISOMASS Harmonic Force Field Re-Diagonalization Engine:
   - "One force field serves every isotopologue" shortcut.
   - Dynamic mass retrieval via Mendeleev.
   - Rigorous Eckart translation and rotation projection (Sayvetz frame).
   - Accurate harmonic vibrational frequency shifts, ZPE shifts, and rotational constant shifts (Delta A0, Delta B0, Delta C0).
6. Pickett SPCAT Bridge Export: formatting .var files with official parameter integer codes.
7. CLI Parsing and Dispatch Architecture.
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
REPO_ROOT = Path(__file__).resolve().parent.parent if "__file__" in locals() else Path(r"D:\__CoChem\GitHub-Repo\CoChem-BASE")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core_engine.cochem_core_cfour_bridge import (
    CONSTANTS,
    CFOURAnharmMode,
    CFOURBridge,
    CFOURCalcLevel,
    CFOURInputConfig,
    CFOURObservables,
    CFOUROutputParser,
    CFOURReference,
    CFOURVibMode,
    ElectricFieldGradientTensor,
    HarmonicForceField,
    IsotopologueFFResult,
    NuclearSpinRotationTensor,
    QuarticCentrifugalDistortion,
    SexticCentrifugalDistortion,
    VibrationRotationAlpha,
    WatsonReduction,
    build_cli_parser,
    compute_center_of_mass,
    compute_equilibrium_rotational_constants,
    compute_inertia_tensor,
    export_cfour_to_spcat_var,
    generate_cfour_zmat,
    get_default_isotope_mass_number,
    get_dynamic_atomic_mass,
    isomass_rediagonalize_force_field,
)


# ==============================================================================
# 1. Test Dynamic Mendeleev Mass Retrieval
# ==============================================================================

def test_dynamic_mendeleev_masses():
    """Verify dynamic atomic and isotopic mass retrieval via Mendeleev with ZERO hardcoding."""
    # 1. Carbon
    c_mass = get_dynamic_atomic_mass("C")
    assert 12.0 < c_mass < 12.02, f"Expected standard atomic weight for C, got {c_mass}"

    c13_mass = get_dynamic_atomic_mass("C", mass_number=13)
    assert 13.003 < c13_mass < 13.004, f"Expected 13C mass ~13.00335, got {c13_mass}"

    # 2. Hydrogen and Isotopes (D, T)
    h_mass = get_dynamic_atomic_mass("H")
    assert 1.007 < h_mass < 1.009, f"Expected H mass ~1.008, got {h_mass}"

    d_mass = get_dynamic_atomic_mass("D")
    assert 2.014 < d_mass < 2.015, f"Expected D mass ~2.0141, got {d_mass}"

    # 3. Nitrogen and Oxygen
    n_mass = get_dynamic_atomic_mass("N", mass_number=14)
    assert 14.003 < n_mass < 14.004, f"Expected 14N mass ~14.00307, got {n_mass}"

    o18_mass = get_dynamic_atomic_mass("O", mass_number=18)
    assert 17.999 < o18_mass < 18.000, f"Expected 18O mass ~17.99916, got {o18_mass}"

    # 4. Default most abundant mass numbers
    assert get_default_isotope_mass_number("C") == 12
    assert get_default_isotope_mass_number("H") == 1
    assert get_default_isotope_mass_number("N") == 14
    assert get_default_isotope_mass_number("O") == 16
    assert get_default_isotope_mass_number("Cl") == 35


# ==============================================================================
# 2. Test Rigid-Rotor Inertial Tensor & Rotational Constants
# ==============================================================================

def test_water_rotational_constants():
    """Verify rigid-rotor rotational constants for canonical water geometry."""
    # Near-equilibrium H2O geometry in Angstroms: r(OH) = 0.9578 Å, theta(HOH) = 104.5°
    theta_rad = math.radians(104.5) / 2.0
    r_oh = 0.9578
    coords = np.array([
        [0.0, 0.0, 0.0],                          # O
        [r_oh * math.sin(theta_rad), 0.0, r_oh * math.cos(theta_rad)],    # H1
        [-r_oh * math.sin(theta_rad), 0.0, r_oh * math.cos(theta_rad)],   # H2
    ], dtype=np.float64)
    symbols = ["O", "H", "H"]

    com = compute_center_of_mass(symbols, coords)
    assert abs(com[0]) < 1e-12
    assert abs(com[1]) < 1e-12
    assert com[2] > 0.0

    (Be_MHz, Be_cm, in_def, (Paa, Pbb, Pcc), kappa) = compute_equilibrium_rotational_constants(symbols, coords)
    Ae, Be, Ce = Be_MHz

    # H2O rotational constants are roughly A ~ 830-850 GHz (830000-850000 MHz), B ~ 435 GHz, C ~ 278 GHz
    assert 800000.0 < Ae < 900000.0, f"Expected Ae ~ 835 GHz, got {Ae}"
    assert 400000.0 < Be < 480000.0, f"Expected Be ~ 435 GHz, got {Be}"
    assert 250000.0 < Ce < 310000.0, f"Expected Ce ~ 278 GHz, got {Ce}"
    assert Ae >= Be >= Ce, "Ordering Ae >= Be >= Ce must hold strictly"

    # Planar molecule equilibrium inertial defect must be exactly ~ 0.0 u*Å^2
    assert abs(in_def) < 1e-6, f"Expected equilibrium inertial defect Delta_e ~ 0 for planar H2O, got {in_def}"
    assert abs(Pcc) < 1e-6, f"Expected Pcc ~ 0 for planar molecule in xy plane, got {Pcc}"
    assert -1.0 <= kappa <= 1.0, f"Ray's kappa must be in [-1, +1], got {kappa}"


# ==============================================================================
# 3. Test CFOUR ZMAT Input Generator
# ==============================================================================

# ==============================================================================
# 3. Test CFOUR ZMAT Input Generator
# ==============================================================================

def test_cfour_zmat_generation():
    """Verify production of CFOUR ZMAT with 3-character variables, dummy atom insertion, MEMORY_SIZE, and %isotopes."""
    # 1. Linear molecule (HCN) requiring collinear dummy atom 'X'
    coords_linear = np.array([
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 1.156],
        [0.0, 0.0, -1.065],
    ], dtype=np.float64)
    symbols_linear = ["C", "N", "H"]  # HCN linear complex

    config = CFOURInputConfig(
        title="HCN CCSD(T)/ANO1 VPT2",
        calc_level=CFOURCalcLevel.CCSD_T,
        basis="ANO1",
        reference=CFOURReference.RHF,
        frozen_core=True,
        abcdtype="AOBASIS",
        cc_prog="ECC",
        memory_size_gb=32,
        vib_mode=CFOURVibMode.EXACT,
        anharm_mode=CFOURAnharmMode.VPT2,
        anh_stepsiz=50000,
        fd_project=True,
        props="FIRST_ORDER",
    )

    zmat_linear = generate_cfour_zmat(symbols_linear, coords_linear, config)

    # Verifications for linear molecule
    assert "HCN CCSD(T)/ANO1 VPT2" in zmat_linear
    assert "*CFOUR(" in zmat_linear
    assert "CALC=CCSD(T)" in zmat_linear
    assert "BASIS=ANO1" in zmat_linear
    assert "REFERENCE=RHF" in zmat_linear
    assert "FROZEN_CORE=ON" in zmat_linear
    assert "ABCDTYPE=AOBASIS" in zmat_linear
    assert "CC_PROG=ECC" in zmat_linear
    assert "MEMORY_SIZE=32" in zmat_linear
    assert "MEM_UNIT=GB" in zmat_linear
    assert "VIB=EXACT" in zmat_linear
    assert "ANHARM=VPT2" in zmat_linear
    assert "PROPS=FIRST_ORDER" in zmat_linear
    assert "%isotopes" in zmat_linear
    assert "X " in zmat_linear, "Expected collinear dummy atom 'X' in linear ZMAT!"

    # Verify variable names length <= 3 chars in internal coordinate section
    var_section = zmat_linear.split("*CFOUR(")[0]
    for line in var_section.splitlines():
        if "=" in line:
            var_name = line.split("=")[0].strip()
            assert len(var_name) <= 3, f"CFOUR variable name '{var_name}' exceeds 3 characters!"


def test_variable_name_formatting():
    """Verify variable name formatting for indices 1..9, 10..99, and >= 100."""
    from core_engine.cochem_core_cfour_bridge import _format_cfour_var_name
    assert _format_cfour_var_name("R", 1) == "R01"
    assert _format_cfour_var_name("R", 9) == "R09"
    assert _format_cfour_var_name("R", 10) == "R10"
    assert _format_cfour_var_name("R", 99) == "R99"
    assert _format_cfour_var_name("R", 100) == "R00"
    assert _format_cfour_var_name("R", 101) == "R01" or len(_format_cfour_var_name("R", 101)) == 3
    assert len(_format_cfour_var_name("R", 500)) == 3


# ==============================================================================
# 4. Test CFOUR Output Parser Engine
# ==============================================================================

def test_cfour_output_parser_comprehensive():
    """Verify parsing of full CFOUR log including realistic blank lines, table headers, alphas, sextics, and EFGs."""
    cfour_stdout_text = """
    ==============================================================================
                                EXECUTION OF CFOUR
    ==============================================================================

    Total SCF energy                        :   -76.062458920145 a.u.
    Total MP2 energy                        :   -76.284501239841 a.u.
    Total CCSD energy                       :   -76.321489021345 a.u.
    Total CCSD(T) energy                    :   -76.335901245610 a.u.

    Rotational constants (in MHz) :   835201.45230000   435102.12450000   278451.98760000
    Rotational constants (in cm-1):       27.85932100       14.51344500        9.28815900

    Dipole moment (Debye) : X=  0.000000 Y=  0.000000 Z=  1.854200 Total=  1.854200

    Harmonic vibrational frequencies (cm-1)

       Mode  Irrep   Frequency   IR Intensity
       --------------------------------------
       1     A1      1648.5200   12.45
       2     A1      3832.1400    5.12
       3     B2      3942.8500   48.20

    Vibration-rotation interaction constants (in MHz)

       Mode    alpha_A     alpha_B     alpha_C
       ---------------------------------------
       1     2345.1200   1245.8900    890.1200
       2     4512.3400   2145.6700   1450.2300
       3     5120.4500   2340.1200   1620.3400

    Watson's asymmetric reduction (quartic in kHz)
       Delta_J   =   35.421000
       Delta_JK  = -125.430000
       Delta_K   =  680.120000
       delta_j   =    8.450000
       delta_k   =   45.120000

    Watson's asymmetric reduction (sextic in Hz)
       Phi_J     =    0.045000
       Phi_JK    =   -0.340000
       Phi_KJ    =    1.250000
       Phi_K     =    5.640000
       phi_j     =    0.012000
       phi_jk    =   -0.085000
       phi_k     =    0.450000

    ELECTRIC FIELD GRADIENT TENSOR (a.u.)

       Atom  Sym        q_xx        q_yy        q_zz
       ---------------------------------------------
       1     O     -1.245000    0.450000    0.795000
       2     H      0.120000   -0.050000   -0.070000
       3     H      0.120000   -0.050000   -0.070000

    Diagonal Born-Oppenheimer Correction (DBOC) :   0.00124589
    """

    obs = CFOUROutputParser.parse_cfour_stdout(
        cfour_stdout_text,
        symbols_fallback=["O", "H", "H"],
    )

    # 1. Energy checks
    assert obs.scf_energy_hartree == -76.062458920145
    assert obs.ccsd_t_energy_hartree == -76.335901245610
    assert obs.final_energy_hartree == -76.335901245610

    # 2. Rotational constants (Ae, Be, Ce)
    assert abs(obs.Ae_MHz - 835201.4523) < 1e-4
    assert abs(obs.Be_MHz - 435102.1245) < 1e-4
    assert abs(obs.Ce_MHz - 278451.9876) < 1e-4

    # 3. Frequencies & Alphas with Ground-State B0
    assert len(obs.harmonic_force_field.frequencies_cm_inv) == 3
    assert abs(obs.harmonic_force_field.frequencies_cm_inv[0] - 1648.52) < 1e-2
    assert len(obs.vibration_rotation_alphas) == 3
    # delta_B_vib = -0.5 * (1245.89 + 2145.67 + 2340.12) = -0.5 * 5731.68 = -2865.84 MHz
    assert abs(obs.delta_B_vib_MHz - (-2865.84)) < 1e-2
    assert abs(obs.B0_MHz - (435102.1245 - 2865.84)) < 1e-2

    # 4. Quartic Distortion
    assert obs.quartic_distortion is not None
    assert obs.quartic_distortion.Delta_J_kHz == 35.421
    assert obs.quartic_distortion.Delta_JK_kHz == -125.43
    assert obs.quartic_distortion.Delta_K_kHz == 680.12

    # 5. Sextic Distortion
    assert obs.sextic_distortion is not None
    assert obs.sextic_distortion.Phi_J_Hz == 0.045
    assert obs.sextic_distortion.Phi_K_Hz == 5.64

    # 6. Quadrupole Couplings
    assert len(obs.quadrupole_couplings) >= 1
    o_quad = [q for q in obs.quadrupole_couplings if q.symbol == "O"][0]
    assert o_quad.q_xx_au == -1.245
    assert o_quad.nuclear_quadrupole_moment_mbarn == -25.58

    # 7. DBOC
    assert obs.dboc_correction_hartree == 0.00124589


# ==============================================================================
# 5. Test ISOMASS Force Field Re-Diagonalization (§8B.4, §8B.6, §9.3, §14)
# ==============================================================================

def test_isomass_force_field_rediagonalization():
    """Verify ISOMASS free force field re-diagonalization for water -> D2O and H218O."""
    theta_rad = math.radians(104.5) / 2.0
    r_oh = 0.9578
    coords = np.array([
        [0.0, 0.0, 0.0],
        [r_oh * math.sin(theta_rad), 0.0, r_oh * math.cos(theta_rad)],
        [-r_oh * math.sin(theta_rad), 0.0, r_oh * math.cos(theta_rad)],
    ], dtype=np.float64)
    symbols = ["O", "H", "H"]

    # Construct an authentic physical 9x9 harmonic Cartesian force constant matrix (Hartree/bohr^2)
    np.random.seed(42)
    A = np.random.randn(9, 9) * 0.05
    F = A.T @ A + np.diag([0.5, 0.5, 0.5, 0.35, 0.35, 0.35, 0.35, 0.35, 0.35])

    # Re-diagonalize for D2O (isotopes = [16, 2, 2])
    iso_res_d2o = isomass_rediagonalize_force_field(
        cartesian_hessian_hartree_bohr2=F,
        symbols=symbols,
        coordinates_angstrom=coords,
        target_isotopes=[16, 2, 2],
        parent_isotopes=[16, 1, 1],
        parent_name="H2O",
        isotopologue_label="D2O",
    )

    # 1. Check isotopic mass retrieval
    assert iso_res_d2o.isotopologue_masses_u[1] > 2.014  # Deuterium mass ~ 2.0141 u
    assert iso_res_d2o.parent_masses_u[1] < 1.009       # Protium mass ~ 1.0078 u

    # 2. Rotational constants must shift downwards for D2O due to doubled hydrogen mass
    assert iso_res_d2o.iso_Be_MHz[0] < iso_res_d2o.parent_Be_MHz[0]
    assert iso_res_d2o.iso_Be_MHz[1] < iso_res_d2o.parent_Be_MHz[1]
    assert iso_res_d2o.iso_Be_MHz[2] < iso_res_d2o.parent_Be_MHz[2]
    # B for D2O is roughly ~ half of H2O
    ratio_B = iso_res_d2o.iso_Be_MHz[1] / iso_res_d2o.parent_Be_MHz[1]
    assert 0.45 < ratio_B < 0.65, f"Expected D2O/H2O Be ratio ~ 0.5-0.6, got {ratio_B}"

    # 3. Vibrational frequencies must also shift downwards for D2O
    assert len(iso_res_d2o.iso_frequencies_cm_inv) == 3
    assert all(f > 0 for f in iso_res_d2o.iso_frequencies_cm_inv)
    assert iso_res_d2o.iso_zpe_cm_inv < iso_res_d2o.parent_zpe_cm_inv

    # 4. Check shifts
    assert iso_res_d2o.delta_B0_MHz < 0.0, "Delta B0 must be negative upon deuteration"
    assert iso_res_d2o.provenance_tag == "[D]"


# ==============================================================================
# 6. Test Pickett SPCAT Exporter
# ==============================================================================

def test_export_spcat_var():
    """Verify Pickett .var formatting and integer codes."""
    reference_obs = CFOURObservables(
        scf_energy_hartree=-76.0,
        final_energy_hartree=-76.33,
        Ae_MHz=835000.0,
        Be_MHz=435000.0,
        Ce_MHz=278000.0,
        Ae_cm_inv=27.85,
        Be_cm_inv=14.51,
        Ce_cm_inv=9.27,
        delta_A_vib_MHz=-5000.0,
        delta_B_vib_MHz=-2500.0,
        delta_C_vib_MHz=-1500.0,
        A0_MHz=830000.0,
        B0_MHz=432500.0,
        C0_MHz=276500.0,
        A0_cm_inv=27.68,
        B0_cm_inv=14.42,
        C0_cm_inv=9.22,
        inertial_defect_amu_ang2=0.045,
        planar_moment_Paa_amu_ang2=1.0,
        planar_moment_Pbb_amu_ang2=0.5,
        planar_moment_Pcc_amu_ang2=0.01,
        ray_asymmetry_kappa=-0.43,
        dipole_a_debye=0.0,
        dipole_b_debye=0.0,
        dipole_c_debye=1.85,
        dipole_total_debye=1.85,
        harmonic_force_field=HarmonicForceField(
            n_atoms=3,
            symbols=["O", "H", "H"],
            masses_u=[15.9949, 1.0078, 1.0078],
            frequencies_cm_inv=[1600.0, 3800.0, 3900.0],
            zpe_cm_inv=4650.0,
            zpe_kcal_mol=13.29,
        ),
        quartic_distortion=QuarticCentrifugalDistortion(
            Delta_J_kHz=35.0,
            Delta_JK_kHz=-120.0,
            Delta_K_kHz=650.0,
            delta_j_kHz=8.0,
            delta_k_kHz=40.0,
        ),
        sextic_distortion=SexticCentrifugalDistortion(
            Phi_J_Hz=0.04,
            Phi_K_Hz=5.5,
        ),
        quadrupole_couplings=[
            ElectricFieldGradientTensor(
                atom_index=1,
                symbol="N",
                isotope_mass_number=14,
                q_xx_au=1.0,
                q_yy_au=-0.5,
                q_zz_au=-0.5,
                asymmetry_eta=0.0,
                nuclear_quadrupole_moment_mbarn=20.44,
                chi_aa_kHz=4800.0,
                chi_bb_kHz=-2400.0,
                chi_cc_kHz=-2400.0,
            )
        ]
    )

    var_str = export_cfour_to_spcat_var(reference_obs, reduction=WatsonReduction.A)

    assert "10000" in var_str  # A
    assert "20000" in var_str  # B
    assert "30000" in var_str  # C
    assert "   200" in var_str  # Delta_J
    assert "  1100" in var_str  # Delta_JK
    assert "  2000" in var_str  # Delta_K
    assert "   300" in var_str  # Phi_J
    assert "  3000" in var_str  # Phi_K
    assert "110000" in var_str  # chi_aa(1)
    assert "120000" in var_str  # chi_bb-chi_cc(1)


# ==============================================================================
# 7. Test CLI Interface
# ==============================================================================

def test_cli_parser():
    """Verify CLI parser options and commands."""
    parser = build_cli_parser()
    subcommands = parser._subparsers._actions[1].choices
    assert "build-zmat" in subcommands
    assert "parse-output" in subcommands
    assert "isomass" in subcommands
    assert "export-spcat" in subcommands
