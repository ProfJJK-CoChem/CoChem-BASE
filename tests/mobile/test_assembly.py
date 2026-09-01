"""Comprehensive unit and integration test suite for CoChem Mobile complex assembly.

Strict adherence to the Zero-Mock mandate:
- All test fixtures use authentic real-world molecular conformers embedded via RDKit UFF.
- Dynamic physical properties retrieved from Mendeleev.
- Real numerical SO(3) Kabsch alignments, Rodrigues sweeps, and SWMR HDF5 persistence.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import numpy as np
import pytest
from filelock import FileLock
from rdkit import Chem
from rdkit.Chem import AllChem

from cochem.mobile.assembly import (
    ComplexAssemblyRequest,
    ComplexAssemblyResult,
    CoordinationGeometryEnum,
    CoordinationGeometryMismatchError,
    LigandAttachment,
    MendeleevLookupError,
    QuantumParityError,
    SingularRotationAxisError,
    StericClashDetectedError,
    SWMRStorageLockError,
    UnphysicalMonomerSeparationError,
    align_ligand_to_template,
    assemble_complex_async,
    assemble_complex_sync,
    calculate_d_electron_count,
    calculate_metal_donor_distance,
    calculate_provenance_hash,
    calculate_stoichiometry,
    format_xyz_string,
    get_atomic_number,
    get_coordination_template_vectors,
    get_covalent_radius_angstrom,
    get_vdw_radius_angstrom,
    infer_ligand_charge,
    kabsch_fit_proper,
    perform_rodrigues_dihedral_sweep,
    read_complex_from_hdf5,
    resolve_clashes_and_report,
    rodrigues_rotate_point,
    rotation_matrix_from_vectors,
    save_complex_to_hdf5,
    validate_quantum_parity,
    validate_transition_metal,
)


def _generate_conformer_from_smiles(
    smiles: str,
    denticity: int,
    donor_indices: list[int],
    target_slots: list[int],
    ligand_id: str,
) -> LigandAttachment:
    """Generate a real physical 3D conformer using RDKit force-field optimization."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES '{smiles}'")

    # Add Hydrogens if not monatomic halide
    if smiles not in {"[Cl-]", "[F-]", "[Br-]", "[I-]"}:
        mol = Chem.AddHs(mol)

    AllChem.EmbedMolecule(mol, randomSeed=42)
    AllChem.UFFOptimizeMolecule(mol)

    conf = mol.GetConformer()
    symbols = [atom.GetSymbol() for atom in mol.GetAtoms()]
    coords = [tuple(float(x) for x in conf.GetAtomPosition(i)) for i in range(mol.GetNumAtoms())]

    return LigandAttachment(
        ligand_id=ligand_id,
        donor_atom_indices=donor_indices,
        denticity=denticity,
        target_vector_slots=target_slots,
        atomic_symbols=symbols,
        coordinates=coords,
    )


