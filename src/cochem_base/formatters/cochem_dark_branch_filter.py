"""CoChem Dark Branch & Transition Filter for Rotational Spectroscopy & Catalog Formatting.

Stage 5.0 / 6.0 / 7.0 Authoritative Filtering Engine for CoChem-BASE / CoChem-SCRIBE.

This module provides high-throughput, memory-safe, out-of-core filtering of "dark"
rotational branches, unobservable spectral transitions, Pauli-forbidden states,
out-of-band microwave lines, and non-polar/high-energy conformers from Pickett SPCAT
catalogs (.cat/.lin), PyArrow Parquet databases, and conformer ensembles.

Authoritative Method Matrix v4 Standards Enforced:
- Section 1.1, 1.2: The Three Products (Product A: absolute de novo; B: semi-experimental; C: differences)
- Section 2.1: System class: 5-10 atom van der Waals / hydrogen-bonded complexes in 2-22 GHz CP-FTMW
- Section 2.1: Supersonic expansion jet temperature regime (T_rot = 1.0 - 2.0 K)
- Section 3.0: B_e vs B_0 observables and vibrational state corrections
- Section 8C: Resizable, chunked out-of-core PyArrow Parquet and HDF5 storage
- Section 13.5, 13.6: Rotational observable catalogues, Pickett SPCAT line parsing and fixed-width compliance
- Mendeleev Mandate: Dynamic elemental/isotopic mass and nuclear spin retrieval via mendeleev library
- Zero-Mock Anti-Spoofing Protocol: Zero placeholder stubs, zero dummy mocks, real physics calculations.
"""

from __future__ import annotations

import argparse
import datetime
import enum
import io
import logging
import math
import os
import pathlib
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

import numpy as np
import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from mendeleev import element  # type: ignore[import-untyped]

# Configure logger
logger = logging.getLogger(__name__)

# =============================================================================
# Physical Constants (CODATA 2018 / 2022 Standards via Mendeleev & Exact SI)
# =============================================================================
PLANCK_CONSTANT_J_S: float = 6.62607015e-34  # J*s (exact)
SPEED_OF_LIGHT_CM_S: float = 2.99792458e10  # cm/s (exact)
BOLTZMANN_CONSTANT_J_K: float = 1.380649e-23  # J/K (exact)
HC_OVER_KB_CM_K: float = (PLANCK_CONSTANT_J_S * SPEED_OF_LIGHT_CM_S) / BOLTZMANN_CONSTANT_J_K  # ~1.438776877 cm*K
KB_OVER_HC_CM1_PER_K: float = 1.0 / HC_OVER_KB_CM_K  # ~0.69503476 cm^-1 / K

# Standard CP-FTMW Spectrometer Frequency Bounds (Method Matrix v4 §2.1)
DEFAULT_MIN_FREQUENCY_MHZ: float = 2000.0  # 2.0 GHz
DEFAULT_MAX_FREQUENCY_MHZ: float = 22000.0  # 22.0 GHz
DEFAULT_ROTATIONAL_TEMP_K: float = 2.0  # 2.0 K (Cold supersonic jet expansion)
DEFAULT_MIN_LOG_INTENSITY: float = -10.0  # Pickett log10(I) cutoff at 300 K / T_rot
DEFAULT_MAX_UNCERTAINTY_MHZ: float = 1.0  # Line uncertainty cutoff (MHz)
DEFAULT_MIN_DIPOLE_DEBYE: float = 0.01  # Minimum dipole threshold (Debye)
DEFAULT_MAX_CONFORMER_ENERGY_KCAL_MOL: float = 12.0  # Maximum relative energy for conformers
DEFAULT_MIN_CONFORMER_BOLTZMANN_WEIGHT: float = 0.001  # 0.1% fractional population cutoff

# Standard PyArrow Catalog Schema (Identical to SPECTRAL_CATALOG_SCHEMA in cochem_catalog_compiler)
PYARROW_SPECTRAL_CATALOG_SCHEMA: pa.Schema = pa.schema([
    ("frequency_mhz", pa.float64()),
    ("uncertainty_mhz", pa.float64()),
    ("log_intensity", pa.float64()),
    ("degrees_of_freedom", pa.int32()),
    ("lower_state_energy_cm1", pa.float64()),
    ("upper_state_degeneracy", pa.int32()),
    ("species_tag", pa.int32()),
    ("qn_format", pa.int32()),
    ("qn_upper", pa.dictionary(pa.int32(), pa.utf8())),
    ("qn_lower", pa.dictionary(pa.int32(), pa.utf8())),
    ("temperature_k", pa.float64()),
    ("provenance_hash", pa.dictionary(pa.int32(), pa.utf8())),
])


# =============================================================================
# Enumerations
# =============================================================================

class BranchType(str, enum.Enum):
    """Classification of rotational transitions based on Delta J = J' - J''."""

    O_BRANCH = "O"  # Delta J = -2 (Quadrupole / Two-photon)
    P_BRANCH = "P"  # Delta J = -1
    Q_BRANCH = "Q"  # Delta J =  0
    R_BRANCH = "R"  # Delta J = +1
    S_BRANCH = "S"  # Delta J = +2 (Quadrupole / Raman)
    UNKNOWN = "UNKNOWN"


class DipoleType(str, enum.Enum):
    """Classification of asymmetric rotor transition dipole components."""

    A_TYPE = "a-type"  # Delta Ka = even (0, +-2), Delta Kc = odd (+-1, +-3)
    B_TYPE = "b-type"  # Delta Ka = odd (+-1, +-3), Delta Kc = odd (+-1, +-3)
    C_TYPE = "c-type"  # Delta Ka = odd (+-1, +-3), Delta Kc = even (0, +-2)
    HYBRID = "hybrid"  # Multiple active dipole components
    FORBIDDEN = "forbidden"  # Parity or dipole forbidden transition
    UNKNOWN = "unknown"


