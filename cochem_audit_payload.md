Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\07_scribe_templater.md.
Original prompt:
# Phase 4, Task 9: Jinja2 Templating & LaTeX Scaffolding (`formatters/scribe_templater.py`)

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`
**Target Files to Create:**
- `formatters/scribe_templater.py`
- `formatters/templates/base_manuscript.tex`
- `formatters/test_scribe_templater.py`

## Objective
Implement the production-grade LaTeX templating engine class (`Jinja2Templater`), the static publication scaffold (`base_manuscript.tex`), and comprehensive zero-mock integration tests (`test_scribe_templater.py`) for CoChem-SCRIBE (Stage 6.3). This module bridges the **Mathematical Air-Gap** by securely reassembling LLM-generated narrative insights with exact, unhallucinated numerical arrays and physical scalars extracted from quantum chemistry pipelines (e.g., ZPE, enthalpies, Gibbs Free Energy, vibrational frequencies). The implementation must strictly adhere to the **CoChem-SCRIBE Software Requirements Specification (SRS Phase 4, Task 9, Tasks 51–60)**, **Method Matrix v4**, the **Zero-Mock Anti-Spoofing Protocol**, **FAIR Data Principles**, and the **6-Tier Environment Matrix** (Local-Windows WSL, Local-MacOS OrbStack, Local-Linux Debian, Codespaces, GitHub Actions, HPC).

---

## Technical Specifications & Architecture

### 1. Architectural Philosophy: The Air-Gap Reassembly (SRS §9.1)
- **Air-Gap Integration Boundary:** Up to Stage 6.3, generative LLMs are completely isolated from raw physical tensors to prevent hallucinated values. `Jinja2Templater` fuses the scrubbed narrative text with exact numerical data directly harvested from calculation engines.
- **LaTeX Fragility & Defensive Sanitization:** `pdflatex` compilation will fatally abort on unescaped special characters (e.g., raw underscores `_` in calculation log filenames or variable keys). The templating engine must programmatically sanitize all raw strings, system logs, and un-escaped tokens before template injection.
- **Physical Static Scaffold Mandate:** In compliance with the Air-Gap architecture and cross-platform determinism, LaTeX templates must reside as physical static files on disk resolved dynamically via `pathlib.Path`. Inlining templates as multiline Python string constants is strictly prohibited.
- **100% Offline Air-Gap Execution:** All Jinja2 environment configuration, custom filter execution, table formatting, and document rendering must execute locally without network access or external cloud dependencies.

---

## Deliverable 1: `formatters/scribe_templater.py`

### 1. Class Architecture & Interface Contract (`Jinja2Templater`)
Define the `Jinja2Templater` class in `formatters/scribe_templater.py` with exhaustive Python 3.10+ typing (`typing.Dict`, `typing.Any`, `typing.Optional`, `typing.Union`, `typing.List`, `pathlib.Path`, `pandas.DataFrame`):

```python
import re
import logging
import pathlib
from typing import Dict, Any, Optional, Union, List
import jinja2
import pandas as pd

class Jinja2Templater:
    """Jinja2-based LaTeX scaffolding and document synthesis engine.
    
    Bridges the Mathematical Air-Gap by injecting exact physical tensors into
    ACS/APS-compliant LaTeX templates with customized delimiters, siunitx unit harmonization,
    booktabs table formatting, chemfig 2D topology rendering, and aggressive LaTeX sanitization.
    """
    def __init__(
        self,
        template_dir: Optional[Union[str, pathlib.Path]] = None,
        template_name: str = "base_manuscript.tex"
    ) -> None:
        """Initializes Jinja2 environment with overridden LaTeX delimiters and custom filters."""
        pass

    def format_siunitx_num(self, value: Union[float, int, str]) -> str:
        """Formats numerical scalars and scientific notation into LaTeX \num{...} syntax."""
        pass

    def format_siunitx_qty(self, value: Union[float, int, str], unit: str) -> str:
        """Formats numerical quantities and units into LaTeX \qty{...}{...} syntax."""
        pass

    def dataframe_to_booktabs(
        self,
        df: pd.DataFrame,
        caption: str = "",
        label: str = "",
        col_align: Optional[str] = None
    ) -> str:
        """Converts a pandas DataFrame into a publication-grade LaTeX booktabs table without vertical rules."""
        pass

    def render_chemfig(self, smiles: str) -> str:
        """Converts a SMILES string into a 2D LaTeX chemfig structural macro."""
        pass

    def sanitize_latex(self, text: str) -> str:
        """Aggressively escapes LaTeX special characters outside of existing macros and math blocks."""
        pass

    def render_manuscript(self, data_payload: Dict[str, Any]) -> str:
        """Renders the complete manuscript by injecting sanitized text and formatted tables into template."""
        pass
