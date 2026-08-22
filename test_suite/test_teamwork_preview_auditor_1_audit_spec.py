"""Physical Zero-Mock Test Suite for teamwork_preview_auditor_1/audit.md Refactoring.

Verifies strict Unix LF line endings, UTF-8 encoding without BOM, zero personal path leakage,
canonical token compliance, complete 15-agent inventory, multi-phase forensic checks,
Mermaid workflow visualization, Method Matrix v4 compliance, and structural integrity.
"""

from __future__ import annotations

from pathlib import Path
import re
import pytest

from cochem_base.path_sanitization import (
    find_path_leaks,
    get_agents_dir,
)


@pytest.fixture
def auditor_audit_path() -> Path:
    agents_dir = get_agents_dir()
    path = agents_dir / "teamwork_preview_auditor_1" / "audit.md"
    assert path.exists(), f"teamwork_preview_auditor_1/audit.md does not exist at {path}"
    return path


def test_auditor_audit_exists_and_non_empty(auditor_audit_path: Path) -> None:
    """Verify that teamwork_preview_auditor_1/audit.md exists and has substantive content."""
    stat = auditor_audit_path.stat()
    assert stat.st_size > 2000, f"File size too small ({stat.st_size} bytes)"
    assert auditor_audit_path.is_file()


def test_auditor_audit_encoding_and_line_endings(auditor_audit_path: Path) -> None:
    """Validate that teamwork_preview_auditor_1/audit.md has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = auditor_audit_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "teamwork_preview_auditor_1/audit.md contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "teamwork_preview_auditor_1/audit.md contains Windows CRLF line endings"
    assert b"\n" in raw_bytes, "teamwork_preview_auditor_1/audit.md missing newline characters"


def test_auditor_audit_path_sanitization_and_no_leaks(auditor_audit_path: Path) -> None:
    """Validate that teamwork_preview_auditor_1/audit.md contains zero personal path leaks and uses standard tokens."""
    content = auditor_audit_path.read_text(encoding="utf-8")
    leaks = find_path_leaks(content)
    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s) in teamwork_preview_auditor_1/audit.md: {leaks}"

    assert "<COCHEM_WORKSPACE>" in content, "Expected <COCHEM_WORKSPACE> placeholder token in audit.md"
    assert "<USER_HOME>" in content, "Expected <USER_HOME> placeholder token in audit.md"
    assert "<GDRIVE_ROOT>" in content, "Expected <GDRIVE_ROOT> placeholder token in audit.md"
    assert "<COCHEM_ROOT>" in content, "Expected <COCHEM_ROOT> placeholder token in audit.md"
    assert "D:\\Gdrive" not in content, "Found unsanitized D:\\Gdrive path in audit.md"
    assert "C:\\Users" not in content, "Found unsanitized C:\\Users path in audit.md"


def test_auditor_audit_mandatory_sections_present(auditor_audit_path: Path) -> None:
    """Validate that all mandatory canonical forensic sections exist in teamwork_preview_auditor_1/audit.md."""
    content = auditor_audit_path.read_text(encoding="utf-8")
    required_sections = [
        "# Forensic Integrity Audit Report",
        "## 1. Document Control, Metadata & Classification",
        "## 2. Path Token Abstraction & Sanitization Mapping",
        "## 3. Executive Summary & Verification Scope",
        "## 4. Multi-Phase Forensic Audit Results & Parity Matrix",
        "## 5. Empirical Evidence Chain & Zero-Mock Proofs",
        "## 6. Quantum Chemistry Method Matrix v4 & Anti-Spoof Invariants",
        "## 7. Verification Logs, Final Verdict & Swarm Directorate Sign-off",
    ]
    for section in required_sections:
        assert section in content, f"Missing required section in teamwork_preview_auditor_1/audit.md: {section}"


def test_auditor_audit_identity_and_audit_fields(auditor_audit_path: Path) -> None:
    """Validate that teamwork_preview_auditor_1/audit.md has correct identity, parent, and audit verdict."""
    content = auditor_audit_path.read_text(encoding="utf-8")
    assert "teamwork_preview_auditor_1" in content
    assert "39f39eb0-6bb9-4f9a-b544-6a701d124d30" in content
    assert "CLEAN" in content
    assert "ORIGINAL_REQUEST.md" in content
    assert "<COCHEM_WORKSPACE>\\GitHub-Repo\\CoChem-BASE\\.agents\\teamwork_preview_auditor_1" in content


def test_auditor_audit_15_agent_inventory_completeness(auditor_audit_path: Path) -> None:
    """Verify all 15 agents are documented in the forensic audit inventory."""
    content = auditor_audit_path.read_text(encoding="utf-8")
    expected_agents = [
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
    for agent in expected_agents:
        assert agent in content, f"Missing agent reference in inventory: {agent}"


def test_auditor_audit_mermaid_diagrams_present(auditor_audit_path: Path) -> None:
    """Verify that Mermaid diagram blocks are well-formed in teamwork_preview_auditor_1/audit.md."""
    content = auditor_audit_path.read_text(encoding="utf-8")
    mermaid_blocks = re.findall(r"```mermaid\s+(.*?)\s+```", content, re.DOTALL)
    assert len(mermaid_blocks) >= 1, f"Expected at least 1 Mermaid diagram, found {len(mermaid_blocks)}"
    for block in mermaid_blocks:
        assert any(kw in block for kw in ["flowchart", "stateDiagram", "sequenceDiagram", "graph"]), (
            "Invalid Mermaid block syntax"
        )


def test_auditor_audit_method_matrix_and_zero_mock_invariants(auditor_audit_path: Path) -> None:
    """Verify Method Matrix rules and Zero-Mock invariants are specified in audit.md."""
    content = auditor_audit_path.read_text(encoding="utf-8")
    assert "defgrid1" in content and "defgrid3" in content
    assert "TolMaxG 1e-5" in content
    assert "Frozen-Monomer" in content
    assert "InHess XTB2" in content
    assert "D3/D4" in content
    assert "Zero-Mock" in content or "zero-mock" in content
