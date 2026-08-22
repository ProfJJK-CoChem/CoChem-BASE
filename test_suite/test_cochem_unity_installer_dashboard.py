"""Physical Zero-Mock Test Suite for CoChem-BASE Unity Installer Dashboard.

Validates:
- LF line endings & standard UTF-8 encoding (no BOM).
- Zero personal path leakage across codebase.
- Pydantic DeploymentManifest validation & serialization.
- Ecosystem registry invariants (5 mandatory modules, 17 total ecosystem modules).
- SynapInstallerGUI pre-flight disk check and widget tree construction.
- Real-time Hardware Profiling HUD, AVX-512 detection, and telemetry rendering.
- 6-Tier interaction & compute selection model with Codespaces auto-lock.
- UI Immutability Orchestrator Lock on pipeline initialization.
- State serialization to cochem_system_config.json and cochem_deployment_manifest.json.
- ORCA binary verification and archive staging logic.
- Air-Gap ZIP sideloading and deployment worker execution.
- Zombie process cleanup handler execution.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any, Dict

import ipywidgets as widgets
import pytest
from pydantic import ValidationError

from cochem_base.config_loader import get_base_root
from cochem_base.interfaces.cochem_unity_installer_dashboard import (
    ECOSYSTEM_REGISTRY,
    TOPOLOGICAL_DEPENDENCY_MAP,
    DeploymentManifest,
    SynapInstallerGUI,
    _cleanup_zombie_processes,
    detect_avx512_support,
    detect_host_hardware,
    resolve_topological_dependencies,
    serialize_default_manifest,
    serialize_system_config_json,
    validate_topological_prerequisites,
)
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def target_file_path() -> Path:
    """Return the absolute path to cochem_base/interfaces/cochem_unity_installer_dashboard.py."""
    path = get_base_root() / "cochem_base" / "interfaces" / "cochem_unity_installer_dashboard.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


@pytest.fixture
def root_file_path() -> Path:
    """Return the absolute path to cochem_unity_installer_dashboard.py."""
    path = get_base_root() / "cochem_unity_installer_dashboard.py"
    assert path.is_file(), f"Root file does not exist: {path}"
    return path


@pytest.fixture
def legacy_file_path() -> Path:
    """Return the absolute path to interfaces/cochem_unity_installer_dashboard.py."""
    path = get_base_root() / "interfaces" / "cochem_unity_installer_dashboard.py"
    assert path.is_file(), f"Legacy file does not exist: {path}"
    return path


def test_file_encoding_and_lf_line_endings(
    target_file_path: Path, root_file_path: Path, legacy_file_path: Path
) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    for p in (target_file_path, root_file_path, legacy_file_path):
        raw = p.read_bytes()
        assert b"\r\n" not in raw, f"Found Windows CRLF line endings in {p.name}"
        assert b"\n" in raw, f"Missing newline characters in {p.name}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"Found UTF-8 BOM marker in {p.name}"

        content = p.read_text(encoding="utf-8")
        assert len(content) > 500, f"File {p.name} content is unexpectedly small."


def test_zero_personal_path_leaks(
    target_file_path: Path, root_file_path: Path, legacy_file_path: Path
) -> None:
    """Verify zero personal machine or local user path leakage in target files."""
    patterns = leak_patterns()
    for p in (target_file_path, root_file_path, legacy_file_path):
        lines = p.read_text(encoding="utf-8").splitlines()
        leaks = []
        for lineno, line in enumerate(lines, 1):
            for pattern, placeholder in patterns:
                if pattern.search(line):
                    leaks.append((lineno, placeholder, line.strip()))

        assert len(leaks) == 0, f"Detected personal path leaks in {p.name}: {leaks}"


def test_deployment_manifest_valid() -> None:
    """Verify DeploymentManifest validates properly with required and optional fields."""
    manifest = DeploymentManifest(
        version="2026.2",
        git_provenance_hash="abcdef0123456789",
        interaction_environment="Local-Windows (WSL)",
        calculation_environment="Local-Windows (WSL)",
        orca_tarball_path="",
        selected_repositories=["CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"],
    )
    assert manifest.version == "2026.2"
    assert manifest.git_provenance_hash == "abcdef0123456789"
    assert "CoChem-BASE" in manifest.selected_repositories
    assert "CoChem-CORE" in manifest.selected_repositories

    dumped = manifest.model_dump()
    assert isinstance(dumped, dict)
    assert dumped["git_provenance_hash"] == "abcdef0123456789"

    json_str = manifest.model_dump_json()
    assert "abcdef0123456789" in json_str


def test_deployment_manifest_validation_error() -> None:
    """Verify DeploymentManifest raises ValidationError when required fields are missing."""
    with pytest.raises(ValidationError):
        DeploymentManifest.model_validate({"version": "2026.2"})


def test_ecosystem_registry_invariants() -> None:
    """Verify ECOSYSTEM_REGISTRY contains all expected repositories with mandatory flags."""
    mandatory_repos = {"CoChem-BASE", "CoChem-MInt", "CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"}
    for repo in mandatory_repos:
        assert repo in ECOSYSTEM_REGISTRY, f"Mandatory repository '{repo}' missing from registry."
        assert ECOSYSTEM_REGISTRY[repo]["mandatory"] is True, (
            f"Repository '{repo}' must be marked mandatory."
        )

    assert len(ECOSYSTEM_REGISTRY) == 17, f"Expected 17 ecosystem modules, found {len(ECOSYSTEM_REGISTRY)}"

    for _name, data in ECOSYSTEM_REGISTRY.items():
        assert "desc" in data and len(data["desc"]) > 5
        assert "repo" in data and data["repo"].startswith("https://")
        assert "mandatory" in data and isinstance(data["mandatory"], bool)


def test_synap_installer_gui_initialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify SynapInstallerGUI initializes correctly and creates necessary directories."""
    scratch = tmp_path / "CoChem_Artifacts"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))

    gui = SynapInstallerGUI()
    assert gui.disk_safe is True
    assert gui.engine_registry.exists()
    assert gui.module_registry.exists()
    assert len(gui.interaction_options) == 6
    assert len(gui.calculation_options) == 5
    assert "GitHub Codespaces" in gui.interaction_options
    assert "Local-Windows (WSL)" in gui.interaction_options

    ui = gui.build_ui()
    assert isinstance(ui, widgets.Widget)


