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

    def format_siunitx_num(self, value: Union[float, int, str]) -> str:
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

    def format_siunitx_qty(self, value: Union[float, int, str], unit: str) -> str:
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
            from rdkit import Chem, RDLogger

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
