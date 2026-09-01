"""
fix_exceptions.py - Comprehensive tool for auditing, sanitizing, and refactoring
exception handling patterns across Python codebases.

Features:
- Detects and resolves missing `import json` when `json.JSONDecodeError` is caught.
- Sanitizes bare `except:` clauses into explicit `except Exception:`.
- Normalizes unwieldy or malformed exception handler tuples.
- AST syntax validation before and after transformation to prevent code corruption.
- Configurable dry-run, backup creation, file exclusions, and custom directory scanning.
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

logger = logging.getLogger("fix_exceptions")

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

# Standard CoChem multi-exception tuple
COCHEM_MULTI_EXCEPTION_PATTERN = (
    r"except\s*\(\s*RuntimeError\s*,\s*ValueError\s*,\s*OSError\s*,\s*FileNotFoundError\s*,"
    r"\s*json\.JSONDecodeError\s*,\s*KeyError\s*,\s*IndexError\s*,\s*TypeError\s*\)\s*as\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*:"
)


@dataclass
class FileFixResult:
    """Result of an exception fix attempt on a single file."""

    path: Path
    modified: bool = False
    changes_count: int = 0
    skipped: bool = False
    reason: Optional[str] = None
    error: Optional[str] = None


@dataclass
class RepoFixSummary:
    """Summary of exception fixes across an entire repository or directory."""

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
            f"Fix Exceptions Summary for: {self.root_dir}",
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


def has_json_import(content: str) -> bool:
    """Check if 'json' is imported in the source code."""
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "json":
                        return True
            elif isinstance(node, ast.ImportFrom):
                if node.module == "json":
                    return True
        return False
    except SyntaxError:
        # Fallback to regex if syntax tree is incomplete
        return bool(re.search(r"^\s*(?:import\s+json\b|from\s+json\s+import\b)", content, re.MULTILINE))


def add_json_import_to_content(content: str) -> str:
    """
    Safely insert 'import json' into source code after docstrings and future imports.
    """
    if has_json_import(content):
        return content

    lines = content.splitlines(keepends=True)
    if not lines:
        return "import json\n"

    insert_idx = 0
    in_docstring = False
    docstring_delimiter = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Handle file-level docstring
        if not in_docstring:
            if i == 0 and (stripped.startswith('"""') or stripped.startswith("'''")):
                docstring_delimiter = stripped[:3]
                if stripped.count(docstring_delimiter) >= 2 and len(stripped) > 3:
                    # Single-line docstring
                    insert_idx = i + 1
                    continue
                else:
                    in_docstring = True
                    continue
        else:
            if docstring_delimiter and docstring_delimiter in stripped:
                in_docstring = False
                insert_idx = i + 1
            continue

        # Skip shebang or encoding comments
        if stripped.startswith("#"):
            insert_idx = i + 1
            continue

        # Skip __future__ imports
        if stripped.startswith("from __future__ import"):
            insert_idx = i + 1
            continue

        # Stop at the first real code or import
        break

    # Insert import json
    lines.insert(insert_idx, "import json\n")
    return "".join(lines)


def fix_missing_json_imports(content: str) -> Tuple[str, int]:
    """
    If 'json.JSONDecodeError' or 'json.' is referenced in an exception handler
    or body, ensure 'import json' is present in the module.
    """
    changes = 0
    if "json.JSONDecodeError" in content or "json." in content:
        if not has_json_import(content):
            new_content = add_json_import_to_content(content)
            if new_content != content:
                content = new_content
                changes += 1
    return content, changes


def fix_bare_exceptions(content: str) -> Tuple[str, int]:
    """
    Convert bare 'except:' clauses to explicit 'except Exception:'.
    """
    pattern = re.compile(r"(\bexcept)\s*:", re.MULTILINE)
    new_content, count = pattern.subn(r"\1 Exception:", content)
    return new_content, count


def normalize_cochem_exception_tuples(content: str) -> Tuple[str, int]:
    """
    Standardize CoChem multi-exception tuples and ensure clean syntax.
    """
    pattern = re.compile(COCHEM_MULTI_EXCEPTION_PATTERN)
    replacement = (
        r"except (RuntimeError, ValueError, OSError, FileNotFoundError, "
        r"json.JSONDecodeError, KeyError, IndexError, TypeError) as \1:"
    )
    new_content, count = pattern.subn(replacement, content)
    return new_content, count


