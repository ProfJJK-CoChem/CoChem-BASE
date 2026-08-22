"""
fix_prints.py - Comprehensive AST-based tool for auditing, sanitizing, and refactoring
print statements into structured Python logging calls across codebases.

Features:
- AST-powered detection of actual `print(...)` call nodes.
- Preserves comments, docstrings, string literals containing 'print(', and indentation.
- Handles empty prints, single arguments, multiple arguments with separator formatting,
  and f-strings without runtime string formatting errors.
- Automatically routes `file=sys.stderr` to `logging.error(...)` (or `logger.error(...)`).
- Strips console-specific keywords (end, flush) safely.
- Supports inline exclusions via `# keep-print` or `# noqa: print`.
- Safely inserts `import logging` (and optional `logger = logging.getLogger(__name__)`
  or `logging.basicConfig(level=logging.INFO)`) after file docstrings and `__future__` imports.
- AST syntax validation before and after transformation to prevent code corruption.
- Configurable dry-run, backup creation (.bak), file exclusions, and custom directory scanning.
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

logger = logging.getLogger("fix_prints")

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


@dataclass
class FileFixResult:
    """Result of a print fix attempt on a single file."""

    path: Path
    modified: bool = False
    changes_count: int = 0
    skipped: bool = False
    reason: Optional[str] = None
    error: Optional[str] = None


@dataclass
class RepoFixSummary:
    """Summary of print fixes across an entire repository or directory."""

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
            f"Fix Prints Summary for: {self.root_dir}",
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
        (True, None) if syntax is valid, or (False, error_message) on SyntaxError.
    """
    try:
        ast.parse(source_code)
        return True, None
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"


def has_logging_import(content: str) -> bool:
    """Check if 'logging' or a supported logger module is imported in the source code."""
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ("logging", "loguru"):
                        return True
            elif isinstance(node, ast.ImportFrom):
                if node.module in ("logging", "loguru"):
                    return True
        return False
    except SyntaxError:
        return bool(
            re.search(
                r"^\s*(?:import\s+logging\b|from\s+logging\s+import\b|import\s+loguru\b|from\s+loguru\s+import\b)",
                content,
                re.MULTILINE,
            )
        )


def has_logger_instance(content: str, logger_var_name: str = "logger") -> bool:
    """Check if a module-level logger instance (e.g. logger = logging.getLogger(...)) exists."""
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == logger_var_name:
                        return True
        return False
    except SyntaxError:
        return bool(re.search(rf"^\s*{re.escape(logger_var_name)}\s*=", content, re.MULTILINE))


def add_logging_import_to_content(
    content: str,
    init_basic_config: bool = False,
    init_logger_instance: bool = False,
    logger_var_name: str = "logger",
) -> str:
    """
    Safely insert 'import logging' (and optional logger initialization) into source code
    after module docstrings, shebangs, and __future__ imports.
    """
    needs_logging = not has_logging_import(content)
    needs_logger_inst = init_logger_instance and not has_logger_instance(content, logger_var_name)

    if not needs_logging and not needs_logger_inst and not init_basic_config:
        return content

    lines = content.splitlines(keepends=True)
    if not lines:
        to_add: List[str] = []
        if needs_logging:
            to_add.append("import logging\n")
        if init_basic_config:
            to_add.append("logging.basicConfig(level=logging.INFO)\n")
        if needs_logger_inst:
            to_add.append(f"{logger_var_name} = logging.getLogger(__name__)\n")
        return "".join(to_add)

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
            if stripped.startswith('"""') or stripped.startswith("'''"):
                docstring_delimiter = stripped[:3]
                if stripped.count(docstring_delimiter) >= 2 and len(stripped) > 3:
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

    statements_to_insert: List[str] = []
    if needs_logging:
        statements_to_insert.append("import logging\n")
    if init_basic_config:
        statements_to_insert.append("logging.basicConfig(level=logging.INFO)\n")
    if needs_logger_inst:
        statements_to_insert.append(f"{logger_var_name} = logging.getLogger(__name__)\n")

    for idx, stmt in enumerate(statements_to_insert):
        lines.insert(insert_idx + idx, stmt)

    return "".join(lines)


def get_node_span_in_source(source: str, node: ast.AST) -> Tuple[int, int]:
    """
    Calculate character start and end slice indices for an AST node in the source text.
    """
    lines = source.splitlines(keepends=True)
    start_pos = sum(len(lines[i]) for i in range(node.lineno - 1)) + node.col_offset
    end_pos = sum(len(lines[i]) for i in range(node.end_lineno - 1)) + node.end_col_offset
    return start_pos, end_pos


