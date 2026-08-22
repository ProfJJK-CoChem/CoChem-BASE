"""Comprehensive physical Zero-Mock test suite for cochem_base.io.molecule_definition.

Validates:
- Full Atom model creation (positional, keyword, auto-inference of Z and symbol).
- Strict positive atomic number validation and non-empty symbol validation.
- Atom mass resolution, coordinate properties, and Euclidean distance calculation.
- Molecule container operations (add, remove, indexing, len, iteration).
- Molecule formula generation adhering to Hill system rules (carbonaceous and non-carbonaceous).
- Accurate molecular weight, geometric center, and center of mass calculations.
- Geometric transformations (translation, origin-centering).
- Interatomic distance matrix computation.
- XYZ parsing, validation, error diagnostics, and formatting round-tripping.
- File I/O operations (from_file, to_file).
- Backward compatibility and lazy resolution in cochem_base.io.
- Strict LF line endings and zero personal path leaks.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import cochem_base.io as io_pkg
from cochem_base.io.molecule_definition import Atom, Molecule
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def molecule_def_file_path() -> Path:
    """Return absolute path to cochem_base/io/molecule_definition.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "io" / "molecule_definition.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_encoding_and_lf_line_endings(molecule_def_file_path: Path) -> None:
    """Verify strictly Unix LF line endings (\n), standard UTF-8 encoding, and no BOM."""
    raw = molecule_def_file_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in molecule_definition.py"
    assert b"\n" in raw, "Missing newline characters in molecule_definition.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in molecule_definition.py"


def test_zero_personal_path_leaks(molecule_def_file_path: Path) -> None:
    """Verify zero personal machine or local user path leakage in molecule_definition.py."""
    lines = molecule_def_file_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in molecule_definition.py: {leaks}"


def test_io_package_lazy_resolution() -> None:
    """Verify that cochem_base.io exports Atom and Molecule."""
    atom_cls = io_pkg.Atom
    assert atom_cls is Atom

    mol_cls = io_pkg.Molecule
    assert mol_cls is Molecule


def test_atom_initialization_and_inference() -> None:
    """Test flexible initialization and automatic Z/symbol inference."""
    # Explicit full
    a1 = Atom(symbol="C", atomic_number=6, x=1.0, y=2.0, z=3.0)
    assert a1.symbol == "C"
    assert a1.atomic_number == 6
    assert a1.x == 1.0
    assert a1.y == 2.0
    assert a1.z == 3.0
    assert a1.coordinates == (1.0, 2.0, 3.0)
    assert math.isclose(a1.mass, 12.011, rel_tol=1e-3)

    # Auto-infer atomic_number from symbol
    a2 = Atom("Fe", x=0.0, y=0.0, z=0.0)
    assert a2.symbol == "Fe"
    assert a2.atomic_number == 26
    assert math.isclose(a2.mass, 55.845, rel_tol=1e-3)

    # Auto-infer symbol from atomic_number
    a3 = Atom(atomic_number=8, x=0.0, y=1.0, z=0.0)
    assert a3.symbol == "O"
    assert a3.atomic_number == 8

    # Positional args
    a4 = Atom("H", 1, 0.5, 0.5, 0.5)
    assert a4.symbol == "H"
    assert a4.atomic_number == 1
    assert a4.coordinates == (0.5, 0.5, 0.5)


def test_atom_validation_and_errors() -> None:
    """Test validation errors for invalid atomic numbers and empty symbols."""
    # Negative atomic number
    with pytest.raises(ValueError, match="Atomic number must be strictly positive"):
        Atom("U", -92, 0, 0, 0)

    # Zero atomic number
    with pytest.raises(ValueError, match="Atomic number must be strictly positive"):
        Atom(symbol="X", atomic_number=0, x=0.0, y=0.0, z=0.0)

    # Empty symbol
    with pytest.raises(ValueError, match="Atom symbol cannot be empty"):
        Atom(symbol="   ", atomic_number=6, x=0.0, y=0.0, z=0.0)


def test_atom_distance_and_repr() -> None:
    """Test Euclidean distance calculation and string representations."""
    a1 = Atom("O", 8, 0.0, 0.0, 0.0)
    a2 = Atom("H", 1, 0.0, 3.0, 4.0)
    assert math.isclose(a1.distance_to(a2), 5.0, abs_tol=1e-9)

    repr_str = repr(a1)
    assert "Atom(symbol='O', Z=8, x=0.0, y=0.0, z=0.0)" in repr_str
    assert str(a1) == repr_str


