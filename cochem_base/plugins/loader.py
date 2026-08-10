import pluggy

hookspec = pluggy.HookspecMarker("cochem_studio")
hookimpl = pluggy.HookimplMarker("cochem_studio")

class CoChemStudioSpecs:
    """A hook specification namespace."""
    
    @hookspec
    def register_tabs(self, main_window):
        """Register new tabs to the main window's tab widget."""
        return []

    @hookspec
    def register_3d_overlays(self, viewer):
        """Register 3D overlays to the molecular viewer."""
        return []

    @hookspec
    def register_menu_actions(self, menu_bar):
        """Register new actions to the main menu bar."""
        return []


def get_plugin_manager():
    """Create and return a configured pluggy PluginManager."""
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    spycfit_dir = root / "CoChem-SpycFit"
    if spycfit_dir.exists() and str(spycfit_dir) not in sys.path:
        sys.path.insert(0, str(spycfit_dir))

    pm = pluggy.PluginManager("cochem_studio")
    pm.add_hookspecs(CoChemStudioSpecs)
    try:
        pm.load_setuptools_entrypoints("cochem_studio")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed loading some plugin entrypoints: {e}")
    return pm
