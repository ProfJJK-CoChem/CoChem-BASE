"""Student-facing research layouts, using BASE's existing calculation controls.

This module changes presentation and draft selection only. Capability checks,
request validation, calculation dispatch and saved scientific data stay with
the existing controllers.
"""
from __future__ import annotations

import html
from typing import Any, Iterable, Mapping

import ipywidgets as widgets

from ui.voila_layout.disclosure import Disclosure
from ui.voila_layout.learning import help_html

OPERATION_LABELS = {
    "energy": "Calculate energy at this geometry",
    "gradient": "Calculate energy and gradients",
    "optimize": "Optimize geometry",
    "search": "Search for other conformers",
    "frequency": "Calculate harmonic vibrational frequencies",
    "thermochemistry": "Calculate thermal corrections and free energy",
    "association": "Search for arrangements of the monomers",
    "matrix": "Optimize with a predefined method",
    "research_scan": "Scan the distance between two monomers",
    "wiberg_lowdin": "Wiberg bond indices (Löwdin basis)",
    "wiberg_nao": "Wiberg bond indices (natural atomic orbitals)",
    "nbo_analysis": "Natural Bond Orbital (NBO) analysis",
    "geometry_analysis": "Inspect geometry",
}

_OPERATION_HELP = {
    "energy": "Calculate the electronic energy without moving the atoms.",
    "gradient": "Calculate the electronic energy and its derivatives with respect to atom positions. Forces are the negatives of those derivatives.",
    "optimize": "Move the atoms to search for a nearby energy minimum. A frequency calculation is needed to check whether the optimized structure is a minimum.",
    "search": "Try several starting arrangements and calculate candidate conformers. Compare accepted results in Results.",
    "frequency": "Calculate harmonic vibrational frequencies. Start from a geometry optimized with the same method; the calculation checks whether it meets the required convergence criteria.",
    "thermochemistry": "Calculate harmonic thermal corrections and free energy at the selected temperature. This requires a suitably optimized geometry and a valid frequency calculation.",
    "association": "Search for arrangements of the monomers in your complex. Check each monomer's charge and multiplicity before starting.",
    "matrix": "Choose a predefined combination of method, basis and optimization settings from the installed module.",
}


def _details(title: str, *children: widgets.Widget) -> Disclosure:
    return Disclosure(title, *children)


def _wrap(*children: widgets.Widget) -> widgets.Box:
    return widgets.Box(list(children), layout=widgets.Layout(
        display="flex", flex_flow="row wrap", gap="8px", width="100%"
    )).add_class("cochem-actions")


def _hint(message: str) -> widgets.HTML:
    return widgets.HTML("<p>" + message + "</p>").add_class("cochem-hint")


def _help(title: str, content: str) -> widgets.HTML:
    """Keep teaching beside the decision, accessible without hover or a new page."""
    return widgets.HTML(
        '<details class="cochem-help"><summary>' + html.escape(title)
        + "</summary>" + content + "</details>"
    )


def _step(title: str, *children: widgets.Widget) -> widgets.VBox:
    return widgets.VBox([
        widgets.HTML("<h4>" + html.escape(title) + "</h4>"), *children,
    ]).add_class("cochem-step")


def _readable_controls(*controls: widgets.Widget) -> None:
    for control in controls:
        control.layout.max_width = "100%"
        if isinstance(control, widgets.Button):
            control.layout.width = "auto"
        elif hasattr(control, "description"):
            control.style.description_width = "initial"


