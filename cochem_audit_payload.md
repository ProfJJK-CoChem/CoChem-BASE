Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\11_scribe_doc_manager.md.
Original prompt:
# Phase 4, Task 11: Master Document Assembly & Packaging Daemon (`managers/scribe_doc_manager.py`)

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`  
**Target Files to Create:**
- `managers/scribe_doc_manager.py`
- `managers/test_scribe_doc_manager.py`

## Objective
Implement the production-grade document compilation, manifest generation, and archive packaging daemon (`DocumentManager`) along with comprehensive zero-mock integration tests (`test_scribe_doc_manager.py`) for CoChem-SCRIBE (Stage 6.3). This capstone module is responsible for compiling scientific LaTeX manuscripts (`Methodology.tex`) into publication-grade PDFs via a silent, multi-pass headless loop (`pdflatex -> bibtex -> pdflatex -> pdflatex`), trapping LaTeX syntax errors to fall back gracefully to raw `.tex` and `.md` formats, purging intermediate build waste (`.aux`, `.bbl`, `.blg`, `.log`, `.out`), synthesizing a FAIR-compliant cryptographic `manifest.json`, bundling the finalized output directory into a timestamped `.zip` archive, applying tamper-resistant read-only permission locks, and emitting the absolute artifact path to standard output for remote cluster schedulers (SLURM/PBS) and CI/CD pipelines.

The implementation must strictly adhere to the **CoChem-SCRIBE Software Requirements Specification (SRS Phase 4, Task 11, Tasks 81–90)**, **Method Matrix v4**, the **Zero-Mock Anti-Spoofing Protocol**, **FAIR Data Principles**, and the **6-Tier Environment Matrix** (Local-Windows WSL, Local-MacOS OrbStack, Local-Linux Debian, Codespaces, GitHub Actions, HPC).

---

## Technical Specifications & Architecture

### 1. Architectural Philosophy: The Capstone Integrator & Headless Execution (SRS §11.1)
- **Headless Resiliency across the 6-Tier Matrix:** This module executes in unattended, non-interactive environments (e.g., HPC SLURM batch jobs, GitHub Actions runners, Docker containers). It must never hang waiting for user stdin input, never crash the parent compute queue on compilation failure, and always salvage raw Markdown and LaTeX artifacts if PDF compilation cannot proceed.
- **Strict Mathematical Air-Gap & Local Execution:** Document compilation, manifest generation, and ZIP packaging execute 100% locally and offline without outbound network calls.
- **FAIR-Compliant Provenance & Tamper Resistance:** Generates an immutable, cryptographic `manifest.json` cataloging every generated artifact (file name, relative path, file size in bytes, and SHA-256 digest) alongside the codebase topological hash. Applies read-only permissions (`0o444`) to finalized archives.
- **Dynamic Cross-Platform Path Resolution:** Default archive paths are dynamically resolved via `pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"`. Hardcoded OS paths are strictly forbidden.

---

## Deliverable 1: `managers/scribe_doc_manager.py`

### 1. Class Architecture & Interface Contract (`DocumentManager`)

Define the `DocumentManager` class in `managers/scribe_doc_manager.py` with complete Python 3.10+ typing (`pathlib.Path`, `typing.Dict`, `typing.Any`, `typing.Optional`, `typing.Union`, `typing.List`, `typing.Tuple`):

