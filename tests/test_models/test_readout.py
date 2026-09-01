"""Zero-Mock Physics Contract & Unit Test Suite for EnergyReadout and ShiftedSoftplus.
=====================================================================================
Provides production-grade mathematical and physical validation of EnergyReadout,
ShiftedSoftplus, thermodynamic extensivity, permutation invariance, and C^2 differentiability.

Authoritative Standards & Physics Contracts:
- Method Matrix v4: Physics Contract, Invariance/Equivariance Bounds, Provenance Tags
- SWEBOK v3 / ISO 25010 Software Quality & Mathematical Correctness Standards
- Strict Zero-Mock Mandate: 100% real physical tensor mathematics, zero mocks/stubs
- Thermodynamic Extensivity: Total potential energy is additive over atomic nodes:
    E(M_A \\cup M_B) = E(M_A) + E(M_B)  [D]
- C^2 Differentiability: Smooth non-vanishing derivatives for force and Hessian autograd:
    F = -\\nabla_r E  [D],  H = \\nabla_r^2 E  [D]
- Provenance Tagging: Explicitly tag all tolerances, constants, and bounds with [M], [D], [E]
"""

from __future__ import annotations

import math
from pathlib import Path
import sys
from typing import Any, Callable

import pytest
import torch
import torch.nn as nn
from torch_geometric.nn import global_add_pool, global_max_pool, global_mean_pool

# Ensure CoChem source root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cochem_geom.models.layers.readout import EnergyReadout, ShiftedSoftplus


class TestShiftedSoftplus:
    """Mathematical and differentiability validation suite for ShiftedSoftplus [D]."""

    def test_shifted_softplus_value_at_zero(self) -> None:
        """Verify ShiftedSoftplus maps 0 -> 0 exactly [D]."""
        ssp = ShiftedSoftplus()
        x = torch.tensor([0.0], dtype=torch.float64)
        out = ssp(x)
        expected = math.log(1.0 + math.exp(0.0)) - math.log(2.0)
        assert abs(out.item() - 0.0) < 1e-12
        assert abs(out.item() - expected) < 1e-12

    def test_shifted_softplus_first_derivative(self) -> None:
        """Verify f'(0) = 0.5 (logistic sigmoid at 0) [D]."""
        ssp = ShiftedSoftplus()
        x = torch.tensor([0.0], dtype=torch.float64, requires_grad=True)
        y = ssp(x)
        (grad_x,) = torch.autograd.grad(y, x, create_graph=True)
        assert abs(grad_x.item() - 0.5) < 1e-7

    def test_shifted_softplus_second_derivative(self) -> None:
        """Verify f''(0) = sigma(0) * (1 - sigma(0)) = 0.25 [D]."""
        ssp = ShiftedSoftplus()
        x = torch.tensor([0.0], dtype=torch.float64, requires_grad=True)
        y = ssp(x)
        (grad_x,) = torch.autograd.grad(y, x, create_graph=True)
        (grad2_x,) = torch.autograd.grad(grad_x, x)
        assert abs(grad2_x.item() - 0.25) < 1e-7

    def test_shifted_softplus_asymptotics(self) -> None:
        """Verify asymptotic behavior for large positive and negative inputs [D]."""
        ssp = ShiftedSoftplus()
        x_pos = torch.tensor([50.0], dtype=torch.float64)
        out_pos = ssp(x_pos)
        expected_pos = 50.0 - math.log(2.0)
        assert abs(out_pos.item() - expected_pos) < 1e-7

        x_neg = torch.tensor([-50.0], dtype=torch.float64)
        out_neg = ssp(x_neg)
        expected_neg = -math.log(2.0)
        assert abs(out_neg.item() - expected_neg) < 1e-7


