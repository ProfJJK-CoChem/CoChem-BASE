"""
Authentic Spectroscopic Telemetry Parser & Cross-Platform HDF5 Concurrency Layer.
Method Matrix v4: §3.0, §8C, §13, and SRS Chunk 4 Suggestion #34.
Strictly distinguishes Born-Oppenheimer theoretical B_e from experimental ground-state B_0.
Uses short SWMR reader snapshots alongside the canonical atomic writer lock.
"""
from __future__ import annotations

import math
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

from cochem_base.core.cochem_constants import C_ROT_MHZ_U_ANG2, SPEED_OF_LIGHT_CM_S

try:
    import h5py
except ImportError:
    h5py = None  # type: ignore

# CODATA 2022 Conversion Constant: h / (8 * pi^2) in MHz * amu * Angstrom^2
INERTIA_CONVERSION_MHZ_AMU_ANG2 = C_ROT_MHZ_U_ANG2


class SpectroscopicConstantRecord(BaseModel):
    """Schema for individual rotational and vibrational constants with provenance."""

    name: str = Field(..., description="Observable symbol, e.g. A_e, B_0")
    value: float = Field(..., description="Numerical value in MHz or amu*Angstrom^2")
    unit: str = Field(default="MHz", description="Unit of physical measurement")
    provenance: str = Field(..., description="Method Matrix provenance tag: [M], [D], [E]")
    description: str = Field(default="", description="Theoretical or experimental definition")


class SpectroscopicTelemetryResult(BaseModel):
    """Reported geometry constants and separately supplied vibrational corrections.

    Historical ``*_e`` field names are retained for compatibility. An output
    property's presence alone does not establish a stationary PES minimum.
    """

    engine: str = Field(..., description="Source quantum chemical engine")
    # Equilibrium constants at Born-Oppenheimer PES minimum [M]
    a_e: float = Field(..., description="Equilibrium rotational constant A_e (MHz) [M]")
    b_e: float = Field(..., description="Equilibrium rotational constant B_e (MHz) [M]")
    c_e: float = Field(..., description="Equilibrium rotational constant C_e (MHz) [M]")

    # Vibrational zero-point corrections [M]
    delta_a_vib: Optional[float] = Field(default=None, description="Vibrational correction Delta A_vib (MHz) [M]")
    delta_b_vib: Optional[float] = Field(default=None, description="Vibrational correction Delta B_vib (MHz) [M]")
    delta_c_vib: Optional[float] = Field(default=None, description="Vibrational correction Delta C_vib (MHz) [M]")

    # Effective vibrational ground-state constants [D]
    a_0: Optional[float] = Field(default=None, description="Ground-state rotational constant A_0 = A_e + Delta A_vib (MHz) [D]")
    b_0: Optional[float] = Field(default=None, description="Ground-state rotational constant B_0 = B_e + Delta B_vib (MHz) [D]")
    c_0: Optional[float] = Field(default=None, description="Ground-state rotational constant C_0 = C_e + Delta C_vib (MHz) [D]")

    # Principal moments of inertia (amu * Angstrom^2) [D]
    i_a: float = Field(..., description="Principal moment of inertia I_a (amu*Angstrom^2) [D]")
    i_b: float = Field(..., description="Principal moment of inertia I_b (amu*Angstrom^2) [D]")
    i_c: float = Field(..., description="Principal moment of inertia I_c (amu*Angstrom^2) [D]")

    # Inertial defect Delta = I_c - I_a - I_b (amu * Angstrom^2) [D]
    inertial_defect: float = Field(..., description="Inertial defect Delta = I_c - I_a - I_b [D]")

    # Dipole moments (Debye) [M]
    dipole_components: Optional[Tuple[float, float, float]] = Field(default=None, description="Dipole components (mu_a, mu_b, mu_c) in Debye [M]")
    total_dipole: Optional[float] = Field(default=None, description="Total dipole moment magnitude in Debye [M]")

    equilibrium_geometry_verified: bool = False
    rotational_constant_scope: str = "Native reported rotational constants at the output geometry; a stationary equilibrium geometry is not established."
    ground_state_constant_scope: str = "Missing: a harmonic calculation alone does not provide ground-state vibrational corrections."
    dipole_component_frame: Optional[str] = None
    source_sha256: Optional[str] = None
    source_filename: Optional[str] = None
    reported_rotational_unit: str = "MHz"
    reported_rotational_constants: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    reported_axis_order: Tuple[str, str, str] = ("A", "B", "C")

    provenance_banner: str = Field(
        default="Geometry rotational constants are distinguished from equilibrium B_e and ground-state B_0; an imported property log does not by itself establish stationarity or spectroscopic accuracy.",
        description="Methodological compliance notice"
    )


