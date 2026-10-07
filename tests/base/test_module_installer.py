"""Real offline Git, PEP 517 builds, isolated installs and integrity failures.

The tiny wheel exercises packaging only; it is not a chemistry implementation.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import manage_modules as installer

BACKEND = '''
import base64, hashlib, os, pathlib, zipfile

def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    forbidden = ["COCHEM_SOURCE_READ_TOKEN", "BASE_SOURCE_READ_TOKEN", "ORCA_ASSET_READ_TOKEN", "GH_TOKEN", "GITHUB_TOKEN", "GIT_ASKPASS", "GIT_CONFIG_COUNT"]
    if any(key in os.environ for key in forbidden):
        raise RuntimeError("Source credentials reached package build code")
    name = "cochem_installer_fixture-1.2.3-py3-none-any.whl"
    files = {
        "cochem_installer_fixture.py": b"VALUE = 42\\n",
        "cochem_installer_fixture-1.2.3.dist-info/METADATA": b"Metadata-Version: 2.1\\nName: cochem-installer-fixture\\nVersion: 1.2.3\\n",
        "cochem_installer_fixture-1.2.3.dist-info/WHEEL": b"Wheel-Version: 1.0\\nGenerator: stdlib-test-backend\\nRoot-Is-Purelib: true\\nTag: py3-none-any\\n",
    }
    records = [f"{key},sha256={base64.urlsafe_b64encode(hashlib.sha256(value).digest()).rstrip(b'=').decode()},{len(value)}" for key, value in files.items()]
    record_name = "cochem_installer_fixture-1.2.3.dist-info/RECORD"
    files[record_name] = ("\\n".join(records + [record_name + ",,"]) + "\\n").encode()
    with zipfile.ZipFile(pathlib.Path(wheel_directory) / name, "w") as wheel:
        for key, value in files.items():
            wheel.writestr(key, value)
    return name
'''


def git(path, *args):
    result = subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True, env=installer._build_env())
    return result.stdout.strip()


def offline_environment(origin):
    env = installer._build_env()
    env.update({"GIT_CONFIG_GLOBAL": str(origin.parent / "offline-git.conf"),
                "PIP_NO_INDEX": "1", "PIP_CONFIG_FILE": os.devnull})
    return env


def fixture_command(command, module_id, spec, root, origin, *, extra_env=None):
    manifest = origin.parent / f"{module_id}-manifest.json"
    manifest.write_text(json.dumps({"schema_version": installer.MANIFEST_SCHEMA, "modules": {module_id: spec}}))
    env = offline_environment(origin)
    env.update(extra_env or {})
    return subprocess.run([sys.executable, str(Path(installer.__file__)), command,
                           "--modules", module_id, "--manifest", str(manifest),
                           "--root", str(root), "--json"], env=env, capture_output=True, text=True)


def install_fixture(module_id, spec, root, origin):
    result = fixture_command("install", module_id, spec, root, origin)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["modules"][0]


@pytest.fixture
def repository(tmp_path):
    origin = tmp_path / "origin"
    origin.mkdir()
    git(origin, "init")
    (origin / "pyproject.toml").write_text('[build-system]\nrequires = []\nbuild-backend = "backend"\nbackend-path = ["."]\n')
    (origin / "backend.py").write_text(BACKEND)
    git(origin, "add", ".")
    git(origin, "-c", "user.name=CoChem test", "-c", "user.email=test@example.invalid", "commit", "-m", "Actual minimal package for installer boundary tests")
    spec = {"repository": "ProfJJK-CoChem/CoChem-Installer-Fixture", "revision": git(origin, "rev-parse", "HEAD"),
            "distribution": "cochem-installer-fixture", "adapter": "fixture_geometry", "adapter_requirements": [], "operations": ["geometry_analysis"]}
    # Exercise Git's actual transport configuration, with canonical remote identity.
    config = tmp_path / "offline-git.conf"
    config.write_text(f'[url "{origin.as_uri()}"]\n\tinsteadOf = https://github.com/{spec["repository"]}.git\n')
    return origin, spec, tmp_path / "modules"


@pytest.fixture
def installed(repository):
    origin, spec, root = repository
    receipt = install_fixture("fixture", spec, root, origin)
    return origin, spec, root, receipt


def test_real_isolated_build_install_verify_and_reuse(repository):
    origin, spec, root = repository
    # Fetch offline first. Build hooks then receive an actual credential-bearing
    # parent process environment, and fail if the installer passes credentials on.
    result = fixture_command("fetch", "fixture", spec, root, origin)
    assert result.returncode == 0, result.stderr
    token = "fixture-secret-that-must-never-be-persisted"
    result = fixture_command("install", "fixture", spec, root, origin, extra_env={
        "COCHEM_SOURCE_READ_TOKEN": token, "GITHUB_TOKEN": "fixture-other-secret",
        "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.extraHeader",
        "GIT_CONFIG_VALUE_0": "Authorization: fixture-other-secret"})
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)["modules"][0]
    assert receipt["revision"] == spec["revision"]
    assert receipt["distribution_metadata"]["version"] == "1.2.3"
    assert receipt["pip_check"] == {"passed": True}
    assert receipt["status"] == "installed"
    assert receipt["source_tree_oid"] == git(Path(receipt["source_path"]), "rev-parse", "HEAD^{tree}")
    assert installer.verify_installation("fixture", spec, root) == receipt
    assert install_fixture("fixture", spec, root, origin) == receipt
    assert token not in json.dumps(receipt)
    source = Path(receipt["source_path"])
    config = (source / ".git/config").read_text()
    assert token not in config
    assert "fixture-other-secret" not in config
    assert f'https://github.com/{spec["repository"]}.git' in config
    result = subprocess.run([receipt["python_path"], "-I", "-B", "-c", "import cochem_installer_fixture; print(cochem_installer_fixture.VALUE)"], check=True, text=True, capture_output=True, env=installer._build_env())
    assert result.stdout.strip() == "42"
    assert "cochem_installer_fixture" not in sys.modules


@pytest.mark.parametrize("change", ["tracked", "untracked", "ignored"])
def test_dirty_source_is_rejected_without_overwrite(repository, change):
    origin, spec, root = repository
    result = fixture_command("fetch", "fixture", spec, root, origin)
    assert result.returncode == 0, result.stderr
    source = Path(json.loads(result.stdout)["modules"][0]["source_path"])
    if change == "tracked":
        (source / "backend.py").write_text("changed by user\n")
    elif change == "untracked":
        (source / "notes.txt").write_text("keep this work\n")
    else:
        (source / ".git/info/exclude").write_text("notes.txt\n")
        (source / "notes.txt").write_text("keep this ignored work\n")
    result = fixture_command("install", "fixture", spec, root, origin)
    assert result.returncode == 1
    assert "dirty" in result.stderr
    assert not (root / "fixture/installation.json").exists()
    if change != "tracked":
        expected = "keep this work\n" if change == "untracked" else "keep this ignored work\n"
        assert (source / "notes.txt").read_text() == expected


def test_installed_code_tampering_is_detected(installed):
    _origin, spec, root, receipt = installed
    python = receipt["python_path"]
    filename = subprocess.run([python, "-I", "-B", "-c", "import importlib.util; print(importlib.util.find_spec('cochem_installer_fixture').origin)"], check=True, capture_output=True, text=True).stdout.strip()
    Path(filename).write_text("VALUE = 0\n")
    with pytest.raises(installer.ModuleInstallationError, match="environment integrity"):
        installer.verify_installation("fixture", spec, root)


@pytest.mark.parametrize("injection", ["sitecustomize.py", "unrecorded.pth", "sitecustomize.pyc"])
def test_unrecorded_code_rejected_before_environment_python_executes(installed, injection):
    import py_compile

    origin, spec, root, receipt = installed
    environment = Path(receipt["python_path"]).parent.parent
    sites = list(environment.glob("lib/python*/site-packages")) or [environment / "Lib/site-packages"]
    injected = sites[0] / injection
    execution_marker = origin.parent / "untrusted-code-executed"
    payload = f"import pathlib; pathlib.Path({str(execution_marker)!r}).write_text('executed')\n"
    if injection.endswith(".pyc"):
        source = origin.parent / "injected.py"
        source.write_text(payload)
        py_compile.compile(str(source), cfile=str(injected), doraise=True)
    else:
        injected.write_text(payload)
    result = fixture_command("verify", "fixture", spec, root, origin)
    assert result.returncode == 1
    assert "no module code was executed" in result.stderr
    assert not execution_marker.exists()


@pytest.mark.parametrize("filename", ["source.json", "installation.json"])
@pytest.mark.parametrize("invalid", ["[]", "null", "not JSON"])
def test_invalid_receipt_rejected_as_actionable_installation_error(repository, filename, invalid):
    _origin, spec, root = repository
    (root / "fixture").mkdir(parents=True)
    (root / "fixture" / filename).write_text(invalid)
    with pytest.raises(installer.ModuleInstallationError, match="receipt"):
        installer.install_module("fixture", spec, root)


def test_changed_install_policy_cannot_reuse_receipt(installed):
    _origin, spec, root, _receipt = installed
    changed = dict(spec, adapter_requirements=["ase>=3.23"])
    with pytest.raises(installer.ModuleInstallationError, match="specification"):
        installer.verify_installation("fixture", changed, root)


def test_wrong_immutable_pin_cannot_publish_source_or_installation(repository):
    origin, spec, root = repository
    spec = dict(spec, revision="f" * 40)
    result = fixture_command("install", "fixture", spec, root, origin)
    assert result.returncode == 1
    assert "Fetch pinned" in result.stderr
    assert not (root / "fixture/source.json").exists()
    assert not (root / "fixture/installation.json").exists()


def test_failed_build_keeps_source_but_never_publishes_installation(repository):
    origin, spec, root = repository
    (origin / "backend.py").write_text('raise RuntimeError("Intentional broken build fixture")\n')
    git(origin, "add", ".")
    git(origin, "-c", "user.name=CoChem test", "-c", "user.email=test@example.invalid", "commit", "-m", "Broken backend boundary")
    spec = dict(spec, revision=git(origin, "rev-parse", "HEAD"))
    result = fixture_command("install", "fixture", spec, root, origin)
    assert result.returncode == 1
    assert "Build pinned module wheel" in result.stderr
    assert (root / "fixture/source.json").exists()
    assert not (root / "fixture/installation.json").exists()
    result = fixture_command("install", "fixture", spec, root, origin)
    assert result.returncode == 1
    assert "unreceipted environment" in result.stderr


def test_source_only_module_can_be_downloaded_but_not_claim_installed(repository):
    origin, spec, root = repository
    spec = dict(spec, distribution=None, adapter=None, operations=[])
    result = fixture_command("fetch", "fixture", spec, root, origin)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)["modules"][0]
    assert receipt["status"] == "downloaded"
    assert installer.fetch_module("fixture", spec, root) == receipt
    result = fixture_command("install", "fixture", spec, root, origin)
    assert result.returncode == 1
    assert "upstream Python packaging is unavailable" in result.stderr
    assert not (root / "fixture/installation.json").exists()
    assert not (root / "fixture" / spec["revision"] / "env").exists()


def test_reviewed_packaging_blocker_downloads_source_without_building_environment(repository):
    origin, spec, root = repository
    spec = dict(spec, install_blocker="Upstream packaging requires a reviewed correction.")
    result = fixture_command("fetch", "fixture", spec, root, origin)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["modules"][0]["status"] == "downloaded"
    result = fixture_command("install", "fixture", spec, root, origin)
    assert result.returncode == 1
    assert spec["install_blocker"] in result.stderr
    assert "no runnable installation was created" in result.stderr
    assert not (root / "fixture/installation.json").exists()
    assert not (root / "fixture" / spec["revision"] / "env").exists()


@pytest.mark.parametrize("key,value", [
    ("repository", "https://github.com/owner/repo"), ("repository", "owner/../repo"),
    ("revision", "main"), ("revision", "A" * 40),
    ("adapter_requirements", ["--index-url=https://example.invalid"]),
    ("adapter_requirements", ["package @ https://example.invalid/a.whl"]),
    ("adapter", "../adapter"), ("operations", ["../operation"]),
    ("install_blocker", ""), ("install_blocker", ["invalid explanation"]),
])
def test_manifest_rejects_mutable_pins_paths_and_arbitrary_installer_options(repository, key, value):
    _origin, spec, root = repository
    with pytest.raises(ValueError):
        installer.fetch_module("fixture", dict(spec, **{key: value}), root)
    assert not root.exists()


def test_module_id_and_root_traversal_are_rejected(repository, tmp_path):
    _origin, spec, root = repository
    with pytest.raises(ValueError, match="identifiers"):
        installer.fetch_module("../fixture", spec, root)
    with pytest.raises(ValueError, match="outside the BASE"):
        installer.fetch_module("fixture", spec, installer.REPOSITORY_ROOT / "build-modules")
    root.mkdir()
    (root / "fixture").symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic"):
        installer.fetch_module("fixture", spec, root)


def test_explicit_git_auth_is_temporary_and_build_credentials_removed():
    code = '''
from pathlib import Path
from scripts import manage_modules as installer
import json, os
with installer._git_auth() as (env, options):
    helper = Path(env["GIT_ASKPASS"])
    checks = [helper.exists(), "fixture-secret" not in helper.read_text(),
              env["COCHEM_SOURCE_READ_TOKEN"] == "fixture-secret",
              env["GIT_CONFIG_GLOBAL"] == os.devnull,
              "fixture-secret" not in repr(options), "credential.helper=" in options]
checks.append(not helper.exists())
checks.append(not ({"COCHEM_SOURCE_READ_TOKEN", "COURSE_PRIVATE_TOKEN", "COURSE_PASSWORD", "OTHER_API_KEY"} & installer._build_env().keys()))
print(json.dumps(checks))
'''
    env = installer._build_env()
    env.update({key: "fixture-secret" for key in ("COCHEM_SOURCE_READ_TOKEN", "COURSE_PRIVATE_TOKEN", "COURSE_PASSWORD", "OTHER_API_KEY")})
    result = subprocess.run([sys.executable, "-c", code], env=env, cwd=installer.REPOSITORY_ROOT, capture_output=True, text=True, check=True)
    assert all(json.loads(result.stdout))


def test_existing_credentials_preserved_for_git_without_explicit_token():
    code = '''
from scripts import manage_modules as installer
import json
with installer._git_auth() as (env, options):
    checks = [env["GIT_ASKPASS"] == "/configured/credential-helper", options == []]
checks.append("GIT_ASKPASS" not in installer._build_env())
print(json.dumps(checks))
'''
    env = installer._build_env()
    env["GIT_ASKPASS"] = "/configured/credential-helper"
    result = subprocess.run([sys.executable, "-c", code], env=env, cwd=installer.REPOSITORY_ROOT, capture_output=True, text=True, check=True)
    assert all(json.loads(result.stdout))


def test_cli_explicit_selection_and_list_do_not_install(repository, tmp_path, capsys):
    _origin, spec, root = repository
    path = tmp_path / "modules.json"
    path.write_text(json.dumps({"schema_version": installer.MANIFEST_SCHEMA, "modules": {"fixture": spec}}))
    assert installer.main(["list", "--manifest", str(path), "--root", str(root), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["modules"]["fixture"]["revision"] == spec["revision"]
    assert not root.exists()
    with pytest.raises(SystemExit):
        installer.main(["install", "--manifest", str(path), "--root", str(root)])
    assert installer.main(["verify", "--manifest", str(path), "--root", str(root), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"modules": []}


@pytest.mark.parametrize("action", ["fetch", "install"])
def test_batch_retains_success_after_failed_module_and_returns_failure(repository, tmp_path, action):
    origin, spec, root = repository
    manifest = tmp_path / "batch-manifest.json"
    bad = dict(spec, revision="f" * 40)
    entries = {"unavailable": bad}
    config = origin.parent / "offline-git.conf"
    for name in ("before", "after"):
        independent_origin = tmp_path / f"origin-{name}"
        git(origin, "clone", "--no-hardlinks", str(origin), str(independent_origin))
        repository_name = spec["repository"] + "-" + name
        with config.open("a") as stream:
            stream.write(f'[url "{independent_origin.as_uri()}"]\n\tinsteadOf = https://github.com/{repository_name}.git\n')
        entries[name] = dict(spec, repository=repository_name)
    manifest.write_text(json.dumps({"schema_version": installer.MANIFEST_SCHEMA,
                                    "modules": entries}))
    output = tmp_path / "batch-evidence"
    result = subprocess.run([sys.executable, "-m", "scripts.run_module_installation",
                             "--action", action, "--modules", "before", "unavailable", "after",
                             "--manifest", str(manifest), "--root", str(root), "--output", str(output)],
                            env=offline_environment(origin), cwd=installer.REPOSITORY_ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr
    report = json.loads((output / "installations.json").read_text())
    assert report["completed"] is True
    assert report["success"] is False
    assert report["scientific_accuracy_established"] is False
    assert report["selected_modules"] == ["before", "unavailable", "after"]
    assert [receipt["module_id"] for receipt in report["modules"]] == ["before", "after"]
    assert report["modules"][0]["status"] == ("downloaded" if action == "fetch" else "installed")
    assert report["failures"][0]["module_id"] == "unavailable"
    assert report["failures"][0]["revision"] == "f" * 40
    assert "Fetch pinned module source failed" in report["failures"][0]["message"]
    assert (output / "module-distribution.json").read_bytes() == manifest.read_bytes()
    assert '"module": "before"' in result.stdout
    assert '"module": "after"' in result.stdout
    assert "2 succeeded, 1 failed" in result.stdout
    assert (root / "before/source.json").exists()
    assert (root / "after/source.json").exists()
    assert not (root / "unavailable/source.json").exists()


def test_batch_successful_fetch_returns_success_and_reports_every_module(repository, tmp_path):
    origin, spec, root = repository
    manifest = tmp_path / "batch-manifest.json"
    manifest.write_text(json.dumps({"schema_version": installer.MANIFEST_SCHEMA,
                                    "modules": {"first": spec, "second": spec}}))
    output = tmp_path / "batch-evidence"
    output.mkdir()
    env = offline_environment(origin)
    env["MODULE_IDS"] = "first second first"
    result = subprocess.run([sys.executable, "-m", "scripts.run_module_installation", "--action", "fetch",
                             "--manifest", str(manifest), "--root", str(root), "--output", str(output)],
                            env=env, cwd=installer.REPOSITORY_ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((output / "installations.json").read_text())
    assert report["success"] is True
    assert report["completed"] is True
    assert report["failures"] == []
    assert [receipt["module_id"] for receipt in report["modules"]] == ["first", "second"]
    original_report = (output / "installations.json").read_bytes()
    repeated = subprocess.run([sys.executable, "-m", "scripts.run_module_installation", "--action", "fetch",
                               "--manifest", str(manifest), "--root", str(root), "--output", str(output)],
                              env=env, cwd=installer.REPOSITORY_ROOT, capture_output=True, text=True)
    assert repeated.returncode == 1
    assert "choose a fresh output directory" in repeated.stdout
    assert (output / "installations.json").read_bytes() == original_report


def test_batch_missing_required_token_preserves_manifest_and_configuration_report(repository, tmp_path):
    origin, spec, root = repository
    manifest = tmp_path / "batch-manifest.json"
    manifest.write_text(json.dumps({"schema_version": installer.MANIFEST_SCHEMA, "modules": {"fixture": spec}}))
    output = tmp_path / "batch-evidence"
    result = subprocess.run([sys.executable, "-m", "scripts.run_module_installation", "--action", "fetch",
                             "--modules", "fixture", "--manifest", str(manifest), "--root", str(root),
                             "--output", str(output), "--require-source-token"], env=offline_environment(origin),
                            cwd=installer.REPOSITORY_ROOT, capture_output=True, text=True)
    assert result.returncode == 1
    report = json.loads((output / "installations.json").read_text())
    assert report["success"] is False
    assert report["completed"] is False
    assert report["modules"] == []
    assert "Configure COCHEM_SOURCE_READ_TOKEN" in report["configuration_error"]
    assert (output / "module-distribution.json").read_bytes() == manifest.read_bytes()
    assert not root.exists()
