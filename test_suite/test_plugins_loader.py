"""Comprehensive physical Zero-Mock test suite for cochem_base.plugins.loader module.

Validates:
- File formatting, strict Unix LF line endings (\n), standard UTF-8 encoding, no BOM.
- Zero personal machine or user path leakage.
- Comprehensive module, class, and function docstrings.
- Module-level constants, exported symbols (__all__), and type integrity.
- CoChemStudioSpecs hook specifications and pluggy markers (hookspec, hookimpl).
- SpycFit directory resolution hierarchy (explicit path, environment variable, default fallback).
- Safe sys.path injection mechanics (non-existent path, duplicate path, valid insertion).
- PluginManager initialization, hook registration, entrypoint loading, and hook execution.
- Real hook implementation execution with custom plugin classes.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import pluggy
import pytest

import cochem_base.plugins.loader as loader_mod
from cochem_base.path_sanitization import leak_patterns
from cochem_base.plugins.loader import (
    COCHEM_SPYCFIT_ENV_VAR,
    DEFAULT_SPYCFIT_PLUGIN_RELPATH,
    PLUGIN_PROJECT_NAME,
    CoChemStudioSpecs,
    get_plugin_manager,
    hookimpl,
    hookspec,
    inject_plugin_path,
    resolve_spycfit_plugin_dir,
)


@pytest.fixture
def loader_py_path() -> Path:
    """Return the absolute path to cochem_base/plugins/loader.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "plugins" / "loader.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


# =============================================================================
# 1. File Formatting, Line Endings, and Path Sanitization
# =============================================================================


def test_loader_file_encoding_and_lf_line_endings(loader_py_path: Path) -> None:
    """Verify strictly Unix LF line endings (\n), standard UTF-8 encoding, and no BOM."""
    raw = loader_py_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in plugins/loader.py"
    assert b"\n" in raw, "Missing newline characters in plugins/loader.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in plugins/loader.py"

    content = loader_py_path.read_text(encoding="utf-8")
    assert len(content) > 100, "File content is unexpectedly small."


def test_loader_zero_personal_path_leaks(loader_py_path: Path) -> None:
    """Verify zero personal machine or local user path leakage in plugins/loader.py."""
    lines = loader_py_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in plugins/loader.py: {leaks}"


# =============================================================================
# 2. Docstrings and Architectural Contracts
# =============================================================================


def test_loader_docstrings_and_module_overview() -> None:
    """Verify comprehensive architectural docstrings on module, class, and functions."""
    # Module docstring
    mod_doc = loader_mod.__doc__
    assert mod_doc is not None and len(mod_doc) > 100
    assert "CoChemStudioSpecs" in mod_doc
    assert "cochem_studio" in mod_doc
    assert "get_plugin_manager" in mod_doc
    assert "resolve_spycfit_plugin_dir" in mod_doc
    assert "inject_plugin_path" in mod_doc

    # Class docstrings
    class_doc = CoChemStudioSpecs.__doc__
    assert class_doc is not None and len(class_doc) > 20
    assert "cochem_studio" in class_doc

    # Hook spec method docstrings
    for method_name in ("register_tabs", "register_3d_overlays", "register_menu_actions"):
        func = getattr(CoChemStudioSpecs, method_name)
        assert func.__doc__ is not None and len(func.__doc__) > 20

    # Function docstrings
    assert resolve_spycfit_plugin_dir.__doc__ is not None and len(resolve_spycfit_plugin_dir.__doc__) > 30
    assert inject_plugin_path.__doc__ is not None and len(inject_plugin_path.__doc__) > 30
    assert get_plugin_manager.__doc__ is not None and len(get_plugin_manager.__doc__) > 30


# =============================================================================
# 3. Constants, Exports, and __all__
# =============================================================================


def test_loader_constants_values_and_types() -> None:
    """Verify constant values and types."""
    assert PLUGIN_PROJECT_NAME == "cochem_studio"
    assert isinstance(PLUGIN_PROJECT_NAME, str)

    assert COCHEM_SPYCFIT_ENV_VAR == "COCHEM_SPYCFIT_DIR"
    assert isinstance(COCHEM_SPYCFIT_ENV_VAR, str)

    assert DEFAULT_SPYCFIT_PLUGIN_RELPATH == Path(".cochem") / "plugins" / "CoChem-SpycFit"
    assert isinstance(DEFAULT_SPYCFIT_PLUGIN_RELPATH, Path)

    assert isinstance(hookspec, pluggy.HookspecMarker)
    assert hookspec.project_name == PLUGIN_PROJECT_NAME

    assert isinstance(hookimpl, pluggy.HookimplMarker)
    assert hookimpl.project_name == PLUGIN_PROJECT_NAME


