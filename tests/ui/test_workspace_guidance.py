"""Real widget actions preserve scientific drafts while exposing useful help."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("case", ["goal_navigation", "help_preserves_draft", "input_disclosure", "choice_labels",
                                  "visible_recovery", "reference_instructions", "progress_rendering"])
def test_workspace_guidance_in_fresh_process(tmp_path, case):
    environment = dict(os.environ,
        COCHEM_CONFIG=str(tmp_path / "absent-registry.json"),
        COCHEM_ARTIFACT_DIR=str(tmp_path / "artifacts"),
        COCHEM_ARTIFACTS=str(tmp_path / "artifacts"),
        COCHEM_STUDENT_AUTO_SETUP="false", COCHEM_STUDENT_AUTO_REMOTE_CHECK="0")
    result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), case],
                            env=environment, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr


def _exercise(case):
    from cochem_base.theory_matrix import ProductClass
    from ui.voila_layout.cochem_gui import CoChemGUI

    gui = CoChemGUI()
    gui.state.active_view = "matrix"
    gui.config_tabs.selected_index = 1
    if case == "goal_navigation":
        for goal in (ProductClass.PRODUCT_B, ProductClass.PRODUCT_C):
            gui.product_class_selector.value = goal.value
            assert gui.state.active_view == "matrix"
            assert gui.config_tabs.selected_index == 1
            assert goal.value in gui.product_class_card.value
        gui.btn_goal_periodic.click()
        assert gui.state.active_view == "periodic"
        return
    geometry = Path(__file__).resolve().parents[2].joinpath("examples/jobs/water.xyz").read_text()
    gui.matrix_geometry.value = geometry
    before = (gui.charge_input.value, gui.multiplicity_input.value, gui.matrix_geometry.value,
              gui.matrix_method.value, gui.matrix_basis.value, gui.btn_execute.disabled)
    if case == "visible_recovery":
        from html import unescape

        from cochem_base.calc.calculation_service import CalculationMatrixConfig
        from cochem_base.calc.xtb_execution import validate_xtb_config

        gui.matrix_engine.value = "XTB"
        configuration = CalculationMatrixConfig.model_validate(gui._collect_run_config())
        configuration.multiplicity = 2
        with pytest.raises(ValueError) as rejected:
            validate_xtb_config(configuration, ["O", "H", "H"])
        gui._update_footer(rejected.value)
        visible = unescape(gui.footer_message.value.split("<details", 1)[0])
        assert str(rejected.value) in visible
        assert "do not change the molecule's spin" in visible
        # Keep an actual I/O traceback available without flooding the visible
        # recovery instructions with stack frames.
        import traceback

        try:
            Path(os.environ["COCHEM_ARTIFACT_DIR"], "not_uploaded_output.out").read_text()
        except FileNotFoundError:
            diagnostic = traceback.format_exc()
        recovery = "The calculation output could not be opened. Retrieve the completed run's results again."
        gui._update_footer(RuntimeError(recovery + "\n\n" + diagnostic))
        visible = unescape(gui.footer_message.value.split("<details", 1)[0])
        assert recovery in visible
        assert "Traceback (most recent call last)" not in visible
        assert diagnostic in unescape(gui.footer_message.value)
        assert gui.matrix_geometry.value == geometry
        assert gui.multiplicity_input.value == before[1]
        assert not gui._pipeline_running and not gui._actions_running
        return
    if case == "progress_rendering":
        from html import unescape

        # These are protocol-state rendering inputs, not submitted calculations
        # or scientific-result fixtures. The real widget controller must not
        # create an Actions request while explaining uncertain/nonterminal states.
        for status, label in (("prepared", "request prepared"),
                              ("dispatch_unconfirmed", "confirm submission"),
                              ("cancellation_requested", "cancellation requested")):
            observation = {"status": status, "request_id": "unsent-presentation-check"}
            gui._render_student_actions_status(observation)
            visible, details = gui.actions_status.value.split("<details", 1)
            assert label in unescape(visible)
            assert status in details and observation["request_id"] in details
            assert gui._actions_last_status == observation
            assert gui._actions_running and not gui.btn_cancel.disabled
            assert gui.btn_actions_retrieve.disabled
            if status == "dispatch_unconfirmed":
                assert "do not submit it again" in gui.actions_status.value
        assert gui._actions_submission is None and gui._actions_client is None
        assert not hasattr(gui, "_actions_worker")
        assert gui.matrix_geometry.value == geometry
        assert (gui.charge_input.value, gui.multiplicity_input.value) == before[:2]
        return
    if case == "reference_instructions":
        from ui.voila_layout.disclosure import Disclosure

        panel = next(child for child in gui.tab_fragments.children
                     if isinstance(child, Disclosure) and child.get_title(0) == "Provide R2 monomer references")
        panel.toggle.value = True
        guidance = " ".join(getattr(child, "value", "") for child in panel.body.children
                            if isinstance(getattr(child, "value", None), str))
        for phrase in ("ZIP", "manifest", "CCSD(T)", "both basis sizes", "atom order", "starting XYZ"):
            assert phrase in guidance
        assert "Student_Research_No_Code.md#use-reference-dependent-protocols-when-assigned" in guidance
        assert gui.scientific_r2_upload in panel.body.children
        assert gui.btn_clear_r2_attachment in panel.body.children
        panel.toggle.value = False
        assert (gui.charge_input.value, gui.multiplicity_input.value, gui.matrix_geometry.value,
                gui.matrix_method.value, gui.matrix_basis.value, gui.btn_execute.disabled) == before
        return
    if case == "choice_labels":
        # A valid None-valued solvent and the unavailable-engine prompt must
        # remain named in the UI, without changing their underlying values.
        assert gui.matrix_engine.value is None
        assert gui.matrix_engine.label
        assert gui.btn_execute.disabled
        for solvent in (None, "CPCM(Water)", None):
            gui.matrix_solvation.value = solvent
            assert gui.matrix_solvation.value == solvent
            assert gui.matrix_solvation.label
            if solvent is None:
                assert "Gas phase" in gui.matrix_solvation.label
        gui.matrix_engine.value = "XTB"
        gui.matrix_engine.value = None
        assert gui.matrix_engine.label
        assert gui.btn_execute.disabled
        return
    if case == "help_preserves_draft":
        gui.btn_terms.click()
        assert gui.state.active_view == "guide"
        assert gui.main_content.children == (gui.footer, gui.view_guide)
        gui.btn_matrix.click()
        assert gui.config_tabs.selected_index == 1
        assert gui.t9_disclosure.selected_index is None
        gui.t9_disclosure.toggle.value = True
        assert gui.t9_disclosure.body.layout.display != "none"
        gui.t9_disclosure.toggle.value = False
        assert gui.t9_disclosure.body.layout.display == "none"
    elif case == "input_disclosure":
        for section in (gui.input_pool_disclosure, gui.input_inbox_disclosure,
                        gui.manual_geometry_disclosure, gui.monomer_assembly_disclosure):
            assert section.selected_index is None
            section.toggle.value = True
            assert section.body.layout.display != "none"
            section.toggle.value = False
        assert gui.input_upload in gui.input_upload_section.children
        assert gui.input_kind in gui.input_upload_section.children
    else:
        raise ValueError("Unknown workspace guidance case")
    after = (gui.charge_input.value, gui.multiplicity_input.value, gui.matrix_geometry.value,
             gui.matrix_method.value, gui.matrix_basis.value, gui.btn_execute.disabled)
    assert after == before
    assert not gui._pipeline_running and not gui._actions_running


if __name__ == "__main__":
    _exercise(sys.argv[1])
