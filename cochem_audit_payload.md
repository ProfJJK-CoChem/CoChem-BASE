Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\prompt_scribe_viz_bridge.md.
Original prompt:
# Phase 4, Task 10: Visual Asset Compression & LaTeX Image Linking (`formatters/scribe_viz_bridge.py`)

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`  
**Target Files to Create:**
- `formatters/scribe_viz_bridge.py`
- `formatters/test_scribe_viz_bridge.py`

## Objective
Implement the production-grade visual asset management and LaTeX linking module (`VisualAssetBridge`) along with comprehensive zero-mock integration tests (`test_scribe_viz_bridge.py`) for CoChem-SCRIBE (Stage 6.3). This module manages volumetric 3D data bloat (e.g., NCI `.cube` domains, standalone interactive HTML carousels) by executing stream-based Zstandard maximum-ratio compression and payload truncation for files exceeding 50 MB, logs compressed archives transparently to `CoChem_User_Guide.md`, resolves high-resolution 2D spectra (`.svg`, `.png`, `.pdf`) from downstream analytical tools (e.g., CoChem-SpycFit, CoChem-TORQ), normalizes cross-platform relative paths with POSIX forward-slash conventions, and synthesizes publication-compliant LaTeX `\includegraphics` figure snippets for direct Jinja2 context injection into `scribe_templater.py`. The implementation must strictly adhere to the **CoChem-SCRIBE Software Requirements Specification (SRS Phase 4, Task 10, Tasks 75–78, 80)**, **Method Matrix v4**, the **Zero-Mock Anti-Spoofing Protocol**, **FAIR Data Principles**, and the **6-Tier Environment Matrix** (Local-Windows WSL, Local-MacOS OrbStack, Local-Linux Debian, Codespaces, GitHub Actions, HPC).

---

## Technical Specifications & Architecture

### 1. Architectural Philosophy: Payload Economy & Cross-Platform Portability
- **Volumetric Payload Truncation & HPC Network Economy (SRS §10.1, §10.3.1):** Quantum chemistry visualization data (volumetric electron densities, NCI grid `.cube` files, and monolithic interactive 3D HTML canvases) frequently exceed 50 MB to several gigabytes. Leaving uncompressed volumetric grids inside calculation directories causes severe payload bloat, exhausting disk quotas and throttling network transfers when synchronizing artifacts from HPC clusters to local workstations. Files exceeding **50 MB** (`52,428,800` bytes) must be algorithmically identified, compressed into high-ratio `.tar.zst` or `.zst` archives using `zstandard`, and the original uncompressed files safely removed.
- **LaTeX Relative Path Portability & Path Normalization (SRS §10.3.2):** LaTeX compilers (`pdflatex`, `xelatex`, `lualatex`) fatally reject absolute Windows backslash paths (e.g., `C:\Users\...`) inside `\includegraphics{...}`. All graphical asset references must be programmatically transformed into relative paths resolved against the `Report_Archive/` directory and formatted exclusively with POSIX forward slashes (`/`), guaranteeing flawless compilation across Windows WSL, macOS OrbStack, Linux Debian, GitHub Actions, and HPC.
- **Memory-Safe Streaming Compression:** Massive files must be compressed using buffered stream readers/writers (e.g., 64 KB chunks) to prevent high-memory spikes (OOM) during compression on RAM-constrained nodes.
- **100% Offline Air-Gap Execution:** All file scanning, Zstandard compression, path normalization, markdown logging, and LaTeX figure snippet generation must execute locally and deterministically without external network calls or cloud dependencies. Dynamic path resolution must use `pathlib.Path.home()`.

---

## Deliverable 1: `formatters/scribe_viz_bridge.py`

### 1. Class Architecture & Interface Contract (`VisualAssetBridge`)

Define the `VisualAssetBridge` class in `formatters/scribe_viz_bridge.py` with complete Python 3.10+ typing (`typing.Dict`, `typing.Any`, `typing.Optional`, `typing.Union`, `typing.List`, `typing.Tuple`, `pathlib.Path`):

```python
import os
import tarfile
import pathlib
import logging
from typing import Dict, Any, Optional, Union, List, Tuple
import zstandard as zstd

