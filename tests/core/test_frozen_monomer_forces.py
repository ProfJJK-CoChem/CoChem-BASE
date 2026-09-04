"""Unit tests for Frozen Monomer Rigid-Body Force Decoupling & Strain Thresholding.
Method Matrix v4 §9A.1, §9A.7 Rule 8, and Zero-Mock Protocol Compliance.
"""

import math
import numpy as np
import pytest
from mendeleev import element

from cochem_base.core_engine.cochem_core_frozen_monomer import (
    check_frozen_residual_gradients,
    ResidualGradientCheck,
    TOL_MAXG_DEFAULT,
)


def _get_element_mass(sym: str) -> float:
    """Dynamically retrieves atomic mass in unified atomic mass units (u) via Mendeleev Mandate."""
    return float(element(sym).atomic_weight)


def test_frozen_monomer_rigid_body_force_decoupling_and_strain() -> None:
    """Verifies that non-zero Cartesian atomic forces in an equilibrium dimer decompose

    into zero net force and torque, and that Delta E_def < 1.0 kcal/mol passes validation.
    """
    symbols = ["O", "H", "H", "O", "H", "H"]
    masses = [_get_element_mass(s) for s in symbols]

    # Authentic water dimer coordinates in Angstroms
    coords = np.array([
        [0.0, 0.0, 0.0],       # O1
        [0.0, 0.757, 0.586],    # H1
        [0.0, -0.757, 0.586],   # H2
        [0.0, 0.0, 2.95],      # O2
        [0.757, 0.0, 3.536],    # H3
        [-0.757, 0.0, 3.536],   # H4
    ], dtype=np.float64)

    # Monomer A indices: atoms 0, 1, 2
    frozen_indices = [0, 1, 2]

    # Monomer A center of mass in bohr
    ang2bohr = 1.8897261246257702
    coords_bohr = coords[:3] * ang2bohr
    m_A = np.array(masses[:3], dtype=np.float64)
    com_bohr = np.sum(coords_bohr * m_A[:, np.newaxis], axis=0) / np.sum(m_A)
    delta_r = coords_bohr - com_bohr

    # Construct genuine non-zero Cartesian atomic gradients representing intermolecular forces
    # in an equilibrium dimer (where net intermolecular force and torque on monomer A vanish):
    # Let H1 and H2 experience equal and opposite local interaction forces with O2:
    # f_H1 = [0.0,  0.0015, -0.0008] Eh/bohr
    # f_H2 = [0.0, -0.0015, -0.0008] Eh/bohr
    # f_O1 = [0.0,  0.0000,  0.0016] Eh/bohr
    # Net force: f_H1 + f_H2 + f_O1 = [0, 0, 0]
    # Net torque around COM: sum_i delta_r_i x f_i = [0, 0, 0] by symmetry
    f_O1 = np.array([0.0, 0.0, 0.0016], dtype=np.float64)
    f_H1 = np.array([0.0, 0.0015, -0.0008], dtype=np.float64)
    f_H2 = np.array([0.0, -0.0015, -0.0008], dtype=np.float64)

    # Verify mathematical equilibrium of the constructed force field
    f_net = f_O1 + f_H1 + f_H2
    assert np.allclose(f_net, np.full(3, 0.0), atol=1e-15), "Constructed forces must have zero net force"
    tau_net = (
        np.cross(delta_r[0], f_O1) +
        np.cross(delta_r[1], f_H1) +
        np.cross(delta_r[2], f_H2)
    )
    assert np.allclose(tau_net, np.full(3, 0.0), atol=1e-15), "Constructed forces must have zero net torque"

    # Assemble full complex Cartesian gradient (6 atoms, 3 dimensions)
    full_grad = np.array([
        f_O1,
        f_H1,
        f_H2,
        -f_O1,
        -f_H1,
        -f_H2,
    ], dtype=np.float64)

    # Note: Local Cartesian gradients on atoms exceed TolMaxG (1e-5 Eh/bohr) significantly:
    assert np.max(np.abs(full_grad[frozen_indices])) > 1e-3

    # Case 1: Monomer internal deformation energy is within Method Matrix §9A.1 threshold (0.35 kcal/mol <= 1.0 kcal/mol)
    delta_e_def_physical = 0.35  # typical water monomer deformation in dimer
    check_pass = check_frozen_residual_gradients(
        gradient_cartesian_eh_bohr=full_grad,
        frozen_atom_indices=frozen_indices,
        tol_max_g=TOL_MAXG_DEFAULT,
        coordinates_angstrom=coords,
        masses=masses,
        delta_e_def_kcal_mol=delta_e_def_physical,
        tol_e_def_kcal_mol=1.0,
    )

    assert check_pass.passes_gate is True, "Equilibrium dimer stationary point must pass gate"
    assert check_pass.deformation_channel_flag is False
    assert check_pass.warning_message is None
    assert check_pass.net_force_norm is not None and check_pass.net_force_norm < 1e-12
    assert check_pass.net_torque_norm is not None and check_pass.net_torque_norm < 1e-12
    assert check_pass.delta_e_def_kcal_mol == delta_e_def_physical

    # Case 2: Monomer internal deformation energy exceeds Method Matrix threshold (2.5 kcal/mol > 1.0 kcal/mol)
    delta_e_def_excessive = 2.50
    check_fail = check_frozen_residual_gradients(
        gradient_cartesian_eh_bohr=full_grad,
        frozen_atom_indices=frozen_indices,
        tol_max_g=TOL_MAXG_DEFAULT,
        coordinates_angstrom=coords,
        masses=masses,
        delta_e_def_kcal_mol=delta_e_def_excessive,
        tol_e_def_kcal_mol=1.0,
    )

    assert check_fail.passes_gate is False, "Excessive deformation strain must be flagged"
    assert check_fail.deformation_channel_flag is True
    assert check_fail.warning_message is not None
    assert "[METHOD_MATRIX_WARNING: DEFORMATION_CHANNEL_ACTIVE]" in check_fail.warning_message

    # Case 3: When deformation energy is not supplied, rigid-body equilibrium passes gate
    check_eq = check_frozen_residual_gradients(
        gradient_cartesian_eh_bohr=full_grad,
        frozen_atom_indices=frozen_indices,
        tol_max_g=TOL_MAXG_DEFAULT,
        coordinates_angstrom=coords,
        masses=masses,
        delta_e_def_kcal_mol=None,
    )
    assert check_eq.passes_gate is True, "Rigid body equilibrium (F_net=0, tau_net=0) must pass gate"
    assert check_eq.deformation_channel_flag is False
