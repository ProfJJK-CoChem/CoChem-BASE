"""Authentic physical verification test suite for C^2 Graph Pruning & Reciprocal Topology (REQ-TORQ-TRAIN-100 [D]).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic Ethanol conformational rotor (N=9) sampled along C-C torsion.
"""

from __future__ import annotations

import math
import pytest
import torch

from Libraries.cochem_torq_graph_pruning import (
    build_c2_reciprocal_graph,
    check_reciprocal_topology,
    compute_center_of_mass,
    compute_pairwise_conservative_forces,
    enforce_graph_reciprocity,
    evaluate_momentum_and_antisymmetry,
    quintic_c2_derivative,
    quintic_c2_second_derivative,
    quintic_c2_switching,
    verify_c2_continuity_boundary,
)
from Libraries.cochem_torq_training_errors import (
    DiscontinuousForceError,
    NonReciprocalGraphError,
)
from Libraries.cochem_torq_training_schemas import C2GraphPrunerConfig
from tests.torq_test_fixtures import get_ethanol_rotor_fixture


def test_quintic_c2_switching_boundary_continuity() -> None:
    """Verify quintic switching envelope satisfies f(r_c)=0, f'(r_c)=0, f''(r_c)=0 within tolerance < 10^-7. [D]"""
    cutoff = 5.0
    res = verify_c2_continuity_boundary(cutoff=cutoff)
    assert abs(res["f_rc"]) < 1e-7
    assert abs(res["df_rc"]) < 1e-7
    assert abs(res["d2f_rc"]) < 1e-7

    # Finite difference numerical cross-validation
    eps = 1e-5
    r_val = torch.tensor([cutoff - eps], dtype=torch.float64)
    r_plus = torch.tensor([cutoff], dtype=torch.float64)

    f_minus = float(quintic_c2_switching(r_val, cutoff).item())
    f_zero = float(quintic_c2_switching(r_plus, cutoff).item())

    # Numerical first derivative at cutoff approaching from inside
    num_df = (f_zero - f_minus) / eps
    assert abs(num_df) < 1e-4, f"Numerical df/dr at cutoff should approach 0, got {num_df}"


def test_momentum_conservation_and_force_antisymmetry_ethanol_rotor() -> None:
    """Verify net external force drift < 10^-6 eV/A and pairwise antisymmetry < 10^-7 eV/A across rotor. [D]"""
    # Sample Ethanol along C-C torsion at 0, 60, 120, 180 degrees
    for angle in [0.0, 60.0, 120.0, 180.0]:
        coords, species = get_ethanol_rotor_fixture(dihedral_deg=angle)
        assert coords.shape[0] == 9, "Ethanol must have N=9 atoms."

        config = C2GraphPrunerConfig(cutoff_radius_angstrom=3.5, covalent_core_radius_angstrom=1.5)
        edge_index, _ = build_c2_reciprocal_graph(coords, species, config=config)

        assert edge_index.shape[1] > 0
        pairwise_f, atomic_f = compute_pairwise_conservative_forces(
            coords, edge_index, cutoff=3.5, k_spring=10.0
        )

        metrics = evaluate_momentum_and_antisymmetry(atomic_f, edge_index, pairwise_f)

        # 1. Net external force drift ||sum F_i||_2 < 10^-6 eV/Angstrom
        assert metrics["net_force_drift"] < 1e-6, (
            f"At angle {angle} deg, net force drift ({metrics['net_force_drift']:.2e}) exceeded 1e-6 eV/A."
        )

        # 2. Pairwise force antisymmetry ||F_ij + F_ji||_inf < 10^-7 eV/Angstrom
        assert metrics["pairwise_antisymmetry_error"] < 1e-7, (
            f"At angle {angle} deg, antisymmetry error ({metrics['pairwise_antisymmetry_error']:.2e}) exceeded 1e-7 eV/A."
        )


def test_reciprocity_enforcement_and_asymmetric_drop_detection() -> None:
    """Symmetrize adjacency A (.) A^T; verify asymmetric edge configuration raises NonReciprocalGraphError. [D]"""
    coords, species = get_ethanol_rotor_fixture(dihedral_deg=0.0)
    edge_index, _ = build_c2_reciprocal_graph(coords, species)

    assert check_reciprocal_topology(edge_index) is True

    # Drop a single directed edge to create intentional asymmetry (violating Newton's 3rd Law)
    asymmetric_edges = edge_index[:, :-1]  # Remove last directed edge
    assert check_reciprocal_topology(asymmetric_edges) is False

    with pytest.raises(NonReciprocalGraphError) as exc_info:
        enforce_graph_reciprocity(asymmetric_edges, raise_on_asymmetry=True)

    assert exc_info.value.error_code == "TORQ_TRAIN_NON_RECIPROCAL_GRAPH"


def test_covalent_core_degree_invariant() -> None:
    """Confirm degree d_i >= 1 for all atoms within covalent core radius r_cov = 1.5 Angstroms. [D]"""
    coords, species = get_ethanol_rotor_fixture(dihedral_deg=30.0)
    config = C2GraphPrunerConfig(cutoff_radius_angstrom=4.0, covalent_core_radius_angstrom=1.5)

    edge_index, _ = build_c2_reciprocal_graph(coords, species, config=config)

    src = edge_index[0].tolist()
    # In ethanol, every atom is within 1.5 A of at least one other atom (C-C ~ 1.52 A, C-H ~ 1.09 A, C-O ~ 1.43 A, O-H ~ 0.96 A)
    for atom_idx in range(9):
        degree = src.count(atom_idx)
        assert degree >= 1, f"Atom {atom_idx} violated covalent core degree invariant (degree={degree})."


def test_banned_stochastic_dropout_on_coordinate_graphs() -> None:
    """Assert setting stochastic edge dropout > 0 on coordinate graphs raises DiscontinuousForceError. [D]"""
    coords, species = get_ethanol_rotor_fixture()
    config = C2GraphPrunerConfig(stochastic_edge_dropout=0.2)

    with pytest.raises(DiscontinuousForceError) as exc_info:
        build_c2_reciprocal_graph(coords, species, config=config)

    assert "banned on spatial coordinate graphs" in str(exc_info.value)


def test_dynamic_mendeleev_center_of_mass_ethanol() -> None:
    """Verify center of mass and total molecular mass computed dynamically using mendeleev. [M]"""
    coords, species = get_ethanol_rotor_fixture()
    com, total_mass = compute_center_of_mass(coords, species.tolist())

    # C2H6O mass ~ 2*12.011 + 6*1.008 + 15.999 ~ 46.069 u
    assert 45.9 < total_mass < 46.2, f"Total mass {total_mass} u is physically inconsistent."
    assert com.shape == (3,)
    assert torch.isfinite(com).all()
