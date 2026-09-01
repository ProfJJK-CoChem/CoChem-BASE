"""Unit tests for ci_tools/verify_anti_patching.py."""

from __future__ import annotations

import ast
import tempfile
from pathlib import Path

import pytest

from ci_tools.verify_anti_patching import (
    AntiPatchingVisitor,


    audit_file,
    audit_repository,
)








def test_visitor_bare_except() -> None:
    code = """
try:
    do_something()
except:
    pass
"""
    tree = ast.parse(code)
    visitor = AntiPatchingVisitor()
    visitor.visit(tree)
    assert len(visitor.violations) == 1
    assert "Banned bare 'except:' clause" in visitor.violations[0]


def test_visitor_broad_exception_with_pass() -> None:
    code = """
try:
    do_something()
except Exception:
    pass
"""
    tree = ast.parse(code)
    visitor = AntiPatchingVisitor()
    visitor.visit(tree)
    assert len(visitor.violations) == 1
    assert "Banned broad exception swallowing 'except Exception:' with 'pass'" in visitor.violations[0]


def test_visitor_broad_base_exception_with_ellipsis() -> None:
    code = """
try:
    do_something()
except BaseException:
    ...
"""
    tree = ast.parse(code)
    visitor = AntiPatchingVisitor()
    visitor.visit(tree)
    assert len(visitor.violations) == 1
    assert "Banned broad exception swallowing 'except BaseException:' with '...'" in visitor.violations[0]


def test_visitor_broad_exception_with_docstring_only() -> None:
    code = """
try:
    do_something()
except Exception:
    \"\"\"swallow error silently\"\"\"
"""
    tree = ast.parse(code)
    visitor = AntiPatchingVisitor()
    visitor.visit(tree)
    assert len(visitor.violations) == 1
    assert "Banned broad exception swallowing 'except Exception:' with docstring/no-op body" in visitor.violations[0]


def test_visitor_qualified_exception_builtins() -> None:
    code = """
try:
    do_something()
except builtins.Exception:
    pass
"""
    tree = ast.parse(code)
    visitor = AntiPatchingVisitor()
    visitor.visit(tree)
    assert len(visitor.violations) == 1
    assert "Banned broad exception swallowing 'except Exception:' with 'pass'" in visitor.violations[0]


def test_visitor_tuple_with_broad_exception() -> None:
    code = """
try:
    do_something()
except (KeyError, Exception):
    pass
"""
    tree = ast.parse(code)
    visitor = AntiPatchingVisitor()
    visitor.visit(tree)
    assert len(visitor.violations) == 1
    assert "Banned broad exception swallowing 'except Exception:' with 'pass'" in visitor.violations[0]


def test_visitor_specific_exception_allowed() -> None:
    code = """
try:
    do_something()
except (KeyError, ValueError):
    pass
"""
    tree = ast.parse(code)
    visitor = AntiPatchingVisitor()
    visitor.visit(tree)
    assert len(visitor.violations) == 0


def test_visitor_constant_condition_if_statements() -> None:
    code = """
if True:
    run_bypass()

if False:
    dead_branch()

if 1:
    old_toggle()
"""
    tree = ast.parse(code)
    visitor = AntiPatchingVisitor()
    visitor.visit(tree)
    assert len(visitor.violations) == 3
    assert any("hardcoded constant condition 'if True:'" in v for v in visitor.violations)
    assert any("hardcoded constant condition 'if False:'" in v for v in visitor.violations)
    assert any("hardcoded constant condition 'if 1:'" in v for v in visitor.violations)


def test_visitor_legitimate_conditions_allowed() -> None:
    code = """
if __name__ == '__main__':
    main()

if x > 5:
    compute(x)

if TYPE_CHECKING:
    import foo
"""
    tree = ast.parse(code)
    visitor = AntiPatchingVisitor()
    visitor.visit(tree)
    assert len(visitor.violations) == 0


def test_audit_file(tmp_path: Path) -> None:
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("def foo():\n    return 42\n", encoding="utf-8")

    violating_file = tmp_path / "violating.py"
    violating_file.write_text("try:\n    foo()\nexcept Exception:\n    pass\n", encoding="utf-8")

    syntax_error_file = tmp_path / "broken.py"
    syntax_error_file.write_text("def broken(\n", encoding="utf-8")

    assert audit_file(clean_file, tmp_path) == []
    assert len(audit_file(violating_file, tmp_path)) == 1
    assert any("Syntax error" in v for v in audit_file(syntax_error_file, tmp_path))


def test_audit_repository_target_dirs_prefix_isolation(tmp_path: Path) -> None:
    # Setup directories: "core" and "core_engine"
    core_dir = tmp_path / "core"
    core_dir.mkdir()
    (core_dir / "bad_core.py").write_text("try:\n    1/0\nexcept Exception:\n    pass\n", encoding="utf-8")

    core_engine_dir = tmp_path / "core_engine"
    core_engine_dir.mkdir()
    (core_engine_dir / "bad_engine.py").write_text("try:\n    1/0\nexcept Exception:\n    pass\n", encoding="utf-8")

    # When target_dirs is ["core"], "core_engine" should NOT be scanned
    passed, violations = audit_repository(tmp_path, target_dirs=["core"])
    assert passed is False
    assert any("core" in f and "core_engine" not in f for f in violations)
    assert not any("core_engine" in f for f in violations)


def test_audit_repository_excluded_directories(tmp_path: Path) -> None:
    """Verify common virtualenv, cache, data, and artifact directories are excluded."""
    for excluded in ["venv", "site-packages", "artifacts", "datasets", "data", "__pycache__", "build", "dist", "Report_Archive", "scratch"]:
        exc_dir = tmp_path / excluded
        exc_dir.mkdir(parents=True, exist_ok=True)
        (exc_dir / "bad_excluded.py").write_text("try:\n    1/0\nexcept Exception:\n    pass\n", encoding="utf-8")

    passed, violations = audit_repository(tmp_path)
    assert passed is True
    assert len(violations) == 0


def test_audit_repository_target_dirs_pruning_deep(tmp_path: Path) -> None:
    """Verify deeply nested untargeted directories are pruned and not descended into."""
    deep_untargeted = tmp_path / "other" / "deep1" / "deep2"
    deep_untargeted.mkdir(parents=True, exist_ok=True)
    (deep_untargeted / "bad_deep.py").write_text("try:\n    1/0\nexcept Exception:\n    pass\n", encoding="utf-8")

    target_dir = tmp_path / "core"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "clean.py").write_text("def ok():\n    return 1\n", encoding="utf-8")

    passed, violations = audit_repository(tmp_path, target_dirs=["core"])
    assert passed is True
    assert len(violations) == 0


def test_audit_repository_root_files_skipped_when_target_dirs_specified(tmp_path: Path) -> None:
    """Verify root-level files are not scanned when target_dirs is specified."""
    root_bad = tmp_path / "root_bad.py"
    root_bad.write_text("try:\n    1/0\nexcept Exception:\n    pass\n", encoding="utf-8")

    target_dir = tmp_path / "core"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "clean.py").write_text("def ok():\n    return 1\n", encoding="utf-8")

    passed, violations = audit_repository(tmp_path, target_dirs=["core"])
    assert passed is True
    assert len(violations) == 0

