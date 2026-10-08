"""Real packaging hotfixes preserve accepted environments at unchanged source.

These tiny distributions test installation and upgrade custody, not chemistry.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import manage_modules as installer
from tests.base.test_module_installer import BACKEND, git, offline_environment
from tests.base.test_module_installer import repository as repository


def _run(command, origin):
    return subprocess.run(command, env=offline_environment(origin), check=True,
                          capture_output=True, text=True, timeout=90).stdout.strip()


def _legacy_install(origin, spec, root, dependency_wheels=()):
    """Create a genuine old layout directly, before accepting its receipt."""
    parent = root / "fixture"
    location = parent / spec["revision"]
    source, environment = location / "source", location / "env"
    location.mkdir(parents=True)
    _run(["git", "init", str(source)], origin)
    _run(["git", "-C", str(source), "remote", "add", "origin", installer._repository_url(spec)], origin)
    _run(["git", "-C", str(source), "fetch", "--depth", "1", "origin", spec["revision"]], origin)
    _run(["git", "-C", str(source), "checkout", "--detach", spec["revision"]], origin)
    _run([sys.executable, "-I", "-B", "-m", "venv", str(environment)], origin)
    python = installer._python_path(environment)
    # The actual reviewed backend is stdlib-only; its wheel requires no index.
    wheels = location / "wheels"
    _run([str(python), "-I", "-B", "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheels), str(source)], origin)
    wheel = next(wheels.glob("*.whl"))
    _run([str(python), "-I", "-B", "-m", "pip", "install", str(wheel), *map(str, dependency_wheels)], origin)
    _run([str(python), "-I", "-B", "-m", "pip", "check"], origin)
    receipt = {"schema_version": installer.RECEIPT_SCHEMA, "status": "installed", "module_id": "fixture",
               "repository": spec["repository"], "revision": spec["revision"], "distribution": spec["distribution"],
               "manifest_spec_sha256": installer._digest_json(spec), "source_path": str(source),
               "python_path": str(python), "adapter": spec["adapter"], "operations": spec["operations"],
               "built_wheel_path": str(wheel), "built_wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
               "private_dependency_wheels": [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                              "name": installer._wheel_identity(path)[0], "version": installer._wheel_identity(path)[1]}
                                             for path in dependency_wheels], "pip_check": {"passed": True},
               "environment_sha256": installer._environment_integrity(environment),
               **installer._source_integrity(source, spec), **installer._probe(python, spec["distribution"])}
    installer._atomic_json(parent / "source.json", {"schema_version": installer.SOURCE_SCHEMA, "status": "downloaded",
        "module_id": "fixture", "repository": spec["repository"], "revision": spec["revision"],
        "manifest_spec_sha256": installer._digest_json(spec), "source_path": str(source), **installer._source_integrity(source, spec)})
    installer._atomic_json(parent / "installation.json", receipt)
    assert not (location / "installation.json").exists()
    return receipt


def _dependency_hotfix(origin):
    source = origin.parent / "engineering-dependency"
    source.mkdir()
    git(source, "init")
    (source / "pyproject.toml").write_text('[build-system]\nrequires=[]\nbuild-backend="backend"\nbackend-path=["."]\n')
    revisions, wheels = [], []
    for generation in ("previous", "updated"):
        backend = BACKEND.replace("cochem_installer_fixture", "cochem_generation_dependency").replace(
            "cochem-installer-fixture", "cochem-generation-dependency").replace("VALUE = 42", "GENERATION = '" + generation + "'")
        (source / "backend.py").write_text(backend)
        git(source, "add", ".")
        git(source, "-c", "user.name=CoChem packaging control", "-c", "user.email=packaging@example.invalid", "commit", "-m", generation)
        revisions.append(git(source, "rev-parse", "HEAD"))
        destination = origin.parent / ("dependency-wheel-" + generation)
        _run([sys.executable, "-I", "-B", "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(destination), str(source)], origin)
        wheels.append(next(destination.glob("*.whl")))
    return revisions, wheels


def test_same_provider_revision_new_science_pin_keeps_verified_legacy_runtime(repository):
    origin, original, root = repository
    revisions, wheels = _dependency_hotfix(origin)
    old = dict(original, science_base_revision=revisions[0], adapter_requirements=["cochem-generation-dependency==1.2.3"])
    accepted = _legacy_install(origin, old, root, [wheels[0]])
    before = (root / "fixture/installation.json").read_bytes()
    old_environment = Path(accepted["python_path"]).parent.parent
    environment_hash = installer._environment_integrity(old_environment)
    source_hash = installer._source_integrity(Path(accepted["source_path"]), old)
    changed = dict(old, science_base_revision=revisions[1])
    manifest = origin.parent / "generation-manifest.json"
    manifest.write_text(json.dumps({"schema_version": installer.MANIFEST_SCHEMA, "modules": {"fixture": changed}}))
    code = """import json,sys
from pathlib import Path
from scripts.manage_modules import install_module
print(json.dumps(install_module('fixture',json.loads(sys.argv[1]),Path(sys.argv[2]),activate=False,dependency_wheels=[Path(sys.argv[3])])))
"""
    prepared = json.loads(_run([sys.executable, "-B", "-c", code, json.dumps(changed), str(root), str(wheels[1])], origin))
    assert prepared["revision"] == accepted["revision"]
    assert Path(prepared["python_path"]) != Path(accepted["python_path"])
    assert Path(prepared["python_path"]).is_relative_to(root / "fixture" / old["revision"] / "policies" / installer._digest_json(changed))
    assert (root / "fixture/installation.json").read_bytes() == before
    assert installer._environment_integrity(old_environment) == environment_hash
    assert installer._source_integrity(Path(accepted["source_path"]), old) == source_hash
    assert installer.verify_installation("fixture", old, root) == accepted
    observation = "import cochem_generation_dependency as dependency; print(dependency.GENERATION)"
    assert _run([accepted["python_path"], "-I", "-B", "-c", observation], origin) == "previous"
    assert _run([prepared["python_path"], "-I", "-B", "-c", observation], origin) == "updated"
    # Verify and retain the actual old receipt before activation permits rollback.
    installer._atomic_json(old_environment.parent / "installation.json", accepted)
    installer._atomic_json(old_environment.parent / "source.json", installer._read_receipt(root / "fixture/source.json"))
    installer.activate_installation("fixture", changed, root)
    assert installer.verify_installation("fixture", changed, root) == prepared
    installer.activate_installation("fixture", old, root)
    assert installer.verify_installation("fixture", old, root) == accepted
    assert (root / "fixture/installation.json").read_bytes() == before


def test_dependency_policy_paths_do_not_depend_on_old_receipt_presence(repository):
    origin, original, root = repository
    old = dict(original, science_base_revision="a" * 40)
    changed = dict(original, science_base_revision="b" * 40)
    expected = installer._paths("fixture", changed, root)
    accepted = _legacy_install(origin, old, root)
    assert installer._paths("fixture", changed, root) == expected
    assert installer.verify_installation("fixture", old, root) == accepted


def test_legacy_environment_redirect_is_refused_before_probe(repository):
    origin, spec, root = repository
    accepted = _legacy_install(origin, spec, root)
    environment = Path(accepted["python_path"]).parent.parent
    preserved = root / "relocated-untrusted-environment"
    environment.rename(preserved)
    environment.symlink_to(preserved, target_is_directory=True)
    receipt_before = (root / "fixture/installation.json").read_bytes()
    with pytest.raises(ValueError, match="symbolic links"):
        installer._paths("fixture", spec, root)
    assert preserved.is_dir()
    assert (root / "fixture/installation.json").read_bytes() == receipt_before
