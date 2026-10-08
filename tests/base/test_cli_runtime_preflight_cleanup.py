"""Real CLI authority and preservation controls; no simulated chemistry output."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _environment(**values):
    return dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=os.pathsep.join(str(path) for path in (ROOT / "src", ROOT, ROOT / "Libraries")), **values)


def _cli(arguments, environment=None):
    result = subprocess.run([sys.executable, "-B", str(ROOT / "cli.py"), *arguments],
        cwd=ROOT, env=environment or _environment(), capture_output=True, text=True, timeout=240)
    return result, json.loads(result.stdout)


def _protected_files(root):
    files = [root / "Scratch/cochem_exec_another_student/original.xyz",
        root / "Scratch/cochem_mps_native/pipe-record.txt", root / "Scratch/cochem_tmp_retained.txt",
        root / "Silos/accepted-runtime/pyvenv.cfg", root / "BaseRuntime/rollback/source/input.xyz",
        root / "Modules/retained-generation/installation.json", root / "Results/report.csv"]
    geometry = (ROOT / "tests/data/orca_6_1_1_water_hf_sto3g/water.xyz").read_bytes()
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(geometry if path.suffix == ".xyz" else b"Existing user-owned runtime or result bytes\n")
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}


@pytest.mark.parametrize("arguments,expected_status", [
    (["clean"], "CLEAN_COMPLETE"), (["clean", "--all"], "CLEAN_REFUSED"),
    (["setup", "--clean"], "FAILED"), (["setup", "--clean", "--dry-run"], "FAILED"),
])
def test_cleanup_and_reset_preserve_other_users_runtime_inputs_and_results(tmp_path, arguments, expected_status):
    artifact = tmp_path / "artifacts"
    before = _protected_files(artifact)
    other = tmp_path / "cochem_exec_unrelated_project"
    other.mkdir()
    unrelated = other / "retained.txt"
    unrelated.write_bytes(b"This prefix confers no deletion authority\n")
    before[str(unrelated)] = hashlib.sha256(unrelated.read_bytes()).hexdigest()
    environment = _environment(COCHEM_ARTIFACT_DIR=str(artifact), COCHEM_SCRATCH_DIR=str(artifact / "Scratch"),
                               TMPDIR=str(tmp_path), TEMP=str(tmp_path), TMP=str(tmp_path))
    result, payload = _cli([*arguments, "--artifact-dir", str(artifact), "--json"], environment)
    assert payload.get("status", payload.get("overall_status")) == expected_status
    assert result.returncode == (0 if expected_status == "CLEAN_COMPLETE" else 1), result.stderr
    assert {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in before} == before
    if arguments[0] == "clean":
        assert payload["sandboxes_purged"] == 0 and payload["silos_purged"] is False
        assert payload["filesystem_preserved"] is True
    else:
        assert "reset is unsupported" in payload["error"]
        # Shared registry imports may scaffold its empty directory. They must
        # never run setup phases or issue fresh execution authority on refusal.
        registry = artifact / "Registry"
        assert not registry.exists() or list(registry.iterdir()) == []
        assert "phases_executed" not in payload


def test_clean_refuses_live_registered_work_without_killing_unrelated_child(tmp_path):
    script = r'''
import contextlib, io, json, subprocess, sys
from cochem_base.cli import entrypoint
from cochem_base.core_engine.cochem_core_subprocess_broker import register_popen_process, unregister_popen_process
owned = subprocess.Popen([sys.executable, '-B', '-c', 'import time; time.sleep(120)'])
unrelated = subprocess.Popen([sys.executable, '-B', '-c', 'import time; time.sleep(120)'])
register_popen_process(owned)
try:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = entrypoint()
    observation = json.loads(output.getvalue())
    observation.update(exit_code=code, owned_survived=owned.poll() is None, unrelated_survived=unrelated.poll() is None)
    print(json.dumps(observation))
finally:
    unregister_popen_process(owned)
    for process in (owned, unrelated):
        process.terminate()
        process.wait(timeout=10)
'''
    completed = subprocess.run([sys.executable, "-B", "-c", script, "clean", "--json"], cwd=ROOT,
        env=_environment(), capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    observation = json.loads(completed.stdout)
    assert observation["exit_code"] == 1 and observation["status"] == "CLEAN_BLOCKED_ACTIVE_WORK"
    assert observation["active_owned_process_count"] == 1
    assert observation["owned_survived"] and observation["unrelated_survived"]


def test_preflight_never_treats_empty_module_directories_as_installations(tmp_path):
    artifact = tmp_path / "artifacts"
    for name in ("CoChem-BASE", "CoChem-TOPOS", "CoChem-TORQ", "topos", "torq"):
        (artifact / "Modules" / name).mkdir(parents=True)
    result, payload = _cli(["preflight", "--artifact-dir", str(artifact), "--json"])
    assert result.returncode == 1 and payload["all_passed"] is False
    assert payload["results"]["registry"]["status"] == "invalid"
    for name in ("topos", "torq"):
        item = payload["results"]["module:" + name]
        assert item["required"] and not item["passed"] and item["status"] == "not_installed"
        assert item["scientific_execution_verified"] is False
    assert not (artifact / "Registry").exists()


def test_preflight_rejects_uninitialized_measured_registry(tmp_path):
    from cochem_base.cochem_core_registry_schema import CoChemSystemConfig
    from cochem_base.core.cochem_core_registry_manager import save_system_config

    artifact = tmp_path / "artifacts"
    path = artifact / "Registry/cochem_system_config.json"
    config = CoChemSystemConfig.create_default(auto_detect_hardware=True)
    save_system_config(config, path)
    before = path.read_bytes()
    result, payload = _cli(["preflight", "--artifact-dir", str(artifact), "--json"])
    assert result.returncode == 1 and payload["base_ready"] is False
    assert "complete eleven-phase" in payload["results"]["registry"]["reason"]
    assert path.read_bytes() == before


def test_preflight_rejects_redirected_registry_without_touching_user_file(tmp_path):
    target = tmp_path / "students-record.json"
    target.write_text('{"student_record":"retained"}\n', encoding="utf-8")
    artifact = tmp_path / "artifacts"
    (artifact / "Registry").mkdir(parents=True)
    (artifact / "Registry/cochem_system_config.json").symlink_to(target)
    before = target.read_bytes()
    result, payload = _cli(["preflight", "--artifact-dir", str(artifact), "--json"])
    assert result.returncode == 1 and "regular Golden Registry" in payload["results"]["registry"]["reason"]
    assert target.read_bytes() == before


def test_preflight_refuses_redirected_actual_assignment_runtime_authority(tmp_path):
    from cochem_base.interfaces.student_setup import StudentSetupError, StudentSetupService, validate_runtime_record

    artifact = tmp_path / "artifacts"
    service = StudentSetupService(artifact, ROOT)
    assignment = json.loads((service.state_dir / "assignment-runtime.json").read_text())
    validate_runtime_record(assignment, artifact, ROOT)
    exact = dict(assignment, authority_path=str(artifact))
    validate_runtime_record(exact, artifact, ROOT)
    outside = tmp_path / "another-student-authority"
    outside.mkdir()
    preserved = outside / "retained-input.xyz"
    preserved.write_bytes((ROOT / "tests/data/orca_6_1_1_water_hf_sto3g/water.xyz").read_bytes())
    before = preserved.read_bytes()
    assignment["authority_path"] = str(outside)
    (service.state_dir / "active-runtime.json").write_text(json.dumps(assignment), encoding="utf-8")
    with pytest.raises(StudentSetupError, match="Assignment execution authority"):
        validate_runtime_record(assignment, artifact, ROOT)
    with pytest.raises(StudentSetupError, match="Assignment execution authority"):
        service._active_runtime()
    result, payload = _cli(["preflight", "--artifact-dir", str(artifact), "--json"])
    assert result.returncode == 1 and not payload["base_ready"]
    assert "Assignment execution authority" in payload["results"]["registry"]["reason"]
    assert list(outside.iterdir()) == [preserved] and preserved.read_bytes() == before


def test_real_stage0_preflight_keeps_missing_licensed_engines_optional(tmp_path):
    """Run genuine eleven-phase CPU setup; this is no module/chemistry acceptance."""
    artifact = tmp_path / "actual-setup"
    result_path = tmp_path / "actual-setup-summary.json"
    script = '''
import json,sys
from pathlib import Path
from cochem_base.orchestrator.bootstrap_service import run_setup
summary = run_setup(sys.argv[1], min_disk_space_gb=0.25, skip_heavy=True)
Path(sys.argv[2]).write_text(json.dumps(summary), encoding='utf-8')
'''
    environment = {key: value for key, value in _environment().items()
        if not any(word in key.upper() for word in ("ORCA", "CFOUR", "TOKEN", "SECRET", "CREDENTIAL"))}
    environment.update(COCHEM_ARTIFACT_DIR=str(artifact), COCHEM_CONFIG=str(artifact / "Registry/cochem_system_config.json"),
        PATH=os.pathsep.join([str(Path(sys.executable).parent), "/usr/bin", "/bin"]),
        PYTHONDONTWRITEBYTECODE="1")
    completed = subprocess.run([sys.executable, "-B", "-c", script, str(artifact), str(result_path)],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=300)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    summary = json.loads(result_path.read_text())
    assert summary["overall_status"] in {"PASSED", "DEGRADED_OPERATIONAL"}, summary
    assert len(summary["phases_executed"]) == 11
    result, payload = _cli(["preflight", "--artifact-dir", str(artifact), "--json"], environment)
    assert payload["results"]["registry"]["passed"] and payload["base_ready"], payload
    for name in ("orca", "cfour"):
        item = payload["results"]["engine:" + name]
        assert item["optional"] and not item["required"] and item["status"] == "unavailable", item
    # Private providers are deliberately not installed by this CPU setup control.
    assert result.returncode == 1 and payload["all_passed"] is False
    assert all(not payload["results"]["module:" + name]["passed"] for name in ("topos", "torq"))
    assert payload["scientific_execution_performed"] is False
    explicitly_requested, required = _cli(["preflight", "--artifact-dir", str(artifact),
        "--orca-cmd", sys.executable, "--json"], environment)
    assert explicitly_requested.returncode == 1 and required["base_ready"]
    assert required["results"]["engine:orca"]["required"] and not required["results"]["engine:orca"]["passed"]
    # A genuinely produced authority becomes inadmissible when its seal changes.
    registry = artifact / "Registry/cochem_system_config.json"
    original = registry.read_bytes()
    altered = json.loads(original)
    original_checksum = altered["registry_checksum"]
    altered["registry_checksum"] = ("0" if original_checksum[0] != "0" else "1") + original_checksum[1:]
    altered_artifact = tmp_path / "altered-authority-copy"
    changed_registry = altered_artifact / "Registry/cochem_system_config.json"
    changed_registry.parent.mkdir(parents=True)
    changed_registry.write_text(json.dumps(altered), encoding="utf-8")
    rejected, invalid = _cli(["preflight", "--artifact-dir", str(altered_artifact), "--json"],
        dict(environment, COCHEM_ARTIFACT_DIR=str(altered_artifact), COCHEM_CONFIG=str(changed_registry)))
    assert rejected.returncode == 1 and not invalid["base_ready"]
    assert not invalid["results"]["registry"]["passed"]
    assert "checksummed" in invalid["results"]["registry"]["reason"]
    assert registry.read_bytes() == original
