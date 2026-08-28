"""Comprehensive physical Zero-Mock test suite for cochem_base.gui.main_window module.

Validates:
- File formatting, strict Unix LF line endings, standard UTF-8 encoding, no BOM.
- Zero personal machine or user path leakage.
- Comprehensive module, class, and method docstrings.
- Module-level constants, exported symbols (__all__), and type integrity.
- WorkspaceState Pydantic v2 data model serialization and validation.
- MainWindow initialization, QTabWidget backbone tabs, and ScribeDock logging console.
- Graceful degradation and fallback widget when optional plugins (e.g., SpycFit) are missing.
- Programmatic workspace state serialization (serialize_state) bypassing QFileDialog.
- Programmatic workspace state deserialization (deserialize_state) bypassing QFileDialog.
- Defensive error handling during serialization/deserialization (missing files, bad JSON, invalid schema).
- MainWindow.closeEvent lifecycle ensuring tab cleanup and ScribeDock stream restoration.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QTabWidget, QWidget

import cochem_base.gui.main_window as main_window_mod
from cochem_base.gui.main_window import MainWindow, WorkspaceState
from cochem_base.gui.scribe import OutputStream, ScribeDock
from cochem_base.path_sanitization import leak_patterns
from cochem_base.plugins.internal import (
    CORE_TAB_DASHBOARD_TITLE,
    CORE_TAB_TOPOS_TITLE,
    CORE_TAB_TORQ_TITLE,
)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Ensure a singleton QApplication instance is active for Qt-based GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def main_window_py_path() -> Path:
    """Return the absolute path to cochem_base/gui/main_window.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "gui" / "main_window.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


# =============================================================================
# 1. File Formatting, Line Endings, and Path Sanitization
# =============================================================================


def test_main_window_file_encoding_and_lf_line_endings(main_window_py_path: Path) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    raw = main_window_py_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in gui/main_window.py"
    assert b"\n" in raw, "Missing newline characters in gui/main_window.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in gui/main_window.py"

    content = main_window_py_path.read_text(encoding="utf-8")
    assert len(content) > 100, "File content is unexpectedly small."


def test_main_window_zero_personal_path_leaks(main_window_py_path: Path) -> None:
    """Verify zero personal machine or local user path leakage in gui/main_window.py."""
    lines = main_window_py_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in gui/main_window.py: {leaks}"


# =============================================================================
# 2. Docstrings and Architectural Contracts
# =============================================================================


def test_main_window_docstrings_and_module_overview() -> None:
    """Verify comprehensive architectural docstrings on module, classes, and methods."""
    # Module docstring
    mod_doc = main_window_mod.__doc__
    assert mod_doc is not None and len(mod_doc) > 50
    assert "MainWindow" in mod_doc or "QMainWindow" in mod_doc
    assert "SCRIBE" in mod_doc or "cochem" in mod_doc.lower()

    # Class docstrings
    assert WorkspaceState.__doc__ is not None and len(WorkspaceState.__doc__) > 10
    assert MainWindow.__doc__ is not None and len(MainWindow.__doc__) > 10

    # Method docstrings
    assert MainWindow.load_plugins.__doc__ is not None
    assert MainWindow.setup_menu.__doc__ is not None
    assert MainWindow.serialize_state.__doc__ is not None
    assert MainWindow.deserialize_state.__doc__ is not None
    assert MainWindow.closeEvent.__doc__ is not None


# =============================================================================
# 3. Symbol Exports and __all__ Integrity
# =============================================================================


def test_main_window_exports_and_all() -> None:
    """Verify __all__ is complete and accurately reflects public symbols."""
    assert hasattr(main_window_mod, "__all__")
    assert isinstance(main_window_mod.__all__, list)
    expected_exports = ["MainWindow", "WorkspaceState"]
    for sym in expected_exports:
        assert sym in main_window_mod.__all__, f"Symbol '{sym}' missing from main_window.__all__"
        assert hasattr(main_window_mod, sym), f"Symbol '{sym}' in __all__ but missing from module"


# =============================================================================
# 4. WorkspaceState Pydantic Model Validation
# =============================================================================


def test_workspace_state_validation() -> None:
    """Verify WorkspaceState schema validation and serialization."""
    state = WorkspaceState(
        version="1.0",
        cochem_base="active",
        tabs=["Tab1", "Tab2"],
        active_tab_index=0,
    )
    assert state.version == "1.0"
    assert state.cochem_base == "active"
    assert state.tabs == ["Tab1", "Tab2"]
    assert state.active_tab_index == 0

    json_str = state.model_dump_json()
    parsed = json.loads(json_str)
    assert parsed["tabs"] == ["Tab1", "Tab2"]

    with pytest.raises(ValidationError):
        WorkspaceState(version="1.0")  # type: ignore[call-arg]


# =============================================================================
# 5. MainWindow UI Component Integration
# =============================================================================


