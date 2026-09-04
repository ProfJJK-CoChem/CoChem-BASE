"""Pharmacophore Feature Perception and Extraction Subsystem.

Detects Hydrogen Bond Donors (HBD), Hydrogen Bond Acceptors (HBA), Lipophilic Centers and Clusters,
Aromatic Rings, Cationic Centers, and Anionic Centers on chemical molecular graphs.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import networkx as nx
from pydantic import BaseModel, Field

from cochem.topos.exceptions import PharmacophoreExtractionError
from cochem.topos.graph import TopologyGraph
from cochem.topos.rings import perceive_aromaticity, perceive_cycle_basis

logger = logging.getLogger("cochem.topos.pharmacophore")


class PharmacophoreFeature(BaseModel):
    """Represents a discrete chemical pharmacophore feature."""

    feature_type: str = Field(description="Type: HBD, HBA, aromatic_ring, lipophilic, cationic, anionic.")
    atom_indices: list[int] = Field(description="Topological node indices participating in this feature.")
    details: dict[str, Any] = Field(default_factory=dict, description="Metadata and chemical context.")


class PharmacophoreFeatureSet(BaseModel):
    """Container storing categorized pharmacophoric feature sets adhering to Pydantic v2 contract."""

    donors: list[int] = Field(default_factory=list, description="Atom indices of hydrogen bond donors")
    acceptors: list[int] = Field(default_factory=list, description="Atom indices of hydrogen bond acceptors")
    lipophilic_centers: list[list[int]] = Field(default_factory=list, description="Atom clusters forming lipophilic regions")
    aromatic_rings: list[list[int]] = Field(default_factory=list, description="Atom indices of aromatic rings")
    cationic_centers: list[int] = Field(default_factory=list, description="Atom indices of positive ionizable centers")
    anionic_centers: list[int] = Field(default_factory=list, description="Atom indices of negative ionizable centers")

    # Granular feature objects and compatibility aliases
    hbd: list[PharmacophoreFeature] = Field(default_factory=list)
    hba: list[PharmacophoreFeature] = Field(default_factory=list)
    lipophilic_clusters: list[list[int]] = Field(default_factory=list)

    @property
    def num_hbd(self) -> int:
        return len(self.donors)

    @property
    def num_hba(self) -> int:
        return len(self.acceptors)

    @property
    def num_aromatic_rings(self) -> int:
        return len(self.aromatic_rings)

    @property
    def num_lipophilic_clusters(self) -> int:
        return len(self.lipophilic_centers)

    @property
    def num_cationic_centers(self) -> int:
        return len(self.cationic_centers)

    @property
    def num_anionic_centers(self) -> int:
        return len(self.anionic_centers)


class PharmacophoreExtractor:
    """Perceives and extracts 3D/topological pharmacophore features adhering to IUPAC/Lipinski standards."""

    @classmethod
    def extract(cls, graph: TopologyGraph) -> PharmacophoreFeatureSet:
        """Extracts complete pharmacophore feature set from molecular topology graph.

        Parameters
        ----------
        graph : TopologyGraph
            Chemical topology graph.

        Returns
        -------
        PharmacophoreFeatureSet
            Categorized pharmacophoric features.
        """
        if graph.number_of_nodes() == 0:
            raise PharmacophoreExtractionError("Cannot extract pharmacophores from empty topology graph.")

        # Ensure ring and aromaticity perception
        perceive_cycle_basis(graph)
        perceive_aromaticity(graph)

        hbd_features: list[PharmacophoreFeature] = []
        hba_features: list[PharmacophoreFeature] = []
        anionic_features: list[PharmacophoreFeature] = []
        cationic_features: list[PharmacophoreFeature] = []
        lipophilic_atoms: set[int] = set()

        for u in graph.nodes():
            n_data = graph.nodes[u]
            symbol = str(n_data.get("symbol", "")).upper()
            charge = int(n_data.get("formal_charge", 0))
            in_ring = bool(n_data.get("in_ring", False))
            is_aromatic = bool(n_data.get("is_aromatic", False))

            # Neighbors inspection
            nbr_symbols = [str(graph.nodes[v].get("symbol", "")).upper() for v in graph.neighbors(u)]
            has_explicit_h = "H" in nbr_symbols
            heavy_neighbors = [v for v in graph.neighbors(u) if str(graph.nodes[v].get("symbol", "")).upper() != "H"]
            num_heavy = len(heavy_neighbors)

            # 1. Hydrogen Bond Donors (HBD)
            if symbol in ("O", "N", "S"):
                is_donor = False
                if has_explicit_h and charge >= 0:
                    is_donor = True
                elif not any(s == "H" for s in [str(graph.nodes[n].get("symbol", "")).upper() for n in graph.nodes()]):
                    # Graph lacks explicit hydrogens: infer from valence and formal charge
                    if symbol == "O" and charge == 0:
                        # Hydroxyl -OH: bonded to 1 heavy atom with single bond
                        if num_heavy == 1:
                            v = heavy_neighbors[0]
                            bo = float(graph.edges[u, v].get("bond_order", 1.0))
                            if abs(bo - 1.0) < 1e-2:
                                is_donor = True
                    elif symbol == "N" and charge == 0:
                        # Primary amine -NH2 or secondary amine -NH-
                        if num_heavy in (1, 2) and not is_aromatic:
                            is_donor = True
                        elif is_aromatic and num_heavy == 2:
                            # Pyrrolic NH
                            is_donor = True
                    elif symbol == "S" and charge == 0:
                        if num_heavy == 1:
                            is_donor = True

                if is_donor:
                    hbd_features.append(
                        PharmacophoreFeature(
                            feature_type="HBD",
                            atom_indices=[u],
                            details={"symbol": symbol, "charge": charge},
                        )
                    )

            # 2. Hydrogen Bond Acceptors (HBA)
            if symbol == "O" and charge <= 0:
                hba_features.append(
                    PharmacophoreFeature(
                        feature_type="HBA",
                        atom_indices=[u],
                        details={"symbol": symbol, "charge": charge},
                    )
                )
            elif symbol == "N":
                # Nitrogen with available lone pair (not quaternary ammonium, not pyrrole with H)
                if charge <= 0:
                    # In pyrrole, neutral N bonded to H or 3 atoms donates lone pair into aromatic sextet
                    if not (is_aromatic and (has_explicit_h or num_heavy >= 3)):
                        hba_features.append(
                            PharmacophoreFeature(
                                feature_type="HBA",
                                atom_indices=[u],
                                details={"symbol": symbol, "charge": charge},
                            )
                        )

            # 3. Anionic Centers
            if charge < 0:
                anionic_features.append(
                    PharmacophoreFeature(
                        feature_type="anionic",
                        atom_indices=[u],
                        details={"symbol": symbol, "charge": charge},
                    )
                )

            # 4. Cationic Centers
            if charge > 0:
                cationic_features.append(
                    PharmacophoreFeature(
                        feature_type="cationic",
                        atom_indices=[u],
                        details={"symbol": symbol, "charge": charge},
                    )
                )

            # 5. Lipophilic Centers (sp3 carbons bonded strictly to C or H, not polar heteroatoms)
            if symbol == "C" and not is_aromatic:
                hyb = str(n_data.get("hybridization", "sp3"))
                if hyb == "sp3":
                    # Check that no neighbor is a heteroatom (O, N, S, P) or carbonyl carbon
                    hetero_neighbors = False
                    for v in graph.neighbors(u):
                        nbr_sym = str(graph.nodes[v].get("symbol", "")).upper()
                        if nbr_sym in ("O", "N", "S", "P", "F", "CL", "BR", "I"):
                            hetero_neighbors = True
                            break
                        # If neighbor is a carbon bonded to heteroatom with double bond (like C=O)
                        if nbr_sym == "C":
                            for w in graph.neighbors(v):
                                if w != u and str(graph.nodes[w].get("symbol", "")).upper() in ("O", "N", "S"):
                                    bo = float(graph.edges[v, w].get("bond_order", 1.0))
                                    if bo >= 1.5:
                                        hetero_neighbors = True
                                        break
                    if not hetero_neighbors:
                        lipophilic_atoms.add(u)

        # 6. Aromatic Rings
        aromatic_ring_features: list[PharmacophoreFeature] = []
        cycles = perceive_cycle_basis(graph)
        for cycle in cycles:
            if all(bool(graph.nodes[n].get("is_aromatic", False)) for n in cycle):
                aromatic_ring_features.append(
                    PharmacophoreFeature(
                        feature_type="aromatic_ring",
                        atom_indices=sorted(cycle),
                        details={"ring_size": len(cycle)},
                    )
                )

        # 7. Lipophilic Clusters (connected components of >= 3 lipophilic atoms)
        lipo_subgraph = graph.subgraph(lipophilic_atoms)
        lipophilic_clusters: list[list[int]] = []
        lipophilic_center_features: list[PharmacophoreFeature] = []

        for comp in nx.connected_components(lipo_subgraph):
            if len(comp) >= 3:
                lipophilic_clusters.append(sorted(comp))
                lipophilic_center_features.append(
                    PharmacophoreFeature(
                        feature_type="lipophilic",
                        atom_indices=sorted(comp),
                        details={"cluster_size": len(comp)},
                    )
                )

        donors_list = sorted([f.atom_indices[0] for f in hbd_features if f.atom_indices])
        acceptors_list = sorted([f.atom_indices[0] for f in hba_features if f.atom_indices])
        aromatic_rings_list = [f.atom_indices for f in aromatic_ring_features]
        cationic_list = sorted([f.atom_indices[0] for f in cationic_features if f.atom_indices])
        anionic_list = sorted([f.atom_indices[0] for f in anionic_features if f.atom_indices])

        return PharmacophoreFeatureSet(
            donors=donors_list,
            acceptors=acceptors_list,
            lipophilic_centers=lipophilic_clusters,
            aromatic_rings=aromatic_rings_list,
            cationic_centers=cationic_list,
            anionic_centers=anionic_list,
            hbd=hbd_features,
            hba=hba_features,
            lipophilic_clusters=lipophilic_clusters,
        )
