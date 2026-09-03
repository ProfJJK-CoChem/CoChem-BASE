"""Unit tests for Hybrid Architecture Aware Thread & Core Tuner.
Strictly adheres to Zero-Mock mandate and physical OS topology discovery.
"""

import os

from cochem.core.hardware.topology import (
    HardwareTopology,
    TopologyDiscoveryEngine,
)


def test_topology_discovery_physical_detection() -> None:
    """Verify TopologyDiscoveryEngine detects genuine hardware cores."""
    engine = TopologyDiscoveryEngine()
    topo = engine.discover_topology()

    assert isinstance(topo, HardwareTopology)
    assert topo.total_logical_cpus >= 1
    assert topo.total_physical_cores >= 1
    assert topo.p_cores >= 1
    assert topo.resource_ceiling >= 1
    assert topo.scout_cores >= 1


def test_scout_and_anchor_budgeting() -> None:
    """Verify Scout-and-Anchor budgeting according to Method Matrix v4 §8A."""
    engine = TopologyDiscoveryEngine()
    topo = engine.discover_topology()

    # When physical cores > 2, 1 P-core dedicated to Scout, remainder to Anchor
    if topo.p_cores > 2:
        assert topo.scout_cores == 1
        assert topo.anchor_cores == topo.p_cores - 1
    else:
        assert topo.scout_cores == 1
        assert topo.anchor_cores >= 0

    # Verify thread environment variables
    env_vars = topo.environment_variables
    assert "OMP_NUM_THREADS" in env_vars
    assert "MKL_NUM_THREADS" in env_vars
    assert "OPENBLAS_NUM_THREADS" in env_vars
    assert "VECLIB_MAXIMUM_THREADS" in env_vars
    assert "NUMEXPR_NUM_THREADS" in env_vars

    threads_val = int(env_vars["OMP_NUM_THREADS"])
    assert threads_val >= 1


def test_gpu_mps_worker_ceiling() -> None:
    """Verify GPU MPS worker count is constrained to 2-4 processes."""
    engine = TopologyDiscoveryEngine()
    topo = engine.discover_topology()

    assert 2 <= topo.gpu_mps_workers <= 4


def test_get_worker_env_injection() -> None:
    """Verify get_worker_env injects thread budgeting into child environments."""
    engine = TopologyDiscoveryEngine()
    worker_env = engine.get_worker_env(extra_env={"ORCA_PATH": "/opt/orca"})

    assert "OMP_NUM_THREADS" in worker_env
    assert worker_env["ORCA_PATH"] == "/opt/orca"


def test_pin_scout_affinity_execution() -> None:
    """Verify pin_scout_affinity attempts OS binding without unhandled exceptions."""
    engine = TopologyDiscoveryEngine()
    result = engine.pin_scout_affinity(core_index=0)
    assert isinstance(result, bool)


def test_resource_ceiling_resolution_slurm_env() -> None:
    """Verify resource ceiling respects SLURM_CPUS_PER_TASK when present."""
    old_val = os.environ.get("SLURM_CPUS_PER_TASK")
    try:
        os.environ["SLURM_CPUS_PER_TASK"] = "4"
        engine = TopologyDiscoveryEngine()
        ceiling = engine.resolve_resource_ceiling()
        assert ceiling == 4
    finally:
        if old_val is not None:
            os.environ["SLURM_CPUS_PER_TASK"] = old_val
        else:
            os.environ.pop("SLURM_CPUS_PER_TASK", None)