```python
import os
import sys
import stat
import json
import shutil
import hashlib
import logging
import pathlib
import datetime
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Union, List, Tuple

@dataclass
class CompilationResult:
    """Encapsulates the status and telemetry of the LaTeX compilation process."""
    success: bool
    pdf_path: Optional[pathlib.Path] = None
    log_path: Optional[pathlib.Path] = None
    error_message: Optional[str] = None
    passes_completed: int = 0
    fallback_used: bool = False

class DocumentManager:
    """Capstone document compiler, manifest generator, and archive packaging daemon.
    
    Executes silent multi-pass LaTeX compilation, traps build errors, cleans intermediate
    scratch files, generates FAIR-compliant manifest.json with SHA-256 digests, bundles
    artifacts into timestamped ZIP archives, applies read-only permission locks, and logs
    standardized artifact telemetry for headless cluster schedulers.
    """
    
    CLEANUP_EXTENSIONS: Tuple[str, ...] = (
        ".aux", ".bbl", ".blg", ".log", ".out", ".toc", ".synctex.gz", ".fls", ".fdb_latexmk"
    )

    def __init__(
        self,
        archive_dir: Optional[Union[str, pathlib.Path]] = None,
        timeout_seconds: int = 60
    ) -> None:
        """Initializes DocumentManager locked to the active Report_Archive path."""
        pass

    def check_latex_installed(self) -> bool:
        """Verifies if pdflatex binary is available in the system PATH."""
        pass

    def compile_latex(
        self,
        tex_filename: str = "Methodology.tex",
        target_dir: Optional[Union[str, pathlib.Path]] = None
    ) -> CompilationResult:
        """Executes silent compilation loop (pdflatex -> bibtex -> pdflatex -> pdflatex)."""
        pass

    def check_log_for_fatal_errors(self, log_path: pathlib.Path) -> Tuple[bool, Optional[str]]:
        """Parses LaTeX .log file specifically for 'Fatal error', '! ', or 'Emergency stop'."""
        pass

    def cleanup_intermediate_files(
        self,
        target_dir: Optional[Union[str, pathlib.Path]] = None,
        preserve_pdf: bool = True,
        preserve_log_on_error: bool = False
    ) -> List[pathlib.Path]:
        """Deletes intermediate LaTeX build waste (.aux, .bbl, .blg, .log, .out)."""
        pass

    def compute_file_sha256(self, file_path: pathlib.Path) -> str:
        """Calculates deterministic SHA-256 cryptographic hash of a file."""
        pass

    def generate_manifest(
        self,
        target_dir: Optional[Union[str, pathlib.Path]] = None,
        topological_code_hash: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> pathlib.Path:
        """Generates FAIR-compliant manifest.json listing every file, sizes, and SHA-256 hashes."""
        pass

    def create_archive(
        self,
        source_dir: Optional[Union[str, pathlib.Path]] = None,
        archive_name_prefix: str = "CoChem_Final_Report",
        timestamp_str: Optional[str] = None
    ) -> pathlib.Path:
        """Bundles output directory into a portable .zip archive using shutil.make_archive."""
        pass

    def apply_readonly_lock(self, file_path: pathlib.Path) -> bool:
        """Applies POSIX read-only lock (0o444 / S_IREAD) across 6-Tier filesystems."""
        pass

    def package_final_report(
        self,
        target_dir: Optional[Union[str, pathlib.Path]] = None,
        tex_filename: str = "Methodology.tex",
        topological_code_hash: Optional[str] = None
    ) -> Tuple[CompilationResult, pathlib.Path, pathlib.Path]:
        """Master execution daemon running compilation, cleanup, manifest generation, and packaging."""
        pass
```

---

### 2. Detailed Functional Requirements (Tasks 81–89)

#### 2.1 Initialization & Dynamic Path Resolution (Task 81)
- **Default Directory Resolution:** If `archive_dir` is not provided, resolve dynamically to `pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"`.
- **Directory Scaffolding:** Ensure the target directory exists (`self.archive_dir.mkdir(parents=True, exist_ok=True)`).
- **Timeout Protection:** Configurable subprocess timeout (default `60` seconds) to prevent infinite loops during compilation.

