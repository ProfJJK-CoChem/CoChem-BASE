"""Zero-Mock Production Test Suite for CoChem-SpycFit requirements.txt Specifications.

Defends the Execution Tier dependency locking and Tripartite Architecture by validating:
- Physical existence of requirements.txt at CoChem-SpycFit repository root.
- Strict UTF-8 encoding (no byte order mark) and Unix LF line endings.
- Exact presence and exact pins of all 12 required dependencies.
- Strict exclusion of legacy Fortran binaries, unpinned dependencies, or relaxed specifiers.
- Requirement syntax validity using packaging.requirements.Requirement.
- Strict exact line count, uniqueness, and canonical ordering.
- Verification of zero forbidden testing constructs via AST analysis.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from packaging.requirements import Requirement

# Repository paths
BASE_REPO_ROOT = Path(__file__).resolve().parent.parent
SPYCFIT_REPO_ROOT = BASE_REPO_ROOT.parent / "CoChem-SpycFit"
SPYCFIT_REQUIREMENTS_PATH = SPYCFIT_REPO_ROOT / "requirements.txt"

# Canonical SRS requirements content
CANONICAL_REQUIREMENTS = [
    "jax==0.4.13",
    "jaxlib==0.4.13",
    "cupy-cuda12x==12.2.0",
    "h5py==3.9.0",
    "zarr==2.16.1",
    "pyarrow==13.0.0",
    "plotly==5.17.0",
    "ipywidgets==8.1.1",
    "mendeleev==0.14.0",
    "platformdirs==3.10.0",
    "filelock==3.12.2",
    "pyzmq==25.1.1",
]

CANONICAL_REQUIREMENTS_CONTENT = "\n".join(CANONICAL_REQUIREMENTS) + "\n"

EXPECTED_DEPENDENCY_MAP = {
    "jax": "0.4.13",
    "jaxlib": "0.4.13",
    "cupy-cuda12x": "12.2.0",
    "h5py": "3.9.0",
    "zarr": "2.16.1",
    "pyarrow": "13.0.0",
    "plotly": "5.17.0",
    "ipywidgets": "8.1.1",
    "mendeleev": "0.14.0",
    "platformdirs": "3.10.0",
    "filelock": "3.12.2",
    "pyzmq": "25.1.1",
}

FORBIDDEN_LEGACY_TOKENS = [
    "fortran",
    "spcat",
    "spfit",
    "calpgm",
    "f2py",
    "weave",
    "mock",
    "unittest",
    "pytest",
    "synthetic",
]


@pytest.fixture(scope="module")
def spycfit_requirements_lines() -> list[str]:
    """Fixture providing non-empty lines from CoChem-SpycFit requirements.txt."""
    assert SPYCFIT_REQUIREMENTS_PATH.exists(), f"Missing requirements.txt at {SPYCFIT_REQUIREMENTS_PATH}"
    content = SPYCFIT_REQUIREMENTS_PATH.read_text(encoding="utf-8")
    return [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]


def test_spycfit_requirements_existence_and_size() -> None:
    """Validate that requirements.txt physically exists in CoChem-SpycFit root with valid size bounds."""
    assert SPYCFIT_REQUIREMENTS_PATH.exists(), f"Target file must exist: {SPYCFIT_REQUIREMENTS_PATH}"
    assert SPYCFIT_REQUIREMENTS_PATH.is_file(), f"Target path must be a regular file: {SPYCFIT_REQUIREMENTS_PATH}"
    size = SPYCFIT_REQUIREMENTS_PATH.stat().st_size
    assert 100 < size < 2000, f"requirements.txt size ({size} bytes) outside expected range (100, 2000)"


def test_spycfit_requirements_encoding_and_lf_line_endings() -> None:
    """Validate strict UTF-8 encoding without BOM and Unix LF line endings."""
    raw_bytes = SPYCFIT_REQUIREMENTS_PATH.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "Target file must not contain a UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "Target file contains Windows CRLF line endings"
    assert b"\r" not in raw_bytes, "Target file contains carriage return line endings"
    assert b"\n" in raw_bytes, "Target file must contain Unix LF line endings"
    assert raw_bytes.endswith(b"\n"), "Target file must terminate with a Unix LF newline"
    decoded = raw_bytes.decode("utf-8")
    assert len(decoded) > 0, "Target file content cannot be empty"


def test_spycfit_requirements_canonical_content() -> None:
    """Validate that requirements.txt strictly matches the canonical SRS specification."""
    content = SPYCFIT_REQUIREMENTS_PATH.read_text(encoding="utf-8")
    assert content == CANONICAL_REQUIREMENTS_CONTENT, "Content differs from canonical SRS specification"


def test_spycfit_requirements_exact_count_and_no_duplicates(spycfit_requirements_lines: list[str]) -> None:
    """Validate exactly 12 locked dependencies with zero duplicates."""
    assert len(spycfit_requirements_lines) == 12, (
        f"Expected exactly 12 locked dependencies, found {len(spycfit_requirements_lines)}"
    )
    parsed_names = [Requirement(line).name.lower() for line in spycfit_requirements_lines]
    assert len(parsed_names) == len(set(parsed_names)), "Duplicate dependency declarations found"


@pytest.mark.parametrize(
    "pkg_name, expected_version",
    list(EXPECTED_DEPENDENCY_MAP.items()),
)
def test_spycfit_requirements_individual_pins(
    spycfit_requirements_lines: list[str], pkg_name: str, expected_version: str
) -> None:
    """Validate exact pinned version for each required dependency."""
    req_map = {}
    for line in spycfit_requirements_lines:
        req = Requirement(line)
        req_map[req.name.lower()] = req

    normalized_name = pkg_name.lower()
    assert normalized_name in req_map, f"Missing required dependency: {pkg_name}"
    
    req = req_map[normalized_name]
    specifiers = list(req.specifier)
    assert len(specifiers) == 1, (
        f"Dependency '{pkg_name}' must have exactly one pinned specifier, found: {req.specifier}"
    )
    spec = specifiers[0]
    assert spec.operator == "==", (
        f"Dependency '{pkg_name}' must use strict '==' operator, found '{spec.operator}'"
    )
    assert spec.version == expected_version, (
        f"Dependency '{pkg_name}' pinned version mismatch: expected '{expected_version}', got '{spec.version}'"
    )


def test_spycfit_requirements_packaging_validity(spycfit_requirements_lines: list[str]) -> None:
    """Validate all requirement lines strictly parse under packaging.requirements.Requirement standard."""
    for line in spycfit_requirements_lines:
        req = Requirement(line)
        assert req.name, f"Invalid requirement name parsed from: '{line}'"
        assert req.specifier, f"Requirement must specify a version pin: '{line}'"
        assert not req.url, f"Direct URL references are forbidden: '{line}'"
        assert not req.extras, f"Extras are not permitted in strict locked pins: '{line}'"


def test_spycfit_requirements_exclusion_of_forbidden_and_unpinned(
    spycfit_requirements_lines: list[str],
) -> None:
    """Verify strict exclusion of legacy Fortran binaries, unpinned packages, and forbidden keywords."""
    for line in spycfit_requirements_lines:
        lower_line = line.lower()
        for forbidden in FORBIDDEN_LEGACY_TOKENS:
            assert forbidden not in lower_line, (
                f"Forbidden legacy token or mock reference '{forbidden}' found in requirement line: '{line}'"
            )
        
        # Verify operator is strictly == and not relaxed (>=, <=, ~=, >, <, !=)
        assert "==" in line, f"Requirement line must be strictly version-locked with '==': '{line}'"
        for bad_op in [">=", "<=", "~=", "!=", ">", "<", "*"]:
            if bad_op in line and "==" not in bad_op:
                assert False, f"Relaxed or forbidden version specifier '{bad_op}' found in requirement line: '{line}'"

    # Ensure no extra unrecognized packages exist
    allowed_names = set(EXPECTED_DEPENDENCY_MAP.keys())
    for line in spycfit_requirements_lines:
        req = Requirement(line)
        assert req.name.lower() in allowed_names, (
            f"Unrecognized / non-whitelisted dependency found: '{req.name}'"
        )


def test_zero_mock_or_synthetic_directives_ast() -> None:
    """Verify through AST analysis that no forbidden mock libraries are imported in this test file."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "mock" not in alias.name.lower(), f"Forbidden import found: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "mock" not in module.lower(), f"Forbidden import from module: {module}"
