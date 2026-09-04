"""Physical verification suite for Grimme D3 Empirical Dispersion Layer.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic physics, dynamic Mendeleev radii, and autograd forces.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from Libraries.cochem_torq_dispersion_d3 import (
    CANONICAL_DISPERSION_SHA256,
    DispersionD3Layer,
    compute_coordination_numbers,
)
from Libraries.cochem_torq_inference_errors import DispersionParameterError
from Libraries.cochem_torq_inference_schemas import DispersionD3Config

# Authentic Water Dimer ((H2O)2, Cs symmetry, Global Minimum)
WATER_DIMER_COORDS = np.array(
    [
        [-1.48800000, -0.01200000, 0.00000000],  # O1 (donor)
        [-1.86700000, 0.86500000, 0.00000000],  # H1
        [-0.52800000, 0.08800000, 0.00000000],  # H2 (bound)
        [1.42700000, 0.11000000, 0.00000000],  # O2 (acceptor)
        [1.76500000, -0.39500000, -0.75700000],  # H3
        [1.76500000, -0.39500000, 0.75700000],  # H4
    ],
    dtype=np.float64,
)
WATER_DIMER_Z = [8, 1, 1, 8, 1, 1]

# Authentic Ethanol (C2H5OH, trans-conformer)
ETHANOL_COORDS = np.array(
    [
        [0.0072, 0.4578, 0.0000],  # C1
        [1.2486, -0.4136, 0.0000],  # C2
        [-1.1718, -0.3702, 0.0000],  # O
        [-0.0435, 1.1074, 0.8879],  # H1
        [-0.0435, 1.1074, -0.8879],  # H2
        [1.2847, -1.0538, 0.8879],  # H3
        [1.2847, -1.0538, -0.8879],  # H4
        [2.1524, 0.2018, 0.0000],  # H5
        [-1.9754, 0.1652, 0.0000],  # H6 (OH)
    ],
    dtype=np.float64,
)
ETHANOL_Z = [6, 6, 8, 1, 1, 1, 1, 1, 1]


def test_dispersion_coordination_numbers_dynamic_mendeleev() -> None:
    """Compute coordination numbers CN_A using Mendeleev covalent radii and assert physical sanity. [M]"""
    coords_w = torch.tensor(WATER_DIMER_COORDS, dtype=torch.float64)
    cn_w = compute_coordination_numbers(coords_w, WATER_DIMER_Z)

    assert cn_w.shape == (6,)
    assert torch.all(cn_w > 0.0)
    # Oxygen atoms (indices 0 and 3) should have higher coordination than Hydrogens (1, 2, 4, 5)
    assert cn_w[0] > cn_w[1]
    assert cn_w[0] > cn_w[2]
    assert cn_w[3] > cn_w[4]
    assert cn_w[3] > cn_w[5]

    # Ethanol coordination
    coords_eth = torch.tensor(ETHANOL_COORDS, dtype=torch.float64)
    cn_eth = compute_coordination_numbers(coords_eth, ETHANOL_Z)
    assert cn_eth.shape == (9,)
    assert torch.all(cn_eth > 0.0)
    # Carbons (indices 0, 1) have 4 covalent partners > Oxygen (index 2) with 2 partners > Hydrogens (indices 3-8) with 1 partner
    assert cn_eth[0] > cn_eth[2]
    assert cn_eth[1] > cn_eth[2]
    assert cn_eth[2] > torch.max(cn_eth[3:])


def test_dispersion_autograd_forces_finite_differences() -> None:
    """Autograd Conservative Force Test: assert analytical forces match numerical central differences within 1e-4. [D]"""
    config = DispersionD3Config(data_manifest_sha256=CANONICAL_DISPERSION_SHA256)
    layer = DispersionD3Layer(config)

    coords = torch.tensor(WATER_DIMER_COORDS, dtype=torch.float64)
    e_analytical, f_analytical = layer.compute_energy_and_forces(
        coords, WATER_DIMER_Z
    )

    # Central finite differences
    h = 1e-5
    f_numerical = torch.zeros_like(coords)
    N = coords.shape[0]

    for i in range(N):
        for alpha in range(3):
            coords_plus = coords.clone()
            coords_plus[i, alpha] += h
            e_plus, _ = layer.compute_energy_and_forces(
                coords_plus, WATER_DIMER_Z
            )

            coords_minus = coords.clone()
            coords_minus[i, alpha] -= h
            e_minus, _ = layer.compute_energy_and_forces(
                coords_minus, WATER_DIMER_Z
            )

            # F = -dE / dR
            f_num = -(e_plus.item() - e_minus.item()) / (2.0 * h)
            f_numerical[i, alpha] = f_num

    # Relative difference check
    abs_diff = torch.abs(f_analytical - f_numerical)
    rel_diff = abs_diff / (torch.abs(f_analytical) + 1e-6)
    max_rel_error = float(torch.max(rel_diff).item())

    assert max_rel_error < 1e-4, f"Max relative difference {max_rel_error} exceeds 1e-4 tolerance"


def test_dispersion_translational_and_rotational_invariance() -> None:
    r"""Verify physical invariants: sum_i F_disp,i == 0 and sum_i r_i x F_disp,i == 0 within 1e-6. [D]"""
    layer = DispersionD3Layer()
    for name, raw_coords, z in [
        ("Water Dimer", WATER_DIMER_COORDS, WATER_DIMER_Z),
        ("Ethanol", ETHANOL_COORDS, ETHANOL_Z),
    ]:
        coords = torch.tensor(raw_coords, dtype=torch.float64)
        _, f_disp = layer.compute_energy_and_forces(coords, z)

        # 1. Net translational force
        net_f = torch.norm(torch.sum(f_disp, dim=0)).item()
        assert net_f < 1e-6, f"{name}: Net dispersion force {net_f} exceeds 1e-6 eV/A"

        # 2. Net rotational torque
        net_torque = torch.norm(
            torch.sum(torch.cross(coords, f_disp, dim=-1), dim=0)
        ).item()
        assert net_torque < 1e-6, f"{name}: Net dispersion torque {net_torque} exceeds 1e-6 eV"


def test_dispersion_parameter_table_sha256_verification() -> None:
    """Assert corrupted parameter table hash triggers DispersionParameterError. [M]"""
    corrupt_sha = "deadbeef" * 8
    corrupt_config = DispersionD3Config(data_manifest_sha256=corrupt_sha)

    with pytest.raises(DispersionParameterError) as exc_info:
        DispersionD3Layer(corrupt_config)

    assert exc_info.value.error_code == "TORQ_DISPERSION_PARAM_CORRUPT"
    assert exc_info.value.component == "dispersion_layer"
    assert exc_info.value.diagnostics["expected_sha256"] == corrupt_sha
    assert (
        exc_info.value.diagnostics["calculated_sha256"]
        == CANONICAL_DISPERSION_SHA256
    )
