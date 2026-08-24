Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\prompt_scribe_templater.md.
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
        ...

    def format_siunitx_num(self, value: Union[float, int, str]) -> str:
        """Formats numerical scalars and scientific notation into LaTeX \num{...} syntax."""
        ...

    def format_siunitx_qty(self, value: Union[float, int, str], unit: str) -> str:
        """Formats numerical quantities and units into LaTeX \qty{...}{...} syntax."""
        ...

    def dataframe_to_booktabs(
        self,
        df: pd.DataFrame,
        caption: str = "",
        label: str = "",
        col_align: Optional[str] = None
    ) -> str:
        """Converts a pandas DataFrame into a publication-grade LaTeX booktabs table without vertical rules."""
        ...

    def render_chemfig(self, smiles: str) -> str:
        """Converts a SMILES string into a 2D LaTeX chemfig structural macro."""
        ...

    def sanitize_latex(self, text: str) -> str:
        """Aggressively escapes LaTeX special characters outside of existing macros and math blocks."""
        ...

    def render_manuscript(self, data_payload: Dict[str, Any]) -> str:
        """Renders the complete manuscript by injecting sanitized text and formatted tables into template."""
        ...
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\formatters\scribe_templater.py ---
"""Jinja2 Templating and LaTeX Scaffolding Engine for CoChem-SCRIBE.

Bridges the Mathematical Air-Gap by injecting exact physical tensors into
ACS/APS-compliant LaTeX templates with customized delimiters, siunitx unit harmonization,
booktabs table formatting, chemfig 2D topology rendering, and aggressive LaTeX sanitization.
"""

from __future__ import annotations

import logging
import pathlib
import re
from typing import Any, Dict, List, Optional, Union

import jinja2
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Standard siunitx unit mapping dictionary
SIUNITX_UNIT_MAP: Dict[str, str] = {
    "k": r"\kelvin",
    "kelvin": r"\kelvin",
    "c": r"\celsius",
    "degc": r"\celsius",
    "°c": r"\celsius",
    "celsius": r"\celsius",
    "kcal/mol": r"\kilo\calorie\per\mole",
    "kcal mol-1": r"\kilo\calorie\per\mole",
    "kcal mol^-1": r"\kilo\calorie\per\mole",
    "kcal/mole": r"\kilo\calorie\per\mole",
    "kj/mol": r"\kilo\joule\per\mole",
    "kj mol-1": r"\kilo\joule\per\mole",
    "kj mol^-1": r"\kilo\joule\per\mole",
    "kj/mole": r"\kilo\joule\per\mole",
    "hartree": r"\hartree",
    "eh": r"\hartree",
    "e_h": r"\hartree",
    "ev": r"\electronvolt",
    "electronvolt": r"\electronvolt",
    "cm-1": r"\per\centi\meter",
    "cm^-1": r"\per\centi\meter",
    "cm^{-1}": r"\per\centi\meter",
    "1/cm": r"\per\centi\meter",
    "ghz": r"\giga\hertz",
    "mhz": r"\mega\hertz",
    "khz": r"\kilo\hertz",
    "hz": r"\hertz",
    "d": r"\debye",
    "debye": r"\debye",
    "angstrom": r"\angstrom",
    "ang": r"\angstrom",
    "å": r"\angstrom",
    "bohr": r"\bohr",
    "a0": r"\bohr",
    "a_0": r"\bohr",
    "deg": r"\degree",
    "degree": r"\degree",
    "degrees": r"\degree",
    "°": r"\degree",
    "rad": r"\radian",
    "radian": r"\radian",
    "s": r"\second",
    "sec": r"\second",
    "second": r"\second",
    "fs": r"\femto\second",
    "femtosecond": r"\femto\second",
    "ps": r"\pico\second",
    "picosecond": r"\pico\second",
    "ns": r"\nano\second",
    "nanosecond": r"\nano\second",
    "nm": r"\nano\meter",
    "nanometer": r"\nano\meter",
    "pm": r"\pico\meter",
    "picometer": r"\pico\meter",
    "bar": r"\bar",
    "atm": r"\standardatmosphere",
    "pa": r"\pascal",
}


