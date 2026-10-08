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
import logging
logger = logging.getLogger(__name__)

import concurrent.futures
import functools
import math
import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from cochem_base.config_loader import load_system_config


class CoChemIngestionError(Exception):
    """Exception raised for errors in the ingestion pipeline."""
    def __init__(self, message: str) -> None:
        super().__init__(message)


class AtomMetadata(BaseModel):
    """Metadata container for individual atomic centers."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    symbol: str
    nuclide: str
    mass_number: Optional[int] = None
    atomic_number: int
    monoisotopic_mass: float
    covalent_radius: float
    vdw_radius: float
    x: float
    y: float
    z: float


class MolecularGeometryPayload(BaseModel):
    """Standardized immutable molecular geometry payload with auxiliary tensors."""
    model_config = ConfigDict(frozen=True, extra="forbid")
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
    net_charge: Optional[int] = None
    multiplicity: Optional[int] = None
    record_index: int = 0
    nuclides: List[str]
    mass_numbers: List[Optional[int]]
    electronic_state_source: str = "user_selection_required"
    source_metadata: Dict[str, Any] = Field(default_factory=dict)

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
    successful_files: int = 0
    duplicate_files: int = 0
    errors: Dict[str, str] = Field(default_factory=dict)


@functools.lru_cache(maxsize=4096)
def get_element_data(symbol: str) -> Dict[str, Any]:
    """Resolve exact labelled or most abundant isotope metadata dynamically."""
    from cochem_base.physics.isotopes import parse_nuclide_token, get_isotope_mass
    from cochem_base.physics.nuclide_resolver import get_element
    clean_sym, number = parse_nuclide_token(symbol)
    if clean_sym.upper() in {"GH", "BQ", "X"}:
        return {"symbol": "Gh", "nuclide": "Gh", "mass_number": None,
                "atomic_number": 0, "monoisotopic_mass": 0.0,
                "covalent_radius": 0.0, "vdw_radius": 0.0}
    elem = get_element(clean_sym)
    if number is None:
        measured = [iso for iso in elem.isotopes if iso.mass is not None and iso.abundance is not None and iso.abundance > 0]
        if not measured:
            raise ValueError(f"No naturally abundant isotope for {clean_sym}; choose an explicit physical isotope")
        number = int(max(measured, key=lambda iso: (iso.abundance, -iso.mass_number)).mass_number)
    mass = get_isotope_mass(clean_sym, number)
    # Mendeleev radii are picometres; never guess units from their magnitude.
    cov = elem.covalent_radius_pyykko or elem.covalent_radius
    vdw = elem.vdw_radius
    if cov is None or vdw is None or not math.isfinite(float(cov)) or not math.isfinite(float(vdw)):
        raise ValueError(f"Mendeleev lacks required physical radii for {clean_sym}")
    return {"symbol": elem.symbol, "nuclide": f"{number}{elem.symbol}", "mass_number": number,
            "atomic_number": int(elem.atomic_number), "monoisotopic_mass": mass,
            "covalent_radius": float(cov) / 100.0, "vdw_radius": float(vdw) / 100.0}


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


def _payload(record: dict, *, filename: str, format: str, digest: str) -> MolecularGeometryPayload:
    atoms = []
    for label, coordinates in zip(record["symbols"], record["coords"], strict=True):
        data = get_element_data(label)
        atoms.append(AtomMetadata(**data, x=float(coordinates[0]), y=float(coordinates[1]), z=float(coordinates[2])))
    return MolecularGeometryPayload(
        filename=filename, format=format, sha256_hash=digest,
        symbols=[a.symbol for a in atoms], nuclides=[a.nuclide for a in atoms],
        mass_numbers=[a.mass_number for a in atoms],
        coordinates=record["coords"].tolist(), total_atoms=len(atoms),
        M_aux=[a.monoisotopic_mass for a in atoms], Z_aux=[a.atomic_number for a in atoms],
        R_cov_aux=[a.covalent_radius for a in atoms], R_vdw_aux=[a.vdw_radius for a in atoms],
        atoms=atoms, comment=record["comment"], net_charge=record.get("charge"),
        multiplicity=record.get("multiplicity"), record_index=record.get("record_index", 0),
        electronic_state_source=record.get("electronic_state_source", "user_selection_required"),
        source_metadata={k: v for k, v in record.items() if k not in {"coords", "symbols", "elements", "nuclear_identity"}},
    )


def ingest_string_records(content: str, format: str, filename: str) -> List[MolecularGeometryPayload]:
    """Preserve all molecular records instead of selecting the first silently."""
    from cochem_base.intake.structure_formats import parse_structure_text
    records = parse_structure_text(content, format)
    digest = compute_sha256(content)
    return [_payload(dict(record, record_index=index), filename=filename, format=format, digest=digest)
            for index, record in enumerate(records)]


def ingest_string(content: str, format: str, filename: str) -> MolecularGeometryPayload:
    """Single-record compatibility boundary; ensembles require the batch API."""
    payloads = ingest_string_records(content, format, filename)
    if len(payloads) != 1:
        raise ValueError("This input contains multiple records; use ingest_records to retain the complete ensemble")
    return payloads[0]


def ingest_records(file_path: Union[str, Path]) -> List[MolecularGeometryPayload]:
    """Read every record and bind it to the exact original file-byte digest."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    raw = path.read_bytes()
    digest = compute_sha256(raw)
    payloads = ingest_string_records(raw.decode("utf-8-sig", errors="strict"), path.suffix.lstrip("."), path.name)
    if compute_sha256(path.read_bytes()) != digest:
        raise ValueError("Molecular source changed during ingestion")
    return [payload.model_copy(update={"sha256_hash": digest}) for payload in payloads]


def ingest_file(file_path: Union[str, Path]) -> MolecularGeometryPayload:
    """Single-record compatibility interface for every supported source format."""
    payloads = ingest_records(file_path)
    if len(payloads) != 1:
        raise ValueError("This input contains multiple records; use ingest_records to retain the complete ensemble")
    return payloads[0]


def ingest_xyz(file_path: Union[str, Path]) -> MolecularGeometryPayload:
    return ingest_file(file_path)


def ingest_mol(file_path: Union[str, Path]) -> MolecularGeometryPayload:
    return ingest_file(file_path)


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

    from cochem_base.intake.structure_formats import FORMATS
    files_to_process: List[Path] = []
    iterator = path.rglob("*") if recursive else path.iterdir()
    for item in iterator:
        if item.is_file() and item.suffix.lower().lstrip(".") in FORMATS:
            files_to_process.append(item)

    files_to_process.sort(key=lambda p: p.name)

    payloads: List[MolecularGeometryPayload] = []
    sha256_registry: List[str] = []
    seen_hashes = set()
    errors: Dict[str, str] = {}
    successful_files = duplicate_files = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [(source, executor.submit(ingest_records, source)) for source in files_to_process]
        for source, future in futures:
            try:
                records = future.result()
                digest = records[0].sha256_hash
                successful_files += 1
                if digest in seen_hashes:
                    duplicate_files += 1
                    continue
                seen_hashes.add(digest)
                payloads.extend(records)
                sha256_registry.append(digest)
            except Exception as error:
                errors[str(source.relative_to(path))] = f"{type(error).__name__}: {error}"

    return BatchIngestionSummary(
        input_directory=str(path), total_files_scanned=len(files_to_process),
        successful_ingestions=len(payloads), failed_ingestions=len(errors),
        successful_files=successful_files, duplicate_files=duplicate_files, errors=errors,
        payloads=payloads, sha256_registry=sha256_registry, valid_graphs=payloads,
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
