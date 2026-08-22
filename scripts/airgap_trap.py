#!/usr/bin/env python3
"""Air-Gap Enforcement Trap: Defend the Tripartite Workspace Air-Gap in CI pipelines.

This script scans the repository or specified target directory to detect
restricted artifact types (.h5, .xyz, .gbw, .tmp, .log) or prohibited proprietary
binary / scratch dumps that must never leak into the static repository tier.

Enforcement Rules:
1. Zero-Mock, Real Implementation: Uses safe, physical directory / git scanning.
2. Blocked Extensions: .h5, .xyz, .gbw, .tmp, .log (case-insensitive matching).
3. Detection Response: Immediately outputs formatted violation logs and exits with Exit Code 1.
4. Clean Status: Exits with Exit Code 0 when no restricted artifacts are detected.
5. Scanning Strategy:
   - Primary: 'git ls-files -z --cached --others --exclude-standard' for null-byte safe git scanning.
   - Fallback / Direct: Recursive filesystem tree traversal with exclusions for .git, .venv, .trash.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import FrozenSet, List, Optional, Sequence, Set, Tuple

# Blocked extensions that violate the Tripartite Workspace Air-Gap
BLOCKED_EXTENSIONS: FrozenSet[str] = frozenset({
    ".h5",
    ".xyz",
    ".gbw",
    ".tmp",
    ".log",
})

# Directories excluded from filesystem scans by default
DEFAULT_EXCLUDED_DIRS: FrozenSet[str] = frozenset({
    ".git",
    ".venv",
    ".trash",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".agents",
})


@dataclass(frozen=True)
class AirgapViolation:
    """Represents a detected air-gap violation artifact."""

    file_path: Path
    relative_path: str
    extension: str
    reason: str


@dataclass
class AirgapScanResult:
    """Structured result of an air-gap repository scan."""

    repo_root: Path
    is_clean: bool
    violations: List[AirgapViolation] = field(default_factory=list)
    scanned_files_count: int = 0
    scan_method: str = "unknown"

    @property
    def violation_count(self) -> int:
        """Return the number of detected violations."""
        return len(self.violations)


def is_blocked_file(file_path: Path, blocked_extensions: Set[str]) -> Tuple[bool, str]:
    """Check whether a file matches any blocked extension (case-insensitively).

    Handles standard extensions, multi-part extensions (e.g. .h5.bak),
    case variations (.H5, .XYZ), and dotfiles (e.g. .tmp, .log).

    Args:
        file_path: The file path to check.
        blocked_extensions: Set of lowercased blocked extensions with leading dots (e.g. {'.h5', '.xyz'}).

    Returns:
        A tuple of (is_blocked, matched_extension).
    """
    name_lower = file_path.name.lower()
    if name_lower in blocked_extensions:
        return True, name_lower

    suffix = file_path.suffix.lower()
    if suffix in blocked_extensions:
        return True, suffix

    for s in file_path.suffixes:
        s_lower = s.lower()
        if s_lower in blocked_extensions:
            return True, s_lower

    # Check all dot-delimited segments to catch dotfiles like .tmp.bak or .xyz.old
    parts = name_lower.split(".")
    for part in parts[1:]:
        ext = f".{part}"
        if ext in blocked_extensions:
            return True, ext

    return False, ""


def scan_git_repository(
    repo_root: Path,
    blocked_exts: Set[str],
) -> Tuple[List[AirgapViolation], int]:
    """Scan tracked and untracked repository files using git ls-files -z.

    Args:
        repo_root: Absolute path to the git repository root.
        blocked_exts: Set of lowercased blocked extensions.

    Returns:
        A tuple of (list of AirgapViolation, total scanned files count).

    Raises:
        RuntimeError: If git command fails or is not applicable.
    """
    git_cmd = [
        "git",
        "-C",
        str(repo_root),
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
    ]

    try:
        proc = subprocess.run(
            git_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as exc:
        raise RuntimeError(f"Git scanning failed: {exc}") from exc

    raw_output = proc.stdout
    if not raw_output:
        return [], 0

    entries = raw_output.split(b"\x00")
    violations: List[AirgapViolation] = []
    scanned_count = 0

    for raw_entry in entries:
        if not raw_entry:
            continue
        try:
            rel_str = raw_entry.decode("utf-8")
        except UnicodeDecodeError:
            rel_str = raw_entry.decode("utf-8", errors="replace")

        full_path = repo_root / rel_str
        scanned_count += 1

        blocked, ext = is_blocked_file(full_path, blocked_exts)
        if blocked:
            violations.append(
                AirgapViolation(
                    file_path=full_path,
                    relative_path=rel_str,
                    extension=ext,
                    reason=f"Restricted dynamic artifact extension '{ext}' detected in static workspace repository",
                )
            )

    return violations, scanned_count


def scan_filesystem_tree(
    repo_root: Path,
    blocked_exts: Set[str],
    excluded_dirs: Set[str],
) -> Tuple[List[AirgapViolation], int]:
    """Scan directory tree recursively using pure-Python filesystem traversal.

    Args:
        repo_root: Root directory to scan.
        blocked_exts: Set of lowercased blocked extensions.
        excluded_dirs: Set of directory names to skip (e.g. {'.git', '.venv'}).

    Returns:
        A tuple of (list of AirgapViolation, total scanned files count).
    """
    violations: List[AirgapViolation] = []
    scanned_count = 0

    for root, dirs, files in os.walk(repo_root, topdown=True):
        # Prune excluded directories in-place to avoid traversing them
        dirs[:] = [d for d in dirs if d not in excluded_dirs]

        root_path = Path(root)

        for filename in files:
            full_path = root_path / filename
            scanned_count += 1

            blocked, ext = is_blocked_file(full_path, blocked_exts)
            if blocked:
                try:
                    rel_str = str(full_path.relative_to(repo_root))
                except ValueError:
                    rel_str = str(full_path)

                violations.append(
                    AirgapViolation(
                        file_path=full_path,
                        relative_path=rel_str,
                        extension=ext,
                        reason=f"Restricted dynamic artifact extension '{ext}' detected in static workspace repository",
                    )
                )

    return violations, scanned_count


def scan_repository(
    repo_root: str | Path = ".",
    blocked_extensions: Optional[Sequence[str] | Set[str]] = None,
    excluded_dirs: Optional[Sequence[str] | Set[str]] = None,
    use_git: bool = True,
) -> AirgapScanResult:
    """Scan a repository/directory for air-gap violating artifact types.

    Args:
        repo_root: Path to the repository or directory to scan.
        blocked_extensions: Optional custom blocked extensions. Defaults to BLOCKED_EXTENSIONS.
        excluded_dirs: Optional custom excluded directory names. Defaults to DEFAULT_EXCLUDED_DIRS.
        use_git: If True, attempts 'git ls-files -z' first, falling back to filesystem tree scan.

    Returns:
        AirgapScanResult containing clean status, violations list, and file counts.
    """
    root = Path(repo_root).resolve()

    if not root.exists():
        raise FileNotFoundError(f"Repository root path does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Repository root path is not a directory: {root}")

    if blocked_extensions is None:
        blocked_set: Set[str] = set(BLOCKED_EXTENSIONS)
    else:
        blocked_set = {
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in blocked_extensions
        }

    if excluded_dirs is None:
        excluded_set: Set[str] = set(DEFAULT_EXCLUDED_DIRS)
    else:
        excluded_set = set(excluded_dirs)

    violations: List[AirgapViolation] = []
    scanned_count = 0
    scan_method = "filesystem"

    is_git_repo = (root / ".git").exists()

    if use_git and is_git_repo:
        try:
            violations, scanned_count = scan_git_repository(root, blocked_set)
            scan_method = "git_ls_files"
        except Exception:
            violations, scanned_count = scan_filesystem_tree(root, blocked_set, excluded_set)
            scan_method = "filesystem_fallback"
    else:
        violations, scanned_count = scan_filesystem_tree(root, blocked_set, excluded_set)
        scan_method = "filesystem"

    is_clean = len(violations) == 0

    return AirgapScanResult(
        repo_root=root,
        is_clean=is_clean,
        violations=violations,
        scanned_files_count=scanned_count,
        scan_method=scan_method,
    )


def format_violation_report(result: AirgapScanResult) -> str:
    """Format an air-gap scan result into human-readable console output.

    Args:
        result: The AirgapScanResult from scan_repository.

    Returns:
        Formatted multi-line report string.
    """
    lines: List[str] = []
    header = "=" * 78
    lines.append(header)
    lines.append(" [AIR-GAP ENFORCEMENT TRAP] Tripartite Workspace Security Guard")
    lines.append(header)
    lines.append(f" Target Path  : {result.repo_root}")
    lines.append(f" Scan Method  : {result.scan_method}")
    lines.append(f" Files Checked: {result.scanned_files_count}")

    if result.is_clean:
        lines.append(" Status       : [PASSED] CLEAN (0 violations)")
        lines.append(" Description  : No restricted artifacts (.h5, .xyz, .gbw, .tmp, .log) detected.")
        lines.append(header)
    else:
        lines.append(f" Status       : [FAILED] VIOLATIONS DETECTED ({result.violation_count} files)")
        lines.append(" Description  : Prohibited dynamic artifacts found in static repository tier.")
        lines.append("-" * 78)
        lines.append(" DETECTED VIOLATIONS:")
        for idx, v in enumerate(result.violations, 1):
            lines.append(f"   [{idx}] Extension : {v.extension}")
            lines.append(f"       File Path : {v.relative_path}")
            lines.append(f"       Reason    : {v.reason}")
        lines.append("-" * 78)
        lines.append(" REMEDIATION REQUIRED:")
        lines.append("   Dynamic artifacts (.h5, .xyz, .gbw, .tmp, .log) must strictly reside")
        lines.append("   in the dynamic data tier (~/CoChem_Artifacts or dynamic scratch).")
        lines.append("   Delete or move these files out of the static CoChem-BASE repository.")
        lines.append(header)

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser for airgap_trap.py."""
    parser = argparse.ArgumentParser(
        prog="airgap_trap",
        description="Air-Gap Enforcement Trap: Defend the Tripartite Workspace Air-Gap in CI pipelines.",
    )
    parser.add_argument(
        "--repo-root",
        "-r",
        dest="repo_root",
        type=str,
        default=".",
        help="Path to the repository or directory root to scan (default: current working directory).",
    )
    parser.add_argument(
        "--no-git",
        dest="no_git",
        action="store_true",
        default=False,
        help="Force pure-Python filesystem traversal instead of git ls-files.",
    )
    parser.add_argument(
        "--add-extension",
        dest="add_extensions",
        action="append",
        default=[],
        help="Additional blocked file extension to enforce (can be specified multiple times).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main CLI entry point for Air-Gap Enforcement Trap.

    Args:
        argv: Optional sequence of CLI argument strings.

    Returns:
        0 if clean, 1 if violations are detected or on error.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    blocked_exts = set(BLOCKED_EXTENSIONS)
    for ext in args.add_extensions:
        ext_clean = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        blocked_exts.add(ext_clean)

    use_git = not args.no_git

    try:
        result = scan_repository(
            repo_root=args.repo_root,
            blocked_extensions=blocked_exts,
            use_git=use_git,
        )
    except Exception as exc:
        print(f"[AIR-GAP ENFORCEMENT TRAP ERROR] Scan failed: {exc}", file=sys.stderr)
        return 1

    report = format_violation_report(result)
    if result.is_clean:
        print(report, file=sys.stdout)
        return 0
    else:
        print(report, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
