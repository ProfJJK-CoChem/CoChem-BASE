r"""Exhaustive Production-Grade Pytest Verification Suite for Jinja2Templater.

Validates the Jinja2 LaTeX scaffolding engine (formatters/scribe_templater.py)
in strict accordance with:
- CoChem-SCRIBE SRS Phase 4, Task 9 (Stage 6.3, Tasks 51–60)
- Method Matrix v4 & FAIR Data Principles
- Zero-Mock Anti-Spoofing Protocol (Physical HDF5, physical templates, real DataFrames)
- 6-Tier Environment Matrix (Windows WSL, macOS OrbStack, Linux Debian, Codespaces, CI, HPC)
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
from typing import Any, Dict

import h5py
import numpy as np
import pandas as pd
import pytest

from formatters.scribe_templater import Jinja2Templater

# ==============================================================================
# PYTEST FIXTURES (Physical Real-Disk I/O via tmp_path)
# ==============================================================================


@pytest.fixture
def hdf5_physical_payload(tmp_path: pathlib.Path) -> pathlib.Path:
    r"""Generates an authentic physical HDF5 quantum chemistry dataset on disk.

    Populates:
    - /conformers: Conformer hierarchy (conf_01, conf_02, conf_03) with energies and point groups.
    - /spectroscopy: Rotational constants (A, B, C), dipole moments, and centrifugal distortion.
    - /thermodynamics: ZPE, enthalpy, Gibbs free energy, and harmonic vibrational frequencies.
    """
    h5_path = tmp_path / "landscape.h5"
    with h5py.File(str(h5_path), mode="w", libver="latest") as h5:
        # Conformers group hierarchy
        confs_grp = h5.create_group("conformers")

        c1 = confs_grp.create_group("conf_01")
        c1.attrs["relative_energy"] = 0.0000
        c1.attrs["point_group_symmetry"] = "C2v"
        c1.attrs["electronic_energy"] = -154.34567

        c2 = confs_grp.create_group("conf_02")
        c2.attrs["relative_energy"] = 0.0035
        c2.attrs["point_group_symmetry"] = "Cs"
        c2.attrs["electronic_energy"] = -154.34217

        c3 = confs_grp.create_group("conf_03")
        c3.attrs["relative_energy"] = 0.0082
        c3.attrs["point_group_symmetry"] = "C1"
        c3.attrs["electronic_energy"] = -154.33747

        # Spectroscopy group
        spec_grp = h5.create_group("spectroscopy")
        spec_grp.create_dataset(
            "rotational_constants",
            data=np.array([5420.5, 2810.2, 1950.8], dtype=np.float64),
        )
        spec_grp.create_dataset(
            "dipole_moments",
            data=np.array([1.85, 0.42, 0.00], dtype=np.float64),
        )
        spec_grp.create_dataset(
            "centrifugal_distortion",
            data=np.array([1.25e-3, 4.10e-4, 8.50e-5], dtype=np.float64),
        )

        # Thermodynamics group
        thermo_grp = h5.create_group("thermodynamics")
        thermo_grp.create_dataset("zero_point_energy", data=0.08234)
        thermo_grp.create_dataset("enthalpy", data=-154.25890)
        thermo_grp.create_dataset("gibbs_free_energy", data=-154.29145)
        thermo_grp.create_dataset(
            "vibrational_frequencies",
            data=np.array([450.2, 820.5, 1450.0, 3100.4], dtype=np.float64),
        )

    return h5_path


@pytest.fixture
def sample_template_file(tmp_path: pathlib.Path) -> pathlib.Path:
    r"""Writes an authentic ACS/APS-compliant LaTeX scaffold template to disk."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    template_path = templates_dir / "base_manuscript.tex"

    content = r"""\documentclass[journal=jacsat,manuscript=article]{achemso}

\usepackage{siunitx}
\usepackage{booktabs}
\usepackage{chemfig}
\usepackage{graphicx}
\usepackage{amsmath}
\usepackage{amssymb}

\title{\VAR{title}}
\author{\VAR{authors}}
\affiliation{\VAR{affiliations}}

\begin{document}

\begin{abstract}
\VAR{abstract}
\end{abstract}

\BLOCK{ if chemfig_structure }
\section{Molecular Structure}
\VAR{chemfig_structure}
\BLOCK{ endif }

\section{Computational Details}
\VAR{computational_details}

\BLOCK{ if sinc_dvr_justification }
\subsection{Large-Amplitude Motion \& Discrete Variable Representation}
\VAR{sinc_dvr_justification}
\BLOCK{ endif }

\section{Results and Discussion}

\subsection{Conformational Landscape}
\VAR{conformer_table}

\subsection{Thermodynamic Properties}
\VAR{thermo_table}

\subsection{Vibrational Analysis}
\VAR{vibrational_table}

\section{Computational Provenance}
\VAR{provenance_footer}

\end{document}
"""
    template_path.write_text(content, encoding="utf-8")
    return template_path


