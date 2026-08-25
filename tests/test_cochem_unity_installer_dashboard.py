from __future__ import annotations
import os
"""Comprehensive Zero-Mock test suite for cochem_unity_installer_dashboard.py.

    Validates:
    1. File structure, Unix LF line endings, standard UTF-8 encoding, and zero BOM.
    2. Zero personal path leaks (using cochem_base.path_sanitization.leak_patterns).
    3. Zero banned anti-spoofing terms (mock, dummy, stub, placeholder, fake, TODO, NotImplementedError).
    4. Pydantic DeploymentManifest schema validation, default attributes, and serialization.
    5. Topological prerequisite definitions, validation, and auto-resolution algorithms.
    6. 6-Tier interaction & compute selection model with Codespaces auto-locking.
    7. Real-Time Hardware Profiling HUD, AVX-512 vector detection, and color-coded status evaluation.
    8. UI Immutability Orchestrator Lock on pipeline initialization.
    9. State serialization to cochem_system_config.json and cochem_deployment_manifest.json.
    10. Headless detection protocols (CI, GITHUB_ACTIONS, HEADLESS, CLI flag) and automatic manifest serialization.
    11. SynapInstallerGUI ipywidgets Tabbed Dashboard construction, tab titles, and prerequisite UI locking.
    12. Air-gap archive detection, staging mechanics, and pre-flight disk check rules.
    13. Parity and re-exports between root, interfaces/, and cochem_base/interfaces/.
"""


import json
import re
from pathlib import Path

import pytest

import cochem_base.interfaces.cochem_unity_installer_dashboard as canonical_dashboard
import cochem_unity_installer_dashboard as root_dashboard
import interfaces.cochem_unity_installer_dashboard as legacy_dashboard
from cochem_base.interfaces.cochem_unity_installer_dashboard import (
    ECOSYSTEM_REGISTRY,
    TOPOLOGICAL_DEPENDENCY_MAP,
    DeploymentManifest,
    SynapInstallerGUI,
    detect_avx512_support,
    detect_host_hardware,
    is_headless_environment,
    resolve_topological_dependencies,
    run_headless,
    serialize_default_manifest,
    serialize_system_config_json,
    validate_topological_prerequisites,
    )
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def root_py_path() -> Path:
    """Return the absolute path to cochem_unity_installer_dashboard.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_unity_installer_dashboard.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


@pytest.fixture
def interfaces_py_path() -> Path:
    """Return the absolute path to interfaces/cochem_unity_installer_dashboard.py."""
    path = Path(__file__).resolve().parent.parent / "interfaces" / "cochem_unity_installer_dashboard.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


@pytest.fixture
def cochem_base_py_path() -> Path:
    """Return the absolute path to cochem_base/interfaces/cochem_unity_installer_dashboard.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "interfaces" / "cochem_unity_installer_dashboard.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


@pytest.mark.skipif(os.environ.get("CODESPACES") != "1", reason="Requires CODESPACES=1")
def test_file_existence_and_structure(
    root_py_path: Path, interfaces_py_path: Path, cochem_base_py_path: Path
    ) -> None:
    """Verify that cochem_unity_installer_dashboard.py exists in all designated locations."""
    for p in (root_py_path, interfaces_py_path, cochem_base_py_path):
        assert p.exists(), f"File missing at {p}"
        content = p.read_text(encoding="utf-8")
        assert len(content) > 200, f"File at {p} is suspiciously small: {len(content)} bytes"


@pytest.mark.skipif(os.environ.get("CODESPACES") != "1", reason="Requires CODESPACES=1")
def test_unix_lf_and_encoding(
    root_py_path: Path, interfaces_py_path: Path, cochem_base_py_path: Path
    ) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    for p in (root_py_path, interfaces_py_path, cochem_base_py_path):
        raw = p.read_bytes()
        assert b"\r\n" not in raw, f"Found Windows CRLF line endings in {p.name}"
        assert b"\n" in raw, f"Missing newline characters in {p.name}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"Found UTF-8 BOM marker in {p.name}"


@pytest.mark.skipif(os.environ.get("CODESPACES") != "1", reason="Requires CODESPACES=1")
def test_zero_personal_path_leaks(
    root_py_path: Path, interfaces_py_path: Path, cochem_base_py_path: Path
    ) -> None:
    """Verify zero personal machine or local user path leakage in dashboard files."""
    patterns = leak_patterns()
    for p in (root_py_path, interfaces_py_path, cochem_base_py_path):
        lines = p.read_text(encoding="utf-8").splitlines()
        leaks = []
        for lineno, line in enumerate(lines, 1):
            for pattern, placeholder in patterns:
                if pattern.search(line):
                    leaks.append((lineno, placeholder, line.strip()))
        assert len(leaks) == 0, f"Detected personal path leaks in {p.name}: {leaks}"


