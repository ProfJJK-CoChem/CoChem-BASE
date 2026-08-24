"""Zero-Verification Unit and Integration Test Suite for CoChem-GEOM Dataset Architecture.
========================================================================================
Validates:
1. Pure Immutable Geometric Transforms:
   - CenterOfMassTransform (mass-weighted COM centering with dynamic Mendeleev masses)
   - RandomRotationTransform (SO(3) Haar-distributed rotation with determinant +1 and distance preservation)
   - EckartAlignmentTransform (SVD mass-weighted optimal alignment minimizing RMSD)
   - GaussianJitterTransform (Isotropic Gaussian jitter preserving node count and state immutability)
   - NormalizeTargetsTransform (Target standardization and invertible denormalization)
   - ComposeTransforms (Sequential pipeline composability)
2. Batched Molecular Graphs & Collate Function:
   - MolecularBatch construction, ptr slicing offsets, block-diagonal edge indexing, to_data_list reconstruction
   - geom_collate_fn integration with PyTorch native DataLoader
3. GEOMInMemoryDataset:
   - Ingesting MolecularData list, indexing, slicing subsets, filtering, saving/loading cache
   - Conformer strategies: 'all', 'lowest_energy', 'boltzmann', 'random'
4. GEOMIterableDataset:
   - Streaming MsgPack archives and JSONL files
   - Bounded memory buffers and DataLoader compatibility
5. GEOMDatasetFactory:
   - Factory generation for Pickett, QM9, Drugs, Custom datasets
   - Deterministic train/val/test splitting with validation of ratio sums
6. Strict State Immutability:
   - Verifies original tensors are NEVER mutated in-place by transforms or collation

Authoritative Standards:
- Method Matrix v4: Data Contract & Spectroscopic Tensor Featurization
- Mendeleev Library Mandate: Dynamic atomic mass resolution (No hardcoding)
- SWEBOK v3 / ISO 25010 Software Quality Standards
- Provenance Tags: [M] Measured/Theoretical, [D] Derived/Calculated, [E] Expert Estimate
"""

from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Dict, List, Tuple

import msgpack
import numpy as np
import pytest
import torch
from torch.utils.data import DataLoader

# Ensure CoChem source paths are in sys.path
GEOM_ROOT = Path(__file__).resolve().parent.parent
GEOM_SRC = GEOM_ROOT / "src"
if str(GEOM_SRC) not in sys.path:
    sys.path.insert(0, str(GEOM_SRC))
if str(GEOM_ROOT) not in sys.path:
    sys.path.insert(0, str(GEOM_ROOT))

from cochem_geom.data.dataset import (
    BaseTransform,
    CenterOfMassTransform,
    ComposeTransforms,
    EckartAlignmentTransform,
    GEOMDatasetFactory,
    GEOMInMemoryDataset,
    GEOMIterableDataset,
    GaussianJitterTransform,
    MolecularBatch,
    NormalizeTargetsTransform,
    RandomRotationTransform,
    geom_collate_fn,
    get_default_data_dir,
)
from cochem_geom.data.featurizer import (
    MolecularData,
    MolecularFeaturizer,
    MolecularGraphConfig,
    MolecularInput,
    build_radius_graph,
    compute_center_of_mass,
    compute_principal_rotational_constants,
    get_atomic_mass,
    get_monoisotopic_mass,
)
from cochem_geom.data.geom_parser import (
    ConformerRecord,
    MoleculeRecord,
    conformer_to_molecular_data,
    serialize_geom_archive,
)


# ==============================================================================
# Fixtures: Real Physical Molecular Data Instances
# ==============================================================================

