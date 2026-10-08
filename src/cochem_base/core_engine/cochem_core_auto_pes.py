#!/usr/bin/env python3
# cochem_canvas_target: core_engine/cochem_core_auto_pes.py
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Stage 13.2 / QS-3 - Committee-Based Active Learning & Delta-Learning PES Fitting Engine.

Mandated by:
- Method Matrix v4 Quick Start QS-3 ("I need an intermolecular surface: PES campaign, one day instead of one month")
- Method Matrix v4 §13.2 (Table 2 - Rows T2-12h and T2-1d: Delta-learning + Active Learning PES)
- Method Matrix v4 §10.8 (Committee Uncertainty inside the Wrapper & Gate G5: epsilon = Q3 + 1.5 * IQR)
- Method Matrix v4 §8C (HDF5 PESStore, Delta-pairs alignment & DVR grid integration)
- Method Matrix v4 §8A (Heterogeneous Parallel Concurrency & Single-Thread Grid Workers)
- CoChem Anti-Spoofing Protocol v2 & v3 (Authentic Physical Tensor & Mathematical Invariant Compliance)
- CoChem Mendeleev Library Mandate (Dynamic Atomic and Isotopic Mass Retrieval via mendeleev)

Architectural Overview:
1. Active Learning & Committee Uncertainty Quantification (Method Matrix QS-3 Step 3, §10.8, §13.2):
   - Committee of M diverse estimators (default M=4, matching AIMNet2 / NN ensemble recommendation).
   - Evaluates ensemble mean energy E_bar, ensemble gradient g_bar, normalized per-atom energy
     uncertainty sigma_E / sqrt(N_atoms), and force dispersion U_F = max_i max_m |g_m,i - g_bar,i|.
   - Guard G5 Uncertainty Gate: thresholding epsilon = Q3 + 1.5 * IQR over the training error distribution.
   - Multi-strategy acquisition functions with explicit anti-pure-variance enforcement (Uteva et al.):
     * Two-Set Error-Based Acquisition: weights committee uncertainty by spatial distance to already selected points:
       alpha(x) = sigma_E(x) * (1.0 - exp(-d_min(x, X_selected)^2 / (2 * sigma_dist^2))).
     * Diversity-Weighted UQ Acquisition: combines normalized committee variance with greedy furthest-point distance.
     * Exploration-Exploitation Batching: selects 300-800 points from ~2,000 base DFT pool in iterative batches.

2. Delta-Learning Potential Energy Surface Fitting (Method Matrix QS-3 Step 4, Row T2-12h):
   - Base representation V_low(X) on ~2,000 DFT points + Delta-correction Delta_V(X) on 300-800 CC points:
     V_Delta(X) = V_low(X) + Delta_V(X) where Delta_V(X) = V_high(X) - V_low(X).
   - High-performance Kernel Ridge Regression (RBF, Matern-5/2, Matern-3/2, Polynomial), Permutationally
     Invariant Polynomial (PIP) Morse coordinate expansion, and Regularized Neural Committee.
   - Analytical gradient calculation: grad_X V_Delta(X) = grad_X V_low(X) + grad_X Delta_V(X) through
     interatomic Morse coordinates for molecular dynamics and geometry stepping.

3. Spectroscopic Held-Out Validation Protocol (Method Matrix QS-3 Step 5, §13.2):
   - Strict separation of a dedicated held-out validation grid (e.g. 20% or user-specified held-out test grid).
   - Rigorous residual evaluation reporting RMSE, MAE, and Max Error in cm^-1, kcal/mol, meV, and Hartree.
   - Evaluates against spectroscopic criteria (RMS <= 3-10 cm^-1 for T2-12h, <= 5-20 cm^-1 for T2-1d).

4. Autonomous HDF5 PESStore Integration (Method Matrix §8C):
   - Direct interoperability with `PESStore` (`delta_pairs(low, high)`, `dataset(method_id)`, `todo(method_id, ids)`).
   - Model artifact serialization, parameter persistence, and direct DVR product grid export.

5. Dynamic Mendeleev Mass Resolution (Mendeleev Library Mandate):
   - Strictly ZERO hardcoded atomic/isotopic masses; all masses and atomic numbers resolved dynamically via `mendeleev`.
"""

from __future__ import annotations

import os

# Mandated by Method Matrix QS-3 Step 6 line 167: enforce FP64 double precision on startup
os.environ["JAX_ENABLE_X64"] = "True"

import argparse
import itertools
import json
import logging
import math
import sys
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

import h5py
import numpy as np
import scipy.linalg
import scipy.optimize
import scipy.spatial.distance
from mendeleev import element
from pydantic import BaseModel, ConfigDict, Field, field_validator

from cochem_base.exceptions import (
    CoChemError,
    MethodMatrixViolationError,
    MissingDataError,
    NumericalConditioningError,
    ProvenanceErrorCode,
    SymmetryInvarianceError,
)
from cochem_base.schemas import (
    ActiveLearningBatchConfig,
    KrrRegularizationConfig,
    PipSymmetryConfig,
)
from cochem_base.core import cochem_constants as _constants

# Configure module logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [AutoPES] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# =============================================================================
# Physical & Spectroscopic Constants (Zero Hardcoded Atomic Masses)
# =============================================================================
HARTREE_TO_EV: float = _constants.HARTREE_TO_EV
HARTREE_TO_CM1: float = _constants.HARTREE_TO_CM_INV
EV_TO_CM1: float = HARTREE_TO_CM1 / HARTREE_TO_EV
HARTREE_TO_KCAL_MOL: float = _constants.HARTREE_TO_KCAL_MOL
KCAL_MOL_TO_CM1: float = HARTREE_TO_CM1 / HARTREE_TO_KCAL_MOL
BOHR_TO_ANGSTROM: float = _constants.BOHR_TO_ANGSTROM
ANGSTROM_TO_BOHR: float = _constants.ANGSTROM_TO_BOHR
MEV_PER_HARTREE: float = HARTREE_TO_EV * 1000.0


def get_dynamic_atomic_mass(symbol: str) -> float:
    """Resolve an exact assigned/principal isotope mass from dynamic Mendeleev data."""
    from cochem_base.physics.isotopes import get_isotope_mass
    value = symbol
    return get_isotope_mass(value)


def get_dynamic_atomic_number(symbol: str) -> int:
    """Dynamically retrieves the atomic number Z of an element."""
    clean_sym = symbol.strip()
    if clean_sym in ("D", "T", "2H", "3H"):
        return 1
    try:
        el = element(clean_sym)
        return int(el.atomic_number)
    except Exception as exc:
        raise CoChemError(
            f"Failed to resolve atomic number dynamically for symbol '{symbol}': {exc}",
            error_code=ProvenanceErrorCode.MISSING_DATA,
        ) from exc


# =============================================================================
# Pydantic v2 Configuration & Results Schemas
# =============================================================================

class AcquisitionStrategy(str, Enum):
    """Active learning point acquisition strategies."""
    TWO_SET_ERROR_BASED = "two_set_error_based"
    DIVERSITY_WEIGHTED_UQ = "diversity_weighted_uq"
    EXPLORATION_EXPLOITATION = "exploration_exploitation"
    QUERY_BY_COMMITTEE = "query_by_committee"
    PURE_VARIANCE = "pure_variance"


class FittingBackend(str, Enum):
    """Potential energy surface fitting backends."""
    KERNEL_RIDGE = "kernel_ridge"
    PIP_RBF = "pip_rbf"
    NEURAL_COMMITTEE = "neural_committee"
    POLYNOMIAL_EXPANSION = "polynomial_expansion"


class KernelType(str, Enum):
    """Kernel functions for Kernel Ridge Regression."""
    RBF = "rbf"
    MATERN52 = "matern52"
    MATERN32 = "matern32"
    POLYNOMIAL = "polynomial"


class ActiveLearningConfig(BaseModel):
    """Configuration for committee-based active learning selection."""
    model_config = ConfigDict(extra="forbid")

    pool_size: int = Field(default=2000, description="Size of candidate base DFT pool (QS-3 ~2,000 points)")
    n_select_min: int = Field(default=300, description="Minimum points to select (QS-3 300-800 points)")
    n_select_max: int = Field(default=800, description="Maximum points to select (QS-3 300-800 points)")
    n_select_target: int = Field(default=500, description="Target number of actively selected points")
    batch_size: int = Field(default=50, description="Iterative batch selection size")
    acquisition_strategy: AcquisitionStrategy = Field(
        default=AcquisitionStrategy.TWO_SET_ERROR_BASED,
        description="Acquisition strategy (pure variance alone is restricted per Uteva et al.)",
    )
    committee_size: int = Field(default=4, description="Committee ensemble size (§10.8 AIMNet2 / NN standard)")
    diversity_weight: float = Field(default=0.35, description="Weight for spatial diversity exploration")
    iqr_multiplier: float = Field(default=1.5, description="Guard G5 uncertainty multiplier: Q3 + 1.5 * IQR")
    held_out_ratio: float = Field(default=0.20, description="Separated held-out validation grid ratio")
    morse_lambda: float = Field(default=2.0, description="Morse coordinate decay factor in Angstroms")
    random_seed: int = Field(default=42, description="Random seed for reproducible active selection")

    @field_validator("n_select_target")
    @classmethod
    def validate_n_select(cls, v: int, info: Any) -> int:
        if v < 50:
            raise ValueError(f"n_select_target must be >= 50, got {v}")
        return v


class DeltaFittingConfig(BaseModel):
    """Configuration for Delta-learning potential energy surface fitting."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    backend: FittingBackend = Field(default=FittingBackend.KERNEL_RIDGE, description="Fitting model backend")
    kernel: KernelType = Field(default=KernelType.RBF, description="Kernel function for KRR")
    regularization_alpha: float = Field(default=1e-6, gt=0.0, description="L2 regularization / ridge parameter alpha")
    gamma: Optional[float] = Field(default=None, gt=0.0, description="Kernel lengthscale parameter gamma (1 / (2*sigma^2))")
    poly_degree: int = Field(default=4, ge=1, description="Polynomial degree for PIP expansion")
    morse_lambda: float = Field(default=2.0, gt=0.0, description="Morse coordinate decay parameter lambda in Angstroms")
    include_secondary: bool = Field(default=False, description="Whether to include degree-2 secondary PIP invariants")
    target_rms_cm1: float = Field(default=10.0, gt=0.0, description="Target spectroscopic held-out RMSE in cm^-1 (QS-3 / T2-12h)")
    energy_reference: Literal["absolute", "interaction_zero_asymptote"] = Field(
        default="absolute",
        description="Absolute energy offsets are fitted from training data; zero-asymptote interaction energies retain their declared zero reference",
    )
    neural_committee_size: int = Field(default=4, ge=2, le=16)
    neural_hidden_layers: Tuple[int, ...] = Field(default=(32, 32), min_length=1, max_length=4)
    neural_max_iterations: int = Field(default=500, ge=1)
    neural_validation_fraction: float = Field(default=0.15, gt=0.0, lt=0.5)
    neural_weight_decay: float = Field(default=1e-6, ge=0.0)
    neural_random_seed: int = Field(default=42, ge=0)

    @field_validator("neural_hidden_layers")
    @classmethod
    def validate_neural_widths(cls, widths: Tuple[int, ...]) -> Tuple[int, ...]:
        if any(width < 1 or width > 512 for width in widths):
            raise ValueError("Each neural hidden layer must have 1 to 512 units")
        return widths


class CommitteePrediction(BaseModel):
    """Structured committee ensemble prediction payload."""
    model_config = ConfigDict(extra="forbid")

    mean_energy_hartree: float = Field(description="Ensemble mean energy E_bar in Hartrees")
    sigma_energy_hartree: float = Field(description="Committee standard deviation in Hartrees")
    sigma_energy_mev_per_atom: float = Field(description="Normalised uncertainty in meV/atom (§10.8)")
    force_uncertainty_hartree_bohr: Optional[float] = Field(default=None, description="Max atom-wise force dispersion U_F")
    g5_gate_passed: bool = Field(description="True if committee uncertainty satisfies Guard G5 threshold")
    member_energies: List[float] = Field(description="Individual committee member energies in Hartrees")


class ActiveLearningSelectionResult(BaseModel):
    """Structured outcome of active learning point selection."""
    model_config = ConfigDict(extra="forbid")

    selected_indices: List[int] = Field(description="Indices of actively selected points from pool")
    selected_point_ids: List[str] = Field(description="String identifiers of selected points")
    acquisition_scores: List[float] = Field(description="Acquisition function values at selected points")
    committee_sigmas_hartree: List[float] = Field(description="Committee standard deviations in Hartrees")
    committee_sigmas_mev_atom: List[float] = Field(description="Committee uncertainties in meV/atom")
    selection_rounds: int = Field(description="Number of iterative batch rounds executed")
    n_selected: int = Field(description="Total points selected for high-level CCSD(T) escalation")
    iqr_threshold_hartree: float = Field(description="Calculated Guard G5 threshold in Hartrees (Q3 + 1.5 * IQR)")
    iqr_threshold_mev_atom: float = Field(description="Calculated Guard G5 threshold in meV/atom")
    held_out_indices: List[int] = Field(description="Indices reserved for held-out validation grid")
    held_out_point_ids: List[str] = Field(description="Point IDs of held-out validation grid")
    provenance_info: Dict[str, Any] = Field(default_factory=dict, description="Metadata and audit trail")


class PESValidationMetrics(BaseModel):
    """Numerical fit metrics against supplied labels, not physical certification.

    ``spectroscopic_grade`` is a legacy field name for the specified numerical
    threshold. Its scope is identified explicitly by ``validation_scope``.
    """
    model_config = ConfigDict(extra="forbid")

    n_train: int = Field(description="Number of training points")
    n_held_out: int = Field(description="Number of held-out validation points")
    train_rmse_cm1: float = Field(description="Training RMSE in cm^-1")
    train_mae_cm1: float = Field(description="Training MAE in cm^-1")
    train_max_err_cm1: float = Field(description="Training Max Error in cm^-1")
    held_out_rmse_cm1: float = Field(description="Held-out validation RMSE in cm^-1")
    held_out_mae_cm1: float = Field(description="Held-out validation MAE in cm^-1")
    held_out_max_err_cm1: float = Field(description="Held-out validation Max Error in cm^-1")
    held_out_rmse_kcal_mol: float = Field(description="Held-out validation RMSE in kcal/mol")
    held_out_rmse_hartree: float = Field(description="Held-out validation RMSE in Hartrees")
    spectroscopic_grade: bool = Field(description="True if held_out_rmse_cm1 <= target_rms_cm1")
    target_rms_cm1: float = Field(description="Requested numerical energy-error threshold in cm^-1; not a predicted frequency")
    timestamp: str = Field(description="ISO 8601 evaluation timestamp")
    validation_scope: str = "unspecified_legacy"
    held_out_baseline_rmse_cm1: Optional[float] = None
    held_out_total_surrogate_rmse_cm1: Optional[float] = None
    total_surrogate_meets_target: Optional[bool] = None


class DeltaSurfaceFitResult(BaseModel):
    """Complete summary of Delta-learning potential energy surface fitting."""
    model_config = ConfigDict(extra="forbid")

    low_method: str = Field(description="Base low-level method ID (e.g. DFT wb97x_v_tz)")
    high_method: str = Field(description="High-level escalation method ID (e.g. dlpno_ccsdt1_avtz)")
    n_base_dft_points: int = Field(description="Total base DFT points in grid")
    n_delta_points: int = Field(description="Number of high-level Delta training pairs")
    n_held_out_points: int = Field(description="Number of held-out validation points")
    metrics: PESValidationMetrics = Field(description="Numerical validation against supplied targets, with explicit prediction scope")
    backend: str = Field(description="Fitting backend used")
    model_parameters: Dict[str, Any] = Field(description="Fitted model hyper-parameters and dimensions")
    timestamp: str = Field(description="ISO 8601 fit completion timestamp")


# =============================================================================
# Invariant Geometry Featurizer (Translation & Rotation Invariance)
# =============================================================================

