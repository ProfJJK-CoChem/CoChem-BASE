"""CoChem Ecosystem Electronic Structure Executor Interface.

Compliant with Method Matrix v4 and Zero-Mock Mandate.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from cochem_base.schemas import GradientPayload, QuantumJobSpec


class ElectronicStructureExecutor(ABC):
    """Standard execution interface for electronic structure engines (ORCA, CFOUR, etc.)."""

    @abstractmethod
    def execute(self, job_spec: QuantumJobSpec) -> GradientPayload:
        """Execute an electronic structure calculation described by job_spec.

        Parameters
        ----------
        job_spec : QuantumJobSpec
            Specification of coordinates, method, basis set, and job type.

        Returns
        -------
        GradientPayload
            Energies, gradients, and optional Hessians from the engine.
        """
        ...


__all__ = ["ElectronicStructureExecutor"]
