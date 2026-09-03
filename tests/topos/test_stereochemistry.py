"""Physical Unit Tests for CoChem-TOPOS Stereocenter & Chirality Detector.

Strictly adheres to Zero-Mock mandate.
Validates:
- Coordinate-frame-invariant vector triple product parity on L-alanine (S) and D-alanine (R).
- Degenerate/planar chiral configuration error handling.
- Double bond E/Z stereochemical assignment on (E)- and (Z)-but-2-ene.
"""

from __future__ import annotations

import numpy as np
import pytest

from cochem.topos.exceptions import ChiralityAssignmentError
from cochem.topos.stereochemistry import (
    assign_double_bond_stereo,
    assign_tetrahedral_chirality,
)


class TestTetrahedralChirality:
    """Verifies vector triple product parity and CIP chirality assignment."""

    def test_l_alanine_is_s_enantiomer(self) -> None:
        """Verify L-alanine evaluates strictly to Sinister (S) stereoisomer.
        
        Indices:
          0: Chiral C_alpha (center)
          1: -NH2 (Priority 1, N=7)
          2: -COOH (Priority 2, C bonded to (O,O,O))
          3: -CH3 (Priority 3, C bonded to (H,H,H))
          4: -H (Priority 4, H=1)
        """
        # Authentic L-alanine (S) coordinates in Angstroms
        coords = np.array([
            [ 0.000,  0.000,  0.000],  # 0: C_alpha
            [ 0.000,  1.458,  0.000],  # 1: N (-NH2)
            [-1.520, -0.420,  0.000],  # 2: C (-COOH)
            [ 0.780, -0.650,  1.210],  # 3: C (-CH3)
            [ 0.520, -0.360, -0.890],  # 4: H
        ], dtype=float)

        configuration = assign_tetrahedral_chirality(
            coords=coords,
            center_idx=0,
            priority_indices=(1, 2, 3, 4),
        )
        assert configuration == "S"

    def test_d_alanine_is_r_enantiomer(self) -> None:
        """Verify D-alanine evaluates strictly to Rectus (R) stereoisomer."""
        # Authentic D-alanine (R) coordinates in Angstroms
        coords = np.array([
            [ 0.000,  0.000,  0.000],  # 0: C_alpha
            [ 0.000,  1.458,  0.000],  # 1: N (-NH2)
            [ 1.520, -0.420,  0.000],  # 2: C (-COOH)
            [-0.780, -0.650,  1.210],  # 3: C (-CH3)
            [-0.520, -0.360, -0.890],  # 4: H
        ], dtype=float)

        configuration = assign_tetrahedral_chirality(
            coords=coords,
            center_idx=0,
            priority_indices=(1, 2, 3, 4),
        )
        assert configuration == "R"

    def test_planar_degenerate_geometry_raises(self) -> None:
        """Verify coplanar ligands produce delta_chiral == 0 and raise ChiralityAssignmentError."""
        planar_coords = np.array([
            [ 0.0,  0.0, 0.0],  # center
            [ 1.0,  0.0, 0.0],  # 1
            [ 0.0,  1.0, 0.0],  # 2
            [-1.0,  0.0, 0.0],  # 3
            [ 0.0, -1.0, 0.0],  # 4
        ], dtype=float)

        with pytest.raises(ChiralityAssignmentError, match="Planar or degenerate"):
            assign_tetrahedral_chirality(
                coords=planar_coords,
                center_idx=0,
                priority_indices=(1, 2, 3, 4),
            )


class TestDoubleBondStereo:
    """Verifies E/Z torsional dihedral boundary assignment."""

    def test_z_but_2_ene(self) -> None:
        """Verify cisoid (Z)-but-2-ene has dihedral |phi| < 90 deg -> 'Z'."""
        coords = np.array([
            [-1.80,  1.05, 0.0],  # 0: C1
            [-0.67,  0.00, 0.0],  # 1: C2
            [ 0.67,  0.00, 0.0],  # 2: C3
            [ 1.80,  1.05, 0.0],  # 3: C4
        ], dtype=float)

        stereo = assign_double_bond_stereo(
            coords=coords,
            substituent_a=0,
            terminus_a=1,
            terminus_b=2,
            substituent_b=3,
        )
        assert stereo == "Z"

    def test_e_but_2_ene(self) -> None:
        """Verify transoid (E)-but-2-ene has dihedral |phi| >= 90 deg -> 'E'."""
        coords = np.array([
            [-1.80,  1.05, 0.0],  # 0: C1
            [-0.67,  0.00, 0.0],  # 1: C2
            [ 0.67,  0.00, 0.0],  # 2: C3
            [ 1.80, -1.05, 0.0],  # 3: C4
        ], dtype=float)

        stereo = assign_double_bond_stereo(
            coords=coords,
            substituent_a=0,
            terminus_a=1,
            terminus_b=2,
            substituent_b=3,
        )
        assert stereo == "E"
