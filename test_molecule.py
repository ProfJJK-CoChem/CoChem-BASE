import pytest

from cochem_base.io.molecule_definition import Atom, Molecule


def test_molecule_valid_parsing():
    """Test valid xyz parsing using pytest assertions."""
    xyz_data = '''3
Water Molecule
O 0.000 0.000 0.117
H 0.000 0.757 -0.477
H 0.000 -0.757 -0.477
'''
    mol = Molecule.from_xyz(xyz_data)
    assert len(mol.atoms) == 3
    assert mol.atoms[0].symbol == 'O'
    assert mol.atoms[1].symbol == 'H'
    assert mol.atoms[2].symbol == 'H'


def test_molecule_invalid_symbol():
    """Test strict positivity validation for invalid symbols."""
    invalid_xyz = '''1
Invalid
X 0.0 0.0 0.0
'''
    with pytest.raises(ValueError, match="Atomic number must be strictly positive"):
        Molecule.from_xyz(invalid_xyz)


def test_atom_negative_z():
    """Test strict positivity validation for negative Z."""
    with pytest.raises(ValueError, match="Atomic number must be strictly positive"):
        Atom("U", -92, 0, 0, 0)
