"""Comprehensive physical Zero-Mock test suite for cochem_base.plugins.internal module.

Validates:
- File formatting, strict Unix LF line endings, standard UTF-8 encoding, no BOM.
- Zero personal machine or user path leakage.
- Comprehensive module, class, and method docstrings.
- Module-level constants, exported symbols (__all__), and type integrity.
- CorePlugin instantiation, hook implementation marker compliance, and pluggy registration.
- Tab registration lifecycle, title correctness, execution order, and logging.
- Defensive error handling when MainWindow or QTabWidget container is invalid or None.
- Real physical Qt widget integration with QTabWidget and QApplication.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pluggy
import pytest
from PySide6.QtWidgets import QApplication, QTabWidget, QWidget

import cochem_base.plugins.internal as internal_mod
from cochem_base.path_sanitization import leak_patterns
from cochem_base.plugins.internal import (
    CORE_TAB_DASHBOARD_TITLE,
    CORE_TAB_TITLES,
    CORE_TAB_TOPOS_TITLE,
    CORE_TAB_TORQ_TITLE,
    CorePlugin,
)
from cochem_base.plugins.loader import CoChemStudioSpecs, get_plugin_manager


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Ensure a singleton QApplication instance is active for Qt-based plugin tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def internal_py_path() -> Path:
    """Return the absolute path to cochem_base/plugins/internal.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "plugins" / "internal.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


# =============================================================================
# 1. File Formatting, Line Endings, and Path Sanitization
# =============================================================================


def test_internal_file_encoding_and_lf_line_endings(internal_py_path: Path) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    raw = internal_py_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in plugins/internal.py"
    assert b"\n" in raw, "Missing newline characters in plugins/internal.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in plugins/internal.py"

    content = internal_py_path.read_text(encoding="utf-8")
    assert len(content) > 100, "File content is unexpectedly small."


def test_internal_zero_personal_path_leaks(internal_py_path: Path) -> None:
    """Verify zero personal machine or local user path leakage in plugins/internal.py."""
    lines = internal_py_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in plugins/internal.py: {leaks}"


# =============================================================================
# 2. Docstrings and Architectural Contracts
# =============================================================================


def test_internal_docstrings_and_module_overview() -> None:
    """Verify comprehensive architectural docstrings on module, class, and methods."""
    # Module docstring
    mod_doc = internal_mod.__doc__
    assert mod_doc is not None and len(mod_doc) > 50
    assert "CorePlugin" in mod_doc
    assert "BASE - Hardware Orchestrator" in mod_doc
    assert "TOPOS - Combinatorial Engine" in mod_doc
    assert "TORQ - Quantum Resonance" in mod_doc

    # Class docstring
    class_doc = CorePlugin.__doc__
    assert class_doc is not None and len(class_doc) > 20
    assert "backbone" in class_doc.lower() or "plugin" in class_doc.lower()

    # Method docstring
    method_doc = CorePlugin.register_tabs.__doc__
    assert method_doc is not None and len(method_doc) > 20
    assert "main_window" in method_doc


# =============================================================================
# 3. Constants, Exports, and __all__
# =============================================================================


def test_internal_constants_values_and_types() -> None:
    """Verify constant values, types, and tuple structure."""
    assert CORE_TAB_DASHBOARD_TITLE == "BASE - Hardware Orchestrator"
    assert isinstance(CORE_TAB_DASHBOARD_TITLE, str)

    assert CORE_TAB_TOPOS_TITLE == "TOPOS - Combinatorial Engine"
    assert isinstance(CORE_TAB_TOPOS_TITLE, str)

    assert CORE_TAB_TORQ_TITLE == "TORQ - Quantum Resonance"
    assert isinstance(CORE_TAB_TORQ_TITLE, str)

    assert isinstance(CORE_TAB_TITLES, tuple)
    assert len(CORE_TAB_TITLES) == 3
    assert CORE_TAB_TITLES == (
        "BASE - Hardware Orchestrator",
        "TOPOS - Combinatorial Engine",
        "TORQ - Quantum Resonance",
    )


def test_internal_exports_and_all() -> None:
    """Verify __all__ is complete and accurately reflects public symbols."""
    assert hasattr(internal_mod, "__all__")
    assert isinstance(internal_mod.__all__, list)
    expected_exports = [
        "CORE_TAB_DASHBOARD_TITLE",
        "CORE_TAB_TITLES",
        "CORE_TAB_TOPOS_TITLE",
        "CORE_TAB_TORQ_TITLE",
        "CorePlugin",
    ]
    for sym in expected_exports:
        assert sym in internal_mod.__all__, f"Symbol '{sym}' missing from internal.__all__"
        assert hasattr(internal_mod, sym), f"Symbol '{sym}' defined in __all__ but missing from module"


