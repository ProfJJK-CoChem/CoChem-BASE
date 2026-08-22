"""CorePlugin internal plugin module for CoChem-Studio backbone UI components.

Registers the primary core backbone tabs:
- BASE - Hardware Orchestrator
- TOPOS - Combinatorial Engine
- TORQ - Quantum Resonance
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from cochem_base.gui.dashboard import DashboardTab
from cochem_base.gui.topos import ToposTab
from cochem_base.gui.torq import TorqTab
from cochem_base.plugins.loader import hookimpl

if TYPE_CHECKING:
    from cochem_base.gui.main_window import MainWindow

logger = logging.getLogger(__name__)

CORE_TAB_DASHBOARD_TITLE: str = "BASE - Hardware Orchestrator"
CORE_TAB_TOPOS_TITLE: str = "TOPOS - Combinatorial Engine"
CORE_TAB_TORQ_TITLE: str = "TORQ - Quantum Resonance"

CORE_TAB_TITLES: tuple[str, str, str] = (
    CORE_TAB_DASHBOARD_TITLE,
    CORE_TAB_TOPOS_TITLE,
    CORE_TAB_TORQ_TITLE,
)


class CorePlugin:
    """Internal plugin that registers the core backbone UI components for CoChem Studio."""

    @hookimpl
    def register_tabs(self, main_window: Any) -> None:
        """Register core backbone tabs to the MainWindow tab container."""
        if not hasattr(main_window, "tabs") or main_window.tabs is None:
            raise AttributeError("Cannot register core tabs: MainWindow has no valid 'tabs' attribute.")

        # Register CoChem-BASE Dashboard
        logger.debug("Instantiating DashboardTab (%s)", CORE_TAB_DASHBOARD_TITLE)
        dashboard = DashboardTab()
        main_window.tabs.addTab(dashboard, CORE_TAB_DASHBOARD_TITLE)

        # Register CoChem-TOPOS
        logger.debug("Instantiating ToposTab (%s)", CORE_TAB_TOPOS_TITLE)
        topos = ToposTab()
        main_window.tabs.addTab(topos, CORE_TAB_TOPOS_TITLE)

        # Register CoChem-TORQ
        logger.debug("Instantiating TorqTab (%s)", CORE_TAB_TORQ_TITLE)
        torq = TorqTab()
        main_window.tabs.addTab(torq, CORE_TAB_TORQ_TITLE)

        logger.info("CorePlugin successfully registered 3 core backbone tabs: %s", ", ".join(CORE_TAB_TITLES))


__all__ = [
    "CORE_TAB_DASHBOARD_TITLE",
    "CORE_TAB_TITLES",
    "CORE_TAB_TOPOS_TITLE",
    "CORE_TAB_TORQ_TITLE",
    "CorePlugin",
]

