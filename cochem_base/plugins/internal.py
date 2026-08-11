import pluggy
from typing import Any
from cochem_base.gui.dashboard import DashboardTab
from cochem_base.gui.topos import ToposTab
from cochem_base.gui.torq import TorqTab


class CorePlugin:
    """Internal plugin that registers the core backbone UI components."""

    @pluggy.HookimplMarker("cochem_studio")
    def register_tabs(self, main_window: Any) -> None:
        # Register CoChem-BASE Dashboard
        dashboard = DashboardTab()
        main_window.tabs.addTab(dashboard, "BASE - Hardware Orchestrator")

        # Register CoChem-TOPOS
        topos = ToposTab()
        main_window.tabs.addTab(topos, "TOPOS - Combinatorial Engine")

        # Register CoChem-TORQ
        torq = TorqTab()
        main_window.tabs.addTab(torq, "TORQ - Quantum Resonance")
