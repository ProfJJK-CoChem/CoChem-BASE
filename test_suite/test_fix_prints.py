"""
Unit and integration tests for fix_prints.py
"""

from __future__ import annotations

import ast
from pathlib import Path
import pytest

from fix_prints import (
    DEFAULT_EXCLUDE_DIRS,
    FileFixResult,
    RepoFixSummary,
    add_logging_import_to_content,
    build_parser,
    fix_file,
    get_node_span_in_source,
    has_logger_instance,
    has_logging_import,
    main,
    scan_and_fix_repo,
    should_exclude_path,
    transform_content,
    transform_print_call,
    validate_python_syntax,
)


def test_validate_python_syntax():
    valid, err = validate_python_syntax("x = 10 + 20\nprint(x)")
    assert valid is True
    assert err is None

    invalid, err = validate_python_syntax("def broken_func(:\n    pass")
    assert invalid is False
    assert err is not None
    assert "Line 1" in err


def test_has_logging_import():
    assert has_logging_import("import logging\nlogging.info('hi')") is True
    assert has_logging_import("from logging import getLogger\nlog = getLogger()") is True
    assert has_logging_import("import loguru\n") is True
    assert has_logging_import("from loguru import logger\n") is True
    assert has_logging_import("import os, sys\nprint('no logging')") is False
    assert has_logging_import("def foo():\n    import logging\n    return logging") is True


def test_has_logger_instance():
    assert has_logger_instance("logger = logging.getLogger(__name__)") is True
    assert has_logger_instance("custom_log = logging.getLogger(__name__)", "custom_log") is True
    assert has_logger_instance("x = 10\nprint(x)") is False


def test_add_logging_import_to_content():
    content = '"""Module docstring."""\nfrom __future__ import annotations\n\nimport os\n'
    updated = add_logging_import_to_content(content)
    assert "import logging" in updated
    lines = updated.splitlines()
    assert lines[0] == '"""Module docstring."""'
    assert lines[1] == "from __future__ import annotations"
    assert lines[2] == "import logging"

    already = "import logging\nimport os\n"
    assert add_logging_import_to_content(already) == already

    with_basic = add_logging_import_to_content(content, init_basic_config=True)
    assert "logging.basicConfig(level=logging.INFO)" in with_basic

    with_logger = add_logging_import_to_content(content, init_logger_instance=True, logger_var_name="logger")
    assert "logger = logging.getLogger(__name__)" in with_logger

    shebang_content = '#!/usr/bin/env python3\n"""Docstring after shebang."""\nimport sys\n'
    updated_shebang = add_logging_import_to_content(shebang_content)
    assert "import logging" in updated_shebang
    shebang_lines = updated_shebang.splitlines()
    assert shebang_lines[0] == "#!/usr/bin/env python3"
    assert shebang_lines[1] == '"""Docstring after shebang."""'
    assert shebang_lines[2] == "import logging"


def test_get_node_span_in_source():
    src = "x = 1\nprint('hello', 42)\ny = 2\n"
    tree = ast.parse(src)
    call_node = [n for n in ast.walk(tree) if isinstance(n, ast.Call)][0]
    start, end = get_node_span_in_source(src, call_node)
    assert src[start:end] == "print('hello', 42)"


def test_transform_print_call():
    src1 = "print()"
    tree1 = ast.parse(src1)
    assert transform_print_call(src1, tree1.body[0].value) == 'logging.info("")'

    src2 = "print('Hello world')"
    tree2 = ast.parse(src2)
    assert transform_print_call(src2, tree2.body[0].value) == "logging.info('Hello world')"

    src3 = "print(f'Count: {count}')"
    tree3 = ast.parse(src3)
    assert transform_print_call(src3, tree3.body[0].value) == "logging.info(f'Count: {count}')"

    src4 = "print('User:', user_id, 42)"
    tree4 = ast.parse(src4)
    assert transform_print_call(src4, tree4.body[0].value) == "logging.info('%s %s %s', 'User:', user_id, 42)"

    src5 = "print('A', 'B', sep=', ')"
    tree5 = ast.parse(src5)
    assert transform_print_call(src5, tree5.body[0].value) == "logging.info('%s, %s', 'A', 'B')"

    src6 = "print('Fatal error', file=sys.stderr)"
    tree6 = ast.parse(src6)
    assert transform_print_call(src6, tree6.body[0].value, stderr_to_error=True) == "logging.error('Fatal error')"

    src7 = "print('Info', file=sys.stdout)"
    tree7 = ast.parse(src7)
    assert transform_print_call(src7, tree7.body[0].value) == "logging.info('Info')"

    src8 = "print('Writing to file', file=custom_out)"
    tree8 = ast.parse(src8)
    assert transform_print_call(src8, tree8.body[0].value, skip_custom_files=True) is None


