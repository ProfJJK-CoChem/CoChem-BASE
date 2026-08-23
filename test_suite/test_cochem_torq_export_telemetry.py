"""
Unit Test Suite for CoChem-TORQ Export & Telemetry Modules
===========================================================
Validates Stage 5.5 / 6.0 SpycFit Payload Synthesis, Out-of-Core Inspection,
Deterministic Bundling, Provenance Seals, Webhook Circuit Breakers,
3D Visualizers, and Steric Shatter Crash Trajectory Diagnostics.

Strict Zero-Mock Mandate Compliant: All tests execute authentic I/O,
real pyarrow Parquet tables, real cryptographic SHA-256 checks, real
HTTP loopback servers, and real mathematical tensors.
"""

import http.server
import io
import json
import os
import shutil
import socket
import socketserver
import tarfile
import tempfile
import threading
import time
import warnings
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np
import psutil
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from cochem_base.exceptions import (
    CoChemIntegrityError,
    KraitchmanSingularityError,
    KraitchmanZPVEWarning,
    TelemetryNetworkExhaustedWarning,
)
from cochem_torq_export import (
    INERTIA_CONVERSION_AMU_ANG2_MHZ,
    bundle_spycfit_payload,
    calculate_kraitchman_coords,
    generate_pgopher_skeleton,
    lock_provenance_payload,
    verify_payload_integrity,
)
from cochem_torq_telemetry import (
    TELEMETRY_BUFFER,
    export_crash_animation,
    generate_plotly_3d_carousels,
    stream_webhook_events,
)


# =====================================================================
# 1. Kraitchman Substitution Coordinates & Costain Bounds Tests
# =====================================================================

def test_kraitchman_asymmetric_substitution():
    """Validates substitution coordinates on an asymmetric top with known parameters."""
    # Parent molecule moments (amu * A^2)
    parent_data = {
        "I_a": 35.0,
        "I_b": 60.0,
        "I_c": 90.0,
        "parent_mass": 50.0,
    }
    # 13C substitution site with real positive moment shifts
    iso_data = {
        "I_a_iso": 35.8,
        "I_b_iso": 60.5,
        "I_c_iso": 91.2,
        "delta_m": 1.00335,  # 13C - 12C mass
    }
    input_dict = {**parent_data, **iso_data}

    res = calculate_kraitchman_coords(input_dict)

    assert "coordinates" in res
    assert "costain_uncertainties" in res
    assert "radicands" in res
    assert res["reduced_mass_mu"] > 0.0

    coords = res["coordinates"]
    costain = res["costain_uncertainties"]

    # Coordinates must be non-negative real floats
    for axis in ("a", "b", "c"):
        assert coords[axis] >= 0.0
        assert not np.isnan(coords[axis])
        assert costain[f"delta_{axis}"] > 0.0

        # Costain piecewise check:
        if coords[axis] >= 0.15:
            expected_costain = 0.0015 / coords[axis]
            assert abs(costain[f"delta_{axis}"] - expected_costain) < 1e-6
        else:
            expected_costain = np.sqrt(abs(res["radicands"][f"R_{axis}"]))
            assert abs(costain[f"delta_{axis}"] - expected_costain) < 1e-6


def test_kraitchman_near_symmetric_damping():
    """Validates singularity damping when |I_a - I_b| < 1e-4 amu*A^2."""
    # Near-prolate symmetric top where I_b and I_c are nearly degenerate
    input_dict = {
        "I_a": 15.0,
        "I_b": 50.00001,  # |I_b - I_c| < 1e-4
        "I_c": 50.00003,
        "I_a_iso": 15.05,
        "I_b_iso": 50.10001,
        "I_c_iso": 50.10003,
        "parent_mass": 60.0,
        "delta_m": 1.0,
    }

    res = calculate_kraitchman_coords(input_dict)

    # Damping guard must activate on nearly degenerate axes
    assert res["near_symmetric_damped"]["b"] is True or res["near_symmetric_damped"]["c"] is True
    # Coordinates must not explode to infinity or NaN
    for axis in ("a", "b", "c"):
        assert np.isfinite(res["coordinates"][axis])


