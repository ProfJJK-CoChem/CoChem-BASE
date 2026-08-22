"""Comprehensive Zero-Mock Physical Test Suite for cochem_dock_visuals_api.

Validates Plotly data models, QCSchema spectral extraction, mathematical lineshape
broadening (Lorentzian/Gaussian), HDF5 PES scan rendering, directory traversal defense,
artifact inventory discovery, and full REST API endpoint integration.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Generator

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import cochem_base.interfaces as interfaces
from cochem_base.interfaces.cochem_dock_visuals_api import (
    AxisLayout,
    PlotlyLayout,
    PlotlyPayload,
    QCSchemaPropertiesView,
    QCSchemaView,
    ScatterTrace,
    VisualArtifactSummary,
    convolve_spectrum,
    get_potential_energy_surface,
    get_spectrum,
    list_visual_artifacts,
    locate_hdf5_path,
    locate_qcschema_path,
    resolve_base_artifact_dir,
    router,
    validate_basin_id,
    visuals_router,
)
from cochem_base.path_sanitization import leak_patterns

try:
    import h5py
    HAS_H5PY = True
except ImportError:
    HAS_H5PY = False


@pytest.fixture
def target_file_path() -> Path:
    """Return the absolute path to cochem_dock_visuals_api.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "interfaces" / "cochem_dock_visuals_api.py"
    assert path.is_file(), f"Target file does not exist at {path}"
    return path


@pytest.fixture
def api_app() -> FastAPI:
    """Construct a test FastAPI app containing the visuals router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(api_app: FastAPI) -> TestClient:
    """Return a TestClient instance for testing visuals endpoints."""
    return TestClient(api_app)


@pytest.fixture
def isolated_artifact_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up an isolated physical artifact directory hierarchy for testing."""
    artifact_dir = tmp_path / "CoChem_Artifacts"
    scratch_dir = artifact_dir / "Scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(artifact_dir))
    return artifact_dir


# ============================================================================
# Section 1: File Encoding, LF Line Endings, and Zero Path Leakage
# ============================================================================


def test_file_encoding_and_lf_line_endings(target_file_path: Path) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    raw = target_file_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF line endings in cochem_dock_visuals_api.py"
    assert b"\n" in raw, "Missing newline characters in cochem_dock_visuals_api.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in cochem_dock_visuals_api.py"

    content = target_file_path.read_text(encoding="utf-8")
    assert len(content) > 500, "File content is unexpectedly small."


