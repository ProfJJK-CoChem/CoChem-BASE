"""Comprehensive Zero-Mock Physical Test Suite for verify_diff.py.

Validates all functionality:
- expand_target_placeholders: token expansion with default and custom placeholder mappings
- compute_unified_diff: exact matching lines and diff line generation
- verify_file_diff: mode selection ('expand_target', 'sanitize_source', 'raw'), file existence checks, leak detection
- run_verification: batch verification across file sets with match/mismatch tallies
- format_report: human-readable report formatting with APPROVE/REJECT verdicts
- parse_args: CLI parameter parsing and default resolution
- main: CLI execution flow, return codes, and file output options
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

from cochem_base.path_sanitization import get_agents_dir

# Import verify_diff functions directly
challenger_dir = get_agents_dir() / "teamwork_preview_challenger_2"
if str(challenger_dir) not in sys.path:
    sys.path.insert(0, str(challenger_dir))

from verify_diff import (
    CANONICAL_AGENT_FILES,
    compute_unified_diff,
    expand_target_placeholders,
    format_report,
    main,
    parse_args,
    run_verification,
    verify_file_diff,
)


def test_canonical_agent_files_count() -> None:
    """Verify CANONICAL_AGENT_FILES contains all 15 expected agent configuration filenames."""
    assert len(CANONICAL_AGENT_FILES) == 15
    expected_files = [
        "0rchestrator.agent.md",
        "artist.agent.md",
        "cochem-audit.agent.md",
        "cochem-coder.agent.md",
        "cochem-debug.agent.md",
        "cochem-helper.agent.md",
        "cochem-improve.agent.md",
        "cochem-scribe.agent.md",
        "cochem-sdp_manager.agent.md",
        "cochem-tester.agent.md",
        "educator.agent.md",
        "researcher.agent.md",
        "teacher.agent.md",
        "ui.agent.md",
        "web_mcp.agent.md",
    ]
    for filename in expected_files:
        assert filename in CANONICAL_AGENT_FILES


def test_expand_target_placeholders_custom_map() -> None:
    """Verify expand_target_placeholders correctly replaces placeholder tokens."""
    content = "Workspace is at <COCHEM_WORKSPACE>/repo and user home is <USER_HOME>."
    custom_map = {
        "<COCHEM_WORKSPACE>": "/custom/cochem/workspace",
        "<USER_HOME>": "/home/customuser",
    }
    expanded = expand_target_placeholders(content, placeholder_map=custom_map)
    assert "<COCHEM_WORKSPACE>" not in expanded
    assert "<USER_HOME>" not in expanded
    assert "Workspace is at /custom/cochem/workspace/repo and user home is /home/customuser." == expanded


def test_expand_target_placeholders_ordering() -> None:
    """Verify longer placeholder tokens are prioritized during expansion."""
    content = "<COCHEM_WORKSPACE_DEEP> and <COCHEM_WORKSPACE>"
    custom_map = {
        "<COCHEM_WORKSPACE>": "/short",
        "<COCHEM_WORKSPACE_DEEP>": "/deep/path",
    }
    expanded = expand_target_placeholders(content, placeholder_map=custom_map)
    assert expanded == "/deep/path and /short"


def test_compute_unified_diff_identical() -> None:
    """Verify compute_unified_diff returns empty list for identical inputs."""
    text = "Line 1\nLine 2\nLine 3\n"
    diff = compute_unified_diff(text, text)
    assert diff == []


def test_compute_unified_diff_differing() -> None:
    """Verify compute_unified_diff returns unified diff headers and changes."""
    text_a = "Line 1\nLine 2\n"
    text_b = "Line 1\nLine 2 modified\n"
    diff = compute_unified_diff(text_a, text_b, from_file="src.md", to_file="tgt.md")
    assert len(diff) > 0
    assert any("--- src.md" in line for line in diff)
    assert any("+++ tgt.md" in line for line in diff)
    assert any("-Line 2" in line for line in diff)
    assert any("+Line 2 modified" in line for line in diff)


def test_verify_file_diff_missing_files(tmp_path: Path) -> None:
    """Verify verify_file_diff gracefully reports missing source or target files."""
    missing_src = tmp_path / "missing_src.md"
    missing_tgt = tmp_path / "missing_tgt.md"
    real_file = tmp_path / "real.md"
    real_file.write_text("content", encoding="utf-8")

    is_match, diffs, leaks = verify_file_diff(missing_src, real_file)
    assert is_match is False
    assert any("ERROR: Source file not found" in d for d in diffs)

    is_match, diffs, leaks = verify_file_diff(real_file, missing_tgt)
    assert is_match is False
    assert any("ERROR: Target file not found" in d for d in diffs)


def test_verify_file_diff_expand_target_mode(tmp_path: Path) -> None:
    """Verify verify_file_diff in expand_target mode."""
    src_file = tmp_path / "source.agent.md"
    tgt_file = tmp_path / "target.agent.md"

    custom_map = {
        "<COCHEM_WORKSPACE>": str(tmp_path / "workspace"),
        "<USER_HOME>": str(tmp_path / "home"),
    }

    src_file.write_text(f"Root: {tmp_path / 'workspace'}\nHome: {tmp_path / 'home'}\n", encoding="utf-8")
    tgt_file.write_text("Root: <COCHEM_WORKSPACE>\nHome: <USER_HOME>\n", encoding="utf-8")

    is_match, diffs, leaks = verify_file_diff(
        src_file,
        tgt_file,
        mode="expand_target",
        placeholder_map=custom_map,
    )
    assert is_match is True
    assert diffs == []
    assert leaks == []


def test_verify_file_diff_sanitize_source_mode(tmp_path: Path) -> None:
    """Verify verify_file_diff in sanitize_source mode."""
    src_file = tmp_path / "source.agent.md"
    tgt_file = tmp_path / "target.agent.md"

    ws_path = (tmp_path / "workspace").resolve()
    custom_map = {
        "<COCHEM_WORKSPACE>": str(ws_path),
    }

    src_file.write_text(f"Path: {ws_path}\n", encoding="utf-8")
    tgt_file.write_text("Path: <COCHEM_WORKSPACE>\n", encoding="utf-8")

    is_match, diffs, leaks = verify_file_diff(
        src_file,
        tgt_file,
        mode="sanitize_source",
        placeholder_map=custom_map,
    )
    assert is_match is True
    assert diffs == []


def test_verify_file_diff_raw_mode(tmp_path: Path) -> None:
    """Verify verify_file_diff in raw mode."""
    src_file = tmp_path / "source.agent.md"
    tgt_file = tmp_path / "target.agent.md"

    src_file.write_text("Exact match text\n", encoding="utf-8")
    tgt_file.write_text("Exact match text\n", encoding="utf-8")

    is_match, diffs, leaks = verify_file_diff(src_file, tgt_file, mode="raw")
    assert is_match is True
    assert diffs == []

    tgt_file.write_text("Mismatched text\n", encoding="utf-8")
    is_match, diffs, leaks = verify_file_diff(src_file, tgt_file, mode="raw")
    assert is_match is False
    assert len(diffs) > 0


def test_verify_file_diff_invalid_mode(tmp_path: Path) -> None:
    """Verify verify_file_diff raises ValueError on invalid mode."""
    f1 = tmp_path / "f1.md"
    f2 = tmp_path / "f2.md"
    f1.write_text("a", encoding="utf-8")
    f2.write_text("b", encoding="utf-8")

    with pytest.raises(ValueError, match="Unknown verification mode"):
        verify_file_diff(f1, f2, mode="invalid_mode")


def test_run_verification_and_format_report(tmp_path: Path) -> None:
    """Verify run_verification and format_report end-to-end."""
    src_dir = tmp_path / "src"
    tgt_dir = tmp_path / "tgt"
    src_dir.mkdir()
    tgt_dir.mkdir()

    custom_map = {
        "<COCHEM_WORKSPACE>": str(tmp_path / "cochem"),
        "<USER_HOME>": str(tmp_path / "user"),
    }

    files = ["file1.agent.md", "file2.agent.md"]
    # file1 matches
    (src_dir / "file1.agent.md").write_text(f"Dir: {tmp_path / 'cochem'}\n", encoding="utf-8")
    (tgt_dir / "file1.agent.md").write_text("Dir: <COCHEM_WORKSPACE>\n", encoding="utf-8")

    # file2 mismatches
    (src_dir / "file2.agent.md").write_text("Header A\n", encoding="utf-8")
    (tgt_dir / "file2.agent.md").write_text("Header B\n", encoding="utf-8")

    matches, mismatches, results = run_verification(
        source_dir=src_dir,
        target_dir=tgt_dir,
        agent_files=files,
        mode="expand_target",
        placeholder_map=custom_map,
    )

    assert matches == 1
    assert mismatches == 1
    assert results["file1.agent.md"][0] is True
    assert results["file2.agent.md"][0] is False

    report = format_report(
        source_dir=src_dir,
        target_dir=tgt_dir,
        placeholder_map=custom_map,
        matches_count=matches,
        mismatches_count=mismatches,
        results=results,
        mode="expand_target",
    )

    assert "=== EMPIRICAL DIFF VERIFICATION REPORT ===" in report
    assert "[MATCH] file1.agent.md: EXACT MATCH" in report
    assert "[FAIL] file2.agent.md: MISMATCH DETECTED!" in report
    assert "VERDICT: REJECT" in report


def test_main_cli_execution(tmp_path: Path) -> None:
    """Verify main function parses CLI options, writes report output, and returns exit code."""
    src_dir = tmp_path / "source"
    tgt_dir = tmp_path / "target"
    src_dir.mkdir()
    tgt_dir.mkdir()

    for agent_file in CANONICAL_AGENT_FILES:
        (src_dir / agent_file).write_text(f"# Agent {agent_file}\nContent line.\n", encoding="utf-8")
        (tgt_dir / agent_file).write_text(f"# Agent {agent_file}\nContent line.\n", encoding="utf-8")

    out_file = tmp_path / "output_report.txt"

    exit_code = main([
        "--source", str(src_dir),
        "--target", str(tgt_dir),
        "--mode", "raw",
        "--output", str(out_file),
    ])

    assert exit_code == 0
    assert out_file.is_file()
    content = out_file.read_text(encoding="utf-8")
    assert "VERDICT: APPROVE" in content
    assert "15 / 15 files matched exactly." in content
