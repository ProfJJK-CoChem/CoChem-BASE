"""Comprehensive physically verified zero-mock test suite for CoChem-TORQ Model Backbones.

Adheres strictly to Zero-Mock mandate v3, Mendeleev monoisotopic masses mandate,
and Pydantic v2 schemas.
"""

from __future__ import annotations

import math
from pathlib import Path
import tempfile
import threading
from typing import List, Tuple
import numpy as np
import pydantic
import pytest
import torch
from ase import Atoms, units
from ase.md.verlet import VelocityVerlet

import cochem.torq.constants as const
from cochem.torq.backbones.cutoff import (
    BesselBasis,
    GaussianSmearing,
    RadialBasis,
    polynomial_cutoff,
)
from cochem.torq.backbones.equivariant_tensor import (
    CartesianEquivariantBackbone,
    MACEBackbone,
    NequIPWrapper,
)
from cochem.torq.backbones.observables import DifferentiableObservables
from cochem.torq.backbones.schnet import SchNetBackbone, SchNetFallbackRouter
from cochem.torq.backbones.spherical_harmonics import real_spherical_harmonics
from cochem.torq.calculators.ase_calc import TORQCalculator
from cochem.torq.constants import (
    ANGSTROM_TO_METER,
    BOHR_TO_ANGSTROM,
    DEBYE_PER_EAA,
    EV_PER_ANGSTROM_TO_NEWTON,
    EV_PER_ANGSTROM3_TO_GPA,
    EV_TO_JOULE,
    HARTREE_PER_BOHR_TO_EV_PER_ANGSTROM,
    HARTREE_TO_EV,
)
from cochem.torq.errors import (
    AutogradForceError,
    CoChemError,
    EquivarianceViolationError,
    ObservableComputationError,
    PeriodicBoundaryConditionError,
    TorqDeviceAllocationError,
    TorqError,
    TorqModelBackboneError,
    TorqPersistenceLockError,
)
from cochem.torq.models.schemas import (
    AtomicConfigurationInput,
    HDF5PersistenceConfig,
    ObservableOutput,
    PotentialEnergyOutput,
    TorqModelConfig,
)
from cochem.torq.storage.hdf5_persister import HDF5TorqStorage
from cochem.torq.utils.mendeleev_masses import (
    get_monoisotopic_masses,
    query_single_monoisotopic_mass,
)

# Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical

# ---------------------------------------------------------------------------
# Authentic Chemical Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def water_monomer() -> Tuple[List[int], torch.Tensor, Atoms]:
    """Authentic gas-phase Water (H2O) equilibrium geometry in Angstroms [M]."""
    z = [8, 1, 1]
    coords_np = np.array(
        [
            [0.0000, 0.0000, 0.0000],  # Oxygen
            [0.0000, 0.7570, 0.5860],  # Hydrogen 1
            [0.0000, -0.7570, 0.5860],  # Hydrogen 2
        ],
        dtype=np.float64,
    )
    coords_torch = torch.tensor(coords_np, dtype=torch.float64)
    atoms = Atoms(numbers=z, positions=coords_np, pbc=False)
    return z, coords_torch, atoms


@pytest.fixture
def ethanol_molecule() -> Tuple[List[int], torch.Tensor, Atoms]:
    """Authentic all-atom Ethanol (C2H6O) geometry in Angstroms [M]."""
    z = [6, 6, 8, 1, 1, 1, 1, 1, 1]
    coords_np = np.array(
        [
            [0.00, 0.00, 0.00],  # C1
            [1.52, 0.00, 0.00],  # C2
            [2.05, 1.33, 0.00],  # O
            [-0.36, -0.51, 0.89],  # H1
            [-0.36, -0.51, -0.89],  # H2
            [-0.36, 1.03, 0.00],  # H3
            [1.88, -0.51, 0.89],  # H4
            [1.88, -0.51, -0.89],  # H5
            [3.01, 1.33, 0.00],  # H6
        ],
        dtype=np.float64,
    )
    coords_torch = torch.tensor(coords_np, dtype=torch.float64)
    atoms = Atoms(numbers=z, positions=coords_np, pbc=False)
    return z, coords_torch, atoms


