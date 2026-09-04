"""Active Learning Orchestrator for dynamic QM selection, Kabsch RMSD, and air-gapped manifests.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic physics, dynamic Mendeleev masses, and air-gapped serialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
import torch

from Libraries.cochem_torq_inference_errors import (
    ActiveLearningSelectionError,
    AirGapViolationError,
)
from Libraries.cochem_torq_inference_schemas import ActiveLearningOrchestratorConfig
from Libraries.cochem_torq_masses import get_monoisotopic_mass


class ActiveLearningState(str, Enum):
    """Lifecycle state machine for active learning candidates. [M]"""

    UNLABELED = "UNLABELED"
    CANDIDATE_SELECTED = "CANDIDATE_SELECTED"
    MANIFEST_EMITTED = "MANIFEST_EMITTED"
    QM_COMPLETED = "QM_COMPLETED"
    INGESTED = "INGESTED"


@dataclass
class CandidateGeometry:
    """Authentic physical molecular geometry with committee uncertainty telemetry. [M]"""

    candidate_id: str
    coordinates: np.ndarray             # (N, 3) in Angstroms
    atomic_numbers: List[int]           # (N,) atomic numbers Z
    energy_variance: float              # sigma_E^2 in eV^2
    max_force_std: float                # alpha_F^std in eV/Angstrom
    rotational_constants: Tuple[float, float, float] # (A, B, C) in cm^-1
    state: ActiveLearningState = ActiveLearningState.UNLABELED
    assigned_tier: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def compute_qbc_energy_variance(energies: Sequence[float]) -> float:
    """Compute Query-by-Committee (QBC) unbiased energy sample variance. [D]
    
    sigma_E^2(X) = 1/(M-1) sum_m (E_m - E_mean)^2
    """
    m = len(energies)
    if m < 2:
        raise ActiveLearningSelectionError(
            f"QBC energy variance requires at least 2 committee predictions, got M={m}.",
            diagnostics={"num_models": m},
        )
    arr = np.asarray(energies, dtype=np.float64)
    mean_e = np.mean(arr)
    var_e = np.sum((arr - mean_e) ** 2) / float(m - 1)
    return float(max(0.0, var_e))


def compute_max_force_epistemic_std(forces: np.ndarray) -> float:
    """Compute maximum atomic force epistemic standard deviation alpha_F^std in eV/Angstrom. [D]
    
    forces shape: (M, N, 3)
    alpha_F^std = max_i sqrt( 1/(M-1) sum_m ||F_{i,m} - F_{i,mean}||_2^2 )
    """
    m, n, _ = forces.shape
    if m < 2:
        raise ActiveLearningSelectionError(
            f"Force epistemic variance requires at least 2 committee predictions, got M={m}.",
            diagnostics={"num_models": m},
        )
    mean_f = np.mean(forces, axis=0, keepdims=True) # (1, N, 3)
    diff_f = forces - mean_f                        # (M, N, 3)
    sq_norm = np.sum(diff_f ** 2, axis=-1)          # (M, N)
    var_f = np.sum(sq_norm, axis=0) / float(m - 1)  # (N,)
    stds = np.sqrt(np.maximum(0.0, var_f))          # (N,)
    return float(np.max(stds))


def center_geometry_mass_weighted(
    coordinates: np.ndarray,
    atomic_numbers: Sequence[int],
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute Mendeleev mass-weighted center of mass and translate to origin. [M]/[D]
    
    Returns (centered_coords, com).
    """
    coords = np.asarray(coordinates, dtype=np.float64)
    masses = np.array([get_monoisotopic_mass(int(z)) for z in atomic_numbers], dtype=np.float64)
    total_mass = np.sum(masses)
    if total_mass <= 1e-12:
        raise ActiveLearningSelectionError("Total molecular mass must be strictly positive.")

    com = np.sum(coords * masses[:, np.newaxis], axis=0) / total_mass
    centered = coords - com[np.newaxis, :]
    return centered, com


