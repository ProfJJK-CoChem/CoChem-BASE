"""Request/UI/transport boundaries; no native calculation or installation fixtures."""
from __future__ import annotations

import hashlib
import json
import threading
import urllib.request
import zipfile

import pytest

from scripts import hosted_module_kit as transport
from scripts.module_request import (
    TOPOS_OPERATIONS,
    execution_timeout,
    handoff_options,
    hosted_topos_request,
    read_topos_request,
    repository_member,
)


@pytest.fixture
def payload():
    return {"molecule": {"symbols": ["O", "H", "H"], "coordinates": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                         "charge": 0, "multiplicity": 1, "isotopes": [18, 2, None]},
            "purpose": "energy", "engine": "xtb", "method": "GFN2-xTB", "threads": 1, "memory_mb": 512,
            "budget_seconds": 30, "calculation_environment": "local", "metadata": {"assignment": "no native calculation"},
            "per_geometry_budget_seconds": 15.0, "temperature_k": 300.0}


@pytest.fixture
def request_file(tmp_path, payload):
    path = tmp_path / "request.json"
    path.write_text(json.dumps(payload))
    return path


@pytest.fixture
def xyz(tmp_path):
    path = tmp_path / "geometry.xyz"
    path.write_text("3\nElectronic symbols; nuclear state declared in request\nO 0 0 0\nH 1 0 0\nH 0 1 0\n")
    return path


@pytest.mark.parametrize("purpose", TOPOS_OPERATIONS)
def test_every_provider_purpose_preserves_entire_request(request_file, payload, purpose):
    payload["purpose"] = purpose
    payload["matrix_inputs"] = {"explicit_component": {"method": "unchanged", "state": [0, 1]}}
    request_file.write_text(json.dumps(payload))
    operation, options = handoff_options("topos", request_file)
    assert operation == purpose
    assert options == {"topos_request": payload}
    assert execution_timeout(40, options) == 40


@pytest.mark.parametrize("mutation", ["duplicate", "nan", "overflow", "state", "purpose", "resource", "boolean"])
def test_ambiguous_or_incomplete_request_rejected(request_file, payload, mutation):
    if mutation == "duplicate":
        raw = request_file.read_text().replace('"purpose": "energy"', '"purpose": "energy", "purpose": "gradient"')
    elif mutation in {"nan", "overflow"}:
        raw = request_file.read_text().replace('300.0', 'NaN' if mutation == "nan" else '1e999')
    else:
        if mutation == "state":
            del payload["molecule"]["charge"]
        if mutation == "purpose":
            payload["purpose"] = "geometry_analysis"
        if mutation == "resource":
            del payload["memory_mb"]
        if mutation == "boolean":
            payload["threads"] = True
        raw = json.dumps(payload)
    request_file.write_text(raw)
    with pytest.raises(ValueError):
        read_topos_request(request_file)


def test_timeout_and_recipient_cannot_drop_typed_request(request_file):
    _, options = handoff_options("topos", request_file)
    with pytest.raises(ValueError, match="cover"):
        execution_timeout(29, options)
    with pytest.raises(ValueError, match="only"):
        handoff_options("torq", request_file)
    with pytest.raises(ValueError, match="explicit"):
        handoff_options("topos", None)
    assert handoff_options("torq", None) == ("geometry_analysis", {})


def test_actual_base_handoff_preserves_isotope_request(request_file, xyz, tmp_path):
    from cochem_base.interfaces.artifact_handoff import load_module_handoff, prepare_module_handoff
    operation, options = handoff_options("topos", request_file)
    prepare_module_handoff("topos", xyz, tmp_path / "handoff", operation=operation, options=options)
    receipt = load_module_handoff(tmp_path / "handoff/handoff.json")
    request = receipt.options["topos_request"]
    assert request["molecule"]["isotopes"] == [18, 2, None]
    assert request["per_geometry_budget_seconds"] == 15
    assert request == json.loads(request_file.read_text())
    assert receipt.scientific_execution_performed is False


