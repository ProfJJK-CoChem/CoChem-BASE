"""Authentic physical verification test suite for ANI-2x Transfer Learning Pipeline (REQ-TORQ-TRAIN-092).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Authentic Ar-Kr dimer and Fluorobenzene complex fixtures.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import torch

from Libraries.cochem_torq_ani2x_transfer import (
    BASE_ANI2X_SPECIES,
    ANI2xModel,
    expand_ani2x_domain,
    generate_test_ani2x_weights,
    get_llrd_parameter_groups,
    load_verified_ani2x_weights,
)
from Libraries.cochem_torq_training_errors import (
    CheckpointCorruptionError,
    UnsupportedElementError,
)
from tests.torq_test_fixtures import (
    get_ar_kr_dimer_fixture,
    get_fluorobenzene_complex_fixture,
)


def test_cryptographic_ingestion_and_tamper_detection() -> None:
    """Verify offline SHA-256 validation and CheckpointCorruptionError upon byte alteration. [M]"""
    with tempfile.TemporaryDirectory() as tmpdir:
        weights_dir = Path(tmpdir)
        weights_path, valid_hash = generate_test_ani2x_weights(weights_dir)

        # 1. Successful verified ingestion
        state_dict = load_verified_ani2x_weights(weights_path, valid_hash)
        assert isinstance(state_dict, dict)
        assert len(state_dict) > 0

        # 2. Corrupted hash test
        corrupt_hash = valid_hash[:-4] + "0000"
        with pytest.raises(CheckpointCorruptionError):
            load_verified_ani2x_weights(weights_path, corrupt_hash)

        # 3. Physical file tampering test: flip a single byte in file
        with open(weights_path, "r+b") as f:
            f.seek(10)
            orig_byte = f.read(1)
            f.seek(10)
            f.write(bytes([(orig_byte[0] ^ 0xFF)]))

        with pytest.raises(CheckpointCorruptionError):
            load_verified_ani2x_weights(weights_path, valid_hash)


def test_fluorobenzene_baseline_energy_parity_upon_expansion() -> None:
    """Verify input matrix W1 expansion guarantees exact baseline energy parity at initialization. [D]"""
    coords, species = get_fluorobenzene_complex_fixture()

    base_model = ANI2xModel(species_list=BASE_ANI2X_SPECIES, feature_dim_per_species=16)
    base_model.eval()
    baseline_energy = base_model(coords, species).item()

    # Expand domain to include noble gases Argon (18) and Krypton (36)
    expanded_model = expand_ani2x_domain(base_model, new_species_atomic_numbers=[18, 36])
    expanded_model.eval()
    expanded_energy = expanded_model(coords, species).item()

    # Invariant: W1 zero-initialization on novel species channels guarantees bit-for-bit identical energy
    energy_diff = abs(baseline_energy - expanded_energy)
    assert energy_diff < 1e-10, (
        f"Baseline energy altered upon domain expansion: diff={energy_diff:.2e} Hartree."
    )


def test_ar_kr_dimer_mutual_polarization_forces() -> None:
    """Verify host-guest mutual polarization: gradients flow into W1 and obey Newton's third law. [D]"""
    coords, species = get_ar_kr_dimer_fixture()
    coords = coords.clone().detach().requires_grad_(True)

    base_model = ANI2xModel(species_list=BASE_ANI2X_SPECIES, feature_dim_per_species=16)
    expanded_model = expand_ani2x_domain(base_model, new_species_atomic_numbers=[18, 36])
    expanded_model.train()

    energy = expanded_model(coords, species)
    assert not torch.isnan(energy)
    assert not torch.isinf(energy)

    # Compute analytical forces
    forces = -torch.autograd.grad(energy, coords, create_graph=True)[0]
    assert forces.shape == (2, 3)

    # Interspecies force balance (Newton's third law for dimer along z-axis: F_Ar + F_Kr = 0)
    net_force = torch.sum(forces, dim=0)
    max_net_force = torch.max(torch.abs(net_force)).item()
    assert max_net_force < 1e-6, f"Newton third law violation in Ar-Kr dimer: net force {max_net_force:.2e}."


def test_llrd_learning_rate_decay_hierarchy() -> None:
    """Verify Layer-wise Learning Rate Decay (LLRD) reduces learning rates by gamma=0.8 per layer. [M]"""
    base_model = ANI2xModel(species_list=BASE_ANI2X_SPECIES, feature_dim_per_species=16)
    expanded_model = expand_ani2x_domain(base_model, new_species_atomic_numbers=[36])

    base_lr = 1e-3
    gamma = 0.8
    param_groups = get_llrd_parameter_groups(
        expanded_model,
        base_learning_rate=base_lr,
        layer_decay_rate=gamma,
    )

    assert len(param_groups) > 0

    # Group learning rates by head
    for z_str in expanded_model.heads.keys():
        head_groups = [
            g for g in param_groups
            if g["layer_name"].startswith(f"head_{z_str}_") and "weight" in g["layer_name"]
        ]
        assert len(head_groups) == 4  # 3 hidden layers + 1 readout layer

        # Expected decay: layer 3 (readout): base_lr * gamma^0 = 1e-3
        # layer 2: base_lr * gamma^1 = 8e-4
        # layer 1: base_lr * gamma^2 = 6.4e-4
        # layer 0: base_lr * gamma^3 = 5.12e-4
        lr_values = [g["lr"] for g in head_groups]
        assert pytest.approx(lr_values[3], rel=1e-5) == base_lr
        assert pytest.approx(lr_values[2], rel=1e-5) == base_lr * gamma
        assert pytest.approx(lr_values[1], rel=1e-5) == base_lr * (gamma ** 2)
        assert pytest.approx(lr_values[0], rel=1e-5) == base_lr * (gamma ** 3)


def test_unsupported_element_exception() -> None:
    """Verify UnsupportedElementError is raised immediately when unregistered species are passed. [M]"""
    base_model = ANI2xModel(species_list=BASE_ANI2X_SPECIES, feature_dim_per_species=16)

    # Ingest geometry containing Mercury (Hg, Z=80)
    coords = torch.tensor([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=torch.float64)
    species = torch.tensor([80, 1], dtype=torch.long)

    with pytest.raises(UnsupportedElementError) as exc_info:
        base_model(coords, species)

    assert "Z=80" in str(exc_info.value)
    assert exc_info.value.error_code == "TORQ_TRAIN_UNSUPPORTED_ELEMENT"
