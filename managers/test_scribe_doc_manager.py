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
    """Verifies that intermediate scratch files are purged even when LaTeX compilation fails."""
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
    """Verifies bundling a Run_[TIMESTAMP] directory into CoChem_Final_Report_[TIMESTAMP].zip."""
    timestamp_tag = "20260824_153000"
    run_dir = tmp_path / f"Run_{timestamp_tag}"
    run_dir.mkdir()

    (run_dir / "Methodology.tex").write_text("\\documentclass{article}\\begin{document}Run\\end{document}", encoding="utf-8")
    (run_dir / "data_output.csv").write_text("param,value\nenergy,-120.5", encoding="utf-8")

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

