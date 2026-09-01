"""Agent frontmatter, capability, sanitization, and structural integrity verification suite.

This script performs an exhaustive, production-grade audit of all 15 core CoChem
agent configuration files (*.agent.md). It validates YAML frontmatter AST validity,
mandatory tool capabilities (enable_write_tools, enable_mcp_tools), zero personal path
leakages, standard placeholder utilization (<USER_HOME>, <COCHEM_WORKSPACE>, <GDRIVE_ROOT>),
structural body completeness, and exact parity against sanitized source templates.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from pydantic import BaseModel, Field

# Attempt relative/package import or dynamic path resolution for cochem_base
try:
    from cochem_base.path_sanitization import (
        find_path_leaks,
        get_agent_templates_dir,
        get_agents_dir,
        sanitize_local_paths,
    )
except ImportError:
    # Resolve repository root and inject into sys.path
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from cochem_base.path_sanitization import (
        find_path_leaks,
        get_agent_templates_dir,
        get_agents_dir,
        sanitize_local_paths,
    )


EXPECTED_15_AGENTS: List[str] = [
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
]

REQUIRED_FRONTMATTER_KEYS: List[str] = [
    "name",
    "description",
    "argument-hint",
    "enable_write_tools",
    "enable_mcp_tools",
]

KNOWN_PLACEHOLDERS: List[str] = [
    "<USER_HOME>",
    "<COCHEM_WORKSPACE>",
    "<GDRIVE_ROOT>",
]

UNFINISHED_STUB_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r'^\s*(?:TODO|FIXME|TBD|XXX):', re.MULTILINE | re.IGNORECASE), "Unresolved TODO/FIXME task line"),
    (re.compile(r'<!--\s*(?:TODO|FIXME|TBD)\b', re.IGNORECASE), "Unfinished HTML comment stub"),
    (re.compile(r'^\s*\[(?:TODO|FIXME|TBD)\]', re.MULTILINE | re.IGNORECASE), "Unresolved square bracket stub"),
]


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


class FrontmatterDetail(BaseModel):
    is_valid: bool = False
    name: str = ""
    description: str = ""
    version: Optional[str] = None
    domain: Optional[str] = None
    routes_to: List[str] = Field(default_factory=list)
    missing_keys: List[str] = Field(default_factory=list)
    raw_keys: List[str] = Field(default_factory=list)
    parse_error: Optional[str] = None


class CapabilityDetail(BaseModel):
    enable_write_tools: bool = False
    enable_mcp_tools: bool = False
    enable_subagent_tools: Optional[bool] = None
    is_compliant: bool = False
    violations: List[str] = Field(default_factory=list)


class LeakScanDetail(BaseModel):
    leak_count: int = 0
    is_clean: bool = True
    detected_leaks: List[str] = Field(default_factory=list)
    placeholders_present: List[str] = Field(default_factory=list)


class BodyDetail(BaseModel):
    char_count: int = 0
    line_count: int = 0
    is_complete: bool = False
    stub_violations: List[str] = Field(default_factory=list)


class ParityDetail(BaseModel):
    compared: bool = False
    matches_template: bool = False
    message: str = ""


class AgentValidationResult(BaseModel):
    agent_file: str
    file_path: str
    exists: bool = False
    frontmatter: FrontmatterDetail = Field(default_factory=FrontmatterDetail)
    capabilities: CapabilityDetail = Field(default_factory=CapabilityDetail)
    sanitization: LeakScanDetail = Field(default_factory=LeakScanDetail)
    body: BodyDetail = Field(default_factory=BodyDetail)
    parity: ParityDetail = Field(default_factory=ParityDetail)
    overall_status: CheckStatus = CheckStatus.FAIL


class VerificationSummary(BaseModel):
    timestamp: str
    target_directory: str
    total_expected: int = 15
    total_found: int = 0
    total_passed: int = 0
    total_failed: int = 0
    all_passed: bool = False
    results: List[AgentValidationResult] = Field(default_factory=list)


def extract_frontmatter(content: str) -> Tuple[Optional[str], str]:
    """Extracts raw YAML frontmatter block and remaining body content from markdown."""
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", content, re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    return None, content


def validate_frontmatter_block(fm_text: Optional[str]) -> FrontmatterDetail:
    """Parses and validates the YAML frontmatter AST and mandatory keys."""
    detail = FrontmatterDetail()
    if fm_text is None:
        detail.is_valid = False
        detail.parse_error = "No frontmatter block found (missing '---' delimiters)."
        return detail

    try:
        parsed = yaml.safe_load(fm_text)
    except Exception as exc:
        detail.is_valid = False
        detail.parse_error = f"YAML syntax error: {exc}"
        return detail

    if not isinstance(parsed, dict):
        detail.is_valid = False
        detail.parse_error = f"Frontmatter did not parse into a key-value mapping (got {type(parsed).__name__})."
        return detail

    detail.raw_keys = list(parsed.keys())
    detail.name = str(parsed.get("name", ""))
    detail.description = str(parsed.get("description", ""))
    detail.version = str(parsed.get("version")) if "version" in parsed else None
    detail.domain = str(parsed.get("domain")) if "domain" in parsed else None

    routes = parsed.get("routes_to", [])
    if isinstance(routes, list):
        detail.routes_to = [str(r) for r in routes]
    elif isinstance(routes, str):
        detail.routes_to = [r.strip() for r in routes.split(",") if r.strip()]

    for req_key in REQUIRED_FRONTMATTER_KEYS:
        if req_key not in parsed:
            detail.missing_keys.append(req_key)

    detail.is_valid = (len(detail.missing_keys) == 0 and bool(detail.name) and bool(detail.description))
    return detail


def validate_capabilities(fm_text: Optional[str]) -> CapabilityDetail:
    """Verifies that mandatory tool capability flags are explicitly set to true."""
    detail = CapabilityDetail()
    if fm_text is None:
        detail.violations.append("Cannot evaluate capabilities: missing frontmatter.")
        detail.is_compliant = False
        return detail

    try:
        parsed = yaml.safe_load(fm_text)
    except Exception as exc:
        detail.violations.append(f"Cannot evaluate capabilities: YAML parse error ({exc}).")
        detail.is_compliant = False
        return detail

    if not isinstance(parsed, dict):
        detail.violations.append("Frontmatter is not a dictionary.")
        detail.is_compliant = False
        return detail

    enable_write = parsed.get("enable_write_tools")
    enable_mcp = parsed.get("enable_mcp_tools")
    enable_sub = parsed.get("enable_subagent_tools")

    detail.enable_write_tools = bool(enable_write is True)
    detail.enable_mcp_tools = bool(enable_mcp is True)
    if enable_sub is not None:
        detail.enable_subagent_tools = bool(enable_sub is True)

    if enable_write is not True:
        detail.violations.append(f"enable_write_tools must be true (got {enable_write!r})")

    if enable_mcp is not True:
        detail.violations.append(f"enable_mcp_tools must be true (got {enable_mcp!r})")

    detail.is_compliant = len(detail.violations) == 0
    return detail


def validate_sanitization(content: str) -> LeakScanDetail:
    """Scans content for personal path leakages and verifies placeholder presence."""
    detail = LeakScanDetail()
    leaks = find_path_leaks(content)
    detail.leak_count = len(leaks)
    detail.is_clean = (len(leaks) == 0)

    for line_num, placeholder, line_content in leaks:
        detail.detected_leaks.append(
            f"Line {line_num} [{placeholder}]: {line_content.strip()[:100]}"
        )

    for ph in KNOWN_PLACEHOLDERS:
        if ph in content:
            detail.placeholders_present.append(ph)

    return detail


def validate_body_integrity(body_text: str) -> BodyDetail:
    """Validates body completeness, line counts, and absence of stub/mock patterns."""
    detail = BodyDetail()
    detail.char_count = len(body_text)
    detail.line_count = len(body_text.splitlines())

    for pattern, label in UNFINISHED_STUB_PATTERNS:
        matches = pattern.findall(body_text)
        if matches:
            detail.stub_violations.append(f"{label}: found {len(matches)} occurrence(s)")

    detail.is_complete = (
        detail.char_count >= 200
        and detail.line_count >= 10
        and len(detail.stub_violations) == 0
    )
    return detail


def validate_template_parity(
    agent_filename: str, target_raw_content: str, source_dir: Optional[Path]
) -> ParityDetail:
    """Checks character-by-character parity with sanitized source configuration templates."""
    detail = ParityDetail()
    if source_dir is None or not source_dir.exists():
        detail.compared = False
        detail.matches_template = True
        detail.message = "Template comparison skipped (source directory not available)."
        return detail

    src_file = source_dir / agent_filename
    if not src_file.exists():
        detail.compared = True
        detail.matches_template = False
        detail.message = f"Source template {src_file.name} does not exist in template dir."
        return detail

    detail.compared = True
    try:
        src_raw = src_file.read_text(encoding="utf-8").replace("\r\n", "\n")
        tgt_norm = target_raw_content.replace("\r\n", "\n")
        src_sanitized = sanitize_local_paths(src_raw)

        if src_sanitized == tgt_norm:
            detail.matches_template = True
            detail.message = "100% exact match with sanitized template."
        else:
            detail.matches_template = False
            detail.message = f"Content mismatch: template ({len(src_sanitized)} chars) vs target ({len(tgt_norm)} chars)."
    except Exception as exc:
        detail.matches_template = False
        detail.message = f"Error reading or comparing template: {exc}"

    return detail


def verify_agent_file(
    file_path: Path, source_dir: Optional[Path] = None
) -> AgentValidationResult:
    """Runs the complete battery of frontmatter, capability, leak, and parity tests on a single agent file."""
    res = AgentValidationResult(
        agent_file=file_path.name,
        file_path=str(file_path.resolve()),
        exists=file_path.exists(),
    )

    if not file_path.exists():
        res.overall_status = CheckStatus.FAIL
        return res

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        res.frontmatter.parse_error = f"Failed to read file: {exc}"
        res.overall_status = CheckStatus.FAIL
        return res

    fm_text, body_text = extract_frontmatter(content)

    res.frontmatter = validate_frontmatter_block(fm_text)
    res.capabilities = validate_capabilities(fm_text)
    res.sanitization = validate_sanitization(content)
    res.body = validate_body_integrity(body_text)
    res.parity = validate_template_parity(file_path.name, content, source_dir)

    is_all_clean = (
        res.exists
        and res.frontmatter.is_valid
        and res.capabilities.is_compliant
        and res.sanitization.is_clean
        and res.body.is_complete
        and (not res.parity.compared or res.parity.matches_template)
    )

    res.overall_status = CheckStatus.PASS if is_all_clean else CheckStatus.FAIL
    return res


def run_verification_suite(
    target_dir: Optional[Path] = None,
    source_dir: Optional[Path] = None,
    verbose: bool = True,
) -> VerificationSummary:
    """Executes verification for all 15 core agents in target_dir."""
    t_dir = target_dir if target_dir is not None else get_agents_dir()
    s_dir = source_dir if source_dir is not None else get_agent_templates_dir()

    summary = VerificationSummary(
        timestamp=datetime.now(timezone.utc).isoformat(),
        target_directory=str(t_dir.resolve()),
        total_expected=len(EXPECTED_15_AGENTS),
    )

    for agent_fname in EXPECTED_15_AGENTS:
        agent_path = t_dir / agent_fname
        result = verify_agent_file(agent_path, source_dir=s_dir if s_dir.exists() else None)
        if result.exists:
            summary.total_found += 1
        if result.overall_status == CheckStatus.PASS:
            summary.total_passed += 1
        else:
            summary.total_failed += 1
        summary.results.append(result)

    summary.all_passed = (
        summary.total_passed == summary.total_expected
        and summary.total_found == summary.total_expected
    )

    if verbose:
        print_verification_report(summary)

    return summary


def print_verification_report(summary: VerificationSummary) -> None:
    """Prints formatted ASCII/Markdown tables matching the Reviewer 2 audit reports."""
    print("=" * 100)
    print(" CoChem-BASE: 15 Agent Frontmatter & Capability Verification Suite")
    print(f" Target Directory : {summary.target_directory}")
    print(f" Timestamp        : {summary.timestamp}")
    print(f" Status           : {'ALL PASS (15/15)' if summary.all_passed else 'VIOLATIONS DETECTED'}")
    print("=" * 100)
    print()
    print("| Agent File | YAML Valid | enable_write_tools | enable_mcp_tools | Leaks Found | Placeholders Present | Status |")
    print("|---|---|---|---|---|---|---|")

    for r in summary.results:
        yaml_valid = "Yes" if r.frontmatter.is_valid else "FAIL"
        w_tools = f"`{str(r.capabilities.enable_write_tools).lower()}`"
        m_tools = f"`{str(r.capabilities.enable_mcp_tools).lower()}`"
        leaks = str(r.sanitization.leak_count)
        placeholders = ", ".join(r.sanitization.placeholders_present) if r.sanitization.placeholders_present else "None"
        status_str = r.overall_status.value

        print(
            f"| `{r.agent_file}` | {yaml_valid} | {w_tools} | {m_tools} | {leaks} | {placeholders} | {status_str} |"
        )

    print()
    if not summary.all_passed:
        print("=" * 100)
        print(" DETAILED FAILURE BREAKDOWN")
        print("=" * 100)
        for r in summary.results:
            if r.overall_status != CheckStatus.PASS:
                print(f"\n[FAIL] Agent: {r.agent_file}")
                if not r.exists:
                    print("  - File does not exist on disk.")
                if r.frontmatter.parse_error:
                    print(f"  - Frontmatter Error: {r.frontmatter.parse_error}")
                if r.frontmatter.missing_keys:
                    print(f"  - Missing Frontmatter Keys: {r.frontmatter.missing_keys}")
                for violation in r.capabilities.violations:
                    print(f"  - Capability Violation: {violation}")
                for leak in r.sanitization.detected_leaks:
                    print(f"  - Leak Detected: {leak}")
                for stub in r.body.stub_violations:
                    print(f"  - Stub Violation: {stub}")
                if not r.body.is_complete:
                    print(f"  - Incomplete Body: {r.body.char_count} chars, {r.body.line_count} lines")
                if r.parity.compared and not r.parity.matches_template:
                    print(f"  - Template Parity Failure: {r.parity.message}")
        print()


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for agent verification."""
    parser = argparse.ArgumentParser(
        description="Verify frontmatter, capabilities, sanitization, and integrity of the 15 CoChem agents."
    )
    parser.add_argument(
        "--target-dir",
        type=str,
        default=None,
        help="Path to the directory containing .agent.md files (defaults to CoChem-BASE/.agents).",
    )
    parser.add_argument(
        "--source-dir",
        type=str,
        default=None,
        help="Path to the source template directory (defaults to ~/.gemini/config/agents).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full verification report as structured JSON.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress human-readable table output.",
    )

    args = parser.parse_args(argv)

    t_dir = Path(args.target_dir) if args.target_dir else None
    s_dir = Path(args.source_dir) if args.source_dir else None
    is_verbose = (not args.json) and (not args.quiet)

    report = run_verification_suite(target_dir=t_dir, source_dir=s_dir, verbose=is_verbose)

    if args.json:
        dump_fn = getattr(report, "model_dump", getattr(report, "dict", None))
        data = dump_fn() if dump_fn is not None else report.__dict__
        print(json.dumps(data, indent=2))

    return 0 if report.all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