def test_bound_handoff_rejects_changed_geometry_before_any_native_job(request_file, xyz, tmp_path):
    from cochem_base.interfaces.artifact_handoff import load_module_handoff, prepare_module_handoff
    operation, options = handoff_options("topos", request_file)
    prepare_module_handoff("topos", xyz, tmp_path / "handoff", operation=operation, options=options)
    handoff = load_module_handoff(tmp_path / "handoff/handoff.json")
    retained = tmp_path / "handoff" / handoff.artifact.filename
    retained.write_text(retained.read_text().replace("H 1 0 0", "H 2 0 0"))
    with pytest.raises(ValueError, match="SHA|integrity|hash|changed"):
        load_module_handoff(tmp_path / "handoff/handoff.json")
    assert not list(tmp_path.rglob("engine.stdout"))


@pytest.mark.parametrize("case", ["public", "remote", "cores", "memory", "deadline"])
def test_hosted_request_preserves_private_allocation_boundary(request_file, payload, tmp_path, case):
    if case == "remote":
        payload["calculation_environment"] = "github-actions"
    if case == "cores":
        payload["threads"] = 3
    if case == "memory":
        payload["memory_mb"] = 4097
    request_file.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        hosted_topos_request(tmp_path, request_file=request_file.name, timeout=14401 if case == "deadline" else 180,
                             repository_private=case != "public")


@pytest.mark.parametrize("value", ["../outside", "/absolute", "bad\nvalue"])
def test_hosted_member_rejects_escapes(tmp_path, value):
    with pytest.raises(ValueError):
        repository_member(tmp_path, value)


def test_hosted_member_rejects_linked_inputs(tmp_path, request_file):
    (tmp_path / "alias").symlink_to(request_file)
    with pytest.raises(ValueError, match="links"):
        repository_member(tmp_path, "alias")


def test_dashboard_rejects_source_checkout_storage_before_bootstrap(tmp_path):
    from pathlib import Path

    from scripts.hosted_dashboard import setup_dashboard
    root = Path(__file__).resolve().parents[2]
    with pytest.raises(ValueError, match="outside the source checkout"):
        setup_dashboard(tmp_path / "absent/python", root / "forbidden-runtime", 1)
    assert not (root / "forbidden-runtime").exists()


def test_dashboard_rejects_redirected_native_storage_before_bootstrap(tmp_path):
    from scripts.hosted_dashboard import setup_dashboard
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    (runtime / "free-engines").symlink_to(unrelated, target_is_directory=True)
    with pytest.raises(ValueError, match="inside their external profile"):
        setup_dashboard(tmp_path / "absent/python", runtime, 1)
    assert not list(unrelated.iterdir())


def _gui_process(tmp_path, body):
    """Drive actual widgets in an isolated process with owned external storage."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    environment = {name: value for name, value in os.environ.items()
                   if name in {"PATH", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT", "COMSPEC", "WINDIR"}}
    environment.update(COCHEM_ARTIFACT_DIR=str(tmp_path / "gui-runtime"),
                       COCHEM_CONFIG=str(tmp_path / "absent-registry.json"),
                       COCHEM_STUDENT_AUTO_SETUP="0", COCHEM_STUDENT_AUTO_REMOTE_CHECK="0",
                       COCHEM_ASSIGNMENT_ROOT=str(tmp_path), QT_QPA_PLATFORM="offscreen",
                       COCHEM_HEADLESS="1", PYTHONDONTWRITEBYTECODE="1")
    program = "import sys\nsys.path[:0]=" + repr([str(root), str(root / "src")]) + "\n"
    program += "from ui.voila_layout.cochem_gui import CoChemGUI\ngui=CoChemGUI()\n"
    program += body + "\ngui._inbox_stop.set()\ngui._hpc_monitor_stop.set()\ngui._actions_monitor_stop.set()\ngui._cleanup_topos_search()\n"
    completed = subprocess.run([sys.executable, "-B", "-c", program], cwd=tmp_path,
                               env=environment, capture_output=True, text=True, timeout=40)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return completed


def test_gui_prepares_real_integrity_bound_handoff_without_execution(xyz, tmp_path):
    _gui_process(tmp_path, f"""
