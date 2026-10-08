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
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import uuid
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SOURCE_TARGETS = ("src", "cochem", "ui", "frontend", "scripts", ".scripts", "cli.py", "ci_tools")
INFRASTRUCTURE_RING = ".core_infrastructure_hashring.json"
ROOT_INFRASTRUCTURE = {"pyproject.toml", "pytest.ini", "pytest-srs.ini", "pytest.toml", "tox.ini", "setup.cfg",
                       "setup.py", "cli.py", ".gitattributes", ".gitignore", ".coveragerc", "MANIFEST.in",
                       "requirements.txt", "requirements-ui.txt", "cochem_system_config.json", "Pipfile",
                       "Pipfile.lock", "poetry.lock", "uv.lock", "package.json", "package-lock.json",
                       "pnpm-lock.yaml", "yarn.lock", "Dockerfile", "docker-compose.yml", "compose.yml"}
RUNTIME_INFRASTRUCTURE = ("src/cochem_base/orchestrator/", "src/cochem_base/core_engine/", "src/cochem_base/calc/")
RUNTIME_RUNNERS = {"src/cochem_base/interfaces/module_execution.py", "src/cochem_base/interfaces/module_registry.py",
                   "src/cochem_base/interfaces/course_access.py",
                   "src/cochem_base/cli.py",
                   "src/cochem_base/interfaces/student_setup.py", "src/cochem_base/interfaces/student_actions.py",
                   "src/cochem_base/interfaces/student_hpc.py", "src/cochem_base/interfaces/actions_jobs.py",
                   "src/cochem_base/interfaces/executors.py", "src/cochem_base/spectroscopy/spcat_runner.py",
                   "src/cochem_base/topos_runner.py", "src/cochem_base/cochem_torq_engine.py"}


class InfrastructureIntegrityError(ValueError):
    """The source does not match its independently selected Git revision."""


def _git_environment() -> dict[str, str]:
    # Network trust and injected credentials stay inherited; Git path/config
    # injection cannot redirect an inspection to another repository or hooks.
    env = {key: value for key, value in os.environ.items()
           if key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
                          "GIT_CONFIG", "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS", "GIT_OBJECT_DIRECTORY",
                          "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_SHALLOW_FILE", "GIT_REPLACE_REF_BASE",
                          "GIT_NAMESPACE", "GIT_TEMPLATE_DIR"}
           and not key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_TERMINAL_PROMPT="0", GIT_NO_REPLACE_OBJECTS="1")
    return env


def _git(root: Path, args: list[str], *, timeout: int = 60) -> bytes:
    executable = shutil.which("git")
    if not executable:
        raise InfrastructureIntegrityError("[HARD_ABORT: INFRASTRUCTURE TAMPERING] Git inspection is unavailable")
    if Path(executable).resolve().is_relative_to(root.resolve()):
        raise InfrastructureIntegrityError("[HARD_ABORT: INFRASTRUCTURE TAMPERING] Git inspection executable is inside untrusted source")
    result = subprocess.run([str(Path(executable).absolute()), "--no-pager", "-c", "core.hooksPath=" + os.devnull,
                             "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
                             "-c", "core.attributesFile=" + os.devnull,
                             "-C", str(root), *args], capture_output=True,
                            env=_git_environment(), timeout=timeout, check=False)
    if result.returncode:
        # Git diagnostics may contain a configured credential URL. Never echo
        # arbitrary environment values or Git stderr into evidence or the UI.
        raise InfrastructureIntegrityError(
            "[HARD_ABORT: INFRASTRUCTURE TAMPERING] Git source inspection failed")
    return result.stdout


