"""Tests for CoChem-GEOM PyTorch Geometric (PyG) Execution Tensor Schema.
=============================================================================
Comprehensive unit and integration test suite validating `ConformerData` and schema utilities.

Authoritative Standards:
- Method Matrix v4: Data Ingestion & Spectroscopic Graph Contracts
- SWEBOK v3 / ISO 25010 Software Quality Standards
- Mendeleev Library Mandate: Dynamic atomic mass & isotopic resolution (NEVER hardcoded)
- Cryptographic Provenance: SHA-256 checksum generation for structures and files
- SE(3) Equivariance & Invariance: Separation of spatial pos vs non-spatial features
- State Immutability: Pure functional transformations
- Strict Zero-Mock Mandate: Authentic physical constants and real quantum chemical geometries
"""

from __future__ import annotations

import math
import os
import tempfile

import numpy as np
import pytest
import torch
from torch_geometric.data import Batch, Data
from torch_geometric.loader import DataLoader

from cochem_geom.data.featurizer import (
    MolecularData,
    get_atomic_mass,
)
from cochem_geom.data.geom_parser import (
    ConformerRecord,
)
from cochem_geom.data.pyg_schema import (
    ConformerData,
    SchemaValidationError,
    batch_conformer_data,
    center_at_com_conformer_data,
    is_valid_conformer_data,
    rotate_conformer_data,
    translate_conformer_data,
    validate_conformer_data,
)

# ==============================================================================
# Authentic Molecular Test Geometries (Zero-Mock Policy)
# ==============================================================================

# Water (H2O, C2v) - Experimental Ground State Geometry (Angstroms)
WATER_SYMBOLS = ["O", "H", "H"]
WATER_Z = [8, 1, 1]
WATER_POS = [
    [0.000000, 0.000000, 0.117300],
    [0.000000, 0.757200, -0.469200],
    [0.000000, -0.757200, -0.469200],
]
WATER_ENERGY_EV = -2079.35  # ~ -76.4 Hartree
WATER_DIPOLE = [0.0, 0.0, 1.8546]  # Debye (along z-axis)

# Methane (CH4, Td) - Ground State Geometry (Angstroms)
METHANE_SYMBOLS = ["C", "H", "H", "H", "H"]
METHANE_Z = [6, 1, 1, 1, 1]
METHANE_POS = [
    [0.000000, 0.000000, 0.000000],
    [0.629118, 0.629118, 0.629118],
    [-0.629118, -0.629118, 0.629118],
    [-0.629118, 0.629118, -0.629118],
    [0.629118, -0.629118, -0.629118],
]
METHANE_ENERGY_EV = -1098.24

# Formaldehyde (H2CO, C2v) - Ground State Geometry (Angstroms)
FORMALDEHYDE_SYMBOLS = ["C", "O", "H", "H"]
FORMALDEHYDE_Z = [6, 8, 1, 1]
FORMALDEHYDE_POS = [
    [0.000000, 0.000000, -0.537500],
    [0.000000, 0.000000, 0.665500],
    [0.000000, 0.935000, -1.112500],
    [0.000000, -0.935000, -1.112500],
]
FORMALDEHYDE_ENERGY_EV = -3105.12


def create_rotation_matrix_3d(alpha: float, beta: float, gamma: float) -> torch.Tensor:
    """Generate an authentic 3D SO(3) Euler angle rotation matrix R = Rz(gamma) * Ry(beta) * Rx(alpha)."""
    ca, sa = math.cos(alpha), math.sin(alpha)
    cb, sb = math.cos(beta), math.sin(beta)
    cg, sg = math.cos(gamma), math.sin(gamma)

    rx = np.array([[1, 0, 0], [0, ca, -sa], [0, sa, ca]], dtype=np.float32)
    ry = np.array([[cb, 0, sb], [0, 1, 0], [-sb, 0, cb]], dtype=np.float32)
    rz = np.array([[cg, -sg, 0], [sg, cg, 0], [0, 0, 1]], dtype=np.float32)

    r_mat = rz @ ry @ rx
    return torch.tensor(r_mat, dtype=torch.float32)


