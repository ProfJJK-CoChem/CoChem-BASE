"""Zero-Mock Production Test Suite for VisualAssetBridge (CoChem-SCRIBE Stage 6.3).

Strictly adheres to:
- CoChem-SCRIBE SRS Phase 4, Task 10 (Stage 6.3, Tasks 75-78, 80)
- Method Matrix v4
- Zero-Mock Anti-Spoofing Protocol: Real filesystem I/O, real zstandard byte streams,
  real tmp_path files, real >= 51 MB synthetic binary .cube and .html files.
- 6-Tier Environment Matrix (POSIX path assertions).
- Complete, functional Python 3.10+ code with zero mocks, zero stubs, zero pass blocks.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
from typing import Any

import pytest

from formatters.scribe_viz_bridge import (
    CHUNK_SIZE_BYTES,
    DEFAULT_50MB_THRESHOLD,
    DEFAULT_COMPRESSION_LEVEL,
    VisualAssetBridge,
)

# Test constants to eliminate magic values and enforce zero-mock invariants
MIN_COMPRESSION_SAVINGS_PCT: float = 80.0
SYNTHETIC_CHUNK_64KB_COUNT_51MB: int = 816  # 816 * 65536 = 53,477,376 bytes (51.0 MB)
SYNTHETIC_CHUNK_64KB_COUNT_1MB: int = 16  # 16 * 65536 = 1,048,576 bytes (1.0 MB)
EXPECTED_SPECTRAL_FIGURES_COUNT: int = 3
EXPECTED_COMPRESSED_COUNT_SINGLE: int = 1
SYNTHETIC_ORIG_SIZE_60MB: int = 62914560
SYNTHETIC_COMP_SIZE_4MB: int = 4194304
SYNTHETIC_ORIG_SIZE_50MB: int = 52428800
SYNTHETIC_COMP_SIZE_5MB: int = 5242880
SUBPROCESS_TIMEOUT_SECONDS: int = 30


# ==============================================================================
# Pytest Fixture Architecture (Real Disk via tmp_path)
# ==============================================================================


@pytest.fixture
def large_volumetric_cube_file(tmp_path: pathlib.Path) -> pathlib.Path:
    """Dynamically creates a physical .cube binary file exceeding 50 MB threshold.

    Creates >= 51 MB (53,477,376 bytes) structured floating-point density grid bytes
    at tmp_path / "artifacts" / "esp_grid_large.cube" via 64 KB buffered streaming.
    """
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    cube_file = artifacts_dir / "esp_grid_large.cube"

    pattern_chunk = (
        b"ESP_DENSITY_GRID_DATA_CHUNK_64KB_" + b"0123456789ABCDEF" * 4100
    )[:CHUNK_SIZE_BYTES]  # Exactly 65536 bytes
    assert len(pattern_chunk) == CHUNK_SIZE_BYTES

    with open(cube_file, "wb") as f_out:
        for _ in range(SYNTHETIC_CHUNK_64KB_COUNT_51MB):
            f_out.write(pattern_chunk)

    assert cube_file.stat().st_size >= DEFAULT_50MB_THRESHOLD
    return cube_file


@pytest.fixture
def small_volumetric_cube_file(tmp_path: pathlib.Path) -> pathlib.Path:
    """Dynamically creates a physical sub-threshold .cube file (1 MB / 1,048,576 bytes).

    Located at tmp_path / "artifacts" / "esp_grid_small.cube".
    """
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    cube_file = artifacts_dir / "esp_grid_small.cube"

    pattern_chunk = (
        b"ESP_DENSITY_GRID_DATA_CHUNK_64KB_" + b"0123456789ABCDEF" * 4100
    )[:CHUNK_SIZE_BYTES]  # Exactly 65536 bytes
    assert len(pattern_chunk) == CHUNK_SIZE_BYTES

    with open(cube_file, "wb") as f_out:
        for _ in range(SYNTHETIC_CHUNK_64KB_COUNT_1MB):
            f_out.write(pattern_chunk)

    assert cube_file.stat().st_size < DEFAULT_50MB_THRESHOLD
    return cube_file


@pytest.fixture
def large_volumetric_html_file(tmp_path: pathlib.Path) -> pathlib.Path:
    """Dynamically creates a physical .html 3D carousel file >= 51 MB.

    Located at tmp_path / "artifacts" / "molstar_interactive_large.html".
    """
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    html_file = artifacts_dir / "molstar_interactive_large.html"

    pattern_chunk = (
        b"<div><canvas data-grid='VOLUMETRIC_3D_NGL_STREAM'></canvas></div>\n"
        * 1024
    )[:CHUNK_SIZE_BYTES]  # Exactly 65536 bytes
    assert len(pattern_chunk) == CHUNK_SIZE_BYTES

    with open(html_file, "wb") as f_out:
        for _ in range(SYNTHETIC_CHUNK_64KB_COUNT_51MB):
            f_out.write(pattern_chunk)

    assert html_file.stat().st_size >= DEFAULT_50MB_THRESHOLD
    return html_file


@pytest.fixture
def spectral_figure_assets(tmp_path: pathlib.Path) -> dict[str, pathlib.Path]:
    """Creates a dedicated figures directory with authentic 2D spectral image assets.

    Includes ir_spectrum.png, raman_spectrum.svg, uv_vis_spectrum.pdf,
    and noise/filter files: ir_spectrum_thumb.png, .hidden_spectrum.png, data.csv.
    """
    fig_dir = tmp_path / "artifacts" / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    ir_img = fig_dir / "ir_spectrum.png"
    raman_img = fig_dir / "raman_spectrum.svg"
    uv_vis_img = fig_dir / "uv_vis_spectrum.pdf"
    thumb_img = fig_dir / "ir_spectrum_thumb.png"
    hidden_img = fig_dir / ".hidden_spectrum.png"
    non_img = fig_dir / "data.csv"

    # Real byte formats for authentic assets
    ir_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 200)
    raman_img.write_text(
        "<svg xmlns='http://www.w3.org/2000/svg'><path d='M0 0 L10 10'/></svg>",
        encoding="utf-8",
    )
    uv_vis_img.write_bytes(
        b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    )
    thumb_img.write_bytes(b"THUMBNAIL_PREVIEW_BYTES")
    hidden_img.write_bytes(b"HIDDEN_CACHE_BYTES")
    non_img.write_text("wavenumber,intensity\n1000,0.5\n", encoding="utf-8")

    return {
        "figures_dir": fig_dir,
        "ir": ir_img,
        "raman": raman_img,
        "uv_vis": uv_vis_img,
        "thumb": thumb_img,
        "hidden": hidden_img,
        "non_img": non_img,
    }


@pytest.fixture
def configured_bridge(tmp_path: pathlib.Path) -> VisualAssetBridge:
    """Instantiates VisualAssetBridge configured with dynamic tmp_path paths."""
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_archive_dir = tmp_path / "Report_Archive"
    report_archive_dir.mkdir(parents=True, exist_ok=True)
    user_guide_path = report_archive_dir / "CoChem_User_Guide.md"

    return VisualAssetBridge(
        artifacts_dir=artifacts_dir,
        report_archive_dir=report_archive_dir,
        user_guide_path=user_guide_path,
        compression_threshold_bytes=DEFAULT_50MB_THRESHOLD,
        compression_level=DEFAULT_COMPRESSION_LEVEL,
    )


# ==============================================================================
# Required Test Cases (Tasks 75-78, 80)
# ==============================================================================


def test_visual_asset_bridge_initialization_and_dynamic_pathing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test Case 1: VisualAssetBridge Initialization & Dynamic Pathing.
    
    Covers Tasks 75 & 78.
    """
    # 1. Default initialization without parameters or environment variables
    monkeypatch.delenv("COCHEM_ARTIFACTS_DIR", raising=False)
    monkeypatch.delenv("COCHEM_REPORT_ARCHIVE_DIR", raising=False)
    monkeypatch.delenv("COCHEM_USER_GUIDE_PATH", raising=False)

    bridge_default = VisualAssetBridge()
    expected_default_art = pathlib.Path.home() / "CoChem_Artifacts"
    expected_default_rep = expected_default_art / "Report_Archive"
    expected_default_guide = expected_default_rep / "CoChem_User_Guide.md"

    assert bridge_default.artifacts_dir == expected_default_art
    assert bridge_default.report_archive_dir == expected_default_rep
    assert bridge_default.user_guide_path == expected_default_guide
    assert bridge_default.compression_threshold_bytes == DEFAULT_50MB_THRESHOLD
    assert bridge_default.compression_threshold_bytes == 52428800
    assert bridge_default.compression_level == DEFAULT_COMPRESSION_LEVEL
    assert bridge_default.compression_level == 19

    # 2. Custom path initialization
    custom_art = tmp_path / "custom_artifacts"
    custom_rep = tmp_path / "custom_reports"
    custom_guide = tmp_path / "custom_guide.md"

    bridge_custom = VisualAssetBridge(
        artifacts_dir=str(custom_art),
        report_archive_dir=str(custom_rep),
        user_guide_path=str(custom_guide),
        compression_threshold_bytes=1048576,
        compression_level=12,
    )

    assert bridge_custom.artifacts_dir == custom_art
    assert isinstance(bridge_custom.artifacts_dir, pathlib.Path)
    assert bridge_custom.report_archive_dir == custom_rep
    assert isinstance(bridge_custom.report_archive_dir, pathlib.Path)
    assert bridge_custom.user_guide_path == custom_guide
    assert isinstance(bridge_custom.user_guide_path, pathlib.Path)
    assert bridge_custom.compression_threshold_bytes == 1048576
    assert bridge_custom.compression_level == 12

    # 3. Dynamic pathing via environment variables
    env_art = tmp_path / "env_artifacts"
    env_rep = tmp_path / "env_reports"
    env_guide = tmp_path / "env_guide.md"

    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(env_art))
    monkeypatch.setenv("COCHEM_REPORT_ARCHIVE_DIR", str(env_rep))
    monkeypatch.setenv("COCHEM_USER_GUIDE_PATH", str(env_guide))

    bridge_env = VisualAssetBridge()
    assert bridge_env.artifacts_dir == env_art
    assert bridge_env.report_archive_dir == env_rep
    assert bridge_env.user_guide_path == env_guide


