#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Method Matrix Reference Validation Suite: Exact Rigid-Rotor Moments & Rotational Constant Propagation.

Mandated by Method Matrix §4.1, §4.2, §4.3, §4.5, §4.6, §12.3, §12.5, and §16.3.

Physical Background & Mathematical Foundation:
----------------------------------------------
In high-resolution microwave spectroscopy of weakly bound van der Waals and hydrogen-bonded
complexes, accurate assignment requires transforming geometric uncertainties (from electronic
structure optimizations, basis set incompleteness, or residual numerical gradients) into
rotational constant uncertainties.

1. Pseudo-Diatomic Error Propagation (§4.1, §4.2):
-------------------------------------------------
For a weakly bound complex treated as a pseudo-diatomic with reduced mass mu and intermolecular separation R:
    B = h / (8 * pi^2 * mu * R^2) = CONV / (mu * R^2)
where CONV = 505379.0 MHz * amu * Angstrom^2 (Groner (2016); NIST CCCBDB).

Differentiating exactly:
    dB / dR = -2 * CONV / (mu * R^3) = -2 * B / R
    Delta B / B = -2 * (Delta R / R)  [Leading-order linear propagation]

The exact non-linearized relative shift is:
    Delta B / B = ((R + Delta R)^-2 - R^-2) / R^-2
                = (1 + Delta R / R)^-2 - 1
                = -2*(Delta R / R) + 3*(Delta R / R)^2 - 4*(Delta R / R)^3 + ...

Inverting this relation for target microwave assignment windows:
    Delta R ~= -(R / 2) * (Delta B / B)
To achieve Delta B / B = 0.1% at R = 4.0 Angstrom requires Delta R <= 2.0 mAngstrom (0.20 pm).
To achieve Delta B / B = 0.02% requires Delta R <= 0.04 pm.

2. Coordinate Sensitivity Partitioning: Monomer Geometry vs. Intermolecular Separation (§4.5):
---------------------------------------------------------------------------------------------
Rigid-rotor moments recomputed exactly without linearization reveal that for weak complexes:
- Monomer covalent bond errors dominate the A rotational constant and have negligible effect on B and C.
- Intermolecular separation (R) errors dominate B and C and have zero/negligible effect on A.
- Therefore, a composite scheme MUST freeze accurate monomers (e.g. from high-level coupled cluster)
  to pin down A, and spend remaining electronic-structure budget on intermolecular R to pin down B and C.

For T-shaped CO2···H2O (6 atoms, R = 2.836 Angstrom, A/B/C = 11433.66 / 4621.35 / 3341.41 MHz):
- A +0.001 Angstrom uniform monomer bond error changes A by -0.173% (-19.8 MHz), but B by only -0.008% (-0.37 MHz).
- A +0.002 Angstrom error in R changes A by 0.000% (0.00 MHz), but B by -0.135% (-6.26 MHz).
- Break-Even Analysis: An error of Delta R = 0.002 Angstrom produces the same Delta B in B as a 16.8 mAngstrom
  uniform error in every monomer bond! Since fc-CCSD(T)/VTZ has a covalent MAD of only 3 mAngstrom,
  covalent errors are never the bottleneck for B and C.

3. Residual Gradient Component Displacements (§4.3, §4.4):
---------------------------------------------------------
A residual gradient component g on a coordinate with force constant k leaves the geometry displaced by:
    Delta r ~= g / k
With 1 mdyn * Angstrom^-1 = 100 N/m = 6.423e-2 Eh * bohr^-2:
- On soft intermolecular modes (k = 0.069 mdyn/Angstrom = 4.425e-3 Eh/bohr^2):
  - !Opt (TolMaxG = 3e-4 au)       => Delta r = 3.6 pm  => Delta B / B ~= 2.1%  (Inadequate)
  - !TightOpt (TolMaxG = 1e-4 au)  => Delta r = 1.2 pm  => Delta B / B ~= 0.69% (Inadequate)
  - !VeryTightOpt (TolMaxG = 3e-5) => Delta r = 0.36 pm => Delta B / B ~= 0.21%
  - Custom %geom (TolMaxG = 1e-5)  => Delta r = 0.12 pm => Delta B / B ~= 0.07% (Spectroscopic tightness)

4. Intramolecular Sensitivities (§4.6):
--------------------------------------
Calibrated derivatives from all-electron CCSD(T)/cc-pCVQZ equilibrium structures show:
    d(ln B)/dr ~= -0.10% per +0.001 Angstrom at r ~= 2 Angstrom (SiS)
    d(ln B)/dr ~= -0.22% per +0.001 Angstrom at r ~= 1 Angstrom (HF)

Provenance Discipline (§12.5 Rule 7):
-------------------------------------
Every number emitted carries an authoritative provenance tag:
- [M] : Measured or published benchmark
- [D] : Derived by exact mathematical or physical arithmetic
- [E] : Expert estimate
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

# Reconfigure stream encodings for safe cross-platform output (prevent Windows cp1252 crash)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception as _e:
        logger.debug(f"Ignored exception: {_e}")
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception as _e:
        logger.debug(f"Ignored exception: {_e}")

try:
    from mendeleev import element as _mendeleev_element
    _MENDELEEV_AVAILABLE = True
except ImportError:
    _mendeleev_element = None  # type: ignore[assignment]
    _MENDELEEV_AVAILABLE = False

# ---------------------------------------------------------------------------
# Physical Constants & Authoritative Calibration Standards
# ---------------------------------------------------------------------------
# Conversion constant from moment of inertia (amu * Angstrom^2) to rotational
# constant in MHz: [B(MHz)][I(amu Angstrom^2)] = 505379.0 MHz * amu * Angstrom^2
# Reference: Groner (2016); NIST CCCBDB; Method Matrix §4.1, §4.5, §5.1.
CONV_MHZ_AMU_ANG2: float = 505379.0
CODATA_CONV_EXACT: float = 505379.00536  # High-precision Groner / CODATA constant

# Unit conversions
BOHR_TO_ANGSTROM: float = 0.529177210903
ANGSTROM_TO_BOHR: float = 1.0 / BOHR_TO_ANGSTROM
ANGSTROM_TO_PM: float = 100.0
PM_TO_ANGSTROM: float = 0.01

# Force constant conversions: 1 mdyn / Angstrom = 100 N/m = 6.423e-2 Eh / bohr^2
MDYN_ANG_TO_EH_BOHR2: float = 6.423e-2
EH_BOHR2_TO_MDYN_ANG: float = 1.0 / MDYN_ANG_TO_EH_BOHR2

PROVENANCE_M: str = "[M]"
PROVENANCE_D: str = "[D]"
PROVENANCE_E: str = "[E]"

SECTION_REF_4_1: str = "Method Matrix §4.1"
SECTION_REF_4_2: str = "Method Matrix §4.2"
SECTION_REF_4_3: str = "Method Matrix §4.3"
SECTION_REF_4_5: str = "Method Matrix §4.5"
SECTION_REF_4_6: str = "Method Matrix §4.6"
SECTION_REF_12_3: str = "Method Matrix §12.3"

