"""CoChem-TOPOS Alignment Subsystem (Part 1).

Rigorous molecular topology alignment, Maximum Common Substructure (MCS) perception,
Kabsch SVD coordinate transformation with reflection parity guard and numerical
degeneracy safeguards, ensemble deduplication, and thread-safe HDF5 persistence [M][D].
"""

from __future__ import annotations

import concurrent.futures
from enum import Enum
import os
from pathlib import Path
import sys
import time
from typing import Dict, List, Optional, Tuple

import filelock
import h5py
from mendeleev import element
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from rdkit import Chem
from rdkit.Chem import rdFMCS
from scipy.linalg import svd

from cochem.topos.exceptions import (
    AirGapBoundaryViolationError,
    CollinearDegeneracyError,
    DegenerateCoordinatesError,
    IncompatibleTopologyError,
    MCSConvergenceTimeoutError,
    ToposAlignmentError,
)


class StorageTier(str, Enum):
    """Storage and concurrency tiers across the CoChem ecosystem [D]."""

    TIER1_WINDOWS = "tier1_windows"
    TIER2_MACOS = "tier2_macos"
    TIER3_LINUX = "tier3_linux"
    TIER4_CODESPACES = "tier4_codespaces"
    TIER5_GITHUB_ACTIONS = "tier5_github_actions"
    TIER6_HPC = "tier6_hpc"


def detect_concurrency_tier() -> StorageTier:
    """Detects active execution tier based on OS and environment invariants [D]."""
    if "SLURM_JOB_ID" in os.environ or "PBS_JOBID" in os.environ:
        return StorageTier.TIER6_HPC
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return StorageTier.TIER5_GITHUB_ACTIONS
    if os.environ.get("CODESPACES") == "true":
        return StorageTier.TIER4_CODESPACES
    if sys.platform == "win32":
        return StorageTier.TIER1_WINDOWS
    if sys.platform == "darwin":
        return StorageTier.TIER2_MACOS
    return StorageTier.TIER3_LINUX


class ConformerInput(BaseModel):
    """Input representation of a 3D molecular conformer [D]."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    conformer_id: str
    elements: List[str]
    atomic_numbers: List[int]
    coordinates: List[Tuple[float, float, float]]
    bonds: List[Tuple[int, int, float]] = Field(default_factory=list)
    reference_smiles: Optional[str] = None
    masses: Optional[List[float]] = None
    energy_kcal_mol: Optional[float] = None
    is_ghost: List[bool] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_conformer(self) -> "ConformerInput":
        """Enforces length matching across conformer atom arrays [D]."""
        n_elem = len(self.elements)
        n_atomic = len(self.atomic_numbers)
        n_coords = len(self.coordinates)
        if n_coords == 0 or n_elem == 0:
            raise ValueError("Coordinates and elements cannot be empty")
        if n_elem != n_atomic or n_elem != n_coords:
            raise ValueError(
                f"Length mismatch: elements ({n_elem}), atomic_numbers ({n_atomic}), and coordinates ({n_coords}) must match"
            )
        if self.is_ghost:
            if len(self.is_ghost) != n_elem:
                raise ValueError(
                    f"is_ghost length ({len(self.is_ghost)}) must match elements length ({n_elem})"
                )
        else:
            self.is_ghost = [False] * n_elem

        if self.masses is not None:
            if len(self.masses) != n_elem:
                raise ValueError(
                    f"masses length ({len(self.masses)}) must match elements length ({n_elem})"
                )
        return self

    def get_dynamic_masses(self) -> List[float]:
        """Dynamically retrieves atomic masses from mendeleev with ghost-atom guard [M]."""
        if self.masses is not None:
            return list(self.masses)
        resolved: List[float] = []
        for i, z in enumerate(self.atomic_numbers):
            if self.is_ghost[i] or z == 0 or self.elements[i] in ("Gh", "Bq", "X"):
                resolved.append(0.0)
            else:
                resolved.append(float(element(z).mass))
        return resolved


class MCSAlignmentConfig(BaseModel):
    """Configuration options controlling MCS perception and Kabsch alignment [D]."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    timeout_seconds: float = Field(default=30.0, gt=0.0, le=300.0)
    mass_weighting: bool = False
    match_valences: bool = True
    ring_matches_ring_only: bool = True
    complete_rings_only: bool = False
    min_mcs_atoms: int = Field(default=3, ge=3)
    svd_condition_tol: float = Field(default=1e-7, ge=1e-12)
    rmsd_cluster_threshold_angstrom: float = Field(default=0.25, ge=0.01)
    ignore_ghost_atoms: bool = True


