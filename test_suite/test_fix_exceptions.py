"""
Unit and integration tests for fix_exceptions.py
"""

from __future__ import annotations

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


def test_validate_python_syntax() -> None:
    valid, err = validate_python_syntax("x = 10 + 20\nprint(x)")
    assert valid is True
    assert err is None

    invalid, err = validate_python_syntax("def broken_func(:\n    pass")
    assert invalid is False
    assert err is not None
    assert "Line 1" in err


def test_has_json_import() -> None:
    assert has_json_import("import json\nx = json.dumps({})") is True
    assert has_json_import("from json import loads\nx = loads(\"{}\")") is True
    assert has_json_import("import os, sys\nprint('no json')") is False
    assert has_json_import("def foo():\n    import json\n    return json") is True
    # Syntax error fallback to regex
    assert has_json_import("import json\ndef broken(:\n") is True
    assert has_json_import("from json import loads\ndef broken(:\n") is True
    assert has_json_import("x = 1\ndef broken(:\n") is False


def test_add_json_import_to_content() -> None:
    # Empty string
    assert add_json_import_to_content("") == "import json\n"

    # Single-line docstring + future import
    content = '"""Module docstring."""\nfrom __future__ import annotations\n\nimport os\n'
    updated = add_json_import_to_content(content)
    assert "import json" in updated
    lines = updated.splitlines()
    assert lines[0] == '"""Module docstring."""'
    assert lines[1] == "from __future__ import annotations"
    assert lines[2] == "import json"

    # Multi-line docstring
    multiline_doc = '"""\nLine 1\nLine 2\n"""\nimport sys\n'
    updated_multi = add_json_import_to_content(multiline_doc)
    assert '"""\nLine 1\nLine 2\n"""\nimport json\nimport sys\n' == updated_multi

    # Shebang and comments
    shebang_content = "#!/usr/bin/env python\n# coding: utf-8\nx = 1\n"
    updated_shebang = add_json_import_to_content(shebang_content)
    assert "#!/usr/bin/env python\n# coding: utf-8\nimport json\nx = 1\n" == updated_shebang

    # Already imported
    already = "import json\nimport os\n"
    assert add_json_import_to_content(already) == already


def test_fix_missing_json_imports() -> None:
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


def test_fix_bare_exceptions() -> None:
    code = "try:\n    val = 1 / 0\nexcept:\n    val = 0\n"
    new_code, count = fix_bare_exceptions(code)
    assert count == 1
    assert "except Exception:" in new_code
    valid, _ = validate_python_syntax(new_code)
    assert valid is True


def test_normalize_cochem_exception_tuples() -> None:
    clean_code = (
        "try:\n"
        "    pass\n"
        "except (RuntimeError, ValueError, OSError, FileNotFoundError, json.JSONDecodeError, KeyError, IndexError, TypeError) as err:\n"
        "    pass\n"
    )
    new_code, count = normalize_cochem_exception_tuples(clean_code)
    assert count == 1
    assert "except (RuntimeError, ValueError, OSError, FileNotFoundError, json.JSONDecodeError, KeyError, IndexError, TypeError) as err:" in new_code


def test_strip_json_decode_error_if_unimported() -> None:
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

    # When json is already imported, it should not strip
    with_import = "import json\n" + code
    unchanged, count0 = strip_json_decode_error_if_unimported(with_import)
    assert count0 == 0
    assert "json.JSONDecodeError" in unchanged


def test_transform_content_pipeline() -> None:
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

    # Strip unimported json branch
    stripped, c = transform_content(
        "except (RuntimeError, ValueError, OSError, FileNotFoundError, json.JSONDecodeError, KeyError, IndexError, TypeError) as e:\n    pass\n",
        add_json_import=False,
        strip_unimported_json=True,
    )
    assert c == 1
    assert "json.JSONDecodeError" not in stripped


def test_fix_file_dry_run_and_backup(tmp_path: Path) -> None:
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

    # Unmodified file
    res_clean = fix_file(target, dry_run=False)
    assert res_clean.modified is False
    assert res_clean.changes_count == 0


def test_fix_file_non_existent() -> None:
    res = fix_file(Path("/non/existent/path/file.py"))
    assert res.modified is False
    assert res.error is not None
    assert "File not found" in res.error


def test_fix_file_initial_syntax_error(tmp_path: Path) -> None:
    target = tmp_path / "syntax_err.py"
    target.write_text("def broken(:\n    try:\n        pass\n    except:\n        pass\n", encoding="utf-8")
    res = fix_file(target, dry_run=False)
    assert res.modified is True


def test_should_exclude_path() -> None:
    p1 = Path("D:/repo/__pycache__/compiled.py")
    p2 = Path("D:/repo/.git/config.py")
    p3 = Path("D:/repo/scratch/temp.py")
    p4 = Path("D:/repo/core/module.py")

    assert should_exclude_path(p1, DEFAULT_EXCLUDE_DIRS) is True
    assert should_exclude_path(p2, DEFAULT_EXCLUDE_DIRS) is True
    assert should_exclude_path(p3, DEFAULT_EXCLUDE_DIRS) is True
    assert should_exclude_path(p4, DEFAULT_EXCLUDE_DIRS) is False


def test_scan_and_fix_repo(tmp_path: Path) -> None:
    repo = tmp_path / "mock_repo"
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


def test_scan_and_fix_repo_single_file(tmp_path: Path) -> None:
    target = tmp_path / "single.py"
    target.write_text("try:\n    pass\nexcept:\n    pass\n", encoding="utf-8")

    summary = scan_and_fix_repo(target, dry_run=False)
    assert summary.total_found == 1
    assert summary.scanned == 1
    assert summary.modified == 1
    assert summary.errors == 0


def test_scan_and_fix_repo_non_existent(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist"
    summary = scan_and_fix_repo(missing)
    assert summary.errors == 1
    assert summary.has_errors is True
    report = summary.format_report()
    assert "Errors:" in report


def test_repo_fix_summary_formatting() -> None:
    mod_path = Path("/test/dir/mod.py")
    err_path = Path("/test/dir/err.py")
    summary = RepoFixSummary(root_dir=Path("/test/dir"))
    summary.errors = 1
    summary.modified = 1
    summary.results.append(
        FileFixResult(path=mod_path, modified=True, changes_count=3)
    )
    summary.results.append(
        FileFixResult(path=err_path, error="Disk read error")
    )
    report = summary.format_report()
    assert "Modified files:" in report
    assert f"{mod_path} (3 changes)" in report
    assert "Errors:" in report
    assert f"{err_path}: Disk read error" in report


def test_cli_main(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "test_cli.py"
    target.write_text("try:\n    pass\nexcept:\n    pass\n", encoding="utf-8")

    exit_code = main(["--file", str(target), "--dry-run"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Files modified:           1" in captured.out

    # Non existent path
    exit_fail = main(["--file", str(tmp_path / "non_existent.py")])
    assert exit_fail == 1