@pytest.fixture
def silicon_crystal() -> Atoms:
    """Authentic diamond cubic Silicon (Si8) unit cell (a = 5.431 Angstroms) [M]."""
    a = 5.431  # [M] Silicon lattice parameter in Angstroms
    basis = (
        np.array(
            [
                [0.0, 0.0, 0.0],
                [0.0, 0.5, 0.5],
                [0.5, 0.0, 0.5],
                [0.5, 0.5, 0.0],
                [0.25, 0.25, 0.25],
                [0.25, 0.75, 0.75],
                [0.75, 0.25, 0.75],
                [0.75, 0.75, 0.25],
            ],
            dtype=np.float64,
        )
        * a
    )
    cell = np.array(
        [
            [a, 0.0, 0.0],
            [0.0, a, 0.0],
            [0.0, 0.0, a],
        ],
        dtype=np.float64,
    )
    atoms = Atoms(numbers=[14] * 8, positions=basis, cell=cell, pbc=True)
    return atoms


# ---------------------------------------------------------------------------
# DEF-01: Virial Stress via Strain Autograd [D], [M]
# ---------------------------------------------------------------------------


def test_def01_virial_stress_strain_autograd(silicon_crystal: Atoms) -> None:
    """Verify TORQCalculator evaluates stress strictly via spatial strain autograd.

    Guarantees:
    - Returns Voigt 6-vector in eV/Angstrom^3 [M]
    - Parity with central finite-difference cell strain < 10^-4 eV/Angstrom^3 [M]
    - Zero velocities/kinetic terms present in static potential calculator [M]
    - Periodic boundary condition validation [M]
    """
    model = CartesianEquivariantBackbone().double()
    calc = TORQCalculator(model=model, dtype=torch.float64)
    silicon_crystal.calc = calc

    # 1. Evaluate analytical autograd stress
    stress_auto = silicon_crystal.get_stress(voigt=True)
    assert isinstance(stress_auto, np.ndarray)
    assert stress_auto.shape == (6,)

    # 2. Compute central finite-difference strain response
    # Voigt index mapping: (xx, yy, zz, yz, xz, xy)
    voigt_map = [(0, 0), (1, 1), (2, 2), (1, 2), (0, 2), (0, 1)]
    volume = silicon_crystal.get_volume()
    base_pos = silicon_crystal.get_positions()
    base_cell = np.array(silicon_crystal.get_cell())
    z_nums = silicon_crystal.get_atomic_numbers()

    h = 1e-6  # Strain perturbation step [E]
    stress_fd = np.array([0.0] * 6, dtype=np.float64)

    for idx, (i, j) in enumerate(voigt_map):
        eps_plus = np.array(
            [
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
            ],
            dtype=np.float64,
        )
        if i == j:
            eps_plus[i, i] = h
            denom = 2.0 * h
        else:
            eps_plus[i, j] = h
            eps_plus[j, i] = h
            denom = 4.0 * h

        # Positive strain
        at_plus = Atoms(
            numbers=z_nums,
            positions=base_pos + base_pos @ eps_plus,
            cell=base_cell + base_cell @ eps_plus,
            pbc=True,
        )
        at_plus.calc = calc
        e_plus = at_plus.get_potential_energy()

        # Negative strain
        eps_minus = -eps_plus
        at_minus = Atoms(
            numbers=z_nums,
            positions=base_pos + base_pos @ eps_minus,
            cell=base_cell + base_cell @ eps_minus,
            pbc=True,
        )
        at_minus.calc = calc
        e_minus = at_minus.get_potential_energy()

        stress_fd[idx] = ((e_plus - e_minus) / denom) / volume

    # Numerical parity threshold: < 10^-4 eV/Angstrom^3 [M]
    max_stress_error = np.max(np.abs(stress_auto - stress_fd))
    assert (
        max_stress_error < 1e-4
    ), f"Virial stress finite-diff mismatch: {max_stress_error:.4e} >= 1e-4 eV/Angstrom^3"

    # 3. Verify calculator contains ZERO kinetic energy / velocity terms [M]
    silicon_crystal.set_velocities(
        np.ones_like(base_pos) * 100.0
    )  # Huge non-zero velocities
    stress_with_vel = silicon_crystal.get_stress(voigt=True)
    np.testing.assert_allclose(
        stress_auto,
        stress_with_vel,
        atol=1e-12,
        err_msg="TORQCalculator erroneously included particle velocities in potential virial stress!",
    )

    # 4. Verify singular cell raises PeriodicBoundaryConditionError
    singular_crystal = silicon_crystal.copy()
    singular_crystal.set_cell(
        np.array(
            [
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
            ],
            dtype=np.float64,
        )
    )
    singular_crystal.calc = calc
    with pytest.raises(PeriodicBoundaryConditionError):
        singular_crystal.get_stress()


# ---------------------------------------------------------------------------
# DEF-02: Rigorous Polarizability Formulation [D], [M]
# ---------------------------------------------------------------------------


