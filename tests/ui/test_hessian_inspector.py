"""Real ASE/EMT force Hessians validate UI transport, not ab-initio accuracy."""
from __future__ import annotations

import hashlib

import h5py
import numpy as np
import pytest
from ase.build import molecule
from ase.calculators.emt import EMT
from ase.optimize import BFGS
from ase.units import Bohr, Hartree
from ase.vibrations import Vibrations

from cochem_base.spectroscopy.artifacts import load_hessian_artifact
from cochem_base.spectroscopy.parser import read_hdf5_dataset_previews
from ui.voila_layout.cochem_gui import CoChemGUI


@pytest.fixture(scope="module")
def physical_bundle(tmp_path_factory):
    directory = tmp_path_factory.mktemp("inspector-hessian")
    atoms = molecule("H2O")
    atoms.calc = EMT()
    assert BFGS(atoms, logfile=None).run(fmax=1e-8, steps=200)
    vibrations = Vibrations(atoms, name=str(directory / "vib"))
    vibrations.run()
    payload = {
        "symbols": np.asarray(atoms.get_chemical_symbols()),
        "coordinates_angstrom": atoms.positions,
        "hessian_hartree_bohr2": vibrations.get_vibrations().get_hessian_2d() * Bohr**2 / Hartree,
        "source": np.asarray("ASE/EMT finite-difference Hessian; not an ab-initio accuracy reference"),
    }
    path = directory / "water.npz"
    np.savez(path, **payload)
    return path, payload


def test_npz_hessian_preserves_units_geometry_and_provenance(physical_bundle):
    path, payload = physical_bundle
    artifact = load_hessian_artifact(path)
    assert artifact.symbols == tuple(payload["symbols"])
    np.testing.assert_array_equal(artifact.hessian_hartree_bohr2, payload["hessian_hartree_bohr2"])
    np.testing.assert_array_equal(artifact.coordinates_angstrom, payload["coordinates_angstrom"])
    assert artifact.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert not artifact.hessian_hartree_bohr2.flags.writeable


def test_hdf5_bundle_and_missing_provenance(physical_bundle, tmp_path):
    _, payload = physical_bundle
    path = tmp_path / "water.h5"
    with h5py.File(path, "w", libver="latest") as handle:
        for key, value in payload.items():
            handle[key] = value.astype("S") if value.dtype.kind == "U" else value
    assert load_hessian_artifact(path).symbols == ("O", "H", "H")


def test_missing_geometry_or_source_never_becomes_valid_hessian(physical_bundle, tmp_path):
    _, payload = physical_bundle
    for missing in ("coordinates_angstrom", "source"):
        path = tmp_path / f"missing-{missing}.npz"
        np.savez(path, **{key: value for key, value in payload.items() if key != missing})
        with pytest.raises(ValueError, match="requires datasets"):
            load_hessian_artifact(path)


def test_nested_hdf5_previews_bound_read_and_preserve_units(physical_bundle, tmp_path):
    _, payload = physical_bundle
    path = tmp_path / "nested.h5"
    hessian = payload["hessian_hartree_bohr2"]
    with h5py.File(path, "w", libver="latest") as handle:
        dataset = handle.create_dataset("jobs/water/hessian", data=hessian)
        dataset.attrs["units"] = "Hartree/bohr^2"
        dataset.attrs["source"] = str(payload["source"])
    preview, = read_hdf5_dataset_previews(path, limit=5)
    assert preview["name"] == "jobs/water/hessian"
    assert preview["shape"] == (9, 9)
    assert preview["shown"] == 5 and preview["total"] == 81
    assert preview["units"] == "Hartree/bohr^2"
    np.testing.assert_array_equal(preview["values"], hessian[:1, :5])


def test_gui_selects_multiple_isotopes_and_reuses_real_hessian(physical_bundle):
    path, _ = physical_bundle
    gui = CoChemGUI()
    gui.isotope_hessian_path.value = str(path)
    gui._on_load_hessian_clicked(None)
    assert gui._isotope_hessian_data is not None, gui.isotope_hessian_status.value
    gui.isotope_selectors[0].value = "18O"
    gui.isotope_selectors[1].value = "2H"
    gui.isotope_selectors[2].value = "2H"
    gui._on_run_isotope_reanalysis_clicked(None)
    result = gui.isotope_results_table.value
    assert "Substituted (18O2H2H)" in result
    assert "Projected harmonic modes" in result
    assert "Rigid modes removed: 6" in result
    assert "B0 is [MISSING DATA]" in result
    assert "ASE/EMT" in result
    assert gui._isotope_hessian_data.sha256 in result
    assert "Download SVG figure" in gui.isotope_modes_plot.value
    assert "Download frequency data (CSV)" in gui.isotope_modes_plot.value
    gui.matrix_geometry.value = gui.matrix_geometry.value.replace("O ", "O 1.0 ", 1)
    gui._on_run_isotope_reanalysis_clicked(None)
    assert "failed" in gui.isotope_results_table.value.lower()


def test_gui_rejects_hessian_after_valid_geometry_change(physical_bundle):
    path, _ = physical_bundle
    gui = CoChemGUI()
    gui.isotope_hessian_path.value = str(path)
    gui._on_load_hessian_clicked(None)
    rows = gui.matrix_geometry.value.splitlines()
    tokens = rows[1].split()
    tokens[1] = str(float(tokens[1]) + 0.1)
    rows[1] = " ".join(tokens)
    gui.matrix_geometry.value = "\n".join(rows)
    gui._on_run_isotope_reanalysis_clicked(None)
    assert "Geometry changed" in gui.isotope_results_table.value
    gui._on_clear_hessian_clicked(None)
    gui._on_run_isotope_reanalysis_clicked(None)
    assert "No Hessian" in gui.isotope_results_table.value


def test_gui_does_not_claim_unconnected_backends_are_active():
    gui = CoChemGUI()
    assert "No connected assistant backend" in gui.ai_container.children[0].value
    assert gui.torq_dihedrals.disabled
    assert "MACE-MD (MLFF)" not in gui.topos_heuristic.options
    gui.state.system_status = "Running Pipeline..."
    assert "aria-live='polite'" in gui.header_status.value
    gui.state.error_message = "A real validation error"
    assert 'role="alert"' in gui.footer_message.value


def test_installation_requires_real_data_and_tracks_license_choice(physical_bundle):
    path, _ = physical_bundle
    gui = CoChemGUI()
    assert gui.run_install_btn.disabled
    assert gui.license_mode.value == "none"
    gui.install_data_path.value = str(path)
    assert gui._validate_installation_data()
    assert not gui.run_install_btn.disabled
    assert gui._install_input_artifact.sha256 in gui.install_data_status.value
    gui.license_mode.value = "orca"
    assert gui.license_mode.value == "orca"
    gui.install_data_path.value = str(path.with_name("missing.npz"))
    assert gui.run_install_btn.disabled
    assert not gui._validate_installation_data()
