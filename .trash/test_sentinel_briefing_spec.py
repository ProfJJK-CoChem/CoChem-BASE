from pathlib import Path
import pytest

from cochem_base.path_sanitization import (
    get_agents_dir,
    leak_patterns,
    find_path_leaks,
)


@pytest.fixture
def sentinel_briefing_path() -> Path:
    agents_dir = get_agents_dir()
    path = agents_dir / "sentinel" / "BRIEFING.md"
    assert path.exists(), f"sentinel/BRIEFING.md does not exist at {path}"
    return path


def test_sentinel_briefing_encoding_and_line_endings(sentinel_briefing_path: Path) -> None:
    """Validate that sentinel/BRIEFING.md has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = sentinel_briefing_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "sentinel/BRIEFING.md contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "sentinel/BRIEFING.md contains Windows CRLF line endings"


def test_sentinel_briefing_path_sanitization_and_no_leaks(sentinel_briefing_path: Path) -> None:
    """Validate that sentinel/BRIEFING.md contains zero personal path leaks and uses standard tokens."""
    content = sentinel_briefing_path.read_text(encoding="utf-8")
    leaks = find_path_leaks(content)
    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s) in sentinel/BRIEFING.md: {leaks}"

    assert "<COCHEM_WORKSPACE>" in content, "Expected <COCHEM_WORKSPACE> placeholder token in BRIEFING.md"
    assert "<USER_HOME>" in content, "Expected <USER_HOME> placeholder token in BRIEFING.md"
    assert "<GDRIVE_ROOT>" in content, "Expected <GDRIVE_ROOT> placeholder token in BRIEFING.md"


def test_sentinel_briefing_mandatory_sections_present(sentinel_briefing_path: Path) -> None:
    """Validate that all mandatory canonical briefing sections exist in sentinel/BRIEFING.md."""
    content = sentinel_briefing_path.read_text(encoding="utf-8")
    required_sections = [
        "# BRIEFING",
        "## Mission",
        "## 🔒 My Identity",
        "## 🔒 Key Constraints",
        "## User Context",
        "## Project Status",
        "## Victory Audit Status",
        "## Artifact Index",
    ]
    for section in required_sections:
        assert section in content, f"Missing required section in sentinel/BRIEFING.md: {section}"


def test_sentinel_briefing_identity_and_audit_fields(sentinel_briefing_path: Path) -> None:
    """Validate that sentinel/BRIEFING.md has correct identity, orchestrator, and victory audit fields."""
    content = sentinel_briefing_path.read_text(encoding="utf-8")
    assert "Archetype" in content and "sentinel" in content
    assert "39f39eb0-6bb9-4f9a-b544-6a701d124d30" in content
    assert "bdb1d815-7fce-4980-b132-edaf7aeca112" in content
    assert "VICTORY CONFIRMED" in content
