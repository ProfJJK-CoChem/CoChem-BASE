import sys

from PySide6.QtWidgets import QApplication

from cochem_base.gui.main_window import MainWindow


def test_main_window_plugin_loading() -> None:
    if not QApplication.instance():
        QApplication(sys.argv)

    window = MainWindow()
    
    # Verify that the core tabs are loaded correctly from CorePlugin
    expected_tabs = [
        "BASE - Hardware Orchestrator",
        "TOPOS - Combinatorial Engine",
        "TORQ - Quantum Resonance"
    ]
    
    found_tabs = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    
    for expected in expected_tabs:
        assert any(expected in tab for tab in found_tabs), f"Missing tab: {expected}"