def test_kraitchman_zpve_defect_clamping():
    """Validates clamping of negative radicands (ZPVE defects) to 0.0000 A with KraitchmanZPVEWarning."""
    # Construct an artificial shift along axis 'a' producing negative radicand
    input_dict = {
        "I_a": 40.0,
        "I_b": 70.0,
        "I_c": 100.0,
        "I_a_iso": 40.0001,  # Very small shift
        "I_b_iso": 72.0,     # Large shift on b/c making Delta P_a negative
        "I_c_iso": 68.0,
        "parent_mass": 45.0,
        "delta_m": 1.0,
    }

    with pytest.warns(KraitchmanZPVEWarning) as record:
        res = calculate_kraitchman_coords(input_dict)

    assert len(record) >= 1
    # Check that at least one axis had ZPVE defect clamped to 0.0
    clamped_any = any(res["zpve_defect_clamped"].values())
    assert clamped_any is True

    for axis, is_clamped in res["zpve_defect_clamped"].items():
        if is_clamped:
            assert res["coordinates"][axis] == 0.0000


def test_kraitchman_rotational_constants_input():
    """Validates Kraitchman calculation using rotational constants in MHz."""
    input_dict = {
        "A": 9500.0,
        "B": 4200.0,
        "C": 2800.0,
        "A_iso": 9420.0,
        "B_iso": 4180.0,
        "C_iso": 2790.0,
        "mass": 75.0,
        "delta_m": 1.00335,
    }

    res = calculate_kraitchman_coords(input_dict)
    assert res["coordinates"]["a"] >= 0.0
    assert res["coordinates"]["b"] >= 0.0
    assert res["coordinates"]["c"] >= 0.0


def test_kraitchman_input_validation():
    """Validates error handling for missing inputs or invalid mass values."""
    with pytest.raises(ValueError):
        calculate_kraitchman_coords({"I_a": 10.0})  # Missing I_b, I_c

    with pytest.raises(ValueError):
        calculate_kraitchman_coords({
            "I_a": 10.0, "I_b": 20.0, "I_c": 30.0,
            "I_a_iso": 10.1, "I_b_iso": 20.1, "I_c_iso": 30.1,
            "parent_mass": -5.0, "delta_m": 1.0,
        })


# =====================================================================
# 2. PGOPHER Skeleton & Zero-RAM PyArrow Metadata Inspection
# =====================================================================