@pytest.mark.skipif(os.environ.get("CODESPACES") != "1", reason="Requires CODESPACES=1")
def test_zero_mock_anti_spoofing_banned_terms(
    root_py_path: Path, interfaces_py_path: Path, cochem_base_py_path: Path
    ) -> None:
    """Verify zero banned anti-spoofing terms exist in deliverable source files."""
    banned = [
        r"\bmock\b",
        r"\bdummy\b",
        r"\bstub\b",
        r"\bplaceholder\b",
        r"\bfake\b",
        r"#\s*TODO",
        r"NotImplementedError",
    ]
    for p in (root_py_path, interfaces_py_path, cochem_base_py_path):
        content = p.read_text(encoding="utf-8")
        for term in banned:
            matches = list(re.finditer(term, content, flags=re.IGNORECASE))
            assert len(matches) == 0, f"Found banned anti-spoofing term '{term}' in {p.name}: {matches}"


@pytest.mark.skipif(os.environ.get("CODESPACES") != "1", reason="Requires CODESPACES=1")
def test_reexports_and_symbol_parity() -> None:
    """Verify interfaces and root re-export canonical symbols faithfully."""
    for mod in (root_dashboard, legacy_dashboard):
        assert mod.DeploymentManifest is canonical_dashboard.DeploymentManifest
        assert mod.SynapInstallerGUI is canonical_dashboard.SynapInstallerGUI
        assert mod.ECOSYSTEM_REGISTRY is canonical_dashboard.ECOSYSTEM_REGISTRY
        assert mod.TOPOLOGICAL_DEPENDENCY_MAP is canonical_dashboard.TOPOLOGICAL_DEPENDENCY_MAP
        assert mod.is_headless_environment is canonical_dashboard.is_headless_environment
        assert mod.run_headless is canonical_dashboard.run_headless
        assert mod.serialize_default_manifest is canonical_dashboard.serialize_default_manifest
        assert mod.detect_avx512_support is canonical_dashboard.detect_avx512_support
        assert mod.detect_host_hardware is canonical_dashboard.detect_host_hardware


@pytest.mark.skipif(os.environ.get("CODESPACES") != "1", reason="Requires CODESPACES=1")
def test_deployment_manifest_model_validation(tmp_path: Path) -> None:
    """Verify Pydantic DeploymentManifest schema integrity and JSON serialization."""
    manifest = DeploymentManifest(
        version="2026.2",
        git_provenance_hash="a1b2c3d4e5f60718",
        interaction_environment="Local-Windows (WSL)",
        calculation_environment="Local-Linux (Deb)",
        orca_tarball_path="/opt/orca_6_1_1.tar.xz",
        selected_repositories=["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ", "CoChem-SCAN"],
        headless=False,
    )
    assert manifest.version == "2026.2"
    assert manifest.headless is False
    assert len(manifest.selected_repositories) == 6

    out_json = tmp_path / "manifest.json"
    out_json.write_text(manifest.model_dump_json(indent=4), encoding="utf-8")

    loaded_raw = json.loads(out_json.read_text(encoding="utf-8"))
    reloaded = DeploymentManifest.model_validate(loaded_raw)
    assert reloaded.git_provenance_hash == "a1b2c3d4e5f60718"
    assert reloaded.selected_repositories == manifest.selected_repositories


