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
def scribe_path() -> Path:
    agents_dir = get_agents_dir()
    path = agents_dir / "cochem-scribe.agent.md"
    assert path.exists(), f"cochem-scribe.agent.md does not exist at {path}"
    return path


def test_scribe_file_encoding_and_line_endings(scribe_path: Path) -> None:
    """Validate that cochem-scribe.agent.md has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = scribe_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "cochem-scribe.agent.md contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "cochem-scribe.agent.md contains Windows CRLF line endings"


def test_scribe_yaml_frontmatter_schema(scribe_path: Path) -> None:
    """Validate that YAML frontmatter parses correctly and contains all mandatory keys and types."""
    content = scribe_path.read_text(encoding="utf-8")
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

    assert fm["name"] == "cochem-scribe"
    assert fm["enable_write_tools"] is True
    assert fm["enable_subagent_tools"] is False
    assert fm["enable_mcp_tools"] is True
    if "version" in fm:
        assert fm["version"] == "2.0.0"
    if "domain" in fm:
        assert fm["domain"] == "writing"
    if "routes_to" in fm:
        assert isinstance(fm["routes_to"], list)
        assert "0rchestrator" in fm["routes_to"]
        assert "human_read" in fm["routes_to"]
        assert "cochem-audit" in fm["routes_to"]


def test_scribe_path_sanitization_and_no_leaks(scribe_path: Path) -> None:
    """Validate that cochem-scribe.agent.md contains zero personal path leaks and uses standard tokens."""
    content = scribe_path.read_text(encoding="utf-8")
    patterns = leak_patterns()

    leaks = []
    for line_idx, line in enumerate(content.splitlines(), start=1):
        for pattern, label in patterns:
            if pattern.search(line):
                leaks.append((line_idx, label, line.strip()))

    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s): {leaks}"
    assert "<COCHEM_WORKSPACE>" in content, "Expected <COCHEM_WORKSPACE> placeholder token"
    assert "<GDRIVE_ROOT>" in content, "Expected <GDRIVE_ROOT> placeholder token"


def test_scribe_mandatory_sections_present(scribe_path: Path) -> None:
    """Validate that all mandatory canonical architecture sections exist in cochem-scribe.agent.md."""
    content = scribe_path.read_text(encoding="utf-8")
    required_sections = [
        "# IDENTITY AND ROLE",
        "# AUTHORITATIVE KNOWLEDGE SOURCES",
        "# CORE DIRECTIVES",
        "## 1. Method Matrix Provenance Tagging & Quantum Chemistry Compliance",
        "## 2. Automated SI Compilation, Citation & FAIR Compliance",
        "## 3. LaTeX and Mermaid Escaping Validation",
        "## 4. Zero Truncation & SI Unit Standardization",
        "## 5. Local Hardware Offloading & MCP Tool Utilization",
        "## 6. Human Read Handoff & Aesthetic Polish",
        "## 7. Sane Defaults, Cross-Platform Portability & Safe File Handling",
        "## 8. Swarm State Management Protocol",
        "# GLOBAL SWARM PROTOCOLS",
        "# OUTPUT FORMAT",
        "# BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
    ]
    for section in required_sections:
        assert section in content, f"Missing required section in cochem-scribe.agent.md: {section}"


def test_scribe_anti_spoofing_invariants(scribe_path: Path) -> None:
    """Validate that cochem-scribe.agent.md incorporates critical anti-spoofing and zero-mock protocols."""
    content = scribe_path.read_text(encoding="utf-8")

    assert "cochem_references.bib" in content
    assert "human_read" in content
    assert "cochem-audit" in content
    assert "[MISSING DATA]" in content
