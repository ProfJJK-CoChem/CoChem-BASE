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
        display="flex", flex_flow="row wrap", gap="8px", width="100%"))


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
            + "Disabled analyses need an additional supported program or module. Open Start here to check installation; ORCA alone does not establish that NBO is available.</p>"
            + ("<details><summary>Why these analyses are unavailable</summary><ul>" + details + "</ul></details>" if details else ""))


def build_topos_panel(gui: Any) -> widgets.VBox:
    """Keep the relevant chemistry choices visible for the selected operation."""
    gui.research_topos_operation.description = "Calculation:"
    gui.research_topos_engine.description = "TOPOS method:"
    gui.research_matrix_recipe.description = "Predefined method:"
    gui.btn_research_refresh.description = "Check available calculations"
    gui.btn_research_fragment_states.description = "Check monomer charges and spins"
    gui.btn_research_topos.description = "Start TOPOS calculation"
    gui.research_operation_help = widgets.HTML()
    gui.research_matrix_section = widgets.VBox([
        gui.research_matrix_recipe,
        _details("About predefined methods", gui.research_matrix_guidance),
    ])
    gui.research_monomer_section = widgets.VBox([
        gui.btn_research_fragment_states, gui.research_fragment_states,
    ])

    def show_operation(change: Any = None) -> None:
        operation = gui.research_topos_operation.value
        gui.research_operation_help.value = "<p>" + html.escape(_OPERATION_HELP.get(
            operation, "Finish setup to see available calculations. Then select a starting geometry and choose a calculation here.")) + "</p>"
        gui.research_topos_engine.layout.display = "none" if operation == "matrix" else ""
        gui.research_matrix_section.layout.display = "" if operation == "matrix" else "none"
        gui.research_candidates.layout.display = "" if operation in {"search", "association"} else "none"
        gui.research_monomer_section.layout.display = "" if operation == "association" else "none"
        # The same temperature control is also used by Results; keep it
        # available there instead of hiding the shared widget itself.
        gui.research_topos_temperature.layout.display = "" if operation == "thermochemistry" else "none"

    gui.research_topos_temperature = widgets.VBox([gui.research_temperature])
    gui.research_topos_operation.observe(show_operation, names="value")
    show_operation()
    _readable_controls(gui.research_topos_operation, gui.research_topos_engine,
                       gui.research_matrix_recipe, gui.btn_research_topos,
                       gui.btn_research_fragment_states, gui.btn_research_refresh)
    return widgets.VBox([
        widgets.HTML("<h3>TOPOS: structures and energies</h3><p>Choose your starting geometry in Your files or Molecule Builder, then select a calculation below.</p>"),
        gui.research_topos_operation, gui.research_operation_help,
        gui.research_topos_engine, gui.research_matrix_section,
        gui.research_candidates, gui.research_topos_temperature,
        gui.research_monomer_section, gui.btn_research_topos, gui.research_status,
        _details("Available calculations and setup help", gui.research_capabilities, gui.btn_research_refresh),
        _details("What these calculations can tell you", widgets.HTML(
            "<p>A conformer search finds candidates. Geometry optimization and frequency calculations check them further. Calculation time and accuracy depend on the molecule and method. Review the actual calculation warnings and results before interpreting an energy difference.</p>")),
    ])


