Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\09_scribe_viz_bridge.md.
Original prompt:
# Phase 4, Task 10: Visual Asset Compression & LaTeX Image Linking (`formatters/scribe_viz_bridge.py`)

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`  
**Target Files to Create:**
- `formatters/scribe_viz_bridge.py`
- `formatters/test_scribe_viz_bridge.py`

## Objective
Implement the production-grade visual asset management and LaTeX linking module (`VisualAssetBridge`) along with comprehensive zero-mock integration tests (`test_scribe_viz_bridge.py`) for CoChem-SCRIBE (Stage 6.3). This module manages volumetric 3D data bloat (e.g., NCI `.cube` domains, standalone interactive HTML carousels) by executing stream-based Zstandard maximum-ratio compression and payload truncation for files exceeding 50 MB, logs compressed archives transparently to `CoChem_User_Guide.md`, resolves high-resolution 2D spectra (`.svg`, `.png`) from downstream analytical tools (e.g., CoChem-SpycFit, CoChem-TORQ), normalizes cross-platform relative paths with POSIX forward-slash conventions, and synthesizes publication-compliant LaTeX `\includegraphics` figure snippets for direct Jinja2 context injection into `scribe_templater.py`. The implementation must strictly adhere to the **CoChem-SCRIBE Software Requirements Specification (SRS Phase 4, Task 10, Tasks 75–78, 80)**, **Method Matrix v4**, the **Zero-Mock Anti-Spoofing Protocol**, **FAIR Data Principles**, and the **6-Tier Environment Matrix** (Local-Windows WSL, Local-MacOS OrbStack, Local-Linux Debian, Codespaces, GitHub Actions, HPC).

---

## Technical Specifications & Architecture

### 1. Architectural Philosophy: Payload Economy & Cross-Platform Portability
- **Volumetric Payload Truncation & HPC Network Economy (SRS §10.1, §10.3.1):** Quantum chemistry visualization data (volumetric electron densities, NCI grid `.cube` files, and monolithic interactive 3D HTML canvases) frequently exceed 50 MB to several gigabytes. Leaving uncompressed volumetric grids inside calculation directories causes severe payload bloat, exhausting disk quotas and throttling network transfers when synchronizing artifacts from HPC clusters to local workstations. Files exceeding **50 MB** (`52,428,800` bytes) must be algorithmically identified, compressed into high-ratio `.tar.zst` or `.zst` archives using `zstandard`, and the original uncompressed files safely deleted (`os.remove` / `Path.unlink`).
- **LaTeX Relative Path Portability & Path Normalization (SRS §10.3.2):** LaTeX compilers (`pdflatex`, `xelatex`, `lualatex`) fatally reject absolute Windows backslash paths (e.g., `C:\Users\...`) inside `\includegraphics{...}`. All graphical asset references must be programmatically transformed into relative paths resolved against the `Report_Archive/` directory and formatted exclusively with POSIX forward slashes (`/`), guaranteeing flawless compilation across Windows WSL, macOS OrbStack, Linux Debian, GitHub Actions, and HPC.
- **Memory-Safe Streaming Compression:** Massive files must be compressed using buffered stream readers/writers or chunked framing to prevent high-memory spikes (OOM) during compression on RAM-constrained nodes.
- **100% Offline Air-Gap Execution:** All file scanning, Zstandard compression, path normalization, markdown logging, and LaTeX figure snippet generation must execute locally and deterministically without external network calls or cloud dependencies.

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
    into CoChem_User_Guide.md, discovers 2D spectral plots (.svg, .png), and generates
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
        """Recursively scans the directory for 2D publication spectral images (.svg, .png)."""
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
    4. Execute safe file deletion on the original uncompressed file: `os.remove(file_path)` (or `file_path.unlink()`) to eliminate disk bloat.
    5. Log the compression ratio: `ratio = (1.0 - (compressed_size / original_size)) * 100`.
    6. Return the newly created `archive_path`.
  - If `file_size < self.compression_threshold_bytes`:
    - Leave the file completely untouched and uncompressed. Return `None`.

#### 2.3 User Guide Markdown Logging (Task 76)
- Implement `log_compressed_artifact(self, compressed_path, original_path, original_size, compressed_size)`:
  - Target `self.user_guide_path` (defaulting dynamically to `pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive" / "CoChem_User_Guide.md"` or repo-level `CoChem_User_Guide.md`).
  - If the target file does not exist, initialize it with a markdown header: `# CoChem Volumetric Visual Assets Archive`.
  - Append a structured Markdown table row or bullet entry detailing:
    - Original filename
    - Compressed archive path (as POSIX relative/absolute path)
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
   - Programmatically generate a physical binary `.cube` file with size $\ge 51\text{ MB}$ (`53,477,376` bytes) filled with repetitive/structured authentic binary data inside `tmp_path`.
   - Record initial file size and path.
   - Execute `bridge.compress_volumetric_artifact()`.
   - Mathematically assert:
     - The `.tar.zst` (or `.zst`) archive exists on disk.
     - The original uncompressed `.cube` file no longer exists (confirming truncation / deletion).
     - The compressed file size is strictly less than the original size (`compressed_size < original_size`).
     - The compression ratio exceeds $80\%$ for realistic repetitive grid data.

3. **Sub-Threshold Passthrough Test:**
   - Create a small $1\text{ MB}$ `.cube` file inside `tmp_path`.
   - Execute `bridge.compress_volumetric_artifact()`.
   - Assert that the returned path is `None`, the original file remains intact, and no `.zst` file is created.

4. **HTML 3D Carousel Compression Test:**
   - Create a $51\text{ MB}$ `.html` file inside `tmp_path`.
   - Execute `bridge.process_all_volumetric_artifacts()`.
   - Assert that the `.html` file is compressed into `.tar.zst` and the original `.html` is truncated.

5. **2D Spectral Image Discovery & Relative Path Formatting Test:**
   - Create authentic `ir_spectrum.png` and `raman_spectrum.svg` files inside `tmp_path / "figures"`.
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
   - Compression of large files must utilize chunked/streaming I/O to avoid spiking node RAM.
5. **Deliverable Scope:**
   - Implement `formatters/scribe_viz_bridge.py` and `formatters/test_scribe_viz_bridge.py`.

---

## Task
Implement the Python modules and tests as described and save them to:
- `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\formatters\scribe_viz_bridge.py`
- `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\formatters\test_scribe_viz_bridge.py`
using the `write_to_file` tool.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_geom\data\__init__.py ---
"""CoChem-GEOM Data Module."""

from .dataset import (
    DEFAULT_RANDOM_SEED,
    DEFAULT_STREAMING_BUFFER_SIZE,
    BaseTransform,
    CenterOfMassTransform,
    ComposeTransforms,
    EckartAlignmentTransform,
    GEOMDatasetFactory,
    GEOMInMemoryDataset,
    GEOMIterableDataset,
    GaussianJitterTransform,
    MolecularBatch,
    NormalizeTargetsTransform,
    RandomRotationTransform,
    geom_collate_fn,
    get_default_data_dir,
)
from .featurizer import (
    ATOMIC_MASS_UNIT_KG,
    ATOMIC_NUMBER_TO_SYMBOL,
    BOHR_RADIUS_ANGSTROM,
    BOLTZMANN_CONSTANT_EV_K,
    BOLTZMANN_CONSTANT_J_K,
    DEFAULT_ELEMENT_TYPES,
    DEFAULT_GRAPH_CUTOFF_ANGSTROM,
    DEFAULT_MAX_NEIGHBORS,
    ELEMENT_TYPE_TO_INDEX,
    ELEMENTARY_CHARGE_C,
    EV_TO_CM_MINUS_ONE,
    EV_TO_HARTREE,
    EV_TO_KCAL_MOL,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    INDEX_TO_ELEMENT_TYPE,
    KCAL_MOL_TO_EV,
    KCAL_MOL_TO_HARTREE,
    PLANCK_CONSTANT_J_S,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SPEED_OF_LIGHT_M_S,
    STANDARD_TEMPERATURE_K,
    SYMBOL_TO_ATOMIC_NUMBER,
    MolecularData,
    MolecularFeaturizer,
    MolecularGraphConfig,
    MolecularInput,
    build_radius_graph,
    calculate_boltzmann_weights,
    center_of_mass_molecular_data,
    compute_center_of_mass,
    compute_gaussian_rbf,
    compute_moment_of_inertia_tensor,
    compute_principal_rotational_constants,
    eckart_align_molecular_data,
    ev_to_hartree,
    ev_to_kcal_mol,
    get_atomic_mass,
    get_covalent_radius_angstrom,
    get_isotopic_mass,
    get_monoisotopic_mass,
    get_pauling_electronegativity,
    get_vdw_radius_angstrom,
    hartree_to_ev,
    hartree_to_kcal_mol,
    kcal_mol_to_ev,
    kcal_mol_to_hartree,
    rotate_molecular_data,
    translate_molecular_data,
)
from .geom_parser import (
    DEFAULT_MAX_BUFFER_SIZE,
    ConformerRecord,
    MoleculeRecord,
    QMOutputRecord,
    compute_bytes_sha256,
    compute_file_sha256,
    compute_rotational_constants,
    compute_structure_sha256,
    conformer_to_molecular_data,
    deserialize_geom_archive,
    deserialize_geom_bytes,
    ensemble_to_molecular_data,
    molecular_data_to_conformer,
    parse_geom_raw_molecule,
    parse_qm_log_text,
    parse_qm_output,
    rotate_conformer,
    serialize_geom_archive,
    serialize_geom_bytes,
    translate_conformer,
)
from .pyg_schema import (
    ConformerData,
    SchemaValidationError,
    batch_conformer_data,
    center_at_com_conformer_data,
    is_valid_conformer_data,
    rotate_conformer_data,
    translate_conformer_data,
    validate_conformer_data,
)

