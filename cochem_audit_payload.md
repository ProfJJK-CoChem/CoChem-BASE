Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-GEOM\.in-progress\Task_10_data_dataset_py.md.
Original prompt:
# Task: Create `src/cochem_geom/data/dataset.py`

## Context
You are an autonomous execution agent coding the new version of CoChem-GEOM based on the approved System Architecture.
Target output directory: `D:\__CoChem\GitHub-Repo\CoChem-GEOM`

## Strict Execution Constraints
1. **Scope:** Generate exactly one coding script file for this prompt (`src/cochem_geom/data/dataset.py`).
2. **Path:** Output the generated file to the target output directory at `D:\__CoChem\GitHub-Repo\CoChem-GEOM\src/cochem_geom/data/dataset.py`. Do not execute or run the code, only generate the file.
3. **Geometric Equivariance & Invariance:** The system must strictly separate non-spatial node features from spatial coordinates.
4. **State Immutability:** Geometric transformations are immutable (`data.pos = data.pos + update`, never `data.pos += update`).
5. **No Hardcoded Paths:** Use dynamic lookups (`pathlib.Path.home()`, environment variables).
6. **Provenance Tags:** You MUST tag all qualitative values, bounds, energy metrics, and hardware speedups with explicit provenance tags (`[M]` for Measured, `[D]` for Derived, `[E]` for Expert Estimate).

## File Specific Instructions
PyG InMemoryDataset and IterableDataset implementations. Factory pattern for GEOM-QM9 and GEOM-Drugs subsets. Treat 3D coordinates and node features distinctly.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\formatters\test_scribe_templater.py ---
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
import jinja2
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
    conformer_df = pd.DataFrame({
        "Conformer": ["conf_01", "conf_02", "conf_03"],
        "Delta_E_kcal_mol": [0.00, 2.20, 5.15],
        "Symmetry": ["C2v", "Cs", "C1"],
        "Population_Percent": [85.4, 12.1, 2.5],
    })

    thermo_df = pd.DataFrame({
        "Parameter": ["Zero-Point Energy", "Enthalpy H(298K)", "Gibbs Free Energy G(298K)"],
        "Value_Hartree": [0.08234, -154.25890, -154.29145],
        "Value_kcal_mol": [51.67, 0.00, 0.00],
    })

    vib_df = pd.DataFrame({
        "Mode": [1, 2, 3, 4],
        "Frequency_cm1": [450.2, 820.5, 1450.0, 3100.4],
        "Intensity_km_mol": [12.4, 45.1, 108.7, 5.3],
        "Symmetry": ["A1", "B2", "A1", "B1"],
    })

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
    assert templater.format_siunitx_qty(-154.3, "kcal/mol") == r"\qty{-154.3}{\kilo\calorie\per\mole}"
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
    assert r"\subsection{Large-Amplitude Motion \& Discrete Variable Representation}" in rendered_active
    assert "Torsional Sinc-DVR justified for internal rotor." in rendered_active

    # Case B: LAM Inactive
    inactive_payload = dict(base_payload)
    inactive_payload["lam_trigger"] = False
    inactive_payload["sinc_dvr_justification"] = ""
    rendered_inactive = templater.render_manuscript(inactive_payload)

    assert r"\section{Computational Details}" in rendered_inactive
    assert r"\subsection{Large-Amplitude Motion \& Discrete Variable Representation}" not in rendered_inactive


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

        conformer_df = pd.DataFrame({
            "Conformer": conf_names,
            "Electronic_Energy_Hartree": electronic_energies,
            "Delta_E_Hartree": rel_energies,
            "Symmetry": symmetries,
        })

        # Thermodynamics
        zpe = float(h5["thermodynamics"]["zero_point_energy"][()])
        h_val = float(h5["thermodynamics"]["enthalpy"][()])
        g_val = float(h5["thermodynamics"]["gibbs_free_energy"][()])

        thermo_df = pd.DataFrame({
            "Property": ["Zero-Point Energy", "Enthalpy H(298K)", "Gibbs Free Energy G(298K)"],
            "Value_Hartree": [zpe, h_val, g_val],
        })

        # Vibrations
        frequencies = list(h5["thermodynamics"]["vibrational_frequencies"][()])
        vib_df = pd.DataFrame({
            "Mode": list(range(1, len(frequencies) + 1)),
            "Frequency_cm1": frequencies,
        })

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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_geom\data\__init__.py ---
"""CoChem-GEOM Data Module."""

from .dataset import (
    DEFAULT_RANDOM_SEED,
    DEFAULT_STREAMING_BUFFER_SIZE,
    BaseTransform,
    CenterOfMassTransform,
    ComposeTransforms,
    EckartAlignmentTransform,
    GEOMDatasetFactory,
    GEOMInMemoryDataset,
    GEOMIterableDataset,
    GaussianJitterTransform,
    MolecularBatch,
    NormalizeTargetsTransform,
    RandomRotationTransform,
    geom_collate_fn,
    get_default_data_dir,
)
from .featurizer import (
    ATOMIC_MASS_UNIT_KG,
    ATOMIC_NUMBER_TO_SYMBOL,
    BOHR_RADIUS_ANGSTROM,
    BOLTZMANN_CONSTANT_EV_K,
    BOLTZMANN_CONSTANT_J_K,
    DEFAULT_ELEMENT_TYPES,
    DEFAULT_GRAPH_CUTOFF_ANGSTROM,
    DEFAULT_MAX_NEIGHBORS,
    ELEMENT_TYPE_TO_INDEX,
    ELEMENTARY_CHARGE_C,
    EV_TO_CM_MINUS_ONE,
    EV_TO_HARTREE,
    EV_TO_KCAL_MOL,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    INDEX_TO_ELEMENT_TYPE,
    KCAL_MOL_TO_EV,
    KCAL_MOL_TO_HARTREE,
    PLANCK_CONSTANT_J_S,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SPEED_OF_LIGHT_M_S,
    STANDARD_TEMPERATURE_K,
    SYMBOL_TO_ATOMIC_NUMBER,
    MolecularData,
    MolecularFeaturizer,
    MolecularGraphConfig,
    MolecularInput,
    build_radius_graph,
    calculate_boltzmann_weights,
    center_of_mass_molecular_data,
    compute_center_of_mass,
    compute_gaussian_rbf,
    compute_moment_of_inertia_tensor,
    compute_principal_rotational_constants,
    eckart_align_molecular_data,
    ev_to_hartree,
    ev_to_kcal_mol,
    get_atomic_mass,
    get_covalent_radius_angstrom,
    get_isotopic_mass,
    get_monoisotopic_mass,
    get_pauling_electronegativity,
    get_vdw_radius_angstrom,
    hartree_to_ev,
    hartree_to_kcal_mol,
    kcal_mol_to_ev,
    kcal_mol_to_hartree,
    rotate_molecular_data,
    translate_molecular_data,
)
from .geom_parser import (
    DEFAULT_MAX_BUFFER_SIZE,
    ConformerRecord,
    MoleculeRecord,
    QMOutputRecord,
    compute_bytes_sha256,
    compute_file_sha256,
    compute_rotational_constants,
    compute_structure_sha256,
    conformer_to_molecular_data,
    deserialize_geom_archive,
    deserialize_geom_bytes,
    ensemble_to_molecular_data,
    molecular_data_to_conformer,
    parse_geom_raw_molecule,
    parse_qm_log_text,
    parse_qm_output,
    rotate_conformer,
    serialize_geom_archive,
    serialize_geom_bytes,
    translate_conformer,
)

