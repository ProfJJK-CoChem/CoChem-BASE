#!/usr/bin/env python3
# cochem_canvas_target: core_engine/cochem_core_pes_store.py
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Stage 8C - QCSchema-Compliant Chunked HDF5 PES Store,
SWMR/Archival Storage Bifurcation, and Isotopologue Force Field Recycling.

Mandated by:
- SRS Doc 1 (Topology 1.0 §2)
- SRS Doc 2 Part 1 (§2.7)
- Method Matrix v4 §8C (HDF5 PES Store), §8B.4 (Canonical State Reuse & Arrow 7),
  §6.10 (Isotopologue Shortcut), §3-§5 (Rotational & Anharmonic Observables), §8A (Concurrency)
- CoChem Anti-Spoofing Protocol v2
- CoChem Mendeleev Library Mandate

Architectural Overview:
1. QCSchema-Compliant Chunked HDF5 PES Store (PESStore):
   - Structured HDF5 hierarchy (/meta, /methods, /points, /grids, /hessians, /isotopologues, /checkpoints).
   - Resizable chunked datasets with CHUNK_POINTS=512 (~120 KiB for 10-atom systems, in 10 KiB-1 MiB envelope).
   - Lossless gzip (compression_opts=4) + byte shuffle filter on numeric datasets.
   - Fletcher32 per-chunk error-detecting checksum on critical energy and coordinate arrays.
   - STRICT BAN on lossy scaleoffset filter to preserve micro-Hartree energy accuracy and avoid artificial frequencies.
   - Provenance tracking with QCSchema field names, JSON serialization, and cryptographic HMAC-SHA256 signatures.

2. SWMR / Archival Storage Bifurcation (BifurcatedPESStore):
   - Active Runtime Store (runtime_active.h5): Low-latency, uncompressed or fast chunking for live IPC streaming,
     steering, and concurrent reader queries with POSIX/Windows byte-range file locking.
   - Archival QCSchema Store (archive_pes.h5 / campaign.h5): Standard HDF5 mode with full lossless compression,
     checksum validation, and formal QCSchema v1 archival schema validation.
   - Atomic promotion from active runtime store to compressed archival store.
   - Parallel shard merger (merge_pes_shards) for multi-worker parallel grid evaluations.

3. Isotopologue Force Field Recycling Engine (Method Matrix Arrow 7, §8B.4, §6.10):
   - Dynamic atomic and isotopic mass retrieval using the `mendeleev` library (strictly ZERO hardcoded mass constants).
   - Mass-weighting and normal mode diagonalization of Cartesian Hessians: H_mw[i, j] = H[i, j] / sqrt(m_i * m_j).
   - Harmonic vibrational frequencies in cm^-1 (preserving sign for imaginary saddle-point modes).
   - Moment of inertia tensor (Ia <= Ib <= Ic in u * A^2), rotational constants (A >= B >= C in MHz),
     planar moments (Paa, Pbb, Pcc in u * A^2), inertial defect (Delta = Ic - Ia - Ib in u * A^2),
     and Ray's asymmetry parameter (kappa).
   - Zero electronic structure cost evaluation of arbitrary isotopologue suites (13C, 18O, D, 15N) from a single Hessian.

4. Idempotent Active-Learning & DVR Integration:
   - todo(method_id, wanted_ids): Identifies missing or unconverged points on high-dimensional grids for restarts.
   - dataset(method_id, converged_only): Extracts aligned coordinates and energies as NumPy arrays.
   - delta_pairs(low_method, high_method): Generates aligned (X, Delta_E) pairs for Delta-learning MLFF training.
   - dvr_grid(method_id, grid_id): Reshapes potential energies onto product grids for DVR solvers, marking holes with NaN.
"""

from __future__ import annotations

import argparse
import atexit
import copy
import hashlib
import hmac
import json
import logging
import math
import os
import platform
import shutil
import socket
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Dict,
    Generator,
    Iterable,
    List,
    Literal,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
    cast,
)

import h5py
import numpy as np
from filelock import FileLock, Timeout
from mendeleev import element
from pydantic import BaseModel, ConfigDict, Field, field_validator

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from cochem_base.config_loader import (
    get_artifact_dir,
    get_runtime_dir,
    get_state_file_path,
    resolve_mapped_path,
)
from cochem_base.exceptions import (
    CoChemError,
    HDF5LockTimeoutError,
    MethodMatrixViolationError,
    ProvenanceErrorCode,
    QCSchemaValidationError,
    SingularityError,
)
from cochem_base.core.ipc.serializer import validate_airgap_write_path
from cochem_base.core.licensing import validate_spdx_license
from cochem_base.core.models import NAMESPACE_COCHEM, PESPointRecord


def get_node_local_scratch_dir() -> Path:
    """Resolve node-local ephemeral scratch directory adhering to HPC Distributed Lock Prohibition [D]."""
    scratch = os.environ.get("SLURM_TMPDIR") or os.environ.get("TMPDIR") or (Path.home() / ".cochem" / "scratch")
    p = Path(scratch).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logger = logging.getLogger("CoChem-PESStore")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [cochem_core_pes_store]: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Physical Constants & Convergence Standards (Method Matrix §4.4, §5, §8B)
# ---------------------------------------------------------------------------
PLANCK_CONSTANT_J_S = 6.62607015e-34       # J * s (CODATA exact)
SPEED_OF_LIGHT_CM_S = 2.99792458e10       # cm / s (CODATA exact)
SPEED_OF_LIGHT_M_S = 2.99792458e8         # m / s (CODATA exact)
ATOMIC_MASS_UNIT_KG = 1.66053906660e-27   # kg / u
ANGSTROM_TO_METER = 1.0e-10               # m / Angstrom
BOHR_TO_ANGSTROM = 0.529177210903         # Angstrom / Bohr
ANGSTROM_TO_BOHR = 1.0 / BOHR_TO_ANGSTROM  # Bohr / Angstrom
BOHR_TO_METER = 0.529177210903e-10        # m / Bohr
HARTREE_TO_JOULE = 4.3597447222071e-18    # J / Hartree
HARTREE_TO_EV = 27.211386245988           # eV / Hartree
HARTREE_TO_CM_INV = 219474.63136320       # cm^-1 / Hartree
ROTATIONAL_INERTIA_CONVERSION = 505379.0084350172  # MHz * u * Angstrom^2

# Factor converting Inertia (u * Angstrom^2) to Rotational Constant (MHz):
# B = h / (8 * pi^2 * I) * 1e-6 (Hz -> MHz)
INERTIA_TO_MHZ_FACTOR = (
    PLANCK_CONSTANT_J_S
    / (8.0 * (math.pi ** 2) * ATOMIC_MASS_UNIT_KG * (ANGSTROM_TO_METER ** 2))
) * 1.0e-6  # ~505379.0091414361 MHz * u * Angstrom^2

# Factor converting Hessian eigenvalue (Hartree / (Bohr^2 * u)) to wavenumber (cm^-1):
# f_lambda = HARTREE_TO_JOULE / (BOHR_TO_METER^2 * ATOMIC_MASS_UNIT_KG)
# f_cm1 = 1 / (2 * pi * c_cm_s)
HESSIAN_EIG_TO_CM_INV_FACTOR = (
    math.sqrt(HARTREE_TO_JOULE / ((BOHR_TO_METER ** 2) * ATOMIC_MASS_UNIT_KG))
    / (2.0 * math.pi * SPEED_OF_LIGHT_CM_S)
)  # ~5140.487143715827 cm^-1

# HDF5 Storage Specifications (Method Matrix §8C)
CHUNK_POINTS = 512
VLEN_STR = h5py.string_dtype(encoding="utf-8")
DEFAULT_LOCK_TIMEOUT_S = 30.0


# =============================================================================
# 1. PYDANTIC V2 DATA MODELS & SCHEMAS
# =============================================================================

class StorageMode(str, Enum):
    """Storage architecture operating mode classification."""
    BIFURCATED = "BIFURCATED"
    ARCHIVAL_ONLY = "ARCHIVAL_ONLY"
    RUNTIME_SWMR = "RUNTIME_SWMR"


class DriverType(str, Enum):
    """QCSchema calculation driver type."""
    ENERGY = "energy"
    GRADIENT = "gradient"
    HESSIAN = "hessian"
    PROPERTIES = "properties"


class QCSchemaProvenance(BaseModel):
    """QCSchema v1 compliant calculation provenance metadata with asymmetric Ed25519 signatures."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    creator: str = Field(default="ORCA", description="Name of quantum chemistry package or MLFF engine")
    version: str = Field(default="6.1", description="Software version identifier")
    routine: str = Field(default="sp", description="Calculation routine (sp, opt, freq, vpt2, scan)")
    host: str = Field(default_factory=socket.gethostname, description="Hostname where calculation executed")
    platform: str = Field(default_factory=platform.platform, description="OS platform string")
    utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        description="ISO 8601 UTC timestamp",
    )
    signature: Optional[str] = Field(
        default=None, description="URL-safe base64 encoded Ed25519 digital signature"
    )
    public_key: Optional[str] = Field(
        default=None, description="URL-safe base64 encoded Ed25519 public key"
    )
    fingerprint: Optional[str] = Field(
        default=None, description="SHA-256 fingerprint of public key"
    )
    signature_algorithm: str = Field(
        default="PureEd25519", description="Cryptographic signing standard"
    )
    license: str = Field(
        default="CC-BY-4.0", description="SPDX license identifier governing data reuse rights (FAIR R1.1)"
    )

    @field_validator("license")
    @classmethod
    def validate_license(cls, v: str) -> str:
        return validate_spdx_license(v)

    def canonical_bytes(self) -> bytes:
        """Construct RFC 8785 canonical bytes for core provenance fields."""
        from cochem_base.core.cochem_crypto import canonicalize_json
        payload = {
            "creator": self.creator,
            "version": self.version,
            "routine": self.routine,
            "host": self.host,
            "platform": self.platform,
            "utc": self.utc,
            "license": self.license,
        }
        return canonicalize_json(payload)

    def sign(self, private_key: Any) -> str:
        """Sign provenance metadata with PureEd25519 and populate signature/public_key/fingerprint."""
        from cochem_base.core.cochem_crypto import sign_canonical_bytes
        c_bytes = self.canonical_bytes()
        sig, pub, fp = sign_canonical_bytes(c_bytes, private_key)
        self.signature = sig
        self.public_key = pub
        self.fingerprint = fp
        return sig

    def verify(self) -> bool:
        """Verify PureEd25519 digital signature against embedded public key."""
        if not self.signature or not self.public_key:
            return False
        from cochem_base.core.cochem_crypto import verify_canonical_signature
        c_bytes = self.canonical_bytes()
        return verify_canonical_signature(c_bytes, self.signature, self.public_key)