def transform_print_call(
    source: str,
    node: ast.Call,
    target_logger: str = "logging",
    default_level: str = "info",
    stderr_to_error: bool = True,
    skip_custom_files: bool = True,
) -> Optional[str]:
    """
    Convert an ast.Call node for `print(...)` into the corresponding logging call string.

    Returns:
        The replacement code string, or None if the call should not be transformed.
    """
    level = default_level.lower()
    sep_str = " "
    is_custom_file = False

    for kw in node.keywords:
        if kw.arg == "file":
            file_src = ast.get_source_segment(source, kw.value) or ""
            if "stderr" in file_src:
                if stderr_to_error:
                    level = "error"
            elif "stdout" in file_src:
                level = default_level.lower()
            else:
                is_custom_file = True
        elif kw.arg == "sep":
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                sep_str = kw.value.value

    if is_custom_file and skip_custom_files:
        # Avoid breaking file writer calls like print(..., file=f)
        return None

    func_call = f"{target_logger}.{level}"

    if not node.args:
        return f'{func_call}("")'

    if len(node.args) == 1:
        arg_src = ast.get_source_segment(source, node.args[0])
        return f"{func_call}({arg_src})"

    # Multiple positional arguments: format as safe format string with arguments
    fmt_pattern = sep_str.join(["%s"] * len(node.args))
    args_src = ", ".join(ast.get_source_segment(source, a) for a in node.args)
    return f"{func_call}({repr(fmt_pattern)}, {args_src})"


def transform_content(
    content: str,
    target_logger: str = "logging",
    default_level: str = "info",
    auto_import_logging: bool = True,
    init_basic_config: bool = False,
    init_logger_instance: bool = False,
    logger_var_name: str = "logger",
    stderr_to_error: bool = True,
    skip_custom_files: bool = True,
) -> Tuple[str, int]:
    """
    Apply AST-based print-to-logging transformation on Python source code string.

    Returns:
        (transformed_content, total_changes_count)
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return content, 0

    lines = content.splitlines(keepends=True)
    calls_to_replace: List[Tuple[int, int, str]] = []

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        ):
            # Check for inline exclusion comments on the line of the call
            if node.lineno <= len(lines):
                line_text = lines[node.lineno - 1]
                if any(
                    marker in line_text
                    for marker in ("# keep-print", "# noqa: print", "# noqa:print", "# pragma: no-fix-print")
                ):
                    continue

            replacement = transform_print_call(
                source=content,
                node=node,
                target_logger=target_logger,
                default_level=default_level,
                stderr_to_error=stderr_to_error,
                skip_custom_files=skip_custom_files,
            )

            if replacement is not None:
                start_pos, end_pos = get_node_span_in_source(content, node)
                calls_to_replace.append((start_pos, end_pos, replacement))

    if not calls_to_replace:
        return content, 0

    # Sort in reverse order of start position to keep offsets valid
    calls_to_replace.sort(key=lambda item: item[0], reverse=True)

    result = content
    for start_pos, end_pos, replacement in calls_to_replace:
        result = result[:start_pos] + replacement + result[end_pos:]

    total_changes = len(calls_to_replace)

    if auto_import_logging:
        result = add_logging_import_to_content(
            content=result,
            init_basic_config=init_basic_config,
            init_logger_instance=init_logger_instance or (target_logger == logger_var_name),
            logger_var_name=logger_var_name,
        )

    return result, total_changes


def fix_file(
    file_path: Path | str,
    dry_run: bool = False,
    backup: bool = False,
    target_logger: str = "logging",
    default_level: str = "info",
    auto_import_logging: bool = True,
    init_basic_config: bool = False,
    init_logger_instance: bool = False,
    logger_var_name: str = "logger",
    stderr_to_error: bool = True,
    skip_custom_files: bool = True,
) -> FileFixResult:
    """
    Safely process and refactor print statements in a single Python file.
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
        return FileFixResult(
            path=path,
            error=f"Initial syntax error: {initial_err}",
        )

    # Perform transformation
    new_content, changes = transform_content(
        content=content,
        target_logger=target_logger,
        default_level=default_level,
        auto_import_logging=auto_import_logging,
        init_basic_config=init_basic_config,
        init_logger_instance=init_logger_instance,
        logger_var_name=logger_var_name,
        stderr_to_error=stderr_to_error,
        skip_custom_files=skip_custom_files,
    )

    if new_content == content or changes == 0:
        return FileFixResult(path=path, modified=False, changes_count=0)

    # Validate transformed syntax
    is_valid_post, post_err = validate_python_syntax(new_content)
    if not is_valid_post:
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
            logger.info("Fixed %d print statements in %s", changes, path)
        except OSError as e:
            return FileFixResult(path=path, error=f"File write error: {e}")

    return FileFixResult(path=path, modified=True, changes_count=changes)


