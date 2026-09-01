"""Physical Verification Test Suite for teamwork_preview_auditor_1/forensic_check.py.

Verifies encoding, path sanitization, template parity comparison logic,
leak scanning mechanisms, worker integrity checks, and CLI execution.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest

from cochem_base.path_sanitization import (
    find_path_leaks,
    get_agents_dir,
)

# Import the module under test from .agents/teamwork_preview_auditor_1/forensic_check.py
sys.path.insert(0, str(get_agents_dir() / "teamwork_preview_auditor_1"))
import forensic_check
from forensic_check import (
    MatchStatus,
    check_agent_md_leaks,
    check_subdirectory_leaks,
    check_template_content_parity,
    check_worker_integrity,
    main,
    run_forensic_suite,
)


@pytest.fixture
def forensic_script_path() -> Path:
    """Fixture providing the path to forensic_check.py."""
    path = get_agents_dir() / "teamwork_preview_auditor_1" / "forensic_check.py"
    assert path.exists(), f"forensic_check.py does not exist at {path}"
    return path


def test_forensic_check_exists_and_non_empty(forensic_script_path: Path) -> None:
    """Verify that forensic_check.py exists and has substantive content."""
    stat = forensic_script_path.stat()
    assert stat.st_size > 2000, f"File size too small ({stat.st_size} bytes)"
    assert forensic_script_path.is_file()


def test_forensic_check_encoding_and_line_endings(forensic_script_path: Path) -> None:
    """Validate that forensic_check.py has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = forensic_script_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "forensic_check.py contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "forensic_check.py contains Windows CRLF line endings"
    assert b"\n" in raw_bytes, "forensic_check.py missing newline characters"


def test_forensic_check_path_sanitization_and_no_leaks(forensic_script_path: Path) -> None:
    """Validate that forensic_check.py contains zero personal path leaks."""
    content = forensic_script_path.read_text(encoding="utf-8")
    leaks = find_path_leaks(content)
    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s) in forensic_check.py: {leaks}"


def test_template_content_parity_identical(tmp_path: Path) -> None:
    """Test check_template_content_parity with perfectly matching files after sanitization."""
    src_dir = tmp_path / "templates"
    tgt_dir = tmp_path / "agents"
    src_dir.mkdir()
    tgt_dir.mkdir()

    # Create dummy template with a local path
    dummy_home = Path.home()
    template_content = f"# Agent Definition\nHome: {dummy_home}\n"
    (src_dir / "test-agent.agent.md").write_text(template_content, encoding="utf-8")

    # Create target with sanitized token
    target_content = "# Agent Definition\nHome: <USER_HOME>\n"
    (tgt_dir / "test-agent.agent.md").write_text(target_content, encoding="utf-8")

    report = check_template_content_parity(source_dir=src_dir, target_dir=tgt_dir)

    assert report.source_count == 1
    assert report.target_count == 1
    assert report.passed_count == 1
    assert report.failed_count == 0
    assert report.missing_count == 0
    assert report.is_clean is True
    assert report.details[0].status == MatchStatus.PASS


def test_template_content_parity_mismatch(tmp_path: Path) -> None:
    """Test check_template_content_parity detecting content mismatch."""
    src_dir = tmp_path / "templates"
    tgt_dir = tmp_path / "agents"
    src_dir.mkdir()
    tgt_dir.mkdir()

    (src_dir / "test-agent.agent.md").write_text("Alpha Content\n", encoding="utf-8")
    (tgt_dir / "test-agent.agent.md").write_text("Beta Content\n", encoding="utf-8")

    report = check_template_content_parity(source_dir=src_dir, target_dir=tgt_dir)

    assert report.passed_count == 0
    assert report.failed_count == 1
    assert report.is_clean is False
    assert report.details[0].status == MatchStatus.FAIL


def test_template_content_parity_missing_target(tmp_path: Path) -> None:
    """Test check_template_content_parity detecting missing target file."""
    src_dir = tmp_path / "templates"
    tgt_dir = tmp_path / "agents"
    src_dir.mkdir()
    tgt_dir.mkdir()

    (src_dir / "missing.agent.md").write_text("Content\n", encoding="utf-8")

    report = check_template_content_parity(source_dir=src_dir, target_dir=tgt_dir)

    assert report.missing_count == 1
    assert report.is_clean is False
    assert report.details[0].status == MatchStatus.MISSING


