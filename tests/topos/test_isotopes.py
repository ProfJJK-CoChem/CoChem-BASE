"""Physical Unit Tests for CoChem-TOPOS Dynamic Mendeleev Isotope Subsystem.

Strictly adheres to Zero-Mock mandate and dynamic Mendeleev mass queries.
Verifies dynamic isotopic mass queries, natural abundances, mass matrices,
reduced mass calculations, and kinetic isotope effects (KIE).
"""

from __future__ import annotations

import numpy as np
import pytest
from mendeleev import element

from cochem.topos.graph import TopologyGraph
from cochem.topos.isotopes import (
    IsotopeManager,
    IsotopeNodeSpec,
    get_isotope_info,
    get_isotope_mass,
)


def build_ethanol() -> TopologyGraph:
    """Builds authentic topological representation of ethanol (CH3-CH2-OH)."""
    graph = TopologyGraph()
    # Node 0: Methyl C
    graph.add_chemical_node(0, "C", formal_charge=0, hybridization="sp3")
    # Node 1: Methylene C
    graph.add_chemical_node(1, "C", formal_charge=0, hybridization="sp3")
    # Node 2: Hydroxyl O
    graph.add_chemical_node(2, "O", formal_charge=0, hybridization="sp3")
    # Node 3: Hydroxyl H
    graph.add_chemical_node(3, "H", formal_charge=0, hybridization="sp3")

    graph.add_chemical_edge(0, 1, bond_order=1.0)
    graph.add_chemical_edge(1, 2, bond_order=1.0)
    graph.add_chemical_edge(2, 3, bond_order=1.0)
    return graph


class TestIsotopes:
    """Verifies dynamic Mendeleev isotope assignment and physical mass invariants."""

    def test_deuterated_ethanol_hydroxyl_substitution(self) -> None:
        """Deuterate ethanol at hydroxyl position (assert m_D matches dynamic mendeleev isotopic mass for 2H

        [~2.0141 Da], natural abundance matches mendeleev abundance [~0.0145%, within CIAAW terrestrial range
        0.0115%-0.0150%], reduced mass shift delta_mu > 0).
        """
        ethanol = build_ethanol()
        m_H_initial = float(ethanol.nodes[3]["mass"])

        # Mendeleev ground-truth query
        elem_h = element("H")
        iso_2h = [iso for iso in elem_h.isotopes if iso.mass_number == 2][0]
        expected_d_mass = float(iso_2h.mass)
        expected_d_abundance = float(iso_2h.abundance)

        # Confirm dynamic mendeleev bounds
        assert abs(expected_d_mass - 2.01410178) < 1e-4
        assert 0.0115 <= expected_d_abundance <= 0.0150

        # Assign isotope 2H (Deuterium) to hydroxyl hydrogen (node 3)
        deuterated = IsotopeManager.assign_isotope(ethanol, atom_idx=3, mass_number=2)

        d_node = deuterated.nodes[3]
        assert abs(d_node["mass"] - expected_d_mass) < 1e-7
        assert d_node["mass_number"] == 2
        assert abs(d_node["abundance"] - expected_d_abundance) < 1e-7
        assert d_node["is_isotope"] is True

        # Verify get_isotope_mass helper and IsotopeNodeSpec contract
        assert abs(get_isotope_mass("H", 2) - expected_d_mass) < 1e-7
        info = get_isotope_info("H", 2)
        assert isinstance(info, IsotopeNodeSpec)
        assert info.element_symbol == "H"
        assert info.mass_number == 2
        assert abs(info.atomic_mass - expected_d_mass) < 1e-7
        assert info.natural_abundance is not None
        assert abs(info.natural_abundance - expected_d_abundance) < 1e-7

        # Reduced mass calculation for O-H vs O-D bond
        m_O = float(deuterated.nodes[2]["mass"])
        mu_OH = IsotopeManager.compute_reduced_mass(m_O, m_H_initial)
        mu_OD = IsotopeManager.compute_reduced_mass(m_O, expected_d_mass)

        delta_mu = mu_OD - mu_OH
        assert delta_mu > 0

        # Physical KIE frequency shift ratio nu1/nu2 = sqrt(mu2/mu1) ~ 1.37
        kie_shift = IsotopeManager.compute_kie_shift(mu_OH, mu_OD)
        assert kie_shift > 1.35
        assert kie_shift < 1.40

        # Mass matrix M = diag(m_1, ..., m_|V|)
        mass_matrix = IsotopeManager.compute_mass_matrix(deuterated)
        assert mass_matrix.shape == (4, 4)
        assert np.allclose(np.diag(mass_matrix), [
            deuterated.nodes[0]["mass"],
            deuterated.nodes[1]["mass"],
            deuterated.nodes[2]["mass"],
            expected_d_mass,
        ])

    def test_carbon_13_labeling(self) -> None:
        """Verify dynamic isotope assignment for 13C carbon labeling."""
        graph = TopologyGraph()
        graph.add_chemical_node(0, "C", formal_charge=0, hybridization="sp3")
        elem_c = element("C")
        iso_13c = [iso for iso in elem_c.isotopes if iso.mass_number == 13][0]

        labeled = IsotopeManager.assign_isotope(graph, atom_idx=0, mass_number=13)
        assert abs(labeled.nodes[0]["mass"] - float(iso_13c.mass)) < 1e-7
        assert abs(labeled.nodes[0]["abundance"] - float(iso_13c.abundance)) < 1e-7