def _refuse_external_git_filters(root: Path) -> None:
    # Status can invoke a configured clean filter before a byte comparison. Read
    # names only, without exposing credential-bearing config values, and refuse
    # external conversion programs rather than running them during inspection.
    executable = shutil.which("git")
    if executable is None or Path(executable).resolve().is_relative_to(root):
        raise InfrastructureIntegrityError("[HARD_ABORT: INFRASTRUCTURE TAMPERING] Git inspection is unavailable")
    result = subprocess.run([str(Path(executable).absolute()), "--no-pager", "-c", "core.fsmonitor=false",
        "-c", "core.hooksPath=" + os.devnull, "-C", str(root), "config", "--local", "--includes",
        "--name-only", "--get-regexp", r"^filter\..*\.(clean|smudge|process)$"],
        capture_output=True, env=_git_environment(), timeout=30, check=False)
    if result.returncode not in (0, 1) or result.stdout:
        raise InfrastructureIntegrityError("[HARD_ABORT: INFRASTRUCTURE TAMPERING] External Git conversion programs are not trusted infrastructure")


def tracked_source_snapshot(root: Path) -> dict[str, str]:
    """Hash every tracked file, including non-Python locks and build inputs."""
    names = _git(root, ["ls-files", "-z"]).decode("utf-8").split("\0")
    result = {}
    for name in names:
        if not name:
            continue
        target = root / name
        if target.is_symlink():
            result[name] = hashlib.sha256(os.fsencode(os.readlink(target))).hexdigest()
        elif target.is_file():
            result[name] = hashlib.sha256(target.read_bytes()).hexdigest()
        else:
            raise InfrastructureIntegrityError(
                "[HARD_ABORT: INFRASTRUCTURE TAMPERING] A tracked source file is missing")
    if not result:
        raise InfrastructureIntegrityError("[HARD_ABORT: INFRASTRUCTURE TAMPERING] No tracked source files")
    return result


def _excluded_source_guard(root: Path, tracked: dict[str, str], *, development: bool = False) -> tuple[list[str], list[str]]:
    """Exclude student data, while refusing executable/import/config injection."""
    excluded = sorted(name for name in _git(root, ["ls-files", "--others", "-z"])
                      .decode("utf-8").split("\0") if name)
    executable = {".py", ".pyc", ".pyo", ".pth", ".so", ".pyd", ".dll", ".exe", ".sh", ".ps1", ".bat", ".cmd"}
    config = {".json", ".ini", ".toml", ".yaml", ".yml", ".cfg"}
    namespaces = {"src", "cochem", "ui", "frontend", "scripts", ".scripts", "ci_tools", "Libraries",
                  "tests", "test_suite", ".github", ".devcontainer"}
    unsafe = []
    for name in excluded:
        path = root / name
        suffix = path.suffix.lower()
        if (suffix in executable or name in ROOT_INFRASTRUCTURE or (Path(name).parts[0] in namespaces and suffix in config)
                or (path.is_file() and path.stat().st_mode & 0o111)):
            unsafe.append(name)
    if unsafe and not development:
        raise InfrastructureIntegrityError("[HARD_ABORT: INFRASTRUCTURE TAMPERING] Untracked executable or source configuration")
    manifest = root / "ci_tools/source_fixtures.json"
    if manifest.is_file():
        try:
            fixtures = json.loads(manifest.read_text(encoding="utf-8"))["fixtures"]
            if any(entry["path"] not in tracked for entry in fixtures):
                raise ValueError("untracked fixture")
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise InfrastructureIntegrityError("[HARD_ABORT: INFRASTRUCTURE TAMPERING] Source fixtures require tracked reviewed bytes") from error
    return excluded, unsafe