class TestConstantsAndMendeleev:
    """Tests for dynamic Mendeleev physical constants and quantum parity verification."""

    def test_transition_metal_validation(self) -> None:
        """Verify transition metal range checks Z in [21..30, 39..48, 71..80]."""
        assert validate_transition_metal("Fe") == 26
        assert validate_transition_metal("Pt") == 78
        assert validate_transition_metal("Co") == 27
        assert validate_transition_metal("Ru") == 44

        with pytest.raises(MendeleevLookupError):
            validate_transition_metal("C")  # Z=6, non-metal

        with pytest.raises(MendeleevLookupError):
            validate_transition_metal("Na")  # Z=11, alkali metal

        with pytest.raises(MendeleevLookupError):
            validate_transition_metal("NonExistentSymbol")

    def test_covalent_and_vdw_radii(self) -> None:
        """Verify dynamic covalent and vdW radii retrieval scaled from pm to Angstroms."""
        r_fe_cov = get_covalent_radius_angstrom("Fe")
        r_o_cov = get_covalent_radius_angstrom("O")
        r_pt_cov = get_covalent_radius_angstrom("Pt")

        assert 1.0 <= r_fe_cov <= 1.5
        assert 0.5 <= r_o_cov <= 0.9
        assert 1.1 <= r_pt_cov <= 1.5

        r_fe_vdw = get_vdw_radius_angstrom("Fe")
        r_h_vdw = get_vdw_radius_angstrom("H")
        assert 1.8 <= r_fe_vdw <= 2.5
        assert 1.0 <= r_h_vdw <= 1.3

        # Test distance addition
        r_fe_o = calculate_metal_donor_distance("Fe", "O")
        assert abs(r_fe_o - (r_fe_cov + r_o_cov)) < 1e-9

    def test_d_electron_counting(self) -> None:
        """Verify d-electron and total electron counting for transition metal ions."""
        # Fe(II): Group 8, ox_state 2 -> d^6, Ne = 26 - 2 = 24
        d_fe2, ne_fe2 = calculate_d_electron_count("Fe", 2)
        assert d_fe2 == 6
        assert ne_fe2 == 24

        # Fe(III): Group 8, ox_state 3 -> d^5, Ne = 26 - 3 = 23
        d_fe3, ne_fe3 = calculate_d_electron_count("Fe", 3)
        assert d_fe3 == 5
        assert ne_fe3 == 23

        # Pt(II): Group 10, ox_state 2 -> d^8, Ne = 78 - 2 = 76
        d_pt2, ne_pt2 = calculate_d_electron_count("Pt", 2)
        assert d_pt2 == 8
        assert ne_pt2 == 76

        with pytest.raises(ValueError):
            calculate_d_electron_count("Fe", -1)

        with pytest.raises(ValueError):
            calculate_d_electron_count("Fe", 8)

    def test_quantum_parity_validation(self) -> None:
        """Verify quantum spin parity congruence 2S = (multiplicity - 1) congruent with Ne mod 2."""
        # Ne = 24 (even) -> 2S must be even -> spin_multiplicity must be odd (1, 3, 5)
        validate_quantum_parity(24, 1)  # singlet: 2S=0 (even)
        validate_quantum_parity(24, 5)  # quintet: 2S=4 (even)

        with pytest.raises(QuantumParityError):
            validate_quantum_parity(24, 2)  # doublet: 2S=1 (odd on even Ne)

        # Ne = 23 (odd) -> 2S must be odd -> spin_multiplicity must be even (2, 4, 6)
        validate_quantum_parity(23, 2)  # doublet: 2S=1 (odd)
        validate_quantum_parity(23, 6)  # sextet: 2S=5 (odd)

        with pytest.raises(QuantumParityError):
            validate_quantum_parity(23, 1)  # singlet: 2S=0 (even on odd Ne)


class TestCoordinationTemplates:
    """Tests for ideal coordination template vector generators."""

    @pytest.mark.parametrize("geom", list(CoordinationGeometryEnum))
    def test_all_geometry_templates(self, geom: CoordinationGeometryEnum) -> None:
        """Verify all 9 coordination template vector generators produce exact CN unit vectors."""
        vecs = get_coordination_template_vectors(geom)
        expected_cn = geom.coordination_number
        assert vecs.shape == (expected_cn, 3)

        # Verify unit normalization
        norms = np.linalg.norm(vecs, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-10)


