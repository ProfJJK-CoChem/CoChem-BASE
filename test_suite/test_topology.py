"""Comprehensive test suite for cochem_topos.topology module.

Validates:
- AtomModel Pydantic data validation and sanitization.
- Covalent radius retrieval and fallback tables.
- Pairwise Euclidean distance matrix computation.
- Binary covalent adjacency matrix generation.
- Topology validation and sanitization against unphysical interatomic edges.
- Dynamic adjacency re-derivation upon unphysical edge detection.
- Connected component counting, fragment partitioning, and graph connectivity verification.
"""

from __future__ import annotations

import logging
import numpy as np
import pytest
from pydantic import ValidationError

from cochem_topos.topology import (
    FALLBACK_RADII,
    AtomModel,
    compute_covalent_adjacency,
    compute_distance_matrix,
    get_connected_components,
    get_covalent_radius,
    get_fragment_indices,
    is_connected,
    validate_and_sanitize_topology,
)


# =============================================================================
# 1. AtomModel & Covalent Radii Tests
# =============================================================================


def test_atom_model_valid_instantiation():
    """Verify AtomModel accepts tuples, lists, and numpy arrays for 3D coordinates."""
    atom1 = AtomModel(symbol="c", coords=(0.0, 1.0, 2.0))
    assert atom1.symbol == "C"
    assert atom1.coords == (0.0, 1.0, 2.0)

    atom2 = AtomModel(symbol="O", coords=[1.5, -0.5, 0.0])
    assert atom2.symbol == "O"
    assert atom2.coords == (1.5, -0.5, 0.0)

    atom3 = AtomModel(symbol="H", coords=np.array([0.0, 0.0, 1.0]))
    assert atom3.symbol == "H"
    assert atom3.coords == (0.0, 0.0, 1.0)


def test_atom_model_invalid_inputs():
    """Verify AtomModel raises validation errors for missing or invalid inputs."""
    with pytest.raises(ValidationError):
        AtomModel(symbol="", coords=(0.0, 0.0, 0.0))

    with pytest.raises(ValidationError):
        AtomModel(symbol="C", coords=(0.0, 0.0))  # Only 2 coords

    with pytest.raises(ValidationError):
        AtomModel(symbol="C", coords=(0.0, 0.0, 0.0, 1.0))  # 4 coords


def test_get_covalent_radius_standard_elements():
    """Verify covalent radii for standard organic and transition metals."""
    r_h = get_covalent_radius("H")
    assert 0.25 < r_h < 0.40

    r_c = get_covalent_radius("c")
    assert 0.70 < r_c < 0.85

    r_o = get_covalent_radius("O")
    assert 0.60 < r_o < 0.75

    r_fe = get_covalent_radius("Fe")
    assert 1.20 < r_fe < 1.45


def test_get_covalent_radius_unknown_element():
    """Verify ValueError is raised when querying an unknown elemental symbol."""
    with pytest.raises(ValueError, match=r"\[MISSING DATA\]"):
        get_covalent_radius("UnknownElementXyz")

    with pytest.raises(ValueError, match=r"\[MISSING DATA\]"):
        get_covalent_radius("")


# =============================================================================
# 2. Distance Matrix & Adjacency Computation Tests
# =============================================================================


def test_compute_distance_matrix():
    """Verify pairwise distance matrix calculation across known coordinates."""
    coords = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 2.0, 0.0],
    ])
    dist_mat = compute_distance_matrix(coords)
    assert dist_mat.shape == (3, 3)
    assert dist_mat[0, 0] == 0.0
    assert dist_mat[1, 1] == 0.0
    assert dist_mat[2, 2] == 0.0
    assert np.isclose(dist_mat[0, 1], 1.0)
    assert np.isclose(dist_mat[1, 0], 1.0)
    assert np.isclose(dist_mat[0, 2], 2.0)
    assert np.isclose(dist_mat[1, 2], np.sqrt(5.0))


def test_compute_distance_matrix_invalid_shape():
    """Verify ValueError when passing coordinates with invalid dimensions."""
    with pytest.raises(ValueError, match=r"\[MISSING DATA\]"):
        compute_distance_matrix(np.array([[0.0, 0.0], [1.0, 1.0]]))


