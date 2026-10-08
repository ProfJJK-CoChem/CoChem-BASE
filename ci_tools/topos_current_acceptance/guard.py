"""Prospective source/installation/named-test guards; never launch chemistry.

The committed TOPOS acceptance scripts execute all native science unchanged.
This external guard preserves original source and raw evidence identities.
"""
from __future__ import annotations

import argparse
import email
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
import re
import subprocess
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

BASE_PIN = '14202e182e1fa4f99258ed32a8ae9ba8c1c565ad'
TORQ_PIN = '79fbb111125e50627a1a2c129888a45496f368d4'
BASE_VERSION = '1.0.1'
BASE_GENERATED_TRACKED_FILES = frozenset()
BASELINE_CASES = frozenset({'hf3c-energy-gradient', 'r2scan3c-optimization-thermochemistry',
                          'wb97xv-optimization', 'counterpoise', 'goat-refinement'})
EXTENDED_CASES = ('native-hessian', 'native-vpt2', 'MP2', 'MP2-optimization', 'CCSD(T)',
                  'AUTOCI-CCSD(T)', 'DLPNO-CCSD(T1)', 'CCSD(T)-F12D/RI', 'F12-MP2',
                  'F12-RI-MP2', 'DLPNO-counterpoise', 'F12-composite')
LICENSED_TESTS = frozenset({
    'tests.v010.test_native_hessian::test_authentic_orca_native_hessian_and_verified_recovery',
    'tests.v010.test_anharmonic::test_authentic_orca_vpt2_water_and_completed_recovery',
    'tests.v010.test_reference_thermal::test_actual_licensed_orca_ordinary_thermal_reference_import',
})


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_new(path: Path, value: dict) -> None:
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def checked_source(root: Path, expected: str, *, allowed_generated=frozenset()) -> dict:
    require(re.fullmatch('[0-9a-f]{40}', expected) is not None, 'Unbound prospective scientific pin')
    git = lambda *args: subprocess.check_output(['git', '-C', str(root), *args], timeout=30)
    require(git('rev-parse', 'HEAD').decode().strip() == expected, 'Scientific HEAD differs')
    tree = git('ls-tree', '-rz', 'HEAD')
    files, changes = {}, {}
    for record in filter(None, tree.split(b'\0')):
        identity, encoded_name = record.split(b'\t', 1)
        mode, kind, object_id = identity.decode().split()
        require(kind == 'blob' and mode in {'100644', '100755'}, 'Scientific source must be a regular blob')
        name = encoded_name.decode()
        path = root / name
        require(path.is_file() and not path.is_symlink(), 'Scientific source missing or symlinked: ' + name)
        require(bool(path.stat().st_mode & 0o111) == (mode == '100755'), 'Tracked scientific source executable mode differs: ' + name)
        raw = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw, usedforsecurity=False).hexdigest()
        files[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'git_blob': blob,
                       'committed_git_blob': object_id, 'size_bytes': len(raw)}
        if blob != object_id:
            require(name in allowed_generated, 'Tracked scientific source was modified: ' + name)
            original = git('show', 'HEAD:' + name)
            changes[name] = {'committed_sha256': hashlib.sha256(original).hexdigest(),
                             'actual_sha256': files[name]['sha256'], 'actual_size_bytes': len(raw)}
    require(set(allowed_generated) <= set(files), 'Generated-file exception is not an original tracked file')
    # No arbitrary current source change can gain scientific credit through an
    # exception. Every specifically reviewed generated file remains recorded.
    return {'commit': expected, 'files': files, 'generated_tracked_changes': changes,
            'allowed_generated_tracked_files': sorted(allowed_generated)}


def require_source_manifest(observations: dict, declared: dict) -> None:
    require(declared.get('schema') == 'reviewed-immutable-full-ecosystem-Git-source-manifest/1',
            'Expected full source manifest schema differs')
    require(set(observations) == set(declared.get('sources', {})) == {'base', 'topos', 'torq'},
            'Mandatory source manifest omits or substitutes a component')
    for name, observed in observations.items():
        expected = declared['sources'][name]
        require(observed['commit'] == expected['commit'], 'Source manifest commit differs: ' + name)
        require(observed['files'] == expected['files'], 'Full immutable source manifest bytes differ: ' + name)
        require(observed['generated_tracked_changes'] == {} and observed['allowed_generated_tracked_files'] == [],
                'Unreviewed tracked generated source exception: ' + name)