# ==============================================================================
# 1. Fail-Fast Strict Validation Tests
# ==============================================================================


class TestValidationFailFast:
    """Tests fail-fast rejection of malformed shapes, types, dtypes, and bounds."""

    def test_valid_conformer_data_passes(self) -> None:
        """Valid ConformerData instantiation must pass validation cleanly."""
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
            y=torch.tensor([WATER_ENERGY_EV], dtype=torch.float32),
            dipole=torch.tensor(WATER_DIPOLE, dtype=torch.float32),
            weight=torch.tensor([1.0], dtype=torch.float32),
        )
        assert is_valid_conformer_data(data) is True
        validate_conformer_data(data)
        assert data.num_nodes == 3

    def test_rejection_of_float16_pos(self) -> None:
        """float16 coordinates must be strictly rejected due to insufficient precision."""
        with pytest.raises(TypeError, match="float16"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float16),
            )

    def test_rejection_of_bfloat16_pos(self) -> None:
        """bfloat16 coordinates must be strictly rejected."""
        with pytest.raises(TypeError, match="bfloat16"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.bfloat16),
            )

    def test_rejection_of_non_float32_pos(self) -> None:
        """pos with dtype double/float64 or int must raise TypeError."""
        with pytest.raises(TypeError, match="torch.float32"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float64),
            )

    def test_rejection_of_z_pos_count_mismatch(self) -> None:
        """Mismatch between atom count in z and pos must raise SchemaValidationError."""
        with pytest.raises((ValueError, SchemaValidationError), match="Atom count mismatch"):
            ConformerData(
                z=torch.tensor([8, 1], dtype=torch.long),  # 2 atoms
                pos=torch.tensor(WATER_POS, dtype=torch.float32),  # 3 atoms
            )

    def test_rejection_of_invalid_pos_shape(self) -> None:
        """pos tensor with shape other than (N, 3) must raise SchemaValidationError."""
        with pytest.raises((ValueError, SchemaValidationError), match="shape"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor([[0.0, 1.0], [2.0, 3.0], [4.0, 5.0]], dtype=torch.float32),
            )

    def test_rejection_of_invalid_edge_index_shape(self) -> None:
        """edge_index not of shape (2, E) must raise SchemaValidationError."""
        with pytest.raises((ValueError, SchemaValidationError), match="edge_index"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                edge_index=torch.tensor([[0, 1, 2]], dtype=torch.long),  # (1, 3) instead of (2, E)
            )

    def test_rejection_of_edge_index_out_of_bounds(self) -> None:
        """edge_index referencing atom index >= N must raise SchemaValidationError."""
        with pytest.raises((ValueError, SchemaValidationError), match="references node index"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),  # N=3 atoms (indices 0, 1, 2)
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                edge_index=torch.tensor([[0, 5], [1, 0]], dtype=torch.long),  # index 5 >= 3
            )

    def test_rejection_of_edge_index_negative_index(self) -> None:
        """edge_index containing negative indices must raise SchemaValidationError."""
        with pytest.raises((ValueError, SchemaValidationError), match="negative node index"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                edge_index=torch.tensor([[-1, 0], [0, 1]], dtype=torch.long),
            )

    def test_rejection_of_non_float32_y(self) -> None:
        """Non-float32 target property y must raise TypeError."""
        with pytest.raises(TypeError, match="y.*torch.float32"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                y=torch.tensor([WATER_ENERGY_EV], dtype=torch.float64),
            )

    def test_rejection_of_non_float32_weight(self) -> None:
        """Non-float32 weight must raise TypeError."""
        with pytest.raises(TypeError, match="weight.*torch.float32"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                weight=torch.tensor([1.0], dtype=torch.float64),
            )

    def test_rejection_of_non_float32_forces(self) -> None:
        """forces with incorrect dtype or shape must raise TypeError or ValueError."""
        with pytest.raises(TypeError, match="forces"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                forces=torch.zeros((3, 3), dtype=torch.float64),
            )

    def test_rejection_of_invalid_dipole_shape(self) -> None:
        """dipole vector with shape != (3,) or (1, 3) must raise SchemaValidationError."""
        with pytest.raises((ValueError, SchemaValidationError), match="dipole"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                dipole=torch.tensor([1.0, 2.0, 3.0, 4.0], dtype=torch.float32),
            )

    def test_rejection_of_empty_z(self) -> None:
        """Empty atomic number tensor must be rejected."""
        with pytest.raises((ValueError, SchemaValidationError), match="cannot be empty"):
            ConformerData(
                z=torch.empty((0,), dtype=torch.long),
                pos=torch.empty((0, 3), dtype=torch.float32),
            )

    def test_rejection_of_non_positive_z(self) -> None:
        """Non-positive atomic numbers (z <= 0) must raise SchemaValidationError."""
        with pytest.raises((ValueError, SchemaValidationError), match="must be positive"):
            ConformerData(
                z=torch.tensor([8, 0, -1], dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
            )

    def test_rejection_of_invalid_x_shape(self) -> None:
        """Node feature tensor x with shape (M, F) where M != N must raise SchemaValidationError."""
        with pytest.raises((ValueError, SchemaValidationError), match="Attribute 'x' must have shape"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                x=torch.zeros((4, 16), dtype=torch.float32),  # 4 rows != 3 atoms
            )

    def test_rejection_of_invalid_edge_attr_shape(self) -> None:
        """Edge feature tensor edge_attr with shape (E2, D) where E2 != E must raise SchemaValidationError."""
        edge_index = torch.tensor([[0, 1], [1, 0]], dtype=torch.long)  # E=2
        with pytest.raises((ValueError, SchemaValidationError), match="Attribute 'edge_attr' must have shape"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                edge_index=edge_index,
                edge_attr=torch.zeros((5, 8), dtype=torch.float32),  # 5 rows != 2 edges
            )

    def test_rejection_of_invalid_forces_shape(self) -> None:
        """forces tensor with shape not matching pos must raise SchemaValidationError."""
        with pytest.raises((ValueError, SchemaValidationError), match="forces"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                forces=torch.zeros((3, 2), dtype=torch.float32),  # (3, 2) != (3, 3)
            )

    def test_rejection_of_invalid_rotational_constants_shape(self) -> None:
        """rotational_constants with shape != (3,) or (1, 3) must raise SchemaValidationError."""
        with pytest.raises((ValueError, SchemaValidationError), match="rotational_constants"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                rotational_constants=torch.tensor([1.0, 2.0, 3.0, 4.0], dtype=torch.float32),
            )

    def test_rejection_of_non_data_instance(self) -> None:
        """validate_conformer_data must raise TypeError on non-Data input."""
        with pytest.raises(TypeError, match="Expected ConformerData or torch_geometric.data.Data"):
            validate_conformer_data("invalid_data_string")  # type: ignore[arg-type]


# ==============================================================================
# 2. PyG Subclassing, Mini-Batching, and __inc__ Correctness Tests
# ==============================================================================


class TestPyGBatchingAndInc:
    """Tests PyG Data inheritance, Batch collation, and __inc__ offset mechanism."""

    def test_subclassing_pyg_data(self) -> None:
        """ConformerData must be an instance of torch_geometric.data.Data."""
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
        )
        assert isinstance(data, Data)
        assert isinstance(data, ConformerData)

    def test_batch_collation_and_offsets(self) -> None:
        """Collation via Batch.from_data_list must correctly offset edge_index via __inc__."""
        # Molecule 1: Water (3 atoms, 4 edges: 0-1, 1-0, 0-2, 2-0)
        edge_index1 = torch.tensor([[0, 1, 0, 2], [1, 0, 2, 0]], dtype=torch.long)
        d1 = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
            edge_index=edge_index1,
            y=torch.tensor([WATER_ENERGY_EV], dtype=torch.float32),
            conformer_id=1,
        )

        # Molecule 2: Formaldehyde (4 atoms, 6 edges)
        edge_index2 = torch.tensor([[0, 1, 0, 2, 0, 3], [1, 0, 2, 0, 3, 0]], dtype=torch.long)
        d2 = ConformerData(
            z=torch.tensor(FORMALDEHYDE_Z, dtype=torch.long),
            pos=torch.tensor(FORMALDEHYDE_POS, dtype=torch.float32),
            edge_index=edge_index2,
            y=torch.tensor([FORMALDEHYDE_ENERGY_EV], dtype=torch.float32),
            conformer_id=2,
        )

        # Molecule 3: Methane (5 atoms, 8 edges)
        edge_index3 = torch.tensor(
            [[0, 1, 0, 2, 0, 3, 0, 4], [1, 0, 2, 0, 3, 0, 4, 0]], dtype=torch.long
        )
        d3 = ConformerData(
            z=torch.tensor(METHANE_Z, dtype=torch.long),
            pos=torch.tensor(METHANE_POS, dtype=torch.float32),
            edge_index=edge_index3,
            y=torch.tensor([METHANE_ENERGY_EV], dtype=torch.float32),
            conformer_id=3,
        )

        batch = Batch.from_data_list([d1, d2, d3])

        # Total node count = 3 + 4 + 5 = 12
        assert batch.num_nodes == 12
        assert batch.z.shape == (12,)
        assert batch.pos.shape == (12, 3)

        # Total edge count = 4 + 6 + 8 = 18
        assert batch.edge_index.shape == (2, 18)

        # Verify batch index vector
        expected_batch = torch.tensor([0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2], dtype=torch.long)
        assert torch.equal(batch.batch, expected_batch)

        # Verify ptr vector: [0, 3, 7, 12]
        expected_ptr = torch.tensor([0, 3, 7, 12], dtype=torch.long)
        assert torch.equal(batch.ptr, expected_ptr)

        # Verify edge_index offset correctness:
        # Molecule 2 edges must be shifted by 3 (indices in range [3, 6])
        mol2_edges = batch.edge_index[:, 4:10]
        assert mol2_edges.min().item() >= 3
        assert mol2_edges.max().item() <= 6

        # Molecule 3 edges must be shifted by 7 (indices in range [7, 11])
        mol3_edges = batch.edge_index[:, 10:18]
        assert mol3_edges.min().item() >= 7
        assert mol3_edges.max().item() <= 11

    def test_pyg_dataloader_iteration(self) -> None:
        """PyG DataLoader must iterate smoothly over ConformerData dataset."""
        dataset = [
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                y=torch.tensor([WATER_ENERGY_EV], dtype=torch.float32),
            ),
            ConformerData(
                z=torch.tensor(METHANE_Z, dtype=torch.long),
                pos=torch.tensor(METHANE_POS, dtype=torch.float32),
                y=torch.tensor([METHANE_ENERGY_EV], dtype=torch.float32),
            ),
            ConformerData(
                z=torch.tensor(FORMALDEHYDE_Z, dtype=torch.long),
                pos=torch.tensor(FORMALDEHYDE_POS, dtype=torch.float32),
                y=torch.tensor([FORMALDEHYDE_ENERGY_EV], dtype=torch.float32),
            ),
        ]

        loader = DataLoader(dataset, batch_size=2, shuffle=False)
        batches = list(loader)

        assert len(batches) == 2
        batch0 = batches[0]
        assert batch0.num_nodes == 3 + 5  # Water + Methane = 8
        assert batch0.num_graphs == 2

        batch1 = batches[1]
        assert batch1.num_nodes == 4  # Formaldehyde = 4
        assert batch1.num_graphs == 1


