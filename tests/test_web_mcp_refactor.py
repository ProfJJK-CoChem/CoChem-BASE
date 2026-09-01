"""Physical Zero-Mock Test Suite for web_mcp.agent.md Refactoring.

Verifies strict Unix LF line endings, UTF-8 encoding without BOM, zero personal path leakage,
YAML frontmatter schema compliance, DOM sanitization, SPA fast-fail protocol, MCP web scraping,
anti-spoofing directives, and structural integrity.
"""

from pathlib import Path
import pytest
import yaml

from cochem_base.path_sanitization import (
    get_agents_dir,
    leak_patterns,
)


@pytest.fixture
def target_file() -> Path:
    target = get_agents_dir() / "web_mcp.agent.md"
    assert target.exists(), f"Target file does not exist at {target}"
    return target


def test_file_exists_and_non_empty(target_file: Path) -> None:
    """Verify that web_mcp.agent.md exists and has substantive content."""
    stat = target_file.stat()
    assert stat.st_size > 1000, f"File size too small ({stat.st_size} bytes)"


def test_unix_lf_line_endings(target_file: Path) -> None:
    """Verify strictly Unix LF line endings (\n) and no CRLF (\r\n)."""
    with open(target_file, "rb") as f:
        raw = f.read()
    assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in web_mcp.agent.md"
    assert b"\n" in raw, "Missing newline characters"


def test_utf8_encoding_no_bom(target_file: Path) -> None:
    """Verify standard UTF-8 encoding without Byte Order Mark."""
    with open(target_file, "rb") as f:
        header = f.read(3)
    assert header != b"\xef\xbb\xbf", "Found UTF-8 BOM marker in web_mcp.agent.md"

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
    content = target_file.read_text(encoding="utf-8")
    assert "<COCHEM_WORKSPACE>" in content, "Expected <COCHEM_WORKSPACE> placeholder token"
    assert "<GDRIVE_ROOT>" in content, "Expected <GDRIVE_ROOT> placeholder token"


def test_yaml_frontmatter_validity(target_file: Path) -> None:
    """Verify valid YAML frontmatter and required schema attributes."""
    content = target_file.read_text(encoding="utf-8")
    assert content.startswith("---"), "Document must start with YAML frontmatter delimiter (---)"
    parts = content.split("---", 2)
    assert len(parts) >= 3, "Frontmatter must be enclosed between '---' delimiters"

    fm_raw = parts[1].strip()
    data = yaml.safe_load(fm_raw)
    assert isinstance(data, dict), "Frontmatter must parse into a dictionary"

    assert data.get("name") == "web-mcp", f"Expected name 'web-mcp', got {data.get('name')}"
    assert "description" in data and len(data["description"]) > 10, "Missing or insufficient description"
    assert "argument-hint" in data, "Missing argument-hint in frontmatter"
    assert data.get("version") == "2.0.0"
    assert data.get("domain") == "interface"
    assert isinstance(data.get("routes_to"), list)
    assert "0rchestrator" in data["routes_to"]
    assert "researcher" in data["routes_to"]
    assert "cochem-audit" in data["routes_to"]
    assert data.get("enable_write_tools") is True, "enable_write_tools must be true"
    assert data.get("enable_subagent_tools") is False, "enable_subagent_tools must be false"
    assert data.get("enable_mcp_tools") is True, "enable_mcp_tools must be true"


def test_canonical_sections_present(target_file: Path) -> None:
    """Verify all mandatory sections and core directives are present."""
    content = target_file.read_text(encoding="utf-8")

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

    for sec in required_sections:
        assert sec in content, f"Missing required section: {sec}"


def test_web_mcp_core_directives_invariants(target_file: Path) -> None:
    """Verify web scraping directives, SPA protocol, DOM sanitization, and provenance tags."""
    content = target_file.read_text(encoding="utf-8")

    assert "read_url_content" in content
    assert "chrome-devtools" in content
    assert "document.body.innerText" in content
    assert "SPA WALL DETECTED" in content
    assert "[WEB SCRAPE RESULT]" in content
    assert "[AUTH REQUIRED]" in content
    assert "[M]" in content and "[D]" in content and "[E]" in content


def test_anti_spoofing_directives(target_file: Path) -> None:
    """Verify anti-spoofing, council handoff, and zero-mock requirements."""
    content = target_file.read_text(encoding="utf-8")

    assert "MAX_META_PIVOT=3" in content
    assert "[MISSING DATA]" in content
    assert "cochem-audit" in content
    assert "send_message" in content
