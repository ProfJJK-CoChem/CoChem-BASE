"""Real widget events keep collapsed controls reachable without losing input."""
from __future__ import annotations

import ipywidgets as widgets
import pytest
from traitlets import TraitError

from ui.voila_layout.disclosure import Disclosure


def test_toggle_events_preserve_child_values_and_synchronize_open_state():
    field = widgets.Text(value="Student's starting geometry")
    panel = Disclosure("Geometry details", field)
    assert isinstance(panel.toggle, widgets.ToggleButton)
    assert panel.body.children == (field,)
    assert panel.selected_index is None
    assert panel.body.layout.display == "none"
    assert panel.toggle.description == "Show Geometry details"

    panel.toggle.value = True
    assert panel.selected_index == 0
    assert panel.body.layout.display != "none"
    assert panel.toggle.description == "Hide Geometry details"
    field.value = "Corrected student label"

    panel.toggle.value = False
    assert panel.selected_index is None
    assert panel.body.layout.display == "none"
    panel.selected_index = 0
    assert panel.toggle.value is True
    assert panel.body.children[0] is field
    assert field.value == "Corrected student label"
    panel.selected_index = None
    assert panel.toggle.value is False
    assert field.value == "Corrected student label"


def test_renaming_keeps_current_state_and_invalid_sections_are_rejected():
    panel = Disclosure("Original title", widgets.HTML("Instructions"))
    panel.set_title(0, "Calculation resources")
    assert panel.get_title(0) == "Calculation resources"
    assert panel.toggle.description == "Show Calculation resources"
    panel.selected_index = 0
    panel.set_title(0, "More settings")
    assert panel.toggle.description == "Hide More settings"
    assert panel.body.layout.display != "none"

    with pytest.raises(TraitError):
        panel.selected_index = 1
    assert panel.selected_index == 0
    assert panel.toggle.value is True
    with pytest.raises(IndexError):
        panel.set_title(1, "No second section")
    with pytest.raises(IndexError):
        panel.get_title(1)
    assert panel.get_title(0) == "More settings"
