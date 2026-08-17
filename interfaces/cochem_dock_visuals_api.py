#!/usr/bin/env python3
"""
CoChem-DOCK: Stage 9.0 - Subprocess Bridge for Live UI Plotting
Parses QCSchema and HDF5 binaries to serve Plotly-compatible JSON payloads.
"""
from typing import Optional, List
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from cochem_base.config_loader import get_artifact_dir

router = APIRouter(prefix="/api/visuals", tags=["Visuals"])


class QCSchemaPropertiesView(BaseModel):
    calcinfo_frequencies: Optional[List[float]] = None
    calcinfo_intensities: Optional[List[float]] = None
    frequencies: Optional[List[float]] = None
    intensities: Optional[List[float]] = None
    return_energy: Optional[float] = None

class QCSchemaView(BaseModel):
    properties: QCSchemaPropertiesView = Field(default_factory=QCSchemaPropertiesView)


class PlotlyData(BaseModel):
    x: List[float]
    y: List[float]
    type: str = "scatter"
    mode: str = "lines+markers"
    name: str = "Theoretical Output"


class PlotlyLayoutAxis(BaseModel):
    title: str


class PlotlyLayout(BaseModel):
    title: str
    xaxis: PlotlyLayoutAxis
    yaxis: PlotlyLayoutAxis


class PlotlyPayload(BaseModel):
    data: List[PlotlyData]
    layout: PlotlyLayout


@router.get("/spectrum/{basin_id}", response_model=PlotlyPayload)
async def get_spectrum(basin_id: str) -> PlotlyPayload:
    """Fetches finalized theoretical spectrum data for Plotly rendering."""
    schema_path = get_artifact_dir() / "Scratch" / f"{basin_id}_qcschema.json"

    if not schema_path.exists():
        raise HTTPException(status_code=404, detail="QCSchema artifact not found.")

    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            # Support both Pydantic v1 and v2
            if hasattr(QCSchemaView, "model_validate"):
                schema_obj = QCSchemaView.model_validate(raw_data)
            else:
                schema_obj = QCSchemaView(**raw_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse QCSchema: {e}") from e

    props = schema_obj.properties
    freqs = props.calcinfo_frequencies or props.frequencies
    ints = props.calcinfo_intensities or props.intensities

    if not freqs or not ints:
        raise HTTPException(
            status_code=404,
            detail="[MISSING DATA] QCSchema properties missing frequency or intensity arrays."
        )

    plotly_payload = PlotlyPayload(
        data=[PlotlyData(
            x=freqs,
            y=ints,
            name="Theoretical Output"
        )],
        layout=PlotlyLayout(
            title=f"Spectrum Trace for {basin_id}",
            xaxis=PlotlyLayoutAxis(title="Frequency (MHz)"),
            yaxis=PlotlyLayoutAxis(title="Intensity / Energy")
        )
    )
    return plotly_payload
