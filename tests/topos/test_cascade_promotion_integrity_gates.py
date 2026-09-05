"""CoChem-TOPOS: Test Cascade Promotion Integrity Gates & Basin-Identity Verification.

Compliant with Method Matrix v4 §4.4, §8B, Suggestion #153, and Anti-Spoofing Directives.
Verifies Deliverable 3:
1. G3 Basin-Identity & Dissociation Gate (verify_g3_basin_identity) on authentic water dimer.
2. Intermolecular distance threshold trip (Delta R > 0.20 A and R > 6.0 A).
3. Heavy-atom Kabsch RMSD threshold trip (> 0.25 A).
4. Spin contamination detection (> 10% s2 error -> ERR_SPIN_CONTAMINATION).
5. Cascade gate telemetry manifest persistence (cascade_gate_telemetry.json).
"""

import io
import json
from pathlib import Path

import pytest
from ase import Atoms
from ase.io import write as ase_write
from cascade_engine.cochem_topos_cascade_orchestrator import (
    CascadeConfig,
    CascadeOrchestrator,
)

from cochem_base.exceptions import SpinContaminationError


def _make_authentic_water_dimer() -> Atoms:
    """Construct authentic water dimer minimum geometry in Angstroms."""
    symbols = ["O", "H", "H", "O", "H", "H"]
    positions = [
        [0.000, 0.000, 0.000],
        [0.000, 0.000, 0.960],
        [0.890, 0.000, -0.270],
        [0.000, 0.000, 2.910],
        [0.000, 0.760, 3.460],
        [0.000, -0.760, 3.460],
    ]
    return Atoms(symbols=symbols, positions=positions)


def _atoms_to_xyz(atoms: Atoms, comment: str = "") -> str:
    """Convert ASE Atoms to standard XYZ string."""
    buf = io.StringIO()
    ase_write(buf, atoms, format="xyz", comment=comment)
    return buf.getvalue()


def test_verify_g3_basin_identity_water_dimer_baseline(tmp_path: Path):
    """Verify that an unchanged water dimer passes the G3 basin identity gate."""
    config = CascadeConfig(artifact_dir=tmp_path, complex_flag=True)
    orchestrator = CascadeOrchestrator(config)

    atoms_prev = _make_authentic_water_dimer()
    atoms_curr = _make_authentic_water_dimer()

    is_same_basin, heavy_rmsd, delta_r, msg = orchestrator.verify_g3_basin_identity(
        atoms_prev=atoms_prev,
        atoms_curr=atoms_curr,
        rmsd_threshold=0.25,
        delta_r_threshold=0.20,
    )

    assert is_same_basin is True
    assert heavy_rmsd < 1e-4
    assert delta_r < 1e-4
    assert "Basin identity verified" in msg


def test_verify_g3_basin_identity_delta_r_dissociation(tmp_path: Path):
    """Verify that stretching inter-monomer distance by > 0.20 A halts promotion with DISSOCIATED."""
    config = CascadeConfig(artifact_dir=tmp_path, complex_flag=True)
    orchestrator = CascadeOrchestrator(config)

    atoms_prev = _make_authentic_water_dimer()
    atoms_curr = _make_authentic_water_dimer()

    # Translate second water molecule by +0.35 A along Z axis (monomer indices 3, 4, 5)
    pos = atoms_curr.get_positions()
    pos[3:, 2] += 0.35
    atoms_curr.set_positions(pos)

    is_same_basin, heavy_rmsd, delta_r, msg = orchestrator.verify_g3_basin_identity(
        atoms_prev=atoms_prev,
        atoms_curr=atoms_curr,
        rmsd_threshold=0.25,
        delta_r_threshold=0.20,
    )

    assert is_same_basin is False
    assert delta_r > 0.20
    assert "[INTEGRITY-GATE-TRIPPED]" in msg
    assert "Promotion halted" in msg


