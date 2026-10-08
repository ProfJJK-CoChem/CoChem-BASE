"""Authorization, credential isolation and persistent Codespaces environment.

Filesystem/control tests use text artifacts. They do not run licensed engines
or describe stubbed orchestration as scientific calculation acceptance.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cochem_base.core_engine.engine_environment import engine_runtime_environment
from scripts import hosted_dashboard
from scripts import setup_licensed_engines as setup


@pytest.mark.parametrize("remote", [
    "https://github.com/student/project.git", "git@github.com:student/project.git",
    "ssh://git@github.com/student/project.git", "https://user:credential@github.com/student/project.git",
])
def test_project_origin_resolves_without_returning_url_credentials(remote):
    assert setup.github_repository(remote) == "student/project"


@pytest.mark.parametrize("remote", ["https://elsewhere.example/student/project.git", "../project",
                                         "https://github.com/student/project/other.git"])
def test_non_github_or_ambiguous_origin_is_rejected(remote):
    with pytest.raises(ValueError):
        setup.github_repository(remote)


@pytest.mark.parametrize("metadata", [{"full_name": "student/project", "private": False},
                                      {"full_name": "someone/else", "private": True}, {}])
def test_project_visibility_and_identity_are_both_required(monkeypatch, metadata):
    monkeypatch.setattr(setup, "github_call", lambda arguments: json.dumps(metadata))
    with pytest.raises(ValueError, match="private"):
        setup.require_private_repository("student/project")


def test_public_project_is_rejected_before_any_asset_access(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(setup.platform, "system", lambda: "Linux")
    monkeypatch.setattr(setup.platform, "machine", lambda: "x86_64")

    def run(arguments, **kwargs):
        calls.append(arguments)
        assert arguments == ["git", "remote", "get-url", "origin"]
        return subprocess.CompletedProcess(arguments, 0, "https://github.com/student/project.git\n", "")

    def github(arguments):
        calls.append(arguments)
        assert arguments == ["api", "repos/student/project"]
        return json.dumps({"full_name": "student/project", "private": False})

    monkeypatch.setattr(setup.subprocess, "run", run)
    monkeypatch.setattr(setup, "github_call", github)
    with pytest.raises(ValueError, match="private"):
        setup.provision_selected(["orca", "cfour"], tmp_path, 2)
    assert len(calls) == 2
    assert not (tmp_path / "licensed-engines").exists()


def test_github_denial_does_not_echo_untrusted_token_bearing_cli_output(monkeypatch):
    confidential = "never-echo-this-auth-value"
    monkeypatch.setattr(setup.subprocess, "run", lambda arguments, **kwargs:
                        subprocess.CompletedProcess(arguments, 1, confidential, confidential))
    with pytest.raises(ValueError) as caught:
        setup.github_call(["api", "repos/student/project"])
    assert confidential not in str(caught.value)
    assert "permissions" in str(caught.value)


def test_installer_process_environment_uses_explicit_non_secret_inputs(monkeypatch):
    for key in ("GH_TOKEN", "GITHUB_TOKEN", "LAB_ARCHIVE_TOKEN", "AWS_ACCESS_KEY_ID",
                "SECRET_VAR", "HTTPS_PROXY", "LD_PRELOAD", "CUSTOM_CREDENTIAL"):
        monkeypatch.setenv(key, "sensitive-placeholder")
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    environment = setup.installer_environment()
    assert environment["LANG"] == "C"
    assert environment["PATH"]
    assert not any("sensitive-placeholder" == value for value in environment.values())
    assert os.environ["GH_TOKEN"] == "sensitive-placeholder"


@pytest.mark.parametrize("engine", ["orca", "cfour", "xtb", "crest", "qe"])
def test_real_child_does_not_receive_github_or_other_authentication(engine):
    confidential = {key: "sensitive-placeholder" for key in (
        "GH_TOKEN", "GITHUB_TOKEN", "LAB_ARCHIVE_TOKEN", "AWS_ACCESS_KEY_ID", "OPENAI_API_KEY",
        "ACTIONS_RUNTIME_TOKEN", "MY_PASSWORD", "SSH_AUTH_SOCK", "GIT_ASKPASS", "HTTPS_PROXY",
        "GIT_CONFIG_VALUE_0", "GH_CONFIG_DIR",
    )}
    inherited = {**os.environ, **confidential, "OMP_NUM_THREADS": "2", "GITHUB_ACTIONS": "true"}
    before = dict(inherited)
    child_environment = engine_runtime_environment(engine, inherited, executable=sys.executable)
    probe = "import os,sys; assert all(name not in os.environ for name in sys.argv[1:]); assert os.environ['GITHUB_ACTIONS']=='true'"
    subprocess.run([sys.executable, "-c", probe, *confidential], env=child_environment,
                   check=True, timeout=15)
    assert inherited == before


def environment_payload(root):
    executable = root / "licensed-engines" / "orca" / "distribution" / "orca"
    return {"schema_version": 1, "providers": {}, "values": {"COCHEM_ORCA_BIN": str(executable)},
            "path_entries": [str(executable.parent)]}


def test_persistent_bindings_are_loaded_by_later_dashboard_process(tmp_path):
    payload = environment_payload(tmp_path)
    setup.save_environment(tmp_path, payload)
    environment = hosted_dashboard.runtime_environment(tmp_path)
    assert environment["COCHEM_ORCA_BIN"] == payload["values"]["COCHEM_ORCA_BIN"]
    assert environment["PATH"].split(os.pathsep)[0] == payload["path_entries"][0]
    shell_file = tmp_path / "licensed-engines/codespaces-environment.sh"
    assert shell_file.stat().st_mode & 0o077 == 0


def test_terminal_helper_quotes_paths_without_executing_shell_substitutions(tmp_path):
    # A malicious-looking path remains a literal path in both JSON and shell.
    root = tmp_path / "a space $(touch injected) `touch injected`"
    setup.save_environment(root, environment_payload(root))
    helper = root / "licensed-engines/codespaces-environment.sh"
    process = subprocess.run(["bash", "-c", 'source "$1"; test "$COCHEM_ORCA_BIN" = "$2"',
                              "test", str(helper), environment_payload(root)["values"]["COCHEM_ORCA_BIN"]],
                             cwd=tmp_path, check=False, timeout=10)
    assert process.returncode == 0
    assert not (tmp_path / "injected").exists()


@pytest.mark.parametrize("mutation", ["secret", "checkout", "newline", "mpi_path", "invalid_boolean"])
def test_persisted_environment_rejects_secret_variables_and_unsafe_paths(tmp_path, mutation):
    payload = environment_payload(tmp_path)
    if mutation == "secret":
        payload["values"]["LAB_ARCHIVE_TOKEN"] = "confidential"
    elif mutation == "checkout":
        payload["values"]["COCHEM_ORCA_BIN"] = str(setup.REPO_ROOT / "fake-orca")
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
    file.write_text("text-only-test-fixture")
    records = {"program": {"bytes": file.stat().st_size,
                           "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}}
    setup.verify_file_inventory(tmp_path, records, "receipt.json")
    file.write_text("changed-test-fixture")
    with pytest.raises(ValueError, match="bytes changed"):
        setup.verify_file_inventory(tmp_path, records, "receipt.json")
    (tmp_path / "extra").write_text("unexpected")
    with pytest.raises(ValueError, match="inventory changed"):
        setup.verify_file_inventory(tmp_path, records, "receipt.json")


def test_unrecorded_installation_refuses_overwrite_before_download(monkeypatch, tmp_path):
    (tmp_path / "licensed-engines/orca").mkdir(parents=True)
    monkeypatch.setattr(setup.platform, "system", lambda: "Linux")
    monkeypatch.setattr(setup.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(setup, "require_private_project", lambda: "student/project")
    monkeypatch.setattr(setup, "require_private_repository", lambda repository: None)
    monkeypatch.setattr(setup, "github_call", lambda arguments: pytest.fail("must not download"))
    with pytest.raises(ValueError, match="unrecorded"):
        setup.provision_selected(["orca"], tmp_path, 2)


def test_archive_checksum_failure_precedes_mpi_build_or_native_provision(monkeypatch, tmp_path):
    monkeypatch.setattr(setup.platform, "system", lambda: "Linux")
    monkeypatch.setattr(setup.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(setup, "require_private_project", lambda: "student/project")
    monkeypatch.setattr(setup, "require_private_repository", lambda repository: None)
    manifest = setup.provision_orca.load_distribution_manifest()

    def download(arguments):
        assert arguments[:3] == ["release", "download", manifest["release_tag"]]
        Path(arguments[arguments.index("--dir") + 1], manifest["archive_name"]).write_text("tampered text fixture")
        return ""

    monkeypatch.setattr(setup, "github_call", download)
    monkeypatch.setattr(setup, "checked_installer", lambda arguments: pytest.fail("must not execute native/build"))
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        setup.provision_selected(["orca"], tmp_path, 2)
    assert not (tmp_path / "licensed-engines" / setup.ENVIRONMENT_NAME).exists()
    assert not list((tmp_path / "licensed-engines").glob(".private-download-*"))


def prepare_orca_control(monkeypatch):
    archive_bytes = b"text fixture for ORCA routing control"
    manifest = {**setup.provision_orca.load_distribution_manifest(),
                "sha256": hashlib.sha256(archive_bytes).hexdigest()}
    monkeypatch.setattr(setup.provision_orca, "load_distribution_manifest", lambda: manifest)
    monkeypatch.setattr(setup.platform, "system", lambda: "Linux")
    monkeypatch.setattr(setup.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(setup, "require_private_project", lambda: "student/project")
    monkeypatch.setattr(setup, "require_private_repository", lambda repository: None)

    def download(arguments):
        Path(arguments[arguments.index("--dir") + 1], manifest["archive_name"]).write_bytes(archive_bytes)
        return ""

    monkeypatch.setattr(setup, "github_call", download)


def test_mpi_public_source_prefetch_retains_controller_proxy_before_scrubbed_builder(monkeypatch, tmp_path):
    prepare_orca_control(monkeypatch)
    monkeypatch.setenv("GH_TOKEN", "sensitive-placeholder")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:8080")
    order = []

    def prefetch(build_root):
        order.append("download")
        assert os.environ["HTTPS_PROXY"] == "http://proxy.invalid:8080"
        assert build_root.is_dir()
        source = build_root / setup.install_openmpi.SOURCE_URL.rsplit("/", 1)[-1]
        source.write_text("text-only public-source routing fixture")
        return source

    def run(arguments, **kwargs):
        order.append("build")
        assert arguments[1] == str(setup.REPO_ROOT / "scripts/install_openmpi.py")
        assert "GH_TOKEN" not in kwargs["env"] and "HTTPS_PROXY" not in kwargs["env"]
        build_root = Path(arguments[arguments.index("--build-root") + 1])
        assert (build_root / setup.install_openmpi.SOURCE_URL.rsplit("/", 1)[-1]).is_file()
        # End this control at the compiler boundary; no native software runs.
        raise subprocess.CalledProcessError(1, arguments)

    monkeypatch.setattr(setup.install_openmpi, "download_source", prefetch)
    monkeypatch.setattr(setup.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        setup.provision_selected(["orca"], tmp_path, 2)
    assert order == ["download", "build"]
    assert os.environ["GH_TOKEN"] == "sensitive-placeholder"


def test_corrupt_mpi_source_cache_is_refused_before_credential_free_builder(monkeypatch, tmp_path):
    prepare_orca_control(monkeypatch)
    build_root = tmp_path / "licensed-engines/openmpi-build"
    build_root.mkdir(parents=True)
    cache = build_root / setup.install_openmpi.SOURCE_URL.rsplit("/", 1)[-1]
    cache.write_text("incorrect public-source cache")
    monkeypatch.setattr(setup, "checked_installer", lambda arguments: pytest.fail("must not build"))
    with pytest.raises(ValueError, match="Cached Open MPI source differs"):
        setup.provision_selected(["orca"], tmp_path, 2)
    assert cache.read_text() == "incorrect public-source cache"


def test_cfour_routing_persists_real_provider_environment_format_and_reuses_only_after_verification(monkeypatch, tmp_path):
    # Mock the external installation boundary, not the verification/parser code;
    # the text fixture is deliberately not represented as a CFOUR executable.
    archive_bytes = b"text fixture for installation orchestration"
    manifest = {**setup.provision_cfour.load_distribution_manifest(),
                "sha256": hashlib.sha256(archive_bytes).hexdigest()}
    monkeypatch.setattr(setup.provision_cfour, "load_distribution_manifest", lambda: manifest)
    monkeypatch.setattr(setup.platform, "system", lambda: "Linux")
    monkeypatch.setattr(setup.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(setup, "require_private_project", lambda: "student/project")
    monkeypatch.setattr(setup, "require_private_repository", lambda repository: None)
    downloads, installs, verifications = [], [], []

    def download(arguments):
        downloads.append(arguments)
        assert arguments[:3] == ["release", "download", manifest["release_tag"]]
        assert arguments[arguments.index("--repo") + 1] == manifest["repository"]
        Path(arguments[arguments.index("--dir") + 1], manifest["archive_name"]).write_bytes(archive_bytes)
        return ""

    def installer(arguments):
        installs.append(arguments)
        assert arguments[0] == str(setup.REPO_ROOT / "scripts/provision_cfour.py")
        prefix = Path(arguments[arguments.index("--install-root") + 1])
        prefix.mkdir()
        result = {"executable": str(prefix / "bin/xcfour"), "cfour_home": str(prefix),
                  "cfour_bin": str(prefix / "bin"), "genbas": str(prefix / "basis/GENBAS"),
                  "ecpdata": str(prefix / "basis/ECPDATA"), "ld_library_path": str(prefix / "lib/runtime"),
                  "provenance": str(prefix / "receipt.json"), "path_entries": [str(prefix / "bin")]}
        setup.provision_cfour.github_environment(result,
            Path(arguments[arguments.index("--github-env") + 1]),
            Path(arguments[arguments.index("--github-path") + 1]))

    def verify(engine, prefix, approved):
        verifications.append((engine, prefix, approved))

    monkeypatch.setattr(setup, "github_call", download)
    monkeypatch.setattr(setup, "checked_installer", installer)
    monkeypatch.setattr(setup, "verify_existing", verify)
    result = setup.provision_selected(["cfour"], tmp_path, 2)
    assert result["engines"] == ["cfour"] and result["project"] == "student/project"
    values, paths = setup.load_environment(tmp_path)
    assert values["COCHEM_CFOUR_OPENMP_AVAILABLE"] == "true"
    assert values["COCHEM_CFOUR_MPI_AVAILABLE"] == "false"
    assert "LD_LIBRARY_PATH" not in values
    assert paths == [str(tmp_path / "licensed-engines/cfour/bin")]
    assert not (tmp_path / "licensed-engines/cfour/bin/xcfour").exists()
    assert len(downloads) == len(installs) == 1
    setup.provision_selected(["cfour"], tmp_path, 2)
    assert verifications == [("cfour", tmp_path / "licensed-engines/cfour", manifest)]
    assert len(downloads) == len(installs) == 1


def test_stage0_refresh_loads_persistent_paths_without_github_credentials(monkeypatch, tmp_path):
    python = tmp_path / "ui-env/bin/python"
    python.parent.mkdir(parents=True)
    python.touch()
    setup.save_environment(tmp_path, environment_payload(tmp_path))
    monkeypatch.setenv("GH_TOKEN", "sensitive-placeholder")
    monkeypatch.setenv("COCHEM_ANY_OTHER_TOKEN", "sensitive-placeholder")
    calls = []

    def run(arguments, **kwargs):
        calls.append(arguments)
        assert arguments[:3] == [str(python), str(setup.REPO_ROOT / "cli.py"), "setup"]
        assert "--all" in arguments and "--skip-heavy" in arguments
        assert kwargs["env"]["COCHEM_ORCA_BIN"] == environment_payload(tmp_path)["values"]["COCHEM_ORCA_BIN"]
        assert "GH_TOKEN" not in kwargs["env"] and "COCHEM_ANY_OTHER_TOKEN" not in kwargs["env"]
        assert kwargs["check"] is True
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(setup.subprocess, "run", run)
    assert setup.refresh_stage0(tmp_path) is True
    assert len(calls) == 1


def test_successful_provision_instruction_requires_running_dashboard_reload(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(setup, "provision_selected", lambda engines, root, jobs: {"engines": engines})
    monkeypatch.setattr(setup, "refresh_stage0", lambda root: True)
    assert setup.main(["--engine", "both", "--artifacts", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "stop and resume this Codespace" in output
    assert "hosted_dashboard.py start" in output


def test_codespaces_requests_explicit_read_permissions_and_cli_available():
    configuration = json.loads((setup.REPO_ROOT / ".devcontainer/devcontainer.json").read_text())
    repositories = configuration["customizations"]["codespaces"]["repositories"]
    for provider in ("ORCA", "CFOUR"):
        assert repositories[f"ProfJJK-CoChem/CoChem-{provider}"]["permissions"] == {"contents": "read"}
    assert "ghcr.io/devcontainers/features/github-cli:1" in configuration["features"]
