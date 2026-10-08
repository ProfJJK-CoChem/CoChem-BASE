"""
CoChem-TORQ: Phase 3 ML Pre-Flight & Adaptive Grid Triage
=========================================================
Executes spatial scanning using ML / empirical surrogate potentials to map
out PES topography, dynamically refining calculation density at transition states.

Authoritative Standards:
- Method Matrix: Stage 2.0 - 2.1 ML Pre-Flight & Adaptive Triage
- First-Derivative PES Density Tightening
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import networkx as nx
import numpy as np

from cochem_base.cochem_torq_topology import build_molecular_graph

logger = logging.getLogger("CoChem-TORQ.MACE")


def rotate_dihedral_angle(
    coordinates: np.ndarray,
    dihedral_indices: Tuple[int, int, int, int],
    delta_angle_deg: float,
    graph: Optional[nx.Graph] = None,
) -> np.ndarray:
    """
    Rotates all atoms on one side of the central bond (j, k) by delta_angle_deg
    around the unit vector connecting j and k using Rodrigues' rotation formula.
    """
    coords = np.array(coordinates, dtype=np.float64, copy=True)
    i_idx, j_idx, k_idx, l_idx = dihedral_indices

    # Central bond axis: unit vector from j to k
    p_j = coords[j_idx]
    p_k = coords[k_idx]
    axis = p_k - p_j
    norm = np.linalg.norm(axis)
    if norm < 1e-6:
        raise ValueError(f"Degenerate bond axis between atoms {j_idx} and {k_idx}")
    u = axis / norm

    # Determine which atoms to rotate (moving group downstream of k)
    if graph is not None:
        g_copy = graph.copy()
        if g_copy.has_edge(j_idx, k_idx):
            g_copy.remove_edge(j_idx, k_idx)
        # Find connected component containing k_idx
        moving_atoms = list(nx.node_connected_component(g_copy, k_idx))
    else:
        # Fallback: simple BFS from k avoiding j
        n_atoms = len(coords)
        visited = {j_idx}
        queue = [k_idx]
        moving_atoms = []
        while queue:
            curr = queue.pop(0)
            if curr not in visited:
                visited.add(curr)
                moving_atoms.append(curr)
                # Find spatial proximity neighbors
                for neighbor in range(n_atoms):
                    if (
                        neighbor not in visited
                        and np.linalg.norm(coords[neighbor] - coords[curr]) < 2.2
                    ):
                        queue.append(neighbor)

    theta_rad = math.radians(delta_angle_deg)
    cos_t = math.cos(theta_rad)
    sin_t = math.sin(theta_rad)

    # Rodrigues' rotation for each moving atom relative to pivot p_j
    for atom_idx in moving_atoms:
        r = coords[atom_idx] - p_j
        r_rot = r * cos_t + np.cross(u, r) * sin_t + u * np.dot(u, r) * (1.0 - cos_t)
        coords[atom_idx] = p_j + r_rot

    return coords


class RequestedPotentialUnavailableError(RuntimeError):
    """The selected scientific potential has no available evaluation receiver."""


def evaluate_pes_point(
    symbols: Sequence[str],
    coordinates: np.ndarray,
    model_wrapper: Optional[Any] = None,
) -> float:
    """Evaluate only the explicitly supplied potential, returning Hartree.

    An ASE calculator is an explicit model selection; its native eV result is
    converted once. A provider receiver must return a finite Hartree quantity
    with method and provenance. No unrequested force field substitutes for MACE.
    """
    coords = np.asarray(coordinates, dtype=np.float64)
    if coords.shape != (len(symbols), 3) or not np.all(np.isfinite(coords)):
        raise ValueError("Potential evaluation requires finite ordered N-by-3 coordinates")
    if model_wrapper is None:
        raise RequestedPotentialUnavailableError("A selected executable potential is required; no replacement model is authorized")
    from ase.calculators.calculator import BaseCalculator
    if isinstance(model_wrapper, BaseCalculator):
        from ase import Atoms
        from cochem_base.core.cochem_constants import HARTREE_TO_EV
        atoms = Atoms(symbols=list(symbols), positions=coords, calculator=model_wrapper)
        energy = float(atoms.get_potential_energy()) / HARTREE_TO_EV
    elif callable(getattr(model_wrapper, "evaluate", None)):
        result = model_wrapper.evaluate(symbols, coords)
        if not isinstance(result, dict) or not result.get("method") or not result.get("provenance") or "energy_hartree" not in result:
            raise RequestedPotentialUnavailableError("A provider must return energy_hartree, its actual method and provenance")
        energy = float(result["energy_hartree"])
    else:
        raise RequestedPotentialUnavailableError("The selected potential has no compatible scientific receiver")
    if not np.isfinite(energy):
        raise ValueError("The selected potential returned a nonfinite measured energy")
    return energy


def onnx_cpu_fallback(
    model_path: Optional[Union[str, Path]] = None,
    device_preference: str = "cuda",
) -> Dict[str, Any]:
    """
    Inspects hardware availability. If CUDA GPU VRAM is unavailable or exhausted,
    seamlessly routes execution to the ONNX CPU thread-pool with multi-threading.
    """
    has_cuda = False
    try:
        import torch

        has_cuda = torch.cuda.is_available() and torch.cuda.device_count() > 0
    except ImportError:
        has_cuda = False

    cpu_threads = max(1, os.cpu_count() or 1)

    if device_preference.lower() == "cuda" and has_cuda:
        selected_provider = "CUDAExecutionProvider"
        is_fallback = False
        device = "cuda:0"
        logger.info("MACE ONNX engine configured on GPU (%s)", device)
    else:
        selected_provider = "CPUExecutionProvider"
        is_fallback = device_preference.lower() == "cuda"
        device = "cpu"
        if is_fallback:
            logger.warning(
                "CUDA unavailable; executing onnx_cpu_fallback with %d threads", cpu_threads
            )
        else:
            logger.info("MACE ONNX engine configured on CPU (%d threads)", cpu_threads)

    return {
        "provider": selected_provider,
        "device": device,
        "threads": cpu_threads,
        "is_cpu_fallback": is_fallback,
        "model_path": str(model_path) if model_path else None,
    }


def generate_adaptive_grid(
    symbols: Sequence[str],
    coordinates: np.ndarray,
    dihedral_indices: Tuple[int, int, int, int],
    coarse_points: int = 12,
    gradient_threshold: float = 0.005,
    scan_range_deg: Tuple[float, float] = (0.0, 360.0),
    model_wrapper: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Performs initial coarse 1D scan, calculates numerical first derivatives (dE/dTheta),
    and dynamically tightens angular calculation density near transition states/steep regions.
    """
    graph = build_molecular_graph(symbols, coordinates)
    start_deg, end_deg = scan_range_deg
    coarse_angles = np.linspace(start_deg, end_deg, coarse_points, endpoint=False).tolist()

    evaluated_points: Dict[float, float] = {}

    # Step 1: Evaluate coarse grid
    for angle in coarse_angles:
        rot_coords = rotate_dihedral_angle(coordinates, dihedral_indices, angle, graph)
        energy = evaluate_pes_point(symbols, rot_coords, model_wrapper)
        evaluated_points[round(angle, 4)] = energy

    # Step 2: Compute numerical gradients and identify regions requiring refinement
    sorted_angles = sorted(evaluated_points.keys())
    refinement_angles: List[float] = []

    for idx in range(len(sorted_angles)):
        a1 = sorted_angles[idx]
        a2 = sorted_angles[(idx + 1) % len(sorted_angles)]
        e1 = evaluated_points[a1]
        e2 = evaluated_points[a2]

        delta_angle = (a2 - a1) % 360.0
        if delta_angle == 0:
            continue

        grad = abs(e2 - e1) / delta_angle  # Hartree per degree

        # If gradient exceeds threshold, inject intermediate sub-grid points
        if grad > gradient_threshold:
            mid1 = (a1 + delta_angle * 0.3333) % 360.0
            mid2 = (a1 + delta_angle * 0.6667) % 360.0
            refinement_angles.extend([round(mid1, 4), round(mid2, 4)])

    # Step 3: Evaluate refined points
    for angle in refinement_angles:
        if angle not in evaluated_points:
            rot_coords = rotate_dihedral_angle(coordinates, dihedral_indices, angle, graph)
            energy = evaluate_pes_point(symbols, rot_coords, model_wrapper)
            evaluated_points[angle] = energy

    # Final sorted points
    final_sorted_angles = sorted(evaluated_points.keys())
    final_energies = [evaluated_points[a] for a in final_sorted_angles]

    # Compute numerical gradients across final grid
    final_gradients: List[float] = []
    n_pts = len(final_sorted_angles)
    for idx in range(n_pts):
        prev_idx = (idx - 1) % n_pts
        next_idx = (idx + 1) % n_pts
        da = (final_sorted_angles[next_idx] - final_sorted_angles[prev_idx]) % 360.0
        if da == 0:
            da = 1.0
        de = final_energies[next_idx] - final_energies[prev_idx]
        final_gradients.append(de / da)

    logger.info(
        "Adaptive grid generated: %d coarse points -> %d total refined points (injected %d points)",
        len(coarse_angles),
        len(final_sorted_angles),
        len(refinement_angles),
    )

    return {
        "angles_deg": final_sorted_angles,
        "energies_hartree": final_energies,
        "gradients_hartree_per_deg": final_gradients,
        "coarse_point_count": len(coarse_angles),
        "adaptive_point_count": len(final_sorted_angles),
        "refinement_ratio": float(len(final_sorted_angles) / max(1, len(coarse_angles))),
        "dihedral_indices": dihedral_indices,
    }
