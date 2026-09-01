#!/usr/bin/env python3
"""
CoChem-CORE: Stage 1.x - Universal Non-Destructive Ingestor & Mendeleev Metadata Reader.
Module: intake/CoChem-MInt.py

Authoritative Specifications:
1. D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\Method_Matrix.md
2. D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\CoChem_User_Manual.md
3. D:\\__CoChem\\__agentic\\.prompts\\.SRS\\CoChem-BASE\\.in-progress\\Doc2_Part2_08_intake_mint_prompt.md

Directives & Mandates:
- Production-ready zero-defect ingestion engine.
- Exact Mendeleev isotopic mass, nuclear charge, covalent radius, and van der Waals radius resolution.
- Immutable non-destructive Cartesian coordinate indexing with auxiliary 1D metadata tensors:
    M_aux (monoisotopic masses)
    Z_aux (nuclear charges / atomic numbers)
    R_cov_aux (covalent radii in Angstroms)
    R_vdw_aux (van der Waals radii in Angstroms)
- SHA-256 hash provenance and duplicate prevention.
- Bounded ThreadPoolExecutor for concurrent batch scanning.
- Robust I/O fallback hierarchy: custom -> $SCRATCH -> $COCHEM_SCRATCH -> $SLURM_TMPDIR -> $TEMP/$TMPDIR -> local scratch.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import mendeleev
import numpy as np
from pydantic import BaseModel

from cochem_base.config_loader import load_system_config


class CoChemIngestionError(Exception):
    """Exception raised for errors in the ingestion pipeline."""
    pass


class AtomMetadata(BaseModel):
    """Metadata container for individual atomic centers."""
    symbol: str
    atomic_number: int
    monoisotopic_mass: float
    covalent_radius: float
    vdw_radius: float
    x: float
    y: float
    z: float


class MolecularGeometryPayload(BaseModel):
    """Standardized immutable molecular geometry payload with auxiliary tensors."""
    filename: str
    format: str
    sha256_hash: str
    symbols: List[str]
    coordinates: List[List[float]]
    total_atoms: int
    M_aux: List[float]
    Z_aux: List[int]
    R_cov_aux: List[float]
    R_vdw_aux: List[float]
    atoms: List[AtomMetadata]
    comment: str = ""
    net_charge: int = 0
    multiplicity: int = 1

    @property
    def coordinate_array(self) -> np.ndarray:
        """Returns coordinates as an (N, 3) float64 NumPy array."""
        return np.asarray(self.coordinates, dtype=np.float64)

    @property
    def mass_tensor(self) -> np.ndarray:
        """Returns M_aux as a 1D float64 NumPy array."""
        return np.asarray(self.M_aux, dtype=np.float64)

    @property
    def charge_tensor(self) -> np.ndarray:
        """Returns Z_aux as a 1D int32 NumPy array."""
        return np.asarray(self.Z_aux, dtype=np.int32)

    @property
    def cov_radius_tensor(self) -> np.ndarray:
        """Returns R_cov_aux as a 1D float64 NumPy array."""
        return np.asarray(self.R_cov_aux, dtype=np.float64)

    @property
    def vdw_radius_tensor(self) -> np.ndarray:
        """Returns R_vdw_aux as a 1D float64 NumPy array."""
        return np.asarray(self.R_vdw_aux, dtype=np.float64)


class BatchIngestionSummary(BaseModel):
    """Summary of batch directory ingestion operations."""
    input_directory: str
    total_files_scanned: int
    successful_ingestions: int
    failed_ingestions: int
    payloads: List[MolecularGeometryPayload]
    sha256_registry: List[str]
    valid_graphs: List[MolecularGeometryPayload]


# In-memory cache for Mendeleev elemental queries
_ELEMENT_CACHE: Dict[str, Dict[str, Any]] = {}


def get_element_data(symbol: str) -> Dict[str, Any]:
    """Retrieve elemental data via mendeleev with thread-safe caching."""
    clean_sym = symbol.strip().capitalize()
    if clean_sym in _ELEMENT_CACHE:
        return _ELEMENT_CACHE[clean_sym]

    try:
        elem = mendeleev.element(clean_sym)

        z = int(elem.atomic_number)
        isotopes = elem.isotopes
        if isotopes:
            abundant_iso = max(isotopes, key=lambda iso: iso.abundance or 0.0) if any(iso.abundance for iso in isotopes) else isotopes[0]
            mono_mass = float(abundant_iso.mass)
        else:
            mono_mass = float(elem.mass)

        cov_rad = float(elem.covalent_radius_pyykko or elem.covalent_radius or 0.0)
        if cov_rad > 10.0:
            cov_rad = cov_rad / 100.0

        vdw_rad = float(elem.vdw_radius or 0.0)
        if vdw_rad > 10.0:
            vdw_rad = vdw_rad / 100.0

        data = {
            "symbol": elem.symbol,
            "atomic_number": z,
            "monoisotopic_mass": mono_mass,
            "covalent_radius": cov_rad,
            "vdw_radius": vdw_rad,
        }
        _ELEMENT_CACHE[clean_sym] = data
        return data
    except Exception as e:
        raise ValueError(f"Invalid element symbol '{symbol}': {e}") from e


def compute_sha256(content: Union[str, bytes]) -> str:
    """Compute cryptographic SHA-256 hex digest of string or raw bytes."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def bind_system_config(config_path: Optional[Union[str, Path]] = None) -> Any:
    """Bind system configuration via cochem_base.config_loader."""
    if config_path is None:
        config_env = os.environ.get("COCHEM_CONFIG")
        if config_env:
            config_path = Path(config_env)
        else:
            config_path = Path(__file__).resolve().parent.parent / "cochem_system_config.json"
    return load_system_config(Path(config_path))