# ==============================================================================
# 3. SE(3) Equivariance and Invariance Tests
# ==============================================================================


class TestSE3EquivarianceAndInvariance:
    """Tests pure spatial translation and 3D SO(3) rotation equivariance & invariance."""

    def test_spatial_translation_equivariance(self) -> None:
        """Spatial translation T transforms pos equivariantly while forces, dipole, and scalars remain invariant."""
        forces_water = torch.tensor(
            [[0.0, 0.0, 0.05], [0.0, -0.025, -0.025], [0.0, 0.025, -0.025]],
            dtype=torch.float32,
        )
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
            y=torch.tensor([WATER_ENERGY_EV], dtype=torch.float32),
            forces=forces_water,
            dipole=torch.tensor(WATER_DIPOLE, dtype=torch.float32),
            weight=torch.tensor([0.75], dtype=torch.float32),
        )

        t_vec = torch.tensor([12.5, -7.3, 4.2], dtype=torch.float32)
        translated = data.translate(t_vec)

        # 1. pos is translated equivariantly: pos' = pos + T
        expected_pos = data.pos + t_vec
        assert torch.allclose(translated.pos, expected_pos, atol=1e-6)

        # 2. forces are translational invariants: forces' == forces
        assert torch.allclose(translated.forces, data.forces, atol=1e-6)

        # 3. dipole is translational invariant
        assert torch.allclose(translated.dipole, data.dipole, atol=1e-6)

        # 4. Energy y and weight are scalar invariants
        assert torch.allclose(translated.y, data.y, atol=1e-6)
        assert torch.allclose(translated.weight, data.weight, atol=1e-6)

        # 5. Rotational constants computed in COM frame are translational invariants
        rc_orig = data.compute_principal_rotational_constants()
        rc_trans = translated.compute_principal_rotational_constants()
        assert torch.allclose(rc_orig, rc_trans, atol=1e-3)

    def test_3d_rotation_equivariance(self) -> None:
        """3D rotation R transforms pos, forces, and dipole equivariantly while scalars remain invariant."""
        forces_water = torch.tensor(
            [[0.0, 0.0, 0.05], [0.0, -0.025, -0.025], [0.0, 0.025, -0.025]],
            dtype=torch.float32,
        )
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
            y=torch.tensor([WATER_ENERGY_EV], dtype=torch.float32),
            forces=forces_water,
            dipole=torch.tensor(WATER_DIPOLE, dtype=torch.float32),
            weight=torch.tensor([0.85], dtype=torch.float32),
        )

        # Generate orthogonal rotation matrix R
        r_mat = create_rotation_matrix_3d(alpha=0.45, beta=1.12, gamma=-0.78)
        assert torch.allclose(r_mat @ r_mat.t(), torch.eye(3), atol=1e-6)

        rotated = data.rotate(r_mat)

        # 1. pos rotates equivariantly: pos' = pos @ R^T (equivalent to r_i' = R r_i)
        expected_pos = torch.matmul(data.pos, r_mat.t())
        assert torch.allclose(rotated.pos, expected_pos, atol=1e-5)

        # 2. forces rotate equivariantly: forces' = forces @ R^T
        expected_forces = torch.matmul(data.forces, r_mat.t())
        assert torch.allclose(rotated.forces, expected_forces, atol=1e-5)

        # 3. dipole rotates equivariantly: dipole' = R @ dipole
        expected_dipole = torch.matmul(r_mat, data.dipole)
        assert torch.allclose(rotated.dipole, expected_dipole, atol=1e-5)

        # 4. Energy y, weight, z are scalar SO(3) invariants
        assert torch.allclose(rotated.y, data.y, atol=1e-6)
        assert torch.allclose(rotated.weight, data.weight, atol=1e-6)
        assert torch.equal(rotated.z, data.z)

        # 5. Spectroscopic rotational constants (A, B, C) are eigenvalues and SO(3) invariants
        rc_orig = data.compute_principal_rotational_constants()
        rc_rot = rotated.compute_principal_rotational_constants()
        assert torch.allclose(rc_orig, rc_rot, rtol=1e-4, atol=1e-2)


