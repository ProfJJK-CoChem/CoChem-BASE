"""Lossless molecular format boundaries for the Task 1 ingestion specification.

Original bytes belong to the intake receipt. These readers produce ordered
Cartesian records without adding hydrogens, embedding coordinates, optimizing,
or silently choosing an alternate PDB location. Molecular units follow each
format: XYZ/MDL/Tripos/PDB are Angstrom; MolSSI QCSchema is Bohr.
"""
from __future__ import annotations

import io
import json
import math
import re
from dataclasses import asdict
from typing import Any

import numpy as np

from cochem_base.core.cochem_constants import BOHR_TO_ANGSTROM
from cochem_base.geometry.nuclide_geometry import resolve_nuclear_identity

FORMATS = frozenset({"xyz", "mol", "sdf", "mol2", "pdb", "json", "qcschema"})
MAX_RECORDS = 512


def _record(labels: list[str], coordinates: Any, *, comment: str = "", **metadata: Any) -> dict:
    from cochem_base.validators.preflight import validate_ingestion_toolchain
    toolchain = validate_ingestion_toolchain()
    if not labels or len(labels) > 4096:
        raise ValueError("A molecular intake record must contain between 1 and 4096 centers")
    from cochem_base.physics.isotopes import is_ghost_atom, normalize_nuclide_symbol
    ghost_indices = [index for index, label in enumerate(labels) if is_ghost_atom(label)]
    real_labels = [label for index, label in enumerate(labels) if index not in ghost_indices]
    if not real_labels:
        raise ValueError("Molecular input requires at least one real nucleus")
    identity = resolve_nuclear_identity(real_labels)
    elements, nuclides, numbers, masses = [], [], [], []
    real_index = 0
    for index in range(len(labels)):
        if index in ghost_indices:
            elements.append("Gh")
            nuclides.append(normalize_nuclide_symbol(labels[index]).canonical_symbol)
            numbers.append(None)
            masses.append(0.0)
        else:
            elements.append(identity.elements[real_index])
            nuclides.append(identity.nuclides[real_index])
            numbers.append(identity.mass_numbers[real_index])
            masses.append(identity.masses_u[real_index])
            real_index += 1
    coords = np.asarray(coordinates, dtype=np.float64)
    if coords.shape != (len(labels), 3) or not np.isfinite(coords).all():
        raise ValueError("Molecular input requires complete finite ordered Cartesian coordinates")
    # The SRS limit is the physical pair distance, not one Cartesian axis or
    # a bounding-box diagonal. A rotated structure must get the same decision.
    for index in range(len(coords)):
        if np.any(np.linalg.norm(coords[index + 1:] - coords[index], axis=1) > 1000.0):
            raise ValueError("Molecular coordinate diameter exceeds the ingestion limit")
    real_coords = np.asarray([coords[index] for index in range(len(labels)) if index not in ghost_indices])
    for index in range(len(real_coords)):
        if np.any(np.linalg.norm(real_coords[index + 1:] - real_coords[index], axis=1) < 0.4):
            raise ValueError("Molecular input contains overlapping nuclei closer than 0.40 Angstrom")
    nuclear = dict(identity.metadata, nuclides=nuclides, mass_numbers=numbers, masses_u=masses)
    from cochem_base.intake import get_element_data
    properties = [get_element_data(label) for label in nuclides]
    principal_masses = [value["monoisotopic_mass"] for value in properties]
    charge, multiplicity = metadata.get("charge"), metadata.get("multiplicity")
    if charge is not None:
        if type(charge) is not int:
            raise ValueError("Encoded molecular charge must be an integer")
        electrons = sum(value["atomic_number"] for value in properties) - charge
        if electrons < 0:
            raise ValueError("Encoded charge exceeds the total nuclear charge")
        if multiplicity is not None and (type(multiplicity) is not int or multiplicity < 1
                or multiplicity > electrons + 1 or electrons % 2 == multiplicity % 2):
            raise ValueError("Encoded multiplicity is inconsistent with the molecular electron count")
    return {"comment": comment, "symbols": nuclides, "elements": elements, "nuclear_identity": nuclear,
            "coords": coords, "num_atoms": len(labels), "coordinates_unit": "angstrom",
            "coordinates_angstroms": coords.tolist(),
            "canonical_symbols": elements, "atomic_numbers": [value["atomic_number"] for value in properties],
            "mass_numbers": numbers, "resolved_mass_numbers": [value["mass_number"] for value in properties],
            "atomic_masses_daltons": principal_masses, "total_mass_daltons": math.fsum(principal_masses),
            "mass_convention": "explicit_isotope_else_most_abundant_isotope_dynamic_mendeleev",
            "ingestion_toolchain": asdict(toolchain),
            "covalent_radii_angstroms": [value["covalent_radius"] for value in properties],
            "vdw_radii_angstroms": [value["vdw_radius"] for value in properties],
            "ghost_indices": ghost_indices, "requires_counterpoise_adapter": bool(ghost_indices), **metadata}


