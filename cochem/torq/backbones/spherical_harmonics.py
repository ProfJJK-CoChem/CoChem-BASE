"""Pure-PyTorch Real Spherical Harmonics (l <= 2) for CoChem-TORQ."""

from __future__ import annotations

import math
from typing import Dict, Union
import torch

# Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical

_SQRT_1_OVER_4PI: float = 1.0 / math.sqrt(4.0 * math.pi)  # [D]
_SQRT_3_OVER_4PI: float = math.sqrt(3.0 / (4.0 * math.pi))  # [D]
_SQRT_15_OVER_4PI: float = math.sqrt(15.0 / (4.0 * math.pi))  # [D]
_SQRT_5_OVER_16PI: float = math.sqrt(5.0 / (16.0 * math.pi))  # [D]
_SQRT_15_OVER_16PI: float = math.sqrt(15.0 / (16.0 * math.pi))  # [D]


def real_spherical_harmonics(
    r_hat: torch.Tensor,
    l_max: int = 2,
) -> Dict[int, torch.Tensor]:
    """Evaluate real spherical harmonics for l <= 2 on unit vectors r_hat. [D]

    Parameters
    ----------
    r_hat : torch.Tensor
        Unit direction vectors of shape (..., 3) representing [x, y, z].
    l_max : int
        Maximum angular momentum degree, 0 <= l_max <= 2.

    Returns
    -------
    Dict[int, torch.Tensor]
        Dictionary mapping degree l to tensor of spherical harmonics:
        - l=0: shape (..., 1) -> [Y_0^0]
        - l=1: shape (..., 3) -> [Y_1^-1, Y_1^0, Y_1^1] (y, z, x ordering)
        - l=2: shape (..., 5) -> [Y_2^-2, Y_2^-1, Y_2^0, Y_2^1, Y_2^2]
    """
    if l_max < 0 or l_max > 2:
        raise ValueError(f"l_max must be 0, 1, or 2, got {l_max}")

    x = r_hat[..., 0]
    y = r_hat[..., 1]
    z = r_hat[..., 2]

    harmonics: Dict[int, torch.Tensor] = {}

    # l = 0 [D]
    y0_0 = torch.full_like(x, _SQRT_1_OVER_4PI).unsqueeze(-1)
    harmonics[0] = y0_0

    if l_max >= 1:
        # l = 1 [D]
        y1_neg1 = _SQRT_3_OVER_4PI * y
        y1_0 = _SQRT_3_OVER_4PI * z
        y1_pos1 = _SQRT_3_OVER_4PI * x
        harmonics[1] = torch.stack([y1_neg1, y1_0, y1_pos1], dim=-1)

    if l_max >= 2:
        # l = 2 [D]
        y2_neg2 = _SQRT_15_OVER_4PI * (x * y)
        y2_neg1 = _SQRT_15_OVER_4PI * (y * z)
        y2_0 = _SQRT_5_OVER_16PI * (3.0 * (z**2) - 1.0)
        y2_pos1 = _SQRT_15_OVER_4PI * (x * z)
        y2_pos2 = _SQRT_15_OVER_16PI * (x**2 - y**2)
        harmonics[2] = torch.stack(
            [y2_neg2, y2_neg1, y2_0, y2_pos1, y2_pos2], dim=-1
        )

    return harmonics
