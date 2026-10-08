"""Canonical BASE alpha acceptance driver, isolated from application imports.

Static inspection is necessary but does not establish physical correctness.
Actual pytest outcomes, immutable source inputs and source-change detection are
separate gates. Deferred acceptance is reported as pending, never as a pass.
"""
from __future__ import annotations

import argparse
import ast
import configparser
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ci_tools.anti_spoof_linter import run_linter
from ci_tools.ci_airgap_sweep import run_airgap_sweep
from ci_tools.mendeleev_ast_linter import scan_directory, scan_file
from ci_tools.reviewed_test_controls import is_reviewed_control, validate_test_controls
from ci_tools.source_fixtures import validate_source_fixtures

SOURCE_TARGETS = ("src", "cochem", "ui", "frontend", "scripts", ".scripts", "cli.py", "ci_tools")


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def selected_tests(root: Path) -> list[Path]:
    config = configparser.ConfigParser()
    if not config.read(root / "pytest.ini", encoding="utf-8"):
        raise ValueError("Canonical pytest.ini is missing")
    compatibility = configparser.ConfigParser()
    if not compatibility.read(root / "pytest-srs.ini", encoding="utf-8") or dict(config["pytest"]) != dict(compatibility["pytest"]):
        raise ValueError("pytest.ini and pytest-srs.ini must define the same acceptance profile")
    entries = config.get("pytest", "testpaths").split()
    controls = configparser.ConfigParser()
    if not controls.read(root / "ci_tools/pytest-ci.ini", encoding="utf-8"):
        raise ValueError("CI controls profile is missing")
    entries += controls.get("pytest", "testpaths").split()
    if not entries:
        raise ValueError("Canonical pytest profile has no test paths")
    paths = [(root / entry).resolve() for entry in entries]
    if any(not path.is_relative_to(root) or not path.exists() for path in paths):
        raise ValueError("Canonical test paths must exist inside this checkout")
    return paths


def selected_test_sources(root: Path) -> list[Path]:
    """Include conftest ancestry and statically imported local test helpers."""
    pending = []
    for path in selected_tests(root):
        pending.extend(path.rglob("*.py") if path.is_dir() else [path])
    found: set[Path] = set()
    while pending:
        path = pending.pop().resolve()
        if path in found:
            continue
        found.add(path)
        for parent in path.parents:
            if not parent.is_relative_to(root):
                break
            conftest = parent / "conftest.py"
            if conftest.is_file() and conftest not in found:
                pending.append(conftest)
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            modules = []
            bases = [root]
            if isinstance(node, ast.Import):
                modules = [entry.name for entry in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
                modules += [".".join(part for part in (node.module, entry.name) if part) for entry in node.names]
                if node.level:
                    bases = [path.parents[node.level - 1]]
            for base in bases:
                for module in modules:
                    target = base.joinpath(*module.split("."))
                    for candidate in (target.with_suffix(".py"), target / "__init__.py"):
                        if (candidate.is_file() and candidate.is_relative_to(root)
                                and candidate.relative_to(root).parts[0] in {"tests", "test_suite"}):
                            pending.append(candidate)
    return sorted(found)


def source_snapshot(root: Path) -> dict[str, str]:
    """Record actual audited source bytes before and after test execution."""
    selected_tests(root)
    candidates = [root / name for name in SOURCE_TARGETS]
    candidates += [root / ".github", root / ".gitattributes", root / ".gitignore",
                   root / "pytest.ini", root / "pytest-srs.ini", root / "pyproject.toml"]
    # Hash all test sources, even legacy inventory, so imported helpers cannot
    # mutate silently merely because their tests are outside this profile.
    candidates += [root / "tests", root / "test_suite"]
    if (root / "conftest.py").is_file():
        candidates.append(root / "conftest.py")
    candidates += [root / entry["path"] for entry in validate_source_fixtures(root, root / "ci_tools/source_fixtures.json")]
    files: set[Path] = set()
    for candidate in candidates:
        if candidate.is_file():
            files.add(candidate)
        elif candidate.is_dir():
            files.update(path for path in candidate.rglob("*") if path.is_file() and path.suffix in {".py", ".yml", ".json", ".toml", ".ini"} and "__pycache__" not in path.parts)
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(files)}


