#!/usr/bin/env python3
"""
Unit and Integration Test Suite for CoChem-SCRIBE Stage 0.0 Setup (setup/cochem_setup_scribe.py).
Strictly adheres to Zero-Mock mandate, Method Matrix v4, and FAIR data standards.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Generator

import pytest
from pydantic import ValidationError

from setup.cochem_setup_scribe import (
    APPROVED_SCRIBE_DEPENDENCIES,
    FORBIDDEN_DEPENDENCIES,
    PreferredLLMModel,
    ScribeExtendedSystemConfig,
    ScribeSettings,
    evaluate_resource_guard,
    generate_requirements_manifest,
    get_dynamic_atomic_mass,
    init_airgap_directories,
    is_inside_git_tree,
    probe_latex_environment,
    provision_secure_credentials,
    setup_scribe_environment,
    setup_scribe_logger,
    update_scribe_registry,
    validate_credential_security,
    validate_hdf5_compression,
    validate_tiktoken_encoding,
)


@pytest.fixture
def temp_airgap_env(tmp_path: Path) -> Generator[Path, None, None]:
    """Provides an isolated, clean temporary artifacts directory for testing outside git."""
    test_artifacts_dir = tmp_path / "CoChem_Artifacts"
    test_artifacts_dir.mkdir(parents=True, exist_ok=True)
    yield test_artifacts_dir
    # Close any active logger handlers before directory teardown
    scribe_logger = logging.getLogger("CoChem-SCRIBE")
    if scribe_logger.hasHandlers():
        for h in list(scribe_logger.handlers):
            try:
                h.close()
            except Exception:
                pass
        scribe_logger.handlers.clear()
    if test_artifacts_dir.exists():
        shutil.rmtree(test_artifacts_dir, ignore_errors=True)


class TestScribeDependencies:
    """SRS Section 4.1: Micro-Silo Environment Builder & Dependency Locking."""

    def test_approved_dependencies_manifest(self, temp_airgap_env: Path) -> None:
        manifest_file = temp_airgap_env / "requirements_scribe.txt"
        generated_path = generate_requirements_manifest(manifest_file)

        assert generated_path.exists()
        content = generated_path.read_text(encoding="utf-8").strip().splitlines()
        manifest_packages = [
            line.split("==")[0].split(">=")[0].strip()
            for line in content
            if line.strip() and not line.startswith("#")
        ]

        for approved in APPROVED_SCRIBE_DEPENDENCIES:
            assert approved in manifest_packages, (
                f"Approved dependency '{approved}' missing from manifest."
            )

        for forbidden in FORBIDDEN_DEPENDENCIES:
            assert forbidden not in manifest_packages, (
                f"Forbidden package '{forbidden}' detected in manifest!"
            )

    def test_manifest_rejects_forbidden_injection(self, temp_airgap_env: Path) -> None:
        manifest_file = temp_airgap_env / "requirements_scribe_custom.txt"
        with pytest.raises(ValueError, match="Unapproved or forbidden dependencies detected"):
            generate_requirements_manifest(
                manifest_file, custom_packages=["google-genai", "tenacity"]
            )

    def test_manifest_rejects_unapproved_injection(self, temp_airgap_env: Path) -> None:
        manifest_file = temp_airgap_env / "requirements_scribe_unapproved.txt"
        with pytest.raises(
            ValueError, match="Unapproved dependencies rejected by micro-silo whitelist"
        ):
            generate_requirements_manifest(
                manifest_file, custom_packages=["google-genai", "unapproved_pkg_xyz"]
            )

    def test_tiktoken_encoding_validation(self) -> None:
        assert validate_tiktoken_encoding("cl100k_base") is True


class TestScribeRegistrySchema:
    """SRS Section 4.2: The Golden Registry & Pydantic Schema Extensions."""

    def test_scribe_settings_valid(self, temp_airgap_env: Path) -> None:
        silo_path = temp_airgap_env / "Silos" / "scribe_llm"
        silo_path.mkdir(parents=True, exist_ok=True)
        report_archive = temp_airgap_env / "Report_Archive"
        report_archive.mkdir(parents=True, exist_ok=True)
        env_file = report_archive / ".env"
        env_file.write_text("GEMINI_API_KEY=AIzaSyValidRealKey12345\n", encoding="utf-8")

        settings = ScribeSettings(
            silo_path=str(silo_path.resolve()),
            api_key_paths=str(env_file.resolve()),
            resource_guard=True,
            preferred_llm_model=PreferredLLMModel.GOOGLE_GENAI.value,
            latex_ready=False,
        )

        assert settings.silo_path == str(silo_path.resolve())
        assert settings.api_key_paths == str(env_file.resolve())
        assert settings.resource_guard is True
        assert settings.preferred_llm_model == "google-genai"
        assert settings.latex_ready is False

    def test_scribe_settings_rejects_relative_path(self) -> None:
        with pytest.raises(ValidationError):
            ScribeSettings(
                silo_path="relative/path/silo",
                api_key_paths="relative/.env",
                preferred_llm_model="google-genai",
            )

    def test_scribe_settings_rejects_invalid_model(self, temp_airgap_env: Path) -> None:
        silo_path = temp_airgap_env / "Silos" / "scribe_llm"
        env_file = temp_airgap_env / ".env"
        with pytest.raises(ValidationError):
            ScribeSettings(
                silo_path=str(silo_path.resolve()),
                api_key_paths=str(env_file.resolve()),
                preferred_llm_model="invalid-llm-engine",
            )

    def test_extended_config_preserves_registry(self, temp_airgap_env: Path) -> None:
        silo_path = temp_airgap_env / "Silos" / "scribe_llm"
        report_archive = temp_airgap_env / "Report_Archive"
        silo_path.mkdir(parents=True, exist_ok=True)
        report_archive.mkdir(parents=True, exist_ok=True)
        env_file = report_archive / ".env"
        env_file.write_text("GEMINI_API_KEY=AIzaSyValidProductionKey123\n", encoding="utf-8")

        settings = ScribeSettings(
            silo_path=str(silo_path.resolve()),
            api_key_paths=str(env_file.resolve()),
            resource_guard=True,
            preferred_llm_model=PreferredLLMModel.GOOGLE_GENAI.value,
            latex_ready=True,
        )

        config_file = temp_airgap_env / "Registry" / "cochem_system_config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)

        updated_config = update_scribe_registry(config_file, settings)
        assert updated_config.scribe_settings is not None
        assert updated_config.scribe_settings.preferred_llm_model == "google-genai"
        assert updated_config.scribe_settings.latex_ready is True
        assert config_file.exists()

        loaded_raw = json.loads(config_file.read_text(encoding="utf-8"))
        assert "scribe_settings" in loaded_raw
        assert loaded_raw["scribe_settings"]["latex_ready"] is True


class TestSecureCredentialProvisioning:
    """SRS Section 4.3: Secure Credential Provisioning & Air-Gap Standards."""

    def test_init_airgap_directories(self, temp_airgap_env: Path) -> None:
        dirs = init_airgap_directories(temp_airgap_env, allow_git_nested=True)
        assert dirs["report_archive"].exists()
        assert dirs["registry"].exists()
        assert dirs["logs"].exists()
        assert dirs["silos"].exists()
        assert dirs["report_archive"].is_dir()
        assert dirs["registry"].is_dir()

    def test_provision_valid_credentials(self, temp_airgap_env: Path) -> None:
        init_airgap_directories(temp_airgap_env, allow_git_nested=True)
        env_path = provision_secure_credentials(
            api_key="AIzaSyAuthenticApiKeyPayloadForVerification777",
            artifacts_root=temp_airgap_env,
            allow_git_nested=True,
        )
        assert env_path.exists()
        assert env_path.parent == temp_airgap_env / "Report_Archive"
        content = env_path.read_text(encoding="utf-8")
        assert "GEMINI_API_KEY=AIzaSyAuthenticApiKeyPayloadForVerification777" in content

        # Verify security validation passes
        assert validate_credential_security(env_path) is True

    def test_provision_fails_on_missing_credentials(self, temp_airgap_env: Path) -> None:
        old_env_key = os.environ.pop("GEMINI_API_KEY", None)
        try:
            init_airgap_directories(temp_airgap_env, allow_git_nested=True)
            with pytest.raises(ValueError, match="Missing or invalid authentic API credentials"):
                provision_secure_credentials(
                    api_key="",
                    artifacts_root=temp_airgap_env,
                    allow_git_nested=True,
                )
        finally:
            if old_env_key is not None:
                os.environ["GEMINI_API_KEY"] = old_env_key

    def test_airgap_boundary_violation_in_git_tree(self, tmp_path: Path) -> None:
        git_dir = tmp_path / "mock_repo"
        git_dir.mkdir(parents=True, exist_ok=True)
        (git_dir / ".git").mkdir()
        artifacts_nested = git_dir / "CoChem_Artifacts"

        assert is_inside_git_tree(artifacts_nested) is True
        with pytest.raises(PermissionError, match="Air-Gap boundary violation"):
            init_airgap_directories(artifacts_nested, allow_git_nested=False)


class TestResourceGuardProtocol:
    """SRS Section 4.4: Hardware-Aware Guardrails: RESOURCE_GUARD Protocol."""

    def test_resource_guard_triggers_below_8gb(self, temp_airgap_env: Path) -> None:
        # Override RAM to 6.0 GB to test constraint
        report_archive = temp_airgap_env / "Report_Archive"
        report_archive.mkdir(parents=True, exist_ok=True)

        triggered, model = evaluate_resource_guard(
            requested_model="llama-cpp",
            override_ram_gb=6.0,
            api_key_available=True,
            artifacts_root=temp_airgap_env,
        )
        assert triggered is True
        assert model == PreferredLLMModel.GOOGLE_GENAI.value

        # Check central audit log recording
        audit_file = report_archive / "cochem_audit_log.json"
        assert audit_file.exists()
        logs = json.loads(audit_file.read_text(encoding="utf-8"))
        assert len(logs) >= 1
        assert logs[-1]["level"] == "[SCRIBE-WARNING]"
        assert logs[-1]["event_type"] == "RESOURCE_GUARD_RAM_OVERRIDE"

    def test_resource_guard_passes_above_8gb(self) -> None:
        triggered, model = evaluate_resource_guard(
            requested_model="llama-cpp",
            override_ram_gb=16.0,
            api_key_available=True,
        )
        assert triggered is False
        assert model == "llama-cpp"

    def test_resource_guard_fail_fast_missing_api_key(self, temp_airgap_env: Path) -> None:
        with pytest.raises(RuntimeError, match="RESOURCE_GUARD triggered due to total RAM"):
            evaluate_resource_guard(
                requested_model="llama-cpp",
                override_ram_gb=4.0,
                api_key_available=False,
                artifacts_root=temp_airgap_env,
            )


class TestOSProbingAndHDF5:
    """SRS Section 4.5: Base Utilities & OS-Level Probing."""

    def test_latex_probing(self) -> None:
        result = probe_latex_environment()
        assert isinstance(result, bool)

    def test_hdf5_compression_validation(self, temp_airgap_env: Path) -> None:
        test_h5_dir = temp_airgap_env / "HDF5_Test"
        test_h5_dir.mkdir(parents=True, exist_ok=True)
        # Test authentic 3D quantum density grid slice compression
        success = validate_hdf5_compression(test_h5_dir)
        assert success is True

    def test_scribe_logger_setup(self, temp_airgap_env: Path) -> None:
        report_archive = temp_airgap_env / "Report_Archive"
        report_archive.mkdir(parents=True, exist_ok=True)
        logger_inst = setup_scribe_logger(report_archive, log_filename="cochem_scribe_api.log")

        assert isinstance(logger_inst, logging.Logger)
        logger_inst.info("Test SCRIBE audit message")

        log_file = report_archive / "cochem_scribe_api.log"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "[SCRIBE-" in content


class TestMendeleevIntegration:
    """Mendeleev Library Mandate: Dynamic atomic mass retrieval."""

    def test_mendeleev_dynamic_masses(self) -> None:
        c_mass = get_dynamic_atomic_mass("C")
        h_mass = get_dynamic_atomic_mass("H")
        o_mass = get_dynamic_atomic_mass("O")
        n_mass = get_dynamic_atomic_mass("N")
        fe_mass = get_dynamic_atomic_mass("Fe")

        assert 12.0 <= c_mass <= 12.02
        assert 1.0 <= h_mass <= 1.01
        assert 15.99 <= o_mass <= 16.00
        assert 14.00 <= n_mass <= 14.01
        assert 55.84 <= fe_mass <= 55.85

    def test_mendeleev_invalid_symbol(self) -> None:
        with pytest.raises((ValueError, KeyError)):
            get_dynamic_atomic_mass("InvalidElementSymbol999")


class TestFullScribeSetupWorkflow:
    """Integration Test: Full Stage 0.0 Setup Orchestration."""

    def test_setup_scribe_environment_e2e(self, temp_airgap_env: Path) -> None:
        config = setup_scribe_environment(
            artifacts_root=temp_airgap_env,
            api_key="AIzaSyAuthenticProductionValidKey456",
            preferred_model="google-genai",
            allow_git_nested=True,
        )

        assert isinstance(config, ScribeExtendedSystemConfig)
        assert config.scribe_settings is not None
        assert config.scribe_settings.preferred_llm_model == "google-genai"
        assert Path(config.scribe_settings.api_key_paths).exists()
        assert Path(config.scribe_settings.silo_path).exists()
        assert (temp_airgap_env / "Report_Archive" / "cochem_scribe_api.log").exists()
        assert (temp_airgap_env / "Registry" / "requirements_scribe.txt").exists()
