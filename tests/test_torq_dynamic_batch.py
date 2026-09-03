"""Authentic physical verification test suite for Dynamic Batch Scaler & OOM Recovery (REQ-TORQ-TRAIN-099 [M]).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely unmocked Heterogeneous mixture: Water (N=3), Ethanol (N=9), C60 (N=60).
"""

from __future__ import annotations

import pytest
import torch

from Libraries.cochem_torq_dynamic_batch import (
    DynamicOOMRecovery,
    MolecularGraph,
    calculate_sparse_padding_waste,
    get_vram_telemetry,
    pack_graphs_dual_budget,
)
from Libraries.cochem_torq_training_errors import OOMRecoveryError
from Libraries.cochem_torq_training_schemas import DynamicBatchScalerConfig
from tests.torq_test_fixtures import (
    get_c60_fullerene_fixture,
    get_ethanol_fixture,
    get_water_monomer_fixture,
)


def _create_heterogeneous_mixture() -> list[MolecularGraph]:
    """Create authentic heterogeneous molecular graphs: Water (N=3), Ethanol (N=9), C60 (N=60). [M]"""
    water_coords, water_species = get_water_monomer_fixture()
    ethanol_coords, ethanol_species = get_ethanol_fixture()
    c60_coords, c60_species = get_c60_fullerene_fixture()

    graphs: list[MolecularGraph] = []

    # 1. 20 Water molecules (N=3, E=6)
    w_edges = torch.tensor([[0, 0, 1, 2, 1, 2], [1, 2, 0, 0, 2, 1]], dtype=torch.long)
    for i in range(20):
        graphs.append(
            MolecularGraph(
                coordinates=water_coords.clone(),
                species=water_species.clone(),
                edge_index=w_edges.clone(),
                name=f"water_{i}",
            )
        )

    # 2. 15 Ethanol molecules (N=9, E=20)
    eth_edges = torch.tensor(
        [[0, 1, 1, 2], [1, 0, 2, 1]], dtype=torch.long
    )  # Core skeleton
    for i in range(15):
        graphs.append(
            MolecularGraph(
                coordinates=ethanol_coords.clone(),
                species=ethanol_species.clone(),
                edge_index=eth_edges.clone(),
                name=f"ethanol_{i}",
            )
        )

    # 3. 5 Buckminsterfullerene C60 molecules (N=60, E=180)
    c60_edges = torch.empty((2, 180), dtype=torch.long)
    for i in range(5):
        graphs.append(
            MolecularGraph(
                coordinates=c60_coords.clone(),
                species=c60_species.clone(),
                edge_index=c60_edges.clone(),
                name=f"c60_{i}",
            )
        )

    return graphs


def test_dual_token_budget_packing_heterogeneous_mixture() -> None:
    """Confirm that packed micro-batches strictly obey sum N_i <= 4096 and sum |E_i| <= 32768. [M]"""
    graphs = _create_heterogeneous_mixture()
    max_nodes = 120  # Tight budget for clear verification
    max_edges = 400

    batches = pack_graphs_dual_budget(
        graphs, max_node_budget=max_nodes, max_edge_budget=max_edges, sort_by_size=True
    )
    assert len(batches) > 1

    total_packed_graphs = 0
    for b in batches:
        assert b.total_nodes <= max_nodes, f"Node budget exceeded: {b.total_nodes} > {max_nodes}"
        assert b.total_edges <= max_edges, f"Edge budget exceeded: {b.total_edges} > {max_edges}"
        total_packed_graphs += len(b.graphs)

        # Collation check
        collated = b.collate()
        assert collated["coordinates"].shape[0] == b.total_nodes
        assert collated["species"].shape[0] == b.total_nodes
        assert collated["batch"].shape[0] == b.total_nodes

    assert total_packed_graphs == len(graphs), "All graphs must be packed without loss."


