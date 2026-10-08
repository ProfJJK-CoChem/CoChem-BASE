"""Real Git provenance and original TORQ transport checks; no engine doubles."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts import manage_modules as manager
from scripts.native_torq_actions import REQUIRED_NATIVE_FILES, resolve_catalog, verify_source


def git(directory, *arguments):
    return subprocess.run(
        ["git", "-C", str(directory), *arguments], check=True, capture_output=True, text=True
    ).stdout.strip()


def init_git(directory):
    directory.mkdir()
    git(directory, "init", "--quiet")
    git(directory, "config", "user.name", "Provenance test")
    git(directory, "config", "user.email", "provenance@example.invalid")


def committed_source_pair(tmp_path):
    """Small real commits exercise identity validation, without a calculator."""
    controller, source = tmp_path / "controller", tmp_path / "scientific"
    init_git(controller)
    init_git(source)
    for name in REQUIRED_NATIVE_FILES:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Source identity fixture; never executed.\n")
    git(source, "add", ".")
    git(source, "commit", "--quiet", "-m", "Identity-only scientific source fixture")
    scientific_sha = git(source, "rev-parse", "HEAD")
    git(source, "checkout", "--quiet", "--detach", scientific_sha)
    git(source, "remote", "add", "origin", "https://github.com/lab/scientific.git")
    spec = {
        "repository": "lab/scientific",
        "revision": scientific_sha,
        "distribution": "CoChem-TORQ",
        "adapter": "torq_geometry",
        "adapter_requirements": [],
        "operations": ["geometry_analysis"],
    }
    catalog = controller / "scripts/module-distribution.json"
    catalog.parent.mkdir()
    catalog.write_text(
        json.dumps({"schema_version": manager.MANIFEST_SCHEMA, "modules": {"torq": spec}})
    )
    git(controller, "add", ".")
    git(controller, "commit", "--quiet", "-m", "Exact student controller catalog")
    return controller, source, catalog, git(controller, "rev-parse", "HEAD"), scientific_sha


def verify_pair(pair, output, **overrides):
    controller, source, catalog, controller_sha, _ = pair
    values = {
        "controller": controller,
        "source": source,
        "manifest": catalog,
        "output": output,
        "expected_controller_sha": controller_sha,
        "observed_controller_sha": controller_sha,
    }
    return verify_source(**(values | overrides))


@pytest.mark.parametrize(
    "origin", ["https://github.com/lab/scientific.git", "https://github.com/lab/scientific"]
)
def test_exact_distinct_controller_and_clean_scientific_source_retains_observed_identity(
    tmp_path, origin
):
    pair = committed_source_pair(tmp_path)
    git(pair[1], "remote", "set-url", "origin", origin)
    evidence = verify_pair(pair, tmp_path / "evidence/identity.json")
    assert evidence["controller_commit"] == pair[3]
    assert evidence["torq_commit"] == pair[4] != pair[3]
    assert evidence["observed_torq_origin"] == origin
    assert evidence["source_tree_oid"] == git(pair[1], "rev-parse", "HEAD^{tree}")
    assert evidence["catalog_sha256"] == hashlib.sha256(pair[2].read_bytes()).hexdigest()
    assert evidence["scientific_calculation_performed"] is False
    assert evidence["scientific_release_certified"] is False
    assert json.loads((tmp_path / "evidence/identity.json").read_text()) == evidence
    with pytest.raises(FileExistsError):
        verify_pair(pair, tmp_path / "evidence/identity.json")


@pytest.mark.parametrize("authority", ["main", "a" * 40])
def test_ambiguous_or_changed_controller_cannot_write_evidence(tmp_path, authority):
    pair = committed_source_pair(tmp_path)
    with pytest.raises(ValueError):
        verify_pair(pair, tmp_path / "identity.json", expected_controller_sha=authority)
    assert not (tmp_path / "identity.json").exists()


@pytest.mark.parametrize("mutation", ["tracked", "untracked", "ignored", "branch", "origin"])
def test_changed_actual_torq_source_is_rejected_before_transport_or_evidence(tmp_path, mutation):
    pair = committed_source_pair(tmp_path)
    source = pair[1]
    if mutation == "tracked":
        (source / REQUIRED_NATIVE_FILES[0]).write_text("changed\n")
    elif mutation == "untracked":
        (source / "unreviewed.py").write_text("untracked\n")
    elif mutation == "ignored":
        (source / ".git/info/exclude").write_text("generated\n")
        (source / "generated").write_text("ignored\n")
    elif mutation == "branch":
        git(source, "checkout", "--quiet", "-b", "moving")
    else:
        git(source, "remote", "set-url", "origin", "https://github.com/other/source.git")
    with pytest.raises(manager.ModuleInstallationError):
        verify_pair(pair, tmp_path / "identity.json")
    assert not (tmp_path / "identity.json").exists()


def test_changed_controller_catalog_is_rejected_even_with_same_event_commit(tmp_path):
    pair = committed_source_pair(tmp_path)
    pair[2].write_text(pair[2].read_text() + "\n")
    with pytest.raises(ValueError, match="modified"):
        verify_pair(pair, tmp_path / "identity.json")
    assert not (tmp_path / "identity.json").exists()


def test_catalog_cannot_be_selected_outside_owning_controller(tmp_path):
    pair = committed_source_pair(tmp_path)
    outside = tmp_path / "outside-catalog.json"
    outside.write_bytes(pair[2].read_bytes())
    with pytest.raises(ValueError, match="belong"):
        verify_pair(pair, tmp_path / "identity.json", manifest=outside)


def test_checkout_and_controller_cannot_share_scientific_authority(tmp_path):
    pair = committed_source_pair(tmp_path)
    with pytest.raises(ValueError, match="separate"):
        verify_pair(pair, tmp_path / "identity.json", source=pair[0])


def test_catalog_only_emits_reviewed_repository_and_exact_pin(tmp_path):
    pair = committed_source_pair(tmp_path)
    output = tmp_path / "outputs"
    assert resolve_catalog(pair[2], output) == {"repository": "lab/scientific", "revision": pair[4]}
    assert output.read_text() == f"repository=lab/scientific\nrevision={pair[4]}\n"


def test_native_workflow_keeps_exact_seven_input_schema_and_separate_authorities():
    path = Path(__file__).resolve().parents[2] / ".github/workflows/calculation.yml"
    text = path.read_text()
    workflow = yaml.safe_load(text)
    trigger = workflow.get("on", workflow.get(True))
    inputs = trigger["workflow_dispatch"]["inputs"]
    assert set(inputs) == {
        "request_b64",
        "request_sha256",
        "request_id",
        "expected_source_sha",
        "approved_plan_b64",
        "approved_plan_sha256",
        "engine",
    }
    assert inputs["engine"]["options"] == ["pyscf"]
    job = workflow["jobs"]["calculation"]
    assert "github.event.repository.private" in job["if"]
    steps = job["steps"]
    checkouts = [step for step in steps if step.get("uses", "").startswith("actions/checkout@")]
    assert len(checkouts) == 2
    assert checkouts[0]["with"]["ref"] == "${{ github.sha }}"
    assert checkouts[1]["with"]["ref"] == "${{ steps.torq.outputs.revision }}"
    assert all(step["with"]["persist-credentials"] is False for step in checkouts)
    assert all(len(step["uses"].split("@")[-1]) == 40 for step in steps if "uses" in step)
    assert "ci_tools/actions_request.py" in text and "qualify_pyscf_image.py" in text
    assert "--approved-plan /input/approved-plan.json" in text
    assert '--env COCHEM_SOURCE_COMMIT="$TORQ_SCIENTIFIC_SHA"' in text
    assert "--network none" in text and "--read-only" in text
    assert "secrets." not in text
    assert "${{ inputs." not in "\n".join(step.get("run", "") for step in steps)
    assert steps[-1]["if"] == "always()" and "torq-input/" in steps[-1]["with"]["path"]


def test_genuine_native_approval_and_original_transport_survive_base_controller(tmp_path):
    python = os.environ.get("COCHEM_TEST_TORQ_UI_PYTHON")
    source = os.environ.get("COCHEM_TEST_TORQ_SOURCE")
    if not python or not source:
        pytest.skip(
            "Set actual separately installed TORQ Python and genuine source checkout for native transport acceptance."
        )
    generation = """import json,sys,uuid