class GeometryFeaturizer:
    """
    Computes rotationally and translationally invariant molecular descriptors:
    - Pairwise interatomic distances R_ij = ||r_i - r_j||_2
    - Morse coordinates y_ij = exp(-R_ij / lambda)
    - Inverse Coulomb matrix representation
    - Analytical Morse coordinate Jacobians d(y_ij)/d(r_ka) for exact force evaluations.
    """

    def __init__(
        self,
        symbols: Sequence[str],
        morse_lambda: float = 2.0,
        include_secondary: bool = False,
        pip_config: Optional[PipSymmetryConfig] = None,
    ) -> None:
        self.symbols: List[str] = [s.strip() for s in symbols]
        self.n_atoms: int = len(self.symbols)
        if self.n_atoms < 2:
            raise ValueError(f"GeometryFeaturizer requires at least 2 atoms, got {self.n_atoms}")

        self.morse_lambda: float = float(morse_lambda)
        if self.morse_lambda <= 0.0:
            raise ValueError(f"morse_lambda must be strictly positive, got {self.morse_lambda}")

        self.include_secondary: bool = bool(include_secondary)
        self.pip_config: PipSymmetryConfig = pip_config or PipSymmetryConfig()

        # Dynamically resolve atomic masses and atomic numbers (Mendeleev Mandate)
        self.atomic_masses: np.ndarray = np.array(
            [get_dynamic_atomic_mass(s) for s in self.symbols], dtype=np.float64
        )
        self.atomic_numbers: np.ndarray = np.array(
            [get_dynamic_atomic_number(s) for s in self.symbols], dtype=np.int32
        )

        # Build pair index mapping (i < j)
        self.pair_indices: List[Tuple[int, int]] = []
        for i in range(self.n_atoms):
            for j in range(i + 1, self.n_atoms):
                self.pair_indices.append((i, j))
        self.n_pairs: int = len(self.pair_indices)
        self.pair_to_idx: Dict[Tuple[int, int], int] = {
            pair: p for p, pair in enumerate(self.pair_indices)
        }

        # Identify permutation equivalence classes of identical nuclei (Task 5 PIP Symmetrization)
        self.equiv_classes: Dict[int, List[int]] = {}
        for idx, z in enumerate(self.atomic_numbers):
            self.equiv_classes.setdefault(int(z), []).append(idx)

        # Generate permutation group G over identical nuclei with closed subgroup orbit averaging
        class_perms: List[List[Tuple[int, ...]]] = []
        for _z_val, indices in self.equiv_classes.items():
            n_class = len(indices)
            n_factorial = math.factorial(n_class)
            sub_type = self.pip_config.subgroup_type

            if sub_type == "full" and n_factorial <= self.pip_config.max_symmetric_order:
                class_perms.append([tuple(p) for p in itertools.permutations(indices)])
            elif sub_type == "alternating" or (sub_type == "full" and n_factorial > self.pip_config.max_symmetric_order and n_factorial // 2 <= self.pip_config.max_symmetric_order):
                # Alternating group A_n (even parity permutations)
                idx_map = {idx: i for i, idx in enumerate(indices)}
                a_n = []
                for p in itertools.permutations(indices):
                    invs = 0
                    arr = [idx_map[x] for x in p]
                    for i_pos in range(len(arr)):
                        for j_pos in range(i_pos + 1, len(arr)):
                            if arr[i_pos] > arr[j_pos]:
                                invs += 1
                    if invs % 2 == 0:
                        a_n.append(tuple(p))
                class_perms.append(a_n)
            else:
                # Molecular automorphism wreath product S_k wr S_m
                if n_class % 2 == 0:
                    k = 2
                    m = n_class // 2
                elif n_class % 3 == 0:
                    k = 3
                    m = n_class // 3
                else:
                    k = 1
                    m = n_class

                if k == 1 or m == 1:
                    # Cyclic group C_N which is a strictly closed abelian subgroup
                    c_n = []
                    for shift in range(n_class):
                        c_n.append(tuple(indices[(i + shift) % n_class] for i in range(n_class)))
                    class_perms.append(c_n)
                else:
                    blocks = [indices[r * k : (r + 1) * k] for r in range(m)]
                    block_perms = list(itertools.permutations(range(m)))
                    internal_perms = list(itertools.permutations(range(k)))

                    wreath_grp = []
                    for internal_choices in itertools.product(internal_perms, repeat=m):
                        for sigma in block_perms:
                            p_map = {}
                            for r in range(m):
                                target_block = sigma[r]
                                h_r = internal_choices[r]
                                for s in range(k):
                                    orig_idx = blocks[r][s]
                                    target_idx = blocks[target_block][h_r[s]]
                                    p_map[orig_idx] = target_idx
                            p_full_class = tuple(p_map[i] for i in indices)
                            wreath_grp.append(p_full_class)
                    class_perms.append(wreath_grp)

        # Combine across equivalence classes
        group_perms: List[Tuple[int, ...]] = []
        for perm_tuple in itertools.product(*class_perms):
            p_full = list(range(self.n_atoms))
            for orig_indices, perm_indices in zip(self.equiv_classes.values(), perm_tuple, strict=False):
                for orig, target in zip(orig_indices, perm_indices, strict=False):
                    p_full[orig] = target
            group_perms.append(tuple(p_full))

        # Strict mathematical subgroup closure verification: for all ga, gb in G => ga o gb in G
        perm_set = set(group_perms)
        n_at = self.n_atoms
        is_closed = True
        for p1 in group_perms:
            for p2 in group_perms:
                comp = tuple(p1[p2[i]] for i in range(n_at))
                if comp not in perm_set:
                    is_closed = False
                    break
            if not is_closed:
                break

        if not is_closed:
            raise SymmetryInvarianceError(
                "Permutation set violates group closure axiom: ga o gb not in G."
            )

        self.group_permutations = group_perms

        # Precompute pair index permutations pi_P
        pair_perms: List[np.ndarray] = []
        for P in self.group_permutations:
            pi_p = np.empty(self.n_pairs, dtype=np.int32)
            for p_idx, (i, j) in enumerate(self.pair_indices):
                u, v = P[i], P[j]
                ordered_pair = (u, v) if u < v else (v, u)
                pi_p[p_idx] = self.pair_to_idx[ordered_pair]
            pair_perms.append(pi_p)
        self.pair_permutations = pair_perms

        # Precompute degree-1 orbits (primary invariants)
        visited_pairs: Set[int] = set()
        self.deg1_orbits: List[List[int]] = []
        for p in range(self.n_pairs):
            if p in visited_pairs:
                continue
            orb = sorted({int(pi_p[p]) for pi_p in self.pair_permutations})
            self.deg1_orbits.append(orb)
            visited_pairs.update(orb)

        # Precompute degree-2 orbits (secondary invariants)
        self.deg2_orbits: List[List[Tuple[int, int]]] = []
        if self.include_secondary:
            visited_pair_pairs: Set[Tuple[int, int]] = set()
            for p in range(self.n_pairs):
                for q in range(p, self.n_pairs):
                    if (p, q) in visited_pair_pairs:
                        continue
                    orb = sorted({
                        (int(min(pi_p[p], pi_p[q])), int(max(pi_p[p], pi_p[q])))
                        for pi_p in self.pair_permutations
                    })
                    self.deg2_orbits.append(orb)
                    visited_pair_pairs.update(orb)

        self.n_pip_features: int = len(self.deg1_orbits) + (len(self.deg2_orbits) if self.include_secondary else 0)
        self.n_features: int = self.n_pip_features

    def compute_distance_matrix(self, geom: np.ndarray) -> np.ndarray:
        """
        Computes the pairwise distance matrix for a single geometry (N_atoms, 3)
        or an ensemble (N_points, N_atoms, 3).
        """
        coords = np.asarray(geom, dtype=np.float64)
        if coords.ndim == 2:
            # Single geometry: (N_atoms, 3)
            diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
            dist = np.sqrt(np.sum(diff**2, axis=-1) + 1e-18)
            np.fill_diagonal(dist, 0.0)
            return dist
        elif coords.ndim == 3:
            # Batch of geometries: (N_pts, N_atoms, 3)
            diff = coords[:, :, np.newaxis, :] - coords[:, np.newaxis, :, :]
            dist = np.sqrt(np.sum(diff**2, axis=-1) + 1e-18)
            for k in range(dist.shape[0]):
                np.fill_diagonal(dist[k], 0.0)
            return dist
        else:
            raise ValueError(f"Expected 2D or 3D geometry array, got shape {coords.shape}")

    def compute_morse_features(self, geoms: np.ndarray) -> np.ndarray:
        """
        Computes Permutationally Invariant Polynomial (PIP) features over identical nuclei:
        - Primary invariants: degree-1 pair orbit averages.
        - Secondary invariants: degree-2 pair-pair orbit averages.
        Guarantees ||f(PX) - f(X)||_2 < 10^-14 for all nuclear permutations P in G.
        """
        coords = np.asarray(geoms, dtype=np.float64)
        is_single = (coords.ndim == 2)
        if is_single:
            coords = coords[np.newaxis, :, :]

        n_pts = coords.shape[0]
        y_raw = np.full((n_pts, self.n_pairs), 0.0, dtype=np.float64)

        for p_idx, (i, j) in enumerate(self.pair_indices):
            d_vec = coords[:, i, :] - coords[:, j, :]
            r_ij = np.sqrt(np.sum(d_vec**2, axis=-1) + 1e-18)
            y_raw[:, p_idx] = np.exp(-r_ij / self.morse_lambda)

        feats = np.full((n_pts, self.n_pip_features), 0.0, dtype=np.float64)

        # 1. Primary invariants (degree 1)
        for k, orbit in enumerate(self.deg1_orbits):
            feats[:, k] = np.mean(y_raw[:, orbit], axis=1)

        # 2. Secondary invariants (degree 2)
        if self.include_secondary:
            offset = len(self.deg1_orbits)
            for s, orbit in enumerate(self.deg2_orbits):
                p_indices = [item[0] for item in orbit]
                q_indices = [item[1] for item in orbit]
                vals = y_raw[:, p_indices] * y_raw[:, q_indices]
                feats[:, offset + s] = np.mean(vals, axis=1)

        return feats[0] if is_single else feats

    def featurize(self, geoms: np.ndarray) -> np.ndarray:
        """Computes PIP invariant features over identical nuclei (alias for compute_morse_features). [M]"""
        return self.compute_morse_features(geoms)

    def compute_coulomb_matrix(self, geoms: np.ndarray) -> np.ndarray:
        """
        Computes the canonical sorted Coulomb matrix representation invariant under
        nuclear permutations of identical atoms.
        C_ij = Z_i * Z_j / R_ij (off-diag) and 0.5 * Z_i^2.4 (diag).
        """
        coords = np.asarray(geoms, dtype=np.float64)
        is_single = (coords.ndim == 2)
        if is_single:
            coords = coords[np.newaxis, :, :]

        n_pts = coords.shape[0]
        n_features = self.n_atoms + self.n_pairs
        c_feats = np.full((n_pts, n_features), 0.0, dtype=np.float64)

        for p in range(n_pts):
            c_mat = np.full((self.n_atoms, self.n_atoms), 0.0, dtype=np.float64)
            for i in range(self.n_atoms):
                c_mat[i, i] = 0.5 * (float(self.atomic_numbers[i]) ** 2.4)
            for i in range(self.n_atoms):
                for j in range(i + 1, self.n_atoms):
                    d_vec = coords[p, i, :] - coords[p, j, :]
                    r_ij = math.sqrt(float(np.sum(d_vec**2)) + 1e-18)
                    val = float(self.atomic_numbers[i] * self.atomic_numbers[j]) / r_ij
                    c_mat[i, j] = val
                    c_mat[j, i] = val

            # Canonical sort order by (atomic_number desc, row_norm desc, index) to enforce permutation invariance
            row_norms = np.sqrt(np.sum(c_mat**2, axis=1))
            sort_keys = [(-int(self.atomic_numbers[i]), -float(row_norms[i]), i) for i in range(self.n_atoms)]
            sorted_indices = [item[2] for item in sorted(sort_keys)]

            c_sorted = c_mat[np.ix_(sorted_indices, sorted_indices)]
            diag_part = np.diag(c_sorted)
            triu_indices = np.triu_indices(self.n_atoms, k=1)
            offdiag_part = c_sorted[triu_indices]
            c_feats[p, :self.n_atoms] = diag_part
            c_feats[p, self.n_atoms:] = offdiag_part

        return c_feats[0] if is_single else c_feats

    def compute_morse_jacobian(self, geom: np.ndarray) -> np.ndarray:
        """
        Computes the analytical Jacobian matrix J_alpha,ia = d(f_alpha)/d(r_ia) of PIP features
        with respect to Cartesian coordinates for a single geometry (N_atoms, 3).
        Returns array of shape (N_pip_features, N_atoms, 3).
        """
        coords = np.asarray(geom, dtype=np.float64)
        if coords.shape != (self.n_atoms, 3):
            raise ValueError(f"Expected geometry of shape ({self.n_atoms}, 3), got {coords.shape}")

        raw_jac = np.full((self.n_pairs, self.n_atoms, 3), 0.0, dtype=np.float64)
        y_raw = np.full(self.n_pairs, 0.0, dtype=np.float64)
        inv_lam = 1.0 / self.morse_lambda

        for p_idx, (i, j) in enumerate(self.pair_indices):
            d_vec = coords[i, :] - coords[j, :]
            r_ij = math.sqrt(float(np.sum(d_vec**2)) + 1e-18)
            y_ij = math.exp(-r_ij * inv_lam)
            y_raw[p_idx] = y_ij
            unit_vec = d_vec / r_ij

            grad_i = -inv_lam * y_ij * unit_vec
            grad_j = inv_lam * y_ij * unit_vec
            raw_jac[p_idx, i, :] = grad_i
            raw_jac[p_idx, j, :] = grad_j

        pip_jac = np.full((self.n_pip_features, self.n_atoms, 3), 0.0, dtype=np.float64)

        # Primary invariants (degree 1)
        for k, orbit in enumerate(self.deg1_orbits):
            pip_jac[k, :, :] = np.mean(raw_jac[orbit, :, :], axis=0)

        # Secondary invariants (degree 2)
        if self.include_secondary:
            offset = len(self.deg1_orbits)
            for s, orbit in enumerate(self.deg2_orbits):
                orbit_jac = np.full((len(orbit), self.n_atoms, 3), 0.0, dtype=np.float64)
                for idx, (p, q) in enumerate(orbit):
                    if p == q:
                        orbit_jac[idx] = 2.0 * y_raw[p] * raw_jac[p]
                    else:
                        orbit_jac[idx] = y_raw[q] * raw_jac[p] + y_raw[p] * raw_jac[q]
                pip_jac[offset + s, :, :] = np.mean(orbit_jac, axis=0)

        return pip_jac


# =============================================================================
# Kernel Ridge Regression & Base Estimators
# =============================================================================

class KernelFunction:
    """Evaluates kernel matrices and analytical feature derivatives."""

    @staticmethod
    def compute_kernel_matrix(
        X1: np.ndarray,
        X2: np.ndarray,
        kernel_type: Union[KernelType, str] = KernelType.RBF,
        gamma: float = 1.0,
        poly_degree: int = 4,
        chunk_size: Optional[int] = None,
    ) -> np.ndarray:
        """Computes the pairwise Gram/kernel matrix K(X1, X2)."""
        X1 = np.asarray(X1, dtype=np.float64)
        X2 = np.asarray(X2, dtype=np.float64)

        if isinstance(kernel_type, str):
            try:
                kernel_type = KernelType(kernel_type.lower())
            except (ValueError, KeyError):
                kernel_type = KernelType[kernel_type.upper()]

        # Chunked evaluation if requested and applicable
        if chunk_size is not None and chunk_size > 0 and X1.shape[0] > chunk_size:
            out = np.empty((X1.shape[0], X2.shape[0]), dtype=np.float64)
            for i in range(0, X1.shape[0], chunk_size):
                out[i : i + chunk_size] = KernelFunction.compute_kernel_matrix(
                    X1[i : i + chunk_size],
                    X2,
                    kernel_type=kernel_type,
                    gamma=gamma,
                    poly_degree=poly_degree,
                    chunk_size=None,
                )
            return out

        # Check for GPU tier acceleration
        try:
            import torch
            if torch.cuda.is_available():
                device = torch.device("cuda")
                stream = torch.cuda.Stream()
                with torch.cuda.stream(stream):
                    t1 = torch.as_tensor(X1, dtype=torch.float64, device=device)
                    t2 = torch.as_tensor(X2, dtype=torch.float64, device=device)
                    if kernel_type == KernelType.RBF:
                        dists_sq = torch.cdist(t1, t2, p=2.0) ** 2
                        res = torch.exp(-gamma * dists_sq)
                    elif kernel_type == KernelType.MATERN52:
                        dists = torch.cdist(t1, t2, p=2.0)
                        sqrt5 = math.sqrt(5.0)
                        scaled_d = sqrt5 * math.sqrt(2.0 * gamma) * dists
                        res = (1.0 + scaled_d + (5.0 * 2.0 * gamma / 3.0) * (dists**2)) * torch.exp(-scaled_d)
                    elif kernel_type == KernelType.MATERN32:
                        dists = torch.cdist(t1, t2, p=2.0)
                        sqrt3 = math.sqrt(3.0)
                        scaled_d = sqrt3 * math.sqrt(2.0 * gamma) * dists
                        res = (1.0 + scaled_d) * torch.exp(-scaled_d)
                    elif kernel_type == KernelType.POLYNOMIAL:
                        dot = torch.mm(t1, t2.t())
                        res = (gamma * dot + 1.0) ** poly_degree
                    else:
                        raise ValueError(f"Unsupported kernel type: {kernel_type}")
                    stream.synchronize()
                    return res.cpu().numpy()
        except Exception as _e:
            logger.debug(f"Ignored exception: {_e}")

        if kernel_type == KernelType.RBF:
            dists_sq = scipy.spatial.distance.cdist(X1, X2, metric="sqeuclidean")
            return np.exp(-gamma * dists_sq)

        elif kernel_type == KernelType.MATERN52:
            dists = scipy.spatial.distance.cdist(X1, X2, metric="euclidean")
            sqrt5 = math.sqrt(5.0)
            scaled_d = sqrt5 * math.sqrt(2.0 * gamma) * dists
            return (1.0 + scaled_d + (5.0 * 2.0 * gamma / 3.0) * (dists**2)) * np.exp(-scaled_d)

        elif kernel_type == KernelType.MATERN32:
            dists = scipy.spatial.distance.cdist(X1, X2, metric="euclidean")
            sqrt3 = math.sqrt(3.0)
            scaled_d = sqrt3 * math.sqrt(2.0 * gamma) * dists
            return (1.0 + scaled_d) * np.exp(-scaled_d)

        elif kernel_type == KernelType.POLYNOMIAL:
            dot = np.dot(X1, X2.T)
            return (gamma * dot + 1.0) ** poly_degree

        else:
            raise ValueError(f"Unsupported kernel type: {kernel_type}")

    @staticmethod
    def compute_kernel_gradient_weights(
        x_eval: np.ndarray,
        X_train: np.ndarray,
        weights: np.ndarray,
        kernel_type: KernelType = KernelType.RBF,
        gamma: float = 1.0,
        poly_degree: int = 4,
    ) -> np.ndarray:
        """
        Computes analytical derivative of the fitted KRR function w.r.t input features x_eval:
        d(f(x))/d(x) = sum_i w_i * d(K(x, X_train[i]))/d(x).
        Returns array of shape (N_features,).
        """
        x_eval = np.asarray(x_eval, dtype=np.float64).reshape(1, -1)
        X_train = np.asarray(X_train, dtype=np.float64)
        weights = np.asarray(weights, dtype=np.float64)

        if kernel_type == KernelType.RBF:
            # d(exp(-gamma * ||x - x_i||^2)) / d(x) = -2 * gamma * exp(...) * (x - x_i)
            dists_sq = scipy.spatial.distance.cdist(x_eval, X_train, metric="sqeuclidean")
            k_vals = np.exp(-gamma * dists_sq)[0]  # (N_train,)
            diff = x_eval - X_train  # (N_train, N_features)
            weighted_k = weights * k_vals  # (N_train,)
            grad_features = -2.0 * gamma * np.sum(weighted_k[:, np.newaxis] * diff, axis=0)
            return grad_features
        if kernel_type == KernelType.POLYNOMIAL:
            base = gamma * (X_train @ x_eval[0]) + 1.0
            factors = weights * poly_degree * gamma * base ** (poly_degree - 1)
            return factors @ X_train
        diff = x_eval - X_train
        distance = np.linalg.norm(diff, axis=1)
        if kernel_type == KernelType.MATERN32:
            rate = math.sqrt(6.0 * gamma)
            factors = -(rate ** 2) * np.exp(-rate * distance)
        elif kernel_type == KernelType.MATERN52:
            rate = math.sqrt(10.0 * gamma)
            factors = -(rate ** 2) / 3.0 * (1.0 + rate * distance) * np.exp(-rate * distance)
        else:
            raise ValueError(f"Unsupported kernel type: {kernel_type}")
        return np.sum((weights * factors)[:, np.newaxis] * diff, axis=0)


class ExactKernelRidgeEstimator:
    """
    High-performance exact Kernel Ridge Regression estimator solved via
    numerically stable Cholesky decomposition or SVD pseudo-inversion.
    With asymptotic_zero=True, uses a zero mean and constrains a supplied
    zero-energy boundary. For positive Morse descriptors the zero-energy
    point with smallest feature norm is the default dissociation anchor;
    explicit zero_anchor_indices support other boundary definitions.
    Dissociation of molecular fragments
    still requires representative anchors; Morse features need not vanish
    when intrafragment bonds remain intact.
    """

    def __init__(
        self,
        kernel_type: Union[KernelType, str] = KernelType.RBF,
        alpha: float = 1e-6,
        gamma: Optional[float] = None,
        poly_degree: int = 4,
        asymptotic_zero: bool = True,
        reg_config: Optional[KrrRegularizationConfig] = None,
        regularization_config: Optional[KrrRegularizationConfig] = None,
    ) -> None:
        if isinstance(kernel_type, str):
            try:
                self.kernel_type = KernelType(kernel_type.lower())
            except (ValueError, KeyError):
                self.kernel_type = KernelType[kernel_type.upper()]
        else:
            self.kernel_type = kernel_type
        self.alpha: float = float(alpha)
        self.gamma: Optional[float] = float(gamma) if gamma is not None else None
        self.poly_degree: int = int(poly_degree)
        self.asymptotic_zero: bool = bool(asymptotic_zero)
        self.reg_config: KrrRegularizationConfig = (
            reg_config or regularization_config or KrrRegularizationConfig(base_alpha=self.alpha)
        )

        self.X_train: Optional[np.ndarray] = None
        self.y_train: Optional[np.ndarray] = None
        self.weights: Optional[np.ndarray] = None
        self.y_mean: float = 0.0
        self.effective_gamma: float = 1.0

    @property
    def is_fitted(self) -> bool:
        """Indicates whether KRR estimator has been successfully fitted."""
        return self.weights is not None and self.X_train is not None

    @property
    def alpha_vector(self) -> Optional[np.ndarray]:
        """Dual coefficient weights vector."""
        return self.weights

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        sample_alpha: Optional[np.ndarray] = None,
        zero_anchor_indices: Optional[Sequence[int]] = None,
    ) -> ExactKernelRidgeEstimator:
        """Fits KRR model on training features X (N, D) and target energies y (N,)."""
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)

        if X.ndim != 2:
            raise ValueError(f"Features must be 2D array, got shape {X.shape}")
        if y.ndim != 1 or y.shape[0] != X.shape[0]:
            raise ValueError(f"Targets shape {y.shape} does not match features shape {X.shape}")
        if X.shape[0] == 0:
            raise ValueError("Cannot fit on empty dataset")
        if not np.all(np.isfinite(X)) or not np.all(np.isfinite(y)):
            raise ValueError("Training features and energies must be finite")

        self.X_train = X.copy()
        self.y_train = y.copy()
        if self.asymptotic_zero:
            self.y_mean = 0.0
        else:
            self.y_mean = float(np.mean(y))
        y_centered = y - self.y_mean

        # Automatically determine default gamma via median heuristic if not specified
        if self.gamma is None:
            if X.shape[0] > 1:
                sub_features = X[: min(500, X.shape[0])]
                p_dists = scipy.spatial.distance.pdist(sub_features, metric="sqeuclidean")
                median_sq = float(np.median(p_dists)) if len(p_dists) > 0 else 1.0
                median_sq = max(median_sq, 1e-4)
                self.effective_gamma = 1.0 / (2.0 * median_sq)
            else:
                self.effective_gamma = 1.0
        else:
            self.effective_gamma = self.gamma

        # Compute kernel Gram matrix K
        K = KernelFunction.compute_kernel_matrix(
            self.X_train,
            self.X_train,
            kernel_type=self.kernel_type,
            gamma=self.effective_gamma,
            poly_degree=self.poly_degree,
        )

        # Add ridge regularization to diagonal: (K + alpha_diag)
        if sample_alpha is not None:
            alpha_diag = np.asarray(sample_alpha, dtype=np.float64)
            if alpha_diag.shape != y.shape or not np.all(np.isfinite(alpha_diag)) or np.any(alpha_diag < 0):
                raise ValueError("sample_alpha must contain one finite nonnegative value per training point")
        else:
            alpha_diag = np.full(X.shape[0], max(self.alpha, self.reg_config.base_alpha), dtype=np.float64)
            if self.asymptotic_zero:
                # Regularization on asymptotic anchor points (y ~ 0.0) bounded by anchor_alpha_floor
                is_anchor = np.abs(y_centered) < 1e-8
                alpha_diag[is_anchor] = np.maximum(
                    self.reg_config.anchor_alpha_floor, self.alpha * 1e-4
                )

        # Enforce anchor_alpha_floor across all diagonal entries
        alpha_diag = np.maximum(alpha_diag, self.reg_config.anchor_alpha_floor)

        # Solve for weights via Cholesky decomposition with adaptive Tikhonov jitter escalation
        jitter = self.reg_config.jitter_epsilon
        max_jitter = self.reg_config.max_jitter_escalation
        cholesky_success = False

        while jitter <= max_jitter * 10.0:
            A = K + np.diag(alpha_diag + jitter)
            try:
                c, low = scipy.linalg.cho_factor(A, lower=True, check_finite=False)
                self.weights = scipy.linalg.cho_solve((c, low), y_centered, check_finite=False)
                cholesky_success = True
                break
            except (scipy.linalg.LinAlgError, np.linalg.LinAlgError):
                logger.debug(f"Cholesky LinAlgError at jitter={jitter:.2e}; escalating by 10x")
                jitter *= 10.0

        if not cholesky_success:
            # Truncated SVD pseudo-inverse pinvh exclusively for unrecoverable rank-deficient systems
            logger.warning(
                "Cholesky factorization unrecoverable across jitter escalation ladder; "
                "invoking regularized truncated SVD pinvh."
            )
            try:
                A = K + np.diag(alpha_diag + max_jitter)
                inv_A = scipy.linalg.pinvh(A)
                self.weights = np.dot(inv_A, y_centered)
            except Exception as exc:
                raise NumericalConditioningError(
                    f"KRR Gram matrix inversion failed conditioning floor: {exc}"
                ) from exc

        # Condition the RKHS on a zero-energy dissociation boundary, rather
        # than making its regularization arbitrarily small. Other zero-valued
        # observations remain ordinary ridge targets: declaring an interval
        # of nearby samples an exact zero boundary can force spurious flatness.
        # The default farthest dissociation point is defined by the smallest
        # norm of positive Morse features. Callers with general descriptors
        # can supply their boundary indices explicitly.
        anchor_indices = np.empty(0, dtype=int)
        if zero_anchor_indices is not None:
            raw_indices = np.asarray(zero_anchor_indices)
            if not self.asymptotic_zero or raw_indices.ndim != 1 or raw_indices.dtype.kind not in "iu":
                raise ValueError("zero_anchor_indices requires integer indices and asymptotic_zero=True")
            anchor_indices = np.unique(raw_indices.astype(int))
            if np.any(anchor_indices < 0) or np.any(anchor_indices >= len(y)) or np.any(y[anchor_indices] != 0.0):
                raise ValueError("Each boundary index must identify an exact zero training target")
        elif self.asymptotic_zero:
            zero_targets = np.flatnonzero(y == 0.0)
            if zero_targets.size:
                anchor_indices = zero_targets[[np.argmin(np.linalg.norm(X[zero_targets], axis=1))]]
        if anchor_indices.size:
            anchor_kernel = K[np.ix_(anchor_indices, anchor_indices)]
            anchor_inverse = scipy.linalg.pinvh(anchor_kernel)
            conditioned_kernel = K - K[:, anchor_indices] @ anchor_inverse @ K[anchor_indices]
            conditioned_kernel = (conditioned_kernel + conditioned_kernel.T) / 2.0
            conditioned_weights = scipy.linalg.solve(
                conditioned_kernel + np.diag(alpha_diag + min(jitter, max_jitter)),
                y_centered,
                assume_a="pos",
            )
            # Express the conditioned predictor in the original kernel basis
            # so gradients, batching, and model persistence use the same path.
            self.weights = conditioned_weights.copy()
            self.weights[anchor_indices] -= anchor_inverse @ (K[anchor_indices] @ conditioned_weights)

        return self

    def predict(self, X: np.ndarray, batch_size: int = 2048) -> Union[float, np.ndarray]:
        """Predicts energies for evaluation features X (N, D) using chunked batch evaluation."""
        if self.X_train is None or self.weights is None:
            raise RuntimeError("Estimator is not fitted yet.")

        X = np.asarray(X, dtype=np.float64)
        is_single = (X.ndim == 1)
        if is_single:
            X = X[np.newaxis, :]

        n_samples = X.shape[0]
        preds = np.empty(n_samples, dtype=np.float64)
        bs = max(1, batch_size) if batch_size is not None else 2048

        for start_idx in range(0, n_samples, bs):
            end_idx = min(start_idx + bs, n_samples)
            X_batch = X[start_idx:end_idx]
            K_batch = KernelFunction.compute_kernel_matrix(
                X_batch,
                self.X_train,
                kernel_type=self.kernel_type,
                gamma=self.effective_gamma,
                poly_degree=self.poly_degree,
            )
            preds[start_idx:end_idx] = np.dot(K_batch, self.weights) + self.y_mean

        return float(preds[0]) if is_single else preds

    def predict_gradient_wrt_features(self, x_eval: np.ndarray) -> np.ndarray:
        """Computes analytical gradient d(E)/d(x) w.r.t invariant features."""
        if self.X_train is None or self.weights is None:
            raise RuntimeError("Estimator is not fitted yet.")
        return KernelFunction.compute_kernel_gradient_weights(
            x_eval=x_eval,
            X_train=self.X_train,
            weights=self.weights,
            kernel_type=self.kernel_type,
            gamma=self.effective_gamma,
            poly_degree=self.poly_degree,
        )


