"""CoChem-GEOM: Radial Basis Function (RBF) Distance Expansions.
=============================================================================
Provides continuous Gaussian distance smearing and radial basis expansions
for 3D Graph Neural Networks (SchNet, DimeNet, PaiNN) within the CoChem ecosystem.

Theoretical Foundations & Physics Contracts:
1. Continuous Distance Smearing:
   - Expands scalar Euclidean distances $d \\in \\mathbb{R}^+$ into a continuous,
     smooth feature representation $\\boldsymbol{\\phi}(d) \\in \\mathbb{R}^K$:
     $$\\phi_k(d) = \\exp\\left(-\\gamma (d - \\mu_k)^2\\right)$$
   - Centers $\\mu_k$ are uniformly distributed in $[d_{\\text{start}}, d_{\\text{stop}}]$.
   - Variance $\\gamma = \\frac{1}{2 \\sigma^2}$ is set based on center spacing $\\Delta \\mu$
     to guarantee smooth overlap and partition of unity properties [D]:
     $$\\gamma = \\frac{1}{2 \\left(\\frac{d_{\\text{stop}} - d_{\\text{start}}}{K - 1}\\right)^2}$$

2. Twice-Continuous Differentiability ($C^2$):
   - Gaussian basis functions have infinitely smooth ($C^\\infty$) derivatives,
     guaranteeing smooth interatomic force derivation: $\\mathbf{F} = -\\nabla_{\\mathbf{r}} E$ [M].

3. Provenance Tagging:
   - [M] Measured / Theoretical physical invariants
   - [D] Derived mathematical & geometric equations
   - [E] Expert engineering hyperparameter defaults
"""

from __future__ import annotations

import math
from typing import Optional, Union

import torch
import torch.nn as nn


class GaussianSmearing(nn.Module):
    """Gaussian Radial Basis Function (RBF) continuous distance expansion [D].

    Expands 1D interatomic Euclidean distances into a $K$-dimensional continuous
    feature space using evenly spaced Gaussian kernels:

    $$\\phi_k(d) = \\exp\\left( -\\frac{(d - \\mu_k)^2}{2 \\sigma^2} \\right) = \\exp\\left( \\text{coeff} \\cdot (d - \\mu_k)^2 \\right)$$

    Parameters
    ----------
    start : float
        Lower bound distance for Gaussian center placement in Angstroms (default: 0.0) [E].
    stop : float
        Upper bound cutoff distance for Gaussian centers in Angstroms (default: 10.0) [E].
    num_gaussians : int
        Number of Gaussian basis kernels $K$ (default: 50) [E].
    """

    def __init__(
        self,
        start: float = 0.0,
        stop: float = 10.0,
        num_gaussians: int = 50,
    ) -> None:
        super().__init__()
        if num_gaussians <= 1:
            raise ValueError(f"num_gaussians must be > 1, got {num_gaussians}")
        if stop <= start:
            raise ValueError(f"stop ({stop}) must be strictly greater than start ({start})")

        self.start: float = float(start)
        self.stop: float = float(stop)
        self.num_gaussians: int = int(num_gaussians)

        # Evenly space the Gaussian kernel centers mu_k in [start, stop]
        offset = torch.linspace(self.start, self.stop, self.num_gaussians)
        self.register_buffer("offset", offset)

        # Compute width parameter coeff = -0.5 / (delta_mu)^2
        delta_mu = (self.stop - self.start) / (self.num_gaussians - 1)
        coeff = -0.5 / (delta_mu ** 2)
        self.register_buffer("coeff", torch.tensor(coeff, dtype=torch.float32))

    def forward(self, dist: torch.Tensor) -> torch.Tensor:
        """Expand 1D distances into smooth Gaussian basis representations [D].

        Parameters
        ----------
        dist : torch.Tensor
            Scalar distances tensor of shape `[E]` or `[E, 1]`.

        Returns
        -------
        torch.Tensor
            Continuous Gaussian RBF expansions of shape `[E, num_gaussians]`.
        """
        # Broadcast subtraction: [E, 1] - [1, num_gaussians] -> [E, num_gaussians]
        dist_view = dist.view(-1, 1) - self.offset.view(1, -1)
        return torch.exp(self.coeff * torch.pow(dist_view, 2))

    def extra_repr(self) -> str:
        """String representation showing basis parameters."""
        return (
            f"start={self.start}, "
            f"stop={self.stop}, "
            f"num_gaussians={self.num_gaussians}"
        )


__all__ = [
    "GaussianSmearing",
]
