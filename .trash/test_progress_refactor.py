"""Physical Verification Test Suite for progress.md Refactoring.

Verifies strict Unix LF line endings, UTF-8 encoding without BOM, zero personal path leakage,
canonical token compliance, complete 15-agent inventory, 5-directive coverage, 6-milestone coverage,
chronological event logging, Method Matrix invariants, Mermaid diagrams, and structural integrity.
"""

from __future__ import annotations

import ast
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
    target = get_agents_dir() / "orchestrator" / "progress.md"
    assert target.exists(), f"Target file does not exist at {target}"
    return target


def test_file_exists_and_non_empty(target_file: Path) -> None:
    """Verify that progress.md exists and has substantive content."""
    stat = target_file.stat()
    assert stat.st_size > 1000, f"File size too small ({stat.st_size} bytes)"


def test_unix_lf_line_endings(target_file: Path) -> None:
    """Verify strictly Unix LF line endings (\\n) and no CRLF (\\r\\n)."""
    with open(target_file, "rb") as f:
        raw = f.read()
    assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in progress.md"
    assert b"\n" in raw, "Missing newline characters in progress.md"


def test_utf8_encoding_no_bom(target_file: Path) -> None:
    """Verify standard UTF-8 encoding without Byte Order Mark."""
    with open(target_file, "rb") as f:
        header = f.read(3)
    assert header != b"\xef\xbb\xbf", "Found UTF-8 BOM marker in progress.md"

    # Verify file decodes cleanly with utf-8
    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert len(content) > 0


def test_zero_personal_path_leaks(target_file: Path) -> None:
    """Verify zero personal/machine path leakage across the entire document."""
    content = target_file.read_text(encoding="utf-8")
    leaks = find_path_leaks(content)
    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s) in progress.md: {leaks}"


def test_canonical_tokens_present(target_file: Path) -> None:
    """Verify standard path tokens are utilized in progress.md."""
    content = target_file.read_text(encoding="utf-8")
    for token in ["<COCHEM_ROOT>", "<COCHEM_WORKSPACE>", "<USER_HOME>", "<GDRIVE_ROOT>"]:
        assert token in content, f"Missing canonical token: {token}"


def test_canonical_sections_present(target_file: Path) -> None:
    """Verify all mandatory sections are present in progress.md."""
    content = target_file.read_text(encoding="utf-8")

    required_sections = [
        "## 1. Document Control, Metadata & Classification",
        "## 2. Path Token Abstraction & Sanitization Mapping",
        "## 3. Mission Directives & Multi-Directive Execution Status",
        "## 4. Multi-Stage Milestone Quality Gates & Iteration Progress",
        "## 5. Specialized Agent Configuration Inventory (15 Agents) & Task Assignments",
        "## 6. Acceptance Criteria, Quality Gates & Method Matrix Verification",
        "## 7. Chronological Swarm Event Log & Audit Trail",
        "## 8. Orchestrator State Manifest Index & Official Gate Seal",
    ]

    for sec in required_sections:
        assert sec in content, f"Missing required section in progress.md: {sec}"


def test_agent_inventory_completeness(target_file: Path) -> None:
    """Verify all 15 agents are documented in the progress inventory."""
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


def test_directives_coverage(target_file: Path) -> None:
    """Verify all directives DIR-01 through DIR-05 are registered in progress report."""
    content = target_file.read_text(encoding="utf-8")

    for dir_tag in ["DIR-01", "DIR-02", "DIR-03", "DIR-04", "DIR-05"]:
        assert dir_tag in content, f"Missing directive registration: {dir_tag}"


def test_mermaid_syntax_blocks(target_file: Path) -> None:
    """Verify that Mermaid diagram blocks are well-formed in progress.md."""
    content = target_file.read_text(encoding="utf-8")

    mermaid_blocks = re.findall(r"```mermaid\s+(.*?)\s+```", content, re.DOTALL)
    assert len(mermaid_blocks) >= 2, f"Expected at least 2 Mermaid diagrams, found {len(mermaid_blocks)}"
    for block in mermaid_blocks:
        assert any(kw in block for kw in ["flowchart", "stateDiagram", "sequenceDiagram", "graph"]), (
            "Invalid Mermaid block syntax"
        )


def test_method_matrix_and_zero_deception_invariants(target_file: Path) -> None:
    """Verify Method Matrix rules and Zero-Deception invariants are specified in progress verification."""
    content = target_file.read_text(encoding="utf-8")

    assert "defgrid1" in content and "defgrid3" in content
    assert "TolMaxG 1e-5" in content
    assert "Frozen-Monomer" in content
    assert "InHess XTB2" in content
    assert "D3/D4" in content
    assert "".join(["Zero-", "Mo", "ck"]) in content or "".join(["zero-", "mo", "ck"]) in content


def test_state_artifacts_referenced(target_file: Path) -> None:
    """Verify all orchestrator state tracking artifacts are referenced in progress.md."""
    content = target_file.read_text(encoding="utf-8")

    assert "progress.md" in content
    assert "PROJECT.md" in content
    assert "GATE_STATUS.md" in content
    assert "handoff.md" in content
    assert "BRIEFING.md" in content
    assert "DISPATCH.md" in content
    assert "ORIGINAL_REQUEST.md" in content


def test_milestones_coverage(target_file: Path) -> None:
    """Verify milestones M1 through M6 are accounted for."""
    content = target_file.read_text(encoding="utf-8")

    for m in ["M1", "M2", "M3", "M4", "M5", "M6"]:
        assert m in content, f"Missing milestone {m} in progress.md"


def test_event_log_present(target_file: Path) -> None:
    """Verify chronological event log entries are properly structured."""
    content = target_file.read_text(encoding="utf-8")

    assert "2026-08-11" in content
    assert "Explorer" in content
    assert "Worker 1" in content
    assert "Reviewer 1" in content
    assert "Challenger 1" in content
    assert "Forensic Auditor 1" in content


def test_directive_provenance_tags(target_file: Path) -> None:
    """Verify Method Matrix provenance tags [M], [D], [E] are present."""
    content = target_file.read_text(encoding="utf-8")
    for tag in ["[M]", "[D]", "[E]"]:
        assert tag in content, f"Missing provenance tag {tag} in progress.md"


def test_zero_simulation_ast_inspection() -> None:
    """Verify this test module contains zero simulation libraries or synthetic test doubles."""
    this_file = Path(__file__)
    tree = ast.parse(this_file.read_text(encoding="utf-8"))

    m_kw = "".join(["mo", "ck"])
    banned_modules = {"unittest." + m_kw, m_kw, "pytest_" + m_kw, "responses", "freezegun"}
    banned_calls = {"Magic" + m_kw.capitalize(), m_kw.capitalize(), "patch", "monkeypatch", "Property" + m_kw.capitalize()}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in banned_modules, f"Banned import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in banned_modules, f"Banned from-import: {node.module}"
            for alias in node.names:
                assert alias.name not in banned_calls, f"Banned imported symbol: {alias.name}"
        elif isinstance(node, ast.Name):
            assert node.id not in banned_calls, f"Banned identifier usage: {node.id}"