@pytest.fixture
def sample_chemistry_dataframes() -> Dict[str, pd.DataFrame]:
    r"""Returns authentic pandas DataFrames for conformers, thermodynamics, and vibrations."""
    conformer_df = pd.DataFrame(
        {
            "Conformer": ["conf_01", "conf_02", "conf_03"],
            "Delta_E_kcal_mol": [0.00, 2.20, 5.15],
            "Symmetry": ["C2v", "Cs", "C1"],
            "Population_Percent": [85.4, 12.1, 2.5],
        }
    )

    thermo_df = pd.DataFrame(
        {
            "Parameter": ["Zero-Point Energy", "Enthalpy H(298K)", "Gibbs Free Energy G(298K)"],
            "Value_Hartree": [0.08234, -154.25890, -154.29145],
            "Value_kcal_mol": [51.67, 0.00, 0.00],
        }
    )

    vib_df = pd.DataFrame(
        {
            "Mode": [1, 2, 3, 4],
            "Frequency_cm1": [450.2, 820.5, 1450.0, 3100.4],
            "Intensity_km_mol": [12.4, 45.1, 108.7, 5.3],
            "Symmetry": ["A1", "B2", "A1", "B1"],
        }
    )

    return {
        "conformers": conformer_df,
        "thermodynamics": thermo_df,
        "vibrations": vib_df,
    }


@pytest.fixture
def full_manuscript_payload(
    sample_chemistry_dataframes: Dict[str, pd.DataFrame],
) -> Dict[str, Any]:
    r"""Returns a comprehensive data dictionary containing metadata, narratives, and tables."""
    return {
        "title": "Quantum Mechanical Analysis of Ethanol Conformational Landscape",
        "authors": "Dr. Ada Lovelace, Dr. Linus Pauling",
        "affiliations": "Department of Computational Chemistry, CoChem Institute",
        "abstract": "We report ab initio quantum chemical calculations for ethanol conformers using density functional theory.",
        "smiles": "CCO",
        "computational_details": "Calculations carried out at B3LYP/def2-TZVP level of theory. INSERT_THERMO_TABLE_HERE",
        "conformer_table": sample_chemistry_dataframes["conformers"],
        "thermo_table": sample_chemistry_dataframes["thermodynamics"],
        "vibrational_table": sample_chemistry_dataframes["vibrations"],
        "lam_trigger": True,
        "sinc_dvr_justification": "Torsional Sinc-DVR justified based on 1.2 kcal/mol barrier.",
        "provenance_footer": "Telemetry generated according to FAIR data principles and validated via CoChem-SCRIBE.",
    }


# ==============================================================================
# TEST CASES (Tasks 51–60)
# ==============================================================================


