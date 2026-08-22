#!/usr/bin/env python3
"""
CoChem-DOCK: Stage 9.0 - Subprocess Bridge for Live UI Plotting
Parses QCSchema and HDF5 binaries to serve Plotly-compatible JSON payloads.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Sequence, Union

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from cochem_base.config_loader import get_artifact_dir, resolve_mapped_path

logger = logging.getLogger(__name__)

# Standard Physical Conversion Factors
HARTREE_TO_KCAL_MOL: float = 627.5094740631
HARTREE_TO_EV: float = 27.211386245988
HARTREE_TO_KJ_MOL: float = 2625.4996394799

router = APIRouter(prefix="/api/visuals", tags=["Visuals"])
visuals_router = router


def validate_basin_id(basin_id: str) -> str:
    """Validates basin_id against directory traversal attacks and invalid characters."""
    if not basin_id or not isinstance(basin_id, str) or not basin_id.strip():
        raise HTTPException(status_code=400, detail="Basin ID cannot be empty.")
    
    cleaned = basin_id.strip()
    if "\0" in cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        raise HTTPException(status_code=400, detail="Invalid basin ID: directory traversal detected.")
    
    # Check valid characters (alphanumeric, underscore, hyphen, dot)
    if not re.fullmatch(r"^[a-zA-Z0-9_.\-]+$", cleaned):
        raise HTTPException(status_code=400, detail="Invalid basin ID characters.")
    
    return cleaned


def resolve_base_artifact_dir(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the artifact directory for visual files."""
    if custom_path is not None:
        return resolve_mapped_path(custom_path)
    env_art = os.getenv("COCHEM_ARTIFACT_DIR")
    if env_art:
        return resolve_mapped_path(env_art)
    return get_artifact_dir()


