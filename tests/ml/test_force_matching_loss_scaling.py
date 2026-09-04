import os
os.environ["JAX_ENABLE_X64"] = "True"

import pytest
import torch
from mendeleev import element

from Libraries.cochem_torq_force_matching import ForceMatchingLoss
from cochem_base.schemas import ForceMatchingLossConfig


def test_force_matching_loss_normalization_scaling():
    """Verify atom_norm mode eliminates 3x gradient attenuation and scales correctly (Suggestion #55 / Method Matrix v4 §10.3 [M], [D])."""
    # Dynamic Mendeleev check
    c_elem = element("C")
    assert c_elem.atomic_number == 6

    # 1. Parameter setup
    delta_f = 0.05
    w_e = 1.0
    w_f = 10.0
    cfg_atom_norm = ForceMatchingLossConfig(
        energy_weight=w_e,
        force_weight=w_f,
        huber_delta_force=delta_f,
        normalization_mode="atom_norm",
    )
    loss_engine = ForceMatchingLoss(config=cfg_atom_norm)

    pred_e = torch.tensor([10.1], dtype=torch.float64)
    target_e = torch.tensor([10.0], dtype=torch.float64)

    # For N=2 atoms: each atom has force error [0.1, 0.0, 0.0]
    n_atoms = 2
    pred_f = torch.tensor([[[0.1, 0.0, 0.0], [0.1, 0.0, 0.0]]], dtype=torch.float64, requires_grad=True)
    target_f = torch.zeros_like(pred_f)

    out = loss_engine(pred_e, target_e, pred_f, target_f, num_atoms=[n_atoms])

    # Vector norm is 0.1 > delta_f (0.05). Huber loss = 0.1 - 0.5 * 0.05 = 0.075.
    # Total sum for 2 atoms = 0.15.
    # Normalized by total_atoms (2) = 0.075.
    # Weighted force loss = 10.0 * 0.075 = 0.75 (NOT 0.25!).
    expected_force_loss = w_f * 0.075
    assert abs(out["force_loss"].item() - expected_force_loss) < 1e-8

    # Verify backpropagation gradient w.r.t pred_f matches exact analytical expectation:
    # dL_F / dF_i = (w_f / N) * (err / ||err||) = (10.0 / 2) * [1.0, 0.0, 0.0] = [5.0, 0.0, 0.0]
    out["force_loss"].backward()
    assert pred_f.grad is not None
    expected_grad = torch.tensor([[[5.0, 0.0, 0.0], [5.0, 0.0, 0.0]]], dtype=torch.float64)
    assert torch.allclose(pred_f.grad, expected_grad, atol=1e-8)

    # 2. Compare against coordinate_component mode (which retains the 3x factor for Cartesian components)
    cfg_coord = ForceMatchingLossConfig(
        energy_weight=w_e,
        force_weight=w_f,
        huber_delta_force=delta_f,
        normalization_mode="coordinate_component",
    )
    loss_engine_coord = ForceMatchingLoss(config=cfg_coord)
    pred_f2 = torch.tensor([[[0.1, 0.0, 0.0], [0.1, 0.0, 0.0]]], dtype=torch.float64)
    out_coord = loss_engine_coord(pred_e, target_e, pred_f2, target_f, num_atoms=[n_atoms])

    # Component x error: 0.075. Components y, z: 0.0. Total = 0.15.
    # Normalized by 3 * N (6) = 0.025.
    # Weighted = 10.0 * 0.025 = 0.25.
    assert abs(out_coord["force_loss"].item() - 0.25) < 1e-8
    # Exact 3x factor verified
    assert abs(out["force_loss"].item() - 3.0 * out_coord["force_loss"].item()) < 1e-8
