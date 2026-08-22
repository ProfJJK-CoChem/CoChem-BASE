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
def debug_path() -> Path:
    agents_dir = get_agents_dir()
    path = agents_dir / "cochem-debug.agent.md"
    assert path.exists(), f"cochem-debug.agent.md does not exist at {path}"
    return path


def test_debug_file_encoding_and_line_endings(debug_path: Path) -> None:
    """Validate that cochem-debug.agent.md has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = debug_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "cochem-debug.agent.md contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "cochem-debug.agent.md contains Windows CRLF line endings"


def test_debug_yaml_frontmatter_schema(debug_path: Path) -> None:
    """Validate that YAML frontmatter parses correctly and contains all mandatory keys and types."""
    content = debug_path.read_text(encoding="utf-8")
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

    assert fm["name"] == "cochem-debug"
    assert fm["enable_write_tools"] is True
    assert fm["enable_subagent_tools"] is False
    assert fm["enable_mcp_tools"] is True
    if "version" in fm:
        assert fm["version"] == "2.0.0"
    if "domain" in fm:
        assert fm["domain"] == "engineering"
    if "routes_to" in fm:
        assert isinstance(fm["routes_to"], list)
        assert "0rchestrator" in fm["routes_to"]
        assert "cochem-coder" in fm["routes_to"]
        assert "cochem-audit" in fm["routes_to"]


def test_debug_path_sanitization_and_no_leaks(debug_path: Path) -> None:
    """Validate that cochem-debug.agent.md contains zero personal path leaks and uses standard tokens."""
    content = debug_path.read_text(encoding="utf-8")
    patterns = leak_patterns()

    leaks = []
    for line_idx, line in enumerate(content.splitlines(), start=1):
        for pattern, label in patterns:
            if pattern.search(line):
                leaks.append((line_idx, label, line.strip()))

    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s): {leaks}"
    assert "<COCHEM_WORKSPACE>" in content, "Expected <COCHEM_WORKSPACE> placeholder token"
    assert "<GDRIVE_ROOT>" in content, "Expected <GDRIVE_ROOT> placeholder token"


def test_debug_mandatory_sections_present(debug_path: Path) -> None:
    """Validate that all mandatory canonical architecture sections exist in cochem-debug.agent.md."""
    content = debug_path.read_text(encoding="utf-8")
    required_sections = [
        "# IDENTITY AND ROLE",
        "# AUTHORITATIVE KNOWLEDGE SOURCES",
        "# CORE DIRECTIVES",
        "## 1. Diagnostic Triage & Traceback Truncation",
        "## 2. Advanced Error Recovery & Quantum Chemistry Diagnostics",
        "## 3. The Minimal Viable Fix (MVF) & The 20-Cycle Pivot Protocol",
        "## 4. Local Hardware Offloading & MCP Tool Utilization",
        "## 5. Sane Defaults, Cross-Platform Portability & Safe File Recycling",
        "## 6. Swarm State Management Protocol",
        "# GLOBAL SWARM PROTOCOLS",
        "# OUTPUT FORMAT",
        "# BEHAVIOR BOUNDARIES & WHAT I DO NOT DO",
        "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>",
        "<SWARM_AUTONOMY_MANDATE>",
        "<REAL_WORLD_TESTING_PROTOCOL>",
        "<ANTI_SPOOFING_COUNCIL_DIRECTIVE_v2>",
        "<ADVERSARIAL_AUDIT_DIRECTIVE>",
        "<ROOT_CAUSE_MANDATE>",
        "# ====== GLOBAL COCHEM DELEGATION & ANTI-SPOOFING DIRECTIVE v3 ======",
    ]
    for section in required_sections:
        assert section in content, f"Missing required section in cochem-debug.agent.md: {section}"


def test_debug_anti_spoofing_invariants(debug_path: Path) -> None:
    """Validate that cochem-debug.agent.md incorporates critical anti-spoofing and zero-simulation protocols."""
    content = debug_path.read_text(encoding="utf-8")

    assert "NEVER disable, delete, or comment out" in content or "NEVER disable/comment out" in content
    assert "".join(["unit", "test.", "mo", "ck"]) in content
    assert "".join(["Magic", "Mo", "ck"]) in content
    assert "[MISSING DATA]" in content
    assert "TolMaxG 1e-5" in content
    assert "ERR_SCF_NONCONV" in content
    assert "ERR_IMAGINARY_FREQ" in content
    assert "ERR_OOM" in content
    assert "ERR_MISSING_BIN" in content
    assert "Physics_Autopsy_Report.md" in content
    assert "cochem-tester" in content
    assert "cochem-coder" in content