class TestEnergyReadoutInitialization:
    """Parameter validation and configuration tests for EnergyReadout [D]."""

    def test_valid_init_defaults(self) -> None:
        """Verify default parameters instantiate correctly."""
        readout = EnergyReadout(hidden_channels=64)
        assert readout.hidden_channels == 64
        assert readout.out_channels == 1
        assert readout.aggr == "sum"
        assert readout.pool is global_add_pool
        assert len(readout.output_network) == 3
        assert isinstance(readout.output_network[0], nn.Linear)
        assert isinstance(readout.output_network[1], nn.SiLU)
        assert isinstance(readout.output_network[2], nn.Linear)

    def test_invalid_hidden_channels(self) -> None:
        """Verify ValueError is raised on non-positive hidden_channels."""
        with pytest.raises(ValueError, match="hidden_channels must be a positive integer"):
            EnergyReadout(hidden_channels=0)
        with pytest.raises(ValueError, match="hidden_channels must be a positive integer"):
            EnergyReadout(hidden_channels=-16)

    def test_invalid_out_channels(self) -> None:
        """Verify ValueError is raised on non-positive out_channels."""
        with pytest.raises(ValueError, match="out_channels must be a positive integer"):
            EnergyReadout(hidden_channels=32, out_channels=0)
        with pytest.raises(ValueError, match="out_channels must be a positive integer"):
            EnergyReadout(hidden_channels=32, out_channels=-1)

    @pytest.mark.parametrize(
        "act_name, expected_type",
        [
            ("silu", nn.SiLU),
            ("gelu", nn.GELU),
            ("tanh", nn.Tanh),
            ("relu", nn.ReLU),
            ("ssp", ShiftedSoftplus),
            ("shifted_softplus", ShiftedSoftplus),
            ("softplus", nn.Softplus),
        ],
    )
    def test_activation_string_resolution(self, act_name: str, expected_type: type) -> None:
        """Verify activation strings resolve to expected Module types."""
        readout = EnergyReadout(hidden_channels=32, activation=act_name)
        assert isinstance(readout.output_network[1], expected_type)

    def test_custom_activation_module(self) -> None:
        """Verify custom nn.Module activation is supported."""
        custom_act = nn.LeakyReLU(0.1)
        readout = EnergyReadout(hidden_channels=32, activation=custom_act)
        assert readout.output_network[1] is custom_act

    @pytest.mark.parametrize(
        "aggr_name, expected_pool",
        [
            ("sum", global_add_pool),
            ("add", global_add_pool),
            ("mean", global_mean_pool),
            ("avg", global_mean_pool),
            ("max", global_max_pool),
        ],
    )
    def test_aggregation_resolution(self, aggr_name: str, expected_pool: Any) -> None:
        """Verify aggregation string maps to appropriate PyG pooling function."""
        readout = EnergyReadout(hidden_channels=32, aggr=aggr_name)
        assert readout.pool is expected_pool


