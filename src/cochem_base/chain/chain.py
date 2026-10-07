#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
chain.py -- Canonical State-Chaining Driver & Execution-Arrow Recorder for CoChem-BASE.

Mandated by Method Matrix v4 (§8B.1–§8B.6, §8C, §8D) as the authoritative state-chaining
driver script recording every execution arrow and state transfer into one HDF5 file.

Core Architectural Directives:
  1. Executive Finding (§8B.1): The highest-value state transfer is the CONVERGED GEOMETRY,
     not the wavefunction. Geometry is primary state; MOs (.gbw) and Hessians (.opt/.hess)
     are secondary state transfers.
  2. Master State Inventory (§8B.2): Exhaustive tracking of ORCA .gbw MO projections,
     BFGS-updated .opt / Cartesian .hess Hessians, model Hessians (InHess XTB2/Lindh),
     numerical frequency restarts (%freq Restart true), GFN2-xTB .xtbw states,
     MD/PIMD restart states (.mdrestart), PySCF .chk HDF5 checkpoints, and CFOUR archives.
  3. Canonical 11-Arrow Pipeline (§8B.4):
     Arrow 1:  MLFF/xTB GOAT search -> CREST cross-check (union & re-filtering)
     Arrow 2:  Conformer ensemble -> GFN2-xTB refinement (vtight --strict)
     Arrow 3:  GFN2-xTB -> r2SCAN-3c optimization with InHess XTB2 model Hessian
     Arrow 4:  r2SCAN-3c -> wB97X-V/def2-TZVPP tight optimization (MORead s2.gbw + InHess Read s2.opt)
     Arrow 5:  wB97X-V/TZ -> wB97M-V/def2-QZVPP tight optimization (MORead s3.gbw + InHess Read s3.opt)
     Arrow 6:  Tight optimization -> analytic DFT Hessian (! Freq at identical level & geometry)
     Arrow 7:  Hessian -> all isotopologues (free re-analysis at zero electronic-structure cost)
     Arrow 8:  Tight optimization -> high-level single point (! DLPNO-CCSD(T1) with s4.gbw)
     Arrow 9:  Counterpoise legs (ghost atoms ':', basis exported & pinned)
     Arrow 10: DFT force field -> CFOUR anharmonic VPT2 (substituted hybrid FCMINT/FCMFINAL)
     Arrow 11: Multi-step compound script within one ORCA process (New_Step ... Step_End)
  4. Dangerous Reuse Protections -- Rules D1–D5 (§8B.5):
     D1: Geometry stationarity validation & ΔR -> ΔB error propagation check
     D2: Hessian reuse validation (flags modes <100 cm⁻¹ for exclusion from hybrid fields)
     D3: SCF density reuse stability guard against basin collapse / symmetry breaking
     D4: Counterpoise and ghost-atom inconsistency guard (rejects dimer .gbw for ghost legs)
     D5: Unique %base naming hygiene so no reader is ever also the writer
  5. Mendeleev Library Mandate: All atomic and isotopic masses dynamically retrieved via `mendeleev`.
  6. Persistent HDF5 Database (§8C): Chunked (512 points), resizable, gzip level 4 compression,
     shuffle filter, fletcher32 checksums, and QCSchema metadata vocabulary.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import json
import logging
import math
import re
import shutil
import sys
import time
import threading
from dataclasses import asdict, dataclass, field
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import h5py
import numpy as np
from filelock import FileLock
from cochem.core.context import assert_writable_path
from cochem_base.analysis.electronic_sanitizer import SpinContaminationStreamValidator
from cochem_base.calc.cochem_calc_output_parser import QuantumParser
from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
from cochem_base.core_engine.engine_environment import engine_runtime_environment
from cochem_base.spectroscopy.isotopologue import get_nuclide_mass, projected_harmonic_frequencies
from cochem_base.core.cochem_constants import (
    PLANCK_CONSTANT_J_S, SPEED_OF_LIGHT_CM_S, SPEED_OF_LIGHT_M_S,
    ATOMIC_MASS_UNIT_KG, ANGSTROM_TO_METER, BOHR_TO_ANGSTROM, BOHR_TO_METER,
    HARTREE_TO_JOULE, HARTREE_TO_EV, HARTREE_TO_CM_INV, C_ROT_MHZ_U_ANG2,
)
from cochem_base.calc.cochem_calc_input_generator import MoleculeInput
from cochem_base.core_engine.execution_authority import authorize_engine_execution
from cochem_base.core_engine.scientific_telemetry import append_scientific_result
from cochem_base.core_engine.trajectory_telemetry import XYZTrajectoryFollower
from cochem_base.physics.eckart_aligner import align_coordinates
from cochem_base.theory_matrix import canonical_tier_for_method

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logger = logging.getLogger("CoChem-Chain")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [chain]: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Physical Constants & Convergence Standards (Method Matrix §4.4, §5, §8B)
# ---------------------------------------------------------------------------
# Conversion factor from Inertia (u * Angstrom^2) to Rotational Constant (MHz):
# B = h / (8 * pi^2 * I) * 1e-6 (Hz -> MHz)
INERTIA_TO_MHZ_FACTOR = C_ROT_MHZ_U_ANG2

# Conversion factor for Hessian eigenvalue (Hartree / (Bohr^2 * u)) to wavenumber (cm^-1):
# f_lambda = HARTREE_TO_JOULE / (BOHR_TO_METER^2 * ATOMIC_MASS_UNIT_KG)
# f_cm1 = 1 / (2 * pi * c_cm_s)
# sqrt(f_lambda) * f_cm1 ~ 5140.487143715827 cm^-1
HESSIAN_EIG_TO_CM_INV_FACTOR = (
    math.sqrt(HARTREE_TO_JOULE / ((BOHR_TO_METER ** 2) * ATOMIC_MASS_UNIT_KG))
    / (2.0 * math.pi * SPEED_OF_LIGHT_CM_S)
)

# Mandatory Tight Geometry Optimization Convergence Block (Method Matrix §4.4, §8B.4)
TIGHT_GEOM_BLOCK = (
    "  TolE 1e-7\n"
    "  TolRMSG 3e-6\n"
    "  TolMaxG 1e-5\n"
    "  TolRMSD 5e-5\n"
    "  TolMaxD 1e-4\n"
    "  MaxIter 200\n"
)

# HDF5 Storage Specifications (Method Matrix §8C)
CHUNK_POINTS = 512
VLEN_STR = h5py.string_dtype(encoding="utf-8")


class MissingBinaryError(FileNotFoundError):
    """Raised immediately when configured ORCA, CREST, or xTB executable is invalid or not executable."""
    pass


class ConvergenceFailureError(RuntimeError):
    """Raised when an electronic structure engine fails to achieve SCF or geometry convergence."""
    pass


class CorruptOutputError(RuntimeError):
    """Raised when expected binary wavefunction containers or Hessian matrices are missing or malformed."""
    pass


# ---------------------------------------------------------------------------
# Canonical Execution Arrows Registry (Method Matrix §8B.4)
# ---------------------------------------------------------------------------
CANONICAL_ARROWS: Dict[int, Dict[str, str]] = {
    1: {
        "name": "SearchUnion",
        "from_to": "MLFF/xTB GOAT search -> CREST cross-check",
        "file_passed": "BaseName.finalensemble.xyz",
        "keyword": "crest --cregen ens.xyz --ethr 0.05 --bthr 0.01 --rthr 0.125",
        "saving": "Re-filtering costs zero gradients; 100% of search cost avoided on threshold changes",
    },
    2: {
        "name": "EnsembleRefinement",
        "from_to": "Conformer ensemble -> GFN2-xTB refinement",
        "file_passed": ".xyz per conformer alongside .CHRG / .UHF",
        "keyword": "xtb conf.xyz --opt vtight --strict / ORCA ! XTB2 TightOpt",
        "saving": "Fast pre-optimization to reach r2SCAN-3c with sane intermolecular distance",
    },
    3: {
        "name": "xTBToR2SCAN",
        "from_to": "GFN2-xTB -> r2SCAN-3c optimization",
        "file_passed": "xtbopt.xyz + GFN2 model Hessian (InHess XTB2)",
        "keyword": "%geom InHess XTB2 end",
        "saving": ">=2x, typically ~5x fewer optimization steps on floppy complexes [E]",
    },
    4: {
        "name": "R2SCANToWB97XV",
        "from_to": "r2SCAN-3c -> wB97X-V/def2-TZVPP tight optimization",
        "file_passed": "s2.xyz + s2.gbw + s2.opt",
        "keyword": "! MORead + %moinp 's2.gbw'; %geom InHess Read InHessName 's2.opt' end",
        "saving": "Cycles removed (dominant); .opt carries BFGS-updated Hessian",
    },
    5: {
        "name": "TZToQZCascade",
        "from_to": "wB97X-V/TZ -> wB97M-V/def2-QZVPP tight optimization",
        "file_passed": "s3.gbw (projected across basis via GuessMode FMatrix)",
        "keyword": "! MORead + %moinp 's3.gbw'; %scf GuessMode FMatrix end",
        "saving": "Expensive QZ SCF starts from converged TZ density [E]",
    },
    6: {
        "name": "OptToAnalyticHessian",
        "from_to": "Tight optimization -> analytic DFT Hessian",
        "file_passed": "s4.xyz (identical geometry) + s4.gbw",
        "keyword": "! Freq at identical level; ! MORead",
        "saving": "Skips re-converging SCF; stationary force field delivery",
    },
    7: {
        "name": "IsotopologueShortcut",
        "from_to": "Hessian -> all isotopologues",
        "file_passed": "s5.hess",
        "keyword": "re-run Freq with .hess present / orca_vib s5.hess / CFOUR ISOMASS + xjoda",
        "saving": "N isotopologues for the price of one force field (6-15x saving [D])",
    },
    8: {
        "name": "OptToHighLevelSP",
        "from_to": "Tight optimization -> high-level single point",
        "file_passed": "s4.xyz + s4.gbw",
        "keyword": "! DLPNO-CCSD(T1) ... MORead + %moinp 's4.gbw'",
        "saving": "Saves SCF iteration time on the stationary reference geometry",
    },
    9: {
        "name": "CounterpoiseLegs",
        "from_to": "Dimer -> Monomer counterpoise legs",
        "file_passed": "dimer geometry + exported basis (orca_exportbasis)",
        "keyword": "ghost atoms with ':' after element symbol",
        "saving": "Guarantees three legs share identical basis set; pins BSSE correction",
    },
    10: {
        "name": "SubstitutedHybridVPT2",
        "from_to": "DFT force field -> CFOUR anharmonic VPT2",
        "file_passed": "FCMINT in, FCMFINAL out",
        "keyword": "FCMINT read when Hessian updating is off",
        "saving": "Substituted hybrid force field: high-level harmonic + low-level anharmonic",
    },
    11: {
        "name": "CompoundScriptChaining",
        "from_to": "Any stage -> next step within single ORCA process",
        "file_passed": "Geometry & MOs implicitly in memory",
        "keyword": "Read_Geom(n); ReadMOs(n); inside New_Step ... Step_End",
        "saving": "Eliminates file plumbing when whole chain fits one wall-clock window",
    },
}


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
class CounterpoiseType(str, Enum):
    """Counterpoise calculation fragment modes."""
    NONE = "none"
    DIMER = "dimer"
    MONOMER_A = "monomer_a"
    MONOMER_B = "monomer_b"
    FULL_CP = "full"
    HALF_CP = "half"


class CanonicalArrow(IntEnum):
    """Method Matrix canonical 11-Arrow pipeline enumeration."""
    ARROW_1_MLFF_XTB_GOAT = 1
    ARROW_2_CONFORMER_XTB = 2
    ARROW_3_R2SCAN_3C_OPT = 3
    ARROW_4_WB97X_V_TZ_OPT = 4
    ARROW_5_WB97M_V_QZ_OPT = 5
    ARROW_6_ANALYTIC_DFT_HESS = 6
    ARROW_7_ISOTOPOLOGUE = 7
    ARROW_8_DLPNO_CCSD_T1_SP = 8
    ARROW_9_COUNTERPOISE = 9
    ARROW_10_CFOUR_VPT2 = 10
    ARROW_11_COMPOUND_CHAIN = 11


