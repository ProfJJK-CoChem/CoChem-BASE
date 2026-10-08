"""
CoChem-BASE Geometry Suite: Fragment Partitioner & Frozen-Monomer Constraints.
Validating Suggestion #40 (Chunk 4).

Method Matrix v4 Compliance:
- §9A.1-§9A.2 Recipe R1 & R2: Intermolecular complexes must freeze monomer internal coordinates.
- §4.4 & QS-1: Enforce tightened 5-threshold %geom block:
  TolMaxG 1e-5, TolRMSG 3e-6, TolMaxD 1e-4, TolRMSD 5e-5, TolE 1e-7.
- Model Hessians: InHess XTB2 or Lindh.
- Strict prohibition (§8B.3 & §9A.5): Calc_Hess true is strictly forbidden and raises MethodologyViolationError.
- Dynamic Mendeleev Covalent Radii: Retrieved via mendeleev.element.
"""

from __future__ import annotations

import collections
import functools
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import numpy as np
from cochem_base.physics.nuclide_resolver import get_element

from cochem_base.exceptions import MethodologyViolationError


@functools.lru_cache(maxsize=128)
def get_covalent_radius_angstrom(symbol_or_atomic_number: Union[str, int]) -> float:
    """Retrieves covalent radius in Angstroms dynamically via mendeleev. [M]"""
    el = get_element(symbol_or_atomic_number)
    # mendeleev reports covalent_radius in picometers (pm), convert to Angstroms
    r_pm = el.covalent_radius_pyykko or el.covalent_radius
    if r_pm is None:
        raise ValueError(f"No covalent radius available for {symbol_or_atomic_number}.")
    return float(r_pm) / 100.0