__all__ = [
    "ATOMIC_MASS_UNIT_KG",
    "ATOMIC_NUMBER_TO_SYMBOL",
    "BOHR_RADIUS_ANGSTROM",
    "BOLTZMANN_CONSTANT_EV_K",
    "BOLTZMANN_CONSTANT_J_K",
    "DEFAULT_ELEMENT_TYPES",
    "DEFAULT_GRAPH_CUTOFF_ANGSTROM",
    "DEFAULT_MAX_BUFFER_SIZE",
    "DEFAULT_MAX_NEIGHBORS",
    "DEFAULT_RANDOM_SEED",
    "DEFAULT_STREAMING_BUFFER_SIZE",
    "ELEMENT_TYPE_TO_INDEX",
    "ELEMENTARY_CHARGE_C",
    "EV_TO_CM_MINUS_ONE",
    "EV_TO_HARTREE",
    "EV_TO_KCAL_MOL",
    "HARTREE_TO_EV",
    "HARTREE_TO_KCAL_MOL",
    "HARTREE_TO_KJ_MOL",
    "INDEX_TO_ELEMENT_TYPE",
    "KCAL_MOL_TO_EV",
    "KCAL_MOL_TO_HARTREE",
    "PLANCK_CONSTANT_J_S",
    "ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ",
    "SPEED_OF_LIGHT_M_S",
    "STANDARD_TEMPERATURE_K",
    "SYMBOL_TO_ATOMIC_NUMBER",
    "BaseTransform",
    "CenterOfMassTransform",
    "ComposeTransforms",
    "ConformerData",
    "ConformerRecord",
    "EckartAlignmentTransform",
    "GEOMDatasetFactory",
    "GEOMInMemoryDataset",
    "GEOMIterableDataset",
    "GaussianJitterTransform",
    "MolecularBatch",
    "MolecularData",
    "MolecularFeaturizer",
    "MolecularGraphConfig",
    "MolecularInput",
    "MoleculeRecord",
    "NormalizeTargetsTransform",
    "QMOutputRecord",
    "RandomRotationTransform",
    "SchemaValidationError",
    "batch_conformer_data",
    "build_radius_graph",
    "calculate_boltzmann_weights",
    "center_at_com_conformer_data",
    "center_of_mass_molecular_data",
    "compute_bytes_sha256",
    "compute_center_of_mass",
    "compute_file_sha256",
    "compute_gaussian_rbf",
    "compute_moment_of_inertia_tensor",
    "compute_principal_rotational_constants",
    "compute_rotational_constants",
    "compute_structure_sha256",
    "conformer_to_molecular_data",
    "deserialize_geom_archive",
    "deserialize_geom_bytes",
    "eckart_align_molecular_data",
    "ensemble_to_molecular_data",
    "ev_to_hartree",
    "ev_to_kcal_mol",
    "geom_collate_fn",
    "get_atomic_mass",
    "get_covalent_radius_angstrom",
    "get_default_data_dir",
    "get_isotopic_mass",
    "get_monoisotopic_mass",
    "get_pauling_electronegativity",
    "get_vdw_radius_angstrom",
    "hartree_to_ev",
    "hartree_to_kcal_mol",
    "is_valid_conformer_data",
    "kcal_mol_to_ev",
    "kcal_mol_to_hartree",
    "molecular_data_to_conformer",
    "parse_geom_raw_molecule",
    "parse_qm_log_text",
    "parse_qm_output",
    "rotate_conformer",
    "rotate_conformer_data",
    "rotate_molecular_data",
    "serialize_geom_archive",
    "serialize_geom_bytes",
    "translate_conformer",
    "translate_conformer_data",
    "translate_molecular_data",
    "validate_conformer_data",
]

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
            self.report_archive_dir = pathlib.Path(os.environ["COCHEM_REPORT_ARCHIVE_DIR"])
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
        target_dir = pathlib.Path(search_dir) if search_dir is not None else self.artifacts_dir
        if not target_dir.exists() or not target_dir.is_dir():
            return []

        volumetric_exts = {".cube", ".html"}
        found_files: list[pathlib.Path] = []

        for path in target_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in volumetric_exts:
                if not path.name.startswith(".") and not path.name.endswith((".tar.zst", ".zst")):
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
        if target_path.name.endswith((".tar.zst", ".zst", ".tar.gz", ".gz", ".tar.bz2", ".xz")):
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
                self.logger.warning("Failed to log compressed artifact to User Guide: %s", e)
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
        target_dir = pathlib.Path(search_dir) if search_dir is not None else self.artifacts_dir
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
            ((1.0 - (compressed_size / original_size)) * 100.0) if original_size > 0 else 0.0
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
                new_content = existing_content.rstrip() + "\n\n" + table_header + table_row
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
            caption if caption else img_p.stem.replace("_", " ").replace("-", " ").title()
        )
        clean_label = (
            label if label else f"fig:{img_p.stem.lower().replace(' ', '_').replace('-', '_')}"
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
        target_dir = pathlib.Path(search_dir) if search_dir is not None else self.artifacts_dir
        base_dir = target_dir if search_dir is not None else self.report_archive_dir

        # Process and compress bloated volumetric artifacts
        compression_metrics = self.process_all_volumetric_artifacts(search_dir=target_dir)
        compressed_3d_assets: list[dict[str, Any]] = []
        for comp_path, orig_size, comp_size in compression_metrics:
            orig_mb = round(orig_size / (1024 * 1024), 2)
            comp_mb = round(comp_size / (1024 * 1024), 2)
            savings_pct = (
                round(((1.0 - (comp_size / orig_size)) * 100.0), 2) if orig_size > 0 else 0.0
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

    pattern_chunk = (b"ESP_DENSITY_GRID_DATA_CHUNK_64KB_" + b"0123456789ABCDEF" * 4100)[
        :CHUNK_SIZE_BYTES
    ]  # Exactly 65536 bytes
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

    pattern_chunk = (b"ESP_DENSITY_GRID_DATA_CHUNK_64KB_" + b"0123456789ABCDEF" * 4100)[
        :CHUNK_SIZE_BYTES
    ]  # Exactly 65536 bytes
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

    pattern_chunk = (b"<div><canvas data-grid='VOLUMETRIC_3D_NGL_STREAM'></canvas></div>\n" * 1024)[
        :CHUNK_SIZE_BYTES
    ]  # Exactly 65536 bytes
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
    uv_vis_img.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n")
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

    archive_path = configured_bridge.compress_volumetric_artifact(large_volumetric_cube_file)

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

    result = configured_bridge.compress_volumetric_artifact(small_volumetric_cube_file)

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
    assert "\\" not in rel_default, f"Path contains Windows backslashes: {rel_default}"
    assert "/" in rel_default
    assert rel_default == "../artifacts/figures/ir_spectrum.png"

    # 2. Relative path to artifacts_dir
    rel_artifacts = configured_bridge.calculate_relative_image_path(
        ir_path, base_dir=tmp_path / "artifacts"
    )
    assert "\\" not in rel_artifacts, f"Path contains Windows backslashes: {rel_artifacts}"
    assert rel_artifacts == "figures/ir_spectrum.png"

    # 3. String input compatibility
    rel_str = configured_bridge.calculate_relative_image_path(
        str(ir_path), base_dir=str(tmp_path / "artifacts")
    )
    assert "\\" not in rel_str
    assert rel_str == "figures/ir_spectrum.png"

    # 4. Already relative path string passthrough
    rel_already = configured_bridge.calculate_relative_image_path("figures/custom_spectrum.png")
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
    assert r"\includegraphics[width=\textwidth]{figures/ir_spectrum.png}" in snippet_custom
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
    assert r"\includegraphics[width=0.8\textwidth]{figures/raman_spectrum.svg}" in snippet_width

    # Clean default fallback caption and label from sanitized stem
    snippet_default = configured_bridge.generate_latex_image_snippet(
        image_path=spectral_figure_assets["uv_vis"],
        base_dir=artifacts_dir,
    )
    assert r"\caption{Uv Vis Spectrum}" in snippet_default
    assert r"\label{fig:uv_vis_spectrum}" in snippet_default
    assert r"\includegraphics[width=\textwidth]{figures/uv_vis_spectrum.pdf}" in snippet_default


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
    assert enriched["compressed_3d_assets"][0]["original_name"] == "esp_grid_large.cube"
    assert enriched["compressed_3d_assets"][0]["savings_pct"] > MIN_COMPRESSION_SAVINGS_PCT

    # 2. Test build_visual_payload directly on a separate sub-directory
    # with fresh assets
    sub_artifacts = tmp_path / "sub_artifacts"
    sub_figs = sub_artifacts / "figures"
    sub_figs.mkdir(parents=True, exist_ok=True)
    (sub_figs / "ir_spectrum.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 100
    )
    sub_cube = sub_artifacts / "homo_density.cube"
    chunk = (b"DENSITY_CHUNK_64KB_" + b"0123456789ABCDEF" * 4100)[:CHUNK_SIZE_BYTES]
    with open(sub_cube, "wb") as f_out:
        for _ in range(SYNTHETIC_CHUNK_64KB_COUNT_51MB):
            f_out.write(chunk)

    payload = configured_bridge.build_visual_payload(search_dir=sub_artifacts)
    assert "spectral_figures" in payload
    assert "spectral_figure_snippets" in payload
    assert "compressed_3d_assets" in payload
    assert len(payload["spectral_figures"]) == 1
    assert len(payload["compressed_3d_assets"]) == 1
    assert payload["compressed_3d_assets"][0]["original_name"] == "homo_density.cube"
    assert payload["compressed_3d_assets"][0]["savings_pct"] > MIN_COMPRESSION_SAVINGS_PCT


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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_geom\data\__init__.py ---
"""CoChem-GEOM Data Module."""

from .dataset import (
    DEFAULT_RANDOM_SEED,
    DEFAULT_STREAMING_BUFFER_SIZE,
    BaseTransform,
    CenterOfMassTransform,
    ComposeTransforms,
    EckartAlignmentTransform,
    GEOMDatasetFactory,
    GEOMInMemoryDataset,
    GEOMIterableDataset,
    GaussianJitterTransform,
    MolecularBatch,
    NormalizeTargetsTransform,
    RandomRotationTransform,
    geom_collate_fn,
    get_default_data_dir,
)
from .featurizer import (
    ATOMIC_MASS_UNIT_KG,
    ATOMIC_NUMBER_TO_SYMBOL,
    BOHR_RADIUS_ANGSTROM,
    BOLTZMANN_CONSTANT_EV_K,
    BOLTZMANN_CONSTANT_J_K,
    DEFAULT_ELEMENT_TYPES,
    DEFAULT_GRAPH_CUTOFF_ANGSTROM,
    DEFAULT_MAX_NEIGHBORS,
    ELEMENT_TYPE_TO_INDEX,
    ELEMENTARY_CHARGE_C,
    EV_TO_CM_MINUS_ONE,
    EV_TO_HARTREE,
    EV_TO_KCAL_MOL,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    INDEX_TO_ELEMENT_TYPE,
    KCAL_MOL_TO_EV,
    KCAL_MOL_TO_HARTREE,
    PLANCK_CONSTANT_J_S,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SPEED_OF_LIGHT_M_S,
    STANDARD_TEMPERATURE_K,
    SYMBOL_TO_ATOMIC_NUMBER,
    MolecularData,
    MolecularFeaturizer,
    MolecularGraphConfig,
    MolecularInput,
    build_radius_graph,
    calculate_boltzmann_weights,
    center_of_mass_molecular_data,
    compute_center_of_mass,
    compute_gaussian_rbf,
    compute_moment_of_inertia_tensor,
    compute_principal_rotational_constants,
    eckart_align_molecular_data,
    ev_to_hartree,
    ev_to_kcal_mol,
    get_atomic_mass,
    get_covalent_radius_angstrom,
    get_isotopic_mass,
    get_monoisotopic_mass,
    get_pauling_electronegativity,
    get_vdw_radius_angstrom,
    hartree_to_ev,
    hartree_to_kcal_mol,
    kcal_mol_to_ev,
    kcal_mol_to_hartree,
    rotate_molecular_data,
    translate_molecular_data,
)
from .geom_parser import (
    DEFAULT_MAX_BUFFER_SIZE,
    ConformerRecord,
    MoleculeRecord,
    QMOutputRecord,
    compute_bytes_sha256,
    compute_file_sha256,
    compute_rotational_constants,
    compute_structure_sha256,
    conformer_to_molecular_data,
    deserialize_geom_archive,
    deserialize_geom_bytes,
    ensemble_to_molecular_data,
    molecular_data_to_conformer,
    parse_geom_raw_molecule,
    parse_qm_log_text,
    parse_qm_output,
    rotate_conformer,
    serialize_geom_archive,
    serialize_geom_bytes,
    translate_conformer,
)
from .pyg_schema import (
    ConformerData,
    SchemaValidationError,
    batch_conformer_data,
    center_at_com_conformer_data,
    is_valid_conformer_data,
    rotate_conformer_data,
    translate_conformer_data,
    validate_conformer_data,
)

__all__ = [
    "ATOMIC_MASS_UNIT_KG",
    "ATOMIC_NUMBER_TO_SYMBOL",
    "BOHR_RADIUS_ANGSTROM",
    "BOLTZMANN_CONSTANT_EV_K",
    "BOLTZMANN_CONSTANT_J_K",
    "DEFAULT_ELEMENT_TYPES",
    "DEFAULT_GRAPH_CUTOFF_ANGSTROM",
    "DEFAULT_MAX_BUFFER_SIZE",
    "DEFAULT_MAX_NEIGHBORS",
    "DEFAULT_RANDOM_SEED",
    "DEFAULT_STREAMING_BUFFER_SIZE",
    "ELEMENT_TYPE_TO_INDEX",
    "ELEMENTARY_CHARGE_C",
    "EV_TO_CM_MINUS_ONE",
    "EV_TO_HARTREE",
    "EV_TO_KCAL_MOL",
    "HARTREE_TO_EV",
    "HARTREE_TO_KCAL_MOL",
    "HARTREE_TO_KJ_MOL",
    "INDEX_TO_ELEMENT_TYPE",
    "KCAL_MOL_TO_EV",
    "KCAL_MOL_TO_HARTREE",
    "PLANCK_CONSTANT_J_S",
    "ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ",
    "SPEED_OF_LIGHT_M_S",
    "STANDARD_TEMPERATURE_K",
    "SYMBOL_TO_ATOMIC_NUMBER",
    "BaseTransform",
    "CenterOfMassTransform",
    "ComposeTransforms",
    "ConformerData",
    "ConformerRecord",
    "EckartAlignmentTransform",
    "GEOMDatasetFactory",
    "GEOMInMemoryDataset",
    "GEOMIterableDataset",
    "GaussianJitterTransform",
    "MolecularBatch",
    "MolecularData",
    "MolecularFeaturizer",
    "MolecularGraphConfig",
    "MolecularInput",
    "MoleculeRecord",
    "NormalizeTargetsTransform",
    "QMOutputRecord",
    "RandomRotationTransform",
    "SchemaValidationError",
    "batch_conformer_data",
    "build_radius_graph",
    "calculate_boltzmann_weights",
    "center_at_com_conformer_data",
    "center_of_mass_molecular_data",
    "compute_bytes_sha256",
    "compute_center_of_mass",
    "compute_file_sha256",
    "compute_gaussian_rbf",
    "compute_moment_of_inertia_tensor",
    "compute_principal_rotational_constants",
    "compute_rotational_constants",
    "compute_structure_sha256",
    "conformer_to_molecular_data",
    "deserialize_geom_archive",
    "deserialize_geom_bytes",
    "eckart_align_molecular_data",
    "ensemble_to_molecular_data",
    "ev_to_hartree",
    "ev_to_kcal_mol",
    "geom_collate_fn",
    "get_atomic_mass",
    "get_covalent_radius_angstrom",
    "get_default_data_dir",
    "get_isotopic_mass",
    "get_monoisotopic_mass",
    "get_pauling_electronegativity",
    "get_vdw_radius_angstrom",
    "hartree_to_ev",
    "hartree_to_kcal_mol",
    "is_valid_conformer_data",
    "kcal_mol_to_ev",
    "kcal_mol_to_hartree",
    "molecular_data_to_conformer",
    "parse_geom_raw_molecule",
    "parse_qm_log_text",
    "parse_qm_output",
    "rotate_conformer",
    "rotate_conformer_data",
    "rotate_molecular_data",
    "serialize_geom_archive",
    "serialize_geom_bytes",
    "translate_conformer",
    "translate_conformer_data",
    "translate_molecular_data",
    "validate_conformer_data",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_geom\data\pyg_schema.py ---
"""CoChem-GEOM: PyTorch Geometric (PyG) Execution Tensor Schema.
=============================================================================
Defines the authoritative `ConformerData` tensor container subclassing
`torch_geometric.data.Data` for rotational spectroscopy, quantum chemistry,
and equivariant neural network architectures (EGNN, SchNet, DimeNet++, PaiNN).

Authoritative Standards:
- Method Matrix v4: Data Ingestion & Spectroscopic Graph Contracts
- SWEBOK v3 / ISO 25010 Software Quality Standards
- Mendeleev Library Mandate: Dynamic atomic mass & isotopic resolution (NEVER hardcoded)
- Cryptographic Provenance: SHA-256 checksum generation for structures and files
- SE(3) Equivariance & Invariance: Separation of spatial pos vs non-spatial node features
- State Immutability: Pure functional geometric transformations (immutable operations)
- Strict Zero-Mock Mandate: Authentic physical constants and real quantum chemical geometries
"""

from __future__ import annotations

import copy
import hashlib
import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from mendeleev import element
import numpy as np
import torch
from torch_geometric.data import Batch, Data

from cochem_geom.data.featurizer import (
    ATOMIC_NUMBER_TO_SYMBOL,
    DEFAULT_GRAPH_CUTOFF_ANGSTROM,
    DEFAULT_MAX_NEIGHBORS,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SYMBOL_TO_ATOMIC_NUMBER,
    MolecularData,
    build_radius_graph,
    compute_center_of_mass as base_compute_center_of_mass,
    compute_moment_of_inertia_tensor as base_compute_moment_of_inertia_tensor,
    compute_principal_rotational_constants as base_compute_principal_rotational_constants,
    get_atomic_mass,
    get_monoisotopic_mass,
)
from cochem_geom.data.geom_parser import (
    ConformerRecord,
    MoleculeRecord,
    compute_file_sha256,
    compute_structure_sha256,
)

logger = logging.getLogger("cochem_geom.data.pyg_schema")


# ==============================================================================
# 1. Validation Helpers and Error Definitions
# ==============================================================================


class SchemaValidationError(ValueError):
    """Raised when tensor shapes, types, or physical constraints are violated."""
    pass


def validate_conformer_data(data: ConformerData) -> None:
    """Perform fail-fast strict validation of ConformerData tensor schema [M]/[D].

    Validation rules:
    - `z`: 1D torch.Tensor of dtype `torch.long` or `torch.int64`, non-empty, non-negative.
    - `pos`: 2D torch.Tensor of shape `(N, 3)` of dtype `torch.float32`. float16/half is rejected.
    - `z.size(0) == pos.size(0)`: Number of atomic centers must match exactly.
    - `edge_index`: 2D torch.Tensor of shape `(2, E)` of dtype `torch.long` or `torch.int64`.
      Indices must satisfy `0 <= edge_index < N`.
    - `y`: Optional torch.Tensor of dtype `torch.float32`.
    - `weight`: Optional torch.Tensor of dtype `torch.float32`.
    - `x`: Optional 2D torch.Tensor of shape `(N, F)` of dtype `torch.float32`.
    - `edge_attr`: Optional 2D torch.Tensor of shape `(E, D)` of dtype `torch.float32`.
    - `forces`: Optional 2D torch.Tensor of shape `(N, 3)` of dtype `torch.float32`.
    - `dipole`: Optional torch.Tensor of shape `(3,)` or `(1, 3)` of dtype `torch.float32`.
    - `rotational_constants`: Optional torch.Tensor of shape `(3,)` or `(1, 3)` of dtype `torch.float32`.

    Parameters
    ----------
    data : ConformerData
        The ConformerData instance to validate.

    Raises
    ------
    TypeError
        If dtypes or non-tensor attributes violate specification.
    ValueError / SchemaValidationError
        If shapes, dimensions, or indexing bounds are invalid.
    """
    if not isinstance(data, (Data, ConformerData)):
        raise TypeError(f"Expected ConformerData or torch_geometric.data.Data, got {type(data)}")

    # 1. Validate z (Atomic Numbers)
    z_val = getattr(data, "z", None)
    if z_val is None:
        raise SchemaValidationError("ConformerData must contain atomic numbers tensor 'z'.")
    if not isinstance(z_val, torch.Tensor):
        raise TypeError(f"Attribute 'z' must be a torch.Tensor, got {type(z_val)}")
    if z_val.dim() != 1:
        raise SchemaValidationError(f"Attribute 'z' must be a 1D tensor of shape (N,), got shape {list(z_val.shape)}")
    if z_val.dtype not in (torch.int64, torch.long, torch.int32):
        raise TypeError(f"Attribute 'z' must have integer dtype (torch.long/int64), got {z_val.dtype}")
    if z_val.numel() == 0:
        raise SchemaValidationError("Attribute 'z' cannot be empty (N >= 1 required).")
    if (z_val <= 0).any():
        raise SchemaValidationError(f"All atomic numbers in 'z' must be positive integers, found <= 0 in {z_val.tolist()}")

    num_atoms = z_val.size(0)

    # 2. Validate pos (Cartesian Coordinates)
    pos_val = getattr(data, "pos", None)
    if pos_val is None:
        raise SchemaValidationError("ConformerData must contain Cartesian coordinates tensor 'pos'.")
    if not isinstance(pos_val, torch.Tensor):
        raise TypeError(f"Attribute 'pos' must be a torch.Tensor, got {type(pos_val)}")
    if pos_val.dtype in (torch.float16, torch.bfloat16):
        raise TypeError(
            f"ConformerData pos does not support reduced precision float16/bfloat16 ({pos_val.dtype}); "
            "float32 is required for physical and rotational coordinate precision."
        )
    if pos_val.dtype != torch.float32:
        raise TypeError(f"Attribute 'pos' must have dtype torch.float32, got {pos_val.dtype}")
    if pos_val.dim() != 2 or pos_val.size(1) != 3:
        raise SchemaValidationError(
            f"Attribute 'pos' must have shape (N, 3), got {list(pos_val.shape)}"
        )
    if pos_val.size(0) != num_atoms:
        raise SchemaValidationError(
            f"Atom count mismatch: z has {num_atoms} atoms but pos has {pos_val.size(0)} coordinates."
        )

    # 3. Validate edge_index (Graph Connectivity)
    edge_index_val = getattr(data, "edge_index", None)
    if edge_index_val is not None:
        if not isinstance(edge_index_val, torch.Tensor):
            raise TypeError(f"Attribute 'edge_index' must be a torch.Tensor, got {type(edge_index_val)}")
        if edge_index_val.dtype not in (torch.int64, torch.long, torch.int32):
            raise TypeError(f"Attribute 'edge_index' must have integer dtype (torch.long), got {edge_index_val.dtype}")
        if edge_index_val.dim() != 2 or edge_index_val.size(0) != 2:
            raise SchemaValidationError(
                f"Attribute 'edge_index' must have shape (2, E), got {list(edge_index_val.shape)}"
            )
        num_edges = edge_index_val.size(1)
        if num_edges > 0 and num_atoms > 0:
            max_idx = int(edge_index_val.max().item())
            min_idx = int(edge_index_val.min().item())
            if min_idx < 0:
                raise SchemaValidationError(f"Attribute 'edge_index' contains negative node index {min_idx}.")
            if max_idx >= num_atoms:
                raise SchemaValidationError(
                    f"Attribute 'edge_index' references node index {max_idx} >= num_atoms ({num_atoms})."
                )
    else:
        num_edges = 0

    # 4. Validate y (Target Property / Energy)
    y_val = getattr(data, "y", None)
    if y_val is not None:
        if not isinstance(y_val, torch.Tensor):
            raise TypeError(f"Attribute 'y' must be a torch.Tensor, got {type(y_val)}")
        if y_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'y' must have dtype torch.float32, got {y_val.dtype}")

    # 5. Validate weight (Statistical / Boltzmann Weight)
    w_val = getattr(data, "weight", None)
    if w_val is not None:
        if not isinstance(w_val, torch.Tensor):
            raise TypeError(f"Attribute 'weight' must be a torch.Tensor, got {type(w_val)}")
        if w_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'weight' must have dtype torch.float32, got {w_val.dtype}")

    # 6. Validate x (Node Invariant Features)
    x_val = getattr(data, "x", None)
    if x_val is not None:
        if not isinstance(x_val, torch.Tensor):
            raise TypeError(f"Attribute 'x' must be a torch.Tensor, got {type(x_val)}")
        if x_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'x' must have dtype torch.float32, got {x_val.dtype}")
        if x_val.dim() != 2 or x_val.size(0) != num_atoms:
            raise SchemaValidationError(
                f"Attribute 'x' must have shape (N, F) where N={num_atoms}, got {list(x_val.shape)}"
            )

    # 7. Validate edge_attr (Edge Feature Tensor)
    ea_val = getattr(data, "edge_attr", None)
    if ea_val is not None:
        if not isinstance(ea_val, torch.Tensor):
            raise TypeError(f"Attribute 'edge_attr' must be a torch.Tensor, got {type(ea_val)}")
        if ea_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'edge_attr' must have dtype torch.float32, got {ea_val.dtype}")
        if ea_val.dim() != 2 or ea_val.size(0) != num_edges:
            raise SchemaValidationError(
                f"Attribute 'edge_attr' must have shape (E, D) where E={num_edges}, got {list(ea_val.shape)}"
            )

    # 8. Validate forces (Cartesian Atomic Forces)
    f_val = getattr(data, "forces", None)
    if f_val is not None:
        if not isinstance(f_val, torch.Tensor):
            raise TypeError(f"Attribute 'forces' must be a torch.Tensor, got {type(f_val)}")
        if f_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'forces' must have dtype torch.float32, got {f_val.dtype}")
        if f_val.dim() != 2 or f_val.shape != pos_val.shape:
            raise SchemaValidationError(
                f"Attribute 'forces' must have shape {list(pos_val.shape)}, got {list(f_val.shape)}"
            )

    # 9. Validate dipole (Electric Dipole Vector)
    d_val = getattr(data, "dipole", None)
    if d_val is not None:
        if not isinstance(d_val, torch.Tensor):
            raise TypeError(f"Attribute 'dipole' must be a torch.Tensor, got {type(d_val)}")
        if d_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'dipole' must have dtype torch.float32, got {d_val.dtype}")
        if not ((d_val.dim() == 1 and d_val.size(0) == 3) or (d_val.dim() == 2 and d_val.shape == (1, 3))):
            raise SchemaValidationError(
                f"Attribute 'dipole' must have shape (3,) or (1, 3), got {list(d_val.shape)}"
            )

    # 10. Validate rotational_constants (A, B, C in MHz)
    rc_val = getattr(data, "rotational_constants", None)
    if rc_val is not None:
        if not isinstance(rc_val, torch.Tensor):
            raise TypeError(f"Attribute 'rotational_constants' must be a torch.Tensor, got {type(rc_val)}")
        if rc_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'rotational_constants' must have dtype torch.float32, got {rc_val.dtype}")
        if not ((rc_val.dim() == 1 and rc_val.size(0) == 3) or (rc_val.dim() == 2 and rc_val.shape == (1, 3))):
            raise SchemaValidationError(
                f"Attribute 'rotational_constants' must have shape (3,) or (1, 3), got {list(rc_val.shape)}"
            )


def is_valid_conformer_data(data: Any) -> bool:
    """Return True if object is a fully valid ConformerData instance, False otherwise.

    Parameters
    ----------
    data : Any
        Object to inspect.

    Returns
    -------
    bool
        True if valid without exception, False otherwise.
    """
    try:
        validate_conformer_data(data)
        return True
    except (SchemaValidationError, TypeError, ValueError, AttributeError):
        return False


# ==============================================================================
# 2. ConformerData Tensor Schema Class
# ==============================================================================


class ConformerData(Data):
    """Authoritative PyTorch Geometric execution tensor container for molecular conformers.

    Inherits from `torch_geometric.data.Data`. Enforces float32 spatial coordinate precision,
    SE(3)-equivariant operations, dynamic Mendeleev mass calculations, and state immutability.

    Attributes
    ----------
    z : torch.Tensor
        Atomic numbers Z of shape (N,) with dtype torch.long.
    pos : torch.Tensor
        Spatial Cartesian coordinates in Angstroms of shape (N, 3) with dtype torch.float32.
    edge_index : torch.Tensor
        Graph connectivity edge indices of shape (2, E) with dtype torch.long.
    y : Optional[torch.Tensor]
        Scalar target ground-state electronic energy of shape (1,) with dtype torch.float32.
    x : Optional[torch.Tensor]
        Non-spatial invariant node features of shape (N, F) with dtype torch.float32.
    edge_attr : Optional[torch.Tensor]
        Edge feature attributes (e.g. RBF distances) of shape (E, D) with dtype torch.float32.
    weight : torch.Tensor
        Statistical or Boltzmann thermodynamic weighting factor of shape (1,) with dtype torch.float32.
    forces : Optional[torch.Tensor]
        Spatial gradient forces of shape (N, 3) with dtype torch.float32.
    dipole : Optional[torch.Tensor]
        Electric dipole moment vector of shape (3,) with dtype torch.float32.
    rotational_constants : Optional[torch.Tensor]
        Principal spectroscopic rotational constants (A, B, C) in MHz of shape (3,) with dtype torch.float32.
    symbols : List[str]
        IUPAC chemical symbols of length N.
    smiles : Optional[str]
        Canonical SMILES string representation.
    conformer_id : Optional[int]
        Sequential conformer index within the molecular ensemble.
    source_hash : Optional[str]
        Cryptographic SHA-256 provenance checksum of the calculation source or file.
    frequencies : Optional[torch.Tensor]
        Harmonic vibrational frequencies in cm^-1 of shape (M,) with dtype torch.float32.
    s2_spin : Optional[float]
        Spin angular momentum expectation value <S^2>.
    metadata : Dict[str, Any]
        Arbitrary user and provenance metadata dictionary.
    """

    def __init__(
        self,
        z: Optional[torch.Tensor] = None,
        pos: Optional[torch.Tensor] = None,
        edge_index: Optional[torch.Tensor] = None,
        y: Optional[torch.Tensor] = None,
        x: Optional[torch.Tensor] = None,
        edge_attr: Optional[torch.Tensor] = None,
        weight: Optional[torch.Tensor] = None,
        forces: Optional[torch.Tensor] = None,
        dipole: Optional[torch.Tensor] = None,
        rotational_constants: Optional[torch.Tensor] = None,
        symbols: Optional[List[str]] = None,
        smiles: Optional[str] = None,
        conformer_id: Optional[int] = None,
        source_hash: Optional[str] = None,
        frequencies: Optional[torch.Tensor] = None,
        s2_spin: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        validate: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            x=x,
            edge_index=edge_index,
            edge_attr=edge_attr,
            y=y,
            pos=pos,
            z=z,
            **kwargs,
        )

        if z is not None:
            self.z = z
        if pos is not None:
            self.pos = pos
        if edge_index is not None:
            self.edge_index = edge_index
        elif not hasattr(self, "edge_index") or self.edge_index is None:
            self.edge_index = torch.empty((2, 0), dtype=torch.long, device=pos.device if pos is not None else None)

        if y is not None:
            self.y = y
        if x is not None:
            self.x = x
        if edge_attr is not None:
            self.edge_attr = edge_attr

        self.weight = (
            weight
            if weight is not None
            else torch.tensor([1.0], dtype=torch.float32, device=pos.device if pos is not None else None)
        )

        if forces is not None:
            self.forces = forces
        if dipole is not None:
            self.dipole = dipole
        if rotational_constants is not None:
            self.rotational_constants = rotational_constants

        if symbols is not None:
            self.symbols = list(symbols)
        elif z is not None:
            self.symbols = [ATOMIC_NUMBER_TO_SYMBOL.get(int(zi.item()), "X") for zi in z]
        else:
            self.symbols = []

        if smiles is not None:
            self.smiles = smiles
        if conformer_id is not None:
            self.conformer_id = conformer_id
        if source_hash is not None:
            self.source_hash = source_hash
        if frequencies is not None:
            self.frequencies = frequencies
        if s2_spin is not None:
            self.s2_spin = s2_spin

        self.metadata = dict(metadata) if metadata is not None else {}

        if validate and z is not None and pos is not None:
            validate_conformer_data(self)

    # --------------------------------------------------------------------------
    # Fallback Property Resolution for PyG GlobalStorage
    # --------------------------------------------------------------------------

    def __getattr__(self, key: str) -> Any:
        """Safe attribute access returning None for unassigned optional fields."""
        try:
            return super().__getattr__(key)
        except AttributeError:
            if key in (
                "forces",
                "dipole",
                "rotational_constants",
                "frequencies",
                "s2_spin",
                "conformer_id",
                "source_hash",
                "smiles",
                "y",
                "x",
                "edge_attr",
                "edge_index",
                "z",
                "pos",
                "symbols",
                "metadata",
                "weight",
            ):
                return None
            raise

    # --------------------------------------------------------------------------
    # PyG Batching Increment Override
    # --------------------------------------------------------------------------

    def __inc__(self, key: str, value: Any, *args: Any, **kwargs: Any) -> Any:
        """Override PyG index incrementing during mini-batch concatenation.

        For `edge_index`, returns `self.z.size(0)` (the total number of node centers)
        so that edges across separate graphs in a batch are correctly offset.
        """
        if key == "edge_index":
            if self.z is not None:
                return self.z.size(0)
            if self.pos is not None:
                return self.pos.size(0)
            return self.num_nodes
        return super().__inc__(key, value, *args, **kwargs)

    # --------------------------------------------------------------------------
    # Pure Functional SE(3) Transformations (State Immutability Guaranteed)
    # --------------------------------------------------------------------------

    def translate(
        self, vector: Union[torch.Tensor, Sequence[float], np.ndarray]
    ) -> ConformerData:
        """Translate Cartesian coordinates immutably by translation vector T [D].

        Under spatial translation $\\mathbf{r}' = \\mathbf{r} + \\mathbf{T}$:
        - `pos` translates equivariantly.
        - `forces` are invariant (internal gradients remain identical).
        - `y`, `weight`, `rotational_constants` are invariant.
        - `dipole` is invariant for neutral molecules.

        Parameters
        ----------
        vector : Union[torch.Tensor, Sequence[float], np.ndarray]
            3D translation vector of shape (3,).

        Returns
        -------
        ConformerData
            A new ConformerData instance with translated coordinates.
        """
        if isinstance(vector, torch.Tensor):
            t_vec = vector.to(dtype=self.pos.dtype, device=self.pos.device)
        else:
            t_vec = torch.tensor(vector, dtype=self.pos.dtype, device=self.pos.device)

        if t_vec.shape != (3,) and t_vec.shape != (1, 3):
            raise ValueError(f"Translation vector must have shape (3,) or (1, 3), got {list(t_vec.shape)}")

        new_pos = self.pos + t_vec.squeeze()

        return ConformerData(
            z=self.z.clone() if self.z is not None else None,
            pos=new_pos,
            edge_index=self.edge_index.clone() if self.edge_index is not None else None,
            y=self.y.clone() if self.y is not None else None,
            x=self.x.clone() if self.x is not None else None,
            edge_attr=self.edge_attr.clone() if self.edge_attr is not None else None,
            weight=self.weight.clone() if self.weight is not None else None,
            forces=self.forces.clone() if self.forces is not None else None,
            dipole=self.dipole.clone() if self.dipole is not None else None,
            rotational_constants=(
                self.rotational_constants.clone()
                if self.rotational_constants is not None
                else None
            ),
            symbols=list(self.symbols) if self.symbols is not None else None,
            smiles=self.smiles,
            conformer_id=self.conformer_id,
            source_hash=self.source_hash,
            frequencies=self.frequencies.clone() if self.frequencies is not None else None,
            s2_spin=self.s2_spin,
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else {},
            validate=False,
        )

    def rotate(
        self, matrix: Union[torch.Tensor, Sequence[Sequence[float]], np.ndarray]
    ) -> ConformerData:
        """Rotate Cartesian coordinates, forces, and dipole immutably via SO(3) matrix R [D].

        Under 3D rotation $\\mathbf{r}' = \\mathbf{R} \\mathbf{r}$:
        - `pos` rotates equivariantly: $\\text{pos}' = \\text{pos} \\mathbf{R}^T$.
        - `forces` rotate equivariantly: $\\text{forces}' = \\text{forces} \\mathbf{R}^T$.
        - `dipole` rotates equivariantly: $\\boldsymbol{\\mu}' = \\boldsymbol{\\mu} \\mathbf{R}^T$.
        - `y`, `weight`, `rotational_constants` are scalar SO(3) invariants.

        Parameters
        ----------
        matrix : Union[torch.Tensor, Sequence[Sequence[float]], np.ndarray]
            3x3 orthogonal rotation matrix R.

        Returns
        -------
        ConformerData
            A new ConformerData instance with rotated geometric properties.
        """
        if isinstance(matrix, torch.Tensor):
            rot_mat = matrix.to(dtype=self.pos.dtype, device=self.pos.device)
        else:
            rot_mat = torch.tensor(matrix, dtype=self.pos.dtype, device=self.pos.device)

        if rot_mat.shape != (3, 3):
            raise ValueError(f"Rotation matrix must have shape (3, 3), got {list(rot_mat.shape)}")

        # Equivariant rotation: pos' = pos @ R^T
        new_pos = torch.matmul(self.pos, rot_mat.t())

        # Equivariant forces rotation if present
        new_forces = (
            torch.matmul(self.forces, rot_mat.t())
            if self.forces is not None
            else None
        )

        # Equivariant dipole rotation if present
        if self.dipole is not None:
            if self.dipole.dim() == 1:
                new_dipole = torch.matmul(rot_mat, self.dipole)
            else:
                new_dipole = torch.matmul(self.dipole, rot_mat.t())
        else:
            new_dipole = None

        return ConformerData(
            z=self.z.clone() if self.z is not None else None,
            pos=new_pos,
            edge_index=self.edge_index.clone() if self.edge_index is not None else None,
            y=self.y.clone() if self.y is not None else None,
            x=self.x.clone() if self.x is not None else None,
            edge_attr=self.edge_attr.clone() if self.edge_attr is not None else None,
            weight=self.weight.clone() if self.weight is not None else None,
            forces=new_forces,
            dipole=new_dipole,
            rotational_constants=(
                self.rotational_constants.clone()
                if self.rotational_constants is not None
                else None
            ),
            symbols=list(self.symbols) if self.symbols is not None else None,
            smiles=self.smiles,
            conformer_id=self.conformer_id,
            source_hash=self.source_hash,
            frequencies=self.frequencies.clone() if self.frequencies is not None else None,
            s2_spin=self.s2_spin,
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else {},
            validate=False,
        )

    # --------------------------------------------------------------------------
    # Center of Mass and Spectroscopic Tensor Calculations
    # --------------------------------------------------------------------------

    def center_of_mass(
        self, masses: Optional[Union[torch.Tensor, Sequence[float]]] = None
    ) -> torch.Tensor:
        """Compute Center of Mass (COM) coordinates in Angstroms [D].

        Dynamically queries standard atomic weights from the Mendeleev database
        if `masses` is omitted.

        $$\\mathbf{r}_{\\text{COM}} = \\frac{\\sum_{i=1}^N m_i \\mathbf{r}_i}{\\sum_{i=1}^N m_i}$$

        Parameters
        ----------
        masses : Optional[Union[torch.Tensor, Sequence[float]]]
            Optional explicit mass array of shape (N,).

        Returns
        -------
        torch.Tensor
            Center of mass vector of shape (3,) with dtype torch.float32.
        """
        if masses is not None:
            if isinstance(masses, torch.Tensor):
                m_tensor = masses.to(dtype=self.pos.dtype, device=self.pos.device)
            else:
                m_tensor = torch.tensor(masses, dtype=self.pos.dtype, device=self.pos.device)
        else:
            # Dynamic Mendeleev resolution (NEVER hardcoded)
            m_list = [get_atomic_mass(int(zi.item())) for zi in self.z]
            m_tensor = torch.tensor(m_list, dtype=self.pos.dtype, device=self.pos.device)

        if m_tensor.dim() == 1:
            m_tensor = m_tensor.unsqueeze(-1)

        total_mass = m_tensor.sum()
        if total_mass <= 0.0:
            raise ValueError(f"Total molecular mass must be positive, got {total_mass.item()}")

        com = (self.pos * m_tensor).sum(dim=0) / total_mass
        return com.squeeze()

    def center_at_com(
        self, masses: Optional[Union[torch.Tensor, Sequence[float]]] = None
    ) -> ConformerData:
        """Return a new ConformerData centered at the molecular Center of Mass [D].

        State immutability: returns a fresh instance without mutating current coordinates.

        Parameters
        ----------
        masses : Optional[Union[torch.Tensor, Sequence[float]]]
            Optional explicit atomic mass vector.

        Returns
        -------
        ConformerData
            A new ConformerData instance centered at COM.
        """
        com = self.center_of_mass(masses=masses)
        return self.translate(-com)

    def compute_moment_of_inertia_tensor(
        self, masses: Optional[Union[torch.Tensor, Sequence[float]]] = None
    ) -> torch.Tensor:
        """Construct the 3x3 Moment of Inertia tensor in the COM frame [D].

        $$I_{\\alpha \\beta} = \\sum_{i=1}^N m_i \\left( r_i'^2 \\delta_{\\alpha \\beta} - r'_{i,\\alpha} r'_{i,\\beta} \\right)$$

        where $\\mathbf{r}'_i = \\mathbf{r}_i - \\mathbf{r}_{\\text{COM}}$ in units of $u \\cdot \\text{\\AA}^2$.

        Parameters
        ----------
        masses : Optional[Union[torch.Tensor, Sequence[float]]]
            Atomic masses in Daltons. Queries Mendeleev dynamically if None.

        Returns
        -------
        torch.Tensor
            Moment of inertia tensor of shape (3, 3) with dtype torch.float32.
        """
        if masses is not None:
            if isinstance(masses, torch.Tensor):
                m = masses.to(dtype=self.pos.dtype, device=self.pos.device)
            else:
                m = torch.tensor(masses, dtype=self.pos.dtype, device=self.pos.device)
        else:
            m_list = [get_atomic_mass(int(zi.item())) for zi in self.z]
            m = torch.tensor(m_list, dtype=self.pos.dtype, device=self.pos.device)

        com = self.center_of_mass(masses=m)
        rel_pos = self.pos - com.unsqueeze(0)

        x = rel_pos[:, 0]
        y = rel_pos[:, 1]
        z = rel_pos[:, 2]

        ixx = (m * (y**2 + z**2)).sum()
        iyy = (m * (x**2 + z**2)).sum()
        izz = (m * (x**2 + y**2)).sum()

        ixy = -(m * x * y).sum()
        ixz = -(m * x * z).sum()
        iyz = -(m * y * z).sum()

        inertia = torch.tensor(
            [
                [ixx, ixy, ixz],
                [ixy, iyy, iyz],
                [ixz, iyz, izz],
            ],
            dtype=self.pos.dtype,
            device=self.pos.device,
        )
        return inertia

    def compute_principal_rotational_constants(
        self, masses: Optional[Union[torch.Tensor, Sequence[float]]] = None
    ) -> torch.Tensor:
        """Compute principal spectroscopic rotational constants (A, B, C) in MHz [D].

        Rotational constant factor: $h / (8 \\pi^2) = 505379.008784\\text{ MHz} \\cdot u \\cdot \\text{\\AA}^2$.
        Eigenvalues sorted such that $I_a \\le I_b \\le I_c$, yielding $A \\ge B \\ge C$.

        Parameters
        ----------
        masses : Optional[Union[torch.Tensor, Sequence[float]]]
            Atomic masses in Daltons. Queries Mendeleev dynamically if None.

        Returns
        -------
        torch.Tensor
            Rotational constants tensor of shape (3,) in MHz: [A, B, C].
        """
        inertia = self.compute_moment_of_inertia_tensor(masses=masses)
        eigenvalues = torch.linalg.eigvalsh(inertia)
        eigenvalues, _ = torch.sort(eigenvalues)

        ia = float(eigenvalues[0].item())
        ib = float(eigenvalues[1].item())
        ic = float(eigenvalues[2].item())

        a_const = float(ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / ia) if ia > 1e-6 else 0.0
        b_const = float(ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / ib) if ib > 1e-6 else 0.0
        c_const = float(ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / ic) if ic > 1e-6 else 0.0

        return torch.tensor([a_const, b_const, c_const], dtype=torch.float32, device=self.pos.device)

    # --------------------------------------------------------------------------
    # Inter-Schema Conversions (MolecularData & ConformerRecord)
    # --------------------------------------------------------------------------

    @classmethod
    def from_molecular_data(cls, mol_data: MolecularData) -> ConformerData:
        """Construct a ConformerData instance from a MolecularData container [D].

        Parameters
        ----------
        mol_data : MolecularData
            Source MolecularData object.

        Returns
        -------
        ConformerData
            Converted ConformerData instance.
        """
        pos = mol_data.pos.to(dtype=torch.float32)
        z = mol_data.z.to(dtype=torch.long)
        edge_index = mol_data.edge_index.to(dtype=torch.long) if mol_data.edge_index is not None else None
        y = mol_data.y.to(dtype=torch.float32) if mol_data.y is not None else None
        x = mol_data.x.to(dtype=torch.float32) if mol_data.x is not None else None
        edge_attr = mol_data.edge_attr.to(dtype=torch.float32) if mol_data.edge_attr is not None else None
        weight = mol_data.weight.to(dtype=torch.float32) if mol_data.weight is not None else None
        forces = mol_data.forces.to(dtype=torch.float32) if mol_data.forces is not None else None
        dipole = mol_data.dipole.to(dtype=torch.float32) if mol_data.dipole is not None else None
        rotational_constants = (
            mol_data.rotational_constants.to(dtype=torch.float32)
            if mol_data.rotational_constants is not None
            else None
        )

        return cls(
            z=z,
            pos=pos,
            edge_index=edge_index,
            y=y,
            x=x,
            edge_attr=edge_attr,
            weight=weight,
            forces=forces,
            dipole=dipole,
            rotational_constants=rotational_constants,
            symbols=list(mol_data.symbols),
            metadata=dict(mol_data.metadata),
            validate=True,
        )

    def to_molecular_data(self) -> MolecularData:
        """Convert ConformerData instance back to a MolecularData container [D].

        Returns
        -------
        MolecularData
            Converted MolecularData object.
        """
        return MolecularData(
            z=self.z.clone(),
            pos=self.pos.clone(),
            edge_index=self.edge_index.clone() if self.edge_index is not None else None,
            y=self.y.clone() if self.y is not None else None,
            x=self.x.clone() if self.x is not None else None,
            edge_attr=self.edge_attr.clone() if self.edge_attr is not None else None,
            weight=self.weight.clone() if self.weight is not None else None,
            forces=self.forces.clone() if self.forces is not None else None,
            dipole=self.dipole.clone() if self.dipole is not None else None,
            rotational_constants=(
                self.rotational_constants.clone()
                if self.rotational_constants is not None
                else None
            ),
            symbols=list(self.symbols) if self.symbols is not None else None,
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else {},
        )

    @classmethod
    def from_conformer_record(
        cls,
        record: ConformerRecord,
        atomic_numbers: Sequence[int],
        smiles: Optional[str] = None,
        cutoff: float = DEFAULT_GRAPH_CUTOFF_ANGSTROM,
        max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
    ) -> ConformerData:
        """Construct a ConformerData instance from a ConformerRecord [D].

        Parameters
        ----------
        record : ConformerRecord
            Conformer record from raw parsing.
        atomic_numbers : Sequence[int]
            Atomic numbers Z corresponding to atom positions.
        smiles : Optional[str]
            Canonical SMILES string.
        cutoff : float
            Interatomic distance neighborhood graph cutoff in Angstroms.
        max_neighbors : int
            Maximum neighbor edges per atom.

        Returns
        -------
        ConformerData
            Constructed ConformerData instance.
        """
        pos = torch.tensor(record.coords, dtype=torch.float32)
        z = torch.tensor(atomic_numbers, dtype=torch.long)

        edge_index, _ = build_radius_graph(pos, cutoff=cutoff, max_neighbors=max_neighbors)

        y = torch.tensor([record.energy], dtype=torch.float32) if record.energy is not None else None
        weight = (
            torch.tensor([record.boltzmann_weight], dtype=torch.float32)
            if record.boltzmann_weight is not None
            else torch.tensor([1.0], dtype=torch.float32)
        )
        forces = torch.tensor(record.forces, dtype=torch.float32) if record.forces is not None else None
        dipole = torch.tensor(record.dipole, dtype=torch.float32) if record.dipole is not None else None
        rot_consts = (
            torch.tensor(record.rotational_constants, dtype=torch.float32)
            if record.rotational_constants is not None
            else None
        )
        freqs = (
            torch.tensor(record.frequencies, dtype=torch.float32)
            if record.frequencies is not None
            else None
        )

        metadata = dict(record.metadata)
        metadata["relative_energy"] = record.relative_energy
        if record.qm_method:
            metadata["qm_method"] = record.qm_method

        return cls(
            z=z,
            pos=pos,
            edge_index=edge_index,
            y=y,
            weight=weight,
            forces=forces,
            dipole=dipole,
            rotational_constants=rot_consts,
            smiles=smiles,
            conformer_id=record.conformer_id,
            source_hash=record.source_hash,
            frequencies=freqs,
            s2_spin=record.s2_spin,
            metadata=metadata,
            validate=True,
        )

    def to_conformer_record(self, conformer_id: Optional[int] = None) -> ConformerRecord:
        """Convert ConformerData back to an immutable ConformerRecord [D].

        Parameters
        ----------
        conformer_id : Optional[int]
            Optional override for sequential conformer integer ID.

        Returns
        -------
        ConformerRecord
            Converted conformer record.
        """
        coords = self.pos.detach().cpu().numpy().astype(np.float64)
        y_tensor = getattr(self, "y", None)
        energy = float(y_tensor.item()) if y_tensor is not None and y_tensor.numel() > 0 else 0.0
        meta = self.metadata if getattr(self, "metadata", None) is not None else {}
        relative_energy = float(meta.get("relative_energy", 0.0))
        w_tensor = getattr(self, "weight", None)
        boltzmann_weight = float(w_tensor.item()) if w_tensor is not None and w_tensor.numel() > 0 else 1.0

        f_tensor = getattr(self, "forces", None)
        forces = f_tensor.detach().cpu().numpy().astype(np.float64) if f_tensor is not None else None
        d_tensor = getattr(self, "dipole", None)
        dipole = d_tensor.detach().cpu().numpy().astype(np.float64) if d_tensor is not None else None
        rc_tensor = getattr(self, "rotational_constants", None)
        rot_consts = (
            rc_tensor.detach().cpu().numpy().astype(np.float64)
            if rc_tensor is not None
            else None
        )
        freq_tensor = getattr(self, "frequencies", None)
        freqs = (
            freq_tensor.detach().cpu().numpy().astype(np.float64)
            if freq_tensor is not None
            else None
        )
        cid_val = getattr(self, "conformer_id", None)
        cid = conformer_id if conformer_id is not None else (cid_val if cid_val is not None else 0)

        return ConformerRecord(
            conformer_id=cid,
            coords=coords,
            energy=energy,
            relative_energy=relative_energy,
            boltzmann_weight=boltzmann_weight,
            forces=forces,
            dipole=dipole,
            rotational_constants=rot_consts,
            qm_method=meta.get("qm_method", None),
            source_hash=getattr(self, "source_hash", None),
            s2_spin=getattr(self, "s2_spin", None),
            frequencies=freqs,
            metadata=copy.deepcopy(meta),
        )

    @classmethod
    def from_xyz_file(
        cls,
        file_path: Union[str, Path],
        energy: Optional[float] = None,
        cutoff: float = DEFAULT_GRAPH_CUTOFF_ANGSTROM,
        max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
    ) -> ConformerData:
        """Parse an authentic Cartesian .xyz file into a validated ConformerData instance [M].

        Parameters
        ----------
        file_path : Union[str, Path]
            Path to the .xyz file.
        energy : Optional[float]
            Optional total energy in eV.
        cutoff : float
            Radial graph neighbor cutoff in Angstroms.
        max_neighbors : int
            Maximum incoming neighbors per atom.

        Returns
        -------
        ConformerData
            Validated ConformerData instance with SHA-256 provenance hash.
        """
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"XYZ file not found: {path}")

        sha256_hash = compute_file_sha256(path)

        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        if len(lines) < 3:
            raise ValueError(f"XYZ file {path} has fewer than 3 non-empty lines.")

        num_atoms = int(lines[0])
        comment = lines[1]

        symbols: List[str] = []
        atomic_numbers: List[int] = []
        coords: List[List[float]] = []

        for line_idx, line in enumerate(lines[2 : 2 + num_atoms]):
            tokens = line.split()
            if len(tokens) < 4:
                raise ValueError(f"Malformed coordinate line {line_idx + 3} in XYZ file: '{line}'")
            sym = tokens[0].capitalize()
            if sym not in SYMBOL_TO_ATOMIC_NUMBER:
                raise ValueError(f"Unrecognized chemical symbol '{sym}' on line {line_idx + 3}")
            z_val = SYMBOL_TO_ATOMIC_NUMBER[sym]
            x_val, y_val, z_pos = float(tokens[1]), float(tokens[2]), float(tokens[3])

            symbols.append(sym)
            atomic_numbers.append(z_val)
            coords.append([x_val, y_val, z_pos])

        pos_tensor = torch.tensor(coords, dtype=torch.float32)
        z_tensor = torch.tensor(atomic_numbers, dtype=torch.long)

        edge_index, _ = build_radius_graph(pos_tensor, cutoff=cutoff, max_neighbors=max_neighbors)

        y_tensor = torch.tensor([energy], dtype=torch.float32) if energy is not None else None

        metadata = {"xyz_comment": comment, "source_file": str(path)}

        return cls(
            z=z_tensor,
            pos=pos_tensor,
            edge_index=edge_index,
            y=y_tensor,
            symbols=symbols,
            source_hash=sha256_hash,
            metadata=metadata,
            validate=True,
        )


# ==============================================================================
# 3. Pure Functional Schema Utilities
# ==============================================================================


def rotate_conformer_data(
    data: ConformerData,
    matrix: Union[torch.Tensor, Sequence[Sequence[float]], np.ndarray],
) -> ConformerData:
    """Pure functional wrapper for ConformerData rotation [D]."""
    return data.rotate(matrix)


def translate_conformer_data(
    data: ConformerData,
    vector: Union[torch.Tensor, Sequence[float], np.ndarray],
) -> ConformerData:
    """Pure functional wrapper for ConformerData translation [D]."""
    return data.translate(vector)


def center_at_com_conformer_data(
    data: ConformerData,
    masses: Optional[Union[torch.Tensor, Sequence[float]]] = None,
) -> ConformerData:
    """Pure functional wrapper for ConformerData center-of-mass centering [D]."""
    return data.center_at_com(masses=masses)


def batch_conformer_data(data_list: Sequence[ConformerData]) -> Batch:
    """Collate a sequence of ConformerData objects into a unified PyG Batch [D].

    Parameters
    ----------
    data_list : Sequence[ConformerData]
        List or sequence of ConformerData instances.

    Returns
    -------
    torch_geometric.data.Batch
        Unified batched graph container.
    """
    return Batch.from_data_list(list(data_list))

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_geom\data\pyg_schema.py ---
"""CoChem-GEOM: PyTorch Geometric (PyG) Execution Tensor Schema.
=============================================================================
Defines the authoritative `ConformerData` tensor container subclassing
`torch_geometric.data.Data` for rotational spectroscopy, quantum chemistry,
and equivariant neural network architectures (EGNN, SchNet, DimeNet++, PaiNN).

Authoritative Standards:
- Method Matrix v4: Data Ingestion & Spectroscopic Graph Contracts
- SWEBOK v3 / ISO 25010 Software Quality Standards
- Mendeleev Library Mandate: Dynamic atomic mass & isotopic resolution (NEVER hardcoded)
- Cryptographic Provenance: SHA-256 checksum generation for structures and files
- SE(3) Equivariance & Invariance: Separation of spatial pos vs non-spatial node features
- State Immutability: Pure functional geometric transformations (immutable operations)
- Strict Zero-Mock Mandate: Authentic physical constants and real quantum chemical geometries
"""

from __future__ import annotations

import copy
import hashlib
import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from mendeleev import element
import numpy as np
import torch
from torch_geometric.data import Batch, Data

from cochem_geom.data.featurizer import (
    ATOMIC_NUMBER_TO_SYMBOL,
    DEFAULT_GRAPH_CUTOFF_ANGSTROM,
    DEFAULT_MAX_NEIGHBORS,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SYMBOL_TO_ATOMIC_NUMBER,
    MolecularData,
    build_radius_graph,
    compute_center_of_mass as base_compute_center_of_mass,
    compute_moment_of_inertia_tensor as base_compute_moment_of_inertia_tensor,
    compute_principal_rotational_constants as base_compute_principal_rotational_constants,
    get_atomic_mass,
    get_monoisotopic_mass,
)
from cochem_geom.data.geom_parser import (
    ConformerRecord,
    MoleculeRecord,
    compute_file_sha256,
    compute_structure_sha256,
)

logger = logging.getLogger("cochem_geom.data.pyg_schema")


# ==============================================================================
# 1. Validation Helpers and Error Definitions
# ==============================================================================


class SchemaValidationError(ValueError):
    """Raised when tensor shapes, types, or physical constraints are violated."""
    pass


def validate_conformer_data(data: ConformerData) -> None:
    """Perform fail-fast strict validation of ConformerData tensor schema [M]/[D].

    Validation rules:
    - `z`: 1D torch.Tensor of dtype `torch.long` or `torch.int64`, non-empty, non-negative.
    - `pos`: 2D torch.Tensor of shape `(N, 3)` of dtype `torch.float32`. float16/half is rejected.
    - `z.size(0) == pos.size(0)`: Number of atomic centers must match exactly.
    - `edge_index`: 2D torch.Tensor of shape `(2, E)` of dtype `torch.long` or `torch.int64`.
      Indices must satisfy `0 <= edge_index < N`.
    - `y`: Optional torch.Tensor of dtype `torch.float32`.
    - `weight`: Optional torch.Tensor of dtype `torch.float32`.
    - `x`: Optional 2D torch.Tensor of shape `(N, F)` of dtype `torch.float32`.
    - `edge_attr`: Optional 2D torch.Tensor of shape `(E, D)` of dtype `torch.float32`.
    - `forces`: Optional 2D torch.Tensor of shape `(N, 3)` of dtype `torch.float32`.
    - `dipole`: Optional torch.Tensor of shape `(3,)` or `(1, 3)` of dtype `torch.float32`.
    - `rotational_constants`: Optional torch.Tensor of shape `(3,)` or `(1, 3)` of dtype `torch.float32`.

    Parameters
    ----------
    data : ConformerData
        The ConformerData instance to validate.

    Raises
    ------
    TypeError
        If dtypes or non-tensor attributes violate specification.
    ValueError / SchemaValidationError
        If shapes, dimensions, or indexing bounds are invalid.
    """
    if not isinstance(data, (Data, ConformerData)):
        raise TypeError(f"Expected ConformerData or torch_geometric.data.Data, got {type(data)}")

    # 1. Validate z (Atomic Numbers)
    z_val = getattr(data, "z", None)
    if z_val is None:
        raise SchemaValidationError("ConformerData must contain atomic numbers tensor 'z'.")
    if not isinstance(z_val, torch.Tensor):
        raise TypeError(f"Attribute 'z' must be a torch.Tensor, got {type(z_val)}")
    if z_val.dim() != 1:
        raise SchemaValidationError(f"Attribute 'z' must be a 1D tensor of shape (N,), got shape {list(z_val.shape)}")
    if z_val.dtype not in (torch.int64, torch.long, torch.int32):
        raise TypeError(f"Attribute 'z' must have integer dtype (torch.long/int64), got {z_val.dtype}")
    if z_val.numel() == 0:
        raise SchemaValidationError("Attribute 'z' cannot be empty (N >= 1 required).")
    if (z_val <= 0).any():
        raise SchemaValidationError(f"All atomic numbers in 'z' must be positive integers, found <= 0 in {z_val.tolist()}")

    num_atoms = z_val.size(0)

    # 2. Validate pos (Cartesian Coordinates)
    pos_val = getattr(data, "pos", None)
    if pos_val is None:
        raise SchemaValidationError("ConformerData must contain Cartesian coordinates tensor 'pos'.")
    if not isinstance(pos_val, torch.Tensor):
        raise TypeError(f"Attribute 'pos' must be a torch.Tensor, got {type(pos_val)}")
    if pos_val.dtype in (torch.float16, torch.bfloat16):
        raise TypeError(
            f"ConformerData pos does not support reduced precision float16/bfloat16 ({pos_val.dtype}); "
            "float32 is required for physical and rotational coordinate precision."
        )
    if pos_val.dtype != torch.float32:
        raise TypeError(f"Attribute 'pos' must have dtype torch.float32, got {pos_val.dtype}")
    if pos_val.dim() != 2 or pos_val.size(1) != 3:
        raise SchemaValidationError(
            f"Attribute 'pos' must have shape (N, 3), got {list(pos_val.shape)}"
        )
    if pos_val.size(0) != num_atoms:
        raise SchemaValidationError(
            f"Atom count mismatch: z has {num_atoms} atoms but pos has {pos_val.size(0)} coordinates."
        )

    # 3. Validate edge_index (Graph Connectivity)
    edge_index_val = getattr(data, "edge_index", None)
    if edge_index_val is not None:
        if not isinstance(edge_index_val, torch.Tensor):
            raise TypeError(f"Attribute 'edge_index' must be a torch.Tensor, got {type(edge_index_val)}")
        if edge_index_val.dtype not in (torch.int64, torch.long, torch.int32):
            raise TypeError(f"Attribute 'edge_index' must have integer dtype (torch.long), got {edge_index_val.dtype}")
        if edge_index_val.dim() != 2 or edge_index_val.size(0) != 2:
            raise SchemaValidationError(
                f"Attribute 'edge_index' must have shape (2, E), got {list(edge_index_val.shape)}"
            )
        num_edges = edge_index_val.size(1)
        if num_edges > 0 and num_atoms > 0:
            max_idx = int(edge_index_val.max().item())
            min_idx = int(edge_index_val.min().item())
            if min_idx < 0:
                raise SchemaValidationError(f"Attribute 'edge_index' contains negative node index {min_idx}.")
            if max_idx >= num_atoms:
                raise SchemaValidationError(
                    f"Attribute 'edge_index' references node index {max_idx} >= num_atoms ({num_atoms})."
                )
    else:
        num_edges = 0

    # 4. Validate y (Target Property / Energy)
    y_val = getattr(data, "y", None)
    if y_val is not None:
        if not isinstance(y_val, torch.Tensor):
            raise TypeError(f"Attribute 'y' must be a torch.Tensor, got {type(y_val)}")
        if y_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'y' must have dtype torch.float32, got {y_val.dtype}")

    # 5. Validate weight (Statistical / Boltzmann Weight)
    w_val = getattr(data, "weight", None)
    if w_val is not None:
        if not isinstance(w_val, torch.Tensor):
            raise TypeError(f"Attribute 'weight' must be a torch.Tensor, got {type(w_val)}")
        if w_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'weight' must have dtype torch.float32, got {w_val.dtype}")

    # 6. Validate x (Node Invariant Features)
    x_val = getattr(data, "x", None)
    if x_val is not None:
        if not isinstance(x_val, torch.Tensor):
            raise TypeError(f"Attribute 'x' must be a torch.Tensor, got {type(x_val)}")
        if x_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'x' must have dtype torch.float32, got {x_val.dtype}")
        if x_val.dim() != 2 or x_val.size(0) != num_atoms:
            raise SchemaValidationError(
                f"Attribute 'x' must have shape (N, F) where N={num_atoms}, got {list(x_val.shape)}"
            )

    # 7. Validate edge_attr (Edge Feature Tensor)
    ea_val = getattr(data, "edge_attr", None)
    if ea_val is not None:
        if not isinstance(ea_val, torch.Tensor):
            raise TypeError(f"Attribute 'edge_attr' must be a torch.Tensor, got {type(ea_val)}")
        if ea_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'edge_attr' must have dtype torch.float32, got {ea_val.dtype}")
        if ea_val.dim() != 2 or ea_val.size(0) != num_edges:
            raise SchemaValidationError(
                f"Attribute 'edge_attr' must have shape (E, D) where E={num_edges}, got {list(ea_val.shape)}"
            )

    # 8. Validate forces (Cartesian Atomic Forces)
    f_val = getattr(data, "forces", None)
    if f_val is not None:
        if not isinstance(f_val, torch.Tensor):
            raise TypeError(f"Attribute 'forces' must be a torch.Tensor, got {type(f_val)}")
        if f_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'forces' must have dtype torch.float32, got {f_val.dtype}")
        if f_val.dim() != 2 or f_val.shape != pos_val.shape:
            raise SchemaValidationError(
                f"Attribute 'forces' must have shape {list(pos_val.shape)}, got {list(f_val.shape)}"
            )

    # 9. Validate dipole (Electric Dipole Vector)
    d_val = getattr(data, "dipole", None)
    if d_val is not None:
        if not isinstance(d_val, torch.Tensor):
            raise TypeError(f"Attribute 'dipole' must be a torch.Tensor, got {type(d_val)}")
        if d_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'dipole' must have dtype torch.float32, got {d_val.dtype}")
        if not ((d_val.dim() == 1 and d_val.size(0) == 3) or (d_val.dim() == 2 and d_val.shape == (1, 3))):
            raise SchemaValidationError(
                f"Attribute 'dipole' must have shape (3,) or (1, 3), got {list(d_val.shape)}"
            )

    # 10. Validate rotational_constants (A, B, C in MHz)
    rc_val = getattr(data, "rotational_constants", None)
    if rc_val is not None:
        if not isinstance(rc_val, torch.Tensor):
            raise TypeError(f"Attribute 'rotational_constants' must be a torch.Tensor, got {type(rc_val)}")
        if rc_val.dtype != torch.float32:
            raise TypeError(f"Attribute 'rotational_constants' must have dtype torch.float32, got {rc_val.dtype}")
        if not ((rc_val.dim() == 1 and rc_val.size(0) == 3) or (rc_val.dim() == 2 and rc_val.shape == (1, 3))):
            raise SchemaValidationError(
                f"Attribute 'rotational_constants' must have shape (3,) or (1, 3), got {list(rc_val.shape)}"
            )


def is_valid_conformer_data(data: Any) -> bool:
    """Return True if object is a fully valid ConformerData instance, False otherwise.

    Parameters
    ----------
    data : Any
        Object to inspect.

    Returns
    -------
    bool
        True if valid without exception, False otherwise.
    """
    try:
        validate_conformer_data(data)
        return True
    except (SchemaValidationError, TypeError, ValueError, AttributeError):
        return False


# ==============================================================================
# 2. ConformerData Tensor Schema Class
# ==============================================================================


class ConformerData(Data):
    """Authoritative PyTorch Geometric execution tensor container for molecular conformers.

    Inherits from `torch_geometric.data.Data`. Enforces float32 spatial coordinate precision,
    SE(3)-equivariant operations, dynamic Mendeleev mass calculations, and state immutability.

    Attributes
    ----------
    z : torch.Tensor
        Atomic numbers Z of shape (N,) with dtype torch.long.
    pos : torch.Tensor
        Spatial Cartesian coordinates in Angstroms of shape (N, 3) with dtype torch.float32.
    edge_index : torch.Tensor
        Graph connectivity edge indices of shape (2, E) with dtype torch.long.
    y : Optional[torch.Tensor]
        Scalar target ground-state electronic energy of shape (1,) with dtype torch.float32.
    x : Optional[torch.Tensor]
        Non-spatial invariant node features of shape (N, F) with dtype torch.float32.
    edge_attr : Optional[torch.Tensor]
        Edge feature attributes (e.g. RBF distances) of shape (E, D) with dtype torch.float32.
    weight : torch.Tensor
        Statistical or Boltzmann thermodynamic weighting factor of shape (1,) with dtype torch.float32.
    forces : Optional[torch.Tensor]
        Spatial gradient forces of shape (N, 3) with dtype torch.float32.
    dipole : Optional[torch.Tensor]
        Electric dipole moment vector of shape (3,) with dtype torch.float32.
    rotational_constants : Optional[torch.Tensor]
        Principal spectroscopic rotational constants (A, B, C) in MHz of shape (3,) with dtype torch.float32.
    symbols : List[str]
        IUPAC chemical symbols of length N.
    smiles : Optional[str]
        Canonical SMILES string representation.
    conformer_id : Optional[int]
        Sequential conformer index within the molecular ensemble.
    source_hash : Optional[str]
        Cryptographic SHA-256 provenance checksum of the calculation source or file.
    frequencies : Optional[torch.Tensor]
        Harmonic vibrational frequencies in cm^-1 of shape (M,) with dtype torch.float32.
    s2_spin : Optional[float]
        Spin angular momentum expectation value <S^2>.
    metadata : Dict[str, Any]
        Arbitrary user and provenance metadata dictionary.
    """

    def __init__(
        self,
        z: Optional[torch.Tensor] = None,
        pos: Optional[torch.Tensor] = None,
        edge_index: Optional[torch.Tensor] = None,
        y: Optional[torch.Tensor] = None,
        x: Optional[torch.Tensor] = None,
        edge_attr: Optional[torch.Tensor] = None,
        weight: Optional[torch.Tensor] = None,
        forces: Optional[torch.Tensor] = None,
        dipole: Optional[torch.Tensor] = None,
        rotational_constants: Optional[torch.Tensor] = None,
        symbols: Optional[List[str]] = None,
        smiles: Optional[str] = None,
        conformer_id: Optional[int] = None,
        source_hash: Optional[str] = None,
        frequencies: Optional[torch.Tensor] = None,
        s2_spin: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        validate: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            x=x,
            edge_index=edge_index,
            edge_attr=edge_attr,
            y=y,
            pos=pos,
            z=z,
            **kwargs,
        )

        if z is not None:
            self.z = z
        if pos is not None:
            self.pos = pos
        if edge_index is not None:
            self.edge_index = edge_index
        elif not hasattr(self, "edge_index") or self.edge_index is None:
            self.edge_index = torch.empty((2, 0), dtype=torch.long, device=pos.device if pos is not None else None)

        if y is not None:
            self.y = y
        if x is not None:
            self.x = x
        if edge_attr is not None:
            self.edge_attr = edge_attr

        self.weight = (
            weight
            if weight is not None
            else torch.tensor([1.0], dtype=torch.float32, device=pos.device if pos is not None else None)
        )

        if forces is not None:
            self.forces = forces
        if dipole is not None:
            self.dipole = dipole
        if rotational_constants is not None:
            self.rotational_constants = rotational_constants

        if symbols is not None:
            self.symbols = list(symbols)
        elif z is not None:
            self.symbols = [ATOMIC_NUMBER_TO_SYMBOL.get(int(zi.item()), "X") for zi in z]
        else:
            self.symbols = []

        if smiles is not None:
            self.smiles = smiles
        if conformer_id is not None:
            self.conformer_id = conformer_id
        if source_hash is not None:
            self.source_hash = source_hash
        if frequencies is not None:
            self.frequencies = frequencies
        if s2_spin is not None:
            self.s2_spin = s2_spin

        self.metadata = dict(metadata) if metadata is not None else {}

        if validate and z is not None and pos is not None:
            validate_conformer_data(self)

    # --------------------------------------------------------------------------
    # Fallback Property Resolution for PyG GlobalStorage
    # --------------------------------------------------------------------------

    def __getattr__(self, key: str) -> Any:
        """Safe attribute access returning None for unassigned optional fields."""
        try:
            return super().__getattr__(key)
        except AttributeError:
            if key in (
                "forces",
                "dipole",
                "rotational_constants",
                "frequencies",
                "s2_spin",
                "conformer_id",
                "source_hash",
                "smiles",
                "y",
                "x",
                "edge_attr",
                "edge_index",
                "z",
                "pos",
                "symbols",
                "metadata",
                "weight",
            ):
                return None
            raise

    # --------------------------------------------------------------------------
    # PyG Batching Increment Override
    # --------------------------------------------------------------------------

    def __inc__(self, key: str, value: Any, *args: Any, **kwargs: Any) -> Any:
        """Override PyG index incrementing during mini-batch concatenation.

        For `edge_index`, returns `self.z.size(0)` (the total number of node centers)
        so that edges across separate graphs in a batch are correctly offset.
        """
        if key == "edge_index":
            if self.z is not None:
                return self.z.size(0)
            if self.pos is not None:
                return self.pos.size(0)
            return self.num_nodes
        return super().__inc__(key, value, *args, **kwargs)

    # --------------------------------------------------------------------------
    # Pure Functional SE(3) Transformations (State Immutability Guaranteed)
    # --------------------------------------------------------------------------

    def translate(
        self, vector: Union[torch.Tensor, Sequence[float], np.ndarray]
    ) -> ConformerData:
        """Translate Cartesian coordinates immutably by translation vector T [D].

        Under spatial translation $\\mathbf{r}' = \\mathbf{r} + \\mathbf{T}$:
        - `pos` translates equivariantly.
        - `forces` are invariant (internal gradients remain identical).
        - `y`, `weight`, `rotational_constants` are invariant.
        - `dipole` is invariant for neutral molecules.

        Parameters
        ----------
        vector : Union[torch.Tensor, Sequence[float], np.ndarray]
            3D translation vector of shape (3,).

        Returns
        -------
        ConformerData
            A new ConformerData instance with translated coordinates.
        """
        if isinstance(vector, torch.Tensor):
            t_vec = vector.to(dtype=self.pos.dtype, device=self.pos.device)
        else:
            t_vec = torch.tensor(vector, dtype=self.pos.dtype, device=self.pos.device)

        if t_vec.shape != (3,) and t_vec.shape != (1, 3):
            raise ValueError(f"Translation vector must have shape (3,) or (1, 3), got {list(t_vec.shape)}")

        new_pos = self.pos + t_vec.squeeze()

        return ConformerData(
            z=self.z.clone() if self.z is not None else None,
            pos=new_pos,
            edge_index=self.edge_index.clone() if self.edge_index is not None else None,
            y=self.y.clone() if self.y is not None else None,
            x=self.x.clone() if self.x is not None else None,
            edge_attr=self.edge_attr.clone() if self.edge_attr is not None else None,
            weight=self.weight.clone() if self.weight is not None else None,
            forces=self.forces.clone() if self.forces is not None else None,
            dipole=self.dipole.clone() if self.dipole is not None else None,
            rotational_constants=(
                self.rotational_constants.clone()
                if self.rotational_constants is not None
                else None
            ),
            symbols=list(self.symbols) if self.symbols is not None else None,
            smiles=self.smiles,
            conformer_id=self.conformer_id,
            source_hash=self.source_hash,
            frequencies=self.frequencies.clone() if self.frequencies is not None else None,
            s2_spin=self.s2_spin,
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else {},
            validate=False,
        )

    def rotate(
        self, matrix: Union[torch.Tensor, Sequence[Sequence[float]], np.ndarray]
    ) -> ConformerData:
        """Rotate Cartesian coordinates, forces, and dipole immutably via SO(3) matrix R [D].

        Under 3D rotation $\\mathbf{r}' = \\mathbf{R} \\mathbf{r}$:
        - `pos` rotates equivariantly: $\\text{pos}' = \\text{pos} \\mathbf{R}^T$.
        - `forces` rotate equivariantly: $\\text{forces}' = \\text{forces} \\mathbf{R}^T$.
        - `dipole` rotates equivariantly: $\\boldsymbol{\\mu}' = \\boldsymbol{\\mu} \\mathbf{R}^T$.
        - `y`, `weight`, `rotational_constants` are scalar SO(3) invariants.

        Parameters
        ----------
        matrix : Union[torch.Tensor, Sequence[Sequence[float]], np.ndarray]
            3x3 orthogonal rotation matrix R.

        Returns
        -------
        ConformerData
            A new ConformerData instance with rotated geometric properties.
        """
        if isinstance(matrix, torch.Tensor):
            rot_mat = matrix.to(dtype=self.pos.dtype, device=self.pos.device)
        else:
            rot_mat = torch.tensor(matrix, dtype=self.pos.dtype, device=self.pos.device)

        if rot_mat.shape != (3, 3):
            raise ValueError(f"Rotation matrix must have shape (3, 3), got {list(rot_mat.shape)}")

        # Equivariant rotation: pos' = pos @ R^T
        new_pos = torch.matmul(self.pos, rot_mat.t())

        # Equivariant forces rotation if present
        new_forces = (
            torch.matmul(self.forces, rot_mat.t())
            if self.forces is not None
            else None
        )

        # Equivariant dipole rotation if present
        if self.dipole is not None:
            if self.dipole.dim() == 1:
                new_dipole = torch.matmul(rot_mat, self.dipole)
            else:
                new_dipole = torch.matmul(self.dipole, rot_mat.t())
        else:
            new_dipole = None

        return ConformerData(
            z=self.z.clone() if self.z is not None else None,
            pos=new_pos,
            edge_index=self.edge_index.clone() if self.edge_index is not None else None,
            y=self.y.clone() if self.y is not None else None,
            x=self.x.clone() if self.x is not None else None,
            edge_attr=self.edge_attr.clone() if self.edge_attr is not None else None,
            weight=self.weight.clone() if self.weight is not None else None,
            forces=new_forces,
            dipole=new_dipole,
            rotational_constants=(
                self.rotational_constants.clone()
                if self.rotational_constants is not None
                else None
            ),
            symbols=list(self.symbols) if self.symbols is not None else None,
            smiles=self.smiles,
            conformer_id=self.conformer_id,
            source_hash=self.source_hash,
            frequencies=self.frequencies.clone() if self.frequencies is not None else None,
            s2_spin=self.s2_spin,
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else {},
            validate=False,
        )

    # --------------------------------------------------------------------------
    # Center of Mass and Spectroscopic Tensor Calculations
    # --------------------------------------------------------------------------

    def center_of_mass(
        self, masses: Optional[Union[torch.Tensor, Sequence[float]]] = None
    ) -> torch.Tensor:
        """Compute Center of Mass (COM) coordinates in Angstroms [D].

        Dynamically queries standard atomic weights from the Mendeleev database
        if `masses` is omitted.

        $$\\mathbf{r}_{\\text{COM}} = \\frac{\\sum_{i=1}^N m_i \\mathbf{r}_i}{\\sum_{i=1}^N m_i}$$

        Parameters
        ----------
        masses : Optional[Union[torch.Tensor, Sequence[float]]]
            Optional explicit mass array of shape (N,).

        Returns
        -------
        torch.Tensor
            Center of mass vector of shape (3,) with dtype torch.float32.
        """
        if masses is not None:
            if isinstance(masses, torch.Tensor):
                m_tensor = masses.to(dtype=self.pos.dtype, device=self.pos.device)
            else:
                m_tensor = torch.tensor(masses, dtype=self.pos.dtype, device=self.pos.device)
        else:
            # Dynamic Mendeleev resolution (NEVER hardcoded)
            m_list = [get_atomic_mass(int(zi.item())) for zi in self.z]
            m_tensor = torch.tensor(m_list, dtype=self.pos.dtype, device=self.pos.device)

        if m_tensor.dim() == 1:
            m_tensor = m_tensor.unsqueeze(-1)

        total_mass = m_tensor.sum()
        if total_mass <= 0.0:
            raise ValueError(f"Total molecular mass must be positive, got {total_mass.item()}")

        com = (self.pos * m_tensor).sum(dim=0) / total_mass
        return com.squeeze()

    def center_at_com(
        self, masses: Optional[Union[torch.Tensor, Sequence[float]]] = None
    ) -> ConformerData:
        """Return a new ConformerData centered at the molecular Center of Mass [D].

        State immutability: returns a fresh instance without mutating current coordinates.

        Parameters
        ----------
        masses : Optional[Union[torch.Tensor, Sequence[float]]]
            Optional explicit atomic mass vector.

        Returns
        -------
        ConformerData
            A new ConformerData instance centered at COM.
        """
        com = self.center_of_mass(masses=masses)
        return self.translate(-com)

    def compute_moment_of_inertia_tensor(
        self, masses: Optional[Union[torch.Tensor, Sequence[float]]] = None
    ) -> torch.Tensor:
        """Construct the 3x3 Moment of Inertia tensor in the COM frame [D].

        $$I_{\\alpha \\ beta} = \\sum_{i=1}^N m_i \\left( r_i'^2 \\delta_{\\alpha \\beta} - r'_{i,\\alpha} r'_{i,\\beta} \\right)$$

        where $\\mathbf{r}'_i = \\mathbf{r}_i - \\mathbf{r}_{\\text{COM}}$ in units of $u \\cdot \\text{\\AA}^2$.

        Parameters
        ----------
        masses : Optional[Union[torch.Tensor, Sequence[float]]]
            Atomic masses in Daltons. Queries Mendeleev dynamically if None.

        Returns
        -------
        torch.Tensor
            Moment of inertia tensor of shape (3, 3) with dtype torch.float32.
        """
        if masses is not None:
            if isinstance(masses, torch.Tensor):
                m = masses.to(dtype=self.pos.dtype, device=self.pos.device)
            else:
                m = torch.tensor(masses, dtype=self.pos.dtype, device=self.pos.device)
        else:
            m_list = [get_atomic_mass(int(zi.item())) for zi in self.z]
            m = torch.tensor(m_list, dtype=self.pos.dtype, device=self.pos.device)

        com = self.center_of_mass(masses=m)
        rel_pos = self.pos - com.unsqueeze(0)

        x = rel_pos[:, 0]
        y = rel_pos[:, 1]
        z = rel_pos[:, 2]

        ixx = (m * (y**2 + z**2)).sum()
        iyy = (m * (x**2 + z**2)).sum()
        izz = (m * (x**2 + y**2)).sum()

        ixy = -(m * x * y).sum()
        ixz = -(m * x * z).sum()
        iyz = -(m * y * z).sum()

        inertia = torch.tensor(
            [
                [ixx, ixy, ixz],
                [ixy, iyy, iyz],
                [ixz, iyz, izz],
            ],
            dtype=self.pos.dtype,
            device=self.pos.device,
        )
        return inertia

    def compute_principal_rotational_constants(
        self, masses: Optional[Union[torch.Tensor, Sequence[float]]] = None
    ) -> torch.Tensor:
        """Compute principal spectroscopic rotational constants (A, B, C) in MHz [D].

        Rotational constant factor: $h / (8 \\pi^2) = 505379.008784\\text{ MHz} \\cdot u \\cdot \\text{\\AA}^2$.
        Eigenvalues sorted such that $I_a \\le I_b \\le I_c$, yielding $A \\ge B \\ge C$.

        Parameters
        ----------
        masses : Optional[Union[torch.Tensor, Sequence[float]]]
            Atomic masses in Daltons. Queries Mendeleev dynamically if None.

        Returns
        -------
        torch.Tensor
            Rotational constants tensor of shape (3,) in MHz: [A, B, C].
        """
        inertia = self.compute_moment_of_inertia_tensor(masses=masses)
        eigenvalues = torch.linalg.eigvalsh(inertia)
        eigenvalues, _ = torch.sort(eigenvalues)

        ia = float(eigenvalues[0].item())
        ib = float(eigenvalues[1].item())
        ic = float(eigenvalues[2].item())

        a_const = float(ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / ia) if ia > 1e-6 else 0.0
        b_const = float(ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / ib) if ib > 1e-6 else 0.0
        c_const = float(ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / ic) if ic > 1e-6 else 0.0

        return torch.tensor([a_const, b_const, c_const], dtype=torch.float32, device=self.pos.device)

    # --------------------------------------------------------------------------
    # Inter-Schema Conversions (MolecularData & ConformerRecord)
    # --------------------------------------------------------------------------

    @classmethod
    def from_molecular_data(cls, mol_data: MolecularData) -> ConformerData:
        """Construct a ConformerData instance from a MolecularData container [D].

        Parameters
        ----------
        mol_data : MolecularData
            Source MolecularData object.

        Returns
        -------
        ConformerData
            Converted ConformerData instance.
        """
        pos = mol_data.pos.to(dtype=torch.float32)
        z = mol_data.z.to(dtype=torch.long)
        edge_index = mol_data.edge_index.to(dtype=torch.long) if mol_data.edge_index is not None else None
        y = mol_data.y.to(dtype=torch.float32) if mol_data.y is not None else None
        x = mol_data.x.to(dtype=torch.float32) if mol_data.x is not None else None
        edge_attr = mol_data.edge_attr.to(dtype=torch.float32) if mol_data.edge_attr is not None else None
        weight = mol_data.weight.to(dtype=torch.float32) if mol_data.weight is not None else None
        forces = mol_data.forces.to(dtype=torch.float32) if mol_data.forces is not None else None
        dipole = mol_data.dipole.to(dtype=torch.float32) if mol_data.dipole is not None else None
        rotational_constants = (
            mol_data.rotational_constants.to(dtype=torch.float32)
            if mol_data.rotational_constants is not None
            else None
        )

        return cls(
            z=z,
            pos=pos,
            edge_index=edge_index,
            y=y,
            x=x,
            edge_attr=edge_attr,
            weight=weight,
            forces=forces,
            dipole=dipole,
            rotational_constants=rotational_constants,
            symbols=list(mol_data.symbols),
            metadata=dict(mol_data.metadata),
            validate=True,
        )

    def to_molecular_data(self) -> MolecularData:
        """Convert ConformerData instance back to a MolecularData container [D].

        Returns
        -------
        MolecularData
            Converted MolecularData object.
        """
        return MolecularData(
            z=self.z.clone(),
            pos=self.pos.clone(),
            edge_index=self.edge_index.clone() if self.edge_index is not None else None,
            y=self.y.clone() if self.y is not None else None,
            x=self.x.clone() if self.x is not None else None,
            edge_attr=self.edge_attr.clone() if self.edge_attr is not None else None,
            weight=self.weight.clone() if self.weight is not None else None,
            forces=self.forces.clone() if self.forces is not None else None,
            dipole=self.dipole.clone() if self.dipole is not None else None,
            rotational_constants=(
                self.rotational_constants.clone()
                if self.rotational_constants is not None
                else None
            ),
            symbols=list(self.symbols) if self.symbols is not None else None,
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else {},
        )

    @classmethod
    def from_conformer_record(
        cls,
        record: ConformerRecord,
        atomic_numbers: Sequence[int],
        smiles: Optional[str] = None,
        cutoff: float = DEFAULT_GRAPH_CUTOFF_ANGSTROM,
        max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
    ) -> ConformerData:
        """Construct a ConformerData instance from a ConformerRecord [D].

        Parameters
        ----------
        record : ConformerRecord
            Conformer record from raw parsing.
        atomic_numbers : Sequence[int]
            Atomic numbers Z corresponding to atom positions.
        smiles : Optional[str]
            Canonical SMILES string.
        cutoff : float
            Interatomic distance neighborhood graph cutoff in Angstroms.
        max_neighbors : int
            Maximum neighbor edges per atom.

        Returns
        -------
        ConformerData
            Constructed ConformerData instance.
        """
        pos = torch.tensor(record.coords, dtype=torch.float32)
        z = torch.tensor(atomic_numbers, dtype=torch.long)

        edge_index, _ = build_radius_graph(pos, cutoff=cutoff, max_neighbors=max_neighbors)

        y = torch.tensor([record.energy], dtype=torch.float32) if record.energy is not None else None
        weight = (
            torch.tensor([record.boltzmann_weight], dtype=torch.float32)
            if record.boltzmann_weight is not None
            else torch.tensor([1.0], dtype=torch.float32)
        )
        forces = torch.tensor(record.forces, dtype=torch.float32) if record.forces is not None else None
        dipole = torch.tensor(record.dipole, dtype=torch.float32) if record.dipole is not None else None
        rot_consts = (
            torch.tensor(record.rotational_constants, dtype=torch.float32)
            if record.rotational_constants is not None
            else None
        )
        freqs = (
            torch.tensor(record.frequencies, dtype=torch.float32)
            if record.frequencies is not None
            else None
        )

        metadata = dict(record.metadata)
        metadata["relative_energy"] = record.relative_energy
        if record.qm_method:
            metadata["qm_method"] = record.qm_method

        return cls(
            z=z,
            pos=pos,
            edge_index=edge_index,
            y=y,
            weight=weight,
            forces=forces,
            dipole=dipole,
            rotational_constants=rot_consts,
            smiles=smiles,
            conformer_id=record.conformer_id,
            source_hash=record.source_hash,
            frequencies=freqs,
            s2_spin=record.s2_spin,
            metadata=metadata,
            validate=True,
        )

    def to_conformer_record(self, conformer_id: Optional[int] = None) -> ConformerRecord:
        """Convert ConformerData back to an immutable ConformerRecord [D].

        Parameters
        ----------
        conformer_id : Optional[int]
            Optional override for sequential conformer integer ID.

        Returns
        -------
        ConformerRecord
            Converted conformer record.
        """
        coords = self.pos.detach().cpu().numpy().astype(np.float64)
        y_tensor = getattr(self, "y", None)
        energy = float(y_tensor.item()) if y_tensor is not None and y_tensor.numel() > 0 else 0.0
        meta = self.metadata if getattr(self, "metadata", None) is not None else {}
        relative_energy = float(meta.get("relative_energy", 0.0))
        w_tensor = getattr(self, "weight", None)
        boltzmann_weight = float(w_tensor.item()) if w_tensor is not None and w_tensor.numel() > 0 else 1.0

        f_tensor = getattr(self, "forces", None)
        forces = f_tensor.detach().cpu().numpy().astype(np.float64) if f_tensor is not None else None
        d_tensor = getattr(self, "dipole", None)
        dipole = d_tensor.detach().cpu().numpy().astype(np.float64) if d_tensor is not None else None
        rc_tensor = getattr(self, "rotational_constants", None)
        rot_consts = (
            rc_tensor.detach().cpu().numpy().astype(np.float64)
            if rc_tensor is not None
            else None
        )
        freq_tensor = getattr(self, "frequencies", None)
        freqs = (
            freq_tensor.detach().cpu().numpy().astype(np.float64)
            if freq_tensor is not None
            else None
        )
        cid_val = getattr(self, "conformer_id", None)
        cid = conformer_id if conformer_id is not None else (cid_val if cid_val is not None else 0)

        return ConformerRecord(
            conformer_id=cid,
            coords=coords,
            energy=energy,
            relative_energy=relative_energy,
            boltzmann_weight=boltzmann_weight,
            forces=forces,
            dipole=dipole,
            rotational_constants=rot_consts,
            qm_method=meta.get("qm_method", None),
            source_hash=getattr(self, "source_hash", None),
            s2_spin=getattr(self, "s2_spin", None),
            frequencies=freqs,
            metadata=copy.deepcopy(meta),
        )

    @classmethod
    def from_xyz_file(
        cls,
        file_path: Union[str, Path],
        energy: Optional[float] = None,
        cutoff: float = DEFAULT_GRAPH_CUTOFF_ANGSTROM,
        max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
    ) -> ConformerData:
        """Parse an authentic Cartesian .xyz file into a validated ConformerData instance [M].

        Parameters
        ----------
        file_path : Union[str, Path]
            Path to the .xyz file.
        energy : Optional[float]
            Optional total energy in eV.
        cutoff : float
            Radial graph neighbor cutoff in Angstroms.
        max_neighbors : int
            Maximum incoming neighbors per atom.

        Returns
        -------
        ConformerData
            Validated ConformerData instance with SHA-256 provenance hash.
        """
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"XYZ file not found: {path}")

        sha256_hash = compute_file_sha256(path)

        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        if len(lines) < 3:
            raise ValueError(f"XYZ file {path} has fewer than 3 non-empty lines.")

        num_atoms = int(lines[0])
        comment = lines[1]

        symbols: List[str] = []
        atomic_numbers: List[int] = []
        coords: List[List[float]] = []

        for line_idx, line in enumerate(lines[2 : 2 + num_atoms]):
            tokens = line.split()
            if len(tokens) < 4:
                raise ValueError(f"Malformed coordinate line {line_idx + 3} in XYZ file: '{line}'")
            sym = tokens[0].capitalize()
            if sym not in SYMBOL_TO_ATOMIC_NUMBER:
                raise ValueError(f"Unrecognized chemical symbol '{sym}' on line {line_idx + 3}")
            z_val = SYMBOL_TO_ATOMIC_NUMBER[sym]
            x_val, y_val, z_pos = float(tokens[1]), float(tokens[2]), float(tokens[3])

            symbols.append(sym)
            atomic_numbers.append(z_val)
            coords.append([x_val, y_val, z_pos])

        pos_tensor = torch.tensor(coords, dtype=torch.float32)
        z_tensor = torch.tensor(atomic_numbers, dtype=torch.long)

        edge_index, _ = build_radius_graph(pos_tensor, cutoff=cutoff, max_neighbors=max_neighbors)

        y_tensor = torch.tensor([energy], dtype=torch.float32) if energy is not None else None

        metadata = {"xyz_comment": comment, "source_file": str(path)}

        return cls(
            z=z_tensor,
            pos=pos_tensor,
            edge_index=edge_index,
            y=y_tensor,
            symbols=symbols,
            source_hash=sha256_hash,
            metadata=metadata,
            validate=True,
        )


# ==============================================================================
# 3. Pure Functional Schema Utilities
# ==============================================================================


def rotate_conformer_data(
    data: ConformerData,
    matrix: Union[torch.Tensor, Sequence[Sequence[float]], np.ndarray],
) -> ConformerData:
    """Pure functional wrapper for ConformerData rotation [D]."""
    return data.rotate(matrix)


def translate_conformer_data(
    data: ConformerData,
    vector: Union[torch.Tensor, Sequence[float], np.ndarray],
) -> ConformerData:
    """Pure functional wrapper for ConformerData translation [D]."""
    return data.translate(vector)


def center_at_com_conformer_data(
    data: ConformerData,
    masses: Optional[Union[torch.Tensor, Sequence[float]]] = None,
) -> ConformerData:
    """Pure functional wrapper for ConformerData center-of-mass centering [D]."""
    return data.center_at_com(masses=masses)


def batch_conformer_data(data_list: Sequence[ConformerData]) -> Batch:
    """Collate a sequence of ConformerData objects into a unified PyG Batch [D].

    Parameters
    ----------
    data_list : Sequence[ConformerData]
        List or sequence of ConformerData instances.

    Returns
    -------
    torch_geometric.data.Batch
        Unified batched graph container.
    """
    return Batch.from_data_list(list(data_list))

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_pyg_schema.py ---
"""Tests for CoChem-GEOM PyTorch Geometric (PyG) Execution Tensor Schema.
=============================================================================
Comprehensive unit and integration test suite validating `ConformerData` and schema utilities.

Authoritative Standards:
- Method Matrix v4: Data Ingestion & Spectroscopic Graph Contracts
- SWEBOK v3 / ISO 25010 Software Quality Standards
- Mendeleev Library Mandate: Dynamic atomic mass & isotopic resolution (NEVER hardcoded)
- Cryptographic Provenance: SHA-256 checksum generation for structures and files
- SE(3) Equivariance & Invariance: Separation of spatial pos vs non-spatial features
- State Immutability: Pure functional transformations
- Strict Zero-Mock Mandate: Authentic physical constants and real quantum chemical geometries
"""

from __future__ import annotations

import math
import os
from pathlib import Path
import tempfile
import pytest

from mendeleev import element
import numpy as np
import torch
from torch_geometric.data import Batch, Data
from torch_geometric.loader import DataLoader

from cochem_geom.data.featurizer import (
    ATOMIC_NUMBER_TO_SYMBOL,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SYMBOL_TO_ATOMIC_NUMBER,
    MolecularData,
    build_radius_graph,
    get_atomic_mass,
    get_monoisotopic_mass,
)
from cochem_geom.data.geom_parser import (
    ConformerRecord,
    MoleculeRecord,
    compute_file_sha256,
    compute_structure_sha256,
)
from cochem_geom.data.pyg_schema import (
    ConformerData,
    SchemaValidationError,
    batch_conformer_data,
    center_at_com_conformer_data,
    is_valid_conformer_data,
    rotate_conformer_data,
    translate_conformer_data,
    validate_conformer_data,
)


# ==============================================================================
# Authentic Molecular Test Geometries (Zero-Mock Policy)
# ==============================================================================

# Water (H2O, C2v) - Experimental Ground State Geometry (Angstroms)
WATER_SYMBOLS = ["O", "H", "H"]
WATER_Z = [8, 1, 1]
WATER_POS = [
    [0.000000, 0.000000, 0.117300],
    [0.000000, 0.757200, -0.469200],
    [0.000000, -0.757200, -0.469200],
]
WATER_ENERGY_EV = -2079.35  # ~ -76.4 Hartree
WATER_DIPOLE = [0.0, 0.0, 1.8546]  # Debye (along z-axis)

# Methane (CH4, Td) - Ground State Geometry (Angstroms)
METHANE_SYMBOLS = ["C", "H", "H", "H", "H"]
METHANE_Z = [6, 1, 1, 1, 1]
METHANE_POS = [
    [0.000000, 0.000000, 0.000000],
    [0.629118, 0.629118, 0.629118],
    [-0.629118, -0.629118, 0.629118],
    [-0.629118, 0.629118, -0.629118],
    [0.629118, -0.629118, -0.629118],
]
METHANE_ENERGY_EV = -1098.24

# Formaldehyde (H2CO, C2v) - Ground State Geometry (Angstroms)
FORMALDEHYDE_SYMBOLS = ["C", "O", "H", "H"]
FORMALDEHYDE_Z = [6, 8, 1, 1]
FORMALDEHYDE_POS = [
    [0.000000, 0.000000, -0.537500],
    [0.000000, 0.000000, 0.665500],
    [0.000000, 0.935000, -1.112500],
    [0.000000, -0.935000, -1.112500],
]
FORMALDEHYDE_ENERGY_EV = -3105.12


def create_rotation_matrix_3d(alpha: float, beta: float, gamma: float) -> torch.Tensor:
    """Generate an authentic 3D SO(3) Euler angle rotation matrix R = Rz(gamma) * Ry(beta) * Rx(alpha)."""
    ca, sa = math.cos(alpha), math.sin(alpha)
    cb, sb = math.cos(beta), math.sin(beta)
    cg, sg = math.cos(gamma), math.sin(gamma)

    rx = np.array([[1, 0, 0], [0, ca, -sa], [0, sa, ca]], dtype=np.float32)
    ry = np.array([[cb, 0, sb], [0, 1, 0], [-sb, 0, cb]], dtype=np.float32)
    rz = np.array([[cg, -sg, 0], [sg, cg, 0], [0, 0, 1]], dtype=np.float32)

    r_mat = rz @ ry @ rx
    return torch.tensor(r_mat, dtype=torch.float32)


# ==============================================================================
# 1. Fail-Fast Strict Validation Tests
# ==============================================================================


class TestValidationFailFast:
    """Tests fail-fast rejection of malformed shapes, types, dtypes, and bounds."""

    def test_valid_conformer_data_passes(self) -> None:
        """Valid ConformerData instantiation must pass validation cleanly."""
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
            y=torch.tensor([WATER_ENERGY_EV], dtype=torch.float32),
            dipole=torch.tensor(WATER_DIPOLE, dtype=torch.float32),
            weight=torch.tensor([1.0], dtype=torch.float32),
        )
        assert is_valid_conformer_data(data) is True
        validate_conformer_data(data)
        assert data.num_nodes == 3

    def test_rejection_of_float16_pos(self) -> None:
        """float16 coordinates must be strictly rejected due to insufficient precision."""
        with pytest.raises(TypeError, match="float16"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float16),
            )

    def test_rejection_of_bfloat16_pos(self) -> None:
        """bfloat16 coordinates must be strictly rejected."""
        with pytest.raises(TypeError, match="bfloat16"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.bfloat16),
            )

    def test_rejection_of_non_float32_pos(self) -> None:
        """pos with dtype double/float64 or int must raise TypeError."""
        with pytest.raises(TypeError, match="torch.float32"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float64),
            )

    def test_rejection_of_z_pos_count_mismatch(self) -> None:
        """Mismatch between atom count in z and pos must raise SchemaValidationError."""
        with pytest.raises((ValueError, SchemaValidationError), match="Atom count mismatch"):
            ConformerData(
                z=torch.tensor([8, 1], dtype=torch.long),  # 2 atoms
                pos=torch.tensor(WATER_POS, dtype=torch.float32),  # 3 atoms
            )

    def test_rejection_of_invalid_pos_shape(self) -> None:
        """pos tensor with shape other than (N, 3) must raise SchemaValidationError."""
        with pytest.raises((ValueError, SchemaValidationError), match="shape"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor([[0.0, 1.0], [2.0, 3.0], [4.0, 5.0]], dtype=torch.float32),
            )

    def test_rejection_of_invalid_edge_index_shape(self) -> None:
        """edge_index not of shape (2, E) must raise SchemaValidationError."""
        with pytest.raises((ValueError, SchemaValidationError), match="edge_index"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                edge_index=torch.tensor([[0, 1, 2]], dtype=torch.long),  # (1, 3) instead of (2, E)
            )

    def test_rejection_of_edge_index_out_of_bounds(self) -> None:
        """edge_index referencing atom index >= N must raise SchemaValidationError."""
        with pytest.raises((ValueError, SchemaValidationError), match="references node index"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),  # N=3 atoms (indices 0, 1, 2)
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                edge_index=torch.tensor([[0, 5], [1, 0]], dtype=torch.long),  # index 5 >= 3
            )

    def test_rejection_of_edge_index_negative_index(self) -> None:
        """edge_index containing negative indices must raise SchemaValidationError."""
        with pytest.raises((ValueError, SchemaValidationError), match="negative node index"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                edge_index=torch.tensor([[-1, 0], [0, 1]], dtype=torch.long),
            )

    def test_rejection_of_non_float32_y(self) -> None:
        """Non-float32 target property y must raise TypeError."""
        with pytest.raises(TypeError, match="y.*torch.float32"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                y=torch.tensor([WATER_ENERGY_EV], dtype=torch.float64),
            )

    def test_rejection_of_non_float32_weight(self) -> None:
        """Non-float32 weight must raise TypeError."""
        with pytest.raises(TypeError, match="weight.*torch.float32"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                weight=torch.tensor([1.0], dtype=torch.float64),
            )

    def test_rejection_of_non_float32_forces(self) -> None:
        """forces with incorrect dtype or shape must raise TypeError or ValueError."""
        with pytest.raises(TypeError, match="forces"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                forces=torch.zeros((3, 3), dtype=torch.float64),
            )

    def test_rejection_of_invalid_dipole_shape(self) -> None:
        """dipole vector with shape != (3,) or (1, 3) must raise SchemaValidationError."""
        with pytest.raises((ValueError, SchemaValidationError), match="dipole"):
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                dipole=torch.tensor([1.0, 2.0, 3.0, 4.0], dtype=torch.float32),
            )

    def test_rejection_of_empty_z(self) -> None:
        """Empty atomic number tensor must be rejected."""
        with pytest.raises((ValueError, SchemaValidationError), match="cannot be empty"):
            ConformerData(
                z=torch.empty((0,), dtype=torch.long),
                pos=torch.empty((0, 3), dtype=torch.float32),
            )


