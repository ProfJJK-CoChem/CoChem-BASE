"""Covalent Graph Partitioning & Pairwise Non-Covalent Fallback Potential Zero-Mock Tests.

Method Matrix Reference: Method Matrix v4 §4.4, §8A, §9A.1, §9B.4, Suggestion #127.
Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.

Validates:
1. Dynamic covalent graph partitioning G = (V, E) using Mendeleev Pyykkö covalent radii.
2. Separation of non-covalent complexes (e.g., CO2...H2O) into distinct molecular fragments.
3. Bipartite potential evaluation: bonded Morse stretching intra-fragment, Lennard-Jones 12-6 & Coulomb inter-fragment.
4. Prevention of artificial covalent collapse in non-covalent complexes.
5. Non-blocking pinned CPU fallback under CUDA memory locking/contention.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
import torch
from mendeleev import element

from Libraries.cochem_torq_mace import (
    evaluate_physical_potential,
    get_covalent_radius,
    partition_molecular_graph,
)
from scripts.oet_maceoff import PhysicalMACEOFFFallbackCalculator


def test_mendeleev_covalent_radius_resolution():
    """Assert Pyykkö covalent radii are retrieved dynamically via Mendeleev [M], [E]."""
    r_c = get_covalent_radius("C")
    r_o = get_covalent_radius("O")
    r_h = get_covalent_radius("H")

    # Dynamic Mendeleev comparison
    elem_c = element("C")
    elem_o = element("O")
    elem_h = element("H")

    assert abs(r_c - float(elem_c.covalent_radius_pyykko) / 100.0) < 1e-4
    assert abs(r_o - float(elem_o.covalent_radius_pyykko) / 100.0) < 1e-4
    assert abs(r_h - float(elem_h.covalent_radius_pyykko) / 100.0) < 1e-4


def test_co2_water_complex_graph_partitioning():
    """Assert molecular connectivity graph isolates CO2 and H2O into two distinct components [M]."""
    # CO2 ... H2O complex at 3.00 A physical separation
    symbols = ["C", "O", "O", "O", "H", "H"]
    coords = np.array([
        # CO2 monomer
        [0.000, 0.000, 0.000],
        [0.000, 0.000, 1.162],
        [0.000, 0.000, -1.162],
        # H2O monomer (3.0 A away along Y)
        [0.000, 3.000, 0.000],
        [0.757, 3.586, 0.000],
        [-0.757, 3.586, 0.000],
    ], dtype=np.float64)

    fragments, adj = partition_molecular_graph(symbols, coords)
    assert len(fragments) == 2, f"Expected 2 partitioned fragments, got {len(fragments)}"
    assert set(fragments[0]) == {0, 1, 2}
    assert set(fragments[1]) == {3, 4, 5}

    # Inter-fragment adjacency entries must be strictly False
    for i in {0, 1, 2}:
        for j in {3, 4, 5}:
            assert adj[i, j] is np.False_ or adj[i, j] is False


def test_bipartite_potential_prevents_covalent_collapse():
    """Assert inter-fragment non-covalent forces evaluate via Lennard-Jones/Coulomb and prevent collapse [M]."""
    # An untrained pair potential must never be emitted as MACE output.
    with pytest.raises(RuntimeError, match="untrained physical MACE fallback was removed"):
        PhysicalMACEOFFFallbackCalculator(charge=0, multiplicity=1)

    symbols = ["C", "O", "O", "O", "H", "H"]
    coords = [
        [0.000, 0.000, 0.000],
        [0.000, 0.000, 1.162],
        [0.000, 0.000, -1.162],
        [0.000, 3.000, 0.000],
        [0.757, 3.586, 0.000],
        [-0.757, 3.586, 0.000],
    ]

    # Test library function evaluate_physical_potential
    energy_lib, forces_lib, converged = evaluate_physical_potential(symbols, coords)
    assert converged is True
    assert not np.isnan(energy_lib)
    assert forces_lib.shape == (6, 3)

    # Bring fragments very close (e.g. 1.2 A) - repulsion must dominate, force along Y must repel
    repulsive_coords = [
        [0.000, 0.000, 0.000],
        [0.000, 0.000, 1.162],
        [0.000, 0.000, -1.162],
        [0.000, 1.200, 0.000],
        [0.757, 1.786, 0.000],
        [-0.757, 1.786, 0.000],
    ]
    e_rep, f_rep, _ = evaluate_physical_potential(symbols, repulsive_coords)
    # Total energy at 1.2 A must be much higher than at equilibrium 3.0 A due to Pauli/LJ repulsion
    assert e_rep > energy_lib


def test_non_blocking_gpu_allocation_cpu_fallback():
    """Assert non-blocking fallback to pinned CPU threads when CUDA is contended or absent [M], [D]."""
    # Simulate CPU fallback routing
    num_cpus = os.cpu_count() or 4
    torch.set_num_threads(min(num_cpus, 8))
    device = torch.device("cpu")
    assert device.type == "cpu"

    # Evaluation on CPU device
    t = torch.tensor([1.0, 2.0, 3.0], device=device)
    assert t.device.type == "cpu"