def _rdkit_record(molecule: Any, *, record_index: int) -> dict:
    if molecule is None or molecule.GetNumAtoms() < 1 or molecule.GetNumConformers() != 1:
        raise ValueError(f"Molecular record {record_index + 1} is invalid or lacks Cartesian coordinates")
    labels = [f"{a.GetIsotope()}{a.GetSymbol()}" if a.GetIsotope() else a.GetSymbol()
              for a in molecule.GetAtoms()]
    conformer = molecule.GetConformer()
    coordinates = [[float(conformer.GetAtomPosition(i)[axis]) for axis in range(3)]
                   for i in range(len(labels))]
    charge = sum(a.GetFormalCharge() for a in molecule.GetAtoms())
    radicals = [a.GetNumRadicalElectrons() for a in molecule.GetAtoms()]
    props = molecule.GetPropsAsDict(includePrivate=False, includeComputed=False)
    multiplicity = None
    declared = [v for k, v in props.items() if k.lower() in {"multiplicity", "spin_multiplicity", "molecular_multiplicity"}]
    if declared:
        if any(not re.fullmatch(r"[1-9][0-9]*", str(v).strip()) for v in declared) or len({int(v) for v in declared}) != 1:
            raise ValueError("SDF multiplicity declarations are invalid or contradictory")
        multiplicity = int(declared[0])
    # Radical atom flags do not specify coupling of several open-shell centers.
    # Never turn their sum into an invented molecular spin multiplicity.
    return _record(labels, coordinates,
                   comment=molecule.GetProp("_Name") if molecule.HasProp("_Name") else "",
                   record_index=record_index, charge=charge, multiplicity=multiplicity,
                   atom_formal_charges=[a.GetFormalCharge() for a in molecule.GetAtoms()],
                   atom_radical_electrons=radicals,
                   bonds=[[b.GetBeginAtomIdx(), b.GetEndAtomIdx(), b.GetBondTypeAsDouble()] for b in molecule.GetBonds()],
                   properties=props, electronic_state_source="file_formal_charges_and_optional_spin_property")


def parse_mdl_text(text: str) -> list[dict]:
    """Read every V2000/V3000 MOL/SDF record with strict real RDKit parsing."""
    from rdkit import Chem

    if not text.strip() or "M  END" not in text:
        raise ValueError("MOL/SDF input is empty or lacks its molecular table terminator")
    supplier = Chem.ForwardSDMolSupplier(io.BytesIO(text.removeprefix("\ufeff").encode("utf-8")),
                                         sanitize=True, removeHs=False, strictParsing=True)
    records = []
    for index, molecule in enumerate(supplier):
        if index >= MAX_RECORDS:
            raise ValueError("MOL/SDF exceeds the bounded molecular record count")
        records.append(_rdkit_record(molecule, record_index=index))
    if not records:
        raise ValueError("MOL/SDF input contains no complete molecular records")
    return records


def parse_mol2_text(text: str) -> list[dict]:
    """Read Tripos molecules without conflating partial and formal charges."""
    from rdkit import Chem

    starts = list(re.finditer(r"(?m)^@<TRIPOS>MOLECULE\s*$", text))
    if not starts or text[:starts[0].start()].strip():
        raise ValueError("MOL2 requires an explicit Tripos molecule section")
    if len(starts) > MAX_RECORDS:
        raise ValueError("MOL2 exceeds the bounded molecular record count")
    records = []
    for index, start in enumerate(starts):
        block = text[start.start():starts[index + 1].start() if index + 1 < len(starts) else len(text)]
        molecule = Chem.MolFromMol2Block(block, sanitize=True, removeHs=False, cleanupSubstructures=False)
        record = _rdkit_record(molecule, record_index=index)
        charges = [float(a.GetProp("_TriposPartialCharge")) if a.HasProp("_TriposPartialCharge") else None
                   for a in molecule.GetAtoms()]
        if any(value is not None and not math.isfinite(value) for value in charges):
            raise ValueError("MOL2 partial charges must be finite")
        record.update(partial_charges=charges, charge=None, multiplicity=None,
                      electronic_state_source="Tripos_partial_charges_do_not_define_molecular_state")
        records.append(record)
    return records