def test_loader_exports_and_all() -> None:
    """Verify __all__ is complete, sorted, and accurately reflects public symbols."""
    assert hasattr(loader_mod, "__all__")
    assert isinstance(loader_mod.__all__, list)
    assert loader_mod.__all__ == sorted(loader_mod.__all__)

    expected_exports = [
        "COCHEM_SPYCFIT_ENV_VAR",
        "CoChemStudioSpecs",
        "DEFAULT_SPYCFIT_PLUGIN_RELPATH",
        "PLUGIN_PROJECT_NAME",
        "get_plugin_manager",
        "hookimpl",
        "hookspec",
        "inject_plugin_path",
        "resolve_spycfit_plugin_dir",
    ]
    assert loader_mod.__all__ == expected_exports
    for sym in expected_exports:
        assert hasattr(loader_mod, sym), f"Symbol '{sym}' defined in __all__ but missing from module"


# =============================================================================
# 4. CoChemStudioSpecs Hook Specifications
# =============================================================================


def test_cochem_studio_specs_methods() -> None:
    """Verify CoChemStudioSpecs defines the required hook specifications with default returns."""
    specs = CoChemStudioSpecs()
    assert specs.register_tabs(main_window=None) == []
    assert specs.register_3d_overlays(viewer=None) == []
    assert specs.register_menu_actions(menu_bar=None) == []


# =============================================================================
# 5. SpycFit Directory Resolution
# =============================================================================


def test_resolve_spycfit_plugin_dir_custom_path(tmp_path: Path) -> None:
    """Verify explicit custom_path argument takes highest precedence."""
    custom = tmp_path / "custom_spycfit"
    resolved = resolve_spycfit_plugin_dir(custom_path=custom)
    assert resolved == custom.resolve()


