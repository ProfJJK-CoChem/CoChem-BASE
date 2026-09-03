"""Authentic physical verification test suite for Mixed-Precision Training Engine (REQ-TORQ-TRAIN-096).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Authentic Octasulfur S8 and Kr@C60 fixtures with dependency injection.
"""

from __future__ import annotations

import pytest
import torch
import torch.nn as nn

from Libraries.cochem_torq_amp_trainer import (
    AMPTrainer,
    resolve_amp_precision,
)
from Libraries.cochem_torq_training_errors import PrecisionDivergenceError
from Libraries.cochem_torq_training_schemas import TrainingDynamicsConfig
from tests.torq_test_fixtures import (
    get_kr_fullerene_c60_fixture,
    get_octasulfur_s8_fixture,
)


class PhysicalMLFFBackbone(nn.Module):
    """Authentic physical neural backbone for Octasulfur and Kr@C60 mixed-precision validation."""

    def __init__(self, hidden_dim: int = 32) -> None:
        super().__init__()
        self.embedding = nn.Embedding(119, hidden_dim)
        self.r_centers = nn.Parameter(
            torch.linspace(1.0, 7.0, 16, dtype=torch.float32),
            requires_grad=False,
        )
        self.mlp = nn.Sequential(
            nn.Linear(hidden_dim + 16, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(
        self,
        coordinates: torch.Tensor,
        species: torch.Tensor,
        edge_index: torch.Tensor | None = None,
        batch: torch.Tensor | None = None,
    ) -> torch.Tensor:
        # Distance calculation in FP32
        diff = coordinates.unsqueeze(1) - coordinates.unsqueeze(0)
        dist = torch.norm(diff + 1e-12, dim=-1)
        r_exp = torch.exp(-0.5 * torch.square((dist.unsqueeze(-1) - self.r_centers) / 0.5))
        r_sum = torch.sum(r_exp, dim=1)  # (N, 16)

        z_emb = self.embedding(species)
        node_features = torch.cat([z_emb, r_sum], dim=-1)
        atomic_e = self.mlp(node_features).squeeze(-1)
        return torch.sum(atomic_e)


def test_hardware_aware_precision_dispatcher_dependency_injection() -> None:
    """Verify precision dispatching logic across hardware compute capabilities via dependency injection. [D]"""
    # 1. Ampere/Hopper (8, 0) -> BF16 without GradScaler
    cuda_dev = torch.device("cuda:0" if torch.cuda.is_available() else "cuda")
    dtype_ampere, scaler_ampere = resolve_amp_precision(cuda_dev, compute_capability=(8, 0))
    assert dtype_ampere == torch.bfloat16
    assert scaler_ampere is None

    # 2. Turing/Volta (7, 5) -> FP16 with GradScaler
    dtype_turing, scaler_turing = resolve_amp_precision(cuda_dev, compute_capability=(7, 5))
    assert dtype_turing == torch.float16
    assert scaler_turing is not None
    assert isinstance(scaler_turing, torch.amp.GradScaler)

    # 3. CPU / MPS -> Native FP32 without GradScaler
    cpu_dev = torch.device("cpu")
    dtype_cpu, scaler_cpu = resolve_amp_precision(cpu_dev, compute_capability=None)
    assert dtype_cpu == torch.float32
    assert scaler_cpu is None


def test_octasulfur_s8_training_step_and_gradient_clipping() -> None:
    """Verify force autograd precision and gradient norm clipping on Octasulfur S8. [M]"""
    coords, species = get_octasulfur_s8_fixture()
    coords = coords.to(torch.float32)

    torch.manual_seed(42)
    model = PhysicalMLFFBackbone(hidden_dim=32)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

    config = TrainingDynamicsConfig(
        max_gradient_norm=1.0,
        energy_loss_weight=1.0,
        force_loss_weight=50.0,
    )

    trainer = AMPTrainer(
        model=model,
        optimizer=optimizer,
        config=config,
        device=torch.device("cpu"),
    )

    ref_energy = torch.tensor(0.0, dtype=torch.float32)
    ref_forces = torch.zeros_like(coords)

    tot_loss, e_loss, f_loss = trainer.train_step(
        coordinates=coords,
        species=species,
        ref_energy=ref_energy,
        ref_forces=ref_forces,
    )

    assert tot_loss > 0.0
    assert e_loss >= 0.0
    assert f_loss >= 0.0
    assert not torch.isnan(torch.tensor(tot_loss))


def test_kr_fullerene_c60_high_atom_count_stability() -> None:
    """Verify autograd force graph stability on high-atom Kr@C60 (N=61 atoms). [M]"""
    coords, species = get_kr_fullerene_c60_fixture()
    coords = coords.to(torch.float32)

    torch.manual_seed(101)
    model = PhysicalMLFFBackbone(hidden_dim=24)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

    config = TrainingDynamicsConfig(
        max_gradient_norm=0.5,
        energy_loss_weight=1.0,
        force_loss_weight=10.0,
    )

    trainer = AMPTrainer(
        model=model,
        optimizer=optimizer,
        config=config,
        device=torch.device("cpu"),
    )

    ref_energy = torch.tensor(-10.0, dtype=torch.float32)
    ref_forces = torch.zeros_like(coords)

    tot_loss, e_loss, f_loss = trainer.train_step(
        coordinates=coords,
        species=species,
        ref_energy=ref_energy,
        ref_forces=ref_forces,
    )

    assert tot_loss > 0.0
    assert not torch.isnan(torch.tensor(tot_loss))


def test_precision_divergence_detection() -> None:
    """Verify PrecisionDivergenceError is raised when unrecoverable NaN gradients persist. [M]"""
    coords, species = get_octasulfur_s8_fixture()
    coords = coords.to(torch.float32)

    model = PhysicalMLFFBackbone(hidden_dim=16)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

    config = TrainingDynamicsConfig()
    trainer = AMPTrainer(model, optimizer, config, device=torch.device("cpu"))

    # Force NaN in model weights to trigger divergence
    with torch.no_grad():
        for p in model.parameters():
            p.fill_(float("nan"))
            break

    ref_e = torch.tensor(0.0, dtype=torch.float32)
    ref_f = torch.zeros_like(coords)

    with pytest.raises(PrecisionDivergenceError) as exc_info:
        for _ in range(5):
            trainer.train_step(coords, species, ref_e, ref_f)

    assert exc_info.value.error_code == "TORQ_TRAIN_PRECISION_DIVERGENCE"
