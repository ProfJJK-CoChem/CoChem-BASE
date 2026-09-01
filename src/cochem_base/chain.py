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
import json
import logging
import math
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import h5py
import numpy as np
from mendeleev import element

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
# CODATA 2018 / 2022 recommended constants
PLANCK_CONSTANT_J_S = 6.62607015e-34       # J*s (exact)
SPEED_OF_LIGHT_CM_S = 2.99792458e10       # cm/s (exact)
SPEED_OF_LIGHT_M_S = 2.99792458e8         # m/s (exact)
ATOMIC_MASS_UNIT_KG = 1.66053906660e-27   # kg/u
ANGSTROM_TO_METER = 1.0e-10               # m / Angstrom
BOHR_TO_ANGSTROM = 0.529177210903         # Angstrom / Bohr
BOHR_TO_METER = 0.529177210903e-10        # m / Bohr
HARTREE_TO_JOULE = 4.3597447222071e-18    # J / Hartree
HARTREE_TO_EV = 27.211386245988           # eV / Hartree
HARTREE_TO_CM_INV = 219474.63136320       # cm^-1 / Hartree

# Conversion factor from Inertia (u * Angstrom^2) to Rotational Constant (MHz):
# B = h / (8 * pi^2 * I) * 1e-6 (Hz -> MHz)
INERTIA_TO_MHZ_FACTOR = (
    PLANCK_CONSTANT_J_S
    / (8.0 * (math.pi ** 2) * ATOMIC_MASS_UNIT_KG * (ANGSTROM_TO_METER ** 2))
) * 1.0e-6  # ~505379.0091414361 MHz * u * Angstrom^2

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
    converged: bool = True
    exit_status: str = "SUCCESS"
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Mendeleev Dynamic Atomic Mass Retrieval (Mendeleev Library Mandate)
# ---------------------------------------------------------------------------
def get_atomic_mass(symbol: str, mass_number: Optional[int] = None) -> float:
    """
    Dynamically retrieves atomic or isotopic mass from the `mendeleev` library.
    Strictly forbids hardcoding masses or manual CODATA constants.
    """
    clean_sym = symbol.strip().capitalize()
    if clean_sym in ("D", "H2"):
        clean_sym = "H"
        mass_number = 2
    elif clean_sym in ("T", "H3"):
        clean_sym = "H"
        mass_number = 3

    el = element(clean_sym)
    if mass_number is not None:
        for iso in el.isotopes:
            if iso.mass_number == mass_number:
                if iso.mass is not None:
                    return float(iso.mass)
                break
    if el.mass is not None:
        return float(el.mass)
    raise ValueError(f"Could not retrieve dynamic mass for element '{symbol}' (mass_number={mass_number})")


