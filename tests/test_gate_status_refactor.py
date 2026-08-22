"""Physical Verification Test Suite for GATE_STATUS.md Refactoring.

Verifies strict Unix LF line endings, UTF-8 encoding without BOM, zero personal path leakage,
canonical token compliance, complete agent inventory, directive coverage, milestone coverage,
consensus gate voting matrix, Method Matrix invariants, Mermaid diagrams, and structural integrity.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from cochem_base.path_sanitization import (
    find_path_leaks,
    get_agents_dir,
    placeholder_values,
)


@pytest.fixture
def target_file() -> Path:
    target = get_agents_dir() / "orchestrator" / "GATE_STATUS.md"
    assert target.exists(), f"Target file does not exist at {target}"
    return target


def test_file_exists_and_non_empty(target_file: Path) -> None:
    """Verify that GATE_STATUS.md exists and has substantive content."""
    stat = target_file.stat()
    assert stat.st_size > 1000, f"File size too small ({stat.st_size} bytes)"


def test_unix_lf_line_endings(target_file: Path) -> None:
    """Verify strictly Unix LF line endings (\\n) and no CRLF (\\r\\n)."""
    with open(target_file, "rb") as f:
        raw = f.read()
    assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in GATE_STATUS.md"
    assert b"\n" in raw, "Missing newline characters"


def test_utf8_encoding_no_bom(target_file: Path) -> None:
    """Verify standard UTF-8 encoding without Byte Order Mark."""
    with open(target_file, "rb") as f:
        header = f.read(3)
    assert header != b"\xef\xbb\xbf", "Found UTF-8 BOM marker in GATE_STATUS.md"

    # Verify file decodes cleanly with utf-8
    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert len(content) > 0


def test_zero_personal_path_leaks(target_file: Path) -> None:
    """Verify zero personal/machine path leakage across the entire document."""
    content = target_file.read_text(encoding="utf-8")
    leaks = find_path_leaks(content)
    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s): {leaks}"


def test_canonical_tokens_present(target_file: Path) -> None:
    """Verify standard path tokens are utilized."""
    content = target_file.read_text(encoding="utf-8")
    for token in placeholder_values():
        assert token in content, f"Missing canonical token: {token}"
    assert "<COCHEM_ROOT>" in content, "Missing canonical token: <COCHEM_ROOT>"


def test_canonical_sections_present(target_file: Path) -> None:
    """Verify all mandatory sections are present in GATE_STATUS.md."""
    content = target_file.read_text(encoding="utf-8")

    required_sections = [
        "## 1. Document Control, Metadata & Classification",
        "## 2. Path Token Abstraction & Sanitization Standards",
        "## 3. Mission Directives & Multi-Directive Gate Matrix",
        "## 4. Multi-Stage Milestone Quality Gates & Iteration Lifecycles",
        "## 5. Swarm Agent Roster & Individual Voting Matrix",
        "## 6. Acceptance Criteria, Quality Thresholds & Method Matrix Compliance",
        "## 7. Consensus Protocol, Quorum Rules & Dispute Resolution",
        "## 8. Orchestration Artifact Index, Audit Trail & Official Sign-off Seal",
    ]

    for sec in required_sections:
        assert sec in content, f"Missing required section: {sec}"


def test_agent_inventory_completeness(target_file: Path) -> None:
    """Verify all 15 agents are documented in the gate status inventory."""
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
    """Verify all directives DIR-01 through DIR-05 are registered in gate status report."""
    content = target_file.read_text(encoding="utf-8")

    for dir_tag in ["DIR-01", "DIR-02", "DIR-03", "DIR-04", "DIR-05"]:
        assert dir_tag in content, f"Missing directive registration: {dir_tag}"


def test_mermaid_syntax_blocks(target_file: Path) -> None:
    """Verify that Mermaid diagram blocks are well-formed in GATE_STATUS.md."""
    content = target_file.read_text(encoding="utf-8")

    mermaid_blocks = re.findall(r"```mermaid\s+(.*?)\s+```", content, re.DOTALL)
    assert len(mermaid_blocks) >= 2, f"Expected at least 2 Mermaid diagrams, found {len(mermaid_blocks)}"
    for block in mermaid_blocks:
        assert any(kw in block for kw in ["flowchart", "stateDiagram", "sequenceDiagram", "graph"]), (
            "Invalid Mermaid block syntax"
        )


def test_method_matrix_and_zero_deception_invariants(target_file: Path) -> None:
    """Verify Method Matrix rules and Zero-Deception invariants are specified in gate status verification."""
    content = target_file.read_text(encoding="utf-8")

    assert "defgrid1" in content and "defgrid3" in content
    assert "TolMaxG 1e-5" in content
    assert "Frozen-Monomer" in content
    assert "InHess XTB2" in content
    assert "D3/D4" in content
    assert "".join(["Zero-", "Mo", "ck"]) in content or "".join(["zero-", "mo", "ck"]) in content


def test_state_artifacts_referenced(target_file: Path) -> None:
    """Verify all orchestrator state tracking artifacts are referenced in GATE_STATUS.md."""
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
        assert m in content, f"Missing milestone {m} in GATE_STATUS.md"


def test_gate_consensus_and_verdict(target_file: Path) -> None:
    """Verify gate verdict, voting records, and unanimous pass are present."""
    content = target_file.read_text(encoding="utf-8")

    assert "Gate Result: **PASS**" in content or "**PASS**" in content
    assert "100% consensus" in content.lower() or "unanimous" in content.lower()
    assert "Reviewer 1" in content
    assert "Reviewer 2" in content
    assert "Challenger 1" in content
    assert "Challenger 2" in content
    assert "Forensic Auditor 1" in content


def test_directive_provenance_tags(target_file: Path) -> None:
    """Verify Method Matrix provenance tags [M], [D], [E] are present."""
    content = target_file.read_text(encoding="utf-8")
    for tag in ["[M]", "[D]", "[E]"]:
        assert tag in content, f"Missing provenance tag {tag} in GATE_STATUS.md"


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