def compute_rotational_constants(
    coordinates: np.ndarray,
    atomic_numbers: Sequence[int],
) -> Tuple[float, float, float]:
    """Compute principal rotational constants (A, B, C) in cm^-1 via Mendeleev inertia tensor. [D]
    
    I_{alpha, beta} = sum_i m_i (||x'_i||^2 delta_{alpha, beta} - x'_{i, alpha} x'_{i, beta})
    A = h / (8 pi^2 c I_A), B = h / (8 pi^2 c I_B), C = h / (8 pi^2 c I_C)
    """
    centered, _ = center_geometry_mass_weighted(coordinates, atomic_numbers)
    masses = np.array([get_monoisotopic_mass(int(z)) for z in atomic_numbers], dtype=np.float64)

    r2 = np.sum(centered ** 2, axis=1) # (N,)
    inertia = np.array(
        [
            [
                np.sum(masses * ((1.0 if alpha == beta else 0.0) * r2 - centered[:, alpha] * centered[:, beta]))
                for beta in range(3)
            ]
            for alpha in range(3)
        ],
        dtype=np.float64,
    )

    # Diagonalize inertia tensor
    eigvals = np.linalg.eigvalsh(inertia)
    eigvals = np.sort(np.maximum(1e-12, eigvals))
    ia, ib, ic = eigvals[0], eigvals[1], eigvals[2]

    # Conversion factor from u * Angstrom^2 to cm^-1:
    # h / (8 * pi^2 * c * 1.66053906660e-47 kg m^2) approx 16.8576292
    h_c_factor = 16.857629204031
    const_a = float(h_c_factor / ia)
    const_b = float(h_c_factor / ib)
    const_c = float(h_c_factor / ic)
    return (const_a, const_b, const_c)


def kabsch_rmsd(
    coords_a: np.ndarray,
    coords_b: np.ndarray,
) -> float:
    """Compute pairwise minimum root-mean-square deviation via Kabsch SVD in SO(3). [D]
    
    D_geom = sqrt( 1/N sum_i ||x_{a,i} - x_{b,i} R||_2^2 )
    """
    p = np.asarray(coords_a, dtype=np.float64)
    q = np.asarray(coords_b, dtype=np.float64)
    n = p.shape[0]

    # Center both coordinates at centroid
    p_c = p - np.mean(p, axis=0, keepdims=True)
    q_c = q - np.mean(q, axis=0, keepdims=True)

    # Covariance matrix H = p_c^T @ q_c
    h = np.dot(p_c.T, q_c)
    u, s, vt = np.linalg.svd(h)
    v = vt.T

    # Reflection determinant correction
    d = np.linalg.det(np.dot(v, u.T))
    s_mat = np.diag([1.0, 1.0, np.sign(d)])

    # Optimal rotation matrix R in SO(3)
    r = np.dot(np.dot(v, s_mat), u.T)

    # Rotated q coordinates
    q_rot = np.dot(q_c, r)
    diff = p_c - q_rot
    rmsd = np.sqrt(np.mean(np.sum(diff ** 2, axis=1)))
    return float(rmsd)


def check_stage_b_rotational_redundancy(
    rot_a: Tuple[float, float, float],
    rot_b: Tuple[float, float, float],
    threshold: float = 0.001,
) -> bool:
    """Stage B relative rotational constant invariance check max(|Delta B| / B) < threshold. [M]"""
    a_a, b_a, c_a = rot_a
    a_b, b_b, c_b = rot_b

    rel_a = abs(a_a - a_b) / max(1e-12, a_a)
    rel_b = abs(b_a - b_b) / max(1e-12, b_a)
    rel_c = abs(c_a - c_b) / max(1e-12, c_a)

    max_rel = max(rel_a, rel_b, rel_c)
    return max_rel < threshold


