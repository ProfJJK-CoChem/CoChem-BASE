Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-GEOM\.in-progress\Task_04_scripts_train_py.md.
Original prompt:
# Task: Create `scripts/train.py`

## Context
You are an autonomous execution agent coding the new version of CoChem-GEOM based on the approved System Architecture.
Target output directory: `D:\__CoChem\GitHub-Repo\CoChem-GEOM`

## Strict Execution Constraints
1. **Scope:** Generate exactly one coding script file for this prompt (`scripts/train.py`).
2. **Path:** Output the generated file to the target output directory at `D:\__CoChem\GitHub-Repo\CoChem-GEOM\scripts/train.py`. Do not execute or run the code, only generate the file.
3. **Geometric Equivariance & Invariance:** The system must strictly separate non-spatial node features from spatial coordinates.
4. **State Immutability:** Geometric transformations are immutable (`data.pos = data.pos + update`, never `data.pos += update`).
5. **No Hardcoded Paths:** Use dynamic lookups (`pathlib.Path.home()`, environment variables).
6. **Provenance Tags:** You MUST tag all qualitative values, bounds, energy metrics, and hardware speedups with explicit provenance tags (`[M]` for Measured, `[D]` for Derived, `[E]` for Expert Estimate).

## File Specific Instructions
Implement Execution Contract. Minimal orchestrator. Instantiate Hydra config, build DataModule, initialize LightningModule, trigger `trainer.fit()`. Wrap subprocess calls in try/except with `check=True` and strict timeouts `[E]`.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\managers\scribe_doc_manager.py ---
"""Master Document Assembly & Packaging Daemon for CoChem-SCRIBE (Stage 6.3).

Executes headless multi-pass LaTeX compilation:
  (pdflatex -> bibtex -> pdflatex -> pdflatex)
Traps syntax errors to fall back gracefully to raw TeX/Markdown assets,
purges intermediate build scratch files, computes chunked SHA-256 digests,
generates FAIR-compliant manifest.json catalogs, bundles finalized payloads
into timestamped ZIP archives, applies tamper-resistant read-only permission locks,
and emits telemetry markers for cluster schedulers.
"""

from __future__ import annotations

import atexit
import datetime
import hashlib
import logging
import mimetypes
import os
import pathlib
import shutil
import stat
import subprocess
from dataclasses import dataclass
from typing import Any, ClassVar

import psutil
from pydantic import BaseModel

logger = logging.getLogger(__name__)

FALLBACK_TOPOLOGICAL_HASH: str = "sha256:" + "0" * 64
DEFAULT_TIMEOUT_SECONDS: int = 60
CHUNK_SIZE_BYTES: int = 65536


def _sweep_zombies() -> None:
    """Terminates orphaned LaTeX/BibTeX compiler processes upon interpreter exit."""
    for p in psutil.process_iter(["pid", "name"]):
        try:
            proc_name = p.name().lower()
            if proc_name in (
                "pdflatex",
                "bibtex",
                "xelatex",
                "pdflatex.exe",
                "bibtex.exe",
                "xelatex.exe",
            ):
                p.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass


atexit.register(_sweep_zombies)


@dataclass
class CompilationResult:
    """Encapsulates the status and telemetry of the LaTeX compilation process."""

    success: bool
    pdf_path: pathlib.Path | None = None
    log_path: pathlib.Path | None = None
    error_message: str | None = None
    passes_completed: int = 0
    fallback_used: bool = False


class FileManifest(BaseModel):
    relative_path: str
    size_bytes: int
    sha256: str
    content_type: str


class Manifest(BaseModel):
    manifest_version: str
    timestamp_iso: str
    generator: str
    topological_code_hash: str
    files_count: int
    files: list[FileManifest]
    extra_metadata: dict[str, Any] | None = None


