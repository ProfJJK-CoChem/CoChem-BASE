"""CoChem-Studio Main Window Graphical Interface and Workspace Orchestration.

This module provides the primary QMainWindow architecture for the CoChem-Studio
application, integrating the core plugin management backbone, QTabWidget multi-panel
workspace navigation, and the SCRIBE data provenance logging console.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional, Union

from pydantic import BaseModel, ValidationError
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from cochem_base.config_loader import get_artifact_dir
from cochem_base.gui.scribe import ScribeDock
from cochem_base.plugins.internal import CorePlugin
from cochem_base.plugins.loader import get_plugin_manager

__all__ = ["MainWindow", "WorkspaceState"]


class WorkspaceState(BaseModel):
    """Pydantic v2 data model representing serialized CoChem workspace state."""

    version: str
    cochem_base: str
    tabs: list[str]
    active_tab_index: int


class MainWindow(QMainWindow):
    """Primary graphical user interface window for the CoChem-Studio ecosystem."""

    def __init__(self) -> None:
        """Initialize the main window, UI components, plugins, and SCRIBE logger."""
        super().__init__()
        self.setWindowTitle("CoChem-Studio")
        self.resize(1024, 768)

        self.setup_menu()

        # Central Tab Widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Bottom Dock for SCRIBE (Logging Console)
        self.scribe_dock = ScribeDock(self)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.scribe_dock)  # type: ignore

        # Initialize plugin manager
        self.pm = get_plugin_manager()

        # Register core modules
        self.pm.register(CorePlugin())

        self.load_plugins()

    def load_plugins(self) -> None:
        """Invoke pluggy hooks to register tabs, menu actions, and fallback widgets."""
        self.pm.hook.register_tabs(main_window=self)
        self.pm.hook.register_menu_actions(menu_bar=self.menuBar())

        # Graceful Degradation Check
        spycfit_found = False
        for i in range(self.tabs.count()):
            if "SpycFit" in self.tabs.tabText(i):
                spycfit_found = True
                break

        if not spycfit_found:
            fallback_widget = QWidget()
            layout = QVBoxLayout(fallback_widget)
            lbl = QLabel("Module Missing: CoChem-SpycFit is not installed.")
            lbl.setToolTip("SpycFit requires the cochem-spycfit package for Bayesian Active Learning.")
            layout.addWidget(lbl)
            self.tabs.addTab(fallback_widget, "SpycFit (Missing)")
            self.tabs.setTabEnabled(self.tabs.count() - 1, False)

    def setup_menu(self) -> None:
        """Construct the top menu bar actions for workspace persistence."""
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        save_action = QAction("Save Workspace", self)
        save_action.triggered.connect(lambda: self.serialize_state())
        file_menu.addAction(save_action)

        load_action = QAction("Load Workspace", self)
        load_action.triggered.connect(lambda: self.deserialize_state())
        file_menu.addAction(load_action)

    def serialize_state(self, file_path: Optional[Union[str, Path]] = None) -> Optional[Path]:
        """Serialize current workspace state to disk with programmatic or dialog path selection."""
        if file_path is None or isinstance(file_path, bool):
            workspace_dir = get_artifact_dir() / "Workspaces"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            selected_path, _ = QFileDialog.getSaveFileName(
                self, "Save Workspace", str(workspace_dir), "JSON Files (*.json)"
            )
            if not selected_path:
                return None
            target_path = Path(selected_path)
        else:
            target_path = Path(file_path)

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            state = WorkspaceState(
                version="1.0",
                cochem_base="active",
                tabs=[self.tabs.tabText(i) for i in range(self.tabs.count())],
                active_tab_index=self.tabs.currentIndex(),
            )
            target_path.write_text(state.model_dump_json(indent=4), encoding="utf-8")
            self.scribe_dock.log(f"Workspace saved to {target_path}")
            return target_path
        except OSError as e:
            self.scribe_dock.log(f"Failed to save workspace: OSError: {e}")
            return None
        except Exception as e:
            self.scribe_dock.log(f"Failed to save workspace: {e}")
            return None

    def deserialize_state(self, file_path: Optional[Union[str, Path]] = None) -> Optional[WorkspaceState]:
        """Deserialize and restore workspace state from a JSON file path or interactive dialog."""
        if file_path is None or isinstance(file_path, bool):
            workspace_dir = get_artifact_dir() / "Workspaces"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            selected_path, _ = QFileDialog.getOpenFileName(
                self, "Load Workspace", str(workspace_dir), "JSON Files (*.json)"
            )
            if not selected_path:
                return None
            target_path = Path(selected_path)
        else:
            target_path = Path(file_path)

        if not target_path.is_file():
            self.scribe_dock.log(f"Failed to load workspace: File not found: {target_path}")
            return None

        try:
            raw_text = target_path.read_text(encoding="utf-8")
            data = json.loads(raw_text)
            state = WorkspaceState(**data)

            if 0 <= state.active_tab_index < self.tabs.count():
                self.tabs.setCurrentIndex(state.active_tab_index)

            self.scribe_dock.log(f"Workspace loaded from {target_path}")
            return state
        except OSError as e:
            self.scribe_dock.log(f"Failed to load workspace: OSError: {e}")
            return None
        except json.JSONDecodeError as e:
            self.scribe_dock.log(f"Failed to load workspace: JSON Decode Error: {e}")
            return None
        except ValidationError as e:
            self.scribe_dock.log(f"Failed to load workspace: Invalid State Format: {e}")
            return None
        except Exception as e:
            self.scribe_dock.log(f"Failed to load workspace: Unexpected Error: {e}")
            return None

    def closeEvent(self, event: QCloseEvent) -> None:
        """Clean up active child tab resources and restore standard system I/O streams."""
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if widget is not None:
                if hasattr(widget, "cleanup") and callable(widget.cleanup):
                    widget.cleanup()
                if hasattr(widget, "close") and callable(widget.close):
                    widget.close()

        if hasattr(self, "scribe_dock") and self.scribe_dock is not None:
            self.scribe_dock.close()

        # Explicitly restore streams if not already restored by ScribeDock
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

        super().closeEvent(event)

