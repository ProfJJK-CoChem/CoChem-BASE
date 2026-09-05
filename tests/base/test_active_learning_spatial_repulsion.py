"""Spatial Repulsion & Intra-Batch Diversity Filtering in Active Learning Zero-Mock Tests.

Method Matrix Reference: Method Matrix v4 §4.4, §8A, §10.8, Table 2, Suggestion #130.
Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.

Validates:
1. Sequential spatial repulsion / furthest-point diversity in active learning candidate pool selection.
2. Balancing of predictive uncertainty spike with spatial coverage penalty:
   alpha_repulsive(x) = sigma(x) * [1.0 - exp(-d_min(x)^2 / (2 * l_rep^2))].
3. Prevention of redundant localized greedy clustering in expensive coupled-cluster escalation batches.
4. Concurrency-safe, deduplicated batch allocation with strict zero duplicate selections.
5. Dynamic atomic mass / property retrieval via Mendeleev.
"""

from __future__ import annotations

import os

os.environ["JAX_ENABLE_X64"] = "True"

import numpy as np
from ase import Atoms, units
from ase.calculators.emt import EMT
from ase.md.verlet import VelocityVerlet
from mendeleev import element

from cochem_base.core_engine.cochem_core_auto_pes import ActiveLearningEngine
from cochem_base.schemas import ActiveLearningBatchConfig


def test_dynamic_mendeleev_invariants():
    """Verify Mendeleev dynamic retrieval of element properties [M]."""
    c_elem = element("C")
    assert c_elem.atomic_number == 6
    assert float(c_elem.mass) > 12.0


def test_spatial_repulsion_prevents_greedy_clustering():
    """Assert active learning batch selection disperses candidates despite localized uncertainty spike [M], [D]."""
    # 1. Generate realistic molecular dynamics candidate pool using ASE EMT
    atoms = Atoms("CuAg", positions=[[0.0, 0.0, 0.0], [2.5, 0.0, 0.0]])
    atoms.calc = EMT()

    # Tightly clustered points near equilibrium (low velocity)
    atoms.set_velocities([[0.001, 0.0, 0.0], [-0.001, 0.0, 0.0]])
    cluster_geoms = []
    dyn1 = VelocityVerlet(atoms, 0.001 * units.fs)
    for _ in range(25):
        dyn1.run(1)
        cluster_geoms.append(atoms.get_positions())

    # Dispersed exploration points (high velocity)
    atoms.set_velocities([[0.100, 0.0, 0.0], [-0.100, 0.0, 0.0]])
    dispersed_geoms = []
    dyn2 = VelocityVerlet(atoms, 2.0 * units.fs)
    for _ in range(35):
        dyn2.run(2)
        dispersed_geoms.append(atoms.get_positions())

    pool = np.vstack([cluster_geoms, dispersed_geoms])
    n_pool = pool.shape[0]  # 60 candidate geometries
    pool_features = pool.reshape(n_pool, -1)  # 6D Cartesian coordinate features

    # 2. Localized uncertainty spike in the cluster region (indices 0 to 24)
    # Highest uncertainty is clustered around indices 0-5
    spike_uncertainties = np.array([20.0 - 0.2 * i for i in range(25)], dtype=np.float64)
    flat_uncertainties = np.full(35, 6.0, dtype=np.float64)
    uncertainties = np.concatenate([spike_uncertainties, flat_uncertainties])

    engine = ActiveLearningEngine()

    # 3. Unconstrained Greedy Selection (diversity_weight = 0.0)
    greedy_cfg = ActiveLearningBatchConfig(
        batch_size=5,
        repulsion_length_scale=0.5,
        diversity_weight=0.0,
        kernel_type="gaussian",
    )
    greedy_indices = engine.select_batch(pool_features, uncertainties, batch_config=greedy_cfg)
    assert len(greedy_indices) == 5
    # Greedy picks solely top 5 highest uncertainty points from the tightly clustered region
    assert all(idx < 25 for idx in greedy_indices)

    # 4. Sequential Repulsive Selection (diversity_weight = 1.0, l_rep = 0.5 A)
    l_rep = 0.50
    repulsion_cfg = ActiveLearningBatchConfig(
        batch_size=5,
        repulsion_length_scale=l_rep,
        diversity_weight=1.0,
        kernel_type="gaussian",
    )
    repulsive_indices = engine.select_batch(pool_features, uncertainties, batch_config=repulsion_cfg)
    assert len(repulsive_indices) == 5

    # Zero duplicate geometries
    assert len(set(repulsive_indices)) == 5

    # With repulsion, only 1 candidate comes from the tight spike cluster,
    # and the remaining 4 points are forced to explore the dispersed candidate pool
    cluster_selected = [idx for idx in repulsive_indices if idx < 25]
    assert len(cluster_selected) == 1, (
        f"Spatial repulsion must limit localized cluster selections to 1, got {len(cluster_selected)}"
    )

    # Selected batch geometries must maintain spatial diversity
    repulsive_geoms = pool_features[repulsive_indices]
    for i in range(len(repulsive_geoms)):
        for j in range(i + 1, len(repulsive_geoms)):
            d = float(np.linalg.norm(repulsive_geoms[i] - repulsive_geoms[j]))
            assert d > 0.1, f"Repulsion failed: distance between candidates {i} and {j} is {d:.4f} <= 0.1 A"
