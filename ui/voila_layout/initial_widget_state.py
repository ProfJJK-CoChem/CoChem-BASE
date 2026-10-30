"""Initial backend-owned library state after each model's own display acknowledgement.

Qualified with ipywidgets 8.1.9 and its widgets-manager8 frontend. The synced
``_view_count`` opt-in is experimental: runtime features are checked explicitly.
This never replays selection indices, draft values or a global widget tree.
"""
from __future__ import annotations

import ipywidgets as widgets
from packaging.version import InvalidVersion, Version
from traitlets import Int


class UnsupportedWidgetRuntime(RuntimeError):
    """The installed interface cannot provide the required acknowledgement."""


def _supported_version(version: str) -> bool:
    try:
        parsed = Version(version)
        return parsed.major == 8 and Version("8.1") <= parsed < Version("9")
    except InvalidVersion:
        return False


def ensure_widget_runtime() -> None:
    """Fail explicitly rather than treating an unsupported lifecycle as ready."""
    if not _supported_version(widgets.__version__):
        raise UnsupportedWidgetRuntime(
            "BASE's interface needs ipywidgets >=8.1,<9 with startup display acknowledgements. "
            "Ask your instructor to repair the interface setup. The qualified runtime is ipywidgets 8.1.9."
        )
    _check_view_count(widgets.Widget.class_traits().get("_view_count"))


def _check_view_count(trait: object) -> None:
    if not (isinstance(trait, Int) and trait.allow_none and trait.default_value is None
            and trait.metadata.get("sync") is True):
        raise UnsupportedWidgetRuntime(
            "The installed widget runtime lacks the synchronized startup display acknowledgement. "
            "Ask your instructor to repair the interface setup; ipywidgets 8.1.9 is the qualified runtime."
        )


def arm_initial_widget_state(widget: widgets.Widget) -> None:
    """Replay only backend-owned fields once, on this model's first real view.

    This is scoped to the initial library catalog: placeholder index 0, frame
    index None and an empty pool selection. ``index`` and ``value`` are never
    replayed over a pending local choice. It is not general reconciliation of
    resized/reordered catalogs or arbitrary stale indices. No scan or timer.
    """
    ensure_widget_runtime()
    _check_view_count(widget.traits().get("_view_count"))
    if isinstance(widget, widgets.HTML):
        keys = ("value",)
    elif isinstance(widget, widgets.Button):
        keys = ("disabled",)
    elif isinstance(widget, (widgets.Dropdown, widgets.SelectMultiple)):
        keys = ("_options_labels",)
    else:
        raise ValueError("Initial library state synchronization accepts HTML, buttons and library selectors only")
    if widget._view_count is not None:
        raise ValueError("Initial library state synchronization must be armed once before display")

    def acknowledge(change: dict) -> None:
        count = change["new"]
        if type(count) is not int or count <= 0:
            return
        widget.unobserve(acknowledge, names="_view_count")
        widget.send_state(key=list(keys))

    widget.observe(acknowledge, names="_view_count")
    widget._view_count = 0
