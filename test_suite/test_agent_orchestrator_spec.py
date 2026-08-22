import os
import re
from pathlib import Path
import pytest
import yaml

from cochem_base.path_sanitization import (
    get_agents_dir,
    leak_patterns,
    path_variants,
    placeholder_values,
)


@pytest.fixture
def orchestrator_path() -> Path:
    agents_dir = get_agents_dir()
    path = agents_dir / "0rchestrator.agent.md"
    assert path.exists(), f"0rchestrator.agent.md does not exist at {path}"
    return path


def test_orchestrator_file_encoding_and_line_endings(orchestrator_path: Path) -> None:
    """Validate that 0rchestrator.agent.md has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = orchestrator_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "0rchestrator.agent.md contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "0rchestrator.agent.md contains Windows CRLF line endings"


def test_orchestrator_yaml_frontmatter_schema(orchestrator_path: Path) -> None:
    """Validate that YAML frontmatter parses correctly and contains all mandatory keys and types."""
    content = orchestrator_path.read_text(encoding="utf-8")
    match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    assert match is not None, "YAML frontmatter is missing or improperly delimited"

    fm = yaml.safe_load(match.group(1))
    assert isinstance(fm, dict), "Frontmatter must parse as a dictionary"

    required_keys = [
        "name",
        "description",
        "argument-hint",
        "version",
        "domain",
        "routes_to",
        "enable_write_tools",
        "enable_subagent_tools",
        "enable_mcp_tools",
    ]
    for key in required_keys:
        assert key in fm, f"Missing required frontmatter key: {key}"

    assert fm["name"] == "0rchestrator"
    assert fm["domain"] == "orchestration"
    assert fm["enable_write_tools"] is True
    assert fm["enable_subagent_tools"] is True
    assert fm["enable_mcp_tools"] is True
    assert isinstance(fm["routes_to"], list)
    assert len(fm["routes_to"]) >= 15


def test_orchestrator_path_sanitization_and_no_leaks(orchestrator_path: Path) -> None:
    """Validate that 0rchestrator.agent.md contains zero personal path leaks and uses standard tokens."""
    content = orchestrator_path.read_text(encoding="utf-8")
    patterns = leak_patterns()

    leaks = []
    for line_idx, line in enumerate(content.splitlines(), start=1):
        for pattern, label in patterns:
            if pattern.search(line):
                leaks.append((line_idx, label, line.strip()))

    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s): {leaks}"
    assert "<COCHEM_WORKSPACE>" in content, "Expected <COCHEM_WORKSPACE> placeholder token"
    assert "<GDRIVE_ROOT>" in content, "Expected <GDRIVE_ROOT> placeholder token"


def test_orchestrator_mandatory_sections_present(orchestrator_path: Path) -> None:
    """Validate that all mandatory canonical architecture sections exist in 0rchestrator.agent.md."""
    content = orchestrator_path.read_text(encoding="utf-8")
    required_sections = [
        "# IDENTITY AND ROLE",
        "# AUTHORITATIVE KNOWLEDGE SOURCES",
        "# 0RCHESTRATOR GLOBAL PROTOCOL",
        "# CORE DIRECTIVES & WORKFLOW ENGINE",
        "## 1. Deep Granularity & Work Breakdown Structure (WBS) Mandate",
        "## 2. The Vanguard Swarm Initialization",
        "## 3. Simple Task Short-Circuit",
        "## 4. Mandatory Task List Initialization & State Management",
        "## 5. Method Matrix v4 Tier Routing",
        "# SWARM TAXONOMY & SPECIALIST ROLES",
        "# PROACTIVE MCP AUTO-ACTIVATION MATRIX",
        "# SWARM STATE MANAGEMENT PROTOCOL",
        "# GLOBAL SWARM ANTI-HALLUCINATION & ZERO-MOCK DIRECTIVES",
        "# ANTI-SPOOFING PROTOCOL",
        "# SWARM ARCHITECTURE & DISTRIBUTED EXECUTION PROTOCOLS",
        "# SWARM AUTONOMY & HEADLESS EXECUTION MANDATE",
        "# THE \"EDIT-FIRST\" IN-PLACE MODIFICATION MANDATE",
        "# ADVERSARIAL AUDIT & 10-CYCLE DEBATE MANDATE",
        "# MANDATORY SUBAGENT GARBAGE COLLECTION",
        "# CONTEXT-AWARE CONFLICT RESOLUTION",
        "# BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
    ]
    for section in required_sections:
        assert section in content, f"Missing required section in 0rchestrator.agent.md: {section}"


def test_orchestrator_anti_spoofing_invariants(orchestrator_path: Path) -> None:
    """Validate that 0rchestrator.agent.md incorporates critical anti-spoofing and zero-mock protocols."""
    content = orchestrator_path.read_text(encoding="utf-8")

    assert "zero_trust_runner.py" in content
    assert "verify_core_integrity.py" in content
    assert "MAX_PIVOT_CYCLES=3" in content
    assert "MAX_META_PIVOT=3" in content
    assert "Physics_Autopsy_Report.md" in content
    assert "CRDT" in content
    assert "Merkle" in content


def test_orchestrator_briefing_encoding_and_sanitization() -> None:
    """Validate that .agents/orchestrator/BRIEFING.md is clean, properly encoded, and leak-free."""
    agents_dir = get_agents_dir()
    briefing_path = agents_dir / "orchestrator" / "BRIEFING.md"
    assert briefing_path.exists(), f"BRIEFING.md does not exist at {briefing_path}"

    raw_bytes = briefing_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "BRIEFING.md contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "BRIEFING.md contains Windows CRLF line endings"

    content = briefing_path.read_text(encoding="utf-8")
    patterns = leak_patterns()

    leaks = []
    for line_idx, line in enumerate(content.splitlines(), start=1):
        for pattern, label in patterns:
            if pattern.search(line):
                leaks.append((line_idx, label, line.strip()))

    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s) in BRIEFING.md: {leaks}"
    assert "<COCHEM_WORKSPACE>" in content, "Expected <COCHEM_WORKSPACE> placeholder token in BRIEFING.md"
    assert "<USER_HOME>" in content, "Expected <USER_HOME> placeholder token in BRIEFING.md"
    assert "<GDRIVE_ROOT>" in content, "Expected <GDRIVE_ROOT> placeholder token in BRIEFING.md"

