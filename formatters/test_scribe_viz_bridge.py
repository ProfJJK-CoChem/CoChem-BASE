"""Zero-Mock Integration Test Suite for VisualAssetBridge (CoChem-SCRIBE Stage 6.3).

Strictly adheres to:
- SRS Phase 4 Task 10 (Tasks 75-78, 80)
- Zero-Mock Anti-Spoofing Protocol: Real filesystem I/O, real zstandard byte streams,
  real tmp_path files, real >= 51 MB synthetic binary .cube and .html files.
- 6-Tier Environment Matrix (POSIX path assertions).
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

from formatters.scribe_viz_bridge import (
    DEFAULT_50MB_THRESHOLD,
    VisualAssetBridge,
)

# Test constants to eliminate magic values
MIN_COMPRESSION_SAVINGS_PCT: float = 80.0
SYNTHETIC_CUBE_CHUNK_COUNT: int = 1600
SYNTHETIC_HTML_CHUNK_COUNT: int = 1700
SUB_THRESHOLD_REPEAT: int = 70000
EXPECTED_DISCOVERED_SPECTRAL_COUNT: int = 2
EXPECTED_COMPRESSED_COUNT: int = 1
SYNTHETIC_ORIG_SIZE_60MB: int = 62914560
SYNTHETIC_COMP_SIZE_4MB: int = 4194304
SYNTHETIC_ORIG_SIZE_50MB: int = 52428800
SYNTHETIC_COMP_SIZE_5MB: int = 5242880
SUBPROCESS_TIMEOUT_SECONDS: int = 30


def test_zstandard_compression_boundary_50mb(tmp_path: pathlib.Path) -> None:
    """Task 80: Real binary .cube file >= 51 MB stream compression boundary test."""
    cube_file = tmp_path / "orbital_density.cube"

    # Generate structured synthetic binary data >= 51 MB (54,400,000 bytes)
    # Chunked write to keep test memory footprint minimal
    pattern_chunk = b"CUBE_DENSITY_GRID_DATA_CHUNK_12345" * 1000  # 34,000 bytes
    with open(cube_file, "wb") as f_out:
        for _ in range(SYNTHETIC_CUBE_CHUNK_COUNT):
            f_out.write(pattern_chunk)

    original_size = cube_file.stat().st_size
    assert original_size >= DEFAULT_50MB_THRESHOLD, (
        f"Generated file size {original_size} < 50 MB threshold"
    )

    bridge = VisualAssetBridge(
        artifacts_dir=tmp_path,
        report_archive_dir=tmp_path,
        user_guide_path=tmp_path / "Report_Archive" / "CoChem_User_Guide.md",
        compression_threshold_bytes=DEFAULT_50MB_THRESHOLD,
        compression_level=19,
    )

    archive_path = bridge.compress_volumetric_artifact(cube_file)

    assert archive_path is not None, "Compression returned None for >= 50 MB file"
    assert archive_path.exists(), f"Archive {archive_path} was not written to disk"
    assert archive_path.name == "orbital_density.cube.tar.zst"

    # Original file must be unlinked to truncate disk bloat
    assert not cube_file.exists(), (
        "Original .cube file was not deleted after compression"
    )

    compressed_size = archive_path.stat().st_size
    assert compressed_size > 0, "Compressed archive is empty"
    assert compressed_size < original_size, (
        "Compressed archive is not smaller than original"
    )

    savings_pct = (1.0 - (compressed_size / original_size)) * 100.0
    assert savings_pct > MIN_COMPRESSION_SAVINGS_PCT, (
        f"Expected >80% space savings on repetitive grid, got {savings_pct:.2f}%"
    )


def test_sub_threshold_passthrough(tmp_path: pathlib.Path) -> None:
    """Sub-threshold passthrough: 1 MB .cube file remains intact and uncompressed."""
    small_cube = tmp_path / "small_grid.cube"
    small_cube.write_bytes(b"CUBE_DATA_SMALL" * SUB_THRESHOLD_REPEAT)  # ~1.05 MB

    original_size = small_cube.stat().st_size
    assert original_size < DEFAULT_50MB_THRESHOLD

    bridge = VisualAssetBridge(
        artifacts_dir=tmp_path,
        report_archive_dir=tmp_path,
        compression_threshold_bytes=DEFAULT_50MB_THRESHOLD,
    )

    result = bridge.compress_volumetric_artifact(small_cube)

    assert result is None, "Sub-threshold file should return None"
    assert small_cube.exists(), "Sub-threshold file must remain untouched"
    assert not small_cube.with_name(f"{small_cube.name}.tar.zst").exists()


def test_already_compressed_file_passthrough(tmp_path: pathlib.Path) -> None:
    """Guard test: Files ending in .tar.zst or .zst are not double-compressed."""
    already_comp = tmp_path / "density.cube.tar.zst"
    already_comp.write_bytes(b"EXISTING_COMPRESSED_DATA" * 1000)

    bridge = VisualAssetBridge(
        artifacts_dir=tmp_path,
        report_archive_dir=tmp_path,
        compression_threshold_bytes=100,
    )

    result = bridge.compress_volumetric_artifact(already_comp)
    assert result is None, "Already-compressed archive should not be re-compressed"
    assert already_comp.exists()
    assert not (tmp_path / "density.cube.tar.zst.tar.zst").exists()


def test_html_3d_carousel_compression(tmp_path: pathlib.Path) -> None:
    """HTML 3D carousel compression: 51 MB .html file processed in batch."""
    html_file = tmp_path / "carousel_3d.html"

    # Write ~55.25 MB synthetic html data
    pattern = (
        b"<div><canvas data-grid='VOLUMETRIC_3D_NGL_STREAM'></canvas></div>\n" * 500
    )  # 32,500 bytes
    with open(html_file, "wb") as f_out:
        for _ in range(SYNTHETIC_HTML_CHUNK_COUNT):
            f_out.write(pattern)

    assert html_file.stat().st_size >= DEFAULT_50MB_THRESHOLD

    bridge = VisualAssetBridge(
        artifacts_dir=tmp_path,
        report_archive_dir=tmp_path,
        compression_threshold_bytes=DEFAULT_50MB_THRESHOLD,
    )

    metrics = bridge.process_all_volumetric_artifacts(search_dir=tmp_path)

    assert len(metrics) == EXPECTED_COMPRESSED_COUNT
    archive_path, orig_size, comp_size = metrics[0]

    assert archive_path.name == "carousel_3d.html.tar.zst"
    assert archive_path.exists()
    assert not html_file.exists(), "Original .html file was not unlinked"
    assert comp_size < orig_size
    assert comp_size > 0


def test_spectral_image_discovery_and_relative_path(
    tmp_path: pathlib.Path,
) -> None:
    """2D spectral discovery, filtering, and cross-platform relative path."""
    figures_dir = tmp_path / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    ir_img = figures_dir / "ir_spectrum.png"
    raman_img = figures_dir / "raman_spectrum.svg"
    hidden_img = figures_dir / ".hidden_spectrum.png"
    thumb_img = figures_dir / "ir_spectrum_thumb.png"
    non_img = figures_dir / "data.csv"

    ir_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    raman_img.write_text(
        "<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8"
    )
    hidden_img.write_bytes(b"hidden")
    thumb_img.write_bytes(b"thumb")
    non_img.write_text("wavenumber,intensity", encoding="utf-8")

    bridge = VisualAssetBridge(
        artifacts_dir=tmp_path,
        report_archive_dir=tmp_path,
    )

    discovered = bridge.scan_spectral_artifacts(search_dir=tmp_path)

    assert len(discovered) == EXPECTED_DISCOVERED_SPECTRAL_COUNT
    assert ir_img in discovered
    assert raman_img in discovered
    assert hidden_img not in discovered
    assert thumb_img not in discovered
    assert non_img not in discovered

    # Verify POSIX forward slash normalization
    rel_ir = bridge.calculate_relative_image_path(ir_img, base_dir=tmp_path)
    rel_raman = bridge.calculate_relative_image_path(raman_img, base_dir=tmp_path)

    assert "\\" not in rel_ir, "Relative path contains Windows backslashes"
    assert "\\" not in rel_raman, "Relative path contains Windows backslashes"
    assert rel_ir == "figures/ir_spectrum.png"
    assert rel_raman == "figures/raman_spectrum.svg"


def test_latex_figure_snippet_generation(tmp_path: pathlib.Path) -> None:
    """LaTeX figure environment generation with verified formatting and POSIX paths."""
    figures_dir = tmp_path / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    ir_img = figures_dir / "ir_spectrum.png"
    ir_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    bridge = VisualAssetBridge(
        artifacts_dir=tmp_path,
        report_archive_dir=tmp_path,
    )

    snippet = bridge.generate_latex_image_snippet(
        image_path=ir_img,
        caption="Calculated IR Vibrational Spectrum",
        label="fig:ir_spectrum",
        width=r"\textwidth",
        base_dir=tmp_path,
    )

    assert r"\begin{figure}" in snippet
    assert r"\centering" in snippet
    assert r"\includegraphics[width=\textwidth]{figures/ir_spectrum.png}" in snippet
    assert r"\caption{Calculated IR Vibrational Spectrum}" in snippet
    assert r"\label{fig:ir_spectrum}" in snippet
    assert r"\end{figure}" in snippet


def test_default_latex_snippet_caption_and_label(tmp_path: pathlib.Path) -> None:
    """Default fallback generation for caption and label when omitted."""
    figures_dir = tmp_path / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    uv_img = figures_dir / "uv_vis_spectrum.png"
    uv_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    bridge = VisualAssetBridge(
        artifacts_dir=tmp_path,
        report_archive_dir=tmp_path,
    )

    snippet = bridge.generate_latex_image_snippet(image_path=uv_img, base_dir=tmp_path)

    assert r"\caption{Uv Vis Spectrum}" in snippet
    assert r"\label{fig:uv_vis_spectrum}" in snippet
    assert r"\includegraphics[width=\textwidth]{figures/uv_vis_spectrum.png}" in snippet


def test_user_guide_markdown_logging(tmp_path: pathlib.Path) -> None:
    """Markdown logging of compressed volumetric assets to CoChem_User_Guide.md."""
    guide_file = tmp_path / "Report_Archive" / "CoChem_User_Guide.md"

    bridge = VisualAssetBridge(
        artifacts_dir=tmp_path,
        report_archive_dir=tmp_path / "Report_Archive",
        user_guide_path=guide_file,
    )

    orig_cube = tmp_path / "electron_density.cube"
    comp_cube = tmp_path / "electron_density.cube.tar.zst"

    # 60 MB original, 4 MB compressed (testing with str path compatibility)
    bridge.log_compressed_artifact(
        compressed_path=str(comp_cube),
        original_path=str(orig_cube),
        original_size=SYNTHETIC_ORIG_SIZE_60MB,
        compressed_size=SYNTHETIC_COMP_SIZE_4MB,
    )

    assert guide_file.exists()
    content = guide_file.read_text(encoding="utf-8")

    assert "# CoChem Volumetric Visual Assets Archive" in content
    assert (
        "| Original File | Compressed Archive | Original Size (MB) | "
        "Compressed Size (MB) | Space Savings (%) |" in content
    )
    assert "electron_density.cube" in content
    assert "60.00 MB" in content
    assert "4.00 MB" in content
    assert "93.33%" in content

    # Append second asset and assert table header is not duplicated
    orig_html = tmp_path / "carousel.html"
    comp_html = tmp_path / "carousel.html.tar.zst"
    bridge.log_compressed_artifact(
        compressed_path=comp_html,
        original_path=orig_html,
        original_size=SYNTHETIC_ORIG_SIZE_50MB,
        compressed_size=SYNTHETIC_COMP_SIZE_5MB,
    )

    content2 = guide_file.read_text(encoding="utf-8")
    assert content2.count("# CoChem Volumetric Visual Assets Archive") == 1
    assert "carousel.html" in content2
    assert "50.00 MB" in content2
    assert "5.00 MB" in content2
    assert "90.00%" in content2


def test_jinja2_context_injection_integration(tmp_path: pathlib.Path) -> None:
    """Full pipeline: scanning, compression, snippet, and Jinja2 context injection."""
    figures_dir = tmp_path / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    (figures_dir / "ir_spectrum.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    )
    (figures_dir / "raman_spectrum.svg").write_text("<svg></svg>", encoding="utf-8")

    cube_file = tmp_path / "nci_density.cube"
    pattern = b"NCI_GRID_BINARY_STREAM_BYTE_CHUNK_999" * 1000  # 37,000 bytes
    with open(cube_file, "wb") as f_out:
        for _ in range(1500):  # 55,500,000 bytes (~52.93 MB)
            f_out.write(pattern)

    bridge = VisualAssetBridge(
        artifacts_dir=tmp_path,
        report_archive_dir=tmp_path,
        compression_threshold_bytes=DEFAULT_50MB_THRESHOLD,
    )

    base_context = {
        "title": "DFT Exploration of Porphyrin Metal Complexes",
        "computational_details": "B3LYP-D3(BJ)/def2-TZVP",
    }

    enriched = bridge.inject_visuals_into_context(base_context, search_dir=tmp_path)

    # Assert base keys preserved
    assert enriched["title"] == "DFT Exploration of Porphyrin Metal Complexes"
    assert enriched["computational_details"] == "B3LYP-D3(BJ)/def2-TZVP"

    # Assert visual keys injected
    assert "spectral_figures" in enriched
    assert len(enriched["spectral_figures"]) == EXPECTED_DISCOVERED_SPECTRAL_COUNT

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
    assert len(enriched["compressed_3d_assets"]) == EXPECTED_COMPRESSED_COUNT
    assert enriched["compressed_3d_assets"][0]["original_name"] == "nci_density.cube"
    assert (
        enriched["compressed_3d_assets"][0]["savings_pct"] > MIN_COMPRESSION_SAVINGS_PCT
    )


def test_empty_and_nonexistent_directories_safe_handling(
    tmp_path: pathlib.Path,
) -> None:
    """Safe graceful handling when directories do not exist or are empty."""
    non_existent = tmp_path / "missing_dir"

    bridge = VisualAssetBridge(
        artifacts_dir=non_existent,
        report_archive_dir=non_existent,
    )

    assert bridge.scan_volumetric_artifacts() == []
    assert bridge.scan_spectral_artifacts() == []
    assert bridge.process_all_volumetric_artifacts() == []
    assert bridge.compress_volumetric_artifact(non_existent / "fake.cube") is None


def test_environment_variable_dynamic_lookups(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tests dynamic path configuration via environment variables."""
    custom_art = tmp_path / "custom_artifacts"
    custom_rep = tmp_path / "custom_reports"
    custom_guide = tmp_path / "custom_guide.md"

    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(custom_art))
    monkeypatch.setenv("COCHEM_REPORT_ARCHIVE_DIR", str(custom_rep))
    monkeypatch.setenv("COCHEM_USER_GUIDE_PATH", str(custom_guide))

    bridge = VisualAssetBridge()

    assert bridge.artifacts_dir == custom_art
    assert bridge.report_archive_dir == custom_rep
    assert bridge.user_guide_path == custom_guide


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