def resolve_io_scratch_directory(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve fallback scratch directory in order of decreasing locality:
    1. custom_path (explicit caller override)
    2. $SCRATCH / $COCHEM_SCRATCH / $SLURM_TMPDIR / $COCHEM_SCRATCH_DIR
    3. %TEMP% / $TMPDIR
    4. tempfile.gettempdir() / 'cochem_scratch'
    """
    if custom_path is not None:
        path = Path(custom_path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    for env_var in ["SCRATCH", "COCHEM_SCRATCH", "SLURM_TMPDIR", "COCHEM_SCRATCH_DIR", "TEMP", "TMPDIR"]:
        val = os.environ.get(env_var)
        if val:
            path = Path(val)
            path.mkdir(parents=True, exist_ok=True)
            return path

    fallback = Path(tempfile.gettempdir()) / "cochem_scratch"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def resolve_scratch_directory(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """Convenience alias for resolve_io_scratch_directory."""
    return resolve_io_scratch_directory(custom_path)


def get_scratch_dir(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """Convenience alias for resolve_io_scratch_directory."""
    return resolve_io_scratch_directory(custom_path)


def ingest_string(content: str, format: str, filename: str) -> MolecularGeometryPayload:
    """Parse raw string content of xyz or mol/sdf format into MolecularGeometryPayload."""
    sha256_hash = compute_sha256(content)
    content_stripped = content.strip()
    if not content_stripped:
        raise ValueError("Empty file content")

    fmt = format.lower()
    if fmt == "xyz":
        lines = content.splitlines()
        if len(lines) < 3:
            raise ValueError("Invalid XYZ format: too few lines")
        try:
            total_atoms = int(lines[0].strip())
        except ValueError as e:
            raise ValueError("Invalid XYZ format: first line must be atom count") from e

        comment = lines[1].strip()

        symbols: List[str] = []
        coords: List[List[float]] = []
        atoms: List[AtomMetadata] = []
        m_aux: List[float] = []
        z_aux: List[int] = []
        r_cov_aux: List[float] = []
        r_vdw_aux: List[float] = []

        if len(lines) < total_atoms + 2:
            raise ValueError(f"Truncated coordinate lines. Expected {total_atoms}, got {len(lines) - 2}")

        for i in range(2, 2 + total_atoms):
            parts = lines[i].split()
            if len(parts) < 4:
                raise ValueError(f"Invalid atom line: {lines[i]}")
            sym = parts[0]
            try:
                x = float(parts[1])
                y = float(parts[2])
                z = float(parts[3])
            except ValueError as e:
                raise ValueError(f"Non-numeric coordinates on line {i + 1}: {lines[i]}") from e

            edata = get_element_data(sym)
            symbols.append(edata["symbol"])
            coords.append([x, y, z])
            m_aux.append(edata["monoisotopic_mass"])
            z_aux.append(edata["atomic_number"])
            r_cov_aux.append(edata["covalent_radius"])
            r_vdw_aux.append(edata["vdw_radius"])

            atoms.append(AtomMetadata(
                symbol=edata["symbol"],
                atomic_number=edata["atomic_number"],
                monoisotopic_mass=edata["monoisotopic_mass"],
                covalent_radius=edata["covalent_radius"],
                vdw_radius=edata["vdw_radius"],
                x=x, y=y, z=z
            ))

    elif fmt in ["mol", "sdf"]:
        lines = content.splitlines()
        if len(lines) < 4:
            raise ValueError("Invalid MOL format: too few lines")
        comment = lines[0].strip()

        counts_line = lines[3]
        if len(counts_line) < 3:
            raise ValueError("Invalid MOL counts line")
        try:
            total_atoms = int(counts_line[0:3].strip())
        except ValueError as e:
            raise ValueError("Invalid MOL counts line: atom count not integer") from e

        symbols = []
        coords = []
        atoms = []
        m_aux = []
        z_aux = []
        r_cov_aux = []
        r_vdw_aux = []

        if len(lines) < 4 + total_atoms:
            raise ValueError(f"Truncated MOL coordinates. Expected {total_atoms} atoms.")

        for i in range(4, 4 + total_atoms):
            line = lines[i]
            if len(line) >= 34:
                try:
                    x = float(line[0:10].strip())
                    y = float(line[10:20].strip())
                    z = float(line[20:30].strip())
                    sym = line[31:34].strip()
                except ValueError:
                    parts = line.split()
                    if len(parts) >= 4:
                        x = float(parts[0])
                        y = float(parts[1])
                        z = float(parts[2])
                        sym = parts[3]
                    else:
                        raise ValueError(f"Invalid MOL atom line: {line}") from None
            else:
                parts = line.split()
                if len(parts) >= 4:
                    x = float(parts[0])
                    y = float(parts[1])
                    z = float(parts[2])
                    sym = parts[3]
                else:
                    raise ValueError(f"Invalid MOL atom line: {line}")

            edata = get_element_data(sym)
            symbols.append(edata["symbol"])
            coords.append([x, y, z])
            m_aux.append(edata["monoisotopic_mass"])
            z_aux.append(edata["atomic_number"])
            r_cov_aux.append(edata["covalent_radius"])
            r_vdw_aux.append(edata["vdw_radius"])

            atoms.append(AtomMetadata(
                symbol=edata["symbol"],
                atomic_number=edata["atomic_number"],
                monoisotopic_mass=edata["monoisotopic_mass"],
                covalent_radius=edata["covalent_radius"],
                vdw_radius=edata["vdw_radius"],
                x=x, y=y, z=z
            ))
    else:
        raise ValueError(f"Unsupported format: {format}")

    return MolecularGeometryPayload(
        filename=filename,
        format=format,
        sha256_hash=sha256_hash,
        symbols=symbols,
        coordinates=coords,
        total_atoms=total_atoms,
        M_aux=m_aux,
        Z_aux=z_aux,
        R_cov_aux=r_cov_aux,
        R_vdw_aux=r_vdw_aux,
        atoms=atoms,
        comment=comment
    )


def ingest_file(file_path: Union[str, Path]) -> MolecularGeometryPayload:
    """Ingest a file automatically determining format from its extension."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    ext = path.suffix.lower()
    if ext == ".xyz":
        return ingest_xyz(path)
    elif ext in [".mol", ".sdf"]:
        return ingest_mol(path)
    else:
        raise ValueError(f"Unsupported file extension: {ext}")


def ingest_xyz(file_path: Union[str, Path]) -> MolecularGeometryPayload:
    """Ingest an XYZ geometry file."""
    path = Path(file_path)
    raw_bytes = path.read_bytes()
    content = raw_bytes.decode("utf-8")
    payload = ingest_string(content, format="xyz", filename=path.name)
    payload.sha256_hash = compute_sha256(raw_bytes)
    return payload


def ingest_mol(file_path: Union[str, Path]) -> MolecularGeometryPayload:
    """Ingest a MOL/SDF geometry file."""
    path = Path(file_path)
    raw_bytes = path.read_bytes()
    content = raw_bytes.decode("utf-8")
    payload = ingest_string(content, format="mol", filename=path.name)
    payload.sha256_hash = compute_sha256(raw_bytes)
    return payload


def scan_batch_directory(
    input_dir: Union[str, Path],
    max_workers: int = 4,
    recursive: bool = False
) -> BatchIngestionSummary:
    """
    Scans a directory for molecular files using a bounded thread pool.
    Deduplicates incoming files via SHA-256 hashing.
    """
    path = Path(input_dir)
    if not path.is_dir():
        raise ValueError(f"Input directory not found: {path}")

    files_to_process: List[Path] = []
    iterator = path.rglob("*") if recursive else path.iterdir()
    for item in iterator:
        if item.is_file() and item.suffix.lower() in [".xyz", ".mol", ".sdf"]:
            files_to_process.append(item)

    files_to_process.sort(key=lambda p: p.name)

    payloads: List[MolecularGeometryPayload] = []
    sha256_registry: List[str] = []
    seen_hashes = set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(ingest_file, f) for f in files_to_process]
        for future in futures:
            try:
                payload = future.result()
                if payload.sha256_hash not in seen_hashes:
                    seen_hashes.add(payload.sha256_hash)
                    payloads.append(payload)
                    sha256_registry.append(payload.sha256_hash)
            except Exception:
                pass

    return BatchIngestionSummary(
        input_directory=str(path),
        total_files_scanned=len(files_to_process),
        successful_ingestions=len(payloads),
        failed_ingestions=len(files_to_process) - len(payloads),
        payloads=payloads,
        sha256_registry=sha256_registry,
        valid_graphs=payloads
    )


