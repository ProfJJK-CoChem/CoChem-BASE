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
def web_mcp_path() -> Path:
    agents_dir = get_agents_dir()
    path = agents_dir / "web_mcp.agent.md"
    assert path.exists(), f"web_mcp.agent.md does not exist at {path}"
    return path


def test_web_mcp_file_encoding_and_line_endings(web_mcp_path: Path) -> None:
    """Validate that web_mcp.agent.md has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = web_mcp_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "web_mcp.agent.md contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "web_mcp.agent.md contains Windows CRLF line endings"


def test_web_mcp_yaml_frontmatter_schema(web_mcp_path: Path) -> None:
    """Validate that YAML frontmatter parses correctly and contains all mandatory keys and types."""
    content = web_mcp_path.read_text(encoding="utf-8")
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

    assert fm["name"] == "web-mcp"
    assert fm["enable_write_tools"] is True
    assert fm["enable_subagent_tools"] is False
    assert fm["enable_mcp_tools"] is True
    if "version" in fm:
        assert fm["version"] == "2.0.0"
    if "domain" in fm:
        assert fm["domain"] == "interface"
    if "routes_to" in fm:
        assert isinstance(fm["routes_to"], list)
        assert "0rchestrator" in fm["routes_to"]
        assert "researcher" in fm["routes_to"]
        assert "cochem-audit" in fm["routes_to"]


def test_web_mcp_path_sanitization_and_no_leaks(web_mcp_path: Path) -> None:
    """Validate that web_mcp.agent.md contains zero personal path leaks and uses standard tokens."""
    content = web_mcp_path.read_text(encoding="utf-8")
    patterns = leak_patterns()

    leaks = []
    for line_idx, line in enumerate(content.splitlines(), start=1):
        for pattern, label in patterns:
            if pattern.search(line):
                leaks.append((line_idx, label, line.strip()))

    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s): {leaks}"
    assert "<COCHEM_WORKSPACE>" in content, "Expected <COCHEM_WORKSPACE> placeholder token"
    assert "<GDRIVE_ROOT>" in content, "Expected <GDRIVE_ROOT> placeholder token"


def test_web_mcp_mandatory_sections_present(web_mcp_path: Path) -> None:
    """Validate that all mandatory canonical architecture sections exist in web_mcp.agent.md."""
    content = web_mcp_path.read_text(encoding="utf-8")
    required_sections = [
        "# IDENTITY AND ROLE",
        "# AUTHORITATIVE KNOWLEDGE SOURCES",
        "# CORE DIRECTIVES",
        "## 1. Precision Web Scraping",
        "## 2. DOM Sanitization (Token Efficiency)",
        "## 3. Timeout Watchdogs & Blank Traps",
        "## 4. SPA Fast-Fail Protocol (Zero-Cost / Token-Efficient)",
        "# GLOBAL SWARM PROTOCOLS",
        "# OUTPUT FORMAT",
        "# WHAT I DO NOT DO",
        "# SECURITY",
        "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>",
        "<SWARM_AUTONOMY_MANDATE>",
        "<ANTI_SPOOFING_COUNCIL_DIRECTIVE>",
        "<ADVERSARIAL_AUDIT_DIRECTIVE>",
        "# ====== GLOBAL COCHEM DELEGATION & ANTI-SPOOFING DIRECTIVE v3 ======",
    ]
    for section in required_sections:
        assert section in content, f"Missing required section in web_mcp.agent.md: {section}"


def test_web_mcp_anti_spoofing_invariants(web_mcp_path: Path) -> None:
    """Validate that web_mcp.agent.md incorporates critical anti-spoofing and zero-mock protocols."""
    content = web_mcp_path.read_text(encoding="utf-8")

    assert "read_url_content" in content
    assert "chrome-devtools" in content
    assert "document.body.innerText" in content
    assert "MAX_META_PIVOT=3" in content
    assert "cochem-audit" in content
    assert "[MISSING DATA]" in content
    assert "[M]" in content and "[D]" in content and "[E]" in content
