"""Unit and integration tests for Deliverable 2: Dual-Interface In-Memory xTB-Python Evaluation & Radical Handling (Suggestion #102).

Mandated by Method Matrix v4 (§1.2, §8B.3) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Authentic molecular coordinates and real execution pathways.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ase import Atoms

from Libraries.cochem_torq_delta_ml import GFN2Result, GFN2xTBEngine


def _build_water_radical_cation() -> Atoms:
    """Construct authentic physical H2O.+ radical cation (charge=1, uhf=1, multiplicity=2)."""
    # Authentic C2v geometry
    coords = [
        [0.0, 0.0, 0.0],
        [0.0, 0.81649, 0.57735],
        [0.0, -0.81649, 0.57735],
    ]
    atoms = Atoms("OH2", positions=coords)
    atoms.info["charge"] = 1
    atoms.info["uhf"] = 1
    atoms.info["multiplicity"] = 2
    return atoms


def test_xtb_engine_accepts_charge_and_uhf(tmp_path: Path):
    """Verify that GFN2xTBEngine.calculate() accepts explicit charge, uhf, and scratch_dir."""
    engine = GFN2xTBEngine()
    atoms = _build_water_radical_cation()

    # Verify electron parity check passes for radical cation
    valid = engine.validate_electron_parity(atoms, charge=1, multiplicity=2)
    assert valid is True

    # Call calculate with explicit charge and uhf
    custom_scratch = tmp_path / "custom_scratch"
    custom_scratch.mkdir(parents=True, exist_ok=True)

    res = engine.calculate(
        atoms=atoms,
        charge=1,
        uhf=1,
        scratch_dir=custom_scratch,
    )

    assert isinstance(res, GFN2Result)
    assert hasattr(res, "energy_ev")
    assert hasattr(res, "forces")
    assert res.charge == 1
    assert res.uhf == 1

    # Verify no residual scratch artifacts leak into current working directory (T_src)
    cwd = Path.cwd()
    for leaked in ["charges", "wbo", "xtbopt.xyz", ".xtbtopo.mol", "xtbrestart", "gradient"]:
        assert not (cwd / leaked).exists(), f"Leaked temporary file {leaked} in T_src!"


def test_electron_parity_validation_guards():
    """Verify that unphysical electron-spin parity combinations are rejected."""
    engine = GFN2xTBEngine()
    water = Atoms("OH2", positions=[[0, 0, 0], [0, 0, 1], [0, 1, 0]])

    # Neutral water has 8 + 1 + 1 = 10 electrons (even). Multiplicity 2 (uhf=1) violates parity: (10 - 1) % 2 != 0
    with pytest.raises(ValueError, match="Electron parity violation"):
        engine.validate_electron_parity(water, charge=0, multiplicity=2)

    # Radical cation: 10 - 1 = 9 electrons (odd). Multiplicity 2 (uhf=1) is valid: (9 - 1) % 2 == 0
    assert engine.validate_electron_parity(water, charge=1, multiplicity=2) is True