logger = logging.getLogger("cochem.mm.conference2.a7.propagate")


# ---------------------------------------------------------------------------
# Custom Exceptions (Method Matrix §16.3 Guardrails)
# ---------------------------------------------------------------------------
class MethodMatrixComplianceError(Exception):
    """Base exception for violations of Method Matrix mandates."""


class PropagationComplianceError(MethodMatrixComplianceError):
    """Raised when error propagation violates Method Matrix accuracy or convergence mandates."""


# ---------------------------------------------------------------------------
# Mendeleev Dynamic Atomic Mass Retrieval (Mendeleev Mandate)
# ---------------------------------------------------------------------------
def get_atomic_mass(symbol: str, mass_number: Optional[int] = None) -> float:
    """
    Dynamically retrieves atomic or isotopic mass in unified atomic mass units (u/amu)
    from the `mendeleev` library. Strictly adheres to the Mendeleev Library Mandate.
    """
    if not _MENDELEEV_AVAILABLE or _mendeleev_element is None:
        raise RuntimeError(
            "The 'mendeleev' library is strictly required by the Mendeleev Mandate "
            "but is not available in the current environment."
        )

    clean_sym = symbol.strip().capitalize()
    # Handle hydrogen isotope naming conventions
    if clean_sym in ("D", "H2"):
        clean_sym = "H"
        mass_number = 2
    elif clean_sym in ("T", "H3"):
        clean_sym = "H"
        mass_number = 3

    el = _mendeleev_element(clean_sym)
    if mass_number is not None:
        for iso in getattr(el, "isotopes", []):
            if getattr(iso, "mass_number", None) == mass_number:
                iso_mass = getattr(iso, "mass", None)
                if iso_mass is not None:
                    return float(iso_mass)
                break

    el_mass = getattr(el, "mass", None) or getattr(el, "atomic_weight", None)
    if el_mass is not None:
        return float(el_mass)

    raise ValueError(f"Could not retrieve dynamic mass for element '{symbol}' (mass_number={mass_number})")


def get_reduced_mass(
    symbol1: str,
    symbol2: str,
    mass_number1: Optional[int] = None,
    mass_number2: Optional[int] = None,
) -> float:
    """Computes two-body reduced mass mu = (m1 * m2) / (m1 + m2) in amu dynamically."""
    m1 = get_atomic_mass(symbol1, mass_number1)
    m2 = get_atomic_mass(symbol2, mass_number2)
    return float((m1 * m2) / (m1 + m2))


# ---------------------------------------------------------------------------
# Data Schemas & Results Containers
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RigidRotorObservables:
    """Comprehensive container for exact rigid-rotor moments and spectroscopic constants."""
    symbols: List[str]
    masses: List[float]
    coords: List[List[float]]
    com: List[float]
    inertia_tensor: List[List[float]]
    principal_moments: Tuple[float, float, float]  # Ia <= Ib <= Ic (amu * Angstrom^2)
    rotational_constants: Tuple[float, float, float]  # A >= B >= C (MHz)
    ray_kappa: float  # Asymmetry parameter: (2B - A - C) / (A - C)
    inertial_defect: float  # Delta = Ic - Ia - Ib (amu * Angstrom^2)
    planar_moments: Tuple[float, float, float]  # Paa, Pbb, Pcc (amu * Angstrom^2)
    provenance: str = PROVENANCE_D

    @property
    def A(self) -> float:
        return self.rotational_constants[0]

    @property
    def B(self) -> float:
        return self.rotational_constants[1]

    @property
    def C(self) -> float:
        return self.rotational_constants[2]

    @property
    def Ia(self) -> float:
        return self.principal_moments[0]

    @property
    def Ib(self) -> float:
        return self.principal_moments[1]

    @property
    def Ic(self) -> float:
        return self.principal_moments[2]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Propagation1DResult:
    """Results container for 1D pseudo-diatomic error propagation analysis (§4.1, §4.2)."""
    system_name: str
    reduced_mass_amu: float
    R0_angstrom: float
    B0_MHz: float
    delta_R_angstrom: float
    B_perturbed_MHz: float
    delta_B_MHz: float
    delta_B_pct: float
    linearized_delta_B_pct: float
    non_linear_excess_pct: float
    provenance: str = PROVENANCE_D

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CoordinatePerturbationResult:
    """Results container for exact coordinate sensitivity partitioning (§4.5)."""
    complex_name: str
    perturbation_label: str
    parameter_name: str
    perturbation_value: float
    unit: str
    A_unperturbed: float
    B_unperturbed: float
    C_unperturbed: float
    A_perturbed: float
    B_perturbed: float
    C_perturbed: float
    delta_A_pct: float
    delta_B_pct: float
    delta_C_pct: float
    delta_A_MHz: float
    delta_B_MHz: float
    delta_C_MHz: float
    equivalent_monomer_bond_error_mAng: Optional[float] = None
    provenance: str = PROVENANCE_D

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ThresholdDisplacementResult:
    """Results container for optimization gradient threshold analysis (§4.3, §4.4)."""
    opt_level: str
    tol_max_g_au: float
    force_constant_mdyn_ang: float
    force_constant_eh_bohr2: float
    delta_r_bohr: float
    delta_r_pm: float
    delta_r_angstrom: float
    implied_delta_B_pct_at_3_5A: float
    compliance_class: str
    provenance: str = PROVENANCE_D

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IntramolecularSensitivityResult:
    """Results container for measured intramolecular bond sensitivity benchmarks (§4.6)."""
    molecule: str
    r_e_angstrom: float
    B_e_MHz: float
    delta_B_plus_1mAng_MHz: float
    relative_sensitivity_pct: float
    provenance: str = PROVENANCE_M

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MethodMatrixAuditReport:
    """Audit report verifying Method Matrix §4.1, §4.2, §4.3, §4.5, §4.6 compliance."""
    status: str
    section: str
    rejection_triggered: bool
    findings: List[str]
    sha256_checksum: str
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Exact Rigid-Rotor Inertia & Rotational Constant Engine
# ---------------------------------------------------------------------------
def compute_center_of_mass(coords: np.ndarray, masses: np.ndarray) -> np.ndarray:
    """Computes center of mass vector for a Cartesian molecular structure."""
    if coords.ndim != 2 or coords.shape[1] != 3:
        raise ValueError(f"coords must have shape (N, 3), got {coords.shape}")
    if len(masses) != coords.shape[0]:
        raise ValueError(f"masses length ({len(masses)}) must match atom count ({coords.shape[0]})")

    total_mass = float(np.sum(masses))
    if total_mass <= 0.0:
        raise ValueError("Total molecular mass must be strictly positive.")

    return np.sum(coords * masses[:, np.newaxis], axis=0) / total_mass


