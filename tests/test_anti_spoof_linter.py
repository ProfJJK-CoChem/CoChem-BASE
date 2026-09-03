"""Physical unit tests for CoChem Anti-Spoofing Linter (ci_tools/anti_spoof_linter.py).

Zero-Mock Mandate Compliance:
- Real test files created in tmp_path.
- Tests verify AST inspection, banned imports, and stubs.
"""

from __future__ import annotations

from pathlib import Path

from ci_tools.anti_spoof_linter import (
    BANNED_CONCURRENCY_MODULES,
    BANNED_MOCK_MODULES,
    EXCLUDED_DIRS,
    check_file,
    load_amnesty,
    run_linter,
)


def test_excluded_dirs() -> None:
    assert ".git" in EXCLUDED_DIRS
    assert "__pycache__" in EXCLUDED_DIRS
    assert ".pytest_cache" in EXCLUDED_DIRS


def test_detect_banned_imports(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_import.py"
    bad_script.write_text("import parsl\nimport dask\n", encoding="utf-8")
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any("parsl" in v.symbol for v in violations)
    assert any("dask" in v.symbol for v in violations)


def test_detect_mock_modules(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_mock.py"
    bad_script.write_text("import mock\n", encoding="utf-8")
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any("mock" in v.symbol for v in violations)


def test_detect_pass_stub(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_stub.py"
    bad_script.write_text("def solve():\n    pass\n", encoding="utf-8")
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any("pass" in v.message.lower() for v in violations)


def test_detect_not_implemented_error(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_raise.py"
    bad_script.write_text(
        "def compute():\n    raise NotImplementedError('Not done')\n",
        encoding="utf-8",
    )
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any(v.category == "NOT_IMPLEMENTED_ERROR" for v in violations)


def test_detect_banned_identifier(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_ident.py"
    bad_script.write_text("def run():\n    dummy_var = 123\n", encoding="utf-8")
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any(v.category == "BANNED_IDENTIFIER" for v in violations)


def test_clean_script_passes(tmp_path: Path) -> None:
    clean_script = tmp_path / "clean_module.py"
    clean_script.write_text(
        "def compute_energy(x: float) -> float:\n    return x * 2.5\n",
        encoding="utf-8",
    )
    violations = check_file(clean_script, tmp_path, amnesty_set=set())
    assert len(violations) == 0


def test_run_linter_directory(tmp_path: Path) -> None:
    sub_dir = tmp_path / "clean_dir"
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / "clean_mod.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )
    exit_code, violations = run_linter(
        targets=[sub_dir], repo_root=sub_dir, strict_mode=True
    )
    assert exit_code == 0
    assert len(violations) == 0


def test_amnesty_bypass(tmp_path: Path) -> None:
    conc_script = tmp_path / "conc_worker.py"
    conc_script.write_text("import parsl\n", encoding="utf-8")
    # Without amnesty, it fails
    v_un = check_file(conc_script, tmp_path, amnesty_set=set())
    assert len(v_un) > 0
    # With amnesty, it passes
    v_am = check_file(conc_script, tmp_path, amnesty_set={"conc_worker.py"})
    assert len(v_am) == 0
