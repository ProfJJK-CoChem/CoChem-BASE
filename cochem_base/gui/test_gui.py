import sys
import pytest
from PySide6.QtWidgets import QApplication, QWidget, QLabel
from cochem_base.gui.main_window import MainWindow
import pluggy


class DummyPlugin:
    @pluggy.HookimplMarker("cochem_studio")
    def register_tabs(self, main_window: MainWindow) -> None:
        dummy_tab = QWidget()
        label = QLabel("Dummy Plugin Tab", dummy_tab)
        main_window.tabs.addTab(dummy_tab, "Dummy")


def test_main_window_plugin_loading() -> None:
    if not QApplication.instance():
        app = QApplication(sys.argv)

    window = MainWindow()
    initial_count = window.tabs.count()
    window.pm.register(DummyPlugin())
    window.tabs.clear()
    window.load_plugins()

    assert window.tabs.count() == initial_count + 1

    dummy_found = False
    for i in range(window.tabs.count()):
        if window.tabs.tabText(i) == "Dummy":
            dummy_found = True
            break
    assert dummy_found
