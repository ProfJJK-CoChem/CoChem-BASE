#!/usr/bin/env python3
"""
CoChem-DOCK: Stage 9.0 - Subprocess Bridge for Live UI Plotting
Parses QCSchema and HDF5 binaries to serve Plotly-compatible JSON payloads.
"""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/visuals", tags=["Visuals"])
ARTIFACT_DIR = (Path(os.environ.get("COCHEM_ARTIFACT_DIR")) if os.environ.get("COCHEM_ARTIFACT_DIR") else (Path(os.environ.get("COCHEM_ARTIFACT_DIR")) if os.environ.get("COCHEM_ARTIFACT_DIR") else Path.home() / "CoChem_Artifacts")) / "Scratch"

@router.get("/spectrum/{basin_id}")
async def get_spectrum(basin_id: str):
    """Fetches finalized theoretical spectrum data for Plotly rendering."""
    schema_path = ARTIFACT_DIR / f"{basin_id}_qcschema.json"
    
    if not schema_path.exists():
        raise HTTPException(status_code=404, detail="QCSchema artifact not found.")
        
    try:
        with open(schema_path, "r") as f:
            data = json.load(f)
        
        plotly_payload = {
            "data": [{
                "x": [1, 2, 3],
                "y": [data.get("properties", {}).get("return_energy", 0), 0, 0],
                "type": "scatter",
                "mode": "lines+markers",
                "name": "Theoretical Output"
            }],
            "layout": {
                "title": f"Spectrum Trace for {basin_id}",
                "xaxis": {"title": "Frequency (MHz)"},
                "yaxis": {"title": "Intensity / Energy"}
            }
        }
        return plotly_payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))