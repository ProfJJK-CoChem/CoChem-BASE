"""Pytest reporting plugin; collects real outcomes without importing application code."""
from __future__ import annotations

import json
from pathlib import Path

from _pytest.reports import TestReport

try:
    from _pytest.subtests import SubtestContext, SubtestReport
except ModuleNotFoundError as error:
    if error.name != "_pytest.subtests":
        raise
    # Older pytest's ordinary reports retain their existing strict accounting.
    # Third-party subreport types are not silently treated as builtin subtests.
    SubtestContext = SubtestReport = None


def pytest_addoption(parser):
    parser.addoption("--cochem-evidence", help="Write actual per-node acceptance outcomes as JSON")


def pytest_configure(config):
    config._cochem_outcomes = {}
    config._cochem_subtests = {}
    config._cochem_collection_errors = []
    config._cochem_deselected = []


def pytest_runtest_logreport(report):
    # The hook does not receive config. Pytest owns this one plugin instance for
    # one process; no application test objects or physics values are intercepted.
    if _active_config is None:
        return
    subtest = SubtestReport is not None and type(report) is SubtestReport
    if subtest:
        if type(report.context) is not SubtestContext or report.when != "call":
            raise TypeError("Unsupported builtin pytest subtest report/context")
        rows = _active_config._cochem_subtests.setdefault(report.nodeid, [])
    elif type(report) is TestReport:
        rows = _active_config._cochem_outcomes.setdefault(report.nodeid, [])
    else:
        raise TypeError("Unsupported pytest runtime report type")
    reason = None
    if report.skipped:
        if isinstance(report.longrepr, tuple):
            reason = str(report.longrepr[2]).removeprefix("Skipped: ")
        else:
            reason = str(report.longrepr)
    row = {"phase": report.when, "outcome": report.outcome, "reason": reason,
           "xfail": getattr(report, "wasxfail", None), "duration_seconds": report.duration}
    if subtest:
        row.update(report_type="_pytest.subtests.SubtestReport", context=report.context._to_json())
    rows.append(row)


_active_config = None


def pytest_sessionstart(session):
    global _active_config
    _active_config = session.config


def pytest_collectreport(report):
    if _active_config is not None and report.failed:
        _active_config._cochem_collection_errors.append({"nodeid": report.nodeid, "error": str(report.longrepr)})
    if _active_config is not None and report.skipped:
        _active_config._cochem_outcomes[report.nodeid] = [{
            "phase": "collection", "outcome": "skipped", "reason": str(report.longrepr),
        }]


def pytest_deselected(items):
    if _active_config is not None:
        _active_config._cochem_deselected.extend(item.nodeid for item in items)


def pytest_collection_finish(session):
    session.config._cochem_collected_nodeids = [item.nodeid for item in session.items]


def pytest_sessionfinish(session, exitstatus):
    target = session.config.getoption("--cochem-evidence")
    if target:
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "schema_version": 1,
            "exit_code": int(exitstatus),
            "collected": session.testscollected,
            "collected_nodeids": getattr(session.config, "_cochem_collected_nodeids", []),
            "collection_errors": session.config._cochem_collection_errors,
            "deselected": session.config._cochem_deselected,
            "tests": session.config._cochem_outcomes,
            "subtests": session.config._cochem_subtests,
        }, indent=2) + "\n", encoding="utf-8")
