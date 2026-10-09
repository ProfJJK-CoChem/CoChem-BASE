"""Author-owned TORQ numeric contracts, preserved for BASE canonical helpers.

Source: CoChem-TORQ 4f323800227dbde00ffb082bd6d9e44d851e1c7a.
The formulas/configuration/error payload semantics are retained unchanged.
"""
from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class CoChemError(Exception):
    """Root exception for CoChem framework. [M]"""

    def __init__(self, message: str = "Generic CoChem error") -> None:
        super().__init__(message)
        self.message = message


class CoChemTorqError(CoChemError):
    """Base exception for all TORQ sub-framework operations. [M]"""

    def __init__(
        self,
        message: str = "Generic TORQ error",
        error_code: str = "TORQ_GENERIC_ERROR",
        component: str = "inference_export",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.component = component
        self.diagnostics = diagnostics or {}


class TorqInferenceError(CoChemTorqError):
    """Base exception for all TORQ inference and export errors. [M]"""

    def __init__(
        self,
        message: str,
        error_code: str = "TORQ_INF_GENERIC",
        component: str = "inference_engine",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            component=component,
            diagnostics=diagnostics,
        )


class CutoffContinuityError(TorqInferenceError):
    """Raised when radial cutoff function violates C^2 smoothness or boundary zero condition. [D]"""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message, error_code="TORQ_CUTOFF_ERR", component="c2_cutoff", **kwargs
        )


class EnsembleConsensusError(TorqInferenceError):
    """Raised when committee ensemble encounters dimension mismatch or consensus divergence. [D]"""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            error_code="TORQ_ENSEMBLE_ERR",
            component="committee_ensemble",
            **kwargs,
        )


class C2SmoothCutoffConfig(BaseModel):
    """Configuration contract for C^2-smooth radial cutoff envelope. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cutoff_radius_rc: float = Field(
        default=5.0,
        gt=1.0,
        description="Radial cutoff boundary radius r_c in Angstroms [M]",
    )
    polynomial_degree: Literal[5] = Field(
        default=5,
        description="Degree of C^2 continuous switching polynomial [D]",
    )
