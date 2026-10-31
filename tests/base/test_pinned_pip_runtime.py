"""Real offline pinned-tool execution; no scientific packages or executor doubles."""
import hashlib
import importlib.metadata
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import manage_modules as installer
from tests.base.test_module_installer import BACKEND


PIP_SIZE = 1816475
PIP_SHA256 = "931c303696af6fa3417112103b1cad26890e5a07eccb5b99783700e33f2b8aad"
INSPECT = '''import base64,csv,hashlib,importlib.metadata,json,pathlib,sys
report={'prefix':sys.prefix,'distributions':{},'installed_distributions':{
    dist.metadata['Name']:dist.version for dist in importlib.metadata.distributions()}}
for name in ('pip','cochem-installer-fixture'):
    try: dist=importlib.metadata.distribution(name)
    except importlib.metadata.PackageNotFoundError: continue
    files={}
    for row in csv.reader(dist.read_text('RECORD').splitlines()):
        relative,encoded,size=row
        path=pathlib.Path(dist.locate_file(relative)).resolve()
        assert path.is_relative_to(pathlib.Path(sys.prefix).resolve()),str(path)
        if not path.exists() and path.suffix in ('.pyc','.pyo'):
            assert not encoded,(name,relative)
            files[relative]={'missing_optional_bytecode':True}
            continue
        data=path.read_bytes()
        if encoded:
            algorithm,digest=encoded.split('=',1)
            actual=base64.urlsafe_b64encode(hashlib.new(algorithm,data).digest()).rstrip(b'=').decode()
            assert actual==digest,(name,relative)
            assert len(data)==int(size),(name,relative)
        files[relative]=hashlib.sha256(data).hexdigest()
    report['distributions'][name]={'version':dist.version,'files':files,
        'direct_url':json.loads(dist.read_text('direct_url.json') or 'null')}
if 'cochem-installer-fixture' in report['distributions']:
    import cochem_installer_fixture
    report['fixture_value']=cochem_installer_fixture.VALUE
    report['fixture_origin']=cochem_installer_fixture.__file__
print(json.dumps(report))
'''


def _tree(path):
    """Compare owned runtime bytes/modes/links, without following executable links."""
    result = {}
    for member in sorted(path.rglob("*")):
        info = member.lstat()
        if stat.S_ISLNK(info.st_mode):
            value = ("link", info.st_mode, os.readlink(member))
        elif stat.S_ISREG(info.st_mode):
            value = ("file", info.st_mode, hashlib.sha256(member.read_bytes()).hexdigest())
        else:
            assert stat.S_ISDIR(info.st_mode), str(member)
            value = ("directory", info.st_mode)
        result[member.relative_to(path).as_posix()] = value
    return result


def _caller_pip():
    """The caller's installed tool stays intact even when another tool executes."""
    dist = importlib.metadata.distribution("pip")
    files = {}
    for name in dist.files:
        path = Path(dist.locate_file(name))
        try:
            files[str(path)] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        except FileNotFoundError:
            # Retain absent RECORD entries as state, rather than silently
            # dropping them or repairing an existing accepted environment.
            files[str(path)] = {"missing": True}
    return {"version": dist.version, "files": files}


@pytest.fixture
def wheel():
    # The shared session fixture supplies the checksum-verified artifact.
    # This fixture validates that delivery; missing prerequisites fail visibly.
    path = Path(os.environ["COCHEM_PINNED_PIP_WHEEL"])
    assert path.name == "pip-26.2-py3-none-any.whl"
    assert not path.is_symlink() and path.is_file()
    data = path.read_bytes()
    assert len(data) == PIP_SIZE
    assert hashlib.sha256(data).hexdigest() == PIP_SHA256
    return path


@pytest.fixture
def offline_env(tmp_path):
    env = {key: value for key, value in installer._build_env().items()
           if not key.startswith("PIP_")}
    env.update(PIP_NO_INDEX="1", PIP_CONFIG_FILE=os.devnull,
               PIP_CACHE_DIR=str(tmp_path / "cache"),
               PIP_DISABLE_PIP_VERSION_CHECK="1", PYTHONDONTWRITEBYTECODE="1")
    return env


@pytest.fixture
def bare_python(tmp_path, offline_env):
    target = tmp_path / "target"
    subprocess.run([sys.executable, "-I", "-B", "-m", "venv", "--without-pip", str(target)],
                   check=True, capture_output=True, text=True, env=offline_env, timeout=45)
    python = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    assert _inspect(python, offline_env)["distributions"] == {}
    return python, target


