import os
import tempfile
from pathlib import Path
from ci_tools.anti_spoof_linter import (
    is_file_exempt,
    load_amnesty_list,
    check_script,
    run_linter,
    EXCLUDED_DIRS,
    BANNED_PARALLEL_IMPORTS,
    BANNED_MOCK_IMPORTS,
)


def test_is_file_exempt() -> None:
    amnesty = {"tests/test_foo.py", "mock"}
    assert is_file_exempt(Path("tests/test_foo.py"), amnesty) is True
    assert is_file_exempt(Path("tests/test_bar.py"), amnesty) is False
    assert is_file_exempt(Path("src/mock_engine.py"), amnesty) is True
    assert is_file_exempt(Path(".docs/improvements/proposal.md"), amnesty) is True
    assert is_file_exempt(Path("ci_tools/anti_spoof_linter.py"), amnesty) is True


def test_excluded_dirs() -> None:
    assert ".git" in EXCLUDED_DIRS
    assert "__pycache__" in EXCLUDED_DIRS
    assert ".pytest_cache" in EXCLUDED_DIRS


def test_detect_banned_imports(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_import.py"
    bad_script.write_text("import parsl\nimport dask\n", encoding="utf-8")
    violations = check_script(bad_script, strict_mode=False)
    assert any("parsl" in v for v in violations)
    assert any("dask" in v for v in violations)


def test_detect_mock_modules(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_mock.py"
    bad_script.write_text("import mock\n", encoding="utf-8")
    violations = check_script(bad_script, strict_mode=False)
    assert any("mock" in v for v in violations)


def test_detect_pass_stub(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_stub.py"
    bad_script.write_text("def solve():\n    pass\n", encoding="utf-8")
    violations = check_script(bad_script, strict_mode=True)
    assert any("Unimplemented 'pass' stub" in v for v in violations)


def test_detect_not_implemented_error(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_raise.py"
    bad_script.write_text("def compute():\n    raise NotImplementedError('Not done')\n", encoding="utf-8")
    violations = check_script(bad_script, strict_mode=True)
    assert any("NotImplementedError" in v for v in violations)


def test_detect_synthetic_dummy_loop(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_loop.py"
    bad_script.write_text("for i in range(10):\n    pass\n", encoding="utf-8")
    violations = check_script(bad_script, strict_mode=False)
    assert any("Synthetic dummy loop" in v for v in violations)


def test_clean_script_passes(tmp_path: Path) -> None:
    clean_script = tmp_path / "clean_module.py"
    clean_script.write_text(
        "def compute_energy(x: float) -> float:\n    return x * 2.5\n",
        encoding="utf-8",
    )
    violations = check_script(clean_script, strict_mode=True)
    assert len(violations) == 0
