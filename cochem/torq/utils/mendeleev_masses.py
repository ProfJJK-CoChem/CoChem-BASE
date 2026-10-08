"""Mendeleev Monoisotopic Mass Retrieval Engine for CoChem-TORQ."""

from __future__ import annotations

from typing import List, Sequence, Union
import mendeleev
import torch

# Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical

_MONOISOTOPIC_CACHE: dict[int, float] = {}


def query_single_monoisotopic_mass(z: int) -> float:
    """Resolve a measured principal isotope; ghost Z=0 has exact zero mass."""
    if z == 0:
        return 0.0
    from cochem_base.physics.isotopes import get_isotope_mass
    return get_isotope_mass(mendeleev.element(int(z)).symbol)


def get_monoisotopic_masses(
    atomic_numbers: Union[Sequence[int], torch.Tensor, List[int]],
    device: Union[torch.device, str] = "cpu",
    dtype: torch.dtype = torch.float64,
) -> torch.Tensor:
    """Retrieve monoisotopic masses dynamically matching active device and dtype. [M]

    Parameters
    ----------
    atomic_numbers : Sequence[int] or torch.Tensor
        IUPAC atomic numbers Z.
    device : torch.device or str
        Target PyTorch compute device.
    dtype : torch.dtype
        Target floating point precision.

    Returns
    -------
    torch.Tensor
        1D tensor of monoisotopic masses in atomic mass units (u).
    """
    if isinstance(atomic_numbers, torch.Tensor):
        z_list = atomic_numbers.cpu().to(torch.int64).tolist()
    else:
        z_list = [int(z) for z in atomic_numbers]

    masses = [query_single_monoisotopic_mass(z) for z in z_list]
    return torch.tensor(masses, dtype=dtype, device=device)
