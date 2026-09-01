"""
Unit and integration tests for fix_exceptions.py
"""

from pathlib import Path
import pytest

from fix_exceptions import (
    DEFAULT_EXCLUDE_DIRS,
    FileFixResult,
    RepoFixSummary,
    add_json_import_to_content,
    fix_bare_exceptions,
    fix_file,
    fix_missing_json_imports,
    has_json_import,
    main,
    normalize_cochem_exception_tuples,
    scan_and_fix_repo,
    should_exclude_path,
    strip_json_decode_error_if_unimported,
    transform_content,
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


def test_has_json_import():
    assert has_json_import("import json\nx = json.dumps({})") is True
    assert has_json_import("from json import loads\nx = loads(\"{}\")") is True
    assert has_json_import("import os, sys\nprint('no json')") is False
    assert has_json_import("def foo():\n    import json\n    return json") is True


def test_add_json_import_to_content():
    content = '"""Module docstring."""\nfrom __future__ import annotations\n\nimport os\n'
    updated = add_json_import_to_content(content)
    assert "import json" in updated
    lines = updated.splitlines()
    assert lines[0] == '"""Module docstring."""'
    assert lines[1] == "from __future__ import annotations"
    assert lines[2] == "import json"

    already = "import json\nimport os\n"
    assert add_json_import_to_content(already) == already


def test_fix_missing_json_imports():
    code = (
        "try:\n"
        "    pass\n"
        "except (RuntimeError, json.JSONDecodeError) as e:\n"
        "    pass\n"
    )
    new_code, changes = fix_missing_json_imports(code)
    assert changes == 1
    assert "import json" in new_code
    valid, _ = validate_python_syntax(new_code)
    assert valid is True

    no_json = "try:\n    pass\nexcept ValueError:\n    pass\n"
    _, changes = fix_missing_json_imports(no_json)
    assert changes == 0


def test_fix_bare_exceptions():
    code = "try:\n    val = 1 / 0\nexcept:\n    val = 0\n"
    new_code, count = fix_bare_exceptions(code)
    assert count == 1
    assert "except Exception:" in new_code
    valid, _ = validate_python_syntax(new_code)
    assert valid is True


def test_normalize_cochem_exception_tuples():
    clean_code = (
        "try:\n"
        "    pass\n"
        "except (RuntimeError, ValueError, OSError, FileNotFoundError, json.JSONDecodeError, KeyError, IndexError, TypeError) as err:\n"
        "    pass\n"
    )
    new_code, count = normalize_cochem_exception_tuples(clean_code)
    assert count == 1
    assert "except (RuntimeError, ValueError, OSError, FileNotFoundError, json.JSONDecodeError, KeyError, IndexError, TypeError) as err:" in new_code


def test_strip_json_decode_error_if_unimported():
    code = (
        "try:\n"
        "    pass\n"
        "except (RuntimeError, ValueError, OSError, FileNotFoundError, json.JSONDecodeError, KeyError, IndexError, TypeError) as e:\n"
        "    pass\n"
    )
    new_code, count = strip_json_decode_error_if_unimported(code)
    assert count == 1
    assert "json.JSONDecodeError" not in new_code
    assert "except (RuntimeError, ValueError, OSError, FileNotFoundError, KeyError, IndexError, TypeError) as e:" in new_code


def test_transform_content_pipeline():
    sample = (
        '"""Sample doc."""\n'
        "from __future__ import annotations\n\n"
        "def process():\n"
        "    try:\n"
        "        pass\n"
        "    except:\n"
        "        pass\n"
        "    try:\n"
        "        pass\n"
        "    except (RuntimeError, ValueError, OSError, FileNotFoundError, json.JSONDecodeError, KeyError, IndexError, TypeError) as e:\n"
        "        pass\n"
    )
    transformed, changes = transform_content(sample, add_json_import=True, fix_bare=True)
    assert changes >= 2
    assert "import json" in transformed
    assert "except Exception:" in transformed
    valid, err = validate_python_syntax(transformed)
    assert valid is True, f"Syntax error: {err}"


def test_fix_file_dry_run_and_backup(tmp_path: Path):
    target = tmp_path / "sample.py"
    initial_content = "try:\n    pass\nexcept:\n    pass\n"
    target.write_text(initial_content, encoding="utf-8")

    res_dry = fix_file(target, dry_run=True)
    assert res_dry.modified is True
    assert res_dry.changes_count == 1
    assert target.read_text(encoding="utf-8") == initial_content

    res_live = fix_file(target, dry_run=False, backup=True)
    assert res_live.modified is True
    assert "except Exception:" in target.read_text(encoding="utf-8")
    assert (tmp_path / "sample.py.bak").exists()
    assert (tmp_path / "sample.py.bak").read_text(encoding="utf-8") == initial_content


def test_fix_file_non_existent():
    res = fix_file(Path("/non/existent/path/file.py"))
    assert res.modified is False
    assert res.error is not None
    assert "File not found" in res.error


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
    repo = tmp_path / "physical_test_files"
    repo.mkdir()
    (repo / "core").mkdir()
    (repo / "__pycache__").mkdir()

    f1 = repo / "core" / "app.py"
    f1.write_text("try:\n    pass\nexcept:\n    pass\n", encoding="utf-8")

    f2 = repo / "__pycache__" / "cached.py"
    f2.write_text("try:\n    pass\nexcept:\n    pass\n", encoding="utf-8")

    summary = scan_and_fix_repo(repo, dry_run=False)
    assert summary.total_found == 2
    assert summary.scanned == 1
    assert summary.modified == 1
    assert summary.skipped == 1
    assert summary.errors == 0
    assert summary.has_errors is False

    report = summary.format_report()
    assert "Fix Exceptions Summary" in report
    assert "Files modified:           1" in report


def test_cli_main(tmp_path: Path, capsys):
    target = tmp_path / "test_cli.py"
    target.write_text("try:\n    pass\nexcept:\n    pass\n", encoding="utf-8")

    exit_code = main(["--file", str(target), "--dry-run"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Files modified:           1" in captured.out