def test_compute_covalent_adjacency_water():
    """Verify covalent adjacency matrix derivation for physical water molecule."""
    # Water: O at origin, H1 at (0, 0.757, -0.469), H2 at (0, -0.757, -0.469)
    # O-H distances ~ 0.957 Angstrom
    water_atoms = [
        {"symbol": "O", "coords": (0.0, 0.0, 0.1173)},
        {"symbol": "H", "coords": (0.0, 0.7572, -0.4692)},
        {"symbol": "H", "coords": (0.0, -0.7572, -0.4692)},
    ]
    adj = compute_covalent_adjacency(water_atoms, alpha=1.15)
    assert adj.shape == (3, 3)
    # Diagonal must be 0
    assert np.all(np.diag(adj) == 0)
    # O-H1 bond
    assert adj[0, 1] == 1 and adj[1, 0] == 1
    # O-H2 bond
    assert adj[0, 2] == 1 and adj[2, 0] == 1
    # H1-H2 is not a covalent bond
    assert adj[1, 2] == 0 and adj[2, 1] == 0


# =============================================================================
# 3. Topology Validation & Sanitization Tests
# =============================================================================


def test_validate_and_sanitize_topology_clean():
    """Verify that a physical adjacency matrix passes validation without modification."""
    water_atoms = [
        {"symbol": "O", "coords": (0.0, 0.0, 0.1173)},
        {"symbol": "H", "coords": (0.0, 0.7572, -0.4692)},
        {"symbol": "H", "coords": (0.0, -0.7572, -0.4692)},
    ]
    valid_adj = np.array([
        [0, 1, 1],
        [1, 0, 0],
        [1, 0, 0],
    ], dtype=np.int32)

    sanitized = validate_and_sanitize_topology(water_atoms, valid_adj, tol=0.8)
    assert np.array_equal(sanitized, valid_adj)


def test_validate_and_sanitize_topology_unphysical_edge(caplog):
    """Verify detection of unphysical edges, logging, and dynamic re-derivation."""
    # Water molecule with an unphysical H1-H2 bond (distance ~1.51 A > (0.31+0.31)+0.8 = 1.42 A)
    water_atoms = [
        {"symbol": "O", "coords": (0.0, 0.0, 0.1173)},
        {"symbol": "H", "coords": (0.0, 0.7572, -0.4692)},
        {"symbol": "H", "coords": (0.0, -0.7572, -0.4692)},
    ]
    # Spurious unphysical triangle topology
    unphysical_adj = np.array([
        [0, 1, 1],
        [1, 0, 1],  # Spurious H1-H2 edge
        [1, 1, 0],  # Spurious H2-H1 edge
    ], dtype=np.int32)

    with caplog.at_level(logging.WARNING):
        sanitized = validate_and_sanitize_topology(water_atoms, unphysical_adj, tol=0.8)

    assert "[E: TOPOLOGY_SANITIZED_UNPHYSICAL_EDGE]" in caplog.text
    # Sanitized adjacency should only have O-H bonds (0-1 and 0-2)
    assert sanitized[0, 1] == 1 and sanitized[1, 0] == 1
    assert sanitized[0, 2] == 1 and sanitized[2, 0] == 1
    assert sanitized[1, 2] == 0 and sanitized[2, 1] == 0


def test_validate_and_sanitize_topology_dimension_mismatch():
    """Verify ValueError when atoms count and adjacency matrix shape mismatch."""
    atoms = [{"symbol": "H", "coords": (0.0, 0.0, 0.0)}]
    mismatched_adj = np.zeros((2, 2), dtype=np.int32)

    with pytest.raises(ValueError, match=r"\[MISSING DATA\]"):
        validate_and_sanitize_topology(atoms, mismatched_adj)


# =============================================================================
# 4. Graph Connectivity & Fragment Partitioning Tests
# =============================================================================


def test_get_connected_components_and_fragments():
    """Verify connected components and fragment partitioning for single molecule vs dimer."""
    # Water molecule (1 connected component)
    water_adj = np.array([
        [0, 1, 1],
        [1, 0, 0],
        [1, 0, 0],
    ], dtype=np.int32)

    assert get_connected_components(water_adj) == 1
    assert is_connected(water_adj) is True
    fragments = get_fragment_indices(water_adj)
    assert len(fragments) == 1
    assert sorted(fragments[0]) == [0, 1, 2]

    # Water dimer (6 atoms: 0,1,2 = water 1; 3,4,5 = water 2)
    dimer_adj = np.zeros((6, 6), dtype=np.int32)
    # Water 1
    dimer_adj[0, 1] = dimer_adj[1, 0] = 1
    dimer_adj[0, 2] = dimer_adj[2, 0] = 1
    # Water 2
    dimer_adj[3, 4] = dimer_adj[4, 3] = 1
    dimer_adj[3, 5] = dimer_adj[5, 3] = 1

    assert get_connected_components(dimer_adj) == 2
    assert is_connected(dimer_adj) is False
    dimer_fragments = get_fragment_indices(dimer_adj)
    assert len(dimer_fragments) == 2
    assert sorted(dimer_fragments[0]) == [0, 1, 2]
    assert sorted(dimer_fragments[1]) == [3, 4, 5]
