"""Actual widget navigation and reversible selection, without engine claims."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("case", ["operation_fields", "shared_status", "clear_selection"])
def test_actual_research_widgets_in_fresh_process(tmp_path, case):
    environment = dict(os.environ,
        COCHEM_CONFIG=str(tmp_path / "absent-registry.json"),
        COCHEM_ARTIFACT_DIR=str(tmp_path / "artifacts"),
        COCHEM_ARTIFACTS=str(tmp_path / "artifacts"),
        COCHEM_STUDENT_AUTO_SETUP="false",
        COCHEM_STUDENT_AUTO_REMOTE_CHECK="0")
    result = subprocess.run(
        [sys.executable, "-B", str(Path(__file__).resolve()), case],
        env=environment, capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _descendants(widget):
    yield widget
    for child in getattr(widget, "children", ()):
        yield from _descendants(child)


def _exercise(case):
    import ipywidgets as widgets

    from ui.voila_layout.cochem_gui import CoChemGUI
    from ui.voila_layout.disclosure import Disclosure
    from ui.voila_layout.research_panels import OPERATION_LABELS

    gui = CoChemGUI()
    gui._research_capability_worker.join(timeout=30)
    assert not gui._research_capability_worker.is_alive()
    assert gui.btn_research_topos.disabled
    assert gui.btn_research_torq.disabled
    assert gui.btn_research_nbo.disabled
    if case == "operation_fields":
        # These are presentation inputs to real ipywidgets. The actual module
        # observations stay absent and cannot authorize a scientific request.
        gui.research_topos_operation.options = [
            (OPERATION_LABELS[name], name)
            for name in ("energy", "search", "association", "matrix", "thermochemistry")]
        for operation in ("energy", "search", "association", "matrix", "thermochemistry"):
            gui.research_topos_operation.value = operation
            assert (gui.research_candidates.layout.display != "none") == (operation in {"search", "association"})
            assert (gui.research_monomer_section.layout.display != "none") == (operation == "association")
            assert (gui.research_matrix_section.layout.display != "none") == (operation == "matrix")
            assert (gui.research_topos_temperature.layout.display != "none") == (operation == "thermochemistry")
        assert gui.btn_research_topos.disabled
        assert not gui._research_capability_observations["topos"]["operations"]
        for panel in (gui.research_topos_panel, gui.tab_torq, gui.view_modules):
            disclosures = [item for item in _descendants(panel)
                           if isinstance(item, (Disclosure, widgets.Accordion))]
            assert disclosures
            assert all(item.selected_index is None for item in disclosures)
            disclosures[0].selected_index = 0
            assert disclosures[0].selected_index == 0
            disclosures[0].selected_index = None
        assert gui.research_temperature in tuple(_descendants(gui.view_modules))
        return
    if case == "shared_status":
        assert gui.research_status in tuple(_descendants(gui.tab_topos))
        assert gui.research_status in tuple(_descendants(gui.tab_torq))
        original_status = gui.research_status.value
        gui.research_torq_tools.selected_index = 1
        assert gui.research_torq_tools.get_title(1) == "Bond analysis"
        assert gui.research_status.value == original_status
        gui._run_student_torq()
        assert "not started" in gui.research_status.value
        assert not gui._pipeline_running and not gui._actions_running
        assert gui.research_status in gui.tab_torq.children
        assert gui.btn_research_wiberg_nao.disabled
        return
    if case == "clear_selection":
        # Selector values only; no observations, energies or provider outputs
        # are manufactured. The real selection-clearing callback is exercised.
        choices = (("Earlier result", 0), ("Later result", 1))
        gui.research_isomer_choices.options = choices
        gui.research_isomer_choices.value = (0, 1)
        reports_before = tuple(gui._research_reports)
        observations_before = tuple(gui._research_observations)
        displayed_before = gui.research_report_output.value
        downloads_before = gui.research_report_download.value
        gui.btn_research_clear_selection.click()
        assert gui.research_isomer_choices.value == ()
        assert gui.research_isomer_choices.options == choices
        assert tuple(gui._research_reports) == reports_before
        assert tuple(gui._research_observations) == observations_before
        assert gui.research_report_output.value == displayed_before
        assert gui.research_report_download.value == downloads_before
        gui.research_isomer_choices.value = (1,)
        assert gui.research_isomer_choices.value == (1,)
        assert gui.btn_research_compare.disabled
        return
    raise ValueError("Unknown widget case")


if __name__ == "__main__":
    _exercise(sys.argv[1])