def parse_pdb_text(text: str) -> list[dict]:
    """Read PDB 3.3 fixed columns and every model; reject unresolved disorder."""
    records, atoms, identifiers = [], [], set()
    model_id = None
    explicit_model = False
    uses_model_blocks = any(line[:6].strip() == "MODEL" for line in text.removeprefix("\ufeff").splitlines())

    def finish() -> None:
        nonlocal atoms, identifiers
        if not atoms:
            raise ValueError("PDB model contains no ATOM/HETATM coordinates")
        if len(records) >= MAX_RECORDS:
            raise ValueError("PDB exceeds the bounded molecular record count")
        records.append(_record([a[0] for a in atoms], [a[1] for a in atoms], comment=f"PDB model {model_id or 1}",
                               record_index=len(records), model_id=model_id or 1,
                               atom_identifiers=[a[2] for a in atoms], atom_formal_charges=[a[3] for a in atoms],
                               charge=sum(a[3] for a in atoms), multiplicity=None,
                               electronic_state_source="PDB_atom_charge_columns_spin_unprovided"))
        atoms, identifiers = [], set()

    for line in text.removeprefix("\ufeff").splitlines():
        tag = line[:6].strip()
        if tag == "MODEL":
            if atoms or explicit_model:
                raise ValueError("PDB MODEL records must be properly nested with ENDMDL")
            model_id, explicit_model = int(line[10:14].strip()), True
        elif tag == "ENDMDL":
            if not explicit_model:
                raise ValueError("PDB ENDMDL has no matching MODEL")
            finish()
            model_id, explicit_model = None, False
        elif tag in {"ATOM", "HETATM"}:
            if uses_model_blocks and not explicit_model:
                raise ValueError("PDB ATOM/HETATM records must be inside MODEL/ENDMDL blocks when explicit models are present")
            if len(line) < 78 or line[16:17].strip():
                raise ValueError("PDB requires element columns and resolved alternate locations")
            occupancy = line[54:60].strip()
            if occupancy and (not math.isfinite(float(occupancy)) or float(occupancy) != 1.0):
                raise ValueError("PDB partial occupancy must be resolved before molecular ingestion")
            label = line[76:78].strip()
            if not label:
                raise ValueError("PDB requires an explicit element; atom names cannot substitute for elements")
            identifier = [int(line[6:11]), line[12:16].strip(), line[17:20].strip(), line[21:22], line[22:27].strip()]
            if identifier[0] in identifiers:
                raise ValueError("PDB atom serials must be unique within each model")
            identifiers.add(identifier[0])
            charge_token = line[78:80].strip()
            if charge_token and re.fullmatch(r"[1-9][+-]", charge_token) is None:
                raise ValueError("Invalid PDB atom formal-charge field")
            charge = 0 if not charge_token else int(charge_token[0]) * (1 if charge_token[1] == "+" else -1)
            atoms.append((label, [float(line[30:38]), float(line[38:46]), float(line[46:54])], identifier, charge))
    if explicit_model:
        raise ValueError("PDB MODEL is missing its ENDMDL terminator")
    if atoms:
        finish()
    if not records:
        raise ValueError("PDB contains no molecular coordinates")
    return records


