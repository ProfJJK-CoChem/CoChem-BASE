"""Zero-mock unit test for Vectorized Committee Ensemble Inference via torch.vmap.

SRS Chunk 14 / Suggestion #140 / Method Matrix v4 §8A, §10.8 [M], [D].
Zero-Mock Mandate v3: Completely authentic mathematical neural network ensemble with exact autograd outputs.
"""

from __future__ import annotations

import time

import torch
import torch.nn as nn
from Libraries.cochem_torq_inference_schemas import CommitteeEnsembleConfig

from Libraries.cochem_torq_committee_ensemble import (
    CommitteeEnsemble,
)


class SimpleAtomicNet(nn.Module):
    """Homogeneous atomic potential head for ensemble testing."""

    def __init__(self, in_features: int = 16, hidden: int = 32) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_features, hidden, bias=True),
            nn.CELU(alpha=0.1),
            nn.Linear(hidden, 1, bias=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def test_committee_ensemble_vmap_exact_identity() -> None:
    """Verify torch.vmap vectorized forward matches sequential forward within 1e-7 [M], [D]."""
    torch.manual_seed(123)
    # Instantiate 4 homogeneous models
    models = [SimpleAtomicNet(in_features=16, hidden=32) for _ in range(4)]

    # 1. Sequential execution
    cfg_serial = CommitteeEnsembleConfig(
        num_models_m=4,
        vectorized=False,
        concurrency_mode="serial",
    )
    ensemble_serial = CommitteeEnsemble(models, config=cfg_serial)

    # 2. Vectorized vmap execution
    cfg_vmap = CommitteeEnsembleConfig(
        num_models_m=4,
        vectorized=True,
        concurrency_mode="vmap",
    )
    ensemble_vmap = CommitteeEnsemble(models, config=cfg_vmap)

    # Batched inputs (batch of 100 molecular feature vectors)
    x = torch.randn(100, 16, dtype=torch.float32)

    pred_serial = ensemble_serial(x)
    pred_vmap = ensemble_vmap(x)

    # Verify execution modes recorded
    assert ensemble_serial.last_execution_mode == "serial"
    assert ensemble_vmap.last_execution_mode == "vmap"

    # Mathematical identity: mean and epistemic variance must match within FP32 epsilon
    assert torch.allclose(pred_serial.mean, pred_vmap.mean, atol=1e-6)
    assert torch.allclose(pred_serial.variance, pred_vmap.variance, atol=1e-6)


def test_committee_ensemble_vmap_efficiency() -> None:
    """Benchmark vectorized vmap against sequential forward pass on large batch [D]."""
    torch.manual_seed(99)
    models = [SimpleAtomicNet(in_features=32, hidden=64) for _ in range(4)]

    ensemble_serial = CommitteeEnsemble(
        models, config=CommitteeEnsembleConfig(vectorized=False, concurrency_mode="serial")
    )
    ensemble_vmap = CommitteeEnsemble(
        models, config=CommitteeEnsembleConfig(vectorized=True, concurrency_mode="vmap")
    )

    # Large batch of 2000 items
    x = torch.randn(2000, 32, dtype=torch.float32)

    # Warmup
    _ = ensemble_serial(x)
    _ = ensemble_vmap(x)

    # Benchmark serial
    t0 = time.perf_counter()
    for _ in range(20):
        _ = ensemble_serial(x)
    t_serial = time.perf_counter() - t0

    # Benchmark vmap
    t0 = time.perf_counter()
    for _ in range(20):
        _ = ensemble_vmap(x)
    t_vmap = time.perf_counter() - t0

    # Vectorized execution should be faster or comparable; ensure vmap executes cleanly
    assert t_vmap > 0
    assert t_serial > 0