# ==============================================================================
# 4. Dynamic Mendeleev Mass Retrieval and Spectroscopic Physics Tests
# ==============================================================================


class TestDynamicMendeleevSpectroscopy:
    """Tests dynamic mass resolution from mendeleev for COM, inertia, and rotational constants."""

    def test_dynamic_mendeleev_mass_resolution(self) -> None:
        """Atomic masses must be queried dynamically from mendeleev and match physical values."""
        m_h = get_atomic_mass(1)
        m_o = get_atomic_mass(8)
        m_c = get_atomic_mass(6)

        assert 1.007 < m_h < 1.009
        assert 15.998 < m_o < 16.001
        assert 12.010 < m_c < 12.012

    def test_water_center_of_mass_calculation(self) -> None:
        """COM calculation for H2O must match analytical weighted average."""
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
        )
        com = data.center_of_mass()

        m_o = get_atomic_mass(8)
        m_h = get_atomic_mass(1)
        total_m = m_o + 2 * m_h
        expected_z = (m_o * 0.1173 + 2 * m_h * (-0.4692)) / total_m

        assert math.isclose(float(com[0].item()), 0.0, abs_tol=1e-5)
        assert math.isclose(float(com[1].item()), 0.0, abs_tol=1e-5)
        assert math.isclose(float(com[2].item()), expected_z, abs_tol=1e-5)

    def test_center_at_com(self) -> None:
        """center_at_com() must translate coordinates so that the new COM is at origin (0, 0, 0)."""
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
        )
        centered = data.center_at_com()
        new_com = centered.center_of_mass()

        assert torch.allclose(new_com, torch.zeros(3), atol=1e-5)

    def test_moment_of_inertia_and_rotational_constants(self) -> None:
        """Principal rotational constants A, B, C for H2O must satisfy A > B > C in MHz."""
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
        )
        rc = data.compute_principal_rotational_constants()
        a, b, c = float(rc[0].item()), float(rc[1].item()), float(rc[2].item())

        # For H2O: A ~ 835 GHz (835,000 MHz), B ~ 435 GHz, C ~ 278 GHz
        assert a >= b >= c
        assert a > 500000.0  # > 500 GHz
        assert b > 250000.0  # > 250 GHz
        assert c > 150000.0  # > 150 GHz

    def test_isotopic_mass_variation(self) -> None:
        """Heavier isotope (Deuterium D2O vs H2O) must yield smaller rotational constants."""
        data_h2o = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
        )
        # Explicit Deuterium mass ~ 2.0141 u
        masses_d2o = [get_atomic_mass(8), 2.0141017781, 2.0141017781]
        rc_h2o = data_h2o.compute_principal_rotational_constants()
        rc_d2o = data_h2o.compute_principal_rotational_constants(masses=masses_d2o)

        # Rotational constants of D2O must be strictly smaller than H2O due to larger moment of inertia
        assert rc_d2o[0] < rc_h2o[0]
        assert rc_d2o[1] < rc_h2o[1]
        assert rc_d2o[2] < rc_h2o[2]


