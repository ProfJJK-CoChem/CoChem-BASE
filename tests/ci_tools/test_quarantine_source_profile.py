"""Execute actual copied engineering tests with immutable source and origins."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from ci_tools.base_ci import run_profile, tracked_source_snapshot
from tests.ci_tools.integrity_control_repository import commit, repository, review_ring

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
    pathlib.Path(os.environ['CONTROL_RESULT']).write_text(json.dumps(
        {'cwd':str(root), 'module':str(module), 'interpreter':str(runtime)}))
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
               QT_QPA_PLATFORM="offscreen", OMP_NUM_THREADS="1", PYTHONHOME=str(tmp_path / "untrusted-python"),
               PYTHONUSERBASE=str(tmp_path / "untrusted-usersite"), PYTHONSTARTUP=str(tmp_path / "untrusted-startup.py"),
               PYTEST_ADDOPTS="--control-injection", PYTEST_PLUGINS="unreviewed_control_plugin",
               GIT_DIR=str(tmp_path / "untrusted-git"), GIT_CONFIG_COUNT="1",
               GIT_CONFIG_KEY_0="core.hooksPath", GIT_CONFIG_VALUE_0=str(tmp_path / "untrusted-hooks"))
    before = tracked_source_snapshot(root)
    output = tmp_path / "profile-evidence"
    report = run_profile(root, output, expected_revision=revision, timeout=60,
                         strict_deferred=True, environment=env)
    assert report["passed"], report
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
    assert proof["cwd"] != str(root)
    assert Path(proof["module"]).is_relative_to(Path(proof["cwd"]))
    assert not Path(proof["cwd"]).exists()


def test_strict_audit_refuses_before_selected_test_execution(tmp_path):
    adversarial = ("def unavailable_engineering_operation():\n"
                   "    raise NotImplementedError('deliberate infrastructure control')\n")
    root, revision = repository(tmp_path, adversarial)
    output = tmp_path / "audit-refusal"
    report = run_profile(root, output, expected_revision=revision, timeout=60)
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
    report = run_profile(root, tmp_path / "mutated-copy-evidence", expected_revision=revision, timeout=60)
    assert report["executed"] and report["passed_tests"] == 1
    assert not report["passed"] and not report["release_accepted"]
    assert report["quarantine_source_changed"] == ["ci_tools/process_runner.py"]
    assert tracked_source_snapshot(root) == before


def test_actual_foreign_base_editable_namespace_cannot_escape_second_checkout(tmp_path):
    source = '''import pathlib, psutil
import cochem_base
import cochem_base.core_engine.hardware_observations as observations
def test_actual_namespace_and_module_origins():
    root = pathlib.Path.cwd()
    assert all(pathlib.Path(path).resolve().is_relative_to(root) for path in cochem_base.__path__)
    assert pathlib.Path(observations.__file__).resolve().is_relative_to(root)
    assert not pathlib.Path(psutil.__file__).resolve().is_relative_to(root)
'''
    root, _ = repository(tmp_path, source)
    original = Path(__file__).resolve().parents[2]
    module = "src/cochem_base/core_engine/hardware_observations.py"
    (root / module).parent.mkdir(parents=True)
    shutil.copy2(original / module, root / module)
    review_ring(root)
    revision = commit(root)
    # This is the actual configured setuptools editable, observed in a fresh
    # interpreter. No synthetic finder or monkeypatched import system is used.
    program = ("import sys,json; print(json.dumps({name:module.MAPPING for name,module in "
               "sys.modules.items() if isinstance(getattr(module,'MAPPING',None),dict) "
               "and 'cochem_base' in module.MAPPING}))")
    observed = subprocess.run([sys.executable, "-I", "-B", "-c", program], capture_output=True,
                              text=True, check=True, timeout=30)
    mapping = json.loads(observed.stdout)
    assert mapping, "Canonical source controls require the configured BASE editable environment"
    assert all(not Path(record["cochem_base"]).resolve().is_relative_to(root)
               for record in mapping.values())
    output = tmp_path / "foreign-editable-evidence"
    report = run_profile(root, output, expected_revision=revision, timeout=60, strict_deferred=True)
    assert report["passed"], report
    removed = json.loads((output / "quarantine-editable-exclusions.json").read_text())
    assert any("cochem_base" in keys for keys in removed.values())
    (output / "observed-real-foreign-editable.json").write_text(json.dumps(mapping, indent=2) + "\n")
