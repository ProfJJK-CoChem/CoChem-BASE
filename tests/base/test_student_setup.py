"""No-command setup and retained versions with real offline Git/PEP 517 builds.

The tiny wheels test packaging, not computational chemistry. Offline Git uses
its normal URL rewrite configuration, without replacing any executor or probe.
"""
from pathlib import Path
import json
import os
import subprocess
import sys
from threading import Event

import pytest

from scripts import manage_modules as installer
from scripts.hosted_dashboard import setup_build_environment, _validate_runtime_metadata
from cochem_base.interfaces.student_setup import StudentSetupService, StudentSetupError, resolve_worker_source, RUNTIME_SCHEMA
import test_module_installer as offline_installer


@pytest.fixture
def repository(tmp_path):
    return offline_installer.repository.__wrapped__(tmp_path)


@pytest.fixture
def student_service(tmp_path, repository):
    origin, spec, _root = repository
    assignment = tmp_path / "assignment"
    (assignment / "scripts").mkdir(parents=True)
    (assignment / "Start_Here.ipynb").write_text('{}\n')
    catalog = {name: dict(spec) for name in ("topos", "torq")}
    (assignment / "scripts/module-distribution.json").write_text(json.dumps({"schema_version": installer.MANIFEST_SCHEMA, "modules": catalog}))
    return StudentSetupService(tmp_path / "artifacts", assignment), catalog, origin