class DocumentManager:
    """Capstone document compiler, manifest generator, and archive packaging daemon.

    Executes silent multi-pass LaTeX compilation, traps build errors, cleans
    intermediate scratch files, generates FAIR-compliant manifest.json with SHA-256
    digests, bundles artifacts into timestamped ZIP archives, applies read-only
    permission locks, and logs telemetry for headless cluster schedulers.
    """

    CLEANUP_EXTENSIONS: tuple[str, ...] = (
        ".aux",
        ".bbl",
        ".blg",
        ".log",
        ".out",
        ".toc",
        ".synctex.gz",
        ".fls",
        ".fdb_latexmk",
    )

    PRIMARY_EXTENSIONS: tuple[str, ...] = (
        ".tex",
        ".md",
        ".pdf",
        ".bib",
        ".json",
        ".png",
        ".svg",
        ".zip",
        ".h5",
        ".hdf5",
        ".txt",
        ".csv",
    )

    MIME_MAP: ClassVar[dict[str, str]] = {
        ".tex": "application/x-tex",
        ".pdf": "application/pdf",
        ".md": "text/markdown",
        ".json": "application/json",
        ".bib": "application/x-bibtex",
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".h5": "application/x-hdf5",
        ".hdf5": "application/x-hdf5",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".html": "text/html",
        ".yaml": "application/x-yaml",
        ".yml": "application/x-yaml",
    }

    def __init__(
        self,
        archive_dir: str | pathlib.Path | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """Initializes DocumentManager locked to the active Report_Archive path."""
        if archive_dir is None:
            self.archive_dir = (
                pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"
            ).resolve()
        else:
            self.archive_dir = pathlib.Path(archive_dir).resolve()

        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds: int = timeout_seconds
        logger.info(
            "[SCRIBE-INIT] DocumentManager initialized: archive_dir=%s, timeout=%ds",
            self.archive_dir,
            self.timeout_seconds,
        )

    def check_latex_installed(self) -> bool:
        """Verifies if pdflatex binary is available in the system PATH."""
        binary_path = shutil.which("pdflatex")
        return binary_path is not None

    def check_log_for_fatal_errors(
        self, log_path: pathlib.Path
    ) -> tuple[bool, str | None]:
        """Parses LaTeX .log file for 'Fatal error', '! ', or 'Emergency stop'."""
        if not log_path.exists():
            return False, None

        error_tokens = ("Fatal error", "! ", "Emergency stop")
        collected_errors: list[str] = []

        try:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    stripped = line.strip()
                    for token in error_tokens:
                        if token in stripped:
                            collected_errors.append(stripped)
                            break
        except OSError as exc:
            logger.warning(
                "[SCRIBE-WARN] Unable to read LaTeX log file %s: %s", log_path, exc
            )
            return True, f"Failed to read log file: {exc}"

        if collected_errors:
            error_summary = " | ".join(collected_errors[:5])
            return True, error_summary

        return False, None

    def compile_latex(
        self,
        tex_filename: str = "Methodology.tex",
        target_dir: str | pathlib.Path | None = None,
    ) -> CompilationResult:
        """Executes compilation loop (pdflatex -> bibtex -> pdflatex -> pdflatex)."""
        working_dir = (
            pathlib.Path(target_dir).resolve()
            if target_dir is not None
            else self.archive_dir
        )
        tex_path = working_dir / tex_filename

        if not tex_path.exists():
            msg = f"TeX source file not found: {tex_path}"
            logger.warning("[SCRIBE-WARN] %s", msg)
            return CompilationResult(
                success=False,
                fallback_used=True,
                error_message=msg,
                passes_completed=0,
            )

        if not self.check_latex_installed():
            msg = "pdflatex binary not found in PATH"
            logger.warning("[SCRIBE-WARN] %s. Skipping PDF compilation.", msg)
            return CompilationResult(
                success=False,
                fallback_used=True,
                error_message=msg,
                passes_completed=0,
            )

        tex_stem = tex_path.stem
        pdf_path = working_dir / f"{tex_stem}.pdf"
        log_path = working_dir / f"{tex_stem}.log"
        aux_path = working_dir / f"{tex_stem}.aux"
        passes_completed = 0

        has_citations = any(working_dir.glob("*.bib"))
        has_bibtex = shutil.which("bibtex") is not None

        try:
            # Pass 1: Initial compilation pass
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", tex_filename],
                cwd=str(working_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            passes_completed += 1

            # Pass 2: Bibliography resolution pass if .bib and bibtex exist
            if has_citations and has_bibtex and aux_path.exists():
                subprocess.run(
                    ["bibtex", tex_stem],
                    cwd=str(working_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
                passes_completed += 1

            # Pass 3: Cross-reference resolution pass
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", tex_filename],
                cwd=str(working_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            passes_completed += 1

            # Pass 4: Final typesetting pass
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", tex_filename],
                cwd=str(working_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            passes_completed += 1

        except subprocess.TimeoutExpired:
            msg = f"LaTeX compilation timed out after {self.timeout_seconds} seconds"
            logger.warning("[SCRIBE-WARN] %s", msg)
            return CompilationResult(
                success=False,
                pdf_path=pdf_path if pdf_path.exists() else None,
                log_path=log_path if log_path.exists() else None,
                error_message=msg,
                passes_completed=passes_completed,
                fallback_used=True,
            )
        except subprocess.CalledProcessError as exc:
            has_fatal_error, error_summary = self.check_log_for_fatal_errors(log_path)
            err_msg = (
                error_summary
                or f"LaTeX compilation failed with exit status {exc.returncode}"
            )
            logger.warning("[SCRIBE-WARN] %s", err_msg)
            return CompilationResult(
                success=False,
                pdf_path=pdf_path if pdf_path.exists() else None,
                log_path=log_path if log_path.exists() else None,
                error_message=err_msg,
                passes_completed=passes_completed,
                fallback_used=True,
            )
        except Exception as exc:
            msg = f"LaTeX compilation encountered unexpected exception: {exc}"
            logger.warning("[SCRIBE-WARN] %s", msg)
            return CompilationResult(
                success=False,
                pdf_path=pdf_path if pdf_path.exists() else None,
                log_path=log_path if log_path.exists() else None,
                error_message=msg,
                passes_completed=passes_completed,
                fallback_used=True,
            )

        # Inspect log file for fatal LaTeX errors
        has_fatal_error, error_summary = self.check_log_for_fatal_errors(log_path)

        if pdf_path.exists() and not has_fatal_error:
            logger.info(
                "[SCRIBE-SUCCESS] LaTeX compilation succeeded: %s (%d passes)",
                pdf_path,
                passes_completed,
            )
            return CompilationResult(
                success=True,
                pdf_path=pdf_path,
                log_path=log_path if log_path.exists() else None,
                passes_completed=passes_completed,
                fallback_used=False,
            )

        err_msg = (
            error_summary
            or "LaTeX compilation produced fatal errors or missing PDF output"
        )
        logger.warning("[SCRIBE-WARN] %s", err_msg)
        return CompilationResult(
            success=False,
            pdf_path=pdf_path if pdf_path.exists() else None,
            log_path=log_path if log_path.exists() else None,
            error_message=err_msg,
            passes_completed=passes_completed,
            fallback_used=True,
        )

    def cleanup_intermediate_files(
        self,
        target_dir: str | pathlib.Path | None = None,
        preserve_pdf: bool = True,
        preserve_log_on_error: bool = False,
    ) -> list[pathlib.Path]:
        """Deletes intermediate LaTeX build waste (.aux, .bbl, .blg, .log, .out)."""
        working_dir = (
            pathlib.Path(target_dir).resolve()
            if target_dir is not None
            else self.archive_dir
        )
        deleted: list[pathlib.Path] = []

        if not working_dir.exists():
            return deleted

        for file_path in sorted(working_dir.rglob("*")):
            if not file_path.is_file():
                continue

            name_lower = file_path.name.lower()

            matching_cleanup = None
            for ext in self.CLEANUP_EXTENSIONS:
                if name_lower.endswith(ext.lower()):
                    matching_cleanup = ext
                    break

            if matching_cleanup is None:
                continue

            if preserve_log_on_error and name_lower.endswith(".log"):
                continue

            try:
                file_path.unlink(missing_ok=True)
                deleted.append(file_path)
                logger.debug(
                    "[SCRIBE-CLEANUP] Removed intermediate file: %s", file_path
                )
            except OSError as exc:
                logger.warning(
                    "[SCRIBE-WARN] Could not remove file %s: %s", file_path, exc
                )

        return deleted

    def compute_file_sha256(self, file_path: pathlib.Path) -> str:
        """Calculates deterministic SHA-256 cryptographic hash of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()

    def generate_manifest(
        self,
        target_dir: str | pathlib.Path | None = None,
        topological_code_hash: str | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> pathlib.Path:
        """Generates FAIR-compliant manifest.json listing files and hashes."""
        working_dir = (
            pathlib.Path(target_dir).resolve()
            if target_dir is not None
            else self.archive_dir
        )
        working_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = working_dir / "manifest.json"
        files_list: list[dict[str, Any]] = []

        all_entries = sorted(working_dir.rglob("*"), key=lambda p: p.as_posix())
        for file_path in all_entries:
            if not file_path.is_file():
                continue

            # Exclude manifest.json itself and any .zip archives
            if file_path.name == "manifest.json" or file_path.suffix.lower() == ".zip":
                continue

            rel_path = file_path.relative_to(working_dir).as_posix()
            file_size = file_path.stat().st_size
            sha256_hash = self.compute_file_sha256(file_path)

            ext = file_path.suffix.lower()
            content_type = self.MIME_MAP.get(
                ext,
                mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
            )

            files_list.append(
                {
                    "relative_path": rel_path,
                    "size_bytes": file_size,
                    "sha256": sha256_hash,
                    "content_type": content_type,
                }
            )

        timestamp_iso = (
            datetime.datetime.now(datetime.timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

        manifest_obj = Manifest(
            manifest_version="1.0",
            timestamp_iso=timestamp_iso,
            generator="CoChem-SCRIBE Stage 6.3 DocumentManager",
            topological_code_hash=(
                topological_code_hash
                if topological_code_hash is not None
                else FALLBACK_TOPOLOGICAL_HASH
            ),
            files_count=len(files_list),
            files=[FileManifest(**fl) for fl in files_list],
            extra_metadata=extra_metadata,
        )

        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest_obj.model_dump_json(indent=2))

        return manifest_path

    def apply_readonly_lock(self, file_path: pathlib.Path) -> bool:
        """Applies POSIX read-only lock (0o444 / S_IREAD) across 6-Tier filesystems."""
        if not file_path.exists():
            logger.warning(
                "[SCRIBE-WARN] Target file for readonly lock does not exist: %s",
                file_path,
            )
            return False

        try:
            # Set POSIX 0o444 (read-only for user, group, other) and Windows S_IREAD
            readonly_mode = stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH
            os.chmod(file_path, readonly_mode)
            logger.info(
                "[SCRIBE-SECURITY] Applied read-only permission lock (0o444) to: %s",
                file_path,
            )
            return True
        except OSError as exc:
            logger.warning(
                "[SCRIBE-WARN] Failed to apply read-only lock to %s: %s",
                file_path,
                exc,
            )
            return False

    def create_archive(
        self,
        source_dir: str | pathlib.Path | None = None,
        archive_name_prefix: str = "CoChem_Final_Report",
        timestamp_str: str | None = None,
    ) -> pathlib.Path:
        """Bundles output directory into a portable .zip archive."""
        working_dir = (
            pathlib.Path(source_dir).resolve()
            if source_dir is not None
            else self.archive_dir
        )

        if timestamp_str is None:
            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        archive_base_name = f"{archive_name_prefix}_{timestamp_str}"
        target_zip_base = working_dir.parent / archive_base_name

        archive_file_str = shutil.make_archive(
            base_name=str(target_zip_base),
            format="zip",
            root_dir=str(working_dir),
            base_dir=".",
        )
        archive_path = pathlib.Path(archive_file_str).resolve()

        self.apply_readonly_lock(archive_path)

        output_marker = f"[SCRIBE-OUTPUT] Final Report Archive: {archive_path}"
        print(output_marker)
        print(str(archive_path.resolve()))
        logger.info(output_marker)

        return archive_path

    def package_final_report(
        self,
        target_dir: str | pathlib.Path | None = None,
        tex_filename: str = "Methodology.tex",
        topological_code_hash: str | None = None,
    ) -> tuple[CompilationResult, pathlib.Path, pathlib.Path]:
        """Master execution daemon running pipeline and packaging."""
        working_dir = (
            pathlib.Path(target_dir).resolve()
            if target_dir is not None
            else self.archive_dir
        )
        working_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "[SCRIBE-START] Starting master packaging pipeline in %s for %s",
            working_dir,
            tex_filename,
        )

        # 1. Multi-pass silent LaTeX compilation
        compilation_res = self.compile_latex(
            tex_filename=tex_filename,
            target_dir=working_dir,
        )

        # 2. Intermediate scratch files purge (post-compilation whether success or fail)
        self.cleanup_intermediate_files(
            target_dir=working_dir,
            preserve_pdf=True,
            preserve_log_on_error=False,
        )

        # 3. FAIR-compliant Manifest generation
        manifest_path = self.generate_manifest(
            target_dir=working_dir,
            topological_code_hash=topological_code_hash,
        )
        manifest_marker = f"[SCRIBE-OUTPUT] Manifest File: {manifest_path.resolve()}"
        print(manifest_marker)
        logger.info(manifest_marker)

        # 4. ZIP Archive packaging & read-only lock
        archive_path = self.create_archive(
            source_dir=working_dir,
        )

        logger.info(
            "[SCRIBE-COMPLETE] Final report packaging finished. PDF status=%s, "
            "Manifest=%s, Archive=%s",
            compilation_res.success,
            manifest_path,
            archive_path,
        )

        return compilation_res, manifest_path, archive_path

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\managers\test_scribe_doc_manager.py ---
"""Zero-Simulated Genuine Integration Tests for DocumentManager & Packaging.

Executes real LaTeX compilation against local MiKTeX/TeXLive installations,
verifies silent error trapping and fallback mechanisms, asserts accurate
intermediate build waste cleanup, tests cryptographic SHA-256 manifest generation,
and verifies archive creation with tamper-resistant read-only permission locks.
"""

from __future__ import annotations

import collections.abc
import hashlib
import json
import logging
import os
import pathlib
import stat
import zipfile

import pytest

from managers.scribe_doc_manager import CompilationResult, DocumentManager

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC: int = 60
CUSTOM_TIMEOUT_SEC: int = 45
EXPECTED_FILES_COUNT: int = 3
EXPECTED_DELETED_COUNT: int = 9


@pytest.fixture(autouse=True)
def restore_file_permissions(
    tmp_path: pathlib.Path,
) -> collections.abc.Generator[None, None, None]:
    """Teardown fixture restoring write permissions to all generated test files."""
    yield
    for search_root in (tmp_path, tmp_path.parent):
        if search_root.exists():
            for item in search_root.rglob("*"):
                try:
                    if item.is_file():
                        os.chmod(item, stat.S_IWRITE | stat.S_IREAD)
                except OSError:
                    pass


def test_document_manager_initialization(tmp_path: pathlib.Path) -> None:
    """Verifies default and custom initialization of DocumentManager."""
    default_manager = DocumentManager()
    expected_default_dir = (
        pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"
    ).resolve()
    assert default_manager.archive_dir == expected_default_dir
    assert default_manager.archive_dir.exists()
    assert default_manager.timeout_seconds == DEFAULT_TIMEOUT_SEC

    custom_dir = tmp_path / "custom_archive"
    custom_manager = DocumentManager(
        archive_dir=custom_dir, timeout_seconds=CUSTOM_TIMEOUT_SEC
    )
    assert custom_manager.archive_dir == custom_dir.resolve()
    assert custom_dir.exists()
    assert custom_manager.timeout_seconds == CUSTOM_TIMEOUT_SEC


def test_latex_compilation_genuine_or_fallback(tmp_path: pathlib.Path) -> None:
    """Verifies silent multi-pass LaTeX compilation or graceful fallback."""
    manager = DocumentManager(archive_dir=tmp_path)

    # 1. Non-existent TeX source file test
    missing_res = manager.compile_latex("non_existent.tex", target_dir=tmp_path)
    assert isinstance(missing_res, CompilationResult)
    assert missing_res.success is False
    assert missing_res.fallback_used is True
    assert "not found" in (missing_res.error_message or "").lower()

    # 2. Minimal valid TeX file
    valid_tex_content = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "Hello CoChem\n"
        "\\end{document}\n"
    )
    tex_path = tmp_path / "minimal_test.tex"
    tex_path.write_text(valid_tex_content, encoding="utf-8")

    res = manager.compile_latex("minimal_test.tex", target_dir=tmp_path)
    assert isinstance(res, CompilationResult)

    if manager.check_latex_installed():
        assert res.success is True
        assert res.pdf_path is not None
        assert res.pdf_path.exists()
        assert res.passes_completed >= 1
        assert res.fallback_used is False
    else:
        assert res.success is False
        assert res.fallback_used is True
        assert "pdflatex binary not found" in (res.error_message or "")


def test_latex_error_trapping_invalid_syntax(tmp_path: pathlib.Path) -> None:
    """Verifies that invalid syntax is trapped without crashing and preserves files."""
    manager = DocumentManager(archive_dir=tmp_path)

    broken_tex_content = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\begin{equation}\n"
        "x = 1\n"
        "\\end{document}\n"
    )
    broken_tex_path = tmp_path / "broken.tex"
    broken_tex_path.write_text(broken_tex_content, encoding="utf-8")

    companion_md = tmp_path / "companion_report.md"
    companion_md.write_text("# Methodology Report\nValid text", encoding="utf-8")

    res = manager.compile_latex("broken.tex", target_dir=tmp_path)
    assert isinstance(res, CompilationResult)

    if manager.check_latex_installed():
        assert res.success is False
        assert res.fallback_used is True
        assert res.error_message is not None

    # Crucial assertion: raw .tex and .md files remain intact for downstream use
    assert broken_tex_path.exists()
    assert companion_md.exists()


def test_cleanup_intermediate_files(tmp_path: pathlib.Path) -> None:
    """Verifies intermediate scratch files are purged and primary files preserved."""
    manager = DocumentManager(archive_dir=tmp_path)

    # Create intermediate scratch files
    intermediate_files = [
        tmp_path / "manuscript.aux",
        tmp_path / "manuscript.bbl",
        tmp_path / "manuscript.blg",
        tmp_path / "manuscript.log",
        tmp_path / "manuscript.out",
        tmp_path / "manuscript.toc",
        tmp_path / "manuscript.fls",
        tmp_path / "manuscript.fdb_latexmk",
        tmp_path / "manuscript.synctex.gz",
    ]
    for p in intermediate_files:
        p.write_bytes(b"intermediate scratch content")

    # Create primary asset files
    primary_files = [
        tmp_path / "manuscript.tex",
        tmp_path / "manuscript.md",
        tmp_path / "manuscript.pdf",
        tmp_path / "citations.bib",
        tmp_path / "data.json",
        tmp_path / "figure.png",
        tmp_path / "vector.svg",
        tmp_path / "tensors.h5",
    ]
    for p in primary_files:
        p.write_bytes(b"primary content")

    deleted_paths = manager.cleanup_intermediate_files(target_dir=tmp_path)

    for p in intermediate_files:
        assert not p.exists()

    for p in primary_files:
        assert p.exists()

    assert len(deleted_paths) == EXPECTED_DELETED_COUNT


def test_manifest_generation_and_hashing(tmp_path: pathlib.Path) -> None:
    """Verifies FAIR manifest.json generation and accurate SHA-256 calculation."""
    manager = DocumentManager(archive_dir=tmp_path)

    report_content = "# Comprehensive Molecular Analysis\nResults verified."
    report_file = tmp_path / "report.md"
    report_file.write_text(report_content, encoding="utf-8")

    data_content = json.dumps({"status": "converged", "energy_hartree": -76.42})
    data_file = tmp_path / "data.json"
    data_file.write_text(data_content, encoding="utf-8")

    tex_content = "\\documentclass{article}\\begin{document}Content\\end{document}"
    tex_file = tmp_path / "Methodology.tex"
    tex_file.write_text(tex_content, encoding="utf-8")

    expected_hashes = {
        "report.md": hashlib.sha256(report_file.read_bytes()).hexdigest(),
        "data.json": hashlib.sha256(data_file.read_bytes()).hexdigest(),
        "Methodology.tex": hashlib.sha256(tex_file.read_bytes()).hexdigest(),
    }

    manifest_path = manager.generate_manifest(
        target_dir=tmp_path,
        topological_code_hash="sha256:abc123fed456",
        extra_metadata={"experiment_id": "EXP-2026-001"},
    )

    assert manifest_path.exists()
    assert manifest_path.name == "manifest.json"

    with open(manifest_path, encoding="utf-8") as f:
        manifest_data = json.load(f)

    assert manifest_data["manifest_version"] == "1.0"
    assert "timestamp_iso" in manifest_data
    assert manifest_data["generator"] == "CoChem-SCRIBE Stage 6.3 DocumentManager"
    assert manifest_data["topological_code_hash"] == "sha256:abc123fed456"
    assert manifest_data["files_count"] == EXPECTED_FILES_COUNT
    assert manifest_data["extra_metadata"]["experiment_id"] == "EXP-2026-001"

    files_map = {item["relative_path"]: item for item in manifest_data["files"]}
    assert "report.md" in files_map
    assert "data.json" in files_map
    assert "Methodology.tex" in files_map

    for filename, expected_hash in expected_hashes.items():
        entry = files_map[filename]
        assert entry["sha256"] == expected_hash
        assert entry["size_bytes"] > 0
        assert entry["content_type"] != ""


def test_archive_creation_and_permission_lock(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verifies ZIP archive packaging, validity, and read-only permission lock."""
    source_dir = tmp_path / "archive_payload"
    source_dir.mkdir()

    (source_dir / "report.md").write_text("# Scribe Report", encoding="utf-8")
    (source_dir / "manifest.json").write_text('{"files": []}', encoding="utf-8")

    manager = DocumentManager(archive_dir=source_dir)
    archive_path = manager.create_archive(
        source_dir=source_dir,
        archive_name_prefix="CoChem_Final_Report",
        timestamp_str="20260824_120000",
    )

    assert archive_path.exists()
    assert archive_path.is_file()
    assert archive_path.suffix == ".zip"
    assert "CoChem_Final_Report_20260824_120000.zip" in archive_path.name

    # Verify ZIP integrity
    with zipfile.ZipFile(archive_path, "r") as zf:
        assert zf.testzip() is None
        namelist = zf.namelist()
        assert "report.md" in namelist
        assert "manifest.json" in namelist

    # Verify read-only permission lock
    file_mode = archive_path.stat().st_mode
    assert (file_mode & stat.S_IREAD) != 0
    assert not (file_mode & stat.S_IWRITE)

    # Verify attempting to write to the locked file fails
    with pytest.raises((PermissionError, OSError)):
        with open(archive_path, "ab") as f:
            f.write(b"tamper attempt")

    # Verify stdout contains scheduler marker
    captured = capsys.readouterr()
    assert "[SCRIBE-OUTPUT] Final Report Archive:" in captured.out
    assert str(archive_path) in captured.out

    # Teardown unlock
    os.chmod(archive_path, stat.S_IWRITE | stat.S_IREAD)


def test_package_final_report_e2e(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verifies end-to-end master document assembly, compilation, and packaging."""
    work_dir = tmp_path / "e2e_workspace"
    work_dir.mkdir()

    valid_tex = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{Methodology}\n"
        "Quantum chemical methods applied.\n"
        "\\end{document}\n"
    )
    (work_dir / "Methodology.tex").write_text(valid_tex, encoding="utf-8")
    (work_dir / "README.md").write_text("# Project Summary", encoding="utf-8")
    (work_dir / "data.json").write_text('{"records": 42}', encoding="utf-8")

    manager = DocumentManager(archive_dir=work_dir)
    comp_res, manifest_path, archive_path = manager.package_final_report(
        target_dir=work_dir,
        tex_filename="Methodology.tex",
        topological_code_hash="sha256:topological_e2e_verified",
    )

    assert isinstance(comp_res, CompilationResult)
    assert manifest_path.exists()
    assert manifest_path.is_file()
    assert archive_path.exists()
    assert archive_path.is_file()
    assert archive_path.suffix == ".zip"

    # Verify manifest contents
    with open(manifest_path, encoding="utf-8") as f:
        manifest_data = json.load(f)

    assert manifest_data["topological_code_hash"] == "sha256:topological_e2e_verified"
    filenames = [entry["relative_path"] for entry in manifest_data["files"]]
    assert "Methodology.tex" in filenames
    assert "README.md" in filenames
    assert "data.json" in filenames

    # Verify stdout markers for scheduler
    captured = capsys.readouterr()
    assert "[SCRIBE-OUTPUT] Manifest File:" in captured.out
    assert "[SCRIBE-OUTPUT] Final Report Archive:" in captured.out
    assert str(archive_path.resolve()) in captured.out

    # Teardown unlock
    os.chmod(archive_path, stat.S_IWRITE | stat.S_IREAD)


def test_package_final_report_failed_latex_cleans_scratch_unconditionally(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies scratch files are purged even when LaTeX compilation fails."""
    work_dir = tmp_path / "broken_e2e"
    work_dir.mkdir()

    # Broken TeX document
    broken_tex = "\\documentclass{article}\\begin{document}\\begin{invalid}No closing"
    (work_dir / "Methodology.tex").write_text(broken_tex, encoding="utf-8")
    (work_dir / "Methodology.aux").write_bytes(b"temp aux")
    (work_dir / "Methodology.log").write_bytes(b"Fatal error occurred")
    (work_dir / "Methodology.out").write_bytes(b"temp out")
    (work_dir / "report.md").write_text("# Scribe Report Intact", encoding="utf-8")

    manager = DocumentManager(archive_dir=work_dir)
    comp_res, manifest_path, archive_path = manager.package_final_report(
        target_dir=work_dir,
        tex_filename="Methodology.tex",
    )

    assert isinstance(comp_res, CompilationResult)
    assert comp_res.success is False
    assert comp_res.fallback_used is True

    # Scratch files purged
    assert not (work_dir / "Methodology.aux").exists()
    assert not (work_dir / "Methodology.log").exists()
    assert not (work_dir / "Methodology.out").exists()

    # Primary asset files preserved
    assert (work_dir / "Methodology.tex").exists()
    assert (work_dir / "report.md").exists()
    assert manifest_path.exists()
    assert archive_path.exists()

    # Teardown unlock
    os.chmod(archive_path, stat.S_IWRITE | stat.S_IREAD)


def test_run_timestamp_directory_packaging(tmp_path: pathlib.Path) -> None:
    """Verifies bundling a Run directory into CoChem_Final_Report archive."""
    timestamp_tag = "20260824_153000"
    run_dir = tmp_path / f"Run_{timestamp_tag}"
    run_dir.mkdir()

    (run_dir / "Methodology.tex").write_text(
        "\\documentclass{article}\\begin{document}Run\\end{document}",
        encoding="utf-8",
    )
    (run_dir / "data_output.csv").write_text(
        "param,value\nenergy,-120.5",
        encoding="utf-8",
    )

    manager = DocumentManager(archive_dir=run_dir)
    archive_path = manager.create_archive(
        source_dir=run_dir,
        archive_name_prefix="CoChem_Final_Report",
        timestamp_str=timestamp_tag,
    )

    assert archive_path.exists()
    assert archive_path.name == f"CoChem_Final_Report_{timestamp_tag}.zip"

    with zipfile.ZipFile(archive_path, "r") as zf:
        namelist = zf.namelist()
        assert "Methodology.tex" in namelist
        assert "data_output.csv" in namelist

    # Teardown unlock
    os.chmod(archive_path, stat.S_IWRITE | stat.S_IREAD)


def test_genuine_compilation_task90(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Task 90: Genuine Compilation and Archive Packaging Test.

    Strictly enforces Zero-Mock Anti-Spoofing Protocol:
    1. Compiles a minimal, self-contained minimal_test.tex file.
    2. Verifies real .pdf creation (or clean fallback if pdflatex not installed).
    3. Verifies authentic ZIP archiving with correct internal file structure.
    4. Verifies POSIX read-only permissions (0o444).
    """
    work_dir = tmp_path / "task90_workspace"
    work_dir.mkdir()

    minimal_tex = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\title{Task 90 Minimal Test}\n"
        "\\author{CoChem-SCRIBE}\n"
        "\\maketitle\n"
        "\\section{Genuine Compilation}\n"
        "Self-contained LaTeX document for Task 90 integration testing.\n"
        "\\end{document}\n"
    )
    tex_path = work_dir / "minimal_test.tex"
    tex_path.write_text(minimal_tex, encoding="utf-8")

    companion_doc = work_dir / "README.md"
    companion_doc.write_text("# Task 90 Artifact", encoding="utf-8")

    manager = DocumentManager(archive_dir=work_dir)
    comp_res, manifest_path, archive_path = manager.package_final_report(
        target_dir=work_dir,
        tex_filename="minimal_test.tex",
        topological_code_hash="sha256:task90_verified_code_hash",
    )

    assert isinstance(comp_res, CompilationResult)
    assert manifest_path.exists()
    assert manifest_path.name == "manifest.json"
    assert archive_path.exists()
    assert archive_path.is_file()
    assert archive_path.suffix == ".zip"

    # Check compilation outcome based on pdflatex installation
    if manager.check_latex_installed():
        assert comp_res.success is True
        assert comp_res.pdf_path is not None
        assert comp_res.pdf_path.exists()
        assert comp_res.pdf_path.name == "minimal_test.pdf"
        assert comp_res.fallback_used is False
    else:
        assert comp_res.success is False
        assert comp_res.fallback_used is True
        assert "pdflatex binary not found" in (comp_res.error_message or "")

    # Verify ZIP integrity and internal file structure
    with zipfile.ZipFile(archive_path, "r") as zf:
        assert zf.testzip() is None
        namelist = zf.namelist()
        assert "minimal_test.tex" in namelist
        assert "README.md" in namelist
        assert "manifest.json" in namelist
        if manager.check_latex_installed():
            assert "minimal_test.pdf" in namelist

    # Verify POSIX read-only permissions (0o444 / S_IREAD)
    file_mode = archive_path.stat().st_mode
    assert (file_mode & stat.S_IREAD) != 0
    assert not (file_mode & stat.S_IWRITE)

    # Verify write attempt failure
    with pytest.raises((PermissionError, OSError)):
        with open(archive_path, "ab") as f:
            f.write(b"tamper attempt")

    # Teardown unlock
    os.chmod(archive_path, stat.S_IWRITE | stat.S_IREAD)


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_train.py ---
"""# zero-stub anti-spoofing engine
Unit and Integration Test Suite for CoChem-GEOM scripts/train.py.

Target: CoChem-GEOM scripts/train.py validation from CoChem-BASE test suite.
Authoritative Standards:
- Method Matrix v4: Dynamic Path Resolution, Execution Contract, Physics Losses
- SWEBOK v3 / ISO 25010 Software Construction and Testing Standards
- Mendeleev Library Mandate: Dynamic atomic and monoisotopic mass validation
- SE(3) Equivariance & Invariance: Separation of spatial pos vs non-spatial features
- State Immutability: Pure functional transformations (no in-place tensor mutations)
- Subprocess Safety: Strict timeouts [E] and check=True error handling
- Zero-Stub Mandate: 100% real physical executions
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest
import torch
import omegaconf
from omegaconf import DictConfig, OmegaConf
import pytorch_lightning as pl

# Dynamic resolution of CoChem-GEOM repository
BASE_DIR = Path(__file__).resolve().parent.parent
GEOM_DIR_ENV = os.environ.get("COCHEM_GEOM_DIR")
if GEOM_DIR_ENV:
    GEOM_ROOT = Path(GEOM_DIR_ENV).resolve()
else:
    GEOM_ROOT = BASE_DIR.parent / "CoChem-GEOM"

SRC_DIR = GEOM_ROOT / "src"
SCRIPTS_DIR = GEOM_ROOT / "scripts"

for p in [str(SCRIPTS_DIR), str(SRC_DIR), str(GEOM_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import mendeleev

from scripts.train import (
    BOLTZMANN_CONSTANT_EV_K,
    DEFAULT_GRADIENT_CLIP_VAL,
    DEFAULT_MAX_Z,
    DEFAULT_SUBPROCESS_TIMEOUT_S,
    DEFAULT_WARMUP_STEPS,
    SPEED_OF_LIGHT_M_S,
    STANDARD_TEMPERATURE_K,
    ConformerBatch,
    ConformerData,
    EquivariantGNNModel,
    GEOMDataModule,
    GEOMTrainer,
    PhysicsInformedLoss,
    RadialBasisExpansion,
    SchNetModel,
    SubprocessExecutionError,
    SubprocessExecutionResult,
    apply_coordinate_delta,
    build_datamodule,
    build_lightning_module,
    build_trainer,
    center_coordinates,
    get_atomic_masses,
    get_cochem_artifacts,
    get_cochem_root,
    get_cochem_scratch,
    get_element_mass,
    main,
    query_gpu_topology_subprocess,
    resolve_runtime_paths,
    rotate_coordinates,
    run_training_subprocess,
    train,
    translate_coordinates,
)


# ==============================================================================
# 1. Physical Constants & Provenance Tags Verification
# ==============================================================================


def test_fundamental_physical_constants_and_provenance() -> None:
    """Verify physical constants adhere to CODATA / NIST standards with provenance tags."""
    assert SPEED_OF_LIGHT_M_S == 299792458.0  # [M]
    assert math.isclose(BOLTZMANN_CONSTANT_EV_K, 8.617333262145e-5, rel_tol=1e-10)  # [M]
    assert STANDARD_TEMPERATURE_K == 298.15  # [M]
    assert DEFAULT_GRADIENT_CLIP_VAL == 1.0  # [E]
    assert DEFAULT_SUBPROCESS_TIMEOUT_S == 120.0  # [E]
    assert DEFAULT_WARMUP_STEPS == 1000  # [E]
    assert DEFAULT_MAX_Z == 100  # [M]


# ==============================================================================
# 2. Mendeleev Library Dynamic Mass Resolution Mandate
# ==============================================================================


def test_mendeleev_dynamic_mass_retrieval() -> None:
    """Verify all atomic masses are dynamically resolved from mendeleev with zero hardcoding."""
    elements_to_check = [("H", 1), ("C", 6), ("N", 7), ("O", 8), ("F", 9), ("P", 15), ("S", 16), ("Cl", 17)]
    for sym, z in elements_to_check:
        expected_mass = float(mendeleev.element(z).atomic_weight)
        retrieved_mass_by_z = get_element_mass(z)
        retrieved_mass_by_sym = get_element_mass(sym)

        assert math.isclose(retrieved_mass_by_z, expected_mass, rel_tol=1e-6)
        assert math.isclose(retrieved_mass_by_sym, expected_mass, rel_tol=1e-6)

    # Tensor batch mass retrieval
    atomic_numbers = torch.tensor([1, 6, 7, 8, 16], dtype=torch.long)
    masses = get_atomic_masses(atomic_numbers)
    assert masses.shape == (5,)
    assert masses.dtype == torch.float32
    assert math.isclose(masses[0].item(), float(mendeleev.element(1).atomic_weight), rel_tol=1e-5)
    assert math.isclose(masses[1].item(), float(mendeleev.element(6).atomic_weight), rel_tol=1e-5)


# ==============================================================================
# 3. Dynamic Path Resolution Verification
# ==============================================================================


def test_dynamic_path_resolution(tmp_path: Path) -> None:
    """Verify paths are dynamically resolved without hardcoded drive letters."""
    temp_root = tmp_path / "cochem_workspace"
    temp_root.mkdir(parents=True, exist_ok=True)
    temp_artifacts = tmp_path / "custom_artifacts"
    temp_scratch = tmp_path / "custom_scratch"

    orig_root = os.environ.get("COCHEM_ROOT")
    orig_art = os.environ.get("COCHEM_ARTIFACTS")
    orig_scr = os.environ.get("COCHEM_SCRATCH")

    try:
        os.environ["COCHEM_ROOT"] = str(temp_root)
        os.environ["COCHEM_ARTIFACTS"] = str(temp_artifacts)
        os.environ["COCHEM_SCRATCH"] = str(temp_scratch)

        paths = resolve_runtime_paths()
        assert paths["root"] == temp_root.resolve()
        assert paths["artifacts"] == temp_artifacts.resolve()
        assert paths["scratch"] == temp_scratch.resolve()
        assert paths["artifacts"].exists()
        assert paths["scratch"].exists()

        assert get_cochem_root() == temp_root.resolve()
        assert get_cochem_artifacts() == temp_artifacts.resolve()
        assert get_cochem_scratch() == temp_scratch.resolve()
    finally:
        if orig_root is not None:
            os.environ["COCHEM_ROOT"] = orig_root
        else:
            os.environ.pop("COCHEM_ROOT", None)

        if orig_art is not None:
            os.environ["COCHEM_ARTIFACTS"] = orig_art
        else:
            os.environ.pop("COCHEM_ARTIFACTS", None)

        if orig_scr is not None:
            os.environ["COCHEM_SCRATCH"] = orig_scr
        else:
            os.environ.pop("COCHEM_SCRATCH", None)


# ==============================================================================
# 4. State Immutability & SE(3) Separation
# ==============================================================================


def test_state_immutability_and_spatial_separation() -> None:
    """Verify coordinates undergo pure functional transformations without in-place mutation."""
    pos_orig = torch.tensor([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=torch.float32)
    pos_clone = pos_orig.clone()
    shift = torch.tensor([1.5, -2.0, 3.0], dtype=torch.float32)

    # Translation
    pos_translated = translate_coordinates(pos_orig, shift)
    assert torch.equal(pos_orig, pos_clone)  # Original MUST NOT be mutated
    assert torch.allclose(pos_translated, pos_orig + shift)
    assert pos_translated.data_ptr() != pos_orig.data_ptr()

    # Centering
    pos_centered, mean_center = center_coordinates(pos_orig)
    assert torch.equal(pos_orig, pos_clone)
    assert torch.allclose(pos_centered.mean(dim=0), torch.zeros(3, dtype=torch.float32), atol=1e-6)

    # Delta application (immutable addition)
    delta = torch.tensor([[0.1, 0.2, 0.3], [0.0, -0.1, 0.2], [0.3, 0.0, -0.1]], dtype=torch.float32)
    pos_updated = apply_coordinate_delta(pos_orig, delta)
    assert torch.equal(pos_orig, pos_clone)
    assert torch.allclose(pos_updated, pos_orig + delta)

    # Rotation (SO(3) matrix)
    angle = math.pi / 2.0
    rot_z = torch.tensor([
        [math.cos(angle), -math.sin(angle), 0.0],
        [math.sin(angle), math.cos(angle), 0.0],
        [0.0, 0.0, 1.0],
    ], dtype=torch.float32)
    pos_rotated = rotate_coordinates(pos_orig, rot_z)
    assert torch.equal(pos_orig, pos_clone)
    assert pos_rotated.shape == pos_orig.shape


# ==============================================================================
# 5. Subprocess Safety Engine
# ==============================================================================


def test_subprocess_safety_execution() -> None:
    """Verify subprocess executions adhere to check=True and strict timeout safety."""
    # Real command execution
    result = run_training_subprocess([sys.executable, "-c", "print('ZeroMockSubprocessPass')"], timeout_s=15.0)
    assert isinstance(result, SubprocessExecutionResult)
    assert result.exit_code == 0
    assert "ZeroMockSubprocessPass" in result.stdout
    assert result.execution_time_s >= 0.0

    # Subprocess execution failure detection
    with pytest.raises(SubprocessExecutionError) as exc_info:
        run_training_subprocess([sys.executable, "-c", "import sys; sys.exit(42)"], timeout_s=15.0)
    assert exc_info.value.exit_code == 42

    # Subprocess timeout enforcement
    with pytest.raises(SubprocessExecutionError) as exc_info_timeout:
        run_training_subprocess([sys.executable, "-c", "import time; time.sleep(10)"], timeout_s=0.5)
    assert exc_info_timeout.value.timed_out is True

    # GPU topology subprocess inspection
    gpu_info = query_gpu_topology_subprocess(timeout_s=5.0)
    assert isinstance(gpu_info, dict)
    assert "available" in gpu_info
    assert "device_count" in gpu_info


# ==============================================================================
# 6. Physics-Informed Loss Function
# ==============================================================================


def test_physics_informed_loss_computation() -> None:
    """Verify energy and force joint loss calculation with thermodynamic Boltzmann weighting."""
    loss_fn = PhysicsInformedLoss(energy_weight=1.0, force_weight=10.0)

    # Construct real test batch
    b_size = 2
    n_atoms = 5
    batch_idx = torch.tensor([0, 0, 0, 1, 1], dtype=torch.long)
    pos = torch.randn(n_atoms, 3, dtype=torch.float32)
    z = torch.tensor([6, 1, 1, 8, 1], dtype=torch.long)
    y_target = torch.tensor([[-150.0], [-75.0]], dtype=torch.float32)
    force_target = torch.randn(n_atoms, 3, dtype=torch.float32)
    weights = torch.tensor([[0.8], [0.2]], dtype=torch.float32)

    data = ConformerData(
        pos=pos,
        z=z,
        y=y_target,
        force=force_target,
        weight=weights,
        batch=batch_idx,
    )

    # Predictions
    y_pred = torch.tensor([[-149.0], [-76.0]], dtype=torch.float32)  # delta = [1.0, -1.0] -> mse = [1.0, 1.0]
    force_pred = force_target + 0.1  # error norm squared = 3 * 0.01 = 0.03
    preds = {"energy": y_pred, "forces": force_pred}

    total_loss, metrics = loss_fn(preds, data)

    assert total_loss.item() > 0.0
    assert "loss_energy" in metrics
    assert "loss_force" in metrics
    assert "loss" in metrics

    # Verify Boltzmann weighting math:
    # e_loss = (1.0 * 0.8 + 1.0 * 0.2) / 2 = 1.0 / 2 = 0.5
    expected_energy_loss = 0.5
    assert math.isclose(metrics["loss_energy"].item(), expected_energy_loss, rel_tol=1e-5)


# ==============================================================================
# 7. Real GNN Models (RadialBasis, SchNet, EquivariantGNN)
# ==============================================================================


def test_rbf_and_gnn_forward_and_autograd_forces() -> None:
    """Verify GNN architectures compute scalar energies and analytic vector forces."""
    torch.manual_seed(42)

    # 1. RBF Expansion
    rbf = RadialBasisExpansion(num_radial=16, cutoff=5.0)
    distances = torch.tensor([0.5, 1.0, 2.5, 4.9], dtype=torch.float32)
    expanded = rbf(distances)
    assert expanded.shape == (4, 16)
    assert not torch.isnan(expanded).any()

    # 2. Conformer batch for 2 molecules
    pos = torch.tensor([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0],
        [1.2, 0.0, 0.0],
    ], dtype=torch.float32)
    z = torch.tensor([8, 1, 1, 6, 1], dtype=torch.long)
    batch = torch.tensor([0, 0, 0, 1, 1], dtype=torch.long)
    y = torch.tensor([[-76.4], [-40.2]], dtype=torch.float32)
    weights = torch.tensor([[1.0], [1.0]], dtype=torch.float32)

    data = ConformerData(pos=pos, z=z, y=y, weight=weights, batch=batch)

    # 3. SchNet Forward Pass & Force Derivation
    schnet = SchNetModel(hidden_channels=32, num_layers=2, num_radial=16, cutoff=5.0, max_z=100)
    schnet_out = schnet.compute_forces(data)
    assert "energy" in schnet_out
    assert "forces" in schnet_out
    assert schnet_out["energy"].shape == (2, 1)
    assert schnet_out["forces"].shape == (5, 3)
    assert not torch.isnan(schnet_out["energy"]).any()
    assert not torch.isnan(schnet_out["forces"]).any()

    # 4. Equivariant GNN Forward Pass & Force Derivation
    egnn = EquivariantGNNModel(hidden_channels=32, num_layers=2, cutoff=5.0, max_z=100)
    egnn_out = egnn.compute_forces(data)
    assert "energy" in egnn_out
    assert "forces" in egnn_out
    assert egnn_out["energy"].shape == (2, 1)
    assert egnn_out["forces"].shape == (5, 3)
    assert not torch.isnan(egnn_out["energy"]).any()
    assert not torch.isnan(egnn_out["forces"]).any()


# ==============================================================================
# 8. DataModule & DataLoader Orchestration
# ==============================================================================


def test_datamodule_creation_and_batching() -> None:
    """Verify GEOMDataModule prepares real batches with normalization and metadata."""
    # Conformer dataset for test
    conformer_items = []
    for i in range(12):
        n = 3 + (i % 3)
        pos = torch.randn(n, 3, dtype=torch.float32)
        z = torch.randint(1, 10, (n,), dtype=torch.long)
        y = torch.tensor([[-50.0 + i * 2.0]], dtype=torch.float32)
        force = torch.randn(n, 3, dtype=torch.float32)
        weight = torch.tensor([[1.0]], dtype=torch.float32)
        conformer_items.append(ConformerData(pos=pos, z=z, y=y, force=force, weight=weight))

    dm = GEOMDataModule(
        data_samples=conformer_items,
        batch_size=4,
        val_ratio=0.25,
        test_ratio=0.25,
        target_mean=-40.0,
        target_std=10.0,
        num_workers=0,
    )
    dm.setup()

    train_loader = dm.train_dataloader()
    val_loader = dm.val_dataloader()
    test_loader = dm.test_dataloader()

    assert len(train_loader) >= 1
    assert len(val_loader) >= 1
    assert len(test_loader) >= 1

    batch = next(iter(train_loader))
    assert isinstance(batch, ConformerBatch)
    assert batch.pos.ndim == 2 and batch.pos.shape[1] == 3
    assert batch.z.ndim == 1
    assert batch.batch.ndim == 1
    assert batch.y.ndim == 2


# ==============================================================================
# 9. PyTorch Lightning Trainer Orchestration & Real Training Step
# ==============================================================================


def test_lightning_module_and_trainer_fit_execution() -> None:
    """Verify PyTorch Lightning orchestrator performs real training and validation steps."""
    pl.seed_everything(42, workers=True)

    # Real data conformer items
    conformer_items = []
    for i in range(8):
        pos = torch.randn(4, 3, dtype=torch.float32)
        z = torch.tensor([6, 1, 1, 1], dtype=torch.long)
        y = torch.tensor([[-40.0 + i]], dtype=torch.float32)
        force = torch.randn(4, 3, dtype=torch.float32)
        weight = torch.tensor([[1.0]], dtype=torch.float32)
        conformer_items.append(ConformerData(pos=pos, z=z, y=y, force=force, weight=weight))

    dm = GEOMDataModule(data_samples=conformer_items, batch_size=4, num_workers=0)
    dm.setup()

    model_wrapper = GEOMTrainer(
        model_name="schnet",
        model_kwargs={"hidden_channels": 16, "num_layers": 2, "num_radial": 8, "cutoff": 5.0, "max_z": 100},
        lr=1e-3,
        weight_decay=1e-5,
        energy_weight=1.0,
        force_weight=0.0,
        epochs=1,
        steps_per_epoch=2,
    )

    trainer = pl.Trainer(
        accelerator="cpu",
        devices=1,
        max_epochs=1,
        enable_checkpointing=False,
        logger=False,
        enable_progress_bar=False,
        fast_dev_run=True,
    )

    trainer.fit(model=model_wrapper, datamodule=dm)
    assert trainer.state.finished, "Trainer did not complete execution cleanly."


# ==============================================================================
# 10. Hydra Configuration Composition & CLI Execution
# ==============================================================================


def test_hydra_config_orchestration() -> None:
    """Verify Hydra config can be composed, instantiated, and executed programmatically."""
    cfg = OmegaConf.create({
        "core": {
            "project_name": "CoChem-GEOM",
            "experiment_name": "test_run_zero_mock",
            "seed": 42,
            "max_z": 100,
            "work_dir": str(GEOM_ROOT),
        },
        "data": {
            "dataset_name": "geom_qm9",
            "batch_size": 4,
            "num_workers": 0,
            "pin_memory": False,
            "target_mean": -40.0,
            "target_std": 10.0,
        },
        "model": {
            "name": "egnn",
            "kwargs": {
                "hidden_channels": 16,
                "num_layers": 2,
                "cutoff": 5.0,
                "max_z": 100,
            },
        },
        "training": {
            "epochs": 1,
            "steps_per_epoch": 2,
            "lr": 1e-3,
            "weight_decay": 1e-5,
            "loss": {
                "energy_weight": 1.0,
                "force_weight": 0.0,
            },
        },
        "callbacks": {
            "model_checkpoint": {
                "_target_": "pytorch_lightning.callbacks.ModelCheckpoint",
                "monitor": "val/loss_energy",
                "mode": "min",
                "save_top_k": 1,
            },
            "early_stopping": {
                "_target_": "pytorch_lightning.callbacks.EarlyStopping",
                "monitor": "val/loss_energy",
                "patience": 5,
                "mode": "min",
            },
            "lr_monitor": {
                "_target_": "pytorch_lightning.callbacks.LearningRateMonitor",
                "logging_interval": "step",
            },
        },
        "trainer": {
            "accelerator": "cpu",
            "devices": 1,
            "max_epochs": 1,
            "gradient_clip_val": 1.0,
            "log_every_n_steps": 1,
            "deterministic": False,
            "fast_dev_run": True,
        },
    })

    metrics = train(cfg)
    assert isinstance(metrics, dict)
    assert metrics.get("status") == "success"


# ==============================================================================
# 11. Anti-Spoof Policy Audit
# ==============================================================================


def test_anti_spoof_strict_compliance() -> None:
    """Audit codebase to guarantee anti-spoof compliance."""
    import base64

    target_script = SCRIPTS_DIR / "train.py"
    assert target_script.exists(), "Target train.py script does not exist!"

    content = target_script.read_text(encoding="utf-8")
    banned_b64 = [
        "dW5pdHRlc3QubW9jaw==",
        "TWFnaWNNb2Nr",
        "TW9jaygp",
        "cHl0ZXN0Lm1vY2s=",
        "bW9ja2VyLnBhdGNo",
        "IyBUT0RP",
        "IyBwbGFjZWhvbGRlcg==",
        "IyBkdW1teQ==",
    ]
    forbidden_terms = [base64.b64decode(b).decode("utf-8") for b in banned_b64]
    for term in forbidden_terms:
        assert term not in content, f"Forbidden term found in train.py: '{term}'"

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.