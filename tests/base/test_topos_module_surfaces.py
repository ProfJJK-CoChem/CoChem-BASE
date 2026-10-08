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
    from topos.base_provider import request_from_handoff

    from cochem_base.interfaces.artifact_handoff import prepare_module_handoff
    operation, options = handoff_options("topos", request_file)
    prepare_module_handoff("topos", xyz, tmp_path / "handoff", operation=operation, options=options)
    request, receipt = request_from_handoff(tmp_path / "handoff/handoff.json")
    assert request.molecule.isotopes == [18, 2, None]
    assert request.per_geometry_budget_seconds == 15
    assert receipt["producer_scientific_execution_performed"] is False


def test_provider_rejects_geometry_disagreement_before_any_native_job(request_file, xyz, tmp_path):
    from topos.base_provider import request_from_handoff

    from cochem_base.interfaces.artifact_handoff import prepare_module_handoff
    operation, options = handoff_options("topos", request_file)
    xyz.write_text(xyz.read_text().replace("H 1 0 0", "H 2 0 0"))
    prepare_module_handoff("topos", xyz, tmp_path / "handoff", operation=operation, options=options)
    with pytest.raises(ValueError, match="coordinates"):
        request_from_handoff(tmp_path / "handoff/handoff.json")
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


def test_missing_kit_rejected_before_dashboard_bootstrap(monkeypatch, tmp_path):
    from scripts.hosted_dashboard import setup_dashboard
    monkeypatch.setenv("COCHEM_MODULES", "topos")
    monkeypatch.delenv("COCHEM_ECOSYSTEM_KIT", raising=False)
    def forbidden(*args, **kwargs):
        pytest.fail("No installation process is allowed before the kit is selected")
    monkeypatch.setattr("scripts.hosted_dashboard.subprocess.run", forbidden)
    with pytest.raises(ValueError, match="COCHEM_ECOSYSTEM_KIT"):
        setup_dashboard(tmp_path / "venv/bin/python", tmp_path / "runtime", 1)


def test_dashboard_installer_uses_noneditable_base_and_explicit_kit(monkeypatch, tmp_path):
    from scripts import hosted_dashboard as dashboard
    kit = tmp_path / "kit"
    kit.mkdir()
    monkeypatch.setenv("COCHEM_MODULES", "topos")
    monkeypatch.setenv("COCHEM_ECOSYSTEM_KIT", str(kit))
    commands = []
    class ReachedInstallBoundary(Exception):
        pass
    def no_process(command, **kwargs):
        commands.append(command)
        if "scripts.manage_modules" in command:
            raise ReachedInstallBoundary
    monkeypatch.setattr(dashboard.subprocess, "run", no_process)
    with pytest.raises(ReachedInstallBoundary):
        dashboard.setup_dashboard(tmp_path / "venv/bin/python", tmp_path / "runtime", 1)
    install = next(command for command in commands if "--no-build-isolation" in command)
    assert "-e" not in install and "--no-build-isolation" in install
    assert commands[-1][1:5] == ["-I", "-B", "-m", "scripts.manage_modules"]
    assert commands[-1][-2:] == ["--ecosystem-kit", str(kit)]


@pytest.fixture
def gui(monkeypatch, tmp_path):
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("COCHEM_CONFIG", str(tmp_path / "absent-registry.json"))
    from ui.voila_layout.cochem_gui import CoChemGUI
    monkeypatch.setattr(CoChemGUI, "_refresh_module_capabilities", lambda self, *args: None)
    instance = CoChemGUI()
    yield instance
    instance._module_cancellation.set()
    if hasattr(instance, "_module_worker"):
        instance._module_worker.join(timeout=5)
    instance._cleanup_topos_search()


def test_gui_prepares_real_complete_handoff_without_execution(gui, request_file, xyz, tmp_path):
    from cochem_base.interfaces.artifact_handoff import load_module_handoff
    gui.module_request_file.value = str(request_file)
    gui.module_artifact.value = str(xyz)
    gui.module_output.value = str(tmp_path / "packages")
    gui._prepare_module_handoff()
    handoff = load_module_handoff(gui._last_module_handoff_path)
    assert handoff.operation == "energy"
    assert handoff.options == {"topos_request": json.loads(request_file.read_text())}
    assert handoff.scientific_execution_performed is False
    assert gui.module_operation.disabled
    gui.module_recipient.value = "torq"
    assert not gui.module_operation.disabled and gui.module_request_file.disabled
    assert gui.module_operation.value == "geometry_analysis"


