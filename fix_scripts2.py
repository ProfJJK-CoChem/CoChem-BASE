"""
fix_scripts2.py - Comprehensive tool for auditing, sanitizing, normalizing, and refactoring
script paths, malformed artifact strings, backslash separators, and swarm state updater scripts
across Python codebases.

Features:
- Detects and repairs malformed artifact path string joins (e.g., str(Path(__file__).resolve().parent\\\\foo.py")).
- Normalizes Windows backslashes inside Path division operands (e.g., parent / "tests\\sub\\test.py" -> parent / "tests/sub/test.py").
- Converts legacy os.path.join(Path(__file__).resolve().parent, ...) or os.path.join(os.path.dirname(__file__), ...) into Path expressions.
- Detects and repairs malformed nested Path expressions (e.g., Path(r"(Path(__file__)...)")).
- Sanitizes hardcoded absolute repository paths (e.g., D:\\__CoChem\\... or C:\\...) into dynamic Path(__file__).resolve().parent paths.
- Standardizes swarm state file resolution across updater and test scripts.
- Safely inserts `from pathlib import Path` after module docstrings (including raw/unicode prefixes), shebangs, and `__future__` imports.
- AST syntax validation before and after transformation to prevent code corruption.
- Configurable dry-run, backup creation (.bak), file exclusions, glob patterns, and directory scanning.
- Structured dataclass reporting and argparse CLI entrypoint.
"""

from __future__ import annotations

import argparse
import ast
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

logger = logging.getLogger("fix_scripts2")

# Standard directories to exclude from scanning
DEFAULT_EXCLUDE_DIRS: Tuple[str, ...] = (
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    "scratch",
    ".tox",
    "build",
    "dist",
    ".egg-info",
)

# Common docstring prefixes in Python
DOCSTRING_PREFIXES: Tuple[str, ...] = (
    '"""', "'''",
    'r"""', "r'''",
    'u"""', "u'''",
    'f"""', "f'''",
    'b"""', "b'''",
    'R"""', "R'''",
    'U"""', "U'''",
    'F"""', "F'''",
    'B"""', "B'''",
)

# Regex pattern for malformed artifact string with backslashes on parent resolution
ARTIFACT_BACKSLASH_PATTERN = re.compile(
    r'str\(Path\(__file__\)\.resolve\(\)\.parent(?:\\\\|\\)+([^"\'\)]+?)["\']\)'
)

# Regex pattern for backslashes within Path / "..." string literals, supporting string prefixes
PATH_SLASH_OPERAND_BACKSLASH_PATTERN = re.compile(
    r'(\bPath\([^)]+\)(?:\.resolve\(\))?(?:\.parent)*\s*/\s*)([rRuUbB]?)(["\'])(.*?)\3'
)

# Regex patterns for os.path.join with Path or dirname/abspath constructs
OS_PATH_JOIN_PARENT_PATTERN = re.compile(
    r'os\.path\.join\(\s*Path\(__file__\)(?:\.resolve\(\))?\.parent\s*,\s*([rRuUbB]?["\'][^"\']+["\'])\s*\)'
)

OS_PATH_JOIN_DIRNAME_PATTERN = re.compile(
    r'os\.path\.join\(\s*(?:os\.path\.dirname\(\s*(?:os\.path\.abspath\()?\s*__file__\s*\)?\s*\)|os\.path\.abspath\(\s*os\.path\.dirname\(\s*__file__\s*\)\s*\))\s*,\s*([rRuUbB]?["\'][^"\']+["\'])\s*\)'
)

# Common regex patterns for malformed or nested Path constructs
NESTED_PATH_PATTERN = re.compile(
    r'Path\(r?["\']\(Path\(__file__\)\.resolve\(\)\.parent\s*/\s*\\?["\']([^"\'\\]+)\\?["\']\s*\)["\']\)'
)

GENERAL_NESTED_PATH_PATTERN = re.compile(
    r'Path\(r?["\']\((Path\(.*?\))\)["\']\)'
)

REDUNDANT_STR_PATH_PATTERN = re.compile(
    r'Path\(\s*str\(\s*(Path\(.*?\))\s*\)\s*\)'
)

HARDCODED_COCHEM_BASE_PATTERN = re.compile(
    r'r?["\'](?:[a-zA-Z]:)?[\\/]+(?:__CoChem|CoChem)[\\/]+(?:GitHub-Repo[\\/]+)?(?:CoChem-BASE)[\\/]+([^"\']+)["\']'
)

