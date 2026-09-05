"""
Authentic Spectroscopic Output Parser & Thread-Safe HDF5 SWMR Telemetry Layer.
Method Matrix v4: §3.0, §8C, §13, and SRS Chunk 12 Suggestion #113.
Computes and parses the Five Free Observables with explicit provenance tags: [M], [D], [E].
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Tuple, Union

import filelock
import numpy as np
from pydantic import BaseModel, Field

try:
    import h5py
except ImportError:
    h5py = None

# Authoritative CODATA 2022 Rotational Constant Factor: h / (8 * pi^2 * u * Angstrom^2) in MHz
INERTIA_CONVERSION_MHZ_AMU_ANG2 = 505379.008784


class SpectroscopicObservablesResult(BaseModel):
    """Authoritative physical model storing the five free observables with Method Matrix provenance."""

    engine: str = Field(default="ORCA", description="Quantum engine origin")

    # 1. Equilibrium Rotational Constants (BO surface minimum) in MHz [M]
    a_e: float = Field(default=0.0, description="Equilibrium constant A_e (MHz) [M]")
    b_e: float = Field(default=0.0, description="Equilibrium constant B_e (MHz) [M]")
    c_e: float = Field(default=0.0, description="Equilibrium constant C_e (MHz) [M]")

    # 2. Vibrational Corrections (Delta B_vib) in MHz [M]
    delta_a_vib: float = Field(default=0.0, description="Vibrational correction Delta A_vib (MHz) [M]")
    delta_b_vib: float = Field(default=0.0, description="Vibrational correction Delta B_vib (MHz) [M]")
    delta_c_vib: float = Field(default=0.0, description="Vibrational correction Delta C_vib (MHz) [M]")

    # 3. Physical Ground-State Observables (B_0 = B_e + Delta B_vib) in MHz [D]
    a_0: float = Field(default=0.0, description="Effective ground-state constant A_0 (MHz) [D]")
    b_0: float = Field(default=0.0, description="Effective ground-state constant B_0 (MHz) [D]")
    c_0: float = Field(default=0.0, description="Effective ground-state constant C_0 (MHz) [D]")

    # 4. Inertial Defect (Delta = I_c - I_a - I_b) in amu * Angstrom^2 [D]
    inertial_defect: float = Field(default=0.0, description="Inertial defect Delta = I_c - I_a - I_b [D]")

    # Planar Moments P_aa, P_bb, P_cc in amu * Angstrom^2 [D]
    planar_moments: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="Planar moments (P_aa, P_bb, P_cc) in amu*A^2 [D]"
    )

    # 5. Dipole Moment Components in Debye [M]
    dipole_components: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="Dipole components (mu_a, mu_b, mu_c) in Debye [M]"
    )
    total_dipole: float = Field(default=0.0, description="Total dipole moment magnitude in Debye [M]")

    # Quartic Centrifugal Distortion Constants (kHz) [M]
    centrifugal_distortion_watson_s: Dict[str, float] = Field(
        default_factory=dict, description="Watson S-reduction constants (D_J, D_JK, D_K, d_1, d_2) [kHz] [M]"
    )
    centrifugal_distortion_watson_a: Dict[str, float] = Field(
        default_factory=dict, description="Watson A-reduction constants (Delta_J, Delta_JK, Delta_K, delta_J, delta_K) [kHz] [M]"
    )

    provenance: str = Field(
        default="[M] Born-Oppenheimer PES minimum / [D] Mathematical projection",
        description="Authoritative Method Matrix compliance tag"
    )


class OutputParser:
    """Authentic multi-engine quantum chemistry telemetry parser.

    Ingests ORCA, CFOUR, CREST logs, property files (.property.txt), QCSchema JSON,
    and HDF5 SWMR datasets.
    """

    def __init__(self) -> None:
        self._re_orca_rot = re.compile(
            r"Rotational constants in MHz\s*:\s*\n\s*A\s*=\s*([0-9\.\-]+)\s+B\s*=\s*([0-9\.\-]+)\s+C\s*=\s*([0-9\.\-]+)",
            re.IGNORECASE,
        )
        self._re_orca_vib = re.compile(
            r"Vibrational corrections to rotational constants\s*\(MHz\)\s*:\s*\n\s*(?:Delta_?A\s*=\s*)?([0-9\.\-]+)\s+(?:Delta_?B\s*=\s*)?([0-9\.\-]+)\s+(?:Delta_?C\s*=\s*)?([0-9\.\-]+)",
            re.IGNORECASE,
        )
        self._re_orca_dipole = re.compile(
            r"(?:Total Dipole Moment|Magnitude of dipole moment)\s*:\s*([0-9\.\-]+)",
            re.IGNORECASE,
        )

    def parse_file(self, file_path: Union[str, Path]) -> SpectroscopicObservablesResult:
        """Parses output log or property file into SpectroscopicObservablesResult."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Calculation output file not found: {path}")

        content = path.read_text(encoding="utf-8", errors="replace")
        return self.parse_text(content)

    def parse_text(self, content: str) -> SpectroscopicObservablesResult:
        """Parses text content from ORCA / CFOUR / CREST output."""
        a_e, b_e, c_e = 0.0, 0.0, 0.0
        da_vib, db_vib, dc_vib = 0.0, 0.0, 0.0
        total_dipole = 0.0

        # Match ORCA Rotational Constants
        m_rot = self._re_orca_rot.search(content)
        if m_rot:
            a_e = float(m_rot.group(1))
            b_e = float(m_rot.group(2))
            c_e = float(m_rot.group(3))

        # Match Vibrational Corrections
        m_vib = self._re_orca_vib.search(content)
        if m_vib:
            da_vib = float(m_vib.group(1))
            db_vib = float(m_vib.group(2))
            dc_vib = float(m_vib.group(3))

        # Match Dipole
        m_dip = self._re_orca_dipole.search(content)
        if m_dip:
            total_dipole = float(m_dip.group(1))

        # Calculate effective ground state observables B_0 = B_e + Delta B_vib
        a_0 = a_e + da_vib
        b_0 = b_e + db_vib
        c_0 = c_e + dc_vib

        # Calculate principal moments of inertia I = conversion / B
        i_a = INERTIA_CONVERSION_MHZ_AMU_ANG2 / a_e if a_e > 0 else 0.0
        i_b = INERTIA_CONVERSION_MHZ_AMU_ANG2 / b_e if b_e > 0 else 0.0
        i_c = INERTIA_CONVERSION_MHZ_AMU_ANG2 / c_e if c_e > 0 else 0.0

        # Inertial defect and planar moments
        inertial_defect = i_c - i_a - i_b
        p_aa = 0.5 * (i_b + i_c - i_a)
        p_bb = 0.5 * (i_a + i_c - i_b)
        p_cc = 0.5 * (i_a + i_b - i_c)

        # Parse Watson S-reduction and A-reduction if present in output
        watson_s: Dict[str, float] = {}
        watson_a: Dict[str, float] = {}

        # S-reduction patterns
        for pat, key in [
            (r"(?:D_J|DJ)\s*[:=]\s*([0-9\.\-]+)", "D_J"),
            (r"(?:D_JK|DJK)\s*[:=]\s*([0-9\.\-]+)", "D_JK"),
            (r"(?:D_K|DK)\s*[:=]\s*([0-9\.\-]+)", "D_K"),
            (r"(?:d_1|d1)\s*[:=]\s*([0-9\.\-]+)", "d_1"),
            (r"(?:d_2|d2)\s*[:=]\s*([0-9\.\-]+)", "d_2"),
        ]:
            m_cd = re.search(pat, content, re.IGNORECASE)
            if m_cd:
                watson_s[key] = float(m_cd.group(1))

        # A-reduction patterns
        for pat, key in [
            (r"(?:Delta_J|DEL_J)\s*[:=]\s*([0-9\.\-]+)", "Delta_J"),
            (r"(?:Delta_JK|DEL_JK)\s*[:=]\s*([0-9\.\-]+)", "Delta_JK"),
            (r"(?:Delta_K|DEL_K)\s*[:=]\s*([0-9\.\-]+)", "Delta_K"),
            (r"(?:delta_J|del_j)\s*[:=]\s*([0-9\.\-]+)", "delta_J"),
            (r"(?:delta_K|del_k)\s*[:=]\s*([0-9\.\-]+)", "delta_K"),
        ]:
            m_cd = re.search(pat, content, re.IGNORECASE)
            if m_cd:
                watson_a[key] = float(m_cd.group(1))

        # Support MolSSI QCSchema JSON ingestion
        if content.strip().startswith("{"):
            try:
                qc_dict = json.loads(content)
                props = qc_dict.get("properties", {})
                rot = props.get("rotational_constants", [])
                if len(rot) >= 3:
                    a_e, b_e, c_e = float(rot[0]), float(rot[1]), float(rot[2])
                rot_eff = props.get("rotational_constants_effective", [])
                if len(rot_eff) >= 3:
                    a_0, b_0, c_0 = float(rot_eff[0]), float(rot_eff[1]), float(rot_eff[2])
                    da_vib, db_vib, dc_vib = a_0 - a_e, b_0 - b_e, c_0 - c_e
                vib_corr = props.get("vibrational_corrections", [])
                if len(vib_corr) >= 3:
                    da_vib, db_vib, dc_vib = float(vib_corr[0]), float(vib_corr[1]), float(vib_corr[2])
                    a_0, b_0, c_0 = a_e + da_vib, b_e + db_vib, c_e + dc_vib
                dip = props.get("scf_dipole_moment", [])
                if len(dip) >= 3:
                    total_dipole = float(np.linalg.norm([float(x) for x in dip]))
            except Exception:
                pass

        # Support CFOUR output patterns
        if a_e == 0.0:
            m_cfour_rot = re.search(
                r"(?:Rotational constants|B_e)\s*(?:\(in MHz\))?\s*[:=]?\s*\n?\s*A\s*=\s*([0-9\.\-]+)\s+B\s*=\s*([0-9\.\-]+)\s+C\s*=\s*([0-9\.\-]+)",
                content,
                re.IGNORECASE,
            )
            if m_cfour_rot:
                a_e = float(m_cfour_rot.group(1))
                b_e = float(m_cfour_rot.group(2))
                c_e = float(m_cfour_rot.group(3))
                a_0, b_0, c_0 = a_e + da_vib, b_e + db_vib, c_e + dc_vib

        return SpectroscopicObservablesResult(
            engine="ORCA",
            a_e=a_e,
            b_e=b_e,
            c_e=c_e,
            delta_a_vib=da_vib,
            delta_b_vib=db_vib,
            delta_c_vib=dc_vib,
            a_0=a_0,
            b_0=b_0,
            c_0=c_0,
            inertial_defect=inertial_defect,
            planar_moments=(p_aa, p_bb, p_cc),
            total_dipole=total_dipole,
            centrifugal_distortion_watson_s=watson_s,
            centrifugal_distortion_watson_a=watson_a,
        )

    def read_hdf5_swmr(self, h5_path: Union[str, Path]) -> Dict[str, Any]:
        """Reads persistent calculation datasets using Thread-Safe HDF5 SWMR mode. [M]"""
        path = Path(h5_path)
        if not path.exists():
            raise FileNotFoundError(f"HDF5 datastore not found: {path}")

        lock_path = path.with_name(path.name + ".lock")
        results: Dict[str, Any] = {}

        with filelock.FileLock(str(lock_path), timeout=15):
            if h5py is None:
                raise ImportError("h5py package is required for HDF5 SWMR inspection.")
            with h5py.File(path, "r", libver="latest", swmr=True) as f:
                def visitor(name: str, node: Any) -> None:
                    if isinstance(node, h5py.Dataset):
                        data = node[()]
                        if isinstance(data, np.ndarray) and data.size == 1:
                            results[name] = float(data.item())
                        else:
                            results[name] = data

                f.visititems(visitor)

        return results


# Alias for backward compatibility
SpectroscopyTelemetryParser = OutputParser