SpectroscopyTelemetryResult = SpectroscopicTelemetryResult


class SpectroscopyTelemetryParser:
    """Parses ORCA and CFOUR output logs into authentic physical telemetry structures."""

    def __init__(self) -> None:
        number = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
        # ORCA 6 prints a single line with optional whitespace before ':'.
        # Older ORCA/CFOUR layouts use named axes on one or three lines.
        self._rot_pattern = re.compile(
            rf"Rotational constants\s*(?:in\s+|\(\s*(?:in\s+)?)(MHz|GHz|cm(?:\*\*|\^)?-1)\s*\)?\s*:\s*"
            rf"(?:A\s*=\s*)?({number})\s+(?:B\s*=\s*)?({number})\s+(?:C\s*=\s*)?({number})",
            re.IGNORECASE,
        )
        self._orca_vib_corr_pattern = re.compile(
            rf"Vibrational corrections to rotational constants\s*\(MHz\)\s*:\s*(?:Delta_?A\s*=\s*)?({number})\s+(?:Delta_?B\s*=\s*)?({number})\s+(?:Delta_?C\s*=\s*)?({number})",
            re.IGNORECASE
        )
        self._dipole_pattern = re.compile(
            rf"(?:Magnitude\s*\(Debye\)\s*:\s*|(?:Total Dipole Moment|Magnitude of dipole moment)\s*:\s*)({number})\s*(?:Debye)?",
            re.IGNORECASE
        )
        self._dipole_xyz_pattern = re.compile(
            rf"X\s*=\s*({number})\s+Y\s*=\s*({number})\s+Z\s*=\s*({number})",
            re.IGNORECASE
        )
        self._rot_axis_dipole_pattern = re.compile(
            rf"x,y,z\s*\[Debye\]\s*:\s*({number})\s+({number})\s+({number})", re.IGNORECASE,
        )
        self._cfour_total_dipole_pattern = re.compile(
            rf"Total dipole moment\s*\n\s*-+\s*\n\s*au\s+Debye\s*\n\s*"
            rf"x\s+{number}\s+({number})\s*\n\s*y\s+{number}\s+({number})\s*\n\s*z\s+{number}\s+({number})",
            re.IGNORECASE,
        )

    def parse_log_content(self, content: str, engine_hint: Optional[str] = None) -> SpectroscopyTelemetryResult:
        """Parses output text and extracts spectroscopic observables."""
        a_e, b_e, c_e = 0.0, 0.0, 0.0
        delta_a = delta_b = delta_c = None
        dipole_components = None
        total_dipole = None
        detected_engine = engine_hint or "orca"

        def value(text: str) -> float:
            result = float(text.replace("D", "E").replace("d", "e"))
            if not math.isfinite(result):
                raise ValueError("Spectroscopy values must be finite")
            return result

        matches = list(self._rot_pattern.finditer(content))
        # Prefer the last explicitly reported MHz block over rounded cm^-1
        # duplicates. Without MHz, convert the last native unit-labelled block.
        mhz_matches = [m for m in matches if m.group(1).lower() == "mhz"]
        match = mhz_matches[-1] if mhz_matches else matches[-1] if matches else None
        reported_unit = match.group(1) if match else "MHz"
        if match:
            factor = (1.0 if reported_unit.lower() == "mhz" else
                      1000.0 if reported_unit.lower() == "ghz" else SPEED_OF_LIGHT_CM_S / 1e6)
            a_e, b_e, c_e = (value(match.group(i)) * factor for i in (2, 3, 4))
            if "CFOUR" in content.upper() or "Rotational constants (in MHz)" in match.group(0):
                detected_engine = engine_hint or "cfour"
        reported_values = (a_e, b_e, c_e)
        reported_axes = ("A", "B", "C")
        if match and detected_engine.lower() == "cfour" and not re.search(r"[ABC]\s*=", match.group(0), re.I):
            # Native CFOUR prints an unlabelled native-axis triplet, and its
            # rotcon2 block can permute these axes. Keep the original order and
            # its explicit canonical mapping while deriving A >= B >= C.
            order = sorted(range(3), key=lambda index: (-reported_values[index], index))
            mapping = {index: axis for axis, index in zip(("A", "B", "C"), order, strict=True)}
            reported_axes = tuple(mapping[index] for index in range(3))
            a_e, b_e, c_e = (reported_values[index] for index in order)

        # Check for vibrational corrections
        vibration_matches = list(self._orca_vib_corr_pattern.finditer(content))
        match_vib = vibration_matches[-1] if vibration_matches else None
        if match_vib:
            delta_a, delta_b, delta_c = (value(match_vib.group(i)) for i in (1, 2, 3))

        # Check for dipole moments
        # ORCA's 'Total Dipole Moment' three-vector is in atomic units. Only
        # explicitly Debye-labelled magnitudes/components are admitted here.
        matches_dip = [m for m in self._dipole_pattern.finditer(content)
                       if "debye" in m.group(0).lower()]
        if matches_dip:
            total_dipole = abs(value(matches_dip[-1].group(1)))

        frame = None
        axis_matches = list(self._rot_axis_dipole_pattern.finditer(content))
        match_dip_xyz = axis_matches[-1] if axis_matches else None
        if match_dip_xyz:
            frame = "reported rotational principal axes"
        else:
            # Legacy labelled XYZ forms are supported only beside a declared
            # Debye dipole property, not arbitrary Cartesian XYZ coordinates.
            xyz_matches = [m for m in self._dipole_xyz_pattern.finditer(content)
                           if any(0 <= m.start() - d.end() < 200 for d in matches_dip)]
            match_dip_xyz = xyz_matches[-1] if xyz_matches else None
            if match_dip_xyz:
                frame = "reported Cartesian axes"
        if match_dip_xyz:
            dipole_components = tuple(value(match_dip_xyz.group(i)) for i in (1, 2, 3))
            if total_dipole is None:
                total_dipole = math.sqrt(sum(component ** 2 for component in dipole_components))
        if detected_engine.lower() == "cfour":
            cfour_dipoles = list(self._cfour_total_dipole_pattern.finditer(content))
            if cfour_dipoles:
                dipole_components = tuple(value(cfour_dipoles[-1].group(i)) for i in (1, 2, 3))
                total_dipole = math.sqrt(sum(component ** 2 for component in dipole_components))
                frame = "reported native Cartesian axes"

        # Axis labels also index vibrational corrections: never silently reorder.
        if a_e < b_e or b_e < c_e:
            raise ValueError("Rotational constants must preserve their reported A >= B >= C axis labels.")

        if a_e <= 0.0 or b_e <= 0.0 or c_e <= 0.0:
            raise ValueError("Failed to extract positive unit-labelled rotational constants from output log.")

        # Compute ground-state effective constants B_0 = B_e + Delta B_vib
        a_0 = a_e + delta_a if delta_a is not None else None
        b_0 = b_e + delta_b if delta_b is not None else None
        c_0 = c_e + delta_c if delta_c is not None else None

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
            dipole_components=dipole_components,
            total_dipole=total_dipole,
            dipole_component_frame=frame,
            reported_rotational_unit=reported_unit,
            reported_rotational_constants=reported_values,
            reported_axis_order=reported_axes,
            ground_state_constant_scope=("Derived from the explicitly reported MHz vibrational corrections; their physical origin, stationary geometry and accuracy are not independently established by this import." if match_vib else
                                         "Missing: a harmonic calculation alone does not provide ground-state vibrational corrections."),
        )

    def parse_file(self, filepath: Union[str, Path]) -> SpectroscopyTelemetryResult:
        """Parses a physical log file on disk."""
        path = Path(filepath).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Log file not found at: {path}")
        raw = path.read_bytes()
        result = self.parse_log_content(raw.decode("utf-8-sig", errors="replace"))
        result.source_sha256 = hashlib.sha256(raw).hexdigest()
        result.source_filename = path.name
        return result


