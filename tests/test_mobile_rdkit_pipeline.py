"""Zero-Mock Test Suite for SMILES-to-3D Algorithmic Bridge (SRS Chunk 05).

Validates REQ-MOB-040 through REQ-MOB-043:
- REQ-MOB-040: Air-Gap Sanitization & Async Concurrency Isolation (length <= 2048, HTTP 422 mapping, thread isolation).
- REQ-MOB-041: Complete Valence Saturation & Explicit Hydrogen Addition.
- REQ-MOB-042: Deterministic Conformer Generation (ETKDGv3, seed=42) & 3-Tier Fallback Ladder.
- REQ-MOB-043: Forcefield Relaxation Hierarchy (MMFF94s -> UFF), Quantum Electronic States, and Standard XYZ.
- Zero-Mock mandate strictly enforced: No stubs, no fake returns, dynamic Mendeleev masses.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import tempfile
from typing import List

import mendeleev
import numpy as np
import pytest
from rdkit import Chem

from cochem.mobile.rdkit_bridge import (
    AtomCoordinate3DRecord,
    ConformerEmbeddingError,
    InvalidSmilesError,
    RDKit3DResult,
    Smiles3DConformerEngine,
    generate_deterministic_3d_coordinates,
    relax_geometry_and_calculate_energy,
    serialize_standard_xyz,
    smiles_to_3d,
    smiles_to_3d_async,
    validate_and_sanitize_smiles,
)


def test_airgap_sanitization_valid_inputs() -> None:
    """Verify whitespace trimming and valid SMILES parsing across typical organic structures."""
    clean_smi, mol = validate_and_sanitize_smiles("   CCO   \n")
    assert clean_smi == "CCO"
    assert mol is not None
    assert mol.GetNumAtoms() == 3

    # Benzene
    clean_smi, mol = validate_and_sanitize_smiles("c1ccccc1")
    assert clean_smi == "c1ccccc1"
    assert mol.GetNumAtoms() == 6


def test_airgap_sanitization_empty_and_whitespace() -> None:
    """Verify empty and whitespace-only SMILES trigger InvalidSmilesError with HTTP 422."""
    with pytest.raises(InvalidSmilesError) as exc_info:
        validate_and_sanitize_smiles("")
    assert exc_info.value.status_code == 422
    assert exc_info.value.http_status_code == 422
    assert "empty" in exc_info.value.message.lower()

    with pytest.raises(InvalidSmilesError) as exc_info2:
        validate_and_sanitize_smiles("    \t \n ")
    assert exc_info2.value.status_code == 422


def test_airgap_sanitization_length_boundary() -> None:
    """Verify length boundary check strictly enforces <= 2048 characters (REQ-MOB-040)."""
    # 2048 character SMILES (valid long carbon chain)
    valid_len_smi = "C" * 2048
    # Parsing 2048 carbons will parse in RDKit
    clean_smi, mol = validate_and_sanitize_smiles(valid_len_smi)
    assert len(clean_smi) == 2048
    assert mol.GetNumAtoms() == 2048

    # 2049 character SMILES must be rejected immediately
    over_boundary_smi = "C" * 2049
    with pytest.raises(InvalidSmilesError) as exc_info:
        validate_and_sanitize_smiles(over_boundary_smi)
    assert exc_info.value.status_code == 422
    assert "2048" in exc_info.value.message


def test_airgap_sanitization_malformed_syntax() -> None:
    """Verify malformed SMILES strings raise InvalidSmilesError with diagnostic details."""
    malformed_smiles_inputs = [
        "C1CC11",
        "invalid_chemical_string",
        "CC(=O)(O)(O)(O)O",  # Hypervalent invalid carbon
        "N#N#N#N",
        "[INVALID]",
    ]

    for bad_smi in malformed_smiles_inputs:
        with pytest.raises(InvalidSmilesError) as exc_info:
            validate_and_sanitize_smiles(bad_smi)
        assert exc_info.value.status_code == 422
        assert bad_smi in exc_info.value.smiles


def test_airgap_sanitization_type_error() -> None:
    """Verify non-string payloads raise structured InvalidSmilesError."""
    with pytest.raises(InvalidSmilesError) as exc_info:
        validate_and_sanitize_smiles(12345)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 422
    assert "string" in exc_info.value.message.lower()


def test_valence_saturation_explicit_hydrogens() -> None:
    """Verify explicit hydrogen saturation across diverse molecular topologies (REQ-MOB-041)."""
    # Ethanol: C2H6O -> 9 atoms
    res_ethanol = smiles_to_3d("CCO")
    assert res_ethanol.num_atoms == 9
    assert res_ethanol.atomic_symbols.count("C") == 2
    assert res_ethanol.atomic_symbols.count("O") == 1
    assert res_ethanol.atomic_symbols.count("H") == 6

    # Caffeine: C8H10N4O2 -> 24 atoms
    res_caffeine = smiles_to_3d("CN1C=NC2=C1C(=O)N(C(=O)N2C)C")
    assert res_caffeine.num_atoms == 24
    assert res_caffeine.atomic_symbols.count("C") == 8
    assert res_caffeine.atomic_symbols.count("H") == 10
    assert res_caffeine.atomic_symbols.count("N") == 4
    assert res_caffeine.atomic_symbols.count("O") == 2

    # DMSO: C2H6OS -> 10 atoms
    res_dmso = smiles_to_3d("CS(=O)C")
    assert res_dmso.num_atoms == 10
    assert res_dmso.atomic_symbols.count("S") == 1
    assert res_dmso.atomic_symbols.count("H") == 6


def test_deterministic_embedding_and_reproducibility() -> None:
    """Verify ETKDGv3 seed=42 produces bitwise identical 3D coordinates (REQ-MOB-042)."""
    res1 = smiles_to_3d("CCO", random_seed=42)
    res2 = smiles_to_3d("CCO", random_seed=42)

    assert res1.num_atoms == res2.num_atoms == 9
    assert res1.energy_kcal_mol == pytest.approx(res2.energy_kcal_mol, rel=1e-7)
    assert res1.xyz_block == res2.xyz_block

    for c1, c2 in zip(res1.coordinates_3d, res2.coordinates_3d):
        assert c1[0] == pytest.approx(c2[0], abs=1e-6)
        assert c1[1] == pytest.approx(c2[1], abs=1e-6)
        assert c1[2] == pytest.approx(c2[2], abs=1e-6)


def test_stereocenter_preservation() -> None:
    """Verify enantiomeric stereochemistry integrity between L-Alanine and D-Alanine."""
    res_l = smiles_to_3d("C[C@@H](C(=O)O)N")
    res_d = smiles_to_3d("C[C@H](C(=O)O)N")

    assert res_l.num_atoms == 13
    assert res_d.num_atoms == 13
    # Chiral canonical SMILES must distinguish the enantiomers
    assert res_l.canonical_smiles != res_d.canonical_smiles
    assert "C[C@H](N)C(=O)O" in [res_l.canonical_smiles, res_d.canonical_smiles]
    assert "C[C@@H](N)C(=O)O" in [res_l.canonical_smiles, res_d.canonical_smiles]

    # Coordinates must be structurally distinct due to stereocenter inversion
    coords_l = np.array(res_l.coordinates_3d)
    coords_d = np.array(res_d.coordinates_3d)
    assert not np.allclose(coords_l, coords_d, atol=1e-3)


def test_single_atom_guard() -> None:
    """Verify single atom guard (N <= 1) sets origin coords, zero energy, and method NONE (REQ-MOB-043)."""
    single_atoms = ["[He]", "[Ne]", "[Ar]"]
    for smi in single_atoms:
        res = smiles_to_3d(smi)
        assert res.num_atoms == 1
        assert res.energy_kcal_mol == 0.0
        assert res.force_field_method == "NONE"
        assert res.converged is True
        assert res.coordinates_3d == [[0.0, 0.0, 0.0]]


def test_forcefield_hierarchy_mmff94s() -> None:
    """Verify standard organic molecules relax via MMFF94s forcefield (REQ-MOB-043)."""
    res = smiles_to_3d("CC(=O)Oc1ccccc1C(=O)O")  # Aspirin
    assert res.num_atoms == 21
    assert res.force_field_method == "MMFF94s"
    assert res.converged is True
    assert isinstance(res.energy_kcal_mol, float)


def test_forcefield_hierarchy_uff_fallback() -> None:
    """Verify molecules with unsupported MMFF94 elements fallback to UFF (REQ-MOB-043)."""
    res = smiles_to_3d("C[Ge](C)(C)C")  # Tetramethylgermane
    assert res.num_atoms == 17
    assert res.force_field_method == "UFF"
    assert res.converged is True
    assert "Ge" in res.atomic_symbols
    assert res.energy_kcal_mol != 0.0


def test_quantum_states_formal_charges() -> None:
    """Verify accurate formal charge calculations across neutral, anionic, and cationic species."""
    # Neutral: Ethanol (Q = 0)
    res_neutral = smiles_to_3d("CCO")
    assert res_neutral.formal_charge == 0

    # Anion: Acetate (Q = -1)
    res_anion = smiles_to_3d("CC(=O)[O-]")
    assert res_anion.formal_charge == -1

    # Cation: Ammonium (Q = +1)
    res_cation = smiles_to_3d("[NH4+]")
    assert res_cation.formal_charge == 1

    # Zwitterion: Glycine (Q = 0)
    res_zwitter = smiles_to_3d("C(C(=O)[O-])[NH3+]")
    assert res_zwitter.formal_charge == 0


def test_quantum_states_spin_multiplicity() -> None:
    """Verify ground-state spin multiplicity (2S + 1) calculation for closed and open-shell species."""
    # Closed shell singlet: Ethanol (2S + 1 = 1)
    res_singlet = smiles_to_3d("CCO")
    assert res_singlet.spin_multiplicity == 1

    # Radical doublet: Methyl radical [CH3] (2S + 1 = 2)
    res_doublet = smiles_to_3d("[CH3]")
    assert res_doublet.spin_multiplicity == 2

    # Radical doublet: Hydroxyl radical [OH] (2S + 1 = 2)
    res_oh = smiles_to_3d("[OH]")
    assert res_oh.spin_multiplicity == 2

    # Carbene triplet: [CH2] (2S + 1 = 3)
    res_triplet = smiles_to_3d("[CH2]")
    assert res_triplet.spin_multiplicity == 3


def test_standard_xyz_serialization_format(tmp_path: Path) -> None:
    """Verify strict 3-part XYZ schema with 8-decimal precision and LF line endings."""
    out_file = tmp_path / "ethanol_conformer.xyz"
    res = smiles_to_3d("CCO", output_path=out_file)

    assert out_file.exists()
    xyz_content = out_file.read_text(encoding="utf-8")
    assert xyz_content == res.xyz_block

    # Split into lines
    lines = xyz_content.splitlines()
    assert len(lines) == res.num_atoms + 2

    # Line 1: Atom count
    assert lines[0].strip() == str(res.num_atoms)

    # Line 2: Enriched comment header
    header = lines[1]
    assert "canonical_smiles=CCO" in header
    assert "energy_kcal_mol=" in header
    assert "method=MMFF94s" in header
    assert "converged=True" in header
    assert "charge=0" in header
    assert "multiplicity=1" in header

    # Atom lines: Check 8-decimal precision
    for line in lines[2:]:
        tokens = line.split()
        assert len(tokens) == 4
        sym, x_str, y_str, z_str = tokens
        assert sym in ["C", "O", "H"]
        # Verify 8 decimals after dot
        assert len(x_str.split(".")[1]) == 8
        assert len(y_str.split(".")[1]) == 8
        assert len(z_str.split(".")[1]) == 8


def test_mendeleev_dynamic_masses_integration() -> None:
    """Verify zero hardcoded masses; total mass is dynamically calculated via Mendeleev."""
    res = smiles_to_3d("CCO")  # C2H6O
    c_weight = float(mendeleev.element("C").atomic_weight)
    o_weight = float(mendeleev.element("O").atomic_weight)
    h_weight = float(mendeleev.element("H").atomic_weight)

    expected_mass = 2 * c_weight + 1 * o_weight + 6 * h_weight
    assert res.total_mass_amu == pytest.approx(expected_mass, rel=1e-5)

    # Test coordinate record property
    rec = AtomCoordinate3DRecord(atom_index=0, symbol="Fe", x=0.0, y=0.0, z=0.0)
    assert rec.atomic_weight == pytest.approx(float(mendeleev.element("Fe").atomic_weight), rel=1e-5)


def test_async_worker_isolation_and_concurrency() -> None:
    """Verify non-blocking async execution and concurrent batch execution across threads."""
    async def _runner() -> None:
        molecules = [
            "CCO",                                    # Ethanol
            "CC(=O)O",                               # Acetic acid
            "c1ccccc1",                              # Benzene
            "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",          # Caffeine
            "CC(=O)Oc1ccccc1C(=O)O",                 # Aspirin
            "CS(=O)C",                               # DMSO
            "C1CCCCC1",                              # Cyclohexane
            "C[C@@H](C(=O)O)N",                      # L-Alanine
        ]

        # 1. Test single smiles_to_3d_async
        single_res = await smiles_to_3d_async("CCO")
        assert single_res.num_atoms == 9
        assert single_res.canonical_smiles == "CCO"

        # 2. Test concurrent batch conversion via Smiles3DConformerEngine
        async with Smiles3DConformerEngine(max_workers=4) as engine:
            results = await engine.convert_batch_async(molecules)
            assert len(results) == len(molecules)
            for res, original_smi in zip(results, molecules):
                assert res.num_atoms > 0
                assert res.converged is True
                assert res.xyz_block.endswith("\n")

    asyncio.run(_runner())


def test_engine_lifecycle_and_shutdown() -> None:
    """Verify Smiles3DConformerEngine clean shutdown and exception on reuse."""
    with Smiles3DConformerEngine(max_workers=2) as engine:
        res = engine.convert("CCO")
        assert res.num_atoms == 9

    # After exiting context manager, engine is shut down
    with pytest.raises(RuntimeError, match="closed"):
        engine.convert("CCO")
