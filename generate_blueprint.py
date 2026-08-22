"""Deterministic Two-Pass Blueprint Generator for CoChem Modules.

Crawls target repositories/directories to generate a structured markdown
checklist (Blueprint) for file-level audits, tracking, and compliance.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
from pathlib import Path
from typing import Optional, Sequence, Union

DEFAULT_EXCLUDES: tuple[str, ...] = (
    ".git",
    ".github",
    ".svn",
    ".hg",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    "htmlcov",
    ".tox",
    ".hypothesis",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    "*.log",
    "*.lock",
    "*.tmp",
    "*.swp",
    "*.bak",
    "artifacts",
    "swarm_state.json",
    ".trash",
    "*.egg-info",
    "dist",
    "build",
)


def match_exclude(
    path: Union[str, Path],
    excludes: Optional[Sequence[str]] = None,
    base_dir: Optional[Union[str, Path]] = None,
) -> bool:
    """Check if a path matches any exclude pattern.

    Args:
        path: Path or string to check.
        excludes: Sequence of glob/name exclude patterns. Defaults to DEFAULT_EXCLUDES.
        base_dir: Optional base directory to calculate relative path.

    Returns:
        True if the path should be excluded, False otherwise.
    """
    p = Path(path)
    patterns = DEFAULT_EXCLUDES if excludes is None else tuple(excludes)

    parts = p.parts
    posix_str = p.as_posix()
    name = p.name

    rel_str = None
    if base_dir is not None:
        try:
            rel_p = p.relative_to(base_dir)
            rel_str = rel_p.as_posix()
        except ValueError:
            rel_str = posix_str

    for pattern in patterns:
        clean_pat = pattern.rstrip("/\\")

        # 1. Check exact part name or wildcard in part
        if clean_pat in parts:
            return True

        for part in parts:
            if fnmatch.fnmatch(part, clean_pat):
                return True

        # 2. Match filename or full path
        if fnmatch.fnmatch(name, clean_pat):
            return True

        if fnmatch.fnmatch(posix_str, clean_pat):
            return True

        if rel_str is not None and fnmatch.fnmatch(rel_str, clean_pat):
            return True

        # 3. Pathlib match
        try:
            if p.match(pattern):
                return True
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            pass

    return False


def discover_files(
    repo_path: Union[str, Path],
    excludes: Optional[Sequence[str]] = None,
    include_extensions: Optional[Sequence[str]] = None,
) -> list[Path]:
    """Deterministically discover all auditable files within a repository directory.

    Args:
        repo_path: Root directory to crawl.
        excludes: Exclusion patterns to skip. Defaults to DEFAULT_EXCLUDES.
        include_extensions: Optional whitelist of file extensions (e.g. ['.py', '.md']).

    Returns:
        Sorted list of resolved Path objects.

    Raises:
        FileNotFoundError: If repo_path does not exist.
        NotADirectoryError: If repo_path is not a directory.
    """
    root = Path(repo_path).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Target repository path does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Target repository path is not a directory: {root}")

    normalized_exts = None
    if include_extensions:
        normalized_exts = {
            ext if ext.startswith(".") else f".{ext}"
            for ext in include_extensions
        }

    discovered: list[Path] = []

    for item in root.rglob("*"):
        if not item.is_file():
            continue

        if match_exclude(item, excludes=excludes, base_dir=root):
            continue

        if normalized_exts and item.suffix.lower() not in normalized_exts:
            continue

        try:
            if not os.access(item, os.R_OK):
                continue
        except OSError:
            continue

        discovered.append(item)

    # Sort deterministically by canonical POSIX path
    discovered.sort(key=lambda p: p.as_posix().lower())
    return discovered


def format_blueprint_entry(
    file_path: Path,
    relative_to: Optional[Union[str, Path]] = None,
    prefix: str = "- [ ] ",
) -> str:
    """Format a single blueprint checklist item.

    Args:
        file_path: The file Path object.
        relative_to: Optional base directory to format relative paths.
        prefix: Checkbox markdown prefix (default: '- [ ] ').

    Returns:
        Formatted markdown checklist line.
    """
    if relative_to is not None:
        try:
            target_str = str(file_path.relative_to(relative_to))
        except ValueError:
            target_str = str(file_path.resolve())
    else:
        target_str = str(file_path.resolve())

    return f"{prefix}{target_str}\n"


def generate_blueprint(
    repo_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    excludes: Optional[Sequence[str]] = None,
    include_extensions: Optional[Sequence[str]] = None,
    relative: bool = False,
    prefix: str = "- [ ] ",
) -> tuple[Path, int]:
    """Generate a markdown file blueprint for a target repository.

    Args:
        repo_path: Target directory to crawl.
        output_path: Destination path for the blueprint markdown file.
        excludes: Custom exclude patterns.
        include_extensions: Optional extension filter.
        relative: If True, record paths relative to repo_path; otherwise absolute.
        prefix: Checkbox prefix format.

    Returns:
        Tuple of (resolved output Path, count of discovered files).
    """
    root = Path(repo_path).resolve()
    files = discover_files(
        repo_path=root,
        excludes=excludes,
        include_extensions=include_extensions,
    )

    if output_path is None:
        module_name = root.name or "cochem-audit"
        out = root / f"{module_name}_File_Blueprint.md"
    else:
        out = Path(output_path).resolve()

    out.parent.mkdir(parents=True, exist_ok=True)

    rel_base = root if relative else None
    lines = [
        format_blueprint_entry(p, relative_to=rel_base, prefix=prefix)
        for p in files
    ]

    # Write strictly with LF line endings and UTF-8 encoding
    content = "".join(lines)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    return out, len(files)


def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments for the blueprint generator."""
    parser = argparse.ArgumentParser(
        description="Deterministic Two-Pass Blueprint Generator for CoChem Modules.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--repo-dir",
        "-r",
        type=str,
        default=os.getcwd(),
        help="Path to the target repository or module directory.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Destination path for the generated File Blueprint markdown.",
    )
    parser.add_argument(
        "--exclude",
        "-e",
        action="append",
        default=[],
        help="Additional exclude patterns (can specify multiple times).",
    )
    parser.add_argument(
        "--no-default-excludes",
        action="store_true",
        help="Disable built-in default exclusion patterns.",
    )
    parser.add_argument(
        "--include-ext",
        nargs="+",
        default=None,
        help="Filter discovery to specific file extensions (e.g. .py .md).",
    )
    parser.add_argument(
        "--relative",
        action="store_true",
        help="Output relative file paths instead of absolute paths.",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="- [ ] ",
        help="Markdown checklist prefix for each entry.",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress console output.",
    )

    return parser.parse_args(args)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point for the blueprint generator."""
    args = parse_args(argv)

    repo_dir = Path(args.repo_dir).resolve()
    if not repo_dir.exists():
        print(f"Error: Target repository directory does not exist: {repo_dir}")
        return 1
    if not repo_dir.is_dir():
        print(f"Error: Target repository path is not a directory: {repo_dir}")
        return 1

    if args.no_default_excludes:
        effective_excludes: list[str] = list(args.exclude)
    else:
        effective_excludes = list(DEFAULT_EXCLUDES) + list(args.exclude)

    try:
        blueprint_path, count = generate_blueprint(
            repo_path=repo_dir,
            output_path=args.output,
            excludes=effective_excludes,
            include_extensions=args.include_ext,
            relative=args.relative,
            prefix=args.prefix,
        )
        if not args.quiet:
            print(f"Discovered {count} file(s).")
            print(f"Blueprint saved to: {blueprint_path}")
        return 0
    except Exception as exc:
        print(f"Error generating blueprint: {exc}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