from cochem_torq.domain import canonical_json
from cochem_torq.service import plan_request,approve_plan
request={'schema_version':'cochem.torq.request/1','request_id':str(uuid.uuid4()),
'molecule':{'symbols':['H','H'],'geometry_bohr':[[0.,0.,0.],[0.,0.,1.4]],'charge':0,'multiplicity':1},
'recipe':'hf-sto-3g-education','products':['geometry'],
'resources':{'cores':1,'memory_mb':1024,'wall_seconds':60}}
review=plan_request(request)
approval=approve_plan(review,actor='Actual installed transport test',max_scratch_bytes=1024**2)
from pathlib import Path
Path(sys.argv[1]).write_bytes(canonical_json(approval['plan']['request']))
Path(sys.argv[2]).write_bytes(canonical_json(approval))
"""
    original_request, original_approval = (
        tmp_path / "original.json",
        tmp_path / "original-approval.json",
    )
    subprocess.run(
        [python, "-I", "-B", "-c", generation, str(original_request), str(original_approval)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    request, approval = original_request.read_bytes(), original_approval.read_bytes()
    controller_sha = "a" * 40
    environment = {
        **os.environ,
        "GITHUB_SHA": controller_sha,
        "TORQ_EXPECTED_SOURCE_SHA": controller_sha,
        "TORQ_REQUEST_B64": base64.b64encode(request).decode(),
        "TORQ_REQUEST_SHA256": hashlib.sha256(request).hexdigest(),
        "TORQ_REQUEST_ID": json.loads(request)["request_id"],
        "TORQ_ENGINE": "pyscf",
        "TORQ_APPROVED_PLAN_B64": base64.b64encode(approval).decode(),
        "TORQ_APPROVED_PLAN_SHA256": hashlib.sha256(approval).hexdigest(),
    }
    command = [
        python,
        "-I",
        "-B",
        str(Path(source) / "ci_tools/actions_request.py"),
        "--output",
        str(tmp_path / "native-input/request.json"),
        "--approved-plan-output",
        str(tmp_path / "native-input/approval.json"),
    ]
    subprocess.run(command, env=environment, check=True, capture_output=True, timeout=30)
    assert (tmp_path / "native-input/request.json").read_bytes() == request
    assert (tmp_path / "native-input/approval.json").read_bytes() == approval
    evidence = json.loads((tmp_path / "native-input/request.transport.json").read_text())
    assert evidence["source_commit"] == controller_sha
    assert evidence["scientific_calculation_performed"] is False
    environment["TORQ_REQUEST_SHA256"] = "0" * 64
    result = subprocess.run(command, env=environment, capture_output=True, timeout=30)
    assert result.returncode != 0
    environment["TORQ_REQUEST_SHA256"] = hashlib.sha256(request).hexdigest()
    environment["TORQ_EXPECTED_SOURCE_SHA"] = "b" * 40
    result = subprocess.run(command, env=environment, capture_output=True, timeout=30)
    assert result.returncode != 0
