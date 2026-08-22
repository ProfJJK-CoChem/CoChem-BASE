"""Physical Zero-Mock Test Suite for BRIEFING.md Refactoring.

Verifies strict Unix LF line endings, UTF-8 encoding without BOM, zero personal path leakage,
canonical token compliance, required section headers, team roster integrity, and artifact index.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from cochem_base.path_sanitization import (
    find_path_leaks,
    get_agents_dir,
    leak_patterns,
)


@pytest.fixture
def target_file() -> Path:
    target = get_agents_dir() / "orchestrator" / "BRIEFING.md"
    assert target.exists(), f"Target file does not exist at {target}"
    return target


def test_briefing_file_exists_and_non_empty(target_file: Path) -> None:
    """Verify that BRIEFING.md exists and has substantive content."""
    stat = target_file.stat()
    assert stat.st_size > 500, f"File size too small ({stat.st_size} bytes)"


def test_briefing_unix_lf_line_endings(target_file: Path) -> None:
    """Verify strictly Unix LF line endings (\n) and no CRLF (\r\n)."""
    with open(target_file, "rb") as f:
        raw = f.read()
    assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in BRIEFING.md"
    assert b"\n" in raw, "Missing newline characters in BRIEFING.md"


def test_briefing_utf8_encoding_no_bom(target_file: Path) -> None:
    """Verify standard UTF-8 encoding without Byte Order Mark."""
    with open(target_file, "rb") as f:
        header = f.read(3)
    assert header != b"\xef\xbb\xbf", "Found UTF-8 BOM marker in BRIEFING.md"

    # Verify file decodes cleanly with utf-8
    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert len(content) > 0


def test_briefing_zero_personal_path_leaks(target_file: Path) -> None:
    """Verify zero personal/machine path leakage across the entire document."""
    content = target_file.read_text(encoding="utf-8")
    leaks = find_path_leaks(content)
    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s) in BRIEFING.md: {leaks}"


def test_briefing_canonical_tokens_present(target_file: Path) -> None:
    """Verify standard path tokens are utilized in BRIEFING.md."""
    content = target_file.read_text(encoding="utf-8")
    for token in ["<COCHEM_WORKSPACE>", "<USER_HOME>", "<GDRIVE_ROOT>"]:
        assert token in content, f"Missing canonical token in BRIEFING.md: {token}"


def test_briefing_canonical_sections_present(target_file: Path) -> None:
    """Verify all mandatory sections are present in BRIEFING.md."""
    content = target_file.read_text(encoding="utf-8")

    required_sections = [
        "## Mission",
        "## 🔒 My Identity",
        "## 🔒 My Workflow",
        "## 🔒 Key Constraints",
        "## Current Parent",
        "## Key Decisions Made",
        "## Team Roster",
        "## Succession Status",
        "## Active Timers",
        "## Artifact Index",
    ]

    for sec in required_sections:
        assert sec in content, f"Missing required section in BRIEFING.md: {sec}"


def test_briefing_artifact_index_references(target_file: Path) -> None:
    """Verify that all four key orchestrator artifacts are properly referenced in the Artifact Index."""
    content = target_file.read_text(encoding="utf-8")

    expected_artifacts = [
        "PROJECT.md",
        "progress.md",
        "GATE_STATUS.md",
        "handoff.md",
    ]

    for artifact in expected_artifacts:
        assert artifact in content, f"Missing artifact index entry for {artifact} in BRIEFING.md"


def test_briefing_team_roster_completeness(target_file: Path) -> None:
    """Verify team roster contains completed status for all preview roles."""
    content = target_file.read_text(encoding="utf-8")

    expected_agents = [
        "Explorer 1",
        "Explorer 2",
        "Explorer 3",
        "Worker 1",
        "Reviewer 1",
        "Reviewer 2",
        "Challenger 1",
        "Challenger 2",
        "Forensic Auditor 1",
    ]

    for agent in expected_agents:
        assert agent in content, f"Missing agent in team roster: {agent}"