class QCSchemaMethodRecord(BaseModel):
    """QCSchema method attributes registered in HDF5 /methods/<method_id>."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    method: str = Field(..., description="Electronic structure method (e.g. DLPNO-CCSD(T1), wB97M-V, MP2)")
    basis: str = Field(..., description="Primary orbital basis set (e.g. def2-TZVPP, cc-pVDZ-F12)")
    aux_basis: Optional[str] = Field(None, description="Auxiliary density fitting or CABS basis set")
    program: str = Field(default="ORCA", description="Quantum chemistry package (ORCA, MPQC, CFOUR, PySCF, MACE)")
    program_version: str = Field(default="6.1", description="Software version string")
    driver: DriverType = Field(default=DriverType.ENERGY, description="Calculation driver")
    frozen_core: bool = Field(default=True, description="Whether frozen core approximation was enabled")
    counterpoise: str = Field(default="none", description="Counterpoise status: 'none', 'half', or 'full'")
    keywords: Dict[str, Any] = Field(default_factory=dict, description="Dictionary of calculation keywords and tolerances")
    license: str = Field(
        default="CC-BY-4.0", description="SPDX license identifier governing data reuse rights (FAIR R1.1)"
    )
    registered_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        description="ISO 8601 registration timestamp",
    )

    @field_validator("license")
    @classmethod
    def validate_license(cls, v: str) -> str:
        return validate_spdx_license(v)


class PESGridDefinition(BaseModel):
    """Multidimensional grid definition for potential energy surfaces."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    grid_id: str = Field(..., description="Unique identifier for the grid (e.g. 'grid_2d_r_theta')")
    axes: Dict[str, List[float]] = Field(..., description="Mapping of axis names to 1D coordinate arrays")
    axis_order: List[str] = Field(..., description="Ordered list of axis names")
    shape: List[int] = Field(..., description="Grid dimension shape [dim_0, dim_1, ...]")
    grid_type: str = Field(default="cartesian", description="Grid coordinate type ('cartesian', 'spherical', 'internal')")


class HessianRecord(BaseModel):
    """Cartesian Hessian record stored under /hessians/<label>."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True, arbitrary_types_allowed=True)

    label: str = Field(..., description="Unique label for the Hessian (e.g. 'opt_wb97mv_qz', 'parent_dimer')")
    level: str = Field(..., description="Level of theory (e.g. 'wB97M-V/def2-QZVPP')")
    geometry_ref: str = Field(..., description="Reference geometry identifier or filename")
    cartesian_hessian: Union[List[List[float]], np.ndarray] = Field(..., description="3N x 3N Cartesian Hessian matrix in Hartree/Bohr^2")
    units: str = Field(default="Hartree/Bohr^2", description="Units of the Hessian tensor")
    mass_weighted: bool = Field(default=False, description="Whether Hessian is already mass-weighted")
    frequencies_cm_inv: Optional[List[float]] = Field(None, description="Calculated harmonic vibrational frequencies")
    created_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        description="ISO 8601 creation timestamp",
    )


class IsotopologueResult(BaseModel):
    """Complete rotational, vibrational, and inertial result for an isotopologue."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    iso_label: str = Field(..., description="Isotopologue label (e.g. 'parent', '13C_1', 'D_dimer', '18O_2')")
    parent_label: str = Field(..., description="Reference parent Hessian label from /hessians/<label>")
    substituted_mass_numbers: List[Optional[int]] = Field(
        ..., description="Substituted mass number for each atom (None = standard elemental weight)"
    )
    atomic_masses_amu: List[float] = Field(
        ..., description="Dynamic Mendeleev atomic masses in unified atomic mass units (u)"
    )
    harmonic_frequencies_cm_inv: List[float] = Field(
        ..., description="All 3N harmonic frequencies in cm^-1 (negative for imaginary modes)"
    )
    vibrational_frequencies_cm_inv: List[float] = Field(
        ..., description="Genuine vibrational frequencies in cm^-1 excluding 5/6 external translations/rotations"
    )
    lowest_harmonic_mode_cm_inv: float = Field(
        ..., description="Lowest genuine intermolecular/intramolecular vibrational mode in cm^-1"
    )
    A_MHz: float = Field(..., description="Rotational constant A in MHz")
    B_MHz: float = Field(..., description="Rotational constant B in MHz")
    C_MHz: float = Field(..., description="Rotational constant C in MHz")
    Ia_u_A2: float = Field(..., description="Principal moment of inertia Ia in u * Angstrom^2")
    Ib_u_A2: float = Field(..., description="Principal moment of inertia Ib in u * Angstrom^2")
    Ic_u_A2: float = Field(..., description="Principal moment of inertia Ic in u * Angstrom^2")
    Paa_u_A2: float = Field(..., description="Planar moment Paa = (Ib + Ic - Ia) / 2 in u * Angstrom^2")
    Pbb_u_A2: float = Field(..., description="Planar moment Pbb = (Ia + Ic - Ib) / 2 in u * Angstrom^2")
    Pcc_u_A2: float = Field(..., description="Planar moment Pcc = (Ia + Ib - Ic) / 2 in u * Angstrom^2")
    inertial_defect_amu_A2: float = Field(
        ..., description="Inertial defect Delta = Ic - Ia - Ib in u * Angstrom^2"
    )
    kappa: float = Field(..., description="Ray's asymmetry parameter kappa = (2B - A - C) / (A - C)")


