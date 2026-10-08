"""Exact authored TOPOS draft-kit/engine workflow authority, without providers.

These are security contract checks on the actual YAML, not remote distribution
access, installation, engine qualification, or scientific acceptance claims.
"""
from __future__ import annotations

import pytest

from tests.base.test_private_licensed_actions import ROOT, document

WORKFLOW = ROOT / ".github/workflows/topos_calculation.yml"
REQUIRED_INPUTS = {
    "dispatch_id", "job_file", "request_sha256", "staging_bundle", "staging_bundle_sha256",
}
PRIVATE_MANUAL_OWNER_IF = (
    "${{ github.event.repository.private && github.event.repository.owner.type == 'User' "
    "&& github.event_name == 'workflow_dispatch' }}"
)


def test_topos_bundle_consumer_keeps_exact_private_personal_manual_authority():
    workflow = document(WORKFLOW)
    triggers = workflow.get("on", workflow.get(True))
    assert set(triggers) == {"workflow_dispatch"}
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert set(inputs) == REQUIRED_INPUTS | {"engine_task_ids"}
    assert all(inputs[name]["required"] is True for name in REQUIRED_INPUTS)
    assert all(value["type"] == "string" for value in inputs.values())
    assert inputs["engine_task_ids"]["required"] is False
    assert inputs["engine_task_ids"]["default"] == ""
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"calculate"}
    job = workflow["jobs"]["calculate"]
    assert job["permissions"] == {"contents": "write", "actions": "read"}
    assert job["if"] == PRIVATE_MANUAL_OWNER_IF
    assert job["runs-on"] == "ubuntu-24.04"
    assert job["env"]["TOPOS_DISPATCH_ID"] == "${{ inputs.dispatch_id }}"
    assert job["env"]["JOB_FILE"] == "${{ inputs.job_file }}"
    assert job["env"]["TOPOS_REQUEST_SHA256"] == "${{ inputs.request_sha256 }}"
    assert job["env"]["TOPOS_STAGING_BUNDLE"] == "${{ inputs.staging_bundle }}"
    assert job["env"]["TOPOS_STAGING_BUNDLE_SHA256"] == "${{ inputs.staging_bundle_sha256 }}"
    assert workflow["run-name"] == "CoChem TOPOS ${{ inputs.dispatch_id }} ${{ inputs.engine_task_ids }}"


def test_topos_bundle_preflight_precedes_every_licensed_consumer_on_the_event_source():
    steps = document(WORKFLOW)["jobs"]["calculate"]["steps"]
    checkouts = [step for step in steps if step.get("uses", "").startswith("actions/checkout@")]
    assert len(checkouts) == 1
    assert checkouts[0]["with"] == {
        "repository": "${{ github.repository }}", "ref": "${{ github.sha }}", "persist-credentials": False,
    }
    preflight = next(step for step in steps if step.get("id") == "staging")
    assert preflight["env"] == {"GH_TOKEN": "${{ github.token }}", "PYTHONPATH": "src"}
    assert preflight["run"] == (
        'python -B -m scripts.run_private_topos_actions preflight --output "$RUNNER_TEMP/topos-evidence/preflight.json"'
    )
    audit = next(step for step in steps if "ci_tools/base_ci.py audit" in step.get("run", ""))
    consumers = [step for step in steps if step.get("uses") in {
        "./.github/actions/setup-orca", "./.github/actions/setup-cfour",
    }]
    assert len(consumers) == 2
    assert steps.index(checkouts[0]) < steps.index(preflight) < steps.index(audit)
    assert all(steps.index(audit) < steps.index(step) for step in consumers)


@pytest.mark.parametrize("engine", ["orca", "cfour"])
def test_topos_only_selected_engines_receive_their_separate_original_staging_receipts(engine):
    steps = document(WORKFLOW)["jobs"]["calculate"]["steps"]
    matches = [step for step in steps if step.get("uses") == f"./.github/actions/setup-{engine}"]
    assert len(matches) == 1
    step = matches[0]
    assert step["if"] == f"env.TOPOS_REQUIRES_{engine.upper()} == 'true'"
    assert step.get("continue-on-error", False) is False
    expected = {
        "asset-receipt": "${{ steps.staging.outputs." + engine + "_receipt }}",
        "asset-receipt-sha256": "${{ steps.staging.outputs." + engine + "_sha256 }}",
        "asset-task-id": "${{ steps.staging.outputs." + engine + "_task }}",
    }
    if engine == "cfour":
        expected["required"] = "true"
    assert step["with"] == expected


def test_topos_owning_token_stays_in_explicit_control_plane_steps():
    steps = document(WORKFLOW)["jobs"]["calculate"]["steps"]
    authenticated = [step for step in steps if "GH_TOKEN" in step.get("env", {})]
    assert len(authenticated) == 3
    assert all(step["env"]["GH_TOKEN"] == "${{ github.token }}" for step in authenticated)
    assert {step.get("id") for step in authenticated} == {"staging", None}
    assert sum(" download-kit " in step["run"] for step in authenticated) == 1
    assert sum(" run " in step["run"] for step in authenticated) == 1
    text = WORKFLOW.read_text()
    assert "secrets." not in text and "secrets[" not in text
    assert "gh release download" not in text
    assert "asset-token" not in text


def test_topos_retains_verified_evidence_and_removes_job_local_licensed_transports():
    steps = document(WORKFLOW)["jobs"]["calculate"]["steps"]
    exports = [step for step in steps if "scripts.export_topos_evidence" in step.get("run", "")]
    assert len(exports) == 1 and exports[0]["if"] == "always()"
    upload = next(step for step in steps if step.get("uses", "").startswith("actions/upload-artifact@"))
    assert upload["if"] == "always()"
    assert upload["with"]["if-no-files-found"] == "error"
    paths = upload["with"]["path"]
    assert "submitted-job.json" in paths
    assert "topos-evidence/" in paths and "hosted-budget-controls.json" in paths
    assert all(name not in paths for name in (
        "cochem-orca-download", "cochem-orca-install", "cochem-cfour-download", "cochem-cfour-install", "mandatory-kit.zip",
    ))
    cleanup = steps[-1]
    assert cleanup["if"] == "always()"
    assert "rm -rf --" in cleanup["run"]
    assert all('"$RUNNER_TEMP/' + name + '"' in cleanup["run"] for name in (
        "cochem-orca-download", "cochem-orca-install", "cochem-cfour-download", "cochem-cfour-install",
        "topos-kit", "mandatory-kit.zip",
    ))
