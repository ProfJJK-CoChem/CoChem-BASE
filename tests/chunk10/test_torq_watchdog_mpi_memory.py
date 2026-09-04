import subprocess
import sys

from cochem_base.cochem_torq_watchdog import (
    DynamicMemoryResult,
    dynamic_memory_backoff,
)


def test_multi_rank_mpi_memory_governance():
    # 16 GB available RAM, 8 MPI ranks
    avail_mb = 16384
    tot_mb = 32768
    nprocs = 8

    res = dynamic_memory_backoff(
        req_mb=4000,
        total_system_ram_mb=tot_mb,
        available_system_ram_mb=avail_mb,
        nprocs=nprocs,
        backoff_factor=0.75,
    )
    assert isinstance(res, DynamicMemoryResult)
    # Total aggregate maxcore across 8 ranks must be <= 85% of available RAM (13926 MB)
    maxcore = int(res)
    assert maxcore * nprocs <= 0.85 * avail_mb
    assert res["direct_scf_required"] is False

def test_direct_scf_recommendation_when_maxcore_under_512():
    # Very constrained memory: 2000 MB available, 4 ranks -> maxcore ~ 425 MB (< 512 MB)
    res = dynamic_memory_backoff(
        req_mb=2000,
        total_system_ram_mb=4096,
        available_system_ram_mb=2000,
        nprocs=4,
    )
    assert int(res) < 512
    assert res["direct_scf_required"] is True
    assert res["integral_mode_recommendation"] == "! NoRifDirect"

def test_numeric_comparison_and_casting():
    res = DynamicMemoryResult(new_maxcore_mb=1024)
    assert int(res) == 1024
    assert float(res) == 1024.0
    assert res > 512
    assert res <= 1024
    assert res + 256 == 1280

def test_process_reaping_on_oom():
    # Launch real subprocess
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    try:
        assert proc.poll() is None
        res = dynamic_memory_backoff(
            req_mb=4096,
            process_pid=proc.pid,
            available_system_ram_mb=8192,
            total_system_ram_mb=16384,
        )
        assert res["process_reaped"] is True
        # Verify process is terminated
        proc.wait(timeout=3.0)
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()