def test_volumetric_artifact_discovery(
    tmp_path: pathlib.Path, configured_bridge: VisualAssetBridge
) -> None:
    """Test Case 2: Volumetric Artifact Discovery (Task 75)."""
    artifacts_dir = tmp_path / "artifacts"
    nested_dir = artifacts_dir / "nested" / "sub_calc"
    nested_dir.mkdir(parents=True, exist_ok=True)

    # Valid volumetric candidate files (.cube, .html)
    cube_root = artifacts_dir / "esp_density.cube"
    cube_nested = nested_dir / "homo_lumo_grid.cube"
    html_root = artifacts_dir / "interactive_3d.html"
    html_nested = nested_dir / "molstar_view.html"

    cube_root.write_bytes(b"CUBE_ROOT")
    cube_nested.write_bytes(b"CUBE_NESTED")
    html_root.write_bytes(b"HTML_ROOT")
    html_nested.write_bytes(b"HTML_NESTED")

    # Non-volumetric or filtered files
    (artifacts_dir / "plot.png").write_bytes(b"PNG_DATA")
    (artifacts_dir / "diagram.svg").write_text("<svg></svg>", encoding="utf-8")
    (artifacts_dir / "calc_meta.json").write_text("{}", encoding="utf-8")
    (artifacts_dir / "references.bib").write_text("@article{}", encoding="utf-8")
    (artifacts_dir / "notes.txt").write_text("calculation notes", encoding="utf-8")
    (artifacts_dir / ".hidden_volumetric.cube").write_bytes(b"HIDDEN_CUBE")
    (artifacts_dir / "existing_archive.cube.tar.zst").write_bytes(b"ZST_ARCHIVE")
    (artifacts_dir / "existing_single.cube.zst").write_bytes(b"ZST_FILE")

    discovered = configured_bridge.scan_volumetric_artifacts()

    expected = sorted([cube_root, cube_nested, html_root, html_nested])
    assert discovered == expected
    assert len(discovered) == 4
    assert all(isinstance(p, pathlib.Path) for p in discovered)
    assert cube_root in discovered
    assert cube_nested in discovered
    assert html_root in discovered
    assert html_nested in discovered