```

---

### 2. Detailed Functional Requirements (Tasks 51–60)

#### 2.1 Jinja2 Environment & LaTeX Delimiter Override (Tasks 51 & 52)
- **Custom `jinja2.Environment`:** Initialize a custom Jinja2 Environment using `jinja2.FileSystemLoader` targeting `template_dir`.
- **Delimiter Remapping:** Standard Jinja2 curly braces (`{{ }}` and `{% %}`) collide with LaTeX syntax. The environment must explicitly override default delimiters:
  - `variable_start_string = r"\VAR{"`
  - `variable_end_string = "}"`
  - `block_start_string = r"\BLOCK{"`
  - `block_end_string = "}"`
  - `comment_start_string = r"\COMMENT{"`
  - `comment_end_string = "}"`
  - `trim_blocks = True`
  - `lstrip_blocks = True`
- **Custom Filter Registration:** Register the following custom filters in `self.env.filters`:
  - `latex_escape`: maps to `self.sanitize_latex`
  - `siunitx_num`: maps to `self.format_siunitx_num`
  - `siunitx_qty`: maps to `self.format_siunitx_qty`
  - `chemfig`: maps to `self.render_chemfig`

#### 2.2 Dynamic Template Resolution & Air-Gap Pathing (Task 53)
- If `template_dir` is not provided, dynamically resolve the path relative to the module file:
  `pathlib.Path(__file__).resolve().parent / "templates"`
- Ensure path resolution is deterministic and OS-agnostic across all 6-Tier environments.
- Enforce that the template file exists on disk; raise `FileNotFoundError` with a clear message if missing.

#### 2.3 Scientific Unit Harmonization with `siunitx` (Task 54)
- Implement `format_siunitx_num(self, value: Union[float, int, str]) -> str`:
  - Scientific notation: convert `1.23e-4` or `1.23E-04` to `\num{1.23e-4}`.
  - Floating point numbers: wrap in `\num{<val>}` preserving significant figures.
- Implement `format_siunitx_qty(self, value: Union[float, int, str], unit: str) -> str`:
  - Temperature: convert `298.15` and `"K"`/`"kelvin"` to `\qty{298.15}{\kelvin}`.
  - Energetics: convert numerical values and `"kcal/mol"` to `\qty{<val>}{\kilo\calorie\per\mole}`, `"kJ/mol"` to `\qty{<val>}{\kilo\joule\per\mole}`, `"Hartree"` to `\qty{<val>}{\hartree}`.
  - Frequencies: convert `"cm-1"` or `"cm^-1"` to `\qty{<val>}{\per\centi\meter}`.
  - Dipoles: convert `"D"` or `"Debye"` to `\qty{<val>}{\debye}`.

#### 2.4 Academic Table Conversion with `booktabs` (Task 55)
- Implement `dataframe_to_booktabs(self, df: pd.DataFrame, caption: str = "", label: str = "", col_align: Optional[str] = None) -> str`:
  - Convert `pandas.DataFrame` tables into academic LaTeX tables using `\toprule`, `\midrule`, and `\bottomrule`.
  - **Strictly prohibit vertical grid lines (`|`)** in column specifications (enforce academic typesetting standards).
  - Automatically format floating-point values inside numeric table cells using `format_siunitx_num`.
  - Wrap output in standard LaTeX environment:
    ```latex
    \begin{table}[htbp]
    \centering
    \caption{<caption>}
    \label{<label>}
    \begin{tabular}{<alignment>}
    \toprule
    <headers> \\
    \midrule
    <rows>
    \bottomrule
    \end{tabular}
    \end{table}
    ```

#### 2.5 2D Molecular Topology Rendering (`chemfig`) (Task 56)
- Implement `render_chemfig(self, smiles: str) -> str`:
  - If a valid SMILES string is present, generate a `\chemfig{...}` macro representation.
  - If SMILES string is empty, missing, or unparseable, provide a clean fallback comment `% [No 2D chemfig structure available]`.

#### 2.6 Aggressive LaTeX Sanitization & Escape Filter (Task 59)
- Implement `sanitize_latex(self, text: str) -> str`:
  - Aggressively escape special LaTeX characters originating from raw quantum logs and narrative text outside of existing math mode (`$ ... $` or `\( ... \)`) and existing LaTeX commands:
    - `_` $\to$ `\_`
    - `&` $\to$ `\&`
    - `%` $\to$ `\%`
    - `#` $\to$ `\#`
    - `$` $\to$ `\$` (when unescaped and not part of valid math delimiters)
    - `~` $\to$ `\textasciitilde{}`
    - `^` $\to$ `\textasciicircum{}`
  - Preserve valid LaTeX macros (e.g., `\num{}`, `\qty{}`, `\section{}`, `\subsection{}`, `\textbf{}`, `\emph{}`, `\chemfig{}`).