def verify_source_binding(root: Path, *, expected_revision: str | None = None,
                          development: bool = False) -> dict[str, Any]:
    """Refuse changed initial infrastructure before importing/executing tests.

    Git's committed blobs provide a byte baseline, not a self-issued signature.
    A hosted publisher SHA is the default when provided. A separate approved
    canonical worker may supply its explicit reviewed revision instead.
    """
    root = root.resolve()
    actual_root = Path(_git(root, ["rev-parse", "--show-toplevel"]).decode().strip()).resolve()
    if actual_root != root:
        raise InfrastructureIntegrityError("[HARD_ABORT: INFRASTRUCTURE TAMPERING] Source root is not a repository root")
    _refuse_external_git_filters(root)
    revision = _git(root, ["rev-parse", "--verify", "HEAD^{commit}"]).decode().strip()
    publisher = os.environ.get("GITHUB_SHA")
    expected = expected_revision or publisher or revision
    if not re.fullmatch(r"[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", expected):
        raise InfrastructureIntegrityError("[HARD_ABORT: INFRASTRUCTURE TAMPERING] Expected revision is not immutable")
    if development and publisher:
        raise InfrastructureIntegrityError("[HARD_ABORT: INFRASTRUCTURE TAMPERING] Development mode cannot qualify a hosted publisher run")
    if revision.lower() != expected.lower():
        raise InfrastructureIntegrityError("[HARD_ABORT: INFRASTRUCTURE TAMPERING] Checkout contradicts the selected publisher revision")
    changed = _git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=no"])
    if changed and not development:
        raise InfrastructureIntegrityError("[HARD_ABORT: INFRASTRUCTURE TAMPERING] Release source is not a clean committed checkout")
    snapshot = tracked_source_snapshot(root)
    excluded, untrusted = _excluded_source_guard(root, snapshot, development=development)
    mismatched = []
    # One authenticated archive reads committed blobs without thousands of
    # subprocesses. Tar metadata is never the physical-byte authority.
    committed = {}
    with tarfile.open(fileobj=io.BytesIO(_git(root, ["archive", "--format=tar", revision]))) as archive:
        for member in archive:
            if member.isfile():
                handle = archive.extractfile(member)
                if handle is None:
                    raise InfrastructureIntegrityError("[HARD_ABORT: INFRASTRUCTURE TAMPERING] Committed source is unreadable")
                committed[member.name] = hashlib.sha256(handle.read()).hexdigest()
            elif member.issym():
                committed[member.name] = hashlib.sha256(os.fsencode(member.linkname)).hexdigest()
    for name in snapshot.keys() | committed.keys():
        if snapshot.get(name) != committed.get(name):
            mismatched.append(name)
    if mismatched and not development:
        raise InfrastructureIntegrityError("[HARD_ABORT: INFRASTRUCTURE TAMPERING] Source bytes differ from committed Git blobs")
    try:
        ring = _verify_infrastructure_ring(root)
    except InfrastructureIntegrityError:
        if not development:
            raise
        ring = {"passed": False, "status": "pending-reviewed-ring", "release_accepted": False}
    return {"passed": True, "mode": "development" if development else "release",
            "release_accepted": not development, "revision": revision, "expected_revision": expected.lower(),
            "authority": "explicit-reviewed-revision" if expected_revision else ("github-publisher-sha" if publisher else "clean-committed-head"),
            "tracked_file_count": len(snapshot), "tracked_source_sha256": hashlib.sha256(
                json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "initial_changed_paths": sorted(mismatched), "initial_dirty": bool(changed),
            "excluded_untracked_paths": excluded,
            "excluded_untrusted_source_paths": untrusted,
            "infrastructure_ring": ring}


def infrastructure_paths(root: Path) -> list[str]:
    """Complete tracked runner/build/config coverage for the reviewed ring."""
    names = _git(root, ["ls-files", "-z"]).decode("utf-8").split("\0")
    roots = {"ci_tools", "scripts", ".scripts", ".github", ".devcontainer"}
    extensions = {".py", ".json", ".ini", ".toml", ".yml", ".yaml", ".sh", ".ps1", ".bat", ".cmd", ".txt", ".lock"}
    build_names = {"Pipfile", "Pipfile.lock", "poetry.lock", "uv.lock", "package.json", "package-lock.json",
                   "pnpm-lock.yaml", "yarn.lock", "MANIFEST.in"}
    def required(name: str) -> bool:
        path = Path(name)
        return bool(name in ROOT_INFRASTRUCTURE or name in RUNTIME_RUNNERS
            or (name.startswith(RUNTIME_INFRASTRUCTURE) and path.suffix in extensions)
            or path.name in build_names or path.name.startswith("Dockerfile")
            or (path.name.startswith("requirements") and path.suffix == ".txt")
            or (path.parts[0] in roots and path.suffix in extensions))
    return sorted(name for name in names if name and required(name))


def _verify_infrastructure_ring(root: Path) -> dict[str, Any]:
    """Check a committed reviewed ring; this reader never regenerates it."""
    path = root / INFRASTRUCTURE_RING
    try:
        if path.is_symlink():
            raise ValueError("redirected ring")
        record = json.loads(path.read_text(encoding="utf-8"))
        files = record["files"]
        required = infrastructure_paths(root)
        tracked = set(_git(root, ["ls-files", "-z"]).decode("utf-8").split("\0"))
        if INFRASTRUCTURE_RING not in tracked:
            raise ValueError("uncommitted infrastructure authority")
        if record.get("schema_version") != 1 or record.get("algorithm") != "sha256" or not isinstance(files, dict):
            raise ValueError("invalid ring schema")
        if set(files) != set(required) or not required:
            raise ValueError("incomplete infrastructure coverage")
        for name, expected in files.items():
            target = root / name
            if (not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected)
                    or target.is_symlink() or not target.is_file()
                    or hashlib.sha256(target.read_bytes()).hexdigest() != expected):
                raise ValueError("infrastructure digest mismatch")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise InfrastructureIntegrityError(
            "[HARD_ABORT: INFRASTRUCTURE TAMPERING] Reviewed infrastructure ring is missing, incomplete or changed") from error
    return {"path": INFRASTRUCTURE_RING, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "file_count": len(files), "passed": True, "authority": "reviewed-committed-git-bytes"}


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
    from ci_tools.source_fixtures import validate_source_fixtures
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


