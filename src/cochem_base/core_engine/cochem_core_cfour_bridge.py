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
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Sequence,
    Set,
    Tuple,
    TextIO,
    Union,
)

import numpy as np
import scipy.linalg
from mendeleev import element
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cochem_base.core import cochem_constants as _constants
from cochem_base.config_loader import (
    get_artifact_dir,
    get_base_root,
    get_ramdisk_dir,
    get_repo_root,
    get_runtime_dir,
)
from cochem_base.exceptions import (
    BinaryNotFoundError,
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
    """Public conversion aliases and derived factors from the central CODATA registry."""

    # Planck constant (exact, SI definition 2019) [J * s]
    H_JS: float = _constants.PLANCK_CONSTANT_J_S
    # Boltzmann constant (exact, SI definition 2019) [J * K^-1]
    K_B_JK: float = _constants.BOLTZMANN_CONSTANT_J_K
    # Speed of light in vacuum (exact) [m * s^-1]
    C_M_S: float = _constants.SPEED_OF_LIGHT_M_S
    # Speed of light in vacuum (exact) [cm * s^-1]
    C_CM_S: float = _constants.SPEED_OF_LIGHT_CM_S
    # Rotational constant factor C_rot = h / (8 * pi^2) in [MHz * u * Angstrom^2]
    # CODATA 2022 / Method Matrix standard: 505379.0084350172 MHz * u * Angstrom^2
    C_ROT_MHZ_U_ANG2: float = _constants.C_ROT_MHZ_U_ANG2
    # Avogadro constant (exact) [mol^-1]
    N_A: float = _constants.AVOGADRO_CONSTANT
    # Atomic mass constant [kg]
    AMU_KG: float = _constants.ATOMIC_MASS_UNIT_KG
    # Bohr to Angstrom conversion factor
    BOHR_TO_ANGSTROM: float = _constants.BOHR_TO_ANGSTROM
    ANGSTROM_TO_BOHR: float = _constants.ANGSTROM_TO_BOHR
    # Hartree to eV
    HARTREE_TO_EV: float = _constants.HARTREE_TO_EV
    # Hartree to kcal/mol
    HARTREE_TO_KCAL_MOL: float = _constants.HARTREE_TO_KCAL_MOL
    # Hartree to kJ/mol
    HARTREE_TO_KJ_MOL: float = HARTREE_TO_KCAL_MOL * 4.184
    # Hartree to cm^-1
    HARTREE_TO_CM_INV: float = _constants.HARTREE_TO_CM_INV
    # Electric Field Gradient (a.u.) to Nuclear Quadrupole Coupling Constant (kHz)
    # e * EFG * Q / h; 1 mbarn = 1e-31 m^2 and 1 kHz = 1e3 Hz.
    EFG_TO_CHI_KHZ: float = _constants.HARTREE_TO_JOULE / (H_JS * _constants.BOHR_TO_METER**2) * 1e-34
    # Conversion factor from sqrt(Hartree / (bohr^2 * u)) to cm^-1:
    # 1 / (2 * pi * c) * sqrt(E_h / (a0^2 * m_u)), using central SI units.
    HESSIAN_EIGENVALUE_TO_CM_INV: float = math.sqrt(
        _constants.HARTREE_TO_JOULE / (_constants.BOHR_TO_METER**2 * AMU_KG)
    ) / (2.0 * math.pi * C_CM_S)


CONSTANTS = PhysicalConstants()

# Standard nuclear electric quadrupole moments Q in millibarns (1 mbarn = 10^-31 m^2 = 10^-3 barn)
# chi (kHz) = EFG (a.u.) * Q (mbarn) * CONSTANTS.EFG_TO_CHI_KHZ (Method Matrix §9.3 & §14.1)
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
    """Resolve an exact assigned/principal isotope mass from dynamic Mendeleev data."""
    from cochem_base.physics.isotopes import get_isotope_mass
    from cochem_base.physics.nuclide_resolver import get_element
    value = symbol_or_z
    if isinstance(value, bool):
        raise ValueError("A Boolean is not an atomic number")
    if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):
        value = get_element(int(value)).symbol
    return get_isotope_mass(value, mass_number)


def get_default_isotope_mass_number(symbol_or_z: Union[str, int]) -> int:
    """Resolve an assigned/principal mass number; never round an averaged weight."""
    from cochem_base.physics.isotopes import get_principal_isotope_mass_number
    from cochem_base.physics.nuclide_resolver import get_element
    if isinstance(symbol_or_z, bool):
        raise ValueError("A Boolean is not an atomic number")
    if isinstance(symbol_or_z, int) or (isinstance(symbol_or_z, str) and symbol_or_z.strip().isdigit()):
        symbol_or_z = get_element(int(symbol_or_z)).symbol
    return get_principal_isotope_mass_number(symbol_or_z)


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
    NONE = "NONE"          # Single-point electronic energy / properties (no Hessian)
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
    props: str = Field(
        default="OFF",
        description="Property evaluation (OFF by default; FIRST_ORDER silently suppresses VIB/ANHARM in CFOUR 2.1).",
    )
    memory_size_gb: int = Field(default=32, description="Global memory allocation in GB (MEMORY_SIZE=32, MEM_UNIT=GB).")
    memory_size_mb: Optional[int] = Field(default=None, ge=1, description="Optional global memory allocation in MB (overrides memory_size_gb when set).")
    scf_conv: int = Field(default=10, description="SCF convergence exponent (10 -> 10^-10).")
    cc_conv: int = Field(default=10, description="CC convergence exponent (10 -> 10^-10).")
    lineq_conv: int = Field(default=10, description="Linear equation convergence exponent (10 -> 10^-10; kept tight while CPHF_CONVER=12 avoids xcphf FP64 roundoff stall).")
    cphf_conver: int = Field(default=12, ge=1, le=15, description="CPHF response convergence exponent (12 -> 10^-12; avoids CFOUR 2.1 10^-16 FP64 roundoff abort while keeping LINEQ_CONV=10).")
    cphf_maxcyc: int = Field(default=128, ge=1, description="Maximum CPHF cycles for analytic second derivatives.")
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
    alpha_A_cm_inv: float = Field(default=0.0, description="Alpha constant for A in cm^-1.")
    alpha_B_cm_inv: float = Field(default=0.0, description="Alpha constant for B in cm^-1.")
    alpha_C_cm_inv: float = Field(default=0.0, description="Alpha constant for C in cm^-1.")


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
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    n_atoms: int = Field(..., description="Number of atoms.")
    symbols: List[str] = Field(..., description="Atom symbols.")
    masses_u: List[float] = Field(..., description="Atomic masses in unified atomic mass units.")
    frequencies_cm_inv: List[float] = Field(..., description="Harmonic vibrational frequencies in cm^-1.")
    symmetries: List[str] = Field(default_factory=list, description="Normal mode symmetry labels.")
    ir_intensities_km_mol: List[float] = Field(default_factory=list, description="IR intensities in km/mol.")
    zpe_cm_inv: Optional[float] = Field(default=None, description="Zero-point vibrational energy in cm^-1.")
    zpe_kcal_mol: Optional[float] = Field(default=None, description="Zero-point vibrational energy in kcal/mol.")
    cartesian_hessian: Optional[List[List[float]]] = Field(
        default=None, description="Cartesian force constant matrix (3N x 3N) in Hartree/bohr^2."
    )


