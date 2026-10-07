"""Real handoff rejection and isolated-install provenance at module execution.

The shared tiny wheel is a packaging boundary fixture, never a scientific engine.
Successful downstream chemistry remains a separate real-provider acceptance run.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from cochem_base.interfaces.artifact_handoff import prepare_module_handoff
from cochem_base.interfaces.module_execution import (
    execute_module_handoff,
    installed_module_status,
)
from scripts import manage_modules as installer
from tests.base.test_module_installer import git, install_fixture, repository  # noqa: F401; shared real Git fixture


@pytest.fixture
def geometry(tmp_path):
    path = tmp_path / "water.xyz"
    path.write_text("3\nGeometry input, no energy observation\nO 0 0 0\nH .757 .587 0\nH -.757 .587 0\n")
    return path


def _handoff(geometry, destination, *, module="topos", operation="geometry_analysis", options=None):
    prepare_module_handoff(module, geometry, destination, operation=operation, options=options)
    return destination / "handoff.json"


@pytest.mark.parametrize("module,operation", [("base", "geometry_analysis"), ("topos", "conformer_search")])
def test_unreviewed_recipient_or_operation_never_starts(geometry, tmp_path, module, operation):
    handoff = _handoff(geometry, tmp_path / "handoff", module=module, operation=operation)
    output = tmp_path / "result"
    with pytest.raises(ValueError, match="no reviewed execution adapter"):
        execute_module_handoff(handoff, output, root=tmp_path / "absent-installation")
    assert not output.exists()


def test_unknown_module_identifier_never_publishes_handoff(geometry, tmp_path):
    with pytest.raises(ValueError, match="Unknown ecosystem"):
        _handoff(geometry, tmp_path / "handoff", module="not_a_cochem_module")
    assert not (tmp_path / "handoff").exists()


def test_geometry_options_are_not_forwarded_as_commands(geometry, tmp_path):
    handoff = _handoff(geometry, tmp_path / "handoff", options={"command": "arbitrary-shell-input"})
    with pytest.raises(ValueError, match="accepts no options"):
        execute_module_handoff(handoff, tmp_path / "result", root=tmp_path / "modules")
    assert not (tmp_path / "result").exists()


def test_copied_artifact_tampering_is_detected_before_installation(geometry, tmp_path):
    handoff = _handoff(geometry, tmp_path / "handoff")
    copied = handoff.parent / "artifact.xyz"
    copied.write_text(copied.read_text().replace(".757", ".758"))
    with pytest.raises(ValueError, match="integrity verification failed"):
        execute_module_handoff(handoff, tmp_path / "result", root=tmp_path / "modules")
    assert not (tmp_path / "result").exists()


def test_arbitrary_json_cannot_be_used_as_execution_authority(tmp_path):
    source = tmp_path / "not-a-handoff.json"
    source.write_text(json.dumps({"module_id": "topos", "operation": "geometry_analysis", "command": "run-anything"}))
    with pytest.raises(ValueError):
        execute_module_handoff(source, tmp_path / "result", root=tmp_path / "modules")
    assert not (tmp_path / "result").exists()


def test_missing_installation_is_not_reported_as_execution(geometry, tmp_path):
    handoff = _handoff(geometry, tmp_path / "handoff")
    with pytest.raises(installer.ModuleInstallationError, match="Cannot read a valid module receipt.*installation.json"):
        execute_module_handoff(handoff, tmp_path / "result", root=tmp_path / "modules")
    assert not (tmp_path / "result").exists()


def test_geometry_adapter_rejects_real_periodic_structure_input(tmp_path):
    source = Path(__file__).resolve().parents[2] / "examples/product_b/gaas_fractional.json"
    handoff = _handoff(source, tmp_path / "handoff")
    with pytest.raises(ValueError, match="single XYZ geometry"):
        execute_module_handoff(handoff, tmp_path / "result", root=tmp_path / "modules")
    assert not (tmp_path / "result").exists()


def test_bound_on_geometry_size_applies_before_provider_start(tmp_path):
    source = tmp_path / "large.xyz"
    source.write_text("2001\nDeliberate operation-budget boundary input\n" + "".join(f"H {i * 2} 0 0\n" for i in range(2001)))
    handoff = _handoff(source, tmp_path / "handoff")
    with pytest.raises(ValueError, match="at most 2000 atoms"):
        execute_module_handoff(handoff, tmp_path / "result", root=tmp_path / "modules")
    assert not (tmp_path / "result").exists()


def test_missing_and_invalid_installations_stay_unavailable(tmp_path):
    root = tmp_path / "modules"
    statuses = installed_module_status(root)
    assert {item["status"] for item in statuses} == {"not_installed"}
    assert all(item["operations"] == [] and item["scientific_execution_verified"] is False for item in statuses)
    (root / "topos").mkdir(parents=True)
    (root / "topos/installation.json").write_text("{}")
    topos = next(item for item in installed_module_status(root) if item["module_id"] == "topos")
    assert topos["status"] == "installation_invalid"
    assert topos["operations"] == []
    assert topos["scientific_execution_verified"] is False
    assert "specification" in topos["reason"]


def test_provider_environment_removes_credentials_and_injection():
    blocked = ["COCHEM_SOURCE_READ_TOKEN", "ORCA_ASSET_READ_TOKEN", "GITHUB_TOKEN", "GH_TOKEN",
               "MY_API_KEY", "PRIVATE_PASSWORD", "SOURCE_CREDENTIAL", "MY_SECRET", "GIT_CONFIG_COUNT",
               "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0", "GIT_ASKPASS", "SSH_ASKPASS", "PYTHONPATH",
               "PYTHONHOME", "PYTHONUSERBASE", "VIRTUAL_ENV", "LD_PRELOAD", "LD_LIBRARY_PATH"]
    child_environment = installer._build_env()
    child_environment.update(dict.fromkeys(blocked, "boundary-test-value"))
    child_environment["COCHEM_OPERATION_TEST_LABEL"] = "ordinary-setting"
    program = """
