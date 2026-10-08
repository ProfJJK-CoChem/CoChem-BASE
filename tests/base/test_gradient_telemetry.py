"""Measured native fixtures exercise live geometry-bound derivative publication."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from cochem_base.calc.calculation_service import parse_run_geometry
from cochem_base.calc.xtb_optimization import read_xtb_gradient
from cochem_base.core_engine.gradient_telemetry import GradientStreamError, ORCAGradientStream
from cochem_base.core_engine.scientific_telemetry import read_scientific_results

DATA = Path(__file__).parents[1] / "data"


def _orca():
    directory = DATA / "orca_6_1_1_water_hf_sto3g"
    provenance = json.loads((directory / "provenance.json").read_text())
    output = directory / "water.out.txt"
    assert hashlib.sha256(output.read_bytes()).hexdigest() == provenance["files"][output.name]["sha256"]
    return output.read_text().splitlines()


def _stream(tmp_path, **changes):
    return ORCAGradientStream("water", ["O", "H", "H"], store_path=tmp_path / "results.h5",
        source_path=tmp_path / "gradient-native.txt", source_id="hashed-native-water-fixture", **changes)


def test_authentic_orca_gradients_bind_each_ordered_geometry_energy_and_exact_source(tmp_path):
    stream = _stream(tmp_path, nuclides=["18O", "2H", "3H"])
    for line in _orca():
        stream(line)
    assert stream.finish()["gradient_records_published"] == 5
    records = read_scientific_results("water", store_path=tmp_path / "results.h5")
    assert records["elements"] == ["O", "H", "H"]
    assert records["nuclides"] == ["18O", "2H", "3H"]
    assert records["gradients_hartree_per_bohr"].shape == (5, 3, 3)
    np.testing.assert_array_equal(records["gradient_record_indices"], np.arange(5))
    np.testing.assert_allclose(records["gradients_hartree_per_bohr"][0],
        [[0., 0., .061009020], [0., .023592247, -.030504510], [0., -.023592247, -.030504510]], atol=1e-12)
    assert records["energy_hartree"][0] == -74.963063130292
    assert records["energy_hartree"][-1] == -74.965901192170
    assert stream.records[0]["max_gradient"] == .061009020
    assert stream.records[-1]["max_gradient"] == .000004182
    raw = (tmp_path / "gradient-native.txt").read_bytes()
    for metadata in records["metadata"]:
        source = metadata["gradient_source"]
        chunk = raw[source["byte_offset"]:source["byte_offset"] + source["byte_length"]]
        assert hashlib.sha256(chunk).hexdigest() == source["record_sha256"]
        assert source["gradient_unit"] == "hartree/bohr"
        assert source["coordinates_print_resolution_bohr"] == 1e-6
        assert source["electronic_elements"] == ["O", "H", "H"]
        assert source["nuclides"] == ["18O", "2H", "3H"]
        assert source["convergence_status"] == "not_inferred_from_gradient"


def test_partial_actual_orca_gradient_is_not_published_and_end_is_rejected(tmp_path):
    lines = _orca()
    last = next(i for i, line in enumerate(lines) if "3   H   :" in line)
    stream = _stream(tmp_path)
    for line in lines[:last]:
        stream(line)
    assert stream.records == []
    assert not (tmp_path / "results.h5").exists()
    with pytest.raises(GradientStreamError, match="incomplete"):
        stream.finish()
    stream(lines[last])
    assert len(stream.records) == 1
    assert read_scientific_results("water", store_path=tmp_path / "results.h5")["gradients_hartree_per_bohr"].shape == (1, 3, 3)


@pytest.mark.parametrize("mutation,match", [
    (lambda s: s.replace("1   O   :", "1   C   :"), "identities"),
    (lambda s: s.replace("0.061009020", "nan"), "finite"),
    (lambda s: s.replace("FINAL SINGLE POINT ENERGY       -74.963063130292", "unlabeled energy -74.963063130292"), "preceding geometry and energy"),
    (lambda s: s.replace("   0 O     8.0000", "   0 O     6.0000"), "identities"),
])
def test_corrupted_native_orca_derivative_evidence_is_rejected(tmp_path, mutation, match):
    stream = _stream(tmp_path)
    with pytest.raises(GradientStreamError, match=match):
        for line in mutation("\n".join(_orca())).splitlines():
            stream(line)
    assert stream.records == []


@pytest.mark.parametrize("name,energy,z_gradient", [
    ("gfn2", -5.06577461509, .064450142689729),
    ("gfnff", -.31946770265, .094179644246837),
])
def test_actual_xtb_native_derivatives_preserve_geometry_energy_units_and_hash(name, energy, z_gradient):
    directory = DATA / "xtb_6_7_1_native_gradients" / name
    provenance = json.loads((directory / "provenance.json").read_text())
    for filename, source in provenance["files"].items():
        assert hashlib.sha256((directory / filename).read_bytes()).hexdigest() == source["sha256"]
    elements, positions = parse_run_geometry((directory / "input.xyz").read_text())
    accepted = read_xtb_gradient(directory / "gradient", elements, positions, energy)
    assert accepted["gradients_hartree_per_bohr"][0][2] == pytest.approx(z_gradient, abs=1e-14)
    np.testing.assert_allclose(accepted["native_coordinates_angstrom"], positions, rtol=0, atol=1e-9)
    assert accepted["gradient_artifact"]["sha256"] == provenance["files"]["gradient"]["sha256"]
    assert accepted["gradient_artifact"]["unit"] == "hartree/bohr"
    assert accepted["gradient_artifact"]["coordinates_unit"] == "bohr"
    with pytest.raises(ValueError, match="submitted geometry"):
        read_xtb_gradient(directory / "gradient", elements, np.asarray(positions) + .01, energy)
    with pytest.raises(ValueError, match="energy disagree"):
        read_xtb_gradient(directory / "gradient", elements, positions, energy + .01)
    with pytest.raises(ValueError, match="identities"):
        read_xtb_gradient(directory / "gradient", ["C", "H", "H"], positions, energy)


def test_bad_native_gradient_cannot_reinterpret_a_norm_as_cartesian_vectors(tmp_path):
    directory = DATA / "xtb_6_7_1_native_gradients/gfn2"
    elements, positions = parse_run_geometry((directory / "input.xyz").read_text())
    bad = tmp_path / "gradient"
    lines = (directory / "gradient").read_text().splitlines()
    bad.write_text("\n".join(lines[:-2]) + "\n$end\n")
    with pytest.raises(ValueError, match="complete"):
        read_xtb_gradient(bad, elements, positions, -5.06577461509)
    bad.write_text((directory / "gradient").read_text().replace("6.4450142689729E-02", "NaN"))
    with pytest.raises(ValueError, match="finite"):
        read_xtb_gradient(bad, elements, positions, -5.06577461509)
