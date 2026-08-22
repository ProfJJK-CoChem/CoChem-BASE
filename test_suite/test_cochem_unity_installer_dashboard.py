"""Physical Zero-Mock Test Suite for CoChem-BASE Unity Installer Dashboard.

Validates:
- LF line endings & standard UTF-8 encoding (no BOM).
- Zero personal path leakage across codebase.
- Pydantic DeploymentManifest validation & serialization.
- Ecosystem registry invariants and metadata integrity.
- SynapInstallerGUI pre-flight disk check and widget tree construction.
- ORCA binary verification and archive staging logic.
- Air-Gap ZIP sideloading and deployment worker execution.
- Zombie process cleanup handler execution.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, Dict

import ipywidgets as widgets
import pytest
from pydantic import ValidationError

from cochem_base.config_loader import get_base_root
from cochem_base.interfaces.cochem_unity_installer_dashboard import (
    ECOSYSTEM_REGISTRY,
    DeploymentManifest,
    SynapInstallerGUI,
    _cleanup_zombie_processes,
)
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def target_file_path() -> Path:
    """Return the absolute path to cochem_base/interfaces/cochem_unity_installer_dashboard.py."""
    path = get_base_root() / "cochem_base" / "interfaces" / "cochem_unity_installer_dashboard.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_encoding_and_lf_line_endings(target_file_path: Path) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    raw = target_file_path.read_bytes()
    assert b"\r\n" not in raw, (
        "Found Windows CRLF (\\r\\n) line endings in cochem_unity_installer_dashboard.py"
    )
    assert b"\n" in raw, "Missing newline characters in cochem_unity_installer_dashboard.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), (
        "Found UTF-8 BOM marker in cochem_unity_installer_dashboard.py"
    )

    content = target_file_path.read_text(encoding="utf-8")
    assert len(content) > 500, "File content is unexpectedly small."


def test_zero_personal_path_leaks(target_file_path: Path) -> None:
    """Verify zero personal machine or local user path leakage in target file."""
    lines = target_file_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, (
        f"Detected personal path leaks in cochem_unity_installer_dashboard.py: {leaks}"
    )


def test_deployment_manifest_valid() -> None:
    """Verify DeploymentManifest validates properly with required and optional fields."""
    manifest = DeploymentManifest(
        version="2026.2",
        git_provenance_hash="abcdef0123456789",
        interaction_environment="Local-Windows (WSL)",
        calculation_environment="Local-Windows (WSL)",
        orca_tarball_path="",
        selected_repositories=["CoChem-CORE", "CoChem-TOPOS"],
    )
    assert manifest.version == "2026.2"
    assert manifest.git_provenance_hash == "abcdef0123456789"
    assert manifest.selected_repositories == ["CoChem-CORE", "CoChem-TOPOS"]

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
    mandatory_repos = {"CoChem-CORE", "CoChem-TOPOS", "CoChem-TORQ"}
    for repo in mandatory_repos:
        assert repo in ECOSYSTEM_REGISTRY, f"Mandatory repository '{repo}' missing from registry."
        assert ECOSYSTEM_REGISTRY[repo]["mandatory"] is True, (
            f"Repository '{repo}' must be marked mandatory."
        )

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
    assert len(gui.interaction_options) >= 4
    assert len(gui.calculation_options) >= 5

    ui = gui.build_ui()
    assert isinstance(ui, widgets.Widget)


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
    test_archive.write_bytes(b"dummy archive content")

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
        "orca_5_0_3.tar.gz": {"content": b"mock_tarball_bytes"},
        "CoChem-MAGE.zip": {"content": b"mock_zip_bytes"},
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

    # Create a real zip archive with dummy payload
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