import json, sys
from cochem_base.interfaces.module_execution import _environment
environment = _environment()
print(json.dumps({"remaining_blocked_names": sorted(set(json.loads(sys.argv[1])) & environment.keys()),
    "ordinary_setting": environment.get("COCHEM_OPERATION_TEST_LABEL"),
    "threads": environment.get("OMP_NUM_THREADS"),
    "no_user_site": environment.get("PYTHONNOUSERSITE")}))
"""
    result = subprocess.run([sys.executable, "-I", "-B", "-c", program, json.dumps(blocked)],
                            env=child_environment, capture_output=True, text=True, check=True, timeout=30)
    observed = json.loads(result.stdout)
    assert observed == {"remaining_blocked_names": [], "ordinary_setting": "ordinary-setting",
                        "threads": "1", "no_user_site": "1"}


def test_cli_lists_reviewed_modules_without_installing(tmp_path):
    root = tmp_path / "modules"
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-m", "cochem_base.cli", "modules", "list", "--root", str(root), "--json"],
        cwd=tmp_path, env=installer._build_env(), capture_output=True, text=True, check=True, timeout=30,
    )
    catalog = json.loads(result.stdout)
    assert catalog == installer.load_manifest()
    assert catalog["modules"]["topos"]["operations"] == ["geometry_analysis"]
    assert catalog["modules"]["torq"]["operations"] == ["geometry_analysis"]
    assert not root.exists()


@pytest.fixture
def execution_installation(repository, tmp_path):
    origin, fixture_spec, root = repository
    # This real wheel has no geometry provider; tests must reject before dispatch.
    spec = dict(fixture_spec, adapter="topos_geometry")
    receipt = install_fixture("topos", spec, root, origin)
    manifest = tmp_path / "fixture-distribution.json"
    manifest.write_text(json.dumps({"schema_version": installer.MANIFEST_SCHEMA, "modules": {"topos": spec}}))
    return spec, root, receipt, manifest


def test_execution_destination_cannot_be_inside_base_checkout(geometry, tmp_path, execution_installation):
    from cochem.core.context import AirGapViolationError

    _spec, root, _receipt, manifest = execution_installation
    handoff = _handoff(geometry, tmp_path / "handoff")
    output = Path(__file__).resolve().parents[2] / "forbidden-module-execution"
    with pytest.raises(AirGapViolationError):
        execute_module_handoff(handoff, output, root=root, manifest=manifest)
    assert not output.exists()


def test_execution_rejects_tampered_interpreter_receipt(geometry, tmp_path, execution_installation):
    _spec, root, receipt, manifest = execution_installation
    handoff = _handoff(geometry, tmp_path / "handoff")
    receipt["python_path"] = str(tmp_path / "unreviewed-python")
    (root / "topos/installation.json").write_text(json.dumps(receipt))
    with pytest.raises(installer.ModuleInstallationError, match="specification"):
        execute_module_handoff(handoff, tmp_path / "result", root=root, manifest=manifest)
    assert not (tmp_path / "result").exists()


def test_execution_rejects_changed_git_origin(geometry, tmp_path, execution_installation):
    _spec, root, receipt, manifest = execution_installation
    handoff = _handoff(geometry, tmp_path / "handoff")
    git(Path(receipt["source_path"]), "remote", "set-url", "origin", str(tmp_path / "unreviewed-origin"))
    with pytest.raises(installer.ModuleInstallationError, match="origin differs"):
        execute_module_handoff(handoff, tmp_path / "result", root=root, manifest=manifest)
    assert not (tmp_path / "result").exists()


def test_gui_reports_missing_provider_without_success_or_result(geometry, tmp_path):
    from ui.voila_layout.cochem_gui import CoChemGUI

    gui = CoChemGUI()
    gui.module_recipient.value = "topos"
    gui.module_artifact.value = str(geometry)
    gui.module_root.value = str(tmp_path / "absent-modules")
    gui.module_output.value = str(tmp_path / "gui-executions")
    gui.btn_module_run.click()
    gui._module_worker.join(timeout=20)
    assert not gui._module_worker.is_alive()
    assert gui.btn_module_run.disabled is False
    assert "role='alert'" in gui.module_handoff_status.value
    assert "Module operation failed" in gui.module_handoff_status.value
    assert "completed" not in gui.module_handoff_status.value
    assert not list(tmp_path.rglob("result.json"))
    assert not getattr(gui, "_last_module_result", None)