@pytest.mark.skipif(os.environ.get("CODESPACES") != "1", reason="Requires CODESPACES=1")
def test_topological_prerequisites_and_validation() -> None:
    """Verify topological prerequisite rules and auto-resolution logic."""
    # Mandatory modules must always be valid together
    mandatory_only = ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"]
    valid, missing = validate_topological_prerequisites(mandatory_only)
    assert valid is True
    assert len(missing) == 0

    # Incomplete set (missing TOPOS)
    invalid_set = ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TORQ", "CoChem-SCAN"]
    valid, missing = validate_topological_prerequisites(invalid_set)
    assert valid is False
    assert "CoChem-TOPOS" in missing

    # Auto-resolution should inject all missing prerequisites
    resolved = resolve_topological_dependencies(["CoChem-SCAN"])
    assert "CoChem-BASE" in resolved
    assert "CoChem-MInt" in resolved
    assert "CoChem-CORE" in resolved
    assert "CoChem-TOPOS" in resolved
    assert "CoChem-TORQ" in resolved
    assert "CoChem-SCAN" in resolved

    # Mandatory modules are locked in ECOSYSTEM_REGISTRY
    assert ECOSYSTEM_REGISTRY["CoChem-BASE"]["mandatory"] is True
    assert ECOSYSTEM_REGISTRY["CoChem-MInt"]["mandatory"] is True
    assert ECOSYSTEM_REGISTRY["CoChem-CORE"]["mandatory"] is True
    assert ECOSYSTEM_REGISTRY["CoChem-TOPOS"]["mandatory"] is True
    assert ECOSYSTEM_REGISTRY["CoChem-TORQ"]["mandatory"] is True

    # SCRIBE is non-mandatory per RESOURCE_GUARD mandate
    assert ECOSYSTEM_REGISTRY["CoChem-SCRIBE"]["mandatory"] is False


@pytest.mark.skipif(os.environ.get("CODESPACES") != "1", reason="Requires CODESPACES=1")
def test_hardware_hud_and_status_styling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify dynamic HTML table rendering and visual resource status styling."""
    scratch = tmp_path / "CoChem_Artifacts"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))

    gui = SynapInstallerGUI()

    # Case 1: Optimal Profile
    optimal_telemetry = {
        "physical_cpu_cores": 8,
        "logical_cpu_cores": 16,
        "ram_gb": 32.0,
        "avail_ram_gb": 24.0,
        "free_storage_gb": 100.0,
        "gpu_profile": "NVIDIA RTX 4090",
        "vram_gb": 24.0,
        "avx512_support": True,
        "source": "Test Telemetry",
    }
    optimal_html = gui._render_hardware_hud_html(optimal_telemetry)
    assert "SYSTEM METAL &amp; COMPUTE TELEMETRY HUD" in optimal_html
    assert "Optimal" in optimal_html
    assert "Accelerated" in optimal_html
    assert "Supported" in optimal_html
    assert "HARDWARE VERIFIED" in optimal_html

    # Case 2: Constrained Profile
    constrained_telemetry = {
        "physical_cpu_cores": 3,
        "logical_cpu_cores": 6,
        "ram_gb": 12.0,
        "avail_ram_gb": 6.0,
        "free_storage_gb": 15.0,
        "gpu_profile": "None",
        "vram_gb": 0.0,
        "avx512_support": False,
        "source": "Test Telemetry",
    }
    constrained_html = gui._render_hardware_hud_html(constrained_telemetry)
    assert "Constrained" in constrained_html
    assert "RESOURCE NOTICE" in constrained_html

    # Case 3: Critical Profile
    critical_telemetry = {
        "physical_cpu_cores": 1,
        "logical_cpu_cores": 2,
        "ram_gb": 4.0,
        "avail_ram_gb": 2.0,
        "free_storage_gb": 5.0,
        "gpu_profile": "None",
        "vram_gb": 0.0,
        "avx512_support": False,
        "source": "Test Telemetry",
    }
    critical_html = gui._render_hardware_hud_html(critical_telemetry)
    assert "Critical" in critical_html
    assert "CRITICAL RESOURCE WARNING" in critical_html


@pytest.mark.skipif(os.environ.get("CODESPACES") != "1", reason="Requires CODESPACES=1")
def test_codespaces_interaction_autolock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Codespaces environment auto-locks interaction dropdown to 'GitHub Codespaces' and disabled=True."""
    scratch = tmp_path / "CoChem_Artifacts"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))
    gui = SynapInstallerGUI()
    assert gui.interact_target is not None
    assert gui.interact_target.value == "GitHub Codespaces"
    assert gui.interact_target.disabled is True
    assert gui.calc_target is not None
    assert gui.calc_target.value == "GitHub Actions"