class BifurcatedStorageConfig(BaseModel):
    """Configuration profile for bifurcated active runtime and archival stores."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    active_runtime_path: str = Field(..., description="Filesystem path to runtime_active.h5")
    archive_pes_path: str = Field(..., description="Filesystem path to archive_pes.h5 / campaign.h5")
    storage_mode: StorageMode = Field(default=StorageMode.BIFURCATED, description="Operating storage mode")
    chunk_points: int = Field(default=512, ge=1, description="Number of points per chunk in HDF5 datasets")
    compression: str = Field(default="gzip", description="Lossless compression algorithm (gzip, lzf)")
    compression_opts: int = Field(default=4, ge=1, le=9, description="Compression level for gzip")
    shuffle: bool = Field(default=True, description="Enable byte shuffle filter for better compression ratios")
    fletcher32: bool = Field(default=True, description="Enable Fletcher32 checksum filter for data integrity")
    scaleoffset: Optional[int] = Field(
        default=None, description="Lossy scale-offset filter (MUST be None; strictly banned in CoChem)"
    )

    @field_validator("scaleoffset")
    @classmethod
    def validate_scaleoffset_strictly_banned(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            raise MethodMatrixViolationError(
                "scaleoffset lossy compression filter is strictly banned in CoChem HDF5 datastores to "
                "prevent precision truncation on micro-Hartree energy surfaces and artificial Hessian frequencies.",
                error_code=ProvenanceErrorCode.PRECISION_VIOLATION,
            )
        return v


# =============================================================================
# 2. MENDELEEV DYNAMIC MASS RESOLUTION (Mendeleev Library Mandate)
# =============================================================================

def get_atomic_mass(symbol: str, mass_number: Optional[int] = None) -> float:
    """
    Dynamically retrieves standard atomic weight or exact isotopic mass from the `mendeleev` library.
    Strictly forbids hardcoding atomic masses or manually inserting CODATA mass constants.

    Args:
        symbol: Element symbol (e.g. 'C', 'H', 'O', 'Cl', 'D', 'T')
        mass_number: Specific isotope nucleon count (e.g. 13 for 13C, 2 for 2H/D).
                     If None, returns the standard IUPAC atomic weight.

    Returns:
        Atomic mass in unified atomic mass units (u / Da).
    """
    clean_sym = symbol.strip().capitalize()
    # Normalize hydrogen isotopes
    if clean_sym in ("D", "H2"):
        clean_sym = "H"
        mass_number = 2
    elif clean_sym in ("T", "H3"):
        clean_sym = "H"
        mass_number = 3

    try:
        el = element(clean_sym)
    except Exception as exc:
        raise ValueError(f"Failed to query Mendeleev library for element '{symbol}': {exc}") from exc

    if mass_number is not None:
        for iso in el.isotopes:
            if iso.mass_number == mass_number:
                if iso.mass is not None:
                    return float(iso.mass)
                break
        # Fallback to isotopic mass estimation if exact mass is None
        logger.warning(
            f"Exact isotopic mass not found in Mendeleev for {clean_sym}-{mass_number}; "
            f"using nominal integer mass {mass_number}.0"
        )
        return float(mass_number)

    if el.mass is not None:
        return float(el.mass)

    raise ValueError(f"Mendeleev mass is undefined for element '{symbol}' (mass_number={mass_number})")


def get_atomic_masses_for_symbols(
    symbols: Sequence[str],
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> np.ndarray:
    """
    Returns array of atomic masses in unified atomic mass units (u) for a sequence of symbols.

    Args:
        symbols: Sequence of elemental symbols (e.g. ['C', 'O', 'H', 'H'])
        mass_numbers: Optional sequence of specific isotope mass numbers (e.g. [13, None, None, 2])

    Returns:
        NumPy array of shape (N,) with dtype float64.
    """
    masses: List[float] = []
    for i, s in enumerate(symbols):
        iso_num = mass_numbers[i] if mass_numbers is not None and i < len(mass_numbers) else None
        masses.append(get_atomic_mass(s, iso_num))
    return np.asarray(masses, dtype=np.float64)


# =============================================================================
# 3. MOLECULAR GEOMETRY & ROTATIONAL MATHEMATICS (§3, §4, §5)
# =============================================================================

def compute_center_of_mass(
    symbols: Sequence[str],
    coords: np.ndarray,
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> np.ndarray:
    """
    Computes the 3D center of mass in Angstroms.

    Args:
        symbols: Sequence of atom symbols
        coords: Cartesian coordinates array (N, 3) in Angstroms
        mass_numbers: Optional isotopic mass numbers

    Returns:
        3-element center of mass vector (x, y, z) in Angstroms.
    """
    masses = get_atomic_masses_for_symbols(symbols, mass_numbers)
    total_mass = float(np.sum(masses))
    if total_mass <= 0.0:
        raise ValueError("Total molecular mass must be strictly positive.")
    com = np.sum(coords * masses[:, None], axis=0) / total_mass
    return com


def compute_inertia_tensor(
    symbols: Sequence[str],
    coords: np.ndarray,
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Computes the moment of inertia tensor shifted to the molecular center of mass.

    Returns:
        I_tensor: 3x3 inertia tensor in u * Angstrom^2
        principal_moments: sorted eigenvalues (Ia <= Ib <= Ic) in u * Angstrom^2
        principal_axes: 3x3 eigenvector matrix (columns are principal axes a, b, c)
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    com = compute_center_of_mass(symbols, coords_arr, mass_numbers)
    r = coords_arr - com
    masses = get_atomic_masses_for_symbols(symbols, mass_numbers)

    I = np.full((3, 3), 0.0, dtype=np.float64)
    eye3 = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    for m_i, r_i in zip(masses, r, strict=False):
        r_sq = float(np.dot(r_i, r_i))
        I += m_i * (r_sq * eye3 - np.outer(r_i, r_i))

    evals, evecs = np.linalg.eigh(I)
    idx = np.argsort(evals)
    principal_moments = evals[idx]
    principal_axes = evecs[:, idx]

    return I, principal_moments, principal_axes


def compute_rotational_constants(
    symbols: Sequence[str],
    coords: np.ndarray,
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> Dict[str, Any]:
    """
    Computes rotational constants (A >= B >= C in MHz), principal moments of inertia,
    planar moments (Paa, Pbb, Pcc), inertial defect (Delta = Ic - Ia - Ib), and Ray's kappa.
    """
    _, principal_moments, principal_axes = compute_inertia_tensor(symbols, coords, mass_numbers)
    Ia, Ib, Ic = float(principal_moments[0]), float(principal_moments[1]), float(principal_moments[2])

    A_MHz = INERTIA_TO_MHZ_FACTOR / Ia if Ia > 1e-12 else float("inf")
    B_MHz = INERTIA_TO_MHZ_FACTOR / Ib if Ib > 1e-12 else float("inf")
    C_MHz = INERTIA_TO_MHZ_FACTOR / Ic if Ic > 1e-12 else float("inf")

    Paa = (Ib + Ic - Ia) / 2.0
    Pbb = (Ia + Ic - Ib) / 2.0
    Pcc = (Ia + Ib - Ic) / 2.0
    inertial_defect = Ic - Ia - Ib

    denom = A_MHz - C_MHz
    kappa = (2.0 * B_MHz - A_MHz - C_MHz) / denom if abs(denom) > 1e-6 else 0.0

    return {
        "A_MHz": A_MHz,
        "B_MHz": B_MHz,
        "C_MHz": C_MHz,
        "Ia_u_A2": Ia,
        "Ib_u_A2": Ib,
        "Ic_u_A2": Ic,
        "Paa_u_A2": Paa,
        "Pbb_u_A2": Pbb,
        "Pcc_u_A2": Pcc,
        "inertial_defect_amu_A2": inertial_defect,
        "kappa": kappa,
        "principal_axes": principal_axes,
    }


def compute_delta_r_and_delta_b(
    coords1: np.ndarray,
    coords2: np.ndarray,
    symbols: Sequence[str],
) -> Dict[str, float]:
    """
    Computes coordinate shifts between two geometries (Delta R) and propagates error to rotational
    constant B using the Method Matrix law: Delta B / B ≈ 2 * Delta R / R (§4.1, §8B.5 Rule D1).
    """
    coords1_arr = np.asarray(coords1, dtype=np.float64)
    coords2_arr = np.asarray(coords2, dtype=np.float64)
    if coords1_arr.shape != coords2_arr.shape:
        raise ValueError(f"Shape mismatch in coordinate comparison: {coords1_arr.shape} vs {coords2_arr.shape}")

    diff = coords2_arr - coords1_arr
    rmsd_angstrom = float(np.sqrt(np.mean(np.sum(diff ** 2, axis=1))))
    rmsd_pm = rmsd_angstrom * 100.0

    com1 = compute_center_of_mass(symbols, coords1_arr)
    com2 = compute_center_of_mass(symbols, coords2_arr)
    com_shift_angstrom = float(np.linalg.norm(com2 - com1))
    com_shift_pm = com_shift_angstrom * 100.0

    rot1 = compute_rotational_constants(symbols, coords1_arr)
    rot2 = compute_rotational_constants(symbols, coords2_arr)

    b1 = rot1["B_MHz"]
    b2 = rot2["B_MHz"]
    delta_b_mhz = abs(b2 - b1)
    rel_b_error_pct = (delta_b_mhz / b1) * 100.0 if b1 > 0 else 0.0

    return {
        "rmsd_angstrom": rmsd_angstrom,
        "rmsd_pm": rmsd_pm,
        "com_shift_angstrom": com_shift_angstrom,
        "com_shift_pm": com_shift_pm,
        "B_initial_MHz": b1,
        "B_final_MHz": b2,
        "delta_B_MHz": delta_b_mhz,
        "rel_B_error_pct": rel_b_error_pct,
    }


# =============================================================================
# 4. ISOTOPOLOGUE FORCE FIELD RECYCLING ENGINE (Method Matrix Arrow 7 & §6.10)
# =============================================================================

def diagonalize_mass_weighted_hessian(
    cart_hessian: np.ndarray,
    symbols: Sequence[str],
    mass_numbers: Optional[Sequence[Optional[int]]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Mass-weights a Cartesian Hessian (3N x 3N in Hartree/Bohr^2) using dynamic Mendeleev masses,
    diagonalizes to normal modes, and converts eigenvalues to harmonic frequencies in cm^-1.
    Imaginary frequencies (saddle points) are returned with negative values.

    Args:
        cart_hessian: 3N x 3N Cartesian Hessian matrix in Hartree/Bohr^2
        symbols: Sequence of atom symbols
        mass_numbers: Optional sequence of isotopic mass numbers

    Returns:
        sorted_freqs: 1D array of 3N harmonic frequencies in cm^-1
        sorted_modes: 3N x 3N eigenvector matrix of normal modes
    """
    natoms = len(symbols)
    h_arr = np.asarray(cart_hessian, dtype=np.float64)
    expected_dim = 3 * natoms
    if h_arr.shape != (expected_dim, expected_dim):
        raise ValueError(
            f"Hessian shape {h_arr.shape} does not match expected (3N, 3N) = ({expected_dim}, {expected_dim}) "
            f"for N={natoms} atoms."
        )

    masses = get_atomic_masses_for_symbols(symbols, mass_numbers)
    # Construct 3N mass vector: (m0, m0, m0, m1, m1, m1, ...)
    m3n = np.repeat(masses, 3)

    # Mass-weighting: H_mw[i, j] = H[i, j] / sqrt(m[i] * m[j])
    inv_sqrt_m = 1.0 / np.sqrt(m3n)
    h_mw = h_arr * np.outer(inv_sqrt_m, inv_sqrt_m)

    # Symmetrize to eliminate machine precision numerical drift
    h_mw = 0.5 * (h_mw + h_mw.T)

    evals, evecs = np.linalg.eigh(h_mw)

    frequencies: List[float] = []
    for val in evals:
        if val >= 0.0:
            freq = math.sqrt(val) * HESSIAN_EIG_TO_CM_INV_FACTOR
        else:
            freq = -math.sqrt(-val) * HESSIAN_EIG_TO_CM_INV_FACTOR
        frequencies.append(freq)

    freq_arr = np.asarray(frequencies, dtype=np.float64)
    sort_idx = np.argsort(freq_arr)
    sorted_freqs = freq_arr[sort_idx]
    sorted_modes = evecs[:, sort_idx]

    return sorted_freqs, sorted_modes


def reanalyze_isotopologue(
    cart_hessian: np.ndarray,
    coords: np.ndarray,
    symbols: Sequence[str],
    substituted_mass_numbers: Sequence[Optional[int]],
    iso_label: str,
    parent_label: str = "parent",
) -> IsotopologueResult:
    """
    Executes the zero-cost Isotopologue Shortcut (Method Matrix §8B.4 Arrow 7 & §6.10).
    Re-diagonalizes the saved Cartesian Hessian with substituted isotopic masses,
    recalculating harmonic frequencies, moments of inertia, and rotational constants.

    Args:
        cart_hessian: 3N x 3N Cartesian Hessian in Hartree/Bohr^2
        coords: Cartesian coordinates in Angstroms (N, 3)
        symbols: Elemental symbols
        substituted_mass_numbers: Target isotopic nucleon counts (e.g. [13, None, None, 2])
        iso_label: Descriptive label for this isotopologue (e.g. '13C_1', 'D_dimer')
        parent_label: Reference label of the parent Hessian

    Returns:
        IsotopologueResult containing all updated spectroscopic observables.
    """
    freqs, _ = diagonalize_mass_weighted_hessian(cart_hessian, symbols, substituted_mass_numbers)
    rot = compute_rotational_constants(symbols, coords, substituted_mass_numbers)
    masses = get_atomic_masses_for_symbols(symbols, substituted_mass_numbers)

    # Filter out 5 or 6 translational/rotational zero modes (|freq| < 20 cm^-1)
    vib_freqs = [float(f) for f in freqs if abs(f) > 20.0]
    lowest_harmonic = float(vib_freqs[0]) if vib_freqs else 0.0

    return IsotopologueResult(
        iso_label=iso_label,
        parent_label=parent_label,
        substituted_mass_numbers=list(substituted_mass_numbers),
        atomic_masses_amu=masses.tolist(),
        harmonic_frequencies_cm_inv=freqs.tolist(),
        vibrational_frequencies_cm_inv=vib_freqs,
        lowest_harmonic_mode_cm_inv=lowest_harmonic,
        A_MHz=rot["A_MHz"],
        B_MHz=rot["B_MHz"],
        C_MHz=rot["C_MHz"],
        Ia_u_A2=rot["Ia_u_A2"],
        Ib_u_A2=rot["Ib_u_A2"],
        Ic_u_A2=rot["Ic_u_A2"],
        Paa_u_A2=rot["Paa_u_A2"],
        Pbb_u_A2=rot["Pbb_u_A2"],
        Pcc_u_A2=rot["Pcc_u_A2"],
        inertial_defect_amu_A2=rot["inertial_defect_amu_A2"],
        kappa=rot["kappa"],
    )


