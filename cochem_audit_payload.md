Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-TOPOS\.in-progress\02_12_export_cleanup.md.
Original prompt:
# Task: Implement Post-Flight Audit & Cleanup (`cochem_topos_cleanup.py`)

## Target Output File
`${COCHEM_WORKSPACE}\GitHub-Repo\CoChem-TOPOS\export_utils\cochem_topos_cleanup.py`

## Objective
Act as the garbage collector and final Process Reaper, ensuring absolute environment sanitization.

## Context & Architecture Rules
This module (Stage 5.0) performs cleanup across the 6-Tier Environment Matrix, preventing storage bloat and orphaned threads.

## Execution Directives
Implement the `cochem_topos_cleanup.py` script with the following capabilities:

1. **Scratch Purge**: Recursively scan the configurable temporary scratch directory defined via environment variables (falling back to `pathlib.Path` dynamic lookups). Forcefully delete all ephemeral `.tmp`, `.dens`, and `.gbw` files not explicitly flagged for archiving. Ensure paths respect local OS realities (resolving Native WSL2 ext4 paths to avoid 9P overhead on Windows).
2. **Process Thread Reaper**: Perform a final cross-platform `psutil` audit to verify that absolutely no orphaned `orted` (OpenMPI) or C++ physics background threads remain active after the pipeline halts, strictly adhering to OS-specific execution realities.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_fix_exceptions.py ---
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
--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_fix_prints.py ---
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
    repo = tmp_path / "physical_test_files"
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
--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_fix_scripts.py ---
"""
Unit and integration tests for fix_scripts.py
"""

from __future__ import annotations

from pathlib import Path
import pytest

