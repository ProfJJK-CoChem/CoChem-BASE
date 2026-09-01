"""CoChem-GEOM: Precision Geometric Evaluation and Structural Metric Suite.
========================================================================
Implements TorchMetrics-compliant evaluation metrics, pure functional SE(3)
invariant alignment (Kabsch algorithm), Conformer Coverage (COV), Average
Minimum RMSD (AMR), Energy MAE/RMSE, Relative Energy Ranking, Boltzmann-Weighted
Energies, Force Error Metrics, Spectroscopic Rotational Constants (A, B, C),
Inertial Defects, and Internal Molecular Coordinates (Bonds, Angles, Dihedrals).

Authoritative Standards & Directives:
- Method Matrix v4.1: Conformer Ensemble Metrics & Physical Observables
- TorchMetrics v1.0+: Modular Metric Interface with DDP State Reduction & Pure Tensor Ops
- Mendeleev Library Mandate: All atomic/isotopic masses dynamically resolved via `mendeleev`
- SE(3) Equivariance & Invariance: Strict separation of spatial pos [N, 3] from invariant features
- State Immutability: Pure functional geometric transformations (pos_new = pos + shift, never in-place)
- Dynamic Path Resolution: Cross-platform dynamic pathing via `pathlib` and environment variables
- Provenance Tags: [M] Measured/Theoretical, [D] Derived/Calculated, [E] Expert Estimate
- Strict Zero-Mock Policy: 100% authentic physical tensor mathematics and real execution
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from mendeleev import element
import numpy as np
import torch
import torch.nn as nn
from torchmetrics import Metric

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. Fundamental Physical Constants & Conversion Factors (CODATA 2018/2022)
# ==============================================================================

SPEED_OF_LIGHT_M_S: float = 299792458.0
"""Speed of light in vacuum in meters per second (exact) [M]."""

PLANCK_CONSTANT_J_S: float = 6.62607015e-34
"""Planck constant in Joule seconds (exact) [M]."""

BOLTZMANN_CONSTANT_J_K: float = 1.380649e-23
"""Boltzmann constant in Joules per Kelvin (exact) [M]."""

BOLTZMANN_CONSTANT_EV_K: float = 8.617333262145e-5
"""Boltzmann constant in electron-volts per Kelvin [D]."""

ELEMENTARY_CHARGE_C: float = 1.602176634e-19
"""Elementary charge in Coulombs (exact) [M]."""

AVOGADRO_CONSTANT_MOL: float = 6.02214076e23
"""Avogadro constant per mole (exact) [M]."""

ATOMIC_MASS_UNIT_KG: float = 1.66053906660e-27
"""Unified atomic mass unit / Dalton in kilograms [M]."""

BOHR_RADIUS_ANGSTROM: float = 0.529177210903
"""Bohr radius in Angstroms [M]."""

HARTREE_TO_EV: float = 27.211386245988
"""Conversion factor from Hartree to electron-volts [D]."""

EV_TO_HARTREE: float = 1.0 / HARTREE_TO_EV
"""Conversion factor from electron-volts to Hartree [D]."""

HARTREE_TO_KCAL_MOL: float = 627.5094740631
"""Conversion factor from Hartree to kilocalories per mole [D]."""

KCAL_MOL_TO_HARTREE: float = 1.0 / HARTREE_TO_KCAL_MOL
"""Conversion factor from kilocalories per mole to Hartree [D]."""

KCAL_MOL_TO_EV: float = 0.04336411530877
"""Conversion factor from kilocalories per mole to electron-volts [D]."""

EV_TO_KCAL_MOL: float = 1.0 / KCAL_MOL_TO_EV
"""Conversion factor from electron-volts to kilocalories per mole [D]."""

HARTREE_TO_KJ_MOL: float = 2625.4996394799
"""Conversion factor from Hartree to kilojoules per mole [D]."""

EV_TO_KJ_MOL: float = HARTREE_TO_KJ_MOL / HARTREE_TO_EV
"""Conversion factor from electron-volts to kilojoules per mole [D]."""

EV_TO_CM_MINUS_ONE: float = 8065.54429
"""Conversion factor from electron-volts to wavenumbers (cm^-1) [D]."""

ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ: float = 505379.008784
"""Spectroscopic rotational constant conversion factor in MHz * u * Angstrom^2 [D]."""

STANDARD_TEMPERATURE_K: float = 298.15
"""Standard ambient reference temperature in Kelvin (25 deg C) [M]."""

DEFAULT_TEMPERATURE_K: float = 298.15
"""Default thermodynamic temperature in Kelvin for Boltzmann weighting [M]."""

DEFAULT_COV_THRESHOLD: float = 0.5
"""Default RMSD coverage threshold in Angstroms for conformer ensemble matching [E]."""

DEFAULT_AMR_THRESHOLD: float = 0.5
"""Default RMSD tolerance in Angstroms for average minimum RMSD evaluation [E]."""


def convert_energy(
    value: Union[float, torch.Tensor],
    from_unit: str = "ev",
    to_unit: str = "ev",
) -> Union[float, torch.Tensor]:
    """Convert energy values between supported physical units [D].

    Supported units: 'ev', 'hartree', 'kcal_mol', 'kj_mol'.
    """
    from_u = from_unit.lower().replace("/", "_").replace("-", "_")
    to_u = to_unit.lower().replace("/", "_").replace("-", "_")

    if from_u == to_u:
        return value

    # Direct conversion dictionary for exact numerical precision
    conversion_factors = {
        ("ev", "hartree"): EV_TO_HARTREE,
        ("hartree", "ev"): HARTREE_TO_EV,
        ("hartree", "kcal_mol"): HARTREE_TO_KCAL_MOL,
        ("kcal_mol", "hartree"): KCAL_MOL_TO_HARTREE,
        ("hartree", "kj_mol"): HARTREE_TO_KJ_MOL,
        ("kj_mol", "hartree"): 1.0 / HARTREE_TO_KJ_MOL,
        ("ev", "kcal_mol"): EV_TO_KCAL_MOL,
        ("kcal_mol", "ev"): KCAL_MOL_TO_EV,
        ("ev", "kj_mol"): EV_TO_KJ_MOL,
        ("kj_mol", "ev"): 1.0 / EV_TO_KJ_MOL,
        ("kcal_mol", "kj_mol"): 4.184,
        ("kj_mol", "kcal_mol"): 1.0 / 4.184,
    }

    if (from_u, to_u) in conversion_factors:
        return value * conversion_factors[(from_u, to_u)]

    # Fallback via eV
    if from_u == "ev":
        ev_val = value
    elif from_u == "hartree":
        ev_val = value * HARTREE_TO_EV
    elif from_u == "kcal_mol":
        ev_val = value * KCAL_MOL_TO_EV
    elif from_u == "kj_mol":
        ev_val = value * (1.0 / EV_TO_KJ_MOL)
    else:
        raise ValueError(f"Unsupported input energy unit: '{from_unit}'")

    if to_u == "ev":
        return ev_val
    elif to_u == "hartree":
        return ev_val * EV_TO_HARTREE
    elif to_u == "kcal_mol":
        return ev_val * EV_TO_KCAL_MOL
    elif to_u == "kj_mol":
        return ev_val * EV_TO_KJ_MOL
    else:
        raise ValueError(f"Unsupported target energy unit: '{to_unit}'")


# ==============================================================================
# 2. Dynamic Mendeleev Mass and Property Resolution Functions
# ==============================================================================

def get_atomic_mass(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query standard atomic weight from mendeleev [M]."""
    el = element(symbol_or_z)
    if el.atomic_weight is not None:
        return float(el.atomic_weight)
    if el.isotopes:
        return float(el.isotopes[0].mass)
    if el.mass is not None:
        return float(el.mass)
    raise ValueError(f"Standard atomic mass not found for element '{symbol_or_z}'")