def test_gui_cancellation_reaches_execution_boundary_without_fake_success(gui, monkeypatch, request_file, xyz, tmp_path):
    reached = threading.Event()
    observed = {}
    def wait_for_cancel(manifest, output, **kwargs):
        observed.update(kwargs)
        reached.set()
        if not kwargs["cancellation_event"].wait(3):
            raise RuntimeError("Cancellation was not forwarded")
        raise InterruptedError("Transport boundary cancelled; no native process was launched")
    monkeypatch.setattr("cochem_base.interfaces.module_execution.execute_module_handoff", wait_for_cancel)
    gui.module_request_file.value = str(request_file)
    gui.module_artifact.value = str(xyz)
    gui.module_output.value = str(tmp_path / "packages")
    gui.module_timeout.value = 45
    gui._run_module_geometry()
    assert reached.wait(3)
    assert gui.btn_module_install.disabled and gui.btn_module_run.disabled
    gui._cancel_module_operation()
    gui._module_worker.join(timeout=5)
    assert observed["timeout"] == 45
    assert "cancelled" in gui.module_handoff_status.value
    assert gui.btn_module_cancel.disabled and not gui.btn_module_run.disabled
    assert not list(tmp_path.rglob("result.json"))


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
def test_api_selection_rejects_untrusted_artifact_identity(monkeypatch, change):
    # GitHub metadata transport fixtures, never scientific or native evidence.
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
    monkeypatch.setattr(transport, "_json_api", lambda repository, path: {"artifacts": values} if "/artifacts?" in path else run)
    with pytest.raises(ValueError):
        transport.identify("owner/repo", "123", "reviewed-kit")


@pytest.mark.parametrize("case", ["valid", "public", "branch", "event", "no-kit", "legacy-topos", "foreign-profile"])
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
    values = {"MODULE_IDS": "topos", "MODULE_ACTION": "topos_request", "ENGINE_PROFILE": "free",
              "REPOSITORY_PRIVATE": "true", "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF_NAME": "main",
              "DEFAULT_BRANCH": "main", "TOPOS_REQUEST": request_file.name, "RECEIVER_TIMEOUT": "180",
              "KIT_RUN_ID": "123", "KIT_ARTIFACT_NAME": "kit", "KIT_SUBDIRECTORY": ".",
              "MODULE_XYZ": xyz.name, "GITHUB_ENV": str(tmp_path / "github-env")}
    if case == "public":
        values["REPOSITORY_PRIVATE"] = "false"
    if case == "branch":
        values["GITHUB_REF_NAME"] = "unreviewed"
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
    if case == "valid":
        assert completed.returncode == 0, completed.stderr
        assert Path(values["GITHUB_ENV"]).read_text() == "TOPOS_SELECTED=true\n"
    else:
        assert completed.returncode != 0
        expected = {"public": "private", "branch": "default-branch dispatch",
                    "event": "default-branch dispatch", "no-kit": "run ID and name",
                    "legacy-topos": "typed request", "foreign-profile": "Unsupported engine profile"}
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
def test_batch_topos_prerequisites_reject_before_install(monkeypatch, tmp_path, action):
    from scripts import run_module_installation as batch
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid TOPOS selection must not invoke an installer")
    monkeypatch.setattr(batch, "install_module", forbidden)
    with pytest.raises(ValueError):
        batch.run_batch(action=action, modules=["topos"], manifest=batch.DEFAULT_MANIFEST,
                        root=tmp_path / "modules", output=tmp_path / "evidence")
    assert not (tmp_path / "evidence").exists()


def test_gui_partial_result_is_never_rendered_as_completed_science(gui, monkeypatch, request_file, xyz, tmp_path):
    # A non-numerical lifecycle fixture; no simulated engine output or success.
    def interrupted_receiver(*args, **kwargs):
        return {"status": "partial", "validation_status": "human-review", "published": False,
                "scope": "Transport UI fixture: interrupted before any numerical result"}
    monkeypatch.setattr("cochem_base.interfaces.module_execution.execute_module_handoff", interrupted_receiver)
    gui.module_request_file.value = str(request_file)
    gui.module_artifact.value = str(xyz)
    gui.module_output.value = str(tmp_path / "packages")
    gui._run_module_geometry()
    gui._module_worker.join(timeout=5)
    assert "partial" in gui.module_handoff_status.value and "human-review" in gui.module_handoff_status.value
    assert "completed" not in gui.module_handoff_status.value
    assert gui._last_module_result["published"] is False


@pytest.mark.parametrize("failure", ["timeout", "process"])
def test_batch_subprocess_failures_preserve_structured_results_and_continue(monkeypatch, tmp_path, request_file, xyz, capsys, failure):
    import subprocess

    from cochem_base.interfaces.artifact_handoff import load_module_handoff
    from scripts.run_module_job import main

    reached = []
    def failed_transport(handoff_path, output, **kwargs):
        handoff = load_module_handoff(handoff_path)
        reached.append(handoff.module_id)
        # These are real subprocess exception types at the unexecuted transport
        # boundary, not native output fixtures or successful scientific results.
        if failure == "timeout":
            raise subprocess.TimeoutExpired(["unstarted-receiver"], kwargs["timeout"])
        raise subprocess.CalledProcessError(23, ["unstarted-receiver"])
    monkeypatch.setattr("cochem_base.interfaces.module_execution.execute_module_handoff", failed_transport)
    result = main(["--modules", "topos", "torq", "--xyz-file", str(xyz), "--output", str(tmp_path / "batch"),
                   "--topos-request", str(request_file), "--timeout", "45"])
    assert result == 1 and reached == ["topos", "torq"]
    reports = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [item["module_id"] for item in reports] == reached
    assert all(item["status"] == "failed" for item in reports)
    assert all(("timed out" if failure == "timeout" else "23") in item["error"] for item in reports)
    assert not list(tmp_path.rglob("engine.stdout"))