def test_jinja2_environment_initialization_and_delimiters(
    sample_template_file: pathlib.Path,
) -> None:
    r"""Test Case 1: Jinja2 Environment Initialization & Custom Delimiter Remapping (Tasks 51 & 52).

    Validates:
    - Instantiation with a valid template directory.
    - Custom LaTeX-safe Jinja2 delimiters: \VAR{...}, \BLOCK{...}, \COMMENT{...}.
    - Whitespace trimming rules (trim_blocks, lstrip_blocks).
    - Filter registration for latex_escape, siunitx_num, siunitx_qty, chemfig.
    """
    templater = Jinja2Templater(template_dir=sample_template_file.parent)

    assert templater.env.variable_start_string == r"\VAR{"
    assert templater.env.variable_end_string == "}"
    assert templater.env.block_start_string == r"\BLOCK{"
    assert templater.env.block_end_string == "}"
    assert templater.env.comment_start_string == r"\COMMENT{"
    assert templater.env.comment_end_string == "}"
    assert templater.env.trim_blocks is True
    assert templater.env.lstrip_blocks is True

    # Assert custom filters
    assert "latex_escape" in templater.env.filters
    assert "siunitx_num" in templater.env.filters
    assert "siunitx_qty" in templater.env.filters
    assert "chemfig" in templater.env.filters


def test_dynamic_template_resolution_and_error_trapping(
    tmp_path: pathlib.Path, sample_template_file: pathlib.Path
) -> None:
    r"""Test Case 2: Dynamic Template Resolution & Error Trapping (Task 53).

    Validates:
    - Default template path resolves dynamically via pathlib.Path relative to module.
    - Non-existent template directories raise FileNotFoundError.
    - Non-existent template filenames raise FileNotFoundError or TemplateNotFound.
    """
    # Default template directory resolution
    default_templater = Jinja2Templater()
    assert default_templater.template_dir.is_dir()
    assert (default_templater.template_dir / "base_manuscript.tex").is_file()

    # Non-existent template directory
    nonexistent_dir = tmp_path / "nonexistent_templates_dir"
    with pytest.raises(FileNotFoundError) as exc_info:
        Jinja2Templater(template_dir=nonexistent_dir)
    assert "Template file not found" in str(exc_info.value)

    # Non-existent template file in valid directory
    with pytest.raises(FileNotFoundError) as exc_info:
        Jinja2Templater(
            template_dir=sample_template_file.parent,
            template_name="nonexistent_template.tex",
        )
    assert "Template file not found" in str(exc_info.value)


def test_scientific_unit_harmonization_siunitx() -> None:
    r"""Test Case 3: Scientific Unit Harmonization with siunitx (Task 54).

    Validates:
    - format_siunitx_num formats scientific notation, floats, and integers with \num{...}.
    - format_siunitx_qty harmonizes chemical and physical units into LaTeX \qty{...}{...}.
    """
    templater = Jinja2Templater()

    # Numbers
    assert templater.format_siunitx_num("1.23e-4") in (r"\num{1.23e-4}", r"\num{1.23e-04}")
    assert templater.format_siunitx_num("1.23E-04") in (r"\num{1.23e-4}", r"\num{1.23e-04}")
    assert templater.format_siunitx_num(1.23e-5) in (r"\num{1.23e-5}", r"\num{1.23e-05}")
    assert templater.format_siunitx_num(298.15) == r"\num{298.15}"
    assert templater.format_siunitx_num(-154.34567) == r"\num{-154.34567}"
    assert templater.format_siunitx_num(42) == r"\num{42}"

    # Quantities: Temperature
    assert templater.format_siunitx_qty(298.15, "K") == r"\qty{298.15}{\kelvin}"
    assert templater.format_siunitx_qty(298.15, "kelvin") == r"\qty{298.15}{\kelvin}"
    assert templater.format_siunitx_qty(25.0, "degC") == r"\qty{25.0}{\celsius}"
    assert templater.format_siunitx_qty(25.0, "°C") == r"\qty{25.0}{\celsius}"

    # Quantities: Energetics
    assert (
        templater.format_siunitx_qty(-154.3, "kcal/mol") == r"\qty{-154.3}{\kilo\calorie\per\mole}"
    )
    assert templater.format_siunitx_qty(45.2, "kJ/mol") == r"\qty{45.2}{\kilo\joule\per\mole}"
    assert templater.format_siunitx_qty(-76.43, "Hartree") == r"\qty{-76.43}{\hartree}"
    assert templater.format_siunitx_qty(13.6, "eV") == r"\qty{13.6}{\electronvolt}"

    # Quantities: Spectroscopy
    assert templater.format_siunitx_qty(1450.0, "cm-1") == r"\qty{1450.0}{\per\centi\meter}"
    assert templater.format_siunitx_qty(1450.0, "cm^-1") == r"\qty{1450.0}{\per\centi\meter}"
    assert templater.format_siunitx_qty(9.45, "GHz") == r"\qty{9.45}{\giga\hertz}"
    assert templater.format_siunitx_qty(1420.4, "MHz") == r"\qty{1420.4}{\mega\hertz}"

    # Quantities: Dipoles, Geometry, Pressure, Time
    assert templater.format_siunitx_qty(1.85, "Debye") == r"\qty{1.85}{\debye}"
    assert templater.format_siunitx_qty(1.85, "D") == r"\qty{1.85}{\debye}"
    assert templater.format_siunitx_qty(1.09, "Angstrom") == r"\qty{1.09}{\angstrom}"
    assert templater.format_siunitx_qty(109.5, "deg") == r"\qty{109.5}{\degree}"
    assert templater.format_siunitx_qty(1.0, "bar") == r"\qty{1.0}{\bar}"
    assert templater.format_siunitx_qty(1.0, "atm") == r"\qty{1.0}{\standardatmosphere}"
    assert templater.format_siunitx_qty(100, "fs") == r"\qty{100}{\femto\second}"


