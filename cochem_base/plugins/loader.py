"""Plugin loader and hook specification engine for CoChem Studio (cochem_studio).

Manages pluggy-based plugin lifecycles, hook registration, entrypoint discovery,
and safe path injection for CoChem Studio extensions like CoChem-SpycFit.
Functions include get_plugin_manager, resolve_spycfit_plugin_dir, and inject_plugin_path.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, List, Optional, Sequence, Union

import pluggy

logger = logging.getLogger(__name__)

PLUGIN_PROJECT_NAME: str = "cochem_studio"
COCHEM_SPYCFIT_ENV_VAR: str = "COCHEM_SPYCFIT_DIR"
DEFAULT_SPYCFIT_PLUGIN_RELPATH: Path = Path(".cochem") / "plugins" / "CoChem-SpycFit"

hookspec = pluggy.HookspecMarker(PLUGIN_PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PLUGIN_PROJECT_NAME)


class CoChemStudioSpecs:
    """A hook specification namespace for cochem_studio plugins."""

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


def resolve_spycfit_plugin_dir(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolve the CoChem-SpycFit plugin directory using explicit argument, env var, or default."""
    if custom_path is not None:
        return Path(custom_path).resolve()

    env_val = os.environ.get(COCHEM_SPYCFIT_ENV_VAR)
    if env_val and env_val.strip():
        return Path(env_val.strip()).resolve()

    return (Path.home() / DEFAULT_SPYCFIT_PLUGIN_RELPATH).resolve()


def inject_plugin_path(path: Union[str, Path]) -> bool:
    """Inject a plugin directory into sys.path safely with deduplication. Returns True if inserted."""
    p = Path(path).resolve()
    if not p.is_dir():
        logger.debug("Plugin directory does not exist, skipping sys.path injection: %s", p)
        return False

    p_str = str(p)
    # Check normalized resolution in sys.path
    for entry in sys.path:
        try:
            if Path(entry).resolve() == p:
                logger.debug("Plugin directory already in sys.path: %s", p_str)
                return False
        except Exception:
            if entry == p_str:
                return False

    sys.path.insert(0, p_str)
    logger.debug("Injected plugin directory into sys.path: %s", p_str)
    return True


def get_plugin_manager(
    load_entrypoints: bool = True,
    custom_plugin_dir: Optional[Union[str, Path, Sequence[Union[str, Path]]]] = None,
) -> pluggy.PluginManager:
    """Create and return a configured pluggy PluginManager for cochem_studio."""
    if custom_plugin_dir is not None:
        if isinstance(custom_plugin_dir, (str, Path)):
            inject_plugin_path(custom_plugin_dir)
        else:
            for p in custom_plugin_dir:
                inject_plugin_path(p)
    else:
        spycfit_dir = resolve_spycfit_plugin_dir()
        if spycfit_dir.is_dir():
            inject_plugin_path(spycfit_dir)

    pm = pluggy.PluginManager(PLUGIN_PROJECT_NAME)
    pm.add_hookspecs(CoChemStudioSpecs)

    if load_entrypoints:
        try:
            pm.load_setuptools_entrypoints(PLUGIN_PROJECT_NAME)
        except Exception as e:
            logger.warning("Error loading setuptools entrypoints for %s: %s", PLUGIN_PROJECT_NAME, e)

    logger.debug("Pluggy PluginManager initialized successfully for project %s", PLUGIN_PROJECT_NAME)
    return pm


__all__ = [
    "COCHEM_SPYCFIT_ENV_VAR",
    "CoChemStudioSpecs",
    "DEFAULT_SPYCFIT_PLUGIN_RELPATH",
    "PLUGIN_PROJECT_NAME",
    "get_plugin_manager",
    "hookimpl",
    "hookspec",
    "inject_plugin_path",
    "resolve_spycfit_plugin_dir",
]

