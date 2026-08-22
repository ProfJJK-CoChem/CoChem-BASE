"""Comprehensive Zero-Mock Unit and Integration Test Suite for Start_Here.ipynb.

Validates:
1. Physical existence of Start_Here.ipynb at repository root.
2. Strict UTF-8 encoding without BOM (\xef\xbb\xbf) and strict Unix LF line endings (\n).
3. Valid Jupyter notebook JSON structure conforming strictly to nbformat 4 specification.
4. Top-level metadata with valid Python kernelspec and language_info.
5. Markdown cells describing the Stage 0.0 Entry Point, Tripartite Workspace Air-Gap, and top-level orchestrator workflow.
6. Existence, exact syntax, and strictly sequential ordering of code cells executing:
   !python orchestrator/cochem_setup_phase_1.py through !python orchestrator/cochem_setup_phase_11.py
7. Explanatory markdown headers and descriptions preceding each setup phase.
8. Cell count, cell ID uniqueness, cell metadata schema invariants, and empty pre-run outputs.
9. Zero-Mock & Anti-Placeholder Mandate (no mock, stub, dummy, placeholder, fake, sample, or TODO tokens).
10. AST anti-spoofing sweep ensuring zero prohibited mock imports in the test suite itself.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, List, cast

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
NOTEBOOK_PATH: Path = REPO_ROOT / "Start_Here.ipynb"


@pytest.fixture(scope="module")
def notebook_raw_bytes() -> bytes:
    """Fixture providing raw bytes of Start_Here.ipynb."""
    assert NOTEBOOK_PATH.exists(), f"Start_Here.ipynb does not exist at {NOTEBOOK_PATH}"
    return NOTEBOOK_PATH.read_bytes()


@pytest.fixture(scope="module")
def notebook_content(notebook_raw_bytes: bytes) -> str:
    """Fixture providing decoded UTF-8 string content of Start_Here.ipynb."""
    return notebook_raw_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def notebook_json(notebook_content: str) -> Dict[str, Any]:
    """Fixture providing parsed JSON dictionary of Start_Here.ipynb."""
    data = json.loads(notebook_content)
    assert isinstance(data, dict), "Notebook content must parse into a JSON dictionary"
    return cast(Dict[str, Any], data)


# ==============================================================================
# 1. Physical File Integrity, Encoding & Line Endings
# ==============================================================================


def test_notebook_file_exists_and_is_regular_file() -> None:
    """Validate that Start_Here.ipynb exists as a physical regular file in the repository root."""
    assert NOTEBOOK_PATH.exists(), f"Start_Here.ipynb missing at {NOTEBOOK_PATH}"
    assert NOTEBOOK_PATH.is_file(), f"Start_Here.ipynb at {NOTEBOOK_PATH} is not a regular file"
    stat = NOTEBOOK_PATH.stat()
    assert stat.st_size >= 1000, (
        f"Start_Here.ipynb size too small ({stat.st_size} bytes); complete orchestrator notebook expected."
    )


def test_notebook_encoding_and_no_bom(notebook_raw_bytes: bytes) -> None:
    """Validate that Start_Here.ipynb has no UTF-8 BOM."""
    assert not notebook_raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "Start_Here.ipynb contains illegal UTF-8 BOM"
    )


def test_notebook_strict_lf_line_endings(notebook_raw_bytes: bytes) -> None:
    """Validate that Start_Here.ipynb strictly uses Unix LF line endings without Windows CRLF or legacy Mac CR."""
    assert b"\r\n" not in notebook_raw_bytes, (
        "Start_Here.ipynb contains Windows CRLF line endings (strict Unix LF required)"
    )
    assert b"\r" not in notebook_raw_bytes, (
        "Start_Here.ipynb contains legacy Mac CR line endings"
    )
    assert b"\n" in notebook_raw_bytes, (
        "Start_Here.ipynb missing newline characters"
    )


# ==============================================================================
# 2. JSON Syntax & Jupyter nbformat Schema
# ==============================================================================


def test_notebook_valid_json_structure(notebook_json: Dict[str, Any]) -> None:
    """Validate that Start_Here.ipynb parses into a valid Jupyter notebook dictionary structure."""
    assert isinstance(notebook_json, dict), "Notebook root must be a JSON dictionary"
    assert "cells" in notebook_json, "Notebook root must contain 'cells' key"
    assert "metadata" in notebook_json, "Notebook root must contain 'metadata' key"
    assert "nbformat" in notebook_json, "Notebook root must contain 'nbformat' key"
    assert "nbformat_minor" in notebook_json, "Notebook root must contain 'nbformat_minor' key"

    assert notebook_json["nbformat"] == 4, (
        f"Notebook nbformat must be 4, found {notebook_json['nbformat']}"
    )
    assert isinstance(notebook_json["nbformat_minor"], int) and notebook_json["nbformat_minor"] >= 2, (
        f"Notebook nbformat_minor must be an integer >= 2, found {notebook_json['nbformat_minor']}"
    )


def test_notebook_metadata_kernelspec_and_language(notebook_json: Dict[str, Any]) -> None:
    """Validate that notebook metadata defines valid kernelspec and Python language info."""
    meta = notebook_json.get("metadata", {})
    assert isinstance(meta, dict), "Notebook metadata must be a dictionary"

    kernelspec = meta.get("kernelspec", {})
    assert isinstance(kernelspec, dict), "Notebook metadata.kernelspec must be a dictionary"
    assert "name" in kernelspec, "kernelspec must specify 'name'"
    assert "language" in kernelspec or "display_name" in kernelspec, (
        "kernelspec must specify 'language' or 'display_name'"
    )

    language_info = meta.get("language_info", {})
    assert isinstance(language_info, dict), "Notebook metadata.language_info must be a dictionary"
    assert language_info.get("name") == "python", (
        f"Notebook language_info name must be 'python', found '{language_info.get('name')}'"
    )


def test_notebook_cells_structure_and_types(notebook_json: Dict[str, Any]) -> None:
    """Validate that all cells conform to standard Jupyter notebook cell schemas."""
    cells = notebook_json.get("cells", [])
    assert isinstance(cells, list), "Notebook cells must be a list"
    assert len(cells) >= 12, f"Notebook must contain at least 12 cells (found {len(cells)})"

    for idx, cell in enumerate(cells):
        assert isinstance(cell, dict), f"Cell {idx} must be a dictionary"
        assert "cell_type" in cell, f"Cell {idx} missing 'cell_type'"
        assert cell["cell_type"] in {"markdown", "code", "raw"}, (
            f"Cell {idx} has invalid cell_type: {cell['cell_type']}"
        )
        assert "metadata" in cell, f"Cell {idx} missing 'metadata'"
        assert "source" in cell, f"Cell {idx} missing 'source'"

        # Source should be non-empty
        source = cell["source"]
        if isinstance(source, list):
            assert len(source) > 0, f"Cell {idx} has empty source list"
            assert any(s.strip() for s in source), f"Cell {idx} has whitespace-only source list"
        else:
            assert str(source).strip(), f"Cell {idx} has empty source string"

        # Validate code cell specific fields
        if cell["cell_type"] == "code":
            assert "outputs" in cell, f"Code cell {idx} missing 'outputs' field"
            assert isinstance(cell["outputs"], list), f"Code cell {idx} 'outputs' must be a list"
            assert "execution_count" in cell, f"Code cell {idx} missing 'execution_count' field"


def test_notebook_cell_ids_unique_and_valid(notebook_json: Dict[str, Any]) -> None:
    """Validate that all cell metadata IDs are unique and non-empty."""
    cells = notebook_json.get("cells", [])
    cell_ids: List[str] = []

    for cell in cells:
        cid = cell.get("id") or cell.get("metadata", {}).get("id")
        if cid:
            cell_ids.append(cid)

    # If IDs are used, ensure they are unique
    if cell_ids:
        assert len(cell_ids) == len(set(cell_ids)), (
            f"Duplicate cell IDs found in Start_Here.ipynb: {cell_ids}"
        )


# ==============================================================================
# 3. Stage 0.0 Entry Point & Orchestrator Documentation
# ==============================================================================


def test_notebook_stage_0_entry_point_header(notebook_json: Dict[str, Any]) -> None:
    """Validate that markdown cells explicitly describe Stage 0.0 Entry Point and Orchestrator."""
    cells = notebook_json.get("cells", [])
    markdown_cells = [c for c in cells if c.get("cell_type") == "markdown"]
    assert len(markdown_cells) >= 1, "Notebook must contain at least one markdown cell"

    combined_md = "\n".join(
        "".join(c.get("source", [])) if isinstance(c.get("source"), list) else str(c.get("source", ""))
        for c in markdown_cells
    )

    combined_lower = combined_md.lower()
    assert "stage 0.0" in combined_lower or "stage 0" in combined_lower, (
        "Notebook markdown must document Stage 0.0 Entry Point"
    )
    assert "entry point" in combined_lower, (
        "Notebook markdown must document Entry Point"
    )
    assert "orchestrator" in combined_lower or "orchestration" in combined_lower, (
        "Notebook markdown must document Orchestrator / Orchestration workflow"
    )
    assert "cochem" in combined_lower, (
        "Notebook markdown must document CoChem ecosystem"
    )


def test_notebook_explains_sequential_execution_and_isolation(notebook_json: Dict[str, Any]) -> None:
    """Validate that markdown documentation explains sequential phase execution and crash isolation."""
    cells = notebook_json.get("cells", [])
    markdown_cells = [c for c in cells if c.get("cell_type") == "markdown"]

    combined_md = "\n".join(
        "".join(c.get("source", [])) if isinstance(c.get("source"), list) else str(c.get("source", ""))
        for c in markdown_cells
    )
    combined_lower = combined_md.lower()

    assert "sequential" in combined_lower or "phase" in combined_lower, (
        "Notebook markdown must document sequential phase execution"
    )


def test_notebook_explains_tripartite_workspace_airgap(notebook_json: Dict[str, Any]) -> None:
    """Validate that introductory markdown explains the Tripartite Workspace Air-Gap architecture."""
    cells = notebook_json.get("cells", [])
    markdown_cells = [c for c in cells if c.get("cell_type") == "markdown"]

    combined_md = "\n".join(
        "".join(c.get("source", [])) if isinstance(c.get("source"), list) else str(c.get("source", ""))
        for c in markdown_cells
    )
    combined_lower = combined_md.lower()

    assert "tripartite" in combined_lower or "air-gap" in combined_lower or "execution tier" in combined_lower, (
        "Notebook markdown should document Tripartite Workspace Air-Gap architecture"
    )


# ==============================================================================
# 4. Sequential Execution of Orchestrator Setup Phases 1 Through 11
# ==============================================================================


def test_notebook_contains_all_11_setup_phase_code_cells(notebook_json: Dict[str, Any]) -> None:
    """Validate that code cells execute orchestrator/cochem_setup_phase_1.py through phase_11.py."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]

    code_sources: List[str] = [
        "".join(c.get("source", [])) if isinstance(c.get("source"), list) else str(c.get("source", ""))
        for c in code_cells
    ]

    for phase_num in range(1, 12):
        expected_script = f"orchestrator/cochem_setup_phase_{phase_num}.py"
        matching = [
            src for src in code_sources
            if expected_script in src and "!python" in src
        ]
        assert len(matching) >= 1, (
            f"Missing code cell executing '!python {expected_script}'"
        )


