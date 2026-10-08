"""Build isolated, real Git repositories for infrastructure engineering controls.

These inputs exercise execution authority and filesystem ownership. They do not
represent molecular calculations, licensed-engine acceptance, or science data.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from ci_tools.base_ci import INFRASTRUCTURE_RING, SOURCE_TARGETS, infrastructure_paths


def git(root: Path, *args: str) -> str:
    environment = dict(os.environ)
    for key in list(environment):
        if key.startswith("GIT_"):
            environment.pop(key)
    environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                       GIT_TERMINAL_PROMPT="0")
    command = [str(Path(shutil.which("git")).resolve()), "-c", "core.hooksPath=" + os.devnull,
               "-C", str(root), *args]
    result = subprocess.run(command, env=environment, capture_output=True, text=True,
                            check=True, timeout=30)
    return result.stdout.strip()


def commit(root: Path) -> str:
    git(root, "add", "--all")
    git(root, "-c", "user.name=CoChem infrastructure control",
        "-c", "user.email=control@invalid.example", "commit", "--no-gpg-sign", "-m",
        "Reviewed engineering control source")
    return git(root, "rev-parse", "HEAD")


def review_ring(root: Path) -> None:
    """Explicit initial engineering baseline; the production reader never writes."""
    git(root, "add", "--all")
    files = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
             for name in infrastructure_paths(root)}
    (root / INFRASTRUCTURE_RING).write_text(json.dumps(
        {"schema_version": 1, "algorithm": "sha256", "files": files},
        indent=2, sort_keys=True) + "\n", encoding="utf-8")


def repository(path: Path, test_source: str) -> tuple[Path, str]:
    root = path / "reviewed-source"
    root.mkdir(parents=True)
    original = Path(__file__).resolve().parents[2]
    names = git(original, "ls-files", "ci_tools").splitlines()
    for name in names:
        source = original / name
        if source.is_file() and not source.is_symlink():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    for name in SOURCE_TARGETS:
        target = root / name
        if target.exists():
            continue
        if target.suffix == ".py":
            target.write_text('"""Engineering-only control entrypoint."""\n', encoding="utf-8")
        else:
            target.mkdir(parents=True)
            (target / "__init__.py").write_text('"""Engineering-only control namespace."""\n', encoding="utf-8")
    profile = ("[pytest]\ntestpaths = tests/control_profile\n"
               "addopts = --strict-markers --import-mode=importlib -p no:cacheprovider\n")
    for name in ("pytest.ini", "pytest-srs.ini", "ci_tools/pytest-ci.ini"):
        (root / name).write_text(profile, encoding="utf-8")
    (root / "ci_tools/source_fixtures.json").write_text(
        '{"schema_version": 1, "fixtures": []}\n', encoding="utf-8")
    (root / "ci_tools/deferred_acceptance.json").write_text(
        '{"schema_version": 1, "deferred_tests": []}\n', encoding="utf-8")
    (root / "tests/control_profile").mkdir(parents=True)
    (root / "tests/__init__.py").write_text("", encoding="utf-8")
    (root / "tests/control_profile/__init__.py").write_text("", encoding="utf-8")
    (root / "tests/control_profile/test_engineering.py").write_text(test_source, encoding="utf-8")
    git(root, "init", "--quiet")
    review_ring(root)
    return root, commit(root)
