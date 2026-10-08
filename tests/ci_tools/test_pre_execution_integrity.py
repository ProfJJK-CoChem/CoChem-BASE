"""Genuine committed-Git and reviewed-ring refusal controls; no science fixtures."""
from __future__ import annotations

import hashlib
import json
import os

import pytest

from ci_tools.base_ci import (
    INFRASTRUCTURE_RING,
    InfrastructureIntegrityError,
    run_profile,
    verify_source_binding,
)
from tests.ci_tools.integrity_control_repository import commit, repository, review_ring

CONTROL_TEST = "def test_engineering_identity():\n    assert __name__.startswith('tests.')\n"


def test_clean_reviewed_commit_and_explicit_wrong_authority(tmp_path):
    root, revision = repository(tmp_path, CONTROL_TEST)
    report = verify_source_binding(root, expected_revision=revision)
    assert report["release_accepted"]
    assert report["infrastructure_ring"]["passed"]
    with pytest.raises(InfrastructureIntegrityError, match="selected publisher revision"):
        verify_source_binding(root, expected_revision="0" * len(revision))


def test_build_and_runtime_configuration_inputs_are_in_the_reviewed_ring(tmp_path):
    from ci_tools.base_ci import infrastructure_paths
    root, _ = repository(tmp_path, CONTROL_TEST)
    sources = (".devcontainer/Dockerfile", "scripts/free_engine_requirements/pyscf.txt",
               "requirements.txt", "requirements-ui.txt", "uv.lock", "MANIFEST.in",
               "src/cochem_base/orchestrator/bootstrap_service.py",
               "src/cochem_base/core_engine/hardware_observations.py",
               "src/cochem_base/calc/slurm_submission.py")
    for name in sources:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('# Engineering-only infrastructure coverage control.\n')
    review_ring(root)
    revision = commit(root)
    assert set(sources).issubset(infrastructure_paths(root))
    assert verify_source_binding(root, expected_revision=revision)["infrastructure_ring"]["passed"]
    target = root / "scripts/free_engine_requirements/pyscf.txt"
    target.write_bytes(target.read_bytes() + b"# Unreviewed dependency change.\n")
    revision = commit(root)
    with pytest.raises(InfrastructureIntegrityError, match="Reviewed infrastructure ring"):
        verify_source_binding(root, expected_revision=revision)


def test_initial_comment_tampering_refused_before_test_with_unchanged_seals(tmp_path):
    root, revision = repository(tmp_path, CONTROL_TEST)
    target = root / "ci_tools/process_runner.py"
    original = target.read_bytes()
    appended = b"\n# Controlled external engineering-integrity probe.\n"
    target.write_bytes(original + appended)
    output = tmp_path / "evidence"
    with pytest.raises(InfrastructureIntegrityError, match=r"\[HARD_ABORT: INFRASTRUCTURE TAMPERING\]"):
        run_profile(root, output, expected_revision=revision)
    report = json.loads((output / "test-acceptance.json").read_text())
    assert not report["executed"] and not report["passed"]
    assert not (output / "pytest-outcomes.json").exists()
    before = json.loads((output / "source-before.json").read_text())
    after = json.loads((output / "source-after.json").read_text())
    assert before == after
    assert before["ci_tools/process_runner.py"] == hashlib.sha256(original + appended).hexdigest()
    assert before["ci_tools/process_runner.py"] != hashlib.sha256(original).hexdigest()


def test_committed_wrong_ring_rejects_and_reader_never_refreshes(tmp_path):
    root, _ = repository(tmp_path, CONTROL_TEST)
    ring = root / INFRASTRUCTURE_RING
    record = json.loads(ring.read_text())
    record["files"]["ci_tools/process_runner.py"] = "0" * 64
    ring.write_text(json.dumps(record) + "\n")
    revision = commit(root)
    before = ring.read_bytes()
    with pytest.raises(InfrastructureIntegrityError, match="Reviewed infrastructure ring"):
        verify_source_binding(root, expected_revision=revision)
    assert ring.read_bytes() == before


def test_committed_incomplete_ring_is_not_accepted(tmp_path):
    root, _ = repository(tmp_path, CONTROL_TEST)
    ring = root / INFRASTRUCTURE_RING
    record = json.loads(ring.read_text())
    record["files"].pop("ci_tools/process_runner.py")
    ring.write_text(json.dumps(record) + "\n")
    revision = commit(root)
    with pytest.raises(InfrastructureIntegrityError, match="incomplete or changed"):
        verify_source_binding(root, expected_revision=revision)


def test_untracked_ring_cannot_issue_its_own_authority(tmp_path):
    from tests.ci_tools.integrity_control_repository import git
    root, _ = repository(tmp_path, CONTROL_TEST)
    ring = root / INFRASTRUCTURE_RING
    reviewed_bytes = ring.read_bytes()
    git(root, "rm", INFRASTRUCTURE_RING)
    revision = commit(root)
    ring.write_bytes(reviewed_bytes)
    with pytest.raises(InfrastructureIntegrityError, match="Reviewed infrastructure ring"):
        verify_source_binding(root, expected_revision=revision)


def test_development_mode_is_explicit_nonrelease(tmp_path):
    import subprocess
    import sys
    root, revision = repository(tmp_path, CONTROL_TEST)
    target = root / "ci_tools/process_runner.py"
    target.write_bytes(target.read_bytes() + b"\n# Local engineering edit.\n")
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    environment.pop("GITHUB_SHA", None)
    program = ("import json,pathlib; from ci_tools.base_ci import verify_source_binding; "
               "print(json.dumps(verify_source_binding(pathlib.Path.cwd(), "
               "expected_revision=" + repr(revision) + ", development=True)))")
    completed = subprocess.run([sys.executable, "-B", "-c", program], cwd=root,
                               env=environment, capture_output=True, text=True, check=True, timeout=30)
    report = json.loads(completed.stdout)
    assert report["mode"] == "development" and not report["release_accepted"]
    assert report["initial_changed_paths"] == ["ci_tools/process_runner.py"]
    assert not report["infrastructure_ring"]["passed"]


