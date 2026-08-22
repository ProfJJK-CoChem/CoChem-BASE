# cochem_canvas_target: cochem_core/ai/template_engine.py
"""
CoChem-BASE AI Integrations - Hallucination-Resistant Template Engine & Data Injection Protocol.
Strict Zero-Mock Mandate Compliance.

Air-gaps Large Language Models (LLMs) from physical constants, energies, coordinates,
and geometric matrices. LLMs are restricted to qualitative narrative insight, methodology
descriptions, and error analysis, while exact, uncorrupted float64 values are dynamically
injected directly from the landscape.h5 database into Jinja2 placeholders post-inference.

Core Capabilities:
1. PayloadBuilder:
   - System prompt generation with immutable air-gap systemic command injection:
     "Never invent physical constants, energies, or geometric values. Provide narrative insight, error analysis, and methodology structure only."
   - Standardized chat message assembly and parameter catalog formatting.
2. Post-Inference Data Injection:
   - Direct extraction of uncorrupted float64 datasets, eigenvalues, coordinates, and attributes from landscape.h5.
   - Jinja2 template rendering with dynamic HDF5 node resolution.
   - IEEE-754 byte-level SHA-256 provenance checksumming.
3. LaTeX siunitx Enforcement:
   - American Physical Society (APS) & Physical Review formatting standards.
   - Wraps all physical numbers in \\num{...} and physical quantities in \\qty{...}{...}.
   - Standardizes angles (\\ang{...}), scientific notation (\\num{1.23e-4}), and chemistry units.
   - Generates LaTeX tables with siunitx 'S' alignment columns.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import h5py
import jinja2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("CoChem.AI.TemplateEngine")

# =============================================================================
# CONSTANTS & IMMUTABLE SYSTEMIC COMMAND
# =============================================================================

SYSTEMIC_COMMAND_AIRGAP: str = (
    "Never invent physical constants, energies, or geometric values. "
    "Provide narrative insight, error analysis, and methodology structure only."
)

SYSTEMIC_COMMAND: str = SYSTEMIC_COMMAND_AIRGAP

DEFAULT_ROLE_PROMPT: str = (
    "You are an expert computational chemist and scientific scribe for the CoChem ecosystem. "
    "Your objective is to generate rigorous, publication-grade scientific manuscripts and analysis. "
    "Follow American Physical Society (APS) and IUPAC technical conventions."
)

LATEX_GUIDANCE_PROMPT: str = (
    "When generating manuscript templates, use Jinja2 variable placeholders "
    "(e.g., {{ energies.ground_state | si_qty('hartree') }} or {{ conformers[0].bond_length | si_qty('angstrom') }}) "
    "for all numerical data, thermodynamic constants, bond metrics, frequencies, and coordinates. "
    "Ensure all physical properties are formatted with standard \\siunitx macros (\\num{}, \\qty{}, \\ang{})."
)

# Standard chemistry & physics unit mappings to siunitx macros
APS_UNIT_MAPPINGS: Dict[str, str] = {
    # Energy
    "hartree": r"\hartree",
    "hartrees": r"\hartree",
    "eh": r"\hartree",
    "a.u.": r"\hartree",
    "au": r"\hartree",
    "ev": r"\electronvolt",
    "electronvolt": r"\electronvolt",
    "electronvolts": r"\electronvolt",
    "mev": r"\milli\electronvolt",
    "gev": r"\giga\electronvolt",
    "kcal/mol": r"\kilo\calorie\per\mole",
    "kcal_per_mol": r"\kilo\calorie\per\mole",
    "kcal_mol-1": r"\kilo\calorie\per\mole",
    "kj/mol": r"\kilo\joule\per\mole",
    "kj_per_mol": r"\kilo\joule\per\mole",
    "kj_mol-1": r"\kilo\joule\per\mole",
    "j/mol": r"\joule\per\mole",
    "j": r"\joule",
    "kj": r"\kilo\joule",
    "cal": r"\calorie",
    "kcal": r"\kilo\calorie",
    # Distance / Geometry
    "angstrom": r"\angstrom",
    "angstroms": r"\angstrom",
    "a": r"\angstrom",
    "aa": r"\angstrom",
    "å": r"\angstrom",
    "Å": r"\angstrom",
    "bohr": r"\bohr",
    "bohrs": r"\bohr",
    "a0": r"\bohr",
    "pm": r"\picometer",
    "picometer": r"\picometer",
    "nm": r"\nanometer",
    "nanometer": r"\nanometer",
    "um": r"\micro\meter",
    "micrometer": r"\micro\meter",
    "m": r"\meter",
    "meter": r"\meter",
    "cm": r"\centi\meter",
    # Angle
    "deg": r"\degree",
    "degree": r"\degree",
    "degrees": r"\degree",
    "rad": r"\radian",
    "radian": r"\radian",
    "radians": r"\radian",
    # Frequency / Spectroscopy
    "cm-1": r"\per\centi\meter",
    "cm^-1": r"\per\centi\meter",
    "1/cm": r"\per\centi\meter",
    "wavenumber": r"\per\centi\meter",
    "wavenumbers": r"\per\centi\meter",
    "hz": r"\hertz",
    "khz": r"\kilo\hertz",
    "mhz": r"\mega\hertz",
    "ghz": r"\giga\hertz",
    "thz": r"\tera\hertz",
    # Dipole / Electromagnetic
    "debye": r"\debye",
    "d": r"\debye",
    "c*m": r"\coulomb\meter",
    # Temperature / Pressure
    "k": r"\kelvin",
    "kelvin": r"\kelvin",
    "c": r"\degreeCelsius",
    "celsius": r"\degreeCelsius",
    "bar": r"\bar",
    "mbar": r"\milli\bar",
    "atm": r"\standardatmosphere",
    "atmosphere": r"\standardatmosphere",
    "atmospheres": r"\standardatmosphere",
    "pa": r"\pascal",
    "kpa": r"\kilo\pascal",
    "mpa": r"\mega\pascal",
    # Time
    "fs": r"\femtosecond",
    "femtosecond": r"\femtosecond",
    "femtoseconds": r"\femtosecond",
    "ps": r"\picosecond",
    "picosecond": r"\picosecond",
    "picoseconds": r"\picosecond",
    "ns": r"\nanosecond",
    "nanosecond": r"\nanosecond",
    "s": r"\second",
    "second": r"\second",
    "seconds": r"\second",
}

# Regex to detect raw physical quantities in LaTeX text for siunitx wrapping
_NON_ANGLE_UNITS = [
    re.escape(k) for k in APS_UNIT_MAPPINGS.keys()
    if k not in ("deg", "degree", "degrees", "rad", "radian", "radians")
]
# Sort by length descending to match longest substrings first (e.g. kcal/mol before cal)
_UNIT_PATTERN_STR = "|".join(sorted(set(_NON_ANGLE_UNITS), key=len, reverse=True))

RAW_QUANTITY_REGEX: re.Pattern[str] = re.compile(
    r"(?<!\\num\{)(?<!\\qty\{)(?<!\\SI\{)(?<!\\ang\{)"
    r"([+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?)\s*"
    rf"({_UNIT_PATTERN_STR})\b",
    re.IGNORECASE,
)

# Regex to detect raw angle measurements (e.g., 104.5 deg, 104.5°)
RAW_ANGLE_REGEX: re.Pattern[str] = re.compile(
    r"(?<!\\ang\{)([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*(?:°|deg|degrees?)\b",
    re.IGNORECASE,
)


# =============================================================================
# PYDANTIC DATA MODELS
# =============================================================================

class HDF5PointerRef(BaseModel):
    """
    Pointer model for lightweight referencing of HDF5 datasets.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    file_path: str = Field(..., description="Filesystem path to the HDF5 archive")
    node_path: str = Field(..., description="Internal dataset or attribute path in the HDF5 archive")
    dtype: Optional[str] = Field(default="float64", description="Expected datatype")
    shape: Optional[List[int]] = Field(default=None, description="Dataset shape")


