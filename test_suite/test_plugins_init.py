"""Comprehensive physical Zero-Mock test suite for cochem_base.plugins subsystem.

Validates lazy loading architecture (PEP 562), exported symbols, type hinting integrity,
AttributeError handling, __dir__ reflection, LF line endings, path sanitization,
CorePlugin hook implementation, and pluggy PluginManager lifecycle.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pluggy
import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

import cochem_base.plugins as plugins
from cochem_base.path_sanitization import leak_patterns
from cochem_base.plugins.internal import CorePlugin
from cochem_base.plugins.loader import CoChemStudioSpecs, get_plugin_manager, hookimpl, hookspec


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Ensure a singleton QApplication instance is active for Qt-based plugin tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def plugins_init_path() -> Path:
    """Return the absolute path to cochem_base/plugins/__init__.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "plugins" / "__init__.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_encoding_and_lf_line_endings(plugins_init_path: Path) -> None:
    """Verify strictly Unix LF line endings (\n), standard UTF-8 encoding, and no BOM."""
    raw = plugins_init_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in plugins/__init__.py"
    assert b"\n" in raw, "Missing newline characters in plugins/__init__.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in plugins/__init__.py"

    content = plugins_init_path.read_text(encoding="utf-8")
    assert len(content) > 200, "File content is unexpectedly small."


def test_zero_personal_path_leaks(plugins_init_path: Path) -> None:
    """Verify zero personal machine or local user path leakage in plugins/__init__.py."""
    lines = plugins_init_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in plugins/__init__.py: {leaks}"


def test_docstring_and_architectural_overview(plugins_init_path: Path) -> None:
    """Verify comprehensive architectural docstring is present on the module."""
    doc = plugins.__doc__
    assert doc is not None and len(doc) > 100
    assert "CoChemStudioSpecs" in doc
    assert "CorePlugin" in doc
    assert "get_plugin_manager" in doc
    assert "hookimpl" in doc
    assert "hookspec" in doc


def test_module_all_exports_present() -> None:
    """Verify __all__ is a sorted list of non-empty public symbols."""
    assert hasattr(plugins, "__all__")
    assert isinstance(plugins.__all__, list)
    assert plugins.__all__ == sorted(plugins.__all__)

    expected_symbols = [
        "CoChemStudioSpecs",
        "CorePlugin",
        "get_plugin_manager",
        "hookimpl",
        "hookspec",
    ]
    assert plugins.__all__ == expected_symbols
    for sym in expected_symbols:
        assert sym in plugins.__all__, f"Symbol '{sym}' missing from plugins.__all__"


@pytest.mark.parametrize(
    "symbol_name",
    [
        "CoChemStudioSpecs",
        "CorePlugin",
        "get_plugin_manager",
        "hookimpl",
        "hookspec",
    ],
)
def test_lazy_attribute_resolution(symbol_name: str) -> None:
    """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
    attr = getattr(plugins, symbol_name)
    assert attr is not None
    # Verify cached in module dictionary
    assert symbol_name in plugins.__dict__


def test_invalid_attribute_access_raises_attribute_error() -> None:
    """Verify accessing undefined attributes raises AttributeError with descriptive message."""
    with pytest.raises(AttributeError) as exc_info:
        _ = plugins.NonExistentPluginSymbol
    assert "module 'cochem_base.plugins' has no attribute 'NonExistentPluginSymbol'" in str(exc_info.value)


def test_dir_reflection_contains_all_and_globals() -> None:
    """Verify __dir__() lists all public exports and module globals."""
    dir_symbols = dir(plugins)
    for sym in plugins.__all__:
        assert sym in dir_symbols, f"Symbol '{sym}' missing from dir(plugins)"
    assert "__all__" in dir_symbols
    assert "__getattr__" in dir_symbols
    assert "__dir__" in dir_symbols


def test_plugin_manager_lifecycle_and_hooks() -> None:
    """Verify get_plugin_manager configures pluggy with CoChemStudioSpecs."""
    pm = plugins.get_plugin_manager()
    assert isinstance(pm, pluggy.PluginManager)
    assert hasattr(pm.hook, "register_tabs")
    assert hasattr(pm.hook, "register_3d_overlays")
    assert hasattr(pm.hook, "register_menu_actions")


def test_core_plugin_registration(qapp: QApplication) -> None:
    """Verify CorePlugin tab registration hook registers standard backbone tabs on physical QMainWindow."""
    plugin = plugins.CorePlugin()
    main_window = QMainWindow()
    main_window.tabs = QTabWidget(main_window)  # type: ignore[attr-defined]

    try:
        assert main_window.tabs.count() == 0
        plugin.register_tabs(main_window)
        assert main_window.tabs.count() == 3
        added_titles = [main_window.tabs.tabText(i) for i in range(main_window.tabs.count())]
        assert "BASE - Hardware Orchestrator" in added_titles
        assert "TOPOS - Combinatorial Engine" in added_titles
        assert "TORQ - Quantum Resonance" in added_titles
    finally:
        main_window.close()
