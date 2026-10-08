"""Scientific input transport boundaries and covariant tensor mathematics.

The R2 byte fixtures deliberately contain no quantum output or measured energy;
they test file linkage and cannot pass the native reference validator. The
Hessian fixture is an explicitly mathematical two-point spring, not a claimed
engine calculation. Physical warm-start acceptance runs the real ORCA engine.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import stat
import zipfile

import numpy as np
import pytest

from cochem_base.interfaces.scientific_inputs import (
    MANIFEST_NAME, MAX_FILE_BYTES, build_bundle, extract_bundle,
    ingest_scientific_upload, transform_read_hessian, verify_bundle,
)
from cochem_base.interfaces.student_request import canonical_json


REQUEST_ID = "42e6cf49-1228-47fd-a87d-459ba4a13988"
XYZ = "2\nMathematical transport geometry; no calculated energy\nH 1 2 3\nH 2 4 6\n"
GEOMETRY_SHA = hashlib.sha256(XYZ.encode()).hexdigest()


def identity(kind="read_hessian", entrypoint="initial.hess"):
    return {"request_id": REQUEST_ID, "geometry_sha256": GEOMETRY_SHA,
            "kind": kind, "entrypoint": entrypoint}


def zip_bytes(files, mode=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        entries = files.items() if isinstance(files, dict) else files
        for name, raw in entries:
            info = zipfile.ZipInfo(name)
            if mode is not None:
                info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    return buffer.getvalue()


def r2_inputs(*, absolute=False, nested=False):
    files = {"monomer.xyz": b"2\nTransport input only\nH 0 0 0\nH 0 0 .74\n",
             "lower.out": b"Retained lower-cardinal file bytes; not a quantum calculation\n",
             "upper.out": b"Retained upper-cardinal file bytes; not a quantum calculation\n"}

    def source(name):
        return {"path": ("/previous/native/job/" if absolute else "") + name,
                "sha256": hashlib.sha256(files[name]).hexdigest()}

    monomers = []
    for indices in ([0, 1], [2, 3]):
        item = {"atom_indices": indices, "charge": 0, "multiplicity": 1,
                "method": "CCSD(T)/CBS", "basis_cardinal_pair": [3, 4],
                "basis_family": "cc-pVXZ", "source_uri": "urn:cochem:transport-only",
                "geometry": source("monomer.xyz"), "lower_cardinal_output": source("lower.out"),
                "upper_cardinal_output": source("upper.out")}
        if nested:
            points = {basis: {"output_path": source(name)["path"], "output_sha256": source(name)["sha256"]}
                      for basis, name in (("cc-pVTZ", "lower.out"), ("cc-pVQZ", "upper.out"))}
            files["minimum-evidence.json"] = canonical_json({
                "schema_version": "cochem.bounded-cbs-reference/1",
                "evaluations": [{"basis_results": points}],
                "scope": "Transport linkage only; no minimum or energy assertion"})
            item["geometry_optimization_evidence"] = source("minimum-evidence.json")
        monomers.append(item)
    files["r2-reference.json"] = canonical_json({"schema_version": "cochem.r2-reference/1", "monomers": monomers})
    return files


def test_sealed_input_is_exactly_request_and_geometry_bound_before_extraction(tmp_path):
    original = b"Opaque initializer bytes for integrity testing only\n"
    raw, descriptor = build_bundle({"initial.hess": original}, **identity())
    assert descriptor["bundle_sha256"] == hashlib.sha256(raw).hexdigest()
    assert descriptor["bundle_size_bytes"] == len(raw)
    verified = extract_bundle(raw, tmp_path / "extracted", **identity())
    assert verified["entrypoint_path"].read_bytes() == original
    assert verified["entrypoint_path"].stat().st_mode & 0o222 == 0
    assert verified["scientific_validation_performed"] is False
    assert verified["manifest"]["files"]["initial.hess"]["sha256"] == hashlib.sha256(original).hexdigest()


@pytest.mark.parametrize("field,value", [
    ("request_id", "e94d2a66-c51f-41bd-8f8d-34cb5c28bbac"),
    ("geometry_sha256", "a" * 64), ("entrypoint", "another.hess"), ("kind", "r2_reference")])
def test_other_request_geometry_entrypoint_or_kind_never_creates_destination(tmp_path, field, value):
    raw, _ = build_bundle({"initial.hess": b"Retained input bytes"}, **identity())
    wrong = {**identity(), field: value}
    with pytest.raises(ValueError, match="different"):
        extract_bundle(raw, tmp_path / "rejected", **wrong)
    assert not (tmp_path / "rejected").exists()


@pytest.mark.parametrize("name", ["../escape.hess", "/absolute.hess", "inputs\\escape.hess",
                                "C:escape.hess", "inputs/CON.hess", "initial.hess/child.hess",
                                "inputs/quoted\".hess", "inputs/unknown?.hess"])
def test_unsafe_input_names_and_file_parent_conflicts_rejected(name):
    with pytest.raises(ValueError):
        build_bundle({"initial.hess": b"Original", name: b"Second"}, **identity())


def test_case_colliding_inputs_rejected_on_windows_and_linux():
    with pytest.raises(ValueError, match="collide"):
        build_bundle({"initial.hess": b"Original", "INITIAL.HESS": b"Second"}, **identity())


@pytest.mark.parametrize("name,raw", [("analysis.py", b"print('data must not execute')"),
                                    ("initial.hess", b"\x7fELFbinary"), ("initial.hess", b"MZbinary")])
def test_executable_inputs_cannot_be_sealed(name, raw):
    with pytest.raises(ValueError):
        build_bundle({name: raw}, **identity())


def test_oversized_input_rejected_before_bundle_creation():
    with pytest.raises(ValueError, match="16 MiB"):
        build_bundle({"initial.hess": b"x" * (MAX_FILE_BYTES + 1)}, **identity())


def test_tampered_sealed_bytes_cannot_be_extracted(tmp_path):
    raw, _ = build_bundle({"initial.hess": b"Original"}, **identity())
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    entries["initial.hess"] = b"Changed"
    with pytest.raises(ValueError, match="sealed inventory"):
        extract_bundle(zip_bytes(entries), tmp_path / "tampered", **identity())
    assert not (tmp_path / "tampered").exists()


@pytest.mark.parametrize("entries,mode", [
    ([("initial.hess", b"one"), ("initial.hess", b"two")], None),
    ({"../outside.hess": b"unsafe"}, None),
    ({"initial.hess": b"target"}, stat.S_IFLNK | 0o777),
    ({"initial.hess": b"device"}, stat.S_IFCHR | 0o600)])
def test_hostile_zip_structure_rejected_before_creating_files(tmp_path, entries, mode):
    with pytest.raises(ValueError):
        extract_bundle(zip_bytes(entries, mode), tmp_path / "rejected", **identity())
    assert not (tmp_path / "rejected").exists()


def test_noncanonical_duplicate_manifest_fields_are_rejected(tmp_path):
    raw, _ = build_bundle({"initial.hess": b"Original"}, **identity())
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    entries[MANIFEST_NAME] = entries[MANIFEST_NAME][:-1] + b',"kind":"read_hessian"}'
    with pytest.raises(ValueError, match="Duplicate"):
        verify_bundle(zip_bytes(entries), **identity())


def test_real_files_are_not_overwritten_and_symlink_parent_is_rejected(tmp_path):
    raw, _ = build_bundle({"initial.hess": b"Original"}, **identity())
    existing = tmp_path / "owned"
    existing.mkdir()
    note = existing / "student-notes.txt"
    note.write_bytes(b"Preserve this research")
    with pytest.raises(ValueError, match="new owned"):
        extract_bundle(raw, existing, **identity())
    assert note.read_bytes() == b"Preserve this research"
    link = tmp_path / "link"
    link.symlink_to(existing, target_is_directory=True)
    with pytest.raises(ValueError, match="nonsymlink"):
        extract_bundle(raw, link / "new", **identity())
    assert not (existing / "new").exists()


def test_r2_nested_path_normalization_retains_all_original_bytes_without_quantum_claim(tmp_path):
    original = r2_inputs(absolute=True, nested=True)
    intake = ingest_scientific_upload("r2_reference", zip_bytes(original), "student-reference.zip",
                                       geometry_xyz=XYZ, destination=tmp_path / "intake")
    assert intake["scientific_validation_performed"] is False
    assert all(intake["files"][name] == raw for name, raw in original.items())
    transformed = json.loads(intake["files"][intake["entrypoint"]])
    for item in transformed["monomers"]:
        assert item["geometry"]["path"] == "monomer.xyz"
        minimum = item["geometry_optimization_evidence"]
        evidence = json.loads(intake["files"][minimum["path"]])
        assert evidence["evaluations"][0]["basis_results"]["cc-pVTZ"]["output_path"] == "lower.out"
        assert minimum["sha256"] == hashlib.sha256(intake["files"][minimum["path"]]).hexdigest()
    receipt = json.loads(intake["files"]["scientific-input-normalization.json"])
    assert receipt["original_manifest"]["sha256"] == hashlib.sha256(original["r2-reference.json"]).hexdigest()
    raw, _ = build_bundle(intake["files"], **identity("r2_reference", intake["entrypoint"]))
    verified = verify_bundle(raw, **identity("r2_reference", intake["entrypoint"]))
    assert verified["files"]["lower.out"] == original["lower.out"]
    from cochem_base.calc.recipe_r2_execution import validate_reference_output, R2ReferenceError
    with pytest.raises(R2ReferenceError):
        validate_reference_output(tmp_path / "intake/lower.out", "cc-pVTZ")


@pytest.mark.parametrize("missing", ["monomer.xyz", "lower.out", "upper.out", "minimum-evidence.json"])
def test_missing_authentic_r2_dependency_never_creates_intake_directory(tmp_path, missing):
    files = r2_inputs(absolute=True, nested=True)
    files.pop(missing)
    with pytest.raises(ValueError, match="raw source"):
        ingest_scientific_upload("r2_reference", zip_bytes(files), "reference.zip",
                                  geometry_xyz=XYZ, destination=tmp_path / "rejected")
    assert not (tmp_path / "rejected").exists()


def test_missing_nested_r2_output_cannot_hide_behind_complete_top_level_references(tmp_path):
    files = r2_inputs(nested=True)
    evidence = json.loads(files["minimum-evidence.json"])
    evidence["evaluations"][0]["basis_results"]["cc-pVQZ"]["output_sha256"] = "1" * 64
    files["minimum-evidence.json"] = canonical_json(evidence)
    manifest = json.loads(files["r2-reference.json"])
    for item in manifest["monomers"]:
        item["geometry_optimization_evidence"]["sha256"] = hashlib.sha256(files["minimum-evidence.json"]).hexdigest()
    files["r2-reference.json"] = canonical_json(manifest)
    with pytest.raises(ValueError, match="raw source"):
        ingest_scientific_upload("r2_reference", zip_bytes(files), "reference.zip",
                                  geometry_xyz=XYZ, destination=tmp_path / "rejected")


def mathematical_spring_hessian(path: Path, *, asymmetric=False):
    """A defined spring tensor, with no electronic-method or engine assertion."""
    from cochem_base.core.cochem_constants import BOHR_TO_ANGSTROM
    from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
    identity_record = parse_geometry_identity(XYZ)
    axis = np.asarray([1., 2., 3.])
    axis /= np.linalg.norm(axis)
    block = np.outer(axis, axis)
    hessian = np.block([[block, -block], [-block, block]])
    if asymmetric:
        hessian[0, 1] += 0.1
    lines = ["$hessian", "6", "0 1 2 3 4 5"]
    lines += [str(row) + " " + " ".join(format(value, ".17g") for value in hessian[row]) for row in range(6)]
    lines += ["$atoms", "2"]
    for element, mass, xyz in zip(identity_record.elements, identity_record.masses_u,
                                   np.asarray(identity_record.coordinates_angstrom) / BOHR_TO_ANGSTROM, strict=True):
        lines.append(element + " " + format(mass, ".17g") + " " + " ".join(format(value, ".17g") for value in xyz))
    lines.append("$end")
    path.write_text("\n".join(lines) + "\n")
    return hessian


def test_read_frame_transform_preserves_original_tensor_eigenvalues_and_native_roundtrip(tmp_path):
    source = tmp_path / "original.hess"
    hessian = mathematical_spring_hessian(source)
    original_bytes = source.read_bytes()
    result = transform_read_hessian(source, XYZ, tmp_path / "aligned.hess")
    assert source.read_bytes() == original_bytes
    assert result["receipt"]["source_sha256"] == hashlib.sha256(original_bytes).hexdigest()
    assert result["receipt"]["scientific_execution_performed"] is False
    assert np.allclose(np.linalg.eigvalsh(result["hessian_hartree_bohr2"]), np.linalg.eigvalsh(hessian), atol=1e-12)
    from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
    masses = np.asarray(parse_geometry_identity(XYZ).masses_u)
    assert np.max(np.abs(np.average(result["coordinates_angstrom"], axis=0, weights=masses))) < 1e-12
    from cochem_base.spectroscopy.artifacts import load_hessian_artifact
    parsed = load_hessian_artifact(result["path"])
    assert np.allclose(parsed.coordinates_angstrom, result["coordinates_angstrom"], atol=1e-12)
    assert np.allclose(parsed.hessian_hartree_bohr2, result["hessian_hartree_bohr2"], atol=1e-12)


@pytest.mark.parametrize("geometry", [XYZ.replace("H 1 2 3", "He 1 2 3"),
                                      XYZ.replace("H 2 4 6", "H 2 4 6.01")])
def test_read_different_atom_order_or_original_geometry_is_rejected(tmp_path, geometry):
    source = tmp_path / "original.hess"
    mathematical_spring_hessian(source)
    before = source.read_bytes()
    with pytest.raises(ValueError, match="differ"):
        transform_read_hessian(source, geometry, tmp_path / "rejected.hess")
    assert source.read_bytes() == before and not (tmp_path / "rejected.hess").exists()


def test_asymmetric_native_hessian_cannot_be_transformed(tmp_path):
    source = tmp_path / "original.hess"
    mathematical_spring_hessian(source, asymmetric=True)
    from cochem_base.chain.chain import CorruptOutputError
    with pytest.raises(CorruptOutputError, match="symmetric"):
        transform_read_hessian(source, XYZ, tmp_path / "rejected.hess")
    assert not (tmp_path / "rejected.hess").exists()
