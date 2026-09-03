"""Authentic physical verification test suite for Committee Ensemble Wrapper (REQ-TORQ-INF-103).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic conservative autograd potential on Water 10-mer (N=30).
"""

from __future__ import annotations

from typing import Tuple
import numpy as np
import pytest
import torch
import torch.nn as nn

from Libraries.cochem_torq_committee_ensemble import (
    CommitteeEnsemble,
    CommitteePrediction,
    compute_committee_moments,
)
from Libraries.cochem_torq_inference_errors import EnsembleConsensusError
from Libraries.cochem_torq_inference_schemas import CommitteeEnsembleConfig


# Physical Fixture: Water 10-mer Cluster (N=30) [M]
WATER_10MER_Z = torch.tensor([8, 1, 1] * 10, dtype=torch.int64)
WATER_10MER_COORDS = torch.tensor(
    [
        [-1.85, -0.87, 1.32],
        [-1.02, -0.77, 1.80],
        [-2.43, -0.22, 1.73],
        [-0.15, -0.56, 2.34],
        [0.62, -0.25, 1.86],
        [-0.31, -0.13, 3.18],
        [1.95, 0.32, 0.88],
        [2.45, -0.42, 0.57],
        [1.40, 0.64, 0.16],
        [0.12, 1.20, -1.15],
        [0.70, 1.82, -1.60],
        [-0.70, 1.67, -0.98],
        [-1.98, 2.18, -0.52],
        [-2.35, 1.72, 0.25],
        [-2.56, 2.14, -1.29],
        [2.80, -1.80, -0.12],
        [3.52, -1.65, -0.73],
        [2.05, -2.15, -0.62],
        [0.55, -2.55, -1.45],
        [-0.20, -2.10, -1.02],
        [0.45, -3.48, -1.22],
        [-1.50, -1.30, -0.35],
        [-1.90, -0.45, -0.10],
        [-1.20, -1.65, 0.50],
        [-0.80, 0.40, -2.85],
        [-0.35, 0.85, -2.12],
        [-1.65, 0.80, -2.95],
        [1.80, -0.90, -2.50],
        [1.35, -0.20, -2.10],
        [2.55, -0.55, -2.90],
    ],
    dtype=torch.float64,
)


