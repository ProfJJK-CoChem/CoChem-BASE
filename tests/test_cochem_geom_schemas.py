"""# zero-stub anti-spoofing engine
Unit tests for cochem_geom.engine.schemas adhering to Method Matrix v4.
"""

import math
import pytest
from pydantic import ValidationError

from cochem_geom.engine.schemas import (
    AtomCoordinate,
    CartesianConstraint,
    CFOURInputDeckSchema,
    ChainedStateSchema,
    ConvergenceThresholds,
    CoordinateType,
    DispersionMissingError,
    DispersionType,
    DynamicMassDict,
    EngineType,
    FrozenMonomerSettings,
    HessianPreconditioner,
    InertialParameters,
    IntegrationGrid,
    InternalConstraint,
    InvalidHessianStrategyError,
    MolecularGeometry,
    OptimizationSettings,
    ORCAInputDeckSchema,
    PickettCentrifugalDistortion,
    PickettDeckSchema,
    PickettDipoleComponents,
    PickettParameter,
    PickettQuadrupoleTensor,
    PickettQuantumNumbers,
    PickettReduction,
    PickettRepresentation,
    PickettRotationalConstants,
    PickettTransition,
    ProvenanceRecord,
    ProvenanceTag,
    QuantumCalculationResult,
    SchemaValidationError,
    SpectroscopicConstants,
    SpycFitPayloadModel,
    STANDARD_ATOMIC_MASSES,
    SystemConfigSchema,
    TaskType,
    UnphysicalQuantumNumberError,
)


def test_dynamic_mendeleev_masses():
    """Verify live Mendeleev atomic and isotopic mass lookups without mocks or stubs."""
    assert abs(STANDARD_ATOMIC_MASSES.get("H") - 1.008) < 0.01
    assert abs(STANDARD_ATOMIC_MASSES.get("C") - 12.011) < 0.01
    assert abs(STANDARD_ATOMIC_MASSES.get("13C") - 13.00335) < 0.001
    assert abs(STANDARD_ATOMIC_MASSES.get("18O") - 17.99916) < 0.001
    assert abs(STANDARD_ATOMIC_MASSES.get("D") - 2.01410) < 0.001
    assert abs(STANDARD_ATOMIC_MASSES.get("T") - 3.01605) < 0.001

    assert "13C" in STANDARD_ATOMIC_MASSES
    assert "18O" in STANDARD_ATOMIC_MASSES
    assert "D" in STANDARD_ATOMIC_MASSES
    assert "T" in STANDARD_ATOMIC_MASSES
    assert "Unobtainium" not in STANDARD_ATOMIC_MASSES


def test_atom_coordinate_and_geometry():
    """Verify AtomCoordinate and MolecularGeometry data integrity and XYZ serialization."""
    c12 = AtomCoordinate(element="C", x=0.0, y=0.0, z=0.0)
    assert c12.mass is not None and abs(c12.mass - 12.011) < 0.01

    c13 = AtomCoordinate(element="13C", x=1.0, y=0.0, z=0.0)
    assert abs(c13.mass - 13.00335) < 0.001

    d_atom = AtomCoordinate(element="D", x=2.0, y=0.0, z=0.0)
    assert abs(d_atom.mass - 2.01410) < 0.001

    xyz = """3
Water molecule
O   0.00000000   0.00000000   0.11730000
H   0.00000000   0.75720000  -0.46920000
H   0.00000000  -0.75720000  -0.46920000
"""
    geom = MolecularGeometry.from_xyz_string(xyz, species_id="H2O")
    assert geom.num_atoms == 3
    assert abs(geom.total_mass - 18.015) < 0.05
    assert len(geom.coordinates_array()) == 3

    roundtrip_xyz = geom.to_xyz_string()
    geom2 = MolecularGeometry.from_xyz_string(roundtrip_xyz, species_id="H2O")
    assert geom2.num_atoms == 3


