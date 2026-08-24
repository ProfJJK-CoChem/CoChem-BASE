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

import datetime
import hashlib
import json
import logging
import mimetypes
import os
import pathlib
import shutil
import stat
import subprocess
from dataclasses import dataclass
from typing import Any, ClassVar

logger = logging.getLogger(__name__)

FALLBACK_TOPOLOGICAL_HASH: str = "sha256:" + "0" * 64
DEFAULT_TIMEOUT_SECONDS: int = 60
CHUNK_SIZE_BYTES: int = 65536


@dataclass
class CompilationResult:
    """Encapsulates the status and telemetry of the LaTeX compilation process."""

    success: bool
    pdf_path: pathlib.Path | None = None
    log_path: pathlib.Path | None = None
    error_message: str | None = None
    passes_completed: int = 0
    fallback_used: bool = False


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

        manifest_data: dict[str, Any] = {
            "manifest_version": "1.0",
            "timestamp_iso": timestamp_iso,
            "generator": "CoChem-SCRIBE Stage 6.3 DocumentManager",
            "topological_code_hash": (
                topological_code_hash
                if topological_code_hash is not None
                else FALLBACK_TOPOLOGICAL_HASH
            ),
            "files_count": len(files_list),
            "files": files_list,
        }

        if extra_metadata:
            manifest_data["extra_metadata"] = extra_metadata

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

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
            readonly_mode = stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH
            os.chmod(file_path, readonly_mode)
            logger.info(
                "[SCRIBE-SECURITY] Applied read-only permission lock to: %s", file_path
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

        # 2. Intermediate scratch files purge
        self.cleanup_intermediate_files(
            target_dir=working_dir,
            preserve_pdf=True,
            preserve_log_on_error=not compilation_res.success,
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