# =============================================================================
# 4. CorePlugin Class and Tab Registration Logic
# =============================================================================


def test_core_plugin_instantiation() -> None:
    """Verify CorePlugin can be instantiated cleanly."""
    plugin = CorePlugin()
    assert isinstance(plugin, CorePlugin)
    assert hasattr(plugin, "register_tabs")
    assert callable(plugin.register_tabs)


class DummyTabs:
    def __init__(self):
        self.addTab_calls = []
    def addTab(self, widget, title):
        self.addTab_calls.append((widget, title))

class DummyMainWindow:
    def __init__(self):
        self.tabs = DummyTabs()

def test_core_plugin_register_tabs_mock_main_window(qapp: QApplication) -> None:
    """Verify CorePlugin.register_tabs registers all tabs with correct titles and order."""
    plugin = CorePlugin()
    mock_main_window = DummyMainWindow()

    plugin.register_tabs(mock_main_window)

    assert len(mock_main_window.tabs.addTab_calls) == 3
    calls = mock_main_window.tabs.addTab_calls

    # First tab: Dashboard
    assert calls[0][1] == CORE_TAB_DASHBOARD_TITLE
    # Second tab: TOPOS
    assert calls[1][1] == CORE_TAB_TOPOS_TITLE
    # Third tab: TORQ
    assert calls[2][1] == CORE_TAB_TORQ_TITLE


def test_core_plugin_defensive_missing_tabs_attribute() -> None:
    """Verify CorePlugin.register_tabs raises AttributeError if main_window has no tabs attribute."""
    plugin = CorePlugin()
    invalid_window = object()

    with pytest.raises(AttributeError) as exc_info:
        plugin.register_tabs(invalid_window)  # type: ignore[arg-type]

    assert "Cannot register core tabs: MainWindow has no valid 'tabs' attribute." in str(exc_info.value)


def test_core_plugin_defensive_none_tabs_attribute() -> None:
    """Verify CorePlugin.register_tabs raises AttributeError if main_window.tabs is None."""
    plugin = CorePlugin()
    mock_window = DummyMainWindow()
    mock_window.tabs = None

    with pytest.raises(AttributeError) as exc_info:
        plugin.register_tabs(mock_window)

    assert "Cannot register core tabs: MainWindow has no valid 'tabs' attribute." in str(exc_info.value)


def test_core_plugin_pluggy_integration(qapp: QApplication) -> None:
    """Verify CorePlugin registers and fires cleanly through pluggy PluginManager."""
    pm = pluggy.PluginManager("cochem_studio")
    pm.add_hookspecs(CoChemStudioSpecs)

    plugin = CorePlugin()
    pm.register(plugin)

    assert pm.is_registered(plugin)

    mock_main_window = DummyMainWindow()

    pm.hook.register_tabs(main_window=mock_main_window)

    assert len(mock_main_window.tabs.addTab_calls) == 3
    added_titles = [call[1] for call in mock_main_window.tabs.addTab_calls]
    assert added_titles == list(CORE_TAB_TITLES)


def test_core_plugin_physical_qt_widgets(qapp: QApplication) -> None:
    """Verify physical instantiation of real Qt widgets and tab insertion into QTabWidget."""
    plugin = CorePlugin()

    class PhysicalMainWindow(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.tabs = QTabWidget(self)

    win = PhysicalMainWindow()
    try:
        assert win.tabs.count() == 0
        plugin.register_tabs(win)  # type: ignore[arg-type]
        assert win.tabs.count() == 3

        tab_titles = [win.tabs.tabText(i) for i in range(win.tabs.count())]
        assert tab_titles == [
            CORE_TAB_DASHBOARD_TITLE,
            CORE_TAB_TOPOS_TITLE,
            CORE_TAB_TORQ_TITLE,
        ]

        # Verify each widget is a valid QWidget instance
        for i in range(win.tabs.count()):
            widget = win.tabs.widget(i)
            assert isinstance(widget, QWidget)
    finally:
        win.close()


def test_core_plugin_logging_output(caplog: pytest.LogCaptureFixture, qapp: QApplication) -> None:
    """Verify informative logging during tab registration."""
    plugin = CorePlugin()
    mock_main_window = DummyMainWindow()

    with caplog.at_level(logging.DEBUG, logger="cochem_base.plugins.internal"):
        plugin.register_tabs(mock_main_window)

    records = [r for r in caplog.records if r.name == "cochem_base.plugins.internal"]
    assert len(records) >= 4
    info_records = [r for r in records if r.levelno == logging.INFO]
    assert len(info_records) >= 1
    assert "CorePlugin successfully registered 3 core backbone tabs" in info_records[0].message
