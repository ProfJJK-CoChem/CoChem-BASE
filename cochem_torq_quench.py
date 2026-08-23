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

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from cochem_torq_topology import COVALENT_RADII_ANG

logger = logging.getLogger("CoChem-TORQ.Quench")


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
        r_i = COVALENT_RADII_ANG.get(sym_i, 0.76)
        for j in range(i + 1, n_atoms):
            sym_j = symbols[j].capitalize()
            r_j = COVALENT_RADII_ANG.get(sym_j, 0.76)
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
    }