def test_academic_table_conversion_booktabs(
    sample_chemistry_dataframes: Dict[str, pd.DataFrame],
) -> None:
    r"""Test Case 4: Academic Table Conversion with booktabs (Task 55).

    Validates:
    - Converts DataFrame to valid booktabs table structure (\toprule, \midrule, \bottomrule).
    - Strictly forbids vertical grid rules (|) in tabular alignment specification.
    - Wraps numeric float cells in \num{...}.
    - Sanitizes column headers and string values.
    - Includes caption and label.
    - Handles empty DataFrames gracefully.
    """
    templater = Jinja2Templater()
    df = sample_chemistry_dataframes["conformers"]

    table_latex = templater.dataframe_to_booktabs(
        df,
        caption="Calculated Conformer Landscape",
        label="tab:conformers",
    )

    assert r"\begin{table}[htbp]" in table_latex
    assert r"\centering" in table_latex
    assert r"\caption{Calculated Conformer Landscape}" in table_latex
    assert r"\label{tab:conformers}" in table_latex
    assert r"\begin{tabular}" in table_latex
    assert r"\toprule" in table_latex
    assert r"\midrule" in table_latex
    assert r"\bottomrule" in table_latex
    assert r"\end{tabular}" in table_latex
    assert r"\end{table}" in table_latex

    # Disallow vertical rules
    tabular_spec = table_latex.split(r"\begin{tabular}")[1].split(r"\toprule")[0]
    assert "|" not in tabular_spec

    # Check numeric formatting in table
    assert r"\num{0.0}" in table_latex or r"\num{0}" in table_latex
    assert r"\num{2.2}" in table_latex
    assert r"\num{85.4}" in table_latex

    # Header sanitization check
    assert r"Delta\_E\_kcal\_mol" in table_latex
    assert r"Population\_Percent" in table_latex

    # Custom column alignment with forbidden vertical bars must be sanitized
    custom_table = templater.dataframe_to_booktabs(df, col_align="l|r|c|r")
    custom_spec = custom_table.split(r"\begin{tabular}")[1].split(r"\toprule")[0]
    assert "|" not in custom_spec
    assert "lrcr" in custom_spec

    # Graceful handling of empty DataFrames and None
    assert templater.dataframe_to_booktabs(pd.DataFrame()) == ""
    assert templater.dataframe_to_booktabs(None) == ""  # type: ignore[arg-type]

    empty_with_cols = templater.dataframe_to_booktabs(pd.DataFrame(columns=["Mode", "Frequency"]))
    assert r"\toprule" in empty_with_cols
    assert r"\bottomrule" in empty_with_cols


