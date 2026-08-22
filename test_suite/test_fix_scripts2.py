"""
Unit and integration tests for fix_scripts2.py
"""

from __future__ import annotations

from pathlib import Path
import pytest

from fix_scripts2 import (
    DEFAULT_EXCLUDE_DIRS,
    FileFixResult,
    RepoFixSummary,
    add_pathlib_import_to_content,
    build_parser,
    fix_artifact_backslash_strings,
    fix_file,
    fix_hardcoded_cochem_paths,
    fix_nested_path_constructs,
    fix_os_path_joins,
    fix_path_slash_operands,
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


def test_fix_artifact_backslash_strings():
    code1 = 'art = str(Path(__file__).resolve().parent\\\\tests\\test_antigravity.py")'
    fixed1, c1 = fix_artifact_backslash_strings(code1)
    assert c1 == 1
    assert fixed1 == 'art = str(Path(__file__).resolve().parent / "tests/test_antigravity.py")'

    code2 = 'art = str(Path(__file__).resolve().parent\\data\\config.json")'
    fixed2, c2 = fix_artifact_backslash_strings(code2)
    assert c2 == 1
    assert fixed2 == 'art = str(Path(__file__).resolve().parent / "data/config.json")'


def test_fix_path_slash_operands():
    code1 = 'p = Path(__file__).resolve().parent / "tests\\sub\\test_demo.py"'
    fixed1, c1 = fix_path_slash_operands(code1)
    assert c1 == 1
    assert fixed1 == 'p = Path(__file__).resolve().parent / "tests/sub/test_demo.py"'

    code2 = "p = Path(__file__).resolve().parent / 'data\\raw\\matrix.dat'"
    fixed2, c2 = fix_path_slash_operands(code2)
    assert c2 == 1
    assert fixed2 == "p = Path(__file__).resolve().parent / 'data/raw/matrix.dat'"

    clean = 'p = Path(__file__).resolve().parent / "already/clean/path.py"'
    fixed_clean, c_clean = fix_path_slash_operands(clean)
    assert c_clean == 0
    assert fixed_clean == clean


def test_fix_os_path_joins():
    code1 = 'p = os.path.join(Path(__file__).resolve().parent, "data/file.txt")'
    fixed1, c1 = fix_os_path_joins(code1)
    assert c1 == 1
    assert fixed1 == 'p = Path(__file__).resolve().parent / "data/file.txt"'

    code2 = 'p = os.path.join(os.path.dirname(__file__), "configs\\settings.json")'
    fixed2, c2 = fix_os_path_joins(code2)
    assert c2 == 1
    assert fixed2 == 'p = Path(__file__).resolve().parent / "configs/settings.json"'

    code3 = 'p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "module.py")'
    fixed3, c3 = fix_os_path_joins(code3)
    assert c3 == 1
    assert fixed3 == 'p = Path(__file__).resolve().parent / "module.py"'


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


def test_fix_swarm_state_paths():
    code = 'state_file = Path("swarm_state.json")'
    fixed, count = fix_swarm_state_paths(code)
    assert count == 1
    assert fixed == 'state_file = Path(__file__).resolve().parent / "swarm_state.json"'


def test_transform_content_pipeline():
    sample = (
        '"""State updater v2."""\n'
        'import json\n\n'
        'state_file = Path(r"(Path(__file__).resolve().parent / \"swarm_state.json\")")\n'
        'art1 = str(Path(__file__).resolve().parent\\\\tests\\test_runner.py")\n'
        'art2 = Path(__file__).resolve().parent / "tests\\sub\\test_unit.py"\n'
        'art3 = os.path.join(Path(__file__).resolve().parent, "data/output.csv")\n'
    )
    transformed, changes = transform_content(sample, auto_import_pathlib=True)
    assert changes >= 3
    assert "from pathlib import Path" in transformed
    assert 'state_file = Path(__file__).resolve().parent / "swarm_state.json"' in transformed
    assert 'str(Path(__file__).resolve().parent / "tests/test_runner.py")' in transformed
    assert 'Path(__file__).resolve().parent / "tests/sub/test_unit.py"' in transformed
    assert 'Path(__file__).resolve().parent / "data/output.csv"' in transformed

    valid, err = validate_python_syntax(transformed)
    assert valid is True, f"Syntax error: {err}"


def test_fix_file_dry_run_and_backup(tmp_path: Path):
    target = tmp_path / "update_swarm_state_02.py"
    initial_content = 'state_file = Path("swarm_state.json")\n'
    target.write_text(initial_content, encoding="utf-8")

    res_dry = fix_file(target, dry_run=True)
    assert res_dry.modified is True
    assert res_dry.changes_count >= 1
    assert target.read_text(encoding="utf-8") == initial_content

    res_live = fix_file(target, dry_run=False, backup=True)
    assert res_live.modified is True
    assert 'Path(__file__).resolve().parent / "swarm_state.json"' in target.read_text(encoding="utf-8")
    assert (tmp_path / "update_swarm_state_02.py.bak").exists()
    assert (tmp_path / "update_swarm_state_02.py.bak").read_text(encoding="utf-8") == initial_content


def test_fix_file_non_existent():
    res = fix_file(Path("/non/existent/path/file2.py"))
    assert res.modified is False
    assert res.error is not None
    assert "File not found" in res.error


def test_fix_file_initial_syntax_error(tmp_path: Path):
    target = tmp_path / "broken2.py"
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
    repo = tmp_path / "mock_repo2"
    repo.mkdir()
    (repo / "__pycache__").mkdir()

    f1 = repo / "update_swarm_state_test2.py"
    f1.write_text('state_file = Path("swarm_state.json")\n', encoding="utf-8")

    f2 = repo / "__pycache__" / "update_swarm_state_cached2.py"
    f2.write_text('state_file = Path("swarm_state.json")\n', encoding="utf-8")

    summary = scan_and_fix_repo(repo, glob_pattern="update_swarm_state*.py", dry_run=False)
    assert summary.total_found == 1
    assert summary.scanned == 1
    assert summary.modified == 1
    assert summary.skipped == 0
    assert summary.errors == 0
    assert summary.has_errors is False

    report = summary.format_report()
    assert "Fix Scripts 2 Summary" in report
    assert "Files modified:           1" in report


def test_cli_main(tmp_path: Path, capsys):
    target = tmp_path / "update_swarm_state_cli2.py"
    target.write_text('state_file = Path("swarm_state.json")\n', encoding="utf-8")

    exit_code = main(["--file", str(target), "--dry-run"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Files modified:           1" in captured.out

    exit_code_no_swarm = main(["--file", str(target), "--no-fix-swarm-state", "--dry-run"])
    assert exit_code_no_swarm == 0