import os
os.environ["JAX_ENABLE_X64"] = "True"

import numpy as np
import pytest
from mendeleev import element

from cochem_base.core_engine.cochem_core_auto_pes import ActiveLearningEngine
from cochem_base.schemas import ActiveLearningBatchConfig


def test_active_learning_sequential_repulsion_batch_diversity():
    """Verify sequential furthest-point repulsion prevents localized greedy clustering (Suggestion #51 / Method Matrix v4 §10.8 [M], [D])."""
    # Dynamic Mendeleev check
    c_elem = element("C")
    assert c_elem.atomic_number == 6

    from ase import Atoms
    from ase.calculators.emt import EMT
    from ase.md.verlet import VelocityVerlet
    from ase import units

    # Construct physical candidate pool: 20 cluster points near origin, 30 dispersed points
    atoms = Atoms("CuAg", positions=[[0,0,0], [2.5,0,0]])
    atoms.calc = EMT()

    # Cluster points: low velocity, small timestep
    atoms.set_velocities([[0.001, 0, 0], [-0.001, 0, 0]])
    cluster_geoms = []
    dyn1 = VelocityVerlet(atoms, 0.001 * units.fs)
    for _ in range(20):
        dyn1.run(1)
        cluster_geoms.append(atoms.get_positions())
    
    # Dispersed points: high velocity, large timestep
    atoms.set_velocities([[0.1, 0, 0], [-0.1, 0, 0]])
    dispersed_geoms = []
    dyn2 = VelocityVerlet(atoms, 2.0 * units.fs)
    for _ in range(30):
        dyn2.run(2)
        dispersed_geoms.append(atoms.get_positions())

    pool = np.vstack([cluster_geoms, dispersed_geoms])
    pool = pool.reshape(50, -1)  # 6D feature vector from coordinates
    
    # High uncertainties in cluster: 10.0 down to 8.1
    cluster_uncertainties = np.array([10.0 - 0.1 * i for i in range(20)], dtype=np.float64)
    # Dispersed uncertainties: flat
    dispersed_uncertainties = np.full(30, 5.0, dtype=np.float64)
    uncertainties = np.concatenate([cluster_uncertainties, dispersed_uncertainties])

    engine = ActiveLearningEngine()

    # 1. Greedy Selection (diversity_weight = 0.0) [D]
    greedy_cfg = ActiveLearningBatchConfig(
        batch_size=5,
        repulsion_length_scale=0.5,
        diversity_weight=0.0,
        kernel_type="gaussian",
    )
    greedy_indices = engine.select_batch(pool, uncertainties, batch_config=greedy_cfg)
    assert len(greedy_indices) == 5

    # In greedy selection, all 5 points must come from the top uncertainty cluster (indices < 20)
    assert all(idx < 20 for idx in greedy_indices)
    greedy_selected = pool[greedy_indices]
    for i in range(len(greedy_selected)):
        for j in range(i + 1, len(greedy_selected)):
            dist = np.linalg.norm(greedy_selected[i] - greedy_selected[j])
            assert dist < 0.1, f"Greedy selection points unexpectedly dispersed: dist={dist}"

    # 2. Repulsion Selection (diversity_weight = 1.0, sigma_repulse = 0.5 A) [M]
    repulsion_cfg = ActiveLearningBatchConfig(
        batch_size=5,
        repulsion_length_scale=0.5,
        diversity_weight=1.0,
        kernel_type="gaussian",
    )
    repulsion_indices = engine.select_batch(pool, uncertainties, batch_config=repulsion_cfg)
    assert len(repulsion_indices) == 5

    # With repulsion, only 1 point is taken from the cluster, and remaining points come from dispersed region
    cluster_count = sum(1 for idx in repulsion_indices if idx < 20)
    assert cluster_count == 1, f"Repulsion should take at most 1 point from cluster, got {cluster_count}"

    repulsion_selected = pool[repulsion_indices]
    for i in range(len(repulsion_selected)):
        for j in range(i + 1, len(repulsion_selected)):
            dist = np.linalg.norm(repulsion_selected[i] - repulsion_selected[j])
            assert dist > 0.1, f"Repulsion failed to disperse points: dist={dist} <= 0.1"
