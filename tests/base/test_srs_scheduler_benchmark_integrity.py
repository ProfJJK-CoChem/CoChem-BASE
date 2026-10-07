"""Physical persistence and explicit unavailable benchmark regressions."""

import json
import os
from pathlib import Path
import threading

import pytest

from cochem.core.context import AirGapViolationError
from cochem_base.config_loader import get_state_file_path
from cochem_base.core_engine.cochem_core_scheduler import (
    CoreScheduler, SchedulerStateError, TaskResult, persist_swarm_state_atomic,
)
from cochem_base.orchestrator.cochem_gpu_crossover_bench import (
    BenchmarkUnavailableError, fit_empirical_crossover_surface,
    get_standard_benchmark_systems, run_analytical_physics_point,
)


@pytest.mark.parametrize("is_gpu", [False, True])
def test_retired_surrogate_cannot_publish_physics_or_timings(is_gpu):
    system = get_standard_benchmark_systems()["water_dimer"]
    with pytest.raises(BenchmarkUnavailableError, match="genuine PySCF/ORCA"):
        run_analytical_physics_point(system, is_gpu=is_gpu)


def test_calibration_cannot_invent_a_threshold_without_observations():
    with pytest.raises(BenchmarkUnavailableError, match="two measured"):
        fit_empirical_crossover_surface([])


@pytest.mark.parametrize("existing", [b'{"retained":', b'["wrong-schema"]', b'\xff\xfe'])
def test_scheduler_preserves_corrupt_state(tmp_path, existing):
    state = tmp_path / "swarm_state.json"
    state.write_bytes(existing)
    with pytest.raises(SchedulerStateError):
        persist_swarm_state_atomic(state, "new-task", {"status": "SUCCESS"})
    assert state.read_bytes() == existing


def test_scheduler_default_state_is_external_and_source_override_rejected():
    repo = Path(__file__).resolve().parents[2]
    scheduler = CoreScheduler(max_workers=1)
    try:
        assert scheduler.state_file == get_state_file_path()
        assert not scheduler.state_file.is_relative_to(repo)
    finally:
        scheduler.stop_scheduling()
    with pytest.raises(AirGapViolationError):
        CoreScheduler(max_workers=1, project_root=repo)


def test_scheduler_atomic_updates_remain_readable(tmp_path):
    state = tmp_path / "swarm_state.json"
    state.write_text('{"retained": {"status": "SUCCESS"}}')
    errors = []
    stop = threading.Event()
    observed = threading.Event()

    def reader():
        while not stop.is_set():
            try:
                assert "retained" in json.loads(state.read_text())
                observed.set()
            except Exception as exc:
                errors.append(exc)
                return

    thread = threading.Thread(target=reader)
    thread.start()
    try:
        for index in range(30):
            persist_swarm_state_atomic(state, f"task-{index}", {"status": "SUCCESS"})
        assert observed.wait(2)
    finally:
        stop.set()
        thread.join(2)
    assert not errors
    assert len(json.loads(state.read_text())) == 31


def test_scheduler_merges_outcome_in_explicit_external_workspace(tmp_path):
    scheduler = CoreScheduler(max_workers=1, project_root=tmp_path)
    try:
        scheduler._update_swarm_state(TaskResult(task_id="physical-task", status="completed"))
        assert json.loads((tmp_path / "swarm_state.json").read_text())["physical-task"]["status"] == "SUCCESS"
    finally:
        scheduler.stop_scheduling()


@pytest.mark.parametrize("entry", [{"time": float("nan")}, {"energy": float("inf")}])
def test_scheduler_rejects_nonfinite_new_state_without_mutation(tmp_path, entry):
    state = tmp_path / "swarm_state.json"
    original = b'{"retained": {"status": "SUCCESS"}}'
    state.write_bytes(original)
    with pytest.raises(SchedulerStateError, match="finite JSON"):
        persist_swarm_state_atomic(state, "new-task", entry)
    assert state.read_bytes() == original


def test_scheduler_preserves_nonfinite_prior_state(tmp_path):
    state = tmp_path / "swarm_state.json"
    original = b'{"retained": {"time": NaN}}'
    state.write_bytes(original)
    with pytest.raises(SchedulerStateError, match="Corrupt"):
        persist_swarm_state_atomic(state, "new-task", {"status": "SUCCESS"})
    assert state.read_bytes() == original


def test_benchmark_hardware_does_not_invent_performance_core_count():
    from cochem_base.orchestrator.cochem_gpu_crossover_bench import interrogate_hardware
    hardware = interrogate_hardware()
    assert hardware.performance_cores is None
    if Path("/proc/cpuinfo").is_file():
        assert hardware.has_avx2 == ("avx2" in Path("/proc/cpuinfo").read_text().split())


# Grammar examples test the output parser; they are not physical reference data.
_ORCA_PARSER_EXAMPLE = """
Number of basis functions ... 118
SCF CONVERGED AFTER 12 CYCLES
FINAL SINGLE POINT ENERGY -1.52D+02
Total SCF time: 1.25 sec
ORCA TERMINATED NORMALLY
"""


