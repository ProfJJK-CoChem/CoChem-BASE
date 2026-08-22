"""Physical Zero-Mock Test Suite for cochem-helper.agent.md Refactoring.

Verifies strict Unix LF line endings, UTF-8 encoding without BOM, zero personal path leakage,
YAML frontmatter schema compliance, Method Matrix invariants, rote work automation, user-facing error translation,
SI publication support, MCP offloading, and structural integrity.
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
    target = get_agents_dir() / "cochem-helper.agent.md"
    assert target.exists(), f"Target file does not exist at {target}"
    return target


def test_file_exists_and_non_empty(target_file: Path) -> None:
    """Verify that cochem-helper.agent.md exists and has substantive content."""
    stat = target_file.stat()
    assert stat.st_size > 1000, f"File size too small ({stat.st_size} bytes)"


def test_unix_lf_line_endings(target_file: Path) -> None:
    """Verify strictly Unix LF line endings (\n) and no CRLF (\r\n)."""
    with open(target_file, "rb") as f:
        raw = f.read()
    assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in cochem-helper.agent.md"
    assert b"\n" in raw, "Missing newline characters"


def test_utf8_encoding_no_bom(target_file: Path) -> None:
    """Verify standard UTF-8 encoding without Byte Order Mark."""
    with open(target_file, "rb") as f:
        header = f.read(3)
    assert header != b"\xef\xbb\xbf", "Found UTF-8 BOM marker in cochem-helper.agent.md"

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

    assert data.get("name") == "cochem-helper", f"Expected name 'cochem-helper', got {data.get('name')}"
    assert "description" in data and len(data["description"]) > 10, "Missing or insufficient description"
    assert "argument-hint" in data, "Missing argument-hint in frontmatter"
    assert data.get("version") == "2.0.0"
    assert data.get("domain") == "writing"
    assert isinstance(data.get("routes_to"), list)
    assert "0rchestrator" in data["routes_to"]
    assert "cochem-debug" in data["routes_to"]
    assert "cochem-scribe" in data["routes_to"]
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

    for sec in required_sections:
        assert sec in content, f"Missing required section: {sec}"


def test_method_matrix_invariants(target_file: Path) -> None:
    """Verify Method Matrix rules: grids, geometries, dispersion, spin, BSSE, and provenance."""
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


def test_automating_rote_work_and_spectral_processing(target_file: Path) -> None:
    """Verify automation of rote tasks, regex parsing, LTTB downsampling, and isotope substitution."""
    content = target_file.read_text(encoding="utf-8")

    assert "os.makedirs" in content
    assert "pathlib.Path" in content
    assert "LTTB" in content or "Largest Triangle Three Buckets" in content
    assert "pyarrow" in content or "dask" in content
    assert "KIE" in content or "Kinetic Isotope Effects" in content


def test_user_error_translation_and_publication_support(target_file: Path) -> None:
    """Verify user-facing error triage, SI compilation, and SI unit standardization."""
    content = target_file.read_text(encoding="utf-8")

    assert "SCF" in content
    assert "MaxIter" in content or "SlowConv" in content or "SOSCF" in content
    assert "Supporting Information" in content or "SI" in content
    assert ".docx" in content or ".tex" in content
    assert "SI Unit Standardization" in content or "kcal/mol" in content


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
    assert "teacher" in content
    assert "cochem-improve" in content
    assert "cochem-audit" in content
    assert ".trash" in content
    assert "shutil.move" in content