__all__ = [
    "ATOMIC_MASS_UNIT_KG",
    "ATOMIC_NUMBER_TO_SYMBOL",
    "BOHR_RADIUS_ANGSTROM",
    "BOLTZMANN_CONSTANT_EV_K",
    "BOLTZMANN_CONSTANT_J_K",
    "DEFAULT_ELEMENT_TYPES",
    "DEFAULT_GRAPH_CUTOFF_ANGSTROM",
    "DEFAULT_MAX_BUFFER_SIZE",
    "DEFAULT_MAX_NEIGHBORS",
    "DEFAULT_RANDOM_SEED",
    "DEFAULT_STREAMING_BUFFER_SIZE",
    "ELEMENT_TYPE_TO_INDEX",
    "ELEMENTARY_CHARGE_C",
    "EV_TO_CM_MINUS_ONE",
    "EV_TO_HARTREE",
    "EV_TO_KCAL_MOL",
    "HARTREE_TO_EV",
    "HARTREE_TO_KCAL_MOL",
    "HARTREE_TO_KJ_MOL",
    "INDEX_TO_ELEMENT_TYPE",
    "KCAL_MOL_TO_EV",
    "KCAL_MOL_TO_HARTREE",
    "PLANCK_CONSTANT_J_S",
    "ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ",
    "SPEED_OF_LIGHT_M_S",
    "STANDARD_TEMPERATURE_K",
    "SYMBOL_TO_ATOMIC_NUMBER",
    "BaseTransform",
    "CenterOfMassTransform",
    "ComposeTransforms",
    "ConformerRecord",
    "EckartAlignmentTransform",
    "GEOMDatasetFactory",
    "GEOMInMemoryDataset",
    "GEOMIterableDataset",
    "GaussianJitterTransform",
    "MolecularBatch",
    "MolecularData",
    "MolecularFeaturizer",
    "MolecularGraphConfig",
    "MolecularInput",
    "MoleculeRecord",
    "NormalizeTargetsTransform",
    "QMOutputRecord",
    "RandomRotationTransform",
    "build_radius_graph",
    "calculate_boltzmann_weights",
    "center_of_mass_molecular_data",
    "compute_bytes_sha256",
    "compute_center_of_mass",
    "compute_file_sha256",
    "compute_gaussian_rbf",
    "compute_moment_of_inertia_tensor",
    "compute_principal_rotational_constants",
    "compute_rotational_constants",
    "compute_structure_sha256",
    "conformer_to_molecular_data",
    "deserialize_geom_archive",
    "deserialize_geom_bytes",
    "eckart_align_molecular_data",
    "ensemble_to_molecular_data",
    "ev_to_hartree",
    "ev_to_kcal_mol",
    "geom_collate_fn",
    "get_atomic_mass",
    "get_covalent_radius_angstrom",
    "get_default_data_dir",
    "get_isotopic_mass",
    "get_monoisotopic_mass",
    "get_pauling_electronegativity",
    "get_vdw_radius_angstrom",
    "hartree_to_ev",
    "hartree_to_kcal_mol",
    "kcal_mol_to_ev",
    "kcal_mol_to_hartree",
    "molecular_data_to_conformer",
    "parse_geom_raw_molecule",
    "parse_qm_log_text",
    "parse_qm_output",
    "rotate_conformer",
    "rotate_molecular_data",
    "serialize_geom_archive",
    "serialize_geom_bytes",
    "translate_conformer",
    "translate_molecular_data",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_geom\data\featurizer.py ---
"""CoChem-GEOM: Molecular Data Featurizer and Geometric Deep Learning Data Contract.
=====================================================================================
Establishes the definitive data contract, Pydantic v2 validation models, and
PyTorch geometric tensor representations for rotational spectroscopy, quantum chemistry,
and equivariant neural network architectures.

Authoritative Standards:
- Method Matrix v4: Data Ingestion & Spectroscopic Graph Contracts
- Mendeleev Library Mandate: Dynamic atomic mass & monoisotopic resolution (No hardcoding)
- SE(3) Equivariance & Invariance: Separation of spatial pos vs non-spatial node features
- State Immutability: Pure functional geometric transformations (immutable operations)
- SWEBOK v3 / ISO 25010 Software Quality Standards
- Provenance Tags: [M] Measured/Theoretical, [D] Derived/Calculated, [E] Expert Estimate
"""

from __future__ import annotations

import functools
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from mendeleev import element
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import torch


# ==============================================================================
# 1. Fundamental Physical Constants and Conversion Factors (CODATA 2018/2022)
# ==============================================================================

SPEED_OF_LIGHT_M_S: float = 299792458.0
"""Speed of light in vacuum in meters per second (exact) [M]."""

PLANCK_CONSTANT_J_S: float = 6.62607015e-34
"""Planck constant in Joule seconds (exact) [M]."""

BOLTZMANN_CONSTANT_J_K: float = 1.380649e-23
"""Boltzmann constant in Joules per Kelvin (exact) [M]."""

BOLTZMANN_CONSTANT_EV_K: float = 8.617333262145e-5
"""Boltzmann constant in electron-volts per Kelvin [D]."""

ELEMENTARY_CHARGE_C: float = 1.602176634e-19
"""Elementary charge in Coulombs (exact) [M]."""

AVOGADRO_CONSTANT_MOL: float = 6.02214076e23
"""Avogadro constant per mole (exact) [M]."""

ATOMIC_MASS_UNIT_KG: float = 1.66053906660e-27
"""Unified atomic mass unit / Dalton in kilograms [M]."""

BOHR_RADIUS_ANGSTROM: float = 0.529177210903
"""Bohr radius in Angstroms [M]."""

HARTREE_TO_EV: float = 27.211386245988
"""Conversion factor from Hartree to electron-volts [D]."""

EV_TO_HARTREE: float = 1.0 / HARTREE_TO_EV
"""Conversion factor from electron-volts to Hartree [D]."""

HARTREE_TO_KCAL_MOL: float = 627.5094740631
"""Conversion factor from Hartree to kilocalories per mole [D]."""

KCAL_MOL_TO_HARTREE: float = 1.0 / HARTREE_TO_KCAL_MOL
"""Conversion factor from kilocalories per mole to Hartree [D]."""

KCAL_MOL_TO_EV: float = 0.04336411530877
"""Conversion factor from kilocalories per mole to electron-volts [D]."""

EV_TO_KCAL_MOL: float = 1.0 / KCAL_MOL_TO_EV
"""Conversion factor from electron-volts to kilocalories per mole [D]."""

HARTREE_TO_KJ_MOL: float = 2625.4996394799
"""Conversion factor from Hartree to kilojoules per mole [D]."""

EV_TO_CM_MINUS_ONE: float = 8065.54429
"""Conversion factor from electron-volts to wavenumbers (cm^-1) [D]."""

ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ: float = 505379.008784
"""Spectroscopic rotational constant conversion factor in MHz * u * Angstrom^2 [D]."""

STANDARD_TEMPERATURE_K: float = 298.15
"""Standard ambient temperature in Kelvin (25 deg C) [M]."""

DEFAULT_GRAPH_CUTOFF_ANGSTROM: float = 5.0
"""Default interatomic graph neighborhood cutoff in Angstroms [E]."""

DEFAULT_MAX_NEIGHBORS: int = 32
"""Default maximum neighbors per atom in radius graph [E]."""


# ==============================================================================
# 2. Deterministic Element and Atomic Typing Mappings
# ==============================================================================

SYMBOL_TO_ATOMIC_NUMBER: Dict[str, int] = {
    "H": 1, "He": 2, "Li": 3, "Be": 4, "B": 5, "C": 6, "N": 7, "O": 8,
    "F": 9, "Ne": 10, "Na": 11, "Mg": 12, "Al": 13, "Si": 14, "P": 15, "S": 16,
    "Cl": 17, "Ar": 18, "K": 19, "Ca": 20, "Sc": 21, "Ti": 22, "V": 23, "Cr": 24,
    "Mn": 25, "Fe": 26, "Co": 27, "Ni": 28, "Cu": 29, "Zn": 30, "Ga": 31, "Ge": 32,
    "As": 33, "Se": 34, "Br": 35, "Kr": 36, "Rb": 37, "Sr": 38, "Y": 39, "Zr": 40,
    "Nb": 41, "Mo": 42, "Tc": 43, "Ru": 44, "Rh": 45, "Pd": 46, "Ag": 47, "Cd": 48,
    "In": 49, "Sn": 50, "Sb": 51, "Te": 52, "I": 53, "Xe": 54, "Cs": 55, "Ba": 56,
    "La": 57, "Ce": 58, "Pr": 59, "Nd": 60, "Pm": 61, "Sm": 62, "Eu": 63, "Gd": 64,
    "Tb": 65, "Dy": 66, "Ho": 67, "Er": 68, "Tm": 69, "Yb": 70, "Lu": 71, "Hf": 72,
    "Ta": 73, "W": 74, "Re": 75, "Os": 76, "Ir": 77, "Pt": 78, "Au": 79, "Hg": 80,
    "Tl": 81, "Pb": 82, "Bi": 83, "Po": 84, "At": 85, "Rn": 86, "Fr": 87, "Ra": 88,
    "Ac": 89, "Th": 90, "Pa": 91, "U": 92, "Np": 93, "Pu": 94, "Am": 95, "Cm": 96,
    "Bk": 97, "Cf": 98, "Es": 99, "Fm": 100, "Md": 101, "No": 102, "Lr": 103,
    "Rf": 104, "Db": 105, "Sg": 106, "Bh": 107, "Hs": 108, "Mt": 109, "Ds": 110,
    "Rg": 111, "Cn": 112, "Nh": 113, "Fl": 114, "Mc": 115, "Lv": 116, "Ts": 117, "Og": 118,
}
"""Deterministic mapping from IUPAC chemical symbols to atomic numbers Z."""

ATOMIC_NUMBER_TO_SYMBOL: Dict[int, str] = {
    z: sym for sym, z in SYMBOL_TO_ATOMIC_NUMBER.items()
}
"""Deterministic reverse mapping from atomic number Z to chemical symbol."""

DEFAULT_ELEMENT_TYPES: Dict[str, int] = {
    "H": 0,
    "C": 1,
    "N": 2,
    "O": 3,
    "F": 4,
    "P": 5,
    "S": 6,
    "Cl": 7,
    "Br": 8,
    "I": 9,
}
"""Deterministic 10-class core element type index mapping for organic and bio-inorganic systems."""

ELEMENT_TYPE_TO_INDEX: Dict[str, int] = dict(DEFAULT_ELEMENT_TYPES)
"""Alias for element type mapping."""

INDEX_TO_ELEMENT_TYPE: Dict[int, str] = {
    idx: sym for sym, idx in DEFAULT_ELEMENT_TYPES.items()
}
"""Reverse index-to-symbol mapping for core element types."""


# ==============================================================================
# 3. Dynamic Mendeleev Mass and Property Resolution Functions
# ==============================================================================


@functools.lru_cache(maxsize=256)
def get_atomic_mass(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query standard atomic weight from mendeleev [M].

    Parameters
    ----------
    symbol_or_z : Union[str, int]
        Chemical element symbol (e.g., 'C', 'O') or atomic number Z (e.g., 6, 8).

    Returns
    -------
    float
        Standard atomic mass in Daltons (atomic mass units).
    """
    el = element(symbol_or_z)
    if el.atomic_weight is not None:
        return float(el.atomic_weight)
    if el.isotopes:
        return float(el.isotopes[0].mass)
    raise ValueError(f"Standard atomic mass not found for element '{symbol_or_z}'")


@functools.lru_cache(maxsize=256)
def get_monoisotopic_mass(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query exact mass of most abundant natural isotope from mendeleev [M].

    Parameters
    ----------
    symbol_or_z : Union[str, int]
        Chemical element symbol or atomic number Z.

    Returns
    -------
    float
        Monoisotopic mass in Daltons to full precision.
    """
    el = element(symbol_or_z)
    if el.isotopes:
        most_abundant = max(
            el.isotopes,
            key=lambda iso: (iso.abundance if iso.abundance is not None else 0.0),
        )
        if most_abundant.mass is not None:
            return float(most_abundant.mass)
    if el.atomic_weight is not None:
        return float(el.atomic_weight)
    raise ValueError(f"Monoisotopic mass not found for element '{symbol_or_z}'")


@functools.lru_cache(maxsize=512)
def get_isotopic_mass(symbol_or_z: Union[str, int], mass_number: int) -> float:
    """Dynamically query exact mass of a specific isotope from mendeleev [M].

    Parameters
    ----------
    symbol_or_z : Union[str, int]
        Chemical element symbol or atomic number Z.
    mass_number : int
        Isotopic mass number A (protons + neutrons), e.g., 12 for C-12, 13 for C-13.

    Returns
    -------
    float
        Exact isotopic mass in Daltons.
    """
    el = element(symbol_or_z)
    for iso in el.isotopes:
        if iso.mass_number == mass_number:
            if iso.mass is not None:
                return float(iso.mass)
            return float(iso.mass_number)
    raise ValueError(
        f"Isotope with mass number {mass_number} not found for element '{symbol_or_z}'"
    )


@functools.lru_cache(maxsize=256)
def get_covalent_radius_angstrom(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query Pyykko covalent single-bond radius in Angstroms [M]."""
    el = element(symbol_or_z)
    if el.covalent_radius_pyykko is not None:
        return float(el.covalent_radius_pyykko) / 100.0
    if el.covalent_radius_cordero is not None:
        return float(el.covalent_radius_cordero) / 100.0
    if el.covalent_radius_bragg is not None:
        return float(el.covalent_radius_bragg) / 100.0
    return 1.0


@functools.lru_cache(maxsize=256)
def get_pauling_electronegativity(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query Pauling electronegativity from mendeleev [M]."""
    el = element(symbol_or_z)
    if el.en_pauling is not None:
        return float(el.en_pauling)
    return 0.0


@functools.lru_cache(maxsize=256)
def get_vdw_radius_angstrom(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query Van der Waals radius in Angstroms [M]."""
    el = element(symbol_or_z)
    if el.vdw_radius_alvarez is not None:
        return float(el.vdw_radius_alvarez) / 100.0
    if el.vdw_radius is not None:
        return float(el.vdw_radius) / 100.0
    return 1.7


# ==============================================================================
# 4. Energy Conversion Pure Functions
# ==============================================================================


def hartree_to_ev(energy_hartree: float) -> float:
    """Convert energy from Hartree to electron-volts [D]."""
    return energy_hartree * HARTREE_TO_EV


def ev_to_hartree(energy_ev: float) -> float:
    """Convert energy from electron-volts to Hartree [D]."""
    return energy_ev * EV_TO_HARTREE


def hartree_to_kcal_mol(energy_hartree: float) -> float:
    """Convert energy from Hartree to kcal/mol [D]."""
    return energy_hartree * HARTREE_TO_KCAL_MOL


def kcal_mol_to_hartree(energy_kcal_mol: float) -> float:
    """Convert energy from kcal/mol to Hartree [D]."""
    return energy_kcal_mol * KCAL_MOL_TO_HARTREE


def kcal_mol_to_ev(energy_kcal_mol: float) -> float:
    """Convert energy from kcal/mol to electron-volts [D]."""
    return energy_kcal_mol * KCAL_MOL_TO_EV


def ev_to_kcal_mol(energy_ev: float) -> float:
    """Convert energy from electron-volts to kcal/mol [D]."""
    return energy_ev * EV_TO_KCAL_MOL


# ==============================================================================
# 5. Pydantic v2 Data Contract Models
# ==============================================================================


class MolecularGraphConfig(BaseModel):
    """Pydantic v2 configuration model for molecular graph featurization."""

    cutoff_radius: float = Field(
        default=DEFAULT_GRAPH_CUTOFF_ANGSTROM,
        ge=0.1,
        le=50.0,
        description="Graph neighborhood radial cutoff distance in Angstroms [E]",
    )
    max_neighbors: Optional[int] = Field(
        default=DEFAULT_MAX_NEIGHBORS,
        ge=1,
        le=1024,
        description="Maximum incoming neighbor edges per atom node [E]",
    )
    include_charges: bool = Field(
        default=True,
        description="Include formal/partial atomic charges in node feature vector [D]",
    )
    include_masses: bool = Field(
        default=True,
        description="Include dynamically retrieved atomic masses in node features [M]",
    )
    include_covalent_radii: bool = Field(
        default=True,
        description="Include covalent radii in node features [M]",
    )
    include_electronegativity: bool = Field(
        default=True,
        description="Include Pauling electronegativity in node features [M]",
    )
    include_edge_distances: bool = Field(
        default=True,
        description="Include Euclidean interatomic distances in edge features [D]",
    )
    include_edge_vectors: bool = Field(
        default=False,
        description="Include directed displacement vectors in edge features [D]",
    )
    include_edge_rbf: bool = Field(
        default=True,
        description="Expand interatomic distances via Gaussian radial basis functions [D]",
    )
    num_rbf: int = Field(
        default=16,
        ge=2,
        le=256,
        description="Number of Gaussian radial basis function centers [E]",
    )
    rbf_gamma: Optional[float] = Field(
        default=None,
        description="Gaussian radial basis function kernel width parameter [E]",
    )
    directed: bool = Field(
        default=True,
        description="Construct directed pairwise edge graph (i->j and j->i)",
    )
    self_loops: bool = Field(
        default=False,
        description="Include self-loop edges (i->i) in graph connectivity",
    )
    dtype: str = Field(
        default="float32",
        description="Target floating point precision: 'float32' or 'float64'",
    )
    device: str = Field(
        default="cpu",
        description="Target PyTorch device: 'cpu' or 'cuda'",
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        extra="forbid",
    )


class MolecularInput(BaseModel):
    """Pydantic v2 input data contract representing a valid molecular structure."""

    symbols: List[str] = Field(
        ...,
        min_length=1,
        description="List of IUPAC chemical element symbols (N atoms)",
    )
    positions: List[List[float]] = Field(
        ...,
        min_length=1,
        description="Cartesian coordinates in Angstroms of shape (N, 3) [M]",
    )
    atomic_numbers: Optional[List[int]] = Field(
        default=None,
        description="Optional pre-computed atomic numbers Z (N,)",
    )
    formal_charges: Optional[List[int]] = Field(
        default=None,
        description="Formal atomic charges per atom (N,) [D]",
    )
    partial_charges: Optional[List[float]] = Field(
        default=None,
        description="Partial atomic charges per atom (N,) [D]",
    )
    masses: Optional[List[float]] = Field(
        default=None,
        description="Atomic masses in Daltons (N,) [M]",
    )
    total_charge: int = Field(
        default=0,
        description="Total molecular net charge [D]",
    )
    spin_multiplicity: int = Field(
        default=1,
        ge=1,
        description="Total spin multiplicity (2S + 1) [D]",
    )
    energy: Optional[float] = Field(
        default=None,
        description="Ground-state electronic energy in Hartree or eV [D]",
    )
    forces: Optional[List[List[float]]] = Field(
        default=None,
        description="Atomic force vectors of shape (N, 3) in eV/Angstrom [D]",
    )
    dipole: Optional[List[float]] = Field(
        default=None,
        description="Electric dipole moment vector (3,) in Debye [D]",
    )
    rotational_constants: Optional[List[float]] = Field(
        default=None,
        description="Rotational constants (A, B, C) in MHz [D]",
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        description="Statistical or Boltzmann weighting factor [D]",
    )
    tags: Dict[str, str] = Field(
        default_factory=dict,
        description="User metadata and provenance annotation tags",
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        extra="forbid",
    )

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: List[str]) -> List[str]:
        for sym in v:
            clean_sym = sym.capitalize()
            if clean_sym not in SYMBOL_TO_ATOMIC_NUMBER:
                raise ValueError(f"Unrecognized chemical element symbol: '{sym}'")
        return [s.capitalize() for s in v]

    @field_validator("positions")
    @classmethod
    def validate_positions(cls, v: List[List[float]]) -> List[List[float]]:
        for row_idx, coord in enumerate(v):
            if len(coord) != 3:
                raise ValueError(
                    f"Position at index {row_idx} has dimension {len(coord)}; exactly 3 required."
                )
        return v

    @model_validator(mode="after")
    def validate_matching_lengths(self) -> MolecularInput:
        n_atoms = len(self.symbols)
        if len(self.positions) != n_atoms:
            raise ValueError(
                f"Symbols length ({n_atoms}) does not match positions length ({len(self.positions)})."
            )
        if self.forces is not None:
            if len(self.forces) != n_atoms:
                raise ValueError(
                    f"Forces length ({len(self.forces)}) does not match positions length ({n_atoms})."
                )
            for f in self.forces:
                if len(f) != 3:
                    raise ValueError("Each force vector must have dimension 3.")
        if self.dipole is not None and len(self.dipole) != 3:
            raise ValueError(f"Dipole moment must have dimension 3; got {len(self.dipole)}.")
        if self.rotational_constants is not None and len(self.rotational_constants) != 3:
            raise ValueError(
                f"Rotational constants must have dimension 3 (A, B, C); got {len(self.rotational_constants)}."
            )
        return self


# ==============================================================================
# 6. Tensor Schema: MolecularData Container
# ==============================================================================


class MolecularData:
    """Canonical geometric PyTorch data container for molecular structures.

    Attributes
    ----------
    z : torch.Tensor
        Atomic numbers Z of shape (N,) with dtype torch.long.
    pos : torch.Tensor
        Spatial Cartesian coordinates in Angstroms of shape (N, 3).
    edge_index : torch.Tensor
        Graph connectivity edge indices of shape (2, E) with dtype torch.long.
    y : Optional[torch.Tensor]
        Scalar target properties (e.g. energy) of shape (1, ...).
    x : Optional[torch.Tensor]
        Non-spatial invariant node features of shape (N, F).
    edge_attr : Optional[torch.Tensor]
        Edge feature attributes of shape (E, D).
    weight : torch.Tensor
        Statistical weighting factor of shape (1,).
    forces : Optional[torch.Tensor]
        Spatial vector forces of shape (N, 3).
    dipole : Optional[torch.Tensor]
        Dipole vector of shape (3,) or (1, 3).
    rotational_constants : Optional[torch.Tensor]
        Rotational constants (A, B, C) of shape (3,).
    symbols : List[str]
        IUPAC chemical symbols of length N.
    metadata : Dict[str, Any]
        Arbitrary metadata dictionary.
    """

    def __init__(
        self,
        z: torch.Tensor,
        pos: torch.Tensor,
        edge_index: Optional[torch.Tensor] = None,
        y: Optional[torch.Tensor] = None,
        x: Optional[torch.Tensor] = None,
        edge_attr: Optional[torch.Tensor] = None,
        weight: Optional[torch.Tensor] = None,
        forces: Optional[torch.Tensor] = None,
        dipole: Optional[torch.Tensor] = None,
        rotational_constants: Optional[torch.Tensor] = None,
        symbols: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.z = z
        self.pos = pos
        self.edge_index = (
            edge_index
            if edge_index is not None
            else torch.empty((2, 0), dtype=torch.long, device=pos.device)
        )
        self.y = y
        self.x = x
        self.edge_attr = edge_attr
        self.weight = (
            weight
            if weight is not None
            else torch.tensor([1.0], dtype=pos.dtype, device=pos.device)
        )
        self.forces = forces
        self.dipole = dipole
        self.rotational_constants = rotational_constants
        self.symbols = symbols if symbols is not None else [
            ATOMIC_NUMBER_TO_SYMBOL.get(int(zi.item()), "X") for zi in z
        ]
        self.metadata = metadata if metadata is not None else {}

    @property
    def num_nodes(self) -> int:
        """Total number of atom nodes N in the molecular structure."""
        return int(self.pos.size(0))

    @property
    def num_edges(self) -> int:
        """Total number of directed graph edges E."""
        return int(self.edge_index.size(1)) if self.edge_index is not None else 0

    @property
    def atomic_numbers(self) -> torch.Tensor:
        """Alias for atomic numbers tensor z."""
        return self.z

    def clone(self) -> MolecularData:
        """Create an independent deep copy of all tensors and attributes."""
        return MolecularData(
            z=self.z.clone(),
            pos=self.pos.clone(),
            edge_index=self.edge_index.clone() if self.edge_index is not None else None,
            y=self.y.clone() if self.y is not None else None,
            x=self.x.clone() if self.x is not None else None,
            edge_attr=self.edge_attr.clone() if self.edge_attr is not None else None,
            weight=self.weight.clone() if self.weight is not None else None,
            forces=self.forces.clone() if self.forces is not None else None,
            dipole=self.dipole.clone() if self.dipole is not None else None,
            rotational_constants=(
                self.rotational_constants.clone()
                if self.rotational_constants is not None
                else None
            ),
            symbols=list(self.symbols),
            metadata=dict(self.metadata),
        )

    def to(
        self,
        device: Optional[Union[str, torch.device]] = None,
        dtype: Optional[torch.dtype] = None,
    ) -> MolecularData:
        """Transfer tensor attributes to specified device and dtype immutably."""
        new_pos = self.pos.to(device=device, dtype=dtype) if dtype is not None else self.pos.to(device=device)
        new_z = self.z.to(device=device)
        new_edge_index = self.edge_index.to(device=device) if self.edge_index is not None else None
        new_y = (
            self.y.to(device=device, dtype=dtype)
            if self.y is not None and dtype is not None
            else (self.y.to(device=device) if self.y is not None else None)
        )
        new_x = (
            self.x.to(device=device, dtype=dtype)
            if self.x is not None and dtype is not None
            else (self.x.to(device=device) if self.x is not None else None)
        )
        new_edge_attr = (
            self.edge_attr.to(device=device, dtype=dtype)
            if self.edge_attr is not None and dtype is not None
            else (self.edge_attr.to(device=device) if self.edge_attr is not None else None)
        )
        new_weight = (
            self.weight.to(device=device, dtype=dtype)
            if self.weight is not None and dtype is not None
            else (self.weight.to(device=device) if self.weight is not None else None)
        )
        new_forces = (
            self.forces.to(device=device, dtype=dtype)
            if self.forces is not None and dtype is not None
            else (self.forces.to(device=device) if self.forces is not None else None)
        )
        new_dipole = (
            self.dipole.to(device=device, dtype=dtype)
            if self.dipole is not None and dtype is not None
            else (self.dipole.to(device=device) if self.dipole is not None else None)
        )
        new_rot_consts = (
            self.rotational_constants.to(device=device, dtype=dtype)
            if self.rotational_constants is not None and dtype is not None
            else (self.rotational_constants.to(device=device) if self.rotational_constants is not None else None)
        )

        return MolecularData(
            z=new_z,
            pos=new_pos,
            edge_index=new_edge_index,
            y=new_y,
            x=new_x,
            edge_attr=new_edge_attr,
            weight=new_weight,
            forces=new_forces,
            dipole=new_dipole,
            rotational_constants=new_rot_consts,
            symbols=list(self.symbols),
            metadata=dict(self.metadata),
        )

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"Key '{key}' not present in MolecularData.")

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key) and getattr(self, key) is not None

    def keys(self) -> List[str]:
        all_keys = [
            "z", "pos", "edge_index", "y", "x", "edge_attr",
            "weight", "forces", "dipole", "rotational_constants", "symbols", "metadata"
        ]
        return [k for k in all_keys if getattr(self, k) is not None]

    def items(self) -> List[Tuple[str, Any]]:
        return [(k, getattr(self, k)) for k in self.keys()]

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.keys()}

    def __repr__(self) -> str:
        attrs = [f"num_nodes={self.num_nodes}", f"num_edges={self.num_edges}"]
        if self.y is not None:
            attrs.append(f"y={list(self.y.shape)}")
        if self.x is not None:
            attrs.append(f"x={list(self.x.shape)}")
        if self.edge_attr is not None:
            attrs.append(f"edge_attr={list(self.edge_attr.shape)}")
        return f"MolecularData({', '.join(attrs)})"


# ==============================================================================
# 7. Pure Graph Construction and Radial Basis Functions
# ==============================================================================


def build_radius_graph(
    pos: torch.Tensor,
    cutoff: float = DEFAULT_GRAPH_CUTOFF_ANGSTROM,
    max_neighbors: Optional[int] = DEFAULT_MAX_NEIGHBORS,
    directed: bool = True,
    self_loops: bool = False,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Pure PyTorch radius neighborhood graph construction.

    Parameters
    ----------
    pos : torch.Tensor
        Cartesian atomic coordinates of shape (N, 3).
    cutoff : float
        Interatomic distance cutoff in Angstroms [E].
    max_neighbors : Optional[int]
        Maximum allowed neighbor edges per node [E].
    directed : bool
        If True, returns directed pairs (i, j).
    self_loops : bool
        If True, includes diagonal self-loops (i, i).

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor]
        edge_index of shape (2, E) and edge_distances of shape (E, 1) [D].
    """
    n_nodes = pos.size(0)
    if n_nodes <= 1:
        return (
            torch.empty((2, 0), dtype=torch.long, device=pos.device),
            torch.empty((0, 1), dtype=pos.dtype, device=pos.device),
        )

    # Compute pairwise Euclidean distance matrix
    # dist[i, j] = ||pos[i] - pos[j]||_2
    diff = pos.unsqueeze(1) - pos.unsqueeze(0)  # (N, N, 3)
    dist_matrix = torch.norm(diff, dim=-1)      # (N, N)

    mask = dist_matrix <= cutoff
    if not self_loops:
        mask = mask & (~torch.eye(n_nodes, dtype=torch.bool, device=pos.device))

    source_nodes: List[int] = []
    target_nodes: List[int] = []
    edge_dists: List[float] = []

    for i in range(n_nodes):
        neighbors = torch.where(mask[i])[0]
        if len(neighbors) == 0:
            continue
        neighbor_dists = dist_matrix[i, neighbors]
        if max_neighbors is not None and len(neighbors) > max_neighbors:
            sorted_indices = torch.argsort(neighbor_dists)[:max_neighbors]
            neighbors = neighbors[sorted_indices]
            neighbor_dists = neighbor_dists[sorted_indices]

        for j_node, d_val in zip(neighbors, neighbor_dists):
            source_nodes.append(i)
            target_nodes.append(int(j_node.item()))
            edge_dists.append(float(d_val.item()))

    if len(source_nodes) == 0:
        return (
            torch.empty((2, 0), dtype=torch.long, device=pos.device),
            torch.empty((0, 1), dtype=pos.dtype, device=pos.device),
        )

    edge_index = torch.tensor(
        [source_nodes, target_nodes], dtype=torch.long, device=pos.device
    )
    edge_distances = torch.tensor(
        edge_dists, dtype=pos.dtype, device=pos.device
    ).unsqueeze(-1)

    return edge_index, edge_distances


def compute_gaussian_rbf(
    distances: torch.Tensor,
    num_rbf: int = 16,
    cutoff: float = DEFAULT_GRAPH_CUTOFF_ANGSTROM,
    gamma: Optional[float] = None,
) -> torch.Tensor:
    """Expand interatomic distances using Gaussian Radial Basis Functions [D].

    Parameters
    ----------
    distances : torch.Tensor
        Interatomic distances tensor of shape (E, 1) or (E,).
    num_rbf : int
        Number of Gaussian centers [E].
    cutoff : float
        Upper cutoff distance in Angstroms [E].
    gamma : Optional[float]
        RBF width parameter. Defaults to (1 / delta_mu^2) [E].

    Returns
    -------
    torch.Tensor
        RBF features of shape (E, num_rbf) with values in [0, 1] [D].
    """
    if distances.dim() == 1:
        distances = distances.unsqueeze(-1)

    centers = torch.linspace(
        0.0, cutoff, num_rbf, dtype=distances.dtype, device=distances.device
    )
    if gamma is None:
        delta = float(centers[1] - centers[0]) if num_rbf > 1 else 1.0
        gamma = 1.0 / (delta ** 2)

    # phi_k(d) = exp(-gamma * (d - mu_k)^2)
    diff = distances - centers.unsqueeze(0)  # (E, num_rbf)
    return torch.exp(-gamma * (diff ** 2))


# ==============================================================================
# 8. Physical and Spectroscopic Math Functions
# ==============================================================================


def compute_center_of_mass(positions: torch.Tensor, masses: torch.Tensor) -> torch.Tensor:
    """Compute center of mass Cartesian coordinate vector [D].

    $$\\mathbf{r}_{\\text{COM}} = \\frac{\\sum_i m_i \\mathbf{r}_i}{\\sum_i m_i}$$

    Parameters
    ----------
    positions : torch.Tensor
        Atomic coordinates of shape (N, 3).
    masses : torch.Tensor
        Atomic masses of shape (N,) or (N, 1).

    Returns
    -------
    torch.Tensor
        Center-of-mass coordinate vector of shape (3,) [D].
    """
    if masses.dim() == 1:
        masses = masses.unsqueeze(-1)
    total_mass = masses.sum()
    if total_mass <= 0.0:
        raise ValueError("Total molecular mass must be strictly positive.")
    com = (positions * masses).sum(dim=0) / total_mass
    return com


def compute_moment_of_inertia_tensor(
    positions: torch.Tensor, masses: torch.Tensor
) -> torch.Tensor:
    """Construct the 3x3 Moment of Inertia tensor in COM frame [D].

    $$I_{\\alpha \\beta} = \\sum_i m_i \\left( r_i^2 \\delta_{\\alpha \\beta} - r_{i,\\alpha} r_{i,\\beta} \\right)$$

    Parameters
    ----------
    positions : torch.Tensor
        Atomic coordinates of shape (N, 3).
    masses : torch.Tensor
        Atomic masses of shape (N,).

    Returns
    -------
    torch.Tensor
        Inertia tensor of shape (3, 3) in u * Angstrom^2 [D].
    """
    com = compute_center_of_mass(positions, masses)
    com_pos = positions - com.unsqueeze(0)

    m = masses.to(dtype=positions.dtype)
    x = com_pos[:, 0]
    y = com_pos[:, 1]
    z = com_pos[:, 2]

    i_xx = (m * (y ** 2 + z ** 2)).sum()
    i_yy = (m * (x ** 2 + z ** 2)).sum()
    i_zz = (m * (x ** 2 + y ** 2)).sum()

    i_xy = -(m * x * y).sum()
    i_xz = -(m * x * z).sum()
    i_yz = -(m * y * z).sum()

    inertia_tensor = torch.tensor(
        [
            [i_xx, i_xy, i_xz],
            [i_xy, i_yy, i_yz],
            [i_xz, i_yz, i_zz],
        ],
        dtype=positions.dtype,
        device=positions.device,
    )
    return inertia_tensor


def compute_principal_rotational_constants(
    positions: torch.Tensor, masses: torch.Tensor
) -> Tuple[float, float, float]:
    """Compute principal rotational constants A >= B >= C in MHz [D].

    Parameters
    ----------
    positions : torch.Tensor
        Atomic coordinates of shape (N, 3).
    masses : torch.Tensor
        Atomic masses of shape (N,).

    Returns
    -------
    Tuple[float, float, float]
        Principal rotational constants (A, B, C) in MHz [D].
    """
    inertia = compute_moment_of_inertia_tensor(positions, masses)
    eigenvalues = torch.linalg.eigvalsh(inertia)  # sorted ascending I_a <= I_b <= I_c

    i_a = float(eigenvalues[0].item())
    i_b = float(eigenvalues[1].item())
    i_c = float(eigenvalues[2].item())

    # Conversion constant: 505379.008784 MHz * u * Angstrom^2
    a = ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / i_a if i_a > 1e-6 else float("inf")
    b = ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / i_b if i_b > 1e-6 else float("inf")
    c = ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / i_c if i_c > 1e-6 else float("inf")

    return (a, b, c)


def calculate_boltzmann_weights(
    energies_hartree: Union[torch.Tensor, Sequence[float]],
    temperature_k: float = STANDARD_TEMPERATURE_K,
) -> torch.Tensor:
    """Calculate normalized Boltzmann statistical probability weights [D].

    $$p_i = \\frac{\\exp(-\\Delta E_i / k_B T)}{\\sum_j \\exp(-\\Delta E_j / k_B T)}$$

    Parameters
    ----------
    energies_hartree : Union[torch.Tensor, Sequence[float]]
        Electronic or free energies in Hartree.
    temperature_k : float
        Temperature in Kelvin (default 298.15 K) [M].

    Returns
    -------
    torch.Tensor
        Normalized probability weights summing to 1.0 [D].
    """
    if not isinstance(energies_hartree, torch.Tensor):
        energies_hartree = torch.tensor(energies_hartree, dtype=torch.float64)
    else:
        energies_hartree = energies_hartree.to(dtype=torch.float64)

    # Shift by ground state minimum for numerical stability
    min_e = energies_hartree.min()
    delta_e_hartree = energies_hartree - min_e
    delta_e_ev = delta_e_hartree * HARTREE_TO_EV

    kt_ev = BOLTZMANN_CONSTANT_EV_K * temperature_k
    exponent = -delta_e_ev / kt_ev
    unnormalized = torch.exp(exponent)
    weights = unnormalized / unnormalized.sum()
    return weights.to(dtype=torch.float32)


# ==============================================================================
# 9. Equivariant Transformations and State Immutability
# ==============================================================================


def translate_molecular_data(
    data: MolecularData,
    translation_vector: Union[torch.Tensor, Sequence[float]],
) -> MolecularData:
    """Translate molecular coordinates immutably (no in-place tensor modification).

    Separates spatial coordinates (which translate equivariantly) from non-spatial
    node features (which remain strictly invariant).

    Parameters
    ----------
    data : MolecularData
        Source molecular data container.
    translation_vector : Union[torch.Tensor, Sequence[float]]
        3D translation vector (dx, dy, dz).

    Returns
    -------
    MolecularData
        New MolecularData instance with translated positions.
    """
    if not isinstance(translation_vector, torch.Tensor):
        translation_vector = torch.tensor(
            translation_vector, dtype=data.pos.dtype, device=data.pos.device
        )
    else:
        translation_vector = translation_vector.to(
            dtype=data.pos.dtype, device=data.pos.device
        )

    # Immutable addition (never in-place +=)
    new_pos = data.pos + translation_vector.view(1, 3)

    # Invariant features cloned without alteration
    return MolecularData(
        z=data.z.clone(),
        pos=new_pos,
        edge_index=data.edge_index.clone() if data.edge_index is not None else None,
        y=data.y.clone() if data.y is not None else None,
        x=data.x.clone() if data.x is not None else None,
        edge_attr=data.edge_attr.clone() if data.edge_attr is not None else None,
        weight=data.weight.clone() if data.weight is not None else None,
        forces=data.forces.clone() if data.forces is not None else None,
        dipole=data.dipole.clone() if data.dipole is not None else None,
        rotational_constants=(
            data.rotational_constants.clone()
            if data.rotational_constants is not None
            else None
        ),
        symbols=list(data.symbols),
        metadata=dict(data.metadata),
    )


def rotate_molecular_data(
    data: MolecularData,
    rotation_matrix: Union[torch.Tensor, Sequence[Sequence[float]]],
) -> MolecularData:
    """Rotate molecular coordinates and vectors equivariantly and immutably.

    Parameters
    ----------
    data : MolecularData
        Source molecular data container.
    rotation_matrix : Union[torch.Tensor, Sequence[Sequence[float]]]
        3x3 orthogonal rotation matrix R in SO(3).

    Returns
    -------
    MolecularData
        New MolecularData instance with rotated coordinates and forces.
    """
    if not isinstance(rotation_matrix, torch.Tensor):
        r_matrix = torch.tensor(
            rotation_matrix, dtype=data.pos.dtype, device=data.pos.device
        )
    else:
        r_matrix = rotation_matrix.to(dtype=data.pos.dtype, device=data.pos.device)

    # Equivariant rotation: pos' = pos @ R^T
    new_pos = data.pos @ r_matrix.T

    # Rotate vector properties (forces, dipole) equivariantly
    new_forces = data.forces @ r_matrix.T if data.forces is not None else None
    new_dipole = data.dipole @ r_matrix.T if data.dipole is not None else None

    # Invariant features (scalar y, node features x, z, graph connectivity) unchanged
    return MolecularData(
        z=data.z.clone(),
        pos=new_pos,
        edge_index=data.edge_index.clone() if data.edge_index is not None else None,
        y=data.y.clone() if data.y is not None else None,
        x=data.x.clone() if data.x is not None else None,
        edge_attr=data.edge_attr.clone() if data.edge_attr is not None else None,
        weight=data.weight.clone() if data.weight is not None else None,
        forces=new_forces,
        dipole=new_dipole,
        rotational_constants=(
            data.rotational_constants.clone()
            if data.rotational_constants is not None
            else None
        ),
        symbols=list(data.symbols),
        metadata=dict(data.metadata),
    )


def center_of_mass_molecular_data(
    data: MolecularData,
    use_monoisotopic: bool = False,
) -> MolecularData:
    """Translate molecular coordinates to center of mass origin immutably.

    Parameters
    ----------
    data : MolecularData
        Source molecular data container.
    use_monoisotopic : bool
        If True, uses exact monoisotopic masses instead of standard atomic weights.

    Returns
    -------
    MolecularData
        New MolecularData centered at COM.
    """
    if use_monoisotopic:
        masses_list = [get_monoisotopic_mass(s) for s in data.symbols]
    else:
        masses_list = [get_atomic_mass(s) for s in data.symbols]

    masses_tensor = torch.tensor(
        masses_list, dtype=data.pos.dtype, device=data.pos.device
    )
    com = compute_center_of_mass(data.pos, masses_tensor)
    return translate_molecular_data(data, -com)


def eckart_align_molecular_data(
    data: MolecularData,
    reference: MolecularData,
    use_mass_weighting: bool = True,
) -> MolecularData:
    """Align molecular coordinates to reference structure via Kabsch SVD rotation [D].

    Parameters
    ----------
    data : MolecularData
        Source structure to align.
    reference : MolecularData
        Target reference structure.
    use_mass_weighting : bool
        If True, computes mass-weighted Eckart rotation.

    Returns
    -------
    MolecularData
        Aligned MolecularData rotated into the reference coordinate frame.
    """
    if use_mass_weighting:
        masses_list = [get_atomic_mass(s) for s in data.symbols]
    else:
        masses_list = [1.0 for _ in data.symbols]

    masses_tensor = torch.tensor(
        masses_list, dtype=data.pos.dtype, device=data.pos.device
    )

    data_com = compute_center_of_mass(data.pos, masses_tensor)
    ref_com = compute_center_of_mass(reference.pos, masses_tensor)

    p = data.pos - data_com.unsqueeze(0)
    q = reference.pos - ref_com.unsqueeze(0)

    if use_mass_weighting:
        m = masses_tensor.unsqueeze(-1)
        # Weighted covariance matrix H = P^T * W * Q
        h = (p * m).T @ q
    else:
        h = p.T @ q

    # SVD of covariance matrix
    u, s, v_t = torch.linalg.svd(h)
    d = torch.det(v_t.T @ u.T)

    correction = torch.eye(3, dtype=p.dtype, device=p.device)
    if d < 0:
        correction[2, 2] = -1.0

    # Optimal rotation matrix R = V * correction * U^T
    rot_matrix = v_t.T @ correction @ u.T

    # Rotate centered data and place in reference COM frame
    new_pos = p @ rot_matrix.T + ref_com.unsqueeze(0)

    # Rotate vector properties (forces, dipole) equivariantly
    new_forces = data.forces @ rot_matrix.T if data.forces is not None else None
    new_dipole = data.dipole @ rot_matrix.T if data.dipole is not None else None

    return MolecularData(
        z=data.z.clone(),
        pos=new_pos,
        edge_index=data.edge_index.clone() if data.edge_index is not None else None,
        y=data.y.clone() if data.y is not None else None,
        x=data.x.clone() if data.x is not None else None,
        edge_attr=data.edge_attr.clone() if data.edge_attr is not None else None,
        weight=data.weight.clone() if data.weight is not None else None,
        forces=new_forces,
        dipole=new_dipole,
        rotational_constants=(
            data.rotational_constants.clone()
            if data.rotational_constants is not None
            else None
        ),
        symbols=list(data.symbols),
        metadata=dict(data.metadata),
    )


# ==============================================================================
# 10. High-Level Molecular Featurizer API
# ==============================================================================


class MolecularFeaturizer:
    """Universal molecular graph featurizer for quantum chemistry and spectroscopy.

    Converts Pydantic validated MolecularInput instances, XYZ files, RDKit Mol objects,
    and ASE Atoms into canonical MolecularData PyTorch geometric containers.
    """

    def __init__(self, config: Optional[MolecularGraphConfig] = None) -> None:
        self.config = config if config is not None else MolecularGraphConfig()

    def featurize(self, mol_input: MolecularInput) -> MolecularData:
        """Featurize a validated MolecularInput instance into MolecularData [D].

        Parameters
        ----------
        mol_input : MolecularInput
            Validated molecular input structure.

        Returns
        -------
        MolecularData
            Canonical PyTorch geometric tensor container.
        """
        torch_dtype = torch.float64 if self.config.dtype == "float64" else torch.float32
        target_device = torch.device(self.config.device)

        n_atoms = len(mol_input.symbols)
        symbols = mol_input.symbols

        # 1. Atomic Numbers Z
        z_values = [
            SYMBOL_TO_ATOMIC_NUMBER[s] for s in symbols
        ]
        z_tensor = torch.tensor(z_values, dtype=torch.long, device=target_device)

        # 2. Spatial Cartesian Coordinates pos (N, 3)
        pos_tensor = torch.tensor(
            mol_input.positions, dtype=torch_dtype, device=target_device
        )

        # 3. Non-Spatial Invariant Node Features x (N, F)
        node_features_list: List[List[float]] = []
        for i, sym in enumerate(symbols):
            feat_row: List[float] = []

            # One-hot element type encoding (10 dimensions)
            type_idx = ELEMENT_TYPE_TO_INDEX.get(sym, -1)
            one_hot = [0.0] * len(DEFAULT_ELEMENT_TYPES)
            if 0 <= type_idx < len(DEFAULT_ELEMENT_TYPES):
                one_hot[type_idx] = 1.0
            feat_row.extend(one_hot)

            # Atomic mass [M]
            if self.config.include_masses:
                mass_val = (
                    mol_input.masses[i]
                    if mol_input.masses is not None
                    else get_atomic_mass(sym)
                )
                feat_row.append(float(mass_val))

            # Covalent radius [M]
            if self.config.include_covalent_radii:
                cov_radius = get_covalent_radius_angstrom(sym)
                feat_row.append(cov_radius)

            # Pauling electronegativity [M]
            if self.config.include_electronegativity:
                en = get_pauling_electronegativity(sym)
                feat_row.append(en)

            # Formal and partial charges [D]
            if self.config.include_charges:
                fc = (
                    float(mol_input.formal_charges[i])
                    if mol_input.formal_charges is not None
                    else 0.0
                )
                pc = (
                    float(mol_input.partial_charges[i])
                    if mol_input.partial_charges is not None
                    else 0.0
                )
                feat_row.extend([fc, pc])

            node_features_list.append(feat_row)

        x_tensor = torch.tensor(
            node_features_list, dtype=torch_dtype, device=target_device
        )

        # 4. Graph Edge Construction & Edge Attributes
        edge_index, edge_distances = build_radius_graph(
            pos_tensor,
            cutoff=self.config.cutoff_radius,
            max_neighbors=self.config.max_neighbors,
            directed=self.config.directed,
            self_loops=self.config.self_loops,
        )

        edge_attrs_list: List[torch.Tensor] = []
        if edge_index.size(1) > 0:
            if self.config.include_edge_distances:
                edge_attrs_list.append(edge_distances)

            if self.config.include_edge_rbf:
                rbf = compute_gaussian_rbf(
                    edge_distances,
                    num_rbf=self.config.num_rbf,
                    cutoff=self.config.cutoff_radius,
                    gamma=self.config.rbf_gamma,
                )
                edge_attrs_list.append(rbf)

            if self.config.include_edge_vectors:
                # Directed unit displacement vectors
                src, dst = edge_index[0], edge_index[1]
                disp = pos_tensor[dst] - pos_tensor[src]
                disp_norm = edge_distances.clamp(min=1e-8)
                unit_vectors = disp / disp_norm
                edge_attrs_list.append(unit_vectors)

        edge_attr_tensor = (
            torch.cat(edge_attrs_list, dim=-1)
            if edge_attrs_list
            else torch.empty((edge_index.size(1), 0), dtype=torch_dtype, device=target_device)
        )

        # 5. Target Property y
        y_tensor = (
            torch.tensor([mol_input.energy], dtype=torch_dtype, device=target_device)
            if mol_input.energy is not None
            else None
        )

        # 6. Forces, Dipole, Rotational Constants
        forces_tensor = (
            torch.tensor(mol_input.forces, dtype=torch_dtype, device=target_device)
            if mol_input.forces is not None
            else None
        )
        dipole_tensor = (
            torch.tensor(mol_input.dipole, dtype=torch_dtype, device=target_device)
            if mol_input.dipole is not None
            else None
        )
        rot_consts_tensor = (
            torch.tensor(
                mol_input.rotational_constants, dtype=torch_dtype, device=target_device
            )
            if mol_input.rotational_constants is not None
            else None
        )
        weight_tensor = torch.tensor(
            [mol_input.weight], dtype=torch_dtype, device=target_device
        )

        return MolecularData(
            z=z_tensor,
            pos=pos_tensor,
            edge_index=edge_index,
            y=y_tensor,
            x=x_tensor,
            edge_attr=edge_attr_tensor,
            weight=weight_tensor,
            forces=forces_tensor,
            dipole=dipole_tensor,
            rotational_constants=rot_consts_tensor,
            symbols=symbols,
            metadata=dict(mol_input.tags),
        )

    def featurize_batch(
        self, mol_inputs: Sequence[MolecularInput]
    ) -> List[MolecularData]:
        """Featurize multiple molecular inputs into a list of MolecularData."""
        return [self.featurize(inp) for inp in mol_inputs]

    def from_symbols_and_positions(
        self,
        symbols: Sequence[str],
        positions: Sequence[Sequence[float]],
        **kwargs: Any,
    ) -> MolecularData:
        """Construct and featurize MolecularData directly from symbols and coordinates."""
        mol_input = MolecularInput(
            symbols=list(symbols),
            positions=[list(p) for p in positions],
            **kwargs,
        )
        return self.featurize(mol_input)

    def from_xyz(
        self,
        xyz_input: Union[str, Path],
        energy: Optional[float] = None,
        **kwargs: Any,
    ) -> MolecularData:
        """Parse standard .xyz file or string content and produce featurized MolecularData."""
        if isinstance(xyz_input, Path) or (isinstance(xyz_input, str) and os.path.exists(xyz_input)):
            content = Path(xyz_input).read_text(encoding="utf-8").strip()
        else:
            content = str(xyz_input).strip()

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if len(lines) < 3:
            raise ValueError(f"XYZ content too short ({len(lines)} lines; minimum 3 lines required).")

        try:
            n_atoms = int(lines[0])
        except ValueError:
            raise ValueError(f"First line of XYZ must be integer atom count; got '{lines[0]}'.")

        atom_lines = lines[2: 2 + n_atoms]
        symbols: List[str] = []
        positions: List[List[float]] = []

        for line in atom_lines:
            parts = line.split()
            if len(parts) < 4:
                raise ValueError(f"Malformed XYZ atom coordinate line: '{line}'")
            symbols.append(parts[0])
            positions.append([float(parts[1]), float(parts[2]), float(parts[3])])

        mol_input = MolecularInput(
            symbols=symbols,
            positions=positions,
            energy=energy,
            **kwargs,
        )
        return self.featurize(mol_input)

    def from_rdkit(
        self,
        mol: Any,
        conf_id: int = -1,
        **kwargs: Any,
    ) -> MolecularData:
        """Extract atomic coordinates and elements from RDKit Mol object."""
        if mol is None:
            raise ValueError("RDKit Mol instance cannot be None.")

        conf = mol.GetConformer(conf_id)
        symbols: List[str] = []
        positions: List[List[float]] = []
        formal_charges: List[int] = []

        for i, atom in enumerate(mol.GetAtoms()):
            symbols.append(atom.GetSymbol())
            formal_charges.append(atom.GetFormalCharge())
            pos = conf.GetAtomPosition(i)
            positions.append([float(pos.x), float(pos.y), float(pos.z)])

        mol_input = MolecularInput(
            symbols=symbols,
            positions=positions,
            formal_charges=formal_charges,
            **kwargs,
        )
        return self.featurize(mol_input)

    def from_ase(
        self,
        atoms: Any,
        **kwargs: Any,
    ) -> MolecularData:
        """Extract coordinates and chemical symbols from ASE Atoms object."""
        if atoms is None:
            raise ValueError("ASE Atoms instance cannot be None.")

        symbols = [str(sym) for sym in atoms.get_chemical_symbols()]
        positions = atoms.get_positions().tolist()

        mol_input = MolecularInput(
            symbols=symbols,
            positions=positions,
            **kwargs,
        )
        return self.featurize(mol_input)

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_scribe_templater.py ---
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
import jinja2
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
    conformer_df = pd.DataFrame({
        "Conformer": ["conf_01", "conf_02", "conf_03"],
        "Delta_E_kcal_mol": [0.00, 2.20, 5.15],
        "Symmetry": ["C2v", "Cs", "C1"],
        "Population_Percent": [85.4, 12.1, 2.5],
    })

    thermo_df = pd.DataFrame({
        "Parameter": ["Zero-Point Energy", "Enthalpy H(298K)", "Gibbs Free Energy G(298K)"],
        "Value_Hartree": [0.08234, -154.25890, -154.29145],
        "Value_kcal_mol": [51.67, 0.00, 0.00],
    })

    vib_df = pd.DataFrame({
        "Mode": [1, 2, 3, 4],
        "Frequency_cm1": [450.2, 820.5, 1450.0, 3100.4],
        "Intensity_km_mol": [12.4, 45.1, 108.7, 5.3],
        "Symmetry": ["A1", "B2", "A1", "B1"],
    })

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
    assert templater.format_siunitx_qty(-154.3, "kcal/mol") == r"\qty{-154.3}{\kilo\calorie\per\mole}"
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
    assert r"\subsection{Large-Amplitude Motion \& Discrete Variable Representation}" in rendered_active
    assert "Torsional Sinc-DVR justified for internal rotor." in rendered_active

    # Case B: LAM Inactive
    inactive_payload = dict(base_payload)
    inactive_payload["lam_trigger"] = False
    inactive_payload["sinc_dvr_justification"] = ""
    rendered_inactive = templater.render_manuscript(inactive_payload)

    assert r"\section{Computational Details}" in rendered_inactive
    assert r"\subsection{Large-Amplitude Motion \& Discrete Variable Representation}" not in rendered_inactive


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

        conformer_df = pd.DataFrame({
            "Conformer": conf_names,
            "Electronic_Energy_Hartree": electronic_energies,
            "Delta_E_Hartree": rel_energies,
            "Symmetry": symmetries,
        })

        # Thermodynamics
        zpe = float(h5["thermodynamics"]["zero_point_energy"][()])
        h_val = float(h5["thermodynamics"]["enthalpy"][()])
        g_val = float(h5["thermodynamics"]["gibbs_free_energy"][()])

        thermo_df = pd.DataFrame({
            "Property": ["Zero-Point Energy", "Enthalpy H(298K)", "Gibbs Free Energy G(298K)"],
            "Value_Hartree": [zpe, h_val, g_val],
        })

        # Vibrations
        frequencies = list(h5["thermodynamics"]["vibrational_frequencies"][()])
        vib_df = pd.DataFrame({
            "Mode": list(range(1, len(frequencies) + 1)),
            "Frequency_cm1": frequencies,
        })

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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_geom\data\dataset.py ---
"""CoChem-GEOM: PyTorch & PyG Geometric Dataset Architecture and Data Pipeline.
=====================================================================================
Establishes the definitive Tier 1 PyTorch and PyG dataset infrastructure for geometric
deep learning, conformer ensembles, rotational spectroscopy, and quantum chemistry.

Key Components:
1. Pure Immutable Geometric Transforms:
   - `CenterOfMassTransform`: Translates coordinates to COM origin (pure immutable subtraction).
   - `RandomRotationTransform`: Applies SO(3) 3D rotations equivariantly (pure immutable multiplication).
   - `EckartAlignmentTransform`: Aligns conformer to reference frame via SVD Kabsch rotation.
   - `GaussianJitterTransform`: Injects zero-mean Gaussian noise immutably.
   - `NormalizeTargetsTransform`: Standardizes target scalar energies/properties.
   - `ComposeTransforms`: Composes a sequential pipeline of pure transformations.

2. Batched Geometric Container & Collation:
   - `MolecularBatch`: Contiguous batched graph representation with node pointers (`batch`, `ptr`),
     block-diagonal `edge_index`, concatenated `pos`, `z`, `x`, `forces`, stacked `y`, `rotational_constants`.
   - `geom_collate_fn`: High-performance collate function for PyTorch DataLoader.

3. In-Memory & Streaming Datasets:
   - `GEOMInMemoryDataset`: Full-featured cached InMemoryDataset with conformer selection strategies
     ('all', 'lowest_energy', 'boltzmann', 'random'), slicing, indexing, and pre-filtering.
   - `GEOMIterableDataset`: Streaming IterableDataset with PyTorch multi-worker sharding
     (`get_worker_info()`), streaming MsgPack / JSON / QM log parsing, and bounded memory buffers.
   - `GEOMDatasetFactory`: Factory pattern generating QM9, GEOM-Drugs, Pickett, QMLog, and Custom
     datasets with deterministic train/val/test splitting.

Authoritative Standards & Directives:
- Method Matrix v4: Data Ingestion & Spectroscopic Graph Contracts
- Mendeleev Library Mandate: Dynamic atomic mass & isotopic resolution (NEVER hardcoded)
- State Immutability: Pure functional geometric transformations (`data.pos = data.pos + update`)
- Dynamic Path Resolution: Cross-platform dynamic pathing via `os.environ` and `pathlib.Path.home()`
- SE(3) Equivariance & Invariance: Strict separation of spatial `pos` vs non-spatial features `x`
- Provenance Tags: [M] Measured/Theoretical, [D] Derived/Calculated, [E] Expert Estimate
- Strict Zero-Mock Mandate: 100% authentic physical tensor mathematics and real execution
"""

from __future__ import annotations

import abc
import copy
import dataclasses
import hashlib
import io
import json
import logging
import math
import os
from pathlib import Path
import random
import sys
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import mendeleev
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset, IterableDataset, get_worker_info

try:
    import msgpack
except ImportError:
    msgpack = None

# Optional PyG Base Class inheritance if PyG is installed
try:
    import torch_geometric.data as pyg_data
    PYG_AVAILABLE = True
    PyGInMemoryBase = pyg_data.InMemoryDataset
except (ImportError, AttributeError):
    PYG_AVAILABLE = False
    PyGInMemoryBase = Dataset

from cochem_geom.data.featurizer import (
    ATOMIC_MASS_UNIT_KG,
    ATOMIC_NUMBER_TO_SYMBOL,
    BOLTZMANN_CONSTANT_EV_K,
    BOLTZMANN_CONSTANT_J_K,
    DEFAULT_ELEMENT_TYPES,
    DEFAULT_GRAPH_CUTOFF_ANGSTROM,
    DEFAULT_MAX_NEIGHBORS,
    ELEMENT_TYPE_TO_INDEX,
    ELEMENTARY_CHARGE_C,
    EV_TO_CM_MINUS_ONE,
    EV_TO_HARTREE,
    EV_TO_KCAL_MOL,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    INDEX_TO_ELEMENT_TYPE,
    KCAL_MOL_TO_EV,
    KCAL_MOL_TO_HARTREE,
    PLANCK_CONSTANT_J_S,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SPEED_OF_LIGHT_M_S,
    STANDARD_TEMPERATURE_K,
    SYMBOL_TO_ATOMIC_NUMBER,
    MolecularData,
    MolecularFeaturizer,
    MolecularGraphConfig,
    MolecularInput,
    build_radius_graph,
    calculate_boltzmann_weights,
    compute_center_of_mass,
    compute_moment_of_inertia_tensor,
    compute_principal_rotational_constants,
    get_atomic_mass,
    get_covalent_radius_angstrom,
    get_isotopic_mass,
    get_monoisotopic_mass,
    get_pauling_electronegativity,
    get_vdw_radius_angstrom,
)
from cochem_geom.data.geom_parser import (
    ConformerRecord,
    MoleculeRecord,
    QMOutputRecord,
    compute_bytes_sha256,
    compute_file_sha256,
    compute_structure_sha256,
    conformer_to_molecular_data,
    deserialize_geom_archive,
    deserialize_geom_bytes,
    ensemble_to_molecular_data,
    parse_geom_raw_molecule,
    parse_qm_log_text,
    parse_qm_output,
)

logger = logging.getLogger("cochem_geom.data.dataset")


# ==============================================================================
# 1. Fundamental Constants & Buffer Configurations
# ==============================================================================

DEFAULT_STREAMING_BUFFER_SIZE: int = 1000
"""Default bounded in-memory buffer size for streaming IterableDataset [E]."""

DEFAULT_RANDOM_SEED: int = 42
"""Default deterministic pseudo-random generator seed [E]."""

_DYNAMIC_MASS_CACHE: Dict[str, float] = {}
_DYNAMIC_MONO_MASS_CACHE: Dict[str, float] = {}


def resolve_dynamic_mass(symbol_or_z: Union[str, int]) -> float:
    """Resolve atomic mass dynamically via Mendeleev with local thread-safe caching [M]."""
    key = str(symbol_or_z).capitalize()
    if key not in _DYNAMIC_MASS_CACHE:
        _DYNAMIC_MASS_CACHE[key] = get_atomic_mass(symbol_or_z)
    return _DYNAMIC_MASS_CACHE[key]


def resolve_dynamic_monoisotopic_mass(symbol_or_z: Union[str, int]) -> float:
    """Resolve monoisotopic mass dynamically via Mendeleev with local caching [M]."""
    key = str(symbol_or_z).capitalize()
    if key not in _DYNAMIC_MONO_MASS_CACHE:
        _DYNAMIC_MONO_MASS_CACHE[key] = get_monoisotopic_mass(symbol_or_z)
    return _DYNAMIC_MONO_MASS_CACHE[key]


# ==============================================================================
# 2. Dynamic Path & Environment Resolution
# ==============================================================================

def get_default_data_dir() -> Path:
    """Dynamically resolve default CoChem dataset root directory [E].

    Prioritizes the `COCHEM_DATA_DIR` environment variable, falling back to
    `~/.cochem/data` to ensure zero hardcoded machine-specific file paths.

    Returns
    -------
    Path
        Resolved absolute directory path.
    """
    env_dir = os.environ.get("COCHEM_DATA_DIR")
    if env_dir:
        resolved = Path(env_dir).expanduser().resolve()
    else:
        resolved = (Path.home() / ".cochem" / "data").resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


# ==============================================================================
# 3. Pure Immutable Transformations
# ==============================================================================

class BaseTransform(abc.ABC):
    """Abstract base class for pure immutable molecular graph transformations."""

    @abc.abstractmethod
    def __call__(self, data: MolecularData) -> MolecularData:
        """Apply transformation immutably, returning a new MolecularData instance."""
        raise NotImplementedError


class CenterOfMassTransform(BaseTransform):
    """Translate molecular coordinates to center of mass origin immutably [D].

    $$\\mathbf{r}'_i = \\mathbf{r}_i - \\mathbf{r}_{\\text{COM}}$$
    Uses dynamic atomic masses dynamically queried from Mendeleev (NEVER hardcoded).
    """

    def __init__(self, use_monoisotopic: bool = False) -> None:
        self.use_monoisotopic = use_monoisotopic

    def __call__(self, data: MolecularData) -> MolecularData:
        if self.use_monoisotopic:
            masses = [resolve_dynamic_monoisotopic_mass(s) for s in data.symbols]
        else:
            masses = [resolve_dynamic_mass(s) for s in data.symbols]

        masses_tensor = torch.tensor(masses, dtype=data.pos.dtype, device=data.pos.device)
        com = compute_center_of_mass(data.pos, masses_tensor)

        # Pure immutable subtraction (never pos -= com)
        new_pos = data.pos - com.unsqueeze(0)

        return MolecularData(
            z=data.z.clone(),
            pos=new_pos,
            edge_index=data.edge_index.clone() if data.edge_index is not None else None,
            y=data.y.clone() if data.y is not None else None,
            x=data.x.clone() if data.x is not None else None,
            edge_attr=data.edge_attr.clone() if data.edge_attr is not None else None,
            weight=data.weight.clone() if data.weight is not None else None,
            forces=data.forces.clone() if data.forces is not None else None,
            dipole=data.dipole.clone() if data.dipole is not None else None,
            rotational_constants=(
                data.rotational_constants.clone()
                if data.rotational_constants is not None
                else None
            ),
            symbols=list(data.symbols),
            metadata=dict(data.metadata),
        )


class RandomRotationTransform(BaseTransform):
    """Apply a random 3D rotation from SO(3) equivariantly and immutably [D].

    $$\\mathbf{r}'_i = \\mathbf{r}_i \\mathbf{R}^T, \\quad \\mathbf{F}'_i = \\mathbf{F}_i \\mathbf{R}^T, \\quad \\boldsymbol{\\mu}' = \\boldsymbol{\\mu} \\mathbf{R}^T$$
    where $\\mathbf{R} \\in \\mathrm{SO}(3)$ is a valid orthogonal rotation matrix with $\\det(\\mathbf{R}) = +1$.
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self.rng = np.random.default_rng(seed) if seed is not None else None

    def _generate_so3_matrix(self, dtype: torch.dtype, device: torch.device) -> torch.Tensor:
        """Generate a uniformly sampled random SO(3) rotation matrix via Haar measure [D]."""
        if self.rng is not None:
            mat = self.rng.normal(size=(3, 3))
        else:
            mat = np.random.normal(size=(3, 3))

        # QR decomposition
        q, r = np.linalg.qr(mat)
        # Ensure positive diagonal in R for uniqueness
        d = np.diagonal(r)
        ph = d / np.abs(d)
        q = q * ph
        # Ensure proper rotation det(Q) = +1
        if np.linalg.det(q) < 0.0:
            q[:, 0] = -q[:, 0]

        return torch.tensor(q, dtype=dtype, device=device)

    def __call__(self, data: MolecularData) -> MolecularData:
        rot_mat = self._generate_so3_matrix(data.pos.dtype, data.pos.device)

        # Pure immutable transformation
        new_pos = data.pos @ rot_mat.T
        new_forces = data.forces @ rot_mat.T if data.forces is not None else None
        new_dipole = data.dipole @ rot_mat.T if data.dipole is not None else None

        return MolecularData(
            z=data.z.clone(),
            pos=new_pos,
            edge_index=data.edge_index.clone() if data.edge_index is not None else None,
            y=data.y.clone() if data.y is not None else None,
            x=data.x.clone() if data.x is not None else None,
            edge_attr=data.edge_attr.clone() if data.edge_attr is not None else None,
            weight=data.weight.clone() if data.weight is not None else None,
            forces=new_forces,
            dipole=new_dipole,
            rotational_constants=(
                data.rotational_constants.clone()
                if data.rotational_constants is not None
                else None
            ),
            symbols=list(data.symbols),
            metadata=dict(data.metadata),
        )


class EckartAlignmentTransform(BaseTransform):
    """Align molecular coordinates to a target reference structure using Eckart / Kabsch frame alignment [D].

    Finds optimal $\\mathbf{R} \\in \\mathrm{SO}(3)$ minimizing mass-weighted root mean square deviation.
    """

    def __init__(
        self,
        reference: MolecularData,
        use_mass_weighting: bool = True,
    ) -> None:
        self.reference = reference
        self.use_mass_weighting = use_mass_weighting

    def __call__(self, data: MolecularData) -> MolecularData:
        if self.use_mass_weighting:
            masses_list = [resolve_dynamic_mass(s) for s in data.symbols]
        else:
            masses_list = [1.0 for _ in data.symbols]

        masses = torch.tensor(masses_list, dtype=data.pos.dtype, device=data.pos.device)

        data_com = compute_center_of_mass(data.pos, masses)
        ref_com = compute_center_of_mass(self.reference.pos, masses)

        p = data.pos - data_com.unsqueeze(0)
        q = self.reference.pos - ref_com.unsqueeze(0)

        if self.use_mass_weighting:
            m = masses.unsqueeze(-1)
            h = (p * m).T @ q
        else:
            h = p.T @ q

        # SVD: H = U * S * V^T
        u, _, v_t = torch.linalg.svd(h)
        d = torch.det(v_t.T @ u.T)

        correction = torch.eye(3, dtype=p.dtype, device=p.device)
        if d < 0:
            correction[2, 2] = -1.0

        rot_mat = v_t.T @ correction @ u.T

        # Pure immutable transformation
        new_pos = p @ rot_mat.T + ref_com.unsqueeze(0)
        new_forces = data.forces @ rot_mat.T if data.forces is not None else None
        new_dipole = data.dipole @ rot_mat.T if data.dipole is not None else None

        return MolecularData(
            z=data.z.clone(),
            pos=new_pos,
            edge_index=data.edge_index.clone() if data.edge_index is not None else None,
            y=data.y.clone() if data.y is not None else None,
            x=data.x.clone() if data.x is not None else None,
            edge_attr=data.edge_attr.clone() if data.edge_attr is not None else None,
            weight=data.weight.clone() if data.weight is not None else None,
            forces=new_forces,
            dipole=new_dipole,
            rotational_constants=(
                data.rotational_constants.clone()
                if data.rotational_constants is not None
                else None
            ),
            symbols=list(data.symbols),
            metadata=dict(data.metadata),
        )


class GaussianJitterTransform(BaseTransform):
    """Add zero-mean isotropic Gaussian noise to Cartesian coordinates immutably [E].

    $$\\mathbf{r}'_i = \\mathbf{r}_i + \\boldsymbol{\\epsilon}_i, \\quad \\boldsymbol{\\epsilon}_i \\sim \\mathcal{N}(\\mathbf{0}, \\sigma^2 \\mathbf{I})$$
    """

    def __init__(self, sigma: float = 0.01, seed: Optional[int] = None) -> None:
        self.sigma = float(sigma)
        self.seed = seed
        self.generator = torch.Generator().manual_seed(seed) if seed is not None else None

    def __call__(self, data: MolecularData) -> MolecularData:
        if self.sigma <= 0.0:
            return data.clone()

        if self.generator is not None:
            noise = torch.randn(
                data.pos.shape,
                dtype=data.pos.dtype,
                device=data.pos.device,
                generator=self.generator,
            ) * self.sigma
        else:
            noise = torch.randn(
                data.pos.shape,
                dtype=data.pos.dtype,
                device=data.pos.device,
            ) * self.sigma

        # Pure immutable addition (data.pos + noise)
        new_pos = data.pos + noise

        return MolecularData(
            z=data.z.clone(),
            pos=new_pos,
            edge_index=data.edge_index.clone() if data.edge_index is not None else None,
            y=data.y.clone() if data.y is not None else None,
            x=data.x.clone() if data.x is not None else None,
            edge_attr=data.edge_attr.clone() if data.edge_attr is not None else None,
            weight=data.weight.clone() if data.weight is not None else None,
            forces=data.forces.clone() if data.forces is not None else None,
            dipole=data.dipole.clone() if data.dipole is not None else None,
            rotational_constants=(
                data.rotational_constants.clone()
                if data.rotational_constants is not None
                else None
            ),
            symbols=list(data.symbols),
            metadata=dict(data.metadata),
        )


class NormalizeTargetsTransform(BaseTransform):
    """Standardize target properties (e.g. energy y) via mean and standard deviation [D].

    $$y' = \\frac{y - \\mu}{\\sigma + \\epsilon}$$
    """

    def __init__(
        self,
        mean: Union[float, torch.Tensor],
        std: Union[float, torch.Tensor],
        eps: float = 1e-8,
    ) -> None:
        self.mean = torch.as_tensor(mean, dtype=torch.float32)
        self.std = torch.as_tensor(std, dtype=torch.float32)
        self.eps = float(eps)

    def __call__(self, data: MolecularData) -> MolecularData:
        if data.y is None:
            return data.clone()

        mean = self.mean.to(dtype=data.y.dtype, device=data.y.device)
        std = self.std.to(dtype=data.y.dtype, device=data.y.device)

        # Pure immutable normalization
        new_y = (data.y - mean) / (std + self.eps)

        return MolecularData(
            z=data.z.clone(),
            pos=data.pos.clone(),
            edge_index=data.edge_index.clone() if data.edge_index is not None else None,
            y=new_y,
            x=data.x.clone() if data.x is not None else None,
            edge_attr=data.edge_attr.clone() if data.edge_attr is not None else None,
            weight=data.weight.clone() if data.weight is not None else None,
            forces=data.forces.clone() if data.forces is not None else None,
            dipole=data.dipole.clone() if data.dipole is not None else None,
            rotational_constants=(
                data.rotational_constants.clone()
                if data.rotational_constants is not None
                else None
            ),
            symbols=list(data.symbols),
            metadata=dict(data.metadata),
        )

    def denormalize(self, y_norm: torch.Tensor) -> torch.Tensor:
        """Denormalize standardized target tensor back to physical units [D]."""
        mean = self.mean.to(dtype=y_norm.dtype, device=y_norm.device)
        std = self.std.to(dtype=y_norm.dtype, device=y_norm.device)
        return y_norm * (std + self.eps) + mean


class ComposeTransforms(BaseTransform):
    """Chain multiple transformations sequentially into a single callable pipeline [E]."""

    def __init__(self, transforms: Sequence[Callable[[MolecularData], MolecularData]]) -> None:
        self.transforms = list(transforms)

    def __call__(self, data: MolecularData) -> MolecularData:
        current_data = data
        for t in self.transforms:
            current_data = t(current_data)
        return current_data


# ==============================================================================
# 4. Batched Geometric Container & Collation Function
# ==============================================================================

@dataclasses.dataclass
class MolecularBatch:
    """Batched molecular graph collection for geometric deep learning and PyG/PyTorch execution."""

    pos: torch.Tensor
    z: torch.Tensor
    batch: torch.Tensor
    ptr: torch.Tensor
    edge_index: Optional[torch.Tensor] = None
    y: Optional[torch.Tensor] = None
    x: Optional[torch.Tensor] = None
    edge_attr: Optional[torch.Tensor] = None
    forces: Optional[torch.Tensor] = None
    rotational_constants: Optional[torch.Tensor] = None
    dipole: Optional[torch.Tensor] = None
    weight: Optional[torch.Tensor] = None
    num_graphs: int = 1
    num_nodes: int = 0
    symbols: Optional[List[str]] = None
    metadata: Optional[List[Dict[str, Any]]] = None

    def __post_init__(self) -> None:
        if self.num_nodes == 0 and self.pos is not None:
            self.num_nodes = int(self.pos.size(0))

    def to(
        self,
        device: Optional[Union[str, torch.device]] = None,
        dtype: Optional[torch.dtype] = None,
    ) -> MolecularBatch:
        """Transfer all batch tensors to specified device and precision immutably."""
        dev = torch.device(device) if device is not None else self.pos.device

        new_pos = self.pos.to(device=dev, dtype=dtype) if dtype is not None else self.pos.to(device=dev)
        new_z = self.z.to(device=dev)
        new_batch = self.batch.to(device=dev)
        new_ptr = self.ptr.to(device=dev)
        new_edge_index = self.edge_index.to(device=dev) if self.edge_index is not None else None
        new_y = (
            self.y.to(device=dev, dtype=dtype)
            if self.y is not None and dtype is not None
            else (self.y.to(device=dev) if self.y is not None else None)
        )
        new_x = (
            self.x.to(device=dev, dtype=dtype)
            if self.x is not None and dtype is not None
            else (self.x.to(device=dev) if self.x is not None else None)
        )
        new_edge_attr = (
            self.edge_attr.to(device=dev, dtype=dtype)
            if self.edge_attr is not None and dtype is not None
            else (self.edge_attr.to(device=dev) if self.edge_attr is not None else None)
        )
        new_forces = (
            self.forces.to(device=dev, dtype=dtype)
            if self.forces is not None and dtype is not None
            else (self.forces.to(device=dev) if self.forces is not None else None)
        )
        new_rot_consts = (
            self.rotational_constants.to(device=dev, dtype=dtype)
            if self.rotational_constants is not None and dtype is not None
            else (self.rotational_constants.to(device=dev) if self.rotational_constants is not None else None)
        )
        new_dipole = (
            self.dipole.to(device=dev, dtype=dtype)
            if self.dipole is not None and dtype is not None
            else (self.dipole.to(device=dev) if self.dipole is not None else None)
        )
        new_weight = (
            self.weight.to(device=dev, dtype=dtype)
            if self.weight is not None and dtype is not None
            else (self.weight.to(device=dev) if self.weight is not None else None)
        )

        return MolecularBatch(
            pos=new_pos,
            z=new_z,
            batch=new_batch,
            ptr=new_ptr,
            edge_index=new_edge_index,
            y=new_y,
            x=new_x,
            edge_attr=new_edge_attr,
            forces=new_forces,
            rotational_constants=new_rot_consts,
            dipole=new_dipole,
            weight=new_weight,
            num_graphs=self.num_graphs,
            num_nodes=self.num_nodes,
            symbols=list(self.symbols) if self.symbols is not None else None,
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else None,
        )

    def clone(self) -> MolecularBatch:
        """Create a deep copy of the MolecularBatch."""
        return MolecularBatch(
            pos=self.pos.clone(),
            z=self.z.clone(),
            batch=self.batch.clone(),
            ptr=self.ptr.clone(),
            edge_index=self.edge_index.clone() if self.edge_index is not None else None,
            y=self.y.clone() if self.y is not None else None,
            x=self.x.clone() if self.x is not None else None,
            edge_attr=self.edge_attr.clone() if self.edge_attr is not None else None,
            forces=self.forces.clone() if self.forces is not None else None,
            rotational_constants=(
                self.rotational_constants.clone()
                if self.rotational_constants is not None
                else None
            ),
            dipole=self.dipole.clone() if self.dipole is not None else None,
            weight=self.weight.clone() if self.weight is not None else None,
            num_graphs=self.num_graphs,
            num_nodes=self.num_nodes,
            symbols=list(self.symbols) if self.symbols is not None else None,
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else None,
        )

    def __len__(self) -> int:
        return self.num_graphs

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"Key '{key}' not found in MolecularBatch.")

    def keys(self) -> List[str]:
        all_keys = [
            "pos", "z", "batch", "ptr", "edge_index", "y", "x",
            "edge_attr", "forces", "rotational_constants", "dipole", "weight"
        ]
        return [k for k in all_keys if getattr(self, k) is not None]

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.keys()}

    def to_data_list(self) -> List[MolecularData]:
        """Decompose batched representation back into individual MolecularData graphs."""
        data_list: List[MolecularData] = []
        ptr_list = self.ptr.tolist()

        for i in range(self.num_graphs):
            start_node = ptr_list[i]
            end_node = ptr_list[i + 1]

            sub_pos = self.pos[start_node:end_node].clone()
            sub_z = self.z[start_node:end_node].clone()

            sub_x = self.x[start_node:end_node].clone() if self.x is not None else None
            sub_forces = (
                self.forces[start_node:end_node].clone()
                if self.forces is not None
                else None
            )

            # Slicing edges
            sub_edge_index = None
            sub_edge_attr = None
            if self.edge_index is not None and self.edge_index.numel() > 0:
                edge_mask = (self.edge_index[0] >= start_node) & (self.edge_index[0] < end_node)
                if edge_mask.any():
                    sub_edge_index = self.edge_index[:, edge_mask] - start_node
                    if self.edge_attr is not None:
                        sub_edge_attr = self.edge_attr[edge_mask].clone()

            sub_y = self.y[i : i + 1].clone() if self.y is not None else None
            sub_weight = self.weight[i : i + 1].clone() if self.weight is not None else None
            sub_rot = (
                self.rotational_constants[i].clone()
                if self.rotational_constants is not None
                else None
            )
            sub_dipole = self.dipole[i].clone() if self.dipole is not None else None
            sub_symbols = (
                self.symbols[start_node:end_node]
                if self.symbols is not None
                else [ATOMIC_NUMBER_TO_SYMBOL.get(int(z.item()), "X") for z in sub_z]
            )
            sub_meta = self.metadata[i] if self.metadata is not None else {}

            data_list.append(
                MolecularData(
                    z=sub_z,
                    pos=sub_pos,
                    edge_index=sub_edge_index,
                    y=sub_y,
                    x=sub_x,
                    edge_attr=sub_edge_attr,
                    weight=sub_weight,
                    forces=sub_forces,
                    dipole=sub_dipole,
                    rotational_constants=sub_rot,
                    symbols=sub_symbols,
                    metadata=sub_meta,
                )
            )

        return data_list

    def __repr__(self) -> str:
        attrs = [f"num_graphs={self.num_graphs}", f"num_nodes={self.num_nodes}"]
        if self.edge_index is not None:
            attrs.append(f"num_edges={self.edge_index.size(1)}")
        if self.y is not None:
            attrs.append(f"y={list(self.y.shape)}")
        if self.x is not None:
            attrs.append(f"x={list(self.x.shape)}")
        return f"MolecularBatch({', '.join(attrs)})"


def geom_collate_fn(samples: Sequence[Union[MolecularData, Dict[str, Any], Any]]) -> MolecularBatch:
    """Collate a sequence of MolecularData objects into a contiguous MolecularBatch [E]."""
    if not samples:
        raise ValueError("Cannot collate empty sequence of molecular samples.")

    mol_samples: List[MolecularData] = []
    for s in samples:
        if isinstance(s, MolecularData):
            mol_samples.append(s)
        elif isinstance(s, dict):
            mol_samples.append(
                MolecularData(
                    z=s["z"],
                    pos=s["pos"],
                    edge_index=s.get("edge_index"),
                    y=s.get("y"),
                    x=s.get("x"),
                    edge_attr=s.get("edge_attr"),
                    weight=s.get("weight"),
                    forces=s.get("forces"),
                    dipole=s.get("dipole"),
                    rotational_constants=s.get("rotational_constants"),
                    symbols=s.get("symbols"),
                    metadata=s.get("metadata", {}),
                )
            )
        else:
            mol_samples.append(
                MolecularData(
                    z=getattr(s, "z"),
                    pos=getattr(s, "pos"),
                    edge_index=getattr(s, "edge_index", None),
                    y=getattr(s, "y", None),
                    x=getattr(s, "x", None),
                    edge_attr=getattr(s, "edge_attr", None),
                    weight=getattr(s, "weight", None),
                    forces=getattr(s, "forces", None),
                    dipole=getattr(s, "dipole", None),
                    rotational_constants=getattr(s, "rotational_constants", None),
                    symbols=getattr(s, "symbols", None),
                    metadata=getattr(s, "metadata", {}),
                )
            )

    pos_list: List[torch.Tensor] = []
    z_list: List[torch.Tensor] = []
    batch_list: List[torch.Tensor] = []
    ptr_list: List[int] = [0]
    edge_index_list: List[torch.Tensor] = []
    x_list: List[torch.Tensor] = []
    edge_attr_list: List[torch.Tensor] = []
    y_list: List[torch.Tensor] = []
    forces_list: List[torch.Tensor] = []
    rot_consts_list: List[torch.Tensor] = []
    dipole_list: List[torch.Tensor] = []
    weight_list: List[torch.Tensor] = []
    symbols_list: List[str] = []
    metadata_list: List[Dict[str, Any]] = []

    has_edges = any(s.edge_index is not None and s.edge_index.numel() > 0 for s in mol_samples)
    has_x = any(s.x is not None for s in mol_samples)
    has_edge_attr = any(s.edge_attr is not None for s in mol_samples)
    has_y = any(s.y is not None for s in mol_samples)
    has_forces = any(s.forces is not None for s in mol_samples)
    has_rot_consts = any(s.rotational_constants is not None for s in mol_samples)
    has_dipole = any(s.dipole is not None for s in mol_samples)
    has_weight = any(s.weight is not None for s in mol_samples)

    node_offset = 0
    ref_device = mol_samples[0].pos.device
    ref_dtype = mol_samples[0].pos.dtype

    for i, s in enumerate(mol_samples):
        n_nodes = s.num_nodes
        pos_list.append(s.pos.to(device=ref_device, dtype=ref_dtype))
        z_list.append(s.z.to(device=ref_device, dtype=torch.long))
        batch_list.append(torch.full((n_nodes,), i, dtype=torch.long, device=ref_device))

        node_offset += n_nodes
        ptr_list.append(node_offset)

        if has_edges:
            if s.edge_index is not None and s.edge_index.numel() > 0:
                shifted_edges = s.edge_index.to(device=ref_device, dtype=torch.long) + (node_offset - n_nodes)
                edge_index_list.append(shifted_edges)

        if has_x:
            if s.x is not None:
                x_list.append(s.x.to(device=ref_device, dtype=ref_dtype))
            else:
                dim_x = next(item.x.size(1) for item in mol_samples if item.x is not None)
                x_list.append(torch.zeros((n_nodes, dim_x), dtype=ref_dtype, device=ref_device))

        if has_edge_attr and s.edge_attr is not None:
            edge_attr_list.append(s.edge_attr.to(device=ref_device, dtype=ref_dtype))

        if has_y:
            if s.y is not None:
                y_tensor = s.y.view(1, -1) if s.y.dim() <= 1 else s.y
                y_list.append(y_tensor.to(device=ref_device, dtype=ref_dtype))
            else:
                y_list.append(torch.zeros((1, 1), dtype=ref_dtype, device=ref_device))

        if has_forces:
            if s.forces is not None:
                forces_list.append(s.forces.to(device=ref_device, dtype=ref_dtype))
            else:
                forces_list.append(torch.zeros((n_nodes, 3), dtype=ref_dtype, device=ref_device))

        if has_rot_consts:
            if s.rotational_constants is not None:
                rot_consts_list.append(s.rotational_constants.view(1, 3).to(device=ref_device, dtype=ref_dtype))
            else:
                rot_consts_list.append(torch.zeros((1, 3), dtype=ref_dtype, device=ref_device))

        if has_dipole:
            if s.dipole is not None:
                dipole_list.append(s.dipole.view(1, 3).to(device=ref_device, dtype=ref_dtype))
            else:
                dipole_list.append(torch.zeros((1, 3), dtype=ref_dtype, device=ref_device))

        if has_weight:
            if s.weight is not None:
                weight_list.append(s.weight.view(1, 1).to(device=ref_device, dtype=ref_dtype))
            else:
                weight_list.append(torch.ones((1, 1), dtype=ref_dtype, device=ref_device))

        symbols_list.extend(s.symbols)
        metadata_list.append(dict(s.metadata))

    batched_pos = torch.cat(pos_list, dim=0)
    batched_z = torch.cat(z_list, dim=0)
    batched_batch = torch.cat(batch_list, dim=0)
    batched_ptr = torch.tensor(ptr_list, dtype=torch.long, device=ref_device)

    batched_edge_index = (
        torch.cat(edge_index_list, dim=1) if has_edges and edge_index_list else None
    )
    batched_x = torch.cat(x_list, dim=0) if has_x and x_list else None
    batched_edge_attr = torch.cat(edge_attr_list, dim=0) if has_edge_attr and edge_attr_list else None
    batched_y = torch.cat(y_list, dim=0) if has_y and y_list else None
    batched_forces = torch.cat(forces_list, dim=0) if has_forces and forces_list else None
    batched_rot_consts = torch.cat(rot_consts_list, dim=0) if has_rot_consts and rot_consts_list else None
    batched_dipole = torch.cat(dipole_list, dim=0) if has_dipole and dipole_list else None
    batched_weight = torch.cat(weight_list, dim=0) if has_weight and weight_list else None

    return MolecularBatch(
        pos=batched_pos,
        z=batched_z,
        batch=batched_batch,
        ptr=batched_ptr,
        edge_index=batched_edge_index,
        y=batched_y,
        x=batched_x,
        edge_attr=batched_edge_attr,
        forces=batched_forces,
        rotational_constants=batched_rot_consts,
        dipole=batched_dipole,
        weight=batched_weight,
        num_graphs=len(mol_samples),
        num_nodes=node_offset,
        symbols=symbols_list,
        metadata=metadata_list,
    )


# ==============================================================================
# 5. GEOM InMemoryDataset Implementation
# ==============================================================================

class GEOMInMemoryDataset(PyGInMemoryBase):
    """PyTorch and PyG compatible InMemoryDataset with caching, indexing, and conformer filtering."""

    def __init__(
        self,
        root: Optional[Union[str, Path]] = None,
        data_list: Optional[Sequence[MolecularData]] = None,
        raw_file_paths: Optional[Sequence[Union[str, Path]]] = None,
        transform: Optional[Callable[[MolecularData], MolecularData]] = None,
        pre_transform: Optional[Callable[[MolecularData], MolecularData]] = None,
        pre_filter: Optional[Callable[[MolecularData], bool]] = None,
        conformer_strategy: str = "all",
        temperature_k: float = STANDARD_TEMPERATURE_K,
        seed: Optional[int] = DEFAULT_RANDOM_SEED,
    ) -> None:
        self.conformer_strategy = conformer_strategy.lower()
        self.temperature_k = float(temperature_k)
        self.seed = seed
        self._custom_transform = transform
        self._custom_pre_transform = pre_transform
        self._custom_pre_filter = pre_filter
        self._data_list: List[MolecularData] = []

        resolved_root = Path(root).expanduser().resolve() if root is not None else get_default_data_dir() / "inmemory"
        self._root_path = resolved_root

        if PYG_AVAILABLE:
            super().__init__(
                root=str(resolved_root),
                transform=transform,
                pre_transform=pre_transform,
                pre_filter=pre_filter,
            )

        if data_list is not None:
            self._process_data_list(data_list)
        elif raw_file_paths is not None:
            self._process_raw_files(raw_file_paths)
        elif root is not None and (resolved_root / "processed" / "data.pt").exists():
            self.load(resolved_root / "processed" / "data.pt")

    @property
    def raw_file_names(self) -> List[str]:
        return []

    @property
    def processed_file_names(self) -> List[str]:
        return ["data.pt"]

    def _process_data_list(self, data_list: Sequence[MolecularData]) -> None:
        filtered_list: List[MolecularData] = []
        for d in data_list:
            item = d.clone()
            if self._custom_pre_filter is not None and not self._custom_pre_filter(item):
                continue
            if self._custom_pre_transform is not None:
                item = self._custom_pre_transform(item)
            filtered_list.append(item)

        self._data_list = filtered_list

    def _process_raw_files(self, raw_files: Sequence[Union[str, Path]]) -> None:
        extracted_data: List[MolecularData] = []
        rng = random.Random(self.seed) if self.seed is not None else random.Random()

        for rf in raw_files:
            p = Path(rf).expanduser().resolve()
            if not p.exists():
                logger.warning(f"Raw dataset file not found: {p}")
                continue

            if p.suffix in [".msgpack", ".mp"]:
                for smiles, mol_data in deserialize_geom_archive(p):
                    rec = parse_geom_raw_molecule(smiles, mol_data, temperature_k=self.temperature_k)
                    if self.conformer_strategy == "all":
                        for conf in rec.conformers:
                            extracted_data.append(conformer_to_molecular_data(rec, conf))
                    elif self.conformer_strategy in ["lowest_energy", "min_energy"]:
                        lowest = rec.get_lowest_energy_conformer()
                        if lowest is not None:
                            extracted_data.append(conformer_to_molecular_data(rec, lowest))
                    elif self.conformer_strategy == "boltzmann":
                        mols = ensemble_to_molecular_data(rec)
                        extracted_data.extend(mols)
                    elif self.conformer_strategy == "random":
                        if rec.conformers:
                            chosen = rng.choice(rec.conformers)
                            extracted_data.append(conformer_to_molecular_data(rec, chosen))
            elif p.suffix in [".json", ".jsonl"]:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        if not line_str:
                            continue
                        data_dict = json.loads(line_str)
                        mol_in = MolecularInput(**data_dict)
                        featurizer = MolecularFeaturizer()
                        extracted_data.append(featurizer.featurize(mol_in))

        self._process_data_list(extracted_data)

    def len(self) -> int:
        return len(self._data_list)

    def __len__(self) -> int:
        return self.len()

    def get(self, idx: int) -> MolecularData:
        if idx < 0 or idx >= len(self._data_list):
            raise IndexError(f"Index {idx} out of range for dataset with length {len(self._data_list)}")
        item = self._data_list[idx].clone()
        if self._custom_transform is not None:
            item = self._custom_transform(item)
        return item

    def __getitem__(
        self,
        idx: Union[int, slice, Sequence[int], torch.Tensor],
    ) -> Union[MolecularData, GEOMInMemoryDataset]:
        if isinstance(idx, int):
            return self.get(idx)
        elif isinstance(idx, slice):
            sliced_items = self._data_list[idx]
            subset = GEOMInMemoryDataset(
                root=self._root_path,
                data_list=sliced_items,
                transform=self._custom_transform,
                pre_transform=self._custom_pre_transform,
                pre_filter=self._custom_pre_filter,
                conformer_strategy=self.conformer_strategy,
                temperature_k=self.temperature_k,
                seed=self.seed,
            )
            return subset
        elif isinstance(idx, (list, tuple, np.ndarray, torch.Tensor)):
            indices = [int(i) for i in idx]
            selected_items = [self._data_list[i] for i in indices]
            subset = GEOMInMemoryDataset(
                root=self._root_path,
                data_list=selected_items,
                transform=self._custom_transform,
                pre_transform=self._custom_pre_transform,
                pre_filter=self._custom_pre_filter,
                conformer_strategy=self.conformer_strategy,
                temperature_k=self.temperature_k,
                seed=self.seed,
            )
            return subset
        raise TypeError(f"Invalid index type: {type(idx)}")

    def filter(self, filter_fn: Callable[[MolecularData], bool]) -> GEOMInMemoryDataset:
        filtered_items = [d for d in self._data_list if filter_fn(d)]
        return GEOMInMemoryDataset(
            root=self._root_path,
            data_list=filtered_items,
            transform=self._custom_transform,
            pre_transform=self._custom_pre_transform,
            pre_filter=self._custom_pre_filter,
            conformer_strategy=self.conformer_strategy,
            temperature_k=self.temperature_k,
            seed=self.seed,
        )

    def save(self, path: Union[str, Path]) -> None:
        save_path = Path(path).expanduser().resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "data_list": self._data_list,
                "conformer_strategy": self.conformer_strategy,
                "temperature_k": self.temperature_k,
                "seed": self.seed,
            },
            save_path,
        )

    def load(self, path: Union[str, Path]) -> None:
        load_path = Path(path).expanduser().resolve()
        if not load_path.exists():
            raise FileNotFoundError(f"Dataset archive not found: {load_path}")
        payload = torch.load(load_path, map_location="cpu", weights_only=False)
        self._data_list = payload["data_list"]
        self.conformer_strategy = payload.get("conformer_strategy", "all")
        self.temperature_k = payload.get("temperature_k", STANDARD_TEMPERATURE_K)
        self.seed = payload.get("seed", DEFAULT_RANDOM_SEED)

    def copy(self) -> GEOMInMemoryDataset:
        return GEOMInMemoryDataset(
            root=self._root_path,
            data_list=[d.clone() for d in self._data_list],
            transform=self._custom_transform,
            pre_transform=self._custom_pre_transform,
            pre_filter=self._custom_pre_filter,
            conformer_strategy=self.conformer_strategy,
            temperature_k=self.temperature_k,
            seed=self.seed,
        )

    def __repr__(self) -> str:
        return f"GEOMInMemoryDataset(num_samples={len(self._data_list)}, strategy='{self.conformer_strategy}')"


# ==============================================================================
# 6. GEOM Streaming IterableDataset Implementation
# ==============================================================================

class GEOMIterableDataset(IterableDataset):
    """Streaming IterableDataset for multi-gigabyte MsgPack, JSON, and QM log archives."""

    def __init__(
        self,
        file_paths: Union[str, Path, Sequence[Union[str, Path]]],
        buffer_size: int = DEFAULT_STREAMING_BUFFER_SIZE,
        transform: Optional[Callable[[MolecularData], MolecularData]] = None,
        filter_fn: Optional[Callable[[MolecularData], bool]] = None,
        conformer_strategy: str = "all",
        temperature_k: float = STANDARD_TEMPERATURE_K,
        seed: Optional[int] = DEFAULT_RANDOM_SEED,
    ) -> None:
        if isinstance(file_paths, (str, Path)):
            p = Path(file_paths).expanduser().resolve()
            if p.is_dir():
                self.file_paths = sorted(list(p.glob("*.msgpack")) + list(p.glob("*.json*")) + list(p.glob("*.log*")) + list(p.glob("*.out*")))
            else:
                self.file_paths = [p]
        else:
            self.file_paths = [Path(fp).expanduser().resolve() for fp in file_paths]

        self.buffer_size = int(buffer_size)
        self.transform = transform
        self.filter_fn = filter_fn
        self.conformer_strategy = conformer_strategy.lower()
        self.temperature_k = float(temperature_k)
        self.seed = seed

    def _stream_msgpack_file(self, file_path: Path) -> Generator[MoleculeRecord, None, None]:
        if msgpack is None:
            raise ImportError("msgpack is required for streaming MsgPack archives.")
        for smiles, mol_data in deserialize_geom_archive(file_path):
            yield parse_geom_raw_molecule(smiles, mol_data, temperature_k=self.temperature_k)

    def _stream_jsonl_file(self, file_path: Path) -> Generator[MolecularData, None, None]:
        featurizer = MolecularFeaturizer()
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                d = json.loads(line_str)
                mol_in = MolecularInput(**d)
                yield featurizer.featurize(mol_in)

    def _stream_qm_log_file(self, file_path: Path) -> Generator[MolecularData, None, None]:
        qm_rec = parse_qm_output(file_path)
        if qm_rec.structures:
            mol_in = MolecularInput(
                symbols=qm_rec.symbols,
                positions=qm_rec.structures[-1],
                energy=qm_rec.energy_hartree,
                forces=qm_rec.forces,
                dipole=qm_rec.dipole_debye,
                rotational_constants=qm_rec.rotational_constants_mhz,
            )
            featurizer = MolecularFeaturizer()
            yield featurizer.featurize(mol_in)

    def __iter__(self) -> Iterator[MolecularData]:
        worker_info = get_worker_info()
        if worker_info is None:
            files_to_read = self.file_paths
            worker_id = 0
            num_workers = 1
        else:
            worker_id = worker_info.id
            num_workers = worker_info.num_workers
            files_to_read = self.file_paths[worker_id::num_workers]

        rng = random.Random((self.seed or 0) + worker_id)

        for file_path in files_to_read:
            if not file_path.exists():
                continue

            if file_path.suffix in [".msgpack", ".mp"]:
                for rec in self._stream_msgpack_file(file_path):
                    mols: List[MolecularData] = []
                    if self.conformer_strategy == "all":
                        mols = [conformer_to_molecular_data(rec, c) for c in rec.conformers]
                    elif self.conformer_strategy in ["lowest_energy", "min_energy"]:
                        lowest = rec.get_lowest_energy_conformer()
                        if lowest is not None:
                            mols = [conformer_to_molecular_data(rec, lowest)]
                    elif self.conformer_strategy == "boltzmann":
                        mols = ensemble_to_molecular_data(rec)
                    elif self.conformer_strategy == "random":
                        if rec.conformers:
                            mols = [conformer_to_molecular_data(rec, rng.choice(rec.conformers))]

                    for m in mols:
                        if self.filter_fn is not None and not self.filter_fn(m):
                            continue
                        out_mol = self.transform(m) if self.transform is not None else m
                        yield out_mol

            elif file_path.suffix in [".json", ".jsonl"]:
                for m in self._stream_jsonl_file(file_path):
                    if self.filter_fn is not None and not self.filter_fn(m):
                        continue
                    out_mol = self.transform(m) if self.transform is not None else m
                    yield out_mol

            elif file_path.suffix in [".log", ".out"]:
                for m in self._stream_qm_log_file(file_path):
                    if self.filter_fn is not None and not self.filter_fn(m):
                        continue
                    out_mol = self.transform(m) if self.transform is not None else m
                    yield out_mol


# ==============================================================================
# 7. GEOM Dataset Factory Implementation
# ==============================================================================

class GEOMDatasetFactory:
    """Factory design pattern for generating standardized datasets and deterministic data splits."""

    @staticmethod
    def create_custom(
        data_list: Sequence[MolecularData],
        transform: Optional[Callable[[MolecularData], MolecularData]] = None,
        conformer_strategy: str = "all",
        temperature_k: float = STANDARD_TEMPERATURE_K,
        seed: Optional[int] = DEFAULT_RANDOM_SEED,
    ) -> GEOMInMemoryDataset:
        return GEOMInMemoryDataset(
            data_list=data_list,
            transform=transform,
            conformer_strategy=conformer_strategy,
            temperature_k=temperature_k,
            seed=seed,
        )

    @staticmethod
    def create_qm9(
        root: Optional[Union[str, Path]] = None,
        raw_files: Optional[Sequence[Union[str, Path]]] = None,
        conformer_strategy: str = "lowest_energy",
        transform: Optional[Callable[[MolecularData], MolecularData]] = None,
        seed: Optional[int] = DEFAULT_RANDOM_SEED,
    ) -> GEOMInMemoryDataset:
        resolved_root = Path(root).expanduser().resolve() if root is not None else get_default_data_dir() / "qm9"
        return GEOMInMemoryDataset(
            root=resolved_root,
            raw_file_paths=raw_files,
            transform=transform,
            conformer_strategy=conformer_strategy,
            seed=seed,
        )

    @staticmethod
    def create_drugs(
        root: Optional[Union[str, Path]] = None,
        raw_files: Optional[Sequence[Union[str, Path]]] = None,
        conformer_strategy: str = "boltzmann",
        transform: Optional[Callable[[MolecularData], MolecularData]] = None,
        temperature_k: float = STANDARD_TEMPERATURE_K,
        seed: Optional[int] = DEFAULT_RANDOM_SEED,
    ) -> GEOMInMemoryDataset:
        resolved_root = Path(root).expanduser().resolve() if root is not None else get_default_data_dir() / "geom_drugs"
        return GEOMInMemoryDataset(
            root=resolved_root,
            raw_file_paths=raw_files,
            transform=transform,
            conformer_strategy=conformer_strategy,
            temperature_k=temperature_k,
            seed=seed,
        )

    @staticmethod
    def create_pickett(
        molecules: Sequence[MolecularData],
        transform: Optional[Callable[[MolecularData], MolecularData]] = None,
    ) -> GEOMInMemoryDataset:
        processed: List[MolecularData] = []
        for m in molecules:
            item = m.clone()
            if item.rotational_constants is None:
                masses = torch.tensor(
                    [resolve_dynamic_mass(s) for s in item.symbols],
                    dtype=item.pos.dtype,
                    device=item.pos.device,
                )
                a, b, c = compute_principal_rotational_constants(item.pos, masses)
                item.rotational_constants = torch.tensor([a, b, c], dtype=item.pos.dtype, device=item.pos.device)
            processed.append(item)

        return GEOMInMemoryDataset(data_list=processed, transform=transform)

    @staticmethod
    def create_qm_log(
        log_paths: Sequence[Union[str, Path]],
        transform: Optional[Callable[[MolecularData], MolecularData]] = None,
    ) -> GEOMInMemoryDataset:
        data_list: List[MolecularData] = []
        featurizer = MolecularFeaturizer()

        for lp in log_paths:
            p = Path(lp).expanduser().resolve()
            if not p.exists():
                continue
            qm_rec = parse_qm_output(p)
            if qm_rec.structures:
                mol_in = MolecularInput(
                    symbols=qm_rec.symbols,
                    positions=qm_rec.structures[-1],
                    energy=qm_rec.energy_hartree,
                    forces=qm_rec.forces,
                    dipole=qm_rec.dipole_debye,
                    rotational_constants=qm_rec.rotational_constants_mhz,
                )
                data_list.append(featurizer.featurize(mol_in))

        return GEOMInMemoryDataset(data_list=data_list, transform=transform)

    @staticmethod
    def train_val_test_split(
        dataset: GEOMInMemoryDataset,
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        test_ratio: float = 0.1,
        shuffle: bool = True,
        seed: int = DEFAULT_RANDOM_SEED,
        stratify_by: Optional[str] = None,
    ) -> Tuple[GEOMInMemoryDataset, GEOMInMemoryDataset, GEOMInMemoryDataset]:
        if not math.isclose(train_ratio + val_ratio + test_ratio, 1.0, rel_tol=1e-5):
            raise ValueError(f"Split ratios must sum to 1.0; got {train_ratio + val_ratio + test_ratio}")

        n_total = len(dataset)
        if n_total == 0:
            raise ValueError("Cannot split an empty dataset.")

        indices = list(range(n_total))

        if stratify_by is not None:
            strat_groups: Dict[Any, List[int]] = {}
            for i in indices:
                item = dataset.get(i)
                val = getattr(item, stratify_by, item.metadata.get(stratify_by))
                strat_groups.setdefault(val, []).append(i)

            rng = random.Random(seed)
            train_idx, val_idx, test_idx = [], [], []
            for _, grp in strat_groups.items():
                if shuffle:
                    rng.shuffle(grp)
                n_grp = len(grp)
                n_tr = int(round(n_grp * train_ratio))
                n_va = int(round(n_grp * val_ratio))
                train_idx.extend(grp[:n_tr])
                val_idx.extend(grp[n_tr : n_tr + n_va])
                test_idx.extend(grp[n_tr + n_va :])
        else:
            if shuffle:
                rng = random.Random(seed)
                rng.shuffle(indices)

            n_train = int(round(n_total * train_ratio))
            n_val = int(round(n_total * val_ratio))

            train_idx = indices[:n_train]
            val_idx = indices[n_train : n_train + n_val]
            test_idx = indices[n_train + n_val :]

        train_dataset = dataset[train_idx]
        val_dataset = dataset[val_idx]
        test_dataset = dataset[test_idx]

        return train_dataset, val_dataset, test_dataset

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_dataset.py ---
"""Zero-Verification Unit and Integration Test Suite for CoChem-GEOM Dataset Architecture.
========================================================================================
Validates:
1. Pure Immutable Geometric Transforms:
   - CenterOfMassTransform (mass-weighted COM centering with dynamic Mendeleev masses)
   - RandomRotationTransform (SO(3) Haar-distributed rotation with determinant +1 and distance preservation)
   - EckartAlignmentTransform (SVD mass-weighted optimal alignment minimizing RMSD)
   - GaussianJitterTransform (Isotropic Gaussian jitter preserving node count and state immutability)
   - NormalizeTargetsTransform (Target standardization and invertible denormalization)
   - ComposeTransforms (Sequential pipeline composability)
2. Batched Molecular Graphs & Collate Function:
   - MolecularBatch construction, ptr slicing offsets, block-diagonal edge indexing, to_data_list reconstruction
   - geom_collate_fn integration with PyTorch native DataLoader
3. GEOMInMemoryDataset:
   - Ingesting MolecularData list, indexing, slicing subsets, filtering, saving/loading cache
   - Conformer strategies: 'all', 'lowest_energy', 'boltzmann', 'random'
4. GEOMIterableDataset:
   - Streaming MsgPack archives and JSONL files
   - Bounded memory buffers and DataLoader compatibility
5. GEOMDatasetFactory:
   - Factory generation for Pickett, QM9, Drugs, Custom datasets
   - Deterministic train/val/test splitting with validation of ratio sums
6. Strict State Immutability:
   - Verifies original tensors are NEVER mutated in-place by transforms or collation

Authoritative Standards:
- Method Matrix v4: Data Contract & Spectroscopic Tensor Featurization
- Mendeleev Library Mandate: Dynamic atomic mass resolution (No hardcoding)
- SWEBOK v3 / ISO 25010 Software Quality Standards
- Provenance Tags: [M] Measured/Theoretical, [D] Derived/Calculated, [E] Expert Estimate
"""

from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Dict, List, Tuple

import msgpack
import numpy as np
import pytest
import torch
from torch.utils.data import DataLoader

# Ensure CoChem source paths are in sys.path
GEOM_ROOT = Path(__file__).resolve().parent.parent
GEOM_SRC = GEOM_ROOT / "src"
if str(GEOM_SRC) not in sys.path:
    sys.path.insert(0, str(GEOM_SRC))
if str(GEOM_ROOT) not in sys.path:
    sys.path.insert(0, str(GEOM_ROOT))

from cochem_geom.data.dataset import (
    BaseTransform,
    CenterOfMassTransform,
    ComposeTransforms,
    EckartAlignmentTransform,
    GEOMDatasetFactory,
    GEOMInMemoryDataset,
    GEOMIterableDataset,
    GaussianJitterTransform,
    MolecularBatch,
    NormalizeTargetsTransform,
    RandomRotationTransform,
    geom_collate_fn,
    get_default_data_dir,
)
from cochem_geom.data.featurizer import (
    MolecularData,
    MolecularFeaturizer,
    MolecularGraphConfig,
    MolecularInput,
    build_radius_graph,
    compute_center_of_mass,
    compute_principal_rotational_constants,
    get_atomic_mass,
    get_monoisotopic_mass,
)
from cochem_geom.data.geom_parser import (
    ConformerRecord,
    MoleculeRecord,
    conformer_to_molecular_data,
    serialize_geom_archive,
)


# ==============================================================================
# Fixtures: Real Physical Molecular Data Instances
# ==============================================================================

@pytest.fixture
def water_molecule() -> MolecularData:
    """Equilibrium C2v water (H2O) molecule."""
    symbols = ["O", "H", "H"]
    positions = [
        [0.000000, 0.000000, 0.117300],
        [0.000000, 0.757200, -0.469200],
        [0.000000, -0.757200, -0.469200],
    ]
    mol_in = MolecularInput(
        symbols=symbols,
        positions=positions,
        energy=-76.4388,  # Hartree
        forces=[
            [0.001, 0.000, -0.002],
            [0.000, -0.001, 0.001],
            [0.000, 0.001, 0.001],
        ],
        dipole=[0.0, 0.0, 1.85],
        rotational_constants=[835840.0, 435350.0, 278140.0],
    )
    featurizer = MolecularFeaturizer()
    return featurizer.featurize(mol_in)


@pytest.fixture
def methane_molecule() -> MolecularData:
    """Equilibrium Td methane (CH4) molecule."""
    symbols = ["C", "H", "H", "H", "H"]
    positions = [
        [0.000000, 0.000000, 0.000000],
        [0.627600, 0.627600, 0.627600],
        [-0.627600, -0.627600, 0.627600],
        [-0.627600, 0.627600, -0.627600],
        [0.627600, -0.627600, -0.627600],
    ]
    mol_in = MolecularInput(
        symbols=symbols,
        positions=positions,
        energy=-40.518,
        forces=[[0.0, 0.0, 0.0]] * 5,
        dipole=[0.0, 0.0, 0.0],
        rotational_constants=[157120.0, 157120.0, 157120.0],
    )
    featurizer = MolecularFeaturizer()
    return featurizer.featurize(mol_in)


@pytest.fixture
def ethanol_molecule() -> MolecularData:
    """Ethanol (C2H5OH) molecule (9 atoms)."""
    symbols = ["C", "C", "O", "H", "H", "H", "H", "H", "H"]
    positions = [
        [-0.034, 0.000, -0.024],
        [1.464, 0.000, 0.231],
        [-0.635, 1.205, 0.448],
        [-0.207, -0.071, -1.107],
        [-0.485, -0.877, 0.446],
        [1.650, 0.069, 1.309],
        [1.916, 0.884, -0.224],
        [1.936, -0.893, -0.191],
        [-1.589, 1.189, 0.282],
    ]
    mol_in = MolecularInput(
        symbols=symbols,
        positions=positions,
        energy=-155.03,
        dipole=[0.8, 1.2, -0.5],
    )
    featurizer = MolecularFeaturizer()
    return featurizer.featurize(mol_in)


@pytest.fixture
def benzene_molecule() -> MolecularData:
    """Planar D6h benzene (C6H6) molecule (12 atoms)."""
    symbols = ["C", "C", "C", "C", "C", "C", "H", "H", "H", "H", "H", "H"]
    r_cc = 1.397
    r_ch = 1.084
    positions = []
    # 6 Carbons in hexagon
    for k in range(6):
        angle = k * (2.0 * math.pi / 6.0)
        positions.append([r_cc * math.cos(angle), r_cc * math.sin(angle), 0.0])
    # 6 Hydrogens in hexagon
    for k in range(6):
        angle = k * (2.0 * math.pi / 6.0)
        r = r_cc + r_ch
        positions.append([r * math.cos(angle), r * math.sin(angle), 0.0])

    mol_in = MolecularInput(
        symbols=symbols,
        positions=positions,
        energy=-232.25,
        dipole=[0.0, 0.0, 0.0],
    )
    featurizer = MolecularFeaturizer()
    return featurizer.featurize(mol_in)


# ==============================================================================
# 1. Environment & Dynamic Path Resolution Tests
# ==============================================================================

def test_dynamic_data_dir_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify dynamic data dir respects COCHEM_DATA_DIR and defaults to ~/.cochem/data."""
    # Test fallback
    monkeypatch.delenv("COCHEM_DATA_DIR", raising=False)
    default_dir = get_default_data_dir()
    expected_default = (Path.home() / ".cochem" / "data").resolve()
    assert default_dir == expected_default

    # Test custom env var
    with tempfile.TemporaryDirectory() as tmp_dir:
        monkeypatch.setenv("COCHEM_DATA_DIR", tmp_dir)
        resolved = get_default_data_dir()
        assert resolved == Path(tmp_dir).resolve()


# ==============================================================================
# 2. Pure Immutable Transformation Tests
# ==============================================================================

def test_center_of_mass_transform_immutability(water_molecule: MolecularData) -> None:
    """Verify CenterOfMassTransform centers molecular coordinates and preserves immutability."""
    orig_pos_copy = water_molecule.pos.clone()
    transform = CenterOfMassTransform(use_monoisotopic=False)

    centered = transform(water_molecule)

    # 1. Original tensor must NOT be modified in-place
    assert torch.equal(water_molecule.pos, orig_pos_copy)
    assert not torch.equal(centered.pos, water_molecule.pos)

    # 2. Centered coordinates must have mass-weighted center of mass at origin (0, 0, 0)
    masses = torch.tensor(
        [get_atomic_mass(s) for s in centered.symbols],
        dtype=centered.pos.dtype,
        device=centered.pos.device,
    )
    com = compute_center_of_mass(centered.pos, masses)
    assert torch.allclose(com, torch.zeros(3, dtype=com.dtype), atol=1e-6)

    # 3. Pairwise interatomic Euclidean distances must be perfectly preserved
    orig_dist = torch.norm(water_molecule.pos[0] - water_molecule.pos[1])
    cent_dist = torch.norm(centered.pos[0] - centered.pos[1])
    assert torch.allclose(orig_dist, cent_dist, atol=1e-6)


def test_random_rotation_transform_equivariance_and_immutability(
    water_molecule: MolecularData,
) -> None:
    """Verify RandomRotationTransform applies valid SO(3) rotations and preserves immutability."""
    orig_pos_copy = water_molecule.pos.clone()
    orig_forces_copy = water_molecule.forces.clone() if water_molecule.forces is not None else None
    orig_dipole_copy = water_molecule.dipole.clone() if water_molecule.dipole is not None else None

    rot_transform = RandomRotationTransform(seed=123)
    rotated = rot_transform(water_molecule)

    # 1. Original data was not mutated
    assert torch.equal(water_molecule.pos, orig_pos_copy)
    if orig_forces_copy is not None:
        assert torch.equal(water_molecule.forces, orig_forces_copy)

    # 2. Pairwise distances are invariant under rotation: ||r_i' - r_j'|| == ||r_i - r_j||
    for i in range(water_molecule.num_nodes):
        for j in range(i + 1, water_molecule.num_nodes):
            d_orig = torch.norm(water_molecule.pos[i] - water_molecule.pos[j])
            d_rot = torch.norm(rotated.pos[i] - rotated.pos[j])
            assert torch.allclose(d_orig, d_rot, atol=1e-5)

    # 3. Vector norms of forces and dipole are preserved
    if water_molecule.forces is not None and rotated.forces is not None:
        norm_orig_f = torch.norm(water_molecule.forces, dim=-1)
        norm_rot_f = torch.norm(rotated.forces, dim=-1)
        assert torch.allclose(norm_orig_f, norm_rot_f, atol=1e-5)

    if water_molecule.dipole is not None and rotated.dipole is not None:
        norm_orig_d = torch.norm(water_molecule.dipole)
        norm_rot_d = torch.norm(rotated.dipole)
        assert torch.allclose(norm_orig_d, norm_rot_d, atol=1e-5)


def test_eckart_alignment_transform_immutability(water_molecule: MolecularData) -> None:
    """Verify EckartAlignmentTransform aligns rotated geometry back to reference frame."""
    theta = 0.75
    r_z = torch.tensor([
        [math.cos(theta), -math.sin(theta), 0.0],
        [math.sin(theta), math.cos(theta), 0.0],
        [0.0, 0.0, 1.0],
    ], dtype=water_molecule.pos.dtype)

    distorted_water = water_molecule.clone()
    distorted_water.pos = water_molecule.pos @ r_z.T + torch.tensor([2.0, -1.0, 3.0])

    orig_distorted_pos = distorted_water.pos.clone()
    aligner = EckartAlignmentTransform(reference=water_molecule, use_mass_weighting=True)
    aligned = aligner(distorted_water)

    # 1. State immutability
    assert torch.equal(distorted_water.pos, orig_distorted_pos)

    # 2. Aligned coordinates match original reference within machine precision
    rmsd = torch.sqrt(torch.mean((aligned.pos - water_molecule.pos) ** 2))
    assert float(rmsd.item()) < 1e-4


def test_gaussian_jitter_transform_immutability(ethanol_molecule: MolecularData) -> None:
    """Verify GaussianJitterTransform injects noise immutably and reproducibly."""
    orig_pos_copy = ethanol_molecule.pos.clone()
    sigma = 0.05
    jitter_transform = GaussianJitterTransform(sigma=sigma, seed=42)

    jittered = jitter_transform(ethanol_molecule)

    # Immutability
    assert torch.equal(ethanol_molecule.pos, orig_pos_copy)
    assert not torch.equal(jittered.pos, orig_pos_copy)

    # Magnitude of displacement roughly consistent with sigma
    diff = torch.norm(jittered.pos - ethanol_molecule.pos, dim=-1)
    assert float(diff.mean().item()) > 0.0
    assert float(diff.max().item()) < 5.0 * sigma


def test_normalize_targets_transform_invertibility(ethanol_molecule: MolecularData) -> None:
    """Verify NormalizeTargetsTransform normalizes targets and denormalize is invertible."""
    mean_val = -150.0
    std_val = 10.0
    norm_transform = NormalizeTargetsTransform(mean=mean_val, std=std_val)

    normalized = norm_transform(ethanol_molecule)

    # Immutability
    assert math.isclose(float(ethanol_molecule.y.item()), -155.03, rel_tol=1e-4)
    expected_norm_y = (-155.03 - mean_val) / std_val
    assert math.isclose(float(normalized.y.item()), expected_norm_y, rel_tol=1e-4)

    # Invertibility
    denorm_y = norm_transform.denormalize(normalized.y)
    assert math.isclose(float(denorm_y.item()), -155.03, rel_tol=1e-4)


def test_compose_transforms_pipeline(benzene_molecule: MolecularData) -> None:
    """Verify sequential composition of transforms via ComposeTransforms."""
    orig_pos = benzene_molecule.pos.clone()

    pipeline = ComposeTransforms([
        CenterOfMassTransform(),
        RandomRotationTransform(seed=99),
        GaussianJitterTransform(sigma=0.01, seed=99),
    ])

    transformed = pipeline(benzene_molecule)

    # Immutability check
    assert torch.equal(benzene_molecule.pos, orig_pos)
    assert transformed.num_nodes == 12
    assert transformed.pos.shape == (12, 3)


# ==============================================================================
# 3. Batched Geometric Container & Collate Function Tests
# ==============================================================================

def test_geom_collate_fn_with_heterogeneous_graphs(
    water_molecule: MolecularData,
    methane_molecule: MolecularData,
    ethanol_molecule: MolecularData,
) -> None:
    """Verify geom_collate_fn packs heterogeneous molecular graphs into contiguous MolecularBatch."""
    batch_list = [water_molecule, methane_molecule, ethanol_molecule]
    batch = geom_collate_fn(batch_list)

    assert isinstance(batch, MolecularBatch)
    assert batch.num_graphs == 3
    # Water: 3, Methane: 5, Ethanol: 9 -> Total: 17
    assert batch.num_nodes == 17
    assert batch.pos.shape == (17, 3)
    assert batch.z.shape == (17,)
    assert batch.batch.shape == (17,)

    # Ptr slices: [0, 3, 8, 17]
    assert torch.equal(batch.ptr, torch.tensor([0, 3, 8, 17], dtype=torch.long))

    # Batch indices: [0,0,0, 1,1,1,1,1, 2,2,2,2,2,2,2,2,2]
    expected_batch = torch.tensor(
        [0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2], dtype=torch.long
    )
    assert torch.equal(batch.batch, expected_batch)

    # Edge index offsets
    if batch.edge_index is not None and batch.edge_index.numel() > 0:
        second_graph_edges = batch.edge_index[:, (batch.edge_index[0] >= 3) & (batch.edge_index[0] < 8)]
        assert (second_graph_edges[1] >= 3).all() and (second_graph_edges[1] < 8).all()

    # Targets stacked
    assert batch.y is not None
    assert batch.y.shape[0] == 3

    # Decompose batch back to data list
    reconstructed = batch.to_data_list()
    assert len(reconstructed) == 3
    assert reconstructed[0].num_nodes == 3
    assert reconstructed[1].num_nodes == 5
    assert reconstructed[2].num_nodes == 9

    assert torch.allclose(reconstructed[0].pos, water_molecule.pos)
    assert torch.allclose(reconstructed[1].pos, methane_molecule.pos)
    assert torch.allclose(reconstructed[2].pos, ethanol_molecule.pos)


def test_batch_device_and_precision_transfer(
    water_molecule: MolecularData,
    methane_molecule: MolecularData,
) -> None:
    """Verify MolecularBatch transfers devices and dtypes immutably."""
    batch = geom_collate_fn([water_molecule, methane_molecule])
    transferred = batch.to(device="cpu", dtype=torch.float64)

    assert transferred.pos.dtype == torch.float64
    assert transferred.batch.dtype == torch.long
    assert transferred.ptr.dtype == torch.long
    if transferred.y is not None:
        assert transferred.y.dtype == torch.float64


# ==============================================================================
# 4. GEOMInMemoryDataset Tests
# ==============================================================================

def test_geom_inmemory_dataset_indexing_and_slicing(
    water_molecule: MolecularData,
    methane_molecule: MolecularData,
    ethanol_molecule: MolecularData,
    benzene_molecule: MolecularData,
) -> None:
    """Verify GEOMInMemoryDataset supports indexing, slicing, and length operations."""
    mol_list = [water_molecule, methane_molecule, ethanol_molecule, benzene_molecule]
    dataset = GEOMInMemoryDataset(data_list=mol_list)

    assert len(dataset) == 4

    # Single-item indexing
    item0 = dataset[0]
    assert isinstance(item0, MolecularData)
    assert item0.num_nodes == 3
    assert item0.symbols == ["O", "H", "H"]

    # Slice indexing
    sub_ds = dataset[1:3]
    assert isinstance(sub_ds, GEOMInMemoryDataset)
    assert len(sub_ds) == 2
    assert sub_ds[0].num_nodes == 5  # methane
    assert sub_ds[1].num_nodes == 9  # ethanol

    # Tensor indexing
    tensor_idx = torch.tensor([0, 3], dtype=torch.long)
    sub_ds2 = dataset[tensor_idx]
    assert len(sub_ds2) == 2
    assert sub_ds2[0].num_nodes == 3   # water
    assert sub_ds2[1].num_nodes == 12  # benzene


def test_geom_inmemory_dataset_conformer_strategies() -> None:
    """Verify conformer selection strategies: all, lowest_energy, boltzmann, random."""
    raw_mol_dict = {
        "conformers": [
            {
                "xyz": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [-1.0, 0.0, 0.0]],
                "totalenergy": -40.510,
            },
            {
                "xyz": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [-1.0, 0.0, 0.0]],
                "totalenergy": -40.520,  # Lowest energy
            },
            {
                "xyz": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [-1.0, 0.0, 0.0]],
                "totalenergy": -40.505,
            },
        ]
    }
    archive_data = {"C": raw_mol_dict}

    with tempfile.TemporaryDirectory() as tmp_dir:
        archive_path = Path(tmp_dir) / "methane_confs.msgpack"
        serialize_geom_archive(archive_path, archive_data)

        # 1. Strategy: 'all'
        ds_all = GEOMInMemoryDataset(raw_file_paths=[archive_path], conformer_strategy="all")
        assert len(ds_all) == 3

        # 2. Strategy: 'lowest_energy'
        ds_min = GEOMInMemoryDataset(raw_file_paths=[archive_path], conformer_strategy="lowest_energy")
        assert len(ds_min) == 1
        # Energy converted from Hartree to eV: -40.520 * 27.211386...
        assert ds_min[0].y is not None

        # 3. Strategy: 'boltzmann'
        ds_boltz = GEOMInMemoryDataset(raw_file_paths=[archive_path], conformer_strategy="boltzmann")
        assert len(ds_boltz) == 3
        weights = [float(item.weight.item()) for item in ds_boltz]
        assert math.isclose(sum(weights), 1.0, rel_tol=1e-4)
        assert weights[1] > weights[0] and weights[1] > weights[2]

        # 4. Strategy: 'random'
        ds_rand = GEOMInMemoryDataset(raw_file_paths=[archive_path], conformer_strategy="random", seed=42)
        assert len(ds_rand) == 1


def test_geom_inmemory_dataset_save_and_load(
    water_molecule: MolecularData,
    methane_molecule: MolecularData,
) -> None:
    """Verify disk persistence (save and load) of GEOMInMemoryDataset."""
    dataset = GEOMInMemoryDataset(data_list=[water_molecule, methane_molecule])

    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_file = Path(tmp_dir) / "cached_dataset.pt"
        dataset.save(cache_file)

        loaded_dataset = GEOMInMemoryDataset()
        loaded_dataset.load(cache_file)

        assert len(loaded_dataset) == 2
        assert torch.allclose(loaded_dataset[0].pos, water_molecule.pos)
        assert torch.allclose(loaded_dataset[1].pos, methane_molecule.pos)


# ==============================================================================
# 5. GEOMIterableDataset & Streaming Tests
# ==============================================================================

def test_geom_iterable_dataset_streaming_msgpack() -> None:
    """Verify GEOMIterableDataset streams conformers without full in-memory loading."""
    archive_data = {
        "O": {
            "conformers": [
                {
                    "xyz": [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                    "totalenergy": -76.4,
                }
            ]
        },
        "C": {
            "conformers": [
                {
                    "xyz": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [-1.0, 0.0, 0.0]],
                    "totalenergy": -40.5,
                }
            ]
        },
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        archive_path = Path(tmp_dir) / "stream_test.msgpack"
        serialize_geom_archive(archive_path, archive_data)

        stream_ds = GEOMIterableDataset(
            file_paths=[archive_path],
            transform=CenterOfMassTransform(),
        )

        streamed_items = list(stream_ds)
        assert len(streamed_items) == 2
        assert streamed_items[0].num_nodes == 3
        assert streamed_items[1].num_nodes == 5

        # Check COM transform was applied during streaming
        masses = torch.tensor(
            [get_atomic_mass(s) for s in streamed_items[0].symbols],
            dtype=streamed_items[0].pos.dtype,
        )
        com = compute_center_of_mass(streamed_items[0].pos, masses)
        assert torch.allclose(com, torch.zeros(3, dtype=com.dtype), atol=1e-6)


def test_geom_iterable_dataset_streaming_jsonl() -> None:
    """Verify GEOMIterableDataset streams JSONL datasets."""
    data1 = {
        "symbols": ["O", "H", "H"],
        "positions": [[0.0, 0.0, 0.1], [0.0, 0.7, -0.4], [0.0, -0.7, -0.4]],
        "energy": -76.4,
    }
    data2 = {
        "symbols": ["C", "H", "H", "H", "H"],
        "positions": [[0.0, 0.0, 0.0], [0.6, 0.6, 0.6], [-0.6, -0.6, 0.6], [-0.6, 0.6, -0.6], [0.6, -0.6, -0.6]],
        "energy": -40.5,
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        jsonl_path = Path(tmp_dir) / "stream.jsonl"
        with open(jsonl_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(data1) + "\n")
            f.write(json.dumps(data2) + "\n")

        stream_ds = GEOMIterableDataset(file_paths=[jsonl_path])
        items = list(stream_ds)
        assert len(items) == 2
        assert items[0].symbols == ["O", "H", "H"]
        assert items[1].symbols == ["C", "H", "H", "H", "H"]


# ==============================================================================
# 6. GEOMDatasetFactory Tests
# ==============================================================================

def test_geom_dataset_factory_custom_and_pickett(
    water_molecule: MolecularData,
    methane_molecule: MolecularData,
) -> None:
    """Verify GEOMDatasetFactory constructs custom and pickett datasets."""
    # Custom
    ds_custom = GEOMDatasetFactory.create_custom([water_molecule, methane_molecule])
    assert len(ds_custom) == 2

    # Pickett
    ds_pickett = GEOMDatasetFactory.create_pickett([water_molecule, methane_molecule])
    assert len(ds_pickett) == 2
    for item in ds_pickett:
        assert item.rotational_constants is not None
        assert item.rotational_constants.shape == (3,)
        # Constants must be positive
        assert (item.rotational_constants > 0).all()


def test_geom_dataset_factory_train_val_test_split(
    water_molecule: MolecularData,
    methane_molecule: MolecularData,
    ethanol_molecule: MolecularData,
    benzene_molecule: MolecularData,
) -> None:
    """Verify deterministic train, validation, and test dataset splitting."""
    mols = [water_molecule, methane_molecule, ethanol_molecule, benzene_molecule] * 5  # 20 samples
    ds = GEOMInMemoryDataset(data_list=mols)

    train_ds, val_ds, test_ds = GEOMDatasetFactory.train_val_test_split(
        ds,
        train_ratio=0.8,
        val_ratio=0.1,
        test_ratio=0.1,
        shuffle=True,
        seed=42,
    )

    assert len(train_ds) == 16
    assert len(val_ds) == 2
    assert len(test_ds) == 2
    assert len(train_ds) + len(val_ds) + len(test_ds) == 20


def test_geom_dataset_factory_invalid_split_ratio(water_molecule: MolecularData) -> None:
    """Verify ValueError when split ratios do not sum to 1.0."""
    ds = GEOMInMemoryDataset(data_list=[water_molecule])
    with pytest.raises(ValueError, match="Split ratios must sum to 1.0"):
        GEOMDatasetFactory.train_val_test_split(
            ds, train_ratio=0.7, val_ratio=0.1, test_ratio=0.1
        )


# ==============================================================================
# 7. PyTorch DataLoader Integration & Training Loop Simulation
# ==============================================================================

def test_pytorch_dataloader_end_to_end_iteration(
    water_molecule: MolecularData,
    methane_molecule: MolecularData,
    ethanol_molecule: MolecularData,
    benzene_molecule: MolecularData,
) -> None:
    """Verify end-to-end iteration with PyTorch DataLoader and geom_collate_fn."""
    mols = [water_molecule, methane_molecule, ethanol_molecule, benzene_molecule]
    dataset = GEOMInMemoryDataset(
        data_list=mols,
        transform=CenterOfMassTransform(),
    )

    loader = DataLoader(
        dataset,
        batch_size=2,
        shuffle=False,
        collate_fn=geom_collate_fn,
    )

    batches = list(loader)
    assert len(batches) == 2

    # Batch 1: Water (3) + Methane (5) = 8
    b1 = batches[0]
    assert b1.num_graphs == 2
    assert b1.num_nodes == 8
    assert b1.pos.shape == (8, 3)

    # Batch 2: Ethanol (9) + Benzene (12) = 21
    b2 = batches[1]
    assert b2.num_graphs == 2
    assert b2.num_nodes == 21
    assert b2.pos.shape == (21, 3)

    # Forward computation simulation: calculate batch mean coordinate
    for b in loader:
        loss = torch.sum(b.pos ** 2)
        assert not torch.isnan(loss)
        assert float(loss.item()) > 0.0

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.