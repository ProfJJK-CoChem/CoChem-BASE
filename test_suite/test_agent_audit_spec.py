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
def audit_path() -> Path:
    agents_dir = get_agents_dir()
    path = agents_dir / "cochem-audit.agent.md"
    assert path.exists(), f"cochem-audit.agent.md does not exist at {path}"
    return path


def test_audit_file_encoding_and_line_endings(audit_path: Path) -> None:
    """Validate that cochem-audit.agent.md has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = audit_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "cochem-audit.agent.md contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "cochem-audit.agent.md contains Windows CRLF line endings"


def test_audit_yaml_frontmatter_schema(audit_path: Path) -> None:
    """Validate that YAML frontmatter parses correctly and contains all mandatory keys and types."""
    content = audit_path.read_text(encoding="utf-8")
    match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    assert match is not None, "YAML frontmatter is missing or improperly delimited"

    fm = yaml.safe_load(match.group(1))
    assert isinstance(fm, dict), "Frontmatter must parse as a dictionary"

    required_keys = [
        "name",
        "description",
        "argument-hint",
        "enable_write_tools",
        "enable_subagent_tools",
        "enable_mcp_tools",
    ]
    for key in required_keys:
        assert key in fm, f"Missing required frontmatter key: {key}"

    assert fm["name"] == "cochem-audit"
    assert fm["enable_write_tools"] is True
    assert fm["enable_subagent_tools"] is True
    assert fm["enable_mcp_tools"] is True
    if "version" in fm:
        assert fm["version"] == "2.0.0"
    if "domain" in fm:
        assert fm["domain"] == "vanguard"
    if "routes_to" in fm:
        assert isinstance(fm["routes_to"], list)
        assert "0rchestrator" in fm["routes_to"]
        assert "cochem-coder" in fm["routes_to"]


def test_audit_path_sanitization_and_no_leaks(audit_path: Path) -> None:
    """Validate that cochem-audit.agent.md contains zero personal path leaks and uses standard tokens."""
    content = audit_path.read_text(encoding="utf-8")
    patterns = leak_patterns()

    leaks = []
    for line_idx, line in enumerate(content.splitlines(), start=1):
        for pattern, label in patterns:
            if pattern.search(line):
                leaks.append((line_idx, label, line.strip()))

    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s): {leaks}"
    assert "<COCHEM_WORKSPACE>" in content, "Expected <COCHEM_WORKSPACE> placeholder token"
    assert "<GDRIVE_ROOT>" in content, "Expected <GDRIVE_ROOT> placeholder token"


def test_audit_mandatory_sections_present(audit_path: Path) -> None:
    """Validate that all mandatory canonical architecture sections exist in cochem-audit.agent.md."""
    content = audit_path.read_text(encoding="utf-8")
    required_sections = [
        "# IDENTITY AND ROLE",
        "# AUTHORITATIVE KNOWLEDGE SOURCES",
        "# CORE DIRECTIVES",
        "## 1. Registry Consistency & Air-Gap Enforcement",
        "## 2. Rigorous Typing & Linting",
        "## 3. Graceful Failure & Subprocess Safety",
        "## 4. Method Matrix Compliance",
        "## 5. Provenance & Integrity",
        "## 6. Root Cause Resolution (Anti-Band-Aid) Mandate",
        "# SWARM STATE MANAGEMENT PROTOCOL",
        "# GLOBAL SWARM PROTOCOLS",
        "# OUTPUT FORMAT",
        "# WHAT I DO NOT DO",
        "# BEHAVIOR BOUNDARIES",
        "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>",
        "<SWARM_AUTONOMY_MANDATE>",
        "<ANTI_SPOOFING_COUNCIL_DIRECTIVE_v2>",
        "<ADVERSARIAL_AUDIT_DIRECTIVE>",
        "<ROOT_CAUSE_MANDATE>",
        "# ====== GLOBAL COCHEM DELEGATION & ANTI-SPOOFING DIRECTIVE v3 ======",
    ]
    for section in required_sections:
        assert section in content, f"Missing required section in cochem-audit.agent.md: {section}"


def test_audit_anti_spoofing_invariants(audit_path: Path) -> None:
    """Validate that cochem-audit.agent.md incorporates critical anti-spoofing and zero-mock protocols."""
    content = audit_path.read_text(encoding="utf-8")

    assert "zero_trust_runner.py" in content
    assert "verify_core_integrity.py" in content
    assert "MAX_PIVOT_CYCLES=3" in content
    assert "MAX_META_PIVOT=3" in content
    assert "Physics_Autopsy_Report.md" in content
    assert "cochem-audit" in content
    assert "[MISSING DATA]" in content
    assert "TolMaxG 1e-5" in content