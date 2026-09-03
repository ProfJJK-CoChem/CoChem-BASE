"""Authentic physical verification test suite for GNN Gradient Health Debugger (REQ-TORQ-INF-105).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic message passing, Alanine Dipeptide (N=22), and numerical traps.
"""

from __future__ import annotations

import pytest
import torch
import torch.nn as nn

from Libraries.cochem_torq_gnn_debugger import GNNGradientDebugger
from Libraries.cochem_torq_inference_errors import (
    GradientExplosionError,
    VanishingGradientWarning,
)
from Libraries.cochem_torq_inference_schemas import GNNGradientDebuggerConfig


# Physical Fixture: Alanine Dipeptide (N=22) [M]
ALANINE_DIPEPTIDE_Z = torch.tensor(
    [6, 8, 7, 1, 6, 1, 6, 1, 1, 1, 6, 8, 7, 1, 6, 1, 1, 1, 6, 1, 1, 1],
    dtype=torch.int64,
)
ALANINE_DIPEPTIDE_COORDS = torch.tensor(
    [
        [2.012, -0.407, -0.380],
        [1.576, -1.488, -0.771],
        [1.341, 0.697, -0.016],
        [1.776, 1.564, 0.222],
        [-0.089, 0.722, 0.134],
        [-0.344, 0.245, 1.087],
        [-0.721, -0.091, -1.011],
        [-0.495, 0.373, -1.975],
        [-0.334, -1.114, -0.999],
        [-1.808, -0.106, -0.898],
        [-0.589, 2.164, 0.180],
        [-0.038, 2.973, 0.923],
        [-1.637, 2.470, -0.581],
        [-2.083, 1.758, -1.144],
        [-2.247, 3.794, -0.570],
        [-2.213, 4.195, 0.446],
        [-1.706, 4.475, -1.234],
        [-3.284, 3.714, -0.899],
        [3.472, -0.107, -0.324],
        [3.659, 0.885, -0.738],
        [4.020, -0.852, -0.902],
        [3.829, -0.119, 0.710],
    ],
    dtype=torch.float32,
)


def get_alanine_edge_index(cutoff: float = 3.0) -> torch.Tensor:
    """Build authentic bond/radial edge index for Alanine Dipeptide coordinates within cutoff. [M]"""
    diff = ALANINE_DIPEPTIDE_COORDS.unsqueeze(1) - ALANINE_DIPEPTIDE_COORDS.unsqueeze(0)
    dist = torch.norm(diff, dim=-1)
    mask = (dist > 0.01) & (dist <= cutoff)
    src, dst = torch.where(mask)
    return torch.stack([src, dst], dim=0)


class MessagePassingInteractionBlock(nn.Module):
    """Authentic message-passing interaction block on molecular graphs. [M]"""

    def __init__(self, dim: int = 16, init_weight: float = 1.0) -> None:
        super().__init__()
        self.linear1 = nn.Linear(dim, dim)
        self.linear2 = nn.Linear(dim, dim)
        with torch.no_grad():
            self.linear1.weight.fill_(init_weight)
            self.linear2.weight.fill_(init_weight)

    def forward(self, h: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        src, dst = edge_index[0], edge_index[1]
        msg = torch.relu(self.linear1(h[src]))
        agg = torch.zeros_like(h)
        agg.index_add_(0, dst, msg)
        return h + self.linear2(agg)


class MultiBlockGNN(nn.Module):
    """Multi-layer GNN architecture for molecular property prediction. [M]"""

    def __init__(self, num_blocks: int = 4, dim: int = 16, init_weight: float = 1.0) -> None:
        super().__init__()
        self.embedding = nn.Embedding(100, dim)
        self.blocks = nn.ModuleList([
            MessagePassingInteractionBlock(dim=dim, init_weight=init_weight)
            for _ in range(num_blocks)
        ])
        self.out = nn.Linear(dim, 1)

    def forward(self, z: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        h = self.embedding(z)
        for block in self.blocks:
            h = block(h, edge_index)
        return self.out(h).mean()


def test_debugger_captures_activation_and_gradient_norms() -> None:
    """Verify debugger records forward activation norms and backward gradient norms. [M]"""
    model = MultiBlockGNN(num_blocks=3, dim=16, init_weight=0.05)
    debugger = GNNGradientDebugger()
    edge_index = get_alanine_edge_index()

    with debugger.probe(model):
        out = model(ALANINE_DIPEPTIDE_Z, edge_index)
        loss = out
        loss.backward()

        act_norms = debugger.get_activation_norms()
        grad_norms = debugger.get_gradient_norms()

        assert len(act_norms) > 0
        assert len(grad_norms) > 0
        for name, norm in act_norms.items():
            assert norm > 0.0
        for name, norm in grad_norms.items():
            assert norm > 0.0

    # Ensure hooks are cleanly removed upon context exit
    assert len(debugger.handles) == 0


def test_exploding_gradient_trap() -> None:
    """Verify large gradient norm > 10^3 immediately raises GradientExplosionError. [D]"""
    # Initialize with large weights to trigger autograd explosion
    model = MultiBlockGNN(num_blocks=4, dim=16, init_weight=30.0)
    config = GNNGradientDebuggerConfig(exploding_grad_threshold=1000.0)
    debugger = GNNGradientDebugger(config)
    edge_index = get_alanine_edge_index()

    with pytest.raises(GradientExplosionError):
        with debugger.probe(model):
            out = model(ALANINE_DIPEPTIDE_Z, edge_index)
            # Multiplying loss by large scale ensures backward pass explodes
            loss = out * 1000.0
            loss.backward()


def test_vanishing_gradient_warning() -> None:
    """Verify gradient norms below 1e-7 across consecutive layers emits VanishingGradientWarning. [D]"""
    model = MultiBlockGNN(num_blocks=4, dim=16, init_weight=1e-5)
    config = GNNGradientDebuggerConfig(
        vanishing_grad_threshold=1e-7,
        consecutive_vanishing_blocks=3,
    )
    debugger = GNNGradientDebugger(config)
    edge_index = get_alanine_edge_index()

    with pytest.warns(VanishingGradientWarning):
        with debugger.probe(model):
            out = model(ALANINE_DIPEPTIDE_Z, edge_index)
            loss = out * 1e-12
            loss.backward()


def test_zero_overhead_when_disabled() -> None:
    """Verify debugger attaches no active hooks when config.enabled is False. [M]"""
    model = MultiBlockGNN(num_blocks=2, dim=8)
    config = GNNGradientDebuggerConfig(enabled=False)
    debugger = GNNGradientDebugger(config)

    with debugger.probe(model):
        assert len(debugger.handles) == 0
        out = model(ALANINE_DIPEPTIDE_Z, get_alanine_edge_index())
        assert debugger.get_activation_norms() == {}
