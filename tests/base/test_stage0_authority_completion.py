"""Real boundary checks for complete Stage 0 publication and engine identity."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cochem_base.cochem_core_registry_schema import CoChemSystemConfig, EngineInfo
from cochem_base.core.cochem_core_registry_manager import save_system_config
from cochem_base.core_engine.engine_environment import engine_runtime_environment
from cochem_base.core_engine.execution_authority import (
    RegistryAuthorityViolationError,
    authorize_engine_execution,
)
from cochem_base.orchestrator.cochem_setup_phase_3 import (
    audit_binary_linkage,
    extract_semantic_version,
    interrogate_binary_version,
)
from cochem_base.orchestrator.stage0_authority import (
    Stage0AuthorityError,
    build_stage0_authority,
    publish_stage0_authority,
)


def _python_registry(tmp_path):
    """Record the actual running interpreter and measured host limits."""
    config = CoChemSystemConfig.create_default(auto_detect_hardware=True)
    config.hardware.maxcore_mb = 64
    executable = Path(sys.executable).absolute()
    with executable.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    config.engines = {"python": EngineInfo(status="found", path=str(executable), hash=digest)}
    path = tmp_path / "cochem_system_config.json"
    save_system_config(config, path)
    return path


def test_partial_or_preview_run_cannot_publish_stage0_authority(tmp_path):
    with pytest.raises(Stage0AuthorityError, match="eleven"):
        build_stage0_authority({"phases_executed": [], "artifact_dir": str(tmp_path)})
    with pytest.raises(Stage0AuthorityError, match="dry run"):
        build_stage0_authority({"dry_run": True})
    assert not (tmp_path / "Registry" / "cochem_system_config.json").exists()


def test_refused_stage0_publication_does_not_provision_partial_workspace(tmp_path):
    root = tmp_path / "refused-artifacts"
    with pytest.raises(Stage0AuthorityError, match="eleven"):
        publish_stage0_authority({"phases_executed": [], "artifact_dir": str(root)})
    assert not root.exists()
    with pytest.raises(Stage0AuthorityError, match="dry run"):
        publish_stage0_authority({"dry_run": True, "artifact_dir": str(root)})
    assert not root.exists()


def test_no_unmeasured_default_registry():
    with pytest.raises(RegistryAuthorityViolationError, match="measured hardware"):
        CoChemSystemConfig.create_default()


@pytest.mark.parametrize("hosted,restrict_affinity", [(False, False), (True, False), (True, True)])
def test_cpu_policy_uses_real_child_topology_and_affinity(hosted, restrict_affinity):
    """Exercise policy selection on measured CPUs; this is not hosted acceptance."""
    environment = {**os.environ, "COCHEM_CPU_ALLOCATION_POLICY": "github_hosted_vcpus" if hosted else "physical_cores",
                   "GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted"}
    script = '''
import json, os, psutil
from cochem_base.core_engine.hardware_profiler import profile_hardware
from cochem_base.core_engine.engine_environment import engine_runtime_environment
if os.environ['RESTRICT_TEST_AFFINITY'] == '1':
    available = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, [available[0]])
profile = profile_hardware()
child = engine_runtime_environment('orca')
print(json.dumps({'physical': profile.physical_cores, 'observed_physical': psutil.cpu_count(logical=False),
  'logical': profile.logical_cores, 'observed_logical': psutil.cpu_count(logical=True),
  'available': list(profile.available_cpu_ids), 'affinity': sorted(os.sched_getaffinity(0)),
  'budget': profile.allocatable_compute_cores, 'unit': profile.cpu_allocation_policy.budget_unit,
  'mapping': child.get('OMPI_MCA_rmaps_base_mapping_policy'),
  'binding': child.get('OMPI_MCA_hwloc_base_binding_policy'),
  'oversubscribe': child.get('OMPI_MCA_rmaps_base_oversubscribe')}))
'''
    if not hasattr(os, "sched_getaffinity"):
        pytest.skip("This hosted Linux policy boundary requires kernel CPU affinity")
    environment["RESTRICT_TEST_AFFINITY"] = "1" if restrict_affinity else "0"
    completed = subprocess.run([sys.executable, "-c", script], env=environment, check=True,
                               text=True, capture_output=True, timeout=15)
    measured = json.loads(completed.stdout)
    assert measured["physical"] == measured["observed_physical"]
    assert measured["logical"] == measured["observed_logical"]
    assert set(measured["available"]).issubset(measured["affinity"])
    assert 1 <= measured["budget"] <= len(measured["available"])
    if hosted:
        assert measured["unit"] == "virtual_cpu"
        assert measured["budget"] == len(measured["available"])
        assert measured["mapping"] == "hwthread:NOOVERSUBSCRIBE"
        assert measured["binding"] == "hwthread" and measured["oversubscribe"] == "0"
    else:
        assert measured["unit"] == "physical_core"
        assert measured["budget"] <= measured["physical"]
    if restrict_affinity:
        assert measured["budget"] == 1


def test_hosted_cpu_policy_cannot_silently_enable_smt_on_a_self_hosted_machine():
    environment = {**os.environ, "COCHEM_CPU_ALLOCATION_POLICY": "github_hosted_vcpus",
                   "GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "self-hosted"}
    completed = subprocess.run([sys.executable, "-c",
                               "from cochem_base.core_engine.hardware_profiler import profile_hardware; profile_hardware()"],
                               env=environment, capture_output=True, text=True, timeout=15)
    assert completed.returncode != 0
    assert "requires a GitHub-hosted Linux Actions job" in completed.stderr


@pytest.mark.parametrize("metadata,expected", [
    ("Program Version 6.1.1  -  RELEASE   -", "6.1.1"),
    ("Program Version 4.2.1 - RELEASE", "4.2.1"),
    ("ORCA version 5.0.4, Release", "5.0.4"),
    ("* O   R   C   A * Version 5.0.4", "5.0.4"),
    ("An Ab Initio, DFT and Semiempirical Electronic Structure Package\nVersion 6.1.0", "6.1.0"),
    ("Open MPI 4.1.8\nProgram Version 6.1.1 - RELEASE\nLibrary version 9.9.9", "6.1.1"),
    ("Startup preamble\n" * 400 + "Program Version 6.1.1 - RELEASE", "6.1.1"),
    ("Program Version 6.1.1\nProgram Version 6.1.1", "6.1.1"),
])
def test_orca_version_metadata_recognizes_qualified_current_and_legacy_headings(metadata, expected):
    """Parser inputs describe metadata formats, never substituted executables."""
    assert extract_semantic_version(metadata, "orca") == expected


@pytest.mark.parametrize("metadata", [
    "Python 3.12.9", "Open MPI 4.1.8", "Library Version 6.1.1", "6.1.1",
    "Program Version 6.1.1rc1", "Program Version 6.1.1.2",
    "Program Version 6.1.1\nORCA version 6.0.0",
])
def test_orca_version_metadata_rejects_unrelated_or_ambiguous_versions(metadata):
    assert extract_semantic_version(metadata, "orca") is None


def test_actual_interpreter_cannot_be_misidentified_as_orca():
    version, error = interrogate_binary_version(sys.executable, "orca")
    assert version is None
    assert error == "No recognized version was returned by the executable"


@pytest.mark.parametrize("metadata,expected", [
    ("CFOUR version 2.1", "2.1"),
    ("* CFOUR Coupled-Cluster techniques for Computational Chemistry *\n* Version 2.1 *", "2.1"),
    ("CFOUR 2.0\nLibrary version 0.3.20", "2.0"),
    ("GFortran 11.4.0\nOpenBLAS 0.3.20", None),
    ("Version 2.1", None),
    ("CFOUR version 2.1\nCFOUR version 2.0", None),
    ("CFOUR version 2.1rc1", None),
])
def test_cfour_version_requires_unambiguous_native_engine_identity(metadata, expected):
    assert extract_semantic_version(metadata, "xcfour") == expected


def test_actual_interpreter_cannot_be_misidentified_as_cfour():
    version, error = interrogate_binary_version(sys.executable, "xcfour")
    assert version is None
    assert error == "No recognized version was returned by the executable"


def test_optional_runtime_defaults_preserve_existing_registry_checksums(tmp_path):
    path = _python_registry(tmp_path)
    raw = json.loads(path.read_text())
    for record in raw["engines"].values():
        record.pop("runtime_seal_sha256", None)
        record.pop("runtime_metadata", None)
        record.pop("native_components", None)
    payload = {key: value for key, value in raw.items() if key not in {"registry_checksum", "last_updated"}}
    historical = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    assert raw["registry_checksum"] == historical
    assert CoChemSystemConfig.model_validate(raw).verify_checksum()


def test_nonempty_runtime_metadata_is_authenticated_in_registry(tmp_path):
    path = _python_registry(tmp_path)
    config = CoChemSystemConfig.model_validate_json(path.read_text())
    config.engines["python"].runtime_metadata = {"executable": str(Path(sys.executable).absolute())}
    config.update_checksum()
    assert config.verify_checksum()
    config.engines["python"].runtime_metadata["executable"] = str(tmp_path / "another-interpreter")
    assert not config.verify_checksum()


def test_cfour_child_runtime_preserves_audited_threads_without_nested_blas(tmp_path):
    inherited = {**os.environ, "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "8"}
    before = inherited.copy()
    environment = engine_runtime_environment("cfour", inherited, executable=sys.executable)
    completed = subprocess.run([
        sys.executable, "-I", "-c",
        "import json,os; print(json.dumps({key:os.environ.get(key) for key in "
        "['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','OMP_DYNAMIC','PATH']}))",
    ], env=environment, check=True, text=True, capture_output=True, timeout=15)
    observed = json.loads(completed.stdout)
    assert observed["OMP_NUM_THREADS"] == "2"
    assert observed["OPENBLAS_NUM_THREADS"] == "1"
    assert observed["OMP_DYNAMIC"] == "FALSE"
    assert observed["PATH"].split(os.pathsep)[0] == str(Path(sys.executable).resolve().parent)
    assert inherited == before


@pytest.mark.parametrize("engine", ["orca", "qe", "crest", "pyscf"])
def test_native_runtime_selection_reaches_only_its_own_child(engine, tmp_path):
    """A real interpreter observes environment transport, not chemistry output."""
    site_lib = tmp_path / "site-libraries"
    orca_lib = tmp_path / "orca-libraries"
    mpi_bin = tmp_path / "orca-mpi" / "bin"
    for directory in (site_lib, orca_lib, mpi_bin):
        directory.mkdir(parents=True)
    inherited = {**os.environ, "LD_LIBRARY_PATH": str(site_lib),
                 "DYLD_LIBRARY_PATH": str(site_lib),
                 "COCHEM_ORCA_LD_LIBRARY_PATH": str(orca_lib),
                 "COCHEM_ORCA_DYLD_LIBRARY_PATH": str(orca_lib),
                 "COCHEM_ORCA_MPIRUN_BIN": str(mpi_bin / "mpirun")}
    before = inherited.copy()
    environment = engine_runtime_environment(engine, inherited, executable=sys.executable)
    observed = subprocess.run([
        sys.executable, "-I", "-c",
        "import json,os; print(json.dumps({key:os.environ.get(key) for key in "
        "['LD_LIBRARY_PATH','DYLD_LIBRARY_PATH','PATH']}))",
    ], env=environment, check=True, text=True, capture_output=True, timeout=15)
    payload = json.loads(observed.stdout)
    assert inherited == before
    if engine == "orca":
        assert payload["LD_LIBRARY_PATH"] == payload["DYLD_LIBRARY_PATH"] == str(orca_lib)
        assert str(mpi_bin) in payload["PATH"].split(os.pathsep)
    else:
        assert payload["LD_LIBRARY_PATH"].split(os.pathsep)[0] == str(site_lib)
        assert payload["DYLD_LIBRARY_PATH"].split(os.pathsep)[0] == str(site_lib)
        assert str(orca_lib) not in payload["LD_LIBRARY_PATH"].split(os.pathsep)
        assert str(mpi_bin) not in payload["PATH"].split(os.pathsep)


def test_runtime_sibling_libraries_are_child_only_fallbacks(tmp_path):
    executable = tmp_path / "native" / "bin" / "engine"
    sibling = executable.parent.parent / "lib"
    sibling.mkdir(parents=True)
    inherited = {"PATH": os.environ.get("PATH", ""),
                 "LD_LIBRARY_PATH": "/configured/site", "DYLD_LIBRARY_PATH": "/configured/site"}
    environment = engine_runtime_environment("qe", inherited, executable=executable)
    variable = {"linux": "LD_LIBRARY_PATH", "darwin": "DYLD_LIBRARY_PATH"}.get(sys.platform, "PATH")
    assert environment[variable].split(os.pathsep)[-1] == str(sibling)
    assert inherited["LD_LIBRARY_PATH"] == inherited["DYLD_LIBRARY_PATH"] == "/configured/site"
    if variable != "PATH":
        assert environment[variable].split(os.pathsep)[0] == "/configured/site"


def test_runtime_mpi_scope_requires_the_selected_launcher_identity(tmp_path):
    selected = tmp_path / "orca-mpi" / "bin" / "mpirun"
    unrelated = tmp_path / "site-mpi" / "bin" / "mpirun"
    inherited = {"LD_LIBRARY_PATH": "/site/lib", "COCHEM_ORCA_LD_LIBRARY_PATH": "/orca/lib",
                 "COCHEM_ORCA_MPIRUN_BIN": str(selected)}
    assert engine_runtime_environment("mpirun", inherited, executable=selected)["LD_LIBRARY_PATH"] == "/orca/lib"
    assert engine_runtime_environment("mpirun", inherited, executable=unrelated)["LD_LIBRARY_PATH"] == "/site/lib"


def test_actual_linkage_audit_preserves_process_environment():
    before = dict(os.environ)
    valid, missing = audit_binary_linkage(Path(sys.executable), engine_name="python")
    assert valid and not missing
    assert dict(os.environ) == before


def test_real_audited_interpreter_executes_and_resource_overrides_fail(tmp_path):
    path = _python_registry(tmp_path)
    grant = authorize_engine_execution("python", registry_path=path, cores=1, maxcore_mb=32)
    completed = subprocess.run(
        grant.command(["-I", "-c", "print(6 * 7)"]), capture_output=True, text=True, check=True
    )
    assert completed.stdout.strip() == "42"
    with pytest.raises(RegistryAuthorityViolationError, match="core count"):
        authorize_engine_execution("python", registry_path=path, cores=10**6)
    with pytest.raises(RegistryAuthorityViolationError, match="per-core memory"):
        authorize_engine_execution("python", registry_path=path, maxcore_mb=65)


def test_named_engine_cannot_authorize_a_different_command(tmp_path):
    path = _python_registry(tmp_path)
    with pytest.raises(RegistryAuthorityViolationError, match="contradicts"):
        authorize_engine_execution(
            "python", registry_path=path, command=[str(tmp_path / "unverified-engine")]
        )
    with pytest.raises(RegistryAuthorityViolationError, match="not available"):
        authorize_engine_execution("orca", registry_path=path, command=[sys.executable, "-V"])


def test_digest_mismatch_rejected_even_with_valid_registry_checksum(tmp_path):
    path = _python_registry(tmp_path)
    config = CoChemSystemConfig.model_validate_json(path.read_text())
    config.engines["python"].hash = "0" * 64
    save_system_config(config, path)
    with pytest.raises(RegistryAuthorityViolationError, match="SHA-256"):
        authorize_engine_execution("python", registry_path=path)


def test_skipped_phase10_benchmarks_do_not_become_measurements(tmp_path):
    from cochem_base.orchestrator.cochem_setup_phase_10 import run_phase_10_audit

    report = run_phase_10_audit(
        output_dir=tmp_path / "Registry",
        registry_dir=tmp_path / "Registry",
        sandbox_base_dir=tmp_path / "Scratch",
        skip_iops=True,
        skip_eckart=True,
    )
    assert report.iops_profile.write_iops is None
    assert report.iops_profile.status.value == "NOT_RUN"
    assert report.eckart_verification_report.overall_status.value == "NOT_RUN"
    assert not report.alignment_engine_ready
    assert "COCHEM_IOPS_WRITE_IOPS" not in report.injected_env_vars
    assert report.injected_env_vars["COCHEM_ALIGNMENT_ENGINE_READY"] == "0"
    assert report.mass_cache_warmup["mass_source"] == "dynamic_mendeleev"
    assert report.mass_cache_warmup["measured_isotope_count"] > 0
    assert report.mass_cache_warmup["cached_query_median_ns"] > 0
    assert report.mass_cache_telemetry["hit_count"] > 0
    assert report.mass_cache_telemetry["miss_count"] > 0
    assert report.mass_cache_telemetry["avg_latency_ns"] > 0
    persisted = json.loads(Path(report.artifact_path).read_text())
    assert persisted["mass_cache_warmup"] == report.mass_cache_warmup
    assert persisted["mass_cache_telemetry"] == report.mass_cache_telemetry


def test_phase9_does_not_fabricate_measured_scout_latency(tmp_path):
    from cochem_base.orchestrator.cochem_setup_phase_9 import run_phase_9_audit

    report = run_phase_9_audit(output_dir=tmp_path)
    assert report.scout_anchor_profile.scout_step_latency_ms is None
    assert "COCHEM_PARSL_SCOUT_LATENCY_MS" not in report.injected_env_vars


def test_silo_launcher_cannot_be_replaced_by_same_host_binary(tmp_path):
    silo = tmp_path / "isolated"
    subprocess.run([sys.executable, "-I", "-m", "venv", "--without-pip", str(silo)], check=True)
    path = _python_registry(tmp_path)
    config = CoChemSystemConfig.model_validate_json(path.read_text())
    launcher = silo / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    config.engines["python"].path = str(launcher)
    with launcher.open("rb") as handle:
        config.engines["python"].hash = hashlib.file_digest(handle, "sha256").hexdigest()
    save_system_config(config, path)
    assert authorize_engine_execution("python", registry_path=path).executable == str(launcher)
    with pytest.raises(RegistryAuthorityViolationError, match="contradicts"):
        authorize_engine_execution("python", registry_path=path, executable=sys.executable)


def test_native_setup_service_emits_real_phase_events_and_preserves_authority(tmp_path):
    import os

    from cochem_base.orchestrator.bootstrap_service import run_setup
    before = os.environ.get("COCHEM_ARTIFACT_DIR")
    events = []
    summary = run_setup(tmp_path, phases=[1], on_event=events.append)
    assert os.environ.get("COCHEM_ARTIFACT_DIR") == before
    assert summary["overall_status"] == "PARTIAL_AUDIT"
    assert [item["event"] for item in events] == ["phase_start", "phase_result", "setup_complete"]
    assert events[1]["report"]["os_profile"]["system"]
    assert (tmp_path / "Registry" / "p1.json").is_file()
    assert not (tmp_path / "Registry" / "cochem_system_config.json").exists()