def build_torq_panel(gui: Any) -> widgets.VBox:
    """Separate distance scans from bond analysis and show status in both tools."""
    gui.research_scan_method.description = "TORQ method:"
    gui.research_scan_basis.description = "TORQ basis set:"
    gui.research_orbital_backend.description = "NBO / NAO program:"
    gui.btn_research_torq.description = "Start distance scan"
    gui.btn_research_nbo.description = "Calculate NBO analysis"
    gui.btn_research_wiberg.description = "Calculate Löwdin Wiberg indices"
    gui.btn_research_wiberg_nao.description = "Calculate NAO Wiberg indices"
    _readable_controls(gui.research_scan_method, gui.research_scan_basis,
                       gui.research_scan_start, gui.research_scan_end,
                       gui.research_orbital_backend, gui.btn_research_torq,
                       gui.btn_research_nbo, gui.btn_research_wiberg,
                       gui.btn_research_wiberg_nao)
    scan = widgets.VBox([
        widgets.HTML("<p>Calculate how the energy changes as two monomers move apart. Select a complex containing two monomers; their internal coordinates stay fixed.</p>"),
        _wrap(gui.research_scan_start, gui.research_scan_end), gui.research_scan_points,
        gui.btn_research_torq,
        _details("How the distance scan works", widgets.HTML(
            "<p>Distances are between the monomers' centers of mass, in ångströms (Å). The second monomer moves along the original separation direction. TORQ calculates the energy at each requested distance without optimizing that geometry. View the energy table and curve in Results. This is a one-dimensional rigid scan, not a torsional or multidimensional scan.</p>")),
    ])
    bonds = widgets.VBox([
        widgets.HTML("<p>Analyze bonding in the selected geometry. Choose the analysis requested for your experiment; the available analyses use different definitions.</p>"),
        gui.research_orbital_backend,
        _wrap(gui.btn_research_nbo, gui.btn_research_wiberg, gui.btn_research_wiberg_nao),
        gui.research_bond_capability,
        _details("NBO, Löwdin and NAO explained", widgets.HTML(
            "<p><b>NBO</b> means Natural Bond Orbital analysis. It describes bonding using localized orbitals. <b>NAO</b> means natural atomic orbitals. Wiberg bond indices evaluated in the NAO basis differ from Wiberg indices evaluated in the Löwdin-orthogonalized atomic-orbital basis. A Löwdin result is not an NBO/NAO result, and none of these is a Mayer bond order.</p><p>MP2 is available for distance scans, but is not supported by this bond-analysis form. Select HF, PBE-D4 or B3LYP-D4 for bond analysis. Unavailable analyses stay disabled.</p>")),
    ])
    gui.research_torq_tools = widgets.Tab(children=[scan, bonds])
    gui.research_torq_tools.set_title(0, "Distance scan")
    gui.research_torq_tools.set_title(1, "Bond analysis")
    return widgets.VBox([
        widgets.HTML("<h3>TORQ: energy scans and bonding</h3><p>The method and basis below apply to the selected tool. Charge and multiplicity come from your calculation settings.</p>"),
        gui.research_scan_method, gui.research_scan_basis,
        gui.research_torq_tools, gui.research_status,
        _details("A calculation button is disabled", widgets.HTML(
            "<p>First finish or cancel any calculation already running. Open <b>Start here</b> to check module installation, the selected calculation environment and engine access. Only supported operations become selectable. ORCA and CFOUR are optional; installing them does not add every possible analysis to TORQ.</p>")),
    ])


def build_results_panel(gui: Any, advanced: widgets.Widget) -> widgets.VBox:
    """Offer reversible comparison selection without deleting research results."""
    gui.research_populations.description = "Estimate relative populations"
    gui.btn_research_clear_selection = widgets.Button(description="Clear comparison selection")
    gui.research_comparison_status = widgets.HTML()

    def clear_selection(button: Any) -> None:
        gui.research_isomer_choices.value = ()
        gui.research_comparison_status.value = "<p role='status'>Selection cleared. Your calculated results and saved files are unchanged. Select the structures you want to compare.</p>"

    gui.btn_research_clear_selection.on_click(clear_selection)
    _readable_controls(gui.btn_research_compare, gui.btn_research_clear_selection,
                       gui.research_isomer_choices)
    return widgets.VBox([
        widgets.HTML("<h3>Results</h3><p>Completed calculations appear here. Select compatible structures below to compare energies.</p>"),
        gui.research_report_output,
        gui.research_isomer_choices,
        _wrap(gui.btn_research_clear_selection, gui.research_energy_kind),
        gui.research_populations, gui.research_temperature,
        gui.btn_research_compare, gui.research_comparison_status,
        gui.research_report_download,
        _details("How to compare energies and populations", widgets.HTML(
            "<p>Compare the same chemical composition and electronic state using compatible calculation methods. Gibbs free-energy populations also require the same temperature and standard state and verified minima. Electronic-energy weights omit thermal free-energy effects; they are not equilibrium populations. The calculation checks these conditions before producing a comparison.</p><p>Use Ctrl-click (Windows/Linux) or Command-click (macOS) to change a multiple selection. Clear comparison selection starts the selection again and keeps every saved calculation.</p>")),
        advanced,
    ], layout=widgets.Layout(padding="16px"))
