"""
CoChem Specialized QC GUI Visualization Widgets.
"""

from .touch_3d_viewer import Touch3DViewer

__all__ = [
    "AirGapStatusWidget",
    "IRCPathViewerWidget",
    "IsotopeLabelerWidget",
    "QTAIMGraphViewerWidget",
    "ACSTableEditorWidget",
    "OrbitalViewerWidget",
    "HTMLSIPreviewWidget",
    "ZenodoPublishDialog",
    "Touch3DViewer",
]


_LEGACY_WIDGET_MODULES = {
    "AirGapStatusWidget": "airgap_status_widget",
    "IRCPathViewerWidget": "irc_path_viewer",
    "IsotopeLabelerWidget": "isotope_labeler",
    "QTAIMGraphViewerWidget": "qtaim_graph_viewer",
    "ACSTableEditorWidget": "table_editor",
    "OrbitalViewerWidget": "orbital_viewer",
    "HTMLSIPreviewWidget": "html_si_preview",
    "ZenodoPublishDialog": "zenodo_dialog",
}


def __getattr__(name):
    """Resolve optional legacy widgets only when they are explicitly requested."""
    module = _LEGACY_WIDGET_MODULES.get(name)
    if module is not None:
        from importlib import import_module

        return getattr(import_module(f"{__name__}.{module}"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
