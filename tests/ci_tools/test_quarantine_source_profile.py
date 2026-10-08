"""Execute actual copied engineering tests with immutable source and origins."""
from __future__ import annotations

import json
import os
import shutil
import site
import subprocess
import sys
import venv
from pathlib import Path

import pytest

from ci_tools.base_ci import (
    InfrastructureIntegrityError,
    _source_origin_receipts,
    run_profile,
    tracked_source_snapshot,
)
from tests.ci_tools.integrity_control_repository import commit, repository, review_ring


def _profile_diagnostic(report: dict, output: Path) -> str:
    """Retain nested runner errors in hosted pytest's actual failure output."""
    logs = {name: (output / name).read_text(encoding="utf-8")
            for name in ("pytest.stdout.log", "pytest.stderr.log") if (output / name).is_file()}
    return json.dumps({"report": report, "logs": logs}, indent=2)

ORIGIN_TEST = '''import json, os, pathlib, sys
import ci_tools.pytest_evidence
def test_copied_source_and_existing_external_runtime():
    root = pathlib.Path.cwd().resolve()
    module = pathlib.Path(ci_tools.pytest_evidence.__file__).resolve()
    original = pathlib.Path(os.environ['CONTROL_ORIGINAL_ROOT']).resolve()
    runtime = pathlib.Path(os.environ['CONTROL_REGISTERED_RUNTIME']).resolve()
    assert module.is_relative_to(root)
    assert not module.is_relative_to(original)
    assert root != original
    assert runtime.is_file() and not runtime.is_relative_to(root)
    assert pathlib.Path(sys.executable).resolve() == runtime
    assert os.environ['COCHEM_CONFIG'] == os.environ['CONTROL_EXTERNAL_CONFIG']
    assert 'CONTROL_SECRET_NAME' in os.environ
    for injected in ('PYTHONHOME', 'PYTHONUSERBASE', 'PYTHONSTARTUP', 'PYTEST_ADDOPTS',
                     'PYTEST_PLUGINS', 'GIT_DIR', 'GIT_CONFIG_COUNT', 'GIT_CONFIG_KEY_0', 'GIT_CONFIG_VALUE_0'):
        assert injected not in os.environ
    assert os.environ['PYTHONPATH'].split(os.pathsep) == [str(root/'ci_tools/quarantine_startup'),
        str(root/'src'), str(root/'src/cochem_base'), str(root), str(root/'Libraries')]
    assert os.environ['COCHEM_SOURCE_QUARANTINE_ROOT'] == str(root)
    receipts = pathlib.Path(os.environ['COCHEM_CI_CONTROL_EVIDENCE_DIR'])
    assert receipts.is_absolute() and receipts.is_dir() and not receipts.is_relative_to(root)
    assert receipts == pathlib.Path(os.environ['CONTROL_RESULT']).parent/'profile-evidence/process-controls'
    pathlib.Path(os.environ['CONTROL_RESULT']).write_text(json.dumps(
        {'cwd':str(root), 'module':str(module), 'interpreter':str(runtime), 'pid':os.getpid()}))
'''


