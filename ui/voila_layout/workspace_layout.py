"""Task-focused presentation of existing, scientifically gated controllers.

Only navigation, explanatory content and visibility live here. Calculations,
input validation, capability checks and retained data stay with their owners.
"""
from __future__ import annotations

import html
from typing import Any

import ipywidgets as widgets

from ui.voila_layout.disclosure import Disclosure
from ui.voila_layout.learning import build_glossary, help_html, hint_html


def _text(value: str) -> widgets.HTML:
    return widgets.HTML(value)


def _help(topic: str) -> widgets.HTML:
    return _text(hint_html(topic) + help_html(topic))


def _heading(title: str, summary: str) -> widgets.HTML:
    return _text(f"<h2>{html.escape(title)}</h2><p>{html.escape(summary)}</p>").add_class("cochem-page-heading")


def _section(title: str, *children: widgets.Widget) -> widgets.VBox:
    return widgets.VBox([_text(f"<h3>{html.escape(title)}</h3>"), *children]).add_class("cochem-section")


def _actions(*buttons: widgets.Widget) -> widgets.HBox:
    return widgets.HBox(list(buttons)).add_class("cochem-actions")


def _navigate(gui: Any, view: str, title: str, tab: int | None = None) -> widgets.Button:
    button = widgets.Button(description=title, button_style="primary", layout=widgets.Layout(width="auto"))

    def go(_: Any) -> None:
        if tab is not None:
            gui.config_tabs.selected_index = tab
        gui.state.active_view = view

    button.on_click(go)
    return button


def _setup(gui: Any) -> None:
    gui.btn_remote_engine_check.button_style = "primary"
    gui.btn_setup_retry.button_style = ""
    gui.gh_setup_box.layout.border = ""
    gui.gh_setup_box.layout.padding = "0"
    gui.gh_setup_box.children = (
        _text("<h3>Check calculation access</h3><p>Check which licensed programs this project can download. "
              "ORCA and CFOUR are optional and strongly recommended; free methods remain available without them.</p>"),
        *gui.gh_setup_box.children[1:],
    )
    gui.local_setup_box.layout.border = ""
    gui.local_setup_box.children = (
        _text("<h3>Programs on your calculation computer</h3><p>Use <b>Find installed engines</b> to locate ORCA or CFOUR. "
              "If a program is installed elsewhere, select its executable path below.</p>"),
        gui.bin_orca, gui.bin_cfour, _actions(gui.btn_detect_bins, gui.btn_save_bins), gui.local_setup_output,
    )
    gui.install_input_upload.description = "Upload Hessian bundle"
    gui.advanced_local_setup.body.children = (
        _help("hessian"), gui.install_input_upload, *gui.advanced_local_setup.body.children,
    )
    gui.local_install_options.children = (
        gui.license_mode, gui.licensed_engine_status, gui.advanced_local_setup,
        Disclosure("Installation log", gui.install_output),
    )
    gui.btn_continue_inputs = _navigate(gui, "inputs", "Continue to Your files")
    gui.view_install.children = (
        _heading("Start here", "Prepare your workspace, then bring in your own structures and research data."),
        _text("<ol class='cochem-steps'><li><strong>1 · Check access</strong><span>Choose where the chemistry runs.</span></li>"
              "<li><strong>2 · Add your files</strong><span>Inspect the structure and its electronic state.</span></li>"
              "<li><strong>3 · Calculate and interpret</strong><span>Choose a task, then inspect its evidence.</span></li></ol>"),
        _section("Where will calculations run?", gui.calc_env_dropdown, _help("workspace"),
                 Disclosure("Where this interface runs", gui.interact_env_dropdown)),
        gui.dynamic_setup_container, gui.local_install_options, gui.run_install_btn,
        gui.student_setup_panel, _actions(gui.btn_continue_inputs),
    )
    gui.student_setup_panel.layout.border = ""
    gui.student_setup_panel.layout.padding = "0"
    gui.student_setup_panel.add_class("cochem-section")
    gui.student_setup_panel.children = (
        _text("<h3>CoChem tools and updates</h3><p>BASE installs and connects TOPOS and TORQ here. "
              "Use <b>Check for updates</b> when your instructor announces a fix. No terminal commands are needed.</p>"),
        *gui.student_setup_panel.children[1:],
    )

    def route_changed(_: Any = None) -> None:
        gui.run_install_btn.layout.display = "none" if gui.calc_env_dropdown.value == "github-actions" else ""

    gui.calc_env_dropdown.observe(route_changed, names="value")
    route_changed()


