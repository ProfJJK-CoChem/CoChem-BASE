"""Domain-specific typed exceptions for CoChem-TORQ Potential Backbones and Calculators."""

from __future__ import annotations

# Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical

try:
    from cochem.topos.exceptions import CoChemError  # type: ignore[import-not-found]
except ImportError:
    class CoChemError(Exception):  # type: ignore[no-redef]
        """Root fallback exception for all CoChem operations. [M]"""

        def __init__(self, message: str = "") -> None:
            super().__init__(message)


class TorqError(CoChemError):
    """Base exception for TORQ potential backbones, observables, and calculators. [M]"""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TorqModelBackboneError(TorqError):
    """Raised when network forward pass or tensor contraction fails. [M]"""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class EquivarianceViolationError(TorqError):
    """Raised when E(3) rotational or inversion equivariance tolerance is violated. [M]"""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class AutogradForceError(TorqError):
    """Raised when coordinate autograd graph construction or force derivation fails. [M]"""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class ObservableComputationError(TorqError):
    """Raised when dipole or polarizability evaluation encounters singular values. [M]"""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TorqPersistenceLockError(TorqError):
    """Raised when filelock or threading lock acquisition exceeds timeout ceiling. [M]"""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TorqDeviceAllocationError(TorqError):
    """Raised when GPU device indexing or CUDA memory allocation fails. [M]"""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class PeriodicBoundaryConditionError(TorqError):
    """Raised when PBC cell vectors are singular or minimum image convention fails. [M]"""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