def test_molecule_container_methods() -> None:
    """Test container behavior: add, remove, len, getitem, iteration."""
    mol = Molecule(name="Methane")
    assert len(mol) == 0
    assert mol.num_atoms == 0

    c = Atom("C", 6, 0.0, 0.0, 0.0)
    mol.add_atom(c)
    assert len(mol) == 1
    assert mol[0].symbol == "C"

    h1 = Atom("H", 1, 1.0, 0.0, 0.0)
    h2 = Atom("H", 1, 0.0, 1.0, 0.0)
    mol.add_atom(h1)
    mol.add_atom(h2)
    assert len(mol) == 3

    # Iteration
    symbols = [atom.symbol for atom in mol]
    assert symbols == ["C", "H", "H"]
    assert mol.symbols == ["C", "H", "H"]
    assert mol.atomic_numbers == [6, 1, 1]

    # Remove atom
    removed = mol.remove_atom(1)
    assert removed.symbol == "H"
    assert len(mol) == 2


def test_molecule_hill_formula_and_composition() -> None:
    """Test Hill system formula generation and element composition."""
    # Empty molecule
    assert Molecule().formula == ""

    # Carbonaceous: Ethanol C2H6O
    ethanol = Molecule(name="Ethanol")
    ethanol.add_atom(Atom("C", 6, 0.0, 0.0, 0.0))
    ethanol.add_atom(Atom("C", 6, 1.5, 0.0, 0.0))
    for _ in range(6):
        ethanol.add_atom(Atom("H", 1, 0.0, 0.0, 0.0))
    ethanol.add_atom(Atom("O", 8, 2.5, 0.0, 0.0))

    assert ethanol.composition == {"C": 2, "H": 6, "O": 1}
    assert ethanol.formula == "C2H6O"

    # Non-carbonaceous: Sulfuric acid H2SO4 -> H2O4S (alphabetical)
    sulfuric = Molecule(name="Sulfuric Acid")
    sulfuric.add_atom(Atom("S", 16, 0.0, 0.0, 0.0))
    for _ in range(4):
        sulfuric.add_atom(Atom("O", 8, 0.0, 0.0, 0.0))
    for _ in range(2):
        sulfuric.add_atom(Atom("H", 1, 0.0, 0.0, 0.0))

    assert sulfuric.composition == {"S": 1, "O": 4, "H": 2}
    assert sulfuric.formula == "H2O4S"

    # Water H2O -> H2O (alphabetical)
    water = Molecule(name="Water")
    water.add_atom(Atom("O", 8, 0.0, 0.0, 0.117))
    water.add_atom(Atom("H", 1, 0.0, 0.757, -0.477))
    water.add_atom(Atom("H", 1, 0.0, -0.757, -0.477))
    assert water.formula == "H2O"


def test_molecule_molecular_weight() -> None:
    """Test standard molecular weight calculation."""
    # Water H2O
    water = Molecule(name="Water")
    water.add_atom(Atom("O", 8, 0.0, 0.0, 0.0))
    water.add_atom(Atom("H", 1, 0.0, 1.0, 0.0))
    water.add_atom(Atom("H", 1, 0.0, -1.0, 0.0))

    expected_mw = 15.999 + 2 * 1.008
    assert math.isclose(water.molecular_weight, expected_mw, rel_tol=1e-4)


def test_molecule_geometry_and_transformations() -> None:
    """Test geometric center, center of mass, translation, and origin centering."""
    mol = Molecule(name="Diatomic")
    mol.add_atom(Atom("C", 6, 0.0, 0.0, 0.0))
    mol.add_atom(Atom("O", 8, 2.0, 0.0, 0.0))

    # Geometric center
    gc = mol.geometric_center
    assert math.isclose(gc[0], 1.0)
    assert math.isclose(gc[1], 0.0)
    assert math.isclose(gc[2], 0.0)

    # Center of mass: (12.011 * 0 + 15.999 * 2) / (12.011 + 15.999) = 31.998 / 28.01 = 1.14237
    com = mol.center_of_mass
    expected_com_x = (12.011 * 0.0 + 15.999 * 2.0) / (12.011 + 15.999)
    assert math.isclose(com[0], expected_com_x, rel_tol=1e-4)

    # Translation
    mol.translate(10.0, -5.0, 3.0)
    assert math.isclose(mol.atoms[0].x, 10.0)
    assert math.isclose(mol.atoms[0].y, -5.0)
    assert math.isclose(mol.atoms[0].z, 3.0)

    # Center at origin
    mol.center_at_origin()
    gc_new = mol.geometric_center
    assert math.isclose(gc_new[0], 0.0, abs_tol=1e-9)
    assert math.isclose(gc_new[1], 0.0, abs_tol=1e-9)
    assert math.isclose(gc_new[2], 0.0, abs_tol=1e-9)