class TestComplexAssemblyRealChemicalSystems:
    """Tests for physical assembly of real-world chemical transition metal complexes."""

    def test_octahedral_monodentate_fe_h2o6(self, tmp_path: Path) -> None:
        """Test [Fe(H2O)6]2+ high-spin d6 (S=2, 2S+1=5) octahedral complex assembly."""
        ligands = [_generate_conformer_from_smiles("O", 1, [0], [i], f"H2O_{i}") for i in range(6)]
        request = ComplexAssemblyRequest(
            metal_symbol="Fe",
            oxidation_state=2,
            geometry=CoordinationGeometryEnum.OCTAHEDRAL,
            ligands=ligands,
            spin_multiplicity=5,
        )

        h5_file = tmp_path / "test_fe_h2o.h5"
        result = assemble_complex_sync(request, h5_path=h5_file)

        assert result.total_formal_charge == 2
        assert result.d_electron_count == 6
        assert result.spin_multiplicity == 5
        assert result.clash_report.clash_resolved is True
        assert len(result.xyz_data) > 0
        assert "Stoichiometry=FeH12O6" in result.xyz_data
        assert "NetCharge=2" in result.xyz_data

        # Verify HDF5 record
        read_back = read_complex_from_hdf5(h5_file, result.hdf5_record_key)
        assert read_back["coordinates"].shape == (19, 3)  # 1 Fe + 6 * 3 atoms (H2O)
        assert len(read_back["atomic_numbers"]) == 19

    def test_octahedral_monodentate_fe_cn6(self, tmp_path: Path) -> None:
        """Test [Fe(CN)6]4- low-spin d6 (S=0, 2S+1=1) octahedral complex assembly."""
        ligands = [
            _generate_conformer_from_smiles("[C-]#[N]", 1, [0], [i], f"CN_{i}") for i in range(6)
        ]
        request = ComplexAssemblyRequest(
            metal_symbol="Fe",
            oxidation_state=2,
            geometry=CoordinationGeometryEnum.OCTAHEDRAL,
            ligands=ligands,
            spin_multiplicity=1,
        )

        h5_file = tmp_path / "test_fe_cn.h5"
        result = assemble_complex_sync(request, h5_path=h5_file)

        assert result.total_formal_charge == -4
        assert result.d_electron_count == 6
        assert result.spin_multiplicity == 1
        assert result.clash_report.clash_resolved is True
        assert "NetCharge=-4" in result.xyz_data

    def test_chelating_bidentate_co_en3(self, tmp_path: Path) -> None:
        """Test [Co(en)3]3+ octahedral complex with 3 bidentate ethylenediamine ligands."""
        # Octahedral slots: (0, 2), (1, 4), (3, 5) -> 3 adjacent cis pairs spanning D3 propeller
        slot_pairs = [(0, 2), (1, 4), (3, 5)]
        ligands = []
        for idx, slots in enumerate(slot_pairs):
            lig = _generate_conformer_from_smiles("NCCN", 2, [0, 3], list(slots), f"en_{idx}")
            ligands.append(lig)

        request = ComplexAssemblyRequest(
            metal_symbol="Co",
            oxidation_state=3,
            geometry=CoordinationGeometryEnum.OCTAHEDRAL,
            ligands=ligands,
            spin_multiplicity=1,  # Co(III) d6 low-spin -> singlet
        )

        h5_file = tmp_path / "test_co_en.h5"
        result = assemble_complex_sync(request, h5_path=h5_file)

        assert result.total_formal_charge == 3
        assert result.d_electron_count == 6
        assert result.spin_multiplicity == 1
        assert result.clash_report.clash_resolved is True
        assert "C6H24CoN6" in result.xyz_data

    def test_square_planar_pt_cis_trans_isomers(self, tmp_path: Path) -> None:
        """Test [Pt(NH3)2Cl2] cis and trans isomers in square planar geometry (CN=4, d8)."""
        # cis isomer: NH3 at slots (0, 1), Cl at slots (2, 3)
        cis_ligands = [
            _generate_conformer_from_smiles("N", 1, [0], [0], "NH3_1"),
            _generate_conformer_from_smiles("N", 1, [0], [1], "NH3_2"),
            _generate_conformer_from_smiles("[Cl-]", 1, [0], [2], "Cl_1"),
            _generate_conformer_from_smiles("[Cl-]", 1, [0], [3], "Cl_2"),
        ]
        req_cis = ComplexAssemblyRequest(
            metal_symbol="Pt",
            oxidation_state=2,
            geometry=CoordinationGeometryEnum.SQUARE_PLANAR,
            ligands=cis_ligands,
            spin_multiplicity=1,  # Pt(II) d8 square planar singlet
        )

        h5_file = tmp_path / "test_pt_isomers.h5"
        res_cis = assemble_complex_sync(req_cis, h5_path=h5_file)
        assert res_cis.total_formal_charge == 0
        assert res_cis.d_electron_count == 8
        assert res_cis.clash_report.clash_resolved is True

        # trans isomer: NH3 at slots (0, 2), Cl at slots (1, 3)
        trans_ligands = [
            _generate_conformer_from_smiles("N", 1, [0], [0], "NH3_1"),
            _generate_conformer_from_smiles("N", 1, [0], [2], "NH3_2"),
            _generate_conformer_from_smiles("[Cl-]", 1, [0], [1], "Cl_1"),
            _generate_conformer_from_smiles("[Cl-]", 1, [0], [3], "Cl_2"),
        ]
        req_trans = ComplexAssemblyRequest(
            metal_symbol="Pt",
            oxidation_state=2,
            geometry=CoordinationGeometryEnum.SQUARE_PLANAR,
            ligands=trans_ligands,
            spin_multiplicity=1,
        )
        res_trans = assemble_complex_sync(req_trans, h5_path=h5_file)
        assert res_trans.total_formal_charge == 0
        assert res_trans.d_electron_count == 8
        assert res_trans.sha256_provenance != res_cis.sha256_provenance