def stage0_summary(summary: dict, phases: list[dict], artifacts: Path) -> list[dict]:
    require(not summary.get('dry_run'), 'Dry-run setup is not native authority')
    require(Path(summary['artifact_dir']).resolve() == artifacts.resolve(), 'Setup authority root differs')
    entries = summary.get('phases_executed', [])
    require(sorted(p['phase_number'] for p in entries) == list(range(1, 12)), 'Actual all-eleven phases missing')
    require(sorted(p['phase_number'] for p in phases) == list(range(1, 12)), 'Golden all-eleven authority missing')
    by_number = {p['phase_number']: p for p in phases}
    proofs = []
    for entry in entries:
        require(entry.get('success') is True, 'Actual phase success must be explicitly true')
        phase, report = by_number[entry['phase_number']], entry['report']
        require(entry['status'] == phase['status'] == report['status']
                and phase['status'] in {'PASSED', 'DEGRADED'}, 'Actual phase status differs or failed')
        require(not report.get('errors'), 'Phase audit has unresolved errors')
        raw_sha = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
        require(raw_sha == phase['sha256'], 'Native setup report differs from Golden authority')
        proofs.append({'phase_number': phase['phase_number'], 'success': True,
                       'status': phase['status'], 'report_sha256': raw_sha})
    return proofs


def require_named_tests(cases: dict[str, str], declared_summary: dict) -> None:
    require(bool(cases) and len(cases) == declared_summary.get('tests'), 'JUnit test count differs')
    require(all(declared_summary.get(k) == 0 for k in ('failures', 'errors', 'skipped')),
            'Native pytest summary contains failure/error/skip')
    require(all(value == 'passed' for value in cases.values()), 'Native pytest contains failure/error/skip')
    require(LICENSED_TESTS <= set(cases), 'One or more of the three exact licensed tests did not execute')