def test_zstandard_compression_boundary_50mb(
    configured_bridge: VisualAssetBridge, large_volumetric_cube_file: pathlib.Path
) -> None:
    """Test Case 3: Zstandard Max-Ratio Stream Compression Boundary (>= 50 MB).
    
    Covers Tasks 76 & 80.
    """
    original_size = large_volumetric_cube_file.stat().st_size
    assert original_size >= DEFAULT_50MB_THRESHOLD

    archive_path = configured_bridge.compress_volumetric_artifact(
        large_volumetric_cube_file
    )

    # 1. Assert return value is a valid pathlib.Path pointing to the .tar.zst archive
    assert archive_path is not None
    assert isinstance(archive_path, pathlib.Path)
    assert archive_path.name == "esp_grid_large.cube.tar.zst"

    # 2. Assert the .tar.zst archive exists on physical disk
    assert archive_path.exists()
    assert archive_path.is_file()

    # 3. Assert original uncompressed file is unlinked (disk bloat truncated)
    assert not large_volumetric_cube_file.exists()

    # 4. Quantitatively assert space savings
    compressed_size = os.path.getsize(archive_path)
    assert compressed_size > 0
    assert compressed_size < original_size

    savings_pct = (1.0 - (compressed_size / original_size)) * 100.0
    assert savings_pct > MIN_COMPRESSION_SAVINGS_PCT


