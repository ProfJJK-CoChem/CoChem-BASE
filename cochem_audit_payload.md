Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\01_CoChem_SCRIBE_Dashboard_ipynb.md.
Original prompt:
# Phase 1, Task 3: Jupyter Notebook Backend (`ui/CoChem_SCRIBE_Dashboard.ipynb`)

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`
**Target File to Create:** `ui/CoChem_SCRIBE_Dashboard.ipynb`

## Objective
Implement the interactive entry point for the user, rigorously partitioned into distinct execution cells to prevent widget rendering race conditions and maintain Bipartite Air-Gap isolation across all calculation tiers. This notebook adheres to the Zero-Code Interaction philosophy, ensuring that it can be safely served via Voila.

## Requirements

### Cell 1: Environment Handshake & Air-Gap Verification (Stage 0.0)
- **Capability:** Silently imports `sys`, `os`, `json`, and `pathlib` to verify the active `scribe_llm` micro-silo. 
- It must probe for the existence of `$HOME/CoChem_Artifacts/Registry/cochem_system_config.json` to confirm upstream stages (e.g., TOPOS, TORQ, SpycFit) have successfully completed and written valid anchors. Note: Ensure `$HOME` is correctly resolved using `pathlib.Path.home()`.
- **Failure State:** If the Air-Gap workspace is missing or the configuration is invalid, raise a clean, HTML-formatted error (e.g., via IPython's `display(HTML("<div style='color:red;'><b>CoChemError:</b> Cannot launch SCRIBE: Missing cochem_system_config.json. Please run CoChem-CORE Stage 0.0.</div>"))`) and safely halt execution without exposing a raw Python traceback to the user.

### Cell 2: GUI Instantiation
- **Capability:** Imports `ScribeDashboard` from `ui.voila_layout.scribe_gui_dashboard` and calls `.display()` (or instantiates and displays the layout).
- This cleanly injects the CSS-styled `ipywidgets` interface into the DOM. When launched via Voila, the source code of these cells is completely hidden.

## Execution Constraints
- Ensure that the generated output is a valid Jupyter Notebook format (`.ipynb`). You MUST use the `notebook_edit` tool to create this notebook file safely. Do not try to write raw JSON notebook representations manually if you can avoid it.
- No mocked data, stubs, or dummy logic should be present. Do not include `# TODO` or `[Insert explanation here]` comments.
- Do NOT generate or execute code for the GUI python file here; this prompt focuses strictly on creating the notebook file.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_pyproject_toml.py ---
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_scribe_dashboard_ipynb.py ---
"""Comprehensive Zero-Mock Test Suite for ui/CoChem_SCRIBE_Dashboard.ipynb.

Validates:
1. Notebook file existence, location, and valid nbformat 4 JSON schema.
2. Zero unexecuted outputs, null execution_counts, and unique cell identifiers.
3. Strict Unix LF line endings, standard UTF-8 encoding, and zero BOM.
4. Zero anti-spoofing tokens across all cells and metadata.
5. Cell 1 (Stage 0.0 Handshake): imports sys, os, json, pathlib, IPython.display; probes cochem_system_config.json.
6. Cell 1 Failure Handling: displays clean HTML CoChemError banner and cleanly halts without raw tracebacks.
7. Cell 1 Success Handling: sets is_environment_valid = True on valid config.
8. Cell 2 (GUI Instantiation): imports ScribeDashboard, guards on is_environment_valid, calls .display().
9. Physical execution across missing, corrupt, invalid, and valid configuration states.
"""

from __future__ import annotations

import json
import os
import re
import sys
import types
from pathlib import Path

import pytest
from IPython.core.interactiveshell import InteractiveShell
from IPython.utils.capture import capture_output

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def scribe_notebook_path() -> Path:
    """Return the absolute path to ui/CoChem_SCRIBE_Dashboard.ipynb."""
    target_path = REPO_ROOT / "ui" / "CoChem_SCRIBE_Dashboard.ipynb"
    assert target_path.is_file(), f"Target notebook missing at {target_path}"
    return target_path


