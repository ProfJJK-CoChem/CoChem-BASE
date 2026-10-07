"""Public architecture entry point for physical resource guarding."""

from cochem_base.cochem_core.ai.resource_guard import (
    ResourceGuardDecision,
    evaluate_resource_guard,
)

__all__ = ["ResourceGuardDecision", "evaluate_resource_guard"]
