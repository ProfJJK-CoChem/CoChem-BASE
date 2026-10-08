"""Real source/wheel membership boundaries; no package build or science fixture."""
from __future__ import annotations

import configparser
import hashlib
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from scripts import mandatory_ecosystem as ecosystem


def test_catalog_bootstrap_hashes_match_the_reviewed_source_bytes():
    """Git archive preserves CRLF blobs; normalized text is a different payload."""
    from scripts.manage_modules import load_manifest

    source = Path(ecosystem.__file__).resolve().parents[1]
    authority = ecosystem.validate_spec(load_manifest()["modules"]["topos"])
    actual = {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
              for name in authority["base_bootstrap_sha256"]}
    assert actual == authority["base_bootstrap_sha256"]


def test_catalog_complete_source_anchor_matches_the_reviewed_tracked_snapshot(tmp_path):
    """Exclude generated build/cache metadata without dropping reviewed source."""
    from scripts.manage_modules import _build_env, load_manifest

    source = Path(ecosystem.__file__).resolve().parents[1]
    tracked = subprocess.check_output(
        ["git", "-C", str(source), "ls-files", "--stage", "-z"],
        env=_build_env(), timeout=30,
    ).decode().split("\0")
    snapshot = tmp_path / "reviewed-source"
    snapshot.mkdir()
    for entry in filter(None, tracked):
        identity, name = entry.split("\t", 1)
        mode, _object_id, stage = identity.split()
        assert stage == "0" and mode in {"100644", "100755"}
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source / name).read_bytes())
        target.chmod(0o755 if mode == "100755" else 0o644)
    authority = ecosystem.validate_spec(load_manifest()["modules"]["topos"])
    observed = ecosystem.base_source_content_identity(snapshot)
    assert observed["sha256"] == authority["base_source_content_sha256"]


def test_default_acceptance_selects_critical_installer_and_export_boundaries():
    config = configparser.ConfigParser()
    config.read(Path(ecosystem.__file__).resolve().parents[1] / "pytest.ini")
    selected = set(config["pytest"]["testpaths"].split())
    assert {
        "tests/base/test_mandatory_source_ownership.py",
        "tests/base/test_topos_module_surfaces.py",
        "tests/base/test_export_topos_evidence.py",
        "tests/base/test_export_topos_bookkeeping.py",
    } <= selected


@pytest.fixture
def source_and_wheel(tmp_path):
    """Retain actual trusted bootstrap bytes with one inert owned Python module."""
    candidate = Path(ecosystem.__file__).resolve().parents[1]
    source = tmp_path / "source"
    source.mkdir()
    names = ("cli.py", "pyproject.toml", "MANIFEST.in", "requirements.txt", "requirements-ui.txt")
    catalog = source / "scripts/module-distribution.json"
    catalog.parent.mkdir(parents=True)
    shutil.copyfile(candidate / "scripts/module-distribution.json", catalog)
    hashes = {}
    for name in names:
        shutil.copyfile(candidate / name, source / name)
        hashes[name] = hashlib.sha256((source / name).read_bytes()).hexdigest()
    module = source / "src/cochem_base/infrastructure.py"
    module.parent.mkdir(parents=True)
    module.write_text("# Inert membership fixture, never imported.\n")
    wheel = tmp_path / "base-membership.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("cochem_base/infrastructure.py", module.read_bytes())
        archive.writestr("cli.py", (source / "cli.py").read_bytes())
        archive.writestr("scripts/module-distribution.json", catalog.read_bytes())
    authority = {"base_bootstrap_sha256": hashes,
                 "base_source_content_sha256": ecosystem.base_source_content_identity(source)["sha256"]}
    ecosystem.verify_base_source(source, wheel, authority)
    return source, wheel, authority


@pytest.mark.parametrize("folder", [
    "src/cochem_base", "src/cochem", "scripts",
    "src/cochem_torq", "src/cochem_geom", "src/cochem_ml", "src/cochem_mobile",
    "cochem_topos", "frontend", "ui", "cochem/torq", "cochem/ml/models",
    "src/cochem_base_unowned", "cochem_base_unowned",
])
def test_new_source_module_is_rejected_before_bootstrap(source_and_wheel, folder):
    source, wheel, authority = source_and_wheel
    unowned = source / folder / "infrastructure_extra.py"
    unowned.parent.mkdir(parents=True, exist_ok=True)
    unowned.write_text("raise RuntimeError('Unowned infrastructure must never execute')\n")
    with pytest.raises(ValueError, match="Complete BASE source content|unowned executable"):
        ecosystem.verify_base_source(source, wheel, authority)


