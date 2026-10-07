"""Opt-in physical ORCA acceptance; explicitly selecting this file requires ORCA.

The licensed Actions workflow runs the same acceptance script directly. This
test also permits the identical checks on a prepared Linux/WSL/macOS host.
Missing engine authority is a failure, never a successful skipped acceptance.
"""

import json
from pathlib import Path

import pytest

from cochem_base.config_loader import resolve_config_path
from cochem_base.core_engine.execution_authority import RegistryAuthorityViolationError
from scripts.verify_orca import run_acceptance


def test_real_orca_serial_parallel_cli_publication(tmp_path: Path) -> None:
    report = run_acceptance(resolve_config_path(), tmp_path / "orca-acceptance.json")
    assert report["status"] == "passed"
    assert set(report["calculations"]) == {"serial", "parallel"}
    assert report["energy_difference_hartree"] <= 1e-8


def test_missing_engine_authority_is_failed_acceptance(tmp_path: Path) -> None:
    output = tmp_path / "acceptance.json"
    with pytest.raises(RegistryAuthorityViolationError):
        run_acceptance(tmp_path / "absent-registry.json", output)
    report = json.loads(output.read_text())
    assert report["status"] == "failed"
    assert report["calculations"] == {}
    assert report["scientific_accuracy_established"] is False


def test_previous_acceptance_evidence_cannot_be_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "retained-evidence.json"
    output.write_text("retained earlier evidence")
    with pytest.raises(RuntimeError, match="already exists"):
        run_acceptance(tmp_path / "absent-registry.json", output)
    assert output.read_text() == "retained earlier evidence"
