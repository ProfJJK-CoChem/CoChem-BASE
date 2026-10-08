"""Retained native observations test legacy missing-data boundaries, not new chemistry."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import h5py
import numpy as np
import pytest
from cochem_base.calc.recipe_r2_execution import read_dimer_gradient
from cochem_base.data.cochem_base_pes_store import PESStore
from cochem_base.cochem_torq_vault import fetch_topos_matrices
from cochem_base.core_engine.oet_server import parse_ensemble_xyz, stream_ensemble_xyz
from cochem_base.export_utils.cochem_topos_export import TOPOSFAIRExporter
from cochem_base.harvesters.scribe_payload_builder import PayloadBuilder

NATIVE = Path(__file__).parents[1] / 'data/orca_6_1_1_water_hf_sto3g'

def native():
    provenance = json.loads((NATIVE / 'provenance.json').read_text())
    for name in ('water.xyz', 'water.engrad'):
        assert hashlib.sha256((NATIVE / name).read_bytes()).hexdigest() == provenance['files'][name]['sha256']
    text = (NATIVE / 'water.xyz').read_text()
    rows = text.splitlines()[2:]
    symbols = [row.split()[0] for row in rows]
    coordinates = [[float(value) for value in row.split()[1:4]] for row in rows]
    energy, gradient = read_dimer_gradient(NATIVE / 'water.engrad', symbols, coordinates)
    return text, symbols, coordinates, energy, gradient

def test_measured_pes_rejects_unknown_and_protected_rewrite_without_mutation(tmp_path):
    _, symbols, coordinates, energy, gradient = native()
    store = PESStore(tmp_path / 'native.h5', swmr_enabled=False)
    store.write_point('retained', energy_hartree=energy, coordinates=coordinates, gradient=gradient, symbols=symbols, tier='HF-STO3G')
    before = (tmp_path / 'native.h5').read_bytes()
    for extra in (None, {'energy_hartree': energy}, {'symbols': ['H']}, {'tier': 'unexecuted'}):
        with pytest.raises(ValueError):
            store.write_point('retained', energy_hartree=None if extra is None else energy, extra_attrs=extra)
        assert (tmp_path / 'native.h5').read_bytes() == before
    record = store.read_point('retained')
    assert record['energy_hartree'] == energy
    assert np.array_equal(record['coordinates'], coordinates)
    assert record['energy_ev'] != 0
    with h5py.File(store.storage_path, 'a') as handle:
        del handle['retained'].attrs['electronic_energy_hartree']
    with pytest.raises(ValueError, match='no measured'):
        store.read_point('retained')

def test_measured_pes_rejects_conflicting_energy_aliases(tmp_path):
    _, _, _, energy, _ = native()
    store = PESStore(tmp_path / 'aliases.h5', swmr_enabled=False)
    store.write_point('retained', energy_hartree=energy)
    with h5py.File(store.storage_path, 'a') as handle:
        handle['retained'].attrs['energy_hartree'] = float('nan')
    with pytest.raises(ValueError, match='aliases conflict'):
        store.read_point('retained')

def test_vault_keeps_unevaluated_geometry_energy_unknown(tmp_path):
    _, symbols, coordinates, energy, _ = native()
    path = tmp_path / 'geometry.h5'
    with h5py.File(path, 'w') as handle:
        node = handle.create_group('conformers/water')
        node.create_dataset('coordinates', data=coordinates)
        node.create_dataset('symbols', data=symbols, dtype=h5py.string_dtype())
    record = fetch_topos_matrices(path, 'water')
    assert record['energy_hartree'] is None and record['energy_status'] == 'uncomputed'
    assert np.array_equal(record['coordinates'], coordinates)
    with h5py.File(path, 'a') as handle:
        handle['conformers/water'].attrs['energy_hartree'] = energy
    record = fetch_topos_matrices(path, 'water')
    assert record['energy_hartree'] == energy and record['energy_status'] == 'supplied'

def test_ensemble_stream_preserves_native_geometry_and_distinguishes_frame_id(tmp_path):
    text, symbols, coordinates, energy, _ = native()
    rows = text.splitlines()
    path = tmp_path / 'ensemble.xyz'
    rows[1] = '1'  # A frame identifier is not a measured zero energy.
    path.write_text('\n'.join(rows) + '\n')
    first = list(stream_ensemble_xyz(path))[0]
    assert first[1] is None and first[3] == symbols
    assert np.array_equal(first[2], coordinates)
    rows[1] = f'energy={energy:.16g} Hartree'
    path.write_text('\n'.join(rows) + '\n')
    assert list(stream_ensemble_xyz(path))[0][1] == energy
    assert np.array_equal(parse_ensemble_xyz(path)[0][1], coordinates)

@pytest.mark.parametrize('comment', ['energy=not-a-value Hartree', 'energy=nan Hartree', 'energy=3 eV'])
def test_explicit_malformed_ensemble_quantity_cannot_become_unreported_energy(tmp_path, comment):
    text, _, _, _, _ = native()
    rows = text.splitlines(); rows[1] = comment
    path = tmp_path / 'invalid.xyz'; path.write_text('\n'.join(rows) + '\n')
    with pytest.raises(ValueError, match='explicitly reported ensemble energy'):
        list(stream_ensemble_xyz(path))

def test_raw_archive_export_does_not_invent_thermochemistry_or_populations(tmp_path):
    text, _, _, energy, _ = native()
    path = tmp_path / 'landscape.h5'
    with h5py.File(path, 'w') as handle:
        native_group = handle.create_group('deduplicated_isomers/retained-water/HF-STO3G')
        native_group.attrs['electronic_energy_hartree'] = energy
        native_group.create_dataset('geometry_xyz', data=text)
        handle.create_group('deduplicated_isomers/unevaluated/HF-STO3G')
    exporter = TOPOSFAIRExporter(path, tmp_path / 'export', allow_network=False)
    records = exporter._extract_isomer_records()
    retained, unknown = records
    assert retained['energy'] == energy and unknown['energy'] is None
    for record in records:
        assert all(record[key] is None for key in ('enthalpy', 'gibbs', 'zpe', 'dipole', 'boltzmann_pop_percent', 'rel_enthalpy_kcal'))
        assert record['rot_constants'] == (None, None, None)
    rendered = exporter.generate_latex_si().read_text()
    assert '--' in rendered and 'stationary minima' in rendered
    assert '6-Tier Tripartite Air-Gap Verified Matrix' not in rendered
    assert 'Defaulting to 0.0' not in rendered

def test_scribe_preserves_missing_relative_energy_and_engine_identity():
    _, _, _, energy, _ = native()
    data = {'conformers': [{'conformer_id': 'unknown-absolute', 'energy_kcal_mol': energy}, {'conformer_id': 'native-origin', 'relative_energy_kcal_mol': 0.0}, {'conformer_id': 'unknown-one'}, {'conformer_id': 'unknown-two'}]}
    builder = PayloadBuilder(data, manifest_data={})
    truncated = {'conformers': list(data['conformers'])}
    builder._tier1_drop_conformers(truncated)
    assert truncated['conformers'][0]['conformer_id'] == 'native-origin'
    assert 'relative_energy_kcal_mol' not in truncated['conformers'][1]
    prompt = builder.build_insights_prompt()
    assert 'unknown-absolute: Delta E = [MISSING DATA]' in prompt
    assert '[MISSING DATA: engine identity and version were not supplied]' in prompt
    assert 'ORCA 6.1.1 for electronic structure' not in prompt

@pytest.mark.parametrize('field', ['coordinates', 'gradient', 'hessian'])
def test_malformed_derivative_cannot_destroy_retained_pes_point(tmp_path, field):
    _, symbols, coordinates, energy, gradient = native()
    store = PESStore(tmp_path / 'immutable.h5', swmr_enabled=False)
    store.write_point('retained', energy_hartree=energy, coordinates=coordinates, gradient=gradient, symbols=symbols)
    before = store.storage_path.read_bytes()
    values = np.asarray(coordinates if field == 'coordinates' else gradient).copy()
    values[0, 0] = np.nan
    with pytest.raises(ValueError, match='finite'):
        store.write_point('retained', energy_hartree=energy, symbols=symbols, **{field: values})
    assert store.storage_path.read_bytes() == before

def test_vault_does_not_substitute_another_selected_conformer(tmp_path):
    _, symbols, coordinates, _, _ = native()
    path = tmp_path / 'selection.h5'
    with h5py.File(path, 'w') as handle:
        node = handle.create_group('conformers/water')
        node.create_dataset('coordinates', data=coordinates)
        node.create_dataset('symbols', data=symbols, dtype=h5py.string_dtype())
    with pytest.raises(KeyError, match='Requested conformer'):
        fetch_topos_matrices(path, 'absent-student-selection')