@pytest.mark.parametrize("suffix", [".pyw", ".pyc", ".pyo", ".so", ".pyd", ".pth"])
def test_additional_importable_payload_is_not_silently_ignored(source_and_wheel, suffix):
    source, wheel, authority = source_and_wheel
    unowned = source / "src/cochem_base" / ("unowned" + suffix)
    unowned.write_bytes(b"Nonexecuted infrastructure membership boundary\n")
    with pytest.raises(ValueError, match="Complete BASE source content|unowned executable"):
        ecosystem.verify_base_source(source, wheel, authority)


def test_declared_bootstrap_module_requires_wheel_ownership(source_and_wheel):
    source, wheel, authority = source_and_wheel
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("cochem_base/infrastructure.py", (source / "src/cochem_base/infrastructure.py").read_bytes())
        archive.writestr("scripts/module-distribution.json", (source / "scripts/module-distribution.json").read_bytes())
    with pytest.raises(ValueError, match="Complete BASE source content|unowned executable"):
        ecosystem.verify_base_source(source, wheel, authority)


def test_mapping_preserves_independently_anchored_legacy_source(source_and_wheel):
    source, wheel, authority = source_and_wheel
    legacy = source / "cochem/core/legacy.py"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("# Independently pinned legacy source, never executed.\n")
    authority["base_source_content_sha256"] = ecosystem.base_source_content_identity(source)["sha256"]
    ecosystem.verify_base_source(source, wheel, authority)
    # The actual trusted mapping cochem=src/cochem remains inside the guard.
    selected = source / "src/cochem/core/legacy.py"
    selected.parent.mkdir(parents=True)
    selected.write_bytes(legacy.read_bytes())
    with pytest.raises(ValueError, match="Complete BASE source content|unowned executable"):
        ecosystem.verify_base_source(source, wheel, authority)


def test_nonpackaged_files_are_also_bound_to_complete_source_authority(source_and_wheel):
    source, wheel, authority = source_and_wheel
    for name in ("tests/infrastructure.py", ".trash/infrastructure.py"):
        path = source / name
        path.parent.mkdir(parents=True)
        path.write_text("# Independently anchored nonpackage source, never imported.\n")
    authority["base_source_content_sha256"] = ecosystem.base_source_content_identity(source)["sha256"]
    ecosystem.verify_base_source(source, wheel, authority)
    path.write_text("# Changed after complete source authorization.\n")
    with pytest.raises(ValueError, match="Complete BASE source content"):
        ecosystem.verify_base_source(source, wheel, authority)


@pytest.mark.parametrize("kind", ["module", "mapped-folder", "discovered-folder", "source-root", "bootstrap"])
def test_redirected_source_paths_are_rejected(source_and_wheel, tmp_path, kind):
    source, wheel, authority = source_and_wheel
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "extra.py").write_text("# External infrastructure, never imported.\n")
    if kind == "module":
        (source / "src/cochem_base/extra.py").symlink_to(outside / "extra.py")
    elif kind == "mapped-folder":
        (source / "frontend").symlink_to(outside, target_is_directory=True)
    elif kind == "discovered-folder":
        (source / "cochem_base_extra").symlink_to(outside, target_is_directory=True)
    elif kind == "source-root":
        alias = tmp_path / "alias"
        alias.symlink_to(source, target_is_directory=True)
        source = alias
    else:
        payload = source / "pyproject.toml"
        retained = outside / "pyproject.toml"
        payload.rename(retained)
        payload.symlink_to(retained)
    with pytest.raises(ValueError, match="redirected|bootstrap differs"):
        ecosystem.verify_base_source(source, wheel, authority)


@pytest.mark.parametrize("name", ["setup.py", "setup.cfg", "sitecustomize.py", "usercustomize.py"])
def test_unreviewed_top_level_build_customization_stays_rejected(source_and_wheel, name):
    source, wheel, authority = source_and_wheel
    (source / name).write_text("# Unreviewed build hook, never executed.\n")
    authority["base_source_content_sha256"] = ecosystem.base_source_content_identity(source)["sha256"]
    with pytest.raises(ValueError, match="build customization"):
        ecosystem.verify_base_source(source, wheel, authority)


