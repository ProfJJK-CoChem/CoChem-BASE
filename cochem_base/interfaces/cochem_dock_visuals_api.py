#!/usr/bin/env python3
"""
CoChem-DOCK: Stage 9.0 - Subprocess Bridge for Live UI Plotting
Parses QCSchema and HDF5 binaries to serve Plotly-compatible JSON payloads.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from cochem_base.config_loader import get_artifact_dir

router = APIRouter(prefix="/api/visuals", tags=["Visuals"])


class AxisLayout(BaseModel):
    title: str


class PlotlyLayout(BaseModel):
    title: str
    xaxis: AxisLayout
    yaxis: AxisLayout


class ScatterTrace(BaseModel):
    x: List[float]
    y: List[float]
    type: str = Field(default="scatter")
    mode: str = Field(default="markers+lines")
    name: str = Field(default="Theoretical Output")


class PlotlyPayload(BaseModel):
    data: List[ScatterTrace]
    layout: PlotlyLayout


@router.get("/spectrum/{basin_id}", response_model=PlotlyPayload)
async def get_spectrum(basin_id: str) -> PlotlyPayload:
    """Fetches finalized theoretical spectrum data for Plotly rendering."""
    # Enforce configurable artifacts directory lookup
    env_artifact_dir = os.getenv("COCHEM_ARTIFACT_DIR")
    if env_artifact_dir:
        base_dir = Path(env_artifact_dir)
    else:
        base_dir = get_artifact_dir()
        
    schema_path = base_dir / "Scratch" / f"{basin_id}_qcschema.json"

    if not schema_path.exists():
        raise HTTPException(status_code=404, detail="QCSchema artifact not found.")

    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            data = json.loads(f.read())
            
        properties = data.get("properties", {})
        frequencies = properties.get("calcinfo_frequencies")
        intensities = properties.get("calcinfo_ir_intensities")
        
        if frequencies is None or intensities is None:
            # Emit hard [MISSING DATA] token to trigger failure protocols
            raise HTTPException(
                status_code=400, 
                detail="[MISSING DATA] QCSchema lacks calcinfo_frequencies or calcinfo_ir_intensities."
            )
            
        payload = PlotlyPayload(
            data=[ScatterTrace(
                x=frequencies,
                y=intensities,
                type="scatter",
                mode="lines+markers",
                name="Theoretical Spectrum"
            )],
            layout=PlotlyLayout(
                title=f"Spectrum Trace for {basin_id}",
                xaxis=AxisLayout(title="Frequency (cm⁻¹)"),
                yaxis=AxisLayout(title="IR Intensity (km/mol)")
            )
        )
        return payload

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid JSON format in artifact: {str(e)}") from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