# ==============================================================================
# 2. PyG Subclassing, Mini-Batching, and __inc__ Correctness Tests
# ==============================================================================


class TestPyGBatchingAndInc:
    """Tests PyG Data inheritance, Batch collation, and __inc__ offset mechanism."""

    def test_subclassing_pyg_data(self) -> None:
        """ConformerData must be an instance of torch_geometric.data.Data."""
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
        )
        assert isinstance(data, Data)
        assert isinstance(data, ConformerData)

    def test_batch_collation_and_offsets(self) -> None:
        """Collation via Batch.from_data_list must correctly offset edge_index via __inc__."""
        # Molecule 1: Water (3 atoms, 4 edges: 0-1, 1-0, 0-2, 2-0)
        edge_index1 = torch.tensor([[0, 1, 0, 2], [1, 0, 2, 0]], dtype=torch.long)
        d1 = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
            edge_index=edge_index1,
            y=torch.tensor([WATER_ENERGY_EV], dtype=torch.float32),
            conformer_id=1,
        )

        # Molecule 2: Formaldehyde (4 atoms, 6 edges)
        edge_index2 = torch.tensor([[0, 1, 0, 2, 0, 3], [1, 0, 2, 0, 3, 0]], dtype=torch.long)
        d2 = ConformerData(
            z=torch.tensor(FORMALDEHYDE_Z, dtype=torch.long),
            pos=torch.tensor(FORMALDEHYDE_POS, dtype=torch.float32),
            edge_index=edge_index2,
            y=torch.tensor([FORMALDEHYDE_ENERGY_EV], dtype=torch.float32),
            conformer_id=2,
        )

        # Molecule 3: Methane (5 atoms, 8 edges)
        edge_index3 = torch.tensor(
            [[0, 1, 0, 2, 0, 3, 0, 4], [1, 0, 2, 0, 3, 0, 4, 0]], dtype=torch.long
        )
        d3 = ConformerData(
            z=torch.tensor(METHANE_Z, dtype=torch.long),
            pos=torch.tensor(METHANE_POS, dtype=torch.float32),
            edge_index=edge_index3,
            y=torch.tensor([METHANE_ENERGY_EV], dtype=torch.float32),
            conformer_id=3,
        )

        batch = Batch.from_data_list([d1, d2, d3])

        # Total node count = 3 + 4 + 5 = 12
        assert batch.num_nodes == 12
        assert batch.z.shape == (12,)
        assert batch.pos.shape == (12, 3)

        # Total edge count = 4 + 6 + 8 = 18
        assert batch.edge_index.shape == (2, 18)

        # Verify batch index vector
        expected_batch = torch.tensor([0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2], dtype=torch.long)
        assert torch.equal(batch.batch, expected_batch)

        # Verify ptr vector: [0, 3, 7, 12]
        expected_ptr = torch.tensor([0, 3, 7, 12], dtype=torch.long)
        assert torch.equal(batch.ptr, expected_ptr)

        # Verify edge_index offset correctness:
        # Molecule 2 edges must be shifted by 3 (indices in range [3, 6])
        mol2_edges = batch.edge_index[:, 4:10]
        assert mol2_edges.min().item() >= 3
        assert mol2_edges.max().item() <= 6

        # Molecule 3 edges must be shifted by 7 (indices in range [7, 11])
        mol3_edges = batch.edge_index[:, 10:18]
        assert mol3_edges.min().item() >= 7
        assert mol3_edges.max().item() <= 11

    def test_pyg_dataloader_iteration(self) -> None:
        """PyG DataLoader must iterate smoothly over ConformerData dataset."""
        dataset = [
            ConformerData(
                z=torch.tensor(WATER_Z, dtype=torch.long),
                pos=torch.tensor(WATER_POS, dtype=torch.float32),
                y=torch.tensor([WATER_ENERGY_EV], dtype=torch.float32),
            ),
            ConformerData(
                z=torch.tensor(METHANE_Z, dtype=torch.long),
                pos=torch.tensor(METHANE_POS, dtype=torch.float32),
                y=torch.tensor([METHANE_ENERGY_EV], dtype=torch.float32),
            ),
            ConformerData(
                z=torch.tensor(FORMALDEHYDE_Z, dtype=torch.long),
                pos=torch.tensor(FORMALDEHYDE_POS, dtype=torch.float32),
                y=torch.tensor([FORMALDEHYDE_ENERGY_EV], dtype=torch.float32),
            ),
        ]

        loader = DataLoader(dataset, batch_size=2, shuffle=False)
        batches = list(loader)

        assert len(batches) == 2
        batch0 = batches[0]
        assert batch0.num_nodes == 3 + 5  # Water + Methane = 8
        assert batch0.num_graphs == 2

        batch1 = batches[1]
        assert batch1.num_nodes == 4  # Formaldehyde = 4
        assert batch1.num_graphs == 1


