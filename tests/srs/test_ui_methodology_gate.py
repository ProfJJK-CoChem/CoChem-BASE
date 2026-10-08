"""The public dashboard must apply the same non-bypassable molecular guards."""
from cochem_base.theory_matrix import ProductClass
from ui.voila_layout.cochem_gui import CoChemGUI, create_gui, METHOD_MATRIX_TIERS

DIMER = "6\nwater dimer\nO 0 0 0\nH 0.96 0 0\nH -0.24 0.93 0\nO 4 0 0\nH 4.96 0 0\nH 3.76 0.93 0\n"


def test_gui_constructs_with_complete_tier_catalog() -> None:
    assert create_gui() is not None
    gui = CoChemGUI()
    for index in range(10):
        assert METHOD_MATRIX_TIERS[f'T{index}']['methods']
        assert METHOD_MATRIX_TIERS[f'T{index}']['allowed_basis_sets']
    gui.calc_env_dropdown.value = 'github-actions'
    assert {'ORCA', 'CFOUR'}.isdisjoint(value for _, value in gui.matrix_engine.options)
    gui.matrix_engine.value = 'XTB'
    assert gui.matrix_tier.options == ('T1',)
    assert gui.matrix_method.value == 'GFN2-xTB'


def test_ui_closes_dispersion_override_and_materials_misrouting() -> None:
    gui = CoChemGUI()
    gui.matrix_geometry.value = DIMER
    gui.matrix_tier.value = "Legacy / Custom"
    gui.matrix_method.value = "B3LYP"
    gui._check_dispersion_gate()
    assert gui.btn_execute.disabled
    assert gui.unphysical_override.disabled
    gui.unphysical_override.value = True
    assert gui.btn_execute.disabled
    gui._execute_pipeline(None)
    assert gui.state.system_status != "Running Pipeline..."
    gui.unphysical_override.value = False
    gui.product_class_selector.value = ProductClass.PRODUCT_B.value
    assert gui.btn_execute.disabled
    assert "plane-wave/PAW" in gui.dispersion_warning.value


def test_selected_free_configuration_is_preserved_in_portable_request() -> None:
    gui = CoChemGUI()
    gui.calc_env_dropdown.value = 'github-actions'
    gui.gh_repo_input.value = 'course-organization/student-dimer'
    gui.matrix_engine.value = 'XTB'
    gui.matrix_geometry.value = DIMER
    gui.charge_input.value = 2
    gui.multiplicity_input.value = 1
    gui._prepare_actions_job()
    config = gui._last_actions_job['config']
    assert config['geometry'] == DIMER and config['engine'] == 'xtb'
    assert config['method'] == 'GFN2-xTB' and config['basis_set'] == 'built-in'
    assert config['charge'] == 2 and config['multiplicity'] == 1
    assert config['implicit_solvation'] is None and config['theory_tier'] == 'T1'
    assert config['frozen_monomer_indices'] is None and config['is_opt'] is True
    assert not gui._pipeline_running and not gui._actions_running


def test_selected_free_engine_configuration_is_passed_to_cli(tmp_path) -> None:
    import json
    from pathlib import Path

    gui = CoChemGUI()
    gui.artifact_output_path.value = str(tmp_path)
    gui.matrix_geometry.value = DIMER
    gui.matrix_engine.value = 'PYSCF'
    command = gui._build_pipeline_command()
    assert command[2:4] == ["run", "--config"]
    config_path = Path(command[4])
    config = json.loads(config_path.read_text())
    assert config["geometry"] == DIMER
    assert config['engine'] == 'pyscf' and config["method"] == "HF"
    assert config["basis_set"] == "STO-3G"
    assert config["charge"] == 0 and config["multiplicity"] == 1
    assert config["implicit_solvation"] is None
    assert config["theory_tier"] == "T2"
    assert config["frozen_monomer_indices"] is None
    assert "--dry-run" not in command
    assert "--output" in command and "--scratch" in command
