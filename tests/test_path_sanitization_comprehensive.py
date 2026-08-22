"""Comprehensive Zero-Mock Physical Test Suite for cochem_base.path_sanitization.

Validates all functionality:
- Directory resolution (agents and agent templates) with and without environment overrides
- Placeholder token generation and custom mappings
- Path variant generation (native, posix, escaped backslashes, trailing slashes)
- Content sanitization with priority ordering (longest paths first)
- Leak pattern compilation and detection
- Line-accurate leak finding and boolean sanitization checks
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterator

import pytest

from cochem_base.path_sanitization import (
    find_path_leaks,
    get_agent_templates_dir,
    get_agents_dir,
    is_sanitized,
    leak_patterns,
    path_variants,
    placeholder_values,
    sanitize_local_paths,
)


def test_get_agents_dir_default() -> None:
    """Verify get_agents_dir returns expected .agents path under base root by default."""
    agents_dir = get_agents_dir()
    assert isinstance(agents_dir, Path)
    assert agents_dir.name == ".agents"
    assert agents_dir.is_dir()


def test_get_agents_dir_with_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_agents_dir respects COCHEM_AGENTS_DIR environment variable."""
    custom_agents = tmp_path / "custom_agents"
    custom_agents.mkdir()
    monkeypatch.setenv("COCHEM_AGENTS_DIR", str(custom_agents))

    resolved = get_agents_dir()
    assert resolved == custom_agents.resolve()


def test_get_agents_dir_with_base_root_param(tmp_path: Path) -> None:
    """Verify get_agents_dir respects explicit base_root argument."""
    custom_base = tmp_path / "custom_base"
    custom_base.mkdir()
    resolved = get_agents_dir(base_root=custom_base)
    assert resolved == custom_base.resolve() / ".agents"


def test_get_agent_templates_dir_default() -> None:
    """Verify get_agent_templates_dir defaults to user's .gemini/config/agents directory."""
    templates_dir = get_agent_templates_dir()
    assert isinstance(templates_dir, Path)
    expected_suffix = Path(".gemini") / "config" / "agents"
    assert str(templates_dir).endswith(str(expected_suffix))


