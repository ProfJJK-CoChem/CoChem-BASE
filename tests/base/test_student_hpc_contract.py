"""Real scheduler absence, typed admission and original-byte integrity.

These checks execute filesystem operations and Linux command syntax validation.
They do not simulate a scheduler, forge a calculation or claim physical cluster
acceptance. The READ input is the retained genuine ORCA water Hessian fixture.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import uuid
from copy import deepcopy
from pathlib import Path

import pytest

from ci_tools.source_quarantine import source_paths

from cochem_base.interfaces.scientific_inputs import build_bundle
from cochem_base.interfaces.student_hpc import (
    SCHEMA,
    StudentHpcClient,
    StudentHpcError,
    StudentHpcSubmissionUnknown,
    _bind_scientific_inputs,
    _hash,
    _load_package,
    _local_scratch_mount,
    _memory_mb,
    _publish_local_results,
    _source_inventory,
    _verify_source,
    _write,
    load_local_registry_snapshot,
    local_execution_environment,
    render_batch_script,
    validate_portable_calculation,
    validate_resources,
)

FIXTURE = Path(__file__).resolve().parents[1] / "data/orca_6_1_1_water_hf_sto3g"
WATER = (FIXTURE / "water.xyz").read_text()
ROOT = FIXTURE.parents[2]


def _run_without_allocation(code, *arguments, allocation=None, background=False):
    """Run an actual child process with explicit admission-only environment."""
    environment = dict(os.environ)
    for name in ("SLURM_JOB_ID", "PBS_JOBID"):
        environment.pop(name, None)
    environment.update(allocation or {})
    environment["PYTHONPATH"] = os.pathsep.join(source_paths(ROOT))
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    prefix = """from pathlib import Path
import os,sys
source = Path(SOURCE_ROOT)
if os.environ.get('COCHEM_SOURCE_QUARANTINE_ROOT'):
    startup = sys.modules.get('sitecustomize')
    assert startup is not None
    assert Path(startup.__file__).resolve() == source / 'ci_tools/quarantine_startup/sitecustomize.py'
    state = getattr(sys.modules.get('ci_tools.source_quarantine'), '_active', None)
    assert state is not None and state['copied'] == source
