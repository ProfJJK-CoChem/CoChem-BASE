"""No unrequested potential or stale-geometry electronic result is admissible."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from ase import Atoms
from ase.calculators.emt import EMT
from cochem_base.cochem_torq_mace import evaluate_pes_point, RequestedPotentialUnavailableError
from cochem_base.cochem_torq_quench import ConformalMDQuencher, format_to_qcschema_v1, QuenchReevaluationRequiredError
from cochem_base.core.cochem_constants import ANGSTROM_TO_BOHR, HARTREE_TO_EV
from cochem_base.calc.recipe_r2_execution import read_dimer_gradient

NATIVE = Path(__file__).parents[1] / 'data/orca_6_1_1_water_hf_sto3g'

def native():
    provenance = json.loads((NATIVE / 'provenance.json').read_text())
    for name in ('water.xyz', 'water.engrad'):
        assert hashlib.sha256((NATIVE / name).read_bytes()).hexdigest() == provenance['files'][name]['sha256']
    rows = (NATIVE / 'water.xyz').read_text().splitlines()[2:]
    symbols = [row.split()[0] for row in rows]
    coordinates = np.asarray([[float(value) for value in row.split()[1:4]] for row in rows])
    energy, _ = read_dimer_gradient(NATIVE / 'water.engrad', symbols, coordinates)
    return symbols, coordinates, energy

def test_missing_selected_potential_refuses_unrequested_lennard_jones():
    symbols, coordinates, _ = native()
    with pytest.raises(RequestedPotentialUnavailableError, match='no replacement model'):
        evaluate_pes_point(symbols, coordinates)

def test_explicit_actual_emt_is_empirical_emt_and_matches_its_native_evaluation():
    symbols, coordinates, _ = native()
    actual_ev = Atoms(symbols=symbols, positions=coordinates, calculator=EMT()).get_potential_energy()
    assert evaluate_pes_point(symbols, coordinates, model_wrapper=EMT()) == actual_ev / HARTREE_TO_EV
    # This proves an explicitly selected empirical calculator, not MACE or QM accuracy.

def test_geometric_qcschema_is_molecule_only_with_bohr_and_no_invented_energy():
    symbols, coordinates, energy = native()
    result = format_to_qcschema_v1(symbols, coordinates)
    assert result['schema_name'] == 'qcschema_molecule'
    assert np.array_equal(np.asarray(result['geometry']), (coordinates * ANGSTROM_TO_BOHR).reshape(-1))
    assert 'success' not in result and 'return_result' not in result and 'model' not in result
    with pytest.raises(QuenchReevaluationRequiredError, match='cannot certify'):
        format_to_qcschema_v1(symbols, coordinates, energy=energy)

def test_rollback_requires_new_energy_and_gradient_without_successful_archive(tmp_path):
    symbols, coordinates, energy = native()
    archive = tmp_path / 'should-not-exist.h5'
    quencher = ConformalMDQuencher(hdf5_store_path=archive, check_interval=1)
    assert quencher.step(0, symbols, coordinates)['action'] == 'CONTINUE'
    # A diagnostic uncertainty threshold is not a fabricated quantum gradient.
    with pytest.raises(QuenchReevaluationRequiredError, match='fresh selected-engine') as caught:
        quencher.step(1, symbols, coordinates + np.asarray([1., 0., 0.]), forces_sigma=np.asarray([1.]), energy_pred=energy)
    result = caught.value.geometry_result
    assert result['energy_hartree'] is None and result['scientific_status'] == 'uncomputed'
    assert result['discarded_pre_quench_prediction'] is True
    assert np.array_equal(result['quenched_coordinates'], coordinates)
    assert 'return_energy' not in result['qcschema_molecule']
    assert not archive.exists()