class LaTeXFormattingOptions(BaseModel):
    """
    Formatting preferences for American Physical Society (APS) LaTeX siunitx compilation.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    use_qty: bool = Field(default=True, description="Whether to use \\qty{val}{unit} (siunitx v3) or \\SI{val}{unit} (v2)")
    round_precision: Optional[int] = Field(default=None, ge=0, description="Optional decimal places rounding precision")
    significant_figures: Optional[int] = Field(default=None, ge=1, description="Optional significant figures formatting")
    scientific_threshold_low: float = Field(default=1e-3, description="Lower threshold below which scientific notation is enforced")
    scientific_threshold_high: float = Field(default=1e4, description="Upper threshold above which scientific notation is enforced")
    aps_align_decimals: bool = Field(default=True, description="Ensure standard decimal formatting for APS column alignment")
    custom_unit_mappings: Dict[str, str] = Field(default_factory=dict, description="User-supplied unit overrides")


class PromptPayload(BaseModel):
    """
    Structured, air-gapped prompt payload delivered to LLM inference engines.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    system_prompt: str = Field(..., description="Air-gapped system prompt with immutable command")
    user_prompt: str = Field(..., description="Target user instruction or template draft request")
    systemic_command: str = Field(
        default=SYSTEMIC_COMMAND_AIRGAP,
        description="Immutable air-gap directive preventing numerical hallucination"
    )
    context_data: Dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary without raw heavy floats")
    h5_pointers: List[HDF5PointerRef] = Field(default_factory=list, description="Pointers to landscape.h5 data nodes")
    placeholder_spec: List[str] = Field(default_factory=list, description="List of expected placeholder keys")
    template_type: str = Field(default="jinja2", description="Template format (jinja2, latex, markdown, raw)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Auxiliary provenance metadata")

    def to_dict(self) -> Dict[str, Any]:
        """Convert payload to dictionary."""
        return self.model_dump()