@dataclass
class ArrowState:
    """Method Matrix §8B.4 canonical execution arrow state snapshot."""
    arrow_id: int = 1
    stage_name: str = "s1"
    converged: bool = False
    energy_hartree: Optional[float] = None
    geometry: Optional[np.ndarray] = None
    gradient: Optional[np.ndarray] = None
    hessian: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Stage:
    """Specification for an execution stage in the state-chaining pipeline."""
    name: str                                  # Unique stage identifier (e.g. 's2', 's3')
    level: str                                 # The primary ORCA ! route line
    blocks: str = ""                           # Additional %-configuration blocks
    geom_from: Optional[str] = None            # Source stage for optimized geometry
    mo_from: Optional[str] = None              # Source stage for .gbw orbital projection
    hess_from: Optional[str] = None            # Source stage for .opt or .hess initial Hessian
    arrow_index: Optional[int] = None          # Method Matrix canonical arrow index (1-11)
    arrow_desc: str = ""                       # Human-readable arrow description
    engine: str = "orca"                       # Engine backend: 'orca', 'xtb', 'cfour', 'pyscf'
    guess_mode: str = "FMatrix"                # ORCA MO projection mode: 'FMatrix' or 'CMatrix'
    counterpoise: str = "none"                 # Counterpoise state: 'none', 'half', 'full'
    is_restartable: bool = True                # Wall-clock restartability tag (§8B.6)
    recipe: Optional[str] = None
    product_class: Optional[str] = None
    implicit_solvation: Optional[str] = None
    geometry_source: str = "electronic_structure"
    ab_initio_relaxed: bool = False
    cbs_cardinal_pair: Optional[Tuple[int, int]] = None
    scientific_config: Optional[Dict[str, Any]] = None


# Canonical alias mandated by Suggestion #157 (Deliverable 7)
ChainStage = Stage


@dataclass
class ExecutionArrow:
    """Detailed record of a state transfer arrow between two stages."""
    arrow_number: int
    name: str
    from_stage: Optional[str]
    to_stage: str
    transferred_artifacts: List[str]
    consumption_keyword: str
    computational_benefit: str
    validated: bool = True
    warnings: List[str] = field(default_factory=list)


@dataclass
class StateRecord:
    """Physical state record captured after stage execution."""
    stage: str
    level: str
    wall_s: float
    energy_hartree: Optional[float]
    symbols: List[str]
    geometry: np.ndarray                       # (N, 3) in Angstroms
    gradient: Optional[np.ndarray] = None      # (N, 3) in Hartree/Bohr
    hessian: Optional[np.ndarray] = None       # (3N, 3N) in Hartree/Bohr^2
    frequencies_cm_inv: Optional[np.ndarray] = None  # (3N-6,) or (3N-5,) harmonic frequencies
    rotational_constants_mhz: Optional[Tuple[float, float, float]] = None  # (A, B, C) in MHz
    inertial_defect_amu_a2: Optional[float] = None  # Delta = Ic - Ia - Ib in u * Angstrom^2
    planar_moments_amu_a2: Optional[Tuple[float, float, float]] = None    # (Paa, Pbb, Pcc)
    consumed_files: List[str] = field(default_factory=list)
    produced_files: List[str] = field(default_factory=list)
    arrow_index: Optional[int] = None
    arrow_desc: str = ""
    converged: bool = False
    exit_status: str = "NOT_EXECUTED"
    warnings: List[str] = field(default_factory=list)


@dataclass
class PendingStateRecord(StateRecord):
    """A durable input package awaiting a scientific adapter, never a state result."""
    handoff_manifest: str = ""


# ---------------------------------------------------------------------------
# Mendeleev Dynamic Atomic Mass Retrieval (Mendeleev Library Mandate)
# ---------------------------------------------------------------------------
def get_atomic_mass(symbol: str, mass_number: Optional[int] = None) -> float:
    """Resolve an exact isotope; bare elements mean their principal isotope."""
    return get_nuclide_mass(symbol, mass_number)


def get_isotopic_mass(symbol: str, mass_number: Optional[int] = None) -> float:
    """Dynamically retrieves isotopic mass via get_atomic_mass."""
    return get_atomic_mass(symbol, mass_number)