def locate_qcschema_path(basin_id: str, base_dir: Optional[Path] = None) -> Path:
    """Locates the QCSchema JSON file for a given basin_id."""
    valid_id = validate_basin_id(basin_id)
    root = resolve_base_artifact_dir(base_dir)
    # Check Scratch or root
    candidates = [
        root / "Scratch" / f"{valid_id}_qcschema.json",
        root / f"{valid_id}_qcschema.json",
        root / "Scratch" / f"{valid_id}.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return candidates[0]


def locate_hdf5_path(basin_id: str, base_dir: Optional[Path] = None) -> Path:
    """Locates the HDF5 landscape file for a given basin_id."""
    valid_id = validate_basin_id(basin_id)
    root = resolve_base_artifact_dir(base_dir)
    candidates = [
        root / "Scratch" / f"{valid_id}_landscape.h5",
        root / f"{valid_id}_landscape.h5",
        root / "Scratch" / f"{valid_id}.h5",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return candidates[0]


class AxisLayout(BaseModel):
    title: str
    autorange: Optional[str] = None


class PlotlyLayout(BaseModel):
    title: str
    xaxis: AxisLayout
    yaxis: AxisLayout


class ScatterTrace(BaseModel):
    x: List[float] = Field(default_factory=list)
    y: List[float] = Field(default_factory=list)
    z: Optional[List[List[float]]] = None
    text: Optional[List[str]] = None
    type: str = Field(default="scatter")
    mode: str = Field(default="markers+lines")
    name: str = Field(default="Theoretical Output")


class PlotlyPayload(BaseModel):
    basin_id: Optional[str] = None
    data: List[ScatterTrace] = Field(default_factory=list)
    layout: PlotlyLayout
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QCSchemaPropertiesView(BaseModel):
    calcinfo_frequencies: Optional[List[float]] = None
    calcinfo_ir_intensities: Optional[List[float]] = None
    calcinfo_raman_intensities: Optional[List[float]] = None
    calcinfo_intensities: Optional[List[float]] = None
    frequencies: Optional[List[float]] = None
    intensities: Optional[List[float]] = None
    return_energy: Optional[float] = None
    scf_iterations: Optional[int] = None
    dipole_moment: Optional[List[float]] = None


class QCSchemaView(BaseModel):
    schema_name: Optional[str] = None
    schema_version: Optional[int] = None
    basin_id: Optional[str] = None
    properties: QCSchemaPropertiesView = Field(default_factory=QCSchemaPropertiesView)


class VisualArtifactSummary(BaseModel):
    basin_id: str
    has_qcschema: bool = False
    has_hdf5: bool = False
    frequencies_count: int = 0
    qcschema_filename: Optional[str] = None
    hdf5_filename: Optional[str] = None


def convolve_spectrum(
    frequencies: Sequence[float],
    intensities: Sequence[float],
    fwhm: float = 10.0,
    n_points: int = 1000,
    profile: str = "lorentzian",
    voigt_fraction: float = 0.5,
    freq_min: Optional[float] = None,
    freq_max: Optional[float] = None,
) -> Tuple[List[float], List[float]]:
    """Mathematical lineshape broadening (Lorentzian, Gaussian, Pseudo-Voigt)."""
    if not frequencies or not intensities or len(frequencies) != len(intensities):
        return [], []

    if fwhm <= 0.0:
        raise ValueError("FWHM bandwidth parameter must be strictly positive")
    if n_points < 2:
        raise ValueError("n_points must be an integer >= 2")

    pos_freqs = [f for f in frequencies if f > 0]
    if not pos_freqs:
        pos_freqs = list(frequencies)

    f_min = freq_min if freq_min is not None else max(0.0, min(pos_freqs) - 3 * fwhm - 50.0)
    f_max = freq_max if freq_max is not None else (max(pos_freqs) + 3 * fwhm + 50.0)

    if f_min >= f_max:
        raise ValueError(f"freq_min ({f_min}) must be strictly less than freq_max ({f_max})")

    x_grid = [f_min + i * (f_max - f_min) / (n_points - 1) for i in range(n_points)]
    y_grid = [0.0] * n_points

    gamma = fwhm / 2.0  # HWHM
    sigma = fwhm / (2.0 * math.sqrt(2.0 * math.log(2.0)))

    for f_center, intensity in zip(frequencies, intensities):
        for i, x in enumerate(x_grid):
            diff = x - f_center
            if profile.lower() == "lorentzian":
                # L(x) = (1/pi) * (gamma / (diff^2 + gamma^2))
                val = intensity * (1.0 / math.pi) * (gamma / (diff**2 + gamma**2))
            elif profile.lower() == "gaussian":
                # G(x) = (1 / (sigma * sqrt(2*pi))) * exp(-diff^2 / (2*sigma^2))
                val = intensity * (1.0 / (sigma * math.sqrt(2.0 * math.pi))) * math.exp(-0.5 * (diff / sigma)**2)
            elif profile.lower() == "pseudo_voigt":
                l_val = (1.0 / math.pi) * (gamma / (diff**2 + gamma**2))
                g_val = (1.0 / (sigma * math.sqrt(2.0 * math.pi))) * math.exp(-0.5 * (diff / sigma)**2)
                eta = max(0.0, min(1.0, voigt_fraction))
                val = intensity * (eta * l_val + (1.0 - eta) * g_val)
            else:
                val = intensity * (1.0 / math.pi) * (gamma / (diff**2 + gamma**2))
            y_grid[i] += val

    return x_grid, y_grid


def extract_qcschema_spectral_data(
    qcschema: Dict[str, Any]
) -> Tuple[List[float], List[float], Optional[List[float]], Dict[str, Any]]:
    """Extracts frequencies, IR intensities, Raman intensities, and metadata from QCSchema dict."""
    props = qcschema.get("properties", {})
    if not isinstance(props, dict):
        props = {}

    freqs = props.get("calcinfo_frequencies") or qcschema.get("frequencies") or props.get("frequencies")
    ir = (
        props.get("calcinfo_ir_intensities")
        or qcschema.get("intensities")
        or props.get("calcinfo_intensities")
        or props.get("intensities")
    )
    raman = props.get("calcinfo_raman_intensities")

    # Check return_result if nested
    ret_res = qcschema.get("return_result")
    if isinstance(ret_res, dict):
        if freqs is None:
            freqs = ret_res.get("frequencies")
        if ir is None:
            ir = ret_res.get("ir_intensities") or ret_res.get("intensities")
        if raman is None:
            raman = ret_res.get("raman_intensities")

    meta: Dict[str, Any] = {}
    for k in ["return_energy", "scf_iterations", "dipole_moment"]:
        if k in props:
            meta[k] = props[k]
        elif k in qcschema:
            meta[k] = qcschema[k]

    return freqs or [], ir or [], raman, meta


@router.get("/health")
def visuals_health_check() -> Dict[str, Any]:
    """Health check for Visuals API subsystem."""
    art_dir = resolve_base_artifact_dir()
    return {
        "status": "healthy",
        "subsystem": "CoChem-DOCK.Visuals",
        "stage": "9.0",
        "artifact_dir": str(art_dir),
        "artifact_dir_exists": art_dir.exists(),
    }


@router.get("/spectrum/{basin_id}", response_model=PlotlyPayload)
async def get_spectrum(
    basin_id: str,
    broadening: bool = False,
    profile: str = "lorentzian",
    fwhm: float = 10.0,
    points: int = 1000,
    spectrum_type: str = "ir",
    normalize: bool = False,
) -> PlotlyPayload:
    """Fetches theoretical vibrational spectrum for Plotly rendering."""
    valid_id = validate_basin_id(basin_id)
    schema_path = locate_qcschema_path(valid_id)

    if not schema_path.is_file():
        raise HTTPException(status_code=404, detail=f"QCSchema artifact not found for basin '{valid_id}'.")

    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            data = json.loads(f.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Invalid JSON format in artifact: {e}") from e

    freqs, ir, raman, meta = extract_qcschema_spectral_data(data)

    if not freqs or (not ir and not raman):
        raise HTTPException(
            status_code=400,
            detail="[MISSING DATA] QCSchema lacks calcinfo_frequencies or calcinfo_ir_intensities."
        )

    traces: List[ScatterTrace] = []
    metadata: Dict[str, Any] = {
        "modes_count": len(freqs),
        "broadening": broadening,
        "profile": profile if broadening else None,
        "normalized": normalize,
        **meta,
    }

    # Count imaginary modes
    imaginary_count = sum(1 for f in freqs if f < 0)
    metadata["imaginary_modes_count"] = imaginary_count

    # Generate hover texts
    hover_texts = [
        f"Mode {i+1}: {f:.1f} cm⁻¹" + (" [TS/Imaginary]" if f < 0 else "")
        for i, f in enumerate(freqs)
    ]

    # Process IR
    if spectrum_type.lower() in ["ir", "both"] and ir:
        y_ir = list(ir)
        if normalize and max(y_ir) > 0:
            max_val = max(y_ir)
            y_ir = [v / max_val for v in y_ir]

        if broadening:
            x_conv, y_conv = convolve_spectrum(
                freqs, y_ir, fwhm=fwhm, n_points=points, profile=profile
            )
            traces.append(ScatterTrace(
                x=x_conv,
                y=y_conv,
                type="scatter",
                mode="lines",
                name="Theoretical Envelope" if spectrum_type.lower() != "both" else "Theoretical IR Envelope",
            ))

        traces.append(ScatterTrace(
            x=list(freqs),
            y=y_ir,
            text=hover_texts,
            type="scatter",
            mode="markers+lines" if not broadening else "markers",
            name="Theoretical Spectrum" if spectrum_type.lower() != "both" else "Theoretical Spectrum",
        ))

    # Process Raman
    if spectrum_type.lower() in ["raman", "both"] and raman:
        y_raman = list(raman)
        if normalize and max(y_raman) > 0:
            max_val = max(y_raman)
            y_raman = [v / max_val for v in y_raman]

        if broadening:
            x_conv, y_conv = convolve_spectrum(
                freqs, y_raman, fwhm=fwhm, n_points=points, profile=profile
            )
            traces.append(ScatterTrace(
                x=x_conv,
                y=y_conv,
                type="scatter",
                mode="lines",
                name="Theoretical Raman Envelope",
            ))

        traces.append(ScatterTrace(
            x=list(freqs),
            y=y_raman,
            text=hover_texts,
            type="scatter",
            mode="markers+lines" if not broadening else "markers",
            name="Theoretical Raman",
        ))

    layout = PlotlyLayout(
        title=f"Vibrational Spectrum for {valid_id}",
        xaxis=AxisLayout(title="Wavenumber (cm⁻¹)", autorange="reversed"),
        yaxis=AxisLayout(title="Normalized Intensity" if normalize else "Intensity (km/mol)"),
    )

    return PlotlyPayload(basin_id=valid_id, data=traces, layout=layout, metadata=metadata)


@router.get("/landscape/{basin_id}", response_model=PlotlyPayload)
async def get_potential_energy_surface(
    basin_id: str,
    energy_unit: str = "kcal/mol",
    relative: bool = False,
) -> PlotlyPayload:
    """Fetches HDF5 1D/2D Potential Energy Surface scan for Plotly rendering."""
    try:
        import h5py
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="h5py is not available.") from exc

    valid_id = validate_basin_id(basin_id)
    h5_path = locate_hdf5_path(valid_id)

    if not h5_path.is_file():
        raise HTTPException(status_code=404, detail=f"HDF5 landscape artifact not found for basin '{valid_id}'.")

    # Unit factor
    unit_lower = energy_unit.lower().replace(" ", "").replace("_", "")
    if "kcal" in unit_lower:
        conv_factor = HARTREE_TO_KCAL_MOL
        y_label = "Relative Energy (kcal/mol)" if relative else "Energy (kcal/mol)"
        unit_str = "kcal/mol"
    elif "ev" in unit_lower:
        conv_factor = HARTREE_TO_EV
        y_label = "Relative Energy (eV)" if relative else "Energy (eV)"
        unit_str = "ev"
    elif "kj" in unit_lower:
        conv_factor = HARTREE_TO_KJ_MOL
        y_label = "Relative Energy (kJ/mol)" if relative else "Energy (kJ/mol)"
        unit_str = "kj/mol"
    else:
        conv_factor = 1.0
        y_label = "Relative Energy (Hartree)" if relative else "Energy (Hartree)"
        unit_str = "hartree"

    with h5py.File(h5_path, "r") as h5_file:
        coords_x = list(h5_file["coordinates"][:])
        energies = h5_file["energies"][:]
        is_2d = "coordinates_y" in h5_file or len(energies.shape) == 2

        if is_2d:
            coords_y = list(h5_file["coordinates_y"][:]) if "coordinates_y" in h5_file else []
            e_grid = energies * conv_factor
            if relative:
                e_grid = e_grid - float(e_grid.min())

            z_data = e_grid.tolist()
            trace = ScatterTrace(
                x=coords_x,
                y=coords_y,
                z=z_data,
                type="contour",
                name="2D PES",
            )
            layout = PlotlyLayout(
                title=f"2D PES Landscape for {valid_id}",
                xaxis=AxisLayout(title="Coordinate X (deg/Å)"),
                yaxis=AxisLayout(title="Coordinate Y (deg/Å)"),
            )
            metadata = {"is_2d": True, "energy_unit": unit_str, "relative": relative}
            return PlotlyPayload(basin_id=valid_id, data=[trace], layout=layout, metadata=metadata)
        else:
            e_arr = energies * conv_factor
            if relative:
                e_arr = e_arr - float(e_arr.min())

            trace = ScatterTrace(
                x=coords_x,
                y=e_arr.tolist(),
                type="scatter",
                mode="lines+markers",
                name="1D PES Profile",
            )
            layout = PlotlyLayout(
                title=f"1D PES Profile for {valid_id}",
                xaxis=AxisLayout(title="Reaction Coordinate (deg/Å)"),
                yaxis=AxisLayout(title=y_label),
            )
            metadata = {"is_2d": False, "energy_unit": unit_str, "relative": relative}
            return PlotlyPayload(basin_id=valid_id, data=[trace], layout=layout, metadata=metadata)


@router.get("/inventory", response_model=List[VisualArtifactSummary])
def list_visual_artifacts(base_dir: Optional[Path] = None) -> List[VisualArtifactSummary]:
    """Scans artifact directory and returns inventory of available QCSchema and HDF5 files."""
    root = resolve_base_artifact_dir(base_dir)
    search_dirs = [root, root / "Scratch"]

    artifacts: Dict[str, VisualArtifactSummary] = {}

    for s_dir in search_dirs:
        if not s_dir.is_dir():
            continue
        for f in s_dir.glob("*_qcschema.json"):
            basin_id = f.name.replace("_qcschema.json", "")
            if basin_id not in artifacts:
                artifacts[basin_id] = VisualArtifactSummary(basin_id=basin_id)
            artifacts[basin_id].has_qcschema = True
            artifacts[basin_id].qcschema_filename = f.name
            try:
                with open(f, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                    freqs, _, _, _ = extract_qcschema_spectral_data(data)
                    artifacts[basin_id].frequencies_count = len(freqs)
            except Exception:
                pass

        for f in s_dir.glob("*_landscape.h5"):
            basin_id = f.name.replace("_landscape.h5", "")
            if basin_id not in artifacts:
                artifacts[basin_id] = VisualArtifactSummary(basin_id=basin_id)
            artifacts[basin_id].has_hdf5 = True
            artifacts[basin_id].hdf5_filename = f.name

    return sorted(artifacts.values(), key=lambda a: a.basin_id)


__all__ = [
    "AxisLayout",
    "HARTREE_TO_EV",
    "HARTREE_TO_KCAL_MOL",
    "HARTREE_TO_KJ_MOL",
    "PlotlyLayout",
    "PlotlyPayload",
    "QCSchemaPropertiesView",
    "QCSchemaView",
    "ScatterTrace",
    "VisualArtifactSummary",
    "convolve_spectrum",
    "extract_qcschema_spectral_data",
    "get_potential_energy_surface",
    "get_spectrum",
    "list_visual_artifacts",
    "locate_hdf5_path",
    "locate_qcschema_path",
    "resolve_base_artifact_dir",
    "router",
    "validate_basin_id",
    "visuals_health_check",
    "visuals_router",
]