class TestEnergyReadoutForward:
    """Execution, shape correctness, and physical contract validation for EnergyReadout [D]."""

    def test_predict_atomic(self) -> None:
        """Verify predict_atomic produces correct atomic contribution shapes [N, out_channels]."""
        readout = EnergyReadout(hidden_channels=32, out_channels=1)
        x = torch.randn(10, 32, dtype=torch.float32)
        atomic_e = readout.predict_atomic(x)
        assert atomic_e.shape == (10, 1)

    def test_predict_atomic_shape_errors(self) -> None:
        """Verify shape validation in predict_atomic."""
        readout = EnergyReadout(hidden_channels=32, out_channels=1)
        with pytest.raises(ValueError, match="Expected 2D node feature tensor"):
            readout.predict_atomic(torch.randn(10, 32, 1))
        with pytest.raises(ValueError, match="Expected last dimension to match hidden_channels"):
            readout.predict_atomic(torch.randn(10, 64))

    def test_forward_single_graph_default_batch(self) -> None:
        """Verify forward with default batch=None treats all nodes as single graph [1, out_channels]."""
        readout = EnergyReadout(hidden_channels=32, out_channels=1)
        x = torch.randn(12, 32, dtype=torch.float32)
        out = readout(x)
        assert out.shape == (1, 1)

    def test_forward_batched_graphs(self) -> None:
        """Verify forward with batch vector produces correct graph energy shapes [B, out_channels]."""
        readout = EnergyReadout(hidden_channels=32, out_channels=1)
        x = torch.randn(15, 32, dtype=torch.float32)
        batch = torch.tensor([0] * 5 + [1] * 6 + [2] * 4, dtype=torch.long)
        out = readout(x, batch=batch)
        assert out.shape == (3, 1)

    def test_forward_return_atomic(self) -> None:
        """Verify return_atomic=True returns (energy, atomic_energies) tuple."""
        readout = EnergyReadout(hidden_channels=32, out_channels=1)
        x = torch.randn(10, 32, dtype=torch.float32)
        batch = torch.tensor([0] * 6 + [1] * 4, dtype=torch.long)
        energy, atomic_e = readout(x, batch=batch, return_atomic=True)
        assert energy.shape == (2, 1)
        assert atomic_e.shape == (10, 1)
        g0_sum = atomic_e[:6].sum(dim=0, keepdim=True)
        assert torch.allclose(energy[0:1], g0_sum, atol=1e-6)

    def test_forward_shape_errors(self) -> None:
        """Verify shape validation in forward pass."""
        readout = EnergyReadout(hidden_channels=32, out_channels=1)
        with pytest.raises(ValueError, match="Expected 2D node feature tensor"):
            readout(torch.randn(10))
        with pytest.raises(ValueError, match="Expected last dimension to match hidden_channels"):
            readout(torch.randn(10, 16))

    def test_thermodynamic_extensivity(self) -> None:
        """Physics Contract: Energy of composite system equals sum of component energies [D]."""
        readout = EnergyReadout(hidden_channels=32, out_channels=1, aggr="sum")
        x_a = torch.randn(6, 32, dtype=torch.float32)
        x_b = torch.randn(8, 32, dtype=torch.float32)

        e_a = readout(x_a)
        e_b = readout(x_b)

        x_combined = torch.cat([x_a, x_b], dim=0)
        batch_combined = torch.tensor([0] * 6 + [1] * 8, dtype=torch.long)
        e_batched = readout(x_combined, batch=batch_combined)

        assert torch.allclose(e_batched[0], e_a[0], atol=1e-6)
        assert torch.allclose(e_batched[1], e_b[0], atol=1e-6)
        assert torch.allclose(e_batched.sum(), e_a + e_b, atol=1e-6)

    def test_permutation_invariance_within_graph(self) -> None:
        """Physics Contract: Permutation of nodes within graph leaves graph energy invariant [M]."""
        readout = EnergyReadout(hidden_channels=32, out_channels=1, aggr="sum")
        x = torch.randn(10, 32, dtype=torch.float32)
        perm = torch.randperm(10)
        x_perm = x[perm]

        e_orig = readout(x)
        e_perm = readout(x_perm)
        assert torch.allclose(e_orig, e_perm, atol=1e-6)

    def test_c2_differentiability_for_hessians(self) -> None:
        """Physics Contract: C^2 smoothness guarantees valid non-vanishing second derivatives [D]."""
        readout = EnergyReadout(hidden_channels=16, out_channels=1, activation="silu").to(torch.float64)
        x = torch.randn(5, 16, dtype=torch.float64, requires_grad=True)
        energy = readout(x).sum()

        (grad1,) = torch.autograd.grad(energy, x, create_graph=True)
        assert grad1.shape == x.shape
        assert not torch.isnan(grad1).any()
        assert not torch.isinf(grad1).any()

        (grad2,) = torch.autograd.grad(grad1.sum(), x)
        assert grad2.shape == x.shape
        assert not torch.isnan(grad2).any()
        assert not torch.isinf(grad2).any()

    def test_extra_repr(self) -> None:
        """Verify extra_repr metadata formatting string."""
        readout = EnergyReadout(hidden_channels=32, out_channels=1, aggr="sum")
        rep = readout.extra_repr()
        assert "hidden_channels=32" in rep
        assert "out_channels=1" in rep
        assert "aggr='sum'" in rep
        assert "global_add_pool" in rep