def _inputs(gui: Any) -> None:
    gui.input_upload.button_style = "primary"
    gui.input_library_choice.description = "Your uploaded file:"
    gui.input_kind.description = "File contents:"
    gui.input_upload_section = _section("1 · Upload a scientific file",
        _text("<p>Start with <b>Detect from file</b> for ordinary molecular files. "
              "For conformer pools or specialized data, select the matching contents first.</p>"),
        gui.input_kind, gui.input_pool_producer, gui.input_pool_energy_unit, gui.input_upload,
        _text(help_html("scientific_inputs")), gui.input_library_status)
    gui.input_inbox_disclosure = Disclosure("Import from the VS Code inbox",
        _text("<p>You can also drag files into the course inbox in VS Code. Import once, or watch the folder for new files.</p>"),
        _actions(gui.btn_inbox_scan, gui.btn_inbox_watch, gui.btn_inbox_stop))
    gui.input_pool_disclosure = Disclosure("Combine conformer ensembles and remove duplicates",
        _text("<p>Select the ensembles to compare. Structures must have compatible composition and declared energy units. "
              "Energy ranking also needs a common method, charge and spin state.</p>"),
        gui.input_pool_choices, gui.input_pool_declare_context, gui.input_pool_context_box,
        gui.btn_sieve_inputs, gui.input_pool_status, gui.input_unique_conformer, gui.btn_use_unique_conformer)
    gui.btn_continue_calculation_settings = _navigate(gui, "matrix", "Continue to calculation settings", tab=1)
    gui.view_inputs.children = (
        _heading("Your files", "Upload your scientific inputs, inspect them, and choose what to use next."),
        gui.input_upload_section, gui.input_library_rejections,
        _section("2 · Choose a structure or dataset", gui.input_library_choice,
                 gui.input_record_choice, gui.input_management_controls, gui.btn_use_input_geometry,
                 _text("<p class='cochem-hint'>For a molecular calculation, select a structure and choose "
                       "<b>Use selected starting geometry</b>. Check charge and spin in Calculations. "
                       "For spectra, Hessians or periodic data, choose the corresponding tool in the navigation.</p>"),
                 gui.btn_continue_calculation_settings),
        Disclosure("File details and provenance", _text(help_html("provenance")), gui.input_library_table, gui.btn_input_refresh),
        gui.input_inbox_disclosure, gui.input_pool_disclosure,
    )


