"""Physical Unit Tests for CoChem-TOPOS Symmetry Subsystem.

Strictly adheres to Zero-Mock mandate and dynamic Mendeleev mass queries.
Verifies Weisfeiler-Lehman (1-WL) color refinement, topological-to-spatial symmetry mapping,
and rotational symmetry numbers (sigma_sym) on authentic molecular topologies.
"""

from __future__ import annotations

import numpy as np
import pytest

from cochem.topos.graph import TopologyGraph
from cochem.topos.symmetry import (
    TopologicalSymmetryAnalyzer,
    TopologicalSymmetryResult,
)


class TestSymmetryAnalyzer:
    """Verifies symmetry analysis on authentic physical molecular topologies."""

    def test_water_symmetry_c2v(self) -> None:
        """Verify H2O symmetry yields point group C2v and sigma_sym = 2."""
        # Topologically pure water graph
        water = TopologyGraph()
        water.add_chemical_node(0, "O", formal_charge=0, hybridization="sp3")
        water.add_chemical_node(1, "H", formal_charge=0, hybridization="sp3")
        water.add_chemical_node(2, "H", formal_charge=0, hybridization="sp3")
        water.add_chemical_edge(0, 1, bond_order=1.0)
        water.add_chemical_edge(0, 2, bond_order=1.0)

        # Experimental equilibrium geometry in Angstroms
        coords = np.array([
            [0.0, 0.0, 0.1173],
            [0.0, 0.7572, -0.4692],
            [0.0, -0.7572, -0.4692],
        ], dtype=float)

        # Test with coordinates
        res_spatial = TopologicalSymmetryAnalyzer.analyze(water, coordinates=coords)
        assert isinstance(res_spatial, TopologicalSymmetryResult)
        assert res_spatial.point_group == "C2v"
        assert res_spatial.symmetry_number == 2
        assert res_spatial.rotational_symmetry_number == 2
        assert res_spatial.sigma_sym == 2
        assert res_spatial.is_chiral is False

        # Test topological-only perception (without coordinates)
        res_topo = TopologicalSymmetryAnalyzer.analyze(water, coordinates=None)
        assert res_topo.point_group == "C2v"
        assert res_topo.symmetry_number == 2
        assert res_topo.rotational_symmetry_number == 2
        assert res_topo.sigma_sym == 2
        assert len(res_topo.automorphism_partition) == 2

        # Verify 1-WL orbits: oxygen is single, two hydrogens are symmetrically equivalent
        assert len(res_topo.orbits) == 2
        o_orbit = [orbit for orbit in res_topo.orbits.values() if 0 in orbit][0]
        h_orbit = [orbit for orbit in res_topo.orbits.values() if 1 in orbit][0]
        assert len(o_orbit) == 1
        assert sorted(h_orbit) == [1, 2]

    def test_boron_trifluoride_symmetry_d3h(self) -> None:
        """Verify BF3 symmetry yields point group D3h and sigma_sym = 6."""
        bf3 = TopologyGraph()
        bf3.add_chemical_node(0, "B", formal_charge=0, hybridization="sp2")
        bf3.add_chemical_node(1, "F", formal_charge=0, hybridization="sp3")
        bf3.add_chemical_node(2, "F", formal_charge=0, hybridization="sp3")
        bf3.add_chemical_node(3, "F", formal_charge=0, hybridization="sp3")
        bf3.add_chemical_edge(0, 1, bond_order=1.0)
        bf3.add_chemical_edge(0, 2, bond_order=1.0)
        bf3.add_chemical_edge(0, 3, bond_order=1.0)

        # Planar trigonal geometry with B-F bond length ~ 1.313 Angstroms
        r_bf = 1.313
        coords = np.array([
            [0.0, 0.0, 0.0],
            [r_bf, 0.0, 0.0],
            [-r_bf * 0.5, r_bf * np.sqrt(3) / 2.0, 0.0],
            [-r_bf * 0.5, -r_bf * np.sqrt(3) / 2.0, 0.0],
        ], dtype=float)

        # Spatial symmetry
        res_spatial = TopologicalSymmetryAnalyzer.analyze(bf3, coordinates=coords)
        assert res_spatial.point_group == "D3h"
        assert res_spatial.rotational_symmetry_number == 6
        assert res_spatial.sigma_sym == 6
        assert res_spatial.is_chiral is False

        # Topological symmetry
        res_topo = TopologicalSymmetryAnalyzer.analyze(bf3, coordinates=None)
        assert res_topo.point_group == "D3h"
        assert res_topo.rotational_symmetry_number == 6
        assert res_topo.sigma_sym == 6

        # Verify 1-WL orbits: B in one orbit, all 3 F's in one orbit
        assert len(res_topo.orbits) == 2
        f_orbit = [orbit for orbit in res_topo.orbits.values() if 1 in orbit][0]
        assert sorted(f_orbit) == [1, 2, 3]

    def test_methane_symmetry_td(self) -> None:
        """Verify CH4 tetrahedral symmetry yields Td and sigma_sym = 12."""
        ch4 = TopologyGraph()
        ch4.add_chemical_node(0, "C", formal_charge=0, hybridization="sp3")
        for i in range(1, 5):
            ch4.add_chemical_node(i, "H", formal_charge=0, hybridization="sp3")
            ch4.add_chemical_edge(0, i, bond_order=1.0)

        res = TopologicalSymmetryAnalyzer.analyze(ch4)
        assert res.point_group == "Td"
        assert res.rotational_symmetry_number == 12
        assert res.sigma_sym == 12

    def test_asymmetric_molecule_c1(self) -> None:
        """Verify asymmetric molecule yields C1 point group and sigma_sym = 1."""
        asym = TopologyGraph()
        asym.add_chemical_node(0, "C", formal_charge=0, hybridization="sp3")
        asym.add_chemical_node(1, "H", formal_charge=0, hybridization="sp3")
        asym.add_chemical_node(2, "F", formal_charge=0, hybridization="sp3")
        asym.add_chemical_node(3, "Cl", formal_charge=0, hybridization="sp3")
        asym.add_chemical_node(4, "Br", formal_charge=0, hybridization="sp3")
        for i in range(1, 5):
            asym.add_chemical_edge(0, i, bond_order=1.0)

        res = TopologicalSymmetryAnalyzer.analyze(asym)
        assert res.point_group == "C1"
        assert res.rotational_symmetry_number == 1
        assert res.sigma_sym == 1