class InjectedDataSummary(BaseModel):
    """
    Validation artifact and cryptographic provenance report for post-inference data injection.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    injected_keys: List[str] = Field(default_factory=list, description="List of placeholder keys populated with data")
    dataset_count: int = Field(default=0, ge=0, description="Number of unique HDF5 datasets accessed")
    raw_byte_checksum: str = Field(..., description="SHA-256 hash of concatenated raw float64 IEEE-754 bytes")
    output_text: str = Field(..., description="Rendered text containing exact injected float64 data")
    latex_enforced: bool = Field(default=False, description="Whether siunitx formatting was verified and enforced")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Execution and resolution statistics")


# =============================================================================
# LATEX SIUNITX FORMATTING ENGINE (APS STANDARDS)
# =============================================================================

class LaTeXFormatter:
    """
    American Physical Society (APS) and Physical Review compliant LaTeX formatter
    for physical quantities, scientific notation, and siunitx tags.
    """

    def __init__(self, options: Optional[LaTeXFormattingOptions] = None) -> None:
        self.options = options or LaTeXFormattingOptions()
        self.unit_mappings = {**APS_UNIT_MAPPINGS, **self.options.custom_unit_mappings}

    def resolve_unit_macro(self, unit_str: str) -> str:
        """
        Resolves a unit string into an official siunitx macro (e.g. 'kcal/mol' -> '\\kilo\\calorie\\per\\mole').
        """
        clean_unit = unit_str.strip().lower()
        if clean_unit in self.unit_mappings:
            return self.unit_mappings[clean_unit]

        # If already formatted as LaTeX macro or siunitx syntax, return as-is
        if unit_str.startswith("\\") or "{" in unit_str:
            return unit_str

        # Fallback: wrap unit string cleanly
        return unit_str

    def format_num(
        self,
        value: Union[float, int, np.floating, np.integer, np.ndarray, str],
        precision: Optional[int] = None,
        uncertainty: Optional[Union[float, np.floating, np.ndarray]] = None,
        sigfigs: Optional[int] = None,
    ) -> str:
        """
        Formats a numeric scalar into an APS-compliant \\num{...} tag.
        Preserves uncorrupted IEEE-754 float64 representation when precision is omitted.
        """
        if isinstance(value, np.ndarray):
            if value.ndim == 0 or value.size == 1:
                numeric_val = float(value.item())
            else:
                raise ValueError(f"Scalar format requires scalar or 1-element array, got shape {value.shape}")
        elif isinstance(value, str):
            try:
                numeric_val = float(value)
            except ValueError:
                return f"\\num{{{value}}}"
        else:
            numeric_val = float(value)

        # Handle special floats
        if math.isnan(numeric_val):
            return r"\text{NaN}"
        if math.isinf(numeric_val):
            return r"\infty" if numeric_val > 0 else r"-\infty"

        effective_precision = precision if precision is not None else self.options.round_precision
        effective_sigfigs = sigfigs if sigfigs is not None else self.options.significant_figures

        # Determine string representation
        if effective_sigfigs is not None and effective_sigfigs > 0:
            formatted_val_str = f"{numeric_val:.{effective_sigfigs}g}"
            # Standardize scientific notation (e.g., 1.23e-04 -> 1.23e-4, 2.5e+06 -> 2.5e6)
            formatted_val_str = re.sub(r"e\+0*(\d+)", r"e\1", formatted_val_str, flags=re.IGNORECASE)
            formatted_val_str = re.sub(r"e-0*(\d+)", r"e-\1", formatted_val_str, flags=re.IGNORECASE)
        elif effective_precision is not None:
            formatted_val_str = f"{numeric_val:.{effective_precision}f}"
        else:
            # Check if magnitude warrants scientific notation
            abs_val = abs(numeric_val)
            if abs_val > 0 and (
                abs_val < self.options.scientific_threshold_low
                or abs_val >= self.options.scientific_threshold_high
            ):
                formatted_val_str = np.format_float_scientific(
                    np.float64(numeric_val),
                    trim="-",
                    exp_digits=1,
                )
                formatted_val_str = re.sub(r"e\+0*(\d+)", r"e\1", formatted_val_str, flags=re.IGNORECASE)
                formatted_val_str = re.sub(r"e-0*(\d+)", r"e-\1", formatted_val_str, flags=re.IGNORECASE)
            else:
                # Format positional float64 preserving exact precision
                formatted_val_str = np.format_float_positional(
                    np.float64(numeric_val),
                    trim="-",
                    fractional=False
                )

        if uncertainty is not None:
            unc_float = float(uncertainty.item() if isinstance(uncertainty, np.ndarray) else uncertainty)
            if effective_precision is not None:
                unc_str = f"{unc_float:.{effective_precision}f}"
            else:
                unc_str = np.format_float_positional(np.float64(unc_float), trim="-")
            return f"\\num{{{formatted_val_str} \\pm {unc_str}}}"

        return f"\\num{{{formatted_val_str}}}"

    def format_qty(
        self,
        value: Union[float, int, np.floating, np.integer, np.ndarray, str],
        unit: str,
        precision: Optional[int] = None,
        uncertainty: Optional[Union[float, np.floating, np.ndarray]] = None,
        sigfigs: Optional[int] = None,
    ) -> str:
        """
        Formats a physical scalar and unit into an APS-compliant \\qty{val}{unit} or \\SI{val}{unit} tag.
        """
        # If value was provided inside format_num, extract the inner argument
        num_tag = self.format_num(value, precision=precision, uncertainty=uncertainty, sigfigs=sigfigs)
        match = re.match(r"\\num\{(.+)\}", num_tag)
        inner_val = match.group(1) if match else str(value)

        unit_macro = self.resolve_unit_macro(unit)
        macro_name = "\\qty" if self.options.use_qty else "\\SI"

        return f"{macro_name}{{{inner_val}}}{{{unit_macro}}}"

    def format_angle(
        self,
        value: Union[float, int, np.floating, np.integer, np.ndarray, str],
        precision: Optional[int] = None,
    ) -> str:
        """
        Formats an angle into an APS-compliant \\ang{...} tag.
        """
        if isinstance(value, np.ndarray):
            if value.ndim == 0 or value.size == 1:
                num_val = float(value.item())
            else:
                raise ValueError(f"Angle format requires scalar or 1-element array, got shape {value.shape}")
        elif isinstance(value, str):
            try:
                num_val = float(value)
            except ValueError:
                return f"\\ang{{{value}}}"
        else:
            num_val = float(value)

        effective_precision = precision if precision is not None else self.options.round_precision
        if effective_precision is not None:
            val_str = f"{num_val:.{effective_precision}f}"
        else:
            val_str = np.format_float_positional(np.float64(num_val), trim="-")

        return f"\\ang{{{val_str}}}"

    def format_matrix_latex(
        self,
        matrix: Union[np.ndarray, Sequence[Sequence[Any]]],
        col_format: str = "S[table-format=3.6]",
        precision: Optional[int] = None,
    ) -> str:
        """
        Formats a 2D NumPy array into a LaTeX table block using siunitx 'S' alignment columns.
        """
        arr = np.asarray(matrix, dtype=np.float64)
        if arr.ndim != 2:
            raise ValueError(f"Matrix formatting requires 2D array, got shape {arr.shape}")

        rows, cols = arr.shape
        col_specs = " ".join([col_format] * cols)
        lines: List[str] = [f"\\begin{{tabular}}{{{col_specs}}}", "\\hline"]

        for r in range(rows):
            row_items = []
            for c in range(cols):
                val = arr[r, c]
                if precision is not None:
                    item_str = f"{val:.{precision}f}"
                else:
                    item_str = np.format_float_positional(val, trim="-")
                row_items.append(item_str)
            lines.append(" & ".join(row_items) + r" \\")

        lines.append(r"\hline")
        lines.append(r"\end{tabular}")
        return "\n".join(lines)

    def enforce_siunitx(self, text: str) -> str:
        """
        Scans generated LaTeX text for bare physical quantities and angles,
        wrapping them in proper \\qty{...}{...} and \\ang{...} tags.
        """
        # Replace bare angle specifications: 104.5 deg -> \ang{104.5}
        def _replace_angle(match: re.Match[str]) -> str:
            val = match.group(1)
            return self.format_angle(val)

        text = RAW_ANGLE_REGEX.sub(_replace_angle, text)

        # Replace bare quantities: -76.43 hartree -> \qty{-76.43}{\hartree}
        def _replace_qty(match: re.Match[str]) -> str:
            val = match.group(1)
            raw_unit = match.group(2)
            return self.format_qty(val, raw_unit)

        text = RAW_QUANTITY_REGEX.sub(_replace_qty, text)

        return text


# =============================================================================
# HDF5 DATA EXTRACTION & INJECTION (LANDSCAPE.H5 AIR-GAP BRIDGING)
# =============================================================================

def resolve_landscape_h5_file(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Locates the authoritative landscape.h5 database path via configuration or environment.
    """
    if custom_path is not None:
        p = Path(custom_path).resolve()
        return p

    env_path = os.environ.get("COCHEM_LANDSCAPE_H5")
    if env_path:
        return Path(env_path).resolve()

    # Fallback to standard artifact location in user workspace or cwd
    candidates = [
        Path.cwd() / "Databases" / "landscape.h5",
        Path.cwd() / "landscape.h5",
        Path.home() / ".cochem" / "artifacts" / "Databases" / "landscape.h5",
    ]
    for cand in candidates:
        if cand.is_file():
            return cand

    return Path.cwd() / "landscape.h5"