#### 2.2 Silent Headless Multi-Pass LaTeX Compilation (Tasks 82 & 83)
- **Binary Pre-Flight Check:** Check `shutil.which("pdflatex")`. If unavailable, log warning `[SCRIBE-WARN] pdflatex not found in PATH. Skipping PDF compilation.` and return `CompilationResult(success=False, fallback_used=True, error_message="pdflatex binary not found")`.
- **Non-Stop Mode Mandate:** Execute subprocess with `['pdflatex', '-interaction=nonstopmode', tex_filename]`.
- **Academic 4-Pass Resolution Loop:**
  1. Pass 1: `pdflatex -interaction=nonstopmode <tex_filename>`
  2. Pass 2: Check if corresponding `.bib` file or `cochem_citations.bib` exists. If `shutil.which("bibtex")` is found and citations exist, run `bibtex <aux_basename>`.
  3. Pass 3: `pdflatex -interaction=nonstopmode <tex_filename>`
  4. Pass 4: `pdflatex -interaction=nonstopmode <tex_filename>`
- **Subprocess Isolation:** Execute all passes with `cwd=working_dir`, `stdout=subprocess.PIPE`, `stderr=subprocess.STDOUT`, `text=True`, and `timeout=self.timeout_seconds`.

#### 2.3 LaTeX Error Trapping & Graceful Fallback (Task 84)
- **Log Parsing:** In the event of non-zero exit code or missing PDF, read `<tex_basename>.log` and parse for `Fatal error`, `! `, `Emergency stop`, or `Transcript written on`.
- **Graceful Fallback:** If compilation fails, do NOT raise an unhandled exception or crash the process. Return `CompilationResult(success=False, fallback_used=True, error_message=...)`. Ensure raw `.tex`, `.md`, `.bib`, and generated figure assets remain intact for downstream consumption.

#### 2.4 Intermediate Build Waste Cleanup (Task 85)
- **Purge Extensions:** Automatically remove intermediate scratch files matching `CLEANUP_EXTENSIONS` (`.aux`, `.bbl`, `.blg`, `.log`, `.out`, `.toc`, `.synctex.gz`, `.fls`, `.fdb_latexmk`).
- **Asset Preservation:** Must NEVER delete primary artifacts: `.tex`, `.md`, `.pdf`, `.bib`, `.json`, `.png`, `.svg`, `.zip`, `.h5`.
- **Safe Unlinking:** Use `path.unlink(missing_ok=True)` or wrap deletions in `try/except FileNotFoundError` blocks.

#### 2.5 FAIR-Compliant Manifest Generation (Task 86)
- **File Manifest:** Recursively scan the report directory (excluding `manifest.json` itself and any existing `.zip` archives).
- **JSON Structure:**
  ```json
  {
    "manifest_version": "1.0",
    "timestamp_iso": "2026-08-23T12:00:00Z",
    "generator": "CoChem-SCRIBE Stage 6.3 DocumentManager",
    "topological_code_hash": "sha256:...",
    "files_count": 5,
    "files": [
      {
        "relative_path": "Methodology.tex",
        "size_bytes": 4521,
        "sha256": "...",
        "content_type": "application/x-tex"
      }
    ]
  }
  ```
- **Atomic Serialization:** Write `manifest.json` formatted with `indent=2` to the root of the archive directory.

#### 2.6 ZIP Payload Archiving & POSIX Read-Only Locks (Tasks 87, 88, 89)
- **Timestamped Archive:** Format archive name as `CoChem_Final_Report_[TIMESTAMP].zip` using timestamp format `%Y%m%d_%H%M%S`.
- **Shutil Bundling:** Use `shutil.make_archive` with `root_dir` pointing to the target folder and `base_dir="."` to prevent recursive directory nesting or packaging parent folders.
- **Read-Only Permission Locking (Task 88):** Apply read-only mode to the finalized `.zip` file:
  - POSIX: `os.chmod(archive_path, 0o444)` or `stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH`.
  - Windows: Wrap in exception-safe logic to handle NTFS attribute mapping (`stat.S_IREAD`).
- **Headless Scheduler Logging (Task 89):** Emit deterministic standard output marker:
  `[SCRIBE-OUTPUT] Final Report Archive: <absolute_path_to_zip>`
  `[SCRIBE-OUTPUT] Manifest File: <absolute_path_to_manifest>`

---

## Deliverable 2: `managers/test_scribe_doc_manager.py`