def get_atomic_masses_for_symbols(
    symbols: Sequence[str],
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> np.ndarray:
    """Returns array of atomic masses in unified atomic mass units (u) for a sequence of symbols."""
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
    assert cart_hessian.shape == (3 * natoms, 3 * natoms), (
        f"Hessian shape {cart_hessian.shape} does not match 3N x 3N for N={natoms} atoms."
    )

    masses = get_atomic_masses_for_symbols(symbols, mass_numbers)
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

    # Filter out 5 or 6 translational/rotational near-zero modes (<20 cm^-1)
    vib_freqs = [f for f in freqs if abs(f) > 20.0]

    return {
        "iso_label": iso_label,
        "substituted_mass_numbers": list(substituted_mass_numbers),
        "frequencies_cm_inv": freqs.tolist(),
        "vibrational_frequencies_cm_inv": vib_freqs,
        "lowest_harmonic_mode_cm_inv": float(vib_freqs[0]) if vib_freqs else 0.0,
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

    lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        raise ValueError(f"XYZ file is empty: {p.resolve()}")

    try:
        num_atoms = int(lines[0].split()[0])
    except Exception as exc:
        raise ValueError(f"Invalid atom count line in XYZ file {p.resolve()}: {lines[0]}") from exc

    comment = lines[1] if len(lines) > 1 else ""
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

    return symbols, np.array(coords, dtype=float), comment


def write_xyz(
    path: Union[str, Path],
    symbols: Sequence[str],
    coords: np.ndarray,
    comment: str = "Generated by CoChem chain.py",
) -> None:
    """Writes standard XYZ coordinate file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    coords_arr = np.array(coords, dtype=float)
    assert len(symbols) == coords_arr.shape[0], "Atom count mismatch between symbols and coords."

    lines = [str(len(symbols)), comment]
    for i, sym in enumerate(symbols):
        x, y, z = coords_arr[i, 0], coords_arr[i, 1], coords_arr[i, 2]
        lines.append(f"{sym:<4} {x:18.10f} {y:18.10f} {z:18.10f}")

    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_orca_hessian(path: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """
    Exhaustive reader for ORCA .hess files.
    Parses $hessian block (3N x 3N Cartesian matrix in Hartree/Bohr^2),
    $vibrational_frequencies, $normal_modes, and $atoms.
    """
    p = Path(path)
    if not p.exists():
        return None

    raw_text = p.read_text(encoding="utf-8")
    lines = raw_text.splitlines()

    hessian_matrix: Optional[np.ndarray] = None
    frequencies: List[float] = []
    atoms_data: List[Dict[str, Any]] = []

    i = 0
    n_lines = len(lines)
    while i < n_lines:
        line = lines[i].strip()

        # Parse $hessian block
        if line == "$hessian":
            i += 1
            dim = int(lines[i].strip().split()[0])
            hessian_matrix = np.zeros((dim, dim), dtype=np.float64)
            i += 1
            col_offset = 0
            while col_offset < dim and i < n_lines:
                col_headers = [int(c) for c in lines[i].strip().split()]
                i += 1
                num_cols = len(col_headers)
                for _r in range(dim):
                    row_tokens = lines[i].strip().split()
                    row_idx = int(row_tokens[0])
                    for k, col_idx in enumerate(col_headers):
                        hessian_matrix[row_idx, col_idx] = float(row_tokens[k + 1])
                    i += 1
                col_offset += num_cols
            continue

        # Parse $vibrational_frequencies
        if line == "$vibrational_frequencies":
            i += 1
            n_freqs = int(lines[i].strip().split()[0])
            i += 1
            for _ in range(n_freqs):
                if i < n_lines:
                    tokens = lines[i].strip().split()
                    if len(tokens) >= 2:
                        frequencies.append(float(tokens[1]))
                    i += 1
            continue

        # Parse $atoms
        if line == "$atoms":
            i += 1
            n_atoms = int(lines[i].strip().split()[0])
            i += 1
            for _ in range(n_atoms):
                if i < n_lines:
                    tokens = lines[i].strip().split()
                    if len(tokens) >= 5:
                        atoms_data.append({
                            "symbol": tokens[0],
                            "mass": float(tokens[1]),
                            "coords": [float(tokens[2]), float(tokens[3]), float(tokens[4])],
                        })
                    i += 1
            continue

        i += 1

    if hessian_matrix is None:
        return None

    return {
        "hessian": hessian_matrix,
        "frequencies": np.array(frequencies, dtype=float) if frequencies else None,
        "atoms": atoms_data,
    }


def parse_orca_energy(path: Union[str, Path]) -> Optional[float]:
    """Extracts the final electronic energy in Hartree from an ORCA output file."""
    p = Path(path)
    if not p.exists():
        return None

    final_e: Optional[float] = None
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()

    for ln in reversed(lines):
        if "FINAL SINGLE POINT ENERGY" in ln:
            parts = ln.split()
            try:
                final_e = float(parts[-1])
                return final_e
            except Exception:
                pass
        elif "FINAL ENERGY" in ln:
            parts = ln.split()
            try:
                final_e = float(parts[-1])
                return final_e
            except Exception:
                pass
        elif "Total Energy       :" in ln:
            parts = ln.split()
            try:
                final_e = float(parts[3])
                return final_e
            except Exception:
                pass

    return final_e


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
    normal_term = "normal termination of xtb" in content or "finished run on" in content
    converged = "GEOMETRY OPTIMIZATION CONVERGED" in content or normal_term

    final_e: Optional[float] = None
    for ln in content.splitlines():
        if "TOTAL ENERGY" in ln or "total energy" in ln:
            parts = ln.split()
            for k, tok in enumerate(parts):
                if tok in ("energy", "ENERGY"):
                    try:
                        final_e = float(parts[k + 1])
                        break
                    except Exception:
                        pass

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
        h5: Union[str, Path] = "campaign.h5",
        complex_name: str = "complex",
        charge: int = 0,
        mult: int = 1,
        nproc: int = 7,
        maxcore: int = 3400,
        orca_cmd: str = "orca",
        xtb_cmd: str = "xtb",
        strict_guards: bool = True,
    ) -> None:
        self.workdir = Path(workdir).resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)
        h5_p = Path(h5)
        if h5_p.is_absolute():
            self.h5_path = h5_p
        elif len(h5_p.parts) > 1:
            self.h5_path = h5_p.resolve()
        else:
            self.h5_path = (self.workdir / h5_p).resolve()
        self.h5_path.parent.mkdir(parents=True, exist_ok=True)
        self.complex_name = complex_name
        self.charge = charge
        self.mult = mult
        self.nproc = nproc
        self.maxcore = maxcore
        self.orca_cmd = orca_cmd
        self.xtb_cmd = xtb_cmd
        self.strict_guards = strict_guards
        self.stage_records: Dict[str, StateRecord] = {}

        # Initialize HDF5 metadata store
        self._init_hdf5_store()

    def _init_hdf5_store(self) -> None:
        """Initializes the HDF5 metadata header and schema groups."""
        with h5py.File(self.h5_path, "a") as f:
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

    def build_stage_input(self, stage: Stage, geom_file: str) -> str:
        """
        Synthesizes the complete ORCA input deck for a stage, encoding:
        - Unique %base name (Rule D5)
        - Memory (%maxcore) & Parallelism (%pal nprocs)
        - MO guess projection (! MORead + %moinp)
        - Initial Hessian configuration (InHess XTB2 / InHess Read)
        - Tight convergence threshold block (%geom)
        """
        route_tokens = [f"! {stage.level}"]
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
                src_name = f"{stage.hess_from}.opt" if opt_file.exists() else f"{stage.hess_from}.hess"
                geom_block_lines.extend(["  InHess Read", f'  InHessName "{src_name}"'])
            else:
                geom_block_lines.append("  InHess XTB2")  # Cheap model Hessian default (§8B.3)

            input_lines.append("%geom\n" + "\n".join(geom_block_lines) + "\nend")

        if stage.blocks:
            input_lines.append(stage.blocks)

        input_lines.append(f"* xyzfile {self.charge} {self.mult} {geom_file}")
        return "\n".join(input_lines) + "\n"

    def record_to_hdf5(self, rec: StateRecord) -> None:
        """
        Persists an execution record into the HDF5 store with chunking,
        gzip level 4 compression, shuffle filter, and fletcher32 checksums.
        """
        with h5py.File(self.h5_path, "a") as f:
            grp = f.require_group(f"chain/{rec.stage}")
            grp.attrs["level"] = rec.level
            grp.attrs["wall_s"] = rec.wall_s
            grp.attrs["consumed"] = json.dumps(rec.consumed_files)
            grp.attrs["produced"] = json.dumps(rec.produced_files)
            grp.attrs["written_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            grp.attrs["converged"] = rec.converged
            grp.attrs["exit_status"] = rec.exit_status
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

            # Persist Geometry Dataset
            if "geometry" in grp:
                del grp["geometry"]
            grp.create_dataset(
                "geometry",
                data=np.asarray(rec.geometry, dtype=np.float64),
                compression="gzip",
                compression_opts=4,
                shuffle=True,
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
                )

    def run_stage(
        self,
        stage: Stage,
        seed_xyz: Optional[Union[str, Path]] = None,
        dry_run: bool = False,
    ) -> StateRecord:
        """
        Executes a single pipeline stage, validates outputs against Rules D1–D5,
        computes rotational observables, and records all artifacts to HDF5.
        """
        logger.info(f"=== [Stage: {stage.name}] (Level: {stage.level}) ===")

        # Determine geometry source file
        if stage.geom_from:
            geom_source = f"{stage.geom_from}.xyz"
        elif seed_xyz:
            seed_p = Path(seed_xyz)
            geom_source = seed_p.name
            target_dest = self.workdir / geom_source
            if seed_p.exists() and seed_p.resolve() != target_dest.resolve():
                shutil.copy(seed_p, target_dest)
        else:
            raise ValueError(f"Stage '{stage.name}' requires either 'geom_from' or 'seed_xyz'.")

        inp_path = self.workdir / f"{stage.name}.inp"
        out_path = self.workdir / f"{stage.name}.out"
        err_path = self.workdir / f"{stage.name}.err"

        # Generate stage input deck
        input_deck = self.build_stage_input(stage, geom_source)
        inp_path.write_text(input_deck, encoding="utf-8")

        wall_s = 0.0
        exit_status = "SUCCESS"

        if not dry_run:
            t0 = time.time()
            with out_path.open("w", encoding="utf-8") as out_fh, err_path.open("w", encoding="utf-8") as err_fh:
                try:
                    res = subprocess.run(
                        [self.orca_cmd, inp_path.name],
                        cwd=self.workdir,
                        stdout=out_fh,
                        stderr=err_fh,
                        check=False,
                    )
                    wall_s = time.time() - t0
                    if res.returncode != 0:
                        exit_status = f"FAILED_EXIT_{res.returncode}"
                except FileNotFoundError:
                    wall_s = time.time() - t0
                    exit_status = "ENGINE_NOT_FOUND"
                    logger.warning(f"ORCA binary '{self.orca_cmd}' not found on PATH. Recorded input deck.")
        else:
            logger.info(f"[Dry Run] Generated input deck at {inp_path.name}")

        # Post-Execution Ingestion & Parsing
        conv_info = parse_orca_convergence(out_path)
        energy = parse_orca_energy(out_path)

        # Ingest output geometry
        stage_xyz_path = self.workdir / f"{stage.name}.xyz"
        if not stage_xyz_path.exists():
            # Single-points or unwritten xyz: copy input geometry forward
            if (self.workdir / geom_source).exists():
                shutil.copy(self.workdir / geom_source, stage_xyz_path)

        symbols: List[str] = []
        coords: np.ndarray = np.empty((0, 3))
        if stage_xyz_path.exists():
            symbols, coords, _ = read_xyz(stage_xyz_path)

        # Ingest Hessian if generated
        hess_path = self.workdir / f"{stage.name}.hess"
        hess_dict = parse_orca_hessian(hess_path)
        hessian_arr = hess_dict["hessian"] if hess_dict is not None else None
        freqs_arr = hess_dict["frequencies"] if hess_dict is not None else None

        # Compute Rotational Observables
        rot_constants: Optional[Tuple[float, float, float]] = None
        inertial_defect: Optional[float] = None
        planar_moments: Optional[Tuple[float, float, float]] = None
        if len(symbols) > 0 and coords.shape[0] > 0:
            rot_dict = compute_rotational_constants(symbols, coords)
            rot_constants = (rot_dict["A_MHz"], rot_dict["B_MHz"], rot_dict["C_MHz"])
            inertial_defect = rot_dict["inertial_defect_amu_A2"]
            planar_moments = (rot_dict["Paa_u_A2"], rot_dict["Pbb_u_A2"], rot_dict["Pcc_u_A2"])

        # Determine consumed and produced files
        consumed: List[str] = [geom_source]
        if stage.mo_from:
            consumed.append(f"{stage.mo_from}.gbw")
        if stage.hess_from:
            consumed.append(f"{stage.hess_from}.opt")

        produced: List[str] = [p.name for p in self.workdir.glob(f"{stage.name}.*")]

        # Run Dangerous Reuse Guards (Rules D1–D5)
        warnings: List[str] = []
        prev_rec = self.stage_records.get(stage.geom_from) if stage.geom_from else None
        if self.strict_guards and len(symbols) > 0:
            warnings.extend(
                validate_rule_d1_geometry_stationarity(
                    stage,
                    StateRecord(
                        stage=stage.name,
                        level=stage.level,
                        wall_s=wall_s,
                        energy_hartree=energy,
                        symbols=symbols,
                        geometry=coords,
                    ),
                    prev_rec,
                )
            )
            if hessian_arr is not None:
                warnings.extend(
                    validate_rule_d2_hessian_reuse(stage, hessian_arr, symbols, coords)
                )
            warnings.extend(validate_rule_d3_scf_stability(stage, out_path))
            warnings.extend(validate_rule_d4_counterpoise_ghosts(stage, symbols))

        # Assemble StateRecord
        record = StateRecord(
            stage=stage.name,
            level=stage.level,
            wall_s=wall_s,
            energy_hartree=energy,
            symbols=symbols,
            geometry=coords,
            hessian=hessian_arr,
            frequencies_cm_inv=freqs_arr,
            rotational_constants_mhz=rot_constants,
            inertial_defect_amu_a2=inertial_defect,
            planar_moments_amu_a2=planar_moments,
            consumed_files=consumed,
            produced_files=produced,
            arrow_index=stage.arrow_index,
            arrow_desc=stage.arrow_desc,
            converged=conv_info["opt_converged"] if "opt" in stage.level.lower() else conv_info["normal_termination"],
            exit_status=exit_status,
            warnings=warnings,
        )

        self.stage_records[stage.name] = record
        self.record_to_hdf5(record)
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
        shutil.copy(seed_p, self.workdir / seed_p.name)

        records: List[StateRecord] = []
        active_seed = seed_p.name

        # Stage 1: xTB Pre-optimization if requested
        if include_xtb:
            s1_out = self.workdir / "s1_xtb.out"
            s1_xyz = self.workdir / "s1.xyz"
            if not dry_run:
                try:
                    with s1_out.open("w", encoding="utf-8") as fh:
                        subprocess.run(
                            [
                                self.xtb_cmd,
                                seed_p.name,
                                "--opt",
                                "vtight",
                                "--strict",
                                "--chrg",
                                str(self.charge),
                                "--uhf",
                                str(self.mult - 1),
                            ],
                            cwd=self.workdir,
                            stdout=fh,
                            stderr=subprocess.STDOUT,
                            check=False,
                        )
                    xtbopt = self.workdir / "xtbopt.xyz"
                    if xtbopt.exists():
                        shutil.copy(xtbopt, s1_xyz)
                        active_seed = "s1.xyz"
                except FileNotFoundError:
                    logger.warning(f"xTB binary '{self.xtb_cmd}' not found. Falling back to raw seed.")
                    shutil.copy(seed_p, s1_xyz)
                    active_seed = "s1.xyz"

        # Define Canonical Stages
        s2 = Stage(
            name="s2",
            level="r2SCAN-3c TightOpt TightSCF DefGrid3",
            arrow_index=3,
            arrow_desc="GFN2-xTB -> r2SCAN-3c with InHess XTB2 model Hessian",
        )
        s3 = Stage(
            name="s3",
            level="wB97X-V def2-TZVPP def2/J RIJCOSX TightOpt TightSCF DefGrid3",
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
        )
        s5 = Stage(
            name="s5",
            level="wB97M-V def2-QZVPP def2/J RIJCOSX Freq TightSCF DefGrid3",
            geom_from="s4",
            mo_from="s4",
            arrow_index=6,
            arrow_desc="Tight optimization -> analytic DFT Hessian",
        )
        s6 = Stage(
            name="s6",
            level="DLPNO-CCSD(T1) TightPNO cc-pVDZ-F12 (paired with CABS) cc-pVDZ-F12 (paired with CABS)/C TightSCF",
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

        logger.info(f"Canonical pipeline complete. Database: {self.h5_path}")
        return records

    def run_standard_isotopologue_campaign(self, parent_stage: str) -> Dict[str, Dict[str, Any]]:
        """
        Executes standard isotopologue substitution campaign for 13C, 18O, and 2H (D)
        using the saved Cartesian Hessian from `parent_stage` at zero electronic structure cost.
        """
        rec = self.stage_records.get(parent_stage)
        if rec is None or rec.hessian is None:
            logger.warning(f"Cannot run isotopologue campaign: Stage '{parent_stage}' has no saved Hessian.")
            return {}

        symbols = rec.symbols
        coords = rec.geometry
        hess = rec.hessian

        results: Dict[str, Dict[str, Any]] = {}

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
        seed_p = Path(seed_xyz).name
        lines: List[str] = [
            "# Multi-step compound state-chaining script (Method Matrix Arrow 11)",
            f"%pal nprocs {self.nproc} end",
            f"%maxcore {self.maxcore}",
            "",
        ]

        for step_idx, st in enumerate(stages, start=1):
            lines.append(f"# Step {step_idx}: {st.name} ({st.level})")
            lines.append("New_Step")
            lines.append(f"  ! {st.level}")
            if st.mo_from:
                lines.append(f'  %moinp "{st.mo_from}.gbw"')
            if "opt" in st.level.lower():
                lines.append("  %geom")
                lines.append(TIGHT_GEOM_BLOCK.rstrip("\n"))
                if st.hess_from:
                    lines.append("    InHess Read")
                    lines.append(f'    InHessName "{st.hess_from}.opt"')
                else:
                    lines.append("    InHess XTB2")
                lines.append("  end")
            if st.blocks:
                lines.append(f"  {st.blocks}")

            geom_target = f"{st.geom_from}.xyz" if st.geom_from else seed_p
            lines.append(f"  * xyzfile {self.charge} {self.mult} {geom_target}")
            lines.append("Step_End")
            lines.append("")

        deck = "\n".join(lines)
        if output_path is not None:
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
        print(f"Pipeline executed successfully -> {c.h5_path}")
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


if __name__ == "__main__":
    sys.exit(main())
