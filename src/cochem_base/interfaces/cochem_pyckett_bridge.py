#!/usr/bin/env python3
"""CoChem-INTERFACES: Pyckett & Pickett CALPGM Spectroscopy Bridge (Direct Entrypoint).

Re-exports canonical symbols from cochem_base.interfaces.cochem_pyckett_bridge.
Method Matrix v4 Section 7, 16.2, 18 Compliant.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is available in sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cochem_base.interfaces.cochem_pyckett_bridge import (  # noqa: E402
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
    PyckettBridge,
    PyckettBridgeError,
    PyckettDipoleMoments,
    PyckettEnergyLevel,
    PyckettFitResult,
    PyckettLinEntry,
    PyckettPayload,
    PyckettQuadrupoleNucleus,
    PyckettRotationalConstants,
    PyckettSimulationConfig,
    PyckettSymmetryResolution,
    PyckettTransition,
    PyckettWatsonReduction,
    TorqPyckettBridge,
    cat_to_df,
    cat_to_dict,
    compute_sha256,
    compute_spectral_profile,
    decode_pickett_quantum_number,
    egy_to_df,
    egy_to_dict,
    encode_pickett_quantum_number,
    erhamlines_to_df,
    fit_to_dict,
    format_fortran_double,
    fortran_overflow_guard,
    generate_pickett_int,
    generate_pickett_lin,
    generate_pickett_var,
    generate_pyckett_provenance_manifest,
    inspect_parquet_catalog_metadata,
    int_to_dict,
    lin_to_df,
    lin_to_dict,
    low_frequency_lam_trap,
    parvar_to_dict,
    pyckett_add,
    pyckett_auto,
    pyckett_duplicates,
    pyckett_omit,
    pyckett_pmix,
    pyckett_qrot,
    pyckett_report,
    pyckett_uncertainties,
    resolve_isotope_properties,
    resolve_pyckett_symmetry_and_weights,
    solve_asymmetric_rotor_spectrum,
    validate_airgap_boundary,
)

__all__ = [
    # Physical Constants
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
    # Custom Error
    "PyckettBridgeError",
    # Data Structures
    "PyckettRotationalConstants",
    "PyckettWatsonReduction",
    "PyckettDipoleMoments",
    "PyckettQuadrupoleNucleus",
    "PyckettTransition",
    "PyckettEnergyLevel",
    "PyckettLinEntry",
    "PyckettSimulationConfig",
    "PyckettSymmetryResolution",
    "PyckettFitResult",
    "PyckettPayload",
    # Symmetry & Mendeleev Resolution
    "resolve_pyckett_symmetry_and_weights",
    "resolve_isotope_properties",
    "low_frequency_lam_trap",
    # Quantum Number Codecs
    "decode_pickett_quantum_number",
    "encode_pickett_quantum_number",
    # Fortran Precision & Formatting
    "fortran_overflow_guard",
    "format_fortran_double",
    # Pickett File Generators
    "generate_pickett_var",
    "generate_pickett_int",
    "generate_pickett_lin",
    # Pyckett Core Readers
    "cat_to_dict",
    "cat_to_df",
    "parvar_to_dict",
    "int_to_dict",
    "lin_to_dict",
    "lin_to_df",
    "egy_to_dict",
    "egy_to_df",
    "erhamlines_to_df",
    "fit_to_dict",
    # Pyckett Automation & Tooling
    "pyckett_auto",
    "pyckett_add",
    "pyckett_omit",
    "pyckett_uncertainties",
    "pyckett_qrot",
    "pyckett_report",
    "pyckett_duplicates",
    "pyckett_pmix",
    # Simulation & Broadening
    "solve_asymmetric_rotor_spectrum",
    "compute_spectral_profile",
    # Airgap & Provenance
    "validate_airgap_boundary",
    "compute_sha256",
    "generate_pyckett_provenance_manifest",
    "inspect_parquet_catalog_metadata",
    # Lifecycle Class
    "TorqPyckettBridge",
    "PyckettBridge",
]