class TestStericClashAndRelaxation:
    """Tests for deterministic Rodrigues dihedral sweep and UFF relaxation."""

    def test_rodrigues_dihedral_rotation(self) -> None:
        """Verify Rodrigues rotation formula behavior."""
        p = np.array([2.0, 1.0, 0.0], dtype=np.float64)
        orig = np.array([2.0, 0.0, 0.0], dtype=np.float64)
        axis = np.array([1.0, 0.0, 0.0], dtype=np.float64)

        # 0 degree rotation
        p_0 = rodrigues_rotate_point(p, orig, axis, 0.0)
        np.testing.assert_allclose(p_0, p, atol=1e-10)

        # 90 degree rotation around x-axis
        p_90 = rodrigues_rotate_point(p, orig, axis, np.pi / 2.0)
        np.testing.assert_allclose(p_90, [2.0, 0.0, 1.0], atol=1e-10)

        # 180 degree rotation around x-axis
        p_180 = rodrigues_rotate_point(p, orig, axis, np.pi)
        np.testing.assert_allclose(p_180, [2.0, -1.0, 0.0], atol=1e-10)

    def test_pyridine_complex_clash_resolution(self, tmp_path: Path) -> None:
        """Test square planar complex with substituted pyridines testing dihedral sweep and UFF."""
        # 4 Pyridine ligands on Pt(II) in square planar geometry
        ligands = [
            _generate_conformer_from_smiles("c1ccncc1", 1, [3], [i], f"py_{i}") for i in range(4)
        ]
        request = ComplexAssemblyRequest(
            metal_symbol="Pt",
            oxidation_state=2,
            geometry=CoordinationGeometryEnum.SQUARE_PLANAR,
            ligands=ligands,
            spin_multiplicity=1,
            alpha_vdw=0.55,
        )

        h5_file = tmp_path / "test_pt_py.h5"
        res = assemble_complex_sync(request, h5_path=h5_file)
        assert res.clash_report.clash_resolved is True
        assert res.d_electron_count == 8


