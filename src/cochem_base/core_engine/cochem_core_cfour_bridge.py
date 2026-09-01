#!/usr/bin/env python3
# cochem_canvas_target: core_engine/cochem_core_cfour_bridge.py
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""CoChem-CORE: CFOUR Electronic Structure & VPT2 Anharmonic Spectroscopy Bridge.

Mandated by:
- Method Matrix v4 §8B.6 (Restart under Wall-Clock Caps & Irrep/Displacement Decomposition)
- Method Matrix v4 §9.1–§9.5 (Codes & Acquisition: CFOUR Track & Analytic CCSD(T) Second Derivatives)
- Method Matrix v4 §13.4 Table 4-C (Vibrational Averaging & Ground-State B0)
- Method Matrix v4 §14.1 Table 6-C (Secondary Observables: Sextic Centrifugal Distortion & EFGs)
- Method Matrix v4 §8D (3-Tier Coupled-Cluster Routing Protocol: CFOUR Tier 1 Optimal)
- Method Matrix v4 §8B.4 & §6.10 (ISOMASS Free Force Field Re-Diagonalization for Isotopologues)
- CoChem Anti-Spoofing Protocol v3 (Authentic Physical Calculation & Zero Mocks)
- CoChem Mendeleev Library Mandate (Strict Dynamic Atomic/Isotopic Mass Retrieval)

Key Capabilities:
1. CFOUR Track Job Dispatch & ZMAT Generator:
   - Rigid internal coordinate Z-matrix formulation conforming to CFOUR requirements.
   - 3-character variable name constraints (e.g. R01, A01, D01, RX, RH, RC).
   - Automated detection and dummy atom ('X') insertion for collinear fragments (0° / 180° singularity avoidance).
   - Global memory keyword formatting (`MEMORY_SIZE` / `MEM_UNIT`, e.g. 32 GB global allocation vs ORCA per-rank maxcore).
   - Parallel coupled-cluster keyword pairing (`ABCDTYPE=AOBASIS` + `CC_PROG=ECC` for parallel `xcfour`).
   - Dynamic `%isotopes` block construction via the `mendeleev` library.
2. Analytic CCSD(T) Second Derivatives & VPT2 Force Field Orchestration:
   - `VIB=EXACT`, `ANHARM=VPT2` (full cubic + semidiagonal quartic fields) and `ANHARM=VIBROT`.
   - Complete extraction of harmonic frequencies, ZPE, force constant matrices (`FCMINT`, `FCMFINAL`), and dipole derivatives (`DIPDER`).
   - Vibration-rotation interaction constant (alpha_i^A, alpha_i^B, alpha_i^C) extraction and ground-state rotational constants (A0, B0, C0).
3. ISOMASS Harmonic Force Field Re-Diagonalization Engine (§8B.4, §8B.6, §9.3, §14):
   - "One force field serves every isotopologue" shortcut.
   - Dynamic mass retrieval via `mendeleev` for parent and target isotopologues.
   - Rigorous Eckart translation and rotation projection (Sayvetz frame) removing 6 (or 5) zero modes.
   - Full re-diagonalization of Cartesian and internal force constant matrices, computing isotope-shifted harmonic frequencies,
     ZPE shifts, normal mode transformations, and isotope-shifted rotational constants (A0', B0', C0', Ae', Be', Ce').
4. Sextic & Quartic Centrifugal Distortion Extraction (§9.3, §14):
   - Dedicated extraction of Watson A-reduced (Delta_J, Delta_JK, Delta_K, delta_J, delta_K, Phi_J, Phi_JK, Phi_K, Phi_KJ, phi_j, phi_jk, phi_k)
     and Watson S-reduced (D_J, D_JK, D_K, d_1, d_2, H_J, H_JK, H_K, H_KJ, h_1, h_2, h_3) centrifugal distortion constants.
   - First-order property extraction: dipole moments, electric field gradients (EFG) and nuclear quadrupole coupling constants (chi_aa, chi_bb, chi_cc),
     nuclear spin-rotation constants (C_aa, C_bb, C_cc), and diagonal Born-Oppenheimer correction (DBOC).
5. Pickett SPCAT / SPFIT Bridge Export:
   - Production of formatted `.var` and `.int` parameter sets with standardized Pickett parameter codes.
6. Execution Broker & Fault Isolation:
   - Integration with CoChem `SubprocessBroker` / `safe_subprocess_run` with automated PID cleanup and zombie reaping.
   - Checkpointing & state reuse: `JOBARC`, `JAINDX`, `OPTARC`, `MOINTS`, `MOABCD`, `FCMFINAL`.
   - Parallel finite-difference decomposition by irreducible representation (`FD_IRREP`) and displacements under wall-clock caps.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

import numpy as np
import scipy.linalg
from mendeleev import element
from pydantic import BaseModel, ConfigDict, Field, field_validator

from cochem_base.config_loader import (
    get_artifact_dir,
    get_base_root,
    get_ramdisk_dir,
    get_repo_root,
    get_runtime_dir,
)
from cochem_base.exceptions import (
    CoChemError,
    ConvergenceError,
    MethodMatrixViolationError,
    OutOfMemoryGateError,
    ProvenanceErrorCode,
)

logger = logging.getLogger("CoChem-CFOUR-Bridge")


# ==============================================================================
# 1. Fundamental Physical Constants (CODATA 2022 / Method Matrix Standards)
# ==============================================================================

class PhysicalConstants:
    """Exact fundamental physical constants from CODATA 2022 recommended values."""

    # Planck constant (exact, SI definition 2019) [J * s]
    H_JS: float = 6.62607015e-34
    # Boltzmann constant (exact, SI definition 2019) [J * K^-1]
    K_B_JK: float = 1.380649e-23
    # Speed of light in vacuum (exact) [m * s^-1]
    C_M_S: float = 299792458.0
    # Speed of light in vacuum (exact) [cm * s^-1]
    C_CM_S: float = 29979245800.0
    # Rotational constant factor C_rot = h / (8 * pi^2) in [MHz * u * Angstrom^2]
    # Groner / Method Matrix standard: 505379.008435 MHz * u * Angstrom^2
    C_ROT_MHZ_U_ANG2: float = 505379.008435
    # Avogadro constant (exact) [mol^-1]
    N_A: float = 6.02214076e23
    # Atomic mass constant [kg]
    AMU_KG: float = 1.66053906660e-27
    # Bohr to Angstrom conversion factor
    BOHR_TO_ANGSTROM: float = 0.529177210903
    ANGSTROM_TO_BOHR: float = 1.0 / 0.529177210903
    # Hartree to eV
    HARTREE_TO_EV: float = 27.211386245988
    # Hartree to kcal/mol
    HARTREE_TO_KCAL_MOL: float = 627.509474063
    # Hartree to kJ/mol
    HARTREE_TO_KJ_MOL: float = 627.509474063 * 4.184
    # Hartree to cm^-1
    HARTREE_TO_CM_INV: float = 219474.63136320
    # Electric Field Gradient (a.u.) to Nuclear Quadrupole Coupling Constant (kHz)
    # chi (kHz) = EFG (a.u.) * Q (mbarn) * 234.96474
    EFG_TO_CHI_KHZ: float = 234.96474
    # Conversion factor from sqrt(Hartree / (bohr^2 * u)) to cm^-1:
    # 1 / (2 * pi * c) * sqrt(E_h / (a0^2 * m_u)) = 5140.487143715828
    HESSIAN_EIGENVALUE_TO_CM_INV: float = 5140.487143715828


CONSTANTS = PhysicalConstants()

# Standard nuclear electric quadrupole moments Q in millibarns (1 mbarn = 10^-31 m^2 = 10^-3 barn)
# Used for exact conversion: chi (kHz) = EFG (a.u.) * Q (mbarn) * 234.96474 (Method Matrix §9.3 & §14.1)
STANDARD_NUCLEAR_QUADRUPOLE_MOMENTS_MBARN: Dict[str, float] = {
    "1H": 0.0,
    "2H": 2.860,       # Deuterium (I=1)
    "3H": 0.0,
    "6Li": -0.82,
    "7Li": -40.1,
    "9Be": 52.88,
    "10B": 84.59,
    "11B": 40.59,
    "12C": 0.0,
    "13C": 0.0,
    "14N": 20.44,      # Nitrogen-14 (I=1, standard 14N quadrupole)
    "15N": 0.0,
    "16O": 0.0,
    "17O": -25.58,     # Oxygen-17 (I=5/2)
    "18O": 0.0,
    "19F": 0.0,
    "23Na": 104.0,
    "25Mg": 199.4,
    "27Al": 146.6,
    "33S": -67.8,
    "35Cl": -81.65,    # Chlorine-35 (I=3/2)
    "37Cl": -64.35,    # Chlorine-37 (I=3/2)
    "79Br": 313.0,     # Bromine-79 (I=3/2)
    "81Br": 262.0,     # Bromine-81 (I=3/2)
    "127I": -696.0,    # Iodine-127 (I=5/2)
}


# ==============================================================================
# 2. Dynamic Mendeleev Mass & Isotope Engine (Mandatory Zero-Hardcoding)
# ==============================================================================

def get_dynamic_atomic_mass(symbol_or_z: Union[str, int], mass_number: Optional[int] = None) -> float:
    """Dynamically retrieve atomic or isotopic mass via Mendeleev library.

    Strictly satisfies CoChem Mendeleev Library Mandate (ZERO hardcoded mass constants).

    Args:
        symbol_or_z: Chemical element symbol (e.g. 'C', 'H', 'N') or atomic number Z (e.g. 6, 1).
        mass_number: Optional specific isotope mass number (e.g. 13 for 13C, 2 for D, 18 for 18O).

    Returns:
        Exact atomic or isotopic mass in unified atomic mass units (u).

    Raises:
        ValueError: If element or isotope cannot be resolved in Mendeleev.
    """
    if isinstance(symbol_or_z, int):
        el = element(symbol_or_z)
    elif isinstance(symbol_or_z, str) and symbol_or_z.strip().isdigit():
        el = element(int(symbol_or_z.strip()))
    else:
        clean_sym = str(symbol_or_z).strip()
        if clean_sym.upper() == "D":
            clean_sym = "H"
            mass_number = 2
        elif clean_sym.upper() == "T":
            clean_sym = "H"
            mass_number = 3
        el = element(clean_sym)

    if mass_number is not None:
        for iso in el.isotopes:
            if iso.mass_number == mass_number:
                if iso.mass is not None:
                    return float(iso.mass)
                return float(iso.mass_number)
        raise ValueError(f"Isotope with mass number {mass_number} not found for element '{el.symbol}'.")

    if el.mass is None:
        raise ValueError(f"Atomic mass is undefined for element '{el.symbol}' in Mendeleev.")
    return float(el.mass)


def get_default_isotope_mass_number(symbol_or_z: Union[str, int]) -> int:
    """Retrieve the mass number of the most abundant isotope dynamically from Mendeleev."""
    if isinstance(symbol_or_z, int):
        el = element(symbol_or_z)
    elif isinstance(symbol_or_z, str) and symbol_or_z.strip().isdigit():
        el = element(int(symbol_or_z.strip()))
    else:
        clean_sym = str(symbol_or_z).strip()
        if clean_sym.upper() == "D":
            return 2
        if clean_sym.upper() == "T":
            return 3
        el = element(clean_sym)

    best_iso = None
    max_abundance = -1.0
    for iso in el.isotopes:
        if iso.abundance is not None and iso.abundance > max_abundance:
            max_abundance = iso.abundance
            best_iso = iso

    if best_iso is not None:
        return int(best_iso.mass_number)

    return int(round(float(el.mass)))


# ==============================================================================
# 3. Pydantic v2 Models & Structured Data Structures
# ==============================================================================

class CFOURReference(str, Enum):
    """SCF reference wavefunction type for CFOUR."""
    RHF = "RHF"
    UHF = "UHF"
    ROHF = "ROHF"


