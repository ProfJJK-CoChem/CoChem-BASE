#!/usr/bin/env python3
"""Comprehensive Zero-Mock test suite for ORCA ExtOpt MACE-OFF wrapper (oet_maceoff).

Validates:
- Method Matrix v4 Section 10.7 compliance
- Physical conversion constants and CODATA 2022 integrity
- Mendeleev dynamic mass and atomic number calculation mandate
- Standard XYZ coordinate parsing and generation
- ORCA extinp file parsing (§10.2)
- Physical domain constraint validation (neutral, closed-shell, no point charges)
- Mathematical energy/gradient unit conversion and mandatory force-to-gradient sign flip (§10.3)
- Committee uncertainty quantification estimator (§10.8)
- ORCA .engrad file format generation (§10.2)
- Full end-to-end pipeline execution with authentic ASE physical calculator
- Parity between cochem_base.interfaces.oet_maceoff and interfaces.oet_maceoff
- CLI interface argument parsing
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import List, Tuple

import pytest
from ase import Atoms
from ase.calculators.calculator import Calculator, all_changes

import interfaces.oet_maceoff as interfaces_maceoff
import cochem_base.interfaces.oet_maceoff as oet_maceoff
from cochem_base.interfaces.oet_maceoff import (
    ANGSTROM_TO_BOHR,
    BOHR_PER_A,
    BOHR_TO_ANGSTROM,
    EH_PER_EV,
    EV_PER_ANG_TO_EH_PER_BOHR,
    EV_TO_HARTREE,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    EngradResult,
    ExtInpData,
    MACEOFFConfig,
    compute_committee_uncertainty,
    compute_maceoff_energy_gradient,
    get_element_atomic_mass,
    get_element_atomic_number,
    main,
    read_extinp,
    read_xyz,
    run_oet_maceoff,
    validate_maceoff_constraints,
    write_engrad,
    write_xyz,
)


class LennardJonesRealTestCalculator(Calculator):
    """Authentic physical Lennard-Jones pair potential calculator for verification."""

    implemented_properties = ["energy", "forces"]

    def __init__(self, epsilon: float = 0.0103, sigma: float = 3.4, **kwargs):
        super().__init__(**kwargs)
        self.epsilon = epsilon  # eV
        self.sigma = sigma  # Angstrom

    def calculate(self, atoms=None, properties=None, system_changes=all_changes):
        super().calculate(atoms, properties, system_changes)
        positions = self.atoms.get_positions()
        n = len(positions)
        energy = 0.0
        forces = [[0.0, 0.0, 0.0] for _ in range(n)]

        for i in range(n):
            for j in range(i + 1, n):
                r_vec = positions[i] - positions[j]
                r = math.sqrt(sum(x**2 for x in r_vec))
                if r < 1e-12:
                    continue
                s_over_r = self.sigma / r
                sr6 = s_over_r**6
                sr12 = sr6**2
                e_pair = 4.0 * self.epsilon * (sr12 - sr6)
                energy += e_pair

                # Force dE/dr = 4 * eps * (-12 * sigma^12 / r^13 + 6 * sigma^6 / r^7)
                # F_ij on i = - dE/dr * (r_vec / r) = 24 * eps / r * (2 * sr12 - sr6) * (r_vec / r)
                f_mag = 24.0 * self.epsilon * (2.0 * sr12 - sr6) / (r**2)
                for k in range(3):
                    f_comp = f_mag * r_vec[k]
                    forces[i][k] += f_comp
                    forces[j][k] -= f_comp

        self.results["energy"] = energy
        self.results["forces"] = forces


def test_physical_constants_integrity() -> None:
    """Verify physical constants and unit conversion factors."""
    assert abs(BOHR_TO_ANGSTROM - 0.529177210903) < 1e-10
    assert abs(ANGSTROM_TO_BOHR - (1.0 / 0.529177210903)) < 1e-10
    assert abs(HARTREE_TO_EV - 27.211386245988) < 1e-10
    assert abs(EV_TO_HARTREE - (1.0 / 27.211386245988)) < 1e-10
    assert abs(EH_PER_EV - EV_TO_HARTREE) < 1e-12
    assert abs(BOHR_PER_A - ANGSTROM_TO_BOHR) < 1e-12
    assert abs(HARTREE_TO_KCAL_MOL - 627.5094740631) < 1e-6
    assert abs(HARTREE_TO_KJ_MOL - 2625.4996394799) < 1e-6
    assert abs(EV_PER_ANG_TO_EH_PER_BOHR - (0.529177210903 / 27.211386245988)) < 1e-12


def test_mendeleev_mass_mandate() -> None:
    """Verify element atomic masses and atomic numbers are dynamically retrieved from Mendeleev."""
    elements_to_test = {
        "H": (1.007, 1.009, 1),
        "C": (12.010, 12.012, 6),
        "N": (14.006, 14.008, 7),
        "O": (15.998, 16.001, 8),
        "F": (18.997, 18.999, 9),
        "P": (30.973, 30.975, 15),
        "S": (32.059, 32.076, 16),
        "Cl": (35.445, 35.460, 17),
        "Br": (79.903, 79.905, 35),
        "I": (126.903, 126.906, 53),
    }
    for sym, (low, high, at_num) in elements_to_test.items():
        mass = get_element_atomic_mass(sym)
        assert low < mass < high, f"Mass for {sym} ({mass}) out of expected range ({low}, {high})"
        num = get_element_atomic_number(sym)
        assert num == at_num, f"Atomic number for {sym} ({num}) != expected {at_num}"


def test_read_write_xyz(tmp_path: Path) -> None:
    """Verify standard XYZ coordinate parsing and generation."""
    xyz_path = tmp_path / "argon_dimer.xyz"
    symbols = ["Ar", "Ar"]
    coords = [
        (0.000000, 0.000000, 0.000000),
        (0.000000, 0.000000, 3.800000),
    ]
    write_xyz(xyz_path, symbols, coords, comment="Argon dimer test structure")
    assert xyz_path.is_file()

    read_syms, read_coords = read_xyz(xyz_path)
    assert read_syms == symbols
    assert len(read_coords) == len(coords)
    for (x1, y1, z1), (x2, y2, z2) in zip(coords, read_coords):
        assert abs(x1 - x2) < 1e-6
        assert abs(y1 - y2) < 1e-6
        assert abs(z1 - z2) < 1e-6


def test_read_extinp_parsing(tmp_path: Path) -> None:
    """Verify ORCA <base>_EXT.extinp.tmp parsing adhering to Section 10.2."""
    xyz_file = tmp_path / "water_EXT.xyz"
    xyz_file.write_text("3\ntest\nO 0.0 0.0 0.0\nH 0.0 0.7 0.5\nH 0.0 -0.7 0.5\n", encoding="utf-8")

    extinp_file = tmp_path / "water_EXT.extinp.tmp"
    extinp_content = (
        f"{xyz_file.name}    # xyz filename: string, ending in '.xyz'\n"
        "0                   # charge: integer\n"
        "1                   # multiplicity: positive integer\n"
        "4                   # NCores: positive integer\n"
        "1                   # do gradient: 0 or 1\n"
    )
    extinp_file.write_text(extinp_content, encoding="utf-8")

    data = read_extinp(extinp_file)
    assert data.xyz_file.name == "water_EXT.xyz"
    assert data.charge == 0
    assert data.multiplicity == 1
    assert data.ncores == 4
    assert data.dograd is True
    assert data.pointcharges_file is None


def test_validate_maceoff_constraints(tmp_path: Path) -> None:
    """Verify physical and model domain constraints mandated in Section 10.7."""
    xyz_file = tmp_path / "mol.xyz"
    xyz_file.write_text("1\ntest\nAr 0.0 0.0 0.0\n", encoding="utf-8")

    # 1. Valid neutral closed shell
    valid_data = ExtInpData(
        xyz_file=xyz_file,
        charge=0,
        multiplicity=1,
        ncores=1,
        dograd=True,
        pointcharges_file=None,
    )
    validate_maceoff_constraints(valid_data)  # Must not raise

    # 2. Charged system -> must raise ValueError
    charged_data = ExtInpData(
        xyz_file=xyz_file,
        charge=1,
        multiplicity=1,
        ncores=1,
        dograd=True,
        pointcharges_file=None,
    )
    with pytest.raises(ValueError, match="neutral"):
        validate_maceoff_constraints(charged_data)

    # 3. Open shell system -> must raise ValueError
    openshell_data = ExtInpData(
        xyz_file=xyz_file,
        charge=0,
        multiplicity=2,
        ncores=1,
        dograd=True,
        pointcharges_file=None,
    )
    with pytest.raises(ValueError, match="closed-shell"):
        validate_maceoff_constraints(openshell_data)

    # 4. Point charges file -> must raise ValueError
    pc_file = tmp_path / "charges.pc"
    pc_file.write_text("1\n0.0 0.0 0.0 0.5\n", encoding="utf-8")
    pc_data = ExtInpData(
        xyz_file=xyz_file,
        charge=0,
        multiplicity=1,
        ncores=1,
        dograd=True,
        pointcharges_file=pc_file,
    )
    with pytest.raises(ValueError, match="Point charges not supported"):
        validate_maceoff_constraints(pc_data)


def test_ase_energy_and_gradient_conversion_math() -> None:
    """Verify exact energy conversion and force-to-gradient sign flip (§10.3)."""
    atoms = Atoms("Ar2", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 3.8]])
    calc = LennardJonesRealTestCalculator(epsilon=0.0103, sigma=3.4)

    e_Eh, g_Eh_bohr = compute_maceoff_energy_gradient(atoms, calc, dograd=True)

    # Check potential energy
    e_eV = atoms.get_potential_energy()
    expected_e_Eh = e_eV * EH_PER_EV
    assert abs(e_Eh - expected_e_Eh) < 1e-12

    # Check forces vs gradients: gradient = -force in Eh/bohr
    forces_eV_A = atoms.get_forces()
    assert len(g_Eh_bohr) == 6  # 2 atoms * 3 components

    for atom_idx in range(2):
        for c in range(3):
            f_comp = forces_eV_A[atom_idx][c]
            expected_g = -f_comp * EH_PER_EV / BOHR_PER_A
            actual_g = g_Eh_bohr[atom_idx * 3 + c]
            assert abs(actual_g - expected_g) < 1e-12


def test_committee_uncertainty_math() -> None:
    """Verify Section 10.8 committee uncertainty formulas and calculations."""
    atoms = Atoms("Ar2", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 3.8]])
    calc1 = LennardJonesRealTestCalculator(epsilon=0.0100, sigma=3.4)
    calc2 = LennardJonesRealTestCalculator(epsilon=0.0106, sigma=3.4)

    e_bar, g_bar, sigma_e, u_f = compute_committee_uncertainty(atoms, [calc1, calc2], dograd=True)

    e1, g1 = compute_maceoff_energy_gradient(atoms, calc1, dograd=True)
    e2, g2 = compute_maceoff_energy_gradient(atoms, calc2, dograd=True)

    expected_e_bar = (e1 + e2) / 2.0
    assert abs(e_bar - expected_e_bar) < 1e-12

    expected_sigma_e = math.sqrt(((e1 - expected_e_bar) ** 2 + (e2 - expected_e_bar) ** 2) / 2.0) / math.sqrt(2.0)
    assert abs(sigma_e - expected_sigma_e) < 1e-12

    for k in range(6):
        assert abs(g_bar[k] - (g1[k] + g2[k]) / 2.0) < 1e-12

    expected_u_f = max(abs(g1[k] - g_bar[k]) for k in range(6))
    assert abs(u_f - expected_u_f) < 1e-12


def test_write_engrad_format(tmp_path: Path) -> None:
    """Verify strictly compliant ORCA .engrad file format generation (§10.2)."""
    engrad_file = tmp_path / "argon_EXT.engrad"
    energy_val = -0.000378512345
    grads = [0.0, 0.0, 0.000123456789, 0.0, 0.0, -0.000123456789]

    write_engrad(engrad_file, num_atoms=2, energy_Eh=energy_val, gradient_Eh_bohr=grads, dograd=True)
    assert engrad_file.is_file()

    content = engrad_file.read_text(encoding="utf-8")
    lines = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]

    assert int(lines[0]) == 2
    assert abs(float(lines[1]) - energy_val) < 1e-10
    assert len(lines[2:]) == 6
    for val_read, val_exp in zip(lines[2:], grads):
        assert abs(float(val_read) - val_exp) < 1e-6


def test_full_pipeline_with_real_ase_calculator(tmp_path: Path) -> None:
    """Execute run_oet_maceoff full pipeline with physical ASE calculator."""
    xyz_file = tmp_path / "dimer_EXT.xyz"
    write_xyz(
        xyz_file,
        symbols=["Ar", "Ar"],
        coords=[[0.0, 0.0, 0.0], [0.0, 0.0, 3.8]],
        comment="LJ Dimer",
    )

    extinp_file = tmp_path / "dimer_EXT.extinp.tmp"
    extinp_content = (
        f"{xyz_file.name}\n"
        "0\n"
        "1\n"
        "2\n"
        "1\n"
    )
    extinp_file.write_text(extinp_content, encoding="utf-8")

    calc = LennardJonesRealTestCalculator(epsilon=0.0103, sigma=3.4)
    result = run_oet_maceoff(extinp_file, calculator=calc)

    assert result.num_atoms == 2
    assert result.engrad_file.is_file()
    assert result.engrad_file.name == "dimer_EXT.engrad"
    assert len(result.gradient_Eh_bohr) == 6


def test_reexport_parity() -> None:
    """Verify complete parity between cochem_base.interfaces.oet_maceoff and interfaces.oet_maceoff."""
    assert hasattr(interfaces_maceoff, "__all__")
    for sym in interfaces_maceoff.__all__:
        assert hasattr(interfaces_maceoff, sym), f"Missing symbol {sym} in interfaces.oet_maceoff"
        assert hasattr(oet_maceoff, sym), f"Missing symbol {sym} in cochem_base.interfaces.oet_maceoff"
        assert getattr(interfaces_maceoff, sym) is getattr(oet_maceoff, sym)


def test_main_cli_help() -> None:
    """Verify CLI interface parses arguments and returns help correctly."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
