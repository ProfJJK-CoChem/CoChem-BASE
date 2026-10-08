"""Actual workflow guards and receipt-input rejection, without provider substitutes.

The guard inputs below are explicit syntax/context examples. Passing a shell
preflight does not authorize an asset download. Genuine staged-asset consumption
separately verifies the owning project, run, immutable receipt and actual bytes.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
LICENSED_WORKFLOWS = (
    "orca_calculation.yml",
    "cfour_calculation.yml",
    "orca_acceptance.yml",
    "cfour_acceptance.yml",
)
STAGING_INPUTS = ("asset_receipt", "asset_receipt_sha256", "asset_task_id")
PRIVATE_OWNER_IF = "${{ github.event.repository.private && github.event.repository.owner.type == 'User' }}"
DRAFT_CONSUMER_JOBS = {
    "orca_calculation.yml": "calculate",
    "cfour_calculation.yml": "calculate",
    "orca_acceptance.yml": "licensed-calculations",
    "cfour_acceptance.yml": "licensed-calculations",
    "orca_asset_access.yml": "verify-archive",
    "cfour_provisioning.yml": "provision",
}

# Bundled TOPOS uses a separate exact contract; legacy receipt checks remain unchanged.
BUNDLE_DRAFT_CONSUMER_JOBS = {"topos_calculation.yml": "calculate"}
ALL_DRAFT_CONSUMER_JOBS = {**DRAFT_CONSUMER_JOBS, **BUNDLE_DRAFT_CONSUMER_JOBS}


class UniqueSafeLoader(yaml.SafeLoader):
    """Reject duplicate YAML keys instead of silently losing a merge branch."""


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"Duplicate workflow key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
)


def document(path: Path) -> dict:
    return yaml.load(path.read_text(), Loader=UniqueSafeLoader)


@pytest.mark.parametrize("filename,job_name", DRAFT_CONSUMER_JOBS.items())
def test_draft_consumers_have_job_scoped_authority_and_keep_private_receipt_guards(filename, job_name):
    # This checks actual authored permissions, not provider access or native success.
    workflow = document(WORKFLOWS / filename)
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"][job_name]
    assert job["permissions"] == {"contents": "write", "actions": "read"}
    assert job["if"] == PRIVATE_OWNER_IF
    triggers = workflow.get("on", workflow.get(True))
    for field in STAGING_INPUTS:
        assert triggers["workflow_dispatch"]["inputs"][field]["required"] is True
    for other_name, other in workflow["jobs"].items():
        if other_name != job_name:
            assert other.get("permissions", workflow["permissions"]) == {"contents": "read"}
    checkouts = [step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@")]
    assert checkouts and all(step["with"]["persist-credentials"] is False for step in checkouts)
    for step in job["steps"]:
        if step.get("uses", "").startswith("./.github/actions/setup-"):
            if "asset-receipt" in step.get("with", {}):
                for field in STAGING_INPUTS:
                    assert step["with"][field.replace("_", "-")] == "${{ inputs." + field + " }}"
        if "scripts.consume_private_engine_asset" in step.get("run", ""):
            assert step["env"]["GH_TOKEN"] == "${{ github.token }}"
            for field in STAGING_INPUTS:
                assert step["env"]["COCHEM_STAGING_" + field.removeprefix("asset_").upper()] == "${{ inputs." + field + " }}"


def test_only_actual_staged_draft_consumer_jobs_receive_contents_write():
    observed = set()
    privileged = set()
    for path in WORKFLOWS.glob("*.yml"):
        workflow = document(path)
        assert "write" not in workflow.get("permissions", {}).values()
        for job_name, job in workflow["jobs"].items():
            steps = job.get("steps", [])
            consumes = any(
                step.get("uses") in {"./.github/actions/setup-orca", "./.github/actions/setup-cfour"}
                or "scripts.consume_private_engine_asset" in step.get("run", "")
                for step in steps
            )
            if consumes:
                observed.add((path.name, job_name))
            permissions = job.get("permissions", workflow.get("permissions", {}))
            if permissions.get("contents") == "write":
                privileged.add((path.name, job_name))
                assert permissions == {"contents": "write", "actions": "read"}
    assert observed == privileged == set(ALL_DRAFT_CONSUMER_JOBS.items())


def run_guard(source: str, **updates: str) -> subprocess.CompletedProcess[str]:
    # A syntax example, deliberately not represented as a genuine staging receipt.
    raw = '{"schema_example":"shell-input-only"}'
    environment = {
        **os.environ,
        "REPOSITORY_PRIVATE": "true",
        "REPOSITORY_OWNER_TYPE": "User",
        "EXECUTION_EVENT": "workflow_dispatch",
        "COCHEM_STAGING_RECEIPT": raw,
        "COCHEM_STAGING_RECEIPT_SHA256": hashlib.sha256(raw.encode()).hexdigest(),
        "COCHEM_STAGING_TASK_ID": uuid.uuid4().hex,
        "ENGINE_PROFILE": "free",
        "MODULE_IDS": "topos",
        "MODULE_ACTION": "install",
        **updates,
    }
    result = subprocess.run(
        ["bash", "-e", "-c", source], env=environment,
        capture_output=True, text=True, timeout=10, check=False,
    )
    for key in ("COCHEM_STAGING_RECEIPT", "COCHEM_STAGING_RECEIPT_SHA256", "COCHEM_STAGING_TASK_ID"):
        if environment[key]:
            assert environment[key] not in result.stdout + result.stderr
    return result


@pytest.mark.parametrize("filename", LICENSED_WORKFLOWS)
@pytest.mark.parametrize(
    ("updates", "error"),
    [
        ({"REPOSITORY_PRIVATE": "false"}, "private project repository"),
        ({"REPOSITORY_PRIVATE": ""}, "private project repository"),
        ({"REPOSITORY_OWNER_TYPE": "Organization"}, "owning personal private project"),
        ({"REPOSITORY_OWNER_TYPE": ""}, "owning personal private project"),
        ({"EXECUTION_EVENT": "push"}, "explicit workflow dispatch"),
        ({"EXECUTION_EVENT": "pull_request"}, "explicit workflow dispatch"),
        ({"COCHEM_STAGING_RECEIPT": ""}, "privately staged receipt"),
        ({"COCHEM_STAGING_RECEIPT_SHA256": ""}, "privately staged receipt"),
        ({"COCHEM_STAGING_RECEIPT_SHA256": "invalid"}, "privately staged receipt"),
        ({"COCHEM_STAGING_TASK_ID": ""}, "privately staged receipt"),
        ({"COCHEM_STAGING_TASK_ID": "not-a-task"}, "privately staged receipt"),
    ],
)
def test_licensed_job_rejects_unsafe_configuration_before_checkout(filename, updates, error):
    workflow = document(WORKFLOWS / filename)
    validation = workflow["jobs"]["validate-private-project"]
    assert validation["if"] == PRIVATE_OWNER_IF
    assert len(validation["steps"]) == 1
    guard = validation["steps"][0]
    assert "uses" not in guard
    result = run_guard(guard["run"], **updates)
    assert result.returncode != 0
    assert error in result.stdout + result.stderr
    calculation_name = "licensed-calculations" if "acceptance" in filename else "calculate"
    calculation = workflow["jobs"][calculation_name]
    assert calculation["needs"] == "validate-private-project"
    assert calculation["if"] == PRIVATE_OWNER_IF


@pytest.mark.parametrize("filename", LICENSED_WORKFLOWS)
def test_private_manual_preflight_preserves_exact_receipt_fields_without_claiming_auth(filename):
    guard = document(WORKFLOWS / filename)["jobs"]["validate-private-project"]["steps"][0]
    assert run_guard(guard["run"]).returncode == 0
    for variable, field in (
        ("COCHEM_STAGING_RECEIPT", "asset_receipt"),
        ("COCHEM_STAGING_RECEIPT_SHA256", "asset_receipt_sha256"),
        ("COCHEM_STAGING_TASK_ID", "asset_task_id"),
    ):
        assert guard["env"][variable] == "${{ inputs." + field + " }}"


@pytest.mark.parametrize("filename", ("orca_acceptance.yml", "cfour_acceptance.yml"))
def test_reusable_acceptance_requires_exact_staging_inputs_and_no_copied_asset_secret(filename):
    workflow = document(WORKFLOWS / filename)
    triggers = workflow.get("on", workflow.get(True))
    caller = triggers["workflow_call"]
    for field in STAGING_INPUTS:
        assert caller["inputs"][field]["required"] is True
    assert "asset_credential" not in caller.get("secrets", {})
    assert all(value["required"] is False for value in caller.get("secrets", {}).values())


@pytest.mark.parametrize("filename", (*LICENSED_WORKFLOWS, "orca_asset_access.yml", "ecosystem_modules.yml"))
def test_licensed_workflows_have_no_automatic_execution_trigger(filename):
    workflow = document(WORKFLOWS / filename)
    triggers = workflow.get("on", workflow.get(True))
    assert "workflow_dispatch" in triggers
    assert set(triggers) <= {"workflow_dispatch", "workflow_call"}
    assert len(triggers["workflow_dispatch"].get("inputs", {})) <= 10


@pytest.mark.parametrize("engine", ("orca", "cfour"))
def test_composite_provisioner_guards_private_context_then_consumes_task_owned_receipt(engine):
    action = document(ROOT / f".github/actions/setup-{engine}/action.yml")
    assert "asset-token" not in action["inputs"]
    assert {"asset-receipt", "asset-receipt-sha256", "asset-task-id"} <= set(action["inputs"])
    steps = action["runs"]["steps"]
    guard = steps[0]
    assert guard["env"]["REPOSITORY_PRIVATE"] == "${{ github.event.repository.private }}"
    assert run_guard(guard["run"], REPOSITORY_PRIVATE="false").returncode != 0
    assert run_guard(guard["run"]).returncode == 0
    assert "gh release download" not in action_path_text(engine)
    download = next(step for step in steps if "python -m scripts.consume_private_engine_asset" in step.get("run", ""))
    assert download["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert download["env"]["COCHEM_STAGING_RECEIPT"] == "${{ inputs.asset-receipt }}"
    assert download["env"]["COCHEM_STAGING_RECEIPT_SHA256"] == "${{ inputs.asset-receipt-sha256 }}"
    assert download["env"]["COCHEM_STAGING_TASK_ID"] == "${{ inputs.asset-task-id }}"
    assert "--engine " + engine in download["run"]
    assert "--descriptor" in download["run"] and "--receipt-output" in download["run"]
    assert any("load_workflow_receipt" in step.get("run", "") for step in steps)
    assert any(step.get("if") == "always()" and "cochem-" in step.get("run", "") for step in steps)


def action_path_text(engine):
    return (ROOT / f".github/actions/setup-{engine}/action.yml").read_text()


@pytest.mark.parametrize("updates,error", [
    ({"REPOSITORY_PRIVATE": "false"}, "private project repository"),
    ({"REPOSITORY_OWNER_TYPE": "Organization"}, "owning personal private project"),
    ({"EXECUTION_EVENT": "push"}, "explicit workflow dispatch"),
    ({"COCHEM_STAGING_RECEIPT": ""}, "privately staged receipt"),
])
def test_asset_integrity_workflow_rejects_unsafe_configuration_before_checkout(updates, error):
    workflow = document(WORKFLOWS / "orca_asset_access.yml")
    job = workflow["jobs"]["verify-archive"]
    assert job["if"] == PRIVATE_OWNER_IF
    guard = job["steps"][0]
    assert "uses" not in guard
    result = run_guard(guard["run"], **updates)
    assert result.returncode != 0
    assert error in result.stdout + result.stderr
    consume = next(step for step in job["steps"] if "load_workflow_receipt" in step.get("run", ""))
    assert consume["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert "consume(" in consume["run"]


@pytest.mark.parametrize("engine_profile", ("orca", "cfour", "orca-cfour"))
@pytest.mark.parametrize("updates,error", [
    ({"REPOSITORY_PRIVATE": "false"}, "owning personal private project"),
    ({"REPOSITORY_OWNER_TYPE": "Organization"}, "owning personal private project"),
    ({"EXECUTION_EVENT": "push"}, "explicit private TOPOS"),
    ({"MODULE_IDS": "torq"}, "explicit private TOPOS"),
    ({"MODULE_ACTION": "fetch"}, "explicit private TOPOS"),
    ({}, "not qualified for task-owned staging"),
])
def test_module_licensed_profiles_reject_before_checkout_or_any_download(engine_profile, updates, error):
    steps = document(WORKFLOWS / "ecosystem_modules.yml")["jobs"]["modules"]["steps"]
    guard = steps[0]
    assert guard["name"] == "Validate licensed module staging boundary"
    assert "uses" not in guard
    result = run_guard(guard["run"], ENGINE_PROFILE=engine_profile, **updates)
    assert result.returncode != 0
    assert error in result.stdout + result.stderr
    assert not any(step.get("uses", "").startswith("./.github/actions/setup-") for step in steps)


def test_module_free_profile_preserves_mandatory_kit_and_isolated_execution_authority():
    workflow = document(WORKFLOWS / "ecosystem_modules.yml")
    steps = workflow["jobs"]["modules"]["steps"]
    assert run_guard(steps[0]["run"], ENGINE_PROFILE="free").returncode == 0
    names = [step.get("name") for step in steps]
    assert names.index("Verify actual artifact bytes and select the kit") < names.index("Verify the kit against the installed BASE catalog") < names.index("Fetch or install reviewed sources and mandatory authority") < names.index("Execute the validated module request")
    catalog = next(step for step in steps if step.get("name") == "Verify the kit against the installed BASE catalog")
    assert "python -I -B -" in catalog["run"] and "inspect_kit" in catalog["run"]
    execute = next(step for step in steps if step.get("name") == "Execute the validated module request")
    assert "python -I -B -" in execute["run"] and "raise SystemExit(main(arguments))" in execute["run"]


def test_licensed_public_yaml_has_no_fixed_asset_secret_or_secret_enumeration():
    for path in (ROOT / ".github").rglob("*.yml"):
        text = path.read_text()
        assert "toJSON(secrets)" not in text
        assert "secrets: inherit" not in text
        for engine in ("ORCA", "CFOUR"):
            assert "secrets." + engine + "_" not in text
    for filename in LICENSED_WORKFLOWS:
        workflow = document(WORKFLOWS / filename)
        job_name = "licensed-calculations" if "acceptance" in filename else "calculate"
        provision = next(step for step in workflow["jobs"][job_name]["steps"] if step.get("uses", "").startswith("./.github/actions/setup-") and "asset-receipt" in step.get("with", {}))
        assert provision["with"]["asset-receipt"] == "${{ inputs.asset_receipt }}"
        assert provision["with"]["asset-receipt-sha256"] == "${{ inputs.asset_receipt_sha256 }}"
        assert provision["with"]["asset-task-id"] == "${{ inputs.asset_task_id }}"
    ecosystem = (WORKFLOWS / "ecosystem_modules.yml").read_text()
    assert "ASSET_CREDENTIAL" not in ecosystem
    assert "ORCA_PROFILE" not in ecosystem and "CFOUR_PROFILE" not in ecosystem


@pytest.mark.parametrize("topos_ref,private,expected", [("a" * 40, "true", 0), ("main", "true", 1), ("a" * 40, "false", 1)])
def test_public_downstream_sources_need_no_additional_credential_but_keep_private_pinned_execution(topos_ref, private, expected):
    steps = document(WORKFLOWS / "orca_acceptance.yml")["jobs"]["licensed-calculations"]["steps"]
    guard = next(step for step in steps if step.get("name") == "Validate optional downstream source identities")
    result = run_guard(guard["run"], TOPOS_REF=topos_ref, TORQ_REF="b" * 40, CONTROLLER_PRIVATE=private,
                       COCHEM_SOURCE_READ_TOKEN="", BASE_SOURCE_READ_TOKEN="")
    assert (result.returncode == 0) == (expected == 0)
    for repository, ref in (("CoChem-TOPOS", "topos_ref"), ("CoChem-TORQ", "torq_ref")):
        checkout = next(step for step in steps if step.get("with", {}).get("repository") == "ProfJJK-CoChem/" + repository)
        assert checkout["with"]["token"] == "${{ secrets.COCHEM_SOURCE_READ_TOKEN || secrets.BASE_SOURCE_READ_TOKEN || github.token }}"
        assert checkout["with"]["ref"] == "${{ inputs." + ref + " }}"
        assert checkout["with"]["persist-credentials"] is False
    names = [step.get("name") for step in steps]
    assert names.index("Isolate and identify all mandatory source checkouts") < names.index("Complete mandatory package setup using the audited BASE installation") < names.index("Require genuine TOPOS ORCA scientific acceptance")
    source_verification = next(step for step in steps if step.get("name") == "Isolate and identify all mandatory source checkouts")
    assert 'rev-parse HEAD)" = "$TOPOS_REF"' in source_verification["run"]
    assert 'rev-parse HEAD)" = "$TORQ_REF"' in source_verification["run"]


def test_free_compute_sources_keep_full_pins_and_public_token_fallback():
    steps = document(WORKFLOWS / "topos_compute.yml")["jobs"]["calculation"]["steps"]
    for repository in ("CoChem-TOPOS", "CoChem-TORQ"):
        checkout = next(step for step in steps if step.get("with", {}).get("repository") == "ProfJJK-CoChem/" + repository)
        assert re.fullmatch(r"[0-9a-f]{40}", checkout["with"]["ref"])
        assert checkout["with"]["token"].endswith(" || github.token }}")
        assert checkout["with"]["persist-credentials"] is False


@pytest.mark.parametrize("engine", ("orca", "cfour"))
def test_actual_receipt_loader_rejects_missing_and_shape_invalid_receipts(engine):
    # Actual loader subprocesses run without a provider substitute or a valid
    # provider authorization. Canonical '{}' is a malformed boundary input.
    script = """
import os
from scripts.consume_private_engine_asset import load_workflow_receipt
for raw in ("", "{}"):
    os.environ["COCHEM_STAGING_RECEIPT"] = raw
    try:
        load_workflow_receipt(os.environ["CONTRACT_ENGINE"])
    except ValueError:
        pass
    else:
        raise AssertionError("Missing/shape-invalid staging receipt was accepted")
"""
    environment = dict(os.environ)
    environment.update(
        CONTRACT_ENGINE=engine, COCHEM_STAGING_RECEIPT_SHA256=hashlib.sha256(b"{}").hexdigest(),
        COCHEM_STAGING_TASK_ID=uuid.uuid4().hex,
    )
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=environment,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