def get_atomic_masses_for_symbols(
    symbols: Sequence[str],
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> np.ndarray:
    """Returns array of atomic masses in unified atomic mass units (u) for a sequence of symbols."""
    if mass_numbers is not None and len(mass_numbers) != len(symbols):
        raise ValueError("Isotope assignments must match the atom count.")
    masses: List[float] = []
    for i, s in enumerate(symbols):
        iso_num = mass_numbers[i] if mass_numbers is not None and i < len(mass_numbers) else None
        masses.append(get_atomic_mass(s, iso_num))
    return np.array(masses, dtype=float)


# ---------------------------------------------------------------------------
# Molecular Geometry & Rotational Mathematics (Method Matrix §3, §4, §5)
# ---------------------------------------------------------------------------
def compute_center_of_mass(
    symbols: Sequence[str],
    coords: np.ndarray,
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> np.ndarray:
    """Computes the 3D center of mass in Angstroms."""
    masses = get_atomic_masses_for_symbols(symbols, mass_numbers)
    total_mass = float(np.sum(masses))
    if total_mass <= 0.0:
        raise ValueError("Total molecular mass must be strictly positive.")
    com = np.sum(coords * masses[:, None], axis=0) / total_mass
    return com


def compute_inertia_tensor(
    symbols: Sequence[str],
    coords: np.ndarray,
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Computes the moment of inertia tensor shifted to the center of mass.
    Returns:
      I_tensor: 3x3 inertia tensor in u * Angstrom^2
      principal_moments: sorted eigenvalues (Ia <= Ib <= Ic) in u * Angstrom^2
      principal_axes: 3x3 eigenvector matrix (columns are principal axes)
    """
    com = compute_center_of_mass(symbols, coords, mass_numbers)
    r = coords - com
    masses = get_atomic_masses_for_symbols(symbols, mass_numbers)

    i_tensor = np.zeros((3, 3), dtype=np.float64)
    for m_i, r_i in zip(masses, r, strict=True):
        r_sq = float(np.dot(r_i, r_i))
        i_tensor += m_i * (r_sq * np.eye(3, dtype=np.float64) - np.outer(r_i, r_i))

    evals, evecs = np.linalg.eigh(i_tensor)  # type: ignore[attr-defined]
    # Ensure eigenvalues are sorted Ia <= Ib <= Ic
    idx = np.argsort(evals)
    principal_moments = evals[idx]
    principal_axes = evecs[:, idx]

    return i_tensor, principal_moments, principal_axes


def compute_rotational_constants(
    symbols: Sequence[str],
    coords: np.ndarray,
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> Dict[str, Any]:
    """
    Computes the rotational constants (A >= B >= C in MHz), planar moments,
    and inertial defect (Delta = Ic - Ia - Ib in u * Angstrom^2).
    """
    _, principal_moments, principal_axes = compute_inertia_tensor(symbols, coords, mass_numbers)
    Ia, Ib, Ic = float(principal_moments[0]), float(principal_moments[1]), float(principal_moments[2])

    A_MHz = INERTIA_TO_MHZ_FACTOR / Ia if Ia > 1e-12 else float("inf")
    B_MHz = INERTIA_TO_MHZ_FACTOR / Ib if Ib > 1e-12 else float("inf")
    C_MHz = INERTIA_TO_MHZ_FACTOR / Ic if Ic > 1e-12 else float("inf")

    # Planar moments of inertia: Paa = (Ib + Ic - Ia) / 2, etc.
    Paa = (Ib + Ic - Ia) / 2.0
    Pbb = (Ia + Ic - Ib) / 2.0
    Pcc = (Ia + Ib - Ic) / 2.0

    # Inertial defect: Delta = Ic - Ia - Ib
    inertial_defect = Ic - Ia - Ib

    # Ray's asymmetry parameter kappa = (2B - A - C) / (A - C)
    kappa = (2.0 * B_MHz - A_MHz - C_MHz) / (A_MHz - C_MHz) if abs(A_MHz - C_MHz) > 1e-6 else 0.0

    return {
        "A_MHz": A_MHz,
        "B_MHz": B_MHz,
        "C_MHz": C_MHz,
        "Ia_u_A2": Ia,
        "Ib_u_A2": Ib,
        "Ic_u_A2": Ic,
        "Paa_u_A2": Paa,
        "Pbb_u_A2": Pbb,
        "Pcc_u_A2": Pcc,
        "inertial_defect_amu_A2": inertial_defect,
        "kappa": kappa,
        "principal_axes": principal_axes,
    }


def compute_delta_r_and_delta_b(
    coords1: np.ndarray,
    coords2: np.ndarray,
    symbols: Sequence[str],
) -> Dict[str, float]:
    """
    Computes coordinate shifts between two stages (ΔR) and propagates error to rotational constant B
    using the binding Method Matrix law: ΔB / B ≈ 2 * ΔR / R (§4.1, §8B.5 Rule D1).
    """
    assert coords1.shape == coords2.shape, "Coordinate arrays must have identical shape."
    diff = coords2 - coords1
    rmsd_angstrom = float(np.sqrt(np.mean(np.sum(diff ** 2, axis=1))))
    rmsd_pm = rmsd_angstrom * 100.0

    com1 = compute_center_of_mass(symbols, coords1)
    com2 = compute_center_of_mass(symbols, coords2)
    com_shift_angstrom = float(np.linalg.norm(com2 - com1))  # type: ignore[attr-defined]
    com_shift_pm = com_shift_angstrom * 100.0

    rot1 = compute_rotational_constants(symbols, coords1)
    rot2 = compute_rotational_constants(symbols, coords2)

    b1 = rot1["B_MHz"]
    b2 = rot2["B_MHz"]
    delta_b_mhz = abs(b2 - b1)
    rel_b_error_pct = (delta_b_mhz / b1) * 100.0 if b1 > 0 else 0.0

    return {
        "rmsd_angstrom": rmsd_angstrom,
        "rmsd_pm": rmsd_pm,
        "com_shift_angstrom": com_shift_angstrom,
        "com_shift_pm": com_shift_pm,
        "B_initial_MHz": b1,
        "B_final_MHz": b2,
        "delta_B_MHz": delta_b_mhz,
        "rel_B_error_pct": rel_b_error_pct,
    }


# ---------------------------------------------------------------------------
# Vibrational Normal Modes & Isotopologue Solver (Method Matrix Arrow 7, §8B.4)
# ---------------------------------------------------------------------------
def diagonalize_mass_weighted_hessian(
    cart_hessian: np.ndarray,
    symbols: Sequence[str],
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Mass-weights a Cartesian Hessian (3N x 3N in Hartree/Bohr^2) using dynamic Mendeleev masses,
    diagonalizes to normal modes, and converts eigenvalues to harmonic frequencies in cm^-1.
    Imaginary frequencies are reported with negative values.
    """
    natoms = len(symbols)
    cart_hessian = np.asarray(cart_hessian, dtype=float)
    if (cart_hessian.shape != (3 * natoms, 3 * natoms) or not natoms
            or not np.isfinite(cart_hessian).all()
            or not np.allclose(cart_hessian, cart_hessian.T, rtol=1e-8, atol=1e-10)):
        raise ValueError("Hessian must be a complete finite symmetric 3N matrix.")

    masses = get_atomic_masses_for_symbols(symbols, mass_numbers)
    if not np.isfinite(masses).all() or np.any(masses <= 0):
        raise ValueError("Hessian analysis requires positive finite nuclear masses.")
    # Construct 3N 1D mass vector (mx, my, mz for each atom)
    m3n = np.repeat(masses, 3)

    # Mass-weight the Hessian: H_mw[i, j] = H[i, j] / sqrt(m[i] * m[j])
    inv_sqrt_m = 1.0 / np.sqrt(m3n)
    h_mw = cart_hessian * np.outer(inv_sqrt_m, inv_sqrt_m)

    # Symmetrize to eliminate machine precision drift
    h_mw = 0.5 * (h_mw + h_mw.T)

    evals, evecs = np.linalg.eigh(h_mw)  # type: ignore[attr-defined]

    # Convert eigenvalues in Hartree / (Bohr^2 * u) to harmonic wavenumbers in cm^-1
    frequencies: List[float] = []
    for val in evals:
        if val >= 0.0:
            freq = math.sqrt(val) * HESSIAN_EIG_TO_CM_INV_FACTOR
        else:
            freq = -math.sqrt(-val) * HESSIAN_EIG_TO_CM_INV_FACTOR
        frequencies.append(freq)

    sort_idx: List[int] = sorted(range(len(frequencies)), key=lambda k: frequencies[k])
    sorted_freqs = np.array([frequencies[idx] for idx in sort_idx], dtype=float)
    sorted_modes = np.array([evecs[:, idx] for idx in sort_idx], dtype=float).T

    return sorted_freqs, sorted_modes


def reanalyze_isotopologue(
    cart_hessian: np.ndarray,
    coords: np.ndarray,
    symbols: Sequence[str],
    substituted_mass_numbers: Sequence[Optional[int]],
    iso_label: str,
) -> Dict[str, Any]:
    """
    Executes the zero-cost Isotopologue Shortcut (Method Matrix §8B.4 Arrow 7).
    Re-diagonalizes the saved Cartesian Hessian with substituted isotopic masses,
    recalculating harmonic frequencies, moments of inertia, and rotational constants.
    """
    freqs, modes = diagonalize_mass_weighted_hessian(cart_hessian, symbols, substituted_mass_numbers)
    rot = compute_rotational_constants(symbols, coords, substituted_mass_numbers)

    masses = get_atomic_masses_for_symbols(symbols, substituted_mass_numbers)
    vib_freqs, _ = projected_harmonic_frequencies(cart_hessian, np.asarray(coords, dtype=float), masses)

    return {
        "iso_label": iso_label,
        "substituted_mass_numbers": list(substituted_mass_numbers),
        "frequencies_cm_inv": freqs.tolist(),
        "vibrational_frequencies_cm_inv": vib_freqs,
        "lowest_harmonic_mode_cm_inv": float(vib_freqs[0]) if vib_freqs else None,
        "A_MHz": rot["A_MHz"],
        "B_MHz": rot["B_MHz"],
        "C_MHz": rot["C_MHz"],
        "inertial_defect_amu_A2": rot["inertial_defect_amu_A2"],
        "Paa_u_A2": rot["Paa_u_A2"],
        "Pbb_u_A2": rot["Pbb_u_A2"],
        "Pcc_u_A2": rot["Pcc_u_A2"],
    }


# ---------------------------------------------------------------------------
# File I/O and Quantum Chemistry Parsers
# ---------------------------------------------------------------------------
def read_xyz(path: Union[str, Path]) -> Tuple[List[str], np.ndarray, str]:
    """Reads a standard XYZ coordinate file. Returns (symbols, coords (N, 3), comment)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"XYZ file not found: {p.resolve()}")

    lines = p.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"XYZ file is empty: {p.resolve()}")

    try:
        num_atoms = int(lines[0].split()[0])
    except Exception as exc:
        raise ValueError(f"Invalid atom count line in XYZ file {p.resolve()}: {lines[0]}") from exc

    if num_atoms < 1 or len(lines) < 2 or any(line.strip() for line in lines[2 + num_atoms:]):
        raise ValueError("XYZ must contain one complete, nonempty geometry.")
    comment = lines[1]
    symbols: List[str] = []
    coords: List[List[float]] = []

    for idx, ln in enumerate(lines[2 : 2 + num_atoms], start=3):
        parts = ln.split()
        if len(parts) < 4:
            raise ValueError(f"Malformed coordinate line {idx} in {p.resolve()}: '{ln}'")
        symbols.append(parts[0])
        coords.append([float(parts[1]), float(parts[2]), float(parts[3])])

    if len(symbols) != num_atoms:
        raise ValueError(f"Header declared {num_atoms} atoms but found {len(symbols)} in {p.resolve()}")

    coordinates = np.array(coords, dtype=float)
    if coordinates.shape != (num_atoms, 3) or not np.isfinite(coordinates).all():
        raise ValueError("XYZ coordinates must be finite and have shape (N, 3).")
    return symbols, coordinates, comment


def write_xyz(
    path: Union[str, Path],
    symbols: Sequence[str],
    coords: np.ndarray,
    comment: str = "Generated by CoChem chain.py",
) -> None:
    """Writes standard XYZ coordinate file."""
    p = Path(path)
    assert_writable_path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    coords_arr = np.array(coords, dtype=float)
    assert len(symbols) == coords_arr.shape[0], "Atom count mismatch between symbols and coords."

    lines = [str(len(symbols)), comment]
    for i, sym in enumerate(symbols):
        x, y, z = coords_arr[i, 0], coords_arr[i, 1], coords_arr[i, 2]
        lines.append(f"{sym:<4} {x:24.16f} {y:24.16f} {z:24.16f}")

    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _finite_number(token: str) -> float:
    value = float(token.replace("D", "E").replace("d", "e"))
    if not math.isfinite(value):
        raise ValueError("Nonfinite numeric evidence is not admissible.")
    return value


def _indexed_matrix(lines: List[str], dimension: int) -> np.ndarray:
    """Read every cell exactly once from ORCA's column-block representation."""
    if len(lines) < dimension + 1:
        raise ValueError("Truncated matrix block.")
    matrix = np.empty((dimension, dimension), dtype=np.float64)
    columns_seen: Set[int] = set()
    index = 0
    while index < len(lines):
        columns = [int(value) for value in lines[index].split()]
        index += 1
        if (not columns or len(set(columns)) != len(columns)
                or any(column < 0 or column >= dimension or column in columns_seen for column in columns)):
            raise ValueError("Duplicate, missing, or invalid matrix column index.")
        rows_seen: Set[int] = set()
        for _ in range(dimension):
            if index >= len(lines):
                raise ValueError("Truncated matrix block.")
            values = lines[index].split()
            index += 1
            if len(values) != len(columns) + 1:
                raise ValueError("Matrix row length does not match its column header.")
            row = int(values[0])
            if row < 0 or row >= dimension or row in rows_seen:
                raise ValueError("Duplicate or invalid matrix row index.")
            rows_seen.add(row)
            matrix[row, columns] = [_finite_number(value) for value in values[1:]]
        columns_seen.update(columns)
    if columns_seen != set(range(dimension)):
        raise ValueError("Incomplete matrix: not every column was supplied.")
    return matrix


def parse_orca_hessian(path: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """Parse complete finite ORCA Hessian evidence, rejecting partial blocks."""
    p = Path(path)
    if not p.exists():
        return None
    blocks: Dict[str, List[str]] = {}
    current = None
    for raw_line in p.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("$"):
            current = line
            if current in blocks:
                raise CorruptOutputError(f"Duplicate ORCA Hessian block {current}.")
            blocks[current] = []
        elif line and current is not None:
            blocks[current].append(line)
    try:
        data = blocks["$hessian"]
        if len(data[0].split()) != 1:
            raise ValueError("Invalid Hessian dimension header.")
        dimension = int(data[0])
        if dimension <= 0 or dimension % 3:
            raise ValueError("Hessian dimension must be a positive multiple of three.")
        hessian = _indexed_matrix(data[1:], dimension)
        if not np.allclose(hessian, hessian.T, rtol=1e-8, atol=1e-10):
            raise ValueError("Cartesian Hessian must be symmetric.")
        frequencies = None
        if "$vibrational_frequencies" in blocks:
            data = blocks["$vibrational_frequencies"]
            if int(data[0]) != dimension or len(data) != dimension + 1:
                raise ValueError("Frequency block does not match the Hessian dimension.")
            frequencies = np.empty(dimension, dtype=float)
            seen = set()
            for row in data[1:]:
                tokens = row.split()
                if len(tokens) != 2:
                    raise ValueError("Invalid frequency row.")
                index = int(tokens[0])
                if index < 0 or index >= dimension or index in seen:
                    raise ValueError("Duplicate or invalid frequency index.")
                seen.add(index)
                frequencies[index] = _finite_number(tokens[1])
        atoms = []
        if "$atoms" in blocks:
            data = blocks["$atoms"]
            count = int(data[0])
            if count * 3 != dimension or len(data) != count + 1:
                raise ValueError("Atom block does not match the Hessian dimension.")
            for row in data[1:]:
                tokens = row.split()
                if len(tokens) != 5:
                    raise ValueError("Invalid atom row.")
                mass = _finite_number(tokens[1])
                if mass <= 0:
                    raise ValueError("Hessian atom masses must be positive.")
                atoms.append({"symbol": tokens[0], "mass": mass,
                              "coords": [_finite_number(value) for value in tokens[2:]]})
        modes = None
        if "$normal_modes" in blocks:
            data = blocks["$normal_modes"]
            if [int(value) for value in data[0].split()] != [dimension, dimension]:
                raise ValueError("Normal-mode dimensions do not match the Hessian.")
            modes = _indexed_matrix(data[1:], dimension)
        return {"hessian": hessian, "frequencies": frequencies, "atoms": atoms, "normal_modes": modes}
    except (KeyError, IndexError, ValueError, OverflowError) as exc:
        raise CorruptOutputError(f"Invalid ORCA Hessian {p}: {exc}") from exc


def parse_orca_energy(path: Union[str, Path]) -> Optional[float]:
    """Return final finite energy; never reuse earlier energy after invalid evidence."""
    p = Path(path)
    if not p.exists():
        return None
    for line in reversed(p.read_text(encoding="utf-8").splitlines()):
        match = re.search(r"(?:FINAL SINGLE POINT ENERGY|FINAL ENERGY|Total Energy\s*:)\s*(\S+)", line, re.I)
        if match:
            try:
                return _finite_number(match.group(1))
            except ValueError as exc:
                raise CorruptOutputError("Invalid final ORCA energy.") from exc
    return None


def parse_orca_convergence(path: Union[str, Path]) -> Dict[str, Any]:
    """Parses geometry optimization convergence indicators from ORCA output."""
    p = Path(path)
    if not p.exists():
        return {"normal_termination": False, "opt_converged": False, "iterations": 0}

    content = p.read_text(encoding="utf-8", errors="ignore")
    normal_term = "ORCA TERMINATED NORMALLY" in content
    opt_converged = (
        "*** OPTIMIZATION RUN DONE ***" in content
        or "THE OPTIMIZATION HAS CONVERGED" in content
        or "HURRAY" in content
    )

    # Count geometry cycles
    geom_cycles = content.count("GEOMETRY OPTIMIZATION CYCLE")

    # Check for imaginary frequencies warning
    has_imag_freq = "WARNING: The structure has" in content and "imaginary frequencies" in content

    return {
        "normal_termination": normal_term,
        "opt_converged": opt_converged,
        "iterations": geom_cycles,
        "has_imag_freq": has_imag_freq,
    }


def parse_xtb_output(path: Union[str, Path]) -> Dict[str, Any]:
    """Parses xTB optimization or frequency output."""
    p = Path(path)
    if not p.exists():
        return {"normal_termination": False, "energy_hartree": None, "converged": False}

    content = p.read_text(encoding="utf-8", errors="ignore")
    # Native xTB sends the normal-termination marker to stderr. Require that
    # marker, rather than accepting an informational timestamp as success.
    error_path = p.with_suffix(".err")
    diagnostic = error_path.read_text(encoding="utf-8", errors="replace") if error_path.is_file() else ""
    normal_term = "normal termination of xtb" in (content + "\n" + diagnostic).lower()
    converged = "GEOMETRY OPTIMIZATION CONVERGED" in content

    final_e: Optional[float] = None
    for ln in content.splitlines():
        # Only the final summary's delimited Hartree field is authoritative;
        # intermediate 'total energy : ... change' and 'energy gain' are not.
        match = re.search(r"\|\s*TOTAL ENERGY\s+(\S+)\s+Eh\s*\|", ln)
        if match:
            try:
                final_e = _finite_number(match.group(1))
            except ValueError as exc:
                raise CorruptOutputError("Invalid final xTB energy.") from exc

    return {
        "normal_termination": normal_term,
        "converged": converged,
        "energy_hartree": final_e,
    }


# ---------------------------------------------------------------------------
# Dangerous Reuse Guards -- Rules D1–D5 (§8B.5)
# ---------------------------------------------------------------------------
def validate_rule_d1_geometry_stationarity(
    stage: Stage,
    current_record: StateRecord,
    prev_record: Optional[StateRecord],
) -> List[str]:
    """
    Rule D1: A geometry whose intermolecular error exceeds target must not be reported as higher level.
    Validates stationarity and reports ΔR in MHz of ΔB.
    """
    warnings: List[str] = []
    if prev_record is not None:
        shift_metrics = compute_delta_r_and_delta_b(
            prev_record.geometry, current_record.geometry, current_record.symbols
        )
        delta_b = shift_metrics["delta_B_MHz"]
        rmsd_pm = shift_metrics["rmsd_pm"]
        logger.info(
            f"[Rule D1 Audit] Stage '{stage.name}' shift: dR = {rmsd_pm:.2f} pm, "
            f"projected dB = {delta_b:.2f} MHz ({shift_metrics['rel_B_error_pct']:.3f}%)"
        )
        if rmsd_pm > 5.0:
            warnings.append(
                f"Rule D1 Warning: Inter-stage coordinate shift dR = {rmsd_pm:.2f} pm exceeds 5.0 pm threshold."
            )

    return warnings


def validate_rule_d2_hessian_reuse(
    stage: Stage,
    hessian: np.ndarray,
    symbols: Sequence[str],
    coords: np.ndarray,
    prev_hessian: Optional[np.ndarray] = None,
) -> List[str]:
    """
    Rule D2: A Hessian is a second derivative at a point.
    Flags any mode below ~100 cm^-1 for exclusion from substituted hybrid treatments.
    Detects spurious imaginary modes indicating non-stationary geometry.
    """
    warnings: List[str] = []
    freqs, _ = diagonalize_mass_weighted_hessian(hessian, symbols)

    # Check for imaginary frequencies (excluding translations/rotations)
    imag_modes = [f for f in freqs if f < -10.0]
    if imag_modes:
        warnings.append(
            f"Rule D2 Alert: Found {len(imag_modes)} imaginary frequency mode(s) (lowest: {imag_modes[0]:.1f} cm^-1). "
            f"Geometry is non-stationary or in transition basin."
        )

    # Check for floppy modes <100 cm^-1 on semi-rigid manifold
    floppy_modes = [f for f in freqs if 20.0 < f < 100.0]
    if floppy_modes:
        warnings.append(
            f"Rule D2 Notice: Detected {len(floppy_modes)} floppy mode(s) <100 cm^-1 (lowest: {floppy_modes[0]:.1f} cm^-1). "
            f"Must be excluded from substituted hybrid anharmonic force fields."
        )

    return warnings


def validate_rule_d3_scf_stability(
    stage: Stage,
    out_path: Path,
) -> List[str]:
    """
    Rule D3: SCF converging to different or symmetry-broken solution from reused density.
    Checks for convergence alarms or high iteration count signatures.
    """
    warnings: List[str] = []
    if not out_path.exists():
        return warnings

    content = out_path.read_text(encoding="utf-8", errors="ignore")
    if "SCF NOT CONVERGED" in content or "DID NOT CONVERGE" in content:
        warnings.append(f"Rule D3 Violation: SCF failed to converge in stage '{stage.name}'.")

    return warnings


def validate_rule_d4_counterpoise_ghosts(
    stage: Stage,
    symbols: Sequence[str],
) -> List[str]:
    """
    Rule D4: Counterpoise and ghost-atom inconsistency.
    Never reuse dimer .gbw as guess for ghosted monomer leg.
    """
    warnings: List[str] = []
    has_ghosts = any(":" in s for s in symbols)
    if has_ghosts and stage.mo_from and "dimer" in stage.mo_from.lower():
        warnings.append(
            f"Rule D4 Violation: Stage '{stage.name}' uses ghost atoms but attempts to read dimer MO file '{stage.mo_from}.gbw'."
        )

    return warnings


def validate_rule_d5_naming_hygiene(stages: Sequence[Stage]) -> List[str]:
    """
    Rule D5: Silent state contamination from same-named file.
    Every stage must own a unique %base so reader is never writer.
    """
    warnings: List[str] = []
    seen_names: Set[str] = set()
    for st in stages:
        if st.name in seen_names:
            warnings.append(f"Rule D5 Violation: Duplicate stage name / %base '{st.name}' detected.")
        seen_names.add(st.name)
        if st.mo_from == st.name:
            warnings.append(f"Rule D5 Violation: Stage '{st.name}' reads its own .gbw as guess (reader == writer).")

    return warnings


# Method Matrix §8B.5 Dangerous Reuse (D1–D5) Integrity Auditing Engine
# Delegated to canonical auditor.py module (§8B.5, Suggestion #157)
from .auditor import StateChainingAuditor  # noqa: E402


# ---------------------------------------------------------------------------
# The Chain Orchestrator Class (Method Matrix §8B, §8C)
# ---------------------------------------------------------------------------
class Chain:
    """
    Canonical State-Chaining Driver and Execution-Arrow Recorder for CoChem.
    Persists all geometry, orbital, and Hessian transitions into one unified HDF5 file.
    """

    def __init__(
        self,
        workdir: Union[str, Path] = "chain",
        h5: Optional[Union[str, Path]] = None,
        h5_path: Optional[Union[str, Path]] = None,
        complex_name: str = "complex",
        charge: int = 0,
        mult: int = 1,
        nproc: int = 1,
        maxcore: int = 1024,
        orca_cmd: str = "orca",
        xtb_cmd: str = "xtb",
        strict_guards: bool = True,
        registry_path: Optional[Union[str, Path]] = None,
        telemetry_path: Optional[Union[str, Path]] = None,
        t9_fallback: Optional[Dict[str, Any]] = None,
    ) -> None:
        if isinstance(charge, bool) or not isinstance(charge, int):
            raise ValueError("Charge must be an integer.")
        for name, value in (("multiplicity", mult), ("nproc", nproc), ("maxcore", maxcore)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer.")
        self.workdir = Path(workdir).expanduser().resolve()
        assert_writable_path(self.workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        h5_target = h5_path if h5_path is not None else (h5 if h5 is not None else "campaign.h5")
        h5_p = Path(h5_target)
        if h5_p.is_absolute():
            self.h5_path = h5_p
        elif len(h5_p.parts) > 1:
            self.h5_path = h5_p.resolve()
        else:
            self.h5_path = (self.workdir / h5_p).resolve()
        assert_writable_path(self.h5_path)
        self.h5_path.parent.mkdir(parents=True, exist_ok=True)
        self.complex_name = complex_name
        self.charge = charge
        self.mult = mult
        self.nproc = nproc
        self.maxcore = maxcore
        self.orca_cmd = orca_cmd
        self.xtb_cmd = xtb_cmd
        self.strict_guards = strict_guards
        self.registry_path = registry_path
        self.telemetry_path = telemetry_path
        self._planning_geometry: Optional[Tuple[List[str], np.ndarray]] = None
        self.t9_fallback = None
        if t9_fallback is not None:
            from cochem_base.calc.t9_fallback import T9FallbackConfig
            self.t9_fallback = T9FallbackConfig.model_validate(t9_fallback)
        self.stage_records: Dict[str, StateRecord] = {}

        # Initialize HDF5 metadata store
        self._init_hdf5_store()

    def _init_hdf5_store(self) -> None:
        """Initializes the HDF5 metadata header and schema groups."""
        lock = FileLock(Path(f"{self.h5_path}.lock"), timeout=10.0)
        with lock:
            with h5py.File(self.h5_path, "a", libver="latest") as f:
                meta = f.require_group("meta")
                meta.attrs.setdefault("schema_name", "cochem_state_chain")
                meta.attrs.setdefault("schema_version", 1)
                meta.attrs.setdefault("created_utc", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                meta.attrs.setdefault("complex", self.complex_name)
                meta.attrs.setdefault("charge", self.charge)
                meta.attrs.setdefault("multiplicity", self.mult)
                f.require_group("chain")
                f.require_group("isotopologues")
                f.require_group("lineage")

    def build_stage_input(self, stage: Stage, geom_file: str, *, allow_planned_checkpoints: bool = False) -> str:
        """
        Synthesizes the complete ORCA input deck for a stage, encoding:
        - Unique %base name (Rule D5)
        - Memory (%maxcore) & Parallelism (%pal nprocs)
        - MO guess projection (! MORead + %moinp)
        - Initial Hessian configuration (InHess XTB2 / InHess Read)
        - Tight convergence threshold block (%geom)
        """
        for name in (stage.name, stage.geom_from, stage.mo_from, stage.hess_from):
            if name is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
                raise ValueError("Stage identifiers must be safe filename components.")
        if stage.engine.lower() != "orca":
            raise ValueError("ORCA deck builder requires an ORCA stage.")
        if stage.name in (stage.geom_from, stage.mo_from, stage.hess_from):
            raise ValueError("Stage output cannot overwrite its input checkpoint.")
        if any(char in geom_file for char in '\r\n"*') or Path(geom_file).name != geom_file:
            raise ValueError("Geometry input must be a safe local filename.")
        if stage.guess_mode not in {"FMatrix", "CMatrix", ""}:
            raise ValueError("Unsupported ORCA guess projection mode.")
        # Raw blocks must not override validated geometry, dispersion, resource,
        # grid or checkpoint policy. The existing high-level stage only needs MDCI.
        if stage.blocks and not re.fullmatch(r"\s*%mdci\s+[^%!*#]*\bend\s*", stage.blocks, re.I):
            raise ValueError("Only a single MDCI block is supported; use structured stage policy fields.")
        if stage.counterpoise != "none":
            raise ValueError("A Chain stage cannot certify counterpoise without all executed reference legs.")
        source = self.workdir / geom_file
        if source.is_file():
            symbols, coords, _ = read_xyz(source)
        elif self._planning_geometry is not None:
            # The original real geometry validates a planned deck. It is never
            # stored as an optimized result or supplied to a live missing stage.
            symbols, coords = self._planning_geometry
        else:
            raise ValueError("A real input geometry is required to validate stage policy.")
        from cochem_base.geometry.fragment_partitioner import detect_molecular_fragments
        fragments = detect_molecular_fragments(symbols, coords.tolist())
        weak_complex = len(fragments) > 1
        checkpoint = None
        if stage.hess_from:
            choices = [self.workdir / f"{stage.hess_from}.{suffix}" for suffix in ("opt", "hess")]
            checkpoint = next((path for path in choices if path.is_file()), None)
            if checkpoint is None and not allow_planned_checkpoints:
                raise CorruptOutputError("InHess READ requires an existing Hessian checkpoint.")
            if checkpoint is not None and checkpoint.stat().st_size == 0:
                raise CorruptOutputError("InHess READ checkpoint is empty.")
        if stage.mo_from:
            orbital = self.workdir / f"{stage.mo_from}.gbw"
            if orbital.is_file() and orbital.stat().st_size == 0 or not orbital.is_file() and not allow_planned_checkpoints:
                raise CorruptOutputError("MORead requires an existing nonempty orbital checkpoint.")
        policy = MoleculeInput(
            basin_id=stage.name, elements=symbols, coordinates=coords.tolist(),
            theory_level=stage.level, charge=self.charge, multiplicity=self.mult,
            is_opt=bool(re.search(r"(?i)\b(?:tightopt|verytightopt|opt)\b", stage.level)),
            is_freq=bool(re.search(r"(?i)\b(?:freq|numfreq|anfreq)\b", stage.level)),
            tier=int(canonical_tier_for_method(stage.level)[1:]),
            recipe=stage.recipe, product_class=stage.product_class,
            is_weak_complex=weak_complex,
            frozen_monomer_indices=list(range(len(symbols))) if weak_complex and "opt" in stage.level.lower() else None,
            implicit_solvation=stage.implicit_solvation,
            geometry_source=stage.geometry_source, ab_initio_relaxed=stage.ab_initio_relaxed,
            cbs_cardinal_pair=stage.cbs_cardinal_pair,
            initial_hessian="READ" if checkpoint is not None else "XTB2",
            hessian_file=checkpoint,
        )
        from cochem_base.analysis.electronic_sanitizer import ElectronicSanitizer
        dispersion = ElectronicSanitizer.sanitize_dft_dispersion(
            stage.level, is_complex=len(fragments) > 1, num_monomers=len(fragments),
        )
        route = re.sub(r"(?i)\bDEFGRID\d+\b", "", stage.level).strip()
        route_tokens = [f"! {route} {policy.resolved_grid()} NoSym"]
        if stage.implicit_solvation:
            route_tokens.append(stage.implicit_solvation)
        if stage.mo_from:
            route_tokens.append("MORead")

        input_lines: List[str] = [
            " ".join(route_tokens),
            f'%base "{stage.name}"',
            f"%pal nprocs {self.nproc} end",
            f"%maxcore {self.maxcore}",
        ]

        if stage.mo_from:
            input_lines.append(f'%moinp "{stage.mo_from}.gbw"')
            if stage.guess_mode:
                input_lines.append(f"%scf GuessMode {stage.guess_mode} end")

        # Configure geometry and initial Hessian block if optimization is requested
        if "opt" in stage.level.lower():
            geom_block_lines = [TIGHT_GEOM_BLOCK.rstrip("\n")]
            if stage.hess_from:
                opt_file = self.workdir / f"{stage.hess_from}.opt"
                src_name = f"{stage.hess_from}.hess" if (self.workdir / f"{stage.hess_from}.hess").exists() and not opt_file.exists() else f"{stage.hess_from}.opt"
                geom_block_lines.extend(["  InHess Read", f'  InHessName "{src_name}"'])
            else:
                geom_block_lines.append("  InHess XTB2")  # Cheap model Hessian default (§8B.3)

            if policy.frozen_monomer_indices:
                from cochem_base.calc.cochem_calc_input_generator import build_internal_coordinate_constraints
                from cochem_base.geometry.fragment_partitioner import detect_molecular_fragments
                if len(detect_molecular_fragments(symbols, coords.tolist())) < 2:
                    raise ValueError("Frozen-monomer recipes require at least two molecular fragments.")
                constraints = build_internal_coordinate_constraints(symbols, coords.tolist(), policy.frozen_monomer_indices)
                geom_block_lines.extend(["  Constraints", *[f"    {line}" for line in constraints], "  end"])

            input_lines.append("%geom\n" + "\n".join(geom_block_lines) + "\nend")

        if stage.blocks:
            input_lines.append(stage.blocks)
        if dispersion.get("requires_atm_3body") and "D3" in dispersion.get("dispersion", ""):
            input_lines.append("%method\n  D3S9 1.0\nend")

        input_lines.append(f"* xyzfile {self.charge} {self.mult} {geom_file}")
        return "\n".join(input_lines) + "\n"

    def record_to_hdf5(self, rec: StateRecord) -> None:
        """
        Persists an execution record into the HDF5 store with chunking,
        gzip level 4 compression, shuffle filter, and fletcher32 checksums.
        """
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", rec.stage):
            raise ValueError("Invalid stage name.")
        planned = rec.exit_status in {"DECK_GENERATED", "PENDING_INTEGRATION"}
        if planned:
            if rec.converged or rec.energy_hartree is not None or np.asarray(rec.geometry).size:
                raise ValueError("A generated deck or pending integration cannot contain a converged physical result.")
            if rec.exit_status == "PENDING_INTEGRATION":
                from cochem_base.interfaces.scientific_jobs import load_calculation_handoff
                if not isinstance(rec, PendingStateRecord) or not rec.handoff_manifest:
                    raise ValueError("Pending stages require an actual validated scientific job handoff")
                load_calculation_handoff(rec.handoff_manifest)
        elif (not rec.converged or rec.exit_status != "SUCCESS" or rec.energy_hartree is None
              or not math.isfinite(rec.energy_hartree)
              or np.asarray(rec.geometry).shape != (len(rec.symbols), 3)
              or not rec.symbols or not np.isfinite(rec.geometry).all()):
            raise ValueError("Only verified finite physical records may be published.")
        for name, value, shape in (
            ("hessian", rec.hessian, (3 * len(rec.symbols), 3 * len(rec.symbols))),
            ("gradient", rec.gradient, (len(rec.symbols), 3)),
        ):
            if value is not None and (planned or np.asarray(value).shape != shape or not np.isfinite(value).all()):
                raise ValueError(f"Invalid {name} evidence.")
        if rec.frequencies_cm_inv is not None and (planned or not np.isfinite(rec.frequencies_cm_inv).all()):
            raise ValueError("Invalid frequency evidence.")
        assert_writable_path(self.h5_path)
        lock = FileLock(Path(f"{self.h5_path}.lock"), timeout=10.0)
        with lock:
            with h5py.File(self.h5_path, "a", libver="latest") as f:
                if f"chain/{rec.stage}" in f:
                    raise ValueError("Stage already exists in this campaign; use a new basename.")
                grp = f.require_group(f"chain/{rec.stage}")
                grp.attrs["level"] = rec.level
                grp.attrs["wall_s"] = rec.wall_s
                grp.attrs["consumed"] = json.dumps(rec.consumed_files)
                grp.attrs["produced"] = json.dumps(rec.produced_files)
                grp.attrs["written_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                grp.attrs["converged"] = rec.converged
                grp.attrs["exit_status"] = rec.exit_status
                if isinstance(rec, PendingStateRecord):
                    grp.attrs["handoff_manifest"] = rec.handoff_manifest
                    grp.attrs["handoff_manifest_sha256"] = hashlib.sha256(Path(rec.handoff_manifest).read_bytes()).hexdigest()
                grp.attrs["symbols"] = json.dumps(rec.symbols)
                grp.attrs["n_atoms"] = len(rec.symbols)

                if rec.arrow_index is not None:
                    grp.attrs["arrow_index"] = rec.arrow_index
                    grp.attrs["arrow_desc"] = rec.arrow_desc

                if rec.energy_hartree is not None:
                    grp.attrs["energy_hartree"] = rec.energy_hartree

                if rec.rotational_constants_mhz is not None:
                    grp.attrs["rotational_constants_mhz"] = json.dumps(list(rec.rotational_constants_mhz))

                if rec.inertial_defect_amu_a2 is not None:
                    grp.attrs["inertial_defect_amu_a2"] = rec.inertial_defect_amu_a2

                if rec.planar_moments_amu_a2 is not None:
                    grp.attrs["planar_moments_amu_a2"] = json.dumps(list(rec.planar_moments_amu_a2))

                if rec.warnings:
                    grp.attrs["warnings"] = json.dumps(rec.warnings)

                if planned:
                    return

                # Persist Geometry Dataset
                if "geometry" in grp:
                    del grp["geometry"]
                grp.create_dataset(
                    "geometry",
                    data=np.asarray(rec.geometry, dtype=np.float64),
                    compression="gzip",
                    compression_opts=4,
                    shuffle=True,
                    fletcher32=True,
                )

                # Persist Hessian Dataset if available
                if rec.hessian is not None:
                    if "hessian" in grp:
                        del grp["hessian"]
                    grp.create_dataset(
                        "hessian",
                        data=np.asarray(rec.hessian, dtype=np.float64),
                        compression="gzip",
                        compression_opts=4,
                        shuffle=True,
                        fletcher32=True,
                    )

                # Persist Gradient Dataset if available
                if rec.gradient is not None:
                    if "gradient" in grp:
                        del grp["gradient"]
                    grp.create_dataset(
                        "gradient",
                        data=np.asarray(rec.gradient, dtype=np.float64),
                        compression="gzip",
                        compression_opts=4,
                        shuffle=True,
                        fletcher32=True,
                    )

                # Persist Frequencies Dataset if available
                if rec.frequencies_cm_inv is not None:
                    if "frequencies" in grp:
                        del grp["frequencies"]
                    grp.create_dataset(
                        "frequencies",
                        data=np.asarray(rec.frequencies_cm_inv, dtype=np.float64),
                        compression="gzip",
                        compression_opts=4,
                        shuffle=True,
                        fletcher32=True,
                    )
        if not planned:
            campaign_id = hashlib.sha256(str(self.workdir).encode("utf-8")).hexdigest()[:16]
            append_scientific_result(
                f"chain_{campaign_id}_{rec.stage}", rec.symbols, rec.geometry,
                rec.energy_hartree, gradients=rec.gradient,
                metadata={"source": "Chain", "stage": rec.stage, "level": rec.level,
                          "wall_seconds": rec.wall_s, "campaign_metadata": str(self.h5_path)},
                store_path=self.telemetry_path,
            )

    def prepare_scientific_stage(
        self, stage: Stage, calculation_config: Any,
        seed_xyz: Optional[Union[str, Path]] = None,
    ) -> PendingStateRecord:
        """Preserve structured future-module inputs and all checkpoint bytes.

        Raw route/blocks remain verbatim provider options. They are not silently
        translated into another engine's grammar or accepted as a physical result.
        """
        from cochem_base.calc.calculation_service import CalculationMatrixConfig, parse_run_geometry
        from cochem_base.interfaces.scientific_jobs import (
            calculation_capability, prepare_calculation_handoff, validate_job_configuration,
        )
        config = (calculation_config if isinstance(calculation_config, CalculationMatrixConfig)
                  else CalculationMatrixConfig.model_validate(calculation_config))
        validate_job_configuration(config)
        if calculation_capability(config).adapter_status != "pending_integration":
            raise ValueError("This operation has a native adapter; use run_calculation or run_stage to execute it")
        for name in (stage.name, stage.geom_from, stage.mo_from, stage.hess_from):
            if name is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
                raise ValueError("Stage identifiers must be safe filename components.")
        if stage.name in (stage.geom_from, stage.mo_from, stage.hess_from) or stage.name in self.stage_records:
            raise ValueError("Every stage must own a unique output basename.")
        if (config.engine != stage.engine.lower() or config.charge != self.charge
                or config.multiplicity != self.mult):
            raise ValueError("Structured job engine, charge and multiplicity must match its Chain stage")
        route = stage.level.lower().split()
        if (config.method.lower() not in route or config.basis_set and config.basis_set.lower() not in route
                or bool(re.search(r"(?i)\bVPT2\b", stage.level)) != config.is_vpt2):
            raise ValueError("Structured method, basis and VPT2 request must agree with the preserved stage route")
        if config.engine == "orca":
            MoleculeInput(
                basin_id=stage.name, elements=parse_run_geometry(config.geometry)[0],
                coordinates=parse_run_geometry(config.geometry)[1], theory_level=stage.level,
                charge=config.charge, multiplicity=config.multiplicity, is_opt=config.is_opt,
                is_freq=config.is_freq, is_vpt2=config.is_vpt2, grid_stage=config.grid_stage,
                product_class=config.product_class, recipe=config.recipe,
            )
        dependencies: Dict[str, Path] = {}
        for source in (stage.geom_from, stage.mo_from, stage.hess_from):
            if source in self.stage_records and not self.stage_records[source].converged:
                raise ConvergenceFailureError(f"Source stage {source!r} has not converged.")
        if stage.geom_from:
            seed_xyz = self.workdir / f"{stage.geom_from}.xyz"
        if seed_xyz is not None:
            seed = Path(seed_xyz).expanduser()
            if not seed.is_absolute() and not seed.is_file():
                seed = self.workdir / seed
            if parse_run_geometry(seed.read_text()) != parse_run_geometry(config.geometry):
                raise ValueError("Structured job geometry differs from the supplied Chain input")
            dependencies["source_geometry.xyz"] = seed
        if stage.mo_from:
            dependencies[f"{stage.mo_from}.gbw"] = self.workdir / f"{stage.mo_from}.gbw"
        if stage.hess_from:
            candidates = [self.workdir / f"{stage.hess_from}.{suffix}" for suffix in ("opt", "hess")]
            checkpoint = next((path for path in candidates if path.is_file()), None)
            if checkpoint is None:
                raise CorruptOutputError("A pending Hessian reuse job requires its actual checkpoint bytes")
            dependencies[checkpoint.name] = checkpoint
        for name in ("hessian_file", "r2_reference_manifest"):
            source = getattr(config, name)
            if source is not None:
                source = source if source.is_absolute() else self.workdir / source
                dependencies[name + source.suffix] = source
        input_geometry = self.workdir / f"{stage.name}.request.xyz"
        if input_geometry.exists():
            raise CorruptOutputError("Pending stage input already exists; use a new basename")
        symbols, coordinates = parse_run_geometry(config.geometry)
        geometry = "\n".join([str(len(symbols)), "Pending Chain scientific job"] +
                             [symbol + " " + " ".join(format(float(value), ".17g") for value in xyz)
                              for symbol, xyz in zip(symbols, coordinates)]) + "\n"
        input_geometry.write_text(geometry, encoding="utf-8")
        destination = self.workdir / f"{stage.name}.handoff"
        prepare_calculation_handoff(
            config, input_geometry, destination, dependency_files=dependencies,
            provider_options={"chain_stage": asdict(stage), "requested_cores": self.nproc,
                              "requested_maxcore_mb": self.maxcore,
                              "raw_route_requires_provider_validation": True},
        )
        record = PendingStateRecord(
            stage=stage.name, level=stage.level, wall_s=0.0, energy_hartree=None,
            symbols=[], geometry=np.empty((0, 3)), converged=False, exit_status="PENDING_INTEGRATION",
            consumed_files=list(dependencies),
            produced_files=[str(path.relative_to(self.workdir)) for path in destination.rglob("*") if path.is_file()],
            arrow_index=stage.arrow_index, arrow_desc=stage.arrow_desc,
            handoff_manifest=str(destination / "handoff.json"),
            warnings=["Input structure and integrity validated; scientific execution has not occurred."],
        )
        self.record_to_hdf5(record)
        self.stage_records[stage.name] = record
        return record

    def run_stage(
        self,
        stage: Stage,
        seed_xyz: Optional[Union[str, Path]] = None,
        dry_run: bool = False,
    ) -> StateRecord:
        """Publish a stage only after real process and scientific evidence succeed."""
        for name in (stage.name, stage.geom_from, stage.mo_from, stage.hess_from):
            if name is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
                raise ValueError("Stage identifiers must be safe filename components.")
        if stage.name in (stage.geom_from, stage.mo_from, stage.hess_from) or stage.name in self.stage_records:
            raise ValueError("Every stage must own a unique output basename.")
        if stage.scientific_config is not None:
            return self.prepare_scientific_stage(stage, stage.scientific_config, seed_xyz)
        if re.search(r"(?i)\bVPT2\b", stage.level) and not dry_run:
            raise ValueError("VPT2 Chain jobs require Stage.scientific_config or prepare_scientific_stage with an explicit CalculationMatrixConfig; BASE will preserve the input for pending adapter integration.")
        if stage.engine.lower() != "orca":
            raise ValueError(f"run_stage does not implement engine {stage.engine!r}.")
        if stage.recipe == "R2" and not dry_run:
            raise ValueError("R2 production requires authenticated CCSD(T)/CBS monomer references and all counterpoise legs; this Chain path cannot certify them.")
        assert_writable_path(self.workdir)
        if stage.geom_from:
            geom_source = f"{stage.geom_from}.xyz"
        elif seed_xyz is not None:
            seed = Path(seed_xyz)
            if not seed.is_absolute() and not seed.exists():
                seed = self.workdir / seed
            symbols, coords, _ = read_xyz(seed)
            normalized, rotation, rmsd = align_coordinates(
                coords, coords, masses=get_atomic_masses_for_symbols(symbols),
            )
            self._planning_geometry = (symbols, normalized)
            source_digest = hashlib.sha256(seed.read_bytes()).hexdigest()
            geom_source = f"{stage.name}_input.xyz"
            target = self.workdir / geom_source
            assert_writable_path(target)
            write_xyz(target, symbols, normalized, "COM/Eckart normalized Chain input")
            (self.workdir / f"{stage.name}.ingress.json").write_text(json.dumps({
                "source_sha256": source_digest,
                "rotation": rotation.tolist(), "mass_weighted_rmsd_angstrom": rmsd,
                "principal_isotope_masses_u": get_atomic_masses_for_symbols(symbols).tolist(),
            }), encoding="utf-8")
        else:
            raise ValueError("A stage requires a geometry source.")
        if geom_source == f"{stage.name}.xyz":
            raise ValueError("Stage output geometry cannot overwrite its input geometry.")
        consumed = [geom_source]
        if stage.mo_from:
            consumed.append(f"{stage.mo_from}.gbw")
        if stage.hess_from:
            suffix = "hess" if (self.workdir / f"{stage.hess_from}.hess").exists() and not (self.workdir / f"{stage.hess_from}.opt").exists() else "opt"
            consumed.append(f"{stage.hess_from}.{suffix}")
        if not dry_run:
            for source in (stage.geom_from, stage.mo_from, stage.hess_from):
                if source in self.stage_records and not self.stage_records[source].converged:
                    raise ConvergenceFailureError(f"Source stage {source!r} has not converged.")
            for name in consumed:
                if not (self.workdir / name).is_file() or (self.workdir / name).stat().st_size == 0:
                    raise CorruptOutputError(f"Required stage input is missing: {name}")
            for suffix in ("xyz", "hess", "gbw", "opt"):
                if (self.workdir / f"{stage.name}.{suffix}").exists():
                    raise CorruptOutputError(f"Refusing stale stage output {stage.name}.{suffix}; use a new basename.")
        inp_path = self.workdir / f"{stage.name}.inp"
        for output in (inp_path, self.workdir / f"{stage.name}.out", self.workdir / f"{stage.name}.err"):
            assert_writable_path(output)
        inp_path.write_text(self.build_stage_input(stage, geom_source, allow_planned_checkpoints=dry_run), encoding="utf-8")
        if dry_run:
            record = StateRecord(
                stage=stage.name, level=stage.level, wall_s=0.0,
                energy_hartree=None, symbols=[], geometry=np.empty((0, 3)),
                consumed_files=consumed, produced_files=[inp_path.name],
                arrow_index=stage.arrow_index, arrow_desc=stage.arrow_desc,
                converged=False, exit_status="DECK_GENERATED",
            )
            self.record_to_hdf5(record)
            self.stage_records[stage.name] = record
            return record
        binary = shutil.which(self.orca_cmd)
        if binary is None:
            raise MissingBinaryError(f"ORCA executable {self.orca_cmd!r} is missing or not executable.")
        authorization = authorize_engine_execution(
            "orca", registry_path=self.registry_path, executable=binary,
            cores=self.nproc, maxcore_mb=self.maxcore,
        )
        input_symbols, input_coords, _ = read_xyz(self.workdir / geom_source)
        ghost_warnings = validate_rule_d4_counterpoise_ghosts(stage, input_symbols)
        if ghost_warnings:
            raise ValueError("; ".join(ghost_warnings))
        out_path = self.workdir / f"{stage.name}.out"
        started = time.monotonic()
        parser = QuantumParser(str(self.workdir))
        def execute_primary() -> None:
            telemetry_cancel = threading.Event()
            campaign_id = hashlib.sha256(str(self.workdir).encode()).hexdigest()[:16]
            trajectory = XYZTrajectoryFollower(
                self.workdir / f"{stage.name}_trj.xyz", f"chain_{campaign_id}_{stage.name}_trajectory",
                input_symbols, source_format="orca", store_path=self.telemetry_path,
                metadata={"engine": "orca", "stage": stage.name}, required=True,
                on_error=lambda error: telemetry_cancel.set(),
            ) if "opt" in stage.level.lower() else nullcontext()
            with trajectory:
                result = safe_subprocess_run(
                    authorization.command([inp_path.name]), cwd=self.workdir, check=False,
                    env=engine_runtime_environment("orca", executable=authorization.executable),
                    capture_output=True, text=True, required_disk_gb=0.1,
                    cpu_affinity=list(authorization.cpu_affinity) or None,
                    cancellation_event=telemetry_cancel,
                    on_stdout_line=SpinContaminationStreamValidator(self.mult), load_full_stdout=True,
                )
            out_path.write_text(result.stdout or "", encoding="utf-8")
            (self.workdir / f"{stage.name}.err").write_text(result.stderr or "", encoding="utf-8")
            if result.returncode:
                raise ConvergenceFailureError(f"ORCA exited {result.returncode}; diagnostics retained at {out_path}.")
            if not parser.verify_scf_convergence(out_path):
                raise ConvergenceFailureError(f"Missing or failed SCF convergence evidence in {out_path}.")
            parser.check_spin_contamination(out_path, multiplicity=self.mult)
        from cochem_base.calc.t9_fallback import execute_with_t9_fallback
        fallback = execute_with_t9_fallback(
            execute_primary, self.t9_fallback, elements=input_symbols, coordinates=input_coords.tolist(),
            charge=self.charge, multiplicity=self.mult, directory=self.workdir / f"{stage.name}_t9",
            registry_path=self.registry_path,
        )
        wall_s = time.monotonic() - started
        if fallback is not None:
            # Never pass a recovered single-point geometry/wavefunction onward
            # as the originally requested optimized state or harmonic Hessian.
            raise ConvergenceFailureError(
                f"Contaminated stage {stage.name} was halted; real T9 single-point recovery is retained "
                f"at {self.workdir / (stage.name + '_t9')}. The requested Chain stage is incomplete."
            )
        is_optimization = "opt" in stage.level.lower()
        if is_optimization:
            parser.verify_geometry_convergence(out_path)
        energy = parse_orca_energy(out_path)
        if energy is None:
            raise CorruptOutputError("A converged stage must supply a finite final electronic energy.")
        stage_xyz_path = self.workdir / f"{stage.name}.xyz"
        if is_optimization and not stage_xyz_path.is_file():
            raise CorruptOutputError("Optimization did not produce its own final XYZ geometry.")
        if stage_xyz_path.is_file():
            symbols, coords, _ = read_xyz(stage_xyz_path)
            if symbols != input_symbols:
                raise CorruptOutputError("Stage output atom identities/order differ from the input geometry.")
        else:
            # Single-point and frequency calculations keep the accepted input geometry.
            symbols, coords = input_symbols, input_coords
        from cochem_base.geometry.fragment_partitioner import detect_molecular_fragments
        if is_optimization and len(detect_molecular_fragments(input_symbols, input_coords.tolist())) > 1:
            from cochem_base.calc.calculation_service import validate_frozen_monomer_trajectory
            drift = validate_frozen_monomer_trajectory(
                self.workdir / f"{stage.name}_trj.xyz", input_symbols,
                input_coords.tolist(), coords.tolist(),
            )
            (self.workdir / f"{stage.name}.monomer_integrity.json").write_text(json.dumps(drift), encoding="utf-8")
        hess_data = parse_orca_hessian(self.workdir / f"{stage.name}.hess")
        if "freq" in stage.level.lower() and hess_data is None:
            raise CorruptOutputError("Frequency stage did not produce its Cartesian Hessian.")
        hessian = hess_data["hessian"] if hess_data else None
        if hessian is not None and hessian.shape != (3 * len(symbols), 3 * len(symbols)):
            raise CorruptOutputError("Hessian dimension differs from the stage geometry.")
        if hess_data and hess_data["atoms"] and [atom["symbol"] for atom in hess_data["atoms"]] != symbols:
            raise CorruptOutputError("Hessian atoms differ from the stage geometry.")
        if hess_data:
            if not hess_data["atoms"]:
                raise CorruptOutputError("A published Hessian requires its complete geometry-bearing $atoms block.")
            hessian_coordinates = np.asarray([atom["coords"] for atom in hess_data["atoms"]]) * BOHR_TO_ANGSTROM
            if not np.allclose(hessian_coordinates, coords, atol=1e-6, rtol=0):
                raise CorruptOutputError("Hessian coordinates do not match the accepted stage geometry.")
        rot = compute_rotational_constants(symbols, coords)
        record = StateRecord(
            stage=stage.name, level=stage.level, wall_s=wall_s,
            energy_hartree=energy, symbols=symbols, geometry=coords,
            hessian=hessian, frequencies_cm_inv=hess_data["frequencies"] if hess_data else None,
            rotational_constants_mhz=(rot["A_MHz"], rot["B_MHz"], rot["C_MHz"]),
            inertial_defect_amu_a2=rot["inertial_defect_amu_A2"],
            planar_moments_amu_a2=(rot["Paa_u_A2"], rot["Pbb_u_A2"], rot["Pcc_u_A2"]),
            consumed_files=consumed, arrow_index=stage.arrow_index, arrow_desc=stage.arrow_desc,
            converged=True, exit_status="SUCCESS",
        )
        if self.strict_guards:
            record.warnings.extend(validate_rule_d1_geometry_stationarity(
                stage, record, self.stage_records.get(stage.geom_from)))
            if hessian is not None:
                record.warnings.extend(validate_rule_d2_hessian_reuse(stage, hessian, symbols, coords))
        if not stage_xyz_path.exists():
            write_xyz(stage_xyz_path, symbols, coords, "Unchanged input geometry of a verified non-optimization stage")
        record.produced_files = [path.name for path in self.workdir.glob(f"{stage.name}.*")]
        self.record_to_hdf5(record)
        self.stage_records[stage.name] = record
        return record

    def run_canonical_pipeline(
        self,
        seed_xyz: Union[str, Path],
        include_xtb: bool = True,
        include_freq: bool = True,
        include_isotopologues: bool = True,
        include_ccsd: bool = False,
        dry_run: bool = False,
    ) -> List[StateRecord]:
        """
        Executes the full Method Matrix §8B.4 Canonical Chained Pipeline:
        - Stage s1_xtb: GFN2-xTB pre-optimization (Arrow 2)
        - Stage s2: r2SCAN-3c TightOpt with InHess XTB2 model Hessian (Arrow 3)
        - Stage s3: wB97X-V/def2-TZVPP TightOpt with s2.gbw + s2.opt (Arrow 4)
        - Stage s4: wB97M-V/def2-QZVPP TightOpt with s3.gbw + s3.opt (Arrow 5)
        - Stage s5: wB97M-V/def2-QZVPP Freq with s4.gbw (Arrow 6)
        - Stage s5b_iso: Isotopologue re-analysis (13C, 18O, D) (Arrow 7)
        - Stage s6: DLPNO-CCSD(T1) on stage s4 geometry with s4.gbw (Arrow 8)
        """
        seed_p = Path(seed_xyz).resolve()
        if not seed_p.exists():
            raise FileNotFoundError(f"Seed coordinate file not found: {seed_p}")

        logger.info(f"Launching Canonical State-Chaining Pipeline for seed: {seed_p.name}")
        seed_symbols, seed_coordinates, _ = read_xyz(seed_p)
        seed_coordinates, _, _ = align_coordinates(
            seed_coordinates, seed_coordinates, masses=get_atomic_masses_for_symbols(seed_symbols),
        )
        self._planning_geometry = (seed_symbols, seed_coordinates)
        from cochem_base.geometry.fragment_partitioner import detect_molecular_fragments
        weak_complex = len(detect_molecular_fragments(seed_symbols, seed_coordinates.tolist())) > 1
        seed_digest = hashlib.sha256(seed_p.read_bytes()).hexdigest()
        ingress_path = self.workdir / f"chain_input_{seed_digest[:16]}.xyz"
        if ingress_path.exists():
            raise ValueError("Canonical input already exists; use a fresh campaign directory.")
        assert_writable_path(ingress_path)
        write_xyz(ingress_path, seed_symbols, seed_coordinates, "COM/Eckart normalized Chain input")
        (self.workdir / "chain_ingress.json").write_text(json.dumps({
            "source_sha256": seed_digest, "original_source": str(seed_p),
            "normalized_input": ingress_path.name,
        }), encoding="utf-8")

        records: List[StateRecord] = []
        active_seed = ingress_path.name

        # An explicitly requested xTB stage must succeed; no raw-seed fallback.
        if include_xtb:
            command = [self.xtb_cmd, ingress_path.name, "--opt", "vtight", "--strict",
                       "--chrg", str(self.charge), "--uhf", str(self.mult - 1)]
            s1_out = self.workdir / "s1_xtb.out"
            s1_xyz = self.workdir / "s1.xyz"
            for output in (s1_out, s1_xyz, self.workdir / "s1_xtb.err", self.workdir / "s1_xtb.command.json"):
                assert_writable_path(output)
            if dry_run:
                deck = self.workdir / "s1_xtb.command.json"
                deck.write_text(json.dumps({"status": "DECK_GENERATED", "command": command}), encoding="utf-8")
                first = StateRecord(
                    stage="s1", level="GFN2-xTB --opt vtight --strict", wall_s=0.0,
                    energy_hartree=None, symbols=[], geometry=np.empty((0, 3)),
                    consumed_files=[ingress_path.name], produced_files=[deck.name], arrow_index=2,
                    converged=False, exit_status="DECK_GENERATED",
                )
            else:
                binary = shutil.which(self.xtb_cmd)
                if binary is None:
                    raise MissingBinaryError(f"Requested xTB executable {self.xtb_cmd!r} is unavailable.")
                authorization = authorize_engine_execution(
                    "xtb", registry_path=self.registry_path, executable=binary,
                    cores=self.nproc, maxcore_mb=self.maxcore,
                )
                if self.mult != 1:
                    raise ValueError("xTB Chain adapter lacks auditable open-shell S² trajectory diagnostics.")
                xtbopt = self.workdir / "xtbopt.xyz"
                if xtbopt.exists() or s1_xyz.exists():
                    raise CorruptOutputError("Refusing stale xTB geometry; use a fresh campaign directory.")
                command[0] = binary
                started = time.monotonic()
                telemetry_cancel = threading.Event()
                campaign_id = hashlib.sha256(str(self.workdir).encode()).hexdigest()[:16]
                with XYZTrajectoryFollower(
                    self.workdir / "xtbopt.log", f"chain_{campaign_id}_s1_trajectory",
                    seed_symbols, source_format="xtb", store_path=self.telemetry_path,
                    metadata={"engine": "xtb", "stage": "s1"}, required=True,
                    on_error=lambda error: telemetry_cancel.set(),
                ):
                    result = safe_subprocess_run(
                        command, cwd=self.workdir, check=False, capture_output=True, text=True,
                        env=engine_runtime_environment("xtb", executable=authorization.executable),
                        required_disk_gb=0.1, on_stdout_line=SpinContaminationStreamValidator(self.mult),
                        cpu_affinity=list(authorization.cpu_affinity) or None,
                        cancellation_event=telemetry_cancel, load_full_stdout=True,
                    )
                wall_s = time.monotonic() - started
                s1_out.write_text(result.stdout or "", encoding="utf-8")
                (self.workdir / "s1_xtb.err").write_text(result.stderr or "", encoding="utf-8")
                if result.returncode:
                    raise ConvergenceFailureError(f"xTB exited {result.returncode}; diagnostics retained at {s1_out}.")
                info = parse_xtb_output(s1_out)
                if not info["normal_termination"] or not info["converged"] or info["energy_hartree"] is None:
                    raise ConvergenceFailureError("xTB lacks explicit convergence, termination, or finite energy evidence.")
                if not xtbopt.is_file():
                    raise CorruptOutputError("xTB did not produce its optimized XYZ geometry.")
                symbols, coordinates, _ = read_xyz(xtbopt)
                if symbols != read_xyz(seed_p)[0]:
                    raise CorruptOutputError("xTB atom identities/order differ from the seed geometry.")
                shutil.copyfile(xtbopt, s1_xyz)
                first = StateRecord(
                    stage="s1", level="GFN2-xTB --opt vtight --strict", wall_s=wall_s,
                    energy_hartree=info["energy_hartree"], symbols=symbols, geometry=coordinates,
                    consumed_files=[ingress_path.name], produced_files=[s1_out.name, s1_xyz.name],
                    arrow_index=2, converged=True, exit_status="SUCCESS",
                )
            self.record_to_hdf5(first)
            self.stage_records["s1"] = first
            records.append(first)
            active_seed = "s1.xyz"

        # Define Canonical Stages
        s2 = Stage(
            name="s2",
            geom_from="s1" if include_xtb else None,
            level="r2SCAN-3c TightOpt TightSCF DEFGRID1",
            arrow_index=3,
            arrow_desc="GFN2-xTB -> r2SCAN-3c with InHess XTB2 model Hessian",
            recipe="R1" if weak_complex else None,
        )
        s3 = Stage(
            name="s3",
            level="wB97X-V def2-TZVPP def2/J RIJCOSX TightOpt TightSCF DEFGRID2",
            geom_from="s2",
            mo_from="s2",
            hess_from="s2",
            arrow_index=4,
            arrow_desc="r2SCAN-3c -> wB97X-V/def2-TZVPP tight optimization",
        )
        s4 = Stage(
            name="s4",
            level="wB97M-V def2-QZVPP def2/J RIJCOSX TightOpt TightSCF DefGrid3",
            geom_from="s3",
            mo_from="s3",
            hess_from="s3",
            arrow_index=5,
            arrow_desc="wB97X-V/TZ -> wB97M-V/def2-QZVPP tight optimization (MO cascade)",
            recipe="R2" if weak_complex else None,
        )
        s5 = Stage(
            name="s5",
            level="wB97M-V def2-QZVPP def2/J RIJCOSX Freq TightSCF DefGrid3",
            geom_from="s4",
            mo_from="s4",
            arrow_index=6,
            arrow_desc="Tight optimization -> analytic DFT Hessian",
            recipe="R2" if weak_complex else None,
        )
        s6 = Stage(
            name="s6",
            level="DLPNO-CCSD(T1) TightPNO cc-pVQZ cc-pVQZ/C TightSCF DEFGRID3",
            geom_from="s4",
            mo_from="s4",
            blocks="%mdci TCutPNO 1e-7 DoLED true StorageType Shared end",
            arrow_index=8,
            arrow_desc="Tight optimization -> high-level DLPNO-CCSD(T1) single point",
        )

        # Validate Naming Hygiene before execution (Rule D5)
        d5_warnings = validate_rule_d5_naming_hygiene([s2, s3, s4, s5, s6])
        if d5_warnings:
            logger.warning(f"Naming hygiene warnings: {d5_warnings}")

        # Execute Stage 2 (r2SCAN-3c)
        r2 = self.run_stage(s2, seed_xyz=active_seed, dry_run=dry_run)
        records.append(r2)

        # Execute Stage 3 (wB97X-V/TZ)
        r3 = self.run_stage(s3, dry_run=dry_run)
        records.append(r3)

        # Execute Stage 4 (wB97M-V/QZ)
        r4 = self.run_stage(s4, dry_run=dry_run)
        records.append(r4)

        # Execute Stage 5 (Analytic Frequency)
        if include_freq:
            r5 = self.run_stage(s5, dry_run=dry_run)
            records.append(r5)

            # Stage 5b: Zero-Cost Isotopologue Campaign (Arrow 7)
            if include_isotopologues and r5.hessian is not None:
                self.run_standard_isotopologue_campaign("s5")

        # Execute Stage 6 (DLPNO Single Point)
        if include_ccsd:
            r6 = self.run_stage(s6, dry_run=dry_run)
            records.append(r6)

        logger.info("Canonical pipeline %s. Database: %s", "decks generated" if dry_run else "verified", self.h5_path)
        return records

    def run_standard_isotopologue_campaign(self, parent_stage: str) -> Dict[str, Dict[str, Any]]:
        """
        Executes standard isotopologue substitution campaign for 13C, 15N, 18O, and 2H (D)
        using the saved Cartesian Hessian from `parent_stage` at zero electronic structure cost.
        """
        rec = self.stage_records.get(parent_stage)
        if rec is None or not rec.converged or rec.exit_status != "SUCCESS" or rec.hessian is None:
            logger.warning(f"Cannot run isotopologue campaign: Stage '{parent_stage}' has no saved Hessian.")
            return {}

        symbols = rec.symbols
        coords = rec.geometry
        hess = rec.hessian

        results: Dict[str, Dict[str, Any]] = {}

        for idx, sym in enumerate(symbols):
            if sym.strip().capitalize() == "N":
                iso_masses = [None] * len(symbols)
                iso_masses[idx] = 15
                label = f"iso_15N_{idx+1}"
                res = reanalyze_isotopologue(hess, coords, symbols, iso_masses, label)
                results[label] = res
                self._record_isotopologue_to_hdf5(label, parent_stage, res)

        # 1. 13C substitution on each Carbon atom
        for idx, sym in enumerate(symbols):
            if sym.strip().capitalize() == "C":
                iso_masses: List[Optional[int]] = [None] * len(symbols)
                iso_masses[idx] = 13
                label = f"iso_13C_{idx+1}"
                res = reanalyze_isotopologue(hess, coords, symbols, iso_masses, label)
                results[label] = res
                self._record_isotopologue_to_hdf5(label, parent_stage, res)

        # 2. 18O substitution on each Oxygen atom
        for idx, sym in enumerate(symbols):
            if sym.strip().capitalize() == "O":
                iso_masses = [None] * len(symbols)
                iso_masses[idx] = 18
                label = f"iso_18O_{idx+1}"
                res = reanalyze_isotopologue(hess, coords, symbols, iso_masses, label)
                results[label] = res
                self._record_isotopologue_to_hdf5(label, parent_stage, res)

        # 3. Deuterium (2H) substitution on each Hydrogen atom
        for idx, sym in enumerate(symbols):
            if sym.strip().capitalize() == "H":
                iso_masses = [None] * len(symbols)
                iso_masses[idx] = 2
                label = f"iso_D_{idx+1}"
                res = reanalyze_isotopologue(hess, coords, symbols, iso_masses, label)
                results[label] = res
                self._record_isotopologue_to_hdf5(label, parent_stage, res)

        logger.info(f"Isotopologue campaign evaluated {len(results)} isotopologues from force field '{parent_stage}'.")
        return results

    def _record_isotopologue_to_hdf5(
        self,
        iso_label: str,
        parent_stage: str,
        iso_data: Dict[str, Any],
    ) -> None:
        """Records isotopologue rotational and vibrational properties into /isotopologues group."""
        assert_writable_path(self.h5_path)
        with FileLock(str(self.h5_path) + ".lock", timeout=10.0):
            with h5py.File(self.h5_path, "a") as f:
                grp = f.require_group(f"isotopologues/{iso_label}")
                grp.attrs["parent_stage"] = parent_stage
                grp.attrs["substituted_masses"] = json.dumps(iso_data["substituted_mass_numbers"])
                grp.attrs["A_MHz"] = iso_data["A_MHz"]
                grp.attrs["B_MHz"] = iso_data["B_MHz"]
                grp.attrs["C_MHz"] = iso_data["C_MHz"]
                grp.attrs["inertial_defect_amu_A2"] = iso_data["inertial_defect_amu_A2"]
                grp.attrs["Paa_u_A2"] = iso_data["Paa_u_A2"]
                grp.attrs["Pbb_u_A2"] = iso_data["Pbb_u_A2"]
                grp.attrs["Pcc_u_A2"] = iso_data["Pcc_u_A2"]
                if iso_data["lowest_harmonic_mode_cm_inv"] is not None:
                    grp.attrs["lowest_harmonic_mode_cm_inv"] = iso_data["lowest_harmonic_mode_cm_inv"]

                if "frequencies" in grp:
                    del grp["frequencies"]
                grp.create_dataset(
                    "frequencies",
                    data=np.asarray(iso_data["frequencies_cm_inv"], dtype=np.float64),
                    compression="gzip",
                    compression_opts=4,
                    shuffle=True,
                )

    def generate_compound_script(
        self,
        stages: Sequence[Stage],
        seed_xyz: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """
        Implements Method Matrix Arrow 11 (§8B.4):
        Generates a multi-step ORCA compound script (New_Step ... Step_End)
        eliminating intermediate file plumbing when the entire chain fits one job window.
        """
        source = Path(seed_xyz).resolve()
        symbols, coordinates, _ = read_xyz(source)
        coordinates, _, _ = align_coordinates(coordinates, coordinates, masses=get_atomic_masses_for_symbols(symbols))
        self._planning_geometry = (symbols, coordinates)
        seed_p = "compound_input_" + hashlib.sha256(source.read_bytes()).hexdigest()[:16] + ".xyz"
        write_xyz(self.workdir / seed_p, symbols, coordinates, "COM/Eckart normalized compound input")
        warnings = validate_rule_d5_naming_hygiene(stages)
        if warnings:
            raise ValueError("; ".join(warnings))
        lines: List[str] = ["# Planned ORCA compound deck; physical execution has not been verified", ""]
        previous = set()

        for step_idx, st in enumerate(stages, start=1):
            lines.append(f"# Step {step_idx}: {st.name} ({st.level})")
            lines.append("New_Step")
            if any(name not in previous for name in (st.geom_from, st.mo_from, st.hess_from) if name is not None):
                raise ValueError("Compound stage references must point to an earlier stage.")
            geom_target = f"{st.geom_from}.xyz" if st.geom_from else seed_p
            deck_lines = self.build_stage_input(st, geom_target, allow_planned_checkpoints=True).splitlines()
            lines.extend("  " + line for line in deck_lines)
            lines.append("Step_End")
            lines.append("")
            previous.add(st.name)

        deck = "\n".join(lines)
        if output_path is not None:
            assert_writable_path(output_path)
            Path(output_path).write_text(deck, encoding="utf-8")
        return deck

    def inspect_campaign(self) -> Dict[str, Any]:
        """Reads and formats summary statistics from the HDF5 campaign store."""
        summary: Dict[str, Any] = {"stages": {}, "isotopologues": {}}
        if not self.h5_path.exists():
            return summary

        with h5py.File(self.h5_path, "r") as f:
            if "meta" in f:
                meta_dict: Dict[str, Any] = {}
                for k, v in f["meta"].attrs.items():
                    if hasattr(v, "item"):
                        meta_dict[k] = v.item()
                    elif isinstance(v, bytes):
                        meta_dict[k] = v.decode("utf-8")
                    else:
                        meta_dict[k] = v
                summary["meta"] = meta_dict

            if "chain" in f:
                for st_name in f["chain"]:
                    grp = f[f"chain/{st_name}"]
                    st_info: Dict[str, Any] = {
                        "level": grp.attrs.get("level", ""),
                        "wall_s": float(grp.attrs.get("wall_s", 0.0)),
                        "converged": bool(grp.attrs.get("converged", False)),
                        "energy_hartree": float(grp.attrs.get("energy_hartree", 0.0))
                        if "energy_hartree" in grp.attrs
                        else None,
                        "consumed": json.loads(grp.attrs.get("consumed", "[]")),
                        "produced": json.loads(grp.attrs.get("produced", "[]")),
                    }
                    if "rotational_constants_mhz" in grp.attrs:
                        st_info["rotational_constants_mhz"] = json.loads(grp.attrs["rotational_constants_mhz"])
                    if "inertial_defect_amu_a2" in grp.attrs:
                        st_info["inertial_defect_amu_a2"] = float(grp.attrs["inertial_defect_amu_a2"])
                    summary["stages"][st_name] = st_info

            if "isotopologues" in f:
                for iso_name in f["isotopologues"]:
                    grp = f[f"isotopologues/{iso_name}"]
                    summary["isotopologues"][iso_name] = {
                        "parent_stage": grp.attrs.get("parent_stage", ""),
                        "A_MHz": float(grp.attrs.get("A_MHz", 0.0)),
                        "B_MHz": float(grp.attrs.get("B_MHz", 0.0)),
                        "C_MHz": float(grp.attrs.get("C_MHz", 0.0)),
                        "inertial_defect_amu_A2": float(grp.attrs.get("inertial_defect_amu_A2", 0.0)),
                    }

        return summary


# ---------------------------------------------------------------------------
# Campaign Graphviz Lineage Export
# ---------------------------------------------------------------------------
def export_lineage_dot(h5_path: Union[str, Path], output_dot: Union[str, Path]) -> str:
    """Exports Graphviz DOT representation of execution arrows and state transfers."""
    p = Path(h5_path)
    if not p.exists():
        raise FileNotFoundError(f"Campaign HDF5 not found at {p.resolve()}")

    dot_lines = [
        "digraph StateChain {",
        "  rankdir=LR;",
        '  node [shape=box, style="filled,rounded", fontname="Helvetica", fillcolor="#eef2f7", color="#2c3e50"];',
        '  edge [fontname="Helvetica", fontsize=10];',
        "",
    ]

    with h5py.File(p, "r") as f:
        if "chain" in f:
            for st_name in f["chain"]:
                grp = f[f"chain/{st_name}"]
                level = grp.attrs.get("level", "")
                wall = float(grp.attrs.get("wall_s", 0.0))
                arrow_idx = grp.attrs.get("arrow_index", "")
                label = f"{st_name}\\n{level}\\n(wall: {wall:.1f}s)"
                dot_lines.append(f'  "{st_name}" [label="{label}"];')

                consumed = json.loads(grp.attrs.get("consumed", "[]"))
                for src in consumed:
                    src_stage = src.split(".")[0]
                    if src_stage != st_name and "chain" in f and src_stage in f["chain"]:
                        ext = src.split(".")[-1]
                        edge_label = f"Arrow {arrow_idx}: .{ext}" if arrow_idx else f".{ext}"
                        dot_lines.append(f'  "{src_stage}" -> "{st_name}" [label="{edge_label}"];')

    dot_lines.append("}\n")
    dot_str = "\n".join(dot_lines)
    Path(output_dot).write_text(dot_str, encoding="utf-8")
    return dot_str


# ---------------------------------------------------------------------------
# Command-Line Interface (CLI)
# ---------------------------------------------------------------------------
def main() -> int:
    """CLI entrypoint for chain.py."""
    parser = argparse.ArgumentParser(
        description="Canonical State-Chaining Driver & Execution-Arrow Recorder (Method Matrix §8B, §8C)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Command: pipeline (canonical full workflow)
    p_pipe = subparsers.add_parser("pipeline", help="Run the full 11-arrow canonical pipeline from a seed XYZ")
    p_pipe.add_argument("seed_xyz", help="Input seed XYZ coordinate file")
    p_pipe.add_argument("--workdir", default="chain", help="Working directory (default: chain)")
    p_pipe.add_argument("--h5", default="campaign.h5", help="HDF5 campaign database name (default: campaign.h5)")
    p_pipe.add_argument("--complex", default="complex", help="Complex identifier name")
    p_pipe.add_argument("--charge", type=int, default=0, help="Molecular charge (default: 0)")
    p_pipe.add_argument("--mult", type=int, default=1, help="Spin multiplicity (default: 1)")
    p_pipe.add_argument("--nproc", type=int, default=7, help="CPU cores for ORCA (default: 7)")
    p_pipe.add_argument("--maxcore", type=int, default=3400, help="Memory per core in MB (default: 3400)")
    p_pipe.add_argument("--skip-xtb", action="store_true", help="Skip GFN2-xTB pre-optimization")
    p_pipe.add_argument("--skip-freq", action="store_true", help="Skip analytic Hessian stage")
    p_pipe.add_argument("--skip-iso", action="store_true", help="Skip isotopologue re-analysis")
    p_pipe.add_argument("--with-ccsd", action="store_true", help="Include DLPNO-CCSD(T1) single point")
    p_pipe.add_argument("--dry-run", action="store_true", help="Generate input decks without calling binaries")

    # Command: inspect (inspect HDF5 campaign)
    p_insp = subparsers.add_parser("inspect", help="Inspect an existing HDF5 campaign store")
    p_insp.add_argument("h5_file", help="Path to campaign.h5 file")
    p_insp.add_argument("--dot", help="Optional output path to export Graphviz DOT lineage graph")

    # Command: compound (generate multi-step compound script)
    p_comp = subparsers.add_parser("compound", help="Generate a multi-step ORCA compound script (Arrow 11)")
    p_comp.add_argument("seed_xyz", help="Input seed XYZ coordinate file")
    p_comp.add_argument("--output", default="compound_chain.inp", help="Output input file path")
    p_comp.add_argument("--nproc", type=int, default=7, help="CPU cores (default: 7)")
    p_comp.add_argument("--maxcore", type=int, default=3400, help="Memory in MB (default: 3400)")

    # Legacy direct invocation support: python chain.py seed.xyz
    if len(sys.argv) == 2 and not sys.argv[1].startswith("-") and sys.argv[1] not in ("pipeline", "inspect", "compound"):
        seed_arg = sys.argv[1]
        c = Chain()
        c.run_canonical_pipeline(seed_arg)
        print(f"done -> {c.h5_path}")
        return 0

    args = parser.parse_args()

    if args.command == "pipeline":
        c = Chain(
            workdir=args.workdir,
            h5=args.h5,
            complex_name=args.complex,
            charge=args.charge,
            mult=args.mult,
            nproc=args.nproc,
            maxcore=args.maxcore,
        )
        c.run_canonical_pipeline(
            seed_xyz=args.seed_xyz,
            include_xtb=not args.skip_xtb,
            include_freq=not args.skip_freq,
            include_isotopologues=not args.skip_iso,
            include_ccsd=args.with_ccsd,
            dry_run=args.dry_run,
        )
        print(f"{'Decks generated' if args.dry_run else 'Pipeline verified'} -> {c.h5_path}")
        return 0

    elif args.command == "inspect":
        h5_p = Path(args.h5_file)
        if not h5_p.exists():
            print(f"Error: file not found at {h5_p}")
            return 1
        c = Chain(h5=h5_p)
        info = c.inspect_campaign()
        print("\n=== CoChem State-Chaining Campaign Summary ===")
        print(json.dumps(info, indent=2))
        if args.dot:
            export_lineage_dot(h5_p, args.dot)
            print(f"Exported lineage graph to {args.dot}")
        return 0

    elif args.command == "compound":
        c = Chain(nproc=args.nproc, maxcore=args.maxcore)
        s2 = Stage("s2", "r2SCAN-3c TightOpt TightSCF DefGrid3")
        s3 = Stage("s3", "wB97X-V def2-TZVPP def2/J RIJCOSX TightOpt TightSCF DefGrid3", geom_from="s2", mo_from="s2", hess_from="s2")
        s4 = Stage("s4", "wB97M-V def2-QZVPP def2/J RIJCOSX TightOpt TightSCF DefGrid3", geom_from="s3", mo_from="s3", hess_from="s3")
        s5 = Stage("s5", "wB97M-V def2-QZVPP def2/J RIJCOSX Freq TightSCF DefGrid3", geom_from="s4", mo_from="s4")
        c.generate_compound_script([s2, s3, s4, s5], args.seed_xyz, args.output)
        print(f"Generated compound script at {args.output}")
        return 0

    else:
        parser.print_help()
        return 0


__all__ = [
    "Chain",
    "ChainStage",
    "StateChainingAuditor",
    "ArrowState",
    "Stage",
    "ExecutionArrow",
    "StateRecord",
    "CanonicalArrow",
    "CounterpoiseType",
    "CANONICAL_ARROWS",
    "get_atomic_mass",
    "get_isotopic_mass",
    "MissingBinaryError",
    "ConvergenceFailureError",
    "CorruptOutputError",
]


if __name__ == "__main__":
    sys.exit(main())
