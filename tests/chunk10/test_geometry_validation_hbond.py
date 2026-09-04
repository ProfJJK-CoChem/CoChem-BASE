import numpy as np

from cochem.topos.geometry_validation import (
    GeometryValidator,
    get_covalent_radius,
    get_vdw_radius,
)


def test_vdw_and_covalent_radii():
    # Dynamic radii from mendeleev
    r_vdw_h = get_vdw_radius('H')
    r_vdw_o = get_vdw_radius('O')
    r_vdw_cl = get_vdw_radius('Cl')
    assert 1.0 < r_vdw_h < 1.4
    assert 1.4 < r_vdw_o < 1.7
    assert 1.6 < r_vdw_cl < 2.0

    r_cov_h = get_covalent_radius('H')
    r_cov_c = get_covalent_radius('C')
    r_cov_o = get_covalent_radius('O')
    assert 0.25 < r_cov_h < 0.45
    assert 0.65 < r_cov_c < 0.85
    assert 0.55 < r_cov_o < 0.75

def test_water_dimer_hb_relaxation():
    validator = GeometryValidator()
    # Water dimer: donor H is atom 2, acceptor O is atom 3
    # O1 at (0, 0, 0), H1 at (0.75, 0.58, 0), H2 (donor) at (-0.75, 0.58, 0)
    # O2 at (-1.8, 1.4, 0), H3 at (-2.4, 0.8, 0), H4 at (-1.8, 2.3, 0)
    # Distance between H2 and O2 is ~1.32 A (close H-bond)
    # Under standard 0.65 * (1.20 + 1.52) = 1.768 A, it would trigger a clash!
    # Under relaxed 0.50 * (1.20 + 1.52) = 1.36 A, if distance is 1.45 A it passes!
    atoms = ['O', 'H', 'H', 'O', 'H', 'H']
    coords = np.array([
        [0.0, 0.0, 0.0],
        [0.757, 0.586, 0.0],
        [-0.757, 0.586, 0.0],  # Donor H
        [-1.800, 1.400, 0.0],  # Acceptor O, dist to atom 2 is ~1.32 A
        [-2.400, 0.800, 0.0],
        [-1.800, 2.360, 0.0],
    ])
    bonds = [(0, 1, 1.0), (0, 2, 1.0), (3, 4, 1.0), (3, 5, 1.0)]

    # Set H2-O2 distance to 1.45 A:
    # 0.50 * (1.20 + 1.52) = 1.36 A < 1.45 A (no clash with HB exemption)
    # Standard threshold 0.65 * (1.20 + 1.52) = 1.768 A > 1.45 A (would clash without exemption)
    h2_pos = np.array([-0.757, 0.586, 0.0])
    o2_pos = h2_pos + np.array([-1.45, 0.0, 0.0])
    coords[3] = o2_pos

    clashes = validator.validate_steric_contacts(atoms, coords, bonds=bonds)
    assert len(clashes) == 0, f'Expected no clashes for 1.45 A H-bond, got: {clashes}'

    # Now test an unphysical severe clash: H2 and O2 at 0.9 A (< 1.36 A)
    coords[3] = h2_pos + np.array([-0.90, 0.0, 0.0])
    clashes_severe = validator.validate_steric_contacts(atoms, coords, bonds=bonds)
    assert len(clashes_severe) >= 1
    assert any(c.atom_indices == [2, 3] for c in clashes_severe)

def test_halogen_bond_relaxation():
    validator = GeometryValidator()
    # Cl...O halogen bond contact.
    # vdw(Cl) ~ 1.75, vdw(O) ~ 1.52 -> sum ~ 3.27 A
    # Standard 0.65 threshold: ~ 2.125 A
    # Relaxed 0.50 threshold: ~ 1.635 A
    # A contact at 1.85 A should be allowed under halogen bond relaxation!
    atoms = ['C', 'Cl', 'O', 'C']
    coords = np.array([
        [0.0, 0.0, 0.0],
        [1.76, 0.0, 0.0],   # Cl
        [3.61, 0.0, 0.0],   # O, dist to Cl is 1.85 A
        [4.80, 0.0, 0.0],
    ])
    bonds = [(0, 1, 1.0), (2, 3, 1.0)]
    clashes = validator.validate_steric_contacts(atoms, coords, bonds=bonds)
    assert len(clashes) == 0, f'Expected halogen bond at 1.85 A to be allowed, got: {clashes}'

    # Non-halogen, non-HB pair (e.g. C...C at 1.85 A) must trigger standard clash
    atoms_cc = ['C', 'C', 'C', 'C']
    clashes_cc = validator.validate_steric_contacts(atoms_cc, coords, bonds=bonds)
    assert len(clashes_cc) >= 1