def detect_molecular_fragments(
    atomic_numbers_or_symbols: Sequence[Union[int, str]],
    coordinates_angstrom: Union[np.ndarray, Sequence[Sequence[float]]],
    cov_scale: float = 1.25,
) -> List[List[int]]:
    """Partitions a molecular system into discrete fragments using covalent connectivity graph. [M]

    Args:
        atomic_numbers_or_symbols: Atomic numbers or element symbols for all atoms.
        coordinates_angstrom: Cartesian coordinates in Angstroms (N x 3).
        cov_scale: Multiplier on the sum of covalent radii to define bonding threshold (default 1.25).

    Returns:
        List of lists, where each sublist contains the atom indices belonging to a discrete fragment.
    """
    coords = np.array(coordinates_angstrom, dtype=np.float64)
    n_atoms = len(atomic_numbers_or_symbols)
    if n_atoms == 0 or coords.shape != (n_atoms, 3) or not np.all(np.isfinite(coords)):
        raise ValueError(f"Coordinate shape {coords.shape} does not match atom count {n_atoms}")
    if not math.isfinite(cov_scale) or cov_scale <= 0:
        raise ValueError("Covalent-radius scale must be finite and positive.")

    radii = [get_covalent_radius_angstrom(s) for s in atomic_numbers_or_symbols]

    # Build adjacency graph
    adj: Dict[int, List[int]] = collections.defaultdict(list)
    for i in range(n_atoms):
        for j in range(i + 1, n_atoms):
            diff = coords[i] - coords[j]
            dist = float(math.sqrt(diff[0]**2 + diff[1]**2 + diff[2]**2))
            bond_cutoff = cov_scale * (radii[i] + radii[j])
            if dist <= bond_cutoff:
                adj[i].append(j)
                adj[j].append(i)

    # Find connected components via BFS
    visited: Set[int] = set()
    fragments: List[List[int]] = []

    for start_node in range(n_atoms):
        if start_node in visited:
            continue
        comp: List[int] = []
        queue = collections.deque([start_node])
        visited.add(start_node)

        while queue:
            node = queue.popleft()
            comp.append(node)
            for neighbor in adj[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        fragments.append(sorted(comp))

    return fragments


def validate_no_calc_hess(deck_content: str) -> None:
    """Scans deck content and raises MethodologyViolationError if 'Calc_Hess true' is detected. [M]"""
    if not deck_content:
        return
    uncommented = "\n".join(line.split("#", 1)[0] for line in deck_content.splitlines())
    if re.search(r"(?i)\bcalc_?hess\s+(?:true|1)\b", uncommented):
        raise MethodologyViolationError(
            "Method Matrix §8B.3 & §9A.5 Violation: 'Calc_Hess true' is strictly prohibited for geometry optimizations. "
            "Calculating exact initial Hessians wastes excessive computational wall time. "
            "Remediation: use model Hessians 'InHess XTB2' or 'Lindh'."
        )


def generate_frozen_monomer_orca_block(
    fragments: Sequence[Sequence[int]],
    symbols: Optional[Sequence[Union[int, str]]] = None,
    coordinates_angstrom: Optional[Union[np.ndarray, Sequence[Sequence[float]]]] = None,
    initial_hessian: str = "XTB2",
    input_deck_to_validate: Optional[str] = None,
    freeze_all_monomers: bool = True,
    coordinates: Optional[Union[np.ndarray, Sequence[Sequence[float]]]] = None,
) -> str:
    """Synthesizes ORCA %geom Constraints block freezing monomer internal coordinates. [M]

    Enforces Method Matrix v4 §4.4 tightened convergence thresholds:
    TolMaxG 1e-5, TolRMSG 3e-6, TolMaxD 1e-4, TolRMSD 5e-5, TolE 1e-7, and InHess XTB2.
    Strictly raises MethodologyViolationError if 'Calc_Hess true' is detected anywhere.
    """
    if coordinates_angstrom is None and coordinates is not None:
        coordinates_angstrom = coordinates
    # 1. Method Matrix §8B.3 & §9A.5 Audit: Prohibition of Calc_Hess true
    if input_deck_to_validate:
        validate_no_calc_hess(input_deck_to_validate)
    if initial_hessian not in ("XTB2", "Lindh"):
        raise MethodologyViolationError("Initial Hessian must be XTB2 or Lindh; use the input generator for READ checkpoints.")
    if symbols is None or coordinates_angstrom is None:
        raise ValueError("Atomic symbols and coordinates are required; monomer topology cannot be inferred from indices.")
    coords = np.asarray(coordinates_angstrom, dtype=float)
    if coords.shape != (len(symbols), 3) or not np.all(np.isfinite(coords)):
        raise ValueError("Monomer coordinates must be finite and match the symbols.")
    all_indices = [i for fragment in fragments for i in fragment]
    if not fragments or any(not fragment for fragment in fragments) or len(set(all_indices)) != len(all_indices) or any(
        isinstance(i, bool) or not isinstance(i, (int, np.integer)) or i < 0 or i >= len(symbols) for i in all_indices
    ):
        raise ValueError("Monomer fragments must be nonempty, disjoint and contain valid atom indices.")
    if set(all_indices) != set(range(len(symbols))):
        raise MethodologyViolationError("Frozen-monomer fragments must cover every atom.")
    for fragment in fragments:
        if len(detect_molecular_fragments([symbols[i] for i in fragment], coords[list(fragment)], cov_scale=1.30)) != 1:
            raise MethodologyViolationError("Each monomer fragment must be covalently connected.")
    if not freeze_all_monomers:
        raise MethodologyViolationError("Frozen-monomer recipes require every monomer to be constrained.")

    constraints: List[str] = []

    # 2. Build internal constraints for each multi-atom monomer
    for frag in fragments:
        k = len(frag)
        if k < 2:
            continue

        if symbols is not None and coordinates_angstrom is not None:
            # Build bonded network within the monomer
            sub_coords = [coordinates_angstrom[idx] for idx in frag]
            sub_syms = [symbols[idx] for idx in frag]
            radii = [get_covalent_radius_angstrom(s) for s in sub_syms]

            monomer_bonds: List[Tuple[int, int]] = []
            for i_local in range(k):
                for j_local in range(i_local + 1, k):
                    i_glob, j_glob = frag[i_local], frag[j_local]
                    d = float(np.linalg.norm(np.array(sub_coords[i_local]) - np.array(sub_coords[j_local])))
                    if d <= 1.30 * (radii[i_local] + radii[j_local]):
                        monomer_bonds.append((min(i_glob, j_glob), max(i_glob, j_glob)))
                        constraints.append(f"      {{ B {min(i_glob, j_glob)} {max(i_glob, j_glob)} C }}")

            # Angles from adjacent bond pairs
            bond_map: Dict[int, List[int]] = collections.defaultdict(list)
            for a, b in monomer_bonds:
                bond_map[a].append(b)
                bond_map[b].append(a)

            for center, neighbors in bond_map.items():
                if len(neighbors) >= 2:
                    for i_idx in range(len(neighbors)):
                        for j_idx in range(i_idx + 1, len(neighbors)):
                            a1, a2 = neighbors[i_idx], neighbors[j_idx]
                            constraints.append(f"      {{ A {a1} {center} {a2} C }}")
            torsions = set()
            for j, k in monomer_bonds:
                for i in bond_map[j]:
                    for l in bond_map[k]:
                        if len({i, j, k, l}) == 4:
                            torsions.add(min((i, j, k, l), (l, k, j, i)))
            for i, j, k, l in sorted(torsions):
                constraints.append(f"      {{ D {i} {j} {k} {l} C }}")
    # 3. Assemble full tightened %geom block
    lines = [
        "%geom",
        "   TolMaxG 1e-5",
        "   TolRMSG 3e-6",
        "   TolMaxD 1e-4",
        "   TolRMSD 5e-5",
        "   TolE    1e-7",
        "   MaxIter 200",
        f"   InHess  {initial_hessian}",
        "   Constraints",
    ]
    lines.extend(constraints)
    lines.append("   end")
    lines.append("end")

    return "\n".join(lines) + "\n"
