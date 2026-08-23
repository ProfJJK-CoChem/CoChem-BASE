"""Re-export module for cochem_spcat_bridge within the cochem_base package hierarchy."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root path is accessible
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cochem_spcat_bridge import (  # noqa: E402
    BOLTZMANN_CONSTANT_JK,
    C_ROT,
    CODATA2022,
    CODATA_YEAR,
    CONSTANTS,
    HC_OVER_KB,
    KB_OVER_H,
    PICKETT_PARAMETER_CODES,
    PLANCK_CONSTANT_JS,
    ROTATIONAL_FACTOR_C_ROT,
    SPEED_OF_LIGHT_CMS,
    SPEED_OF_LIGHT_MS,
    PartitionFunctionResult,
    SPCATParameter,
    SPCATPayload,
    SymmetryDivisorResult,
    ThreeTierRoutingResult,
    TorqSpcatBridge,
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
    low_frequency_trap,
    route_3tier_abinitio_payload,
    validate_airgap_boundary,
    vibrational_partition_coupling,
)

__all__ = [
    "BOLTZMANN_CONSTANT_JK",
    "C_ROT",
    "CODATA2022",
    "CODATA_YEAR",
    "CONSTANTS",
    "HC_OVER_KB",
    "KB_OVER_H",
    "PLANCK_CONSTANT_JS",
    "ROTATIONAL_FACTOR_C_ROT",
    "SPEED_OF_LIGHT_CMS",
    "SPEED_OF_LIGHT_MS",
    "PICKETT_PARAMETER_CODES",
    "PartitionFunctionResult",
    "SPCATParameter",
    "SPCATPayload",
    "SymmetryDivisorResult",
    "ThreeTierRoutingResult",
    "TorqSpcatBridge",
    "apply_symmetry_divisors",
    "build_complete_spcat_payload",
    "calculate_rotational_partition_function",
    "calculate_vibrational_partition_function",
    "compute_coupled_partition_functions",
    "compute_sha256",
    "format_fortran_double",
    "fortran_double_precision_formatter",
    "fortran_overflow_guard",
    "generate_spcat_int",
    "generate_spcat_provenance_manifest",
    "generate_spcat_var",
    "low_frequency_lam_trap",
    "low_frequency_trap",
    "route_3tier_abinitio_payload",
    "validate_airgap_boundary",
    "vibrational_partition_coupling",
]