class AlignedConformerResult(BaseModel):
    """Superposition result for a single conformer mapped to an invariant reference [D]."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    conformer_id: str
    reference_id: str
    rmsd_angstrom: float = Field(..., ge=0.0)
    rotation_matrix: List[List[float]]
    translation_vector: List[float]
    aligned_coordinates: List[Tuple[float, float, float]]
    atom_mapping: Dict[int, int]
    execution_duration_seconds: float = Field(..., ge=0.0)

    @model_validator(mode="after")
    def validate_rotation(self) -> "AlignedConformerResult":
        """Ensures proper SO(3) orthogonal rotation matrix with det(R) = +1.0 [D]."""
        R = np.array(self.rotation_matrix, dtype=np.float64)
        if R.shape != (3, 3):
            raise ValueError("rotation_matrix must have shape (3, 3)")
        if not np.allclose(R.T @ R, np.eye(3), atol=1e-3):
            raise ValueError("rotation_matrix is not orthogonal (R^T @ R != I)")
        det_R = float(np.linalg.det(R))
        if not np.isclose(det_R, 1.0, atol=1e-3):
            raise ValueError(f"rotation_matrix is not proper SO(3) rotation (det(R)={det_R} != 1.0)")
        if len(self.translation_vector) != 3:
            raise ValueError("translation_vector must have length 3")
        return self


class EnsembleAlignmentSummary(BaseModel):
    """Ensemble-wide alignment, pairwise RMSD matrix, and duplicate cluster summary [D]."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    ensemble_id: str = Field(default="ensemble_default", description="Unique ensemble collection ID")
    reference_id: str
    total_conformers: int
    aligned_conformers: List[AlignedConformerResult]
    pairwise_rmsd_matrix: List[List[float]]
    duplicate_clusters: List[List[str]] = Field(default_factory=list)
    mcs_mapping: Dict[int, int] = Field(default_factory=dict, description="Consensus MCS atom index map")
    aligned_mcs_coords: Optional[List[List[Tuple[float, float, float]]]] = Field(
        default=None, description="Aligned consensus MCS coordinates across ensemble"
    )

    @model_validator(mode="after")
    def validate_summary(self) -> "EnsembleAlignmentSummary":
        """Validates symmetric square pairwise RMSD matrix with zero diagonal [D]."""
        mat = np.array(self.pairwise_rmsd_matrix, dtype=np.float64)
        m = mat.shape[0]
        if mat.shape != (m, m):
            raise ValueError(f"pairwise_rmsd_matrix must be square matrix, got shape {mat.shape}")
        if not np.allclose(mat, mat.T, atol=1e-4):
            raise ValueError("pairwise_rmsd_matrix must be symmetric (D_jk == D_kj)")
        if not np.allclose(np.diag(mat), 0.0, atol=1e-6):
            raise ValueError("pairwise_rmsd_matrix diagonal must be zero")
        if np.any(mat < -1e-6):
            raise ValueError("pairwise_rmsd_matrix elements must be non-negative")
        return self


def _isolated_mcs_worker(
    target_mol_block: str,
    ref_mol_block: str,
    params: dict,
) -> Tuple[bool, int, str]:
    """Module-level isolated worker for cross-process MCS extraction [D]."""
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    target_mol = Chem.MolFromMolBlock(target_mol_block, removeHs=False)
    ref_mol = Chem.MolFromMolBlock(ref_mol_block, removeHs=False)
    if target_mol is None or ref_mol is None:
        return False, 0, ""
    Chem.FastFindRings(target_mol)
    Chem.FastFindRings(ref_mol)

    timeout_sec = float(params.get("timeout_seconds", 30.0))
    rdkit_timeout = max(1, int(timeout_sec))

    atom_comp = rdFMCS.AtomCompare.CompareElements
    bond_comp = rdFMCS.BondCompare.CompareOrder
    match_valences = bool(params.get("match_valences", True))
    ring_matches_ring_only = bool(params.get("ring_matches_ring_only", True))
    complete_rings_only = bool(params.get("complete_rings_only", False))

    res = rdFMCS.FindMCS(
        [target_mol, ref_mol],
        atomCompare=atom_comp,
        bondCompare=bond_comp,
        matchValences=match_valences,
        ringMatchesRingOnly=ring_matches_ring_only,
        completeRingsOnly=complete_rings_only,
        timeout=rdkit_timeout,
    )
    return bool(res.canceled), int(res.numAtoms), str(res.smartsString)