def research_capabilities_html(observations: Iterable[Mapping[str, Any]]) -> str:
    """Summarize real installation observations without granting capabilities."""
    summaries, technical = [], []
    for item in observations:
        module = str(item.get("module_id", "Module")).upper()
        operations = list(item.get("operations", []))
        if item.get("status") == "installed" and operations:
            names = [OPERATION_LABELS[operation] for operation in operations
                     if operation in OPERATION_LABELS]
            message = "; ".join(names) or "Additional operations are installed."
            summaries.append(f"<li><b>{html.escape(module)}</b>: {html.escape(message)}</li>")
        else:
            summaries.append(f"<li><b>{html.escape(module)}</b>: not ready. Open Start here, finish setup, then check availability again.</li>")
        reason = str(item.get("reason", ""))
        technical.append(f"<li>{html.escape(module)}: {html.escape(str(item.get('status', 'unavailable')))}"
                         + (f" — {html.escape(reason)}" if reason else "") + "</li>")
    if not summaries:
        return "<p role='status'>Research modules are not ready. Open Start here to finish installation.</p>"
    return ("<p>Installed module functions are listed below. Engine access and your input are checked separately before a calculation can start.</p><ul>"
            + "".join(summaries) + "</ul><details><summary>Installation details for troubleshooting</summary><ul>"
            + "".join(technical) + "</ul></details>")


def bond_analysis_help_html(reasons: Mapping[str, Any]) -> str:
    """Keep exact bond-analysis definitions and hide lengthy diagnostics."""
    names = [OPERATION_LABELS.get(name, name.replace("_", " ")) for name in reasons]
    summary = ("Currently unavailable: " + "; ".join(names) + ". " if names else "")
    details = "".join(f"<li><b>{html.escape(OPERATION_LABELS.get(name, name.replace('_', ' ')))}</b>: "
                      f"{html.escape(str(reason))}</li>" for name, reason in reasons.items())
    return ("<p>" + html.escape(summary)
            + "Only available analyses can be started. For a disabled analysis, check installation in Start here; NBO also requires its supported orbital-analysis program.</p>"
            + ('<details class="cochem-help"><summary>Why these analyses are unavailable</summary><ul>' + details + "</ul></details>" if details else ""))


def build_topos_panel(gui: Any) -> widgets.VBox:
    """Keep the relevant chemistry choices visible for the selected operation."""
    gui.research_topos_operation.description = "Calculation:"
    gui.research_topos_engine.description = "Method:"
    gui.research_matrix_recipe.description = "Predefined method:"
    gui.btn_research_refresh.description = "Check available calculations"
    gui.btn_research_fragment_states.description = "Check monomer charges and spins"
    gui.btn_research_topos.description = "Start TOPOS calculation"
    gui.research_operation_help = widgets.HTML().add_class("cochem-hint")
    gui.research_topos_method_section = widgets.VBox([
        gui.research_topos_engine,
        _hint("Use the method specified for your study. Compare structures calculated with the same method."),
        widgets.HTML(help_html("method_basis")),
    ])
    gui.research_matrix_section = widgets.VBox([
        gui.research_matrix_recipe,
        _hint("A predefined method supplies a complete combination of calculation settings. Choose the one required for your study."),
        _details("About predefined methods", gui.research_matrix_guidance),
    ])
    gui.research_candidate_section = widgets.VBox([
        gui.research_candidates,
        _hint("More starting candidates explore more arrangements and require more calculations. A search can still miss the lowest-energy structure."),
        _help("What is a conformer?", "<p>Conformers have the same chemical connectivity but different arrangements of their atoms. "
              "A search produces candidates; optimization and frequency checks are needed before treating them as distinct minima. "
              "Keep the search method and settings with your comparison.</p>"),
    ])
    gui.research_monomer_section = widgets.VBox([
        _hint("A monomer is one molecule or ion within the complex. Check its charge and spin state before searching for arrangements."),
        gui.btn_research_fragment_states, gui.research_fragment_states,
        widgets.HTML(help_html("fragments_constraints")),
        _help("How do I choose a monomer's charge and multiplicity?",
              "<p>Charge is the net electrical charge of that monomer, such as 0 for a neutral molecule or −1 for a singly charged anion. "
              "Monomer charges must add up to the charge of the whole complex. Multiplicity is 2S + 1, where S is the total electron spin: "
              "1 is a singlet and 2 is a doublet. Check radicals and ions with your instructor; charge alone does not determine multiplicity.</p>"),
    ])

    def show_operation(change: Any = None) -> None:
        operation = gui.research_topos_operation.value
        gui.research_operation_help.value = "<p>" + html.escape(_OPERATION_HELP.get(
            operation, "Finish setup to see available calculations. Then select a starting geometry and choose a calculation here.")) + "</p>"
        gui.research_topos_engine.layout.display = "none" if operation == "matrix" else ""
        gui.research_topos_method_section.layout.display = "none" if operation == "matrix" else ""
        gui.research_matrix_section.layout.display = "" if operation == "matrix" else "none"
        gui.research_candidates.layout.display = "" if operation in {"search", "association"} else "none"
        gui.research_candidate_section.layout.display = "" if operation in {"search", "association"} else "none"
        gui.research_monomer_section.layout.display = "" if operation == "association" else "none"
        # The same temperature control is also used by Results; keep it
        # available there instead of hiding the shared widget itself.
        gui.research_topos_temperature.layout.display = "" if operation == "thermochemistry" else "none"

    gui.research_topos_temperature = widgets.VBox([
        gui.research_temperature,
        _hint("Thermal corrections depend on temperature. Use the same temperature for every structure you plan to compare."),
        _help("What does a harmonic thermochemistry calculation assume?",
              "<p>Vibrations are approximated as small motions around a minimum. Very soft motions in weakly bound complexes can make "
              "this approximation unreliable. Review the frequencies and the reported temperature and standard state before interpreting free energies.</p>"),
    ])
    gui.research_topos_operation.observe(show_operation, names="value")
    show_operation()
    _readable_controls(gui.research_topos_operation, gui.research_topos_engine,
                       gui.research_matrix_recipe, gui.btn_research_topos,
                       gui.btn_research_fragment_states, gui.btn_research_refresh,
                       gui.research_candidates, gui.research_temperature)
    return widgets.VBox([
        widgets.HTML("<h3>Structures and energies · TOPOS</h3><p>Use your selected starting structure to calculate an energy, refine its geometry or explore other arrangements.</p>"),
        _step("1. Choose what to calculate", gui.research_topos_operation,
              gui.research_operation_help, widgets.HTML(help_html("calculation_types"))),
        _step("2. Set the calculation conditions", gui.research_topos_method_section,
              gui.research_matrix_section, gui.research_candidate_section,
              gui.research_topos_temperature, gui.research_monomer_section),
        _step("3. Run and review", _wrap(gui.btn_research_topos),
              _hint("Review the calculation status below. Completed energy tables and available diagrams appear in Results.")),
        gui.research_status,
        _details("Available calculations and setup help", gui.research_capabilities, gui.btn_research_refresh),
    ]).add_class("cochem-section")


