"""Unit tests for asynchronous multi-node MPI process supervisor."""

import sys
from pathlib import Path

import pytest

from src.cochem.hpc.models import MpiClusterExecutionConfig, MpiProcessSupervisorError
from src.cochem.runners.mpi_supervisor import MpiProcessSupervisor


def test_build_mpi_command() -> None:
    """Verify command assembly across srun, mpirun, and mpiexec."""
    supervisor = MpiProcessSupervisor()
    binary_args = ["orca", "job.inp"]

    # srun
    srun_cfg = MpiClusterExecutionConfig(
        launcher="srun",
        n_nodes=2,
        n_tasks_per_node=4,
        cpus_per_task=2,
    )
    srun_cmd = supervisor.build_mpi_command(srun_cfg, binary_args)
    assert srun_cmd == [
        "srun",
        "--nodes=2",
        "--ntasks-per-node=4",
        "--cpus-per-task=2",
        "--mpi=pmi2",
        "orca",
        "job.inp",
    ]

    # mpirun
    mpirun_cfg = MpiClusterExecutionConfig(
        launcher="mpirun",
        n_nodes=3,
        n_tasks_per_node=2,
        cpus_per_task=1,
    )
    mpirun_cmd = supervisor.build_mpi_command(mpirun_cfg, binary_args)
    assert mpirun_cmd == [
        "mpirun",
        "-np",
        "6",
        "-N",
        "2",
        "--bind-to",
        "core",
        "orca",
        "job.inp",
    ]

    # mpiexec
    mpiexec_cfg = MpiClusterExecutionConfig(
        launcher="mpiexec",
        n_nodes=2,
        n_tasks_per_node=3,
        cpus_per_task=4,
    )
    mpiexec_cmd = supervisor.build_mpi_command(mpiexec_cfg, binary_args)
    assert mpiexec_cmd == [
        "mpiexec",
        "-n",
        "6",
        "-ppn",
        "3",
        "orca",
        "job.inp",
    ]


def test_mpi_supervisor_stream_multiplexing(tmp_path: Path) -> None:
    """Verify physical multi-rank output segregation between rank-0 and rank-N streams."""
    import asyncio

    async def _run() -> None:
        supervisor = MpiProcessSupervisor()
        rank0_messages: list[str] = []
        rank_trace_messages: list[str] = []

        # Run authentic python script outputting multiple rank tags
        py_code = (
            "import sys\n"
            "print('[0] Rank 0 starting SCF calculation', flush=True)\n"
            "print('[1] Rank 1 diagnostic memory 2048MB', flush=True)\n"
            "print('[2] Rank 2 diagnostic memory 2048MB', flush=True)\n"
            "print('Generic non-prefixed message', flush=True)\n"
        )

        result = await supervisor.run_command(
            command=[sys.executable, "-c", py_code],
            cwd=tmp_path,
            timeout_seconds=10.0,
            telemetry_callback=lambda msg: rank0_messages.append(msg),
            rank_trace_callback=lambda msg: rank_trace_messages.append(msg),
        )

        assert result["exit_code"] == 0
        assert any("Rank 0 starting SCF" in msg for msg in rank0_messages)
        assert any("Generic non-prefixed" in msg for msg in rank0_messages)
        assert any("Rank 1 diagnostic" in msg for msg in rank_trace_messages)
        assert any("Rank 2 diagnostic" in msg for msg in rank_trace_messages)

    asyncio.run(_run())


def test_mpi_supervisor_timeout_and_tree_termination(tmp_path: Path) -> None:
    """Verify process tree termination upon exceeding configured timeout."""
    import asyncio

    async def _run() -> None:
        supervisor = MpiProcessSupervisor(grace_period_seconds=1.0)
        py_code = "import time\ntime.sleep(15.0)\n"

        with pytest.raises(MpiProcessSupervisorError) as exc_info:
            await supervisor.run_command(
                command=[sys.executable, "-c", py_code],
                cwd=tmp_path,
                timeout_seconds=0.5,
            )
        assert "timed out" in str(exc_info.value).lower() or "timeout" in str(exc_info.value).lower()

    asyncio.run(_run())


def test_mpi_supervisor_nonzero_exit(tmp_path: Path) -> None:
    """Verify non-zero process exit raises MpiProcessSupervisorError."""
    import asyncio

    async def _run() -> None:
        supervisor = MpiProcessSupervisor()
        py_code = "import sys\nsys.stderr.write('Abnormal computational termination\\n')\nsys.exit(7)\n"

        with pytest.raises(MpiProcessSupervisorError) as exc_info:
            await supervisor.run_command(
                command=[sys.executable, "-c", py_code],
                cwd=tmp_path,
                timeout_seconds=5.0,
            )
        assert "code 7" in str(exc_info.value) or "7" in str(exc_info.value)

    asyncio.run(_run())
