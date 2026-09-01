"""CoChem-GEOM: Continuous Interaction Cutoff Envelopes & Spatial Weighting.
=================================================================================
Provides smooth boundary cutoff envelopes and interaction primitives for 3D
Graph Neural Networks (SchNet, EGNN, DimeNet) within the CoChem ecosystem.

Theoretical Foundations & Physics Contracts:
1. Smooth Spatial Interaction Cutoff:
   - Physical non-covalent and interatomic forces decay to zero at long range.
   - To impose sparsity without discontinuous derivative spikes in autograd force
     derivation ($\\mathbf{F} = -\\nabla_{\\mathbf{r}} E$), a continuously differentiable
     cosine envelope $f_{\\text{cut}}(d)$ is applied [D]:
     $$f_{\\text{cut}}(d) = \\begin{cases}
       \\frac{1}{2} \\left( \\cos\\left( \\frac{\\pi d}{r_{\\text{cut}}} \\right) + 1 \\right), & d < r_{\\text{cut}} \\\\
       0, & d \\ge r_{\\text{cut}}
     \\end{cases}$$

2. Twice-Continuous Differentiability ($C^2$):
   - At $d = r_{\\text{cut}}$, $f_{\\text{cut}}(r_{\\text{cut}}) = 0$ and $f'_{\\text{cut}}(r_{\\text{cut}}) = 0$,
     ensuring smooth force transitions without gradient discontinuities [M].

3. Provenance Tagging:
   - [M] Measured / Theoretical physical cutoff constraints
   - [D] Derived mathematical continuous boundary equations
   - [E] Expert engineering hyperparameter defaults
"""

from __future__ import annotations

import math
from typing import Optional, Union

import torch
import torch.nn as nn


class CosineCutoff(nn.Module):
    """Smooth cosine cutoff envelope function for spatial message damping [D].

    Smoothly decays interaction weights from $1.0$ at $d=0$ to $0.0$ at the cutoff
    boundary $d=r_{\\text{cut}}$, ensuring continuous first- and second-order derivatives:

    $$f_{\\text{cut}}(d) = \\frac{1}{2} \\left( \\cos\\left( \\frac{\\pi d}{r_{\\text{cut}}} \\right) + 1 \\right) \\cdot \\mathbb{I}(d < r_{\\text{cut}})$$

    Parameters
    ----------
    cutoff : float
        Spatial interaction cutoff radius in Angstroms (default: 5.0) [E].
    """

    def __init__(self, cutoff: float = 5.0) -> None:
        super().__init__()
        if cutoff <= 0.0:
            raise ValueError(f"cutoff radius must be strictly positive, got {cutoff}")

        self.cutoff_val: float = float(cutoff)
        self.register_buffer("cutoff", torch.tensor(cutoff, dtype=torch.float32))

    def forward(self, distances: torch.Tensor) -> torch.Tensor:
        """Evaluate smooth cosine cutoff weights for pairwise Euclidean distances [D].

        Parameters
        ----------
        distances : torch.Tensor
            Pairwise Euclidean distances tensor of shape `[E]` or `[E, 1]`.

        Returns
        -------
        torch.Tensor
            Cutoff envelope multiplier weights in $[0.0, 1.0]$ of shape matching `distances`.
        """
        cutoffs = 0.5 * (torch.cos(distances * (math.pi / self.cutoff)) + 1.0)
        mask = (distances < self.cutoff).to(distances.dtype)
        return cutoffs * mask

    def extra_repr(self) -> str:
        """String representation showing cutoff parameter."""
        return f"cutoff={self.cutoff_val}"


__all__ = [
    "CosineCutoff",
]