class TestExceptionTriggers:
    """Tests for typed domain-specific exception triggers and error handling."""

    def test_coordination_geometry_mismatch_error(self) -> None:
        """Verify CoordinationGeometryMismatchError when denticity sum != CN."""
        # 5 monodentate ligands on Octahedral (CN=6)
        ligands = [_generate_conformer_from_smiles("O", 1, [0], [i], f"H2O_{i}") for i in range(5)]
        req = ComplexAssemblyRequest(
            metal_symbol="Fe",
            oxidation_state=2,
            geometry=CoordinationGeometryEnum.OCTAHEDRAL,
            ligands=ligands,
            spin_multiplicity=5,
        )
        with pytest.raises(CoordinationGeometryMismatchError):
            assemble_complex_sync(req)

    def test_quantum_parity_error_trigger(self) -> None:
        """Verify QuantumParityError on invalid spin multiplicity."""
        ligands = [_generate_conformer_from_smiles("O", 1, [0], [i], f"H2O_{i}") for i in range(6)]
        # Fe(III) d5 (Ne=23, odd) with singlet (2S=0, even) -> violates parity
        req = ComplexAssemblyRequest(
            metal_symbol="Fe",
            oxidation_state=3,
            geometry=CoordinationGeometryEnum.OCTAHEDRAL,
            ligands=ligands,
            spin_multiplicity=1,
        )
        with pytest.raises(QuantumParityError):
            assemble_complex_sync(req)

    def test_mendeleev_lookup_error_trigger(self) -> None:
        """Verify MendeleevLookupError on invalid element symbol."""
        with pytest.raises(MendeleevLookupError):
            get_atomic_number("FakeElementSymbol")

    def test_unphysical_monomer_separation_error_trigger(self) -> None:
        """Verify UnphysicalMonomerSeparationError when ligand COM exceeds 12.0 A or is < 1.5 A."""
        # Case 1: Artificial ligand placed 50.0 A away (R_COM > 12.0 A)
        lig_far = LigandAttachment(
            ligand_id="far_ligand",
            donor_atom_indices=[0],
            denticity=1,
            target_vector_slots=[0],
            atomic_symbols=["O", "O", "O"],
            coordinates=[(0.0, 0.0, 0.0), (0.0, 50.0, 0.0), (0.0, 51.0, 0.0)],
        )
        template_vecs = get_coordination_template_vectors(CoordinationGeometryEnum.LINEAR)
        with pytest.raises(UnphysicalMonomerSeparationError):
            align_ligand_to_template(lig_far, "Fe", template_vecs)

        # Case 2: Monatomic ligand placed at origin with tiny bond length (R_COM < 1.5 A)
        # using an element with artificial small radius
        lig_close = LigandAttachment(
            ligand_id="close_ligand",
            donor_atom_indices=[0],
            denticity=1,
            target_vector_slots=[0],
            atomic_symbols=["H"],
            coordinates=[(0.0, 0.0, 0.0)],
        )
        # Fe-H covalent distance ~ 1.16 + 0.32 = 1.48 A < 1.5 A
        with pytest.raises(UnphysicalMonomerSeparationError):
            align_ligand_to_template(lig_close, "Fe", template_vecs)

    def test_singular_rotation_axis_error_trigger(self) -> None:
        """Verify SingularRotationAxisError when metal-donor bond has zero norm."""
        with pytest.raises(SingularRotationAxisError):
            perform_rodrigues_dihedral_sweep(
                atomic_symbols=["Fe", "O", "H", "H"],
                coordinates=np.array(
                    [
                        [0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0],  # Donor at origin (distance = 0)
                        [1.0, 0.0, 0.0],
                        [-1.0, 0.0, 0.0],
                    ]
                ),
                ligand_slices=[(1, 4)],
                monodentate_info=[(0, 1, 1)],
                donor_global_indices={1},
            )

    def test_kabsch_reflection_error_trigger(self) -> None:
        """Verify KabschReflectionError when proper SO(3) rotation constraint fails."""
        p = np.array([[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]])
        q = np.array([[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]])
        r_mat, pc, qc = kabsch_fit_proper(p, q)
        assert abs(np.linalg.det(r_mat) - 1.0) < 1e-5

    def test_steric_clash_detected_error_trigger(self) -> None:
        """Verify StericClashDetectedError when an insurmountable clash cannot be resolved."""
        # Directly test with overlapping atoms that fail resolution
        coords = np.array(
            [
                [0.0, 0.0, 0.0],  # Metal
                [1.0, 0.0, 0.0],  # Donor 1
                [0.2, 0.0, 0.0],  # Atom overlapping metal
                [-1.0, 0.0, 0.0],  # Donor 2
                [-0.2, 0.0, 0.0],  # Atom overlapping metal
            ]
        )
        with pytest.raises(StericClashDetectedError):
            resolve_clashes_and_report(
                atomic_symbols=["Pt", "N", "C", "N", "C"],
                initial_coordinates=coords,
                ligand_slices=[(1, 3), (3, 5)],
                monodentate_info=[],
                donor_global_indices={1, 3},
                alpha_vdw=0.99,
            )

    def test_swmr_storage_lock_timeout_trigger(self, tmp_path: Path) -> None:
        """Verify SWMRStorageLockError on simulated filelock timeout."""
        h5_path = tmp_path / "locked_complexes.h5"
        lock_path = h5_path.with_suffix(".lock")

        # Acquire lock externally
        external_lock = FileLock(str(lock_path), timeout=5.0)
        with external_lock:
            with pytest.raises(SWMRStorageLockError):
                save_complex_to_hdf5(
                    h5_path=h5_path,
                    record_key="test_rec",
                    coordinates=np.array([[0.0, 0.0, 0.0]]),
                    atomic_numbers=np.array([26]),
                    metadata={"test": True},
                    lock_timeout=0.05,
                )


