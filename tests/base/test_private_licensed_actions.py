"""Real Actions refusal and source-transport controls; no chemistry acceptance."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

from cochem_base.interfaces.course_access import (
    CourseAccessError,
    GitHubAPI,
    verify_calculation_project,
)

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
LICENSED_WORKFLOWS = (
    "orca_calculation.yml", "cfour_calculation.yml", "orca_acceptance.yml", "cfour_acceptance.yml",
)

ACCESS_WORKFLOWS = (*LICENSED_WORKFLOWS, "orca_asset_access.yml", "ecosystem_modules.yml")


def licensed_job(filename: str) -> str:
    if filename == "orca_asset_access.yml":
        return "verify-archive"
    if filename == "ecosystem_modules.yml":
        return "modules"
    return "licensed-calculations" if "acceptance" in filename else "calculate"


def document(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def run_guard(source: str, **updates: str) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "ASSET_CREDENTIAL_NAME": "LAB_PRIVATE_RUNTIME",
        "ASSET_CREDENTIAL": "isolated-guard-test-value",
        **updates,
    }
    result = subprocess.run(["bash", "-e", "-c", source], cwd=ROOT, env=environment,
                            capture_output=True, text=True, timeout=15, check=False)
    if environment["ASSET_CREDENTIAL"]:
        assert environment["ASSET_CREDENTIAL"] not in result.stdout + result.stderr
    assert "LAB_PRIVATE_RUNTIME" not in result.stdout + result.stderr
    return result


@pytest.mark.parametrize("case", ["private", "public", "organization", "archived", "fork", "wrong-name",
                                 "missing-visibility", "boolean-id", "denied", "canonical", "wrong-canonical-owner"])
def test_current_project_visibility_uses_real_bounded_http_and_fails_closed(case):
    """Initialized HTTP metadata proves refusal logic, not hosted access."""
    canonical = case in {"canonical", "wrong-canonical-owner"}
    repository = "ProfJJK-CoChem/CoChem-BASE" if canonical else "student/project"
    owner = repository.split("/")[0]
    metadata = {"id": 41, "full_name": repository, "private": not canonical,
                "owner": {"login": owner, "type": "Organization" if canonical else "User"},
                "archived": False, "fork": False}
    if case == "public":
        metadata["private"] = False
    elif case in {"organization", "wrong-canonical-owner"}:
        metadata["owner"]["type"] = "Organization" if case == "organization" else "User"
    elif case in {"archived", "fork"}:
        metadata[case] = True
    elif case == "wrong-name":
        metadata["full_name"] = "someone/else"
    elif case == "missing-visibility":
        del metadata["private"]
    elif case == "boolean-id":
        metadata["id"] = True
    observed = []
    bearer = uuid.uuid4().hex

    class Metadata(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return None

        def do_GET(self):
            observed.append((self.path, self.headers.get("Authorization")))
            authorized = self.headers.get("Authorization") == "Bearer " + bearer
            self.send_response(403 if case == "denied" or not authorized else 200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(metadata).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Metadata)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        api = GitHubAPI(bearer, api_url=f"http://127.0.0.1:{server.server_port}", allow_loopback=True)
        if case in {"private", "canonical"}:
            receipt = verify_calculation_project(api, repository)
            assert receipt["repository"] == repository and receipt["repository_id"] == 41
            assert receipt["private"] is metadata["private"]
            assert receipt["canonical_maintainer"] is canonical
            assert receipt["verified_at"]
        else:
            with pytest.raises(CourseAccessError) as refused:
                verify_calculation_project(api, repository)
            assert bearer not in str(refused.value)
        assert observed == [("/repos/" + repository, "Bearer " + bearer)]
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()
        assert not worker.is_alive()


@pytest.mark.parametrize("case", ["default-branch", "other-branch", "colliding-tag", "changed-source", "changed-repository", "changed-request"])
def test_student_transport_binds_real_checkout_identity_before_provisioning(tmp_path, case):
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    request_id = str(uuid.uuid4())
    # Transport-only data: no invented structures, provider outputs or physical accuracy.
    request = {"schema_version": "cochem.student-request/1", "request_id": request_id,
               "repository": "student/project", "source_sha": revision, "worker_source_sha": revision,
               "resources": {"cores": 1, "maxcore_mb": 128}}
    contents = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
    output = tmp_path / "evidence"
    environment = {**os.environ, "REQUEST_ID": request_id, "REQUEST_BASE64": base64.b64encode(contents).decode(),
                   "REQUEST_SHA256": hashlib.sha256(contents).hexdigest(), "GITHUB_REPOSITORY": "student/project",
                   "GITHUB_SHA": revision, "GITHUB_REF": "refs/heads/main", "DEFAULT_BRANCH": "main",
                   "GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_OUTPUT": str(tmp_path / "outputs")}
    if case == "other-branch":
        environment["GITHUB_REF"] = "refs/heads/research"
    elif case == "colliding-tag":
        environment["GITHUB_REF"] = "refs/tags/main"
    elif case == "changed-source":
        environment["GITHUB_SHA"] = "0" * 40
    elif case == "changed-repository":
        environment["GITHUB_REPOSITORY"] = "someone/project"
    elif case == "changed-request":
        environment["REQUEST_ID"] = str(uuid.uuid4())
    completed = subprocess.run([sys.executable, str(ROOT / "scripts/run_student_research.py"), "--preflight-only",
                                "--output", str(output)], cwd=ROOT, env=environment,
                               capture_output=True, text=True, timeout=15)
    if case == "default-branch":
        assert completed.returncode == 0, completed.stderr
        assert json.loads((output / "request.json").read_text()) == request
        receipt = json.loads((output / "student-result.json").read_text())
        assert receipt["status"] == "prepared" and receipt["operation_performed"] is False
        assert (tmp_path / "outputs").read_text() == "worker_sha=" + revision + "\n"
    else:
        assert completed.returncode != 0
        assert "identity, approved default branch or exact source commit" in completed.stderr
        assert not output.exists() and not (tmp_path / "outputs").exists()


def test_student_private_project_recheck_refuses_without_current_github_identity(tmp_path):
    environment = {**os.environ, "GITHUB_TOKEN": "", "GITHUB_REPOSITORY": "student/project"}
    output = tmp_path / "unreleased"
    completed = subprocess.run([sys.executable, str(ROOT / "scripts/run_student_research.py"),
                                "--verify-project-only", "--output", str(output)], cwd=ROOT, env=environment,
                               capture_output=True, text=True, timeout=15)
    assert completed.returncode != 0 and "read-only GitHub identity is required" in completed.stderr
    assert not output.exists()


def test_student_licensed_route_is_manual_private_pinned_and_rechecks_before_assets():
    workflow = document(WORKFLOWS / "student_research.yml")
    assert set(workflow.get("on", workflow.get(True))) == {"workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    research = workflow["jobs"]["research"]
    assert research["if"].strip() == (
        "github.ref == format('refs/heads/{0}', github.event.repository.default_branch) && "
        "(github.event.repository.private == true || github.repository == 'ProfJJK-CoChem/CoChem-BASE')")
    assert not any("secret" in str(value).lower() for value in research["env"].values())
    steps = research["steps"]
    names = {step.get("name"): index for index, step in enumerate(steps)}
    visibility = names["Recheck the current private project before provisioning access"]
    audit = names["Audit the approved BASE source before application imports"]
    verified = names["Revalidate scientific capabilities and resources in the approved worker"]
    assert audit < verified < visibility
    assert "--verify-project-only" in steps[visibility]["run"]
    assert steps[visibility]["env"] == {"GITHUB_TOKEN": "${{ github.token }}"}
    checkouts = [step for step in steps if step.get("uses", "").startswith("actions/checkout@")]
    assert len(checkouts) == 2
    for checkout in checkouts:
        assert re.fullmatch(r"actions/checkout@[0-9a-f]{40}", checkout["uses"])
        assert checkout["with"]["persist-credentials"] is False
    assert checkouts[1]["with"]["repository"] == "ProfJJK-CoChem/CoChem-BASE"
    assert checkouts[1]["with"]["ref"] == "${{ steps.request.outputs.worker_sha }}"
    for engine in ("orca", "cfour"):
        index = next(i for i, step in enumerate(steps) if step.get("uses") == f"./worker/.github/actions/setup-{engine}")
        assert visibility < index
        assert steps[index]["if"] == f"steps.worker.outputs.{engine} == 'true'"
        assert steps[index]["with"]["asset-token"] == "${{ secrets[vars.COCHEM_" + engine.upper() + "_ACCESS_SECRET] }}"
        if engine == "cfour":
            assert steps[index]["with"]["required"] == "true"


@pytest.mark.parametrize("filename", ("orca_acceptance.yml", "cfour_acceptance.yml"))
@pytest.mark.parametrize("revision", ["", "a" * 40, "main", "a" * 39, "a" * 40 + "\n"])
def test_reusable_acceptance_requires_full_source_revision_before_checkout(filename, revision):
    workflow = document(WORKFLOWS / filename)
    interface = workflow.get("on", workflow.get(True))["workflow_call"]
    assert interface["inputs"]["base_ref"]["required"] is True
    assert interface["secrets"]["engine_asset_credential"]["required"] is True
    assert interface["secrets"]["base_source_credential"]["required"] is False
    steps = workflow["jobs"]["licensed-calculations"]["steps"]
    index = next(i for i, step in enumerate(steps) if step.get("name") == "Validate a reusable caller's BASE revision")
    assert steps[index]["env"] == {"BASE_REF": "${{ inputs.base_ref }}"}
    completed = run_guard(steps[index]["run"], BASE_REF=revision)
    assert (completed.returncode == 0) is (revision in {"", "a" * 40})
    if completed.returncode:
        assert "full CoChem-BASE commit SHA" in completed.stdout + completed.stderr
    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
    assert steps.index(checkout) > index
    assert checkout["with"]["ref"] == "${{ inputs.base_ref || github.sha }}"
    assert checkout["with"]["persist-credentials"] is False
    provision = next(step for step in steps if "asset-token" in step.get("with", {}))
    assert "secrets.engine_asset_credential" in provision["with"]["asset-token"]


@pytest.mark.parametrize("engine", ("orca", "cfour"))
def test_composite_missing_credential_refuses_before_download_and_retains_cleanup(tmp_path, engine):
    action = document(ROOT / f".github/actions/setup-{engine}/action.yml")
    steps = action["runs"]["steps"]
    download = next(step for step in steps if "gh release download" in step.get("run", ""))
    assert download["env"]["GH_TOKEN"] == "${{ inputs.asset-token }}"
    completed = run_guard(download["run"], GH_TOKEN="", RUNNER_TEMP=str(tmp_path),
                          COCHEM_ORCA_ASSET_REPOSITORY="Control/ApprovedEngine")
    assert completed.returncode != 0
    assert "credential" in completed.stdout if engine == "orca" else "remain disabled" in completed.stdout
    assert not list(tmp_path.iterdir())
    cleanup = next(step for step in steps if "Remove the downloaded licensed" in step.get("name", ""))
    assert cleanup["if"] == "always()"
    assert f'"$RUNNER_TEMP/cochem-{engine}-download"' in cleanup["run"]


@pytest.mark.parametrize("required", ["false", "true"])
def test_optional_cfour_failure_is_recorded_and_requested_work_fails(tmp_path, required):
    action = document(ROOT / ".github/actions/setup-cfour/action.yml")
    assert action["inputs"]["required"]["default"] == "false"
    status = next(step for step in action["runs"]["steps"] if step.get("id") == "status")
    environment_file, output_file = tmp_path / "github-env", tmp_path / "github-output"
    completed = run_guard(status["run"], COCHEM_IDENTITY_OUTCOME="success", COCHEM_DOWNLOAD_OUTCOME="failure",
                          COCHEM_INSTALL_OUTCOME="skipped", COCHEM_CFOUR_REQUIRED=required,
                          RUNNER_TEMP=str(tmp_path), GITHUB_ENV=str(environment_file), GITHUB_OUTPUT=str(output_file))
    assert (completed.returncode == 0) is (required == "false")
    receipt = json.loads((tmp_path / "cfour-evidence/installation.json").read_text())
    assert receipt["available"] is False and receipt["status"] == "unavailable"
    assert receipt["required"] is (required == "true")
    assert "could not be downloaded" in receipt["reason"]
    assert environment_file.read_text() == "COCHEM_CFOUR_AVAILABLE=false\n"
    assert "available=false\n" in output_file.read_text()


def test_instructor_archive_access_refuses_missing_credential_before_creating_download(tmp_path):
    steps = document(WORKFLOWS / "orca_asset_access.yml")["jobs"]["verify-archive"]["steps"]
    audit = next(i for i, step in enumerate(steps) if "base_ci.py audit" in step.get("run", ""))
    index = next(i for i, step in enumerate(steps) if "gh release download" in step.get("run", ""))
    assert audit < index
    assert steps[index]["env"] == {"GH_TOKEN": "${{ secrets[vars.COCHEM_ORCA_ACCESS_SECRET] }}"}
    completed = run_guard(steps[index]["run"], GH_TOKEN="", ORCA_ASSET_REPOSITORY="Control/ApprovedEngine",
                          RUNNER_TEMP=str(tmp_path))
    assert completed.returncode != 0 and "Contents read access" in completed.stdout
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("engine", ("orca", "cfour"))
@pytest.mark.parametrize("case", ["missing-selector", "invalid-selector", "missing-value", "selected"])
def test_module_workflow_validates_selected_credential_before_kit_or_engine(engine, case):
    steps = document(WORKFLOWS / "ecosystem_modules.yml")["jobs"]["modules"]["steps"]
    index = next(i for i, step in enumerate(steps) if step.get("name") == f"Validate private {engine.upper()} asset credential selection")
    guard = steps[index]
    selector = "COCHEM_" + engine.upper() + "_ACCESS_SECRET"
    assert guard["env"] == {"ASSET_CREDENTIAL_NAME": "${{ vars." + selector + " }}",
                            "ASSET_CREDENTIAL": "${{ secrets[vars." + selector + "] }}"}
    assert engine in guard["if"]
    assert index < next(i for i, step in enumerate(steps) if step.get("uses", "").startswith("actions/download-artifact@"))
    assert index < next(i for i, step in enumerate(steps) if step.get("uses") == f"./.github/actions/setup-{engine}")
    updates = {"missing-selector": {"ASSET_CREDENTIAL_NAME": ""},
               "invalid-selector": {"ASSET_CREDENTIAL_NAME": "invalid/name"},
               "missing-value": {"ASSET_CREDENTIAL": ""}, "selected": {}}[case]
    completed = run_guard(guard["run"], **updates)
    assert (completed.returncode == 0) is (case == "selected")
    if case == "missing-selector":
        assert "Configure the private" in completed.stdout
    elif case == "invalid-selector":
        assert "valid secret identifier" in completed.stdout
    elif case == "missing-value":
        assert "credential is unavailable" in completed.stdout


def test_licensed_workflow_permissions_and_instructor_pilot_triggers_remain_bounded():
    for filename in LICENSED_WORKFLOWS:
        workflow = document(WORKFLOWS / filename)
        assert workflow["permissions"] == {"contents": "read"}
        triggers = workflow.get("on", workflow.get(True))
        assert "workflow_dispatch" in triggers
        assert set(triggers) <= {"workflow_dispatch", "workflow_call", "push"}
        engine = filename.split("_")[0]
        pilot = "codex/orca-6.1.1-actions" if engine == "orca" else "codex/cfour-optional-integration"
        assert triggers["push"]["branches"] == [pilot]
        for job in workflow["jobs"].values():
            for step in job["steps"]:
                if step.get("uses", "").startswith("actions/checkout@"):
                    assert step["with"]["persist-credentials"] is False
    for filename in ("student_research.yml", "orca_asset_access.yml", "ecosystem_modules.yml"):
        workflow = document(WORKFLOWS / filename)
        assert set(workflow.get("on", workflow.get(True))) == {"workflow_dispatch"}


def test_licensed_public_yaml_uses_scoped_private_selectors_without_enumeration():
    for path in (ROOT / ".github").rglob("*.yml"):
        text = path.read_text()
        assert "toJSON(secrets)" not in text
        assert "secrets: inherit" not in text
        for engine in ("ORCA", "CFOUR"):
            assert "secrets." + engine + "_" not in text
    for filename in LICENSED_WORKFLOWS:
        workflow = document(WORKFLOWS / filename)
        job_name = "licensed-calculations" if "acceptance" in filename else "calculate"
        provision = next(step for step in workflow["jobs"][job_name]["steps"] if "asset-token" in step.get("with", {}))
        assert "secrets[vars.COCHEM_" in provision["with"]["asset-token"]


@pytest.mark.parametrize("filename", ACCESS_WORKFLOWS)
@pytest.mark.parametrize("case", ["private-dispatch", "public", "tag", "other-branch", "fork", "student-push",
                                 "invalid-source", "maintainer-pilot", "maintainer-dispatch", "maintainer-pr"])
def test_every_dedicated_engine_route_rejects_untrusted_refs_before_checkout(filename, case):
    workflow = document(WORKFLOWS / filename)
    job_name = licensed_job(filename)
    steps = workflow["jobs"][job_name]["steps"]
    guard = steps[0]
    assert guard["name"] == "Validate licensed access route before checkout"
    assert guard["env"] == {
        "PROJECT_REPOSITORY": "${{ github.repository }}",
        "PROJECT_PRIVATE": "${{ github.event.repository.private }}",
        "PROJECT_FORK": "${{ github.event.repository.fork }}",
        "PROJECT_EVENT": "${{ github.event_name }}",
        "PROJECT_REF": "${{ github.ref }}",
        "PROJECT_DEFAULT_BRANCH": "${{ github.event.repository.default_branch }}",
        "PROJECT_SOURCE_SHA": "${{ github.sha }}",
    }
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    inputs = {"PROJECT_REPOSITORY": "student/project", "PROJECT_PRIVATE": "true", "PROJECT_FORK": "false",
              "PROJECT_EVENT": "workflow_dispatch", "PROJECT_REF": "refs/heads/main",
              "PROJECT_DEFAULT_BRANCH": "main", "PROJECT_SOURCE_SHA": revision}
    if case == "public":
        inputs["PROJECT_PRIVATE"] = "false"
    elif case == "tag":
        inputs["PROJECT_REF"] = "refs/tags/main"
    elif case == "other-branch":
        inputs["PROJECT_REF"] = "refs/heads/research"
    elif case == "fork":
        inputs["PROJECT_FORK"] = "true"
    elif case == "student-push":
        inputs["PROJECT_EVENT"] = "push"
    elif case == "invalid-source":
        inputs["PROJECT_SOURCE_SHA"] = "main"
    elif case.startswith("maintainer-"):
        inputs["PROJECT_REPOSITORY"] = "ProfJJK-CoChem/CoChem-BASE"
        inputs["PROJECT_PRIVATE"] = "false"
        if case == "maintainer-pilot":
            inputs["PROJECT_EVENT"] = "push"
            triggers = workflow.get("on", workflow.get(True))
            inputs["PROJECT_REF"] = "refs/heads/" + (triggers["push"]["branches"][0] if "push" in triggers else "main")
        elif case == "maintainer-pr":
            inputs["PROJECT_EVENT"] = "pull_request"
            inputs["PROJECT_REF"] = "refs/pull/1/merge"
    completed = run_guard(guard["run"], **inputs)
    allowed = case in {"private-dispatch", "maintainer-pilot", "maintainer-dispatch"}
    assert (completed.returncode == 0) is allowed
    if not allowed:
        assert "::error::" in completed.stdout
    assert "uses" not in guard and "secrets" not in str(guard["env"])


@pytest.mark.parametrize("filename", ACCESS_WORKFLOWS)
def test_dedicated_engine_visibility_recheck_is_isolated_after_audit_before_assets(tmp_path, filename):
    workflow = document(WORKFLOWS / filename)
    job_name = licensed_job(filename)
    job = workflow["jobs"][job_name]
    steps = job["steps"]
    audit = next(i for i, step in enumerate(steps) if "base_ci.py audit" in step.get("run", ""))
    index = next(i for i, step in enumerate(steps) if step.get("name") == "Recheck the current project before licensed provisioning")
    provision = next(i for i, step in enumerate(steps)
                     if "asset-token" in step.get("with", {}) or "gh release download" in step.get("run", ""))
    assert audit < index < provision
    for binding_index, step in enumerate(steps):
        if any("secrets[" in str(value) or "secrets.engine_asset_credential" in str(value)
               for value in (*step.get("env", {}).values(), *step.get("with", {}).values())):
            assert index < binding_index
    assert steps[index]["env"] == {"GITHUB_TOKEN": "${{ github.token }}"}
    assert "python -B -I -S scripts/run_student_research.py --verify-project-only" in steps[index]["run"]
    assert not any("secrets" in str(value) for value in job["env"].values())
    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
    assert re.fullmatch(r"actions/checkout@[0-9a-f]{40}", checkout["uses"])
    assert checkout["with"]["persist-credentials"] is False
    expected_ref = "${{ inputs.base_ref || github.sha }}" if "acceptance" in filename else "${{ github.sha }}"
    assert checkout["with"]["ref"] == expected_ref
    python_step = next(step for step in steps if step.get("uses", "").startswith("actions/setup-python@"))
    assert re.fullmatch(r"actions/setup-python@[0-9a-f]{40}", python_step["uses"])
    assert steps.index(python_step) < index
    engine = filename.split("_")[0]
    evidence = "orca-access-evidence" if filename == "orca_asset_access.yml" else (
        "cochem-modules/evidence" if filename == "ecosystem_modules.yml" else f"{engine}-evidence")
    (tmp_path / evidence).mkdir(parents=True)
    # Run the exact authored gate with no ambient site packages, current project
    # identity or engine reader. Refusal must occur before creating access proof.
    completed = run_guard(steps[index]["run"], RUNNER_TEMP=str(tmp_path),
                          GITHUB_TOKEN="", GITHUB_REPOSITORY="student/project")
    assert completed.returncode != 0
    assert "read-only GitHub identity is required" in completed.stderr
    assert not list(tmp_path.rglob("project-visibility.json"))


@pytest.mark.parametrize("source_case", ["public", "denied-private", "unpinned"])
def test_canonical_source_batch_uses_optional_reader_and_preserves_real_failures(tmp_path, source_case):
    """Real local Git/HTTP transport controls, not live GitHub authorization."""
    import json
    import sys
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    steps = document(WORKFLOWS / "ecosystem_modules.yml")["jobs"]["modules"]["steps"]
    batch = next(step for step in steps if step.get("name") == "Fetch or install reviewed sources and mandatory authority")
    assert batch["env"] == {"COCHEM_SOURCE_CREDENTIAL": "${{ secrets[vars.COCHEM_SOURCE_ACCESS_SECRET] }}"}
    assert "--require-source-token" not in batch["run"]
    source = tmp_path / "reviewed-source"
    source.mkdir()
    subprocess.run(["git", "init", str(source)], check=True, capture_output=True)
    (source / "README.md").write_text("Actual source transport control; no package installation or chemistry.\n")
    subprocess.run(["git", "-C", str(source), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(source), "-c", "user.name=Transport Control",
                    "-c", "user.email=control@example.invalid", "commit", "-m", "Reviewed transport bytes"],
                   check=True, capture_output=True)
    revision = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                              check=True, capture_output=True, text=True).stdout.strip()

    class Denied(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return None

        def do_GET(self):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Read permission denied by actual transport control")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Denied)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        destination = source.as_uri() if source_case != "denied-private" else f"http://127.0.0.1:{server.server_port}/denied.git"
        configuration = tmp_path / "git.config"
        subprocess.run(["git", "config", "--file", str(configuration),
                        f"url.{destination}.insteadOf", "https://github.com/Control/ReviewedModule.git"], check=True)
        manifest = tmp_path / "catalog.json"
        manifest.write_text(json.dumps({"schema_version": "cochem.module-distribution/1", "modules": {
            "control": {"repository": "Control/ReviewedModule", "revision": "main" if source_case == "unpinned" else revision,
                        "distribution": None, "adapter": None, "adapter_requirements": [], "operations": []}}}))
        runtime = tmp_path / "runtime"
        environment = {name: value for name, value in os.environ.items()
                       if name in {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TMPDIR", "TEMP", "TMP"}}
        environment.update(MODULE_ACTION="fetch", MODULE_IDS="control", MODULE_MANIFEST=str(manifest),
                           COCHEM_ARTIFACT_DIR=str(runtime), COCHEM_SOURCE_CREDENTIAL="", KIT_SELECTED="false",
                           GIT_CONFIG_GLOBAL=str(configuration), GIT_CONFIG_NOSYSTEM="1",
                           NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost",
                           PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "src"), str(ROOT / "src/cochem_base")]),
                           PYTHONDONTWRITEBYTECODE="1")
        # The authored fetch route uses python -m before installation. Select the
        # current actual interpreter through PATH rather than replacing any call.
        environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environment.get("PATH", "")
        completed = subprocess.run(["bash", "-e", "-c", batch["run"]], cwd=ROOT, env=environment,
                                   capture_output=True, text=True, timeout=30)
        report_path = runtime / "evidence/installations.json"
        if source_case == "unpinned":
            assert completed.returncode != 0
            assert "revision" in completed.stdout.lower() or "commit" in completed.stdout.lower()
            assert not report_path.exists()
        else:
            report = json.loads(report_path.read_text())
            assert report["scientific_accuracy_established"] is False
            assert "configuration_error" not in report
            if source_case == "public":
                assert completed.returncode == 0, completed.stdout + completed.stderr
                assert report["success"] is True and report["failures"] == []
                assert report["modules"][0]["status"] == "downloaded"
                assert report["modules"][0]["revision"] == revision
                retained = Path(report["modules"][0]["source_path"])
                assert (retained / "README.md").read_bytes() == (source / "README.md").read_bytes()
            else:
                assert completed.returncode != 0 and report["success"] is False
                assert report["modules"] == [] and len(report["failures"]) == 1
                assert "Fetch pinned module source failed" in report["failures"][0]["message"]
                assert "403" in report["failures"][0]["message"]
            assert not list(runtime.rglob("installation.json"))
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()
        assert not worker.is_alive()
