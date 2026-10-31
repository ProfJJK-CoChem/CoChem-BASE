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
from ci_tools.source_quarantine import source_paths

ROOT = Path(__file__).resolve().parents[2]
EMPTY_DEFERRALS = {"schema_version": 1, "deferred_tests": []}


def _execute(tmp_path: Path, source: str, *, conftest: str | None = None) -> dict:
    target = tmp_path / "test_acceptance.py"
    target.write_text(source, encoding="utf-8")
    if conftest is not None:
        (tmp_path / "conftest.py").write_text(conftest, encoding="utf-8")
    configuration = tmp_path / "pytest.ini"
    configuration.write_text("[pytest]\n", encoding="utf-8")
    output = tmp_path / "outcomes.json"
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(source_paths(ROOT)),
               PYTHONDONTWRITEBYTECODE="1",
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    child = r"""
import os,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
if os.environ.get('COCHEM_SOURCE_QUARANTINE_ROOT'):
    startup=sys.modules.get('sitecustomize')
    assert startup is not None and Path(startup.__file__).resolve()==root/'ci_tools/quarantine_startup/sitecustomize.py'
    guard=sys.modules.get('ci_tools.source_quarantine')
    assert guard is not None and Path(guard.__file__).resolve()==root/'ci_tools/source_quarantine.py'
    active=getattr(guard,'_active',None)
    assert active is not None and active['copied']==root
    assert active['original']==Path(os.environ['COCHEM_SOURCE_QUARANTINE_ORIGINAL']).resolve()
    assert active['evidence']==Path(os.environ['COCHEM_SOURCE_QUARANTINE_EVIDENCE']).resolve()
    assert active['revision']==os.environ['COCHEM_SOURCE_QUARANTINE_REVISION']
    assert not guard.loaded_origins(active)['escaped']
import ci_tools.pytest_evidence as recorder
assert Path(recorder.__file__).resolve()==root/'ci_tools/pytest_evidence.py'
import pytest
raise SystemExit(pytest.main(sys.argv[2:]))
"""
    completed = subprocess.run([sys.executable, "-B", "-c", child, str(ROOT), "-c", str(configuration),
                    "-p", "ci_tools.pytest_evidence", "--cochem-evidence", str(output),
                    str(target), "-q"], cwd=tmp_path, env=env, check=False,
                   capture_output=True, text=True, encoding="utf-8", timeout=30)
    (tmp_path / "pytest.stdout.log").write_text(completed.stdout, encoding="utf-8")
    (tmp_path / "pytest.stderr.log").write_text(completed.stderr, encoding="utf-8")
    (tmp_path / "pytest-process.json").write_text(json.dumps({
        "returncode": completed.returncode, "recorder_source_sha256": hashlib.sha256((ROOT / "ci_tools/pytest_evidence.py").read_bytes()).hexdigest(),
        "test_source_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "scope": "Actual child pytest reporting controls, no application/scientific execution"}, indent=2)+"\n")
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


@pytest.mark.parametrize("style", ["pytest", "unittest"])
def test_genuine_passing_subtests_are_separate_from_one_parent(tmp_path, style):
    source = ("def test_parent(subtests):\n"
              "    for index in range(5):\n"
              "        with subtests.test(msg='real subtest', index=index):\n"
              "            assert index < 5\n" if style == "pytest" else
              "import unittest\nclass TestParent(unittest.TestCase):\n"
              "    def test_parent(self):\n"
              "        for index in range(5):\n"
              "            with self.subTest('real subtest', index=index):\n"
              "                self.assertLess(index, 5)\n")
    evidence = _execute(tmp_path, source)
    nodeid = evidence["collected_nodeids"][0]
    assert evidence["collected"] == 1 and evidence["exit_code"] == 0
    assert [row["phase"] for row in evidence["tests"][nodeid]] == ["setup", "call", "teardown"]
    assert len(evidence["subtests"][nodeid]) == 5
    assert all(row["report_type"] == "_pytest.subtests.SubtestReport" and row["phase"] == "call"
               and row["outcome"] == "passed" and row["context"]["msg"] == "real subtest"
               for row in evidence["subtests"][nodeid])
    assert [row["context"]["kwargs"] for row in evidence["subtests"][nodeid]] == [
        {"index": str(index)} for index in range(5)]
    report = evaluate_test_evidence(evidence, EMPTY_DEFERRALS)
    assert report["passed"] and report["passed_tests"] == report["collected"] == 1
    assert report["subtest_counts"] == {"passed": 5, "failed": 0, "skipped": 0, "xfail": 0}
    assert not report["coverage_errors"]
    # An ordinary phase is still required even when all genuine subtests pass.
    evidence["tests"][nodeid] = [row for row in evidence["tests"][nodeid] if row["phase"] != "call"]
    assert not evaluate_test_evidence(evidence, EMPTY_DEFERRALS)["passed"]


@pytest.mark.parametrize("style", ["pytest", "unittest"])
def test_genuine_failed_subtest_cannot_be_counted_as_a_passing_parent(tmp_path, style):
    source = ("def test_parent(subtests):\n"
              "    with subtests.test(msg='real failing subtest', index=0):\n"
              "        assert 2 + 2 == 5\n" if style == "pytest" else
              "import unittest\nclass TestParent(unittest.TestCase):\n"
              "    def test_parent(self):\n"
              "        with self.subTest('real failing subtest', index=0):\n"
              "            self.assertEqual(2 + 2, 5)\n")
    evidence = _execute(tmp_path, source)
    nodeid = evidence["collected_nodeids"][0]
    assert any(row["outcome"] == "failed" for row in evidence["subtests"][nodeid])
    report = evaluate_test_evidence(evidence, EMPTY_DEFERRALS)
    assert not report["passed"] and report["failed_tests"] == [nodeid] and report["passed_tests"] == 0
    assert report["subtest_counts"]["failed"] == 1
    # Even a corrupted process/ordinary-call summary cannot erase the actual
    # failed child record or doublecount its collected parent as passed.
    evidence["exit_code"] = 0
    for row in evidence["tests"][nodeid]:
        if row["phase"] == "call":
            row["outcome"] = "passed"
    report = evaluate_test_evidence(evidence, EMPTY_DEFERRALS)
    assert not report["passed"] and report["passed_tests"] == 0 and report["failed_tests"] == [nodeid]


@pytest.mark.parametrize("style", ["pytest", "unittest"])
def test_genuine_skipped_subtest_is_unexpected_or_exact_pending_never_parent_pass(tmp_path, style):
    source = ("import pytest\ndef test_parent(subtests):\n"
              "    with subtests.test(msg='real skipped subtest'):\n"
              "        pytest.skip('real host required')\n" if style == "pytest" else
              "import unittest\nclass TestParent(unittest.TestCase):\n"
              "    def test_parent(self):\n"
              "        with self.subTest('real skipped subtest'):\n"
              "            self.skipTest('real host required')\n")
    evidence = _execute(tmp_path, source)
    nodeid = evidence["collected_nodeids"][0]
    report = evaluate_test_evidence(evidence, EMPTY_DEFERRALS)
    assert not report["passed"] and report["passed_tests"] == 0
    assert report["unexpected_skips"] == [{"nodeid": nodeid, "reasons": ["real host required"]}]
    assert report["subtest_counts"]["skipped"] == 1
    manifest = {"schema_version": 1, "deferred_tests": [{"nodeid": nodeid,
        "expected_skip_reason": "real host required", "prerequisites": ["physical host"]}]}
    report = evaluate_test_evidence(evidence, manifest)
    assert report["pending_external_acceptance"] == manifest["deferred_tests"]
    assert report["passed_tests"] == 0 and not report["passed"]


def test_genuine_xfailed_subtest_is_not_an_approved_skip_or_parent_pass(tmp_path):
    evidence = _execute(tmp_path, "import pytest\ndef test_parent(subtests):\n"
        "    with subtests.test(msg='real xfail'):\n        pytest.xfail('unapproved subtest xfail')\n")
    nodeid = evidence["collected_nodeids"][0]
    assert evidence["subtests"][nodeid][0]["xfail"] is not None
    report = evaluate_test_evidence(evidence, EMPTY_DEFERRALS)
    assert not report["passed"] and report["passed_tests"] == 0 and report["failed_tests"] == [nodeid]
    assert report["subtest_counts"]["xfail"] == 1


@pytest.mark.parametrize("phase", ["setup", "call", "teardown"])
@pytest.mark.parametrize("marker", [False, True])
def test_actual_duplicate_ordinary_report_is_never_a_subtest_waiver(tmp_path, phase, marker):
    # Use pytest's real reporting hook and actual TestReport serialization, not
    # monkeypatching the recorder or constructing scientific outputs.
    conftest = """
from _pytest.reports import TestReport
_current = None
_sent = False

def pytest_configure(config):
    global _current
    _current = config

def pytest_runtest_logreport(report):
    global _sent
    if report.when != PHASE or _sent:
        return
    _sent = True
    raw = report._to_json()
    if MARKER:
        raw['_report_type'] = 'SubTestReport'
        raw['_subtest.context'] = {'msg': 'misleading marker', 'kwargs': {}}
        raw['context'] = {'msg': 'not a genuine SubtestContext', 'kwargs': {}}
    duplicate = TestReport._from_json(raw)
    _current.hook.pytest_runtest_logreport(report=duplicate)
""".replace("PHASE", repr(phase)).replace("MARKER", repr(marker))
    evidence = _execute(tmp_path, "def test_parent():\n    assert 3 * 3 == 9\n", conftest=conftest)
    nodeid = evidence["collected_nodeids"][0]
    assert sum(row["phase"] == phase for row in evidence["tests"][nodeid]) == 2
    assert evidence["subtests"] == {}
    report = evaluate_test_evidence(evidence, EMPTY_DEFERRALS)
    assert not report["passed"] and report["coverage_errors"] == [f"Incomplete or duplicate execution phases: {nodeid}"]


def test_actual_unsupported_report_subclass_is_not_silently_ignored(tmp_path):
    conftest = """
from _pytest.reports import TestReport
_current = None
_sent = False

class UnsupportedReport(TestReport):
    "Unsupported reporting type used only by this actual pytest negative control."

def pytest_configure(config):
    global _current
    _current = config

def pytest_runtest_logreport(report):
    global _sent
    if report.when != 'call' or _sent:
        return
    _sent = True
    _current.hook.pytest_runtest_logreport(report=UnsupportedReport._from_json(report._to_json()))
"""
    evidence = _execute(tmp_path, "def test_parent():\n    assert 3 * 3 == 9\n", conftest=conftest)
    assert evidence["exit_code"] != 0
    assert "Unsupported pytest runtime report type" in (tmp_path / "pytest.stderr.log").read_text() + (tmp_path / "pytest.stdout.log").read_text()
    assert not evaluate_test_evidence(evidence, EMPTY_DEFERRALS)["passed"]


@pytest.mark.parametrize("corruption", ["parent", "phase", "context", "type", "outcome"])
def test_malformed_subtest_evidence_from_actual_run_is_refused(tmp_path, corruption):
    evidence = _execute(tmp_path, "def test_parent(subtests):\n"
        "    with subtests.test(index=1):\n        assert 3 * 3 == 9\n")
    nodeid = evidence["collected_nodeids"][0]
    row = evidence["subtests"][nodeid][0]
    if corruption == "parent":
        evidence["subtests"]["unknown::parent"] = evidence["subtests"].pop(nodeid)
    elif corruption == "phase":
        row["phase"] = "setup"
    elif corruption == "context":
        row["context"]["kwargs"] = {"index": 1}
    elif corruption == "type":
        row["report_type"] = "_pytest.reports.TestReport"
    else:
        row["outcome"] = ["passed"]
    report = evaluate_test_evidence(evidence, EMPTY_DEFERRALS)
    assert not report["passed"] and report["coverage_errors"]


def test_genuine_empty_reason_xpass_is_failed_while_absent_marker_is_none(tmp_path):
    evidence = _execute(tmp_path, "import pytest\ndef test_plain():\n    assert 3 * 3 == 9\n"
        "@pytest.mark.xfail(strict=False)\ndef test_empty_reason_xpass():\n    assert 3 * 3 == 9\n")
    plain = next(node for node in evidence["collected_nodeids"] if node.endswith("::test_plain"))
    xpass = next(node for node in evidence["collected_nodeids"] if node.endswith("::test_empty_reason_xpass"))
    plain_call = next(row for row in evidence["tests"][plain] if row["phase"] == "call")
    xpass_call = next(row for row in evidence["tests"][xpass] if row["phase"] == "call")
    assert evidence["exit_code"] == 0 and evidence["collected"] == 2
    assert plain_call["outcome"] == xpass_call["outcome"] == "passed"
    assert plain_call["xfail"] is None and xpass_call["xfail"] == ""
    report = evaluate_test_evidence(evidence, EMPTY_DEFERRALS)
    assert not report["passed"] and report["passed_tests"] == 1
    assert report["failed_tests"] == [xpass] and not report["coverage_errors"]