# ==============================================================================
# 3. SE(3) Equivariance and Invariance Tests
# ==============================================================================


class TestSE3EquivarianceAndInvariance:
    """Tests pure spatial translation and 3D SO(3) rotation equivariance & invariance."""

    def test_spatial_translation_equivariance(self) -> None:
        """Spatial translation T transforms pos equivariantly while forces, dipole, and scalars remain invariant."""
        forces_water = torch.tensor(
            [[0.0, 0.0, 0.05], [0.0, -0.025, -0.025], [0.0, 0.025, -0.025]],
            dtype=torch.float32,
        )
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
            y=torch.tensor([WATER_ENERGY_EV], dtype=torch.float32),
            forces=forces_water,
            dipole=torch.tensor(WATER_DIPOLE, dtype=torch.float32),
            weight=torch.tensor([0.75], dtype=torch.float32),
        )

        t_vec = torch.tensor([12.5, -7.3, 4.2], dtype=torch.float32)
        translated = data.translate(t_vec)

        # 1. pos is translated equivariantly: pos' = pos + T
        expected_pos = data.pos + t_vec
        assert torch.allclose(translated.pos, expected_pos, atol=1e-6)

        # 2. forces are translational invariants: forces' == forces
        assert torch.allclose(translated.forces, data.forces, atol=1e-6)

        # 3. dipole is translational invariant
        assert torch.allclose(translated.dipole, data.dipole, atol=1e-6)

        # 4. Energy y and weight are scalar invariants
        assert torch.allclose(translated.y, data.y, atol=1e-6)
        assert torch.allclose(translated.weight, data.weight, atol=1e-6)

        # 5. Rotational constants computed in COM frame are translational invariants
        rc_orig = data.compute_principal_rotational_constants()
        rc_trans = translated.compute_principal_rotational_constants()
        assert torch.allclose(rc_orig, rc_trans, atol=1e-3)

    def test_3d_rotation_equivariance(self) -> None:
        """3D rotation R transforms pos, forces, and dipole equivariantly while scalars remain invariant."""
        forces_water = torch.tensor(
            [[0.0, 0.0, 0.05], [0.0, -0.025, -0.025], [0.0, 0.025, -0.025]],
            dtype=torch.float32,
        )
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
            y=torch.tensor([WATER_ENERGY_EV], dtype=torch.float32),
            forces=forces_water,
            dipole=torch.tensor(WATER_DIPOLE, dtype=torch.float32),
            weight=torch.tensor([0.85], dtype=torch.float32),
        )

        # Generate orthogonal rotation matrix R
        r_mat = create_rotation_matrix_3d(alpha=0.45, beta=1.12, gamma=-0.78)
        assert torch.allclose(r_mat @ r_mat.t(), torch.eye(3), atol=1e-6)

        rotated = data.rotate(r_mat)

        # 1. pos rotates equivariantly: pos' = pos @ R^T (equivalent to r_i' = R r_i)
        expected_pos = torch.matmul(data.pos, r_mat.t())
        assert torch.allclose(rotated.pos, expected_pos, atol=1e-5)

        # 2. forces rotate equivariantly: forces' = forces @ R^T
        expected_forces = torch.matmul(data.forces, r_mat.t())
        assert torch.allclose(rotated.forces, expected_forces, atol=1e-5)

        # 3. dipole rotates equivariantly: dipole' = R @ dipole
        expected_dipole = torch.matmul(r_mat, data.dipole)
        assert torch.allclose(rotated.dipole, expected_dipole, atol=1e-5)

        # 4. Energy y, weight, z are scalar SO(3) invariants
        assert torch.allclose(rotated.y, data.y, atol=1e-6)
        assert torch.allclose(rotated.weight, data.weight, atol=1e-6)
        assert torch.equal(rotated.z, data.z)

        # 5. Spectroscopic rotational constants (A, B, C) are eigenvalues and SO(3) invariants
        rc_orig = data.compute_principal_rotational_constants()
        rc_rot = rotated.compute_principal_rotational_constants()
        assert torch.allclose(rc_orig, rc_rot, rtol=1e-4, atol=1e-2)


