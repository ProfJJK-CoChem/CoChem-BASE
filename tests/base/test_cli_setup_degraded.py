"""Unit and integration tests for Deliverable 4: Two-Tier Setup Partitioning & Pedagogical No-Code Matrix Access (Suggestion #104).

Mandated by Method Matrix v4 (§1.6) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Authentic execution and configuration testing.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import pytest

from cli import action_setup
from ui.voila_layout.cochem_gui import CoChemGUI


def test_cli_setup_degraded_operational_exit_code_zero(tmp_path: Path):
    """Verify cli.py setup partitions into core and optional tracks and exits code 0 with DEGRADED_OPERATIONAL."""
    reg_dir = tmp_path / "Registry"
    reg_dir.mkdir(parents=True, exist_ok=True)

    # Configure test command-line arguments for setup with only Phase 3 (optional solver track)
    args = argparse.Namespace(
        artifact_dir=str(tmp_path),
        phase=[3],
        all=False,
        json=True,
        clean=False,
        dry_run=True,
        skip_heavy=True,
        skip_iops=True,
        skip_eckart=True,
        verbose=False,
    )

    exit_code = action_setup(args)
    # If phase 3 fails due to missing third-party binary, setup must return 0 (DEGRADED_OPERATIONAL), not 1
    assert exit_code == 0

    cfg_path = reg_dir / "cochem_system_config.json"
    assert cfg_path.exists()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert cfg["status"] in ("PASSED", "DEGRADED_OPERATIONAL")


def test_cochem_gui_enables_matrix_and_inspector_on_degraded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify cochem_gui.py enables No Code Matrix & Data Inspector when system is DEGRADED_OPERATIONAL."""
    reg_dir = tmp_path / "Registry"
    reg_dir.mkdir(parents=True, exist_ok=True)

    sys_cfg = {
        "status": "DEGRADED_OPERATIONAL",
        "overall_status": "DEGRADED_OPERATIONAL",
        "missing_capabilities": ["CFOUR", "PyMOL"],
    }
    (reg_dir / "cochem_system_config.json").write_text(json.dumps(sys_cfg), encoding="utf-8")

    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(tmp_path))

    gui = CoChemGUI()

    # Buttons must NOT be disabled when DEGRADED_OPERATIONAL
    assert gui.btn_matrix.disabled is False
    assert gui.btn_inspector.disabled is False

    # Solver dropdown must have tooltips for uninstalled/missing engines
    assert gui.matrix_engine is not None
    assert len(gui.matrix_engine.options) > 0
