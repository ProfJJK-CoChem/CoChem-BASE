"""Zero-Mock Production Test Suite for CoChem-SpycFit pyproject.toml Specifications.

Defends the Execution Tier build system and Tripartite Architecture metadata by validating:
- Physical existence of pyproject.toml at CoChem-SpycFit repository root.
- Strict UTF-8 encoding (no byte order mark) and Unix LF line endings.
- Exact compliance with SRS Document specifications for build system and project metadata.
- TOML syntax validity and schema parsing using tomllib / tomli.
- Build system table: requires = ["setuptools>=61.0", "wheel"], build-backend = "setuptools.build_meta".
- Project table: name = "CoChem-SpycFit", version = "0.1.0", description, authors.
- Exact presence and canonical ordering of all 12 required dependencies:
  jax, jaxlib, cupy-cuda12x, h5py, zarr, pyarrow, plotly, ipywidgets, mendeleev, platformdirs, filelock, pyzmq.
- Optional dependencies: dev = ["pytest", "flake8"].
- Strict exclusion of legacy Fortran binaries, unapproved dependencies, and mock/placeholder tokens.
- Verification of zero forbidden testing constructs via AST analysis.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any, Dict

import pytest
from packaging.requirements import Requirement

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

# Repository paths with strict environmental configuration and Path.home() fallback
COCHEM_HOME = Path(os.environ.get("COCHEM_HOME", Path.home() / "cochem"))
BASE_REPO_ROOT = Path(
    os.environ.get("COCHEM_BASE_ROOT", str(Path(__file__).resolve().parent.parent))
)
SPYCFIT_REPO_ROOT = Path(
    os.environ.get("COCHEM_SPYCFIT_ROOT", str(BASE_REPO_ROOT.parent / "CoChem-SpycFit"))
)
SPYCFIT_PYPROJECT_PATH = SPYCFIT_REPO_ROOT / "pyproject.toml"

# Canonical SRS pyproject.toml content
CANONICAL_PYPROJECT_CONTENT = (
    "[build-system]\n"
    'requires = ["setuptools>=61.0", "wheel"]\n'
    'build-backend = "setuptools.build_meta"\n'
    "\n"
    "[project]\n"
    'name = "CoChem-SpycFit"\n'
    'version = "0.1.0"\n'
    'description = "Tripartite Workspace Air-Gap enabled computational spectroscopy fitter."\n'
    'authors = [{name = "CoChem Swarm"}]\n'
    "dependencies = [\n"
    '    "jax",\n'
    '    "jaxlib",\n'
    '    "cupy-cuda12x",\n'
    '    "h5py",\n'
    '    "zarr",\n'
    '    "pyarrow",\n'
    '    "plotly",\n'
    '    "ipywidgets",\n'
    '    "mendeleev",\n'
    '    "platformdirs",\n'
    '    "filelock",\n'
    '    "pyzmq"\n'
    "]\n"
    "\n"
    "[project.optional-dependencies]\n"
    'dev = ["pytest", "flake8"]\n'
)

EXPECTED_BUILD_SYSTEM_REQUIRES = ["setuptools>=61.0", "wheel"]
EXPECTED_BUILD_BACKEND = "setuptools.build_meta"

EXPECTED_PROJECT_NAME = "CoChem-SpycFit"
EXPECTED_PROJECT_VERSION = "0.1.0"
EXPECTED_PROJECT_DESCRIPTION = (
    "Tripartite Workspace Air-Gap enabled computational spectroscopy fitter."
)
EXPECTED_PROJECT_AUTHORS = [{"name": "CoChem Swarm"}]

EXPECTED_DEPENDENCIES = [
    "jax",
    "jaxlib",
    "cupy-cuda12x",
    "h5py",
    "zarr",
    "pyarrow",
    "plotly",
    "ipywidgets",
    "mendeleev",
    "platformdirs",
    "filelock",
    "pyzmq",
]

EXPECTED_DEV_DEPENDENCIES = ["pytest", "flake8"]

FORBIDDEN_LEGACY_TOKENS = [
    "fortran",
    "spcat",
    "spfit",
    "calpgm",
    "f2py",
    "weave",
    "mock",
    "dummy",
    "fake",
    "synthetic",
    "stub",
    "placeholder",
]


@pytest.fixture(scope="module")
def pyproject_raw_bytes() -> bytes:
    """Fixture providing raw bytes of CoChem-SpycFit pyproject.toml."""
    assert (
        SPYCFIT_PYPROJECT_PATH.exists()
    ), f"Missing pyproject.toml at {SPYCFIT_PYPROJECT_PATH}"
    return SPYCFIT_PYPROJECT_PATH.read_bytes()


@pytest.fixture(scope="module")
def pyproject_content(pyproject_raw_bytes: bytes) -> str:
    """Fixture providing decoded text content of CoChem-SpycFit pyproject.toml."""
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


def test_spycfit_pyproject_existence_and_size() -> None:
    """Validate that pyproject.toml physically exists in CoChem-SpycFit root with valid size bounds."""
    assert (
        SPYCFIT_PYPROJECT_PATH.exists()
    ), f"Target file must exist: {SPYCFIT_PYPROJECT_PATH}"
    assert (
        SPYCFIT_PYPROJECT_PATH.is_file()
    ), f"Target path must be a regular file: {SPYCFIT_PYPROJECT_PATH}"
    size = SPYCFIT_PYPROJECT_PATH.stat().st_size
    assert (
        100 < size < 5000
    ), f"pyproject.toml size ({size} bytes) outside expected range (100, 5000)"


def test_spycfit_pyproject_encoding_and_lf_line_endings(
    pyproject_raw_bytes: bytes,
) -> None:
    """Validate strict UTF-8 encoding without BOM and Unix LF line endings."""
    assert not pyproject_raw_bytes.startswith(
        b"\xef\xbb\xbf"
    ), "Target file must not contain a UTF-8 BOM"
    assert (
        b"\r\n" not in pyproject_raw_bytes
    ), "Target file contains Windows CRLF line endings"
    assert (
        b"\r" not in pyproject_raw_bytes
    ), "Target file contains carriage return line endings"
    assert b"\n" in pyproject_raw_bytes, "Target file must contain Unix LF line endings"
    assert pyproject_raw_bytes.endswith(
        b"\n"
    ), "Target file must terminate with a Unix LF newline"
    decoded = pyproject_raw_bytes.decode("utf-8")
    assert len(decoded) > 0, "Target file content cannot be empty"


def test_spycfit_pyproject_canonical_content(pyproject_content: str) -> None:
    """Validate that pyproject.toml strictly matches the canonical SRS specification."""
    assert pyproject_content == CANONICAL_PYPROJECT_CONTENT, (
        f"pyproject.toml content differs from canonical SRS specification:\n"
        f"--- Got ---\n{pyproject_content}\n"
        f"--- Expected ---\n{CANONICAL_PYPROJECT_CONTENT}"
    )


# ==============================================================================
# 2. TOML Schema & [build-system] Table
# ==============================================================================


def test_spycfit_pyproject_top_level_tables(pyproject_data: Dict[str, Any]) -> None:
    """Validate required top-level tables exist in pyproject.toml."""
    assert "build-system" in pyproject_data, "Missing [build-system] table"
    assert "project" in pyproject_data, "Missing [project] table"
    assert isinstance(
        pyproject_data["build-system"], dict
    ), "[build-system] must be a table"
    assert isinstance(pyproject_data["project"], dict), "[project] must be a table"


def test_spycfit_pyproject_build_system(pyproject_data: Dict[str, Any]) -> None:
    """Validate [build-system] requires setuptools>=61.0, wheel, and setuptools.build_meta backend."""
    build_sys = pyproject_data["build-system"]
    assert "requires" in build_sys, "Missing 'requires' in [build-system]"
    assert "build-backend" in build_sys, "Missing 'build-backend' in [build-system]"

    assert (
        build_sys["requires"] == EXPECTED_BUILD_SYSTEM_REQUIRES
    ), f"Expected build-system requires {EXPECTED_BUILD_SYSTEM_REQUIRES}, got {build_sys['requires']}"
    assert (
        build_sys["build-backend"] == EXPECTED_BUILD_BACKEND
    ), f"Expected build-backend '{EXPECTED_BUILD_BACKEND}', got '{build_sys['build-backend']}'"


# ==============================================================================
# 3. [project] Metadata Table
# ==============================================================================


def test_spycfit_pyproject_metadata(pyproject_data: Dict[str, Any]) -> None:
    """Validate name, version, description, and authors in [project]."""
    proj = pyproject_data["project"]
    assert (
        proj.get("name") == EXPECTED_PROJECT_NAME
    ), f"Expected project.name '{EXPECTED_PROJECT_NAME}', got '{proj.get('name')}'"
    assert (
        proj.get("version") == EXPECTED_PROJECT_VERSION
    ), f"Expected project.version '{EXPECTED_PROJECT_VERSION}', got '{proj.get('version')}'"
    assert (
        proj.get("description") == EXPECTED_PROJECT_DESCRIPTION
    ), f"Expected project.description '{EXPECTED_PROJECT_DESCRIPTION}', got '{proj.get('description')}'"
    assert (
        proj.get("authors") == EXPECTED_PROJECT_AUTHORS
    ), f"Expected project.authors {EXPECTED_PROJECT_AUTHORS}, got {proj.get('authors')}"


# ==============================================================================
# 4. [project.dependencies] Table
# ==============================================================================


def test_spycfit_pyproject_dependencies_presence_and_count(
    pyproject_data: Dict[str, Any],
) -> None:
    """Validate exactly 12 required dependencies are present in [project.dependencies]."""
    proj = pyproject_data["project"]
    assert "dependencies" in proj, "Missing 'dependencies' list in [project]"
    deps = proj["dependencies"]
    assert isinstance(deps, list), "'dependencies' must be a list"
    assert (
        len(deps) == 12
    ), f"Expected exactly 12 dependencies, found {len(deps)}: {deps}"
    assert (
        deps == EXPECTED_DEPENDENCIES
    ), f"Dependencies list mismatch.\nExpected: {EXPECTED_DEPENDENCIES}\nGot: {deps}"


@pytest.mark.parametrize("expected_pkg", EXPECTED_DEPENDENCIES)
def test_spycfit_pyproject_individual_dependency(
    pyproject_data: Dict[str, Any], expected_pkg: str
) -> None:
    """Validate each individual dependency parses cleanly under packaging standards."""
    deps = pyproject_data["project"]["dependencies"]
    assert (
        expected_pkg in deps
    ), f"Required dependency '{expected_pkg}' missing from dependencies"
    req = Requirement(expected_pkg)
    assert req.name.lower() == expected_pkg.lower()


def test_spycfit_pyproject_no_duplicate_dependencies(
    pyproject_data: Dict[str, Any],
) -> None:
    """Validate zero duplicate dependency declarations."""
    deps = pyproject_data["project"]["dependencies"]
    normalized = [Requirement(d).name.lower() for d in deps]
    assert len(normalized) == len(
        set(normalized)
    ), f"Duplicate dependencies detected in: {deps}"


def test_spycfit_pyproject_exclusion_of_forbidden_dependencies(
    pyproject_data: Dict[str, Any],
) -> None:
    """Validate exclusion of legacy Fortran binaries or unapproved packages."""
    deps = pyproject_data["project"]["dependencies"]
    allowed_names = {Requirement(d).name.lower() for d in EXPECTED_DEPENDENCIES}

    for dep in deps:
        req = Requirement(dep)
        assert (
            req.name.lower() in allowed_names
        ), f"Unapproved dependency found in project.dependencies: '{dep}'"
        for forbidden in FORBIDDEN_LEGACY_TOKENS:
            assert (
                forbidden not in dep.lower()
            ), f"Forbidden token '{forbidden}' found in dependency declaration: '{dep}'"


# ==============================================================================
# 5. [project.optional-dependencies] Table
# ==============================================================================


def test_spycfit_pyproject_optional_dependencies(
    pyproject_data: Dict[str, Any],
) -> None:
    """Validate [project.optional-dependencies] defines dev dependencies."""
    proj = pyproject_data["project"]
    assert (
        "optional-dependencies" in proj
    ), "Missing [project.optional-dependencies] table"
    opt_deps = proj["optional-dependencies"]
    assert isinstance(
        opt_deps, dict
    ), "[project.optional-dependencies] must be a dictionary"
    assert "dev" in opt_deps, "Missing 'dev' group in [project.optional-dependencies]"
    dev_deps = opt_deps["dev"]
    assert isinstance(dev_deps, list), "'dev' optional dependencies must be a list"
    assert (
        dev_deps == EXPECTED_DEV_DEPENDENCIES
    ), f"Expected dev dependencies {EXPECTED_DEV_DEPENDENCIES}, got {dev_deps}"

    for dep in dev_deps:
        req = Requirement(dep)
        assert req.name, f"Invalid optional dependency: '{dep}'"


# ==============================================================================
# 6. Zero-Mock & Anti-Spoofing Validations
# ==============================================================================


def test_spycfit_pyproject_zero_mock_and_no_stubs(pyproject_content: str) -> None:
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
        assert (
            token.lower() not in pyproject_content.lower()
        ), f"pyproject.toml contains forbidden placeholder token '{token}'"


def test_test_suite_zero_mock_ast_inspection() -> None:
    """Validate zero-mock compliance across this test suite via AST analysis."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert (
                    "mock" not in alias.name.lower()
                ), f"Forbidden mock import in test suite: '{alias.name}'"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert (
                "mock" not in mod.lower()
            ), f"Forbidden mock import in test suite from module: '{mod}'"