def _build_rdkit_mol_from_conformer(
    conformer: ConformerInput,
    active_indices: List[int],
) -> Chem.Mol:
    """Constructs RDKit 3D molecule for active non-ghost atoms with bond perception fallback [M]."""
    rw_mol = Chem.RWMol()
    for orig_idx in active_indices:
        z = conformer.atomic_numbers[orig_idx]
        atom = Chem.Atom(z)
        rw_mol.AddAtom(atom)

    orig_to_local = {orig_idx: local_idx for local_idx, orig_idx in enumerate(active_indices)}

    if conformer.bonds:
        for u, v, bo in conformer.bonds:
            if u in orig_to_local and v in orig_to_local:
                lu, lv = orig_to_local[u], orig_to_local[v]
                if bo == 2.0:
                    btype = Chem.BondType.DOUBLE
                elif bo == 3.0:
                    btype = Chem.BondType.TRIPLE
                elif bo == 1.5:
                    btype = Chem.BondType.AROMATIC
                else:
                    btype = Chem.BondType.SINGLE
                rw_mol.AddBond(lu, lv, btype)
    else:
        # Distance-based connectivity perception calibrated against Pyykko relativistic covalent radii
        n_active = len(active_indices)
        radii: List[float] = []
        for orig_idx in active_indices:
            z = conformer.atomic_numbers[orig_idx]
            try:
                el = element(z)
                r = el.covalent_radius_pyykko
                if r is None:
                    r = el.covalent_radius
                if r is None:
                    r = 75.0
                radii.append(float(r) / 100.0)
            except Exception:
                radii.append(0.75)

        coords = np.array([conformer.coordinates[i] for i in active_indices], dtype=np.float64)
        for i in range(n_active):
            for j in range(i + 1, n_active):
                d_ij = float(np.linalg.norm(coords[i] - coords[j]))
                cutoff = radii[i] + radii[j] + 0.40
                if d_ij <= cutoff:
                    rw_mol.AddBond(i, j, Chem.BondType.SINGLE)

    mol = rw_mol.GetMol()
    conf = Chem.Conformer(len(active_indices))
    for local_idx, orig_idx in enumerate(active_indices):
        x, y, z = conformer.coordinates[orig_idx]
        conf.SetAtomPosition(local_idx, (float(x), float(y), float(z)))
    mol.AddConformer(conf)
    Chem.FastFindRings(mol)
    return mol


