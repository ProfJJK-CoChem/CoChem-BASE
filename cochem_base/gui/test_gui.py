import pytest
from PySide6.QtWidgets import QWidget, QLabel
from cochem_base.gui.main_window import MainWindow
import pluggy

# Define a dummy plugin
class DummyPlugin:
    @pluggy.HookimplMarker("cochem_studio")
    def register_tabs(self, main_window):
        dummy_tab = QWidget()
        label = QLabel("Dummy Plugin Tab", dummy_tab)
        main_window.tabs.addTab(dummy_tab, "Dummy")

import sys
from PySide6.QtWidgets import QApplication

def test_main_window_plugin_loading():
    if not QApplication.instance():
        app = QApplication(sys.argv)
    
    # Initialize main window
    window = MainWindow()
    
    # Store initial count
    initial_count = window.tabs.count()
    
    # Register dummy plugin manually
    window.pm.register(DummyPlugin())
    
    # Clear existing tabs to prevent duplicates from re-loading
    window.tabs.clear()
    
    # Trigger loading manually for testing
    window.load_plugins()
    
    # Verify tab was added
    assert window.tabs.count() == initial_count + 1
    
    # Check if "Dummy" is in any tab
    dummy_found = False
    for i in range(window.tabs.count()):
        if window.tabs.tabText(i) == "Dummy":
            dummy_found = True
            break
    assert dummy_found
