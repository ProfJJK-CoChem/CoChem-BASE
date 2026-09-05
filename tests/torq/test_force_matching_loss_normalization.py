"""Zero-mock unit test for Dimension-Normalized Vector-Norm Huber Force Loss & Parity Balancing.

SRS Chunk 14 / Suggestion #134 / Method Matrix v4 §10.3, Table 2 (Row T2-12h) [M], [D].
Zero-Mock Mandate v3: Completely authentic mathematical tensors and physical force gradients.
"""

from __future__ import annotations

import torch
from Libraries.cochem_torq_force_matching import (
    ForceMatchingLoss,
    ForceMatchingLossConfig,
    huber_force_loss,
)


def test_force_matching_loss_normalization_and_parity() -> None:
    """Verify vector-norm Huber force loss divides strictly by total_atoms and maintains parity [M], [D]."""
    w_f = 50.0  # within mandated 10--100 A^2
    config = ForceMatchingLossConfig(
        energy_weight=1.0,
        force_weight=w_f,
        normalization_mode="atom_norm",
        huber_delta_force=0.05,
    )
    loss_module = ForceMatchingLoss(config)

    # 2 molecules: mol 1 has 5 atoms, mol 2 has 10 atoms -> total 15 atoms
    n_atoms_seq = [5, 10]
    total_atoms = 15

    pred_e = torch.tensor([[-50.0], [-100.0]], dtype=torch.float64)
    true_e = torch.tensor([[-50.01], [-100.02]], dtype=torch.float64)

    # Pred and target forces for 15 total atoms
    true_f = torch.zeros(total_atoms, 3, dtype=torch.float64)
    # Set known error of 0.01 on all atoms
    pred_f = true_f + 0.01

    loss_dict = loss_module(
        pred_energy=pred_e,
        target_energy=true_e,
        pred_forces=pred_f,
        target_forces=true_f,
        num_atoms=n_atoms_seq,
    )

    unweighted_f_loss = loss_dict["unweighted_force_loss"]
    total_loss = loss_dict["loss"]
    assert total_loss.item() > 0.0

    # In vector norm mode: error vector is [0.01, 0.01, 0.01]
    single_err = torch.tensor([[0.01, 0.01, 0.01]], dtype=torch.float64)
    expected_unweighted_f = huber_force_loss(single_err, delta_f=0.05).item()

    assert abs(unweighted_f_loss.item() - expected_unweighted_f) < 1e-8, (
        f"Loss denominator mismatch: expected {expected_unweighted_f}, got {unweighted_f_loss.item()}"
    )

    # Verify parity: weighted force loss = w_f * unweighted_f_loss
    assert abs(loss_dict["weighted_force_loss"].item() - w_f * expected_unweighted_f) < 1e-8


def test_force_matching_invariance_to_atom_count_replication() -> None:
    """Verify that duplicating an identical system scales loss by per-atom invariant mean [D]."""
    config = ForceMatchingLossConfig(normalization_mode="atom_norm")
    loss_fn = ForceMatchingLoss(config)

    # System 1: 4 atoms
    pred_e1 = torch.tensor([-20.0], dtype=torch.float64)
    true_e1 = torch.tensor([-20.0], dtype=torch.float64)
    f_err = torch.tensor([[0.02, -0.01, 0.03]] * 4, dtype=torch.float64)
    true_f1 = torch.zeros(4, 3, dtype=torch.float64)
    pred_f1 = true_f1 + f_err

    out1 = loss_fn(pred_e1, true_e1, pred_f1, true_f1, num_atoms=[4])

    # System 2: 8 atoms with same error per atom
    pred_e2 = torch.tensor([-40.0], dtype=torch.float64)
    true_e2 = torch.tensor([-40.0], dtype=torch.float64)
    true_f2 = torch.zeros(8, 3, dtype=torch.float64)
    pred_f2 = true_f2 + torch.cat([f_err, f_err], dim=0)

    out2 = loss_fn(pred_e2, true_e2, pred_f2, true_f2, num_atoms=[8])

    # Force loss must be invariant to system size when per-atom errors are identical
    assert abs(out1["force_loss"].item() - out2["force_loss"].item()) < 1e-8
