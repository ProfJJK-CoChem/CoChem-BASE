"""Physical Zero-Mock Test Suite for educator.agent.md Refactoring.

Verifies strict line endings, UTF-8 encoding, zero personal path leakage,
frontmatter schema compliance, pedagogical frameworks (CER, SPARK, ZPD, Bloom's L1-L6, NGSS, ACS),
AST code auditing, Method Matrix invariants, and structural integrity.
"""

from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from cochem_base.path_sanitization import (
    get_agents_dir,
    leak_patterns,
)


@pytest.fixture
def target_file() -> Path:
    target = get_agents_dir() / "educator.agent.md"
    assert target.exists(), f"Target file does not exist at {target}"
    return target


def test_file_exists_and_non_empty(target_file: Path) -> None:
    """Verify that educator.agent.md exists and has substantive content."""
    stat = target_file.stat()
    assert stat.st_size > 1000, f"File size too small ({stat.st_size} bytes)"


def test_unix_lf_line_endings(target_file: Path) -> None:
    """Verify strictly Unix LF line endings (\\n) and no CRLF (\\r\\n)."""
    with open(target_file, "rb") as f:
        raw = f.read()
    assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in educator.agent.md"
    assert b"\n" in raw, "Missing newline characters"


def test_utf8_encoding_no_bom(target_file: Path) -> None:
    """Verify standard UTF-8 encoding without Byte Order Mark."""
    with open(target_file, "rb") as f:
        header = f.read(3)
    assert header != b"\xef\xbb\xbf", "Found UTF-8 BOM marker in educator.agent.md"

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


def test_yaml_frontmatter_validity(target_file: Path) -> None:
    """Verify valid YAML frontmatter and required schema attributes."""
    content = target_file.read_text(encoding="utf-8")
    assert content.startswith("---"), "Document must start with YAML frontmatter delimiter (---)"
    parts = content.split("---", 2)
    assert len(parts) >= 3, "Frontmatter must be enclosed between '---' delimiters"

    fm_raw = parts[1].strip()
    data = yaml.safe_load(fm_raw)
    assert isinstance(data, dict), "Frontmatter must parse into a dictionary"

    assert data.get("name") == "educator", f"Expected name 'educator', got {data.get('name')}"
    assert "description" in data and len(data["description"]) > 10, (
        "Missing or insufficient description"
    )
    assert "argument-hint" in data, "Missing argument-hint in frontmatter"
    assert data.get("enable_write_tools") is True, "enable_write_tools must be true"
    assert data.get("enable_mcp_tools") is True, "enable_mcp_tools must be true"


def test_canonical_sections_present(target_file: Path) -> None:
    """Verify all mandatory sections and core directives are present."""
    content = target_file.read_text(encoding="utf-8")

    required_sections = [
        "# IDENTITY AND ROLE",
        "# AUTHORITATIVE KNOWLEDGE SOURCES",
        "# CORE DIRECTIVES",
        "## 1. Scientific Inquiry Frameworks (CER & SPARK)",
        "## 2. Bloom's Taxonomy Cognitive Escalation & Standards Alignment",
        "## 3. Friction by Design, Productive Struggle & Misconception Traps",
        "## 4. Automated Grading, Rubrics & AST Code Provenance Auditing",
        "## 5. Multidisciplinary STEM Didactics & Macroscopic-Microscopic Bridging",
        "## 6. Method Matrix v4 Compliance in Educational Artifacts",
        "# GLOBAL SWARM PROTOCOLS",
        "# OUTPUT FORMAT",
        "# BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
    ]

    for sec in required_sections:
        assert sec in content, f"Missing required section: {sec}"


def test_pedagogical_frameworks_mandates(target_file: Path) -> None:
    """Verify CER, SPARK, ZPD, Bloom's Taxonomy levels, and standards alignment."""
    content = target_file.read_text(encoding="utf-8")

    # CER & SPARK
    assert "CER Framework" in content
    assert "Claim" in content and "Evidence" in content and "Reasoning" in content
    assert "SPARK Framework" in content
    assert (
        "Statement" in content
        and "Proof" in content
        and "Analysis" in content
        and "Knowledge" in content
    )
    assert "Zone of Proximal Development" in content or "ZPD" in content

    # Bloom's levels
    for level in [
        "[L1-Remember]",
        "[L2-Understand]",
        "[L3-Apply]",
        "[L4-Analyze]",
        "[L5-Evaluate]",
        "[L6-Create]",
    ]:
        assert level in content, f"Missing Bloom's level: {level}"

    # Standards
    assert "ACS" in content
    assert "NGSS" in content


def test_friction_and_misconceptions(target_file: Path) -> None:
    """Verify productive struggle, misconception traps, and fading scaffolding."""
    content = target_file.read_text(encoding="utf-8")

    assert "Productive Struggle" in content
    assert "Misconception Traps" in content
    assert "Fading Scaffolding" in content
    assert "Exemplar" in content or "Good vs. Bad" in content


def test_automated_grading_and_ast_auditing(target_file: Path) -> None:
    """Verify AST code provenance auditing, double-blind grading, and RAI penalty matrix."""
    content = target_file.read_text(encoding="utf-8")

    assert "AST" in content
    assert "Abstract Syntax Tree" in content
    assert "Double-Blind" in content
    assert "Research Aptitude Index" in content or "RAI" in content


def test_method_matrix_invariants(target_file: Path) -> None:
    """Verify Method Matrix rules: grids, geometries, dispersion, spin, BSSE, and provenance."""
    content = target_file.read_text(encoding="utf-8")

    assert "CREST/ORCA GOAT" in content
    assert "defgrid1" in content and "defgrid3" in content
    assert "TolMaxG 1e-5" in content
    assert "Frozen-Monomer" in content
    assert "InHess XTB2" in content or "Lindh" in content
    assert "D3/D4" in content
    assert "10%" in content or "10\\%" in content
    assert "BSSE" in content or "counterpoise" in content
    assert "[M]" in content and "[D]" in content and "[E]" in content


def test_heading_hierarchy_and_clean_markdown(target_file: Path) -> None:
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
    """Verify clear behavior boundaries, backend-only role, and prohibitions."""
    content = target_file.read_text(encoding="utf-8")

    assert "BACKEND" in content or "backend" in content
    assert "teacher" in content
    assert "cochem-coder" in content or "cochem-tester" in content
    assert ".trash" in content