# ==============================================================================
# 5. Inter-Schema Conversion Tests
# ==============================================================================


class TestInterSchemaConversions:
    """Tests bidirectional conversions between ConformerData, MolecularData, and ConformerRecord."""

    def test_molecular_data_roundtrip(self) -> None:
        """ConformerData <-> MolecularData round-trip conversion."""
        mol_data = MolecularData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
            y=torch.tensor([WATER_ENERGY_EV], dtype=torch.float32),
            forces=torch.randn((3, 3), dtype=torch.float32),
            dipole=torch.tensor(WATER_DIPOLE, dtype=torch.float32),
            rotational_constants=torch.tensor([835000.0, 435000.0, 278000.0], dtype=torch.float32),
            symbols=WATER_SYMBOLS,
            metadata={"source": "test_roundtrip"},
        )

        conformer_data = ConformerData.from_molecular_data(mol_data)
        assert isinstance(conformer_data, ConformerData)
        assert torch.equal(conformer_data.z, mol_data.z)
        assert torch.allclose(conformer_data.pos, mol_data.pos)
        assert torch.allclose(conformer_data.forces, mol_data.forces)

        mol_data_back = conformer_data.to_molecular_data()
        assert isinstance(mol_data_back, MolecularData)
        assert torch.equal(mol_data_back.z, mol_data.z)
        assert torch.allclose(mol_data_back.pos, mol_data.pos)
        assert torch.allclose(mol_data_back.forces, mol_data.forces)
        assert mol_data_back.metadata["source"] == "test_roundtrip"

    def test_conformer_record_roundtrip(self) -> None:
        """ConformerData <-> ConformerRecord round-trip conversion."""
        record = ConformerRecord(
            conformer_id=42,
            coords=np.array(WATER_POS, dtype=np.float64),
            energy=WATER_ENERGY_EV,
            relative_energy=0.0,
            boltzmann_weight=0.995,
            forces=np.zeros((3, 3), dtype=np.float64),
            dipole=np.array(WATER_DIPOLE, dtype=np.float64),
            rotational_constants=np.array([835000.0, 435000.0, 278000.0], dtype=np.float64),
            qm_method="DFT/wB97M-V/def2-QZVPP",
            source_hash="a" * 64,
            metadata={"tag": "canonical_minimum"},
        )

        conf_data = ConformerData.from_conformer_record(
            record=record,
            atomic_numbers=WATER_Z,
            smiles="O",
        )
        assert isinstance(conf_data, ConformerData)
        assert conf_data.conformer_id == 42
        assert conf_data.source_hash == "a" * 64
        assert conf_data.smiles == "O"

        record_back = conf_data.to_conformer_record(conformer_id=42)
        assert isinstance(record_back, ConformerRecord)
        assert record_back.conformer_id == 42
        assert np.allclose(record_back.coords, record.coords)
        assert math.isclose(record_back.energy, record.energy, rel_tol=1e-5)
        assert math.isclose(record_back.boltzmann_weight, record.boltzmann_weight, rel_tol=1e-5)
        assert record_back.qm_method == "DFT/wB97M-V/def2-QZVPP"
        assert record_back.source_hash == "a" * 64

    def test_from_xyz_file_parsing(self) -> None:
        """Parsing an authentic XYZ file must create a validated ConformerData with SHA-256 hash."""
        xyz_content = (
            "3\n"
            "Water molecule ground state DFT geometry [eV]\n"
            f"O  {WATER_POS[0][0]:.6f}  {WATER_POS[0][1]:.6f}  {WATER_POS[0][2]:.6f}\n"
            f"H  {WATER_POS[1][0]:.6f}  {WATER_POS[1][1]:.6f}  {WATER_POS[1][2]:.6f}\n"
            f"H  {WATER_POS[2][0]:.6f}  {WATER_POS[2][1]:.6f}  {WATER_POS[2][2]:.6f}\n"
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as tf:
            tf.write(xyz_content)
            temp_path = tf.name

        try:
            conf_data = ConformerData.from_xyz_file(temp_path, energy=WATER_ENERGY_EV)
            assert conf_data.num_nodes == 3
            assert conf_data.symbols == ["O", "H", "H"]
            assert torch.equal(conf_data.z, torch.tensor([8, 1, 1], dtype=torch.long))
            assert torch.allclose(conf_data.pos, torch.tensor(WATER_POS, dtype=torch.float32), atol=1e-5)
            assert conf_data.source_hash is not None
            assert len(conf_data.source_hash) == 64
            assert is_valid_conformer_data(conf_data) is True
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


# ==============================================================================
# 6. State Immutability Tests
# ==============================================================================


class TestStateImmutability:
    """Tests that all geometric transformations adhere strictly to pure functional immutability."""

    def test_translate_immutability(self) -> None:
        """translate() must return a fresh instance without altering original tensors."""
        orig_pos = torch.tensor(WATER_POS, dtype=torch.float32)
        orig_z = torch.tensor(WATER_Z, dtype=torch.long)
        data = ConformerData(z=orig_z, pos=orig_pos)

        pos_copy = orig_pos.clone()
        t_vec = torch.tensor([5.0, -2.0, 1.0], dtype=torch.float32)

        translated = data.translate(t_vec)

        # Original data.pos must be completely unmodified
        assert torch.equal(data.pos, pos_copy)
        # New translated.pos must be distinct in memory
        assert translated.pos.data_ptr() != data.pos.data_ptr()
        assert not torch.equal(translated.pos, data.pos)

    def test_rotate_immutability(self) -> None:
        """rotate() must return a fresh instance without altering original tensors."""
        orig_pos = torch.tensor(WATER_POS, dtype=torch.float32)
        orig_forces = torch.randn((3, 3), dtype=torch.float32)
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=orig_pos,
            forces=orig_forces,
        )

        pos_copy = orig_pos.clone()
        forces_copy = orig_forces.clone()

        r_mat = create_rotation_matrix_3d(0.5, -0.3, 0.8)
        rotated = data.rotate(r_mat)

        # Original tensors must remain untouched
        assert torch.equal(data.pos, pos_copy)
        assert torch.equal(data.forces, forces_copy)
        # New rotated tensors must be distinct memory buffers
        assert rotated.pos.data_ptr() != data.pos.data_ptr()
        assert rotated.forces.data_ptr() != data.forces.data_ptr()

    def test_center_at_com_immutability(self) -> None:
        """center_at_com() must return a fresh instance without altering original coordinates."""
        orig_pos = torch.tensor(WATER_POS, dtype=torch.float32)
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=orig_pos,
        )

        pos_copy = orig_pos.clone()
        centered = data.center_at_com()

        assert torch.equal(data.pos, pos_copy)
        assert centered.pos.data_ptr() != data.pos.data_ptr()


