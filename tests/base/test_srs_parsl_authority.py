"""Dispatch authority exercised with real Parsl executors and child processes."""

import json
from pathlib import Path
import sys

import parsl
from parsl.config import Config
from parsl.dataflow.dflow import DataFlowKernel
from parsl.executors.threads import ThreadPoolExecutor
import pytest

from cochem_base.calc.cochem_calc_execution_router import (
    ExecutionRouter,
    RegistryAuthorityViolationError,
)
from cochem_base.schemas import JobRouteConfig


def _config(tmp_path: Path, labels: tuple[str, ...]) -> Config:
    return Config(
        executors=[ThreadPoolExecutor(label=label, max_threads=1) for label in labels],
        run_dir=str(tmp_path / "parsl-runs"),
        strategy=None,
        retries=0,
        usage_tracking=0,
        initialize_logging=False,
    )


@pytest.fixture
def parsl_registry(audited_registry):
    data = json.loads(audited_registry.read_text(encoding="utf-8"))
    data["execution"]["default_engine"] = "parsl"
    audited_registry.write_text(json.dumps(data), encoding="utf-8")
    return audited_registry


@pytest.fixture
def execution_kernel(tmp_path):
    kernel = DataFlowKernel(_config(tmp_path, ("cochem_anchor_cpu", "cochem_scout_gpu")))
    try:
        yield kernel
    finally:
        kernel.cleanup()


@pytest.mark.parametrize("job_type,executor", [
    ("heavy_qm_opt", "cochem_anchor_cpu"),
    ("frequency", "cochem_anchor_cpu"),
    ("single_point", "cochem_anchor_cpu"),
    ("fast_potential_scan", "cochem_scout_gpu"),
])
def test_explicit_dfk_uses_requested_pool_and_actual_working_directory(
    parsl_registry, execution_kernel, tmp_path, job_type, executor,
):
    result = ExecutionRouter(parsl_registry, dfk=execution_kernel).route_job(
        job_type=job_type,
        payload_command=[
            sys.executable, "-c",
            "from pathlib import Path; Path('working-directory.txt').write_text(str(Path.cwd()))",
        ],
        scratch_dir=tmp_path / "scratch",
    )
    assert result.status == "SUBMITTED"
    assert result.assigned_executor == executor
    assert result.future.result(timeout=30) == 0
    assert result.future.task_record["executor"] == executor
    assert result.future.task_record["dfk"] is execution_kernel
    directory = Path(result.scratch_dir)
    assert Path((directory / "working-directory.txt").read_text()) == directory


def test_real_child_failure_reaches_parsl_future(parsl_registry, execution_kernel, tmp_path):
    result = ExecutionRouter(parsl_registry, dfk=execution_kernel).route_job(
        job_type="heavy_qm_opt",
        payload_command=[sys.executable, "-c", "import sys; print('physical failure',file=sys.stderr); sys.exit(7)"],
        scratch_dir=tmp_path / "scratch",
    )
    with pytest.raises(RuntimeError, match="exit 7.*physical failure"):
        result.future.result(timeout=30)
    assert result.future.exception() is not None


def test_missing_pool_never_routes_to_another_executor(parsl_registry, tmp_path):
    kernel = DataFlowKernel(_config(tmp_path, ("cochem_anchor_cpu",)))
    try:
        with pytest.raises(RegistryAuthorityViolationError, match="absent"):
            ExecutionRouter(parsl_registry, dfk=kernel).route_job(
                job_type="fast_potential_scan",
                payload_command=[sys.executable, "-c", "raise SystemExit(0)"],
                scratch_dir=tmp_path / "scratch",
            )
    finally:
        kernel.cleanup()


def test_explicit_local_registry_rejects_supplied_dfk(audited_registry, execution_kernel, tmp_path):
    with pytest.raises(RegistryAuthorityViolationError, match="local|Parsl|DFK"):
        ExecutionRouter(audited_registry, dfk=execution_kernel).route_job(
            payload_command=[sys.executable, "-c", "print('local')"],
            scratch_dir=tmp_path / "scratch",
        )


def test_global_parsl_kernel_cannot_override_local_registry(audited_registry, tmp_path):
    kernel = parsl.load(_config(tmp_path, ("cochem_anchor_cpu", "cochem_scout_gpu")))
    try:
        result = ExecutionRouter(audited_registry).route_job(
            payload_command=[sys.executable, "-c", "print('local')"],
            scratch_dir=tmp_path / "scratch",
        )
        assert result.status == "COMPLETED"
        assert result.assigned_executor == "local_fallback"
        assert result.future is None
        assert result.output.strip() == "local"
    finally:
        kernel.cleanup()
        parsl.clear()


def test_explicit_job_config_cannot_route_frequency_to_scout(parsl_registry, execution_kernel, tmp_path):
    route = JobRouteConfig(
        job_type="frequency", assigned_executor="cochem_scout_gpu",
        scratch_dir=str(tmp_path / "scratch"),
    )
    with pytest.raises(ValueError, match="requires"):
        ExecutionRouter(parsl_registry, dfk=execution_kernel).route_job(
            job_type="frequency", route_config=route,
            payload_command=[sys.executable, "-c", "print('frequency')"],
        )
