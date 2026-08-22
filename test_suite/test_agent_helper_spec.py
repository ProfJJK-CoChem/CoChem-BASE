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
def helper_path() -> Path:
    agents_dir = get_agents_dir()
    path = agents_dir / "cochem-helper.agent.md"
    assert path.exists(), f"cochem-helper.agent.md does not exist at {path}"
    return path


def test_helper_file_encoding_and_line_endings(helper_path: Path) -> None:
    """Validate that cochem-helper.agent.md has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = helper_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "cochem-helper.agent.md contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "cochem-helper.agent.md contains Windows CRLF line endings"


def test_helper_yaml_frontmatter_schema(helper_path: Path) -> None:
    """Validate that YAML frontmatter parses correctly and contains all mandatory keys and types."""
    content = helper_path.read_text(encoding="utf-8")
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

    assert fm["name"] == "cochem-helper"
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
        assert "cochem-debug" in fm["routes_to"]


def test_helper_path_sanitization_and_no_leaks(helper_path: Path) -> None:
    """Validate that cochem-helper.agent.md contains zero personal path leaks and uses standard tokens."""
    content = helper_path.read_text(encoding="utf-8")
    patterns = leak_patterns()

    leaks = []
    for line_idx, line in enumerate(content.splitlines(), start=1):
        for pattern, label in patterns:
            if pattern.search(line):
                leaks.append((line_idx, label, line.strip()))

    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s): {leaks}"
    assert "<COCHEM_WORKSPACE>" in content, "Expected <COCHEM_WORKSPACE> placeholder token"
    assert "<GDRIVE_ROOT>" in content, "Expected <GDRIVE_ROOT> placeholder token"


def test_helper_mandatory_sections_present(helper_path: Path) -> None:
    """Validate that all mandatory canonical architecture sections exist in cochem-helper.agent.md."""
    content = helper_path.read_text(encoding="utf-8")
    required_sections = [
        "# IDENTITY AND ROLE",
        "# AUTHORITATIVE KNOWLEDGE SOURCES",
        "# CORE DIRECTIVES",
        "## 1. Method Matrix Enforcement & Quantum Chemistry Invariants",
        "## 2. Automating Rote Work & Pipeline Scaffolding",
        "## 3. Human-Readable Error Translations (User-Facing Triage)",
        "## 4. Publication Support & SI Package Standardization",
        "## 5. Local Hardware Offloading & MCP Tool Utilization",
        "## 6. Sane Defaults, Safe File Handling & Environment Portability",
        "## 7. Swarm State Management Protocol",
        "# GLOBAL SWARM PROTOCOLS",
        "# OUTPUT FORMAT",
        "# BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
    ]
    for section in required_sections:
        assert section in content, f"Missing required section in cochem-helper.agent.md: {section}"


def test_helper_anti_spoofing_invariants(helper_path: Path) -> None:
    """Validate that cochem-helper.agent.md incorporates critical anti-spoofing and zero-mock protocols."""
    content = helper_path.read_text(encoding="utf-8")

    assert "TolMaxG 1e-5" in content
    assert "cochem-debug" in content
    assert "cochem-audit" in content
    assert "[MISSING DATA]" in content
