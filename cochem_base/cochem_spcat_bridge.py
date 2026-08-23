"""Re-export module for cochem_spcat_bridge within the cochem_base package hierarchy."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root path is accessible
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cochem_spcat_bridge import (  # noqa: E402
    CONSTANTS,
    CODATA2022,
    PartitionFunctionResult,
    SPCATParameter,
    SPCATPayload,
    SymmetryDivisorResult,
    ThreeTierRoutingResult,
    apply_symmetry_divisors,
    build_complete_spcat_payload,
    calculate_rotational_partition_function,
    calculate_vibrational_partition_function,
    compute_coupled_partition_functions,
    format_fortran_double,
    fortran_double_precision_formatter,
    fortran_overflow_guard,
    generate_spcat_int,
    generate_spcat_var,
    low_frequency_lam_trap,
    route_3tier_abinitio_payload,
    validate_airgap_boundary,
    vibrational_partition_coupling,
)

low_frequency_trap = low_frequency_lam_trap

__all__ = [
    "CONSTANTS",
    "CODATA2022",
    "PartitionFunctionResult",
    "SPCATParameter",
    "SPCATPayload",
    "SymmetryDivisorResult",
    "ThreeTierRoutingResult",
    "apply_symmetry_divisors",
    "build_complete_spcat_payload",
    "calculate_rotational_partition_function",
    "calculate_vibrational_partition_function",
    "compute_coupled_partition_functions",
    "format_fortran_double",
    "fortran_double_precision_formatter",
    "fortran_overflow_guard",
    "generate_spcat_int",
    "generate_spcat_var",
    "low_frequency_lam_trap",
    "low_frequency_trap",
    "route_3tier_abinitio_payload",
    "validate_airgap_boundary",
    "vibrational_partition_coupling",
]

