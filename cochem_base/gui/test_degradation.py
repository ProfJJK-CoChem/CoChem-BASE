import sys
import pytest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from cochem_base.gui.main_window import MainWindow


def test_graceful_degradation_spycfit_missing() -> None:
    if not QApplication.instance():
        app = QApplication(sys.argv)

    with patch('cochem_base.gui.main_window.get_plugin_manager') as mock_get_pm:
        from cochem_base.plugins.loader import get_plugin_manager
        real_pm = get_plugin_manager()

        plugin = real_pm.get_plugin("cochem_spycfit")
        if plugin:
            real_pm.unregister(plugin=plugin)

        real_pm.load_setuptools_entrypoints = lambda *args, **kwargs: None

        mock_get_pm.return_value = real_pm

        window = MainWindow()

        missing_tab_found = False
        for i in range(window.tabs.count()):
            if window.tabs.tabText(i) == "SpycFit (Missing)":
                missing_tab_found = True
                assert window.tabs.isTabEnabled(i) is False
                break

        assert missing_tab_found, "Graceful degradation failed: Missing placeholder tab not found."
