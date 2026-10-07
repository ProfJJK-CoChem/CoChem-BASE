"""Compatibility import for the canonical calculation execution router."""
from cochem_base.calc.cochem_calc_execution_router import (
    ExecutionRouter,
    RegistryAuthorityViolationError,
    compute_counterpoise_interaction_energy,
    validate_counterpoise_request,
)

__all__ = ["ExecutionRouter", "RegistryAuthorityViolationError", "compute_counterpoise_interaction_energy", "validate_counterpoise_request"]