from cochem_base.interfaces.artifact_handoff import load_module_handoff
gui.module_recipient.value='torq'
gui.module_artifact.value={str(xyz)!r}
gui.module_output.value={str(tmp_path / 'packages')!r}
gui._prepare_module_handoff()
handoff=load_module_handoff(gui._last_module_handoff_path)
assert handoff.module_id=='torq' and handoff.operation=='geometry_analysis'
assert handoff.artifact.sha256==__import__('hashlib').sha256(open({str(xyz)!r},'rb').read()).hexdigest()
assert handoff.scientific_execution_performed is False
assert handoff.options=={{}} and handoff.artifact.metadata['atom_count']==3
assert 'no scientific job was submitted' in gui.module_handoff_status.value
""")
    assert not list(tmp_path.rglob("result.json"))


def test_pre_cancelled_typed_receiver_never_reads_missing_input_or_publishes(tmp_path):
    from cochem_base.core_engine.cochem_core_subprocess_broker import SubprocessCancelledError
    from scripts.mandatory_ecosystem import execute
    cancellation = threading.Event()
    cancellation.set()
    with pytest.raises(SubprocessCancelledError, match="cancelled before"):
        execute(tmp_path / "absent-handoff.json", tmp_path / "unpublished", {},
                tmp_path / "absent-modules", timeout=1, cancellation_event=cancellation)
    assert not (tmp_path / "unpublished").exists()


def _archive_fixture(tmp_path, members=None):
    archive = tmp_path / "artifact.zip"
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    members = members or {"kit/wheels/SHA256SUMS": b"transport bytes only; not an installable kit"}
    with zipfile.ZipFile(archive, "w") as handle:
        for name, value in members.items():
            handle.writestr(name, value)
            path = extracted / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
    return archive, extracted, hashlib.sha256(archive.read_bytes()).hexdigest()


def test_artifact_actual_zip_and_every_extracted_file_are_bound(tmp_path):
    archive, extracted, digest = _archive_fixture(tmp_path)
    inventory = transport.verify_extracted_archive(archive, extracted, digest)
    assert set(inventory) == {"kit/wheels/SHA256SUMS"}
    assert inventory["kit/wheels/SHA256SUMS"]["size_bytes"] > 0


@pytest.mark.parametrize("change", ["digest", "payload", "extra", "link", "missing"])
def test_artifact_transport_tamper_rejected(tmp_path, change):
    archive, extracted, digest = _archive_fixture(tmp_path)
    payload = extracted / "kit/wheels/SHA256SUMS"
    if change == "digest":
        digest = "0" * 64
    elif change == "payload":
        payload.write_bytes(b"x" * payload.stat().st_size)
    elif change == "extra":
        (extracted / "unlisted.py").write_text("not executed")
    elif change == "link":
        payload.unlink()
        payload.symlink_to(archive)
    elif change == "missing":
        payload.unlink()
    with pytest.raises(ValueError):
        transport.verify_extracted_archive(archive, extracted, digest)


def test_transport_redirect_never_forwards_token_to_blob_host():
    request = urllib.request.Request("https://api.github.com/example", headers={"Authorization": "Bearer test-only"})
    redirected = transport._Redirect().redirect_request(request, None, 302, "Found", {}, "https://objects.githubusercontent.com/blob")
    assert not redirected.has_header("Authorization")
    with pytest.raises(ValueError, match="HTTPS"):
        transport._Redirect().redirect_request(request, None, 302, "Found", {}, "http://example.com/blob")


@pytest.mark.parametrize("change", ["failed", "fork", "expired", "missing-digest", "duplicate"])
def test_api_selection_rejects_untrusted_artifact_identity(change):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    # Actual loopback HTTP metadata transport, never native or scientific data.
    run = {"id": 123, "status": "completed", "conclusion": "success", "repository": {"full_name": "owner/repo", "private": True},
           "head_repository": {"full_name": "owner/repo"}, "head_sha": "a" * 40, "run_attempt": 1}
    artifact = {"id": 456, "name": "reviewed-kit", "expired": False, "digest": "sha256:" + "b" * 64,
                "size_in_bytes": 1000, "workflow_run": {"id": 123}}
    if change == "failed":
        run["conclusion"] = "failure"
    if change == "fork":
        run["head_repository"]["full_name"] = "other/repo"
    if change == "expired":
        artifact["expired"] = True
    if change == "missing-digest":
        artifact.pop("digest")
    values = [artifact, dict(artifact)] if change == "duplicate" else [artifact]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.server.requests.append(self.path)
            payload = self.server.routes.get(self.path)
            raw = json.dumps(payload if payload is not None else {"message": "Unknown route"}).encode()
            self.send_response(200 if payload is not None else 404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format, *arguments):
            self.server.messages.append(format % arguments)

    class Server(ThreadingHTTPServer):
        def __init__(self):
            super().__init__(("127.0.0.1", 0), Handler)
            self.requests = []
            self.messages = []
            self.routes = {
                "/repos/owner/repo/actions/runs/123": run,
                "/repos/owner/repo/actions/runs/123/artifacts?per_page=100&page=1": {"artifacts": values},
            }

    class Client:
        def __init__(self, server):
            self.base_url = f"http://127.0.0.1:{server.server_port}/repos/"
            self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def request(self, repository, suffix):
            with self.opener.open(self.base_url + repository + "/" + suffix, timeout=5) as response:
                return json.loads(response.read())

    server = Server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(ValueError):
            transport.identify("owner/repo", "123", "reviewed-kit", client=Client(server))
        expected = ["/repos/owner/repo/actions/runs/123"]
        if change not in {"failed", "fork"}:
            expected.append("/repos/owner/repo/actions/runs/123/artifacts?per_page=100&page=1")
        assert server.requests == expected
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


@pytest.mark.parametrize("case", ["valid", "automatic", "automatic-typed", "public", "branch", "event",
                                 "tag-collision", "no-kit", "legacy-topos", "foreign-profile", "zero-timeout"])
def test_actual_workflow_preflight_before_any_network_process(tmp_path, request_file, xyz, case):
    import os
    import subprocess
    import sys
    from pathlib import Path

    import yaml
    workflow = Path(__file__).resolve().parents[2] / ".github/workflows/ecosystem_modules.yml"
    steps = yaml.safe_load(workflow.read_text())["jobs"]["modules"]["steps"]
    authored = next(step["run"] for step in steps if step.get("name") == "Validate explicit selection, request and allocation")
    source = authored.split("python - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    (tmp_path / "scripts").mkdir()
    for catalog in ("module-distribution.json", "module-distribution-legacy-kit-1.0.1.json"):
        (tmp_path / "scripts" / catalog).write_bytes((workflow.parents[2] / "scripts" / catalog).read_bytes())
    values = {"MODULE_IDS": "topos", "MODULE_ACTION": "topos_request", "ENGINE_PROFILE": "free",
              "INSTALLATION_MODE": "legacy-kit",
              "REPOSITORY_PRIVATE": "true", "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF_NAME": "main",
              "GITHUB_REF": "refs/heads/main",
              "DEFAULT_BRANCH": "main", "TOPOS_REQUEST": request_file.name, "RECEIVER_TIMEOUT": "180",
              "KIT_RUN_ID": "123", "KIT_ARTIFACT_NAME": "kit", "KIT_SUBDIRECTORY": ".",
              "MODULE_XYZ": xyz.name, "GITHUB_ENV": str(tmp_path / "github-env")}
    if case in {"automatic", "automatic-typed"}:
        values.update(INSTALLATION_MODE="automatic", KIT_RUN_ID="", KIT_ARTIFACT_NAME="")
        if case == "automatic":
            values.update(MODULE_ACTION="geometry_analysis", MODULE_IDS="topos torq", TOPOS_REQUEST="")
    if case == "zero-timeout":
        values["RECEIVER_TIMEOUT"] = "0"
    if case == "public":
        values["REPOSITORY_PRIVATE"] = "false"
    if case == "branch":
        values["GITHUB_REF_NAME"] = "unreviewed"
        values["GITHUB_REF"] = "refs/heads/unreviewed"
    if case == "tag-collision":
        values["GITHUB_REF"] = "refs/tags/main"
    if case == "event":
        values["GITHUB_EVENT_NAME"] = "push"
    if case == "no-kit":
        values["KIT_RUN_ID"] = ""
    if case == "legacy-topos":
        values["MODULE_ACTION"] = "geometry_analysis"
        values["TOPOS_REQUEST"] = ""
    if case == "foreign-profile":
        values["ENGINE_PROFILE"] = "unreviewed-installer"
    child = tmp_path / "authored-preflight.py"
    child.write_text("import sys\nsys.path.insert(0, " + repr(str(workflow.parents[2])) + ")\n" + source)
    completed = subprocess.run([sys.executable, str(child)], cwd=tmp_path,
                               env=dict(os.environ, **values), capture_output=True, text=True, timeout=30)
    if case in {"valid", "automatic", "automatic-typed"}:
        assert completed.returncode == 0, completed.stderr
        observed = dict(line.split("=", 1) for line in Path(values["GITHUB_ENV"]).read_text().splitlines())
        assert observed["TOPOS_SELECTED"] == "true"
        assert observed["KIT_SELECTED"] == ("true" if case == "valid" else "false")
        assert Path(observed["MODULE_MANIFEST"]).name == (
            "module-distribution-legacy-kit-1.0.1.json" if case == "valid" else "module-distribution.json")
    else:
        assert completed.returncode != 0
        expected = {"public": "private", "branch": "default-branch dispatch",
                    "tag-collision": "default-branch dispatch",
                    "event": "default-branch dispatch", "no-kit": "run ID and name",
                    "legacy-topos": "typed request", "foreign-profile": "Unsupported engine profile",
                    "zero-timeout": "allocation must be finite"}
        assert expected[case] in completed.stderr


def test_actual_workflow_verifies_kit_before_engine_provisioning_and_isolated_execution():
    from pathlib import Path

    import yaml
    document = yaml.safe_load((Path(__file__).resolve().parents[2] / ".github/workflows/ecosystem_modules.yml").read_text())
    assert document["permissions"] == {"contents": "read", "actions": "read"}
    steps = document["jobs"]["modules"]["steps"]
    names = [step.get("name") for step in steps]
    assert names.index("Verify actual artifact bytes and select the kit") < names.index("Verify the kit against the installed BASE catalog")
    assert names.index("Verify the kit against the installed BASE catalog") < names.index("Provision approved ORCA and MPI")
    download = next(step for step in steps if step.get("uses") == "actions/download-artifact@v4")
    assert download["with"]["repository"] == "${{ github.repository }}"
    execute = next(step["run"] for step in steps if step.get("name") == "Execute the validated module request")
    assert "python -I -B -" in execute and "raise SystemExit(main(arguments))" in execute
    upload = next(step["with"]["path"] for step in steps if step.get("uses") == "actions/upload-artifact@v4")
    assert "cochem-modules/evidence" in upload and "cochem-modules/Modules" not in upload


@pytest.mark.parametrize("action", ["install", "topos_request", "geometry_analysis"])
def test_batch_topos_prerequisites_reject_before_install(tmp_path, action):
    from scripts import run_module_installation as batch

    manifest = batch.DEFAULT_MANIFEST.with_name("module-distribution-legacy-kit-1.0.1.json")
    expected = "geometry_analysis" if action == "geometry_analysis" else "explicit verified ecosystem kit"
    with pytest.raises(ValueError, match=expected):
        batch.run_batch(action=action, modules=["topos"], manifest=manifest,
                        root=tmp_path / "modules", output=tmp_path / "evidence")
    assert not (tmp_path / "evidence").exists()
    assert not (tmp_path / "modules").exists()


def test_gui_missing_installed_authority_is_never_rendered_as_completed_science(xyz, tmp_path):
    _gui_process(tmp_path, f"""
