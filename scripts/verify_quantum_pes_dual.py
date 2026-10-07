#!/usr/bin/env python3
"""Independent new-holdout measurement of the declared dual-resolution protocol.

This development follow-up was motivated by the preceding 32/32 experiment.
No hyperparameter or sample-density selection uses the new held-out labels.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
import time

import numpy as np

BASE_SCRIPT = Path(__file__).resolve().with_name('verify_quantum_pes.py')
spec = importlib.util.spec_from_file_location('quantum_pes_original', BASE_SCRIPT)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def coords(distance):
    return [[0., 0., -float(distance) / 2], [0., 0., float(distance) / 2]]


def read_recorded_energy(point: dict, method: str) -> float:
    """Recheck a real input/output pair before using its recorded energy."""
    evidence = point['methods'][method]
    log, deck = Path(evidence['output_path']), Path(evidence['input_path'])
    if base.digest(log) != evidence['output_sha256'] or base.digest(deck) != evidence['input_sha256']:
        raise ValueError('A recorded genuine input/output changed')
    deck_text = deck.read_text(encoding='utf-8')
    rows = re.search(r'\*\s+xyz\s+0\s+1\s*\n(.*?)\n\*', deck_text, re.DOTALL)
    if rows is None:
        raise ValueError('Expected the declared neutral-singlet Cartesian input')
    atoms = [row.split() for row in rows.group(1).splitlines() if row.strip()]
    if len(atoms) != 2 or any(len(row) != 4 or row[0] != 'H' for row in atoms):
        raise ValueError('Recorded geometry is not the declared H2 input')
    coordinates = np.asarray([[float(value) for value in row[1:]] for row in atoms])
    if not np.allclose(coordinates, coords(point['distance_angstrom']), atol=1e-12, rtol=0):
        raise ValueError('Actual input coordinates differ from the declared grid')
    expected_keywords = 'HF STO-3G' if method == 'low' else 'CCSD(T) cc-pVTZ'
    if not deck_text.startswith(f'! {expected_keywords} VeryTightSCF NoTRAH NoSOSCF\n'):
        raise ValueError('Recorded calculation method differs from the declared protocol')
    parser = base.QuantumParser(str(log.parent))
    parser.scf_threshold = 1e-8
    if not parser.verify_scf_convergence(log):
        raise ValueError('Recorded output lacks accepted actual SCF convergence')
    if method == 'high':
        parsed = base.validate_reference_output(log, 'cc-pVTZ')['ccsdt_energy_hartree']
    else:
        values = re.findall(r'FINAL SINGLE POINT ENERGY\s+([-+]?\d+\.\d+(?:[EeDd][-+]?\d+)?)', log.read_text())
        if len(values) != 1:
            raise ValueError('Recorded output has ambiguous final energy')
        parsed = float(values[0].replace('D', 'E'))
    if not math.isfinite(parsed) or not math.isclose(parsed, evidence['energy_hartree'], rel_tol=0, abs_tol=1e-12):
        raise ValueError('Recorded energy differs from its genuine output')
    return parsed


def execute(registry: Path, original: Path, output: Path, timeout: float) -> dict:
    output = base._external_run_path(output)
    if output.exists():
        raise FileExistsError('Existing acceptance evidence cannot be overwritten')
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('A finite positive calculation budget is required')
    old = json.loads(original.read_text())
    if old['status'] != 'measured_threshold_not_met':
        raise ValueError('This follow-up must preserve the preceding measured experiment')
    old_train = [r for r in old['calculations'] if r['partition'] == 'train']
    if len(old_train) != 32:
        raise ValueError('Expected the original declared 32 paired correction geometries')
    train_distances = np.asarray([r['distance_angstrom'] for r in old_train])
    if not np.array_equal(train_distances, np.linspace(.55, 1.80, 32)):
        raise ValueError('The correction training domain/grid must remain unchanged')
    dense_distances = np.linspace(.55, 1.80, 128)
    held_distances = train_distances[:-1] + .37 * np.diff(train_distances)
    for held in held_distances:
        if any(abs(held - value) < 1e-12 for value in np.concatenate((dense_distances, train_distances))):
            raise ValueError('New held-out geometry overlaps training')
        if any(abs(held - r['distance_angstrom']) < 1e-12 for r in old['calculations']):
            raise ValueError('New held-out geometry was previously evaluated')
    work = output.parent / (output.stem + '-work')
    work.mkdir(exist_ok=False, parents=True)
    fitting = base.DeltaFittingConfig()
    protocol = {
        'schema_version': 'cochem.quantum-pes-dual-resolution-protocol/1',
        'declared_utc': datetime.now(timezone.utc).isoformat(),
        'generator_sha256': base.digest(Path(__file__)),
        'base_generator_sha256': base.digest(BASE_SCRIPT),
        'previous_experiment_path': str(original.resolve()),
        'previous_experiment_sha256': base.digest(original),
        'reason_for_followup': 'The preceding 32/32 experiment met the 10 cm^-1 RMS criterion but its standalone maximum error exceeded 10 cm^-1. Its independently measured baseline interpolation error dominated. It is retained as development evidence; this predeclares one denser low-level baseline and a fresh holdout without changing model hyperparameters or narrowing the domain.',
        'symbols': ['H', 'H'], 'charge': 0, 'multiplicity': 1,
        'bond_domain_angstrom': [.55, 1.80],
        'correction_train_distances_angstrom': train_distances.tolist(),
        'baseline_train_distances_angstrom': dense_distances.tolist(),
        'new_held_out_distances_angstrom': held_distances.tolist(),
        'held_out_interval_fraction': .37,
        'lower_method': 'ORCA RHF/STO-3G', 'higher_method': 'ORCA canonical CCSD(T)/cc-pVTZ',
        'scf_solver': old['protocol']['scf_solver'],
        'fitting_configuration': fitting.model_dump(mode='json'),
        'hyperparameter_selection': 'Unchanged BASE defaults; lengthscale and energy centering use training data only',
        'acceptance': 'Both paired and standalone held-out energy RMSE AND maximum absolute error <=10 cm^-1',
        'limitations': old['scope'],
        'prior_holdout_reused_for_training': False,
    }
    protocol_path = work / 'predeclared-protocol.json'
    base.write_json(protocol_path, protocol)
    protocol_hash = base.digest(protocol_path)
    start = time.monotonic()
    report = {'status': 'failed', 'scientific_accuracy_established': False, 'scope': old['scope'],
              'protocol': protocol, 'protocol_sha256': protocol_hash,
              'work_directory': str(work), 'calculations': [], 'reused_training_calculations': []}
    try:
        authority = base.authorize_engine_execution('orca', registry_path=registry, cores=1, maxcore_mb=1000)
        report.update(registry_path=str(registry.resolve()), registry_sha256=base.digest(registry),
                      binary_path=authority.executable, binary_sha256=authority.binary_sha256)
        if authority.binary_sha256 != old['binary_sha256']:
            raise ValueError('Reference reuse requires the identical engine binary')
        environment = base.sanitize_mpi_environment(
            base.engine_runtime_environment('orca', executable=authority.executable), force_single_thread=True)
        train_low, train_high = [], []
        for point in old_train:
            for method in ('low', 'high'):
                parsed = read_recorded_energy(point, method)
                (train_low if method == 'low' else train_high).append(parsed)
            report['reused_training_calculations'].append(point)

        def calculate(label, index, distance, methods):
            point = {'partition': label, 'index': index, 'distance_angstrom': float(distance), 'methods': {}}
            for method in methods:
                directory = work / label / f'point-{index:03d}' / method
                directory.mkdir(parents=True)
                deck = directory / 'h2.inp'
                keywords = 'HF STO-3G' if method == 'low' else 'CCSD(T) cc-pVTZ'
                deck.write_text(
                    f'! {keywords} VeryTightSCF NoTRAH NoSOSCF\n%pal nprocs 1 end\n%maxcore 1000\n'
                    '%scf TolE 1e-11 ConvCheckMode 0 ConvForced true MaxIter 200 end\n'
                    + ('%mdci STol 1e-9 MaxIter 100 end\n' if method == 'high' else '')
                    + f'* xyz 0 1\nH 0 0 {-distance / 2:.15f}\nH 0 0 {distance / 2:.15f}\n*\n', encoding='utf-8')
                remaining = timeout - (time.monotonic() - start)
                if remaining <= 0:
                    raise TimeoutError('Bounded acceptance budget expired')
                result = base.safe_subprocess_run(authority.command([deck.name]), cwd=directory,
                    env=environment, timeout=remaining, capture_output=True, text=True, check=False,
                    load_full_stdout=True, required_disk_gb=.1, cpu_affinity=list(authority.cpu_affinity) or None)
                log = directory / 'h2.out'
                log.write_text(result.stdout or '', encoding='utf-8')
                (directory / 'stderr.log').write_text(result.stderr or '', encoding='utf-8')
                if result.returncode:
                    raise RuntimeError(f'Actual ORCA job failed: {directory}')
                parser = base.QuantumParser(str(directory))
                parser.scf_threshold = 1e-8
                if not parser.verify_scf_convergence(log):
                    raise RuntimeError(f'Actual ORCA SCF convergence failed: {directory}')
                if method == 'high':
                    energy = base.validate_reference_output(log, 'cc-pVTZ')['ccsdt_energy_hartree']
                else:
                    values = re.findall(r'FINAL SINGLE POINT ENERGY\s+([-+]?\d+\.\d+(?:[EeDd][-+]?\d+)?)', result.stdout or '')
                    if len(values) != 1:
                        raise ValueError('Ambiguous actual HF single-point energy')
                    energy = float(values[0].replace('D', 'E'))
                if not math.isfinite(energy):
                    raise ValueError('Nonfinite energy')
                point['methods'][method] = {'energy_hartree': energy, 'input_path': str(deck),
                    'input_sha256': base.digest(deck), 'output_path': str(log),
                    'output_sha256': base.digest(log), 'scf_converged': True}
            report['calculations'].append(point)
            base.write_json(work / label / f'point-{index:03d}' / 'evidence.json', point)
            print(f'{label} point {index + 1} completed at {distance:.6f} angstrom', flush=True)
            return point

        dense_low = []
        for i, distance in enumerate(dense_distances):
            # Retain separate genuine files for every dense-grid point, including
            # the two endpoints shared with the original correction grid.
            point = calculate('baseline_train', i, distance, ('low',))
            dense_low.append(point['methods']['low']['energy_hartree'])
        held_low, held_high = [], []
        for i, distance in enumerate(held_distances):
            point = calculate('new_held_out', i, distance, ('low', 'high'))
            held_low.append(point['methods']['low']['energy_hartree'])
            held_high.append(point['methods']['high']['energy_hartree'])
        if base.digest(protocol_path) != protocol_hash:
            raise ValueError('Predeclared protocol changed during execution')
        held_geoms = np.asarray([coords(r) for r in held_distances])
        model, summary = base.AutoPESOrchestrator(symbols=['H', 'H'],
            low_method=protocol['lower_method'], high_method=protocol['higher_method'], fit_config=fitting
        ).fit_delta_surface_from_data(
            train_geoms=np.asarray([coords(r) for r in train_distances]),
            train_low_energies=np.asarray(train_low), train_high_energies=np.asarray(train_high),
            held_out_geoms=held_geoms, held_out_low_energies=np.asarray(held_low),
            held_out_high_energies=np.asarray(held_high),
            dense_dft_geoms=np.asarray([coords(r) for r in dense_distances]), dense_dft_energies=np.asarray(dense_low))
        predictions = {
            'paired_correction': model.predict_total_energy(held_geoms, v_low_eval=np.asarray(held_low)),
            'standalone_prediction': model.predict_total_energy(held_geoms, allow_unvalidated_baseline=True)}
        metrics = {}
        for name, prediction in predictions.items():
            error = (prediction - np.asarray(held_high)) * base.HARTREE_TO_CM1
            metrics[name] = {'rmse_cm1': float(np.sqrt(np.mean(error ** 2))),
                'maximum_absolute_error_cm1': float(np.max(np.abs(error))),
                'signed_errors_cm1': error.tolist(), 'predicted_energies_hartree': prediction.tolist()}
        met = all(v['rmse_cm1'] <= 10 and v['maximum_absolute_error_cm1'] <= 10 for v in metrics.values())
        report.update(status='passed' if met else 'measured_threshold_not_met', metrics=metrics,
            bounded_10_cm1_target_met=met, fit_summary=summary.model_dump(mode='json'),
            baseline_training_count=128, correction_training_count=32, held_out_count=31,
            held_out_geometries_excluded_from_both_training_sets=True,
            preceding_experiment_status=old['status'], preceding_experiment_metrics=old['metrics'])
        return report
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        report['elapsed_seconds'] = time.monotonic() - start
        base.write_json(output, report)


def verify_existing(acceptance: Path, output: Path) -> dict:
    """Replay hashed real evidence; this never claims a fresh physical run."""
    output = base._external_run_path(output)
    if output.exists():
        raise FileExistsError('Existing evidence must not be overwritten')
    report = json.loads(acceptance.read_text())
    protocol = report['protocol']
    protocol_path = Path(report['work_directory']) / 'predeclared-protocol.json'
    if base.digest(protocol_path) != report['protocol_sha256'] or json.loads(protocol_path.read_text()) != protocol:
        raise ValueError('Original predeclared protocol identity does not verify')
    previous = Path(protocol['previous_experiment_path'])
    if base.digest(previous) != protocol['previous_experiment_sha256']:
        raise ValueError('Preceding development evidence identity does not verify')
    old = json.loads(previous.read_text())
    train_distances = np.linspace(.55, 1.80, 32)
    dense_distances = np.linspace(.55, 1.80, 128)
    held_distances = train_distances[:-1] + .37 * np.diff(train_distances)
    for key, expected in (
        ('correction_train_distances_angstrom', train_distances),
        ('baseline_train_distances_angstrom', dense_distances),
        ('new_held_out_distances_angstrom', held_distances),
    ):
        if not np.array_equal(protocol[key], expected):
            raise ValueError('Recorded protocol does not match the declared fixed grid')
    if protocol['fitting_configuration'] != base.DeltaFittingConfig().model_dump(mode='json'):
        raise ValueError('This replay must use the same unchanged default fitting configuration')
    original_train = [point for point in old['calculations'] if point['partition'] == 'train']
    if report['reused_training_calculations'] != original_train:
        raise ValueError('Reused training records differ from their original evidence')
    original_energies = {}
    checked_pairs = 0
    for point in old['calculations']:
        for method in ('low', 'high'):
            original_energies[(point['partition'], point['index'], method)] = read_recorded_energy(point, method)
            checked_pairs += 1
    if len(original_train) != 32 or not np.array_equal(
        [point['distance_angstrom'] for point in original_train], train_distances
    ):
        raise ValueError('Original correction training grid changed')
    new_records = {label: [point for point in report['calculations'] if point['partition'] == label]
                   for label in ('baseline_train', 'new_held_out')}
    if len(report['calculations']) != 159:
        raise ValueError('Unexpected number of contributing new point records')
    for label, expected in (('baseline_train', dense_distances), ('new_held_out', held_distances)):
        if not np.array_equal([point['distance_angstrom'] for point in new_records[label]], expected):
            raise ValueError('Actual point records differ from their predeclared grid')
        if [point['index'] for point in new_records[label]] != list(range(len(expected))):
            raise ValueError('Recorded point indexing changed')
    for distance in held_distances:
        if any(abs(distance - value) < 1e-12 for value in np.concatenate((dense_distances, train_distances))):
            raise ValueError('New validation geometry appears in a training grid')
        if any(abs(distance - point['distance_angstrom']) < 1e-12 for point in old['calculations']):
            raise ValueError('New validation geometry had previously been evaluated')
    dense_low = []
    for point in new_records['baseline_train']:
        dense_low.append(read_recorded_energy(point, 'low'))
        checked_pairs += 1
    held_low, held_high = [], []
    for point in new_records['new_held_out']:
        held_low.append(read_recorded_energy(point, 'low'))
        held_high.append(read_recorded_energy(point, 'high'))
        checked_pairs += 2
    held_geoms = np.asarray([coords(r) for r in held_distances])
    model, summary = base.AutoPESOrchestrator(symbols=['H', 'H'],
        low_method=protocol['lower_method'], high_method=protocol['higher_method'],
        fit_config=base.DeltaFittingConfig()).fit_delta_surface_from_data(
            train_geoms=np.asarray([coords(r) for r in train_distances]),
            train_low_energies=np.asarray([original_energies[('train', i, 'low')] for i in range(32)]),
            train_high_energies=np.asarray([original_energies[('train', i, 'high')] for i in range(32)]),
            held_out_geoms=held_geoms, held_out_low_energies=np.asarray(held_low),
            held_out_high_energies=np.asarray(held_high),
            dense_dft_geoms=np.asarray([coords(r) for r in dense_distances]), dense_dft_energies=np.asarray(dense_low))
    metrics = {}
    predictions = {
        'paired_correction': model.predict_total_energy(held_geoms, v_low_eval=np.asarray(held_low)),
        'standalone_prediction': model.predict_total_energy(held_geoms, allow_unvalidated_baseline=True)}
    for name, prediction in predictions.items():
        error = (prediction - np.asarray(held_high)) * base.HARTREE_TO_CM1
        metrics[name] = {'rmse_cm1': float(np.sqrt(np.mean(error ** 2))),
                        'maximum_absolute_error_cm1': float(np.max(np.abs(error)))}
        for metric, value in metrics[name].items():
            if not math.isclose(value, report['metrics'][name][metric], rel_tol=0, abs_tol=1e-7):
                raise ValueError('Recomputed metric differs from genuine acceptance evidence')
        if not np.allclose(prediction, report['metrics'][name]['predicted_energies_hartree'], rtol=0, atol=1e-12):
            raise ValueError('Recomputed predictions differ from recorded acceptance')
    met = all(v['rmse_cm1'] <= 10 and v['maximum_absolute_error_cm1'] <= 10 for v in metrics.values())
    if met != report['bounded_10_cm1_target_met'] or report['status'] != ('passed' if met else 'measured_threshold_not_met'):
        raise ValueError('Original pass/fail status differs from its independently recomputed result')
    replay = {'status': 'passed', 'mode': 'existing_evidence_replay', 'new_physical_calculations': False,
              'verified_utc': datetime.now(timezone.utc).isoformat(),
              'generator_sha256': base.digest(Path(__file__)),
              'source_acceptance_path': str(acceptance.resolve()), 'source_acceptance_sha256': base.digest(acceptance),
              'source_protocol_sha256': report['protocol_sha256'],
              'preceding_development_report_sha256': base.digest(previous),
              'checked_genuine_input_output_pairs': checked_pairs,
              'metrics': metrics, 'bounded_10_cm1_target_met': met,
              'scientific_accuracy_established': False, 'scope': report['scope'],
              'fit_summary': summary.model_dump(mode='json')}
    output.parent.mkdir(parents=True, exist_ok=True)
    base.write_json(output, replay)
    return replay


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path)
    parser.add_argument('--previous-experiment', type=Path)
    parser.add_argument('--verify-existing', type=Path, help='Recheck retained real evidence without running new calculations')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=600)
    args = parser.parse_args()
    if args.verify_existing:
        if args.registry or args.previous_experiment:
            parser.error('--verify-existing cannot be combined with calculation arguments')
        report = verify_existing(args.verify_existing, args.output)
    else:
        if not args.registry or not args.previous_experiment:
            parser.error('Calculations require --registry and --previous-experiment')
        report = execute(args.registry, args.previous_experiment, args.output, args.timeout)
    print(json.dumps({'status': report['status'], 'metrics': report['metrics']}, indent=2))
    return 0 if report['bounded_10_cm1_target_met'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
