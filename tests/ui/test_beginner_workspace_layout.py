"""Actual-widget beginner navigation and guidance must preserve the science draft."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

from ci_tools.source_quarantine import source_paths


@pytest.mark.parametrize("case", ["guided_navigation", "help_preserves_draft", "advanced_preserves_draft", "persistent_state_and_results", "goal_remains_visible", "displayed_summary_download_bytes"])
def test_beginner_workspace_in_source_child(tmp_path, case):
    source = Path(__file__).resolve().parents[2]
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join(source_paths(source)),
        PYTHONDONTWRITEBYTECODE="1", COCHEM_ARTIFACT_DIR=str(tmp_path / "artifacts"),
        COCHEM_CONFIG=str(tmp_path / "absent-registry.json"), COCHEM_STUDENT_AUTO_SETUP="0",
        COCHEM_STUDENT_AUTO_REMOTE_CHECK="0")
    completed = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), case],
        env=environment, capture_output=True, text=True, timeout=90)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _walk(widget, seen=None):
    seen = set() if seen is None else seen
    if widget.model_id in seen:
        return
    seen.add(widget.model_id)
    yield widget
    for child in getattr(widget, "children", ()):
        yield from _walk(child, seen)


def _draft(gui):
    return (gui.matrix_geometry.value, gui.charge_input.value, gui.multiplicity_input.value,
        gui.matrix_engine.value, gui.matrix_method.value, gui.matrix_basis.value,
        gui.matrix_tier.value, gui.matrix_solvation.value, gui.product_class_selector.value,
        gui.cb_recipe_r1.value, gui.cb_recipe_r2.value,
        gui.native_operation.value, gui.actions_operation.value)


def _exercise(case):
    source = Path(__file__).resolve().parents[2]
    if os.environ.get("COCHEM_SOURCE_QUARANTINE_ROOT"):
        startup = sys.modules.get("sitecustomize")
        assert startup is not None
        assert Path(startup.__file__).resolve() == source / "ci_tools/quarantine_startup/sitecustomize.py"
        state = getattr(sys.modules.get("ci_tools.source_quarantine"), "_active", None)
        assert state is not None and state["copied"] == source
    import ipywidgets as widgets
    from ui.voila_layout.cochem_gui import CoChemGUI
    import ui.voila_layout.cochem_gui as gui_module
    from ui.voila_layout.disclosure import Disclosure

    assert Path(gui_module.__file__).resolve() == source / "ui/voila_layout/cochem_gui.py"
    gui = CoChemGUI()
    for name in ("_student_setup_initial_worker", "_research_capability_worker"):
        worker = getattr(gui, name, None)
        if worker is not None:
            worker.join(timeout=15)
            assert not worker.is_alive()
    raw = b"3\nStudent-provided water starting geometry\nO 0 0 0\nH 0 0 .96\nH .92 0 -.24\n"
    gui.xyz_upload.value = ({"name": "my-molecule.xyz", "type": "chemical/x-xyz", "size": len(raw),
        "content": memoryview(raw), "last_modified": datetime.now(timezone.utc)},)
    gui.matrix_engine.value = "XTB"
    gui.charge_input.value = 1
    gui.multiplicity_input.value = 2
    before = _draft(gui)
    original = Path(gui._student_uploads[gui.student_geometry_choice.value]["path"])
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    assert original.read_bytes() == raw and gui.btn_execute.disabled

    if case == "guided_navigation":
        assert list(gui.guided_step_buttons) == ["install", "inputs", "matrix", "modules"]
        for view, button in gui.guided_step_buttons.items():
            button.click()
            assert gui.state.active_view == view and button.button_style == "primary"
            assert button.description in gui.guided_step_status.value
            assert gui.learning_help.widget in gui.app.header.children
            assert _draft(gui) == before
    elif case == "help_preserves_draft":
        gui.learning_help.search.value = "charge"
        search_before = gui.learning_help.results.children
        buttons = {widget.description: widget for view in (gui.view_install, gui.view_inputs, gui.view_matrix, gui.view_modules)
            for widget in _walk(view) if isinstance(widget, widgets.Button) and widget.description.startswith("Help ·")}
        for title in ("Help · Where does my calculation run?", "Help · How do I check my molecule?",
                      "Help · Walk me through my first calculation", "Help · How do I know what this result means?"):
            buttons[title].click()
            assert buttons[title].description.startswith("Hide help ·")
            answer_container = next(widget for view in (gui.view_install, gui.view_inputs, gui.view_matrix, gui.view_modules)
                for widget in _walk(view) if isinstance(widget, widgets.VBox)
                and len(widget.children) == 2 and widget.children[0] is buttons[title])
            assert 'data-help-topic=' in answer_container.children[1].value
            assert gui.learning_help.search.value == "charge" and gui.learning_help.results.children == search_before
            buttons[title].click()
            assert answer_container.children[1].layout.display == "none"
            assert _draft(gui) == before
        gui.learning_help.search.value = "charge"
        assert gui.learning_help.results.children
        gui.learning_help.clear.click()
        assert gui.learning_help.search.value == "" and _draft(gui) == before
    elif case == "advanced_preserves_draft":
        for section in (gui.advanced_goal, gui.advanced_tools, gui.t9_disclosure):
            assert section.selected_index is None
            section.toggle.value = True
            section.toggle.value = False
            assert _draft(gui) == before
        tool_buttons = [child for child in _walk(gui.advanced_tools) if isinstance(child, widgets.Button)
            and child.description in {"Other structures and energies", "Distance scans and bonding", "Monomer constraints"}]
        assert len(tool_buttons) == 3
        for button in tool_buttons:
            button.click()
            assert gui.config_tabs.selected_index in (2, 3, 4)
            assert _draft(gui) == before
    elif case == "persistent_state_and_results":
        assert "charge 1" in gui.guided_input_summary.value and "multiplicity 2" in gui.guided_input_summary.value
        assert not isinstance(gui.guided_current, Disclosure)
        assert gui.guided_cancel.disabled == gui.btn_cancel.disabled
        assert gui.guided_cancel in tuple(_walk(gui.guided_current))
        assert "XTB" in gui.guided_draft_status.value and "GFN2-xTB" in gui.guided_draft_status.value
        gui.guided_step_buttons["modules"].click()
        current_results = tuple(_walk(gui.view_modules))
        assert gui.calculation_result in current_results and gui.actions_controls in current_results
        assert "No accepted calculation result" in gui.calculation_result.value
        assert gui.btn_actions_retrieve.disabled and gui.guided_cancel.disabled
        assert gui.footer in gui.main_content.children
        assert _draft(gui) == before
    elif case == "goal_remains_visible":
        assert gui.guided_goal_status in gui.guided_current.children
        for selected in ("Product A (Lead Screening)", "Product B (Materials and Extended Solids)",
                         "Product C (Absolute Spectroscopic Calibration)", "Screening (no product accuracy claim)"):
            gui.product_class_selector.value = selected
            expected = _draft(gui)
            for button in gui.guided_step_buttons.values():
                button.click()
                assert selected in gui.guided_goal_status.value
                assert "requirements still apply" in gui.guided_goal_status.value
                assert _draft(gui) == expected
            gui.advanced_goal.toggle.value = True
            gui.advanced_goal.toggle.value = False
            assert _draft(gui) == expected
    elif case == "displayed_summary_download_bytes":
        import base64
        import html
        import re
        from ui.voila_layout.workspace_layout import _displayed_result_download

        assert gui.result_summary_download.value == ""  # No fabricated live accepted result.
        archived = source / "tests/data/orca_6_1_1_water_hf_sto3g/water.out.txt"
        archived_digest = hashlib.sha256(archived.read_bytes()).hexdigest()
        actual_text = archived.read_text(encoding="utf-8")
        # Render authentic archived output in a standalone actual HTML widget.
        # This tests the text export, not a newly executed/accepted calculation.
        displayed = widgets.HTML("<pre>" + html.escape(actual_text) + "</pre>")
        exported = widgets.HTML(_displayed_result_download(displayed.value))
        assert "download='cochem-displayed-result-summary.txt'" in exported.value
        assert "data:text/plain;charset=utf-8;base64," in exported.value
        data = base64.b64decode(re.search(r"base64,([^']+)'", exported.value).group(1), validate=True)
        content = data.decode("utf-8")
        assert actual_text.strip() in content
        assert "does not contain native output files or a provenance backup" in content
        assert hashlib.sha256(archived.read_bytes()).hexdigest() == archived_digest
        assert gui.result_summary_download.value == "" and _draft(gui) == before
    else:
        raise ValueError(case)
    assert hashlib.sha256(original.read_bytes()).hexdigest() == digest
    assert not gui._pipeline_running and not gui._actions_running and not gui._topos_running


if __name__ == "__main__":
    _exercise(sys.argv[1])