### 1. Test Architecture & Zero-Mock Protocol (Task 90)
Implement exhaustive, genuine integration tests in `managers/test_scribe_doc_manager.py`.
- **ABSOLUTELY NO MOCKS:** Explicitly avoid `unittest.mock` or `MagicMock`. All tests must execute against real directories using `pytest`'s `tmp_path` fixture.
- **Cross-Platform Read-Only Fixture Teardown:** Ensure test cleanup handles read-only files on Windows by restoring write permissions (`os.chmod(p, stat.S_IWRITE)`) before directory removal.

### 2. Required Test Suite Specifications
1. **`test_document_manager_initialization(tmp_path)`:**
   - Verify dynamic path defaulting to `pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"`.
   - Verify custom path initialization and directory creation.
2. **`test_latex_compilation_genuine_or_fallback(tmp_path)`:**
   - Create a valid, minimal self-contained `minimal_test.tex` (`\documentclass{article}\begin{document}Hello CoChem\end{document}`).
   - If `pdflatex` is installed on the host system: assert compilation succeeds, `.pdf` is generated, and intermediate `.aux`/`.log` files are cleaned.
   - If `pdflatex` is not installed: assert `CompilationResult` returns `success=False`, `fallback_used=True`, and no unhandled exception is thrown.
3. **`test_latex_error_trapping_invalid_syntax(tmp_path)`:**
   - Write a broken `.tex` file with intentional fatal syntax errors (e.g., unmatched `\begin{equation}`).
   - Verify that error trapping captures failure, identifies fatal log tokens, does not crash Python, and preserves raw `.tex` and `.md` files.
4. **`test_cleanup_intermediate_files(tmp_path)`:**
   - Populate directory with dummy `.aux`, `.bbl`, `.blg`, `.log`, `.out`, `.tex`, `.md`, `.pdf`.
   - Run `cleanup_intermediate_files()` and assert that all scratch extensions are purged while `.tex`, `.md`, and `.pdf` remain intact.
5. **`test_manifest_generation_and_hashing(tmp_path)`:**
   - Create multiple test files (`report.md`, `data.json`).
   - Generate `manifest.json`, parse output, and verify that file count, relative paths, file sizes, and computed SHA-256 hashes match exact file bytes.
6. **`test_archive_creation_and_permission_lock(tmp_path)`:**
   - Bundle test directory into `.zip` using `create_archive()`.
   - Verify archive exists, is a valid ZIP file via `zipfile.ZipFile(zip_path).testzip()`, and possesses read-only permissions (`0o444` / `stat.S_IREAD`).
   - Verify standard output contains `[SCRIBE-OUTPUT] Final Report Archive:`.
7. **`test_package_final_report_e2e(tmp_path)`:**
   - Execute the end-to-end `package_final_report()` workflow on a complete test payload.
   - Verify return tuple `(compilation_res, manifest_path, zip_path)`.

---

## Directives & Execution Constraints

1. **Target Deliverables:** Implement both `managers/scribe_doc_manager.py` and `managers/test_scribe_doc_manager.py`.
2. **Zero-Mock Anti-Spoofing Protocol:** Strictly NO mocks, fake subprocess stubs, or synthetic file assertions. Subprocess calls and file operations must execute in reality against local temporary paths.
3. **Strict Python 3.10+ Standards:** Use type annotations, `dataclasses`, `pathlib.Path`, and standard `logging` with `[SCRIBE-*]` markers.
4. **Air-Gap Mandate:** Zero network calls. Dynamic home directory resolution.
5. **Method Matrix v4 & FAIR Principles:** Generate complete cryptographic metadata in `manifest.json`.
6. **6-Tier Matrix & Cross-Platform Defense:** Support Windows (NTFS), macOS, Linux, Codespaces, GitHub Actions, and HPC batch nodes without permission crashes.

---

## Task
Implement the Python modules as described and save them to:
1. `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\managers\scribe_doc_manager.py`
2. `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\managers\test_scribe_doc_manager.py`


Modified files content:

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.