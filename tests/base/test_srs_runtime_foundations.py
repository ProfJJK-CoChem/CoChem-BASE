"""Physical Stage 0 and worker lifecycle checks for Chunk 17 + proposal additions."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

import numpy as np
import psutil
import pytest
from pydantic import ValidationError

from cochem.concurrency.subprocess_broker import SubprocessBroker
from cochem_base.core_engine.hardware_profiler import profile_hardware
from cochem_base.orchestrator.cochem_setup_phase_X import SiloConfig, SiloType, provision_micro_silo
from cochem_base.orchestrator.micro_silo_manager import (
    MicroSiloValidationError, provision_isolated_silo, validate_pins, verify_micro_silo,
)


def test_live_hardware_ingress_is_bounded_and_measured():
    profile = profile_hardware()
    assert 0 < profile.elapsed_seconds <= 1.5
    assert profile.physical_cores == psutil.cpu_count(logical=False)
    assert profile.logical_cores == psutil.cpu_count(logical=True)
    assert profile.ram_bytes == psutil.virtual_memory().total
    assert 0 < profile.allocatable_ram_bytes <= profile.ram_bytes
    assert 0 <= profile.available_ram_bytes <= profile.allocatable_ram_bytes
    assert profile.available_cpu_ids
    assert profile.gpu_probe_status in {"unavailable", "measured", "probe_failed"}


def test_golden_registry_requires_observed_topology():
    from cochem_base.orchestrator.cochem_system_config import CoChemSystemConfig, HardwareProfile
    with pytest.raises(ValidationError, match="audited hardware"):
        CoChemSystemConfig.model_validate({})
    with pytest.raises(ValidationError, match="physical CPU"):
        HardwareProfile(ram_gb=8)
    with pytest.raises(ValidationError, match="logical CPU"):
        HardwareProfile(ram_gb=8, physical_cpu_cores=2)


@pytest.fixture(scope="module")
def physical_silo(tmp_path_factory):
    root = tmp_path_factory.mktemp("isolated-silo") / "runtime"
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    result = provision_isolated_silo(root, python_version=version, imports=["json"])
    assert result["imports"] == ["json"]
    return root, version


def test_micro_silo_verifies_interpreter_and_pip(physical_silo):
    root, version = physical_silo
    result = verify_micro_silo(root, python_version=version, imports=["json"])
    assert result["python_version"].startswith(version + ".")
    with pytest.raises(MicroSiloValidationError, match="version drift"):
        verify_micro_silo(root, python_version="2.7")
    with pytest.raises(MicroSiloValidationError, match="validation failed"):
        verify_micro_silo(root, python_version=version, requirements=["not-installed-cochem-contract==1.0"])
    with pytest.raises(MicroSiloValidationError, match="version drift"):
        verify_micro_silo(root, python_version=version, requirements=["pip==0.0.0"])


def test_micro_silo_rejects_global_site_leakage(physical_silo):
    root, version = physical_silo
    config = root / "pyvenv.cfg"
    original = config.read_text()
    try:
        config.write_text(original.replace("include-system-site-packages = false", "include-system-site-packages = true"))
        with pytest.raises(MicroSiloValidationError, match="global site packages"):
            verify_micro_silo(root, python_version=version)
    finally:
        config.write_text(original)


def test_micro_silo_rejects_pth_directory_leak(physical_silo, tmp_path):
    root, version = physical_silo
    site_packages = next(root.rglob("site-packages"))
    injected = site_packages / "external-directory.pth"
    injected.write_text(str(tmp_path) + "\n")
    try:
        with pytest.raises(MicroSiloValidationError, match="external directory"):
            verify_micro_silo(root, python_version=version)
    finally:
        injected.unlink()


def test_micro_silo_rejects_unpinned_packages_and_false_dry_run_readiness(tmp_path):
    with pytest.raises(MicroSiloValidationError, match="exactly pinned"):
        validate_pins(["numpy>=2"])
    report = provision_micro_silo(SiloConfig(name="plan", silo_type=SiloType.CORE, target_path=str(tmp_path / "plan")), dry_run=True)
    assert not report.is_available
    assert not (tmp_path / "plan").exists()


def test_micro_silo_rejects_repository_outputs():
    from cochem.core.context import AirGapViolationError
    repo = Path(__file__).resolve().parents[2]
    with pytest.raises(AirGapViolationError):
        provision_isolated_silo(repo / "forbidden-silo", python_version="3.12")
    assert not (repo / "forbidden-silo").exists()


def test_async_broker_preserves_event_loop_progress(tmp_path):
    async def exercise():
        broker = SubprocessBroker(base_scratch_dir=tmp_path, max_retries=1)
        job = asyncio.create_task(broker.execute_async([sys.executable, "-c", "import time; time.sleep(.15); print('finished')"]))
        ticks = 0
        while not job.done():
            ticks += 1
            await asyncio.sleep(.01)
        result = await job
        assert result.success and result.stdout.strip() == "finished"
        assert ticks > 2
    asyncio.run(exercise())


def test_async_cancellation_reaps_physical_child(tmp_path):
    pid_path = tmp_path / "pid.json"
    script = "import os,pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)"
    async def exercise():
        broker = SubprocessBroker(base_scratch_dir=tmp_path, max_retries=1)
        job = asyncio.create_task(broker.execute_async([sys.executable, "-c", script, str(pid_path)]))
        deadline = time.monotonic() + 10
        while not pid_path.exists() and time.monotonic() < deadline:
            await asyncio.sleep(.01)
        assert pid_path.exists()
        pid = int(pid_path.read_text())
        job.cancel()
        with pytest.raises(asyncio.CancelledError):
            await job
        assert not psutil.pid_exists(pid)
    asyncio.run(exercise())


def test_timeout_reaps_real_grandchild_tree(tmp_path):
    pid_path = tmp_path / "child-pid"
    script = (
        "import subprocess,sys,time,pathlib; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
        "pathlib.Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(30)"
    )
    broker = SubprocessBroker(base_scratch_dir=tmp_path, max_retries=1)
    result = broker.execute([sys.executable, "-c", script, str(pid_path)], timeout_seconds=.3)
    assert result.returncode == -124
    assert pid_path.exists()
    assert not psutil.pid_exists(int(pid_path.read_text()))


def test_portable_suspend_resume_of_real_process(tmp_path):
    pid_path = tmp_path / "pid"
    broker = SubprocessBroker(base_scratch_dir=tmp_path, max_retries=1)
    script = "import os,pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(1)"
    thread = threading.Thread(target=broker.execute, args=([sys.executable, "-c", script, str(pid_path)],))
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not pid_path.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        assert pid_path.exists()
        process = psutil.Process(int(pid_path.read_text()))
        broker.suspend()
        deadline = time.monotonic() + 1
        while process.status() != psutil.STATUS_STOPPED and time.monotonic() < deadline:
            time.sleep(.01)
        assert process.status() == psutil.STATUS_STOPPED
        broker.resume()
        thread.join(5)
        assert not thread.is_alive()
    finally:
        broker.resume()
        broker.cleanup()
        thread.join(5)


def test_crash_tail_preserves_exact_physical_stderr(tmp_path):
    from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
    message = bytes(range(256)) * 2
    result = safe_subprocess_run(
        [sys.executable, "-c", "import os; os.write(2,bytes(range(256))*2); os._exit(139)"],
        cwd=tmp_path, text=False, check=False, required_disk_gb=0,
    )
    assert result.returncode == 139
    assert result.hex_dump == message[-256:].hex()


def test_canonical_broker_persists_exact_crash_provenance(tmp_path):
    import hashlib
    broker = SubprocessBroker(base_scratch_dir=tmp_path, max_retries=3)
    broker.store_dir = tmp_path / "artifacts"
    result = broker.execute([sys.executable, "-c", "import os; os.write(2,bytes(range(256))*2); os._exit(139)"])
    assert not result.success and result.returncode == 139
    record = result.crash_diagnostics
    assert record["stderr_tail_hex"] == bytes(range(256)).hex()
    assert record["git_commit"]
    assert len(record["git_commit_object_sha256"]) == 64
    on_disk = json.loads(Path(record["record_path"]).read_text())
    digest = on_disk.pop("sha256")
    assert hashlib.sha256(json.dumps(on_disk, sort_keys=True, separators=(",", ":")).encode()).hexdigest() == digest
    assert len(list((tmp_path / "artifacts" / "Logs").glob("crash-*.json"))) == 1


def _git_test_environment():
    return {**{key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def _real_broker_crash(tmp_path, environment):
    script = """