SWARM_STATE_STANDALONE_PATTERN = re.compile(
    r'(\b(?:state_file|swarm_state_file|STATE_FILE|swarm_state|state_path)\s*=\s*)Path\(["\']swarm_state\.json["\']\)'
)


@dataclass
class FileFixResult:
    """Result of a script path fix attempt on a single file."""

    path: Path
    modified: bool = False
    changes_count: int = 0
    skipped: bool = False
    reason: Optional[str] = None
    error: Optional[str] = None


@dataclass
class RepoFixSummary:
    """Summary of script fixes across an entire repository or directory."""

    root_dir: Path
    total_found: int = 0
    scanned: int = 0
    modified: int = 0
    skipped: int = 0
    errors: int = 0
    results: List[FileFixResult] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return self.errors > 0

    def format_report(self) -> str:
        """Format a human-readable summary of the fix operation."""
        lines = [
            "=" * 60,
            f"Fix Scripts 2 Summary for: {self.root_dir}",
            "=" * 60,
            f"Total Python files found: {self.total_found}",
            f"Files scanned:            {self.scanned}",
            f"Files modified:           {self.modified}",
            f"Files skipped:            {self.skipped}",
            f"Errors encountered:       {self.errors}",
            "-" * 60,
        ]
        if self.modified > 0:
            lines.append("Modified files:")
            for res in self.results:
                if res.modified:
                    lines.append(f"  - {res.path} ({res.changes_count} changes)")
        if self.errors > 0:
            lines.append("Errors:")
            for res in self.results:
                if res.error:
                    lines.append(f"  - {res.path}: {res.error}")
        lines.append("=" * 60)
        return "\n".join(lines)


