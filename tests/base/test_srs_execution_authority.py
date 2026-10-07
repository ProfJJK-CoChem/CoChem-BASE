"""Real local execution must preserve authority and never invent successful work."""

import json
import sys
from pathlib import Path

import pytest

from cochem_base.calc.cochem_calc_execution_router import (
    ExecutionRouter,
    RegistryAuthorityViolationError,
)
from cochem.core.context import AirGapViolationError


def test_missing_invalid_and_unaudited_registry_rejected(tmp_path):
    path = tmp_path / "registry.json"
    with pytest.raises(RegistryAuthorityViolationError):
        ExecutionRouter(path)
    for content in ("{", "{}", '{"hardware":{"ram_gb":16}}'):
        path.write_text(content, encoding="utf-8")
        with pytest.raises(RegistryAuthorityViolationError):
            ExecutionRouter(path)


def test_empty_payload_rejected_before_creating_task(audited_registry, tmp_path):
    router = ExecutionRouter(audited_registry)
    target = tmp_path / "scratch"
    for command in (None, "", [], [""]):
        with pytest.raises(ValueError, match="explicit nonempty"):
            router.route_job(payload_command=command, scratch_dir=target)
    assert not target.exists()


@pytest.mark.parametrize("physical,logical", [(1.5, 2), (3, 2), (True, 2), (1, "2")])
def test_malformed_audited_core_bounds_rejected(audited_registry, physical, logical):
    data = json.loads(audited_registry.read_text())
    data["hardware"].update(physical_cpu_cores=physical, logical_cpu_cores=logical)
    audited_registry.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RegistryAuthorityViolationError):
        ExecutionRouter(audited_registry)


def test_local_execution_reports_actual_executor_and_failure(audited_registry, tmp_path):
    router = ExecutionRouter(audited_registry)
    command = [sys.executable, "-c", "import os,sys; print(os.getcwd()); sys.exit(7)"]
    result = router.route_job(payload_command=command, scratch_dir=tmp_path / "scratch")
    assert result.status == "FAILED"
    assert result.returncode == 7
    assert result.assigned_executor == "local_fallback"
    assert Path(result.output.strip()) == result.scratch_dir


def test_source_scratch_and_unregistered_engine_rejected(audited_registry):
    router = ExecutionRouter(audited_registry)
    repo = Path(__file__).resolve().parents[2]
    with pytest.raises(AirGapViolationError):
        router.route_job(payload_command=[sys.executable, "-c", "print(1)"], scratch_dir=repo)
    with pytest.raises(RegistryAuthorityViolationError, match="not ready"):
        router.resolve_execution_path("missing-chemistry-engine")


def test_required_parsl_never_silently_executes_locally(audited_registry, tmp_path):
    data = json.loads(audited_registry.read_text())
    data["execution"]["default_engine"] = "parsl"
    audited_registry.write_text(json.dumps(data), encoding="utf-8")
    marker = tmp_path / "executed"
    with pytest.raises(RegistryAuthorityViolationError, match="requires Parsl"):
        ExecutionRouter(audited_registry).route_job(
            payload_command=[sys.executable, "-c", "from pathlib import Path; import sys; Path(sys.argv[1]).touch()", str(marker)],
            scratch_dir=tmp_path / "scratch",
        )
    assert not marker.exists()


def test_legacy_router_uses_same_authority_boundary():
    from cochem_base.core_engine.cochem_calc_execution_router import ExecutionRouter as legacy
    assert legacy is ExecutionRouter


def test_hpc_script_cannot_write_source_or_escape_job_directory(audited_registry, tmp_path):
    router = ExecutionRouter(audited_registry)
    with pytest.raises(ValueError, match="Job name"):
        router._dispatch_hpc("true", "../escaped", str(tmp_path))
    repo = Path(__file__).resolve().parents[2]
    with pytest.raises(AirGapViolationError):
        router._dispatch_hpc("true", "calculation", str(repo))


def test_slurm_directives_reject_injection_and_propagate_failure(tmp_path):
    import subprocess
    from cochem_base.calc.slurm_generator import SlurmGenerator, SlurmSubmissionSpec
    with pytest.raises(ValueError):
        SlurmSubmissionSpec(job_name="job\n#SBATCH --output=elsewhere")
    scratch = tmp_path / "scratch"
    store = tmp_path / "store"
    spec = SlurmSubmissionSpec(job_name="validation", scratch_dir=str(scratch), artifact_dir=str(store), cores=1)
    script = SlurmGenerator().generate_submission_script(spec, payload_command="exit 7")
    result = subprocess.run(["bash"], input=script, text=True, env={"PATH": "/usr/bin:/bin", "SLURM_CPUS_PER_TASK": "1"})
    assert result.returncode == 7
    assert not list(store.iterdir())
