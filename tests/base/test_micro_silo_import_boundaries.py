"""Real native interpreter imports cannot escape an isolated Stage 0 silo."""

import json
from pathlib import Path
import subprocess
import sys
import venv

import pytest

from cochem_base.orchestrator.micro_silo_manager import MicroSiloValidationError, verify_micro_silo


@pytest.fixture
def actual_silo(tmp_path):
    root = tmp_path / "silo"
    venv.EnvBuilder(with_pip=True).create(root)
    python = root / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    command = "import json,sysconfig; print(json.dumps(sysconfig.get_path('purelib')))"
    site = Path(json.loads(subprocess.check_output([str(python), "-I", "-c", command], text=True)))
    return root, site


def test_genuine_standard_library_and_pinned_pip_origins_are_allowed(actual_silo):
    root, _site = actual_silo
    python = root / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    version = subprocess.check_output([str(python), "-I", "-c", "import importlib.metadata; print(importlib.metadata.version('pip'))"], text=True).strip()
    result = verify_micro_silo(root, python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
                              requirements=[f"pip=={version}"], imports=["json", "math", "sys", "pip"])
    assert result["packages"] == {"pip": version}


def test_actual_imported_module_symlink_outside_silo_is_rejected(actual_silo, tmp_path):
    root, site = actual_silo
    outside = tmp_path / "outside_module.py"
    outside.write_text("BOUNDARY_LABEL = 'Real imported external path'\n", encoding="utf-8")
    (site / "external_import_boundary.py").symlink_to(outside)
    with pytest.raises(MicroSiloValidationError, match="origin or namespace path is outside silo"):
        verify_micro_silo(root, python_version=f"{sys.version_info.major}.{sys.version_info.minor}", imports=["external_import_boundary"])


def test_actual_namespace_directory_symlink_outside_silo_is_rejected(actual_silo, tmp_path):
    root, site = actual_silo
    outside = tmp_path / "outside_namespace"
    outside.mkdir()
    (outside / "retained_data.txt").write_bytes(b"Actual namespace directory boundary\n")
    (site / "external_namespace_boundary").symlink_to(outside, target_is_directory=True)
    with pytest.raises(MicroSiloValidationError, match="origin or namespace path is outside silo"):
        verify_micro_silo(root, python_version=f"{sys.version_info.major}.{sys.version_info.minor}", imports=["external_namespace_boundary"])


def test_inside_unversioned_namespace_is_not_treated_as_standard_library(actual_silo):
    root, site = actual_silo
    (site / "unversioned_namespace_boundary").mkdir()
    with pytest.raises(MicroSiloValidationError, match="unversioned import inside silo"):
        verify_micro_silo(root, python_version=f"{sys.version_info.major}.{sys.version_info.minor}", imports=["unversioned_namespace_boundary"])