def audit(root: Path, output: Path, *, expected_revision: str | None = None,
          development: bool = False) -> dict[str, Any]:
    binding = verify_source_binding(root, expected_revision=expected_revision, development=development)
    _write(output / "pre-execution-integrity.json", binding)
    # Infrastructure bytes are refused before any audit helper is imported.
    from ci_tools.anti_spoof_linter import run_linter
    from ci_tools.ci_airgap_sweep import run_airgap_sweep
    from ci_tools.mendeleev_ast_linter import scan_directory, scan_file
    from ci_tools.source_fixtures import validate_source_fixtures
    sources = [root / entry for entry in SOURCE_TARGETS]
    _, source_findings = run_linter(sources, root)
    _, test_findings = run_linter(selected_test_sources(root), root)
    # Static skip sites remain visible. Whether they defer acceptance is decided
    # from actual execution below; an unexpected runtime skip always fails.
    test_blockers = {name: [item for item in rows if item.category != "PYTEST_SKIP"]
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
        "source_binding": binding,
        "release_accepted": bool(binding["release_accepted"] and not source_findings
                                 and not test_blockers and not mass_findings and airgap.is_clean),
        "passed": not source_findings and not test_blockers and not mass_findings and airgap.is_clean,
        "production_and_ci": {name: [v.to_dict() for v in rows] for name, rows in source_findings.items()},
        "selected_test_source": {name: [v.to_dict() for v in rows] for name, rows in test_findings.items()},
        "selected_test_blocker_count": sum(map(len, test_blockers.values())),
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


_PROFILE_BOOTSTRAP = r'''
import json, pathlib, sys
copied = pathlib.Path(sys.argv[1]).resolve()
original = pathlib.Path(sys.argv[2]).resolve()
evidence = pathlib.Path(sys.argv[3]).resolve()
sys.path.insert(0, str(copied))
from ci_tools.source_quarantine import activate_from_environment, loaded_origins
state = activate_from_environment()
if state is None or state['copied'] != copied or state['original'] != original:
    raise RuntimeError('[HARD_ABORT: SOURCE QUARANTINE ESCAPE] Profile startup authority differs')
(evidence/'quarantine-editable-exclusions.json').write_text(json.dumps(state['removed'], indent=2)+'\n')
(evidence/'quarantine-import-origins-before.json').write_text(json.dumps(state['initial'], indent=2)+'\n')
import pytest
result = pytest.main(sys.argv[4:])
observed = loaded_origins(state)
(evidence/'quarantine-import-origins-after.json').write_text(json.dumps(observed, indent=2)+'\n')
raise SystemExit(result if not observed['escaped'] else 1)
'''


def _copy_reviewed_source(root: Path, destination: Path, binding: dict[str, Any]) -> None:
    executable = shutil.which("git")
    if executable is None:
        raise InfrastructureIntegrityError("[HARD_ABORT: INFRASTRUCTURE TAMPERING] Git copy is unavailable")
    # A local protocol clone copies committed source and the minimum genuine Git
    # identity. No parent .git/config, untracked file, artifact or licensed runtime
    # is copied. Disabling local hardlinks also prevents object-store mutation.
    completed = subprocess.run([str(Path(executable).absolute()), "-c", "core.hooksPath=" + os.devnull,
        "clone", "--no-local", "--no-hardlinks", "--no-checkout", "--depth=1",
        root.as_uri(), str(destination)], env=_git_environment(), capture_output=True,
        check=False, timeout=120)
    if completed.returncode:
        raise InfrastructureIntegrityError("[HARD_ABORT: SOURCE QUARANTINE COPY] Could not copy committed source")
    _git(destination, ["checkout", "--detach", binding["revision"]])
    if binding["mode"] == "development":
        # Only Git-tracked current bytes enter an explicit development copy.
        # New untracked scripts are never admitted as executable test source.
        for name in tracked_source_snapshot(root):
            original, copied = root / name, destination / name
            copied.parent.mkdir(parents=True, exist_ok=True)
            if copied.is_symlink():
                copied.unlink()
            if original.is_symlink():
                if copied.exists():
                    copied.unlink()
                copied.symlink_to(os.readlink(original))
            else:
                shutil.copy2(original, copied)
        _git(destination, ["add", "--all"])
    for name in tracked_source_snapshot(destination):
        target = destination / name
        if target.is_symlink() and not target.resolve().is_relative_to(destination):
            raise InfrastructureIntegrityError("[HARD_ABORT: SOURCE QUARANTINE ESCAPE] External source symlink")


def _profile_environment(root: Path, copied: Path, environment: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if environment is None else environment)
    for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "PYTHONSTARTUP", "PYTEST_ADDOPTS", "PYTEST_PLUGINS",
                "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_CONFIG",
                "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS", "COCHEM_CI_CONTROL_EVIDENCE_DIR"):
        env.pop(key, None)
    for key in list(env):
        if key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_", "COCHEM_SOURCE_QUARANTINE_")):
            env.pop(key)
    # An inherited runtime path may select an installed licensed engine, but
    # neither the checkout nor a relative directory may inject executables.
    entries = []
    for entry in env.get("PATH", os.defpath).split(os.pathsep):
        candidate = Path(entry)
        if entry and candidate.is_absolute() and not candidate.resolve().is_relative_to(root):
            entries.append(entry)
    env["PATH"] = os.pathsep.join(entries)
    env.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
               PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    # Ordinary descendants need the same reviewed source and startup boundary;
    # the registered runtime's external editable installation is not this source.
    env["PYTHONPATH"] = os.pathsep.join(str(path) for path in (
        copied / "ci_tools/quarantine_startup", copied / "src", copied / "src/cochem_base",
        copied, copied / "Libraries"))
    for key in ("COCHEM_ROOT", "COCHEM_REPO_DIR", "COCH_SRC", "COCHEM_WORKSPACE_ROOT"):
        env[key] = str(copied)
    # Runtime/engine/config paths outside source stay authoritative and unchanged.
    for key in ("COCHEM_MANIFEST_PATH",):
        value = env.get(key)
        if value:
            path = Path(value).expanduser().resolve()
            if path.is_relative_to(root):
                env[key] = str(copied / path.relative_to(root))
    return env