# ==============================================================================
# 4. Dynamic Mendeleev Mass Retrieval and Spectroscopic Physics Tests
# ==============================================================================


class TestDynamicMendeleevSpectroscopy:
    """Tests dynamic mass resolution from mendeleev for COM, inertia, and rotational constants."""

    def test_dynamic_mendeleev_mass_resolution(self) -> None:
        """Atomic masses must be queried dynamically from mendeleev and match physical values."""
        m_h = get_atomic_mass(1)
        m_o = get_atomic_mass(8)
        m_c = get_atomic_mass(6)

        assert 1.007 < m_h < 1.009
        assert 15.998 < m_o < 16.001
        assert 12.010 < m_c < 12.012

    def test_water_center_of_mass_calculation(self) -> None:
        """COM calculation for H2O must match analytical weighted average."""
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
        )
        com = data.center_of_mass()

        m_o = get_atomic_mass(8)
        m_h = get_atomic_mass(1)
        total_m = m_o + 2 * m_h
        expected_z = (m_o * 0.1173 + 2 * m_h * (-0.4692)) / total_m

        assert math.isclose(float(com[0].item()), 0.0, abs_tol=1e-5)
        assert math.isclose(float(com[1].item()), 0.0, abs_tol=1e-5)
        assert math.isclose(float(com[2].item()), expected_z, abs_tol=1e-5)

    def test_center_at_com(self) -> None:
        """center_at_com() must translate coordinates so that the new COM is at origin (0, 0, 0)."""
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
        )
        centered = data.center_at_com()
        new_com = centered.center_of_mass()

        assert torch.allclose(new_com, torch.zeros(3), atol=1e-5)

    def test_moment_of_inertia_and_rotational_constants(self) -> None:
        """Principal rotational constants A, B, C for H2O must satisfy A > B > C in MHz."""
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
        )
        rc = data.compute_principal_rotational_constants()
        a, b, c = float(rc[0].item()), float(rc[1].item()), float(rc[2].item())

        # For H2O: A ~ 835 GHz (835,000 MHz), B ~ 435 GHz, C ~ 278 GHz
        assert a >= b >= c
        assert a > 500000.0  # > 500 GHz
        assert b > 250000.0  # > 250 GHz
        assert c > 150000.0  # > 150 GHz

    def test_isotopic_mass_variation(self) -> None:
        """Heavier isotope (Deuterium D2O vs H2O) must yield smaller rotational constants."""
        data_h2o = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
        )
        # Explicit Deuterium mass ~ 2.0141 u
        masses_d2o = [get_atomic_mass(8), 2.0141017781, 2.0141017781]
        rc_h2o = data_h2o.compute_principal_rotational_constants()
        rc_d2o = data_h2o.compute_principal_rotational_constants(masses=masses_d2o)

        # Rotational constants of D2O must be strictly smaller than H2O due to larger moment of inertia
        assert rc_d2o[0] < rc_h2o[0]
        assert rc_d2o[1] < rc_h2o[1]
        assert rc_d2o[2] < rc_h2o[2]


