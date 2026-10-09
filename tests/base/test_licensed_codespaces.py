"""Real transport, process and filesystem controls for optional engine setup.

The loopback service and its executable client implement a deliberately limited
GitHub HTTP protocol. They supply repository metadata and invalid archive bytes,
never chemistry output or a successful licensed installation. Native installation,
MPI compilation, Stage 0 acceptance and calculations have separate real-engine
acceptance suites.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from cochem_base.core_engine.engine_environment import engine_runtime_environment
from ci_tools.base_ci import (
    _copy_reviewed_source,
    _profile_environment,
    _source_origin_receipts,
    tracked_source_snapshot,
    verify_source_binding,
)
from scripts import setup_licensed_engines as setup

PROTOCOL_CLIENT = '''import json, os, sys, urllib.error, urllib.request
from pathlib import Path

def request(path):
    url = path if path.startswith("http://") else os.environ["COCHEM_TEST_PROTOCOL_URL"] + "/" + path
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        sys.stderr.write(error.read().decode("utf-8", errors="replace"))
        raise SystemExit(1) from error

arguments = sys.argv[1:]
if len(arguments) == 2 and arguments[0] == "api":
    sys.stdout.buffer.write(request(arguments[1]))
elif len(arguments) == 9 and arguments[:2] == ["release", "download"]:
    tag = arguments[2]
    repository = arguments[arguments.index("--repo") + 1]
    name = arguments[arguments.index("--pattern") + 1]
    destination = Path(arguments[arguments.index("--dir") + 1])
    release = json.loads(request("repos/" + repository + "/releases/tags/" + tag))
    assets = [asset for asset in release["assets"] if asset["name"] == name]
    if len(assets) != 1 or Path(name).name != name:
        raise SystemExit("The protocol client requires one exact safe asset name.")
    destination.joinpath(name).write_bytes(request(assets[0]["browser_download_url"]))
else:
    raise SystemExit("Unsupported protocol-client command.")
'''


class ProtocolHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.requests.append(self.path)
        status, body = self.server.routes.get(self.path, (404, b"Unknown protocol route"))
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *arguments):
        self.server.messages.append(format % arguments)


class ProtocolServer(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), ProtocolHandler)
        self.routes = {}
        self.requests = []
        self.messages = []


class GitHubProtocol:
    def __init__(self, directory: Path, project: Path, binding: dict):
        self.server = ProtocolServer()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.directory = directory
        self.directory.mkdir()
        self.project = project
        self.binding = binding
        self.source_before = tracked_source_snapshot(project)
        self.evidence = directory.parent / "nested-source-origin-observations"
        self.evidence.mkdir(mode=0o700)
        environment = self.child_environment()
        subprocess.run(["git", "remote", "set-url", "origin", "https://github.com/student/project.git"],
                       cwd=self.project, env=environment, stdin=subprocess.DEVNULL,
                       check=True, timeout=15)
        client = self.directory / "protocol_client.py"
        client.write_text(PROTOCOL_CLIENT, encoding="utf-8")
        if os.name == "nt":
            (self.directory / "gh.cmd").write_text(
                f'@"{sys.executable}" -B "{client}" %*\r\n', encoding="utf-8"
            )
        else:
            executable = self.directory / "gh"
            executable.write_text(f"#!{sys.executable}\n" + PROTOCOL_CLIENT, encoding="utf-8")
            executable.chmod(0o700)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        assert not self.thread.is_alive()
        self.verify_observations()

    def verify_observations(self):
        assert tracked_source_snapshot(self.project) == self.source_before
        verified = verify_source_binding(self.project, expected_revision=self.binding["revision"])
        assert verified["tracked_source_sha256"] == self.binding["tracked_source_sha256"]
        observed = _source_origin_receipts(
            self.evidence, self.project, setup.REPO_ROOT, self.binding["revision"])
        assert not observed["authority_errors"], observed
        assert not observed["failed"] and not observed["startup_only"], observed
        assert observed["records"] and any(record["stage"] == "final" for record in observed["records"])
        (self.directory.parent / "nested-source-origin-verification.json").write_text(
            json.dumps(observed, indent=2) + "\n", encoding="utf-8")
        return observed

    def route(self, path: str, value, *, status: int = 200):
        body = value if isinstance(value, bytes) else json.dumps(value).encode("utf-8")
        self.server.routes[path] = (status, body)

    def repository(self, name: str, *, private: bool = True):
        self.route(f"/repos/{name}", {"full_name": name, "private": private})

    def invalid_release(self, engine: str):
        provider = setup.provision_orca if engine == "orca" else setup.provision_cfour
        manifest = provider.load_distribution_manifest()
        self.repository(manifest["repository"])
        self.route(
            f'/repos/{manifest["repository"]}/releases/tags/{manifest["release_tag"]}',
            {"assets": [{"name": manifest["archive_name"],
                         "browser_download_url": self.url + f"/assets/{engine}"}]},
        )
        self.route(f"/assets/{engine}", b"Invalid archive bytes for authentic checksum rejection\n")
        return manifest

    def child_environment(self):
        # The isolated project's own Git configuration supplies its origin. No
        # original repository, parent environment or callable is modified.
        environment = _profile_environment(setup.REPO_ROOT, self.project)
        environment = {key: value for key, value in environment.items()
                       if not key.startswith("GIT_CONFIG_")
                       and key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_NAMESPACE"}}
        environment.update({
            "PATH": str(self.directory) + os.pathsep + environment.get("PATH", ""),
            "COCHEM_TEST_PROTOCOL_URL": self.url,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "PYTHONDONTWRITEBYTECODE": "1",
            "COCHEM_SOURCE_QUARANTINE_ROOT": str(self.project),
            "COCHEM_SOURCE_QUARANTINE_ORIGINAL": str(setup.REPO_ROOT),
            "COCHEM_SOURCE_QUARANTINE_EVIDENCE": str(self.evidence),
            "COCHEM_SOURCE_QUARANTINE_REVISION": self.binding["revision"],
        })
        return environment

    def run(self, source: str, *arguments: str, origin: str = "https://github.com/student/project.git"):
        environment = self.child_environment()
        subprocess.run(["git", "remote", "set-url", "origin", origin], cwd=self.project,
                       env=environment, stdin=subprocess.DEVNULL, check=True, timeout=15)
        process = subprocess.run(
            [sys.executable, "-B", "-c", source, *arguments],
            cwd=self.project, env=environment,
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            check=False, timeout=45,
        )
        self.verify_observations()
        return process


@pytest.fixture(scope="module")
def reviewed_private_project(tmp_path_factory):
    # One complete immutable Git source fixture admits its genuine production
    # modules through the canonical boundary. No production root is overridden.
    binding = verify_source_binding(setup.REPO_ROOT)
    before = tracked_source_snapshot(setup.REPO_ROOT)
    project = tmp_path_factory.mktemp("reviewed-private-project") / "source"
    _copy_reviewed_source(setup.REPO_ROOT, project, binding)
    assert tracked_source_snapshot(project) == before
    verify_source_binding(project, expected_revision=binding["revision"])
    try:
        yield project, binding
    finally:
        assert tracked_source_snapshot(setup.REPO_ROOT) == before
        assert tracked_source_snapshot(project) == before
        verify_source_binding(project, expected_revision=binding["revision"])


@pytest.fixture
def github_protocol(tmp_path, reviewed_private_project):
    protocol = GitHubProtocol(tmp_path / "protocol-client", *reviewed_private_project)
    try:
        yield protocol
    finally:
        protocol.close()


def test_real_stdin_entry_point_has_no_filesystem_pseudo_origin(github_protocol):
    source = '''import json, os, sys
from scripts import setup_licensed_engines as setup
assert __name__ == "__main__" and __file__ == "<stdin>"
assert sys.argv == ["-"] and __spec__ is None
assert setup.REPO_ROOT == __import__("pathlib").Path.cwd()
print(json.dumps({"pid": os.getpid()}))
'''
    process = subprocess.run(
        [sys.executable, "-B", "-"], input=source, cwd=github_protocol.project,
        env=github_protocol.child_environment(), capture_output=True, text=True,
        check=False, timeout=45)
    assert process.returncode == 0, process.stderr
    pid = json.loads(process.stdout)["pid"]
    observations = github_protocol.verify_observations()
    final = [record for record in observations["records"]
             if record["stage"] == "final" and record["pid"] == pid]
    assert len(final) == 1 and final[0]["passed"]
    assert "__main__" not in final[0]["origins"]
    assert final[0]["origins"]["scripts.setup_licensed_engines"] == [
        str(github_protocol.project / "scripts/setup_licensed_engines.py")]


@pytest.mark.parametrize("remote", [
    "https://github.com/student/project.git", "git@github.com:student/project.git",
    "ssh://git@github.com/student/project.git", "https://user:credential@github.com/student/project.git",
])
def test_project_origin_resolves_without_returning_url_credentials(remote):
    assert setup.github_repository(remote) == "student/project"


@pytest.mark.parametrize("remote", [
    "https://elsewhere.example/student/project.git", "../project",
    "https://github.com/student/project/other.git",
])
def test_non_github_or_ambiguous_origin_is_rejected(remote):
    with pytest.raises(ValueError):
        setup.github_repository(remote)


@pytest.mark.parametrize("metadata", [
    {"full_name": "student/project", "private": False},
    {"full_name": "someone/else", "private": True}, {},
])
def test_project_visibility_and_identity_are_both_required(github_protocol, metadata):
    github_protocol.route("/repos/student/project", metadata)
    process = github_protocol.run('''from scripts import setup_licensed_engines as setup
try:
    setup.require_private_repository("student/project")
except ValueError as error:
    assert "private" in str(error)
else:
    raise AssertionError("Unauthorized metadata was accepted")
''')
    assert process.returncode == 0, process.stderr
    assert github_protocol.server.requests == ["/repos/student/project"]


def test_actual_git_origin_and_private_repository_transport(github_protocol):
    github_protocol.repository("student/project")
    process = github_protocol.run('''from scripts import setup_licensed_engines as setup
assert setup.require_private_project() == "student/project"
''')
    assert process.returncode == 0, process.stderr
    assert github_protocol.server.requests == ["/repos/student/project"]


def test_public_project_is_rejected_before_any_asset_access(github_protocol, tmp_path):
    github_protocol.repository("student/project", private=False)
    process = github_protocol.run('''import sys
from pathlib import Path
from scripts import setup_licensed_engines as setup
try:
    setup.provision_selected(["orca", "cfour"], Path(sys.argv[1]), 2)
except ValueError as error:
    print(str(error))
else:
    raise AssertionError("Public project unexpectedly admitted")
''', str(tmp_path))
    assert process.returncode == 0, process.stderr
    if platform.system() == "Linux" and platform.machine() == "x86_64":
        assert "private" in process.stdout
        assert github_protocol.server.requests == ["/repos/student/project"]
    else:
        assert "Linux x86_64" in process.stdout
        assert github_protocol.server.requests == []
    assert not (tmp_path / "licensed-engines").exists()


def test_github_denial_does_not_echo_untrusted_cli_output(github_protocol):
    canary = "credential-isolation-canary-not-a-real-secret"
    github_protocol.route("/repos/student/project", canary.encode(), status=403)
    process = github_protocol.run('''from scripts import setup_licensed_engines as setup
try:
    setup.github_call(["api", "repos/student/project"])
except ValueError as error:
    print(str(error))
else:
    raise AssertionError("Denied request unexpectedly succeeded")
''')
    assert process.returncode == 0, process.stderr
    assert "permissions" in process.stdout
    assert canary not in process.stdout + process.stderr
    assert github_protocol.server.requests == ["/repos/student/project"]


def test_installer_process_uses_explicit_non_secret_inputs(tmp_path):
    canary = "credential-isolation-canary-not-a-real-secret"
    names = ("GH_TOKEN", "GITHUB_TOKEN", "LAB_ARCHIVE_TOKEN", "AWS_ACCESS_KEY_ID",
             "SECRET_VAR", "HTTPS_PROXY", "CUSTOM_CREDENTIAL")
    inherited = {**os.environ, **dict.fromkeys(names, canary), "LANG": "en_US.UTF-8"}
    inherited.pop("LD_PRELOAD", None)
    child = tmp_path / "inspect_installer_environment.py"
    receipt = tmp_path / "installer-environment.json"
    child.write_text('''import json, os, sys
from pathlib import Path
assert not any(value == sys.argv[2] for value in os.environ.values())
assert os.environ["LANG"] == os.environ["LC_ALL"] == "C"
assert os.environ["PATH"]
Path(sys.argv[1]).write_text(json.dumps({"pid": os.getpid(), "argv": sys.argv[3:]}))
''', encoding="utf-8")
    process = subprocess.run(
        [sys.executable, "-B", "-c", '''import os, sys
from scripts import setup_licensed_engines as setup
before = dict(os.environ)
setup.checked_installer([sys.argv[1], sys.argv[2], sys.argv[3], "observed-real-child"])
assert dict(os.environ) == before
''', str(child), str(receipt), canary], cwd=setup.REPO_ROOT, env=inherited,
        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False, timeout=30,
    )
    assert process.returncode == 0, process.stderr
    report = json.loads(receipt.read_text())
    assert report["pid"] != os.getpid()
    assert report["argv"] == ["observed-real-child"]


@pytest.mark.parametrize("engine", ["orca", "cfour", "xtb", "crest", "qe"])
def test_real_child_does_not_receive_github_or_other_authentication(engine):
    confidential = {key: "credential-isolation-canary-not-a-real-secret" for key in (
        "GH_TOKEN", "GITHUB_TOKEN", "LAB_ARCHIVE_TOKEN", "AWS_ACCESS_KEY_ID", "OPENAI_API_KEY",
        "ACTIONS_RUNTIME_TOKEN", "MY_PASSWORD", "SSH_AUTH_SOCK", "GIT_ASKPASS", "HTTPS_PROXY",
        "GIT_CONFIG_VALUE_0", "GH_CONFIG_DIR",
    )}
    inherited = {**os.environ, **confidential, "OMP_NUM_THREADS": "2", "GITHUB_ACTIONS": "true"}
    before = dict(inherited)
    child_environment = engine_runtime_environment(engine, inherited, executable=sys.executable)
    probe = ("import os,sys; assert all(name not in os.environ for name in sys.argv[1:]); "
             "assert os.environ['GITHUB_ACTIONS']=='true'")
    subprocess.run([sys.executable, "-B", "-c", probe, *confidential], env=child_environment,
                   stdin=subprocess.DEVNULL, check=True, timeout=15)
    assert inherited == before


def environment_payload(root):
    executable = root / "licensed-engines" / "orca" / "distribution" / "orca"
    return {"schema_version": 1, "providers": {}, "values": {"COCHEM_ORCA_BIN": str(executable)},
            "path_entries": [str(executable.parent)]}


def test_persistent_bindings_are_loaded_by_later_dashboard_process(tmp_path):
    payload = environment_payload(tmp_path)
    setup.save_environment(tmp_path, payload)
    process = subprocess.run(
        [sys.executable, "-B", "-c", '''import json, sys
from pathlib import Path
from scripts.hosted_dashboard import runtime_environment
environment = runtime_environment(Path(sys.argv[1]))
print(json.dumps({key: environment[key] for key in ("COCHEM_ORCA_BIN", "PATH")}))
''', str(tmp_path)], cwd=setup.REPO_ROOT, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, check=False, timeout=30,
    )
    assert process.returncode == 0, process.stderr
    environment = json.loads(process.stdout)
    assert environment["COCHEM_ORCA_BIN"] == payload["values"]["COCHEM_ORCA_BIN"]
    assert environment["PATH"].split(os.pathsep)[0] == payload["path_entries"][0]
    if os.name != "nt":
        shell_file = tmp_path / "licensed-engines/codespaces-environment.sh"
        assert shell_file.stat().st_mode & 0o077 == 0


def test_terminal_helper_quotes_paths_without_executing_shell_substitutions(tmp_path):
    root = tmp_path / "a space $(touch injected) `touch injected`"
    setup.save_environment(root, environment_payload(root))
    helper = root / "licensed-engines/codespaces-environment.sh"
    process = subprocess.run(["bash", "-c", 'source "$1"; test "$COCHEM_ORCA_BIN" = "$2"',
                              "test", str(helper), environment_payload(root)["values"]["COCHEM_ORCA_BIN"]],
                             cwd=tmp_path, stdin=subprocess.DEVNULL, check=False, timeout=10)
    assert process.returncode == 0
    assert not (tmp_path / "injected").exists()


@pytest.mark.parametrize("mutation", ["secret", "checkout", "newline", "mpi_path", "invalid_boolean"])
def test_persisted_environment_rejects_secret_variables_and_unsafe_paths(tmp_path, mutation):
    payload = environment_payload(tmp_path)
    if mutation == "secret":
        payload["values"]["LAB_ARCHIVE_TOKEN"] = "confidential"
    elif mutation == "checkout":
        payload["values"]["COCHEM_ORCA_BIN"] = str(setup.REPO_ROOT / "invalid-program")
    elif mutation == "newline":
        payload["values"]["COCHEM_ORCA_BIN"] += "\nexport GH_TOKEN=bad"
    elif mutation == "mpi_path":
        payload["path_entries"] = [str(tmp_path / "licensed-engines/openmpi/bin")]
    else:
        payload["values"]["COCHEM_CFOUR_AVAILABLE"] = "false"
    with pytest.raises(ValueError):
        setup.save_environment(tmp_path, payload)


def test_symlinked_licensed_artifacts_cannot_escape_external_root(tmp_path):
    root = tmp_path / "artifacts"
    root.mkdir()
    (root / "licensed-engines").symlink_to(setup.REPO_ROOT, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        setup.load_environment(root)


def test_inventory_reuse_rejects_changed_and_additional_bytes(tmp_path):
    file = tmp_path / "program"
    file.write_text("Non-executable bytes for inventory verification")
    records = {"program": {"bytes": file.stat().st_size,
                           "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}}
    setup.verify_file_inventory(tmp_path, records, "receipt.json")
    file.write_text("Changed non-executable bytes")
    with pytest.raises(ValueError, match="bytes changed"):
        setup.verify_file_inventory(tmp_path, records, "receipt.json")
    (tmp_path / "extra").write_text("Unexpected unrecorded bytes")
    with pytest.raises(ValueError, match="inventory changed"):
        setup.verify_file_inventory(tmp_path, records, "receipt.json")


@pytest.mark.parametrize("engine", ["orca", "cfour"])
def test_unrecorded_installation_refuses_overwrite_before_download(github_protocol, tmp_path, engine):
    github_protocol.repository("student/project")
    provider = setup.provision_orca if engine == "orca" else setup.provision_cfour
    manifest = provider.load_distribution_manifest()
    github_protocol.repository(manifest["repository"])
    prefix = tmp_path / "licensed-engines" / engine
    prefix.mkdir(parents=True)
    marker = prefix / "student-owned-data.txt"
    marker.write_text("Preserve existing project artifact bytes")
    before = marker.read_bytes()
    process = github_protocol.run('''import sys
from pathlib import Path
from scripts import setup_licensed_engines as setup
try:
    setup.provision_selected([sys.argv[2]], Path(sys.argv[1]), 2)
except ValueError as error:
    print(str(error))
else:
    raise AssertionError("Unrecorded installation was replaced")
''', str(tmp_path), engine)
    assert process.returncode == 0, process.stderr
    if platform.system() == "Linux" and platform.machine() == "x86_64":
        assert "unrecorded" in process.stdout
        assert github_protocol.server.requests == ["/repos/student/project", f'/repos/{manifest["repository"]}']
    else:
        assert "Linux x86_64" in process.stdout
        assert github_protocol.server.requests == []
    assert marker.read_bytes() == before
    assert not list((tmp_path / "licensed-engines").glob(".private-download-*"))


@pytest.mark.parametrize("engine", ["orca", "cfour"])
def test_archive_checksum_failure_precedes_build_or_native_provision(github_protocol, tmp_path, engine):
    github_protocol.repository("student/project")
    manifest = github_protocol.invalid_release(engine)
    process = github_protocol.run('''import sys
from pathlib import Path
from scripts import setup_licensed_engines as setup
try:
    setup.provision_selected([sys.argv[2]], Path(sys.argv[1]), 2)
except ValueError as error:
    print(str(error))
else:
    raise AssertionError("Invalid archive became an installed provider")
''', str(tmp_path), engine)
    assert process.returncode == 0, process.stderr
    if platform.system() == "Linux" and platform.machine() == "x86_64":
        assert "SHA-256 mismatch" in process.stdout
        assert github_protocol.server.requests == [
            "/repos/student/project", f'/repos/{manifest["repository"]}',
            f'/repos/{manifest["repository"]}/releases/tags/{manifest["release_tag"]}',
            f"/assets/{engine}",
        ]
    else:
        assert "Linux x86_64" in process.stdout
        assert github_protocol.server.requests == []
    assert not (tmp_path / "licensed-engines" / engine).exists()
    assert not (tmp_path / "licensed-engines/openmpi-build").exists()
    assert not (tmp_path / "licensed-engines" / setup.ENVIRONMENT_NAME).exists()
    assert not list((tmp_path / "licensed-engines").glob(".private-download-*"))


def test_corrupt_mpi_source_cache_is_refused_and_preserved(tmp_path):
    cache = tmp_path / setup.install_openmpi.SOURCE_URL.rsplit("/", 1)[-1]
    cache.write_text("Incorrect public-source cache for checksum rejection")
    before = cache.read_bytes()
    with pytest.raises(ValueError, match="Cached Open MPI source differs"):
        setup.install_openmpi.download_source(tmp_path)
    assert cache.read_bytes() == before
    assert list(tmp_path.iterdir()) == [cache]


def test_cfour_environment_export_format_round_trips_without_installation_claim(tmp_path):
    prefix = tmp_path / "licensed-engines/cfour"
    result = {"executable": str(prefix / "bin/xcfour"), "cfour_home": str(prefix),
              "cfour_bin": str(prefix / "bin"), "genbas": str(prefix / "basis/GENBAS"),
              "ecpdata": str(prefix / "basis/ECPDATA"), "ld_library_path": str(prefix / "lib/runtime"),
              "provenance": str(prefix / "receipt.json"), "path_entries": [str(prefix / "bin")]}
    env_file, path_file = tmp_path / "env.txt", tmp_path / "path.txt"
    setup.provision_cfour.github_environment(result, env_file, path_file)
    values = dict(line.split("=", 1) for line in env_file.read_text().splitlines())
    paths = path_file.read_text().splitlines()
    setup.save_environment(tmp_path, {"schema_version": 1, "providers": {},
                                      "values": values, "path_entries": paths})
    observed_values, observed_paths = setup.load_environment(tmp_path)
    assert observed_values == values
    assert observed_paths == paths == [str(prefix / "bin")]
    assert values["COCHEM_CFOUR_OPENMP_AVAILABLE"] == "true"
    assert values["COCHEM_CFOUR_MPI_AVAILABLE"] == "false"
    assert "LD_LIBRARY_PATH" not in values
    assert not (prefix / "bin/xcfour").exists()
    # Serialization of declared metadata does not bypass the real verifier.
    prefix.mkdir()
    with pytest.raises(ValueError):
        setup.verify_existing("cfour", prefix, setup.provision_cfour.load_distribution_manifest())


def test_orca_reuse_requires_a_real_provisioning_receipt(tmp_path):
    prefix = tmp_path / "orca"
    prefix.mkdir()
    (prefix / "non-executable.txt").write_text("Unrecorded bytes cannot establish engine eligibility")
    with pytest.raises(ValueError, match="no verified provisioning receipt"):
        setup.verify_existing("orca", prefix, setup.provision_orca.load_distribution_manifest())


def test_stage0_refresh_requires_existing_ui_interpreter(tmp_path):
    setup.save_environment(tmp_path, environment_payload(tmp_path))
    assert setup.refresh_stage0(tmp_path) is False
    assert not (tmp_path / "Registry").exists()


def test_stage0_refresh_refuses_unsafe_environment_before_launch(tmp_path):
    interpreter = tmp_path / "ui-env/bin/python"
    interpreter.parent.mkdir(parents=True)
    interpreter.symlink_to(sys.executable)
    destination = tmp_path / "licensed-engines"
    destination.mkdir()
    payload = environment_payload(tmp_path)
    payload["values"]["LAB_ARCHIVE_TOKEN"] = "credential-isolation-canary-not-a-real-secret"
    (destination / setup.ENVIRONMENT_NAME).write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="unsupported variable"):
        setup.refresh_stage0(tmp_path)
    assert not (tmp_path / "Registry").exists()


def test_licensed_setup_cli_exposes_optional_engine_selection_without_provisioning():
    process = subprocess.run(
        [sys.executable, "-B", str(setup.REPO_ROOT / "scripts/setup_licensed_engines.py"), "--help"],
        cwd=setup.REPO_ROOT, stdin=subprocess.DEVNULL, capture_output=True,
        text=True, check=False, timeout=15,
    )
    assert process.returncode == 0, process.stderr
    assert "--engine {orca,cfour,both}" in process.stdout
    assert "--no-refresh-stage0" in process.stdout


def test_codespaces_requests_explicit_read_permissions_and_cli_available():
    configuration = json.loads((setup.REPO_ROOT / ".devcontainer/devcontainer.json").read_text())
    repositories = configuration["customizations"]["codespaces"]["repositories"]
    for provider in ("ORCA", "CFOUR"):
        assert repositories[f"ProfJJK-CoChem/CoChem-{provider}"]["permissions"] == {"contents": "read"}
    assert "ghcr.io/devcontainers/features/github-cli:1" in configuration["features"]