def test_benchmark_parser_reads_fortran_exponent_and_explicit_evidence():
    from cochem_base.orchestrator.cochem_gpu_crossover_bench import parse_orca_benchmark_output
    parsed = parse_orca_benchmark_output(_ORCA_PARSER_EXAMPLE)
    assert parsed == {"energy_hartree": -152.0, "scf_wall_seconds": 1.25,
                      "basis_function_count": 118, "scf_cycles": 12}


@pytest.mark.parametrize("remove", ["ORCA TERMINATED NORMALLY", "SCF CONVERGED AFTER 12 CYCLES",
                                    "FINAL SINGLE POINT ENERGY -1.52D+02", "Total SCF time: 1.25 sec",
                                    "Number of basis functions ... 118"])
def test_benchmark_parser_cannot_fill_missing_evidence(remove):
    from cochem_base.orchestrator.cochem_gpu_crossover_bench import parse_orca_benchmark_output
    with pytest.raises(BenchmarkUnavailableError):
        parse_orca_benchmark_output(_ORCA_PARSER_EXAMPLE.replace(remove, ""))


@pytest.mark.parametrize("trailer", ["FINAL SINGLE POINT ENERGY NaN", "Total SCF time: 0 sec",
                                     "Total SCF time: inf sec", "SCF NOT CONVERGED"])
def test_benchmark_parser_rejects_invalid_last_measurements(trailer):
    from cochem_base.orchestrator.cochem_gpu_crossover_bench import parse_orca_benchmark_output
    with pytest.raises(BenchmarkUnavailableError):
        parse_orca_benchmark_output(_ORCA_PARSER_EXAMPLE + trailer)


def test_benchmark_cannot_publish_empty_measurements(tmp_path):
    from cochem_base.orchestrator.cochem_gpu_crossover_bench import (
        BenchmarkTask, ComparisonMode, FullBenchmarkReport,
        interrogate_hardware, save_calibration_artifacts,
    )
    report = FullBenchmarkReport(hardware=interrogate_hardware(), mode=ComparisonMode.MATCHED,
                                 task=BenchmarkTask.ENERGY, xc="b3lyp", basis="def2-tzvpp")
    with pytest.raises(BenchmarkUnavailableError, match="without measured"):
        save_calibration_artifacts(report, tmp_path / "out.json", tmp_path / "out.md")
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("field,value", [("energy_hartree", float("nan")),
                                         ("scf_wall_seconds", float("inf")),
                                         ("scf_wall_seconds", 0.0), ("converged", "true")])
def test_run_schema_rejects_invalid_measurement_evidence(field, value):
    from pydantic import ValidationError
    from cochem_base.orchestrator.cochem_gpu_crossover_bench import SingleRunResult
    # Deliberately invalid schema inputs; never a measured or published run.
    payload = dict(system_id="parser-contract", engine="pyscf_cpu", device="cpu:1_cores",
                   mode="matched", task="energy", xc="b3lyp", basis="def2-svp",
                   basis_function_count=1, energy_hartree=-1.0, scf_wall_seconds=1.0,
                   total_wall_seconds=1.0, converged=False)
    payload[field] = value
    with pytest.raises(ValidationError) as error:
        SingleRunResult(**payload)
    assert field in {problem["loc"][0] for problem in error.value.errors()}


def test_run_schema_requires_convergence_evidence():
    from pydantic import ValidationError
    from cochem_base.orchestrator.cochem_gpu_crossover_bench import SingleRunResult
    with pytest.raises(ValidationError) as error:
        SingleRunResult(system_id="parser-contract", engine="pyscf_cpu", device="cpu:1_cores",
                        mode="matched", task="energy", xc="b3lyp", basis="def2-svp",
                        basis_function_count=1, energy_hartree=-1.0, scf_wall_seconds=1.0,
                        total_wall_seconds=1.0)
    assert "converged" in {problem["loc"][0] for problem in error.value.errors()}


