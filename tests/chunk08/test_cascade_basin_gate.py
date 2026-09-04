# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Unit test for Deliverable 4 (Suggestion #74):
Basin-Identity & Dissociation Structural Integrity Gates (G3).
Tests process_geometry() with a dissociating complex geometry;
asserts promotion aborts with INTEGRITY-GATE-TRIPPED and status TERMINATED_DISSOCIATED.
Directly verifies verify_g3_basin_identity under Delta R = 0.50 A displacement.
"""

from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path
import pytest
from ase.io import read as ase_read

from cascade_engine.cochem_topos_cascade_orchestrator import (
    CascadeConfig,
    CascadeOrchestrator,
)


def test_cascade_basin_gate_dissociation_abort(caplog: pytest.LogCaptureFixture) -> None:
    """Test process_geometry() with a dissociating geometry;

    assert that promotion to higher tiers aborts with INTEGRITY-GATE-TRIPPED
    and status TERMINATED_DISSOCIATED without fallback loopholes.
    """
    with tempfile.TemporaryDirectory() as td:
        config = CascadeConfig(artifact_dir=Path(td), complex_flag=True)
        orchestrator = CascadeOrchestrator(config)

        # Carbon monoxide dimer with intermolecular separation R ~ 3.5 A
        # Under relaxation, non-equilibrium complex trips G3 basin/dissociation gate
        initial_xyz = (
            "4\n"
            "CO dimer reference\n"
            "C  0.000000  0.000000  0.000000\n"
            "O  0.000000  0.000000  1.128000\n"
            "C  0.000000  0.000000  3.500000\n"
            "O  0.000000  0.000000  4.628000\n"
        )

        with caplog.at_level(logging.WARNING):
            result = orchestrator.process_geometry(
                geom_id="dissociating_complex_01",
                initial_xyz=initial_xyz,
                complex_flag=True,
            )

        # Strictly assert promotion was aborted due to dissociation gate tripping
        assert result.final_status == "TERMINATED_DISSOCIATED"
        assert "[INTEGRITY-GATE-TRIPPED]" in caplog.text


def test_verify_g3_basin_identity_direct() -> None:
    """Direct asymmetric verification of verify_g3_basin_identity gate:

    - Delta R = 0.50 A (> 0.20 A gate) triggers [INTEGRITY-GATE-TRIPPED] and is_same_basin=False
    - Identical geometry yields is_same_basin=True
    """
    with tempfile.TemporaryDirectory() as td:
        config = CascadeConfig(artifact_dir=Path(td), complex_flag=True)
        orchestrator = CascadeOrchestrator(config)

        xyz_base = (
            "4\nCO dimer base\n"
            "C  0.000000  0.000000  0.000000\n"
            "O  0.000000  0.000000  1.128000\n"
            "C  0.000000  0.000000  4.000000\n"
            "O  0.000000  0.000000  5.128000\n"
        )
        xyz_dissoc = (
            "4\nCO dimer dissoc\n"
            "C  0.000000  0.000000  0.000000\n"
            "O  0.000000  0.000000  1.128000\n"
            "C  0.000000  0.000000  4.500000\n"
            "O  0.000000  0.000000  5.628000\n"
        )
        atoms_base = ase_read(io.StringIO(xyz_base), format="xyz")
        atoms_dissoc = ase_read(io.StringIO(xyz_dissoc), format="xyz")

        # Displaced geometry (Delta R = 0.50 A) must fail G3
        is_same_dissoc, rmsd_d, delta_r_d, msg_d = orchestrator.verify_g3_basin_identity(atoms_base, atoms_dissoc)
        assert is_same_dissoc is False
        assert delta_r_d == pytest.approx(0.50, abs=1e-3)
        assert "[INTEGRITY-GATE-TRIPPED]" in msg_d

        # Identical geometry must pass G3
        is_same_ident, rmsd_i, delta_r_i, msg_i = orchestrator.verify_g3_basin_identity(atoms_base, atoms_base.copy())
        assert is_same_ident is True
        assert delta_r_i == pytest.approx(0.0, abs=1e-5)
        assert "Basin identity verified" in msg_i
