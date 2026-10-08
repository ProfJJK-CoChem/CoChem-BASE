"""Genuine native-data round trips and geometry-only admission in optional ML data adapters."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

import numpy as np
import pytest
import torch

from cochem_geom.data.geom_parser import ConformerRecord, molecular_data_to_conformer
from cochem_geom.data.featurizer import MolecularData
from cochem_geom.data.pes_store import PESStore
from cochem_geom.data.pyg_schema import ConformerData

FIXTURE = Path(__file__).parents[1] / "data" / "orca_6_1_1_water_hf_sto3g"


def native_data():
    provenance = json.loads((FIXTURE / "provenance.json").read_text())
    assert hashlib.sha256((FIXTURE / "water.engrad").read_bytes()).hexdigest() == provenance["files"]["water.engrad"]["sha256"]
    rows = (FIXTURE / "water.xyz").read_text().splitlines()[2:]
    coordinates = np.asarray([[float(v) for v in row.split()[1:4]] for row in rows])
    native = [line.strip() for line in (FIXTURE / "water.engrad").read_text().splitlines() if line.strip() and not line.startswith("#")]
    # ORCA native .engrad scalar field, retained Hartree units for storage admission.
    return coordinates, float(native[1])


def test_geometry_without_energy_roundtrips_as_unknown_not_zero():
    coordinates, _ = native_data()
    position = torch.tensor(coordinates, dtype=torch.float32)
    atoms = torch.tensor([8, 1, 1], dtype=torch.long)
    graph = ConformerData(z=atoms, pos=position)
    restored = graph.to_conformer_record()
    assert restored.energy is restored.relative_energy is restored.boltzmann_weight is None
    molecular = MolecularData(z=atoms, pos=position)
    restored_molecular = molecular_data_to_conformer(molecular)
    assert restored_molecular.energy is restored_molecular.relative_energy is restored_molecular.boltzmann_weight is None
    assert np.allclose(restored.coords, coordinates, rtol=0, atol=1e-7)
    roundtrip = ConformerData.from_conformer_record(restored, [8, 1, 1]).to_conformer_record()
    assert roundtrip.energy is roundtrip.boltzmann_weight is None


def test_measured_pes_batch_rejection_is_atomic_and_native_energy_is_preserved(tmp_path):
    coordinates, energy = native_data()
    store = PESStore(tmp_path / "native.h5", max_atoms=3)
    geometry = {"atomic_numbers": [8, 1, 1], "coordinates": coordinates}
    with pytest.raises(ValueError, match="no finite measured energy"):
        store.write_batch([{**geometry, "energy": energy}, geometry])
    assert store.current_idx == 0 and store.file["return_energy"].shape == (0,)
    store.write_conformer({**geometry, "energy": energy})
    assert store.file["return_energy"][0] == energy
    assert np.allclose(store.file["geometry"][0], coordinates, rtol=0, atol=1e-7)
    store.close()
