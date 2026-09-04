"""Physical Zero-Mock Test for Graph-Partitioned Non-Covalent Fallback Potential.

Validates Suggestion #48:
- Dynamic Pyykkö covalent radii graph partitioning.
- Strict isolation of discrete molecular monomers in van der Waals complexes.
- Buffered Lennard-Jones and Coulomb potential evaluation across intermolecular pairs.
- Prevention of artificial covalent collapse in non-covalent dimers.
"""

import numpy as np
import pytest

from Libraries.cochem_torq_mace import partition_molecular_graph, evaluate_physical_potential


def test_maceoff_water_dimer_graph_partitioning():
    """Assert water dimer is partitioned into exactly two discrete monomers."""
    # Water dimer at equilibrium separation (R_O...O = 2.91 A)
    symbols = ["O", "H", "H", "O", "H", "H"]
    coords = np.array([
        [-1.464, -0.010, 0.000],   # O1
        [-0.505, -0.031, 0.000],   # H1 (donor)
        [-1.782, 0.892, 0.000],    # H2
        [1.442, 0.010, 0.000],     # O2 (acceptor)
        [1.798, -0.428, 0.762],    # H3
        [1.798, -0.428, -0.762],   # H4
    ], dtype=np.float64)

    # 1. Graph partitioning
    fragments, adj_matrix = partition_molecular_graph(symbols, coords)
    assert len(fragments) == 2, f"Expected 2 fragments for water dimer, got {len(fragments)}"

    frag_sets = [set(f) for f in fragments]
    assert {0, 1, 2} in frag_sets, "Monomer 1 atoms {0, 1, 2} not correctly grouped."
    assert {3, 4, 5} in frag_sets, "Monomer 2 atoms {3, 4, 5} not correctly grouped."

    # 2. Intermolecular bond adjacency must be False
    assert adj_matrix[0, 3] is np.False_ or adj_matrix[0, 3] == 0, "O1-O2 must not have covalent bond."
    assert adj_matrix[1, 3] is np.False_ or adj_matrix[1, 3] == 0, "H1-O2 hydrogen bond must not be covalent."

    # 3. Energy and forces evaluation
    energy_ev, forces, converged = evaluate_physical_potential(symbols, coords, use_pyscf=False)
    assert converged is True
    assert isinstance(energy_ev, float)
    assert forces.shape == (6, 3)

    # 4. Asymptotic separation vs Covalent collapse check
    # If the monomers were treated as covalently bonded, compressing them would encounter deep well;
    # with buffered LJ + Coulomb, compressing O...O below 2.0 A produces strong core repulsion.
    coords_compressed = np.copy(coords)
    coords_compressed[3:, 0] -= 1.4  # Compress O...O to ~ 1.5 A (severe clash)

    e_comp, f_comp, _ = evaluate_physical_potential(symbols, coords_compressed, use_pyscf=False)
    # Severe clash must produce higher potential energy than equilibrium
    assert e_comp > energy_ev, "Compressed dimer must have higher potential energy due to core repulsion."

    # Contacting donor atom H1 (atom 1) experiences severe repulsive push in -x direction (away from O2)
    # Net force on Monomer 1 must be in -x direction, and net force on Monomer 2 must be in +x direction
    assert f_comp[1, 0] < 0.0, "Core repulsion must push donor H1 away in -x direction."
    assert f_comp[:3, 0].sum() < 0.0, "Net force on Monomer 1 must push monomer away in -x direction."
    assert f_comp[3:, 0].sum() > 0.0, "Net force on Monomer 2 must push monomer away in +x direction."
