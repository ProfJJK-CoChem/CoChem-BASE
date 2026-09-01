"""Zero-Mock Production Test Suite for Inertial Defect Validator & Formatter.

Strictly adheres to:
- CoChem Method Matrix v4 (Sections 1.2, 2.1, 3.0, 4.0 / Step 4 Five Free Observables)
- Zero-Mock Anti-Spoofing Protocol: Real physical Cartesian geometries, real Mendeleev masses,
  real filesystem I/O with tmp_path, real PyArrow Tables and DataFrames.
- Mendeleev Mandate: Dynamic elemental/isotopic mass retrieval via mendeleev library.
- Complete, functional Python 3.10+ code with zero mocks, zero stubs, zero pass blocks.
"""

from __future__ import annotations

import json
import math
import os
import pathlib
import subprocess
import sys
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]
import pytest
from mendeleev import element  # type: ignore[import-untyped]

from formatters.cochem_inertial_defect_validator import (
    InertialDefectValidationReport,
    InertialDefectValidator,
    InertialDefectValidatorConfig,
    MolecularInertialProperties,
    PlanarityClassification,
    ProductClass,
    RotorType,
    ValidationStatus,
    calculate_inertial_properties,
    classify_planarity,
    classify_rotor_type,
    compute_center_of_mass,
    compute_inertia_tensor,
    compute_inertial_defect,
    compute_planar_moments,
    compute_principal_moments_and_axes,
    compute_rays_asymmetry_kappa,
    compute_rotational_constants,
    compute_wangs_asymmetry_parameters,
    get_atomic_mass,
    main,
    validate_inertial_defect,
)


# =============================================================================
# 1. Mendeleev Mandate & Dynamic Mass Tests
# =============================================================================

def test_mendeleev_mass_resolution() -> None:
    """Verifies dynamic atomic and isotopic mass resolution via mendeleev."""
    c_mass = float(element("C").atomic_weight)
    h_mass = float(element("H").atomic_weight)
    o_mass = float(element("O").atomic_weight)
    n_mass = float(element("N").atomic_weight)

    assert math.isclose(get_atomic_mass("C"), c_mass, rel_tol=1e-6)
    assert math.isclose(get_atomic_mass("H"), h_mass, rel_tol=1e-6)
    assert math.isclose(get_atomic_mass("O"), o_mass, rel_tol=1e-6)
    assert math.isclose(get_atomic_mass("N"), n_mass, rel_tol=1e-6)

    # By atomic number
    assert math.isclose(get_atomic_mass(6), c_mass, rel_tol=1e-6)
    assert math.isclose(get_atomic_mass(1), h_mass, rel_tol=1e-6)
    assert math.isclose(get_atomic_mass(8), o_mass, rel_tol=1e-6)

    # Isotopes (13C, D / 2H, 18O, 15N)
    c13_elem = element("C")
    c13_expected = None
    for iso in c13_elem.isotopes:
        if iso.mass_number == 13:
            c13_expected = float(iso.mass)
            break
    assert c13_expected is not None
    assert math.isclose(get_atomic_mass("13C"), c13_expected, rel_tol=1e-6)

    d_mass = get_atomic_mass("D")
    assert d_mass > 2.0 and d_mass < 2.02  # ~2.0141 u


# =============================================================================
# 2. Physics & Mathematics Invariants: Planar Water & Formaldehyde
# =============================================================================

def test_planar_water_inertial_defect_zero() -> None:
    """Verifies Delta = 0.000 u*A^2 for strictly planar rigid equilibrium water (H2O)."""
    # H2O in xy-plane (z = 0 for all atoms)
    # Bond length r(O-H) = 0.9575 A, angle H-O-H = 104.5 degrees
    half_angle = math.radians(104.5 / 2.0)
    r_oh = 0.9575

    symbols = ["O", "H", "H"]
    coords = np.array(
        [
            [0.0, 0.0, 0.0],
            [r_oh * math.sin(half_angle), r_oh * math.cos(half_angle), 0.0],
            [-r_oh * math.sin(half_angle), r_oh * math.cos(half_angle), 0.0],
        ],
        dtype=np.float64,
    )

    props = calculate_inertial_properties(symbols, coords)

    # In rigid planar geometry: I_c = I_a + I_b -> Delta = 0.000
    assert math.isclose(props.inertial_defect_amu_angstrom2, 0.0, abs_tol=1e-6)
    assert props.planarity_class == PlanarityClassification.STRICTLY_PLANAR_EQUILIBRIUM

    # Planar moments: P_cc = -0.5 * Delta = 0.0
    assert math.isclose(props.planar_moment_pcc_amu_angstrom2, 0.0, abs_tol=1e-6)
    assert props.planar_moment_paa_amu_angstrom2 > 0.0
    assert props.planar_moment_pbb_amu_angstrom2 > 0.0

    # Moments ordering: I_a <= I_b <= I_c
    assert props.ia_amu_angstrom2 <= props.ib_amu_angstrom2 <= props.ic_amu_angstrom2

    # Rotational constants ordering: A >= B >= C
    assert props.a_mhz >= props.b_mhz >= props.c_mhz
    assert props.a_ghz >= props.b_ghz >= props.c_ghz

    # Asymmetry parameter: Water is an asymmetric top with -1 < kappa < +1
    assert -1.0 <= props.rays_kappa <= 1.0


