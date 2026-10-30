"""Inspect real release artifacts for the BASE/canonical-provider boundary."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile

import pytest


@pytest.fixture(scope="module")
def release_artifacts(tmp_path_factory):
    root = Path(__file__).resolve().parents[2]
    work = tmp_path_factory.mktemp("base-release-ownership")
    source = work / "source"
    shutil.copytree(root, source, ignore=shutil.ignore_patterns(
        ".git", "build", "dist", "*.egg-info", "__pycache__", ".pytest_cache", ".venv",
    ))
    environment = {key: value for key, value in os.environ.items()
                   if not any(word in key.upper() for word in
                              ("TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "API_KEY"))}
    subprocess.run([sys.executable, "-m", "build", "--no-isolation", "--outdir",
                    str(work / "dist"), str(source)], cwd=work, env=environment,
                   capture_output=True, text=True, check=True, timeout=120)
    return work / "dist"


def test_base_wheel_does_not_publish_canonical_module_namespaces(release_artifacts):
    wheel, = release_artifacts.glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        members = set(archive.namelist())
    foreign = ("cochem_topos/", "cochem_torq/", "cochem/topos/", "cochem/torq/")
    assert not sorted(name for name in members if name.startswith(foreign))
    for owned in ("cochem_base/intake/structure_formats.py",
                  "cochem_base/intake/conformer_engine.py",
                  "cochem_base/intake/conformer_deduplication.py",
                  "cochem_base/geometry/nuclide_geometry.py",
                  "scripts/manage_modules.py", "scripts/module_adapter_torq.py"):
        assert owned in members


def test_base_source_distribution_excludes_obsolete_provider_copies(release_artifacts):
    bundle, = release_artifacts.glob("*.tar.gz")
    with tarfile.open(bundle) as archive:
        members = {name.partition("/")[2] for name in archive.getnames()}
    foreign = ("cochem_topos/", "src/cochem_torq/", "cochem/topos/",
               "src/cochem/topos/", "cochem/torq/")
    assert not sorted(name for name in members if name.startswith(foreign))
    assert "src/cochem_base/intake/conformer_engine.py" in members
