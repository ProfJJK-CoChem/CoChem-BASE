import os
import sys
import logging
from typing import Any, List
from pathlib import Path

import pluggy

hookspec = pluggy.HookspecMarker("cochem_studio")
hookimpl = pluggy.HookimplMarker("cochem_studio")

logger = logging.getLogger(__name__)


class CoChemStudioSpecs:
    """A hook specification namespace."""

    @hookspec
    def register_tabs(self, main_window: Any) -> List[Any]:
        """Register new tabs to the main window's tab widget."""
        return []

    @hookspec
    def register_3d_overlays(self, viewer: Any) -> List[Any]:
        """Register 3D overlays to the molecular viewer."""
        return []

    @hookspec
    def register_menu_actions(self, menu_bar: Any) -> List[Any]:
        """Register new actions to the main menu bar."""
        return []


def get_plugin_manager() -> pluggy.PluginManager:
    """Create and return a configured pluggy PluginManager."""
    # Dynamic pathing via env vars or pathlib.Path.home()
    spycfit_env = os.getenv("COCHEM_SPYCFIT_DIR")
    if spycfit_env:
        spycfit_dir = Path(spycfit_env).resolve()
    else:
        spycfit_dir = Path.home() / ".cochem" / "plugins" / "CoChem-SpycFit"

    if spycfit_dir.exists() and str(spycfit_dir) not in sys.path:
        sys.path.insert(0, str(spycfit_dir))

    pm = pluggy.PluginManager("cochem_studio")
    pm.add_hookspecs(CoChemStudioSpecs)
    
    # Root Cause Resolution: Removed broad Exception swallowing.
    # Architecture must structurally fail loudly if entrypoints are broken.
    pm.load_setuptools_entrypoints("cochem_studio")
    
    return pm