def test_sub_threshold_passthrough(
    configured_bridge: VisualAssetBridge, small_volumetric_cube_file: pathlib.Path
) -> None:
    """Test Case 4: Sub-Threshold Passthrough Test (< 50 MB) (Task 76)."""
    original_size = small_volumetric_cube_file.stat().st_size
    assert original_size < DEFAULT_50MB_THRESHOLD

    result = configured_bridge.compress_volumetric_artifact(
        small_volumetric_cube_file
    )

    # 1. Asserts return value is None
    assert result is None

    # 2. Asserts original file remains completely intact and unmodified
    assert small_volumetric_cube_file.exists()
    assert small_volumetric_cube_file.stat().st_size == original_size

    # 3. Asserts no archive was created
    expected_archive = small_volumetric_cube_file.with_name(
        f"{small_volumetric_cube_file.name}.tar.zst"
    )
    assert not expected_archive.exists()


def test_html_3d_carousel_compression_and_batch_processing(
    configured_bridge: VisualAssetBridge,
    large_volumetric_html_file: pathlib.Path,
    small_volumetric_cube_file: pathlib.Path,
) -> None:
    """Test Case 5: HTML 3D Carousel Compression & Batch Processing (Tasks 75 & 76)."""
    orig_html_size = large_volumetric_html_file.stat().st_size
    assert orig_html_size >= DEFAULT_50MB_THRESHOLD

    orig_small_size = small_volumetric_cube_file.stat().st_size
    assert orig_small_size < DEFAULT_50MB_THRESHOLD

    # Execute batch processing over artifacts directory
    metrics = configured_bridge.process_all_volumetric_artifacts()

    # Only bloated files (>= 50 MB) should be processed and returned
    assert len(metrics) == EXPECTED_COMPRESSED_COUNT_SINGLE
    archive_path, orig_size, comp_size = metrics[0]

    assert archive_path.name == "molstar_interactive_large.html.tar.zst"
    assert archive_path.exists()
    assert not large_volumetric_html_file.exists()
    assert orig_size == orig_html_size
    assert comp_size < orig_size
    assert comp_size > 0

    # Sub-threshold file remains untouched
    assert small_volumetric_cube_file.exists()
    assert small_volumetric_cube_file.stat().st_size == orig_small_size


