#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
cochem_base.chain -- Package export module for chain.py
Exposes the canonical state-chaining driver classes, functions, and constants.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is on path
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from chain import (  # noqa: E402
    CANONICAL_ARROWS,
    CHUNK_POINTS,
    HESSIAN_EIG_TO_CM_INV_FACTOR,
    INERTIA_TO_MHZ_FACTOR,
    TIGHT_GEOM_BLOCK,
    VLEN_STR,
    Chain,
    ExecutionArrow,
    Stage,
    StateRecord,
    compute_center_of_mass,
    compute_delta_r_and_delta_b,
    compute_inertia_tensor,
    compute_rotational_constants,
    diagonalize_mass_weighted_hessian,
    export_lineage_dot,
    get_atomic_mass,
    get_atomic_masses_for_symbols,
    parse_orca_convergence,
    parse_orca_energy,
    parse_orca_hessian,
    parse_xtb_output,
    read_xyz,
    reanalyze_isotopologue,
    validate_rule_d1_geometry_stationarity,
    validate_rule_d2_hessian_reuse,
    validate_rule_d3_scf_stability,
    validate_rule_d4_counterpoise_ghosts,
    validate_rule_d5_naming_hygiene,
    write_xyz,
)

__all__ = [
    "CANONICAL_ARROWS",
    "CHUNK_POINTS",
    "HESSIAN_EIG_TO_CM_INV_FACTOR",
    "INERTIA_TO_MHZ_FACTOR",
    "TIGHT_GEOM_BLOCK",
    "VLEN_STR",
    "Chain",
    "ExecutionArrow",
    "Stage",
    "StateRecord",
    "compute_center_of_mass",
    "compute_delta_r_and_delta_b",
    "compute_inertia_tensor",
    "compute_rotational_constants",
    "diagonalize_mass_weighted_hessian",
    "export_lineage_dot",
    "get_atomic_mass",
    "get_atomic_masses_for_symbols",
    "parse_orca_convergence",
    "parse_orca_energy",
    "parse_orca_hessian",
    "parse_xtb_output",
    "read_xyz",
    "reanalyze_isotopologue",
    "validate_rule_d1_geometry_stationarity",
    "validate_rule_d2_hessian_reuse",
    "validate_rule_d3_scf_stability",
    "validate_rule_d4_counterpoise_ghosts",
    "validate_rule_d5_naming_hygiene",
    "write_xyz",
]