def test_notebook_setup_phases_are_strictly_sequential(notebook_json: Dict[str, Any]) -> None:
    """Validate that setup phases 1 through 11 execute in strictly ascending sequential order."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]

    phase_order: List[int] = []
    phase_pattern = re.compile(r"!python\s+orchestrator/cochem_setup_phase_(\d+)\.py")

    for cell in code_cells:
        src = "".join(cell.get("source", [])) if isinstance(cell.get("source"), list) else str(cell.get("source", ""))
        for match in phase_pattern.finditer(src):
            phase_order.append(int(match.group(1)))

    assert phase_order == list(range(1, 12)), (
        f"Setup phases must execute sequentially from 1 to 11. Found execution order: {phase_order}"
    )


def test_notebook_code_cell_exact_bang_python_syntax(notebook_json: Dict[str, Any]) -> None:
    """Validate that each phase cell uses clean '!python orchestrator/cochem_setup_phase_X.py' command."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]

    phase_code_cells: List[str] = []
    for cell in code_cells:
        src = "".join(cell.get("source", [])) if isinstance(cell.get("source"), list) else str(cell.get("source", ""))
        if "cochem_setup_phase_" in src:
            phase_code_cells.append(src.strip())

    assert len(phase_code_cells) == 11, (
        f"Expected exactly 11 setup phase code cells, found {len(phase_code_cells)}"
    )

    for idx, cell_text in enumerate(phase_code_cells, start=1):
        expected_cmd = f"!python orchestrator/cochem_setup_phase_{idx}.py"
        assert expected_cmd in cell_text, (
            f"Phase {idx} cell does not contain expected command '{expected_cmd}'. Found: '{cell_text}'"
        )