def test_user_guide_markdown_logging(
    configured_bridge: VisualAssetBridge, tmp_path: pathlib.Path
) -> None:
    """Test Case 6: User Guide Markdown Logging (Task 76)."""
    orig_cube = tmp_path / "artifacts" / "esp_grid_large.cube"
    comp_cube = tmp_path / "artifacts" / "esp_grid_large.cube.tar.zst"

    configured_bridge.log_compressed_artifact(
        compressed_path=comp_cube,
        original_path=orig_cube,
        original_size=SYNTHETIC_ORIG_SIZE_60MB,
        compressed_size=SYNTHETIC_COMP_SIZE_4MB,
    )

    guide_path = configured_bridge.user_guide_path
    assert guide_path.exists()

    content = guide_path.read_text(encoding="utf-8")
    assert content.startswith("# CoChem Volumetric Visual Assets Archive")
    assert (
        "| Original File | Compressed Archive | Original Size (MB) | "
        "Compressed Size (MB) | Space Savings (%) |" in content
    )
    assert "esp_grid_large.cube" in content
    assert comp_cube.as_posix() in content
    assert "60.00 MB" in content
    assert "4.00 MB" in content
    assert "93.33%" in content

    # Subsequent log call appends row without duplicate header
    orig_html = tmp_path / "artifacts" / "molstar.html"
    comp_html = tmp_path / "artifacts" / "molstar.html.tar.zst"

    configured_bridge.log_compressed_artifact(
        compressed_path=str(comp_html),
        original_path=str(orig_html),
        original_size=SYNTHETIC_ORIG_SIZE_50MB,
        compressed_size=SYNTHETIC_COMP_SIZE_5MB,
    )

    content2 = guide_path.read_text(encoding="utf-8")
    assert content2.count("# CoChem Volumetric Visual Assets Archive") == 1
    assert "molstar.html" in content2
    assert "50.00 MB" in content2
    assert "5.00 MB" in content2
    assert "90.00%" in content2


def test_spectral_image_discovery_and_filtering(
    configured_bridge: VisualAssetBridge,
    spectral_figure_assets: dict[str, pathlib.Path],
) -> None:
    """Test Case 7: 2D Spectral Image Discovery & Filtering (Task 77)."""
    discovered = configured_bridge.scan_spectral_artifacts()

    assert len(discovered) == EXPECTED_SPECTRAL_FIGURES_COUNT
    assert spectral_figure_assets["ir"] in discovered
    assert spectral_figure_assets["raman"] in discovered
    assert spectral_figure_assets["uv_vis"] in discovered

    # Filter assertions
    assert spectral_figure_assets["thumb"] not in discovered
    assert spectral_figure_assets["hidden"] not in discovered
    assert spectral_figure_assets["non_img"] not in discovered

    # Sorted order assertion
    assert discovered == sorted(discovered)


def test_cross_platform_latex_relative_path_posix_normalization(
    configured_bridge: VisualAssetBridge,
    spectral_figure_assets: dict[str, pathlib.Path],
    tmp_path: pathlib.Path,
) -> None:
    """Test Case 8: LaTeX Relative Path Calculation & POSIX Normalization.
    
    Covers Task 78.
    """
    ir_path = spectral_figure_assets["ir"]

    # 1. Relative path to report_archive_dir (default base)
    rel_default = configured_bridge.calculate_relative_image_path(ir_path)
    assert "\\" not in rel_default, (
        f"Path contains Windows backslashes: {rel_default}"
    )
    assert "/" in rel_default
    assert rel_default == "../artifacts/figures/ir_spectrum.png"

    # 2. Relative path to artifacts_dir
    rel_artifacts = configured_bridge.calculate_relative_image_path(
        ir_path, base_dir=tmp_path / "artifacts"
    )
    assert "\\" not in rel_artifacts, (
        f"Path contains Windows backslashes: {rel_artifacts}"
    )
    assert rel_artifacts == "figures/ir_spectrum.png"

    # 3. String input compatibility
    rel_str = configured_bridge.calculate_relative_image_path(
        str(ir_path), base_dir=str(tmp_path / "artifacts")
    )
    assert "\\" not in rel_str
    assert rel_str == "figures/ir_spectrum.png"

    # 4. Already relative path string passthrough
    rel_already = configured_bridge.calculate_relative_image_path(
        "figures/custom_spectrum.png"
    )
    assert "\\" not in rel_already
    assert rel_already == "figures/custom_spectrum.png"


