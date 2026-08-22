#!/usr/bin/env python3
"""Physical Zero-Mock Test Suite for CoChem-DOCK Visuals API (Stage 9.0).

Tests QCSchema parsing, mathematical lineshape convolution (Lorentzian, Gaussian,
Pseudo-Voigt), HDF5 1D/2D PES scans, inventory discovery, and FastAPI endpoints.
"""

import json
import math
from pathlib import Path
from typing import Generator

import h5py
import numpy as np
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from cochem_base.interfaces.cochem_dock_visuals_api import (
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    AxisLayout,
    PlotlyLayout,
    PlotlyPayload,
    QCSchemaPropertiesView,
    QCSchemaView,
    ScatterTrace,
    VisualArtifactSummary,
    convolve_spectrum,
    extract_qcschema_spectral_data,
    get_potential_energy_surface,
    get_spectrum,
    list_visual_artifacts,
    locate_hdf5_path,
    locate_qcschema_path,
    resolve_base_artifact_dir,
    router,
    validate_basin_id,
    visuals_health_check,
)


@pytest.fixture
def test_client() -> TestClient:
    """FastAPI test client instance for testing visuals endpoints."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def temp_artifact_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """Provide a sterile ephemeral artifact directory with Scratch subfolder."""
    scratch = tmp_path / "Scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(tmp_path))
    yield tmp_path


# =============================================================================
# 1. Basin ID Validation & Security Tests
# =============================================================================


def test_validate_basin_id_valid() -> None:
    """Verify valid basin identifiers pass validation."""
    valid_ids = ["water_dimer", "basin-001", "benzene.opt", "TS_isomer_123.final"]
    for b_id in valid_ids:
        assert validate_basin_id(b_id) == b_id


def test_validate_basin_id_directory_traversal_rejection() -> None:
    """Verify directory traversal attempts are rejected with HTTP 400."""
    invalid_ids = [
        "../etc/passwd",
        "..\\windows\\system32",
        "basin/sub",
        "basin\\sub",
        "",
        "   ",
        "basin*name",
        "basin;rm",
        "basin\0null",
    ]
    for b_id in invalid_ids:
        with pytest.raises(HTTPException) as exc_info:
            validate_basin_id(b_id)
        assert exc_info.value.status_code == 400


# =============================================================================
# 2. Mathematical Lineshape Convolution Tests
# =============================================================================


def test_convolve_spectrum_empty() -> None:
    """Verify empty frequency and intensity lists return empty grids."""
    x, y = convolve_spectrum([], [])
    assert x == []
    assert y == []

    x_mismatch, y_mismatch = convolve_spectrum([100.0], [10.0, 20.0])
    assert x_mismatch == []
    assert y_mismatch == []


def test_convolve_spectrum_invalid_parameters() -> None:
    """Verify invalid parameters raise ValueError."""
    with pytest.raises(ValueError, match="FWHM bandwidth parameter must be strictly positive"):
        convolve_spectrum([1000.0], [50.0], fwhm=0.0)

    with pytest.raises(ValueError, match="FWHM bandwidth parameter must be strictly positive"):
        convolve_spectrum([1000.0], [50.0], fwhm=-5.0)

    with pytest.raises(ValueError, match="n_points must be an integer >= 2"):
        convolve_spectrum([1000.0], [50.0], n_points=1)

    with pytest.raises(ValueError, match="freq_min .* must be strictly less than freq_max"):
        convolve_spectrum([1000.0], [50.0], freq_min=2000.0, freq_max=1000.0)


def test_convolve_spectrum_lorentzian() -> None:
    """Verify Lorentzian convolution lineshape properties."""
    # Water vibrational frequencies (cm⁻¹) and intensities (km/mol)
    freqs = [1595.0, 3657.0, 3756.0]
    intensities = [70.0, 10.0, 50.0]

    x, y = convolve_spectrum(
        frequencies=freqs,
        intensities=intensities,
        fwhm=10.0,
        n_points=500,
        profile="lorentzian",
    )

    assert len(x) == 500
    assert len(y) == 500
    assert min(x) < 1595.0
    assert max(x) > 3756.0

    # Max peak should be near the strongest band (1595 cm⁻¹)
    max_idx = int(np.argmax(y))
    peak_freq = x[max_idx]
    assert abs(peak_freq - 1595.0) < 15.0


def test_convolve_spectrum_gaussian() -> None:
    """Verify Gaussian convolution lineshape execution and peak alignment."""
    freqs = [1000.0, 2000.0]
    intensities = [20.0, 80.0]

    x, y = convolve_spectrum(
        frequencies=freqs,
        intensities=intensities,
        fwhm=12.0,
        n_points=1000,
        profile="gaussian",
    )

    assert len(x) == 1000
    assert len(y) == 1000

    # Max peak should be at 2000.0 cm⁻¹
    max_idx = int(np.argmax(y))
    assert abs(x[max_idx] - 2000.0) < 10.0


def test_convolve_spectrum_pseudo_voigt() -> None:
    """Verify Pseudo-Voigt convolution with varying mixing parameter."""
    freqs = [1200.0]
    intensities = [100.0]

    x_l, y_l = convolve_spectrum(freqs, intensities, fwhm=10.0, profile="lorentzian")
    x_g, y_g = convolve_spectrum(freqs, intensities, fwhm=10.0, profile="gaussian")
    x_pv, y_pv = convolve_spectrum(
        freqs, intensities, fwhm=10.0, profile="pseudo_voigt", voigt_fraction=0.5
    )

    assert len(x_pv) == 1000
    # Center peak of Pseudo-Voigt should be intermediate between pure Gaussian and Lorentzian
    max_idx = int(np.argmax(y_pv))
    assert y_g[max_idx] > y_pv[max_idx] > y_l[max_idx] or y_l[max_idx] > y_pv[max_idx] > y_g[max_idx]


# =============================================================================
# 3. QCSchema Spectral Data Extraction Tests
# =============================================================================


def test_extract_qcschema_standard_keys() -> None:
    """Verify extraction of standard calcinfo keys."""
    qcschema = {
        "schema_name": "qc_schema_output",
        "schema_version": 1,
        "properties": {
            "calcinfo_frequencies": [500.0, 1500.0, 3000.0],
            "calcinfo_ir_intensities": [12.5, 45.0, 80.0],
            "calcinfo_raman_intensities": [5.0, 10.0, 25.0],
            "return_energy": -76.4321,
            "scf_iterations": 12,
        },
    }

    freqs, ir, raman, meta = extract_qcschema_spectral_data(qcschema)
    assert freqs == [500.0, 1500.0, 3000.0]
    assert ir == [12.5, 45.0, 80.0]
    assert raman == [5.0, 10.0, 25.0]
    assert meta["return_energy"] == -76.4321
    assert meta["scf_iterations"] == 12


def test_extract_qcschema_alternative_keys() -> None:
    """Verify extraction from alternative or legacy QCSchema keys."""
    legacy_data = {
        "frequencies": [800.0, 1600.0],
        "intensities": [30.0, 60.0],
        "return_result": {"frequencies": [800.0, 1600.0], "ir_intensities": [30.0, 60.0]},
    }

    freqs, ir, raman, meta = extract_qcschema_spectral_data(legacy_data)
    assert freqs == [800.0, 1600.0]
    assert ir == [30.0, 60.0]
    assert raman is None


# =============================================================================
# 4. FastAPI Endpoints Integration Tests
# =============================================================================


def test_health_check_endpoint(test_client: TestClient, temp_artifact_workspace: Path) -> None:
    """Verify /api/visuals/health returns healthy status and artifact path."""
    response = test_client.get("/api/visuals/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["subsystem"] == "CoChem-DOCK.Visuals"
    assert data["stage"] == "9.0"
    assert data["artifact_dir_exists"] is True


def test_get_spectrum_not_found(test_client: TestClient, temp_artifact_workspace: Path) -> None:
    """Verify requesting non-existent basin returns 404."""
    response = test_client.get("/api/visuals/spectrum/non_existent_basin")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_spectrum_missing_data_error(test_client: TestClient, temp_artifact_workspace: Path) -> None:
    """Verify QCSchema missing frequencies returns 400 with [MISSING DATA]."""
    basin_id = "empty_schema"
    json_path = temp_artifact_workspace / "Scratch" / f"{basin_id}_qcschema.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"schema_name": "qc_schema_output", "properties": {}}, f)

    response = test_client.get(f"/api/visuals/spectrum/{basin_id}")
    assert response.status_code == 400
    assert "[MISSING DATA]" in response.json()["detail"]


def test_get_spectrum_success_with_broadening(test_client: TestClient, temp_artifact_workspace: Path) -> None:
    """Verify physical water dimer QCSchema spectrum endpoint with convolution broadening."""
    basin_id = "water_monomer"
    json_path = temp_artifact_workspace / "Scratch" / f"{basin_id}_qcschema.json"

    water_qcschema = {
        "schema_name": "qc_schema_output",
        "schema_version": 1,
        "basin_id": basin_id,
        "properties": {
            "calcinfo_frequencies": [1595.0, 3657.0, 3756.0],
            "calcinfo_ir_intensities": [70.5, 12.3, 55.8],
            "calcinfo_raman_intensities": [2.1, 15.4, 30.2],
            "return_energy": -76.438912,
            "scf_iterations": 8,
            "dipole_moment": [0.0, 0.0, 1.85],
        },
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(water_qcschema, f)

    # 1. Fetch discrete sticks
    resp_discrete = test_client.get(f"/api/visuals/spectrum/{basin_id}?broadening=false")
    assert resp_discrete.status_code == 200
    payload_d = resp_discrete.json()
    assert payload_d["basin_id"] == basin_id
    assert len(payload_d["data"]) == 1
    assert payload_d["data"][0]["x"] == [1595.0, 3657.0, 3756.0]
    assert payload_d["metadata"]["modes_count"] == 3
    assert payload_d["layout"]["xaxis"]["autorange"] == "reversed"

    # 2. Fetch convolved envelope with Gaussian lineshape
    resp_conv = test_client.get(
        f"/api/visuals/spectrum/{basin_id}?broadening=true&profile=gaussian&fwhm=10.0&points=500"
    )
    assert resp_conv.status_code == 200
    payload_c = resp_conv.json()
    assert len(payload_c["data"]) == 2  # Convolved curve + Sticks
    assert payload_c["data"][0]["mode"] == "lines"
    assert len(payload_c["data"][0]["x"]) == 500
    assert payload_c["metadata"]["broadening"] is True
    assert payload_c["metadata"]["profile"] == "gaussian"


def test_get_spectrum_both_ir_and_raman(test_client: TestClient, temp_artifact_workspace: Path) -> None:
    """Verify dual IR and Raman spectra retrieval."""
    basin_id = "co2_linear"
    json_path = temp_artifact_workspace / "Scratch" / f"{basin_id}_qcschema.json"

    co2_data = {
        "properties": {
            "calcinfo_frequencies": [667.0, 1388.0, 2349.0],
            "calcinfo_ir_intensities": [35.0, 0.0, 120.0],
            "calcinfo_raman_intensities": [0.0, 45.0, 0.0],
        }
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(co2_data, f)

    response = test_client.get(f"/api/visuals/spectrum/{basin_id}?spectrum_type=both&normalize=true")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["data"]) == 2
    assert payload["data"][0]["name"] == "Theoretical Spectrum"
    assert payload["data"][1]["name"] == "Theoretical Raman"
    assert payload["metadata"]["normalized"] is True


def test_get_spectrum_imaginary_ts_mode(test_client: TestClient, temp_artifact_workspace: Path) -> None:
    """Verify imaginary (transition-state) frequencies are properly tagged."""
    basin_id = "ts_sn2_reaction"
    json_path = temp_artifact_workspace / "Scratch" / f"{basin_id}_qcschema.json"

    ts_data = {
        "properties": {
            "calcinfo_frequencies": [-485.2, 520.0, 1200.0],
            "calcinfo_ir_intensities": [110.0, 15.0, 40.0],
        }
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(ts_data, f)

    response = test_client.get(f"/api/visuals/spectrum/{basin_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["imaginary_modes_count"] == 1
    assert "[TS/Imaginary]" in payload["data"][0]["text"][0]


# =============================================================================
# 5. Potential Energy Surface (HDF5) Tests
# =============================================================================


def test_get_pes_1d_scan(test_client: TestClient, temp_artifact_workspace: Path) -> None:
    """Verify 1D potential energy surface extraction and energy unit conversions."""
    basin_id = "torsion_scan_ethane"
    h5_path = temp_artifact_workspace / "Scratch" / f"{basin_id}_landscape.h5"

    angles = list(np.linspace(0.0, 360.0, 37))
    energies_hartree = [(-79.83 + 0.005 * math.cos(math.radians(3 * a))) for a in angles]

    with h5py.File(h5_path, "w") as h5_file:
        h5_file.create_dataset("coordinates", data=angles)
        h5_file.create_dataset("energies", data=energies_hartree)

    # 1. Fetch in kcal/mol (relative)
    resp_kcal = test_client.get(f"/api/visuals/landscape/{basin_id}?energy_unit=kcal/mol&relative=true")
    assert resp_kcal.status_code == 200
    data_kcal = resp_kcal.json()
    assert data_kcal["metadata"]["energy_unit"] == "kcal/mol"
    assert data_kcal["metadata"]["relative"] is True
    assert min(data_kcal["data"][0]["y"]) == 0.0
    assert abs(max(data_kcal["data"][0]["y"]) - (0.01 * HARTREE_TO_KCAL_MOL)) < 1e-3

    # 2. Fetch in eV
    resp_ev = test_client.get(f"/api/visuals/landscape/{basin_id}?energy_unit=ev&relative=true")
    assert resp_ev.status_code == 200
    data_ev = resp_ev.json()
    assert data_ev["metadata"]["energy_unit"] == "ev"


def test_get_pes_2d_surface(test_client: TestClient, temp_artifact_workspace: Path) -> None:
    """Verify 2D potential energy surface grid extraction."""
    basin_id = "ramachandran_grid"
    h5_path = temp_artifact_workspace / "Scratch" / f"{basin_id}_landscape.h5"

    phi = list(np.linspace(-180.0, 180.0, 10))
    psi = list(np.linspace(-180.0, 180.0, 10))
    grid_energies = np.zeros((10, 10), dtype=np.float64)
    for i in range(10):
        for j in range(10):
            grid_energies[i, j] = -150.0 + 0.01 * (math.sin(phi[i]) + math.cos(psi[j]))

    with h5py.File(h5_path, "w") as h5_file:
        h5_file.create_dataset("coordinates", data=phi)
        h5_file.create_dataset("coordinates_y", data=psi)
        h5_file.create_dataset("energies", data=grid_energies)

    response = test_client.get(f"/api/visuals/landscape/{basin_id}?energy_unit=kcal/mol")
    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["is_2d"] is True
    assert payload["data"][0]["type"] == "contour"
    assert len(payload["data"][0]["z"]) == 10


# =============================================================================
# 6. Inventory Discovery Tests
# =============================================================================


def test_list_visual_artifacts_inventory(test_client: TestClient, temp_artifact_workspace: Path) -> None:
    """Verify /api/visuals/inventory finds both QCSchema JSON and HDF5 PES files."""
    scratch = temp_artifact_workspace / "Scratch"

    # Create QCSchema artifact
    q_file = scratch / "basin_alpha_qcschema.json"
    with open(q_file, "w", encoding="utf-8") as f:
        json.dump({"properties": {"calcinfo_frequencies": [100.0, 200.0], "calcinfo_ir_intensities": [5.0, 10.0]}}, f)

    # Create HDF5 artifact
    h5_file = scratch / "basin_alpha_landscape.h5"
    with h5py.File(h5_file, "w") as h5:
        h5.create_dataset("coordinates", data=[1.0, 2.0])
        h5.create_dataset("energies", data=[-10.0, -9.5])

    response = test_client.get("/api/visuals/inventory")
    assert response.status_code == 200
    inv = response.json()
    assert len(inv) >= 1

    alpha = next((item for item in inv if item["basin_id"] == "basin_alpha"), None)
    assert alpha is not None
    assert alpha["has_qcschema"] is True
    assert alpha["has_hdf5"] is True
    assert alpha["frequencies_count"] == 2
    assert alpha["qcschema_filename"] == "basin_alpha_qcschema.json"
    assert alpha["hdf5_filename"] == "basin_alpha_landscape.h5"


def test_interfaces_reexports_and_compatibility() -> None:
    """Verify interfaces.cochem_dock_visuals_api re-exports identical symbols."""
    import cochem_base.interfaces.cochem_dock_visuals_api as base_mod
    import interfaces.cochem_dock_visuals_api as iface_mod

    assert iface_mod.router is base_mod.router
    assert iface_mod.visuals_router is base_mod.visuals_router
    assert iface_mod.get_spectrum is base_mod.get_spectrum
    assert iface_mod.get_potential_energy_surface is base_mod.get_potential_energy_surface
    assert iface_mod.list_visual_artifacts is base_mod.list_visual_artifacts
    assert iface_mod.visuals_health_check is base_mod.visuals_health_check
    assert iface_mod.convolve_spectrum is base_mod.convolve_spectrum
    assert iface_mod.extract_qcschema_spectral_data is base_mod.extract_qcschema_spectral_data
    assert iface_mod.validate_basin_id is base_mod.validate_basin_id
    assert iface_mod.resolve_base_artifact_dir is base_mod.resolve_base_artifact_dir
    assert iface_mod.locate_qcschema_path is base_mod.locate_qcschema_path
    assert iface_mod.locate_hdf5_path is base_mod.locate_hdf5_path
    assert iface_mod.AxisLayout is base_mod.AxisLayout
    assert iface_mod.PlotlyLayout is base_mod.PlotlyLayout
    assert iface_mod.PlotlyPayload is base_mod.PlotlyPayload
    assert iface_mod.ScatterTrace is base_mod.ScatterTrace
    assert iface_mod.QCSchemaView is base_mod.QCSchemaView
    assert iface_mod.QCSchemaPropertiesView is base_mod.QCSchemaPropertiesView
    assert iface_mod.VisualArtifactSummary is base_mod.VisualArtifactSummary
    assert iface_mod.HARTREE_TO_KCAL_MOL == base_mod.HARTREE_TO_KCAL_MOL
    assert iface_mod.HARTREE_TO_EV == base_mod.HARTREE_TO_EV
    assert iface_mod.HARTREE_TO_KJ_MOL == base_mod.HARTREE_TO_KJ_MOL

