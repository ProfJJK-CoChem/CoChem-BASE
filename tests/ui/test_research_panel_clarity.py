"""Actual widget navigation and reversible selection, without engine claims."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("case", [
    "operation_fields", "shared_status", "clear_selection", "scan_sampling",
    "comparison_guidance", "contextual_help",
])
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
            assert (gui.research_candidate_section.layout.display != "none") == (operation in {"search", "association"})
            assert (gui.research_topos_method_section.layout.display != "none") == (operation != "matrix")
            assert (gui.research_monomer_section.layout.display != "none") == (operation == "association")
            assert (gui.research_matrix_section.layout.display != "none") == (operation == "matrix")
            assert (gui.research_topos_temperature.layout.display != "none") == (operation == "thermochemistry")
        assert gui.btn_research_topos.disabled
        assert not gui._research_capability_observations["topos"]["operations"]
        for panel in (gui.research_topos_panel, gui.tab_torq, gui.view_modules):
            disclosures = [item for item in _descendants(panel)
                           if isinstance(item, (Disclosure, widgets.Accordion))]
            native_help = [item for item in _descendants(panel)
                           if isinstance(item, widgets.HTML) and "<details" in item.value]
            assert disclosures or native_help
            assert all(item.selected_index is None for item in disclosures)
            if disclosures:
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
    if case == "scan_sampling":
        source_before = tuple(gui._research_observations)
        gui.research_scan_start.value = 3.0
        gui.research_scan_end.value = 6.0
        gui.research_scan_points.value = 5
        assert "5 energy calculations" in gui.research_scan_summary.value
        assert "0.75 Å" in gui.research_scan_summary.value
        gui.research_scan_points.value = 7
        assert "7 energy calculations" in gui.research_scan_summary.value
        assert "0.5 Å" in gui.research_scan_summary.value
        gui.research_scan_end.value = 2.0
        assert "end distance greater" in gui.research_scan_summary.value
        assert "role='alert'" in gui.research_scan_summary.value
        # The explanation does not correct, submit or authorize the input.
        assert gui.research_scan_end.value == 2.0
        assert gui.btn_research_torq.disabled
        assert tuple(gui._research_observations) == source_before
        assert not gui._pipeline_running and not gui._actions_running
        gui.research_scan_end.value = 6.0
        assert "role='alert'" not in gui.research_scan_summary.value
        return
    if case == "comparison_guidance":
        temperature = gui.research_temperature.value
        displayed = gui.research_report_output.value
        assert "No comparable energies" in gui.research_comparison_hint.value
        assert gui.research_result_temperature.layout.display == "none"
        gui.research_populations.value = True
        assert "equilibrium populations" in gui.research_population_hint.value
        assert "verified minima" in gui.research_population_hint.value
        assert gui.research_result_temperature.layout.display != "none"
        gui.research_energy_kind.value = "gibbs_free_energy"
        assert "standard state" in gui.research_population_hint.value
        assert "does not recalculate" in gui.research_population_hint.value
        assert "equilibrate" in gui.research_population_hint.value
        gui.research_populations.value = False
        assert gui.research_result_temperature.layout.display != "none"
        gui.research_energy_kind.value = "electronic_energy"
        assert gui.research_result_temperature.layout.display == "none"
        assert gui.research_temperature.layout.display != "none"
        assert gui.research_temperature.value == temperature
        assert gui.research_report_output.value == displayed
        assert not gui._research_reports and not gui._research_observations
        assert gui.btn_research_compare.disabled
        return
    if case == "contextual_help":
        from html.parser import HTMLParser

        class HelpStructure(HTMLParser):
            def __init__(self):
                super().__init__()
                self.details = 0
                self.summaries = 0
                self.opened = []

            def handle_starttag(self, tag, attrs):
                if tag == "details":
                    self.details += 1
                    if "open" in dict(attrs):
                        self.opened.append(dict(attrs))
                elif tag == "summary":
                    self.summaries += 1

        for panel in (gui.research_topos_panel, gui.tab_torq, gui.view_modules):
            parser = HelpStructure()
            for item in _descendants(panel):
                if isinstance(item, widgets.HTML):
                    parser.feed(item.value)
            assert parser.details >= 2
            assert parser.details == parser.summaries
            assert not parser.opened
        scan_markup = " ".join(item.value for item in _descendants(gui.research_torq_tools.children[0])
                               if isinstance(item, widgets.HTML))
        assert "centers of mass" in scan_markup
        assert "refine the spacing" in scan_markup
        assert "not a binding energy" in scan_markup
        assert "torsional barrier" in scan_markup
        assert gui.btn_research_torq.disabled
        return
    raise ValueError("Unknown widget case")


if __name__ == "__main__":
    _exercise(sys.argv[1])