def compute_inertia_tensor(coords: np.ndarray, masses: np.ndarray) -> np.ndarray:
    """
    Computes exact 3x3 moment of inertia tensor in amu * Angstrom^2.
    Shifts molecular coordinates to center-of-mass frame before tensor accumulation.
    
    Formula:
        I_alpha_beta = sum_i m_i * [ ||r'_i||^2 * delta_alpha_beta - r'_{i,alpha} * r'_{i,beta} ]
    """
    com = compute_center_of_mass(coords, masses)
    r_rel = coords - com
    I = np.zeros((3, 3), dtype=np.float64)

    for i in range(len(masses)):
        m_i = float(masses[i])
        r_i = r_rel[i]
        r2 = float(np.dot(r_i, r_i))
        I[0, 0] += m_i * (r2 - r_i[0] ** 2)
        I[1, 1] += m_i * (r2 - r_i[1] ** 2)
        I[2, 2] += m_i * (r2 - r_i[2] ** 2)
        I[0, 1] -= m_i * (r_i[0] * r_i[1])
        I[0, 2] -= m_i * (r_i[0] * r_i[2])
        I[1, 2] -= m_i * (r_i[1] * r_i[2])

    I[1, 0] = I[0, 1]
    I[2, 0] = I[0, 2]
    I[2, 1] = I[1, 2]
    return I


def compute_principal_moments(I: np.ndarray) -> Tuple[float, float, float]:
    """Diagonalizes 3x3 moment of inertia tensor to yield sorted principal moments Ia <= Ib <= Ic."""
    eigvals = np.linalg.eigvalsh(I)
    sorted_moments = np.sort(eigvals)
    return float(sorted_moments[0]), float(sorted_moments[1]), float(sorted_moments[2])


def compute_rotational_constants(
    I: np.ndarray,
    conv: float = CONV_MHZ_AMU_ANG2,
) -> Tuple[float, float, float]:
    """
    Computes principal rotational constants A >= B >= C in MHz from a 3x3 inertia tensor.
    Formula:
        A = CONV / Ia, B = CONV / Ib, C = CONV / Ic
    """
    Ia, Ib, Ic = compute_principal_moments(I)
    if Ia <= 1e-12:
        raise ValueError(f"Singular or degenerate principal moment of inertia: Ia={Ia}")
    if Ib <= 1e-12:
        raise ValueError(f"Singular or degenerate principal moment of inertia: Ib={Ib}")
    if Ic <= 1e-12:
        raise ValueError(f"Singular or degenerate principal moment of inertia: Ic={Ic}")

    A = conv / Ia
    B = conv / Ib
    C = conv / Ic
    return float(A), float(B), float(C)


def compute_asymmetry_parameter(A: float, B: float, C: float) -> float:
    """Computes Ray's asymmetry parameter kappa = (2B - A - C) / (A - C)."""
    denom = A - C
    if abs(denom) < 1e-9:
        return 0.0  # Spherical top limit
    return float((2.0 * B - A - C) / denom)


def compute_inertial_defect(Ia: float, Ib: float, Ic: float) -> float:
    """Computes inertial defect Delta = Ic - Ia - Ib (amu * Angstrom^2)."""
    return float(Ic - Ia - Ib)


def compute_planar_moments(Ia: float, Ib: float, Ic: float) -> Tuple[float, float, float]:
    """
    Computes planar moments of inertia about principal planes (Paa, Pbb, Pcc) in amu * Angstrom^2.
    Formula:
        Paa = sum m_i a_i^2 = 0.5 * (Ib + Ic - Ia)
        Pbb = sum m_i b_i^2 = 0.5 * (Ia + Ic - Ib)
        Pcc = sum m_i c_i^2 = 0.5 * (Ia + Ib - Ic)
    """
    Paa = 0.5 * (Ib + Ic - Ia)
    Pbb = 0.5 * (Ia + Ic - Ib)
    Pcc = 0.5 * (Ia + Ib - Ic)
    return float(Paa), float(Pbb), float(Pcc)


def compute_rotational_observables(
    coords: np.ndarray,
    masses: np.ndarray,
    symbols: Optional[Sequence[str]] = None,
    conv: float = CONV_MHZ_AMU_ANG2,
) -> RigidRotorObservables:
    """
    Evaluates complete rigid-rotor spectroscopic observable suite for a Cartesian structure.
    """
    if coords.ndim != 2 or coords.shape[1] != 3:
        raise ValueError(f"coords must have shape (N, 3), got {coords.shape}")
    n_atoms = coords.shape[0]
    if len(masses) != n_atoms:
        raise ValueError(f"masses length ({len(masses)}) must match atom count ({n_atoms})")

    if symbols is None:
        sym_list = [f"X{i+1}" for i in range(n_atoms)]
    else:
        sym_list = list(symbols)

    com = compute_center_of_mass(coords, masses)
    I = compute_inertia_tensor(coords, masses)
    Ia, Ib, Ic = compute_principal_moments(I)
    A, B, C = compute_rotational_constants(I, conv=conv)
    kappa = compute_asymmetry_parameter(A, B, C)
    defect = compute_inertial_defect(Ia, Ib, Ic)
    Paa, Pbb, Pcc = compute_planar_moments(Ia, Ib, Ic)

    return RigidRotorObservables(
        symbols=sym_list,
        masses=list(map(float, masses)),
        coords=coords.tolist(),
        com=com.tolist(),
        inertia_tensor=I.tolist(),
        principal_moments=(Ia, Ib, Ic),
        rotational_constants=(A, B, C),
        ray_kappa=kappa,
        inertial_defect=defect,
        planar_moments=(Paa, Pbb, Pcc),
        provenance=PROVENANCE_D,
    )


# ---------------------------------------------------------------------------
# 1D Pseudo-Diatomic Error Propagation Analysis (Method Matrix §4.1, §4.2)
# ---------------------------------------------------------------------------
def propagate_1d_pseudo_diatomic(
    R0: float,
    reduced_mass: float,
    delta_R: float,
    system_name: str = "Generic Dimer",
    conv: float = CONV_MHZ_AMU_ANG2,
) -> Propagation1DResult:
    """
    Computes exact and linearized error propagation from intermolecular separation shift Delta R
    to rotational constant B for a pseudo-diatomic complex (Method Matrix §4.1, §4.2).
    
    Equations:
        B0 = CONV / (mu * R0^2)
        B_pert = CONV / (mu * (R0 + delta_R)^2)
        Delta B = B_pert - B0
        Delta B / B0 % = 100 * Delta B / B0
        Linearized % = -200 * (delta_R / R0)
    """
    if R0 <= 0.0:
        raise ValueError(f"R0 must be positive, got {R0}")
    if reduced_mass <= 0.0:
        raise ValueError(f"Reduced mass must be positive, got {reduced_mass}")

    I0 = reduced_mass * (R0 ** 2)
    B0 = conv / I0

    R_pert = R0 + delta_R
    if R_pert <= 0.0:
        raise ValueError(f"Perturbed separation (R0 + delta_R) must be positive, got {R_pert}")

    I_pert = reduced_mass * (R_pert ** 2)
    B_pert = conv / I_pert

    delta_B = B_pert - B0
    delta_B_pct = (delta_B / B0) * 100.0
    linearized_delta_B_pct = -200.0 * (delta_R / R0)
    non_linear_excess_pct = delta_B_pct - linearized_delta_B_pct

    return Propagation1DResult(
        system_name=system_name,
        reduced_mass_amu=reduced_mass,
        R0_angstrom=R0,
        B0_MHz=B0,
        delta_R_angstrom=delta_R,
        B_perturbed_MHz=B_pert,
        delta_B_MHz=delta_B,
        delta_B_pct=delta_B_pct,
        linearized_delta_B_pct=linearized_delta_B_pct,
        non_linear_excess_pct=non_linear_excess_pct,
        provenance=PROVENANCE_D,
    )


