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

from ci_tools.base_ci import InfrastructureIntegrityError, run_profile, tracked_source_snapshot
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
    assert os.environ.get('PYTHONPATH') == str(root)
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
    source = '''import os, pathlib, psutil
import cochem_base
import cochem_base.orchestrator.silo_dependency_pins as pins
import quarantine_external_provider
def test_actual_namespace_and_module_origins():
    root = pathlib.Path.cwd()
    assert all(pathlib.Path(path).resolve().is_relative_to(root) for path in cochem_base.__path__)
    assert pathlib.Path(pins.__file__).resolve().is_relative_to(root)
    assert set(pins.DEFAULT_PINS) == {'calc', 'core', 'mace', 'ui'}
    assert not pathlib.Path(psutil.__file__).resolve().is_relative_to(root)
    assert pathlib.Path(quarantine_external_provider.__file__).resolve() == pathlib.Path(os.environ['CONTROL_EXTERNAL_PROVIDER'])
'''
    root, _ = repository(tmp_path, source)
    original = Path(__file__).resolve().parents[2]
    module = "src/cochem_base/orchestrator/silo_dependency_pins.py"
    (root / module).parent.mkdir(parents=True)
    shutil.copy2(original / module, root / module)
    review_ring(root)
    revision = commit(root)

    # A real PEP 660 installation supplies both an unrelated provider and a
    # BASE namespace from a second checkout. No session environment is changed,
    # and no synthetic finder or monkeypatched import system is used.
    foreign = tmp_path / "foreign-editable-source"
    foreign_module = foreign / module
    foreign_module.parent.mkdir(parents=True)
    shutil.copy2(original / module, foreign_module)
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
                              env=dict(os.environ, CONTROL_EXTERNAL_PROVIDER=str(provider.resolve())),
                              capture_output=True, text=True, check=False, timeout=90)
    (output / "profile-controller.stdout.log").write_text(executed.stdout, encoding="utf-8")
    (output / "profile-controller.stderr.log").write_text(executed.stderr, encoding="utf-8")
    report = json.loads((output / "test-acceptance.json").read_text(encoding="utf-8"))
    assert executed.returncode == 0 and report["passed"], _profile_diagnostic(report, output) + executed.stderr
    removed = json.loads((output / "quarantine-editable-exclusions.json").read_text())
    assert any("cochem_base" in keys for keys in removed.values())
    assert all("quarantine_external_provider" not in keys for keys in removed.values())