def test_academic_latex_figure_snippet_generation(
    configured_bridge: VisualAssetBridge,
    spectral_figure_assets: dict[str, pathlib.Path],
    tmp_path: pathlib.Path,
) -> None:
    """Test Case 9: Academic LaTeX Figure Snippet Generation (Task 78)."""
    ir_path = spectral_figure_assets["ir"]
    artifacts_dir = tmp_path / "artifacts"

    # Explicit caption and label
    snippet_custom = configured_bridge.generate_latex_image_snippet(
        image_path=ir_path,
        caption="Experimental IR Spectrum",
        label="fig:ir_spectrum",
        width=r"\textwidth",
        base_dir=artifacts_dir,
    )

    assert r"\begin{figure}[htbp]" in snippet_custom
    assert r"\centering" in snippet_custom
    assert (
        r"\includegraphics[width=\textwidth]{figures/ir_spectrum.png}"
        in snippet_custom
    )
    assert r"\caption{Experimental IR Spectrum}" in snippet_custom
    assert r"\label{fig:ir_spectrum}" in snippet_custom
    assert r"\end{figure}" in snippet_custom

    # Custom width argument
    snippet_width = configured_bridge.generate_latex_image_snippet(
        image_path=spectral_figure_assets["raman"],
        caption="Raman Spectrum",
        label="fig:raman_spectrum",
        width=r"0.8\textwidth",
        base_dir=artifacts_dir,
    )
    assert (
        r"\includegraphics[width=0.8\textwidth]{figures/raman_spectrum.svg}"
        in snippet_width
    )

    # Clean default fallback caption and label from sanitized stem
    snippet_default = configured_bridge.generate_latex_image_snippet(
        image_path=spectral_figure_assets["uv_vis"],
        base_dir=artifacts_dir,
    )
    assert r"\caption{Uv Vis Spectrum}" in snippet_default
    assert r"\label{fig:uv_vis_spectrum}" in snippet_default
    assert (
        r"\includegraphics[width=\textwidth]{figures/uv_vis_spectrum.pdf}"
        in snippet_default
    )


def test_jinja2_context_injection_and_visual_payload_assembly(
    configured_bridge: VisualAssetBridge,
    spectral_figure_assets: dict[str, pathlib.Path],
    large_volumetric_cube_file: pathlib.Path,
    tmp_path: pathlib.Path,
) -> None:
    """Test Case 10: Jinja2 Context Injection & Visual Payload Assembly (Task 78)."""
    artifacts_dir = tmp_path / "artifacts"

    # 1. Test inject_visuals_into_context non-destructive mutation
    initial_context: dict[str, Any] = {
        "title": "Quantum Mechanical Study",
        "method": "B3LYP-D3(BJ)/def2-TZVP",
        "user_id": "cochem_researcher",
    }

    enriched = configured_bridge.inject_visuals_into_context(
        jinja_context=initial_context, search_dir=artifacts_dir
    )

    # Existing keys preserved
    assert enriched["title"] == "Quantum Mechanical Study"
    assert enriched["method"] == "B3LYP-D3(BJ)/def2-TZVP"
    assert enriched["user_id"] == "cochem_researcher"

    # Injected visual assets
    assert "spectral_figures" in enriched
    assert len(enriched["spectral_figures"]) == EXPECTED_SPECTRAL_FIGURES_COUNT
    assert "spectral_figure_snippets" in enriched
    assert "figures/ir_spectrum.png" in enriched["spectral_figure_snippets"]
    assert "figures/raman_spectrum.svg" in enriched["spectral_figure_snippets"]

    assert "figure_ir_snippet" in enriched
    assert r"\begin{figure}" in enriched["figure_ir_snippet"]
    assert "figures/ir_spectrum.png" in enriched["figure_ir_snippet"]

    assert "figure_raman_snippet" in enriched
    assert r"\begin{figure}" in enriched["figure_raman_snippet"]
    assert "figures/raman_spectrum.svg" in enriched["figure_raman_snippet"]

    assert "compressed_3d_assets" in enriched
    assert len(enriched["compressed_3d_assets"]) == EXPECTED_COMPRESSED_COUNT_SINGLE
    assert (
        enriched["compressed_3d_assets"][0]["original_name"]
        == "esp_grid_large.cube"
    )
    assert (
        enriched["compressed_3d_assets"][0]["savings_pct"]
        > MIN_COMPRESSION_SAVINGS_PCT
    )

    # 2. Test build_visual_payload directly on a separate sub-directory
    # with fresh assets
    sub_artifacts = tmp_path / "sub_artifacts"
    sub_figs = sub_artifacts / "figures"
    sub_figs.mkdir(parents=True, exist_ok=True)
    (sub_figs / "ir_spectrum.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 100
    )
    sub_cube = sub_artifacts / "homo_density.cube"
    chunk = (
        b"DENSITY_CHUNK_64KB_" + b"0123456789ABCDEF" * 4100
    )[:CHUNK_SIZE_BYTES]
    with open(sub_cube, "wb") as f_out:
        for _ in range(SYNTHETIC_CHUNK_64KB_COUNT_51MB):
            f_out.write(chunk)

    payload = configured_bridge.build_visual_payload(search_dir=sub_artifacts)
    assert "spectral_figures" in payload
    assert "spectral_figure_snippets" in payload
    assert "compressed_3d_assets" in payload
    assert len(payload["spectral_figures"]) == 1
    assert len(payload["compressed_3d_assets"]) == 1
    assert (
        payload["compressed_3d_assets"][0]["original_name"]
        == "homo_density.cube"
    )
    assert (
        payload["compressed_3d_assets"][0]["savings_pct"]
        > MIN_COMPRESSION_SAVINGS_PCT
    )