def build_torq_panel(gui: Any) -> widgets.VBox:
    """Separate distance scans from bond analysis and show status in both tools."""
    gui.research_scan_method.description = "Method:"
    gui.research_scan_basis.description = "Basis set:"
    gui.research_scan_start.description = "Start distance (Å):"
    gui.research_scan_end.description = "End distance (Å):"
    gui.research_scan_points.description = "Number of points:"
    gui.research_orbital_backend.description = "NBO / NAO program:"
    gui.btn_research_torq.description = "Start distance scan"
    gui.btn_research_nbo.description = "Calculate NBO analysis"
    gui.btn_research_wiberg.description = "Calculate Löwdin Wiberg indices"
    gui.btn_research_wiberg_nao.description = "Calculate NAO Wiberg indices"
    _readable_controls(gui.research_scan_method, gui.research_scan_basis,
                       gui.research_scan_start, gui.research_scan_end, gui.research_scan_points,
                       gui.research_orbital_backend, gui.btn_research_torq,
                       gui.btn_research_nbo, gui.btn_research_wiberg,
                       gui.btn_research_wiberg_nao)
    gui.research_scan_summary = widgets.HTML().add_class("cochem-hint")

    def show_sampling(change: Any = None) -> None:
        start, end = gui.research_scan_start.value, gui.research_scan_end.value
        count = gui.research_scan_points.value
        if end <= start:
            gui.research_scan_summary.value = (
                "<p role='alert'>Choose an end distance greater than the start distance. "
                "The current range cannot be submitted.</p>"
            )
        else:
            spacing = (end - start) / (count - 1)
            gui.research_scan_summary.value = (
                f"<p role='status'>{count} energy calculations, spaced {spacing:.4g} Å apart, "
                "including both end points. More points increase calculation time.</p>"
            )

    for control in (gui.research_scan_start, gui.research_scan_end, gui.research_scan_points):
        control.observe(show_sampling, names="value")
    show_sampling()
    scan = widgets.VBox([
        _step("2. Set the distance range",
              _hint("Select a complex containing two monomers. Distances are measured between their centers of mass in ångströms (Å). Each monomer keeps its internal geometry and orientation."),
              _wrap(gui.research_scan_start, gui.research_scan_end), gui.research_scan_points,
              gui.research_scan_summary,
              _help("How should I choose the range and number of points?",
                    "<p>Choose a range that covers the feature you want to study. For a potential-energy well, include points on both "
                    "sides of the suspected minimum. Very short distances can make atoms overlap and prevent a calculation from converging.</p>"
                    "<p>Begin with a manageable number of points, then sample a smaller spacing around an important feature. "
                    "A narrow minimum can fall between points. Check whether its location and depth change when you refine the spacing.</p>"),
              _help("What does this scan measure?",
                    "<p>This tool samples one distance while keeping the two monomers rigid. The second monomer moves along the original "
                    "separation direction. Each point is an electronic-energy calculation at that geometry. Other coordinates are not optimized.</p>"
                    "<p>The curve is one path through the potential-energy surface. It does not establish a fully optimized minimum, a "
                    "torsional barrier or a multidimensional surface. A curve relative to its lowest point is not a binding energy referenced "
                    "to separated monomers. Record the method, basis, orientation and energy reference when interpreting the curve.</p>")),
        _step("3. Calculate the curve", _wrap(gui.btn_research_torq),
              _hint("The energy table and distance–energy curve will appear in Results after the calculation is collected.")),
    ])
    bonds = widgets.VBox([
        _step("2. Choose the bonding analysis",
              _hint("Use the analysis specified for your experiment. NBO, NAO Wiberg and Löwdin Wiberg results describe different aspects or definitions of bonding."),
              gui.research_orbital_backend,
              _help("What do NBO, NAO and Wiberg mean?",
                    "<p><b>Natural Bond Orbital (NBO) analysis</b> describes bonding with localized orbitals. "
                    "<b>Natural atomic orbitals (NAOs)</b> provide one basis for computing a Wiberg bond index. "
                    "The Löwdin alternative uses a different, orthogonalized atomic-orbital basis.</p>"
                    "<p>A Wiberg index is a measure of electron sharing under its stated definition. It is not a direct measurement "
                    "of a bond or an integer bond count. Report the basis used for the index and compare the same definition across structures. "
                    "Neither Wiberg definition is a Mayer bond order.</p>"),
              _hint("For this bonding form, choose HF, PBE-D4 or B3LYP-D4. MP2 is supported by the distance-scan form only.")),
        _step("3. Run the selected analysis",
              _wrap(gui.btn_research_nbo, gui.btn_research_wiberg, gui.btn_research_wiberg_nao),
              gui.research_bond_capability),
    ])
    gui.research_torq_tools = widgets.Tab(children=[scan, bonds])
    gui.research_torq_tools.set_title(0, "Distance scan")
    gui.research_torq_tools.set_title(1, "Bond analysis")
    return widgets.VBox([
        widgets.HTML("<h3>Energy scans and bonding · TORQ</h3><p>Explore a separation between two monomers, or analyze bonding in your selected structure.</p>"),
        _step("1. Choose the electronic-structure settings",
              gui.research_scan_method, gui.research_scan_basis,
              _hint("These settings apply to the selected tool below. Charge and multiplicity come from your calculation settings."),
              widgets.HTML(help_html("method_basis"))),
        gui.research_torq_tools, gui.research_status,
        _help("Why is a calculation button unavailable?",
              "<p>Finish or cancel any calculation already running, and select a valid starting structure. "
              "Open <b>Start here</b> to check module installation, your calculation environment and engine access. "
              "An NBO or NAO analysis also needs its supported orbital-analysis program. Installing ORCA or CFOUR alone "
              "does not make every bonding analysis available. See the availability message beside the analysis buttons for the reported reason.</p>"),
    ]).add_class("cochem-section")