class VisualAssetBridge:
    """Visual Asset, Compression, and LaTeX Linking Manager.
    
    Scans CoChem artifact directories, compresses massive volumetric 3D files (.cube, .html)
    exceeding 50 MB via Zstandard to eliminate payload bloat, logs compressed archives
    into CoChem_User_Guide.md, discovers 2D spectral plots (.svg, .png, .pdf), and generates
    portable, relative-path LaTeX \\includegraphics figure snippets for Jinja2 template injection.
    """
    def __init__(
        self,
        artifacts_dir: Optional[Union[str, pathlib.Path]] = None,
        report_archive_dir: Optional[Union[str, pathlib.Path]] = None,
        user_guide_path: Optional[Union[str, pathlib.Path]] = None,
        compression_threshold_bytes: int = 52428800,  # Strict 50 MB threshold
        compression_level: int = 19                   # High-ratio Zstandard compression
    ) -> None:
        """Initializes the VisualAssetBridge with dynamic path resolution and configurable compression parameters."""
        pass

    def scan_volumetric_artifacts(
        self,
        search_dir: Optional[Union[str, pathlib.Path]] = None
    ) -> List[pathlib.Path]:
        """Recursively scans the directory for volumetric 3D artifacts (.cube, .html)."""
        pass

    def compress_volumetric_artifact(
        self,
        file_path: Union[str, pathlib.Path]
    ) -> Optional[pathlib.Path]:
        """Compresses a single volumetric file exceeding the size threshold into a .tar.zst archive and truncates original."""
        pass

    def process_all_volumetric_artifacts(
        self,
        search_dir: Optional[Union[str, pathlib.Path]] = None
    ) -> List[Tuple[pathlib.Path, int, int]]:
        """Processes and compresses all bloated volumetric files in the search directory, returning compression metrics."""
        pass

    def log_compressed_artifact(
        self,
        compressed_path: pathlib.Path,
        original_path: pathlib.Path,
        original_size: int,
        compressed_size: int
    ) -> None:
        """Appends structured Markdown entries to CoChem_User_Guide.md documenting compressed volumetric archives."""
        pass

    def scan_spectral_artifacts(
        self,
        search_dir: Optional[Union[str, pathlib.Path]] = None
    ) -> List[pathlib.Path]:
        """Recursively scans the directory for 2D publication spectral images (.svg, .png, .pdf)."""
        pass

    def calculate_relative_image_path(
        self,
        image_path: Union[str, pathlib.Path],
        base_dir: Optional[Union[str, pathlib.Path]] = None
    ) -> str:
        """Calculates POSIX-normalized relative path from base_dir to image_path for LaTeX inclusion."""
        pass

    def generate_latex_image_snippet(
        self,
        image_path: Union[str, pathlib.Path],
        caption: str = "",
        label: str = "",
        width: str = r"\textwidth"
    ) -> str:
        """Constructs an academic LaTeX figure environment snippet with \\includegraphics."""
        pass

    def build_visual_payload(
        self,
        search_dir: Optional[Union[str, pathlib.Path]] = None
    ) -> Dict[str, Any]:
        """Builds comprehensive dictionary payload containing relative image paths, figure snippets, and compression logs."""
        pass

    def inject_visuals_into_context(
        self,
        jinja_context: Dict[str, Any],
        search_dir: Optional[Union[str, pathlib.Path]] = None
    ) -> Dict[str, Any]:
        """Injects spectral figure snippets and asset mappings directly into the Jinja2 manuscript context dictionary."""
        pass
```

---

### 2. Detailed Functional Requirements (Tasks 75–78)

#### 2.1 Volumetric Artifact Discovery (Task 75)
- Recursively traverse `self.artifacts_dir` (defaulting dynamically to `pathlib.Path.home() / "CoChem_Artifacts"` if unconfigured) or a passed `search_dir`.
- Filter and target volumetric files with case-insensitive extensions: `.cube` (representing volumetric electron density grids, electrostatic potentials, or NCI domains) and `.html` (representing standalone 3D interactive carousels / Mol* / NGL viewer grids).
- Return a sorted, deduplicated `List[pathlib.Path]` of identified candidate paths.

#### 2.2 Zstandard Maximum-Ratio Stream Compression & Bloat Truncation (Task 76)
- For each discovered candidate file:
  - Query file size in bytes via `os.path.getsize(file_path)` (or `pathlib.Path.stat().st_size`).
  - If `file_size >= self.compression_threshold_bytes` (strict `50 MB` / `52428800` bytes):
    1. Construct archive path: `archive_path = file_path.with_name(f"{file_path.name}.tar.zst")` (or `.zst`).
    2. Stream-compress using `zstandard.ZstdCompressor(level=self.compression_level)` bundled in a `.tar` stream or direct frame compression:
       - Buffer in chunks (e.g., `65536` bytes / 64 KB) to ensure zero memory exhaustion even when compressing gigabyte-scale `.cube` files.
    3. Verify that the compressed file exists and has size $> 0$.
    4. Safely remove the original uncompressed file to eliminate disk bloat.
    5. Log the compression ratio: `ratio = (1.0 - (compressed_size / original_size)) * 100`.
    6. Return the newly created `archive_path`.
  - If `file_size < self.compression_threshold_bytes`:
    - Leave the file completely untouched and uncompressed. Return `None`.

#### 2.3 User Guide Markdown Logging (Task 76)
- Implement `log_compressed_artifact(self, compressed_path, original_path, original_size, compressed_size)`:
  - Target `self.user_guide_path` (defaulting dynamically to `pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive" / "CoChem_User_Guide.md"` or configurable `user_guide_path`).
  - If the target file does not exist, initialize it with a markdown header: `# CoChem Volumetric Visual Assets Archive`.
  - Append a structured Markdown table row or bullet entry detailing:
    - Original filename
    - Compressed archive path (as POSIX relative/normalized path)
    - Original file size (in MB, formatted to 2 decimal places)
    - Compressed file size (in MB, formatted to 2 decimal places)
    - Space savings percentage (`%`)
  - Ensure file writing uses UTF-8 encoding and creates parent directories dynamically.

