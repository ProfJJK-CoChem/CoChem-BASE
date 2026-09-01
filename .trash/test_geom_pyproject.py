"""Zero-Mock Test Suite for CoChem-GEOM pyproject.toml in CoChem-BASE.

Cross-repository contract validation for CoChem-GEOM package definition:
- Physical file existence, UTF-8 encoding (no BOM), and strict Unix LF line endings.
- Valid TOML syntax parsing via standard tomllib (with tomli fallback).
- [build-system] table adhering to PEP 517 / PEP 518 specifications (setuptools.build_meta, wheel).
- [project] metadata compliance: name ('CoChem-GEOM'), version ('0.1.0'), requires-python ('>=3.10'), description with [D] provenance.
- Required runtime dependencies (mendeleev, h5py, scipy, numpy, tqdm, pydantic>=2, pyarrow, plotly, ipywidgets, platformdirs, filelock, rdkit, torch, ase, molsym).
- Optional developer dependencies (pytest, pytest-cov, ruff, mypy, black).
- Package discovery configuration in [tool.setuptools.packages.find].
- [tool.ruff], [tool.black], [tool.mypy], and [tool.pytest.ini_options] tooling tables.
- Zero-mock policy and absence of forbidden tokens.
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
from typing import Any

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

GEOM_DIR_ENV = os.environ.get("COCHEM_GEOM_DIR")
if GEOM_DIR_ENV:
    GEOM_ROOT = Path(GEOM_DIR_ENV).resolve()
else:
    GEOM_ROOT = Path(__file__).resolve().parent.parent.parent / "CoChem-GEOM"

GEOM_PYPROJECT_PATH = GEOM_ROOT / "pyproject.toml"

REQUIRED_RUNTIME_DEPENDENCIES: list[str] = [
    "mendeleev",
    "h5py",
    "scipy",
    "numpy",
    "tqdm",
    "pydantic",
    "pyarrow",
    "plotly",
    "ipywidgets",
    "platformdirs",
    "filelock",
    "rdkit",
    "torch",
    "ase",
    "molsym",
]

REQUIRED_DEV_DEPENDENCIES: list[str] = [
    "pytest",
    "pytest-cov",
    "ruff",
    "mypy",
    "black",
]


@pytest.fixture(scope="module")
def geom_pyproject_raw_bytes() -> bytes:
    """Fixture providing raw bytes of CoChem-GEOM pyproject.toml."""
    assert GEOM_PYPROJECT_PATH.exists(), f"CoChem-GEOM pyproject.toml does not exist at {GEOM_PYPROJECT_PATH}"
    return GEOM_PYPROJECT_PATH.read_bytes()


@pytest.fixture(scope="module")
def geom_pyproject_content(geom_pyproject_raw_bytes: bytes) -> str:
    """Fixture providing decoded string content of CoChem-GEOM pyproject.toml."""
    return geom_pyproject_raw_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def geom_pyproject_data(geom_pyproject_content: str) -> dict[str, Any]:
    """Fixture providing parsed TOML dictionary."""
    data = tomllib.loads(geom_pyproject_content)
    assert isinstance(data, dict), "Parsed TOML root must be a dictionary"
    return data


# ==============================================================================
# 1. Physical File Integrity & Line Endings
# ==============================================================================


def test_geom_pyproject_file_exists() -> None:
    """Validate that CoChem-GEOM pyproject.toml exists as a regular file."""
    assert GEOM_PYPROJECT_PATH.exists(), f"CoChem-GEOM pyproject.toml missing at {GEOM_PYPROJECT_PATH}"
    assert GEOM_PYPROJECT_PATH.is_file(), f"{GEOM_PYPROJECT_PATH} must be a regular file"
    size = GEOM_PYPROJECT_PATH.stat().st_size
    assert size >= 100, f"CoChem-GEOM pyproject.toml size too small ({size} bytes)"
    assert size <= 50_000, f"CoChem-GEOM pyproject.toml size unexpectedly large ({size} bytes)"


def test_geom_pyproject_encoding_and_unix_lf_endings(geom_pyproject_raw_bytes: bytes) -> None:
    """Validate strict UTF-8 without BOM and strict Unix LF line endings."""
    assert not geom_pyproject_raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "CoChem-GEOM pyproject.toml contains UTF-8 Byte Order Mark (BOM)"
    )
    assert b"\r\n" not in geom_pyproject_raw_bytes, (
        "CoChem-GEOM pyproject.toml contains Windows CRLF line endings; strictly Unix LF required"
    )
    assert b"\r" not in geom_pyproject_raw_bytes, (
        "CoChem-GEOM pyproject.toml contains CR line endings; strictly Unix LF required"
    )
    assert b"\n" in geom_pyproject_raw_bytes, "CoChem-GEOM pyproject.toml must contain Unix LF line endings"


# ==============================================================================
# 2. TOML Syntax & Top-Level Schema
# ==============================================================================


def test_geom_pyproject_toml_syntax_validity(geom_pyproject_data: dict[str, Any]) -> None:
    """Validate that CoChem-GEOM pyproject.toml parses cleanly into required top-level tables."""
    assert "build-system" in geom_pyproject_data, "Missing [build-system] table in CoChem-GEOM pyproject.toml"
    assert "project" in geom_pyproject_data, "Missing [project] table in CoChem-GEOM pyproject.toml"
    assert "tool" in geom_pyproject_data, "Missing [tool] table in CoChem-GEOM pyproject.toml"
    assert isinstance(geom_pyproject_data["build-system"], dict), "[build-system] must be a table"
    assert isinstance(geom_pyproject_data["project"], dict), "[project] must be a table"
    assert isinstance(geom_pyproject_data["tool"], dict), "[tool] must be a table"


# ==============================================================================
# 3. [build-system] Table Specifications
# ==============================================================================


def test_geom_build_system_backend_and_requires(geom_pyproject_data: dict[str, Any]) -> None:
    """Validate PEP 517 / PEP 518 build-system backend and required build tools."""
    build_sys = geom_pyproject_data["build-system"]
    assert "build-backend" in build_sys, "Missing 'build-backend' in [build-system]"
    assert build_sys["build-backend"] == "setuptools.build_meta", (
        f"Expected build-backend 'setuptools.build_meta', got '{build_sys.get('build-backend')}'"
    )

    assert "requires" in build_sys, "Missing 'requires' in [build-system]"
    requires = build_sys["requires"]
    assert isinstance(requires, list), "'requires' in [build-system] must be a list"
    assert len(requires) >= 2, "'requires' list in [build-system] should contain setuptools and wheel"

    has_setuptools = any("setuptools" in req.lower() for req in requires)
    assert has_setuptools, f"Expected setuptools in [build-system].requires, found: {requires}"

    has_wheel = any("wheel" in req.lower() for req in requires)
    assert has_wheel, f"Expected wheel in [build-system].requires, found: {requires}"


# ==============================================================================
# 4. [project] Table Specifications
# ==============================================================================


def test_geom_project_name_version_and_provenance(geom_pyproject_data: dict[str, Any]) -> None:
    """Validate project metadata, version, and provenance tag in description."""
    proj = geom_pyproject_data["project"]

    assert "name" in proj, "Missing 'name' in [project] table"
    assert proj["name"] == "CoChem-GEOM", f"Project name must be 'CoChem-GEOM', got '{proj['name']}'"

    assert "version" in proj, "Missing 'version' in [project] table"
    assert proj["version"] == "0.1.0", f"Project version must be '0.1.0', got '{proj['version']}'"

    assert "description" in proj, "Missing 'description' in [project] table"
    desc = proj["description"]
    assert isinstance(desc, str) and len(desc) > 0, "Description must be non-empty string"
    assert "[D]" in desc, f"Description must include provenance tag '[D]', got: '{desc}'"

    assert "requires-python" in proj, "Missing 'requires-python' in [project] table"
    assert proj["requires-python"] == ">=3.10", (
        f"Expected requires-python '>=3.10', got '{proj['requires-python']}'"
    )

    assert "authors" in proj, "Missing 'authors' in [project] table"
    authors = proj["authors"]
    assert isinstance(authors, list) and len(authors) > 0, "Authors must be non-empty list"
    assert any("name" in a for a in authors), "Author list must have at least one name entry"

    assert "readme" in proj, "Missing 'readme' in [project] table"
    assert proj["readme"] == "README.md", f"Readme must be 'README.md', got '{proj['readme']}'"


def test_geom_project_runtime_dependencies(geom_pyproject_data: dict[str, Any]) -> None:
    """Validate that all mandatory scientific runtime dependencies are present."""
    proj = geom_pyproject_data["project"]
    assert "dependencies" in proj, "Missing 'dependencies' in [project] table"
    deps = proj["dependencies"]
    assert isinstance(deps, list), "'dependencies' must be a list"

    dep_names = [d.split(">=")[0].split("==")[0].split("<")[0].strip().lower() for d in deps]
    for required_dep in REQUIRED_RUNTIME_DEPENDENCIES:
        assert required_dep.lower() in dep_names, (
            f"Mandatory dependency '{required_dep}' missing from project.dependencies: {deps}"
        )


def test_geom_project_dev_dependencies(geom_pyproject_data: dict[str, Any]) -> None:
    """Validate optional dev dependencies table."""
    proj = geom_pyproject_data["project"]
    assert "optional-dependencies" in proj, "Missing 'optional-dependencies' in [project]"
    opt_deps = proj["optional-dependencies"]
    assert isinstance(opt_deps, dict), "'optional-dependencies' must be a dict"
    assert "dev" in opt_deps, "Missing 'dev' in [project.optional-dependencies]"

    dev_deps = opt_deps["dev"]
    assert isinstance(dev_deps, list), "'dev' optional dependencies must be a list"

    dev_names = [d.split(">=")[0].split("==")[0].split("<")[0].strip().lower() for d in dev_deps]
    for req_dev in REQUIRED_DEV_DEPENDENCIES:
        assert req_dev.lower() in dev_names, (
            f"Developer dependency '{req_dev}' missing from optional-dependencies.dev: {dev_deps}"
        )


# ==============================================================================
# 5. [tool.setuptools.packages.find] Discovery
# ==============================================================================


def test_geom_setuptools_package_discovery(geom_pyproject_data: dict[str, Any]) -> None:
    """Validate package discovery configuration in [tool.setuptools.packages.find]."""
    tools = geom_pyproject_data.get("tool", {})
    assert "setuptools" in tools, "Missing [tool.setuptools] configuration in pyproject.toml"

    setuptools_cfg = tools["setuptools"]
    assert "packages" in setuptools_cfg, "Missing [tool.setuptools.packages] table"

    packages_cfg = setuptools_cfg["packages"]
    assert "find" in packages_cfg, "Missing [tool.setuptools.packages.find] table"

    find_cfg = packages_cfg["find"]
    assert "include" in find_cfg, "Missing 'include' in [tool.setuptools.packages.find]"

    includes = find_cfg["include"]
    assert isinstance(includes, list), "'include' in [tool.setuptools.packages.find] must be a list"
    assert "cochem_geom*" in includes, (
        f"Expected 'cochem_geom*' in find.include list, found: {includes}"
    )


# ==============================================================================
# 6. Tool Configurations ([tool.ruff], [tool.black], [tool.mypy], [tool.pytest.ini_options])
# ==============================================================================


def test_geom_ruff_tool_configuration(geom_pyproject_data: dict[str, Any]) -> None:
    """Validate [tool.ruff] and [tool.ruff.lint] configuration tables."""
    tools = geom_pyproject_data.get("tool", {})
    assert "ruff" in tools, "Missing [tool.ruff] in pyproject.toml"

    ruff_cfg = tools["ruff"]
    assert isinstance(ruff_cfg, dict), "[tool.ruff] must be a dictionary"
    assert "line-length" in ruff_cfg, "Missing 'line-length' in [tool.ruff]"
    assert ruff_cfg["line-length"] >= 80, "line-length should be at least 80"
    assert ruff_cfg.get("target-version") == "py310", (
        f"Expected target-version 'py310', got '{ruff_cfg.get('target-version')}'"
    )

    assert "exclude" in ruff_cfg, "Missing 'exclude' in [tool.ruff]"
    excludes = ruff_cfg["exclude"]
    assert isinstance(excludes, list), "'exclude' in [tool.ruff] must be a list"
    for gen_dir in ["build", "dist", "artifacts", "scratch"]:
        assert any(gen_dir in exc for exc in excludes), (
            f"Generated directory '{gen_dir}' must be excluded in [tool.ruff]"
        )

    assert "lint" in ruff_cfg, "Missing [tool.ruff.lint] in pyproject.toml"
    lint_cfg = ruff_cfg["lint"]
    assert "select" in lint_cfg, "Missing 'select' in [tool.ruff.lint]"
    assert isinstance(lint_cfg["select"], list), "'select' must be a list"
    assert "ignore" in lint_cfg, "Missing 'ignore' in [tool.ruff.lint]"


def test_geom_black_tool_configuration(geom_pyproject_data: dict[str, Any]) -> None:
    """Validate [tool.black] configuration table."""
    tools = geom_pyproject_data.get("tool", {})
    assert "black" in tools, "Missing [tool.black] in pyproject.toml"

    black_cfg = tools["black"]
    assert isinstance(black_cfg, dict), "[tool.black] must be a dictionary"
    assert "line-length" in black_cfg, "Missing 'line-length' in [tool.black]"
    assert black_cfg["line-length"] >= 80, "line-length should be at least 80"
    assert "target-version" in black_cfg, "Missing 'target-version' in [tool.black]"
    assert "py310" in black_cfg["target-version"], "Black target-version must include 'py310'"
    assert "exclude" in black_cfg, "Missing 'exclude' in [tool.black]"


def test_geom_mypy_tool_configuration(geom_pyproject_data: dict[str, Any]) -> None:
    """Validate [tool.mypy] strict typing configuration and overrides."""
    tools = geom_pyproject_data.get("tool", {})
    assert "mypy" in tools, "Missing [tool.mypy] in pyproject.toml"

    mypy_cfg = tools["mypy"]
    assert isinstance(mypy_cfg, dict), "[tool.mypy] must be a dictionary"
    assert mypy_cfg.get("python_version") == "3.10", (
        f"Expected mypy python_version '3.10', got '{mypy_cfg.get('python_version')}'"
    )
    assert mypy_cfg.get("strict") is True or mypy_cfg.get("warn_return_any") is True, (
        "Expected strict type checking configuration in [tool.mypy]"
    )
    assert "exclude" in mypy_cfg, "Missing 'exclude' in [tool.mypy]"

    assert "overrides" in mypy_cfg, "Missing [[tool.mypy.overrides]] in [tool.mypy]"
    overrides = mypy_cfg["overrides"]
    assert isinstance(overrides, list), "mypy overrides must be a list of override tables"
    assert len(overrides) > 0, "mypy overrides list must not be empty"

    has_ignore_missing = any(o.get("ignore_missing_imports") is True for o in overrides)
    assert has_ignore_missing, "Expected ignore_missing_imports = true in mypy overrides"


def test_geom_pytest_tool_configuration(geom_pyproject_data: dict[str, Any]) -> None:
    """Validate [tool.pytest.ini_options] defines testpaths and pythonpath."""
    tools = geom_pyproject_data.get("tool", {})
    assert "pytest" in tools, "Missing [tool.pytest] in pyproject.toml"

    pytest_cfg = tools["pytest"]
    assert "ini_options" in pytest_cfg, "Missing [tool.pytest.ini_options] in pyproject.toml"

    ini_options = pytest_cfg["ini_options"]
    assert "testpaths" in ini_options, "Missing 'testpaths' in [tool.pytest.ini_options]"
    assert "tests" in ini_options["testpaths"], f"Expected 'tests' in testpaths, got: {ini_options['testpaths']}"

    assert "pythonpath" in ini_options, "Missing 'pythonpath' in [tool.pytest.ini_options]"
    assert "." in ini_options["pythonpath"], f"Expected '.' in pythonpath, got: {ini_options['pythonpath']}"


# ==============================================================================
# 7. Zero-Mock & Anti-Spoofing Validations
# ==============================================================================


def test_geom_pyproject_zero_mock_and_no_banned_tokens(geom_pyproject_content: str) -> None:
    """Validate that pyproject.toml contains zero banned/placeholder tokens."""
    banned_tokens = [
        "mock",
        "example",
        "stub",
        "dummy",
        "placeholder",
        "fake",
        "sample",
        "TODO",
        "FIXME",
    ]
    content_lower = geom_pyproject_content.lower()
    for token in banned_tokens:
        assert token.lower() not in content_lower, (
            f"pyproject.toml contains forbidden token '{token}'"
        )


def test_geom_test_suite_zero_mock_ast_inspection() -> None:
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
