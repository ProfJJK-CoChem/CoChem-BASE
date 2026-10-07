"""Replay actual native ORCA derivatives and reject explicitly corrupted copies.

The versioned fixture records its native input, complete output, engine identity
and file hashes. These parser tests do not pretend to execute the engine.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from cochem_base.calc.calculation_service import CalculationMatrixConfig, parse_run_geometry
from cochem_base.calc.orca_derivatives import accept_gradient, accept_harmonic_hessian
from cochem_base.chain.chain import CorruptOutputError, parse_orca_hessian
from cochem_base.interfaces.scientific_jobs import calculation_capability
from cochem_base.spectroscopy.isotopologue import get_nuclide_mass


NATIVE = Path(__file__).resolve().parents[1] / "data/orca_6_1_1_water_hf_sto3g"
ENERGY = -74.965901192193


@pytest.fixture
def native(tmp_path):
    source = json.loads((NATIVE / "provenance.json").read_text())
    assert source["engine"] == "ORCA" and source["version"] == "6.1.1"
    # Work only on private copies: artifact locking must not touch test sources.
    for name, record in source["files"].items():
        original = NATIVE / name
        assert hashlib.sha256(original.read_bytes()).hexdigest() == record["sha256"]
        shutil.copyfile(original, tmp_path / name)
    elements, coordinates = parse_run_geometry((tmp_path / "water.xyz").read_text())
    return tmp_path, elements, np.asarray(coordinates)


def test_native_orca_hessian_comments_are_not_parsed_as_numeric_rows(native):
    path, _, _ = native
    parsed = parse_orca_hessian(path / "water.hess")
    assert parsed["hessian"].shape == parsed["normal_modes"].shape == (9, 9)
    assert [atom["symbol"] for atom in parsed["atoms"]] == ["O", "H", "H"]
    assert len(parsed["frequencies"]) == 9


def test_genuine_harmonic_artifact_retains_native_and_principal_mass_results(native):
    path, elements, coordinates = native
    result = accept_harmonic_hessian(path / "water.hess", path / "water.out.txt", elements, coordinates, optimized=True)
    evidence = result["hessian_artifact"]
    assert evidence["shape"] == [9, 9] and evidence["unit"] == "hartree/bohr^2"
    assert evidence["rigid_mode_count"] == 6
    assert evidence["native_spectrum_max_difference_cm1"] < 0.001
    assert evidence["geometry_alignment_max_deviation_angstrom"] < 1e-7
    assert abs(evidence["native_to_final_translation_angstrom"][2]) > 0.02
    assert result["principal_isotope_masses_u"] == [get_nuclide_mass(symbol) for symbol in elements]
    assert len(result["harmonic_frequencies_cm1"]) == 3
    assert not np.allclose(result["harmonic_frequencies_cm1"], evidence["native_vibrational_frequencies_cm1"])
    assert evidence["scientific_accuracy_established"] is False


def test_native_hessian_geometry_binding_accepts_only_proper_rigid_frame_changes(native):
    path, elements, coordinates = native
    rotation = Rotation.from_rotvec([0.4, -0.2, 0.3]).as_matrix()
    transformed = coordinates @ rotation.T + np.asarray([1.3, -0.4, 2.1])
    result = accept_harmonic_hessian(path / "water.hess", path / "water.out.txt", elements, transformed, optimized=True)
    assert result["hessian_artifact"]["geometry_alignment_max_deviation_angstrom"] < 1e-7
    assert np.linalg.det(result["hessian_artifact"]["native_to_final_rotation"]) == pytest.approx(1.0)
    changed = coordinates.copy()
    changed[1, 1] += 1e-3
    with pytest.raises(ValueError, match="final geometry"):
        accept_harmonic_hessian(path / "water.hess", path / "water.out.txt", elements, changed, optimized=True)


def test_hessian_atom_order_and_missing_file_are_rejected(native):
    path, elements, coordinates = native
    with pytest.raises(ValueError, match="atom identities/order"):
        accept_harmonic_hessian(path / "water.hess", path / "water.out.txt", elements[::-1], coordinates, optimized=True)
    with pytest.raises(ValueError, match="actual ORCA .hess"):
        accept_harmonic_hessian(path / "absent.hess", path / "water.out.txt", elements, coordinates, optimized=True)


@pytest.mark.parametrize("mutation", ["missing_spectrum", "truncated_spectrum", "inconsistent_matrix"])
def test_corrupt_native_hessian_cannot_become_accepted_frequency_result(native, mutation):
    path, elements, coordinates = native
    hessian = path / "water.hess"
    content = hessian.read_text()
    if mutation == "missing_spectrum":
        first, remainder = content.split("$vibrational_frequencies", 1)
        content = first + "$normal_modes" + remainder.split("$normal_modes", 1)[1]
    elif mutation == "truncated_spectrum":
        content = content.replace("    8     4390.6590448484366789\n", "")
    else:
        content = content.replace("8.0394251423E-01", "9.0394251423E-01", 1)
    hessian.write_text(content)
    with pytest.raises((ValueError, CorruptOutputError)):
        accept_harmonic_hessian(hessian, path / "water.out.txt", elements, coordinates, optimized=True)


def test_native_output_and_hessian_spectra_must_agree(native):
    path, elements, coordinates = native
    log = path / "water.out.txt"
    log.write_text(log.read_text().replace("2169.82 cm**-1", "2269.82 cm**-1"))
    with pytest.raises(ValueError, match="completed output spectrum"):
        accept_harmonic_hessian(path / "water.hess", log, elements, coordinates, optimized=True)


def test_genuine_gradient_requires_matching_energy_and_final_geometry(native):
    path, elements, coordinates = native
    accepted = accept_gradient(path / "water.engrad", elements, coordinates, ENERGY, required=True)
    gradient = np.asarray(accepted["gradients_hartree_per_bohr"])
    assert gradient.shape == (3, 3) and np.isfinite(gradient).all()
    assert accepted["gradient_artifact"]["unit"] == "hartree/bohr"
    with pytest.raises(ValueError, match="energy differs"):
        accept_gradient(path / "water.engrad", elements, coordinates, ENERGY + 1e-3, required=True)
    with pytest.raises(ValueError, match="final geometry"):
        accept_gradient(path / "water.engrad", elements, coordinates + 1, ENERGY, required=True)
    with pytest.raises(ValueError, match="requires its final .engrad"):
        accept_gradient(path / "missing.engrad", elements, coordinates, ENERGY, required=True)
    assert accept_gradient(path / "missing.engrad", elements, coordinates, ENERGY, required=False) == {}


def test_harmonic_operation_is_connected_but_vpt2_remains_pending():
    config = CalculationMatrixConfig(geometry="H 0 0 0\nH 0 0 0.74", engine="orca", is_freq=True)
    capability = calculation_capability(config)
    assert capability.operation == "harmonic_frequencies" and capability.adapter_status == "connected"
    capability = calculation_capability(config.model_copy(update={"is_vpt2": True}))
    assert capability.operation == "vpt2" and capability.adapter_status == "pending_integration"


@pytest.mark.parametrize("keyword", ["Freq", "NumFreq", "VPT2", "AnFreq", "Opt", "TightOpt", "OptTS"])
def test_embedded_operation_keywords_cannot_bypass_declared_acceptance_scope(keyword):
    with pytest.raises(ValueError, match="require"):
        CalculationMatrixConfig(geometry="H 0 0 0\nH 0 0 0.74", engine="orca",
                                method=f"HF {keyword}", is_opt=False, is_freq=False, is_vpt2=False)