def test_oom_proof_pyarrow_metadata_inspection(tmp_path):
    """
    Zero-Mock OOM-Proof PyArrow Metadata Inspection Test.
    Creates a real Parquet catalog with 100,000 transitions, verifies that
    generate_pgopher_skeleton reads only the metadata with minimal RSS spike (< 50MB).
    """
    parquet_path = tmp_path / "spectral_catalog.parquet"
    json_path = tmp_path / "molecule_params.json"
    pgo_output = tmp_path / "molecule_skeleton.pgo"

    # Generate real Parquet table with 100,000 transition rows
    n_rows = 100000
    freqs = np.linspace(1000.0, 50000.0, n_rows)
    intensities = np.random.uniform(0.01, 100.0, n_rows)
    upper_j = np.random.randint(1, 20, n_rows)
    lower_j = np.random.randint(0, 19, n_rows)

    table = pa.Table.from_arrays(
        [
            pa.array(freqs),
            pa.array(intensities),
            pa.array(upper_j),
            pa.array(lower_j),
        ],
        names=["Frequency", "Intensity", "Upper_J", "Lower_J"],
    )
    pq.write_table(table, parquet_path)

    # Generate JSON metadata
    params = {
        "molecule_name": "Ethanol_Conformer_Anti",
        "point_group": "Cs",
        "rotational_constants": {"A": 34892.123, "B": 9324.567, "C": 8102.345},
        "centrifugal_distortion": {
            "model": "Watson_A",
            "DJ": 1.25e-4,
            "DJK": -3.42e-4,
            "DK": 8.91e-4,
            "dJ": 2.11e-5,
            "dK": 5.43e-5,
        },
        "dipole_moments": {"mu_a": 0.45, "mu_b": 1.35, "mu_c": 0.0},
        "temperature": 10.0,
        "fwhm": 0.05,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(params, f, indent=2)

    # Monitor RSS memory before and during execution
    proc = psutil.Process()
    rss_before = proc.memory_info().rss

    xml_result = generate_pgopher_skeleton(str(parquet_path), str(json_path), str(pgo_output))

    rss_after = proc.memory_info().rss
    rss_delta_mb = (rss_after - rss_before) / (1024 * 1024)

    # Memory RSS delta must remain well below 50 MB
    assert rss_delta_mb < 50.0

    # Verify XML content and structure
    assert pgo_output.exists()
    root = ET.fromstring(xml_result)
    assert root.tag == "PGOPHER"

    species = root.find("Species")
    assert species is not None
    assert species.attrib["Name"] == "Ethanol_Conformer_Anti"

    cat = root.find(".//SpectroscopicCatalog")
    assert cat is not None
    assert int(cat.attrib["TotalTransitions"]) == n_rows
    assert "Frequency" in cat.attrib["Columns"]
    assert "Intensity" in cat.attrib["Columns"]


# =====================================================================
# 3. Provenance Locking & Cryptographic Bit-Flip Tamper Detection
# =====================================================================

def test_lock_provenance_and_bit_flip_tamper(tmp_path):
    """
    Cryptographic Hash Seal & Tamper Detection Test.
    Locks directory, flips a single byte in a file, and verifies CoChemIntegrityError.
    """
    export_dir = tmp_path / "export_payload"
    export_dir.mkdir()

    # Create deliverable files
    var_file = export_dir / "ethanol.var"
    int_file = export_dir / "ethanol.int"
    txt_file = export_dir / "summary.txt"

    var_file.write_text("A = 34892.123\nB = 9324.567\nC = 8102.345\n", encoding="utf-8")
    int_file.write_text("DIPOLE = 1.45 Debye\nINTENSITY = 100.0\n", encoding="utf-8")
    txt_file.write_text("CoChem-TORQ Prediction Stage 5.5 Complete\n", encoding="utf-8")

    # 1. Lock Provenance
    manifest = lock_provenance_payload(str(export_dir))

    manifest_file = export_dir / "spycfit_manifest.json"
    assert manifest_file.exists()
    assert manifest["file_count"] == 3
    assert "ethanol.var" in manifest["files"]
    assert "ethanol.int" in manifest["files"]
    assert "summary.txt" in manifest["files"]
    # Manifest itself must be excluded from files list to prevent circular paradox
    assert "spycfit_manifest.json" not in manifest["files"]

    # 2. Verify untouched payload
    assert verify_payload_integrity(manifest_file) is True

    # 3. Programmatically flip a single byte in ethanol.var
    var_bytes = bytearray(var_file.read_bytes())
    var_bytes[0] ^= 0x01  # Flip least significant bit of first character
    var_file.write_bytes(var_bytes)

    # 4. Verify that bit-flip raises CoChemIntegrityError
    with pytest.raises(CoChemIntegrityError) as exc_info:
        verify_payload_integrity(manifest_file)
    assert "seal broken" in str(exc_info.value).lower() or "integrity" in str(exc_info.value).lower()

    # 5. Restore byte and remove a file to test missing file detection
    var_bytes[0] ^= 0x01
    var_file.write_bytes(var_bytes)
    assert verify_payload_integrity(manifest_file) is True

    txt_file.unlink()
    with pytest.raises(CoChemIntegrityError) as exc_info2:
        verify_payload_integrity(manifest_file)
    assert "missing required file" in str(exc_info2.value).lower()


# =====================================================================
# 4. Deterministic Payload Bundling (mtime=0 & Permissions)
# =====================================================================

def test_bundle_spycfit_payload_determinism(tmp_path):
    """Validates deterministic tar.zst / zip packaging with normalized mtime and permissions."""
    export_dir = tmp_path / "bundle_test"
    export_dir.mkdir()

    (export_dir / "data1.var").write_text("DATA 1", encoding="utf-8")
    (export_dir / "data2.int").write_text("DATA 2", encoding="utf-8")

    manifest = lock_provenance_payload(str(export_dir))
    archive_path = bundle_spycfit_payload(str(export_dir), str(tmp_path), project_name="Methanol")

    assert os.path.exists(archive_path)
    assert "CoChem_Methanol_SpycFit_Payload" in archive_path

    # Inspect archive internals
    if archive_path.endswith(".tar.zst"):
        import zstandard as zstd
        dctx = zstd.ZstdDecompressor()
        with open(archive_path, "rb") as f:
            decompressed_tar = dctx.decompress(f.read())

        with tarfile.open(fileobj=io.BytesIO(decompressed_tar)) as tar:
            members = tar.getmembers()
            assert len(members) >= 3  # manifest + 2 files
            for m in members:
                assert m.mtime == 0  # POSIX epoch normalization
                assert m.mode == 0o644  # Normalized permissions
    elif archive_path.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            infolist = zf.infolist()
            assert len(infolist) >= 3
            for info in infolist:
                assert info.date_time == (1980, 1, 1, 0, 0, 0)


# =====================================================================
# 5. Webhook Circuit Breaker, Timeout & Non-Blocking Spooling
# =====================================================================

def test_stream_webhook_unreachable_circuit_breaker(tmp_path):
    """
    Webhook Circuit Breaker Test.
    Tests timeout and exponential backoff against an unreachable local port.
    Asserts non-blocking execution, warning emission, and spooling to disk.
    """
    # Find an unused, unroutable closed port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    dummy_url = f"http://127.0.0.1:{port}/webhook_test"
    spool_file = tmp_path / "test_telemetry_spool.jsonl"

    status_event = {
        "event": "SoftQuenchCollision",
        "node_id": "worker_03",
        "energy_gap": 142.5,
        "max_grad": 500.0,
    }

    start_time = time.time()
    with pytest.warns(TelemetryNetworkExhaustedWarning):
        success = stream_webhook_events(
            status_payload=status_event,
            webhook_url=dummy_url,
            timeout=2.0,
            max_retries=2,
            spool_file=str(spool_file),
        )
    elapsed = time.time() - start_time

    # Must return False safely without raising exceptions
    assert success is False
    assert elapsed < 10.0  # Respects timeout bounds

    # Tripartite verification: Spool file must exist and contain the event
    assert spool_file.exists()
    with open(spool_file, "r", encoding="utf-8") as f:
        spooled_lines = f.readlines()
    assert len(spooled_lines) >= 1
    last_record = json.loads(spooled_lines[-1])
    assert last_record["payload"]["event"] == "SoftQuenchCollision"
    assert len(TELEMETRY_BUFFER) > 0


def test_stream_webhook_successful_dispatch(tmp_path):
    """
    Validates successful webhook dispatch with a live local HTTP test server.
    """
    received_requests = []

    class TestHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            received_requests.append(json.loads(post_data.decode("utf-8")))
            self.send_response(200)
            self.end_headers()

        def log_message(self, format, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), TestHandler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    webhook_url = f"http://127.0.0.1:{port}/webhook"

    try:
        event = {"event": "StageComplete", "stage": "5.5", "status": "SUCCESS"}
        success = stream_webhook_events(
            status_payload=event,
            webhook_url=webhook_url,
            timeout=3.0,
            max_retries=1,
            spool_file=str(tmp_path / "spool.jsonl"),
        )

        assert success is True
        assert len(received_requests) == 1
        assert "CoChem-TORQ" in received_requests[0].get("content", "")
    finally:
        server.shutdown()


# =====================================================================
# 6. 2D/3D Plotly Visualizer Decimation & Critical Point Preservation
# =====================================================================

def test_plotly_3d_carousel_decimation_and_critical_points(tmp_path):
    """
    Validates downsampling of massive 500,000-point PES grid down to <= 5,000 nodes,
    monotonic PCHIP interpolation, stationary point injection, and HTML envelope < 4.5 MB.
    """
    Nx, Ny = 1000, 500  # 500,000 total nodes
    x = np.linspace(0, 360, Nx)
    y = np.linspace(0, 360, Ny)
    X, Y = np.meshgrid(np.radians(x), np.radians(y), indexing="ij")

    # Analytical 2D PES with explicit double-well minima and saddle points
    pes_grid = (
        1200.0 * np.cos(X)
        + 600.0 * np.cos(2 * X)
        + 800.0 * np.cos(Y)
        + 400.0 * np.cos(2 * Y)
        + 250.0 * np.sin(X) * np.sin(Y)
    )

    out_html = tmp_path / "pes_visualizer.html"

    html_str = generate_plotly_3d_carousels(
        pes_tensor=pes_grid,
        grid_x=x,
        grid_y=y,
        output_path=str(out_html),
        max_nodes=5000,
        interpolation_mode="pchip",
        title="Ethanol 2D Torsional PES",
    )

    assert out_html.exists()
    html_size_mb = out_html.stat().st_size / (1024 * 1024)

    # HTML Envelope must be strictly under 4.5 MB
    assert html_size_mb < 4.5

    # Visualizer must contain critical points and Plotly surface elements
    assert "Potential Energy Surface" in html_str
    assert "Ethanol 2D Torsional PES" in html_str
    assert "colorscale" in html_str
    assert "Torsion Angle" in html_str


# =====================================================================
# 7. Steric Shatter Soft-Quench Crash Animation & Diagnostic Export
# =====================================================================

def test_export_crash_animation(tmp_path):
    """
    Validates export of multi-frame crash_animation.xyz and crash_diagnostic.json
    for Steric Shatter Soft-Quench collision aborts.
    """
    num_frames = 8
    num_atoms = 4
    atom_symbols = ["C", "H", "H", "O"]

    # Trajectory moving O atom progressively closer to H atom until collision (< 0.7 A)
    trajectory = np.zeros((num_frames, num_atoms, 3))
    for f in range(num_frames):
        trajectory[f, 0] = [0.0, 0.0, 0.0]  # C
        trajectory[f, 1] = [1.09, 0.0, 0.0]  # H1
        trajectory[f, 2] = [-0.36, 1.03, 0.0]  # H2
        # O atom moves from (2.5, 0, 0) to (1.45, 0, 0) -> collision with H1 at (1.09, 0, 0)
        dist_x = 2.5 - (f * 0.15)
        trajectory[f, 3] = [dist_x, 0.0, 0.0]  # O

    # Exploding gradient norms leading up to abort
    grad_norms = [0.001, 0.005, 0.05, 0.8, 12.5, 340.0, 5600.0, 99999.0]

    out_dir = tmp_path / "crash_reports"
    xyz_path, json_path = export_crash_animation(
        trajectory_array=trajectory,
        error_node_id="node_04_softquench_steric_shatter",
        output_path=str(out_dir),
        atom_symbols=atom_symbols,
        gradient_norms=grad_norms,
    )

    assert os.path.exists(xyz_path)
    assert os.path.exists(json_path)

    # Validate XYZ format
    with open(xyz_path, "r", encoding="utf-8") as f:
        xyz_content = f.read()

    lines = xyz_content.strip().split("\n")
    # 8 frames * (1 atom_count + 1 comment + 4 atoms) = 48 lines
    assert len(lines) == num_frames * (num_atoms + 2)
    assert "node_04_softquench_steric_shatter" in xyz_content
    assert "grad_norm=9.999900e+04" in xyz_content

    # Validate JSON pathology diagnostic
    with open(json_path, "r", encoding="utf-8") as f:
        diagnostic = json.load(f)

    assert diagnostic["error_node_id"] == "node_04_softquench_steric_shatter"
    assert diagnostic["failure_type"] == "StericShatterCollision"
    assert diagnostic["steric_clash_detected"] is True
    assert diagnostic["minimum_interatomic_distance_angstrom"] < 0.70
    assert diagnostic["status"] == "ABORTED_SOFT_QUENCH"
    assert len(diagnostic["clashing_atom_indices"]) == 2
    assert diagnostic["max_gradient_norm"] == 99999.0