def test_pickett_quantum_numbers_validation():
    """Verify asymmetric rotor parity rule and selection rule bounds."""
    # Valid state
    qn = PickettQuantumNumbers(j_upper=1, ka_upper=0, kc_upper=1, j_lower=0, ka_lower=0, kc_lower=0)
    assert qn.j == 1

    # Ka > J violation
    with pytest.raises((ValidationError, UnphysicalQuantumNumberError)):
        PickettQuantumNumbers(j_upper=1, ka_upper=2, kc_upper=0)

    # Parity rule Ka+Kc in {J, J+1} violation
    with pytest.raises((ValidationError, UnphysicalQuantumNumberError)):
        PickettQuantumNumbers(j_upper=2, ka_upper=0, kc_upper=0)


def test_pickett_rotational_constants():
    """Verify physical rotational constant hierarchy A >= B >= C > 0."""
    rot = PickettRotationalConstants(A_mhz=10000.0, B_mhz=5000.0, C_mhz=2500.0)
    assert rot.ray_asymmetry_parameter == (2 * 5000 - 10000 - 2500) / (10000 - 2500)

    # Inverted hierarchy violation
    with pytest.raises((ValidationError, SchemaValidationError)):
        PickettRotationalConstants(A_mhz=2000.0, B_mhz=5000.0, C_mhz=1000.0)


def test_pickett_quadrupole_tensor():
    """Verify Laplace traceless condition for nuclear quadrupole tensor."""
    quad = PickettQuadrupoleTensor(nucleus="14N", chi_aa_mhz=-4.0, chi_bb_mhz=2.0, chi_cc_mhz=2.0)
    assert abs(quad.chi_aa_mhz + quad.chi_bb_mhz + quad.chi_cc_mhz) < 1e-6

    # Non-traceless violation
    with pytest.raises((ValidationError, SchemaValidationError)):
        PickettQuadrupoleTensor(nucleus="14N", chi_aa_mhz=-4.0, chi_bb_mhz=2.0, chi_cc_mhz=3.0)


def test_inertial_parameters_and_dipole():
    """Verify moment of inertia hierarchy and automatic planar moments derivation."""
    inert = InertialParameters(I_a_amu_ang2=10.0, I_b_amu_ang2=20.0, I_c_amu_ang2=30.0, inertial_defect_amu_ang2=0.0)
    assert inert.P_aa_amu_a2 == 0.5 * (-10.0 + 20.0 + 30.0)  # 20.0
    assert inert.P_bb_amu_a2 == 0.5 * (10.0 - 20.0 + 30.0)   # 10.0
    assert inert.P_cc_amu_a2 == 0.5 * (10.0 + 20.0 - 30.0)   # 0.0

    dip = PickettDipoleComponents(mu_a_debye=3.0, mu_b_debye=4.0, mu_c_debye=0.0)
    assert abs(dip.total_debye - 5.0) < 1e-6


def test_method_matrix_calc_hess_prohibition():
    """Verify Method Matrix v4 §8B.3 Calc_Hess true prohibition."""
    with pytest.raises((ValidationError, InvalidHessianStrategyError)):
        OptimizationSettings(inhess="CALC_HESS TRUE")

    with pytest.raises((ValidationError, InvalidHessianStrategyError)):
        OptimizationSettings(inhess="EXACT")

    with pytest.raises((ValidationError, InvalidHessianStrategyError)):
        ORCAInputDeckSchema(inhess="CALC_HESS TRUE")

    with pytest.raises((ValidationError, InvalidHessianStrategyError)):
        ORCAInputDeckSchema(extra_keywords=["Calc_Hess true"])


def test_method_matrix_convergence_and_grids():
    """Verify Method Matrix v4 §4.4 tightened convergence thresholds and grid rules."""
    conv = ConvergenceThresholds()
    assert conv.tol_e == 1e-7
    assert conv.tol_maxg == 1e-5
    assert conv.tol_rmsg == 3e-6
    assert conv.tol_maxd == 1e-4
    assert conv.tol_rmsd == 5e-5

    geom_block = conv.format_orca_geom_block()
    assert "TolMaxG 1.0E-05" in geom_block
    assert "TolE    1.0E-07" in geom_block

    # Deprecated grids forbidden
    with pytest.raises((ValidationError, SchemaValidationError)):
        ORCAInputDeckSchema(extra_keywords=["GRID3"])

    with pytest.raises((ValidationError, SchemaValidationError)):
        ORCAInputDeckSchema(extra_keywords=["GRID5"])