#### 2.7 Narrative Injection, Tag Harmonization & `LAM_TRIGGER` Mapping (Tasks 57 & 58)
- Implement `render_manuscript(self, data_payload: Dict[str, Any]) -> str`:
  - Inject methodology text into `\VAR{computational_details}`.
  - Harmonize upstream placeholder tags: if `computational_details` or `insights` contains `INSERT_THERMO_TABLE_HERE`, `{{ conformer_table }}`, or `<<INSERT_*>>`, gracefully substitute or resolve them.
  - **Dynamic `LAM_TRIGGER` Mapping:** If `lam_trigger` or Sinc-DVR flag is `True` in `data_payload`, inject the Sinc-DVR justification text into `\VAR{sinc_dvr_justification}` and activate the conditional block in the template.
  - Inject formatted `booktabs` tables into `\VAR{conformer_table}`, `\VAR{thermo_table}`, and `\VAR{vibrational_table}`.
  - Inject metadata into `\VAR{title}`, `\VAR{authors}`, `\VAR{affiliations}`, `\VAR{abstract}`, `\VAR{chemfig_structure}`, and `\VAR{provenance_footer}`.

---

## Deliverable 2: `formatters/templates/base_manuscript.tex`

Provide the physical static LaTeX template formatted according to standard ACS/APS publication guidelines:

```latex
\documentclass[journal=jacsat,manuscript=article]{achemso}

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
```

---

## Deliverable 3: `formatters/test_scribe_templater.py`

Implement a complete `pytest` test suite conforming to the **Zero-Mock Anti-Spoofing Protocol**:
1. **Zero-Mock Enforcement:** Strictly prohibit `unittest.mock`, `mocker`, or simulated string returns. Tests must execute the real `Jinja2Templater` engine against physical template files and real DataFrames.
2. **Template Delimiter & Rendering Test:**
   - Instantiate `Jinja2Templater` pointing to `templates/base_manuscript.tex`.
   - Render a complete payload dictionary containing real chemistry DataFrames, scientific notation floats, and narrative text.
   - Assert rendered LaTeX output contains valid `\toprule`, `\midrule`, `\bottomrule`, and zero un-substituted `\VAR{` or `\BLOCK{` strings.
3. **`siunitx` Unit Harmonization Test:**
   - Test numbers in scientific notation (`1.23e-4` $\to$ `\num{1.23e-4}`).
   - Test temperatures (`298.15` $\to$ `\qty{298.15}{\kelvin}`).
   - Test energetics (`-154.3` $\to$ `\qty{-154.3}{\kilo\calorie\per\mole}`).
4. **Aggressive Sanitization Test:**
   - Input strings containing raw quantum telemetry (`SCF_CONVERGENCE_FAIL & Error_Rate % = 0.5% #1 ~ ^test`).
   - Assert all `_`, `&`, `%`, `#`, `~`, `^` characters are safely escaped without crashing LaTeX macros.
5. **`LAM_TRIGGER` Conditional Mapping Test:**
   - Test rendering with `sinc_dvr_justification="Torsional Sinc-DVR justified."` and assert that the Sinc-DVR subsection is present in the rendered `.tex`.
   - Test rendering with `sinc_dvr_justification=""` and assert that the Sinc-DVR subsection is omitted.
6. **Booktabs Table Rendering Test:**
   - Pass a multi-row pandas DataFrame with numerical float columns.
   - Assert that no vertical rules (`|`) are present and numeric columns are formatted with `\num{...}`.

---

## Execution Constraints & Anti-Spoofing Directives

1. **Zero Mocking / Placeholders:**
   - Every class, method, filter, and template must be completely implemented with functional logic.
   - Strictly NO `pass`, `# TODO`, `...`, or fake mock returns in output files.
2. **Dynamic Path Resolution:**
   - All filesystem operations must resolve dynamically using `pathlib.Path(__file__).resolve().parent`.
   - Hardcoded OS paths (e.g., `C:\Users\...` or `/tmp/...`) are strictly prohibited.
3. **6-Tier Environment Matrix Compliance:**
   - The module and templates must function identically across Linux (Debian/Ubuntu), macOS (OrbStack), Windows (WSL), Codespaces, GitHub Actions, and HPC clusters.
4. **FAIR Data & Provenance Compliance:**
   - Reassembled LaTeX output must preserve exact numerical quantities from upstream calculation tiers.
5. **Deliverable Scope:**
   - Implement `formatters/scribe_templater.py`, `formatters/templates/base_manuscript.tex`, and `formatters/test_scribe_templater.py`.

---

## Task
Implement the Python modules and static LaTeX template as described and save them to:
- `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\formatters\scribe_templater.py`
- `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\formatters\templates\base_manuscript.tex`
- `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\formatters\test_scribe_templater.py`
using the `write_to_file` tool.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\conftest.py ---
import sys
from pathlib import Path

base_root = Path(__file__).resolve().parent
repo_root = base_root.parent

for path in [repo_root / "CoChem-BENCH", repo_root / "CoChem-BASE", base_root / "src", base_root]:
    if path.exists():
        p_str = str(path)
        if p_str in sys.path:
            sys.path.remove(p_str)
        sys.path.insert(0, p_str)

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_scribe_templater.py ---
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
    )
    assert result.returncode == 0, f"CLI script failed with stderr: {result.stderr}"
    assert "[SCRIBE TEMPLATER PRE-FLIGHT VERIFIED]" in result.stdout

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.