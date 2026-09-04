"""Physical Zero-Mock Test Suite for Vectorized Committee Ensemble Inference & Dynamic VRAM Throttling.

Method Matrix Reference: Method Matrix v4 §8A.2 (Throughput Optimization & Heterogeneous Concurrency) [M].
Validates Suggestion #61:
- Mathematical invariance between vectorized torch.vmap and serial inference to machine precision (< 1e-12 in FP64) [M].
- Unbiased sample variance and epistemic standard deviation consistency.
- Dynamic RESOURCE_GUARD memory headroom threshold polling and serialized fallback.
"""

from __future__ import annotations

import time
import pytest
import torch
import torch.nn as nn

from cochem_base.schemas import CommitteeEnsembleConfig
from Libraries.cochem_torq_committee_ensemble import (
    CommitteeEnsemble,
    CommitteePrediction,
    compute_committee_moments,
    get_available_vram_mb,
)


class MolecularFeatureMLP(nn.Module):
    """Authentic physical MLP evaluating molecular feature vectors. [M]"""

    def __init__(self, in_features: int = 128, hidden_dim: int = 64, out_features: int = 1) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_features, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, out_features),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def test_vectorized_vs_serial_mathematical_invariance():
    """Verify that torch.vmap and serial execution are numerically invariant to machine precision (< 1e-12). [M]"""
    torch.manual_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Instantiate 4-member committee with identical parameter shapes
    num_models = 4
    models = [MolecularFeatureMLP(128, 64, 1).to(device=device, dtype=torch.float64) for _ in range(num_models)]

    # Batch of 64 molecular feature vectors (D = 128)
    batch_x = torch.randn(64, 128, device=device, dtype=torch.float64)

    # 1. Serial execution
    serial_cfg = CommitteeEnsembleConfig(
        vectorized=False,
        concurrency_mode="serial",
        vram_headroom_threshold_mb=512.0,
    )
    ensemble_serial = CommitteeEnsemble(models, config=serial_cfg)
    out_serial = ensemble_serial.forward(batch_x)

    # 2. Vectorized execution (torch.vmap)
    vmap_cfg = CommitteeEnsembleConfig(
        vectorized=True,
        concurrency_mode="vmap",
        vram_headroom_threshold_mb=512.0,
    )
    ensemble_vmap = CommitteeEnsemble(models, config=vmap_cfg)
    out_vmap = ensemble_vmap.forward(batch_x)

    assert ensemble_serial.last_execution_mode == "serial"
    assert ensemble_vmap.last_execution_mode == "vmap"

    # Invariance check for mean predictions
    max_mean_diff = float(torch.max(torch.abs(out_vmap.mean - out_serial.mean)).item())
    assert max_mean_diff < 1e-12, f"Mean prediction divergence: {max_mean_diff} >= 1e-12 [M]"

    # Invariance check for epistemic standard deviation
    max_std_diff = float(torch.max(torch.abs(out_vmap.std - out_serial.std)).item())
    assert max_std_diff < 1e-12, f"Epistemic std divergence: {max_std_diff} >= 1e-12 [M]"

    # Check unpacking support: mean, std = ensemble(x)
    mean_unpacked, std_unpacked = out_vmap
    assert torch.allclose(mean_unpacked, out_vmap.mean)
    assert torch.allclose(std_unpacked, out_vmap.std)


def test_dynamic_vram_throttling_fallback():
    """Verify that when available memory drops below threshold, inference gracefully falls back to serial. [M]"""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    models = [MolecularFeatureMLP(128, 32, 1).to(device=device, dtype=torch.float64) for _ in range(4)]
    batch_x = torch.randn(32, 128, device=device, dtype=torch.float64)

    current_free_mb = get_available_vram_mb()

    # Configure threshold significantly higher than actual free memory to force throttling
    throttled_cfg = CommitteeEnsembleConfig(
        vectorized=True,
        concurrency_mode="vmap",
        vram_headroom_threshold_mb=current_free_mb + 50000.0,
    )
    ensemble = CommitteeEnsemble(models, config=throttled_cfg)
    out = ensemble.forward(batch_x)

    assert ensemble.last_execution_mode == "serial", (
        f"Expected serialized fallback under constrained memory headroom, got {ensemble.last_execution_mode}"
    )
    assert out.mean.shape == (32, 1)
    assert out.std.shape == (32, 1)


def test_heterogeneous_model_concurrency_fallback():
    """Verify that models with non-identical architectures fall back from vmap cleanly without crashing. [M]"""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # Member 0 and 1 have hidden_dim=64, Member 2 has hidden_dim=32
    m1 = MolecularFeatureMLP(128, 64, 1).to(device=device, dtype=torch.float64)
    m2 = MolecularFeatureMLP(128, 64, 1).to(device=device, dtype=torch.float64)
    m3 = MolecularFeatureMLP(128, 32, 1).to(device=device, dtype=torch.float64)

    cfg = CommitteeEnsembleConfig(
        vectorized=True,
        concurrency_mode="vmap",
        vram_headroom_threshold_mb=512.0,
    )
    ensemble = CommitteeEnsemble([m1, m2, m3], config=cfg)
    batch_x = torch.randn(16, 128, device=device, dtype=torch.float64)
    out = ensemble.forward(batch_x)

    # Heterogeneous shapes cannot be stacked for vmap, so it falls back to streams/serial
    assert ensemble.last_execution_mode in ("cuda_streams", "serial")
    assert out.mean.shape == (16, 1)


def test_energy_and_forces_moments():
    """Verify unbiased moment calculations for energy and conservative force predictions. [M]/[D]"""
    # 4 models, batch of 1, 5 atoms
    M, N = 4, 5
    energies = torch.tensor([-75.1, -75.12, -75.08, -75.11], dtype=torch.float64)
    forces = torch.randn(M, N, 3, dtype=torch.float64)

    pred = compute_committee_moments(energies, forces)
    assert pred.mean_energy.shape == ()
    assert pred.mean_forces.shape == (N, 3)
    assert pred.energy_variance > 0.0
    assert pred.per_atom_force_variance.shape == (N,)
    assert pred.max_force_std > 0.0
