import typing

class Atom:
    """
    Represents a single atom in a molecule.
    """
    def __init__(self, symbol: str, atomic_number: int, x: float, y: float, z: float):
        if atomic_number <= 0:
            raise ValueError(f"Atomic number must be strictly positive, got {atomic_number} for symbol '{symbol}'")
        self.symbol = symbol
        self.atomic_number = atomic_number
        self.x = x
        self.y = y
        self.z = z

    def __repr__(self):
        return f"Atom(symbol='{self.symbol}', Z={self.atomic_number}, x={self.x}, y={self.y}, z={self.z})"

class Molecule:
    """
    Represents a collection of atoms.
    """
    def __init__(self, name: str = ""):
        self.name = name
        self.atoms: typing.List[Atom] = []

    def add_atom(self, atom: Atom):
        self.atoms.append(atom)

    @classmethod
    def from_xyz(cls, xyz_string: str) -> 'Molecule':
        """
        Parses an XYZ format string and returns a Molecule instance.
        """
        lines = [line.strip() for line in xyz_string.strip().splitlines() if line.strip()]
        if not lines:
            raise ValueError("Empty XYZ string")
        
        try:
            num_atoms = int(lines[0])
        except ValueError:
            raise ValueError("First line of XYZ must be an integer representing the number of atoms.")
            
        name = lines[1] if len(lines) > 1 else "Unknown"
        molecule = cls(name=name)
        
        # Periodic table mapping up to 118
        symbol_to_z = {
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
            "Md": 101, "No": 102, "Lr": 103, "Rf": 104, "Db": 105, "Sg": 106, "Bh": 107, "Hs": 108, "Mt": 109, "Ds": 110,
            "Rg": 111, "Cn": 112, "Nh": 113, "Fl": 114, "Mc": 115, "Lv": 116, "Ts": 117, "Og": 118
        }
        
        for i in range(2, min(2 + num_atoms, len(lines))):
            parts = lines[i].split()
            if len(parts) >= 4:
                symbol = parts[0]
                try:
                    x, y, z = map(float, parts[1:4])
                except ValueError:
                    raise ValueError(f"Invalid coordinates at line {i+1}: {lines[i]}")
                
                # Fetch atomic number, defaulting to 0 if unknown so the Atom class catches it
                atomic_number = symbol_to_z.get(symbol.capitalize(), 0)
                
                atom = Atom(symbol=symbol, atomic_number=atomic_number, x=x, y=y, z=z)
                molecule.add_atom(atom)
                
        return molecule

    def __repr__(self):
        return f"Molecule(name='{self.name}', atoms={len(self.atoms)})"
