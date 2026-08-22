# Test suite for CoChem Core Job Manager
import asyncio
import os
import sys
import time
from pathlib import Path
import pytest
from pydantic import ValidationError

from core_engine.cochem_core_job_manager import JobConfig, JobInfo, JobManager


def test_job_config_defaults_and_validation():
    cfg = JobConfig()
    assert cfg.command == ['echo', 'no command']
    assert cfg.product_class == 'Product_A_DeNovo'
    assert cfg.is_isotopologue is False
    assert cfg.has_parent_anchor is False
    assert cfg.floppy_monomer is False

    custom = JobConfig(
        command=['python', '--version'],
        product_class='Product_C_Differences',
        n_atoms=12,
        temporal_tier_override=2,
        max_duration_override=45,
        job_name='test_job'
    )
    assert custom.temporal_tier_override == 2
    assert custom.max_duration_override == 45
    assert custom.job_name == 'test_job'

    with pytest.raises(ValidationError):
        JobConfig(command=12345)


def test_temporal_tier_assignment():
    jm = JobManager()

    # Product C / isotopologue
    c1 = JobConfig(product_class='Product_C_Differences', atom_count=10)
    assert jm._assign_temporal_tier(c1) == 1
    c2 = JobConfig(is_isotopologue=True, atom_count=25)
    assert jm._assign_temporal_tier(c2) == 2

    # Product B / parent anchor
    b1 = JobConfig(product_class='Product_B_SemiExperimental', atom_count=15)
    assert jm._assign_temporal_tier(b1) == 3
    b2 = JobConfig(has_parent_anchor=True, atom_count=35)
    assert jm._assign_temporal_tier(b2) == 4

    # Product D / Active Learning
    d1 = JobConfig(product_class='Product_D_ActiveLearning', atom_count=20)
    assert jm._assign_temporal_tier(d1) == 9
    d2 = JobConfig(product_class='Product_D_ActiveLearning', atom_count=60)
    assert jm._assign_temporal_tier(d2) == 10

    # Floppy monomer
    f1 = JobConfig(floppy_monomer=True, atom_count=20)
    assert jm._assign_temporal_tier(f1) == 6
    f2 = JobConfig(floppy_monomer=True, atom_count=60)
    assert jm._assign_temporal_tier(f2) == 8

    # Standard Product A
    a1 = JobConfig(product_class='Product_A_DeNovo', atom_count=10)
    assert jm._assign_temporal_tier(a1) == 4
    a2 = JobConfig(product_class='Product_A_DeNovo', atom_count=25)
    assert jm._assign_temporal_tier(a2) == 5
    a3 = JobConfig(product_class='Product_A_DeNovo', atom_count=50)
    assert jm._assign_temporal_tier(a3) == 6
    a4 = JobConfig(product_class='Product_A_DeNovo', atom_count=90)
    assert jm._assign_temporal_tier(a4) == 7

    # Explicit override
    ov = JobConfig(temporal_tier_override=1)
    assert jm._assign_temporal_tier(ov) == 1


def test_job_submission_and_query():
    async def _test():
        jm = JobManager(max_job_history=5)
        job_id = await jm.submit_job({
            'command': [sys.executable, '-c', 'print("test")'],
            'product_class': 'Product_C_Differences',
            'atom_count': 5
        })
        assert job_id == 'job_0'
        info = jm.get_job(job_id)
        assert info is not None
        assert info.status == 'submitted'
        assert info.temporal_tier == 1
        assert info.max_duration == 10

        # Invalid submission
        with pytest.raises(ValueError):
            await jm.submit_job({'command': 9999})

        # Query dict format
        st = jm.get_job_status(job_id)
        assert isinstance(st, dict)
        assert st['job_id'] == 'job_0'
        assert st['status'] == 'submitted'

    asyncio.run(_test())


