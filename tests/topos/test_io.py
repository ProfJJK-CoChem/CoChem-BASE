"""Physical acceptance tests for multi-molecule streaming I/O (.sdf and .mol2)."""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from cochem.topos.exceptions import MalformedRecordError
from cochem.topos.io import Mol2StreamReader, Mol2Writer, SDFStreamReader, SDFWriter
from cochem.topos.models import MoleculeRecord


def test_sdf_v2000_streaming_and_quarantine(tmp_path: Path) -> None:
    """REQ-TOPOS-001: Test streaming parser isolation, 0-based normalization, and quarantine handling."""
    sdf_content = (
        "benzene\n  CoChem  09022610002D\n\n  6  6  0  0  0  0  0  0  0  0999 V2000\n"
        "    0.0000    1.4000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "    1.2124    0.7000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "    1.2124   -0.7000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "    0.0000   -1.4000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "   -1.2124   -0.7000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "   -1.2124    0.7000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "  1  2  2  0  0  0  0\n  2  3  1  0  0  0  0\n  3  4  2  0  0  0  0\n"
        "  4  5  1  0  0  0  0\n  5  6  2  0  0  0  0\n  6  1  1  0  0  0  0\n"
        "M  END\n$$$$\n"
    )
    sdf_file = tmp_path / "benzene.sdf"
    sdf_file.write_text(sdf_content, encoding="utf-8")
    reader = SDFStreamReader(sdf_file)
    records = list(reader.stream_records())
    assert len(records) == 1
    rec = records[0]
    assert rec.name == "benzene"
    assert len(rec.elements) == 6
    # Verify 0-based normalization (input was 1 2 2, normalized should be (0, 1, 2.0))
    assert rec.bonds[0] == (0, 1, 2.0)

    # Quarantine handling test on corrupted record
    corrupt_sdf = tmp_path / "corrupt.sdf"
    corrupt_sdf.write_text("corrupted_mol\ninfo\ncomment\nINVALID COUNTS LINE\n$$$$\n", encoding="utf-8")
    with pytest.raises(MalformedRecordError) as exc_info:
        list(SDFStreamReader(corrupt_sdf).stream_records())

    assert "quarantined to" in str(exc_info.value)
    # Check quarantine directory
    art_dir = Path(os.environ.get("COCH_ARTIFACTS", Path.home() / ".cochem" / "artifacts"))
    quarantine_files = list((art_dir / "quarantine").glob("*.raw"))
    assert len(quarantine_files) > 0


def test_mol2_streaming(tmp_path: Path) -> None:
    """REQ-TOPOS-001: Test Tripos mol2 streaming, Sybyl atom types, and partial charges."""
    mol2_content = (
        "@<TRIPOS>MOLECULE\n"
        "benzene\n"
        "6 6 1 0 0\n"
        "SMALL\n"
        "GASTEIGER\n\n"
        "@<TRIPOS>ATOM\n"
        "1 C1 0.0000 1.4000 0.0000 C.ar 1 BENZENE -0.0600\n"
        "2 C2 1.2124 0.7000 0.0000 C.ar 1 BENZENE -0.0600\n"
        "3 C3 1.2124 -0.7000 0.0000 C.ar 1 BENZENE -0.0600\n"
        "4 C4 0.0000 -1.4000 0.0000 C.ar 1 BENZENE -0.0600\n"
        "5 C5 -1.2124 -0.7000 0.0000 C.ar 1 BENZENE -0.0600\n"
        "6 C6 -1.2124 0.7000 0.0000 C.ar 1 BENZENE -0.0600\n"
        "@<TRIPOS>BOND\n"
        "1 1 2 ar\n"
        "2 2 3 ar\n"
        "3 3 4 ar\n"
        "4 4 5 ar\n"
        "5 5 6 ar\n"
        "6 6 1 ar\n"
        "@<TRIPOS>SUBSTRUCTURE\n"
        "1 BENZENE 1 TEMP 0 **** **** 0 ROOT\n"
    )
    mol2_file = tmp_path / "benzene.mol2"
    mol2_file.write_text(mol2_content, encoding="utf-8")
    reader = Mol2StreamReader(mol2_file)
    records = list(reader.stream_records())
    assert len(records) == 1
    rec = records[0]
    assert rec.name == "benzene"
    assert len(rec.elements) == 6
    assert rec.bonds[0] == (0, 1, 1.5)
    assert len(rec.partial_charges) == 6
    assert abs(rec.partial_charges[0] - (-0.0600)) < 1e-4


def test_sdf_and_mol2_roundtrip_writing(tmp_path: Path) -> None:
    """REQ-TOPOS-001: Test batch and streaming serialization with SDFWriter and Mol2Writer."""
    rec = MoleculeRecord(
        name="phenol",
        elements=["O", "C", "C", "C", "C", "C", "C"],
        coordinates=[
            (0.0, 2.8, 0.0),
            (0.0, 1.4, 0.0),
            (1.2, 0.7, 0.0),
            (1.2, -0.7, 0.0),
            (0.0, -1.4, 0.0),
            (-1.2, -0.7, 0.0),
            (-1.2, 0.7, 0.0),
        ],
        formal_charges=[0, 0, 0, 0, 0, 0, 0],
        bonds=[
            (0, 1, 1.0),
            (1, 2, 1.5),
            (2, 3, 1.5),
            (3, 4, 1.5),
            (4, 5, 1.5),
            (5, 6, 1.5),
            (6, 1, 1.5),
        ],
        properties={"compound": "phenol"},
    )
    sdf_out = tmp_path / "phenol.sdf"
    sdf_writer = SDFWriter(sdf_out)
    sdf_writer.write_record(rec)

    r_sdf = list(SDFStreamReader(sdf_out).stream_records())
    assert len(r_sdf) == 1
    assert r_sdf[0].name == "phenol"
    assert len(r_sdf[0].bonds) == 7

    mol2_out = tmp_path / "phenol.mol2"
    mol2_writer = Mol2Writer(mol2_out)
    mol2_writer.write_record(rec)

    r_mol2 = list(Mol2StreamReader(mol2_out).stream_records())
    assert len(r_mol2) == 1
    assert r_mol2[0].name == "phenol"
    assert len(r_mol2[0].elements) == 7