def validate_base_metadata(raw: bytes, project: dict) -> dict:
    """Validate current installed metadata without changing historical artifacts."""
    metadata = email.message_from_bytes(raw)
    require(canonicalize_name(metadata['Name']) == canonicalize_name(project['name']), 'Installed BASE Name differs')
    require(metadata['Version'] == project['version'] == BASE_VERSION, 'Installed BASE Version differs from F1.0.1')
    require(metadata['Requires-Python'] == project['requires-python'], 'Installed BASE Python requirement differs')

    def normalized(text):
        item = Requirement(text)
        return (canonicalize_name(item.name), tuple(sorted(item.extras)), str(item.specifier),
                item.url, str(item.marker) if item.marker is not None else None)

    expected = [normalized(text) for text in project.get('dependencies', [])]
    for extra, dependencies in project.get('optional-dependencies', {}).items():
        for text in dependencies:
            require(';' not in text, 'F dependency marker needs explicit reviewed composition')
            expected.append(normalized(text + '; extra == "' + extra + '"'))
    observed = [normalized(text) for text in metadata.get_all('Requires-Dist', [])]
    require(sorted(expected, key=repr) == sorted(observed, key=repr), 'Installed BASE dependency fields differ from pinned F pyproject')
    require(set(metadata.get_all('Provides-Extra', [])) == set(project.get('optional-dependencies', {})),
            'Installed BASE optional dependency extras differ')
    return {'name': metadata['Name'], 'version': metadata['Version'],
            'requires_python': metadata['Requires-Python'], 'requires_dist': metadata.get_all('Requires-Dist', []),
            'provides_extra': metadata.get_all('Provides-Extra', []),
            'metadata_sha256': hashlib.sha256(raw).hexdigest(), 'pinned_pyproject_dependency_fields_match': True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['preflight', 'postflight'], required=True)
    parser.add_argument('--topos-commit', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    receipt = {'schema': 'prospective-current-topos-orca-evidence-guard/1', 'phase': args.phase,
               'status': 'failed', 'full_R2_completed': False, 'scientific_accuracy_certified': False,
               'scope': 'Current-source native implementation acceptance; full R2 and reference campaigns separate'}
    try:
        receipt['guard_sha256'] = digest(Path(__file__))
        require(receipt['guard_sha256'] == os.environ['GUARD_EXPECTED_SHA256'], 'External evidence guard changed')
        require(os.environ['CONTROLLER_PRIVATE'] == 'true', 'Controller must be private')
        require(os.environ['GITHUB_REPOSITORY'] == 'ProfJJK-CoChem/CoChem-BASE', 'Wrong controlled repository')
        require(os.environ['GITHUB_EVENT_NAME'] == 'workflow_dispatch', 'Manual reviewed dispatch required')
        require(os.environ['RUNNER_ENVIRONMENT'] == 'github-hosted'
                and os.environ['RUNNER_OS'] == 'Linux' and os.environ['RUNNER_ARCH'] == 'X64', 'Wrong hosted compute')
        roots = {name: Path(os.environ['COCHEM_' + name.upper() + '_ROOT']).resolve()
                 for name in ('base', 'topos', 'torq')}
        receipt['scientific_source'] = {
            'base': checked_source(roots['base'], BASE_PIN, allowed_generated=BASE_GENERATED_TRACKED_FILES),
            'topos': checked_source(roots['topos'], args.topos_commit),
            'torq': checked_source(roots['torq'], TORQ_PIN),
        }
        source_manifest = out / 'expected-full-source-manifest.json'
        require(source_manifest.is_file() and not source_manifest.is_symlink(), 'Reviewed full source manifest missing')
        receipt['expected_source_manifest_sha256'] = digest(source_manifest)
        require(receipt['expected_source_manifest_sha256'] == os.environ['SOURCE_MANIFEST_SHA256'],
                'Reviewed full source manifest changed')
        require_source_manifest(receipt['scientific_source'], json.loads(source_manifest.read_text()))
        require(importlib.metadata.version('CoChem-BASE') == BASE_VERSION, 'BASE distribution differs from F1.0.1')
        distribution = importlib.metadata.distribution('CoChem-BASE')
        metadata_files = [entry for entry in distribution.files or [] if str(entry).endswith('.dist-info/METADATA')]
        require(len(metadata_files) == 1, 'Current installed BASE requires one distribution metadata file')
        installed_metadata = Path(distribution.locate_file(metadata_files[0])).resolve()
        require(installed_metadata.is_file() and not installed_metadata.is_symlink(), 'Installed BASE metadata missing or symlinked')
        project = tomllib.loads((roots['base'] / 'pyproject.toml').read_text())['project']
        receipt['installed_base_metadata'] = validate_base_metadata(installed_metadata.read_bytes(), project)
        receipt['installed_base_metadata']['path'] = str(installed_metadata)
        entrypoints = {entry.name: entry.value for entry in distribution.entry_points if entry.group == 'console_scripts'}
        require(entrypoints == project.get('scripts', {}), 'Installed BASE console entry points differ')
        receipt['installed_base_metadata']['console_scripts'] = entrypoints
        namespace = importlib.util.find_spec('cochem_base')
        require(namespace is not None and namespace.origin is None, 'BASE namespace shadowed')
        locations = list(namespace.submodule_search_locations or [])
        expected_src = str(roots['base'] / 'src/cochem_base')
        allowed_hook = '__editable__.cochem_base-1.0.1.finder.__path_hook__'
        require(expected_src in locations and all(p in {expected_src, allowed_hook} for p in locations),
                'BASE namespace source/hook does not belong to F1.0.1')
        origins = {}
        for name in ('topos.engines', 'topos.native_hessian', 'topos.orca_numerical_profiles',
                     'topos.base_integration', 'cochem_base.core_engine.execution_authority',
                     'cochem_base.core.cochem_core_registry_manager', 'cochem_base.concurrency.subprocess_broker'):
            module = importlib.import_module(name)
            path = Path(module.__file__).resolve()
            root = roots['topos'] if name.startswith('topos.') else roots['base'] / 'src'
            require(path == root / Path(name.replace('.', '/') + '.py'), 'Scientific module origin differs: ' + name)
            origins[name] = {'path': str(path), 'sha256': digest(path)}
        receipt['installed_module_origins'] = origins
        from topos.base_integration import BaseRuntime
        from topos.release import _pytest_cases, source_inventory
        from topos.orca_numerical_profiles import MAPPING_V42, numerical_profile_receipt
        runtime = BaseRuntime(Path(os.environ['COCHEM_CONFIG']))
        require(runtime.registry.verify_checksum(), 'Native Golden registry checksum differs')
        summary_path = runtime.registry_path.parent / 'setup_summary.json'
        require(summary_path.is_file() and not summary_path.is_symlink(), 'Actual setup summary missing')
        actual_summary = json.loads(summary_path.read_text())
        phases = [p.model_dump(mode='json') for p in runtime.registry.stage0.phases]
        receipt['actual_all_eleven_setup_phases'] = stage0_summary(actual_summary, phases, Path(os.environ['COCHEM_ARTIFACT_DIR']))
        receipt['setup_summary_sha256'] = digest(summary_path)
        receipt['registry'] = runtime.provenance()
        receipt['numerical_profile'] = numerical_profile_receipt(MAPPING_V42)
        require(receipt['numerical_profile'] is not None, 'Current explicit numerical profile absent')
        with (out / ('actual-stage0-summary-' + args.phase + '.json')).open('xb') as stream:
            stream.write(summary_path.read_bytes())
        binary = runtime.resolve_executable('orca')
        receipt['orca_executable_sha256'] = digest(Path(binary))
        receipt['controller'] = json.loads((out / 'controller.json').read_text())
        require(receipt['controller']['head_sha'] == os.environ['GITHUB_SHA'] == os.environ['GITHUB_WORKFLOW_SHA'],
                'Actual controller workflow/source identities differ')
        if args.phase == 'postflight':
            native_root = Path(os.environ['RUNNER_TEMP'])
            baseline_root = native_root / 'topos-orca-evidence'
            extended_root = native_root / 'topos-orca-extended'
            baseline = json.loads((baseline_root / 'acceptance.json').read_text())
            extended = json.loads((extended_root / 'acceptance.json').read_text())
            require(baseline.get('status') == 'passed' and set(baseline['requested_cases']) == BASELINE_CASES
                    and set(baseline['cases']) == BASELINE_CASES
                    and all(c['status'] == 'passed' for c in baseline['cases'].values()), 'Baseline native case failed or omitted')
            require(baseline['resources'] == {'threads': 2, 'memory_mb': 2048, 'budget_seconds': 10800}, 'Baseline resource contract changed')
            require(extended.get('status') == 'passed' and tuple(extended['requested_cases']) == EXTENDED_CASES
                    and set(extended['cases']) == set(EXTENDED_CASES)
                    and all(c['status'] == 'passed' for c in extended['cases'].values()), 'Extended native case failed or omitted')
            inventory = source_inventory(roots['topos'])
            native_pytest = json.loads((baseline_root / 'pytest-receipt.json').read_text())
            require(native_pytest.get('status') == 'passed', 'Native pytest receipt failed')
            cases = _pytest_cases(native_pytest, baseline_root / 'pytest-receipt.json', inventory)
            check = native_pytest['verification']['checks'][0]
            require_named_tests(cases, check['junit'])
            receipt['executed_licensed_tests'] = {name: cases[name] for name in sorted(LICENSED_TESTS)}
            receipt['receipt_sha256'] = {name: digest(p) for name, p in {
                'baseline': baseline_root / 'acceptance.json', 'extended': extended_root / 'acceptance.json',
                'licensed_pytest': baseline_root / 'pytest-receipt.json',
                'licensed_junit': baseline_root / 'native-pytest.xml'}.items()}
            receipt['native_file_inventory'] = {
                str(path.relative_to(native_root)): {'sha256': digest(path), 'size_bytes': path.stat().st_size}
                for folder in (baseline_root, extended_root) for path in sorted(folder.rglob('*')) if path.is_file()}
        receipt['status'] = 'passed'
    except Exception as exc:
        receipt.update(reason=str(exc), exception_type=type(exc).__name__)
    write_new(out / ('guard-' + args.phase + '.json'), receipt)
    print(json.dumps({'phase': args.phase, 'status': receipt['status'], 'reason': receipt.get('reason')}))
    return 0 if receipt['status'] == 'passed' else 3


if __name__ == '__main__':
    raise SystemExit(main())