def test_molecule_distance_matrix() -> None:
    """Test pairwise distance matrix computation."""
    mol = Molecule()
    mol.add_atom(Atom("A", 1, 0.0, 0.0, 0.0))
    mol.add_atom(Atom("B", 1, 3.0, 0.0, 0.0))
    mol.add_atom(Atom("C", 1, 0.0, 4.0, 0.0))

    matrix = mol.distance_matrix()
    assert len(matrix) == 3
    assert math.isclose(matrix[0][0], 0.0)
    assert math.isclose(matrix[0][1], 3.0)
    assert math.isclose(matrix[1][0], 3.0)
    assert math.isclose(matrix[0][2], 4.0)
    assert math.isclose(matrix[1][2], 5.0)
    assert math.isclose(matrix[2][1], 5.0)


def test_xyz_parsing_and_serialization_roundtrip() -> None:
    """Test full XYZ string parse and roundtrip serialization."""
    xyz_data = """3
Water Molecule
O 0.000000 0.000000 0.117000
H 0.000000 0.757000 -0.477000
H 0.000000 -0.757000 -0.477000
"""
    mol = Molecule.from_xyz(xyz_data)
    assert mol.name == "Water Molecule"
    assert len(mol) == 3
    assert mol.atoms[0].symbol == "O"
    assert mol.atoms[0].atomic_number == 8

    # Serialize back to XYZ
    exported = mol.to_xyz()
    mol2 = Molecule.from_xyz(exported)
    assert len(mol2) == 3
    assert mol2.name == "Water Molecule"
    assert math.isclose(mol2.atoms[0].z, 0.117, abs_tol=1e-5)


def test_xyz_error_handling() -> None:
    """Test error handling in malformed XYZ inputs."""
    # Empty string
    with pytest.raises(ValueError, match="Empty XYZ string"):
        Molecule.from_xyz("")

    # Non-integer first line
    with pytest.raises(ValueError, match="First line of XYZ must be an integer"):
        Molecule.from_xyz("invalid\ncomment\nC 0 0 0")

    # Negative count
    with pytest.raises(ValueError, match="Number of atoms in XYZ header cannot be negative"):
        Molecule.from_xyz("-5\ncomment\nC 0 0 0")

    # Truncated content
    with pytest.raises(ValueError, match="XYZ string truncated"):
        Molecule.from_xyz("5\ncomment\nC 0.0 0.0 0.0\nH 1.0 0.0 0.0")

    # Invalid coordinates
    with pytest.raises(ValueError, match="Invalid coordinates at line 3"):
        Molecule.from_xyz("1\ncomment\nC not_a_float 0.0 0.0")

    # Incomplete atom line
    with pytest.raises(ValueError, match="Invalid atom definition at line 3"):
        Molecule.from_xyz("1\ncomment\nC 0.0")


def test_file_io_roundtrip(tmp_path: Path) -> None:
    """Test saving and loading Molecule instances from physical XYZ files."""
    xyz_file = tmp_path / "benzene.xyz"
    mol = Molecule(name="Benzene")
    mol.add_atom(Atom("C", 6, 0.0, 1.4, 0.0))
    mol.add_atom(Atom("C", 6, 1.2, 0.7, 0.0))
    mol.add_atom(Atom("H", 1, 0.0, 2.5, 0.0))

    mol.to_file(xyz_file)
    assert xyz_file.is_file()

    loaded = Molecule.from_file(xyz_file)
    assert len(loaded) == 3
    assert loaded.name == "Benzene"
    assert loaded.symbols == ["C", "C", "H"]
