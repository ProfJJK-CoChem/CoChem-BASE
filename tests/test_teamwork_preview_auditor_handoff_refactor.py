"""Physical Zero-Mock Test Suite for teamwork_preview_auditor_1/handoff.md Refactoring.

Verifies strict Unix LF line endings, UTF-8 encoding without BOM, zero personal path leakage,
canonical token compliance, complete 15-agent inventory, 5-directive coverage, milestone coverage,
forensic auditor identity and fields, Method Matrix invariants, and structural integrity.
"""

from __future__ import annotations

import re
from pathlib import Path
import pytest

from cochem_base.path_sanitization import (
    find_path_leaks,
    get_agents_dir,
    leak_patterns,
    placeholder_values,
)


@pytest.fixture
def target_file() -> Path:
    target = get_agents_dir() / "teamwork_preview_auditor_1" / "handoff.md"
    assert target.exists(), f"Target file does not exist at {target}"
    return target


def test_auditor_handoff_exists_and_non_empty(target_file: Path) -> None:
    """Verify that auditor handoff.md exists and has substantive content."""
    stat = target_file.stat()
    assert stat.st_size > 1000, f"File size too small ({stat.st_size} bytes)"
    assert target_file.is_file()


def test_auditor_handoff_unix_lf_line_endings(target_file: Path) -> None:
    """Verify strictly Unix LF line endings (\n) and no CRLF (\r\n)."""
    with open(target_file, "rb") as f:
        raw = f.read()
    assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in handoff.md"
    assert b"\n" in raw, "Missing newline characters"


def test_auditor_handoff_utf8_encoding_no_bom(target_file: Path) -> None:
    """Verify standard UTF-8 encoding without Byte Order Mark."""
    with open(target_file, "rb") as f:
        header = f.read(3)
    assert header != b"\xef\xbb\xbf", "Found UTF-8 BOM marker in handoff.md"

    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert len(content) > 0


def test_auditor_handoff_zero_personal_path_leaks(target_file: Path) -> None:
    """Verify zero personal/machine path leakage across the entire document."""
    content = target_file.read_text(encoding="utf-8")
    leaks = find_path_leaks(content)
    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s): {leaks}"


def test_auditor_handoff_canonical_tokens_present(target_file: Path) -> None:
    """Verify standard path tokens are utilized."""
    content = target_file.read_text(encoding="utf-8")
    for token in ["<COCHEM_ROOT>", "<COCHEM_WORKSPACE>", "<USER_HOME>", "<GDRIVE_ROOT>"]:
        assert token in content, f"Missing canonical token: {token}"


def test_auditor_handoff_canonical_sections_present(target_file: Path) -> None:
    """Verify all mandatory sections are present in handoff.md."""
    content = target_file.read_text(encoding="utf-8")

    required_sections = [
        "## 1. Document Control, Metadata & Classification",
        "## 2. Path Token Abstraction & Sanitization Mapping",
        "## 3. Mission Objectives & Directive Scopes",
        "## 4. Milestone Lifecycle & Swarm Execution Verification",
        "## 5. Active Subagents, Multi-Agent Consensus Gates & Team Roster",
        "## 6. Acceptance Criteria, Quality Gates & Method Matrix Verification",
        "## 7. Key Orchestration Artifacts & Handoff Sign-off Protocol",
    ]

    for sec in required_sections:
        assert sec in content, f"Missing required section: {sec}"


def test_auditor_handoff_identity_and_audit_fields(target_file: Path) -> None:
    """Verify auditor identity and verdict fields."""
    content = target_file.read_text(encoding="utf-8")

    assert "teamwork_preview_auditor_1" in content
    assert "39f39eb0-6bb9-4f9a-b544-6a701d124d30" in content
    assert "CLEAN" in content
    assert "COCHEM-HANDOFF-AUDITOR-TP1-v5.1" in content


def test_auditor_handoff_15_agent_inventory_completeness(target_file: Path) -> None:
    """Verify all 15 agents are documented in the handoff inventory."""
    content = target_file.read_text(encoding="utf-8")

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


def test_auditor_handoff_directives_coverage(target_file: Path) -> None:
    """Verify all directives DIR-01 through DIR-05 are registered in handoff."""
    content = target_file.read_text(encoding="utf-8")

    for dir_tag in ["DIR-01", "DIR-02", "DIR-03", "DIR-04", "DIR-05"]:
        assert dir_tag in content, f"Missing directive registration: {dir_tag}"


def test_auditor_handoff_mermaid_syntax_blocks(target_file: Path) -> None:
    """Verify that Mermaid diagram blocks are well-formed in handoff.md."""
    content = target_file.read_text(encoding="utf-8")

    mermaid_blocks = re.findall(r"```mermaid\s+(.*?)\s+```", content, re.DOTALL)
    assert len(mermaid_blocks) >= 2, f"Expected at least 2 Mermaid diagrams, found {len(mermaid_blocks)}"
    for block in mermaid_blocks:
        assert any(kw in block for kw in ["flowchart", "stateDiagram", "sequenceDiagram", "graph"]), (
            "Invalid Mermaid block syntax"
        )


def test_auditor_handoff_method_matrix_and_zero_mock_invariants(target_file: Path) -> None:
    """Verify Method Matrix rules and Zero-Mock invariants are specified."""
    content = target_file.read_text(encoding="utf-8")

    assert "defgrid1" in content and "defgrid3" in content
    assert "TolMaxG 1e-5" in content
    assert "Frozen-Monomer" in content
    assert "InHess XTB2" in content
    assert "D3/D4" in content
    assert "Zero-Mock" in content or "zero-mock" in content


def test_auditor_handoff_oversight_artifacts_referenced(target_file: Path) -> None:
    """Verify all key oversight artifacts are referenced."""
    content = target_file.read_text(encoding="utf-8")

    assert "ORIGINAL_REQUEST.md" in content
    assert "BRIEFING.md" in content
    assert "PROJECT.md" in content
    assert "DISPATCH.md" in content
    assert "GATE_STATUS.md" in content
    assert "progress.md" in content
    assert "handoff.md" in content
    assert "audit.md" in content
    assert "forensic_check.py" in content


def test_auditor_handoff_milestones_coverage(target_file: Path) -> None:
    """Verify milestones M1 through M6 are accounted for."""
    content = target_file.read_text(encoding="utf-8")

    for m in ["M1", "M2", "M3", "M4", "M5", "M6"]:
        assert m in content, f"Missing milestone {m} in handoff.md"