def _molecular_settings(gui: Any) -> None:
    gui.charge_input.description = "Total charge:"
    gui.multiplicity_input.description = "Spin multiplicity:"
    gui.matrix_tier.description = "Theory family:"
    gui.matrix_solvation.description = "Surroundings:"
    selected_solvent = gui.matrix_solvation.value
    gui.matrix_solvation.options = [("Gas phase (no solvent model)", None), ("Water (CPCM)", "CPCM(Water)"),
        ("Acetone (CPCM)", "CPCM(Acetone)"), ("Ethanol (CPCM)", "CPCM(Ethanol)")]
    gui.matrix_solvation.value = selected_solvent
    gui.t9_disclosure = Disclosure("Advanced: multireference spin recovery (T9)",
        _help("active_space"), gui.t9_panel)
    gui.t9_panel.children = gui.t9_panel.children[1:]
    gui.tab_base.children = (
        _section("Electronic state", _actions(gui.charge_input, gui.multiplicity_input), _help("charge_spin")),
        _section("Method and basis", gui.matrix_engine, gui.engine_warning,
                 gui.matrix_tier, _text(help_html("theory_tiers")),
                 gui.matrix_method, gui.matrix_basis, _help("method_basis")),
        _section("Surroundings", gui.matrix_solvation, _help("solvent")),
        gui.cfour_operation, gui.dispersion_warning,
        Disclosure("Advanced: complete-basis extrapolation", gui.matrix_cbs_pair,
                   _text("<p>CBS means complete basis set. This uses a specified pair of basis sizes to estimate "
                         "the correlation-energy limit. It requires the corresponding calculations; choosing a pair "
                         "does not certify that extrapolation has been performed.</p>")),
        gui.t9_disclosure,
    )
    # Reopening optional controls never changes their calculation values.
    def recovery_changed(change: Any) -> None:
        if change["new"]:
            gui.t9_disclosure.selected_index = 0

    gui.t9_enable.observe(recovery_changed, names="value")
    gui.manual_geometry_disclosure = Disclosure("Edit XYZ coordinates directly", gui.matrix_geometry,
        _text("<p>Coordinates are in ångströms. Edits affect the current calculation draft; the uploaded original remains available. "
              "Check atom order, charge and spin after editing.</p>"))
    gui.monomer_assembly_disclosure = Disclosure("Build a starting complex from your monomers",
        _text("<p>Save each monomer's charge and spin first. This places the selected monomers apart without changing "
              "their internal structures. It produces an initial guess, not an optimized or bound complex.</p>"),
        gui.student_monomer_choices, gui.student_seed_separation, gui.btn_assemble_monomers)
    gui.viewer_output.layout.width = "100%"
    gui.viewer_output.layout.max_width = "100%"
    gui.geometry_charge = widgets.IntText(description="Structure charge:")
    gui.geometry_multiplicity = widgets.IntText(description="Structure multiplicity:")
    gui._geometry_state_links = (
        widgets.link((gui.charge_input, "value"), (gui.geometry_charge, "value")),
        widgets.link((gui.multiplicity_input, "value"), (gui.geometry_multiplicity, "value")),
    )
    gui.tab_builder.children = (
        widgets.VBox([
            _text("<h3>Starting structure</h3><p>Use a file from <b>Your files</b>, or upload an XYZ here. "
                  "Confirm the identity and electronic state before calculating.</p>"),
            gui.xyz_upload, gui.student_geometry_choice, gui.geometry_management_controls,
            gui.student_input_role, gui.student_input_label,
            _actions(gui.geometry_charge, gui.geometry_multiplicity), _help("charge_spin"),
            Disclosure("Assign atoms to monomers", gui.student_fragment_atoms, _text(help_html("fragments_constraints"))),
            gui.btn_save_input_details, gui.student_upload_status,
            gui.monomer_assembly_disclosure,
            Disclosure("Build from a name or SMILES", _text("<p>Use a molecule name or line notation to generate a starting guess. "
                "Inspect the geometry and verify its charge and spin before use.</p>"), gui.smiles_input, gui.btn_build_smiles),
            gui.manual_geometry_disclosure,
        ], layout=widgets.Layout(width="58%")),
        widgets.VBox([_text("<h3>Structure preview</h3><p class='cochem-hint'>Drag to rotate; scroll to zoom. "
            "Drawn bonds help inspect geometry; they are not calculated bond orders.</p>"), gui.viewer_output],
            layout=widgets.Layout(width="40%")),
    )
    gui.tab_builder.add_class("cochem-structure-columns")
    gui.config_tabs.set_title(0, "Starting structure")
    gui.config_tabs.set_title(4, "Monomer constraints")
    gui.tab_fragments.children = (
        _text("<h3>What may move during optimization?</h3>"), _help("fragments_constraints"),
        gui.btn_detect_fragments, gui.fragments_output, gui.cb_recipe_r1, gui.cb_recipe_r2,
        gui.scientific_input_status,
        Disclosure("Provide R2 monomer references", gui.scientific_r2_upload, gui.btn_clear_r2_attachment),
        Disclosure("Choose starting curvature for optimization", _help("hessian"), gui.scientific_initial_hessian,
                   gui.scientific_read_upload, gui.btn_clear_read_attachment),
        Disclosure("Generated ORCA constraints", gui.fragment_preview),
    )


