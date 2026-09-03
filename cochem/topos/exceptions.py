"""Domain-specific typed exceptions for CoChem-TOPOS Graph Theory and Topology subsystem."""

from __future__ import annotations


try:
    from cochem_base.exceptions import CoChemError
except ImportError:
    class CoChemError(Exception):
        """Root fallback exception for CoChem errors."""


class TopologyError(CoChemError):
    """Raised when graph topological invariants, contiguity, or conservation laws fail."""


class StericClashError(CoChemError):
    """Raised when geometric steric clashes are detected or physical radii are undefined."""


class IsomorphismMismatchError(CoChemError):
    """Raised when subgraph isomorphism matching fails or violates attribute constraints."""


class ChiralityAssignmentError(CoChemError):
    """Raised when stereocenter assignment encounters degenerate, planar, or collinear geometries."""


class CoChemToposException(TopologyError):
    """Root domain exception for CoChem-TOPOS Graph Theory operations."""


class SymmetryPerceptionError(CoChemToposException):
    """Raised when symmetry perception or point group assignment fails."""


class PharmacophoreExtractionError(CoChemToposException):
    """Raised when pharmacophore extraction encounters invalid chemical configurations."""


class IsotopeResolutionError(CoChemToposException):
    """Raised when dynamic isotope query or mass resolution fails."""


class TPSACalculationError(CoChemToposException):
    """Raised when topological polar surface area calculation encounters unparameterized atoms."""


class ResonanceEnumerationError(CoChemToposException):
    """Raised when conjugated pi-system traversal or resonance structure generation fails."""


class GraphSparsificationError(CoChemToposException):
    """Raised when graph sparsification or effective resistance solver fails."""

