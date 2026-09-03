"""Authentic physical verification test suite for Gradient Checkpointing Engine (REQ-TORQ-TRAIN-091).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic molecular systems and real PyTorch tensors.
"""

from __future__ import annotations

import pytest
import torch
import torch.nn as nn

from Libraries.cochem_torq_gradient_checkpointing import (
    CheckpointedMLFF,
    compute_composite_loss,
    evaluate_forces_parity,
    profile_checkpointing_memory,
)
from tests.torq_test_fixtures import (
    get_alanine_dipeptide_fixture,
    get_water_dimer_fixture,
)


class StochasticToyPotential(nn.Module):
    """Authentic physical testing potential featuring dropout to test RNG state preservation."""

    def __init__(self, hidden_dim: int = 32) -> None:
        super().__init__()
        self.embedding = nn.Embedding(119, hidden_dim, dtype=torch.float64)
        self.dropout = nn.Dropout(p=0.2)
        self.linear1 = nn.Linear(hidden_dim + 12, hidden_dim, dtype=torch.float64)
        self.silu = nn.SiLU()
        self.linear2 = nn.Linear(hidden_dim, 1, dtype=torch.float64)
        self.r_centers = nn.Parameter(
            torch.linspace(0.8, 5.0, 12, dtype=torch.float64),
            requires_grad=False,
        )

    def forward(
        self,
        coordinates: torch.Tensor,
        species: torch.Tensor,
        edge_index: torch.Tensor | None = None,
        batch: torch.Tensor | None = None,
    ) -> torch.Tensor:
        diff = coordinates.unsqueeze(1) - coordinates.unsqueeze(0)
        dist = torch.norm(diff + 1e-12, dim=-1)
        r_exp = torch.exp(-0.5 * torch.square((dist.unsqueeze(-1) - self.r_centers) / 0.35))
        r_features = torch.sum(r_exp, dim=1)  # (N, 12)

        z_emb = self.embedding(species).to(torch.float64)
        node_features = torch.cat([z_emb, r_features], dim=-1)
        h = self.linear1(node_features)
        h = self.silu(h)
        h = self.dropout(h)
        atomic_e = self.linear2(h).squeeze(-1)
        return torch.sum(atomic_e)


def test_water_dimer_force_parity() -> None:
    """Verify exact analytical force parity on Water dimer (H2O)2 between eager and checkpointed autograd. [M]"""
    coords, species = get_water_dimer_fixture()
    torch.manual_seed(1234)
    model = StochasticToyPotential(hidden_dim=32).to(torch.float64)
    model.eval()  # Deterministic mode for exact numerical parity test

    max_delta, f_eager, f_chkpt = evaluate_forces_parity(model, coords, species)

    assert max_delta < 1e-7, (
        f"Force parity violation on Water dimer: max delta {max_delta:.2e} exceeds threshold 1e-7."
    )
    assert f_eager.shape == coords.shape
    assert f_chkpt.shape == coords.shape


def test_alanine_dipeptide_force_parity() -> None:
    """Verify exact analytical force parity on Alanine dipeptide (N=22). [M]"""
    coords, species = get_alanine_dipeptide_fixture()
    torch.manual_seed(5678)
    model = StochasticToyPotential(hidden_dim=32).to(torch.float64)
    model.eval()

    max_delta, f_eager, f_chkpt = evaluate_forces_parity(model, coords, species)

    assert max_delta < 1e-7, (
        f"Force parity violation on Alanine dipeptide: max delta {max_delta:.2e} exceeds threshold 1e-7."
    )


