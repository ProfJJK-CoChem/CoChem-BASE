"""Measured-quantity admission using retained native ORCA data, not a new engine run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import h5py
import numpy as np
import pytest
from pydantic import ValidationError

from cochem_base.calc.recipe_r2_execution import read_dimer_gradient
from cochem_base.core.models import PESPointRecord
from cochem_base.core.cochem_core_hdf5_manager import CoChemHDF5Manager, DatasetNotFoundError
from cochem_base.core_engine.cochem_core_pes_store import PESStore
from cochem_base.schemas.quantum import GradientPayload

FIXTURE = Path(__file__).parents[1] / "data" / "orca_6_1_1_water_hf_sto3g"


def native_record():
    provenance = json.loads((FIXTURE / "provenance.json").read_text())
    for name in ("water.xyz", "water.engrad"):
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == provenance["files"][name]["sha256"]
    rows = (FIXTURE / "water.xyz").read_text().splitlines()[2:]
    symbols = [row.split()[0] for row in rows]
    coordinates = [[float(value) for value in row.split()[1:4]] for row in rows]
    energy, gradient = read_dimer_gradient(FIXTURE / "water.engrad", symbols, coordinates)
    return symbols, coordinates, energy, gradient


def test_unevaluated_geometry_remains_unknown_and_never_mutates_measured_pes(tmp_path):
    symbols, coordinates, _, _ = native_record()
    point = PESPointRecord(symbols=symbols, coordinates=coordinates, units="angstrom")
    assert point.energy is None and point.to_bohr().energy is None
    store = PESStore(tmp_path / "measured.h5", symbols=symbols)
    with h5py.File(store.path, "r") as handle:
        before = list(handle)
    with pytest.raises(ValueError, match="finite measured energy"):
        store.add_point(point)
    with h5py.File(store.path, "r") as handle:
        assert list(handle) == before
        assert handle["points/coordinates"].shape == (0, 9)
        assert handle["points/energies"].shape == (0,)


def test_native_measured_pes_energy_and_geometry_survive_archive(tmp_path):
    symbols, coordinates, energy, _ = native_record()
    point = PESPointRecord(symbols=symbols, coordinates=coordinates, units="angstrom", energy=energy)
    store = PESStore(tmp_path / "native.h5", symbols=symbols)
    store.add_point(point)
    with h5py.File(store.path, "r") as handle:
        assert handle["points/energies"][0] == energy
        assert np.array_equal(handle["points/coordinates"][0], np.asarray(coordinates).reshape(-1))


def test_gradient_result_requires_measured_energy_without_overwriting_valid_zero():
    _, _, energy, gradient = native_record()
    with pytest.raises(ValidationError):
        GradientPayload(gradient=gradient.tolist())
    result = GradientPayload(energy_hartree=energy, gradient=gradient.tolist())
    assert result.energy == result.energy_hartree == energy
    # Scalar schema arithmetic, not a purported zero-energy molecular calculation.
    assert GradientPayload(energy=0.0).energy_hartree == 0.0
    with pytest.raises(ValidationError, match="Conflicting measured energy"):
        GradientPayload(energy=0.0, energy_hartree=energy)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_measured_energy_cannot_enter_scientific_result_schema(invalid):
    with pytest.raises(ValidationError):
        PESPointRecord(energy=invalid)
    with pytest.raises(ValidationError):
        GradientPayload(energy=invalid)


def test_incomplete_basin_archive_is_rejected_instead_of_read_as_zero(tmp_path):
    _, coordinates, energy, _ = native_record()
    manager = CoChemHDF5Manager(tmp_path / "basins.h5", ipc_db_path=tmp_path / "ipc.sqlite")
    # Deliberately incomplete archive tests missing-field handling; no chemistry is attributed to it.
    with h5py.File(manager.h5_path, "a") as handle:
        group = handle.require_group("basins/incomplete")
        group.attrs["molecule_name"] = "retained water geometry, unevaluated archive"
        group.create_dataset("xyz_coordinates", data=coordinates)
    with pytest.raises(DatasetNotFoundError, match="no measured energy"):
        manager.read_basin_record("incomplete")
    with h5py.File(manager.h5_path, "a") as handle:
        handle["basins/incomplete"].attrs["energy"] = energy
    result = manager.read_basin_record("incomplete")
    assert result.energy == energy and np.array_equal(result.xyz_coordinates, coordinates)
