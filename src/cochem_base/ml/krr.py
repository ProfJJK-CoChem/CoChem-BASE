"""Numerically Conditioned Kernel Ridge Regression (Suggestion #137, #138 / Method Matrix v4 §8C, §13.2 [M], [D])."""

from __future__ import annotations

from cochem_base.core_engine.cochem_core_auto_pes import (
    ExactKernelRidgeEstimator,
    KernelType,
)
from cochem_base.schemas import KrrRegularizationConfig

# Unified KernelRidgeModel alias
KernelRidgeModel = ExactKernelRidgeEstimator

__all__ = [
    "ExactKernelRidgeEstimator",
    "KernelRidgeModel",
    "KernelType",
    "KrrRegularizationConfig",
]