def _inspect(python, env):
    result = subprocess.run([str(python), "-I", "-B", "-c", INSPECT],
                            check=True, capture_output=True, text=True, env=env, timeout=20)
    return json.loads(result.stdout)


def _project(path):
    path.mkdir()
    (path / "pyproject.toml").write_text(
        '[build-system]\nrequires=[]\nbuild-backend="backend"\nbackend-path=["."]\n')
    body = BACKEND.replace(
        "def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):\n",
        "def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):\n"
        "    if 'COCHEM_PINNED_PIP_WHEEL' in os.environ:\n"
        "        raise RuntimeError('Pinned tool delivery reached package backend')\n"
        "    pathlib.Path(__file__).with_name('backend-executed').write_text('real PEP 517 build')\n")
    assert body != BACKEND
    (path / "backend.py").write_text(body)
    return path / "backend-executed"


def test_real_without_pip_bootstrap_build_install_and_record(
        wheel, bare_python, offline_env, tmp_path, pinned_pip_test_artifact):
    python, target = bare_python
    assert wheel == pinned_pip_test_artifact
    caller = _caller_pip()
    installer._run_pip(python, [], env=offline_env, label="Pinned pip bootstrap",
                       wheel=wheel, bootstrap=True, timeout=45)
    bootstrapped = _inspect(python, offline_env)
    assert Path(bootstrapped["prefix"]).resolve() == target.resolve()
    assert bootstrapped["distributions"]["pip"]["version"] == "26.2"
    pip_source = bootstrapped["distributions"]["pip"]["direct_url"]
    assert pip_source["url"].startswith("file:") and pip_source["url"].endswith(wheel.name)
    assert pip_source["archive_info"]["hashes"]["sha256"] == PIP_SHA256
    project, wheels = tmp_path / "project", tmp_path / "wheels"
    marker = _project(project)
    assert not marker.exists()
    build_env = dict(offline_env, COCHEM_PINNED_PIP_WHEEL=str(wheel))
    installer._run_pip(python, ["wheel", "--no-deps", "--no-index", "--wheel-dir", str(wheels), str(project)],
                       env=build_env, label="Real offline fixture build", timeout=45)
    assert marker.read_text() == "real PEP 517 build"
    built = list(wheels.glob("*.whl"))
    assert len(built) == 1 and built[0].name == "cochem_installer_fixture-1.2.3-py3-none-any.whl"
    installer._run_pip(python, ["install", "--no-index", "--no-deps", str(built[0])],
                       env=offline_env, label="Real offline fixture install", wheel=wheel, timeout=45)
    installer._run_pip(python, ["check"], env=offline_env, label="Real dependency check",
                       wheel=wheel, timeout=20)
    installed = _inspect(python, offline_env)
    assert installed["fixture_value"] == 42
    assert Path(installed["fixture_origin"]).resolve().is_relative_to(target.resolve())
    assert installed["distributions"]["cochem-installer-fixture"]["version"] == "1.2.3"
    assert installed["distributions"]["cochem-installer-fixture"]["direct_url"]["url"] == built[0].as_uri()
    assert _caller_pip() == caller


def test_pinned_entrypoint_leaves_callers_installed_pip_unchanged(wheel, offline_env):
    before = _caller_pip()
    output = installer._run_pip(Path(sys.executable), ["--version"], env=offline_env,
                                label="Pinned tool identity", wheel=wheel, timeout=20)
    assert output.startswith("pip 26.2 from ")
    assert wheel.name + "/pip" in output.replace("\\", "/")
    assert _caller_pip() == before