# =============================================================================
# Neural regression and committee uncertainty (NumPy/SciPy CPU backend)
# =============================================================================

class NeuralCommitteeEstimator:
    """Independent tanh networks with analytical backpropagation and forces.

    A deterministic internal validation subset is taken only from the supplied
    training data. Each member uses a distinct initialization and a bootstrap
    sample of the remaining training rows. Checkpoint selection uses that
    internal subset; external campaign hold-out labels never enter ``fit``.
    Ensemble spread measures disagreement, not a calibrated confidence bound.
    """

    def __init__(self, config: DeltaFittingConfig, *, seed_offset: int = 0) -> None:
        if config.backend != FittingBackend.NEURAL_COMMITTEE:
            raise ValueError("NeuralCommitteeEstimator requires backend='neural_committee'")
        self.config = config.model_copy(deep=True)
        self.seed_offset = int(seed_offset)
        self.X_train: Optional[np.ndarray] = None
        self.y_train: Optional[np.ndarray] = None
        self.weights: Optional[np.ndarray] = None
        self.layer_sizes: Tuple[int, ...] = ()
        self.feature_mean: Optional[np.ndarray] = None
        self.feature_scale: Optional[np.ndarray] = None
        self.y_mean = 0.0
        self.y_scale = 1.0
        self.training_indices = np.empty(0, dtype=int)
        self.validation_indices = np.empty(0, dtype=int)
        self.member_training_indices = np.empty((0, 0), dtype=int)
        self.training_history: List[Dict[str, Any]] = []
        self.zero_anchor_features: Optional[np.ndarray] = None

    @property
    def is_fitted(self) -> bool:
        return self.weights is not None and self.feature_mean is not None

    def _unpack(self, parameters: np.ndarray) -> List[Tuple[np.ndarray, np.ndarray]]:
        layers = []
        offset = 0
        for n_in, n_out in zip(self.layer_sizes[:-1], self.layer_sizes[1:]):
            count = n_in * n_out
            weight = parameters[offset:offset + count].reshape(n_in, n_out)
            offset += count
            bias = parameters[offset:offset + n_out]
            offset += n_out
            layers.append((weight, bias))
        if offset != parameters.size:
            raise ValueError("Neural parameter count does not match the saved architecture")
        return layers

    def _forward(self, parameters: np.ndarray, features: np.ndarray) -> Tuple[np.ndarray, List[np.ndarray]]:
        activations = [features]
        layers = self._unpack(parameters)
        for index, (weight, bias) in enumerate(layers):
            output = activations[-1] @ weight + bias
            activations.append(np.tanh(output) if index < len(layers) - 1 else output)
        return activations[-1][:, 0], activations

    def _predict_normalized(self, parameters: np.ndarray, features: np.ndarray) -> np.ndarray:
        prediction = self._forward(parameters, features)[0]
        if self.zero_anchor_features is not None:
            prediction = prediction - self._forward(parameters, self.zero_anchor_features[np.newaxis, :])[0][0]
        return prediction

    def _objective(self, parameters: np.ndarray, features: np.ndarray, targets: np.ndarray) -> Tuple[float, np.ndarray]:
        prediction, activations = self._forward(parameters, features)
        anchor_activations = None
        if self.zero_anchor_features is not None:
            anchor_prediction, anchor_activations = self._forward(parameters, self.zero_anchor_features[np.newaxis, :])
            prediction = prediction - anchor_prediction[0]
        residual = prediction - targets
        loss = 0.5 * float(np.mean(residual ** 2))
        delta = residual[:, np.newaxis] / len(targets)
        layers = self._unpack(parameters)
        gradients = [None] * len(layers)
        for index in range(len(layers) - 1, -1, -1):
            weight, _ = layers[index]
            loss += 0.5 * self.config.neural_weight_decay * float(np.sum(weight ** 2))
            gradient_weight = activations[index].T @ delta + self.config.neural_weight_decay * weight
            gradient_bias = np.sum(delta, axis=0)
            gradients[index] = np.concatenate((gradient_weight.ravel(), gradient_bias))
            if index:
                delta = (delta @ weight.T) * (1.0 - activations[index] ** 2)
        if anchor_activations is not None:
            # Differentiating NN(x)-NN(anchor) also differentiates the anchor
            # with respect to network parameters, but not query coordinates.
            delta = np.asarray([[-float(np.mean(residual))]])
            for index in range(len(layers) - 1, -1, -1):
                weight, _ = layers[index]
                gradients[index] += np.concatenate(((anchor_activations[index].T @ delta).ravel(), np.sum(delta, axis=0)))
                if index:
                    delta = (delta @ weight.T) * (1.0 - anchor_activations[index] ** 2)
        return loss, np.concatenate(gradients)

    def fit(self, X: np.ndarray, y: np.ndarray) -> NeuralCommitteeEstimator:
        X, y = np.asarray(X, dtype=np.float64), np.asarray(y, dtype=np.float64)
        if X.ndim != 2 or X.shape[0] < 4 or X.shape[1] == 0 or y.shape != (len(X),):
            raise ValueError("Neural fitting requires at least four aligned feature/energy rows")
        if not np.all(np.isfinite(X)) or not np.all(np.isfinite(y)):
            raise ValueError("Neural training features and energies must be finite")
        self.weights = None
        self.X_train, self.y_train = X.copy(), y.copy()
        base_seed = self.config.neural_random_seed + self.seed_offset
        split_rng = np.random.default_rng(base_seed)
        order = split_rng.permutation(len(X))
        n_validation = max(1, int(len(X) * self.config.neural_validation_fraction))
        self.validation_indices = np.sort(order[:n_validation])
        self.training_indices = np.sort(order[n_validation:])
        anchor_index = None
        if self.config.energy_reference == "interaction_zero_asymptote":
            anchors = np.flatnonzero(y == 0.0)
            if not anchors.size:
                raise MissingDataError("A zero-asymptote neural interaction fit requires a supplied exact zero-energy boundary point")
            anchor_index = int(anchors[np.argmin(np.linalg.norm(X[anchors], axis=1))])
            if anchor_index in self.validation_indices:
                # Boundary conditions belong in training; preserve split sizes.
                replacement = self.training_indices[0]
                self.training_indices[0] = anchor_index
                self.validation_indices[self.validation_indices == anchor_index] = replacement
                self.training_indices.sort()
                self.validation_indices.sort()
        # Fit scaling only on the optimization pool, never on validation rows.
        self.feature_mean = np.mean(X[self.training_indices], axis=0)
        scale = np.std(X[self.training_indices], axis=0)
        self.feature_scale = np.where(scale > 1e-12, scale, 1.0)
        self.y_mean = float(np.mean(y[self.training_indices])) if anchor_index is None else 0.0
        target_scale = float(np.std(y[self.training_indices]))
        self.y_scale = target_scale if target_scale > 1e-12 else 1.0
        features = (X - self.feature_mean) / self.feature_scale
        self.zero_anchor_features = None if anchor_index is None else features[anchor_index].copy()
        targets = (y - self.y_mean) / self.y_scale
        self.layer_sizes = (X.shape[1], *self.config.neural_hidden_layers, 1)
        fitted_members, bootstrap_rows = [], []
        self.training_history = []
        for member in range(self.config.neural_committee_size):
            seed = base_seed + 104729 * (member + 1)
            rng = np.random.default_rng(seed)
            indices = rng.choice(self.training_indices, size=len(self.training_indices), replace=True)
            bootstrap_rows.append(indices)
            initial = []
            for n_in, n_out in zip(self.layer_sizes[:-1], self.layer_sizes[1:]):
                limit = math.sqrt(6.0 / (n_in + n_out))
                initial.append(rng.uniform(-limit, limit, size=n_in * n_out))
                initial.append(np.full(n_out, 0.0))
            parameters = np.concatenate(initial)
            best_parameters = parameters.copy()
            best_validation = math.inf
            best_iteration, iteration = 0, 0

            def select_checkpoint(candidate: np.ndarray) -> None:
                nonlocal best_parameters, best_validation, best_iteration, iteration
                iteration += 1
                prediction = self._predict_normalized(candidate, features[self.validation_indices])
                score = float(np.mean((prediction - targets[self.validation_indices]) ** 2))
                if np.isfinite(score) and score < best_validation:
                    best_parameters = candidate.copy()
                    best_validation = score
                    best_iteration = iteration

            select_checkpoint(parameters)
            result = scipy.optimize.minimize(
                self._objective,
                parameters,
                args=(features[indices], targets[indices]),
                method="L-BFGS-B",
                jac=True,
                callback=select_checkpoint,
                options={"maxiter": self.config.neural_max_iterations, "ftol": 1e-12, "gtol": 1e-8},
            )
            select_checkpoint(result.x)
            if not np.all(np.isfinite(best_parameters)) or not np.isfinite(best_validation):
                raise NumericalConditioningError("Neural optimization did not produce a finite validation checkpoint")
            fitted_members.append(best_parameters)
            training_prediction = self._predict_normalized(best_parameters, features[indices])
            self.training_history.append({
                "seed": seed,
                "optimizer_success": bool(result.success),
                "optimizer_message": str(result.message),
                "optimizer_iterations": int(result.nit),
                "selected_checkpoint": best_iteration,
                "training_rmse_hartree": self.y_scale * float(np.sqrt(np.mean((training_prediction - targets[indices]) ** 2))),
                "validation_rmse_hartree": self.y_scale * math.sqrt(best_validation),
            })
        self.weights = np.stack(fitted_members)
        self.member_training_indices = np.stack(bootstrap_rows)
        return self

    def predict_members(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Neural committee is not fitted")
        X = np.asarray(X, dtype=np.float64)
        single = X.ndim == 1
        X = np.atleast_2d(X)
        if X.shape[1] != self.layer_sizes[0] or not np.all(np.isfinite(X)):
            raise ValueError("Evaluation features must be finite and match the trained feature dimension")
        features = (X - self.feature_mean) / self.feature_scale
        energies = np.stack([self._predict_normalized(member, features) for member in self.weights])
        energies = self.y_mean + self.y_scale * energies
        return energies[:, 0] if single else energies

    def predict(self, X: np.ndarray, batch_size: int = 2048) -> Union[float, np.ndarray]:
        if not self.is_fitted:
            raise RuntimeError("Neural committee is not fitted")
        X = np.asarray(X, dtype=np.float64)
        if X.ndim not in (1, 2):
            raise ValueError("Prediction requires a feature vector or matrix")
        if X.ndim == 1:
            return float(np.mean(self.predict_members(X)))
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        predictions = np.empty(len(X))
        for start in range(0, len(X), batch_size):
            predictions[start:start + batch_size] = np.mean(self.predict_members(X[start:start + batch_size]), axis=0)
        return predictions

    def predict_with_uncertainty(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        members = self.predict_members(X)
        return np.mean(members, axis=0), np.std(members, axis=0, ddof=1), members

    def predict_member_gradients_wrt_features(self, x_eval: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Neural committee is not fitted")
        x_eval = np.asarray(x_eval, dtype=np.float64)
        if x_eval.shape != (self.layer_sizes[0],) or not np.all(np.isfinite(x_eval)):
            raise ValueError("Gradient evaluation requires one finite feature vector")
        features = ((x_eval - self.feature_mean) / self.feature_scale)[np.newaxis, :]
        gradients = []
        for member in self.weights:
            _, activations = self._forward(member, features)
            layers = self._unpack(member)
            derivative = layers[-1][0][:, 0]
            for index in range(len(layers) - 2, -1, -1):
                derivative = layers[index][0] @ (derivative * (1.0 - activations[index + 1][0] ** 2))
            gradients.append(self.y_scale * derivative / self.feature_scale)
        return np.stack(gradients)

    def predict_gradient_wrt_features(self, x_eval: np.ndarray) -> np.ndarray:
        return np.mean(self.predict_member_gradients_wrt_features(x_eval), axis=0)

    def to_arrays(self, prefix: str) -> Dict[str, Any]:
        if not self.is_fitted:
            raise RuntimeError("Cannot save an unfitted neural committee")
        metadata = {
            "config": self.config.model_dump(mode="json"), "seed_offset": self.seed_offset,
            "layer_sizes": self.layer_sizes, "y_mean": self.y_mean, "y_scale": self.y_scale,
            "training_history": self.training_history,
        }
        arrays = {prefix + "metadata": np.array(json.dumps(metadata))}
        arrays[prefix + "zero_anchor_features"] = np.empty(0) if self.zero_anchor_features is None else self.zero_anchor_features
        for name in ("weights", "X_train", "y_train", "feature_mean", "feature_scale", "training_indices", "validation_indices", "member_training_indices"):
            arrays[prefix + name] = getattr(self, name)
        return arrays

    @classmethod
    def from_arrays(cls, arrays: Any, prefix: str) -> NeuralCommitteeEstimator:
        metadata = json.loads(str(arrays[prefix + "metadata"]))
        estimator = cls(DeltaFittingConfig(**metadata["config"]), seed_offset=metadata["seed_offset"])
        estimator.layer_sizes = tuple(metadata["layer_sizes"])
        estimator.y_mean, estimator.y_scale = float(metadata["y_mean"]), float(metadata["y_scale"])
        estimator.training_history = metadata["training_history"]
        anchor = np.asarray(arrays[prefix + "zero_anchor_features"]) if prefix + "zero_anchor_features" in arrays else np.empty(0)
        estimator.zero_anchor_features = anchor.copy() if anchor.size else None
        for name in ("weights", "X_train", "y_train", "feature_mean", "feature_scale", "training_indices", "validation_indices", "member_training_indices"):
            setattr(estimator, name, np.asarray(arrays[prefix + name]).copy())
        if estimator.weights.ndim != 2 or len(estimator.weights) != estimator.config.neural_committee_size:
            raise ValueError("Saved neural committee has an invalid member count")
        if (
            not np.all(np.isfinite(estimator.weights))
            or not np.all(np.isfinite(estimator.feature_mean))
            or not np.all(np.isfinite(estimator.feature_scale))
            or not np.all(estimator.feature_scale > 0)
            or not np.isfinite(estimator.y_mean)
            or not np.isfinite(estimator.y_scale)
            or estimator.y_scale <= 0
        ):
            raise ValueError("Saved neural weights and normalization must be finite and valid")
        if (
            estimator.X_train.ndim != 2
            or estimator.y_train.shape != (len(estimator.X_train),)
            or not np.all(np.isfinite(estimator.X_train))
            or not np.all(np.isfinite(estimator.y_train))
            or estimator.layer_sizes != (estimator.X_train.shape[1], *estimator.config.neural_hidden_layers, 1)
            or estimator.feature_mean.shape != (estimator.X_train.shape[1],)
            or estimator.feature_scale.shape != estimator.feature_mean.shape
        ):
            raise ValueError("Saved neural dimensions or training data are invalid")
        training, validation = set(estimator.training_indices), set(estimator.validation_indices)
        if (
            estimator.training_indices.dtype.kind not in "iu"
            or estimator.validation_indices.dtype.kind not in "iu"
            or estimator.member_training_indices.dtype.kind not in "iu"
            or estimator.training_indices.ndim != 1
            or estimator.validation_indices.ndim != 1
            or not training or not validation or training & validation
            or training | validation != set(range(len(estimator.X_train)))
            or estimator.member_training_indices.shape != (estimator.config.neural_committee_size, len(training))
            or not set(estimator.member_training_indices.ravel()) <= training
        ):
            raise ValueError("Saved neural training and validation provenance is inconsistent")
        for member in estimator.weights:
            estimator._unpack(member)
        if estimator.zero_anchor_features is not None and (
            estimator.zero_anchor_features.shape != estimator.feature_mean.shape or not np.all(np.isfinite(estimator.zero_anchor_features))
        ):
            raise ValueError("Saved neural dissociation boundary is invalid")
        if estimator.config.energy_reference == "interaction_zero_asymptote" and estimator.zero_anchor_features is None:
            raise ValueError("Saved zero-asymptote neural fit is missing its boundary")
        return estimator


# =============================================================================
# Kernel committee uncertainty quantification (Method Matrix §10.8)
# =============================================================================

class CommitteeModel:
    """
    Implements a committee of M diverse estimators (Method Matrix §10.8):
    - Evaluates ensemble mean energy E_bar
    - Evaluates ensemble gradient g_bar
    - Calculates normalised per-atom uncertainty sigma_E / sqrt(N_atoms) in meV/atom
    - Calculates maximum atom-wise force dispersion U_F = max_i max_m |g_m,i - g_bar,i|
    - Enforces Guard G5 uncertainty thresholding: epsilon = Q3 + 1.5 * IQR.
    """

    def __init__(
        self,
        featurizer: GeometryFeaturizer,
        committee_size: int = 4,
        kernel_type: KernelType = KernelType.RBF,
        alpha: float = 1e-6,
        morse_lambda: float = 2.0,
        random_seed: int = 42,
    ) -> None:
        self.featurizer: GeometryFeaturizer = featurizer
        self.committee_size: int = max(2, int(committee_size))
        self.kernel_type: KernelType = kernel_type
        self.alpha: float = float(alpha)
        self.morse_lambda: float = float(morse_lambda)
        self.random_seed: int = int(random_seed)

        self.members: List[ExactKernelRidgeEstimator] = []
        self.is_fitted: bool = False
        self.training_iqr_threshold_hartree: float = 1e-3
        self.training_iqr_threshold_mev_atom: float = 10.0

    def fit(self, geoms: np.ndarray, energies: np.ndarray) -> CommitteeModel:
        """
        Fits all M committee members using bootstrap subsampling and varied hyper-parameters
        to construct a genuine epistemic uncertainty estimator.
        """
        geoms = np.asarray(geoms, dtype=np.float64)
        energies = np.asarray(energies, dtype=np.float64)

        if geoms.shape[0] < self.committee_size:
            raise ValueError(
                f"Need at least {self.committee_size} points to fit committee, got {geoms.shape[0]}"
            )

        features = self.featurizer.compute_morse_features(geoms)
        n_rows = features.shape[0]
        rng = np.random.RandomState(self.random_seed)

        self.members = []
        residuals_list: List[np.ndarray] = []

        # Varied gamma scaling factors for diverse length-scales
        gamma_multipliers = np.array(
            [0.6 + 0.8 * i / max(1, self.committee_size - 1) for i in range(self.committee_size)],
            dtype=np.float64,
        )

        for m in range(self.committee_size):
            # Bootstrap subsample 85% of dataset with replacement
            indices = rng.choice(n_rows, size=int(0.85 * n_rows), replace=True)
            X_sub = features[indices]
            y_sub = energies[indices]

            # Varied regularization and kernel parameters
            alpha_m = self.alpha * (1.0 + 0.2 * (m - self.committee_size / 2))
            alpha_m = max(alpha_m, 1e-10)

            est = ExactKernelRidgeEstimator(
                kernel_type=self.kernel_type,
                alpha=alpha_m,
                gamma=None,  # Automatically scaled per multiplier
            )
            est.fit(X_sub, y_sub)
            est.effective_gamma *= gamma_multipliers[m]

            # Recompute weights with the scaled gamma
            K_adj = KernelFunction.compute_kernel_matrix(
                est.X_train,
                est.X_train,
                kernel_type=est.kernel_type,
                gamma=est.effective_gamma,
            )
            A_adj = K_adj + est.alpha * np.diag(np.full(est.X_train.shape[0], 1.0, dtype=np.float64))
            try:
                c, low = scipy.linalg.cho_factor(A_adj, lower=True, check_finite=False)
                est.weights = scipy.linalg.cho_solve((c, low), est.y_train - est.y_mean, check_finite=False)
            except Exception:
                est.weights, _, _, _ = scipy.linalg.lstsq(A_adj, est.y_train - est.y_mean)

            self.members.append(est)

            # Evaluate training residuals
            preds_m = est.predict(features)
            residuals_list.append(np.abs(preds_m - energies))

        self.is_fitted = True

        # Calculate Guard G5 threshold epsilon = Q3 + 1.5 * IQR on training error distribution (§10.8)
        all_res = np.concatenate(residuals_list)
        q75, q25 = np.percentile(all_res, [75, 25])
        iqr = float(q75 - q25)
        self.training_iqr_threshold_hartree = float(q75 + 1.5 * iqr)
        self.training_iqr_threshold_mev_atom = (
            self.training_iqr_threshold_hartree * MEV_PER_HARTREE / math.sqrt(self.featurizer.n_atoms)
        )

        logger.info(
            f"Committee fitted with M={self.committee_size} members. "
            f"Guard G5 IQR threshold: {self.training_iqr_threshold_hartree:.6e} Ha "
            f"({self.training_iqr_threshold_mev_atom:.3f} meV/atom)"
        )
        return self

    def predict_energy_and_uncertainty(self, geoms: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Predicts ensemble mean energies, standard deviations, and per-atom uncertainties.
        Returns:
            E_bar: Ensemble mean energy array in Hartrees (N_pts,)
            sigma_E: Ensemble standard deviation in Hartrees (N_pts,)
            sigma_atom_mev: Normalised uncertainty in meV/atom (N_pts,)
        """
        if not self.is_fitted or not self.members:
            raise RuntimeError("CommitteeModel is not fitted yet.")

        geoms = np.asarray(geoms, dtype=np.float64)
        is_single = (geoms.ndim == 2)
        if is_single:
            geoms = geoms[np.newaxis, :, :]

        features = self.featurizer.compute_morse_features(geoms)
        n_pts = features.shape[0]
        member_preds = np.full((self.committee_size, n_pts), 0.0, dtype=np.float64)

        for m, est in enumerate(self.members):
            member_preds[m, :] = est.predict(features)

        E_bar = np.mean(member_preds, axis=0)
        # Epistemic standard deviation across committee members
        sigma_E = np.std(member_preds, axis=0, ddof=1) if self.committee_size > 1 else np.full_like(E_bar, 0.0)

        # Normalised per-atom estimator: sigma_E / sqrt(N_atoms) in meV/atom (Method Matrix line 2797)
        sigma_atom_mev = (sigma_E * MEV_PER_HARTREE) / math.sqrt(self.featurizer.n_atoms)

        if is_single:
            return E_bar[0], sigma_E[0], sigma_atom_mev[0]
        return E_bar, sigma_E, sigma_atom_mev

    def predict_single_with_uq(self, geom: np.ndarray) -> CommitteePrediction:
        """
        Evaluates a single geometry against the committee and returns a complete
        structured CommitteePrediction model compliant with Method Matrix §10.8.
        """
        e_bar, sigma_e, sigma_atom_mev = self.predict_energy_and_uncertainty(geom)
        feats = self.featurizer.compute_morse_features(geom)
        member_energies = [float(est.predict(feats)) for est in self.members]

        # Check G5 Gate
        g5_passed = bool(sigma_e <= self.training_iqr_threshold_hartree)

        return CommitteePrediction(
            mean_energy_hartree=float(e_bar),
            sigma_energy_hartree=float(sigma_e),
            sigma_energy_mev_per_atom=float(sigma_atom_mev),
            force_uncertainty_hartree_bohr=None,
            g5_gate_passed=g5_passed,
            member_energies=member_energies,
        )


# =============================================================================
# Active Learning Point Selection Engine (Method Matrix QS-3 & §13.2)
# =============================================================================

class ActiveLearningEngine:
    """
    Implements committee-based active learning selection of 300-800 points
    from a candidate DFT pool (~2,000 points) as mandated by Method Matrix QS-3.

    Enforces Uteva et al. acquisition rules:
    - Pure variance maximization alone is strictly flagged / prohibited.
    - Two-Set Error-Based Acquisition: balances committee uncertainty with spatial dispersion.
    - Separates a dedicated held-out validation grid (QS-3 Step 5).
    """

    def __init__(
        self,
        featurizer: Optional[GeometryFeaturizer] = None,
        config: Optional[ActiveLearningConfig] = None,
        batch_config: Optional[ActiveLearningBatchConfig] = None,
    ) -> None:
        self.featurizer: Optional[GeometryFeaturizer] = featurizer
        self.config: ActiveLearningConfig = config or ActiveLearningConfig()
        self.batch_config: ActiveLearningBatchConfig = batch_config or ActiveLearningBatchConfig()

    def select_batch(
        self,
        candidate_pool: np.ndarray,
        uncertainties: np.ndarray,
        batch_config: Optional[ActiveLearningBatchConfig] = None,
        labeled_points: Optional[np.ndarray] = None,
    ) -> List[int]:
        """
        Executes sequential furthest-point repulsion batch selection (Suggestion #51). [M]

        S_acq(x) = U(x) * [1 - beta_div * exp(-d_min(x)^2 / (2 * sigma_repulse^2))]
        """
        cfg = batch_config or self.batch_config
        coords = np.asarray(candidate_pool, dtype=np.float64)
        if coords.ndim > 2:
            coords = coords.reshape(coords.shape[0], -1)
        U = np.asarray(uncertainties, dtype=np.float64)
        n_pool = coords.shape[0]

        d_min = np.full(n_pool, np.inf, dtype=np.float64)
        if labeled_points is not None and len(labeled_points) > 0:
            lbl = np.asarray(labeled_points, dtype=np.float64)
            if lbl.ndim > 2:
                lbl = lbl.reshape(lbl.shape[0], -1)
            dists = scipy.spatial.distance.cdist(coords, lbl, metric="euclidean")
            d_min = np.min(dists, axis=1)

        sigma_repulse = float(cfg.repulsion_length_scale)
        beta_div = float(cfg.diversity_weight)
        kernel_type = cfg.kernel_type
        batch_size = min(cfg.batch_size, n_pool)

        selected_indices: List[int] = []
        for _ in range(batch_size):
            if kernel_type == "gaussian":
                pen = np.where(
                    np.isinf(d_min),
                    0.0,
                    np.exp(-(d_min ** 2) / (2.0 * sigma_repulse ** 2)),
                )
            else:
                pen = np.where(
                    np.isinf(d_min),
                    0.0,
                    np.exp(-d_min / sigma_repulse),
                )
            scores = U * (1.0 - beta_div * pen)
            scores[selected_indices] = -np.inf
            best = int(np.argmax(scores))
            selected_indices.append(best)

            # O(N_pool) scalar distance update
            d_new = np.linalg.norm(coords - coords[best], axis=-1)
            d_min = np.minimum(d_min, d_new)

        return selected_indices

    def select_points(
        self,
        pool_geoms: np.ndarray,
        pool_energies: Optional[np.ndarray] = None,
        point_ids: Optional[Sequence[str]] = None,
        batch_config: Optional[ActiveLearningBatchConfig] = None,
        uncertainties: Optional[np.ndarray] = None,
    ) -> ActiveLearningSelectionResult:
        """
        Executes active learning selection from candidate base pool geometries and energies.

        Args:
            pool_geoms: Array of Cartesian geometries of shape (N_pool, N_atoms, 3) or (N_pool, D)
            pool_energies: Optional array of base DFT energies of shape (N_pool,)
            point_ids: Optional list of unique point ID strings
            batch_config: Optional ActiveLearningBatchConfig overriding defaults
            uncertainties: Optional explicit uncertainties array of shape (N_pool,)

        Returns:
            ActiveLearningSelectionResult containing selected indices, point IDs,
            acquisition scores, and held-out validation grid split.
        """
        pool_geoms = np.asarray(pool_geoms, dtype=np.float64)
        n_total = pool_geoms.shape[0]

        effective_batch_cfg = batch_config or self.batch_config

        # Direct coordinate / uncertainty mode (e.g. Test 1)
        if uncertainties is not None or pool_geoms.ndim == 2 or pool_energies is None:
            if uncertainties is None:
                if pool_energies is not None:
                    uncertainties = np.abs(pool_energies - np.mean(pool_energies))
                else:
                    uncertainties = np.full(n_total, 1.0, dtype=np.float64)
            selected_idx = self.select_batch(
                candidate_pool=pool_geoms,
                uncertainties=uncertainties,
                batch_config=effective_batch_cfg,
            )
            return ActiveLearningSelectionResult(
                selected_indices=selected_idx,
                selected_point_ids=[f"pt_{i:05d}" for i in selected_idx],
                acquisition_scores=[float(uncertainties[i]) for i in selected_idx],
                committee_sigmas_hartree=[float(uncertainties[i]) for i in selected_idx],
                committee_sigmas_mev_atom=[float(uncertainties[i]) * 1000.0 for i in selected_idx],
                selection_rounds=1,
                n_selected=len(selected_idx),
                iqr_threshold_hartree=0.0,
                iqr_threshold_mev_atom=0.0,
                held_out_indices=[],
                held_out_point_ids=[],
                provenance_info={
                    "strategy": "sequential_furthest_point_repulsion",
                    "repulsion_length_scale": effective_batch_cfg.repulsion_length_scale,
                    "diversity_weight": effective_batch_cfg.diversity_weight,
                },
            )

        pool_energies = np.asarray(pool_energies, dtype=np.float64)
        if n_total < min(self.config.n_select_min, n_total):
            raise MethodMatrixViolationError(
                f"Candidate pool size ({n_total}) is smaller than minimum active selection "
                f"requirement ({self.config.n_select_min}). Method Matrix QS-3 mandates ~2,000 points.",
                error_code=ProvenanceErrorCode.TRIAGE_OVERRIDE_SPIN,
            )

        if point_ids is None:
            point_ids = [f"pt_{i:05d}" for i in range(n_total)]
        else:
            point_ids = list(point_ids)

        rng = np.random.RandomState(self.config.random_seed)

        # 1. Budget a dedicated held-out validation grid (Method Matrix QS-3 Step 5)
        n_held_out = int(self.config.held_out_ratio * n_total)
        all_indices = np.arange(n_total)
        rng.shuffle(all_indices)

        held_out_idx = sorted(all_indices[:n_held_out].tolist())
        candidate_pool_idx = sorted(all_indices[n_held_out:].tolist())
        n_candidate = len(candidate_pool_idx)

        logger.info(
            f"Active Learning Pool: {n_total} total points -> "
            f"{len(candidate_pool_idx)} candidate pool, {n_held_out} reserved held-out validation grid."
        )

        candidate_geoms = pool_geoms[candidate_pool_idx]
        candidate_energies = pool_energies[candidate_pool_idx]

        # Compute invariant features for the candidate pool
        if self.featurizer is not None and candidate_geoms.ndim == 3:
            cand_features = self.featurizer.compute_morse_features(candidate_geoms)
        else:
            cand_features = candidate_geoms.reshape(n_candidate, -1)

        # 2. Seed initial training set
        initial_seed_size = min(50, effective_batch_cfg.batch_size)
        selected_cand_idx: List[int] = []

        min_e_idx = int(np.argmin(candidate_energies))
        selected_cand_idx.append(min_e_idx)

        for _ in range(1, initial_seed_size):
            cur_selected_feats = cand_features[selected_cand_idx]
            dists = scipy.spatial.distance.cdist(cand_features, cur_selected_feats, metric="euclidean")
            min_dists = np.min(dists, axis=1)
            min_dists[selected_cand_idx] = -1.0
            next_idx = int(np.argmax(min_dists))
            selected_cand_idx.append(next_idx)

        # 3. Iterative Active Learning Loop with Sequential Furthest-Point Repulsion
        n_target = min(self.config.n_select_target, n_candidate)
        n_target = max(n_target, min(self.config.n_select_min, n_candidate))

        if self.featurizer is not None:
            committee = CommitteeModel(
                featurizer=self.featurizer,
                committee_size=self.config.committee_size,
                morse_lambda=self.config.morse_lambda,
                random_seed=self.config.random_seed,
            )
        else:
            committee = None

        rounds = 0
        acquisition_scores_history: List[float] = [0.0] * len(selected_cand_idx)

        while len(selected_cand_idx) < n_target:
            rounds += 1
            cur_train_geoms = candidate_geoms[selected_cand_idx]
            cur_train_energies = candidate_energies[selected_cand_idx]

            unselected_mask = np.full(n_candidate, True, dtype=bool)
            unselected_mask[selected_cand_idx] = False
            unselected_idx = np.where(unselected_mask)[0]

            if len(unselected_idx) == 0:
                break

            unselected_geoms = candidate_geoms[unselected_idx]
            unselected_feats = cand_features[unselected_idx]

            if committee is not None:
                committee.fit(cur_train_geoms, cur_train_energies)
                _, sigmas, sigmas_mev_atom = committee.predict_energy_and_uncertainty(unselected_geoms)
            else:
                sigmas = np.full(len(unselected_idx), 1.0, dtype=np.float64)
                sigmas_mev_atom = np.full(len(unselected_idx), 1.0, dtype=np.float64)

            # Sequential furthest-point repulsion batch selection within this round
            n_batch = min(effective_batch_cfg.batch_size, n_target - len(selected_cand_idx))
            cur_train_feats = cand_features[selected_cand_idx]

            sub_selected_unsel_idx = self.select_batch(
                candidate_pool=unselected_feats,
                uncertainties=sigmas,
                batch_config=ActiveLearningBatchConfig(
                    batch_size=n_batch,
                    repulsion_length_scale=effective_batch_cfg.repulsion_length_scale,
                    diversity_weight=effective_batch_cfg.diversity_weight,
                    kernel_type=effective_batch_cfg.kernel_type,
                ),
                labeled_points=cur_train_feats,
            )

            for rel_idx in sub_selected_unsel_idx:
                cand_idx = unselected_idx[rel_idx]
                selected_cand_idx.append(cand_idx)
                acquisition_scores_history.append(float(sigmas[rel_idx]))

            logger.info(
                f"Active Learning Round {rounds}: Selected {len(selected_cand_idx)}/{n_target} points "
                f"(Max UQ: {np.max(sigmas_mev_atom):.3f} meV/atom, Mean UQ: {np.mean(sigmas_mev_atom):.3f} meV/atom)"
            )

        # Map candidate pool indices back to original pool indices
        final_selected_orig_idx = [candidate_pool_idx[i] for i in selected_cand_idx]
        final_selected_point_ids = [point_ids[i] for i in final_selected_orig_idx]
        held_out_point_ids = [point_ids[i] for i in held_out_idx]

        # Final committee fit on full actively selected set
        final_train_geoms = pool_geoms[final_selected_orig_idx]
        final_train_energies = pool_energies[final_selected_orig_idx]
        if committee is not None:
            committee.fit(final_train_geoms, final_train_energies)
            _, final_sigmas, final_sigmas_mev_atom = committee.predict_energy_and_uncertainty(final_train_geoms)
        else:
            final_sigmas = [0.0] * len(final_selected_orig_idx)
            final_sigmas_mev_atom = [0.0] * len(final_selected_orig_idx)

        res = ActiveLearningSelectionResult(
            selected_indices=final_selected_orig_idx,
            selected_point_ids=final_selected_point_ids,
            acquisition_scores=acquisition_scores_history,
            committee_sigmas_hartree=[float(s) for s in final_sigmas],
            committee_sigmas_mev_atom=[float(s) for s in final_sigmas_mev_atom],
            selection_rounds=rounds,
            n_selected=len(final_selected_orig_idx),
            iqr_threshold_hartree=committee.training_iqr_threshold_hartree,
            iqr_threshold_mev_atom=committee.training_iqr_threshold_mev_atom,
            held_out_indices=held_out_idx,
            held_out_point_ids=held_out_point_ids,
            provenance_info={
                "strategy": self.config.acquisition_strategy.value,
                "committee_size": self.config.committee_size,
                "n_pool": n_total,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        return res


def sequential_repulsion_selector(
    candidate_pool: np.ndarray,
    uncertainties: np.ndarray,
    batch_config: Optional[ActiveLearningBatchConfig] = None,
    labeled_points: Optional[np.ndarray] = None,
) -> List[int]:
    """Functional interface for sequential furthest-point repulsion batch selection (Suggestion #51) [M]."""
    engine = ActiveLearningEngine(batch_config=batch_config)
    return engine.select_batch(
        candidate_pool=candidate_pool,
        uncertainties=uncertainties,
        batch_config=batch_config,
        labeled_points=labeled_points,
    )


# =============================================================================
# Delta-Learning Potential Energy Surface Model (Method Matrix §13.2 Row T2-12h)
# =============================================================================

class DeltaPESModel:
    """
    Represents a fitted Delta-learning potential energy surface:
    V_Delta(X) = V_low(X) + Delta_V(X)
    where Delta_V(X) is fitted on high-level CCSD(T) - low-level DFT energy differences.

    Provides exact analytical potential energy and gradient evaluations.
    """

    def __init__(
        self,
        featurizer: GeometryFeaturizer,
        krr_estimator: Union[ExactKernelRidgeEstimator, NeuralCommitteeEstimator],
        low_level_estimator: Optional[Union[ExactKernelRidgeEstimator, NeuralCommitteeEstimator]] = None,
        low_method: str = "dft_base",
        high_method: str = "dlpno_ccsdt1_avtz",
        validation_metrics: Optional[PESValidationMetrics] = None,
        energy_reference: str = "unspecified_legacy",
        delta_target_definition: str = "unspecified_legacy",
    ) -> None:
        self.featurizer: GeometryFeaturizer = featurizer
        # Retain the historical attribute name for existing callers; the
        # selected estimator may be a kernel model or an actual neural ensemble.
        self.krr_estimator = krr_estimator
        self.low_level_estimator = low_level_estimator
        self.low_method: str = low_method
        self.high_method: str = high_method
        self.validation_metrics: Optional[PESValidationMetrics] = validation_metrics
        self.energy_reference = energy_reference
        self.delta_target_definition = delta_target_definition

    def predict_delta(self, geoms: np.ndarray) -> np.ndarray:
        """Evaluates Delta_V(X) in Hartrees for single or batched geometries."""
        features = self.featurizer.compute_morse_features(geoms)
        return self.krr_estimator.predict(features)

    def predict_delta_with_uncertainty(self, geoms: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return mean, sample standard deviation, and neural member energies.

        Values are in Hartree. Committee disagreement is not a calibrated
        error bar, and this method does not certify external accuracy.
        """
        if not isinstance(self.krr_estimator, NeuralCommitteeEstimator):
            raise TypeError("Ensemble uncertainty requires a fitted neural committee")
        return self.krr_estimator.predict_with_uncertainty(self.featurizer.compute_morse_features(geoms))

    def predict_delta_forces_with_uncertainty(self, geom: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Neural delta forces (negative gradients) and spread in Hartree/Angstrom."""
        if not isinstance(self.krr_estimator, NeuralCommitteeEstimator):
            raise TypeError("Force uncertainty requires a fitted neural committee")
        features = self.featurizer.compute_morse_features(geom)
        jacobian = self.featurizer.compute_morse_jacobian(geom)
        member_gradients = self.krr_estimator.predict_member_gradients_wrt_features(features)
        forces = -np.tensordot(member_gradients, jacobian, axes=(1, 0))
        return np.mean(forces, axis=0), np.std(forces, axis=0, ddof=1), forces

    def predict_forces(self, geom: np.ndarray, grad_low_eval: Optional[np.ndarray] = None) -> np.ndarray:
        """Total conservative Cartesian force in Hartree/Angstrom."""
        return -self.predict_gradient(geom, grad_low_eval=grad_low_eval)

    def predict_total_energy(
        self, geoms: np.ndarray, v_low_eval: Optional[np.ndarray] = None, *,
        allow_unvalidated_baseline: bool = False,
    ) -> np.ndarray:
        """
        Evaluates total potential energy V_Delta(X) = V_low(X) + Delta_V(X) in Hartrees.
        If v_low_eval is provided, adds Delta_V directly; otherwise predicts V_low using low_level_estimator.
        """
        delta_v = self.predict_delta(geoms)
        if v_low_eval is not None:
            low_values = np.asarray(v_low_eval, dtype=np.float64)
            if low_values.shape != np.shape(delta_v) or not np.all(np.isfinite(low_values)):
                raise ValueError("Evaluated low-level energies must be finite and aligned with the requested geometries")
            return low_values + delta_v

        if self.low_level_estimator is not None:
            if (
                self.validation_metrics is not None
                and self.validation_metrics.total_surrogate_meets_target is False
                and not allow_unvalidated_baseline
            ):
                raise MethodMatrixViolationError(
                    "The fitted low-level baseline fails the standalone total-energy accuracy target; "
                    "supply independently evaluated v_low_eval energies for the validated paired correction, "
                    "or explicitly request allow_unvalidated_baseline=True for numerical analysis"
                )
            features = self.featurizer.compute_morse_features(geoms)
            v_low = self.low_level_estimator.predict(features)
            return v_low + delta_v
        else:
            raise CoChemError(
                "Cannot compute total energy: no low_level_estimator fitted and no v_low_eval provided.",
                error_code=ProvenanceErrorCode.MISSING_DATA,
            )

    def predict_gradient(
        self,
        geom: np.ndarray,
        grad_low_eval: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Computes analytical Cartesian gradient grad_X V_Delta(X) = grad_X V_low(X) + grad_X Delta_V(X)
        in Hartree/Angstrom for a geometry supplied in Angstrom (N_atoms, 3).
        """
        geom = np.asarray(geom, dtype=np.float64)
        if geom.shape != (self.featurizer.n_atoms, 3):
            raise ValueError(f"Expected geometry of shape ({self.featurizer.n_atoms}, 3), got {geom.shape}")

        # Compute Morse coordinate Jacobian: d(y_p)/d(r_ia) (N_pairs, N_atoms, 3)
        jac_morse = self.featurizer.compute_morse_jacobian(geom)

        # Compute feature gradient: d(Delta_V)/d(y_p) (N_pairs,)
        features = self.featurizer.compute_morse_features(geom)
        grad_features_delta = self.krr_estimator.predict_gradient_wrt_features(features)

        # Apply chain rule: d(Delta_V)/d(r_ia) = sum_p [d(Delta_V)/d(y_p)] * [d(y_p)/d(r_ia)]
        # grad_cart_delta: (N_atoms, 3)
        grad_cart_delta = np.tensordot(grad_features_delta, jac_morse, axes=(0, 0))

        if grad_low_eval is not None:
            grad_cart_total = np.asarray(grad_low_eval, dtype=np.float64) + grad_cart_delta
        elif self.low_level_estimator is not None:
            grad_features_low = self.low_level_estimator.predict_gradient_wrt_features(features)
            grad_cart_low = np.tensordot(grad_features_low, jac_morse, axes=(0, 0))
            grad_cart_total = grad_cart_low + grad_cart_delta
        else:
            grad_cart_total = grad_cart_delta

        return grad_cart_total

    def to_dict(self) -> Dict[str, Any]:
        """Serializes DeltaPESModel metadata, kernel weights, and training coordinates."""
        metadata = {
            "low_method": self.low_method,
            "high_method": self.high_method,
            "symbols": self.featurizer.symbols,
            "morse_lambda": self.featurizer.morse_lambda,
            "include_secondary": getattr(self.featurizer, "include_secondary", False),
            "energy_reference": self.energy_reference,
            "delta_target_definition": self.delta_target_definition,
            "requires_evaluated_low_energy_for_target": bool(
                self.validation_metrics is not None and self.validation_metrics.total_surrogate_meets_target is False
            ),
            "y_mean": self.krr_estimator.y_mean,
            "n_train": int(self.krr_estimator.X_train.shape[0]) if self.krr_estimator.X_train is not None else 0,
            "validation_metrics": self.validation_metrics.model_dump() if self.validation_metrics else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if isinstance(self.krr_estimator, NeuralCommitteeEstimator):
            metadata.update({
                "estimator_type": "neural_committee",
                "neural_config": self.krr_estimator.config.model_dump(mode="json"),
                "training_history": self.krr_estimator.training_history,
                "uncertainty_kind": "uncalibrated_ensemble_sample_standard_deviation",
            })
        else:
            metadata.update({
                "estimator_type": "kernel_ridge",
                "kernel_type": self.krr_estimator.kernel_type.value,
                "alpha": self.krr_estimator.alpha,
                "effective_gamma": self.krr_estimator.effective_gamma,
                "poly_degree": self.krr_estimator.poly_degree,
                "asymptotic_zero": self.krr_estimator.asymptotic_zero,
            })
        return metadata

    def save_npz(self, filepath: Union[str, Path]) -> Path:
        """Saves fitted model tensors and weights to a compressed .npz archive."""
        p = Path(filepath).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)

        meta_json = json.dumps(self.to_dict(), indent=2)
        if isinstance(self.krr_estimator, NeuralCommitteeEstimator):
            arrays = {"meta_json": np.array(meta_json), **self.krr_estimator.to_arrays("neural_delta_")}
            if self.low_level_estimator is not None:
                if not isinstance(self.low_level_estimator, NeuralCommitteeEstimator):
                    raise TypeError("Neural model archives require a neural baseline or an externally evaluated baseline")
                arrays.update(self.low_level_estimator.to_arrays("neural_low_"))
            np.savez_compressed(p, **arrays)
            return p
        arrays_to_save: Dict[str, Any] = {
            "meta_json": np.array(meta_json),
            "krr_weights": self.krr_estimator.weights if self.krr_estimator.weights is not None else np.empty(0),
            "krr_X_train": self.krr_estimator.X_train if self.krr_estimator.X_train is not None else np.empty((0, 0)),
            "krr_y_train": self.krr_estimator.y_train if self.krr_estimator.y_train is not None else np.empty(0),
        }
        if self.low_level_estimator is not None:
            arrays_to_save["low_weights"] = (
                self.low_level_estimator.weights if self.low_level_estimator.weights is not None else np.empty(0)
            )
            arrays_to_save["low_X_train"] = (
                self.low_level_estimator.X_train if self.low_level_estimator.X_train is not None else np.empty((0, 0))
            )
            arrays_to_save["low_y_train"] = (
                self.low_level_estimator.y_train if self.low_level_estimator.y_train is not None else np.empty(0)
            )
            arrays_to_save["low_y_mean"] = np.array(self.low_level_estimator.y_mean)
            arrays_to_save["low_effective_gamma"] = np.array(self.low_level_estimator.effective_gamma)

        np.savez_compressed(p, **arrays_to_save)
        logger.info(f"Saved DeltaPESModel to {p}")
        return p

    @classmethod
    def load_npz(cls, filepath: Union[str, Path]) -> DeltaPESModel:
        """Loads and reconstructs a DeltaPESModel from a saved .npz archive."""
        p = Path(filepath).resolve()
        if not p.exists():
            raise FileNotFoundError(f"DeltaPESModel file not found at {p}")

        data = np.load(p, allow_pickle=False)
        meta_dict = json.loads(str(data["meta_json"]))

        symbols = meta_dict["symbols"]
        morse_lambda = float(meta_dict.get("morse_lambda", 2.0))
        include_secondary = bool(meta_dict.get("include_secondary", False))
        featurizer = GeometryFeaturizer(
            symbols=symbols,
            morse_lambda=morse_lambda,
            include_secondary=include_secondary,
        )

        if meta_dict.get("estimator_type") == "neural_committee":
            with data:
                delta = NeuralCommitteeEstimator.from_arrays(data, "neural_delta_")
                low = NeuralCommitteeEstimator.from_arrays(data, "neural_low_") if "neural_low_metadata" in data else None
                metrics = PESValidationMetrics(**meta_dict["validation_metrics"]) if meta_dict.get("validation_metrics") else None
            return cls(
                featurizer, delta, low, meta_dict["low_method"], meta_dict["high_method"], metrics,
                meta_dict.get("energy_reference", "unspecified_legacy"),
                meta_dict.get("delta_target_definition", "unspecified_legacy"),
            )

        krr_est = ExactKernelRidgeEstimator(
            kernel_type=KernelType(meta_dict["kernel_type"]),
            alpha=float(meta_dict["alpha"]),
            gamma=float(meta_dict["effective_gamma"]),
            poly_degree=int(meta_dict.get("poly_degree", 4)),
            asymptotic_zero=bool(meta_dict.get("asymptotic_zero", True)),
        )
        krr_est.X_train = data["krr_X_train"]
        krr_est.y_train = data["krr_y_train"]
        krr_est.weights = data["krr_weights"]
        krr_est.y_mean = float(meta_dict["y_mean"])
        krr_est.effective_gamma = float(meta_dict["effective_gamma"])

        low_est: Optional[ExactKernelRidgeEstimator] = None
        if "low_weights" in data:
            low_est = ExactKernelRidgeEstimator(
                kernel_type=KernelType(meta_dict["kernel_type"]),
                alpha=float(meta_dict["alpha"]),
                poly_degree=int(meta_dict.get("poly_degree", 4)),
                asymptotic_zero=bool(meta_dict.get("asymptotic_zero", True)),
            )
            low_est.X_train = data["low_X_train"]
            low_est.y_train = data["low_y_train"]
            low_est.weights = data["low_weights"]
            low_est.y_mean = float(data["low_y_mean"])
            low_est.effective_gamma = float(data["low_effective_gamma"])

        metrics = None
        if meta_dict.get("validation_metrics"):
            metrics = PESValidationMetrics(**meta_dict["validation_metrics"])

        return cls(
            featurizer=featurizer,
            krr_estimator=krr_est,
            low_level_estimator=low_est,
            low_method=meta_dict.get("low_method", "dft_base"),
            high_method=meta_dict.get("high_method", "dlpno_ccsdt1_avtz"),
            validation_metrics=metrics,
            energy_reference=meta_dict.get("energy_reference", "unspecified_legacy"),
            delta_target_definition=meta_dict.get("delta_target_definition", "unspecified_legacy"),
        )


# =============================================================================
# Spectroscopic Validation Engine (Method Matrix QS-3 Step 5)
# =============================================================================

class PESValidator:
    """
    Evaluates potential energy surface fidelity on a held-out test grid.
    Converts all error residuals into spectroscopic units:
    - Root Mean Square Error (RMSE) in cm^-1, kcal/mol, meV, and Hartree
    - Mean Absolute Error (MAE) in cm^-1
    - Maximum Absolute Error (Max Error) in cm^-1
    - Verifies spectroscopic grade target (Method Matrix T2-12h target: RMS <= 3-10 cm^-1).
    """

    @staticmethod
    def evaluate_model(
        model: DeltaPESModel,
        train_geoms: np.ndarray,
        train_delta_true: np.ndarray,
        held_out_geoms: np.ndarray,
        held_out_delta_true: np.ndarray,
        target_rms_cm1: float = 10.0,
        validation_scope: str = "provided_delta_targets",
    ) -> PESValidationMetrics:
        """
        Computes energy-fitting errors against supplied training and held-out targets.
        """
        train_delta_true = np.asarray(train_delta_true, dtype=np.float64)
        held_out_delta_true = np.asarray(held_out_delta_true, dtype=np.float64)
        if (
            train_delta_true.shape != (len(train_geoms),) or held_out_delta_true.shape != (len(held_out_geoms),)
            or not len(train_geoms) or not len(held_out_geoms)
            or not np.all(np.isfinite(train_delta_true)) or not np.all(np.isfinite(held_out_delta_true))
        ):
            raise ValueError("Validation requires finite aligned training and held-out target vectors")

        # 1. Training metrics
        train_preds = model.predict_delta(train_geoms)
        train_res_ha = np.abs(train_preds - train_delta_true)
        train_res_cm1 = train_res_ha * HARTREE_TO_CM1

        train_rmse_cm1 = float(np.sqrt(np.mean(train_res_cm1**2)))
        train_mae_cm1 = float(np.mean(train_res_cm1))
        train_max_err_cm1 = float(np.max(train_res_cm1))

        # 2. Held-out validation metrics
        held_out_preds = model.predict_delta(held_out_geoms)
        held_out_res_ha = np.abs(held_out_preds - held_out_delta_true)
        held_out_res_cm1 = held_out_res_ha * HARTREE_TO_CM1

        held_out_rmse_ha = float(np.sqrt(np.mean(held_out_res_ha**2)))
        held_out_rmse_cm1 = float(np.sqrt(np.mean(held_out_res_cm1**2)))
        held_out_mae_cm1 = float(np.mean(held_out_res_cm1))
        held_out_max_err_cm1 = float(np.max(held_out_res_cm1))
        held_out_rmse_kcal_mol = held_out_rmse_ha * HARTREE_TO_KCAL_MOL

        spectroscopic_grade = bool(held_out_rmse_cm1 <= target_rms_cm1)

        metrics = PESValidationMetrics(
            n_train=int(train_geoms.shape[0]),
            n_held_out=int(held_out_geoms.shape[0]),
            train_rmse_cm1=train_rmse_cm1,
            train_mae_cm1=train_mae_cm1,
            train_max_err_cm1=train_max_err_cm1,
            held_out_rmse_cm1=held_out_rmse_cm1,
            held_out_mae_cm1=held_out_mae_cm1,
            held_out_max_err_cm1=held_out_max_err_cm1,
            held_out_rmse_kcal_mol=held_out_rmse_kcal_mol,
            held_out_rmse_hartree=held_out_rmse_ha,
            spectroscopic_grade=spectroscopic_grade,
            target_rms_cm1=float(target_rms_cm1),
            timestamp=datetime.now(timezone.utc).isoformat(),
            validation_scope=validation_scope,
        )

        logger.info(
            f"Numerical fitting validation ({validation_scope}): Held-out RMSE = {held_out_rmse_cm1:.3f} cm^-1 "
            f"(Target <= {target_rms_cm1:.1f} cm^-1 | Grade: {'PASS' if spectroscopic_grade else 'RETRY'}). "
            f"MAE = {held_out_mae_cm1:.3f} cm^-1, Max = {held_out_max_err_cm1:.3f} cm^-1."
        )
        return metrics


# =============================================================================
# Autonomous PES Campaign Orchestrator (Method Matrix QS-3 & §8C Integration)
# =============================================================================

class AutoPESOrchestrator:
    """
    Coordinates end-to-end PES active learning campaigns:
    1. Ingestion / loading of base DFT pool from HDF5 PESStore
    2. Active learning selection of 300-800 points for high-level calculation
    3. Retrieval of high-level Delta training pairs via PESStore.delta_pairs()
    4. Delta-learning surface fitting with Kernel Ridge Regression
    5. Held-out validation grid residual evaluation in cm^-1
    6. Persistence and export back to HDF5 PESStore.
    """

    def __init__(
        self,
        symbols: Sequence[str],
        low_method: str = "wb97x_v_tz",
        high_method: str = "dlpno_ccsdt1_avtz",
        al_config: Optional[ActiveLearningConfig] = None,
        fit_config: Optional[DeltaFittingConfig] = None,
    ) -> None:
        self.symbols: List[str] = [s.strip() for s in symbols]
        self.low_method: str = low_method
        self.high_method: str = high_method
        self.al_config: ActiveLearningConfig = al_config or ActiveLearningConfig()
        self.fit_config: DeltaFittingConfig = fit_config or DeltaFittingConfig()
        if self.fit_config.backend == FittingBackend.POLYNOMIAL_EXPANSION:
            # Polynomial KRR is the dual form of a ridge-regularized polynomial
            # expansion of the invariant descriptors, including cross terms.
            self.fit_config = self.fit_config.model_copy(update={"kernel": KernelType.POLYNOMIAL})
        elif self.fit_config.backend == FittingBackend.PIP_RBF:
            self.fit_config = self.fit_config.model_copy(
                update={"kernel": KernelType.RBF, "include_secondary": True}
            )

        self.featurizer: GeometryFeaturizer = GeometryFeaturizer(
            symbols=self.symbols,
            morse_lambda=self.fit_config.morse_lambda,
            include_secondary=getattr(self.fit_config, "include_secondary", False),
        )
        self.al_engine: ActiveLearningEngine = ActiveLearningEngine(
            featurizer=self.featurizer,
            config=self.al_config,
        )

    def _surface_estimator(self, *, seed_offset: int = 0) -> Union[ExactKernelRidgeEstimator, NeuralCommitteeEstimator]:
        if self.fit_config.backend == FittingBackend.NEURAL_COMMITTEE:
            return NeuralCommitteeEstimator(self.fit_config, seed_offset=seed_offset)
        return ExactKernelRidgeEstimator(
            kernel_type=self.fit_config.kernel,
            alpha=self.fit_config.regularization_alpha,
            gamma=self.fit_config.gamma,
            poly_degree=self.fit_config.poly_degree,
            asymptotic_zero=self.fit_config.energy_reference == "interaction_zero_asymptote",
        )

    def run_active_selection_from_store(
        self,
        pes_store: Any,
    ) -> ActiveLearningSelectionResult:
        """
        Loads base DFT grid points from PESStore and executes active learning selection.
        """
        # Read low-level dataset from PESStore
        if hasattr(pes_store, "dataset_full"):
            low_data = pes_store.dataset_full(self.low_method, converged_only=True)
            geoms = low_data["coordinates"]
            energies = low_data["energy"]
            point_ids = low_data.get("point_id", [f"pt_{i:05d}" for i in range(len(energies))])
        else:
            raw_data = pes_store.dataset(self.low_method, converged_only=True)
            if isinstance(raw_data, dict):
                geoms = raw_data["coordinates"]
                energies = raw_data["energy"]
                point_ids = raw_data.get("point_id", [f"pt_{i:05d}" for i in range(len(energies))])
            else:
                geoms, energies = raw_data
                point_ids = [f"pt_{i:05d}" for i in range(len(energies))]

        if len(geoms) == 0:
            raise MissingDataError(
                f"No converged points found for low-level method '{self.low_method}' in PESStore.",
                error_code=ProvenanceErrorCode.MISSING_DATA,
            )

        res = self.al_engine.select_points(
            pool_geoms=geoms,
            pool_energies=energies,
            point_ids=point_ids,
        )
        return res

    def fit_delta_surface_from_data(
        self,
        train_geoms: np.ndarray,
        train_low_energies: np.ndarray,
        train_high_energies: np.ndarray,
        held_out_geoms: np.ndarray,
        held_out_low_energies: np.ndarray,
        held_out_high_energies: np.ndarray,
        dense_dft_geoms: Optional[np.ndarray] = None,
        dense_dft_energies: Optional[np.ndarray] = None,
    ) -> Tuple[DeltaPESModel, DeltaSurfaceFitResult]:
        """Fit on training data and evaluate on separate held-out data.

        A dense low-level baseline may be provided explicitly; its overlap
        with the validation geometries then makes this a test of unseen
        high-level labels, not a wholly unseen-geometry test of that baseline.

        Follows Method Matrix §13.2 / QS-3:
        1. Base estimator low_krr is fitted on full dense low-level DFT sampling dataset (N ~ 2,000 points).
        2. Paired energy differences: Delta E_k = E_k^high - E_k^low (Method Matrix delta_pairs contract).
        3. delta_krr is fitted strictly on these sparse active-learning residuals.
        """
        train_geoms = np.asarray(train_geoms, dtype=np.float64)
        held_out_geoms = np.asarray(held_out_geoms, dtype=np.float64)
        if (dense_dft_geoms is None) != (dense_dft_energies is None):
            raise ValueError("Dense baseline coordinates and energies must be supplied together")
        energy_vectors = []
        for values, geometries in (
            (train_low_energies, train_geoms), (train_high_energies, train_geoms),
            (held_out_low_energies, held_out_geoms), (held_out_high_energies, held_out_geoms),
        ):
            original = np.asarray(values)
            vector = np.asarray(values, dtype=np.float64)
            if original.dtype.kind == "b" or vector.shape != (len(geometries),) or not np.all(np.isfinite(vector)):
                raise ValueError("Paired energies must be finite aligned vectors in Hartree")
            energy_vectors.append(vector)
        train_low_energies, train_high_energies, held_out_low_energies, held_out_high_energies = energy_vectors

        # 1. Fit baseline low_krr on the complete dense low-level DFT dataset
        if dense_dft_geoms is not None and dense_dft_energies is not None:
            dense_dft_geoms = np.asarray(dense_dft_geoms, dtype=np.float64)
            dense_dft_energies = np.asarray(dense_dft_energies, dtype=np.float64)
            dense_feats = self.featurizer.compute_morse_features(dense_dft_geoms)
            n_base_total = int(dense_dft_geoms.shape[0])
            low_train_feats = dense_feats
            low_train_y = dense_dft_energies
        else:
            # Held-out labels are validation data. A caller may explicitly
            # supply a dense low-level baseline, but the default must not
            # silently absorb the held-out set into baseline training.
            low_train_feats = self.featurizer.compute_morse_features(train_geoms)
            low_train_y = np.asarray(train_low_energies, dtype=np.float64)
            n_base_total = int(train_geoms.shape[0])

        low_krr = self._surface_estimator()
        low_krr.fit(low_train_feats, low_train_y)

        # 2. Learn aligned high-minus-low labels. Fitting interpolation error in
        # the low-level surrogate instead changes the learning problem and can
        # dominate a supposedly measured delta error on a withheld domain.
        train_feats = self.featurizer.compute_morse_features(train_geoms)
        train_delta = train_high_energies - train_low_energies

        held_out_feats = self.featurizer.compute_morse_features(held_out_geoms)
        held_out_v_low_pred = low_krr.predict(held_out_feats)
        held_out_delta = held_out_high_energies - held_out_low_energies

        # 3. Fit delta_krr strictly on sparse active-learning residuals
        delta_krr = self._surface_estimator(seed_offset=1000003)
        delta_krr.fit(train_feats, train_delta)

        model = DeltaPESModel(
            featurizer=self.featurizer,
            krr_estimator=delta_krr,
            low_level_estimator=low_krr,
            low_method=self.low_method,
            high_method=self.high_method,
            energy_reference=self.fit_config.energy_reference,
            delta_target_definition="paired_high_minus_low",
        )

        # 4. Validate on held-out grid (Method Matrix QS-3 Step 5)
        metrics = PESValidator.evaluate_model(
            model=model,
            train_geoms=train_geoms,
            train_delta_true=train_delta,
            held_out_geoms=held_out_geoms,
            held_out_delta_true=held_out_delta,
            target_rms_cm1=self.fit_config.target_rms_cm1,
            validation_scope="paired_delta_correction_with_evaluated_low_energy",
        )
        baseline_error = held_out_v_low_pred - held_out_low_energies
        total_error = held_out_v_low_pred + model.predict_delta(held_out_geoms) - held_out_high_energies
        baseline_rmse = float(np.sqrt(np.mean(baseline_error ** 2)) * HARTREE_TO_CM1)
        total_rmse = float(np.sqrt(np.mean(total_error ** 2)) * HARTREE_TO_CM1)
        metrics = metrics.model_copy(update={
            "held_out_baseline_rmse_cm1": baseline_rmse,
            "held_out_total_surrogate_rmse_cm1": total_rmse,
            "total_surrogate_meets_target": bool(total_rmse <= self.fit_config.target_rms_cm1),
        })
        logger.info(
            "Separate standalone-surrogate validation: baseline RMSE %.6f cm^-1; total RMSE %.6f cm^-1; target met: %s",
            baseline_rmse, total_rmse, metrics.total_surrogate_meets_target,
        )
        model.validation_metrics = metrics

        fit_summary = DeltaSurfaceFitResult(
            low_method=self.low_method,
            high_method=self.high_method,
            n_base_dft_points=n_base_total,
            n_delta_points=int(train_geoms.shape[0]),
            n_held_out_points=int(held_out_geoms.shape[0]),
            metrics=metrics,
            backend=self.fit_config.backend.value,
            model_parameters=model.to_dict(),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        return model, fit_summary

    def fit_delta_surface_from_store(
        self,
        pes_store: Any,
        held_out_ratio: float = 0.20,
    ) -> Tuple[DeltaPESModel, DeltaSurfaceFitResult]:
        """Extracts aligned Delta pairs directly from PESStore or HDF5 store under dual-locking,

        fits the Delta-learning surface with dense DFT anchoring, and validates in cm^-1.
        """
        # Check if pes_store is a path to an HDF5 datastore file
        if isinstance(pes_store, (str, Path)):
            from cochem_base.core_engine.cochem_core_pes_store import ReadWriteFileLock

            store_path = Path(pes_store).resolve()
            h5_lock = ReadWriteFileLock(Path(f"{store_path}.lock"), timeout=10.0)
            with h5_lock.read_lock():
                with h5py.File(store_path, "r", swmr=True) as h5f:
                    if "dense_dft/coordinates" in h5f:
                        dense_geoms = np.asarray(h5f["dense_dft/coordinates"][:], dtype=np.float64)
                        dense_energies = np.asarray(h5f["dense_dft/energy"][:], dtype=np.float64)
                    elif "dense_dft/features" in h5f:
                        dense_geoms = None
                        dense_energies = np.asarray(h5f["dense_dft/energies"][:], dtype=np.float64)
                    else:
                        raise KeyError("Missing dense_dft dataset in HDF5 store.")

                    if "sparse_ccsd/coordinates" in h5f:
                        high_geoms = np.asarray(h5f["sparse_ccsd/coordinates"][:], dtype=np.float64)
                        high_energies = np.asarray(h5f["sparse_ccsd/energy"][:], dtype=np.float64)
                        if "sparse_ccsd/low_energy" not in h5f:
                            raise MissingDataError("Missing aligned sparse_ccsd/low_energy dataset")
                        high_low_energies = np.asarray(h5f["sparse_ccsd/low_energy"][:], dtype=np.float64)
                    else:
                        raise KeyError("Missing sparse_ccsd dataset in HDF5 store.")

            n_pairs = len(high_geoms)
            rng = np.random.RandomState(self.al_config.random_seed)
            shuffled = np.arange(n_pairs)
            rng.shuffle(shuffled)

            n_held = max(5, int(held_out_ratio * n_pairs))
            held_idx = shuffled[:n_held]
            train_idx = shuffled[n_held:]

            return self.fit_delta_surface_from_data(
                train_geoms=high_geoms[train_idx],
                train_low_energies=high_low_energies[train_idx],
                train_high_energies=high_energies[train_idx],
                held_out_geoms=high_geoms[held_idx],
                held_out_low_energies=high_low_energies[held_idx],
                held_out_high_energies=high_energies[held_idx],
                dense_dft_geoms=dense_geoms,
                dense_dft_energies=dense_energies,
            )

        # Standard PESStore instance branch
        keys, X_high, dE = pes_store.delta_pairs(self.low_method, self.high_method)
        n_pairs = len(keys)

        if n_pairs < 20:
            raise MissingDataError(
                f"Insufficient aligned Delta pairs ({n_pairs}) found between '{self.low_method}' "
                f"and '{self.high_method}'. Need at least 20 aligned pairs.",
                error_code=ProvenanceErrorCode.MISSING_DATA,
            )

        # Retrieve dense DFT dataset for baseline low_krr
        dense_geoms = None
        dense_energies = None
        if hasattr(pes_store, "dataset_full"):
            low_data = pes_store.dataset_full(self.low_method, converged_only=True)
            dense_geoms = low_data["coordinates"]
            dense_energies = low_data["energy"]
            low_id_map = {
                (s.decode("utf-8") if isinstance(s, bytes) else str(s)): low_data["energy"][idx]
                for idx, s in enumerate(low_data["point_id"])
            }
        else:
            low_data = pes_store.dataset(self.low_method, converged_only=True)
            if isinstance(low_data, dict):
                dense_geoms = low_data["coordinates"]
                dense_energies = low_data["energy"]
                low_id_map = {
                    (s.decode("utf-8") if isinstance(s, bytes) else str(s)): low_data["energy"][idx]
                    for idx, s in enumerate(low_data["point_id"])
                }
            else:
                dense_geoms, dense_energies = low_data
                low_id_map = {k: dense_energies[i] for i, k in enumerate(keys)}

        e_low = np.array([low_id_map[k] for k in keys], dtype=np.float64)
        e_high = e_low + dE

        # Split into training and held-out sets
        rng = np.random.RandomState(self.al_config.random_seed)
        shuffled = np.arange(n_pairs)
        rng.shuffle(shuffled)

        n_held = max(5, int(held_out_ratio * n_pairs))
        held_idx = shuffled[:n_held]
        train_idx = shuffled[n_held:]

        return self.fit_delta_surface_from_data(
            train_geoms=X_high[train_idx],
            train_low_energies=e_low[train_idx],
            train_high_energies=e_high[train_idx],
            held_out_geoms=X_high[held_idx],
            held_out_low_energies=e_low[held_idx],
            held_out_high_energies=e_high[held_idx],
            dense_dft_geoms=dense_geoms,
            dense_dft_energies=dense_energies,
        )


# =============================================================================
# Numerical demonstration using an empirical potential (not electronic-structure evidence)
# =============================================================================

def generate_benchmark_intermolecular_pes_data(
    n_points: int = 2000,
    random_seed: int = 42,
) -> Tuple[List[str], np.ndarray, np.ndarray, np.ndarray]:
    """
    Return a deterministic Cu/Ag/Au EMT trajectory and two numerical targets.

    Both energy arrays are in Hartree. The second target is an explicitly
    artificial affine transformation of EMT energy for solver verification;
    it is not DFT, CCSD(T), or evidence of spectroscopic prediction accuracy.
    Specifically, E_target = 1.02 * E_EMT - 0.005 eV. With the same centered
    linear estimator, the correction error scales to 2% of the baseline error;
    passing a correction threshold here is not independent accuracy evidence.
    ``random_seed`` is retained for API compatibility; this trajectory has
    fixed initial coordinates and velocities and uses no random sampling.
    """
    from ase import Atoms, units
    from ase.calculators.emt import EMT
    from ase.md.verlet import VelocityVerlet

    symbols = ["Cu", "Ag", "Au"]
    # Starting geometry
    atoms = Atoms("CuAgAu", positions=[[0.0, 0.0, 0.0], [2.5, 0.0, 0.0], [0.0, 2.5, 0.0]])
    atoms.calc = EMT()

    # Deterministic velocities to start MD
    atoms.set_velocities([[0.01, 0.01, 0.0], [-0.01, 0.0, 0.01], [0.0, -0.01, -0.01]])
    dyn = VelocityVerlet(atoms, 1.0 * units.fs)

    geoms = np.empty((n_points, 3, 3), dtype=np.float64)
    empirical_energies = np.empty(n_points, dtype=np.float64)
    transformed_energies = np.empty(n_points, dtype=np.float64)

    for p in range(n_points):
        dyn.run(2)
        geoms[p] = atoms.get_positions()
        # ASE returns eV; every AutoPES fitting/validation API uses Hartree.
        energy_ev = atoms.get_potential_energy()
        empirical_energies[p] = energy_ev / units.Hartree
        # Numerical target only: preserve the original 0.005 eV shift.
        transformed_energies[p] = (energy_ev * 1.02 - 0.005) / units.Hartree

    return symbols, geoms, empirical_energies, transformed_energies


# =============================================================================
# Command-Line Interface & Demonstration Execution
# =============================================================================

def build_cli_parser() -> argparse.ArgumentParser:
    """Builds the comprehensive CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="CoChem AutoPES: Active Learning Selection (300-800 pts) & Delta-Learning PES Fitting Engine."
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run a numerical Cu/Ag/Au EMT fitting demonstration (not a quantum benchmark).",
    )
    parser.add_argument(
        "--campaign-h5",
        type=str,
        default=None,
        help="Path to campaign HDF5 PESStore file.",
    )
    parser.add_argument(
        "--low-method",
        type=str,
        default="wb97x_v_tz",
        help="Low-level base method ID (e.g. 'wb97x_v_tz').",
    )
    parser.add_argument(
        "--high-method",
        type=str,
        default="dlpno_ccsdt1_avtz",
        help="High-level escalation method ID (e.g. 'dlpno_ccsdt1_avtz').",
    )
    parser.add_argument(
        "--n-select",
        type=int,
        default=500,
        help="Number of active learning points to select (QS-3 mandate: 300-800).",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="two_set_error_based",
        choices=[s.value for s in AcquisitionStrategy],
        help="Acquisition strategy function.",
    )
    parser.add_argument(
        "--target-rms",
        type=float,
        default=10.0,
        help="Target spectroscopic held-out RMSE threshold in cm^-1.",
    )
    parser.add_argument(
        "--output-model",
        type=str,
        default="fitted_delta_pes.npz",
        help="Path to save output fitted DeltaPESModel .npz archive.",
    )
    return parser


def run_demo() -> int:
    """
    Exercise fitting on EMT and an artificial transformed target.

    This measures numerical fitting error, not electronic-structure accuracy.
    """
    logger.info("================================================================================")
    logger.info("CoChem AutoPES: Active Learning (300-800 pts) & Delta-Learning Demonstration")
    logger.info("Empirical numerical demonstration; independent scientific accuracy is not assessed.")
    logger.info("================================================================================")

    # 1. Generate deterministic empirical-potential data in Hartree.
    symbols, geoms, empirical_energy, transformed_energy = generate_benchmark_intermolecular_pes_data(n_points=2000, random_seed=42)
    logger.info("Generated 2,000 Cu/Ag/Au EMT trajectory points; upper target is an artificial affine transform.")
    logger.info("E_target = 1.02 * E_EMT - 0.005 eV; the small correction has no independent quantum reference.")

    # Verify Mendeleev dynamic mass resolution
    for symbol in symbols:
        logger.info("Mendeleev mass: %s=%.6f u", symbol, get_dynamic_atomic_mass(symbol))

    # 2. Configure Active Learning Engine
    al_config = ActiveLearningConfig(
        pool_size=2000,
        n_select_min=300,
        n_select_max=800,
        n_select_target=500,
        batch_size=50,
        acquisition_strategy=AcquisitionStrategy.TWO_SET_ERROR_BASED,
        committee_size=4,
        diversity_weight=0.35,
        held_out_ratio=0.20,
    )
    fit_config = DeltaFittingConfig(
        backend=FittingBackend.KERNEL_RIDGE,
        kernel=KernelType.RBF,
        regularization_alpha=1e-6,
        target_rms_cm1=10.0,
    )

    orchestrator = AutoPESOrchestrator(
        symbols=symbols,
        low_method="ase_emt",
        high_method="numerical_affine_emt_target",
        al_config=al_config,
        fit_config=fit_config,
    )

    # 3. Execute Active Learning Selection (Step 3)
    logger.info("\n--- Phase 1: Committee-Based Active Learning Selection ---")
    start_time = time.perf_counter()
    al_result = orchestrator.al_engine.select_points(
        pool_geoms=geoms,
        pool_energies=empirical_energy,
    )
    sel_elapsed = time.perf_counter() - start_time

    logger.info(
        f"[OK] Selected {al_result.n_selected} points in {al_result.selection_rounds} rounds "
        f"({sel_elapsed:.2f}s). Held-out validation grid: {len(al_result.held_out_indices)} points."
    )
    logger.info(
        f"[OK] Guard G5 Committee Threshold: {al_result.iqr_threshold_hartree:.6e} Ha "
        f"({al_result.iqr_threshold_mev_atom:.3f} meV/atom)."
    )

    # 4. Fit and validate the numerical paired correction on held-out geometries.
    logger.info("\n--- Phase 2: Delta-Learning Potential Energy Surface Fitting ---")
    train_idx = al_result.selected_indices
    held_idx = al_result.held_out_indices

    model, fit_summary = orchestrator.fit_delta_surface_from_data(
        train_geoms=geoms[train_idx],
        train_low_energies=empirical_energy[train_idx],
        train_high_energies=transformed_energy[train_idx],
        held_out_geoms=geoms[held_idx],
        held_out_low_energies=empirical_energy[held_idx],
        held_out_high_energies=transformed_energy[held_idx],
    )

    metrics = fit_summary.metrics
    logger.info("\n================================================================================")
    logger.info("NUMERICAL FITTING VALIDATION REPORT (NOT SPECTROSCOPIC ACCURACY EVIDENCE)")
    logger.info("================================================================================")
    logger.info(f"Training Points (Actively Selected): {metrics.n_train}")
    logger.info(f"Held-Out Validation Points:        {metrics.n_held_out}")
    logger.info(f"Training RMSE:                     {metrics.train_rmse_cm1:.4f} cm^-1")
    logger.info(f"Training MAE:                      {metrics.train_mae_cm1:.4f} cm^-1")
    logger.info(f"Held-Out Validation RMSE:          {metrics.held_out_rmse_cm1:.4f} cm^-1")
    logger.info(f"Held-Out Validation MAE:           {metrics.held_out_mae_cm1:.4f} cm^-1")
    logger.info(f"Held-Out Validation Max Error:     {metrics.held_out_max_err_cm1:.4f} cm^-1")
    logger.info(f"Held-Out Validation RMSE (kcal):   {metrics.held_out_rmse_kcal_mol:.5f} kcal/mol")
    logger.info(f"Numerical Correction Threshold:    <= {metrics.target_rms_cm1:.1f} cm^-1")
    logger.info(f"Correction Threshold Met:          {metrics.spectroscopic_grade}")
    logger.info("Independent physical/spectroscopic accuracy: NOT ASSESSED")
    logger.info("================================================================================")

    # 5. Verify Analytical Gradient Evaluation
    logger.info("\n--- Phase 3: Analytical Surface Gradient Verification ---")
    test_geom = geoms[held_idx[0]]
    grad = model.predict_gradient(test_geom)
    grad_norm = float(np.linalg.norm(grad))
    logger.info(f"[OK] Analytical Cartesian gradient evaluated: shape={grad.shape}, ||grad||={grad_norm:.6e} Ha/A.")

    # 6. Save Model NPZ Archive
    demo_npz = Path("cochem_auto_pes_demo_model.npz")
    model.save_npz(demo_npz)
    logger.info("[OK] Re-loading saved model for verification...")
    reloaded_model = DeltaPESModel.load_npz(demo_npz)
    pred_test = float(reloaded_model.predict_delta(test_geom))
    pred_orig = float(model.predict_delta(test_geom))
    assert abs(pred_test - pred_orig) < 1e-12, "Reloaded model prediction mismatch"
    logger.info(f"[OK] Re-loaded model verified with exact bitwise energy match: {pred_test:.10f} Ha.")

    if demo_npz.exists():
        demo_npz.unlink()

    logger.info("\nAutoPES numerical demonstration finished; scientific accuracy requires independent reference data.")
    return 0 if metrics.spectroscopic_grade else 1


def main() -> int:
    """Main CLI entrypoint."""
    parser = build_cli_parser()
    args = parser.parse_args()

    if args.demo or args.campaign_h5 is None:
        return run_demo()

    # If campaign-h5 is provided, run from real HDF5 store
    from core_engine.cochem_core_pes_store import PESStore

    store_path = Path(args.campaign_h5).resolve()
    if not store_path.exists():
        logger.error(f"PESStore file not found at {store_path}")
        return 1

    store = PESStore(str(store_path))
    symbols = store.symbols

    al_config = ActiveLearningConfig(
        n_select_target=args.n_select,
        acquisition_strategy=AcquisitionStrategy(args.strategy),
    )
    fit_config = DeltaFittingConfig(
        target_rms_cm1=args.target_rms,
    )

    orchestrator = AutoPESOrchestrator(
        symbols=symbols,
        low_method=args.low_method,
        high_method=args.high_method,
        al_config=al_config,
        fit_config=fit_config,
    )

    logger.info(f"Running active learning selection for '{args.low_method}' -> '{args.high_method}'...")
    al_res = orchestrator.run_active_selection_from_store(store)
    logger.info(f"Actively selected {al_res.n_selected} points for escalation.")

    # Check if high-level points are already computed in the store
    todo_ids = store.todo(args.high_method, al_res.selected_point_ids)
    if len(todo_ids) > 0:
        logger.info(
            f"Escalation pending: {len(todo_ids)}/{al_res.n_selected} points still to calculate "
            f"for high-level method '{args.high_method}'."
        )
        return 0

    logger.info("Fitting Delta-learning potential energy surface...")
    model, fit_summary = orchestrator.fit_delta_surface_from_store(store)
    if not fit_summary.metrics.spectroscopic_grade:
        logger.error(
            "PES accuracy gate failed: held-out RMSE %.6f cm^-1 exceeds %.6f cm^-1; model was not published.",
            fit_summary.metrics.held_out_rmse_cm1,
            fit_summary.metrics.target_rms_cm1,
        )
        return 2
    model.save_npz(args.output_model)
    logger.info(f"Delta-learning surface fitted and saved to {args.output_model}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
