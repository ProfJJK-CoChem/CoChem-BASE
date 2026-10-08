"""Real scheduler absence, typed admission and original-byte integrity.

These checks execute filesystem operations and Linux command syntax validation.
They do not simulate a scheduler, forge a calculation or claim physical cluster
acceptance. The READ input is the retained genuine ORCA water Hessian fixture.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import uuid

import pytest

from cochem_base.interfaces.student_hpc import (
    SCHEMA, StudentHpcClient, StudentHpcError, _bind_scientific_inputs,
    _hash, _load_package, _memory_mb, _source_inventory, _verify_source, _write,
    render_batch_script,
    validate_portable_calculation, validate_resources,
)
from cochem_base.interfaces.scientific_inputs import build_bundle

FIXTURE = Path(__file__).resolve().parents[1] / "data/orca_6_1_1_water_hf_sto3g"
WATER = (FIXTURE / "water.xyz").read_text()
ROOT = FIXTURE.parents[2]


def _run_without_allocation(code, *arguments, allocation=None):
    """Run an actual child process with explicit admission-only environment."""
    environment = dict(os.environ)
    for name in ("SLURM_JOB_ID", "PBS_JOBID"):
        environment.pop(name, None)
    environment.update(allocation or {})
    environment["PYTHONPATH"] = os.pathsep.join(_source_inventory()["module_search_paths"])
    return subprocess.run([sys.executable, "-c", code, *map(str, arguments)], env=environment,
        cwd="/tmp", text=True, capture_output=True, check=False, timeout=30)


def resources(**overrides):
    return validate_resources({"scheduler": "slurm", "queue": "teaching", "job_name": "student-water",
        "cores": 16, "memory_mb": 32768, "walltime": "04:00:00", **overrides})


def calculation(**overrides):
    return {"geometry": WATER, "engine": "orca", "method": "HF", "basis_set": "STO-3G", "charge": 0,
        "multiplicity": 1, "is_opt": True, "is_freq": False, "timeout_seconds": 3600, **overrides}


def recovery(**overrides):
    return {"pyscf_version": "2.14.0", "method": "CASSCF", "basis": "STO-3G", "active_electrons": 2,
        "active_orbitals": [4, 5], "active_space_rationale": "Declared occupied/virtual orbital test selection; no calculation is asserted",
        "threads": 8, "memory_mb": 8192, "timeout_seconds": 3600, "max_cycle": 200, **overrides}


def staged(tmp_path):
    identity = str(uuid.uuid4())
    package = tmp_path / identity
    package.mkdir()
    source = package / "inputs/water.xyz"
    source.parent.mkdir()
    source.write_text(WATER)
    request = {"schema_version": SCHEMA, "request_id": identity, "scheduler": "slurm", "resources": resources(),
        "source": _source_inventory(), "calculation": calculation(), "provider": None, "native_search": None,
        "scientific_inputs": None, "t9_request": None, "data_inputs": None,
        "files": {"inputs/water.xyz": {"sha256": _hash(source), "size_bytes": source.stat().st_size}}}
    _write(package / "request.json", request)
    return package, request, _hash(package / "request.json")


@pytest.mark.parametrize("scheduler", ["slurm", "pbs"])
def test_batch_script_is_valid_bash_and_only_dispatches_hash_bound_reviewed_worker(tmp_path, scheduler):
    script = render_batch_script(tmp_path / "owned path", scheduler, resources(scheduler=scheduler), request_sha256="f" * 64)
    completed = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert "--request-sha256 " + "f" * 64 in script
    assert "cochem_base.interfaces.student_hpc" in script
    assert "--nodes=1" in script if scheduler == "slurm" else "select=1:ncpus=16:mem=32768mb" in script
    assert "orca" not in script and "xcfour" not in script and "python -c" not in script


@pytest.mark.parametrize("field,value", [("queue", "teaching; touch /tmp/injected"), ("job_name", "student\n#SBATCH --nodes=2"),
    ("account", "$(whoami)"), ("email", "me@example.org\ncode"), ("cores", True), ("cores", 0),
    ("memory_mb", -1), ("nodes", 2), ("walltime", "00:00:00")])
def test_scheduler_injection_and_unbounded_allocations_rejected(field, value):
    with pytest.raises(ValueError):
        resources(**{field: value})


def test_multicore_hpc_admission_is_not_limited_to_actions_student_profile():
    admitted = validate_portable_calculation(calculation(), resources=resources())
    assert admitted["method"] == "HF" and admitted["timeout_seconds"] == 3600
    accepted_t9 = validate_portable_calculation(calculation(is_opt=False), resources=resources(), t9_request=recovery())
    assert accepted_t9["t9_fallback"] is None  # interpreter authorization belongs to the compute node


@pytest.mark.parametrize("field,value", [("python_executable", "/home/prof/python"), ("threads", 17), ("memory_mb", 32768),
    ("timeout_seconds", 15000), ("active_orbitals", [4, 4]), ("active_electrons", 1), ("active_space_rationale", "")])
def test_t9_recovery_cannot_select_server_paths_overallocate_or_change_electronic_state(field, value):
    with pytest.raises(ValueError):
        validate_portable_calculation(calculation(is_opt=False), resources=resources(), t9_request=recovery(**{field: value}))


@pytest.mark.parametrize("field", ["hessian_file", "r2_reference_manifest", "t9_fallback"])
def test_login_host_scientific_paths_cannot_enter_portable_requests(field):
    with pytest.raises(ValueError, match="login-host"):
        validate_portable_calculation(calculation(**{field: "/login/server/secret"}), resources=resources())


def test_read_checkpoint_requires_its_matching_bundle_and_is_rebound_to_exact_original_bytes(tmp_path):
    raw = calculation(initial_hessian="READ")
    with pytest.raises(ValueError, match="uploaded original"):
        validate_portable_calculation(raw, resources=resources())
    with pytest.raises(ValueError, match="does not match"):
        validate_portable_calculation(raw, resources=resources(), scientific_inputs={"kind": "r2_reference", "entrypoint": "ref.json"})
    admitted = validate_portable_calculation(raw, resources=resources(), scientific_inputs={"kind": "read_hessian", "entrypoint": "initial.hess"})
    identity = str(uuid.uuid4())
    original = (FIXTURE / "water.hess").read_bytes()
    archive, descriptor = build_bundle({"initial.hess": original}, kind="read_hessian", entrypoint="initial.hess",
        request_id=identity, geometry_sha256=hashlib.sha256(WATER.encode()).hexdigest())
    (tmp_path / "scientific-inputs.zip").write_bytes(archive)
    output = tmp_path / "result"
    output.mkdir()
    request = {"request_id": identity, "scientific_inputs": descriptor, "t9_request": None}
    bound = _bind_scientific_inputs(request, tmp_path, output, tmp_path / "absent-registry.json", admitted)
    actual = Path(bound["hessian_file"])
    assert actual.is_relative_to(output) and actual.read_bytes() == original
    assert json.loads((output / "scientific-inputs.json").read_text())["scientific_validation_performed"] is False
    assert actual.stat().st_mode & 0o222 == 0


def test_reference_recipe_cannot_be_admitted_without_its_scientific_manifest():
    with pytest.raises(ValueError, match="uploaded original"):
        validate_portable_calculation(calculation(recipe="R2"), resources=resources())


def test_fresh_genuine_missing_registry_is_reported_as_unavailable(tmp_path):
    client = StudentHpcClient(artifact_dir=tmp_path, registry_path=tmp_path / "missing-registry.json")
    ready = client.preflight()
    assert ready["ready"] is False and ready["reason"]
    with pytest.raises(StudentHpcError):
        client.submit(calculation(), resources=resources())
    assert not client.jobs.exists()


@pytest.mark.parametrize("scheduler,variable", [("slurm", "SLURM_JOB_ID"), ("pbs", "PBS_JOBID")])
def test_actual_absent_allocation_cannot_run_chemistry(tmp_path, scheduler, variable):
    process = _run_without_allocation("from pathlib import Path; import sys; from cochem_base.interfaces.student_hpc import require_allocation; require_allocation({'scheduler':sys.argv[1]}, Path(sys.argv[2]))", scheduler, tmp_path)
    assert process.returncode != 0 and "interface-host execution is forbidden" in process.stderr


@pytest.mark.parametrize("scheduler,variable,command", [("slurm", "SLURM_JOB_ID", "scontrol"), ("pbs", "PBS_JOBID", "qstat")])
def test_environment_job_id_alone_cannot_replace_actual_controller_authority(tmp_path, scheduler, variable, command):
    if shutil.which(command):
        pytest.skip("A connected scheduler requires its separate genuine allocation acceptance; this test checks actual command absence")
    process = _run_without_allocation("from pathlib import Path; import sys; from cochem_base.interfaces.student_hpc import require_allocation; require_allocation({'scheduler':sys.argv[1]}, Path(sys.argv[2]))", scheduler, tmp_path, allocation={variable: "123"})
    assert process.returncode != 0 and "scheduler command is unavailable" in process.stderr


def test_worker_without_scheduler_allocation_retains_failure_and_performs_no_science(tmp_path):
    package, _, digest = staged(tmp_path)
    process = _run_without_allocation("from pathlib import Path; import sys; from cochem_base.interfaces.student_hpc import execute_staged; execute_staged(Path(sys.argv[1]),request_sha256=sys.argv[2])", package, digest)
    assert process.returncode != 0 and "compute allocation" in process.stderr
    report = json.loads((package / "results/student-result.json").read_text())
    assert report["status"] == "failed" and report["operation_performed"] is False
    assert not (package / "results/native").exists() and not (package / "allocation-runtime").exists()
    assert (package / "results/publication-manifest.json").is_file()


def test_queued_originals_and_controller_spooled_request_digest_cannot_change(tmp_path):
    package, _, digest = staged(tmp_path)
    assert _load_package(package, integrity=digest)["scheduler"] == "slurm"
    (package / "inputs/water.xyz").write_text(WATER + "changed\n")
    with pytest.raises(StudentHpcError, match="source input changed"):
        _load_package(package, integrity=digest)
    (package / "inputs/water.xyz").write_text(WATER)
    with (package / "request.json").open("a") as stream:
        stream.write("\n")
    with pytest.raises(StudentHpcError, match="source hash changed"):
        _load_package(package, integrity=digest)


def test_queued_source_fingerprint_rejects_a_different_implementation():
    source = deepcopy(_source_inventory())
    name = next(iter(source["files"]))
    source["files"][name] = "0" * 64
    with pytest.raises(StudentHpcError, match="source/interpreter changed"):
        _verify_source(source)


def test_hpc_history_retains_owned_identity_when_gui_adds_status_observations(tmp_path):
    client = StudentHpcClient(artifact_dir=tmp_path)
    identity = str(uuid.uuid4())
    package = client.jobs / identity
    package.mkdir(parents=True)
    _write(package / "request.json", {"schema_version": SCHEMA})
    saved = {"schema_version": SCHEMA, "request_id": identity, "scheduler": "slurm", "job_id": "123",
             "package": str(package), "request_sha256": _hash(package / "request.json"), "submitted_at": "retained test receipt"}
    _write(package / "submission.json", saved)
    assert client.history() == [saved]
    assert client._saved({**saved, "status": "queued", "conclusion": None})[1] == saved
    with pytest.raises(StudentHpcError, match="original owned"):
        client.cancel({**saved, "job_id": "124"})


@pytest.mark.parametrize("text,expected", [("32G", 32768), ("32768M", 32768), ("32768mb", 32768), ("1048576kb", 1024)])
def test_controller_memory_units_are_interpreted_before_scientific_allocation(text, expected):
    assert _memory_mb(text) == expected


def test_unknown_controller_memory_cannot_authorize_scientific_processes():
    with pytest.raises(StudentHpcError, match="verifiable allocated memory"):
        _memory_mb("unlimited")
