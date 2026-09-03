"""Mendeleev Monoisotopic Mass Retrieval Engine for CoChem-TORQ."""

from __future__ import annotations

from typing import List, Sequence, Union
import mendeleev
import torch

# Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical

_MONOISOTOPIC_CACHE: dict[int, float] = {}


def query_single_monoisotopic_mass(z: int) -> float:
    """Query pure monoisotopic mass for atomic number Z using mendeleev. [M], [D]

    Ghost atoms (Z=0) are assigned 0.0 u without querying mendeleev.
    For Z > 0, the isotope with maximum relative abundance is chosen.
    """
    if z == 0:
        return 0.0  # [M] Ghost atom mass

    if z in _MONOISOTOPIC_CACHE:
        return _MONOISOTOPIC_CACHE[z]

    el = mendeleev.element(int(z))
    isotopes = [
        iso
        for iso in el.isotopes
        if iso.abundance is not None and iso.abundance > 0.0
    ]
    if isotopes:
        # Maximize abundance, breaking ties with mass number [D]
        mono_iso = max(
            isotopes,
            key=lambda iso: (iso.abundance or 0.0, iso.mass_number),
        )
        mass_val = float(mono_iso.mass)
    else:
        # Fallback for synthetic/radioactive elements with no stable abundance [D]
        mono_iso = max(el.isotopes, key=lambda iso: iso.mass_number)
        mass_val = float(mono_iso.mass)

    _MONOISOTOPIC_CACHE[z] = mass_val
    return mass_val


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