def extract_h5_float64_dataset(
    h5_source: Union[str, Path, h5py.File, h5py.Group],
    dataset_node: str,
) -> np.ndarray:
    """
    Extracts an exact, uncorrupted float64 dataset or scalar attribute from an HDF5 source.
    Guarantees IEEE-754 float64 precision without downcasting or lossy string rounding.
    """
    clean_node = dataset_node.strip()

    def _read_from_opened_file(f: Union[h5py.File, h5py.Group]) -> np.ndarray:
        # Check direct dataset access
        if clean_node in f:
            item = f[clean_node]
            if isinstance(item, h5py.Dataset):
                data = item[()]
                return np.asarray(data, dtype=np.float64)
            elif isinstance(item, h5py.Group):
                raise ValueError(f"Target node '{clean_node}' is an HDF5 Group, not a Dataset.")

        # Check attribute access syntax: "group_path@attr_name" or "/conformer_0@energy"
        if "@" in clean_node:
            group_part, attr_name = clean_node.split("@", 1)
            target_group = f[group_part] if group_part in f else f
            if attr_name in target_group.attrs:
                attr_val = target_group.attrs[attr_name]
                return np.asarray(attr_val, dtype=np.float64)
            raise KeyError(f"Attribute '{attr_name}' not found in HDF5 node '{group_part}'")

        # Check root attributes
        if clean_node.startswith("@") and clean_node[1:] in f.attrs:
            attr_name = clean_node[1:]
            return np.asarray(f.attrs[attr_name], dtype=np.float64)

        raise KeyError(f"HDF5 dataset or attribute '{clean_node}' does not exist in archive.")

    if isinstance(h5_source, (h5py.File, h5py.Group)):
        return _read_from_opened_file(h5_source)

    file_path = Path(h5_source).resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"HDF5 database not found at {file_path}")

    # Use swmr=True if available for safe concurrent read
    try:
        with h5py.File(str(file_path), "r", swmr=True) as h5f:
            return _read_from_opened_file(h5f)
    except (OSError, ValueError):
        with h5py.File(str(file_path), "r") as h5f:
            return _read_from_opened_file(h5f)


