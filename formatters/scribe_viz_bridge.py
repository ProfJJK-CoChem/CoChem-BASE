"""Visual Asset Compression & LaTeX Image Linking Bridge (CoChem-SCRIBE Stage 6.3).

This module manages volumetric 3D data bloat (.cube, .html) exceeding 50 MB via
stream-based Zstandard maximum-ratio compression, logs compressed archives into
CoChem_User_Guide.md, discovers 2D spectral plots (.svg, .png, .pdf), normalizes
cross-platform relative paths with POSIX forward-slash conventions, and synthesizes
publication-compliant LaTeX \\includegraphics figure snippets for direct Jinja2
context injection into scribe_templater.py.

Adheres strictly to:
- CoChem-SCRIBE SRS Phase 4, Task 10 (Tasks 75-78, 80)
- Method Matrix v4
- Zero-Mock Anti-Spoofing Protocol
- 6-Tier Environment Matrix
"""

from __future__ import annotations

import logging
import os
import pathlib
import tarfile
from typing import Any

import zstandard as zstd

CHUNK_SIZE_BYTES: int = 65536  # 64 KB streaming buffer
DEFAULT_50MB_THRESHOLD: int = 52428800  # Strict 50 MB threshold (50 * 1024 * 1024)
DEFAULT_COMPRESSION_LEVEL: int = 19  # High-ratio Zstandard compression


