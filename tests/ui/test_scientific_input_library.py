"""Actual upload widgets, canonical file readers and retained scientific inputs."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from ui.voila_layout.cochem_gui import CoChemGUI

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / 'tests/data/orca_6_1_1_water_hf_sto3g'


def upload(gui, raw, filename, *, kind='auto', control=None):
    gui.input_kind.value = kind
    widget = control if control is not None else gui.input_upload
    widget.value = ({'name': filename, 'type': 'application/octet-stream', 'size': len(raw),
        'content': memoryview(raw), 'last_modified': datetime.now(timezone.utc)},)
    gui._ingestion_worker.join(timeout=30)
    assert not gui._ingestion_worker.is_alive(), 'Input validation did not finish'
    assert not gui._ingestion_busy


def molecular_formats():
    """Convert authentic retained ORCA coordinates with the actual chemistry I/O library."""
    from rdkit import Chem
    from rdkit.Chem import rdDetermineBonds
    from cochem.core.cochem_constants import BOHR_TO_ANGSTROM
    xyz = NATIVE.joinpath('water.xyz').read_text()
    molecule = Chem.MolFromXYZBlock(xyz)
    rdDetermineBonds.DetermineBonds(molecule, charge=0)
    molecule.SetProp('multiplicity', '1')
    molecule.GetAtomWithIdx(1).SetIsotope(2)
    stream = io.StringIO()
    writer = Chem.SDWriter(stream)
    writer.write(molecule)
    writer.write(molecule)
    writer.close()
    xyz_atoms = molecule.GetConformer().GetPositions()
    qcschema = {'schema_name': 'qcschema_molecule', 'schema_version': 2,
        'symbols': ['O', 'H', 'H'], 'geometry': (xyz_atoms / BOHR_TO_ANGSTROM).reshape(-1).tolist(),
        'molecular_charge': 0, 'molecular_multiplicity': 1, 'fix_com': True, 'fix_orientation': True}
    mol2 = ('@<TRIPOS>MOLECULE\nNative water coordinates\n3 2 1 0 0\nSMALL\nNO_CHARGES\n\n'
        '@<TRIPOS>ATOM\n' + '\n'.join(
            f'{i+1} {symbol}{i+1} ' + ' '.join(format(float(value), '.17g') for value in row) +
            (' O.3' if symbol == 'O' else ' H') + ' 1 WATER 0.0'
            for i, (symbol, row) in enumerate(zip(['O', 'H', 'H'], xyz_atoms))) +
        '\n@<TRIPOS>BOND\n1 1 2 1\n2 1 3 1\n@<TRIPOS>SUBSTRUCTURE\n1 WATER 1\n')
    return [('native-water.xyz', xyz.encode(), 1),
        ('deuterated-water.mol', Chem.MolToMolBlock(molecule).encode(), 1),
        ('deuterated-water-v3000.mol', Chem.MolToMolBlock(molecule, forceV3000=True).encode(), 1),
        ('two-structures.sdf', stream.getvalue().encode(), 2),
        ('native-water.pdb', Chem.MolToPDBBlock(molecule).encode(), 1),
        ('native-water.mol2', mol2.encode(), 1),
        ('native-water-qcschema.json', json.dumps(qcschema).encode(), 1)]


def case_all_specified_molecular_uploads_and_record_selection(gui):
    for filename, raw, count in molecular_formats():
        upload(gui, raw, filename)
        receipt = gui._input_library[gui.input_library_choice.value]
        assert receipt['filename'] == filename, gui.input_library_status.value
        assert receipt['kind'] == 'molecular' and len(receipt['records']) == count
        assert Path(receipt['path']).read_bytes() == raw
        assert receipt['sha256'] == hashlib.sha256(raw).hexdigest()
        assert Path(receipt['path']).stat().st_mode & 0o222 == 0
        assert len(gui.input_record_choice.options) == count
        gui.input_record_choice.value = count - 1
        gui.charge_input.value = 2
        gui._use_library_geometry()
        record = gui._student_uploads[gui.student_geometry_choice.value]
        assert record['source_sha256'] == receipt['sha256'] and record['source_frame'] == count - 1
        assert record['atom_count'] == 3 and record['origin'] == 'canonical_ingestion'
        if filename.endswith('.mol') or filename.endswith('.sdf'):
            assert record['nuclides'] == ['O', '2H', 'H']
            assert record['charge'] == 0  # Encoded formal charge supersedes the previous form state.
        if filename.endswith('.sdf'):
            assert record['multiplicity'] == 1
        assert Path(receipt['path']).read_bytes() == raw
    reopened = CoChemGUI()
    reopened._input_library_worker.join(timeout=30)
    assert len(reopened._input_library) == 7
    assert len(reopened._student_uploads) == 7
    assert all(item['source_sha256'] in {entry['sha256'] for entry in reopened._input_library.values()}
               for item in reopened._student_uploads.values())


def case_invalid_multi_record_input_never_partially_admitted(gui):
    _, valid, _ = molecular_formats()[3]
    upload(gui, valid, 'valid.sdf')
    before = set(gui._input_library)
    malformed = valid.rsplit(b'$$$$', 2)[0] + b'$$$$\nMalformed molecule\n$$$$\n'
    upload(gui, malformed, 'truncated.sdf')
    assert set(gui._input_library) == before
    assert 'Rejected inputs' in gui.input_library_status.value
    ghost = b'2\nExplicit counterpoise centers\nH 0 0 0\nGh 0 0 2\n'
    upload(gui, ghost, 'ghost-centers.xyz')
    assert not gui.btn_use_input_geometry.disabled
    gui._use_library_geometry()
    assert not gui._student_uploads
    assert 'counterpoise-capable adapter' in gui.input_library_status.value, gui.input_library_status.value


def case_uploaded_native_hessian_and_physical_bundle(gui):
    from cochem_base.spectroscopy.artifacts import load_hessian_artifact
    raw = NATIVE.joinpath('water.hess').read_bytes()
    upload(gui, raw, 'my-native-water.hess', kind='hessian', control=gui.hessian_input_upload)
    gui._on_load_hessian_clicked(None)
    assert gui._isotope_hessian_data is not None, gui.isotope_hessian_status.value
    assert gui._isotope_hessian_data.sha256 == hashlib.sha256(raw).hexdigest()
    artifact = load_hessian_artifact(NATIVE / 'water.hess')
    stream = io.BytesIO()
    np.savez(stream, symbols=np.asarray(artifact.symbols),
        coordinates_angstrom=artifact.coordinates_angstrom,
        hessian_hartree_bohr2=artifact.hessian_hartree_bohr2,
        source=np.asarray('Imported ORCA 6.1.1 HF/STO-3G water Hessian; original SHA-256 ' + artifact.sha256))
    upload(gui, stream.getvalue(), 'my-native-water.npz', kind='hessian', control=gui.install_input_upload)
    assert gui._validate_installation_data()
    assert gui._install_input_artifact.source.endswith(artifact.sha256)
    assert gui._install_input_artifact.sha256 == hashlib.sha256(stream.getvalue()).hexdigest()
    assert not gui.run_install_btn.disabled
    gui._on_read_hdf5_clicked(None)
    gui._physical_data_worker.join(timeout=30)
    assert 'hessian_hartree_bohr2' in gui.hdf5_results_table.value, gui.hdf5_results_table.value
    assert '81' in gui.hdf5_results_table.value



def case_actual_isotope_button_runs_native_tensor_analysis_in_background(gui):
    from cochem_base.spectroscopy.isotopologue import IsotopologueSpectroscopyEngine
    raw = NATIVE.joinpath('water.hess').read_bytes()
    upload(gui, raw, 'my-native-isotope-water.hess', kind='hessian', control=gui.hessian_input_upload)
    gui.btn_load_hessian.click()
    gui._hessian_load_worker.join(timeout=30)
    assert not gui._hessian_load_worker.is_alive()
    artifact = gui._isotope_hessian_data
    assert artifact is not None, gui.isotope_hessian_status.value
    for selector, parent_nuclide in zip(gui.isotope_selectors, artifact.symbols):
        selector.value = parent_nuclide
    gui.isotope_selectors[1].value = '2H'
    expected = IsotopologueSpectroscopyEngine(
        symbols=artifact.symbols, coordinates_angstrom=artifact.coordinates_angstrom,
        cartesian_hessian=artifact.hessian_hartree_bohr2,
        hessian_qualification=artifact.qualification,
    ).compute_observables(isotopic_substitution={1: '2H'})
    gui.btn_run_isotope_reanalysis.click()
    assert gui._isotope_worker.ident is not None
    gui.state.active_view = 'inputs'  # Navigation remains an ordinary synchronous widget event.
    assert gui.state.active_view == 'inputs'
    gui._isotope_worker.join(timeout=30)
    assert not gui._isotope_worker.is_alive(), 'Bounded native Hessian reweighting did not finish'
    assert not gui.btn_run_isotope_reanalysis.disabled and not gui._ingestion_busy
    result = gui.isotope_results_table.value
    assert 'Substituted' in result and format(expected.total_mass_amu, '.4f') in result, result
    assert format(expected.B_e_MHz, '.2f') in result
    assert artifact.sha256 in result and '[MISSING DATA]' in result
    assert 'Supplied tensor' in result or 'supplied' in result.lower()
    assert 'Download frequency data (CSV)' in gui.isotope_modes_plot.value


def case_native_output_upload_uses_real_spectroscopy_reader(gui):
    raw = NATIVE.joinpath('water.out.txt').read_bytes()
    upload(gui, raw, 'my-native-water.out.txt', kind='spectroscopy', control=gui.telemetry_input_upload)
    gui._on_parse_inspector_clicked(None)
    assert '698269.660' in gui.inspector_rot_table.value, gui.inspector_rot_table.value
    assert '[MISSING DATA]' in gui.inspector_rot_table.value
    receipt = gui._input_library[gui._input_selectors['telemetry'].value]
    assert receipt['sha256'] == hashlib.sha256(raw).hexdigest()


def case_no_primary_input_path_or_json_controls(gui):
    hidden = {gui.install_data_path, gui.inspector_file_input, gui.isotope_hessian_path,
        gui.periodic_input_path, gui.periodic_settings_path, gui.periodic_output_path,
        gui.module_root, gui.module_output, gui.module_artifact, gui.module_operation}
    pending = [gui.view_install, gui.view_inspector, gui.view_periodic, gui.view_modules, gui.view_inputs]
    seen = set()
    while pending:
        widget = pending.pop()
        if widget in seen:
            continue
        seen.add(widget)
        assert widget not in hidden, f'Input path remained visible: {getattr(widget, "description", widget)}'
        pending.extend(getattr(widget, 'children', ()))
    assert not gui.run_install_btn.disabled and gui._install_input_artifact is None
    assert gui.paw_ecutrho.value >= 4 * gui.paw_ecutwfc.value
    assert all(item.value == 2 for item in gui.paw_kpoints)


def case_uploaded_periodic_structure_and_real_paw_deck(gui):
    from cochem_base.calc.periodic_execution import PeriodicCalculationConfig, write_periodic_input
    examples = ROOT / 'examples/product_b'
    upload(gui, (examples / 'gaas_ordered.cif').read_bytes(), 'my-gaas.cif',
        kind='periodic', control=gui.periodic_input_upload)
    assert gui._periodic_structure.source.source_filename == 'my-gaas.cif'
    upload(gui, (examples / 'gaas_fractional.json').read_bytes(), 'my-gaas-periodic.json',
        kind='periodic', control=gui.periodic_input_upload)
    assert gui._periodic_structure.source.source_filename == 'my-gaas-periodic.json'
    assert set(gui._paw_pseudopotential_choices) == {'Ga', 'As'}
    with pytest.raises(ValueError, match='PBE PAW pseudopotential'):
        gui._periodic_settings_from_form()
    pseudo_root = Path(os.environ.get('COCHEM_QE_PSEUDO_DIR', '/workspace/cochem-runtime/qe-pseudo'))
    for name in ('Ga.pbe-dn-kjpaw_psl.0.2.upf', 'As.pbe-n-kjpaw_psl.0.2.upf'):
        source = pseudo_root / name
        assert source.is_file(), 'Install the official pinned free QE PAW inputs before this acceptance profile'
        upload(gui, source.read_bytes(), name, kind='pseudopotential', control=gui.paw_input_upload)
    config_path = gui._prepare_periodic_config()
    config = json.loads(config_path.read_text())
    periodic = PeriodicCalculationConfig.model_validate(config['periodic'])
    assert periodic.structure_provenance.source_filename == 'my-gaas-periodic.json'
    assert periodic.ecutwfc_ry == gui.paw_ecutwfc.value
    assert periodic.kpoints == (2, 2, 2)
    structure = gui._periodic_structure
    path = write_periodic_input(structure.elements, structure.coordinates_angstrom,
        periodic, directory=config_path.parent / 'native-deck')
    assert 'ATOMIC_SPECIES' in path.read_text()
    for symbol, chooser in gui._paw_pseudopotential_choices.items():
        receipt = gui._input_library[chooser.value]
        assert periodic.pseudopotentials[symbol].sha256 == receipt['sha256']


def case_canonical_molecule_builder_retains_generated_provenance(gui):
    gui.smiles_input.value = '[2H]O[2H]'
    gui._build_student_molecule()
    gui._ingestion_worker.join(timeout=30)
    assert not gui._ingestion_worker.is_alive()
    assert not gui._ingestion_busy
    record = gui._student_uploads[gui.student_geometry_choice.value]
    assert '2H' in record['nuclides']
    provenance = record['generation_provenance']
    raw = Path(provenance['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == provenance['sha256']
    native = json.loads(raw)
    assert native['query'] == '[2H]O[2H]' and native['quantum_optimized'] is False
    assert native['resolution_source'] == 'direct_smiles'
    assert record['charge'] == native['charge'] == 0
    assert 'No quantum minimum or energy is claimed' in gui.student_upload_status.value


def case_pool_sieve_retains_unranked_records_and_uses_explicit_protocol(gui):
    lines = NATIVE.joinpath('water.xyz').read_text().splitlines()
    energy = float(lines[1].rsplit(' E ', 1)[1])
    frame = (lines[0] + '\nenergy=' + format(energy, '.17g') + ' energy_unit=hartree\n' +
        '\n'.join(lines[2:]) + '\n').encode()
    upload(gui, frame + frame, 'reimported-native-water.xyz', kind='conformer_pool')
    receipt = gui._input_library[gui.input_library_choice.value]
    gui.input_pool_choices.value = (receipt['input_id'],)
    gui._sieve_input_pools()
    gui._ingestion_worker.join(timeout=30)
    assert gui._last_input_pool_sieve['unique_count'] == 2
    assert 'unranked and retained' in gui.input_pool_status.value
    gui.input_pool_declare_context.value = True
    gui.input_pool_engine.value = 'ORCA'
    gui.input_pool_method.value = 'HF'
    gui.input_pool_basis.value = 'STO-3G'
    gui.input_pool_version.value = '6.1.1'
    gui._sieve_input_pools()
    gui._ingestion_worker.join(timeout=30)
    result = gui._last_input_pool_sieve
    assert result['input_count'] == 2 and result['unique_count'] == 1
    assert result['stationary_minima_verified'] is False
    assert len(result['records']) == 2 and len(result['decisions']) == 2
    gui._use_unique_conformer()
    selected = gui._student_uploads[gui.student_geometry_choice.value]
    assert selected['source_sha256'] == receipt['sha256']
    assert Path(receipt['path']).read_bytes() == frame + frame


def case_real_inbox_watcher_and_corrupt_receipt_isolation(gui):
    from cochem_base.config_loader import get_artifact_dir
    directory = get_artifact_dir() / 'Input_Files' / 'Inbox'
    directory.mkdir(parents=True)
    raw = NATIVE.joinpath('water.xyz').read_bytes()
    (directory / 'my-inbox-water.xyz').write_bytes(raw)
    gui._watch_input_inbox()
    gui._ingestion_worker.join(timeout=30)
    assert any(item['filename'] == 'my-inbox-water.xyz' for item in gui._input_library.values())
    assert gui._input_inbox_worker.is_alive()
    gui._stop_input_inbox()
    gui._input_inbox_worker.join(timeout=10)
    assert not gui._input_inbox_worker.is_alive()
    upload(gui, raw, 'my-second-water.xyz')
    record = gui._input_library[gui.input_library_choice.value]
    original = Path(record['path'])
    original.chmod(0o600)
    original.write_bytes(raw + b'corrupt trailing content\n')
    gui._refresh_input_library()
    gui._input_library_worker.join(timeout=30)
    assert record['input_id'] not in gui._input_library
    assert len(gui._input_library) == 1
    assert len(gui._input_library_rejections) == 1
    assert 'Rejected retained inputs' in gui.input_library_table.value
    assert original.read_bytes().endswith(b'corrupt trailing content\n')



def case_native_result_hessian_selection_and_tamper_rejection(gui):
    import h5py
    from cochem_base.config_loader import get_artifact_dir
    from cochem_base.spectroscopy.artifacts import load_hessian_artifact
    root = get_artifact_dir() / 'NativeResultData'
    root.mkdir(parents=True)
    hessian = root / 'water.hess'
    raw = NATIVE.joinpath('water.hess').read_bytes()
    hessian.write_bytes(raw)
    artifact = load_hessian_artifact(hessian)
    source = 'Actual ORCA 6.1.1 HF/STO-3G Hessian, original SHA-256 ' + artifact.sha256
    np.savez(root / 'water.npz', symbols=np.asarray(artifact.symbols),
        coordinates_angstrom=artifact.coordinates_angstrom,
        hessian_hartree_bohr2=artifact.hessian_hartree_bohr2, source=np.asarray(source))
    with h5py.File(root / 'water.h5', 'w') as handle:
        handle.create_dataset('symbols', data=np.asarray(artifact.symbols, dtype='S'))
        handle.create_dataset('coordinates_angstrom', data=artifact.coordinates_angstrom)
        handle.create_dataset('hessian_hartree_bohr2', data=artifact.hessian_hartree_bohr2)
        handle.create_dataset('source', data=source, dtype=h5py.string_dtype('utf-8'))
    candidates = gui._prepare_calculation_hessians(root)
    assert {Path(item['path']).suffix for item in candidates.values()} == {'.hess', '.npz', '.h5'}
    gui._publish_calculation_hessians(candidates)
    for key, record in candidates.items():
        gui.calculation_hessian_choice.value = key
        gui.btn_load_hessian.click()
        gui._hessian_load_worker.join(timeout=30)
        assert not gui._hessian_load_worker.is_alive()
        assert gui._isotope_hessian_data is not None, gui.isotope_hessian_status.value
        assert gui._isotope_hessian_data.sha256 == record['sha256']
        assert not gui._isotope_hessian_data.qualification['stationary_geometry_verified']
        gui.btn_run_isotope_reanalysis.click()
        gui._isotope_worker.join(timeout=30)
        assert record['sha256'] in gui.isotope_results_table.value
        assert 'not established' in gui.isotope_results_table.value
    native_key = next(key for key, item in candidates.items() if Path(item['path']).suffix == '.hess')
    hessian.write_bytes(raw + b'\n')
    gui.calculation_hessian_choice.value = ''
    gui.calculation_hessian_choice.value = native_key
    assert gui._isotope_hessian_data is None
    assert 'hash changed' in gui.isotope_hessian_status.value
    assert not gui.isotope_hessian_path.value
    upload(gui, raw, 'my-new-native-water.hess', kind='hessian', control=gui.hessian_input_upload)
    assert gui.calculation_hessian_choice.value == ''
    gui.btn_load_hessian.click()
    gui._hessian_load_worker.join(timeout=30)
    assert gui._isotope_hessian_data is not None
    assert gui._isotope_hessian_data.sha256 == hashlib.sha256(raw).hexdigest()


def case_retained_archive_preview_binds_exact_source_over_old_library_selection(gui):
    """Render genuine native arrays without claiming this is hosted acceptance."""
    import h5py
    from cochem_base.config_loader import get_artifact_dir
    from cochem_base.spectroscopy.artifacts import load_hessian_artifact
    artifact = load_hessian_artifact(NATIVE / 'water.hess')
    stream = io.BytesIO()
    np.savez(stream, uploaded_force_hessian=artifact.hessian_hartree_bohr2)
    upload(gui, stream.getvalue(), 'my-uploaded-force-data.npz', kind='physical_data', control=gui.physical_data_input_upload)
    old = gui._input_selectors['physical_data'].value
    root = get_artifact_dir() / 'RetainedNativeArrayPreview'
    root.mkdir()
    for suffix in ('.h5', '.npz'):
        path = root / ('retained-native-force-data' + suffix)
        if suffix == '.h5':
            with h5py.File(path, 'w', libver='latest') as archive:
                values = archive.create_dataset('native_force_hessian', data=artifact.hessian_hartree_bohr2)
                values.attrs['units'] = 'hartree/bohr^2'
                values.attrs['source'] = 'Actual retained ORCA water Hessian; original SHA-256 ' + artifact.sha256
        else:
            np.savez(path, native_force_hessian=artifact.hessian_hartree_bohr2)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        gui._input_selectors['physical_data'].value = old
        gui._on_read_hdf5_clicked(None, result_source={'path': str(path), 'filename': path.name, 'sha256': digest})
        gui._physical_data_worker.join(timeout=30)
        assert not gui._physical_data_worker.is_alive()
        assert 'native_force_hessian' in gui.hdf5_results_table.value, gui.hdf5_results_table.value
        assert 'uploaded_force_hessian' not in gui.hdf5_results_table.value
        assert digest in gui.hdf5_results_table.value and path.name in gui.hdf5_results_table.value
        assert gui._input_selectors['physical_data'].value == ''
        gui.btn_read_hdf5.click()
        gui._physical_data_worker.join(timeout=30)
        assert digest in gui.hdf5_results_table.value
    path.write_bytes(path.read_bytes() + b'\n')
    gui.btn_read_hdf5.click()
    gui._physical_data_worker.join(timeout=30)
    assert 'changed after verification' in gui.hdf5_results_table.value
    gui._input_selectors['physical_data'].value = old
    gui.btn_read_hdf5.click()
    gui._physical_data_worker.join(timeout=30)
    assert 'uploaded_force_hessian' in gui.hdf5_results_table.value
    assert 'native_force_hessian' not in gui.hdf5_results_table.value


def case_actions_geometry_control_denies_missing_identity_without_local_fallback(gui):
    raw = NATIVE.joinpath('water.xyz').read_bytes()
    upload(gui, raw, 'my-actions-starting-water.xyz')
    gui._use_library_geometry()
    gui.calc_env_dropdown.value = 'github-actions'
    gui.gh_repo_input.value = 'ProfJJK-CoChem/CoChem-BASE'
    gui.gh_branch_input.value = 'main'
    gui._run_module_geometry()
    gui._actions_worker.join(timeout=30)
    assert not gui._actions_worker.is_alive() and not gui._actions_running
    assert 'GitHub authentication is unavailable' in gui.actions_status.value, gui.actions_status.value
    assert not hasattr(gui, '_module_worker') and not hasattr(gui, '_research_worker')
    assert not hasattr(gui, '_pipeline_worker')


def case_hpc_selection_denies_interface_host_scientific_execution(gui):
    from cochem_base.interfaces.student_hpc import StudentHpcClient
    from cochem_base.interfaces.student_research import SCHEMA
    from cochem_base.config_loader import get_artifact_dir
    raw = NATIVE.joinpath('water.xyz').read_bytes()
    upload(gui, raw, 'my-hpc-starting-water.xyz')
    gui._use_library_geometry()
    gui.calc_env_dropdown.value = 'hpc'
    gui.scheduler_input.value = 'slurm'
    assert gui.slurm_panel.layout.display != 'none'
    client = StudentHpcClient(artifact_dir=get_artifact_dir(), module_root=Path(gui.module_root.value))
    observed = client.preflight()
    assert observed['ready'] is False, 'This isolated UI case requires a genuine scheduler-unavailable environment'
    assert observed['reason']
    provider = {'schema_version': SCHEMA, 'module': 'topos', 'operation': 'geometry_analysis',
        'artifact': 'inputs/starting-geometry.xyz', 'artifact_sha256': hashlib.sha256(raw).hexdigest(), 'options': {}}
    gui._run_student_provider(provider, raw.decode('utf-8'))
    gui._hpc_worker.join(timeout=30)
    assert not gui._hpc_worker.is_alive() and not gui._hpc_running
    assert 'No interface-host scientific fallback' in gui.slurm_status_output.value
    assert not hasattr(gui, '_research_worker') and not hasattr(gui, '_pipeline_worker')
    gui._execute_pipeline(None)
    if hasattr(gui, '_hpc_worker'):
        gui._hpc_worker.join(timeout=30)
    assert not hasattr(gui, '_pipeline_worker')
    assert gui.btn_execute.description == 'Submit HPC calculation'
    with pytest.raises(ValueError, match='scheduler'):
        gui._build_pipeline_command()
    gui._start_topos_search()
    assert not hasattr(gui, '_topos_worker')
    assert gui._topos_broker is None
    gui._run_module_geometry()
    gui._hpc_worker.join(timeout=30)
    assert not gui._hpc_worker.is_alive() and not hasattr(gui, '_research_worker')
    case_uploaded_periodic_structure_and_real_paw_deck(gui)
    gui._execute_periodic_pipeline()
    gui._hpc_worker.join(timeout=30)
    assert not gui._hpc_worker.is_alive() and not hasattr(gui, '_pipeline_worker')
    gui._hpc_monitor_stop.set()


CASES = [name.removeprefix('case_') for name in globals() if name.startswith('case_')]


@pytest.mark.parametrize('case', CASES)
def test_actual_scientific_input_library(case, tmp_path):
    environment = dict(os.environ, COCHEM_ARTIFACTS=str(tmp_path / 'artifacts'),
        COCHEM_ARTIFACT_DIR=str(tmp_path / 'artifacts'), COCHEM_STUDENT_AUTO_SETUP='false',
        COCHEM_STUDENT_REMOTE_CHECKS='false', CODESPACES='false')
    if case in {'hpc_selection_denies_interface_host_scientific_execution',
                'actions_geometry_control_denies_missing_identity_without_local_fallback'}:
        environment['PATH'] = str(Path(sys.executable).parent)
    if case == 'actions_geometry_control_denies_missing_identity_without_local_fallback':
        environment.pop('GH_TOKEN', None)
        environment.pop('GITHUB_TOKEN', None)
    completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), case], env=environment,
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=90, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr


if __name__ == '__main__':
    gui = CoChemGUI()
    gui._input_library_worker.join(timeout=30)
    try:
        globals()['case_' + sys.argv[1]](gui)
    finally:
        gui._actions_monitor_stop.set()
        gui._hpc_monitor_stop.set()
        gui._inbox_stop.set()
        gui._cleanup_topos_search()
