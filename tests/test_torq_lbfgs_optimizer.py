"""Physical verification suite for L-BFGS Geometry Optimizer with Eckart TR-Projection.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic physics, dynamic masses, and physical convergence thresholds.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from Libraries.cochem_torq_delta_ml import LennardJonesBaselineEngine
from Libraries.cochem_torq_inference_errors import (
    ClashDetectedError,
)
from Libraries.cochem_torq_inference_schemas import LBFGSOptimizerConfig
from Libraries.cochem_torq_lbfgs_optimizer import (
    LBFGSOptimizer,
    check_clash,
    project_forces_eckart,
)
from Libraries.cochem_torq_masses import resolve_ciaaw_monoisotopic_mass

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


def test_eckart_tr_projection_water_dimer_and_ethanol() -> None:
    r"""Test exact Cartesian Eckart TR-projection: ||F_net||_2 < 1e-6 and ||Torque||_2 < 1e-6. [D]

    $$\mathbf{F}_{\text{proj}} = (\mathbf{I} - \mathbf{M} \mathbf{D} (\mathbf{D}^T \mathbf{M} \mathbf{D})^{-1} \mathbf{D}^T) \mathbf{F}$$
    """
    for name, raw_coords, z in [
        ("Water Dimer", WATER_DIMER_COORDS, WATER_DIMER_Z),
        ("Ethanol", ETHANOL_COORDS, ETHANOL_Z),
    ]:
        coords = torch.tensor(raw_coords, dtype=torch.float64)
        N = coords.shape[0]

        # Generate arbitrary non-conservative initial test forces with substantial net translation & torque
        torch.manual_seed(123)
        raw_forces = torch.randn((N, 3), dtype=torch.float64) * 0.5 + 0.1

        # Project forces using dynamic CIAAW masses
        f_proj = project_forces_eckart(coords, raw_forces, z)

        # 1. Check Net Translational Drift: sum_i F_proj,i == 0
        net_trans = torch.norm(torch.sum(f_proj, dim=0)).item()
        assert net_trans < 1e-6, f"{name}: Net translation {net_trans} exceeds 1e-6 eV/A"

        # 2. Check Net Rotational Torque: sum_i (r_i - R_COM) x F_proj,i == 0
        masses = torch.tensor(
            [resolve_ciaaw_monoisotopic_mass(int(zi)) for zi in z],
            dtype=torch.float64,
        )
        com = torch.sum(masses.view(-1, 1) * coords, dim=0) / torch.sum(masses)
        r_prime = coords - com
        net_torque = torch.norm(
            torch.sum(torch.cross(r_prime, f_proj, dim=-1), dim=0)
        ).item()
        assert net_torque < 1e-6, f"{name}: Net torque {net_torque} exceeds 1e-6 eV"


def test_lbfgs_full_minimization_to_method_matrix_thresholds() -> None:
    """Execute L-BFGS optimizer in float64 until Method Matrix v4 convergence thresholds are satisfied. [M]"""
    # Authentic Water dimer with slight coordinate distortion
    coords_eq = torch.tensor(WATER_DIMER_COORDS, dtype=torch.float64)
    distortion = torch.tensor(
        [
            [0.010, -0.005, 0.002],
            [-0.008, 0.010, -0.003],
            [0.005, -0.005, 0.002],
            [-0.010, 0.008, -0.004],
            [0.003, -0.002, 0.005],
            [-0.005, 0.004, -0.002],
        ],
        dtype=torch.float64,
    )
    coords_start = coords_eq + distortion

    lj_engine = LennardJonesBaselineEngine()

    def potential_fn(r: torch.Tensor) -> torch.Tensor:
        N = len(WATER_DIMER_Z)
        sigmas = [lj_engine._get_params(zi)[0] for zi in WATER_DIMER_Z]
        epsilons = [lj_engine._get_params(zi)[1] for zi in WATER_DIMER_Z]
        sig = torch.tensor(sigmas, dtype=torch.float64, device=r.device)
        eps = torch.tensor(epsilons, dtype=torch.float64, device=r.device)
        sig_ij = 0.5 * (sig.unsqueeze(1) + sig.unsqueeze(0))
        eps_ij = torch.sqrt(eps.unsqueeze(1) * eps.unsqueeze(0))
        diff = r.unsqueeze(1) - r.unsqueeze(0)
        dist = torch.norm(diff, dim=-1)
        mask = torch.triu(
            torch.ones((N, N), dtype=torch.bool, device=r.device), diagonal=1
        )
        safe_dist = torch.where(mask, dist, torch.ones_like(dist))
        sr6 = (sig_ij / safe_dist) ** 6
        sr12 = sr6**2
        return torch.sum(
            torch.where(mask, 4.0 * eps_ij * (sr12 - sr6), torch.zeros_like(sr6))
        )

    config = LBFGSOptimizerConfig(
        max_iterations=150,
        history_size=10,
        tol_max_g=0.00051422,
        tol_rms_g=0.00034453,
    )
    optimizer = LBFGSOptimizer(config)
    result = optimizer.minimize(potential_fn, coords_start, WATER_DIMER_Z)

    assert result.converged is True
    assert result.max_force <= config.tol_max_g
    assert result.rms_force <= config.tol_rms_g
    assert result.final_coordinates is not None
    assert result.final_coordinates.dtype == torch.float64


def test_lbfgs_clash_guard_aborts_on_overlap() -> None:
    """Introduce overlapping coordinates (r_ij < 0.7 A); assert optimizer aborts and raises ClashDetectedError. [E]"""
    clash_coords = torch.tensor(WATER_DIMER_COORDS, dtype=torch.float64).clone()
    # Move H2 to almost collide with O1: distance ~0.3 Angstroms (< 0.7)
    clash_coords[2] = clash_coords[0] + torch.tensor(
        [0.1, 0.1, 0.1], dtype=torch.float64
    )

    with pytest.raises(ClashDetectedError) as exc_info:
        check_clash(clash_coords, clash_distance=0.7)

    assert exc_info.value.error_code == "TORQ_GEOM_CLASH_DETECTED"
    assert exc_info.value.component == "lbfgs_optimizer"
    assert exc_info.value.diagnostics["min_distance_angstrom"] < 0.7

    # Also test optimizer aborts when starting with clashing geometry
    optimizer = LBFGSOptimizer()
    with pytest.raises(ClashDetectedError):
        optimizer.minimize(
            lambda r: torch.sum(r**2), clash_coords, WATER_DIMER_Z
        )
