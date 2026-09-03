"""Smooth Cutoff Envelopes and Radial Basis Expansions for CoChem-TORQ."""

from __future__ import annotations

import math
from typing import Literal
import torch
import torch.nn as nn

# Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical


def polynomial_cutoff(r: torch.Tensor, r_max: float) -> torch.Tensor:
    """C^2-smooth polynomial cutoff envelope function [D]:

    f_cut(r) = 1 - 10(r/r_max)^3 + 15(r/r_max)^4 - 6(r/r_max)^5 for r <= r_max, else 0.

    Guarantees f_cut(r_max) = 0, f'_cut(r_max) = 0, and f''_cut(r_max) = 0.
    """
    u = r / r_max
    u_clamped = torch.clamp(u, min=0.0, max=1.0)
    envelope = (
        1.0
        - 10.0 * (u_clamped**3)
        + 15.0 * (u_clamped**4)
        - 6.0 * (u_clamped**5)
    )
    mask = (r <= r_max).to(r.dtype)
    return envelope * mask


class GaussianSmearing(nn.Module):
    """Gaussian radial basis function expansion with C^2 polynomial cutoff [D]."""

    def __init__(
        self,
        start: float = 0.0,
        stop: float = 5.0,
        num_gaussians: int = 32,
    ) -> None:
        super().__init__()
        self.start = float(start)
        self.stop = float(stop)
        self.num_gaussians = int(num_gaussians)

        offset = torch.linspace(start, stop, num_gaussians)
        diff = offset[1] - offset[0] if num_gaussians > 1 else torch.tensor(1.0)
        coeff = -0.5 / (diff**2)
        self.register_buffer("offset", offset)
        self.register_buffer("coeff", coeff)

    def forward(self, dist: torch.Tensor) -> torch.Tensor:
        """Expand scalar distances into Gaussian radial basis vectors."""
        dist_expanded = dist.unsqueeze(-1)
        diff = dist_expanded - self.offset
        return torch.exp(self.coeff * torch.pow(diff, 2)) * polynomial_cutoff(
            dist_expanded, self.stop
        )


class BesselBasis(nn.Module):
    """Spherical Bessel basis functions with C^2 polynomial cutoff [D]."""

    def __init__(
        self,
        r_max: float = 5.0,
        num_basis: int = 32,
    ) -> None:
        super().__init__()
        self.r_max = float(r_max)
        self.num_basis = int(num_basis)
        freq = torch.arange(1, num_basis + 1, dtype=torch.float64) * math.pi / r_max
        self.register_buffer("freq", freq)
        self.register_buffer(
            "norm_factor",
            torch.tensor(math.sqrt(2.0 / r_max), dtype=torch.float64),
        )

    def forward(self, dist: torch.Tensor) -> torch.Tensor:
        """Expand scalar distances into spherical Bessel basis vectors."""
        dist_expanded = dist.unsqueeze(-1)
        freq = self.freq.to(dist.dtype)
        norm = self.norm_factor.to(dist.dtype)

        # Handle r -> 0 smoothly: sin(n*pi*r/r_max)/r -> n*pi/r_max
        r_safe = torch.clamp(dist_expanded, min=1e-8)
        bessel = torch.sin(freq * r_safe) / r_safe
        # For very small r, replace with exact analytical limit
        is_zero = dist_expanded < 1e-8
        bessel = torch.where(is_zero, freq, bessel)
        basis = norm * bessel
        return basis * polynomial_cutoff(dist_expanded, self.r_max)


class RadialBasis(nn.Module):
    """Unified radial basis expansion selector."""

    def __init__(
        self,
        num_radial_basis: int = 32,
        r_max: float = 5.0,
        basis_type: Literal["gaussian", "bessel"] = "gaussian",
    ) -> None:
        super().__init__()
        self.num_radial_basis = num_radial_basis
        self.r_max = r_max
        self.basis_type = basis_type
        if basis_type == "gaussian":
            self.basis = GaussianSmearing(
                start=0.0, stop=r_max, num_gaussians=num_radial_basis
            )
        else:
            self.basis = BesselBasis(r_max=r_max, num_basis=num_radial_basis)

    def forward(self, dist: torch.Tensor) -> torch.Tensor:
        return self.basis(dist)