import json, pathlib, sys
from cochem.concurrency.subprocess_broker import SubprocessBroker
root = pathlib.Path(sys.argv[1])
broker = SubprocessBroker(base_scratch_dir=root / 'scratch', max_retries=3)
broker.store_dir = root / 'artifacts'
result = broker.execute([sys.executable, '-c', 'import os; os.write(2,bytes(range(256))*2); os._exit(139)'])
(root / 'result.json').write_text(json.dumps({'returncode': result.returncode, 'success': result.success,
    'retries_attempted': result.retries_attempted, 'crash_diagnostics': result.crash_diagnostics}))
"""
    subprocess.run([sys.executable, "-c", script, str(tmp_path)], cwd=tmp_path,
                   env=environment, check=True, capture_output=True, timeout=20)
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["returncode"] == 139 and result["success"] is False
    assert result["retries_attempted"] == 0
    record = result["crash_diagnostics"]
    assert record["stderr_tail_hex"] == bytes(range(256)).hex()
    target = Path(record["record_path"])
    assert target.is_file() and target.stat().st_mode & 0o222 == 0
    on_disk = json.loads(target.read_text())
    digest = on_disk.pop("sha256")
    assert hashlib.sha256(json.dumps(on_disk, sort_keys=True, separators=(",", ":")).encode()).hexdigest() == digest
    assert len(list((tmp_path / "artifacts" / "Logs").glob("crash-*.json"))) == 1
    return record


@pytest.mark.parametrize("git_condition, expected_status", [
    ("missing_git", "unavailable"), ("timeout", "timeout"),
])
def test_optional_git_failure_preserves_real_broker_crash(tmp_path, git_condition, expected_status):
    """Use genuine Git failures and a real fatal process, without engine substitutes."""
    environment = _git_test_environment()
    if git_condition == "missing_git":
        empty_path = tmp_path / "empty-path"
        empty_path.mkdir()
        environment["PATH"] = str(empty_path)
    else:
        if not hasattr(os, "mkfifo"):
            pytest.skip("A POSIX FIFO is required to block a real Git configuration read")
        configuration = tmp_path / "blocked-git-config"
        os.mkfifo(configuration)
        # Git itself blocks opening a real FIFO; the production timeout must
        # terminate it. No replacement Git executable or patched interface.
        environment["GIT_CONFIG_GLOBAL"] = str(configuration)
    record = _real_broker_crash(tmp_path, environment)
    assert record["git_commit"] is None and record["git_commit_object_sha256"] is None
    assert record["git_provenance"]["status"] == expected_status
    if git_condition == "timeout":
        assert record["git_provenance"]["error_type"] == "TimeoutExpired"
        assert record["git_provenance"]["timeout_seconds"] == 2


def _copied_source_crash(tmp_path, environment):
    """Execute an unmodified provenance module from its physical source layout."""
    from cochem_base.core_engine import crash_provenance
    module = tmp_path / "installed_crash_provenance.py"
    shutil.copyfile(crash_provenance.__file__, module)
    script = """
