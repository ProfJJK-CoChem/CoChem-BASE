"""Physical integration and compliance test suite for CoChem-BASE HPC & Scaling Part 1.

Verifies end-to-end integration across CUDA budgeting, Slurm preflight generation,
multi-node MPI supervision, tripartite air-gapped storage, SWMR HDF5 telemetry,
dynamic atomic constants via Mendeleev, and strict AST Zero-Mock compliance.
"""

import asyncio
import sys
from pathlib import Path
from typing import List

import h5py
import mendeleev
import pytest
from pydantic import ValidationError

from src.cochem.hpc.models import (
    CudaMemoryExhaustionError,
    CudaResourceBudget,
    MpiClusterExecutionConfig,
    MpiProcessSupervisorError,
    SlurmJobDirectiveSpec,
)
from src.cochem.hpc.slurm_generator import SlurmDryRunGenerator
from src.cochem.runners.async_process_runner import AsyncProcessRunner
from src.cochem.runners.cuda_budget import CudaMemoryManager
from src.cochem.runners.mpi_supervisor import MpiProcessSupervisor


def test_models_constraints_and_immutability() -> None:
    """Verify HPC data models enforce immutability, walltime regex, and bounds."""
    # Test valid models
    spec = SlurmJobDirectiveSpec(
        job_name="orca_prod_job",
        partition="standard",
        nodes=2,
        ntasks_per_node=4,
        cpus_per_task=2,
        walltime_str="06:30:00",
        memory_per_node_mb=65536,
        scratch_dir="/scratch/chem/job_prod",
        artifact_dir="/artifacts/chem/job_prod",
    )
    assert spec.job_name == "orca_prod_job"

    # Verify immutability
    with pytest.raises(ValidationError):
        spec.nodes = 4  # type: ignore

    # Verify walltime regex validation
    with pytest.raises(ValidationError):
        SlurmJobDirectiveSpec(
            job_name="invalid_time_job",
            partition="standard",
            walltime_str="bad_walltime",
            memory_per_node_mb=8192,
            scratch_dir="/scratch/job",
            artifact_dir="/artifacts/job",
        )

    # Verify budget calculations
    budget = CudaResourceBudget(
        device_id=0,
        total_vram_mb=32768,
        free_vram_mb=24576,
        reserved_headroom_mb=1024,
        fractional_limit=0.85,
    )
    expected_available = int((24576 - 1024) * 0.85)
    assert budget.available_vram_mb == expected_available


def test_cuda_budget_physical_query_and_backpressure() -> None:
    """Verify physical hardware VRAM query or CPU fallback and backpressure timeouts."""
    mgr = CudaMemoryManager()
    count = mgr.get_device_count()
    assert count >= 0

    env = mgr.prepare_worker_environment(device_id=1)
    assert env["CUDA_VISIBLE_DEVICES"] == "1"
    assert env["PYTORCH_CUDA_ALLOC_CONF"] == "expandable_segments:True"

    async def _test_backpressure() -> None:
        with pytest.raises(CudaMemoryExhaustionError):
            await mgr.acquire_vram_budget(
                device_id=0,
                required_mb=50_000_000,
                timeout_seconds=0.25,
                poll_interval=0.05,
            )

    asyncio.run(_test_backpressure())


def test_slurm_generator_orca_maxcore_and_staging() -> None:
    """Verify exact ORCA %maxcore calculations and tripartite staging directives."""
    spec = SlurmJobDirectiveSpec(
        job_name="orca_scaling_run",
        partition="chem_cluster",
        nodes=1,
        ntasks_per_node=4,
        cpus_per_task=2,
        walltime_str="12:00:00",
        memory_per_node_mb=32768,
        scratch_dir="/tmpfs/scratch/job_01",
        artifact_dir="/vault/artifacts/job_01",
    )
    generator = SlurmDryRunGenerator()
    result = generator.generate_sbatch_script(spec, solver="orca", input_filename="system.inp")

    assert result.is_valid is True
    # floor((32768 * 0.75) / 4) = floor(24576 / 4) = 6144
    assert result.orca_maxcore_mb == 6144
    assert result.estimated_memory_per_rank_mb == 8192

    content = result.generated_script_content
    assert "#SBATCH --job-name=orca_scaling_run" in content
    assert "#SBATCH --partition=chem_cluster" in content
    assert "#SBATCH --mem=32768M" in content
    assert "COCH_SCRATCH=\"/tmpfs/scratch/job_01\"" in content
    assert "COCH_ARTIFACTS=\"/vault/artifacts/job_01\"" in content
    assert "orca system.inp > orca_output.out" in content