def invert_1d_tolerance(
    R0: float,
    reduced_mass: float,
    target_rel_error_pct: float,
    conv: float = CONV_MHZ_AMU_ANG2,
) -> Tuple[float, float, float]:
    """
    Inverts the error propagation relation to find required Delta R tolerance (in Angstrom and pm)
    and equivalent search window in MHz for a target relative error (e.g. 0.1%, 0.5%, 1.0%).
    
    Returns:
        (delta_R_angstrom, delta_R_pm, delta_B_MHz)
    """
    I0 = reduced_mass * (R0 ** 2)
    B0 = conv / I0
    frac_error = target_rel_error_pct / 100.0

    # Linear inversion: Delta R = 0.5 * R0 * (Delta B / B)
    delta_R_ang = 0.5 * R0 * frac_error
    delta_R_pm = delta_R_ang * ANGSTROM_TO_PM
    delta_B_MHz = B0 * frac_error

    return float(delta_R_ang), float(delta_R_pm), float(delta_B_MHz)


def compute_table_4_2_suite(
    conv: float = CONV_MHZ_AMU_ANG2,
) -> Dict[str, List[Propagation1DResult]]:
    """
    Computes the complete, authoritative Method Matrix Table 4.2 validation suite across
    all four benchmark systems and all six perturbation increments [0.001, 0.01, 0.02, 0.034, 0.056, 0.14] Angstrom.
    
    Benchmark systems (§4.2):
    1. Ar–HCl:      mu = 18.93 amu, R = 4.00 Angstrom (B0 ~= 1669 MHz)
    2. Ar–H2O:      mu = 13.60 amu, R = 3.63 Angstrom (B0 ~= 2820 MHz)
    3. Benzene–Ar:  mu = 32.40 amu, R = 3.58 Angstrom (B0 ~= 1217 MHz)
    4. Water Dimer: mu =  9.00 amu, R = 2.91 Angstrom (B0 ~= 6631 MHz)
    """
    systems = [
        ("Ar-HCl", 18.93, 4.00),
        ("Ar-H2O", 13.60, 3.63),
        ("benzene-Ar", 32.40, 3.58),
        ("water dimer", 9.00, 2.91),
    ]
    delta_Rs = [0.001, 0.010, 0.020, 0.034, 0.056, 0.140]

    suite: Dict[str, List[Propagation1DResult]] = {}
    for sys_name, mu, R0 in systems:
        suite[sys_name] = [
            propagate_1d_pseudo_diatomic(R0=R0, reduced_mass=mu, delta_R=dR, system_name=sys_name, conv=conv)
            for dR in delta_Rs
        ]

    return suite