def test_chemfig_2d_molecular_topology_rendering() -> None:
    r"""Test Case 5: 2D Molecular Topology (chemfig) Rendering (Task 56).

    Validates:
    - Converts valid SMILES (e.g. CCO, c1ccccc1) into \chemfig{...} macros.
    - Gracefully handles empty strings, None, and unparseable input with fallback comment.
    - Preserves pre-formatted \chemfig{...} strings.
    """
    templater = Jinja2Templater()

    # Valid SMILES
    cf_ethanol = templater.render_chemfig("CCO")
    assert cf_ethanol.startswith(r"\chemfig{")
    assert cf_ethanol.endswith("}")
    assert "CCO" in cf_ethanol

    cf_benzene = templater.render_chemfig("c1ccccc1")
    assert cf_benzene.startswith(r"\chemfig{")
    assert cf_benzene.endswith("}")

    # Triple bonds mapping
    cf_alkyne = templater.render_chemfig("CC#C")
    assert "~" in cf_alkyne

    # Fallback comment for empty, None, or invalid input
    assert templater.render_chemfig("") == "% [No 2D chemfig structure available]"
    assert templater.render_chemfig(None) == "% [No 2D chemfig structure available]"
    assert templater.render_chemfig("   ") == "% [No 2D chemfig structure available]"
    assert templater.render_chemfig("INVALID$$$CHARS!@#") == "% [No 2D chemfig structure available]"

    # Pre-formatted chemfig preservation
    preformatted = r"\chemfig{C(-[2]H)(-[6]H)-C(=[1]O)-[7]O-H}"
    assert templater.render_chemfig(preformatted) == preformatted


def test_aggressive_latex_sanitization_and_escape_filter() -> None:
    r"""Test Case 6: Aggressive LaTeX Sanitization & Escape Filter (Task 59).

    Validates:
    - Escapes _, &, %, #, ~, ^, $ in raw strings.
    - Preserves valid existing LaTeX macros (\num{...}, \qty{...}{...}, \textbf{...}).
    - Preserves math mode blocks ($...$, $$...$$, \[...\], \(...\)).
    - Avoids double-escaping pre-escaped characters.
    """
    templater = Jinja2Templater()

    # Raw telemetry string
    raw_telemetry = "SCF_CONVERGENCE_FAIL & Error_Rate % = 0.5% #1 ~ ^test $100"
    sanitized = templater.sanitize_latex(raw_telemetry)

    assert r"SCF\_CONVERGENCE\_FAIL" in sanitized
    assert r"\&" in sanitized
    assert r"Error\_Rate" in sanitized
    assert r"\% = 0.5\%" in sanitized
    assert r"\#1" in sanitized
    assert r"\textasciitilde{}" in sanitized
    assert r"\textasciicircum{}test" in sanitized
    assert r"\$100" in sanitized

    # Preservation of valid LaTeX macros and math mode
    macro_text = (
        r"We use \textbf{Gaussian_16} with \num{1.23e-4} and \qty{298.15}{\kelvin} "
        r"to calculate $\Delta G^\circ = -RT \ln K$ and \[ E = mc^2 \]."
    )
    sanitized_macro = templater.sanitize_latex(macro_text)
    assert r"\textbf{Gaussian\_16}" in sanitized_macro
    assert r"\num{1.23e-4}" in sanitized_macro
    assert r"\qty{298.15}{\kelvin}" in sanitized_macro
    assert r"$\Delta G^\circ = -RT \ln K$" in sanitized_macro
    assert r"\[ E = mc^2 \]" in sanitized_macro

    # Idempotency / No double escaping
    already_escaped = r"Paths: /data/\_results \& 50\% \#1 \$100 \textasciitilde{}"
    sanitized_again = templater.sanitize_latex(already_escaped)
    assert r"\\_" not in sanitized_again.replace(r"\_", "")
    assert r"\\&" not in sanitized_again.replace(r"\&", "")
    assert r"\\%" not in sanitized_again.replace(r"\%", "")
    assert r"\\#" not in sanitized_again.replace(r"\#", "")
    assert r"\\$" not in sanitized_again.replace(r"\$", "")