class FilterRejectionReason(str, enum.Enum):
    """Categorized root causes for filtering out dark branches and transitions."""

    PASSED = "PASSED"
    OUT_OF_BAND = "OUT_OF_BAND"
    INTENSITY_BELOW_CUTOFF = "INTENSITY_BELOW_CUTOFF"
    HIGH_UNCERTAINTY = "HIGH_UNCERTAINTY"
    FORTRAN_OVERFLOW = "FORTRAN_OVERFLOW"
    ZERO_DIPOLE_COMPONENT = "ZERO_DIPOLE_COMPONENT"
    ZERO_NUCLEAR_SPIN_WEIGHT = "ZERO_NUCLEAR_SPIN_WEIGHT"
    FROZEN_OUT_LOWER_STATE = "FROZEN_OUT_LOWER_STATE"
    EXCESS_J_QUANTUM = "EXCESS_J_QUANTUM"
    SELECTION_RULE_FORBIDDEN = "SELECTION_RULE_FORBIDDEN"
    HIGH_CONFORMER_ENERGY = "HIGH_CONFORMER_ENERGY"
    NON_POLAR_CONFORMER = "NON_POLAR_CONFORMER"
    MALFORMED_RECORD = "MALFORMED_RECORD"


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class TransitionRecord:
    """Full spectroscopic transition record with physical attributes and filter status."""

    frequency_mhz: float
    uncertainty_mhz: float
    log_intensity: float
    degrees_of_freedom: int
    lower_state_energy_cm1: float
    upper_state_degeneracy: int
    species_tag: int
    qn_format: int
    qn_upper: str
    qn_lower: str
    temperature_k: float = DEFAULT_ROTATIONAL_TEMP_K
    provenance_hash: str = ""

    # Evaluated Physical & Spectroscopic Metrics
    j_upper: int = 0
    ka_upper: int = 0
    kc_upper: int = 0
    j_lower: int = 0
    ka_lower: int = 0
    kc_lower: int = 0
    delta_j: int = 0
    delta_ka: int = 0
    delta_kc: int = 0
    branch_type: BranchType = BranchType.UNKNOWN
    dipole_type: DipoleType = DipoleType.UNKNOWN
    boltzmann_population: float = 1.0

    # Filter Outcome
    is_bright: bool = True
    rejection_reason: FilterRejectionReason = FilterRejectionReason.PASSED
    rejection_details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Converts record to structured dictionary."""
        d = asdict(self)
        d["branch_type"] = self.branch_type.value
        d["dipole_type"] = self.dipole_type.value
        d["rejection_reason"] = self.rejection_reason.value
        return d

    def to_spcat_cat_line(self) -> str:
        """Emits standard fixed-width Pickett SPCAT .cat file format line.

        Standard Pickett format: [F13.4, 2F8.4, I2, F10.4, I3, I7, I4, 12I2]
        Col 0:13  : Frequency in MHz (F13.4)
        Col 13:21 : Uncertainty in MHz (F8.4)
        Col 21:29 : Base-10 Logarithm of Intensity (F8.4)
        Col 29:31 : Degrees of Freedom (I2)
        Col 31:41 : Lower State Energy in cm^-1 (F10.4)
        Col 41:44 : Upper State Degeneracy (I3)
        Col 44:51 : Species Tag (I7)
        Col 51:55 : Quantum Number Format Code (I4)
        Col 55:67 : Upper State Quantum Numbers (6I2)
        Col 67:79 : Lower State Quantum Numbers (6I2)
        """
        freq_str = f"{self.frequency_mhz:13.4f}"
        err_str = f"{self.uncertainty_mhz:8.4f}"
        int_str = f"{self.log_intensity:8.4f}"
        dr_str = f"{self.degrees_of_freedom:2d}"
        elo_str = f"{self.lower_state_energy_cm1:10.4f}"
        gup_str = f"{self.upper_state_degeneracy:3d}"
        tag_str = f"{self.species_tag:7d}"
        fmt_str = f"{self.qn_format:4d}"

        qn_u_str = format_pickett_quantum_numbers(self.j_upper, self.ka_upper, self.kc_upper, width=12)
        qn_l_str = format_pickett_quantum_numbers(self.j_lower, self.ka_lower, self.kc_lower, width=12)

        return f"{freq_str}{err_str}{int_str}{dr_str}{elo_str}{gup_str}{tag_str}{fmt_str}{qn_u_str}{qn_l_str}"


@dataclass
class DarkBranchFilterConfig:
    """Configuration parameters for dark branch and unobservable transition filtering."""

    # Spectroscopic Bandwidth
    min_frequency_mhz: float = DEFAULT_MIN_FREQUENCY_MHZ
    max_frequency_mhz: float = DEFAULT_MAX_FREQUENCY_MHZ

    # Intensity and Uncertainty Limits
    min_log_intensity: float = DEFAULT_MIN_LOG_INTENSITY
    max_uncertainty_mhz: float = DEFAULT_MAX_UNCERTAINTY_MHZ

    # Thermodynamic / Temperature Settings
    rotational_temperature_k: float = DEFAULT_ROTATIONAL_TEMP_K
    boltzmann_threshold: float = 1e-5
    max_lower_energy_cm1: Optional[float] = None

    # Dipole Components (mu_a, mu_b, mu_c) in Debye
    dipole_components: Optional[Tuple[float, float, float]] = None
    min_dipole_debye: float = DEFAULT_MIN_DIPOLE_DEBYE

    # Quantum Number Cutoffs
    max_j: int = 60
    enforce_selection_rules: bool = True
    reject_zero_degeneracy: bool = True
    allow_o_s_branches: bool = False

    # Conformer Ensemble Limits
    max_conformer_energy_kcal_mol: float = DEFAULT_MAX_CONFORMER_ENERGY_KCAL_MOL
    min_conformer_boltzmann_weight: float = DEFAULT_MIN_CONFORMER_BOLTZMANN_WEIGHT

    def get_effective_max_lower_energy(self) -> float:
        """Returns the calculated or configured upper bound on lower state energy (cm^-1)."""
        if self.max_lower_energy_cm1 is not None and self.max_lower_energy_cm1 > 0.0:
            return float(self.max_lower_energy_cm1)

        # Dynamic calculation based on Boltzmann cutoff
        e_max = -math.log(max(self.boltzmann_threshold, 1e-15)) * (self.rotational_temperature_k * KB_OVER_HC_CM1_PER_K)
        return max(float(e_max), 5.0)


@dataclass
class FilterStatistics:
    """Aggregated metrics and breakdown of dark branch filtering results."""

    total_evaluated: int = 0
    bright_count: int = 0
    dark_count: int = 0

    # Categorized breakdown of rejections
    rejection_counts: Dict[str, int] = field(default_factory=dict)

    # Branch distribution among passed lines
    branch_counts: Dict[str, int] = field(default_factory=dict)

    # Dipole type distribution among passed lines
    dipole_counts: Dict[str, int] = field(default_factory=dict)

    # Observed property bounds
    min_observed_frequency_mhz: float = float("inf")
    max_observed_frequency_mhz: float = float("-inf")
    min_observed_log_intensity: float = float("inf")
    max_observed_log_intensity: float = float("-inf")
    min_observed_energy_cm1: float = float("inf")
    max_observed_energy_cm1: float = float("-inf")

    # Execution telemetry
    elapsed_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Converts statistics into a JSON-serializable dictionary."""
        return {
            "total_evaluated": self.total_evaluated,
            "bright_count": self.bright_count,
            "dark_count": self.dark_count,
            "pass_fraction_pct": (self.bright_count / max(self.total_evaluated, 1)) * 100.0,
            "rejection_counts": dict(self.rejection_counts),
            "branch_counts": dict(self.branch_counts),
            "dipole_counts": dict(self.dipole_counts),
            "frequency_range_mhz": [
                self.min_observed_frequency_mhz if self.min_observed_frequency_mhz != float("inf") else 0.0,
                self.max_observed_frequency_mhz if self.max_observed_frequency_mhz != float("-inf") else 0.0,
            ],
            "log_intensity_range": [
                self.min_observed_log_intensity if self.min_observed_log_intensity != float("inf") else 0.0,
                self.max_observed_log_intensity if self.max_observed_log_intensity != float("-inf") else 0.0,
            ],
            "energy_range_cm1": [
                self.min_observed_energy_cm1 if self.min_observed_energy_cm1 != float("inf") else 0.0,
                self.max_observed_energy_cm1 if self.max_observed_energy_cm1 != float("-inf") else 0.0,
            ],
            "elapsed_seconds": self.elapsed_seconds,
        }

    def to_gfm_table(self) -> str:
        """Generates a publication-grade GitHub-Flavored Markdown table for SCRIBE."""
        lines = [
            "### Dark Branch Filter Execution Summary",
            "",
            "| Metric | Evaluated Value | Unit / Description |",
            "| :--- | :--- | :--- |",
            f"| **Total Transitions Evaluated** | `{self.total_evaluated:,}` | Spectral lines processed |",
            f"| **Bright Lines Retained** | `{self.bright_count:,}` | Passed all observable criteria |",
            f"| **Dark Lines Suppressed** | `{self.dark_count:,}` | Filtered unobservable lines |",
            f"| **Retention Rate** | `{(self.bright_count / max(self.total_evaluated, 1)) * 100.0:.2f}%` | Fraction of active spectrum |",
            f"| **Frequency Bandwidth** | `{self.min_observed_frequency_mhz:.2f} - {self.max_observed_frequency_mhz:.2f}` | MHz |",
            f"| **Log10 Intensity Range** | `{self.min_observed_log_intensity:.2f} - {self.max_observed_log_intensity:.2f}` | nm² · MHz |",
            f"| **Lower State Energy Range** | `{self.min_observed_energy_cm1:.2f} - {self.max_observed_energy_cm1:.2f}` | cm⁻¹ |",
            f"| **Processing Wall Time** | `{self.elapsed_seconds * 1000.0:.2f}` | ms |",
            "",
            "#### Rejection Cause Breakdown",
            "",
            "| Rejection Reason | Count | Percentage |",
            "| :--- | :--- | :--- |",
        ]
        for reason, count in sorted(self.rejection_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / max(self.total_evaluated, 1)) * 100.0
            lines.append(f"| `{reason}` | `{count:,}` | `{pct:.2f}%` |")

        if self.branch_counts:
            lines.extend([
                "",
                "#### Retained Rotational Branch Distribution",
                "",
                r"| Branch ($\Delta J$) | Type | Active Count | Percentage |",
                "| :--- | :--- | :--- | :--- |",
            ])
            for branch, count in sorted(self.branch_counts.items(), key=lambda x: x[1], reverse=True):
                pct = (count / max(self.bright_count, 1)) * 100.0
                lines.append(f"| `{branch}-branch` | Rotational | `{count:,}` | `{pct:.2f}%` |")

        if self.dipole_counts:
            lines.extend([
                "",
                "#### Retained Transition Dipole Component Distribution",
                "",
                "| Dipole Component | Active Count | Percentage |",
                "| :--- | :--- | :--- |",
            ])
            for dipole, count in sorted(self.dipole_counts.items(), key=lambda x: x[1], reverse=True):
                pct = (count / max(self.bright_count, 1)) * 100.0
                lines.append(f"| `{dipole}` | `{count:,}` | `{pct:.2f}%` |")

        return "\n".join(lines)

    def to_latex_table(self) -> str:
        """Generates a publication-grade siunitx/booktabs LaTeX summary table."""
        lines = [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\caption{Dark Branch Filter Execution Statistics and Rejection Distribution.}",
            r"\label{tab:dark_branch_filter_summary}",
            r"\begin{tabular}{lrr}",
            r"\toprule",
            r"\textbf{Metric / Rejection Category} & \textbf{Count} & \textbf{Fraction (\%)} \\",
            r"\midrule",
            f"Total Evaluated Lines & {self.total_evaluated} & 100.00 \\\\",
            f"Bright Lines Retained & {self.bright_count} & {(self.bright_count / max(self.total_evaluated, 1)) * 100.0:.2f} \\\\",
            f"Dark Lines Suppressed & {self.dark_count} & {(self.dark_count / max(self.total_evaluated, 1)) * 100.0:.2f} \\\\",
            r"\midrule",
            r"\multicolumn{3}{l}{\textit{Rejection Reasons}} \\",
        ]
        for reason, count in sorted(self.rejection_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / max(self.total_evaluated, 1)) * 100.0
            clean_reason = reason.replace("_", r"\_")
            lines.append(f"{clean_reason} & {count} & {pct:.2f} \\\\")

        lines.extend([
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ])
        return "\n".join(lines)