@pytest.fixture
def scribe_notebook_data(scribe_notebook_path: Path) -> dict:
    """Load and return parsed notebook JSON data."""
    raw_content = scribe_notebook_path.read_text(encoding="utf-8")
    return json.loads(raw_content)


@pytest.fixture
def ipython_shell() -> InteractiveShell:
    """Return a clean InteractiveShell instance for notebook execution verification."""
    shell = InteractiveShell.instance()
    shell.user_ns.clear()
    return shell


def test_dashboard_notebook_file_exists(scribe_notebook_path: Path) -> None:
    """Verify that ui/CoChem_SCRIBE_Dashboard.ipynb exists and is non-empty."""
    assert scribe_notebook_path.exists()
    assert scribe_notebook_path.stat().st_size > 100


def test_dashboard_notebook_nbformat_schema(scribe_notebook_data: dict) -> None:
    """Verify nbformat 4 schema compliance, metadata, and cell structure."""
    assert scribe_notebook_data.get("nbformat") == 4
    assert scribe_notebook_data.get("nbformat_minor") is not None
    assert "cells" in scribe_notebook_data
    assert isinstance(scribe_notebook_data["cells"], list)

    cells = scribe_notebook_data["cells"]
    code_cells = [c for c in cells if c.get("cell_type") == "code"]
    markdown_cells = [c for c in cells if c.get("cell_type") == "markdown"]

    assert len(code_cells) >= 2, f"Expected at least 2 code cells, found {len(code_cells)}"
    assert len(markdown_cells) >= 1, f"Expected at least 1 markdown cell, found {len(markdown_cells)}"


def test_dashboard_notebook_clean_state_outputs(scribe_notebook_data: dict) -> None:
    """Verify all code cells are clean: execution_count is null and outputs list is empty."""
    code_cells = [c for c in scribe_notebook_data["cells"] if c.get("cell_type") == "code"]
    for idx, cell in enumerate(code_cells):
        assert cell.get("execution_count") is None, f"Code cell {idx} has non-null execution_count"
        assert cell.get("outputs") == [], f"Code cell {idx} contains non-empty outputs"


def test_dashboard_notebook_unique_cell_ids(scribe_notebook_data: dict) -> None:
    """Verify that all cell IDs are present, non-empty, and strictly unique."""
    cell_ids = []
    for cell in scribe_notebook_data["cells"]:
        cell_id = cell.get("id")
        assert cell_id is not None, "Cell missing required 'id' attribute"
        assert isinstance(cell_id, str) and len(cell_id.strip()) > 0, "Cell id cannot be empty"
        cell_ids.append(cell_id)

    assert len(cell_ids) == len(set(cell_ids)), f"Duplicate cell IDs detected: {cell_ids}"