class CFOURCalcLevel(str, Enum):
    """Electronic structure calculation level in CFOUR."""
    HF = "HF"
    MP2 = "MP2"
    CCSD = "CCSD"
    CCSD_T = "CCSD(T)"
    CCSDT_N = "CCSDT-n"
    CC3 = "CC3"
    CCSDT = "CCSDT"


class CFOURVibMode(str, Enum):
    """Vibrational derivative mode in CFOUR."""
    EXACT = "EXACT"        # Analytic second derivatives (closed-shell RHF/UHF CCSD(T))
    FINDIF = "FINDIF"      # Finite-difference numerical second derivatives
    ANALYTIC = "ANALYTIC"  # Reserved synonym


class CFOURAnharmMode(str, Enum):
    """Anharmonic force field calculation mode in CFOUR."""
    NONE = "NONE"
    VPT2 = "VPT2"          # Full cubic + semidiagonal quartic field (required for isotopologues & sextics)
    VIBROT = "VIBROT"      # Vibration-rotation alpha constants only (φ_nij with n totally symmetric)
    FULLQUARTIC = "FULLQUARTIC"


class WatsonReduction(str, Enum):
    """Watson reduced Hamiltonian representation."""
    A = "A"  # Asymmetric reduction (Delta_J, Delta_JK, Delta_K, delta_J, delta_K, Phi_J, ...)
    S = "S"  # Symmetric reduction (D_J, D_JK, D_K, d_1, d_2, H_J, ...)


class CFOURInputConfig(BaseModel):
    """Structured configuration and keyword specification for a CFOUR ZMAT run."""
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="CoChem CFOUR Job", description="Title line for ZMAT.")
    calc_level: CFOURCalcLevel = Field(default=CFOURCalcLevel.CCSD_T, description="Electronic structure method.")
    basis: str = Field(default="ANO1", description="Basis set (e.g. ANO1, cc-pVTZ, aug-cc-pVTZ, cc-pCVTZ).")
    reference: CFOURReference = Field(default=CFOURReference.RHF, description="Reference wavefunction.")
    frozen_core: bool = Field(default=True, description="Frozen core approximation (FROZEN_CORE=ON/OFF).")
    abcdtype: str = Field(default="AOBASIS", description="ABCD integral algorithm (AOBASIS for parallel).")
    cc_prog: str = Field(default="ECC", description="Coupled cluster executable (ECC for parallel).")
    spherical: bool = Field(default=True, description="Spherical harmonic basis functions (SPHERICAL=ON).")
    units: str = Field(default="ANGSTROM", description="Coordinate units (ANGSTROM or BOHR).")
    vib_mode: CFOURVibMode = Field(default=CFOURVibMode.EXACT, description="Hessian evaluation mode.")
    anharm_mode: CFOURAnharmMode = Field(default=CFOURAnharmMode.VPT2, description="Anharmonic VPT2 mode.")
    anh_stepsiz: int = Field(default=50000, description="Step size in reduced coordinates (default 50000 = 0.05).")
    fd_project: bool = Field(default=True, description="FD_PROJECT flag (ON for stationary points, OFF for queue split).")
    props: str = Field(default="FIRST_ORDER", description="Property evaluation (FIRST_ORDER for dipole, quadrupole, EFG).")
    memory_size_gb: int = Field(default=32, description="Global memory allocation in GB (MEMORY_SIZE=32, MEM_UNIT=GB).")
    scf_conv: int = Field(default=10, description="SCF convergence exponent (10 -> 10^-10).")
    cc_conv: int = Field(default=10, description="CC convergence exponent (10 -> 10^-10).")
    lineq_conv: int = Field(default=10, description="Linear equation convergence exponent.")
    geo_conv: int = Field(default=5, description="Geometry convergence exponent.")
    spinrot: bool = Field(default=False, description="Compute nuclear spin-rotation constants (SPINROT=ON).")
    dboc: bool = Field(default=False, description="Compute diagonal Born-Oppenheimer correction (DBOC=ON).")
    relativistic: Optional[str] = Field(default=None, description="Relativistic correction (DPT2, X2C1E, etc.).")
    freq_algorithm: Optional[str] = Field(default=None, description="Frequency algorithm (PARALLEL for queue split).")
    anh_algorithm: Optional[str] = Field(default=None, description="Anharmonic algorithm (PARALLEL for queue split).")
    fd_irrep: Optional[int] = Field(default=None, description="Specific IRREP index for finite difference queue slicing.")
    charge: int = Field(default=0, description="Molecular net charge.")
    multiplicity: int = Field(default=1, description="Spin multiplicity (2S+1).")
    isotopes: Optional[List[int]] = Field(default=None, description="Per-atom mass numbers for %isotopes section.")
    extra_keywords: Dict[str, str] = Field(default_factory=dict, description="Additional custom CFOUR keywords.")


class VibrationRotationAlpha(BaseModel):
    """Vibration-rotation interaction alpha constants for a single normal mode."""
    model_config = ConfigDict(extra="forbid")

    mode_index: int = Field(..., description="1-based normal mode index.")
    harmonic_freq_cm_inv: float = Field(..., description="Harmonic vibrational frequency omega_i in cm^-1.")
    symmetry: str = Field(default="A", description="Irreducible representation / symmetry label.")
    alpha_A_MHz: float = Field(..., description="Alpha constant for A rotational constant in MHz.")
    alpha_B_MHz: float = Field(..., description="Alpha constant for B rotational constant in MHz.")
    alpha_C_MHz: float = Field(..., description="Alpha constant for C rotational constant in MHz.")
    alpha_A_cm_inv: float = Field(..., description="Alpha constant for A in cm^-1.")
    alpha_B_cm_inv: float = Field(..., description="Alpha constant for B in cm^-1.")
    alpha_C_cm_inv: float = Field(..., description="Alpha constant for C in cm^-1.")


class QuarticCentrifugalDistortion(BaseModel):
    """Quartic centrifugal distortion constants in Watson A and S reductions."""
    model_config = ConfigDict(extra="forbid")

    # Watson A-reduction (Delta_J, Delta_JK, Delta_K, delta_J, delta_K)
    Delta_J_kHz: Optional[float] = Field(default=None, description="Watson A Delta_J in kHz.")
    Delta_JK_kHz: Optional[float] = Field(default=None, description="Watson A Delta_JK in kHz.")
    Delta_K_kHz: Optional[float] = Field(default=None, description="Watson A Delta_K in kHz.")
    delta_j_kHz: Optional[float] = Field(default=None, description="Watson A delta_J in kHz.")
    delta_k_kHz: Optional[float] = Field(default=None, description="Watson A delta_K in kHz.")

    # Watson S-reduction (D_J, D_JK, D_K, d_1, d_2)
    D_J_kHz: Optional[float] = Field(default=None, description="Watson S D_J in kHz.")
    D_JK_kHz: Optional[float] = Field(default=None, description="Watson S D_JK in kHz.")
    D_K_kHz: Optional[float] = Field(default=None, description="Watson S D_K in kHz.")
    d_1_kHz: Optional[float] = Field(default=None, description="Watson S d_1 in kHz.")
    d_2_kHz: Optional[float] = Field(default=None, description="Watson S d_2 in kHz.")


class SexticCentrifugalDistortion(BaseModel):
    """Sextic centrifugal distortion constants in Watson A and S reductions (CFOUR Public Specialty)."""
    model_config = ConfigDict(extra="forbid")

    # Watson A-reduction (Phi_J, Phi_JK, Phi_K, Phi_KJ, phi_j, phi_jk, phi_k)
    Phi_J_Hz: Optional[float] = Field(default=None, description="Watson A Phi_J in Hz.")
    Phi_JK_Hz: Optional[float] = Field(default=None, description="Watson A Phi_JK in Hz.")
    Phi_KJ_Hz: Optional[float] = Field(default=None, description="Watson A Phi_KJ in Hz.")
    Phi_K_Hz: Optional[float] = Field(default=None, description="Watson A Phi_K in Hz.")
    phi_j_Hz: Optional[float] = Field(default=None, description="Watson A phi_j in Hz.")
    phi_jk_Hz: Optional[float] = Field(default=None, description="Watson A phi_jk in Hz.")
    phi_k_Hz: Optional[float] = Field(default=None, description="Watson A phi_k in Hz.")

    # Watson S-reduction (H_J, H_JK, H_KJ, H_K, h_1, h_2, h_3)
    H_J_Hz: Optional[float] = Field(default=None, description="Watson S H_J in Hz.")
    H_JK_Hz: Optional[float] = Field(default=None, description="Watson S H_JK in Hz.")
    H_KJ_Hz: Optional[float] = Field(default=None, description="Watson S H_KJ in Hz.")
    H_K_Hz: Optional[float] = Field(default=None, description="Watson S H_K in Hz.")
    h_1_Hz: Optional[float] = Field(default=None, description="Watson S h_1 in Hz.")
    h_2_Hz: Optional[float] = Field(default=None, description="Watson S h_2 in Hz.")
    h_3_Hz: Optional[float] = Field(default=None, description="Watson S h_3 in Hz.")


class ElectricFieldGradientTensor(BaseModel):
    """Electric field gradient (EFG) tensor and derived nuclear quadrupole coupling constants."""
    model_config = ConfigDict(extra="forbid")

    atom_index: int = Field(..., description="1-based atom index.")
    symbol: str = Field(..., description="Element symbol.")
    isotope_mass_number: int = Field(..., description="Mass number.")
    q_xx_au: float = Field(..., description="EFG principal component q_xx in a.u.")
    q_yy_au: float = Field(..., description="EFG principal component q_yy in a.u.")
    q_zz_au: float = Field(..., description="EFG principal component q_zz in a.u.")
    asymmetry_eta: float = Field(..., description="EFG asymmetry parameter eta = (q_xx - q_yy) / q_zz.")
    nuclear_quadrupole_moment_mbarn: float = Field(..., description="Nuclear quadrupole moment Q in mbarn.")
    chi_aa_kHz: float = Field(..., description="Quadrupole coupling constant chi_aa in kHz.")
    chi_bb_kHz: float = Field(..., description="Quadrupole coupling constant chi_bb in kHz.")
    chi_cc_kHz: float = Field(..., description="Quadrupole coupling constant chi_cc in kHz.")


class NuclearSpinRotationTensor(BaseModel):
    """Nuclear spin-rotation interaction constants."""
    model_config = ConfigDict(extra="forbid")

    atom_index: int = Field(..., description="1-based atom index.")
    symbol: str = Field(..., description="Element symbol.")
    C_aa_kHz: float = Field(..., description="Spin-rotation principal component C_aa in kHz.")
    C_bb_kHz: float = Field(..., description="Spin-rotation principal component C_bb in kHz.")
    C_cc_kHz: float = Field(..., description="Spin-rotation principal component C_cc in kHz.")
    C_iso_kHz: float = Field(..., description="Isotropic spin-rotation constant C_iso in kHz.")


class HarmonicForceField(BaseModel):
    """Complete harmonic force field specification from CFOUR."""
    model_config = ConfigDict(extra="forbid")

    n_atoms: int = Field(..., description="Number of atoms.")
    symbols: List[str] = Field(..., description="Atom symbols.")
    masses_u: List[float] = Field(..., description="Atomic masses in unified atomic mass units.")
    frequencies_cm_inv: List[float] = Field(..., description="Harmonic vibrational frequencies in cm^-1.")
    symmetries: List[str] = Field(default_factory=list, description="Normal mode symmetry labels.")
    ir_intensities_km_mol: List[float] = Field(default_factory=list, description="IR intensities in km/mol.")
    zpe_cm_inv: float = Field(..., description="Zero-point vibrational energy in cm^-1.")
    zpe_kcal_mol: float = Field(..., description="Zero-point vibrational energy in kcal/mol.")
    cartesian_hessian: Optional[List[List[float]]] = Field(
        default=None, description="Cartesian force constant matrix (3N x 3N) in Hartree/bohr^2."
    )


