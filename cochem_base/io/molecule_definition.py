"""Molecular representation, atom structures, Hill system formula generation, and XYZ format I/O.

Provides immutable and mutable representations of Atoms and Molecules with comprehensive physical calculations.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field, field_validator

from cochem_base.io.atomic_data import get_atomic_data_validator, get_standard_atomic_weight

_SYMBOL_TO_Z: Dict[str, int] = {
    "H": 1, "He": 2, "Li": 3, "Be": 4, "B": 5, "C": 6, "N": 7, "O": 8, "F": 9, "Ne": 10,
    "Na": 11, "Mg": 12, "Al": 13, "Si": 14, "P": 15, "S": 16, "Cl": 17, "Ar": 18, "K": 19, "Ca": 20,
    "Sc": 21, "Ti": 22, "V": 23, "Cr": 24, "Mn": 25, "Fe": 26, "Co": 27, "Ni": 28, "Cu": 29, "Zn": 30,
    "Ga": 31, "Ge": 32, "As": 33, "Se": 34, "Br": 35, "Kr": 36, "Rb": 37, "Sr": 38, "Y": 39, "Zr": 40,
    "Nb": 41, "Mo": 42, "Tc": 43, "Ru": 44, "Rh": 45, "Pd": 46, "Ag": 47, "Cd": 48, "In": 49, "Sn": 50,
    "Sb": 51, "Te": 52, "I": 53, "Xe": 54, "Cs": 55, "Ba": 56, "La": 57, "Ce": 58, "Pr": 59, "Nd": 60,
    "Pm": 61, "Sm": 62, "Eu": 63, "Gd": 64, "Tb": 65, "Dy": 66, "Ho": 67, "Er": 68, "Tm": 69, "Yb": 70,
    "Lu": 71, "Hf": 72, "Ta": 73, "W": 74, "Re": 75, "Os": 76, "Ir": 77, "Pt": 78, "Au": 79, "Hg": 80,
    "Tl": 81, "Pb": 82, "Bi": 83, "Po": 84, "At": 85, "Rn": 86, "Fr": 87, "Ra": 88, "Ac": 89, "Th": 90,
    "Pa": 91, "U": 92, "Np": 93, "Pu": 94, "Am": 95, "Cm": 96, "Bk": 97, "Cf": 98, "Es": 99, "Fm": 100,
    "Md": 101, "No": 102, "Lr": 103, "Rf": 104, "Db": 105, "Sg": 106, "Bh": 107, "Hs": 108, "Mt": 109,
    "Ds": 110, "Rg": 111, "Cn": 112, "Nh": 113, "Fl": 114, "Mc": 115, "Lv": 116, "Ts": 117, "Og": 118,
}

_Z_TO_SYMBOL: Dict[int, str] = {z: sym for sym, z in _SYMBOL_TO_Z.items()}


class Atom(BaseModel):
    """Represents a single atom with 3D Cartesian coordinates and physical properties."""

    symbol: str
    atomic_number: int
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        symbol: Optional[str] = None,
        atomic_number: Optional[int] = None,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        **kwargs: Any,
    ) -> None:
        if symbol is not None and not symbol.strip():
            raise ValueError("Atom symbol cannot be empty")

        if atomic_number is not None and atomic_number <= 0:
            raise ValueError(f"Atomic number must be strictly positive, got {atomic_number}")

        if symbol is None and atomic_number is not None:
            clean_sym = _Z_TO_SYMBOL.get(atomic_number, f"E{atomic_number}")
            super().__init__(symbol=clean_sym, atomic_number=atomic_number, x=x, y=y, z=z, **kwargs)
            return

        if symbol is not None and atomic_number is None:
            clean_sym = symbol.strip()
            norm_sym = clean_sym.capitalize() if len(clean_sym) <= 2 else clean_sym
            z_inferred = _SYMBOL_TO_Z.get(norm_sym, 0)
            if z_inferred <= 0:
                raise ValueError(f"Unknown element symbol '{symbol}'")
            super().__init__(symbol=clean_sym, atomic_number=z_inferred, x=x, y=y, z=z, **kwargs)
            return

        if symbol is not None and atomic_number is not None:
            super().__init__(symbol=symbol.strip(), atomic_number=atomic_number, x=x, y=y, z=z, **kwargs)
            return

        raise ValueError("Either symbol or atomic_number must be provided to instantiate Atom.")

    @property
    def coordinates(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    @property
    def mass(self) -> float:
        return get_standard_atomic_weight(self.symbol)

    def distance_to(self, other: Atom) -> float:
        """Computes Euclidean distance between this atom and another."""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2)

    def __repr__(self) -> str:
        return f"Atom(symbol='{self.symbol}', Z={self.atomic_number}, x={self.x}, y={self.y}, z={self.z})"

    def __str__(self) -> str:
        return self.__repr__()


class Molecule(BaseModel):
    """Collection of Atom instances representing a chemical molecule."""

    name: str = ""
    atoms: List[Atom] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    def __len__(self) -> int:
        return len(self.atoms)

    @property
    def num_atoms(self) -> int:
        return len(self.atoms)

    def __getitem__(self, index: int) -> Atom:
        return self.atoms[index]

    def __iter__(self) -> Any:
        return iter(self.atoms)

    def add_atom(self, atom: Atom) -> None:
        self.atoms.append(atom)

    def remove_atom(self, index: int) -> Atom:
        return self.atoms.pop(index)

    @property
    def symbols(self) -> List[str]:
        return [a.symbol for a in self.atoms]

    @property
    def atomic_numbers(self) -> List[int]:
        return [a.atomic_number for a in self.atoms]

    @property
    def composition(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for a in self.atoms:
            counts[a.symbol] = counts.get(a.symbol, 0) + 1
        return counts

    @property
    def formula(self) -> str:
        """Generates Hill system empirical formula."""
        if not self.atoms:
            return ""

        counts = self.composition
        parts = []

        if "C" in counts:
            c_cnt = counts["C"]
            parts.append(f"C{c_cnt if c_cnt > 1 else ''}")
            if "H" in counts:
                h_cnt = counts["H"]
                parts.append(f"H{h_cnt if h_cnt > 1 else ''}")

            remaining = sorted([k for k in counts if k not in ("C", "H")])
            for elem in remaining:
                cnt = counts[elem]
                parts.append(f"{elem}{cnt if cnt > 1 else ''}")
        else:
            for elem in sorted(counts.keys()):
                cnt = counts[elem]
                parts.append(f"{elem}{cnt if cnt > 1 else ''}")

        return "".join(parts)

    @property
    def molecular_weight(self) -> float:
        return sum(a.mass for a in self.atoms)

    @property
    def geometric_center(self) -> Tuple[float, float, float]:
        if not self.atoms:
            return (0.0, 0.0, 0.0)
        n = len(self.atoms)
        return (
            sum(a.x for a in self.atoms) / n,
            sum(a.y for a in self.atoms) / n,
            sum(a.z for a in self.atoms) / n,
        )

    @property
    def center_of_mass(self) -> Tuple[float, float, float]:
        if not self.atoms:
            return (0.0, 0.0, 0.0)
        total_mass = sum(a.mass for a in self.atoms)
        if total_mass == 0.0:
            return self.geometric_center
        return (
            sum(a.mass * a.x for a in self.atoms) / total_mass,
            sum(a.mass * a.y for a in self.atoms) / total_mass,
            sum(a.mass * a.z for a in self.atoms) / total_mass,
        )

    def translate(self, dx: float, dy: float, dz: float) -> None:
        """Translates all atoms in the molecule by (dx, dy, dz)."""
        for a in self.atoms:
            a.x += dx
            a.y += dy
            a.z += dz

    def center_at_origin(self) -> None:
        """Translates the molecule so its geometric center is at (0, 0, 0)."""
        gc = self.geometric_center
        self.translate(-gc[0], -gc[1], -gc[2])

    def distance_matrix(self) -> List[List[float]]:
        """Computes pairwise Euclidean distance matrix."""
        n = len(self.atoms)
        matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                d = self.atoms[i].distance_to(self.atoms[j])
                matrix[i][j] = d
                matrix[j][i] = d
        return matrix

    def to_xyz(self, comment: Optional[str] = None) -> str:
        """Serializes the molecule to standard XYZ format."""
        comment_line = comment if comment is not None else (self.name or "Molecule")
        lines = [str(len(self.atoms)), comment_line]
        for a in self.atoms:
            lines.append(f"{a.symbol:<2} {a.x:14.6f} {a.y:14.6f} {a.z:14.6f}")
        return "\n".join(lines) + "\n"

    def to_file(self, file_path: Union[str, Path], comment: Optional[str] = None) -> None:
        """Saves molecule to an XYZ file."""
        p = Path(file_path)
        p.write_text(self.to_xyz(comment=comment), encoding="utf-8")

    @classmethod
    def from_file(cls, file_path: Union[str, Path]) -> Molecule:
        """Loads molecule from an XYZ file."""
        p = Path(file_path)
        return cls.from_xyz(p.read_text(encoding="utf-8"))

    @classmethod
    def from_xyz(cls, xyz_string: str) -> Molecule:
        """Parses an XYZ format string."""
        if not xyz_string or not xyz_string.strip():
            raise ValueError("Empty XYZ string")

        raw_lines = xyz_string.strip().splitlines()
        lines = [line.strip() for line in raw_lines if line.strip()]
        if not lines:
            raise ValueError("Empty XYZ string")

        try:
            num_atoms = int(lines[0])
        except ValueError as e:
            raise ValueError("First line of XYZ must be an integer representing atom count") from e

        if num_atoms < 0:
            raise ValueError(f"Number of atoms in XYZ header cannot be negative: {num_atoms}")

        comment = lines[1] if len(lines) > 1 else ""
        atom_lines = lines[2:]

        if len(atom_lines) < num_atoms:
            raise ValueError(f"XYZ string truncated: expected {num_atoms} atoms but found {len(atom_lines)}")

        mol = cls(name=comment)
        for idx, line in enumerate(atom_lines[:num_atoms], start=3):
            tokens = line.split()
            if len(tokens) < 4:
                raise ValueError(f"Invalid atom definition at line {idx}: '{line}'")

            sym = tokens[0]
            try:
                x = float(tokens[1])
                y = float(tokens[2])
                z = float(tokens[3])
            except ValueError as e:
                raise ValueError(f"Invalid coordinates at line {idx}: '{line}'") from e

            mol.add_atom(Atom(symbol=sym, x=x, y=y, z=z))

        return mol

    def __repr__(self) -> str:
        return f"Molecule(name='{self.name}', atoms={len(self.atoms)})"

    def __str__(self) -> str:
        return self.__repr__()


__all__ = ["Atom", "Molecule"]