def test_job_execution_success():
    async def _test():
        jm = JobManager()
        script = 'import sys; sys.stdout.write("OUTPUT_OK"); sys.stderr.write("ERR_OK"); sys.exit(0)'
        job_id = await jm.submit_job({
            'command': [sys.executable, '-c', script],
            'max_duration_override': 15
        })
        await jm.start_job(job_id)
        finished_job = await jm.wait_for_job(job_id, timeout=10.0)

        assert finished_job is not None
        assert finished_job.status == 'completed'
        assert finished_job.return_code == 0
        assert finished_job.stdout == 'OUTPUT_OK'
        assert finished_job.stderr == 'ERR_OK'
        assert finished_job.duration is not None and finished_job.duration >= 0.0
        assert len(jm.get_completed_jobs()) == 1

    asyncio.run(_test())


def test_job_execution_failure_code():
    async def _test():
        jm = JobManager()
        script = 'import sys; sys.stderr.write("NONZERO_FAIL"); sys.exit(7)'
        job = await jm.run_job({
            'command': [sys.executable, '-c', script],
            'max_duration_override': 15
        }, timeout=10.0)

        assert job.status == 'failed'
        assert job.return_code == 7
        assert 'NONZERO_FAIL' in (job.stderr or '')
        assert len(jm.get_failed_jobs()) == 1

    asyncio.run(_test())


def test_job_timeout_enforcement():
    async def _test():
        jm = JobManager()
        script = 'import time; time.sleep(10)'
        job = await jm.run_job({
            'command': [sys.executable, '-c', script],
            'max_duration_override': 1
        }, timeout=5.0)

        assert job.status == 'timed_out'
        assert job.return_code == -1
        assert 'exceeded temporal maximum duration' in (job.error or '')

    asyncio.run(_test())


def test_job_cancellation():
    async def _test():
        jm = JobManager()
        script = 'import time; time.sleep(10)'
        job_id = await jm.submit_job({
            'command': [sys.executable, '-c', script],
            'max_duration_override': 30
        })
        await jm.start_job(job_id)
        await asyncio.sleep(0.2)

        assert len(jm.get_running_jobs()) == 1
        cancelled = jm.cancel_job(job_id)
        assert cancelled is True

        job = jm.get_job(job_id)
        assert job is not None
        assert job.status == 'cancelled'
        assert len(jm.get_running_jobs()) == 0

    asyncio.run(_test())


def test_purge_and_history_limits():
    async def _test():
        jm = JobManager(max_job_history=3)
        for i in range(5):
            await jm.run_job({
                'command': [sys.executable, '-c', f'print("job_{i}")'],
                'max_duration_override': 5
            })

        assert len(jm.jobs) <= 3
        cleared = jm.clear_history()
        assert cleared <= 3
        assert len(jm.jobs) == 0

    asyncio.run(_test())


def test_large_output_stream_no_deadlock():
    async def _test():
        jm = JobManager()
        # Generates ~250KB of stdout and 250KB of stderr to test pipe deadlock prevention
        script = 'import sys; sys.stdout.write("X" * 250000); sys.stderr.write("Y" * 250000); sys.exit(0)'
        job = await jm.run_job({
            'command': [sys.executable, '-c', script],
            'max_duration_override': 15
        }, timeout=10.0)

        assert job.status == 'completed'
        assert job.return_code == 0
        assert len(job.stdout or '') == 250000
        assert len(job.stderr or '') == 250000

    asyncio.run(_test())


def test_custom_cwd_and_env(tmp_path: Path):
    async def _test():
        jm = JobManager()
        custom_var_name = "COCHEM_CUSTOM_ENV_TEST"
        custom_var_val = "SUPER_SECRET_VALUE"
        script = f'import os, sys; sys.stdout.write(os.getcwd() + ":::" + os.getenv("{custom_var_name}", "MISSING"))'

        job = await jm.run_job({
            'command': [sys.executable, '-c', script],
            'cwd': str(tmp_path),
            'env': {custom_var_name: custom_var_val},
            'max_duration_override': 10
        })

        assert job.status == 'completed'
        assert job.return_code == 0
        assert str(tmp_path).lower() in (job.stdout or '').lower()
        assert custom_var_val in (job.stdout or '')

    asyncio.run(_test())