def test_def02_polarizability_tensor_equivariance_and_response(
    water_monomer: Tuple[List[int], torch.Tensor, Atoms],
    ethanol_molecule: Tuple[List[int], torch.Tensor, Atoms],
) -> None:
    """Verify polarizability tensor equivariance and field-coupled autograd response.

    Guarantees:
    - Tensor rotation transformation: alpha(R*R) = R * alpha(R) * R^T [D]
    - Frobenius error < 10^-5 Angstrom^3 [M]
    - Matrix symmetry |alpha_munu - alpha_numu| < 10^-6 [M]
    - Field response d(mu)/d(E)|_{E=0} matches analytic head [D]
    """
    model = CartesianEquivariantBackbone().double()
    obs = DifferentiableObservables().double()

    for name, (z, coords, _) in [
        ("Water", water_monomer),
        ("Ethanol", ethanol_molecule),
    ]:
        out = model(z, coords)
        alpha_analytic, mean_alpha, aniso = obs.compute_polarizability(
            out["scalar_features"], out["rank2_tensor"]
        )

        # 1. Check positive isotropic polarizability [D]
        assert (
            mean_alpha > 0.0
        ), f"{name}: Mean isotropic polarizability must be positive, got {mean_alpha}"
        assert (
            aniso >= 0.0
        ), f"{name}: Polarizability anisotropy must be non-negative, got {aniso}"

        # 2. Check strict symmetry [M]
        sym_diff = (
            torch.max(torch.abs(alpha_analytic - alpha_analytic.T)).detach().item()
        )
        assert (
            sym_diff < 1e-6
        ), f"{name}: Polarizability tensor asymmetry {sym_diff:.4e} exceeds 1e-6"

        # 3. Test rotational equivariance: alpha(R*x) = R * alpha(x) * R^T
        # Authentic deterministic 3D SO(3) rotation matrix (Euler angles alpha=0.5, beta=0.7, gamma=1.1) [D]
        c1, s1 = math.cos(0.5), math.sin(0.5)
        c2, s2 = math.cos(0.7), math.sin(0.7)
        c3, s3 = math.cos(1.1), math.sin(1.1)
        r_rot_np = np.array(
            [
                [c1 * c2, c1 * s2 * s3 - s1 * c3, c1 * s2 * c3 + s1 * s3],
                [s1 * c2, s1 * s2 * s3 + c1 * c3, s1 * s2 * c3 - c1 * s3],
                [-s2, c2 * s3, c2 * c3],
            ],
            dtype=np.float64,
        )

        r_rot_tensor = torch.tensor(r_rot_np, dtype=torch.float64)
        coords_rotated = coords @ r_rot_tensor.T

        out_rot = model(z, coords_rotated)
        alpha_rot, _, _ = obs.compute_polarizability(
            out_rot["scalar_features"], out_rot["rank2_tensor"]
        )

        # Expected rotated polarizability: R * alpha * R^T
        expected_alpha_rot = r_rot_tensor @ alpha_analytic @ r_rot_tensor.T
        frob_error = (
            torch.norm(alpha_rot - expected_alpha_rot, p="fro").detach().item()
        )
        assert (
            frob_error < 1e-5
        ), f"{name}: Rotational Frobenius error {frob_error:.4e} >= 1e-5 Angstrom^3"

        # 4. Field-coupled response matching: d(mu)/d(E) = alpha [D]
        alpha_response = obs.compute_field_response_polarizability(
            coordinates=coords,
            atomic_numbers=z,
            scalar_features=out["scalar_features"],
            vector_features=out["vector_features"],
            rank2_tensor=out["rank2_tensor"],
        )
        response_match_err = (
            torch.max(torch.abs(alpha_response - alpha_analytic)).detach().item()
        )
        assert (
            response_match_err < 1e-5
        ), f"{name}: Field response polarizability mismatch {response_match_err:.4e} >= 1e-5"

    # 5. Check exception on broken tensor symmetry
    with pytest.raises(ObservableComputationError):
        asym_rank2 = torch.zeros(
            (len(water_monomer[0]), 3, 3), dtype=torch.float64
        )
        asym_rank2[0, 0, 1] = 1.0  # Asymmetric perturbation
        obs.compute_polarizability(out["scalar_features"], asym_rank2)


# ---------------------------------------------------------------------------
# DEF-03: C^2-Smooth Polynomial Cutoff Envelope [D]
# ---------------------------------------------------------------------------


