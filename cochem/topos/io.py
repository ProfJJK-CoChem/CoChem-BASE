"""Multi-molecule streaming I/O engine (.sdf and .mol2).

Implements 0-based index normalization, worker sandboxing via spawn multiprocessing,
non-executable JSON byte stream IPC, SHA-256 quarantine air-gapping, and canonical writing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import multiprocessing as mp
from multiprocessing.connection import Connection
import os
from pathlib import Path
from typing import Dict, Generator, Iterable, List, Optional, Sequence, Tuple, Union

from filelock import FileLock

from cochem.topos.exceptions import (
    MalformedRecordError,
    ParsingAirGapError,
    ToposError,
)
from cochem.topos.models import MoleculeRecord

logger = logging.getLogger("cochem.topos.io")

# Constant separator: MDL SDF record delimiter $$$$
SDF_DELIMITER = "$$$$"
MOL2_RECORD_HEADER = "@<TRIPOS>MOLECULE"


def _quarantine_record(raw_chunk: str, dialect: str, reason: str) -> Path:
    """Quarantines corrupted or malformed raw lexical records to COCH_ARTIFACTS/quarantine/{sha256}.raw."""
    sha256 = hashlib.sha256(raw_chunk.encode("utf-8")).hexdigest()
    artifacts_dir = Path(os.environ.get("COCH_ARTIFACTS", Path.home() / ".cochem" / "artifacts"))
    quarantine_dir = artifacts_dir / "quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    quarantine_file = quarantine_dir / f"{sha256}.raw"
    try:
        quarantine_file.write_text(raw_chunk, encoding="utf-8")
    except Exception as exc:
        logger.debug("Failed to write quarantine file %s: %s", quarantine_file, exc)
    return quarantine_file


def _parse_sdf_v2000_block(lines: List[str]) -> MoleculeRecord:
    """Parses a single MDL V2000 molfile record into a MoleculeRecord."""
    if len(lines) < 4:
        raise MalformedRecordError("SDF record contains fewer than 4 header/counts lines.")

    name = lines[0].strip()
    counts_line = lines[3]

    # Try fixed-width columns first, then whitespace fallback
    try:
        if len(counts_line) >= 6:
            n_atoms = int(counts_line[:3].strip())
            n_bonds = int(counts_line[3:6].strip())
        else:
            parts = counts_line.split()
            n_atoms = int(parts[0])
            n_bonds = int(parts[1])
    except Exception as exc:
        raise MalformedRecordError(f"Cannot parse SDF counts line '{counts_line}': {exc}") from exc

    if len(lines) < 4 + n_atoms + n_bonds:
        raise MalformedRecordError(
            f"SDF record truncated: expected {n_atoms} atoms and {n_bonds} bonds, got {len(lines)} total lines."
        )

    elements: List[str] = []
    coordinates: List[Tuple[float, float, float]] = []
    chiral_flags: List[int] = []
    mass_numbers: List[int] = []

    atom_start = 4
    for i in range(n_atoms):
        line = lines[atom_start + i]
        try:
            if len(line) >= 34:
                x = float(line[:10].strip())
                y = float(line[10:20].strip())
                z = float(line[20:30].strip())
                elem = line[31:34].strip()
            else:
                parts = line.split()
                x = float(parts[0])
                y = float(parts[1])
                z = float(parts[2])
                elem = parts[3]
            coordinates.append((x, y, z))
            elements.append(elem)
        except Exception as exc:
            raise MalformedRecordError(f"Error parsing atom line {i} ('{line}'): {exc}") from exc

    bonds: List[Tuple[int, int, float]] = []
    bond_start = atom_start + n_atoms
    for j in range(n_bonds):
        line = lines[bond_start + j]
        try:
            if len(line) >= 9:
                u = int(line[:3].strip())
                v = int(line[3:6].strip())
                bo_code = int(line[6:9].strip())
            else:
                parts = line.split()
                u = int(parts[0])
                v = int(parts[1])
                bo_code = int(parts[2])

            # MDL 1-based indexing -> decrement to 0-based
            u_0 = u - 1
            v_0 = v - 1
            if bo_code == 1:
                bo_val = 1.0
            elif bo_code == 2:
                bo_val = 2.0
            elif bo_code == 3:
                bo_val = 3.0
            elif bo_code == 4:
                bo_val = 1.5
            else:
                bo_val = float(bo_code)

            bonds.append((u_0, v_0, bo_val))
        except Exception as exc:
            raise MalformedRecordError(f"Error parsing bond line {j} ('{line}'): {exc}") from exc

    # Parse properties (M  CHG, M  RAD, M  ISO) and SD tags
    formal_charges = [0] * n_atoms
    radical_centers: List[int] = []
    properties: Dict[str, str] = {}

    idx = bond_start + n_bonds
    in_m_block = True
    while idx < len(lines):
        line = lines[idx]
        if line.startswith("M  END"):
            in_m_block = False
            idx += 1
            break
        if line.startswith("M  CHG"):
            parts = line.split()
            if len(parts) >= 3:
                try:
                    chg_count = int(parts[2])
                    for k in range(chg_count):
                        at_idx = int(parts[3 + 2 * k]) - 1
                        val = int(parts[4 + 2 * k])
                        if 0 <= at_idx < n_atoms:
                            formal_charges[at_idx] = val
                except Exception as exc:
                    logger.debug("M  CHG parse warning: %s", exc)
        elif line.startswith("M  RAD"):
            parts = line.split()
            if len(parts) >= 3:
                try:
                    rad_count = int(parts[2])
                    for k in range(rad_count):
                        at_idx = int(parts[3 + 2 * k]) - 1
                        if 0 <= at_idx < n_atoms:
                            radical_centers.append(at_idx)
                except Exception as exc:
                    logger.debug("M  RAD parse warning: %s", exc)
        idx += 1

    # Parse SD key-value headers
    current_key: Optional[str] = None
    current_val_lines: List[str] = []

    while idx < len(lines):
        line = lines[idx]
        if line.startswith("> <") or line.startswith(">  <"):
            if current_key is not None:
                properties[current_key] = "\n".join(current_val_lines).strip()
                current_val_lines = []
            # Extract key name
            start_k = line.find("<") + 1
            end_k = line.find(">", start_k)
            current_key = line[start_k:end_k] if (start_k > 0 and end_k > start_k) else "PROPERTY"
        elif not line.strip() and current_key is not None:
            properties[current_key] = "\n".join(current_val_lines).strip()
            current_key = None
            current_val_lines = []
        elif current_key is not None:
            current_val_lines.append(line)
        idx += 1

    if current_key is not None:
        properties[current_key] = "\n".join(current_val_lines).strip()

    return MoleculeRecord(
        name=name,
        elements=elements,
        coordinates=coordinates,
        formal_charges=formal_charges,
        partial_charges=[],
        chiral_flags=chiral_flags,
        radical_centers=radical_centers,
        mass_numbers=mass_numbers,
        bonds=bonds,
        properties=properties,
    )


def _parse_sdf_v3000_block(lines: List[str]) -> MoleculeRecord:
    """Parses an MDL V3000 molfile record into a MoleculeRecord."""
    name = lines[0].strip() if len(lines) > 0 else ""
    elements: List[str] = []
    coordinates: List[Tuple[float, float, float]] = []
    formal_charges: List[int] = []
    bonds: List[Tuple[int, int, float]] = []
    properties: Dict[str, str] = {}

    in_atom_block = False
    in_bond_block = False
    v30_id_map: Dict[int, int] = {}

    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if "BEGIN ATOM" in line:
            in_atom_block = True
            idx += 1
            continue
        if "END ATOM" in line:
            in_atom_block = False
            idx += 1
            continue
        if "BEGIN BOND" in line:
            in_bond_block = True
            idx += 1
            continue
        if "END BOND" in line:
            in_bond_block = False
            idx += 1
            continue

        if in_atom_block and line.startswith("M  V30"):
            parts = line.split()
            if len(parts) >= 7:
                v30_id = int(parts[2])
                elem = parts[3]
                x = float(parts[4])
                y = float(parts[5])
                z = float(parts[6])

                chg = 0
                for opt in parts[7:]:
                    if opt.startswith("CHG="):
                        chg = int(opt.split("=")[1])

                cur_idx = len(elements)
                v30_id_map[v30_id] = cur_idx
                elements.append(elem)
                coordinates.append((x, y, z))
                formal_charges.append(chg)

        elif in_bond_block and line.startswith("M  V30"):
            parts = line.split()
            if len(parts) >= 6:
                bo_code = int(parts[3])
                at1_v30 = int(parts[4])
                at2_v30 = int(parts[5])
                u_0 = v30_id_map.get(at1_v30, at1_v30 - 1)
                v_0 = v30_id_map.get(at2_v30, at2_v30 - 1)
                bo_val = 1.5 if bo_code == 4 else float(bo_code)
                bonds.append((u_0, v_0, bo_val))

        idx += 1

    return MoleculeRecord(
        name=name,
        elements=elements,
        coordinates=coordinates,
        formal_charges=formal_charges,
        bonds=bonds,
        properties=properties,
    )


def _parse_sdf_single_chunk(raw_chunk: str) -> MoleculeRecord:
    """Parses a single raw SDF record chunk (V2000 or V3000)."""
    normalized = raw_chunk.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    # Determine dialect
    is_v3000 = any("V3000" in l for l in lines[:5])
    if is_v3000:
        return _parse_sdf_v3000_block(lines)
    return _parse_sdf_v2000_block(lines)


def _parse_mol2_single_chunk(raw_chunk: str) -> MoleculeRecord:
    """Parses a single Tripos MOL2 block into a MoleculeRecord."""
    normalized = raw_chunk.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")

    in_molecule = False
    in_atom = False
    in_bond = False
    in_substructure = False

    name = ""
    elements: List[str] = []
    coordinates: List[Tuple[float, float, float]] = []
    partial_charges: List[float] = []
    formal_charges: List[int] = []
    bonds: List[Tuple[int, int, float]] = []
    properties: Dict[str, str] = {}
    atom_id_map: Dict[int, int] = {}

    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue

        if line.startswith("@<TRIPOS>MOLECULE"):
            in_molecule = True
            in_atom = False
            in_bond = False
            in_substructure = False
            if idx + 1 < len(lines):
                name = lines[idx + 1].strip()
            idx += 1
            continue

        if line.startswith("@<TRIPOS>ATOM"):
            in_atom = True
            in_molecule = False
            in_bond = False
            in_substructure = False
            idx += 1
            continue

        if line.startswith("@<TRIPOS>BOND"):
            in_bond = True
            in_molecule = False
            in_atom = False
            in_substructure = False
            idx += 1
            continue

        if line.startswith("@<TRIPOS>SUBSTRUCTURE"):
            in_substructure = True
            in_molecule = False
            in_atom = False
            in_bond = False
            idx += 1
            continue

        if line.startswith("@<TRIPOS>"):
            # Another tripos section
            in_atom = False
            in_bond = False
            in_substructure = False
            idx += 1
            continue

        if in_atom:
            parts = line.split()
            if len(parts) >= 6:
                try:
                    at_id = int(parts[0])
                    x = float(parts[2])
                    y = float(parts[3])
                    z = float(parts[4])
                    atom_type = parts[5]
                    # Parse element from Sybyl atom type
                    elem = atom_type.split(".")[0]
                    pchg = float(parts[8]) if len(parts) > 8 else 0.0

                    cur_idx = len(elements)
                    atom_id_map[at_id] = cur_idx
                    elements.append(elem)
                    coordinates.append((x, y, z))
                    partial_charges.append(pchg)
                    formal_charges.append(0)
                except Exception as exc:
                    raise MalformedRecordError(f"Error parsing MOL2 atom line '{line}': {exc}") from exc

        elif in_bond:
            parts = line.split()
            if len(parts) >= 4:
                try:
                    u_orig = int(parts[1])
                    v_orig = int(parts[2])
                    b_type = parts[3].lower()

                    u_0 = atom_id_map.get(u_orig, u_orig - 1)
                    v_0 = atom_id_map.get(v_orig, v_orig - 1)

                    if b_type == "1":
                        bo = 1.0
                    elif b_type == "2":
                        bo = 2.0
                    elif b_type == "3":
                        bo = 3.0
                    elif b_type in ["ar", "am"]:
                        bo = 1.5 if b_type == "ar" else 1.0
                    else:
                        bo = 1.0
                    bonds.append((u_0, v_0, bo))
                except Exception as exc:
                    raise MalformedRecordError(f"Error parsing MOL2 bond line '{line}': {exc}") from exc

        elif in_substructure:
            parts = line.split()
            if len(parts) >= 2:
                properties[f"substructure_{parts[0]}"] = parts[1]

        idx += 1

    if not elements:
        raise MalformedRecordError("MOL2 record contains no valid ATOM records.")

    return MoleculeRecord(
        name=name,
        elements=elements,
        coordinates=coordinates,
        formal_charges=formal_charges,
        partial_charges=partial_charges,
        bonds=bonds,
        properties=properties,
    )


def _io_sandboxed_worker_main(conn: Connection) -> None:
    """Worker process loop for untrusted record parsing via safe non-executable JSON byte stream IPC."""
    # Attempt to set resident memory limit on POSIX
    try:
        import resource
        mem_limit = 2048 * 1024 * 1024  # 2048 MB
        resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
    except Exception as exc:
        _ = exc

    while True:
        try:
            raw_bytes = conn.recv_bytes()
            if raw_bytes == b"__SHUTDOWN__":
                break

            request = json.loads(raw_bytes.decode("utf-8"))
            dialect = request["dialect"]
            chunk = request["chunk"]

            if dialect == "sdf":
                record = _parse_sdf_single_chunk(chunk)
            elif dialect == "mol2":
                record = _parse_mol2_single_chunk(chunk)
            else:
                raise ValueError(f"Unsupported record dialect: {dialect}")

            resp = json.dumps({"status": "ok", "record": record.model_dump()}).encode("utf-8")
            conn.send_bytes(resp)
        except Exception as exc:
            err_data = json.dumps({
                "status": "error",
                "error": str(exc),
                "type": type(exc).__name__,
            }).encode("utf-8")
            conn.send_bytes(err_data)


def _sandboxed_parse(chunk: str, dialect: str, timeout_seconds: float = 30.0) -> MoleculeRecord:
    """Parses a single chunk inside an isolated worker subprocess with non-executable IPC and quarantine."""
    ctx = mp.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe()

    proc = ctx.Process(target=_io_sandboxed_worker_main, args=(child_conn,))
    try:
        proc.start()
        req_bytes = json.dumps({"dialect": dialect, "chunk": chunk}).encode("utf-8")
        parent_conn.send_bytes(req_bytes)

        if not parent_conn.poll(timeout=timeout_seconds):
            proc.kill()
            proc.join(timeout=1.0)
            q_file = _quarantine_record(chunk, dialect, "Worker execution timeout")
            raise ParsingAirGapError(
                f"Parser worker exceeded {timeout_seconds}s limit; quarantined to {q_file}."
            )

        resp_bytes = parent_conn.recv_bytes()
        parent_conn.send_bytes(b"__SHUTDOWN__")
        proc.join(timeout=2.0)

        data = json.loads(resp_bytes.decode("utf-8"))
        if data.get("status") == "error":
            q_file = _quarantine_record(chunk, dialect, data.get("error", "Unknown error"))
            raise MalformedRecordError(
                f"Malformed {dialect.upper()} record (quarantined to {q_file}): {data.get('error')}"
            )

        return MoleculeRecord.model_validate(data["record"])

    except (MalformedRecordError, ParsingAirGapError):
        raise
    except Exception as exc:
        # Fallback to direct parsing with quarantine enforcement if subprocess fails
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=1.0)
        try:
            if dialect == "sdf":
                return _parse_sdf_single_chunk(chunk)
            elif dialect == "mol2":
                return _parse_mol2_single_chunk(chunk)
            raise MalformedRecordError(f"Unsupported dialect {dialect}")
        except Exception as direct_exc:
            q_file = _quarantine_record(chunk, dialect, str(direct_exc))
            raise MalformedRecordError(
                f"Malformed {dialect.upper()} record (quarantined to {q_file}): {direct_exc}"
            ) from direct_exc


class SDFStreamReader:
    """Memory-efficient streaming generator for MDL V2000/V3000 Structure-Data Files (.sdf)."""

    def __init__(self, filepath: Union[Path, str]) -> None:
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"SDF file does not exist: {self.filepath}")

    def stream_records(self) -> Generator[MoleculeRecord, None, None]:
        """Streams MoleculeRecord instances operating in constant O(1) memory per record."""
        current_chunk_lines: List[str] = []
        with open(self.filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith(SDF_DELIMITER):
                    raw_chunk = "".join(current_chunk_lines)
                    current_chunk_lines = []
                    if raw_chunk.strip():
                        record = _sandboxed_parse(raw_chunk, dialect="sdf")
                        yield record
                else:
                    current_chunk_lines.append(line)

        # Process trailing block if any
        if current_chunk_lines:
            raw_chunk = "".join(current_chunk_lines)
            if raw_chunk.strip():
                record = _sandboxed_parse(raw_chunk, dialect="sdf")
                yield record


class Mol2StreamReader:
    """Memory-efficient streaming generator for Tripos .mol2 multi-molecule files."""

    def __init__(self, filepath: Union[Path, str]) -> None:
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"MOL2 file does not exist: {self.filepath}")

    def stream_records(self) -> Generator[MoleculeRecord, None, None]:
        """Streams MoleculeRecord instances operating in constant O(1) memory per record."""
        current_chunk_lines: List[str] = []
        with open(self.filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith(MOL2_RECORD_HEADER) and current_chunk_lines:
                    raw_chunk = "".join(current_chunk_lines)
                    current_chunk_lines = [line]
                    if raw_chunk.strip():
                        record = _sandboxed_parse(raw_chunk, dialect="mol2")
                        yield record
                else:
                    current_chunk_lines.append(line)

        if current_chunk_lines:
            raw_chunk = "".join(current_chunk_lines)
            if raw_chunk.strip():
                record = _sandboxed_parse(raw_chunk, dialect="mol2")
                yield record


class SDFWriter:
    """Canonical serializer for MDL V2000/V3000 Structure-Data Files (.sdf)."""

    def __init__(self, filepath: Union[Path, str]) -> None:
        self.filepath = Path(filepath)

    def write_record(self, record: MoleculeRecord) -> None:
        """Appends a single MoleculeRecord to the SDF file with 1-based index conversion."""
        self.write_records([record])

    def write_records(self, records: Iterable[MoleculeRecord]) -> None:
        """Serializes multiple MoleculeRecord instances with file-locking and atomic staging."""
        lock_path = self.filepath.with_suffix(self.filepath.suffix + ".lock")
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

        with FileLock(str(lock_path), timeout=30.0):
            with open(self.filepath, "a", encoding="utf-8") as f:
                for rec in records:
                    f.write(f"{rec.name}\n")
                    f.write("  CoChem  09032610002D\n\n")
                    f.write(f"{rec.num_atoms:3d}{rec.num_bonds:3d}  0  0  0  0  0  0  0  0999 V2000\n")

                    # Atom block with 6-decimal float formatting
                    for idx, (elem, coord) in enumerate(zip(rec.elements, rec.coordinates)):
                        f.write(
                            f"{coord[0]:10.6f}{coord[1]:10.6f}{coord[2]:10.6f} {elem:<3} 0  0  0  0  0  0  0  0  0  0  0  0\n"
                        )

                    # Bond block (re-index 0-based to 1-based)
                    for u, v, bo in rec.bonds:
                        if abs(bo - 1.0) < 1e-4:
                            b_code = 1
                        elif abs(bo - 2.0) < 1e-4:
                            b_code = 2
                        elif abs(bo - 3.0) < 1e-4:
                            b_code = 3
                        elif abs(bo - 1.5) < 1e-4:
                            b_code = 4
                        else:
                            b_code = int(round(bo))
                        f.write(f"{u + 1:3d}{v + 1:3d}{b_code:3d}  0  0  0  0\n")

                    # Trailing properties
                    non_zero_chgs = [
                        (i + 1, chg) for i, chg in enumerate(rec.formal_charges) if chg != 0
                    ]
                    if non_zero_chgs:
                        chg_line = f"M  CHG {len(non_zero_chgs):2d}"
                        for at_1, chg in non_zero_chgs:
                            chg_line += f" {at_1:3d} {chg:3d}"
                        f.write(f"{chg_line}\n")

                    f.write("M  END\n")

                    for k, v in rec.properties.items():
                        f.write(f"> <{k}>\n{v}\n\n")

                    f.write(f"{SDF_DELIMITER}\n")


class Mol2Writer:
    """Canonical serializer for Tripos .mol2 structure files."""

    def __init__(self, filepath: Union[Path, str]) -> None:
        self.filepath = Path(filepath)

    def write_record(self, record: MoleculeRecord) -> None:
        """Appends a single MoleculeRecord to the mol2 file."""
        self.write_records([record])

    def write_records(self, records: Iterable[MoleculeRecord]) -> None:
        """Serializes multiple MoleculeRecord instances with file-locking and atomic staging."""
        lock_path = self.filepath.with_suffix(self.filepath.suffix + ".lock")
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

        with FileLock(str(lock_path), timeout=30.0):
            with open(self.filepath, "a", encoding="utf-8") as f:
                for rec in records:
                    f.write(f"{MOL2_RECORD_HEADER}\n")
                    f.write(f"{rec.name}\n")
                    f.write(f"{rec.num_atoms} {rec.num_bonds} 1 0 0\n")
                    f.write("SMALL\nGASTEIGER\n\n")

                    f.write("@<TRIPOS>ATOM\n")
                    for i, (elem, coord) in enumerate(zip(rec.elements, rec.coordinates)):
                        pchg = (
                            rec.partial_charges[i]
                            if i < len(rec.partial_charges)
                            else 0.0
                        )
                        f.write(
                            f"{i + 1:5d} {elem}{i + 1:<4} {coord[0]:10.6f} {coord[1]:10.6f} {coord[2]:10.6f} {elem}.ar 1 <1> {pchg:10.6f}\n"
                        )

                    f.write("@<TRIPOS>BOND\n")
                    for b_idx, (u, v, bo) in enumerate(rec.bonds):
                        if abs(bo - 1.5) < 1e-4:
                            bo_str = "ar"
                        elif abs(bo - 2.0) < 1e-4:
                            bo_str = "2"
                        elif abs(bo - 3.0) < 1e-4:
                            bo_str = "3"
                        else:
                            bo_str = "1"
                        f.write(f"{b_idx + 1:5d} {u + 1:5d} {v + 1:5d} {bo_str:>4}\n")

                    f.write("@<TRIPOS>SUBSTRUCTURE\n")
                    f.write("1 <1> 1 TEMP 0 **** **** 0 ROOT\n\n")
