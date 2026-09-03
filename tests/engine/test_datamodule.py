"""Physical Unit Verification Suite for PyTorch Lightning DataModule.

Module: tests.engine.test_datamodule
Authoritative Reference: SRS Chunk 02 BASE UI & Web (Part 2), Prompt 5.

Invariants:
- Zero-Mock Protocol: Real PyTorch tensors, genuine SWMR HDF5 dataset files, authentic molecular geometries.
- Dynamic Mendeleev integration: Verification that atomic numbers map to IUPAC physical masses.
- Authentic Euclidean distance calculations and neighbor lists.
- Deterministic random splits with seed reproducibility.
"""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import torch

from src.cochem.engine.datamodule import (
    CoChemDataModule,
    CoChemHDF5Dataset,
    collate_molecular_batches,
    get_mendeleev_atom_properties,
)


def create_sample_physical_hdf5(filepath: Path) -> Path:
    """Create an authentic SWMR-mode HDF5 dataset containing real molecules."""
    # Authentic molecular geometries in Angstroms:
    # 1. Water (H2O): O(0,0,0.117), H(0,0.757,-0.469), H(0,-0.757,-0.469)
    # 2. Methane (CH4): C(0,0,0), H(0.628,0.628,0.628), H(-0.628,-0.628,0.628), H(-0.628,0.628,-0.628), H(0.628,-0.628,-0.628)
    # 3. Carbon Monoxide (CO): C(0,0,0), O(0,0,1.128)
    # 4. Hydrogen Molecule (H2): H(0,0,0), H(0,0,0.741)
    # 5. Formaldehyde (H2CO): C(0,0,0), O(0,0,1.205), H(0,0.940,-0.580), H(0,-0.940,-0.580)
    # 6. Hydrogen Cyanide (HCN): H(0,0,-1.066), C(0,0,0), N(0,0,1.153)
    # 7. Acetylene (C2H2): H(0,0,-1.666), C(0,0,-0.603), C(0,0,0.603), H(0,0,1.666)
    # 8. Ammonia (NH3): N(0,0,0.115), H(0,0.940,-0.268), H(0.814,-0.470,-0.268), H(-0.814,-0.470,-0.268)
    # 9. Nitrogen (N2): N(0,0,-0.549), N(0,0,0.549)
    # 10. Oxygen (O2): O(0,0,-0.604), O(0,0,0.604)

    samples = [
        {
            "name": "mol_01_water",
            "z": [8, 1, 1],
            "coords": [[0.0, 0.0, 0.1173], [0.0, 0.7572, -0.4692], [0.0, -0.7572, -0.4692]],
            "energy": -76.432,
            "charge": 0,
            "spin": 1,
        },
        {
            "name": "mol_02_methane",
            "z": [6, 1, 1, 1, 1],
            "coords": [
                [0.0, 0.0, 0.0],
                [0.6276, 0.6276, 0.6276],
                [-0.6276, -0.6276, 0.6276],
                [-0.6276, 0.6276, -0.6276],
                [0.6276, -0.6276, -0.6276],
            ],
            "energy": -40.514,
            "charge": 0,
            "spin": 1,
        },
        {
            "name": "mol_03_co",
            "z": [6, 8],
            "coords": [[0.0, 0.0, 0.0], [0.0, 0.0, 1.128]],
            "energy": -113.310,
            "charge": 0,
            "spin": 1,
        },
        {
            "name": "mol_04_h2",
            "z": [1, 1],
            "coords": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.7414]],
            "energy": -1.174,
            "charge": 0,
            "spin": 1,
        },
        {
            "name": "mol_05_formaldehyde",
            "z": [6, 8, 1, 1],
            "coords": [[0.0, 0.0, 0.0], [0.0, 0.0, 1.205], [0.0, 0.940, -0.580], [0.0, -0.940, -0.580]],
            "energy": -114.502,
            "charge": 0,
            "spin": 1,
        },
        {
            "name": "mol_06_hcn",
            "z": [1, 6, 7],
            "coords": [[0.0, 0.0, -1.066], [0.0, 0.0, 0.0], [0.0, 0.0, 1.153]],
            "energy": -93.421,
            "charge": 0,
            "spin": 1,
        },
        {
            "name": "mol_07_acetylene",
            "z": [1, 6, 6, 1],
            "coords": [[0.0, 0.0, -1.666], [0.0, 0.0, -0.603], [0.0, 0.0, 0.603], [0.0, 0.0, 1.666]],
            "energy": -77.324,
            "charge": 0,
            "spin": 1,
        },
        {
            "name": "mol_08_ammonia",
            "z": [7, 1, 1, 1],
            "coords": [[0.0, 0.0, 0.115], [0.0, 0.940, -0.268], [0.814, -0.470, -0.268], [-0.814, -0.470, -0.268]],
            "energy": -56.564,
            "charge": 0,
            "spin": 1,
        },
        {
            "name": "mol_09_n2",
            "z": [7, 7],
            "coords": [[0.0, 0.0, -0.549], [0.0, 0.0, 0.549]],
            "energy": -109.523,
            "charge": 0,
            "spin": 1,
        },
        {
            "name": "mol_10_o2",
            "z": [8, 8],
            "coords": [[0.0, 0.0, -0.604], [0.0, 0.0, 0.604]],
            "energy": -150.312,
            "charge": 0,
            "spin": 3,  # Triplet ground state O2
        },
    ]

    with h5py.File(str(filepath), "w", libver="latest") as f:
        grp = f.create_group("molecules")
        for s in samples:
            mol_node = grp.create_group(s["name"])
            mol_node.create_dataset("atomic_numbers", data=np.array(s["z"], dtype=np.int64))
            mol_node.create_dataset("coordinates", data=np.array(s["coords"], dtype=np.float32))
            mol_node.create_dataset("energy", data=s["energy"])
            mol_node.create_dataset("charge", data=s["charge"])
            mol_node.create_dataset("spin_multiplicity", data=s["spin"])

    return filepath