def test_mpi_supervisor_commands_and_execution(tmp_path: Path) -> None:
    """Verify MPI launcher command generation, stream multiplexing, and process tree termination."""
    supervisor = MpiProcessSupervisor(grace_period_seconds=1.0)

    # Command generation check
    for launcher in ("srun", "mpirun", "mpiexec"):
        cfg = MpiClusterExecutionConfig(launcher=launcher, n_nodes=2, n_tasks_per_node=4, cpus_per_task=1)
        cmd = supervisor.build_mpi_command(cfg, ["xtb", "coord.xyz"])
        assert cmd[0] == launcher
        assert "coord.xyz" in cmd

    async def _test_supervisor_execution() -> None:
        telemetry_logs: List[str] = []
        rank_traces: List[str] = []

        py_script = (
            "import sys\n"
            "print('[0] Initializing electronic structure iteration 0', flush=True)\n"
            "print('[1] Node rank 1 memory synchronized', flush=True)\n"
            "print('Non-prefixed standard convergence log', flush=True)\n"
        )
        res = await supervisor.run_command(
            command=[sys.executable, "-c", py_script],
            cwd=tmp_path,
            timeout_seconds=5.0,
            telemetry_callback=lambda msg: telemetry_logs.append(msg),
            rank_trace_callback=lambda msg: rank_traces.append(msg),
        )
        assert res["exit_code"] == 0
        assert any("iteration 0" in m for m in telemetry_logs)
        assert any("convergence log" in m for m in telemetry_logs)
        assert any("rank 1 memory" in m for m in rank_traces)

        # Timeout termination
        hang_script = "import time\ntime.sleep(20.0)\n"
        with pytest.raises(MpiProcessSupervisorError):
            await supervisor.run_command(
                command=[sys.executable, "-c", hang_script],
                cwd=tmp_path,
                timeout_seconds=0.4,
            )

    asyncio.run(_test_supervisor_execution())


def test_async_process_runner_tripartite_and_swmr_telemetry(tmp_path: Path) -> None:
    """Verify tripartite storage air-gap protection, SWMR HDF5 telemetry, and Mendeleev constants."""
    src_dir = tmp_path / "app_src"
    artifacts_dir = tmp_path / "artifacts_vault"
    scratch_dir = tmp_path / "job_scratch"

    src_dir.mkdir(parents=True)
    artifacts_dir.mkdir(parents=True)
    scratch_dir.mkdir(parents=True)

    # Verify Mendeleev dynamic retrieval
    c_elem = mendeleev.element("C")
    o_elem = mendeleev.element("O")
    assert abs(c_elem.atomic_weight - 12.011) < 0.01
    assert abs(o_elem.atomic_weight - 15.999) < 0.01

    runner = AsyncProcessRunner(
        src_dir=src_dir,
        artifacts_dir=artifacts_dir,
        scratch_dir=scratch_dir,
    )

    # 1. Tripartite read-only protection
    with pytest.raises(PermissionError):
        runner.validate_write_path(src_dir / "unauthorized_log.txt")

    # 2. SWMR HDF5 Telemetry
    telemetry_file = scratch_dir / "integration_telemetry.h5"
    runner.init_telemetry(telemetry_file)

    runner.record_telemetry_metric(telemetry_file, step=1, energy=-152.887, walltime=0.12)
    runner.record_telemetry_metric(telemetry_file, step=2, energy=-152.934, walltime=0.25)

    with h5py.File(telemetry_file, "r", swmr=True, libver="latest") as reader:
        energies = reader["telemetry/energy"][:]
        steps = reader["telemetry/step"][:]
        assert len(steps) == 2
        assert abs(energies[1] - (-152.934)) < 1e-4

    # 3. Full dispatch lifecycle
    async def _test_dispatch() -> None:
        worker_code = (
            "import sys\n"
            "print('Authentic compute kernel completed successfully', flush=True)\n"
        )
        dispatch_res = await runner.dispatch_task(
            task_name="integrated_scf",
            binary_args=[sys.executable, "-c", worker_code],
            cleanup_on_completion=False,
        )
        assert dispatch_res["exit_code"] == 0
        assert "Authentic compute kernel" in dispatch_res["stdout"]
        assert Path(dispatch_res["telemetry_file"]).exists()
        runner.cleanup_scratch("integrated_scf")
        assert not Path(dispatch_res["telemetry_file"]).exists()

    asyncio.run(_test_dispatch())


def test_zero_mock_compliance_ast_audit() -> None:
    """AST audit across all production and test files for this chunk certifying compliance."""
    from ci_tools.anti_spoof_linter import check_file

    repo_root = Path(__file__).resolve().parent.parent.parent
    total_violations: List[str] = []

    target_files = [
        "src/cochem/hpc/models.py",
        "src/cochem/runners/cuda_budget.py",
        "src/cochem/hpc/slurm_generator.py",
        "src/cochem/runners/mpi_supervisor.py",
        "src/cochem/runners/async_process_runner.py",
        "tests/hpc/test_models.py",
        "tests/runners/test_cuda_budget.py",
        "tests/hpc/test_slurm_generator.py",
        "tests/runners/test_mpi_supervisor.py",
        "tests/runners/test_async_process_runner.py",
        "tests/integration/test_base_hpc_scaling_part1.py",
    ]

    for rel_path in target_files:
        full_path = repo_root / rel_path
        assert full_path.is_file(), f"Target file '{rel_path}' does not exist!"

        violations = check_file(full_path, repo_root, amnesty_set=set())
        for v in violations:
            total_violations.append(f"{v.file_path}:{v.line} [{v.category}] {v.message}")

    assert len(total_violations) == 0, (
        f"Zero-stub compliance violations detected ({len(total_violations)}):\n"
        + "\n".join(total_violations)
    )
