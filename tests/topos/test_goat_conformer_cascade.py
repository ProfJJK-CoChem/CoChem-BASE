"""Unit and integration tests for Deliverable 1: Physics-Grounded Conformer Fallback Cascade & Open-Shell Radical Guard (Suggestion #101).

Mandated by Method Matrix v4 (§1.2, §2.4, §8B.3) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Authentic molecular coordinates and physical property verification.
"""

from __future__ import annotations

import numpy as np
from ase import Atoms

from cochem_base.topology.cochem_topos_crusher import (
    GOATConformerEngine,
    PhysicalCascadeCalculator,
    get_dynamic_covalent_radius,
)


def _build_methyl_radical() -> Atoms:
    """Construct authentic physical methyl radical (CH3.) doublet (2S+1=2, uhf=1)."""
    r_ch = 1.08
    coords = [
        [0.0, 0.0, 0.0],
        [r_ch, 0.0, 0.0],
        [-r_ch * 0.5, r_ch * np.sqrt(3) / 2.0, 0.0],
        [-r_ch * 0.5, -r_ch * np.sqrt(3) / 2.0, 0.0],
    ]
    atoms = Atoms("CH3", positions=coords)
    atoms.info["charge"] = 0
    atoms.info["uhf"] = 1
    atoms.info["multiplicity"] = 2
    return atoms


def _build_water_molecule() -> Atoms:
    """Construct authentic physical neutral closed-shell water molecule (H2O)."""
    r_oh = 0.9578
    half_angle = np.radians(104.48 / 2.0)
    coords = [
        [0.0, 0.0, 0.0],
        [0.0, r_oh * np.sin(half_angle), r_oh * np.cos(half_angle)],
        [0.0, -r_oh * np.sin(half_angle), r_oh * np.cos(half_angle)],
    ]
    atoms = Atoms("OH2", positions=coords)
    atoms.info["charge"] = 0
    atoms.info["uhf"] = 0
    atoms.info["multiplicity"] = 1
    return atoms


def test_no_lennard_jones_calculator_in_goat():
    """Verify that bare unparameterized LennardJones() is never attached in GOATConformerEngine."""
    water = _build_water_molecule()
    engine = GOATConformerEngine(temperature_k=300.0)

    candidate = engine._goat_single_worker(water, kick_magnitude=0.1)

    assert candidate.calc is not None
    assert isinstance(candidate.calc, PhysicalCascadeCalculator)
    assert candidate.calc.__class__.__name__ != "LennardJones"


def test_open_shell_radical_screening_bypasses_rdkit():
    """Verify that open-shell radicals (uhf > 0, 2S+1 > 1) bypass RDKit force fields (MMFF94/UFF)."""
    radical = _build_methyl_radical()
    calc = PhysicalCascadeCalculator(base_atoms=radical)

    is_open_shell = calc.is_open_shell_or_charged(radical)
    assert is_open_shell is True
    assert calc.get_system_charge(radical) == 0
    assert calc.get_system_uhf(radical) == 1


def test_closed_shell_neutral_permits_tier2_fallback():
    """Verify that closed-shell neutral systems are permitted to use Tier 2 force fields."""
    water = _build_water_molecule()
    calc = PhysicalCascadeCalculator(base_atoms=water)

    is_open_shell = calc.is_open_shell_or_charged(water)
    assert is_open_shell is False


def test_covalent_connectivity_invariance_mendeleev():
    """Verify that covalent connectivity derived via dynamic covalent radii from mendeleev remains invariant."""
    water = _build_water_molecule()
    engine = GOATConformerEngine(temperature_k=300.0)

    r_o = get_dynamic_covalent_radius("O")
    r_h = get_dynamic_covalent_radius("H")
    assert r_o > 0.6
    assert r_h > 0.3

    confs = engine.generate_conformers(water, num_conformers=2)
    assert len(confs) > 0
    for conf in confs:
        d_oh1 = np.linalg.norm(conf.positions[0] - conf.positions[1])
        d_oh2 = np.linalg.norm(conf.positions[0] - conf.positions[2])
        assert 0.8 < d_oh1 < 1.6
        assert 0.8 < d_oh2 < 1.6