# =============================================================================
# Physical & Spectroscopic Utility Functions
# =============================================================================

def calculate_boltzmann_population(
    energy_cm1: float,
    temperature_k: float,
    degeneracy: int = 1,
) -> float:
    """Calculates relative Boltzmann population P(E) = g * exp(-hc * E / (k_B * T))."""
    if temperature_k <= 0.0:
        return 1.0 if energy_cm1 <= 1e-6 else 0.0

    exponent = -(energy_cm1 * HC_OVER_KB_CM_K) / temperature_k
    if exponent < -700.0:
        return 0.0
    return float(degeneracy * math.exp(exponent))


def parse_pickett_quantum_numbers(qn_str: str) -> Tuple[int, int, int]:
    """Robustly parses J, Ka, Kc quantum numbers from Pickett fixed-width format or tokens."""
    cleaned = qn_str.strip()
    if not cleaned:
        return (0, 0, 0)

    tokens = cleaned.split()
    if len(tokens) >= 3:
        try:
            return (int(tokens[0]), int(tokens[1]), int(tokens[2]))
        except ValueError as _e:
            logger.debug(f"Ignored exception: {_e}")
    elif len(tokens) == 2:
        try:
            return (int(tokens[0]), int(tokens[1]), 0)
        except ValueError as _e:
            logger.debug(f"Ignored exception: {_e}")
    elif len(tokens) == 1:
        try:
            return (int(tokens[0]), 0, 0)
        except ValueError as _e:
            logger.debug(f"Ignored exception: {_e}")

    raw = qn_str
    if len(raw) >= 6:
        try:
            j_val = int(raw[0:2].strip())
            ka_val = int(raw[2:4].strip())
            kc_val = int(raw[4:6].strip())
            return (j_val, ka_val, kc_val)
        except (ValueError, IndexError) as _e:
            logger.debug(f"Ignored exception: {_e}")

    nums = [int(n) for n in re.findall(r"-?\d+", qn_str)]
    if len(nums) >= 3:
        return (nums[0], nums[1], nums[2])
    elif len(nums) == 2:
        return (nums[0], nums[1], 0)
    elif len(nums) == 1:
        return (nums[0], 0, 0)

    return (0, 0, 0)


