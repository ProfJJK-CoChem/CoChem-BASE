"""
CoChem-TORQ: Phase 3 Clash Evasion & Quench System
===================================================
Protects downstream electronic structure engines from SCF divergence
caused by severe atomic overlap during large-amplitude torsional rotations.

Authoritative Standards:
- Method Matrix: Stage 2.0 - 2.1 Steric Clash Detection & Soft Quench
- Covalent Radii Thresholds & Micro-Randomization Singularity Avoidance
"""

from __future__ import annotations

import functools
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from mendeleev import element

logger = logging.getLogger("CoChem-TORQ.Quench")


@functools.lru_cache(maxsize=128)
def get_dynamic_covalent_radius_ang(symbol: str) -> float:
    """Retrieve covalent radius in Angstroms dynamically from mendeleev."""
    clean_sym = symbol.strip().capitalize()
    el = element(clean_sym)
    if getattr(el, "covalent_radius_pyykko", None):
        return float(el.covalent_radius_pyykko) / 100.0
    elif getattr(el, "covalent_radius", None):
        return float(el.covalent_radius) / 100.0
    raise ValueError(f"No dynamic covalent radius is available for {clean_sym}")


def detect_covalent_clashes(
    symbols: Sequence[str],
    coordinates: np.ndarray,
    clash_ratio: float = 0.70,
) -> List[Tuple[int, int, float, float]]:
    """
    Identifies pairs of atoms whose interatomic distance is shorter than
    clash_ratio * (r_cov(i) + r_cov(j)).
    Returns list of (atom_i, atom_j, actual_distance, threshold_distance).
    """
    coords = np.asarray(coordinates, dtype=np.float64)
    n_atoms = len(symbols)
    clashes: List[Tuple[int, int, float, float]] = []

    for i in range(n_atoms):
        sym_i = symbols[i].capitalize()
        r_i = get_dynamic_covalent_radius_ang(sym_i)
        for j in range(i + 1, n_atoms):
            sym_j = symbols[j].capitalize()
            r_j = get_dynamic_covalent_radius_ang(sym_j)
            thresh = (r_i + r_j) * clash_ratio
            dist = float(np.linalg.norm(coords[i] - coords[j]))
            if dist < thresh:
                clashes.append((i, j, dist, thresh))

    return clashes


def execute_soft_quench(
    symbols: Sequence[str],
    coordinates: np.ndarray,
    frozen_dihedrals: Optional[List[Tuple[int, int, int, int]]] = None,
    max_steps: int = 50,
    damping: float = 0.2,
    clash_ratio: float = 0.70,
) -> Dict[str, Any]:
    """
    Executes heavily damped numerical relaxation to relieve steric overlap
    while holding dihedral central axis coordinates restrained.
    """
    coords = np.array(coordinates, dtype=np.float64, copy=True)
    initial_clashes = detect_covalent_clashes(symbols, coords, clash_ratio)

    if not initial_clashes:
        return {
            "relaxed_coordinates": coords,
            "initial_clash_count": 0,
            "final_clash_count": 0,
            "converged": True,
            "steps_taken": 0,
            "method": "soft_quench_bypass",
            "scope": "geometric clash relief; no electronic optimization",
        }

    # Restrain only central bond atoms (j, k) of frozen dihedrals (i, j, k, l)
    restrained_atoms = set()
    if frozen_dihedrals:
        for dih in frozen_dihedrals:
            if len(dih) >= 4:
                restrained_atoms.add(dih[1])
                restrained_atoms.add(dih[2])

    step = 0
    while step < max_steps:
        clashes = detect_covalent_clashes(symbols, coords, clash_ratio)
        if not clashes:
            break

        forces = np.zeros_like(coords)
        for i, j, dist, thresh in clashes:
            delta = coords[i] - coords[j]
            norm = max(dist, 1e-4)
            unit_vec = delta / norm
            overlap = thresh - dist
            repulsion = 2.0 * overlap

            i_fixed = i in restrained_atoms
            j_fixed = j in restrained_atoms

            if not i_fixed and not j_fixed:
                forces[i] += unit_vec * repulsion
                forces[j] -= unit_vec * repulsion
            elif not i_fixed and j_fixed:
                forces[i] += unit_vec * (2.0 * repulsion)
            elif i_fixed and not j_fixed:
                forces[j] -= unit_vec * (2.0 * repulsion)
            else:
                # Both restrained: allow relaxation to prevent steric singularity
                forces[i] += unit_vec * repulsion
                forces[j] -= unit_vec * repulsion

        coords += damping * forces
        step += 1

    final_clashes = detect_covalent_clashes(symbols, coords, clash_ratio)
    converged = len(final_clashes) == 0

    logger.info(
        "Soft quench completed in %d steps: clashes %d -> %d (converged=%s)",
        step,
        len(initial_clashes),
        len(final_clashes),
        converged,
    )

    return {
        "relaxed_coordinates": coords,
        "initial_clash_count": len(initial_clashes),
        "final_clash_count": len(final_clashes),
        "converged": converged,
        "steps_taken": step,
        "method": "soft_quench",
        "scope": "geometric clash relief; no electronic optimization",
    }


