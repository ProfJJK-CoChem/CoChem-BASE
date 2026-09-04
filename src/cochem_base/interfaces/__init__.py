"""
CoChem Ecosystem Abstract Execution and Generation Interfaces.
Compliant with Method Matrix v4 and Zero-Mock Mandate.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence, Union
import numpy as np

from cochem_base.schemas import ConformerEnsemblePayload, GradientPayload, QuantumJobSpec


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


class ConformerGenerator(ABC):
    """Standard execution interface for conformer generation engines (GOAT, CREST, etc.)."""

    @abstractmethod
    def generate_conformers(
        self,
        symbols: Sequence[str],
        coordinates: Union[Sequence[Sequence[float]], np.ndarray],
        **kwargs: Any,
    ) -> ConformerEnsemblePayload:
        """Generate a conformer ensemble from an initial seed structure.

        Parameters
        ----------
        symbols : Sequence[str]
            Atomic symbols.
        coordinates : Union[Sequence[Sequence[float]], np.ndarray]
            Seed Cartesian coordinates in Angstroms.
        **kwargs : Any
            Additional engine-specific options.

        Returns
        -------
        ConformerEnsemblePayload
            Container with sampled conformer coordinates, energies, and metadata.
        """
        ...


__all__ = ["ElectronicStructureExecutor", "ConformerGenerator"]