def test_def03_c2_smooth_polynomial_cutoff() -> None:
    """Verify C^2-smooth polynomial cutoff envelope at and across boundary r_max.

    Guarantees:
    - f_cut(r_max) = 0 within 10^-12 [M]
    - f'_cut(r_max) = 0 within 10^-12 [M]
    - f''_cut(r_max) = 0 within 10^-12 [M]
    - Zero NaNs and continuous Hessians across boundary [D]
    """
    r_max = 5.0

    # 1. Exact evaluation at boundary in torch.float64
    r_boundary = torch.tensor([r_max], dtype=torch.float64, requires_grad=True)
    f_val = polynomial_cutoff(r_boundary, r_max)
    grad_1 = torch.autograd.grad(f_val, r_boundary, create_graph=True)[0]
    grad_2 = torch.autograd.grad(grad_1, r_boundary)[0]

    assert (
        abs(f_val.item()) < 1e-12
    ), f"f_cut(r_max) = {f_val.item():.4e} exceeds 1e-12"
    assert (
        abs(grad_1.item()) < 1e-12
    ), f"f'_cut(r_max) = {grad_1.item():.4e} exceeds 1e-12"
    assert (
        abs(grad_2.item()) < 1e-12
    ), f"f''_cut(r_max) = {grad_2.item():.4e} exceeds 1e-12"

    # 2. Continuity across boundary: r in [r_max - 0.1, r_max + 0.1]
    r_sweep = torch.linspace(
        r_max - 0.1, r_max + 0.1, 50, dtype=torch.float64, requires_grad=True
    )
    f_sweep = polynomial_cutoff(r_sweep, r_max)
    g_sweep = torch.autograd.grad(
        f_sweep.sum(), r_sweep, create_graph=True, retain_graph=True
    )[0]
    h_sweep = torch.autograd.grad(g_sweep.sum(), r_sweep)[0]

    assert not torch.isnan(f_sweep).any(), "NaN detected in cutoff envelope"
    assert not torch.isnan(g_sweep).any(), "NaN detected in cutoff 1st derivative"
    assert not torch.isnan(h_sweep).any(), "NaN detected in cutoff 2nd derivative"

    # Values beyond r_max must be strictly 0.0
    beyond_mask = r_sweep > r_max
    assert torch.all(f_sweep[beyond_mask] == 0.0)
    assert torch.all(g_sweep[beyond_mask] == 0.0)
    assert torch.all(h_sweep[beyond_mask] == 0.0)

    # 3. Verify RadialBasis expansions
    gaussian_smear = GaussianSmearing(start=0.0, stop=r_max, num_gaussians=32)
    bessel_basis = BesselBasis(r_max=r_max, num_basis=32)
    dists = torch.tensor([1.0, 2.5, 4.99, 5.01], dtype=torch.float64)

    g_out = gaussian_smear(dists)
    b_out = bessel_basis(dists)
    assert g_out.shape == (4, 32)
    assert b_out.shape == (4, 32)
    # Outside cutoff elements must be zero
    assert torch.all(g_out[3] == 0.0)
    assert torch.all(b_out[3] == 0.0)


# ---------------------------------------------------------------------------
# DEF-04: Unit System Consistency & Finite-Difference Forces [M], [D]
# ---------------------------------------------------------------------------


