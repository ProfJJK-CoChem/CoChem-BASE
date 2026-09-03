"""Dynamic Mendeleev Isotope Subsystem.

Provides dynamic Mendeleev isotopic mass queries, natural abundance retrieval,
topological isotopic substitution, mass matrix construction, reduced mass calculations,
and kinetic isotope effect (KIE) frequency ratio evaluations.
"""

from __future__ import annotations

import functools
import logging
from typing import Optional

import numpy as np
from mendeleev import element
from pydantic import BaseModel, Field

from cochem.topos.exceptions import IsotopeResolutionError
from cochem.topos.graph import TopologyGraph

logger = logging.getLogger("cochem.topos.isotopes")


class IsotopeNodeSpec(BaseModel):
    """Pydantic v2 data model storing dynamic isotopic properties."""

    atom_idx: int = Field(default=0, ge=0, description="Node index in topology graph.")
    element_symbol: str = Field(default="", description="IUPAC chemical element symbol.")
    mass_number: int = Field(ge=1, description="Isotopic nucleon number A = Z + N.")
    atomic_mass: float = Field(default=0.0, ge=0.0, description="Exact isotopic mass in Daltons via mendeleev.")
    natural_abundance: Optional[float] = Field(
        default=None, description="Natural abundance % or None for radioisotopes."
    )

    # Backwards compatibility attributes
    symbol: str = Field(default="", description="Alias for element_symbol.")
    atomic_number: int = Field(default=1, ge=1, description="Atomic number Z.")
    exact_mass: float = Field(default=0.0, ge=0.0, description="Alias for atomic_mass.")
    abundance: Optional[float] = Field(default=None, description="Alias for natural_abundance.")


@functools.lru_cache(maxsize=1024)
def get_isotope_info(symbol: str, mass_number: int) -> IsotopeNodeSpec:
    """Dynamically resolves isotope properties from Mendeleev without hardcoded tables.

    Parameters
    ----------
    symbol : str
        Elemental symbol (e.g. 'H', 'C', 'O').
    mass_number : int
        Mass number A (e.g. 2 for Deuterium, 13 for Carbon-13).

    Returns
    -------
    IsotopeNodeSpec
        Resolved isotope specification.
    """
    sym_clean = symbol.strip().capitalize()
    try:
        elem = element(sym_clean)
    except Exception as exc:
        raise IsotopeResolutionError(f"Failed to query Mendeleev for element symbol '{symbol}': {exc}") from exc

    matched_iso = None
    for iso in elem.isotopes:
        if int(iso.mass_number) == mass_number:
            matched_iso = iso
            break

    if matched_iso is None:
        raise IsotopeResolutionError(
            f"Isotope {sym_clean}-{mass_number} does not exist in Mendeleev database for {sym_clean}."
        )

    exact_m = float(matched_iso.mass)
    abundance = float(matched_iso.abundance) if matched_iso.abundance is not None else None
    return IsotopeNodeSpec(
        atom_idx=0,
        element_symbol=sym_clean,
        symbol=sym_clean,
        mass_number=mass_number,
        atomic_number=int(elem.atomic_number),
        atomic_mass=exact_m,
        exact_mass=exact_m,
        natural_abundance=abundance,
        abundance=abundance,
    )


def get_isotope_mass(symbol: str, mass_number: int) -> float:
    """Cached dynamic retrieval of accurate isotopic mass in Daltons.

    Parameters
    ----------
    symbol : str
        Elemental symbol (e.g. 'H', 'C').
    mass_number : int
        Mass number A.

    Returns
    -------
    float
        Accurate isotopic mass in Daltons.
    """
    return get_isotope_info(symbol, mass_number).exact_mass


class IsotopeManager:
    """Manages dynamic isotopic substitution, mass tensors, and kinetic isotope effects."""

    @classmethod
    def assign_isotope(
        cls,
        graph: TopologyGraph,
        atom_idx: int,
        mass_number: int,
    ) -> TopologyGraph:
        """Assigns an isotope to a node in the graph, updating mass and abundance dynamically.

        Parameters
        ----------
        graph : TopologyGraph
            Chemical topology graph.
        atom_idx : int
            Node index to substitute.
        mass_number : int
            Isotopic mass number A.

        Returns
        -------
        TopologyGraph
            Updated graph with isotope metadata registered on the target node.
        """
        if atom_idx not in graph.nodes:
            raise IsotopeResolutionError(f"Atom index {atom_idx} not found in graph.")

        symbol = str(graph.nodes[atom_idx].get("symbol", ""))
        iso_spec = get_isotope_info(symbol, mass_number)

        graph.nodes[atom_idx]["mass"] = iso_spec.exact_mass
        graph.nodes[atom_idx]["mass_number"] = iso_spec.mass_number
        graph.nodes[atom_idx]["abundance"] = iso_spec.abundance
        graph.nodes[atom_idx]["is_isotope"] = True
        return graph

    @classmethod
    def compute_mass_matrix(cls, graph: TopologyGraph) -> np.ndarray:
        """Computes diagonal atomic mass matrix M = diag(m_1, ..., m_|V|).

        Parameters
        ----------
        graph : TopologyGraph
            Chemical topology graph.

        Returns
        -------
        np.ndarray
            Diagonal mass matrix of shape (|V|, |V|).
        """
        sorted_nodes = sorted(graph.nodes())
        masses = [float(graph.nodes[n]["mass"]) for n in sorted_nodes]
        return np.diag(masses)

    @classmethod
    def compute_reduced_mass(cls, m1: float, m2: float) -> float:
        """Computes reduced mass mu = (m1 * m2) / (m1 + m2) in Daltons.

        Parameters
        ----------
        m1 : float
            Mass of atom 1.
        m2 : float
            Mass of atom 2.

        Returns
        -------
        float
            Reduced mass in Daltons.
        """
        if m1 <= 0.0 or m2 <= 0.0:
            raise IsotopeResolutionError(f"Atomic masses must be strictly positive: m1={m1}, m2={m2}")
        return (m1 * m2) / (m1 + m2)

    @classmethod
    def compute_kie_shift(cls, mu1: float, mu2: float) -> float:
        """Calculates harmonic vibrational frequency ratio nu1 / nu2 = sqrt(mu2 / mu1).

        Parameters
        ----------
        mu1 : float
            Reduced mass of lighter isotopologue (e.g. O-H).
        mu2 : float
            Reduced mass of heavier isotopologue (e.g. O-D).

        Returns
        -------
        float
            Vibrational frequency ratio nu1 / nu2.
        """
        if mu1 <= 0.0 or mu2 <= 0.0:
            raise IsotopeResolutionError(f"Reduced masses must be strictly positive: mu1={mu1}, mu2={mu2}")
        return float(np.sqrt(mu2 / mu1))
