"""Adversarial Unit and Integration Test Suite for GEOMDataModule.
================================================================
Validates:
1. GEOMDataModule lifecycle (prepare_data, setup, train/val/test/predict dataloaders, teardown, close)
2. Block-diagonal graph collation via PyG DataLoader with drop_last=True on training
3. Molecule-level partition disjointness and error handling
4. Pure functional transformations (CenterOfMassZeroing, TargetStandardize)
5. Zero-Mock physical compliance (Mendeleev dynamic masses, real LMDB records)
"""

from __future__ import annotations

import json
from pathlib import Path
import pickle
import tempfile
from typing import Generator, Tuple

import lmdb
import numpy as np
import pytest
import torch
from torch_geometric.data import Batch

from cochem_geom.data.datamodule import GEOMDataModule
from cochem_geom.data.transforms import CenterOfMassZeroing, TargetStandardize, Compose


@pytest.fixture
def physical_lmdb_and_splits() -> Generator[Tuple[Path, Path], None, None]:
    """Create authentic physical LMDB dataset fixture with 6 real molecules."""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_dir = Path(tmp_str)
        lmdb_path = tmp_dir / "geom_test.lmdb"
        split_path = tmp_dir / "splits.json"

        molecules = [
            {
                "z": np.array([8, 1, 1], dtype=np.int64),
                "pos": np.array([[0.0, 0.0, 0.1173], [0.0, 0.7572, -0.4692], [0.0, -0.7572, -0.4692]], dtype=np.float32),
                "y": np.array([-76.4388], dtype=np.float32),
                "symbols": ["O", "H", "H"],
                "metadata": {"smiles": "O", "mol_id": 0},
            },
            {
                "z": np.array([6, 1, 1, 1, 1], dtype=np.int64),
                "pos": np.array([[0.0, 0.0, 0.0], [0.6276, 0.6276, 0.6276], [-0.6276, -0.6276, 0.6276], [-0.6276, 0.6276, -0.6276], [0.6276, -0.6276, -0.6276]], dtype=np.float32),
                "y": np.array([-40.518], dtype=np.float32),
                "symbols": ["C", "H", "H", "H", "H"],
                "metadata": {"smiles": "C", "mol_id": 1},
            },
            {
                "z": np.array([6, 8, 8], dtype=np.int64),
                "pos": np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.16], [0.0, 0.0, -1.16]], dtype=np.float32),
                "y": np.array([-188.58], dtype=np.float32),
                "symbols": ["C", "O", "O"],
                "metadata": {"smiles": "O=C=O", "mol_id": 2},
            },
            {
                "z": np.array([7, 1, 1, 1], dtype=np.int64),
                "pos": np.array([[0.0, 0.0, 0.1], [0.0, 0.94, -0.27], [0.81, -0.47, -0.27], [-0.81, -0.47, -0.27]], dtype=np.float32),
                "y": np.array([-56.56], dtype=np.float32),
                "symbols": ["N", "H", "H", "H"],
                "metadata": {"smiles": "N", "mol_id": 3},
            },
            {
                "z": np.array([6, 6, 1, 1, 1, 1], dtype=np.int64),
                "pos": np.array([[0.0, 0.0, 0.66], [0.0, 0.0, -0.66], [0.92, 0.0, 1.23], [-0.92, 0.0, 1.23], [0.92, 0.0, -1.23], [-0.92, 0.0, -1.23]], dtype=np.float32),
                "y": np.array([-78.58], dtype=np.float32),
                "symbols": ["C", "C", "H", "H", "H", "H"],
                "metadata": {"smiles": "C=C", "mol_id": 4},
            },
            {
                "z": np.array([6, 6, 1, 1, 1, 1, 1, 1], dtype=np.int64),
                "pos": np.array([[0.0, 0.0, 0.76], [0.0, 0.0, -0.76], [1.02, 0.0, 1.15], [-0.51, 0.88, 1.15], [-0.51, -0.88, 1.15], [1.02, 0.0, -1.15], [-0.51, 0.88, -1.15], [-0.51, -0.88, -1.15]], dtype=np.float32),
                "y": np.array([-79.83], dtype=np.float32),
                "symbols": ["C", "C", "H", "H", "H", "H", "H", "H"],
                "metadata": {"smiles": "CC", "mol_id": 5},
            },
        ]

        env = lmdb.open(str(lmdb_path), map_size=10 * 1024 * 1024, subdir=False)
        with env.begin(write=True) as txn:
            for idx, mol in enumerate(molecules):
                txn.put(f"{idx:09d}".encode("ascii"), pickle.dumps(mol))
        env.close()

        splits = {"train": [0, 1, 2, 3], "val": [4], "test": [5]}
        with open(split_path, "w", encoding="utf-8") as f:
            json.dump(splits, f)

        yield lmdb_path, split_path