@pytest.mark.parametrize("name", [
    "json.py", "src/json.py", "src/pathlib.py", "pip.py", "pip/__init__.py", "cochem/__init__.py",
])
def test_bootstrap_import_shadow_is_rejected_against_preexisting_source_anchor(source_and_wheel, name):
    source, wheel, authority = source_and_wheel
    path = source / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Inert import-shadow admission probe; never imported.\n")
    with pytest.raises(ValueError, match="Complete BASE source content"):
        ecosystem.verify_base_source(source, wheel, authority)


def test_self_catalog_exclusion_still_requires_independent_wheel_bytes(source_and_wheel):
    source, wheel, authority = source_and_wheel
    catalog = source / "scripts/module-distribution.json"
    catalog.write_text('{"self_asserted":"not the independently owned catalog"}\n')
    assert ecosystem.base_source_content_identity(source)["sha256"] == authority["base_source_content_sha256"]
    with pytest.raises(ValueError, match="catalog differs from the independently owned wheel"):
        ecosystem.verify_base_source(source, wheel, authority)


@pytest.mark.parametrize("change", ["bytes", "mode", "missing", "extra-hidden", "extra-data"])
def test_full_source_membership_and_mode_are_bound(source_and_wheel, change):
    source, wheel, authority = source_and_wheel
    path = source / "MANIFEST.in"
    if change == "bytes":
        path.write_bytes(path.read_bytes() + b"# altered after authority\n")
    elif change == "mode":
        path.chmod(path.stat().st_mode ^ 0o100)
    elif change == "missing":
        path.unlink()
    else:
        path = source / (".ignored-loader" if change == "extra-hidden" else "unowned-data.json")
        path.write_text("nonexecuted source completeness marker\n")
    with pytest.raises(ValueError, match="Complete BASE source content"):
        ecosystem.verify_base_source(source, wheel, authority)


@pytest.mark.parametrize("value", [None, True, {}, "", "version-only", "a" * 63])
def test_v2_catalog_requires_typed_complete_source_identity(value):
    import copy

    from scripts.manage_modules import load_manifest

    spec = copy.deepcopy(load_manifest()["modules"]["topos"])
    if value is None:
        del spec["mandatory_ecosystem"]["base_source_content_sha256"]
    else:
        spec["mandatory_ecosystem"]["base_source_content_sha256"] = value
    with pytest.raises(ValueError, match="SHA-256"):
        ecosystem.validate_spec(spec)


def test_legacy_catalog_cannot_opt_out_of_complete_source_identity():
    import copy

    from scripts.manage_modules import load_manifest

    spec = copy.deepcopy(load_manifest()["modules"]["topos"])
    spec["mandatory_ecosystem"]["schema_version"] = "cochem.mandatory-ecosystem-catalog/1"
    with pytest.raises(ValueError, match="reviewed typed"):
        ecosystem.validate_spec(spec)


@pytest.mark.parametrize("change", ["tracked", "untracked", "ignored"])
def test_real_git_source_must_be_clean_before_hashing(source_and_wheel, change):
    """Real local Git only; never install or execute fixture source."""
    from scripts.manage_modules import _build_env

    source, wheel, authority = source_and_wheel
    def git(*args):
        subprocess.run(["git", "-C", str(source), *args], env=_build_env(),
                       check=True, capture_output=True, text=True, timeout=30)
    git("init")
    git("add", ".")
    git("-c", "user.name=CoChem source-boundary test", "-c", "user.email=source@test.invalid",
        "commit", "-m", "Actual local source membership fixture")
    ecosystem.verify_base_source(source, wheel, authority)
    if change == "tracked":
        (source / "cli.py").write_text("# Changed tracked bootstrap bytes, never executed.\n")
    else:
        if change == "ignored":
            (source / ".git/info/exclude").write_text("extra-input.txt\n")
        (source / "extra-input.txt").write_text("unreviewed input\n")
    with pytest.raises(ValueError, match="clean tracked checkout"):
        ecosystem.verify_base_source(source, wheel, authority)
