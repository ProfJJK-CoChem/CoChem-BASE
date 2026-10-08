"""Task 1 §3.1.2 full-format intake against retained physical water coordinates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from rdkit import Chem

from cochem_base.core.cochem_constants import BOHR_TO_ANGSTROM
from cochem_base.intake import ingest_file, ingest_records, scan_batch_directory
from cochem_base.intake.cochem_stage2_ingestor import Stage2Ingestor
from cochem_base.intake.structure_formats import parse_structure_text
from cochem_base.physics.isotopes import get_isotope_mass

WATER = Path(__file__).parents[1] / "data/orca_6_1_1_water_hf_sto3g/water.xyz"


def _water() -> tuple[list[str], np.ndarray]:
    record = parse_structure_text(WATER.read_text(), "xyz")[0]
    return record["elements"], record["coords"]


def _mdl(*, v3000: bool, oxygen_isotope: int = 18) -> str:
    # Serialize the genuine retained ORCA geometry. No coordinate generation or
    # test engine substitutes are involved in this format conversion.
    symbols, coords = _water()
    molecule = Chem.RWMol()
    for index, symbol in enumerate(symbols):
        atom = Chem.Atom(symbol)
        if symbol == "O":
            atom.SetIsotope(oxygen_isotope)
        molecule.AddAtom(atom)
    molecule.AddBond(0, 1, Chem.BondType.SINGLE)
    molecule.AddBond(0, 2, Chem.BondType.SINGLE)
    conformer = Chem.Conformer(len(symbols))
    conformer.Set3D(True)
    for index, row in enumerate(coords):
        conformer.SetAtomPosition(index, tuple(row))
    molecule.AddConformer(conformer)
    molecule.SetProp("_Name", "Retained actual ORCA water")
    return Chem.MolToMolBlock(molecule, forceV3000=v3000)


@pytest.mark.parametrize("v3000", [False, True])
def test_mdl_preserves_all_sdf_records_isotopes_geometry_and_bytes(tmp_path, v3000):
    source = tmp_path / "isotopes.sdf"
    raw = (_mdl(v3000=v3000) + "$$$$\n" + _mdl(v3000=v3000, oxygen_isotope=16) + "$$$$\n").encode()
    source.write_bytes(raw)
    parsed = Stage2Ingestor().process_file(source)
    assert len(parsed) == 2
    assert [r["symbols"][0] for r in parsed] == ["18O", "16O"]
    assert [r["source_sha256"] for r in parsed] == [hashlib.sha256(raw).hexdigest()] * 2
    assert [r["record_index"] for r in parsed] == [0, 1]
    assert source.read_bytes() == raw
    np.testing.assert_allclose(parsed[0]["coords"], _water()[1], atol=0.000051)
    payloads = ingest_records(source)
    assert len(payloads) == 2
    assert payloads[0].M_aux[0] == get_isotope_mass("O", 18)
    assert payloads[0].nuclides[0] == "18O"
    assert payloads[0].multiplicity is None
    with pytest.raises(ValueError, match="multiple records"):
        ingest_file(source)


def test_mdl_invalid_second_record_rejects_whole_input():
    text = _mdl(v3000=True) + "$$$$\nBroken molecule\nM  END\n$$$$\n"
    with pytest.raises(ValueError, match="record 2"):
        parse_structure_text(text, "sdf")


def _pdb() -> str:
    symbols, coords = _water()
    lines = []
    for index, (symbol, row) in enumerate(zip(symbols, coords, strict=True), 1):
        x, y, z = row
        lines.append(f"HETATM{index:5d} {symbol + str(index):>4s} HOH A   1    {x:8.3f}{y:8.3f}{z:8.3f}{1.:6.2f}{0.:6.2f}          {symbol:>2s}  ")
    return "\n".join(lines) + "\n"


def test_pdb_all_models_atom_order_and_explicit_elements():
    text = "MODEL        1\n" + _pdb() + "ENDMDL\nMODEL        2\n" + _pdb() + "ENDMDL\n"
    records = parse_structure_text(text, "pdb")
    assert len(records) == 2
    assert [r["model_id"] for r in records] == [1, 2]
    assert records[0]["elements"] == _water()[0]
    np.testing.assert_allclose(records[0]["coords"], _water()[1], atol=0.000501)


@pytest.mark.parametrize("defect", ["alternate", "occupancy", "missing_element", "unterminated"])
def test_pdb_rejects_ambiguous_or_incomplete_structure(defect):
    lines = _pdb().splitlines()
    if defect == "alternate":
        lines[0] = lines[0][:16] + "A" + lines[0][17:]
    elif defect == "occupancy":
        lines[0] = lines[0][:54] + "  0.50" + lines[0][60:]
    elif defect == "missing_element":
        lines[0] = lines[0][:76] + "    "
    text = "\n".join(lines)
    if defect == "unterminated":
        text = "MODEL        1\n" + text
    with pytest.raises(ValueError):
        parse_structure_text(text, "pdb")


def test_mol2_tripostypes_partial_charge_and_all_records():
    _, coords = _water()
    atoms = "\n".join(f"{i+1} {('O','H','H')[i]} {r[0]:.12g} {r[1]:.12g} {r[2]:.12g} {('O.3','H','H')[i]} 1 HOH {(-0.8,0.4,0.4)[i]}" for i,r in enumerate(coords))
    block = "@<TRIPOS>MOLECULE\nActual ORCA water\n3 2 1 0 0\nSMALL\nUSER_CHARGES\n@<TRIPOS>ATOM\n" + atoms + "\n@<TRIPOS>BOND\n1 1 2 1\n2 1 3 1\n@<TRIPOS>SUBSTRUCTURE\n1 HOH 1\n"
    records = parse_structure_text(block + block, "mol2")
    assert len(records) == 2
    assert records[0]["partial_charges"] == [-0.8, 0.4, 0.4]
    assert records[0]["charge"] is None
    assert records[0]["multiplicity"] is None
    np.testing.assert_allclose(records[0]["coords"], coords, atol=1e-11)


def _schema(version=2):
    symbols, coordinates = _water()
    molecule = {"symbols": symbols, "geometry": (coordinates / BOHR_TO_ANGSTROM).ravel().tolist(),
                "molecular_charge": 0, "molecular_multiplicity": 1, "mass_numbers": [18, 2, 2]}
    return dict(molecule, schema_name="qcschema_molecule", schema_version=2) if version == 2 else {
        "schema_name": "qcschema_input", "schema_version": 1, "molecule": molecule}


@pytest.mark.parametrize("version", [1, 2])
def test_qcschema_units_isotopes_state_and_order(version):
    record = parse_structure_text(json.dumps(_schema(version)), "qcschema")[0]
    assert record["symbols"] == ["18O", "2H", "2H"]
    assert record["source_coordinates_unit"] == "bohr"
    assert record["charge"] == 0 and record["multiplicity"] == 1
    np.testing.assert_allclose(record["coords"], _water()[1], atol=1e-14)


@pytest.mark.parametrize("defect", ["units", "shape", "nonfinite", "mass", "schema", "parity"])
def test_qcschema_physical_and_schema_validation_cannot_be_bypassed(defect):
    data = _schema()
    data["validated"] = True
    if defect == "units":
        data["units"] = "angstrom"
    elif defect == "shape":
        data["geometry"].append(0.0)
    elif defect == "nonfinite":
        data["geometry"][0] = float("nan")
    elif defect == "mass":
        data["masses"] = [get_isotope_mass("O", 16), get_isotope_mass("H", 2), get_isotope_mass("H", 2)]
    elif defect == "schema":
        data["schema_name"] = "unreviewed_format"
    elif defect == "parity":
        data["molecular_multiplicity"] = 2
    with pytest.raises((ValueError, KeyError)):
        parse_structure_text(json.dumps(data), "qcschema")


def test_strict_source_encoding_and_bom_hash(tmp_path):
    path = tmp_path / "water.xyz"
    raw = b"\xef\xbb\xbf" + WATER.read_bytes()
    path.write_bytes(raw)
    assert Stage2Ingestor().process_file(path)[0]["source_sha256"] == hashlib.sha256(raw).hexdigest()
    path.write_bytes(raw + b"\xff")
    with pytest.raises(UnicodeDecodeError):
        Stage2Ingestor().process_file(path)


def test_batch_retains_record_counts_duplicates_and_failures(tmp_path):
    raw = (_mdl(v3000=True) + "$$$$\n" + _mdl(v3000=False) + "$$$$\n").encode()
    (tmp_path / "a.sdf").write_bytes(raw)
    (tmp_path / "b.sdf").write_bytes(raw)
    (tmp_path / "invalid.xyz").write_text("not an XYZ molecule")
    summary = scan_batch_directory(tmp_path)
    assert summary.total_files_scanned == 3
    assert summary.successful_files == 2
    assert summary.successful_ingestions == 2
    assert summary.duplicate_files == 1
    assert summary.failed_ingestions == 1
    assert set(summary.errors) == {"invalid.xyz"}
    assert len(summary.payloads) == 2
    assert len(summary.sha256_registry) == 1
    with pytest.raises(ValueError, match="invalid.xyz"):
        Stage2Ingestor().process_directory(tmp_path)


def test_counterpoise_ghost_centers_are_zero_mass_and_explicitly_gated(tmp_path):
    text = WATER.read_text()
    lines = text.splitlines()
    lines[0] = str(int(lines[0]) + 1)
    text = "\n".join(lines) + "\nGh 5 0 0\n"
    path = tmp_path / "counterpoise.xyz"
    path.write_text(text)
    record = Stage2Ingestor().process_file(path)[0]
    assert record["requires_counterpoise_adapter"] is True
    assert record["ghost_indices"] == [3]
    payload = ingest_file(path)
    assert payload.M_aux[-1] == 0.0 and payload.Z_aux[-1] == 0


def test_ingestion_model_metadata_and_true_diagonal_diameter():
    source = parse_structure_text(WATER.read_text(), "xyz")[0]
    assert source["canonical_symbols"] == ["O", "H", "H"]
    assert source["atomic_numbers"] == [8, 1, 1]
    assert source["resolved_mass_numbers"] == [16, 1, 1]
    assert source["atomic_masses_daltons"] == [get_isotope_mass("O", 16), get_isotope_mass("H", 1), get_isotope_mass("H", 1)]
    assert source["total_mass_daltons"] == sum(source["atomic_masses_daltons"])
    assert all(value > 0 for value in source["covalent_radii_angstroms"])
    # Deliberately invalid input for the physical diameter gate; no scientific
    # results are inferred from these malformed coordinates.
    with pytest.raises(ValueError, match="diameter"):
        parse_structure_text("2\nInvalid diagonal span\nH 0 0 0\nH 800 800 0\n", "xyz")


def test_declared_sdf_spin_must_match_actual_electron_count():
    text = _mdl(v3000=True) + "> <MULTIPLICITY>\n2\n\n$$$$\n"
    with pytest.raises(ValueError, match="electron count"):
        parse_structure_text(text, "sdf")
    valid = text.replace("> <MULTIPLICITY>\n2", "> <MULTIPLICITY>\n1")
    record = parse_structure_text(valid, "sdf")[0]
    assert record["multiplicity"] == 1 and record["charge"] == 0


def test_qcschema_retains_ghost_basis_identity_separate_from_zero_mass_centers():
    # An H nucleus with a ghost H basis center is a doublet. QCSchema encodes
    # the ghost with real=False, while retaining its element for basis loading.
    source = {"schema_name": "qcschema_molecule", "schema_version": 2,
              "symbols": ["H", "H"], "geometry": [0., 0., 0., 0., 0., 3.],
              "real": [True, False], "molecular_charge": 0, "molecular_multiplicity": 2}
    record = parse_structure_text(json.dumps(source), "qcschema")[0]
    assert record["basis_center_nuclides"] == ["H", "H"]
    assert record["symbols"] == ["H", "Gh"]
    assert record["atomic_numbers"] == [1, 0]
    assert record["atomic_masses_daltons"][1] == 0.0
    assert record["requires_counterpoise_adapter"] is True


def test_multi_record_bounds_reject_whole_xyz_pool_before_acceptance():
    with pytest.raises(ValueError, match="record count"):
        parse_structure_text(WATER.read_text() * 513, "xyz")
