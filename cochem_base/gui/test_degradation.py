import sys
import pytest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from cochem_base.gui.main_window import MainWindow

def test_graceful_degradation_spycfit_missing():
    if not QApplication.instance():
        app = QApplication(sys.argv)
        
    # Simulate missing cochem_spycfit by patching the plugin manager's hook mechanism
    # to not return anything for SpycFit.
    # Because SpycFit is loaded dynamically by pluggy, we can just patch `pluggy.PluginManager.get_plugins`
    # or easier: just don't have it installed/registered in this mocked context.
    # Since we are running this test, SpycFit might be installed. We must mock the tab addition 
    # to pretend it wasn't added by the hook.
    
    with patch('cochem_base.gui.main_window.get_plugin_manager') as mock_get_pm:
        # We need a real plugin manager but we mock `load_setuptools_entrypoints` to do nothing
        from cochem_base.plugins.loader import get_plugin_manager
        real_pm = get_plugin_manager()
        
        # Unregister cochem_spycfit if it was loaded
        plugin = real_pm.get_plugin("cochem_spycfit")
        if plugin:
            real_pm.unregister(plugin=plugin)
            
        # Also prevent loading any entry points during the test
        real_pm.load_setuptools_entrypoints = lambda *args, **kwargs: None
        
        mock_get_pm.return_value = real_pm
        
        window = MainWindow()
        
        # Verify that SpycFit is reported as missing
        missing_tab_found = False
        for i in range(window.tabs.count()):
            if window.tabs.tabText(i) == "SpycFit (Missing)":
                missing_tab_found = True
                assert window.tabs.isTabEnabled(i) == False
                break
                
        assert missing_tab_found, "Graceful degradation failed: Missing placeholder tab not found."