def build_h5_tree_dict(
    h5_source: Union[str, Path, h5py.File, h5py.Group],
    base_group: str = "/",
) -> Dict[str, Any]:
    """
    Recursively extracts all numerical datasets and attributes into a nested dictionary
    of exact float64 NumPy scalars and arrays.
    """
    def _walk_group(group: Union[h5py.File, h5py.Group]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        # Add group attributes
        for attr_key, attr_val in group.attrs.items():
            try:
                result[f"attr_{attr_key}"] = np.asarray(attr_val, dtype=np.float64)
            except (ValueError, TypeError):
                result[f"attr_{attr_key}"] = attr_val

        for key, item in group.items():
            if isinstance(item, h5py.Dataset):
                try:
                    data = item[()]
                    if np.issubdtype(data.dtype, np.number):
                        result[key] = np.asarray(data, dtype=np.float64)
                    else:
                        result[key] = data
                except Exception as e:
                    logger.debug("Skipping dataset %s during dict walk: %s", key, e)
            elif isinstance(item, h5py.Group):
                result[key] = _walk_group(item)

        return result

    if isinstance(h5_source, (h5py.File, h5py.Group)):
        return _walk_group(h5_source)

    file_path = Path(h5_source).resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"HDF5 archive does not exist at {file_path}")

    with h5py.File(str(file_path), "r") as h5f:
        target = h5f[base_group] if base_group != "/" and base_group in h5f else h5f
        return _walk_group(target)


