"""Authentic physical verification test suite for Scale-Invariant Loss Landscape (REQ-TORQ-TRAIN-095).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Converged physical checkpoint on authentic Water monomer.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import torch
import torch.nn as nn

from Libraries.cochem_torq_loss_landscape import (
    compute_1d_loss_surface,
    compute_2d_loss_grid,
    generate_filter_normalized_direction,
    generate_orthogonal_filter_directions,
    render_loss_contour_plot,
)
from Libraries.cochem_torq_training_schemas import LossLandscapeConfig


class SimpleWaterPotential(nn.Module):
    """Authentic physical neural potential for water molecule landscape profiling."""

    def __init__(self) -> None:
        super().__init__()
        self.r_centers = nn.Parameter(
            torch.tensor([0.957, 1.514, 2.0], dtype=torch.float64),
            requires_grad=False,
        )
        self.linear1 = nn.Linear(3, 16, dtype=torch.float64)
        self.silu = nn.SiLU()
        self.linear2 = nn.Linear(16, 1, dtype=torch.float64)

    def forward(self, coords: torch.Tensor) -> torch.Tensor:
        # Distance matrix for water (3 atoms: O, H1, H2)
        diff = coords.unsqueeze(1) - coords.unsqueeze(0)
        dist = torch.norm(diff + 1e-12, dim=-1)
        # 3 pairwise distances: (O-H1, O-H2, H1-H2)
        d_oh1 = dist[0, 1]
        d_oh2 = dist[0, 2]
        d_hh = dist[1, 2]
        d_vec = torch.stack([d_oh1, d_oh2, d_hh])
        feat = torch.exp(-0.5 * torch.square(d_vec - self.r_centers))
        h = self.silu(self.linear1(feat))
        energy = self.linear2(h).squeeze(-1)
        return energy


def pretrain_converged_checkpoint(coords: torch.Tensor) -> Tuple[SimpleWaterPotential, float]:
    """Train potential on authentic water coordinates for 200 steps to reach local minimum. [M]"""
    torch.manual_seed(42)
    model = SimpleWaterPotential()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.01, weight_decay=1e-4)

    target_energy = torch.tensor(0.0, dtype=torch.float64)

    for step in range(200):
        optimizer.zero_grad()
        pred_e = model(coords)
        loss = torch.square(pred_e - target_energy)
        loss.backward()
        optimizer.step()

    final_pred = model(coords)
    final_loss = float(torch.square(final_pred - target_energy).item())
    return model, final_loss


def test_filter_normalization_frobenius_norm_equality() -> None:
    """Verify generated direction vectors satisfy Frobenius norm equality ||d_j||_F = ||theta^*_j||_F. [D]"""
    model = SimpleWaterPotential()
    d1, d2 = generate_orthogonal_filter_directions(model, seed=42)

    for name, param in model.named_parameters():
        if param.requires_grad:
            assert name in d1
            assert name in d2

            p_data = param.data
            d1_data = d1[name]
            d2_data = d2[name]

            if p_data.dim() >= 2:
                # Check per-filter norm equality
                norm_p = torch.norm(p_data.view(p_data.size(0), -1), dim=1)
                norm_d1 = torch.norm(d1_data.view(d1_data.size(0), -1), dim=1)
                norm_d2 = torch.norm(d2_data.view(d2_data.size(0), -1), dim=1)

                diff1 = torch.max(torch.abs(norm_p - norm_d1)).item()
                diff2 = torch.max(torch.abs(norm_p - norm_d2)).item()
                assert diff1 < 1e-6, f"Filter Frobenius norm violation in {name} d1: max diff {diff1:.2e}"
                assert diff2 < 1e-6, f"Filter Frobenius norm violation in {name} d2: max diff {diff2:.2e}"
            else:
                norm_p = float(torch.norm(p_data).item())
                norm_d1 = float(torch.norm(d1_data).item())
                norm_d2 = float(torch.norm(d2_data).item())
                assert abs(norm_p - norm_d1) < 1e-6
                assert abs(norm_p - norm_d2) < 1e-6


def test_1d_loss_surface_profiles_minimum_at_center() -> None:
    """Verify 1D loss surface along alpha in [-0.5, 0.5] attains its minimum at alpha=0. [D]"""
    coords = torch.tensor(
        [
            [0.0000, 0.0000, 0.0000],  # Oxygen
            [0.0000, 0.7570, 0.5860],  # H1
            [0.0000, -0.7570, 0.5860], # H2
        ],
        dtype=torch.float64,
    )

    model, converged_loss = pretrain_converged_checkpoint(coords)
    d1 = generate_filter_normalized_direction(model, seed=123)

    target_e = torch.tensor(0.0, dtype=torch.float64)

    def eval_loss() -> float:
        with torch.no_grad():
            pred = model(coords)
            return float(torch.square(pred - target_e).item())

    alphas = [round(-0.5 + i * 0.05, 4) for i in range(21)]
    losses = compute_1d_loss_surface(model, eval_loss, d1, alphas)

    # Invariant: minimum loss must occur at alpha=0 (index 10) within tolerance
    min_idx = int(np.argmin(losses))
    min_alpha = float(alphas[min_idx])
    assert abs(min_alpha) <= 0.05, (
        f"1D loss profile minimum did not occur at alpha=0: min at alpha={min_alpha} (loss={losses[min_idx]:.2e})."
    )
    assert all(l >= 0.0 for l in losses), "Negative loss detected on loss surface."


def test_2d_loss_contour_plot_generation() -> None:
    """Verify 2D grid evaluation (10x10) and matplotlib PNG contour output rendering. [M]"""
    coords = torch.tensor(
        [
            [0.0000, 0.0000, 0.0000],
            [0.0000, 0.7570, 0.5860],
            [0.0000, -0.7570, 0.5860],
        ],
        dtype=torch.float64,
    )

    model, _ = pretrain_converged_checkpoint(coords)
    d1, d2 = generate_orthogonal_filter_directions(model, seed=456)

    with tempfile.TemporaryDirectory() as tmpdir:
        plot_path = Path(tmpdir) / "water_loss_landscape.png"
        config = LossLandscapeConfig(
            grid_resolution=10,
            range_min=-0.4,
            range_max=0.4,
            filter_normalization=True,
            output_plot_path=plot_path,
        )

        target_e = torch.tensor(0.0, dtype=torch.float64)

        def eval_loss() -> float:
            with torch.no_grad():
                pred = model(coords)
                return float(torch.square(pred - target_e).item())

        a_grid, b_grid, l_grid = compute_2d_loss_grid(model, eval_loss, d1, d2, config)

        assert l_grid.shape == (10, 10)
        assert not np.isnan(l_grid).any()
        assert (l_grid >= 0.0).all()

        saved_plot = render_loss_contour_plot(a_grid, b_grid, l_grid, config.output_plot_path)

        assert saved_plot.exists()
        assert saved_plot.stat().st_size > 1000  # Non-empty valid image file
