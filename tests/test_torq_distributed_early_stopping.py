"""Authentic physical verification test suite for Multi-GPU Distributed Early Stopping (REQ-TORQ-TRAIN-094).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic multi-process DDP session with Gloo backend.
"""

from __future__ import annotations

import pytest
import torch
import torch.multiprocessing as mp

from Libraries.cochem_torq_distributed_early_stopping import (
    DistributedEarlyStopping,
    distributed_worker_routine,
    find_free_port,
)
from Libraries.cochem_torq_training_schemas import DistributedEarlyStoppingConfig


def test_single_process_early_stopping_logic() -> None:
    """Verify single-process baseline early stopping and patience counter mechanics. [D]"""
    config = DistributedEarlyStoppingConfig(
        patience_epochs=3,
        min_delta_hartree=0.01,
        synchronize_ranks=True,
    )
    stopper = DistributedEarlyStopping(config)

    # Epoch 0: initial loss 1.0 -> best loss 1.0
    stop0, l0 = stopper.step(local_loss_sum=10.0, local_count=10, rank=0, world_size=1)
    assert not stop0
    assert l0 == 1.0
    assert stopper.counter == 0
    assert stopper.best_loss == 1.0

    # Epoch 1: improvement to 0.95 (> min_delta 0.01) -> best loss 0.95
    stop1, l1 = stopper.step(local_loss_sum=9.5, local_count=10, rank=0, world_size=1)
    assert not stop1
    assert stopper.counter == 0
    assert stopper.best_loss == 0.95

    # Epoch 2: negligible improvement to 0.945 (< min_delta 0.01) -> patience counter 1
    stop2, l2 = stopper.step(local_loss_sum=9.45, local_count=10, rank=0, world_size=1)
    assert not stop2
    assert stopper.counter == 1

    # Epoch 3: plateau -> patience counter 2
    stop3, l3 = stopper.step(local_loss_sum=9.45, local_count=10, rank=0, world_size=1)
    assert not stop3
    assert stopper.counter == 2

    # Epoch 4: plateau reached patience 3 -> triggers early stop
    stop4, l4 = stopper.step(local_loss_sum=9.45, local_count=10, rank=0, world_size=1)
    assert stop4
    assert stopper.early_stop is True


def test_distributed_count_weighted_reduction_and_synchronous_stop() -> None:
    """Launch authentic 2-process DDP session and verify count-weighted metric reduction and synchronous exit. [M]"""
    port = find_free_port()
    manager = mp.Manager()
    results = manager.dict()

    # Asymmetric shard sizes:
    # Rank 0: N_0 = 20 samples, Loss sum = 10.0 (Local mean = 0.50)
    # Rank 1: N_1 = 10 samples, Loss sum = 2.0  (Local mean = 0.20)
    # Exact count-weighted global mean: (10.0 + 2.0) / (20 + 10) = 12.0 / 30 = 0.40
    # Epoch 0: global mean = 0.40 (best_loss = 0.40)
    # Epoch 1: global mean = 0.40 (plateau, counter = 1)
    # Epoch 2: global mean = 0.40 (plateau, counter = 2 -> triggers early stop)
    shard_data = {
        0: [(10.0, 20), (10.0, 20), (10.0, 20), (10.0, 20)],
        1: [(2.0, 10), (2.0, 10), (2.0, 10), (2.0, 10)],
    }

    config_dict = {
        "patience_epochs": 2,
        "min_delta_hartree": 1e-4,
        "synchronize_ranks": True,
    }

    mp.spawn(
        distributed_worker_routine,
        args=(2, port, shard_data, config_dict, results),
        nprocs=2,
        join=True,
    )

    assert 0 in results
    assert 1 in results

    # Verify count-weighted reduction was calculated correctly on both ranks
    assert pytest.approx(results[0]["recorded_losses"][0], rel=1e-5) == 0.40
    assert pytest.approx(results[1]["recorded_losses"][0], rel=1e-5) == 0.40

    # Verify synchronous deadlock-free termination at identical epoch
    assert results[0]["stopped_epoch"] == 2
    assert results[1]["stopped_epoch"] == 2
    assert results[0]["stopped_epoch"] == results[1]["stopped_epoch"]