def test_zero_personal_path_leaks(target_file_path: Path) -> None:
    """Verify zero personal machine or local user path leakage in cochem_dock_visuals_api.py."""
    lines = target_file_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, repl_tag in patterns:
            if pattern.search(line):
                leaks.append((lineno, repl_tag, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in cochem_dock_visuals_api.py: {leaks}"


# ============================================================================
# Section 2: Pydantic Data Model Contracts & Validation
# ============================================================================


def test_axis_and_layout_models() -> None:
    """Verify AxisLayout and PlotlyLayout field types and serialization."""
    x_axis = AxisLayout(title="Frequency (cm⁻¹)", autorange="reversed", showgrid=True)
    y_axis = AxisLayout(title="IR Intensity (km/mol)", showgrid=True)
    layout = PlotlyLayout(
        title="Theoretical IR Spectrum",
        xaxis=x_axis,
        yaxis=y_axis,
        hovermode="closest",
        template="plotly_white",
        showlegend=True,
    )

    assert layout.xaxis.title == "Frequency (cm⁻¹)"
    assert layout.xaxis.autorange == "reversed"
    assert layout.yaxis.title == "IR Intensity (km/mol)"
    assert layout.template == "plotly_white"

    data_dump = layout.model_dump()
    assert data_dump["xaxis"]["autorange"] == "reversed"
    assert data_dump["yaxis"]["title"] == "IR Intensity (km/mol)"


def test_scatter_trace_and_payload_models() -> None:
    """Verify ScatterTrace and PlotlyPayload data structures."""
    trace = ScatterTrace(
        x=[1595.0, 3657.0, 3756.0],
        y=[80.5, 12.3, 45.2],
        type="scatter",
        mode="lines+markers",
        name="Water Monomer IR",
        text=["Mode 1", "Mode 2", "Mode 3"],
    )
    assert len(trace.x) == 3
    assert len(trace.y) == 3
    assert trace.name == "Water Monomer IR"

    payload = PlotlyPayload(
        data=[trace],
        layout=PlotlyLayout(
            title="Water Monomer",
            xaxis=AxisLayout(title="Frequency (cm⁻¹)"),
            yaxis=AxisLayout(title="Intensity"),
        ),
        basin_id="water_monomer",
        metadata={"modes_count": 3},
    )

    assert payload.basin_id == "water_monomer"
    assert payload.metadata["modes_count"] == 3
    json_output = payload.model_dump_json()
    assert '"basin_id":"water_monomer"' in json_output
    assert '"modes_count":3' in json_output


def test_qcschema_view_models() -> None:
    """Verify QCSchemaView handles various vibrational and energy keys."""
    raw_data = {
        "schema_name": "qc_schema_output",
        "schema_version": 1,
        "properties": {
            "calcinfo_frequencies": [100.0, 200.0, 300.0],
            "calcinfo_ir_intensities": [10.0, 20.0, 30.0],
            "calcinfo_raman_intensities": [5.0, 15.0, 25.0],
            "return_energy": -76.4321,
            "scf_iterations": 14,
        },
    }
    schema = QCSchemaView.model_validate(raw_data)
    assert schema.properties.calcinfo_frequencies == [100.0, 200.0, 300.0]
    assert schema.properties.calcinfo_ir_intensities == [10.0, 20.0, 30.0]
    assert schema.properties.calcinfo_raman_intensities == [5.0, 15.0, 25.0]
    assert schema.properties.return_energy == -76.4321


# ============================================================================
# Section 3: Lineshape Broadening Convolution Unit Tests
# ============================================================================


def test_convolve_spectrum_lorentzian() -> None:
    """Verify Lorentzian convolution preserves peak center and positive definite envelope."""
    freqs = [1000.0]
    ints = [100.0]
    fwhm = 10.0
    x_grid, y_grid = convolve_spectrum(
        frequencies=freqs,
        intensities=ints,
        fwhm=fwhm,
        n_points=500,
        profile="lorentzian",
        freq_min=900.0,
        freq_max=1100.0,
    )

    assert len(x_grid) == 500
    assert len(y_grid) == 500
    # Peak must be at frequency 1000 cm⁻¹ (center of array)
    max_idx = y_grid.index(max(y_grid))
    assert abs(x_grid[max_idx] - 1000.0) < 1.0
    # Values should decay away from center
    assert y_grid[0] < y_grid[max_idx]
    assert y_grid[-1] < y_grid[max_idx]
    # All values positive
    assert all(val >= 0.0 for val in y_grid)


def test_convolve_spectrum_gaussian() -> None:
    """Verify Gaussian convolution generates symmetric bell curve around mode."""
    freqs = [2000.0]
    ints = [50.0]
    fwhm = 8.0
    x_grid, y_grid = convolve_spectrum(
        frequencies=freqs,
        intensities=ints,
        fwhm=fwhm,
        n_points=400,
        profile="gaussian",
        freq_min=1900.0,
        freq_max=2100.0,
    )

    assert len(x_grid) == 400
    max_idx = y_grid.index(max(y_grid))
    assert abs(x_grid[max_idx] - 2000.0) < 1.0
    # Test symmetry at equidistant offset
    offset = 50
    if 0 <= max_idx - offset and max_idx + offset < len(y_grid):
        assert abs(y_grid[max_idx - offset] - y_grid[max_idx + offset]) < 1e-4


def test_convolve_spectrum_empty_or_mismatched() -> None:
    """Verify convolution returns empty lists on empty or mismatched input."""
    x, y = convolve_spectrum([], [])
    assert x == [] and y == []

    x, y = convolve_spectrum([100.0], [10.0, 20.0])
    assert x == [] and y == []


# ============================================================================
# Section 4: Security & Basin ID Sanitization Tests
# ============================================================================


def test_validate_basin_id_valid() -> None:
    """Verify valid basin identifiers pass validation unchanged."""
    assert validate_basin_id("basin_001") == "basin_001"
    assert validate_basin_id("water-dimer") == "water-dimer"
    assert validate_basin_id("conformers.opt.01") == "conformers.opt.01"


def test_validate_basin_id_traversal_rejection() -> None:
    """Verify directory traversal attempts raise 400 Bad Request."""
    malicious_inputs = [
        "../etc/passwd",
        "..\\windows\\system32",
        "basin/subfolder",
        "basin\\subfolder",
        "",
        "   ",
        "basin;rm -rf /",
        "basin$VAR",
    ]
    for bad_id in malicious_inputs:
        with pytest.raises(HTTPException) as exc_info:
            validate_basin_id(bad_id)
        assert exc_info.value.status_code == 400
        assert "Invalid basin_id" in exc_info.value.detail


# ============================================================================
# Section 5: Spectrum REST Endpoint Integration Tests
# ============================================================================


def test_get_spectrum_success(isolated_artifact_env: Path, client: TestClient) -> None:
    """Verify GET /api/visuals/spectrum/{basin_id} returns valid Plotly payload from physical QCSchema."""
    basin_id = "water_dimer_opt"
    qcschema_path = isolated_artifact_env / "Scratch" / f"{basin_id}_qcschema.json"

    qcschema_content = {
        "schema_name": "qc_schema_output",
        "schema_version": 1,
        "basin_id": basin_id,
        "properties": {
            "calcinfo_frequencies": [1595.2, 3657.1, 3756.4],
            "calcinfo_ir_intensities": [85.4, 15.2, 48.7],
            "calcinfo_raman_intensities": [12.0, 55.0, 90.0],
            "return_energy": -152.8854,
            "scf_iterations": 12,
        },
    }
    qcschema_path.write_text(json.dumps(qcschema_content), encoding="utf-8")

    response = client.get(f"/api/visuals/spectrum/{basin_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["basin_id"] == basin_id
    assert len(data["data"]) == 1
    assert data["data"][0]["x"] == [1595.2, 3657.1, 3756.4]
    assert data["data"][0]["y"] == [85.4, 15.2, 48.7]
    assert data["data"][0]["name"] == "Theoretical Spectrum"
    assert data["layout"]["xaxis"]["autorange"] == "reversed"
    assert data["layout"]["yaxis"]["title"] == "IR Intensity (km/mol)"
    assert data["metadata"]["return_energy"] == -152.8854


def test_get_spectrum_with_broadening(isolated_artifact_env: Path, client: TestClient) -> None:
    """Verify GET /api/visuals/spectrum/{basin_id} with broadening returns envelope and stick traces."""
    basin_id = "broadened_test"
    qcschema_path = isolated_artifact_env / "Scratch" / f"{basin_id}_qcschema.json"
    qcschema_path.write_text(
        json.dumps({
            "properties": {
                "calcinfo_frequencies": [1200.0, 1600.0, 3400.0],
                "calcinfo_ir_intensities": [20.0, 80.0, 150.0],
            }
        }),
        encoding="utf-8",
    )

    response = client.get(
        f"/api/visuals/spectrum/{basin_id}?broadening=true&fwhm=12.0&points=200&profile=gaussian"
    )
    assert response.status_code == 200
    data = response.json()

    # Must contain 2 traces: Convolved Envelope + Sticks
    assert len(data["data"]) == 2
    conv_trace = data["data"][0]
    stick_trace = data["data"][1]

    assert "Convolved Envelope" in conv_trace["name"]
    assert len(conv_trace["x"]) == 200
    assert stick_trace["name"] == "Theoretical IR (Sticks)"
    assert len(stick_trace["x"]) == 3


def test_get_spectrum_raman_and_both_modes(isolated_artifact_env: Path, client: TestClient) -> None:
    """Verify Raman and dual spectroscopy querying modes."""
    basin_id = "raman_test"
    qcschema_path = isolated_artifact_env / "Scratch" / f"{basin_id}_qcschema.json"
    qcschema_path.write_text(
        json.dumps({
            "properties": {
                "frequencies": [500.0, 1000.0],
                "ir_intensities": [10.0, 20.0],
                "raman_intensities": [75.0, 120.0],
            }
        }),
        encoding="utf-8",
    )

    # Test Raman only
    raman_resp = client.get(f"/api/visuals/spectrum/{basin_id}?spectrum_type=raman")
    assert raman_resp.status_code == 200
    raman_data = raman_resp.json()
    assert raman_data["data"][0]["y"] == [75.0, 120.0]
    assert raman_data["layout"]["yaxis"]["title"] == "Raman Activity (Å⁴/amu)"

    # Test Both IR and Raman
    both_resp = client.get(f"/api/visuals/spectrum/{basin_id}?spectrum_type=both")
    assert both_resp.status_code == 200
    both_data = both_resp.json()
    assert len(both_data["data"]) == 2
    assert both_data["data"][0]["name"] == "Theoretical Spectrum"
    assert both_data["data"][1]["name"] == "Theoretical Raman"


def test_get_spectrum_not_found(isolated_artifact_env: Path, client: TestClient) -> None:
    """Verify 404 response for non-existent QCSchema artifacts."""
    response = client.get("/api/visuals/spectrum/nonexistent_basin_xyz")
    assert response.status_code == 404
    assert "QCSchema artifact not found" in response.json()["detail"]


def test_get_spectrum_missing_data_token(isolated_artifact_env: Path, client: TestClient) -> None:
    """Verify 400 response with strict [MISSING DATA] token when frequency properties are missing."""
    basin_id = "missing_data_basin"
    qcschema_path = isolated_artifact_env / "Scratch" / f"{basin_id}_qcschema.json"
    qcschema_path.write_text(
        json.dumps({"properties": {"return_energy": -40.123}}),
        encoding="utf-8",
    )

    response = client.get(f"/api/visuals/spectrum/{basin_id}")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "[MISSING DATA]" in detail
    assert "calcinfo_frequencies" in detail


def test_get_spectrum_corrupted_json(isolated_artifact_env: Path, client: TestClient) -> None:
    """Verify 500 response for corrupted JSON file."""
    basin_id = "corrupted_json_basin"
    qcschema_path = isolated_artifact_env / "Scratch" / f"{basin_id}_qcschema.json"
    qcschema_path.write_text("{ incomplete json string...", encoding="utf-8")

    response = client.get(f"/api/visuals/spectrum/{basin_id}")
    assert response.status_code == 500
    assert "Invalid JSON format" in response.json()["detail"]


# ============================================================================
# Section 6: HDF5 Potential Energy Surface (PES) Landscape Endpoint Tests
# ============================================================================


@pytest.mark.skipif(not HAS_H5PY, reason="h5py not installed in environment")
def test_get_potential_energy_surface_success(isolated_artifact_env: Path, client: TestClient) -> None:
    """Verify GET /api/visuals/landscape/{basin_id} parses HDF5 binary PES scan."""
    basin_id = "pes_scan_test"
    h5_path = isolated_artifact_env / "Scratch" / f"{basin_id}_landscape.h5"

    coords = [0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0]
    energies_hartree = [-76.43, -76.42, -76.40, -76.38, -76.40, -76.42, -76.43]

    with h5py.File(h5_path, "w") as f:
        f.create_dataset("coordinates", data=coords)
        f.create_dataset("energies", data=energies_hartree)

    # Test relative energy in kcal/mol
    resp = client.get(f"/api/visuals/landscape/{basin_id}?energy_unit=kcal/mol&relative=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["basin_id"] == basin_id
    assert len(data["data"]) == 1
    assert data["data"][0]["x"] == coords
    # Relative min should be 0.0 kcal/mol
    assert min(data["data"][0]["y"]) == pytest.approx(0.0, abs=1e-5)
    assert data["layout"]["yaxis"]["title"] == "Relative Energy (kcal/mol)"


@pytest.mark.skipif(not HAS_H5PY, reason="h5py not installed in environment")
def test_get_potential_energy_surface_not_found(isolated_artifact_env: Path, client: TestClient) -> None:
    """Verify 404 response when HDF5 binary is absent."""
    resp = client.get("/api/visuals/landscape/nonexistent_h5_basin")
    assert resp.status_code == 404
    assert "HDF5 landscape binary not found" in resp.json()["detail"]


# ============================================================================
# Section 7: Inventory & Ecosystem Interface Exports Tests
# ============================================================================


def test_list_visual_artifacts(isolated_artifact_env: Path, client: TestClient) -> None:
    """Verify GET /api/visuals/inventory discovers artifacts in Scratch directory."""
    scratch = isolated_artifact_env / "Scratch"
    # Create QCSchema file
    (scratch / "basin_alpha_qcschema.json").write_text(
        json.dumps({"properties": {"calcinfo_frequencies": [100.0, 200.0]}}),
        encoding="utf-8",
    )
    # Create dummy file
    (scratch / "basin_beta_qcschema.json").write_text(
        json.dumps({"properties": {"calcinfo_frequencies": [300.0]}}),
        encoding="utf-8",
    )

    resp = client.get("/api/visuals/inventory")
    assert resp.status_code == 200
    inventory = resp.json()
    basin_ids = [item["basin_id"] for item in inventory]
    assert "basin_alpha" in basin_ids
    assert "basin_beta" in basin_ids


def test_lazy_loading_interface_exports() -> None:
    """Verify cochem_base.interfaces lazy loading exports all symbols properly."""
    assert interfaces.AxisLayout is AxisLayout
    assert interfaces.PlotlyLayout is PlotlyLayout
    assert interfaces.ScatterTrace is ScatterTrace
    assert interfaces.PlotlyPayload is PlotlyPayload
    assert interfaces.get_spectrum is get_spectrum
    assert interfaces.router is router
    assert interfaces.visuals_router is visuals_router


def test_interfaces_cochem_dock_visuals_api_reexports() -> None:
    """Verify interfaces/cochem_dock_visuals_api.py re-exports all canonical symbols."""
    import cochem_base.interfaces.cochem_dock_visuals_api as canonical_visuals
    import interfaces.cochem_dock_visuals_api as legacy_visuals

    assert legacy_visuals.router is canonical_visuals.router
    assert legacy_visuals.visuals_router is canonical_visuals.visuals_router
    assert legacy_visuals.get_spectrum is canonical_visuals.get_spectrum
    assert legacy_visuals.get_potential_energy_surface is canonical_visuals.get_potential_energy_surface
    assert legacy_visuals.list_visual_artifacts is canonical_visuals.list_visual_artifacts
    assert legacy_visuals.visuals_health_check is canonical_visuals.visuals_health_check
    assert legacy_visuals.convolve_spectrum is canonical_visuals.convolve_spectrum
    assert legacy_visuals.extract_qcschema_spectral_data is canonical_visuals.extract_qcschema_spectral_data
    assert legacy_visuals.validate_basin_id is canonical_visuals.validate_basin_id
    assert legacy_visuals.resolve_base_artifact_dir is canonical_visuals.resolve_base_artifact_dir
    assert legacy_visuals.locate_qcschema_path is canonical_visuals.locate_qcschema_path
    assert legacy_visuals.locate_hdf5_path is canonical_visuals.locate_hdf5_path
    assert legacy_visuals.AxisLayout is canonical_visuals.AxisLayout
    assert legacy_visuals.PlotlyLayout is canonical_visuals.PlotlyLayout
    assert legacy_visuals.PlotlyPayload is canonical_visuals.PlotlyPayload
    assert legacy_visuals.ScatterTrace is canonical_visuals.ScatterTrace
    assert legacy_visuals.QCSchemaView is canonical_visuals.QCSchemaView
    assert legacy_visuals.QCSchemaPropertiesView is canonical_visuals.QCSchemaPropertiesView
    assert legacy_visuals.VisualArtifactSummary is canonical_visuals.VisualArtifactSummary
    assert legacy_visuals.HARTREE_TO_KCAL_MOL == canonical_visuals.HARTREE_TO_KCAL_MOL
    assert legacy_visuals.HARTREE_TO_EV == canonical_visuals.HARTREE_TO_EV
    assert legacy_visuals.HARTREE_TO_KJ_MOL == canonical_visuals.HARTREE_TO_KJ_MOL


def test_interfaces_cochem_dock_visuals_api_file_integrity() -> None:
    """Verify interfaces/cochem_dock_visuals_api.py has LF line endings, valid docstrings, and no path leaks."""
    path = Path(__file__).resolve().parent.parent / "interfaces" / "cochem_dock_visuals_api.py"
    assert path.is_file(), f"Target file does not exist at {path}"

    raw = path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF line endings in interfaces/cochem_dock_visuals_api.py"
    assert b"\n" in raw, "Missing newline characters in interfaces/cochem_dock_visuals_api.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in interfaces/cochem_dock_visuals_api.py"

    lines = path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, repl_tag in patterns:
            if pattern.search(line):
                leaks.append((lineno, repl_tag, line.strip()))
    assert len(leaks) == 0, f"Detected personal path leaks: {leaks}"