def test_method_matrix_dispersion_mandate():
    """Verify Method Matrix v4 §4.2 dispersion mandate for weak complexes."""
    # Standard DFT without dispersion on weak complex must fail
    with pytest.raises((ValidationError, DispersionMissingError)):
        ORCAInputDeckSchema(method="B3LYP", is_weak_complex=True, dispersion=DispersionType.NONE)

    # Standard DFT with explicit dispersion must pass
    deck_b3lyp = ORCAInputDeckSchema(method="B3LYP", is_weak_complex=True, dispersion=DispersionType.D3BJ)
    assert deck_b3lyp.dispersion == DispersionType.D3BJ

    # Functional with built-in dispersion must pass
    deck_wB97 = ORCAInputDeckSchema(method="wB97X-V", is_weak_complex=True, dispersion=DispersionType.NONE)
    assert deck_wB97.method == "wB97X-V"


def test_frozen_monomer_settings():
    """Verify Method Matrix v4 §9A.1 disjoint fragment verification."""
    fm_valid = FrozenMonomerSettings(enabled=True, fragment_indices=[[0, 1], [2, 3]])
    assert fm_valid.enabled is True

    # Overlapping indices must fail
    with pytest.raises((ValidationError, SchemaValidationError)):
        FrozenMonomerSettings(enabled=True, fragment_indices=[[0, 1], [1, 2]])


def test_qc_deck_formatting():
    """Verify ORCA and CFOUR deck text generation."""
    geom = MolecularGeometry(
        name="H2O",
        atoms=[
            AtomCoordinate(element="O", x=0.0, y=0.0, z=0.1173),
            AtomCoordinate(element="H", x=0.0, y=0.7572, z=-0.4692),
            AtomCoordinate(element="H", x=0.0, y=-0.7572, z=-0.4692),
        ]
    )
    orca_deck = ORCAInputDeckSchema(
        method="wB97X-V",
        basis="def2-TZVP",
        geometry=geom,
        nprocs=8,
        maxcore_mb=3000,
        convergence=ConvergenceThresholds(),
        cartesian_constraints=[CartesianConstraint(atom_index=0)],
        internal_constraints=[InternalConstraint(constraint_type="BOND", atoms=[0, 1])]
    )
    deck_str = orca_deck.format_deck_string()
    assert "! wB97X-V def2-TZVP Opt DEFGRID2" in deck_str
    assert "%pal nprocs 8 end" in deck_str
    assert "{ C 0 C }" in deck_str
    assert "{ B 0 1 C }" in deck_str

    cfour_deck = CFOURInputDeckSchema(
        method="CCSD(T)",
        basis="ANO1",
        geometry=geom,
        fd_irrep=True,
        sextic_distortion=True
    )
    zmat_str = cfour_deck.format_zmat_string()
    assert "*CFOUR(CALC=CCSD(T)" in zmat_str
    assert "FD_IRREP=TRUE" in zmat_str
    assert "ANHARMONIC=SEXTIC" in zmat_str


def test_provenance_and_results():
    """Verify Method Matrix v4 §15 and §20 scientific provenance tracking."""
    prov = ProvenanceRecord(tag_type=ProvenanceTag.METHOD, software_version="CoChem-GEOM v4.0")
    tag = prov.to_provenance_tag()
    assert "[M]" in tag
    assert "CoChem-GEOM v4.0" in tag
    assert "CODATA 2026" in tag

    res = QuantumCalculationResult(
        engine=EngineType.ORCA,
        task_type=TaskType.OPT,
        method="wB97X-V",
        basis="def2-TZVP",
        energy_hartree=-76.4321,
        converged=True,
        wall_time_seconds=124.5
    )
    assert res.final_energy_hartree == -76.4321
    assert res.calculation_type == TaskType.OPT
    assert res.wall_time_seconds == 124.5