def compute_kabsch_transformation(
    P: np.ndarray,
    Q: np.ndarray,
    weights: Optional[np.ndarray] = None,
    condition_tol: float = 1e-7,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Computes optimal Kabsch proper rotation R and translation t mapping P to Q [D].

    Parameters:
        P: Target coordinate matrix of shape (N, 3).
        Q: Reference coordinate matrix of shape (N, 3).
        weights: Optional non-negative mass weighting vector of shape (N,).
        condition_tol: Singular value condition ratio tolerance for rank-deficiency.

    Returns:
        Tuple containing:
            - R: Proper orthogonal rotation matrix in SO(3) of shape (3, 3) with det(R) = +1.0.
            - t: Optimal translation vector of shape (3,).
            - rmsd: Weighted analytical root-mean-square deviation over mapped coordinates.

    Raises:
        DegenerateCoordinatesError: When coordinates exhibit point degeneracy (sigma_1 < 1e-12).
        CollinearDegeneracyError: When coordinates exhibit collinear rank-deficiency (sigma_2 / sigma_1 < condition_tol).
        IncompatibleTopologyError: When atom count N < 3.
    """
    p_arr = np.asarray(P, dtype=np.float64)
    q_arr = np.asarray(Q, dtype=np.float64)
    if p_arr.ndim != 2 or p_arr.shape[1] != 3:
        raise ValueError(f"P must have shape (N, 3), got {p_arr.shape}")
    if q_arr.ndim != 2 or q_arr.shape[1] != 3:
        raise ValueError(f"Q must have shape (N, 3), got {q_arr.shape}")
    n = p_arr.shape[0]
    if n != q_arr.shape[0]:
        raise ValueError(f"P and Q must have matching atom counts: {n} vs {q_arr.shape[0]}")
    if n < 3:
        raise IncompatibleTopologyError(f"Minimum 3 atoms required for Kabsch alignment, got {n}")

    if weights is None:
        w_arr = np.ones(n, dtype=np.float64)
    else:
        w_arr = np.asarray(weights, dtype=np.float64)
        if w_arr.shape != (n,):
            raise ValueError(f"weights must have shape ({n},), got {w_arr.shape}")
        if np.any(w_arr < 0):
            raise ValueError("weights must be non-negative")

    total_w = float(np.sum(w_arr))
    if total_w <= 0.0:
        raise ValueError("Sum of weights must be strictly positive")

    # Weighted centroids
    p_bar = np.sum(p_arr * w_arr[:, None], axis=0) / total_w
    q_bar = np.sum(q_arr * w_arr[:, None], axis=0) / total_w

    # Centered coordinates
    p_c = p_arr - p_bar
    q_c = q_arr - q_bar

    # Cross-covariance dispersion matrix H = P_c^T W Q_c
    h_mat = p_c.T @ (w_arr[:, None] * q_c)

    # Full SVD decomposition
    u_mat, s_vals, vt_mat = svd(h_mat)
    v_mat = vt_mat.T

    # Point-degeneracy: sigma_1 < 1e-12
    if s_vals[0] < 1e-12:
        raise DegenerateCoordinatesError(
            f"Point-degeneracy detected: primary singular value sigma_1 ({s_vals[0]:.3e}) < 1e-12"
        )

    # Collinear degeneracy: sigma_2 / sigma_1 < condition_tol
    cond_collinear = s_vals[1] / s_vals[0]
    if cond_collinear < condition_tol:
        raise CollinearDegeneracyError(
            f"Collinear coordinates detected: condition ratio sigma_2 / sigma_1 ({cond_collinear:.3e}) < {condition_tol}"
        )

    # Planar stabilization: sigma_2 / sigma_1 >= condition_tol and sigma_3 / sigma_1 < condition_tol
    cond_planar = s_vals[2] / s_vals[0]
    if cond_planar < condition_tol:
        u1, u2 = u_mat[:, 0], u_mat[:, 1]
        v1, v2 = v_mat[:, 0], v_mat[:, 1]
        u3 = np.cross(u1, u2)
        norm_u3 = np.linalg.norm(u3)
        if norm_u3 > 1e-14:
            u3 /= norm_u3
        v3 = np.cross(v1, v2)
        norm_v3 = np.linalg.norm(v3)
        if norm_v3 > 1e-14:
            v3 /= norm_v3
        u_mat = np.column_stack([u1, u2, u3])
        v_mat = np.column_stack([v1, v2, v3])

    # Parity reflection guard d = sgn(det(V @ U^T))
    det_vu = np.linalg.det(v_mat @ u_mat.T)
    d_parity = 1.0 if det_vu >= 0 else -1.0

    s_parity = np.diag([1.0, 1.0, d_parity])
    r_rot = v_mat @ s_parity @ u_mat.T

    # Translation vector t = Q_bar - R @ P_bar
    t_trans = q_bar - r_rot @ p_bar

    # Analytical centered RMSD
    diff = p_c @ r_rot.T - q_c
    rmsd = float(np.sqrt(np.sum(w_arr * np.sum(diff**2, axis=1)) / total_w))

    return r_rot, t_trans, rmsd


def align_conformers_by_mcs(
    target: ConformerInput,
    reference: ConformerInput,
    config: Optional[MCSAlignmentConfig] = None,
) -> AlignedConformerResult:
    """Superimposes a target conformer onto an invariant reference conformer via MCS and Kabsch [D].

    Parameters:
        target: Target conformer input record.
        reference: Invariant reference conformer record.
        config: Optional configuration controlling timeouts, weighting, and tolerances.

    Returns:
        AlignedConformerResult containing transformed coordinates, rotation matrix, and atom mapping.

    Raises:
        MCSConvergenceTimeoutError: If MCS graph search exceeds timeout ceiling or is canceled.
        IncompatibleTopologyError: If common atom count N_MCS < 3.
        CollinearDegeneracyError: If mapped coordinates are collinear.
    """
    start_time = time.perf_counter()
    if config is None:
        config = MCSAlignmentConfig()

    # Ghost atom identification & exclusion
    if config.ignore_ghost_atoms:
        target_active = [
            i for i in range(len(target.elements))
            if not (target.is_ghost[i] or target.atomic_numbers[i] == 0 or target.elements[i] in ("Gh", "Bq", "X"))
        ]
        ref_active = [
            i for i in range(len(reference.elements))
            if not (reference.is_ghost[i] or reference.atomic_numbers[i] == 0 or reference.elements[i] in ("Gh", "Bq", "X"))
        ]
    else:
        target_active = list(range(len(target.elements)))
        ref_active = list(range(len(reference.elements)))

    if len(target_active) < config.min_mcs_atoms or len(ref_active) < config.min_mcs_atoms:
        raise IncompatibleTopologyError(
            f"Insufficient active non-ghost atoms for MCS alignment: target has {len(target_active)}, "
            f"reference has {len(ref_active)}, min required is {config.min_mcs_atoms}"
        )

    target_mol = _build_rdkit_mol_from_conformer(target, target_active)
    ref_mol = _build_rdkit_mol_from_conformer(reference, ref_active)

    target_block = Chem.MolToMolBlock(target_mol)
    ref_block = Chem.MolToMolBlock(ref_mol)

    worker_params = {
        "timeout_seconds": config.timeout_seconds,
        "match_valences": config.match_valences,
        "ring_matches_ring_only": config.ring_matches_ring_only,
        "complete_rings_only": config.complete_rings_only,
    }

    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                _isolated_mcs_worker,
                target_block,
                ref_block,
                worker_params,
            )
            canceled, num_atoms, smarts_str = future.result(timeout=config.timeout_seconds)
    except (concurrent.futures.TimeoutError, TimeoutError):
        raise MCSConvergenceTimeoutError(
            f"MCS graph search exceeded timeout ceiling of {config.timeout_seconds}s"
        )
    except Exception as exc:
        raise ToposAlignmentError(f"MCS worker process encountered unexpected failure: {exc}") from exc

    if canceled:
        raise MCSConvergenceTimeoutError(
            f"MCS graph search canceled (timeout exceeded: {config.timeout_seconds}s)"
        )

    if num_atoms < config.min_mcs_atoms or not smarts_str:
        raise IncompatibleTopologyError(
            f"Common substructure atom count ({num_atoms}) is less than minimum required ({config.min_mcs_atoms})"
        )

    mcs_mol = Chem.MolFromSmarts(smarts_str)
    if mcs_mol is None:
        raise IncompatibleTopologyError(f"Failed to parse MCS SMARTS: {smarts_str}")

    target_match = target_mol.GetSubstructMatch(mcs_mol)
    ref_match = ref_mol.GetSubstructMatch(mcs_mol)
    if not target_match or not ref_match or len(target_match) < config.min_mcs_atoms:
        raise IncompatibleTopologyError(
            f"MCS substructure matching yielded {len(target_match)} mapped atoms, expected >= {config.min_mcs_atoms}"
        )

    atom_mapping: Dict[int, int] = {}
    p_mapped: List[Tuple[float, float, float]] = []
    q_mapped: List[Tuple[float, float, float]] = []
    mapped_weights: List[float] = []

    target_masses = target.get_dynamic_masses()

    for local_t, local_r in zip(target_match, ref_match):
        orig_t = target_active[local_t]
        orig_r = ref_active[local_r]
        atom_mapping[orig_t] = orig_r
        p_mapped.append(target.coordinates[orig_t])
        q_mapped.append(reference.coordinates[orig_r])
        if config.mass_weighting:
            mapped_weights.append(target_masses[orig_t])
        else:
            mapped_weights.append(1.0)

    p_mat = np.array(p_mapped, dtype=np.float64)
    q_mat = np.array(q_mapped, dtype=np.float64)
    w_mat = np.array(mapped_weights, dtype=np.float64) if config.mass_weighting else None

    r_rot, t_trans, rmsd = compute_kabsch_transformation(
        p_mat, q_mat, weights=w_mat, condition_tol=config.svd_condition_tol
    )

    p_full = np.array(target.coordinates, dtype=np.float64)
    p_aligned = p_full @ r_rot.T + t_trans
    aligned_coords = [tuple(row) for row in p_aligned]

    duration = time.perf_counter() - start_time
    return AlignedConformerResult(
        conformer_id=target.conformer_id,
        reference_id=reference.conformer_id,
        rmsd_angstrom=float(rmsd),
        rotation_matrix=r_rot.tolist(),
        translation_vector=t_trans.tolist(),
        aligned_coordinates=aligned_coords,
        atom_mapping=atom_mapping,
        execution_duration_seconds=float(duration),
    )


def cluster_ensemble_conformers(
    conformers: List[ConformerInput],
    reference: ConformerInput,
    config: Optional[MCSAlignmentConfig] = None,
) -> EnsembleAlignmentSummary:
    """Performs batch alignment and pairwise RMSD clustering across a conformer ensemble [D]."""
    if config is None:
        config = MCSAlignmentConfig()

    aligned_conformers: List[AlignedConformerResult] = []
    for conf in conformers:
        aligned_conf = align_conformers_by_mcs(conf, reference, config=config)
        aligned_conformers.append(aligned_conf)

    m = len(conformers)
    pairwise_rmsd = np.zeros((m, m), dtype=np.float64)

    consensus_mapping: Dict[int, int] = {}
    if aligned_conformers:
        consensus_mapping = dict(aligned_conformers[0].atom_mapping)

    aligned_mcs_coords_list: List[List[Tuple[float, float, float]]] = []
    sorted_ref_atoms = sorted(set(consensus_mapping.values()))

    for ac in aligned_conformers:
        rev_map = {r: t for t, r in ac.atom_mapping.items()}
        conf_mcs_pts = []
        for r_idx in sorted_ref_atoms:
            if r_idx in rev_map:
                t_idx = rev_map[r_idx]
                conf_mcs_pts.append(ac.aligned_coordinates[t_idx])
        if conf_mcs_pts:
            aligned_mcs_coords_list.append(conf_mcs_pts)

    has_mcs_coords = len(aligned_mcs_coords_list) == m and all(
        len(pts) == len(aligned_mcs_coords_list[0]) for pts in aligned_mcs_coords_list
    )

    for j in range(m):
        for k in range(j + 1, m):
            if has_mcs_coords:
                pts_j = np.array(aligned_mcs_coords_list[j], dtype=np.float64)
                pts_k = np.array(aligned_mcs_coords_list[k], dtype=np.float64)
            else:
                pts_j = np.array(aligned_conformers[j].aligned_coordinates, dtype=np.float64)
                pts_k = np.array(aligned_conformers[k].aligned_coordinates, dtype=np.float64)
            diff = pts_j - pts_k
            rmsd_val = float(np.sqrt(np.mean(np.sum(diff**2, axis=1))))
            pairwise_rmsd[j, k] = rmsd_val
            pairwise_rmsd[k, j] = rmsd_val

    # Duplicate clustering via connected components
    threshold = config.rmsd_cluster_threshold_angstrom
    visited = [False] * m
    duplicate_clusters: List[List[str]] = []

    for i in range(m):
        if visited[i]:
            continue
        cluster_indices = [i]
        queue = [i]
        visited[i] = True
        while queue:
            curr = queue.pop(0)
            for nxt in range(m):
                if not visited[nxt] and pairwise_rmsd[curr, nxt] < threshold:
                    visited[nxt] = True
                    queue.append(nxt)
                    cluster_indices.append(nxt)
        if len(cluster_indices) >= 2:
            duplicate_clusters.append([conformers[idx].conformer_id for idx in cluster_indices])

    return EnsembleAlignmentSummary(
        ensemble_id=f"ens_{reference.conformer_id}",
        reference_id=reference.conformer_id,
        total_conformers=m,
        aligned_conformers=aligned_conformers,
        pairwise_rmsd_matrix=pairwise_rmsd.tolist(),
        duplicate_clusters=duplicate_clusters,
        mcs_mapping=consensus_mapping,
        aligned_mcs_coords=aligned_mcs_coords_list if has_mcs_coords else None,
    )


def persist_aligned_ensemble_h5(
    summary: EnsembleAlignmentSummary,
    archive_path: Path,
    lock_timeout: float = 30.0,
) -> Path:
    """Persists aligned conformer trajectories and RMSD matrices into HDF5 under 6-tier concurrency [D]."""
    t_store_env = os.environ.get("COCH_STORE_DIR")
    t_store = Path(t_store_env).resolve() if t_store_env else (Path.home() / ".cochem" / "store").resolve()
    resolved_path = archive_path.resolve()

    try:
        resolved_path.relative_to(t_store)
    except ValueError:
        raise AirGapBoundaryViolationError(
            f"Archive path {resolved_path} violates Tripartite Air-Gap: must reside inside {t_store}"
        )

    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    tier = detect_concurrency_tier()
    lock_file_path = str(resolved_path) + ".lock"

    if tier == StorageTier.TIER6_HPC:
        hpc_scratch = os.environ.get("SLURM_TMPDIR") or os.environ.get("COCH_SCRATCH")
        if hpc_scratch:
            scratch_dir = Path(hpc_scratch) / "cochem_staging"
            scratch_dir.mkdir(parents=True, exist_ok=True)
            staging_path = scratch_dir / f"{resolved_path.name}.tmp.{os.getpid()}"
        else:
            staging_path = resolved_path.with_name(f"{resolved_path.name}.tmp.{os.getpid()}")
    else:
        staging_path = resolved_path.with_name(f"{resolved_path.name}.tmp.{os.getpid()}")

    libver = "latest" if tier in (StorageTier.TIER2_MACOS, StorageTier.TIER3_LINUX) else "earliest"

    with filelock.FileLock(lock_file_path, timeout=lock_timeout):
        with h5py.File(staging_path, "w", libver=libver) as h5f:
            ens_grp = h5f.require_group(f"/ensembles/{summary.ensemble_id}")
            rmsd_arr = np.array(summary.pairwise_rmsd_matrix, dtype=np.float32)
            ens_grp.create_dataset("pairwise_rmsd", data=rmsd_arr, dtype="float32")

            mapping_items = sorted(summary.mcs_mapping.items())
            mapping_arr = np.array(mapping_items, dtype=np.int32) if mapping_items else np.empty((0, 2), dtype=np.int32)
            ens_grp.create_dataset("mcs_mapping", data=mapping_arr, dtype="int32")

            if summary.aligned_conformers:
                atom_counts = [len(c.aligned_coordinates) for c in summary.aligned_conformers]
                if len(set(atom_counts)) == 1:
                    coords_arr = np.array(
                        [c.aligned_coordinates for c in summary.aligned_conformers], dtype=np.float64
                    )
                    ens_grp.create_dataset("aligned_coords", data=coords_arr, dtype="float64")
                else:
                    conf_grp = ens_grp.require_group("conformers")
                    for c in summary.aligned_conformers:
                        c_coords = np.array(c.aligned_coordinates, dtype=np.float64)
                        conf_grp.create_dataset(f"{c.conformer_id}/aligned_coords", data=c_coords, dtype="float64")

            if summary.aligned_mcs_coords is not None:
                mcs_coords_arr = np.array(summary.aligned_mcs_coords, dtype=np.float64)
                ens_grp.create_dataset("aligned_mcs_coords", data=mcs_coords_arr, dtype="float64")

        if staging_path.parent == resolved_path.parent:
            os.replace(staging_path, resolved_path)
        else:
            import shutil
            shutil.move(str(staging_path), str(resolved_path))

    return resolved_path