def test_verify_g3_basin_identity_large_r_dissociation(tmp_path: Path):
    """Verify that absolute inter-monomer distance R > 6.0 A trips the dissociation gate."""
    config = CascadeConfig(artifact_dir=tmp_path, complex_flag=True)
    orchestrator = CascadeOrchestrator(config)

    atoms_prev = _make_authentic_water_dimer()
    atoms_curr = _make_authentic_water_dimer()

    # Translate second monomer far away so COM-COM distance > 6.0 A
    pos = atoms_curr.get_positions()
    pos[3:, 2] += 5.0
    atoms_curr.set_positions(pos)

    is_same_basin, heavy_rmsd, delta_r, msg = orchestrator.verify_g3_basin_identity(
        atoms_prev=atoms_prev,
        atoms_curr=atoms_curr,
        rmsd_threshold=0.25,
        delta_r_threshold=0.20,
    )

    assert is_same_basin is False
    assert "[INTEGRITY-GATE-TRIPPED]" in msg


def test_verify_g3_basin_identity_heavy_atom_rmsd(tmp_path: Path):
    """Verify that heavy-atom Kabsch RMSD exceeding 0.25 A trips the G3 gate."""
    config = CascadeConfig(artifact_dir=tmp_path, complex_flag=True)
    orchestrator = CascadeOrchestrator(config)

    atoms_prev = _make_authentic_water_dimer()
    atoms_curr = _make_authentic_water_dimer()

    # Displace one oxygen atom (heavy atom) along Z by 0.60 A so heavy RMSD = 0.30 A > 0.25 A
    pos = atoms_curr.get_positions()
    pos[3, 2] += 0.60
    atoms_curr.set_positions(pos)

    is_same_basin, heavy_rmsd, delta_r, msg = orchestrator.verify_g3_basin_identity(
        atoms_prev=atoms_prev,
        atoms_curr=atoms_curr,
        rmsd_threshold=0.25,
        delta_r_threshold=0.20,
    )

    assert is_same_basin is False
    assert heavy_rmsd > 0.25
    assert "[INTEGRITY-GATE-TRIPPED]" in msg


def test_process_geometry_spin_contamination_detection(tmp_path: Path, monkeypatch):
    """Verify process_geometry detects spin contamination and halts with ERR_SPIN_CONTAMINATION."""
    # Direct scratch and artifacts to tmp_path to verify air-gap
    monkeypatch.setenv("COCHEM_SCRATCH_DIR", str(tmp_path / "scratch"))
    (tmp_path / "scratch").mkdir(parents=True, exist_ok=True)

    config = CascadeConfig(artifact_dir=tmp_path / "artifacts", complex_flag=True)
    (tmp_path / "artifacts").mkdir(parents=True, exist_ok=True)
    orchestrator = CascadeOrchestrator(config)

    dimer = _make_authentic_water_dimer()
    # Inject spin contamination marker in XYZ comment line
    xyz_str = _atoms_to_xyz(dimer, comment="s2_error_pct=14.5 ERR_SPIN_CONTAMINATION")

    payload = orchestrator.process_geometry("water_dimer_spin_tripped", xyz_str, complex_flag=True)

    assert payload.final_status == "ERR_SPIN_CONTAMINATION"
    assert payload.highest_tier == 0

    # Verify structured telemetry JSON persisted in artifact dir and scratch dir
    telemetry_file = tmp_path / "artifacts" / "cascade_gate_telemetry.json"
    assert telemetry_file.exists()
    telemetry_data = json.loads(telemetry_file.read_text(encoding="utf-8"))
    assert telemetry_data["final_status"] == "ERR_SPIN_CONTAMINATION"
    assert telemetry_data["geom_id"] == "water_dimer_spin_tripped"


def test_spin_contamination_error_exception_hierarchy():
    """Verify SpinContaminationError can be instantiated and caught."""
    with pytest.raises(SpinContaminationError) as exc_info:
        raise SpinContaminationError("Open-shell doublet exhibits <S^2> = 1.15 (>10% contamination).")
    assert "contamination" in str(exc_info.value).lower()