def test_planar_formaldehyde_equilibrium() -> None:
    """Verifies planar formaldehyde (H2CO) properties and Ray's kappa."""
    # Planar H2CO in xy-plane
    symbols = ["C", "O", "H", "H"]
    coords = np.array(
        [
            [0.0000, 0.0000, 0.0000],  # C
            [0.0000, 1.2050, 0.0000],  # O
            [0.9400, -0.5850, 0.0000],  # H
            [-0.9400, -0.5850, 0.0000],  # H
        ],
        dtype=np.float64,
    )

    props = calculate_inertial_properties(symbols, coords)

    assert math.isclose(props.inertial_defect_amu_angstrom2, 0.0, abs_tol=1e-5)
    assert props.planarity_class == PlanarityClassification.STRICTLY_PLANAR_EQUILIBRIUM
    assert props.rotor_type in [
        RotorType.NEAR_PROLATE_ASYMMETRIC_TOP,
        RotorType.HIGHLY_ASYMMETRIC_TOP,
        RotorType.ASYMMETRIC_TOP,
    ]


# =============================================================================
# 3. Non-Planar 3D Systems & Methyl Rotors
# =============================================================================

def test_methanol_methyl_rotor_negative_defect() -> None:
    """Verifies negative inertial defect (Delta ~ -3.1 u*A^2) for methanol (CH3OH)."""
    # Authentic Cartesian coordinates for methanol with out-of-plane methyl hydrogens
    symbols = ["C", "O", "H", "H", "H", "H"]
    coords = np.array(
        [
            [-0.0466, 0.6646, 0.0000],  # C
            [-0.0466, -0.7548, 0.0000],  # O
            [0.9859, 1.0772, 0.0000],  # H (in-plane)
            [-0.5630, 1.0330, 0.8906],  # H (out-of-plane +z)
            [-0.5630, 1.0330, -0.8906],  # H (out-of-plane -z)
            [0.8430, -1.0970, 0.0000],  # H (hydroxyl)
        ],
        dtype=np.float64,
    )

    props = calculate_inertial_properties(symbols, coords)

    # For CH3OH, out-of-plane H atoms contribute Delta = -2 * m_H * z_H^2 ~ -3.18 u*A^2
    assert props.inertial_defect_amu_angstrom2 < -2.5
    assert props.inertial_defect_amu_angstrom2 > -4.5
    assert props.planarity_class == PlanarityClassification.METHYL_ROTOR
    assert props.planar_moment_pcc_amu_angstrom2 > 1.0  # P_cc = -0.5 * Delta > 0


def test_spherical_top_methane() -> None:
    """Verifies methane (CH4) spherical top behavior with Ia = Ib = Ic."""
    r_ch = 1.087
    a = r_ch / math.sqrt(3.0)
    symbols = ["C", "H", "H", "H", "H"]
    coords = np.array(
        [
            [0.0, 0.0, 0.0],
            [a, a, a],
            [a, -a, -a],
            [-a, a, -a],
            [-a, -a, a],
        ],
        dtype=np.float64,
    )

    props = calculate_inertial_properties(symbols, coords)

    assert math.isclose(props.ia_amu_angstrom2, props.ib_amu_angstrom2, rel_tol=1e-5)
    assert math.isclose(props.ib_amu_angstrom2, props.ic_amu_angstrom2, rel_tol=1e-5)
    assert math.isclose(props.a_mhz, props.b_mhz, rel_tol=1e-5)
    assert math.isclose(props.b_mhz, props.c_mhz, rel_tol=1e-5)
    assert props.rotor_type == RotorType.SPHERICAL_TOP
    assert props.planarity_class == PlanarityClassification.NON_PLANAR_3D