import cochem_base.interfaces.student_hpc as actual_hpc
assert Path(actual_hpc.__file__).resolve() == source / 'src/cochem_base/interfaces/student_hpc.py'
""".replace('SOURCE_ROOT', repr(str(ROOT)))
    if background:
        return subprocess.Popen([sys.executable, "-B", "-c", prefix + code, *map(str, arguments)], env=environment,
            cwd="/tmp", text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return subprocess.run([sys.executable, "-B", "-c", prefix + code, *map(str, arguments)], env=environment,
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
    directory = tmp_path / "actual-empty-command-directory"
    directory.mkdir()
    process = _run_without_allocation("from pathlib import Path; import sys; from cochem_base.interfaces.student_hpc import require_allocation; require_allocation({'scheduler':sys.argv[1]}, Path(sys.argv[2]))", scheduler, tmp_path, allocation={variable: "123", "PATH": str(directory)})
    assert process.returncode != 0 and "scheduler command is unavailable" in process.stderr


def test_worker_without_scheduler_allocation_retains_failure_and_performs_no_science(tmp_path):
    # Stage inside this same canonical child so the original allocation refusal
    # is exercised after the unchanged exact source/interpreter guard. The
    # separate retained alias diagnostic covers ordinary production3-path use.
    process = _run_without_allocation("from pathlib import Path; import sys,json; from tests.base.test_student_hpc_contract import staged; from cochem_base.interfaces.student_hpc import execute_staged; package,_,digest=staged(Path(sys.argv[1])); Path(sys.argv[2]).write_text(json.dumps({'package':str(package),'digest':digest})); execute_staged(package,request_sha256=digest)", tmp_path, tmp_path / "child-staged-request.json")
    package = Path(json.loads((tmp_path / "child-staged-request.json").read_text())["package"])
    assert process.returncode != 0 and "compute allocation" in process.stderr
    report = json.loads((package / "results/student-result.json").read_text())
    assert report["status"] == "failed" and report["operation_performed"] is False
    assert not (package / "results/native").exists() and not (package / "allocation-runtime").exists()
    assert (package / "results/publication-manifest.json").is_file()
    assert not tuple((package / "results").rglob("*.lock"))


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


def test_actual_scratch_mount_is_measured_not_inferred_from_directory_name(tmp_path):
    import psutil
    scratch = tmp_path / "lustre-nfs-name-is-not-a-mount-observation"
    scratch.mkdir()
    observation = _local_scratch_mount(scratch)
    mounts = [entry for entry in psutil.disk_partitions(all=True)
              if scratch.resolve().is_relative_to(Path(entry.mountpoint).resolve())]
    actual = max(mounts, key=lambda entry: len(Path(entry.mountpoint).resolve().parts))
    assert observation["filesystem_type"] == actual.fstype.lower()
    assert observation["mountpoint"] == str(Path(actual.mountpoint).resolve())
    assert observation["device"] == actual.device
    assert observation["observation"] == "actual_containing_mount"


def test_actual_unclassified_mount_and_redirect_cannot_be_scratch(tmp_path):
    """The real Linux proc filesystem is not a node-local calculation filesystem."""
    with pytest.raises(StudentHpcError, match="shared or unclassified"):
        _local_scratch_mount(Path("/proc"))
    actual = tmp_path / "actual-local-directory"
    actual.mkdir()
    redirect = tmp_path / "redirected-scratch"
    redirect.symlink_to(actual, target_is_directory=True)
    with pytest.raises(StudentHpcError, match="non-symlink"):
        _local_scratch_mount(redirect)
    assert not tuple(actual.iterdir())


def test_allocation_placement_binds_real_host_identity_and_creates_private_unique_roots(tmp_path):
    """Placement metadata is a declared engineering input, not scheduler authority.

    The real process ID is used only as a grammar-valid identifier. This test
    neither calls a controller nor authorizes or executes a scientific job.
    """
    scratch = tmp_path / "node-scratch"
    scratch.mkdir()
    code = '''
import json,os,pwd,socket,stat,uuid
from pathlib import Path
from cochem_base.interfaces.student_hpc import create_allocation_workspace
request={'scheduler':'slurm','request_id':str(uuid.uuid4())}
declared={'scheduler':'slurm','job_id':str(os.getpid()),'request_id':request['request_id'],
 'hostname':socket.gethostname().split('.')[0],'username':pwd.getpwuid(os.getuid()).pw_name}
roots=[]
for index in range(2):
 root,placement=create_allocation_workspace(request,declared)
 roots.append({'path':str(root),'mode':stat.S_IMODE(root.stat().st_mode),'placement':placement})
print(json.dumps({'roots':roots,'declared_identity':declared,'controller_verified':False,'science_performed':False}))
'''
    process = _run_without_allocation(code, allocation={"SLURM_TMPDIR": str(scratch)})
    assert process.returncode == 0, process.stderr
    observed = json.loads(process.stdout)
    assert observed["controller_verified"] is False and observed["science_performed"] is False
    roots = observed["roots"]
    assert roots[0]["path"] != roots[1]["path"]
    for record in roots:
        path = Path(record["path"])
        assert path.parent == scratch and path.is_dir() and record["mode"] == 0o700
        placement = record["placement"]
        assert placement["allocation_identity"] == observed["declared_identity"]
        assert placement["selected_source"] == "SLURM_TMPDIR"
        assert placement["containing_mount"] == _local_scratch_mount(path)
        assert not tuple(path.iterdir())


def test_explicit_unclassified_allocation_scratch_refuses_before_directory_creation(tmp_path):
    code = '''
import os,pwd,socket,uuid
from cochem_base.interfaces.student_hpc import create_allocation_workspace
request={'scheduler':'slurm','request_id':str(uuid.uuid4())}
placement_input={'scheduler':'slurm','job_id':str(os.getpid()),'request_id':request['request_id'],
 'hostname':socket.gethostname().split('.')[0],'username':pwd.getpwuid(os.getuid()).pw_name}
create_allocation_workspace(request,placement_input)
'''
    process = _run_without_allocation(code, allocation={"SLURM_TMPDIR": "/proc"})
    assert process.returncode != 0 and "shared or unclassified" in process.stderr


def test_shared_job_records_use_atomic_staging_without_prohibited_external_lock(tmp_path):
    from cochem.core.context import ExecutionContext, FileLock, scoped_context
    source = tmp_path / "source"
    baseline = tmp_path / "baseline"
    output = tmp_path / "job-results"
    source.mkdir()
    baseline.mkdir()
    context = ExecutionContext("directory-contract", "engineering-test", source, baseline,
                               output, tmp_path / "node-scratch", "Tier 6 HPC")
    record = {"status": "failed", "operation_performed": False,
              "scope": "Actual per-job metadata publication; no chemistry"}
    with scoped_context(context):
        with pytest.raises(RuntimeError, match="locks are prohibited"):
            FileLock(output / "report.json.lock")
        _write(output / "report.json", record)
    assert json.loads((output / "report.json").read_text()) == record
    assert sorted(path.name for path in output.iterdir()) == ["report.json"]
    assert not tuple(source.iterdir()) and not tuple(baseline.iterdir())


def test_local_native_fixture_bytes_and_failed_metadata_publish_exactly(tmp_path):
    local = tmp_path / "node-local-results"
    published = tmp_path / "published-results"
    local.mkdir()
    published.mkdir()
    request = {"request_id": str(uuid.uuid4()), "scope": "Engineering transport; no scheduler authority"}
    _write(local / "request.json", request)
    _write(published / "request.json", request)
    original_request_stat = (published / "request.json").stat()
    originals = {"water.xyz": (FIXTURE / "water.xyz").read_bytes(),
                 "water.hess": (FIXTURE / "water.hess").read_bytes()}
    for name, data in originals.items():
        (local / name).write_bytes(data)
        (local / name).chmod(0o400)
    _write(local / "student-result.json", {"status": "failed", "operation_performed": False,
        "scope": "Replay of authentic retained files; not a new calculation or successful cluster job"})
    files = {str(path.relative_to(local)): {"sha256": _hash(path), "size_bytes": path.stat().st_size}
             for path in local.iterdir()}
    _write(local / "publication-manifest.json", {"schema_version": "cochem.hpc-publication/1", "files": files})
    before = {str(path.relative_to(local)): _hash(path) for path in local.iterdir()}
    _publish_local_results(local, published)
    assert {str(path.relative_to(published)): _hash(path) for path in published.iterdir()} == before
    assert {str(path.relative_to(local)): _hash(path) for path in local.iterdir()} == before
    assert (published / "request.json").stat().st_ino == original_request_stat.st_ino
    assert not tuple(published.rglob("*.lock")) and not tuple(published.rglob("*.tmp"))
    for name, original in originals.items():
        assert (published / name).read_bytes() == original
        assert (published / name).stat().st_mode & 0o777 == 0o400


def test_local_publication_refuses_links_and_retains_existing_result_bytes(tmp_path):
    local = tmp_path / "local"
    published = tmp_path / "published"
    local.mkdir()
    published.mkdir()
    original = published / "water.xyz"
    original.write_bytes(b"Retain this existing student file")
    (local / "water.xyz").write_bytes((FIXTURE / "water.xyz").read_bytes())
    with pytest.raises(StudentHpcError, match="already exists"):
        _publish_local_results(local, published)
    assert original.read_bytes() == b"Retain this existing student file"
    local_link = local / "redirect"
    local_link.symlink_to(FIXTURE / "water.hess")
    before = {path.name: path.read_bytes() for path in published.iterdir()}
    with pytest.raises(StudentHpcError, match="links/special"):
        _publish_local_results(local, published)
    assert {path.name: path.read_bytes() for path in published.iterdir()} == before


def test_queued_registry_is_validated_from_exact_local_bytes_without_shared_source_lock(tmp_path):
    """Real measured registry metadata; no complete setup or science is asserted."""
    from cochem_base.cochem_core_registry_schema import CoChemSystemConfig
    source_root = tmp_path / "queued-authority"
    local_root = tmp_path / "node-local"
    source_root.mkdir()
    local_root.mkdir(mode=0o700)
    original = source_root / "registry.json"
    config = CoChemSystemConfig.create_default(auto_detect_hardware=True)
    config.update_checksum()
    original.write_text(config.model_dump_json(), encoding="utf-8")
    original.chmod(0o400)
    contents = original.read_bytes()
    digest = hashlib.sha256(contents).hexdigest()
    metadata_before = original.stat()
    snapshot = local_root / "registry.json"
    admitted = load_local_registry_snapshot(original, snapshot, digest)
    assert admitted.verify_checksum() and admitted.hardware == config.hardware
    assert original.read_bytes() == snapshot.read_bytes() == contents
    assert sorted(path.name for path in source_root.iterdir()) == ["registry.json"]
    assert (local_root / "registry.json.lock").is_file()
    assert original.stat().st_mode == metadata_before.st_mode
    assert original.stat().st_mtime_ns == metadata_before.st_mtime_ns
    with pytest.raises(StudentHpcError, match="changed while"):
        load_local_registry_snapshot(original, local_root / "rejected.json", "0" * 64)
    assert not (local_root / "rejected.json").exists()
    assert original.read_bytes() == contents


def test_local_registry_snapshot_keeps_canonical_structural_validation(tmp_path):
    from cochem_base.core.cochem_core_registry_manager import RegistryParseError
    source = tmp_path / "malformed-authority.json"
    source.write_bytes(b"{invalid-json}")
    with pytest.raises(RegistryParseError):
        load_local_registry_snapshot(source, tmp_path / "local-copy.json", _hash(source))
    assert source.read_bytes() == b"{invalid-json}"
    assert not (tmp_path / "malformed-authority.json.lock").exists()


def test_worker_temp_cache_and_scratch_aliases_are_local_and_restored_after_exception(tmp_path):
    import tempfile
    runtime = tmp_path / "allocation-runtime"
    temporary = tmp_path / "allocation-temporary"
    keys = ("TMPDIR", "TMP", "TEMP", "COCH_SCRATCH", "COCHEM_SCRATCH_DIR", "COCHEM_SCRATCH",
            "COCHEM_ARTIFACT_DIR", "COCHEM_ARTIFACTS", "COCHEM_CONFIG", "COCHEM_ORCA_BIN")
    original_environment = {key: os.environ.get(key) for key in keys}
    original_tempdir = tempfile.tempdir
    with pytest.raises(ValueError, match="retained engineering exception"):
        with local_execution_environment(runtime, temporary):
            assert Path(tempfile.gettempdir()) == temporary
            assert all(Path(os.environ[key]) == temporary for key in ("TMPDIR", "TMP", "TEMP"))
            assert all(Path(os.environ[key]) == runtime / "Scratch"
                       for key in ("COCH_SCRATCH", "COCHEM_SCRATCH_DIR", "COCHEM_SCRATCH"))
            with tempfile.TemporaryDirectory() as directory:
                assert Path(directory).parent == temporary
            os.environ["COCHEM_ORCA_BIN"] = "engineering-state-restoration-marker"
            raise ValueError("retained engineering exception")
    assert {key: os.environ.get(key) for key in keys} == original_environment
    assert tempfile.tempdir == original_tempdir


# Dispatch-protocol fixtures below never execute submit.sh, sbatch/qsub or
# chemistry. Real filesystem publication and bounded Python side effects test
# uncertain acknowledgement; real Slurm/OpenPBS acceptance remains external.
def _dispatch_protocol_package(client, scheduler="slurm"):
    package = client.jobs / str(uuid.uuid4())
    package.mkdir(parents=True)
    _write(package / "request.json", {"schema_version": SCHEMA, "request_id": package.name, "scheduler": scheduler})
    (package / "submit.sh").write_text("#!/bin/sh\n# Engineering protocol fixture; never executed.\n")
    return package


def test_unknown_dispatch_survives_a_real_side_effect_timeout_and_blocks_duplicate(tmp_path):
    client = StudentHpcClient(artifact_dir=tmp_path)
    package = _dispatch_protocol_package(client)
    attempt = client._record_dispatch_attempt(package, "slurm")
    before = (package / "dispatch-attempt.json").read_bytes()
    witness = tmp_path / "engineering-side-effect"
    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run([sys.executable, "-B", "-c",
            "from pathlib import Path;import sys,time;Path(sys.argv[1]).write_text('side effect before timeout');time.sleep(2)", str(witness)],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=.2, check=True)
    assert witness.is_file() and "job_id" not in attempt
    restored = StudentHpcClient(artifact_dir=tmp_path)
    assert restored.pending_attempts() == [attempt]
    inventory = sorted(client.jobs.iterdir())
    with pytest.raises(StudentHpcSubmissionUnknown) as refused:
        restored.submit(None, resources={})  # Hold precedes even preflight/staging.
    assert refused.value.attempt == attempt
    assert sorted(client.jobs.iterdir()) == inventory
    assert (package / "dispatch-attempt.json").read_bytes() == before
    assert not (package / "submission.json").exists()


@pytest.mark.parametrize("scheduler,reply", [("slurm", ""), ("slurm", "not-a-job"),
    ("slurm", "123\n456"), ("pbs", "pending"), ("pbs", "0.server")])
def test_invalid_dispatch_ack_retains_unknown_without_inventing_job_id(tmp_path, scheduler, reply):
    client = StudentHpcClient(artifact_dir=tmp_path)
    package = _dispatch_protocol_package(client, scheduler)
    attempt = client._record_dispatch_attempt(package, scheduler)
    with pytest.raises(StudentHpcSubmissionUnknown) as failed:
        client._accept_dispatch_ack(attempt, reply)
    assert failed.value.attempt == attempt and "job_id" not in failed.value.attempt
    assert StudentHpcClient(artifact_dir=tmp_path).pending_attempts() == [attempt]
    assert not (package / "submission.json").exists()


@pytest.mark.parametrize("scheduler,reply,expected", [("slurm", "123;cluster\n", "123"), ("pbs", "456.server\n", "456.server")])
def test_matching_saved_receipt_resolves_only_its_original_dispatch_protocol(tmp_path, scheduler, reply, expected):
    client = StudentHpcClient(artifact_dir=tmp_path)
    package = _dispatch_protocol_package(client, scheduler)
    attempt = client._record_dispatch_attempt(package, scheduler)
    immutable = (package / "dispatch-attempt.json").read_bytes()
    saved = client._accept_dispatch_ack(attempt, reply)
    assert saved["job_id"] == expected and client._saved(saved)[1] == saved
    assert client.pending_attempts() == []
    assert (package / "dispatch-attempt.json").read_bytes() == immutable
    with pytest.raises(StudentHpcError, match="original owned"):
        client.cancel({**saved, "job_id": "999"})  # Real protected API refuses before scheduler access.


@pytest.mark.parametrize("fault", ["attempt_missing", "attempt_json", "attempt_schema", "attempt_jobid",
    "request_changed", "script_changed", "attempt_link", "receipt_json", "receipt_schema", "receipt_wrong_hash", "receipt_link"])
def test_corrupt_or_unsupported_dispatch_storage_never_releases_unknown_hold(tmp_path, fault):
    client = StudentHpcClient(artifact_dir=tmp_path)
    package = _dispatch_protocol_package(client)
    attempt = client._record_dispatch_attempt(package, "slurm")
    path = package / "dispatch-attempt.json"
    path.chmod(0o600)
    if fault == "attempt_missing": path.unlink()
    elif fault == "attempt_json": path.write_text("{")
    elif fault == "attempt_schema": path.write_bytes(json.dumps({**attempt, "schema_version": "future/9"}).encode())
    elif fault == "attempt_jobid": path.write_bytes(json.dumps({**attempt, "job_id": "123"}).encode())
    elif fault == "request_changed": (package / "request.json").write_text("{}")
    elif fault == "script_changed": (package / "submit.sh").write_text("changed")
    elif fault == "attempt_link":
        outside = tmp_path / "outside-attempt.json"
        outside.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(outside)
    else:
        saved = client._accept_dispatch_ack(attempt, "123")
        receipt = package / "submission.json"
        if fault == "receipt_json": receipt.write_text("{")
        elif fault == "receipt_schema": receipt.write_text(json.dumps({**saved, "schema_version": "future/9"}))
        elif fault == "receipt_wrong_hash": receipt.write_text(json.dumps({**saved, "script_sha256": "0" * 64}))
        elif fault == "receipt_link":
            outside = tmp_path / "outside-submission.json"
            outside.write_bytes(receipt.read_bytes()); receipt.unlink(); receipt.symlink_to(outside)
    restored = StudentHpcClient(artifact_dir=tmp_path)
    with pytest.raises(StudentHpcSubmissionUnknown): restored.pending_attempts()
    with pytest.raises(StudentHpcSubmissionUnknown): restored.submit(None, resources={})


def test_dispatch_attempt_cannot_be_overwritten_or_resolved_by_another_request(tmp_path):
    client = StudentHpcClient(artifact_dir=tmp_path)
    package = _dispatch_protocol_package(client)
    attempt = client._record_dispatch_attempt(package, "slurm")
    with pytest.raises(FileExistsError): client._record_dispatch_attempt(package, "slurm")
    with pytest.raises(StudentHpcSubmissionUnknown):
        client._accept_dispatch_ack({**attempt, "request_sha256": "0" * 64}, "123")
    assert client.pending_attempts() == [attempt]


@pytest.mark.parametrize("boundary", ["timeout_after_side_effect", "invalid_ack"])
def test_actual_dispatch_command_boundary_classifies_unknown_without_cluster(tmp_path, boundary):
    client = StudentHpcClient(artifact_dir=tmp_path)
    with client._dispatch_admission():
        assert client._pending_attempts(ignore_admission=True) == []
        package = _dispatch_protocol_package(client)
        attempt = client._record_dispatch_attempt(package, "slurm")
    assert not (client.jobs / ".dispatch-admission").exists()
    witness = package / "engineering-side-effect"
    program = ("from pathlib import Path;import sys,time;Path(sys.argv[1]).write_text('observed before timeout');time.sleep(2)"
               if boundary == "timeout_after_side_effect" else "print('invalid acknowledgement')")
    with pytest.raises(StudentHpcSubmissionUnknown) as failed:
        # Same private production wrapper, real _command and real subprocess.
        # Public submit constructs only sbatch/qsub. This Python command tests
        # the engineering error boundary, never a fake scheduler or accepted job.
        client._dispatch_command(attempt, sys.executable, ["-B", "-c", program, str(witness)], timeout=.2)
    assert failed.value.attempt == attempt and "job_id" not in attempt
    if boundary == "timeout_after_side_effect":
        assert witness.is_file()
        assert isinstance(failed.value.__cause__, StudentHpcError)
        assert isinstance(failed.value.__cause__.__cause__, subprocess.TimeoutExpired)
    assert client.pending_attempts() == [attempt]
    assert not (package / "submission.json").exists()


@pytest.mark.parametrize("when", ["while_admitted", "after_unconfirmed"])
def test_real_two_process_admission_blocks_a_second_dispatch_intent(tmp_path, when):
    import time
    ready, release = tmp_path / "ready", tmp_path / "release"
    code = """from pathlib import Path
