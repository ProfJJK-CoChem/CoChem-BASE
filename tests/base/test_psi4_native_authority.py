"""Genuine optional Psi4 audit and native-component authority checks."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from cochem_base.cochem_core_registry_schema import CoChemSystemConfig, EngineInfo, EnginePaths
from cochem_base.core.cochem_core_registry_manager import save_system_config
from cochem_base.core_engine.execution_authority import (
    RegistryAuthorityViolationError,
    authorize_engine_execution,
)
from cochem_base.orchestrator.cochem_setup_phase_3 import audit_single_binary
from cochem_base.orchestrator.psi4_native_probe import probe_psi4_native


def test_schema_supports_unavailable_psi4_without_creating_availability():
    assert EnginePaths().psi4 is None
    value = EnginePaths(psi4=EngineInfo(status="missing"))
    assert value.psi4.status == "missing" and value.psi4.native_components == {}


def test_launcher_version_without_native_core_is_not_an_audit(tmp_path):
    launcher = tmp_path / "psi4"
    launcher.write_text("#!/bin/sh\necho 1.10.2\nexit 0\n")
    launcher.chmod(0o700)
    version, components, error = probe_psi4_native(launcher)
    assert version is None and not components and "native import/HF" in error
    audit = audit_single_binary("psi4", custom_path=launcher)
    assert not audit.is_available and audit.version is None


def test_missing_launcher_remains_unavailable(tmp_path):
    version, components, error = probe_psi4_native(tmp_path / "absent-psi4")
    assert version is None and not components and error


def test_genuine_psi4_native_audit_and_component_change_rejection(tmp_path):
    executable = os.environ.get("COCHEM_TEST_PSI4_EXECUTABLE")
    if not executable or not Path(executable).is_file():
        pytest.skip("Optional genuine Psi4 installation not supplied")
    audit = audit_single_binary("psi4", custom_path=executable)
    assert audit.is_available, audit.error_detail
    assert audit.version == "1.10.2" and len(audit.native_components) == 2
    config = CoChemSystemConfig.create_default(auto_detect_hardware=True)
    config.hardware.maxcore_mb = 1024
    record = EngineInfo(status="found", path=audit.path, version=audit.version, hash=audit.sha256_hash,
                        native_components=audit.native_components)
    config.engines = {"psi4": record}
    path = tmp_path / "registry.json"
    save_system_config(config, path)
    authorized = authorize_engine_execution("psi4", registry_path=path, executable=executable, cores=1, maxcore_mb=128)
    assert authorized.binary_sha256 == audit.sha256_hash
    # Add an actual immutable component fixture, then change its actual bytes.
    # This checks authority enforcement without modifying the installed engine.
    component = tmp_path / "component-fixture"
    component.write_bytes(b"initial native dependency fixture")
    record.native_components[str(component)] = hashlib.sha256(component.read_bytes()).hexdigest()
    config.engines = {"psi4": record}
    save_system_config(config, path)
    component.write_bytes(b"changed native dependency fixture")
    with pytest.raises(RegistryAuthorityViolationError, match="native|Native"):
        authorize_engine_execution("psi4", registry_path=path, executable=executable, cores=1, maxcore_mb=128)