def _control_evidence_directory(output: Path) -> Path:
    """Reserve only a contained directory for small actual process receipts."""
    destination = output / "process-controls"
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise InfrastructureIntegrityError("[HARD_ABORT: SOURCE QUARANTINE EVIDENCE] Unsafe control receipt destination")
    destination.mkdir(mode=0o700, exist_ok=True)
    if destination.resolve().parent != output.resolve():
        raise InfrastructureIntegrityError("[HARD_ABORT: SOURCE QUARANTINE EVIDENCE] Control receipts escaped profile evidence")
    if os.name == "posix":
        destination.chmod(0o700)
    return destination.resolve()


def _source_origin_receipts(directory: Path, copied: Path, original: Path,
                            revision: str) -> dict[str, Any]:
    """Bind actual child observations to this source and startup producer.

    A deliberate native crash may publish its initial boundary without running
    Python's finalizers. Those records describe startup only; they never claim a
    final import observation for the terminated child.
    """
    records, errors = [], []
    expected_hash = hashlib.sha256((copied / "ci_tools/source_quarantine.py").read_bytes()).hexdigest()
    for path in sorted(directory.iterdir()):
        try:
            if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                raise ValueError("Unexpected source-origin evidence entry")
            record = json.loads(path.read_text(encoding="utf-8"))
            matched = re.fullmatch(r"([1-9][0-9]*)-([0-9a-f]{32})-(initial|final)\.json", path.name)
            if (not isinstance(record, dict) or matched is None or record.get("schema_version") != 1
                    or type(record.get("pid")) is not int or record["pid"] != int(matched[1])
                    or type(record.get("parent_pid")) is not int or record["parent_pid"] <= 0
                    or record.get("stage") != matched[3] or type(record.get("passed")) is not bool
                    or record.get("source_root") != str(copied)
                    or record.get("original_root") != str(original)
                    or record.get("source_revision") != revision
                    or record.get("startup_source_sha256") != expected_hash
                    or not isinstance(record.get("interpreter"), str)
                    or not Path(record["interpreter"]).is_absolute()
                    or Path(record["interpreter"]).resolve().is_relative_to(copied)
                    or Path(record["interpreter"]).resolve().is_relative_to(original)):
                raise ValueError("Child source authority differs from this execution")
            origins = record.get("origins")
            if record["passed"] and (not isinstance(origins, dict) or not origins):
                raise ValueError("Successful child origin observation is missing")
            if origins is not None:
                if not isinstance(origins, dict):
                    raise ValueError("Invalid child origin mapping")
                for name, paths in origins.items():
                    if (not isinstance(name, str) or not isinstance(paths, list)
                            or any(not isinstance(value, str) or not Path(value).resolve().is_relative_to(copied)
                                   for value in paths)):
                        raise ValueError("Child origin mapping escaped reviewed copied source")
            if record["stage"] == "final" and (not isinstance(record.get("escaped"), list)
                    or (record["passed"] and record["escaped"])):
                raise ValueError("Final child escape observation is inconsistent")
            record["instance"] = matched[2]
            records.append(record)
        except (OSError, ValueError, TypeError, KeyError) as error:
            errors.append({"file": path.name, "reason": str(error)})
    final_instances = {(record["pid"], record["instance"]) for record in records if record["stage"] == "final"}
    initial_only = [{"pid": record["pid"], "instance": record["instance"], "scope": "startup-only-no-finalizer-observation"}
                    for record in records if record["stage"] == "initial"
                    and (record["pid"], record["instance"]) not in final_instances]
    return {"records": records, "authority_errors": errors,
            "failed": [record for record in records if not record["passed"]],
            "startup_only": initial_only}