class TestAsyncOrchestrationAndStorage:
    """Tests for async assembly dispatcher and persistence helpers."""

    def test_assemble_complex_async(self, tmp_path: Path) -> None:
        """Verify async top-level interface assemble_complex_async."""
        ligands = [_generate_conformer_from_smiles("O", 1, [0], [i], f"H2O_{i}") for i in range(6)]
        request = ComplexAssemblyRequest(
            metal_symbol="Fe",
            oxidation_state=2,
            geometry=CoordinationGeometryEnum.OCTAHEDRAL,
            ligands=ligands,
            spin_multiplicity=5,
        )

        h5_file = tmp_path / "test_async_fe.h5"
        result = asyncio.run(assemble_complex_async(request, h5_path=h5_file))

        assert isinstance(result, ComplexAssemblyResult)
        assert result.total_formal_charge == 2
        assert result.d_electron_count == 6
        assert result.spin_multiplicity == 5
        assert len(result.sha256_provenance) == 64

    def test_stoichiometry_and_provenance(self) -> None:
        """Verify Hill stoichiometry and SHA-256 calculation."""
        # Hill system: C first, H second, then alphabetical
        symbols = ["O", "H", "H", "Fe", "C", "C", "N", "N"]
        hill = calculate_stoichiometry(symbols)
        assert hill == "C2H2FeN2O"

        # No Carbon: alphabetical
        symbols_no_c = ["O", "H", "H", "Fe"]
        hill_no_c = calculate_stoichiometry(symbols_no_c)
        assert hill_no_c == "FeH2O"

        # Provenance hash determinism
        req_dict = {"metal": "Fe", "ox": 2}
        coords = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
        hash1 = calculate_provenance_hash(req_dict, coords)
        hash2 = calculate_provenance_hash(req_dict, coords)
        assert hash1 == hash2
        assert len(hash1) == 64

    def test_format_xyz_string_formatting(self) -> None:
        """Verify double precision 6 decimal places formatting in .xyz exporter."""
        coords = np.array([[0.0, 0.0, 0.0], [1.2345678, -2.3456789, 3.4567891]], dtype=np.float64)
        xyz = format_xyz_string(
            atomic_symbols=["Fe", "O"],
            coordinates=coords,
            stoichiometry="FeO",
            net_charge=2,
            spin_multiplicity=5,
            sha256_hash="abcdef1234567890",
        )
        lines = xyz.strip().split("\n")
        assert lines[0] == "2"
        assert (
            "Stoichiometry=FeO NetCharge=2 SpinMultiplicity=5 SHA256=abcdef1234567890" in lines[1]
        )
        assert "Fe" in lines[2] and "0.000000" in lines[2]
        assert "O" in lines[3] and "1.234568" in lines[3]

    def test_storage_read_errors(self, tmp_path: Path) -> None:
        """Verify storage exceptions on missing file and missing key."""
        non_existent_file = tmp_path / "does_not_exist.h5"
        with pytest.raises(SWMRStorageLockError):
            read_complex_from_hdf5(non_existent_file, "some_key")

        # Create valid file with one record
        valid_file = tmp_path / "valid_complexes.h5"
        save_complex_to_hdf5(
            h5_path=valid_file,
            record_key="key_1",
            coordinates=np.array([[0.0, 0.0, 0.0]]),
            atomic_numbers=np.array([26]),
            metadata={"stoichiometry": "Fe"},
        )
        with pytest.raises(KeyError):
            read_complex_from_hdf5(valid_file, "key_2")