def get_monoisotopic_mass(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query exact mass of most abundant natural isotope from mendeleev [M]."""
    el = element(symbol_or_z)
    if el.isotopes:
        most_abundant = max(
            el.isotopes,
            key=lambda iso: (iso.abundance if iso.abundance is not None else 0.0),
        )
        if most_abundant.mass is not None:
            return float(most_abundant.mass)
    if el.atomic_weight is not None:
        return float(el.atomic_weight)
    raise ValueError(f"Monoisotopic mass not found for element '{symbol_or_z}'")


def get_atomic_masses(atomic_numbers: torch.Tensor) -> torch.Tensor:
    """Dynamically query atomic masses for a tensor of atomic numbers [M]."""
    masses: List[float] = []
    for z_val in atomic_numbers.view(-1).tolist():
        masses.append(get_atomic_mass(int(z_val)))
    return torch.tensor(masses, dtype=torch.float32, device=atomic_numbers.device).view(atomic_numbers.shape)


# ==============================================================================
# 3. Pure Functional Kabsch Algorithm & SE(3) Invariant Operations
# ==============================================================================

def kabsch_rotation(
    p_centered: torch.Tensor,
    q_centered: torch.Tensor,
    weights: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """Compute optimal 3D orthogonal rotation matrix R (SO(3)) minimizing weighted RMSD [D].

    Parameters
    ----------
    p_centered : torch.Tensor
        Centered reference coordinate tensor of shape (..., N, 3).
    q_centered : torch.Tensor
        Centered target coordinate tensor of shape (..., N, 3).
    weights : Optional[torch.Tensor]
        Optional per-atom positive weights of shape (..., N) or (N,).

    Returns
    -------
    torch.Tensor
        Optimal rotation matrix R of shape (..., 3, 3) such that q @ R.mT aligns to p.
    """
    if weights is not None:
        w = weights.unsqueeze(-1) if weights.dim() == p_centered.dim() - 1 else weights
        w = w / torch.sum(w, dim=-2, keepdim=True)
        h = torch.matmul(q_centered.transpose(-1, -2), w * p_centered)
    else:
        h = torch.matmul(q_centered.transpose(-1, -2), p_centered)

    u, s, vt = torch.linalg.svd(h)
    v = vt.transpose(-1, -2)

    # Reflection correction: ensure det(R) = +1 (proper rotation in SO(3))
    det = torch.det(torch.matmul(v, u.transpose(-1, -2)))
    diag = torch.ones_like(det).unsqueeze(-1).repeat_interleave(3, dim=-1)
    diag[..., 2] = torch.where(det < 0.0, -1.0, 1.0)

    r = torch.matmul(torch.matmul(v, torch.diag_embed(diag)), u.transpose(-1, -2))
    return r


def kabsch_align(
    p_ref: torch.Tensor,
    q_target: torch.Tensor,
    weights: Optional[torch.Tensor] = None,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Align target coordinates q to reference coordinates p via Kabsch algorithm [D].

    Pure functional and state-immutable: never mutates input tensors.

    Parameters
    ----------
    p_ref : torch.Tensor
        Reference Cartesian coordinate tensor of shape (..., N, 3).
    q_target : torch.Tensor
        Target Cartesian coordinate tensor of shape (..., N, 3).
    weights : Optional[torch.Tensor]
        Optional per-atom weights of shape (..., N) or (N,).

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]
        - q_aligned: Aligned target coordinates (..., N, 3)
        - R: Optimal rotation matrix (..., 3, 3)
        - t: Translation vector (..., 3)
        - rmsd: Root-mean-square deviation (...,) in Angstroms [D]
    """
    if weights is not None:
        w = weights.unsqueeze(-1) if weights.dim() == p_ref.dim() - 1 else weights
        w_sum = torch.sum(w, dim=-2, keepdim=True) + 1e-12
        p_centroid = torch.sum(p_ref * w, dim=-2, keepdim=True) / w_sum
        q_centroid = torch.sum(q_target * w, dim=-2, keepdim=True) / w_sum
    else:
        p_centroid = torch.mean(p_ref, dim=-2, keepdim=True)
        q_centroid = torch.mean(q_target, dim=-2, keepdim=True)

    p_c = p_ref - p_centroid
    q_c = q_target - q_centroid

    r = kabsch_rotation(p_c, q_c, weights=weights)

    # Pure immutable transformation: q_aligned = q_c @ R.mT + p_centroid
    q_aligned = torch.matmul(q_c, r.transpose(-1, -2)) + p_centroid
    t = p_centroid.squeeze(-2) - torch.matmul(q_centroid.squeeze(-2), r.transpose(-1, -2))

    diff = p_ref - q_aligned
    if weights is not None:
        w_norm = weights / torch.sum(weights, dim=-1, keepdim=True)
        sq_dist = torch.sum(diff**2, dim=-1)
        mean_sq = torch.sum(sq_dist * w_norm, dim=-1)
    else:
        mean_sq = torch.mean(torch.sum(diff**2, dim=-1), dim=-1)

    rmsd = torch.sqrt(torch.clamp(mean_sq, min=0.0))
    return q_aligned, r, t, rmsd


def compute_rmsd(
    p_ref: torch.Tensor,
    q_target: torch.Tensor,
    align: bool = True,
    weights: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """Compute Root-Mean-Square Deviation (RMSD) between coordinates [D].

    Parameters
    ----------
    p_ref : torch.Tensor
        Reference Cartesian coordinates of shape (..., N, 3).
    q_target : torch.Tensor
        Target Cartesian coordinates of shape (..., N, 3).
    align : bool
        If True, applies Kabsch optimal SE(3) superposition prior to RMSD calculation.
    weights : Optional[torch.Tensor]
        Optional atom weights (e.g., atomic masses for mass-weighted RMSD).

    Returns
    -------
    torch.Tensor
        RMSD tensor of shape (...,) in Angstroms [D].
    """
    if align:
        _, _, _, rmsd = kabsch_align(p_ref, q_target, weights=weights)
        return rmsd

    diff = p_ref - q_target
    if weights is not None:
        w_norm = weights / torch.sum(weights, dim=-1, keepdim=True)
        sq_dist = torch.sum(diff**2, dim=-1)
        mean_sq = torch.sum(sq_dist * w_norm, dim=-1)
    else:
        mean_sq = torch.mean(torch.sum(diff**2, dim=-1), dim=-1)
    return torch.sqrt(torch.clamp(mean_sq, min=0.0))


def pairwise_conformer_rmsd(
    ref_conformers: torch.Tensor,
    pred_conformers: torch.Tensor,
    align: bool = True,
) -> torch.Tensor:
    """Compute all-pairs RMSD matrix between reference and predicted conformer ensembles [D].

    Parameters
    ----------
    ref_conformers : torch.Tensor
        Reference conformers tensor of shape (M, N, 3).
    pred_conformers : torch.Tensor
        Predicted conformers tensor of shape (K, N, 3).
    align : bool
        Whether to perform Kabsch alignment for each pair.

    Returns
    -------
    torch.Tensor
        Pairwise RMSD matrix of shape (M, K) in Angstroms [D].
    """
    if ref_conformers.dim() != 3 or pred_conformers.dim() != 3:
        raise ValueError(
            f"Expected 3D tensors of shape (M, N, 3) and (K, N, 3), got "
            f"{ref_conformers.shape} and {pred_conformers.shape}"
        )
    if ref_conformers.shape[1] != pred_conformers.shape[1]:
        raise ValueError(
            f"Atom count mismatch: ref has {ref_conformers.shape[1]}, "
            f"pred has {pred_conformers.shape[1]}"
        )
    m = ref_conformers.shape[0]
    k = pred_conformers.shape[0]
    n = ref_conformers.shape[1]

    if align:
        from cochem_geom.eval.alignment import kabsch_alignment
        ref_expanded = ref_conformers.unsqueeze(1).expand(m, k, n, 3)
        pred_expanded = pred_conformers.unsqueeze(0).expand(m, k, n, 3)
        _, rmsd_matrix = kabsch_alignment(pred_expanded, ref_expanded)
        return rmsd_matrix
    else:
        ref_expanded = ref_conformers.unsqueeze(1).expand(m, k, n, 3)
        pred_expanded = pred_conformers.unsqueeze(0).expand(m, k, n, 3)
        diff = pred_expanded - ref_expanded
        mean_sq = torch.mean(torch.sum(diff**2, dim=-1), dim=-1)
        return torch.sqrt(torch.clamp(mean_sq, min=0.0))


def calculate_ensemble_metrics(
    generated: torch.Tensor,
    reference: torch.Tensor,
    threshold: float = 1.25,  # [E]
) -> Tuple[float, float]:
    """Calculates Coverage (COV) and Average Minimum RMSD (AMR) for a conformer ensemble [D].

    Parameters
    ----------
    generated : torch.Tensor
        Generated conformer ensemble tensor of shape (N_gen, N_atoms, 3) [D].
    reference : torch.Tensor
        Ground-truth reference conformer ensemble tensor of shape (N_ref, N_atoms, 3) [D].
    threshold : float, default=1.25
        Strict tolerance radius delta in Angstroms for Conformer Coverage [E].

    Returns
    -------
    Tuple[float, float]
        - cov: Conformer Coverage percentage (0.0 to 100.0) [D].
        - amr: Average Minimum RMSD in Angstroms [D].

    Raises
    ------
    ValueError
        If inputs are not 3D tensors, do not have 3 spatial dimensions,
        contain 0 conformers or 0 atoms, or have mismatching atom counts.
    """
    if threshold < 0.0:
        raise ValueError(f"Threshold must be non-negative, got {threshold}")

    if generated.dim() != 3 or reference.dim() != 3:
        raise ValueError(
            f"Expected 3D tensors of shape (N_gen, N_atoms, 3) and (N_ref, N_atoms, 3), "
            f"got generated dim {generated.dim()} (shape {generated.shape}) and "
            f"reference dim {reference.dim()} (shape {reference.shape})"
        )

    if generated.shape[-1] != 3 or reference.shape[-1] != 3:
        raise ValueError(
            f"Expected 3D Cartesian coordinates with shape (..., 3), "
            f"got generated shape {generated.shape} and reference shape {reference.shape}"
        )

    if generated.shape[0] < 1 or reference.shape[0] < 1:
        raise ValueError(
            f"Ensembles must contain at least 1 conformer, "
            f"got generated count {generated.shape[0]} and reference count {reference.shape[0]}"
        )

    if generated.shape[1] < 1 or reference.shape[1] < 1:
        raise ValueError(
            f"Number of atoms must be at least 1, "
            f"got generated atoms {generated.shape[1]} and reference atoms {reference.shape[1]}"
        )

    if generated.shape[1] != reference.shape[1]:
        raise ValueError(
            f"Atom count mismatch: generated has {generated.shape[1]} atoms, "
            f"reference has {reference.shape[1]} atoms"
        )

    # Dynamic dtype promotion and device synchronization for cross-precision support [D]
    common_dtype = torch.promote_types(generated.dtype, reference.dtype)
    gen = generated.to(dtype=common_dtype)
    ref = reference.to(dtype=common_dtype, device=gen.device)

    try:
        from eval.alignment import kabsch_alignment
    except ImportError:
        from cochem_geom.eval.alignment import kabsch_alignment

    n_gen = gen.shape[0]
    n_ref = ref.shape[0]
    n_atoms = ref.shape[1]

    # Dense bipartite broadcasting: [N_ref, N_gen, N_atoms, 3] avoiding sequential loops [E]
    ref_expanded = ref.unsqueeze(1).expand(n_ref, n_gen, n_atoms, 3)
    gen_expanded = gen.unsqueeze(0).expand(n_ref, n_gen, n_atoms, 3)

    _, rmsd_matrix = kabsch_alignment(gen_expanded, ref_expanded)  # Shape [N_ref, N_gen]

    # For each reference conformer, find the minimum RMSD across all generated conformers [D]
    min_rmsd_per_ref = torch.min(rmsd_matrix, dim=1).values  # Shape [N_ref]

    # Conformer Coverage (COV): Percentage of ground-truth conformers within tolerance radius threshold [D]
    cov = (torch.sum(min_rmsd_per_ref <= threshold).float() / float(n_ref)) * 100.0

    # Average Minimum RMSD (AMR): Arithmetic mean of minimum RMSDs across all reference conformers [D]
    amr = torch.mean(min_rmsd_per_ref)

    return float(cov.item()), float(amr.item())



def compute_conformer_coverage(
    ref_conformers: torch.Tensor,
    pred_conformers: torch.Tensor,
    threshold: float = DEFAULT_COV_THRESHOLD,
    align: bool = True,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Compute Conformer Coverage Recall (COV-R) and Precision (COV-P) [D].

    - COV-R: Percentage of reference conformers matched by at least one prediction within threshold.
    - COV-P: Percentage of predicted conformers matched by at least one reference within threshold.

    Parameters
    ----------
    ref_conformers : torch.Tensor
        Reference conformer ensemble of shape (M, N, 3).
    pred_conformers : torch.Tensor
        Predicted conformer ensemble of shape (K, N, 3).
    threshold : float
        RMSD cutoff threshold in Angstroms [E].
    align : bool
        Whether to apply Kabsch alignment.

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor]
        (cov_recall_percent, cov_precision_percent)
    """
    dist_matrix = pairwise_conformer_rmsd(ref_conformers, pred_conformers, align=align)

    min_rmsd_ref = torch.min(dist_matrix, dim=1).values  # (M,)
    min_rmsd_pred = torch.min(dist_matrix, dim=0).values  # (K,)

    cov_recall = (torch.sum(min_rmsd_ref <= threshold).float() / float(dist_matrix.shape[0])) * 100.0
    cov_precision = (torch.sum(min_rmsd_pred <= threshold).float() / float(dist_matrix.shape[1])) * 100.0

    return cov_recall, cov_precision


def compute_average_minimum_rmsd(
    ref_conformers: torch.Tensor,
    pred_conformers: torch.Tensor,
    align: bool = True,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Compute Average Minimum RMSD Recall (AMR-R) and Precision (AMR-P) [D].

    - AMR-R: Mean minimum RMSD over all reference conformers to the prediction ensemble.
    - AMR-P: Mean minimum RMSD over all predicted conformers to the reference ensemble.

    Parameters
    ----------
    ref_conformers : torch.Tensor
        Reference conformer ensemble of shape (M, N, 3).
    pred_conformers : torch.Tensor
        Predicted conformer ensemble of shape (K, N, 3).
    align : bool
        Whether to apply Kabsch alignment.

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor]
        (amr_recall_angstrom, amr_precision_angstrom)
    """
    dist_matrix = pairwise_conformer_rmsd(ref_conformers, pred_conformers, align=align)

    min_rmsd_ref = torch.min(dist_matrix, dim=1).values  # (M,)
    min_rmsd_pred = torch.min(dist_matrix, dim=0).values  # (K,)

    amr_recall = torch.mean(min_rmsd_ref)
    amr_precision = torch.mean(min_rmsd_pred)

    return amr_recall, amr_precision


# ==============================================================================
# 4. Spectroscopic Observables: Moments of Inertia & Rotational Constants
# ==============================================================================

def compute_moments_of_inertia(
    positions: torch.Tensor,
    atomic_numbers: torch.Tensor,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Compute principal moments of inertia and rotational constants (A >= B >= C) [D].

    Calculates center of mass using dynamic Mendeleev atomic masses, forms the
    moment of inertia tensor, diagonalizes to obtain I_a <= I_b <= I_c in u*A^2,
    and derives spectroscopic rotational constants A >= B >= C in MHz.

    Parameters
    ----------
    positions : torch.Tensor
        Cartesian coordinate tensor of shape (..., N, 3) in Angstroms.
    atomic_numbers : torch.Tensor
        Atomic numbers Z of shape (..., N) or (N,).

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor]
        - principal_moments: (..., 3) sorted (I_a, I_b, I_c) in u * Angstrom^2 [D]
        - rotational_constants_mhz: (..., 3) sorted (A, B, C) in MHz [D]
    """
    masses = get_atomic_masses(atomic_numbers)  # (..., N)
    w_mass = masses.unsqueeze(-1)  # (..., N, 1)
    total_mass = torch.sum(w_mass, dim=-2, keepdim=True) + 1e-12

    # Center of mass
    com = torch.sum(positions * w_mass, dim=-2, keepdim=True) / total_mass
    r_com = positions - com  # (..., N, 3)

    x = r_com[..., 0]
    y = r_com[..., 1]
    z = r_com[..., 2]

    # Inertia tensor components
    i_xx = torch.sum(masses * (y**2 + z**2), dim=-1)
    i_yy = torch.sum(masses * (x**2 + z**2), dim=-1)
    i_zz = torch.sum(masses * (x**2 + y**2), dim=-1)
    i_xy = -torch.sum(masses * x * y, dim=-1)
    i_xz = -torch.sum(masses * x * z, dim=-1)
    i_yz = -torch.sum(masses * y * z, dim=-1)

    # Assemble 3x3 inertia tensor
    row1 = torch.stack([i_xx, i_xy, i_xz], dim=-1)
    row2 = torch.stack([i_xy, i_yy, i_yz], dim=-1)
    row3 = torch.stack([i_xz, i_yz, i_zz], dim=-1)
    inertia_tensor = torch.stack([row1, row2, row3], dim=-2)  # (..., 3, 3)

    # Eigenvalues (principal moments of inertia)
    eigvals = torch.linalg.eigvalsh(inertia_tensor)  # (..., 3) sorted ascending
    principal_moments = torch.clamp(eigvals, min=1e-8)

    # Rotational constants: B_rot = 505379.008784 / I_p in MHz
    rotational_constants = ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / principal_moments
    # Principal moments I_a <= I_b <= I_c -> Rotational constants A >= B >= C

    return principal_moments, rotational_constants


def compute_inertial_defect(
    positions: torch.Tensor,
    atomic_numbers: torch.Tensor,
) -> torch.Tensor:
    """Compute the planar inertial defect Delta I = I_c - I_a - I_b [D].

    For strictly planar molecules, Delta I ~ 0.0 in the rigid rotor limit [M].

    Parameters
    ----------
    positions : torch.Tensor
        Cartesian coordinates (..., N, 3) in Angstroms.
    atomic_numbers : torch.Tensor
        Atomic numbers Z (..., N) or (N,).

    Returns
    -------
    torch.Tensor
        Planar inertial defect tensor (...,) in u * Angstrom^2 [D].
    """
    moments, _ = compute_moments_of_inertia(positions, atomic_numbers)
    i_a = moments[..., 0]
    i_b = moments[..., 1]
    i_c = moments[..., 2]
    return i_c - i_a - i_b


# ==============================================================================
# 5. Internal Molecular Coordinates: Bonds, Angles, and Dihedrals
# ==============================================================================

def compute_bond_lengths(
    positions: torch.Tensor,
    bonds: torch.Tensor,
) -> torch.Tensor:
    """Compute bond lengths for specified atom pairs [D].

    Parameters
    ----------
    positions : torch.Tensor
        Cartesian coordinates (N, 3) or (B, N, 3).
    bonds : torch.Tensor
        Bond index pairs tensor (E, 2).

    Returns
    -------
    torch.Tensor
        Bond lengths (E,) or (B, E) in Angstroms [D].
    """
    idx_i = bonds[:, 0]
    idx_j = bonds[:, 1]
    pos_i = positions[..., idx_i, :]
    pos_j = positions[..., idx_j, :]
    return torch.sqrt(torch.clamp(torch.sum((pos_i - pos_j) ** 2, dim=-1), min=0.0))


def compute_bond_angles(
    positions: torch.Tensor,
    angles: torch.Tensor,
) -> torch.Tensor:
    """Compute valence bond angles (i - j - k) in degrees [D].

    Parameters
    ----------
    positions : torch.Tensor
        Cartesian coordinates (N, 3) or (B, N, 3).
    angles : torch.Tensor
        Angle triplets index tensor (A, 3) where j is the central vertex atom.

    Returns
    -------
    torch.Tensor
        Valence bond angles in degrees (A,) or (B, A) [D].
    """
    idx_i = angles[:, 0]
    idx_j = angles[:, 1]  # Central vertex
    idx_k = angles[:, 2]

    pos_i = positions[..., idx_i, :]
    pos_j = positions[..., idx_j, :]
    pos_k = positions[..., idx_k, :]

    v_ji = pos_i - pos_j
    v_jk = pos_k - pos_j

    v_ji_u = v_ji / (torch.norm(v_ji, dim=-1, keepdim=True) + 1e-12)
    v_jk_u = v_jk / (torch.norm(v_jk, dim=-1, keepdim=True) + 1e-12)

    dot_prod = torch.sum(v_ji_u * v_jk_u, dim=-1)
    cos_theta = torch.clamp(dot_prod, -1.0 + 1e-7, 1.0 - 1e-7)
    return torch.rad2deg(torch.acos(cos_theta))


def compute_dihedral_angles(
    positions: torch.Tensor,
    dihedrals: torch.Tensor,
) -> torch.Tensor:
    """Compute dihedral / torsion angles (i - j - k - l) in degrees [D].

    Parameters
    ----------
    positions : torch.Tensor
        Cartesian coordinates (N, 3) or (B, N, 3).
    dihedrals : torch.Tensor
        Dihedral quadruplet index tensor (D, 4).

    Returns
    -------
    torch.Tensor
        Dihedral angles in degrees (D,) or (B, D) in range [-180, 180] [D].
    """
    p0 = positions[..., dihedrals[:, 0], :]
    p1 = positions[..., dihedrals[:, 1], :]
    p2 = positions[..., dihedrals[:, 2], :]
    p3 = positions[..., dihedrals[:, 3], :]

    b0 = -1.0 * (p1 - p0)
    b1 = p2 - p1
    b2 = p3 - p2

    b1_norm = b1 / (torch.norm(b1, dim=-1, keepdim=True) + 1e-12)

    v = b0 - torch.sum(b0 * b1_norm, dim=-1, keepdim=True) * b1_norm
    w = b2 - torch.sum(b2 * b1_norm, dim=-1, keepdim=True) * b1_norm

    x = torch.sum(v * w, dim=-1)
    y = torch.sum(torch.cross(b1_norm, v, dim=-1) * w, dim=-1)

    return torch.rad2deg(torch.atan2(y, x))


# ==============================================================================
# 6. TorchMetrics Base Metric Implementations
# ==============================================================================

class ConformerCoverage(Metric):
    """TorchMetrics implementation for Conformer Coverage (COV-R and COV-P) [D].

    Computes percentage of reference conformers covered by generated samples (Recall)
    and percentage of generated conformers matching true references (Precision)
    within a defined RMSD threshold.
    """

    full_state_update: bool = False

    def __init__(
        self,
        threshold: float = DEFAULT_COV_THRESHOLD,
        align: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.threshold = threshold
        self.align = align

        self.add_state("total_ref_covered", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_ref_count", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_pred_covered", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_pred_count", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        ref_conformers: Union[torch.Tensor, Sequence[torch.Tensor]],
        pred_conformers: Union[torch.Tensor, Sequence[torch.Tensor]],
    ) -> None:
        """Update coverage statistics with conformer ensembles.

        Parameters
        ----------
        ref_conformers : Union[torch.Tensor, Sequence[torch.Tensor]]
            Tensor of shape (M, N, 3) or list of ensemble tensors.
        pred_conformers : Union[torch.Tensor, Sequence[torch.Tensor]]
            Tensor of shape (K, N, 3) or list of ensemble tensors.
        """
        if isinstance(ref_conformers, torch.Tensor) and ref_conformers.dim() == 3:
            ref_list = [ref_conformers]
            pred_list = [pred_conformers]  # type: ignore
        else:
            ref_list = list(ref_conformers)  # type: ignore
            pred_list = list(pred_conformers)  # type: ignore

        for refs, preds in zip(ref_list, pred_list):
            dist_mat = pairwise_conformer_rmsd(refs, preds, align=self.align)
            min_ref = torch.min(dist_mat, dim=1).values
            min_pred = torch.min(dist_mat, dim=0).values

            self.total_ref_covered += torch.sum(min_ref <= self.threshold).float()
            self.total_ref_count += float(dist_mat.shape[0])
            self.total_pred_covered += torch.sum(min_pred <= self.threshold).float()
            self.total_pred_count += float(dist_mat.shape[1])

    def compute(self) -> Dict[str, torch.Tensor]:
        """Compute Conformer Coverage Recall and Precision percentages [D]."""
        cov_recall = (
            (self.total_ref_covered / (self.total_ref_count + 1e-12)) * 100.0
            if self.total_ref_count > 0
            else torch.tensor(0.0)
        )
        cov_precision = (
            (self.total_pred_covered / (self.total_pred_count + 1e-12)) * 100.0
            if self.total_pred_count > 0
            else torch.tensor(0.0)
        )
        return {
            "cov_recall": cov_recall,
            "cov_precision": cov_precision,
        }


class AverageMinimumRMSD(Metric):
    """TorchMetrics implementation for Average Minimum RMSD (AMR-R and AMR-P) [D]."""

    full_state_update: bool = False

    def __init__(
        self,
        align: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.align = align

        self.add_state("sum_min_rmsd_ref", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_ref_count", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("sum_min_rmsd_pred", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_pred_count", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        ref_conformers: Union[torch.Tensor, Sequence[torch.Tensor]],
        pred_conformers: Union[torch.Tensor, Sequence[torch.Tensor]],
    ) -> None:
        """Update AMR statistics with conformer ensembles."""
        if isinstance(ref_conformers, torch.Tensor) and ref_conformers.dim() == 3:
            ref_list = [ref_conformers]
            pred_list = [pred_conformers]  # type: ignore
        else:
            ref_list = list(ref_conformers)  # type: ignore
            pred_list = list(pred_conformers)  # type: ignore

        for refs, preds in zip(ref_list, pred_list):
            dist_mat = pairwise_conformer_rmsd(refs, preds, align=self.align)
            min_ref = torch.min(dist_mat, dim=1).values
            min_pred = torch.min(dist_mat, dim=0).values

            self.sum_min_rmsd_ref += torch.sum(min_ref)
            self.total_ref_count += float(dist_mat.shape[0])
            self.sum_min_rmsd_pred += torch.sum(min_pred)
            self.total_pred_count += float(dist_mat.shape[1])

    def compute(self) -> Dict[str, torch.Tensor]:
        """Compute AMR Recall and Precision in Angstroms [D]."""
        amr_recall = (
            self.sum_min_rmsd_ref / (self.total_ref_count + 1e-12)
            if self.total_ref_count > 0
            else torch.tensor(0.0)
        )
        amr_precision = (
            self.sum_min_rmsd_pred / (self.total_pred_count + 1e-12)
            if self.total_pred_count > 0
            else torch.tensor(0.0)
        )
        return {
            "amr_recall": amr_recall,
            "amr_precision": amr_precision,
        }


class EnergyMAE(Metric):
    """TorchMetrics implementation for Mean Absolute Error in molecular energies [D]."""

    full_state_update: bool = False

    def __init__(
        self,
        target_unit: str = "ev",
        input_unit: str = "ev",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.target_unit = target_unit
        self.input_unit = input_unit

        self.add_state("sum_abs_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_count", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_energies: torch.Tensor,
        target_energies: torch.Tensor,
    ) -> None:
        """Update energy MAE accumulator."""
        pred = convert_energy(pred_energies.view(-1), from_unit=self.input_unit, to_unit=self.target_unit)
        target = convert_energy(target_energies.view(-1), from_unit=self.input_unit, to_unit=self.target_unit)
        error = torch.abs(pred - target)
        self.sum_abs_error += torch.sum(error)
        self.total_count += float(error.numel())

    def compute(self) -> torch.Tensor:
        """Compute energy MAE in target units [D]."""
        return self.sum_abs_error / (self.total_count + 1e-12)


class RelativeEnergyMAE(Metric):
    """TorchMetrics implementation for relative conformer energy ranking MAE [D].

    Computes MAE of relative energy differences (Delta E = E - min(E)) for conformer ensembles.
    """

    full_state_update: bool = False

    def __init__(
        self,
        target_unit: str = "ev",
        input_unit: str = "ev",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.target_unit = target_unit
        self.input_unit = input_unit

        self.add_state("sum_rel_abs_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_count", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_energies: torch.Tensor,
        target_energies: torch.Tensor,
    ) -> None:
        """Update relative energy MAE."""
        pred = convert_energy(pred_energies.view(-1), from_unit=self.input_unit, to_unit=self.target_unit)
        target = convert_energy(target_energies.view(-1), from_unit=self.input_unit, to_unit=self.target_unit)

        rel_pred = pred - torch.min(pred)
        rel_target = target - torch.min(target)

        error = torch.abs(rel_pred - rel_target)
        self.sum_rel_abs_error += torch.sum(error)
        self.total_count += float(error.numel())

    def compute(self) -> torch.Tensor:
        """Compute relative energy MAE [D]."""
        return self.sum_rel_abs_error / (self.total_count + 1e-12)


class BoltzmannWeightedEnergyMAE(Metric):
    """TorchMetrics implementation for Boltzmann-weighted energy MAE [D].

    Weights conformers by their equilibrium Boltzmann distribution at temperature T.
    """

    full_state_update: bool = False

    def __init__(
        self,
        temperature_k: float = DEFAULT_TEMPERATURE_K,
        target_unit: str = "ev",
        input_unit: str = "ev",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.temperature_k = temperature_k
        self.target_unit = target_unit
        self.input_unit = input_unit

        self.add_state("sum_weighted_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_ensembles", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_energies: torch.Tensor,
        target_energies: torch.Tensor,
    ) -> None:
        """Update Boltzmann-weighted energy error."""
        # Convert target and pred to eV for Boltzmann factor calculation (kB * T in eV)
        pred_ev = convert_energy(pred_energies.view(-1), from_unit=self.input_unit, to_unit="ev")
        target_ev = convert_energy(target_energies.view(-1), from_unit=self.input_unit, to_unit="ev")

        kb_t_ev = BOLTZMANN_CONSTANT_EV_K * self.temperature_k
        rel_target_ev = target_ev - torch.min(target_ev)
        boltzmann_weights = torch.softmax(-rel_target_ev / kb_t_ev, dim=0)

        # Evaluate absolute error in target units
        pred_target_u = convert_energy(pred_ev, from_unit="ev", to_unit=self.target_unit)
        target_target_u = convert_energy(target_ev, from_unit="ev", to_unit=self.target_unit)
        abs_err = torch.abs(pred_target_u - target_target_u)

        weighted_err = torch.sum(boltzmann_weights * abs_err)
        self.sum_weighted_error += weighted_err
        self.total_ensembles += 1.0

    def compute(self) -> torch.Tensor:
        """Compute average Boltzmann-weighted energy error [D]."""
        return self.sum_weighted_error / (self.total_ensembles + 1e-12)


class ForceMAE(Metric):
    """TorchMetrics implementation for component-wise and vector force MAE [D]."""

    full_state_update: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.add_state("sum_abs_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_components", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(self, pred_forces: torch.Tensor, true_forces: torch.Tensor) -> None:
        """Update force MAE."""
        diff = torch.abs(pred_forces - true_forces)
        self.sum_abs_error += torch.sum(diff)
        self.total_components += float(diff.numel())

    def compute(self) -> torch.Tensor:
        """Compute force MAE in eV/Angstrom [D]."""
        return self.sum_abs_error / (self.total_components + 1e-12)


class ForceRMSE(Metric):
    """TorchMetrics implementation for force Root-Mean-Square Error [D]."""

    full_state_update: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.add_state("sum_sq_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_components", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(self, pred_forces: torch.Tensor, true_forces: torch.Tensor) -> None:
        """Update force RMSE."""
        sq_diff = (pred_forces - true_forces) ** 2
        self.sum_sq_error += torch.sum(sq_diff)
        self.total_components += float(sq_diff.numel())

    def compute(self) -> torch.Tensor:
        """Compute force RMSE in eV/Angstrom [D]."""
        return torch.sqrt(self.sum_sq_error / (self.total_components + 1e-12))


class ForceCosineSimilarity(Metric):
    """TorchMetrics implementation for force vector cosine similarity [D]."""

    full_state_update: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.add_state("sum_cosine_sim", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_vectors", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(self, pred_forces: torch.Tensor, true_forces: torch.Tensor) -> None:
        """Update force cosine similarity."""
        p_norm = torch.norm(pred_forces, dim=-1, keepdim=True) + 1e-12
        t_norm = torch.norm(true_forces, dim=-1, keepdim=True) + 1e-12
        cos_sim = torch.sum((pred_forces / p_norm) * (true_forces / t_norm), dim=-1)
        self.sum_cosine_sim += torch.sum(cos_sim)
        self.total_vectors += float(cos_sim.numel())

    def compute(self) -> torch.Tensor:
        """Compute mean force direction cosine similarity in [-1, 1] [D]."""
        return self.sum_cosine_sim / (self.total_vectors + 1e-12)


class RotationalConstantsMAE(Metric):
    """TorchMetrics implementation for spectroscopic rotational constants MAE (A, B, C) [D]."""

    full_state_update: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.add_state("sum_abs_a", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("sum_abs_b", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("sum_abs_c", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_molecules", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_positions: torch.Tensor,
        target_positions: torch.Tensor,
        atomic_numbers: torch.Tensor,
    ) -> None:
        """Update rotational constants MAE."""
        _, pred_rot = compute_moments_of_inertia(pred_positions, atomic_numbers)
        _, target_rot = compute_moments_of_inertia(target_positions, atomic_numbers)

        err_a = torch.abs(pred_rot[..., 0] - target_rot[..., 0])
        err_b = torch.abs(pred_rot[..., 1] - target_rot[..., 1])
        err_c = torch.abs(pred_rot[..., 2] - target_rot[..., 2])

        self.sum_abs_a += torch.sum(err_a)
        self.sum_abs_b += torch.sum(err_b)
        self.sum_abs_c += torch.sum(err_c)
        self.total_molecules += float(err_a.numel())

    def compute(self) -> Dict[str, torch.Tensor]:
        """Compute rotational constants MAE in MHz [D]."""
        count = self.total_molecules + 1e-12
        mae_a = self.sum_abs_a / count
        mae_b = self.sum_abs_b / count
        mae_c = self.sum_abs_c / count
        mae_mean = (mae_a + mae_b + mae_c) / 3.0
        return {
            "mae_a_mhz": mae_a,
            "mae_b_mhz": mae_b,
            "mae_c_mhz": mae_c,
            "mae_mean_mhz": mae_mean,
        }


class InertialDefectMAE(Metric):
    """TorchMetrics implementation for planar inertial defect MAE [D]."""

    full_state_update: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.add_state("sum_abs_defect_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_molecules", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_positions: torch.Tensor,
        target_positions: torch.Tensor,
        atomic_numbers: torch.Tensor,
    ) -> None:
        """Update planar inertial defect error."""
        pred_defect = compute_inertial_defect(pred_positions, atomic_numbers)
        target_defect = compute_inertial_defect(target_positions, atomic_numbers)
        err = torch.abs(pred_defect - target_defect)
        self.sum_abs_defect_error += torch.sum(err)
        self.total_molecules += float(err.numel())

    def compute(self) -> torch.Tensor:
        """Compute inertial defect MAE in u * Angstrom^2 [D]."""
        return self.sum_abs_defect_error / (self.total_molecules + 1e-12)


class InternalCoordinatesMAE(Metric):
    """TorchMetrics implementation for bond lengths, bond angles, and dihedrals MAE [D]."""

    full_state_update: bool = False

    def __init__(
        self,
        bonds: Optional[torch.Tensor] = None,
        angles: Optional[torch.Tensor] = None,
        dihedrals: Optional[torch.Tensor] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.bonds = bonds
        self.angles = angles
        self.dihedrals = dihedrals

        self.add_state("sum_bond_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_bonds", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("sum_angle_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_angles", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("sum_dihedral_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_dihedrals", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_positions: torch.Tensor,
        target_positions: torch.Tensor,
        bonds: Optional[torch.Tensor] = None,
        angles: Optional[torch.Tensor] = None,
        dihedrals: Optional[torch.Tensor] = None,
    ) -> None:
        """Update internal coordinate errors."""
        active_bonds = bonds if bonds is not None else self.bonds
        active_angles = angles if angles is not None else self.angles
        active_dihedrals = dihedrals if dihedrals is not None else self.dihedrals

        if active_bonds is not None and active_bonds.numel() > 0:
            pred_b = compute_bond_lengths(pred_positions, active_bonds)
            true_b = compute_bond_lengths(target_positions, active_bonds)
            err_b = torch.abs(pred_b - true_b)
            self.sum_bond_error += torch.sum(err_b)
            self.total_bonds += float(err_b.numel())

        if active_angles is not None and active_angles.numel() > 0:
            pred_a = compute_bond_angles(pred_positions, active_angles)
            true_a = compute_bond_angles(target_positions, active_angles)
            err_a = torch.abs(pred_a - true_a)
            self.sum_angle_error += torch.sum(err_a)
            self.total_angles += float(err_a.numel())

        if active_dihedrals is not None and active_dihedrals.numel() > 0:
            pred_d = compute_dihedral_angles(pred_positions, active_dihedrals)
            true_d = compute_dihedral_angles(target_positions, active_dihedrals)
            # Periodic angular difference in [-180, 180]
            diff_d = torch.remainder(pred_d - true_d + 180.0, 360.0) - 180.0
            err_d = torch.abs(diff_d)
            self.sum_dihedral_error += torch.sum(err_d)
            self.total_dihedrals += float(err_d.numel())

    def compute(self) -> Dict[str, torch.Tensor]:
        """Compute internal coordinates MAE dictionary [D]."""
        res: Dict[str, torch.Tensor] = {}
        if self.total_bonds > 0:
            res["mae_bonds_angstrom"] = self.sum_bond_error / self.total_bonds
        if self.total_angles > 0:
            res["mae_angles_deg"] = self.sum_angle_error / self.total_angles
        if self.total_dihedrals > 0:
            res["mae_dihedrals_deg"] = self.sum_dihedral_error / self.total_dihedrals
        return res


class ConformerEnsembleEvaluator(Metric):
    """Comprehensive multi-metric evaluator for conformer generation models.

    Integrates COV-R, COV-P, AMR-R, AMR-P, Energy MAE, Relative Energy MAE,
    and Rotational Constants tracking into a unified evaluation harness.
    """

    full_state_update: bool = False

    def __init__(
        self,
        thresholds: Sequence[float] = (0.5, 1.25),
        temperature_k: float = DEFAULT_TEMPERATURE_K,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.thresholds = list(thresholds)
        self.temperature_k = temperature_k

        # Safe keys without dots for nn.ModuleDict
        self.cov_metrics = nn.ModuleDict(
            {f"cov_{t:.2f}".replace(".", "_"): ConformerCoverage(threshold=t) for t in self.thresholds}
        )
        self.amr_metric = AverageMinimumRMSD()
        self.energy_mae = EnergyMAE(target_unit="ev")
        self.rel_energy_mae = RelativeEnergyMAE(target_unit="ev")
        self.rotational_mae = RotationalConstantsMAE()

    def update(
        self,
        ref_positions: torch.Tensor,
        pred_positions: torch.Tensor,
        ref_energies: Optional[torch.Tensor] = None,
        pred_energies: Optional[torch.Tensor] = None,
        atomic_numbers: Optional[torch.Tensor] = None,
    ) -> None:
        """Update all component metrics with evaluation batch."""
        for metric in self.cov_metrics.values():
            metric.update(ref_positions, pred_positions)

        self.amr_metric.update(ref_positions, pred_positions)

        if ref_energies is not None and pred_energies is not None:
            self.energy_mae.update(pred_energies, ref_energies)
            self.rel_energy_mae.update(pred_energies, ref_energies)

        if atomic_numbers is not None and ref_positions.dim() >= 2 and pred_positions.dim() >= 2:
            self.rotational_mae.update(pred_positions, ref_positions, atomic_numbers)

    def compute(self) -> Dict[str, torch.Tensor]:
        """Compute unified summary dictionary across all evaluated metrics [D]."""
        results: Dict[str, torch.Tensor] = {}

        for name, metric in self.cov_metrics.items():
            cov_res = metric.compute()
            t_str = name.split("cov_")[-1].replace("_", ".")
            results[f"cov_recall_{t_str}"] = cov_res["cov_recall"]
            results[f"cov_precision_{t_str}"] = cov_res["cov_precision"]

        amr_res = self.amr_metric.compute()
        results["amr_recall"] = amr_res["amr_recall"]
        results["amr_precision"] = amr_res["amr_precision"]

        if self.energy_mae.total_count > 0:
            results["energy_mae_ev"] = self.energy_mae.compute()
            results["rel_energy_mae_ev"] = self.rel_energy_mae.compute()

        if self.rotational_mae.total_molecules > 0:
            rot_res = self.rotational_mae.compute()
            results["rotational_mae_mhz"] = rot_res["mae_mean_mhz"]
            results["rotational_mae_a_mhz"] = rot_res["mae_a_mhz"]
            results["rotational_mae_b_mhz"] = rot_res["mae_b_mhz"]
            results["rotational_mae_c_mhz"] = rot_res["mae_c_mhz"]

        return results

    def reset(self) -> None:
        """Reset all child metrics."""
        super().reset()
        for metric in self.cov_metrics.values():
            metric.reset()
        self.amr_metric.reset()
        self.energy_mae.reset()
        self.rel_energy_mae.reset()
        self.rotational_mae.reset()