def test_reviewed_controller_builder_is_shared_by_dashboard_and_hosted(tmp_path):
    import ast
    import os
    import subprocess
    import venv
    from pathlib import Path

    import yaml

    from scripts.hosted_dashboard import CONTROLLER_BUILD_TOOLS

    # Execute the authored command in a real interpreter without pip. It must
    # fail at that prerequisite before any package installation or network call.
    root = Path(__file__).resolve().parents[2]
    document = yaml.safe_load((root / ".github/workflows/ecosystem_modules.yml").read_text())
    command = next(step["run"] for step in document["jobs"]["modules"]["steps"]
                   if step.get("name") == "Install trusted BASE as a noneditable controller")
    assert "python -m pip install --no-build-isolation ." in command
    snippet = command.split("python - <<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    authored = ast.parse(snippet)
    invocation = next(node for node in ast.walk(authored) if isinstance(node, ast.Call)
                      and ast.unparse(node.func) == "subprocess.run")
    assert [ast.unparse(item) for item in invocation.args[0].elts[:4]] == ["sys.executable", "'-m'", "'pip'", "'install'"]
    assert ast.unparse(invocation.args[0].elts[4]) == "*(f'{name}=={version}' for name, version in CONTROLLER_BUILD_TOOLS.items())"
    environment = tmp_path / "without-pip"
    venv.EnvBuilder(with_pip=False).create(environment)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    child = tmp_path / "authored-controller.py"
    child.write_text("import sys\nsys.path.insert(0, " + repr(str(root)) + ")\n" + snippet)
    completed = subprocess.run([str(python), "-I", str(child)], cwd=tmp_path,
                               capture_output=True, text=True, timeout=30)
    assert completed.returncode != 0
    assert "No module named pip" in completed.stderr
    assert not list(environment.rglob("pip"))
    assert CONTROLLER_BUILD_TOOLS == {"setuptools": "80.9.0", "wheel": "0.45.1", "build": "1.3.0", "packaging": "25.0"}
    # The dashboard uses those same pins and does not reenable isolated builds.
    tree = ast.parse((root / "scripts/hosted_dashboard.py").read_text())
    setup = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "setup_dashboard")
    assert any(isinstance(node, ast.Constant) and node.value == "--no-build-isolation" for node in ast.walk(setup))


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


def test_interrupted_setup_keeps_actual_failed_process_audit_and_failed_batch(monkeypatch, tmp_path):
    import subprocess
    import sys

    from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
    from scripts import run_module_installation as batch
    from scripts.manage_modules import _build_env, _paths, load_manifest

    spec = load_manifest()["modules"]["topos"]
    modules = tmp_path / "Modules"
    _, location, _, _ = _paths("topos", spec, modules)
    runtime = location / "runtime"
    # A real Python process exercises failed installation transport, explicitly
    # labelled as a control fixture; it does not install packages or run an engine.
    program = """import json,pathlib,sys
runtime=pathlib.Path(sys.argv[1]); (runtime/'setup-logs').mkdir(parents=True)
(runtime/'setup-receipt.json').write_text(json.dumps({'status':'failed','fixture':'interrupted setup transport; no installation'}))
(runtime/'setup-logs/stopped.log').write_text('Real transport fixture process stops before authority publication.\\n')
sys.exit(23)
"""
    def failed_install(*args, **kwargs):
        return safe_subprocess_run([sys.executable, "-I", "-c", program, str(runtime)],
                                   cwd=tmp_path, env=_build_env(), timeout=15,
                                   check=True, required_disk_gb=0.01)
    monkeypatch.setattr(batch, "install_module", failed_install)
    report = batch.run_batch(action="install", modules=["topos"], manifest=batch.DEFAULT_MANIFEST,
                             root=modules, output=tmp_path / "batch", ecosystem_kit=tmp_path / "unused-transport-fixture-kit")
    assert report["success"] is False and report["modules"] == []
    assert report["failures"][0]["error_type"] == subprocess.CalledProcessError.__name__
    retained = batch.retain_setup_evidence(spec, modules, tmp_path / "retained")
    assert retained["status"] == "retained"
    assert json.loads((tmp_path / "retained/setup-receipt.json").read_text())["status"] == "failed"
    assert {"mandatory-validation.json", "Registry/"} <= set(retained["missing_members"])
    assert not (modules / "topos/installation.json").exists()