def test_main_window_initialization(qapp: QApplication) -> None:
    """Verify MainWindow initializes title, central tabs, dock widgets, and menu bar."""
    window = MainWindow()
    try:
        assert window.windowTitle() == "CoChem-Studio"
        assert isinstance(window.tabs, QTabWidget)
        assert window.centralWidget() == window.tabs

        # ScribeDock
        assert hasattr(window, "scribe_dock")
        assert isinstance(window.scribe_dock, ScribeDock)

        # Tab titles registered by CorePlugin
        tab_titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
        assert CORE_TAB_DASHBOARD_TITLE in tab_titles
        assert CORE_TAB_TOPOS_TITLE in tab_titles
        assert CORE_TAB_TORQ_TITLE in tab_titles

        # Fallback tab for SpycFit
        assert any("SpycFit" in t for t in tab_titles)
        spycfit_idx = next(i for i, t in enumerate(tab_titles) if "SpycFit" in t)
        assert window.tabs.isTabEnabled(spycfit_idx) is False

        # Menu bar
        menubar = window.menuBar()
        actions = menubar.actions()
        assert any(a.text() == "File" for a in actions)
    finally:
        window.close()


# =============================================================================
# 6. Programmatic Workspace State Serialization & Deserialization
# =============================================================================


def test_main_window_programmatic_serialization_and_deserialization(
    qapp: QApplication, tmp_path: Path
) -> None:
    """Verify serialize_state and deserialize_state with explicit file_path bypass QFileDialog."""
    window = MainWindow()
    target_json = tmp_path / "saved_workspace.json"

    try:
        # Set active tab to TORQ (index 2)
        window.tabs.setCurrentIndex(2)
        assert window.tabs.currentIndex() == 2

        # 1. Programmatic serialization
        saved_path = window.serialize_state(file_path=target_json)
        assert saved_path == target_json
        assert target_json.is_file()

        raw_data = json.loads(target_json.read_text(encoding="utf-8"))
        assert raw_data["version"] == "1.0"
        assert raw_data["cochem_base"] == "active"
        assert raw_data["active_tab_index"] == 2
        assert len(raw_data["tabs"]) == window.tabs.count()

        # Switch to index 0
        window.tabs.setCurrentIndex(0)
        assert window.tabs.currentIndex() == 0

        # 2. Programmatic deserialization
        loaded_state = window.deserialize_state(file_path=target_json)
        assert loaded_state is not None
        assert isinstance(loaded_state, WorkspaceState)
        assert loaded_state.active_tab_index == 2
        assert window.tabs.currentIndex() == 2

        # 3. String path input variant
        target_str_json = tmp_path / "str_workspace.json"
        window.tabs.setCurrentIndex(1)
        saved_str_path = window.serialize_state(file_path=str(target_str_json))
        assert saved_str_path == target_str_json
        assert target_str_json.is_file()

        window.tabs.setCurrentIndex(0)
        loaded_str_state = window.deserialize_state(file_path=str(target_str_json))
        assert loaded_str_state is not None
        assert window.tabs.currentIndex() == 1
    finally:
        window.close()


def test_main_window_deserialization_error_handling(
    qapp: QApplication, tmp_path: Path
) -> None:
    """Verify deserialize_state handles missing, invalid JSON, and bad schema files gracefully."""
    window = MainWindow()
    try:
        # 1. Non-existent file
        missing_file = tmp_path / "non_existent.json"
        assert window.deserialize_state(file_path=missing_file) is None

        # 2. Corrupted JSON file
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("{corrupt json syntax...", encoding="utf-8")
        assert window.deserialize_state(file_path=bad_json) is None

        # 3. Invalid schema format
        invalid_schema = tmp_path / "invalid_schema.json"
        invalid_schema.write_text(json.dumps({"unknown_key": 42}), encoding="utf-8")
        assert window.deserialize_state(file_path=invalid_schema) is None
    finally:
        window.close()


# =============================================================================
# 7. MainWindow closeEvent and Resource Teardown
# =============================================================================


class CleanupTrackingTab(QWidget):
    """Custom widget to track cleanup and close invocation during closeEvent."""

    def __init__(self) -> None:
        super().__init__()
        self.cleanup_called = False
        self.close_called = False

    def cleanup(self) -> None:
        self.cleanup_called = True

    def close(self) -> bool:
        self.close_called = True
        return super().close()


def test_main_window_close_event_resource_cleanup(qapp: QApplication) -> None:
    """Verify closeEvent invokes cleanup/close on child tabs and restores sys streams."""
    orig_stdout = sys.__stdout__
    orig_stderr = sys.__stderr__

    window = MainWindow()

    # Add custom tracking tab
    tracker_tab = CleanupTrackingTab()
    window.tabs.addTab(tracker_tab, "Tracking Tab")

    # Verify Scribe redirected sys.stdout
    assert isinstance(sys.stdout, OutputStream)
    assert isinstance(sys.stderr, OutputStream)

    # Trigger window closure
    close_event = QCloseEvent()
    window.closeEvent(close_event)

    # Verify tracking tab cleanup was called
    assert tracker_tab.cleanup_called is True
    assert tracker_tab.close_called is True

    # Verify sys.stdout and sys.stderr are restored
    assert sys.stdout == orig_stdout
    assert sys.stderr == orig_stderr

