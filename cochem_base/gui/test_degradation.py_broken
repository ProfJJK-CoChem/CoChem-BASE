import sys

from PySide6.QtWidgets import QApplication

from cochem_base.gui.main_window import MainWindow
from cochem_base.plugins.loader import get_plugin_manager


def test_graceful_degradation_spycfit_missing() -> None:
    if not QApplication.instance():
        QApplication(sys.argv)

    pm = get_plugin_manager()

    spycfit_plugin = pm.get_plugin("cochem_spycfit")
    if spycfit_plugin:
        pm.unregister(plugin=spycfit_plugin)

    window = MainWindow()

    missing_tab_found = False
    for i in range(window.tabs.count()):
        if window.tabs.tabText(i) == "SpycFit (Missing)":
            missing_tab_found = True
            assert window.tabs.isTabEnabled(i) is False
            break

    assert missing_tab_found, "Graceful degradation failed: Missing tab not found."

    if spycfit_plugin:
        pm.register(spycfit_plugin)