def test_hardware_hud_and_avx512_detection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify hardware telemetry collection and dynamic HUD table rendering."""
    scratch = tmp_path / "CoChem_Artifacts"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))

    # Test AVX-512 detection functions
    avx512 = detect_avx512_support()
    assert isinstance(avx512, bool)

    monkeypatch.setenv("COCHEM_FORCE_AVX512", "1")
    assert detect_avx512_support() is True

    monkeypatch.setenv("COCHEM_FORCE_AVX512", "0")
    assert detect_avx512_support() is False

    monkeypatch.delenv("COCHEM_FORCE_AVX512", raising=False)

    # Test Hardware telemetry collection
    telemetry = detect_host_hardware()
    assert "physical_cpu_cores" in telemetry
    assert "logical_cpu_cores" in telemetry
    assert "ram_gb" in telemetry
    assert "vram_gb" in telemetry
    assert "avx512_support" in telemetry
    assert telemetry["physical_cpu_cores"] >= 1
    assert telemetry["ram_gb"] > 0.0

    gui = SynapInstallerGUI()
    hud_content = gui._render_hardware_hud_html(telemetry)
    assert "SYSTEM METAL &amp; COMPUTE TELEMETRY HUD" in hud_content
    assert "System RAM" in hud_content
    assert "CPU Cores" in hud_content
    assert "GPU Accelerator" in hud_content
    assert "Vector ISA (AVX-512)" in hud_content

    gui.refresh_hardware_hud()
    assert gui.hud_html is not None
    assert len(gui.hud_html.value) > 100


def test_codespaces_interaction_autolock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Codespaces auto-lock sets value to 'GitHub Codespaces' and disabled=True."""
    scratch = tmp_path / "CoChem_Artifacts"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))
    monkeypatch.setenv("CODESPACES", "true")

    gui = SynapInstallerGUI()
    assert gui.interact_target is not None
    assert gui.interact_target.value == "GitHub Codespaces"
    assert gui.interact_target.disabled is True
    assert gui.calc_target is not None
    assert gui.calc_target.value == "GitHub Actions"


