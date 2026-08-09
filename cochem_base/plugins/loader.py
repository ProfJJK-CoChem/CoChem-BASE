import pluggy

hookspec = pluggy.HookspecMarker("cochem_studio")
hookimpl = pluggy.HookimplMarker("cochem_studio")

class CoChemStudioSpecs:
    """A hook specification namespace."""
    
    @hookspec
    def register_tabs(self, main_window):
        """Register new tabs to the main window's tab widget."""
        pass

    @hookspec
    def register_3d_overlays(self, viewer):
        """Register 3D overlays to the molecular viewer."""
        pass

    @hookspec
    def register_menu_actions(self, menu_bar):
        """Register new actions to the main menu bar."""
        pass

def get_plugin_manager():
    """Create and return a configured pluggy PluginManager."""
    pm = pluggy.PluginManager("cochem_studio")
    pm.add_hookspecs(CoChemStudioSpecs)
    pm.load_setuptools_entrypoints("cochem_studio")
    return pm