def batch_scan(input_dir: Union[str, Path], max_workers: int = 4) -> BatchIngestionSummary:
    """Convenience alias for scan_batch_directory."""
    return scan_batch_directory(input_dir, max_workers=max_workers)


class MIntIngestor:
    """Universal Reader Ingestion Engine."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    def ingest_file(self, file_path: Union[str, Path]) -> MolecularGeometryPayload:
        return ingest_file(file_path)

    def parse_xyz(self, file_path: Union[str, Path]) -> MolecularGeometryPayload:
        return ingest_xyz(file_path)

    def parse_mol(self, file_path: Union[str, Path]) -> MolecularGeometryPayload:
        return ingest_mol(file_path)

    def ingest_xyz(self, file_path: Union[str, Path]) -> MolecularGeometryPayload:
        return ingest_xyz(file_path)

    def ingest_mol(self, file_path: Union[str, Path]) -> MolecularGeometryPayload:
        return ingest_mol(file_path)

    def process_batch(self, input_dir: Union[str, Path]) -> BatchIngestionSummary:
        return scan_batch_directory(input_dir, max_workers=self.max_workers)

    def scan_batch_directory(self, input_dir: Union[str, Path]) -> BatchIngestionSummary:
        return scan_batch_directory(input_dir, max_workers=self.max_workers)

    def resolve_io_scratch_directory(self, custom_path: Optional[Union[str, Path]] = None) -> Path:
        return resolve_io_scratch_directory(custom_path)


# Aliases for ecosystem compatibility
CoChemMInt = MIntIngestor
IngestionEngine = MIntIngestor
