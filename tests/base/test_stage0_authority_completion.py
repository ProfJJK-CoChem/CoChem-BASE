"""Real boundary checks for complete Stage 0 publication and engine identity."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys

import pytest

from cochem_base.cochem_core_registry_schema import CoChemSystemConfig, EngineInfo
from cochem_base.core.cochem_core_registry_manager import save_system_config
from cochem_base.core_engine.execution_authority import (
    RegistryAuthorityViolationError,
    authorize_engine_execution,
)
from cochem_base.orchestrator.stage0_authority import Stage0AuthorityError, build_stage0_authority
from cochem_base.orchestrator.cochem_setup_phase_3 import (
    extract_semantic_version,
    interrogate_binary_version,
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


def test_no_unmeasured_default_registry():
    with pytest.raises(RegistryAuthorityViolationError, match="measured hardware"):
        CoChemSystemConfig.create_default()


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
    from cochem_base.orchestrator.bootstrap_service import run_setup
    import os
    before = os.environ.get("COCHEM_ARTIFACT_DIR")
    events = []
    summary = run_setup(tmp_path, phases=[1], on_event=events.append)
    assert os.environ.get("COCHEM_ARTIFACT_DIR") == before
    assert summary["overall_status"] == "PARTIAL_AUDIT"
    assert [item["event"] for item in events] == ["phase_start", "phase_result", "setup_complete"]
    assert events[1]["report"]["os_profile"]["system"]
    assert (tmp_path / "Registry" / "p1.json").is_file()
    assert not (tmp_path / "Registry" / "cochem_system_config.json").exists()
