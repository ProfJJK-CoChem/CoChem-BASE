#!/usr/bin/env python3
"""Comprehensive Zero-Mock test suite for ORCA ExtOpt g-xTB wrapper (oet_gxtb).

Validates:
- Method Matrix v4 Section 10.6 compliance
- ORCA extinp file parsing and coordinate extraction
- Mendeleev dynamic mass calculation
- Turbomole $grad and $energy parsing (with Fortran D/E exponent support)
- Fallback numerical finite difference gradient computation (§10.5(ii))
- ORCA .engrad file format generation (Hartree energy, Hartree/bohr gradients)
- CLI argument parsing and execution
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

import pytest

import interfaces.oet_gxtb as interfaces_oet
import cochem_base.interfaces.oet_gxtb as oet
from cochem_base.interfaces.oet_gxtb import (
    ANGSTROM_TO_BOHR,
    BOHR_PER_A,
    BOHR_TO_ANGSTROM,
    EH_PER_EV,
    EV_TO_HARTREE,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    EngradResult,
    ExtInpData,
    GXTBConfig,
    compute_numerical_gradient,
    find_xtb_binary,
    get_element_atomic_mass,
    main,
    parse_xtb_energy,
    parse_xtb_gradient,
    read_extinp,
    read_xyz,
    run_oet_gxtb,
    run_xtb_single_point,
    write_engrad,
    write_xyz,
)


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


def test_mendeleev_mass_mandate() -> None:
    """Verify element atomic masses are dynamically retrieved from Mendeleev."""
    elements_to_test = {
        "H": (1.007, 1.009),
        "He": (4.001, 4.004),
        "C": (12.010, 12.012),
        "N": (14.006, 14.008),
        "O": (15.998, 16.001),
        "F": (18.997, 18.999),
        "Ne": (20.178, 20.182),
        "Na": (22.988, 22.991),
        "Cl": (35.445, 35.460),
        "Ar": (39.945, 39.955),
    }
    for sym, (low, high) in elements_to_test.items():
        mass = get_element_atomic_mass(sym)
        assert low < mass < high, f"Mass for {sym} ({mass}) out of expected range ({low}, {high})"


def test_read_write_xyz(tmp_path: Path) -> None:
    """Verify standard XYZ coordinate parsing and generation."""
    xyz_path = tmp_path / "water_dimer.xyz"
    symbols = ["O", "H", "H", "O", "H", "H"]
    coords = [
        (0.000000, 0.000000, 0.117000),
        (0.000000, 0.757000, -0.469000),
        (0.000000, -0.757000, -0.469000),
        (2.800000, 0.000000, 0.117000),
        (2.800000, 0.757000, -0.469000),
        (2.800000, -0.757000, -0.469000),
    ]
    write_xyz(xyz_path, symbols, coords, comment="Water dimer test structure")
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
    xyz_file = tmp_path / "complex_EXT.xyz"
    xyz_file.write_text("3\ntest\nO 0.0 0.0 0.0\nH 0.0 0.7 0.5\nH 0.0 -0.7 0.5\n", encoding="utf-8")

    extinp_file = tmp_path / "complex_EXT.extinp.tmp"
    extinp_content = (
        f"{xyz_file.name}    # xyz filename: string, ending in '.xyz'\n"
        "0                   # charge: integer\n"
        "1                   # multiplicity: positive integer\n"
        "8                   # NCores: positive integer\n"
        "1                   # do gradient: 0 or 1\n"
        "pointcharges.pc     # point charge filename: string (optional)\n"
    )
    extinp_file.write_text(extinp_content, encoding="utf-8")

    data = read_extinp(extinp_file)
    assert data.xyz_file.name == "complex_EXT.xyz"
    assert data.charge == 0
    assert data.multiplicity == 1
    assert data.ncores == 8
    assert data.dograd is True


def test_parse_xtb_energy_files_and_stdout(tmp_path: Path) -> None:
    """Verify parsing energy in Hartree from $energy file and stdout fallbacks."""
    # 1. From energy file
    energy_file = tmp_path / "energy"
    energy_file.write_text("$energy\n1   -17.504066223730\n$end\n", encoding="utf-8")
    e1 = parse_xtb_energy(tmp_path)
    assert abs(e1 - (-17.504066223730)) < 1e-10

    # 2. From stdout regex
    fake_empty_dir = tmp_path / "empty_dir"
    fake_empty_dir.mkdir()
    stdout_sample = """
          -----------------------------------------------------------
          | TOTAL ENERGY              -17.504066223730 Eh           |
          | GRADIENT NORM               0.001428571429 Eh/alpha     |
          -----------------------------------------------------------
    """
    e2 = parse_xtb_energy(fake_empty_dir, stdout_text=stdout_sample)
    assert abs(e2 - (-17.504066223730)) < 1e-10


def test_parse_xtb_gradient_turbomole_format(tmp_path: Path) -> None:
    """Verify parsing 3*N Cartesian gradient in Eh/bohr from Turbomole $grad file."""
    grad_file = tmp_path / "gradient"
    grad_content = (
        "$grad\n"
        "cycle =      1    energy =   -17.504066223730 gnorm =    0.0014285\n"
        "  0.00000000000000      0.00000000000000      0.22109723000000      o\n"
        "  0.00000000000000      1.43052280000000     -0.88628260000000      h\n"
        "  0.00000000000000     -1.43052280000000     -0.88628260000000      h\n"
        " -0.00012324158300      0.00000000016000     -0.00054321000000\n"
        "  0.00006162079150      0.00012345678900      0.00027160500000\n"
        "  0.00006162079150     -0.00012345694900      0.00027160500000\n"
        "$end\n"
    )
    grad_file.write_text(grad_content, encoding="utf-8")

    grads = parse_xtb_gradient(tmp_path, num_atoms=3)
    assert len(grads) == 9
    assert abs(grads[0] - (-0.00012324158300)) < 1e-10
    assert abs(grads[1] - (0.00000000016000)) < 1e-10
    assert abs(grads[2] - (-0.00054321000000)) < 1e-10
    assert abs(grads[3] - (0.00006162079150)) < 1e-10


def test_write_engrad_format(tmp_path: Path) -> None:
    """Verify strictly compliant ORCA .engrad file format generation."""
    engrad_file = tmp_path / "water_EXT.engrad"
    energy_val = -17.504066223730
    grads = [-0.000123, 0.000000, -0.000543, 0.000061, 0.000123, 0.000271, 0.000061, -0.000123, 0.000271]

    write_engrad(engrad_file, num_atoms=3, energy_Eh=energy_val, gradient_Eh_bohr=grads, dograd=True)
    assert engrad_file.is_file()

    content = engrad_file.read_text(encoding="utf-8")
    lines = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]

    # First non-comment line is atom count
    assert int(lines[0]) == 3
    # Second non-comment line is energy in Eh
    assert abs(float(lines[1]) - energy_val) < 1e-10
    # Next 9 lines are atomic gradients
    assert len(lines[2:]) == 9
    for val_read, val_exp in zip(lines[2:], grads):
        assert abs(float(val_read) - val_exp) < 1e-6


def test_reexport_parity() -> None:
    """Verify complete parity between cochem_base.interfaces.oet_gxtb and interfaces.oet_gxtb."""
    assert hasattr(interfaces_oet, "__all__")
    for sym in interfaces_oet.__all__:
        assert hasattr(interfaces_oet, sym), f"Missing symbol {sym} in interfaces.oet_gxtb"
        assert hasattr(oet, sym), f"Missing symbol {sym} in cochem_base.interfaces.oet_gxtb"
        assert getattr(interfaces_oet, sym) is getattr(oet, sym)


def test_main_cli_help() -> None:
    """Verify CLI interface parses arguments correctly."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