import sys,time
from cochem_base.interfaces.student_hpc import StudentHpcClient
from tests.base.test_student_hpc_contract import _dispatch_protocol_package
client=StudentHpcClient(artifact_dir=Path(sys.argv[1]))
with client._dispatch_admission():
    assert client._pending_attempts(ignore_admission=True)==[]
    package=_dispatch_protocol_package(client)
    client._record_dispatch_attempt(package,'slurm')
    Path(sys.argv[2]).write_text('immutable attempt published')
    deadline=time.monotonic()+10
    while not Path(sys.argv[3]).exists() and time.monotonic()<deadline:time.sleep(.01)
    assert Path(sys.argv[3]).exists()
"""
    first = _run_without_allocation(code, tmp_path, ready, release, background=True)
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline: time.sleep(.01)
        assert ready.is_file()
        if when == "after_unconfirmed":
            release.write_text("release before second client")
            stdout, stderr = first.communicate(timeout=15)
            assert first.returncode == 0, stdout + stderr
        second = _run_without_allocation("from pathlib import Path;import sys;from cochem_base.interfaces.student_hpc import StudentHpcClient,StudentHpcSubmissionUnknown;client=StudentHpcClient(artifact_dir=Path(sys.argv[1]));\ntry:client.submit(None,resources={})\nexcept StudentHpcSubmissionUnknown:pass\nelse:raise AssertionError('Second client escaped the durable admission hold')", tmp_path)
        assert second.returncode == 0, second.stdout + second.stderr
        assert len(tuple((tmp_path / "StudentHpc").glob("*/dispatch-attempt.json"))) == 1
        assert not tuple((tmp_path / "StudentHpc").glob("*/submission.json"))
    finally:
        release.write_text("finish owned first client")
        stdout, stderr = first.communicate(timeout=15)
        assert first.returncode == 0, stdout + stderr


def test_admission_release_never_removes_an_actual_replacement_directory(tmp_path):
    client = StudentHpcClient(artifact_dir=tmp_path)
    lock = client.jobs / ".dispatch-admission"
    moved = client.jobs / "retained-original-admission"
    with pytest.raises(StudentHpcSubmissionUnknown, match="ownership cannot be confirmed"):
        with client._dispatch_admission():
            lock.rename(moved)
            lock.mkdir()
            (lock / "foreign-owner").write_bytes(b"unrelated replacement bytes")
    assert (lock / "foreign-owner").read_bytes() == b"unrelated replacement bytes"
    assert (moved / "owner.json").is_file()
    with pytest.raises(StudentHpcSubmissionUnknown): client.pending_attempts()


def test_abandoned_admission_is_never_removed_using_a_pid_or_stale_guess(tmp_path):
    code = "from pathlib import Path;import sys,os;from cochem_base.interfaces.student_hpc import StudentHpcClient;client=StudentHpcClient(artifact_dir=Path(sys.argv[1]));\nwith client._dispatch_admission():os._exit(0)"
    child = _run_without_allocation(code, tmp_path)
    assert child.returncode == 0, child.stderr
    owner = tmp_path / "StudentHpc/.dispatch-admission/owner.json"
    retained = owner.read_bytes()
    with pytest.raises(StudentHpcSubmissionUnknown): StudentHpcClient(artifact_dir=tmp_path).submit(None, resources={})
    assert owner.read_bytes() == retained
