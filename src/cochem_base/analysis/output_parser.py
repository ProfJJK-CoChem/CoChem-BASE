"""
Authentic Spectroscopic Output Parser & Thread-Safe HDF5 SWMR Telemetry Layer.
Method Matrix v4: §3.0, §8C, §13, and SRS Chunk 12 Suggestion #113.
Computes and parses the Five Free Observables with explicit provenance tags: [M], [D], [E].
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, Field

try:
    import h5py
except ImportError:
    h5py = None

# Authoritative CODATA 2022 Rotational Constant Factor: h / (8 * pi^2 * u * Angstrom^2) in MHz
from cochem_base.core.cochem_constants import C_ROT_MHZ_U_ANG2

INERTIA_CONVERSION_MHZ_AMU_ANG2 = C_ROT_MHZ_U_ANG2


class SpectroscopicObservablesResult(BaseModel):
    """Authoritative physical model storing the five free observables with Method Matrix provenance."""

    engine: str = Field(default="ORCA", description="Quantum engine origin")

    # 1. Equilibrium Rotational Constants (BO surface minimum) in MHz [M]
    a_e: float = Field(gt=0, allow_inf_nan=False, description="Equilibrium constant A_e (MHz) [M]")
    b_e: float = Field(gt=0, allow_inf_nan=False, description="Equilibrium constant B_e (MHz) [M]")
    c_e: float = Field(gt=0, allow_inf_nan=False, description="Equilibrium constant C_e (MHz) [M]")

    # 2. Vibrational Corrections (Delta B_vib) in MHz [M]
    delta_a_vib: Optional[float] = Field(default=None, description="Vibrational correction Delta A_vib (MHz) [M]")
    delta_b_vib: Optional[float] = Field(default=None, description="Vibrational correction Delta B_vib (MHz) [M]")
    delta_c_vib: Optional[float] = Field(default=None, description="Vibrational correction Delta C_vib (MHz) [M]")

    # 3. Physical Ground-State Observables (B_0 = B_e + Delta B_vib) in MHz [D]
    a_0: Optional[float] = Field(default=None, description="Effective ground-state constant A_0 (MHz) [D]")
    b_0: Optional[float] = Field(default=None, description="Effective ground-state constant B_0 (MHz) [D]")
    c_0: Optional[float] = Field(default=None, description="Effective ground-state constant C_0 (MHz) [D]")

    # 4. Inertial Defect (Delta = I_c - I_a - I_b) in amu * Angstrom^2 [D]
    inertial_defect: Optional[float] = Field(default=None, description="Inertial defect Delta = I_c - I_a - I_b [D]")

    # Planar Moments P_aa, P_bb, P_cc in amu * Angstrom^2 [D]
    planar_moments: Optional[Tuple[float, float, float]] = Field(
        default=None, description="Planar moments (P_aa, P_bb, P_cc) in amu*A^2 [D]"
    )

    # 5. Dipole Moment Components in Debye [M]
    dipole_components: Optional[Tuple[float, float, float]] = Field(
        default=None, description="Dipole components (mu_a, mu_b, mu_c) in Debye [M]"
    )
    total_dipole: Optional[float] = Field(default=None, description="Total dipole moment magnitude in Debye [M]")

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

    _number = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"

    @staticmethod
    def _finite(value: Any) -> float:
        number = float(str(value).replace("D", "E").replace("d", "e"))
        if not np.isfinite(number):
            raise ValueError("Spectroscopic observables must be finite")
        return number

    def parse_file(self, file_path: Union[str, Path]) -> SpectroscopicObservablesResult:
        """Read engine output without manufacturing values for missing properties."""
        return self.parse_text(Path(file_path).read_text(encoding="utf-8", errors="strict"))

    def parse_text(self, content: str) -> SpectroscopicObservablesResult:
        """Parse equilibrium constants in MHz; preserve missing corrections as None.

        JSON rotational properties use the CoChem extension in MHz. QCSchema's
        scf_dipole_moment is in atomic units and is explicitly converted to Debye.
        No calculation-completion claim is inferred by this property parser.
        """
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Empty spectroscopic output")
        rotation = corrections = effective = dipole_components = None
        total_dipole = None
        engine = "ORCA" if "ORCA" in content.upper() else "CFOUR" if "CFOUR" in content.upper() else "unknown"
        if content.lstrip().startswith("{"):
            record = json.loads(content)
            if record.get("success") is False:
                raise ValueError("Cannot accept properties from a failed calculation")
            properties = record.get("properties", {})
            if properties.get("rotational_constants_units", "MHz").lower() != "mhz":
                raise ValueError("Rotational constants must be supplied in MHz")
            def triple(key: str):
                value = properties.get(key)
                if value is None:
                    return None
                if not isinstance(value, (list, tuple)) or len(value) != 3:
                    raise ValueError(f"{key} must contain exactly three values")
                return tuple(self._finite(item) for item in value)
            rotation = triple("rotational_constants")
            corrections = triple("vibrational_corrections")
            effective = triple("rotational_constants_effective")
            dipole_components = triple("scf_dipole_moment")
            if dipole_components is not None:
                from scipy.constants import physical_constants, speed_of_light
                au_to_debye = physical_constants["atomic unit of electric dipole mom."][0] / (1e-21 / speed_of_light)
                dipole_components = tuple(value * au_to_debye for value in dipole_components)
                total_dipole = float(np.linalg.norm(dipole_components))
            engine = str(record.get("provenance", {}).get("creator", "QCSchema"))
        else:
            number = self._number
            rotation_match = re.search(
                rf"(?:Rotational constants(?: in MHz|\s*\((?:in )?MHz\))?|B_e)\s*[:=]?\s*"
                rf"A\s*=\s*({number})\s+B\s*=\s*({number})\s+C\s*=\s*({number})",
                content, re.IGNORECASE,
            )
            if rotation_match is None:
                rotation_match = re.search(
                    rf"Rotational constants in MHz\s*:\s*({number})\s+({number})\s+({number})",
                    content, re.IGNORECASE,
                )
            if rotation_match:
                rotation = tuple(self._finite(v) for v in rotation_match.groups())
            correction_match = re.search(
                rf"Vibrational corrections to rotational constants\s*\(MHz\)\s*:\s*"
                rf"(?:Delta_?A\s*=\s*)?({number})\s+(?:Delta_?B\s*=\s*)?({number})\s+(?:Delta_?C\s*=\s*)?({number})",
                content, re.IGNORECASE,
            )
            if correction_match:
                corrections = tuple(self._finite(v) for v in correction_match.groups())
            dipole_match = re.search(
                rf"(?:Total Dipole Moment|Magnitude of dipole moment)\s*(?:\(Debye\))?\s*:\s*({number})\s*Debye",
                content, re.IGNORECASE,
            )
            if dipole_match:
                total_dipole = self._finite(dipole_match.group(1))

        if rotation is None or any(value <= 0 for value in rotation):
            raise ValueError("Missing or nonpositive equilibrium rotational constants in MHz")
        if effective is not None:
            implied = tuple(value - equilibrium for value, equilibrium in zip(effective, rotation))
            if corrections is not None and not np.allclose(implied, corrections, rtol=1e-8, atol=1e-6):
                raise ValueError("Effective constants contradict vibrational corrections")
            corrections = implied
        elif corrections is not None:
            effective = tuple(value + correction for value, correction in zip(rotation, corrections))
        if effective is not None and any(value <= 0 for value in effective):
            raise ValueError("Effective rotational constants must be positive")
        if total_dipole is not None and total_dipole < 0:
            raise ValueError("Dipole magnitude must be nonnegative")

        inertia = np.asarray([INERTIA_CONVERSION_MHZ_AMU_ANG2 / value for value in rotation])
        i_a, i_b, i_c = inertia
        watson_s, watson_a = {}, {}
        # Case matters: Delta_J and delta_J are physically different constants.
        for keys, destination in [
            ([("D_J", "DJ"), ("D_JK", "DJK"), ("D_K", "DK"), ("d_1", "d1"), ("d_2", "d2")], watson_s),
            ([("Delta_J", "DEL_J"), ("Delta_JK", "DEL_JK"), ("Delta_K", "DEL_K"), ("delta_J", "del_j"), ("delta_K", "del_k")], watson_a),
        ]:
            for key, alias in keys:
                match = re.search(rf"(?<!\w)(?:{key}|{alias})\s*[:=]\s*({self._number})", content)
                if match:
                    destination[key] = self._finite(match.group(1))
        correction_values = corrections if corrections is not None else (None, None, None)
        effective_values = effective if effective is not None else (None, None, None)
        return SpectroscopicObservablesResult(
            engine=engine, a_e=rotation[0], b_e=rotation[1], c_e=rotation[2],
            delta_a_vib=correction_values[0], delta_b_vib=correction_values[1], delta_c_vib=correction_values[2],
            a_0=effective_values[0], b_0=effective_values[1], c_0=effective_values[2],
            inertial_defect=float(i_c - i_a - i_b),
            planar_moments=(float((i_b+i_c-i_a)/2), float((i_a+i_c-i_b)/2), float((i_a+i_b-i_c)/2)),
            dipole_components=dipole_components, total_dipole=total_dipole,
            centrifugal_distortion_watson_s=watson_s, centrifugal_distortion_watson_a=watson_a,
            provenance="Parsed engine properties; inertia derived from equilibrium constants; missing properties remain unavailable",
        )

    def read_hdf5_swmr(self, h5_path: Union[str, Path]) -> Dict[str, Any]:
        """Reads persistent calculation datasets using Thread-Safe HDF5 SWMR mode. [M]"""
        path = Path(h5_path)
        if not path.exists():
            raise FileNotFoundError(f"HDF5 datastore not found: {path}")

        results: Dict[str, Any] = {}

        if h5py is None:
            raise ImportError("h5py package is required for HDF5 SWMR inspection.")
        # Readers use HDF5's SWMR visibility protocol without taking the writer lock.
        with h5py.File(path, "r", libver="latest", swmr=True) as f:
            def visitor(name: str, node: Any) -> None:
                if isinstance(node, h5py.Dataset):
                    node.refresh()
                    data = node[()]
                    results[name] = data.item() if isinstance(data, np.ndarray) and data.size == 1 else data
            f.visititems(visitor)

        return results


# Alias for backward compatibility
SpectroscopyTelemetryParser = OutputParser