def test_selected_profile_executes_copied_bytes_and_preserves_external_runtime(tmp_path):
    root, revision = repository(tmp_path, ORIGIN_TEST)
    (root / "not-tracked-runtime").mkdir()
    (root / "not-tracked-runtime/license-control.txt").write_text("Engineering exclusion control.\n")
    # Release refuses untracked inputs. An explicitly ignored runtime remains
    # external to copied source and never supplies test or licensed authority.
    (root / ".git/info/exclude").write_text("not-tracked-runtime/\n")
    external = tmp_path / "external-config.json"
    external.write_text('{"scope":"engineering-control"}\n')
    result = tmp_path / "actual-control-result.json"
    env = dict(os.environ, CONTROL_ORIGINAL_ROOT=str(root),
               CONTROL_REGISTERED_RUNTIME=str(Path(sys.executable).resolve()),
               COCHEM_CONFIG=str(external), CONTROL_EXTERNAL_CONFIG=str(external),
               CONTROL_RESULT=str(result), CONTROL_SECRET_NAME="engineering-presence-marker",
               COCHEM_CI_CONTROL_EVIDENCE_DIR=str(tmp_path / "untrusted-receipt-destination"),
               QT_QPA_PLATFORM="offscreen", OMP_NUM_THREADS="1", PYTHONHOME=str(tmp_path / "untrusted-python"),
               PYTHONUSERBASE=str(tmp_path / "untrusted-usersite"), PYTHONSTARTUP=str(tmp_path / "untrusted-startup.py"),
               PYTEST_ADDOPTS="--control-injection", PYTEST_PLUGINS="unreviewed_control_plugin",
               GIT_DIR=str(tmp_path / "untrusted-git"), GIT_CONFIG_COUNT="1",
               GIT_CONFIG_KEY_0="core.hooksPath", GIT_CONFIG_VALUE_0=str(tmp_path / "untrusted-hooks"))
    before = tracked_source_snapshot(root)
    output = tmp_path / "profile-evidence"
    report = run_profile(root, output, controls=True, expected_revision=revision, timeout=60,
                         strict_deferred=True, environment=env)
    assert report["passed"], _profile_diagnostic(report, output)
    assert report["release_accepted"] and report["passed_tests"] == 1
    assert report["source_origins_verified"]
    assert report["source_binding"]["excluded_untracked_paths"] == ["not-tracked-runtime/license-control.txt"]
    copy_record = json.loads((output / "quarantine-source.json").read_text())
    assert copy_record["excluded_untracked_paths"] == ["not-tracked-runtime/license-control.txt"]
    assert not copy_record["licensed_runtime_copied"]
    assert tracked_source_snapshot(root) == before
    assert json.loads((output / "source-before.json").read_text()) == json.loads((output / "source-after.json").read_text())
    assert json.loads((output / "quarantine-source-before.json").read_text()) == json.loads((output / "quarantine-source-after.json").read_text())
    proof = json.loads(result.read_text())
    assert report["cleanup_observation"]["launcher_pid"] == proof["pid"]
    assert report["cleanup_observation"]["launcher_returncode"] == 0
    assert report["cleanup_observation"]["owned_work_stopped"]
    assert proof["cwd"] != str(root)
    assert Path(proof["module"]).is_relative_to(Path(proof["cwd"]))
    assert not Path(proof["cwd"]).exists()


def test_unsafe_control_receipt_destination_refuses_before_test_execution(tmp_path):
    root, revision = repository(tmp_path, ORIGIN_TEST)
    output = tmp_path / "unsafe-evidence"
    output.mkdir()
    destination = output / "process-controls"
    original = b"Engineering-only existing regular file; must remain unchanged.\n"
    destination.write_bytes(original)
    with pytest.raises(InfrastructureIntegrityError, match="Unsafe control receipt destination"):
        run_profile(root, output, controls=True, expected_revision=revision, timeout=60)
    assert destination.read_bytes() == original
    report = json.loads((output / "test-acceptance.json").read_text(encoding="utf-8"))
    assert not report["passed"] and not report["executed"]
    assert not (output / "pytest-outcomes.json").exists()
    assert json.loads((output / "source-before.json").read_text()) == json.loads((output / "source-after.json").read_text())


def test_strict_audit_refuses_before_selected_test_execution(tmp_path):
    adversarial = ("def unavailable_engineering_operation():\n"
                   "    raise NotImplementedError('deliberate infrastructure control')\n")
    root, revision = repository(tmp_path, adversarial)
    output = tmp_path / "audit-refusal"
    report = run_profile(root, output, controls=True, expected_revision=revision, timeout=60)
    assert not report["passed"] and not report["executed"]
    assert "[HARD_ABORT: AUDIT FAIL]" in report["error"]
    assert not (output / "pytest-outcomes.json").exists()
    assert json.loads((output / "source-before.json").read_text()) == json.loads((output / "source-after.json").read_text())


def test_executed_copy_mutation_fails_and_leaves_original_source_unchanged(tmp_path):
    adversarial = '''import pathlib
def test_source_mutation_is_detected():
    target = pathlib.Path.cwd()/'ci_tools/process_runner.py'
    target.write_bytes(target.read_bytes()+b'\\n# Controlled copied-source mutation.\\n')
    assert target.is_file()
'''
    root, revision = repository(tmp_path, adversarial)
    before = tracked_source_snapshot(root)
    output = tmp_path / "mutated-copy-evidence"
    report = run_profile(root, output, controls=True, expected_revision=revision, timeout=60)
    assert report["executed"] and report.get("passed_tests") == 1, _profile_diagnostic(report, output)
    assert not report["passed"] and not report["release_accepted"]
    assert report["quarantine_source_changed"] == ["ci_tools/process_runner.py"]
    assert tracked_source_snapshot(root) == before


