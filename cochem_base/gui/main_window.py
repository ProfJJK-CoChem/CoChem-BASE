from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QFileDialog
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
import json
from cochem_base.plugins.loader import get_plugin_manager
from cochem_base.gui.scribe import ScribeDock

from cochem_base.plugins.internal import CorePlugin

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CoChem-Studio")
        self.resize(1024, 768)
        
        self.setup_menu()

        # Central Tab Widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Bottom Dock for SCRIBE (Logging Console)
        self.scribe_dock = ScribeDock(self)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.scribe_dock)

        # Initialize plugin manager
        self.pm = get_plugin_manager()
        
        # Register core modules
        self.pm.register(CorePlugin())
        
        self.load_plugins()

    def load_plugins(self):
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
            from PySide6.QtWidgets import QLabel
            fallback_widget = QWidget()
            layout = QVBoxLayout(fallback_widget)
            lbl = QLabel("Module Missing: CoChem-SpycFit is not installed.")
            lbl.setToolTip("SpycFit requires the cochem-spycfit package for Bayesian Active Learning.")
            layout.addWidget(lbl)
            self.tabs.addTab(fallback_widget, "SpycFit (Missing)")
            self.tabs.setTabEnabled(self.tabs.count() - 1, False)


    def setup_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        
        save_action = QAction("Save Workspace", self)
        save_action.triggered.connect(self.serialize_state)
        file_menu.addAction(save_action)
        
        load_action = QAction("Load Workspace", self)
        load_action.triggered.connect(self.deserialize_state)
        file_menu.addAction(load_action)

    def serialize_state(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Workspace", "", "JSON Files (*.json)")
        if file_path:
            state = {
                "version": "1.0",
                "cochem_base": "active",
                "tabs": [self.tabs.tabText(i) for i in range(self.tabs.count())],
                "active_tab_index": self.tabs.currentIndex()
            }
            with open(file_path, "w") as f:
                json.dump(state, f, indent=4)
            self.scribe_dock.log(f"Workspace saved to {file_path}")


    def deserialize_state(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Workspace", "", "JSON Files (*.json)")
        if file_path:
            with open(file_path, "r") as f:
                state = json.load(f)
            self.scribe_dock.log(f"Workspace loaded from {file_path}")
