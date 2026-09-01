from pathlib import Path
import pytest

from cochem_base.path_sanitization import (
    get_agents_dir,
    leak_patterns,
    find_path_leaks,
)


@pytest.fixture
def auditor_briefing_path() -> Path:
    agents_dir = get_agents_dir()
    path = agents_dir / "teamwork_preview_auditor_1" / "BRIEFING.md"
    assert path.exists(), f"teamwork_preview_auditor_1/BRIEFING.md does not exist at {path}"
    return path


def test_auditor_briefing_encoding_and_line_endings(auditor_briefing_path: Path) -> None:
    """Validate that teamwork_preview_auditor_1/BRIEFING.md has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = auditor_briefing_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "teamwork_preview_auditor_1/BRIEFING.md contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "teamwork_preview_auditor_1/BRIEFING.md contains Windows CRLF line endings"


def test_auditor_briefing_path_sanitization_and_no_leaks(auditor_briefing_path: Path) -> None:
    """Validate that teamwork_preview_auditor_1/BRIEFING.md contains zero personal path leaks and uses standard tokens."""
    content = auditor_briefing_path.read_text(encoding="utf-8")
    leaks = find_path_leaks(content)
    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s) in teamwork_preview_auditor_1/BRIEFING.md: {leaks}"

    assert "<COCHEM_WORKSPACE>" in content, "Expected <COCHEM_WORKSPACE> placeholder token in BRIEFING.md"
    assert "<USER_HOME>" in content, "Expected <USER_HOME> placeholder token in BRIEFING.md"
    assert "<GDRIVE_ROOT>" in content, "Expected <GDRIVE_ROOT> placeholder token in BRIEFING.md"


def test_auditor_briefing_mandatory_sections_present(auditor_briefing_path: Path) -> None:
    """Validate that all mandatory canonical briefing sections exist in teamwork_preview_auditor_1/BRIEFING.md."""
    content = auditor_briefing_path.read_text(encoding="utf-8")
    required_sections = [
        "# BRIEFING",
        "## Mission",
        "## 🔒 My Identity",
        "## 🔒 Key Constraints",
        "## Current Parent",
        "## Audit Scope",
        "## Audit Progress",
        "## Key Decisions Made",
        "## Artifact Index",
    ]
    for section in required_sections:
        assert section in content, f"Missing required section in teamwork_preview_auditor_1/BRIEFING.md: {section}"


def test_auditor_briefing_identity_and_audit_fields(auditor_briefing_path: Path) -> None:
    """Validate that teamwork_preview_auditor_1/BRIEFING.md has correct identity, parent, and audit verdict."""
    content = auditor_briefing_path.read_text(encoding="utf-8")
    assert "Archetype" in content and "forensic_auditor" in content
    assert "39f39eb0-6bb9-4f9a-b544-6a701d124d30" in content
    assert "CLEAN" in content
    assert "<COCHEM_WORKSPACE>\\GitHub-Repo\\CoChem-BASE\\.agents\\teamwork_preview_auditor_1" in content

