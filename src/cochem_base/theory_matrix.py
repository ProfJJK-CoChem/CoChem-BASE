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
    """Canonical product meanings from the selected Chunk 17 specification."""

    PRODUCT_A = "Product A (Lead Screening)"
    PRODUCT_B = "Product B (Materials and Extended Solids)"
    PRODUCT_C = "Product C (Absolute Spectroscopic Calibration)"


class LegacyMolecularProductClass(str, Enum):
    """Historical molecular workflows, explicitly separate from product certification."""

    DE_NOVO = "De Novo Search"
    PARENT_ANCHORED = "Parent-Anchored Complex"
    ISOTOPOLOGUE = "Isotopologue / Difference"


PRODUCT_CLASS_SPECS = {
    ProductClass.PRODUCT_A: {
        "description": "Lead screening with ab initio relaxed geometry and CPCM/SMD solvation.",
        "target_accuracy": "0.3% - 0.5% rotational constants; 2.0 - 3.0 kcal/mol thermochemistry",
        "maximum_tier": 4,
        "required_solvation": ("CPCM", "SMD"),
        "conformer_search_required": True,
        "frozen_monomers_allowed": True,
        "hessian_reuse_allowed": False,
        "spend_priority_focus": "Conformer coverage and solvated electronic structure",
    },
    ProductClass.PRODUCT_B: {
        "description": "Materials and extended solids with plane-wave PAW treatment for periodic systems.",
        "target_accuracy": "bandgap <= 0.1 eV; lattice parameters <= 0.01 Angstrom",
        "periodic_basis": "plane_wave",
        "pseudopotential": "PAW",
        "conformer_search_required": False,
        "frozen_monomers_allowed": False,
        "hessian_reuse_allowed": False,
        "spend_priority_focus": "Periodic cell, basis and reciprocal-space convergence",
    },
    ProductClass.PRODUCT_C: {
        "description": "Absolute spectroscopic calibration with two-point Helgaker CBS correlation extrapolation.",
        "target_accuracy": "0.02% - 0.1% rotational constants; < 0.5 kcal/mol thermochemistry",
        "cbs_cardinal_pairs": ((3, 4), (4, 5)),
        "conformer_search_required": False,
        "frozen_monomers_allowed": True,
        "hessian_reuse_allowed": True,
        "spend_priority_focus": "Benchmark monomer geometry, intermolecular relaxation and vibrational corrections",
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

# The descriptive UI groups above remain available for legacy callers. T0--T9
# are the canonical complexity tiers; historical UI labels are not tier numbers.
COMPLEXITY_TIERS: Dict[str, Dict[str, Any]] = {
    "T0": {"classification": "Topological / MLFF", "methods": ["GFN-FF", "ANI-2x", "MACE-MP-0", "MACE-POLAR-1"]},
    "T1": {"classification": "Semi-Empirical", "methods": ["GFN2-xTB", "PM7", "OM2"]},
    "T2": {"classification": "Minimal Basis HF", "methods": ["HF/MINI", "HF/STO-3G"]},
    "T3": {"classification": "Rapid DFT", "methods": ["r2SCAN-3c", "B97-3c", "PBE-D4"], "grid": "DEFGRID1"},
    "T4": {"classification": "Standard Hybrid DFT", "methods": ["B3LYP-D4", "wB97X-D4", "PBE0-D3BJ"], "grid": "DEFGRID2"},
    "T5": {"classification": "Range-Separated / Double-Hybrid DFT", "methods": ["wB97M-V", "PWPB95-D4", "B2PLYP-D3"], "grid": "DEFGRID3"},
    "T6": {"classification": "Perturbative Correlation", "methods": ["MP2", "SCS-MP2", "RI-MP2"]},
    "T7": {"classification": "Truncated Coupled Cluster", "methods": ["DLPNO-CCSD(T)", "DLPNO-CCSD(T1)"]},
    "T8": {"classification": "Canonical Coupled Cluster", "methods": ["CCSD(T)"]},
    "T9": {"classification": "Multireference", "methods": ["CASSCF", "NEVPT2", "DMRG-CASPT2"]},
}
# Retained public UI metadata; enforcement always uses the canonical sanitizer.
DISPERSION_FREE_METHODS = {"B3LYP", "PBE0", "HF", "PBE"}
_TIER_BASES = {
    "T0": ["built-in"], "T1": ["built-in"], "T2": ["MINI", "STO-3G"],
    "T3": ["built-in", "def2-SVP"], "T4": ["def2-TZVP", "def2-TZVPP"],
    "T5": ["def2-QZVPP", "def2-QZVPPD"], "T6": ["cc-pVTZ", "aug-cc-pVTZ"],
    "T7": ["cc-pVTZ", "cc-pVQZ"], "T8": ["cc-pCVQZ", "cc-pCV5Z"],
    "T9": ["active-space dependent"],
}
for _tier, _metadata in COMPLEXITY_TIERS.items():
    _metadata["allowed_basis_sets"] = _TIER_BASES[_tier]
    _metadata["default_basis"] = _TIER_BASES[_tier][0]

METHOD_MATRIX_UI_GROUPS = METHOD_MATRIX_TIERS
METHOD_MATRIX_TIERS = {**METHOD_MATRIX_UI_GROUPS, **COMPLEXITY_TIERS}


def canonical_tier_for_method(method: str) -> str:
    """Classify supported model families without accepting a caller's tier label."""
    import re

    token = method.strip().upper().replace("Ω", "W").split()[0] if method.strip() else ""
    token = re.sub(r"-(?:D3(?:\(BJ\)|BJ)?|D4)$", "", token)
    families = {
        "T0": {"GFN-FF", "ANI-2X", "MACE-MP-0", "MACE-POLAR-1", "MACE-OFF24(M)", "AIMNET2"},
        "T1": {"GFN2-XTB", "XTB2", "PM7", "OM2"},
        "T2": {"HF", "HF/MINI", "HF/STO-3G"},
        "T3": {"R2SCAN-3C", "B97-3C", "PBE"},
        "T4": {"B3LYP", "PBE0", "WB97X", "WB97X-V"},
        "T5": {"WB97M-V", "PWPB95", "B2PLYP"},
        "T6": {"MP2", "SCS-MP2", "RI-MP2"},
        "T7": {"DLPNO-CCSD(T)", "DLPNO-CCSD(T1)"},
        "T8": {"CCSD(T)"},
        "T9": {"CASSCF", "NEVPT2", "DMRG-CASPT2"},
    }
    for tier_name, methods in families.items():
        if token in methods:
            return tier_name
    raise MethodologyViolationError(f"Method {method!r} has no audited Chunk 17 tier classification")


def validate_product_class_policy(
    product_class: ProductClass | str,
    *,
    tier: int | str,
    method: str | None = None,
    periodic: bool = False,
    basis: str = "",
    pseudopotential: str = "",
    solvation: str | None = None,
    geometry_source: str = "electronic_structure",
    ab_initio_relaxed: bool = False,
    cbs_cardinal_pair: tuple[int, int] | None = None,
) -> bool:
    """Validate declared methodology, not an unmeasured accuracy guarantee.

    These guards apply at product assignment. Raw conformer screening may precede
    assignment; an ML/force-field seed is insufficient evidence of A/C geometry.
    """
    if isinstance(product_class, ProductClass):
        product = product_class
    else:
        aliases = {"A": ProductClass.PRODUCT_A, "B": ProductClass.PRODUCT_B, "C": ProductClass.PRODUCT_C}
        text = str(product_class).strip()
        product = aliases.get(text.upper())
        if product is None:
            try:
                product = ProductClass(text)
            except ValueError as exc:
                raise MethodologyViolationError(f"Unknown Chunk 17 product class: {text}") from exc
    if isinstance(tier, bool):
        raise MethodologyViolationError("Tier must be T0 through T9")
    tier_text = str(tier).strip().upper()
    if tier_text.startswith("T"):
        tier_text = tier_text[1:]
    if tier_text not in {str(value) for value in range(10)}:
        raise MethodologyViolationError("Tier must be T0 through T9")
    tier_number = int(tier_text)
    if method is not None and canonical_tier_for_method(method) != f"T{tier_number}":
        raise MethodologyViolationError(f"Declared tier T{tier_number} does not match method {method!r}")
    if product in (ProductClass.PRODUCT_A, ProductClass.PRODUCT_C):
        if periodic:
            raise MethodologyViolationError("Periodic systems require Product B materials classification")
        source = geometry_source.strip().upper().replace("-", "_")
        if source in {"MLFF", "ML", "FORCE_FIELD", "GFN_FF", "ANI", "MACE", "ETKDG", "MMFF", "UFF"} and not ab_initio_relaxed:
            raise MethodologyViolationError("Product A/C requires ab initio relaxation of ML/force-field geometry")
    if product == ProductClass.PRODUCT_A:
        if tier_number > 4:
            raise MethodologyViolationError("Product A is capped at tier T4")
        if not solvation or solvation.strip().upper().split("(")[0] not in {"CPCM", "SMD"}:
            raise MethodologyViolationError("Product A requires CPCM or SMD implicit solvation")
    elif product == ProductClass.PRODUCT_B:
        if periodic:
            normalized_basis = basis.strip().lower().replace("-", "_").replace(" ", "_")
            if normalized_basis not in {"plane_wave", "plane_waves", "pw"} or pseudopotential.strip().upper() != "PAW":
                raise MethodologyViolationError("Periodic Product B requires a plane-wave basis and PAW pseudopotentials")
    elif cbs_cardinal_pair not in ((3, 4), (4, 5)):
        raise MethodologyViolationError("Product C requires two-point CBS cardinal pair (3,4) or (4,5)")
    return True


def validate_method_matrix_compliance(
    method: str,
    num_fragments: int = 1,
    unphysical_override: bool = False,
    allow_undispersed_legacy: bool = False,
) -> bool:
    """Apply the canonical dispersion guard; historical bypass flags are rejected."""
    from cochem_base.analysis.electronic_sanitizer import ElectronicSanitizer

    if unphysical_override or allow_undispersed_legacy:
        raise MethodologyViolationError("Method Matrix safety gates cannot be disabled by a legacy override")
    if not isinstance(method, str) or not method.strip():
        raise MethodologyViolationError("An explicit method is required")
    if not isinstance(num_fragments, int) or isinstance(num_fragments, bool) or num_fragments < 1:
        raise MethodologyViolationError("num_fragments must be a positive integer")
    correlated_methods = {"MP2", "SCS-MP2", "RI-MP2", "CCSD(T)", "DLPNO-CCSD(T)", "DLPNO-CCSD(T1)", "JUNCHS", "CASSCF", "NEVPT2", "DMRG-CASPT2"}
    if method.strip().upper() in correlated_methods:
        return True
    try:
        ElectronicSanitizer.sanitize_dft_dispersion(
            functional=method, is_complex=num_fragments >= 2, num_monomers=num_fragments,
        )
    except ValueError as exc:
        raise MethodologyViolationError(str(exc)) from exc
    return True