#### 2.4 2D Spectral Asset Discovery (Task 77)
- Recursively search `self.artifacts_dir` / `figures` subdirectory for high-resolution 2D spectra generated by downstream modules (e.g., CoChem-SpycFit Voigt convolved IR/Raman plots, CoChem-TORQ conformational energy profiles).
- Target files with extensions `.svg`, `.png`, and `.pdf`.
- Exclude thumbnail or temporary cache files (e.g., files containing `_thumb` or starting with `.`).
- Return a sorted `List[pathlib.Path]` of high-resolution spectral figures.

#### 2.5 Cross-Platform LaTeX Image Linking & Forward-Slash Normalization (Task 78)
- Implement `calculate_relative_image_path(self, image_path, base_dir=None) -> str`:
  - Calculate relative path from `self.report_archive_dir` (default: `pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"`) to `image_path` using `os.path.relpath`.
  - **Mandatory Forward-Slash Normalization:** Replace all Windows backslashes `\` with POSIX forward slashes `/` (e.g., `figures/spectrum_ir.png`). LaTeX compilers will fail on backslashes in image paths.
- Implement `generate_latex_image_snippet(self, image_path, caption="", label="", width=r"\textwidth") -> str`:
  - Produce standard academic LaTeX figure environment:
    ```latex
    \begin{figure}[htbp]
    \centering
    \includegraphics[width=\textwidth]{<relative_path_with_forward_slashes>}
    \caption{<caption>}
    \label{<label>}
    \end{figure}
    ```
  - If caption/label are omitted, generate clean default captions derived from the sanitized image stem (e.g., `spectrum_ir` $\to$ `Spectrum Ir`).

#### 2.6 Jinja2 Context Injection & Payload Bridging (Task 78)
- Implement `build_visual_payload(self, search_dir=None) -> Dict[str, Any]`:
  - Execute volumetric compression sweep and aggregate compressed file logs.
  - Discover 2D spectral images and compile figure snippets.
  - Return a dictionary structured as:
    ```python
    {
        "spectral_figures": [
            {
                "stem": img.stem,
                "relative_path": rel_path,
                "latex_snippet": snippet,
                "format": img.suffix.lstrip(".").lower()
            }
            for img, rel_path, snippet in ...
        ],
        "spectral_figure_snippets": "\n\n".join(snippets),
        "compressed_3d_assets": [
            {
                "original_name": orig.name,
                "compressed_path": str(comp_path),
                "original_size_mb": orig_mb,
                "compressed_size_mb": comp_mb,
                "savings_pct": pct
            }
            for ...
        ]
    }
    ```
- Implement `inject_visuals_into_context(self, jinja_context: Dict[str, Any], search_dir=None) -> Dict[str, Any]`:
  - Mutate and return `jinja_context` enriched with `spectral_figures`, `spectral_figure_snippets`, `figure_ir_snippet`, `figure_raman_snippet`, and `compressed_3d_assets`.

#### 2.7 Local Pre-Flight CLI Validation (SRS §10.3)
- Include an `if __name__ == '__main__':` execution block at the bottom of `formatters/scribe_viz_bridge.py`.
- When invoked directly from CLI across any tier:
  1. Instantiate `VisualAssetBridge` with local temporary test paths.
  2. Verify volumetric scanning, relative path forward-slash normalization, and LaTeX snippet generation.
  3. Print `[SCRIBE VIZ BRIDGE PRE-FLIGHT VERIFIED]` upon successful verification.

---

## Deliverable 2: `formatters/test_scribe_viz_bridge.py`

Implement a complete `pytest` test suite conforming to the **Zero-Mock Anti-Spoofing Protocol**:

1. **Zero-Mock Enforcement (Task 80):**
   - Strictly prohibit `unittest.mock`, `mocker`, or simulated compression wrappers.
   - All tests must execute real filesystem operations, real `zstandard` byte compression streams, and real path math.

2. **Zstandard Compression Boundary Test (Task 80):**
   - Programmatically generate a physical binary `.cube` file with size $\ge 51\text{ MB}$ (`53,477,376` bytes) filled with repetitive/structured synthetic binary data inside `tmp_path`.
   - Record initial file size and path.
   - Execute `bridge.compress_volumetric_artifact()`.
   - Mathematically assert:
     - The `.tar.zst` (or `.zst`) archive exists on disk.
     - The original uncompressed `.cube` file no longer exists (confirming truncation).
     - The compressed file size is strictly less than the original size (`compressed_size < original_size`).
     - The compression ratio exceeds $80\%$ for synthetic repetitive grid data.

3. **Sub-Threshold Passthrough Test:**
   - Create a small $1\text{ MB}$ `.cube` file inside `tmp_path`.
   - Execute `bridge.compress_volumetric_artifact()`.
   - Assert that the returned path is `None`, the original file remains intact, and no `.zst` file is created.

4. **HTML 3D Carousel Compression Test:**
   - Create a $51\text{ MB}$ `.html` file inside `tmp_path`.
   - Execute `bridge.process_all_volumetric_artifacts()`.
   - Assert that the `.html` file is compressed into `.tar.zst` and the original `.html` is truncated.

5. **2D Spectral Image Discovery & Relative Path Formatting Test:**
   - Create synthetic `ir_spectrum.png` and `raman_spectrum.svg` files inside `tmp_path / "figures"`.
   - Execute `bridge.scan_spectral_artifacts()` and `bridge.calculate_relative_image_path()`.
   - Assert discovered list contains both image paths.
   - Assert generated relative paths contain **zero backslashes** (`\`) and use standard forward slashes (`/`), even when executed on native Windows.

6. **LaTeX Figure Snippet Generation Test:**
   - Generate LaTeX snippet for `ir_spectrum.png`.
   - Assert snippet contains `\begin{figure}`, `\centering`, `\includegraphics[width=\textwidth]{figures/ir_spectrum.png}`, `\caption{...}`, and `\end{figure}`.

7. **User Guide Markdown Logging Test:**
   - Execute `bridge.log_compressed_artifact()` to a test `CoChem_User_Guide.md`.
   - Read the file content and assert table rows containing the filename, size in MB, and compression percentage exist.

8. **Jinja2 Context Injection Integration Test:**
   - Create a base Jinja2 context dictionary: `{"title": "Test Paper", "computational_details": "DFT"}`.
   - Call `bridge.inject_visuals_into_context(jinja_context)`.
   - Assert returned dictionary contains non-empty `spectral_figures` and `spectral_figure_snippets` keys.

---

## Execution Constraints & Anti-Spoofing Directives

1. **Zero Mocking / Placeholders:**
   - Every class, method, helper, and test case must be completely implemented with functional, executable logic.
   - Strictly NO `pass`, `# TODO`, `...`, or placeholder mock returns in output files.