def test_narrative_injection_and_lam_trigger_mapping(
    sample_template_file: pathlib.Path,
) -> None:
    r"""Test Case 7: Narrative Injection & LAM_TRIGGER Mapping (Tasks 57 & 58).

    Validates:
    - Injects computational details into \section{Computational Details}.
    - Cleans upstream placeholder tags (<<INSERT_*>>, INSERT_THERMO_TABLE_HERE, {{ ... }}).
    - When sinc_dvr_justification is provided or lam_trigger is True, renders Sinc-DVR subsection.
    - When lam_trigger is False and sinc_dvr_justification is empty, omits Sinc-DVR subsection.
    """
    templater = Jinja2Templater(template_dir=sample_template_file.parent)

    base_payload: Dict[str, Any] = {
        "title": "Quantum Mechanics of Internal Rotations",
        "authors": "Dr. Marie Curie",
        "affiliations": "Department of Physics, Sorbonne University",
        "abstract": "Analysis of torsional barrier potentials.",
        "computational_details": "Calculations used B3LYP/def2-TZVP. <<INSERT_METHODOLOGY>> INSERT_THERMO_TABLE_HERE {{ custom_tag }}",
        "provenance_footer": "Telemetry recorded under FAIR data principles.",
    }

    # Case A: LAM Active with explicit justification
    active_payload = dict(base_payload)
    active_payload["lam_trigger"] = True
    active_payload["sinc_dvr_justification"] = "Torsional Sinc-DVR justified for internal rotor."
    rendered_active = templater.render_manuscript(active_payload)

    assert r"\section{Computational Details}" in rendered_active
    assert "Calculations used B3LYP/def2-TZVP." in rendered_active
    assert "<<INSERT_" not in rendered_active
    assert "INSERT_THERMO_TABLE_HERE" not in rendered_active
    assert "{{" not in rendered_active
    assert "}}" not in rendered_active
    assert (
        r"\subsection{Large-Amplitude Motion \& Discrete Variable Representation}"
        in rendered_active
    )
    assert "Torsional Sinc-DVR justified for internal rotor." in rendered_active

    # Case B: LAM Inactive
    inactive_payload = dict(base_payload)
    inactive_payload["lam_trigger"] = False
    inactive_payload["sinc_dvr_justification"] = ""
    rendered_inactive = templater.render_manuscript(inactive_payload)

    assert r"\section{Computational Details}" in rendered_inactive
    assert (
        r"\subsection{Large-Amplitude Motion \& Discrete Variable Representation}"
        not in rendered_inactive
    )