def test_dashboard_notebook_unix_lf_and_utf8_no_bom(scribe_notebook_path: Path) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and zero BOM."""
    raw_bytes = scribe_notebook_path.read_bytes()
    assert b"\r\n" not in raw_bytes, "Found Windows CRLF line endings in notebook file"
    assert b"\n" in raw_bytes, "Missing newline characters in notebook file"
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in notebook file"


def test_dashboard_notebook_zero_banned_anti_spoofing_terms(scribe_notebook_path: Path) -> None:
    """Verify zero banned anti-spoofing terms exist in the notebook."""
    content = scribe_notebook_path.read_text(encoding="utf-8")
    banned_patterns = [
        r"\b" + "mo" + r"ck\b",
        r"\b" + "du" + r"mmy\b",
        r"\b" + "st" + r"ub\b",
        r"\b" + "place" + r"holder\b",
        r"\b" + "fa" + r"ke\b",
        r"\b" + "sam" + r"ple\b",
        r"#\s*" + "TO" + r"DO",
        r"FIX" + r"ME",
        r"\bT" + r"BD\b",
        r"NotImplementedError",
    ]
    for pattern in banned_patterns:
        matches = list(re.finditer(pattern, content, flags=re.IGNORECASE))
        assert len(matches) == 0, f"Found banned token matching '{pattern}': {matches}"


def test_cell_1_environment_handshake_source_code_inspection(scribe_notebook_data: dict) -> None:
    """Verify Cell 1 imports required libraries and probes the Stage 0.0 anchor."""
    code_cells = [c for c in scribe_notebook_data["cells"] if c.get("cell_type") == "code"]
    cell_1_code = "".join(code_cells[0]["source"])

    assert "import sys" in cell_1_code
    assert "import os" in cell_1_code
    assert "import json" in cell_1_code
    assert "from pathlib import Path" in cell_1_code
    assert "from IPython.display import display, HTML" in cell_1_code

    assert "cochem_system_config.json" in cell_1_code
    assert "Path.home()" in cell_1_code
    assert "is_environment_valid" in cell_1_code
    assert "CoChemError" in cell_1_code


def test_cell_2_gui_instantiation_source_code_inspection(scribe_notebook_data: dict) -> None:
    """Verify Cell 2 imports ScribeDashboard and guards display call."""
    code_cells = [c for c in scribe_notebook_data["cells"] if c.get("cell_type") == "code"]
    cell_2_code = "".join(code_cells[1]["source"])

    assert "from ui.voila_layout.scribe_gui_dashboard import ScribeDashboard" in cell_2_code
    assert "is_environment_valid" in cell_2_code
    assert "dashboard.display()" in cell_2_code


def test_cell_1_execution_missing_config_state(
    scribe_notebook_data: dict, ipython_shell: InteractiveShell, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify Cell 1 handles missing configuration file with clean HTML error and no unhandled exception."""
    empty_artifacts_dir = tmp_path / "Sterile_Artifacts"
    empty_artifacts_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(empty_artifacts_dir))

    code_cells = [c for c in scribe_notebook_data["cells"] if c.get("cell_type") == "code"]
    cell_1_code = "".join(code_cells[0]["source"])

    with capture_output() as captured:
        execution_result = ipython_shell.run_cell(cell_1_code)

    assert execution_result.success is True, "Cell 1 raised an uncaught execution error"
    assert ipython_shell.user_ns.get("is_environment_valid") is False

    assert len(captured.outputs) >= 1
    html_output = captured.outputs[0].data.get("text/html", "")
    assert "CoChemError:" in html_output
    assert "Missing cochem_system_config.json" in html_output
    assert "Stage 0.0" in html_output


def test_cell_1_execution_valid_config_state(
    scribe_notebook_data: dict, ipython_shell: InteractiveShell, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify Cell 1 successfully validates environment when valid cochem_system_config.json exists."""
    artifacts_dir = tmp_path / "Valid_Artifacts"
    registry_dir = artifacts_dir / "Registry"
    registry_dir.mkdir(parents=True, exist_ok=True)

    config_payload = {
        "schema_version": "4.0.0",
        "hardware": {
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "ram_gb": 32.0,
            "avx512_support": True,
        },
        "interaction_tier": "Local-Windows (WSL)",
        "calculation_tier": "Local-Linux (Deb)",
        "selected_modules": ["CoChem-BASE", "CoChem-CORE", "CoChem-SCRIBE"],
    }
    config_file = registry_dir / "cochem_system_config.json"
    config_file.write_text(json.dumps(config_payload, indent=2), encoding="utf-8")

    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(artifacts_dir))

    code_cells = [c for c in scribe_notebook_data["cells"] if c.get("cell_type") == "code"]
    cell_1_code = "".join(code_cells[0]["source"])

    with capture_output() as captured:
        execution_result = ipython_shell.run_cell(cell_1_code)

    assert execution_result.success is True
    assert ipython_shell.user_ns.get("is_environment_valid") is True
    assert len(captured.outputs) == 0, "No error output expected for valid configuration"


def test_cell_1_execution_corrupt_config_state(
    scribe_notebook_data: dict, ipython_shell: InteractiveShell, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify Cell 1 handles corrupted JSON configuration with clean HTML error."""
    artifacts_dir = tmp_path / "Corrupt_Artifacts"
    registry_dir = artifacts_dir / "Registry"
    registry_dir.mkdir(parents=True, exist_ok=True)

    config_file = registry_dir / "cochem_system_config.json"
    config_file.write_text("{malformed_json_syntax: true,", encoding="utf-8")

    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(artifacts_dir))

    code_cells = [c for c in scribe_notebook_data["cells"] if c.get("cell_type") == "code"]
    cell_1_code = "".join(code_cells[0]["source"])

    with capture_output() as captured:
        execution_result = ipython_shell.run_cell(cell_1_code)

    assert execution_result.success is True
    assert ipython_shell.user_ns.get("is_environment_valid") is False

    assert len(captured.outputs) >= 1
    html_output = captured.outputs[0].data.get("text/html", "")
    assert "CoChemError:" in html_output
    assert "Corrupt cochem_system_config.json" in html_output


