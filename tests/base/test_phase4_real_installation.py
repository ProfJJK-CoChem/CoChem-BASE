"""The legacy phase-4 entry point must not certify an empty or preview silo."""

import json
import os
from pathlib import Path
import subprocess
import sys
import venv

import pytest

from cochem_base.orchestrator.cochem_setup_phase_4 import (
    Phase4AuditError, SiloConfig, SiloStatus, SiloType, filter_silos_by_manifest,
    get_default_silo_configs, load_deployment_manifest, provision_micro_silo, run_phase_4_audit,
)


def config(path, **overrides):
    values = dict(name="verification", silo_type=SiloType.CORE,
                  target_path=str(path), python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
                  is_requested=True, packages=["filelock"], pip_packages=["filelock==3.32.7"])
    values.update(overrides)
    return SiloConfig(**values)


def test_preview_does_not_certify_installation(tmp_path):
    path = tmp_path / "preview"
    result = provision_micro_silo(config(path), dry_run=True)
    assert result.status is SiloStatus.MISSING
    assert result.is_available is False
    assert result.packages_verified == []
    assert not path.exists()


def test_existing_empty_silo_does_not_pass_dependency_gate(tmp_path):
    path = tmp_path / "empty"
    venv.create(path, with_pip=False)
    result = provision_micro_silo(config(path))
    assert result.status is SiloStatus.ERROR
    assert result.is_available is False
    assert "filelock" in result.error_detail


def test_wrong_python_abi_is_rejected_before_creation(tmp_path):
    path = tmp_path / "wrong-abi"
    result = provision_micro_silo(config(path, python_version="3.1"))
    assert result.status is SiloStatus.ERROR
    assert result.is_available is False
    assert not path.exists()


def test_unpinned_install_does_not_create_silo(tmp_path):
    path = tmp_path / "unpinned"
    result = provision_micro_silo(config(path, pip_packages=["filelock>=3"]))
    assert result.status is SiloStatus.ERROR
    assert "exactly pinned" in result.error_detail
    assert not path.exists()


def test_explicit_base_silos_are_selected_without_future_repositories(tmp_path):
    requested = [silo.value for silo in SiloType]
    manifest = {"selected_repositories": ["CoChem-BASE"], "requested_silos": requested}
    audit = filter_silos_by_manifest(manifest)
    assert audit.requested_silos == requested
    assert audit.selected_repositories == ["CoChem-BASE"]
    assert audit.heavy_silos_requested and not audit.skipped_silos
    configs = get_default_silo_configs(tmp_path, audit)
    assert all(silo.is_requested for silo in configs.values())
    assert audit.disk_space_saved_estimated_mb == 0


def test_requested_calc_only_and_skip_heavy_have_explicit_effective_selection(tmp_path):
    requested = [SiloType.CORE.value, SiloType.CALC.value]
    manifest = {"selected_repositories": ["CoChem-BASE"], "requested_silos": requested}
    audit = filter_silos_by_manifest(manifest)
    configs = get_default_silo_configs(tmp_path, audit)
    assert configs[SiloType.CALC.value].is_requested
    assert not configs[SiloType.MACE.value].is_requested
    assert not configs[SiloType.UI.value].is_requested
    assert audit.disk_space_saved_estimated_mb == 4500
    skipped = filter_silos_by_manifest(manifest, skip_heavy_flag=True)
    assert skipped.requested_silos == requested
    assert not skipped.heavy_silos_requested
    assert set(skipped.skipped_silos) == {SiloType.UI.value, SiloType.CALC.value, SiloType.MACE.value}
    assert get_default_silo_configs(tmp_path, skipped)[SiloType.CORE.value].is_requested


def test_phase4_entrypoint_consumes_manifest_silos_before_provisioning(tmp_path):
    requested = [silo.value for silo in SiloType]
    source = tmp_path / "deployment.json"
    source.write_text(json.dumps({"selected_repositories": ["CoChem-BASE"], "requested_silos": requested}))
    report = run_phase_4_audit(
        output_dir=tmp_path / "audit", silo_dir=tmp_path / "silos", manifest_path=source, dry_run=True,
    )
    assert report.manifest_filter.requested_silos == requested
    assert report.manifest_filter.skipped_silos == []
    assert set(report.silos) == set(requested)
    assert all(not silo.is_available for silo in report.silos.values())


@pytest.mark.parametrize("payload", [
    [], {}, {"requested_silos": None}, {"requested_silos": "cochem_calc_silo"},
    {"requested_silos": [True]}, {"requested_silos": ["unknown_silo"]},
    {"requested_silos": ["cochem_core_silo", "cochem_core_silo"]},
    {"selected_repositories": "CoChem-BASE"}, {"selected_repositories": [None]},
    {"downstream_modules": ["CoChem-TORQ"]},
])
def test_malformed_explicit_deployment_manifest_fails_closed(tmp_path, payload):
    source = tmp_path / "deployment.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(Phase4AuditError, match="Invalid deployment manifest"):
        load_deployment_manifest(source)


def test_explicit_missing_and_invalid_json_manifests_never_fall_back(tmp_path):
    with pytest.raises(Phase4AuditError, match="Invalid deployment manifest"):
        load_deployment_manifest(tmp_path / "missing.json")
    source = tmp_path / "broken.json"
    source.write_text('{"requested_silos":', encoding="utf-8")
    with pytest.raises(Phase4AuditError, match="Invalid deployment manifest"):
        load_deployment_manifest(source)
    command = [sys.executable, "-c", (
        "from cochem_base.orchestrator.cochem_setup_phase_4 import load_deployment_manifest; "
        "load_deployment_manifest()"
    )]
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[2],
                            env={**os.environ, "COCHEM_MANIFEST_PATH": str(source)},
                            capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert "Invalid deployment manifest" in result.stderr


def test_silo_argument_contradictions_fail_and_mandatory_core_is_retained():
    with pytest.raises(ValueError, match="contradicts"):
        filter_silos_by_manifest({"requested_silos": [SiloType.CALC.value]}, requested_silos=[])
    audit = filter_silos_by_manifest({"requested_silos": []})
    assert SiloType.CORE.value not in audit.skipped_silos
    assert set(audit.skipped_silos) == {SiloType.UI.value, SiloType.CALC.value, SiloType.MACE.value}