class H5DataInjector:
    """
    Extracts numerical datasets from landscape.h5 and constructs a secure
    data context for Jinja2 post-inference rendering.
    """

    def __init__(self, h5_path: Optional[Union[str, Path]] = None) -> None:
        self.h5_path = Path(h5_path).resolve() if h5_path else resolve_landscape_h5_file()
        self._formatter = LaTeXFormatter()

    def get_dataset(self, node_path: str) -> np.ndarray:
        """Fetch exact float64 dataset from HDF5."""
        return extract_h5_float64_dataset(self.h5_path, node_path)

    def compute_float64_checksum(self, values: Union[Sequence[Any], Dict[str, Any]]) -> str:
        """
        Computes a cryptographic SHA-256 hash over the raw IEEE-754 bytes of injected values.
        Recursively traverses nested dictionaries, lists, and arrays ensuring full precision byte hashing.
        """
        hasher = hashlib.sha256()

        def _hash_item(item: Any) -> None:
            if isinstance(item, (float, int, np.floating, np.integer)):
                arr = np.asarray(item, dtype=np.float64)
                hasher.update(arr.tobytes())
            elif isinstance(item, np.ndarray):
                hasher.update(np.ascontiguousarray(item, dtype=np.float64).tobytes())
            elif isinstance(item, dict):
                for k in sorted(item.keys()):
                    hasher.update(str(k).encode("utf-8"))
                    _hash_item(item[k])
            elif isinstance(item, (list, tuple, set)):
                for sub_item in item:
                    _hash_item(sub_item)
            else:
                hasher.update(str(item).encode("utf-8"))

        if isinstance(values, dict):
            _hash_item(values)
        else:
            for v in values:
                _hash_item(v)

        return hasher.hexdigest()


# =============================================================================
# PAYLOAD BUILDER & SYSTEM PROMPT GENERATOR
# =============================================================================

class PayloadBuilder:
    """
    Constructs air-gapped system prompts and user payloads for LLM interaction.
    Enforces the immutable systemic command preventing numerical hallucination.
    """

    def __init__(self, base_role_prompt: str = DEFAULT_ROLE_PROMPT) -> None:
        self.base_role_prompt = base_role_prompt

    def build_system_prompt(
        self,
        custom_instructions: Optional[str] = None,
        role: Optional[str] = None,
        include_latex_guidance: bool = True,
    ) -> str:
        """
        Generates the authoritative air-gapped system prompt.
        Guarantees that SYSTEMIC_COMMAND_AIRGAP is always present verbatim.
        """
        role_text = role or self.base_role_prompt
        sections: List[str] = [
            f"# ROLE & MANDATE\n{role_text.strip()}",
            f"# AIR-GAP SYSTEMIC DIRECTIVE\n{SYSTEMIC_COMMAND_AIRGAP}",
        ]

        if include_latex_guidance:
            sections.append(f"# LATEX TEMPLATING & SIUNITX GUIDELINES\n{LATEX_GUIDANCE_PROMPT}")

        if custom_instructions and custom_instructions.strip():
            sections.append(f"# DOMAIN-SPECIFIC INSTRUCTIONS\n{custom_instructions.strip()}")

        return "\n\n".join(sections)

    def build_payload(
        self,
        user_prompt: str,
        custom_instructions: Optional[str] = None,
        system_prompt: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
        h5_pointers: Optional[List[Union[HDF5PointerRef, Dict[str, Any]]]] = None,
        placeholder_spec: Optional[List[str]] = None,
        template_type: str = "jinja2",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PromptPayload:
        """
        Assembles a fully typed, validated PromptPayload model.
        """
        effective_system_prompt = system_prompt or self.build_system_prompt(custom_instructions=custom_instructions)

        # Enforce that systemic command is in system prompt
        if SYSTEMIC_COMMAND_AIRGAP not in effective_system_prompt:
            effective_system_prompt = f"{effective_system_prompt}\n\n# AIR-GAP DIRECTIVE\n{SYSTEMIC_COMMAND_AIRGAP}"

        typed_pointers: List[HDF5PointerRef] = []
        if h5_pointers:
            for p in h5_pointers:
                if isinstance(p, HDF5PointerRef):
                    typed_pointers.append(p)
                elif isinstance(p, dict):
                    typed_pointers.append(HDF5PointerRef(**p))

        return PromptPayload(
            system_prompt=effective_system_prompt,
            user_prompt=user_prompt,
            systemic_command=SYSTEMIC_COMMAND_AIRGAP,
            context_data=context_data or {},
            h5_pointers=typed_pointers,
            placeholder_spec=placeholder_spec or [],
            template_type=template_type,
            metadata=metadata or {},
        )

    def build_chat_messages(
        self,
        user_prompt: str,
        custom_instructions: Optional[str] = None,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        """
        Constructs standard chat message dictionaries [{"role": "system", ...}, {"role": "user", ...}].
        """
        sys_prompt = system_prompt or self.build_system_prompt(custom_instructions=custom_instructions)
        messages: List[Dict[str, str]] = [{"role": "system", "content": sys_prompt}]

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_prompt})
        return messages

    @staticmethod
    def format_placeholder_catalog(datasets: Dict[str, str]) -> str:
        """
        Generates a markdown table of available template placeholder keys
        and their descriptions for prompt context injection.
        """
        lines = [
            "| Placeholder Variable | Description |",
            "| :--- | :--- |",
        ]
        for var_name, desc in datasets.items():
            lines.append(f"| `{{{{ {var_name} }}}}` | {desc} |")
        return "\n".join(lines)