def audit(root: Path, output: Path) -> dict[str, Any]:
    sources = [root / entry for entry in SOURCE_TARGETS]
    _, source_findings = run_linter(sources, root)
    _, test_findings = run_linter(selected_test_sources(root), root)
    control_records = validate_test_controls(root, root / "ci_tools/reviewed_test_controls.json", test_findings)
    # Static skip sites remain visible. Whether they defer acceptance is decided
    # from actual execution below; an unexpected runtime skip always fails.
    test_blockers = {name: [item for item in rows if item.category != "PYTEST_SKIP"
                           and not is_reviewed_control(item, control_records)]
                     for name, rows in test_findings.items()}
    test_blockers = {name: rows for name, rows in test_blockers.items() if rows}
    mass_findings = []
    for path in sources:
        mass_findings.extend(scan_directory(path) if path.is_dir() else scan_file(path))
    fixture_records = validate_source_fixtures(root, root / "ci_tools/source_fixtures.json")
    fixture_paths = {entry["path"] for entry in fixture_records}
    airgap = run_airgap_sweep(root)
    # Only exact hashed test input bytes may be stored in the source plane.
    # Registry pollution and IO errors can never be waived by fixture metadata.
    permitted_fixture_categories = {"FORBIDDEN_EXTENSION", "XYZ_FORMAT_VIOLATION", "QM_LOG_VIOLATION", "MAGIC_NUMBER_VIOLATION", "HIGH_ENTROPY_VIOLATION"}
    airgap.violations = [v for v in airgap.violations if not (
        v.relative_path in fixture_paths and v.violation_type in permitted_fixture_categories)]
    airgap.is_clean = not airgap.violations and airgap.scanned_files_count > 0
    _, legacy_findings = run_linter([root], root)
    report = {
        "scope": "BASE alpha source plus canonical local acceptance profile",
        "passed": not source_findings and not test_blockers and not mass_findings and airgap.is_clean,
        "production_and_ci": {name: [v.to_dict() for v in rows] for name, rows in source_findings.items()},
        "selected_test_source": {name: [v.to_dict() for v in rows] for name, rows in test_findings.items()},
        "selected_test_blocker_count": sum(map(len, test_blockers.values())),
        "reviewed_non_scientific_test_controls": {
            "scientific_acceptance": False,
            "note": "Exact reviewed API, packaging and failure/lifecycle controls; raw findings above remain unchanged.",
            "count": len(control_records),
            "controls": control_records,
        },
        "mass_policy": [v.to_dict() for v in mass_findings],
        "airgap": airgap.to_dict(),
        "source_fixtures": fixture_records,
        "whole_repository_inventory": {
            "is_acceptance_pass": False,
            "note": "Unselected legacy tests are inventoried, not executed or certified. Findings require contextual review; adversarial fixtures are not proof of runtime fabrication.",
            "findings_count": sum(map(len, legacy_findings.values())),
            "findings": {name: [v.to_dict() for v in rows] for name, rows in legacy_findings.items()},
        },
    }
    _write(output / "source-audit.json", report)
    return report