class VisualAssetBridge:
    """Visual Asset, Compression, and LaTeX Linking Manager.

    Scans CoChem artifact directories, compresses massive volumetric 3D files
    (.cube, .html) exceeding 50 MB via Zstandard to eliminate payload bloat,
    logs compressed archives into CoChem_User_Guide.md, discovers 2D spectral plots
    (.svg, .png, .pdf), and generates portable, relative-path LaTeX \\includegraphics
    figure snippets for Jinja2 template injection.
    """

    def __init__(
        self,
        artifacts_dir: str | pathlib.Path | None = None,
        report_archive_dir: str | pathlib.Path | None = None,
        user_guide_path: str | pathlib.Path | None = None,
        compression_threshold_bytes: int = DEFAULT_50MB_THRESHOLD,
        compression_level: int = DEFAULT_COMPRESSION_LEVEL,
    ) -> None:
        """Initializes the VisualAssetBridge with dynamic path and env resolution.

        Args:
            artifacts_dir: Base directory containing calculation artifacts.
            report_archive_dir: Directory where the final report is compiled.
            user_guide_path: Target Markdown file path for logging volumetric archives.
            compression_threshold_bytes: Size threshold in bytes above which files
                are compressed.
            compression_level: Zstandard compression level (1-22, default 19).
        """
        if artifacts_dir is not None:
            self.artifacts_dir: pathlib.Path = pathlib.Path(artifacts_dir)
        elif "COCHEM_ARTIFACTS_DIR" in os.environ:
            self.artifacts_dir = pathlib.Path(os.environ["COCHEM_ARTIFACTS_DIR"])
        else:
            self.artifacts_dir = pathlib.Path.home() / "CoChem_Artifacts"

        if report_archive_dir is not None:
            self.report_archive_dir: pathlib.Path = pathlib.Path(report_archive_dir)
        elif "COCHEM_REPORT_ARCHIVE_DIR" in os.environ:
            self.report_archive_dir = pathlib.Path(
                os.environ["COCHEM_REPORT_ARCHIVE_DIR"]
            )
        else:
            self.report_archive_dir = self.artifacts_dir / "Report_Archive"

        if user_guide_path is not None:
            self.user_guide_path: pathlib.Path = pathlib.Path(user_guide_path)
        elif "COCHEM_USER_GUIDE_PATH" in os.environ:
            self.user_guide_path = pathlib.Path(os.environ["COCHEM_USER_GUIDE_PATH"])
        else:
            self.user_guide_path = self.report_archive_dir / "CoChem_User_Guide.md"

        self.compression_threshold_bytes: int = compression_threshold_bytes
        self.compression_level: int = compression_level
        self.logger = logging.getLogger(self.__class__.__name__)

    def scan_volumetric_artifacts(
        self,
        search_dir: str | pathlib.Path | None = None,
    ) -> list[pathlib.Path]:
        """Recursively scans the directory for volumetric 3D artifacts (.cube, .html).

        Args:
            search_dir: Directory to scan. If None, uses self.artifacts_dir.

        Returns:
            Sorted list of identified candidate volumetric file paths.
        """
        target_dir = (
            pathlib.Path(search_dir) if search_dir is not None else self.artifacts_dir
        )
        if not target_dir.exists() or not target_dir.is_dir():
            return []

        volumetric_exts = {".cube", ".html"}
        found_files: list[pathlib.Path] = []

        for path in target_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in volumetric_exts:
                if not path.name.startswith(".") and not path.name.endswith(
                    (".tar.zst", ".zst")
                ):
                    found_files.append(path)

        return sorted(list(set(found_files)))

    def compress_volumetric_artifact(
        self,
        file_path: str | pathlib.Path,
    ) -> pathlib.Path | None:
        """Compresses a volumetric file exceeding the threshold into a .tar.zst archive.

        Uses 64 KB chunked buffer streaming with zstandard to eliminate RAM spikes.

        Args:
            file_path: Path to the uncompressed volumetric file.

        Returns:
            Path to the created .tar.zst archive if compressed, or None if below
            threshold.
        """
        target_path = pathlib.Path(file_path)
        if not target_path.exists() or not target_path.is_file():
            return None

        # Prevent double-compression on already compressed archives
        if target_path.name.endswith(
            (".tar.zst", ".zst", ".tar.gz", ".gz", ".tar.bz2", ".xz")
        ):
            return None

        original_size = target_path.stat().st_size
        if original_size < self.compression_threshold_bytes:
            return None

        archive_path = target_path.with_name(f"{target_path.name}.tar.zst")
        archive_path.parent.mkdir(parents=True, exist_ok=True)

        cctx = zstd.ZstdCompressor(level=self.compression_level)
        try:
            with open(archive_path, "wb") as f_out:
                with cctx.stream_writer(
                    f_out, write_size=CHUNK_SIZE_BYTES, closefd=False
                ) as compressor:
                    with tarfile.open(fileobj=compressor, mode="w|") as tar:
                        tar.add(target_path, arcname=target_path.name)
        except Exception:
            if archive_path.exists():
                archive_path.unlink(missing_ok=True)
            self.logger.error(
                "Failed to compress volumetric artifact %s", target_path, exc_info=True
            )
            raise

        compressed_size = archive_path.stat().st_size
        if compressed_size > 0:
            target_path.unlink()
            try:
                self.log_compressed_artifact(
                    compressed_path=archive_path,
                    original_path=target_path,
                    original_size=original_size,
                    compressed_size=compressed_size,
                )
            except Exception as e:
                self.logger.warning(
                    "Failed to log compressed artifact to User Guide: %s", e
                )
            return archive_path
        else:
            if archive_path.exists():
                archive_path.unlink(missing_ok=True)
            return None

    def process_all_volumetric_artifacts(
        self,
        search_dir: str | pathlib.Path | None = None,
    ) -> list[tuple[pathlib.Path, int, int]]:
        """Processes and compresses all bloated volumetric files in target directory.

        Args:
            search_dir: Directory to scan and compress. If None, uses
                self.artifacts_dir.

        Returns:
            List of tuples: (archive_path, original_size_bytes, compressed_size_bytes).
        """
        target_dir = (
            pathlib.Path(search_dir) if search_dir is not None else self.artifacts_dir
        )
        candidate_files = self.scan_volumetric_artifacts(search_dir=target_dir)

        results: list[tuple[pathlib.Path, int, int]] = []
        for file_path in candidate_files:
            if not file_path.exists():
                continue
            original_size = file_path.stat().st_size
            if original_size >= self.compression_threshold_bytes:
                archive_path = self.compress_volumetric_artifact(file_path)
                if archive_path is not None and archive_path.exists():
                    compressed_size = archive_path.stat().st_size
                    results.append((archive_path, original_size, compressed_size))

        return results

    def log_compressed_artifact(
        self,
        compressed_path: str | pathlib.Path,
        original_path: str | pathlib.Path,
        original_size: int,
        compressed_size: int,
    ) -> None:
        """Appends structured Markdown entries to CoChem_User_Guide.md.

        Args:
            compressed_path: Path to the compressed archive.
            original_path: Path to the original uncompressed file.
            original_size: Original file size in bytes.
            compressed_size: Compressed archive size in bytes.
        """
        target_md = self.user_guide_path
        target_md.parent.mkdir(parents=True, exist_ok=True)

        orig_p = pathlib.Path(original_path)
        comp_p = pathlib.Path(compressed_path)

        orig_mb = original_size / (1024 * 1024)
        comp_mb = compressed_size / (1024 * 1024)
        savings_pct = (
            ((1.0 - (compressed_size / original_size)) * 100.0)
            if original_size > 0
            else 0.0
        )

        comp_path_str = comp_p.as_posix()
        orig_name = orig_p.name

        table_header = (
            "# CoChem Volumetric Visual Assets Archive\n\n"
            "| Original File | Compressed Archive | Original Size (MB) | "
            "Compressed Size (MB) | Space Savings (%) |\n"
            "|---|---|---|---|---|\n"
        )
        table_row = (
            f"| {orig_name} | {comp_path_str} | {orig_mb:.2f} MB | "
            f"{comp_mb:.2f} MB | {savings_pct:.2f}% |\n"
        )

        if not target_md.exists():
            target_md.write_text(table_header + table_row, encoding="utf-8")
        else:
            existing_content = target_md.read_text(encoding="utf-8")
            if "# CoChem Volumetric Visual Assets Archive" not in existing_content:
                new_content = (
                    existing_content.rstrip() + "\n\n" + table_header + table_row
                )
                target_md.write_text(new_content, encoding="utf-8")
            else:
                new_content = existing_content.rstrip() + "\n" + table_row
                target_md.write_text(new_content, encoding="utf-8")

    def scan_spectral_artifacts(
        self,
        search_dir: str | pathlib.Path | None = None,
    ) -> list[pathlib.Path]:
        """Recursively scans the directory for 2D publication spectral images.

        Args:
            search_dir: Directory to scan. If None, checks figures subdir
                or self.artifacts_dir.

        Returns:
            Sorted list of high-resolution spectral image paths.
        """
        if search_dir is not None:
            target_dir = pathlib.Path(search_dir)
        else:
            fig_dir = self.artifacts_dir / "figures"
            target_dir = fig_dir if fig_dir.exists() else self.artifacts_dir

        if not target_dir.exists():
            return []

        spectral_exts = {".svg", ".png", ".pdf"}
        discovered: list[pathlib.Path] = []

        if target_dir.is_file():
            if target_dir.suffix.lower() in spectral_exts:
                return [target_dir]
            return []

        for p in target_dir.rglob("*"):
            if p.is_file() and p.suffix.lower() in spectral_exts:
                if not p.name.startswith(".") and "_thumb" not in p.name.lower():
                    discovered.append(p)

        return sorted(list(set(discovered)))

    def calculate_relative_image_path(
        self,
        image_path: str | pathlib.Path,
        base_dir: str | pathlib.Path | None = None,
    ) -> str:
        """Calculates POSIX-normalized relative path from base_dir to image_path.

        Guarantees standard forward slashes ('/') across all operating systems.

        Args:
            image_path: Path to the image file.
            base_dir: Base directory from which relative path is resolved
                (defaults to self.report_archive_dir).

        Returns:
            POSIX-normalized relative path string.
        """
        img_p = pathlib.Path(image_path)
        base_p = (
            pathlib.Path(base_dir).resolve()
            if base_dir is not None
            else self.report_archive_dir.resolve()
        )

        if img_p.is_absolute():
            try:
                rel = os.path.relpath(img_p.resolve(), base_p)
                return rel.replace("\\", "/")
            except ValueError:
                return img_p.as_posix()
        else:
            return str(img_p).replace("\\", "/")

    def generate_latex_image_snippet(
        self,
        image_path: str | pathlib.Path,
        caption: str = "",
        label: str = "",
        width: str = r"\textwidth",
        base_dir: str | pathlib.Path | None = None,
    ) -> str:
        """Constructs an academic LaTeX figure snippet with \\includegraphics.

        Args:
            image_path: Path to the image file.
            caption: LaTeX figure caption text. Defaults to sanitized image stem.
            label: LaTeX figure label. Defaults to fig:<stem>.
            width: LaTeX graphic width specification (e.g. \\textwidth, 0.8\\linewidth).
            base_dir: Base directory to resolve relative image path against.

        Returns:
            LaTeX figure environment code block string.
        """
        img_p = pathlib.Path(image_path)
        rel_path = self.calculate_relative_image_path(img_p, base_dir=base_dir)

        clean_caption = (
            caption
            if caption
            else img_p.stem.replace("_", " ").replace("-", " ").title()
        )
        clean_label = (
            label
            if label
            else f"fig:{img_p.stem.lower().replace(' ', '_').replace('-', '_')}"
        )

        snippet = (
            r"\begin{figure}[htbp]" + "\n"
            r"\centering" + "\n"
            rf"\includegraphics[width={width}]{{{rel_path}}}" + "\n"
            rf"\caption{{{clean_caption}}}" + "\n"
            rf"\label{{{clean_label}}}" + "\n"
            r"\end{figure}"
        )
        return snippet

    def build_visual_payload(
        self,
        search_dir: str | pathlib.Path | None = None,
    ) -> dict[str, Any]:
        """Builds comprehensive dictionary payload for Jinja2 template rendering.

        Args:
            search_dir: Directory containing visual assets. If None, uses
                self.artifacts_dir.

        Returns:
            Structured dictionary payload for Jinja2 template rendering.
        """
        target_dir = (
            pathlib.Path(search_dir) if search_dir is not None else self.artifacts_dir
        )
        base_dir = target_dir if search_dir is not None else self.report_archive_dir

        # Process and compress bloated volumetric artifacts
        compression_metrics = self.process_all_volumetric_artifacts(
            search_dir=target_dir
        )
        compressed_3d_assets: list[dict[str, Any]] = []
        for comp_path, orig_size, comp_size in compression_metrics:
            orig_mb = round(orig_size / (1024 * 1024), 2)
            comp_mb = round(comp_size / (1024 * 1024), 2)
            savings_pct = (
                round(((1.0 - (comp_size / orig_size)) * 100.0), 2)
                if orig_size > 0
                else 0.0
            )

            orig_name = comp_path.name.removesuffix(".tar.zst").removesuffix(".zst")
            compressed_3d_assets.append(
                {
                    "original_name": orig_name,
                    "compressed_path": comp_path.as_posix(),
                    "original_size_mb": orig_mb,
                    "compressed_size_mb": comp_mb,
                    "savings_pct": savings_pct,
                }
            )

        # Scan 2D spectral images
        spectral_files = self.scan_spectral_artifacts(search_dir=target_dir)
        spectral_figures: list[dict[str, Any]] = []
        snippets: list[str] = []

        for img in spectral_files:
            rel_path = self.calculate_relative_image_path(img, base_dir=base_dir)
            snippet = self.generate_latex_image_snippet(img, base_dir=base_dir)
            spectral_figures.append(
                {
                    "stem": img.stem,
                    "relative_path": rel_path,
                    "latex_snippet": snippet,
                    "format": img.suffix.lstrip(".").lower(),
                }
            )
            snippets.append(snippet)

        return {
            "spectral_figures": spectral_figures,
            "spectral_figure_snippets": "\n\n".join(snippets),
            "compressed_3d_assets": compressed_3d_assets,
        }

    def inject_visuals_into_context(
        self,
        jinja_context: dict[str, Any],
        search_dir: str | pathlib.Path | None = None,
    ) -> dict[str, Any]:
        """Injects spectral figure snippets and asset mappings into Jinja2 context.

        Args:
            jinja_context: Target Jinja2 context dictionary to enrich.
            search_dir: Directory containing visual assets.

        Returns:
            Enriched Jinja2 context dictionary.
        """
        payload = self.build_visual_payload(search_dir=search_dir)

        jinja_context["spectral_figures"] = payload["spectral_figures"]
        jinja_context["spectral_figure_snippets"] = payload["spectral_figure_snippets"]
        jinja_context["compressed_3d_assets"] = payload["compressed_3d_assets"]

        figure_ir_snippet = ""
        figure_raman_snippet = ""

        for fig in payload["spectral_figures"]:
            stem_lower = fig["stem"].lower()
            if "ir" in stem_lower and not figure_ir_snippet:
                figure_ir_snippet = fig["latex_snippet"]
            if "raman" in stem_lower and not figure_raman_snippet:
                figure_raman_snippet = fig["latex_snippet"]

        jinja_context["figure_ir_snippet"] = figure_ir_snippet
        jinja_context["figure_raman_snippet"] = figure_raman_snippet

        return jinja_context


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_p = pathlib.Path(tmp_dir)
        fig_p = tmp_p / "figures"
        fig_p.mkdir(parents=True, exist_ok=True)

        test_img = fig_p / "test_spectrum.png"
        test_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

        bridge = VisualAssetBridge(
            artifacts_dir=tmp_p,
            report_archive_dir=tmp_p,
            user_guide_path=tmp_p / "CoChem_User_Guide.md",
            compression_threshold_bytes=1000,
        )

        specs = bridge.scan_spectral_artifacts(search_dir=tmp_p)
        assert len(specs) == 1, "Spectral scan failed"

        rel_p = bridge.calculate_relative_image_path(test_img, base_dir=tmp_p)
        assert "\\" not in rel_p, "Path contains backslashes"
        assert rel_p == "figures/test_spectrum.png", f"Unexpected rel_path: {rel_p}"

        snippet = bridge.generate_latex_image_snippet(test_img, base_dir=tmp_p)
        assert r"\begin{figure}" in snippet
        assert "figures/test_spectrum.png" in snippet

        ctx = bridge.inject_visuals_into_context({}, search_dir=tmp_p)
        assert "spectral_figures" in ctx
        assert len(ctx["spectral_figures"]) == 1

        print("[SCRIBE VIZ BRIDGE PRE-FLIGHT VERIFIED]")