def service_command(service, origin, method, arguments=None):
    code = """import json,sys
from cochem_base.interfaces.student_setup import StudentSetupService
s=StudentSetupService(sys.argv[1],sys.argv[2])
args=json.loads(sys.argv[4])
result=getattr(s,sys.argv[3])(*args)
print(json.dumps(result))
"""
    result = subprocess.run([sys.executable, "-B", "-c", code, str(service.artifact_dir), str(service.repository_root), method, json.dumps(arguments or [])],
        env=offline_installer.offline_environment(origin), cwd=installer.REPOSITORY_ROOT,
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def installation_command(origin, spec, root, *, activate):
    code = """import json,sys
from pathlib import Path
from scripts.manage_modules import install_module
print(json.dumps(install_module('fixture',json.loads(sys.argv[1]),Path(sys.argv[2]),activate=json.loads(sys.argv[3]))))
"""
    result = subprocess.run([sys.executable, "-B", "-c", code, json.dumps(spec), str(root), json.dumps(activate)],
        env=offline_installer.offline_environment(origin), cwd=installer.REPOSITORY_ROOT,
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_automatic_defaults_really_install_isolated_wheels_preserving_student_xyz(student_service):
    service, catalog, origin = student_service
    geometry = service.repository_root / "student-complex.xyz"
    geometry.write_text("2\nOriginal student geometry\nHe 0 0 0\nHe 0 0 4\n")
    results = service.repository_root / "results"
    results.mkdir()
    report = results / "research.json"
    report.write_text('{"notes":"retain this student record"}\n')
    before = {path: path.read_bytes() for path in (geometry, report)}
    result = service_command(service, origin, "install_default_modules")
    assert result["ready"] is True
    assert service.status()["ready"] is True
    for name in ("topos", "torq"):
        receipt = installer.verify_installation(name, catalog[name], service.artifact_dir / "Modules")
        assert Path(receipt["python_path"]).is_relative_to(service.artifact_dir)
        assert Path(receipt["built_wheel_path"]).is_file()
        assert installer.verify_installation(name, catalog[name], service.artifact_dir / "Modules", active=False) == receipt
    assert all(path.read_bytes() == value for path, value in before.items())


def test_real_source_only_provider_failure_keeps_base_and_other_module_available(student_service):
    service, catalog, origin = student_service
    catalog["topos"].update(distribution=None, adapter=None, operations=[])
    service.manifest_path.write_text(json.dumps({"schema_version": installer.MANIFEST_SCHEMA, "modules": catalog}))
    result = service_command(service, origin, "install_default_modules")
    assert result["ready"] is False
    status = service.status()
    assert status["base"]["status"] == "ready"
    assert status["modules"]["torq"]["status"] == "installed"
    assert status["modules"]["topos"]["status"] == "failed"
    assert status["modules"]["topos"]["operations"] == []
    assert "Retry setup" in status["modules"]["topos"]["message"]
    assert (service.artifact_dir / "Modules/topos/source.json").is_file()
    assert not (service.artifact_dir / "Modules/topos/installation.json").exists()


def test_busy_execution_rejects_install_before_source_or_runtime_changes(student_service):
    service, _catalog, _origin = student_service
    registry = service.artifact_dir / "Registry/cochem_system_config.json"
    registry.parent.mkdir()
    registry.write_text('{"active_jobs":{"student-calculation":{"status":"running"}}}')
    with pytest.raises(StudentSetupError, match="active jobs"):
        service.install_default_modules()
    assert not (service.artifact_dir / "Modules/topos").exists()


def test_gui_busy_signal_prevents_runtime_changes(student_service):
    service, _catalog, _origin = student_service
    idle_signal = Event()
    service.idle_check = idle_signal.is_set
    with pytest.raises(StudentSetupError, match="calculation or import"):
        service.install_default_modules()
    assert not (service.artifact_dir / "Modules/topos").exists()


def test_retry_preserves_real_interrupted_checkout_files(student_service):
    service, catalog, origin = student_service
    location = service.artifact_dir / "Modules/topos" / catalog["topos"]["revision"]
    location.mkdir(parents=True)
    note = location / "interrupted-job-notes.txt"
    note.write_bytes(b"This diagnostic must survive retry\n")
    result = service_command(service, origin, "install_modules", [["topos"]])
    assert result["ready"] is True
    preserved = list(location.parent.glob("failed-*/interrupted-job-notes.txt"))
    assert len(preserved) == 1
    assert preserved[0].read_bytes() == b"This diagnostic must survive retry\n"


def test_build_environment_strips_source_binary_and_user_credentials():
    original = {"COCHEM_SOURCE_READ_TOKEN": "source-secret", "PRIVATE_CFOUR_ASSET_CREDENTIAL": "cfour-secret",
        "PRIVATE_ORCA_ASSET_CREDENTIAL": "orca-secret", "GITHUB_TOKEN": "user-identity-secret",
        "GIT_CONFIG_COUNT": "1", "PYTHONPATH": "/injected/python", "COCHEM_ARTIFACT_DIR": "/student/artifacts",
        "HTTPS_PROXY": "http://approved-session-proxy:3128"}
    sanitized = setup_build_environment(original)
    assert not any("TOKEN" in key or key == "PYTHONPATH" for key in sanitized)
    assert sanitized["COCHEM_ARTIFACT_DIR"] == original["COCHEM_ARTIFACT_DIR"]
    assert sanitized["HTTPS_PROXY"] == original["HTTPS_PROXY"]
    assert sanitized["GIT_CONFIG_GLOBAL"] == os.devnull
    assert original["GITHUB_TOKEN"] == "user-identity-secret"


def test_template_selects_stable_release_without_student_commands(student_service):
    service, _catalog, _origin = student_service
    config = service.repository_root / ".cochem/course-runtime.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"schema_version": "cochem.course-channel/1", "channel": "stable-release"}))
    assert service._update_channel() == "stable-release"
    assert service._course_channel() is None


def test_instructor_channel_refuses_foreign_repository_or_executable_path(student_service):
    service, _catalog, _origin = student_service
    config = service.repository_root / ".cochem/course-runtime.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"schema_version": "cochem.course-channel/1", "repository": "unknown/code", "path": "scripts/malicious.py"}))
    with pytest.raises(StudentSetupError, match="canonical BASE"):
        resolve_worker_source(service.repository_root, service.artifact_dir)


def test_real_revision_preparation_activation_and_rollback_preserve_both_installs(repository):
    origin, old, root = repository
    before = installation_command(origin, old, root, activate=True)
    (origin / "release-note.txt").write_text("Reviewed packaging revision 2\n")
    offline_installer.git(origin, "add", ".")
    offline_installer.git(origin, "-c", "user.name=CoChem test", "-c", "user.email=test@example.invalid", "commit", "-m", "Second reviewed revision")
    new = dict(old, revision=offline_installer.git(origin, "rev-parse", "HEAD"))
    prepared = installation_command(origin, new, root, activate=False)
    assert installer.verify_installation("fixture", old, root) == before
    assert installer.verify_installation("fixture", new, root, active=False) == prepared
    installer.activate_installation("fixture", new, root)
    assert installer.verify_installation("fixture", new, root) == prepared
    installer.activate_installation("fixture", old, root)
    assert installer.verify_installation("fixture", old, root) == before
    assert Path(prepared["source_path"]).is_dir()
    assert Path(before["source_path"]).is_dir()


def test_runtime_selection_rejects_python_outside_immutable_revision(tmp_path):
    record = {"schema_version": RUNTIME_SCHEMA, "kind": "reviewed-release", "revision": "a" * 40,
        "source_path": str(tmp_path / "BaseRuntime/base" / ("a" * 40) / "source"), "python_path": sys.executable,
        "base_spec": {"repository": "ProfJJK-CoChem/CoChem-BASE", "revision": "a" * 40}}
    with pytest.raises(RuntimeError, match="managed revision"):
        _validate_runtime_metadata(record, tmp_path)


def test_setup_state_cannot_pollute_student_repository(tmp_path):
    with pytest.raises(StudentSetupError, match="outside the assignment"):
        StudentSetupService(tmp_path / "repo/runtime", tmp_path / "repo")


def test_retry_preserves_partial_environment_and_builds_a_verified_replacement(student_service):
    service, catalog, origin = student_service
    root = service.artifact_dir / "Modules"
    fetched = offline_installer.fixture_command("fetch", "topos", catalog["topos"], root, origin)
    assert fetched.returncode == 0, fetched.stderr
    location = root / "topos" / catalog["topos"]["revision"]
    environment = location / "env"
    environment.mkdir()
    note = environment / "partial-installation.log"
    note.write_bytes(b"Interrupted package download diagnostic\n")
    result = service_command(service, origin, "install_modules", [["topos"]])
    assert result["ready"] is True
    preserved = list(location.glob("env.failed-*/partial-installation.log"))
    assert len(preserved) == 1
    assert preserved[0].read_bytes() == b"Interrupted package download diagnostic\n"
    installer.verify_installation("topos", catalog["topos"], root)


def test_selected_revision_authority_does_not_change_original_registry(tmp_path):
    from scripts.hosted_dashboard import runtime_environment
    artifacts = tmp_path / "artifacts"
    original = artifacts / "Registry/cochem_system_config.json"
    original.parent.mkdir(parents=True)
    original.write_bytes(b'{"student":"previous valid execution authority"}\n')
    revision = "a" * 40
    location = artifacts / "BaseRuntime/base" / revision
    candidate_registry = location / "authority/Registry/cochem_system_config.json"
    candidate_registry.parent.mkdir(parents=True)
    candidate_registry.write_bytes(b'{"candidate":"separate revision authority"}\n')
    state = artifacts / "StudentSetup/active-runtime.json"
    state.parent.mkdir()
    state.write_text(json.dumps({"schema_version": RUNTIME_SCHEMA, "kind": "reviewed-release", "revision": revision,
        "source_path": str(location / "source"), "python_path": str(installer._python_path(location / "env")),
        "authority_path": str(location / "authority"), "base_spec": {"repository": "ProfJJK-CoChem/CoChem-BASE", "revision": revision}}))
    env = runtime_environment(artifacts)
    assert env["COCHEM_CONFIG"] == str(candidate_registry)
    assert Path(env["COCHEM_CORE_SILO"]).is_relative_to(location / "authority")
    assert original.read_bytes() == b'{"student":"previous valid execution authority"}\n'
    state.unlink()
    restored = runtime_environment(artifacts)
    assert restored["COCHEM_CONFIG"] == str(original)
    assert original.read_bytes() == b'{"student":"previous valid execution authority"}\n'
    assert candidate_registry.read_bytes() == b'{"candidate":"separate revision authority"}\n'


def test_codespace_discovers_actual_student_assignment_repository(student_service):
    from scripts.hosted_dashboard import assignment_identity, runtime_environment
    service, _catalog, _origin = student_service
    source = service.repository_root
    offline_installer.git(source, "init")
    offline_installer.git(source, "add", ".")
    offline_installer.git(source, "-c", "user.name=Student fixture", "-c", "user.email=student@example.invalid", "commit", "-m", "Student assignment starter")
    offline_installer.git(source, "branch", "-M", "main")
    offline_installer.git(source, "remote", "add", "origin", "https://github.com/ProfJJK-CoChem/student-research-assignment.git")
    assert assignment_identity(source) == {"GITHUB_REPOSITORY": "ProfJJK-CoChem/student-research-assignment", "GITHUB_REF_NAME": "main"}
    environment = runtime_environment(service.artifact_dir)
    assert environment["COCHEM_ASSIGNMENT_ROOT"] == str(source)
    assert environment["GITHUB_REPOSITORY"] == "ProfJJK-CoChem/student-research-assignment"
    assert environment["GITHUB_REF_NAME"] == "main"


def test_update_receipt_identity_cannot_overwrite_student_files(student_service):
    service, _catalog, _origin = student_service
    geometry = service.repository_root / "important-student-input.xyz"
    geometry.write_bytes(b"1\nOriginal Avogadro input\nHe 0 0 0\n")
    (service.state_dir / "update-plan.json").write_text(json.dumps({"schema_version": "cochem.student-update-plan/1",
        "status": "updates_available", "plan_id": "../../important-student-input"}))
    with pytest.raises(StudentSetupError, match="receipt identity"):
        service.apply_updates()
    assert geometry.read_bytes() == b"1\nOriginal Avogadro input\nHe 0 0 0\n"


def test_private_science_wheel_uses_actual_reviewed_candidate_source_before_release(student_service):
    service, _catalog, origin = student_service
    (origin / "pyproject.toml").write_text('[build-system]\nrequires=[]\nbuild-backend="backend"\nbackend-path=["."]\n'
        '[project]\nname="CoChem-BASE"\nversion="1.1.0"\n')
    backend = offline_installer.BACKEND.replace("cochem_installer_fixture", "cochem_base").replace("cochem-installer-fixture", "CoChem-BASE").replace("1.2.3", "1.1.0")
    (origin / "backend.py").write_text(backend)
    offline_installer.git(origin, "add", ".")
    offline_installer.git(origin, "-c", "user.name=CoChem packaging test", "-c", "user.email=packaging@example.invalid", "commit", "-m", "Actual private science-wheel packaging boundary")
    revision = offline_installer.git(origin, "rev-parse", "HEAD")
    (origin.parent / "offline-git.conf").write_text(f'[url "{origin.as_uri()}"]\n\tinsteadOf = https://github.com/ProfJJK-CoChem/CoChem-BASE.git\n')
    code = """import json,sys
from pathlib import Path
from cochem_base.interfaces.student_setup import StudentSetupService
from scripts.manage_modules import _wheel_identity
s=StudentSetupService(sys.argv[1],sys.argv[2])
wheel=s._private_base_wheel('1.1.0',sys.argv[3])
assert s._private_base_wheel('1.1.0',sys.argv[3])==wheel
print(json.dumps({'wheel':str(wheel),'identity':_wheel_identity(wheel)}))
"""
    result = subprocess.run([sys.executable, "-B", "-c", code, str(service.artifact_dir), str(service.repository_root), revision],
        env=offline_installer.offline_environment(origin), cwd=installer.REPOSITORY_ROOT,
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["identity"] == ["CoChem-BASE", "1.1.0"]
    wheel = Path(report["wheel"])
    assert wheel.is_relative_to(service.artifact_dir / "DependencyRuntime/base" / revision)
    receipt = json.loads((wheel.parent.parent / "wheel.json").read_text())
    assert receipt["revision"] == revision
    assert receipt["version"] == "1.1.0"
    with pytest.raises(StudentSetupError, match="declared distribution or version"):
        service._private_base_wheel("1.0.1", revision)


@pytest.mark.parametrize("revision", ["main", "v1.1.0", "a" * 39, "A" * 40])
def test_private_science_source_pin_rejects_moving_or_invalid_identity(student_service, revision):
    service, _catalog, _origin = student_service
    with pytest.raises(StudentSetupError, match="exact Git revision"):
        service._private_base_wheel("1.1.0", revision)
    assert not (service.artifact_dir / "DependencyRuntime").exists()