class CFOURObservables(BaseModel):
    """Complete structured spectroscopic observables emitted by CFOUR CCSD(T) / VPT2."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    # Energies
    scf_energy_hartree: Optional[float] = Field(default=None, description="SCF total energy in Hartree.")
    mp2_energy_hartree: Optional[float] = Field(default=None, description="MP2 correlation / total energy.")
    ccsd_energy_hartree: Optional[float] = Field(default=None, description="CCSD total energy in Hartree.")
    ccsd_t_energy_hartree: Optional[float] = Field(default=None, description="CCSD(T) total energy in Hartree.")
    final_energy_hartree: float = Field(..., description="Final electronic energy in Hartree.")

    # Equilibrium Rotational Constants (Be)
    Ae_MHz: Optional[float] = Field(default=None, description="Equilibrium rotational constant A_e in MHz.")
    Be_MHz: Optional[float] = Field(default=None, description="Equilibrium rotational constant B_e in MHz.")
    Ce_MHz: Optional[float] = Field(default=None, description="Equilibrium rotational constant C_e in MHz.")
    Ae_cm_inv: Optional[float] = Field(default=None, description="Equilibrium rotational constant A_e in cm^-1.")
    Be_cm_inv: Optional[float] = Field(default=None, description="Equilibrium rotational constant B_e in cm^-1.")
    Ce_cm_inv: Optional[float] = Field(default=None, description="Equilibrium rotational constant C_e in cm^-1.")

    # Vibrational Corrections & Ground-State Constants (B0)
    delta_A_vib_MHz: Optional[float] = Field(default=None, description="Vibrational correction delta_A_vib in MHz.")
    delta_B_vib_MHz: Optional[float] = Field(default=None, description="Vibrational correction delta_B_vib in MHz.")
    delta_C_vib_MHz: Optional[float] = Field(default=None, description="Vibrational correction delta_C_vib in MHz.")
    A0_MHz: Optional[float] = Field(default=None, description="Ground-state rotational constant A_0 = A_e + delta_A_vib (MHz).")
    B0_MHz: Optional[float] = Field(default=None, description="Ground-state rotational constant B_0 = B_e + delta_B_vib (MHz).")
    C0_MHz: Optional[float] = Field(default=None, description="Ground-state rotational constant C_0 = C_e + delta_C_vib (MHz).")
    A0_cm_inv: Optional[float] = Field(default=None, description="Ground-state rotational constant A_0 in cm^-1.")
    B0_cm_inv: Optional[float] = Field(default=None, description="Ground-state rotational constant B_0 in cm^-1.")
    C0_cm_inv: Optional[float] = Field(default=None, description="Ground-state rotational constant C_0 in cm^-1.")

    # Rigid-Rotor Inertial Observables
    inertial_defect_amu_ang2: Optional[float] = Field(default=None, description="Inertial defect Delta = I_c - I_a - I_b (u * Angstrom^2).")
    planar_moment_Paa_amu_ang2: Optional[float] = Field(default=None, description="Planar moment P_aa in u * Angstrom^2.")
    planar_moment_Pbb_amu_ang2: Optional[float] = Field(default=None, description="Planar moment P_bb in u * Angstrom^2.")
    planar_moment_Pcc_amu_ang2: Optional[float] = Field(default=None, description="Planar moment P_cc in u * Angstrom^2.")
    ray_asymmetry_kappa: Optional[float] = Field(default=None, description="Ray's asymmetry parameter kappa = (2B-A-C)/(A-C).")

    # Dipole Moments (Debye)
    dipole_a_debye: Optional[float] = Field(default=None, description="Principal axis dipole component mu_a in Debye.")
    dipole_b_debye: Optional[float] = Field(default=None, description="Principal axis dipole component mu_b in Debye.")
    dipole_c_debye: Optional[float] = Field(default=None, description="Principal axis dipole component mu_c in Debye.")
    dipole_total_debye: Optional[float] = Field(default=None, description="Total dipole moment in Debye.")

    # Vibrational & Anharmonic Data
    harmonic_force_field: HarmonicForceField = Field(..., description="Harmonic force field and normal modes.")
    fundamental_frequencies_cm_inv: List[float] = Field(default_factory=list, description="VPT2 fundamental anharmonic frequencies in cm^-1.")
    anharmonic_contributions_cm_inv: List[float] = Field(default_factory=list, description="VPT2 anharmonic shifts (fundamental - harmonic) in cm^-1.")
    fundamental_ir_intensities_km_mol: List[float] = Field(default_factory=list, description="VPT2 fundamental IR intensities in km/mol.")
    vpt2_zpe_cm_inv: Optional[float] = Field(default=None, description="Anharmonic Harm+VPT2 ZPE in cm^-1.")
    vpt2_zpe_kcal_mol: Optional[float] = Field(default=None, description="Anharmonic Harm+VPT2 ZPE in kcal/mol.")
    vibration_rotation_alphas: List[VibrationRotationAlpha] = Field(default_factory=list, description="Alpha constants.")
    quartic_distortion: Optional[QuarticCentrifugalDistortion] = Field(default=None, description="Quartic distortion.")
    sextic_distortion: Optional[SexticCentrifugalDistortion] = Field(default=None, description="Sextic distortion.")
    quadrupole_couplings: List[ElectricFieldGradientTensor] = Field(default_factory=list, description="Quadrupole couplings.")
    spin_rotation_tensors: List[NuclearSpinRotationTensor] = Field(default_factory=list, description="Spin rotation.")
    dboc_correction_hartree: Optional[float] = Field(default=None, description="DBOC in Hartree.")
    dboc_correction_cm_inv: Optional[float] = Field(default=None, description="DBOC in cm^-1.")

    @property
    def final_energy(self) -> float:
        return self.final_energy_hartree

    @property
    def scf_energy(self) -> Optional[float]:
        return self.scf_energy_hartree

    @property
    def mp2_energy(self) -> Optional[float]:
        return self.mp2_energy_hartree

    @property
    def ccsd_energy(self) -> Optional[float]:
        return self.ccsd_energy_hartree

    @property
    def ccsd_t_energy(self) -> Optional[float]:
        return self.ccsd_t_energy_hartree

    @property
    def dipole_tot(self) -> float:
        return self.dipole_total_debye


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
    parent_B0_MHz: Optional[Tuple[float, float, float]] = Field(default=None, description="Parent ground-state (A0, B0, C0) in MHz.")
    parent_zpe_cm_inv: float = Field(..., description="Parent harmonic ZPE in cm^-1.")

    # Isotopologue constants
    iso_Be_MHz: Tuple[float, float, float] = Field(..., description="Isotopologue equilibrium (Ae, Be, Ce) in MHz.")
    iso_B0_MHz: Optional[Tuple[float, float, float]] = Field(default=None, description="Isotopologue ground-state (A0, B0, C0) in MHz.")
    iso_frequencies_cm_inv: List[float] = Field(..., description="Isotopologue harmonic vibrational frequencies (cm^-1).")
    iso_zpe_cm_inv: float = Field(..., description="Isotopologue harmonic ZPE in cm^-1.")
    zpe_shift_cm_inv: float = Field(..., description="Delta ZPE = ZPE_iso - ZPE_parent in cm^-1.")

    # Inertial properties
    iso_inertial_defect_amu_ang2: float = Field(..., description="Isotopologue inertial defect Delta (u * Angstrom^2).")
    iso_planar_moments_amu_ang2: Tuple[float, float, float] = Field(..., description="Isotopologue planar moments (Paa, Pbb, Pcc).")
    iso_ray_asymmetry_kappa: float = Field(..., description="Isotopologue Ray's asymmetry parameter kappa.")

    # Shifts
    delta_A0_MHz: Optional[float] = Field(default=None, description="Shift Delta A0 = A0_iso - A0_parent in MHz.")
    delta_B0_MHz: Optional[float] = Field(default=None, description="Shift Delta B0 = B0_iso - B0_parent in MHz.")
    delta_C0_MHz: Optional[float] = Field(default=None, description="Shift Delta C0 = C0_iso - C0_parent in MHz.")
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
    status: Literal["EXECUTION_VERIFIED", "PENDING_INTEGRATION", "REJECTED"] = "REJECTED"
    handoff_manifest: Optional[str] = None

    @model_validator(mode="after")
    def verify_status_scope(self) -> "CFOURJobResult":
        if self.success != (self.status == "EXECUTION_VERIFIED"):
            raise ValueError("Only an execution-verified CFOUR result can report success")
        if self.status == "PENDING_INTEGRATION" and (
            not self.handoff_manifest or self.observables is not None or self.error_message is not None
            or self.stdout_hash or self.zmat_hash
        ):
            raise ValueError("A pending CFOUR job requires a handoff and cannot contain execution evidence")
        return self


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

    I = np.full((3, 3), 0.0, dtype=np.float64)
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


def _compute_bond_angle_deg(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray) -> float:
    """Compute bond angle p0-p1-p2 in degrees with vertex at p1."""
    v1 = p0 - p1
    v2 = p2 - p1
    n1 = float(np.linalg.norm(v1))
    n2 = float(np.linalg.norm(v2))
    if n1 <= 1e-15 or n2 <= 1e-15:
        raise ValueError("Cannot compute bond angle with coincident reference coordinates.")
    cos_val = float(np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0))
    return float(np.degrees(np.arccos(cos_val)))


def _compute_cfour_dihedral_deg(
    p0: np.ndarray,
    p1: np.ndarray,
    p2: np.ndarray,
    p3: np.ndarray,
) -> float:
    """Compute exact CFOUR/IUPAC Z-matrix dihedral (degrees) for ordered 4-tuple (p0, p1, p2, p3).

    Matches CFOUR 2.1 ``xjoda`` connectivity ``SYM p1 R p2 A p3 D`` around bond axis
    ``p1 -> p2`` (cis = 0 deg, trans = 180 deg, proper right-handed rotation det(R) = +1):
        b0 = p0 - p1, b1 = p2 - p1, b2 = p3 - p2
        v = b0 - (b0 . b1_hat) * b1_hat
        w = b2 - (b2 . b1_hat) * b1_hat
        D = atan2((b1_hat x v) . w, v . w)
    """
    b0 = p0 - p1
    b1 = p2 - p1
    b2 = p3 - p2
    norm_b1 = float(np.linalg.norm(b1))
    if norm_b1 <= 1e-15:
        raise ValueError("Degenerate central bond axis (p1 == p2) while computing CFOUR Z-matrix dihedral.")
    b1_hat = b1 / norm_b1
    v = b0 - float(np.dot(b0, b1_hat)) * b1_hat
    w = b2 - float(np.dot(b2, b1_hat)) * b1_hat
    norm_v = float(np.linalg.norm(v))
    norm_w = float(np.linalg.norm(w))
    if norm_v <= 1e-12 or norm_w <= 1e-12:
        raise ValueError(
            "Collinear reference triple encountered while computing CFOUR Z-matrix dihedral "
            f"(|v|={norm_v:.3e}, |w|={norm_w:.3e})."
        )
    v_hat = v / norm_v
    w_hat = w / norm_w
    x = float(np.dot(v_hat, w_hat))
    y = float(np.dot(np.cross(b1_hat, v_hat), w_hat))
    dihed_deg = float(np.degrees(np.arctan2(y, x)))
    if abs(dihed_deg) < 1e-12:
        return 0.0
    if abs(abs(dihed_deg) - 180.0) < 1e-12:
        return 180.0
    return dihed_deg


def _orthogonal_unit_vector(axis: np.ndarray, secondary: Optional[np.ndarray] = None) -> np.ndarray:
    """Return a deterministic unit vector orthogonal to ``axis`` (and ``secondary`` when non-collinear)."""
    norm_axis = float(np.linalg.norm(axis))
    if norm_axis <= 1e-15:
        raise ValueError("Cannot construct orthogonal vector to zero-length bond axis.")
    u = axis / norm_axis
    if secondary is not None:
        cross_sec = np.cross(u, secondary)
        norm_sec = float(np.linalg.norm(cross_sec))
        if norm_sec > 1e-10:
            return cross_sec / norm_sec
    ref_axis = (
        np.array([1.0, 0.0, 0.0], dtype=np.float64)
        if abs(float(u[0])) < 0.8
        else np.array([0.0, 1.0, 0.0], dtype=np.float64)
    )
    perp = np.cross(u, ref_axis)
    return perp / float(np.linalg.norm(perp))


def generate_cfour_zmat(
    symbols: Sequence[str],
    coordinates_angstrom: np.ndarray,
    config: Optional[CFOURInputConfig] = None,
    isotopes: Optional[Sequence[int]] = None,
) -> str:
    """Generate a production-grade CFOUR ZMAT input file conforming strictly to Method Matrix v4 §9.5.

    Implements:
    - 3-character variable names (e.g. R01, A01, D01, RX, RH).
    - Automated detection and perpendicular auxiliary atom ('X') insertion for collinear fragments (0° / 180° singularity avoidance).
    - Exact IUPAC/CFOUR Z-matrix dihedral reconstruction preserving planar trans and chiral handedness (det(R) = +1).
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

    # 2. Build Internal Coordinates / Z-matrix with Collinear Auxiliary Atom Insertion
    zmat_entries: List[str] = []
    variables: Dict[str, float] = {}

    var_r_idx = 1
    var_a_idx = 1
    var_d_idx = 1
    var_x_idx = 1

    # Keep track of ZMAT row positions (0-indexed) and their 3D coordinates
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
            # Compute angles at atom 1 (row 1) and atom 2 (row 2) to detect collinear / near-collinear triples
            angle_at_1 = _compute_bond_angle_deg(cur_pos, zmat_coords[0], zmat_coords[1])
            angle_at_2 = _compute_bond_angle_deg(cur_pos, zmat_coords[1], zmat_coords[0])

            # If collinear or near-collinear (angle < 5 deg or > 175 deg), insert auxiliary atom X
            # perpendicular to bond 2-1 (and to 2-3 when slightly bent) so row 3 is strictly non-collinear.
            if angle_at_1 < 5.0 or angle_at_1 > 175.0 or angle_at_2 < 5.0 or angle_at_2 > 175.0:
                v21 = zmat_coords[0] - zmat_coords[1]
                v23 = cur_pos - zmat_coords[1]
                perp = _orthogonal_unit_vector(v21, v23)

                x_pos = zmat_coords[1] + 1.0 * perp
                rx_name = _format_cfour_var_name("X", var_x_idx)
                var_x_idx += 1
                ax_name = _format_cfour_var_name("A", var_a_idx)
                var_a_idx += 1

                variables[rx_name] = 1.000000
                variables[ax_name] = 90.000000

                # Insert auxiliary atom X at row 3 (referencing row 2 with 1.0 Å and row 1 with 90°)
                zmat_entries.append(f"X 2 {rx_name} 1 {ax_name}")
                zmat_coords.append(x_pos)
                x_row = len(zmat_coords)  # 3

                # Add atom 3 at row 4: distance to row 2, exact angle to X (row 3), exact dihedral to row 1
                r_name = _format_cfour_var_name("R", var_r_idx)
                var_r_idx += 1
                a_name = _format_cfour_var_name("A", var_a_idx)
                var_a_idx += 1
                d_name = _format_cfour_var_name("D", var_d_idx)
                var_d_idx += 1

                variables[r_name] = float(np.linalg.norm(v23))
                variables[a_name] = _compute_bond_angle_deg(cur_pos, zmat_coords[1], x_pos)
                variables[d_name] = _compute_cfour_dihedral_deg(
                    cur_pos, zmat_coords[1], x_pos, zmat_coords[0]
                )

                zmat_entries.append(f"{sym} 2 {r_name} {x_row} {a_name} 1 {d_name}")
                zmat_coords.append(cur_pos)
            else:
                r_name = _format_cfour_var_name("R", var_r_idx)
                var_r_idx += 1
                a_name = _format_cfour_var_name("A", var_a_idx)
                var_a_idx += 1

                variables[r_name] = float(np.linalg.norm(cur_pos - zmat_coords[0]))
                variables[a_name] = angle_at_1
                zmat_entries.append(f"{sym} 1 {r_name} 2 {a_name}")
                zmat_coords.append(cur_pos)
        else:
            # Verify both angle(i, 1, 2) and angle(3, 2, 1) are safely non-collinear before using (1, 2, 3)
            angle_i12 = _compute_bond_angle_deg(cur_pos, zmat_coords[0], zmat_coords[1])
            angle_321 = _compute_bond_angle_deg(zmat_coords[2], zmat_coords[1], zmat_coords[0])

            if 5.0 <= angle_i12 <= 175.0 and 5.0 <= angle_321 <= 175.0:
                ref_a, ref_b, ref_c = 1, 2, 3
                dist = float(np.linalg.norm(cur_pos - zmat_coords[0]))
                angle_deg = angle_i12
                dihed_deg = _compute_cfour_dihedral_deg(
                    cur_pos, zmat_coords[0], zmat_coords[1], zmat_coords[2]
                )
            else:
                # Try well-conditioned existing reference triples before inserting a new auxiliary atom X.
                # Order: (2, 3, 1) reuses a row-3 perpendicular X cleanly for linear chains (e.g. C2H2);
                # (1, 3, 2) handles linear axial ligands around a bent/T-shaped/square-planar core.
                chosen: Optional[Tuple[int, int, int, float, float, float]] = None
                for cand_a, cand_b, cand_c in ((2, 3, 1), (1, 3, 2)):
                    pa = zmat_coords[cand_a - 1]
                    pb = zmat_coords[cand_b - 1]
                    pc = zmat_coords[cand_c - 1]
                    cand_dist = float(np.linalg.norm(cur_pos - pa))
                    if cand_dist <= 1e-6:
                        continue
                    ang_iab = _compute_bond_angle_deg(cur_pos, pa, pb)
                    ang_cba = _compute_bond_angle_deg(pc, pb, pa)
                    if 10.0 <= ang_iab <= 170.0 and 10.0 <= ang_cba <= 170.0:
                        cand_dihed = _compute_cfour_dihedral_deg(cur_pos, pa, pb, pc)
                        chosen = (cand_a, cand_b, cand_c, cand_dist, ang_iab, cand_dihed)
                        break

                if chosen is not None:
                    ref_a, ref_b, ref_c, dist, angle_deg, dihed_deg = chosen
                else:
                    # Universal fallback: insert a full 3-internal auxiliary atom X at row >= 4
                    # positioned 1.0 Å from row 1, at 90° to row 2, cis (0°) to row 3.
                    p1, p2, p3 = zmat_coords[0], zmat_coords[1], zmat_coords[2]
                    u12 = (p2 - p1) / float(np.linalg.norm(p2 - p1))
                    w3 = (p3 - p2) - float(np.dot(p3 - p2, u12)) * u12
                    norm_w3 = float(np.linalg.norm(w3))
                    if norm_w3 > 1e-10:
                        e_perp = w3 / norm_w3
                    else:
                        e_perp = _orthogonal_unit_vector(p2 - p1, cur_pos - p1)

                    x_pos = p1 + 1.0 * e_perp
                    rx_name = _format_cfour_var_name("X", var_x_idx)
                    var_x_idx += 1
                    ax_name = _format_cfour_var_name("A", var_a_idx)
                    var_a_idx += 1
                    dx_name = _format_cfour_var_name("D", var_d_idx)
                    var_d_idx += 1

                    variables[rx_name] = 1.000000
                    variables[ax_name] = 90.000000
                    variables[dx_name] = _compute_cfour_dihedral_deg(x_pos, p1, p2, p3)

                    zmat_entries.append(f"X 1 {rx_name} 2 {ax_name} 3 {dx_name}")
                    zmat_coords.append(x_pos)
                    x_row = len(zmat_coords)

                    ref_a, ref_b, ref_c = 1, x_row, 2
                    dist = float(np.linalg.norm(cur_pos - p1))
                    angle_deg = _compute_bond_angle_deg(cur_pos, p1, x_pos)
                    dihed_deg = _compute_cfour_dihedral_deg(cur_pos, p1, x_pos, p2)

            r_name = _format_cfour_var_name("R", var_r_idx)
            var_r_idx += 1
            a_name = _format_cfour_var_name("A", var_a_idx)
            var_a_idx += 1
            d_name = _format_cfour_var_name("D", var_d_idx)
            var_d_idx += 1

            variables[r_name] = dist
            variables[a_name] = angle_deg
            variables[d_name] = dihed_deg
            zmat_entries.append(f"{sym} {ref_a} {r_name} {ref_b} {a_name} {ref_c} {d_name}")
            zmat_coords.append(cur_pos)

    lines.extend(zmat_entries)
    lines.append("")  # Mandatory blank line separating topology from variables

    # 3. Variable definitions
    for k, v in sorted(variables.items()):
        lines.append(f"{k} = {v:.6f}")

    lines.append("")  # Mandatory blank line before *CFOUR block

    # 4. *CFOUR(...) Keyword Block
    from cochem_base.calc.cfour_execution import normalize_cfour_basis_keyword

    eff_reference = cfg.reference
    if cfg.multiplicity > 1 and eff_reference == CFOURReference.RHF:
        eff_reference = CFOURReference.UHF
    basis_kw = normalize_cfour_basis_keyword(cfg.basis)
    if basis_kw == cfg.basis.strip():
        basis_kw = basis_kw.upper()
    cfour_kw: List[str] = [
        f"CALC={cfg.calc_level.value}",
        f"BASIS={basis_kw}",
        f"REFERENCE={eff_reference.value}",
        f"FROZEN_CORE={'ON' if cfg.frozen_core else 'OFF'}",
        f"SPHERICAL={'ON' if cfg.spherical else 'OFF'}",
        f"UNITS={cfg.units.upper()}",
    ]
    if cfg.vib_mode != CFOURVibMode.NONE or cfg.anharm_mode != CFOURAnharmMode.NONE:
        eff_vib = CFOURVibMode.EXACT if cfg.vib_mode == CFOURVibMode.NONE else cfg.vib_mode
        cfour_kw.append(f"VIB={eff_vib.value}")
    if cfg.calc_level not in {CFOURCalcLevel.HF, CFOURCalcLevel.MP2}:
        cc_prog = cfg.cc_prog.upper()
        if eff_reference != CFOURReference.RHF and cc_prog == "ECC":
            cc_prog = "VCC"
        cfour_kw.append(f"ABCDTYPE={cfg.abcdtype.upper()}")
        cfour_kw.append(f"CC_PROG={cc_prog}")

    if cfg.anharm_mode != CFOURAnharmMode.NONE:
        cfour_kw.append(f"ANHARM={cfg.anharm_mode.value}")
        cfour_kw.append(f"ANH_STEPSIZ={cfg.anh_stepsiz}")

    has_vib_or_anharm = cfg.vib_mode != CFOURVibMode.NONE or cfg.anharm_mode != CFOURAnharmMode.NONE
    if cfg.vib_mode == CFOURVibMode.FINDIF or cfg.anharm_mode != CFOURAnharmMode.NONE:
        cfour_kw.append(f"FD_PROJECT={'ON' if cfg.fd_project else 'OFF'}")
    if cfg.props and cfg.props.upper() != "OFF":
        if has_vib_or_anharm and cfg.props.upper() == "FIRST_ORDER":
            logger.warning(
                "Omitting PROPS=FIRST_ORDER because CFOUR 2.1 silently suppresses VIB/ANHARM "
                "stages when PROPS=FIRST_ORDER is active in the same ZMAT."
            )
        else:
            cfour_kw.append(f"PROPS={cfg.props.upper()}")
    if cfg.memory_size_mb is not None:
        cfour_kw.append(f"MEMORY_SIZE={cfg.memory_size_mb}")
        cfour_kw.append("MEM_UNIT=MB")
    else:
        cfour_kw.append(f"MEMORY_SIZE={cfg.memory_size_gb}")
        cfour_kw.append("MEM_UNIT=GB")
    cfour_kw.append(f"SCF_CONV={cfg.scf_conv}")
    cfour_kw.append(f"CC_CONV={cfg.cc_conv}")
    cfour_kw.append(f"LINEQ_CONV={cfg.lineq_conv}")
    extra_upper_keys = {ek.upper() for ek in cfg.extra_keywords}
    if has_vib_or_anharm:
        if "CPHF_CONVER" not in extra_upper_keys:
            cfour_kw.append(f"CPHF_CONVER={cfg.cphf_conver}")
        if "CPHF_MAXCYC" not in extra_upper_keys:
            cfour_kw.append(f"CPHF_MAXCYC={cfg.cphf_maxcyc}")
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

    # Append custom keywords (never permit PROPS=FIRST_ORDER alongside VIB/ANHARM)
    for ek, ev in sorted(cfg.extra_keywords.items()):
        ek_up, ev_up = ek.upper(), ev.upper()
        if has_vib_or_anharm and ek_up == "PROPS" and ev_up == "FIRST_ORDER":
            logger.warning(
                "Omitting extra keyword PROPS=FIRST_ORDER because CFOUR 2.1 silently suppresses "
                "VIB/ANHARM stages when PROPS=FIRST_ORDER is active in the same ZMAT."
            )
            continue
        cfour_kw.append(f"{ek_up}={ev_up}")

    # Join *CFOUR(...) block
    lines.append("*CFOUR(" + "\n".join(cfour_kw) + ")")

    # 5. %isotopes block when explicitly specified
    iso_list = isotopes or cfg.isotopes
    if iso_list is not None and len(iso_list) == n_atoms:
        lines.append("")
        lines.append("%isotopes")
        for iso_val in iso_list:
            lines.append(str(int(iso_val)))

    lines.append("")  # Trailing newline
    return "\n".join(lines)


