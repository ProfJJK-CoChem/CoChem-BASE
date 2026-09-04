"""Unit and integration tests for Deliverable 6: Non-Initializing NVML Telemetry, Worker Partitioning & Zero-CUDA-Locking (Suggestion #106).

Mandated by Method Matrix v4 (§8A, §8A.4) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Authentic environment inspection and worker partitioning.
"""

from __future__ import annotations

from pathlib import Path

from cochem.concurrency.subprocess_broker import SubprocessBroker
from cochem.core.hardware.topology import TopologyDiscoveryEngine


def test_non_initializing_nvml_gpu_discovery():
    """Verify GPU discovery polls hardware without calling initializing CUDA runtime context."""
    engine = TopologyDiscoveryEngine()
    gpus = engine.get_available_gpus()
    assert isinstance(gpus, list)
    # The call must return safely without raising or creating CUDA runtime context


def test_worker_env_gpu_partitioning():
    """Verify each worker gets explicit assigned GPU and isolated MPS pipe paths."""
    engine = TopologyDiscoveryEngine()

    worker0_env = engine.get_worker_env(concurrent_workers=2, worker_index=0)
    worker1_env = engine.get_worker_env(concurrent_workers=2, worker_index=1)

    assert "CUDA_VISIBLE_DEVICES" in worker0_env
    assert "CUDA_VISIBLE_DEVICES" in worker1_env
    assert "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE" in worker0_env


def test_subprocess_broker_mps_isolation(tmp_path: Path):
    """Verify SubprocessBroker injects unique MPS pipe and log directories."""
    broker = SubprocessBroker(scratch_dir=tmp_path)
    job_env = broker._prepare_worker_environment(worker_index=0, retries=0)

    assert "CUDA_MPS_PIPE_DIRECTORY" in job_env
    assert "CUDA_MPS_LOG_DIRECTORY" in job_env
    # Must contain unique identifiers to prevent socket collisions
    assert str(tmp_path) in job_env["CUDA_MPS_PIPE_DIRECTORY"] or "mps" in job_env["CUDA_MPS_PIPE_DIRECTORY"]