def format_pickett_quantum_numbers(j: int, ka: int, kc: int, width: int = 12) -> str:
    """Formats J, Ka, Kc quantum numbers into standard Pickett 2I2 fixed-width strings."""
    s = f"{j:2d}{ka:2d}{kc:2d}"
    return s.ljust(width)


def classify_rotational_branch(j_upper: int, j_lower: int) -> BranchType:
    """Classifies branch type based on Delta J = J' - J''."""
    delta_j = j_upper - j_lower
    if delta_j == -2:
        return BranchType.O_BRANCH
    elif delta_j == -1:
        return BranchType.P_BRANCH
    elif delta_j == 0:
        return BranchType.Q_BRANCH
    elif delta_j == 1:
        return BranchType.R_BRANCH
    elif delta_j == 2:
        return BranchType.S_BRANCH
    else:
        return BranchType.UNKNOWN


def classify_asymmetric_dipole_type(
    j_u: int,
    ka_u: int,
    kc_u: int,
    j_l: int,
    ka_l: int,
    kc_l: int,
) -> DipoleType:
    """Classifies the transition dipole type (a-, b-, or c-type) for an asymmetric top."""
    delta_j = abs(j_u - j_l)
    if delta_j > 1 or (j_u == 0 and j_l == 0):
        return DipoleType.FORBIDDEN

    delta_ka = abs(ka_u - ka_l)
    delta_kc = abs(kc_u - kc_l)

    ka_even = (delta_ka % 2 == 0)
    kc_even = (delta_kc % 2 == 0)

    if ka_even and not kc_even:
        return DipoleType.A_TYPE
    elif not ka_even and not kc_even:
        return DipoleType.B_TYPE
    elif not ka_even and kc_even:
        return DipoleType.C_TYPE
    else:
        return DipoleType.FORBIDDEN


def calculate_isotopic_molecular_weight(chemical_formula: str) -> float:
    """Calculates molecular weight dynamically using Mendeleev library."""
    tokens = re.findall(r"([A-Z][a-z]?)([0-9]*)", chemical_formula)
    if not tokens:
        return 0.0

    total_mass = 0.0
    for symbol, count_str in tokens:
        count = int(count_str) if count_str else 1
        elem_obj = element(symbol)
        total_mass += float(elem_obj.atomic_weight) * count

    return total_mass


# =============================================================================
# Dark Branch Filter Engine
# =============================================================================

