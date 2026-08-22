"""Physical Zero-Mock Test Suite for artist.agent.md Refactoring.

Verifies strict Unix LF line endings, UTF-8 encoding without BOM, zero personal path leakage,
YAML frontmatter schema compliance, ACS graphic standards, negative prompting, vector preference,
MCP offloading, anti-spoofing directives, and structural integrity.
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
    target = get_agents_dir() / "artist.agent.md"
    assert target.exists(), f"Target file does not exist at {target}"
    return target


def test_file_exists_and_non_empty(target_file: Path) -> None:
    """Verify that artist.agent.md exists and has substantive content."""
    stat = target_file.stat()
    assert stat.st_size > 1000, f"File size too small ({stat.st_size} bytes)"


def test_unix_lf_line_endings(target_file: Path) -> None:
    """Verify strictly Unix LF line endings (\n) and no CRLF (\r\n)."""
    with open(target_file, "rb") as f:
        raw = f.read()
    assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in artist.agent.md"
    assert b"\n" in raw, "Missing newline characters"


def test_utf8_encoding_no_bom(target_file: Path) -> None:
    """Verify standard UTF-8 encoding without Byte Order Mark."""
    with open(target_file, "rb") as f:
        header = f.read(3)
    assert header != b"\xef\xbb\xbf", "Found UTF-8 BOM marker in artist.agent.md"

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

    assert data.get("name") == "artist", f"Expected name 'artist', got {data.get('name')}"
    assert "description" in data and len(data["description"]) > 10, "Missing or insufficient description"
    assert "argument-hint" in data, "Missing argument-hint in frontmatter"
    assert data.get("version") == "2.0.0"
    assert data.get("domain") == "interface"
    assert isinstance(data.get("routes_to"), list)
    assert "0rchestrator" in data["routes_to"]
    assert "cochem-scribe" in data["routes_to"]
    assert "ui" in data["routes_to"]
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
        "## 1. Native Image Generation",
        "## 2. External Prompt Crafting",
        "## 3. Negative Prompting",
        "## 4. Vector Graphics Preference",
        "## 5. Local Hardware Offloading & MCP Tool Utilization",
        "## 6. Swarm State Management Protocol",
        "# GLOBAL SWARM PROTOCOLS",
        "# OUTPUT FORMAT",
        "# WHAT I DO NOT DO",
        "# BEHAVIOR BOUNDARIES",
        "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>",
        "<SWARM_AUTONOMY_MANDATE>",
        "<ANTI_SPOOFING_COUNCIL_DIRECTIVE>",
        "<ADVERSARIAL_AUDIT_DIRECTIVE>",
        "# ====== GLOBAL COCHEM DELEGATION & ANTI-SPOOFING DIRECTIVE v3 ======",
    ]

    for sec in required_sections:
        assert sec in content, f"Missing required section: {sec}"


def test_artist_core_directives_invariants(target_file: Path) -> None:
    """Verify native image generation, negative prompting, ACS specs, and vector preference."""
    content = target_file.read_text(encoding="utf-8")

    assert "generate_image" in content
    assert "AspectRatio" in content
    assert "ImageName" in content
    assert "Negative Prompt" in content
    assert "SVG" in content or "svg" in content
    assert "PDF" in content or "pdf" in content
    assert ".jpg" in content
    assert "3.25 inches" in content or "3.25 in" in content
    assert "7.00 inches" in content or "7.00 in" in content
    assert "300 DPI" in content
    assert "CPK" in content
    assert "[M]" in content and "[D]" in content and "[E]" in content


def test_mcp_hardware_offloading(target_file: Path) -> None:
    """Verify local hardware offloading via MCP tools."""
    content = target_file.read_text(encoding="utf-8")

    assert "github-copilot" in content
    assert "ollama_generate" in content or "smart_generate" in content


def test_anti_spoofing_directives(target_file: Path) -> None:
    """Verify anti-spoofing and zero-mock requirements."""
    content = target_file.read_text(encoding="utf-8")

    assert "MAX_META_PIVOT=3" in content
    assert "[MISSING DATA]" in content
    assert "cochem-audit" in content
    assert "cochem-coder" in content
    assert ".trash" in content
    assert "shutil.move" in content
