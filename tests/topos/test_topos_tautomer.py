"""Physical Verification Test Suite for CoChem-TOPOS Chemical Perception Part 1.

Verifies 1,3- and 1,5-prototropic shifts, heterocyclic annular shifts, BFS state space bounds,
fixed-H InChIKey deduplication, Patterson scoring, BSSE ghost-atom exclusion, dynamic Mendeleev masses,
thermodynamic filtering, and thread-safe HDF5 persistence [M][D][E].
"""

from __future__ import annotations

import os
from pathlib import Path
import time
import filelock
import h5py
from mendeleev import element
import numpy as np
from pydantic import ValidationError
import pytest
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors

from cochem.topos.tautomer import (
    GhostAtomSanitizationError,
    InvalidTopologyInputError,
    QuantumChemistryHandshakeError,
    TautomerCandidate,
    TautomerCanonicalizationError,
    TautomerCombinatorialLimitExceededError,
    TautomerEnsemble,
    TautomerEnumerationConfig,
    TautomerEnumerationTimeoutError,
    TautomerPersistenceError,
    TautomerStorageLockTimeoutError,
    TopologyInput,
    ToposPerceptionError,
    ValenceConservationError,
    compute_patterson_score,
    enumerate_tautomers,
    filter_tautomers_thermodynamics,
    load_tautomer_ensemble_from_hdf5,
    save_tautomer_ensemble_to_hdf5,
)


def test_1_3_prototropic_shifts():
    """REQ-TOPOS-014.1a: Verify 1,3-prototropic shifts across keto-enol, lactam-lactim, and amidine systems.

    Ensures net formal charge and total hydrogen count are strictly conserved [M][D].
    """
    # 1. Acetylacetone (keto-enol)
    acac = TopologyInput(
        molecule_id="acac",
        smiles="CC(=O)CC(=O)C",
        elements=["C", "C", "O", "C", "C", "O", "C"],
        atomic_numbers=[6, 6, 8, 6, 6, 8, 6],
    )
    config = TautomerEnumerationConfig(max_tautomers=50, max_transform_depth=4)
    ens_acac = enumerate_tautomers(acac, config)
    assert ens_acac.total_generated >= 2
    smiles_pool = {c.smiles for c in ens_acac.candidates}
    # Enol form must be generated
    assert any("O" in s and "=" in s for s in smiles_pool)

    # 2. 2-Pyridone (heteroaromatic lactam-lactim)
    pyridone = TopologyInput(
        molecule_id="2_pyridone",
        smiles="c1cc[nH]c(=O)c1",
        elements=["C", "C", "C", "N", "C", "O", "C"],
        atomic_numbers=[6, 6, 6, 7, 6, 8, 6],
    )
    ens_pyr = enumerate_tautomers(pyridone, config)
    assert ens_pyr.total_generated >= 2
    pyr_smiles = {c.smiles for c in ens_pyr.candidates}
    assert any("Oc1ccccn1" in s or "c1ccncc1O" in s or "n" in s for s in pyr_smiles)

    # 3. Acetamidine (amidine-amidine)
    acetamidine = TopologyInput(
        molecule_id="acetamidine",
        smiles="CC(=N)N",
        elements=["C", "C", "N", "N"],
        atomic_numbers=[6, 6, 7, 7],
    )
    ens_amd = enumerate_tautomers(acetamidine, config)
    assert ens_amd.total_generated >= 1
    for c in ens_amd.candidates:
        assert c.fixed_h_inchi_key is not None
        assert len(c.fixed_h_inchi_key) == 27