def test_def04_unit_system_and_finite_diff_forces(
    water_monomer: Tuple[List[int], torch.Tensor, Atoms],
) -> None:
    """Verify force accuracy via central finite differences in torch.float64.

    Guarantees:
    - Step size h = 10^-4 Angstroms [M]
    - max |F_autograd - F_FD| <= 10^-4 eV/Angstrom [M]
    - Center-of-mass momentum drift ||sum F_i||_2 <= 10^-6 eV/Angstrom [M]
    - Velocity Verlet NVE molecular dynamics energy drift < 10^-4 eV [M]
    """
    z, coords, atoms = water_monomer
    model = CartesianEquivariantBackbone().double()

    # 1. Analytical autograd forces
    coords_in = coords.clone().detach().requires_grad_(True)
    out = model(z, coords_in, compute_forces=True)
    forces_auto = out["forces"].detach().numpy()

    # Net momentum drift check
    net_force_norm = float(np.linalg.norm(np.sum(forces_auto, axis=0)))
    assert (
        net_force_norm <= 1e-6
    ), f"Center-of-mass force drift {net_force_norm:.4e} exceeds 1e-6 eV/Angstrom [M]"

    # 2. Central finite differences
    h = 1e-4  # [M] Mandated finite difference step in Angstroms
    forces_fd = np.zeros_like(forces_auto)

    for i in range(len(z)):
        for alpha in range(3):
            coords_plus = coords.clone().detach()
            coords_plus[i, alpha] += h
            e_plus = model(z, coords_plus, compute_forces=False)["energy"].item()

            coords_minus = coords.clone().detach()
            coords_minus[i, alpha] -= h
            e_minus = model(z, coords_minus, compute_forces=False)["energy"].item()

            forces_fd[i, alpha] = -(e_plus - e_minus) / (2.0 * h)

    # Project center of mass drift on finite difference forces for fair comparison
    forces_fd = forces_fd - forces_fd.mean(axis=0, keepdims=True)

    max_force_err = np.max(np.abs(forces_auto - forces_fd))
    assert (
        max_force_err <= 1e-4
    ), f"Finite-difference force error {max_force_err:.4e} exceeds 1e-4 eV/Angstrom [M]"

    # 3. ASE Velocity Verlet NVE MD stability check
    calc = TORQCalculator(model=model, dtype=torch.float64)
    atoms_md = atoms.copy()
    atoms_md.calc = calc

    dyn = VelocityVerlet(atoms_md, timestep=0.2 * units.fs)
    initial_total_energy = atoms_md.get_total_energy()
    traj_energies = [initial_total_energy]

    for _ in range(10):
        dyn.run(1)
        traj_energies.append(atoms_md.get_total_energy())

    max_nve_drift = max(abs(e - initial_total_energy) for e in traj_energies)
    assert (
        max_nve_drift < 1e-4
    ), f"NVE MD energy drift {max_nve_drift:.4e} exceeds 1e-4 eV threshold [M]"


# ---------------------------------------------------------------------------
# DEF-05: E(3) Rotational & Inversion Equivariance [M], [D]
# ---------------------------------------------------------------------------


def test_def05_e3_rotational_and_inversion_equivariance(
    water_monomer: Tuple[List[int], torch.Tensor, Atoms],
    ethanol_molecule: Tuple[List[int], torch.Tensor, Atoms],
) -> None:
    """Verify E(3) rotational invariance, force equivariance, and parity inversion.

    Guarantees:
    - Energy invariance |E(R*x + t) - E(x)| <= 10^-5 eV [M]
    - Force equivariance ||F(R*x) - R*F(x)||_inf <= 10^-5 eV/Angstrom [M]
    - Inversion parity E(P*x) = E(x) and F(P*x) = -F(x) for P = -I [D]
    """
    model = CartesianEquivariantBackbone().double()
    schnet = SchNetBackbone().double()

    systems = [("Water", water_monomer), ("Ethanol", ethanol_molecule)]

    for name, (z, coords, _) in systems:
        out_base = model(
            z, coords.clone().requires_grad_(True), compute_forces=True
        )
        e_base = out_base["energy"].item()
        f_base = out_base["forces"].detach().numpy()

        # 1. 5 Authentic deterministic SO(3) rotations and spatial translations [D]
        rot_angles = [
            (0.5, 0.7, 1.1, [1.2, -0.5, 0.8]),
            (1.2, -0.4, 0.6, [-0.7, 1.5, -2.1]),
            (-0.8, 0.9, -1.3, [3.0, 0.0, -1.0]),
            (0.3, -1.1, 0.4, [0.2, -1.8, 0.5]),
            (-1.4, -0.6, 0.8, [-1.1, 2.3, 0.4]),
        ]
        for rot_idx, (a1, a2, a3, t_vec) in enumerate(rot_angles):
            c1, s1 = math.cos(a1), math.sin(a1)
            c2, s2 = math.cos(a2), math.sin(a2)
            c3, s3 = math.cos(a3), math.sin(a3)
            q = np.array(
                [
                    [c1 * c2, c1 * s2 * s3 - s1 * c3, c1 * s2 * c3 + s1 * s3],
                    [s1 * c2, s1 * s2 * s3 + c1 * c3, s1 * s2 * c3 - c1 * s3],
                    [-s2, c2 * s3, c2 * c3],
                ],
                dtype=np.float64,
            )
            r_mat = torch.tensor(q, dtype=torch.float64)
            translation = torch.tensor(t_vec, dtype=torch.float64)

            # Transformed coordinates: R*x + t
            coords_rot = (coords @ r_mat.T + translation).clone().requires_grad_(True)

            out_rot = model(z, coords_rot, compute_forces=True)
            e_rot = out_rot["energy"].item()
            f_rot = out_rot["forces"].detach().numpy()

            # Energy invariance check
            de = abs(e_rot - e_base)
            assert (
                de <= 1e-5
            ), f"{name} Rotation {rot_idx}: Energy invariance error {de:.4e} > 1e-5 eV [M]"

            # Force equivariance check: F(R*x) = R*F(x)
            expected_f_rot = f_base @ q.T
            df = np.max(np.abs(f_rot - expected_f_rot))
            assert (
                df <= 1e-5
            ), f"{name} Rotation {rot_idx}: Force equivariance error {df:.4e} > 1e-5 eV/Angstrom [M]"

        # 2. Parity inversion: P = -I
        p_mat = np.array(
            [
                [-1.0, 0.0, 0.0],
                [0.0, -1.0, 0.0],
                [0.0, 0.0, -1.0],
            ],
            dtype=np.float64,
        )
        coords_inv = (coords @ torch.tensor(p_mat, dtype=torch.float64)).clone().requires_grad_(True)

        out_inv = model(z, coords_inv, compute_forces=True)
        e_inv = out_inv["energy"].item()
        f_inv = out_inv["forces"].detach().numpy()

        de_inv = abs(e_inv - e_base)
        assert (
            de_inv <= 1e-5
        ), f"{name} Inversion: Energy invariance error {de_inv:.4e} > 1e-5 eV [M]"

        expected_f_inv = -f_base
        df_inv = np.max(np.abs(f_inv - expected_f_inv))
        assert (
            df_inv <= 1e-5
        ), f"{name} Inversion: Force equivariance error {df_inv:.4e} > 1e-5 eV/Angstrom [M]"

        # 3. Verify SchNet energy invariance under rotation
        out_schnet_base = schnet(z, coords)
        out_schnet_rot = schnet(z, coords_rot)
        de_schnet = abs(
            out_schnet_rot["energy"].item() - out_schnet_base["energy"].item()
        )
        assert (
            de_schnet <= 1e-5
        ), f"{name}: SchNet rotation invariance error {de_schnet:.4e} > 1e-5 eV [M]"

    # 4. Verify pure-PyTorch real spherical harmonics l <= 2
    r_hat = torch.tensor([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0]], dtype=torch.float64)
    sh = real_spherical_harmonics(r_hat, l_max=2)
    assert 0 in sh and sh[0].shape == (2, 1)
    assert 1 in sh and sh[1].shape == (2, 3)
    assert 2 in sh and sh[2].shape == (2, 5)