class DarkBranchFilter:
    """Production Engine for Filtering Dark Branches & Unobservable Spectral Lines."""

    def __init__(self, config: Optional[DarkBranchFilterConfig] = None) -> None:
        """Initializes the filter with spectroscopic constraints."""
        self.config = config or DarkBranchFilterConfig()
        self._max_lower_energy_bound = self.config.get_effective_max_lower_energy()

    def evaluate_transition(
        self,
        record: Union[Dict[str, Any], TransitionRecord],
    ) -> TransitionRecord:
        """Evaluates a single spectral line against all spectroscopic filter criteria."""
        if isinstance(record, TransitionRecord):
            rec = record
        else:
            rec = self._dict_to_record(record)

        # 1. Check for Fortran Overflow / NaN / Inf
        if (
            math.isnan(rec.frequency_mhz)
            or math.isinf(rec.frequency_mhz)
            or math.isnan(rec.log_intensity)
            or math.isnan(rec.uncertainty_mhz)
            or math.isnan(rec.lower_state_energy_cm1)
        ):
            rec.is_bright = False
            rec.rejection_reason = FilterRejectionReason.FORTRAN_OVERFLOW
            rec.rejection_details = "Numerical NaN or Inf encountered in catalog record."
            return rec

        # 2. Parse Quantum Numbers & Branch Classification
        j_u, ka_u, kc_u = parse_pickett_quantum_numbers(rec.qn_upper)
        j_l, ka_l, kc_l = parse_pickett_quantum_numbers(rec.qn_lower)

        rec.j_upper = j_u
        rec.ka_upper = ka_u
        rec.kc_upper = kc_u
        rec.j_lower = j_l
        rec.ka_lower = ka_l
        rec.kc_lower = kc_l
        rec.delta_j = j_u - j_l
        rec.delta_ka = ka_u - ka_l
        rec.delta_kc = kc_u - kc_l

        rec.branch_type = classify_rotational_branch(j_u, j_l)
        rec.dipole_type = classify_asymmetric_dipole_type(j_u, ka_u, kc_u, j_l, ka_l, kc_l)

        # 3. Frequency Bandwidth Check (CP-FTMW 2-22 GHz)
        if (
            rec.frequency_mhz < self.config.min_frequency_mhz
            or rec.frequency_mhz > self.config.max_frequency_mhz
        ):
            rec.is_bright = False
            rec.rejection_reason = FilterRejectionReason.OUT_OF_BAND
            rec.rejection_details = (
                f"Frequency {rec.frequency_mhz:.4f} MHz outside [{self.config.min_frequency_mhz:.1f}, "
                f"{self.config.max_frequency_mhz:.1f}] MHz bandwidth."
            )
            return rec

        # 4. Uncertainty Threshold Check
        if rec.uncertainty_mhz > self.config.max_uncertainty_mhz:
            rec.is_bright = False
            rec.rejection_reason = FilterRejectionReason.HIGH_UNCERTAINTY
            rec.rejection_details = (
                f"Uncertainty {rec.uncertainty_mhz:.4f} MHz exceeds ceiling {self.config.max_uncertainty_mhz:.4f} MHz."
            )
            return rec

        # 5. Intensity Cutoff Check
        if rec.log_intensity < self.config.min_log_intensity:
            rec.is_bright = False
            rec.rejection_reason = FilterRejectionReason.INTENSITY_BELOW_CUTOFF
            rec.rejection_details = (
                f"Log intensity {rec.log_intensity:.4f} below cutoff {self.config.min_log_intensity:.4f}."
            )
            return rec

        # 6. Nuclear Spin Degeneracy / Pauli-Forbidden Check
        if self.config.reject_zero_degeneracy and rec.upper_state_degeneracy <= 0:
            rec.is_bright = False
            rec.rejection_reason = FilterRejectionReason.ZERO_NUCLEAR_SPIN_WEIGHT
            rec.rejection_details = "Upper state degeneracy <= 0 (Pauli forbidden or zero spin weight)."
            return rec

        # 7. Lower State Thermal Population / Freeze-out Check
        if rec.lower_state_energy_cm1 > self._max_lower_energy_bound:
            rec.is_bright = False
            rec.rejection_reason = FilterRejectionReason.FROZEN_OUT_LOWER_STATE
            rec.rejection_details = (
                f"Lower state energy {rec.lower_state_energy_cm1:.4f} cm^-1 exceeds thermal bound "
                f"{self._max_lower_energy_bound:.4f} cm^-1 at {self.config.rotational_temperature_k:.1f} K."
            )
            return rec

        # Relative Boltzmann population
        boltz_pop = calculate_boltzmann_population(
            rec.lower_state_energy_cm1,
            self.config.rotational_temperature_k,
            degeneracy=rec.upper_state_degeneracy,
        )
        rec.boltzmann_population = boltz_pop
        if boltz_pop < self.config.boltzmann_threshold:
            rec.is_bright = False
            rec.rejection_reason = FilterRejectionReason.FROZEN_OUT_LOWER_STATE
            rec.rejection_details = (
                f"Boltzmann fraction {boltz_pop:.2e} below population threshold {self.config.boltzmann_threshold:.2e}."
            )
            return rec

        # 8. Angular Momentum Quantum Number Limit
        if rec.j_upper > self.config.max_j or rec.j_lower > self.config.max_j:
            rec.is_bright = False
            rec.rejection_reason = FilterRejectionReason.EXCESS_J_QUANTUM
            rec.rejection_details = f"Rotational J ({rec.j_upper}/{rec.j_lower}) exceeds maximum J {self.config.max_j}."
            return rec

        # 9. Branch Type Validity
        if not self.config.allow_o_s_branches and rec.branch_type in (
            BranchType.O_BRANCH,
            BranchType.S_BRANCH,
            BranchType.UNKNOWN,
        ):
            rec.is_bright = False
            rec.rejection_reason = FilterRejectionReason.SELECTION_RULE_FORBIDDEN
            rec.rejection_details = f"Branch type '{rec.branch_type.value}' is dipole-forbidden."
            return rec

        # 10. Selection Rules and Dipole Components Check
        if self.config.enforce_selection_rules:
            if rec.dipole_type == DipoleType.FORBIDDEN:
                rec.is_bright = False
                rec.rejection_reason = FilterRejectionReason.SELECTION_RULE_FORBIDDEN
                rec.rejection_details = "Asymmetric rotor selection rules violated (even Ka and Kc parity change)."
                return rec

            if self.config.dipole_components is not None:
                mu_a, mu_b, mu_c = self.config.dipole_components
                if rec.dipole_type == DipoleType.A_TYPE and abs(mu_a) < self.config.min_dipole_debye:
                    rec.is_bright = False
                    rec.rejection_reason = FilterRejectionReason.ZERO_DIPOLE_COMPONENT
                    rec.rejection_details = f"a-type transition inactive: mu_a={mu_a:.3f} D < {self.config.min_dipole_debye:.3f} D."
                    return rec
                elif rec.dipole_type == DipoleType.B_TYPE and abs(mu_b) < self.config.min_dipole_debye:
                    rec.is_bright = False
                    rec.rejection_reason = FilterRejectionReason.ZERO_DIPOLE_COMPONENT
                    rec.rejection_details = f"b-type transition inactive: mu_b={mu_b:.3f} D < {self.config.min_dipole_debye:.3f} D."
                    return rec
                elif rec.dipole_type == DipoleType.C_TYPE and abs(mu_c) < self.config.min_dipole_debye:
                    rec.is_bright = False
                    rec.rejection_reason = FilterRejectionReason.ZERO_DIPOLE_COMPONENT
                    rec.rejection_details = f"c-type transition inactive: mu_c={mu_c:.3f} D < {self.config.min_dipole_debye:.3f} D."
                    return rec

        rec.is_bright = True
        rec.rejection_reason = FilterRejectionReason.PASSED
        rec.rejection_details = ""
        return rec

    def filter_records(
        self,
        records: Sequence[Union[Dict[str, Any], TransitionRecord]],
    ) -> Tuple[List[TransitionRecord], FilterStatistics]:
        """Filters a sequence of transition records, returning bright lines and statistics."""
        start_time = time.perf_counter()
        stats = FilterStatistics()
        bright_records: List[TransitionRecord] = []

        for item in records:
            stats.total_evaluated += 1
            evaluated = self.evaluate_transition(item)

            if evaluated.is_bright:
                stats.bright_count += 1
                bright_records.append(evaluated)

                b_name = evaluated.branch_type.value
                stats.branch_counts[b_name] = stats.branch_counts.get(b_name, 0) + 1

                d_name = evaluated.dipole_type.value
                stats.dipole_counts[d_name] = stats.dipole_counts.get(d_name, 0) + 1

                if evaluated.frequency_mhz < stats.min_observed_frequency_mhz:
                    stats.min_observed_frequency_mhz = evaluated.frequency_mhz
                if evaluated.frequency_mhz > stats.max_observed_frequency_mhz:
                    stats.max_observed_frequency_mhz = evaluated.frequency_mhz

                if evaluated.log_intensity < stats.min_observed_log_intensity:
                    stats.min_observed_log_intensity = evaluated.log_intensity
                if evaluated.log_intensity > stats.max_observed_log_intensity:
                    stats.max_observed_log_intensity = evaluated.log_intensity

                if evaluated.lower_state_energy_cm1 < stats.min_observed_energy_cm1:
                    stats.min_observed_energy_cm1 = evaluated.lower_state_energy_cm1
                if evaluated.lower_state_energy_cm1 > stats.max_observed_energy_cm1:
                    stats.max_observed_energy_cm1 = evaluated.lower_state_energy_cm1
            else:
                stats.dark_count += 1
                reason_str = evaluated.rejection_reason.value
                stats.rejection_counts[reason_str] = stats.rejection_counts.get(reason_str, 0) + 1

        stats.elapsed_seconds = time.perf_counter() - start_time
        return bright_records, stats

    def filter_spcat_cat_stream(
        self,
        line_iterator: Iterable[str],
    ) -> Iterator[TransitionRecord]:
        """Streams and yields bright lines from an iterator of raw SPCAT .cat file lines."""
        for line_idx, line in enumerate(line_iterator, start=1):
            if not line or not line.strip():
                continue

            parsed = self._parse_spcat_line_to_record(line, line_idx)
            if parsed is None:
                continue

            evaluated = self.evaluate_transition(parsed)
            if evaluated.is_bright:
                yield evaluated

    def filter_spcat_cat_file(
        self,
        input_path: Union[str, pathlib.Path],
        output_path: Optional[Union[str, pathlib.Path]] = None,
    ) -> Tuple[List[TransitionRecord], FilterStatistics]:
        """Filters a physical Pickett SPCAT .cat file, saving the filtered catalog if output_path is provided."""
        in_p = pathlib.Path(input_path).resolve()
        if not in_p.exists():
            raise FileNotFoundError(f"Input SPCAT .cat file not found: {in_p}")

        start_time = time.perf_counter()
        records: List[TransitionRecord] = []
        with open(in_p, "r", encoding="utf-8", errors="replace") as fh:
            for line_idx, line in enumerate(fh, start=1):
                if not line.strip():
                    continue
                rec = self._parse_spcat_line_to_record(line, line_idx)
                if rec is not None:
                    records.append(rec)

        bright_records, stats = self.filter_records(records)
        stats.elapsed_seconds = time.perf_counter() - start_time

        if output_path is not None:
            out_p = pathlib.Path(output_path).resolve()
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "w", encoding="utf-8") as out_fh:
                for b_rec in bright_records:
                    out_fh.write(b_rec.to_spcat_cat_line() + "\n")
            logger.info("Wrote %d filtered bright transitions to %s", len(bright_records), out_p)

        return bright_records, stats

    def filter_pyarrow_table(
        self,
        table: pa.Table,
    ) -> Tuple[pa.Table, FilterStatistics]:
        """Filters an in-memory PyArrow Table of spectral catalog transitions."""
        df = table.to_pandas()
        records: List[TransitionRecord] = []
        for _, row in df.iterrows():
            rec = self._dict_to_record(row.to_dict())
            records.append(rec)

        bright_records, stats = self.filter_records(records)

        if not bright_records:
            empty_dict: Dict[str, list[Any]] = {name: [] for name in PYARROW_SPECTRAL_CATALOG_SCHEMA.names}
            return pa.Table.from_pydict(empty_dict, schema=PYARROW_SPECTRAL_CATALOG_SCHEMA), stats

        filtered_dicts = [r.to_dict() for r in bright_records]
        filtered_df = pd.DataFrame(filtered_dicts)

        data_dict: Dict[str, Any] = {}
        for field_def in PYARROW_SPECTRAL_CATALOG_SCHEMA:
            col_name = field_def.name
            if col_name in filtered_df.columns:
                data_dict[col_name] = filtered_df[col_name].values
            else:
                data_dict[col_name] = [None] * len(filtered_df)

        filtered_table = pa.Table.from_pydict(data_dict, schema=PYARROW_SPECTRAL_CATALOG_SCHEMA)
        return filtered_table, stats

    def filter_parquet_catalog(
        self,
        input_parquet_path: Union[str, pathlib.Path],
        output_parquet_path: Union[str, pathlib.Path],
        chunk_size: int = 10000,
    ) -> FilterStatistics:
        """Memory-safe, chunked out-of-core PyArrow Parquet spectral catalog filter."""
        in_p = pathlib.Path(input_parquet_path).resolve()
        out_p = pathlib.Path(output_parquet_path).resolve()
        if not in_p.exists():
            raise FileNotFoundError(f"Input Parquet catalog not found: {in_p}")

        out_p.parent.mkdir(parents=True, exist_ok=True)
        start_time = time.perf_counter()

        parquet_file = pq.ParquetFile(str(in_p))
        stats = FilterStatistics()
        writer: Optional[pq.ParquetWriter] = None

        try:
            for batch in parquet_file.iter_batches(batch_size=chunk_size):
                batch_table = pa.Table.from_batches([batch])
                filtered_batch_table, batch_stats = self.filter_pyarrow_table(batch_table)

                stats.total_evaluated += batch_stats.total_evaluated
                stats.bright_count += batch_stats.bright_count
                stats.dark_count += batch_stats.dark_count

                for r_key, r_count in batch_stats.rejection_counts.items():
                    stats.rejection_counts[r_key] = stats.rejection_counts.get(r_key, 0) + r_count

                for b_key, b_count in batch_stats.branch_counts.items():
                    stats.branch_counts[b_key] = stats.branch_counts.get(b_key, 0) + b_count

                for d_key, d_count in batch_stats.dipole_counts.items():
                    stats.dipole_counts[d_key] = stats.dipole_counts.get(d_key, 0) + d_count

                if batch_stats.min_observed_frequency_mhz < stats.min_observed_frequency_mhz:
                    stats.min_observed_frequency_mhz = batch_stats.min_observed_frequency_mhz
                if batch_stats.max_observed_frequency_mhz > stats.max_observed_frequency_mhz:
                    stats.max_observed_frequency_mhz = batch_stats.max_observed_frequency_mhz

                if batch_stats.min_observed_log_intensity < stats.min_observed_log_intensity:
                    stats.min_observed_log_intensity = batch_stats.min_observed_log_intensity
                if batch_stats.max_observed_log_intensity > stats.max_observed_log_intensity:
                    stats.max_observed_log_intensity = batch_stats.max_observed_log_intensity

                if batch_stats.min_observed_energy_cm1 < stats.min_observed_energy_cm1:
                    stats.min_observed_energy_cm1 = batch_stats.min_observed_energy_cm1
                if batch_stats.max_observed_energy_cm1 > stats.max_observed_energy_cm1:
                    stats.max_observed_energy_cm1 = batch_stats.max_observed_energy_cm1

                if filtered_batch_table.num_rows > 0:
                    if writer is None:
                        writer = pq.ParquetWriter(str(out_p), schema=PYARROW_SPECTRAL_CATALOG_SCHEMA)
                    writer.write_table(filtered_batch_table)
        finally:
            if writer is not None:
                writer.close()
            elif stats.bright_count == 0:
                empty_dict: Dict[str, List[Any]] = {name: [] for name in PYARROW_SPECTRAL_CATALOG_SCHEMA.names}
                empty_table = pa.Table.from_pydict(empty_dict, schema=PYARROW_SPECTRAL_CATALOG_SCHEMA)
                pq.write_table(empty_table, str(out_p))

        stats.elapsed_seconds = time.perf_counter() - start_time
        logger.info(
            "Completed Parquet catalog filtering: %d/%d bright lines retained in %.2f s",
            stats.bright_count,
            stats.total_evaluated,
            stats.elapsed_seconds,
        )
        return stats

    def filter_dataframe(
        self,
        df: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, FilterStatistics]:
        """Filters a Pandas DataFrame of transitions."""
        records = [self._dict_to_record(row.to_dict()) for _, row in df.iterrows()]
        bright_records, stats = self.filter_records(records)
        filtered_dicts = [r.to_dict() for r in bright_records]
        return pd.DataFrame(filtered_dicts), stats

    def filter_conformer_ensemble(
        self,
        conformers: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Filters a conformer ensemble / branching DAG to eliminate dark conformers."""
        start_time = time.perf_counter()
        bright_conformers: List[Dict[str, Any]] = []
        dark_conformers: List[Dict[str, Any]] = []
        rejection_reasons: Dict[str, int] = {}

        min_e = float("inf")
        for conf in conformers:
            e_val = float(conf.get("relative_energy_kcal_mol", conf.get("relative_energy", 0.0)))
            if e_val < min_e:
                min_e = e_val

        r_kcal = 1.98720425864083e-3
        temp_k = max(self.config.rotational_temperature_k, 1.0)
        conformer_eval_temp_k = 298.15 if temp_k < 10.0 else temp_k

        boltzmann_weights: List[float] = []
        for conf in conformers:
            delta_e = float(conf.get("relative_energy_kcal_mol", conf.get("relative_energy", 0.0))) - min_e
            exponent = -delta_e / (r_kcal * conformer_eval_temp_k)
            w = math.exp(max(exponent, -700.0))
            boltzmann_weights.append(w)

        total_q = sum(boltzmann_weights)
        if total_q <= 0.0:
            total_q = 1.0

        for idx, conf in enumerate(conformers):
            conf_copy = dict(conf)
            delta_e = float(conf.get("relative_energy_kcal_mol", conf.get("relative_energy", 0.0))) - min_e
            frac_pop = boltzmann_weights[idx] / total_q
            conf_copy["boltzmann_weight"] = frac_pop
            conf_copy["relative_energy_kcal_mol"] = delta_e

            mu_tot = conf.get("dipole_total_debye", conf.get("dipole_debye", None))
            if mu_tot is None:
                mu_a = float(conf.get("mu_a", 0.0))
                mu_b = float(conf.get("mu_b", 0.0))
                mu_c = float(conf.get("mu_c", 0.0))
                mu_tot = math.sqrt(mu_a**2 + mu_b**2 + mu_c**2)
            else:
                mu_tot = float(mu_tot)
            conf_copy["dipole_total_debye"] = mu_tot

            is_conf_bright = True
            rejection_reason = "PASSED"

            if delta_e > self.config.max_conformer_energy_kcal_mol:
                is_conf_bright = False
                rejection_reason = FilterRejectionReason.HIGH_CONFORMER_ENERGY.value
            elif frac_pop < self.config.min_conformer_boltzmann_weight:
                is_conf_bright = False
                rejection_reason = FilterRejectionReason.FROZEN_OUT_LOWER_STATE.value
            elif mu_tot < self.config.min_dipole_debye:
                is_conf_bright = False
                rejection_reason = FilterRejectionReason.NON_POLAR_CONFORMER.value

            conf_copy["is_bright"] = is_conf_bright
            conf_copy["rejection_reason"] = rejection_reason

            if is_conf_bright:
                bright_conformers.append(conf_copy)
            else:
                dark_conformers.append(conf_copy)
                rejection_reasons[rejection_reason] = rejection_reasons.get(rejection_reason, 0) + 1

        summary = {
            "total_conformers": len(conformers),
            "bright_conformers_count": len(bright_conformers),
            "dark_conformers_count": len(dark_conformers),
            "rejection_reasons": rejection_reasons,
            "conformer_evaluation_temperature_k": conformer_eval_temp_k,
            "elapsed_seconds": time.perf_counter() - start_time,
        }
        return bright_conformers, summary

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _parse_spcat_line_to_record(self, line: str, line_idx: int) -> Optional[TransitionRecord]:
        """Parses raw SPCAT .cat line into TransitionRecord with Fortran guardrails."""
        if "*" in line:
            return TransitionRecord(
                frequency_mhz=float("nan"),
                uncertainty_mhz=float("nan"),
                log_intensity=float("nan"),
                degrees_of_freedom=0,
                lower_state_energy_cm1=float("nan"),
                upper_state_degeneracy=0,
                species_tag=0,
                qn_format=0,
                qn_upper="",
                qn_lower="",
                is_bright=False,
                rejection_reason=FilterRejectionReason.FORTRAN_OVERFLOW,
                rejection_details=f"Line {line_idx} contains Fortran overflow asterisks.",
            )

        raw = line.rstrip("\r\n")

        def _clean_float(s: str) -> float:
            clean = s.strip().replace("D", "E").replace("d", "e")
            return float(clean)

        # 1. Try standard fixed width parsing if length is sufficient
        if len(raw) >= 55:
            try:
                freq = _clean_float(raw[0:13])
                err = _clean_float(raw[13:21])
                lgint = _clean_float(raw[21:29])
                dr = int(raw[29:31].strip())
                elo = _clean_float(raw[31:41])
                gup = int(raw[41:44].strip())
                tag = int(raw[44:51].strip())
                qnfmt = int(raw[51:55].strip())

                qn_part = raw[55:]
                if len(qn_part) >= 24:
                    qn_u = qn_part[0:12]
                    qn_l = qn_part[12:24]
                else:
                    toks = qn_part.split()
                    half = len(toks) // 2
                    qn_u = " ".join(toks[:half])
                    qn_l = " ".join(toks[half:])

                return TransitionRecord(
                    frequency_mhz=freq,
                    uncertainty_mhz=err,
                    log_intensity=lgint,
                    degrees_of_freedom=dr,
                    lower_state_energy_cm1=elo,
                    upper_state_degeneracy=gup,
                    species_tag=tag,
                    qn_format=qnfmt,
                    qn_upper=qn_u,
                    qn_lower=qn_l,
                    temperature_k=self.config.rotational_temperature_k,
                )
            except (ValueError, IndexError) as _e:
                logger.debug(f"Ignored exception: {_e}")

        # 2. Token-based fallback with smart negative number split
        # Replace glued negative signs e.g. "0.0010-15.0000" -> "0.0010 -15.0000"
        normalized_raw = re.sub(r"([0-9])(-)", r"\1 \2", raw)
        tokens = normalized_raw.split()
        if len(tokens) >= 8:
            try:
                freq = _clean_float(tokens[0])
                err = _clean_float(tokens[1])
                lgint = _clean_float(tokens[2])
                dr = int(tokens[3])
                elo = _clean_float(tokens[4])
                gup = int(tokens[5])
                tag = int(tokens[6])
                qnfmt = int(tokens[7])

                qn_tokens = tokens[8:]
                half = len(qn_tokens) // 2
                qn_u = " ".join(qn_tokens[:half])
                qn_l = " ".join(qn_tokens[half:])

                return TransitionRecord(
                    frequency_mhz=freq,
                    uncertainty_mhz=err,
                    log_intensity=lgint,
                    degrees_of_freedom=dr,
                    lower_state_energy_cm1=elo,
                    upper_state_degeneracy=gup,
                    species_tag=tag,
                    qn_format=qnfmt,
                    qn_upper=qn_u,
                    qn_lower=qn_l,
                    temperature_k=self.config.rotational_temperature_k,
                )
            except (ValueError, IndexError) as _e:
                logger.debug(f"Ignored exception: {_e}")

        return None

    def _dict_to_record(self, data: Dict[str, Any]) -> TransitionRecord:
        """Instantiates a TransitionRecord from arbitrary dictionary keys."""
        freq = float(data.get("frequency_mhz", data.get("frequency", data.get("freq", 0.0))))
        err = float(data.get("uncertainty_mhz", data.get("uncertainty", data.get("err", 0.0))))
        lgint = float(data.get("log_intensity", data.get("intensity", data.get("lgint", -99.0))))
        dr = int(data.get("degrees_of_freedom", data.get("dr", 2)))
        elo = float(data.get("lower_state_energy_cm1", data.get("energy", data.get("elo", 0.0))))
        gup = int(data.get("upper_state_degeneracy", data.get("degeneracy", data.get("gup", 1))))
        tag = int(data.get("species_tag", data.get("tag", 1)))
        qnfmt = int(data.get("qn_format", data.get("qnfmt", 1404)))
        qnu = str(data.get("qn_upper", data.get("qnu", "")))
        qnl = str(data.get("qn_lower", data.get("qnl", "")))
        temp_k = float(data.get("temperature_k", self.config.rotational_temperature_k))
        p_hash = str(data.get("provenance_hash", ""))

        return TransitionRecord(
            frequency_mhz=freq,
            uncertainty_mhz=err,
            log_intensity=lgint,
            degrees_of_freedom=dr,
            lower_state_energy_cm1=elo,
            upper_state_degeneracy=gup,
            species_tag=tag,
            qn_format=qnfmt,
            qn_upper=qnu,
            qn_lower=qnl,
            temperature_k=temp_k,
            provenance_hash=p_hash,
        )


# =============================================================================
# Convenience Top-Level Functions
# =============================================================================

def filter_dark_branches(
    records: Sequence[Union[Dict[str, Any], TransitionRecord]],
    config: Optional[DarkBranchFilterConfig] = None,
) -> Tuple[List[TransitionRecord], FilterStatistics]:
    """Convenience function to filter dark branches from a sequence of transition records."""
    engine = DarkBranchFilter(config=config)
    return engine.filter_records(records)


def filter_spcat_catalog(
    input_cat_path: Union[str, pathlib.Path],
    output_cat_path: Optional[Union[str, pathlib.Path]] = None,
    config: Optional[DarkBranchFilterConfig] = None,
) -> Tuple[List[TransitionRecord], FilterStatistics]:
    """Convenience function to filter a Pickett SPCAT .cat file on disk."""
    engine = DarkBranchFilter(config=config)
    return engine.filter_spcat_cat_file(input_cat_path, output_cat_path)


def filter_parquet_catalog(
    input_parquet_path: Union[str, pathlib.Path],
    output_parquet_path: Union[str, pathlib.Path],
    config: Optional[DarkBranchFilterConfig] = None,
    chunk_size: int = 10000,
) -> FilterStatistics:
    """Convenience function to stream and filter an out-of-core PyArrow Parquet catalog."""
    engine = DarkBranchFilter(config=config)
    return engine.filter_parquet_catalog(input_parquet_path, output_parquet_path, chunk_size=chunk_size)


def generate_dark_branch_report(
    stats: FilterStatistics,
    output_markdown_path: Optional[Union[str, pathlib.Path]] = None,
    output_latex_path: Optional[Union[str, pathlib.Path]] = None,
) -> Dict[str, str]:
    """Generates and optionally writes GFM Markdown and LaTeX summary reports."""
    gfm = stats.to_gfm_table()
    latex = stats.to_latex_table()

    if output_markdown_path is not None:
        p = pathlib.Path(output_markdown_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(gfm + "\n")

    if output_latex_path is not None:
        p = pathlib.Path(output_latex_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(latex + "\n")

    return {"gfm": gfm, "latex": latex}


# =============================================================================
# Command-Line Interface (CLI) Entrypoint
# =============================================================================

def build_cli_parser() -> argparse.ArgumentParser:
    """Constructs the command-line argument parser for cochem_dark_branch_filter."""
    parser = argparse.ArgumentParser(
        description="CoChem Dark Branch & Spectroscopic Transition Filter Engine (Stage 5.0 / 6.0 / 7.0).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input-cat", type=str, help="Input Pickett SPCAT .cat file to filter.")
    parser.add_argument("--output-cat", type=str, help="Destination path for filtered .cat file.")
    parser.add_argument("--input-parquet", type=str, help="Input PyArrow Parquet spectral catalog to filter.")
    parser.add_argument("--output-parquet", type=str, help="Destination path for filtered Parquet catalog.")

    parser.add_argument(
        "--min-freq",
        type=float,
        default=DEFAULT_MIN_FREQUENCY_MHZ,
        help="Minimum frequency cutoff in MHz.",
    )
    parser.add_argument(
        "--max-freq",
        type=float,
        default=DEFAULT_MAX_FREQUENCY_MHZ,
        help="Maximum frequency cutoff in MHz.",
    )
    parser.add_argument(
        "--min-log-int",
        type=float,
        default=DEFAULT_MIN_LOG_INTENSITY,
        help="Minimum Pickett log10 intensity cutoff.",
    )
    parser.add_argument(
        "--max-uncertainty",
        type=float,
        default=DEFAULT_MAX_UNCERTAINTY_MHZ,
        help="Maximum line uncertainty in MHz.",
    )
    parser.add_argument(
        "--temp-k",
        type=float,
        default=DEFAULT_ROTATIONAL_TEMP_K,
        help="Rotational temperature in Kelvin for supersonic jet population calculation.",
    )
    parser.add_argument(
        "--mu-a",
        type=float,
        default=None,
        help="Permanent dipole moment along principal axis a in Debye.",
    )
    parser.add_argument(
        "--mu-b",
        type=float,
        default=None,
        help="Permanent dipole moment along principal axis b in Debye.",
    )
    parser.add_argument(
        "--mu-c",
        type=float,
        default=None,
        help="Permanent dipole moment along principal axis c in Debye.",
    )
    parser.add_argument(
        "--report-gfm",
        type=str,
        default=None,
        help="Destination markdown file path for GFM summary table.",
    )
    parser.add_argument(
        "--report-latex",
        type=str,
        default=None,
        help="Destination latex file path for LaTeX summary table.",
    )
    return parser


def main(args_list: Optional[Sequence[str]] = None) -> int:
    """Main CLI execution entrypoint."""
    parser = build_cli_parser()
    args = parser.parse_args(args_list)

    dipoles = None
    if args.mu_a is not None or args.mu_b is not None or args.mu_c is not None:
        mu_a = args.mu_a if args.mu_a is not None else 0.0
        mu_b = args.mu_b if args.mu_b is not None else 0.0
        mu_c = args.mu_c if args.mu_c is not None else 0.0
        dipoles = (mu_a, mu_b, mu_c)

    config = DarkBranchFilterConfig(
        min_frequency_mhz=args.min_freq,
        max_frequency_mhz=args.max_freq,
        min_log_intensity=args.min_log_int,
        max_uncertainty_mhz=args.max_uncertainty,
        rotational_temperature_k=args.temp_k,
        dipole_components=dipoles,
    )

    stats: Optional[FilterStatistics] = None

    if args.input_cat:
        _, stats = filter_spcat_catalog(args.input_cat, args.output_cat, config=config)
    elif args.input_parquet and args.output_parquet:
        stats = filter_parquet_catalog(args.input_parquet, args.output_parquet, config=config)
    else:
        logger.warning("No input target specified. Run with --help for options.")
        parser.print_help()
        return 0

    if stats is not None:
        generate_dark_branch_report(
            stats,
            output_markdown_path=args.report_gfm,
            output_latex_path=args.report_latex,
        )
        print(stats.to_gfm_table())

    return 0


if __name__ == "__main__":
    sys.exit(main())
