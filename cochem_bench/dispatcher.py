"""
CoChem-BENCH Dispatcher & Thermochemical Serializer
Validates geometries, aggregates thermochemical CBS corrections, and manages HDF5 state.
"""
import math
from pathlib import Path
from typing import Any
import h5py

def validate_geometry(coords: list[tuple[str, float, float, float]]) -> bool:
    """
    Validates molecular geometry and detects severe interatomic clashes (< 0.60 Å).
    """
    n = len(coords)
    for i in range(n):
        c1 = coords[i]
        try:
            sym1 = str(c1[0])
            p1 = (float(c1[1]), float(c1[2]), float(c1[3]))
        except (IndexError, TypeError, ValueError) as e:
            raise ValueError(f"Invalid coordinate data for atom {i}: {c1}") from e
            
        for j in range(i + 1, n):
            c2 = coords[j]
            try:
                sym2 = str(c2[0])
                p2 = (float(c2[1]), float(c2[2]), float(c2[3]))
            except (IndexError, TypeError, ValueError) as e:
                raise ValueError(f"Invalid coordinate data for atom {j}: {c2}") from e
                
            dist = math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2 + (p1[2] - p2[2])**2)
            if dist < 0.60:
                raise ValueError(f"Atomic clash detected between atom {i} ({sym1}) and {j} ({sym2}): distance {dist:.3f} Å < 0.60 Å")
    return True

def compute_thermochemical_cbs(
    electronic_cbs: float,
    zpe: float = 0.0,
    thermal_h_corr: float = 0.0,
    thermal_g_corr: float = 0.0
) -> dict[str, float]:
    """
    Combines electronic CBS energy with ZPE and thermal enthalpy/free energy corrections.
    """
    h_cbs = electronic_cbs + zpe + thermal_h_corr
    g_cbs = electronic_cbs + zpe + thermal_g_corr
    return {
        "electronic_cbs": float(electronic_cbs),
        "zpe": float(zpe),
        "thermal_h_corr": float(thermal_h_corr),
        "thermal_g_corr": float(thermal_g_corr),
        "h_cbs": float(h_cbs),
        "g_cbs": float(g_cbs)
    }

def serialize_cbs_to_hdf5(filepath: str | Path, data: dict[str, Any]) -> None:
    """
    Serializes thermochemical benchmark state to HDF5 file.
    """
    p = Path(filepath)
    p.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(p, "w", libver="latest") as f:
        grp = f.create_group("thermochemistry_cbs")
        for k, v in data.items():
            if isinstance(v, (int, float, str)):
                grp.create_dataset(k, data=v)
            else:
                raise TypeError(f"Unsupported data type for HDF5 serialization: key '{k}' has type {type(v).__name__}")