def evaluate_test_evidence(evidence: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema_version") != 1:
        raise ValueError("Invalid deferred acceptance manifest schema")
    deferred = {}
    for entry in manifest["deferred_tests"]:
        nodeid = entry["nodeid"]
        if nodeid in deferred or not entry.get("expected_skip_reason") or not entry.get("prerequisites"):
            raise ValueError("Deferred acceptance entries require unique node IDs, reasons and prerequisites")
        deferred[nodeid] = entry
    pending = []
    unexpected = []
    passed = 0
    failed = []
    collected_ids = evidence.get("collected_nodeids", [])
    coverage_errors = []
    if (len(collected_ids) != evidence.get("collected") or len(set(collected_ids)) != len(collected_ids)
            or set(collected_ids) != set(evidence.get("tests", {}))):
        coverage_errors.append("Reported outcomes do not cover every collected test exactly once")
    for nodeid, phases in evidence.get("tests", {}).items():
        phase_names = [phase["phase"] for phase in phases]
        setup_skipped = any(phase["phase"] == "setup" and phase["outcome"] == "skipped" for phase in phases)
        expected_phases = {"setup", "teardown"} if setup_skipped else {"setup", "call", "teardown"}
        if set(phase_names) != expected_phases or len(phase_names) != len(expected_phases):
            coverage_errors.append(f"Incomplete or duplicate execution phases: {nodeid}")
        if any(phase["outcome"] == "failed" or phase.get("xfail") for phase in phases):
            failed.append(nodeid)
        skipped = [phase for phase in phases if phase["outcome"] == "skipped"]
        if skipped:
            entry = deferred.get(nodeid)
            if entry and all(phase["reason"] == entry["expected_skip_reason"] for phase in skipped):
                pending.append(entry)
            else:
                unexpected.append({"nodeid": nodeid, "reasons": [phase["reason"] for phase in skipped]})
        elif any(phase["phase"] == "call" and phase["outcome"] == "passed" for phase in phases):
            passed += 1
    ok = (evidence.get("exit_code") == 0 and evidence.get("collected", 0) > 0
          and passed > 0 and not failed and not unexpected
          and not coverage_errors and not evidence.get("collection_errors") and not evidence.get("deselected"))
    return {"passed": ok, "passed_tests": passed, "failed_tests": failed,
            "pending_external_acceptance": pending, "unexpected_skips": unexpected,
            "coverage_errors": coverage_errors,
            "collected": evidence.get("collected", 0),
            "scope": "Local runnable acceptance; pending external checks do not count as passed"}


def test(root: Path, output: Path, *, controls: bool = False) -> dict[str, Any]:
    evidence_path = output / "pytest-outcomes.json"
    evidence_path.unlink(missing_ok=True)
    before = source_snapshot(root)
    _write(output / "source-before.json", before)
    env = {key: value for key, value in os.environ.items() if key not in {"PYTEST_ADDOPTS", "PYTEST_PLUGINS"}}
    env.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    # Pytest itself runs in a child process. The CI plane never imports the app.
    profile = root / ("ci_tools/pytest-ci.ini" if controls else "pytest.ini")
    command = [sys.executable, "-m", "pytest", "-c", str(profile),
               "--rootdir", str(root),
               "-p", "ci_tools.pytest_evidence", "--cochem-evidence", str(evidence_path),
               "--junitxml", str(output / "pytest.xml"), "-q"]
    if not controls:
        command.extend(["-p", "pytest_asyncio.plugin"])
    completed = subprocess.run(command, cwd=root, env=env, check=False)
    after = source_snapshot(root)
    _write(output / "source-after.json", after)
    if not evidence_path.is_file():
        report = {"passed": False, "error": "Pytest did not publish actual outcome evidence", "exit_code": completed.returncode}
    else:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        manifest = json.loads((root / "ci_tools/deferred_acceptance.json").read_text(encoding="utf-8"))
        report = evaluate_test_evidence(evidence, manifest)
        report["command_exit_code"] = completed.returncode
        report["source_changed"] = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
        report["passed"] = report["passed"] and completed.returncode == 0 and not report["source_changed"]
    _write(output / "test-acceptance.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("audit", "test", "controls", "all"), nargs="?", default="all")
    parser.add_argument("--output", type=Path, required=True, help="External evidence directory")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output.is_relative_to(root):
        parser.error("CI evidence must be outside the source checkout")
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    try:
        if args.stage in {"audit", "all"}:
            results["audit"] = audit(root, output)
        if args.stage in {"test", "all"}:
            results["tests"] = test(root, output)
        if args.stage == "controls":
            results["controls"] = test(root, output, controls=True)
    except (OSError, ValueError, KeyError, SyntaxError, configparser.Error) as error:
        results["error"] = {"passed": False, "error": str(error)}
    passed = bool(results) and all(result["passed"] for result in results.values())
    summary = {"passed": passed, "stages": {key: {"passed": value["passed"], **({"error": value["error"]} if "error" in value else {})} for key, value in results.items()},
               "evidence_directory": str(output)}
    _write(output / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
