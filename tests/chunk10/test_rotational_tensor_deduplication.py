import numpy as np
from cochem_torq_goat import (
    check_rotational_equivalence,
    compute_rmsd,
    deduplicate_conformers,
)


def test_rotational_constants_screening():
    # Rotational constants within 0.2%
    rot1 = (5000.0, 2500.0, 1200.0)
    rot2 = (5005.0, 2502.0, 1201.0) # max diff is 5/5005 ~ 0.099% < 0.2%
    assert check_rotational_equivalence(rot1, rot2, threshold_rel=0.002) is True

    # Rotational constants differing by 0.5% in A
    rot3 = (5030.0, 2500.0, 1200.0) # diff is 30/5030 ~ 0.59% > 0.2%
    assert check_rotational_equivalence(rot1, rot3, threshold_rel=0.002) is False

    # Rotational constants differing in B
    rot4 = (5000.0, 2520.0, 1200.0) # 20/2520 ~ 0.79% > 0.2%
    assert check_rotational_equivalence(rot1, rot4, threshold_rel=0.002) is False

def test_inertial_defect_and_planar_moments():
    rot1 = (5000.0, 2500.0, 1200.0)
    rot2 = (5001.0, 2500.5, 1200.2)

    # Identical defect
    assert check_rotational_equivalence(
        rot1, rot2, threshold_rel=0.002, defect1=0.05, defect2=0.06, defect_threshold=0.05
    ) is True

    # Discriminating planar vs non-planar by inertial defect
    assert check_rotational_equivalence(
        rot1, rot2, threshold_rel=0.002, defect1=0.05, defect2=1.50, defect_threshold=0.05
    ) is False

    # Discriminating by planar moments
    assert check_rotational_equivalence(
        rot1, rot2, threshold_rel=0.002,
        planar1=(0.02, 10.0, 10.0), planar2=(0.85, 10.0, 10.0)
    ) is False

def test_hungarian_rmsd_permutation_invariance():
    # Formaldehyde: C, O, H1, H2
    syms = ['C', 'O', 'H', 'H']
    coords1 = np.array([
        [0.0, 0.0, 0.0],
        [1.21, 0.0, 0.0],
        [-0.59, 0.94, 0.0],
        [-0.59, -0.94, 0.0],
    ])
    # Swap identical hydrogen positions (index 2 and 3)
    coords2 = np.array([
        [0.0, 0.0, 0.0],
        [1.21, 0.0, 0.0],
        [-0.59, -0.94, 0.0],
        [-0.59, 0.94, 0.0],
    ])

    rmsd = compute_rmsd(coords1, coords2, symbols=syms, symbols2=syms)
    assert rmsd < 1e-4, f'Expected Hungarian matching to resolve permutation symmetry, got rmsd={rmsd}'

def test_deduplicate_conformers_pool():
    syms = ['C', 'O', 'H', 'H']
    c1 = {
        'symbols': syms,
        'coordinates': [
            [0.0, 0.0, 0.0],
            [1.21, 0.0, 0.0],
            [-0.59, 0.94, 0.0],
            [-0.59, -0.94, 0.0],
        ],
        'energy_kcal_rel': 0.0,
    }
    # Permuted copy (same geometry, swapped H indices)
    c2 = {
        'symbols': syms,
        'coordinates': [
            [0.0, 0.0, 0.0],
            [1.21, 0.0, 0.0],
            [-0.59, -0.94, 0.0],
            [-0.59, 0.94, 0.0],
        ],
        'energy_kcal_rel': 0.001,
    }
    # Distinct geometry (stretched C=O and bent)
    c3 = {
        'symbols': syms,
        'coordinates': [
            [0.0, 0.0, 0.0],
            [1.40, 0.0, 0.0],
            [-0.50, 1.20, 0.2],
            [-0.50, -1.20, -0.2],
        ],
        'energy_kcal_rel': 12.5,
    }

    pool = [c1, c2, c3]
    accepted = deduplicate_conformers(pool, delta_rot_rel_threshold=0.002, rmsd_threshold=0.15)
    # c2 should be deduplicated as duplicate of c1, retaining c1 and c3
    assert len(accepted) == 2
