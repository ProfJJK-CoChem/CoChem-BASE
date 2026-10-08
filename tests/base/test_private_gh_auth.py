"""Actual process environment selection; no provider or credential simulation.

Inherited credentials are never printed or inspected outside ordinary environment
copying. When a token variable is absent, an empty variable tests name handling;
it is not an authentication credential and no GitHub command is executed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "codespaces,actions,mode,retained",
    [
        ("true", "false", "auto", False),
        ("false", "false", "auto", True),
        ("true", "false", "stored-cli", False),
        ("false", "false", "stored-cli", False),
        ("true", "false", "environment", True),
        ("true", "true", "auto", True),
        ("true", "true", "stored-cli", True),
        ("true", "true", "environment", True),
        ("true", "true", "invalid-local-override", True),
    ],
)
def test_real_subprocess_authentication_selection_preserves_parent_and_actions(
    codespaces,
    actions,
    mode,
    retained,
):
    environment = os.environ.copy()
    environment.update(CODESPACES=codespaces, GITHUB_ACTIONS=actions)
    environment["COCHEM_PRIVATE_GH_AUTH"] = mode
    environment.setdefault("GH_TOKEN", "")
    environment.setdefault("GITHUB_TOKEN", "")
    environment["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
    code = """
import os, sys
from scripts.private_gh_auth import private_gh_environment
from scripts.private_engine_assets import _gh_environment
before = dict(os.environ)
retained = sys.argv[1] == 'true'
for selected in (private_gh_environment(), _gh_environment()):
    for name in ('GH_TOKEN', 'GITHUB_TOKEN'):
        assert (name in selected) == retained
        if retained:
            assert selected[name] == before[name]
    assert selected['CODESPACES'] == before['CODESPACES']
    assert selected['GITHUB_ACTIONS'] == before['GITHUB_ACTIONS']
assert dict(os.environ) == before
"""
    subprocess.run(
        [sys.executable, "-c", code, str(retained).lower()],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_invalid_local_mode_fails_before_any_provider_process():
    environment = os.environ.copy()
    environment.update(
        CODESPACES="true",
        GITHUB_ACTIONS="false",
        COCHEM_PRIVATE_GH_AUTH="invalid-local-override",
        PYTHONPATH=str(ROOT / "src") + os.pathsep + str(ROOT),
    )
    code = """
from scripts.private_gh_auth import private_gh_environment
from scripts.private_engine_assets import _gh_environment
for select in (private_gh_environment, _gh_environment):
    try:
        select()
    except ValueError as error:
        assert str(error) == 'COCHEM_PRIVATE_GH_AUTH must be auto, stored-cli, or environment.'
    else:
        raise AssertionError('Invalid local authentication mode was accepted')
"""
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.parametrize("actions", ["true", "false"])
def test_private_asset_bootstrap_uses_only_checkout_root_and_standard_library(actions):
    """Native asset setup precedes BASE installation in the composite action."""
    environment = os.environ.copy()
    environment.update(
        CODESPACES="true",
        GITHUB_ACTIONS=actions,
        COCHEM_PRIVATE_GH_AUTH="stored-cli",
    )
    environment.setdefault("GH_TOKEN", "")
    environment.setdefault("GITHUB_TOKEN", "")
    code = """
import importlib.util
import os
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
assert root / 'src' not in [Path(path) for path in sys.path]
assert not any('site-packages' in path or 'dist-packages' in path for path in sys.path)
assert importlib.util.find_spec('cochem_base') is None
from scripts.consume_private_engine_asset import load_workflow_receipt
from scripts.private_engine_assets import _gh_environment
from scripts.private_gh_auth import private_gh_environment

assert callable(load_workflow_receipt)
before = dict(os.environ)
retained = before['GITHUB_ACTIONS'] == 'true'
for selected in (private_gh_environment(), _gh_environment()):
    for name in ('GH_TOKEN', 'GITHUB_TOKEN'):
        assert (name in selected) == retained
        if retained:
            assert selected[name] == before[name]
assert dict(os.environ) == before
assert not any(name == 'cochem_base' or name.startswith('cochem_base.') for name in sys.modules)
"""
    subprocess.run(
        [sys.executable, "-I", "-S", "-c", code, str(ROOT)],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