# ==============================================================================
# 7. Pure Functional Top-Level Wrapper Functions Tests
# ==============================================================================


class TestFunctionalWrappers:
    """Tests top-level pure functional wrapper functions for rotate, translate, COM, and batching."""

    def test_rotate_conformer_data_wrapper(self) -> None:
        """rotate_conformer_data wrapper must return rotated ConformerData."""
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
        )
        r_mat = create_rotation_matrix_3d(0.2, 0.4, 0.6)
        rotated = rotate_conformer_data(data, r_mat)
        expected = data.rotate(r_mat)
        assert torch.allclose(rotated.pos, expected.pos, atol=1e-6)

    def test_translate_conformer_data_wrapper(self) -> None:
        """translate_conformer_data wrapper must return translated ConformerData."""
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
        )
        t_vec = torch.tensor([1.0, 2.0, 3.0], dtype=torch.float32)
        translated = translate_conformer_data(data, t_vec)
        expected = data.translate(t_vec)
        assert torch.allclose(translated.pos, expected.pos, atol=1e-6)

    def test_center_at_com_conformer_data_wrapper(self) -> None:
        """center_at_com_conformer_data wrapper must return COM-centered ConformerData."""
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
        )
        centered = center_at_com_conformer_data(data)
        new_com = centered.center_of_mass()
        assert torch.allclose(new_com, torch.zeros(3), atol=1e-5)

    def test_batch_conformer_data_wrapper(self) -> None:
        """batch_conformer_data wrapper must collate ConformerData instances into Batch."""
        d1 = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
        )
        d2 = ConformerData(
            z=torch.tensor(METHANE_Z, dtype=torch.long),
            pos=torch.tensor(METHANE_POS, dtype=torch.float32),
        )
        batched = batch_conformer_data([d1, d2])
        assert isinstance(batched, Batch)
        assert batched.num_graphs == 2
        assert batched.num_nodes == 3 + 5

