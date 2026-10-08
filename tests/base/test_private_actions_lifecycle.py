"""Real filesystem/UI and mathematical identity checks; no provider simulation.

Process identity dictionaries below are explicitly supplied algebraic boundary
inputs. They are never treated as actual GitHub runs or scientific observations.
No credential, API response, native engine, or callback is replaced.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import yaml

from cochem_base.interfaces.private_actions import (
    PrivateActionsController,
    PrivateActionsError,
    run_belongs_to_task,
    validate_ref,
)
from scripts.consume_private_engine_asset import validate_calculation_intent
from scripts.provision_cfour import load_distribution_manifest

ROOT = Path(__file__).resolve().parents[2]


def supplied_job_intent(tmp_path):
    path = tmp_path / "jobs" / "submitted.json"
    path.parent.mkdir()
    # Genuine repository example is a supplied molecular request, not an energy.
    contents = (ROOT / "examples/jobs/water-single-point.json").read_bytes()
    path.write_bytes(contents)
    intent = {
        "job_file": "jobs/submitted.json",
        "input_sha256": hashlib.sha256(contents).hexdigest(),
        "cores": 1,
        "maxcore_mb": 512,
    }
    receipt = {"project": {
        "workflow_path": ".github/workflows/orca_calculation.yml",
        "calculation": intent,
    }}
    environment = {"JOB_FILE": intent["job_file"], "JOB_CORES": "1", "JOB_MAXCORE_MB": "512"}
    return receipt, environment, path


def test_actual_supplied_job_bytes_and_resource_tuple_are_bound(tmp_path):
    receipt, environment, _ = supplied_job_intent(tmp_path)
    validate_calculation_intent(receipt, tmp_path, environment)


@pytest.mark.parametrize("variable,value", [
    ("JOB_FILE", "jobs/another.json"), ("JOB_CORES", "2"), ("JOB_MAXCORE_MB", "1024"),
])
def test_changed_dispatch_controls_cannot_reuse_original_intent(tmp_path, variable, value):
    receipt, environment, _ = supplied_job_intent(tmp_path)
    environment[variable] = value
    with pytest.raises(ValueError, match="differ"):
        validate_calculation_intent(receipt, tmp_path, environment)


def test_changed_actual_job_bytes_cannot_reuse_staging_receipt(tmp_path):
    receipt, environment, path = supplied_job_intent(tmp_path)
    content = json.loads(path.read_bytes())
    content["method"] = "HF"
    path.write_text(json.dumps(content))
    with pytest.raises(ValueError, match="SHA-256"):
        validate_calculation_intent(receipt, tmp_path, environment)


def test_missing_input_intent_cannot_authorize_a_calculation(tmp_path):
    receipt, environment, _ = supplied_job_intent(tmp_path)
    receipt["project"]["calculation"] = None
    with pytest.raises(ValueError, match="intent"):
        validate_calculation_intent(receipt, tmp_path, environment)


def test_fixed_provisioning_cannot_borrow_arbitrary_calculation_controls(tmp_path):
    receipt, environment, _ = supplied_job_intent(tmp_path)
    receipt["project"]["workflow_path"] = ".github/workflows/cfour_provisioning.yml"
    with pytest.raises(ValueError, match="borrow"):
        validate_calculation_intent(receipt, tmp_path, environment)


@pytest.mark.parametrize("value", [
    "main", "refs/tags/release", "refs/heads/../branch", "refs/heads/.hidden",
    "refs/heads/name.lock", "refs/heads/name?input", "refs/heads/name\n",
])
def test_unsafe_or_ambiguous_project_refs_are_rejected(value):
    with pytest.raises(PrivateActionsError):
        validate_ref(value)


def test_explicit_project_branch_syntax_is_preserved():
    assert validate_ref("refs/heads/student/project") == "refs/heads/student/project"


def test_exact_process_identity_comparison_includes_ref_and_head_repository():
    # Mathematical identity-comparison inputs only; no actual run is claimed.
    task, source = "a" * 32, "b" * 40
    receipt = {
        "task_id": task,
        "project": {"source_sha": source, "ref": "refs/heads/main",
                    "workflow_path": ".github/workflows/orca_calculation.yml"},
        "destination": {"repository_id": 17},
    }
    run = {
        "display_title": "Mathematical task " + task, "event": "workflow_dispatch",
        "head_sha": source, "head_branch": "main", "id": 23,
        "path": ".github/workflows/orca_calculation.yml",
        "repository": {"full_name": "algebra/project", "id": 17},
        "head_repository": {"full_name": "algebra/project", "id": 17},
    }
    assert run_belongs_to_task(run, receipt, "algebra/project")
    for field, value in (
        ("head_branch", "different"),
        ("head_repository", {"full_name": "algebra/other", "id": 18}),
        ("path", None),
        ("head_sha", "c" * 40),
    ):
        assert not run_belongs_to_task({**run, field: value}, receipt, "algebra/project")


def test_actual_os_file_lock_preserves_concurrent_local_process_history(tmp_path):
    controller = PrivateActionsController("algebra/project", tmp_path / "runtime")
    count_path = controller.runtime / "mathematical-count.json"
    count_path.write_text('{"count":0}')

    def increment(_):
        with controller._locked():
            actual = json.loads(count_path.read_text())
            actual["count"] += 1
            count_path.write_text(json.dumps(actual))

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(increment, range(32)))
    assert json.loads(count_path.read_text()) == {"count": 32}


def test_genuine_reviewed_cfour_descriptor_is_available_without_claiming_native_execution():
    descriptor = load_distribution_manifest(ROOT / "scripts/cfour-distribution.json")
    assert descriptor["runtime_manifest_sha256"] and descriptor["source_sha256"]
    assert descriptor["cfour_version"] == "2.1"
    assert descriptor["mpi"] is False and descriptor["openmp"] is True


def test_licensed_workflows_guard_private_ownership_and_bind_staged_inputs():
    for engine in ("orca", "cfour"):
        for name in (engine + "_calculation.yml", engine + "_acceptance.yml"):
            document = yaml.load((ROOT / ".github/workflows" / name).read_text(),
                                 Loader=yaml.BaseLoader)
            inputs = document["on"]["workflow_dispatch"]["inputs"]
            for key in ("asset_receipt", "asset_receipt_sha256", "asset_task_id"):
                assert inputs[key]["required"] == "true"
            assert "asset_task_id" in document["run-name"]
            assert document["permissions"] == {"contents": "read"}
            for job in document["jobs"].values():
                assert "repository.private" in job["if"] and "owner.type == 'User'" in job["if"]


def test_real_dashboard_controls_are_wired_without_dispatching_or_fabricating_results(tmp_path):
    code = (
        "from ui.voila_layout.cochem_gui import CoChemGUI\n"
        "gui=CoChemGUI()\n"
        "assert gui.actions_stage_submit.description=='Stage privately and submit'\n"
        "assert gui.actions_download.description=='Download owned results'\n"
        "assert gui.actions_task_id.value==''\n"
        "assert gui._last_actions_job is None\n"
        "gui._run_private_actions('status')\n"
        "assert 'blocked' in gui.actions_lifecycle_status.value\n"
        "assert not gui._actions_lifecycle_running\n"
        "gui.app.close()\n"
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
    environment["COCHEM_CONFIG"] = str(tmp_path / "actual-absent-registry.json")
    environment["COCHEM_ARTIFACT_DIR"] = str(tmp_path / "actual-runtime")
    subprocess.run([sys.executable, "-c", code], env=environment, cwd=ROOT,
                   check=True, capture_output=True, text=True, timeout=60)
