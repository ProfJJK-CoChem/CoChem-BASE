"""Physical Zero-Mock Test Suite for generate_blueprint.py.

Verifies strict line endings, UTF-8 encoding, zero personal path leakage,
CLI functionality, exclusion filtering, deterministic file discovery,
and blueprint markdown generation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import generate_blueprint as gb
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def target_file() -> Path:
    target = Path(__file__).resolve().parent.parent / "generate_blueprint.py"
    assert target.exists(), f"Target file does not exist at {target}"
    return target


def test_file_exists_and_non_empty(target_file: Path) -> None:
    """Verify that generate_blueprint.py exists and has substantive content."""
    stat = target_file.stat()
    assert stat.st_size > 500, f"File size too small ({stat.st_size} bytes)"


def test_unix_lf_line_endings(target_file: Path) -> None:
    """Verify strictly Unix LF line endings (\\n) and no CRLF (\\r\\n)."""
    with open(target_file, "rb") as f:
        raw = f.read()
    assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in generate_blueprint.py"
    assert b"\n" in raw, "Missing newline characters"


def test_utf8_encoding_no_bom(target_file: Path) -> None:
    """Verify standard UTF-8 encoding without Byte Order Mark."""
    with open(target_file, "rb") as f:
        header = f.read(3)
    assert header != b"\xef\xbb\xbf", "Found UTF-8 BOM marker in generate_blueprint.py"

    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert len(content) > 0


def test_zero_personal_path_leaks(target_file: Path) -> None:
    """Verify zero personal/machine path leakage across the entire file."""
    with open(target_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    leaks = []
    patterns = leak_patterns()
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s): {leaks}"


def test_default_excludes_structure() -> None:
    """Verify DEFAULT_EXCLUDES contains essential ignored patterns."""
    assert ".git" in gb.DEFAULT_EXCLUDES
    assert "__pycache__" in gb.DEFAULT_EXCLUDES
    assert "*.pyc" in gb.DEFAULT_EXCLUDES
    assert "*.log" in gb.DEFAULT_EXCLUDES
    assert ".venv" in gb.DEFAULT_EXCLUDES
    assert ".trash" in gb.DEFAULT_EXCLUDES


def test_match_exclude_patterns() -> None:
    """Test exclusion matching logic for filenames, directory parts, and globs."""
    assert gb.match_exclude(Path("repo/.git/config"))
    assert gb.match_exclude(Path("repo/module/__pycache__/core.cpython-314.pyc"))
    assert gb.match_exclude(Path("repo/debug.log"))
    assert gb.match_exclude(Path("repo/poetry.lock"))
    assert gb.match_exclude(Path("repo/.trash/old_file.py"))
    assert gb.match_exclude(Path("repo/.venv/bin/activate"))

    # Non-excluded files
    assert not gb.match_exclude(Path("repo/cochem_base/core.py"))
    assert not gb.match_exclude(Path("repo/README.md"))
    assert not gb.match_exclude(Path("repo/setup.py"))


def test_match_exclude_custom_patterns() -> None:
    """Test custom exclude overrides."""
    custom = ["*.csv", "temp_*"]
    assert gb.match_exclude(Path("repo/data.csv"), excludes=custom)
    assert gb.match_exclude(Path("repo/temp_test.py"), excludes=custom)
    assert not gb.match_exclude(Path("repo/data.json"), excludes=custom)


def test_discover_files_in_temp_tree(tmp_path: Path) -> None:
    """Verify discovering files recursively with deterministic sorting."""
    # Create test directory structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("print('a')", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("print('b')", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Guide", encoding="utf-8")

    # Excluded files
    (tmp_path / "src" / "__pycache__").mkdir()
    (tmp_path / "src" / "__pycache__" / "a.cpython-314.pyc").write_text("bytecode", encoding="utf-8")
    (tmp_path / "test.log").write_text("log data", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref", encoding="utf-8")

    discovered = gb.discover_files(tmp_path)
    discovered_names = [p.name for p in discovered]

    assert "a.py" in discovered_names
    assert "b.py" in discovered_names
    assert "guide.md" in discovered_names
    assert "a.cpython-314.pyc" not in discovered_names
    assert "test.log" not in discovered_names
    assert "HEAD" not in discovered_names
    assert len(discovered) == 3


def test_discover_files_with_extension_filter(tmp_path: Path) -> None:
    """Verify include_extensions filtering."""
    (tmp_path / "script.py").write_text("pass", encoding="utf-8")
    (tmp_path / "doc.md").write_text("# Doc", encoding="utf-8")
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")

    py_only = gb.discover_files(tmp_path, include_extensions=[".py"])
    assert len(py_only) == 1
    assert py_only[0].name == "script.py"

    multi_ext = gb.discover_files(tmp_path, include_extensions=["py", "md"])
    assert len(multi_ext) == 2
    assert {p.name for p in multi_ext} == {"script.py", "doc.md"}


def test_discover_files_error_handling(tmp_path: Path) -> None:
    """Verify FileNotFoundError and NotADirectoryError handling."""
    with pytest.raises(FileNotFoundError):
        gb.discover_files(tmp_path / "non_existent_folder")

    dummy_file = tmp_path / "file.txt"
    dummy_file.write_text("content", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        gb.discover_files(dummy_file)


def test_format_blueprint_entry(tmp_path: Path) -> None:
    """Test checklist formatting for absolute and relative paths."""
    sample = tmp_path / "src" / "mod.py"
    abs_line = gb.format_blueprint_entry(sample)
    assert abs_line == f"- [ ] {sample.resolve()}\n"

    rel_line = gb.format_blueprint_entry(sample, relative_to=tmp_path)
    assert rel_line == f"- [ ] {Path('src') / 'mod.py'}\n"


def test_generate_blueprint(tmp_path: Path) -> None:
    """Test full generate_blueprint file creation and content."""
    sub = tmp_path / "project"
    sub.mkdir()
    (sub / "main.py").write_text("main", encoding="utf-8")
    (sub / "util.py").write_text("util", encoding="utf-8")

    output_file = tmp_path / "output" / "blueprint.md"
    out_path, count = gb.generate_blueprint(
        repo_path=sub,
        output_path=output_file,
    )

    assert out_path == output_file.resolve()
    assert count == 2
    assert output_file.exists()

    content = output_file.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    assert len(lines) == 2
    for line in lines:
        assert line.startswith("- [ ] ")


def test_generate_blueprint_relative(tmp_path: Path) -> None:
    """Test generate_blueprint with relative=True."""
    sub = tmp_path / "project"
    sub.mkdir()
    (sub / "nested").mkdir()
    (sub / "nested" / "mod.py").write_text("pass", encoding="utf-8")

    out_path, count = gb.generate_blueprint(
        repo_path=sub,
        relative=True,
    )

    assert count == 1
    content = out_path.read_text(encoding="utf-8")
    expected_rel = str(Path("nested") / "mod.py")
    assert f"- [ ] {expected_rel}" in content


def test_cli_parsing_and_main(tmp_path: Path) -> None:
    """Test CLI argument parsing and main() execution."""
    test_dir = tmp_path / "repo"
    test_dir.mkdir()
    (test_dir / "index.py").write_text("print('index')", encoding="utf-8")

    out_file = tmp_path / "test_blueprint.md"

    # Test main with valid arguments
    exit_code = gb.main([
        "--repo-dir", str(test_dir),
        "--output", str(out_file),
        "--quiet",
    ])
    assert exit_code == 0
    assert out_file.exists()

    # Test main with invalid directory
    exit_code_invalid = gb.main([
        "--repo-dir", str(tmp_path / "invalid_dir"),
        "--quiet",
    ])
    assert exit_code_invalid == 1


def test_subprocess_cli_execution(tmp_path: Path) -> None:
    """Test real subprocess execution of generate_blueprint.py."""
    target_script = Path(__file__).resolve().parent.parent / "generate_blueprint.py"

    test_dir = tmp_path / "sub_repo"
    test_dir.mkdir()
    (test_dir / "app.py").write_text("app", encoding="utf-8")
    out_file = tmp_path / "cli_blueprint.md"

    cmd = [
        sys.executable,
        str(target_script),
        "--repo-dir", str(test_dir),
        "--output", str(out_file),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0
    assert "Discovered 1 file(s)" in result.stdout
    assert out_file.exists()