def _calculations(gui: Any) -> None:
    gui.btn_goal_periodic = _navigate(gui, "periodic", "Open periodic-structure calculations")
    gui.product_class_selector.options = [
        ("Molecular screening in solution (Product A)", "Product A (Lead Screening)"),
        ("Periodic materials and solids (Product B)", "Product B (Materials and Extended Solids)"),
        ("Spectroscopic calibration (Product C)", "Product C (Absolute Spectroscopic Calibration)"),
        ("Exploratory calculation — no accuracy certification", "Screening (no product accuracy claim)"),
    ]
    gui.product_class_selector.description = "Scientific goal:"
    gui.goal_guidance = _text("")

    def goal_changed(_: Any = None) -> None:
        periodic = "Product B" in gui.product_class_selector.value
        gui.btn_goal_periodic.layout.display = "" if periodic else "none"
        gui.goal_guidance.value = (
            "<p class='cochem-hint'>Use the Periodic structures tool for a repeating solid and its unit cell. "
            "Your current molecular settings are retained.</p>" if periodic else
            "<p class='cochem-hint'>The goal applies scientific requirements. It is not an accuracy guarantee. "
            "For a basic gas-phase exercise, use Exploratory calculation and your assigned method.</p>")

    gui.product_class_selector.observe(goal_changed, names="value")
    goal_changed()
    gui.actions_operation.description = "Calculate:"
    gui.native_operation.description = "Calculate:"
    gui.actions_job_options.children = (gui.actions_operation, _text(help_html("calculation_types")), *gui.actions_job_options.children[1:])
    gui.native_job_options.children = (gui.native_operation, _text(help_html("calculation_types")),
        Disclosure("Time limit and frequency guidance", *gui.native_job_options.children[1:]))
    gui.matrix_config_panel.layout.border = ""
    gui.matrix_config_panel.layout.padding = "0"
    gui.molecular_operation_controls = widgets.VBox([gui.actions_job_options, gui.native_job_options])
    gui.matrix_config_panel.children = (
        gui.calculation_environment_status, gui.molecular_operation_controls,
        gui.config_tabs, gui.output_config_box, gui.output_destination_guidance, gui.configuration_export,
    )
    gui.project_name.description = "Calculation label:"
    gui.project_name.layout.width = "100%"
    gui.project_name.placeholder = "Optional label, for example water-dimer-scan"
    gui.context_summary = _text("").add_class("cochem-selection")

    def refresh_context(_: Any = None) -> None:
        from cochem_base.geometry.nuclide_geometry import parse_geometry_identity

        record = gui._student_uploads.get(gui.student_geometry_choice.value, {})
        label = str(record.get("label") or record.get("filename") or "Current structure")
        try:
            identity = parse_geometry_identity(gui.matrix_geometry.value)
            description = f"{label} · {len(identity.elements)} atoms · charge {gui.charge_input.value} · multiplicity {gui.multiplicity_input.value}"
        except (ValueError, TypeError):
            description = "No valid starting structure selected. Open Your files to upload and select one."
        gui.context_summary.value = "<p><strong>Calculation input</strong><br>" + html.escape(description) + "</p>"

    for field in (gui.matrix_geometry, gui.student_geometry_choice, gui.charge_input, gui.multiplicity_input):
        field.observe(refresh_context, names="value")
    refresh_context()
    gui.goal_section = _section("Calculation goal", gui.product_class_selector, gui.goal_guidance, gui.btn_goal_periodic,
                               Disclosure("Scientific requirements for this goal", gui.product_class_card))
    gui.view_matrix.children = (
        _heading("Calculations", "Choose your scientific question, check the starting structure, then select a supported method."),
        gui.context_summary,
        gui.goal_section,
        gui.matrix_config_panel, gui.slurm_panel, gui.telemetry_panel,
    )
    gui.telemetry_panel.layout.border = ""
    gui.telemetry_panel.layout.padding = "0"
    gui.telemetry_panel.add_class("cochem-section")
    gui.telemetry_panel.children = (gui.telemetry_panel.children[0], _text(help_html("convergence_frequencies")),
                                    *gui.telemetry_panel.children[1:])

    def tool_changed(_: Any = None) -> None:
        module_tool = gui.config_tabs.selected_index in (2, 3)
        gui.goal_section.layout.display = "none" if module_tool else ""
        gui.molecular_operation_controls.layout.display = "none" if module_tool else ""
        gui.btn_execute.layout.display = "none" if module_tool else ""
        gui.execution_description.layout.display = "none" if module_tool else ""
        gui.telemetry_panel.children[0].value = "<h3>Current calculation</h3>" if module_tool else "<h3>Run calculation</h3>"

    gui.config_tabs.observe(tool_changed, names="selected_index")
    tool_changed()