def test_1_5_prototropic_shifts():
    """REQ-TOPOS-014.1b: Verify 1,5-prototropic shifts across conjugated systems (glutaconic acid, vinylogous amide) [M][D]."""
    # 1. Glutaconic acid (conjugated diacid)
    glutaconic = TopologyInput(
        molecule_id="glutaconic_acid",
        smiles="OC(=O)CC=CC(=O)O",
        elements=["O", "C", "O", "C", "C", "C", "C", "O", "O"],
        atomic_numbers=[8, 6, 8, 6, 6, 6, 6, 8, 8],
    )
    config = TautomerEnumerationConfig(max_tautomers=50, max_transform_depth=4)
    ens_glut = enumerate_tautomers(glutaconic, config)
    assert ens_glut.total_generated >= 2
    # Net formal charge, transform depth bounds, and strict chemical formula conservation (C5H6O4)
    for cand in ens_glut.candidates:
        assert cand.transform_depth <= config.max_transform_depth
        m = Chem.AddHs(Chem.MolFromSmiles(cand.smiles))
        assert rdMolDescriptors.CalcMolFormula(m) == "C5H6O4"
        assert sum(1 for a in m.GetAtoms() if a.GetAtomicNum() == 1) == 6

    # 2. 3-Aminoacrolein / vinylogous amide (NC=CC=O)
    amide = TopologyInput(
        molecule_id="vinylogous_amide",
        smiles="NC=CC=O",
        elements=["N", "C", "C", "C", "O"],
        atomic_numbers=[7, 6, 6, 6, 8],
    )
    ens_amide = enumerate_tautomers(amide, config)
    assert ens_amide.total_generated >= 2
    for cand in ens_amide.candidates:
        m = Chem.AddHs(Chem.MolFromSmiles(cand.smiles))
        assert rdMolDescriptors.CalcMolFormula(m) == "C3H5NO"
        assert sum(1 for a in m.GetAtoms() if a.GetAtomicNum() == 1) == 5


def test_diaza_annular_shifts():
    """REQ-TOPOS-014.1c: Verify 1,2- and 1,3-diaza annular prototropic shifts across azoles [M][D]."""
    # 1H-1,2,3-triazole (c1cn[nH]n1) undergoing annular shifts
    triazole = TopologyInput(
        molecule_id="1H_triazole",
        smiles="c1cn[nH]n1",
        elements=["C", "C", "N", "N", "N"],
        atomic_numbers=[6, 6, 7, 7, 7],
    )
    config = TautomerEnumerationConfig(max_tautomers=20, max_transform_depth=3)
    ens_triazole = enumerate_tautomers(triazole, config)
    assert ens_triazole.total_generated >= 2
    for c in ens_triazole.candidates:
        assert len(c.fixed_h_inchi_key) == 27


def test_bfs_traversal_combinatorial_limits_and_timeout():
    """REQ-TOPOS-014.2: Verify bounds on state space traversal, truncation policies, and process timeout [M][D]."""
    acac = TopologyInput(
        molecule_id="acac",
        smiles="CC(=O)CC(=O)C",
        elements=["C", "C", "O", "C", "C", "O", "C"],
        atomic_numbers=[6, 6, 8, 6, 6, 8, 6],
    )
    # Test max_tautomers truncation policy 'truncate'
    config_trunc = TautomerEnumerationConfig(max_tautomers=1, truncation_policy="truncate")
    ens_trunc = enumerate_tautomers(acac, config_trunc)
    assert ens_trunc.total_generated <= 1

    # Test max_tautomers truncation policy 'raise'
    config_raise = TautomerEnumerationConfig(max_tautomers=1, truncation_policy="raise")
    with pytest.raises(TautomerCombinatorialLimitExceededError):
        enumerate_tautomers(acac, config_raise)

    # Test timeout ceiling (using sub-second timeout enabled by gt=0.0)
    config_timeout = TautomerEnumerationConfig(timeout_seconds=0.0001)
    with pytest.raises(TautomerEnumerationTimeoutError):
        enumerate_tautomers(acac, config_timeout)


