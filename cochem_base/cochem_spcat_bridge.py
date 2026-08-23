"""Re-export module for cochem_spcat_bridge within the cochem_base package hierarchy."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root path is accessible
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cochem_spcat_bridge import (  # noqa: E402
    CODATA2022,
    CONSTANTS,
    PICKETT_PARAMETER_CODES,
    PartitionFunctionResult,
    SPCATParameter,
    SPCATPayload,
    SymmetryDivisorResult,
    apply_symmetry_divisors,
    build_complete_spcat_payload,
    calculate_rotational_partition_function,
    calculate_vibrational_partition_function,
    compute_coupled_partition_functions,
    compute_sha256,
    format_fortran_double,
    fortran_double_precision_formatter,
    fortran_overflow_guard,
    generate_spcat_int,
    generate_spcat_provenance_manifest,
    generate_spcat_var,
    low_frequency_lam_trap,
    validate_airgap_boundary,
    vibrational_partition_coupling,
)

__all__ = [
    "CODATA2022",
    "CONSTANTS",
    "SymmetryDivisorResult",
    "PartitionFunctionResult",
    "SPCATParameter",
    "SPCATPayload",
    "PICKETT_PARAMETER_CODES",
    "low_frequency_lam_trap",
    "apply_symmetry_divisors",
    "calculate_rotational_partition_function",
    "calculate_vibrational_partition_function",
    "vibrational_partition_coupling",
    "compute_coupled_partition_functions",
    "fortran_overflow_guard",
    "format_fortran_double",
    "fortran_double_precision_formatter",
    "generate_spcat_var",
    "generate_spcat_int",
    "validate_airgap_boundary",
    "compute_sha256",
    "generate_spcat_provenance_manifest",
    "build_complete_spcat_payload",
]
