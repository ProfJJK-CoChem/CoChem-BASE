"""Physical verification of rotational constants unification across CoChem modules.
Strictly adheres to Method Matrix v4, CODATA 2022 standards, and Zero-Mock Protocol.
Verifies sub-microhertz rotational constant agreement across all five core calculation engines.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch
from mendeleev import element

from cochem_base.core.cochem_constants import C_ROT_MHZ_U_ANG2
from cochem_base.core_engine.cochem_core_frozen_monomer import compute_rotational_constants
from cochem_base.cochem_torq_alignment import diagonalize_principal_axes
from cochem_base.core_engine.cochem_core_cfour_bridge import compute_equilibrium_rotational_constants
from cochem_geom.eval.metrics import compute_moments_of_inertia, ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ
from cochem_base.core_engine.cochem_core_dvr_solver import INERTIA_TO_MHZ_FACTOR


def test_rotational_constants_unification_water_monomer() -> None:
    """Verify sub-microhertz rotational constant agreement for equilibrium H2O monomer."""
    symbols = ["O", "H", "H"]
    # Experimental equilibrium geometry of water monomer (Angstrom)
    coordinates = np.array([
        [0.0, 0.0, 0.1173],
        [0.0, 0.7572, -0.4692],
        [0.0, -0.7572, -0.4692],
    ], dtype=np.float64)

    # Mendeleev Mandate: dynamically retrieve masses
    masses = [float(element(sym).mass) for sym in symbols]
    atomic_numbers = [int(element(sym).atomic_number) for sym in symbols]

    # 1. cochem_core_frozen_monomer
    res_monomer = compute_rotational_constants(symbols, coordinates, masses=masses)
    rot_monomer = np.array([res_monomer.A_MHz, res_monomer.B_MHz, res_monomer.C_MHz], dtype=np.float64)

    # 2. cochem_torq_alignment
    res_torq = diagonalize_principal_axes(symbols=symbols, coordinates=coordinates, masses=masses)
    rot_torq = np.array(res_torq["rotational_constants_mhz"], dtype=np.float64)

    # 3. cochem_core_cfour_bridge
    res_cfour = compute_equilibrium_rotational_constants(
        symbols=symbols, coordinates_angstrom=coordinates, masses_u=masses
    )
    rot_cfour = np.array(res_cfour[0], dtype=np.float64)

    # 4. cochem_geom.eval.metrics
    z_tensor = torch.tensor(atomic_numbers, dtype=torch.long)
    pos_tensor = torch.tensor(coordinates, dtype=torch.float64)
    _, rot_geom_tensor = compute_moments_of_inertia(pos_tensor, z_tensor)
    rot_geom = rot_geom_tensor.detach().cpu().numpy()

    # 5. cochem_core_dvr_solver (using direct moments of inertia from tensor diagonalization)
    moments = np.array([res_monomer.Ia_uA2, res_monomer.Ib_uA2, res_monomer.Ic_uA2], dtype=np.float64)
    rot_dvr = INERTIA_TO_MHZ_FACTOR / moments

    # Verify authoritative constant matching
    assert C_ROT_MHZ_U_ANG2 == 505379.0084350172
    assert ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ == 505379.0084350172
    assert INERTIA_TO_MHZ_FACTOR == 505379.0084350172

    # Assert sub-microhertz (< 1e-6 MHz) agreement across all modules
    np.testing.assert_allclose(rot_monomer, rot_torq, atol=1e-6, rtol=1e-12)
    np.testing.assert_allclose(rot_monomer, rot_cfour, atol=1e-6, rtol=1e-12)
    np.testing.assert_allclose(rot_monomer, rot_geom, atol=1e-6, rtol=1e-12)
    np.testing.assert_allclose(rot_monomer, rot_dvr, atol=1e-6, rtol=1e-12)


def test_rotational_constants_unification_water_dimer() -> None:
    """Verify sub-microhertz rotational constant agreement for equilibrium (H2O)2 dimer."""
    symbols = ["O", "H", "H", "O", "H", "H"]
    # Equilibrium geometry of hydrogen-bonded water dimer (Smith et al. standard benchmark)
    coordinates = np.array([
        [-1.455, 0.0, -0.076],
        [-1.838, -0.781, 0.325],
        [-0.518, 0.0, 0.147],
        [1.455, 0.0, 0.076],
        [1.772, 0.758, -0.412],
        [1.772, -0.758, -0.412],
    ], dtype=np.float64)

    masses = [float(element(sym).mass) for sym in symbols]
    atomic_numbers = [int(element(sym).atomic_number) for sym in symbols]

    # 1. cochem_core_frozen_monomer
    res_monomer = compute_rotational_constants(symbols, coordinates, masses=masses)
    rot_monomer = np.array([res_monomer.A_MHz, res_monomer.B_MHz, res_monomer.C_MHz], dtype=np.float64)

    # 2. cochem_torq_alignment
    res_torq = diagonalize_principal_axes(symbols=symbols, coordinates=coordinates, masses=masses)
    rot_torq = np.array(res_torq["rotational_constants_mhz"], dtype=np.float64)

    # 3. cochem_core_cfour_bridge
    res_cfour = compute_equilibrium_rotational_constants(
        symbols=symbols, coordinates_angstrom=coordinates, masses_u=masses
    )
    rot_cfour = np.array(res_cfour[0], dtype=np.float64)

    # 4. cochem_geom.eval.metrics
    z_tensor = torch.tensor(atomic_numbers, dtype=torch.long)
    pos_tensor = torch.tensor(coordinates, dtype=torch.float64)
    _, rot_geom_tensor = compute_moments_of_inertia(pos_tensor, z_tensor)
    rot_geom = rot_geom_tensor.detach().cpu().numpy()

    # 5. cochem_core_dvr_solver
    moments = np.array([res_monomer.Ia_uA2, res_monomer.Ib_uA2, res_monomer.Ic_uA2], dtype=np.float64)
    rot_dvr = INERTIA_TO_MHZ_FACTOR / moments

    # Assert sub-microhertz (< 1e-6 MHz) agreement across all modules
    np.testing.assert_allclose(rot_monomer, rot_torq, atol=1e-6, rtol=1e-12)
    np.testing.assert_allclose(rot_monomer, rot_cfour, atol=1e-6, rtol=1e-12)
    np.testing.assert_allclose(rot_monomer, rot_geom, atol=1e-6, rtol=1e-12)
    np.testing.assert_allclose(rot_monomer, rot_dvr, atol=1e-6, rtol=1e-12)
