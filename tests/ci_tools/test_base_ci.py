"""Actual child-pytest evidence and immutable-input enforcement regressions."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from ci_tools.base_ci import evaluate_test_evidence
from ci_tools.source_fixtures import validate_source_fixtures

ROOT = Path(__file__).resolve().parents[2]
EMPTY_DEFERRALS = {"schema_version": 1, "deferred_tests": []}


def _execute(tmp_path: Path, source: str) -> dict:
    target = tmp_path / "test_acceptance.py"
    target.write_text(source, encoding="utf-8")
    configuration = tmp_path / "pytest.ini"
    configuration.write_text("[pytest]\n", encoding="utf-8")
    output = tmp_path / "outcomes.json"
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    subprocess.run([sys.executable, "-m", "pytest", "-c", str(configuration),
                    "-p", "ci_tools.pytest_evidence", "--cochem-evidence", str(output),
                    str(target), "-q"], cwd=tmp_path, env=env, check=False,
                   capture_output=True, text=True, encoding="utf-8")
    return json.loads(output.read_text())


def test_actual_passing_child_produces_acceptance(tmp_path):
    evidence = _execute(tmp_path, "def test_arithmetic():\n    assert 2 + 2 == 4\n")
    report = evaluate_test_evidence(evidence, EMPTY_DEFERRALS)
    assert report["passed"] and report["passed_tests"] == 1


@pytest.mark.parametrize("source", [
    "def test_failure():\n    assert 2 + 2 == 5\n",
    "import pytest\ndef test_skipped():\n    pytest.skip('unapproved missing dependency')\n",
    "import pytest\npytest.skip('skipped whole module', allow_module_level=True)\n",
    "# A zero-test run must never pass acceptance.\n",
    "import pytest\n@pytest.mark.xfail(reason='unapproved expected failure')\ndef test_failure():\n    assert False\n",
])
def test_real_failed_skipped_xfailed_and_empty_child_runs_fail_acceptance(tmp_path, source):
    report = evaluate_test_evidence(_execute(tmp_path, source), EMPTY_DEFERRALS)
    assert not report["passed"]


def test_exact_external_deferral_is_pending_not_passed(tmp_path):
    evidence = _execute(tmp_path, "import pytest\ndef test_local():\n    assert True\ndef test_external():\n    pytest.skip('real host required')\n")
    nodeid = next(name for name in evidence["tests"] if name.endswith("::test_external"))
    manifest = {"schema_version": 1, "deferred_tests": [{"nodeid": nodeid,
        "expected_skip_reason": "real host required", "prerequisites": ["physical host"]}]}
    report = evaluate_test_evidence(evidence, manifest)
    assert report["passed"] and report["passed_tests"] == 1
    assert len(report["pending_external_acceptance"]) == 1
    manifest["deferred_tests"][0]["expected_skip_reason"] = "different reason"
    assert not evaluate_test_evidence(evidence, manifest)["passed"]


def test_source_fixture_requires_exact_bytes_and_cannot_authorize_other_paths(tmp_path):
    target = tmp_path / "tests" / "water.xyz"
    target.parent.mkdir()
    target.write_text("2\ngeometry input\nH 0 0 0\nH 0 0 0.74\n")
    manifest = tmp_path / "fixtures.json"
    record = {"path": "tests/water.xyz", "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
              "purpose": "Parser input", "provenance_status": "constructed_input", "provenance": "Constructed H2 coordinates; no calculation claim"}
    manifest.write_text(json.dumps({"schema_version": 1, "fixtures": [record]}))
    assert validate_source_fixtures(tmp_path, manifest) == [record]
    target.write_text("changed")
    with pytest.raises(ValueError, match="content changed"):
        validate_source_fixtures(tmp_path, manifest)
    record["path"] = "../runtime.xyz"
    manifest.write_text(json.dumps({"schema_version": 1, "fixtures": [record]}))
    with pytest.raises(ValueError, match="specific test input"):
        validate_source_fixtures(tmp_path, manifest)


def test_forged_collected_count_or_missing_phase_cannot_pass(tmp_path):
    evidence = _execute(tmp_path, "def test_local():\n    assert 3 * 3 == 9\n")
    evidence["collected"] += 1
    assert not evaluate_test_evidence(evidence, EMPTY_DEFERRALS)["passed"]
    evidence["collected"] -= 1
    nodeid = evidence["collected_nodeids"][0]
    evidence["tests"][nodeid] = [phase for phase in evidence["tests"][nodeid] if phase["phase"] != "teardown"]
    assert not evaluate_test_evidence(evidence, EMPTY_DEFERRALS)["passed"]
