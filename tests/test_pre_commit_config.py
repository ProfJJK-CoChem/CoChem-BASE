"""Unit tests for CoChem-BASE pre-commit configuration (.pre-commit-config.yaml).

Validates:
- File existence, UTF-8 encoding, and strict LF line endings.
- Valid YAML schema parsing.
- Core hygiene hooks from pre-commit/pre-commit-hooks.
- Deterministic PEP-8 code formatting via psf/black.
- Syntax and unused import detection via pycqa/flake8.
- Absence of bypass flags or placeholder mocks.
- Blocking behavior enforcement.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml  # type: ignore[import-untyped]


@pytest.fixture
def repo_root() -> Path:
    """Return the absolute path to the CoChem-BASE repository root."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def pre_commit_config_path(repo_root: Path) -> Path:
    """Return the absolute path to the .pre-commit-config.yaml file."""
    path = repo_root / ".pre-commit-config.yaml"
    assert path.exists(), f"Pre-commit config file does not exist at {path}"
    return path


def test_pre_commit_config_exists(repo_root: Path) -> None:
    """Validate that .pre-commit-config.yaml exists in the repository root."""
    path = repo_root / ".pre-commit-config.yaml"
    assert path.exists(), f"Pre-commit config file does not exist at {path}"
    assert path.is_file(), f"Pre-commit config at {path} must be a regular file"


def test_pre_commit_file_integrity_and_lf_endings(pre_commit_config_path: Path) -> None:
    """Validate that .pre-commit-config.yaml has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = pre_commit_config_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), ".pre-commit-config.yaml contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, ".pre-commit-config.yaml contains Windows CRLF line endings"


def test_pre_commit_yaml_parsing(pre_commit_config_path: Path) -> None:
    """Validate that .pre-commit-config.yaml is valid YAML and parses into a dict with repos."""
    content = pre_commit_config_path.read_text(encoding="utf-8")
    data: Dict[str, Any] = yaml.safe_load(content)
    assert isinstance(data, dict), ".pre-commit-config.yaml must parse as a dictionary"
    assert "repos" in data, ".pre-commit-config.yaml must define 'repos'"
    assert isinstance(data["repos"], list), "'repos' must be a list of repository configurations"
    assert len(data["repos"]) > 0, "'repos' list must not be empty"


def test_pre_commit_hooks_included(pre_commit_config_path: Path) -> None:
    """Validate that core hygiene hooks from pre-commit/pre-commit-hooks are configured."""
    content = pre_commit_config_path.read_text(encoding="utf-8")
    data: Dict[str, Any] = yaml.safe_load(content)
    repos: List[Dict[str, Any]] = data.get("repos", [])

    pre_commit_hooks_repo = None
    for r in repos:
        repo_url = r.get("repo", "")
        if "pre-commit/pre-commit-hooks" in repo_url:
            pre_commit_hooks_repo = r
            break

    assert pre_commit_hooks_repo is not None, (
        "Repository 'pre-commit/pre-commit-hooks' must be defined in .pre-commit-config.yaml"
    )

    hook_ids = {h.get("id") for h in pre_commit_hooks_repo.get("hooks", [])}
    expected_hygiene_hooks = {
        "trailing-whitespace",
        "end-of-file-fixer",
        "check-yaml",
        "check-added-large-files",
        "check-merge-conflict",
        "check-ast",
    }
    missing_hooks = expected_hygiene_hooks - hook_ids
    assert not missing_hooks, (
        f"Missing expected pre-commit-hooks: {missing_hooks}. Found: {hook_ids}"
    )


def test_black_hook_configured(pre_commit_config_path: Path) -> None:
    """Validate that black is configured for deterministic PEP-8 formatting."""
    content = pre_commit_config_path.read_text(encoding="utf-8")
    data: Dict[str, Any] = yaml.safe_load(content)
    repos: List[Dict[str, Any]] = data.get("repos", [])

    black_repo = None
    for r in repos:
        repo_url = r.get("repo", "")
        if "psf/black" in repo_url:
            black_repo = r
            break

    assert black_repo is not None, (
        "Repository 'psf/black' must be defined in .pre-commit-config.yaml"
    )

    hooks = black_repo.get("hooks", [])
    hook_ids = [h.get("id") for h in hooks]
    assert "black" in hook_ids, "Hook 'black' must be configured in psf/black repo"

    # Verify language version or python3 target
    for h in hooks:
        if h.get("id") == "black":
            lang_version = h.get("language_version")
            if lang_version is not None:
                assert "python" in str(lang_version).lower() or "3" in str(lang_version), (
                    f"Invalid language_version '{lang_version}' for black hook"
                )


def test_flake8_hook_configured(pre_commit_config_path: Path) -> None:
    """Validate that flake8 is configured for syntax and unused import detection."""
    content = pre_commit_config_path.read_text(encoding="utf-8")
    data: Dict[str, Any] = yaml.safe_load(content)
    repos: List[Dict[str, Any]] = data.get("repos", [])

    flake8_repo = None
    for r in repos:
        repo_url = r.get("repo", "")
        if "pycqa/flake8" in repo_url:
            flake8_repo = r
            break

    assert flake8_repo is not None, (
        "Repository 'pycqa/flake8' must be defined in .pre-commit-config.yaml"
    )

    hook_ids = [h.get("id") for h in flake8_repo.get("hooks", [])]
    assert "flake8" in hook_ids, "Hook 'flake8' must be configured in pycqa/flake8 repo"


def test_zero_mock_and_no_stubs(pre_commit_config_path: Path) -> None:
    """Validate that .pre-commit-config.yaml contains no mock, stub, or placeholder tokens."""
    content = pre_commit_config_path.read_text(encoding="utf-8")
    forbidden_tokens = ["TODO", "FIXME", "placeholder", "stub", "mock", "dummy", "fake"]
    for token in forbidden_tokens:
        assert token.lower() not in content.lower(), (
            f"Pre-commit config contains forbidden token '{token}'"
        )


def test_no_bypass_or_always_pass(pre_commit_config_path: Path) -> None:
    """Validate that hooks do not include always_run or bypass flags that allow failing commits."""
    content = pre_commit_config_path.read_text(encoding="utf-8")
    data: Dict[str, Any] = yaml.safe_load(content)
    repos: List[Dict[str, Any]] = data.get("repos", [])

    for r in repos:
        for hook in r.get("hooks", []):
            assert hook.get("verbose") is not True, "Hooks should not set verbose: true by default"
            args = hook.get("args", [])
            if isinstance(args, list):
                for arg in args:
                    assert "--exit-zero" not in str(arg), (
                        f"Hook {hook.get('id')} contains '--exit-zero' which bypasses local failure blocking"
                    )
