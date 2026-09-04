"""Physical verification suite for GPU-accelerated spatial neighbor-list generator.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic spatial metrics, zero self-interaction, exact symmetry.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from Libraries.cochem_torq_neighbor_list import (
    TRITON_AVAILABLE,
    build_neighbor_list,
)

# Authentic Alanine Dipeptide (Ace-Ala-Nme, C7eq minima, N=22)
ALANINE_DIPEPTIDE_COORDS = np.array(
    [
        [-2.085, 1.374, -0.271],  # C
        [-1.571, 2.405, 0.144],  # O
        [-1.877, 0.098, 0.169],  # N
        [-2.392, -0.732, -0.252],  # H
        [-0.903, -0.231, 1.204],  # CA
        [-0.941, -1.288, 1.467],  # HA
        [-1.234, 0.612, 2.441],  # CB
        [-0.518, 0.448, 3.247],  # HB1
        [-1.214, 1.667, 2.164],  # HB2
        [-2.235, 0.387, 2.809],  # HB3
        [0.513, 0.038, 0.678],  # C
        [0.824, 1.121, 0.179],  # O
        [1.385, -0.963, 0.793],  # N
        [1.082, -1.828, 1.205],  # H
        [2.774, -0.822, 0.354],  # C
        [3.376, -0.428, 1.173],  # H1
        [2.859, -0.126, -0.481],  # H2
        [3.148, -1.799, 0.043],  # H3
        [-3.224, 1.488, -1.246],  # C
        [-3.844, 0.596, -1.218],  # H1
        [-3.842, 2.371, -1.066],  # H2
        [-2.812, 1.579, -2.253],  # H3
    ],
    dtype=np.float64,
)


def test_neighbor_list_alanine_dipeptide_invariants() -> None:
    """Test neighbor list on Alanine dipeptide: zero self-interaction, displacement accuracy, and symmetry. [M]"""
    coords = torch.tensor(ALANINE_DIPEPTIDE_COORDS, dtype=torch.float64)
    cutoff = 4.5

    result = build_neighbor_list(coords, cutoff_radius=cutoff)

    # 1. Shape and count verification
    num_edges = result.edge_index.shape[1]
    assert num_edges > 0
    assert result.edge_index.shape[0] == 2
    assert result.edge_vector.shape == (num_edges, 3)
    assert result.edge_distance.shape == (num_edges,)

    # 2. Zero self-interaction invariant: i != j for all edges
    src = result.edge_index[0]
    dst = result.edge_index[1]
    assert torch.all(src != dst), "Self-interaction detected in neighbor list"

    # 3. Displacement and distance accuracy: ||r_j - r_i||_2 == edge_distance within 1e-6
    expected_vec = coords[dst] - coords[src]
    vec_diff = torch.norm(expected_vec - result.edge_vector, dim=-1)
    assert (
        torch.max(vec_diff).item() < 1e-6
    ), "Edge displacement vector differs from r_j - r_i"

    norm_diff = torch.abs(
        torch.norm(result.edge_vector, dim=-1) - result.edge_distance
    )
    assert (
        torch.max(norm_diff).item() < 1e-6
    ), "Edge distance differs from Euclidean norm"

    # Strict cutoff bound: 0 < distance <= cutoff
    assert torch.all(result.edge_distance > 0.0)
    assert torch.all(result.edge_distance <= cutoff + 1e-8)

    # 4. Reciprocal symmetry: for every (i, j), (j, i) exists with opposite displacement
    edge_map: dict[tuple[int, int], torch.Tensor] = {}
    for k in range(num_edges):
        u = int(src[k].item())
        v = int(dst[k].item())
        edge_map[(u, v)] = result.edge_vector[k]

    for (u, v), vec_uv in edge_map.items():
        assert (v, u) in edge_map, f"Missing reciprocal edge ({v}, {u}) for ({u}, {v})"
        vec_vu = edge_map[(v, u)]
        assert torch.norm(vec_uv + vec_vu).item() < 1e-6, f"Reciprocal displacement asymmetry at ({u}, {v})"


def test_neighbor_list_dtype_and_device_preservation() -> None:
    """Assert output tensors strictly match input coordinates device and dtype (float32 and float64). [M]"""
    coords = torch.tensor(ALANINE_DIPEPTIDE_COORDS)

    # float32 check
    coords_f32 = coords.to(dtype=torch.float32)
    res_f32 = build_neighbor_list(coords_f32, cutoff_radius=4.5)
    assert res_f32.edge_index.dtype == torch.int64
    assert res_f32.edge_vector.dtype == torch.float32
    assert res_f32.edge_distance.dtype == torch.float32
    assert res_f32.edge_vector.device == coords_f32.device
    assert res_f32.edge_distance.device == coords_f32.device

    # float64 check
    coords_f64 = coords.to(dtype=torch.float64)
    res_f64 = build_neighbor_list(coords_f64, cutoff_radius=4.5)
    assert res_f64.edge_index.dtype == torch.int64
    assert res_f64.edge_vector.dtype == torch.float64
    assert res_f64.edge_distance.dtype == torch.float64
    assert res_f64.edge_vector.device == coords_f64.device
    assert res_f64.edge_distance.device == coords_f64.device


def test_neighbor_list_boundary_single_atom() -> None:
    """Verify single atom returns empty edge containers without crashing. [D]"""
    single_atom = torch.tensor([[0.0, 0.0, 0.0]], dtype=torch.float64)
    res = build_neighbor_list(single_atom, cutoff_radius=5.0)
    assert res.edge_index.shape == (2, 0)
    assert res.edge_vector.shape == (0, 3)
    assert res.edge_distance.shape == (0,)
