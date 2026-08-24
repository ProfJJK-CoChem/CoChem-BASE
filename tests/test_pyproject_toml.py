"""Comprehensive Zero-Mock Test Suite for CoChem-BASE pyproject.toml Configuration.

Defends build system integrity, package metadata, and developer tooling by validating:
- Physical file existence, UTF-8 encoding (no BOM), and strict Unix LF line endings.
- Valid TOML syntax parsing via standard tomllib (with tomli fallback).
- [build-system] table adhering to PEP 517 / PEP 518 specifications (setuptools.build_meta).
- [project] metadata table compliance: name ("CoChem-BASE"), requires-python (">=3.11").
- [tool.setuptools.packages.find] package discovery containing "cochem_base*".
- [tool.pytest.ini_options] test execution configuration with testpaths.
- [tool.ruff] linting and formatting configuration.
- [tool.mypy] strict static type checking and module overrides.
- Zero-mock policy and absence of placeholder / dummy / stub tokens.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict

import pytest

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


@pytest.fixture(scope="module")
def pyproject_raw_bytes() -> bytes:
    """Fixture providing raw bytes of pyproject.toml."""
    assert PYPROJECT_PATH.exists(), f"pyproject.toml does not exist at {PYPROJECT_PATH}"
    return PYPROJECT_PATH.read_bytes()


@pytest.fixture(scope="module")
def pyproject_content(pyproject_raw_bytes: bytes) -> str:
    """Fixture providing decoded string content of pyproject.toml."""
    return pyproject_raw_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def pyproject_data(pyproject_content: str) -> Dict[str, Any]:
    """Fixture providing parsed TOML dictionary."""
    data = tomllib.loads(pyproject_content)
    assert isinstance(data, dict), "Parsed TOML root must be a dictionary"
    return data


# ==============================================================================
# 1. Physical File Integrity & Line Endings
# ==============================================================================


def test_pyproject_file_exists() -> None:
    """Validate that pyproject.toml exists as a regular file in repository root."""
    assert PYPROJECT_PATH.exists(), f"pyproject.toml missing at {PYPROJECT_PATH}"
    assert PYPROJECT_PATH.is_file(), f"{PYPROJECT_PATH} must be a regular file"
    size = PYPROJECT_PATH.stat().st_size
    assert size > 50, f"pyproject.toml size too small ({size} bytes)"
    assert size < 50_000, f"pyproject.toml size unexpectedly large ({size} bytes)"


def test_pyproject_encoding_and_unix_lf_endings(pyproject_raw_bytes: bytes) -> None:
    """Validate strict UTF-8 without BOM and strict Unix LF line endings."""
    assert not pyproject_raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "pyproject.toml contains UTF-8 Byte Order Mark (BOM)"
    )
    assert b"\r\n" not in pyproject_raw_bytes, (
        "pyproject.toml contains Windows CRLF line endings; strictly Unix LF required"
    )
    assert b"\r" not in pyproject_raw_bytes, (
        "pyproject.toml contains CR line endings; strictly Unix LF required"
    )
    assert b"\n" in pyproject_raw_bytes, "pyproject.toml must contain Unix LF line endings"


# ==============================================================================
# 2. TOML Syntax & Top-Level Schema
# ==============================================================================


def test_pyproject_toml_syntax_validity(pyproject_data: Dict[str, Any]) -> None:
    """Validate that pyproject.toml parses cleanly into required top-level tables."""
    assert "build-system" in pyproject_data, "Missing [build-system] table in pyproject.toml"
    assert "project" in pyproject_data, "Missing [project] table in pyproject.toml"
    assert isinstance(pyproject_data["build-system"], dict), "[build-system] must be a table"
    assert isinstance(pyproject_data["project"], dict), "[project] must be a table"


# ==============================================================================
# 3. [build-system] Table Specifications
# ==============================================================================


def test_build_system_backend_and_requires(pyproject_data: Dict[str, Any]) -> None:
    """Validate PEP 517 / PEP 518 build-system backend and required build tools."""
    build_sys = pyproject_data["build-system"]
    assert "build-backend" in build_sys, "Missing 'build-backend' in [build-system]"
    assert build_sys["build-backend"] == "setuptools.build_meta", (
        f"Expected build-backend 'setuptools.build_meta', got '{build_sys.get('build-backend')}'"
    )

    assert "requires" in build_sys, "Missing 'requires' in [build-system]"
    requires = build_sys["requires"]
    assert isinstance(requires, list), "'requires' in [build-system] must be a list"
    assert len(requires) > 0, "'requires' list in [build-system] must not be empty"

    # Verify setuptools dependency requirement
    has_setuptools = any("setuptools" in req.lower() for req in requires)
    assert has_setuptools, f"Expected setuptools in [build-system].requires, found: {requires}"


# ==============================================================================
# 4. [project] Table Specifications
# ==============================================================================


def test_project_name_and_python_version(pyproject_data: Dict[str, Any]) -> None:
    """Validate project name 'CoChem-BASE' and required Python version >=3.11."""
    proj = pyproject_data["project"]

    assert "name" in proj, "Missing 'name' in [project] table"
    project_name = proj["name"]
    assert project_name in ("CoChem-BASE", "cochem-base"), (
        f"Unexpected project name '{project_name}', expected 'CoChem-BASE' or 'cochem-base'"
    )
    assert project_name == "CoChem-BASE", (
        f"Project name must be exactly 'CoChem-BASE', got '{project_name}'"
    )

    assert "requires-python" in proj, "Missing 'requires-python' in [project] table"
    req_py = proj["requires-python"]
    assert req_py == ">=3.11", f"Expected requires-python '>=3.11', got '{req_py}'"


def test_project_optional_metadata(pyproject_data: Dict[str, Any]) -> None:
    """Validate standard project metadata fields when present."""
    proj = pyproject_data["project"]

    if "version" in proj:
        assert isinstance(proj["version"], str), "'version' must be a string"
        assert len(proj["version"]) > 0, "'version' cannot be empty"

    if "description" in proj:
        assert isinstance(proj["description"], str), "'description' must be a string"
        assert len(proj["description"]) > 0, "'description' cannot be empty"

    if "authors" in proj:
        assert isinstance(proj["authors"], list), "'authors' must be a list"
        for author in proj["authors"]:
            assert isinstance(author, dict), "Author entry must be a dictionary"
            assert "name" in author, "Author entry must contain 'name'"

    if "readme" in proj:
        assert isinstance(proj["readme"], str), "'readme' must be a string path"
        # If readme specified, check filename pattern
        assert proj["readme"].lower().endswith(".md"), "Readme file should be a Markdown file"


def test_project_dependencies_structure(pyproject_data: Dict[str, Any]) -> None:
    """Validate dependencies and optional-dependencies structure in [project]."""
    proj = pyproject_data["project"]

    if "dependencies" in proj:
        deps = proj["dependencies"]
        assert isinstance(deps, list), "'dependencies' must be a list of strings"
        for dep in deps:
            assert isinstance(dep, str) and dep.strip(), f"Invalid dependency entry: {dep}"

    if "optional-dependencies" in proj:
        opt_deps = proj["optional-dependencies"]
        assert isinstance(opt_deps, dict), "'optional-dependencies' must be a table"
        for group_name, group_list in opt_deps.items():
            assert isinstance(group_name, str) and group_name, "Optional dependency group name cannot be empty"
            assert isinstance(group_list, list), f"Group '{group_name}' must map to a list"
            for item in group_list:
                assert isinstance(item, str) and item.strip(), f"Invalid optional dependency: {item}"


# ==============================================================================
# 5. [tool.setuptools.packages.find] Discovery
# ==============================================================================


def test_setuptools_package_discovery(pyproject_data: Dict[str, Any]) -> None:
    """Validate package discovery configuration in [tool.setuptools.packages.find]."""
    tools = pyproject_data.get("tool", {})
    assert "setuptools" in tools, "Missing [tool.setuptools] configuration in pyproject.toml"

    setuptools_cfg = tools["setuptools"]
    assert "packages" in setuptools_cfg, "Missing [tool.setuptools.packages] table"

    packages_cfg = setuptools_cfg["packages"]
    assert "find" in packages_cfg, "Missing [tool.setuptools.packages.find] table"

    find_cfg = packages_cfg["find"]
    assert "include" in find_cfg, "Missing 'include' in [tool.setuptools.packages.find]"

    includes = find_cfg["include"]
    assert isinstance(includes, list), "'include' in [tool.setuptools.packages.find] must be a list"
    assert "cochem_base*" in includes, (
        f"Expected 'cochem_base*' in find.include list, found: {includes}"
    )


# ==============================================================================
# 6. Tool Configurations ([tool.pytest.ini_options], [tool.ruff], [tool.mypy])
# ==============================================================================


def test_pytest_tool_configuration(pyproject_data: Dict[str, Any]) -> None:
    """Validate [tool.pytest.ini_options] defines testpaths."""
    tools = pyproject_data.get("tool", {})
    assert "pytest" in tools, "Missing [tool.pytest] in pyproject.toml"

    pytest_cfg = tools["pytest"]
    assert "ini_options" in pytest_cfg, "Missing [tool.pytest.ini_options] in pyproject.toml"

    ini_options = pytest_cfg["ini_options"]
    assert "testpaths" in ini_options, "Missing 'testpaths' in [tool.pytest.ini_options]"

    testpaths = ini_options["testpaths"]
    assert isinstance(testpaths, list), "'testpaths' must be a list"
    assert "tests" in testpaths, f"Expected 'tests' in testpaths, got: {testpaths}"


def test_ruff_tool_configuration(pyproject_data: Dict[str, Any]) -> None:
    """Validate [tool.ruff] configuration table."""
    tools = pyproject_data.get("tool", {})
    assert "ruff" in tools, "Missing [tool.ruff] in pyproject.toml"

    ruff_cfg = tools["ruff"]
    assert isinstance(ruff_cfg, dict), "[tool.ruff] must be a dictionary"

    if "line-length" in ruff_cfg:
        assert isinstance(ruff_cfg["line-length"], int), "line-length must be an integer"
        assert ruff_cfg["line-length"] >= 80, "line-length should be at least 80"

    if "exclude" in ruff_cfg:
        assert isinstance(ruff_cfg["exclude"], list), "exclude must be a list"


def test_mypy_tool_configuration(pyproject_data: Dict[str, Any]) -> None:
    """Validate [tool.mypy] configuration and overrides."""
    tools = pyproject_data.get("tool", {})
    assert "mypy" in tools, "Missing [tool.mypy] in pyproject.toml"

    mypy_cfg = tools["mypy"]
    assert isinstance(mypy_cfg, dict), "[tool.mypy] must be a dictionary"
    assert "python_version" in mypy_cfg or "warn_return_any" in mypy_cfg or "check_untyped_defs" in mypy_cfg, (
        "Expected type checking configurations in [tool.mypy]"
    )


# ==============================================================================
# 7. Zero-Mock & Anti-Spoofing Validations
# ==============================================================================


def test_pyproject_zero_mock_and_no_stubs(pyproject_content: str) -> None:
    """Validate that pyproject.toml contains no mock, stub, or placeholder tokens."""
    forbidden_tokens = [
        "TODO",
        "FIXME",
        "placeholder",
        "dummy",
        "fake",
        "synthetic",
        "stub",
        "mock",
        "TEMPORARY",
    ]
    for token in forbidden_tokens:
        assert token.lower() not in pyproject_content.lower(), (
            f"pyproject.toml contains forbidden placeholder token '{token}'"
        )


def test_test_suite_zero_mock_ast_inspection() -> None:
    """Validate zero-mock compliance across this test suite via AST analysis."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "mock" not in alias.name.lower(), (
                    f"Forbidden mock import in test suite: '{alias.name}'"
                )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "mock" not in mod.lower(), (
                f"Forbidden mock import in test suite from module: '{mod}'"
            )