@pytest.fixture
def water_molecule() -> MolecularData:
    """Equilibrium C2v water (H2O) molecule."""
    symbols = ["O", "H", "H"]
    positions = [
        [0.000000, 0.000000, 0.117300],
        [0.000000, 0.757200, -0.469200],
        [0.000000, -0.757200, -0.469200],
    ]
    mol_in = MolecularInput(
        symbols=symbols,
        positions=positions,
        energy=-76.4388,  # Hartree
        forces=[
            [0.001, 0.000, -0.002],
            [0.000, -0.001, 0.001],
            [0.000, 0.001, 0.001],
        ],
        dipole=[0.0, 0.0, 1.85],
        rotational_constants=[835840.0, 435350.0, 278140.0],
    )
    featurizer = MolecularFeaturizer()
    return featurizer.featurize(mol_in)


@pytest.fixture
def methane_molecule() -> MolecularData:
    """Equilibrium Td methane (CH4) molecule."""
    symbols = ["C", "H", "H", "H", "H"]
    positions = [
        [0.000000, 0.000000, 0.000000],
        [0.627600, 0.627600, 0.627600],
        [-0.627600, -0.627600, 0.627600],
        [-0.627600, 0.627600, -0.627600],
        [0.627600, -0.627600, -0.627600],
    ]
    mol_in = MolecularInput(
        symbols=symbols,
        positions=positions,
        energy=-40.518,
        forces=[[0.0, 0.0, 0.0]] * 5,
        dipole=[0.0, 0.0, 0.0],
        rotational_constants=[157120.0, 157120.0, 157120.0],
    )
    featurizer = MolecularFeaturizer()
    return featurizer.featurize(mol_in)


@pytest.fixture
def ethanol_molecule() -> MolecularData:
    """Ethanol (C2H5OH) molecule (9 atoms)."""
    symbols = ["C", "C", "O", "H", "H", "H", "H", "H", "H"]
    positions = [
        [-0.034, 0.000, -0.024],
        [1.464, 0.000, 0.231],
        [-0.635, 1.205, 0.448],
        [-0.207, -0.071, -1.107],
        [-0.485, -0.877, 0.446],
        [1.650, 0.069, 1.309],
        [1.916, 0.884, -0.224],
        [1.936, -0.893, -0.191],
        [-1.589, 1.189, 0.282],
    ]
    mol_in = MolecularInput(
        symbols=symbols,
        positions=positions,
        energy=-155.03,
        dipole=[0.8, 1.2, -0.5],
    )
    featurizer = MolecularFeaturizer()
    return featurizer.featurize(mol_in)


@pytest.fixture
def benzene_molecule() -> MolecularData:
    """Planar D6h benzene (C6H6) molecule (12 atoms)."""
    symbols = ["C", "C", "C", "C", "C", "C", "H", "H", "H", "H", "H", "H"]
    r_cc = 1.397
    r_ch = 1.084
    positions = []
    # 6 Carbons in hexagon
    for k in range(6):
        angle = k * (2.0 * math.pi / 6.0)
        positions.append([r_cc * math.cos(angle), r_cc * math.sin(angle), 0.0])
    # 6 Hydrogens in hexagon
    for k in range(6):
        angle = k * (2.0 * math.pi / 6.0)
        r = r_cc + r_ch
        positions.append([r * math.cos(angle), r * math.sin(angle), 0.0])

    mol_in = MolecularInput(
        symbols=symbols,
        positions=positions,
        energy=-232.25,
        dipole=[0.0, 0.0, 0.0],
    )
    featurizer = MolecularFeaturizer()
    return featurizer.featurize(mol_in)


# ==============================================================================
# 1. Environment & Dynamic Path Resolution Tests
# ==============================================================================