def test_invalid_cwd_or_empty_command():
    async def _test():
        jm = JobManager()

        # Non-existent directory
        bad_dir_job_id = await jm.submit_job({
            'command': [sys.executable, '-c', 'print("hi")'],
            'cwd': 'D:\\non_existent_folder_xyz_123'
        })
        await jm.start_job(bad_dir_job_id)
        info1 = jm.get_job(bad_dir_job_id)
        assert info1 is not None
        assert info1.status == 'failed'
        assert 'Specified working directory does not exist' in (info1.error or '')

        # Empty command
        empty_cmd_job_id = await jm.submit_job({
            'command': []
        })
        await jm.start_job(empty_cmd_job_id)
        info2 = jm.get_job(empty_cmd_job_id)
        assert info2 is not None
        assert info2.status == 'failed'
        assert 'Job command list cannot be empty' in (info2.error or '')

    asyncio.run(_test())


def test_list_jobs_filtering():
    async def _test():
        jm = JobManager()
        j1 = await jm.run_job({'command': [sys.executable, '-c', 'import sys; sys.exit(0)']})
        j2 = await jm.run_job({'command': [sys.executable, '-c', 'import sys; sys.exit(1)']})

        all_jobs = jm.list_jobs()
        assert len(all_jobs) == 2

        completed_jobs = jm.list_jobs(status='completed')
        assert len(completed_jobs) == 1
        assert completed_jobs[0]['status'] == 'completed'

        failed_jobs = jm.list_jobs(status='failed')
        assert len(failed_jobs) == 1
        assert failed_jobs[0]['status'] == 'failed'

    asyncio.run(_test())


def test_process_tree_zombie_cleanup_on_timeout():
    import psutil
    async def _test():
        jm = JobManager()
        parent_script = '''
import subprocess, sys, time
proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
time.sleep(60)
'''
        job_id = await jm.submit_job({
            'command': [sys.executable, '-c', parent_script],
            'max_duration_override': 2
        })
        await jm.start_job(job_id)
        await asyncio.sleep(0.8)

        parent_proc_info = jm.active_processes.get(job_id)
        assert parent_proc_info is not None
        parent_pid = parent_proc_info['process'].pid

        p = psutil.Process(parent_pid)
        children = p.children(recursive=True)
        assert len(children) >= 1
        child_pids = [c.pid for c in children]

        finished = await jm.wait_for_job(job_id, timeout=6.0)
        assert finished is not None
        assert finished.status == 'timed_out'

        await asyncio.sleep(0.5)
        assert not psutil.pid_exists(parent_pid)
        for c_pid in child_pids:
            assert not psutil.pid_exists(c_pid), f"Child process {c_pid} was not cleaned up!"

    asyncio.run(_test())


def test_job_cancellation_race_and_process_tree():
    import psutil
    async def _test():
        jm = JobManager()
        parent_script = '''
import subprocess, sys, time
proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
time.sleep(60)
'''
        job_id = await jm.submit_job({
            'command': [sys.executable, '-c', parent_script],
            'max_duration_override': 30
        })
        await jm.start_job(job_id)
        await asyncio.sleep(0.8)

        parent_proc_info = jm.active_processes.get(job_id)
        assert parent_proc_info is not None
        parent_pid = parent_proc_info['process'].pid

        p = psutil.Process(parent_pid)
        children = p.children(recursive=True)
        assert len(children) >= 1
        child_pids = [c.pid for c in children]

        assert jm.cancel_job(job_id) is True
        await asyncio.sleep(0.3)

        job = jm.get_job(job_id)
        assert job is not None
        assert job.status == 'cancelled'

        await asyncio.sleep(0.5)
        assert not psutil.pid_exists(parent_pid)
        for c_pid in child_pids:
            assert not psutil.pid_exists(c_pid), f"Child process {c_pid} survived cancellation!"

    asyncio.run(_test())


def test_massive_stream_communicate_deadlock_safety():
    async def _test():
        jm = JobManager()
        # Generates 1,000,000 bytes of stdout and 1,000,000 bytes of stderr simultaneously
        script = 'import sys; sys.stdout.write("A" * 1000000); sys.stderr.write("B" * 1000000); sys.exit(0)'
        job = await jm.run_job({
            'command': [sys.executable, '-c', script],
            'max_duration_override': 15
        }, timeout=10.0)

        assert job.status == 'completed'
        assert job.return_code == 0
        assert len(job.stdout or '') == 1000000
        assert len(job.stderr or '') == 1000000

    asyncio.run(_test())