def build_results_panel(gui: Any, advanced: widgets.Widget) -> widgets.VBox:
    """Offer reversible comparison selection without deleting research results."""
    gui.research_populations.description = "Include a population model"
    gui.research_energy_kind.description = "Energy to compare:"
    gui.btn_research_clear_selection = widgets.Button(description="Clear comparison selection")
    gui.research_comparison_status = widgets.HTML()
    gui.research_comparison_hint = widgets.HTML().add_class("cochem-hint")
    gui.research_population_hint = widgets.HTML().add_class("cochem-hint")
    gui.research_result_temperature = widgets.VBox([gui.research_temperature])

    def show_comparison_guidance(change: Any = None) -> None:
        count = len(gui.research_isomer_choices.value)
        if not gui.research_isomer_choices.options:
            selection = "No comparable energies have been collected yet. Run a calculation, then collect its results here."
        elif not count:
            selection = "Choose the calculated structures to compare. Clearing this selection keeps your saved results."
        else:
            selection = f"{count} selected. Compare the same composition, charge and spin state using the same method and basis."
        gui.research_comparison_hint.value = "<p>" + selection + "</p>"
        gibbs = gui.research_energy_kind.value == "gibbs_free_energy"
        populations = gui.research_populations.value
        gui.research_result_temperature.layout.display = "" if gibbs or populations else "none"
        if gibbs:
            explanation = ("Gibbs free energies include thermal and entropy contributions. Use results evaluated at the same "
                           "temperature and standard state; changing the temperature here does not recalculate them.")
        else:
            explanation = "Electronic energies exclude thermal and entropy contributions. Lower energy alone does not establish a stable minimum."
        if populations and gibbs:
            explanation += (" Population fractions require verified minima and distinct states. They describe only the selected set; "
                            "the calculation does not establish that all states were found or that they equilibrate.")
        elif populations:
            explanation += (" Electronic-energy weights require verified minima. They omit thermal free-energy effects "
                            "and must not be reported as equilibrium populations.")
        gui.research_population_hint.value = "<p>" + explanation + "</p>"

    gui.research_isomer_choices.observe(show_comparison_guidance, names=["options", "value"])
    gui.research_energy_kind.observe(show_comparison_guidance, names="value")
    gui.research_populations.observe(show_comparison_guidance, names="value")
    show_comparison_guidance()

    def clear_selection(button: Any) -> None:
        gui.research_isomer_choices.value = ()
        gui.research_comparison_status.value = "<p role='status'>Selection cleared. Your calculated results and saved files are unchanged. Select the structures you want to compare.</p>"

    gui.btn_research_clear_selection.on_click(clear_selection)
    _readable_controls(gui.btn_research_compare, gui.btn_research_clear_selection,
                       gui.research_isomer_choices, gui.research_energy_kind,
                       gui.research_populations)
    return widgets.VBox([
        widgets.HTML("<h3>Results</h3><p>Review your calculated values and their limitations, compare compatible structures, and download the tables and diagrams.</p>"),
        gui.research_report_output,
        _step("Compare calculated structures", gui.research_comparison_hint,
              gui.research_isomer_choices, _wrap(gui.btn_research_clear_selection),
              _help("How do I select more than one result?",
                    "<p>Hold Ctrl (Windows/Linux) or Command (macOS) while clicking to add or remove individual selections. "
                    "Use Shift to select a range. With the list focused, Shift + Arrow extends a contiguous keyboard selection. "
                    "Clear comparison selection starts again and preserves every calculated result.</p>"),
              gui.research_energy_kind,
              _hint("Only selected results with this energy type are included in the comparison."),
              gui.research_populations,
              gui.research_result_temperature, gui.research_population_hint,
              widgets.HTML(help_html("compare_results")),
              _wrap(gui.btn_research_compare), gui.research_comparison_status),
        _hint("Download the data alongside each figure. Keep its method, units, temperature where relevant, and calculation warnings in your research record."),
        gui.research_report_download,
        advanced,
    ]).add_class("cochem-section")
