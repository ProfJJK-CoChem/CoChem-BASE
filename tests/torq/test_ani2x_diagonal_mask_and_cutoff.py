"""Zero-mock unit test for Diagonal Self-Interaction Masking & C^2 Quintic Cutoff Envelope in ANI-2x.

SRS Chunk 14 / Suggestion #132 / Method Matrix v4 §9A, §10.2 [M], [D].
Zero-Mock Mandate v3: Authentic diatomic H2 and single atom H calculations.
"""

from __future__ import annotations

import torch
from Libraries.cochem_torq_ani2x_transfer import (
    BASE_ANI2X_SPECIES,
    ANI2xModel,
)

from cochem_base.schemas import ANI2xCutoffConfig


def test_ani2x_single_atom_zero_self_interaction_smearing() -> None:
    """Verify single atom evaluates with zero self-interaction smearing (r_ii masked) [M]."""
    model = ANI2xModel(
        species_list=BASE_ANI2X_SPECIES,
        feature_dim_per_species=16,
        cutoff_config=ANI2xCutoffConfig(mask_self_interactions=True, envelope_type="quintic", cutoff_radius=5.2),
    )
    model.eval()

    # Single isolated Hydrogen atom
    coords = torch.tensor([[0.0, 0.0, 0.0]], dtype=torch.float64)
    species = torch.tensor([1], dtype=torch.long)

    # In single atom, pairwise off-diagonal distance tensor is empty; projection features must be zero
    energy = model(coords, species)
    assert not torch.isnan(energy)
    assert not torch.isinf(energy)

    # Gradient of isolated single atom must be strictly zero vector
    coords_grad = coords.clone().detach().requires_grad_(True)
    e = model(coords_grad, species)
    grad = torch.autograd.grad(e, coords_grad)[0]
    assert torch.allclose(grad, torch.zeros_like(grad), atol=1e-12)


def test_ani2x_c2_quintic_cutoff_continuity_and_smoothness() -> None:
    """Verify C^2 quintic polynomial envelope smoothly approaches zero energy and forces at Rc = 5.2 A [M], [D]."""
    rc = 5.2
    model = ANI2xModel(
        species_list=BASE_ANI2X_SPECIES,
        feature_dim_per_species=16,
        cutoff_config=ANI2xCutoffConfig(mask_self_interactions=True, envelope_type="quintic", cutoff_radius=rc),
    ).to(torch.float64)
    model.eval()

    species = torch.tensor([1, 1], dtype=torch.long)  # H2 diatomic

    # Test points right below, at, and beyond Rc
    r_inside = rc - 0.01
    r_at = rc
    r_outside = rc + 0.50

    coords_inside = torch.tensor([[0.0, 0.0, 0.0], [0.0, 0.0, r_inside]], dtype=torch.float64, requires_grad=True)
    coords_at = torch.tensor([[0.0, 0.0, 0.0], [0.0, 0.0, r_at]], dtype=torch.float64, requires_grad=True)
    coords_outside = torch.tensor([[0.0, 0.0, 0.0], [0.0, 0.0, r_outside]], dtype=torch.float64, requires_grad=True)

    e_inside = model(coords_inside, species)
    f_inside = -torch.autograd.grad(e_inside, coords_inside)[0]

    e_at = model(coords_at, species)
    f_at = -torch.autograd.grad(e_at, coords_at)[0]

    e_outside = model(coords_outside, species)
    f_outside = -torch.autograd.grad(e_outside, coords_outside)[0]

    # At R = Rc and R > Rc, cutoff envelope evaluates to 0.0, so interaction energy and forces vanish
    # and match 2 isolated single atoms exactly
    single_atom_coords = torch.tensor([[0.0, 0.0, 0.0]], dtype=torch.float64)
    single_e = model(single_atom_coords, torch.tensor([1], dtype=torch.long)).item()
    two_atoms_isolated_e = 2.0 * single_e

    assert abs(e_at.item() - two_atoms_isolated_e) < 1e-6
    assert abs(e_outside.item() - two_atoms_isolated_e) < 1e-8

    # Analytical forces vanish continuously at and beyond Rc
    assert torch.allclose(f_at, torch.zeros_like(f_at), atol=1e-5)
    assert torch.allclose(f_outside, torch.zeros_like(f_outside), atol=1e-10)

    # Verify C^2 value continuity: |f_inside| -> 0 smoothly as R -> Rc
    assert torch.max(torch.abs(f_inside)).item() < 0.1
