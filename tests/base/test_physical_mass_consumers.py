"""Task1/proposal16: shipped mass consumers preserve physical nuclear identity."""
from __future__ import annotations
import importlib
import json
import h5py
import numpy as np
import pytest
from mendeleev import element

CONSUMERS = (
    ("core_engine.cochem_core_dvr_solver", "get_dynamic_mass"),
    ("core_engine.cochem_core_pes_store", "get_atomic_mass"),
    ("core_engine.hetero_config", "get_atomic_mass"),
    ("core_engine.cochem_core_cfour_bridge", "get_dynamic_atomic_mass"),
    ("core_engine.cochem_core_frozen_monomer", "get_dynamic_atomic_mass"),
    ("core_engine.cochem_core_auto_pes", "get_dynamic_atomic_mass"),
    ("orchestrator.cochem_gpu_crossover_bench", "get_dynamic_atomic_mass"),
    ("orchestrator.cochem_setup_phase_10", "get_physical_mass"),
)

@pytest.mark.parametrize("module_name,function_name", CONSUMERS)
def test_numerical_mass_consumers_do_not_average_or_estimate_isotopes(module_name, function_name):
    getter = getattr(importlib.import_module("cochem_base." + module_name), function_name)
    for label, symbol, number in (("C", "C", 12), ("13C", "C", 13), ("C-13", "C", 13), ("D", "H", 2), ("T", "H", 3)):
        measured = next(isotope.mass for isotope in element(symbol).isotopes if isotope.mass_number == number)
        assert getter(label) == measured
    with pytest.raises((ValueError, RuntimeError)):
        getter("C999")


def test_phase6_archive_preserves_exact_isotope_identity_and_rejects_unknown_before_creation(tmp_path):
    from cochem_base.orchestrator.cochem_setup_phase_6 import DatabaseProvisioningError, provision_archive_pes_db
    path = tmp_path / "archive.h5"
    labels = ["18O", "D", "H"]
    provision_archive_pes_db(path, symbols=labels)
    with h5py.File(path, "r") as handle:
        identity = json.loads(handle["meta"].attrs["nuclear_identity_json"])
        assert identity["nuclides"] == ["18O", "2H", "H"]
        assert identity["mass_convention"] == "explicit_isotope_mass_else_principal_isotope_mass"
        np.testing.assert_array_equal(handle["meta"].attrs["atomic_masses"], identity["masses_u"])
        np.testing.assert_array_equal(handle["meta"].attrs["atomic_numbers"], [8, 1, 1])
    rejected = tmp_path / "unknown.h5"
    with pytest.raises(DatabaseProvisioningError):
        provision_archive_pes_db(rejected, symbols=["C999"])
    assert not rejected.exists()


def test_cfour_mass_number_does_not_round_an_average_or_forget_assignment():
    from cochem_base.core_engine.cochem_core_cfour_bridge import get_default_isotope_mass_number, get_dynamic_atomic_mass
    assert get_default_isotope_mass_number("D") == 2
    assert get_default_isotope_mass_number("C-13") == 13
    assert get_default_isotope_mass_number(6) == 12
    with pytest.raises(ValueError):
        get_default_isotope_mass_number("Tc")
    with pytest.raises(ValueError):
        get_dynamic_atomic_mass("C", 999)



def test_phase6_keeps_named_ghost_basis_parent_and_zero_nuclear_contribution(tmp_path):
    from cochem_base.orchestrator.cochem_setup_phase_6 import provision_archive_pes_db
    path = tmp_path / "counterpoise.h5"
    provision_archive_pes_db(path, symbols=["H", "Gh_C"])
    with h5py.File(path, "r") as handle:
        identity = json.loads(handle["meta"].attrs["nuclear_identity_json"])
        assert identity["nuclides"] == ["H", "Gh_C"]
        assert identity["masses_u"][1] == 0.0
        assert handle["meta"].attrs["atomic_numbers"].tolist() == [1, 0]



def test_declared_basis_center_has_zero_translational_and_angular_contribution():
    from cochem_base.physics.eckart_aligner import (
        compute_mass_weighted_covariance_matrix, translate_to_center_of_mass, verify_com_residual,
    )
    from cochem_base.physics.isotopes import get_nuclide_mass, ZeroMassSystemError
    labels = ["H", "D", "Gh_C"]
    geometry = np.asarray([[0., 0., 0.], [0., 0., .74], [20., -30., 5.]])
    centered, center = translate_to_center_of_mass(geometry, symbols=labels)
    masses = np.asarray([get_nuclide_mass(label) for label in labels])
    assert verify_com_residual(centered, masses, tol=1e-12) < 1e-12
    assert center[2] > .4
    changed = geometry.copy()
    changed[2] = [-100., 100., 0.]
    _, alternate_center = translate_to_center_of_mass(changed, symbols=labels)
    np.testing.assert_array_equal(center, alternate_center)
    covariance = compute_mass_weighted_covariance_matrix(geometry, geometry, masses=masses[:, None], symbols=labels)
    altered = compute_mass_weighted_covariance_matrix(changed, changed, masses=masses[:, None], symbols=labels)
    np.testing.assert_allclose(covariance, altered, atol=1e-12, rtol=0)
    np.testing.assert_array_equal(np.cross(centered[2], centered[2] * masses[2]), [0., 0., 0.])
    with pytest.raises(ZeroMassSystemError):
        translate_to_center_of_mass(geometry[:1], symbols=["Gh_C"])