def test_get_agent_templates_dir_with_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_agent_templates_dir respects COCHEM_GEMINI_AGENTS_DIR environment variable."""
    custom_templates = tmp_path / "custom_templates"
    custom_templates.mkdir()
    monkeypatch.setenv("COCHEM_GEMINI_AGENTS_DIR", str(custom_templates))

    resolved = get_agent_templates_dir()
    assert resolved == custom_templates.resolve()


def test_placeholder_values_keys() -> None:
    """Verify canonical placeholder tokens exist in placeholder_values dictionary."""
    placeholders = placeholder_values()
    assert "<USER_HOME>" in placeholders
    assert "<COCHEM_WORKSPACE>" in placeholders
    assert "<GDRIVE_ROOT>" in placeholders

    for token, p in placeholders.items():
        assert token.startswith("<") and token.endswith(">")
        assert isinstance(p, Path)
        assert p.is_absolute()


def test_placeholder_values_custom_mappings(tmp_path: Path) -> None:
    """Verify custom mappings are properly merged into placeholder_values."""
    custom_path = tmp_path / "custom_scratch"
    custom_path.mkdir()

    custom_mappings: dict[str, str | Path] = {
        "<CUSTOM_SCRATCH>": custom_path,
        "<RELATIVE_TEST>": "relative/subfolder",
    }
    placeholders = placeholder_values(custom_mappings=custom_mappings)

    assert "<CUSTOM_SCRATCH>" in placeholders
    assert placeholders["<CUSTOM_SCRATCH>"] == custom_path.resolve()
    assert "<RELATIVE_TEST>" in placeholders
    assert placeholders["<RELATIVE_TEST>"].is_absolute()


def test_path_variants_generation() -> None:
    """Verify path_variants generates native, posix, escaped, and trailing slash forms."""
    test_path = Path("C:/Users/testuser/workspace/repo")
    variants = path_variants(test_path)

    assert isinstance(variants, tuple)
    assert len(variants) >= 2

    # Should contain native and posix forms
    assert str(test_path) in variants or test_path.as_posix() in variants

    # Sorted by length descending
    lengths = [len(v) for v in variants]
    assert lengths == sorted(lengths, reverse=True)


def test_path_variants_escaped_backslashes() -> None:
    """Verify path_variants includes double-escaped backslash variant for Windows paths."""
    win_path = Path("D:\\CoChem\\Repo")
    variants = path_variants(win_path)

    # Should include escaped backslash representation
    if "\\" in str(win_path):
        escaped = str(win_path).replace("\\", "\\\\")
        assert escaped in variants


def test_sanitize_local_paths_basic() -> None:
    """Verify sanitize_local_paths correctly replaces local paths with canonical tokens."""
    placeholders = placeholder_values()
    workspace_path = placeholders["<COCHEM_WORKSPACE>"]

    raw_text = f"The workspace is located at {workspace_path}/subfolder/module.py"
    sanitized = sanitize_local_paths(raw_text)

    assert str(workspace_path) not in sanitized
    assert "<COCHEM_WORKSPACE>/subfolder/module.py" in sanitized or "<COCHEM_WORKSPACE>" in sanitized


def test_sanitize_local_paths_case_insensitive() -> None:
    """Verify sanitize_local_paths performs case-insensitive matching."""
    placeholders = placeholder_values()
    workspace_path = str(placeholders["<COCHEM_WORKSPACE>"])

    # Test lowercase version
    lower_path = workspace_path.lower()
    raw_text = f"File is at {lower_path}/test.py"
    sanitized = sanitize_local_paths(raw_text)

    assert lower_path not in sanitized
    assert "<COCHEM_WORKSPACE>" in sanitized


def test_sanitize_local_paths_priority_ordering(tmp_path: Path) -> None:
    """Verify longer/child paths are substituted before shorter/parent paths."""
    parent_dir = tmp_path / "parent"
    child_dir = parent_dir / "child" / "deep"
    child_dir.mkdir(parents=True)

    custom_placeholders = {
        "<PARENT>": parent_dir,
        "<CHILD>": child_dir,
    }

    raw_text = f"Target: {child_dir}/file.txt"
    sanitized = sanitize_local_paths(raw_text, custom_placeholders=custom_placeholders)

    assert "<CHILD>/file.txt" in sanitized
    assert "<PARENT>/child/deep/file.txt" not in sanitized


def test_leak_patterns_compilation() -> None:
    """Verify leak_patterns returns compiled regex patterns and tokens."""
    patterns = leak_patterns()
    assert isinstance(patterns, list)
    assert len(patterns) > 0

    for pat, token in patterns:
        assert isinstance(pat, re.Pattern)
        assert isinstance(token, str)
        assert token.startswith("<") and token.endswith(">")


def test_find_path_leaks_clean_content() -> None:
    """Verify find_path_leaks returns empty list when content has no leaks."""
    clean_text = """
    # Clean Document
    The workspace root is <COCHEM_WORKSPACE>/CoChem-BASE.
    Home is <USER_HOME>.
    Shared storage is <GDRIVE_ROOT>.
    """
    leaks = find_path_leaks(clean_text)
    assert leaks == []
    assert is_sanitized(clean_text) is True


def test_find_path_leaks_detected() -> None:
    """Verify find_path_leaks accurately reports line numbers and leaked tokens."""
    placeholders = placeholder_values()
    user_home = placeholders["<USER_HOME>"]

    leaky_text = f"""Line 1: clean header
Line 2: Leaked home path {user_home}/secret_keys.txt
Line 3: clean footer
"""
    leaks = find_path_leaks(leaky_text)
    assert len(leaks) >= 1
    line_num, token, line_content = leaks[0]
    assert line_num == 2
    assert token == "<USER_HOME>"
    assert str(user_home) in line_content
    assert is_sanitized(leaky_text) is False


def test_is_sanitized_utility() -> None:
    """Verify is_sanitized returns True for clean text and False for text with path leaks."""
    placeholders = placeholder_values()
    workspace = placeholders["<COCHEM_WORKSPACE>"]

    assert is_sanitized("Clean text with token <COCHEM_WORKSPACE>") is True
    assert is_sanitized(f"Leaked text with {workspace}") is False