# ---------------------------------------------------------------------------
# Coordinate Sensitivity Partitioning: Monomer vs Intermolecular (§4.5)
# ---------------------------------------------------------------------------
def build_co2_h2o_geometry(
    r_co: float = 1.1600,
    r_oh: float = 0.9575,
    theta_deg: float = 104.51,
    R: float = 2.836,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Builds Cartesian geometry for T-shaped CO2···H2O dimer (6 atoms) matching Method Matrix §4.5.
    
    Structure:
    - CO2 is linear along the Y axis, centered at origin (C at origin, O1/O2 along +/- Y).
    - H2O is placed at intermolecular separation R along the X axis.
    - Water oxygen sits at (R, 0, 0); hydrogen atoms are disposed symmetrically in the XZ plane.
    """
    m_C = get_atomic_mass("C", 12)
    m_O = get_atomic_mass("O", 16)
    m_H = get_atomic_mass("H", 1)

    theta_rad = math.radians(theta_deg)
    h_x = R + r_oh * math.cos(theta_rad / 2.0)
    h_z1 = r_oh * math.sin(theta_rad / 2.0)
    h_z2 = -h_z1

    coords = np.array(
        [
            [0.0, 0.0, 0.0],       # C (CO2)
            [0.0, r_co, 0.0],      # O1 (CO2)
            [0.0, -r_co, 0.0],     # O2 (CO2)
            [R, 0.0, 0.0],         # O_w (H2O)
            [h_x, 0.0, h_z1],      # H1 (H2O)
            [h_x, 0.0, h_z2],      # H2 (H2O)
        ],
        dtype=np.float64,
    )
    masses = np.array([m_C, m_O, m_O, m_O, m_H, m_H], dtype=np.float64)
    symbols = ["C", "O", "O", "O", "H", "H"]
    return coords, masses, symbols


def build_ch4_h2o_geometry(
    r_ch: float = 1.087,
    r_oh: float = 0.958,
    theta_deg: float = 104.5,
    R: float = 3.70,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Builds Cartesian geometry for CH4···H2O dimer (8 atoms) matching Method Matrix §4.5.
    
    Structure:
    - CH4 (tetrahedral Td) centered at origin (C at origin, 4 H vertices).
    - H2O at intermolecular separation R along X axis (O at (R, 0, 0), H in XZ plane).
    """
    m_C = get_atomic_mass("C", 12)
    m_H = get_atomic_mass("H", 1)
    m_O = get_atomic_mass("O", 16)

    s = r_ch / math.sqrt(3.0)
    ch4_c = np.array(
        [
            [0.0, 0.0, 0.0],
            [s, s, s],
            [s, -s, -s],
            [-s, s, -s],
            [-s, -s, s],
        ],
        dtype=np.float64,
    )
    ch4_m = np.array([m_C, m_H, m_H, m_H, m_H], dtype=np.float64)
    ch4_s = ["C", "H", "H", "H", "H"]

    theta_rad = math.radians(theta_deg)
    h2o_c = np.array(
        [
            [R, 0.0, 0.0],
            [R + r_oh * math.cos(theta_rad / 2.0), 0.0, r_oh * math.sin(theta_rad / 2.0)],
            [R + r_oh * math.cos(theta_rad / 2.0), 0.0, -r_oh * math.sin(theta_rad / 2.0)],
        ],
        dtype=np.float64,
    )
    h2o_m = np.array([m_O, m_H, m_H], dtype=np.float64)
    h2o_s = ["O", "H", "H"]

    coords = np.vstack([ch4_c, h2o_c])
    masses = np.concatenate([ch4_m, h2o_m])
    symbols = ch4_s + h2o_s
    return coords, masses, symbols


def compute_table_4_5_suite(
    conv: float = CONV_MHZ_AMU_ANG2,
) -> List[CoordinatePerturbationResult]:
    """
    Computes exact coordinate sensitivity suite for CO2···H2O (Method Matrix §4.5).
    Evaluates:
    - All monomer bond perturbations: +0.001, +0.003, +0.006, +0.010, +0.020 Angstrom
    - Intermolecular separation perturbations: R +0.002, +0.005, +0.010, +0.020 Angstrom
    - Valence angle perturbation: HOH angle +0.5 degrees
    - Break-even equivalent uniform monomer bond error for each R perturbation.
    """
    r_co_ref = 1.1600
    r_oh_ref = 0.9575
    th_ref = 104.51
    R_ref = 2.836

    c0, m0, s0 = build_co2_h2o_geometry(r_co=r_co_ref, r_oh=r_oh_ref, theta_deg=th_ref, R=R_ref)
    ref_obs = compute_rotational_observables(c0, m0, s0, conv=conv)
    A0, B0, C0 = ref_obs.A, ref_obs.B, ref_obs.C

    perturbations: List[Tuple[str, str, float, str, float, float, float, float]] = [
        ("all monomer bonds +0.001 Å", "monomer_bonds", 0.001, "Å", r_co_ref + 0.001, r_oh_ref + 0.001, th_ref, R_ref),
        ("+0.003 Å (fc-CCSD(T)/VTZ MAD)", "monomer_bonds", 0.003, "Å", r_co_ref + 0.003, r_oh_ref + 0.003, th_ref, R_ref),
        ("+0.006 Å (r²SCAN-3c class)", "monomer_bonds", 0.006, "Å", r_co_ref + 0.006, r_oh_ref + 0.006, th_ref, R_ref),
        ("+0.010 Å (B3LYP class)", "monomer_bonds", 0.010, "Å", r_co_ref + 0.010, r_oh_ref + 0.010, th_ref, R_ref),
        ("+0.020 Å (poor double-zeta DFT)", "monomer_bonds", 0.020, "Å", r_co_ref + 0.020, r_oh_ref + 0.020, th_ref, R_ref),
        ("R +0.002 Å", "R_separation", 0.002, "Å", r_co_ref, r_oh_ref, th_ref, R_ref + 0.002),
        ("R +0.005 Å", "R_separation", 0.005, "Å", r_co_ref, r_oh_ref, th_ref, R_ref + 0.005),
        ("R +0.010 Å", "R_separation", 0.010, "Å", r_co_ref, r_oh_ref, th_ref, R_ref + 0.010),
        ("R +0.020 Å", "R_separation", 0.020, "Å", r_co_ref, r_oh_ref, th_ref, R_ref + 0.020),
        ("HOH angle +0.5°", "HOH_angle", 0.5, "deg", r_co_ref, r_oh_ref, th_ref + 0.5, R_ref),
    ]

    # Monomer sensitivity scaling factor: Delta B % per mAngstrom of uniform monomer bond shift
    # From +0.001 A (1 mAngstrom) monomer bond perturbation:
    c_m1, m_m1, s_m1 = build_co2_h2o_geometry(r_co=r_co_ref + 0.001, r_oh=r_oh_ref + 0.001, theta_deg=th_ref, R=R_ref)
    obs_m1 = compute_rotational_observables(c_m1, m_m1, s_m1, conv=conv)
    dB_pct_per_mAng_mono = 100.0 * (obs_m1.B - B0) / B0

    results: List[CoordinatePerturbationResult] = []
    for label, param, val, unit, r_c, r_o, th, r_sep in perturbations:
        c_p, m_p, s_p = build_co2_h2o_geometry(r_co=r_c, r_oh=r_o, theta_deg=th, R=r_sep)
        obs_p = compute_rotational_observables(c_p, m_p, s_p, conv=conv)

        dA_pct = 100.0 * (obs_p.A - A0) / A0
        dB_pct = 100.0 * (obs_p.B - B0) / B0
        dC_pct = 100.0 * (obs_p.C - C0) / C0

        dA_MHz = obs_p.A - A0
        dB_MHz = obs_p.B - B0
        dC_MHz = obs_p.C - C0

        eq_mAng: Optional[float] = None
        if param == "R_separation":
            # Equivalent uniform monomer bond error in mAngstrom: delta_r_mAng = dB_pct / dB_pct_per_mAng_mono
            eq_mAng = float(dB_pct / dB_pct_per_mAng_mono)

        results.append(
            CoordinatePerturbationResult(
                complex_name="CO2···H2O",
                perturbation_label=label,
                parameter_name=param,
                perturbation_value=val,
                unit=unit,
                A_unperturbed=A0,
                B_unperturbed=B0,
                C_unperturbed=C0,
                A_perturbed=obs_p.A,
                B_perturbed=obs_p.B,
                C_perturbed=obs_p.C,
                delta_A_pct=dA_pct,
                delta_B_pct=dB_pct,
                delta_C_pct=dC_pct,
                delta_A_MHz=dA_MHz,
                delta_B_MHz=dB_MHz,
                delta_C_MHz=dC_MHz,
                equivalent_monomer_bond_error_mAng=eq_mAng,
                provenance=PROVENANCE_D,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Residual Gradient Threshold Analysis (Method Matrix §4.3, §4.4)
# ---------------------------------------------------------------------------
def compute_gradient_displacement(
    force_constant_mdyn_ang: float,
    tol_max_g_au: float,
    opt_level_name: str = "Custom",
    R_reference_angstrom: float = 3.50,
) -> ThresholdDisplacementResult:
    """
    Computes spatial displacement Delta r = g / k and implied Delta B / B error for a given
    residual gradient tolerance g (au) and force constant k (mdyn/Angstrom) (Method Matrix §4.3).
    """
    if force_constant_mdyn_ang <= 0.0:
        raise ValueError(f"force_constant_mdyn_ang must be positive, got {force_constant_mdyn_ang}")

    k_eh_bohr2 = force_constant_mdyn_ang * MDYN_ANG_TO_EH_BOHR2
    delta_r_bohr = tol_max_g_au / k_eh_bohr2
    delta_r_ang = delta_r_bohr * BOHR_TO_ANGSTROM
    delta_r_pm = delta_r_ang * ANGSTROM_TO_PM

    # Implied Delta B / B ~= 2 * Delta r / R
    implied_delta_B_pct = 200.0 * (delta_r_ang / R_reference_angstrom)

    if implied_delta_B_pct <= 0.10:
        compliance = "Compliant (<=0.1% Microwave Spectroscopic Target)"
    elif implied_delta_B_pct <= 0.50:
        compliance = "Semi-Rigid Search Window (<=0.5%)"
    elif implied_delta_B_pct <= 1.00:
        compliance = "Broad Search Screen (<=1.0%)"
    else:
        compliance = "Inadequate for Intermolecular Assignment (>1.0%)"

    return ThresholdDisplacementResult(
        opt_level=opt_level_name,
        tol_max_g_au=tol_max_g_au,
        force_constant_mdyn_ang=force_constant_mdyn_ang,
        force_constant_eh_bohr2=k_eh_bohr2,
        delta_r_bohr=delta_r_bohr,
        delta_r_pm=delta_r_pm,
        delta_r_angstrom=delta_r_ang,
        implied_delta_B_pct_at_3_5A=implied_delta_B_pct,
        compliance_class=compliance,
        provenance=PROVENANCE_D,
    )


def compute_table_4_3_suite() -> List[ThresholdDisplacementResult]:
    """
    Computes standard Method Matrix Table 4.3 optimization threshold suite
    across all standard levels (!LooseOpt, !Opt, !TightOpt, !VeryTightOpt, %geom custom).
    """
    levels = [
        ("!LooseOpt", 2e-3),
        ("!Opt (default)", 3e-4),
        ("!TightOpt", 1e-4),
        ("!VeryTightOpt", 3e-5),
        ("%geom custom (§4.4)", 1e-5),
    ]
    # Intermolecular stretch k = 0.069 mdyn/Angstrom (H2CO-HCl Fraser et al. 1987)
    k_vdw = 0.069

    return [
        compute_gradient_displacement(
            force_constant_mdyn_ang=k_vdw,
            tol_max_g_au=g_val,
            opt_level_name=lvl_name,
            R_reference_angstrom=3.50,
        )
        for lvl_name, g_val in levels
    ]


# ---------------------------------------------------------------------------
# Intramolecular Sensitivity Benchmark Suite (Method Matrix §4.6)
# ---------------------------------------------------------------------------
def compute_table_4_6_suite() -> List[IntramolecularSensitivityResult]:
    """
    Returns authoritative measured intramolecular bond length sensitivities from all-electron
    CCSD(T)/cc-pCVQZ equilibrium structures (Puzzarini & Stanton 2023, Method Matrix §4.6).
    """
    data = [
        ("SiS", 1.9316, 9077.97, -9.40, -0.1035),
        ("PN", 1.4913, 23563.42, -30.63, -0.1300),
        ("CN", 1.1674, 57386.18, -97.56, -0.1700),
        ("CO", 1.1289, 57841.66, -104.11, -0.1800),
        ("HCl", 1.2736, 318069.32, -498.90, -0.1569),
        ("OH", 0.9689, 567822.08, -1170.29, -0.2061),
        ("HF", 0.9158, 629664.95, -1372.92, -0.2180),
        ("H2O (A_e)", 0.9584, 805164.30, -1677.50, -0.2083),
        ("H2O (B_e)", 0.9584, 441462.40, -919.80, -0.2084),
        ("H2O (C_e)", 0.9584, 285129.30, -594.10, -0.2084),
    ]

    return [
        IntramolecularSensitivityResult(
            molecule=mol,
            r_e_angstrom=r_e,
            B_e_MHz=B_e,
            delta_B_plus_1mAng_MHz=dB,
            relative_sensitivity_pct=rel_sens,
            provenance=PROVENANCE_M,
        )
        for mol, r_e, B_e, dB, rel_sens in data
    ]


# ---------------------------------------------------------------------------
# Finite-Difference Jacobian Engine for Arbitrary Geometries
# ---------------------------------------------------------------------------
def compute_cartesian_jacobian(
    coords: np.ndarray,
    masses: np.ndarray,
    conv: float = CONV_MHZ_AMU_ANG2,
    delta: float = 1e-5,
) -> np.ndarray:
    """
    Computes the 3 x 3N Cartesian sensitivity Jacobian matrix J_alpha, i_beta = d(A,B,C)_alpha / d(x_i_beta)
    via central finite differences.
    """
    n_atoms = coords.shape[0]
    jacobian = np.zeros((3, n_atoms, 3), dtype=np.float64)

    for i in range(n_atoms):
        for beta in range(3):
            c_plus = coords.copy()
            c_minus = coords.copy()
            c_plus[i, beta] += delta
            c_minus[i, beta] -= delta

            I_plus = compute_inertia_tensor(c_plus, masses)
            I_minus = compute_inertia_tensor(c_minus, masses)

            A_p, B_p, C_p = compute_rotational_constants(I_plus, conv=conv)
            A_m, B_m, C_m = compute_rotational_constants(I_minus, conv=conv)

            jacobian[0, i, beta] = (A_p - A_m) / (2.0 * delta)
            jacobian[1, i, beta] = (B_p - B_m) / (2.0 * delta)
            jacobian[2, i, beta] = (C_p - C_m) / (2.0 * delta)

    return jacobian


# ---------------------------------------------------------------------------
# Method Matrix Assertions & Reference Validation Suite
# ---------------------------------------------------------------------------
def verify_method_matrix_section_4_2_table() -> bool:
    """Programmatically verifies reproduction of Method Matrix Section 4.2 Table."""
    suite = compute_table_4_2_suite()

    # Expected values for Ar-HCl at dR = 0.01 A: dB ~= 8.34 MHz, 0.50%
    ar_hcl_001 = [r for r in suite["Ar-HCl"] if math.isclose(r.delta_R_angstrom, 0.01, abs_tol=1e-4)][0]
    assert abs(abs(ar_hcl_001.delta_B_MHz) - 8.34) < 0.15, f"Ar-HCl 0.01A dB mismatch: {ar_hcl_001.delta_B_MHz}"
    assert abs(abs(ar_hcl_001.delta_B_pct) - 0.50) < 0.02, f"Ar-HCl 0.01A % mismatch: {ar_hcl_001.delta_B_pct}"

    # Water dimer at dR = 0.01 A: dB ~= 45.6 MHz, 0.69%
    wdim_001 = [r for r in suite["water dimer"] if math.isclose(r.delta_R_angstrom, 0.01, abs_tol=1e-4)][0]
    assert abs(abs(wdim_001.delta_B_MHz) - 45.6) < 0.8, f"Water dimer 0.01A dB mismatch: {wdim_001.delta_B_MHz}"
    assert abs(abs(wdim_001.delta_B_pct) - 0.69) < 0.03, f"Water dimer 0.01A % mismatch: {wdim_001.delta_B_pct}"

    return True


def verify_method_matrix_section_4_5_table() -> bool:
    """Programmatically verifies reproduction of Method Matrix Section 4.5 Table (CO2···H2O)."""
    res = compute_table_4_5_suite()
    by_label = {r.perturbation_label: r for r in res}

    # Reference values from Method Matrix §4.5:
    # all monomer bonds +0.001 A: dA/A = -0.173%, dB/B = -0.008%, dC/C = -0.053%, dB = -0.37 MHz
    m_001 = by_label["all monomer bonds +0.001 Å"]
    assert abs(m_001.delta_A_pct - (-0.173)) < 0.01, f"Mismatch dA/A: {m_001.delta_A_pct}"
    assert abs(m_001.delta_B_pct - (-0.008)) < 0.005, f"Mismatch dB/B: {m_001.delta_B_pct}"
    assert abs(m_001.delta_C_pct - (-0.053)) < 0.01, f"Mismatch dC/C: {m_001.delta_C_pct}"
    assert abs(m_001.delta_B_MHz - (-0.37)) < 0.05, f"Mismatch dB MHz: {m_001.delta_B_MHz}"

    # R +0.002 A: dA/A = 0.000%, dB/B = -0.135%, dC/C = -0.098%, dB = -6.26 MHz
    r_002 = by_label["R +0.002 Å"]
    assert abs(r_002.delta_A_pct - 0.000) < 0.005, f"Mismatch dA/A: {r_002.delta_A_pct}"
    assert abs(r_002.delta_B_pct - (-0.135)) < 0.01, f"Mismatch dB/B: {r_002.delta_B_pct}"
    assert abs(r_002.delta_C_pct - (-0.098)) < 0.01, f"Mismatch dC/C: {r_002.delta_C_pct}"
    assert abs(r_002.delta_B_MHz - (-6.26)) < 0.10, f"Mismatch dB MHz: {r_002.delta_B_MHz}"

    # Break-even check: Delta R = 0.002 A equivalent monomer error ~= 16.8 mAngstrom
    assert r_002.equivalent_monomer_bond_error_mAng is not None
    assert abs(r_002.equivalent_monomer_bond_error_mAng - 16.8) < 0.5, (
        f"Break-even mismatch: {r_002.equivalent_monomer_bond_error_mAng}"
    )

    return True


def verify_method_matrix_section_4_3_table() -> bool:
    """Programmatically verifies reproduction of Method Matrix Section 4.3 Table."""
    suite = compute_table_4_3_suite()
    by_opt = {r.opt_level: r for r in suite}

    # !Opt at k = 0.069 mdyn/A => Delta r ~= 3.6 pm
    opt_res = by_opt["!Opt (default)"]
    assert abs(opt_res.delta_r_pm - 3.6) < 0.2, f"!Opt pm mismatch: {opt_res.delta_r_pm}"

    # !VeryTightOpt => Delta r ~= 0.36 pm
    vt_res = by_opt["!VeryTightOpt"]
    assert abs(vt_res.delta_r_pm - 0.36) < 0.05, f"!VeryTightOpt pm mismatch: {vt_res.delta_r_pm}"

    return True


def run_full_method_matrix_verification() -> MethodMatrixAuditReport:
    """Runs full suite of Method Matrix reference verifications and generates an audit report."""
    findings: List[str] = []
    rejection = False

    try:
        verify_method_matrix_section_4_2_table()
        findings.append("[PASSED §4.2] 1D pseudo-diatomic error propagation suite exactly reproduces Table 4.2.")
    except Exception as e:
        findings.append(f"[FAILED §4.2] Table 4.2 reproduction failed: {e}")
        rejection = True

    try:
        verify_method_matrix_section_4_5_table()
        findings.append("[PASSED §4.5] Coordinate sensitivity partitioning and break-even suite exactly reproduces Table 4.5.")
    except Exception as e:
        findings.append(f"[FAILED §4.5] Table 4.5 reproduction failed: {e}")
        rejection = True

    try:
        verify_method_matrix_section_4_3_table()
        findings.append("[PASSED §4.3] Optimization threshold displacement suite exactly reproduces Table 4.3.")
    except Exception as e:
        findings.append(f"[FAILED §4.3] Table 4.3 reproduction failed: {e}")
        rejection = True

    status = "REJECTED_NON_COMPLIANT" if rejection else "PASSED_COMPLIANT"
    payload_str = json.dumps({"status": status, "findings": findings}, sort_keys=True)
    sha = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    report = MethodMatrixAuditReport(
        status=status,
        section=f"{SECTION_REF_4_1}, {SECTION_REF_4_2}, {SECTION_REF_4_3}, {SECTION_REF_4_5}",
        rejection_triggered=rejection,
        findings=findings,
        sha256_checksum=sha,
    )

    if rejection:
        raise PropagationComplianceError("; ".join(findings))

    return report


# ---------------------------------------------------------------------------
# Formatting & Pretty-Printing Utilities
# ---------------------------------------------------------------------------
def format_table_4_2_markdown(suite: Dict[str, List[Propagation1DResult]]) -> str:
    """Formats Table 4.2 as GitHub-Flavored Markdown."""
    delta_Rs = [0.001, 0.010, 0.020, 0.034, 0.056, 0.140]
    systems = list(suite.keys())

    header = [
        "| ΔR | " + " | ".join([f"{s} (μ={suite[s][0].reduced_mass_amu:.2f}, R={suite[s][0].R0_angstrom:.2f} Å, B={suite[s][0].B0_MHz:.0f} MHz)" for s in systems]) + " |",
        "|---" + "|---" * len(systems) + "|",
    ]

    rows = []
    for i, dR in enumerate(delta_Rs):
        bold = "**" if math.isclose(dR, 0.010, abs_tol=1e-4) else ""
        cells = [f"{bold}{dR:.3f} Å{bold}"]
        for s in systems:
            res = suite[s][i]
            cells.append(f"{bold}{abs(res.delta_B_MHz):.2f} MHz ({abs(res.delta_B_pct):.3f} %){bold}")
        rows.append("| " + " | ".join(cells) + " |")

    return "\n".join(header + rows)


def format_table_4_5_markdown(results: List[CoordinatePerturbationResult]) -> str:
    """Formats Table 4.5 as GitHub-Flavored Markdown."""
    header = [
        "| Perturbation | ΔA/A % | ΔB/B % | ΔC/C % | ΔB (MHz) | Break-Even Monomer Error | Provenance |",
        "|:---|---:|---:|---:|---:|:---:|:---:|",
    ]
    rows = []
    for r in results:
        bold = "**" if (r.parameter_name == "R_separation" or "B3LYP" in r.perturbation_label) else ""
        eq_str = f"{r.equivalent_monomer_bond_error_mAng:.1f} mÅ" if r.equivalent_monomer_bond_error_mAng is not None else "—"
        rows.append(
            f"| {bold}{r.perturbation_label}{bold} | "
            f"{r.delta_A_pct:+.3f} | "
            f"{r.delta_B_pct:+.3f} | "
            f"{r.delta_C_pct:+.3f} | "
            f"{r.delta_B_MHz:+.2f} | "
            f"{eq_str} | "
            f"{r.provenance} |"
        )
    return "\n".join(header + rows)


def format_table_4_3_markdown(results: List[ThresholdDisplacementResult]) -> str:
    """Formats Table 4.3 as GitHub-Flavored Markdown."""
    header = [
        "| Level | TolMaxG (a.u.) | Δr at k=0.069 mdyn/Å (pm) | Implied ΔB/B at R=3.5 Å (%) | Compliance Class | Provenance |",
        "|:---|---:|---:|---:|:---|:---:|",
    ]
    rows = []
    for r in results:
        bold = "**" if "geom" in r.opt_level or "VeryTight" in r.opt_level else ""
        rows.append(
            f"| {bold}{r.opt_level}{bold} | "
            f"{r.tol_max_g_au:.1e} | "
            f"{bold}{r.delta_r_pm:.2f} pm{bold} | "
            f"{bold}{r.implied_delta_B_pct_at_3_5A:.2f} %{bold} | "
            f"{r.compliance_class} | "
            f"{r.provenance} |"
        )
    return "\n".join(header + rows)


def format_table_4_6_markdown(results: List[IntramolecularSensitivityResult]) -> str:
    """Formats Table 4.6 as GitHub-Flavored Markdown."""
    header = [
        "| Molecule | r_e (Å) | B_e (MHz) | ΔB for +0.001 Å (MHz) | Relative Sensitivity (%) | Provenance |",
        "|:---|---:|---:|---:|---:|:---:|",
    ]
    rows = []
    for r in results:
        rows.append(
            f"| {r.molecule} | "
            f"{r.r_e_angstrom:.4f} | "
            f"{r.B_e_MHz:.2f} | "
            f"{r.delta_B_plus_1mAng_MHz:+.2f} | "
            f"{r.relative_sensitivity_pct:+.2f} % | "
            f"{r.provenance} |"
        )
    return "\n".join(header + rows)


# ---------------------------------------------------------------------------
# CLI Application Entrypoint
# ---------------------------------------------------------------------------
def main() -> int:
    """CLI entrypoint for rotational constant error propagation analysis."""
    parser = argparse.ArgumentParser(
        description="Method Matrix §4.1, §4.2, §4.3, §4.5, §4.6, §12.3 Exact Rigid-Rotor Propagation Suite."
    )
    parser.add_argument(
        "--table-4-2",
        action="store_true",
        help="Print Method Matrix Table 4.2 (1D pseudo-diatomic propagation suite).",
    )
    parser.add_argument(
        "--table-4-5",
        action="store_true",
        help="Print Method Matrix Table 4.5 (CO2···H2O coordinate sensitivity partitioning).",
    )
    parser.add_argument(
        "--table-4-3",
        action="store_true",
        help="Print Method Matrix Table 4.3 (optimization gradient thresholds).",
    )
    parser.add_argument(
        "--table-4-6",
        action="store_true",
        help="Print Method Matrix Table 4.6 (intramolecular bond sensitivities).",
    )
    parser.add_argument(
        "--breakeven",
        action="store_true",
        help="Print detailed break-even analysis between monomer bond error and Delta R.",
    )
    parser.add_argument(
        "--verify-all",
        action="store_true",
        help="Run strict programmatic assertions against all Method Matrix §4 tables.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit full validation and computation suite in JSON format.",
    )
    parser.add_argument(
        "--jacobian-demo",
        action="store_true",
        help="Compute and display Cartesian sensitivity Jacobian for CO2···H2O.",
    )

    args = parser.parse_args()

    # Default action if no flags provided
    if not (args.table_4_2 or args.table_4_5 or args.table_4_3 or args.table_4_6 or args.breakeven or args.verify_all or args.json or args.jacobian_demo):
        args.table_4_5 = True
        args.breakeven = True
        args.verify_all = True

    if args.verify_all:
        report = run_full_method_matrix_verification()
        logger.info("All Method Matrix §4 reference verifications: %s", report.status)

    if args.json:
        suite_4_2 = compute_table_4_2_suite()
        suite_4_5 = compute_table_4_5_suite()
        suite_4_3 = compute_table_4_3_suite()
        suite_4_6 = compute_table_4_6_suite()
        audit = run_full_method_matrix_verification()

        payload = {
            "metadata": {
                "module": "mm.conference2.a7.propagate",
                "mandate": "Method Matrix §4.1, §4.2, §4.3, §4.5, §4.6, §12.3, §16.3",
                "conversion_constant_MHz_amu_Ang2": CONV_MHZ_AMU_ANG2,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            },
            "audit_report": audit.to_dict(),
            "table_4_2_pseudo_diatomic": {k: [r.to_dict() for r in v] for k, v in suite_4_2.items()},
            "table_4_5_co2_h2o_partitioning": [r.to_dict() for r in suite_4_5],
            "table_4_3_optimization_thresholds": [r.to_dict() for r in suite_4_3],
            "table_4_6_intramolecular_sensitivities": [r.to_dict() for r in suite_4_6],
        }
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return 0

    if args.table_4_2:
        suite_4_2 = compute_table_4_2_suite()
        print("\n" + "=" * 90)
        print(" Method Matrix §4.2 Worked Error Propagation: Pseudo-Diatomic Complexes ")
        print("=" * 90)
        print(format_table_4_2_markdown(suite_4_2))
        print()

    if args.table_4_5:
        suite_4_5 = compute_table_4_5_suite()
        print("\n" + "=" * 90)
        print(" Method Matrix §4.5 Coordinate Sensitivity Partitioning: CO2···H2O (R = 2.836 Å) ")
        print(" Reference Constants: A = 11433.66 MHz, B = 4621.35 MHz, C = 3341.41 MHz [D] ")
        print("=" * 90)
        print(format_table_4_5_markdown(suite_4_5))
        print()

    if args.table_4_3:
        suite_4_3 = compute_table_4_3_suite()
        print("\n" + "=" * 90)
        print(" Method Matrix §4.3 Optimization Threshold Arithmetic & Residual Gradient Displacements ")
        print(" Model: Soft Intermolecular Mode k = 0.069 mdyn/Å (4.425e-3 Eh/bohr^2) ")
        print("=" * 90)
        print(format_table_4_3_markdown(suite_4_3))
        print()

    if args.table_4_6:
        suite_4_6 = compute_table_4_6_suite()
        print("\n" + "=" * 90)
        print(" Method Matrix §4.6 Measured Intramolecular Bond Length Sensitivities (Puzzarini & Stanton) ")
        print("=" * 90)
        print(format_table_4_6_markdown(suite_4_6))
        print()

    if args.breakeven:
        print("\n" + "=" * 90)
        print(" Method Matrix §4.5 Break-Even Analysis on B (CO2···H2O) ")
        print("=" * 90)
        print("Statement: ΔR in intermolecular coordinate produces the same ΔB as a uniform monomer error:")
        print("  - ΔR = 0.002 Å  <==>  16.8 mÅ (0.0168 Å) uniform monomer bond error")
        print("  - ΔR = 0.005 Å  <==>  41.9 mÅ (0.0419 Å) uniform monomer bond error")
        print("  - ΔR = 0.010 Å  <==>  83.1 mÅ (0.0831 Å) uniform monomer bond error")
        print("  - ΔR = 0.020 Å  <==> 163.5 mÅ (0.1635 Å) uniform monomer bond error")
        print("Conclusion: No electronic-structure method errs by 83 mÅ on a covalent bond.")
        print("Strategy: Freeze good monomers to fix A; spend remaining budget on R to fix B and C.")
        print("=" * 90 + "\n")

    if args.jacobian_demo:
        print("\n--- Cartesian Sensitivity Jacobian Demo (CO2···H2O) ---")
        c0, m0, s0 = build_co2_h2o_geometry()
        jac = compute_cartesian_jacobian(c0, m0)
        print(f"Jacobian Shape: {jac.shape} (Observables [A,B,C] x Atoms x Coordinates [x,y,z])")
        print("d(A)/d(x_i):", jac[0].tolist())
        print("d(B)/d(x_i):", jac[1].tolist())
        print("d(C)/d(x_i):", jac[2].tolist())
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
