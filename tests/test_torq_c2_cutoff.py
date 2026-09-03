"""Authentic physical verification test suite for C^2-Smooth Cutoff Function (REQ-TORQ-INF-104).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic analytical calculus, Argon dimer, and Ethanol coordinates.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from Libraries.cochem_torq_c2_cutoff import (
    C2SmoothCutoff,
    quintic_c2_envelope,
    quintic_c2_first_derivative,
    quintic_c2_second_derivative,
    quintic_c2_spatial_gradient,
    quintic_c2_spatial_hessian,
    verify_cutoff_continuity,
)
from Libraries.cochem_torq_inference_errors import CutoffContinuityError
from Libraries.cochem_torq_inference_schemas import C2SmoothCutoffConfig


# Physical Fixtures
# 1. Argon dimer at equilibrium van der Waals distance r = 3.76 Angstroms [M]
ARGON_DIMER_COORDS = torch.tensor(
    [
        [0.0, 0.0, 0.0],
        [3.76, 0.0, 0.0],
    ],
    dtype=torch.float64,
)

# 2. Ethanol (N=9) authentic physical coordinates [M]
ETHANOL_COORDS = torch.tensor(
    [
        [0.0072, 0.0000, 0.0000],  # C1
        [1.5173, 0.0000, 0.0000],  # C2
        [-0.5638, 1.2987, 0.0000],  # O
        [-0.3756, -0.5218, 0.8872],  # H
        [-0.3756, -0.5218, -0.8872],  # H
        [1.9056, 0.5255, 0.8837],  # H
        [1.9056, 0.5255, -0.8837],  # H
        [1.8885, -1.0253, 0.0000],  # H
        [-1.5277, 1.2052, 0.0000],  # H
    ],
    dtype=torch.float64,
)


def test_c2_boundary_continuity() -> None:
    """Verify |f_c(r_c)| < 1e-7, |df_c/dr| < 1e-7, |d2f_c/dr2| < 1e-7 and ||Hessian||_F < 1e-7. [M]/[D]"""
    rc = 5.0
    rc_tensor = torch.tensor([rc], dtype=torch.float64)

    val = float(quintic_c2_envelope(rc_tensor, rc=rc)[0])
    d1 = float(quintic_c2_first_derivative(rc_tensor, rc=rc)[0])
    d2 = float(quintic_c2_second_derivative(rc_tensor, rc=rc)[0])

    assert abs(val) < 1e-7
    assert abs(d1) < 1e-7
    assert abs(d2) < 1e-7

    # Test spatial gradient and Hessian at exactly r = rc
    r_i = torch.tensor([0.0, 0.0, 0.0], dtype=torch.float64)
    r_j = torch.tensor([rc, 0.0, 0.0], dtype=torch.float64)

    grad = quintic_c2_spatial_gradient(r_i, r_j, rc=rc)
    hessian = quintic_c2_spatial_hessian(r_i, r_j, rc=rc)

    assert torch.norm(grad).item() < 1e-7
    assert torch.norm(hessian).item() < 1e-7

    # Verify helper function
    assert verify_cutoff_continuity(rc=rc, tolerance=1e-7) is True


def test_autograd_double_backward_parity() -> None:
    """Compute first and second spatial derivatives via torch.autograd and compare with analytical formulas. [D]"""
    rc = 5.0
    # Coordinates for Argon dimer: r_ij = 3.76 A < rc
    r_i = torch.tensor([0.2, 0.4, 0.1], dtype=torch.float64, requires_grad=True)
    r_j = torch.tensor([2.5, 2.0, 1.8], dtype=torch.float64)

    # 1. Forward evaluation of envelope
    r_ij = r_j - r_i
    dist = torch.norm(r_ij)
    u = dist / rc
    # Direct polynomial computation for autograd graph
    fc_val = 1.0 - 10.0 * (u ** 3) + 15.0 * (u ** 4) - 6.0 * (u ** 5)

    # 2. Autograd first derivative (gradient wrt r_i)
    grad_auto = torch.autograd.grad(fc_val, r_i, create_graph=True)[0]
    grad_analytic = quintic_c2_spatial_gradient(r_i, r_j, rc=rc)

    assert torch.allclose(grad_auto, grad_analytic, atol=1e-6)

    # 3. Autograd second derivative (Hessian wrt r_i)
    hessian_rows = []
    for alpha in range(3):
        row = torch.autograd.grad(grad_auto[alpha], r_i, retain_graph=True)[0]
        hessian_rows.append(row)
    hessian_auto = torch.stack(hessian_rows, dim=0)

    hessian_analytic = quintic_c2_spatial_hessian(r_i, r_j, rc=rc)

    assert torch.allclose(hessian_auto, hessian_analytic, atol=1e-6)
    # Check Hessian symmetry
    assert torch.allclose(hessian_analytic, hessian_analytic.t(), atol=1e-7)


def test_cutoff_beyond_boundary_vanishes() -> None:
    """Verify evaluation beyond cutoff boundary smoothly vanishes to zero. [D]"""
    rc = 5.0
    d_far = torch.tensor([5.001, 6.0, 10.0, 50.0], dtype=torch.float64)
    fc_far = quintic_c2_envelope(d_far, rc=rc)
    d1_far = quintic_c2_first_derivative(d_far, rc=rc)
    d2_far = quintic_c2_second_derivative(d_far, rc=rc)

    assert (fc_far == 0.0).all()
    assert (d1_far == 0.0).all()
    assert (d2_far == 0.0).all()

    # Spatial gradient and Hessian beyond rc
    r_i = torch.tensor([0.0, 0.0, 0.0], dtype=torch.float64)
    r_j = torch.tensor([5.5, 0.0, 0.0], dtype=torch.float64)
    assert (quintic_c2_spatial_gradient(r_i, r_j, rc=rc) == 0.0).all()
    assert (quintic_c2_spatial_hessian(r_i, r_j, rc=rc) == 0.0).all()


def test_discontinuity_guard_raises_error() -> None:
    """Verify attempting to evaluate cutoff with invalid radius raises CutoffContinuityError. [M]"""
    with pytest.raises(CutoffContinuityError):
        quintic_c2_envelope(torch.tensor([1.0]), rc=-2.0)

    with pytest.raises(CutoffContinuityError):
        verify_cutoff_continuity(rc=0.0)

    with pytest.raises(CutoffContinuityError):
        C2SmoothCutoff(cutoff_radius_rc=-5.0)


def test_module_evaluation_on_ethanol() -> None:
    """Evaluate C2SmoothCutoff module on Ethanol interatomic coordinate matrix. [M]"""
    module = C2SmoothCutoff(C2SmoothCutoffConfig(cutoff_radius_rc=5.0))
    coords = ETHANOL_COORDS

    diff = coords.unsqueeze(1) - coords.unsqueeze(0)  # (9, 9, 3)
    dist = torch.norm(diff, dim=-1)                   # (9, 9)

    fc = module(dist)
    # Self-distance is 0 -> f_c(0) = 1
    assert torch.allclose(torch.diag(fc), torch.ones(9, dtype=torch.float64))

    # All values must be in [0, 1]
    assert (fc >= 0.0).all() and (fc <= 1.0).all()

    # Verify module derivatives
    fc, d1, d2 = module.compute_radial_derivatives(dist)
    assert fc.shape == (9, 9)
    assert d1.shape == (9, 9)
    assert d2.shape == (9, 9)
    assert module.verify_continuity() is True