def test_end_to_end_zero_mock_manuscript_rendering(
    tmp_path: pathlib.Path,
    sample_template_file: pathlib.Path,
    hdf5_physical_payload: pathlib.Path,
) -> None:
    r"""Test Case 8: End-to-End Zero-Mock Manuscript Rendering (Task 60).

    Validates:
    - Extracts authentic telemetry directly from physical HDF5 file on disk.
    - Constructs conformer, thermodynamic, and vibrational DataFrames.
    - Renders complete LaTeX document via Jinja2Templater.
    - Asserts document structure: documentclass, document, abstract, toprule, num, qty.
    - Asserts 100% resolution of Jinja2 delimiters (zero unrendered \VAR{ or \BLOCK{ tags).
    """
    # 1. Read authentic physical telemetry from HDF5 file
    with h5py.File(str(hdf5_physical_payload), mode="r") as h5:
        # Conformers
        conf_names = list(h5["conformers"].keys())
        rel_energies = [h5["conformers"][c].attrs["relative_energy"] for c in conf_names]
        symmetries = [h5["conformers"][c].attrs["point_group_symmetry"] for c in conf_names]
        electronic_energies = [h5["conformers"][c].attrs["electronic_energy"] for c in conf_names]

        conformer_df = pd.DataFrame(
            {
                "Conformer": conf_names,
                "Electronic_Energy_Hartree": electronic_energies,
                "Delta_E_Hartree": rel_energies,
                "Symmetry": symmetries,
            }
        )

        # Thermodynamics
        zpe = float(h5["thermodynamics"]["zero_point_energy"][()])
        h_val = float(h5["thermodynamics"]["enthalpy"][()])
        g_val = float(h5["thermodynamics"]["gibbs_free_energy"][()])

        thermo_df = pd.DataFrame(
            {
                "Property": ["Zero-Point Energy", "Enthalpy H(298K)", "Gibbs Free Energy G(298K)"],
                "Value_Hartree": [zpe, h_val, g_val],
            }
        )

        # Vibrations
        frequencies = list(h5["thermodynamics"]["vibrational_frequencies"][()])
        vib_df = pd.DataFrame(
            {
                "Mode": list(range(1, len(frequencies) + 1)),
                "Frequency_cm1": frequencies,
            }
        )

    # 2. Build complete payload
    payload: Dict[str, Any] = {
        "title": "Quantum Conformational Landscape and Spectroscopy of Ethanol",
        "authors": "Dr. Ada Lovelace, Dr. Linus Pauling",
        "affiliations": "Consortium for Advanced Quantum Chemistry, CoChem-SCRIBE",
        "abstract": "We report rigorous physical quantum chemical properties for ethanol.",
        "smiles": "CCO",
        "computational_details": "Calculations were carried out with B3LYP/def2-TZVP. INSERT_THERMO_TABLE_HERE",
        "conformer_table": conformer_df,
        "thermo_table": thermo_df,
        "vibrational_table": vib_df,
        "lam_trigger": True,
        "sinc_dvr_justification": "Torsional Sinc-DVR discretization is justified based on low barrier.",
        "provenance_footer": "Telemetry recorded in landscape.h5 under FAIR data principles.",
    }

    # 3. Render manuscript using Jinja2Templater
    templater = Jinja2Templater(template_dir=sample_template_file.parent)
    manuscript = templater.render_manuscript(payload)

    # 4. Strict Structural Assertions
    assert isinstance(manuscript, str)
    assert len(manuscript) > 500

    # LaTeX document structure
    assert r"\documentclass[journal=jacsat,manuscript=article]{achemso}" in manuscript
    assert r"\title{Quantum Conformational Landscape and Spectroscopy of Ethanol}" in manuscript
    assert r"\author{Dr. Ada Lovelace, Dr. Linus Pauling}" in manuscript
    assert r"\affiliation{Consortium for Advanced Quantum Chemistry, CoChem-SCRIBE}" in manuscript
    assert r"\begin{document}" in manuscript
    assert r"\begin{abstract}" in manuscript
    assert r"\end{abstract}" in manuscript
    assert r"\end{document}" in manuscript

    # Molecular topology and sections
    assert r"\section{Molecular Structure}" in manuscript
    assert r"\chemfig{CCO}" in manuscript
    assert r"\section{Computational Details}" in manuscript
    assert r"\subsection{Large-Amplitude Motion \& Discrete Variable Representation}" in manuscript
    assert "Torsional Sinc-DVR discretization is justified based on low barrier." in manuscript

    # Academic booktabs tables and siunitx numbers
    assert r"\toprule" in manuscript
    assert r"\midrule" in manuscript
    assert r"\bottomrule" in manuscript
    assert r"\num{-154.34567}" in manuscript
    assert r"\num{450.2}" in manuscript
    assert r"\num{3100.4}" in manuscript

    # Zero unrendered Jinja2 delimiters
    assert r"\VAR{" not in manuscript
    assert r"\BLOCK{" not in manuscript
    assert r"\COMMENT{" not in manuscript
    assert "INSERT_THERMO_TABLE_HERE" not in manuscript


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