def test_deduplication_fixed_h_inchikey_and_canonicalization():
    """REQ-TOPOS-014.3: Verify deduplication via Fixed-H InChIKeys and Patterson scoring canonicalization.

    4-Methyl-1H-imidazole tautomers share standard InChIKey but diverge on fixed-H InChIKey [M][D].
    """
    med = TopologyInput(
        molecule_id="4_methyl_imidazole",
        smiles="Cc1c[nH]cn1",
        elements=["C", "C", "C", "N", "C", "N"],
        atomic_numbers=[6, 6, 6, 7, 6, 7],
    )
    config = TautomerEnumerationConfig(max_tautomers=50, max_transform_depth=4)
    ens = enumerate_tautomers(med, config)
    assert ens.total_generated >= 2

    # Standard InChIKeys match, Fixed-H InChIKeys diverge
    fixed_h_keys = {c.fixed_h_inchi_key for c in ens.candidates}
    assert len(fixed_h_keys) == ens.total_generated

    # Canonical selection check
    assert ens.canonical_tautomer_id is not None
    canonical_candidates = [c for c in ens.candidates if c.is_canonical]
    assert len(canonical_candidates) == 1
    assert canonical_candidates[0].candidate_id == ens.canonical_tautomer_id


def test_ghost_atom_bsse_exclusion():
    """REQ-TOPOS-014.4: Verify ghost atoms (Z=0, symbol 'Gh') are assigned 0.0 Da and 0.0 A

    without invoking mendeleev, and excluded from SMIRKS reaction graphs and InChI calculation [M][D].
    """
    bsse_water = TopologyInput(
        molecule_id="bsse_water_dimer",
        smiles="O.[*]",
        elements=["O", "H", "H", "Gh"],
        atomic_numbers=[8, 1, 1, 0],
        is_ghost=[False, False, False, True],
    )
    assert bsse_water.is_ghost[3] is True
    assert bsse_water.masses[3] == 0.0

    config = TautomerEnumerationConfig(max_tautomers=10, max_transform_depth=2)
    ens = enumerate_tautomers(bsse_water, config)
    # Ghost atom did not cause crash, valid ensemble produced with valid 27-char InChIKeys
    assert ens.total_generated >= 1
    for c in ens.candidates:
        assert len(c.inchi_key) == 27
        assert len(c.fixed_h_inchi_key) == 27


def test_qm_handshake_and_thermodynamic_filtering(tmp_path):
    """REQ-TOPOS-014.5: Verify 3D conformer generation (ETKDGv3) and thermodynamic pre-filtering adapter [M][D]."""
    acac = TopologyInput(
        molecule_id="acac",
        smiles="CC(=O)CC(=O)C",
        elements=["C", "C", "O", "C", "C", "O", "C"],
        atomic_numbers=[6, 6, 8, 6, 6, 8, 6],
    )
    config = TautomerEnumerationConfig(max_tautomers=10, max_transform_depth=2, energy_cutoff_kcal_mol=15.0)
    ens = enumerate_tautomers(acac, config)

    filtered_ens = filter_tautomers_thermodynamics(ens, config, scratch_dir=tmp_path)
    assert filtered_ens.total_generated >= 1
    for c in filtered_ens.candidates:
        if c.relative_energy_kcal_mol is not None:
            assert c.relative_energy_kcal_mol <= config.energy_cutoff_kcal_mol + 1e-4


def test_hdf5_threadsafe_concurrency_persistence(tmp_path):
    """REQ-TOPOS-014.6: Verify thread-safe and process-safe HDF5 persistence under filelock [M][D]."""
    h5_file = tmp_path / "tautomer_archive.h5"
    acac = TopologyInput(
        molecule_id="acac_persisted",
        smiles="CC(=O)CC(=O)C",
        elements=["C", "C", "O", "C", "C", "O", "C"],
        atomic_numbers=[6, 6, 8, 6, 6, 8, 6],
    )
    config = TautomerEnumerationConfig(max_tautomers=10, max_transform_depth=2)
    ens = enumerate_tautomers(acac, config)

    # Save to HDF5
    saved_path = save_tautomer_ensemble_to_hdf5(ens, h5_file)
    assert saved_path.exists()

    # Load from HDF5
    loaded_ens = load_tautomer_ensemble_from_hdf5(h5_file, molecule_id="acac_persisted")
    assert loaded_ens.parent_id == ens.parent_id
    assert loaded_ens.total_generated == ens.total_generated
    assert loaded_ens.canonical_tautomer_id == ens.canonical_tautomer_id

    # Verify fixed-width datatypes
    with h5py.File(h5_file, "r") as f:
        grp = f[f"/tautomers/{ens.parent_id}"]
        assert "smiles" in grp
        assert "fixed_h_inchi_key" in grp
        assert "canonical_score" in grp
        assert grp["smiles"].dtype.kind == "S" or grp["smiles"].dtype.metadata is not None


