"""Physical Verification Test Suite for cochem-tester.agent.md Refactoring.

Verifies strict line endings, UTF-8 encoding, zero personal path leakage,
frontmatter schema compliance, Method Matrix invariants, and structural integrity.
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
    target = get_agents_dir() / "cochem-tester.agent.md"
    assert target.exists(), f"Target file does not exist at {target}"
    return target


def test_file_exists_and_non_empty(target_file: Path) -> None:
    """Verify that cochem-tester.agent.md exists and has substantive content."""
    stat = target_file.stat()
    assert stat.st_size > 1000, f"File size too small ({stat.st_size} bytes)"


def test_unix_lf_line_endings(target_file: Path) -> None:
    """Verify strictly Unix LF line endings (\n) and no CRLF (\r\n)."""
    with open(target_file, "rb") as f:
        raw = f.read()
    assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in cochem-tester.agent.md"
    assert b"\n" in raw, "Missing newline characters"


def test_utf8_encoding_no_bom(target_file: Path) -> None:
    """Verify standard UTF-8 encoding without Byte Order Mark."""
    with open(target_file, "rb") as f:
        header = f.read(3)
    assert header != b"\xef\xbb\xbf", "Found UTF-8 BOM marker in cochem-tester.agent.md"

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

    assert data.get("name") == "cochem-tester", f"Expected name 'cochem-tester', got {data.get('name')}"
    assert "description" in data and len(data["description"]) > 10, "Missing or insufficient description"
    assert "argument-hint" in data, "Missing argument-hint in frontmatter"
    assert data.get("version") == "2.0.0"
    assert data.get("domain") == "vanguard"
    assert isinstance(data.get("routes_to"), list)
    assert "0rchestrator" in data["routes_to"]
    assert "cochem-debug" in data["routes_to"]
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
        "## 1. Absolute Zero-Mock Policy & Real Binary Execution",
        "## 2. Real-World Molecular Validation & Edge-Case Stress Testing",
        "## 3. Scientific Output Validation & Method Matrix Compliance",
        "## 4. Professional Pytest Architecture & Headless Execution",
        "## 5. Process Lifecycle & Resource Monitoring",
        "## 6. Swarm Integration & Error Escalation",
        "# GLOBAL SWARM PROTOCOLS",
        "# OUTPUT FORMAT",
        "# BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
    ]

    for sec in required_sections:
        assert sec in content, f"Missing required section: {sec}"


def test_zero_simulation_and_physical_testing_mandates(target_file: Path) -> None:
    """Verify zero-simulation constraints and real physical binary execution requirements."""
    content = target_file.read_text(encoding="utf-8")

    assert "NEVER use mocks" in content or "NEVER mocks" in content
    assert "patch" in content and "mock" in content
    assert "MagicMock" in content
    assert "[ERR_MISSING_BIN]" in content
    assert "ORCA" in content
    assert "PySCF" in content
    assert "MACE" in content
    assert "CREST" in content
    assert "XTB" in content


def test_method_matrix_invariants(target_file: Path) -> None:
    """Verify Method Matrix rules: grids, geometries, dispersion, spin, BSSE, and provenance."""
    content = target_file.read_text(encoding="utf-8")

    assert "CREST/ORCA GOAT" in content
    assert "defgrid1" in content and "defgrid3" in content
    assert "TolMaxG 1e-5" in content
    assert "Frozen-Monomer" in content
    assert "InHess XTB2" in content
    assert "D3/D4" in content
    assert "10%" in content or r"10\%" in content
    assert "BSSE" in content or "counterpoise" in content
    assert "[M]" in content and "[D]" in content and "[E]" in content


def test_pytest_and_process_monitoring(target_file: Path) -> None:
    """Verify pytest architecture, pytest-qt headless execution, and psutil monitoring."""
    content = target_file.read_text(encoding="utf-8")

    assert "pytest-qt" in content
    assert "QTest" in content
    assert "psutil" in content
    assert "RAM" in content


def test_heading_hierarchy_integrity(target_file: Path) -> None:
    """Verify heading hierarchy and ensure no raw XML tag pollution or malformed headers."""
    content = target_file.read_text(encoding="utf-8")

    # Ensure no raw XML tags lingering
    assert "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>" not in content
    assert "<SWARM_AUTONOMY_MANDATE>" not in content
    assert "<ANTI_SPOOFING_COUNCIL_DIRECTIVE" not in content
    assert "<ADVERSARIAL_AUDIT_DIRECTIVE>" not in content

    lines = content.splitlines()
    current_level = 0
    for lineno, line in enumerate(lines, 1):
        if line.startswith("#"):
            heading_hashes = len(line) - len(line.lstrip("#"))
            heading_text = line.lstrip("#").strip()
            # If we are inside CORE DIRECTIVES (H1) and a sub-section (H2), we shouldn't jump back to H1 without exiting
            if heading_hashes == 1 and current_level >= 2:
                # Only allowed top-level H1 headers
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
    """Verify clear behavior boundaries and prohibitions."""
    content = target_file.read_text(encoding="utf-8")

    assert "I NEVER use mocks" in content
    assert "cochem-debug" in content
    assert "cochem-coder" in content
    assert ".trash" in content
    assert "shutil.move" in content