gui.calc_env_dropdown.value='local'
gui.module_recipient.value='torq'
gui.module_root.value={str(tmp_path / 'absent-modules')!r}
gui.module_artifact.value={str(xyz)!r}
gui.module_output.value={str(tmp_path / 'packages')!r}
gui._run_module_geometry()
gui._module_worker.join(timeout=15)
assert not gui._module_worker.is_alive()
assert 'failed' in gui.module_handoff_status.value.lower(), gui.module_handoff_status.value
assert 'completed' not in gui.module_handoff_status.value.lower()
assert not gui.btn_module_run.disabled
""")
    assert not list(tmp_path.rglob("result.json"))
    assert not list(tmp_path.rglob("engine.stdout"))


@pytest.mark.parametrize("failure", ["missing", "malformed"])
def test_batch_subprocess_failures_preserve_structured_results_and_continue(tmp_path, request_file, xyz, capsys, failure):
    from cochem_base.interfaces.artifact_handoff import load_module_handoff
    from scripts.manage_modules import DEFAULT_MANIFEST
    from scripts.run_module_job import main

    manifest = DEFAULT_MANIFEST.with_name("module-distribution-legacy-kit-1.0.1.json")
    modules = tmp_path / "Modules"
    if failure == "malformed":
        for name in ("topos", "torq"):
            directory = modules / name
            directory.mkdir(parents=True)
            (directory / "installation.json").write_text("Invalid JSON; not an installed authority receipt")
    result = main(["--modules", "topos", "torq", "--xyz-file", str(xyz), "--output", str(tmp_path / "batch"),
                   "--root", str(modules), "--manifest", str(manifest),
                   "--topos-request", str(request_file), "--timeout", "45"])
    assert result == 1
    reports = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [item["module_id"] for item in reports] == ["topos", "torq"]
    assert all(item["status"] == "failed" for item in reports)
    assert all("Cannot read a valid module receipt" in item["error"] for item in reports)
    for name, report in zip(("topos", "torq"), reports):
        assert str(modules / name / "installation.json") in report["error"]
        handoff = load_module_handoff(tmp_path / "batch" / name / "handoff/handoff.json")
        assert handoff.module_id == name
        assert handoff.scientific_execution_performed is False
        assert not (tmp_path / "batch" / name / "execution").exists()
    assert not list(tmp_path.rglob("engine.stdout"))


def test_actual_dashboard_build_environment_drops_credentials_and_loader_overrides(tmp_path):
    import os
    import subprocess
    import sys

    from scripts.hosted_dashboard import setup_build_environment
    incoming = {"PATH": os.environ.get("PATH", ""), "COCHEM_MODULES": "topos torq",
                "PYTHONPATH": str(tmp_path / "untrusted"), "PYTHONHOME": str(tmp_path / "untrusted"),
                "VIRTUAL_ENV": str(tmp_path / "untrusted"), "SSH_ASKPASS": "untrusted",
                "GIT_CONFIG_COUNT": "1", "BUILD_ACCESS_KEY": "non-secret engineering input",
                "BUILD_CREDENTIAL": "non-secret engineering input"}
    environment = setup_build_environment(incoming)
    completed = subprocess.run([sys.executable, "-I", "-B", "-c",
                                "import json,os; print(json.dumps(sorted(os.environ)))"],
                               cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=10)
    assert completed.returncode == 0, completed.stderr
    names = set(json.loads(completed.stdout))
    assert not names.intersection({"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "SSH_ASKPASS",
                                   "GIT_CONFIG_COUNT", "BUILD_ACCESS_KEY", "BUILD_CREDENTIAL"})
    assert {"COCHEM_MODULES", "PYTHONNOUSERSITE", "GIT_CONFIG_NOSYSTEM", "GIT_TERMINAL_PROMPT"} <= names


@pytest.fixture
def audit_layout(tmp_path):
    from scripts.manage_modules import DEFAULT_MANIFEST, _paths, load_manifest
    spec = load_manifest(DEFAULT_MANIFEST)["modules"]["topos"]
    modules = tmp_path / "Modules"
    _, location, _, _ = _paths("topos", spec, modules)
    runtime = location / "runtime"
    # Explicit transport fixtures carry no forged successful audit or chemistry.
    files = {"setup-receipt.json": b'{"status":"failed","fixture":"transport"}',
             "mandatory-deployment.json": b'{"selected_repositories":[]}',
             "Registry/setup_summary.json": b'{"status":"incomplete","phases":[]}',
             "Registry/cochem_system_config.json": b'{"status":"UNINITIALIZED"}',
             "Registry/cochem_system_config.json.sha256": b"transport-fixture-only\n",
             "setup-logs/mandatory-stage0.log": b"Actual transport fixture: setup interrupted.\n"}
    for name, payload in files.items():
        path = runtime / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    for name in ("free-engines/xtb", "Silos/private-native-library.so", "ui-env/bin/python", "Registry/unrelated.bin"):
        path = runtime / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"Excluded transport fixture; no native executable")
    return spec, modules, runtime, files


def test_retention_keeps_exact_audit_bytes_and_excludes_silos_engines(audit_layout, tmp_path):
    from scripts.run_module_installation import retain_setup_evidence
    spec, modules, runtime, files = audit_layout
    output = tmp_path / "evidence"
    receipt = retain_setup_evidence(spec, modules, output)
    assert receipt["status"] == "retained"
    assert set(receipt["files"]) == set(files)
    assert receipt["missing_members"] == ["mandatory-validation.json"]
    assert receipt["original_runtime"] == str(runtime)
    for name, raw in files.items():
        assert (output / name).read_bytes() == raw
        assert receipt["files"][name]["sha256"] == hashlib.sha256(raw).hexdigest()
        assert receipt["files"][name]["source_path"] == str(runtime / name)
    assert not (output / "Silos").exists() and not (output / "free-engines").exists()
    assert "no new" in receipt["scope"]


@pytest.mark.parametrize("target", ["runtime", "Registry", "setup-logs/redirect.log", "setup-receipt.json"])
def test_retention_rejects_symlinked_audit_sources(audit_layout, tmp_path, target):
    import shutil

    from scripts.run_module_installation import retain_setup_evidence
    spec, modules, runtime, _ = audit_layout
    selected = runtime if target == "runtime" else runtime / target
    if selected.is_dir():
        shutil.rmtree(selected)
    elif selected.exists():
        selected.unlink()
    selected.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="redirect|regular"):
        retain_setup_evidence(spec, modules, tmp_path / "retained")


def test_retention_does_not_claim_missing_runtime_as_completed(audit_layout, tmp_path):
    import shutil

    from scripts.run_module_installation import retain_setup_evidence
    spec, modules, runtime, _ = audit_layout
    shutil.rmtree(runtime)
    receipt = retain_setup_evidence(spec, modules, tmp_path / "retained")
    assert receipt["status"] == "unavailable" and receipt["files"] == {}
    assert "Registry/" in receipt["missing_members"]


def test_retention_size_bound_and_previous_evidence_are_preserved(audit_layout, tmp_path):
    from scripts.run_module_installation import retain_setup_evidence
    spec, modules, runtime, _ = audit_layout
    with (runtime / "setup-logs/oversized.log").open("wb") as stream:
        stream.truncate(128 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="128 MiB"):
        retain_setup_evidence(spec, modules, tmp_path / "retained")
    previous = tmp_path / "previous"
    previous.mkdir()
    (previous / "marker").write_text("keep me")
    with pytest.raises(ValueError, match="fresh"):
        retain_setup_evidence(spec, modules, previous)
    assert (previous / "marker").read_text() == "keep me"


def test_workflow_retains_audit_after_failure_before_always_upload():
    from pathlib import Path

    import yaml
    document = yaml.safe_load((Path(__file__).resolve().parents[2] / ".github/workflows/ecosystem_modules.yml").read_text())
    steps = document["jobs"]["modules"]["steps"]
    retained = next(step for step in steps if step.get("name") == "Retain the actual mandatory setup audit")
    assert "always()" in retained["if"]
    assert "retain_setup_evidence" in retained["run"]
    assert "root / 'Modules'" in retained["run"] and "root / 'evidence' / 'mandatory-setup'" in retained["run"]
    assert steps.index(retained) < next(i for i, step in enumerate(steps) if step.get("uses") == "actions/upload-artifact@v4")


def test_dashboard_bootstrap_still_starts_before_base_is_installed(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts/hosted_dashboard.py"
    environment = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
    result = subprocess.run([sys.executable, "-I", "-S", str(script), "--help"],
                            cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert "setup" in result.stdout and "start" in result.stdout


@pytest.mark.parametrize("location", ["source-root-parent", "source-module-parent", "source-revision-parent", "destination-parent"])
def test_setup_retention_rejects_redirected_parents_before_copy(audit_layout, tmp_path, location):
    import shutil

    from scripts.run_module_installation import retain_setup_evidence
    spec, modules, runtime, _ = audit_layout
    output = tmp_path / "evidence"
    if location == "source-root-parent":
        alias = tmp_path / "storage-alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        modules = alias / "Modules"
    elif location in {"source-module-parent", "source-revision-parent"}:
        original = modules / "topos" if location == "source-module-parent" else runtime.parent
        moved = tmp_path / "redirected-source"
        shutil.move(str(original), moved)
        original.symlink_to(moved, target_is_directory=True)
    else:
        external = tmp_path / "unrelated-output"
        external.mkdir()
        (tmp_path / "output-alias").symlink_to(external, target_is_directory=True)
        output = tmp_path / "output-alias" / "evidence"
    with pytest.raises(ValueError, match="redirect|symbolic"):
        retain_setup_evidence(spec, modules, output)
    assert not output.exists()


def test_interrupted_setup_keeps_actual_failed_process_audit_and_failed_batch(tmp_path):
    import os
    import subprocess
    import sys

    from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
    from scripts import run_module_installation as batch
    from scripts.manage_modules import DEFAULT_MANIFEST, _build_env, _paths, load_manifest

    manifest = DEFAULT_MANIFEST.with_name("module-distribution-legacy-kit-1.0.1.json")
    spec = load_manifest(manifest)["modules"]["topos"]
    modules = tmp_path / "Modules"
    _, location, _, _ = _paths("topos", spec, modules)
    runtime = location / "runtime"
    # This genuinely failed owned Python process produces transport audit bytes.
    # It is independent of the subsequent genuine kit rejection, and never
    # represents a package install, Stage 0 completion or chemistry calculation.
    program = """import json,os,pathlib,sys
