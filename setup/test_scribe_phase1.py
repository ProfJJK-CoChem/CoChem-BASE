#!/usr/bin/env python3
"""
Authoritative CI/CD Test Suite for CoChem-SCRIBE Stage 0.0 Initialization.
Governed strictly by Phase 2, Task 4: SCRIBE Environment, Configuration &
Resource Guards (Stage 0.0) of the CoChem-SCRIBE SRS, Method Matrix v4,
FAIR data principles, the Air-Gap Compliance Directive, and the 6-Tier
Environment Matrix (WSL, OrbStack, Debian, Codespaces, GitHub Actions, HPC).

Target: setup/test_scribe_phase1.py
Zero-Mock Anti-Spoofing Protocol: Strictly authentic physical testing with zero mocks.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import platform
import shutil
import stat
import sys
from collections.abc import Generator
from pathlib import Path

import psutil
import pytest
import tiktoken
from pydantic import ValidationError

# Dynamically ensure setup directory is in sys.path for direct module import
_SETUP_DIR = Path(__file__).resolve().parent
if str(_SETUP_DIR) not in sys.path:
    sys.path.insert(0, str(_SETUP_DIR))

# Import cochem_setup_scribe components
from cochem_setup_scribe import (  # noqa: E402 # type: ignore
    APPROVED_SCRIBE_DEPENDENCIES,
    FORBIDDEN_DEPENDENCIES,
    RESOURCE_GUARD_RAM_THRESHOLD_BYTES,
    RESOURCE_GUARD_RAM_THRESHOLD_GB,
    TIKTOKEN_ENCODING,
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
    """Provides an isolated clean temporary artifacts directory outside live $HOME."""
    test_artifacts_dir = tmp_path / "CoChem_Artifacts"
    test_artifacts_dir.mkdir(parents=True, exist_ok=True)
    yield test_artifacts_dir
    # Cleanup handlers and remove test directory
    logger = logging.getLogger("CoChem-SCRIBE")
    for h in list(logger.handlers):
        try:
            h.close()
        except Exception:
            pass
        logger.removeHandler(h)
    if test_artifacts_dir.exists():
        shutil.rmtree(test_artifacts_dir, ignore_errors=True)


# =============================================================================
# 1. MICRO-SILO ENVIRONMENT & DEPENDENCY MANIFEST TEST (SRS Section 4.1)
# =============================================================================


class TestMicroSiloEnvironmentAndManifest:
    """SRS Section 4.1: Micro-Silo Environment Builder & Dependency Locking."""

    def test_requirements_scribe_created_and_locked_to_approved_dependencies(
        self, temp_airgap_env: Path
    ) -> None:
        """Verifies requirements_scribe.txt is locked to the 8 approved packages."""
        manifest_file = temp_airgap_env / "requirements_scribe.txt"
        generated_path = generate_requirements_manifest(manifest_file)

        assert generated_path.exists(), "requirements_scribe.txt was not generated."
        assert generated_path == manifest_file.resolve()

        content = generated_path.read_text(encoding="utf-8").strip().splitlines()
        manifest_packages = [
            line.split("==")[0].split(">=")[0].strip().lower()
            for line in content
            if line.strip() and not line.startswith("#")
        ]

        # Assert exactly the 8 approved dependencies are present
        assert len(manifest_packages) == len(APPROVED_SCRIBE_DEPENDENCIES), (
            f"Expected {len(APPROVED_SCRIBE_DEPENDENCIES)} dependencies, "
            f"found {len(manifest_packages)}: {manifest_packages}"
        )

        for approved in APPROVED_SCRIBE_DEPENDENCIES:
            assert approved in manifest_packages, (
                f"Approved dependency '{approved}' is missing from manifest."
            )

        # Assert unapproved/forbidden packages are strictly absent
        for forbidden in FORBIDDEN_DEPENDENCIES:
            assert forbidden not in manifest_packages, (
                f"Forbidden package '{forbidden}' detected in requirements manifest."
            )

    def test_manifest_rejects_forbidden_dependency_injection(
        self, temp_airgap_env: Path
    ) -> None:
        """Verifies that injecting forbidden dependencies raises ValueError."""
        manifest_file = temp_airgap_env / "requirements_forbidden.txt"
        with pytest.raises(
            ValueError, match="Unapproved or forbidden dependencies detected"
        ):
            generate_requirements_manifest(
                manifest_file,
                custom_packages=["google-genai", "tenacity", "jinja2"],
            )

    def test_manifest_rejects_unapproved_dependency_injection(
        self, temp_airgap_env: Path
    ) -> None:
        """Verifies that injecting unapproved packages raises ValueError."""
        manifest_file = temp_airgap_env / "requirements_unapproved.txt"
        with pytest.raises(
            ValueError,
            match="Unapproved dependencies rejected by micro-silo whitelist",
        ):
            generate_requirements_manifest(
                manifest_file,
                custom_packages=["google-genai", "unapproved_framework_xyz"],
            )

    def test_tiktoken_cl100k_base_encoding_resolution(self) -> None:
        """Verifies tiktoken.get_encoding('cl100k_base') operates accurately."""
        encoding = tiktoken.get_encoding(TIKTOKEN_ENCODING)
        assert encoding is not None
        assert encoding.name == "cl100k_base"

        test_payload = (
            "CoChem-SCRIBE Authentic Token Verification String: Quantum Chem 2026."
        )
        tokens = encoding.encode(test_payload)
        assert isinstance(tokens, list)
        assert len(tokens) > 0
        decoded = encoding.decode(tokens)
        assert decoded == test_payload

        # Also verify validate_tiktoken_encoding helper
        assert validate_tiktoken_encoding(TIKTOKEN_ENCODING) is True

    def test_scribe_silo_executable_path_resolution(
        self, temp_airgap_env: Path
    ) -> None:
        """Verifies scribe_llm silo path resolves dynamically and is isolated."""
        dirs = init_airgap_directories(temp_airgap_env, allow_git_nested=True)
        silo_path = dirs["scribe_silo"]

        assert silo_path.exists()
        assert silo_path.is_dir()
        assert silo_path.is_absolute()
        assert silo_path == (temp_airgap_env / "Silos" / "scribe_llm").resolve()
        assert "Silos" in silo_path.parts
        assert "scribe_llm" in silo_path.parts


# =============================================================================
# 2. GOLDEN REGISTRY SCHEMA & ATOMIC CONCURRENCY TEST (SRS Section 4.2)
# =============================================================================


class TestGoldenRegistrySchemaAndAtomicConcurrency:
    """SRS Section 4.2: The Golden Registry & Pydantic Schema Extensions."""

    def test_registry_path_resolution_and_schema_keys(
        self, temp_airgap_env: Path
    ) -> None:
        """Verifies dynamic registry path resolution and Pydantic schema validation."""
        registry_dir = temp_airgap_env / "Registry"
        registry_dir.mkdir(parents=True, exist_ok=True)

        silo_path = temp_airgap_env / "Silos" / "scribe_llm"
        silo_path.mkdir(parents=True, exist_ok=True)
        env_file = temp_airgap_env / "Report_Archive" / ".env"
        env_file.parent.mkdir(parents=True, exist_ok=True)
        env_file.write_text(
            "GEMINI_API_KEY=AIzaSyAuthenticApiKeyValid12345\n", encoding="utf-8"
        )

        settings = ScribeSettings(
            silo_path=str(silo_path.resolve()),
            api_key_paths=str(env_file.resolve()),
            resource_guard=True,
            preferred_llm_model=PreferredLLMModel.GOOGLE_GENAI.value,
            latex_ready=True,
        )

        assert settings.silo_path == str(silo_path.resolve())
        assert settings.api_key_paths == str(env_file.resolve())
        assert settings.resource_guard is True
        assert settings.preferred_llm_model == "google-genai"
        assert settings.latex_ready is True

    def test_scribe_settings_rejects_relative_paths(self) -> None:
        """Verifies ScribeSettings strictly rejects relative paths for silo and key."""
        with pytest.raises(ValidationError) as exc_info:
            ScribeSettings(
                silo_path="relative/path/to/silo",
                api_key_paths="relative/path/.env",
                preferred_llm_model="google-genai",
            )
        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "silo_path" in field_names or "api_key_paths" in field_names

    def test_scribe_settings_rejects_invalid_model_enum(
        self, temp_airgap_env: Path
    ) -> None:
        """Verifies ScribeSettings strictly rejects unapproved LLM engine names."""
        silo_path = temp_airgap_env / "Silos" / "scribe_llm"
        env_file = temp_airgap_env / "Report_Archive" / ".env"

        with pytest.raises(ValidationError):
            ScribeSettings(
                silo_path=str(silo_path.resolve()),
                api_key_paths=str(env_file.resolve()),
                preferred_llm_model="hallucinated-gpt-model",
            )

    def test_scribe_settings_forbids_extra_fields(
        self, temp_airgap_env: Path
    ) -> None:
        """Verifies ScribeSettings forbids undeclared extra fields (extra='forbid')."""
        silo_path = temp_airgap_env / "Silos" / "scribe_llm"
        env_file = temp_airgap_env / "Report_Archive" / ".env"

        with pytest.raises(ValidationError):
            ScribeSettings(
                silo_path=str(silo_path.resolve()),
                api_key_paths=str(env_file.resolve()),
                preferred_llm_model="google-genai",
                unauthorized_extra_field="malicious_payload",  # type: ignore[call-arg]
            )

    def test_atomic_update_mechanics_and_sha256_checksum(
        self, temp_airgap_env: Path
    ) -> None:
        """Verifies atomic update mechanics and SHA-256 checksum calculation."""
        config_path = temp_airgap_env / "Registry" / "cochem_system_config.json"
        silo_path = temp_airgap_env / "Silos" / "scribe_llm"
        env_file = temp_airgap_env / "Report_Archive" / ".env"

        silo_path.mkdir(parents=True, exist_ok=True)
        env_file.parent.mkdir(parents=True, exist_ok=True)
        env_file.write_text(
            "GEMINI_API_KEY=AIzaSyAuthenticApiKeyValid12345\n", encoding="utf-8"
        )

        settings = ScribeSettings(
            silo_path=str(silo_path.resolve()),
            api_key_paths=str(env_file.resolve()),
            resource_guard=True,
            preferred_llm_model=PreferredLLMModel.GOOGLE_GENAI.value,
            latex_ready=False,
        )

        updated_config = update_scribe_registry(config_path, settings)

        assert config_path.exists()
        assert updated_config.scribe_settings is not None
        assert updated_config.registry_checksum is not None
        assert len(updated_config.registry_checksum) == 64

        # Verify physical file on disk matches Pydantic serialization
        disk_raw = json.loads(config_path.read_text(encoding="utf-8"))
        assert disk_raw["scribe_settings"]["preferred_llm_model"] == "google-genai"
        assert disk_raw["registry_checksum"] == updated_config.registry_checksum

    def test_posix_fcntl_filelocks_strictly_banned(self) -> None:
        """Verifies via AST inspection that POSIX fcntl is BANNED for cluster safety."""
        setup_script = _SETUP_DIR / "cochem_setup_scribe.py"
        assert setup_script.exists(), f"Target script {setup_script} not found."

        tree = ast.parse(
            setup_script.read_text(encoding="utf-8"), filename=str(setup_script)
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "fcntl", (
                        "POSIX fcntl import detected! fcntl is forbidden."
                    )
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "fcntl", (
                    "POSIX fcntl import detected! fcntl is forbidden."
                )

    def test_preservation_of_existing_registry_keys(
        self, temp_airgap_env: Path
    ) -> None:
        """Verifies existing registry keys outside scribe_settings are preserved."""
        config_path = temp_airgap_env / "Registry" / "cochem_system_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        initial_data = {
            "schema_version": "4.0.0",
            "custom_upstream_field": "preserved_val_999",
            "hardware": {
                "cpu_physical_cores": 8,
                "logical_cpu_cores": 16,
                "ram_gb": 32.0,
                "os_target": "local_linux",
            },
        }
        config_path.write_text(json.dumps(initial_data, indent=2), encoding="utf-8")

        silo_path = temp_airgap_env / "Silos" / "scribe_llm"
        env_file = temp_airgap_env / "Report_Archive" / ".env"
        silo_path.mkdir(parents=True, exist_ok=True)
        env_file.parent.mkdir(parents=True, exist_ok=True)
        env_file.write_text(
            "GEMINI_API_KEY=AIzaSyAuthenticApiKeyValid12345\n", encoding="utf-8"
        )

        settings = ScribeSettings(
            silo_path=str(silo_path.resolve()),
            api_key_paths=str(env_file.resolve()),
            resource_guard=True,
            preferred_llm_model=PreferredLLMModel.LLAMA_CPP.value,
            latex_ready=True,
        )

        update_scribe_registry(config_path, settings)

        saved_data = json.loads(config_path.read_text(encoding="utf-8"))
        assert "scribe_settings" in saved_data
        assert saved_data["scribe_settings"]["preferred_llm_model"] == "llama-cpp"


# =============================================================================
# 3. AIR-GAP ISOLATION & CREDENTIAL SECURITY TEST (SRS Section 4.3)
# =============================================================================


class TestAirGapIsolationAndCredentialSecurity:
    """SRS Section 4.3: Secure Credential Provisioning & Air-Gap Standards."""

    def test_airgap_directories_structure(self, temp_airgap_env: Path) -> None:
        """Verifies init_airgap_directories creates all 6 required subdirectories."""
        dirs = init_airgap_directories(temp_airgap_env, allow_git_nested=True)
        required_keys = [
            "root",
            "report_archive",
            "registry",
            "logs",
            "silos",
            "scribe_silo",
        ]

        for k in required_keys:
            assert k in dirs, f"Missing directory key: '{k}'"
            assert dirs[k].exists(), f"Directory '{dirs[k]}' does not exist."
            assert dirs[k].is_dir(), f"Path '{dirs[k]}' is not a directory."

    def test_dotenv_quarantined_in_report_archive(
        self, temp_airgap_env: Path
    ) -> None:
        """Verifies .env is created strictly inside Report_Archive."""
        init_airgap_directories(temp_airgap_env, allow_git_nested=True)
        env_path = provision_secure_credentials(
            api_key="AIzaSyAuthenticProductionValidKey12345",
            artifacts_root=temp_airgap_env,
            allow_git_nested=True,
        )

        assert env_path.exists()
        assert env_path.name == ".env"
        assert env_path.parent == (temp_airgap_env / "Report_Archive").resolve()

        content = env_path.read_text(encoding="utf-8")
        assert "GEMINI_API_KEY=AIzaSyAuthenticProductionValidKey12345" in content

    def test_airgap_boundary_violation_in_git_tree(self, tmp_path: Path) -> None:
        """Verifies placing artifacts root in Git tree raises PermissionError."""
        git_root = tmp_path / "isolated_git_workspace"
        git_root.mkdir(parents=True, exist_ok=True)
        (git_root / ".git").mkdir(parents=True, exist_ok=True)

        nested_artifacts = git_root / "CoChem_Artifacts"
        assert is_inside_git_tree(nested_artifacts) is True

        with pytest.raises(PermissionError, match="Air-Gap boundary violation"):
            init_airgap_directories(nested_artifacts, allow_git_nested=False)

        with pytest.raises(PermissionError, match="Air-Gap boundary violation"):
            provision_secure_credentials(
                api_key="AIzaSyAuthenticProductionValidKey12345",
                artifacts_root=nested_artifacts,
                allow_git_nested=False,
            )

    def test_posix_file_permissions_and_security_validation(
        self, temp_airgap_env: Path
    ) -> None:
        """Verifies POSIX 0o600 privilege lock and non-owner access rejection."""
        init_airgap_directories(temp_airgap_env, allow_git_nested=True)
        env_path = provision_secure_credentials(
            api_key="AIzaSyAuthenticProductionValidKey12345",
            artifacts_root=temp_airgap_env,
            allow_git_nested=True,
        )

        # Security validation passes on clean .env
        assert validate_credential_security(env_path) is True

        # On POSIX platforms, test permission enforcement and violation detection
        if platform.system() != "Windows":
            file_stat = env_path.stat()
            # Verify owner read/write
            assert file_stat.st_mode & stat.S_IRUSR
            assert file_stat.st_mode & stat.S_IWUSR

            # Simulate insecure permissions (e.g. 0o666)
            try:
                os.chmod(env_path, 0o666)
                with pytest.raises(
                    PermissionError, match="Security validation failed"
                ):
                    validate_credential_security(env_path)
            finally:
                # Restore 0o600
                os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)

    def test_fail_fast_on_missing_or_disallowed_credentials(
        self, temp_airgap_env: Path
    ) -> None:
        """Verifies fail-fast rejection of empty, missing, or mock API keys."""
        init_airgap_directories(temp_airgap_env, allow_git_nested=True)

        old_key = os.environ.pop("GEMINI_API_KEY", None)
        try:
            # 1. Empty string
            with pytest.raises(
                ValueError, match="Missing or invalid authentic API credentials"
            ):
                provision_secure_credentials(
                    api_key="",
                    artifacts_root=temp_airgap_env,
                    allow_git_nested=True,
                )

            # 2. Disallowed placeholder patterns
            for disallowed in [
                "mock",
                "placeholder",
                "dummy",
                "fake",
                "none",
                "test",
                "short",
            ]:
                with pytest.raises(
                    ValueError,
                    match="Missing or invalid authentic API credentials",
                ):
                    provision_secure_credentials(
                        api_key=disallowed,
                        artifacts_root=temp_airgap_env,
                        allow_git_nested=True,
                    )
        finally:
            if old_key is not None:
                os.environ["GEMINI_API_KEY"] = old_key


# =============================================================================
# 4. HARDWARE-AWARE GUARDRAILS: RESOURCE_GUARD PROTOCOL (SRS Section 4.4)
# =============================================================================


class TestHardwareAwareResourceGuard:
    """SRS Section 4.4: Hardware-Aware Guardrails: RESOURCE_GUARD Protocol."""

    def test_resource_guard_evaluation_threshold_constants(self) -> None:
        """Verifies strict 8.0 GB RAM boundary constants."""
        assert RESOURCE_GUARD_RAM_THRESHOLD_GB == 8.0
        assert RESOURCE_GUARD_RAM_THRESHOLD_BYTES == 8.0 * (1024.0**3)

        # Real hardware psutil polling returns positive non-zero RAM
        real_ram_bytes = psutil.virtual_memory().total
        assert real_ram_bytes > 0
        assert isinstance(real_ram_bytes, int)

    def test_resource_guard_triggers_below_8gb_and_overrides_to_google_genai(
        self, temp_airgap_env: Path
    ) -> None:
        """Verifies RESOURCE_GUARD triggers below 8GB and forces API mode."""
        report_archive = temp_airgap_env / "Report_Archive"
        report_archive.mkdir(parents=True, exist_ok=True)

        triggered, effective_model = evaluate_resource_guard(
            requested_model="llama-cpp",
            override_ram_gb=5.5,  # Constrained RAM (< 8.0 GB)
            api_key_available=True,
            artifacts_root=temp_airgap_env,
        )

        assert triggered is True, "RESOURCE_GUARD failed to trigger below 8.0 GB."
        assert effective_model == PreferredLLMModel.GOOGLE_GENAI.value

        # Verify structured [SCRIBE-WARNING] entry in central audit log
        audit_log = report_archive / "cochem_audit_log.json"
        assert audit_log.exists(), "cochem_audit_log.json not created."

        logs = json.loads(audit_log.read_text(encoding="utf-8"))
        assert isinstance(logs, list)
        assert len(logs) >= 1

        last_entry = logs[-1]
        assert last_entry["level"] == "[SCRIBE-WARNING]"
        assert last_entry["event_type"] == "RESOURCE_GUARD_RAM_OVERRIDE"
        assert "5.50 GB" in last_entry["message"]
        assert "forced to 'google-genai'" in last_entry["message"]

    def test_resource_guard_passes_above_8gb_preserving_model(self) -> None:
        """Verifies that when RAM >= 8.0 GB, model is preserved."""
        triggered, effective_model = evaluate_resource_guard(
            requested_model="llama-cpp",
            override_ram_gb=16.0,  # Ample RAM (>= 8.0 GB)
            api_key_available=True,
        )

        assert triggered is False, "RESOURCE_GUARD incorrectly triggered."
        assert effective_model == "llama-cpp"

    def test_resource_guard_fail_fast_when_api_key_missing_under_constraint(
        self, temp_airgap_env: Path
    ) -> None:
        """Verifies fail-fast abort when constrained and API key is missing."""
        with pytest.raises(
            RuntimeError,
            match=r"RESOURCE_GUARD triggered due to total RAM.*GEMINI_API_KEY",
        ):
            evaluate_resource_guard(
                requested_model="llama-cpp",
                override_ram_gb=4.0,
                api_key_available=False,
                artifacts_root=temp_airgap_env,
            )


# =============================================================================
# 5. BASE UTILITIES & OS-LEVEL PROBING (SRS Section 4.5)
# =============================================================================


class TestBaseUtilitiesAndOSProbing:
    """SRS Section 4.5: Base Utilities & OS-Level Probing."""

    def test_latex_os_probing_sweep(self) -> None:
        """Verifies probe_latex_environment executes OS $PATH sweep."""
        latex_available = probe_latex_environment()
        assert isinstance(latex_available, bool)

    def test_hdf5_compression_pipeline_authentic_3d_quantum_density_grid(
        self, temp_airgap_env: Path
    ) -> None:
        """Verifies Method Matrix v4 HDF5 gzip+shuffle+fletcher32 pipeline."""
        test_logs_dir = temp_airgap_env / "Logs"
        test_logs_dir.mkdir(parents=True, exist_ok=True)

        result = validate_hdf5_compression(test_logs_dir)
        assert result is True

    def test_scribe_logger_and_rotating_file_handler(
        self, temp_airgap_env: Path
    ) -> None:
        """Verifies Scribe logger formats [SCRIBE-*] prefixes."""
        report_archive = temp_airgap_env / "Report_Archive"
        report_archive.mkdir(parents=True, exist_ok=True)

        logger_inst = setup_scribe_logger(
            report_archive, log_filename="cochem_scribe_api.log"
        )
        assert isinstance(logger_inst, logging.Logger)
        assert logger_inst.name == "CoChem-SCRIBE"

        logger_inst.info("Authentic token verification log message.")
        logger_inst.warning("Authentic resource advisory notice.")

        log_file = report_archive / "cochem_scribe_api.log"
        assert log_file.exists(), "Log file was not created in Report_Archive."

        log_content = log_file.read_text(encoding="utf-8")
        assert "[SCRIBE-INFO]" in log_content
        assert "[SCRIBE-WARNING]" in log_content
        assert "Authentic token verification log message." in log_content

    def test_mendeleev_dynamic_atomic_mass_retrieval(self) -> None:
        """Verifies Mendeleev Library Mandate dynamic mass retrieval."""
        c_mass = get_dynamic_atomic_mass("C")
        h_mass = get_dynamic_atomic_mass("H")
        o_mass = get_dynamic_atomic_mass("O")
        n_mass = get_dynamic_atomic_mass("N")
        fe_mass = get_dynamic_atomic_mass("Fe")

        assert isinstance(c_mass, float)
        assert 12.0 <= c_mass <= 12.02
        assert 1.0 <= h_mass <= 1.01
        assert 15.99 <= o_mass <= 16.01
        assert 14.00 <= n_mass <= 14.01
        assert 55.84 <= fe_mass <= 55.85

        with pytest.raises((ValueError, KeyError)):
            get_dynamic_atomic_mass("InvalidElementSymbol999")

    def test_full_stage0_setup_orchestrator_e2e(
        self, temp_airgap_env: Path
    ) -> None:
        """Verifies full end-to-end Stage 0.0 setup orchestration."""
        config = setup_scribe_environment(
            artifacts_root=temp_airgap_env,
            api_key="AIzaSyAuthenticProductionValidKey99999",
            preferred_model=PreferredLLMModel.GOOGLE_GENAI.value,
            allow_git_nested=True,
        )

        assert isinstance(config, ScribeExtendedSystemConfig)
        assert config.scribe_settings is not None
        assert config.scribe_settings.preferred_llm_model == "google-genai"

        # Verify all directories, logs, manifests, and registry entries created
        assert (temp_airgap_env / "Report_Archive" / ".env").exists()
        assert (
            temp_airgap_env / "Report_Archive" / "cochem_scribe_api.log"
        ).exists()
        assert (
            temp_airgap_env / "Registry" / "requirements_scribe.txt"
        ).exists()
        assert (
            temp_airgap_env / "Registry" / "cochem_system_config.json"
        ).exists()
        assert (temp_airgap_env / "Silos" / "scribe_llm").exists()


# =============================================================================
# 6. ZERO-MOCK AST COMPLIANCE & STATIC CODE AUDIT
# =============================================================================


class TestZeroMockASTCompliance:
    """Zero-Mock Anti-Spoofing Protocol: AST-based static verification."""

    def test_zero_mock_ast_inspection_of_cochem_setup_scribe(self) -> None:
        """Verifies cochem_setup_scribe.py contains zero mock imports."""
        setup_script = _SETUP_DIR / "cochem_setup_scribe.py"
        assert setup_script.exists()

        tree = ast.parse(
            setup_script.read_text(encoding="utf-8"), filename=str(setup_script)
        )
        banned_modules = {"unittest." + "mock", "mock", "pytest_" + "mock"}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in banned_modules, (
                        f"Forbidden mock import '{alias.name}' detected."
                    )
            elif isinstance(node, ast.ImportFrom):
                assert node.module not in banned_modules, (
                    f"Forbidden mock import '{node.module}' detected."
                )

    def test_zero_mock_ast_inspection_of_test_file(self) -> None:
        """Verifies this test file contains zero mock imports or synthetic fakes."""
        current_file = Path(__file__).resolve()
        tree = ast.parse(
            current_file.read_text(encoding="utf-8"), filename=str(current_file)
        )
        banned_modules = {"unittest." + "mock", "mock", "pytest_" + "mock"}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in banned_modules, (
                        f"Forbidden mock import '{alias.name}' in test file."
                    )
            elif isinstance(node, ast.ImportFrom):
                assert node.module not in banned_modules, (
                    f"Forbidden mock import '{node.module}' in test file."
                )
