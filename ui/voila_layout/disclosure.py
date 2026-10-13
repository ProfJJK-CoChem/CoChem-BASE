"""Keyboard-operable disclosure for optional controls and explanations.

The installed ipywidgets Accordion renders its headings as unfocusable divs.
A real ToggleButton keeps optional settings reachable with Tab and Enter/Space
without requiring injected JavaScript or changing the contained controls.
"""
from __future__ import annotations

import ipywidgets as widgets
from traitlets import Int, TraitError, validate


class Disclosure(widgets.VBox):
    """One optional section with an accessible toggle and retained widget state."""

    selected_index = Int(default_value=None, allow_none=True)

    def __init__(self, title: str, *children: widgets.Widget) -> None:
        self._section_title = str(title)
        self.toggle = widgets.ToggleButton(
            value=False,
            description="Show " + self._section_title,
            tooltip="Show or hide these optional settings",
            layout=widgets.Layout(width="auto", max_width="100%"),
        )
        self.body = widgets.VBox(
            list(children), layout=widgets.Layout(display="none", width="100%", max_width="100%"),
        )
        super().__init__(
            children=[self.toggle, self.body],
            layout=widgets.Layout(width="100%", max_width="100%"),
        )
        self.toggle.observe(self._toggle_changed, names="value")
        self.observe(self._selection_changed, names="selected_index")

    @validate("selected_index")
    def _valid_selection(self, proposal):
        value = proposal["value"]
        if value not in (None, 0):
            raise TraitError("A disclosure has one section: select 0 to open or None to close.")
        return value

    def _toggle_changed(self, change) -> None:
        self.selected_index = 0 if change["new"] else None

    def _selection_changed(self, change) -> None:
        opened = change["new"] == 0
        self.body.layout.display = "" if opened else "none"
        self.toggle.description = ("Hide " if opened else "Show ") + self._section_title
        if self.toggle.value != opened:
            self.toggle.value = opened

    def set_title(self, index: int, title: str) -> None:
        if index != 0:
            raise IndexError("A disclosure has only section 0.")
        self._section_title = str(title)
        self.toggle.description = ("Hide " if self.selected_index == 0 else "Show ") + self._section_title

    def get_title(self, index: int) -> str:
        if index != 0:
            raise IndexError("A disclosure has only section 0.")
        return self._section_title