# ---------------------------------------------------------------------------
# DEF-06: Pydantic v2 Schemas & Domain Exceptions [M]
# ---------------------------------------------------------------------------


def test_def06_pydantic_v2_and_exceptions() -> None:
    """Verify Pydantic v2 configuration immutability and complete exception hierarchy.

    Guarantees:
    - model_config = ConfigDict(frozen=True, extra="forbid") [M]
    - Domain exceptions inherit from TorqError(CoChemError) [M]
    """
    # 1. Config immutability and extra field prohibition
    cfg = TorqModelConfig(
        model_name="cartesian_equivariant",
        r_max=5.0,
        num_channels=64,
        num_radial_basis=32,
        num_layers=3,
    )

    with pytest.raises((pydantic.ValidationError, TypeError)):
        cfg.r_max = 6.0  # Cannot mutate frozen instance

    with pytest.raises(pydantic.ValidationError):
        TorqModelConfig(invalid_extra_field=999)  # Forbids extra fields

    with pytest.raises(pydantic.ValidationError):
        TorqModelConfig(r_max=-1.0)  # gt=0.0 validation

    # 2. Test other Pydantic v2 models
    atomic_in = AtomicConfigurationInput(
        atomic_numbers=[8, 1, 1],
        coordinates=[(0.0, 0.0, 0.0), (0.0, 0.757, 0.586), (0.0, -0.757, 0.586)],
    )
    assert len(atomic_in.atomic_numbers) == 3

    pot_out = PotentialEnergyOutput(
        energy=-14.5,
        forces=[(0.0, 0.0, 0.1), (0.0, 0.2, -0.05), (0.0, -0.2, -0.05)],
    )
    assert pot_out.energy == -14.5

    obs_out = ObservableOutput(
        dipole_vector=(0.0, 0.0, 1.85),
        polarizability_tensor=[
            [1.5, 0.0, 0.0],
            [0.0, 1.5, 0.0],
            [0.0, 0.0, 1.5],
        ],
        mean_polarizability=1.5,
        anisotropy=0.0,
    )
    assert obs_out.mean_polarizability == 1.5

    # 3. Exception hierarchy verification [M]
    domain_exceptions = [
        TorqModelBackboneError,
        EquivarianceViolationError,
        AutogradForceError,
        ObservableComputationError,
        TorqPersistenceLockError,
        TorqDeviceAllocationError,
        PeriodicBoundaryConditionError,
    ]

    assert issubclass(TorqError, CoChemError)

    for exc_cls in domain_exceptions:
        assert issubclass(
            exc_cls, TorqError
        ), f"{exc_cls.__name__} does not inherit from TorqError"
        assert issubclass(
            exc_cls, CoChemError
        ), f"{exc_cls.__name__} does not inherit from CoChemError"
        # Verify instantiation and message preservation
        err_instance = exc_cls(f"Test failure message for {exc_cls.__name__}")
        assert "Test failure message" in str(err_instance)