def test_orchestrator_lock_ui_immutability(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify all ipywidgets inputs shift to disabled=True upon pipeline initialization."""
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


def test_state_serialization_system_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify state serialization creates strict cochem_system_config.json without hardcoded home."""
    scratch = tmp_path / "CoChem_Artifacts"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))

    target_manifest = scratch / "Registry" / "cochem_deployment_manifest.json"
    manifest = serialize_default_manifest(output_path=target_manifest)

    assert target_manifest.exists()
    system_config_file = scratch / "Registry" / "cochem_system_config.json"
    assert system_config_file.exists()

    config_data = json.loads(system_config_file.read_text(encoding="utf-8"))
    assert config_data["schema_version"] == "4.0.0"
    assert "hardware" in config_data
    assert "ram_gb" in config_data["hardware"]
    assert "physical_cpu_cores" in config_data["hardware"]
    assert "avx512_support" in config_data["hardware"]
    assert "interaction_tier" in config_data
    assert "calculation_tier" in config_data
    assert "selected_modules" in config_data
    assert "CoChem-BASE" in config_data["selected_modules"]


def test_git_hash_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _get_git_hash returns a valid hash string."""
    scratch = tmp_path / "CoChem_Artifacts"
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))
    gui = SynapInstallerGUI()

    git_hash = gui._get_git_hash()
    assert isinstance(git_hash, str)
    assert len(git_hash) > 0
    assert len(git_hash) <= 16


def test_has_staged_orca_archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _has_staged_orca_archive accurately detects staged tarballs."""
    scratch = tmp_path / "CoChem_Artifacts"
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))
    gui = SynapInstallerGUI()

    assert gui._has_staged_orca_archive() is False

    test_archive = gui.engine_registry / "orca_5_0_4_linux_x86-64.tar.xz"
    test_archive.write_bytes(b"sample archive payload bytes")

    assert gui._has_staged_orca_archive() is True


def test_extract_upload_entries_and_stage_orca(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify archive staging from file upload structures."""
    scratch = tmp_path / "CoChem_Artifacts"
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))
    gui = SynapInstallerGUI()

    # Test dict input format
    files_dict = {
        "orca_5_0_3.tar.gz": {"content": b"tarball_content_payload"},
        "CoChem-MAGE.zip": {"content": b"zip_content_payload"},
    }
    staged = gui._stage_orca_upload(files_dict)
    assert staged is True
    assert (gui.engine_registry / "orca_5_0_3.tar.gz").exists()
    assert (gui.module_registry / "CoChem-MAGE.zip").exists()


def test_verify_host_orca_path_nonexistent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _verify_host_orca_path returns False for invalid or missing executable paths."""
    scratch = tmp_path / "CoChem_Artifacts"
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))
    gui = SynapInstallerGUI()

    # Explicitly invalid path must always return False
    assert gui._verify_host_orca_path("/non/existent/custom/path/orca_xyz_123") is False
    assert gui._verify_host_orca_path("C:\\non_existent_orca_binary.exe") is False


def test_pure_python_deployment_airgap_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Air-Gap Zip Sideloading extracts target module without network calls."""
    scratch = tmp_path / "CoChem_Artifacts"
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(scratch))
    gui = SynapInstallerGUI()

    target_mod = "CoChem-BENCH"
    zip_path = gui.module_registry / f"{target_mod}.zip"

    # Create a real zip archive with valid payload
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(f"{target_mod}/__init__.py", "# Bench module init\n")
        zf.writestr(f"{target_mod}/bench_core.py", "def run(): pass\n")

    manifest_payload: Dict[str, Any] = {
        "version": "2026.2",
        "git_provenance_hash": "test_hash",
        "interaction_environment": "Local-Linux (Deb)",
        "calculation_environment": "Local-Linux (Deb)",
        "orca_tarball_path": "",
        "selected_repositories": [target_mod],
    }

    gui._pure_python_deployment_worker(manifest_payload)

    extracted_dir = gui.module_registry / target_mod
    assert extracted_dir.is_dir()
    assert (extracted_dir / "__init__.py").exists()
    assert (extracted_dir / "bench_core.py").exists()

    log_content = gui.log_file.read_text(encoding="utf-8")
    assert "Air-Gap Bridge: Sideloading" in log_content
    assert "Extracted CoChem-BENCH via Air-Gap" in log_content


def test_zombie_cleanup_callable() -> None:
    """Verify _cleanup_zombie_processes executes safely without throwing exceptions."""
    _cleanup_zombie_processes()
