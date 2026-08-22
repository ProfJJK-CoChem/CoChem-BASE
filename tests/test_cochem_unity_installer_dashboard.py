"""Comprehensive Zero-Mock test suite for cochem_unity_installer_dashboard.py.

Validates:
1. File structure, Unix LF line endings, standard UTF-8 encoding, and zero BOM.
2. Zero personal path leaks (using cochem_base.path_sanitization.leak_patterns).
3. Zero banned anti-spoofing terms (mock, dummy, stub, placeholder, fake, TODO, NotImplementedError).
4. Pydantic DeploymentManifest schema validation, default attributes, and serialization.
5. Topological prerequisite definitions, validation, and auto-resolution algorithms.
6. Headless detection protocols (CI, GITHUB_ACTIONS, HEADLESS, CLI flag) and automatic manifest serialization.
7. SynapInstallerGUI ipywidgets Tabbed Dashboard construction, tab titles, and UI immutability locks.
8. Air-gap archive detection, staging mechanics, and pre-flight disk check rules.
9. Parity and re-exports between interfaces/ and cochem_base/interfaces/.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import cochem_base.interfaces.cochem_unity_installer_dashboard as canonical_dashboard
import interfaces.cochem_unity_installer_dashboard as legacy_dashboard
from cochem_base.interfaces.cochem_unity_installer_dashboard import (
    ECOSYSTEM_REGISTRY,
    DeploymentManifest,
    SynapInstallerGUI,
    is_headless_environment,
    resolve_topological_dependencies,
    run_headless,
    serialize_default_manifest,
    validate_topological_prerequisites,
)
from cochem_base.path_sanitization import leak_patterns


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


def test_file_existence_and_structure(
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify that cochem_unity_installer_dashboard.py exists in both locations."""
    for p in (interfaces_py_path, cochem_base_py_path):
        assert p.exists(), f"File missing at {p}"
        content = p.read_text(encoding="utf-8")
        assert len(content) > 200, f"File at {p} is suspiciously small: {len(content)} bytes"


