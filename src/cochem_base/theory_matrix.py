"""
Method Matrix v4 Authoritative Level of Theory Catalog & Compliance Validation.
Governed by Method Matrix v4: §0 (Product Classes), §3.3 (Spend Priority),
§4.4 (Tight Convergence & Dispersion), §9A (Non-covalent Complexes), and Table 3.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List

from cochem_base.exceptions import MethodologyViolationError


class ProductClass(str, Enum):
    """Method Matrix §0 Product Class Categories."""
    PRODUCT_A = "Product A (De Novo Search)"
    PRODUCT_B = "Product B (Parent-Anchored Complex)"
    PRODUCT_C = "Product C (Isotopologue / Difference)"


PRODUCT_CLASS_SPECS = {
    ProductClass.PRODUCT_A: {
        "description": "Unanchored de novo structure. Full conformer search (CREST/GOAT) + DFT screening + composite.",
        "target_accuracy": "0.3% - 0.5% [M]",
        "spend_priority_focus": "Global conformer exploration, dispersion DFT geometry, harmonic ZPVE",
        "conformer_search_required": True,
        "frozen_monomers_allowed": False,
        "hessian_reuse_allowed": False,
    },
    ProductClass.PRODUCT_B: {
        "description": "Known parent complex. Freeze monomer internal geometry to fix A, optimize intermolecular R to determine B and C.",
        "target_accuracy": "0.03% - 0.06% [M]",
        "spend_priority_focus": "Intermolecular separation R, monomer rotational constant A, vibrational correction Delta B_vib",
        "conformer_search_required": False,
        "frozen_monomers_allowed": True,
        "hessian_reuse_allowed": False,
    },
    ProductClass.PRODUCT_C: {
        "description": "Mass perturbation of existing electronic PES. Re-diagonalize parent Hessian for millisecond isotopic shifts.",
        "target_accuracy": "0.02% - 0.1% [M]",
        "spend_priority_focus": "Sub-100ms mass-weighted Cartesian Hessian re-diagonalization (Mendeleev dynamic masses)",
        "conformer_search_required": False,
        "frozen_monomers_allowed": False,
        "hessian_reuse_allowed": True,
    },
}

# Method Matrix v4 §3.3 Mandatory Spend Priority Hierarchy
SPEND_PRIORITY_HIERARCHY: List[str] = [
    "1. Geometry (R) [M]",
    "2. Cheap anharmonic vibrational correction Delta B_vib [M]",
    "3. Frozen Monomers (A) [M]",
    "4. Quartic Centrifugal Distortion [M]",
    "5. Inertial Defect (Delta) and planar moments [D]",
    "6. Signed Dipole Components (mu) [M]",
    "7. Nuclear Quadrupole Coupling Tensor (chi) [M]",
    "8. V3 Internal Rotation Barriers [E]",
    "9. Tunnelling Splittings [E]",
    "10. Binding Energy D0 [M]",
]


# Method Matrix v4 Table 3 & §4.4 Level of Theory Tiers
METHOD_MATRIX_TIERS: Dict[str, Dict[str, Any]] = {
    "Tier 1: Modern Dispersion DFT": {
        "methods": ["wB97M-V", "wB97X-V", "r2SCAN-3c"],
        "default_basis": "def2-TZVP",
        "allowed_basis_sets": ["def2-TZVP", "def2-QZVP", "cc-pVTZ", "aug-cc-pVTZ", "mTZVP"],
        "basis_constraints": {"r2SCAN-3c": ["mTZVP"]},
        "target_accuracy": "0.3% - 0.5% [M]",
        "has_dispersion": True,
        "notes": "State-of-the-art non-local correlation dispersion; mandatory default for de novo conformers.",
    },
    "Tier 2: Wave-Function Composite": {
        "methods": ["junChS", "CCSD(T)", "MP2"],
        "default_basis": "ANO0",
        "allowed_basis_sets": ["ANO0", "cc-pVTZ", "aug-cc-pVTZ", "def2-TZVP", "jun-cc-pVTZ", "jun-cc-pVQZ"],
        "basis_constraints": {"junChS": ["jun-cc-pVTZ", "jun-cc-pVQZ"]},
        "target_accuracy": "0.03% - 0.06% [M]",
        "has_dispersion": True,
        "notes": "Gold-standard composite schemes for parent-anchored complexes (§9A).",
    },
    "Tier 3: Semiempirical Screening": {
        "methods": ["GFN2-xTB", "GFN-FF"],
        "default_basis": "SVP-tight",
        "allowed_basis_sets": ["default"],
        "target_accuracy": "Fast conformational sorting and preliminary screening",
        "has_dispersion": True,
        "notes": "Fast screening for TOPOS / CREST conformer deduplication.",
    },
    "Benchmark Dispersion Tier": {
        "methods": ["B3LYP-D4", "PBE0-D4"],
        "default_basis": "def2-TZVP",
        "allowed_basis_sets": ["def2-TZVP", "def2-QZVP", "cc-pVTZ", "aug-cc-pVTZ"],
        "target_accuracy": "0.1% - 0.3% [M]",
        "has_dispersion": True,
        "notes": "Empirical D4 dispersion benchmark calculations.",
    },
    "Legacy / Custom": {
        "methods": ["B3LYP", "HF"],
        "default_basis": "def2-SVP",
        "allowed_basis_sets": ["def2-SVP", "def2-TZVP", "cc-pVDZ", "cc-pVTZ"],
        "target_accuracy": "Unreliable for non-covalent complexes without dispersion correction",
        "has_dispersion": False,
        "notes": "Dispersion-free functionals are strictly prohibited for non-covalent complexes per §4.4.",
    },
}

DISPERSION_FREE_METHODS = {"B3LYP", "HF"}


def validate_method_matrix_compliance(
    method: str,
    num_fragments: int = 1,
    unphysical_override: bool = False,
    allow_undispersed_legacy: bool = False,
) -> bool:
    """Validates method selection against Method Matrix §4.4 and §9A anti-dispersion mandates.

    If system is a non-covalent complex (num_fragments >= 2) and method lacks dispersion,
    raises MethodologyViolationError unless unphysical_override or allow_undispersed_legacy is explicitly True. [M]
    """
    clean_method = method.strip()
    is_dispersion_free = clean_method in DISPERSION_FREE_METHODS

    if num_fragments >= 2 and is_dispersion_free and not (unphysical_override or allow_undispersed_legacy):
        raise MethodologyViolationError(
            f"Dispersion corrections are mandatory for non-covalent complexes per Method Matrix §4.4 & §9A. "
            f"Uncorrected DFT produces up to 12.74% MAE errors [M]. Functional '{clean_method}' is dispersion-free and "
            f"physically invalid for non-covalent complexes (detected {num_fragments} fragments). "
            f"Use a Tier 1 modern dispersion functional (e.g. wB97M-V) or pass allow_undispersed_legacy=True."
        )

    return True
