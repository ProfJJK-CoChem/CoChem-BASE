"""Replay unmodified real ORCA derivatives; no fresh-engine or accuracy claim."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import shutil
import zipfile

import h5py

import numpy as np
import pytest

from cochem_base.core.cochem_constants import C_ROT_MHZ_U_ANG2, SPEED_OF_LIGHT_CM_S
from cochem_base.spectroscopy.artifacts import load_hessian_artifact, qualify_native_hessian
from cochem_base.spectroscopy.isotopologue import IsotopologueSpectroscopyEngine
from cochem_base.spectroscopy.parser import SpectroscopyTelemetryParser

FIXTURE = Path(__file__).parents[1] / "data" / "orca_6_1_1_water_hf_sto3g"


def test_actual_orca_611_property_output_units_frame_and_missing_b0():
    provenance = json.loads((FIXTURE / "provenance.json").read_text())
    result = SpectroscopyTelemetryParser().parse_file(FIXTURE / "water.out.txt")
    assert result.source_sha256 == provenance["files"]["water.out.txt"]["sha256"]
    assert (result.a_e, result.b_e, result.c_e) == (698269.660196, 436210.534019, 268486.468884)
    assert result.total_dipole == 1.709241821
    assert result.dipole_components == (0.0, 1.709242, 0.0)
    assert result.dipole_component_frame == "reported rotational principal axes"
    assert result.a_0 is result.b_0 is result.c_0 is None
    assert result.equilibrium_geometry_verified is False
    assert result.i_a == C_ROT_MHZ_U_ANG2 / result.a_e


def test_actual_cfour_native_axis_triplet_preserves_mapping_and_debye_column():
    directory = FIXTURE.parent / "cfour_2_1_water_hf_sto3g"
    provenance = json.loads((directory / "provenance.json").read_text())
    result = SpectroscopyTelemetryParser().parse_file(directory / "water.out.txt")
    assert result.source_sha256 == provenance["files"]["water.out.txt"]["sha256"]
    assert result.engine == "cfour"
    assert result.reported_rotational_constants == (268534.2964654386, 698398.9627985370, 436286.3217559056)
    assert result.reported_axis_order == ("C", "A", "B")
    assert (result.a_e, result.b_e, result.c_e) == (698398.9627985370, 436286.3217559056, 268534.2964654386)
    assert result.total_dipole == 1.70920815
    assert result.dipole_component_frame == "reported native Cartesian axes"
    assert not result.equilibrium_geometry_verified and result.b_0 is None


@pytest.mark.parametrize("unit,factor", [("GHz", 1000), ("cm**-1", SPEED_OF_LIGHT_CM_S / 1e6)])
def test_explicit_unit_grammar_conversion_does_not_claim_equilibrium(unit, factor):
    # Unit grammar/arithmetic, not a purported chemical calculation output.
    result = SpectroscopyTelemetryParser().parse_log_content(f"Rotational constants in {unit} : 3D0 2D0 1D0")
    assert (result.a_e, result.b_e, result.c_e) == (3 * factor, 2 * factor, factor)
    assert result.equilibrium_geometry_verified is False
    assert result.total_dipole is None


def test_unlabelled_atomic_unit_dipole_vector_never_becomes_debye_magnitude():
    result = SpectroscopyTelemetryParser().parse_log_content(
        "Rotational constants in MHz : 3 2 1\nTotal Dipole Moment : 0.3 0.2 0.1\n"
        "X = 0.3 Y = 0.2 Z = 0.1\nMagnitude (a.u.) : 0.3741657")
    assert result.total_dipole is None and result.dipole_components is None


def _replay_native_derivative_acceptance(tmp_path):
    from cochem_base.calc.orca_derivatives import accept_gradient, accept_harmonic_hessian
    from cochem_base.calc.recipe_r2_execution import read_dimer_gradient

    for name in ("water.hess", "water.engrad", "water.xyz", "water.out.txt"):
        shutil.copyfile(FIXTURE / name, tmp_path / name)
    rows = (tmp_path / "water.xyz").read_text().splitlines()[2:]
    elements = [row.split()[0] for row in rows]
    coordinates = np.asarray([[float(value) for value in row.split()[1:4]] for row in rows])
    energy, _ = read_dimer_gradient(tmp_path / "water.engrad", elements, coordinates)
    assert "ORCA TERMINATED NORMALLY" in (tmp_path / "water.out.txt").read_text()
    result = {"engine": "orca", "method": "HF", "converged": True, "elements": elements,
              "coordinates_angstrom": coordinates.tolist(), "energy_hartree": energy,
              "optimization_performed": True}
    result.update(accept_gradient(tmp_path / "water.engrad", elements, coordinates, energy, required=True))
    result.update(accept_harmonic_hessian(tmp_path / "water.hess", tmp_path / "water.out.txt",
                                        elements, coordinates, optimized=True))
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(result, allow_nan=False))
    return result, result_path


def test_real_native_receipts_qualify_minimum_without_modifying_source(tmp_path):
    result, result_path = _replay_native_derivative_acceptance(tmp_path)
    path = tmp_path / "water.hess"
    original = path.read_bytes()
    artifact = load_hessian_artifact(path)
    qualification = artifact.qualification
    assert qualification["physical_hessian_verified"] is True
    assert qualification["stationary_geometry_verified"] is True
    assert qualification["minimum_verified"] is True
    assert qualification["scientific_accuracy_established"] is False
    assert path.read_bytes() == original
    assert qualification["native_result_sha256"] == hashlib.sha256(result_path.read_bytes()).hexdigest()
    engine = IsotopologueSpectroscopyEngine(list(artifact.symbols), artifact.coordinates_angstrom,
                                            artifact.hessian_hartree_bohr2,
                                            hessian_qualification=qualification)
    heavy = engine.compute_observables({1: "2H", 2: "2H"})
    assert heavy.physical_hessian_verified and heavy.equilibrium_geometry_verified
    assert len(heavy.harmonic_frequencies_cm1) == 3 and min(heavy.harmonic_frequencies_cm1) > 0
    assert heavy.B_0_MHz is None
    # A file name or a positive spectrum is not a substitute for measured
    # stationarity. Removing the native optimization receipt removes B_e scope.
    result["optimization_performed"] = False
    result_path.write_text(json.dumps(result, allow_nan=False))
    frequency_only = load_hessian_artifact(path)
    assert frequency_only.qualification["physical_hessian_verified"] is True
    assert frequency_only.qualification["stationary_geometry_verified"] is False
    assert frequency_only.qualification["minimum_verified"] is False


def test_modified_native_gradient_or_tensor_cannot_retain_minimum_qualification(tmp_path):
    _, result_path = _replay_native_derivative_acceptance(tmp_path)
    artifact = load_hessian_artifact(tmp_path / "water.hess")
    gradient = tmp_path / "water.engrad"
    gradient.write_text(gradient.read_text() + "\nmodified\n")
    with pytest.raises(ValueError, match="checksum"):
        qualify_native_hessian(artifact, result_path)
    assert load_hessian_artifact(artifact.path).qualification["minimum_verified"] is False


def test_standalone_native_tensor_stays_supplied_without_stationarity_receipt(tmp_path):
    shutil.copyfile(FIXTURE / "water.hess", tmp_path / "water.hess")
    artifact = load_hessian_artifact(tmp_path / "water.hess")
    assert artifact.qualification["physical_hessian_verified"] is False
    assert artifact.qualification["stationary_geometry_verified"] is False
    result = IsotopologueSpectroscopyEngine(list(artifact.symbols), artifact.coordinates_angstrom,
                                           artifact.hessian_hartree_bohr2).compute_observables()
    assert result.physical_hessian_verified is False
    assert result.equilibrium_geometry_verified is False
    assert "supplied Cartesian tensor" in result.harmonic_frequency_scope


def test_huge_declared_hessian_shape_is_rejected_before_allocating(tmp_path):
    path = tmp_path / "hostile.npz"
    header = io.BytesIO()
    np.lib.format.write_array_header_1_0(header, {"descr": "<f8", "fortran_order": False, "shape": (10**12,)})
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("hessian_hartree_bohr2.npy", header.getvalue())
    with pytest.raises(ValueError, match="logical memory bounds"):
        load_hessian_artifact(path)


def test_sparse_hdf5_hessian_cannot_bypass_logical_memory_bound(tmp_path):
    path = tmp_path / "hostile.h5"
    with h5py.File(path, "w") as archive:
        archive["symbols"] = np.asarray(["O"], dtype="S")
        archive["coordinates_angstrom"] = np.zeros((1, 3))
        archive.create_dataset("hessian_hartree_bohr2", (10**6, 10**6), dtype="f8", chunks=(10, 10))
        archive["source"] = np.bytes_("Supplied tensor")
    with pytest.raises(ValueError, match="logical memory bounds"):
        load_hessian_artifact(path)