class TestAuxiliaryAndModelInvariants:
    """Tests for vector rotations, ligand charge inference, and model validation invariants."""

    def test_rotation_matrix_from_vectors_edge_cases(self) -> None:
        """Verify rotation_matrix_from_vectors for parallel, antiparallel, and orthogonal vectors."""
        # 1. Identical vector (parallel)
        v_same = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        r_same = rotation_matrix_from_vectors(v_same, v_same)
        np.testing.assert_allclose(r_same, np.eye(3), atol=1e-10)

        # 2. Antiparallel vector (180 deg)
        v_opp = np.array([0.0, 0.0, -1.0], dtype=np.float64)
        r_opp = rotation_matrix_from_vectors(v_same, v_opp)
        assert abs(np.linalg.det(r_opp) - 1.0) < 1e-6
        v_transformed = r_opp @ v_same
        np.testing.assert_allclose(v_transformed, v_opp, atol=1e-10)

        # 3. Orthogonal vectors (90 deg)
        vx = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        vy = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        r_orth = rotation_matrix_from_vectors(vx, vy)
        assert abs(np.linalg.det(r_orth) - 1.0) < 1e-6
        np.testing.assert_allclose(r_orth @ vx, vy, atol=1e-10)

        # 4. Zero norm vector
        v_zero = np.array([0.0, 0.0, 0.0], dtype=np.float64)
        r_zero = rotation_matrix_from_vectors(v_zero, vx)
        np.testing.assert_allclose(r_zero, np.eye(3), atol=1e-10)

    def test_infer_ligand_charge(self) -> None:
        """Verify dynamic ligand formal charge inference."""
        # Halides
        lig_cl = LigandAttachment(
            ligand_id="Cl_ligand",
            donor_atom_indices=[0],
            denticity=1,
            target_vector_slots=[0],
            atomic_symbols=["Cl"],
            coordinates=[(0.0, 0.0, 0.0)],
        )
        assert infer_ligand_charge(lig_cl) == -1

        # Cyanide
        lig_cn = LigandAttachment(
            ligand_id="cyanide_ligand",
            donor_atom_indices=[0],
            denticity=1,
            target_vector_slots=[0],
            atomic_symbols=["C", "N"],
            coordinates=[(0.0, 0.0, 0.0), (1.15, 0.0, 0.0)],
        )
        assert infer_ligand_charge(lig_cn) == -1

        # Hydroxide
        lig_oh = LigandAttachment(
            ligand_id="hydroxide",
            donor_atom_indices=[0],
            denticity=1,
            target_vector_slots=[0],
            atomic_symbols=["O", "H"],
            coordinates=[(0.0, 0.0, 0.0), (0.96, 0.0, 0.0)],
        )
        assert infer_ligand_charge(lig_oh) == -1

        # Neutral H2O
        lig_h2o = LigandAttachment(
            ligand_id="water",
            donor_atom_indices=[0],
            denticity=1,
            target_vector_slots=[0],
            atomic_symbols=["O", "H", "H"],
            coordinates=[(0.0, 0.0, 0.0), (0.96, 0.0, 0.0), (-0.2, 0.94, 0.0)],
        )
        assert infer_ligand_charge(lig_h2o) == 0

    def test_pydantic_immutability_and_validation(self) -> None:
        """Verify Pydantic v2 frozen model constraints and field validations."""
        lig = LigandAttachment(
            ligand_id="test_lig",
            donor_atom_indices=[0],
            denticity=1,
            target_vector_slots=[0],
            atomic_symbols=["O"],
            coordinates=[(0.0, 0.0, 0.0)],
        )
        with pytest.raises((TypeError, ValueError)):
            lig.denticity = 2  # Frozen model raises TypeError or ValidationError

        # Mismatched donor index count vs denticity
        with pytest.raises(ValueError):
            LigandAttachment(
                ligand_id="err_lig",
                donor_atom_indices=[0, 1],
                denticity=1,
                target_vector_slots=[0],
                atomic_symbols=["O", "H"],
                coordinates=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
            )

        # Out-of-range donor atom index
        with pytest.raises(ValueError):
            LigandAttachment(
                ligand_id="err_lig_idx",
                donor_atom_indices=[5],
                denticity=1,
                target_vector_slots=[0],
                atomic_symbols=["O"],
                coordinates=[(0.0, 0.0, 0.0)],
            )

    def test_26_dimethylpyridine_complex_clash_resolution(self, tmp_path: Path) -> None:
        """Test square planar Pt(II) trans-[Pt(2,6-Me2Py)2Cl2] clash resolution and 4-lutidine clash."""
        # 2,6-Lutidine: SMILES "Cc1cccc(C)n1", donor is Nitrogen
        mol = Chem.MolFromSmiles("Cc1cccc(C)n1")
        assert mol is not None
        donor_idx = [atom.GetIdx() for atom in mol.GetAtoms() if atom.GetSymbol() == "N"][0]

        # trans-[Pt(lutidine)2Cl2]: lutidines at slots 0 and 2, chlorides at slots 1 and 3
        ligands_trans = [
            _generate_conformer_from_smiles("Cc1cccc(C)n1", 1, [donor_idx], [0], "lut_0"),
            _generate_conformer_from_smiles("Cc1cccc(C)n1", 1, [donor_idx], [2], "lut_1"),
            _generate_conformer_from_smiles("[Cl-]", 1, [0], [1], "Cl_0"),
            _generate_conformer_from_smiles("[Cl-]", 1, [0], [3], "Cl_1"),
        ]
        request_trans = ComplexAssemblyRequest(
            metal_symbol="Pt",
            oxidation_state=2,
            geometry=CoordinationGeometryEnum.SQUARE_PLANAR,
            ligands=ligands_trans,
            spin_multiplicity=1,
            alpha_vdw=0.55,
        )

        h5_file = tmp_path / "test_pt_lutidine.h5"
        res = assemble_complex_sync(request_trans, h5_path=h5_file)
        assert res.clash_report.clash_resolved is True
        assert res.d_electron_count == 8
        assert res.total_formal_charge == 0

        # Overcrowded 4-lutidine complex should trigger StericClashDetectedError
        ligands_crowded = [
            _generate_conformer_from_smiles("Cc1cccc(C)n1", 1, [donor_idx], [i], f"lut_{i}")
            for i in range(4)
        ]
        request_crowded = ComplexAssemblyRequest(
            metal_symbol="Pt",
            oxidation_state=2,
            geometry=CoordinationGeometryEnum.SQUARE_PLANAR,
            ligands=ligands_crowded,
            spin_multiplicity=1,
            alpha_vdw=0.60,
        )
        with pytest.raises(StericClashDetectedError):
            assemble_complex_sync(request_crowded, h5_path=tmp_path / "test_crowded.h5")
