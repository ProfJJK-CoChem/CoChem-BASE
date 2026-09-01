"""Comprehensive physical Zero-Mock test suite for tests/__init__.py.

Validates root discovery anchors, getter utilities, dynamic test module listing,
test suite namespace grouping, environment telemetry, and export integrity conforming to
SRS Document 10 §2, Method Matrix v4, and CoChem Anti-Spoofing Protocol v3.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

import tests
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def tests_init_path() -> Path:
    """Return the absolute path to tests/__init__.py."""
    path = Path(__file__).resolve().parent / "__init__.py"
    if not path.is_file():
        path = Path(__file__).resolve().parent.parent / "tests" / "__init__.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_encoding_and_lf_line_endings(tests_init_path: Path) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    raw = tests_init_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in tests/__init__.py"
    assert b"\n" in raw, "Missing newline characters in tests/__init__.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in tests/__init__.py"

    content = tests_init_path.read_text(encoding="utf-8")
    assert len(content) > 200, "File content is unexpectedly small."


def test_zero_personal_path_leaks(tests_init_path: Path) -> None:
    """Verify zero personal machine or local user path leakage in tests/__init__.py."""
    lines = tests_init_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks: List[tuple[int, str, str]] = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in tests/__init__.py: {leaks}"


def test_docstring_and_provenance_tags(tests_init_path: Path) -> None:
    """Verify comprehensive architectural docstring with [M], [D], [E] provenance tags."""
    doc = tests.__doc__
    assert doc is not None and len(doc) > 100
    assert "[M]" in doc
    assert "[D]" in doc
    assert "[E]" in doc
    assert "SRS Document 10 §2" in doc
    assert "Method Matrix v4" in doc


def test_constants_and_anchors() -> None:
    """Verify standardized path constants resolve correctly."""
    assert isinstance(tests.TESTS_ROOT, Path)
    assert tests.TESTS_ROOT.is_dir()
    assert tests.TESTS_ROOT.name == "tests"

    assert isinstance(tests.REPO_ROOT, Path)
    assert tests.REPO_ROOT.is_dir()
    assert tests.REPO_ROOT == tests.TESTS_ROOT.parent

    assert isinstance(tests.FIXTURES_DIR, Path)
    assert tests.FIXTURES_DIR == tests.TESTS_ROOT / "fixtures"

    assert isinstance(tests.INTEGRATION_DIR, Path)
    assert tests.INTEGRATION_DIR == tests.TESTS_ROOT / "integration"

    assert isinstance(tests.MODELS_TEST_DIR, Path)
    assert tests.MODELS_TEST_DIR == tests.TESTS_ROOT / "test_models"


def test_path_getter_functions() -> None:
    """Verify getter functions return the expected Path objects."""
    assert tests.get_tests_root() == tests.TESTS_ROOT
    assert tests.get_repo_root() == tests.REPO_ROOT
    assert tests.get_fixtures_dir() == tests.FIXTURES_DIR
    assert tests.get_integration_dir() == tests.INTEGRATION_DIR
    assert tests.get_models_test_dir() == tests.MODELS_TEST_DIR


def test_list_available_test_modules_root() -> None:
    """Verify dynamic discovery of root test modules."""
    root_modules = tests.list_available_test_modules(None)
    assert isinstance(root_modules, list)
    assert len(root_modules) > 0
    assert root_modules == sorted(root_modules)
    for mod in root_modules:
        assert mod.startswith("test_")
        assert mod.endswith(".py")
        assert (tests.TESTS_ROOT / mod).is_file()


def test_list_available_test_modules_subpackages() -> None:
    """Verify dynamic discovery of subpackage test modules."""
    if tests.INTEGRATION_DIR.is_dir():
        integration_modules = tests.list_available_test_modules("integration")
        assert isinstance(integration_modules, list)
        assert integration_modules == sorted(integration_modules)
        for mod in integration_modules:
            assert mod.startswith("test_")
            assert mod.endswith(".py")
            assert (tests.INTEGRATION_DIR / mod).is_file()

    if tests.MODELS_TEST_DIR.is_dir():
        model_modules = tests.list_available_test_modules("test_models")
        assert isinstance(model_modules, list)
        assert model_modules == sorted(model_modules)
        for mod in model_modules:
            assert mod.startswith("test_")
            assert mod.endswith(".py")
            assert (tests.MODELS_TEST_DIR / mod).is_file()


def test_list_available_test_modules_nonexistent() -> None:
    """Verify passing a nonexistent subpackage returns an empty list."""
    res = tests.list_available_test_modules("nonexistent_directory_xyz123")
    assert res == []


def test_discover_all_test_suites() -> None:
    """Verify recursive test suite discovery and namespace grouping."""
    suites = tests.discover_all_test_suites()
    assert isinstance(suites, dict)
    assert "root" in suites
    assert isinstance(suites["root"], list)
    assert len(suites["root"]) > 0

    if tests.INTEGRATION_DIR.is_dir():
        assert "integration" in suites
        assert suites["integration"] == tests.list_available_test_modules("integration")

    if tests.MODELS_TEST_DIR.is_dir():
        assert "test_models" in suites
        assert suites["test_models"] == tests.list_available_test_modules("test_models")


def test_get_test_environment_metadata() -> None:
    """Verify host environment metadata extraction."""
    meta = tests.get_test_environment_metadata()
    assert isinstance(meta, dict)
    assert meta["python_version"] == sys.version
    assert meta["platform"] == sys.platform
    assert meta["tests_root"] == str(tests.TESTS_ROOT)
    assert meta["repo_root"] == str(tests.REPO_ROOT)
    assert isinstance(meta["headless"], bool)


def test_get_test_environment_metadata_headless_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify environment metadata correctly reflects COCHEM_HEADLESS setting."""
    monkeypatch.setenv("COCHEM_HEADLESS", "0")
    meta_gui = tests.get_test_environment_metadata()
    assert meta_gui["headless"] is False

    monkeypatch.setenv("COCHEM_HEADLESS", "1")
    meta_headless = tests.get_test_environment_metadata()
    assert meta_headless["headless"] is True


def test_all_exports_integrity() -> None:
    """Verify all symbols in __all__ are defined and match module attributes."""
    assert hasattr(tests, "__all__")
    assert isinstance(tests.__all__, list)

    expected_symbols = [
        "__version__",
        "__author__",
        "__license__",
        "TESTS_ROOT",
        "REPO_ROOT",
        "FIXTURES_DIR",
        "INTEGRATION_DIR",
        "MODELS_TEST_DIR",
        "get_tests_root",
        "get_repo_root",
        "get_fixtures_dir",
        "get_integration_dir",
        "get_models_test_dir",
        "list_available_test_modules",
        "discover_all_test_suites",
        "get_test_environment_metadata",
    ]

    for sym in expected_symbols:
        assert sym in tests.__all__, f"Symbol '{sym}' missing from tests.__all__"
        assert hasattr(tests, sym), f"Symbol '{sym}' listed in __all__ but not defined on module"

    assert isinstance(tests.__version__, str)
    assert isinstance(tests.__author__, str)
    assert isinstance(tests.__license__, str)
