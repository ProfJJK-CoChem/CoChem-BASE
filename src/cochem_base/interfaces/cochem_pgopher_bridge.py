#!/usr/bin/env python3
"""CoChem-INTERFACES: PGOPHER Rotational Spectroscopy Simulation Bridge (Direct Entrypoint).

Re-exports canonical symbols from cochem_base.interfaces.cochem_pgopher_bridge.
Method Matrix v4 Section 7, 16.2, 18 Compliant.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is available in sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cochem_base.interfaces.cochem_pgopher_bridge import (  # noqa: E402
    BOLTZMANN_CONSTANT_JK,
    C_ROT,
    CM1_TO_MHZ,
    CODATA2022,
    CODATA_YEAR,
    CONSTANTS,
    HC_OVER_KB,
    KB_OVER_H,
    MHZ_TO_CM1,
    PLANCK_CONSTANT_JS,
    ROTATIONAL_FACTOR_C_ROT,
    SPEED_OF_LIGHT_CMS,
    SPEED_OF_LIGHT_MS,
    PGOPHERBridgeError,
    PGOPHERDipoleMoments,
    PGOPHERPayload,
    PGOPHERQuadrupoleNucleus,
    PGOPHERRotationalConstants,
    PGOPHESpectralTransition,
    PGOPHERSpectralTransition,
    PGOPHERSimulationConfig,
    PGOPHERSymmetryResolution,
    PGOPHERWatsonReduction,
    TorqPGOPHERBridge,
    calculate_pgopher_partition_function,
    compute_sha256,
    compute_spectral_profile,
    convert_pgopher_to_pickett,
    convert_pickett_to_pgopher,
    find_pgopher_executable,
    generate_pgopher_provenance_manifest,
    generate_pgopher_xml,
    inspect_parquet_catalog_metadata,
    parse_pgopher_linelist,
    parse_pgopher_xml,
    resolve_isotope_properties,
    resolve_pgopher_symmetry_and_weights,
    run_pgopher_headless,
    validate_airgap_boundary,
)

__all__ = [
    "CODATA2022",
    "CONSTANTS",
    "CODATA_YEAR",
    "PLANCK_CONSTANT_JS",
    "BOLTZMANN_CONSTANT_JK",
    "SPEED_OF_LIGHT_CMS",
    "SPEED_OF_LIGHT_MS",
    "ROTATIONAL_FACTOR_C_ROT",
    "C_ROT",
    "HC_OVER_KB",
    "KB_OVER_H",
    "MHZ_TO_CM1",
    "CM1_TO_MHZ",
    "PGOPHERBridgeError",
    "PGOPHERRotationalConstants",
    "PGOPHERWatsonReduction",
    "PGOPHERDipoleMoments",
    "PGOPHERQuadrupoleNucleus",
    "PGOPHERSimulationConfig",
    "PGOPHESpectralTransition",
    "PGOPHERSpectralTransition",
    "PGOPHERPayload",
    "PGOPHERSymmetryResolution",
    "resolve_pgopher_symmetry_and_weights",
    "resolve_isotope_properties",
    "calculate_pgopher_partition_function",
    "compute_spectral_profile",
    "generate_pgopher_xml",
    "parse_pgopher_xml",
    "convert_pickett_to_pgopher",
    "convert_pgopher_to_pickett",
    "inspect_parquet_catalog_metadata",
    "validate_airgap_boundary",
    "compute_sha256",
    "generate_pgopher_provenance_manifest",
    "find_pgopher_executable",
    "run_pgopher_headless",
    "parse_pgopher_linelist",
    "TorqPGOPHERBridge",
]
