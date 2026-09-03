"""Authentic physical verification test suite for PBC Radial Graph Engine and Virial Stress (REQ-TORQ-INF-106).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic crystal lattices, Silicon Diamond (Fd-3m), and Rutile TiO2 (P4_2/mnm).
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from Libraries.cochem_torq_inference_errors import PBCGraphError
from Libraries.cochem_torq_inference_schemas import PBCRadialGraphConfig
from Libraries.cochem_torq_pbc_graph import (
    PBCGraph,
    PBCRadialGraphEngine,
    build_pbc_radial_graph,
    cartesian_to_fractional,
    compute_cell_volume,
    compute_hydrostatic_pressure,
    compute_interplanar_spacings,
    compute_virial_stress_tensor,
    fractional_to_cartesian,
)


# Physical Fixture 1: Silicon Diamond Lattice (Fd-3m, a = 5.43 Angstroms) [M]
SILICON_LATTICE = np.eye(3, dtype=np.float64) * 5.43
SILICON_FRAC_COORDS = np.array(
    [
        [0.0, 0.0, 0.0],
        [0.5, 0.5, 0.0],
        [0.5, 0.0, 0.5],
        [0.0, 0.5, 0.5],
        [0.25, 0.25, 0.25],
        [0.75, 0.75, 0.25],
        [0.75, 0.25, 0.75],
        [0.25, 0.75, 0.75],
    ],
    dtype=np.float64,
)
SILICON_Z = [14] * 8

# Physical Fixture 2: Rutile TiO2 Unit Cell (P4_2/mnm, a = 4.5937 Angstroms, c = 2.9587 Angstroms) [M]
RUTILE_LATTICE = np.diag([4.5937, 4.5937, 2.9587]).astype(np.float64)
RUTILE_FRAC_COORDS = np.array(
    [
        [0.0, 0.0, 0.0],        # Ti1
        [0.5, 0.5, 0.5],        # Ti2
        [0.3053, 0.3053, 0.0],  # O1
        [0.6947, 0.6947, 0.0],  # O2
        [0.8053, 0.1947, 0.5],  # O3
        [0.1947, 0.8053, 0.5],  # O4
    ],
    dtype=np.float64,
)
RUTILE_Z = [22, 22, 8, 8, 8, 8]


def test_lattice_metric_and_interplanar_spacings() -> None:
    """Verify cyclic permutation produces exact perpendicular interplanar distances. [D]"""
    lat_si = torch.tensor(SILICON_LATTICE, dtype=torch.float64)
    vol_si = compute_cell_volume(lat_si)
    expected_vol = 5.43 ** 3
    assert abs(vol_si - expected_vol) < 1e-6

    # For cubic lattice, d_perp = a = 5.43 in all 3 directions
    spacings, n_max = compute_interplanar_spacings(lat_si, rc=5.0)
    assert spacings.shape == (3,)
    for d in spacings:
        assert abs(float(d.item()) - 5.43) < 1e-6
    # n_max = ceil(5.0 / 5.43) = 1
    assert (n_max == 1).all()

    # Rutile tetragonal lattice
    lat_rutile = torch.tensor(RUTILE_LATTICE, dtype=torch.float64)
    vol_rutile = compute_cell_volume(lat_rutile)
    assert abs(vol_rutile - (4.5937 * 4.5937 * 2.9587)) < 1e-6

    spacings_r, n_max_r = compute_interplanar_spacings(lat_rutile, rc=5.0)
    assert abs(float(spacings_r[0].item()) - 4.5937) < 1e-4
    assert abs(float(spacings_r[1].item()) - 4.5937) < 1e-4
    assert abs(float(spacings_r[2].item()) - 2.9587) < 1e-4
    assert int(n_max_r[2].item()) == 2  # ceil(5.0 / 2.9587) = 2


def test_fractional_cartesian_transform_parity() -> None:
    """Verify round-trip coordinate transformations between fractional and Cartesian spaces. [D]"""
    lat = torch.tensor(SILICON_LATTICE, dtype=torch.float64)
    frac_orig = torch.tensor(SILICON_FRAC_COORDS, dtype=torch.float64)

    cart = fractional_to_cartesian(frac_orig, lat)
    frac_back = cartesian_to_fractional(cart, lat)

    assert torch.allclose(frac_orig, frac_back, atol=1e-10)


def test_self_image_exclusion_invariant() -> None:
    """Verify strict self-image exclusion invariant (no edge with d=0 when i=j and S=(0,0,0)). [D]"""
    lat_si = torch.tensor(SILICON_LATTICE, dtype=torch.float64)
    frac_si = torch.tensor(SILICON_FRAC_COORDS, dtype=torch.float64)
    cart_si = fractional_to_cartesian(frac_si, lat_si)

    graph = build_pbc_radial_graph(cart_si, lat_si, rc=5.0)

    assert graph.edge_index.shape[1] > 0
    assert (graph.edge_distances > 1e-7).all()

    # Check that any self-interaction edge has non-zero shift vector
    src, dst = graph.edge_index[0], graph.edge_index[1]
    self_loops = src == dst
    if self_loops.any():
        self_shifts = graph.edge_shifts[self_loops]
        assert not (self_shifts == 0).all(dim=-1).any()


def test_analytical_virial_stress_symmetry_silicon() -> None:
    """Compute symmetric virial stress tensor on Silicon and confirm ||Xi - Xi^T||_inf < 1e-7. [M]/[D]"""
    lat_si = torch.tensor(SILICON_LATTICE, dtype=torch.float64)
    frac_si = torch.tensor(SILICON_FRAC_COORDS, dtype=torch.float64)
    cart_si = fractional_to_cartesian(frac_si, lat_si)

    graph = build_pbc_radial_graph(cart_si, lat_si, rc=5.0)

    # Authentic pairwise Lennard-Jones interaction forces
    # V(r) = 4 * eps * ((sigma/r)^12 - (sigma/r)^6)
    # F = -grad_r V = - dV/dr * (r / r)
    sigma = 2.15
    epsilon = 0.25
    r = graph.edge_distances
    r_vec = graph.edge_vectors

    d_v_dr = 4.0 * epsilon * (-12.0 * (sigma ** 12) / (r ** 13) + 6.0 * (sigma ** 6) / (r ** 7))
    pair_forces = - d_v_dr.unsqueeze(-1) * (r_vec / r.unsqueeze(-1))

    virial = compute_virial_stress_tensor(
        edge_vectors=r_vec,
        pair_forces_or_gradients=pair_forces,
        cell_volume=graph.cell_volume,
        is_force=True,
    )

    # Assert tensorial symmetry
    asym_norm = torch.max(torch.abs(virial - virial.t())).item()
    assert asym_norm < 1e-7

    # Assert hydrostatic pressure computation
    pressure = compute_hydrostatic_pressure(virial)
    expected_p = - (1.0 / 3.0) * float(torch.trace(virial).item())
    assert abs(pressure - expected_p) < 1e-10


def test_analytical_virial_stress_rutile_tio2() -> None:
    """Compute symmetric virial stress tensor on Rutile TiO2 unit cell. [M]/[D]"""
    engine = PBCRadialGraphEngine(PBCRadialGraphConfig(cutoff_radius_rc=5.0))
    lat_r = torch.tensor(RUTILE_LATTICE, dtype=torch.float64)
    frac_r = torch.tensor(RUTILE_FRAC_COORDS, dtype=torch.float64)
    cart_r = fractional_to_cartesian(frac_r, lat_r)

    graph = engine(cart_r, lat_r)
    assert graph.edge_index.shape[1] > 0

    # Authentic harmonic pairwise interaction
    k_spring = 15.0
    r0 = 2.0
    r = graph.edge_distances
    r_vec = graph.edge_vectors
    f_mag = - k_spring * (r - r0)
    pair_forces = f_mag.unsqueeze(-1) * (r_vec / r.unsqueeze(-1))

    virial = engine.compute_virial(r_vec, pair_forces, graph.cell_volume, is_force=True)
    asym_norm = torch.max(torch.abs(virial - virial.t())).item()
    assert asym_norm < 1e-7

    p = engine.compute_pressure(virial)
    assert isinstance(p, float)


def test_pbc_graph_degenerate_lattice_error() -> None:
    """Verify degenerate or zero-volume lattice raises PBCGraphError. [M]"""
    singular_lat = torch.zeros((3, 3), dtype=torch.float64)
    with pytest.raises(PBCGraphError):
        compute_cell_volume(singular_lat)

    with pytest.raises(PBCGraphError):
        build_pbc_radial_graph(torch.zeros((2, 3)), singular_lat)