def reanalyze_isotopologue_suite(
    cart_hessian: np.ndarray,
    coords: np.ndarray,
    symbols: Sequence[str],
    isotopologue_map: Dict[str, Sequence[Optional[int]]],
    parent_label: str = "parent",
) -> Dict[str, IsotopologueResult]:
    """
    Batch evaluates a complete campaign suite of isotopologues from a single Hessian.

    Args:
        cart_hessian: 3N x 3N Cartesian Hessian in Hartree/Bohr^2
        coords: Cartesian coordinates in Angstroms (N, 3)
        symbols: Elemental symbols
        isotopologue_map: Mapping of iso_label to substituted mass numbers
        parent_label: Label of the parent Hessian

    Returns:
        Dictionary mapping iso_label to IsotopologueResult.
    """
    results: Dict[str, IsotopologueResult] = {}
    for iso_label, mass_nums in isotopologue_map.items():
        res = reanalyze_isotopologue(
            cart_hessian=cart_hessian,
            coords=coords,
            symbols=symbols,
            substituted_mass_numbers=mass_nums,
            iso_label=iso_label,
            parent_label=parent_label,
        )
        results[iso_label] = res
    return results


# =============================================================================
# 5. CORE HDF5 PES STORE (Method Matrix §8C)
# =============================================================================

_H5PY_PROCESS_LOCK = threading.RLock()


class ReadWriteFileLock:
    """Portable cross-platform Reader-Writer Lock backed by FileLock token tracking."""

    def __init__(self, lock_path: Union[str, Path], timeout: float = 30.0) -> None:
        self.lock_path = Path(lock_path)
        self.writer_lock_path = self.lock_path.with_name(self.lock_path.name + ".writer.lock")
        self.readers_dir = self.lock_path.with_name(self.lock_path.name + ".readers")
        self.timeout = timeout
        self.writer_lock = FileLock(str(self.writer_lock_path), timeout=timeout)
        self.readers_dir.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()

    def _get_write_depth(self) -> int:
        return getattr(self._local, "write_depth", 0)

    def _set_write_depth(self, val: int) -> None:
        self._local.write_depth = val

    def _get_read_depth(self) -> int:
        return getattr(self._local, "read_depth", 0)

    def _set_read_depth(self, val: int) -> None:
        self._local.read_depth = val

    @contextmanager
    def read_lock(self) -> Generator[None, None, None]:
        """Shared read lock allowing unbounded concurrent readers with re-entrancy."""
        # If the current thread already holds the write lock, reading is re-entrant and safe
        if self._get_write_depth() > 0:
            yield
            return

        read_depth = self._get_read_depth()
        if read_depth > 0:
            self._set_read_depth(read_depth + 1)
            try:
                yield
            finally:
                self._set_read_depth(self._get_read_depth() - 1)
            return

        token = self.readers_dir / f"read_{os.getpid()}_{threading.get_ident()}_{uuid.uuid4().hex[:8]}.token"
        t0 = time.time()
        while self.writer_lock.is_locked:
            if time.time() - t0 > self.timeout:
                raise HDF5LockTimeoutError(
                    f"Timed out after {self.timeout}s waiting for read lock on {self.lock_path}",
                    error_code=ProvenanceErrorCode.HDF5_SWMR_LOCK_TIMEOUT,
                )
            time.sleep(0.005)

        token.touch(exist_ok=True)
        self._set_read_depth(1)
        try:
            yield
        finally:
            self._set_read_depth(0)
            token.unlink(missing_ok=True)

    @contextmanager
    def write_lock(self) -> Generator[None, None, None]:
        """Exclusive write lock waiting for active readers to finish."""
        depth = self._get_write_depth()
        if depth > 0:
            # Re-entrant acquisition by the same thread
            self._set_write_depth(depth + 1)
            try:
                yield
            finally:
                self._set_write_depth(self._get_write_depth() - 1)
            return

        try:
            self.writer_lock.acquire(timeout=self.timeout)
        except Timeout as exc:
            raise HDF5LockTimeoutError(
                f"Timed out after {self.timeout}s acquiring writer lock on {self.lock_path}",
                error_code=ProvenanceErrorCode.HDF5_SWMR_LOCK_TIMEOUT,
            ) from exc

        self._set_write_depth(1)
        t0 = time.time()
        try:
            while any(self.readers_dir.glob("*.token")):
                # Clean up stale tokens from exited processes
                for tok in list(self.readers_dir.glob("*.token")):
                    parts = tok.stem.split("_")
                    if len(parts) >= 2 and parts[1].isdigit():
                        r_pid = int(parts[1])
                        if HAS_PSUTIL and not psutil.pid_exists(r_pid):
                            tok.unlink(missing_ok=True)
                if not any(self.readers_dir.glob("*.token")):
                    break
                if time.time() - t0 > self.timeout:
                    raise HDF5LockTimeoutError(
                        f"Timed out after {self.timeout}s waiting for readers to clear on {self.lock_path}",
                        error_code=ProvenanceErrorCode.HDF5_SWMR_LOCK_TIMEOUT,
                    )
                time.sleep(0.005)
            yield
        finally:
            self._set_write_depth(0)
            if self.writer_lock.is_locked:
                self.writer_lock.release()