# ==============================================================================
# 5. Inter-Schema Conversion Tests
# ==============================================================================


class TestInterSchemaConversions:
    """Tests bidirectional conversions between ConformerData, MolecularData, and ConformerRecord."""

    def test_molecular_data_roundtrip(self) -> None:
        """ConformerData <-> MolecularData round-trip conversion."""
        mol_data = MolecularData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=torch.tensor(WATER_POS, dtype=torch.float32),
            y=torch.tensor([WATER_ENERGY_EV], dtype=torch.float32),
            forces=torch.randn((3, 3), dtype=torch.float32),
            dipole=torch.tensor(WATER_DIPOLE, dtype=torch.float32),
            rotational_constants=torch.tensor([835000.0, 435000.0, 278000.0], dtype=torch.float32),
            symbols=WATER_SYMBOLS,
            metadata={"source": "test_roundtrip"},
        )

        conformer_data = ConformerData.from_molecular_data(mol_data)
        assert isinstance(conformer_data, ConformerData)
        assert torch.equal(conformer_data.z, mol_data.z)
        assert torch.allclose(conformer_data.pos, mol_data.pos)
        assert torch.allclose(conformer_data.forces, mol_data.forces)

        mol_data_back = conformer_data.to_molecular_data()
        assert isinstance(mol_data_back, MolecularData)
        assert torch.equal(mol_data_back.z, mol_data.z)
        assert torch.allclose(mol_data_back.pos, mol_data.pos)
        assert torch.allclose(mol_data_back.forces, mol_data.forces)
        assert mol_data_back.metadata["source"] == "test_roundtrip"

    def test_conformer_record_roundtrip(self) -> None:
        """ConformerData <-> ConformerRecord round-trip conversion."""
        record = ConformerRecord(
            conformer_id=42,
            coords=np.array(WATER_POS, dtype=np.float64),
            energy=WATER_ENERGY_EV,
            relative_energy=0.0,
            boltzmann_weight=0.995,
            forces=np.zeros((3, 3), dtype=np.float64),
            dipole=np.array(WATER_DIPOLE, dtype=np.float64),
            rotational_constants=np.array([835000.0, 435000.0, 278000.0], dtype=np.float64),
            qm_method="DFT/wB97M-V/def2-QZVPP",
            source_hash="a" * 64,
            metadata={"tag": "canonical_minimum"},
        )

        conf_data = ConformerData.from_conformer_record(
            record=record,
            atomic_numbers=WATER_Z,
            smiles="O",
        )
        assert isinstance(conf_data, ConformerData)
        assert conf_data.conformer_id == 42
        assert conf_data.source_hash == "a" * 64
        assert conf_data.smiles == "O"

        record_back = conf_data.to_conformer_record(conformer_id=42)
        assert isinstance(record_back, ConformerRecord)
        assert record_back.conformer_id == 42
        assert np.allclose(record_back.coords, record.coords)
        assert math.isclose(record_back.energy, record.energy, rel_tol=1e-5)
        assert math.isclose(record_back.boltzmann_weight, record.boltzmann_weight, rel_tol=1e-5)
        assert record_back.qm_method == "DFT/wB97M-V/def2-QZVPP"
        assert record_back.source_hash == "a" * 64

    def test_from_xyz_file_parsing(self) -> None:
        """Parsing an authentic XYZ file must create a validated ConformerData with SHA-256 hash."""
        xyz_content = (
            "3\n"
            "Water molecule ground state DFT geometry [eV]\n"
            f"O  {WATER_POS[0][0]:.6f}  {WATER_POS[0][1]:.6f}  {WATER_POS[0][2]:.6f}\n"
            f"H  {WATER_POS[1][0]:.6f}  {WATER_POS[1][1]:.6f}  {WATER_POS[1][2]:.6f}\n"
            f"H  {WATER_POS[2][0]:.6f}  {WATER_POS[2][1]:.6f}  {WATER_POS[2][2]:.6f}\n"
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as tf:
            tf.write(xyz_content)
            temp_path = tf.name

        try:
            conf_data = ConformerData.from_xyz_file(temp_path, energy=WATER_ENERGY_EV)
            assert conf_data.num_nodes == 3
            assert conf_data.symbols == ["O", "H", "H"]
            assert torch.equal(conf_data.z, torch.tensor([8, 1, 1], dtype=torch.long))
            assert torch.allclose(conf_data.pos, torch.tensor(WATER_POS, dtype=torch.float32), atol=1e-5)
            assert conf_data.source_hash is not None
            assert len(conf_data.source_hash) == 64
            assert is_valid_conformer_data(conf_data) is True
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


# ==============================================================================
# 6. State Immutability Tests
# ==============================================================================


class TestStateImmutability:
    """Tests that all geometric transformations adhere strictly to pure functional immutability."""

    def test_translate_immutability(self) -> None:
        """translate() must return a fresh instance without altering original tensors."""
        orig_pos = torch.tensor(WATER_POS, dtype=torch.float32)
        orig_z = torch.tensor(WATER_Z, dtype=torch.long)
        data = ConformerData(z=orig_z, pos=orig_pos)

        pos_copy = orig_pos.clone()
        t_vec = torch.tensor([5.0, -2.0, 1.0], dtype=torch.float32)

        translated = data.translate(t_vec)

        # Original data.pos must be completely unmodified
        assert torch.equal(data.pos, pos_copy)
        # New translated.pos must be distinct in memory
        assert translated.pos.data_ptr() != data.pos.data_ptr()
        assert not torch.equal(translated.pos, data.pos)

    def test_rotate_immutability(self) -> None:
        """rotate() must return a fresh instance without altering original tensors."""
        orig_pos = torch.tensor(WATER_POS, dtype=torch.float32)
        orig_forces = torch.randn((3, 3), dtype=torch.float32)
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=orig_pos,
            forces=orig_forces,
        )

        pos_copy = orig_pos.clone()
        forces_copy = orig_forces.clone()

        r_mat = create_rotation_matrix_3d(0.5, -0.3, 0.8)
        rotated = data.rotate(r_mat)

        # Original tensors must remain untouched
        assert torch.equal(data.pos, pos_copy)
        assert torch.equal(data.forces, forces_copy)
        # New rotated tensors must be distinct memory buffers
        assert rotated.pos.data_ptr() != data.pos.data_ptr()
        assert rotated.forces.data_ptr() != data.forces.data_ptr()

    def test_center_at_com_immutability(self) -> None:
        """center_at_com() must return a fresh instance without altering original coordinates."""
        orig_pos = torch.tensor(WATER_POS, dtype=torch.float32)
        data = ConformerData(
            z=torch.tensor(WATER_Z, dtype=torch.long),
            pos=orig_pos,
        )

        pos_copy = orig_pos.clone()
        centered = data.center_at_com()

        assert torch.equal(data.pos, pos_copy)
        assert centered.pos.data_ptr() != data.pos.data_ptr()

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.