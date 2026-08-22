from pathlib import Path
import pytest

from cochem_base.path_sanitization import (
    get_agents_dir,
    find_path_leaks,
)


@pytest.fixture
def auditor_dispatch_path() -> Path:
    agents_dir = get_agents_dir()
    path = agents_dir / "teamwork_preview_auditor_1" / "DISPATCH.md"
    assert path.exists(), f"teamwork_preview_auditor_1/DISPATCH.md does not exist at {path}"
    return path


def test_auditor_dispatch_encoding_and_line_endings(auditor_dispatch_path: Path) -> None:
    """Validate that teamwork_preview_auditor_1/DISPATCH.md has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = auditor_dispatch_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "teamwork_preview_auditor_1/DISPATCH.md contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "teamwork_preview_auditor_1/DISPATCH.md contains Windows CRLF line endings"


def test_auditor_dispatch_path_sanitization_and_no_leaks(auditor_dispatch_path: Path) -> None:
    """Validate that teamwork_preview_auditor_1/DISPATCH.md contains zero personal path leaks and uses standard tokens."""
    content = auditor_dispatch_path.read_text(encoding="utf-8")
    leaks = find_path_leaks(content)
    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s) in teamwork_preview_auditor_1/DISPATCH.md: {leaks}"

    assert "<COCHEM_WORKSPACE>" in content, "Expected <COCHEM_WORKSPACE> placeholder token in DISPATCH.md"
    assert "D:\\Gdrive" not in content, "Found unsanitized D:\\Gdrive path in DISPATCH.md"
    assert "C:\\Users" not in content, "Found unsanitized C:\\Users path in DISPATCH.md"


def test_auditor_dispatch_mandatory_sections_present(auditor_dispatch_path: Path) -> None:
    """Validate that all mandatory canonical dispatch directives exist in teamwork_preview_auditor_1/DISPATCH.md."""
    content = auditor_dispatch_path.read_text(encoding="utf-8")
    required_sections = [
        "## 2026-08-11T18:04:23Z",
        "<USER_REQUEST>",
        "You are a Forensic Auditor agent.",
        "Your working directory:",
        "Original Request path:",
        "Instructions:",
        "Check for integrity violations:",
        "audit.md",
        "handoff.md",
        "CLEAN",
        "INTEGRITY VIOLATION",
        "</USER_REQUEST>",
    ]
    for section in required_sections:
        assert section in content, f"Missing required section in teamwork_preview_auditor_1/DISPATCH.md: {section}"


def test_auditor_dispatch_working_dir_and_targets(auditor_dispatch_path: Path) -> None:
    """Validate working directory and target paths in teamwork_preview_auditor_1/DISPATCH.md."""
    content = auditor_dispatch_path.read_text(encoding="utf-8")
    assert "<COCHEM_WORKSPACE>\\GitHub-Repo\\CoChem-BASE\\.agents\\teamwork_preview_auditor_1" in content
    assert "<COCHEM_WORKSPACE>\\GitHub-Repo\\CoChem-BASE\\.agents\\ORIGINAL_REQUEST.md" in content
    assert "<COCHEM_WORKSPACE>\\GitHub-Repo\\CoChem-BASE\\.agents" in content