def test_actual_foreign_base_editable_namespace_cannot_escape_second_checkout(tmp_path):
    source = '''import hashlib, json, os, pathlib, psutil, subprocess, sys
import cochem_base
import cochem_base.orchestrator.silo_dependency_pins as pins
import quarantine_external_provider
from ci_tools.source_quarantine import source_child_environment, source_paths
def test_actual_namespace_and_module_origins():
    root = pathlib.Path.cwd()
    assert all(pathlib.Path(path).resolve().is_relative_to(root) for path in cochem_base.__path__)
    assert pathlib.Path(pins.__file__).resolve().is_relative_to(root)
    assert {'calc', 'core', 'mace', 'ui'}.issubset(pins.DEFAULT_PINS)
    assert not pathlib.Path(psutil.__file__).resolve().is_relative_to(root)
    assert pathlib.Path(quarantine_external_provider.__file__).resolve() == pathlib.Path(os.environ['CONTROL_EXTERNAL_PROVIDER'])
    program = root/'tests/control_profile/namespace_child.py'
    scrubbed = dict(os.environ, PYTHONPATH=str(root/'not-reviewed'))
    child_environment = source_child_environment(scrubbed, selected_source=root)
    assert child_environment['PYTHONPATH'].split(os.pathsep) == source_paths(root)
    assert scrubbed['PYTHONPATH'] == str(root/'not-reviewed')
    records = []
    for isolated, command in enumerate(([sys.executable, '-B', str(program), '--grandchild'],
                    [sys.executable, '-I', '-B', str(root/'ci_tools/source_quarantine.py'), str(program)])):
        result = subprocess.run(command, env=child_environment, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data['isolated'] == isolated
        for observed in [data, *([data['grandchild']] if 'grandchild' in data else [])]:
            assert all(pathlib.Path(path).resolve().is_relative_to(root) for path in observed['namespace'])
            assert pathlib.Path(observed['module']).resolve().is_relative_to(root)
            assert observed['module_sha256'] == hashlib.sha256(pathlib.Path(pins.__file__).read_bytes()).hexdigest()
            assert observed['external_provider'] == os.environ['CONTROL_EXTERNAL_PROVIDER']
            assert observed['pid'] != os.getpid()
        records.append(data)
    pathlib.Path(os.environ['CONTROL_CHILD_RESULTS']).write_text(json.dumps(records))
    alias_cases = (
            ([sys.executable, '-B', str(program), '--foreign-alias'], 1),
            ([sys.executable, '-I', '-B', str(root/'ci_tools/source_quarantine.py'), str(program), '--foreign-alias'], 1),
            ([sys.executable, '-B', str(program), '--alias-grandchild'], 0))
    for index, (command, expected_exit) in enumerate(alias_cases + alias_cases):
        alias_evidence = pathlib.Path(os.environ['CONTROL_CHILD_RESULTS']).parent / ('alias-origin-' + str(index))
        alias_evidence.mkdir(mode=0o700)
        environment = dict(child_environment, COCHEM_SOURCE_QUARANTINE_EVIDENCE=str(alias_evidence))
        selected = os.environ['CONTROL_FOREIGN_BASE_MODULE' if index < len(alias_cases) else 'CONTROL_UNREGISTERED_BASE_MODULE']
        environment['CONTROL_FOREIGN_BASE_MODULE'] = selected
        result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=30)
        (alias_evidence / 'command.stdout.log').write_text(result.stdout)
        (alias_evidence / 'command.stderr.log').write_text(result.stderr)
        assert result.returncode == expected_exit, result.stdout + result.stderr
        assert result.stdout, result.stderr
        observed = json.loads(result.stdout)
        if 'grandchild' in observed:
            observed = observed['grandchild']
        assert pathlib.Path(observed['foreign_alias']).resolve() == pathlib.Path(selected)
        assert observed['foreign_alias_sha256'] == hashlib.sha256(pathlib.Path(observed['foreign_alias']).read_bytes()).hexdigest()
        receipts = [json.loads(path.read_text()) for path in alias_evidence.glob('*-final.json')]
        refused = next(item for item in receipts if item['pid'] == observed['pid'])
        assert not refused['passed'] and 'real_foreign_base_alias' in refused['escaped']
        assert refused['origins']['real_foreign_base_alias'] == [observed['foreign_alias']]
        assert refused['retired_source_roots']
        assert observed['external_provider'] == os.environ['CONTROL_EXTERNAL_PROVIDER']
'''
    root, _ = repository(tmp_path, source)
    original = Path(__file__).resolve().parents[2]
    shutil.copy2(original / "pyproject.toml", root / "pyproject.toml")
    module = "src/cochem_base/orchestrator/silo_dependency_pins.py"
    (root / module).parent.mkdir(parents=True)
    shutil.copy2(original / module, root / module)
    cuda_sources = "src/cochem_base/orchestrator/ml_cuda_sources.py"
    shutil.copy2(original / cuda_sources, root / cuda_sources)
    child = '''import hashlib, importlib.util, json, os, pathlib, subprocess, sys
import cochem_base
import cochem_base.orchestrator.silo_dependency_pins as pins
import quarantine_external_provider
record = {'pid':os.getpid(), 'parent_pid':os.getppid(), 'isolated':sys.flags.isolated, 'namespace':list(cochem_base.__path__),
          'module':pins.__file__, 'module_sha256':hashlib.sha256(pathlib.Path(pins.__file__).read_bytes()).hexdigest(),
          'external_provider':str(pathlib.Path(quarantine_external_provider.__file__).resolve())}
if len(sys.argv)>1 and sys.argv[1]=='--foreign-alias':
    path = pathlib.Path(os.environ['CONTROL_FOREIGN_BASE_MODULE'])
    spec = importlib.util.spec_from_file_location('real_foreign_base_alias', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    record.update(foreign_alias=module.__file__, foreign_alias_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    if not sys.flags.isolated:
        from ci_tools.source_quarantine import FORBIDDEN_ROOTS_KEY, activate_from_environment, loaded_origins
        observed = loaded_origins(activate_from_environment())
        assert 'real_foreign_base_alias' in observed['escaped']
        record['retired_lineage'] = json.loads(os.environ[FORBIDDEN_ROOTS_KEY])
        assert any(path.resolve().is_relative_to(pathlib.Path(root)) for root in record['retired_lineage'])
if len(sys.argv)>1 and sys.argv[1]=='--alias-grandchild':
    result = subprocess.run([sys.executable, '-B', __file__, '--foreign-alias'], capture_output=True, text=True, timeout=30)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'Child source verification failed' in result.stderr
    record['grandchild'] = json.loads(result.stdout)
if len(sys.argv)>1 and sys.argv[1]=='--grandchild':
    result = subprocess.run([sys.executable, '-B', __file__], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    record['grandchild'] = json.loads(result.stdout)
print(json.dumps(record), flush=True)
'''
    (root / "tests/control_profile/namespace_child.py").write_text(child, encoding="utf-8")
    review_ring(root)
    revision = commit(root)

    # A real PEP 660 installation supplies both an unrelated provider and a
    # BASE namespace from a second checkout. No session environment is changed,
    # and no synthetic finder or monkeypatched import system is used.
    foreign = tmp_path / "foreign-editable-source"
    foreign_module = foreign / module
    foreign_module.parent.mkdir(parents=True)
    shutil.copy2(original / module, foreign_module)
    shutil.copy2(original / cuda_sources, foreign / cuda_sources)
    unregistered = tmp_path / "unregistered-base-source"
    unregistered_module = unregistered / module
    unregistered_module.parent.mkdir(parents=True)
    shutil.copy2(original / module, unregistered_module)
    shutil.copy2(original / cuda_sources, unregistered / cuda_sources)
    shutil.copy2(original / "pyproject.toml", unregistered / "pyproject.toml")
    provider = foreign / "provider/__init__.py"
    provider.parent.mkdir()
    provider.write_text('"""External engineering namespace ownership control."""\n', encoding="utf-8")
    (foreign / "pyproject.toml").write_text('''[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"
[project]
name = "cochem-quarantine-editable-control"
version = "0.0.1"
[tool.setuptools]
packages = ["cochem_base", "cochem_base.orchestrator", "quarantine_external_provider"]
[tool.setuptools.package-dir]
cochem_base = "src/cochem_base"
quarantine_external_provider = "provider"
''', encoding="utf-8")
    runtime = tmp_path / "editable-runtime"
    venv.EnvBuilder(system_site_packages=True, with_pip=False).create(runtime)
    interpreter = runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    # Nested venvs inherit the base interpreter's sites, which may differ from
    # this registered test interpreter's sites. Reuse its actual external
    # engineering dependencies by path; never copy installed runtime files.
    located = subprocess.run([str(interpreter), "-I", "-B", "-c",
                              "import sysconfig; print(sysconfig.get_path('purelib'))"],
                             capture_output=True, text=True, check=True, timeout=30)
    runtime_site = Path(located.stdout.strip())
    registered_sites = [Path(path).resolve() for path in site.getsitepackages()]
    assert all(path.is_absolute() and path.is_dir() and not path.is_relative_to(original)
               for path in registered_sites), registered_sites
    (runtime_site / "registered-engineering-runtime.pth").write_text(
        "".join(str(path) + "\n" for path in registered_sites), encoding="utf-8")
    installed = subprocess.run([str(interpreter), "-I", "-B", "-m", "pip", "install",
                                "--no-deps", "--no-build-isolation", "--no-index",
                                "--disable-pip-version-check", "--no-cache-dir", "-e", str(foreign)],
                               capture_output=True, text=True, check=False, timeout=90)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    output = tmp_path / "foreign-editable-evidence"
    output.mkdir()
    (output / "editable-install.stdout.log").write_text(installed.stdout, encoding="utf-8")
    (output / "editable-install.stderr.log").write_text(installed.stderr, encoding="utf-8")
    program = ("import sys,json; print(json.dumps({name:module.MAPPING for name,module in "
               "sys.modules.items() if isinstance(getattr(module,'MAPPING',None),dict) "
               "and 'cochem_base' in module.MAPPING}))")
    observed = subprocess.run([str(interpreter), "-I", "-B", "-c", program], capture_output=True,
                              text=True, check=True, timeout=30)
    mapping = json.loads(observed.stdout)
    assert any(Path(record["cochem_base"]).resolve() == (foreign / "src/cochem_base").resolve()
               and "quarantine_external_provider" in record for record in mapping.values()), mapping
    assert all(not Path(record["cochem_base"]).resolve().is_relative_to(root)
               for record in mapping.values())
    (output / "observed-real-foreign-editable.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    # The isolated runtime is authoritative for this engineering execution,
    # while reviewed control source still supplies the actual canonical runner.
    program = ("import json,pathlib,sys; sys.path.insert(0," + repr(str(root)) + "); "
               "from ci_tools.base_ci import run_profile; "
               "report=run_profile(pathlib.Path(" + repr(str(root)) + "),pathlib.Path(" + repr(str(output)) + "),"
               "controls=True,expected_revision=" + repr(revision) + ",timeout=60,strict_deferred=True); "
               "print(json.dumps(report)); raise SystemExit(0 if report['passed'] else 1)")
    executed = subprocess.run([str(interpreter), "-I", "-B", "-c", program],
                              env=dict(os.environ, CONTROL_EXTERNAL_PROVIDER=str(provider.resolve()),
                                       CONTROL_FOREIGN_BASE_MODULE=str(foreign_module.resolve()),
                                       CONTROL_UNREGISTERED_BASE_MODULE=str(unregistered_module.resolve()),
                                       CONTROL_CHILD_RESULTS=str(output / "actual-descendant-results.json")),
                              capture_output=True, text=True, check=False, timeout=90)
    (output / "profile-controller.stdout.log").write_text(executed.stdout, encoding="utf-8")
    (output / "profile-controller.stderr.log").write_text(executed.stderr, encoding="utf-8")
    report = json.loads((output / "test-acceptance.json").read_text(encoding="utf-8"))
    assert executed.returncode == 0 and report["passed"], _profile_diagnostic(report, output) + executed.stderr
    removed = json.loads((output / "quarantine-editable-exclusions.json").read_text())
    assert any("cochem_base" in keys for keys in removed.values())
    assert all("quarantine_external_provider" not in keys for keys in removed.values())
    children = json.loads((output / "actual-descendant-results.json").read_text(encoding="utf-8"))
    actual_pids = {record["pid"] for record in children} | {children[0]["grandchild"]["pid"]}
    origin_receipts = [json.loads(path.read_text(encoding="utf-8"))
                       for path in Path(report["descendant_evidence_directory"]).glob("*.json")]
    final_pids = {record["pid"] for record in origin_receipts if record["stage"] == "final" and record["passed"]}
    assert actual_pids.issubset(final_pids)
    assert all(record["source_revision"] == revision for record in origin_receipts)


def test_ordinary_startup_refusal_is_not_swallowed_by_python(tmp_path):
    root, _ = repository(tmp_path, "def test_engineering_identity():\n    assert __name__.startswith('tests.')\n")
    marker = tmp_path / "program-ran"
    environment = dict(os.environ)
    for key in list(environment):
        if key.startswith("COCHEM_SOURCE_QUARANTINE_"):
            environment.pop(key)
    environment.update(PYTHONPATH=os.pathsep.join((str(root / "ci_tools/quarantine_startup"), str(root))),
                       COCHEM_SOURCE_QUARANTINE_ROOT=str(root), PYTHONDONTWRITEBYTECODE="1")
    program = "from pathlib import Path; Path(" + repr(str(marker)) + ").write_text('started')"
    result = subprocess.run([sys.executable, "-B", "-c", program], env=environment,
                            capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 1
    assert "[HARD_ABORT: SOURCE QUARANTINE ESCAPE]" in result.stderr
    assert not marker.exists()


@pytest.mark.parametrize("field", ["source_root", "source_revision", "startup_source_sha256", "origins"])
def test_actual_child_receipt_authority_corruption_is_refused(tmp_path, field):
    root, revision = repository(tmp_path, '"""Tracked engineering source-origin script."""\n')
    original = Path(__file__).resolve().parents[2]
    evidence = tmp_path / "actual-source-origin-observations"
    evidence.mkdir(mode=0o700)
    environment = dict(os.environ, COCHEM_SOURCE_QUARANTINE_ROOT=str(root),
                       COCHEM_SOURCE_QUARANTINE_ORIGINAL=str(original),
                       COCHEM_SOURCE_QUARANTINE_EVIDENCE=str(evidence),
                       COCHEM_SOURCE_QUARANTINE_REVISION=revision)
    result = subprocess.run([sys.executable, "-I", "-B", str(root / "ci_tools/source_quarantine.py"),
                             str(root / "tests/control_profile/test_engineering.py")],
                            env=environment, capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    observations = _source_origin_receipts(evidence, root, original, revision)
    assert not observations["authority_errors"] and not observations["failed"]
    assert {record["stage"] for record in observations["records"]} == {"initial", "final"}
    receipt = next(evidence.glob("*-final.json"))
    actual = json.loads(receipt.read_text(encoding="utf-8"))
    actual[field] = {"outside": [str(original)]} if field == "origins" else "unreviewed-source-authority"
    receipt.write_text(json.dumps(actual), encoding="utf-8")
    refused = _source_origin_receipts(evidence, root, original, revision)
    assert refused["authority_errors"]
    assert not any(record["stage"] == "final" for record in refused["records"])


def test_isolated_child_refuses_untracked_script_before_execution(tmp_path):
    root, revision = repository(tmp_path, '"""Tracked source control."""\n')
    original = Path(__file__).resolve().parents[2]
    evidence = tmp_path / "isolated-refusal-observations"
    evidence.mkdir(mode=0o700)
    marker = tmp_path / "untracked-program-ran"
    script = root / "untracked_control.py"
    script.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\n",
                      encoding="utf-8")
    environment = dict(os.environ, COCHEM_SOURCE_QUARANTINE_ROOT=str(root),
                       COCHEM_SOURCE_QUARANTINE_ORIGINAL=str(original),
                       COCHEM_SOURCE_QUARANTINE_EVIDENCE=str(evidence),
                       COCHEM_SOURCE_QUARANTINE_REVISION=revision)
    result = subprocess.run([sys.executable, "-I", "-B", str(root / "ci_tools/source_quarantine.py"), str(script)],
                            env=environment, capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode != 0
    assert "must be tracked reviewed source" in result.stderr
    assert not marker.exists()


def test_source_observations_reresolve_actual_moving_module_symlink(tmp_path):
    """A real module alias cannot retain copied authority after its link moves."""
    source = '''import json, os, pathlib, subprocess, sys
def test_changed_real_module_origin_is_refused():
    program = r"""
import hashlib, importlib.util, json, os, pathlib, sys
from ci_tools.source_quarantine import activate_from_environment, loaded_origins
state = activate_from_environment()
root = pathlib.Path.cwd()
copied_module = root / 'src/cochem_base/orchestrator/silo_dependency_pins.py'
foreign_module = pathlib.Path(os.environ['CONTROL_FOREIGN_PIN_MODULE'])
link = pathlib.Path(os.environ['CONTROL_MOVING_MODULE_LINK'])
link.symlink_to(copied_module)
spec = importlib.util.spec_from_file_location('actual_moving_module_alias', link)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
assert {'calc', 'core', 'mace', 'ui'}.issubset(module.DEFAULT_PINS)
before = loaded_origins(state)
assert spec.name in before['origins'] and spec.name not in before['escaped']
assert before['origins'][spec.name] == [str(link)]
copied_sha = hashlib.sha256(copied_module.read_bytes()).hexdigest()
link.unlink()
link.symlink_to(foreign_module)
after = loaded_origins(state)
assert spec.name in after['escaped']
assert after['origins'][spec.name] == [str(link)]
assert hashlib.sha256(copied_module.read_bytes()).hexdigest() == copied_sha
assert any(foreign_module.is_relative_to(path) for path in state['retired_roots'])
print(json.dumps({'alias': spec.name, 'raw_origin': str(link),
    'before_resolved': str(copied_module.resolve()), 'after_resolved': str(link.resolve()),
    'copied_source_sha256': copied_sha, 'foreign_source_sha256': hashlib.sha256(foreign_module.read_bytes()).hexdigest(),
    'before_refused': spec.name in before['escaped'], 'after_refused': spec.name in after['escaped']}), flush=True)
"""
    evidence = pathlib.Path(os.environ['CONTROL_MOVING_CHILD_EVIDENCE'])
    evidence.mkdir(mode=0o700)
    environment = dict(os.environ, COCHEM_SOURCE_QUARANTINE_EVIDENCE=str(evidence))
    result = subprocess.run([sys.executable, '-B', '-c', program], capture_output=True,
        text=True, timeout=30, env=environment)
    pathlib.Path(os.environ['CONTROL_MOVING_RESULT']).write_text(json.dumps(
        {'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}))
    assert result.returncode == 1, result.stdout + result.stderr
    assert '[HARD_ABORT: SOURCE QUARANTINE ESCAPE]' in result.stderr
    observed = json.loads(result.stdout)
    assert not observed['before_refused'] and observed['after_refused']
    assert pathlib.Path(observed['before_resolved']).is_relative_to(pathlib.Path.cwd())
    assert observed['after_resolved'] == os.environ['CONTROL_FOREIGN_PIN_MODULE']
    final = [json.loads(path.read_text()) for path in evidence.glob('*-final.json')]
    assert len(final) == 1 and not final[0]['passed']
    assert observed['alias'] in final[0]['escaped']
    assert final[0]['origins'][observed['alias']] == [observed['raw_origin']]
'''
    root, _ = repository(tmp_path, source)
    original = Path(__file__).resolve().parents[2]
    relative = Path("src/cochem_base/orchestrator/silo_dependency_pins.py")
    actual_module = original / relative
    copied_module = root / relative
    copied_module.parent.mkdir(parents=True)
    shutil.copy2(actual_module, copied_module)
    shutil.copy2(original / "pyproject.toml", root / "pyproject.toml")
    review_ring(root)
    revision = commit(root)
    output = tmp_path / "moving-symlink-origin-evidence"
    observed = tmp_path / "moving-symlink-observation.json"
    environment = dict(os.environ, CONTROL_FOREIGN_PIN_MODULE=str(actual_module),
        CONTROL_MOVING_MODULE_LINK=str(tmp_path / "actual-moving-module.py"),
        CONTROL_MOVING_CHILD_EVIDENCE=str(tmp_path / "actual-moving-child-receipts"),
        CONTROL_MOVING_RESULT=str(observed))
    before = tracked_source_snapshot(root)
    report = run_profile(root, output, controls=True, expected_revision=revision,
        timeout=60, strict_deferred=True, environment=environment)
    assert report["passed"], _profile_diagnostic(report, output)
    assert report["passed_tests"] == 1 and report["source_origins_verified"]
    assert tracked_source_snapshot(root) == before
    actual = json.loads(observed.read_text())
    assert actual["returncode"] == 1
    assert json.loads(actual["stdout"])["after_refused"]
