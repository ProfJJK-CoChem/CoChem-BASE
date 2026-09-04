"""
CoChem-TORQ: Phase 4 Multi-Fidelity Spline Router & WKB Tunneling Estimator
===========================================================================
Evaluates ML-generated PES topography to isolate critical topographic nodes
(minima, transition state saddles) and computes WKB quantum tunneling estimates.

Authoritative Standards:
- Method Matrix: Stage 3.0 / 6.0 Spline Fitting & Quantum Tunneling Routing
- Semiclassical Wentzel-Kramers-Brillouin (WKB) Tunneling Formulation
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Sequence

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.optimize import brentq

logger = logging.getLogger("CoChem-TORQ.Slicer")

from cochem_base.core.glossary import (
    AMU_TO_KG,
    HARTREE_TO_CM_INV,
    HARTREE_TO_KCAL_MOL,
    UnitConversionConstants,
)

# Fundamental Conversion Factors
HARTREE_TO_CM1: float = HARTREE_TO_CM_INV
KCAL_MOL_TO_CM1: float = 349.755
PLANCK_HBAR_SI: float = 1.054571817e-34  # J * s
ANGSTROM_TO_M: float = 1.0e-10  # m / Angstrom
JOULE_TO_CM1: float = 5.034116567e22  # cm^-1 / J


def fit_continuous_splines(
    angles_deg: Sequence[float],
    energies_hartree: Sequence[float],
    periodic: bool = True,
) -> Dict[str, Any]:
    """
    Fits continuous 1D periodic cubic splines across discrete angular points.
    Analytically extracts stationary points (minima, maxima/saddles) via root-finding
    on the first derivative V'(theta) = 0 and classifies curvature via V''(theta).
    """
    raw_angles = np.asarray(angles_deg, dtype=np.float64)
    raw_energies = np.asarray(energies_hartree, dtype=np.float64)

    if len(raw_angles) < 4:
        raise ValueError(
            f"At least 4 points required for cubic spline fitting, got {len(raw_angles)}"
        )

    # Sort angles into [0, 360)
    order = np.argsort(raw_angles)
    sorted_deg = raw_angles[order]
    sorted_e = raw_energies[order]

    # Convert to radians
    angles_rad = np.radians(sorted_deg)

    if periodic:
        # Wrap endpoints for smooth periodic spline: append 2*pi point if needed
        if abs(sorted_deg[-1] - 360.0) > 1e-3 and abs(sorted_deg[0] - 0.0) < 1e-3:
            angles_rad = np.append(angles_rad, 2.0 * math.pi)
            sorted_e = np.append(sorted_e, sorted_e[0])
            sorted_deg = np.append(sorted_deg, 360.0)

        spline = CubicSpline(angles_rad, sorted_e, bc_type="periodic")
    else:
        spline = CubicSpline(angles_rad, sorted_e)

    # First and second derivatives
    d_spline = spline.derivative(nu=1)
    d2_spline = spline.derivative(nu=2)

    # Dense sampling to locate sign changes of derivative
    dense_rad = np.linspace(0.0, 2.0 * math.pi, 1000)
    d_vals = d_spline(dense_rad)

    critical_rads: List[float] = []
    for i in range(len(dense_rad) - 1):
        if d_vals[i] * d_vals[i + 1] <= 0.0:
            try:
                root = brentq(d_spline, dense_rad[i], dense_rad[i + 1])
                # Check uniqueness (within 1e-3 rad)
                if not any(abs(root - cr) < 1e-3 for cr in critical_rads):
                    critical_rads.append(float(root))
            except (ValueError, RuntimeError) as _e:
                logger.debug(f"Ignored exception: {_e}")

    critical_rads.sort()
    stationary_points: List[Dict[str, Any]] = []

    for rad in critical_rads:
        deg = math.degrees(rad) % 360.0
        e_hartree = float(spline(rad))
        curvature = float(d2_spline(rad))

        if curvature > 0:
            node_type = "MINIMUM"
        elif curvature < 0:
            node_type = "MAXIMUM"
        else:
            node_type = "INFLECTION"

        stationary_points.append(
            {
                "angle_deg": round(deg, 3),
                "angle_rad": round(rad, 5),
                "energy_hartree": e_hartree,
                "energy_kcal_mol": e_hartree * HARTREE_TO_KCAL_MOL,
                "energy_cm1": e_hartree * HARTREE_TO_CM1,
                "curvature": curvature,
                "type": node_type,
            }
        )

    # Identify global minimum
    minima = [p for p in stationary_points if p["type"] == "MINIMUM"]
    maxima = [p for p in stationary_points if p["type"] == "MAXIMUM"]

    if minima:
        global_min = min(minima, key=lambda p: p["energy_hartree"])
    elif stationary_points:
        global_min = min(stationary_points, key=lambda p: p["energy_hartree"])
    else:
        # Fallback to discrete min
        min_idx = int(np.argmin(sorted_e))
        global_min = {
            "angle_deg": float(sorted_deg[min_idx]),
            "angle_rad": float(angles_rad[min_idx]),
            "energy_hartree": float(sorted_e[min_idx]),
            "energy_kcal_mol": float(sorted_e[min_idx] * HARTREE_TO_KCAL_MOL),
            "energy_cm1": float(sorted_e[min_idx] * HARTREE_TO_CM1),
            "curvature": 1.0,
            "type": "MINIMUM",
        }

    # Relative energies relative to global min
    e_ref = global_min["energy_hartree"]
    for p in stationary_points:
        p["rel_energy_hartree"] = p["energy_hartree"] - e_ref
        p["rel_energy_kcal_mol"] = p["rel_energy_hartree"] * HARTREE_TO_KCAL_MOL
        p["rel_energy_cm1"] = p["rel_energy_hartree"] * HARTREE_TO_CM1

    max_barrier_kcal = max([p["rel_energy_kcal_mol"] for p in maxima]) if maxima else 0.0
    max_barrier_cm1 = max([p["rel_energy_cm1"] for p in maxima]) if maxima else 0.0

    logger.info(
        "Spline fitted: %d stationary points found (%d minima, %d maxima, max barrier = %.2f kcal/mol)",
        len(stationary_points),
        len(minima),
        len(maxima),
        max_barrier_kcal,
    )

    return {
        "spline": spline,
        "stationary_points": stationary_points,
        "global_minimum": global_min,
        "minima": minima,
        "maxima": maxima,
        "max_barrier_kcal_mol": max_barrier_kcal,
        "max_barrier_cm1": max_barrier_cm1,
    }


def wkb_tunneling_estimator(
    rotor_type: str,
    barrier_height_cm1: float,
    reduced_moment_inertia_amu_ang2: float = 3.0,
    periodicity: int = 3,
) -> Dict[str, Any]:
    """
    Applies semiclassical Wentzel-Kramers-Brillouin (WKB) estimation to evaluate
    the quantum tunneling probability and torsional tunneling splitting for light rotors.
    """
    clean_rotor = rotor_type.strip().upper()
    is_light_rotor = any(
        group in clean_rotor for group in ["CH3", "-CH3", "OH", "-OH", "NH2", "-NH2"]
    )

    # Moment of inertia in SI units (kg * m^2)
    i_red_si = reduced_moment_inertia_amu_ang2 * AMU_TO_KG * (ANGSTROM_TO_M**2)

    # Barrier height V0 in Joules
    v0_joules = barrier_height_cm1 / JOULE_TO_CM1

    # Torsional harmonic frequency estimate omega_0 = n * sqrt(V0 / (2 * I_red))
    if i_red_si > 0 and v0_joules > 0:
        omega_0 = periodicity * math.sqrt(v0_joules / (2.0 * i_red_si))
        # Zero-point energy approximation: E_0 = 0.5 * hbar * omega_0
        e0_joules = 0.5 * PLANCK_HBAR_SI * omega_0

        # Semiclassical WKB integral for V(theta) = V0/2 * (1 - cos(n*theta))
        # Integral approx: S_wkb = 2 * (8 * sqrt(2 * I_red * V0) / (n * hbar)) * (1 - E0/V0)
        eff_barrier = max(1e-25, v0_joules - e0_joules)
        action = (4.0 / (periodicity * PLANCK_HBAR_SI)) * math.sqrt(2.0 * i_red_si * eff_barrier)
        action = min(action, 100.0)  # Bound to prevent underflow

        tunneling_probability = math.exp(-2.0 * action)
        # Tunneling splitting in Hz: Delta_nu ~ (omega_0 / pi) * exp(-action)
        tunneling_splitting_hz = (omega_0 / math.pi) * math.exp(-action)
        tunneling_splitting_mhz = tunneling_splitting_hz / 1.0e6
    else:
        tunneling_probability = 0.0
        tunneling_splitting_mhz = 0.0

    # Quantum treatment required if splitting is spectroscopically observable (> 0.01 MHz)
    # or if rotor is light and barrier is below typical tunneling threshold (~1200 cm^-1 for OH, ~1000 cm^-1 for CH3)
    quantum_required = is_light_rotor and (
        tunneling_splitting_mhz > 0.01 or barrier_height_cm1 < 1200.0
    )

    logger.info(
        "WKB tunneling estimate for %s: barrier=%.1f cm^-1, P_tunnel=%.2e, Splitting=%.4f MHz, QuantumRequired=%s",
        rotor_type,
        barrier_height_cm1,
        tunneling_probability,
        tunneling_splitting_mhz,
        quantum_required,
    )

    return {
        "rotor_type": rotor_type,
        "is_light_rotor": is_light_rotor,
        "barrier_height_cm1": barrier_height_cm1,
        "reduced_moment_inertia_amu_ang2": reduced_moment_inertia_amu_ang2,
        "tunneling_probability": tunneling_probability,
        "tunneling_splitting_mhz": tunneling_splitting_mhz,
        "quantum_treatment_required": quantum_required,
    }
