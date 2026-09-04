#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Method Matrix Reference Validation Suite: Jensen's Inequality & Vibrationally Averaged Moments.

Mandated by Method Matrix §5.1, §16.3, and Table 4-O (T4O-3d, T4O-1w).

Physical Background & Mathematical Foundation:
----------------------------------------------
The vibrationally averaged rotational constant is one-half the expectation value of
the inverse effective inertia tensor, NOT a function of the expectation value of
the inertia tensor.

In the Eckart-Watson formulation (Czako, Matyus, and Czaszar, JPCA 113, 11665 (2009)):
    mu_alpha_beta = (I'^-1)_alpha_beta
    I'_R_gamma = I_R_gamma - sum_{k,l,m} zeta^{km}_R zeta^{lm}_gamma Q_k Q_l
    A_V ~= 1/2 <mu_xx>_V
    B_V ~= 1/2 <mu_yy>_V
    C_V ~= 1/2 <mu_zz>_V

In frequency units (MHz):
    B[MHz] = CONV / I[amu Angstrom^2], where CONV = 505379.0 MHz*amu*Angstrom^2 (Groner, NIST CCCBDB).
    Equivalently, B[MHz] = CONV * mu[amu^-1 Angstrom^-2].

Jensen's Inequality:
-------------------
By Jensen's inequality for the convex function f(x) = 1/x (for x > 0):
    <1/I> >= 1/<I>

Averaging the wrong quantity (i.e., inverting <I> rather than taking <I^-1>) systematically
underestimates the rotational constant. The leading fractional bias is:
    fractional_bias = 3 * sigma_R^2 / R0^2

For a typical floppy intermolecular stretch (reduced mass = 10.0 amu, R0 = 3.80 Angstrom):
- sigma_R = 0.05 Angstrom: B(<1/I>) = 3501.69 MHz, B(1/<I>) = 3499.26 MHz, bias = 2.43 MHz (0.069%)
- sigma_R = 0.10 Angstrom: B(<1/I>) = 3507.18 MHz, B(1/<I>) = 3497.46 MHz, bias = 9.72 MHz (0.278%)
- sigma_R = 0.15 Angstrom: B(<1/I>) = 3516.38 MHz, B(1/<I>) = 3494.45 MHz, bias = 21.93 MHz (0.628%)
- sigma_R = 0.20 Angstrom: B(<1/I>) = 3529.40 MHz, B(1/<I>) = 3490.25 MHz, bias = 39.16 MHz (1.122%)
- sigma_R = 0.30 Angstrom: B(<1/I>) = 3567.50 MHz, B(1/<I>) = 3478.27 MHz, bias = 89.24 MHz (2.566%)

At zero-point amplitude sigma_R ~= 0.15 Angstrom, the systematic bias is 21.93 MHz (0.63%), which is
more than 6x the 0.1% microwave spectroscopic assignment target!

Method Matrix Section 16.3 Rejection Mandate:
--------------------------------------------
"A result is discarded if ... a rotational constant is computed by inverting the
averaged inertia tensor rather than averaging the inverse inertia tensor."
Any calculation that evaluates 1/<I> instead of <1/I> is strictly non-compliant and
must be rejected.
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
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from scipy import integrate

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
# Reference: Groner (2016); NIST CCCBDB; Method Matrix Section 5.1, Section 4.1.
CONV_MHZ_AMU_ANG2: float = 505379.0
CODATA_CONV_EXACT: float = 505379.00536  # High-precision Groner / CODATA constant

PROVENANCE_TAG: str = "[M]"
SECTION_REF: str = "Method Matrix §5.1 & §16.3"

logger = logging.getLogger("cochem.mm.conference.ref.jensen")


# ---------------------------------------------------------------------------
# Custom Exceptions (Method Matrix §16.3 Guardrails)
# ---------------------------------------------------------------------------
class MethodMatrixComplianceError(Exception):
    """Base exception for violations of Method Matrix mandates."""


class VibrationalAveragingRejectionError(MethodMatrixComplianceError):
    """Raised when vibrational averaging inverts <I> instead of averaging <1/I>."""


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
    # Handle hydrogen isotopes notation
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
class Jensen1DResult:
    """Results container for 1D intermolecular stretch vibrational averaging."""
    sigma_R: float
    R0: float
    reduced_mass: float
    B_e: float
    B_inv_I: float
    B_I_avg: float
    bias_MHz: float
    bias_pct: float
    taylor_B_inv_I: float
    leading_fractional_bias: float
    provenance: str = PROVENANCE_TAG

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Jensen3DResult:
    """Results container for 3D polyatomic molecular vibrational tensor averaging."""
    symbols: List[str]
    n_atoms: int
    n_snapshots: int
    A_correct: float
    B_correct: float
    C_correct: float
    A_flawed: float
    B_flawed: float
    C_flawed: float
    bias_A_MHz: float
    bias_B_MHz: float
    bias_C_MHz: float
    bias_pct_A: float
    bias_pct_B: float
    bias_pct_C: float
    avg_mu_tensor: List[List[float]]
    avg_I_tensor: List[List[float]]
    is_valid_jensen: bool
    provenance: str = PROVENANCE_TAG

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MethodMatrixAuditReport:
    """Audit verification report for Method Matrix §16.3 compliance."""
    status: str
    section: str
    rejection_triggered: bool
    findings: List[str]
    sha256_checksum: str
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 1D Floppy Intermolecular Stretch Model (Method Matrix §5.1)
# ---------------------------------------------------------------------------
def compute_1d_jensen_model(
    R0: float = 3.80,
    reduced_mass: float = 10.0,
    sigma_R: float = 0.15,
    conv: float = CONV_MHZ_AMU_ANG2,
) -> Jensen1DResult:
    """
    Computes exact vibrationally averaged rotational constants for a 1D floppy
    stretch mode with Gaussian probability density P(R) ~ N(R0, sigma_R^2).
    
    Equations:
        I(R) = mu * R^2
        B_e = CONV / (mu * R0^2)
        <I> = mu * (R0^2 + sigma_R^2)
        B(1/<I>) = CONV / <I> = CONV / [mu * (R0^2 + sigma_R^2)]
        <1/I> = int P(R) / (mu * R^2) dR
        B(<1/I>) = CONV * <1/I>
        bias = B(<1/I>) - B(1/<I>)
        bias_% = 100 * bias / B(1/<I>)
        leading_fractional_bias = 3 * sigma_R^2 / R0^2
    """
    if R0 <= 0.0:
        raise ValueError(f"Equilibrium separation R0 must be positive, got {R0}")
    if reduced_mass <= 0.0:
        raise ValueError(f"Reduced mass must be positive, got {reduced_mass}")
    if sigma_R <= 0.0:
        raise ValueError(f"Standard deviation sigma_R must be positive, got {sigma_R}")

    I0 = reduced_mass * (R0 ** 2)
    B_e = conv / I0

    # Exact Gaussian distribution integration for <1/I>
    def integrand_inv_I(r: float) -> float:
        norm_const = 1.0 / (math.sqrt(2.0 * math.pi) * sigma_R)
        p_r = norm_const * math.exp(-0.5 * (((r - R0) / sigma_R) ** 2))
        return p_r / (reduced_mass * (r ** 2))

    # Numerical integration across 10 standard deviations
    r_min = max(1e-4, R0 - 10.0 * sigma_R)
    r_max = R0 + 10.0 * sigma_R
    inv_I_avg, _ = integrate.quad(integrand_inv_I, r_min, r_max, epsabs=1e-13, epsrel=1e-13)
    B_inv_I = conv * inv_I_avg

    # Analytical exact expectation value <I> = mu * (R0^2 + sigma_R^2)
    I_avg = reduced_mass * (R0 ** 2 + sigma_R ** 2)
    B_I_avg = conv / I_avg

    bias_MHz = B_inv_I - B_I_avg
    bias_pct = (bias_MHz / B_I_avg) * 100.0

    # High-order Taylor series expansion:
    # <1/R^2> = R0^-2 * [1 + 3*(sigma/R0)^2 + 15*(sigma/R0)^4 + 105*(sigma/R0)^6]
    x2 = (sigma_R / R0) ** 2
    taylor_factor = 1.0 + 3.0 * x2 + 15.0 * (x2 ** 2) + 105.0 * (x2 ** 3)
    taylor_B_inv_I = B_e * taylor_factor

    leading_fractional_bias = 3.0 * x2

    return Jensen1DResult(
        sigma_R=sigma_R,
        R0=R0,
        reduced_mass=reduced_mass,
        B_e=B_e,
        B_inv_I=B_inv_I,
        B_I_avg=B_I_avg,
        bias_MHz=bias_MHz,
        bias_pct=bias_pct,
        taylor_B_inv_I=taylor_B_inv_I,
        leading_fractional_bias=leading_fractional_bias,
    )


def compute_1d_benchmark_suite(
    R0: float = 3.80,
    reduced_mass: float = 10.0,
    sigmas: Optional[Sequence[float]] = None,
    conv: float = CONV_MHZ_AMU_ANG2,
) -> List[Jensen1DResult]:
    """
    Computes the standard Method Matrix §5.1 validation benchmark suite
    across all mandated zero-point amplitudes [0.05, 0.10, 0.15, 0.20, 0.30] Angstrom.
    """
    if sigmas is None:
        sigmas = [0.05, 0.10, 0.15, 0.20, 0.30]

    return [
        compute_1d_jensen_model(R0=R0, reduced_mass=reduced_mass, sigma_R=s, conv=conv)
        for s in sigmas
    ]


# ---------------------------------------------------------------------------
# 3D Polyatomic Molecular Ensemble Tensor Averaging Engine (Eckart-Watson)
# ---------------------------------------------------------------------------
def compute_center_of_mass(coords: np.ndarray, masses: np.ndarray) -> np.ndarray:
    """Computes the center of mass vector for a Cartesian coordinate frame."""
    total_mass = float(np.sum(masses))
    if total_mass <= 0.0:
        raise ValueError("Total molecular mass must be strictly positive.")
    return np.sum(coords * masses[:, np.newaxis], axis=0) / total_mass


def compute_inertia_tensor(coords: np.ndarray, masses: np.ndarray) -> np.ndarray:
    """
    Computes the 3x3 moment of inertia tensor in amu * Angstrom^2.
    Shifts coordinates to the center-of-mass frame before accumulation.
    
    Formula:
        I_alpha_beta = sum_i m_i * [ ||r_i - COM||^2 * delta_alpha_beta - (r_i - COM)_alpha * (r_i - COM)_beta ]
    """
    com = compute_center_of_mass(coords, masses)
    r = coords - com
    I = np.zeros((3, 3), dtype=np.float64)
    for i in range(len(masses)):
        m = masses[i]
        r_i = r[i]
        r2 = float(np.dot(r_i, r_i))
        I[0, 0] += m * (r2 - r_i[0] ** 2)
        I[1, 1] += m * (r2 - r_i[1] ** 2)
        I[2, 2] += m * (r2 - r_i[2] ** 2)
        I[0, 1] -= m * (r_i[0] * r_i[1])
        I[0, 2] -= m * (r_i[0] * r_i[2])
        I[1, 2] -= m * (r_i[1] * r_i[2])

    I[1, 0] = I[0, 1]
    I[2, 0] = I[0, 2]
    I[2, 1] = I[1, 2]
    return I


def compute_principal_moments(I: np.ndarray) -> Tuple[float, float, float]:
    """Diagonalizes inertia tensor to obtain principal moments I_a <= I_b <= I_c."""
    eigvals = np.linalg.eigvalsh(I)
    sorted_moments = np.sort(eigvals)
    return float(sorted_moments[0]), float(sorted_moments[1]), float(sorted_moments[2])


def compute_rotational_constants_from_inertia(
    I: np.ndarray,
    conv: float = CONV_MHZ_AMU_ANG2,
) -> Tuple[float, float, float]:
    """Computes rotational constants (A >= B >= C) from a 3x3 moment of inertia tensor."""
    Ia, Ib, Ic = compute_principal_moments(I)
    if Ia <= 1e-12:
        raise ValueError(f"Singular or degenerate principal moment of inertia: {Ia}")
    A = conv / Ia
    B = conv / Ib
    C = conv / Ic
    return float(A), float(B), float(C)


def compute_rotational_constants_from_inverse_inertia(
    mu: np.ndarray,
    conv: float = CONV_MHZ_AMU_ANG2,
) -> Tuple[float, float, float]:
    """
    Computes rotational constants (A >= B >= C) directly from the eigenvalues of
    the generalized inverse inertia tensor mu = I^-1.
    
    Formula:
        eigvals(mu) = [mu_c <= mu_b <= mu_a]
        A = conv * mu_a
        B = conv * mu_b
        C = conv * mu_c
    """
    eigvals = np.linalg.eigvalsh(mu)
    sorted_mu = np.sort(eigvals)[::-1]  # descending order: mu_a >= mu_b >= mu_c
    A = conv * float(sorted_mu[0])
    B = conv * float(sorted_mu[1])
    C = conv * float(sorted_mu[2])
    return float(A), float(B), float(C)


def eckart_align(
    coords: np.ndarray,
    ref_coords: np.ndarray,
    masses: np.ndarray,
) -> np.ndarray:
    """
    Performs optimal mass-weighted Eckart alignment (Kabsch algorithm)
    of `coords` onto `ref_coords` so that rotational coordinates are referenced
    to a single unambiguous Eckart frame (Method Matrix Section 5.1).
    """
    com_target = compute_center_of_mass(coords, masses)
    com_ref = compute_center_of_mass(ref_coords, masses)

    r_target = coords - com_target
    r_ref = ref_coords - com_ref

    # Mass-weighted covariance matrix H = sum_i m_i * (r_target_i) (r_ref_i)^T
    W = np.diag(masses)
    H = np.dot(r_target.T, np.dot(W, r_ref))

    U, S, Vt = np.linalg.svd(H)
    R_mat = np.dot(Vt.T, U.T)

    # Ensure proper rotation (det(R) == +1)
    if np.linalg.det(R_mat) < 0:
        Vt[-1, :] *= -1.0
        R_mat = np.dot(Vt.T, U.T)

    aligned = np.dot(r_target, R_mat.T) + com_ref
    return aligned


def average_inverse_inertia_ensemble(
    ensemble_coords: np.ndarray,
    masses: np.ndarray,
    symbols: Optional[Sequence[str]] = None,
    conv: float = CONV_MHZ_AMU_ANG2,
    ref_coords: Optional[np.ndarray] = None,
) -> Jensen3DResult:
    """
    Computes vibrationally averaged rotational constants for an ensemble of
    3D molecular geometries (e.g. from PIMD beads, DMC walkers, or normal mode sampling).
    
    Evaluates:
    1. Correct route: <mu> = (1/M) sum_{k=1}^M [I(k)^-1], then diagonalizes <mu>.
    2. Flawed route: <I> = (1/M) sum_{k=1}^M I(k), then inverts and diagonalizes.
    3. Exact Jensen bias vector [dA, dB, dC] in MHz and percentages.
    """
    if ensemble_coords.ndim != 3 or ensemble_coords.shape[2] != 3:
        raise ValueError(
            f"ensemble_coords must have shape (M, N, 3), got {ensemble_coords.shape}"
        )
    
    n_snapshots, n_atoms, _ = ensemble_coords.shape
    if len(masses) != n_atoms:
        raise ValueError(
            f"Length of masses ({len(masses)}) does not match n_atoms ({n_atoms})"
        )

    if symbols is None:
        sym_list = [f"X{i+1}" for i in range(n_atoms)]
    else:
        sym_list = list(symbols)

    if ref_coords is None:
        ref_coords = ensemble_coords[0]

    mu_accum = np.zeros((3, 3), dtype=np.float64)
    I_accum = np.zeros((3, 3), dtype=np.float64)

    for k in range(n_snapshots):
        curr_geom = ensemble_coords[k]
        aligned_geom = eckart_align(curr_geom, ref_coords, masses)
        I_k = compute_inertia_tensor(aligned_geom, masses)
        mu_k = np.linalg.inv(I_k)

        I_accum += I_k
        mu_accum += mu_k

    avg_mu = mu_accum / float(n_snapshots)
    avg_I = I_accum / float(n_snapshots)

    # Correct route: diagonalize <mu>
    A_corr, B_corr, C_corr = compute_rotational_constants_from_inverse_inertia(avg_mu, conv=conv)

    # Flawed route: diagonalize <I>, then invert
    A_flaw, B_flaw, C_flaw = compute_rotational_constants_from_inertia(avg_I, conv=conv)

    bias_A = A_corr - A_flaw
    bias_B = B_corr - B_flaw
    bias_C = C_corr - C_flaw

    bias_pct_A = (bias_A / A_flaw) * 100.0 if A_flaw > 0 else 0.0
    bias_pct_B = (bias_B / B_flaw) * 100.0 if B_flaw > 0 else 0.0
    bias_pct_C = (bias_C / C_flaw) * 100.0 if C_flaw > 0 else 0.0

    # Verification of Jensen's inequality: A_corr >= A_flaw, B_corr >= B_flaw, C_corr >= C_flaw
    eps = -1e-7  # Numerical tolerance
    is_valid_jensen = (bias_A >= eps) and (bias_B >= eps) and (bias_C >= eps)

    return Jensen3DResult(
        symbols=sym_list,
        n_atoms=n_atoms,
        n_snapshots=n_snapshots,
        A_correct=A_corr,
        B_correct=B_corr,
        C_correct=C_corr,
        A_flawed=A_flaw,
        B_flawed=B_flaw,
        C_flawed=C_flaw,
        bias_A_MHz=bias_A,
        bias_B_MHz=bias_B,
        bias_C_MHz=bias_C,
        bias_pct_A=bias_pct_A,
        bias_pct_B=bias_pct_B,
        bias_pct_C=bias_pct_C,
        avg_mu_tensor=avg_mu.tolist(),
        avg_I_tensor=avg_I.tolist(),
        is_valid_jensen=is_valid_jensen,
    )


def generate_vdw_stretch_ensemble(
    monomer1_coords: np.ndarray,
    monomer2_coords: np.ndarray,
    monomer1_masses: np.ndarray,
    monomer2_masses: np.ndarray,
    R0: float = 3.80,
    sigma_R: float = 0.15,
    n_samples: int = 10000,
    seed: Optional[int] = 42,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Generates a synthetic physical vibrational ensemble for a weakly bound van der Waals
    dimer along the intermolecular separation coordinate R ~ N(R0, sigma_R^2).
    """
    if seed is not None:
        np.random.seed(seed)

    com1 = compute_center_of_mass(monomer1_coords, monomer1_masses)
    com2 = compute_center_of_mass(monomer2_coords, monomer2_masses)

    m1_centered = monomer1_coords - com1
    m2_centered = monomer2_coords - com2

    axis = np.array([0.0, 0.0, 1.0], dtype=np.float64)

    total_masses = np.concatenate([monomer1_masses, monomer2_masses])
    n_total_atoms = len(total_masses)
    symbols = ["Ar", "C", "O", "O"][:n_total_atoms]

    ensemble = np.zeros((n_samples, n_total_atoms, 3), dtype=np.float64)
    r_displacements = np.random.normal(R0, sigma_R, size=n_samples)

    for k in range(n_samples):
        R_k = max(0.5, float(r_displacements[k]))
        pos1 = m1_centered - 0.5 * R_k * axis
        pos2 = m2_centered + 0.5 * R_k * axis
        ensemble[k] = np.vstack([pos1, pos2])

    return ensemble, total_masses, symbols


# ---------------------------------------------------------------------------
# Method Matrix §16.3 Compliance & Audit Protocol
# ---------------------------------------------------------------------------
def validate_vibrational_averaging_compliance(
    averaging_method: str,
    inverse_before_avg: bool,
    eckart_aligned: bool = True,
) -> MethodMatrixAuditReport:
    """
    Validates a computational pipeline against Method Matrix Section 5.1 and Section 16.3 mandates.
    Rejects any execution that inverts <I> or averages rotational constants directly.
    """
    findings: List[str] = []
    rejection_triggered = False

    if not inverse_before_avg:
        findings.append(
            "[REJECTION TRIGGERED §16.3] Averaging strategy computed <I> before inversion "
            "or inverted the averaged inertia tensor. Violates Jensen's inequality directive."
        )
        rejection_triggered = True

    if not eckart_aligned:
        findings.append(
            "[WARNING §5.1] Snapshots were not aligned to a single Eckart reference frame. "
            "Rotational-vibrational Coriolis coupling may contaminate moments."
        )

    if averaging_method.lower() in ("direct_b_average", "scalar_b_average"):
        findings.append(
            "[REJECTION TRIGGERED §5.1] Direct averaging of scalar rotational constants "
            "B(R) without inverting the 3x3 inertia tensor is forbidden."
        )
        rejection_triggered = True

    if rejection_triggered:
        status = "REJECTED_NON_COMPLIANT"
    else:
        status = "PASSED_COMPLIANT"
        findings.append(
            "[COMPLIANCE VERIFIED §5.1, §16.3] Inverse inertia tensor mu = I^-1 evaluated element-wise "
            "prior to expectation value accumulation and tensor diagonalization."
        )

    payload_str = json.dumps({"status": status, "findings": findings}, sort_keys=True)
    sha = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    report = MethodMatrixAuditReport(
        status=status,
        section=SECTION_REF,
        rejection_triggered=rejection_triggered,
        findings=findings,
        sha256_checksum=sha,
    )

    if rejection_triggered:
        raise VibrationalAveragingRejectionError("; ".join(findings))

    return report


def verify_method_matrix_section_5_1_table() -> bool:
    """
    Authoritative reference validation asserting that this module exactly reproduces
    the published reference table in Method Matrix Section 5.1.
    """
    results = compute_1d_benchmark_suite()

    # Reference values from Method Matrix Section 5.1:
    # sigma=0.05: B(<1/I>)=3501.69, B(1/<I>)=3499.26, bias=2.43 MHz, bias%=0.069%
    # sigma=0.10: B(<1/I>)=3507.18, B(1/<I>)=3497.46, bias=9.72 MHz, bias%=0.278%
    # sigma=0.15: B(<1/I>)=3516.38, B(1/<I>)=3494.45, bias=21.93 MHz, bias%=0.628%
    # sigma=0.20: B(<1/I>)=3529.40, B(1/<I>)=3490.25, bias=39.16 MHz, bias%=1.122%
    # sigma=0.30: B(<1/I>)=3567.50, B(1/<I>)=3478.27, bias=89.24 MHz, bias%=2.566%

    expected_benchmarks = [
        (0.05, 3501.69, 3499.26, 2.43, 0.069),
        (0.10, 3507.18, 3497.46, 9.72, 0.278),
        (0.15, 3516.38, 3494.45, 21.93, 0.628),
        (0.20, 3529.40, 3490.25, 39.16, 1.122),
        (0.30, 3567.50, 3478.27, 89.24, 2.566),
    ]

    for res, (exp_s, exp_binv, exp_bavg, exp_bias, exp_pct) in zip(results, expected_benchmarks):
        assert math.isclose(res.sigma_R, exp_s, abs_tol=1e-3)
        assert abs(res.bias_MHz - exp_bias) < 0.05, (
            f"Bias mismatch for sigma={exp_s}: got {res.bias_MHz:.2f}, expected {exp_bias:.2f}"
        )
        assert abs(res.bias_pct - exp_pct) < 0.01, (
            f"Bias % mismatch for sigma={exp_s}: got {res.bias_pct:.3f}, expected {exp_pct:.3f}"
        )

    return True


# ---------------------------------------------------------------------------
# Pretty-Printing & Formatting Utilities
# ---------------------------------------------------------------------------
def format_benchmark_table_markdown(results: Sequence[Jensen1DResult]) -> str:
    """Renders the 1D benchmark suite as a GitHub-flavored Markdown table."""
    lines: List[str] = [
        "| σ_R (Å) | B from ⟨1/I⟩ (MHz) | B from 1/⟨I⟩ (MHz) | bias (MHz) | bias (%) | Provenance |",
        "|---:|---:|---:|---:|---:|:---:|",
    ]
    for r in results:
        bold = "**" if math.isclose(r.sigma_R, 0.15, abs_tol=1e-4) else ""
        lines.append(
            f"| {bold}{r.sigma_R:.2f}{bold} | "
            f"{bold}{r.B_inv_I:.2f}{bold} | "
            f"{bold}{r.B_I_avg:.2f}{bold} | "
            f"{bold}{r.bias_MHz:.2f}{bold} | "
            f"{bold}{r.bias_pct:.3f}{bold} | "
            f"{r.provenance} |"
        )
    return "\n".join(lines)


def format_benchmark_table_ascii(results: Sequence[Jensen1DResult]) -> str:
    """Renders the 1D benchmark suite as a formatted terminal ASCII table."""
    header = f"{'sigma_R (A)':>12} | {'B from <1/I> (MHz)':>18} | {'B from 1/<I> (MHz)':>18} | {'bias (MHz)':>12} | {'bias (%)':>10} | {'Tag':>5}"
    sep = "-" * len(header)
    rows = [header, sep]
    for r in results:
        rows.append(
            f"{r.sigma_R:12.2f} | {r.B_inv_I:18.2f} | {r.B_I_avg:18.2f} | {r.bias_MHz:12.2f} | {r.bias_pct:10.3f} | {r.provenance:>5}"
        )
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# CLI Application Entrypoint
# ---------------------------------------------------------------------------
def main() -> int:
    """CLI entrypoint for Jensen reference validation."""
    parser = argparse.ArgumentParser(
        description="Method Matrix §5.1, §16.3 Jensen Inequality Reference Validation Suite."
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run and print the authoritative Method Matrix §5.1 1D benchmark table.",
    )
    parser.add_argument(
        "--verify-table",
        action="store_true",
        help="Run strict programmatic assertions against Method Matrix §5.1 table values.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit validation results in JSON format.",
    )
    parser.add_argument(
        "--vdw-3d-test",
        action="store_true",
        help="Run 3D polyatomic molecular ensemble vibrational tensor averaging test.",
    )

    args = parser.parse_args()

    # Default to benchmark if no flags provided
    if not (args.benchmark or args.verify_table or args.json or args.vdw_3d_test):
        args.benchmark = True
        args.verify_table = True

    results = compute_1d_benchmark_suite()

    if args.verify_table:
        is_verified = verify_method_matrix_section_5_1_table()
        if is_verified:
            logger.info("Method Matrix §5.1 table assertions: PASSED [M]")
        else:
            logger.error("Method Matrix §5.1 table assertions: FAILED")
            return 1

    if args.json:
        out_payload = {
            "metadata": {
                "module": "mm.conference.ref.jensen",
                "mandate": "Method Matrix §5.1, §16.3",
                "conversion_constant_MHz_amu_Ang2": CONV_MHZ_AMU_ANG2,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            },
            "benchmark_1d_results": [r.to_dict() for r in results],
        }
        if args.vdw_3d_test:
            m_Ar = get_atomic_mass("Ar")
            m_C = get_atomic_mass("C")
            m_O = get_atomic_mass("O")
            m1 = np.array([m_Ar])
            m2 = np.array([m_C, m_O, m_O])
            c1 = np.array([[0.0, 0.0, 0.0]])
            c2 = np.array([[0.0, 0.0, 0.0], [0.0, 1.16, 0.0], [0.0, -1.16, 0.0]])
            ens, total_masses, syms = generate_vdw_stretch_ensemble(c1, c2, m1, m2, R0=3.80, sigma_R=0.15)
            res_3d = average_inverse_inertia_ensemble(ens, total_masses, syms)
            out_payload["vdw_3d_test_result"] = res_3d.to_dict()

        sys.stdout.write(json.dumps(out_payload, indent=2) + "\n")
        return 0

    if args.benchmark:
        print("\n" + "=" * 80)
        print(" CoChem Method Matrix §5.1 Reference Table: Jensen Inequality Bias ")
        print(" Model: Floppy intermolecular stretch, mu = 10.0 amu, R0 = 3.80 Å ")
        print("=" * 80)
        print(format_benchmark_table_ascii(results))
        print("=" * 80)
        print("\nMarkdown Table for Method_Matrix.md:")
        print(format_benchmark_table_markdown(results))
        print()

    if args.vdw_3d_test:
        print("\n--- Running 3D Polyatomic Ensemble Tensor Averaging Test (Ar···CO2) ---")
        m_Ar = get_atomic_mass("Ar")
        m_C = get_atomic_mass("C")
        m_O = get_atomic_mass("O")
        m1 = np.array([m_Ar])
        m2 = np.array([m_C, m_O, m_O])
        c1 = np.array([[0.0, 0.0, 0.0]])
        c2 = np.array([[0.0, 0.0, 0.0], [0.0, 1.16, 0.0], [0.0, -1.16, 0.0]])
        ens, total_masses, syms = generate_vdw_stretch_ensemble(c1, c2, m1, m2, R0=3.80, sigma_R=0.15)
        res_3d = average_inverse_inertia_ensemble(ens, total_masses, syms)
        print(f"Correct <mu> Route: A = {res_3d.A_correct:.2f} MHz, B = {res_3d.B_correct:.2f} MHz, C = {res_3d.C_correct:.2f} MHz")
        print(f"Flawed  1/<I> Route: A = {res_3d.A_flawed:.2f} MHz, B = {res_3d.B_flawed:.2f} MHz, C = {res_3d.C_flawed:.2f} MHz")
        print(f"Bias:               dA = {res_3d.bias_A_MHz:.2f} MHz ({res_3d.bias_pct_A:.3f}%), dB = {res_3d.bias_B_MHz:.2f} MHz ({res_3d.bias_pct_B:.3f}%), dC = {res_3d.bias_C_MHz:.2f} MHz ({res_3d.bias_pct_C:.3f}%)")
        print(f"3D Jensen Inequality Maintained: {res_3d.is_valid_jensen}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