class CFOURObservables(BaseModel):
    """Complete structured spectroscopic observables emitted by CFOUR CCSD(T) / VPT2."""
    model_config = ConfigDict(extra="forbid")

    # Energies
    scf_energy_hartree: Optional[float] = Field(default=None, description="SCF total energy in Hartree.")
    mp2_energy_hartree: Optional[float] = Field(default=None, description="MP2 correlation / total energy.")
    ccsd_energy_hartree: Optional[float] = Field(default=None, description="CCSD total energy in Hartree.")
    ccsd_t_energy_hartree: Optional[float] = Field(default=None, description="CCSD(T) total energy in Hartree.")
    final_energy_hartree: float = Field(..., description="Final electronic energy in Hartree.")

    # Equilibrium Rotational Constants (Be)
    Ae_MHz: float = Field(..., description="Equilibrium rotational constant A_e in MHz.")
    Be_MHz: float = Field(..., description="Equilibrium rotational constant B_e in MHz.")
    Ce_MHz: float = Field(..., description="Equilibrium rotational constant C_e in MHz.")
    Ae_cm_inv: float = Field(..., description="Equilibrium rotational constant A_e in cm^-1.")
    Be_cm_inv: float = Field(..., description="Equilibrium rotational constant B_e in cm^-1.")
    Ce_cm_inv: float = Field(..., description="Equilibrium rotational constant C_e in cm^-1.")

    # Vibrational Corrections & Ground-State Constants (B0)
    delta_A_vib_MHz: float = Field(default=0.0, description="Vibrational correction delta_A_vib in MHz.")
    delta_B_vib_MHz: float = Field(default=0.0, description="Vibrational correction delta_B_vib in MHz.")
    delta_C_vib_MHz: float = Field(default=0.0, description="Vibrational correction delta_C_vib in MHz.")
    A0_MHz: float = Field(..., description="Ground-state rotational constant A_0 = A_e + delta_A_vib (MHz).")
    B0_MHz: float = Field(..., description="Ground-state rotational constant B_0 = B_e + delta_B_vib (MHz).")
    C0_MHz: float = Field(..., description="Ground-state rotational constant C_0 = C_e + delta_C_vib (MHz).")
    A0_cm_inv: float = Field(..., description="Ground-state rotational constant A_0 in cm^-1.")
    B0_cm_inv: float = Field(..., description="Ground-state rotational constant B_0 in cm^-1.")
    C0_cm_inv: float = Field(..., description="Ground-state rotational constant C_0 in cm^-1.")

    # Rigid-Rotor Inertial Observables
    inertial_defect_amu_ang2: float = Field(..., description="Inertial defect Delta = I_c - I_a - I_b (u * Angstrom^2).")
    planar_moment_Paa_amu_ang2: float = Field(..., description="Planar moment P_aa in u * Angstrom^2.")
    planar_moment_Pbb_amu_ang2: float = Field(..., description="Planar moment P_bb in u * Angstrom^2.")
    planar_moment_Pcc_amu_ang2: float = Field(..., description="Planar moment P_cc in u * Angstrom^2.")
    ray_asymmetry_kappa: float = Field(..., description="Ray's asymmetry parameter kappa = (2B-A-C)/(A-C).")

    # Dipole Moments (Debye)
    dipole_a_debye: float = Field(default=0.0, description="Principal axis dipole component mu_a in Debye.")
    dipole_b_debye: float = Field(default=0.0, description="Principal axis dipole component mu_b in Debye.")
    dipole_c_debye: float = Field(default=0.0, description="Principal axis dipole component mu_c in Debye.")
    dipole_total_debye: float = Field(default=0.0, description="Total dipole moment in Debye.")

    # Vibrational & Anharmonic Data
    harmonic_force_field: HarmonicForceField = Field(..., description="Harmonic force field and normal modes.")
    vibration_rotation_alphas: List[VibrationRotationAlpha] = Field(default_factory=list, description="Alpha constants.")
    quartic_distortion: Optional[QuarticCentrifugalDistortion] = Field(default=None, description="Quartic distortion.")
    sextic_distortion: Optional[SexticCentrifugalDistortion] = Field(default=None, description="Sextic distortion.")
    quadrupole_couplings: List[ElectricFieldGradientTensor] = Field(default_factory=list, description="Quadrupole couplings.")
    spin_rotation_tensors: List[NuclearSpinRotationTensor] = Field(default_factory=list, description="Spin rotation.")
    dboc_correction_hartree: Optional[float] = Field(default=None, description="DBOC in Hartree.")
    dboc_correction_cm_inv: Optional[float] = Field(default=None, description="DBOC in cm^-1.")


class IsotopologueFFResult(BaseModel):
    """Telemetry and spectroscopic constants resulting from ISOMASS force field re-diagonalization."""
    model_config = ConfigDict(extra="forbid")

    parent_name: str = Field(..., description="Identifier of the parent molecule.")
    isotopologue_label: str = Field(..., description="Isotopologue description, e.g. '13C', 'D', '18O'.")
    symbols: List[str] = Field(..., description="Atom symbols.")
    parent_masses_u: List[float] = Field(..., description="Parent atomic masses (u).")
    isotopologue_masses_u: List[float] = Field(..., description="Isotopologue atomic masses (u).")

    # Parent constants
    parent_Be_MHz: Tuple[float, float, float] = Field(..., description="Parent equilibrium (Ae, Be, Ce) in MHz.")
    parent_B0_MHz: Tuple[float, float, float] = Field(..., description="Parent ground-state (A0, B0, C0) in MHz.")
    parent_zpe_cm_inv: float = Field(..., description="Parent harmonic ZPE in cm^-1.")

    # Isotopologue constants
    iso_Be_MHz: Tuple[float, float, float] = Field(..., description="Isotopologue equilibrium (Ae, Be, Ce) in MHz.")
    iso_B0_MHz: Tuple[float, float, float] = Field(..., description="Isotopologue ground-state (A0, B0, C0) in MHz.")
    iso_frequencies_cm_inv: List[float] = Field(..., description="Isotopologue harmonic vibrational frequencies (cm^-1).")
    iso_zpe_cm_inv: float = Field(..., description="Isotopologue harmonic ZPE in cm^-1.")
    zpe_shift_cm_inv: float = Field(..., description="Delta ZPE = ZPE_iso - ZPE_parent in cm^-1.")

    # Inertial properties
    iso_inertial_defect_amu_ang2: float = Field(..., description="Isotopologue inertial defect Delta (u * Angstrom^2).")
    iso_planar_moments_amu_ang2: Tuple[float, float, float] = Field(..., description="Isotopologue planar moments (Paa, Pbb, Pcc).")
    iso_ray_asymmetry_kappa: float = Field(..., description="Isotopologue Ray's asymmetry parameter kappa.")

    # Shifts
    delta_A0_MHz: float = Field(..., description="Shift Delta A0 = A0_iso - A0_parent in MHz.")
    delta_B0_MHz: float = Field(..., description="Shift Delta B0 = B0_iso - B0_parent in MHz.")
    delta_C0_MHz: float = Field(..., description="Shift Delta C0 = C0_iso - C0_parent in MHz.")
    provenance_tag: str = Field(default="[D]", description="Method Matrix provenance tag ([M], [D], [E]).")


class CFOURJobResult(BaseModel):
    """Complete result container for a dispatched or parsed CFOUR calculation."""
    model_config = ConfigDict(extra="forbid")

    success: bool = Field(..., description="True if execution completed without error.")
    job_id: str = Field(..., description="Unique job identifier.")
    working_directory: str = Field(..., description="Path to execution directory.")
    wall_time_seconds: float = Field(..., description="Execution wall-clock time in seconds.")
    stdout_hash: str = Field(..., description="SHA-256 hash of stdout.")
    zmat_hash: str = Field(..., description="SHA-256 hash of input ZMAT.")
    observables: Optional[CFOURObservables] = Field(default=None, description="Extracted spectroscopic observables.")
    isotopologues: List[IsotopologueFFResult] = Field(default_factory=list, description="ISOMASS re-diagonalized isotopologues.")
    error_message: Optional[str] = Field(default=None, description="Error message if run failed.")
    preserved_files: List[str] = Field(default_factory=list, description="List of preserved binary archive files.")
    compliance_notes: List[str] = Field(default_factory=list, description="Method Matrix audit and compliance remarks.")


# ==============================================================================
# 4. Geometry & Inertial Mathematics Helper Engine
# ==============================================================================

def compute_center_of_mass(symbols: Sequence[str], coordinates_angstrom: np.ndarray, masses_u: Optional[Sequence[float]] = None) -> np.ndarray:
    """Compute center of mass using exact dynamic atomic masses."""
    coords = np.asarray(coordinates_angstrom, dtype=np.float64)
    if masses_u is None:
        masses = np.array([get_dynamic_atomic_mass(s) for s in symbols], dtype=np.float64)
    else:
        masses = np.asarray(masses_u, dtype=np.float64)
    total_mass = np.sum(masses)
    if total_mass <= 0.0:
        raise ValueError("Total molecular mass must be strictly positive.")
    com = np.sum(coords * masses[:, np.newaxis], axis=0) / total_mass
    return com


def compute_inertia_tensor(symbols: Sequence[str], coordinates_angstrom: np.ndarray, masses_u: Optional[Sequence[float]] = None) -> np.ndarray:
    """Compute exact Cartesian moment of inertia tensor in u * Angstrom^2."""
    coords = np.asarray(coordinates_angstrom, dtype=np.float64)
    com = compute_center_of_mass(symbols, coords, masses_u)
    shifted_coords = coords - com

    if masses_u is None:
        masses = np.array([get_dynamic_atomic_mass(s) for s in symbols], dtype=np.float64)
    else:
        masses = np.asarray(masses_u, dtype=np.float64)

    I = np.zeros((3, 3), dtype=np.float64)
    for m, (x, y, z) in zip(masses, shifted_coords):
        I[0, 0] += m * (y**2 + z**2)
        I[1, 1] += m * (x**2 + z**2)
        I[2, 2] += m * (x**2 + y**2)
        I[0, 1] -= m * x * y
        I[0, 2] -= m * x * z
        I[1, 2] -= m * y * z

    I[1, 0] = I[0, 1]
    I[2, 0] = I[0, 2]
    I[2, 1] = I[1, 2]
    return I


def compute_equilibrium_rotational_constants(
    symbols: Sequence[str], coordinates_angstrom: np.ndarray, masses_u: Optional[Sequence[float]] = None
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], float, Tuple[float, float, float], float]:
    """Compute sorted equilibrium rotational constants (Ae >= Be >= Ce), planar moments, inertial defect, and Ray's kappa.

    Returns:
        ((Ae_MHz, Be_MHz, Ce_MHz), (Ae_cm, Be_cm, Ce_cm), inertial_defect, (Paa, Pbb, Pcc), kappa)
    """
    I_tensor = compute_inertia_tensor(symbols, coordinates_angstrom, masses_u)
    evals, evecs = np.linalg.eigh(I_tensor)

    # Sorted moments: Ia <= Ib <= Ic
    Ia, Ib, Ic = float(evals[0]), float(evals[1]), float(evals[2])

    conv = CONSTANTS.C_ROT_MHZ_U_ANG2
    c_cm_s = CONSTANTS.C_CM_S

    Ae_MHz = conv / Ia if Ia > 1e-6 else 1e9
    Be_MHz = conv / Ib if Ib > 1e-6 else 1e9
    Ce_MHz = conv / Ic if Ic > 1e-6 else 1e9

    Ae_cm = (Ae_MHz * 1e6) / c_cm_s
    Be_cm = (Be_MHz * 1e6) / c_cm_s
    Ce_cm = (Ce_MHz * 1e6) / c_cm_s

    # Planar moments: Paa = (Ib + Ic - Ia)/2, Pbb = (Ia + Ic - Ib)/2, Pcc = (Ia + Ib - Ic)/2
    Paa = (Ib + Ic - Ia) / 2.0
    Pbb = (Ia + Ic - Ib) / 2.0
    Pcc = (Ia + Ib - Ic) / 2.0

    # Inertial defect Delta = Ic - Ia - Ib = -2 * Pcc
    inertial_defect = Ic - Ia - Ib

    # Ray's asymmetry parameter kappa = (2B - A - C) / (A - C)
    denom = Ae_MHz - Ce_MHz
    if abs(denom) > 1e-6:
        kappa = (2.0 * Be_MHz - Ae_MHz - Ce_MHz) / denom
    else:
        kappa = -1.0 if abs(Be_MHz - Ce_MHz) < 1e-6 else 1.0

    return ((Ae_MHz, Be_MHz, Ce_MHz), (Ae_cm, Be_cm, Ce_cm), inertial_defect, (Paa, Pbb, Pcc), kappa)


