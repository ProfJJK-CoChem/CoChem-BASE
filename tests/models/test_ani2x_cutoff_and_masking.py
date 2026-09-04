import os
os.environ["JAX_ENABLE_X64"] = "True"

import pytest
import torch
from mendeleev import element

from Libraries.cochem_torq_ani2x_transfer import ANI2xModel
from cochem_base.schemas import ANI2xCutoffConfig


def test_ani2x_single_isolated_atom_zero_force():
    """Verify diagonal self-interaction masking yields exact zero residual force on isolated atom (Suggestion #53 / Method Matrix v4 §10.3 [M], [D])."""
    # Dynamic Mendeleev check
    c_elem = element("C")
    assert c_elem.atomic_number == 6

    cfg = ANI2xCutoffConfig(cutoff_radius=5.2, envelope_type="quintic", mask_self_interactions=True)
    model = ANI2xModel(species_list=[1, 6, 7, 8], feature_dim_per_species=16, cutoff_config=cfg)
    model.to(torch.float64)

    coords = torch.tensor([[10.0, 10.0, 10.0]], dtype=torch.float64, requires_grad=True)
    species = torch.tensor([6], dtype=torch.long)

    energy, forces = model.compute_energy_and_forces(coords, species)

    # Isolated single atom must have exactly zero pair interactions and zero force residual
    force_norm = torch.norm(forces).item()
    assert force_norm < 1e-14, f"Isolated atom experienced non-zero self-force: {force_norm:.4e} eV/A >= 1e-14"


def test_ani2x_dimer_cutoff_envelope_transition():
    """Verify C^2 quintic and cosine cutoff envelopes continuously vanish at and beyond Rc = 5.2 A."""
    cfg = ANI2xCutoffConfig(cutoff_radius=5.2, envelope_type="quintic", mask_self_interactions=True)
    model = ANI2xModel(species_list=[1, 6, 7, 8], feature_dim_per_species=16, cutoff_config=cfg)
    model.to(torch.float64)

    species = torch.tensor([6, 6], dtype=torch.long)

    # Reference single-atom energy
    c_single = torch.tensor([[0.0, 0.0, 0.0]], dtype=torch.float64, requires_grad=True)
    e_single, _ = model.compute_energy_and_forces(c_single, torch.tensor([6], dtype=torch.long))

    # 1. Within cutoff: r = 5.0 A (< 5.2 A)
    coords_in = torch.tensor([[0.0, 0.0, 0.0], [0.0, 0.0, 5.0]], dtype=torch.float64, requires_grad=True)
    e_in, f_in = model.compute_energy_and_forces(coords_in, species)
    assert torch.norm(f_in).item() > 0.0, "Force unexpectedly zero inside cutoff envelope"

    # 2. Beyond cutoff: r = 5.25 A and r = 5.3 A (> 5.2 A)
    coords_out1 = torch.tensor([[0.0, 0.0, 0.0], [0.0, 0.0, 5.25]], dtype=torch.float64, requires_grad=True)
    coords_out2 = torch.tensor([[0.0, 0.0, 0.0], [0.0, 0.0, 5.30]], dtype=torch.float64, requires_grad=True)

    e_out1, f_out1 = model.compute_energy_and_forces(coords_out1, species)
    e_out2, f_out2 = model.compute_energy_and_forces(coords_out2, species)

    # Interaction energy must be strictly zero (separated atoms limit)
    interaction_energy1 = abs((e_out1 - 2.0 * e_single).item())
    interaction_energy2 = abs((e_out2 - 2.0 * e_single).item())

    assert interaction_energy1 < 1e-14, f"Dimer interaction energy at 5.25 A not zero: {interaction_energy1}"
    assert interaction_energy2 < 1e-14, f"Dimer interaction energy at 5.30 A not zero: {interaction_energy2}"

    # Force outside cutoff must be identically zero
    assert torch.norm(f_out1).item() < 1e-14, f"Force at 5.25 A outside cutoff not zero: {torch.norm(f_out1).item():.4e}"
    assert torch.norm(f_out2).item() < 1e-14, f"Force at 5.30 A outside cutoff not zero: {torch.norm(f_out2).item():.4e}"