def test_linear_rotor_ocs() -> None:
    """Verifies linear carbonyl sulfide (OCS) with Ia ~ 0 and Ib = Ic."""
    # Linear along z-axis
    symbols = ["O", "C", "S"]
    coords = np.array(
        [
            [0.0, 0.0, -1.157],  # O
            [0.0, 0.0, 0.0],  # C
            [0.0, 0.0, 1.560],  # S
        ],
        dtype=np.float64,
    )

    props = calculate_inertial_properties(symbols, coords)

    assert props.ia_amu_angstrom2 < 1e-4
    assert math.isclose(props.ib_amu_angstrom2, props.ic_amu_angstrom2, rel_tol=1e-5)
    assert props.rotor_type == RotorType.LINEAR
    assert math.isclose(props.b_mhz, props.c_mhz, rel_tol=1e-4)


# =============================================================================
# 4. Method Matrix v4 Validation Engine & Tolerance Auditing
# =============================================================================

def test_validation_report_product_a_and_b(tmp_path: pathlib.Path) -> None:
    """Tests validation reporting against Product A and Product B target tolerances."""
    validator = InertialDefectValidator()

    # Formamidinium formate complex (Method Matrix v4 §1.1 planar complex)
    # Simplified planar formamidinium-like test coordinates
    symbols = ["C", "N", "N", "H", "H", "H"]
    coords = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.3, 0.0, 0.0],
            [-1.3, 0.0, 0.0],
            [1.8, 0.8, 0.0],
            [1.8, -0.8, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=np.float64,
    )

    # Compute baseline properties
    props = calculate_inertial_properties(symbols, coords)

    # 1. Product A validation (matches calculated within 0.5%)
    ref_a_ok = (props.a_mhz * 1.002, props.b_mhz * 0.998, props.c_mhz * 1.001)
    report_a = validator.validate_geometry(
        symbols=symbols,
        coords=coords,
        reference_rotational_constants_mhz=ref_a_ok,
        product_class=ProductClass.PRODUCT_A_ABSOLUTE_DENOVO,
        molecule_name="Planar_Formamidinium",
    )
    assert report_a.is_valid is True
    assert report_a.status in [ValidationStatus.VALID, ValidationStatus.WARNING]
    assert len(report_a.errors) == 0

    # 2. Product B tight tolerance check (0.06% target)
    ref_b_tight = (props.a_mhz * 1.0002, props.b_mhz * 1.0001, props.c_mhz * 0.9999)
    report_b = validator.validate_geometry(
        symbols=symbols,
        coords=coords,
        reference_rotational_constants_mhz=ref_b_tight,
        product_class=ProductClass.PRODUCT_B_SEMI_EXPERIMENTAL,
        molecule_name="Formamidinium_Product_B",
    )
    assert report_b.is_valid is True
    assert report_b.status == ValidationStatus.VALID

    # 3. Product C differences / isotopologue tolerance check (0.10% target)
    ref_c_diff = (props.a_mhz * 1.0008, props.b_mhz * 0.9994, props.c_mhz * 1.0005)
    report_c = validator.validate_geometry(
        symbols=symbols,
        coords=coords,
        reference_rotational_constants_mhz=ref_c_diff,
        product_class=ProductClass.PRODUCT_C_DIFFERENCES,
        molecule_name="Formamidinium_Product_C",
    )
    assert report_c.is_valid is True
    assert report_c.status == ValidationStatus.VALID


def test_vibrational_ground_state_v0_positive_defect() -> None:
    """Verifies that is_ground_state_v0 allows physical positive Delta_0 in [0, 0.50] u*A^2."""
    cfg = InertialDefectValidatorConfig(is_ground_state_v0=True)
    validator = InertialDefectValidator(config=cfg)

    # Water coordinates
    symbols = ["O", "H", "H"]
    coords = np.array(
        [[0.0, 0.0, 0.0], [0.757, 0.586, 0.0], [-0.757, 0.586, 0.0]], dtype=np.float64
    )

    report = validator.validate_geometry(symbols, coords, molecule_name="Water_v0")
    assert report.is_valid is True


# =============================================================================
# 5. File I/O: XYZ Parsing, Multi-format Export & Formatter Tests
# =============================================================================

