"""Authentic physical verification test suite for GNN Warm Restart Scheduler (REQ-TORQ-TRAIN-097 [D]).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic numerical and physical verification with Alanine Dipeptide (N=22).
"""

from __future__ import annotations

import math
import pytest
import torch
import torch.nn as nn

from Libraries.cochem_torq_gnn_scheduler import (
    GNNWarmRestartScheduler,
    check_and_clip_gradients,
    compute_lr_at_step,
)
from Libraries.cochem_torq_training_errors import SchedulerDivergenceError
from Libraries.cochem_torq_training_schemas import GNNWarmRestartSchedulerConfig
from tests.torq_test_fixtures import get_alanine_dipeptide_fixture


class AlanineDipeptideModel(nn.Module):
    """Authentic physical neural backbone for Alanine Dipeptide (N=22). [M]"""

    def __init__(self, hidden_dim: int = 32) -> None:
        super().__init__()
        self.embedding = nn.Embedding(119, hidden_dim)
        self.r_centers = nn.Parameter(
            torch.linspace(0.8, 6.0, 16, dtype=torch.float32),
            requires_grad=False,
        )
        self.net = nn.Sequential(
            nn.Linear(hidden_dim + 16, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, coordinates: torch.Tensor, species: torch.Tensor) -> torch.Tensor:
        coords_f = coordinates.float()
        diff = coords_f.unsqueeze(1) - coords_f.unsqueeze(0)
        dist = torch.norm(diff + 1e-12, dim=-1)
        r_exp = torch.exp(-0.5 * torch.square((dist.unsqueeze(-1) - self.r_centers) / 0.5))
        r_sum = torch.sum(r_exp, dim=1)

        z_emb = self.embedding(species)
        node_feats = torch.cat([z_emb, r_sum], dim=-1)
        atomic_e = self.net(node_feats).squeeze(-1)
        return torch.sum(atomic_e)


def test_linear_warmup_trajectory() -> None:
    """Verify learning rate advances deterministically from eta_0 = eta_min to eta_1000 = eta_max. [D]"""
    config = GNNWarmRestartSchedulerConfig(
        initial_lr=1e-4,
        min_lr=1e-7,
        warmup_steps=1000,
        first_cycle_steps=10000,
        cycle_multiplier=1.5,
        restart_decay=0.75,
    )

    # 1. At step 0: exactly min_lr
    lr_0 = compute_lr_at_step(0, config)
    assert math.isclose(lr_0, 1e-7, rel_tol=1e-8, abs_tol=1e-12)

    # 2. At step 500: halfway point
    lr_500 = compute_lr_at_step(500, config)
    expected_500 = 1e-7 + 0.5 * (1e-4 - 1e-7)
    assert math.isclose(lr_500, expected_500, rel_tol=1e-8)

    # 3. At step 1000: peak initial_lr
    lr_1000 = compute_lr_at_step(1000, config)
    assert math.isclose(lr_1000, 1e-4, rel_tol=1e-8, abs_tol=1e-12)


def test_warm_restart_cycle_expansion_and_peak_attenuation() -> None:
    """Confirm initial restart satisfies eta_max^(1) = 0.75 * eta_max^(0) and cycle expands by T_mult. [D]"""
    config = GNNWarmRestartSchedulerConfig(
        initial_lr=1e-4,
        min_lr=1e-7,
        warmup_steps=1000,
        first_cycle_steps=10000,
        cycle_multiplier=1.5,
        restart_decay=0.75,
    )

    # Cycle 0 ends at step 1000 + 10000 = 11000
    # At step 11000: cycle 1 restarts with peak LR = 0.75 * 1e-4 = 7.5e-5
    lr_restart_1 = compute_lr_at_step(11000, config)
    expected_peak_1 = 0.75 * 1e-4
    assert math.isclose(lr_restart_1, expected_peak_1, rel_tol=1e-8, abs_tol=1e-8)

    # Cycle 1 duration is 10000 * 1.5 = 15000 steps
    # Cycle 2 starts at 11000 + 15000 = 26000
    lr_restart_2 = compute_lr_at_step(26000, config)
    expected_peak_2 = (0.75**2) * 1e-4
    assert math.isclose(lr_restart_2, expected_peak_2, rel_tol=1e-8, abs_tol=1e-8)


def test_step_based_optimizer_integration_alanine_dipeptide() -> None:
    """Verify scheduler updates on every optimizer step rather than epoch boundaries. [D]"""
    coords, species = get_alanine_dipeptide_fixture()
    assert coords.shape[0] == 22, "Alanine dipeptide must have N=22 atoms."

    model = AlanineDipeptideModel(hidden_dim=16)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)

    config = GNNWarmRestartSchedulerConfig(
        initial_lr=1e-4,
        min_lr=1e-7,
        warmup_steps=100,
        first_cycle_steps=500,
        max_grad_norm=1.0,
    )
    scheduler = GNNWarmRestartScheduler(optimizer, config)

    initial_lr = optimizer.param_groups[0]["lr"]
    assert math.isclose(initial_lr, 1e-7, rel_tol=1e-6)

    # Execute 5 optimization steps on Alanine dipeptide
    coords_var = coords.clone().requires_grad_(True)
    for step_idx in range(1, 6):
        optimizer.zero_grad()
        energy = model(coords_var, species)
        energy.backward()

        unclipped_norm = scheduler.step_and_clip()
        assert unclipped_norm > 0.0

        current_lr = optimizer.param_groups[0]["lr"]
        expected_lr = compute_lr_at_step(step_idx, config)
        assert math.isclose(current_lr, expected_lr, rel_tol=1e-6)


def test_gradient_norm_clipping_enforcement() -> None:
    """Assert parameter gradients are clipped strictly to ||g||_2 <= 1.0 eV/Angstrom. [D]"""
    model = nn.Sequential(nn.Linear(10, 10), nn.Linear(10, 1))
    optimizer = torch.optim.SGD(model.parameters(), lr=1e-3)

    # Inject large gradients
    for p in model.parameters():
        p.grad = torch.full_like(p.data, 50.0)

    norm = check_and_clip_gradients(optimizer, max_grad_norm=1.0)
    assert norm > 1.0, "Unclipped norm should exceed ceiling."

    # Compute new gradient norm after clipping
    clipped_norm_sq = sum(float(p.grad.norm(2).item()) ** 2 for p in model.parameters())
    clipped_norm = math.sqrt(clipped_norm_sq)
    assert math.isclose(clipped_norm, 1.0, rel_tol=1e-5, abs_tol=1e-5)


def test_scheduler_divergence_error_on_nan_gradient() -> None:
    """Inject NaN gradients and verify SchedulerDivergenceError is raised. [D]"""
    model = nn.Linear(5, 1)
    optimizer = torch.optim.SGD(model.parameters(), lr=1e-3)

    # Inject NaN into gradient
    for p in model.parameters():
        p.grad = torch.tensor([float("nan")] * p.numel()).reshape(p.shape)

    with pytest.raises(SchedulerDivergenceError) as exc_info:
        check_and_clip_gradients(optimizer, max_grad_norm=1.0)

    assert "NaN or Inf" in str(exc_info.value)