2. **Dynamic Path Resolution & Air-Gap Compliance:**
   - All filesystem paths must resolve dynamically using `pathlib.Path.home()` or explicit parameters.
   - Hardcoded OS paths (e.g., `C:\Users\...` or `/tmp/...`) are strictly forbidden.
   - All compression and formatting must execute 100% offline without external network sockets.
3. **6-Tier Environment Matrix Compliance:**
   - The module and tests must function identically across Linux (Debian/Ubuntu), macOS (OrbStack), Windows (WSL), Codespaces, GitHub Actions, and HPC clusters.
   - Path normalization must guarantee forward slashes in LaTeX code across all OS platforms.
4. **Memory & Resource Safety:**
   - Compression of large files must utilize chunked/streaming I/O (64 KB buffers) to avoid spiking node RAM.
5. **Deliverable Scope:**
   - Implement `formatters/scribe_viz_bridge.py` and `formatters/test_scribe_viz_bridge.py`.

---

## Task
Implement the Python modules and tests as described and save them to:
- `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\formatters\scribe_viz_bridge.py`
- `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\formatters\test_scribe_viz_bridge.py`
using the `write_to_file` tool.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\formatters\scribe_viz_bridge.py ---
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\formatters\test_scribe_viz_bridge.py ---
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

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.