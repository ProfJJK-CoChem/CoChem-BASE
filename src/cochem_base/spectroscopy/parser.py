"""
Authentic Spectroscopic Telemetry Parser & Cross-Platform HDF5 Concurrency Layer.
Method Matrix v4: §3.0, §8C, §13, and SRS Chunk 4 Suggestion #34.
Strictly distinguishes Born-Oppenheimer theoretical B_e from experimental ground-state B_0.
Enforces thread-safe SWMR concurrency via filelock (POSIX fcntl is strictly prohibited).
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import filelock
from pydantic import BaseModel, Field

try:
    import h5py
except ImportError:
    h5py = None  # type: ignore

# CODATA 2022 Conversion Constant: h / (8 * pi^2) in MHz * amu * Angstrom^2
INERTIA_CONVERSION_MHZ_AMU_ANG2 = 505379.008784


class SpectroscopicConstantRecord(BaseModel):
    """Schema for individual rotational and vibrational constants with provenance."""

    name: str = Field(..., description="Observable symbol, e.g. A_e, B_0")
    value: float = Field(..., description="Numerical value in MHz or amu*Angstrom^2")
    unit: str = Field(default="MHz", description="Unit of physical measurement")
    provenance: str = Field(..., description="Method Matrix provenance tag: [M], [D], [E]")
    description: str = Field(default="", description="Theoretical or experimental definition")


class SpectroscopicTelemetryResult(BaseModel):
    """Authoritative spectroscopic telemetry model distinguishing B_e and B_0."""

    engine: str = Field(..., description="Source quantum chemical engine")
    # Equilibrium constants at Born-Oppenheimer PES minimum [M]
    a_e: float = Field(..., description="Equilibrium rotational constant A_e (MHz) [M]")
    b_e: float = Field(..., description="Equilibrium rotational constant B_e (MHz) [M]")
    c_e: float = Field(..., description="Equilibrium rotational constant C_e (MHz) [M]")

    # Vibrational zero-point corrections [M]
    delta_a_vib: float = Field(default=0.0, description="Vibrational correction Delta A_vib (MHz) [M]")
    delta_b_vib: float = Field(default=0.0, description="Vibrational correction Delta B_vib (MHz) [M]")
    delta_c_vib: float = Field(default=0.0, description="Vibrational correction Delta C_vib (MHz) [M]")

    # Effective vibrational ground-state constants [D]
    a_0: float = Field(..., description="Ground-state rotational constant A_0 = A_e + Delta A_vib (MHz) [D]")
    b_0: float = Field(..., description="Ground-state rotational constant B_0 = B_e + Delta B_vib (MHz) [D]")
    c_0: float = Field(..., description="Ground-state rotational constant C_0 = C_e + Delta C_vib (MHz) [D]")

    # Principal moments of inertia (amu * Angstrom^2) [D]
    i_a: float = Field(..., description="Principal moment of inertia I_a (amu*Angstrom^2) [D]")
    i_b: float = Field(..., description="Principal moment of inertia I_b (amu*Angstrom^2) [D]")
    i_c: float = Field(..., description="Principal moment of inertia I_c (amu*Angstrom^2) [D]")

    # Inertial defect Delta = I_c - I_a - I_b (amu * Angstrom^2) [D]
    inertial_defect: float = Field(..., description="Inertial defect Delta = I_c - I_a - I_b [D]")

    # Dipole moments (Debye) [M]
    dipole_components: Tuple[float, float, float] = Field(default=(0.0, 0.0, 0.0), description="Dipole components (mu_a, mu_b, mu_c) in Debye [M]")
    total_dipole: float = Field(default=0.0, description="Total dipole moment magnitude in Debye [M]")

    provenance_banner: str = Field(
        default="Method Matrix §3.0: Equilibrium B_e is purely theoretical at the PES minimum; ground-state B_0 is the observable measured in rotational spectroscopy.",
        description="Methodological compliance notice"
    )


SpectroscopyTelemetryResult = SpectroscopicTelemetryResult


class SpectroscopyTelemetryParser:
    """Parses ORCA and CFOUR output logs into authentic physical telemetry structures."""

    def __init__(self) -> None:
        self._orca_rot_mhz_pattern = re.compile(
            r"Rotational constants in MHz\s*:\s*\n\s*A\s*=\s*([0-9\.\-]+)\s+B\s*=\s*([0-9\.\-]+)\s+C\s*=\s*([0-9\.\-]+)",
            re.IGNORECASE
        )
        self._orca_rot_alt_pattern = re.compile(
            r"Rotational constants\s*\(MHz\)\s*:\s*\n\s*([0-9\.\-]+)\s+([0-9\.\-]+)\s+([0-9\.\-]+)",
            re.IGNORECASE
        )
        self._orca_vib_corr_pattern = re.compile(
            r"Vibrational corrections to rotational constants\s*\(MHz\)\s*:\s*\n\s*(?:Delta_?A\s*=\s*)?([0-9\.\-]+)\s+(?:Delta_?B\s*=\s*)?([0-9\.\-]+)\s+(?:Delta_?C\s*=\s*)?([0-9\.\-]+)",
            re.IGNORECASE
        )
        self._cfour_rot_pattern = re.compile(
            r"Rotational constants\s*\(in MHz\)\s*:\s*\n\s*A\s*=\s*([0-9\.\-]+)\s*\n\s*B\s*=\s*([0-9\.\-]+)\s*\n\s*C\s*=\s*([0-9\.\-]+)",
            re.IGNORECASE
        )
        self._dipole_pattern = re.compile(
            r"(?:Total Dipole Moment|Magnitude of dipole moment)\s*:\s*([0-9\.\-]+)",
            re.IGNORECASE
        )
        self._dipole_xyz_pattern = re.compile(
            r"X\s*=\s*([0-9\.\-]+)\s+Y\s*=\s*([0-9\.\-]+)\s+Z\s*=\s*([0-9\.\-]+)",
            re.IGNORECASE
        )

    def parse_log_content(self, content: str, engine_hint: Optional[str] = None) -> SpectroscopyTelemetryResult:
        """Parses output text and extracts spectroscopic observables."""
        a_e, b_e, c_e = 0.0, 0.0, 0.0
        delta_a, delta_b, delta_c = 0.0, 0.0, 0.0
        dipole_x, dipole_y, dipole_z = 0.0, 0.0, 0.0
        total_dipole = 0.0
        detected_engine = engine_hint or "orca"

        # Try ORCA standard pattern
        match_orca = self._orca_rot_mhz_pattern.search(content)
        if match_orca:
            a_e = float(match_orca.group(1))
            b_e = float(match_orca.group(2))
            c_e = float(match_orca.group(3))
            detected_engine = "orca"
        else:
            # Try ORCA alternate pattern
            match_alt = self._orca_rot_alt_pattern.search(content)
            if match_alt:
                a_e = float(match_alt.group(1))
                b_e = float(match_alt.group(2))
                c_e = float(match_alt.group(3))
                detected_engine = "orca"
            else:
                # Try CFOUR pattern
                match_cfour = self._cfour_rot_pattern.search(content)
                if match_cfour:
                    a_e = float(match_cfour.group(1))
                    b_e = float(match_cfour.group(2))
                    c_e = float(match_cfour.group(3))
                    detected_engine = "cfour"

        # Check for vibrational corrections
        match_vib = self._orca_vib_corr_pattern.search(content)
        if match_vib:
            delta_a = float(match_vib.group(1))
            delta_b = float(match_vib.group(2))
            delta_c = float(match_vib.group(3))

        # Check for dipole moments
        match_dip = self._dipole_pattern.search(content)
        if match_dip:
            total_dipole = abs(float(match_dip.group(1)))

        match_dip_xyz = self._dipole_xyz_pattern.search(content)
        if match_dip_xyz:
            dipole_x = float(match_dip_xyz.group(1))
            dipole_y = float(match_dip_xyz.group(2))
            dipole_z = float(match_dip_xyz.group(3))
            if total_dipole == 0.0:
                total_dipole = math.sqrt(dipole_x**2 + dipole_y**2 + dipole_z**2)

        # Ensure ordered rotational constants A >= B >= C
        if a_e < b_e or b_e < c_e:
            vals = sorted([a_e, b_e, c_e], reverse=True)
            a_e, b_e, c_e = vals[0], vals[1], vals[2]

        if a_e <= 0.0 or b_e <= 0.0 or c_e <= 0.0:
            raise ValueError("Failed to extract positive equilibrium rotational constants from output log.")

        # Compute ground-state effective constants B_0 = B_e + Delta B_vib
        a_0 = a_e + delta_a
        b_0 = b_e + delta_b
        c_0 = c_e + delta_c

        # Compute principal moments of inertia I = conversion / B
        i_a = INERTIA_CONVERSION_MHZ_AMU_ANG2 / a_e
        i_b = INERTIA_CONVERSION_MHZ_AMU_ANG2 / b_e
        i_c = INERTIA_CONVERSION_MHZ_AMU_ANG2 / c_e

        # Inertial defect Delta = I_c - I_a - I_b
        inertial_defect = i_c - i_a - i_b

        return SpectroscopyTelemetryResult(
            engine=detected_engine,
            a_e=a_e,
            b_e=b_e,
            c_e=c_e,
            delta_a_vib=delta_a,
            delta_b_vib=delta_b,
            delta_c_vib=delta_c,
            a_0=a_0,
            b_0=b_0,
            c_0=c_0,
            i_a=i_a,
            i_b=i_b,
            i_c=i_c,
            inertial_defect=inertial_defect,
            dipole_components=(dipole_x, dipole_y, dipole_z),
            total_dipole=total_dipole,
        )

    def parse_file(self, filepath: Union[str, Path]) -> SpectroscopyTelemetryResult:
        """Parses a physical log file on disk."""
        path = Path(filepath).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Log file not found at: {path}")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return self.parse_log_content(content)


def read_hdf5_swmr_telemetry(h5_path: Union[str, Path]) -> Dict[str, Any]:
    """Reads HDF5 telemetry in thread-safe SWMR mode protected by cross-platform FileLock.

    POSIX fcntl is strictly prohibited. [M]
    """
    path = Path(h5_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"HDF5 store not found: {path}")

    lock_file = path.with_suffix(".lock")
    lock = filelock.FileLock(str(lock_file), timeout=10.0)

    with lock:
        if h5py is None:
            raise ImportError("h5py library is required to read SWMR HDF5 telemetry.")
        
        data: Dict[str, Any] = {}
        with h5py.File(str(path), "r", swmr=True, libver="latest") as h5_file:
            for key in h5_file.keys():
                item = h5_file[key]
                if isinstance(item, h5py.Dataset):
                    data[key] = item[()]
                elif isinstance(item, h5py.Group):
                    sub_dict = {}
                    for sub_k in item.keys():
                        if isinstance(item[sub_k], h5py.Dataset):
                            sub_dict[sub_k] = item[sub_k][()]
                    data[key] = sub_dict
            for attr_k, attr_v in h5_file.attrs.items():
                data[f"attr_{attr_k}"] = attr_v

    return data
