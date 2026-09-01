"""Physical Zero-Mock Test Suite for verify_15_agents.py.

Verifies that verify_15_agents.py executes correctly, parses YAML frontmatter AST,
checks mandatory agent capabilities, detects path leaks, validates body completeness,
and functions properly both as an imported library and as a CLI entry point.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import pytest

from cochem_base.path_sanitization import get_agents_dir

# Import verify_15_agents functions directly
sys.path.insert(0, str(get_agents_dir().parent))
reviewer_dir = get_agents_dir() / "teamwork_preview_reviewer_2"
sys.path.insert(0, str(reviewer_dir))

from verify_15_agents import (
    CheckStatus,
    FrontmatterDetail,
    CapabilityDetail,
    LeakScanDetail,
    BodyDetail,
    ParityDetail,
    AgentValidationResult,
    VerificationSummary,
    EXPECTED_15_AGENTS,
    REQUIRED_FRONTMATTER_KEYS,
    extract_frontmatter,
    validate_frontmatter_block,
    validate_capabilities,
    validate_sanitization,
    validate_body_integrity,
    validate_template_parity,
    verify_agent_file,
    run_verification_suite,
    main,
)


def test_expected_15_agents_list() -> None:
    """Verify that all 15 expected agent configuration filenames are defined."""
    assert len(EXPECTED_15_AGENTS) == 15
    for expected in [
        "0rchestrator.agent.md",
        "artist.agent.md",
        "cochem-audit.agent.md",
        "cochem-coder.agent.md",
        "cochem-debug.agent.md",
        "cochem-helper.agent.md",
        "cochem-improve.agent.md",
        "cochem-scribe.agent.md",
        "cochem-sdp_manager.agent.md",
        "cochem-tester.agent.md",
        "educator.agent.md",
        "researcher.agent.md",
        "teacher.agent.md",
        "ui.agent.md",
        "web_mcp.agent.md",
    ]:
        assert expected in EXPECTED_15_AGENTS


def test_required_frontmatter_keys() -> None:
    """Verify required frontmatter key constants."""
    for req in ["name", "description", "argument-hint", "enable_write_tools", "enable_mcp_tools"]:
        assert req in REQUIRED_FRONTMATTER_KEYS


def test_extract_frontmatter_valid() -> None:
    """Test extracting frontmatter from well-formed markdown."""
    sample = "---\nname: test\ndescription: A test\n---\n# Body Content\nHello world."
    fm, body = extract_frontmatter(sample)
    assert fm == "name: test\ndescription: A test"
    assert "# Body Content\nHello world." in body


def test_extract_frontmatter_missing() -> None:
    """Test extracting frontmatter when delimiters are absent."""
    sample = "# Just Body Content\nNo frontmatter here."
    fm, body = extract_frontmatter(sample)
    assert fm is None
    assert body == sample


def test_validate_frontmatter_block_valid() -> None:
    """Test frontmatter parser on a valid YAML block."""
    fm_text = (
        "name: test_agent\n"
        "description: Testing agent\n"
        "argument-hint: test hint\n"
        "version: 1.0.0\n"
        "domain: testing\n"
        "routes_to: [agent1, agent2]\n"
        "enable_write_tools: true\n"
        "enable_mcp_tools: true\n"
    )
    detail = validate_frontmatter_block(fm_text)
    assert detail.is_valid is True
    assert detail.name == "test_agent"
    assert detail.description == "Testing agent"
    assert detail.version == "1.0.0"
    assert detail.domain == "testing"
    assert detail.routes_to == ["agent1", "agent2"]
    assert len(detail.missing_keys) == 0
    assert detail.parse_error is None


def test_validate_frontmatter_block_missing_keys() -> None:
    """Test frontmatter parser with missing mandatory keys."""
    fm_text = "name: incomplete_agent\nversion: 1.0.0\n"
    detail = validate_frontmatter_block(fm_text)
    assert detail.is_valid is False
    assert "description" in detail.missing_keys
    assert "argument-hint" in detail.missing_keys


def test_validate_frontmatter_block_invalid_yaml() -> None:
    """Test frontmatter parser on invalid YAML syntax."""
    fm_text = "name: bad: yaml:\n  - [invalid"
    detail = validate_frontmatter_block(fm_text)
    assert detail.is_valid is False
    assert detail.parse_error is not None


def test_validate_capabilities_compliant() -> None:
    """Test capability validator with true flags."""
    fm_text = "enable_write_tools: true\nenable_mcp_tools: true\nenable_subagent_tools: true\n"
    detail = validate_capabilities(fm_text)
    assert detail.is_compliant is True
    assert detail.enable_write_tools is True
    assert detail.enable_mcp_tools is True
    assert detail.enable_subagent_tools is True
    assert len(detail.violations) == 0


def test_validate_capabilities_violations() -> None:
    """Test capability validator with false or missing flags."""
    fm_text = "enable_write_tools: false\nenable_mcp_tools: false\n"
    detail = validate_capabilities(fm_text)
    assert detail.is_compliant is False
    assert detail.enable_write_tools is False
    assert detail.enable_mcp_tools is False
    assert len(detail.violations) == 2


def test_validate_sanitization_clean_and_placeholders() -> None:
    """Test leak scanner on clean content with placeholders."""
    content = "Path to workspace: <COCHEM_WORKSPACE>\\GitHub-Repo\nHome is <USER_HOME>"
    detail = validate_sanitization(content)
    assert detail.is_clean is True
    assert detail.leak_count == 0
    assert "<COCHEM_WORKSPACE>" in detail.placeholders_present
    assert "<USER_HOME>" in detail.placeholders_present


def test_validate_body_integrity_valid() -> None:
    """Test body integrity check on substantive text."""
    body = "\n".join([f"Line {i}: Substantive documentation and protocol instructions." for i in range(25)])
    detail = validate_body_integrity(body)
    assert detail.is_complete is True
    assert detail.line_count == 25
    assert len(detail.stub_violations) == 0


def test_validate_body_integrity_stubs_detected() -> None:
    """Test body integrity check when stub markers are present."""
    body = "TODO: Finish this section later\n<!-- FIXME: Add more content -->\n"
    detail = validate_body_integrity(body)
    assert detail.is_complete is False
    assert len(detail.stub_violations) > 0


def test_verify_agent_file_real_artist(tmp_path: Path) -> None:
    """Test verify_agent_file on a synthesized valid agent file."""
    test_agent = tmp_path / "artist.agent.md"
    body_lines = "\n".join([f"Instruction line {i} for artist agent with detailed directives." for i in range(20)])
    test_agent.write_text(
        "---\n"
        "name: artist\n"
        "description: Visual media agent\n"
        "argument-hint: Prompt for visual assets\n"
        "enable_write_tools: true\n"
        "enable_mcp_tools: true\n"
        "---\n\n"
        f"# Artist Directives\n{body_lines}\nUsing <COCHEM_WORKSPACE> and <USER_HOME>.\n",
        encoding="utf-8",
    )
    result = verify_agent_file(test_agent)
    assert result.exists is True
    assert result.frontmatter.is_valid is True
    assert result.capabilities.is_compliant is True
    assert result.sanitization.is_clean is True
    assert result.body.is_complete is True
    assert result.overall_status == CheckStatus.PASS


def test_cli_execution_with_custom_target(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Test CLI execution using arguments pointing to a test directory."""
    for agent_name in EXPECTED_15_AGENTS:
        f = tmp_path / agent_name
        body_content = "\n".join([f"Valid rule line {i} for {agent_name}." for i in range(15)])
        f.write_text(
            "---\n"
            f"name: {agent_name.replace('.agent.md', '')}\n"
            "description: Core agent description\n"
            "argument-hint: Standard task input\n"
            "enable_write_tools: true\n"
            "enable_mcp_tools: true\n"
            "---\n\n"
            f"# {agent_name}\n{body_content}\nPlaceholder: <COCHEM_WORKSPACE>\n",
            encoding="utf-8",
        )

    exit_code = main(["--target-dir", str(tmp_path), "--quiet"])
    assert exit_code == 0
