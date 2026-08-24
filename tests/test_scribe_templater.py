"""Exhaustive Verification Suite for Jinja2Templater & LaTeX Scaffolding Module.

Conforms to CoChem Anti-Spoofing Protocol:
- Real filesystem interactions with physical templates.
- Real pandas DataFrame objects and exact physical scalar verification.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
from typing import Any, Dict

import pandas as pd
import pytest

from formatters.scribe_templater import Jinja2Templater


@pytest.fixture
def templater() -> Jinja2Templater:
    """Fixture providing initialized Jinja2Templater instance."""
    return Jinja2Templater()


# ==============================================================================
# TEST 1: Full Manuscript Synthesis & Delimiter Rendering
# ==============================================================================
def test_full_manuscript_synthesis(templater: Jinja2Templater) -> None:
    """Tests complete manuscript assembly with real DataFrames and LaTeX delimiter rendering."""
    conformer_df = pd.DataFrame({
        "Conformer": ["Conf-Anti", "Conf-Gauche"],
        "Energy (Hartree)": [-154.34567, -154.34120],
        "Rel_Energy (kcal/mol)": [0.00, 2.81],
        "Dipole (D)": [1.45, 2.10],
    })

    thermo_df = pd.DataFrame({
        "Property": ["Zero-Point Energy", "Enthalpy H(298K)", "Gibbs Free Energy G(298K)"],
        "Value (Hartree)": [0.08234, -154.25890, -154.29145],
        "Rel_Value (kcal/mol)": [51.67, 0.00, 0.00],
    })

    vib_df = pd.DataFrame({
        "Mode": [1, 2, 3],
        "Frequency (cm-1)": [245.3, 389.1, 1054.8],
        "IR Intensity (km/mol)": [12.4, 45.1, 108.7],
    })

    payload: Dict[str, Any] = {
        "title": "Quantum Mechanical Simulation of Ethanol Torsional PES & Thermochemistry",
        "authors": "Dr. Alice Turing, Dr. Bob Wheeler",
        "affiliations": "CoChem Consortium for Advanced Quantum Computing",
        "abstract": "We present high-level ab initio calculations for ethanol conformers using B3LYP/def2-TZVP.",
        "smiles": "CCO",
        "computational_details": "Density functional theory (DFT) was applied. INSERT_THERMO_TABLE_HERE",
        "lam_trigger": True,
        "sinc_dvr_justification": "Torsional Sinc-DVR discretization is justified for the C-O dihedral mode.",
        "conformer_table": conformer_df,
        "thermo_table": thermo_df,
        "vibrational_table": vib_df,
        "provenance_footer": "FAIR-compliant calculation payload validated via CoChem-SCRIBE.",
    }

    manuscript = templater.render_manuscript(payload)

    # Document structure assertions
    assert r"\documentclass[journal=jacsat,manuscript=article]{achemso}" in manuscript
    assert r"\title{Quantum Mechanical Simulation of Ethanol Torsional PES \& Thermochemistry}" in manuscript
    assert r"\author{Dr. Alice Turing, Dr. Bob Wheeler}" in manuscript
    assert r"\affiliation{CoChem Consortium for Advanced Quantum Computing}" in manuscript
    assert r"\begin{abstract}" in manuscript
    assert r"\end{abstract}" in manuscript
    assert r"\begin{document}" in manuscript
    assert r"\end{document}" in manuscript

    # Molecular structure & LAM assertions
    assert r"\section{Molecular Structure}" in manuscript
    assert r"\chemfig{CCO}" in manuscript
    assert r"\subsection{Large-Amplitude Motion \& Discrete Variable Representation}" in manuscript
    assert "Torsional Sinc-DVR discretization is justified for the C-O dihedral mode." in manuscript

    # Table assertions
    assert r"\toprule" in manuscript
    assert r"\midrule" in manuscript
    assert r"\bottomrule" in manuscript
    assert r"\num{-154.34567}" in manuscript
    assert r"\num{245.3}" in manuscript

    # Upstream insertion tag cleanup assertions
    assert "INSERT_THERMO_TABLE_HERE" not in manuscript
    assert "{{" not in manuscript
    assert "}}" not in manuscript

    # Delimiter hygiene assertions: zero unrendered Jinja2 delimiters
    assert r"\VAR{" not in manuscript
    assert r"\BLOCK{" not in manuscript
    assert r"\COMMENT{" not in manuscript


# ==============================================================================
# TEST 2: siunitx Number & Quantity Formatting
# ==============================================================================
def test_siunitx_number_formatting(templater: Jinja2Templater) -> None:
    """Tests siunitx number formatting for scientific notation, floats, and integers."""
    assert templater.format_siunitx_num("1.23e-4") == r"\num{1.23e-4}"
    assert templater.format_siunitx_num("1.23E-04") == r"\num{1.23e-4}"
    assert templater.format_siunitx_num(1.23e-5) == r"\num{1.23e-5}"
    assert templater.format_siunitx_num(298.15) == r"\num{298.15}"
    assert templater.format_siunitx_num(-154.34567) == r"\num{-154.34567}"
    assert templater.format_siunitx_num(42) == r"\num{42}"
    assert templater.format_siunitx_num(r"\num{1.23e-4}") == r"\num{1.23e-4}"


def test_siunitx_quantity_formatting(templater: Jinja2Templater) -> None:
    """Tests siunitx quantity formatting across physical chemistry domains."""
    # Temperature
    assert templater.format_siunitx_qty(298.15, "K") == r"\qty{298.15}{\kelvin}"
    assert templater.format_siunitx_qty(300, "kelvin") == r"\qty{300}{\kelvin}"
    assert templater.format_siunitx_qty(25.0, "degC") == r"\qty{25.0}{\celsius}"

    # Energetics
    assert templater.format_siunitx_qty(-154.3, "kcal/mol") == r"\qty{-154.3}{\kilo\calorie\per\mole}"
    assert templater.format_siunitx_qty(45.2, "kJ/mol") == r"\qty{45.2}{\kilo\joule\per\mole}"
    assert templater.format_siunitx_qty(-76.43, "Hartree") == r"\qty{-76.43}{\hartree}"
    assert templater.format_siunitx_qty(13.6, "eV") == r"\qty{13.6}{\electronvolt}"

    # Frequencies & Rotational constants
    assert templater.format_siunitx_qty(1200.5, "cm-1") == r"\qty{1200.5}{\per\centi\meter}"
    assert templater.format_siunitx_qty(1200.5, "cm^-1") == r"\qty{1200.5}{\per\centi\meter}"
    assert templater.format_siunitx_qty(9.45, "GHz") == r"\qty{9.45}{\giga\hertz}"
    assert templater.format_siunitx_qty(1420.4, "MHz") == r"\qty{1420.4}{\mega\hertz}"

    # Dipoles & Geometry
    assert templater.format_siunitx_qty(1.85, "D") == r"\qty{1.85}{\debye}"
    assert templater.format_siunitx_qty(1.85, "Debye") == r"\qty{1.85}{\debye}"
    assert templater.format_siunitx_qty(1.09, "Angstrom") == r"\qty{1.09}{\angstrom}"
    assert templater.format_siunitx_qty(109.5, "deg") == r"\qty{109.5}{\degree}"

    # Pressure & Time
    assert templater.format_siunitx_qty(1.0, "bar") == r"\qty{1.0}{\bar}"
    assert templater.format_siunitx_qty(1.0, "atm") == r"\qty{1.0}{\standardatmosphere}"
    assert templater.format_siunitx_qty(100, "fs") == r"\qty{100}{\femto\second}"


# ==============================================================================
# TEST 3: Aggressive LaTeX Sanitization & Macro/Math Preservation
# ==============================================================================
def test_latex_sanitization_raw_characters(templater: Jinja2Templater) -> None:
    """Tests that unsafe raw LaTeX characters are escaped properly."""
    raw = "SCF_CONVERGENCE_FAIL & Error_Rate % = 0.5% #1 ~ ^test"
    sanitized = templater.sanitize_latex(raw)

    assert r"SCF\_CONVERGENCE\_FAIL" in sanitized
    assert r"\&" in sanitized
    assert r"Error\_Rate" in sanitized
    assert r"\%" in sanitized
    assert r"\#1" in sanitized
    assert r"\textasciitilde{}" in sanitized
    assert r"\textasciicircum{}test" in sanitized


def test_latex_sanitization_macro_and_math_preservation(templater: Jinja2Templater) -> None:
    """Tests that valid LaTeX macros and math mode blocks are preserved intact."""
    text_with_macros = (
        r"We use \textbf{Gaussian_16} with \num{1.23e-4} and \qty{298.15}{\kelvin} "
        r"to calculate $\Delta G^\circ = -RT \ln K$ and \[ E = mc^2 \]."
    )
    sanitized = templater.sanitize_latex(text_with_macros)

    # Macros preserved
    assert r"\textbf{Gaussian\_16}" in sanitized
    assert r"\num{1.23e-4}" in sanitized
    assert r"\qty{298.15}{\kelvin}" in sanitized

    # Math mode preserved
    assert r"$\Delta G^\circ = -RT \ln K$" in sanitized
    assert r"\[ E = mc^2 \]" in sanitized


def test_latex_sanitization_already_escaped(templater: Jinja2Templater) -> None:
    """Tests that pre-escaped characters are not double-escaped."""
    already_escaped = r"Paths: C:\data\_results \& 50\% \#1 \$100 \textasciitilde{}"
    sanitized = templater.sanitize_latex(already_escaped)

    assert r"\\_" not in sanitized.replace(r"\_", "")
    assert r"\\&" not in sanitized.replace(r"\&", "")
    assert r"\\%" not in sanitized.replace(r"\%", "")
    assert r"\\#" not in sanitized.replace(r"\#", "")


# ==============================================================================
# TEST 4: LAM_TRIGGER Active vs Inactive Conditional Mapping
# ==============================================================================
def test_lam_trigger_active_and_inactive(templater: Jinja2Templater) -> None:
    """Tests that LAM_TRIGGER activates and deactivates the Sinc-DVR subsection."""
    base_payload: Dict[str, Any] = {
        "title": "Torsional Study",
        "authors": "Researcher",
        "affiliations": "Lab",
        "abstract": "Abstract text.",
        "computational_details": "DFT methodology.",
        "provenance_footer": "Telemetry verified.",
    }

    # Case A: LAM Active
    active_payload = dict(base_payload)
    active_payload["lam_trigger"] = True
    active_payload["sinc_dvr_justification"] = "Sinc-DVR active for internal rotation."
    rendered_active = templater.render_manuscript(active_payload)
    assert r"\subsection{Large-Amplitude Motion \& Discrete Variable Representation}" in rendered_active
    assert "Sinc-DVR active for internal rotation." in rendered_active

    # Case B: LAM Inactive
    inactive_payload = dict(base_payload)
    inactive_payload["lam_trigger"] = False
    inactive_payload["sinc_dvr_justification"] = ""
    rendered_inactive = templater.render_manuscript(inactive_payload)
    assert r"\subsection{Large-Amplitude Motion \& Discrete Variable Representation}" not in rendered_inactive


# ==============================================================================
# TEST 5: Academic Booktabs Table Generation (Zero Vertical Rules)
# ==============================================================================
def test_dataframe_to_booktabs_academic_standard(templater: Jinja2Templater) -> None:
    """Tests conversion of DataFrame to academic booktabs table with zero vertical rules."""
    df = pd.DataFrame({
        "Conformer_Name": ["Conf_A", "Conf_B", "Conf_C"],
        "Electronic_Energy (Hartree)": [-154.34567, -154.34120, -154.33981],
        "Rel_Gibbs (kcal/mol)": [0.00, 2.81, 3.68],
        "Population_%": [82.5, 12.3, 5.2],
    })

    # Test with default alignment and custom caption/label
    latex_table = templater.dataframe_to_booktabs(
        df,
        caption="Calculated Conformer Thermochemistry",
        label="tab:conf_thermo",
    )

    assert r"\begin{table}[htbp]" in latex_table
    assert r"\centering" in latex_table
    assert r"\caption{Calculated Conformer Thermochemistry}" in latex_table
    assert r"\label{tab:conf_thermo}" in latex_table
    assert r"\toprule" in latex_table
    assert r"\midrule" in latex_table
    assert r"\bottomrule" in latex_table
    assert r"\end{tabular}" in latex_table
    assert r"\end{table}" in latex_table

    # Numerical cells formatted with \num{...}
    assert r"\num{-154.34567}" in latex_table
    assert r"\num{82.5}" in latex_table

    # Headers sanitized
    assert r"Conformer\_Name" in latex_table
    assert r"Population\_\%" in latex_table

    # Zero vertical rules assertion
    tabular_spec = latex_table.split(r"\begin{tabular}")[1].split(r"\toprule")[0]
    assert "|" not in tabular_spec

    # Test that custom col_align with vertical rules has rules stripped
    latex_table_custom = templater.dataframe_to_booktabs(df, col_align="l|r|r|r")
    custom_spec = latex_table_custom.split(r"\begin{tabular}")[1].split(r"\toprule")[0]
    assert "|" not in custom_spec
    assert "lrrr" in custom_spec


# ==============================================================================
# TEST 6: Missing Template FileNotFoundError Assertion
# ==============================================================================
def test_missing_template_raises_filenotfound() -> None:
    """Tests that a missing template file or directory raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        Jinja2Templater(template_name="nonexistent_template_9999.tex")

    with pytest.raises(FileNotFoundError):
        Jinja2Templater(template_dir=pathlib.Path("/nonexistent_directory_9999"))


# ==============================================================================
# TEST 7: Standalone CLI Pre-Flight Execution
# ==============================================================================
def test_cli_preflight_execution() -> None:
    """Executes scribe_templater.py as standalone CLI script and asserts exit code 0."""
    module_dir = pathlib.Path(__file__).resolve().parent
    if (module_dir / "scribe_templater.py").is_file():
        script_path = module_dir / "scribe_templater.py"
    else:
        script_path = module_dir.parent / "formatters" / "scribe_templater.py"

    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, f"CLI script failed with stderr: {result.stderr}"
    assert "[SCRIBE TEMPLATER PRE-FLIGHT VERIFIED]" in result.stdout