# ==============================================================================
# Additional Zero-Mock Protocol & Edge Case Verification
# ==============================================================================


def test_already_compressed_file_passthrough(
    configured_bridge: VisualAssetBridge, tmp_path: pathlib.Path
) -> None:
    """Guard test: Archives ending in compression suffixes are not double-compressed."""
    already_comp = tmp_path / "artifacts" / "density.cube.tar.zst"
    already_comp.write_bytes(b"EXISTING_COMPRESSED_DATA" * 1000)

    result = configured_bridge.compress_volumetric_artifact(already_comp)
    assert result is None
    assert already_comp.exists()
    assert not (tmp_path / "artifacts" / "density.cube.tar.zst.tar.zst").exists()


def test_empty_and_nonexistent_directories_safe_handling(
    tmp_path: pathlib.Path,
) -> None:
    """Safe graceful handling when directories do not exist or are empty."""
    missing_dir = tmp_path / "non_existent_artifacts"
    missing_report = tmp_path / "non_existent_reports"

    bridge = VisualAssetBridge(
        artifacts_dir=missing_dir,
        report_archive_dir=missing_report,
    )

    assert bridge.scan_volumetric_artifacts() == []
    assert bridge.scan_spectral_artifacts() == []
    assert bridge.process_all_volumetric_artifacts() == []
    assert bridge.compress_volumetric_artifact(missing_dir / "fake.cube") is None


def test_cli_preflight_verification() -> None:
    """CLI pre-flight execution test executing scribe_viz_bridge as __main__."""
    bridge_script = pathlib.Path(__file__).parent / "scribe_viz_bridge.py"
    assert bridge_script.exists(), f"Script not found at {bridge_script}"

    try:
        result = subprocess.run(
            [sys.executable, str(bridge_script)],
            capture_output=True,
            text=True,
            check=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            f"Pre-flight CLI timed out after {SUBPROCESS_TIMEOUT_SECONDS}s"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise AssertionError(
            f"Pre-flight failed with code {exc.returncode}:\n"
            f"STDOUT:\n{exc.stdout}\nSTDERR:\n{exc.stderr}"
        ) from exc

    assert result.returncode == 0
    assert "[SCRIBE VIZ BRIDGE PRE-FLIGHT VERIFIED]" in result.stdout
