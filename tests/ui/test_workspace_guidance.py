"""Real widget actions preserve scientific drafts while exposing useful help."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("case", ["goal_navigation", "help_preserves_draft", "input_disclosure"])
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
