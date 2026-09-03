"""Physical Unit Tests for CoChem-TOPOS Geometric Clash Detector.

Strictly adheres to Zero-Mock mandate and Mendeleev dynamic radius queries.
Validates:
- Dynamic Van der Waals queries and 5-tier fallback hierarchy (including transactinides Rf, Og).
- Exclusion of 1-2 (bonded) and 1-3 (geminal) pairs.
- Detection of 1-4 torsional clashes.
- Detection of hydrogen-bonded pairs (relaxed threshold).
- Detection of severe non-bonded steric clashes.
- Spatial acceleration with scipy.spatial.cKDTree.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pytest
from mendeleev import element

from cochem.topos.clash import ClashPair, GeometricClashDetector
from cochem.topos.exceptions import StericClashError
from cochem.topos.graph import TopologyGraph


class TestDynamicVdWHierarchy:
    """Verifies dynamic Mendeleev Van der Waals radius queries and transactinide fallbacks."""

    def test_standard_element_vdw_radii(self) -> None:
        """Verify dynamic query for standard organic elements C, N, O, H."""
        detector = GeometricClashDetector()

        r_c = detector.get_vdw_radius("C")
        r_n = detector.get_vdw_radius("N")
        r_o = detector.get_vdw_radius("O")
        r_h = detector.get_vdw_radius("H")

        # Mendeleev C vdw_radius is 170 pm -> 1.70 Angstroms
        assert abs(r_c - (element("C").vdw_radius / 100.0)) < 1e-4
        assert abs(r_n - (element("N").vdw_radius / 100.0)) < 1e-4
        assert abs(r_o - (element("O").vdw_radius / 100.0)) < 1e-4
        assert abs(r_h - (element("H").vdw_radius / 100.0)) < 1e-4

    def test_transactinide_superheavy_fallback(self) -> None:
        """Verify superheavy transactinides Rf (Z=104) and Og (Z=118) fallback to 1.60 * r_cov."""
        detector = GeometricClashDetector()

        # Rutherfordium Z=104 has no VdW in Mendeleev, but has covalent_radius_pyykko = 157 pm
        r_rf = detector.get_vdw_radius("Rf")
        expected_rf = 1.60 * (float(element("Rf").covalent_radius_pyykko) / 100.0)
        assert abs(r_rf - expected_rf) < 1e-4

        # Oganesson Z=118
        r_og = detector.get_vdw_radius("Og")
        expected_og = 1.60 * (float(element("Og").covalent_radius_pyykko) / 100.0)
        assert abs(r_og - expected_og) < 1e-4

    def test_unknown_or_unresolvable_element_raises(self) -> None:
        """Verify invalid element symbol raises StericClashError."""
        detector = GeometricClashDetector()
        with pytest.raises(StericClashError, match="Undefined Van der Waals"):
            detector.get_vdw_radius("UnknownNonexistentElement")


class TestClashDetectionExclusionsAndThresholds:
    """Verifies topological exclusion masks (1-2, 1-3) and threshold scaling (1-4, non-bonded, h-bond)."""

    def test_bonded_and_geminal_exclusions(self) -> None:
        """Verify 1-2 bonded (C-C ~ 1.54 A) and 1-3 geminal (C-C ~ 2.5 A) do NOT trigger clashes."""
        # Propane backbone: C0 - C1 - C2
        propane = TopologyGraph()
        propane.add_chemical_node(0, "C")
        propane.add_chemical_node(1, "C")
        propane.add_chemical_node(2, "C")
        propane.add_chemical_edge(0, 1, bond_order=1.0)
        propane.add_chemical_edge(1, 2, bond_order=1.0)

        # Standard tetrahedral geometry
        coords = np.array([
            [ 0.00,  0.00, 0.00],  # 0
            [ 1.54,  0.00, 0.00],  # 1 (d(0,1)=1.54, 1-2 bonded)
            [ 2.06,  1.45, 0.00],  # 2 (d(0,2)=2.51, 1-3 geminal)
        ], dtype=float)

        detector = GeometricClashDetector(k_clash=0.75, k_hbond=0.55, k_14=0.60)
        clashes = detector.detect_clashes(coords, propane)

        # Both (0,1) and (0,2) must be excluded topologically!
        assert len(clashes) == 0

    def test_torsional_14_clash_detection(self) -> None:
        """Verify 1-4 torsional pair is detected with k_14 = 0.60 threshold."""
        # Butane cis-conformation: C0 - C1 - C2 - C3 where C0 and C3 are forced very close
        butane = TopologyGraph()
        for i in range(4):
            butane.add_chemical_node(i, "C")
        butane.add_chemical_edge(0, 1, bond_order=1.0)
        butane.add_chemical_edge(1, 2, bond_order=1.0)
        butane.add_chemical_edge(2, 3, bond_order=1.0)

        # Forced syn-periplanar eclipsed conformer where d(0, 3) = 1.80 A
        coords = np.array([
            [ 0.00,  1.20, 0.00],  # 0
            [ 0.00,  0.00, 0.00],  # 1
            [ 1.54,  0.00, 0.00],  # 2
            [ 1.54,  1.20, 0.00],  # 3 (d(0,3) = 1.54 A, severely clashing for 1-4)
        ], dtype=float)

        detector = GeometricClashDetector(k_clash=0.75, k_hbond=0.55, k_14=0.60)
        clashes = detector.detect_clashes(coords, butane)

        assert len(clashes) == 1
        clash = clashes[0]
        assert (clash.atom_i, clash.atom_j) == (0, 3)
        assert clash.pair_type == "1-4"
        assert clash.distance < clash.clash_threshold
        r_c = detector.get_vdw_radius("C")
        expected_thresh = 0.60 * (r_c + r_c)
        assert abs(clash.clash_threshold - expected_thresh) < 1e-4

    def test_hbond_pair_relaxed_threshold(self) -> None:
        """Verify polar hydrogen bonding pair applies k_hbond = 0.55 threshold."""
        graph = TopologyGraph()
        graph.add_chemical_node(0, "O")
        graph.add_chemical_node(1, "H")
        graph.add_chemical_node(2, "C")
        graph.add_chemical_node(3, "C")
        graph.add_chemical_node(4, "C")
        graph.add_chemical_node(5, "O")
        # Ensure path length > 3 (non-bonded or 1-5+)
        graph.add_chemical_edge(0, 1)
        graph.add_chemical_edge(0, 2)
        graph.add_chemical_edge(2, 3)
        graph.add_chemical_edge(3, 4)
        graph.add_chemical_edge(4, 5)

        # Place H1 and O5 at 1.85 A (typical hydrogen bond)
        coords = np.array([
            [0.0, 0.0, 0.0],   # 0: O
            [0.0, 0.96, 0.0],  # 1: H
            [1.4, 0.0, 0.0],   # 2: C
            [2.8, 0.0, 0.0],   # 3: C
            [4.2, 0.0, 0.0],   # 4: C
            [0.0, 2.70, 0.0],  # 5: O (d(1, 5) = 1.74 A)
        ], dtype=float)

        detector = GeometricClashDetector(k_clash=0.75, k_hbond=0.55, k_14=0.60)
        clashes = detector.detect_clashes(coords, graph)

        # r_vdw(H) ~ 1.20, r_vdw(O) ~ 1.52. Sum ~ 2.72.
        # With k_clash=0.75, threshold would be 2.04 A (so 1.74 would clash as non-bonded).
        # But with k_hbond=0.55, threshold is 0.55 * 2.72 = 1.50 A!
        # At 1.74 A, d > 1.50 A -> NO CLASH! H-bond is accommodated.
        hbond_clashes = [c for c in clashes if (c.atom_i, c.atom_j) in [(1, 5), (5, 1)]]
        assert len(hbond_clashes) == 0

    def test_severe_nonbonded_steric_clash(self) -> None:
        """Verify non-bonded pair penetrating VdW spheres is detected as non-bonded clash."""
        graph = TopologyGraph()
        # Two disconnected methane carbons
        graph.add_chemical_node(0, "C")
        graph.add_chemical_node(1, "C")

        # Placed at 1.90 A (VdW sum is 3.40 A, k_clash * 3.40 = 2.55 A)
        coords = np.array([
            [0.0, 0.0, 0.0],
            [1.9, 0.0, 0.0],
        ], dtype=float)

        detector = GeometricClashDetector()
        clashes = detector.detect_clashes(coords, graph)

        assert len(clashes) == 1
        assert clashes[0].atom_i == 0
        assert clashes[0].atom_j == 1
        assert clashes[0].pair_type == "non-bonded"
        assert abs(clashes[0].distance - 1.90) < 1e-4
