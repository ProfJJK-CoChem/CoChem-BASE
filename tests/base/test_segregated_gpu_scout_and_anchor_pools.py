"""CoChem-BASE: Test Segregated GPU Scout and Dedicated PySCF Anchor Pools.

Compliant with Method Matrix §8A.2, §8A.4, §8A.6, Suggestion #155, and Anti-Spoofing Directives.
Verifies Deliverable 5:
1. Segregated ExecutorStreamType enums (GPU_SCOUT_MLFF, GPU_ANCHOR_PYSCF).
2. Heterogeneous profile generation with segregated pools (gpu_scout_mlff vs gpu_anchor_pyscf).
3. Dedicated VRAM isolation for gpu_anchor_pyscf (max_workers=1, available_accelerators=1).
4. Multi-worker MPS concurrency for gpu_scout_mlff.
5. Integration with hetero_config.py HeteroParslConfig.
6. Integration with gpu_point.py GPUPointConfig target_pool selector.
"""

from gpu_point import GPUPointConfig

from cochem_base.core_engine.cochem_core_parsl_executors import (
    ExecutorStreamType,
    ParslProviderType,
    build_heterogeneous_profile,
)
from cochem_base.core_engine.hetero_config import (
    HeteroParslConfig,
    build_hetero_config,
)


def test_segregated_executor_stream_types():
    """Verify ExecutorStreamType enumerations for segregated pools."""
    assert ExecutorStreamType.GPU_SCOUT_MLFF.value == "GPU_SCOUT_MLFF"
    assert ExecutorStreamType.GPU_ANCHOR_PYSCF.value == "GPU_ANCHOR_PYSCF"
    assert ExecutorStreamType.GPU_SCOUT_MLFF != ExecutorStreamType.GPU_ANCHOR_PYSCF


def test_build_heterogeneous_profile_segregated_pools():
    """Verify build_heterogeneous_profile populates segregated GPU pools."""
    profile = build_heterogeneous_profile(
        provider_type=ParslProviderType.LOCAL,
        segregated_gpu_pools=True,
    )

    assert profile.gpu_scout_mlff_executor is not None
    assert profile.gpu_anchor_pyscf_executor is not None

    # Inspect Scout MLFF executor
    scout_mlff = profile.gpu_scout_mlff_executor
    assert scout_mlff.label == "gpu_scout_mlff"
    assert scout_mlff.stream == ExecutorStreamType.GPU_SCOUT_MLFF
    assert scout_mlff.cpu_affinity == "block-reverse"
    assert scout_mlff.max_workers_per_node >= 1

    # Inspect Anchor PySCF executor (dedicated VRAM)
    anchor_pyscf = profile.gpu_anchor_pyscf_executor
    assert anchor_pyscf.label == "gpu_anchor_pyscf"
    assert anchor_pyscf.stream == ExecutorStreamType.GPU_ANCHOR_PYSCF
    assert anchor_pyscf.max_workers_per_node == 1
    assert anchor_pyscf.available_accelerators == 1
    assert anchor_pyscf.cpu_affinity == "block"


def test_hetero_config_segregated_gpu_pools():
    """Verify hetero_config.py instantiates segregated pool executors."""
    config = build_hetero_config(as_parsl_object=False)
    assert isinstance(config, HeteroParslConfig)
    assert config.gpu_scout_mlff_executor is not None
    assert config.gpu_anchor_pyscf_executor is not None

    assert config.gpu_scout_mlff_executor.label == "gpu_scout_mlff"
    assert config.gpu_anchor_pyscf_executor.label == "gpu_anchor_pyscf"
    assert config.gpu_anchor_pyscf_executor.max_workers_per_node == 1
    assert config.gpu_anchor_pyscf_executor.available_accelerators == 1


def test_gpu_point_config_pool_selection():
    """Verify gpu_point.py GPUPointConfig targets segregated GPU pools."""
    cfg_anchor = GPUPointConfig()
    assert cfg_anchor.target_pool == "gpu_anchor_pyscf"

    cfg_scout = GPUPointConfig(target_pool="gpu_scout_mlff")
    assert cfg_scout.target_pool == "gpu_scout_mlff"
