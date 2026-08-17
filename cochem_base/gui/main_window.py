import json

from pydantic import BaseModel, ValidationError
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from cochem_base.config_loader import get_artifact_dir
from cochem_base.gui.scribe import ScribeDock
from cochem_base.plugins.internal import CorePlugin
from cochem_base.plugins.loader import get_plugin_manager


class WorkspaceState(BaseModel):
    version: str
    cochem_base: str
    tabs: list[str]
    active_tab_index: int


class MainWindow(QMainWindow):
    def __init__(self) -> None:
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
        """Invoke hooks to load plugins into the GUI."""
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
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        save_action = QAction("Save Workspace", self)
        save_action.triggered.connect(self.serialize_state)
        file_menu.addAction(save_action)

        load_action = QAction("Load Workspace", self)
        load_action.triggered.connect(self.deserialize_state)
        file_menu.addAction(load_action)

    def serialize_state(self) -> None:
        workspace_dir = get_artifact_dir() / "Workspaces"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Workspace", str(workspace_dir), "JSON Files (*.json)")
        if file_path:
            try:
                state = WorkspaceState(
                    version="1.0",
                    cochem_base="active",
                    tabs=[self.tabs.tabText(i) for i in range(self.tabs.count())],
                    active_tab_index=self.tabs.currentIndex()
                )
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(state.model_dump_json(indent=4))
                self.scribe_dock.log(f"Workspace saved to {file_path}")
            except OSError as e:
                self.scribe_dock.log(f"Failed to save workspace: OSError: {e}")

    def deserialize_state(self) -> None:
        workspace_dir = get_artifact_dir() / "Workspaces"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Workspace", str(workspace_dir), "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                state = WorkspaceState(**data)
                
                if 0 <= state.active_tab_index < self.tabs.count():
                    self.tabs.setCurrentIndex(state.active_tab_index)
                
                self.scribe_dock.log(f"Workspace loaded from {file_path}")
            except OSError as e:
                self.scribe_dock.log(f"Failed to load workspace: OSError: {e}")
            except json.JSONDecodeError as e:
                self.scribe_dock.log(f"Failed to load workspace: JSON Decode Error: {e}")
            except ValidationError as e:
                self.scribe_dock.log(f"Failed to load workspace: Invalid State Format: {e}")