def test_student_data_is_excluded_but_untracked_importable_source_is_refused(tmp_path):
    root, revision = repository(tmp_path, CONTROL_TEST)
    geometry = root / "student-starting.xyz"
    geometry.write_text("Engineering-only data exclusion control.\n")
    report = verify_source_binding(root, expected_revision=revision)
    assert report["excluded_untracked_paths"] == ["student-starting.xyz"]
    assert report["release_accepted"]
    injection = root / "ci_tools/unreviewed_source.py"
    injection.write_text('"""Unreviewed import injection control."""\n')
    with pytest.raises(InfrastructureIntegrityError, match="Untracked executable or source configuration"):
        verify_source_binding(root, expected_revision=revision)
    assert geometry.read_text() == "Engineering-only data exclusion control.\n"


def test_gitignored_importable_source_is_still_refused(tmp_path):
    root, revision = repository(tmp_path, CONTROL_TEST)
    (root / ".git/info/exclude").write_text("ci_tools/ignored-control.py\n")
    (root / "ci_tools/ignored-control.py").write_text('"""Ignored injection control."""\n')
    with pytest.raises(InfrastructureIntegrityError, match="Untracked executable or source configuration"):
        verify_source_binding(root, expected_revision=revision)


def test_root_test_configuration_must_be_tracked_reviewed_source(tmp_path):
    from tests.ci_tools.integrity_control_repository import git
    root, _ = repository(tmp_path, CONTROL_TEST)
    profile = root / "pytest.ini"
    content = profile.read_bytes()
    git(root, "rm", "pytest.ini")
    review_ring(root)
    revision = commit(root)
    profile.write_bytes(content)
    with pytest.raises(InfrastructureIntegrityError, match="Untracked executable or source configuration"):
        verify_source_binding(root, expected_revision=revision)


def test_registered_fixture_cannot_use_untracked_data(tmp_path):
    root, _ = repository(tmp_path, CONTROL_TEST)
    manifest = root / "ci_tools/source_fixtures.json"
    manifest.write_text(json.dumps({"schema_version": 1, "fixtures": [
        {"path": "tests/unreviewed-input.xyz"}]}) + "\n")
    review_ring(root)
    revision = commit(root)
    (root / "tests/unreviewed-input.xyz").write_text("Engineering-only registered-input control.\n")
    with pytest.raises(InfrastructureIntegrityError, match="Source fixtures require tracked reviewed bytes"):
        verify_source_binding(root, expected_revision=revision)


def test_git_inspection_disables_fsmonitor_and_refuses_external_conversion(tmp_path):
    import shlex
    import sys
    from pathlib import Path

    from tests.ci_tools.integrity_control_repository import git
    root, revision = repository(tmp_path, CONTROL_TEST)
    sentinel = tmp_path / "untrusted-git-program-ran"
    program = tmp_path / "untrusted-git-program.py"
    program.write_text("from pathlib import Path\nimport sys\nPath(" + repr(str(sentinel))
                       + ").write_text('invoked')\nsys.stdout.buffer.write(b'control-token\\0/\\0')\n",
                       encoding="utf-8")
    # Git executes hook commands with its native shell, including Git Bash on
    # Windows. This real external interpreter control must demonstrably run
    # before its absence can prove the canonical inspector disabled it.
    command = " ".join(shlex.quote(path.as_posix())
                       for path in (Path(sys.executable).absolute(), program))
    git(root, "config", "core.fsmonitor", command)
    git(root, "status", "--porcelain=v1", "--untracked-files=no")
    assert sentinel.read_text() == "invoked"
    sentinel.unlink()
    report = verify_source_binding(root, expected_revision=revision)
    assert report["passed"] and not sentinel.exists()
    git(root, "config", "filter.control.clean", command)
    with pytest.raises(InfrastructureIntegrityError, match="External Git conversion programs"):
        verify_source_binding(root, expected_revision=revision)
    assert not sentinel.exists()


def test_git_replace_cannot_rebind_the_expected_publisher_commit(tmp_path):
    from tests.ci_tools.integrity_control_repository import git
    root, revision = repository(tmp_path, CONTROL_TEST)
    target = root / "ci_tools/process_runner.py"
    original = target.read_bytes()
    target.write_bytes(original + b"\n# Replacement-tree engineering control.\n")
    review_ring(root)
    replacement = commit(root)
    git(root, "replace", revision, replacement)
    git(root, "checkout", "--detach", revision)
    assert target.read_bytes() != original
    assert git(root, "rev-parse", "HEAD") == revision
    with pytest.raises(InfrastructureIntegrityError, match=r"\[HARD_ABORT: INFRASTRUCTURE TAMPERING\]"):
        verify_source_binding(root, expected_revision=revision)


def test_publisher_environment_cannot_be_downgraded_to_development(tmp_path):
    import subprocess
    import sys
    root, revision = repository(tmp_path, CONTROL_TEST)
    environment = dict(os.environ, GITHUB_SHA=revision, PYTHONDONTWRITEBYTECODE="1")
    command = [sys.executable, "-B", "-m", "ci_tools.base_ci", "audit", "--development",
               "--output", str(tmp_path / "publisher-refusal")]
    completed = subprocess.run(command, cwd=root, env=environment, capture_output=True,
                               text=True, check=False, timeout=30)
    assert completed.returncode == 1
    assert "Development mode cannot qualify a hosted publisher run" in completed.stdout
