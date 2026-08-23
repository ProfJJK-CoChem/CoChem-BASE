# -*- coding: utf-8 -*-
"""CoChem-BASE Tensor Extractor Proxy Module.

Re-exports all symbols from cochem_tensor_extractor within the cochem_base package hierarchy.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root path is accessible
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cochem_tensor_extractor import (  # noqa: E402
    AMU_KG,
    CIAAW_ISOTOPIC_MASSES,
    INERTIA_CONVERSION_AMU_ANG2_CM1,
    INERTIA_CONVERSION_AMU_ANG2_GHZ,
    INERTIA_CONVERSION_AMU_ANG2_MHZ,
    PLANCK_H,
    SPEED_OF_LIGHT_CM_S,
    CartesianProtectionResult,
    InertiaTensorResult,
    RepresentationSwitchResult,
    TorqTensorExtractor,
    apply_cartesian_protections,
    build_inertia_tensor,
    calculate_center_of_mass,
    diagonalize_inertia_tensor,
    dynamic_representation_switch,
    resolve_atomic_mass,
    translate_to_center_of_mass,
)

__all__ = [
    "AMU_KG",
    "CIAAW_ISOTOPIC_MASSES",
    "CartesianProtectionResult",
    "INERTIA_CONVERSION_AMU_ANG2_CM1",
    "INERTIA_CONVERSION_AMU_ANG2_GHZ",
    "INERTIA_CONVERSION_AMU_ANG2_MHZ",
    "InertiaTensorResult",
    "PLANCK_H",
    "RepresentationSwitchResult",
    "SPEED_OF_LIGHT_CM_S",
    "TorqTensorExtractor",
    "apply_cartesian_protections",
    "build_inertia_tensor",
    "calculate_center_of_mass",
    "diagonalize_inertia_tensor",
    "dynamic_representation_switch",
    "resolve_atomic_mass",
    "translate_to_center_of_mass",
]
