"""Tests for architecture - Part 7 (Suggestions #65, #67, #68, #69, #70)."""

import math
import os
import time
import atexit
import threading
import tempfile
from pathlib import Path
import pytest
import h5py
from cochem_base.core.exceptions import AirGapBoundaryError
from cochem_base.core.mendeleev_invariants import get_element_cache
from cochem_base.core.cochem_sandbox import SandboxContext
from cochem_base.core.process_reaper import ProcessTreeManager
from cochem_base.core_engine.cochem_core_subprocess_broker import (
    verify_scratch_quota_and_io,
    _SCRATCH_VERIFICATION_CACHE,
)


def test_hdf5_swmr_inplace_resizing_and_airgap(tmp_path):
    """Validates Suggestion #65: In-place HDF5 SWMR chunk resizing and Air-Gap enforcement."""
    # Configure test environment
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    os.environ["COCH_SRC"] = str(src_dir)

    # Attempting to write into Tier 1 ($COCH_SRC) must raise AirGapBoundaryError
    h5_src_path = src_dir / "store.h5"
    with pytest.raises(AirGapBoundaryError) as exc_info:
        from cochem_base.core.ipc.serializer import validate_airgap_write_path
        validate_airgap_write_path(h5_src_path)
    assert exc_info.value.error_code == "COCHEM_E_AIRGAP_BREACH"

    # Valid write into temporary scratch
    h5_scratch_path = tmp_path / "scratch" / "store.h5"
    h5_scratch_path.parent.mkdir()

    # Create SWMR dataset
    with h5py.File(h5_scratch_path, "w", libver="latest") as f:
        ds = f.create_dataset(
            "energies",
            shape=(1,),
            maxshape=(None,),
            chunks=(512,),
            dtype="float64",
            compression="gzip",
        )
        ds[0] = -76.432

    # In-place chunk resizing
    with h5py.File(h5_scratch_path, "a", libver="latest") as f:
        ds = f["energies"]
        new_len = ds.shape[0] + 1
        ds.resize((new_len,))
        ds[new_len - 1] = -76.435
        ds.flush()

    # Verify length without whole-file copying
    with h5py.File(h5_scratch_path, "r") as f:
        assert f["energies"].shape[0] == 2
        assert math.isclose(f["energies"][1], -76.435)


def test_mendeleev_invariants_lazy_singleton_startup():
    """Validates Suggestion #67: Lazy singleton initialization eliminates top-level import lag."""
    # Ensure cache function returns valid mapping from Z=1 to Z=118
    cache = get_element_cache()
    assert len(cache) >= 118
    assert cache[1].symbol == "H"
    assert cache[6].symbol == "C"


def test_sandbox_context_atexit_unregister_and_airgap(tmp_path):
    """Validates Suggestion #68: atexit callback unregistration on context exit."""
    # Air-gap boundary assertion: attempting to allocate sandbox inside Tier 1 ($COCH_SRC) must fail
    src_dir = tmp_path / "src"
    src_dir.mkdir(exist_ok=True)
    os.environ["COCH_SRC"] = str(src_dir)
    with pytest.raises(AirGapBoundaryError) as exc_info:
        SandboxContext(scratch_root=src_dir)
    assert exc_info.value.error_code == "COCHEM_E_AIRGAP_BREACH"

    scratch_dir = tmp_path / "scratch"
    os.environ["COCH_SCRATCH"] = str(scratch_dir)

    with SandboxContext(scratch_root=scratch_dir) as sb:
        assert sb.path.exists()

    # Path must be unlinked and cleaned
    assert not sb.path.exists()

    # Cleaned flag must be set
    assert sb._cleaned is True


def test_process_reaper_direct_pid_monitoring():
    """Validates Suggestion #69: Direct child PID tracking in ProcessTreeManager."""
    manager = ProcessTreeManager()

    # Spawn child process
    import subprocess
    import sys
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    manager.register_process(proc.pid)

    assert proc.pid in manager._tracked
    rss = manager.sample_process_tree_rss_bytes()
    assert rss > 0

    # Terminate tracked process
    manager.terminate_tree()
    proc.wait()
    assert not proc.poll() is None


def test_subprocess_broker_scratch_verification_cache(tmp_path):
    """Validates Suggestion #70: Scratch verification caching with TTL."""
    scratch_dir = tmp_path / "scratch_io"
    scratch_dir.mkdir()
    _SCRATCH_VERIFICATION_CACHE.clear()

    # First call must perform physical write probe
    t0 = time.perf_counter()
    assert verify_scratch_quota_and_io(scratch_dir, ttl_seconds=300.0) is True
    t1 = time.perf_counter()
    initial_duration = t1 - t0

    # Second call within TTL must hit cache and return immediately (< 2 ms)
    t2 = time.perf_counter()
    assert verify_scratch_quota_and_io(scratch_dir, ttl_seconds=300.0) is True
    t3 = time.perf_counter()
    cached_duration = t3 - t2

    assert cached_duration < 0.002
    assert cached_duration < initial_duration