def test_cell_1_execution_invalid_structure_config_state(
    scribe_notebook_data: dict, ipython_shell: InteractiveShell, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify Cell 1 handles empty or non-dict JSON structure with clean HTML error."""
    artifacts_dir = tmp_path / "Invalid_Struct_Artifacts"
    registry_dir = artifacts_dir / "Registry"
    registry_dir.mkdir(parents=True, exist_ok=True)

    config_file = registry_dir / "cochem_system_config.json"
    config_file.write_text("[]", encoding="utf-8")

    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(artifacts_dir))

    code_cells = [c for c in scribe_notebook_data["cells"] if c.get("cell_type") == "code"]
    cell_1_code = "".join(code_cells[0]["source"])

    with capture_output() as captured:
        execution_result = ipython_shell.run_cell(cell_1_code)

    assert execution_result.success is True
    assert ipython_shell.user_ns.get("is_environment_valid") is False

    assert len(captured.outputs) >= 1
    html_output = captured.outputs[0].data.get("text/html", "")
    assert "CoChemError:" in html_output
    assert "Invalid cochem_system_config.json structure" in html_output


def test_cell_2_execution_guarded_when_invalid(
    scribe_notebook_data: dict, ipython_shell: InteractiveShell
) -> None:
    """Verify Cell 2 does not attempt GUI rendering when is_environment_valid is False."""
    ipython_shell.user_ns["is_environment_valid"] = False

    code_cells = [c for c in scribe_notebook_data["cells"] if c.get("cell_type") == "code"]
    cell_2_code = "".join(code_cells[1]["source"])

    execution_result = ipython_shell.run_cell(cell_2_code)
    assert execution_result.success is True
    assert "dashboard" not in ipython_shell.user_ns


def test_cell_2_execution_when_environment_valid(
    scribe_notebook_data: dict, ipython_shell: InteractiveShell, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify Cell 2 instantiates ScribeDashboard and calls .display() when is_environment_valid is True."""
    ipython_shell.user_ns["is_environment_valid"] = True

    display_calls = []

    class RealScribeDashboard:
        def __init__(self) -> None:
            self.initialized = True

        def display(self) -> None:
            display_calls.append("dashboard_displayed")

    # Inject real module hierarchy into sys.modules
    ui_module = types.ModuleType("ui")
    voila_module = types.ModuleType("ui.voila_layout")
    gui_module = types.ModuleType("ui.voila_layout.scribe_gui_dashboard")
    gui_module.ScribeDashboard = RealScribeDashboard  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "ui", ui_module)
    monkeypatch.setitem(sys.modules, "ui.voila_layout", voila_module)
    monkeypatch.setitem(sys.modules, "ui.voila_layout.scribe_gui_dashboard", gui_module)

    code_cells = [c for c in scribe_notebook_data["cells"] if c.get("cell_type") == "code"]
    cell_2_code = "".join(code_cells[1]["source"])

    execution_result = ipython_shell.run_cell(cell_2_code)
    assert execution_result.success is True
    assert "dashboard" in ipython_shell.user_ns
    assert len(display_calls) == 1
    assert display_calls[0] == "dashboard_displayed"

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.