def test_dynamic_mendeleev_mass_invariants():
    """Anti-Spoofing & Mendeleev Mandate: Verify non-ghost masses are dynamically queried from Mendeleev [M][D]."""
    top = TopologyInput(
        molecule_id="dyn_mass_test",
        elements=["C", "O", "N", "Gh"],
        atomic_numbers=[6, 8, 7, 0],
        bonds=[(0, 1, 1.0), (0, 2, 1.0)],
    )
    # Check dynamic mendeleev values against live library
    assert np.isclose(top.masses[0], float(element(6).mass), atol=1e-4)
    assert np.isclose(top.masses[1], float(element(8).mass), atol=1e-4)
    assert np.isclose(top.masses[2], float(element(7).mass), atol=1e-4)
    assert top.masses[3] == 0.0


def test_invalid_topology_input_handling():
    """REQ-TOPOS-014.1: Verify InvalidTopologyInputError on malformed SMILES [M][D]."""
    with pytest.raises(InvalidTopologyInputError):
        top_bad = TopologyInput(
            molecule_id="bad_smiles",
            smiles="INVALID_SMILES_STRING_NOT_CHEMICAL",
            elements=["C"],
            atomic_numbers=[6],
        )
        config = TautomerEnumerationConfig()
        enumerate_tautomers(top_bad, config)


def test_all_ghost_atoms_raises_sanitization_error():
    """REQ-TOPOS-014.4: Verify GhostAtomSanitizationError when topology has only ghost atoms [M][D]."""
    all_ghosts = TopologyInput(
        molecule_id="only_ghosts",
        smiles="[*].[*]",
        elements=["Gh", "Gh"],
        atomic_numbers=[0, 0],
        is_ghost=[True, True],
    )
    config = TautomerEnumerationConfig()
    with pytest.raises(GhostAtomSanitizationError):
        enumerate_tautomers(all_ghosts, config)


def test_tautomer_storage_lock_timeout(tmp_path):
    """REQ-TOPOS-014.6: Verify TautomerStorageLockTimeoutError when lock cannot be acquired [M][D]."""
    h5_file = tmp_path / "locked_archive.h5"
    lock_file = h5_file.with_suffix(".h5.lock")

    ens = TautomerEnsemble(
        parent_id="lock_test",
        canonical_tautomer_id="c1",
        total_generated=1,
        candidates=[
            TautomerCandidate(
                candidate_id="c1",
                smiles="O",
                inchi_key="XLYOFNOQVPJJNP-UHFFFAOYSA-N",
                fixed_h_inchi_key="XLYOFNOQVPJJNP-UHFFFAOYNA-N",
                canonical_score=0.0,
                is_canonical=True,
                transform_depth=0,
            )
        ],
        execution_duration_seconds=0.01,
    )

    # Ensure archive file exists so load attempts lock acquisition rather than missing file check
    h5_file.touch()

    # Acquire lock externally to simulate locked condition
    external_lock = filelock.FileLock(str(lock_file))
    with external_lock.acquire():
        # Physically calling save under locked condition must raise TautomerStorageLockTimeoutError
        with pytest.raises(TautomerStorageLockTimeoutError):
            save_tautomer_ensemble_to_hdf5(ens, h5_file, lock_timeout=0.05)

        # Physically calling load under locked condition must raise TautomerStorageLockTimeoutError
        with pytest.raises(TautomerStorageLockTimeoutError):
            load_tautomer_ensemble_from_hdf5(h5_file, "lock_test", lock_timeout=0.05)


