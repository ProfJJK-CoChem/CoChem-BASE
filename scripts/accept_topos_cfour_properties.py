"""One genuine TOPOS CCSD(T)/PVTZ FIRST_ORDER diagnostic, never row certification.

Run only on the reviewed private BASE Actions job after actual provisioning
and all eleven mandatory ecosystem setup phases. No fallback method or retry.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from topos.base_integration import BaseRuntime
from topos.campaign_authority import retained_registries
from topos.config import SystemConfig
from topos.external_engines import ExternalProtocol, _native_genbas, run_external
from topos.matrix_components import run_component
from topos.models import Molecule, ResourceLimits, RunRecord, RunRequest, utc_now
from topos.native_diagnostics import native_failure_tails
from topos.storage import RunStore, atomic_json, file_digest
from topos.workflow import Workflow, software_provenance

# A declared fixed-geometry property case, not an optimized or experimental structure.
# Properly rotate the declared planar seed about (1,2,3) by 0.47 rad and
# translate by (0.3,-0.2,0.4) A, so native/requested tensor frames are distinct.
WATER = Molecule(symbols=['O', 'H', 'H'], coordinates=[[0.3, -0.2, 0.4],
    [1.1633408740484075, -0.5337215443356982, 0.6547007382076628],
    [0.4362693824140611, 0.741400748956536, 0.266976373224289]])
RESOURCES = ResourceLimits(threads=2, memory_mb=2048, budget_seconds=3600)
TORQ_REF = '79fbb111125e50627a1a2c129888a45496f368d4'
TEXT_NAMES = {'ZMAT', 'GRD', 'DIPOL', 'EFG', 'FCMFINAL', 'engine.stdout', 'engine.stderr',
              'engine-cfour-runtime.json', 'protocol.json', 'native-result.json', 'matrix-component-result.json'}


def checkout(root: Path, expected: str, module: str | None) -> dict:
    if not re.fullmatch('[a-f0-9]{40}', expected):
        raise ValueError('Every source identity requires its reviewed full Git SHA')
    observed = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, text=True, capture_output=True, check=True).stdout.strip()
    if observed != expected:
        raise ValueError(f'{module} checkout differs from the reviewed source')
    subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', '*.py', '*.toml', '*.yml', '*.json'],
                   cwd=root, capture_output=True, check=True)
    if module is None:
        # Discover mandatory TORQ through BASE; do not execute its bootstrap.
        return {'commit': observed, 'scope': 'Source identity; mandatory distribution discovery is recorded by BASE'}
    path = Path(importlib.import_module(module).__file__).resolve()
    relative = Path(*module.split('.')).with_suffix('.py')
    expected_path = root/relative if (root/relative).is_file() else root/'src'/relative
    if not expected_path.is_file() or file_digest(path) != file_digest(expected_path):
        raise ValueError(f'{module} imported bytes differ from the reviewed source checkout')
    return {'commit': observed, 'imported_module': str(path), 'module_sha256': file_digest(path)}


def protocol(library: Path, digest: str) -> ExternalProtocol:
    # PVTZ is the explicit CFOUR native cc-pVTZ alias already allowed by TOPOS.
    # All-electron treatment is declared for this diagnostic, not inferred from
    # the source row (whose property core treatment is an explicit caller choice).
    return ExternalProtocol(engine='cfour', engine_version='2.1', operation='first-order-properties',
        method='CCSD(T)', orbital_basis='PVTZ', frozen_core=False,
        genbas_path=str(library), genbas_sha256=digest)


def require_stage0(runtime: BaseRuntime, artifacts: Path) -> dict:
    setup = json.loads((artifacts/'setup-receipt.json').read_text())
    validation = json.loads((artifacts/'mandatory-validation.json').read_text())
    phases = runtime.registry.stage0.phases if runtime.registry.stage0 is not None else []
    if (setup.get('status') != 'completed' or validation.get('status') != 'verified'
            or not runtime.registry.verify_checksum()
            or sorted(p.phase_number for p in phases) != list(range(1, 12))
            or any(p.status not in {'PASSED', 'DEGRADED'} for p in phases)
            or sorted(validation.get('selected_repositories', [])) != ['CoChem-BASE', 'CoChem-TOPOS', 'CoChem-TORQ']):
        raise RuntimeError('A fresh successful complete eleven-phase mandatory ecosystem audit is required')
    if validation.get('runtime', {}).get('registry_sha256') != runtime.provenance()['registry_sha256']:
        raise RuntimeError('The mandatory validation does not identify this exact audited registry')
    registry_path = Path(runtime.registry_path).resolve()
    if registry_path != artifacts.resolve()/'Registry'/'cochem_system_config.json':
        raise RuntimeError('Stage 0 registry is outside the declared fresh artifact root')
    # Reuse the strict portable verifier: every actual summary entry must have
    # success is True, and its unchanged report hashes to its Golden Registry
    # phase. Raw reports do not have a success field.
    registries, proofs = retained_registries(artifacts.resolve(), [registry_path])
    digest = runtime.provenance()['registry_sha256']
    observed = registries.get(digest)
    if (observed is None or observed['retained_setup_registry_path'] != str(registry_path)
            or {k: v for k, v in observed.items() if k != 'retained_setup_registry_path'}
            != runtime.registry.model_dump(mode='json')):
        raise RuntimeError('Actual Stage 0 reports do not bind this current runtime registry')
    return {'setup_receipt_sha256': file_digest(artifacts/'setup-receipt.json'),
            'mandatory_validation_sha256': file_digest(artifacts/'mandatory-validation.json'),
            'phases': [p.model_dump(mode='json') for p in phases],
            'actual_report_bindings': proofs}



def export_text_evidence(work: Path, destination: Path, report: dict) -> None:
    """Select only named scientific text. This is not a complete portable RunStore."""
    destination.mkdir(parents=True, exist_ok=True)
    retained, omitted = {}, []
    # Never walk snapshot caches: they duplicate complete basis/native binary data.
    for path in sorted((work/'run'/'attempts').rglob('*')):
        if not path.is_file() or path.is_symlink() or path.name not in TEXT_NAMES:
            continue
        if any(part.startswith('.') for part in path.relative_to(work).parts):
            continue
        relative = path.relative_to(work).as_posix()
        data = path.read_bytes()
        try:
            data.decode('utf-8')
            if b'\0' in data:
                raise ValueError('NUL in native artifact')
        except (UnicodeError, ValueError) as exc:
            omitted.append({'path': relative, 'sha256': file_digest(path), 'bytes': len(data),
                            'reason': 'Non-text artifact retained only in controlled job scratch: '+str(exc)})
            continue
        target = destination/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        retained[relative] = {'sha256': file_digest(target), 'size_bytes': target.stat().st_size}
    atomic_json(destination/'diagnostic.json', report)
    retained['diagnostic.json'] = {'sha256': file_digest(destination/'diagnostic.json'),
                                  'size_bytes': (destination/'diagnostic.json').stat().st_size}
    atomic_json(destination/'INDEX.json', {'scope': 'Selected actual scientific text and hashes; licensed GENBAS/ECPDATA and complete native scratch excluded; not a self-contained replay bundle',
        'files': retained, 'omitted_nontext': omitted, 'matrix_row_completed': False, 'efg_tensor_validated': False})
    if any(p.name in {'GENBAS', 'ECPDATA'} for p in destination.rglob('*')):
        raise RuntimeError('Licensed basis library appeared in selected evidence')


def run(args) -> int:
    work, evidence = args.work.resolve(), args.evidence.resolve()
    if work.exists() or evidence.exists() or evidence.is_relative_to(work) or work.is_relative_to(evidence):
        raise ValueError('Native scratch and selected evidence must be separate fresh directories')
    roots = {name: getattr(args, name+'_root').resolve() for name in ('base', 'topos', 'torq')}
    if any(work.is_relative_to(root) or evidence.is_relative_to(root) for root in roots.values()):
        raise ValueError('Diagnostic scratch/evidence must remain outside all source checkouts')
    work.mkdir(parents=True)
    report = {'schema_version': 'topos-cfour-first-order-diagnostic/1', 'status': 'running', 'started_at': utc_now(),
        'scope': 'One actual all-electron CCSD(T)/cc-pVTZ fixed-geometry FIRST_ORDER diagnostic. EFG raw output collection only; tensor/parser/nuclear-quadrupole validation remains separate.',
        'pin_scope': 'reviewed-interim-grammar-diagnostic', 'final_A_B_acceptance': False,
        'matrix_row_id': 'T3C-1h', 'matrix_row_completed': False, 'accuracy_benchmark': False,
        'efg_tensor_validated': False, 'native_retries': 0, 'resources': RESOURCES.model_dump(mode='json'),
        'molecule': WATER.model_dump(mode='json'), 'controller_sha256': file_digest(Path(__file__)),
        'github_run_id': os.environ.get('GITHUB_RUN_ID'), 'github_run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
        'github_controller_sha': os.environ.get('GITHUB_SHA')}
    started = time.monotonic()
    deadline = started + RESOURCES.budget_seconds
    exit_code = 1
    try:
        if args.torq_ref != TORQ_REF:
            raise ValueError('TORQ reference differs from the reviewed mandatory consumer')
        runtime = BaseRuntime(args.registry)
        report['checkouts'] = {name: checkout(roots[name], getattr(args, name+'_ref'), module)
            for name, module in [('base', 'cochem_base.core_engine.execution_authority'), ('topos', 'topos.external_engines'),
                                 ('torq', None)]}
        runtime.validate_resources(RESOURCES)
        report['stage0'] = require_stage0(runtime, args.artifacts)
        report['base'] = runtime.provenance()
        report['source'] = software_provenance()
        authority = runtime.cfour_runtime_identity()
        report['cfour_runtime_authority'] = authority
        from cochem_base.core_engine.cfour_runtime import verify_cfour_runtime
        actual = verify_cfour_runtime(authority['executable'])
        if actual['runtime_seal_sha256'] != authority['runtime_seal_sha256']:
            raise RuntimeError('BASE runtime preflight differs from actual execution authority')
        library = Path(actual['genbas'])
        native = protocol(library, file_digest(library))
        _native_genbas(Path(authority['executable']), native, WATER)
        report['requested_protocol'] = native.model_dump(mode='json')
        request = RunRequest(molecule=WATER, purpose='energy', engine='cfour', method=native.method,
            basis=native.orbital_basis, threads=RESOURCES.threads, memory_mb=RESOURCES.memory_mb,
            budget_seconds=RESOURCES.budget_seconds)
        record = RunRecord(request=request, status='running', metadata={'execution_authority': runtime.provenance(),
            'scope': report['scope'], 'software': software_provenance(), 'matrix_row_completed': False})
        store = RunStore(work/'run')
        store.commit(record)
        workflow = Workflow(work/'unused-runs', config=SystemConfig(execution_backend='base', base_registry_path=args.registry))
        workflow.base_runtime = runtime
        key = 'cfour-2.1-all-electron-CCSD(T)-PVTZ-FIRST_ORDER-diagnostic'
        result = run_component(workflow, record, store, key, WATER, native, run_external, deadline, None)
        if result is None:
            raise RuntimeError(f'TOPOS native property component failed: {record.status}; {record.metadata.get("termination_reason")}')
        if result.engine_version != '2.1' or result.metadata.get('execution_kind') != 'real':
            raise RuntimeError('No genuine current CFOUR result was established')
        before_count = len(record.attempts)
        original_runner = runtime.run_process
        launches = []
        def reject_relaunch(*argv, **kwargs):
            launches.append('unexpected-native-process')
            raise RuntimeError('Completed native component replay attempted a new process')
        runtime.run_process = reject_relaunch
        try:
            restored = RunRecord.model_validate(store.load())
            replay = run_component(workflow, restored, store, key, WATER, native, run_external, deadline, None)
        finally:
            runtime.run_process = original_runner
        if replay is None or replay.model_dump(mode='json') != result.model_dump(mode='json') or len(restored.attempts) != before_count or launches:
            raise RuntimeError('Persisted unchanged-runtime property replay was not exact')
        efg = [p for p in (work/'run'/'attempts').rglob('EFG') if p.is_file() and not p.is_symlink() and p.stat().st_size]
        labels = []
        for path in (work/'run'/'attempts').rglob('engine.stdout'):
            labels.extend(line for line in path.read_text(errors='strict').splitlines()
                          if re.search(r'\bEFG\b|electric field gradient', line, re.I))
        report.update(native_component_status='completed', energy_hartree=result.energy_hartree,
            native_result_metadata=result.metadata.get('native_result'), replay_verified=True,
            snapshot_id=store.verify()['snapshot_id'], efg_file_paths=[str(p.relative_to(work)) for p in efg],
            efg_file_available=bool(efg), efg_stdout_labels=labels[:40],
            status='diagnostic-evidence-collected' if efg or labels else 'native-completed-no-EFG-evidence')
        exit_code = 0 if efg or labels else 2
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as exc:
        report.update(status='failed', reason=str(exc), exception=type(exc).__name__, native_failure_tails=native_failure_tails(work))
    finally:
        report.update(finished_at=utc_now(), elapsed_seconds=time.monotonic()-started)
        atomic_json(work/'diagnostic.json', report)
        export_text_evidence(work, evidence, report)
    print(json.dumps({'status': report['status'], 'matrix_row_completed': False, 'evidence': str(evidence)}), flush=True)
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'topos', 'torq'):
        parser.add_argument('--'+name+'-root', type=Path, required=True)
        parser.add_argument('--'+name+'-ref', required=True)
    for name in ('registry', 'artifacts', 'work', 'evidence'):
        parser.add_argument('--'+name, type=Path, required=True)
    return run(parser.parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