def route_qm_tier(
    max_force_std: float,
    hardware_topology: Optional[Any] = None,
    compute_budget_hours: Optional[float] = None,
    available_engines: Optional[Sequence[str]] = None,
    interactive_gate: Optional[Callable[..., bool]] = None,
    **kwargs: Any,
) -> str:
    """Route candidate dynamically based on epistemic force uncertainty severity and hardware availability [M].

    - Moderate (0.05 < alpha_F <= 0.20 eV/A): Tier T3-10s GFN2-xTB
    - High (0.20 < alpha_F <= 0.80 eV/A): Tier T3O-1h ORCA 6.0 omegaB97X-V/jun-cc-pVTZ
    - Extreme (alpha_F > 0.80 eV/A): Tier T3O-12h Canonical junChS composite scheme

    Hardware Triage Gate:
    Inspects available local computational engines (e.g. ORCA, CFOUR) and the allocated compute budget
    before assigning high-force-uncertainty candidates to high-cost composite tiers.
    If a required engine is absent or projected wall-clock time exceeds budget, triggers an interactive
    decision gate or gracefully degrades to the highest supported tier (e.g., 'B3LYP-D4/def2-TZVP' or 'T3O-1h').
    """
    if max_force_std <= 0.20:
        nominal_tier = "T3-10s"
    elif max_force_std <= 0.80:
        nominal_tier = "T3O-1h"
    else:
        nominal_tier = "T3O-12h"

    if nominal_tier == "T3-10s":
        return nominal_tier

    # Normalize engine availability
    engines: List[str] = []
    if available_engines is not None:
        engines = [e.lower() for e in available_engines]
    elif hardware_topology is not None and hasattr(hardware_topology, "available_engines") and hardware_topology.available_engines:
        engines = [e.lower() for e in hardware_topology.available_engines]
    else:
        import shutil
        if shutil.which("orca") is not None:
            engines.append("orca")
        if shutil.which("xcfour") is not None or shutil.which("cfour") is not None:
            engines.append("cfour")
        if shutil.which("xtb") is not None:
            engines.append("xtb")

    # Ingest compute budget from hardware topology if not explicitly provided
    if compute_budget_hours is None and hardware_topology is not None and hasattr(hardware_topology, "compute_budget_hours"):
        compute_budget_hours = float(hardware_topology.compute_budget_hours)

    needs_cfour = (nominal_tier == "T3O-12h")
    needs_orca = (nominal_tier in ("T3O-1h", "T3O-12h"))
    has_cfour = "cfour" in engines
    has_orca = "orca" in engines

    projected_hours = 12.0 if nominal_tier == "T3O-12h" else 1.0
    budget_exceeded = (compute_budget_hours is not None and compute_budget_hours < projected_hours)

    # Core capacity gate from hardware topology: T3O-12h requires >= 4 P-cores for parallel CC
    if hardware_topology is not None and nominal_tier == "T3O-12h":
        p_cores = getattr(hardware_topology, "p_cores", None)
        if p_cores is not None and p_cores < 4:
            budget_exceeded = True

    missing_engines: List[str] = []
    if needs_cfour and not has_cfour:
        missing_engines.append("CFOUR")
    if needs_orca and not has_orca:
        missing_engines.append("ORCA")

    if missing_engines or budget_exceeded:
        if interactive_gate is not None:
            decision = interactive_gate(
                nominal_tier=nominal_tier,
                missing_engines=missing_engines,
                budget_exceeded=budget_exceeded,
                compute_budget_hours=compute_budget_hours,
            )
            if decision:
                return nominal_tier

        # Graceful degradation cascade [M]
        if has_orca:
            if budget_exceeded and compute_budget_hours is not None and compute_budget_hours < 1.0:
                return "T3-10s" if "xtb" in engines else "B3LYP-D4/def2-TZVP"
            return "B3LYP-D4/def2-TZVP" if nominal_tier == "T3O-12h" else "T3O-1h"
        elif "xtb" in engines:
            return "T3-10s"
        else:
            return "B3LYP-D4/def2-TZVP"

    return nominal_tier