class Jinja2Templater:
    """Jinja2-based LaTeX scaffolding and document synthesis engine.

    Bridges the Mathematical Air-Gap by injecting exact physical tensors into
    ACS/APS-compliant LaTeX templates with customized delimiters, siunitx unit harmonization,
    booktabs table formatting, chemfig 2D topology rendering, and aggressive LaTeX sanitization.
    """

    def __init__(
        self,
        template_dir: Optional[Union[str, pathlib.Path]] = None,
        template_name: str = "base_manuscript.tex",
    ) -> None:
        """Initializes Jinja2 environment with overridden LaTeX delimiters and custom filters.

        Args:
            template_dir: Directory containing LaTeX templates. Defaults to `templates/`
                          relative to this module.
            template_name: Name of the template file to load. Defaults to `base_manuscript.tex`.

        Raises:
            FileNotFoundError: If the template directory or template file does not exist on disk.
        """
        if template_dir is None:
            self.template_dir = pathlib.Path(__file__).resolve().parent / "templates"
        else:
            self.template_dir = pathlib.Path(template_dir).resolve()

        self.template_name = template_name

        # Enforce physical template existence on disk (Mathematical Air-Gap Mandate)
        template_path = self.template_dir / self.template_name
        if not template_path.is_file():
            raise FileNotFoundError(
                f"Template file not found at dynamic path: {template_path}"
            )

        # Initialize Jinja2 environment with LaTeX-compatible delimiter overrides
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.template_dir)),
            variable_start_string=r"\VAR{",
            variable_end_string="}",
            block_start_string=r"\BLOCK{",
            block_end_string="}",
            comment_start_string=r"\COMMENT{",
            comment_end_string="}",
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,
        )

        # Register custom Jinja2 filters
        self.env.filters["latex_escape"] = self.sanitize_latex
        self.env.filters["siunitx_num"] = self.format_siunitx_num
        self.env.filters["siunitx_qty"] = self.format_siunitx_qty
        self.env.filters["chemfig"] = self.render_chemfig

    def format_siunitx_num(
        self, value: Union[float, int, str, np.integer, np.floating, Any]
    ) -> str:
        """Formats numerical scalars and scientific notation into LaTeX \\num{...} syntax.

        Args:
            value: Number (int, float) or numeric string to format.

        Returns:
            Formatted LaTeX \\num{...} string.
        """
        if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
            val_str = str(value)
            # Normalize scientific notation exponent (e.g. 1.23e-04 -> 1.23e-4)
            val_str = re.sub(r"[eE]([+-])0+(\d+)", r"e\1\2", val_str)
            val_str = re.sub(r"[eE]", "e", val_str)
            return rf"\num{{{val_str}}}"

        val_str = str(value).strip()
        if val_str.startswith(r"\num{") and val_str.endswith("}"):
            return val_str

        # Check if value matches numeric / scientific notation pattern
        if re.match(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$", val_str):
            val_str = re.sub(r"[eE]([+-])0+(\d+)", r"e\1\2", val_str)
            val_str = re.sub(r"[eE]", "e", val_str)
            return rf"\num{{{val_str}}}"

        return self.sanitize_latex(val_str)

    def format_siunitx_qty(
        self, value: Union[float, int, str, np.integer, np.floating, Any], unit: str
    ) -> str:
        """Formats numerical quantities and units into LaTeX \\qty{...}{...} syntax.

        Args:
            value: Numerical quantity value.
            unit: Physical unit string (e.g. 'K', 'kcal/mol', 'Hartree', 'cm-1', 'D').

        Returns:
            Formatted LaTeX \\qty{...}{...} string.
        """
        # Normalize numerical component
        if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
            val_str = str(value)
            val_str = re.sub(r"[eE]([+-])0+(\d+)", r"e\1\2", val_str)
            val_str = re.sub(r"[eE]", "e", val_str)
        else:
            val_str = str(value).strip()
            # Strip outer \num{...} if already present
            if val_str.startswith(r"\num{") and val_str.endswith("}"):
                val_str = val_str[5:-1].strip()
            if re.match(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$", val_str):
                val_str = re.sub(r"[eE]([+-])0+(\d+)", r"e\1\2", val_str)
                val_str = re.sub(r"[eE]", "e", val_str)

        # Normalize unit
        unit_clean = unit.strip().lower()
        if unit_clean in SIUNITX_UNIT_MAP:
            unit_macro = SIUNITX_UNIT_MAP[unit_clean]
        elif unit.strip().startswith("\\"):
            unit_macro = unit.strip()
        else:
            unit_macro = unit.strip()

        return rf"\qty{{{val_str}}}{{{unit_macro}}}"

    def dataframe_to_booktabs(
        self,
        df: pd.DataFrame,
        caption: str = "",
        label: str = "",
        col_align: Optional[str] = None,
    ) -> str:
        """Converts a pandas DataFrame into a publication-grade LaTeX booktabs table.

        Strictly enforces academic typesetting standards:
        - Uses \\toprule, \\midrule, and \\bottomrule.
        - Strictly prohibits vertical rules ('|') in column specifications.
        - Automatically formats numerical cells with \\num{...}.
        - Sanitizes text and column headers.

        Args:
            df: The pandas DataFrame to convert.
            caption: Optional table caption.
            label: Optional table LaTeX label.
            col_align: Optional column alignment string (e.g. 'lrrr').

        Returns:
            Complete LaTeX table environment string.
        """
        if df is None or (df.empty and len(df.columns) == 0):
            return ""

        if col_align is not None:
            # Strictly prohibit vertical grid lines in column specifications
            alignment = col_align.replace("|", "").strip()
        else:
            align_chars: List[str] = []
            for col in df.columns:
                if pd.api.types.is_numeric_dtype(df[col]):
                    align_chars.append("r")
                else:
                    align_chars.append("l")
            alignment = "".join(align_chars) if align_chars else "l"

        lines: List[str] = [
            r"\begin{table}[htbp]",
            r"\centering",
        ]
        if caption:
            lines.append(rf"\caption{{{caption}}}")
        if label:
            lines.append(rf"\label{{{label}}}")

        lines.append(rf"\begin{{tabular}}{{{alignment}}}")
        lines.append(r"\toprule")

        # Format column headers
        sanitized_headers = [self.sanitize_latex(str(col)) for col in df.columns]
        lines.append(" & ".join(sanitized_headers) + r" \\")
        lines.append(r"\midrule")

        # Format data rows
        for _, row in df.iterrows():
            row_cells: List[str] = []
            for col in df.columns:
                val = row[col]
                if pd.isna(val):
                    row_cells.append("-")
                elif isinstance(val, (int, float, np.integer, np.floating)) and not isinstance(val, bool):
                    row_cells.append(self.format_siunitx_num(val))
                elif isinstance(val, str) and re.match(
                    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$", val.strip()
                ):
                    row_cells.append(self.format_siunitx_num(val.strip()))
                else:
                    row_cells.append(self.sanitize_latex(str(val)))
            lines.append(" & ".join(row_cells) + r" \\")

        lines.append(r"\bottomrule")
        lines.append(r"\end{tabular}")
        lines.append(r"\end{table}")

        return "\n".join(lines)

    def render_chemfig(self, smiles: Optional[str]) -> str:
        """Converts a SMILES string into a 2D LaTeX chemfig structural macro.

        Args:
            smiles: Input SMILES string.

        Returns:
            LaTeX \\chemfig{...} string or a clean fallback comment if unparseable/empty.
        """
        if not smiles or not isinstance(smiles, str) or not smiles.strip():
            return "% [No 2D chemfig structure available]"

        clean_smiles = smiles.strip()

        # If already formatted as a chemfig macro or LaTeX comment, return directly
        if clean_smiles.startswith(r"\chemfig{") and clean_smiles.endswith("}"):
            return clean_smiles
        if clean_smiles.startswith("%"):
            return clean_smiles

        # Validate SMILES string with RDKit if present
        try:
            import importlib
            Chem = importlib.import_module("rdkit.Chem")
            RDLogger = importlib.import_module("rdkit.RDLogger")

            RDLogger.DisableLog("rdApp.*")
            mol = Chem.MolFromSmiles(clean_smiles)
            if mol is None:
                return "% [No 2D chemfig structure available]"
        except Exception:
            # Fallback heuristic validation
            if re.search(r"[^A-Za-z0-9@+\-\[\]\(\)\\\/%=#$:]", clean_smiles):
                return "% [No 2D chemfig structure available]"

        # Transform SMILES notation into ChemFig notation:
        # 1. Triple bonds '#' in SMILES -> '~' in chemfig
        cf_body = clean_smiles.replace("#", "~")

        # 2. Ring closure digits: map digits 1-9 to chemfig hooks ?[1]
        cf_body = re.sub(r"%(\d{2})", r"?[\1]", cf_body)
        cf_body = re.sub(r"(?<!\?\[)(\d)", r"?[\1]", cf_body)

        return rf"\chemfig{{{cf_body}}}"

    def sanitize_latex(self, text: Optional[str]) -> str:
        """Aggressively escapes LaTeX special characters outside of existing macros and math blocks.

        Escapes `_`, `&`, `%`, `#`, `~`, `^`, `$` in raw narrative and calculation logs,
        while preserving valid LaTeX macros and math mode blocks.

        Args:
            text: Raw input text.

        Returns:
            Sanitized, LaTeX-safe string.
        """
        if text is None:
            return ""
        if not isinstance(text, str):
            text = str(text)
        if not text:
            return ""

        stashed_segments: List[str] = []

        def save_match(m: re.Match[str]) -> str:
            idx = len(stashed_segments)
            stashed_segments.append(m.group(0))
            return f"QQQCOCHEMLATEXESC{idx}ZZZ"

        # Protected patterns: math modes, existing macros, and pre-escaped characters
        protected_patterns = [
            r"\\\\",
            r"\\_",
            r"\\&",
            r"\\%",
            r"\\#",
            r"\\\$",
            r"\\textasciitilde\{\}",
            r"\\textasciicircum\{\}",
            r"\$\$(?:[^\$]|\\\$)+?\$\$",
            r"\\\[(?:[\s\S]*?)\\\]",
            r"\\\((?:[\s\S]*?)\\\)",
            r"(?<!\\)\$(?:[^\$\n]|\\\$)+?(?<!\\)\$",
            r"\\chemfig\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}",
            r"\\qty\{[^{}]*\}\{[^{}]*\}",
            r"\\num\{[^{}]*\}",
            r"\\VAR\{[^{}]*\}",
            r"\\BLOCK\{[^{}]*\}",
            r"\\COMMENT\{[^{}]*\}",
            r"\\(?:begin|end)\{[^{}]+\}(?:\[[^\]]*\])?",
            r"\\(?:documentclass|usepackage)(?:\[[^\]]*\])?\{[^{}]+\}",
            r"\\(?:toprule|midrule|bottomrule|centering|relax|item|newline|hline)",
            r"\\(?:ref|cite|label|url|href)\{[^{}]*\}",
            r"\\[a-zA-Z]+",
        ]

        combined_pattern = re.compile("|".join(f"(?:{p})" for p in protected_patterns))

        # Extract protected regions
        tokenized = combined_pattern.sub(save_match, text)

        # Escape special characters in unprotected regions
        escaped = tokenized
        escaped = escaped.replace("_", r"\_")
        escaped = escaped.replace("&", r"\&")
        escaped = escaped.replace("%", r"\%")
        escaped = escaped.replace("#", r"\#")
        escaped = escaped.replace("~", r"\textasciitilde{}")
        escaped = escaped.replace("^", r"\textasciicircum{}")
        escaped = escaped.replace("$", r"\$")

        # Restore protected regions
        for idx, orig in enumerate(stashed_segments):
            escaped = escaped.replace(f"QQQCOCHEMLATEXESC{idx}ZZZ", orig)

        return escaped

    def _clean_tags(self, text: str) -> str:
        """Removes legacy upstream insertion tags and unresolved delimiters."""
        text = re.sub(r"<<INSERT_[^>]+>>", "", text)
        text = re.sub(r"INSERT_[A-Z_]+_HERE", "", text)
        text = re.sub(r"\{\{\s*[\w_]+\s*\}\}", "", text)
        return text.strip()

    def render_manuscript(self, data_payload: Dict[str, Any]) -> str:
        """Renders the complete manuscript by injecting sanitized text and formatted tables into template.

        Resolves upstream insertion tags, maps dynamic LAM_TRIGGER conditional blocks,
        and converts DataFrames to publication-grade booktabs tables.

        Args:
            data_payload: Dictionary containing manuscript narrative and exact physical data.

        Returns:
            Rendered complete LaTeX manuscript string.
        """
        # 1. Metadata and Header Elements
        title = self.sanitize_latex(self._clean_tags(str(data_payload.get("title", "Quantum Chemical Investigation"))))
        authors = self.sanitize_latex(
            self._clean_tags(str(data_payload.get("authors", "CoChem-SCRIBE Automated Synthesis Pipeline")))
        )
        affiliations = self.sanitize_latex(
            self._clean_tags(str(data_payload.get("affiliations", "CoChem Open-Source Computational Consortium")))
        )
        abstract = self.sanitize_latex(self._clean_tags(str(data_payload.get("abstract", ""))))

        # 2. Molecular Structure (chemfig)
        raw_chemfig = data_payload.get("chemfig_structure")
        raw_smiles = data_payload.get("smiles")
        if raw_chemfig is not None and str(raw_chemfig).strip():
            chemfig_structure = self.render_chemfig(str(raw_chemfig))
        elif raw_smiles is not None and str(raw_smiles).strip():
            chemfig_structure = self.render_chemfig(str(raw_smiles))
        else:
            chemfig_structure = ""

        # 3. Computational Details & Upstream Insertion Tag Harmonization
        raw_comp = data_payload.get(
            "computational_details",
            data_payload.get("methodology", data_payload.get("computational_methods", "")),
        )
        comp_text = self._clean_tags(str(raw_comp))
        computational_details = self.sanitize_latex(comp_text)

        # 4. Large-Amplitude Motion (LAM_TRIGGER) & Sinc-DVR Justification
        lam_trigger = bool(
            data_payload.get("lam_trigger", False)
            or data_payload.get("sinc_dvr_flag", False)
            or data_payload.get("lam_active", False)
        )
        raw_justification = data_payload.get("sinc_dvr_justification", "")
        if raw_justification:
            sinc_dvr_justification = self.sanitize_latex(self._clean_tags(str(raw_justification)))
        elif lam_trigger:
            sinc_dvr_justification = self.sanitize_latex(
                "Large-amplitude torsional degrees of freedom detected; 1D/2D Sinc-DVR numerical "
                "potential energy surface discretization is applied to account for quantum anharmonicity."
            )
        else:
            sinc_dvr_justification = ""

        # 5. Tables Formatting (Conformer, Thermodynamic, Vibrational)
        # Conformer Table
        raw_conf = data_payload.get(
            "conformer_table", data_payload.get("conformation_table", "")
        )
        if isinstance(raw_conf, pd.DataFrame):
            conformer_table = self.dataframe_to_booktabs(
                raw_conf,
                caption="Relative Energies and Boltzmann Populations of Optimized Conformers",
                label="tab:conformers",
            )
        elif raw_conf:
            conformer_table = str(raw_conf)
        else:
            conformer_table = ""

        # Thermodynamic Table
        raw_thermo = data_payload.get(
            "thermo_table", data_payload.get("thermodynamics_table", "")
        )
        if isinstance(raw_thermo, pd.DataFrame):
            thermo_table = self.dataframe_to_booktabs(
                raw_thermo,
                caption="Thermochemical Properties and Free Energies at Standard State (\\qty{298.15}{\\kelvin}, \\qty{1.0}{\\bar})",
                label="tab:thermo",
            )
        elif raw_thermo:
            thermo_table = str(raw_thermo)
        else:
            thermo_table = ""

        # Vibrational Table
        raw_vib = data_payload.get(
            "vibrational_table", data_payload.get("frequencies_table", "")
        )
        if isinstance(raw_vib, pd.DataFrame):
            vibrational_table = self.dataframe_to_booktabs(
                raw_vib,
                caption="Harmonic Vibrational Frequencies and IR Intensities",
                label="tab:vibrational",
            )
        elif raw_vib:
            vibrational_table = str(raw_vib)
        else:
            vibrational_table = ""

        # 6. Provenance Footer
        raw_prov = data_payload.get(
            "provenance_footer",
            data_payload.get(
                "provenance",
                "All calculation telemetry recorded under FAIR data principles and validated via CoChem-SCRIBE.",
            ),
        )
        provenance_footer = self.sanitize_latex(self._clean_tags(str(raw_prov)))

        # 7. Assemble Context & Render Template
        context: Dict[str, Any] = {
            "title": title,
            "authors": authors,
            "affiliations": affiliations,
            "abstract": abstract,
            "chemfig_structure": chemfig_structure,
            "computational_details": computational_details,
            "sinc_dvr_justification": sinc_dvr_justification,
            "conformer_table": conformer_table,
            "thermo_table": thermo_table,
            "vibrational_table": vibrational_table,
            "provenance_footer": provenance_footer,
        }

        # Inject any supplementary user variables into template context
        for key, val in data_payload.items():
            if key not in context:
                if isinstance(val, pd.DataFrame):
                    context[key] = self.dataframe_to_booktabs(val)
                elif isinstance(val, str):
                    context[key] = self.sanitize_latex(self._clean_tags(val))
                else:
                    context[key] = val

        template = self.env.get_template(self.template_name)
        rendered_manuscript: str = str(template.render(**context))

        return rendered_manuscript


if __name__ == "__main__":
    # Standalone CLI pre-flight verification test block
    print("[COCHEM-SCRIBE] Executing Jinja2Templater Pre-Flight Verification...")

    templater = Jinja2Templater()

    # Verify siunitx formatting
    assert templater.format_siunitx_num("1.23e-4") == r"\num{1.23e-4}"
    assert templater.format_siunitx_num("1.23E-04") == r"\num{1.23e-4}"
    assert templater.format_siunitx_num(1.23e-5) == r"\num{1.23e-5}"
    assert templater.format_siunitx_num(298.15) == r"\num{298.15}"
    assert templater.format_siunitx_qty(298.15, "K") == r"\qty{298.15}{\kelvin}"
    assert templater.format_siunitx_qty(-154.3, "kcal/mol") == r"\qty{-154.3}{\kilo\calorie\per\mole}"
    assert templater.format_siunitx_qty(1200.5, "cm-1") == r"\qty{1200.5}{\per\centi\meter}"

    # Verify sanitization
    dirty_text = "SCF_CONVERGENCE_FAIL & Error_Rate % = 0.5% #1 ~ ^test"
    clean_text = templater.sanitize_latex(dirty_text)
    assert r"\_" in clean_text
    assert r"\&" in clean_text
    assert r"\%" in clean_text
    assert r"\#" in clean_text
    assert r"\textasciitilde{}" in clean_text
    assert r"\textasciicircum{}" in clean_text

    # Verify ChemFig rendering
    assert r"\chemfig{CCO}" == templater.render_chemfig("CCO")
    assert templater.render_chemfig("") == "% [No 2D chemfig structure available]"

    # Verify DataFrame to booktabs
    df_confs = pd.DataFrame({
        "Conformer": ["Conf-1", "Conf-2"],
        "Energy (Hartree)": [-154.34567, -154.34120],
        "Rel_Energy (kcal/mol)": [0.0, 2.81],
    })
    table_latex = templater.dataframe_to_booktabs(df_confs, caption="Test Table", label="tab:test")
    assert r"\toprule" in table_latex
    assert r"\midrule" in table_latex
    assert r"\bottomrule" in table_latex
    assert "|" not in table_latex.split(r"\begin{tabular}")[1].split(r"\toprule")[0]

    # Verify full manuscript synthesis
    test_payload = {
        "title": "Quantum Analysis of Ethanol",
        "authors": "Jane Doe, John Smith",
        "affiliations": "Department of Chemistry, CoChem University",
        "abstract": "We investigate the torsional potential of ethanol using DFT and Sinc-DVR.",
        "smiles": "CCO",
        "computational_details": "Calculations were carried out using B3LYP/def2-TZVP. INSERT_THERMO_TABLE_HERE",
        "lam_trigger": True,
        "conformer_table": df_confs,
        "thermo_table": df_confs,
        "vibrational_table": df_confs,
        "provenance_footer": "Telemetry verified under FAIR principles.",
    }
    manuscript = templater.render_manuscript(test_payload)
    assert r"\title{Quantum Analysis of Ethanol}" in manuscript
    assert r"\subsection{Large-Amplitude Motion \& Discrete Variable Representation}" in manuscript
    assert r"\chemfig{CCO}" in manuscript
    assert r"\VAR{" not in manuscript
    assert r"\BLOCK{" not in manuscript

    print("[SCRIBE TEMPLATER PRE-FLIGHT VERIFIED]")

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.