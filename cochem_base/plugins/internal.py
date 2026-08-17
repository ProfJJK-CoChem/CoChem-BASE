from typing import TYPE_CHECKING

from cochem_base.gui.dashboard import DashboardTab
from cochem_base.gui.topos import ToposTab
from cochem_base.gui.torq import TorqTab
from cochem_base.plugins.loader import hookimpl

if TYPE_CHECKING:
    from cochem_base.gui.main_window import MainWindow


class CorePlugin:
    """Internal plugin that registers the core backbone UI components."""

    @hookimpl
    def register_tabs(self, main_window: "MainWindow") -> None:
        # Register CoChem-BASE Dashboard
        dashboard = DashboardTab()
        main_window.tabs.addTab(dashboard, "BASE - Hardware Orchestrator")

        # Register CoChem-TOPOS
        topos = ToposTab()
        main_window.tabs.addTab(topos, "TOPOS - Combinatorial Engine")

        # Register CoChem-TORQ
        torq = TorqTab()
        main_window.tabs.addTab(torq, "TORQ - Quantum Resonance")
