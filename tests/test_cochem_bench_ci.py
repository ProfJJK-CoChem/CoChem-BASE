"""Migrated BENCH pipeline checks exercise the canonical BASE tools.

Byte-signature samples below are deliberately constructed detector inputs. They
are neither engine calculations nor physical evidence. Old inline reimplementations
and amnesty-bypass acceptance were retired with the duplicated workflow.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from ci_tools.anti_spoof_linter import run_linter
from ci_tools.ci_airgap_sweep import (
    calculate_shannon_entropy,
    check_config_pollution,
    check_qm_log_signatures,
    inspect_file_airgap,
    inspect_magic_number,
    is_xyz_coordinate_payload,
    FORBIDDEN_EXTENSIONS,
)

ROOT = Path(__file__).resolve().parents[1]


def test_canonical_workflow_and_reusable_physical_acceptance():
    path = ROOT / ".github/workflows/cochem_base_ci.yml"
    data = path.read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf") and b"\r\n" not in data
    workflow = yaml.safe_load(data)
    triggers = workflow.get("on", workflow.get(True))
    assert {"push", "pull_request", "workflow_dispatch"} <= triggers.keys()
    jobs = workflow["jobs"]
    assert set(jobs) == {"source-integrity", "ci-plane-contract", "bounded-physical-acceptance", "installed-wheel", "public-ci-scope"}
    assert jobs["installed-wheel"]["needs"] == "source-integrity"
    assert set(jobs["installed-wheel"]["strategy"]["matrix"]["os"]) == {"ubuntu-24.04", "macos-latest", "windows-latest"}
    wheel_commands = "\n".join(step.get("run", "") for step in jobs["installed-wheel"]["steps"])
    assert "scripts.verify_release_ci wheel" in wheel_commands
    assert set(jobs["public-ci-scope"]["needs"]) == set(jobs) - {"public-ci-scope"}
    assert set(jobs["ci-plane-contract"]["strategy"]["matrix"]["os"]) == {"ubuntu-24.04", "macos-latest", "windows-latest"}
    assert jobs["ci-plane-contract"]["strategy"]["fail-fast"] is False
    assert jobs["ci-plane-contract"]["needs"] == "source-integrity"
    assert set(jobs["bounded-physical-acceptance"]["needs"]) == {"source-integrity", "ci-plane-contract"}
    control_steps = jobs["ci-plane-contract"]["steps"]
    python_setup = next(step for step in control_steps if step.get("uses", "").startswith("actions/setup-python@"))
    assert python_setup["with"]["python-version"] == "3.12"
    control_commands = "\n".join(step.get("run", "") for step in control_steps)
    assert "base_ci.py controls" in control_commands
    assert "pip install pytest psutil pyyaml" in control_commands
    assert not any(package in control_commands.lower() for package in ("torch", "pyscf", "openmpi", "orca"))
    assert jobs["bounded-physical-acceptance"]["uses"] == "./.github/workflows/low_compute_acceptance.yml"
    assert "base_ci.py audit" in data.decode()
    assert "continue-on-error" not in data.decode()
    physical = yaml.safe_load((ROOT / ".github/workflows/low_compute_acceptance.yml").read_text())
    assert "workflow_call" in physical.get("on", physical.get(True))
    physical_commands = "\n".join(step.get("run", "") for step in physical["jobs"]["physical-acceptance"]["steps"])
    assert "scripts.verify_release_ci regressions" in physical_commands
    for obsolete in ("ci_scribe.yml", "scribe_ci_cd.yml", "cochem_bench_ci.yml"):
        assert not (ROOT / ".github/workflows" / obsolete).exists()


@pytest.mark.parametrize("header,label", [
    (b"\x89HDF\r\n\x1a\n", "HDF5"),
    (b"SQLite format 3\x00", "SQLite"),
    (b"\x93NUMPY", "NumPy"),
    (b"PAR1", "Parquet"),
    (b"\x7fELF", "ELF"),
    (b"MZ\x90\x00", "PE"),
])
def test_canonical_magic_scanner_rejects_disguised_headers(tmp_path, header, label):
    file = tmp_path / "disguised.dat"
    file.write_bytes(header + bytes(80))
    assert label in inspect_magic_number(file.read_bytes())
    findings, _ = inspect_file_airgap(file, tmp_path, FORBIDDEN_EXTENSIONS, 7.8)
    assert any(v.violation_type == "MAGIC_NUMBER_VIOLATION" for v in findings)


def test_entropy_and_coordinate_detection_uses_canonical_implementation():
    assert calculate_shannon_entropy(b"ordinary source code\n" * 50) < 5.5
    assert calculate_shannon_entropy(bytes(range(256)) * 4) > 7.5
    assert is_xyz_coordinate_payload(b"2\ninput geometry\nH 0 0 0\nH 0 0 0.74\n")
    assert not is_xyz_coordinate_payload(b"ordinary documentation\n")
    assert check_qm_log_signatures(b"ORCA TERMINATED NORMALLY")


def test_canonical_config_pollution_detection(tmp_path):
    config = tmp_path / "cochem_system_config.json"
    config.write_text(json.dumps({"active_jobs": {"job": "running"}, "path": "C:\\Users\\operator\\orca"}))
    assert len(check_config_pollution(config)) >= 2
    config.write_text(json.dumps({"active_jobs": {}, "engines": {}}))
    assert check_config_pollution(config) == []


def test_old_amnesty_cannot_waive_an_executable_mock(tmp_path):
    target = tmp_path / "engine.py"
    target.write_text("import unittest.mock\n", encoding="utf-8")
    (tmp_path / ".anti_spoof_amnesty.json").write_text(json.dumps(["engine.py"]))
    code, findings = run_linter([target], tmp_path)
    assert code == 1 and findings
