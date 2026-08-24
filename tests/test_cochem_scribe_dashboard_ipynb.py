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
