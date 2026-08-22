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
def sdp_manager_path() -> Path:
    agents_dir = get_agents_dir()
    path = agents_dir / "cochem-sdp_manager.agent.md"
    assert path.exists(), f"cochem-sdp_manager.agent.md does not exist at {path}"
    return path


def test_sdp_manager_file_encoding_and_line_endings(sdp_manager_path: Path) -> None:
    """Validate that cochem-sdp_manager.agent.md has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = sdp_manager_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "cochem-sdp_manager.agent.md contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "cochem-sdp_manager.agent.md contains Windows CRLF line endings"


def test_sdp_manager_yaml_frontmatter_schema(sdp_manager_path: Path) -> None:
    """Validate that YAML frontmatter parses correctly and contains all mandatory keys and types."""
    content = sdp_manager_path.read_text(encoding="utf-8")
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

    assert fm["name"] == "cochem-sdp_manager"
    assert fm["enable_write_tools"] is True
    assert fm["enable_subagent_tools"] is True
    assert fm["enable_mcp_tools"] is True
    if "version" in fm:
        assert fm["version"] == "2.0.0"
    if "domain" in fm:
        assert fm["domain"] == "vanguard"
    if "routes_to" in fm:
        assert isinstance(fm["routes_to"], list)
        assert "0rchestrator" in fm["routes_to"]
        assert "researcher" in fm["routes_to"]
        assert "cochem-audit" in fm["routes_to"]
        assert "cochem-improve" in fm["routes_to"]
        assert "cochem-coder" in fm["routes_to"]
        assert "cochem-tester" in fm["routes_to"]


def test_sdp_manager_path_sanitization_and_no_leaks(sdp_manager_path: Path) -> None:
    """Validate that cochem-sdp_manager.agent.md contains zero personal path leaks and uses standard tokens."""
    content = sdp_manager_path.read_text(encoding="utf-8")
    patterns = leak_patterns()

    leaks = []
    for line_idx, line in enumerate(content.splitlines(), start=1):
        for pattern, label in patterns:
            if pattern.search(line):
                leaks.append((line_idx, label, line.strip()))

    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s): {leaks}"
    assert "<COCHEM_WORKSPACE>" in content, "Expected <COCHEM_WORKSPACE> placeholder token"
    assert "<GDRIVE_ROOT>" in content, "Expected <GDRIVE_ROOT> placeholder token"


def test_sdp_manager_mandatory_sections_present(sdp_manager_path: Path) -> None:
    """Validate that all mandatory canonical architecture sections exist in cochem-sdp_manager.agent.md."""
    content = sdp_manager_path.read_text(encoding="utf-8")
    required_sections = [
        "# IDENTITY AND ROLE",
        "# AUTHORITATIVE KNOWLEDGE SOURCES",
        "# CORE DIRECTIVES",
        "## 1. Absolute Task Breakdown & 3-Tier WBS Mandate",
        "## 2. Project Planning & Artifact Generation (PMBOK/SWEBOK)",
        "## 3. Vanguard Swarm Coordination",
        "## 4. Swarm Task Guidance & Method Matrix Compliance",
        "## 5. Iterative Adaptation & Agile/Hybrid PM",
        "## SWARM STATE MANAGEMENT PROTOCOL",
        "# GLOBAL SWARM PROTOCOLS",
        "# OUTPUT FORMAT",
        "# WHAT I DO NOT DO",
        "# BEHAVIOR BOUNDARIES",
        "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>",
        "<SWARM_AUTONOMY_MANDATE>",
        "<ANTI_SPOOFING_COUNCIL_DIRECTIVE_v2>",
        "<ADVERSARIAL_AUDIT_DIRECTIVE>",
        "<ROOT_CAUSE_MANDATE>",
        "# ====== GLOBAL COCHEM DELEGATION & ANTI-SPOOFING DIRECTIVE v3 ======",
    ]
    for section in required_sections:
        assert section in content, f"Missing required section in cochem-sdp_manager.agent.md: {section}"


def test_sdp_manager_anti_spoofing_invariants(sdp_manager_path: Path) -> None:
    """Validate that cochem-sdp_manager.agent.md incorporates critical anti-spoofing and zero-mock protocols."""
    content = sdp_manager_path.read_text(encoding="utf-8")

    assert "zero_trust_runner.py" in content
    assert "verify_core_integrity.py" in content
    assert "MAX_PIVOT_CYCLES=3" in content
    assert "MAX_META_PIVOT=3" in content
    assert "cochem-audit" in content
    assert "[MISSING DATA]" in content
    assert "TolMaxG 1e-5" in content
    assert "CREST/ORCA GOAT" in content
    assert "defgrid1" in content
    assert "defgrid3" in content
    assert "PMBOK" in content
    assert "SWEBOK" in content
    assert "Work Breakdown Structure" in content or "WBS" in content
