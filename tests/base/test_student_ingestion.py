"""Real canonical intake, immutable provenance and hostile uploaded-data bounds."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import zipfile

import h5py
import numpy as np
import pytest
from rdkit import Chem

from cochem_base.interfaces.student_ingestion import ingest_uploaded_file, list_ingested_inputs, deduplicate_ingested_pools
from cochem_base.intake.structure_formats import parse_structure_text
from cochem_base.core.cochem_constants import BOHR_TO_ANGSTROM

DATA = Path(__file__).parents[1] / 'data/orca_6_1_1_water_hf_sto3g'
WATER = (DATA / 'water.xyz').read_bytes()


def _mdl(v3000=False):
    record = parse_structure_text(WATER.decode(), 'xyz')[0]
    molecule = Chem.RWMol()
    for symbol in record['elements']:
        atom = Chem.Atom(symbol)
        if symbol == 'O':
            atom.SetIsotope(18)
        molecule.AddAtom(atom)
    molecule.AddBond(0, 1, Chem.BondType.SINGLE)
    molecule.AddBond(0, 2, Chem.BondType.SINGLE)
    conformer = Chem.Conformer(3)
    for index, row in enumerate(record['coords']):
        conformer.SetAtomPosition(index, tuple(row))
    molecule.AddConformer(conformer)
    return Chem.MolToMolBlock(molecule, forceV3000=v3000).encode()


@pytest.mark.parametrize('name,raw,count', [
    ('student.xyz', WATER, 1), ('student.mol', _mdl(), 1),
    ('student.sdf', _mdl(True) + b'$$$$\n' + _mdl() + b'$$$$\n', 2),
])
def test_real_formats_originals_isotopes_and_reopen(tmp_path, name, raw, count):
    receipt = ingest_uploaded_file(name, raw, artifact_dir=tmp_path)
    assert len(receipt['records']) == count
    assert receipt['sha256'] == hashlib.sha256(raw).hexdigest()
    assert Path(receipt['path']).read_bytes() == raw
    assert list_ingested_inputs(tmp_path) == [receipt]
    if name != 'student.xyz':
        assert receipt['records'][0]['symbols'][0] == '18O'
        assert receipt['records'][0]['multiplicity'] is None
    assert receipt['scientific_execution_performed'] is False


def test_qcschema_original_bohr_identity_and_state(tmp_path):
    record = parse_structure_text(WATER.decode(), 'xyz')[0]
    source = dict(schema_name='qcschema_molecule', schema_version=2,
                  symbols=record['elements'], geometry=(record['coords']/BOHR_TO_ANGSTROM).ravel().tolist(),
                  molecular_charge=0, molecular_multiplicity=1, mass_numbers=[18, 2, 2])
    raw = json.dumps(source).encode()
    receipt = ingest_uploaded_file('student.json', raw, artifact_dir=tmp_path)
    assert receipt['records'][0]['symbols'] == ['18O', '2H', '2H']
    np.testing.assert_allclose(receipt['records'][0]['coords'], record['coords'], atol=1e-14)
    assert Path(receipt['path']).read_bytes() == raw


@pytest.mark.parametrize('name,raw', [('x.py', b'print(1)'), ('../x.xyz', WATER),
                                      ('x.xyz', b'MZpayload'), ('x.xyz', b'0\nempty\n'),
                                      ('x.xyz', b'3\ninvalid\nO 0 0 0\nH 0 1 0\n')])
def test_bad_data_never_publishes_partial_receipt(tmp_path, name, raw):
    with pytest.raises(ValueError):
        ingest_uploaded_file(name, raw, artifact_dir=tmp_path)
    assert not list_ingested_inputs(tmp_path)


def test_changed_original_rejected_on_reopen(tmp_path):
    receipt = ingest_uploaded_file('water.xyz', WATER, artifact_dir=tmp_path)
    Path(receipt['path']).chmod(0o600)
    Path(receipt['path']).write_bytes(WATER.replace(b'O ', b'N ', 1))
    with pytest.raises(ValueError, match='checksum'):
        list_ingested_inputs(tmp_path)


def test_changed_receipt_cannot_invent_atom_state(tmp_path):
    receipt = ingest_uploaded_file('water.xyz', WATER, artifact_dir=tmp_path)
    path = Path(receipt['path']).parent/'receipt.json'
    changed = json.loads(path.read_text())
    changed['records'][0]['charge'] = 8
    path.chmod(0o600)
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match='receipt checksum'):
        list_ingested_inputs(tmp_path)


def test_linked_artifacts_never_write_through(tmp_path):
    real = tmp_path/'actual'
    real.mkdir()
    link = tmp_path/'linked'
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match='symbolic'):
        ingest_uploaded_file('water.xyz', WATER, artifact_dir=link)
    assert not list(real.iterdir())


def test_npz_object_payload_rejected_without_unpickling(tmp_path):
    stream = io.BytesIO()
    np.savez(stream, unsafe=np.asarray([{'code':'data'}], dtype=object))
    with pytest.raises(ValueError, match='Pickled'):
        ingest_uploaded_file('arrays.npz', stream.getvalue(), artifact_dir=tmp_path)
    assert not list_ingested_inputs(tmp_path)


def test_npz_declared_huge_shape_rejected_before_allocation(tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        header = io.BytesIO()
        np.lib.format.write_array_header_1_0(header, {'descr':'<f8', 'fortran_order':False, 'shape':(10**12,)})
        archive.writestr('huge.npy', header.getvalue())
    with pytest.raises(ValueError, match='logical dimensions'):
        ingest_uploaded_file('huge.npz', stream.getvalue(), artifact_dir=tmp_path)


@pytest.mark.parametrize('kind', ['external', 'virtual', 'huge'])
def test_hdf5_data_dependencies_and_bombs_rejected(tmp_path, kind):
    path = tmp_path/'malicious.h5'
    with h5py.File(path, 'w', libver='latest') as archive:
        if kind == 'external':
            archive['foreign'] = h5py.ExternalLink('/etc/passwd', '/secret')
        elif kind == 'virtual':
            layout = h5py.VirtualLayout(shape=(1,), dtype='f8')
            layout[:] = h5py.VirtualSource('/tmp/foreign.h5', 'energy', shape=(1,))
            archive.create_virtual_dataset('energy', layout)
        else:
            archive.create_dataset('energy', shape=(10**12,), dtype='f8', chunks=(1,))
    with pytest.raises(ValueError):
        ingest_uploaded_file('malicious.h5', path.read_bytes(), artifact_dir=tmp_path/'artifacts')
    assert not list_ingested_inputs(tmp_path/'artifacts')


def test_actual_hessian_roundtrip_never_certifies_stationary_minimum(tmp_path):
    candidates = list(DATA.glob('*.hess'))
    assert candidates, 'The retained real ORCA Hessian fixture is required'
    receipt = ingest_uploaded_file('water.hess', candidates[0].read_bytes(), artifact_dir=tmp_path, kind='hessian')
    assert receipt['metadata']['hessian_shape'] == [9, 9]
    assert receipt['metadata']['physical_force_field_verified'] is False
    assert receipt['metadata']['stationary_geometry_verified'] is False
    assert list_ingested_inputs(tmp_path) == [receipt]


def test_pool_requires_explicit_source_and_units_without_zero_energy(tmp_path):
    with pytest.raises(ValueError, match='producer'):
        ingest_uploaded_file('pool.xyz', WATER, artifact_dir=tmp_path, kind='conformer_pool')
    with pytest.raises(ValueError, match='recorded energy'):
        ingest_uploaded_file('pool.xyz', WATER, artifact_dir=tmp_path, kind='conformer_pool', producer='crest', energy_unit='hartree')
    receipt = ingest_uploaded_file('geometries.xyz', WATER + WATER, artifact_dir=tmp_path)
    assert all('imported_energy' not in record for record in receipt['records'])
    result = deduplicate_ingested_pools([receipt['input_id']], artifact_dir=tmp_path)
    assert result['unique_count'] == 2
    assert all(item['disposition'] == 'unranked-energy' for item in result['decisions'])
    assert result['records'] == receipt['records']


def test_native_failed_output_retained_as_diagnostics_not_accepted_result(tmp_path):
    receipt = ingest_uploaded_file('failed.out', b'ORCA SCF NOT CONVERGED\n', artifact_dir=tmp_path)
    assert receipt['metadata']['diagnostics']['is_failure'] is True
    assert receipt['metadata']['scope'].endswith('not_accepted_calculation')
    assert receipt['scientific_execution_performed'] is False


def test_native_spectroscopy_import_keeps_unmeasured_ground_state_missing(tmp_path):
    raw = (DATA/'water.out.txt').read_bytes()
    receipt = ingest_uploaded_file('research-water.out.txt', raw, artifact_dir=tmp_path, kind='spectroscopy')
    values = receipt['metadata']['measured_spectroscopy']
    assert values['engine'].lower() == 'orca'
    assert values['b_e'] > 0
    assert values['b_0'] is None and values['delta_b_vib'] is None
    assert receipt['metadata']['stationary_geometry_verified'] is False
    assert Path(receipt['path']).read_bytes() == raw
    assert list_ingested_inputs(tmp_path) == [receipt]


@pytest.mark.parametrize('filename', ['gaas_ordered.cif', 'gaas_fractional.json'])
def test_periodic_import_keeps_actual_student_filename_and_canonical_units(tmp_path, filename):
    path = Path(__file__).parents[2]/'examples/product_b'/filename
    raw = path.read_bytes()
    receipt = ingest_uploaded_file('student-'+filename, raw, artifact_dir=tmp_path)
    structure = receipt['metadata']['validated_periodic_structure']
    assert structure['source']['source_filename'] == 'student-'+filename
    assert structure['source']['source_sha256'] == hashlib.sha256(raw).hexdigest()
    assert structure['elements'] == ['Ga', 'As'] and structure['pbc'] == [True, True, True]
    assert list_ingested_inputs(tmp_path) == [receipt]


def test_npz_bounded_preview_never_invents_units_or_source(tmp_path):
    from cochem_base.interfaces.student_ingestion import preview_ingested_input
    stream = io.BytesIO()
    # A numerical data fixture tests serialization bounds, not chemistry results.
    np.savez(stream, observations=np.asarray([[2., 4.], [6., 8.]]))
    receipt = ingest_uploaded_file('observations.npz', stream.getvalue(), artifact_dir=tmp_path)
    rows = preview_ingested_input(receipt['input_id'], artifact_dir=tmp_path, limit=3)
    assert rows[0]['total'] == 4 and rows[0]['shown'] == 3
    assert rows[0]['values'] == [2., 4., 6.]
    assert rows[0]['units'] == rows[0]['source'] == '[MISSING DATA]'


def test_hdf5_bounded_preview_preserves_actual_explicit_metadata(tmp_path):
    from cochem_base.interfaces.student_ingestion import preview_ingested_input
    path = tmp_path/'actual-data.h5'
    with h5py.File(path, 'w', libver='latest') as archive:
        values = archive.create_dataset('measured', data=np.asarray([[2., 4.], [6., 8.]]))
        values.attrs['units'] = 'fixture units'
        values.attrs['source'] = 'numerical serialization fixture; no quantum result'
    receipt = ingest_uploaded_file('actual-data.h5', path.read_bytes(), artifact_dir=tmp_path/'artifacts')
    rows = preview_ingested_input(receipt['input_id'], artifact_dir=tmp_path/'artifacts', limit=2)
    assert rows[0]['shown'] == 2 and rows[0]['total'] == 4
    assert rows[0]['units'] == 'fixture units'
    assert rows[0]['source'].endswith('no quantum result')


def test_resealed_forged_geometry_cannot_change_original_scientific_record(tmp_path):
    from cochem_base.interfaces.student_ingestion import _canonical
    receipt = ingest_uploaded_file('water.xyz', WATER, artifact_dir=tmp_path)
    path = Path(receipt['path']).parent/'receipt.json'
    changed = json.loads(path.read_text())
    changed['records'][0]['coords'][0][0] = 12.0
    changed.pop('receipt_sha256')
    changed['receipt_sha256'] = hashlib.sha256(_canonical(changed)).hexdigest()
    path.chmod(0o600)
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match='canonical parsing'):
        list_ingested_inputs(tmp_path)


def test_malformed_pseudopotential_never_pretends_to_be_paw(tmp_path):
    with pytest.raises(ValueError, match='UPF2'):
        ingest_uploaded_file('gallium.UPF', b'No pseudopotential data', artifact_dir=tmp_path)


def test_corrupt_input_isolated_without_hiding_another_valid_original(tmp_path):
    from cochem_base.interfaces.student_ingestion import scan_ingested_inputs
    good = ingest_uploaded_file('valid.xyz', WATER, artifact_dir=tmp_path)
    bad = ingest_uploaded_file('damaged.xyz', WATER, artifact_dir=tmp_path)
    path = Path(bad['path']); path.chmod(0o600); path.write_bytes(b'corrupted')
    scan = scan_ingested_inputs(tmp_path)
    assert scan['inputs'] == [good]
    assert len(scan['rejections']) == 1 and scan['rejections'][0]['input_id'] == bad['input_id']
    assert scan['rejections'][0]['original_retained'] is True
    assert path.read_bytes() == b'corrupted'
    with pytest.raises(ValueError, match='Invalid retained input'):
        list_ingested_inputs(tmp_path)


def test_new_derived_fields_revalidate_without_mutating_original_receipt(tmp_path):
    from cochem_base.interfaces.student_ingestion import _canonical
    receipt = ingest_uploaded_file('actual-water.hess', (DATA/'water.hess').read_bytes(), artifact_dir=tmp_path, kind='hessian')
    path = Path(receipt['path']).parent/'receipt.json'
    prior = json.loads(path.read_text()); prior['metadata'].pop('stationary_geometry_verified')
    prior.pop('receipt_sha256'); prior['receipt_sha256'] = hashlib.sha256(_canonical(prior)).hexdigest()
    prior_raw = _canonical(prior); path.chmod(0o600); path.write_bytes(prior_raw); path.chmod(0o400)
    reopened = list_ingested_inputs(tmp_path)[0]
    assert reopened['sha256'] == receipt['sha256']
    assert reopened['metadata']['stationary_geometry_verified'] is False
    assert reopened['source_receipt']['receipt_sha256'] == prior['receipt_sha256']
    assert reopened['revalidation']['original_receipt_modified'] is False
    assert path.read_bytes() == prior_raw
    assert Path(reopened['path']).read_bytes() == (DATA/'water.hess').read_bytes()


def test_real_native_observation_imports_canonical_telemetry_without_new_engine_job(tmp_path):
    from cochem_base.core_engine.scientific_telemetry import append_scientific_result
    from cochem_base.calc.cochem_calc_output_parser import QuantumParser
    log = DATA/'water.out.txt'
    native = QuantumParser(str(tmp_path/'parser')).parse_to_qcschema(log, 'actual-water', hashlib.sha256(log.read_bytes()).hexdigest())
    record = parse_structure_text(WATER.decode(), 'xyz')[0]
    source = tmp_path/'measured.h5'
    append_scientific_result('actual-water', record['symbols'], record['coords'], native.properties.return_energy,
        metadata={'source_sha256':hashlib.sha256(log.read_bytes()).hexdigest(), 'scope':'actual retained native ORCA observation; no new engine calculation'}, store_path=source)
    raw = source.read_bytes()
    receipt = ingest_uploaded_file('measured.h5', raw, artifact_dir=tmp_path/'artifacts', kind='telemetry')
    assert receipt['metadata']['measured_trajectories'] == [{'job_id':'actual-water','committed_records':1,'symbols':record['symbols']}]
    assert Path(receipt['path']).read_bytes() == raw
    assert list_ingested_inputs(tmp_path/'artifacts') == [receipt]


def test_uncommitted_or_corrupt_telemetry_cannot_claim_complete_measured_results(tmp_path):
    path = tmp_path/'corrupt.h5'
    with h5py.File(path,'w',libver='latest') as archive:
        group = archive.create_group('trajectories/bad')
        group.create_dataset('committed_records',data=np.int64(2))
        for key in ('coordinates_angstrom','energy_hartree','metadata_json','gradient_record_indices','gradients_hartree_per_bohr'):
            group.create_dataset(key,data=np.asarray([1.]))
    with pytest.raises(ValueError,match='inventory is incomplete'):
        ingest_uploaded_file('corrupt.h5', path.read_bytes(), artifact_dir=tmp_path/'artifacts', kind='telemetry')


@pytest.mark.parametrize('suffix', ['.h5', '.npz'])
def test_retained_scientific_archive_preview_preserves_actual_native_values_and_bounds(tmp_path, suffix):
    from cochem_base.interfaces.student_ingestion import preview_scientific_archive
    from cochem_base.spectroscopy.artifacts import load_hessian_artifact
    artifact = load_hessian_artifact(DATA/'water.hess')
    path = tmp_path/('retained-native-hessian'+suffix)
    if suffix == '.h5':
        with h5py.File(path, 'w', libver='latest') as archive:
            values = archive.create_dataset('force_hessian', data=artifact.hessian_hartree_bohr2)
            values.attrs['units'] = 'hartree/bohr^2'
            values.attrs['source'] = 'Actual retained native ORCA water Hessian; SHA-256 '+artifact.sha256
    else:
        np.savez(path, force_hessian=artifact.hessian_hartree_bohr2)
    raw = path.read_bytes()
    rows = preview_scientific_archive(path, limit=7, dataset_limit=1)
    assert len(rows) == 1 and rows[0]['shown'] == 7 and rows[0]['total'] == 81
    np.testing.assert_array_equal(np.asarray(rows[0]['values']).ravel(), artifact.hessian_hartree_bohr2.ravel()[:7])
    assert path.read_bytes() == raw
    with pytest.raises(ValueError, match='1 to 500'):
        preview_scientific_archive(path, limit=501)
    link = tmp_path/('linked'+suffix)
    link.symlink_to(path)
    with pytest.raises(ValueError, match='symbolic links'):
        preview_scientific_archive(link)


def test_retained_archive_preview_does_not_bypass_external_or_pickled_data_guards(tmp_path):
    from cochem_base.interfaces.student_ingestion import preview_scientific_archive
    source = tmp_path/'source.h5'
    with h5py.File(source, 'w', libver='latest') as archive:
        archive['values'] = np.asarray([1.])
    linked = tmp_path/'external.h5'
    with h5py.File(linked, 'w', libver='latest') as archive:
        archive['external'] = h5py.ExternalLink(str(source), '/values')
    with pytest.raises(ValueError, match='external or symbolic'):
        preview_scientific_archive(linked)
    objects = tmp_path/'objects.npz'
    np.savez(objects, unsupported_objects=np.asarray([{'declared': 'not science'}], dtype=object))
    with pytest.raises(ValueError, match='object arrays'):
        preview_scientific_archive(objects)