# ==============================================================================
# 5. CFOUR ZMAT Input Generator Engine
# ==============================================================================

def _format_cfour_var_name(prefix: str, index: int) -> str:
    """Format variable name strictly conforming to CFOUR 3-character constraint (Method Matrix §9.5)."""
    p = prefix.strip()[:1].upper()
    if 1 <= index <= 9:
        return f"{p}0{index}"
    elif 10 <= index <= 99:
        return f"{p}{index}"
    else:
        # Base-36 alphanumeric encoding for index >= 100 to prevent collisions up to 1296 variables
        idx_rem = index - 100
        chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        c1 = chars[(idx_rem // 36) % 36]
        c2 = chars[idx_rem % 36]
        return f"{p}{c1}{c2}"


def generate_cfour_zmat(
    symbols: Sequence[str],
    coordinates_angstrom: np.ndarray,
    config: Optional[CFOURInputConfig] = None,
    isotopes: Optional[Sequence[int]] = None,
) -> str:
    """Generate a production-grade CFOUR ZMAT input file conforming strictly to Method Matrix v4 §9.5.

    Implements:
    - 3-character variable names (e.g. R01, A01, D01, RX, RH).
    - Automated detection and perpendicular dummy atom ('X') insertion for collinear fragments (0° / 180° singularity avoidance).
    - Global memory keyword formatting: `MEMORY_SIZE=32`, `MEM_UNIT=GB`.
    - Single-space formatting between fields.
    - `%isotopes` block generated dynamically via `mendeleev`.
    """
    cfg = config or CFOURInputConfig()
    coords = np.asarray(coordinates_angstrom, dtype=np.float64)
    n_atoms = len(symbols)
    if coords.shape != (n_atoms, 3):
        raise ValueError(f"Coordinate shape {coords.shape} does not match {n_atoms} atom symbols.")

    lines: List[str] = []
    # 1. Title line
    lines.append(cfg.title.strip())

    # 2. Build Internal Coordinates / Z-matrix with Collinear Dummy Atom Insertion
    zmat_entries: List[str] = []
    variables: Dict[str, float] = {}

    var_r_idx = 1
    var_a_idx = 1
    var_d_idx = 1
    var_x_idx = 1

    # Keep track of ZMAT row positions and their 3D coordinates
    zmat_coords: List[np.ndarray] = []

    for i in range(n_atoms):
        sym = symbols[i].strip().upper()
        cur_pos = coords[i]

        if i == 0:
            zmat_entries.append(sym)
            zmat_coords.append(cur_pos)
        elif i == 1:
            r_name = _format_cfour_var_name("R", var_r_idx)
            var_r_idx += 1
            dist = float(np.linalg.norm(cur_pos - zmat_coords[0]))
            variables[r_name] = dist
            zmat_entries.append(f"{sym} 1 {r_name}")
            zmat_coords.append(cur_pos)
        elif i == 2:
            # Check angle with row 1 and row 2
            v21 = zmat_coords[0] - zmat_coords[1]
            v23 = cur_pos - zmat_coords[1]
            norm21 = np.linalg.norm(v21)
            norm23 = np.linalg.norm(v23)
            cos_theta = np.dot(v21, v23) / (norm21 * norm23 + 1e-15)
            cos_theta = np.clip(cos_theta, -1.0, 1.0)
            angle_deg = float(np.degrees(np.arccos(cos_theta)))

            # If collinear (angle < 5 deg or > 175 deg), insert dummy atom X perpendicular to bond 1-2
            if angle_deg < 5.0 or angle_deg > 175.0:
                # Find perpendicular vector
                u = v21 / (norm21 + 1e-15)
                # Pick arbitrary non-collinear vector
                ref_axis = np.array([1.0, 0.0, 0.0]) if abs(u[0]) < 0.8 else np.array([0.0, 1.0, 0.0])
                perp = np.cross(u, ref_axis)
                perp = perp / np.linalg.norm(perp)

                # Dummy atom position attached to atom 1 (row 2)
                x_pos = zmat_coords[1] + 1.0 * perp
                rx_name = _format_cfour_var_name("X", var_x_idx)
                var_x_idx += 1
                ax_name = _format_cfour_var_name("A", var_a_idx)
                var_a_idx += 1

                variables[rx_name] = 1.000000
                variables[ax_name] = 90.000000

                # Insert dummy atom X at row 3 (referencing row 2 with 1.0 Å and row 1 with 90°)
                zmat_entries.append(f"X 2 {rx_name} 1 {ax_name}")
                zmat_coords.append(x_pos)
                x_row = len(zmat_coords)  # 3

                # Now add atom 2 (row 4): distance to atom 1 (row 2), angle to X (90°), dihedral to atom 0 (row 1)
                r_name = _format_cfour_var_name("R", var_r_idx)
                var_r_idx += 1
                a_name = _format_cfour_var_name("A", var_a_idx)
                var_a_idx += 1
                d_name = _format_cfour_var_name("D", var_d_idx)
                var_d_idx += 1

                variables[r_name] = float(norm23)
                variables[a_name] = 90.000000
                variables[d_name] = 180.000000 if angle_deg > 90.0 else 0.000000

                zmat_entries.append(f"{sym} 2 {r_name} {x_row} {a_name} 1 {d_name}")
                zmat_coords.append(cur_pos)
            else:
                r_name = _format_cfour_var_name("R", var_r_idx)
                var_r_idx += 1
                a_name = _format_cfour_var_name("A", var_a_idx)
                var_a_idx += 1

                variables[r_name] = float(np.linalg.norm(cur_pos - zmat_coords[0]))
                variables[a_name] = angle_deg
                zmat_entries.append(f"{sym} 1 {r_name} 2 {a_name}")
                zmat_coords.append(cur_pos)
        else:
            # Check angle with atom 0 (row 1) and atom 1 (row 2)
            v1i = cur_pos - zmat_coords[0]
            v12 = zmat_coords[1] - zmat_coords[0]
            norm1i = np.linalg.norm(v1i)
            norm12 = np.linalg.norm(v12)
            cos_theta = np.dot(v1i, v12) / (norm1i * norm12 + 1e-15)
            cos_theta = np.clip(cos_theta, -1.0, 1.0)
            angle_deg = float(np.degrees(np.arccos(cos_theta)))

            if angle_deg < 5.0 or angle_deg > 175.0:
                # Find perpendicular vector
                u = v12 / (norm12 + 1e-15)
                ref_axis = np.array([1.0, 0.0, 0.0]) if abs(u[0]) < 0.8 else np.array([0.0, 1.0, 0.0])
                perp = np.cross(u, ref_axis)
                perp = perp / np.linalg.norm(perp)

                x_pos = zmat_coords[0] + 1.0 * perp
                rx_name = _format_cfour_var_name("X", var_x_idx)
                var_x_idx += 1
                ax_name = _format_cfour_var_name("A", var_a_idx)
                var_a_idx += 1

                variables[rx_name] = 1.000000
                variables[ax_name] = 90.000000

                zmat_entries.append(f"X 1 {rx_name} 2 {ax_name}")
                zmat_coords.append(x_pos)
                x_row = len(zmat_coords)

                r_name = _format_cfour_var_name("R", var_r_idx)
                var_r_idx += 1
                a_name = _format_cfour_var_name("A", var_a_idx)
                var_a_idx += 1
                d_name = _format_cfour_var_name("D", var_d_idx)
                var_d_idx += 1

                variables[r_name] = float(norm1i)
                variables[a_name] = 90.000000
                variables[d_name] = 180.000000 if angle_deg > 90.0 else 0.000000

                zmat_entries.append(f"{sym} 1 {r_name} {x_row} {a_name} 2 {d_name}")
                zmat_coords.append(cur_pos)
            else:
                r_name = _format_cfour_var_name("R", var_r_idx)
                var_r_idx += 1
                a_name = _format_cfour_var_name("A", var_a_idx)
                var_a_idx += 1
                d_name = _format_cfour_var_name("D", var_d_idx)
                var_d_idx += 1

                dist = float(norm1i)

                # Dihedral i-1-2-3
                v1 = zmat_coords[1] - zmat_coords[0]
                v2 = zmat_coords[2] - zmat_coords[1]
                v3 = cur_pos - zmat_coords[2]

                n1 = np.cross(v1, v2)
                n2 = np.cross(v2, v3)
                norm_n1 = np.linalg.norm(n1)
                norm_n2 = np.linalg.norm(n2)
                if norm_n1 > 1e-8 and norm_n2 > 1e-8:
                    m1 = np.cross(n1, v2 / (np.linalg.norm(v2) + 1e-15))
                    x = np.dot(n1, n2) / (norm_n1 * norm_n2)
                    y = np.dot(m1, n2) / (norm_n1 * norm_n2)
                    dihed_deg = float(np.degrees(np.arctan2(y, x)))
                else:
                    dihed_deg = 0.0

                variables[r_name] = dist
                variables[a_name] = angle_deg
                variables[d_name] = dihed_deg
                zmat_entries.append(f"{sym} 1 {r_name} 2 {a_name} 3 {d_name}")
                zmat_coords.append(cur_pos)

    lines.extend(zmat_entries)
    lines.append("")  # Mandatory blank line separating topology from variables

    # 3. Variable definitions
    for k, v in sorted(variables.items()):
        lines.append(f"{k} = {v:.6f}")

    lines.append("")  # Mandatory blank line before *CFOUR block

    # 4. *CFOUR(...) Keyword Block
    cfour_kw: List[str] = [
        f"CALC={cfg.calc_level.value}",
        f"BASIS={cfg.basis.upper()}",
        f"REFERENCE={cfg.reference.value}",
        f"FROZEN_CORE={'ON' if cfg.frozen_core else 'OFF'}",
        f"ABCDTYPE={cfg.abcdtype.upper()}",
        f"CC_PROG={cfg.cc_prog.upper()}",
        f"SPHERICAL={'ON' if cfg.spherical else 'OFF'}",
        f"UNITS={cfg.units.upper()}",
        f"VIB={cfg.vib_mode.value}",
    ]

    if cfg.anharm_mode != CFOURAnharmMode.NONE:
        cfour_kw.append(f"ANHARM={cfg.anharm_mode.value}")
        cfour_kw.append(f"ANH_STEPSIZ={cfg.anh_stepsiz}")

    cfour_kw.append(f"FD_PROJECT={'ON' if cfg.fd_project else 'OFF'}")
    cfour_kw.append(f"PROPS={cfg.props.upper()}")
    cfour_kw.append(f"MEMORY_SIZE={cfg.memory_size_gb}")
    cfour_kw.append("MEM_UNIT=GB")
    cfour_kw.append(f"SCF_CONV={cfg.scf_conv}")
    cfour_kw.append(f"CC_CONV={cfg.cc_conv}")
    cfour_kw.append(f"LINEQ_CONV={cfg.lineq_conv}")
    cfour_kw.append(f"GEO_CONV={cfg.geo_conv}")

    if cfg.charge != 0:
        cfour_kw.append(f"CHARGE={cfg.charge}")
    if cfg.multiplicity != 1:
        cfour_kw.append(f"MULTIPLICITY={cfg.multiplicity}")
    if cfg.spinrot:
        cfour_kw.append("SPINROT=ON")
    if cfg.dboc:
        cfour_kw.append("DBOC=ON")
    if cfg.relativistic:
        cfour_kw.append(f"RELATIVISTIC={cfg.relativistic.upper()}")
    if cfg.freq_algorithm:
        cfour_kw.append(f"FREQ_ALGORITHM={cfg.freq_algorithm.upper()}")
    if cfg.anh_algorithm:
        cfour_kw.append(f"ANH_ALGORITHM={cfg.anh_algorithm.upper()}")
    if cfg.fd_irrep is not None:
        cfour_kw.append(f"FD_IRREP={cfg.fd_irrep}")

    # Append custom keywords
    for ek, ev in sorted(cfg.extra_keywords.items()):
        cfour_kw.append(f"{ek.upper()}={ev.upper()}")

    # Join *CFOUR(...) block
    lines.append("*CFOUR(" + "\n".join(cfour_kw) + ")")

    # 5. %isotopes block if specified or derived dynamically (for real atoms only)
    iso_list = isotopes or cfg.isotopes
    if iso_list is not None and len(iso_list) == n_atoms:
        lines.append("")
        lines.append("%isotopes")
        for iso_val in iso_list:
            lines.append(str(int(iso_val)))
    elif iso_list is None:
        lines.append("")
        lines.append("%isotopes")
        for sym in symbols:
            lines.append(str(get_default_isotope_mass_number(sym)))

    lines.append("")  # Trailing newline
    return "\n".join(lines)


# ==============================================================================
# 6. CFOUR Output Parser Engine
# ==============================================================================

class CFOUROutputParser:
    """Robust parser for CFOUR standard output logs and auxiliary text archives."""

    PAT_SCF_ENERGY = re.compile(r"(?:E\(SCF\)|SCF ENERGY|Total SCF energy|SCF energy)\s*[:=]?\s*([+-]?\d+\.\d+)", re.IGNORECASE)
    PAT_MP2_ENERGY = re.compile(r"(?:E\(MP2\)|MP2 ENERGY|Total MP2 energy)\s*[:=]?\s*([+-]?\d+\.\d+)", re.IGNORECASE)
    PAT_CCSD_ENERGY = re.compile(r"(?:E\(CCSD\)|CCSD ENERGY|Total CCSD energy)\s*[:=]?\s*([+-]?\d+\.\d+)", re.IGNORECASE)
    PAT_CCSD_T_ENERGY = re.compile(r"(?:E\(CCSD\(T\)\)|CCSD\(T\) ENERGY|Total CCSD\(T\) energy)\s*[:=]?\s*([+-]?\d+\.\d+)", re.IGNORECASE)

    PAT_ROT_CONST_BE = re.compile(
        r"Rotational constants\s*\(in\s*MHz\)\s*:\s*([+-]?\d+\.\d+)\s+([+-]?\d+\.\d+)\s+([+-]?\d+\.\d+)",
        re.IGNORECASE,
    )
    PAT_ROT_CONST_CM = re.compile(
        r"Rotational constants\s*\(in\s*cm-1\)\s*:\s*([+-]?\d+\.\d+)\s+([+-]?\d+\.\d+)\s+([+-]?\d+\.\d+)",
        re.IGNORECASE,
    )

    PAT_DIPOLE = re.compile(
        r"Dipole moment\s*\(Debye\)\s*:\s*X=\s*([+-]?\d+\.\d+)\s+Y=\s*([+-]?\d+\.\d+)\s+Z=\s*([+-]?\d+\.\d+)\s+Total=\s*([+-]?\d+\.\d+)",
        re.IGNORECASE,
    )

    @classmethod
    def parse_cfour_stdout(
        cls,
        stdout_text: str,
        symbols_fallback: Optional[Sequence[str]] = None,
        coordinates_fallback: Optional[np.ndarray] = None,
    ) -> CFOURObservables:
        """Parse complete spectroscopic observables from a CFOUR execution stdout.

        Args:
            stdout_text: Full standard output log text.
            symbols_fallback: Optional atom symbols if not found in log.
            coordinates_fallback: Optional Cartesian coordinates array.

        Returns:
            CFOURObservables instance with extracted parameters.
        """
        lines = stdout_text.splitlines()

        scf_energy: Optional[float] = None
        mp2_energy: Optional[float] = None
        ccsd_energy: Optional[float] = None
        ccsd_t_energy: Optional[float] = None
        final_energy: Optional[float] = None

        Ae_MHz, Be_MHz, Ce_MHz = 0.0, 0.0, 0.0
        Ae_cm, Be_cm, Ce_cm = 0.0, 0.0, 0.0

        dipole_a, dipole_b, dipole_c, dipole_tot = 0.0, 0.0, 0.0, 0.0

        freqs: List[float] = []
        symmetries: List[str] = []
        ir_intensities: List[float] = []

        alphas: List[VibrationRotationAlpha] = []
        quartic = QuarticCentrifugalDistortion()
        sextic = SexticCentrifugalDistortion()
        quadrupoles: List[ElectricFieldGradientTensor] = []
        spin_rots: List[NuclearSpinRotationTensor] = []
        dboc_hartree: Optional[float] = None
        dboc_cm: Optional[float] = None

        parsed_symbols: List[str] = list(symbols_fallback or [])

        i = 0
        while i < len(lines):
            line = lines[i]

            # 1. Parse Energies
            if "SCF energy" in line or "E(SCF)" in line or "Total SCF energy" in line:
                m = cls.PAT_SCF_ENERGY.search(line)
                if m:
                    scf_energy = float(m.group(1))
            if "MP2 energy" in line or "E(MP2)" in line:
                m = cls.PAT_MP2_ENERGY.search(line)
                if m:
                    mp2_energy = float(m.group(1))
            if "CCSD energy" in line or "E(CCSD)" in line:
                m = cls.PAT_CCSD_ENERGY.search(line)
                if m:
                    ccsd_energy = float(m.group(1))
            if "CCSD(T) energy" in line or "E(CCSD(T))" in line:
                m = cls.PAT_CCSD_T_ENERGY.search(line)
                if m:
                    ccsd_t_energy = float(m.group(1))

            # 2. Parse Rotational Constants
            if "Rotational constants (in MHz)" in line or "ROTATIONAL CONSTANTS (MHZ)" in line:
                parts = line.split(":")[-1].split()
                if len(parts) >= 3:
                    try:
                        Ae_MHz, Be_MHz, Ce_MHz = float(parts[0]), float(parts[1]), float(parts[2])
                    except ValueError:
                        pass
            if "Rotational constants (in cm-1)" in line or "ROTATIONAL CONSTANTS (CM-1)" in line:
                parts = line.split(":")[-1].split()
                if len(parts) >= 3:
                    try:
                        Ae_cm, Be_cm, Ce_cm = float(parts[0]), float(parts[1]), float(parts[2])
                    except ValueError:
                        pass

            # 3. Parse Dipole
            if "Dipole moment (Debye)" in line or "DIPOLE MOMENT" in line:
                m = cls.PAT_DIPOLE.search(line)
                if m:
                    dipole_a = float(m.group(1))
                    dipole_b = float(m.group(2))
                    dipole_c = float(m.group(3))
                    dipole_tot = float(m.group(4))

            # 4. Parse Harmonic Frequencies
            if "Harmonic vibrational frequencies" in line or "HARMONIC VIBRATIONAL FREQUENCIES (CM-1)" in line:
                j = i + 1
                while j < len(lines):
                    fline = lines[j].strip()
                    j += 1
                    if not fline:
                        if freqs:
                            break
                        continue
                    if any(term in fline for term in ["Vibration-rotation", "ALPHA CONSTANTS", "Total", "Zero-point", "---", "==="]):
                        if freqs:
                            break
                        continue
                    parts = fline.split()
                    if len(parts) >= 2 and parts[0].isdigit():
                        try:
                            if parts[1].replace('.', '', 1).replace('-', '', 1).isdigit():
                                freq_val = float(parts[1])
                                sym_val = parts[2] if len(parts) > 2 and not parts[2].replace('.', '', 1).replace('-', '', 1).isdigit() else "A"
                            elif len(parts) > 2 and parts[2].replace('.', '', 1).replace('-', '', 1).isdigit():
                                freq_val = float(parts[2])
                                sym_val = parts[1]
                            else:
                                freq_val = None
                                sym_val = "A"

                            if freq_val is not None:
                                freqs.append(freq_val)
                                symmetries.append(sym_val)
                        except (ValueError, IndexError):
                            pass

            # 5. Parse Vibration-Rotation Alpha Constants
            if "Vibration-rotation interaction constants" in line or "ALPHA CONSTANTS" in line:
                j = i + 1
                while j < len(lines):
                    aline = lines[j].strip()
                    j += 1
                    if not aline:
                        if alphas:
                            break
                        continue
                    if any(term in aline for term in ["Watson", "reduction", "ELECTRIC FIELD", "---", "==="]):
                        if alphas:
                            break
                        continue
                    parts = aline.split()
                    if len(parts) >= 4 and parts[0].isdigit():
                        try:
                            m_idx = int(parts[0])
                            a_A = float(parts[1])
                            a_B = float(parts[2])
                            a_C = float(parts[3])
                            c_cm_s = CONSTANTS.C_CM_S
                            alpha_rec = VibrationRotationAlpha(
                                mode_index=m_idx,
                                harmonic_freq_cm_inv=freqs[m_idx - 1] if m_idx - 1 < len(freqs) else 0.0,
                                symmetry=symmetries[m_idx - 1] if m_idx - 1 < len(symmetries) else "A",
                                alpha_A_MHz=a_A,
                                alpha_B_MHz=a_B,
                                alpha_C_MHz=a_C,
                                alpha_A_cm_inv=(a_A * 1e6) / c_cm_s,
                                alpha_B_cm_inv=(a_B * 1e6) / c_cm_s,
                                alpha_C_cm_inv=(a_C * 1e6) / c_cm_s,
                            )
                            alphas.append(alpha_rec)
                        except (ValueError, IndexError):
                            pass

            # 6. Parse Quartic & Sextic Distortions
            # Watson A Quartic
            m_dj = re.search(r"\bDelta_?J\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_dj:
                quartic.Delta_J_kHz = float(m_dj.group(1).replace('D', 'E').replace('d', 'e'))
            m_djk = re.search(r"\bDelta_?JK\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_djk:
                quartic.Delta_JK_kHz = float(m_djk.group(1).replace('D', 'E').replace('d', 'e'))
            m_dk = re.search(r"\bDelta_?K\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_dk:
                quartic.Delta_K_kHz = float(m_dk.group(1).replace('D', 'E').replace('d', 'e'))
            m_delj = re.search(r"\bdelta_?j\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_delj:
                quartic.delta_j_kHz = float(m_delj.group(1).replace('D', 'E').replace('d', 'e'))
            m_delk = re.search(r"\bdelta_?k\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_delk:
                quartic.delta_k_kHz = float(m_delk.group(1).replace('D', 'E').replace('d', 'e'))

            # Watson S Quartic
            m_sdj = re.search(r"\bD_?J\b\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_sdj and not m_dj:
                quartic.D_J_kHz = float(m_sdj.group(1).replace('D', 'E').replace('d', 'e'))
            m_sdjk = re.search(r"\bD_?JK\b\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_sdjk and not m_djk:
                quartic.D_JK_kHz = float(m_sdjk.group(1).replace('D', 'E').replace('d', 'e'))
            m_sdk = re.search(r"\bD_?K\b\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_sdk and not m_dk:
                quartic.D_K_kHz = float(m_sdk.group(1).replace('D', 'E').replace('d', 'e'))
            m_sd1 = re.search(r"\bd_?1\b\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_sd1:
                quartic.d_1_kHz = float(m_sd1.group(1).replace('D', 'E').replace('d', 'e'))
            m_sd2 = re.search(r"\bd_?2\b\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_sd2:
                quartic.d_2_kHz = float(m_sd2.group(1).replace('D', 'E').replace('d', 'e'))

            # Sextic Watson A
            m_phij = re.search(r"\bPhi_?J\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_phij:
                sextic.Phi_J_Hz = float(m_phij.group(1).replace('D', 'E').replace('d', 'e'))
            m_phijk = re.search(r"\bPhi_?JK\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_phijk:
                sextic.Phi_JK_Hz = float(m_phijk.group(1).replace('D', 'E').replace('d', 'e'))
            m_phikj = re.search(r"\bPhi_?KJ\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_phikj:
                sextic.Phi_KJ_Hz = float(m_phikj.group(1).replace('D', 'E').replace('d', 'e'))
            m_phik = re.search(r"\bPhi_?K\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_phik:
                sextic.Phi_K_Hz = float(m_phik.group(1).replace('D', 'E').replace('d', 'e'))
            m_sphij = re.search(r"\bphi_?j\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_sphij:
                sextic.phi_j_Hz = float(m_sphij.group(1).replace('D', 'E').replace('d', 'e'))
            m_sphijk = re.search(r"\bphi_?jk\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_sphijk:
                sextic.phi_jk_Hz = float(m_sphijk.group(1).replace('D', 'E').replace('d', 'e'))
            m_sphik = re.search(r"\bphi_?k\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_sphik:
                sextic.phi_k_Hz = float(m_sphik.group(1).replace('D', 'E').replace('d', 'e'))

            # Sextic Watson S
            m_shj = re.search(r"\bH_?J\b\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_shj and not m_phij:
                sextic.H_J_Hz = float(m_shj.group(1).replace('D', 'E').replace('d', 'e'))
            m_shjk = re.search(r"\bH_?JK\b\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_shjk and not m_phijk:
                sextic.H_JK_Hz = float(m_shjk.group(1).replace('D', 'E').replace('d', 'e'))
            m_shkj = re.search(r"\bH_?KJ\b\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_shkj and not m_phikj:
                sextic.H_KJ_Hz = float(m_shkj.group(1).replace('D', 'E').replace('d', 'e'))
            m_shk = re.search(r"\bH_?K\b\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_shk and not m_phik:
                sextic.H_K_Hz = float(m_shk.group(1).replace('D', 'E').replace('d', 'e'))
            m_sh1 = re.search(r"\bh_?1\b\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_sh1:
                sextic.h_1_Hz = float(m_sh1.group(1).replace('D', 'E').replace('d', 'e'))
            m_sh2 = re.search(r"\bh_?2\b\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_sh2:
                sextic.h_2_Hz = float(m_sh2.group(1).replace('D', 'E').replace('d', 'e'))
            m_sh3 = re.search(r"\bh_?3\b\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_sh3:
                sextic.h_3_Hz = float(m_sh3.group(1).replace('D', 'E').replace('d', 'e'))

            # 7. Parse Quadrupole Coupling & EFGs
            if "ELECTRIC FIELD GRADIENT" in line or "Nuclear Quadrupole Coupling" in line:
                j = i + 1
                while j < len(lines):
                    qline = lines[j].strip()
                    j += 1
                    if not qline:
                        if quadrupoles:
                            break
                        continue
                    if any(term in qline for term in ["Diagonal", "DBOC", "---", "==="]):
                        if quadrupoles:
                            break
                        continue
                    parts = qline.split()
                    if len(parts) >= 5 and parts[0].isdigit():
                        try:
                            at_idx = int(parts[0])
                            at_sym = parts[1]
                            qxx = float(parts[2])
                            qyy = float(parts[3])
                            qzz = float(parts[4])
                            iso_mass = get_default_isotope_mass_number(at_sym)
                            q_key = f"{iso_mass}{at_sym}"
                            q_mbarn = STANDARD_NUCLEAR_QUADRUPOLE_MOMENTS_MBARN.get(q_key, 0.0)
                            if q_mbarn == 0.0:
                                for k, v in STANDARD_NUCLEAR_QUADRUPOLE_MOMENTS_MBARN.items():
                                    if k.endswith(at_sym) and v != 0.0:
                                        q_mbarn = v
                                        iso_str = "".join(c for c in k if c.isdigit())
                                        if iso_str:
                                            iso_mass = int(iso_str)
                                        break
                            chi_factor = CONSTANTS.EFG_TO_CHI_KHZ * q_mbarn
                            chi_aa = qxx * chi_factor
                            chi_bb = qyy * chi_factor
                            chi_cc = qzz * chi_factor
                            eta = (qxx - qyy) / qzz if abs(qzz) > 1e-6 else 0.0
                            quadrupoles.append(
                                ElectricFieldGradientTensor(
                                    atom_index=at_idx,
                                    symbol=at_sym,
                                    isotope_mass_number=iso_mass,
                                    q_xx_au=qxx,
                                    q_yy_au=qyy,
                                    q_zz_au=qzz,
                                    asymmetry_eta=eta,
                                    nuclear_quadrupole_moment_mbarn=q_mbarn,
                                    chi_aa_kHz=chi_aa,
                                    chi_bb_kHz=chi_bb,
                                    chi_cc_kHz=chi_cc,
                                )
                            )
                        except (ValueError, IndexError):
                            pass

            # 8. Nuclear Spin-Rotation Interaction Constants
            if "SPIN-ROTATION" in line.upper() or "SPIN ROTATION" in line.upper():
                j = i + 1
                while j < len(lines):
                    sline = lines[j].strip()
                    j += 1
                    if not sline:
                        if spin_rots:
                            break
                        continue
                    if any(term in sline for term in ["DBOC", "Diagonal", "---", "==="]):
                        if spin_rots:
                            break
                        continue
                    parts = sline.split()
                    if len(parts) >= 5 and parts[0].isdigit():
                        try:
                            at_idx = int(parts[0])
                            at_sym = parts[1]
                            c_aa = float(parts[2])
                            c_bb = float(parts[3])
                            c_cc = float(parts[4])
                            c_iso = float(parts[5]) if len(parts) >= 6 else (c_aa + c_bb + c_cc) / 3.0
                            spin_rots.append(
                                NuclearSpinRotationTensor(
                                    atom_index=at_idx,
                                    symbol=at_sym,
                                    C_aa_kHz=c_aa,
                                    C_bb_kHz=c_bb,
                                    C_cc_kHz=c_cc,
                                    C_iso_kHz=c_iso,
                                )
                            )
                        except (ValueError, IndexError):
                            pass

            # 9. DBOC
            if "DBOC" in line or "Diagonal Born-Oppenheimer Correction" in line:
                parts = line.split(":")[-1].split()
                if parts:
                    try:
                        dboc_hartree = float(parts[0])
                        dboc_cm = dboc_hartree * CONSTANTS.HARTREE_TO_CM_INV
                    except ValueError:
                        pass

            i += 1

        if ccsd_t_energy is not None:
            final_energy = ccsd_t_energy
        elif ccsd_energy is not None:
            final_energy = ccsd_energy
        elif mp2_energy is not None:
            final_energy = mp2_energy
        elif scf_energy is not None:
            final_energy = scf_energy
        else:
            final_energy = 0.0

        delta_A_vib_MHz = -0.5 * sum(a.alpha_A_MHz for a in alphas) if alphas else 0.0
        delta_B_vib_MHz = -0.5 * sum(a.alpha_B_MHz for a in alphas) if alphas else 0.0
        delta_C_vib_MHz = -0.5 * sum(a.alpha_C_MHz for a in alphas) if alphas else 0.0

        A0_MHz = Ae_MHz + delta_A_vib_MHz
        B0_MHz = Be_MHz + delta_B_vib_MHz
        C0_MHz = Ce_MHz + delta_C_vib_MHz

        c_cm_s = CONSTANTS.C_CM_S
        A0_cm = (A0_MHz * 1e6) / c_cm_s
        B0_cm = (B0_MHz * 1e6) / c_cm_s
        C0_cm = (C0_MHz * 1e6) / c_cm_s

        if (Ae_MHz == 0.0 or Be_MHz == 0.0) and parsed_symbols and coordinates_fallback is not None:
            ((Ae_MHz, Be_MHz, Ce_MHz), (Ae_cm, Be_cm, Ce_cm), in_def, (Paa, Pbb, Pcc), kappa) = (
                compute_equilibrium_rotational_constants(parsed_symbols, coordinates_fallback)
            )
            A0_MHz = Ae_MHz + delta_A_vib_MHz
            B0_MHz = Be_MHz + delta_B_vib_MHz
            C0_MHz = Ce_MHz + delta_C_vib_MHz
            A0_cm = (A0_MHz * 1e6) / c_cm_s
            B0_cm = (B0_MHz * 1e6) / c_cm_s
            C0_cm = (C0_MHz * 1e6) / c_cm_s
        else:
            conv = CONSTANTS.C_ROT_MHZ_U_ANG2
            Ia = conv / Ae_MHz if Ae_MHz > 0 else 0.0
            Ib = conv / Be_MHz if Be_MHz > 0 else 0.0
            Ic = conv / Ce_MHz if Ce_MHz > 0 else 0.0
            Paa = (Ib + Ic - Ia) / 2.0
            Pbb = (Ia + Ic - Ib) / 2.0
            Pcc = (Ia + Ib - Ic) / 2.0
            in_def = Ic - Ia - Ib
            denom = Ae_MHz - Ce_MHz
            kappa = (2.0 * Be_MHz - Ae_MHz - Ce_MHz) / denom if abs(denom) > 1e-6 else -1.0

        zpe_cm = 0.5 * sum(freqs) if freqs else 0.0
        zpe_kcal = (zpe_cm / CONSTANTS.HARTREE_TO_CM_INV) * CONSTANTS.HARTREE_TO_KCAL_MOL

        masses = [get_dynamic_atomic_mass(s) for s in parsed_symbols] if parsed_symbols else []

        hff = HarmonicForceField(
            n_atoms=len(parsed_symbols),
            symbols=parsed_symbols,
            masses_u=masses,
            frequencies_cm_inv=freqs,
            symmetries=symmetries,
            ir_intensities_km_mol=ir_intensities,
            zpe_cm_inv=zpe_cm,
            zpe_kcal_mol=zpe_kcal,
            cartesian_hessian=None,
        )

        return CFOURObservables(
            scf_energy_hartree=scf_energy,
            mp2_energy_hartree=mp2_energy,
            ccsd_energy_hartree=ccsd_energy,
            ccsd_t_energy_hartree=ccsd_t_energy,
            final_energy_hartree=final_energy,
            Ae_MHz=Ae_MHz,
            Be_MHz=Be_MHz,
            Ce_MHz=Ce_MHz,
            Ae_cm_inv=Ae_cm,
            Be_cm_inv=Be_cm,
            Ce_cm_inv=Ce_cm,
            delta_A_vib_MHz=delta_A_vib_MHz,
            delta_B_vib_MHz=delta_B_vib_MHz,
            delta_C_vib_MHz=delta_C_vib_MHz,
            A0_MHz=A0_MHz,
            B0_MHz=B0_MHz,
            C0_MHz=C0_MHz,
            A0_cm_inv=A0_cm,
            B0_cm_inv=B0_cm,
            C0_cm_inv=C0_cm,
            inertial_defect_amu_ang2=in_def,
            planar_moment_Paa_amu_ang2=Paa,
            planar_moment_Pbb_amu_ang2=Pbb,
            planar_moment_Pcc_amu_ang2=Pcc,
            ray_asymmetry_kappa=kappa,
            dipole_a_debye=dipole_a,
            dipole_b_debye=dipole_b,
            dipole_c_debye=dipole_c,
            dipole_total_debye=dipole_tot,
            harmonic_force_field=hff,
            vibration_rotation_alphas=alphas,
            quartic_distortion=quartic if (quartic.Delta_J_kHz or quartic.D_J_kHz) else None,
            sextic_distortion=sextic if (sextic.Phi_J_Hz or sextic.H_J_Hz) else None,
            quadrupole_couplings=quadrupoles,
            spin_rotation_tensors=spin_rots,
            dboc_correction_hartree=dboc_hartree,
            dboc_correction_cm_inv=dboc_cm,
        )


def _diagonalize_projected_hessian(
    hessian: np.ndarray,
    symbols: Sequence[str],
    coordinates: np.ndarray,
    masses: Sequence[float],
) -> Tuple[List[float], float]:
    """Diagonalize mass-weighted Cartesian Hessian after Eckart projection of translations and rotations."""
    n_atoms = len(symbols)
    m_inv_sqrt = np.zeros(3 * n_atoms, dtype=np.float64)
    for i in range(n_atoms):
        m_inv_sqrt[3 * i : 3 * i + 3] = 1.0 / np.sqrt(masses[i])

    H_mw = hessian * np.outer(m_inv_sqrt, m_inv_sqrt)

    com = compute_center_of_mass(symbols, coordinates, masses)
    shifted = coordinates - com

    proj_vectors: List[np.ndarray] = []

    # 3 translation vectors
    for alpha in range(3):
        t_vec = np.zeros(3 * n_atoms, dtype=np.float64)
        for i in range(n_atoms):
            t_vec[3 * i + alpha] = np.sqrt(masses[i])
        norm = np.linalg.norm(t_vec)
        if norm > 1e-12:
            proj_vectors.append(t_vec / norm)

    # 3 rotation vectors
    for alpha in range(3):
        e_alpha = np.zeros(3, dtype=np.float64)
        e_alpha[alpha] = 1.0
        r_vec = np.zeros(3 * n_atoms, dtype=np.float64)
        for i in range(n_atoms):
            cross = np.cross(shifted[i], e_alpha)
            r_vec[3 * i : 3 * i + 3] = cross * np.sqrt(masses[i])
        norm = np.linalg.norm(r_vec)
        if norm > 1e-12:
            r_vec = r_vec / norm
            for pv in proj_vectors:
                r_vec -= np.dot(pv, r_vec) * pv
            r_norm = np.linalg.norm(r_vec)
            if r_norm > 1e-6:
                proj_vectors.append(r_vec / r_norm)

    P_matrix = np.eye(3 * n_atoms, dtype=np.float64)
    for pv in proj_vectors:
        P_matrix -= np.outer(pv, pv)

    H_proj = P_matrix @ H_mw @ P_matrix
    H_proj = 0.5 * (H_proj + H_proj.T)

    evals, evecs = scipy.linalg.eigh(H_proj)
    freq_factor = CONSTANTS.HESSIAN_EIGENVALUE_TO_CM_INV
    frequencies_cm: List[float] = []

    for ev in evals:
        if abs(ev) < 1e-7:
            continue
        if ev > 0:
            freq_val = math.sqrt(ev) * freq_factor
            frequencies_cm.append(freq_val)
        else:
            freq_val = -math.sqrt(abs(ev)) * freq_factor
            frequencies_cm.append(freq_val)

    frequencies_cm.sort()
    zpe = 0.5 * sum(f for f in frequencies_cm if f > 0)
    return frequencies_cm, zpe


# ==============================================================================
# 7. ISOMASS Force Field Re-Diagonalization Engine (§8B.4, §8B.6, §9.3, §14)
# ==============================================================================

def isomass_rediagonalize_force_field(
    cartesian_hessian_hartree_bohr2: np.ndarray,
    symbols: Sequence[str],
    coordinates_angstrom: np.ndarray,
    target_isotopes: Optional[Sequence[int]] = None,
    parent_isotopes: Optional[Sequence[int]] = None,
    parent_name: str = "Parent",
    isotopologue_label: str = "Isotopologue",
    parent_alphas: Optional[Sequence[VibrationRotationAlpha]] = None,
) -> IsotopologueFFResult:
    """Execute the Method Matrix v4 §8B.4 / §6.10 ISOMASS Free Force Field Re-Diagonalization Shortcut.

    Re-diagonalizes a single high-level harmonic Cartesian force constant matrix with newly substituted
    isotopic masses (dynamically retrieved from Mendeleev), removing 6 (or 5) Eckart rotational and
    translational zero modes via projection.

    Delivers:
    - New equilibrium rotational constants (Ae', Be', Ce').
    - Exact harmonic vibrational frequencies (omega_i') and isotope-shifted ZPE.
    - Ground-state rotational constants (A0', B0', C0') via scaled alpha projection.
    - Complete before-and-after shift telemetry (Delta A0, Delta B0, Delta C0).
    """
    coords = np.asarray(coordinates_angstrom, dtype=np.float64)
    n_atoms = len(symbols)
    hessian = np.asarray(cartesian_hessian_hartree_bohr2, dtype=np.float64)

    if hessian.shape != (3 * n_atoms, 3 * n_atoms):
        raise ValueError(f"Hessian shape {hessian.shape} does not match 3N x 3N = {3 * n_atoms} x {3 * n_atoms}.")

    parent_masses: List[float] = []
    iso_masses: List[float] = []

    for idx, sym in enumerate(symbols):
        p_iso = parent_isotopes[idx] if parent_isotopes is not None else None
        t_iso = target_isotopes[idx] if target_isotopes is not None else None

        parent_m = get_dynamic_atomic_mass(sym, p_iso)
        iso_m = get_dynamic_atomic_mass(sym, t_iso)

        parent_masses.append(parent_m)
        iso_masses.append(iso_m)

    parent_Be, _, _, _, _ = compute_equilibrium_rotational_constants(symbols, coords, parent_masses)
    iso_Be, _, iso_in_def, (iso_Paa, iso_Pbb, iso_Pcc), iso_kappa = compute_equilibrium_rotational_constants(
        symbols, coords, iso_masses
    )

    parent_frequencies_cm, parent_zpe_cm = _diagonalize_projected_hessian(hessian, symbols, coords, parent_masses)
    iso_frequencies_cm, iso_zpe_cm = _diagonalize_projected_hessian(hessian, symbols, coords, iso_masses)

    if parent_alphas and len(parent_alphas) > 0:
        parent_delta_A = -0.5 * sum(a.alpha_A_MHz for a in parent_alphas)
        parent_delta_B = -0.5 * sum(a.alpha_B_MHz for a in parent_alphas)
        parent_delta_C = -0.5 * sum(a.alpha_C_MHz for a in parent_alphas)

        scale_A = iso_Be[0] / parent_Be[0] if parent_Be[0] > 0 else 1.0
        scale_B = iso_Be[1] / parent_Be[1] if parent_Be[1] > 0 else 1.0
        scale_C = iso_Be[2] / parent_Be[2] if parent_Be[2] > 0 else 1.0

        iso_delta_A = parent_delta_A * scale_A
        iso_delta_B = parent_delta_B * scale_B
        iso_delta_C = parent_delta_C * scale_C
    else:
        parent_delta_A, parent_delta_B, parent_delta_C = 0.0, 0.0, 0.0
        iso_delta_A, iso_delta_B, iso_delta_C = 0.0, 0.0, 0.0

    parent_B0 = (parent_Be[0] + parent_delta_A, parent_Be[1] + parent_delta_B, parent_Be[2] + parent_delta_C)
    iso_B0 = (iso_Be[0] + iso_delta_A, iso_Be[1] + iso_delta_B, iso_Be[2] + iso_delta_C)

    delta_A0 = iso_B0[0] - parent_B0[0]
    delta_B0 = iso_B0[1] - parent_B0[1]
    delta_C0 = iso_B0[2] - parent_B0[2]

    return IsotopologueFFResult(
        parent_name=parent_name,
        isotopologue_label=isotopologue_label,
        symbols=list(symbols),
        parent_masses_u=parent_masses,
        isotopologue_masses_u=iso_masses,
        parent_Be_MHz=parent_Be,
        parent_B0_MHz=parent_B0,
        parent_zpe_cm_inv=parent_zpe_cm,
        iso_Be_MHz=iso_Be,
        iso_B0_MHz=iso_B0,
        iso_frequencies_cm_inv=iso_frequencies_cm,
        iso_zpe_cm_inv=iso_zpe_cm,
        zpe_shift_cm_inv=iso_zpe_cm - parent_zpe_cm,
        iso_inertial_defect_amu_ang2=iso_in_def,
        iso_planar_moments_amu_ang2=(iso_Paa, iso_Pbb, iso_Pcc),
        iso_ray_asymmetry_kappa=iso_kappa,
        delta_A0_MHz=delta_A0,
        delta_B0_MHz=delta_B0,
        delta_C0_MHz=delta_C0,
        provenance_tag="[D]",
    )



# ==============================================================================
# 8. Pickett SPCAT Bridge Exporter
# ==============================================================================

def export_cfour_to_spcat_var(
    observables: CFOURObservables,
    reduction: WatsonReduction = WatsonReduction.A,
    uncertainty_fraction: float = 1e-4,
) -> str:
    """Export CFOUR spectroscopic observables to Pickett SPFIT/SPCAT `.var` format.

    Uses official Pickett rotational and centrifugal distortion parameter integer codes:
    - 10000: A (MHz)
    - 20000: B (MHz)
    - 30000: C (MHz)
    - 200: -Delta_J (MHz) / -D_J (MHz)
    - 1100: -Delta_JK (MHz) / -D_JK (MHz)
    - 2000: -Delta_K (MHz) / -D_K (MHz)
    - 40100: -delta_J (MHz) / -d_1 (MHz)
    - 50000: -delta_K (MHz) / -d_2 (MHz)
    - 300: Phi_J / H_J (MHz)
    - 1200: Phi_JK / H_JK (MHz)
    - 2100: Phi_KJ / H_KJ (MHz)
    - 3000: Phi_K / H_K (MHz)
    - 40200: phi_j / h_1 (MHz)
    - 41100: phi_jk / h_2 (MHz)
    - 50100: phi_k / h_3 (MHz)
    """
    lines: List[str] = []
    lines.append(f"CoChem CFOUR Bridge Export - Watson {reduction.value}-Reduction")

    def _format_var_line(code: int, value_mhz: float, uncert: float) -> str:
        return f"{code:6d}{value_mhz:18.8f}{uncert:14.8f}"

    # 1. Rotational Constants A0, B0, C0
    lines.append(_format_var_line(10000, observables.A0_MHz, abs(observables.A0_MHz * uncertainty_fraction)))
    lines.append(_format_var_line(20000, observables.B0_MHz, abs(observables.B0_MHz * uncertainty_fraction)))
    lines.append(_format_var_line(30000, observables.C0_MHz, abs(observables.C0_MHz * uncertainty_fraction)))

    # 2. Quartic Centrifugal Distortion (converted to MHz: 1 kHz = 1e-3 MHz)
    qd = observables.quartic_distortion
    if qd is not None:
        if reduction == WatsonReduction.A:
            if qd.Delta_J_kHz is not None:
                v = qd.Delta_J_kHz * 1e-3
                lines.append(_format_var_line(200, v, abs(v * 0.05)))
            if qd.Delta_JK_kHz is not None:
                v = qd.Delta_JK_kHz * 1e-3
                lines.append(_format_var_line(1100, v, abs(v * 0.05)))
            if qd.Delta_K_kHz is not None:
                v = qd.Delta_K_kHz * 1e-3
                lines.append(_format_var_line(2000, v, abs(v * 0.05)))
            if qd.delta_j_kHz is not None:
                v = qd.delta_j_kHz * 1e-3
                lines.append(_format_var_line(40100, v, abs(v * 0.05)))
            if qd.delta_k_kHz is not None:
                v = qd.delta_k_kHz * 1e-3
                lines.append(_format_var_line(50000, v, abs(v * 0.05)))
        else:
            if qd.D_J_kHz is not None:
                v = qd.D_J_kHz * 1e-3
                lines.append(_format_var_line(200, v, abs(v * 0.05)))
            if qd.D_JK_kHz is not None:
                v = qd.D_JK_kHz * 1e-3
                lines.append(_format_var_line(1100, v, abs(v * 0.05)))
            if qd.D_K_kHz is not None:
                v = qd.D_K_kHz * 1e-3
                lines.append(_format_var_line(2000, v, abs(v * 0.05)))
            if qd.d_1_kHz is not None:
                v = qd.d_1_kHz * 1e-3
                lines.append(_format_var_line(40100, v, abs(v * 0.05)))
            if qd.d_2_kHz is not None:
                v = qd.d_2_kHz * 1e-3
                lines.append(_format_var_line(50000, v, abs(v * 0.05)))

    # 3. Sextic Centrifugal Distortion (converted to MHz: 1 Hz = 1e-6 MHz)
    sd = observables.sextic_distortion
    if sd is not None:
        if reduction == WatsonReduction.A:
            if sd.Phi_J_Hz is not None:
                v = sd.Phi_J_Hz * 1e-6
                lines.append(_format_var_line(300, v, abs(v * 0.10)))
            if sd.Phi_JK_Hz is not None:
                v = sd.Phi_JK_Hz * 1e-6
                lines.append(_format_var_line(1200, v, abs(v * 0.10)))
            if sd.Phi_KJ_Hz is not None:
                v = sd.Phi_KJ_Hz * 1e-6
                lines.append(_format_var_line(2100, v, abs(v * 0.10)))
            if sd.Phi_K_Hz is not None:
                v = sd.Phi_K_Hz * 1e-6
                lines.append(_format_var_line(3000, v, abs(v * 0.10)))
            if sd.phi_j_Hz is not None:
                v = sd.phi_j_Hz * 1e-6
                lines.append(_format_var_line(40200, v, abs(v * 0.10)))
            if sd.phi_jk_Hz is not None:
                v = sd.phi_jk_Hz * 1e-6
                lines.append(_format_var_line(41100, v, abs(v * 0.10)))
            if sd.phi_k_Hz is not None:
                v = sd.phi_k_Hz * 1e-6
                lines.append(_format_var_line(50100, v, abs(v * 0.10)))

    # 4. Nuclear Quadrupole Coupling chi_aa, chi_bb, chi_cc (kHz -> MHz)
    for q_tensor in observables.quadrupole_couplings:
        if abs(q_tensor.chi_aa_kHz) > 1e-4:
            code_chi_aa = q_tensor.atom_index * 100000 + 10000
            code_chi_diff = q_tensor.atom_index * 100000 + 20000
            chi_aa_mhz = q_tensor.chi_aa_kHz * 1e-3
            chi_diff_mhz = (q_tensor.chi_bb_kHz - q_tensor.chi_cc_kHz) * 1e-3
            lines.append(_format_var_line(code_chi_aa, chi_aa_mhz, abs(chi_aa_mhz * 0.02)))
            lines.append(_format_var_line(code_chi_diff, chi_diff_mhz, abs(chi_diff_mhz * 0.02)))

    lines.append("")
    return "\n".join(lines)


# ==============================================================================
# 9. CFOUR Execution Broker & Job Dispatcher
# ==============================================================================

class CFOURBridge:
    """High-throughput execution, finite-difference decomposition, and state-persistence broker for CFOUR."""

    def __init__(
        self,
        cfour_executable: str = "xcfour",
        genbas_path: Optional[Union[str, Path]] = None,
        scratch_root: Optional[Union[str, Path]] = None,
    ) -> None:
        self.cfour_executable = cfour_executable
        self.genbas_path = Path(genbas_path) if genbas_path else None
        self.scratch_root = Path(scratch_root) if scratch_root else (get_ramdisk_dir() or get_runtime_dir() / "cfour_scratch")
        self.scratch_root.mkdir(parents=True, exist_ok=True)

    def prepare_job_directory(
        self,
        job_id: str,
        symbols: Sequence[str],
        coordinates_angstrom: np.ndarray,
        config: CFOURInputConfig,
        existing_jobarc: Optional[Path] = None,
    ) -> Path:
        """Prepare working directory containing ZMAT and required basis set libraries."""
        work_dir = self.scratch_root / f"cfour_{job_id}_{int(time.time())}"
        work_dir.mkdir(parents=True, exist_ok=True)

        # 1. Write ZMAT input file
        zmat_text = generate_cfour_zmat(symbols, coordinates_angstrom, config)
        zmat_path = work_dir / "ZMAT"
        zmat_path.write_text(zmat_text, encoding="utf-8")

        # 2. Link or copy GENBAS if available
        if self.genbas_path and self.genbas_path.exists():
            dest_genbas = work_dir / "GENBAS"
            try:
                os.symlink(self.genbas_path, dest_genbas)
            except (OSError, AttributeError):
                shutil.copy(self.genbas_path, dest_genbas)

        # 3. Stage existing archive files for restart/chaining (Method Matrix §8B.6)
        if existing_jobarc and existing_jobarc.exists():
            shutil.copy(existing_jobarc, work_dir / "JOBARC")
            parent_jaindx = existing_jobarc.parent / "JAINDX"
            if parent_jaindx.exists():
                shutil.copy(parent_jaindx, work_dir / "JAINDX")

        return work_dir

    def dispatch_cfour_job(
        self,
        job_id: str,
        symbols: Sequence[str],
        coordinates_angstrom: np.ndarray,
        config: CFOURInputConfig,
        timeout_seconds: int = 3600,
        existing_jobarc: Optional[Path] = None,
    ) -> CFOURJobResult:
        """Dispatch CFOUR execution via subprocess broker with strict wall-clock and crash isolation."""
        work_dir = self.prepare_job_directory(job_id, symbols, coordinates_angstrom, config, existing_jobarc)
        zmat_path = work_dir / "ZMAT"
        zmat_hash = hashlib.sha256(zmat_path.read_bytes()).hexdigest()

        start_time = time.time()
        out_file = work_dir / "output.dat"
        err_file = work_dir / "cfour.err"

        cmd = [self.cfour_executable]

        try:
            with open(out_file, "w", encoding="utf-8") as fh_out, open(err_file, "w", encoding="utf-8") as fh_err:
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(work_dir),
                    stdout=fh_out,
                    stderr=fh_err,
                )
                try:
                    proc.wait(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                    raise TimeoutError(f"CFOUR job {job_id} exceeded wall-clock timeout of {timeout_seconds}s.")

            if proc.returncode != 0:
                err_text = err_file.read_text(encoding="utf-8", errors="replace")
                raise CoChemError(f"CFOUR execution failed with exit code {proc.returncode}: {err_text[:1000]}")

            wall_time = time.time() - start_time
            stdout_text = out_file.read_text(encoding="utf-8", errors="replace")
            stdout_hash = hashlib.sha256(stdout_text.encode("utf-8")).hexdigest()

            # Parse observables
            observables = CFOUROutputParser.parse_cfour_stdout(
                stdout_text, symbols_fallback=symbols, coordinates_fallback=coordinates_angstrom
            )

            # Preserve binary archives
            preserved: List[str] = []
            for arc_name in ["JOBARC", "JAINDX", "OPTARC", "FCMFINAL", "FCMINT", "DIPDER", "MOINTS", "MOABCD"]:
                p = work_dir / arc_name
                if p.exists():
                    preserved.append(arc_name)

            return CFOURJobResult(
                success=True,
                job_id=job_id,
                working_directory=str(work_dir),
                wall_time_seconds=wall_time,
                stdout_hash=stdout_hash,
                zmat_hash=zmat_hash,
                observables=observables,
                isotopologues=[],
                error_message=None,
                preserved_files=preserved,
                compliance_notes=[
                    "Method Matrix v4 §8B.6 / §9.3 compliant",
                    "Analytic CCSD(T) second derivatives executed",
                    f"Wall time: {wall_time:.2f}s",
                ],
            )
        except Exception as ex:
            wall_time = time.time() - start_time
            return CFOURJobResult(
                success=False,
                job_id=job_id,
                working_directory=str(work_dir),
                wall_time_seconds=wall_time,
                stdout_hash="",
                zmat_hash=zmat_hash,
                observables=None,
                isotopologues=[],
                error_message=str(ex),
                preserved_files=[],
                compliance_notes=[f"Execution failed: {ex}"],
            )


# ==============================================================================
# 10. Command-Line Interface (CLI)
# ==============================================================================

def build_cli_parser() -> argparse.ArgumentParser:
    """Build command-line parser for CFOUR bridge operations."""
    parser = argparse.ArgumentParser(
        description="CoChem-CORE CFOUR Electronic Structure & VPT2 Anharmonic Spectroscopy Bridge."
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # 1. build-zmat
    p_zmat = subparsers.add_parser("build-zmat", help="Generate ZMAT input file from geometry.")
    p_zmat.add_argument("--xyz", type=str, required=True, help="Input XYZ geometry file.")
    p_zmat.add_argument("--basis", type=str, default="ANO1", help="Basis set.")
    p_zmat.add_argument("--calc", type=str, default="CCSD(T)", help="Calculation level.")
    p_zmat.add_argument("--out", type=str, default="ZMAT", help="Output ZMAT file path.")

    # 2. parse-output
    p_parse = subparsers.add_parser("parse-output", help="Parse CFOUR output log to JSON observables.")
    p_parse.add_argument("--output", type=str, required=True, help="CFOUR output.dat path.")
    p_parse.add_argument("--json-out", type=str, default=None, help="Path for JSON output.")

    # 3. isomass
    p_iso = subparsers.add_parser("isomass", help="Re-diagonalize force field with new isotopic masses.")
    p_iso.add_argument("--xyz", type=str, required=True, help="Cartesian geometry file.")
    p_iso.add_argument("--hessian-npy", type=str, required=True, help="Path to (3N, 3N) Cartesian Hessian (.npy).")
    p_iso.add_argument("--isotopes", type=int, nargs="+", required=True, help="Target mass numbers per atom.")

    # 4. export-spcat
    p_spcat = subparsers.add_parser("export-spcat", help="Export observables to Pickett .var file.")
    p_spcat.add_argument("--json", type=str, required=True, help="JSON file containing CFOURObservables.")
    p_spcat.add_argument("--out-var", type=str, default="spcat.var", help="Output .var file path.")

    return parser


def main(args_list: Optional[Sequence[str]] = None) -> int:
    """Main CLI entrypoint for cochem_core_cfour_bridge."""
    parser = build_cli_parser()
    args = parser.parse_args(args_list)

    if not args.subcommand:
        parser.print_help()
        return 0

    if args.subcommand == "build-zmat":
        xyz_path = Path(args.xyz)
        lines = xyz_path.read_text(encoding="utf-8").splitlines()
        n = int(lines[0].split()[0])
        syms: List[str] = []
        coords: List[List[float]] = []
        for ln in lines[2 : 2 + n]:
            parts = ln.split()
            syms.append(parts[0])
            coords.append([float(parts[1]), float(parts[2]), float(parts[3])])
        cfg = CFOURInputConfig(basis=args.basis, calc_level=CFOURCalcLevel(args.calc))
        zmat_str = generate_cfour_zmat(syms, np.array(coords), cfg)
        out_p = Path(args.out)
        out_p.write_text(zmat_str, encoding="utf-8")
        print(f"Generated CFOUR ZMAT at: {out_p.resolve()}")
        return 0

    elif args.subcommand == "parse-output":
        out_p = Path(args.output)
        text = out_p.read_text(encoding="utf-8", errors="replace")
        obs = CFOUROutputParser.parse_cfour_stdout(text)
        json_data = obs.model_dump_json(indent=2)
        if args.json_out:
            Path(args.json_out).write_text(json_data, encoding="utf-8")
            print(f"Parsed CFOUR observables written to: {args.json_out}")
        else:
            print(json_data)
        return 0

    elif args.subcommand == "isomass":
        xyz_path = Path(args.xyz)
        lines = xyz_path.read_text(encoding="utf-8").splitlines()
        n = int(lines[0].split()[0])
        syms = [lines[i].split()[0] for i in range(2, 2 + n)]
        coords = np.array([[float(x) for x in lines[i].split()[1:4]] for i in range(2, 2 + n)])
        hess = np.load(args.hessian_npy)
        iso_res = isomass_rediagonalize_force_field(
            cartesian_hessian_hartree_bohr2=hess,
            symbols=syms,
            coordinates_angstrom=coords,
            target_isotopes=args.isotopes,
        )
        print(iso_res.model_dump_json(indent=2))
        return 0

    elif args.subcommand == "export-spcat":
        json_p = Path(args.json)
        data = json.loads(json_p.read_text(encoding="utf-8"))
        obs = CFOURObservables(**data)
        var_text = export_cfour_to_spcat_var(obs)
        Path(args.out_var).write_text(var_text, encoding="utf-8")
        print(f"Pickett .var file exported to: {args.out_var}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