def test_resolve_spycfit_plugin_dir_env_var(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify COCHEM_SPYCFIT_DIR environment variable is respected."""
    env_dir = tmp_path / "env_spycfit"
    monkeypatch.setenv(COCHEM_SPYCFIT_ENV_VAR, str(env_dir))

    resolved = resolve_spycfit_plugin_dir()
    assert resolved == env_dir.resolve()


def test_resolve_spycfit_plugin_dir_default_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify fallback to ~/.cochem/plugins/CoChem-SpycFit when no env var is set."""
    monkeypatch.delenv(COCHEM_SPYCFIT_ENV_VAR, raising=False)

    resolved = resolve_spycfit_plugin_dir()
    expected = (Path.home() / DEFAULT_SPYCFIT_PLUGIN_RELPATH).resolve()
    assert resolved == expected


# =============================================================================
# 6. sys.path Injection Mechanics
# =============================================================================


def test_inject_plugin_path_non_existent(tmp_path: Path) -> None:
    """Verify non-existent directory returns False and does not modify sys.path."""
    non_existent = tmp_path / "does_not_exist_folder"
    initial_sys_path = list(sys.path)

    result = inject_plugin_path(non_existent)
    assert result is False
    assert sys.path == initial_sys_path


def test_inject_plugin_path_success(tmp_path: Path) -> None:
    """Verify existing directory is prepended to sys.path and returns True."""
    target_dir = tmp_path / "valid_plugin_dir"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_str = str(target_dir.resolve())

    # Ensure not in sys.path before test
    if target_str in sys.path:
        sys.path.remove(target_str)

    try:
        result = inject_plugin_path(target_dir)
        assert result is True
        assert sys.path[0] == target_str

        # Subsequent call should detect duplicate and return False
        dup_result = inject_plugin_path(target_dir)
        assert dup_result is False
        assert sys.path.count(target_str) == 1
    finally:
        if target_str in sys.path:
            sys.path.remove(target_str)


# =============================================================================
# 7. PluginManager Factory and Hook Execution
# =============================================================================


def test_get_plugin_manager_creation() -> None:
    """Verify get_plugin_manager returns a configured PluginManager with registered hookspecs."""
    pm = get_plugin_manager(load_entrypoints=False)
    assert isinstance(pm, pluggy.PluginManager)
    assert pm.project_name == PLUGIN_PROJECT_NAME

    # Check hook specifications are registered
    assert hasattr(pm.hook, "register_tabs")
    assert hasattr(pm.hook, "register_3d_overlays")
    assert hasattr(pm.hook, "register_menu_actions")


def test_get_plugin_manager_with_custom_plugin_dir(tmp_path: Path) -> None:
    """Verify get_plugin_manager injects custom plugin directory if it exists."""
    custom_dir = tmp_path / "custom_silo_dir"
    custom_dir.mkdir()
    custom_str = str(custom_dir.resolve())

    try:
        pm = get_plugin_manager(load_entrypoints=False, custom_plugin_dir=custom_dir)
        assert isinstance(pm, pluggy.PluginManager)
        assert custom_str in sys.path
    finally:
        if custom_str in sys.path:
            sys.path.remove(custom_str)


def test_get_plugin_manager_hook_execution() -> None:
    """Verify custom plugin can register hook implementations and execute through manager."""
    pm = get_plugin_manager(load_entrypoints=False)

    class CustomTestPlugin:
        @hookimpl
        def register_tabs(self, main_window: Any) -> list[str]:
            return ["CustomTabA", "CustomTabB"]

        @hookimpl
        def register_3d_overlays(self, viewer: Any) -> list[str]:
            return ["OverlayActor1"]

        @hookimpl
        def register_menu_actions(self, menu_bar: Any) -> list[str]:
            return ["ActionExport"]

    plugin = CustomTestPlugin()
    pm.register(plugin)
    assert pm.is_registered(plugin)

    # Execute register_tabs hook
    tab_results = pm.hook.register_tabs(main_window=None)
    assert ["CustomTabA", "CustomTabB"] in tab_results

    # Execute register_3d_overlays hook
    overlay_results = pm.hook.register_3d_overlays(viewer=None)
    assert ["OverlayActor1"] in overlay_results

    # Execute register_menu_actions hook
    menu_results = pm.hook.register_menu_actions(menu_bar=None)
    assert ["ActionExport"] in menu_results


def test_get_plugin_manager_logging(caplog: pytest.LogCaptureFixture) -> None:
    """Verify debug logging during PluginManager initialization."""
    with caplog.at_level(logging.DEBUG, logger="cochem_base.plugins.loader"):
        _ = get_plugin_manager(load_entrypoints=False)

    records = [r for r in caplog.records if r.name == "cochem_base.plugins.loader"]
    assert any("Pluggy PluginManager initialized successfully" in r.message for r in records)


def test_get_plugin_manager_with_sequence_plugin_dirs(tmp_path: Path) -> None:
    """Verify get_plugin_manager injects multiple custom plugin directories when passed as a sequence."""
    dir1 = tmp_path / "plugin_dir_1"
    dir2 = tmp_path / "plugin_dir_2"
    dir1.mkdir()
    dir2.mkdir()
    str1 = str(dir1.resolve())
    str2 = str(dir2.resolve())

    try:
        pm = get_plugin_manager(load_entrypoints=False, custom_plugin_dir=[dir1, dir2])
        assert isinstance(pm, pluggy.PluginManager)
        assert str1 in sys.path
        assert str2 in sys.path
    finally:
        if str1 in sys.path:
            sys.path.remove(str1)
        if str2 in sys.path:
            sys.path.remove(str2)


def test_resolve_spycfit_plugin_dir_whitespace_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify whitespace-only COCHEM_SPYCFIT_DIR falls back to default directory."""
    monkeypatch.setenv(COCHEM_SPYCFIT_ENV_VAR, "   ")
    resolved = resolve_spycfit_plugin_dir()
    expected = (Path.home() / DEFAULT_SPYCFIT_PLUGIN_RELPATH).resolve()
    assert resolved == expected


def test_inject_plugin_path_normalized_deduplication(tmp_path: Path) -> None:
    """Verify inject_plugin_path avoids duplicates even when path is referenced with alternate casing."""
    target_dir = tmp_path / "norm_test_dir"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_str = str(target_dir.resolve())

    try:
        assert inject_plugin_path(target_dir) is True
        # Try injecting again with uppercase/lowercase variation
        assert inject_plugin_path(Path(target_str.lower())) is False
        assert sys.path.count(target_str) == 1
    finally:
        if target_str in sys.path:
            sys.path.remove(target_str)