def test_template_content_parity_nonexistent_src(tmp_path: Path) -> None:
    """Test check_template_content_parity with nonexistent template dir."""
    nonexistent = tmp_path / "does_not_exist"
    tgt_dir = tmp_path / "agents"
    tgt_dir.mkdir()

    report = check_template_content_parity(source_dir=nonexistent, target_dir=tgt_dir)
    assert report.source_count == 0
    assert report.is_clean is True
    assert report.details[0].status == MatchStatus.SKIPPED


def test_agent_md_leaks_detection(tmp_path: Path) -> None:
    """Test check_agent_md_leaks detecting personal path leaks."""
    tgt_dir = tmp_path / "agents"
    tgt_dir.mkdir()

    # Clean file
    (tgt_dir / "clean.agent.md").write_text("Role: <USER_HOME>\n", encoding="utf-8")
    # Leaking file
    dummy_home = Path.home()
    (tgt_dir / "leaking.agent.md").write_text(f"Role: {dummy_home}\n", encoding="utf-8")

    report = check_agent_md_leaks(target_dir=tgt_dir)

    assert report.files_scanned == 2
    assert report.leak_count == 1
    assert report.is_clean is False
    assert report.leaks[0].file_rel_path == "leaking.agent.md"


def test_subdirectory_leaks_and_exclusions(tmp_path: Path) -> None:
    """Test check_subdirectory_leaks respecting exclusions and finding leaks."""
    tgt_dir = tmp_path / "agents"
    tgt_dir.mkdir()

    # Excluded folder
    auditor_dir = tgt_dir / "teamwork_preview_auditor_1"
    auditor_dir.mkdir()
    (auditor_dir / "audit.md").write_text(f"Path: {Path.home()}\n", encoding="utf-8")

    # Excluded file
    (tgt_dir / "ORIGINAL_REQUEST.md").write_text(f"Path: {Path.home()}\n", encoding="utf-8")

    # Worker folder with a leak
    worker_dir = tgt_dir / "worker_1"
    worker_dir.mkdir()
    (worker_dir / "report.md").write_text(f"Path: {Path.home()}\n", encoding="utf-8")

    report = check_subdirectory_leaks(target_dir=tgt_dir)

    assert report.leak_count == 1
    assert "worker_1" in report.leaks[0].file_rel_path


def test_worker_integrity_and_anomalies(tmp_path: Path) -> None:
    """Test check_worker_integrity for compliance and deception detection."""
    tgt_dir = tmp_path / "agents"
    tgt_dir.mkdir()

    # 1. Clean worker
    w1 = tgt_dir / "teamwork_preview_clean_worker"
    w1.mkdir()
    (w1 / "BRIEFING.md").write_text("# Briefing\n", encoding="utf-8")
    (w1 / "DISPATCH.md").write_text("# Dispatch\n", encoding="utf-8")
    (w1 / "handoff.md").write_text("# Handoff\n", encoding="utf-8")
    (w1 / "progress.md").write_text("# Progress\n", encoding="utf-8")
    (w1 / "script.py").write_text("print('Physical execution test')\n", encoding="utf-8")

    # 2. Worker with violation
    w2 = tgt_dir / "teamwork_preview_deceptive_worker"
    w2.mkdir()
    (w2 / "BRIEFING.md").write_text("# Briefing\n", encoding="utf-8")
    bad_code = "from unittest." + "mo" + "ck import Magic" + "Mo" + "ck\nm = Magic" + "Mo" + "ck()\n"
    (w2 / "fake_test.py").write_text(bad_code, encoding="utf-8")

    report = check_worker_integrity(target_dir=tgt_dir)

    assert report.workers_checked == 2
    assert report.clean_workers == 1
    assert report.is_clean is False

    w2_detail = next(d for d in report.details if d.worker_name == "teamwork_preview_deceptive_worker")
    assert w2_detail.is_clean is False
    assert len(w2_detail.mock_violations) >= 2


def test_run_forensic_suite_on_actual_repo() -> None:
    """Test run_forensic_suite against the actual repository directory."""
    report = run_forensic_suite(verbose=False)
    assert report.timestamp is not None
    assert report.agent_leak_scan.is_clean is True
    assert report.agent_leak_scan.files_scanned == 15
    assert report.worker_integrity.is_clean is True
    assert report.worker_integrity.workers_checked >= 1


def test_main_cli(capsys: pytest.CaptureFixture[str]) -> None:
    """Test main CLI entrypoint with JSON output."""
    exit_code = main(["--json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "content_match" in data
    assert "agent_leak_scan" in data
    assert "worker_integrity" in data
    assert data["agent_leak_scan"]["is_clean"] is True