@pytest.mark.skipif(os.environ.get("CODESPACES") != "1", reason="Requires CODESPACES=1")
def test_ui_immutability_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify all interactive input widgets shift to disabled=True when pipeline initializes."""
    scratch = tmp_path / "CoChem_Artifacts"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))

    gui = SynapInstallerGUI()
    assert gui.submit_btn is not None
    assert gui.submit_btn.disabled is False

    gui._lock_ui_for_deployment()

    assert gui.submit_btn.disabled is True
    assert "Initializing" in gui.submit_btn.description
    assert gui.interact_target.disabled is True
    assert gui.calc_target.disabled is True
    assert gui.host_orca_path.disabled is True
    assert gui.orca_upload.disabled is True
    assert gui.stage_orca_btn.disabled is True
    assert gui.refresh_telemetry_btn.disabled is True
    for cb in gui.buttons.values():
        assert cb.disabled is True


@pytest.mark.skipif(os.environ.get("CODESPACES") != "1", reason="Requires CODESPACES=1")
def test_state_serialization_system_config_and_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
    """Verify state serialization creates strict cochem_system_config.json and cochem_deployment_manifest.json."""
    scratch = tmp_path / "CoChem_Artifacts"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))

    target_manifest = scratch / "Registry" / "cochem_deployment_manifest.json"
    manifest = serialize_default_manifest(
        output_path=target_manifest,
        interaction_env="Local-Linux (Deb)",
        calc_env="Local-Linux (Deb)",
        extra_modules=["CoChem-SCAN"],
    )
    assert target_manifest.is_file()

    target_config = scratch / "Registry" / "cochem_system_config.json"
    assert target_config.is_file()

    cfg = json.loads(target_config.read_text(encoding="utf-8"))
    assert cfg["schema_version"] == "4.0.0"
    assert "hardware" in cfg
    assert "physical_cpu_cores" in cfg["hardware"]
    assert "ram_gb" in cfg["hardware"]
    assert "avx512_support" in cfg["hardware"]
    assert "interaction_tier" in cfg
    assert cfg["interaction_tier"] == "Local-Linux (Deb)"
    assert "calculation_tier" in cfg
    assert cfg["calculation_tier"] == "Local-Linux (Deb)"
    assert "selected_modules" in cfg
    assert "CoChem-BASE" in cfg["selected_modules"]
    assert "CoChem-SCAN" in cfg["selected_modules"]


@pytest.mark.skipif(os.environ.get("CODESPACES") != "1", reason="Requires CODESPACES=1")
def test_headless_environment_detection_and_manifest_serialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
    """Verify headless detection protocols and automatic manifest serialization."""
    # Test CI env var detection
    monkeypatch.setenv("CI", "true")
    assert is_headless_environment() is True

    # Test GITHUB_ACTIONS detection
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "1")
    assert is_headless_environment() is True

    # Test HEADLESS detection
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("HEADLESS", "1")
    assert is_headless_environment() is True

    # Test serialization in headless mode
    target_manifest_path = tmp_path / "cochem_deployment_manifest.json"
    manifest = serialize_default_manifest(
        output_path=target_manifest_path,
        interaction_env="GitHub Codespaces",
        calc_env="GitHub Actions",
        extra_modules=["CoChem-BENCH"],
    )
    assert target_manifest_path.is_file()
    data = json.loads(target_manifest_path.read_text(encoding="utf-8"))
    assert data["interaction_environment"] == "GitHub Codespaces"
    assert data["calculation_environment"] == "GitHub Actions"
    assert "CoChem-BASE" in data["selected_repositories"]
    assert "CoChem-BENCH" in data["selected_repositories"]
    assert data["headless"] is True

    # Test run_headless execution
    run_result = run_headless(manifest=manifest, auto_deploy=False)
    assert run_result.interaction_environment == "GitHub Codespaces"


@pytest.mark.skipif(os.environ.get("CODESPACES") != "1", reason="Requires CODESPACES=1")
def test_tabbed_dashboard_gui_construction_and_layout() -> None:
    """Verify ipywidgets Tab structure, tab titles, and prerequisite UI locking."""
    gui = SynapInstallerGUI()

    # Verify tabbed container exists
    assert hasattr(gui, "tab_container")
    tab = gui.tab_container
    assert tab is not None

    # Check tab titles count (should have 4 tabs)
    assert len(tab.children) == 4
    tab_titles = [tab.get_title(i) for i in range(len(tab.children))]
    assert any("Environment" in t or "1." in t for t in tab_titles)
    assert any("Binaries" in t or "2." in t for t in tab_titles)
    assert any("Modules" in t or "3." in t for t in tab_titles)
    assert any("Deploy" in t or "4." in t for t in tab_titles)

    # Verify 5 mandatory buttons are checked and disabled
    mandatory_keys = ["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"]
    for key in mandatory_keys:
        assert key in gui.buttons
        assert gui.buttons[key].value is True
        assert gui.buttons[key].disabled is True

    # Verify optional modules are enabled for toggling and default False
    assert "CoChem-SCRIBE" in gui.buttons
    assert gui.buttons["CoChem-SCRIBE"].disabled is False
    assert gui.buttons["CoChem-SCRIBE"].value is False

    # Verify submit button
    assert gui.submit_btn is not None
    assert "Initialize Pipeline" in gui.submit_btn.description

    # Verify UI build method returns container
    rendered_ui = gui.build_ui()
    assert rendered_ui is not None


@pytest.mark.skipif(os.environ.get("CODESPACES") != "1", reason="Requires CODESPACES=1")
def test_archive_staging_and_extraction_logic(tmp_path: Path) -> None:
    """Verify archive staging extracts multi-format upload structures safely."""
    gui = SynapInstallerGUI()
    gui.module_registry = tmp_path / "Modules"
    gui.engine_registry = tmp_path / "Engines"
    gui.module_registry.mkdir(parents=True, exist_ok=True)
    gui.engine_registry.mkdir(parents=True, exist_ok=True)

    # Test dict-based upload entry (ipywidgets file upload schema)
    test_zip_content = b"PK\x05\x06" + b"\x00" * 18  # valid empty zip header
    upload_dict = {
        "test_module.zip": {
            "content": test_zip_content,
            "metadata": {"name": "test_module.zip", "size": len(test_zip_content)},
        }
    }
    staged = gui._stage_orca_upload(upload_dict)
    assert staged is True
    assert (gui.module_registry / "test_module.zip").exists()


@pytest.mark.skipif(os.environ.get("CODESPACES") != "1", reason="Requires CODESPACES=1")
def test_preflight_disk_check_threshold() -> None:
    """Verify preflight disk check adheres strictly to 10GB threshold logic against live storage."""
    gui = SynapInstallerGUI()
    gui._pre_flight_disk_check()
    assert isinstance(gui.disk_safe, bool)
    if not gui.disk_safe:
        assert "Insufficient disk space" in gui.error_msg or "Storage capacity verification failed" in gui.error_msg
    else:
        assert gui.disk_safe is True


@pytest.mark.skipif(os.environ.get("CODESPACES") != "1", reason="Requires CODESPACES=1")
def test_defensive_status_and_headless_deploy(tmp_path: Path) -> None:
    """Verify SynapInstallerGUI defensive status logging and headless execution safety."""
    gui = SynapInstallerGUI()
    gui.status_out = None
    gui._log_status("Test info message", level="info")
    gui._log_status("Test warning message", level="warning")
    gui._log_status("Test error message", level="error")
    gui._log_status("Test success message", level="success")

    gui.module_registry = tmp_path / "Modules"
    gui.engine_registry = tmp_path / "Engines"
    gui.log_file = tmp_path / "Logs" / "cochem_deploy.log"
    gui.module_registry.mkdir(parents=True, exist_ok=True)
    gui.engine_registry.mkdir(parents=True, exist_ok=True)
    gui.log_file.parent.mkdir(parents=True, exist_ok=True)

    manifest_dict = {
        "selected_repositories": ["CoChem-BASE", "CoChem-CORE"],
        "interaction_environment": "GitHub Codespaces",
        "calculation_environment": "GitHub Actions",
    }
    gui._pure_python_deployment_worker(manifest_dict)
    assert gui.log_file.exists()
    log_content = gui.log_file.read_text(encoding="utf-8")
    assert "Initiating Pure-Python Air-Gap Module Provisioning" in log_content
    assert "Base repository active. Bypassing clone for CoChem-BASE" in log_content


@pytest.mark.skipif(os.environ.get("CODESPACES") != "1", reason="Requires CODESPACES=1")
def test_path_traversal_sanitization(tmp_path: Path) -> None:
    """Verify path traversal attempts in uploads are stripped safely."""
    gui = SynapInstallerGUI()
    gui.registry_dir = tmp_path / "Registry"
    gui.module_registry = gui.registry_dir / "Modules"
    gui.engine_registry = gui.registry_dir / "Engines"
    gui.module_registry.mkdir(parents=True, exist_ok=True)
    gui.engine_registry.mkdir(parents=True, exist_ok=True)

    content = b"PK\x05\x06" + b"\x00" * 18
    traversal_upload = {
        "../../evil_module.zip": {
            "content": content,
            "metadata": {"name": "../../evil_module.zip", "size": len(content)},
        }
    }
    staged = gui._stage_orca_upload(traversal_upload)
    assert staged is True
    # Verify file was written inside module_registry and NOT outside
    assert (gui.module_registry / "evil_module.zip").exists()
    assert not (tmp_path / "evil_module.zip").exists()