def test_transform_content():
    sample = (
        '"""Sample module."""\n'
        "from __future__ import annotations\n\n"
        "def process():\n"
        "    print('Starting process')\n"
        "    print('Status:', 200)\n"
        "    print('Retaining this')  # keep-print\n"
        "    print('Error occurred', file=sys.stderr)\n"
    )
    transformed, count = transform_content(sample, target_logger="logging", default_level="info")
    assert count == 3
    assert "import logging" in transformed
    assert "logging.info('Starting process')" in transformed
    assert "logging.info('%s %s', 'Status:', 200)" in transformed
    assert "print('Retaining this')  # keep-print" in transformed
    assert "logging.error('Error occurred')" in transformed

    valid, err = validate_python_syntax(transformed)
    assert valid is True, f"Transformed code is invalid syntax: {err}"


def test_transform_content_with_logger_instance():
    sample = "def run():\n    print('Running task')\n"
    transformed, count = transform_content(
        sample,
        target_logger="logger",
        init_logger_instance=True,
    )
    assert count == 1
    assert "import logging" in transformed
    assert "logger = logging.getLogger(__name__)" in transformed
    assert "logger.info('Running task')" in transformed


def test_transform_content_preserves_strings_and_comments():
    sample = (
        "# print('in comment')\n"
        "msg = 'print(inside string)'\n"
        "def foo():\n"
        "    '''print in docstring'''\n"
        "    return 42\n"
    )
    transformed, count = transform_content(sample)
    assert count == 0
    assert transformed == sample


def test_fix_file_dry_run_and_backup(tmp_path: Path):
    target = tmp_path / "sample.py"
    initial_content = "def test():\n    print('Hello')\n"
    target.write_text(initial_content, encoding="utf-8")

    res_dry = fix_file(target, dry_run=True)
    assert res_dry.modified is True
    assert res_dry.changes_count == 1
    assert target.read_text(encoding="utf-8") == initial_content

    res_live = fix_file(target, dry_run=False, backup=True)
    assert res_live.modified is True
    assert "logging.info('Hello')" in target.read_text(encoding="utf-8")
    assert (tmp_path / "sample.py.bak").exists()
    assert (tmp_path / "sample.py.bak").read_text(encoding="utf-8") == initial_content


def test_fix_file_non_existent():
    res = fix_file(Path("/non/existent/path/file.py"))
    assert res.modified is False
    assert res.error is not None
    assert "File not found" in res.error


def test_fix_file_initial_syntax_error(tmp_path: Path):
    target = tmp_path / "broken.py"
    target.write_text("def broken(:\n    print(1)\n", encoding="utf-8")
    res = fix_file(target)
    assert res.modified is False
    assert res.error is not None
    assert "Initial syntax error" in res.error


def test_should_exclude_path():
    p1 = Path("D:/repo/__pycache__/compiled.py")
    p2 = Path("D:/repo/.git/config.py")
    p3 = Path("D:/repo/scratch/temp.py")
    p4 = Path("D:/repo/core/module.py")

    assert should_exclude_path(p1, DEFAULT_EXCLUDE_DIRS) is True
    assert should_exclude_path(p2, DEFAULT_EXCLUDE_DIRS) is True
    assert should_exclude_path(p3, DEFAULT_EXCLUDE_DIRS) is True
    assert should_exclude_path(p4, DEFAULT_EXCLUDE_DIRS) is False


def test_scan_and_fix_repo(tmp_path: Path):
    repo = tmp_path / "mock_repo"
    repo.mkdir()
    (repo / "core").mkdir()
    (repo / "__pycache__").mkdir()

    f1 = repo / "core" / "app.py"
    f1.write_text("def run():\n    print('app start')\n", encoding="utf-8")

    f2 = repo / "__pycache__" / "cached.py"
    f2.write_text("def run():\n    print('cached')\n", encoding="utf-8")

    summary = scan_and_fix_repo(repo, dry_run=False)
    assert summary.total_found == 2
    assert summary.scanned == 1
    assert summary.modified == 1
    assert summary.skipped == 1
    assert summary.errors == 0
    assert summary.has_errors is False

    report = summary.format_report()
    assert "Fix Prints Summary" in report
    assert "Files modified:           1" in report


def test_cli_main(tmp_path: Path, capsys):
    target = tmp_path / "test_cli.py"
    target.write_text("def main():\n    print('CLI test')\n", encoding="utf-8")

    exit_code = main(["--file", str(target), "--dry-run"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Files modified:           1" in captured.out