def should_exclude_path(path: Path, exclude_dirs: Sequence[str]) -> bool:
    """Check if any path component matches the exclusion list."""
    path_parts = set(path.parts)
    for excl in exclude_dirs:
        if excl in path_parts:
            return True
        if any(part.startswith(excl) for part in path.parts):
            return True
    return False


def scan_and_fix_repo(
    root_dir: Path | str,
    exclude_dirs: Optional[Sequence[str]] = None,
    dry_run: bool = False,
    backup: bool = False,
    target_logger: str = "logging",
    default_level: str = "info",
    auto_import_logging: bool = True,
    init_basic_config: bool = False,
    init_logger_instance: bool = False,
    logger_var_name: str = "logger",
    stderr_to_error: bool = True,
    skip_custom_files: bool = True,
) -> RepoFixSummary:
    """
    Recursively discover and refactor print statements in Python files across a directory.
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
            target_logger=target_logger,
            default_level=default_level,
            auto_import_logging=auto_import_logging,
            init_basic_config=init_basic_config,
            init_logger_instance=init_logger_instance,
            logger_var_name=logger_var_name,
            stderr_to_error=stderr_to_error,
            skip_custom_files=skip_custom_files,
        )
        summary.results.append(res)
        if res.modified:
            summary.modified += 1
        if res.error:
            summary.errors += 1
        return summary

    all_py_files = sorted(list(root.rglob("*.py")))
    summary.total_found = len(all_py_files)

    for py_file in all_py_files:
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
            target_logger=target_logger,
            default_level=default_level,
            auto_import_logging=auto_import_logging,
            init_basic_config=init_basic_config,
            init_logger_instance=init_logger_instance,
            logger_var_name=logger_var_name,
            stderr_to_error=stderr_to_error,
            skip_custom_files=skip_custom_files,
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
        description="Audit, sanitize, and refactor print statements to structured logging in Python source files."
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
        "--target-logger",
        type=str,
        default="logging",
        help="Target logger identifier (default: 'logging', e.g. 'logging' or 'logger').",
    )
    parser.add_argument(
        "--level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Default log level for converted print statements (default: 'info').",
    )
    parser.add_argument(
        "--no-auto-import",
        action="store_true",
        help="Do not auto-insert 'import logging' when prints are converted.",
    )
    parser.add_argument(
        "--add-basic-config",
        action="store_true",
        help="Auto-insert 'logging.basicConfig(level=logging.INFO)' when logging is imported.",
    )
    parser.add_argument(
        "--use-logger-instance",
        action="store_true",
        help="Create and use a module-level logger instance: logger = logging.getLogger(__name__).",
    )
    parser.add_argument(
        "--logger-var",
        type=str,
        default="logger",
        help="Variable name for logger instance (default: 'logger').",
    )
    parser.add_argument(
        "--no-stderr-to-error",
        action="store_true",
        help="Do not map file=sys.stderr to logging.error.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging.",
    )
    return parser


def main(args: Optional[Sequence[str]] = None) -> int:
    """CLI entry point for fix_prints."""
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    logging.basicConfig(
        level=logging.DEBUG if parsed_args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    target_path = parsed_args.file if parsed_args.file else parsed_args.dir
    target_logger = parsed_args.logger_var if parsed_args.use_logger_instance else parsed_args.target_logger

    summary = scan_and_fix_repo(
        root_dir=target_path,
        dry_run=parsed_args.dry_run,
        backup=parsed_args.backup,
        target_logger=target_logger,
        default_level=parsed_args.level,
        auto_import_logging=not parsed_args.no_auto_import,
        init_basic_config=parsed_args.add_basic_config,
        init_logger_instance=parsed_args.use_logger_instance,
        logger_var_name=parsed_args.logger_var,
        stderr_to_error=not parsed_args.no_stderr_to_error,
    )

    print(summary.format_report())
    return 1 if summary.has_errors else 0


if __name__ == "__main__":
    sys.exit(main())

