"""
CoChem-BENCH Basis Set Manager
Handles core-valence basis mapping, CABS selection, relativistic variants (-DK).
"""
from typing import Any

HEAVY_ATOMIC_NUMBERS: dict[str, int] = {
    "H": 1, "He": 2, "Li": 3, "Be": 4, "B": 5, "C": 6, "N": 7, "O": 8, "F": 9, "Ne": 10,
    "Na": 11, "Mg": 12, "Al": 13, "Si": 14, "P": 15, "S": 16, "Cl": 17, "Ar": 18,
    "K": 19, "Ca": 20, "Sc": 21, "Ti": 22, "V": 23, "Cr": 24, "Mn": 25, "Fe": 26, "Co": 27, "Ni": 28, "Cu": 29, "Zn": 30,
    "Ga": 31, "Ge": 32, "As": 33, "Se": 34, "Br": 35, "Kr": 36,
    "Rb": 37, "Sr": 38, "Y": 39, "Zr": 40, "Nb": 41, "Mo": 42, "Tc": 43, "Ru": 44, "Rh": 45, "Pd": 46, "Ag": 47, "Cd": 48,
    "In": 49, "Sn": 50, "Sb": 51, "Te": 52, "I": 53, "Xe": 54
}

def map_core_valence_basis_per_element(symbols: list[str], base_cv_basis: str = "aug-cc-pCVTZ") -> dict[str, str]:
    """
    Maps light elements (H, He) to standard correlation-consistent basis without CV,
    and heavier elements to base_cv_basis.
    """
    if not isinstance(symbols, list):
        raise TypeError("symbols must be a list of strings.")

    mapped: dict[str, str] = {}
    light_basis = base_cv_basis.replace("pCV", "pV")
    for s in symbols:
        if not isinstance(s, str):
            raise TypeError(f"Symbol must be a string, got {type(s).__name__}")
        
        elem = s.capitalize()
        if elem not in HEAVY_ATOMIC_NUMBERS:
            raise ValueError(f"Unrecognized chemical symbol: {s}")
            
        if elem in ("H", "He"):
            mapped[elem] = light_basis
        else:
            mapped[elem] = base_cv_basis
    return mapped

def get_cabs_auxiliary_basis(orbital_basis: str) -> str:
    """
    Returns complementary auxiliary basis set (CABS) for F12 calculations.
    """
    if not isinstance(orbital_basis, str):
        raise TypeError(f"orbital_basis must be a string, got {type(orbital_basis).__name__}")

    cabs_registry: dict[str, str] = {
        "cc-pVDZ-F12": "cc-pVDZ-F12-CABS",
        "cc-pVTZ-F12": "cc-pVTZ-F12-CABS",
        "cc-pVQZ-F12": "cc-pVQZ-F12-CABS",
        "aug-cc-pVDZ": "aug-cc-pVDZ/OptRI",
        "aug-cc-pVTZ": "aug-cc-pVTZ/OptRI",
        "aug-cc-pVQZ": "aug-cc-pVQZ/OptRI",
        "def2-SVP": "def2-SVP/C",
        "def2-TZVP": "def2-TZVP/C",
        "def2-QZVP": "def2-QZVP/C"
    }

    if orbital_basis not in cabs_registry:
        raise ValueError(f"No CABS auxiliary basis registered for {orbital_basis}")

    return cabs_registry[orbital_basis]