def read_hdf5_swmr_telemetry(h5_path: Union[str, Path]) -> Dict[str, Any]:
    """Return bounded nested SWMR observations without taking the writer lock.

    Scientific trajectories expose only their captured committed prefix. This
    compatibility view is a bounded inspection, not a scientific qualification.
    """
    from cochem_base.core_engine.scientific_writer import scientific_reader_snapshot
    path = Path(h5_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"HDF5 store not found: {path}")

    with scientific_reader_snapshot(store_path=path):
        if h5py is None:
            raise ImportError("h5py library is required to read SWMR HDF5 telemetry.")
        data: Dict[str, Any] = {}
        for row in read_hdf5_dataset_previews(path):
            parent = data
            parts = row["name"].split("/")
            for component in parts[:-1]:
                parent = parent.setdefault(component, {})
            parent[parts[-1]] = row["values"]
        with h5py.File(str(path), "r", swmr=True, libver="latest") as h5_file:
            for attr_k, attr_v in h5_file.attrs.items():
                data[f"attr_{attr_k}"] = attr_v

    return data


def read_hdf5_dataset_previews(h5_path: Union[str, Path], *, limit: int = 500) -> List[Dict[str, Any]]:
    """Read bounded nested dataset previews with shape, units and source attributes.

    The numerical store remains authoritative; previews never synthesize missing
    arrays and never materialize an unbounded trajectory into the browser kernel.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("HDF5 preview limit must be an integer from 1 to 500")
    if h5py is None:
        raise ImportError("h5py is required for the HDF5 inspector")
    from cochem_base.core_engine.scientific_writer import scientific_reader_snapshot
    path = Path(h5_path).resolve(strict=True)
    rows = []
    views = {}

    def scientific_view(item):
        """Capture one count boundary per canonical trajectory, without copies."""
        group = item.parent
        required = {"committed_records", "coordinates_angstrom", "energy_hartree", "metadata_json"}
        if (len(group.name.strip("/").split("/")) != 2
                or not group.name.startswith("/trajectories/") or not required.issubset(group.keys())):
            return item.shape, None
        if group.name not in views:
            group["committed_records"].refresh()
            count = int(group["committed_records"][()])
            if count < 0:
                raise ValueError("Scientific telemetry has a negative committed record count")
            for name in ("coordinates_angstrom", "energy_hartree", "metadata_json"):
                group[name].refresh()
                if not group[name].shape or group[name].shape[0] < count:
                    raise ValueError("Committed scientific observations are incomplete")
            gradients = 0
            if "gradient_record_indices" in group and "gradients_hartree_per_bohr" in group:
                indices = group["gradient_record_indices"]
                vectors = group["gradients_hartree_per_bohr"]
                if "committed_gradients" in group:
                    group["committed_gradients"].refresh()
                    published = int(group["committed_gradients"][()])
                else:
                    indices.refresh()
                    vectors.refresh()
                    published = min(indices.shape[0], vectors.shape[0])
                indices.refresh()
                vectors.refresh()
                if published < 0 or indices.shape[0] < published or vectors.shape[0] < published:
                    raise ValueError("Committed scientific gradients are incomplete")
                # An independent writer can advance while this snapshot opens.
                # Its gradient prefix is sorted by the true measured record
                # index; binary search avoids materializing a large trajectory.
                left, right = 0, published
                while left < right:
                    middle = (left + right) // 2
                    observed = int(indices[middle])
                    if observed < 0:
                        raise ValueError("Committed scientific gradient index is invalid")
                    if observed < count:
                        left = middle + 1
                    else:
                        right = middle
                gradients = left
            views[group.name] = (count, gradients)
        count, gradients = views[group.name]
        name = item.name.rsplit("/", 1)[-1]
        if name == "committed_records":
            return item.shape, count
        if name == "committed_gradients":
            return item.shape, gradients
        if name in {"coordinates_angstrom", "energy_hartree", "metadata_json"}:
            return (count, *item.shape[1:]), None
        if name in {"gradient_record_indices", "gradients_hartree_per_bohr"}:
            return (gradients, *item.shape[1:]), None
        return item.shape, None

    with scientific_reader_snapshot(store_path=path):
        with h5py.File(path, "r", swmr=True, libver="latest") as handle:
            def visit(name, item):
                if not isinstance(item, h5py.Dataset):
                    return None
                if len(rows) >= 100:
                    return "dataset-preview-limit"
                item.refresh()
                shape, committed_scalar = scientific_view(item)
                total = math.prod(shape)
                if not shape:
                    values = committed_scalar if committed_scalar is not None else item[()]
                    count = 1
                elif total == 0:
                    values = []
                    count = 0
                else:
                    # A bounded hyper-rectangle supports scalar through tensor datasets.
                    remaining = limit
                    slices = []
                    for dimension in reversed(shape):
                        size = min(dimension, remaining)
                        slices.insert(0, slice(0, size))
                        remaining = max(1, remaining // max(size, 1))
                    values = item[tuple(slices)]
                    count = int(values.size)
                rows.append({"name": name, "shape": shape, "stored_shape": item.shape, "dtype": str(item.dtype),
                             "units": item.attrs.get("units", item.attrs.get("unit", "[MISSING DATA]")),
                             "source": item.attrs.get("source", "[MISSING DATA]"),
                             "values": values, "shown": count, "total": total})
                return None

            handle.visititems(visit)
    return rows
