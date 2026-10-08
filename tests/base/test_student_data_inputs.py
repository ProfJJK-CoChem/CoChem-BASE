"""Original scientific ingress survives portable transport and rejects alteration."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest
from rdkit import Chem

from cochem_base.interfaces.student_data_inputs import build_data_bundle, extract_data_bundle
from cochem_base.interfaces.student_request import canonical_json, decode_transport_request
from cochem_base.intake.structure_formats import parse_structure_text
from scripts.run_student_research import _atomic_json, _bind_original_inputs, _run_free_native, finalize

ROOT = Path(__file__).resolve().parents[2]
WATER = (ROOT / "tests/data/orca_6_1_1_water_hf_sto3g/water.xyz").read_bytes()
REQUEST_ID = "df775dd7-56a0-4267-97d6-257453f2fe31"


def _geometry(record):
    return str(len(record["symbols"])) + "\nSelected retained physical record\n" + "".join(
        symbol + " " + " ".join(format(value, ".17g") for value in row) + "\n"
        for symbol, row in zip(record["symbols"], record["coords"], strict=True))


def _materialize(tmp_path, intake, geometry):
    digest = hashlib.sha256(geometry.encode()).hexdigest()
    contents, descriptor = build_data_bundle(intake, kind="molecular_ingestion", request_id=REQUEST_ID,
                                              geometry_sha256=digest)
    receipt = extract_data_bundle(contents, tmp_path / "data-inputs", request_id=REQUEST_ID,
                                  geometry_sha256=digest, kind="molecular_ingestion")
    _atomic_json(tmp_path / "data-inputs.json", receipt)
    request = {"calculation": {"engine": "xtb", "geometry": geometry, "charge": 0, "multiplicity": 1},
               "provider": None, "data_inputs": descriptor}
    return request, contents


def _mdl(isotope):
    retained = parse_structure_text(WATER.decode(), "xyz")[0]
    molecule = Chem.RWMol()
    for symbol in retained["elements"]:
        atom = Chem.Atom(symbol)
        if symbol == "O":
            atom.SetIsotope(isotope)
        molecule.AddAtom(atom)
    molecule.AddBond(0, 1, Chem.BondType.SINGLE)
    molecule.AddBond(0, 2, Chem.BondType.SINGLE)
    conformer = Chem.Conformer(3)
    conformer.Set3D(True)
    for index, row in enumerate(retained["coords"]):
        conformer.SetAtomPosition(index, tuple(row))
    molecule.AddConformer(conformer)
    return Chem.MolToMolBlock(molecule, forceV3000=True).encode()


def test_sdf_second_record_is_explicit_and_complete_original_is_retained(tmp_path):
    original = _mdl(18) + b"$$$$\n" + _mdl(16) + b"$$$$\n"
    records = parse_structure_text(original.decode(), "sdf")
    geometry = _geometry(records[1])
    request, _ = _materialize(tmp_path, {"filename": "student.sdf", "format": "sdf", "content": original,
                                        "record_index": 1}, geometry)
    _bind_original_inputs(request, tmp_path)
    receipt = json.loads((tmp_path / "original-ingestion-validation.json").read_text())
    assert receipt["record_count"] == 2 and receipt["selected_record_index"] == 1
    assert receipt["nuclides"][0] == "16O"
    assert receipt["all_original_records_retained"] is True
    assert (tmp_path / "data-inputs/source/original.sdf").read_bytes() == original
    assert receipt["scientific_execution_performed"] is False


def test_source_record_cannot_be_replaced_by_another_isotope(tmp_path):
    original = _mdl(18) + b"$$$$\n" + _mdl(16) + b"$$$$\n"
    records = parse_structure_text(original.decode(), "sdf")
    request, _ = _materialize(tmp_path, {"filename": "student.sdf", "format": "sdf", "content": original,
                                        "record_index": 1}, _geometry(records[0]))
    with pytest.raises(ValueError, match="derived calculation XYZ"):
        _bind_original_inputs(request, tmp_path)


def test_qcschema_encoded_electronic_state_cannot_be_overridden(tmp_path):
    from cochem_base.core.cochem_constants import BOHR_TO_ANGSTROM
    retained = parse_structure_text(WATER.decode(), "xyz")[0]
    raw = canonical_json({"schema_name": "qcschema_molecule", "schema_version": 2,
        "symbols": retained["elements"], "geometry": (retained["coords"] / BOHR_TO_ANGSTROM).ravel().tolist(),
        "molecular_charge": 1, "molecular_multiplicity": 2})
    record = parse_structure_text(raw.decode(), "qcschema")[0]
    request, _ = _materialize(tmp_path, {"filename": "student.json", "format": "qcschema", "content": raw,
                                        "record_index": 0}, _geometry(record))
    with pytest.raises(ValueError, match="electronic state"):
        _bind_original_inputs(request, tmp_path)


@pytest.mark.parametrize("identity", ["request_id", "geometry_sha256"])
def test_original_data_cannot_move_to_another_request_or_geometry(tmp_path, identity):
    digest = hashlib.sha256(WATER).hexdigest()
    contents, _ = build_data_bundle({"filename": "student.xyz", "format": "xyz", "content": WATER,
                                    "record_index": 0}, kind="molecular_ingestion", request_id=REQUEST_ID,
                                    geometry_sha256=digest)
    options = {"request_id": REQUEST_ID, "geometry_sha256": digest, "kind": "molecular_ingestion"}
    options[identity] = "changed"
    with pytest.raises(ValueError, match="manifest"):
        extract_data_bundle(contents, tmp_path / "results", **options)
    assert not (tmp_path / "results").exists()


def test_original_data_rejects_traversal_before_publishing_any_file(tmp_path):
    contents, _ = build_data_bundle({"filename": "student.xyz", "format": "xyz", "content": WATER,
                                    "record_index": 0}, kind="molecular_ingestion", request_id=REQUEST_ID,
                                    geometry_sha256=hashlib.sha256(WATER).hexdigest())
    altered = io.BytesIO(contents)
    with zipfile.ZipFile(altered, "a") as archive:
        archive.writestr("../escape.py", b"unexecuted hostile file")
    with pytest.raises(ValueError, match="traversal"):
        extract_data_bundle(altered.getvalue(), tmp_path / "results", request_id=REQUEST_ID,
                            geometry_sha256=hashlib.sha256(WATER).hexdigest(), kind="molecular_ingestion")
    assert not (tmp_path / "results").exists() and not (tmp_path / "escape.py").exists()


def test_stable_assignment_transport_preserves_future_science_without_materializing_it():
    import base64
    request = {"schema_version": "cochem.student-request/1", "request_id": REQUEST_ID,
        "repository": "ProfJJK-CoChem/CoChem-BASE", "source_sha": "a" * 40, "worker_source_sha": "b" * 40,
        "resources": {"cores": 2, "maxcore_mb": 512}, "future_scientific_payload": {"data": "bound to approved worker"}}
    raw = canonical_json(request)
    result = decode_transport_request(base64.b64encode(raw).decode(), hashlib.sha256(raw).hexdigest())
    assert result == request


def test_paw_file_bytes_cannot_claim_a_different_digest():
    source = (ROOT / "examples/product_b/gaas_fractional.json").read_bytes()
    with pytest.raises(ValueError, match="SHA-256"):
        build_data_bundle({"structure": {"filename": "student.json", "format": "json", "content": source},
            "pseudopotentials": {"Ga": {"filename": "Ga.UPF", "sha256": "0" * 64, "content": b"unaccepted bytes"}}},
            kind="periodic_inputs", request_id=REQUEST_ID, geometry_sha256=hashlib.sha256(WATER).hexdigest())


def test_real_native_process_crash_survives_sealed_scratch_cleanup(tmp_path):
    from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
    scratch = tmp_path / "native-scratch"
    scratch.mkdir()
    result = safe_subprocess_run([sys.executable, "-c",
        "import os; os.write(2, bytes(range(256))*2); os._exit(139)"],
        cwd=scratch, text=False, check=False, required_disk_gb=0)
    assert result.returncode == 139
    originals = list((scratch / "CrashRecords").glob("crash-*.json"))
    assert len(originals) == 1
    original = originals[0].read_bytes()
    _atomic_json(tmp_path / "student-result.json", {"status": "failed", "request_id": REQUEST_ID,
        "repository": "ProfJJK-CoChem/CoChem-BASE", "source_sha": "a" * 40,
        "worker_source_sha": "b" * 40, "payload_sha256": "c" * 64, "run_id": 1, "run_attempt": 1})
    publication = finalize(tmp_path)
    retained = list((tmp_path / "crash-provenance").glob("crash-*.json"))
    assert len(retained) == 1 and retained[0].read_bytes() == original
    assert retained[0].stat().st_mode & 0o222 == 0
    record = json.loads(original)
    assert record["stderr_tail_hex"] == bytes(range(256)).hex()
    assert not originals[0].exists()
    assert retained[0].relative_to(tmp_path).as_posix() in publication["files"]
    assert json.loads((tmp_path / "crash-provenance-receipt.json").read_bytes())["scientific_execution_claimed_from_crash"] is False


@pytest.mark.parametrize("kind", ["sdf_selected_isotope", "qcschema_encoded_charge"])
def test_original_selected_record_drives_real_pyscf_worker_and_retained_archive(tmp_path, kind):
    """Run genuine RHF with current Stage 0 authority; never substitute an engine."""
    import math
    from cochem_base.config_loader import resolve_config_path
    from cochem_base.core_engine.execution_authority import authorize_engine_execution
    registry = resolve_config_path()
    authorize_engine_execution("pyscf", registry_path=registry, cores=1, maxcore_mb=512)
    if kind == "sdf_selected_isotope":
        original = _mdl(18) + b"$$$$\n" + _mdl(16) + b"$$$$\n"
        intake = {"filename": "student.sdf", "format": "sdf", "content": original, "record_index": 1}
        charge = 0
    else:
        from cochem_base.core.cochem_constants import BOHR_TO_ANGSTROM
        original = canonical_json({"schema_name": "qcschema_molecule", "schema_version": 2,
            "symbols": ["He", "H"], "geometry": [0, 0, 0, 0, 0, .78 / BOHR_TO_ANGSTROM],
            "molecular_charge": 1, "molecular_multiplicity": 1})
        intake = {"filename": "student.json", "format": "qcschema", "content": original, "record_index": 0}
        charge = 1
    record = parse_structure_text(original.decode(), intake["format"])[intake["record_index"]]
    request, _ = _materialize(tmp_path, intake, _geometry(record))
    request["calculation"].update(engine="pyscf", method="HF", basis_set="STO-3G", charge=charge,
        multiplicity=1, is_opt=False, is_freq=False, is_vpt2=False, timeout_seconds=120.0)
    request["resources"] = {"cores": 1, "maxcore_mb": 512}
    (tmp_path / "inputs").mkdir()
    outcome = _run_free_native(request, tmp_path, registry)
    assert outcome["status"] == "EXECUTION_VERIFIED"
    accepted = json.loads((tmp_path / "native/result.json").read_bytes())
    assert accepted["scf_converged"] is True and math.isfinite(accepted["energy_hartree"])
    assert accepted["charge"] == charge and accepted["multiplicity"] == 1
    validation = json.loads((tmp_path / "original-ingestion-validation.json").read_bytes())
    assert validation["selected_record_index"] == intake["record_index"]
    assert validation["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert validation["all_original_records_retained"] is True
    portable_receipt = json.loads((tmp_path / "data-inputs/input-receipt.json").read_bytes())
    assert (tmp_path / "data-inputs" / portable_receipt["source"]["path"]).read_bytes() == original
    archive = json.loads((tmp_path / "telemetry-publication.json").read_bytes())
    assert archive["sha256"] == hashlib.sha256((tmp_path / "complexes.h5").read_bytes()).hexdigest()
    assert (tmp_path / "stage0-registry.json").read_bytes() == registry.read_bytes()
    from cochem_base.core_engine.scientific_telemetry import read_scientific_results
    telemetry = read_scientific_results(accepted["telemetry_job_id"], store_path=tmp_path / "complexes.h5")
    assert float(telemetry["energy_hartree"][-1]) == accepted["energy_hartree"]
    assert telemetry["coordinates_angstrom"][-1].tolist() == accepted["coordinates_angstrom"]
    assert telemetry["gradients_hartree_per_bohr"].shape[-2:] == (len(record["symbols"]), 3)
