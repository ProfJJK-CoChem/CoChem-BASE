from cochem.core.hardware.topology import HardwareTopology, TopologyDiscoveryEngine


def test_discover_p_e_cores_basic():
    engine = TopologyDiscoveryEngine()
    p_cores, e_cores = engine.discover_p_e_cores()
    assert p_cores >= 1
    assert e_cores >= 0

def test_resolve_resource_ceiling_slurm_override():
    import os
    engine = TopologyDiscoveryEngine()
    old_val = os.environ.get("SLURM_CPUS_PER_TASK")
    os.environ["SLURM_CPUS_PER_TASK"] = "8"
    try:
        ceiling = engine.resolve_resource_ceiling()
        assert ceiling == 8
    finally:
        if old_val is None:
            os.environ.pop("SLURM_CPUS_PER_TASK", None)
        else:
            os.environ["SLURM_CPUS_PER_TASK"] = old_val

def test_scout_and_anchor_partitioning():
    engine = TopologyDiscoveryEngine()
    topo = engine.discover_topology(concurrent_workers=2)
    assert isinstance(topo, HardwareTopology)
    assert topo.scout_cores == 1
    if topo.p_cores > 2:
        assert topo.anchor_cores == topo.p_cores - 1
    elif topo.p_cores == 2:
        assert topo.anchor_cores == 1
    else:
        assert topo.anchor_cores == 0

    assert "OMP_NUM_THREADS" in topo.environment_variables
    assert "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE" in topo.environment_variables

def test_worker_env_generation():
    engine = TopologyDiscoveryEngine()
    env = engine.get_worker_env(concurrent_workers=2, worker_index=0)
    assert "OMP_NUM_THREADS" in env
    assert int(env["OMP_NUM_THREADS"]) >= 1
    assert "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE" in env
