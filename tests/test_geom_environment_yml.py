"""Zero-Mock Test Suite for CoChem-GEOM environment.yml in CoChem-BASE.

Cross-repository contract validation for CoChem-GEOM Conda environment definition:
- Physical file existence, UTF-8 encoding (no BOM), and strict Unix LF line endings.
- Valid YAML syntax parsing via PyYAML (yaml.safe_load).
- Conda environment configuration: name ('cochem-geom'), prioritized channels (pytorch, pyg, conda-forge, nodefaults).
- Python version specification (>=3.10).
- Mandatory runtime dependencies (mendeleev, h5py, scipy, numpy, tqdm, pydantic>=2, pyarrow, plotly, ipywidgets, platformdirs, filelock, rdkit, ase, pytorch, pyg, pyg-lib, torch-scatter, torch-sparse, torch-cluster, hydra-core, omegaconf, pytorch-lightning, lmdb, msgpack-python, torchmetrics, wandb, molsym).
- Quality assurance and developer dependencies (pytest, pytest-cov, ruff, mypy, black).
- C++ ABI synchronization, hardware acceleration, and provenance tags ([E], [D]).
- Mendeleev library dynamic mass resolution contract validation.
- Zero-mock policy and absence of forbidden tokens.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

GEOM_DIR_ENV = os.environ.get("COCHEM_GEOM_DIR")
if GEOM_DIR_ENV:
    GEOM_ROOT = Path(GEOM_DIR_ENV).resolve()
else:
    GEOM_ROOT = Path(__file__).resolve().parent.parent.parent / "CoChem-GEOM"

GEOM_ENV_YML_PATH = GEOM_ROOT / "environment.yml"

REQUIRED_CHANNELS: list[str] = [
    "pytorch",
    "pyg",
    "conda-forge",
    "nodefaults",
]

REQUIRED_RUNTIME_PACKAGES: list[str] = [
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
    "ase",
    "pytorch",
    "pyg",
    "pyg-lib",
    "torch-scatter",
    "torch-sparse",
    "torch-cluster",
    "hydra-core",
    "omegaconf",
    "pytorch-lightning",
    "torchmetrics",
    "wandb",
    "lmdb",
    "msgpack-python",
    "molsym",
]

REQUIRED_DEV_PACKAGES: list[str] = [
    "pytest",
    "pytest-cov",
    "ruff",
    "mypy",
    "black",
]


@pytest.fixture(scope="module")
def geom_env_raw_bytes() -> bytes:
    """Fixture providing raw bytes of CoChem-GEOM environment.yml."""
    assert GEOM_ENV_YML_PATH.exists(), f"CoChem-GEOM environment.yml does not exist at {GEOM_ENV_YML_PATH}"
    return GEOM_ENV_YML_PATH.read_bytes()


@pytest.fixture(scope="module")
def geom_env_content(geom_env_raw_bytes: bytes) -> str:
    """Fixture providing decoded string content of CoChem-GEOM environment.yml."""
    return geom_env_raw_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def geom_env_data(geom_env_content: str) -> dict[str, Any]:
    """Fixture providing parsed YAML dictionary."""
    data = yaml.safe_load(geom_env_content)
    assert isinstance(data, dict), "Parsed YAML root must be a dictionary"
    return data


@pytest.fixture(scope="module")
def all_flattened_dependencies(geom_env_data: dict[str, Any]) -> list[str]:
    """Fixture providing all dependencies flattened from conda and pip sections."""
    deps = geom_env_data.get("dependencies", [])
    flat: list[str] = []
    for item in deps:
        if isinstance(item, str):
            flat.append(item)
        elif isinstance(item, dict) and "pip" in item:
            pip_items = item["pip"]
            if isinstance(pip_items, list):
                for p in pip_items:
                    if isinstance(p, str):
                        flat.append(p)
    return flat


# ==============================================================================
# 1. Physical File Integrity & Line Endings
# ==============================================================================


def test_geom_env_file_exists() -> None:
    """Validate that CoChem-GEOM environment.yml exists as a regular file."""
    assert GEOM_ENV_YML_PATH.exists(), f"CoChem-GEOM environment.yml missing at {GEOM_ENV_YML_PATH}"
    assert GEOM_ENV_YML_PATH.is_file(), f"{GEOM_ENV_YML_PATH} must be a regular file"
    size = GEOM_ENV_YML_PATH.stat().st_size
    assert size >= 100, f"CoChem-GEOM environment.yml size too small ({size} bytes)"
    assert size <= 50_000, f"CoChem-GEOM environment.yml size unexpectedly large ({size} bytes)"


def test_geom_env_encoding_and_unix_lf_endings(geom_env_raw_bytes: bytes) -> None:
    """Validate strict UTF-8 without BOM and strict Unix LF line endings."""
    assert not geom_env_raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "CoChem-GEOM environment.yml contains UTF-8 Byte Order Mark (BOM)"
    )
    assert b"\r\n" not in geom_env_raw_bytes, (
        "CoChem-GEOM environment.yml contains Windows CRLF line endings; strictly Unix LF required"
    )
    assert b"\r" not in geom_env_raw_bytes, (
        "CoChem-GEOM environment.yml contains CR line endings; strictly Unix LF required"
    )
    assert b"\n" in geom_env_raw_bytes, "CoChem-GEOM environment.yml must contain Unix LF line endings"


# ==============================================================================
# 2. YAML Syntax & Top-Level Schema
# ==============================================================================


def test_geom_env_yaml_syntax_validity(geom_env_data: dict[str, Any]) -> None:
    """Validate that CoChem-GEOM environment.yml parses cleanly into required top-level keys."""
    assert "name" in geom_env_data, "Missing 'name' key in CoChem-GEOM environment.yml"
    assert "channels" in geom_env_data, "Missing 'channels' key in CoChem-GEOM environment.yml"
    assert "dependencies" in geom_env_data, "Missing 'dependencies' key in CoChem-GEOM environment.yml"
    assert isinstance(geom_env_data["name"], str), "'name' must be a string"
    assert isinstance(geom_env_data["channels"], list), "'channels' must be a list"
    assert isinstance(geom_env_data["dependencies"], list), "'dependencies' must be a list"


def test_geom_env_name(geom_env_data: dict[str, Any]) -> None:
    """Validate environment name is 'cochem-geom'."""
    assert geom_env_data["name"] == "cochem-geom", (
        f"Expected environment name 'cochem-geom', got '{geom_env_data.get('name')}'"
    )


# ==============================================================================
# 3. Channels Configuration & Priority
# ==============================================================================


def test_geom_env_channels_configuration(geom_env_data: dict[str, Any]) -> None:
    """Validate channel definitions and priority order for C++ ABI resolution."""
    channels = geom_env_data["channels"]
    for req_chan in REQUIRED_CHANNELS:
        assert req_chan in channels, (
            f"Required channel '{req_chan}' missing from channels list: {channels}"
        )

    # PyTorch and PyG channels must be prioritized before conda-forge and nodefaults
    idx_pytorch = channels.index("pytorch")
    idx_pyg = channels.index("pyg")
    idx_forge = channels.index("conda-forge")
    idx_nodefaults = channels.index("nodefaults")

    assert idx_pytorch < idx_forge, "Channel 'pytorch' must precede 'conda-forge' for ABI alignment"
    assert idx_pyg < idx_forge, "Channel 'pyg' must precede 'conda-forge' for ABI alignment"
    assert idx_forge < idx_nodefaults, "Channel 'conda-forge' must precede 'nodefaults'"


# ==============================================================================
# 4. Python Specification & Runtime Dependencies
# ==============================================================================


def test_geom_env_python_version(all_flattened_dependencies: list[str]) -> None:
    """Validate Python version requirement (>=3.10)."""
    python_deps = [d for d in all_flattened_dependencies if d.startswith("python")]
    assert len(python_deps) > 0, "Missing 'python' specification in dependencies"
    python_spec = python_deps[0]
    assert ">=3.10" in python_spec or "=3.10" in python_spec or "==3.10" in python_spec, (
        f"Expected Python >=3.10 specification, got '{python_spec}'"
    )


def test_geom_env_runtime_dependencies(all_flattened_dependencies: list[str]) -> None:
    """Validate that all mandatory scientific runtime dependencies are specified."""
    dep_names = [
        d.split(">=")[0].split("==")[0].split("<=")[0].split("<")[0].split(">")[0].split("=")[0].strip().lower()
        for d in all_flattened_dependencies
    ]

    for req_pkg in REQUIRED_RUNTIME_PACKAGES:
        pkg_lower = req_pkg.lower()
        match_found = False
        if pkg_lower in dep_names:
            match_found = True
        elif pkg_lower == "pytorch" and ("torch" in dep_names or "pytorch" in dep_names):
            match_found = True
        elif pkg_lower == "pyg" and ("torch-geometric" in dep_names or "pyg" in dep_names):
            match_found = True
        elif pkg_lower == "pytorch-lightning" and ("lightning" in dep_names or "pytorch-lightning" in dep_names):
            match_found = True
        elif pkg_lower == "msgpack-python" and ("msgpack" in dep_names or "msgpack-python" in dep_names):
            match_found = True
        elif pkg_lower == "lmdb" and ("python-lmdb" in dep_names or "lmdb" in dep_names):
            match_found = True

        assert match_found, (
            f"Mandatory runtime dependency '{req_pkg}' missing from dependencies: {all_flattened_dependencies}"
        )


def test_geom_env_pydantic_v2_constraint(all_flattened_dependencies: list[str]) -> None:
    """Validate that pydantic is constrained to >=2."""
    pydantic_deps = [d for d in all_flattened_dependencies if d.lower().startswith("pydantic")]
    assert len(pydantic_deps) > 0, "Missing pydantic dependency"
    spec = pydantic_deps[0]
    assert ">=2" in spec or ">= 2" in spec, f"Pydantic must be pinned to >=2, got '{spec}'"


def test_geom_env_pip_section_and_molsym(geom_env_data: dict[str, Any]) -> None:
    """Validate presence of pip subsection and molsym dependency."""
    deps = geom_env_data.get("dependencies", [])
    pip_section = next((item for item in deps if isinstance(item, dict) and "pip" in item), None)
    assert pip_section is not None, "Missing 'pip' subsection under dependencies in environment.yml"
    pip_deps = pip_section["pip"]
    assert isinstance(pip_deps, list), "'pip' subsection must contain a list of dependencies"
    has_molsym = any("molsym" in p.lower() for p in pip_deps)
    assert has_molsym, f"Expected 'molsym' in pip dependencies, found: {pip_deps}"


# ==============================================================================
# 5. Developer & QA Dependencies
# ==============================================================================


def test_geom_env_dev_dependencies(all_flattened_dependencies: list[str]) -> None:
    """Validate developer and test dependencies are included."""
    dep_names = [
        d.split(">=")[0].split("==")[0].split("<=")[0].split("<")[0].split(">")[0].split("=")[0].strip().lower()
        for d in all_flattened_dependencies
    ]
    for req_dev in REQUIRED_DEV_PACKAGES:
        assert req_dev.lower() in dep_names, (
            f"Developer/QA dependency '{req_dev}' missing from environment dependencies: {all_flattened_dependencies}"
        )


# ==============================================================================
# 6. C++ ABI Synchronization & Provenance Tags
# ==============================================================================


def test_geom_env_provenance_and_abi_documentation(geom_env_content: str) -> None:
    """Validate documentation of C++ ABI synchronization and explicit [E] / [D] provenance tags."""
    assert "[E]" in geom_env_content, (
        "environment.yml must include expert estimate provenance tag '[E]' for hardware/ABI speedup bounds"
    )
    assert "[D]" in geom_env_content, (
        "environment.yml must include derived provenance tag '[D]' for configuration reproducibility"
    )
    content_lower = geom_env_content.lower()
    assert "c++ abi" in content_lower or "abi" in content_lower, (
        "environment.yml header comments must document C++ ABI synchronization rationale"
    )
    assert "acceleration" in content_lower or "speedup" in content_lower, (
        "environment.yml header comments must document hardware acceleration bounds"
    )


# ==============================================================================
# 7. Mendeleev Dynamic Atomic Mass Mandate Validation
# ==============================================================================


def test_geom_env_mendeleev_dynamic_mass_mandate(all_flattened_dependencies: list[str]) -> None:
    """Validate mendeleev dependency presence and demonstrate dynamic mass lookup."""
    has_mendeleev = any("mendeleev" in d.lower() for d in all_flattened_dependencies)
    assert has_mendeleev, "'mendeleev' dependency must be declared in environment.yml"

    import mendeleev

    carbon = mendeleev.element("C")
    hydrogen = mendeleev.element("H")
    oxygen = mendeleev.element("O")

    assert carbon.atomic_weight > 12.0 and carbon.atomic_weight < 12.02, (
        f"Unexpected dynamic atomic weight for Carbon: {carbon.atomic_weight}"
    )
    assert hydrogen.atomic_weight > 1.007 and hydrogen.atomic_weight < 1.009, (
        f"Unexpected dynamic atomic weight for Hydrogen: {hydrogen.atomic_weight}"
    )
    assert oxygen.atomic_weight > 15.998 and oxygen.atomic_weight < 16.001, (
        f"Unexpected dynamic atomic weight for Oxygen: {oxygen.atomic_weight}"
    )


# ==============================================================================
# 8. Zero-Mock & Anti-Spoofing Validations
# ==============================================================================


def test_geom_env_zero_mock_and_no_banned_tokens(geom_env_content: str) -> None:
    """Validate that environment.yml contains zero banned/placeholder tokens."""
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
    content_lower = geom_env_content.lower()
    for token in banned_tokens:
        assert token.lower() not in content_lower, (
            f"environment.yml contains forbidden token '{token}'"
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
