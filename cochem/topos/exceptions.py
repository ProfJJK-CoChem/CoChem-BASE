"""Domain-specific typed exceptions for CoChem-TOPOS Graph Theory and Topology subsystem."""

from __future__ import annotations


try:
    from cochem_base.exceptions import CoChemError  # type: ignore[import-not-found]
except ImportError:
    class CoChemError(Exception):  # type: ignore[no-redef]
        """Root fallback exception for CoChem errors."""

        def __init__(self, message: str = "") -> None:
            super().__init__(message)


class ToposError(CoChemError):
    """Base exception for all TOPOS operations."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TopologyError(ToposError):
    """Raised when graph topological invariants, contiguity, or conservation laws fail."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class StericClashError(ToposError):
    """Raised when geometric steric clashes are detected or physical radii are undefined."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class IsomorphismMismatchError(ToposError):
    """Raised when subgraph isomorphism matching fails or violates attribute constraints."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class ChiralityAssignmentError(ToposError):
    """Raised when stereocenter assignment encounters degenerate, planar, or collinear geometries."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class CoChemToposException(TopologyError):
    """Root domain exception for CoChem-TOPOS Graph Theory operations."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class SymmetryPerceptionError(CoChemToposException):
    """Raised when symmetry perception or point group assignment fails."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class PharmacophoreExtractionError(CoChemToposException):
    """Raised when pharmacophore extraction encounters invalid chemical configurations."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class IsotopeResolutionError(CoChemToposException):
    """Raised when dynamic isotope query or mass resolution fails."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TPSACalculationError(CoChemToposException):
    """Raised when topological polar surface area calculation encounters unparameterized atoms."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class ResonanceEnumerationError(CoChemToposException):
    """Raised when conjugated pi-system traversal or resonance structure generation fails."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class GraphSparsificationError(CoChemToposException):
    """Raised when graph sparsification or effective resistance solver fails."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class SolventBuilderError(CoChemToposException):
    """Raised when explicit solvent builder encounters invalid geometry, density, or bounding box."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TopologicalCanonicalizationError(CoChemToposException):
    """Raised when topological graph canonicalization or isomorphism invariant indexing fails."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class MalformedRecordError(ToposError):
    """Raised when input record syntax is corrupted or unparseable."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class UnparameterizedAtomError(ToposError):
    """Raised when an atom lacks forcefield parameters."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class BondPerceptionError(ToposError):
    """Raised when physical valences or bond orders cannot be resolved."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class ParsingAirGapError(ToposError):
    """Raised when a parser worker process exceeds memory or execution time limits."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TopologyDiffError(ToposError):
    """Raised when MCS graph diffing fails to resolve."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class FragmentationError(ToposError):
    """Raised when retrosynthetic fragmentation or valence checking fails."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class FingerprintGenerationError(ToposError):
    """Raised when circular fingerprint generation fails."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