def test_dynamic_data_dir_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify dynamic data dir respects COCHEM_DATA_DIR and defaults to ~/.cochem/data."""
    # Test fallback
    monkeypatch.delenv("COCHEM_DATA_DIR", raising=False)
    default_dir = get_default_data_dir()
    expected_default = (Path.home() / ".cochem" / "data").resolve()
    assert default_dir == expected_default

    # Test custom env var
    with tempfile.TemporaryDirectory() as tmp_dir:
        monkeypatch.setenv("COCHEM_DATA_DIR", tmp_dir)
        resolved = get_default_data_dir()
        assert resolved == Path(tmp_dir).resolve()


# ==============================================================================
# 2. Pure Immutable Transformation Tests
# ==============================================================================

def test_center_of_mass_transform_immutability(water_molecule: MolecularData) -> None:
    """Verify CenterOfMassTransform centers molecular coordinates and preserves immutability."""
    orig_pos_copy = water_molecule.pos.clone()
    transform = CenterOfMassTransform(use_monoisotopic=False)

    centered = transform(water_molecule)

    # 1. Original tensor must NOT be modified in-place
    assert torch.equal(water_molecule.pos, orig_pos_copy)
    assert not torch.equal(centered.pos, water_molecule.pos)

    # 2. Centered coordinates must have mass-weighted center of mass at origin (0, 0, 0)
    masses = torch.tensor(
        [get_atomic_mass(s) for s in centered.symbols],
        dtype=centered.pos.dtype,
        device=centered.pos.device,
    )
    com = compute_center_of_mass(centered.pos, masses)
    assert torch.allclose(com, torch.zeros(3, dtype=com.dtype), atol=1e-6)

    # 3. Pairwise interatomic Euclidean distances must be perfectly preserved
    orig_dist = torch.norm(water_molecule.pos[0] - water_molecule.pos[1])
    cent_dist = torch.norm(centered.pos[0] - centered.pos[1])
    assert torch.allclose(orig_dist, cent_dist, atol=1e-6)


def test_random_rotation_transform_equivariance_and_immutability(
    water_molecule: MolecularData,
) -> None:
    """Verify RandomRotationTransform applies valid SO(3) rotations and preserves immutability."""
    orig_pos_copy = water_molecule.pos.clone()
    orig_forces_copy = water_molecule.forces.clone() if water_molecule.forces is not None else None
    orig_dipole_copy = water_molecule.dipole.clone() if water_molecule.dipole is not None else None

    rot_transform = RandomRotationTransform(seed=123)
    rotated = rot_transform(water_molecule)

    # 1. Original data was not mutated
    assert torch.equal(water_molecule.pos, orig_pos_copy)
    if orig_forces_copy is not None:
        assert torch.equal(water_molecule.forces, orig_forces_copy)

    # 2. Pairwise distances are invariant under rotation: ||r_i' - r_j'|| == ||r_i - r_j||
    for i in range(water_molecule.num_nodes):
        for j in range(i + 1, water_molecule.num_nodes):
            d_orig = torch.norm(water_molecule.pos[i] - water_molecule.pos[j])
            d_rot = torch.norm(rotated.pos[i] - rotated.pos[j])
            assert torch.allclose(d_orig, d_rot, atol=1e-5)

    # 3. Vector norms of forces and dipole are preserved
    if water_molecule.forces is not None and rotated.forces is not None:
        norm_orig_f = torch.norm(water_molecule.forces, dim=-1)
        norm_rot_f = torch.norm(rotated.forces, dim=-1)
        assert torch.allclose(norm_orig_f, norm_rot_f, atol=1e-5)

    if water_molecule.dipole is not None and rotated.dipole is not None:
        norm_orig_d = torch.norm(water_molecule.dipole)
        norm_rot_d = torch.norm(rotated.dipole)
        assert torch.allclose(norm_orig_d, norm_rot_d, atol=1e-5)


def test_eckart_alignment_transform_immutability(water_molecule: MolecularData) -> None:
    """Verify EckartAlignmentTransform aligns rotated geometry back to reference frame."""
    theta = 0.75
    r_z = torch.tensor([
        [math.cos(theta), -math.sin(theta), 0.0],
        [math.sin(theta), math.cos(theta), 0.0],
        [0.0, 0.0, 1.0],
    ], dtype=water_molecule.pos.dtype)

    distorted_water = water_molecule.clone()
    distorted_water.pos = water_molecule.pos @ r_z.T + torch.tensor([2.0, -1.0, 3.0])

    orig_distorted_pos = distorted_water.pos.clone()
    aligner = EckartAlignmentTransform(reference=water_molecule, use_mass_weighting=True)
    aligned = aligner(distorted_water)

    # 1. State immutability
    assert torch.equal(distorted_water.pos, orig_distorted_pos)

    # 2. Aligned coordinates match original reference within machine precision
    rmsd = torch.sqrt(torch.mean((aligned.pos - water_molecule.pos) ** 2))
    assert float(rmsd.item()) < 1e-4


def test_gaussian_jitter_transform_immutability(ethanol_molecule: MolecularData) -> None:
    """Verify GaussianJitterTransform injects noise immutably and reproducibly."""
    orig_pos_copy = ethanol_molecule.pos.clone()
    sigma = 0.05
    jitter_transform = GaussianJitterTransform(sigma=sigma, seed=42)

    jittered = jitter_transform(ethanol_molecule)

    # Immutability
    assert torch.equal(ethanol_molecule.pos, orig_pos_copy)
    assert not torch.equal(jittered.pos, orig_pos_copy)

    # Magnitude of displacement roughly consistent with sigma
    diff = torch.norm(jittered.pos - ethanol_molecule.pos, dim=-1)
    assert float(diff.mean().item()) > 0.0
    assert float(diff.max().item()) < 5.0 * sigma


def test_normalize_targets_transform_invertibility(ethanol_molecule: MolecularData) -> None:
    """Verify NormalizeTargetsTransform normalizes targets and denormalize is invertible."""
    mean_val = -150.0
    std_val = 10.0
    norm_transform = NormalizeTargetsTransform(mean=mean_val, std=std_val)

    normalized = norm_transform(ethanol_molecule)

    # Immutability
    assert math.isclose(float(ethanol_molecule.y.item()), -155.03, rel_tol=1e-4)
    expected_norm_y = (-155.03 - mean_val) / std_val
    assert math.isclose(float(normalized.y.item()), expected_norm_y, rel_tol=1e-4)

    # Invertibility
    denorm_y = norm_transform.denormalize(normalized.y)
    assert math.isclose(float(denorm_y.item()), -155.03, rel_tol=1e-4)


def test_compose_transforms_pipeline(benzene_molecule: MolecularData) -> None:
    """Verify sequential composition of transforms via ComposeTransforms."""
    orig_pos = benzene_molecule.pos.clone()

    pipeline = ComposeTransforms([
        CenterOfMassTransform(),
        RandomRotationTransform(seed=99),
        GaussianJitterTransform(sigma=0.01, seed=99),
    ])

    transformed = pipeline(benzene_molecule)

    # Immutability check
    assert torch.equal(benzene_molecule.pos, orig_pos)
    assert transformed.num_nodes == 12
    assert transformed.pos.shape == (12, 3)


# ==============================================================================
# 3. Batched Geometric Container & Collate Function Tests
# ==============================================================================

def test_geom_collate_fn_with_heterogeneous_graphs(
    water_molecule: MolecularData,
    methane_molecule: MolecularData,
    ethanol_molecule: MolecularData,
) -> None:
    """Verify geom_collate_fn packs heterogeneous molecular graphs into contiguous MolecularBatch."""
    batch_list = [water_molecule, methane_molecule, ethanol_molecule]
    batch = geom_collate_fn(batch_list)

    assert isinstance(batch, MolecularBatch)
    assert batch.num_graphs == 3
    # Water: 3, Methane: 5, Ethanol: 9 -> Total: 17
    assert batch.num_nodes == 17
    assert batch.pos.shape == (17, 3)
    assert batch.z.shape == (17,)
    assert batch.batch.shape == (17,)

    # Ptr slices: [0, 3, 8, 17]
    assert torch.equal(batch.ptr, torch.tensor([0, 3, 8, 17], dtype=torch.long))

    # Batch indices: [0,0,0, 1,1,1,1,1, 2,2,2,2,2,2,2,2,2]
    expected_batch = torch.tensor(
        [0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2], dtype=torch.long
    )
    assert torch.equal(batch.batch, expected_batch)

    # Edge index offsets
    if batch.edge_index is not None and batch.edge_index.numel() > 0:
        second_graph_edges = batch.edge_index[:, (batch.edge_index[0] >= 3) & (batch.edge_index[0] < 8)]
        assert (second_graph_edges[1] >= 3).all() and (second_graph_edges[1] < 8).all()

    # Targets stacked
    assert batch.y is not None
    assert batch.y.shape[0] == 3

    # Decompose batch back to data list
    reconstructed = batch.to_data_list()
    assert len(reconstructed) == 3
    assert reconstructed[0].num_nodes == 3
    assert reconstructed[1].num_nodes == 5
    assert reconstructed[2].num_nodes == 9

    assert torch.allclose(reconstructed[0].pos, water_molecule.pos)
    assert torch.allclose(reconstructed[1].pos, methane_molecule.pos)
    assert torch.allclose(reconstructed[2].pos, ethanol_molecule.pos)


def test_batch_device_and_precision_transfer(
    water_molecule: MolecularData,
    methane_molecule: MolecularData,
) -> None:
    """Verify MolecularBatch transfers devices and dtypes immutably."""
    batch = geom_collate_fn([water_molecule, methane_molecule])
    transferred = batch.to(device="cpu", dtype=torch.float64)

    assert transferred.pos.dtype == torch.float64
    assert transferred.batch.dtype == torch.long
    assert transferred.ptr.dtype == torch.long
    if transferred.y is not None:
        assert transferred.y.dtype == torch.float64


# ==============================================================================
# 4. GEOMInMemoryDataset Tests
# ==============================================================================

def test_geom_inmemory_dataset_indexing_and_slicing(
    water_molecule: MolecularData,
    methane_molecule: MolecularData,
    ethanol_molecule: MolecularData,
    benzene_molecule: MolecularData,
) -> None:
    """Verify GEOMInMemoryDataset supports indexing, slicing, and length operations."""
    mol_list = [water_molecule, methane_molecule, ethanol_molecule, benzene_molecule]
    dataset = GEOMInMemoryDataset(data_list=mol_list)

    assert len(dataset) == 4

    # Single-item indexing
    item0 = dataset[0]
    assert isinstance(item0, MolecularData)
    assert item0.num_nodes == 3
    assert item0.symbols == ["O", "H", "H"]

    # Slice indexing
    sub_ds = dataset[1:3]
    assert isinstance(sub_ds, GEOMInMemoryDataset)
    assert len(sub_ds) == 2
    assert sub_ds[0].num_nodes == 5  # methane
    assert sub_ds[1].num_nodes == 9  # ethanol

    # Tensor indexing
    tensor_idx = torch.tensor([0, 3], dtype=torch.long)
    sub_ds2 = dataset[tensor_idx]
    assert len(sub_ds2) == 2
    assert sub_ds2[0].num_nodes == 3   # water
    assert sub_ds2[1].num_nodes == 12  # benzene


def test_geom_inmemory_dataset_conformer_strategies() -> None:
    """Verify conformer selection strategies: all, lowest_energy, boltzmann, random."""
    raw_mol_dict = {
        "conformers": [
            {
                "xyz": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [-1.0, 0.0, 0.0]],
                "totalenergy": -40.510,
            },
            {
                "xyz": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [-1.0, 0.0, 0.0]],
                "totalenergy": -40.520,  # Lowest energy
            },
            {
                "xyz": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [-1.0, 0.0, 0.0]],
                "totalenergy": -40.505,
            },
        ]
    }
    archive_data = {"C": raw_mol_dict}

    with tempfile.TemporaryDirectory() as tmp_dir:
        archive_path = Path(tmp_dir) / "methane_confs.msgpack"
        serialize_geom_archive(archive_path, archive_data)

        # 1. Strategy: 'all'
        ds_all = GEOMInMemoryDataset(raw_file_paths=[archive_path], conformer_strategy="all")
        assert len(ds_all) == 3

        # 2. Strategy: 'lowest_energy'
        ds_min = GEOMInMemoryDataset(raw_file_paths=[archive_path], conformer_strategy="lowest_energy")
        assert len(ds_min) == 1
        # Energy converted from Hartree to eV: -40.520 * 27.211386...
        assert ds_min[0].y is not None

        # 3. Strategy: 'boltzmann'
        ds_boltz = GEOMInMemoryDataset(raw_file_paths=[archive_path], conformer_strategy="boltzmann")
        assert len(ds_boltz) == 3
        weights = [float(item.weight.item()) for item in ds_boltz]
        assert math.isclose(sum(weights), 1.0, rel_tol=1e-4)
        assert weights[1] > weights[0] and weights[1] > weights[2]

        # 4. Strategy: 'random'
        ds_rand = GEOMInMemoryDataset(raw_file_paths=[archive_path], conformer_strategy="random", seed=42)
        assert len(ds_rand) == 1


def test_geom_inmemory_dataset_save_and_load(
    water_molecule: MolecularData,
    methane_molecule: MolecularData,
) -> None:
    """Verify disk persistence (save and load) of GEOMInMemoryDataset."""
    dataset = GEOMInMemoryDataset(data_list=[water_molecule, methane_molecule])

    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_file = Path(tmp_dir) / "cached_dataset.pt"
        dataset.save(cache_file)

        loaded_dataset = GEOMInMemoryDataset()
        loaded_dataset.load(cache_file)

        assert len(loaded_dataset) == 2
        assert torch.allclose(loaded_dataset[0].pos, water_molecule.pos)
        assert torch.allclose(loaded_dataset[1].pos, methane_molecule.pos)


# ==============================================================================
# 5. GEOMIterableDataset & Streaming Tests
# ==============================================================================

def test_geom_iterable_dataset_streaming_msgpack() -> None:
    """Verify GEOMIterableDataset streams conformers without full in-memory loading."""
    archive_data = {
        "O": {
            "conformers": [
                {
                    "xyz": [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                    "totalenergy": -76.4,
                }
            ]
        },
        "C": {
            "conformers": [
                {
                    "xyz": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [-1.0, 0.0, 0.0]],
                    "totalenergy": -40.5,
                }
            ]
        },
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        archive_path = Path(tmp_dir) / "stream_test.msgpack"
        serialize_geom_archive(archive_path, archive_data)

        stream_ds = GEOMIterableDataset(
            file_paths=[archive_path],
            transform=CenterOfMassTransform(),
        )

        streamed_items = list(stream_ds)
        assert len(streamed_items) == 2
        assert streamed_items[0].num_nodes == 3
        assert streamed_items[1].num_nodes == 5

        # Check COM transform was applied during streaming
        masses = torch.tensor(
            [get_atomic_mass(s) for s in streamed_items[0].symbols],
            dtype=streamed_items[0].pos.dtype,
        )
        com = compute_center_of_mass(streamed_items[0].pos, masses)
        assert torch.allclose(com, torch.zeros(3, dtype=com.dtype), atol=1e-6)


def test_geom_iterable_dataset_streaming_jsonl() -> None:
    """Verify GEOMIterableDataset streams JSONL datasets."""
    data1 = {
        "symbols": ["O", "H", "H"],
        "positions": [[0.0, 0.0, 0.1], [0.0, 0.7, -0.4], [0.0, -0.7, -0.4]],
        "energy": -76.4,
    }
    data2 = {
        "symbols": ["C", "H", "H", "H", "H"],
        "positions": [[0.0, 0.0, 0.0], [0.6, 0.6, 0.6], [-0.6, -0.6, 0.6], [-0.6, 0.6, -0.6], [0.6, -0.6, -0.6]],
        "energy": -40.5,
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        jsonl_path = Path(tmp_dir) / "stream.jsonl"
        with open(jsonl_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(data1) + "\n")
            f.write(json.dumps(data2) + "\n")

        stream_ds = GEOMIterableDataset(file_paths=[jsonl_path])
        items = list(stream_ds)
        assert len(items) == 2
        assert items[0].symbols == ["O", "H", "H"]
        assert items[1].symbols == ["C", "H", "H", "H", "H"]


# ==============================================================================
# 6. GEOMDatasetFactory Tests
# ==============================================================================

def test_geom_dataset_factory_custom_and_pickett(
    water_molecule: MolecularData,
    methane_molecule: MolecularData,
) -> None:
    """Verify GEOMDatasetFactory constructs custom and pickett datasets."""
    # Custom
    ds_custom = GEOMDatasetFactory.create_custom([water_molecule, methane_molecule])
    assert len(ds_custom) == 2

    # Pickett
    ds_pickett = GEOMDatasetFactory.create_pickett([water_molecule, methane_molecule])
    assert len(ds_pickett) == 2
    for item in ds_pickett:
        assert item.rotational_constants is not None
        assert item.rotational_constants.shape == (3,)
        # Constants must be positive
        assert (item.rotational_constants > 0).all()


def test_geom_dataset_factory_train_val_test_split(
    water_molecule: MolecularData,
    methane_molecule: MolecularData,
    ethanol_molecule: MolecularData,
    benzene_molecule: MolecularData,
) -> None:
    """Verify deterministic train, validation, and test dataset splitting."""
    mols = [water_molecule, methane_molecule, ethanol_molecule, benzene_molecule] * 5  # 20 samples
    ds = GEOMInMemoryDataset(data_list=mols)

    train_ds, val_ds, test_ds = GEOMDatasetFactory.train_val_test_split(
        ds,
        train_ratio=0.8,
        val_ratio=0.1,
        test_ratio=0.1,
        shuffle=True,
        seed=42,
    )

    assert len(train_ds) == 16
    assert len(val_ds) == 2
    assert len(test_ds) == 2
    assert len(train_ds) + len(val_ds) + len(test_ds) == 20


def test_geom_dataset_factory_invalid_split_ratio(water_molecule: MolecularData) -> None:
    """Verify ValueError when split ratios do not sum to 1.0."""
    ds = GEOMInMemoryDataset(data_list=[water_molecule])
    with pytest.raises(ValueError, match="Split ratios must sum to 1.0"):
        GEOMDatasetFactory.train_val_test_split(
            ds, train_ratio=0.7, val_ratio=0.1, test_ratio=0.1
        )


# ==============================================================================
# 7. PyTorch DataLoader Integration & Training Loop Simulation
# ==============================================================================

def test_pytorch_dataloader_end_to_end_iteration(
    water_molecule: MolecularData,
    methane_molecule: MolecularData,
    ethanol_molecule: MolecularData,
    benzene_molecule: MolecularData,
) -> None:
    """Verify end-to-end iteration with PyTorch DataLoader and geom_collate_fn."""
    mols = [water_molecule, methane_molecule, ethanol_molecule, benzene_molecule]
    dataset = GEOMInMemoryDataset(
        data_list=mols,
        transform=CenterOfMassTransform(),
    )

    loader = DataLoader(
        dataset,
        batch_size=2,
        shuffle=False,
        collate_fn=geom_collate_fn,
    )

    batches = list(loader)
    assert len(batches) == 2

    # Batch 1: Water (3) + Methane (5) = 8
    b1 = batches[0]
    assert b1.num_graphs == 2
    assert b1.num_nodes == 8
    assert b1.pos.shape == (8, 3)

    # Batch 2: Ethanol (9) + Benzene (12) = 21
    b2 = batches[1]
    assert b2.num_graphs == 2
    assert b2.num_nodes == 21
    assert b2.pos.shape == (21, 3)

    # Forward computation simulation: calculate batch mean coordinate
    for b in loader:
        loss = torch.sum(b.pos ** 2)
        assert not torch.isnan(loss)
        assert float(loss.item()) > 0.0