def run_profile(root: Path, output: Path, *, test_paths: Any = None, controls: bool = False,
                expected_revision: str | None = None, development: bool = False,
                timeout: int = 7200, strict_deferred: bool = False,
                environment: dict[str, str] | None = None) -> dict[str, Any]:
    """Run the selected profile only after trusted-byte and strict-audit gates."""
    root, output = root.resolve(), output.resolve()
    if output.is_relative_to(root) or timeout <= 0:
        raise ValueError("Profile evidence must be external and the timeout positive")
    output.mkdir(parents=True, exist_ok=True)
    before = {}
    binding = None
    report = {"passed": False, "executed": False, "release_accepted": False}
    _write(output / "source-before.json", before)
    for name in ("pytest-outcomes.json", "pytest.xml", "quarantine-import-origins-before.json",
                 "quarantine-import-origins-after.json"):
        (output / name).unlink(missing_ok=True)
    try:
        before = tracked_source_snapshot(root)
        _write(output / "source-before.json", before)
        checked = audit(root, output, expected_revision=expected_revision, development=development)
        report["source_binding"] = checked["source_binding"]
        if not checked["passed"]:
            report["error"] = "[HARD_ABORT: AUDIT FAIL] Test subprocess was not started"
            return report
        binding = verify_source_binding(root, expected_revision=expected_revision, development=development)
        evidence_path = output / "pytest-outcomes.json"
        selectors = list(test_paths or ())
        for selector in selectors:
            if not isinstance(selector, str) or not selector or selector.startswith("-"):
                raise ValueError("Test selection must contain repository-relative test paths")
            path = (root / selector.split("::", 1)[0]).resolve()
            if (not path.is_relative_to(root) or not path.exists()
                    or not any((root / name).is_relative_to(path) for name in before)):
                raise ValueError("Test selection escaped tracked reviewed source")
        report.update(source_binding=binding, selected_test_files=selectors)
        from ci_tools.zero_trust_runner import QuarantineEnvironment
        with QuarantineEnvironment(base_dir=output / "quarantine") as quarantine:
            copied = quarantine.quarantine_dir
            _copy_reviewed_source(root, copied, binding)
            copy_before = tracked_source_snapshot(copied)
            dirty_before = _git(copied, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
            if before != copy_before:
                raise InfrastructureIntegrityError("[HARD_ABORT: SOURCE QUARANTINE COPY] Copied source bytes differ")
            _write(output / "quarantine-source-before.json", copy_before)
            _write(output / "quarantine-source.json", {"source_root": str(copied), "original_root": str(root),
                "mode": binding["mode"], "revision": binding["revision"], "tracked_file_count": len(copy_before),
                "licensed_runtime_copied": False, "untracked_source_copied": False,
                "excluded_untracked_paths": binding["excluded_untracked_paths"]})
            profile = copied / ("ci_tools/pytest-ci.ini" if controls else "pytest.ini")
            command = [str(Path(sys.executable).absolute()), "-I", "-B", "-c", _PROFILE_BOOTSTRAP,
                str(copied), str(root), str(output), "-c", str(profile), "--rootdir", str(copied),
                "-p", "ci_tools.pytest_evidence", "--cochem-evidence", str(evidence_path),
                "--junitxml", str(output / "pytest.xml"), "-q"]
            if not controls:
                command.extend(["-p", "pytest_asyncio.plugin"])
            command.extend(selectors)
            profile_environment = _profile_environment(root, copied, environment)
            # One exclusive directory per execution prevents old source-origin
            # receipts from being mistaken for this profile's observations.
            descendant_evidence = output / ("descendant-origins-" + uuid.uuid4().hex)
            descendant_evidence.mkdir(mode=0o700, exist_ok=False)
            if descendant_evidence.resolve().parent != output:
                raise InfrastructureIntegrityError("[HARD_ABORT: SOURCE QUARANTINE EVIDENCE] Child evidence escaped profile output")
            profile_environment.update(COCHEM_SOURCE_QUARANTINE_ROOT=str(copied),
                COCHEM_SOURCE_QUARANTINE_ORIGINAL=str(root), COCHEM_SOURCE_QUARANTINE_EVIDENCE=str(descendant_evidence),
                COCHEM_SOURCE_QUARANTINE_REVISION=binding["revision"])
            if controls:
                profile_environment["COCHEM_CI_CONTROL_EVIDENCE_DIR"] = str(_control_evidence_directory(output))
            completed = quarantine.run_command(command, timeout=timeout, environment=profile_environment)
            if completed.cleanup_observation is not None:
                report["cleanup_observation"] = completed.cleanup_observation.to_dict()
            (output / "pytest.stdout.log").write_text(completed.stdout, encoding="utf-8")
            (output / "pytest.stderr.log").write_text(completed.stderr, encoding="utf-8")
            copy_after = tracked_source_snapshot(copied)
            dirty_after = _git(copied, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
            _write(output / "quarantine-source-after.json", copy_after)
            copied_changes = sorted(name for name in copy_before.keys() | copy_after.keys() if copy_before.get(name) != copy_after.get(name))
            if evidence_path.is_file():
                evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
                manifest = ({"schema_version": 1, "deferred_tests": []} if strict_deferred else
                    json.loads((copied / "ci_tools/deferred_acceptance.json").read_text(encoding="utf-8")))
                report.update(evaluate_test_evidence(evidence, manifest))
            else:
                report["error"] = "Pytest did not publish actual outcome evidence"
            origins_path = output / "quarantine-import-origins-after.json"
            origins = json.loads(origins_path.read_text()) if origins_path.is_file() else None
            child_observations = _source_origin_receipts(descendant_evidence, copied, root, binding["revision"])
            child_records, child_failed = child_observations["records"], child_observations["failed"]
            report.update(executed=True, command_exit_code=completed.exit_code, timed_out=completed.timed_out,
                          quarantine_source_changed=copied_changes, quarantine_workspace_changed=dirty_before != dirty_after,
                          descendant_evidence_directory=str(descendant_evidence),
                          descendant_source_records=len(child_records), descendant_source_failures=child_failed,
                          descendant_source_authority_errors=child_observations["authority_errors"],
                          descendant_startup_only=child_observations["startup_only"],
                          source_origins_verified=bool(origins is not None and not origins.get("escaped") and child_records
                              and not child_failed and not child_observations["authority_errors"]))
            report["passed"] = bool(report["passed"] and completed.passed and not copied_changes
                                    and dirty_before == dirty_after and report["source_origins_verified"])
    except (OSError, ValueError, KeyError, SyntaxError, configparser.Error) as error:
        report["passed"] = False
        report["error"] = str(error)
        raise
    finally:
        try:
            after = tracked_source_snapshot(root)
        except InfrastructureIntegrityError as error:
            after = {}
            report["source_after_error"] = str(error)
            report["passed"] = False
        if not (output / "source-before.json").is_file():
            _write(output / "source-before.json", before)
        _write(output / "source-after.json", after)
        changes = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
        report["source_changed"] = changes
        report["passed"] = bool(report["passed"] and not changes)
        report["release_accepted"] = bool(report["passed"] and binding and binding["release_accepted"])
        _write(output / "test-acceptance.json", report)
    return report


def test(root: Path, output: Path, *, controls: bool = False, expected_revision: str | None = None,
         development: bool = False, timeout: int = 7200) -> dict[str, Any]:
    return run_profile(root, output, controls=controls, expected_revision=expected_revision,
                       development=development, timeout=timeout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("audit", "test", "controls", "all"), nargs="?", default="all")
    parser.add_argument("--output", type=Path, required=True, help="External evidence directory")
    parser.add_argument("--expected-revision", help="Immutable publisher/approved canonical worker Git revision")
    parser.add_argument("--development", action="store_true", help="Explicit local development checks; never release acceptance")
    parser.add_argument("--timeout", type=int, default=7200, help="Bounded profile subprocess lifetime in seconds")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output.is_relative_to(root):
        parser.error("CI evidence must be outside the source checkout")
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    try:
        if args.stage in {"audit", "all"}:
            results["audit"] = audit(root, output, expected_revision=args.expected_revision, development=args.development)
        if args.stage in {"test", "all"}:
            if args.stage == "all" and not results["audit"]["passed"]:
                results["tests"] = {"passed": False, "executed": False,
                                    "error": "[HARD_ABORT: AUDIT FAIL] Test subprocess was not started"}
                _write(output / "test-acceptance.json", results["tests"])
            else:
                results["tests"] = test(root, output, expected_revision=args.expected_revision,
                    development=args.development, timeout=args.timeout)
        if args.stage == "controls":
            results["controls"] = test(root, output, controls=True, expected_revision=args.expected_revision,
                development=args.development, timeout=args.timeout)
    except (OSError, ValueError, KeyError, SyntaxError, configparser.Error) as error:
        results["error"] = {"passed": False, "error": str(error)}
    passed = bool(results) and all(result["passed"] for result in results.values())
    summary = {"passed": passed, "stages": {key: {"passed": value["passed"], **({"error": value["error"]} if "error" in value else {})} for key, value in results.items()},
               "evidence_directory": str(output), "mode": "development" if args.development else "release",
               "release_accepted": passed and not args.development}
    _write(output / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
