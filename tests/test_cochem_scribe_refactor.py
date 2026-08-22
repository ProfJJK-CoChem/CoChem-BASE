"""Physical Zero-Mock Test Suite for cochem-scribe.agent.md Refactoring.

Verifies strict Unix LF line endings, UTF-8 encoding without BOM, zero personal path leakage,
YAML frontmatter schema compliance, Method Matrix invariants, automated SI compilation,
LaTeX/Mermaid escaping, SI unit standardization, MCP offloading, and structural integrity.
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
    target = get_agents_dir() / "cochem-scribe.agent.md"
    assert target.exists(), f"Target file does not exist at {target}"
    return target


def test_file_exists_and_non_empty(target_file: Path) -> None:
    """Verify that cochem-scribe.agent.md exists and has substantive content."""
    stat = target_file.stat()
    assert stat.st_size > 1000, f"File size too small ({stat.st_size} bytes)"


def test_unix_lf_line_endings(target_file: Path) -> None:
    """Verify strictly Unix LF line endings (\n) and no CRLF (\r\n)."""
    with open(target_file, "rb") as f:
        raw = f.read()
    assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in cochem-scribe.agent.md"
    assert b"\n" in raw, "Missing newline characters"


def test_utf8_encoding_no_bom(target_file: Path) -> None:
    """Verify standard UTF-8 encoding without Byte Order Mark."""
    with open(target_file, "rb") as f:
        header = f.read(3)
    assert header != b"\xef\xbb\xbf", "Found UTF-8 BOM marker in cochem-scribe.agent.md"

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

    assert data.get("name") == "cochem-scribe", f"Expected name 'cochem-scribe', got {data.get('name')}"
    assert "description" in data and len(data["description"]) > 10, "Missing or insufficient description"
    assert "argument-hint" in data, "Missing argument-hint in frontmatter"
    assert data.get("version") == "2.0.0"
    assert data.get("domain") == "writing"
    assert isinstance(data.get("routes_to"), list)
    assert "0rchestrator" in data["routes_to"]
    assert "human_read" in data["routes_to"]
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

    for sec in required_sections:
        assert sec in content, f"Missing required section: {sec}"


def test_method_matrix_provenance_and_quantum_invariants(target_file: Path) -> None:
    """Verify Method Matrix rules: grids, geometries, dispersion, spin, BSSE, and provenance tags."""
    content = target_file.read_text(encoding="utf-8")

    assert "CREST/ORCA GOAT" in content
    assert "defgrid1" in content and "defgrid3" in content
    assert "TolMaxG 1e-5" in content
    assert "Frozen-Monomer" in content
    assert "InHess XTB2" in content or "Lindh" in content
    assert "D3/D4" in content
    assert "10%" in content or r"10\%" in content
    assert "BSSE" in content or "counterpoise" in content
    assert "[M]" in content and "[D]" in content and "[E]" in content


def test_automated_si_compilation_and_citations(target_file: Path) -> None:
    """Verify SI packaging, FAIR data compliance, and bibtex generation."""
    content = target_file.read_text(encoding="utf-8")

    assert "Supporting Information" in content
    assert ".docx" in content or ".tex" in content
    assert "FAIR" in content
    assert "cochem_references.bib" in content
    assert "QCSchema" in content


def test_latex_mermaid_and_si_unit_standardization(target_file: Path) -> None:
    """Verify LaTeX math formatting, mermaid diagram rules, and SI unit standards."""
    content = target_file.read_text(encoding="utf-8")

    assert "mermaid" in content
    assert "LaTeX" in content or "latex" in content
    assert "kcal/mol" in content
    assert "Angstrom" in content
    assert "Hartrees" in content


def test_mcp_hardware_offloading(target_file: Path) -> None:
    """Verify local hardware offloading via MCP tools."""
    content = target_file.read_text(encoding="utf-8")

    assert "github-copilot" in content
    assert "ollama_generate" in content or "smart_generate" in content


def test_heading_hierarchy_integrity(target_file: Path) -> None:
    """Verify heading hierarchy and ensure no raw XML tag pollution or malformed headers."""
    content = target_file.read_text(encoding="utf-8")

    # Ensure no raw XML tags lingering
    assert "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>" not in content
    assert "<SWARM_AUTONOMY_MANDATE>" not in content
    assert "<ANTI_SPOOFING_COUNCIL_DIRECTIVE>" not in content
    assert "<ADVERSARIAL_AUDIT_DIRECTIVE>" not in content

    lines = content.splitlines()
    current_level = 0
    for lineno, line in enumerate(lines, 1):
        if line.startswith("#"):
            heading_hashes = len(line) - len(line.lstrip("#"))
            heading_text = line.lstrip("#").strip()
            if heading_hashes == 1 and current_level >= 2:
                assert heading_text in [
                    "IDENTITY AND ROLE",
                    "AUTHORITATIVE KNOWLEDGE SOURCES",
                    "CORE DIRECTIVES",
                    "GLOBAL SWARM PROTOCOLS",
                    "OUTPUT FORMAT",
                    "BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
                ], f"Improper H1 header inside section at line {lineno}: {line}"
            current_level = heading_hashes


def test_behavior_boundaries_defined(target_file: Path) -> None:
    """Verify clear behavior boundaries, routing, and safe recycling."""
    content = target_file.read_text(encoding="utf-8")

    assert "cochem-coder" in content
    assert "cochem-debug" in content
    assert "cochem-improve" in content
    assert "cochem-audit" in content
    assert "cochem-tester" in content
    assert ".trash" in content
    assert "shutil.move" in content
