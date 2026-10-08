"""CODATA unit parity and genuine archived derivative transport across BASE boundaries."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from scipy import constants as si

from cochem.core.ingestors import protocols
from cochem_base import cochem_tensor_extractor as tensor
from cochem_base import cochem_torq_alignment as alignment
from cochem_base import cochem_torq_export as export
from cochem_base.calc.recipe_r2_execution import read_dimer_gradient
from cochem_base.core import cochem_constants as registry
from cochem_base.physics.isotopes import get_nuclide_mass
from scripts import oet_client, oet_maceoff


def test_shared_aliases_match_actual_codata_database():
    assert tensor.AMU_KG == registry.ATOMIC_MASS_UNIT_KG == si.physical_constants["atomic mass constant"][0]
    assert tensor.PLANCK_H == registry.PLANCK_CONSTANT_J_S == si.h
    assert tensor.SPEED_OF_LIGHT_CM_S == registry.SPEED_OF_LIGHT_CM_S == si.c * 100
    assert (alignment.INERTIA_CONVERSION_AMU_ANG2_MHZ
            == export.INERTIA_CONVERSION_AMU_ANG2_MHZ
            == tensor.INERTIA_CONVERSION_AMU_ANG2_MHZ
            == registry.C_ROT_MHZ_U_ANG2 == 505379.0084350172)
    assert tensor.INERTIA_CONVERSION_AMU_ANG2_GHZ == registry.C_ROT_MHZ_U_ANG2 / 1000
    assert tensor.INERTIA_CONVERSION_AMU_ANG2_CM1 == registry.C_ROT_MHZ_U_ANG2 * 1e6 / (si.c * 100)


@pytest.mark.parametrize("consumer", [protocols, oet_client, oet_maceoff])
def test_bohr_and_energy_boundaries_have_one_unit_authority(consumer):
    bohr_angstrom = si.physical_constants["Bohr radius"][0] / 1e-10
    hartree_joule = si.physical_constants["Hartree energy"][0]
    assert consumer.BOHR_TO_ANGSTROM == bohr_angstrom
    assert consumer.ANGSTROM_TO_BOHR == 1 / bohr_angstrom
    assert consumer.HARTREE_TO_KCAL_MOL == hartree_joule * si.Avogadro / 4184
    if consumer is protocols:
        assert consumer.HARTREE_TO_WAVENUMBER == hartree_joule / (si.h * (si.c * 100))
    else:
        assert consumer.HARTREE_TO_EV == hartree_joule / si.e
        assert consumer.HARTREE_TO_KJ_MOL == consumer.HARTREE_TO_KCAL_MOL * 4.184
        assert consumer.EV_PER_ANG_TO_EH_PER_BOHR == consumer.BOHR_TO_ANGSTROM / consumer.HARTREE_TO_EV


def test_water_rotor_agrees_in_mhz_ghz_and_wavenumber():
    symbols = ["O", "H", "H"]
    coordinates = np.array([[0., 0., .1173], [0., .7572, -.4692], [0., -.7572, -.4692]], dtype=np.float64)
    original = coordinates.copy()
    masses = np.array([get_nuclide_mass(symbol) for symbol in symbols], dtype=np.float64)
    center = np.average(coordinates, axis=0, weights=masses)
    centered = coordinates - center
    inertia = sum(mass * (np.dot(position, position) * np.eye(3) - np.outer(position, position))
                  for mass, position in zip(masses, centered))
    principal_moments = np.linalg.eigvalsh(inertia)
    expected_mhz = registry.C_ROT_MHZ_U_ANG2 / principal_moments
    result = tensor.diagonalize_inertia_tensor(coordinates, symbols, apply_protection=False)
    aligned = alignment.diagonalize_principal_axes(symbols, coordinates)
    np.testing.assert_allclose(list(result.rotational_constants_mhz.values()), expected_mhz, rtol=1e-12, atol=1e-6)
    np.testing.assert_allclose(aligned["rotational_constants_mhz"], expected_mhz, rtol=1e-12, atol=1e-6)
    np.testing.assert_allclose(list(result.rotational_constants_ghz.values()), expected_mhz / 1000, rtol=1e-12)
    np.testing.assert_allclose(list(result.rotational_constants_cm1.values()), expected_mhz * 1e6 / (si.c * 100), rtol=1e-12)
    np.testing.assert_array_equal(coordinates, original)


def test_real_orca_gradient_survives_codata_force_roundtrip():
    fixture = Path(__file__).parents[1] / "data" / "orca_6_1_1_water_hf_sto3g"
    provenance = json.loads((fixture / "provenance.json").read_text())
    assert hashlib.sha256((fixture / "water.engrad").read_bytes()).hexdigest() == provenance["files"]["water.engrad"]["sha256"]
    rows = (fixture / "water.xyz").read_text().splitlines()[2:]
    symbols = [row.split()[0] for row in rows]
    coordinates = [[float(value) for value in row.split()[1:4]] for row in rows]
    _, measured_gradient = read_dimer_gradient(fixture / "water.engrad", symbols, coordinates)
    forces = oet_client.convert_orca_gradient_to_ase_forces(measured_gradient.reshape(-1).tolist())
    recovered = np.array(oet_client.convert_ase_forces_to_orca_gradient(forces)).reshape(-1, 3)
    np.testing.assert_allclose(recovered, measured_gradient, rtol=1e-15, atol=1e-18)
    assert np.any(measured_gradient != 0)


@pytest.mark.parametrize("consumer", [oet_client, oet_maceoff])
def test_oet_nuclear_mass_is_assigned_or_principal(consumer):
    assert consumer.get_element_atomic_mass("C") == get_nuclide_mass("12C")
    assert consumer.get_element_atomic_mass("C-13") == get_nuclide_mass("13-C")
    assert consumer.get_element_atomic_mass("D") == get_nuclide_mass("2H")
    with pytest.raises(ValueError):
        consumer.get_element_atomic_mass("C999")