def test_bootstrap_ignores_hostile_install_config_and_environment(wheel, bare_python, offline_env, tmp_path):
    python, target = bare_python
    project = tmp_path / "injected-project"
    marker = _project(project)
    requirements = tmp_path / "injected-requirements.txt"
    requirements.write_text(str(project) + "\n")
    constraint = tmp_path / "injected-constraints.txt"
    constraint.write_text("pip==0.0\n")
    destinations = {name: tmp_path / name for name in
                    ("config-target", "env-target", "env-prefix", "env-root")}
    config = tmp_path / "hostile-pip.conf"
    config.write_text("[install]\nrequirement=" + str(requirements)
                      + "\ntarget=" + str(destinations["config-target"]) + "\nuser=true\n")
    env = dict(offline_env, PIP_CONFIG_FILE=str(config),
               PIP_TARGET=str(destinations["env-target"]),
               PIP_PREFIX=str(destinations["env-prefix"]),
               PIP_ROOT=str(destinations["env-root"]), PIP_USER="1",
               PIP_REQUIREMENT=str(requirements), PIP_CONSTRAINT=str(constraint))
    before_env, before_project, caller = dict(env), _tree(project), _caller_pip()
    installer._run_pip(python, [], env=env, label="Hostile settings bootstrap",
                       wheel=wheel, bootstrap=True, timeout=45)
    installed = _inspect(python, offline_env)
    assert Path(installed["prefix"]).resolve() == target.resolve()
    assert installed["installed_distributions"] == {"pip": "26.2"}
    assert installed["distributions"]["pip"]["direct_url"]["archive_info"]["hashes"]["sha256"] == PIP_SHA256
    assert _tree(project) == before_project
    assert not marker.exists()
    assert all(not path.exists() for path in destinations.values())
    assert env == before_env
    assert _caller_pip() == caller


def test_fresh_environment_bootstrap_retry_and_readonly_reuse(wheel, bare_python, offline_env, tmp_path):
    python, target = bare_python
    missing = tmp_path / "missing" / wheel.name
    before, caller = _tree(target), _caller_pip()
    with pytest.raises(installer.ModuleInstallationError, match="artifact is missing"):
        installer._ensure_pip(python, target, env=offline_env,
                              label="Actual failed fresh bootstrap", wheel=missing, timeout=45)
    assert _tree(target) == before
    assert _inspect(python, offline_env)["installed_distributions"] == {}
    assert _caller_pip() == caller
    installer._ensure_pip(python, target, env=offline_env,
                          label="Actual fresh bootstrap retry", wheel=wheel, timeout=45)
    installed = _inspect(python, offline_env)
    assert Path(installed["prefix"]).resolve() == target.resolve()
    assert installed["installed_distributions"] == {"pip": "26.2"}
    assert installed["distributions"]["pip"]["direct_url"]["archive_info"]["hashes"]["sha256"] == PIP_SHA256
    accepted = _tree(target)
    # An accepted existing tool is inspected, never upgraded or re-seeded.
    # The missing artifact must be irrelevant to this read-only branch.
    installer._ensure_pip(python, target, env=offline_env,
                          label="Read-only existing pip reuse", wheel=missing, timeout=20)
    assert _tree(target) == accepted
    assert _caller_pip() == caller


@pytest.mark.parametrize("damage", ["missing", "one-byte-corruption"])
@pytest.mark.parametrize(("bootstrap", "delivery"), [(True, "explicit"), (False, "configured")])
def test_invalid_artifact_refuses_without_backend_or_runtime_mutation(
        wheel, bare_python, offline_env, tmp_path, damage, bootstrap, delivery):
    python, target = bare_python
    project = tmp_path / "project"
    marker = _project(project)
    invalid = tmp_path / "invalid" / wheel.name
    if damage == "one-byte-corruption":
        invalid.parent.mkdir()
        data = bytearray(wheel.read_bytes())
        data[len(data) // 2] ^= 1
        invalid.write_bytes(data)
        assert invalid.stat().st_size == PIP_SIZE
        assert hashlib.sha256(invalid.read_bytes()).hexdigest() != PIP_SHA256
    before, caller = _tree(target), _caller_pip()
    arguments = [] if bootstrap else ["wheel", "--no-index", "--no-deps", "--wheel-dir",
                                     str(tmp_path / "wheels"), str(project)]
    env = dict(offline_env, COCHEM_PINNED_PIP_WHEEL=str(invalid))
    refusal = ("artifact is missing, redirected or has the wrong size" if damage == "missing"
               else "checksum verification failed; no package tool was executed")
    with pytest.raises(installer.ModuleInstallationError, match=refusal):
        installer._run_pip(python, arguments, env=env, label="Invalid artifact refusal",
                           wheel=invalid if delivery == "explicit" else None,
                           bootstrap=bootstrap, timeout=20)
    assert _tree(target) == before
    assert _caller_pip() == caller
    assert not marker.exists()
    assert not (tmp_path / "wheels").exists()
    assert not (tmp_path / "cache").exists()
