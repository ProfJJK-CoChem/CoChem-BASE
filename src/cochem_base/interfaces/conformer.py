"""CoChem Ecosystem Conformer Generator Interface.

Compliant with Method Matrix v4 §9B and Zero-Mock Mandate.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence, Union
import numpy as np

from cochem_base.schemas import ConformerEnsemblePayload


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


__all__ = ["ConformerGenerator"]
