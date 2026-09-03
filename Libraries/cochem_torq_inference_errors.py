"""Domain-specific typed exceptions for CoChem-TORQ Inference, Active Learning, and Export.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Absolutely no stubs or empty pass blocks.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class CoChemError(Exception):
    """Root exception for CoChem framework. [M]"""

    def __init__(self, message: str = "Generic CoChem error") -> None:
        super().__init__(message)
        self.message = message


class CoChemTorqError(CoChemError):
    """Base exception for all TORQ sub-framework operations. [M]"""

    def __init__(self, message: str = "Generic TORQ error") -> None:
        super().__init__(message)
        self.message = message


class TorqInferenceError(CoChemTorqError):
    """Base exception for all TORQ inference and export errors. [M]"""

    def __init__(
        self,
        message: str,
        error_code: str = "TORQ_INF_GENERIC",
        component: str = "inference_engine",
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.component = component
        self.diagnostics = diagnostics or {}


class ActiveLearningSelectionError(TorqInferenceError):
    """Raised when active learning selection or pool deduplication fails. [M]"""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            error_code="TORQ_AL_SELECTION_ERR",
            component="active_learning",
            **kwargs,
        )


class HDF5DataModuleLockError(TorqInferenceError):
    """Raised when multi-worker HDF5 handle acquisition encounters lock timeout. [M]"""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            error_code="TORQ_HDF5_LOCK_ERR",
            component="hdf5_datamodule",
            **kwargs,
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


class CutoffContinuityError(TorqInferenceError):
    """Raised when radial cutoff function violates C^2 smoothness or boundary zero condition. [D]"""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message, error_code="TORQ_CUTOFF_ERR", component="c2_cutoff", **kwargs
        )


class GradientExplosionError(TorqInferenceError):
    """Raised when GNN message passing activations or gradients exceed stability threshold. [D]"""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            error_code="TORQ_GRAD_EXPLOSION_ERR",
            component="gnn_debugger",
            **kwargs,
        )


class VanishingGradientWarning(UserWarning):
    """Emitted when message passing gradients drop below minimum threshold across consecutive layers. [D]"""

    def __init__(
        self, message: str = "GNN message passing gradients vanishing"
    ) -> None:
        super().__init__(message)
        self.message = message


class PBCGraphError(TorqInferenceError):
    """Raised when periodic boundary condition graph construction or virial calculation fails. [D]"""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            error_code="TORQ_PBC_GRAPH_ERR",
            component="pbc_graph",
            **kwargs,
        )


class AirGapViolationError(TorqInferenceError):
    """Raised when inference or active learning loops attempt forbidden outbound networking or direct subprocess execution. [M]"""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            error_code="TORQ_AIRGAP_ERR",
            component="airgap_sandbox",
            **kwargs,
        )