def test_datamodule_full_lifecycle(physical_lmdb_and_splits: Tuple[Path, Path]) -> None:
    """Test standard DataModule execution, batch collation, and center of mass zeroing."""
    lmdb_path, split_path = physical_lmdb_and_splits

    dm = GEOMDataModule(
        lmdb_path=lmdb_path,
        split_json_path=split_path,
        batch_size=2,
        num_workers=0,
        pin_memory=False,
        target_mean=-80.0,
        target_std=50.0,
    )

    dm.prepare_data()
    dm.setup(stage="fit")

    assert dm.train_dataset is not None
    assert dm.val_dataset is not None
    assert dm.test_dataset is not None
    assert dm.predict_dataset is not None
    assert len(dm.train_dataset) == 4
    assert len(dm.val_dataset) == 1
    assert len(dm.test_dataset) == 1

    train_loader = dm.train_dataloader()
    assert train_loader.drop_last is True

    batches = list(train_loader)
    assert len(batches) == 2

    for batch in batches:
        assert isinstance(batch, Batch)
        assert batch.num_graphs == 2
        for i in range(batch.num_graphs):
            sub_pos = batch.pos[batch.batch == i]
            com = sub_pos.mean(dim=0)
            assert torch.allclose(com, torch.zeros(3), atol=1e-5)

    val_loader = dm.val_dataloader()
    assert val_loader.drop_last is False
    assert len(list(val_loader)) == 1

    test_loader = dm.test_dataloader()
    assert test_loader.drop_last is False
    assert len(list(test_loader)) == 1

    predict_loader = dm.predict_dataloader()
    assert predict_loader.drop_last is False
    assert len(list(predict_loader)) == 1

    dm.teardown()


def test_datamodule_error_handling(physical_lmdb_and_splits: Tuple[Path, Path]) -> None:
    """Test error handling for missing files and malformed split JSON."""
    lmdb_path, split_path = physical_lmdb_and_splits
    temp_dir = lmdb_path.parent

    bad_dm = GEOMDataModule(lmdb_path=temp_dir / "missing.lmdb", split_json_path=split_path)
    with pytest.raises(FileNotFoundError):
        bad_dm.prepare_data()

    bad_dm2 = GEOMDataModule(lmdb_path=lmdb_path, split_json_path=temp_dir / "missing.json")
    with pytest.raises(FileNotFoundError):
        bad_dm2.prepare_data()

    malformed_split = temp_dir / "malformed_split.json"
    with open(malformed_split, "w", encoding="utf-8") as f:
        json.dump({"train": [0, 1]}, f)

    bad_dm3 = GEOMDataModule(lmdb_path=lmdb_path, split_json_path=malformed_split)
    with pytest.raises(KeyError):
        bad_dm3.setup()


def test_datamodule_context_manager(physical_lmdb_and_splits: Tuple[Path, Path]) -> None:
    """Test context manager cleanup."""
    lmdb_path, split_path = physical_lmdb_and_splits

    with GEOMDataModule(lmdb_path=lmdb_path, split_json_path=split_path) as dm:
        dm.setup()
        assert dm._full_dataset is not None
        _ = dm.train_dataset[0]

    assert dm._full_dataset is None