def _inspection(gui: Any) -> None:
    gui.btn_parse_inspector.description = "Read calculated properties"
    gui.inspector_tabs.set_title(0, "Rotational constants")
    gui.inspector_tabs.set_title(1, "Isotope effects")
    gui.inspector_banner.value = (
        "<p>Compare like quantities: equilibrium rotational constants describe the calculated geometry; "
        "ground-state constants include vibrational effects.</p>"
        "<details class='cochem-help'><summary>Explain equilibrium Bₑ and ground-state B₀</summary>"
        "<p>Rotational constants depend on the distribution of mass. Bₑ is calculated at an equilibrium geometry. "
        "B₀ describes the vibrational ground state and includes vibrational corrections. An experimental ground-state "
        "constant should not be compared directly with an uncorrected Bₑ as if they were the same quantity. "
        "BASE shows available quantities and their source; missing corrections are not invented.</p></details>")
    isotope = gui.inspector_tabs.children[1]
    isotope.children = (_help("isotopes"), _text(help_html("hessian")), *isotope.children)
    physical = gui.inspector_tabs.children[2]
    physical.children = tuple(child for child in physical.children
        if not isinstance(child, widgets.HTML) or "SWMR HDF5 Concurrency" not in child.value)
    gui.hdf5_results_table.value = (
        "<p>Select an uploaded HDF5 or NPZ file, then choose <b>Inspect HDF5 / NPZ data</b>. "
        "The preview shows up to 100 datasets and 500 values per dataset; your original file stays intact.</p>")
    gui.view_inspector.children = (
        _heading("Spectra and properties", "Read quantities from completed calculations or examine isotope effects using a matching Hessian."),
        _section("Read a calculation output", gui.telemetry_input_upload, gui._input_selectors["telemetry"], gui.btn_parse_inspector),
        gui.inspector_tabs,
    )
    gui.view_periodic.children = (
        _heading("Periodic structures", "Inspect a repeating crystal structure and prepare a supported Quantum ESPRESSO calculation."),
        _help("periodic"), *gui.view_periodic.children[1:],
    )


def apply_workspace_layout(gui: Any) -> None:
    """Compose real controls after ingestion and provider bindings are installed."""
    _setup(gui)
    _inputs(gui)
    _molecular_settings(gui)
    _calculations(gui)
    _inspection(gui)
    glossary = build_glossary()
    glossary.children = glossary.children[1:]
    gui.view_guide = widgets.VBox([
        _heading("Scientific terms", "Find a definition without changing your calculation. Explanations also appear beside the relevant settings."),
        glossary,
    ])
    gui.btn_terms = _navigate(gui, "guide", "Scientific terms")
    gui.btn_terms.button_style = ""
    gui.sidebar.children = (
        _text("<p class='cochem-nav-label'>RESEARCH WORKSPACE</p>"),
        gui.btn_install, gui.btn_inputs, gui.btn_matrix, gui.btn_modules,
        _text("<p class='cochem-nav-label'>SCIENTIFIC TOOLS</p>"),
        gui.btn_inspector, gui.btn_periodic,
        _text("<p class='cochem-nav-label'>HELP</p>"), gui.btn_terms,
    )
    gui.sidebar.layout.width = "220px"
    gui.header_title.value = "<div class='cochem-brand'><h1>CoChem</h1><p>Computational chemistry workspace</p></div>"
    gui.header.add_class("cochem-header")
    gui.header_status.add_class("cochem-status")
    gui.header_env.add_class("cochem-status")
    gui.footer.add_class("cochem-footer")
    gui.main_content.layout.width = "100%"
    gui.app.pane_widths = ["220px", 1, 0]
    # Place actionable errors before the current form, where they can be found.
    gui.app.footer = None
    gui.app.layout.grid_template_rows = "auto minmax(0, 1fr)"
    for view in (gui.view_install, gui.view_inputs, gui.view_matrix, gui.view_modules,
                 gui.view_inspector, gui.view_periodic, gui.view_guide):
        view.add_class("cochem-page")
    gui._on_status_change({"new": gui.state.system_status})
    gui._on_environment_change({"new": gui.state.environment})
    gui._on_view_change({"new": gui.state.active_view})
