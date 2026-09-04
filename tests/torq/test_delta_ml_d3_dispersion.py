import os
os.environ["JAX_ENABLE_X64"] = "True"

import pytest
import torch
from mendeleev import element

from cochem.ml.delta import DeltaMLDispersionConfig, DeltaMLEngine


def test_delta_ml_d3_dispersion_and_gradient_conservation():
    """Verify Delta-ML D3(BJ) dispersion augmentation, attractive R^-6 tail, and force conservation (Suggestion #60 / Method Matrix v4 §9A.5 [M], [D])."""
    # Dynamic Mendeleev check: Argon dimer
    ar = element("Ar")
    assert ar.atomic_number == 18
    z_list = [ar.atomic_number, ar.atomic_number]

    cfg = DeltaMLDispersionConfig(
        use_d3_dispersion=True,
        damping_scheme="bj",
        s6_scale=1.0,
        s8_scale=0.0,
    )
    engine = DeltaMLEngine(config=cfg)

    # 1. Separation scan across r in [3.0 A, 7.0 A]
    r_values = [3.0, 3.8, 4.5, 5.5, 7.0]
    energies = []
    for r in r_values:
        coords = torch.tensor([[0.0, 0.0, 0.0], [0.0, 0.0, float(r)]], dtype=torch.float64)
        e, _ = engine.compute_baseline(coords, z_list)
        energies.append(e)

    # In the attractive dispersion regime (r >= 3.8 A), energy must be negative
    for r, e in zip(r_values[1:], energies[1:]):
        assert e < 0.0, f"Dispersion energy at r={r} A must be attractive (negative), got {e}"

    # Verify R^-6 asymptotic decay: |E(4.5)| > |E(5.5)| > |E(7.0)|
    assert abs(energies[2]) > abs(energies[3]) > abs(energies[4])

    # 2. Analytical conservative force validation against two-point finite differences [M]
    r0 = 4.0
    h = 1e-5
    coords_0 = torch.tensor([[0.0, 0.0, 0.0], [0.0, 0.0, r0]], dtype=torch.float64)
    _, forces_analytic = engine.compute_baseline(coords_0, z_list)

    coords_plus = torch.tensor([[0.0, 0.0, 0.0], [0.0, 0.0, r0 + h]], dtype=torch.float64)
    e_plus, _ = engine.compute_baseline(coords_plus, z_list)

    coords_minus = torch.tensor([[0.0, 0.0, 0.0], [0.0, 0.0, r0 - h]], dtype=torch.float64)
    e_minus, _ = engine.compute_baseline(coords_minus, z_list)

    # Two-point central difference: F_z = -dE / dz
    fd_force_z = -(e_plus - e_minus) / (2.0 * h)
    analytic_force_z = forces_analytic[1, 2].item()

    force_error = abs(analytic_force_z - fd_force_z)
    # Must match to within 1e-4 eV/A [M]
    assert (
        force_error < 1e-4
    ), f"Analytic force error {force_error:.4e} exceeds 1e-4 eV/A threshold: analytic={analytic_force_z}, fd={fd_force_z}"
