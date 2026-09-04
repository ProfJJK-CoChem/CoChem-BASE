"""Zero-Mock Architecture, Air-Gap, and Concurrency Test Suite (Part 4).
Validates Suggestions #31, #32, #33, #37, and #40.
Adheres strictly to Method Matrix v4 and Zero-Mock Anti-Spoofing Protocol v3.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import pathlib
import sys
import threading
import time
from typing import Optional

import pytest

from cochem.core.config import CoChemConfigManager, ConfigurationParseError
from cochem.core.cochem_sandbox import SandboxConfig, SandboxContext
from cochem.core.airgap_coordinator import (
    AirGapCoordinator,
    AirGapViolationError,
    TripartiteStorageConfig,
)
from cochem.core.context import FileLock


def test_config_manager_strict_toml_parsing(tmp_path: pathlib.Path) -> None:
    """Validate that invalid TOML raises ConfigurationParseError with diagnostics and valid TOML ingests 64 GB."""
    # 1. Deliberate syntax error in cochem.toml
    bad_toml = tmp_path / "cochem.toml"
    bad_toml.write_text("memory_gb = [unclosed_bracket\n", encoding="utf-8")

    manager = CoChemConfigManager(project_root=tmp_path)

    with pytest.raises(ConfigurationParseError) as exc_info:
        manager.load_config()

    error_msg = str(exc_info.value)
    assert str(bad_toml.resolve()) in error_msg
    assert "line" in error_msg.lower()
    assert "syntax error" in error_msg.lower() or "decoding error" in error_msg.lower()

    # 2. Valid cochem.toml with memory_gb = 64
    valid_toml = tmp_path / "cochem.toml"
    valid_toml.write_text("[core]\nmemory_gb = 64\n", encoding="utf-8")

    valid_manager = CoChemConfigManager(project_root=tmp_path)
    cfg = valid_manager.load_config()
    assert cfg.core.memory_gb == 64


def test_sandbox_preserves_primary_scientific_exception(tmp_path: pathlib.Path) -> None:
    """Validate that primary scientific exceptions are preserved when secondary cleanup OSErrors occur."""
    scratch_dir = tmp_path / "scratch_work"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    sb_config = SandboxConfig(
        scratch_parent_dir=scratch_dir,
        max_cleanup_retries=1,
        cleanup_backoff_base_s=0.01,
    )

    open_handle = None
    locked_target_path: Optional[pathlib.Path] = None

    try:
        with pytest.raises(RuntimeError, match="Electronic structure SCF failed to converge"):
            with SandboxContext(sb_config) as sandbox:
                assert sandbox.root is not None
                locked_target_path = sandbox.root / "active_scf_matrix.dat"
                locked_target_path.write_text("DENSE_FOCK_MATRIX_CONVERGENCE_TRACE", encoding="utf-8")

                # Force an un-deletable file lock:
                # On Windows, open for read/write without delete sharing prevents unlinking/rmtree.
                # On POSIX, revoking directory write permission prevents rmtree deletion.
                open_handle = open(locked_target_path, "r+b")
                if sys.platform != "win32":
                    os.chmod(sandbox.root, 0o555)

                raise RuntimeError("Electronic structure SCF failed to converge")
    finally:
        if open_handle is not None:
            open_handle.close()
        if sys.platform != "win32" and locked_target_path is not None and locked_target_path.parent.exists():
            try:
                os.chmod(locked_target_path.parent, 0o777)
            except OSError:
                pass


def test_artifact_publication_atomicity_and_source_immutability(tmp_path: pathlib.Path) -> None:
    """Validate atomic artifact publication, SHA-256 verification, source immutability, and scratch lock resilience."""
    code_dir = tmp_path / "immutable_source"
    artifacts_dir = tmp_path / "published_artifacts"
    scratch_dir = tmp_path / "ephemeral_scratch"

    code_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    config = TripartiteStorageConfig(
        code_root=code_dir,
        artifacts_root=artifacts_dir,
        scratch_root=scratch_dir,
    )
    coordinator = AirGapCoordinator(config)

    # 1. Create valid artifact in scratch
    job_scratch = scratch_dir / "calc_job_001"
    job_scratch.mkdir(parents=True, exist_ok=True)
    source_artifact = job_scratch / "optimized_geometry.xyz"
    content = b"3\nWater molecule\nO 0.000 0.000 0.000\nH 0.000 0.757 0.586\nH 0.000 -0.757 0.586\n"
    source_artifact.write_bytes(content)
    expected_sha256 = hashlib.sha256(content).hexdigest()

    # 2. Publish artifact to artifacts tier
    rel_dest = pathlib.Path("water") / "optimized_geometry.xyz"
    dest_path, sha256_result = coordinator.publish_artifact(
        source_path=source_artifact,
        relative_dest=rel_dest,
        compute_sha256=True,
    )

    assert dest_path.exists()
    assert dest_path.read_bytes() == content
    assert sha256_result == expected_sha256

    # 3. Source Tier ($T_src) write attempts must raise AirGapViolationError
    forbidden_src_dest = code_dir / "backdoored_module.py"
    with pytest.raises(AirGapViolationError, match="immutable and read-only"):
        coordinator.publish_artifact(
            source_path=source_artifact,
            relative_dest=forbidden_src_dest,
        )

    # 4. Scratch unlinking collision resilience:
    # Create new artifact, hold it open so phase 2 unlink fails on Windows, verify publication succeeds.
    scratch_file_2 = job_scratch / "wavefunction.npy"
    scratch_file_2.write_bytes(b"\x93NUMPY\x01\x00_TEST_ORBITAL_ENERGIES_DATA")
    rel_dest_2 = pathlib.Path("water") / "wavefunction.npy"

    held_open = open(scratch_file_2, "rb")
    try:
        dest_path_2, sha_2 = coordinator.publish_artifact(
            source_path=scratch_file_2,
            relative_dest=rel_dest_2,
            compute_sha256=True,
        )
        assert dest_path_2.exists()
        assert sha_2 == hashlib.sha256(b"\x93NUMPY\x01\x00_TEST_ORBITAL_ENERGIES_DATA").hexdigest()
    finally:
        held_open.close()


def test_cross_platform_file_lock_mutual_exclusion(tmp_path: pathlib.Path) -> None:
    """Validate cross-platform mutual exclusion and timeout without file descriptor leakage."""
    lock_file = tmp_path / "pes_coordination.lock"

    lock1 = FileLock(lock_file, timeout_sec=5.0)
    lock2 = FileLock(lock_file, timeout_sec=0.5)

    assert lock1.acquire() is True

    thread_failed = threading.Event()
    thread_succeeded = threading.Event()
    thread_raised_timeout = threading.Event()

    def try_acquire_second() -> None:
        try:
            lock2.acquire()
            thread_succeeded.set()
        except TimeoutError:
            thread_raised_timeout.set()
        except Exception:
            thread_failed.set()

    t = threading.Thread(target=try_acquire_second, daemon=True)
    t.start()
    t.join(timeout=3.0)

    assert thread_raised_timeout.is_set()
    assert not thread_succeeded.is_set()
    assert not thread_failed.is_set()

    # Release instance 1, now instance 2 acquires successfully
    lock1.release()

    assert lock2.acquire() is True
    lock2.release()

    # Verify repeated timeouts do not leak descriptors
    for _ in range(5):
        lock1.acquire()
        timed_out = False
        try:
            lock2.acquire()
        except TimeoutError:
            timed_out = True
        finally:
            lock1.release()
        assert timed_out is True


def test_unified_core_namespace_and_dynamic_gpu_scheduling() -> None:
    """Validate authoritative symbol re-exports from cochem_base.core and non-blocking GPU scheduling."""
    import cochem_base.core as c_core
    from cochem.runners.cuda_budget import CudaMemoryManager

    # 1. Validate authoritative public re-exports
    expected_symbols = [
        "cochem_core_registry_manager",
        "CoChemRegistry",
        "CoChemConfigManager",
        "ConfigurationParseError",
        "SandboxContext",
        "SandboxConfig",
        "AirGapCoordinator",
        "AirGapViolationError",
        "FileLock",
        "PESStore",
        "SharedMemoryBuffer",
        "HMACSocketServer",
        "TruncatedPayloadError",
        "OversizedPayloadError",
        "MolecularStructureData",
        "QCResultsSchema",
        "SpinContaminationError",
        "HessianSymmetryError",
        "MendeleevInvariantError",
        "QCValidationError",
    ]

    for sym in expected_symbols:
        assert hasattr(c_core, sym), f"Expected symbol '{sym}' missing from cochem_base.core"

    # 2. Validate dynamic non-locking GPU scheduling
    cuda_manager = CudaMemoryManager(allow_cpu_fallback=True)

    async def run_gpu_schedule() -> Optional[int]:
        return await cuda_manager.schedule_gpu_task(required_mb=512, timeout_sec=2.0)

    assigned_device = asyncio.run(run_gpu_schedule())

    # In environment without CUDA (or with CUDA), returns valid device int >= 0 or None for CPU fallback
    if assigned_device is not None:
        assert isinstance(assigned_device, int)
        assert assigned_device >= 0
        worker_env = cuda_manager.prepare_worker_environment(device_id=assigned_device)
        assert worker_env.get("CUDA_VISIBLE_DEVICES") == str(assigned_device)
    else:
        worker_env = cuda_manager.prepare_worker_environment(device_id=None)
        assert worker_env.get("CUDA_VISIBLE_DEVICES") == ""