def test_rng_state_preservation() -> None:
    """Verify bit-for-bit RNG determinism during activation recomputation with dropout enabled. [M]"""
    coords, species = get_water_dimer_fixture()
    coords = coords.clone().detach().requires_grad_(True)

    torch.manual_seed(42)
    model = StochasticToyPotential(hidden_dim=32).to(torch.float64)
    model.train()  # Enable dropout

    wrapper = CheckpointedMLFF(model, gradient_checkpointing=True, preserve_rng_state=True)

    # Run pass 1
    torch.manual_seed(999)
    coords1 = coords.clone().detach().requires_grad_(True)
    e1, f1 = wrapper(coords1, species)
    loss1 = e1.sum() + f1.sum()
    loss1.backward()
    grad1 = [p.grad.clone() for p in model.parameters() if p.grad is not None]

    model.zero_grad()

    # Run pass 2 with identical seed
    torch.manual_seed(999)
    coords2 = coords.clone().detach().requires_grad_(True)
    e2, f2 = wrapper(coords2, species)
    loss2 = e2.sum() + f2.sum()
    loss2.backward()
    grad2 = [p.grad.clone() for p in model.parameters() if p.grad is not None]

    # Verify bit-for-bit exact reproduction
    assert torch.equal(e1, e2), "Energy mismatch across identical RNG recomputation passes."
    assert torch.equal(f1, f2), "Force mismatch across identical RNG recomputation passes."
    for g1, g2 in zip(grad1, grad2):
        assert torch.equal(g1, g2), "Gradient mismatch across identical RNG recomputation passes."


def test_composite_loss_and_second_derivatives() -> None:
    """Verify second-derivative backpropagation d^2E/(dtheta dR) under composite loss. [D]"""
    coords, species = get_alanine_dipeptide_fixture()
    coords = coords.clone().detach().requires_grad_(True)

    torch.manual_seed(101)
    model = StochasticToyPotential(hidden_dim=24).to(torch.float64)
    model.train()

    wrapper = CheckpointedMLFF(model, gradient_checkpointing=True)
    pred_energy, pred_forces = wrapper(coords, species)

    # Reference values with slight physical displacement
    ref_energy = pred_energy.detach() + 0.05
    ref_forces = pred_forces.detach() + 0.01

    total_loss, e_loss, f_loss = compute_composite_loss(
        predicted_energy=pred_energy,
        reference_energy=ref_energy,
        predicted_forces=pred_forces,
        reference_forces=ref_forces,
        energy_loss_weight=1.0,
        force_loss_weight=100.0,
    )

    assert total_loss.item() > 0.0
    assert not torch.isnan(total_loss)
    assert not torch.isinf(total_loss)

    # Backpropagate second-order gradients into model weights
    total_loss.backward()

    # Verify gradients exist, are finite, and non-zero
    for name, p in model.named_parameters():
        if p.requires_grad:
            assert p.grad is not None, f"Missing gradient for parameter {name}"
            assert not torch.isnan(p.grad).any(), f"NaN in gradient for {name}"
            assert not torch.isinf(p.grad).any(), f"Inf in gradient for {name}"
            assert torch.norm(p.grad) > 0.0, f"Zero gradient for {name}"


def test_checkpointing_memory_benchmarking() -> None:
    """Verify memory tracking via tracemalloc on CPU and CUDA VRAM if available. [M]"""
    coords, species = get_alanine_dipeptide_fixture()
    model = StochasticToyPotential(hidden_dim=32).to(torch.float64)

    metrics = profile_checkpointing_memory(model, coords, species)

    assert "eager_bytes" in metrics
    assert "checkpoint_bytes" in metrics
    assert metrics["eager_bytes"] > 0
    assert metrics["checkpoint_bytes"] > 0


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required for VRAM benchmark")
def test_cuda_vram_ratio_benchmark() -> None:
    """Assert VRAM_checkpoint <= 0.45 * VRAM_eager on CUDA hardware. [M]"""
    coords, species = get_alanine_dipeptide_fixture()
    model = StochasticToyPotential(hidden_dim=64).to(torch.float64).cuda()
    metrics = profile_checkpointing_memory(model, coords.cuda(), species.cuda())
    assert metrics["ratio"] <= 0.45, f"VRAM ratio {metrics['ratio']:.2f} exceeded 0.45 threshold."