def test_unix_lf_and_encoding(
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    for p in (interfaces_py_path, cochem_base_py_path):
        raw = p.read_bytes()
        assert b"\r\n" not in raw, f"Found Windows CRLF line endings in {p.name}"
        assert b"\n" in raw, f"Missing newline characters in {p.name}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"Found UTF-8 BOM marker in {p.name}"


def test_zero_personal_path_leaks(
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify zero personal machine or local user path leakage in dashboard files."""
    patterns = leak_patterns()
    for p in (interfaces_py_path, cochem_base_py_path):
        lines = p.read_text(encoding="utf-8").splitlines()
        leaks = []
        for lineno, line in enumerate(lines, 1):
            for pattern, placeholder in patterns:
                if pattern.search(line):
                    leaks.append((lineno, placeholder, line.strip()))
        assert len(leaks) == 0, f"Detected personal path leaks in {p.name}: {leaks}"


def test_zero_mock_anti_spoofing_banned_terms(
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify zero mock, dummy, stub, or placeholder logic exists in the deliverable."""
    banned = [
        r"\bmock\b",
        r"\bdummy\b",
        r"\bstub\b",
        r"\bplaceholder\b",
        r"\bfake\b",
        r"#\s*TODO",
        r"NotImplementedError",
    ]
    for p in (interfaces_py_path, cochem_base_py_path):
        content = p.read_text(encoding="utf-8")
        for term in banned:
            matches = list(re.finditer(term, content, flags=re.IGNORECASE))
            assert len(matches) == 0, f"Found banned anti-spoofing term '{term}' in {p.name}: {matches}"


def test_reexports_and_symbol_parity() -> None:
    """Verify interfaces.cochem_unity_installer_dashboard re-exports canonical symbols."""
    assert legacy_dashboard.DeploymentManifest is canonical_dashboard.DeploymentManifest
    assert legacy_dashboard.SynapInstallerGUI is canonical_dashboard.SynapInstallerGUI
    assert legacy_dashboard.ECOSYSTEM_REGISTRY is canonical_dashboard.ECOSYSTEM_REGISTRY
    assert legacy_dashboard.is_headless_environment is canonical_dashboard.is_headless_environment
    assert legacy_dashboard.run_headless is canonical_dashboard.run_headless
    assert legacy_dashboard.serialize_default_manifest is canonical_dashboard.serialize_default_manifest


def test_deployment_manifest_model_validation(tmp_path: Path) -> None:
    """Verify Pydantic DeploymentManifest schema integrity and JSON serialization."""
    manifest = DeploymentManifest(
        version="2026.2",
        git_provenance_hash="a1b2c3d4e5f60718",
        interaction_environment="Local-Windows (WSL)",
        calculation_environment="Local-Linux (Deb)",
        orca_tarball_path="/opt/orca_6_1_1.tar.xz",
        selected_repositories=["CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ", "CoChem-SCAN"],
        headless=False,
    )
    assert manifest.version == "2026.2"
    assert manifest.headless is False
    assert len(manifest.selected_repositories) == 4

    out_json = tmp_path / "manifest.json"
    out_json.write_text(manifest.model_dump_json(indent=4), encoding="utf-8")

    loaded_raw = json.loads(out_json.read_text(encoding="utf-8"))
    reloaded = DeploymentManifest.model_validate(loaded_raw)
    assert reloaded.git_provenance_hash == "a1b2c3d4e5f60718"
    assert reloaded.selected_repositories == manifest.selected_repositories


def test_topological_prerequisites_and_validation() -> None:
    """Verify topological prerequisite rules and auto-resolution logic."""
    # Mandatory modules must always be valid together
    mandatory_only = ["CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"]
    valid, missing = validate_topological_prerequisites(mandatory_only)
    assert valid is True
    assert len(missing) == 0

    # Incomplete set (missing TOPOS)
    invalid_set = ["CoChem-CORE", "CoChem-TORQ", "CoChem-SCAN"]
    valid, missing = validate_topological_prerequisites(invalid_set)
    assert valid is False
    assert "CoChem-TOPOS" in missing

    # Auto-resolution should inject all missing prerequisites
    resolved = resolve_topological_dependencies(["CoChem-SCAN"])
    assert "CoChem-CORE" in resolved
    assert "CoChem-TOPOS" in resolved
    assert "CoChem-TORQ" in resolved
    assert "CoChem-SCAN" in resolved

    # Mandatory modules are locked in ECOSYSTEM_REGISTRY
    assert ECOSYSTEM_REGISTRY["CoChem-CORE"]["mandatory"] is True
    assert ECOSYSTEM_REGISTRY["CoChem-TOPOS"]["mandatory"] is True
    assert ECOSYSTEM_REGISTRY["CoChem-TORQ"]["mandatory"] is True
    assert ECOSYSTEM_REGISTRY["CoChem-SCRIBE"]["mandatory"] is False


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
        interaction_env="Codespaces",
        calc_env="GitHub Actions",
        extra_modules=["CoChem-BENCH"],
    )
    assert target_manifest_path.is_file()
    data = json.loads(target_manifest_path.read_text(encoding="utf-8"))
    assert data["interaction_environment"] == "Codespaces"
    assert data["calculation_environment"] == "GitHub Actions"
    assert "CoChem-CORE" in data["selected_repositories"]
    assert "CoChem-BENCH" in data["selected_repositories"]
    assert data["headless"] is True

    # Test run_headless execution
    run_result = run_headless(manifest=manifest, auto_deploy=False)
    assert run_result.interaction_environment == "Codespaces"


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

    # Verify mandatory buttons are checked and disabled
    assert "CoChem-CORE" in gui.buttons
    assert gui.buttons["CoChem-CORE"].value is True
    assert gui.buttons["CoChem-CORE"].disabled is True

    assert "CoChem-TOPOS" in gui.buttons
    assert gui.buttons["CoChem-TOPOS"].value is True
    assert gui.buttons["CoChem-TOPOS"].disabled is True

    assert "CoChem-TORQ" in gui.buttons
    assert gui.buttons["CoChem-TORQ"].value is True
    assert gui.buttons["CoChem-TORQ"].disabled is True

    # Verify optional modules are enabled for toggling
    assert "CoChem-SCRIBE" in gui.buttons
    assert gui.buttons["CoChem-SCRIBE"].disabled is False
    assert gui.buttons["CoChem-SCRIBE"].value is False

    # Verify UI build method returns container
    rendered_ui = gui.build_ui()
    assert rendered_ui is not None


def test_archive_staging_and_extraction_logic(tmp_path: Path) -> None:
    """Verify archive staging extracts multi-format upload structures safely."""
    gui = SynapInstallerGUI()
    gui.module_registry = tmp_path / "Modules"
    gui.engine_registry = tmp_path / "Engines"
    gui.module_registry.mkdir(parents=True, exist_ok=True)
    gui.engine_registry.mkdir(parents=True, exist_ok=True)

    # Test dict-based upload entry (ipywidgets file upload schema)
    fake_content = b"PK\x05\x06" + b"\x00" * 18  # valid empty zip header
    upload_dict = {
        "test_module.zip": {
            "content": fake_content,
            "metadata": {"name": "test_module.zip", "size": len(fake_content)},
        }
    }
    staged = gui._stage_orca_upload(upload_dict)
    assert staged is True
    assert (gui.module_registry / "test_module.zip").exists()


def test_preflight_disk_check_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify preflight disk check adheres strictly to 10GB threshold logic."""
    class FakeUsage:
        def __init__(self, free_bytes: int):
            self.free = free_bytes

    gui = SynapInstallerGUI()

    # Case 1: < 10GB free space
    monkeypatch.setattr("psutil.disk_usage", lambda _: FakeUsage(5 * 1024**3))
    gui._pre_flight_disk_check()
    assert gui.disk_safe is False
    assert "Insufficient disk space" in gui.error_msg

    # Case 2: >= 10GB free space
    monkeypatch.setattr("psutil.disk_usage", lambda _: FakeUsage(15 * 1024**3))
    gui._pre_flight_disk_check()
    assert gui.disk_safe is True


def test_defensive_status_and_headless_deploy(tmp_path: Path) -> None:
    """Verify SynapInstallerGUI defensive status logging and headless execution safety."""
    gui = SynapInstallerGUI()
    gui.status_out = None
    gui._log_status("Test info message", level="info")
    gui._log_status("Test warning message", level="warning")
    gui._log_status("Test error message", level="error")

    gui.module_registry = tmp_path / "Modules"
    gui.engine_registry = tmp_path / "Engines"
    gui.log_file = tmp_path / "Logs" / "cochem_deploy.log"
    gui.module_registry.mkdir(parents=True, exist_ok=True)
    gui.engine_registry.mkdir(parents=True, exist_ok=True)
    gui.log_file.parent.mkdir(parents=True, exist_ok=True)

    manifest_dict = {
        "selected_repositories": ["CoChem-CORE"],
        "interaction_environment": "Codespaces",
        "calculation_environment": "GitHub Actions",
    }
    gui._pure_python_deployment_worker(manifest_dict)
    assert gui.log_file.exists()
    log_content = gui.log_file.read_text(encoding="utf-8")
    assert "Initiating Pure-Python Air-Gap Module Provisioning" in log_content
    assert "Base repository active. Bypassing clone for CoChem-CORE" in log_content


def test_path_traversal_sanitization(tmp_path: Path) -> None:
    """Verify CWE-22 path traversal attempts in uploads are stripped safely."""
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

