#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""cochem_base.pes_h5 -- Package export module for pes_h5.py.

Exposes the HDF5 interchange layer classes, functions, and constants mandated by Method Matrix §8C.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is on path
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from pes_h5 import (  # noqa: E402
    CHUNK_POINTS,
    CHUNK_PTS,
    DEFAULT_LOCK_TIMEOUT_S,
    HESSIAN_EIG_TO_CM_INV_FACTOR,
    INERTIA_TO_MHZ_FACTOR,
    VLEN,
    VLEN_STR,
    BifurcatedPESStore,
    BifurcatedStorageConfig,
    DriverType,
    HessianRecord,
    IsotopologueResult,
    PESGridDefinition,
    PESPointRecord,
    PESStore,
    QCSchemaMethodRecord,
    QCSchemaProvenance,
    StorageMode,
    build_cli_parser,
    compute_center_of_mass,
    compute_delta_r_and_delta_b,
    compute_inertia_tensor,
    compute_rotational_constants,
    diagonalize_mass_weighted_hessian,
    get_atomic_mass,
    get_atomic_masses_for_symbols,
    main,
    merge_pes_shards,
    reanalyze_isotopologue,
    reanalyze_isotopologue_suite,
)

__all__ = [
    "CHUNK_POINTS",
    "CHUNK_PTS",
    "DEFAULT_LOCK_TIMEOUT_S",
    "HESSIAN_EIG_TO_CM_INV_FACTOR",
    "INERTIA_TO_MHZ_FACTOR",
    "VLEN",
    "VLEN_STR",
    "BifurcatedPESStore",
    "BifurcatedStorageConfig",
    "DriverType",
    "HessianRecord",
    "IsotopologueResult",
    "PESGridDefinition",
    "PESPointRecord",
    "PESStore",
    "QCSchemaMethodRecord",
    "QCSchemaProvenance",
    "StorageMode",
    "build_cli_parser",
    "compute_center_of_mass",
    "compute_delta_r_and_delta_b",
    "compute_inertia_tensor",
    "compute_rotational_constants",
    "diagonalize_mass_weighted_hessian",
    "get_atomic_mass",
    "get_atomic_masses_for_symbols",
    "main",
    "merge_pes_shards",
    "reanalyze_isotopologue",
    "reanalyze_isotopologue_suite",
]

if __name__ == "__main__":
    main()