def parse_qcschema_text(text: str) -> list[dict]:
    """Validate MolSSI v1/v2 molecules without unit or atom-order guessing."""
    import qcelemental as qcel
    from cochem_base.physics.nuclide_resolver import get_element

    def pairs(items: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("QCSchema contains duplicate JSON keys")
            result[key] = value
        return result

    data = json.loads(text.removeprefix("\ufeff"), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite QCSchema value: " + value)))
    if (not isinstance(data, dict) or type(data.get("schema_version")) is not int
            or data["schema_version"] not in {1, 2}
            or data.get("schema_name") not in {"qcschema_molecule", "qcschema_input", "qcschema_output", "qc_schema_input", "qc_schema_output"}):
        raise ValueError("QCSchema requires an explicit supported schema version")
    molecule = data.get("molecule", data)
    if not isinstance(molecule, dict) or not {"symbols", "geometry"}.issubset(molecule):
        raise ValueError("QCSchema requires its molecular symbols and Bohr geometry")
    if molecule is not data:
        if "schema_name" in molecule and molecule["schema_name"] != "qcschema_molecule":
            raise ValueError("Nested QCSchema molecule requires a supported molecule schema name")
        if "schema_version" in molecule and (type(molecule["schema_version"]) is not int or molecule["schema_version"] not in {1, 2}):
            raise ValueError("Nested QCSchema molecule requires a supported schema version")
    units = molecule.get("units", "bohr")
    if not isinstance(units, str) or units.lower() not in {"bohr", "au", "a.u."}:
        raise ValueError("QCSchema geometry is defined in Bohr; explicit incompatible units are rejected")
    check = dict(molecule, schema_name="qcschema_molecule", schema_version=2,
                 fix_com=True, fix_orientation=True)
    # molparse always validates physical data; a user-provided validated=True
    # must never bypass its checks. It also rejects a fragment-induced reorder.
    try:
        qcel.molparse.from_schema(check, verbose=0)
    except qcel.exceptions.ValidationError as error:
        raise ValueError(f"QCSchema physical validation failed: {error}") from error
    symbols = molecule["symbols"]
    if not isinstance(symbols, list) or any(not isinstance(s, str) for s in symbols):
        raise ValueError("QCSchema symbols must be an ordered array")
    numbers = molecule.get("mass_numbers")
    masses = molecule.get("masses")
    if numbers is not None and (len(numbers) != len(symbols) or any(type(v) is not int or v < 1 for v in numbers)):
        raise ValueError("QCSchema isotope mass numbers must be positive ordered integers")
    labels = []
    for index, symbol in enumerate(symbols):
        number = numbers[index] if numbers is not None else None
        if masses is not None:
            if len(masses) != len(symbols) or isinstance(masses[index], bool) or not math.isfinite(float(masses[index])):
                raise ValueError("QCSchema masses require complete finite physical values")
            matching = [iso for iso in get_element(symbol).isotopes if iso.mass is not None
                        and abs(float(iso.mass) - float(masses[index])) <= 1e-6]
            if len(matching) != 1 or number is not None and int(matching[0].mass_number) != number:
                raise ValueError("QCSchema masses must match the dynamically resolved physical isotope")
            number = int(matching[0].mass_number)
        labels.append(f"{number}{symbol}" if number is not None else symbol)
    real = molecule.get("real", [True] * len(symbols))
    if not isinstance(real, list) or len(real) != len(symbols) or any(type(value) is not bool for value in real):
        raise ValueError("QCSchema real-center flags must match the ordered atom count")
    basis_labels = list(labels)
    labels = [label if real[index] else "Gh" for index, label in enumerate(labels)]
    geometry = np.asarray(molecule["geometry"], dtype=np.float64)
    if geometry.size != len(symbols) * 3:
        raise ValueError("QCSchema geometry must contain exactly three values per atom")
    charge = molecule.get("molecular_charge", 0)
    if isinstance(charge, bool) or not isinstance(charge, (int, float)) or not math.isfinite(charge) or int(charge) != charge:
        raise ValueError("Molecular quantum calculations require an integer charge")
    multiplicity = molecule.get("molecular_multiplicity", 1)
    if type(multiplicity) is not int or multiplicity < 1:
        raise ValueError("QCSchema multiplicity must be a positive integer")
    return [_record(labels, geometry.reshape((-1, 3)) * BOHR_TO_ANGSTROM,
                    comment=str(molecule.get("name", molecule.get("comment", "QCSchema molecule"))),
                    record_index=0, charge=int(charge), multiplicity=multiplicity,
                    source_coordinates_unit="bohr", schema_name=data.get("schema_name"),
                    schema_version=data["schema_version"], fragments=molecule.get("fragments", []),
                    basis_center_nuclides=basis_labels, real_centers=real,
                    fragment_charges=molecule.get("fragment_charges", []),
                    fragment_multiplicities=molecule.get("fragment_multiplicities", []),
                    electronic_state_source="QCSchema_molecular_charge_and_multiplicity")]


def parse_structure_text(text: str, format: str) -> list[dict]:
    """Dispatch only the formats required by the Task 1 ingestion architecture."""
    name = format.lower().lstrip(".")
    if name == "xyz":
        return parse_xyz_records(text)
    readers = {"mol": parse_mdl_text, "sdf": parse_mdl_text, "mol2": parse_mol2_text,
               "pdb": parse_pdb_text, "json": parse_qcschema_text, "qcschema": parse_qcschema_text}
    if name not in readers:
        raise ValueError("Unsupported molecular structure format: " + name)
    return readers[name](text)


def parse_xyz_records(text: str) -> list[dict]:
    """Read complete counted frames, including inspected counterpoise centers."""
    lines = text.removeprefix("\ufeff").splitlines()
    records, index = [], 0
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        count = int(lines[index].strip())
        stop = index + count + 2
        if count < 1 or count > 4096 or stop > len(lines):
            raise ValueError("XYZ frame has an invalid atom count or is truncated")
        if len(records) >= MAX_RECORDS:
            raise ValueError("XYZ exceeds the bounded molecular record count")
        fields = [line.split() for line in lines[index + 2:stop]]
        if any(len(row) != 4 for row in fields):
            raise ValueError("XYZ requires exactly one label and three coordinates per atom")
        records.append(_record([row[0] for row in fields], [[float(v) for v in row[1:]] for row in fields],
                               comment=lines[index + 1], record_index=len(records)))
        index = stop
    if not records:
        raise ValueError("XYZ contains no complete frames")
    return records