def validate_python_syntax(source_code: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that the provided source code parses as valid Python AST.

    Returns:
        (True, None) if syntax is valid, or (False, error_message) on SyntaxError / ValueError.
    """
    try:
        ast.parse(source_code)
        return True, None
    except (SyntaxError, ValueError) as e:
        lineno = getattr(e, "lineno", 1)
        msg = getattr(e, "msg", str(e))
        return False, f"Line {lineno}: {msg}"


def has_pathlib_import(content: str) -> bool:
    """Check if 'pathlib' or 'Path' is imported in the source code."""
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "pathlib" or alias.name.startswith("pathlib."):
                        return True
            elif isinstance(node, ast.ImportFrom):
                if node.module == "pathlib":
                    for alias in node.names:
                        if alias.name in ("Path", "*"):
                            return True
        return False
    except (SyntaxError, ValueError):
        return bool(
            re.search(
                r"^\s*(?:from\s+pathlib\s+import\s+.*(?:\bPath\b|\*)|import\s+pathlib\b)",
                content,
                re.MULTILINE,
            )
        )


def add_pathlib_import_to_content(content: str) -> str:
    """
    Safely insert 'from pathlib import Path' into source code after module docstrings,
    shebangs, and __future__ imports.
    """
    if has_pathlib_import(content):
        return content

    lines = content.splitlines(keepends=True)
    if not lines:
        return "from pathlib import Path\n"

    insert_idx = 0
    in_docstring = False
    docstring_delimiter = None
    seen_docstring = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Handle shebang, encoding comments, or blank lines before docstring
        if not in_docstring and not seen_docstring and (stripped.startswith("#") or not stripped):
            insert_idx = i + 1
            continue

        # Handle file-level docstring
        if not in_docstring and not seen_docstring:
            matched_prefix = None
            for pfx in DOCSTRING_PREFIXES:
                if stripped.startswith(pfx):
                    matched_prefix = pfx
                    break

            if matched_prefix:
                docstring_delimiter = '"""' if '"""' in matched_prefix else "'''"
                content_after_pfx = stripped[len(matched_prefix):]
                if docstring_delimiter in content_after_pfx:
                    # Single-line docstring
                    seen_docstring = True
                    insert_idx = i + 1
                    continue
                else:
                    in_docstring = True
                    continue
        elif in_docstring:
            if docstring_delimiter and docstring_delimiter in stripped:
                in_docstring = False
                seen_docstring = True
                insert_idx = i + 1
            continue

        # Skip __future__ imports
        if stripped.startswith("from __future__ import"):
            insert_idx = i + 1
            continue

        # Stop at the first real code or import
        break

    lines.insert(insert_idx, "from pathlib import Path\n")
    return "".join(lines)


def fix_artifact_backslash_strings(content: str) -> Tuple[str, int]:
    """
    Fix malformed artifact strings with backslashes on parent resolution, e.g.:
    str(Path(__file__).resolve().parent\\\\tests\\test_signin.py")
    -> str(Path(__file__).resolve().parent / "tests/test_signin.py")
    """
    def _replace_artifact(match: re.Match) -> str:
        raw_sub = match.group(1).replace("\\\\", "/").replace("\\", "/").lstrip("/")
        return f'str(Path(__file__).resolve().parent / "{raw_sub}")'

    new_content, count = ARTIFACT_BACKSLASH_PATTERN.subn(_replace_artifact, content)
    return new_content, count


def fix_path_slash_operands(content: str) -> Tuple[str, int]:
    """
    Normalize Windows backslashes inside Path division operands, e.g.:
    Path(__file__).resolve().parent / "tests\\sub\\test_06.py"
    -> Path(__file__).resolve().parent / "tests/sub/test_06.py"
    """
    changes = 0

    def _replace_slash_operand(match: re.Match) -> str:
        nonlocal changes
        prefix = match.group(1)
        str_pfx = match.group(2)
        quote = match.group(3)
        inner = match.group(4)
        if "\\" in inner:
            changes += 1
            normalized = inner.replace("\\\\", "/").replace("\\", "/")
            return f"{prefix}{str_pfx}{quote}{normalized}{quote}"
        return match.group(0)

    new_content = PATH_SLASH_OPERAND_BACKSLASH_PATTERN.sub(_replace_slash_operand, content)
    return new_content, changes


def fix_os_path_joins(content: str) -> Tuple[str, int]:
    """
    Convert legacy os.path.join calls to Path / syntax:
    os.path.join(Path(__file__).resolve().parent, "data/file.txt")
    -> Path(__file__).resolve().parent / "data/file.txt"
    """
    changes = 0

    def _replace_join(match: re.Match) -> str:
        subpath = match.group(1).replace("\\\\", "/").replace("\\", "/")
        return f"Path(__file__).resolve().parent / {subpath}"

    new_content, c1 = OS_PATH_JOIN_PARENT_PATTERN.subn(_replace_join, content)
    changes += c1

    new_content, c2 = OS_PATH_JOIN_DIRNAME_PATTERN.subn(_replace_join, new_content)
    changes += c2

    return new_content, changes


def fix_nested_path_constructs(content: str) -> Tuple[str, int]:
    """
    Clean up malformed nested or stringified Path calls, e.g.:
    Path(r"(Path(__file__).resolve().parent / "swarm_state.json")")
    -> Path(__file__).resolve().parent / "swarm_state.json"
    """
    changes = 0

    def _replace_nested(match: re.Match) -> str:
        filename = match.group(1).replace("\\\\", "/").replace("\\", "/").lstrip("/")
        return f'Path(__file__).resolve().parent / "{filename}"'

    new_content, count1 = NESTED_PATH_PATTERN.subn(_replace_nested, content)
    changes += count1

    new_content, count2 = GENERAL_NESTED_PATH_PATTERN.subn(r"\1", new_content)
    changes += count2

    new_content, count3 = REDUNDANT_STR_PATH_PATTERN.subn(r"\1", new_content)
    changes += count3

    return new_content, changes


def fix_hardcoded_cochem_paths(
    content: str,
    base_expr: str = "Path(__file__).resolve().parent",
) -> Tuple[str, int]:
    """
    Replace hardcoded absolute repository paths (e.g. D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\...)
    with dynamic Path resolution.
    """
    def _replace_hardcoded(match: re.Match) -> str:
        rel_subpath = match.group(1).replace("\\\\", "/").replace("\\", "/").lstrip("/")
        return f'str({base_expr} / "{rel_subpath}")'

    new_content, count = HARDCODED_COCHEM_BASE_PATTERN.subn(_replace_hardcoded, content)
    return new_content, count


def fix_swarm_state_paths(content: str) -> Tuple[str, int]:
    """
    Ensure swarm state path references use dynamic Path(__file__).resolve().parent.
    """
    def _replace_state(match: re.Match) -> str:
        prefix = match.group(1)
        return f'{prefix}Path(__file__).resolve().parent / "swarm_state.json"'

    new_content, count = SWARM_STATE_STANDALONE_PATTERN.subn(_replace_state, content)
    return new_content, count


def transform_content(
    content: str,
    fix_artifact_backslash: bool = True,
    fix_slash_operands: bool = True,
    fix_os_joins: bool = True,
    fix_nested: bool = True,
    fix_hardcoded: bool = True,
    fix_swarm_state: bool = True,
    auto_import_pathlib: bool = True,
) -> Tuple[str, int]:
    """
    Apply configured script path transformations to Python source code string.

    Returns:
        (transformed_content, total_changes_count)
    """
    total_changes = 0

    if fix_artifact_backslash:
        content, c = fix_artifact_backslash_strings(content)
        total_changes += c

    if fix_slash_operands:
        content, c = fix_path_slash_operands(content)
        total_changes += c

    if fix_os_joins:
        content, c = fix_os_path_joins(content)
        total_changes += c

    if fix_nested:
        content, c = fix_nested_path_constructs(content)
        total_changes += c

    if fix_hardcoded:
        content, c = fix_hardcoded_cochem_paths(content)
        total_changes += c

    if fix_swarm_state:
        content, c = fix_swarm_state_paths(content)
        total_changes += c

    if auto_import_pathlib and ("Path(" in content or "Path." in content):
        if not has_pathlib_import(content):
            new_content = add_pathlib_import_to_content(content)
            if new_content != content:
                content = new_content
                total_changes += 1

    return content, total_changes


def fix_file(
    file_path: Path | str,
    dry_run: bool = False,
    backup: bool = False,
    fix_artifact_backslash: bool = True,
    fix_slash_operands: bool = True,
    fix_os_joins: bool = True,
    fix_nested: bool = True,
    fix_hardcoded: bool = True,
    fix_swarm_state: bool = True,
    auto_import_pathlib: bool = True,
) -> FileFixResult:
    """
    Safely process and refactor script paths in a single Python file.
    """
    path = Path(file_path).resolve()

    if not path.is_file():
        return FileFixResult(path=path, error=f"File not found: {path}")

    try:
        content = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as e:
        return FileFixResult(path=path, error=f"Encoding error (UTF-8 required): {e}")
    except OSError as e:
        return FileFixResult(path=path, error=f"File read error: {e}")

    # Validate initial syntax
    is_valid_initial, initial_err = validate_python_syntax(content)
    if not is_valid_initial:
        logger.warning("File %s has initial syntax errors: %s", path, initial_err)
        return FileFixResult(path=path, error=f"Initial syntax error: {initial_err}")

    # Perform transformation
    new_content, changes = transform_content(
        content=content,
        fix_artifact_backslash=fix_artifact_backslash,
        fix_slash_operands=fix_slash_operands,
        fix_os_joins=fix_os_joins,
        fix_nested=fix_nested,
        fix_hardcoded=fix_hardcoded,
        fix_swarm_state=fix_swarm_state,
        auto_import_pathlib=auto_import_pathlib,
    )

    if new_content == content or changes == 0:
        return FileFixResult(path=path, modified=False, changes_count=0)

    # Validate transformed syntax
    is_valid_post, post_err = validate_python_syntax(new_content)
    if not is_valid_post and is_valid_initial:
        return FileFixResult(
            path=path,
            error=f"Refactoring aborted: Transformed code produced syntax error: {post_err}",
        )

    # Write changes if not dry-run
    if not dry_run:
        try:
            if backup:
                backup_path = path.with_suffix(path.suffix + ".bak")
                backup_path.write_text(content, encoding="utf-8")

            path.write_text(new_content, encoding="utf-8")
            logger.info("Fixed %d script path issues in %s", changes, path)
        except OSError as e:
            return FileFixResult(path=path, error=f"File write error: {e}")

    return FileFixResult(path=path, modified=True, changes_count=changes)


def should_exclude_path(path: Path, exclude_dirs: Sequence[str]) -> bool:
    """Check if any path component matches the exclusion list."""
    path_parts = set(path.parts)
    for excl in exclude_dirs:
        if excl in path_parts:
            return True
        if excl.endswith("-info") and any(part.endswith(excl) for part in path.parts):
            return True
    return False


def scan_and_fix_repo(
    root_dir: Path | str,
    glob_pattern: str = "update_swarm_state*.py",
    exclude_dirs: Optional[Sequence[str]] = None,
    dry_run: bool = False,
    backup: bool = False,
    fix_artifact_backslash: bool = True,
    fix_slash_operands: bool = True,
    fix_os_joins: bool = True,
    fix_nested: bool = True,
    fix_hardcoded: bool = True,
    fix_swarm_state: bool = True,
    auto_import_pathlib: bool = True,
) -> RepoFixSummary:
    """
    Discover and refactor Python files matching the specified glob pattern in a directory.
    """
    root = Path(root_dir).resolve()
    excludes = tuple(exclude_dirs) if exclude_dirs is not None else DEFAULT_EXCLUDE_DIRS

    summary = RepoFixSummary(root_dir=root)

    if not root.exists():
        summary.errors += 1
        summary.results.append(
            FileFixResult(path=root, error=f"Directory does not exist: {root}")
        )
        return summary

    if root.is_file():
        summary.total_found = 1
        summary.scanned = 1
        res = fix_file(
            root,
            dry_run=dry_run,
            backup=backup,
            fix_artifact_backslash=fix_artifact_backslash,
            fix_slash_operands=fix_slash_operands,
            fix_os_joins=fix_os_joins,
            fix_nested=fix_nested,
            fix_hardcoded=fix_hardcoded,
            fix_swarm_state=fix_swarm_state,
            auto_import_pathlib=auto_import_pathlib,
        )
        summary.results.append(res)
        if res.modified:
            summary.modified += 1
        if res.error:
            summary.errors += 1
        return summary

    matched_files = sorted(list(root.glob(glob_pattern)))
    summary.total_found = len(matched_files)

    for py_file in matched_files:
        if not py_file.is_file():
            continue

        if should_exclude_path(py_file, excludes):
            summary.skipped += 1
            summary.results.append(
                FileFixResult(path=py_file, skipped=True, reason="Excluded directory")
            )
            continue

        summary.scanned += 1
        res = fix_file(
            py_file,
            dry_run=dry_run,
            backup=backup,
            fix_artifact_backslash=fix_artifact_backslash,
            fix_slash_operands=fix_slash_operands,
            fix_os_joins=fix_os_joins,
            fix_nested=fix_nested,
            fix_hardcoded=fix_hardcoded,
            fix_swarm_state=fix_swarm_state,
            auto_import_pathlib=auto_import_pathlib,
        )
        summary.results.append(res)
        if res.modified:
            summary.modified += 1
        if res.error:
            summary.errors += 1

    return summary


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Audit, sanitize, and refactor script paths and swarm state updaters (v2)."
    )
    parser.add_argument(
        "-d",
        "--dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Target directory to scan (default: repository root).",
    )
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        default=None,
        help="Target a single Python file.",
    )
    parser.add_argument(
        "-p",
        "--pattern",
        type=str,
        default="update_swarm_state*.py",
        help="Glob pattern for discovering script files (default: 'update_swarm_state*.py').",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Simulate modifications without writing to disk.",
    )
    parser.add_argument(
        "-b",
        "--backup",
        action="store_true",
        help="Create .bak backup files before modifying.",
    )
    parser.add_argument(
        "--no-auto-pathlib",
        action="store_true",
        help="Do not auto-insert 'from pathlib import Path' when Path is used.",
    )
    parser.add_argument(
        "--no-fix-artifact-backslash",
        action="store_true",
        help="Do not sanitize artifact backslash strings.",
    )
    parser.add_argument(
        "--no-fix-slash-operands",
        action="store_true",
        help="Do not normalize backslashes inside Path division operands.",
    )
    parser.add_argument(
        "--no-fix-os-joins",
        action="store_true",
        help="Do not convert os.path.join calls to Path division.",
    )
    parser.add_argument(
        "--no-fix-nested",
        action="store_true",
        help="Do not sanitize nested Path(...) expressions.",
    )
    parser.add_argument(
        "--no-fix-hardcoded",
        action="store_true",
        help="Do not replace hardcoded absolute repository paths.",
    )
    parser.add_argument(
        "--no-fix-swarm-state",
        action="store_true",
        help="Do not standardize swarm_state.json file resolution.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging.",
    )
    return parser


def main(args: Optional[Sequence[str]] = None) -> int:
    """CLI entry point for fix_scripts2."""
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    logging.basicConfig(
        level=logging.DEBUG if parsed_args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    target_path = parsed_args.file if parsed_args.file else parsed_args.dir
    glob_pattern = parsed_args.pattern

    summary = scan_and_fix_repo(
        root_dir=target_path,
        glob_pattern=glob_pattern,
        dry_run=parsed_args.dry_run,
        backup=parsed_args.backup,
        fix_artifact_backslash=not parsed_args.no_fix_artifact_backslash,
        fix_slash_operands=not parsed_args.no_fix_slash_operands,
        fix_os_joins=not parsed_args.no_fix_os_joins,
        fix_nested=not parsed_args.no_fix_nested,
        fix_hardcoded=not parsed_args.no_fix_hardcoded,
        fix_swarm_state=not parsed_args.no_fix_swarm_state,
        auto_import_pathlib=not parsed_args.no_auto_pathlib,
    )

    print(summary.format_report())
    return 1 if summary.has_errors else 0


if __name__ == "__main__":
    sys.exit(main())