runtime=pathlib.Path(sys.argv[1]); (runtime/'setup-logs').mkdir(parents=True)
(runtime/'setup-receipt.json').write_text(json.dumps({'status':'failed','process_pid':os.getpid(),
    'scope':'Owned transport control; no installation or scientific authority',
    'scientific_accuracy_established':False}))
(runtime/'setup-logs/stopped.log').write_text('Owned transport process PID=' + str(os.getpid()) + '\\n')
sys.exit(23)
"""
    with pytest.raises(subprocess.CalledProcessError) as stopped:
        safe_subprocess_run([sys.executable, "-I", "-c", program, str(runtime)],
                            cwd=tmp_path, env=_build_env(), timeout=15,
                            check=True, required_disk_gb=0.01)
    assert stopped.value.returncode == 23
    before = (runtime / "setup-receipt.json").read_bytes()
    audit = json.loads(before)
    assert audit["process_pid"] != os.getpid()
    assert audit["scientific_accuracy_established"] is False
    invalid_kit = tmp_path / "incomplete-reviewed-kit"
    invalid_kit.mkdir()
    report = batch.run_batch(action="install", modules=["topos"], manifest=manifest,
                             root=modules, output=tmp_path / "batch", ecosystem_kit=invalid_kit)
    assert report["success"] is False and report["modules"] == []
    assert report["completed"] is True
    assert report["scientific_accuracy_established"] is False
    assert report["failures"][0]["error_type"] == "ValueError"
    assert "SHA256SUMS" in report["failures"][0]["message"]
    assert (runtime / "setup-receipt.json").read_bytes() == before
    retained = batch.retain_setup_evidence(spec, modules, tmp_path / "retained")
    assert retained["status"] == "retained"
    assert (tmp_path / "retained/setup-receipt.json").read_bytes() == before
    assert retained["files"]["setup-receipt.json"]["sha256"] == hashlib.sha256(before).hexdigest()
    assert json.loads((tmp_path / "retained/setup-receipt.json").read_text())["status"] == "failed"
    assert {"mandatory-validation.json", "Registry/"} <= set(retained["missing_members"])
    assert not (modules / "topos/installation.json").exists()