# ==============================================================================
# 6. CFOUR Output Parser Engine
# ==============================================================================

class CFOUROutputParser:
    """Robust parser for CFOUR standard output logs and auxiliary text archives."""

    PAT_SCF_ENERGY = re.compile(r"(?:E\(SCF\)|SCF ENERGY|Total SCF energy|SCF energy)\s*[:=]?\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?|[+-]?(?:nan|inf))", re.IGNORECASE)
    PAT_MP2_ENERGY = re.compile(r"(?:E\(CORR\)\(MP2\)|E\(MP2\)|MP2 ENERGY|Total MP2 energy|Total MBPT\(2\)\s+energy)\s*[:=]?\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?|[+-]?(?:nan|inf))", re.IGNORECASE)
    PAT_CCSD_ENERGY = re.compile(r"(?:E\(CCSD\)|CCSD ENERGY|Total CCSD energy)\s*[:=]?\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?|[+-]?(?:nan|inf))", re.IGNORECASE)
    PAT_CCSD_T_ENERGY = re.compile(r"(?:E\(CCSD\(T\)\)|CCSD\(T\) ENERGY|Total CCSD\(T\) energy)\s*[:=]?\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?|[+-]?(?:nan|inf))", re.IGNORECASE)

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

    PAT_FINAL_ENERGY = re.compile(
        r"(?:The\s+final\s+electronic\s+energy\s+is|FINAL\s+ELECTRONIC\s+ENERGY\s+IS|FINAL\s+ENERGY)\s*[:=]?\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?|[+-]?(?:nan|inf))",
        re.IGNORECASE,
    )

    @staticmethod
    def verify_execution_evidence(text: str, config: CFOURInputConfig) -> None:
        """Reject absent convergence or nonzero module exits; status 0 on xcfour alone is not physics."""
        bad_modules = [
            (mod, int(code))
            for mod, code in re.findall(r"--executable\s+(\S+)\s+finished with status\s+(-?\d+)\b", text)
            if int(code) != 0
        ]
        if bad_modules or "Job has terminated with error flag" in text:
            raise ConvergenceError(f"CFOUR native module exited abnormally: {bad_modules}")
        if re.search(r"NOT CONVERGED|DID NOT CONVERGE|FAILED TO CONVERGE|FATAL ERROR|ABNORMAL TERMINATION", text, re.I):
            raise ConvergenceError("CFOUR reported failed electronic convergence")
        if not re.search(r"\bSCF\b[^\n]*\b(?:converged|convergence achieved)\b", text, re.I):
            raise ConvergenceError("CFOUR output lacks explicit SCF convergence evidence")
        if config.calc_level.value.upper() not in {"SCF", "HF", "MP2"}:
            if not re.search(
                r"(?:\b(?:CCSD(?:\(T\))?|coupled.cluster|CC amplitude|CC iterations?)\b[^\n]*\bconverged\b|"
                r"Amplitude equations converged)",
                text,
                re.I,
            ):
                raise ConvergenceError("CFOUR output lacks explicit coupled-cluster convergence evidence")

    @staticmethod
    def verify_requested_stage_completeness(observables: CFOURObservables, config: CFOURInputConfig) -> None:
        """Fail closed when requested VPT2 or vibrational stages were silently skipped or incomplete."""
        if config.anharm_mode == CFOURAnharmMode.VPT2:
            if not observables.fundamental_frequencies_cm_inv or not all(
                math.isfinite(val) for val in observables.fundamental_frequencies_cm_inv
            ):
                raise ConvergenceError(
                    "EXECUTION_FAILED: CFOUR VPT2 (ANHARM=VPT2) was requested, but output contains no "
                    "finite parsed fundamental frequencies (VPT2 stage was suppressed or did not complete)."
                )
            if observables.B0_MHz is None or not math.isfinite(observables.B0_MHz):
                raise ConvergenceError(
                    "EXECUTION_FAILED: CFOUR VPT2 (ANHARM=VPT2) was requested, but output lacks a finite "
                    "ground-state rotational constant B0_MHz."
                )
        if config.vib_mode != CFOURVibMode.NONE or config.anharm_mode != CFOURAnharmMode.NONE:
            if not observables.harmonic_force_field.frequencies_cm_inv:
                raise ConvergenceError(
                    "EXECUTION_FAILED: CFOUR vibrational analysis was requested, but output contains no "
                    "parsed harmonic vibrational frequencies."
                )

    @classmethod
    def parse_cfour_stdout(
        cls,
        stdout_source: Union[str, Iterable[str], TextIO, None] = None,
        symbols_fallback: Optional[Sequence[str]] = None,
        coordinates_fallback: Optional[np.ndarray] = None,
        stdout_text: Optional[str] = None,
    ) -> CFOURObservables:
        """Parse complete spectroscopic observables from a CFOUR execution stdout stream or text.

        Args:
            stdout_source: Stream, line iterator, file object, or full text.
            symbols_fallback: Optional atom symbols if not found in log.
            coordinates_fallback: Optional Cartesian coordinates array.
            stdout_text: Backward-compatible keyword argument for raw string.

        Returns:
            CFOURObservables instance with extracted parameters.
        """
        source = stdout_source if stdout_source is not None else stdout_text
        if source is None:
            raise ValueError("Must provide stdout_source or stdout_text.")

        if isinstance(source, str):
            line_iter = iter(source.splitlines())
        elif hasattr(source, "readline"):
            line_iter = (line.rstrip("\r\n") for line in source)
        else:
            line_iter = (line.rstrip("\r\n") if isinstance(line, str) else str(line) for line in source)

        class _StreamWrapper:
            def __init__(self, it: Any) -> None:
                self._it = it
                self._peek: Optional[str] = None
                self._has_peek: bool = False

            def __iter__(self) -> _StreamWrapper:
                return self

            def __next__(self) -> str:
                if self._has_peek:
                    val = self._peek
                    self._has_peek = False
                    self._peek = None
                    return val  # type: ignore[return-value]
                return next(self._it)

            def peek(self) -> Optional[str]:
                if not self._has_peek:
                    try:
                        self._peek = next(self._it)
                        self._has_peek = True
                    except StopIteration:
                        return None
                return self._peek

        stream = _StreamWrapper(line_iter)

        scf_energy: Optional[float] = None
        mp2_energy: Optional[float] = None
        ccsd_energy: Optional[float] = None
        ccsd_t_energy: Optional[float] = None
        explicit_final_energy: Optional[float] = None

        Ae_MHz, Be_MHz, Ce_MHz = None, None, None
        Ae_cm, Be_cm, Ce_cm = None, None, None
        direct_A0_MHz, direct_B0_MHz, direct_C0_MHz = None, None, None
        direct_A0_cm, direct_B0_cm, direct_C0_cm = None, None, None

        dipole_a, dipole_b, dipole_c, dipole_tot = None, None, None, None

        freqs: List[float] = []
        symmetries: List[str] = []
        ir_intensities: List[float] = []
        vpt2_harm_freqs: List[float] = []
        vpt2_fund_freqs: List[float] = []
        vpt2_anharm_contribs: List[float] = []
        vpt2_harm_intensities: List[float] = []
        vpt2_fund_intensities: List[float] = []
        vpt2_zpe_cm: Optional[float] = None
        vpt2_zpe_kcal: Optional[float] = None
        harm_zpe_cm_direct: Optional[float] = None
        harm_zpe_kcal_direct: Optional[float] = None
        vib_table_freqs: List[float] = []
        vib_table_syms: List[str] = []
        vib_table_intensities: List[float] = []
        vibrot_by_mode: Dict[int, Dict[int, float]] = {}
        distortion_section: Optional[str] = None
        distortion_unit_scale_khz: float = 1.0

        alphas: List[VibrationRotationAlpha] = []
        quartic = QuarticCentrifugalDistortion()
        sextic = SexticCentrifugalDistortion()
        quadrupoles: List[ElectricFieldGradientTensor] = []
        spin_rots: List[NuclearSpinRotationTensor] = []
        dboc_hartree: Optional[float] = None
        dboc_cm: Optional[float] = None

        parsed_symbols: List[str] = list(symbols_fallback or [])
        _num = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?"

        def _f(tok: str) -> float:
            return float(tok.replace("D", "E").replace("d", "e"))

        for line in stream:
            # Energy tokens preserve scientific notation, including Fortran D exponents.
            m = cls.PAT_SCF_ENERGY.search(line)
            if m:
                scf_energy = _f(m.group(1))
            m = cls.PAT_MP2_ENERGY.search(line)
            if m:
                mp2_energy = _f(m.group(1))
            m = cls.PAT_CCSD_ENERGY.search(line)
            if m:
                ccsd_energy = _f(m.group(1))
            m = cls.PAT_CCSD_T_ENERGY.search(line)
            if m:
                ccsd_t_energy = _f(m.group(1))
            m_fin = cls.PAT_FINAL_ENERGY.search(line)
            if m_fin:
                explicit_final_energy = _f(m_fin.group(1))

            # 2. Parse Rotational Constants (CFOUR 2.1 Be/B0 table + generic lines)
            if "Be, B0 AND B-B0 SHIFTS FOR SINGLY EXCITED VIBRATIONAL STATES" in line:
                is_mhz_table = "(MHz)" in line or "(MHZ)" in line.upper()
                is_cm_table = "(CM-1)" in line.upper()
                while True:
                    rline = stream.peek()
                    if rline is None:
                        break
                    r_strip = rline.strip()
                    if r_strip.startswith("searchzmat") or r_strip.startswith("Be, B0 AND"):
                        break
                    next(stream)
                    if r_strip.startswith("Be "):
                        nums = [_f(t) for t in re.findall(_num, r_strip[2:])]
                        if len(nums) >= 3:
                            sorted_vals = sorted(nums[:3], reverse=True)
                            if is_mhz_table:
                                Ae_MHz, Be_MHz, Ce_MHz = sorted_vals[0], sorted_vals[1], sorted_vals[2]
                            elif is_cm_table:
                                Ae_cm, Be_cm, Ce_cm = sorted_vals[0], sorted_vals[1], sorted_vals[2]
                        elif len(nums) == 2:
                            # Linear molecules emit only two degenerate rotational constants (X/Y axes; A=0).
                            if is_mhz_table:
                                Ae_MHz, Be_MHz, Ce_MHz = 0.0, nums[0], nums[1]
                            elif is_cm_table:
                                Ae_cm, Be_cm, Ce_cm = 0.0, nums[0], nums[1]
                    elif r_strip.startswith("B0 "):
                        nums = [_f(t) for t in re.findall(_num, r_strip[2:])]
                        if len(nums) >= 3:
                            sorted_vals = sorted(nums[:3], reverse=True)
                            if is_mhz_table:
                                direct_A0_MHz, direct_B0_MHz, direct_C0_MHz = sorted_vals[0], sorted_vals[1], sorted_vals[2]
                            elif is_cm_table:
                                direct_A0_cm, direct_B0_cm, direct_C0_cm = sorted_vals[0], sorted_vals[1], sorted_vals[2]
                        elif len(nums) == 2:
                            if is_mhz_table:
                                direct_A0_MHz, direct_B0_MHz, direct_C0_MHz = 0.0, nums[0], nums[1]
                            elif is_cm_table:
                                direct_A0_cm, direct_B0_cm, direct_C0_cm = 0.0, nums[0], nums[1]
                    elif r_strip.startswith("---"):
                        if (is_mhz_table and direct_A0_MHz is not None) or (is_cm_table and direct_A0_cm is not None):
                            break
                continue

            if "Rotational constants (in MHz)" in line or "ROTATIONAL CONSTANTS (MHZ)" in line:
                after_colon = line.split(":")[-1].strip()
                m_rot = re.search(r"(?:A\s*=\s*)?([+-]?\d+\.\d+)\s+(?:B\s*=\s*)?([+-]?\d+\.\d+)\s+(?:C\s*=\s*)?([+-]?\d+\.\d+)", after_colon)
                if m_rot and float(m_rot.group(1)) != 0.0:
                    try:
                        vals = sorted([float(m_rot.group(1)), float(m_rot.group(2)), float(m_rot.group(3))], reverse=True)
                        Ae_MHz, Be_MHz, Ce_MHz = vals[0], vals[1], vals[2]
                    except ValueError as _e:
                        logger.debug(f"Ignored exception: {_e}")
                else:
                    next_l = stream.peek()
                    if next_l:
                        m_rot2 = re.search(r"(?:A\s*=\s*)?([+-]?\d+\.\d+)\s+(?:B\s*=\s*)?([+-]?\d+\.\d+)\s+(?:C\s*=\s*)?([+-]?\d+\.\d+)", next_l)
                        if m_rot2:
                            next(stream)
                            try:
                                vals = sorted([float(m_rot2.group(1)), float(m_rot2.group(2)), float(m_rot2.group(3))], reverse=True)
                                Ae_MHz, Be_MHz, Ce_MHz = vals[0], vals[1], vals[2]
                            except ValueError as _e:
                                logger.debug(f"Ignored exception: {_e}")

            if "Rotational constants (in cm-1)" in line or "ROTATIONAL CONSTANTS (CM-1)" in line:
                after_colon = line.split(":")[-1].strip()
                m_rot = re.search(r"(?:A\s*=\s*)?([+-]?\d+\.\d+)\s+(?:B\s*=\s*)?([+-]?\d+\.\d+)\s+(?:C\s*=\s*)?([+-]?\d+\.\d+)", after_colon)
                if m_rot and float(m_rot.group(1)) != 0.0:
                    try:
                        vals = sorted([float(m_rot.group(1)), float(m_rot.group(2)), float(m_rot.group(3))], reverse=True)
                        Ae_cm, Be_cm, Ce_cm = vals[0], vals[1], vals[2]
                    except ValueError as _e:
                        logger.debug(f"Ignored exception: {_e}")
                else:
                    next_l = stream.peek()
                    if next_l:
                        m_rot2 = re.search(r"(?:A\s*=\s*)?([+-]?\d+\.\d+)\s+(?:B\s*=\s*)?([+-]?\d+\.\d+)\s+(?:C\s*=\s*)?([+-]?\d+\.\d+)", next_l)
                        if m_rot2:
                            next(stream)
                            try:
                                vals = sorted([float(m_rot2.group(1)), float(m_rot2.group(2)), float(m_rot2.group(3))], reverse=True)
                                Ae_cm, Be_cm, Ce_cm = vals[0], vals[1], vals[2]
                            except ValueError as _e:
                                logger.debug(f"Ignored exception: {_e}")

            # 3. Parse Dipole (Single-line, Multiline, and CFOUR 2.1 VPT2 summary)
            m_eq_dip = re.search(rf"Equilibrium dipole moment:\s*({_num})\s*a\.u\.\s*\(\s*({_num})\s*D\s*\)", line)
            if m_eq_dip:
                dipole_tot = _f(m_eq_dip.group(2))
            if line.strip().startswith("MU_e"):
                nums = [_f(t) for t in re.findall(_num, line)]
                if len(nums) >= 6:
                    dipole_a, dipole_b, dipole_c = nums[3], nums[4], nums[5]
            if "Dipole moment (Debye)" in line or "DIPOLE MOMENT" in line:
                m_dip = re.search(
                    r"(?:[XYZxyz]\s*=\s*)?([+-]?\d+\.\d+)\s+(?:[XYZxyz]\s*=\s*)?([+-]?\d+\.\d+)\s+(?:[XYZxyz]\s*=\s*)?([+-]?\d+\.\d+)\s+(?:tot(?:al)?\s*=\s*)?([+-]?\d+\.\d+)",
                    line.split(":")[-1],
                    re.IGNORECASE,
                )
                if not m_dip or len(line.split(":")[-1].strip()) < 5:
                    next_l = stream.peek()
                    if next_l:
                        m_dip2 = re.search(
                            r"[XYZxyz]\s*=\s*([+-]?\d+\.\d+)\s+[XYZxyz]\s*=\s*([+-]?\d+\.\d+)\s+[XYZxyz]\s*=\s*([+-]?\d+\.\d+)\s+(?:tot(?:al)?\s*=\s*)?([+-]?\d+\.\d+)",
                            next_l,
                            re.IGNORECASE,
                        )
                        if m_dip2:
                            next(stream)
                            m_dip = m_dip2
                if m_dip:
                    try:
                        dipole_a = float(m_dip.group(1))
                        dipole_b = float(m_dip.group(2))
                        dipole_c = float(m_dip.group(3))
                        dipole_tot = float(m_dip.group(4))
                    except (ValueError, IndexError) as _e:
                        logger.debug(f"Ignored exception: {_e}")

            # 4a. Parse CFOUR 2.1 VPT2 Harmonic & Fundamental Frequencies Table
            if "HARMONIC AND FUNDAMENTAL FREQUENCIES" in line.upper():
                vpt2_harm_freqs, vpt2_fund_freqs, vpt2_anharm_contribs = [], [], []
                vpt2_harm_intensities, vpt2_fund_intensities = [], []
                seen_rows = False
                while True:
                    vline = stream.peek()
                    if vline is None:
                        break
                    v_strip = vline.strip()
                    if v_strip.startswith("---") and seen_rows:
                        break
                    next(stream)
                    m_vf = re.match(
                        rf"^\s*(\d+)\s+({_num})\s+({_num})\s+({_num})\s+({_num})\s+({_num})\s+({_num})\s*$",
                        vline,
                    )
                    if m_vf:
                        seen_rows = True
                        vpt2_harm_freqs.append(_f(m_vf.group(2)))
                        vpt2_fund_freqs.append(_f(m_vf.group(3)))
                        vpt2_anharm_contribs.append(_f(m_vf.group(4)))
                        vpt2_harm_intensities.append(_f(m_vf.group(5)))
                        vpt2_fund_intensities.append(_f(m_vf.group(6)))
                continue

            # 4b. Parse CFOUR 2.1 ZERO-POINT VIBRATIONAL ENERGIES
            if line.strip().startswith("Harmonic contribution"):
                nums = [_f(t) for t in re.findall(_num, line.split(":")[-1])]
                if len(nums) >= 4:
                    harm_zpe_kcal_direct = nums[0]
                    harm_zpe_cm_direct = nums[3]
            elif line.strip().startswith("Harm+VPT2"):
                nums = [_f(t) for t in re.findall(_num, line.split(":")[-1])]
                if len(nums) >= 4:
                    vpt2_zpe_kcal = nums[0]
                    vpt2_zpe_cm = nums[3]

            # 4c. Parse CFOUR 2.1 xjoda Harmonic Frequency table (VIBRATION rows)
            m_xj = re.match(
                rf"^\s*(\S+)\s+({_num})(i?)\s+({_num})\s+VIBRATION\s*$",
                line,
            )
            if m_xj and not vib_table_freqs:
                # Capture the first (reference geometry) classified vibrational spectrum
                vib_table_syms.append(m_xj.group(1))
                val = (-1.0 if m_xj.group(3) else 1.0) * _f(m_xj.group(2))
                vib_table_freqs.append(val)
                vib_table_intensities.append(_f(m_xj.group(4)))
                while True:
                    nline = stream.peek()
                    if nline is None:
                        break
                    m_next = re.match(
                        rf"^\s*(\S+)\s+({_num})(i?)\s+({_num})\s+VIBRATION\s*$",
                        nline,
                    )
                    if not m_next:
                        break
                    next(stream)
                    vib_table_syms.append(m_next.group(1))
                    vib_table_freqs.append((-1.0 if m_next.group(3) else 1.0) * _f(m_next.group(2)))
                    vib_table_intensities.append(_f(m_next.group(4)))
                continue

            # 4d. Parse Legacy Harmonic Frequencies Header
            if "Harmonic vibrational frequencies" in line or "HARMONIC VIBRATIONAL FREQUENCIES (CM-1)" in line:
                while True:
                    fline = stream.peek()
                    if fline is None:
                        break
                    fline_strip = fline.strip()
                    if not fline_strip:
                        if freqs:
                            break
                        next(stream)
                        continue
                    if any(term in fline_strip for term in ["Vibration-rotation", "ALPHA CONSTANTS", "Total", "Zero-point", "---", "==="]):
                        if freqs:
                            break
                        next(stream)
                        continue
                    next(stream)
                    parts = fline_strip.split()
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
                        except (ValueError, IndexError) as _e:
                            logger.debug(f"Ignored exception: {_e}")

            # 5a. Parse CFOUR 2.1 VIB-ROT CONSTANT / (cm-1) table
            if "VIB-ROT CONSTANT / (cm-1)" in line:
                seen_vr = False
                while True:
                    vrline = stream.peek()
                    if vrline is None:
                        break
                    vr_strip = vrline.strip()
                    if vr_strip.startswith("---") and seen_vr:
                        break
                    next(stream)
                    m_vr = re.match(
                        rf"^\s*([123])\s+(\d+)\s+({_num})\s+({_num})\s+({_num})\s+({_num})\s*$",
                        vrline,
                    )
                    if m_vr:
                        seen_vr = True
                        axis_i = int(m_vr.group(1))
                        mode_i = int(m_vr.group(2))
                        total_cm = _f(m_vr.group(6))
                        vibrot_by_mode.setdefault(mode_i, {})[axis_i] = total_cm
                continue

            # 5b. Parse Legacy Vibration-Rotation Alpha Constants
            if "Vibration-rotation interaction constants" in line or "ALPHA CONSTANTS" in line:
                while True:
                    aline = stream.peek()
                    if aline is None:
                        break
                    aline_strip = aline.strip()
                    if not aline_strip:
                        if alphas:
                            break
                        next(stream)
                        continue
                    if any(term in aline_strip for term in ["Watson", "reduction", "ELECTRIC FIELD", "---", "==="]):
                        if alphas:
                            break
                        next(stream)
                        continue
                    next(stream)
                    parts = aline_strip.split()
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
                        except (ValueError, IndexError) as _e:
                            logger.debug(f"Ignored exception: {_e}")

            # 6. Parse Quartic & Sextic Distortions (CFOUR 2.1 native tables + legacy syntax)
            if "Parameter" in line and "(MHz)" in line:
                distortion_unit_scale_khz = 1000.0
            if "A-reduced centrifugal distortion parameters" in line:
                distortion_section = "A"
                continue
            if "S-reduced centrifugal distortion parameters" in line:
                distortion_section = "S"
                continue
            if distortion_section is not None:
                s_line = line.strip()
                if s_line.startswith("---"):
                    distortion_section = None
                elif s_line:
                    m_cd = re.match(rf"^(DELJ|DELK|DELJK|delJ|delK|DJ|DK|DJK|D1|D2)\s+({_num})", s_line)
                    if m_cd:
                        pname, pval = m_cd.group(1), _f(m_cd.group(2)) * distortion_unit_scale_khz
                        if distortion_section == "A":
                            if pname == "DELJ":
                                quartic.Delta_J_kHz = pval
                            elif pname == "DELJK":
                                quartic.Delta_JK_kHz = pval
                            elif pname == "DELK":
                                quartic.Delta_K_kHz = pval
                            elif pname == "delJ":
                                quartic.delta_j_kHz = pval
                            elif pname == "delK":
                                quartic.delta_k_kHz = pval
                        elif distortion_section == "S":
                            if pname == "DJ":
                                quartic.D_J_kHz = pval
                            elif pname == "DJK":
                                quartic.D_JK_kHz = pval
                            elif pname == "DK":
                                quartic.D_K_kHz = pval
                            elif pname == "D1":
                                quartic.d_1_kHz = pval
                            elif pname == "D2":
                                quartic.d_2_kHz = pval
                        continue

            # Watson A Quartic (legacy syntax)
            m_dj = re.search(r"\bDelta_?J\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_dj:
                quartic.Delta_J_kHz = _f(m_dj.group(1))
            m_djk = re.search(r"\bDelta_?JK\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_djk:
                quartic.Delta_JK_kHz = _f(m_djk.group(1))
            m_dk = re.search(r"\bDelta_?K\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_dk:
                quartic.Delta_K_kHz = _f(m_dk.group(1))
            m_delj = re.search(r"\bdelta_?j\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_delj:
                quartic.delta_j_kHz = _f(m_delj.group(1))
            m_delk = re.search(r"\bdelta_?k\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_delk:
                quartic.delta_k_kHz = _f(m_delk.group(1))

            # Watson S Quartic (legacy syntax)
            m_sdj = re.search(r"\bD_?J\b\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_sdj and not m_dj:
                quartic.D_J_kHz = _f(m_sdj.group(1))
            m_sdjk = re.search(r"\bD_?JK\b\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_sdjk and not m_djk:
                quartic.D_JK_kHz = _f(m_sdjk.group(1))
            m_sdk = re.search(r"\bD_?K\b\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_sdk and not m_dk:
                quartic.D_K_kHz = _f(m_sdk.group(1))
            m_sd1 = re.search(r"\bd_?1\b\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_sd1:
                quartic.d_1_kHz = _f(m_sd1.group(1))
            m_sd2 = re.search(r"\bd_?2\b\s*[:=]?\s*([+-]?\d+\.?\d*(?:[eEdD][+-]?\d+)?)", line)
            if m_sd2:
                quartic.d_2_kHz = _f(m_sd2.group(1))

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
                while True:
                    qline = stream.peek()
                    if qline is None:
                        break
                    qline_strip = qline.strip()
                    if not qline_strip:
                        if quadrupoles:
                            break
                        next(stream)
                        continue
                    if any(term in qline_strip for term in ["Diagonal", "DBOC", "---", "==="]):
                        if quadrupoles:
                            break
                        next(stream)
                        continue
                    next(stream)
                    parts = qline_strip.split()
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
                        except (ValueError, IndexError) as _e:
                            logger.debug(f"Ignored exception: {_e}")

            # 8. Nuclear Spin-Rotation Interaction Constants
            if "SPIN-ROTATION" in line.upper() or "SPIN ROTATION" in line.upper():
                while True:
                    sline = stream.peek()
                    if sline is None:
                        break
                    sline_strip = sline.strip()
                    if not sline_strip:
                        if spin_rots:
                            break
                        next(stream)
                        continue
                    if any(term in sline_strip for term in ["DBOC", "Diagonal", "---", "==="]):
                        if spin_rots:
                            break
                        next(stream)
                        continue
                    next(stream)
                    parts = sline_strip.split()
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
                        except (ValueError, IndexError) as _e:
                            logger.debug(f"Ignored exception: {_e}")

            # 9. DBOC
            if "DBOC" in line or "Diagonal Born-Oppenheimer Correction" in line:
                parts = line.split(":")[-1].split()
                if parts:
                    try:
                        dboc_hartree = float(parts[0])
                        dboc_cm = dboc_hartree * CONSTANTS.HARTREE_TO_CM_INV
                    except ValueError as _e:
                        logger.debug(f"Ignored exception: {_e}")

        if explicit_final_energy is not None:
            final_energy = explicit_final_energy
        elif ccsd_t_energy is not None:
            final_energy = ccsd_t_energy
        elif ccsd_energy is not None:
            final_energy = ccsd_energy
        elif mp2_energy is not None and scf_energy is not None:
            # E(CORR)(MP2) is not a total electronic energy; never promote it.
            raise ValueError("CFOUR MP2 output requires an explicit final total energy")
        elif scf_energy is not None:
            final_energy = scf_energy
        else:
            raise ValueError("CFOUR output contains no measured finite electronic energy")
        if not math.isfinite(final_energy):
            raise ValueError("CFOUR final electronic energy is not finite")

        # Merge parsed harmonic frequencies from VPT2 or xjoda tables when legacy header was absent
        if vpt2_harm_freqs:
            freqs = list(vpt2_harm_freqs)
            ir_intensities = list(vpt2_harm_intensities)
            if not symmetries and len(vib_table_syms) == len(freqs):
                symmetries = list(vib_table_syms)
        elif vib_table_freqs and not freqs:
            freqs = list(vib_table_freqs)
            symmetries = list(vib_table_syms)
            ir_intensities = list(vib_table_intensities)

        c_cm_s = CONSTANTS.C_CM_S
        if not alphas and vibrot_by_mode:
            for idx_pos, mode_id in enumerate(sorted(vibrot_by_mode), start=1):
                axes = vibrot_by_mode[mode_id]
                a_cm = axes.get(1, 0.0)
                b_cm = axes.get(2, 0.0)
                c_cm = axes.get(3, 0.0)
                alphas.append(
                    VibrationRotationAlpha(
                        mode_index=idx_pos,
                        harmonic_freq_cm_inv=freqs[idx_pos - 1] if idx_pos - 1 < len(freqs) else 0.0,
                        symmetry=symmetries[idx_pos - 1] if idx_pos - 1 < len(symmetries) else "A",
                        alpha_A_MHz=(a_cm * c_cm_s) / 1e6,
                        alpha_B_MHz=(b_cm * c_cm_s) / 1e6,
                        alpha_C_MHz=(c_cm * c_cm_s) / 1e6,
                        alpha_A_cm_inv=a_cm,
                        alpha_B_cm_inv=b_cm,
                        alpha_C_cm_inv=c_cm,
                    )
                )

        if Ae_MHz is None and Ae_cm is not None:
            Ae_MHz, Be_MHz, Ce_MHz = (value * c_cm_s / 1e6 for value in (Ae_cm, Be_cm, Ce_cm))
        if Ae_MHz is None and parsed_symbols and coordinates_fallback is not None:
            ((Ae_MHz, Be_MHz, Ce_MHz), (Ae_cm, Be_cm, Ce_cm), in_def, (Paa, Pbb, Pcc), kappa) = (
                compute_equilibrium_rotational_constants(parsed_symbols, coordinates_fallback)
            )
        elif Ae_MHz is not None:
            Ae_cm, Be_cm, Ce_cm = (value * 1e6 / c_cm_s for value in (Ae_MHz, Be_MHz, Ce_MHz))
            conv = CONSTANTS.C_ROT_MHZ_U_ANG2
            Ia = conv / Ae_MHz if Ae_MHz > 0 else 0.0
            Ib = conv / Be_MHz if Be_MHz > 0 else 0.0
            Ic = conv / Ce_MHz if Ce_MHz > 0 else 0.0
            Paa, Pbb, Pcc = (Ib + Ic - Ia) / 2, (Ia + Ic - Ib) / 2, (Ia + Ib - Ic) / 2
            in_def = Ic - Ia - Ib
            denom = Ae_MHz - Ce_MHz
            kappa = (2 * Be_MHz - Ae_MHz - Ce_MHz) / denom if abs(denom) > 1e-6 else None
        else:
            in_def = Paa = Pbb = Pcc = kappa = None

        if direct_A0_MHz is None and direct_A0_cm is not None:
            direct_A0_MHz, direct_B0_MHz, direct_C0_MHz = (
                value * c_cm_s / 1e6 for value in (direct_A0_cm, direct_B0_cm, direct_C0_cm)
            )

        rigid_modes = 5 if Ae_MHz == 0 and Be_MHz is not None and Be_MHz > 0 else 6
        expected_modes = max(0, 3 * len(parsed_symbols) - rigid_modes) if parsed_symbols else None
        complete_frequencies = (
            (expected_modes is not None and len(freqs) == expected_modes and bool(freqs))
            or bool(vpt2_harm_freqs)
        )
        complete_alphas = complete_frequencies and len(alphas) == len(freqs) and {a.mode_index for a in alphas} == set(range(1, len(freqs) + 1))

        if direct_A0_MHz is not None and Ae_MHz is not None:
            A0_MHz, B0_MHz, C0_MHz = direct_A0_MHz, direct_B0_MHz, direct_C0_MHz
            delta_A_vib_MHz = A0_MHz - Ae_MHz
            delta_B_vib_MHz = B0_MHz - Be_MHz if (B0_MHz is not None and Be_MHz is not None) else None
            delta_C_vib_MHz = C0_MHz - Ce_MHz if (C0_MHz is not None and Ce_MHz is not None) else None
        else:
            delta_A_vib_MHz = -0.5 * sum(a.alpha_A_MHz for a in alphas) if complete_alphas else None
            delta_B_vib_MHz = -0.5 * sum(a.alpha_B_MHz for a in alphas) if complete_alphas else None
            delta_C_vib_MHz = -0.5 * sum(a.alpha_C_MHz for a in alphas) if complete_alphas else None
            A0_MHz = Ae_MHz + delta_A_vib_MHz if Ae_MHz is not None and complete_alphas else None
            B0_MHz = Be_MHz + delta_B_vib_MHz if Be_MHz is not None and complete_alphas else None
            C0_MHz = Ce_MHz + delta_C_vib_MHz if Ce_MHz is not None and complete_alphas else None
        A0_cm = direct_A0_cm if direct_A0_cm is not None else (A0_MHz * 1e6 / c_cm_s if A0_MHz is not None else None)
        B0_cm = direct_B0_cm if direct_B0_cm is not None else (B0_MHz * 1e6 / c_cm_s if B0_MHz is not None else None)
        C0_cm = direct_C0_cm if direct_C0_cm is not None else (C0_MHz * 1e6 / c_cm_s if C0_MHz is not None else None)
        zpe_cm = (
            harm_zpe_cm_direct
            if harm_zpe_cm_direct is not None
            else (0.5 * sum(freqs) if complete_frequencies and all(value >= 0 for value in freqs) else None)
        )
        zpe_kcal = (
            harm_zpe_kcal_direct
            if harm_zpe_kcal_direct is not None
            else (zpe_cm / CONSTANTS.HARTREE_TO_CM_INV * CONSTANTS.HARTREE_TO_KCAL_MOL if zpe_cm is not None else None)
        )

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

        has_quartic = any(v is not None for v in quartic.model_dump().values())
        has_sextic = any(v is not None for v in sextic.model_dump().values())

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
            fundamental_frequencies_cm_inv=vpt2_fund_freqs,
            anharmonic_contributions_cm_inv=vpt2_anharm_contribs,
            fundamental_ir_intensities_km_mol=vpt2_fund_intensities,
            vpt2_zpe_cm_inv=vpt2_zpe_cm,
            vpt2_zpe_kcal_mol=vpt2_zpe_kcal,
            vibration_rotation_alphas=alphas,
            quartic_distortion=quartic if has_quartic else None,
            sextic_distortion=sextic if has_sextic else None,
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
    return_modes: bool = False,
) -> Union[Tuple[List[float], float], Tuple[List[float], float, np.ndarray, np.ndarray]]:
    """Diagonalize mass-weighted Cartesian Hessian via exact Eckart null-space complement projection.

    Method Matrix v4 §3.3 & Suggestion #3:
    Constructs the exact 6-dimensional (or 5-dimensional for linear systems) Eckart translational
    and infinitesimal rotational subspace in mass-weighted coordinates:
      t_alpha = sqrt(m_i) e_alpha
      r_alpha = sqrt(m_i) (e_alpha x (x_i - com))
    Orthonormalizes U_ext via complete QR decomposition to construct the (3N - k) vibrational
    complement basis U_vib such that U_ext^T U_vib = 0.
    Projects the mass-weighted Hessian into the intrinsic vibrational subspace:
      H_vib = U_vib^T H_mw U_vib in R^{(3N-k) x (3N-k)}
    Diagonalizing H_vib strictly guarantees exactly 3N - 6 (or 3N - 5) physical vibrational eigenvalues
    with zero translation/rotation contamination, preserving authentic soft modes down to 0.1 cm^-1
    without scalar cutoff filters.

    Args:
        hessian: (3N, 3N) Cartesian Hessian in Hartree / bohr^2.
        symbols: Sequence of atom symbols (length N).
        coordinates: (N, 3) Cartesian coordinates in Angstroms.
        masses: Sequence of atomic masses in unified atomic mass units (u).
        return_modes: If True, also returns mass-weighted normal mode matrix L_mw (3N x (3N-k))
                      and eigenvalues.

    Returns:
        If return_modes is False: (frequencies_cm, zpe)
        If return_modes is True: (frequencies_cm, zpe, L_mw, evals)
    """
    n_atoms = len(symbols)
    m_inv_sqrt = np.full(3 * n_atoms, 0.0, dtype=np.float64)
    for i in range(n_atoms):
        m_inv_sqrt[3 * i : 3 * i + 3] = 1.0 / np.sqrt(masses[i])

    H_mw = hessian * np.outer(m_inv_sqrt, m_inv_sqrt)

    com = compute_center_of_mass(symbols, coordinates, masses)
    shifted = coordinates - com

    # Construct translational and rotational vectors in mass-weighted coordinates
    proj_vectors: List[np.ndarray] = []

    # 3 translation vectors: t_alpha = sqrt(m_i) * e_alpha
    for alpha in range(3):
        t_vec = np.full(3 * n_atoms, 0.0, dtype=np.float64)
        for i in range(n_atoms):
            t_vec[3 * i + alpha] = np.sqrt(masses[i])
        norm = float(np.linalg.norm(t_vec))
        if norm > 1e-12:
            proj_vectors.append(t_vec / norm)

    # 3 infinitesimal rotation vectors: r_alpha = sqrt(m_i) * (e_alpha x (x_i - com))
    for alpha in range(3):
        e_alpha = np.full(3, 0.0, dtype=np.float64)
        e_alpha[alpha] = 1.0
        r_vec = np.full(3 * n_atoms, 0.0, dtype=np.float64)
        for i in range(n_atoms):
            cross = np.cross(e_alpha, shifted[i])
            r_vec[3 * i : 3 * i + 3] = cross * np.sqrt(masses[i])

        # Gram-Schmidt orthogonalization against already accepted external vectors
        for pv in proj_vectors:
            r_vec -= float(np.dot(pv, r_vec)) * pv

        r_norm = float(np.linalg.norm(r_vec))
        if r_norm > 1e-6:
            proj_vectors.append(r_vec / r_norm)

    k = len(proj_vectors)
    if k == 0:
        U_vib = np.diag(np.full(3 * n_atoms, 1.0, dtype=np.float64))
    else:
        U_ext = np.column_stack(proj_vectors)
        # Complete QR decomposition to compute null-space vibrational complement
        Q, _ = np.linalg.qr(U_ext, mode="complete")
        U_vib = Q[:, k:]

    # Project mass-weighted Hessian into intrinsic vibrational subspace:
    # H_vib = U_vib.T @ H_mw @ U_vib (shape (3N-k) x (3N-k))
    H_vib = U_vib.T @ H_mw @ U_vib
    H_vib = 0.5 * (H_vib + H_vib.T)

    evals, evecs = scipy.linalg.eigh(H_vib)
    freq_factor = CONSTANTS.HESSIAN_EIGENVALUE_TO_CM_INV

    frequencies_cm: List[float] = []
    for ev in evals:
        if abs(ev) < 1e-12:
            frequencies_cm.append(0.0)
        elif ev > 0:
            freq_val = math.sqrt(ev) * freq_factor
            frequencies_cm.append(freq_val)
        else:
            freq_val = -math.sqrt(abs(ev)) * freq_factor
            frequencies_cm.append(freq_val)

    # Normal mode transformation matrix in mass-weighted coordinates:
    # L_mw = U_vib @ evecs (shape 3N x (3N-k))
    L_mw = U_vib @ evecs

    # Sort modes by frequency ascending
    sort_idx = np.argsort(evals)
    frequencies_sorted = [frequencies_cm[idx] for idx in sort_idx]
    evals_sorted = evals[sort_idx]
    L_mw_sorted = L_mw[:, sort_idx]

    zpe = 0.5 * sum(f for f in frequencies_sorted if f > 0)

    if return_modes:
        return frequencies_sorted, zpe, L_mw_sorted, evals_sorted
    return frequencies_sorted, zpe


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
    - Parent ground-state constants only when complete parent alphas are supplied.
    - Isotope ground-state constants remain unknown: harmonic data and parent
      alphas cannot replace a transformation of the full anharmonic force field.
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

    parent_frequencies_cm, parent_zpe_cm, L_parent, _ = _diagonalize_projected_hessian(
        hessian, symbols, coords, parent_masses, return_modes=True
    )
    iso_frequencies_cm, iso_zpe_cm, L_iso, _ = _diagonalize_projected_hessian(
        hessian, symbols, coords, iso_masses, return_modes=True
    )

    n_modes = len(parent_frequencies_cm)
    parent_B0 = None
    if parent_alphas:
        if len(parent_alphas) != n_modes or {alpha.mode_index for alpha in parent_alphas} != set(range(1, n_modes + 1)):
            raise ValueError("Parent ground-state constants require complete, uniquely indexed vibration-rotation alphas")
        corrections = [-0.5 * sum(getattr(alpha, component) for alpha in parent_alphas)
                       for component in ("alpha_A_MHz", "alpha_B_MHz", "alpha_C_MHz")]
        if not all(math.isfinite(value) for value in corrections):
            raise ValueError("Parent vibration-rotation corrections must be finite")
        parent_B0 = tuple(value + correction for value, correction in zip(parent_Be, corrections, strict=True))
    # A harmonic Hessian gives exact mass-dependent harmonic modes and Be.
    # Isotope-specific B0 needs transformed cubic/quartic force constants and
    # Coriolis/rotation couplings; neither alpha rescaling nor Be is equivalent.
    iso_B0 = None
    delta_A0 = delta_B0 = delta_C0 = None

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

    Uses official JPL Pickett rotational and centrifugal distortion parameter codes
    and sign conventions strictly in MHz:
    - 10000: A (MHz)
    - 20000: B (MHz)
    - 30000: C (MHz)
    -   200: -Delta_J (Watson A) / -D_J (Watson S) (MHz)
    -  1100: -Delta_JK (Watson A) / -D_JK (Watson S) (MHz)
    -  2000: -Delta_K (Watson A) / -D_K (Watson S) (MHz)
    - 40100: -delta_J (Watson A) / +d_1 (Watson S) (MHz)
    - 41000: -delta_K (Watson A) (MHz)
    - 50000: +d_2 (Watson S) (MHz)
    -   300: Phi_J / H_J (MHz)
    -  1200: Phi_JK / H_JK (MHz)
    -  2100: Phi_KJ / H_KJ (MHz)
    -  3000: Phi_K / H_K (MHz)
    - 40200: phi_j / h_1 (MHz)
    - 41100: phi_jk (Watson A) (MHz)
    - 42000: phi_k (Watson A) (MHz)
    - 50100: h_2 (Watson S) (MHz)
    - 60000: h_3 (Watson S) (MHz)
    """
    if any(value is None or not math.isfinite(value) for value in (observables.A0_MHz, observables.B0_MHz, observables.C0_MHz)):
        raise ValueError("SPCAT export requires measured or complete anharmonically derived ground-state rotational constants")

    def _format_var_line(code: int, value_mhz: float, uncert: float) -> str:
        return f"{code:6d}{value_mhz:18.8f}{uncert:14.8f}"

    param_lines: List[str] = []

    # 1. Rotational Constants A0, B0, C0 (MHz)
    param_lines.append(_format_var_line(10000, observables.A0_MHz, abs(observables.A0_MHz * uncertainty_fraction)))
    param_lines.append(_format_var_line(20000, observables.B0_MHz, abs(observables.B0_MHz * uncertainty_fraction)))
    param_lines.append(_format_var_line(30000, observables.C0_MHz, abs(observables.C0_MHz * uncertainty_fraction)))

    # 2. Quartic Centrifugal Distortion (kHz -> MHz: 1 kHz = 1e-3 MHz)
    # Pickett Watson-A requires negated quartics (-Delta_J, -Delta_JK, -Delta_K,
    # -delta_J [40100], -delta_K [41000]); Watson-S uses -D_J, -D_JK, -D_K,
    # +d_1 [40100], +d_2 [50000].
    qd = observables.quartic_distortion
    if qd is not None:
        if reduction == WatsonReduction.A:
            if qd.Delta_J_kHz is not None:
                v = -qd.Delta_J_kHz * 1e-3
                param_lines.append(_format_var_line(200, v, abs(v * 0.05)))
            if qd.Delta_JK_kHz is not None:
                v = -qd.Delta_JK_kHz * 1e-3
                param_lines.append(_format_var_line(1100, v, abs(v * 0.05)))
            if qd.Delta_K_kHz is not None:
                v = -qd.Delta_K_kHz * 1e-3
                param_lines.append(_format_var_line(2000, v, abs(v * 0.05)))
            if qd.delta_j_kHz is not None:
                v = -qd.delta_j_kHz * 1e-3
                param_lines.append(_format_var_line(40100, v, abs(v * 0.05)))
            if qd.delta_k_kHz is not None:
                v = -qd.delta_k_kHz * 1e-3
                param_lines.append(_format_var_line(41000, v, abs(v * 0.05)))
        else:
            if qd.D_J_kHz is not None:
                v = -qd.D_J_kHz * 1e-3
                param_lines.append(_format_var_line(200, v, abs(v * 0.05)))
            if qd.D_JK_kHz is not None:
                v = -qd.D_JK_kHz * 1e-3
                param_lines.append(_format_var_line(1100, v, abs(v * 0.05)))
            if qd.D_K_kHz is not None:
                v = -qd.D_K_kHz * 1e-3
                param_lines.append(_format_var_line(2000, v, abs(v * 0.05)))
            if qd.d_1_kHz is not None:
                v = qd.d_1_kHz * 1e-3
                param_lines.append(_format_var_line(40100, v, abs(v * 0.05)))
            if qd.d_2_kHz is not None:
                v = qd.d_2_kHz * 1e-3
                param_lines.append(_format_var_line(50000, v, abs(v * 0.05)))

    # 3. Sextic Centrifugal Distortion (Hz -> MHz: 1 Hz = 1e-6 MHz)
    sd = observables.sextic_distortion
    if sd is not None:
        if reduction == WatsonReduction.A:
            if sd.Phi_J_Hz is not None:
                v = sd.Phi_J_Hz * 1e-6
                param_lines.append(_format_var_line(300, v, abs(v * 0.10)))
            if sd.Phi_JK_Hz is not None:
                v = sd.Phi_JK_Hz * 1e-6
                param_lines.append(_format_var_line(1200, v, abs(v * 0.10)))
            if sd.Phi_KJ_Hz is not None:
                v = sd.Phi_KJ_Hz * 1e-6
                param_lines.append(_format_var_line(2100, v, abs(v * 0.10)))
            if sd.Phi_K_Hz is not None:
                v = sd.Phi_K_Hz * 1e-6
                param_lines.append(_format_var_line(3000, v, abs(v * 0.10)))
            if sd.phi_j_Hz is not None:
                v = sd.phi_j_Hz * 1e-6
                param_lines.append(_format_var_line(40200, v, abs(v * 0.10)))
            if sd.phi_jk_Hz is not None:
                v = sd.phi_jk_Hz * 1e-6
                param_lines.append(_format_var_line(41100, v, abs(v * 0.10)))
            if sd.phi_k_Hz is not None:
                v = sd.phi_k_Hz * 1e-6
                param_lines.append(_format_var_line(42000, v, abs(v * 0.10)))
        else:
            if sd.H_J_Hz is not None:
                v = sd.H_J_Hz * 1e-6
                param_lines.append(_format_var_line(300, v, abs(v * 0.10)))
            if sd.H_JK_Hz is not None:
                v = sd.H_JK_Hz * 1e-6
                param_lines.append(_format_var_line(1200, v, abs(v * 0.10)))
            if sd.H_KJ_Hz is not None:
                v = sd.H_KJ_Hz * 1e-6
                param_lines.append(_format_var_line(2100, v, abs(v * 0.10)))
            if sd.H_K_Hz is not None:
                v = sd.H_K_Hz * 1e-6
                param_lines.append(_format_var_line(3000, v, abs(v * 0.10)))
            if sd.h_1_Hz is not None:
                v = sd.h_1_Hz * 1e-6
                param_lines.append(_format_var_line(40200, v, abs(v * 0.10)))
            if sd.h_2_Hz is not None:
                v = sd.h_2_Hz * 1e-6
                param_lines.append(_format_var_line(50100, v, abs(v * 0.10)))
            if sd.h_3_Hz is not None:
                v = sd.h_3_Hz * 1e-6
                param_lines.append(_format_var_line(60000, v, abs(v * 0.10)))

    # 4. Nuclear Quadrupole Coupling: fail closed until spin-coupled SPIND/hyperfine IDs are implemented
    for q_tensor in observables.quadrupole_couplings:
        if (
            abs(q_tensor.chi_aa_kHz) > 1e-4
            or abs(q_tensor.chi_bb_kHz) > 1e-4
            or abs(q_tensor.chi_cc_kHz) > 1e-4
        ):
            raise ValueError(
                "Hyperfine nuclear quadrupole SPCAT export requires spin-coupled SPIND/hyperfine parameter IDs "
                "(e.g., 110010000 = 1.5*chi_aa, 110040000 = (chi_bb-chi_cc)/4) and is not yet implemented; "
                "omit quadrupole_couplings for rotational-only export."
            )

    reduction_flag = "a" if reduction == WatsonReduction.A else "s"
    lines: List[str] = [
        f"CoChem CFOUR Bridge Export - Watson {reduction.value}-Reduction",
        f"{len(param_lines):4d}  0  1  0  0.0000E+00  1.0000E+04  1.0000E+00  1.0000E+00",
        f"{reduction_flag}    1  1   0   30   0   1   1   1   0   0   0",
        *param_lines,
        "",
    ]
    return "\n".join(lines)


# ==============================================================================
# 9. CFOUR Execution Broker & Job Dispatcher
# ==============================================================================

class CFOURBridge:
    """Authentic CFOUR 2.1 ZMAT builder, basis stager, and live xcfour execution bridge."""

    _CANONICAL_XCFOUR_PATHS = (
        "/home/ansac/.local/cochem/cfour/2.1-gcc11-openmp-ilp64-20261007/bin/xcfour",
    )

    def __init__(
        self,
        cfour_executable: str = "xcfour",
        genbas_path: Optional[Union[str, Path]] = None,
        scratch_root: Optional[Union[str, Path]] = None,
    ) -> None:
        self.cfour_executable = cfour_executable
        self.genbas_path = Path(genbas_path) if genbas_path else None
        self.scratch_root = Path(scratch_root) if scratch_root else (get_ramdisk_dir() or get_runtime_dir() / "cfour_scratch")
        from cochem.core.context import assert_writable_path
        assert_writable_path(self.scratch_root)
        self.scratch_root.mkdir(parents=True, exist_ok=True)

    def _resolve_cfour_executable(self) -> Path:
        """Resolve real xcfour executable; fail closed with BinaryNotFoundError if absent."""
        raw = str(self.cfour_executable or "").strip()
        if not raw:
            raise BinaryNotFoundError("CFOUR executable (xcfour) is not configured")

        explicit_path = Path(os.path.expandvars(raw)).expanduser()
        if explicit_path.is_file():
            return explicit_path.resolve()
        found_direct = shutil.which(raw)
        if found_direct and Path(found_direct).is_file():
            return Path(found_direct).resolve()

        # Only consult env/canonical defaults when using the default executable name.
        if raw == "xcfour":
            for env_var in ("COCHEM_CFOUR_BIN", "COCHEM_XCFOUR_BIN", "CFOUR_CMD", "CFOUR_EXE"):
                env_val = os.environ.get(env_var)
                if env_val:
                    cand = Path(os.path.expandvars(env_val)).expanduser()
                    if cand.is_file():
                        return cand.resolve()
            for env_dir in ("CFOUR_BIN",):
                if os.environ.get(env_dir):
                    cand = Path(os.path.expandvars(os.environ[env_dir])).expanduser() / "xcfour"
                    if cand.is_file():
                        return cand.resolve()
            for env_root in ("CFOUR_ROOT", "CFOUR_HOME"):
                if os.environ.get(env_root):
                    cand = Path(os.path.expandvars(os.environ[env_root])).expanduser() / "bin" / "xcfour"
                    if cand.is_file():
                        return cand.resolve()
            for canonical in self._CANONICAL_XCFOUR_PATHS:
                cand = Path(canonical)
                if cand.is_file():
                    return cand.resolve()

        raise BinaryNotFoundError(
            f"[MISSING DATA] CFOUR executable ({raw!r}) not found. Configure COCHEM_CFOUR_BIN, "
            "CFOUR_CMD, or PATH."
        )

    def _stage_basis_files(self, xcfour_path: Optional[Path], work_dir: Path) -> Dict[str, Path]:
        """Stage GENBAS and ECPDATA from explicit path or xcfour's ../basis/ directory."""
        staged: Dict[str, Path] = {}
        basis_dirs: List[Path] = []
        if self.genbas_path is not None:
            basis_dirs.append(self.genbas_path.parent if self.genbas_path.is_file() else self.genbas_path)
        if xcfour_path is not None:
            basis_dirs.append(xcfour_path.parent.parent / "basis")
            basis_dirs.append(xcfour_path.parent / "basis")
        for env_root in ("CFOUR_ROOT", "CFOUR_HOME"):
            if os.environ.get(env_root):
                basis_dirs.append(Path(os.path.expandvars(os.environ[env_root])).expanduser() / "basis")

        for filename, env_keys in (
            ("GENBAS", ("COCHEM_CFOUR_GENBAS", "CFOUR_GENBAS")),
            ("ECPDATA", ("COCHEM_CFOUR_ECPDATA", "CFOUR_ECPDATA")),
        ):
            source: Optional[Path] = None
            if filename == "GENBAS" and self.genbas_path is not None and self.genbas_path.is_file():
                source = self.genbas_path.resolve()
            if source is None:
                for bdir in basis_dirs:
                    cand = bdir / filename
                    if cand.is_file():
                        source = cand.resolve()
                        break
            if source is None:
                for env_k in env_keys:
                    val = os.environ.get(env_k)
                    if val and Path(os.path.expandvars(val)).expanduser().is_file():
                        source = Path(os.path.expandvars(val)).expanduser().resolve()
                        break
            if source is not None:
                dest = work_dir / filename
                if dest.exists() or dest.is_symlink():
                    dest.unlink()
                try:
                    os.symlink(source, dest)
                except (OSError, AttributeError):
                    shutil.copy2(source, dest)
                staged[filename] = source

        if "GENBAS" not in staged:
            raise FileNotFoundError(
                f"CFOUR basis file GENBAS not found relative to {xcfour_path} (../basis/) or CFOUR_GENBAS."
            )
        return staged

    def prepare_job_directory(
        self,
        job_id: str,
        symbols: Sequence[str],
        coordinates_angstrom: np.ndarray,
        config: CFOURInputConfig,
        existing_jobarc: Optional[Path] = None,
        xcfour_path: Optional[Path] = None,
    ) -> Path:
        """Prepare working directory containing ZMAT and required GENBAS/ECPDATA libraries."""
        from cochem.core.context import assert_writable_path
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", job_id):
            raise ValueError("CFOUR job_id must be a safe filename component")
        work_dir = self.scratch_root / f"cfour_{job_id}_{uuid.uuid4().hex}"
        assert_writable_path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

        # 1. Write ZMAT input file
        zmat_text = generate_cfour_zmat(symbols, coordinates_angstrom, config)
        zmat_path = work_dir / "ZMAT"
        zmat_path.write_text(zmat_text, encoding="utf-8")

        # 2. Link or copy GENBAS and ECPDATA
        try:
            self._stage_basis_files(xcfour_path, work_dir)
        except FileNotFoundError:
            if xcfour_path is not None:
                raise

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
        """Execute real CFOUR 2.1 (`xcfour`), staging GENBAS/ECPDATA, and parse observables.

        Fails closed with BinaryNotFoundError when the `xcfour` binary is absent.
        """
        from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
        from cochem_base.core_engine.engine_environment import engine_runtime_environment

        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", job_id):
            raise ValueError("CFOUR job identifiers must contain only safe filename characters")

        xcfour_path = self._resolve_cfour_executable()
        work_dir = self.prepare_job_directory(
            job_id=job_id,
            symbols=symbols,
            coordinates_angstrom=coordinates_angstrom,
            config=config,
            existing_jobarc=existing_jobarc,
            xcfour_path=xcfour_path,
        )

        zmat_path = work_dir / "ZMAT"
        zmat_hash = hashlib.sha256(zmat_path.read_bytes()).hexdigest()

        child_env = engine_runtime_environment("cfour", dict(os.environ), executable=xcfour_path)
        child_env.setdefault("OMP_NUM_THREADS", "2")

        started = time.monotonic()
        proc = safe_subprocess_run(
            [str(xcfour_path)],
            cwd=work_dir,
            timeout=float(timeout_seconds),
            check=False,
            capture_output=True,
            text=True,
            env=child_env,
            required_disk_gb=0.1,
            load_full_stdout=True,
            sanitize_mpi=False,
        )
        wall_time = time.monotonic() - started

        stdout_text = proc.stdout or ""
        stderr_text = proc.stderr or ""
        out_path = work_dir / "output.dat"
        err_path = work_dir / "stderr.log"
        out_path.write_text(stdout_text, encoding="utf-8")
        err_path.write_text(stderr_text, encoding="utf-8")
        stdout_hash = hashlib.sha256(out_path.read_bytes()).hexdigest()

        preserved = [
            name
            for name in ("JOBARC", "JAINDX", "OPTARC", "FCMFINAL", "FCMINT", "GRD", "DIPDER", "quadratic", "cubic", "quartic")
            if (work_dir / name).is_file()
        ]

        if proc.returncode != 0:
            raise RuntimeError(
                f"CFOUR xcfour exited with code {proc.returncode}; diagnostics retained in {work_dir}"
            )

        CFOUROutputParser.verify_execution_evidence(stdout_text, config)
        observables = CFOUROutputParser.parse_cfour_stdout(
            stdout_text,
            symbols_fallback=list(symbols),
            coordinates_fallback=np.asarray(coordinates_angstrom, dtype=np.float64),
        )
        CFOUROutputParser.verify_requested_stage_completeness(observables, config)
        return CFOURJobResult(
            success=True,
            status="EXECUTION_VERIFIED",
            job_id=job_id,
            working_directory=str(work_dir),
            wall_time_seconds=round(wall_time, 4),
            stdout_hash=stdout_hash,
            zmat_hash=zmat_hash,
            observables=observables,
            preserved_files=preserved,
            compliance_notes=[
                f"Authentic CFOUR execution completed via {xcfour_path}.",
                f"GENBAS/ECPDATA staged from {xcfour_path.parent.parent / 'basis'}.",
            ],
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