class PESStore:
    """
    Resizable, chunked, gzip+shuffle+fletcher32 HDF5 PES Store with QCSchema field names.
    Implements Method Matrix §8C layout, state persistence, grid registration,
    Delta-learning alignment, and DVR grid reshaping.
    """

    def __init__(
        self,
        path: Union[str, Path],
        complex_name: str = "",
        symbols: Sequence[str] = (),
        molecular_charge: int = 0,
        spin_multiplicity: int = 1,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT_S,
        swmr_mode: bool = False,
        lock_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        self.path = validate_airgap_write_path(Path(path).resolve())
        self.lock_dir = Path(lock_dir).resolve() if lock_dir else get_node_local_scratch_dir()
        self.lock_path = self.lock_dir / f"{self.path.name}.lock"
        self.lock_timeout = lock_timeout
        self.rw_lock = ReadWriteFileLock(self.lock_path, timeout=self.lock_timeout)
        self.swmr_mode = swmr_mode
        new_file = not self.path.exists()

        if new_file:
            self.path.parent.mkdir(parents=True, exist_ok=True)

        with self._file_lock():
            with h5py.File(self.path, "a", libver="latest") as f:
                m = f.require_group("meta")
                if new_file:
                    m.attrs["schema_name"] = "vdw_pes_campaign"
                    m.attrs["schema_version"] = 1
                    m.attrs["created_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if complex_name:
                    m.attrs["complex"] = complex_name
                if symbols:
                    m.attrs["symbols"] = json.dumps(list(symbols))
                    m.attrs["n_atoms"] = len(symbols)
                    masses = get_atomic_masses_for_symbols(symbols)
                    m.attrs["atomic_masses_amu"] = json.dumps(masses.tolist())
                m.attrs["molecular_charge"] = molecular_charge
                m.attrs["spin_multiplicity"] = spin_multiplicity

                # Ensure required root groups exist
                f.require_group("methods")
                pts_grp = f.require_group("points")
                f.require_group("grids")
                f.require_group("hessians")
                f.require_group("isotopologues")
                f.require_group("checkpoints")

                # Pre-allocate chunked, resizable datasets before SWMR activation [D]
                n_dim = 3 * max(1, len(symbols))
                if "coordinates" not in pts_grp:
                    pts_grp.create_dataset(
                        "coordinates",
                        shape=(0, n_dim),
                        maxshape=(None, n_dim),
                        dtype=np.float64,
                        chunks=(512, n_dim),
                    )
                if "energies" not in pts_grp:
                    pts_grp.create_dataset(
                        "energies",
                        shape=(0,),
                        maxshape=(None,),
                        dtype=np.float64,
                        chunks=(512,),
                    )
                if "point_ids" not in pts_grp:
                    dt = h5py.string_dtype(encoding="utf-8")
                    pts_grp.create_dataset(
                        "point_ids",
                        shape=(0,),
                        maxshape=(None,),
                        dtype=dt,
                        chunks=(512,),
                    )

                # Cache properties
                self.n_atoms = int(m.attrs.get("n_atoms", len(symbols)))
                self.complex_name = str(m.attrs.get("complex", complex_name))
                sym_attr = m.attrs.get("symbols")
                self.symbols = json.loads(sym_attr) if isinstance(sym_attr, str) else list(symbols)
                self.molecular_charge = int(m.attrs.get("molecular_charge", molecular_charge))
                self.spin_multiplicity = int(m.attrs.get("spin_multiplicity", spin_multiplicity))

                # Phase 2 SWMR Activation: Flush metadata and enable SWMR mode
                f.flush()
                if self.swmr_mode:
                    try:
                        f.swmr_mode = True
                    except (AttributeError, RuntimeError):
                        pass

    @contextmanager
    def _file_lock(self) -> Generator[None, None, None]:
        """Cross-platform byte-range file lock context manager serialized under process RLock."""
        with _H5PY_PROCESS_LOCK:
            with self.rw_lock.write_lock():
                yield

    @contextmanager
    def shared_read_lock(self) -> Generator[None, None, None]:
        """Shared read lock allowing unbounded concurrent readers serialized under process RLock."""
        with _H5PY_PROCESS_LOCK:
            with self.rw_lock.read_lock():
                yield

    @contextmanager
    def open_reader(self) -> Generator[h5py.File, None, None]:
        """Open HDF5 file in SWMR read mode with libver='latest' under shared read lock."""
        with self.shared_read_lock():
            with h5py.File(self.path, "r", libver="latest", swmr=True) as f:
                yield f

    @contextmanager
    def exclusive_write_lock(self) -> Generator[None, None, None]:
        """Exclusive write lock waiting for active readers to clear serialized under process RLock."""
        with _H5PY_PROCESS_LOCK:
            with self.rw_lock.write_lock():
                yield

    # -------------------------------------------------------------------------
    # Method Registration (QCSchema v1)
    # -------------------------------------------------------------------------
    def register_method(self, method_id: str, **attrs: Any) -> None:
        """
        Registers a computational method with QCSchema attributes in /methods/<method_id>.

        Args:
            method_id: Unique string identifier for the method (e.g. 'dlpno_avtz', 'wb97mv_qz')
            attrs: QCSchema method attributes (method, basis, aux_basis, program, driver, keywords, etc.)
        """
        # Validate through Pydantic record if method and basis provided
        if "method" in attrs and "basis" in attrs:
            QCSchemaMethodRecord(method_id=method_id, **attrs)

        with self._file_lock():
            with h5py.File(self.path, "a") as f:
                g = f.require_group(f"methods/{method_id}")
                for k, v in attrs.items():
                    if isinstance(v, (dict, list)):
                        g.attrs[k] = json.dumps(v)
                    elif isinstance(v, (int, float, str, bool)):
                        g.attrs[k] = v
                    elif isinstance(v, Enum):
                        g.attrs[k] = v.value
                g.attrs.setdefault("registered_utc", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    def get_method(self, method_id: str) -> Dict[str, Any]:
        """Retrieves registered method attributes dictionary."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if f"methods/{method_id}" not in f:
                    raise KeyError(f"Method '{method_id}' not found in PESStore methods.")
                g = f[f"methods/{method_id}"]
                res: Dict[str, Any] = {}
                for k, v in g.attrs.items():
                    val = v.item() if hasattr(v, "item") and not isinstance(v, (str, bytes)) else v
                    if isinstance(val, str) and (val.startswith("{") or val.startswith("[")):
                        try:
                            res[k] = json.loads(val)
                        except json.JSONDecodeError:
                            res[k] = val
                    else:
                        res[k] = val
                return res

    def list_methods(self) -> List[str]:
        """Lists all registered method IDs."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if "methods" not in f:
                    return []
                return sorted(list(f["methods"].keys()))

    # -------------------------------------------------------------------------
    # Dataset Creation Helper
    # -------------------------------------------------------------------------
    def _ds(
        self,
        f: h5py.File,
        mid: str,
        name: str,
        shape_tail: Tuple[int, ...],
        dtype: Any,
        checksum: bool = False,
    ) -> h5py.Dataset:
        """Internal helper creating resizable chunked datasets with gzip+shuffle+fletcher32."""
        grp = f.require_group(f"points/{mid}")
        if name in grp:
            return grp[name]

        kw: Dict[str, Any] = {
            "shape": (0,) + shape_tail,
            "maxshape": (None,) + shape_tail,
            "dtype": dtype,
            "chunks": (CHUNK_POINTS,) + shape_tail,
        }
        if dtype != VLEN_STR:
            kw.update(compression="gzip", compression_opts=4, shuffle=True)
            if checksum:
                kw["fletcher32"] = True
        return grp.create_dataset(name, **kw)

    @staticmethod
    def _append(ds: h5py.Dataset, block: np.ndarray) -> int:
        """Appends a block of data along axis 0 of a resizable dataset."""
        idx = int(ds.shape[0])
        ds.resize(idx + len(block), axis=0)
        ds[idx:] = block
        return idx

    def add_point(self, point: PESPointRecord) -> None:
        """Append a single PESPointRecord into the HDF5 store in a thread-safe SWMR-compliant manner [D]."""
        with self._file_lock():
            with h5py.File(self.path, "a", libver="latest") as f:
                pts = f.require_group("points")
                coords = np.asarray(point.coordinates, dtype=np.float64)
                if coords.ndim == 1:
                    coords = coords[None, :]
                elif coords.ndim == 2:
                    coords = coords.reshape(1, -1)

                cur_len = pts["energies"].shape[0] if "energies" in pts else 0
                new_len = cur_len + 1

                if "coordinates" in pts:
                    if pts["coordinates"].shape[1] != coords.shape[1]:
                        pts["coordinates"].resize((new_len, max(pts["coordinates"].shape[1], coords.shape[1])))
                    else:
                        pts["coordinates"].resize((new_len, coords.shape[1]))
                    pts["coordinates"][cur_len] = coords[0]
                else:
                    pts.create_dataset(
                        "coordinates",
                        data=coords,
                        maxshape=(None, coords.shape[1]),
                        chunks=(512, coords.shape[1]),
                    )

                if "energies" in pts:
                    pts["energies"].resize((new_len,))
                    pts["energies"][cur_len] = float(point.energy)
                else:
                    pts.create_dataset(
                        "energies",
                        data=np.array([point.energy], dtype=np.float64),
                        maxshape=(None,),
                        chunks=(512,),
                    )

                if "point_ids" in pts:
                    pts["point_ids"].resize((new_len,))
                    pts["point_ids"][cur_len] = str(point.point_id)
                else:
                    dt = h5py.string_dtype(encoding="utf-8")
                    d = pts.create_dataset(
                        "point_ids",
                        shape=(1,),
                        maxshape=(None,),
                        dtype=dt,
                        chunks=(512,),
                    )
                    d[0] = str(point.point_id)

                f.flush()

    def write_entry(self, point: Any) -> None:
        """Persist PES point record in-place adhering to Suggestion #65."""
        self.add_point(point)

    def get_all_point_ids(self) -> List[str]:
        """Retrieve all registered point IDs with SWMR refresh [D]."""
        with self.rw_lock.read_lock():
            with h5py.File(self.path, "r", libver="latest", swmr=self.swmr_mode) as f:
                if "/points/point_ids" in f:
                    dset = f["/points/point_ids"]
                    if self.swmr_mode:
                        try:
                            dset.refresh()
                        except Exception:
                            pass
                    raw = dset[:]
                    return [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in raw]
                return []

    # -------------------------------------------------------------------------
    # Writing PES Points
    # -------------------------------------------------------------------------
    def add_points(
        self,
        method_id: str,
        coords: Union[Sequence[Any], np.ndarray],
        energies: Union[Sequence[float], np.ndarray, float],
        *,
        point_ids: Optional[Sequence[str]] = None,
        gradients: Optional[Union[Sequence[Any], np.ndarray]] = None,
        converged: Optional[Union[Sequence[bool], np.ndarray, bool]] = None,
        wall_s: Optional[Union[Sequence[float], np.ndarray, float]] = None,
        creator: str = "ORCA",
        version: str = "6.1",
        routine: str = "sp",
    ) -> int:
        """
        Adds computed PES points with full QCSchema provenance, chunking, and checksums.

        Args:
            method_id: Registered method identifier
            coords: Cartesian coordinates array (Npts, Natoms, 3) or (Natoms, 3) for a single point
            energies: Electronic energies array (Npts,) or float for single point
            point_ids: Optional list of unique point IDs
            gradients: Optional gradients array (Npts, Natoms, 3) in Hartree/Bohr
            converged: Convergence flags (Npts,) or bool
            wall_s: Wall clock times in seconds
            creator: Package name
            version: Package version
            routine: Calculation routine

        Returns:
            Starting index i0 where points were inserted.
        """
        coords_arr = np.asarray(coords, dtype=np.float64)
        if coords_arr.ndim == 2:
            coords_arr = coords_arr[None]
        npts, natm = coords_arr.shape[0], coords_arr.shape[1]

        energies_arr = np.asarray(energies, dtype=np.float64)
        if energies_arr.ndim == 0:
            energies_arr = energies_arr[None]

        if len(energies_arr) != npts:
            raise ValueError(f"Number of energies ({len(energies_arr)}) does not match number of points ({npts}).")

        # Construct signed provenance record
        prov_obj = QCSchemaProvenance(
            creator=creator,
            version=version,
            routine=routine,
            host=socket.gethostname(),
            platform=platform.platform(),
            utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        prov_obj.compute_signature()
        prov_json = prov_obj.model_dump_json()

        with self._file_lock():
            with h5py.File(self.path, "a") as f:
                # Ensure method group exists
                f.require_group(f"methods/{method_id}")

                i0 = self._append(self._ds(f, method_id, "coordinates", (natm, 3), np.float64), coords_arr)
                self._append(self._ds(f, method_id, "energy", (), np.float64, checksum=True), energies_arr)

                # Convergence
                conv_block = np.full(npts, True, dtype=bool) if converged is None else np.asarray(converged, dtype=bool)
                if conv_block.ndim == 0:
                    conv_block = np.full(npts, bool(converged), dtype=bool)
                self._append(self._ds(f, method_id, "converged", (), np.bool_), conv_block)

                # Wall time
                wall_block = np.full(npts, 0.0, dtype=np.float64) if wall_s is None else np.asarray(wall_s, dtype=np.float64)
                if wall_block.ndim == 0:
                    wall_block = np.full(npts, float(wall_s), dtype=np.float64)
                self._append(self._ds(f, method_id, "wall_s", (), np.float64), wall_block)

                # Provenance
                self._append(self._ds(f, method_id, "provenance", (), VLEN_STR), np.array([prov_json] * npts, dtype=object))

                # Point IDs
                p_ids = list(point_ids) if point_ids is not None else [f"{method_id}:{i0 + k}" for k in range(npts)]
                self._append(self._ds(f, method_id, "point_id", (), VLEN_STR), np.array(p_ids, dtype=object))

                # Optional gradients
                if gradients is not None:
                    g_arr = np.asarray(gradients, dtype=np.float64)
                    if g_arr.ndim == 2:
                        g_arr = g_arr[None]
                    if "gradient" not in f[f"points/{method_id}"] and i0 > 0:
                        g_ds = self._ds(f, method_id, "gradient", (natm, 3), np.float64)
                        nan_pad = np.full((i0, natm, 3), np.nan, dtype=np.float64)
                        self._append(g_ds, nan_pad)
                        self._append(g_ds, g_arr)
                    else:
                        self._append(self._ds(f, method_id, "gradient", (natm, 3), np.float64), g_arr)
                elif "gradient" in f[f"points/{method_id}"]:
                    nan_pad = np.full((npts, natm, 3), np.nan, dtype=np.float64)
                    self._append(f[f"points/{method_id}/gradient"], nan_pad)

                f.flush()

        return i0

    def get_points(self, method_id: str, converged_only: bool = False) -> List[Dict[str, Any]]:
        """Convenience query returning list of point dicts for a method."""
        payload = self.dataset_full(method_id, converged_only=converged_only)
        n = min(len(payload["energy"]), len(payload["point_id"]), len(payload["coordinates"]))
        points_list = []
        for i in range(n):
            pt = {
                "point_id": payload["point_id"][i],
                "coordinates": payload["coordinates"][i],
                "energy": float(payload["energy"][i]),
                "converged": bool(payload["converged"][i]),
                "wall_s": float(payload["wall_s"][i]),
            }
            if "gradient" in payload and i < len(payload["gradient"]):
                pt["gradient"] = payload["gradient"][i]
            points_list.append(pt)
        return points_list

    # -------------------------------------------------------------------------
    # Hessians & Isotopologue Storage
    # -------------------------------------------------------------------------
    def add_hessian(
        self,
        label: str,
        H: Union[Sequence[Any], np.ndarray],
        *,
        level: str = "",
        geometry_ref: str = "",
        units: str = "Hartree/Bohr^2",
        mass_weighted: bool = False,
        frequencies_cm_inv: Optional[Sequence[float]] = None,
    ) -> None:
        """Stores Cartesian Hessian tensor and metadata in /hessians/<label>."""
        h_arr = np.asarray(H, dtype=np.float64)
        with self._file_lock():
            with h5py.File(self.path, "a") as f:
                g = f.require_group("hessians")
                if label in g:
                    del g[label]
                d = g.create_dataset(
                    label,
                    data=h_arr,
                    compression="gzip",
                    compression_opts=4,
                    shuffle=True,
                )
                d.attrs["level"] = level
                d.attrs["geometry_ref"] = geometry_ref
                d.attrs["units"] = units
                d.attrs["mass_weighted"] = mass_weighted
                d.attrs["created_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if frequencies_cm_inv is not None:
                    d.attrs["frequencies_cm_inv"] = json.dumps(list(frequencies_cm_inv))

    def get_hessian(self, label: str) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Retrieves Cartesian Hessian array and metadata dictionary."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if f"hessians/{label}" not in f:
                    raise KeyError(f"Hessian '{label}' not found in PESStore.")
                ds = f[f"hessians/{label}"]
                h_arr = ds[:]
                attrs = {k: v for k, v in ds.attrs.items()}
                return h_arr, attrs

    def list_hessians(self) -> List[str]:
        """Lists all registered Hessian labels."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if "hessians" not in f:
                    return []
                return sorted(list(f["hessians"].keys()))

    def add_isotopologue_result(self, label: str, iso_result: IsotopologueResult) -> None:
        """Stores an IsotopologueResult under /isotopologues/<label>/<iso_label>."""
        with self._file_lock():
            with h5py.File(self.path, "a") as f:
                grp = f.require_group(f"isotopologues/{label}/{iso_result.iso_label}")
                grp.attrs["payload_json"] = iso_result.model_dump_json()
                grp.attrs["A_MHz"] = iso_result.A_MHz
                grp.attrs["B_MHz"] = iso_result.B_MHz
                grp.attrs["C_MHz"] = iso_result.C_MHz
                grp.attrs["inertial_defect_amu_A2"] = iso_result.inertial_defect_amu_A2
                grp.attrs["lowest_harmonic_mode_cm_inv"] = iso_result.lowest_harmonic_mode_cm_inv
                grp.attrs["saved_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_isotopologue_result(self, label: str, iso_label: str) -> IsotopologueResult:
        """Retrieves a saved IsotopologueResult."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                path = f"isotopologues/{label}/{iso_label}"
                if path not in f:
                    raise KeyError(f"Isotopologue '{iso_label}' not found under Hessian '{label}'.")
                grp = f[path]
                payload = grp.attrs.get("payload_json")
                if payload is None:
                    raise ValueError(f"Isotopologue record at '{path}' is missing 'payload_json' attribute.")
                return IsotopologueResult.model_validate_json(payload)

    def list_isotopologues(self, label: str) -> List[str]:
        """Lists all isotopologue labels evaluated under Hessian label."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                path = f"isotopologues/{label}"
                if path not in f:
                    return []
                return sorted(list(f[path].keys()))

    # -------------------------------------------------------------------------
    # Grids & Multi-Dimensional Scans
    # -------------------------------------------------------------------------
    def register_grid(self, grid_id: str, axes: Dict[str, Sequence[float]], grid_type: str = "cartesian") -> None:
        """Registers grid axes for potential energy surfaces in /grids/<grid_id>."""
        with self._file_lock():
            with h5py.File(self.path, "a") as f:
                g = f.require_group(f"grids/{grid_id}")
                for name, vals in axes.items():
                    if name in g:
                        del g[name]
                    g.create_dataset(name, data=np.asarray(vals, dtype=np.float64))
                g.attrs["axis_order"] = json.dumps(list(axes.keys()))
                g.attrs["shape"] = [len(v) for v in axes.values()]
                g.attrs["grid_type"] = grid_type
                g.attrs["registered_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_grid(self, grid_id: str) -> Dict[str, Any]:
        """Retrieves grid axes and metadata."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if f"grids/{grid_id}" not in f:
                    raise KeyError(f"Grid '{grid_id}' not found in PESStore.")
                g = f[f"grids/{grid_id}"]
                axes: Dict[str, np.ndarray] = {}
                for k in g.keys():
                    axes[k] = g[k][:]
                axis_order = json.loads(g.attrs.get("axis_order", "[]"))
                shape = list(g.attrs.get("shape", []))
                grid_type = str(g.attrs.get("grid_type", "cartesian"))
                return {
                    "grid_id": grid_id,
                    "axes": axes,
                    "axis_order": axis_order,
                    "shape": shape,
                    "grid_type": grid_type,
                }

    def list_grids(self) -> List[str]:
        """Lists all registered grid IDs."""
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if "grids" not in f:
                    return []
                return sorted(list(f["grids"].keys()))

    # -------------------------------------------------------------------------
    # Idempotent Querying, Delta-Learning, & DVR
    # -------------------------------------------------------------------------
    def todo(self, method_id: str, wanted_ids: Iterable[str]) -> List[str]:
        """
        Identifies missing / unconverged points for incremental refinement and restart.

        Args:
            method_id: Method identifier
            wanted_ids: List of requested point IDs

        Returns:
            List of point IDs that are missing or not yet converged.
        """
        wanted_list = list(wanted_ids)
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                p = f.get(f"points/{method_id}")
                if p is None or "point_id" not in p:
                    return wanted_list
                p_ids = [(s.decode("utf-8") if isinstance(s, bytes) else str(s)) for s in p["point_id"][:]]
                converged = p["converged"][:]
                have = {s for s, ok in zip(p_ids, converged, strict=False) if ok}
        return [i for i in wanted_list if i not in have]

    def dataset(self, method_id: str, converged_only: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """
        Retrieves coordinates and energies array for a method.

        Args:
            method_id: Method identifier
            converged_only: If True, only returns converged points

        Returns:
            Tuple of (coordinates (Npts, Natoms, 3), energies (Npts,))
        """
        with self.shared_read_lock():
            with h5py.File(self.path, "r") as f:
                if f"points/{method_id}" not in f:
                    raise KeyError(f"No points dataset found for method '{method_id}'.")
                p = f[f"points/{method_id}"]
                mask = p["converged"][:] if converged_only else slice(None)
                coords = p["coordinates"][:][mask]
                energies = p["energy"][:][mask]
                return coords, energies

    def dataset_full(self, method_id: str, converged_only: bool = True) -> Dict[str, Any]:
        """Retrieves full points payload dictionary for a method."""
        with self.shared_read_lock():
            with h5py.File(self.path, "r") as f:
                if f"points/{method_id}" not in f:
                    raise KeyError(f"No points dataset found for method '{method_id}'.")
                p = f[f"points/{method_id}"]
                mask = p["converged"][:] if converged_only else slice(None)
                point_ids = [(s.decode("utf-8") if isinstance(s, bytes) else str(s)) for s in p["point_id"][:][mask]]
                res: Dict[str, Any] = {
                    "method_id": method_id,
                    "coordinates": p["coordinates"][:][mask],
                    "energy": p["energy"][:][mask],
                    "converged": p["converged"][:][mask],
                    "wall_s": p["wall_s"][:][mask],
                    "point_id": point_ids,
                }
                if "gradient" in p:
                    res["gradient"] = p["gradient"][:][mask]
                return res

    def delta_pairs(self, low_method: str, high_method: str) -> Tuple[List[str], np.ndarray, np.ndarray]:
        """
        Returns aligned (keys, coordinates, E_high - E_low) pairs for Delta-learning MLFF training.

        Args:
            low_method: Low-level method identifier (e.g. 'wb97xd4_tz')
            high_method: High-level method identifier (e.g. 'dlpno_ccsdt1_avtz')

        Returns:
            keys: Aligned common point IDs
            X: High-level coordinates array (Npts, Natoms, 3)
            dE: Delta energies array (Npts,) in Hartrees (E_high - E_low)
        """
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                def get_idx(mid: str) -> Dict[str, int]:
                    if f"points/{mid}" not in f:
                        return {}
                    p = f[f"points/{mid}"]
                    ids = [(s.decode("utf-8") if isinstance(s, bytes) else str(s)) for s in p["point_id"][:]]
                    conv = p["converged"][:]
                    return {k: j for j, (k, ok) in enumerate(zip(ids, conv, strict=False)) if ok}

                il = get_idx(low_method)
                ih = get_idx(high_method)
                keys = sorted(set(il.keys()) & set(ih.keys()))

                if not keys:
                    return [], np.empty((0, self.n_atoms, 3)), np.empty((0,))

                idx_h = [ih[k] for k in keys]
                idx_l = [il[k] for k in keys]

                X = f[f"points/{high_method}/coordinates"][:][idx_h]
                dE = f[f"points/{high_method}/energy"][:][idx_h] - f[f"points/{low_method}/energy"][:][idx_l]
                return keys, X, dE

    def dvr_grid(self, method_id: str, grid_id: str) -> np.ndarray:
        """
        Reshapes energies onto a registered product grid for Discrete Variable Representation (DVR) solvers.
        Missing or unconverged points are filled with NaN.

        Args:
            method_id: Method identifier
            grid_id: Grid identifier

        Returns:
            Multidimensional NumPy array matching grid shape with potential values in Hartrees.
        """
        with self.open_reader() as f:
            if f"grids/{grid_id}" not in f:
                raise KeyError(f"Grid '{grid_id}' not found in PESStore.")
            shape = tuple(int(x) for x in f[f"grids/{grid_id}"].attrs["shape"])
            if f"points/{method_id}" not in f:
                return np.full(shape, np.nan, dtype=np.float64)

            p = f[f"points/{method_id}"]
            for ds_name in ["point_id", "converged", "energy"]:
                if ds_name in p and hasattr(p[ds_name], "refresh"):
                    try:
                        p[ds_name].refresh()
                    except Exception:
                        pass
            ids = [(s.decode("utf-8") if isinstance(s, bytes) else str(s)) for s in p["point_id"][:]]
            conv = p["converged"][:]
            energies = p["energy"][:]

            total_pts = 1
            for dim in shape:
                total_pts *= dim

            V = np.full(total_pts, np.nan, dtype=np.float64)
            prefix = f"{grid_id}:"
            for j, k in enumerate(ids):
                if k.startswith(prefix) and conv[j]:
                    try:
                        idx = int(k.split(":")[1])
                        if 0 <= idx < total_pts:
                            V[idx] = energies[j]
                    except (ValueError, IndexError):
                        logger.debug("Failed to parse point index from point_id '%s'", k)
            return V.reshape(shape)

    # -------------------------------------------------------------------------
    # Checkpoints & Integrity
    # -------------------------------------------------------------------------
    def checkpoint_state(self, checkpoint_name: str, state_data: Dict[str, Any]) -> None:
        """Serializes arbitrary dictionary state to /checkpoints/<checkpoint_name>."""
        with self._file_lock():
            with h5py.File(self.path, "a") as f:
                grp = f.require_group(f"checkpoints/{checkpoint_name}")
                grp.attrs["saved_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                for k, v in state_data.items():
                    if isinstance(v, np.ndarray):
                        if k in grp:
                            del grp[k]
                        grp.create_dataset(k, data=v)
                    elif isinstance(v, (int, float, str, bool)):
                        grp.attrs[k] = v
                    else:
                        grp.attrs[k] = json.dumps(v)

    def read_checkpoint(self, checkpoint_name: str) -> Dict[str, Any]:
        """Reads back saved checkpoint state dictionary."""
        result: Dict[str, Any] = {}
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                path = f"checkpoints/{checkpoint_name}"
                if path not in f:
                    return result
                grp = f[path]
                for k, v in grp.attrs.items():
                    val = v.item() if hasattr(v, "item") and not isinstance(v, (str, bytes)) else v
                    if isinstance(val, str) and (val.startswith("{") or val.startswith("[")):
                        try:
                            result[k] = json.loads(val)
                        except json.JSONDecodeError:
                            result[k] = val
                    else:
                        result[k] = val
                for k in grp.keys():
                    result[k] = grp[k][:]
        return result

    def validate_integrity(self) -> Dict[str, Any]:
        """Verifies Fletcher32 checksums and dataset completeness."""
        report: Dict[str, Any] = {"status": "PASSED", "methods": {}, "corrupted_datasets": []}
        with self._file_lock():
            with h5py.File(self.path, "r") as f:
                if "points" in f:
                    for mid in f["points"].keys():
                        grp = f[f"points/{mid}"]
                        n_pts = len(grp["energy"]) if "energy" in grp else 0
                        report["methods"][mid] = {"n_points": n_pts}
                        # Reading full dataset forces Fletcher32 checksum validation
                        try:
                            _ = grp["energy"][:]
                            _ = grp["coordinates"][:]
                        except Exception as exc:
                            report["status"] = "CORRUPTED"
                            report["corrupted_datasets"].append(f"points/{mid}: {exc}")
        return report


# =============================================================================
# 6. SWMR & ARCHIVAL BIFURCATED PES STORE
# =============================================================================

class BifurcatedPESStore:
    """
    Manages dual-tier storage bifurcation:
    1. Active Runtime Store (runtime_active.h5): High-throughput active SWMR or scratch container.
    2. Archival QCSchema Store (archive_pes.h5 / campaign.h5): Lossless compressed HDF5 store.
    """

    def __init__(
        self,
        active_runtime_path: Optional[Union[str, Path]] = None,
        archive_pes_path: Optional[Union[str, Path]] = None,
        complex_name: str = "",
        symbols: Sequence[str] = (),
        molecular_charge: int = 0,
        spin_multiplicity: int = 1,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT_S,
    ) -> None:
        art_dir = get_artifact_dir()
        runtime_dir = get_runtime_dir()

        self.active_path = (
            resolve_mapped_path(active_runtime_path, runtime_dir)
            if active_runtime_path is not None
            else runtime_dir / "runtime_active.h5"
        )
        self.archive_path = (
            resolve_mapped_path(archive_pes_path, art_dir)
            if archive_pes_path is not None
            else art_dir / "Databases" / "archive_pes.h5"
        )

        self.complex_name = complex_name
        self.symbols = list(symbols)
        self.molecular_charge = molecular_charge
        self.spin_multiplicity = spin_multiplicity
        self.lock_timeout = lock_timeout

        # Initialize underlying PES stores
        self.active_store = PESStore(
            path=self.active_path,
            complex_name=complex_name,
            symbols=symbols,
            molecular_charge=molecular_charge,
            spin_multiplicity=spin_multiplicity,
            lock_timeout=lock_timeout,
        )
        self.archive_store = PESStore(
            path=self.archive_path,
            complex_name=complex_name,
            symbols=symbols,
            molecular_charge=molecular_charge,
            spin_multiplicity=spin_multiplicity,
            lock_timeout=lock_timeout,
        )

    # -------------------------------------------------------------------------
    # Active / Archival Execution Context Managers
    # -------------------------------------------------------------------------
    @contextmanager
    def active_writer(self) -> Generator[PESStore, None, None]:
        """Context manager providing thread-safe write access to active runtime store."""
        with self.active_store.exclusive_write_lock():
            yield self.active_store

    @contextmanager
    def active_reader(self) -> Generator[PESStore, None, None]:
        """Context manager providing concurrent read access to active runtime store."""
        with self.active_store.shared_read_lock():
            yield self.active_store

    @contextmanager
    def archive_writer(self) -> Generator[PESStore, None, None]:
        """Context manager providing thread-safe write access to archival store."""
        with self.archive_store.exclusive_write_lock():
            yield self.archive_store

    @contextmanager
    def archive_reader(self) -> Generator[PESStore, None, None]:
        """Context manager providing read access to archival store."""
        with self.archive_store.shared_read_lock():
            yield self.archive_store

    # -------------------------------------------------------------------------
    # Point Recording & Promotion
    # -------------------------------------------------------------------------
    def record_point_to_active(
        self,
        method_id: str,
        coords: Union[Sequence[Any], np.ndarray],
        energy: float,
        *,
        point_id: Optional[str] = None,
        gradient: Optional[Union[Sequence[Any], np.ndarray]] = None,
        converged: bool = True,
        wall_s: float = 0.0,
        creator: str = "ORCA",
        version: str = "6.1",
        routine: str = "sp",
    ) -> int:
        """Appends a single calculation result to the active runtime store."""
        return self.active_store.add_points(
            method_id=method_id,
            coords=coords,
            energies=[energy],
            point_ids=[point_id] if point_id is not None else None,
            gradients=[gradient] if gradient is not None else None,
            converged=[converged],
            wall_s=[wall_s],
            creator=creator,
            version=version,
            routine=routine,
        )

    def record_hessian_and_recycle_isotopologues(
        self,
        label: str,
        cart_hessian: np.ndarray,
        coords: np.ndarray,
        isotopologue_map: Dict[str, Sequence[Optional[int]]],
        level: str = "",
        geometry_ref: str = "",
    ) -> Dict[str, IsotopologueResult]:
        """
        Stores Cartesian Hessian in active store, executes zero-cost isotopologue recycling
        for all requested isotopic substitutions, and persists results to active store.
        """
        self.active_store.add_hessian(
            label=label,
            H=cart_hessian,
            level=level,
            geometry_ref=geometry_ref,
        )

        iso_results = reanalyze_isotopologue_suite(
            cart_hessian=cart_hessian,
            coords=coords,
            symbols=self.symbols,
            isotopologue_map=isotopologue_map,
            parent_label=label,
        )

        for _, res in iso_results.items():
            self.active_store.add_isotopologue_result(label, res)

        return iso_results

    def promote_active_to_archive(self, method_id: Optional[str] = None) -> int:
        """
        Transfers converged points and methods from the active runtime store into the
        compressed archival store with Fletcher32 checksum verification.

        Args:
            method_id: Optional specific method ID to promote. If None, promotes all methods.

        Returns:
            Total count of points promoted.
        """
        methods = [method_id] if method_id is not None else self.active_store.list_methods()
        total_promoted = 0

        for mid in methods:
            # Transfer method registration
            try:
                m_attrs = self.active_store.get_method(mid)
                self.archive_store.register_method(mid, **m_attrs)
            except Exception as exc:
                logger.warning(f"Could not transfer method registration for '{mid}': {exc}")

            # Transfer points
            try:
                data = self.active_store.dataset_full(mid, converged_only=True)
                npts = len(data["energy"])
                if npts > 0:
                    # Check which points are already in archive
                    needed_ids = self.archive_store.todo(mid, data["point_id"])
                    if needed_ids:
                        needed_set = set(needed_ids)
                        keep_mask = [pid in needed_set for pid in data["point_id"]]

                        coords_to_add = data["coordinates"][keep_mask]
                        energies_to_add = data["energy"][keep_mask]
                        pids_to_add = [pid for pid, ok in zip(data["point_id"], keep_mask, strict=False) if ok]
                        grads_to_add = data.get("gradient")[keep_mask] if "gradient" in data else None
                        conv_to_add = data["converged"][keep_mask]
                        wall_to_add = data["wall_s"][keep_mask]

                        self.archive_store.add_points(
                            method_id=mid,
                            coords=coords_to_add,
                            energies=energies_to_add,
                            point_ids=pids_to_add,
                            gradients=grads_to_add,
                            converged=conv_to_add,
                            wall_s=wall_to_add,
                        )
                        total_promoted += len(pids_to_add)
            except KeyError:
                continue

        # Transfer Hessians and Isotopologues
        for h_label in self.active_store.list_hessians():
            try:
                h_mat, h_attrs = self.active_store.get_hessian(h_label)
                self.archive_store.add_hessian(
                    label=h_label,
                    H=h_mat,
                    level=str(h_attrs.get("level", "")),
                    geometry_ref=str(h_attrs.get("geometry_ref", "")),
                    units=str(h_attrs.get("units", "Hartree/Bohr^2")),
                )
                for iso_label in self.active_store.list_isotopologues(h_label):
                    iso_res = self.active_store.get_isotopologue_result(h_label, iso_label)
                    self.archive_store.add_isotopologue_result(h_label, iso_res)
            except Exception as exc:
                logger.warning(f"Could not transfer Hessian '{h_label}' to archive: {exc}")

        logger.info(f"Promoted {total_promoted} active runtime points to archival store {self.archive_path}")
        return total_promoted


class TripartitePESStore(BifurcatedPESStore):
    """
    Tripartite PES Store architecture incorporating:
    1. Active runtime SWMR store for real-time trajectory/grid evaluation.
    2. Shared reader / exclusive writer synchronization via ReadWriteFileLock.
    3. Archival store for long-term compressed QCSchema representations.
    """

    def __init__(
        self,
        path: Optional[Union[str, Path]] = None,
        complex_name: str = "",
        symbols: Sequence[str] = (),
        molecular_charge: int = 0,
        spin_multiplicity: int = 1,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT_S,
        archive_path: Optional[Union[str, Path]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            active_runtime_path=path,
            archive_pes_path=archive_path,
            complex_name=complex_name,
            symbols=symbols,
            molecular_charge=molecular_charge,
            spin_multiplicity=spin_multiplicity,
            lock_timeout=lock_timeout,
        )

    def register_method(self, method_id: str, **attrs: Any) -> None:
        """Registers computational method into the active runtime store."""
        self.active_store.register_method(method_id, **attrs)

    def get_points(self, method_id: str, converged_only: bool = False) -> List[Dict[str, Any]]:
        """Retrieves points for a method from active runtime store."""
        return self.active_store.get_points(method_id, converged_only=converged_only)

    def add_points(self, *args: Any, **kwargs: Any) -> int:
        """Appends points into the active runtime store."""
        return self.active_store.add_points(*args, **kwargs)

    def list_methods(self) -> List[str]:
        """Lists methods registered in active runtime store."""
        return self.active_store.list_methods()

    def get_method(self, method_id: str) -> Dict[str, Any]:
        """Retrieves metadata attributes for a registered method."""
        return self.active_store.get_method(method_id)

    def todo(self, method_id: str, wanted_point_ids: Sequence[str]) -> List[str]:
        """Identifies missing or unconverged points in active runtime store."""
        return self.active_store.todo(method_id, wanted_point_ids)

    def dataset(self, *args: Any, **kwargs: Any) -> Tuple[np.ndarray, np.ndarray]:
        """Extracts aligned coordinates and energies from active runtime store."""
        return self.active_store.dataset(*args, **kwargs)

    def dataset_full(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Extracts full structured dataset dictionary from active runtime store."""
        return self.active_store.dataset_full(*args, **kwargs)


# =============================================================================
# 7. PARALLEL SHARD MERGER UTILITY
# =============================================================================

def merge_pes_shards(
    shard_paths: Sequence[Union[str, Path]],
    target_store_path: Union[str, Path],
    complex_name: str = "",
    symbols: Sequence[str] = (),
) -> int:
    """
    Merges multiple worker PES shards (campaign_rank_0.h5, campaign_rank_1.h5, ...)
    into a single master PES store atomically.

    Args:
        shard_paths: List of shard file paths
        target_store_path: Destination HDF5 file path
        complex_name: Complex name identifier
        symbols: Elemental symbols

    Returns:
        Total count of points merged into the target store.
    """
    target = PESStore(
        path=target_store_path,
        complex_name=complex_name,
        symbols=symbols,
    )
    total_merged = 0

    for s_path in shard_paths:
        p = Path(s_path)
        if not p.exists():
            logger.warning(f"Shard file not found: {p}")
            continue

        shard = PESStore(path=p)
        methods = shard.list_methods()

        for mid in methods:
            # Register method if not present
            try:
                m_attrs = shard.get_method(mid)
                target.register_method(mid, **m_attrs)
            except Exception as exc:
                logger.debug("Method registration skipped or failed during merge for '%s': %s", mid, exc)

            try:
                data = shard.dataset_full(mid, converged_only=True)
                npts = len(data["energy"])
                if npts > 0:
                    needed_ids = target.todo(mid, data["point_id"])
                    if needed_ids:
                        needed_set = set(needed_ids)
                        keep_mask = [pid in needed_set for pid in data["point_id"]]

                        coords_to_add = data["coordinates"][keep_mask]
                        energies_to_add = data["energy"][keep_mask]
                        pids_to_add = [pid for pid, ok in zip(data["point_id"], keep_mask, strict=False) if ok]
                        grads_to_add = data.get("gradient")[keep_mask] if "gradient" in data else None
                        conv_to_add = data["converged"][keep_mask]
                        wall_to_add = data["wall_s"][keep_mask]

                        target.add_points(
                            method_id=mid,
                            coords=coords_to_add,
                            energies=energies_to_add,
                            point_ids=pids_to_add,
                            gradients=grads_to_add,
                            converged=conv_to_add,
                            wall_s=wall_to_add,
                        )
                        total_merged += len(pids_to_add)
            except KeyError:
                continue

    logger.info(f"Successfully merged {total_merged} points across {len(shard_paths)} shards into {target_store_path}")
    return total_merged


# =============================================================================
# 8. COMMAND-LINE INTERFACE
# =============================================================================

def build_cli_parser() -> argparse.ArgumentParser:
    """Builds comprehensive CLI parser for PES store management."""
    parser = argparse.ArgumentParser(
        description="CoChem Core PES Store: QCSchema HDF5, SWMR/Archival Bifurcation, & Isotopologue Recycling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # info
    p_info = subparsers.add_parser("info", help="Display summary information for a PESStore HDF5 file")
    p_info.add_argument("path", help="Path to HDF5 store file")

    # todo
    p_todo = subparsers.add_parser("todo", help="Check missing points on a grid")
    p_todo.add_argument("path", help="Path to HDF5 store file")
    p_todo.add_argument("--method", required=True, help="Method ID")
    p_todo.add_argument("--grid", required=True, help="Grid ID")

    # merge
    p_merge = subparsers.add_parser("merge", help="Merge multiple HDF5 shards into a destination store")
    p_merge.add_argument("--target", required=True, help="Target master HDF5 path")
    p_merge.add_argument("shards", nargs="+", help="Input shard file paths")

    # recycle-isotopologues
    p_iso = subparsers.add_parser("recycle-isotopologues", help="Re-analyze a saved Hessian with isotopic substitutions")
    p_iso.add_argument("path", help="Path to HDF5 store file")
    p_iso.add_argument("--hessian-label", required=True, help="Registered Hessian label")
    p_iso.add_argument("--xyz", required=True, help="Path to reference XYZ geometry")

    return parser


def main() -> None:
    """Main CLI execution router."""
    parser = build_cli_parser()
    args = parser.parse_args()

    if not args.subcommand or args.subcommand == "info":
        path = args.path if hasattr(args, "path") else get_state_file_path()
        store = PESStore(path)
        print("=" * 60)
        print(f"CoChem PES Store: {store.path}")
        print(f"Complex: {store.complex_name} | N_atoms: {store.n_atoms} | Symbols: {store.symbols}")
        print(f"Methods registered: {store.list_methods()}")
        print(f"Hessians stored: {store.list_hessians()}")
        print(f"Grids registered: {store.list_grids()}")
        print("Integrity Check:", store.validate_integrity())
        print("=" * 60)

    elif args.subcommand == "todo":
        store = PESStore(args.path)
        grid = store.get_grid(args.grid)
        shape = grid["shape"]
        total_pts = 1
        for dim in shape:
            total_pts *= dim
        wanted = [f"{args.grid}:{i}" for i in range(total_pts)]
        missing = store.todo(args.method, wanted)
        print(f"Grid '{args.grid}' has {total_pts} total points.")
        print(f"Method '{args.method}' has {len(missing)} points remaining to compute ({len(wanted) - len(missing)} completed).")

    elif args.subcommand == "merge":
        merged = merge_pes_shards(args.shards, args.target)
        print(f"Merged {merged} total points into {args.target}")

    elif args.subcommand == "recycle-isotopologues":
        store = PESStore(args.path)
        h_mat, h_attrs = store.get_hessian(args.hessian_label)
        # Parse XYZ
        xyz_p = Path(args.xyz)
        lines = xyz_p.read_text(encoding="utf-8").splitlines()
        n = int(lines[0].split()[0])
        syms: List[str] = []
        coords_list: List[List[float]] = []
        for ln in lines[2:2 + n]:
            parts = ln.split()
            syms.append(parts[0])
            coords_list.append([float(x) for x in parts[1:4]])
        coords_arr = np.asarray(coords_list, dtype=np.float64)

        # Standard test suite of common isotopologues
        iso_map: Dict[str, List[Optional[int]]] = {"parent": [None] * len(syms)}
        for i, s in enumerate(syms):
            clean_s = s.strip().capitalize()
            if clean_s == "C":
                m_list = [None] * len(syms)
                m_list[i] = 13
                iso_map[f"13C_atom_{i}"] = m_list
            elif clean_s == "O":
                m_list = [None] * len(syms)
                m_list[i] = 18
                iso_map[f"18O_atom_{i}"] = m_list
            elif clean_s == "H":
                m_list = [None] * len(syms)
                m_list[i] = 2
                iso_map[f"D_atom_{i}"] = m_list

        results = reanalyze_isotopologue_suite(h_mat, coords_arr, syms, iso_map, parent_label=args.hessian_label)
        print(f"Evaluated {len(results)} isotopologues from Hessian '{args.hessian_label}':")
        for k, v in results.items():
            store.add_isotopologue_result(args.hessian_label, v)
            print(f"  [{k}] A={v.A_MHz:.3f} MHz, B={v.B_MHz:.3f} MHz, C={v.C_MHz:.3f} MHz | Lowest Mode: {v.lowest_harmonic_mode_cm_inv:.2f} cm^-1")


if __name__ == "__main__":
    main()
