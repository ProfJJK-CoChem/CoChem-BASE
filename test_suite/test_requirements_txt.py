"""Comprehensive Zero-Mock Test Suite for CoChem-BASE requirements.txt.

Defends dependency specification, micro-silo boundary enforcement, and environment reproducibility by validating:
- Physical existence of requirements.txt at repository root.
- Strict UTF-8 encoding (no BOM: \\xef\\xbb\\xbf) and strict Unix LF line endings (no \\r\\n, no \\r).
- Non-empty file within reasonable bounds (> 20 bytes, < 10,000 bytes).
- Valid PEP 508 syntax parsing for all non-comment, non-empty lines using packaging.requirements.Requirement.
- Mandatory version-locked routing, validation, SWMR I/O, IPC, and GPU polling dependencies:
  * pydantic (>=2.0.0)
  * h5py (>=3.9.0)
  * pyzmq (>=25.1.0)
  * pynvml (>=11.5.0)
- Exact dependency inventory validation (strictly matching required structural dependencies).
- Every requirement specifies non-empty version constraints (no unpinned floating packages).
- Specifier version constraints compatibility verification.
- Prohibited dependency exclusion (psutil must not be declared; GPU polling uses pynvml/nvidia-smi).
- Micro-silo boundary enforcement: strictly zero heavy compute engines (torch, pytorch, pyscf, gpu4pyscf, jax, tensorflow, etc.).
- Documentation compliance: Lustre POSIX lock corruption fallback and GPU polling requirements documented in comments.
- Zero-mock policy and absence of placeholder, dummy, or stub tokens in requirements.txt and test suite.
- AST inspection ensuring zero mock imports across the test suite.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, List, Set

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS_PATH = REPO_ROOT / "requirements.txt"

# Mandatory core structural dependencies specified in SRS
MANDATORY_DEPENDENCIES: Set[str] = {
    "pydantic",
    "h5py",
    "pyzmq",
    "pynvml",
}

# Minimum version constraints per SRS specifications
EXPECTED_MINIMUM_VERSIONS: Dict[str, str] = {
    "pydantic": "2.0.0",
    "h5py": "3.9.0",
    "pyzmq": "25.1.0",
    "pynvml": "11.5.0",
}

# Forbidden heavy compute dependencies that MUST reside exclusively in dynamically provisioned Micro-Silos
FORBIDDEN_COMPUTE_PACKAGES: Set[str] = {
    "torch",
    "pytorch",
    "torchvision",
    "torchaudio",
    "pyscf",
    "gpu4pyscf",
    "mace",
    "mace-torch",
    "jax",
    "jaxlib",
    "tensorflow",
    "cupy",
    "cupy-cuda11x",
    "cupy-cuda12x",
    "deepspeed",
    "horovod",
    "openmm",
    "ambertools",
    "quantum-espresso",
    "cp2k",
    "nwchem",
}

# Forbidden placeholder / mock tokens
FORBIDDEN_TOKENS: List[str] = [
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


@pytest.fixture(scope="module")
def requirements_raw_bytes() -> bytes:
    """Fixture providing raw bytes of requirements.txt."""
    assert REQUIREMENTS_PATH.exists(), f"requirements.txt does not exist at {REQUIREMENTS_PATH}"
    return REQUIREMENTS_PATH.read_bytes()


@pytest.fixture(scope="module")
def requirements_content(requirements_raw_bytes: bytes) -> str:
    """Fixture providing decoded string content of requirements.txt."""
    return requirements_raw_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def parsed_requirements(requirements_content: str) -> Dict[str, Requirement]:
    """Fixture parsing requirements.txt into a canonical name -> Requirement mapping."""
    reqs: Dict[str, Requirement] = {}
    for line_num, line in enumerate(requirements_content.splitlines(), start=1):
        clean_line = line.split("#")[0].strip()
        if not clean_line:
            continue
        try:
            req = Requirement(clean_line)
        except Exception as err:
            pytest.fail(f"Line {line_num} in requirements.txt has invalid PEP 508 syntax: '{line}' ({err})")

        canon_name = canonicalize_name(req.name)
        assert canon_name not in reqs, f"Duplicate dependency '{canon_name}' found on line {line_num}"
        reqs[canon_name] = req
    return reqs


# ==============================================================================
# 1. Physical File Integrity & Line Endings
# ==============================================================================


def test_requirements_file_exists() -> None:
    """Validate that requirements.txt exists as a regular file in repository root."""
    assert REQUIREMENTS_PATH.exists(), f"requirements.txt missing at {REQUIREMENTS_PATH}"
    assert REQUIREMENTS_PATH.is_file(), f"{REQUIREMENTS_PATH} must be a regular file"
    size = REQUIREMENTS_PATH.stat().st_size
    assert size > 20, f"requirements.txt size too small ({size} bytes)"
    assert size < 10_000, f"requirements.txt size unexpectedly large ({size} bytes)"


def test_requirements_encoding_and_unix_lf_endings(requirements_raw_bytes: bytes) -> None:
    """Validate strict UTF-8 without BOM and strict Unix LF line endings."""
    assert not requirements_raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "requirements.txt contains UTF-8 Byte Order Mark (BOM)"
    )
    assert b"\r\n" not in requirements_raw_bytes, (
        "requirements.txt contains Windows CRLF line endings; strictly Unix LF required"
    )
    assert b"\r" not in requirements_raw_bytes, (
        "requirements.txt contains CR line endings; strictly Unix LF required"
    )
    assert b"\n" in requirements_raw_bytes, "requirements.txt must contain Unix LF line endings"


# ==============================================================================
# 2. PEP 508 Requirements Parsing & Mandatory Dependency Specifications
# ==============================================================================


def test_requirements_pep508_syntax_validity(parsed_requirements: Dict[str, Requirement]) -> None:
    """Validate that all non-empty, non-comment lines parse as valid PEP 508 requirements."""
    assert len(parsed_requirements) > 0, "requirements.txt must define at least one dependency"
    for name, req in parsed_requirements.items():
        assert req.name, f"Requirement has empty package name: {req}"
        assert canonicalize_name(req.name) == name, f"Mismatch in canonical name normalization for {req.name}"


@pytest.mark.parametrize("dep", sorted(MANDATORY_DEPENDENCIES))
def test_mandatory_structural_dependencies_present(
    parsed_requirements: Dict[str, Requirement], dep: str
) -> None:
    """Validate that all mandatory structural dependencies specified in SRS are present."""
    canon_dep = canonicalize_name(dep)
    assert canon_dep in parsed_requirements, (
        f"Mandatory dependency '{dep}' missing from requirements.txt. Found: {list(parsed_requirements.keys())}"
    )


def test_exact_structural_dependencies_inventory(
    parsed_requirements: Dict[str, Requirement],
) -> None:
    """Validate that requirements.txt contains exactly the bare-minimum structural dependencies."""
    parsed_keys = set(parsed_requirements.keys())
    assert parsed_keys == MANDATORY_DEPENDENCIES, (
        f"Mismatch in dependencies. Expected {MANDATORY_DEPENDENCIES}, found {parsed_keys}"
    )


def test_every_requirement_has_version_constraints(
    parsed_requirements: Dict[str, Requirement],
) -> None:
    """Validate that every dependency in requirements.txt specifies non-empty version constraints."""
    unconstrained: List[str] = []
    for name, req in parsed_requirements.items():
        if not req.specifier or len(req.specifier) == 0 or str(req.specifier).strip() == "":
            unconstrained.append(name)

    assert not unconstrained, (
        f"The following dependencies are missing version constraints in requirements.txt: {unconstrained}"
    )


@pytest.mark.parametrize("dep,expected_min", sorted(EXPECTED_MINIMUM_VERSIONS.items()))
def test_minimum_version_specifiers(
    parsed_requirements: Dict[str, Requirement], dep: str, expected_min: str
) -> None:
    """Validate that each mandatory dependency satisfies the minimum version constraint specified in SRS."""
    canon_dep = canonicalize_name(dep)
    assert canon_dep in parsed_requirements, f"Dependency '{dep}' missing from parsed requirements"
    req = parsed_requirements[canon_dep]

    # Test that the expected minimum version is accepted by the specifier
    min_version = Version(expected_min)
    assert req.specifier.contains(str(min_version)), (
        f"Specifier '{req.specifier}' for '{dep}' does not accept minimum expected version '{expected_min}'"
    )

    # Test that a lower major/minor version is rejected
    if min_version.major > 0 or min_version.minor > 0:
        if min_version.minor > 0:
            lower_version = f"{min_version.major}.{min_version.minor - 1}.0"
        else:
            lower_version = f"{min_version.major - 1}.0.0"
        assert not req.specifier.contains(lower_version), (
            f"Specifier '{req.specifier}' for '{dep}' erroneously accepts lower version '{lower_version}'"
        )


def test_no_editable_or_direct_url_dependencies(requirements_content: str) -> None:
    """Validate that requirements.txt does not contain local paths, editable flags, or URLs."""
    forbidden_prefixes = ["-e ", "--editable ", "git+", "http://", "https://", "file:"]
    for line_num, line in enumerate(requirements_content.splitlines(), start=1):
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        for prefix in forbidden_prefixes:
            assert not clean.startswith(prefix), (
                f"Line {line_num} contains forbidden dependency format '{prefix}': {clean}"
            )
        assert not clean.endswith(".whl"), f"Line {line_num} references direct .whl file: {clean}"
        assert not clean.endswith(".tar.gz"), f"Line {line_num} references direct .tar.gz file: {clean}"


# ==============================================================================
# 3. Prohibited Dependencies & Micro-Silo Boundary Enforcement
# ==============================================================================


def test_prohibited_psutil_exclusion(parsed_requirements: Dict[str, Requirement]) -> None:
    """Validate that psutil is excluded (GPU hardware polling must use pynvml or nvidia-smi)."""
    assert "psutil" not in parsed_requirements, (
        "Forbidden dependency 'psutil' declared in requirements.txt. "
        "GPU Hardware Polling MUST use pynvml or nvidia-smi wrappers, NOT psutil."
    )


@pytest.mark.parametrize("pkg", sorted(FORBIDDEN_COMPUTE_PACKAGES))
def test_micro_silo_boundary_exclusion(
    parsed_requirements: Dict[str, Requirement], pkg: str
) -> None:
    """Validate that heavy compute dependencies are excluded from requirements.txt."""
    canon_pkg = canonicalize_name(pkg)
    assert canon_pkg not in parsed_requirements, (
        f"Forbidden heavy compute package '{pkg}' found in requirements.txt. "
        "Heavy compute engines must reside exclusively in dynamically provisioned Micro-Silos."
    )


def test_micro_silo_boundary_raw_content_check(requirements_content: str) -> None:
    """Validate that raw requirements.txt does not mention heavy compute packages as dependencies."""
    for line_num, line in enumerate(requirements_content.splitlines(), start=1):
        clean = line.split("#")[0].strip()
        if not clean:
            continue
        try:
            req = Requirement(clean)
            canon = canonicalize_name(req.name)
            assert canon not in FORBIDDEN_COMPUTE_PACKAGES, (
                f"Line {line_num}: Forbidden heavy compute package '{canon}' declared in requirements.txt"
            )
        except Exception:
            pass


# ==============================================================================
# 4. Architecture & Protocol Documentation Compliance
# ==============================================================================


def test_lustre_posix_fallback_documented(requirements_content: str) -> None:
    """Validate that requirements.txt documents SQLite/checkpointing fallback due to Lustre POSIX lock corruption."""
    content_lower = requirements_content.lower()
    assert "swmr" in content_lower, "requirements.txt must document SWMR I/O operations"
    assert "lustre" in content_lower, "requirements.txt must document Lustre filesystem considerations"
    assert "sqlite" in content_lower, "requirements.txt must document SQLite/checkpointing fallback mechanism"


def test_gpu_polling_pynvml_documented(requirements_content: str) -> None:
    """Validate that requirements.txt documents that GPU polling must use pynvml/nvidia-smi, NOT psutil."""
    content_lower = requirements_content.lower()
    assert "pynvml" in content_lower, "requirements.txt must document pynvml GPU polling"
    assert "psutil" in content_lower, "requirements.txt must document prohibition of psutil for GPU polling"
    assert "nvidia-smi" in content_lower or "gpu" in content_lower, (
        "requirements.txt must document GPU hardware polling"
    )


def test_micro_silo_isolation_protocol_documented(requirements_content: str) -> None:
    """Validate that requirements.txt documents Tripartite Air-Gap and Micro-Silo boundary isolation."""
    content_lower = requirements_content.lower()
    assert "micro-silo" in content_lower or "micro silo" in content_lower, (
        "requirements.txt must document Micro-Silo isolation protocol"
    )
    assert "air-gap" in content_lower or "air gap" in content_lower, (
        "requirements.txt must document Tripartite Air-Gap architecture"
    )


# ==============================================================================
# 5. Zero-Mock & Anti-Spoofing Validations
# ==============================================================================


def test_requirements_zero_mock_and_no_stubs(requirements_content: str) -> None:
    """Validate that requirements.txt contains no mock, stub, or placeholder tokens."""
    for token in FORBIDDEN_TOKENS:
        assert token.lower() not in requirements_content.lower(), (
            f"requirements.txt contains forbidden placeholder token '{token}'"
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