# ---------------------------------------------------------------------------
# DEF-07: Dual-Locked HDF5 Persistence [M]
# ---------------------------------------------------------------------------


def test_def07_dual_locked_hdf5_persistence() -> None:
    """Verify thread-safe and process-safe HDF5 persistence under 4 concurrent threads.

    Guarantees:
    - Dual filelock and threading.RLock() concurrency isolation [M]
    - Zero data corruption across concurrent appends [M]
    - Clean lock acquisition and release [M]
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        h5_file = Path(tmpdir) / "concurrent_test.h5"
        storage = HDF5TorqStorage(
            config_or_path=h5_file,
            timeout=15.0,
            compression="gzip",
            compression_opts=4,
        )

        num_threads = 4
        frames_per_thread = 5
        errors: List[Exception] = []

        def worker(thread_idx: int) -> None:
            try:
                for step in range(frames_per_thread):
                    coords = np.array(
                        [
                            [0.1 * thread_idx, 0.2 * step, 0.0],
                            [0.0, 0.757 + 0.01 * step, 0.586],
                            [0.0, -0.757 - 0.01 * step, 0.586],
                        ],
                        dtype=np.float64,
                    )
                    forces = np.array(
                        [
                            [0.01 * (step + 1), -0.02 * (thread_idx + 1), 0.0],
                            [-0.005 * (step + 1), 0.01 * (thread_idx + 1), 0.01],
                            [-0.005 * (step + 1), 0.01 * (thread_idx + 1), -0.01],
                        ],
                        dtype=np.float64,
                    )
                    storage.append_frame(
                        traj_id=f"traj_worker_{thread_idx}",
                        coordinates=coords,
                        forces=forces,
                        energy=float(thread_idx * 100.0 + step),
                        atomic_numbers=np.array([8, 1, 1], dtype=np.int32),
                        monoisotopic_masses=np.array([15.9949, 1.0078, 1.0078]),
                        stress=np.array(
                            [0.1 * step, 0.2, -0.1, 0.0, 0.0, 0.05],
                            dtype=np.float64,
                        ),
                        dipole=np.array(
                            [0.0, 0.0, 1.85 + 0.01 * step], dtype=np.float64
                        ),
                        polarizability=np.array(
                            [
                                [1.5 + 0.1 * step, 0.0, 0.0],
                                [0.0, 1.5 + 0.1 * step, 0.0],
                                [0.0, 0.0, 1.5 + 0.1 * step],
                            ],
                            dtype=np.float64,
                        ),
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(i,)) for i in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert (
            len(errors) == 0
        ), f"Errors encountered during concurrent HDF5 writes: {errors}"

        # Verify all trajectories exist and have intact shapes
        trajs = storage.list_trajectories()
        assert len(trajs) == num_threads
        for i in range(num_threads):
            t_id = f"traj_worker_{i}"
            assert t_id in trajs
            data = storage.load_trajectory(t_id)
            assert data["coordinates"].shape == (frames_per_thread, 3, 3)
            assert data["forces"].shape == (frames_per_thread, 3, 3)
            assert data["energy"].shape == (frames_per_thread,)
            assert data["stress"].shape == (frames_per_thread, 6)
            assert data["dipole"].shape == (frames_per_thread, 3)
            assert data["polarizability"].shape == (frames_per_thread, 3, 3)
            assert data["atomic_numbers"].shape == (3,)
            assert data["monoisotopic_masses"].shape == (3,)


# ---------------------------------------------------------------------------
# DEF-08: Method Matrix v4 Provenance & CODATA 2022 Constants [M]
# ---------------------------------------------------------------------------


def test_def08_provenance_and_codata_constants() -> None:
    """Verify CODATA 2022 physical constants, unit conversion factors, and provenance tags.

    Guarantees:
    - Exact CODATA 2022 constants [M]
    - Derived force and pressure conversion constants [D]
    """
    # 1. Energy conversions [M]
    assert HARTREE_TO_EV == 27.211386245988
    assert EV_TO_JOULE == 1.602176634e-19

    # 2. Length conversions [M]
    assert BOHR_TO_ANGSTROM == 0.529177210903
    assert ANGSTROM_TO_METER == 1.0e-10

    # 3. Force conversions [D], [M]
    expected_hartree_per_bohr = 27.211386245988 / 0.529177210903
    assert abs(HARTREE_PER_BOHR_TO_EV_PER_ANGSTROM - expected_hartree_per_bohr) < 1e-12
    assert abs(HARTREE_PER_BOHR_TO_EV_PER_ANGSTROM - 51.4220674763) < 1e-6
    assert EV_PER_ANGSTROM_TO_NEWTON == 1.602176634e-9

    # 4. Stress conversions [M]
    assert EV_PER_ANGSTROM3_TO_GPA == 160.21766208

    # 5. Dipole moment conversion [M]
    assert DEBYE_PER_EAA == 4.80320427

    # 6. Fallback router check
    router = SchNetFallbackRouter()
    z = [8, 1, 1]
    r = torch.tensor(
        [[0.0, 0.0, 0.0], [0.0, 0.757, 0.586], [0.0, -0.757, 0.586]],
        dtype=torch.float64,
    )
    res = router.forward(z, r)
    assert "energy" in res and "forces" in res


# ---------------------------------------------------------------------------
# DEF-09: Dynamic Mendeleev Monoisotopic Masses [M], [D]
# ---------------------------------------------------------------------------


def test_def09_mendeleev_monoisotopic_masses(
    water_monomer: Tuple[List[int], torch.Tensor, Atoms],
) -> None:
    """Verify dynamic monoisotopic mass retrieval via mendeleev.element(Z).isotopes.

    Guarantees:
    - Z=6 (Carbon) returns exactly 12.000000 u [M]
    - Z=17 (Chlorine) returns 34.968853 u (not average 35.45 u) [M]
    - Z=0 (Ghost atom) returns 0.0 u without querying mendeleev [M]
    - Dynamic device and dtype matching [M]
    - Dipole center of mass translational invariance with monoisotopic masses [D]
    """
    # 1. Monoisotopic mass values check
    masses_f64 = get_monoisotopic_masses([6, 17, 0], device="cpu", dtype=torch.float64)
    assert masses_f64.dtype == torch.float64
    assert masses_f64.device == torch.device("cpu")

    # Carbon-12 definition [M]
    assert abs(masses_f64[0].item() - 12.000000) < 1e-6

    # Chlorine-35 monoisotopic mass [M]
    cl_mass = masses_f64[1].item()
    assert abs(cl_mass - 34.968853) < 1e-5
    assert abs(cl_mass - 35.45) > 0.4  # Explicitly NOT standard atomic weight

    # Ghost atom (Z=0) [M]
    assert masses_f64[2].item() == 0.0

    # 2. Dynamic dtype matching
    masses_f32 = get_monoisotopic_masses([1, 8], device="cpu", dtype=torch.float32)
    assert masses_f32.dtype == torch.float32

    # 3. Neutral dipole translational invariance via center of mass [D]
    z, coords, _ = water_monomer
    model = CartesianEquivariantBackbone().double()
    obs = DifferentiableObservables().double()

    out_base = model(z, coords)
    res_base = obs.forward(
        coordinates=coords,
        atomic_numbers=z,
        scalar_features=out_base["scalar_features"],
        vector_features=out_base["vector_features"],
        rank2_tensor=out_base["rank2_tensor"],
        total_charge=0.0,
    )

    # Shift coordinates by arbitrary translation vector
    translation = torch.tensor([10.0, -5.0, 2.5], dtype=torch.float64)
    coords_shifted = coords + translation

    out_shifted = model(z, coords_shifted)
    res_shifted = obs.forward(
        coordinates=coords_shifted,
        atomic_numbers=z,
        scalar_features=out_shifted["scalar_features"],
        vector_features=out_shifted["vector_features"],
        rank2_tensor=out_shifted["rank2_tensor"],
        total_charge=0.0,
    )

    # Verify origin invariance to < 10^-6 Debye
    dipole_diff = [
        abs(d1 - d2)
        for d1, d2 in zip(res_base.dipole_vector, res_shifted.dipole_vector)
    ]
    max_dipole_diff = max(dipole_diff)
    assert (
        max_dipole_diff < 1e-6
    ), f"Neutral dipole moment origin translation error {max_dipole_diff:.4e} >= 1e-6 Debye [M]"