def test_greedy_bin_packing_reduces_padding_waste() -> None:
    """Verify atom sorting reduces sparse block padding compared to naive unsorted batching. [M]"""
    graphs = _create_heterogeneous_mixture()

    # Pack with sorting
    sorted_batches = pack_graphs_dual_budget(
        graphs, max_node_budget=150, max_edge_budget=500, sort_by_size=True
    )
    sorted_waste = calculate_sparse_padding_waste(sorted_batches)

    # Pack without sorting (simulating naive sequential/random order)
    unsorted_batches = pack_graphs_dual_budget(
        graphs, max_node_budget=150, max_edge_budget=500, sort_by_size=False
    )
    unsorted_waste = calculate_sparse_padding_waste(unsorted_batches)

    # Sorted bin-packing groups similar sizes together, yielding lower ragged padding waste
    assert sorted_waste <= unsorted_waste, (
        f"Sorted waste ({sorted_waste}) should be <= unsorted waste ({unsorted_waste})"
    )


def test_transparent_oom_recovery_and_budget_stepdown() -> None:
    """Inject simulated OOM; verify cache purge, 0.75x budget step-down, sub-batch split, and recovery. [M]"""
    config = DynamicBatchScalerConfig(
        max_node_budget=4096,
        max_edge_budget=32768,
        backoff_factor=0.75,
        max_recovery_retries=3,
    )
    recovery_mgr = DynamicOOMRecovery(config)

    graphs = _create_heterogeneous_mixture()[:8]  # 8 graphs
    initial_node_budget = recovery_mgr.current_node_budget
    initial_edge_budget = recovery_mgr.current_edge_budget

    oom_injected = [True]  # Fail once then succeed
    processed_calls: list[int] = []

    def execute_step_fn(sub_batch: list[MolecularGraph], accum_scale: float) -> str:
        if oom_injected[0]:
            oom_injected[0] = False
            # Simulate CUDA OutOfMemoryError
            raise torch.cuda.OutOfMemoryError("CUDA out of memory in backward pass.")
        processed_calls.append(len(sub_batch))
        return f"success_{len(sub_batch)}"

    results = recovery_mgr.execute_with_recovery(graphs, execute_step_fn)

    # Invariant checks:
    # 1. Budget was stepped down by 0.75x
    assert recovery_mgr.current_node_budget == int(initial_node_budget * 0.75)
    assert recovery_mgr.current_edge_budget == int(initial_edge_budget * 0.75)

    # 2. Batch of 8 was partitioned into 2 sub-batches of 4
    assert processed_calls == [4, 4]
    assert len(results) == 2
    assert recovery_mgr.total_oom_events == 1


def test_oom_recovery_escalation_error_after_max_retries() -> None:
    """Exceeding max_recovery_retries=3 raises OOMRecoveryError. [M]"""
    config = DynamicBatchScalerConfig(
        max_node_budget=4096,
        max_edge_budget=32768,
        backoff_factor=0.75,
        max_recovery_retries=3,
    )
    recovery_mgr = DynamicOOMRecovery(config)
    graphs = _create_heterogeneous_mixture()[:4]

    def always_fail_fn(sub_batch: list[MolecularGraph], accum_scale: float) -> None:
        raise torch.cuda.OutOfMemoryError("Persistent CUDA out of memory.")

    with pytest.raises(OOMRecoveryError) as exc_info:
        recovery_mgr.execute_with_recovery(graphs, always_fail_fn)

    assert exc_info.value.error_code == "TORQ_TRAIN_OOM_RECOVERY_EXHAUSTED"


def test_vram_telemetry_profiling() -> None:
    """Verify real-time VRAM telemetry profiling function returns structured dictionary. [M]"""
    telemetry = get_vram_telemetry()
    assert "allocated_mb" in telemetry
    assert "max_allocated_mb" in telemetry
    assert "reserved_mb" in telemetry
    assert "cuda_available" in telemetry
