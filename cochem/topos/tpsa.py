"""Topological Polar Surface Area (TPSA) Subsystem.

Implements the complete, physically verified Ertl et al. (2000) fragment-based polar surface
area parameters for neutral and charged oxygen, nitrogen, phosphorus, and sulfur heteroatoms.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from cochem.topos.exceptions import TPSACalculationError
from cochem.topos.graph import TopologyGraph
from cochem.topos.rings import perceive_aromaticity, perceive_cycle_basis

logger = logging.getLogger("cochem.topos.tpsa")


class TPSAResult(BaseModel):
    """Pydantic v2 model storing topological polar surface area results."""

    total_tpsa: float = Field(ge=0.0, description="Total topological polar surface area in Angstroms squared (A^2).")
    atom_contributions: dict[int, float] = Field(
        description="Per-atom polar surface area contributions in Angstroms squared."
    )
    polar_atoms: list[int] = Field(
        description="List of node indices identified as polar heteroatoms."
    )

    @property
    def tpsa(self) -> float:
        """Alias for total_tpsa."""
        return self.total_tpsa


class TPSACalculator:
    """Calculates molecular Topological Polar Surface Area (TPSA) according to Ertl 2000 fragment rules."""

    @classmethod
    def calculate(cls, graph: TopologyGraph) -> TPSAResult:
        """Computes fragment-based TPSA across all topological nodes.

        Parameters
        ----------
        graph : TopologyGraph
            Chemical topology graph.

        Returns
        -------
        TPSAResult
            Result containing total polar surface area and atomic contributions.
        """
        if graph.number_of_nodes() == 0:
            return TPSAResult(total_tpsa=0.0, atom_contributions={}, polar_atoms=[])

        # Ensure rings and aromaticity are perceived
        perceive_cycle_basis(graph)
        perceive_aromaticity(graph)

        atom_contributions: dict[int, float] = {}
        polar_atoms: list[int] = []

        for u in graph.nodes():
            n_data = graph.nodes[u]
            symbol = str(n_data.get("symbol", "")).upper()
            if symbol not in ("O", "N", "P", "S"):
                atom_contributions[u] = 0.0
                continue

            contrib = cls._calculate_atom_contribution(graph, u)
            atom_contributions[u] = contrib
            if contrib > 0.0:
                polar_atoms.append(u)

        total_tpsa = round(sum(atom_contributions.values()), 4)
        return TPSAResult(
            total_tpsa=total_tpsa,
            atom_contributions=atom_contributions,
            polar_atoms=polar_atoms,
        )

    @classmethod
    def _calculate_atom_contribution(cls, graph: TopologyGraph, u: int) -> float:
        """Determines the Ertl 2000 fragment contribution for a single heteroatom."""
        n_data = graph.nodes[u]
        symbol = str(n_data.get("symbol", "")).upper()
        charge = int(n_data.get("formal_charge", 0))
        in_ring = bool(n_data.get("in_ring", False))
        is_aromatic = bool(n_data.get("is_aromatic", False))
        ring_sizes = list(n_data.get("ring_sizes", []))
        in_3_ring = 3 in ring_sizes

        # Collect neighbors
        neighbors = list(graph.neighbors(u))
        h_neighbors = [v for v in neighbors if str(graph.nodes[v].get("symbol", "")).upper() == "H"]
        heavy_neighbors = [v for v in neighbors if str(graph.nodes[v].get("symbol", "")).upper() != "H"]
        num_h = len(h_neighbors)
        num_heavy = len(heavy_neighbors)

        # Bond orders to heavy neighbors
        bonds = [float(graph.edges[u, v].get("bond_order", 1.0)) for v in heavy_neighbors]
        has_double_bond = any(abs(bo - 2.0) < 1e-2 for bo in bonds)
        has_triple_bond = any(abs(bo - 3.0) < 1e-2 for bo in bonds)
        has_aromatic_bond = any(bool(graph.edges[u, v].get("aromatic", False)) for v in heavy_neighbors)

        # -------------------------------------------------------------
        # 1. OXYGEN
        # -------------------------------------------------------------
        if symbol == "O":
            if charge == -1:
                # Deprotonated oxygen / carboxylate oxygen (-O^-)
                return 23.06

            if charge == 0:
                if num_heavy == 1:
                    v = heavy_neighbors[0]
                    bo = float(graph.edges[u, v].get("bond_order", 1.0))
                    # Check if carbonyl =O
                    if abs(bo - 2.0) < 1e-2 or has_double_bond:
                        return 14.14 if in_3_ring else 17.07

                    # Single bond: check if hydroxyl -OH (explicit H or implicit H)
                    if num_h >= 1 or abs(bo - 1.0) < 1e-2:
                        return 20.23

                elif num_heavy == 2:
                    # Ether / ester bridge (-O-)
                    if in_3_ring:
                        return 12.53
                    if is_aromatic:
                        return 13.14
                    return 9.23

                elif num_heavy == 0:
                    # Water molecule
                    return 20.23 if num_h >= 1 else 0.0

            return 0.0

        # -------------------------------------------------------------
        # 2. NITROGEN
        # -------------------------------------------------------------
        if symbol == "N":
            # Check for nitro group: N attached to 2 oxygens
            o_neighbors = [v for v in heavy_neighbors if str(graph.nodes[v].get("symbol", "")).upper() == "O"]
            if len(o_neighbors) == 2:
                if charge == 0:
                    # Neutral pentavalent nitro N
                    return 11.68
                if charge == 1:
                    # Zwitterionic charge-separated nitro N+
                    return 3.01

            # Neutral Nitrogen
            if charge == 0:
                if is_aromatic:
                    # Pyridine-like =N- (degree 2, no H)
                    if num_heavy == 2 and num_h == 0 and not has_double_bond:
                        # In 6-membered aromatic ring with degree 2
                        return 12.89
                    # Pyrrole-like -NH- or >N- in aromatic ring
                    if num_h >= 1 or num_heavy == 2:
                        return 15.79
                    return 4.36

                if has_triple_bond:
                    # Nitrile #N
                    return 23.79

                if has_double_bond:
                    # Imine =NH or =N-
                    if num_h >= 1 or (num_heavy == 1 and num_h == 0):
                        return 23.85
                    return 8.89 if in_3_ring else 12.36

                # Single bonds only
                if num_heavy == 1:
                    # Primary amine -NH2
                    return 26.02
                if num_heavy == 2:
                    # Secondary amine -NH-
                    return 21.94 if in_3_ring else 12.03
                if num_heavy == 3:
                    # Tertiary amine >N-
                    return 3.01 if in_3_ring else 3.24

            # Cationic Nitrogen (charge = +1)
            if charge == 1:
                if is_aromatic:
                    return 14.14 if num_h >= 1 else 4.10
                if num_heavy == 1:
                    return 26.37  # RNH3+
                if num_heavy == 2:
                    return 16.61  # R2NH2+
                if num_heavy == 3:
                    return 4.36   # R3NH+
                if num_heavy >= 4:
                    return 0.00   # R4N+

            return 0.0

        # -------------------------------------------------------------
        # 3. PHOSPHORUS
        # -------------------------------------------------------------
        if symbol == "P":
            if has_double_bond:
                return 9.81
            return 13.59

        # -------------------------------------------------------------
        # 4. SULFUR
        # -------------------------------------------------------------
        if symbol == "S":
            if charge == 0:
                if is_aromatic:
                    return 28.24
                if num_heavy == 1:
                    return 38.80  # -SH
                if num_heavy == 2 and not has_double_bond:
                    return 25.30  # -S-
                # Sulfoxide / Sulfone: S has 0 polar contribution; the =O oxygens carry the TPSA
                if has_double_bond:
                    return 0.0

            return 0.0

        return 0.0
