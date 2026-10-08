"""Execute licensed Actions guards without provisioning or running an engine."""

from __future__ import annotations

import os
import subprocess
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


def document(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def run_guard(source: str, **updates: str) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "REPOSITORY_PRIVATE": "true",
        "EXECUTION_EVENT": "workflow_dispatch",
        "ASSET_CREDENTIAL_NAME": "LAB_PRIVATE_RUNTIME",
        "ASSET_CREDENTIAL": "isolated-guard-test-value",
        **updates,
    }
    result = subprocess.run(
        ["bash", "-e", "-c", source],
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if environment["ASSET_CREDENTIAL"]:
        assert environment["ASSET_CREDENTIAL"] not in result.stdout + result.stderr
    assert "LAB_PRIVATE_RUNTIME" not in result.stdout + result.stderr
    return result


@pytest.mark.parametrize("filename", LICENSED_WORKFLOWS)
@pytest.mark.parametrize(
    ("updates", "error"),
    [
        ({"REPOSITORY_PRIVATE": "false"}, "private project repository"),
        ({"REPOSITORY_PRIVATE": ""}, "private project repository"),
        ({"EXECUTION_EVENT": "push"}, "explicit workflow dispatch"),
        ({"EXECUTION_EVENT": "pull_request"}, "explicit workflow dispatch"),
        ({"ASSET_CREDENTIAL_NAME": "", "ASSET_CREDENTIAL": ""}, "Configure the private"),
        ({"ASSET_CREDENTIAL_NAME": "bad/name"}, "valid secret identifier"),
        ({"ASSET_CREDENTIAL": ""}, "credential is unavailable"),
    ],
)
def test_licensed_job_rejects_unsafe_configuration_before_checkout(filename, updates, error):
    workflow = document(WORKFLOWS / filename)
    validation = workflow["jobs"]["validate-private-project"]
    assert len(validation["steps"]) == 1
    guard = validation["steps"][0]
    assert "uses" not in guard
    result = run_guard(guard["run"], **updates)
    assert result.returncode != 0
    assert error in result.stdout + result.stderr
    calculation_name = "licensed-calculations" if "acceptance" in filename else "calculate"
    calculation = workflow["jobs"][calculation_name]
    assert calculation["needs"] == "validate-private-project"
    assert calculation["if"] == "github.event.repository.private"


@pytest.mark.parametrize("filename", LICENSED_WORKFLOWS)
def test_licensed_job_accepts_private_manual_configuration_without_disclosing_identity(filename):
    guard = document(WORKFLOWS / filename)["jobs"]["validate-private-project"]["steps"][0]
    assert run_guard(guard["run"]).returncode == 0
    engine = filename.split("_")[0].upper()
    assert guard["env"]["ASSET_CREDENTIAL_NAME"] == "${{ vars.COCHEM_" + engine + "_ASSET_CREDENTIAL }}"
    assert "secrets[vars.COCHEM_" + engine + "_ASSET_CREDENTIAL]" in guard["env"]["ASSET_CREDENTIAL"]


@pytest.mark.parametrize("filename", ("orca_acceptance.yml", "cfour_acceptance.yml"))
def test_reusable_acceptance_accepts_only_an_explicit_generic_credential(filename):
    workflow = document(WORKFLOWS / filename)
    triggers = workflow.get("on", workflow.get(True))
    assert "asset_credential" in triggers["workflow_call"]["secrets"]
    guard = workflow["jobs"]["validate-private-project"]["steps"][0]
    assert "secrets.asset_credential" in guard["env"]["ASSET_CREDENTIAL"]
    assert run_guard(guard["run"], ASSET_CREDENTIAL_NAME="").returncode == 0


@pytest.mark.parametrize("filename", (*LICENSED_WORKFLOWS, "orca_asset_access.yml", "ecosystem_modules.yml"))
def test_licensed_workflows_have_no_automatic_execution_trigger(filename):
    workflow = document(WORKFLOWS / filename)
    triggers = workflow.get("on", workflow.get(True))
    assert "workflow_dispatch" in triggers
    assert set(triggers) <= {"workflow_dispatch", "workflow_call"}


@pytest.mark.parametrize("engine", ("orca", "cfour"))
def test_composite_provisioner_rejects_public_repository_before_distribution_lookup(engine):
    steps = document(ROOT / f".github/actions/setup-{engine}/action.yml")["runs"]["steps"]
    guard = steps[0]
    assert guard["env"]["REPOSITORY_PRIVATE"] == "${{ github.event.repository.private }}"
    assert run_guard(guard["run"], REPOSITORY_PRIVATE="false").returncode != 0
    assert run_guard(guard["run"]).returncode == 0
    assert "gh release download" not in guard["run"]
    download = next(step for step in steps if "gh release download" in step.get("run", ""))
    assert download["env"]["GH_TOKEN"] == "${{ inputs.asset-token }}"
    assert any(step.get("if") == "always()" and "cochem-" in step.get("run", "") for step in steps)


@pytest.mark.parametrize(
    ("updates", "error"),
    [
        ({"REPOSITORY_PRIVATE": "false"}, "private project repository"),
        ({"ASSET_CREDENTIAL_NAME": ""}, "Configure the private"),
        ({"ASSET_CREDENTIAL_NAME": "invalid/name"}, "valid secret identifier"),
        ({"ASSET_CREDENTIAL": ""}, "credential is unavailable"),
    ],
)
def test_asset_integrity_workflow_rejects_unsafe_configuration_before_checkout(updates, error):
    guard = document(WORKFLOWS / "orca_asset_access.yml")["jobs"]["verify-archive"]["steps"][0]
    assert "uses" not in guard
    result = run_guard(guard["run"], **updates)
    assert result.returncode != 0
    assert error in result.stdout + result.stderr


@pytest.mark.parametrize("engine", ("orca", "cfour"))
def test_module_workflow_validates_selected_credential_before_kit_download(engine):
    steps = document(WORKFLOWS / "ecosystem_modules.yml")["jobs"]["modules"]["steps"]
    index = next(i for i, step in enumerate(steps) if step.get("name") == f"Validate private {engine.upper()} asset credential selection")
    guard = steps[index]
    assert engine in guard["if"]
    assert index < next(i for i, step in enumerate(steps) if step.get("uses", "").startswith("actions/download-artifact@"))
    assert index < next(i for i, step in enumerate(steps) if step.get("uses") == f"./.github/actions/setup-{engine}")
    assert run_guard(guard["run"], ASSET_CREDENTIAL_NAME="").returncode != 0
    assert run_guard(guard["run"], ASSET_CREDENTIAL="").returncode != 0
    assert run_guard(guard["run"]).returncode == 0


def test_licensed_public_yaml_uses_private_selectors_without_secret_enumeration():
    for path in (ROOT / ".github").rglob("*.yml"):
        text = path.read_text()
        assert "toJSON(secrets)" not in text
        assert "secrets: inherit" not in text
        for engine in ("ORCA", "CFOUR"):
            assert "secrets." + engine + "_" not in text
    for filename in LICENSED_WORKFLOWS:
        workflow = document(WORKFLOWS / filename)
        job_name = "licensed-calculations" if "acceptance" in filename else "calculate"
        provision = next(step for step in workflow["jobs"][job_name]["steps"] if step.get("uses", "").startswith("./.github/actions/setup-"))
        if filename == "cfour_acceptance.yml":
            provision = next(step for step in workflow["jobs"][job_name]["steps"] if "asset-token" in step.get("with", {}))
        assert "secrets[vars.COCHEM_" in provision["with"]["asset-token"]


@pytest.mark.parametrize("topos_ref,private,expected", [("a" * 40, "true", 0), ("main", "true", 1), ("a" * 40, "false", 1)])
def test_public_downstream_sources_need_no_additional_credential_but_keep_private_pinned_execution(topos_ref, private, expected):
    steps = document(WORKFLOWS / "orca_acceptance.yml")["jobs"]["licensed-calculations"]["steps"]
    guard = next(step for step in steps if step.get("name") == "Validate optional downstream source identities")
    result = run_guard(guard["run"], TOPOS_REF=topos_ref, TORQ_REF="b" * 40, CONTROLLER_PRIVATE=private,
                       COCHEM_SOURCE_READ_TOKEN="", BASE_SOURCE_READ_TOKEN="")
    assert (result.returncode == 0) == (expected == 0)
    assert all(step.get("name") != "Validate configured downstream source credential" for step in steps)
    for repository, ref in (("CoChem-TOPOS", "topos_ref"), ("CoChem-TORQ", "torq_ref")):
        checkout = next(step for step in steps if step.get("with", {}).get("repository") == "ProfJJK-CoChem/" + repository)
        assert checkout["with"]["token"] == "${{ secrets.COCHEM_SOURCE_READ_TOKEN || secrets.BASE_SOURCE_READ_TOKEN || github.token }}"
        assert checkout["with"]["ref"] == "${{ inputs." + ref + " }}"
        assert checkout["with"]["persist-credentials"] is False
