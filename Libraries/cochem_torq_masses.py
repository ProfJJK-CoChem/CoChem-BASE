"""Dynamic Mendeleev monoisotopic mass retrieval with unstable element fallback.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Hardcoded mass dictionaries are strictly forbidden.
All masses are dynamically queried from the mendeleev library.
"""

from __future__ import annotations

import functools
from typing import List, Sequence
from mendeleev import element
import torch


@functools.lru_cache(maxsize=128)
def get_monoisotopic_mass(atomic_number: int) -> float:
    """Dynamically query monoisotopic mass using mendeleev with unstable element fallback. [M]
    
    Parameters
    ----------
    atomic_number : int
        Atomic number Z (0 for ghost atoms, 1 <= Z <= 118).
        
    Returns
    -------
    float
        Monoisotopic mass in unified atomic mass units (u).
    """
    if atomic_number == 0:
        return 0.0  # Ghost atom [M]
    if atomic_number < 0 or atomic_number > 118:
        raise ValueError(f"Atomic number Z={atomic_number} outside valid chemical range [0, 118].")

    el = element(atomic_number)
    stable_isotopes = [
        iso for iso in el.isotopes if iso.abundance is not None and iso.abundance > 0.0
    ]
    if stable_isotopes:
        return float(max(stable_isotopes, key=lambda iso: iso.abundance).mass)

    # Fallback for elements without stable isotopes (e.g. Tc Z=43, Pm Z=61) [D]
    return float(max(el.isotopes, key=lambda iso: (iso.half_life or 0.0, iso.mass_number)).mass)


def get_monoisotopic_masses(atomic_numbers: Sequence[int]) -> List[float]:
    """Dynamically query monoisotopic masses for a sequence of atomic numbers. [M]"""
    return [get_monoisotopic_mass(int(z)) for z in atomic_numbers]


def get_monoisotopic_masses_tensor(
    atomic_numbers: Sequence[int],
    dtype: torch.dtype = torch.float64,
    device: torch.device | str = "cpu",
) -> torch.Tensor:
    """Return dynamic monoisotopic masses as a PyTorch tensor. [M]"""
    masses = get_monoisotopic_masses(atomic_numbers)
    return torch.tensor(masses, dtype=dtype, device=device)