import importlib.util, json, pathlib, subprocess, sys
root = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location('installed_crash_provenance', root / 'installed_crash_provenance.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
command = [sys.executable, '-c', 'import os; os.write(2,b"fatal process bytes"); os._exit(139)']
result = subprocess.run(command, capture_output=True, check=False)
record = module.record_process_crash(command, result.returncode, result.stderr, root / 'logs')
(root / 'result.json').write_text(json.dumps(record))
"""
    subprocess.run([sys.executable, "-c", script, str(tmp_path)], cwd=tmp_path,
                   env=environment, check=True, capture_output=True, timeout=20)
    record = json.loads((tmp_path / "result.json").read_text())
    assert record["exit_code"] == 139
    assert record["stderr_tail_hex"] == b"fatal process bytes".hex()
    target = Path(record["record_path"])
    assert target.is_file() and target.stat().st_mode & 0o222 == 0
    on_disk = json.loads(target.read_text())
    digest = on_disk.pop("sha256")
    assert hashlib.sha256(json.dumps(on_disk, sort_keys=True, separators=(",", ":")).encode()).hexdigest() == digest
    return record


@pytest.mark.parametrize("layout, expected_status", [
    ("installed_without_git", "no_repository"), ("invalid_repository", "failed"),
    ("unborn_repository", "failed"),
])
def test_source_layout_git_failures_preserve_real_crash(tmp_path, layout, expected_status):
    environment = _git_test_environment()
    if layout == "invalid_repository":
        (tmp_path / ".git").mkdir()
    elif layout == "unborn_repository":
        subprocess.run(["git", "init", "--quiet", "--template=", str(tmp_path)],
                       env=environment, check=True, capture_output=True)
    record = _copied_source_crash(tmp_path, environment)
    assert record["git_commit"] is None and record["git_commit_object_sha256"] is None
    assert record["git_provenance"]["status"] == expected_status
    assert record["git_provenance"]["repository"] == (None if layout == "installed_without_git" else str(tmp_path))


def _create_real_git_repository(path, environment):
    subprocess.run(["git", "init", "--quiet", "--template=", str(path)],
                   env=environment, check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.name=CoChem Git boundary test",
                    "-c", "user.email=git-boundary@example.invalid", "commit", "--quiet",
                    "--allow-empty", "--no-gpg-sign", "-m", "Actual source identity boundary fixture"],
                   env=environment, check=True, capture_output=True)
    return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                          env=environment, check=True, capture_output=True, text=True).stdout.strip()


def test_crash_source_identity_ignores_foreign_git_repository(tmp_path):
    from cochem_base.core_engine import crash_provenance
    environment = _git_test_environment()
    foreign = tmp_path / "foreign-repository"
    foreign_commit = _create_real_git_repository(foreign, environment)
    source = next(parent for parent in Path(crash_provenance.__file__).resolve().parents if (parent / ".git").exists())
    source_commit = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                                  env=environment, check=True, capture_output=True, text=True).stdout.strip()
    assert foreign_commit != source_commit
    foreign_git = foreign / ".git"
    environment.update(GIT_DIR=str(foreign_git), GIT_WORK_TREE=str(foreign), GIT_COMMON_DIR=str(foreign_git),
                       GIT_OBJECT_DIRECTORY=str(foreign_git / "objects"), GIT_NAMESPACE="foreign-namespace",
                       GIT_REPLACE_REF_BASE="refs/foreign-replacements")
    record = _real_broker_crash(tmp_path, environment)
    assert record["git_commit"] == source_commit
    assert record["git_provenance"] == {"status": "available", "repository": str(source)}
    commit_object = subprocess.run(["git", "-C", str(source), "cat-file", "commit", source_commit],
                                   env=_git_test_environment(), check=True, capture_output=True).stdout
    assert record["git_commit_object_sha256"] == hashlib.sha256(commit_object).hexdigest()


def test_crash_source_identity_follows_linked_worktree(tmp_path):
    environment = _git_test_environment()
    repository = tmp_path / "main-repository"
    expected_commit = _create_real_git_repository(repository, environment)
    worktree = tmp_path / "linked-worktree"
    subprocess.run(["git", "-C", str(repository), "worktree", "add", "--quiet", "--detach", str(worktree)],
                   env=environment, check=True, capture_output=True)
    assert (worktree / ".git").is_file()
    record = _copied_source_crash(worktree, environment)
    assert record["git_commit"] == expected_commit
    assert record["git_provenance"] == {"status": "available", "repository": str(worktree)}


def test_resource_guard_uses_container_available_memory(tmp_path):
    from cochem_base.core.resource_guard import evaluate_resource_guard
    # On-disk cgroup contract is an explicit supported input, not a patched probe.
    (tmp_path / "memory.max").write_text(str(16 * 1024**3))
    (tmp_path / "memory.current").write_text(str(15 * 1024**3))
    decision = evaluate_resource_guard(custom_cgroup_v2_path=tmp_path / "memory.max", scan_process_table=False)
    assert not decision.allow_local_llm
    assert decision.available_ram_gb <= 1
    assert decision.execution_mode in {"DRY_RUN", "EXTERNAL_API"}


def test_resource_guard_matches_v1_usage_when_v2_unlimited(tmp_path):
    from cochem_base.core.resource_guard import evaluate_resource_guard
    (tmp_path / "memory.max").write_text("max")
    (tmp_path / "memory.current").write_text("0")
    (tmp_path / "memory.limit_in_bytes").write_text(str(16 * 1024**3))
    (tmp_path / "memory.usage_in_bytes").write_text(str(15 * 1024**3))
    decision = evaluate_resource_guard(
        custom_cgroup_v2_path=tmp_path / "memory.max",
        custom_cgroup_v1_path=tmp_path / "memory.limit_in_bytes", scan_process_table=False,
    )
    assert decision.available_ram_gb <= 1
    assert not decision.allow_local_llm


def test_prompt_compression_bounds_real_process_telemetry():
    from cochem_base.cochem_core.ai.context_compression import ContextCompressor
    process = psutil.Process()
    observations = np.array([(time.monotonic(), process.memory_info().rss) for _ in range(600)])
    compressor = ContextCompressor()
    payload = compressor.compress_payload({"trajectory": compressor.compress_trajectory(observations)})["trajectory"]
    assert len(payload["points"]) <= 500
    assert payload["statistics"]["count"] == len(observations)
    assert payload["statistics"]["mean"] == np.mean(observations[:, 1])
    assert "skewness" in payload["statistics"]
    np.testing.assert_array_equal(payload["points"][0], observations[0])
    np.testing.assert_array_equal(payload["points"][-1], observations[-1])
    json.dumps(payload, allow_nan=False)
