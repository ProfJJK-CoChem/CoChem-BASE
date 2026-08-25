"""
CoChem-BASE: Export and Audit Utilities
Includes FAIR packaging, LaTeX SI generation, ephemeral scratch purging,
process thread reaping, HDF5 lock sweeping, and environment sanitization.
"""

from .cochem_topos_export import (
    DEFAULT_TEMPERATURE_K,
    GAS_CONSTANT_KCAL_MOL_K,
    HARTREE_TO_KCAL_MOL,
    STATIC_METHOD_CITATIONS,
    TOPOSFAIRExporter,
    _compute_sha256,
    apply_readonly_lock,
    calculate_boltzmann_weights,
    remove_readonly_lock,
    sanitize_latex,
)

__all__ = [
    "TOPOSFAIRExporter",
    "apply_readonly_lock",
    "remove_readonly_lock",
    "calculate_boltzmann_weights",
    "sanitize_latex",
    "_compute_sha256",
    "STATIC_METHOD_CITATIONS",
    "HARTREE_TO_KCAL_MOL",
    "GAS_CONSTANT_KCAL_MOL_K",
    "DEFAULT_TEMPERATURE_K",
]