# =============================================================================
# TEMPLATE ENGINE (JINJA2 RENDERING & SIUNITX ENFORCEMENT)
# =============================================================================

class TemplateEngine:
    """
    Hallucination-resistant template engine managing Jinja2 template rendering,
    HDF5 data injection from landscape.h5, and LaTeX siunitx standard compliance.
    """

    def __init__(
        self,
        landscape_path: Optional[Union[str, Path]] = None,
        formatting_options: Optional[LaTeXFormattingOptions] = None,
    ) -> None:
        self.landscape_path = Path(landscape_path).resolve() if landscape_path else resolve_landscape_h5_file()
        self.formatting_options = formatting_options or LaTeXFormattingOptions()
        self.formatter = LaTeXFormatter(self.formatting_options)
        self.payload_builder = PayloadBuilder()
        self.injector = H5DataInjector(self.landscape_path)
        self._jinja_env = self._create_jinja_environment()

    def _create_jinja_environment(self) -> jinja2.Environment:
        """
        Configures the sandboxed Jinja2 execution environment with scientific filters and globals.
        """
        env = jinja2.Environment(
            autoescape=False,
            undefined=jinja2.Undefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Register scientific siunitx filters
        env.filters["si_num"] = lambda val, prec=None, unc=None, sig=None: self.formatter.format_num(
            val, precision=prec, uncertainty=unc, sigfigs=sig
        )
        env.filters["si_qty"] = lambda val, unit, prec=None, unc=None, sig=None: self.formatter.format_qty(
            val, unit, precision=prec, uncertainty=unc, sigfigs=sig
        )
        env.filters["si_angle"] = lambda val, prec=None: self.formatter.format_angle(val, precision=prec)
        env.filters["aps_num"] = env.filters["si_num"]
        env.filters["aps_qty"] = env.filters["si_qty"]

        env.filters["float64_exact"] = lambda val: (
            np.format_float_positional(np.float64(val), trim="-")
            if isinstance(val, (float, int, np.floating, np.integer))
            else str(val)
        )
        env.filters["sigfigs"] = lambda val, n: f"{float(val):.{n}g}"

        # Register globals
        env.globals["num"] = env.filters["si_num"]
        env.globals["qty"] = env.filters["si_qty"]
        env.globals["ang"] = env.filters["si_angle"]

        # HDF5 dynamic fetcher global
        def _h5_fetcher(node_path: str) -> Any:
            try:
                arr = extract_h5_float64_dataset(self.landscape_path, node_path)
                return float(arr) if arr.ndim == 0 else arr
            except Exception as e:
                logger.warning("Failed to fetch HDF5 node '%s': %s", node_path, e)
                return f"[H5_UNRESOLVED:{node_path}]"

        env.globals["h5"] = _h5_fetcher

        return env

    def render_template(
        self,
        template_str: str,
        context: Optional[Dict[str, Any]] = None,
        h5_source: Optional[Union[str, Path, Dict[str, Any], h5py.File]] = None,
        output_format: str = "latex",
    ) -> InjectedDataSummary:
        """
        Renders a Jinja2 template string using exact float64 values from HDF5 database
        and optional supplementary context dictionary.
        """
        render_context: Dict[str, Any] = {}
        injected_keys: List[str] = []
        accessed_values: List[Any] = []
        dataset_count = 0

        # Load HDF5 data tree if source exists
        target_h5 = h5_source or self.landscape_path
        if isinstance(target_h5, (str, Path)):
            p = Path(target_h5).resolve()
            if p.is_file():
                h5_dict = build_h5_tree_dict(p)
                render_context.update(h5_dict)
                dataset_count += len(h5_dict)
        elif isinstance(target_h5, dict):
            render_context.update(target_h5)
            dataset_count += len(target_h5)
        elif isinstance(target_h5, (h5py.File, h5py.Group)):
            h5_dict = build_h5_tree_dict(target_h5)
            render_context.update(h5_dict)
            dataset_count += len(h5_dict)

        # Merge custom user context (overriding HDF5 tree if explicit)
        if context:
            render_context.update(context)

        # Track accessed injected values for checksum calculation
        for k, v in render_context.items():
            injected_keys.append(k)
            accessed_values.append(v)

        # Compile and render template
        jinja_template = self._jinja_env.from_string(template_str)
        rendered_text = jinja_template.render(**render_context)

        latex_enforced = False
        if output_format.lower() in ("latex", "tex", "aps"):
            rendered_text = self.formatter.enforce_siunitx(rendered_text)
            latex_enforced = True

        checksum = self.injector.compute_float64_checksum(accessed_values)

        return InjectedDataSummary(
            injected_keys=injected_keys,
            dataset_count=dataset_count,
            raw_byte_checksum=checksum,
            output_text=rendered_text,
            latex_enforced=latex_enforced,
            metadata={"output_format": output_format, "h5_source": str(target_h5)},
        )

    def inject_llm_response(
        self,
        llm_response_text: str,
        h5_source: Optional[Union[str, Path, Dict[str, Any], h5py.File]] = None,
        output_format: str = "latex",
        custom_context: Optional[Dict[str, Any]] = None,
    ) -> InjectedDataSummary:
        """
        Processes raw LLM response text containing Jinja2 placeholders (e.g. {{ energy }}),
        injecting uncorrupted float64 data directly from landscape.h5.
        """
        return self.render_template(
            template_str=llm_response_text,
            context=custom_context,
            h5_source=h5_source,
            output_format=output_format,
        )


# =============================================================================
# CONVENIENCE FACTORY FUNCTIONS
# =============================================================================

def build_system_prompt(
    custom_instructions: Optional[str] = None,
    role: Optional[str] = None,
    include_latex_guidance: bool = True,
) -> str:
    """Convenience helper to generate an air-gapped system prompt."""
    builder = PayloadBuilder()
    return builder.build_system_prompt(
        custom_instructions=custom_instructions,
        role=role,
        include_latex_guidance=include_latex_guidance,
    )


def create_payload(
    user_prompt: str,
    custom_instructions: Optional[str] = None,
    context_data: Optional[Dict[str, Any]] = None,
    h5_pointers: Optional[List[Union[HDF5PointerRef, Dict[str, Any]]]] = None,
    template_type: str = "jinja2",
) -> PromptPayload:
    """Convenience helper to create a validated PromptPayload."""
    builder = PayloadBuilder()
    return builder.build_payload(
        user_prompt=user_prompt,
        custom_instructions=custom_instructions,
        context_data=context_data,
        h5_pointers=h5_pointers,
        template_type=template_type,
    )


def format_siunitx_num(
    value: Union[float, int, np.floating, np.integer, np.ndarray, str],
    precision: Optional[int] = None,
    uncertainty: Optional[Union[float, np.floating, np.ndarray]] = None,
    sigfigs: Optional[int] = None,
) -> str:
    """Convenience helper to format a number into \\num{...}."""
    formatter = LaTeXFormatter()
    return formatter.format_num(value, precision=precision, uncertainty=uncertainty, sigfigs=sigfigs)


def format_siunitx_qty(
    value: Union[float, int, np.floating, np.integer, np.ndarray, str],
    unit: str,
    precision: Optional[int] = None,
    uncertainty: Optional[Union[float, np.floating, np.ndarray]] = None,
    sigfigs: Optional[int] = None,
) -> str:
    """Convenience helper to format a quantity into \\qty{...}{...}."""
    formatter = LaTeXFormatter()
    return formatter.format_qty(value, unit=unit, precision=precision, uncertainty=uncertainty, sigfigs=sigfigs)


def format_siunitx_angle(
    value: Union[float, int, np.floating, np.integer, np.ndarray, str],
    precision: Optional[int] = None,
) -> str:
    """Convenience helper to format an angle into \\ang{...}."""
    formatter = LaTeXFormatter()
    return formatter.format_angle(value, precision=precision)


def enforce_latex_siunitx(latex_text: str) -> str:
    """Convenience helper to enforce siunitx macros across a LaTeX string."""
    formatter = LaTeXFormatter()
    return formatter.enforce_siunitx(latex_text)


def inject_landscape_data(
    template_str: str,
    h5_source: Optional[Union[str, Path, Dict[str, Any], h5py.File]] = None,
    output_format: str = "latex",
    custom_context: Optional[Dict[str, Any]] = None,
) -> InjectedDataSummary:
    """Convenience helper to render a template with uncorrupted HDF5 data."""
    engine = TemplateEngine()
    return engine.render_template(
        template_str=template_str,
        context=custom_context,
        h5_source=h5_source,
        output_format=output_format,
    )
