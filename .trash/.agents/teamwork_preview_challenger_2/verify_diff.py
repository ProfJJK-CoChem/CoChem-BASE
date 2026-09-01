#!/usr/bin/env python3
"""Path sanitization and string substitution verification script.

This script verifies that canonical `.agent.md` configuration files
in the target repository (`.agents/`) correctly mirror their source templates
(`config/agents/`) under bidirectional variable expansion and path sanitization.

It provides comprehensive unified diff analysis, placeholder leak scanning,
and detailed compliance reporting.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# Ensure repository root is on sys.path for cochem_base imports
CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from cochem_base.path_sanitization import (
        find_path_leaks,
        get_agent_templates_dir,
        get_agents_dir,
        placeholder_values,
        sanitize_local_paths,
    )
except ImportError:
    # Graceful fallback implementations if cochem_base is executed outside repository context
    def get_agents_dir(base_root: Optional[Path] = None) -> Path:
        root = base_root if base_root is not None else REPO_ROOT
        return (root / ".agents").resolve()

    def get_agent_templates_dir() -> Path:
        return (Path.home() / ".gemini" / "config" / "agents").resolve()

    def placeholder_values(
        custom_mappings: Optional[Dict[str, str | Path]] = None,
    ) -> Dict[str, Path]:
        workspace = REPO_ROOT.parent
        shared_root = workspace.parent
        placeholders: Dict[str, Path] = {
            "<USER_HOME>": Path.home().resolve(),
            "<COCHEM_WORKSPACE>": workspace.resolve(),
            "<GDRIVE_ROOT>": shared_root.resolve(),
        }
        if custom_mappings:
            for k, v in custom_mappings.items():
                placeholders[k] = Path(v).resolve() if not isinstance(v, Path) else v.resolve()
        return placeholders

    def sanitize_local_paths(
        content: str, custom_placeholders: Optional[Dict[str, Path]] = None
    ) -> str:
        sanitized = content
        placeholders = (
            custom_placeholders if custom_placeholders is not None else placeholder_values()
        )
        sorted_placeholders = sorted(
            placeholders.items(), key=lambda item: len(str(item[1])), reverse=True
        )
        for placeholder, path in sorted_placeholders:
            sanitized = sanitized.replace(str(path), placeholder)
            sanitized = sanitized.replace(path.as_posix(), placeholder)
        return sanitized

    def find_path_leaks(
        content: str, custom_placeholders: Optional[Dict[str, Path]] = None
    ) -> List[Tuple[int, str, str]]:
        leaks: List[Tuple[int, str, str]] = []
        placeholders = (
            custom_placeholders if custom_placeholders is not None else placeholder_values()
        )
        for line_idx, line in enumerate(content.splitlines(), start=1):
            for token, p in placeholders.items():
                if str(p).lower() in line.lower() or p.as_posix().lower() in line.lower():
                    leaks.append((line_idx, token, line))
        return leaks

    def is_sanitized(content: str, custom_placeholders: Optional[Dict[str, Path]] = None) -> bool:
        return len(find_path_leaks(content, custom_placeholders)) == 0


CANONICAL_AGENT_FILES: Tuple[str, ...] = (
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
)


def expand_target_placeholders(
    content: str,
    placeholder_map: Optional[Dict[str, str]] = None,
) -> str:
    """Replaces placeholder tokens in target content with concrete local paths.

    Args:
        content: Target string content containing placeholder tokens.
        placeholder_map: Mapping of placeholder tokens (e.g. '<USER_HOME>') to path strings.

    Returns:
        String with placeholders substituted by concrete paths.
    """
    if placeholder_map is None:
        values = placeholder_values()
        placeholder_map = {k: str(v) for k, v in values.items()}

    expanded = content
    # Order replacements by descending placeholder length to avoid partial collisions
    sorted_items = sorted(placeholder_map.items(), key=lambda item: len(item[0]), reverse=True)
    for placeholder, path_str in sorted_items:
        expanded = expanded.replace(placeholder, path_str)
    return expanded


def compute_unified_diff(
    expected_text: str,
    actual_text: str,
    from_file: str = "expected",
    to_file: str = "actual",
) -> List[str]:
    """Generates a list of unified diff lines between expected and actual text.

    Args:
        expected_text: Source/baseline text.
        actual_text: Target/transformed text.
        from_file: Label for expected source in diff header.
        to_file: Label for actual target in diff header.

    Returns:
        List of formatted unified diff lines.
    """
    expected_lines = expected_text.splitlines(keepends=True)
    actual_lines = actual_text.splitlines(keepends=True)
    return list(
        difflib.unified_diff(
            expected_lines,
            actual_lines,
            fromfile=from_file,
            tofile=to_file,
            lineterm="",
        )
    )


def verify_file_diff(
    source_path: Path,
    target_path: Path,
    mode: str = "expand_target",
    placeholder_map: Optional[Dict[str, str]] = None,
) -> Tuple[bool, List[str], List[Tuple[int, str, str]]]:
    """Verifies a single agent file between source template and target repository.

    Args:
        source_path: Path to canonical source template file.
        target_path: Path to target repository file.
        mode: Comparison mode ('expand_target', 'sanitize_source', 'raw').
        placeholder_map: Dictionary mapping token names to string paths.

    Returns:
        A tuple of (is_match, diff_lines, leak_list).
    """
    if not source_path.is_file():
        return False, [f"ERROR: Source file not found: {source_path}"], []
    if not target_path.is_file():
        return False, [f"ERROR: Target file not found: {target_path}"], []

    source_content = source_path.read_text(encoding="utf-8")
    target_content = target_path.read_text(encoding="utf-8")

    custom_placeholders = (
        {k: Path(v) for k, v in placeholder_map.items()} if placeholder_map is not None else None
    )
    leaks = find_path_leaks(target_content, custom_placeholders=custom_placeholders)

    if mode == "expand_target":
        expected = source_content
        actual = expand_target_placeholders(target_content, placeholder_map)
        from_label = f"expected/{source_path.name}"
        to_label = f"actual_expanded/{target_path.name}"
    elif mode == "sanitize_source":
        expected = sanitize_local_paths(source_content, custom_placeholders=custom_placeholders)
        actual = target_content
        from_label = f"expected_sanitized/{source_path.name}"
        to_label = f"actual/{target_path.name}"
    elif mode == "raw":
        expected = source_content
        actual = target_content
        from_label = f"expected/{source_path.name}"
        to_label = f"actual/{target_path.name}"
    else:
        raise ValueError(f"Unknown verification mode: {mode}")

    is_match = expected == actual
    diff_lines: List[str] = []
    if not is_match:
        diff_lines = compute_unified_diff(expected, actual, from_label, to_label)

    return is_match, diff_lines, leaks


def run_verification(
    source_dir: Path,
    target_dir: Path,
    agent_files: Optional[Sequence[str]] = None,
    mode: str = "expand_target",
    placeholder_map: Optional[Dict[str, str]] = None,
    verbose: bool = False,
) -> Tuple[int, int, Dict[str, Tuple[bool, List[str], List[Tuple[int, str, str]]]]]:
    """Runs verification across all target agent files.

    Args:
        source_dir: Directory containing source template files.
        target_dir: Directory containing target repository agent files.
        agent_files: Optional custom list of agent filenames to check.
        mode: Verification mode ('expand_target', 'sanitize_source', 'raw').
        placeholder_map: Optional custom mapping of placeholder tokens to paths.
        verbose: If True, produces additional diagnostic logs.

    Returns:
        Tuple of (matches_count, mismatches_count, detailed_results_dict).
    """
    if agent_files is None:
        agent_files = CANONICAL_AGENT_FILES

    if placeholder_map is None:
        raw_values = placeholder_values()
        placeholder_map = {k: str(v) for k, v in raw_values.items()}

    matches_count = 0
    mismatches_count = 0
    results: Dict[str, Tuple[bool, List[str], List[Tuple[int, str, str]]]] = {}

    for filename in agent_files:
        src_file = source_dir / filename
        tgt_file = target_dir / filename

        is_match, diff_lines, leaks = verify_file_diff(
            src_file,
            tgt_file,
            mode=mode,
            placeholder_map=placeholder_map,
        )

        results[filename] = (is_match, diff_lines, leaks)
        if is_match:
            matches_count += 1
        else:
            mismatches_count += 1

    return matches_count, mismatches_count, results


def format_report(
    source_dir: Path,
    target_dir: Path,
    placeholder_map: Dict[str, str],
    matches_count: int,
    mismatches_count: int,
    results: Dict[str, Tuple[bool, List[str], List[Tuple[int, str, str]]]],
    mode: str,
) -> str:
    """Formats the verification output as a clean, human-readable report.

    Args:
        source_dir: Source templates directory.
        target_dir: Target repository directory.
        placeholder_map: Active token replacement mappings.
        matches_count: Count of matching files.
        mismatches_count: Count of mismatching or missing files.
        results: Detailed dictionary of per-file results.
        mode: Verification mode string.

    Returns:
        Formatted multi-line report string.
    """
    lines: List[str] = [
        "=== EMPIRICAL DIFF VERIFICATION REPORT ===",
        f"Source Directory: {source_dir}",
        f"Target Directory: {target_dir}",
        f"Verification Mode: {mode}",
        "Replacements applied:",
    ]
    for token, val in placeholder_map.items():
        lines.append(f"  '{token}' -> '{val}'")
    lines.append("-" * 60)

    for filename, (is_match, diff_lines, leaks) in results.items():
        if is_match:
            lines.append(f"[MATCH] {filename}: EXACT MATCH (0 diff lines)")
        else:
            lines.append(f"[FAIL] {filename}: MISMATCH DETECTED!")
            if diff_lines:
                lines.append("Diff output:")
                lines.extend(diff_lines)

        if leaks:
            lines.append(f"  [WARNING] Residual path leaks detected in {filename}:")
            for line_no, token, line_snippet in leaks:
                lines.append(f"    L{line_no} [{token}]: {line_snippet.strip()}")

        lines.append("-" * 60)

    total = matches_count + mismatches_count
    lines.append(f"Summary: {matches_count} / {total} files matched exactly.")

    if mismatches_count == 0:
        lines.append("============================================================")
        lines.append("VERDICT: APPROVE - All agent configuration files verified compliant.")
    else:
        lines.append("============================================================")
        lines.append(
            "VERDICT: REJECT - Discrepancies found between source templates and target agent files."
        )

    return "\n".join(lines)


def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parses command-line arguments.

    Args:
        args: Optional list of argument strings.

    Returns:
        Parsed Namespace object.
    """
    parser = argparse.ArgumentParser(
        description="Verify path sanitization and string substitution across agent config files."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Path to source agent templates directory (defaults to config/agents).",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Path to target agent repository directory (defaults to .agents).",
    )
    parser.add_argument(
        "--mode",
        choices=["expand_target", "sanitize_source", "raw"],
        default="expand_target",
        help="Verification mode: 'expand_target' (default), 'sanitize_source', or 'raw'.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write formatted report output.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output logging.",
    )
    return parser.parse_args(args)


def main(args: Optional[Sequence[str]] = None) -> int:
    """CLI entrypoint for verify_diff."""
    parsed = parse_args(args)

    source_dir = parsed.source.resolve() if parsed.source else get_agent_templates_dir()
    target_dir = parsed.target.resolve() if parsed.target else get_agents_dir()

    raw_placeholders = placeholder_values()
    placeholder_map = {k: str(v) for k, v in raw_placeholders.items()}

    matches, mismatches, results = run_verification(
        source_dir=source_dir,
        target_dir=target_dir,
        mode=parsed.mode,
        placeholder_map=placeholder_map,
        verbose=parsed.verbose,
    )

    report_text = format_report(
        source_dir=source_dir,
        target_dir=target_dir,
        placeholder_map=placeholder_map,
        matches_count=matches,
        mismatches_count=mismatches,
        results=results,
        mode=parsed.mode,
    )

    print(report_text)

    if parsed.output:
        parsed.output.parent.mkdir(parents=True, exist_ok=True)
        parsed.output.write_text(report_text, encoding="utf-8")
        if parsed.verbose:
            print(f"Report written to: {parsed.output}")

    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