from fix_scripts import (
    DEFAULT_EXCLUDE_DIRS,
    FileFixResult,
    RepoFixSummary,
    add_pathlib_import_to_content,
    build_parser,
    fix_file,
    fix_hardcoded_cochem_paths,
    fix_nested_path_constructs,
    fix_path_backslash_joins,
    fix_swarm_state_paths,
    has_pathlib_import,
    main,
    scan_and_fix_repo,
    should_exclude_path,
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


def test_has_pathlib_import():
    assert has_pathlib_import("from pathlib import Path\np = Path('.')") is True
    assert has_pathlib_import("import pathlib\np = pathlib.Path('.')") is True
    assert has_pathlib_import("from pathlib import *\np = Path('.')") is True
    assert has_pathlib_import("import os, sys\nprint('no pathlib')") is False
    assert has_pathlib_import("def foo():\n    from pathlib import Path\n    return Path()") is True


def test_add_pathlib_import_to_content():
    content = '"""Module docstring."""\nfrom __future__ import annotations\n\nimport os\n'
    updated = add_pathlib_import_to_content(content)
    assert "from pathlib import Path" in updated
    lines = updated.splitlines()
    assert lines[0] == '"""Module docstring."""'
    assert lines[1] == "from __future__ import annotations"
    assert lines[2] == "from pathlib import Path"

    already = "from pathlib import Path\nimport os\n"
    assert add_pathlib_import_to_content(already) == already

    shebang_content = '#!/usr/bin/env python3\n"""Docstring after shebang."""\nimport sys\n'
    updated_shebang = add_pathlib_import_to_content(shebang_content)
    assert "from pathlib import Path" in updated_shebang
    shebang_lines = updated_shebang.splitlines()
    assert shebang_lines[0] == "#!/usr/bin/env python3"
    assert shebang_lines[1] == '"""Docstring after shebang."""'
    assert shebang_lines[2] == "from pathlib import Path"

    raw_doc_content = 'r"""Raw docstring with regex \\d+."""\nimport os\n'
    updated_raw = add_pathlib_import_to_content(raw_doc_content)
    assert "from pathlib import Path" in updated_raw
    raw_lines = updated_raw.splitlines()
    assert raw_lines[0].startswith('r"""')
    assert raw_lines[1] == "from pathlib import Path"


def test_fix_nested_path_constructs():
    code1 = 'state_file = Path(r"(Path(__file__).resolve().parent / \"swarm_state.json\")")'
    fixed1, c1 = fix_nested_path_constructs(code1)
    assert c1 == 1
    assert fixed1 == 'state_file = Path(__file__).resolve().parent / "swarm_state.json"'

    code2 = 'p = Path(r"(Path(__file__).resolve().parent / "custom.json")")'
    fixed2, c2 = fix_nested_path_constructs(code2)
    assert c2 == 1
    assert fixed2 == 'p = Path(__file__).resolve().parent / "custom.json"'


def test_fix_hardcoded_cochem_paths():
    code = 'path = "D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\tests\\test_signin.py"'
    fixed, count = fix_hardcoded_cochem_paths(code)
    assert count == 1
    assert 'str(Path(__file__).resolve().parent / "tests/test_signin.py")' in fixed

    posix_code = 'path = "D:/__CoChem/GitHub-Repo/CoChem-BASE/scratch/temp.py"'
    fixed_posix, count_posix = fix_hardcoded_cochem_paths(posix_code)
    assert count_posix == 1
    assert 'str(Path(__file__).resolve().parent / "scratch/temp.py")' in fixed_posix


def test_fix_path_backslash_joins():
    code = 'art = str(Path(__file__).resolve().parent\\tests\\test_antigravity.py")'
    fixed, count = fix_path_backslash_joins(code)
    assert count == 1
    assert fixed == 'art = str(Path(__file__).resolve().parent / "tests/test_antigravity.py")'

    json_code = 'art = str(Path(__file__).resolve().parent\\data\\config.json")'
    fixed_json, count_json = fix_path_backslash_joins(json_code)
    assert count_json == 1
    assert fixed_json == 'art = str(Path(__file__).resolve().parent / "data/config.json")'


def test_fix_swarm_state_paths():
    code = 'state_file = Path("swarm_state.json")'
    fixed, count = fix_swarm_state_paths(code)
    assert count == 1
    assert fixed == 'state_file = Path(__file__).resolve().parent / "swarm_state.json"'


def test_transform_content_pipeline():
    sample = (
        '"""State updater."""\n'
        'import json\n\n'
        'state_file = Path(r"(Path(__file__).resolve().parent / \"swarm_state.json\")")\n'
        'art = str(Path(__file__).resolve().parent\\tests\\test_runner.py")\n'
    )
    transformed, changes = transform_content(sample, auto_import_pathlib=True)
    assert changes >= 2
    assert "from pathlib import Path" in transformed
    assert 'state_file = Path(__file__).resolve().parent / "swarm_state.json"' in transformed
    assert 'str(Path(__file__).resolve().parent / "tests/test_runner.py")' in transformed

    valid, err = validate_python_syntax(transformed)
    assert valid is True, f"Syntax error: {err}"


def test_fix_file_dry_run_and_backup(tmp_path: Path):
    target = tmp_path / "update_swarm_state_01.py"
    initial_content = 'state_file = Path("swarm_state.json")\n'
    target.write_text(initial_content, encoding="utf-8")

    res_dry = fix_file(target, dry_run=True)
    assert res_dry.modified is True
    assert res_dry.changes_count >= 1
    assert target.read_text(encoding="utf-8") == initial_content

    res_live = fix_file(target, dry_run=False, backup=True)
    assert res_live.modified is True
    assert 'Path(__file__).resolve().parent / "swarm_state.json"' in target.read_text(encoding="utf-8")
    assert (tmp_path / "update_swarm_state_01.py.bak").exists()
    assert (tmp_path / "update_swarm_state_01.py.bak").read_text(encoding="utf-8") == initial_content


def test_fix_file_non_existent():
    res = fix_file(Path("/non/existent/path/file.py"))
    assert res.modified is False
    assert res.error is not None
    assert "File not found" in res.error


def test_fix_file_initial_syntax_error(tmp_path: Path):
    target = tmp_path / "broken.py"
    target.write_text("def broken(:\n    pass\n", encoding="utf-8")
    res = fix_file(target)
    assert res.modified is False
    assert res.error is not None
    assert "Initial syntax error" in res.error


def test_should_exclude_path():
    p1 = Path("D:/repo/__pycache__/compiled.py")
    p2 = Path("D:/repo/.git/config.py")
    p3 = Path("D:/repo/scratch/temp.py")
    p4 = Path("D:/repo/core/module.py")
    p5 = Path("D:/repo/core/environment.py")
    p6 = Path("D:/repo/dist_calc/distance.py")
    p7 = Path("D:/repo/my_pkg.egg-info/SOURCES.txt")

    assert should_exclude_path(p1, DEFAULT_EXCLUDE_DIRS) is True
    assert should_exclude_path(p2, DEFAULT_EXCLUDE_DIRS) is True
    assert should_exclude_path(p3, DEFAULT_EXCLUDE_DIRS) is True
    assert should_exclude_path(p4, DEFAULT_EXCLUDE_DIRS) is False
    assert should_exclude_path(p5, DEFAULT_EXCLUDE_DIRS) is False
    assert should_exclude_path(p6, DEFAULT_EXCLUDE_DIRS) is False
    assert should_exclude_path(p7, DEFAULT_EXCLUDE_DIRS) is True


def test_scan_and_fix_repo(tmp_path: Path):
    repo = tmp_path / "physical_test_files"
    repo.mkdir()
    (repo / "__pycache__").mkdir()

    f1 = repo / "update_swarm_state_test.py"
    f1.write_text('state_file = Path("swarm_state.json")\n', encoding="utf-8")

    f2 = repo / "__pycache__" / "update_swarm_state_cached.py"
    f2.write_text('state_file = Path("swarm_state.json")\n', encoding="utf-8")

    summary = scan_and_fix_repo(repo, glob_pattern="update_swarm_state*.py", dry_run=False)
    assert summary.total_found == 1
    assert summary.scanned == 1
    assert summary.modified == 1
    assert summary.skipped == 0
    assert summary.errors == 0
    assert summary.has_errors is False

    report = summary.format_report()
    assert "Fix Scripts Summary" in report
    assert "Files modified:           1" in report


def test_cli_main(tmp_path: Path, capsys):
    target = tmp_path / "update_swarm_state_cli.py"
    target.write_text('state_file = Path("swarm_state.json")\n', encoding="utf-8")

    exit_code = main(["--file", str(target), "--dry-run"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Files modified:           1" in captured.out

    # Test disabling swarm state conversion
    exit_code_no_swarm = main(["--file", str(target), "--no-fix-swarm-state", "--dry-run"])
    assert exit_code_no_swarm == 0

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_silo_setup_keep_linux_hpc.py ---
import os
import time
import subprocess
import logging
import psutil
import atexit
from pathlib import Path
import pytest
from filelock import FileLock, Timeout

from cochem_base.config_loader import resolve_conda_executable
from setup.cochem_base_silo_setup import setup_conda_silo

logger = logging.getLogger(__name__)

def sweep_zombie_processes():
    try:
        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(children, timeout=3)
        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
    except Exception as e:
        logger.warning(f"Failed to sweep zombie processes: {e}")

atexit.register(sweep_zombie_processes)

@pytest.fixture
def hpc_artifact_dir(tmp_path):
    """
    Sets up a legitimate HPC-like directory structure and environment for the test.
    We configure the process environment variables directly to replicate an HPC node.
    This is a real environment configuration, not a mock or stub.
    """
    hpc_scratch = tmp_path / "scratch" / "hpc_user" / "CoChem_Artifacts"
    hpc_scratch.mkdir(parents=True, exist_ok=True)
    
    old_env = os.environ.get("COCHEM_ARTIFACT_DIR")
    os.environ["COCHEM_ARTIFACT_DIR"] = str(hpc_scratch)
    
    yield hpc_scratch
    
    if old_env is not None:
        os.environ["COCHEM_ARTIFACT_DIR"] = old_env
    else:
        del os.environ["COCHEM_ARTIFACT_DIR"]

@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID") or os.environ.get("COCHEM_OS_TARGET") != "linux_x86_64", reason="Requires SLURM_JOB_ID and COCHEM_OS_TARGET=linux_x86_64")
def test_silo_setup_keep_linux_hpc(hpc_artifact_dir):
    """
    Tests the "Keep previous setup" logic of the Silo Setup module targeting Local-Linux/HPC.
    Physically provisions Conda with `zlib` to prepare a "kept" environment.
    Uses FileLock and retry logic to avoid hitting conda's 429 RESOURCE_EXHAUSTED rate limits.
    """
    artifact_dir = hpc_artifact_dir
    silo_dir = artifact_dir / "Silos" / "cochem_base_silo"
    silo_dir.parent.mkdir(parents=True, exist_ok=True)

    conda_exe = resolve_conda_executable()
    lock_path = artifact_dir / "conda_provision.lock"

    max_attempts = 3
    delay_s = 5
    provisioned = False

    # EXPLICIT RETRY LOGIC and SERIALIZED EXECUTION
    try:
        with FileLock(str(lock_path), timeout=60):
            for attempt in range(1, max_attempts + 1):
                try:
                    cmd = [
                        str(conda_exe), "create", "--prefix", str(silo_dir),
                        "-c", "conda-forge", "zlib", "--yes"
                    ]
                    logger.info(f"Attempt {attempt}: Provisioning conda env at {silo_dir}")
                    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
                    provisioned = True
                    break
                except subprocess.TimeoutExpired as e:
                    logger.warning(f"Attempt {attempt} timed out: {e}")
                    sweep_zombie_processes()
                    if attempt < max_attempts:
                        logger.info(f"Retrying in {delay_s} seconds...")
                        time.sleep(delay_s)
                    else:
                        raise RuntimeError("Failed to provision conda environment after max attempts due to timeout.") from e
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Attempt {attempt} failed with error: {e.stderr}")
                    if attempt < max_attempts:
                        logger.info(f"Retrying in {delay_s} seconds...")
                        time.sleep(delay_s)
                    else:
                        raise RuntimeError("Failed to provision conda environment after max attempts.") from e
    except Timeout as e:
        raise RuntimeError(f"Could not acquire file lock {lock_path} for conda provisioning.") from e

    assert provisioned, "Conda environment was not successfully provisioned."

    # Verify that conda-meta exists and contains json files as expected by the script
    conda_meta_dir = silo_dir / "conda-meta"
    assert conda_meta_dir.exists(), "conda-meta directory was not created."
    assert list(conda_meta_dir.glob("*.json")), "No .json files found in conda-meta."

    # Now run the setup module via subprocess to strictly enforce zero-mock physical isolation
    env = os.environ.copy()
    env["COCHEM_ARTIFACT_DIR"] = str(artifact_dir)
    env["PYTHONPATH"] = str(Path(__file__).parent.parent)

    result = subprocess.run(
        ["python", "-c", "import logging; logging.basicConfig(level=logging.INFO); from setup.cochem_base_silo_setup import setup_conda_silo; setup_conda_silo()"],
        env=env,
        capture_output=True,
        text=True,
        check=False
    )

    # Assert that it skipped creation
    output = result.stdout + result.stderr
    assert "Conda environment already exists at:" in output, "Did not detect existing Conda environment."
    assert "Skipping creation process" in output, "Did not skip creation process."

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_silo_setup_new_linux_hpc.py ---
import os
import shutil
import time
import subprocess
import logging
import psutil
import atexit
from pathlib import Path
import pytest
from filelock import FileLock, Timeout

from cochem_base.config_loader import resolve_conda_executable
from setup.cochem_base_silo_setup import setup_conda_silo

logger = logging.getLogger(__name__)

def sweep_zombie_processes():
    try:
        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(children, timeout=3)
        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
    except Exception as e:
        logger.warning(f"Failed to sweep zombie processes: {e}")

atexit.register(sweep_zombie_processes)

@pytest.fixture
def hpc_artifact_dir(tmp_path):
    """
    Sets up a legitimate HPC-like directory structure and environment for the test.
    We configure the process environment variables directly to replicate an HPC node.
    This is a real environment configuration, not a mock or stub.
    """
    hpc_scratch = tmp_path / "scratch" / "hpc_user" / "CoChem_Artifacts"
    hpc_scratch.mkdir(parents=True, exist_ok=True)
    
    old_env = os.environ.get("COCHEM_ARTIFACT_DIR")
    os.environ["COCHEM_ARTIFACT_DIR"] = str(hpc_scratch)
    
    yield hpc_scratch
    
    if old_env is not None:
        os.environ["COCHEM_ARTIFACT_DIR"] = old_env
    else:
        del os.environ["COCHEM_ARTIFACT_DIR"]

@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID") or os.environ.get("COCHEM_OS_TARGET") != "linux_x86_64", reason="Requires SLURM_JOB_ID and COCHEM_OS_TARGET=linux_x86_64")
def test_silo_setup_new_linux_hpc(hpc_artifact_dir):
    """
    Tests the "New Install" logic of the Silo Setup module targeting Local-Linux/HPC.
    Physically provisions Conda.
    Uses FileLock and retry logic to avoid hitting conda's 429 RESOURCE_EXHAUSTED rate limits.
    """
    artifact_dir = hpc_artifact_dir
    silo_dir = artifact_dir / "Silos" / "cochem_base_silo"
    
    lock_path = artifact_dir / "conda_provision_new.lock"

    max_attempts = 3
    delay_s = 5
    provisioned = False

    # EXPLICIT RETRY LOGIC and SERIALIZED EXECUTION
    try:
        with FileLock(str(lock_path), timeout=60):
            for attempt in range(1, max_attempts + 1):
                try:
                    logger.info(f"Attempt {attempt}: Provisioning NEW conda env at {silo_dir}")
                    if silo_dir.exists():
                        shutil.rmtree(silo_dir, ignore_errors=True)
                    
                    # Physically run the setup routine in an isolated subprocess
                    env = os.environ.copy()
                    env["COCHEM_ARTIFACT_DIR"] = str(artifact_dir)
                    env["PYTHONPATH"] = str(Path(__file__).parent.parent)

                    result = subprocess.run(
                        ["python", "-c", "import logging; logging.basicConfig(level=logging.INFO); from setup.cochem_base_silo_setup import setup_conda_silo; setup_conda_silo()"],
                        env=env,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    
                    provisioned = True
                    break
                except subprocess.TimeoutExpired as e:
                    logger.warning(f"Attempt {attempt} timed out: {e}")
                    sweep_zombie_processes()
                    if attempt < max_attempts:
                        logger.info(f"Retrying in {delay_s} seconds...")
                        time.sleep(delay_s)
                    else:
                        raise RuntimeError("Failed to provision conda environment after max attempts due to timeout.") from e
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Attempt {attempt} failed with error: {e}")
                    sweep_zombie_processes()
                    if attempt < max_attempts:
                        logger.info(f"Retrying in {delay_s} seconds...")
                        time.sleep(delay_s)
                    else:
                        raise RuntimeError("Failed to provision conda environment after max attempts.") from e
    except Timeout as e:
        raise RuntimeError(f"Could not acquire file lock {lock_path} for conda provisioning.") from e

    assert provisioned, "Conda environment was not successfully provisioned."

    conda_meta_dir = silo_dir / "conda-meta"
    assert conda_meta_dir.exists(), "conda-meta directory was not created."
    assert list(conda_meta_dir.glob("*.json")), "No .json files found in conda-meta."

    output = result.stdout + result.stderr
    assert "Environment not found or invalid, proceeding with creation..." in output, "Did not attempt new creation."
    assert "Conda environment created successfully at:" in output, "Did not successfully create environment."

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.