def strip_json_decode_error_if_unimported(content: str) -> Tuple[str, int]:
    """
    Replace 'json.JSONDecodeError' from multi-exception tuples if 'json' is not imported.
    """
    if has_json_import(content):
        return content, 0

    pattern = re.compile(
        r"except\s*\(\s*RuntimeError\s*,\s*ValueError\s*,\s*OSError\s*,\s*FileNotFoundError\s*,"
        r"\s*json\.JSONDecodeError\s*,\s*KeyError\s*,\s*IndexError\s*,\s*TypeError\s*\)\s*as\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*:"
    )
    replacement = (
        r"except (RuntimeError, ValueError, OSError, FileNotFoundError, "
        r"KeyError, IndexError, TypeError) as \1:"
    )
    new_content, count = pattern.subn(replacement, content)
    return new_content, count


def transform_content(
    content: str,
    add_json_import: bool = True,
    fix_bare: bool = True,
    normalize_tuples: bool = True,
    strip_unimported_json: bool = False,
) -> Tuple[str, int]:
    """
    Apply configured transformations to Python source code string.

    Returns:
        (transformed_content, total_changes_count)
    """
    total_changes = 0

    if strip_unimported_json and not add_json_import:
        content, c = strip_json_decode_error_if_unimported(content)
        total_changes += c
    elif add_json_import:
        content, c = fix_missing_json_imports(content)
        total_changes += c

    if normalize_tuples:
        content, c = normalize_cochem_exception_tuples(content)
        total_changes += c

    if fix_bare:
        content, c = fix_bare_exceptions(content)
        total_changes += c

    return content, total_changes


def fix_file(
    file_path: Path | str,
    dry_run: bool = False,
    backup: bool = False,
    add_json_import: bool = True,
    fix_bare: bool = True,
    normalize_tuples: bool = True,
    strip_unimported_json: bool = False,
) -> FileFixResult:
    """
    Safely process and refactor exception handling in a single Python file.
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

    # Perform transformation
    new_content, changes = transform_content(
        content=content,
        add_json_import=add_json_import,
        fix_bare=fix_bare,
        normalize_tuples=normalize_tuples,
        strip_unimported_json=strip_unimported_json,
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
            logger.info("Fixed %d exception issues in %s", changes, path)
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
    add_json_import: bool = True,
    fix_bare: bool = True,
    normalize_tuples: bool = True,
    strip_unimported_json: bool = False,
) -> RepoFixSummary:
    """
    Recursively discover and refactor Python files in a directory.
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
            add_json_import=add_json_import,
            fix_bare=fix_bare,
            normalize_tuples=normalize_tuples,
            strip_unimported_json=strip_unimported_json,
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
            add_json_import=add_json_import,
            fix_bare=fix_bare,
            normalize_tuples=normalize_tuples,
            strip_unimported_json=strip_unimported_json,
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
        description="Audit, sanitize, and refactor exception handling in Python source files."
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
        "--no-json-import",
        action="store_true",
        help="Do not auto-insert 'import json' when json.JSONDecodeError is caught.",
    )
    parser.add_argument(
        "--strip-unimported-json",
        action="store_true",
        help="Remove json.JSONDecodeError from tuples if json is not imported.",
    )
    parser.add_argument(
        "--no-fix-bare",
        action="store_true",
        help="Do not convert bare 'except:' to 'except Exception:'.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging.",
    )
    return parser


def main(args: Optional[Sequence[str]] = None) -> int:
    """CLI entry point for fix_exceptions."""
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    logging.basicConfig(
        level=logging.DEBUG if parsed_args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    target_path = parsed_args.file if parsed_args.file else parsed_args.dir
    add_json_import = not parsed_args.no_json_import
    fix_bare = not parsed_args.no_fix_bare

    summary = scan_and_fix_repo(
        root_dir=target_path,
        dry_run=parsed_args.dry_run,
        backup=parsed_args.backup,
        add_json_import=add_json_import,
        fix_bare=fix_bare,
        strip_unimported_json=parsed_args.strip_unimported_json,
    )

    print(summary.format_report())
    return 1 if summary.has_errors else 0


if __name__ == "__main__":
    sys.exit(main())