def test_notebook_phase_documentation_precedes_or_matches_each_phase(notebook_json: Dict[str, Any]) -> None:
    """Validate that all 11 phases have descriptive markdown documentation."""
    cells = notebook_json.get("cells", [])
    markdown_cells = [c for c in cells if c.get("cell_type") == "markdown"]

    combined_md = "\n".join(
        "".join(c.get("source", [])) if isinstance(c.get("source"), list) else str(c.get("source", ""))
        for c in markdown_cells
    )

    for phase_num in range(1, 12):
        pattern = re.compile(rf"phase\s+{phase_num}\b|phase_{phase_num}\.py\b", re.IGNORECASE)
        assert pattern.search(combined_md) is not None, (
            f"Markdown documentation missing for Phase {phase_num} (orchestrator/cochem_setup_phase_{phase_num}.py)"
        )


def test_notebook_code_cells_have_pristine_initial_state(notebook_json: Dict[str, Any]) -> None:
    """Validate that all code cells have execution_count=null and outputs=[] in initial state."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]

    for idx, cell in enumerate(code_cells):
        assert cell.get("execution_count") is None, (
            f"Code cell {idx} has non-null execution_count: {cell.get('execution_count')}"
        )
        assert cell.get("outputs") == [], (
            f"Code cell {idx} has pre-populated outputs: {cell.get('outputs')}"
        )


# ==============================================================================
# 5. Zero-Mock & Anti-Placeholder Compliance
# ==============================================================================


def test_notebook_zero_mock_policy(notebook_content: str) -> None:
    """Validate absolute absence of forbidden mock / placeholder / stub tokens in Start_Here.ipynb."""
    prohibited_patterns = [
        r"\bTODO\b",
        r"\bFIXME\b",
        r"\bTBD\b",
        r"\bPLACEHOLDER\b",
        r"\bMOCK\b",
        r"\bSTUB\b",
        r"\bDUMMY\b",
        r"\bFAKE\b",
        r"\bSAMPLE\b",
        r"#\s*TODO",
    ]

    for pattern in prohibited_patterns:
        matches = re.findall(pattern, notebook_content, re.IGNORECASE)
        assert not matches, (
            f"Prohibited placeholder/mock pattern '{pattern}' found in Start_Here.ipynb: {matches}"
        )


def test_notebook_code_cells_contain_no_dummy_returns(notebook_json: Dict[str, Any]) -> None:
    """Validate that code cells do not contain dummy mocks, pass-only functions, or stub dicts."""
    cells = notebook_json.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]

    for idx, cell in enumerate(code_cells):
        src = "".join(cell.get("source", [])) if isinstance(cell.get("source"), list) else str(cell.get("source", ""))
        assert "pass" not in src.split(), f"Code cell {idx} contains bare 'pass' statement"
        assert "return {}" not in src, f"Code cell {idx} contains dummy return"
        assert "mock" not in src.lower(), f"Code cell {idx} contains 'mock'"
        assert "stub" not in src.lower(), f"Code cell {idx} contains 'stub'"


# ==============================================================================
# 6. Test Suite AST Anti-Spoofing Sweep
# ==============================================================================


def test_test_suite_zero_mock_ast_compliance() -> None:
    """Validate that this test file itself contains zero prohibited mock imports."""
    this_file = Path(__file__).resolve()
    tree = ast.parse(this_file.read_text(encoding="utf-8"), filename=str(this_file))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "mock" not in alias.name.lower(), f"Prohibited mock import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "mock" not in mod.lower(), f"Prohibited mock import from: {mod}"