class ActiveLearningOrchestrator:
    """Active Learning engine coordinating candidate acquisition, deduplication, and air-gapped manifests. [M]"""

    def __init__(self, config: ActiveLearningOrchestratorConfig) -> None:
        self.config = config
        self.pool: List[CandidateGeometry] = []
        self.selected_batch: List[CandidateGeometry] = []

    def evaluate_pool(
        self,
        geometries: Sequence[np.ndarray],
        atomic_numbers: Sequence[Sequence[int]],
        committee_energies: Sequence[Sequence[float]],
        committee_forces: Sequence[np.ndarray],
        candidate_ids: Optional[Sequence[str]] = None,
    ) -> List[CandidateGeometry]:
        """Evaluate unlabeled pool and instantiate CandidateGeometry representations. [M]"""
        p = len(geometries)
        self.pool.clear()

        for idx in range(p):
            cid = candidate_ids[idx] if candidate_ids is not None else f"cand_{idx:04d}"
            coords = np.asarray(geometries[idx], dtype=np.float64)
            z = list(atomic_numbers[idx])
            e_m = list(committee_energies[idx])
            f_m = np.asarray(committee_forces[idx], dtype=np.float64)

            var_e = compute_qbc_energy_variance(e_m)
            max_f_std = compute_max_force_epistemic_std(f_m)
            rot_consts = compute_rotational_constants(coords, z)

            candidate = CandidateGeometry(
                candidate_id=cid,
                coordinates=coords,
                atomic_numbers=z,
                energy_variance=var_e,
                max_force_std=max_f_std,
                rotational_constants=rot_consts,
                state=ActiveLearningState.UNLABELED,
            )
            self.pool.append(candidate)

        return self.pool

    def select_active_batch(self) -> List[CandidateGeometry]:
        """Apply acquisition triggering and two-stage deduplication to assemble active batch. [M]"""
        triggered: List[CandidateGeometry] = []

        # 1. Acquisition Filter
        th_f = self.config.force_uncertainty_threshold_ev_per_angstrom
        th_e = self.config.energy_uncertainty_threshold_ev2_per_atom

        for cand in self.pool:
            n_atoms = len(cand.atomic_numbers)
            per_atom_e_var = cand.energy_variance / float(max(1, n_atoms))

            if cand.max_force_std > th_f or per_atom_e_var > th_e:
                cand.state = ActiveLearningState.CANDIDATE_SELECTED
                cand.assigned_tier = route_qm_tier(cand.max_force_std)
                triggered.append(cand)

        # 2. Sort descending by uncertainty score alpha_F^std
        triggered.sort(key=lambda c: c.max_force_std, reverse=True)

        # 3. Two-Stage Deduplication
        rmsd_th = self.config.stage_a_rmsd_threshold_angstrom
        rot_th = self.config.stage_b_rotational_threshold
        capacity = self.config.batch_capacity_k

        self.selected_batch.clear()

        for cand in triggered:
            is_redundant = False
            for selected in self.selected_batch:
                # Require identical chemical composition
                if cand.atomic_numbers != selected.atomic_numbers:
                    continue

                # Stage A: Kabsch SVD RMSD
                d_geom = kabsch_rmsd(cand.coordinates, selected.coordinates)
                if d_geom < rmsd_th:
                    is_redundant = True
                    break

                # Stage B: Rotational Constant Invariance
                if check_stage_b_rotational_redundancy(
                    cand.rotational_constants,
                    selected.rotational_constants,
                    threshold=rot_th,
                ):
                    is_redundant = True
                    break

            if not is_redundant:
                self.selected_batch.append(cand)
                if len(self.selected_batch) >= capacity:
                    break

        return self.selected_batch

    def emit_air_gapped_manifest(
        self,
        manifest_filename: str = "active_learning_manifest.json",
    ) -> Tuple[Path, str]:
        """Atomically serialize selected structures into an air-gapped job manifest with SHA-256. [M]"""
        staging_dir = Path(self.config.staging_manifest_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)

        manifest_data = {
            "version": "1.0.0",
            "batch_capacity": self.config.batch_capacity_k,
            "selected_count": len(self.selected_batch),
            "candidates": [
                {
                    "candidate_id": c.candidate_id,
                    "atomic_numbers": c.atomic_numbers,
                    "coordinates": c.coordinates.tolist(),
                    "energy_variance": c.energy_variance,
                    "max_force_std": c.max_force_std,
                    "assigned_tier": c.assigned_tier,
                    "rotational_constants": list(c.rotational_constants),
                    "state": ActiveLearningState.MANIFEST_EMITTED.value,
                }
                for c in self.selected_batch
            ],
        }

        manifest_path = staging_dir / manifest_filename
        tmp_path = staging_dir / f"{manifest_filename}.tmp"

        payload_bytes = json.dumps(manifest_data, indent=2).encode("utf-8")
        sha256_hash = hashlib.sha256(payload_bytes).hexdigest()

        # Atomic serialization: write .tmp -> fsync -> replace
        with open(tmp_path, "wb") as f:
            f.write(payload_bytes)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, manifest_path)

        # Accompanying SHA-256 digest file
        digest_path = manifest_path.with_suffix(manifest_path.suffix + ".sha256")
        digest_path.write_text(f"{sha256_hash}  {manifest_path.name}\n", encoding="utf-8")

        # Update candidate state transitions
        for c in self.selected_batch:
            c.state = ActiveLearningState.MANIFEST_EMITTED

        return manifest_path, sha256_hash