def execute_jiggle_quench(
    symbols: Sequence[str],
    coordinates: np.ndarray,
    frozen_dihedrals: Optional[List[Tuple[int, int, int, int]]] = None,
    jiggle_amplitude: float = 0.02,
    max_steps: int = 30,
    clash_ratio: float = 0.70,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Introduces controlled micro-randomization (+/- jiggle_amplitude Angstrom)
    followed by numerical relaxation to route around geometric singularities.
    """
    rng = np.random.default_rng(seed)
    coords = np.array(coordinates, dtype=np.float64, copy=True)
    initial_clashes = detect_covalent_clashes(symbols, coords, clash_ratio)

    restrained_atoms = set()
    if frozen_dihedrals:
        for dih in frozen_dihedrals:
            if len(dih) >= 4:
                restrained_atoms.add(dih[1])
                restrained_atoms.add(dih[2])

    perturbation = rng.normal(loc=0.0, scale=jiggle_amplitude, size=coords.shape)
    for idx in restrained_atoms:
        perturbation[idx] = 0.0

    coords += perturbation

    quench_result = execute_soft_quench(
        symbols=symbols,
        coordinates=coords,
        frozen_dihedrals=frozen_dihedrals,
        max_steps=max_steps,
        damping=0.15,
        clash_ratio=clash_ratio,
    )

    final_clashes = quench_result["final_clash_count"]

    logger.info(
        "Jiggle quench completed: initial clashes=%d, final clashes=%d, converged=%s",
        len(initial_clashes),
        final_clashes,
        quench_result["converged"],
    )

    return {
        "relaxed_coordinates": quench_result["relaxed_coordinates"],
        "initial_clash_count": len(initial_clashes),
        "final_clash_count": final_clashes,
        "converged": quench_result["converged"],
        "steps_taken": quench_result["steps_taken"],
        "method": "jiggle_quench",
        "scope": "geometric clash relief; no electronic optimization",
    }


class QuenchReevaluationRequiredError(RuntimeError):
    """Geometry changed without a native selected-engine reevaluation."""

    def __init__(self, message: str, geometry_result: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.geometry_result = geometry_result


def format_to_qcschema_v1(
    symbols: Sequence[str],
    coordinates: np.ndarray,
    energy: Optional[float] = None,
    temperature_k: float = 298.15,
    pressure_atm: float = 1.0,
    provenance: Optional[Dict[str, Any]] = None,
    charge: int = 0,
    multiplicity: int = 1,
) -> Dict[str, Any]:
    """Export a supplied geometric state as a QCSchema molecule, in Bohr.

    Clash relief does not compute an electronic energy. Native result producers
    own result schemas and their state/method/source receipts.
    """
    if energy is not None:
        raise QuenchReevaluationRequiredError("A geometric quench cannot certify an electronic result; use the selected scientific provider")
    from cochem_base.core.cochem_constants import ANGSTROM_TO_BOHR
    coords = np.asarray(coordinates, dtype=np.float64)
    if coords.shape != (len(symbols), 3) or not np.all(np.isfinite(coords)):
        raise ValueError("A supplied quench geometry requires finite N-by-3 coordinates")
    if isinstance(charge, bool) or not isinstance(charge, int) or isinstance(multiplicity, bool) or not isinstance(multiplicity, int) or multiplicity < 1:
        raise ValueError("Molecular state requires integer charge and positive multiplicity")
    return {
        "schema_name": "qcschema_molecule", "schema_version": 2,
        "symbols": [str(symbol) for symbol in symbols],
        "geometry": (coords * ANGSTROM_TO_BOHR).reshape(-1).tolist(),
        "molecular_charge": charge, "molecular_multiplicity": multiplicity,
        "extras": {"scope": "supplied geometry; no electronic result or stationary-minimum claim", "source": provenance or {}},
    }


class ConformalMDQuencher:
    """Couples Conformal Prediction uncertainty quantification with MD trajectory rollback and quenching [M]."""

    def __init__(
        self,
        conformal_predictor: Optional[Any] = None,
        hdf5_store_path: Optional[Union[str, Path]] = None,
        check_interval: int = 5,
        force_uncertainty_threshold: float = 0.50,
    ) -> None:
        self.conformal_predictor = conformal_predictor
        self.hdf5_store_path = Path(hdf5_store_path) if hdf5_store_path else None
        self.check_interval = max(1, int(check_interval))
        self.force_uncertainty_threshold = force_uncertainty_threshold
        self.last_checkpoint_coords: Optional[np.ndarray] = None
        self.last_checkpoint_symbols: Optional[List[str]] = None

    def step(
        self,
        step_idx: int,
        symbols: Sequence[str],
        coordinates: np.ndarray,
        forces_sigma: Optional[Any] = None,
        forces_pred: Optional[Any] = None,
        energy_pred: Optional[float] = None,
        energy_sigma: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Evaluate MD step with conformal bounds, triggering rollback and quench if uncertainty exceeded."""
        coords = np.asarray(coordinates, dtype=np.float64)
        syms = [str(s).capitalize() for s in symbols]

        # Initial checkpoint if not set
        if self.last_checkpoint_coords is None:
            self.last_checkpoint_coords = np.copy(coords)
            self.last_checkpoint_symbols = list(syms)

        should_check = (step_idx % self.check_interval == 0)

        uncertainty_exceeded = False
        if should_check:
            # 1. Check steric clashes
            clashes = detect_covalent_clashes(syms, coords)
            if len(clashes) > 0:
                uncertainty_exceeded = True

            # 2. Check epistemic force uncertainty and conformal bounds
            if forces_sigma is not None:
                max_f_sig = float(forces_sigma.max().item())
                if max_f_sig > self.force_uncertainty_threshold:
                    uncertainty_exceeded = True

                if self.conformal_predictor is not None and getattr(self.conformal_predictor, "is_calibrated", False):
                    q_force = getattr(self.conformal_predictor, "q_hat_force", float("inf"))
                    eps_f = getattr(self.conformal_predictor, "eps_f", 1e-4)
                    conformal_half_width = q_force * (max_f_sig + eps_f)
                    if conformal_half_width > self.force_uncertainty_threshold:
                        uncertainty_exceeded = True

        if should_check and uncertainty_exceeded:
            # Halt dynamics, rollback to last checkpoint
            rollback_coords = (
                np.copy(self.last_checkpoint_coords)
                if self.last_checkpoint_coords is not None
                else np.copy(coords)
            )

            # Apply physical quench (soft quench)
            quench_result = execute_soft_quench(syms, rollback_coords)
            quenched_coords = quench_result["relaxed_coordinates"]
            diagnostic = {
                "action": "REEVALUATION_REQUIRED", "step_idx": step_idx,
                "quenched_coordinates": quenched_coords,
                "qcschema_molecule": format_to_qcschema_v1(syms, quenched_coords),
                "scientific_status": "uncomputed", "energy_hartree": None,
                "discarded_pre_quench_prediction": energy_pred is not None,
                "geometric_clash_relief": quench_result,
            }
            # The old geometry's prediction is not the changed geometry's energy.
            # Do not continue MD or append a successful quantum result to HDF5.
            raise QuenchReevaluationRequiredError(
                "Rollback/clash relief requires a fresh selected-engine energy and gradient before dynamics resumes",
                diagnostic,
            )

        # Otherwise continue and record checkpoint
        self.last_checkpoint_coords = np.copy(coords)
        self.last_checkpoint_symbols = list(syms)
        return {
            "action": "CONTINUE",
            "step_idx": step_idx,
        }