@pytest.mark.skipif(os.name == "nt", reason="POSIX zombie ownership contract")
def test_exit_cleanup_does_not_wait_for_unrelated_zombies():
    import subprocess
    import sys
    import time
    from cochem_base.orchestrator.cochem_setup_phase_10 import sweep_zombies

    # The helper owns its exited child; the caller cannot reap that grandchild.
    helper = subprocess.Popen([sys.executable, "-u", "-c",
                               "import subprocess,sys,time; "
                               "child=subprocess.Popen([sys.executable,'-c','pass']); "
                               "time.sleep(.2); print('ready',flush=True); sys.stdin.readline(); child.wait()"],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert helper.stdout.readline().strip() == "ready"
        started = time.monotonic()
        sweep_zombies()
        assert time.monotonic() - started < 0.5
        assert helper.poll() is None
    finally:
        helper.stdin.write("reap\n")
        helper.stdin.flush()
        helper.wait(timeout=5)
        helper.stdin.close()
        helper.stdout.close()


def test_scheduler_real_commands_preserve_failure_and_isolated_working_directory(tmp_path):
    import sys
    from cochem_base.core_engine.cochem_core_scheduler import TaskConfig

    scheduler = CoreScheduler(max_workers=1, project_root=tmp_path)
    try:
        failed = scheduler._execute_task(TaskConfig(task_id="failed-process", command=[
            sys.executable, "-c", "import sys; print('transport failure'); sys.exit(7)"]))
        succeeded = scheduler._execute_task(TaskConfig(task_id="successful-process", command=[
            sys.executable, "-c", "from pathlib import Path; print(Path.cwd())"]))
        assert failed.status == "failed" and failed.return_code == 7
        assert "transport failure" in Path(failed.output_file).read_text()
        assert succeeded.status == "completed" and succeeded.return_code == 0
        assert Path(succeeded.output_file).read_text().strip() == str(Path(succeeded.output_file).parent)
        assert Path(failed.output_file).parent != Path(succeeded.output_file).parent
        state = json.loads((tmp_path / "swarm_state.json").read_text())
        assert state["failed-process"]["status"] == "FAILURE"
        assert state["successful-process"]["status"] == "SUCCESS"
    finally:
        scheduler.stop_scheduling()


@pytest.mark.skipif(os.name == "nt", reason="POSIX resource-tracker wait ownership")
def test_cleanup_preserves_multiprocessing_resource_tracker_wait_ownership():
    import os
    import subprocess
    import sys
    import textwrap

    # A genuine tracker is started in an isolated interpreter, then exits before
    # its owning ResourceTracker object collects its status. This is the race
    # that blanket direct-child reaping broke during final interpreter cleanup.
    script = textwrap.dedent("""
        import os, signal, time
        import psutil
        from multiprocessing.resource_tracker import ResourceTracker
        from cochem_base.process_cleanup import reap_owned_children
        from cochem_base.core_engine.cochem_core_scheduler import sweep_zombie_processes
        from cochem_base.core_engine.cochem_core_context_compressor import _reap_zombies as context_cleanup
        from cochem_base.core_engine.cochem_core_config_compiler import _reap_zombies as compiler_cleanup
        from cochem_base.core_engine.cochem_core_hardware_profiler import _sweep_zombies as hardware_cleanup
        from cochem_base.core_engine.cochem_core_parsl_executors import _sweep_zombie_processes as parsl_cleanup
        from cochem_base.managers.scribe_doc_manager import _sweep_zombies as scribe_cleanup

        tracker = ResourceTracker()
        tracker.ensure_running()
        pid = tracker._pid
        try:
            os.kill(pid, signal.SIGKILL)
            deadline = time.monotonic() + 5
            while psutil.Process(pid).status() != psutil.STATUS_ZOMBIE:
                if time.monotonic() > deadline:
                    raise TimeoutError('Resource tracker did not exit')
                time.sleep(.01)
            for cleanup in (reap_owned_children, sweep_zombie_processes, context_cleanup,
                            compiler_cleanup, hardware_cleanup, parsl_cleanup, scribe_cleanup):
                cleanup()
        finally:
            tracker._stop()
        assert tracker._pid is None
        print('tracker owner reaped successfully')
    """)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(path for path in sys.path if path)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                            env=env, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "tracker owner reaped successfully" in result.stdout
    assert "Exception ignored" not in result.stderr
    assert "ChildProcessError" not in result.stderr


def test_cleanup_reaps_registered_handles_and_preserves_their_exit_status():
    import subprocess
    import sys
    import time
    from cochem_base.process_cleanup import reap_owned_children
    from cochem_base.core_engine.cochem_core_subprocess_broker import (
        register_popen_process, unregister_popen_process,
    )

    child = subprocess.Popen([sys.executable, "-c", "import time,sys; time.sleep(.1); sys.exit(7)"])
    register_popen_process(child)
    try:
        deadline = time.monotonic() + 5
        while child.returncode is None:
            reap_owned_children()
            if time.monotonic() > deadline:
                raise TimeoutError("Registered child was not reaped through its Popen handle")
            time.sleep(.01)
        assert child.wait(timeout=1) == 7
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        unregister_popen_process(child)


def test_imported_cleanup_hooks_coexist_with_real_shared_memory_at_interpreter_exit():
    import os
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent("""
        from cochem_base.core_engine import cochem_core_context_compressor
        from cochem_base.core_engine import cochem_core_config_compiler
        from cochem_base.core_engine import cochem_core_hardware_profiler
        from cochem_base.core_engine import cochem_core_parsl_executors
        from cochem_base.managers import scribe_doc_manager
        from multiprocessing.shared_memory import SharedMemory

        segment = SharedMemory(create=True, size=16)
        try:
            segment.buf[:4] = b'BASE'
            assert bytes(segment.buf[:4]) == b'BASE'
        finally:
            segment.close()
            segment.unlink()
        print('shared-memory work completed')
    """)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(path for path in sys.path if path)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                            env=env, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "shared-memory work completed" in result.stdout
    assert "Exception ignored" not in result.stderr
    assert "ChildProcessError" not in result.stderr
    assert "leaked shared_memory" not in result.stderr
