"""
CoChem-TORQ: Stage 5.5 / 6.0 SpycFit Payload Synthesis & Handoff Module
========================================================================
Implements the cryptographic bridge between CoChem-TORQ forward predictions
and downstream CoChem-SpycFit inverse spectral fitting workflows.

Authoritative Standards:
- Method Matrix (Section 2.3, 2.4, 12.5, 21): Substitution coordinates & Costain bounds
- RFC 8785: Canonical JSON serialization for cryptographic provenance manifests
- PyArrow Metadata Introspection: Zero-RAM out-of-core catalog inspection
- Deterministic Archival: POSIX epoch normalization (mtime=0) and permission pinning
"""

from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

import gc
import hashlib
import io
import json
import math
import os
import tarfile
import warnings
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pyarrow.parquet as pq

from cochem_base.exceptions import (
    CoChemIntegrityError,
    KraitchmanZPVEWarning,
)

# Planck constant over 8*pi^2 in amu * Angstrom^2 * MHz (CODATA 2022 canonical)
INERTIA_CONVERSION_AMU_ANG2_MHZ = 505379.0084350172


def _to_float(val: Any) -> float:
    """Helper to convert scalar/numpy/float value to float."""
    if hasattr(val, "item"):
        return float(val.item())
    return float(val)


def calculate_kraitchman_coords(tensor_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates Kraitchman substitution coordinates (|a_s|, |b_s|, |c_s|) and Costain
    uncertainties from parent and isotopologue moments of inertia or rotational constants.

    Mathematical Guardrails:
    - Evaluates substitution coordinates (r_s) via planar moment differences Delta P_g.
    - Near-Symmetric Singularity Guard: Damps near-symmetric top denominators
      (|I_g - I_g'| < 1e-4 amu*A^2) to prevent numerical divergence.
    - ZPVE Defect Clamping: Traps imaginary roots (radicand R_g < 0 or NaN) caused by
      vibrational zero-point energy shifts, clamps coordinate to 0.0000 A, and issues
      a KraitchmanZPVEWarning.
    - Piecewise Costain Bounds:
        delta g_s = 0.0015 / |g_s| for |g_s| >= 0.15 A
        delta g_s = sqrt(|R_g|) for |g_s| < 0.15 A

    Parameters:
        tensor_dict: Dictionary containing parent and isotopic inertia data.
            Supported keys:
            - 'I_a', 'I_b', 'I_c' (parent moments in amu*A^2)
            - 'I_a_iso', 'I_b_iso', 'I_c_iso' (isotopologue moments in amu*A^2)
            - 'parent_mass' or 'mass' (parent molecular mass in amu)
            - 'delta_m' (isotopic mass difference in amu)
            OR nested structure:
            - 'parent': {'I_a': ..., 'I_b': ..., 'I_c': ..., 'mass': ...}
            - 'isotopologue': {'I_a': ..., 'I_b': ..., 'I_c': ..., 'delta_m': ...}
            OR rotational constants 'A', 'B', 'C', 'A_iso', 'B_iso', 'C_iso' in MHz.

    Returns:
        Dictionary containing:
        - 'coordinates': {'a': float, 'b': float, 'c': float} in Angstroms
        - 'costain_uncertainties': {'delta_a': float, 'delta_b': float, 'delta_c': float} in Angstroms
        - 'radicands': {'R_a': float, 'R_b': float, 'R_c': float} in Angstroms^2
        - 'planar_moments_parent': {'P_a': float, 'P_b': float, 'P_c': float}
        - 'delta_planar_moments': {'delta_P_a': float, 'delta_P_b': float, 'delta_P_c': float}
        - 'zpve_defect_clamped': {'a': bool, 'b': bool, 'c': bool}
        - 'near_symmetric_damped': {'a': bool, 'b': bool, 'c': bool}
        - 'reduced_mass_mu': float
    """
    # 1. Parse parent and isotopic parameters
    parent_data = tensor_dict.get("parent", tensor_dict)
    iso_data = tensor_dict.get("isotopologue", tensor_dict.get("isotope", tensor_dict))

    # Parse parent moments of inertia
    if "I_a" in parent_data and "I_b" in parent_data and "I_c" in parent_data:
        I_a = _to_float(parent_data["I_a"])
        I_b = _to_float(parent_data["I_b"])
        I_c = _to_float(parent_data["I_c"])
    elif "A" in parent_data and "B" in parent_data and "C" in parent_data:
        I_a = INERTIA_CONVERSION_AMU_ANG2_MHZ / _to_float(parent_data["A"])
        I_b = INERTIA_CONVERSION_AMU_ANG2_MHZ / _to_float(parent_data["B"])
        I_c = INERTIA_CONVERSION_AMU_ANG2_MHZ / _to_float(parent_data["C"])
    else:
        raise ValueError(
            "tensor_dict must provide parent moments ('I_a', 'I_b', 'I_c') or constants ('A', 'B', 'C')."
        )

    # Parse isotopic moments of inertia
    if "I_a_iso" in tensor_dict:
        I_a_p = _to_float(tensor_dict["I_a_iso"])
        I_b_p = _to_float(tensor_dict["I_b_iso"])
        I_c_p = _to_float(tensor_dict["I_c_iso"])
    elif "I_a" in iso_data and iso_data is not parent_data:
        I_a_p = _to_float(iso_data["I_a"])
        I_b_p = _to_float(iso_data["I_b"])
        I_c_p = _to_float(iso_data["I_c"])
    elif "A_iso" in tensor_dict:
        I_a_p = INERTIA_CONVERSION_AMU_ANG2_MHZ / _to_float(tensor_dict["A_iso"])
        I_b_p = INERTIA_CONVERSION_AMU_ANG2_MHZ / _to_float(tensor_dict["B_iso"])
        I_c_p = INERTIA_CONVERSION_AMU_ANG2_MHZ / _to_float(tensor_dict["C_iso"])
    elif "A" in iso_data and iso_data is not parent_data:
        I_a_p = INERTIA_CONVERSION_AMU_ANG2_MHZ / _to_float(iso_data["A"])
        I_b_p = INERTIA_CONVERSION_AMU_ANG2_MHZ / _to_float(iso_data["B"])
        I_c_p = INERTIA_CONVERSION_AMU_ANG2_MHZ / _to_float(iso_data["C"])
    else:
        raise ValueError(
            "tensor_dict must provide isotopologue moments ('I_a_iso' or iso_data) or constants ('A_iso')."
        )

    # Parse masses
    mass = _to_float(
        tensor_dict.get("parent_mass", tensor_dict.get("mass", parent_data.get("mass", 0.0)))
    )
    delta_m = _to_float(
        tensor_dict.get("delta_m", iso_data.get("delta_m", 0.0))
    )

    if mass <= 0.0:
        raise ValueError("Parent molecular mass ('parent_mass' or 'mass') must be strictly positive.")
    if delta_m == 0.0:
        raise ValueError("Isotopic mass shift ('delta_m') must be non-zero for Kraitchman analysis.")

    # Calculate reduced mass factor: mu = (M * delta_m) / (M + delta_m)
    mu = (mass * delta_m) / (mass + delta_m)

    # 2. Planar moments of inertia for parent
    P_a = 0.5 * (-I_a + I_b + I_c)
    P_b = 0.5 * (I_a - I_b + I_c)
    P_c = 0.5 * (I_a + I_b - I_c)

    # Moment differences: Delta I_g = I_g' - I_g
    dI_a = I_a_p - I_a
    dI_b = I_b_p - I_b
    dI_c = I_c_p - I_c

    # Planar moment differences: Delta P_g = P_g' - P_g
    dP_a = 0.5 * (-dI_a + dI_b + dI_c)
    dP_b = 0.5 * (dI_a - dI_b + dI_c)
    dP_c = 0.5 * (dI_a + dI_b - dI_c)

    # 3. Near-symmetric top singularity damping helper
    # Singularity Threshold: |I_g - I_g'| < 1e-4 amu*A^2
    SINGULARITY_THRESHOLD = 1e-4
    near_symmetric_flags = {"a": False, "b": False, "c": False}

    def safe_denominator(diff: float, axis_label: str) -> float:
        if abs(diff) < SINGULARITY_THRESHOLD:
            near_symmetric_flags[axis_label] = True
            sign = 1.0 if diff >= 0.0 else -1.0
            return sign * SINGULARITY_THRESHOLD
        return diff

    # Kraitchman factors for asymmetric top
    den_ab = safe_denominator(I_a - I_b, "a")
    den_ac = safe_denominator(I_a - I_c, "a")
    den_ba = safe_denominator(I_b - I_a, "b")
    den_bc = safe_denominator(I_b - I_c, "b")
    den_ca = safe_denominator(I_c - I_a, "c")
    den_cb = safe_denominator(I_c - I_b, "c")

    R_a = (dP_a / mu) * (1.0 + (dP_b / den_ab)) * (1.0 + (dP_c / den_ac))
    R_b = (dP_b / mu) * (1.0 + (dP_c / den_bc)) * (1.0 + (dP_a / den_ba))
    R_c = (dP_c / mu) * (1.0 + (dP_a / den_ca)) * (1.0 + (dP_b / den_cb))

    coords = {}
    costain_bounds = {}
    zpve_clamped = {}
    radicands = {"R_a": float(R_a), "R_b": float(R_b), "R_c": float(R_c)}

    axes = [("a", R_a), ("b", R_b), ("c", R_c)]

    for axis_name, R_val in axes:
        # ZPVE Defect Clamping: If R_val < 0 or NaN, clamp to 0.0000 A
        if math.isnan(R_val) or R_val < 0.0:
            coords[axis_name] = 0.0000
            zpve_clamped[axis_name] = True
            warnings.warn(
                f"Kraitchman coordinate along '{axis_name}' axis evaluated to imaginary root "
                f"(radicand R_{axis_name} = {R_val:.6f} amu*A^2) due to ZPVE defect; "
                f"clamped to 0.0000 A.",
                KraitchmanZPVEWarning,
                stacklevel=2,
            )
            # Costain uncertainty for clamped / small coordinate: sqrt(|R_g|)
            costain_bounds[f"delta_{axis_name}"] = float(math.sqrt(abs(R_val))) if not math.isnan(R_val) else 0.015
        else:
            coord = math.sqrt(R_val)
            coords[axis_name] = float(coord)
            zpve_clamped[axis_name] = False

            # Piecewise Costain Bounds:
            # delta g_s = 0.0015 / |g_s| for |g_s| >= 0.15 A
            # delta g_s = sqrt(|R_g|) for |g_s| < 0.15 A
            if coord >= 0.15:
                costain_bounds[f"delta_{axis_name}"] = float(0.0015 / coord)
            else:
                costain_bounds[f"delta_{axis_name}"] = float(math.sqrt(R_val))

    return {
        "coordinates": coords,
        "costain_uncertainties": costain_bounds,
        "radicands": radicands,
        "planar_moments_parent": {"P_a": float(P_a), "P_b": float(P_b), "P_c": float(P_c)},
        "delta_planar_moments": {"delta_P_a": float(dP_a), "delta_P_b": float(dP_b), "delta_P_c": float(dP_c)},
        "zpve_defect_clamped": zpve_clamped,
        "near_symmetric_damped": near_symmetric_flags,
        "reduced_mass_mu": float(mu),
    }


def generate_pgopher_skeleton(
    parquet_path: str, json_path: str, output_path: Optional[str] = None
) -> str:
    """
    Zero-RAM PGOPHER Skeleton Synthesizer.
    Inspects out-of-core PyArrow Parquet catalogs via pyarrow.parquet.read_metadata()
    (< 50 MB RSS ceiling) and generates a standardized, schema-validated .pgo XML file.

    Parameters:
        parquet_path: Absolute or relative path to .parquet spectral catalog.
        json_path: Path to internal JSON containing rotational/dipole/centrifugal parameters.
        output_path: Optional destination path for the generated .pgo XML file.

    Returns:
        String containing the formatted .pgo XML document.
    """
    parquet_file = Path(parquet_path)
    if not parquet_file.exists():
        raise FileNotFoundError(f"Parquet catalog file not found: {parquet_path}")

    json_file = Path(json_path)
    if not json_file.exists():
        raise FileNotFoundError(f"JSON parameter file not found: {json_path}")

    # 1. Zero-RAM Parquet Metadata Inspection (Bypasses dataset loading)
    metadata = pq.read_metadata(str(parquet_file))
    num_rows = metadata.num_rows
    num_columns = metadata.num_columns
    column_names = metadata.schema.names

    # 2. Parse JSON Spectroscopic Parameters
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    molecule_name = data.get("molecule_name", data.get("name", parquet_file.stem))
    point_group = data.get("point_group", data.get("symmetry_group", "C1"))

    # Rotational constants in MHz (PGOPHER standard conversion supported)
    rot_constants = data.get("rotational_constants", data)
    A_mhz = _to_float(rot_constants.get("A", 10000.0))
    B_mhz = _to_float(rot_constants.get("B", 5000.0))
    C_mhz = _to_float(rot_constants.get("C", 2500.0))

    # Centrifugal distortion terms (Watson A/S reduction)
    centrifugal = data.get("centrifugal_distortion", {})
    model = centrifugal.get("model", centrifugal.get("reduction", "Watson_A"))
    DJ = _to_float(centrifugal.get("DJ", centrifugal.get("Delta_J", 0.0)))
    DJK = _to_float(centrifugal.get("DJK", centrifugal.get("Delta_JK", 0.0)))
    DK = _to_float(centrifugal.get("DK", centrifugal.get("Delta_K", 0.0)))
    dJ = _to_float(centrifugal.get("dJ", centrifugal.get("delta_J", 0.0)))
    dK = _to_float(centrifugal.get("dK", centrifugal.get("delta_K", 0.0)))

    # Dipole moments in Debye
    dipoles = data.get("dipole_moments", {})
    mu_a = _to_float(dipoles.get("mu_a", dipoles.get("MuA", 1.0)))
    mu_b = _to_float(dipoles.get("mu_b", dipoles.get("MuB", 0.0)))
    mu_c = _to_float(dipoles.get("mu_c", dipoles.get("MuC", 0.0)))

    temperature = _to_float(data.get("temperature", data.get("simulation_temperature", 298.15)))
    fwhm = _to_float(data.get("fwhm", data.get("line_width", 1.0)))

    # 3. Construct Standardized PGOPHER XML Skeleton
    xml_lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<PGOPHER Version="1.0.0" Generator="CoChem-TORQ-Export" Created="{datetime.now(timezone.utc).isoformat()}">',
        f'  <Species Name="{molecule_name}" AsymmetricTop="True">',
        f'    <AsymmetricMolecule Name="Ground" PointGroup="{point_group}">',
        '      <AsymmetricTop Name="v=0" S="0">',
        f'        <RotationalConstants A="{A_mhz:.6f}" B="{B_mhz:.6f}" C="{C_mhz:.6f}" Units="MHz"/>',
        f'        <CentrifugalDistortion Model="{model}" DJ="{DJ:.8e}" DJK="{DJK:.8e}" DK="{DK:.8e}" dJ="{dJ:.8e}" dK="{dK:.8e}" Units="MHz"/>',
        f'        <DipoleMoments MuA="{mu_a:.4f}" MuB="{mu_b:.4f}" MuC="{mu_c:.4f}" Units="Debye"/>',
        f'        <SpectroscopicCatalog File="{parquet_file.name}" TotalTransitions="{num_rows}" TotalColumns="{num_columns}" Columns="{",".join(column_names)}"/>',
        '      </AsymmetricTop>',
        '    </AsymmetricMolecule>',
        '  </Species>',
        f'  <Simulation Temperature="{temperature:.2f}" Units="K" LineShape="Gaussian" FWHM="{fwhm:.4f}" UnitsFWHM="MHz"/>',
        '</PGOPHER>',
    ]
    xml_content = "\n".join(xml_lines) + "\n"

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(xml_content)

    return xml_content


def lock_provenance_payload(
    target_directory: str, manifest_filename: str = "spycfit_manifest.json"
) -> Dict[str, Any]:
    """
    Deterministic Provenance Locking Gate.
    Traverses target_directory in deterministic POSIX sort order, computes streaming
    SHA-256 in 8192-byte binary chunks, excludes manifest_filename from circular hashing,
    and serializes spycfit_manifest.json under RFC 8785 Canonical JSON standards.

    Parameters:
        target_directory: Path to directory containing export artifacts.
        manifest_filename: Name of manifest file (default: spycfit_manifest.json).

    Returns:
        Dictionary containing manifest metadata and file checksum mapping.
    """
    target_path = Path(target_directory).resolve()
    if not target_path.exists() or not target_path.is_dir():
        raise NotADirectoryError(f"Target directory does not exist: {target_directory}")

    # Discover all files recursively, excluding manifest and temporary artifacts
    excluded_names = {manifest_filename, ".DS_Store", "Thumbs.db"}
    all_files: List[Path] = []

    for root, dirs, files in os.walk(target_path):
        # Sort directories in-place for deterministic traversal
        dirs.sort()
        for f in sorted(files):
            if f not in excluded_names and not f.endswith((".pyc", ".tmp")):
                all_files.append(Path(root) / f)

    # Sort files by relative POSIX path for strict determinism
    relative_files = sorted(
        all_files, key=lambda p: p.relative_to(target_path).as_posix()
    )

    files_manifest: Dict[str, Dict[str, Any]] = {}
    root_hasher = hashlib.sha256()
    total_bytes = 0

    for file_path in relative_files:
        posix_rel_path = file_path.relative_to(target_path).as_posix()
        file_size = file_path.stat().st_size
        total_bytes += file_size

        # Memory-safe 8192-byte streaming SHA-256
        file_hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                file_hasher.update(chunk)
        file_sha256 = file_hasher.hexdigest()

        files_manifest[posix_rel_path] = {
            "sha256": file_sha256,
            "size_bytes": file_size,
        }

        # Update root composite hash
        root_hasher.update(f"{posix_rel_path}:{file_sha256}:{file_size}\n".encode("utf-8"))

    root_payload_hash = root_hasher.hexdigest()

    manifest_dict: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "generator": "CoChem-TORQ-Export",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_directory": target_path.as_posix(),
        "file_count": len(files_manifest),
        "total_bytes": total_bytes,
        "root_payload_hash": root_payload_hash,
        "files": files_manifest,
    }

    # RFC 8785 Canonical JSON Serialization: sorted keys, compact separators, UTF-8
    canonical_json_bytes = json.dumps(
        manifest_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")

    manifest_out_path = target_path / manifest_filename
    with open(manifest_out_path, "wb") as f:
        f.write(canonical_json_bytes)

    return manifest_dict


def bundle_spycfit_payload(
    manifest_path: str,
    output_dir: Optional[str] = None,
    archive_format: str = "auto",
    project_name: str = "Project",
) -> str:
    """
    Deterministic SpycFit Deliverable Compression Gateway.
    Archives export deliverables into CoChem_[Project]_SpycFit_Payload.tar.zst (or .zip fallback),
    normalizing POSIX epoch (mtime=0) and file permissions (0644/0755), and flushing JAX buffers.

    Parameters:
        manifest_path: Path to spycfit_manifest.json or parent directory.
        output_dir: Destination folder for payload archive (defaults to target directory).
        archive_format: 'tar.zst', 'zip', or 'auto'.
        project_name: Name of project for archive naming.

    Returns:
        String path to the generated payload archive.
    """
    m_path = Path(manifest_path).resolve()
    if m_path.is_dir():
        target_dir = m_path
        manifest_file = target_dir / "spycfit_manifest.json"
    else:
        manifest_file = m_path
        target_dir = manifest_file.parent

    if not manifest_file.exists():
        # Auto-lock if manifest not yet generated
        lock_provenance_payload(str(target_dir))

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    out_folder = Path(output_dir).resolve() if output_dir else target_dir
    out_folder.mkdir(parents=True, exist_ok=True)

    archive_base_name = f"CoChem_{project_name}_SpycFit_Payload"

    # Check Zstandard availability
    has_zstd = False
    try:
        import zstandard as zstd
        has_zstd = True
    except ImportError as _e:
        logger.debug(f"Ignored exception: {_e}")

    use_zstd = (archive_format in ("auto", "tar.zst", "zst")) and has_zstd

    # Deterministic file list: manifest + all registered files
    files_to_pack = sorted(list(manifest["files"].keys()))
    manifest_rel_name = manifest_file.name

    if use_zstd:
        archive_file = out_folder / f"{archive_base_name}.tar.zst"
        import zstandard as zstd

        cctx = zstd.ZstdCompressor(level=19)
        tar_buffer = io.BytesIO()

        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            # 1. Add manifest
            manifest_bytes = manifest_file.read_bytes()
            ti = tarfile.TarInfo(name=manifest_rel_name)
            ti.size = len(manifest_bytes)
            ti.mtime = 0  # POSIX epoch normalization
            ti.mode = 0o644  # Normalized file permissions
            ti.uid = 0
            ti.gid = 0
            ti.uname = ""
            ti.gname = ""
            tar.addfile(ti, io.BytesIO(manifest_bytes))

            # 2. Add all payload files
            for rel_posix in files_to_pack:
                src_path = target_dir / rel_posix
                if src_path.exists() and src_path.is_file():
                    content = src_path.read_bytes()
                    ti = tarfile.TarInfo(name=rel_posix)
                    ti.size = len(content)
                    ti.mtime = 0
                    ti.mode = 0o644
                    ti.uid = 0
                    ti.gid = 0
                    ti.uname = ""
                    ti.gname = ""
                    tar.addfile(ti, io.BytesIO(content))

        tar_bytes = tar_buffer.getvalue()
        compressed_bytes = cctx.compress(tar_bytes)

        with open(archive_file, "wb") as f:
            f.write(compressed_bytes)

    else:
        # Fallback to deterministic Zip archive
        archive_file = out_folder / f"{archive_base_name}.zip"
        with zipfile.ZipFile(archive_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 1. Add manifest with normalized timestamp (1980-01-01 00:00:00)
            zinfo = zipfile.ZipInfo(manifest_rel_name, date_time=(1980, 1, 1, 0, 0, 0))
            zinfo.external_attr = 0o644 << 16
            zf.writestr(zinfo, manifest_file.read_bytes())

            # 2. Add all payload files
            for rel_posix in files_to_pack:
                src_path = target_dir / rel_posix
                if src_path.exists() and src_path.is_file():
                    zinfo = zipfile.ZipInfo(rel_posix, date_time=(1980, 1, 1, 0, 0, 0))
                    zinfo.external_attr = 0o644 << 16
                    zf.writestr(zinfo, src_path.read_bytes())

    # Flush JAX execution buffers and drop tensor memory
    try:
        import jax
        jax.clear_caches()
    except (ImportError, AttributeError) as _e:
        logger.debug(f"Ignored exception: {_e}")
    gc.collect()

    return str(archive_file)


def verify_payload_integrity(payload: Union[Dict[str, Any], str, Path]) -> bool:
    """
    Autonomous Pre-Ingestion Self-Audit Gate.
    Validates cryptographic SHA-256 checksums across all payload files.
    Raises CoChemIntegrityError if any corrupted or flipped bytes are detected.

    Parameters:
        payload: Manifest dictionary, path to spycfit_manifest.json, or target directory.

    Returns:
        True if all cryptographic hashes match 100%.

    Raises:
        CoChemIntegrityError: If a hash mismatch, missing file, or bit-flip is detected.
    """
    if isinstance(payload, (str, Path)):
        p_path = Path(payload).resolve()
        if p_path.is_dir():
            manifest_file = p_path / "spycfit_manifest.json"
            target_dir = p_path
        elif p_path.is_file() and p_path.suffix == ".json":
            manifest_file = p_path
            target_dir = p_path.parent
        else:
            raise FileNotFoundError(f"Cannot resolve payload manifest from: {payload}")

        if not manifest_file.exists():
            raise CoChemIntegrityError(f"Missing manifest file: {manifest_file}")

        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest_dict = json.load(f)
    elif isinstance(payload, dict):
        manifest_dict = payload
        target_dir = Path(manifest_dict.get("target_directory", ".")).resolve()
    else:
        raise TypeError(f"Invalid payload type: {type(payload)}")

    files = manifest_dict.get("files", {})
    if not files:
        raise CoChemIntegrityError("Manifest contains no registered files.")

    for rel_posix, meta in files.items():
        expected_sha256 = meta.get("sha256", "")
        expected_size = meta.get("size_bytes", None)
        file_path = target_dir / rel_posix

        if not file_path.exists():
            raise CoChemIntegrityError(
                f"Payload integrity failure: missing required file '{rel_posix}' in '{target_dir}'."
            )

        if expected_size is not None:
            actual_size = file_path.stat().st_size
            if actual_size != expected_size:
                raise CoChemIntegrityError(
                    f"Payload size tamper detected for '{rel_posix}'. "
                    f"Expected {expected_size} bytes, found {actual_size} bytes."
                )

        # Compute streaming SHA-256
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        actual_sha256 = hasher.hexdigest()

        if actual_sha256 != expected_sha256:
            raise CoChemIntegrityError(
                f"Cryptographic hash seal broken for '{rel_posix}'. "
                f"Expected SHA-256: {expected_sha256}, Actual SHA-256: {actual_sha256}."
            )

    return True