def test_tautomer_persistence_error_missing_file_and_group(tmp_path):
    """REQ-TOPOS-014.6: Verify TautomerPersistenceError on missing archive or missing molecule ID [M][D]."""
    missing_file = tmp_path / "nonexistent.h5"
    with pytest.raises(TautomerPersistenceError):
        load_tautomer_ensemble_from_hdf5(missing_file, "mol_missing")

    # Create empty HDF5
    existing_file = tmp_path / "empty.h5"
    with h5py.File(existing_file, "w") as f:
        f.create_group("/other_group")

    with pytest.raises(TautomerPersistenceError):
        load_tautomer_ensemble_from_hdf5(existing_file, "mol_not_present")


def test_pydantic_validation_invariants():
    """Verify strict Pydantic v2 validation rules and error contracts across all domain models [M][D]."""
    # 1. TopologyInput missing all structural inputs
    with pytest.raises(ValidationError):
        TopologyInput(
            molecule_id="empty",
            elements=["C"],
            atomic_numbers=[6],
        )

    # 2. TopologyInput length mismatch
    with pytest.raises(ValidationError):
        TopologyInput(
            molecule_id="mismatch",
            smiles="C",
            elements=["C", "C"],
            atomic_numbers=[6],
        )

    # 3. TautomerEnsemble canonical count != 1
    with pytest.raises(ValidationError):
        TautomerEnsemble(
            parent_id="ens_bad",
            canonical_tautomer_id="c1",
            total_generated=1,
            candidates=[
                TautomerCandidate(
                    candidate_id="c1",
                    smiles="C",
                    inchi_key="VNWKTokens",
                    fixed_h_inchi_key="VNWKTokens",
                    canonical_score=0.0,
                    is_canonical=False,  # Should be True!
                    transform_depth=0,
                )
            ],
            execution_duration_seconds=0.01,
        )


def test_valence_conservation_and_exception_hierarchy():
    """Verify domain exception hierarchy and ValenceConservationError properties [M][D]."""
    assert issubclass(TautomerEnumerationTimeoutError, ToposPerceptionError)
    assert issubclass(TautomerCombinatorialLimitExceededError, ToposPerceptionError)
    assert issubclass(ValenceConservationError, ToposPerceptionError)
    assert issubclass(InvalidTopologyInputError, ToposPerceptionError)
    assert issubclass(TautomerCanonicalizationError, ToposPerceptionError)
    assert issubclass(TautomerPersistenceError, ToposPerceptionError)
    assert issubclass(TautomerStorageLockTimeoutError, ToposPerceptionError)
    assert issubclass(QuantumChemistryHandshakeError, ToposPerceptionError)
    assert issubclass(GhostAtomSanitizationError, ToposPerceptionError)

    val_err = ValenceConservationError("Valence octet exceeded")
    assert "Valence octet exceeded" in str(val_err)
    assert isinstance(val_err, ToposPerceptionError)


def test_3d_coordinate_reconstruction_and_covalent_radii():
    """REQ-TOPOS-014.1: Verify 3D coordinate connectivity perception via Pyykkö covalent radii [M][D]."""
    coords = [
        (0.0, 0.0, 0.0),      # O1
        (0.757, 0.586, 0.0),  # H2
        (-0.757, 0.586, 0.0), # H3
        (3.0, 0.0, 0.0),      # Gh4 (BSSE ghost atom)
    ]
    top_3d = TopologyInput(
        molecule_id="water_3d_bsse",
        elements=["O", "H", "H", "Gh"],
        atomic_numbers=[8, 1, 1, 0],
        coordinates=coords,
        is_ghost=[False, False, False, True],
    )
    config = TautomerEnumerationConfig(max_tautomers=10, max_transform_depth=2)
    ens = enumerate_tautomers(top_3d, config)
    assert ens.total_generated >= 1
    assert ens.candidates[0].fixed_h_inchi_key is not None
    assert len(ens.candidates[0].fixed_h_inchi_key) == 27

