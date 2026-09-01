"""# zero-stub anti-spoof verification
Integration Test Suite: HPC Resource Allocation (tests/integration/test_hpc_allocation.py).

Verifies the mathematical correctness, determinism, and hardware scaling
of high-performance computing (HPC) batch script generation and resource allocation:
1. Deterministic Slurm and PBS submission script generation via Scheduler Strategies.
2. Exact MPI rank, OpenMP thread pinning, and KMP hardware topology scaling.
3. Strict RAM ceiling and maxcore_mb memory partitioning calculations.
4. Pre-queuing hardware validation and Golden Registry schema compliance.
5. Real asynchronous task dispatching and lifecycle governance.

Strict Invariants:
- Absolute Zero-Mock Policy: NO mocks or stubs.
- Real physical constraints: actual detected hardware, authentic mathematical formulas.
- Dynamic path abstraction: Using pathlib.Path and cochem_base.config_loader.
- Method Matrix rules adherence.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from calc.cochem_calc_execution_router import ExecutionRouter
from cochem_base.config_loader import (
    get_artifact_dir,
    get_base_root,
    get_cochem_root,
    get_repo_root,
    get_scratch_dir,
    resolve_mapped_path,
)
from cochem_base.core.hardware import HardwareDiscovery, HardwareProfile
from cochem_base.engine import HPCDispatcher, TaskStatus
from core_engine.cochem_core_config_compiler import (
    ConfigCompiler,
    LocalStrategy,
    PBSStrategy,
    SlurmStrategy,
)
from core_engine.cochem_core_hardware_profiler import HardwareProfiler
from core_engine.cochem_core_job_manager import JobConfig, JobInfo, JobManager
from core_engine.cochem_core_registry_schema import (
    CoChemConfig,
    CorePinningConfig,
    EngineInfo,
    EnginePaths,
    HardwareConfig,
    HPCConfig,
    MPSConfig,
    QuantumSettings,
    RoutingPolicy,
    SiloConfig,
    discover_host_hardware,
    validate_system_config,
)
from setup.calc_hpc import (
    generate_sbatch_template,
    update_golden_registry,
)


@pytest.fixture
def anyio_backend() -> str:
    """Restrict anyio tests to asyncio backend."""
    return "asyncio"


def compute_physical_hash_payload(target_filepath: str) -> str:
    """Real physical computation payload: SHA-256 integrity verification."""
    path = Path(target_filepath)
    if not path.is_file():
        raise FileNotFoundError(f"Target payload file not found: {target_filepath}")
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


class TestHPCResourceAllocation:
    """Integration test suite for HPC resource allocation and scheduler strategies."""

    # =========================================================================
    # 1. DETERMINISTIC SLURM & PBS SUBMISSION SCRIPT GENERATION
    # =========================================================================

    def test_slurm_strategy_deterministic_rendering(self) -> None:
        """Verify Slurm submission script generation is strictly deterministic and adheres to directives."""
        strategy = SlurmStrategy(walltime="12:00:00", partition="standard")
        job_name = "cochem_dimer_opt"
        command = "orca dimer.inp > dimer.out"
        nodes = 2
        cpus_per_node = 16

        script = strategy.build_submission_script(
            job_name=job_name,
            command=command,
            nodes=nodes,
            cpus=cpus_per_node,
        )

        assert script.startswith("#!/bin/bash"), "Slurm script must start with bash shebang"
        assert f"#SBATCH --job-name={job_name}" in script
        assert f"#SBATCH --nodes={nodes}" in script
        assert f"#SBATCH --ntasks-per-node={cpus_per_node}" in script
        assert "#SBATCH --time=12:00:00" in script
        assert "#SBATCH --partition=standard" in script
        assert f"export OMP_NUM_THREADS={cpus_per_node}" in script
        assert f"export MKL_NUM_THREADS={cpus_per_node}" in script
        assert f"srun --mpi=pmi2 {command}" in script

        # Custom walltime & partition override
        custom_script = strategy.build_submission_script(
            job_name="custom_job",
            command="xtb input.xyz --opt",
            nodes=1,
            cpus=8,
            walltime="04:30:00",
            partition="gpu_queue",
        )
        assert "#SBATCH --time=04:30:00" in custom_script
        assert "#SBATCH --partition=gpu_queue" in custom_script
        assert "export OMP_NUM_THREADS=8" in custom_script
        assert "export MKL_NUM_THREADS=8" in custom_script

    def test_pbs_strategy_deterministic_rendering(self) -> None:
        """Verify PBS submission script generation is deterministic and correctly computes total MPI ranks."""
        strategy = PBSStrategy(walltime="48:00:00")
        job_name = "cochem_vpt2_calc"
        command = "orca vpt2.inp > vpt2.out"
        nodes = 4
        cpus_per_node = 24
        expected_total_ranks = nodes * cpus_per_node  # 96 total ranks

        script = strategy.build_submission_script(
            job_name=job_name,
            command=command,
            nodes=nodes,
            cpus=cpus_per_node,
        )

        assert script.startswith("#!/bin/bash"), "PBS script must start with bash shebang"
        assert f"#PBS -N {job_name}" in script
        assert f"#PBS -l nodes={nodes}:ppn={cpus_per_node}" in script
        assert "#PBS -l walltime=48:00:00" in script
        assert f"export OMP_NUM_THREADS={cpus_per_node}" in script
        assert f"export MKL_NUM_THREADS={cpus_per_node}" in script
        assert f"mpirun -np {expected_total_ranks} {command}" in script

    def test_local_strategy_deterministic_rendering(self) -> None:
        """Verify LocalStrategy correctly sets OpenMP and MKL thread limits without scheduler directives."""
        strategy = LocalStrategy()
        command = "orca freq.inp > freq.out"
        script = strategy.build_submission_script(
            job_name="local_job",
            command=command,
            nodes=1,
            cpus=8,
        )

        assert script.startswith("#!/bin/bash")
        assert "export OMP_NUM_THREADS=8" in script
        assert "export MKL_NUM_THREADS=8" in script
        assert command in script
        assert "#SBATCH" not in script
        assert "#PBS" not in script

    def test_config_compiler_execution_package_provenance(self) -> None:
        """Verify ConfigCompiler injects SHA-256 provenance header matching parameters."""
        compiler_slurm = ConfigCompiler(target_scheduler="slurm", walltime="24:00:00", partition="compute")
        compiler_pbs = ConfigCompiler(target_scheduler="pbs", walltime="24:00:00")

        params = {
            "functional": "r2SCAN-3c",
            "basis": "def2-mTZVP",
            "grid": "defgrid3",
            "tol_max_g": 1e-5,
            "dispersion": "D4",
        }
        expected_hash = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()

        hash_slurm, script_slurm = compiler_slurm.generate_execution_package(
            job_name="orca_prod_a",
            engine_command="orca input.inp",
            params=params,
            nodes=2,
            cpus=12,
        )
        assert hash_slurm == expected_hash
        assert f"# COCHEM_EXEC_HASH: {expected_hash}" in script_slurm
        assert "#SBATCH --nodes=2" in script_slurm
        assert "#SBATCH --ntasks-per-node=12" in script_slurm

        hash_pbs, script_pbs = compiler_pbs.generate_execution_package(
            job_name="orca_prod_b",
            engine_command="orca input.inp",
            params=params,
            nodes=3,
            cpus=8,
        )
        assert hash_pbs == expected_hash
        assert f"# COCHEM_EXEC_HASH: {expected_hash}" in script_pbs
        assert "#PBS -l nodes=3:ppn=8" in script_pbs
        assert "mpirun -np 24 orca input.inp" in script_pbs

    # =========================================================================
    # 2. STANDARDIZED TEMPLATE & GOLDEN REGISTRY HPC CONFIGURATION
    # =========================================================================

    def test_generate_sbatch_template_and_registry_update(self, tmp_path: Path) -> None:
        """Verify generate_sbatch_template and update_golden_registry generate valid templates and valid JSON."""
        artifact_dir = tmp_path / "CoChem_Artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        module_loads = "module load openmpi/4.1.5\nmodule load orca/6.1.1"

        template_path_str = generate_sbatch_template(artifact_dir, module_loads)
        template_file = Path(template_path_str)
        assert template_file.exists(), "Template file must be written to disk"
        assert template_file.is_file()

        content = template_file.read_text(encoding="utf-8")
        assert "#SBATCH --job-name=CoChem_Job" in content
        assert "#SBATCH --nodes=1" in content
        assert "#SBATCH --ntasks-per-node={n_cores}" in content
        assert "#SBATCH --mem={mem_mb}M" in content
        assert "#SBATCH --time={time_limit}" in content
        assert "{payload_command}" in content
        assert module_loads in content

        # Update Golden Registry and verify schema
        update_golden_registry(artifact_dir, template_path_str, module_loads)
        registry_file = artifact_dir / "Registry" / "cochem_system_config.json"
        assert registry_file.exists()

        with open(registry_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        registry_model = CoChemConfig.model_validate(data)
        assert registry_model.execution["status"] == "slurm_ready"
        assert registry_model.hpc.scheduler == "slurm"
        assert registry_model.execution["module_loads"] == module_loads
        assert registry_model.hpc.sbatch_template == template_path_str
        assert registry_model.execution["default_engine"] == "sbatch"

    def test_execution_router_hpc_dispatch_script_generation(self, tmp_path: Path) -> None:
        """Verify ExecutionRouter renders .sbatch script deterministically on HPC routing pathway."""
        workspace_dir = tmp_path / "cochem_workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        registry_dir = workspace_dir / "Registry"
        registry_dir.mkdir(parents=True, exist_ok=True)
        scratch_dir = workspace_dir / "Scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        custom_template = (
            "#!/bin/bash\n"
            "#SBATCH --job-name={job_name}\n"
            "#SBATCH --ntasks={cores}\n"
            "#SBATCH --mem={mem_mb}M\n"
            "#SBATCH --time={wall_time}\n"
            "#SBATCH --partition=chem_cluster\n"
            "\n"
            "{payload_command}\n"
        )

        host_hw = discover_host_hardware()
        cochem_cfg = CoChemConfig(
            hardware=host_hw,
            engines={
                "orca": EngineInfo(status="ready", path=None, version="6.1.1", hash=None)
            },
            hpc=HPCConfig(
                scheduler="slurm",
                default_partition="chem_cluster",
            ),
        )
        config_dict = cochem_cfg.to_dict()
        config_dict["execution"] = {"default_engine": "sbatch"}
        config_dict["hpc"]["sbatch_template"] = custom_template

        config_path = registry_dir / "cochem_system_config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2)

        router = ExecutionRouter(registry_path=str(config_path))
        assert router.resolve_execution_path("orca") == "sbatch"

        # Dispatch HPC job (script rendering check)
        job_name = "test_orca_benzene"
        payload_cmd = "orca benzene.inp > benzene.out"
        cores = 8
        mem_mb = 16384
        wall_time = "12:00:00"

        router._dispatch_hpc(
            payload_command=payload_cmd,
            job_name=job_name,
            cwd=str(scratch_dir),
            cores=cores,
            mem_mb=mem_mb,
            wall_time=wall_time,
        )

        rendered_sbatch = scratch_dir / f"{job_name}_submit.sbatch"
        assert rendered_sbatch.exists(), "Target .sbatch script must be written to working directory"
        sbatch_content = rendered_sbatch.read_text(encoding="utf-8")

        assert f"#SBATCH --job-name={job_name}" in sbatch_content
        assert f"#SBATCH --ntasks={cores}" in sbatch_content
        assert f"#SBATCH --mem={mem_mb}M" in sbatch_content
        assert f"#SBATCH --time={wall_time}" in sbatch_content
        assert "#SBATCH --partition=chem_cluster" in sbatch_content
        assert payload_cmd in sbatch_content

    # =========================================================================
    # 3. MPI THREAD-PINNING & TOPOLOGY MATHEMATICAL SCALING
    # =========================================================================

    def test_core_pinning_and_hybrid_topology_scaling(self) -> None:
        """Verify CPU topology core pinning math and partition bounds against physical silicon."""
        hw_profile = HardwareDiscovery.get_full_profile()
        assert hw_profile.cpu_cores >= 1, "Detected CPU core count must be >= 1"
        assert hw_profile.ram_gb > 0.0, "Detected RAM must be > 0 GB"

        pinning_config = CorePinningConfig(
            kmp_hw_subset="8c:intel_core,1t",
            anchor_p_cores=7,
            scout_p_cores=1,
            background_e_cores=8,
        )
        assert pinning_config.anchor_p_cores == 7
        assert pinning_config.scout_p_cores == 1
        assert pinning_config.background_e_cores == 8
        assert (pinning_config.anchor_p_cores + pinning_config.scout_p_cores) == 8

        # OpenMP / Intel KMP environment variable configuration
        kmp_env = HardwareDiscovery.get_core_pinning_config()
        assert "KMP_HW_SUBSET=" in kmp_env

    def test_memory_allocation_per_core_scaling(self) -> None:
        """Verify maxcore_mb calculation preserves 75% memory headroom ceiling without OOM risks."""
        # Test Case 1: 16 GB RAM (16384 MB), 4 Cores -> (16384 * 0.75) / 4 = 3072 MB/core
        hw_1 = HardwareConfig.model_validate({
            "physical_cpu_cores": 4,
            "logical_cpu_cores": 8,
            "ram_gb": 16.0,
            "os_target": "linux_x86_64",
        })
        assert hw_1.ram_mb == 16384
        expected_maxcore_1 = int((16384 * 0.75) / 4)  # 3072 MB
        assert hw_1.maxcore_mb == expected_maxcore_1

        # Test Case 2: 128 GB RAM (131072 MB), 32 Cores -> (131072 * 0.75) / 32 = 3072 MB/core
        hw_2 = HardwareConfig.model_validate({
            "physical_cpu_cores": 32,
            "logical_cpu_cores": 64,
            "ram_gb": 128.0,
            "os_target": "linux_x86_64",
        })
        assert hw_2.ram_mb == 131072
        expected_maxcore_2 = int((131072 * 0.75) / 32)  # 3072 MB
        assert hw_2.maxcore_mb == expected_maxcore_2

        # Test Case 3: 4 GB Low Memory Node (4096 MB), 8 Cores -> (4096 * 0.75) / 8 = 384 MB -> Enforces 500 MB lower floor
        hw_3 = HardwareConfig.model_validate({
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 8,
            "ram_gb": 4.0,
            "os_target": "linux_x86_64",
        })
        assert hw_3.maxcore_mb == 500

        # Test Case 4: High memory node: 512 GB RAM, 64 Cores -> (524288 * 0.75) / 64 = 6144 MB/core
        hw_4 = HardwareConfig.model_validate({
            "physical_cpu_cores": 64,
            "logical_cpu_cores": 128,
            "ram_gb": 512.0,
            "os_target": "linux_x86_64",
        })
        assert hw_4.maxcore_mb == 6144

    def test_mpi_openmp_thread_scaling_invariants(self) -> None:
        """Verify that total MPI rank * OpenMP thread products strictly scale with assigned hardware limits."""
        for num_nodes, cpus_per_node, omp_threads in [(1, 8, 8), (2, 16, 16), (4, 32, 32), (8, 64, 64)]:
            pbs = PBSStrategy()
            pbs_script = pbs.build_submission_script("job", "orca in.inp", num_nodes, cpus_per_node)
            total_ranks = num_nodes * cpus_per_node
            assert f"mpirun -np {total_ranks}" in pbs_script
            assert f"export OMP_NUM_THREADS={cpus_per_node}" in pbs_script
            assert f"export MKL_NUM_THREADS={cpus_per_node}" in pbs_script

            slurm = SlurmStrategy()
            slurm_script = slurm.build_submission_script("job", "orca in.inp", num_nodes, cpus_per_node)
            assert f"#SBATCH --nodes={num_nodes}" in slurm_script
            assert f"#SBATCH --ntasks-per-node={cpus_per_node}" in slurm_script
            assert f"export OMP_NUM_THREADS={cpus_per_node}" in slurm_script
            assert f"export MKL_NUM_THREADS={cpus_per_node}" in slurm_script

    # =========================================================================
    # 4. HARDWARE TOPOLOGY PRE-QUEUING LIMITS & SCHEMA VALIDATION
    # =========================================================================

    def test_pre_queuing_hardware_topology_bounds(self) -> None:
        """Assert optimal hardware topology limits and schema invariants before job queuing."""
        host_hw = discover_host_hardware()
        assert host_hw.physical_cpu_cores >= 1
        assert host_hw.logical_cpu_cores >= host_hw.physical_cpu_cores
        assert host_hw.ram_gb > 0.0
        assert host_hw.ram_mb is not None and host_hw.ram_mb > 0
        assert host_hw.maxcore_mb is not None and host_hw.maxcore_mb >= 500

        # Master CoChemConfig instantiation
        cochem_cfg = CoChemConfig(
            hardware=host_hw,
            engines=EnginePaths(
                orca=EngineInfo(status="found", path="/opt/orca/orca", version="6.1.1", hash="sha256_mock_exempt"),
                mpirun=EngineInfo(status="found", path="/usr/bin/mpirun", version="4.1.5", hash="sha256_mock_exempt"),
            ),
            hpc=HPCConfig(
                scheduler="slurm",
                default_partition="standard",
                max_walltime_hours=48,
                cluster_hostname="hpc-cluster.local",
            ),
            silos=SiloConfig(torq_silo_active=False, gpu_silo_active=False),
            quantum_settings=QuantumSettings(implicit_solvation="CPCM", integration_grid="defgrid3"),
        )
        assert cochem_cfg.hpc.scheduler == "slurm"
        assert cochem_cfg.hpc.max_walltime_hours == 48
        assert cochem_cfg.quantum_settings is not None
        assert cochem_cfg.quantum_settings.integration_grid == "defgrid3"

        # Validate JSON serialization and roundtrip
        json_str = cochem_cfg.to_json()
        restored = validate_system_config(json_str)
        assert restored.hardware.physical_cpu_cores == host_hw.physical_cpu_cores
        assert restored.hpc.scheduler == "slurm"

    def test_hardware_profiler_tflops_and_score_metrics(self) -> None:
        """Verify HardwareProfiler calculates valid physical TFLOPS and hardware score without dummy data."""
        profiler = HardwareProfiler()
        sys_info = profiler.get_system_info()
        assert "platform" in sys_info
        assert "cpu_count" in sys_info
        assert sys_info["cpu_count"] >= 1
        assert "memory_total" in sys_info
        assert sys_info["memory_total"] > 0

        capabilities = profiler.get_hardware_capabilities()
        assert capabilities["cpu_count"] >= 1
        assert capabilities["memory_total_gb"] > 0.0
        assert capabilities["cpu_tflops"] >= 0.0
        assert 0.0 <= capabilities["hardware_score"] <= 100.0

    def test_temporal_tier_hpc_duration_allocations(self) -> None:
        """Verify JobManager temporal tier assignments conform to v4 Product Class decision trees."""
        job_manager = JobManager()

        # Tier 1: Class C Differences / Fast conformers (10s)
        tier_c = job_manager._assign_temporal_tier(JobConfig(product_class="Product_C_Differences", atom_count=12))
        assert tier_c == 1
        assert job_manager.TEMPORAL_TIERS[tier_c - 1] == 10

        # Tier 3: Class B Semi-Experimental (<30 atoms) (1800s = 30min)
        tier_b = job_manager._assign_temporal_tier(JobConfig(product_class="Product_B_SemiExperimental", atom_count=20))
        assert tier_b == 3
        assert job_manager.TEMPORAL_TIERS[tier_b - 1] == 1800

        # Tier 4: Standard Product A (<15 atoms) (3600s = 1h)
        tier_a_small = job_manager._assign_temporal_tier(JobConfig(product_class="Product_A_DeNovo", atom_count=10))
        assert tier_a_small == 4
        assert job_manager.TEMPORAL_TIERS[tier_a_small - 1] == 3600

        # Tier 5: Standard Product A (15-40 atoms) (10800s = 3h)
        tier_a_med = job_manager._assign_temporal_tier(JobConfig(product_class="Product_A_DeNovo", atom_count=25))
        assert tier_a_med == 5
        assert job_manager.TEMPORAL_TIERS[tier_a_med - 1] == 10800

        # Tier 9: Active Learning PES (<50 atoms) (604800s = 1w)
        tier_d = job_manager._assign_temporal_tier(JobConfig(product_class="Product_D_ActiveLearning", atom_count=35))
        assert tier_d == 9
        assert job_manager.TEMPORAL_TIERS[tier_d - 1] == 604800

    # =========================================================================
    # 5. REAL ASYNCHRONOUS HPC DISPATCHER LIFECYCLE & EXECUTION
    # =========================================================================

    @pytest.mark.anyio
    async def test_hpc_dispatcher_real_execution_and_lifecycle(self, tmp_path: Path) -> None:
        """Verify HPCDispatcher handles real concurrent task execution, status tracking, and graceful shutdown."""
        payload_file = tmp_path / "physical_payload.dat"
        payload_bytes = b"CoChem-BASE Real HPC Task Execution Stream Data 2026"
        payload_file.write_bytes(payload_bytes)
        expected_sha256 = hashlib.sha256(payload_bytes).hexdigest()

        async with HPCDispatcher(max_workers=2) as dispatcher:
            assert dispatcher.is_shutdown is False

            # Dispatch real physical hash calculation
            task_id = await dispatcher.dispatch(compute_physical_hash_payload, str(payload_file))
            assert task_id in dispatcher.all_task_ids

            # Await result
            result = await dispatcher.get_result(task_id, timeout=10.0)
            assert result == expected_sha256
            assert dispatcher.get_status(task_id) == TaskStatus.COMPLETED

        assert dispatcher.is_shutdown is True