def test_xyz_file_parsing_and_report_generation(tmp_path: pathlib.Path) -> None:
    """Tests end-to-end reading of .xyz files and multi-format exports."""
    xyz_content = """3
Water molecule planar equilibrium
O  0.000000  0.000000  0.000000
H  0.757000  0.586000  0.000000
H -0.757000  0.586000  0.000000
"""
    xyz_file = tmp_path / "water.xyz"
    xyz_file.write_text(xyz_content, encoding="utf-8")

    validator = InertialDefectValidator()
    report = validator.validate_xyz_file(xyz_file)

    assert report.is_valid is True
    assert report.properties.number_of_atoms == 3
    assert math.isclose(report.properties.inertial_defect_amu_angstrom2, 0.0, abs_tol=1e-5)

    # GFM Markdown report
    md_text = validator.format_markdown_report(report)
    assert "# CoChem Inertial Defect & Planar Moment Audit" in md_text
    assert "Inertial Defect" in md_text
    assert "Planar Moments" in md_text
    assert "> [!NOTE]" in md_text

    # LaTeX table
    tex_text = validator.format_latex_table(report)
    assert r"\begin{table}" in tex_text
    assert r"Rotational constant" in tex_text
    assert r"\end{table}" in tex_text

    # Pickett comment block
    pickett_comments = validator.format_pickett_comments(report)
    assert "# Pickett Parameter File Generated with CoChem-BASE" in pickett_comments
    assert "Inertial Defect Delta" in pickett_comments

    # JSON report
    json_text = validator.format_json_report(report)
    parsed_json = json.loads(json_text)
    assert parsed_json["is_valid"] is True
    assert "properties" in parsed_json

    # ANSI Terminal card
    term_text = validator.format_terminal_summary(report)
    assert "CoChem Spectroscopic Inertial Defect Audit" in term_text


def test_dataframe_and_pyarrow_export() -> None:
    """Verifies conversion of multiple validation reports into DataFrames and PyArrow Tables."""
    validator = InertialDefectValidator()

    # Create two reports
    symbols1 = ["O", "H", "H"]
    coords1 = np.array([[0, 0, 0], [0.75, 0.58, 0], [-0.75, 0.58, 0]], dtype=np.float64)
    rep1 = validator.validate_geometry(symbols1, coords1, molecule_name="H2O")

    symbols2 = ["C", "O"]
    coords2 = np.array([[0, 0, 0], [0, 0, 1.128]], dtype=np.float64)
    rep2 = validator.validate_geometry(symbols2, coords2, molecule_name="CO")

    reports = [rep1, rep2]

    df = validator.to_dataframe(reports)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "inertial_defect_u_ang2" in df.columns
    assert "rays_kappa" in df.columns

    table = validator.to_pyarrow_table(reports)
    assert isinstance(table, pa.Table)
    assert table.num_rows == 2
    assert "A_mhz" in table.column_names


# =============================================================================
# 6. CLI Subprocess & Main Entrypoint Tests
# =============================================================================

def test_cli_execution_with_xyz(tmp_path: pathlib.Path) -> None:
    """Verifies CLI execution with output export flags."""
    xyz_file = tmp_path / "sample.xyz"
    xyz_file.write_text(
        "3\nSample\nO 0.0 0.0 0.0\nH 0.75 0.58 0.0\nH -0.75 0.58 0.0\n",
        encoding="utf-8",
    )

    out_md = tmp_path / "report.md"
    out_json = tmp_path / "report.json"
    out_tex = tmp_path / "table.tex"

    cmd_args = [
        "--input", str(xyz_file),
        "--output-md", str(out_md),
        "--output-json", str(out_json),
        "--output-tex", str(out_tex),
        "--product", "A",
    ]

    ret_code = main(cmd_args)
    assert ret_code == 0

    assert out_md.is_file()
    assert out_json.is_file()
    assert out_tex.is_file()

    assert "# CoChem Inertial Defect" in out_md.read_text(encoding="utf-8")
    assert r"\begin{table}" in out_tex.read_text(encoding="utf-8")


def test_convenience_validate_inertial_defect() -> None:
    """Tests module-level validate_inertial_defect functional interface."""
    symbols = ["C", "O"]
    coords = np.array([[0, 0, 0], [0, 0, 1.13]], dtype=np.float64)
    report = validate_inertial_defect(symbols, coords, molecule_name="CarbonMonoxide")
    assert report.is_valid is True
    assert report.properties.rotor_type == RotorType.LINEAR