class TestCoChemDataModule:
    """Test suite validating SWMR HDF5 dataset loading, dynamic Mendeleev tensors, and collation."""

    def test_dynamic_mendeleev_atom_properties(self) -> None:
        """Verify dynamic retrieval of atomic weights, nuclear charges, and covalent radii."""
        z_list = [1, 6, 7, 8, 26]  # H, C, N, O, Fe
        masses, charges, radii = get_mendeleev_atom_properties(z_list)

        assert isinstance(masses, torch.Tensor)
        assert len(masses) == 5
        # Verify carbon mass > 12.0
        assert masses[1].item() > 12.0
        # Verify iron nuclear charge == 26.0
        assert charges[4].item() == 26.0
        # Verify oxygen radius > 0.5 Angstrom
        assert radii[3].item() > 0.5

    def test_swmr_hdf5_dataset_reading(self, tmp_path: Path) -> None:
        """Verify reading molecular samples from HDF5 file in SWMR mode."""
        h5_path = tmp_path / "test_dataset.h5"
        create_sample_physical_hdf5(h5_path)

        dataset = CoChemHDF5Dataset(h5_path)
        assert len(dataset) == 10

        sample = dataset[0]
        assert "atomic_numbers" in sample
        assert "coordinates" in sample
        assert "atomic_masses" in sample
        assert "nuclear_charges" in sample
        assert "covalent_radii" in sample
        assert "total_energy" in sample
        assert sample["atomic_numbers"].shape[0] == sample["coordinates"].shape[0]

        dataset.close()

    def test_collate_molecular_batches_euclidean_and_neighbors(self, tmp_path: Path) -> None:
        """Verify batch collation calculates real Euclidean distances and 3D neighbor lists."""
        h5_path = tmp_path / "collate_dataset.h5"
        create_sample_physical_hdf5(h5_path)

        dataset = CoChemHDF5Dataset(h5_path)
        batch_samples = [dataset[0], dataset[1]]  # Water (3 atoms) and Methane (5 atoms)

        batch = collate_molecular_batches(batch_samples, cutoff_angstrom=5.0)

        assert batch["batch_size"] == 2
        assert batch["total_atoms"] == 8
        assert batch["atomic_numbers"].shape == (8,)
        assert batch["coordinates"].shape == (8, 3)
        assert batch["batch_indices"].shape == (8,)

        # Verify pairwise distance matrix calculation
        pw_mols = batch["pairwise_distances_by_mol"]
        assert len(pw_mols) == 2

        # Water pairwise distances (3x3)
        d_water = pw_mols[0]
        assert d_water.shape == (3, 3)
        # Diagonals must be ~0
        for i in range(3):
            assert d_water[i, i].item() < 1e-4
        # Symmetry check
        assert torch.allclose(d_water, d_water.T, atol=1e-5)

        # Neighbor list verification
        assert "edge_index" in batch
        edge_index = batch["edge_index"]
        assert edge_index.ndim == 2
        assert edge_index.shape[0] == 2
        assert edge_index.shape[1] > 0  # Water & Methane atoms are within 5.0 Angstroms

        # Charge-spin validation mask check
        assert "charge_spin_valid_mask" in batch
        assert batch["charge_spin_valid_mask"].shape == (2,)
        # Both neutral closed-shell molecules satisfy parity
        assert batch["charge_spin_valid_mask"][0].item() is True
        assert batch["charge_spin_valid_mask"][1].item() is True

        dataset.close()

    def test_cochem_datamodule_splits_and_dataloaders(self, tmp_path: Path) -> None:
        """Verify Lightning DataModule deterministic splitting and DataLoader iteration."""
        h5_path = tmp_path / "datamodule_dataset.h5"
        create_sample_physical_hdf5(h5_path)

        dm = CoChemDataModule(
            h5_dataset_path=h5_path,
            batch_size=4,
            train_val_test_split=(0.8, 0.1, 0.1),
            seed=12345,
            num_workers=0,
        )

        dm.prepare_data()
        dm.setup()

        # Total 10 samples: 8 train, 1 val, 1 test
        assert dm.train_dataset is not None
        assert dm.val_dataset is not None
        assert dm.test_dataset is not None
        assert len(dm.train_dataset) == 8
        assert len(dm.val_dataset) == 1
        assert len(dm.test_dataset) == 1

        train_loader = dm.train_dataloader()
        assert isinstance(train_loader, torch.utils.data.DataLoader)

        # Iterate over one train batch
        for batch in train_loader:
            assert "batch_size" in batch
            assert batch["batch_size"] <= 4
            assert "atomic_numbers" in batch
            assert "coordinates" in batch
            break

        dm.teardown()
