"""Physical Zero-Mock Test Suite for ORIGINAL_REQUEST.md Refactoring.

Verifies strict line endings, UTF-8 encoding, zero personal path leakage,
canonical token compliance, and structural integrity.
"""

import re
from pathlib import Path
import pytest

from cochem_base.path_sanitization import (
    get_agents_dir,
    leak_patterns,
    placeholder_values,
)


@pytest.fixture
def target_file() -> Path:
    target = get_agents_dir() / "ORIGINAL_REQUEST.md"
    assert target.exists(), f"Target file does not exist at {target}"
    return target


def test_file_exists_and_non_empty(target_file: Path) -> None:
    """Verify that ORIGINAL_REQUEST.md exists and has substantive content."""
    stat = target_file.stat()
    assert stat.st_size > 1000, f"File size too small ({stat.st_size} bytes)"


def test_unix_lf_line_endings(target_file: Path) -> None:
    """Verify strictly Unix LF line endings (\n) and no CRLF (\r\n)."""
    with open(target_file, "rb") as f:
        raw = f.read()
    assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in ORIGINAL_REQUEST.md"
    assert b"\n" in raw, "Missing newline characters"


def test_utf8_encoding_no_bom(target_file: Path) -> None:
    """Verify standard UTF-8 encoding without Byte Order Mark."""
    with open(target_file, "rb") as f:
        header = f.read(3)
    assert header != b"\xef\xbb\xbf", "Found UTF-8 BOM marker in ORIGINAL_REQUEST.md"
    
    # Verify file decodes cleanly with utf-8
    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert len(content) > 0


def test_zero_personal_path_leaks(target_file: Path) -> None:
    """Verify zero personal/machine path leakage across the entire document."""
    with open(target_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    leaks = []
    patterns = leak_patterns()
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s): {leaks}"


def test_canonical_sections_present(target_file: Path) -> None:
    """Verify all mandatory sections are present."""
    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()

    required_sections = [
        "## 1. Document Control, Metadata & Classification",
        "## 2. Path Token Dictionary & Abstraction Standards",
        "## 3. Chronological Directive Registry & Status Matrix",
        "## 4. Swarm Governance & Execution Lifecycle",
        "## 5. Directive 01 Specification — Phase 4: Code Audit Council",
        "## 6. Directive 02 Specification — Agent Configuration Synchronization & Path Sanitization",
        "## 7. Directive 03 Specification — Ecosystem Refactoring & Compliance Gap Resolution",
        "## 8. Directive 04 Specification — Continuous Stateful Batching & 18-Module Improvements",
        "## 9. Directive 05 Specification — Two-Pass Blueprint File Audit & Zero-Mock Quarantine",
        "## 10. Directive Ingestion Protocol for Future Directives",
        "## 11. Quality Assurance, Anti-Spoofing & Zero-Mock Compliance",
        "## 12. Verification & Sign-off Log",
    ]

    for sec in required_sections:
        assert sec in content, f"Missing required section: {sec}"


def test_agent_inventory_completeness(target_file: Path) -> None:
    """Verify all 15 agents are documented in the specification inventory."""
    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()

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
    """Verify all directives DIR-01 through DIR-05 are registered."""
    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()

    for dir_tag in ["DIR-01", "DIR-02", "DIR-03", "DIR-04", "DIR-05"]:
        assert dir_tag in content, f"Missing directive registration: {dir_tag}"


def test_mermaid_syntax_blocks(target_file: Path) -> None:
    """Verify that Mermaid diagram blocks are well-formed."""
    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()

    mermaid_blocks = re.findall(r"```mermaid\s+(.*?)\s+```", content, re.DOTALL)
    assert len(mermaid_blocks) >= 3, f"Expected at least 3 Mermaid diagrams, found {len(mermaid_blocks)}"
    for block in mermaid_blocks:
        assert any(kw in block for kw in ["flowchart", "stateDiagram", "sequenceDiagram", "graph"]), (
            "Invalid Mermaid block syntax"
        )