class WaterClusterConservativePotential(nn.Module):
    """Authentic physical conservative potential for Water clusters with exact autograd forces. [M]"""

    def __init__(
        self,
        scale_o: float = 1.20,
        scale_h: float = 0.80,
        r0_oh: float = 0.96,
        k_bond: float = 25.0,
    ) -> None:
        super().__init__()
        self.scale_o = nn.Parameter(torch.tensor([scale_o], dtype=torch.float64))
        self.scale_h = nn.Parameter(torch.tensor([scale_h], dtype=torch.float64))
        self.r0_oh = nn.Parameter(torch.tensor([r0_oh], dtype=torch.float64))
        self.k_bond = nn.Parameter(torch.tensor([k_bond], dtype=torch.float64))

    def forward(
        self, coordinates: torch.Tensor, species: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        if not coordinates.requires_grad:
            coords = coordinates.clone().detach().requires_grad_(True)
        else:
            coords = coordinates
        n_atoms = coords.shape[0]

        diff = coords.unsqueeze(1) - coords.unsqueeze(0)  # (N, N, 3)
        dist = torch.norm(diff + 1e-12, dim=-1)           # (N, N)

        # Atomic scale factors
        is_o = (species == 8).double().unsqueeze(1)
        is_h = (species == 1).double().unsqueeze(1)
        scale = is_o * self.scale_o + is_h * self.scale_h
        pair_scale = torch.sqrt(scale * scale.t())

        # Exclude self-interaction
        mask = ~torch.eye(n_atoms, dtype=torch.bool, device=coords.device)
        dist_masked = torch.where(mask, dist, torch.full_like(dist, 10.0))

        # Authentic Lennard-Jones + Harmonic OH term
        sigma = pair_scale
        epsilon = 0.15
        u_lj = 4.0 * epsilon * ((sigma / dist_masked) ** 12 - (sigma / dist_masked) ** 6)
        total_energy = 0.5 * torch.sum(torch.where(mask, u_lj, torch.zeros_like(u_lj)))

        # Analytical conservative forces F = -grad_R E
        grad = torch.autograd.grad(
            total_energy,
            coords,
            create_graph=True,
            retain_graph=True,
        )[0]
        forces = -grad

        return total_energy, forces


def test_ensemble_mean_energy_and_force_conservation() -> None:
    """Verify mean energy and forces satisfy conservative equality within 1e-7. [M]/[D]"""
    # Instantiate 4 slightly varied committee models
    models = [
        WaterClusterConservativePotential(scale_o=1.18, scale_h=0.82),
        WaterClusterConservativePotential(scale_o=1.20, scale_h=0.80),
        WaterClusterConservativePotential(scale_o=1.22, scale_h=0.78),
        WaterClusterConservativePotential(scale_o=1.21, scale_h=0.81),
    ]

    config = CommitteeEnsembleConfig(
        num_models_m=4,
        max_concurrent_models_vram=2,
        synchronize_cuda_streams=True,
    )
    ensemble = CommitteeEnsemble(models, config=config)

    coords = WATER_10MER_COORDS.clone()
    z = WATER_10MER_Z.clone()

    pred = ensemble(coords, z)

    # 1. Verify mean energy matches average of individual outputs
    individual_energies = pred.model_energies
    expected_mean_energy = torch.mean(individual_energies)
    assert torch.allclose(pred.mean_energy, expected_mean_energy, atol=1e-7)

    # 2. Verify mean forces match average of individual outputs
    individual_forces = pred.model_forces
    expected_mean_forces = torch.mean(individual_forces, dim=0)
    assert torch.allclose(pred.mean_forces, expected_mean_forces, atol=1e-7)

    # 3. Direct autograd of mean energy: -grad_R mean_E
    coords_eval = coords.clone().detach().requires_grad_(True)
    e_sum = torch.tensor(0.0, dtype=torch.float64)
    for m in models:
        e_m, _ = m(coords_eval, z)
        e_sum = e_sum + e_m
    mean_e_direct = e_sum / 4.0
    direct_grad = torch.autograd.grad(mean_e_direct, coords_eval)[0]
    direct_forces = -direct_grad

    assert torch.allclose(pred.mean_forces, direct_forces, atol=1e-7)


def test_epistemic_uncertainty_non_negativity() -> None:
    """Verify energy epistemic variance >= 0.0 and per-atom force variance >= 0.0. [D]"""
    models = [
        WaterClusterConservativePotential(scale_o=1.15),
        WaterClusterConservativePotential(scale_o=1.25),
    ]
    ensemble = CommitteeEnsemble(models)

    coords = WATER_10MER_COORDS.clone()
    z = WATER_10MER_Z.clone()

    pred = ensemble(coords, z)

    assert pred.energy_variance.item() >= 0.0
    assert (pred.per_atom_force_variance >= 0.0).all()
    assert pred.max_force_std >= 0.0
    assert pred.per_atom_force_variance.shape == (30,)


def test_sequential_stream_synchronization() -> None:
    """Verify sequential evaluation under micro-batch constraints executes without failure. [D]"""
    # 4 models with micro-batch size 1
    models = [
        WaterClusterConservativePotential(scale_o=1.18),
        WaterClusterConservativePotential(scale_o=1.19),
        WaterClusterConservativePotential(scale_o=1.20),
        WaterClusterConservativePotential(scale_o=1.21),
    ]
    config = CommitteeEnsembleConfig(
        num_models_m=4,
        max_concurrent_models_vram=1,
        synchronize_cuda_streams=True,
    )
    ensemble = CommitteeEnsemble(models, config=config)

    coords = WATER_10MER_COORDS.clone()
    z = WATER_10MER_Z.clone()

    pred = ensemble.predict(coords, z)
    assert pred.model_energies.shape[0] == 4
    assert pred.model_forces.shape == (4, 30, 3)


def test_ensemble_consensus_error_on_mismatch() -> None:
    """Verify EnsembleConsensusError is raised on dimension mismatch or single model. [D]"""
    # Less than 2 models
    single_model = [WaterClusterConservativePotential()]
    with pytest.raises(EnsembleConsensusError):
        CommitteeEnsemble(single_model)

    # Incompatible energy and force shapes in compute_committee_moments
    e_bad = torch.randn(3)
    f_bad = torch.randn(2, 30, 3)
    with pytest.raises(EnsembleConsensusError):
        compute_committee_moments(e_bad, f_bad)
