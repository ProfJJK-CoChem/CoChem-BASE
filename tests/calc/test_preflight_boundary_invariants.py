"""Test Suite for Preflight Validation & Boundary Invariant Gatekeepers (L3.2.1 - L3.2.3).

Verifies Method Matrix v4 §1.2, §3.0, §4.4 standards:
1. L3.2.1: Domain Integrity Preflight Guard & Mutual Exclusivity Validator
2. L3.2.2: Product B Spectroscopic Boundary & Ray's Asymmetry Parameter Gate
3. L3.2.3: Product M Crystal Symmetry & Reciprocal Density Gate
Zero-mock compliant: executes authentic physics calculations and dynamic mass resolution.
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from cochem_base.exceptions import (
    CoChemError,
    MethodMatrixViolationError,
    OntologicalCollisionError,
    ProductDomainBoundaryViolation,
    ReciprocalDensityViolation,
    InvalidRotationalAnchorError,
    InvalidPeriodicCellError,
    ProvenanceErrorCode,
    _EXCEPTION_REGISTRY,
)
from cochem_base.calc.preflight import validate_product_ontology_preflight
from cochem_base.formatters.cochem_inertial_defect_validator import (
    DEFAULT_PRODUCT_B_MAX_ERROR_REL,
    validate_product_b_invariants,
    get_atomic_mass,
)
from cochem_base.calc.materials_preflight import (
    validate_product_m_invariants,
    compute_cell_volume,
    compute_scalar_triple_product_volume,
    compute_reciprocal_lattice_vectors,
    detect_crystal_symmetry,
    compute_kmesh_density,
    compute_vacuum_separation,
    _resolve_element_symbol,
)


# =============================================================================
# 1. Exception Hierarchy & Polymorphic Deserialization Tests (L3.2.1)
# =============================================================================

def test_exception_inheritance_hierarchy():
    """Verify that all boundary invariant exceptions inherit from MethodMatrixViolationError."""
    assert issubclass(OntologicalCollisionError, MethodMatrixViolationError)
    assert issubclass(ProductDomainBoundaryViolation, MethodMatrixViolationError)
    assert issubclass(ReciprocalDensityViolation, ProductDomainBoundaryViolation)
    assert issubclass(InvalidRotationalAnchorError, ProductDomainBoundaryViolation)
    assert issubclass(InvalidPeriodicCellError, ProductDomainBoundaryViolation)


def test_exception_registry_and_polymorphic_roundtrip():
    """Verify registration in _EXCEPTION_REGISTRY and full JSON/dict roundtrip."""
    for exc_cls in [
        OntologicalCollisionError,
        ProductDomainBoundaryViolation,
        ReciprocalDensityViolation,
        InvalidRotationalAnchorError,
        InvalidPeriodicCellError,
    ]:
        assert exc_cls.__name__ in _EXCEPTION_REGISTRY
        instance = exc_cls("Detailed failure message [M]", details={"axis": 1, "val": 0.02})
        payload_dict = instance.to_dict()
        reconstructed = CoChemError.from_dict(payload_dict)
        assert isinstance(reconstructed, exc_cls)
        assert reconstructed.message == instance.message
        assert reconstructed.details == instance.details

        # Test JSON roundtrip
        json_str = instance.to_json()
        from_json_obj = CoChemError.from_json(json_str)
        assert isinstance(from_json_obj, exc_cls)


def test_exception_pedagogical_guidance():
    """Verify that to_pedagogical_guidance returns actionable didactic advice."""
    col_err = OntologicalCollisionError("Mixed parameters")
    assert "Ontological collision" in col_err.to_pedagogical_guidance()

    dens_err = ReciprocalDensityViolation("Under-resolved kmesh")
    assert "Periodic k-point mesh density" in dens_err.to_pedagogical_guidance()

    rot_err = InvalidRotationalAnchorError("Ordering violated")
    assert "Rotational constant ordering" in rot_err.to_pedagogical_guidance()

    cell_err = InvalidPeriodicCellError("Degenerate cell")
    assert "unit cell volume" in cell_err.to_pedagogical_guidance()


# =============================================================================
# 2. Product Ontology Mutual Exclusivity Guard Tests (L3.2.1)
# =============================================================================

def test_product_b_clean_payload():
    """Verify that a clean Product B payload passes preflight validation."""
    payload = {
        "product": "PRODUCT_B",
        "rotational_constants": [9652.14, 4826.07, 3217.38],
    }
    telemetry = validate_product_ontology_preflight(payload)
    assert telemetry["status"] == "VALID"
    assert telemetry["product_category"] == "PRODUCT_B"
    assert "mutual_exclusivity_preflight" in telemetry["checked_invariants"]


@pytest.mark.parametrize(
    "prohibited_param",
    [
        {"lattice_vectors": [[5.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 5.0]]},
        {"unit_cell": [[5.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 5.0]]},
        {"cell": [10.0, 10.0, 10.0]},
        {"kpoints": (4, 4, 4)},
        {"kmesh": (2, 2, 2)},
        {"pbc": True},
        {"pbc": (True, False, False)},
        {"cutoff_energy": 520.0},
        {"encut": 400.0},
        {"pseudopotentials": {"C": "C.pbe-n-kjpaw_psl.1.0.0.UPF"}},
        {"pseudo_potentials": {"O": "O_PAW"}},
    ],
)
def test_product_b_fails_closed_on_periodic_parameters(prohibited_param):
    """Verify Product B fails closed with OntologicalCollisionError on periodic parameters."""
    job = {"product": "PRODUCT_B", "rotational_constants": [9652.14, 4826.07, 3217.38]}
    job.update(prohibited_param)
    with pytest.raises(OntologicalCollisionError) as exc_info:
        validate_product_ontology_preflight(job)
    assert "Ontological collision" in str(exc_info.value)


def test_product_m_clean_payload():
    """Verify that a clean Product M payload passes preflight validation."""
    payload = {
        "product": "PRODUCT_M",
        "lattice_vectors": [[15.0, 0.0, 0.0], [0.0, 15.0, 0.0], [0.0, 0.0, 15.0]],
        "kmesh": (1, 1, 1),
    }
    telemetry = validate_product_ontology_preflight(payload)
    assert telemetry["status"] == "VALID"
    assert telemetry["product_category"] == "PRODUCT_M"


@pytest.mark.parametrize(
    "prohibited_param",
    [
        {"rot_a": 9652.14},
        {"rot_b": 4826.07},
        {"rot_c": 3217.38},
        {"rotational_constants": [9652.14, 4826.07, 3217.38]},
        {"a_0": 9650.0},
        {"b_0": 4825.0},
        {"c_0": 3215.0},
        {"centrifugal_distortion": True},
        {"quartic_distortion": {"DJ": 0.001}},
        {"sextic_distortion": True},
        {"eckart": True},
        {"eckart_frame": "principal"},
        {"eckart_orientation": [1.0, 0.0, 0.0]},
        {"delta_b_vib": 12.45},
        {"vibrational_rotational_coupling": True},
    ],
)
def test_product_m_fails_closed_on_spectroscopic_parameters(prohibited_param):
    """Verify Product M fails closed with OntologicalCollisionError on spectroscopic parameters."""
    job = {
        "product": "PRODUCT_M",
        "lattice_vectors": [[15.0, 0.0, 0.0], [0.0, 15.0, 0.0], [0.0, 0.0, 15.0]],
        "kmesh": (1, 1, 1),
    }
    job.update(prohibited_param)
    with pytest.raises(OntologicalCollisionError) as exc_info:
        validate_product_ontology_preflight(job)
    assert "Ontological collision" in str(exc_info.value)


def test_mixed_parameters_simultaneous_collision():
    """Verify collision is triggered even if product category is undeclared."""
    mixed_job = {
        "rotational_constants": [9652.14, 4826.07, 3217.38],
        "lattice_vectors": [[5.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 5.0]],
    }
    with pytest.raises(OntologicalCollisionError):
        validate_product_ontology_preflight(mixed_job)


def test_product_m_permits_lowercase_cell_lengths():
    """Verify Product M correctly permits lowercase real-space lattice lengths a, b, c."""
    job = {
        "product": "PRODUCT_M",
        "lattice_vectors": [[5.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 5.0]],
        "kmesh": (4, 4, 4),
        "a": 5.0,
        "b": 5.0,
        "c": 5.0,
    }
    telemetry = validate_product_ontology_preflight(job)
    assert telemetry["status"] == "VALID"
    assert telemetry["product_category"] == "PRODUCT_M"


# =============================================================================
# 3. Product B Spectroscopic Boundary & Ray's Asymmetry Gate Tests (L3.2.2)
# =============================================================================

def test_product_b_ordering_invariant():
    """Verify strict physical ordering A > B > C > 0."""
    # Valid ordering
    res = validate_product_b_invariants(A=10000.0, B=5000.0, C=2000.0)
    assert res["status"] == "VALID"
    assert res["A_mhz"] == 10000.0
    assert res["B_mhz"] == 5000.0
    assert res["C_mhz"] == 2000.0

    # A <= B
    with pytest.raises(ProductDomainBoundaryViolation):
        validate_product_b_invariants(A=5000.0, B=5000.0, C=2000.0)
    with pytest.raises(ProductDomainBoundaryViolation):
        validate_product_b_invariants(A=4000.0, B=5000.0, C=2000.0)

    # B <= C
    with pytest.raises(ProductDomainBoundaryViolation):
        validate_product_b_invariants(A=10000.0, B=2000.0, C=2000.0)
    with pytest.raises(ProductDomainBoundaryViolation):
        validate_product_b_invariants(A=10000.0, B=1000.0, C=2000.0)

    # C <= 0
    with pytest.raises(ProductDomainBoundaryViolation):
        validate_product_b_invariants(A=10000.0, B=5000.0, C=0.0)
    with pytest.raises(ProductDomainBoundaryViolation):
        validate_product_b_invariants(A=10000.0, B=5000.0, C=-100.0)


def test_product_b_rays_asymmetry_parameter():
    """Verify Ray's asymmetry parameter calculation: kappa = (2B - A - C) / (A - C)."""
    # Prolate top limit (B close to C): kappa -> -1.0
    res_prolate = validate_product_b_invariants(A=10000.0, B=2001.0, C=2000.0)
    # (4002 - 12000) / 8000 = -7998 / 8000 = -0.99975
    assert math.isclose(res_prolate["kappa"], -0.99975, rel_tol=1e-5)
    assert res_prolate["rotor_type"] in ["PROLATE_SYMMETRIC_TOP", "NEAR_PROLATE_ASYMMETRIC_TOP"]

    # Oblate top limit (B close to A): kappa -> +1.0
    res_oblate = validate_product_b_invariants(A=10000.0, B=9999.0, C=2000.0)
    # (19998 - 12000) / 8000 = 7998 / 8000 = +0.99975
    assert math.isclose(res_oblate["kappa"], +0.99975, rel_tol=1e-5)
    assert res_oblate["rotor_type"] in ["OBLATE_SYMMETRIC_TOP", "NEAR_OBLATE_ASYMMETRIC_TOP"]

    # Maximally asymmetric (kappa = 0.0)
    # 2B = A + C -> B = (10000 + 2000) / 2 = 6000
    res_asym = validate_product_b_invariants(A=10000.0, B=6000.0, C=2000.0)
    assert math.isclose(res_asym["kappa"], 0.0, abs_tol=1e-9)
    assert res_asym["rotor_type"] == "HIGHLY_ASYMMETRIC_TOP"


def test_product_b_parent_anchor_ordering():
    """Verify that parent anchor constants must satisfy A_0 > B_0 > C_0 > 0."""
    with pytest.raises(InvalidRotationalAnchorError):
        # Parent A_0 <= B_0
        validate_product_b_invariants(
            A=10000.0, B=5000.0, C=2000.0,
            parent_A=4900.0, parent_B=5000.0, parent_C=2000.0,
        )

    with pytest.raises(InvalidRotationalAnchorError):
        # Incomplete parent
        validate_product_b_invariants(
            A=10000.0, B=5000.0, C=2000.0,
            parent_A=10000.0, parent_B=5000.0, parent_C=None,
        )


def test_product_b_topology_preservation_gate():
    """Verify that prolate <-> oblate topology inversion raises InvalidRotationalAnchorError."""
    # Trial is prolate: A=10000, B=3000, C=2000 -> kappa = (6000 - 12000)/8000 = -0.75
    # Parent is oblate: A=10000, B=9000, C=2000 -> kappa = (18000 - 12000)/8000 = +0.75
    with pytest.raises(InvalidRotationalAnchorError) as exc_info:
        validate_product_b_invariants(
            A=10000.0, B=3000.0, C=2000.0,
            parent_A=10000.0, parent_B=9000.0, parent_C=2000.0,
        )
    assert "Topology inversion" in str(exc_info.value)


def test_product_b_asymmetry_divergence_gate():
    """Verify that |kappa_trial - kappa_parent| > 0.05 raises InvalidRotationalAnchorError."""
    # Trial: A=10000, B=5000, C=2000 -> kappa = (10000 - 12000) / 8000 = -0.25
    # Parent: A=10000, B=4500, C=2000 -> kappa = (9000 - 12000) / 8000 = -0.375
    # delta_kappa = 0.125 > 0.05
    with pytest.raises(InvalidRotationalAnchorError) as exc_info:
        validate_product_b_invariants(
            A=10000.0, B=5000.0, C=2000.0,
            parent_A=10000.0, parent_B=4500.0, parent_C=2000.0,
        )
    assert "divergence" in str(exc_info.value).lower()


def test_product_b_calibrated_relative_shift_gate():
    """Verify relative shift |B_trial - B_parent| / B_parent <= 0.06% (0.0006)."""
    # Parent: B_0 = 5000.0 MHz. Tolerance 0.06% = 3.0 MHz.
    # Trial with B = 5002.0 MHz -> rel_error = 2.0 / 5000 = 0.04% <= 0.06% (PASS)
    res_pass = validate_product_b_invariants(
        A=10004.0, B=5002.0, C=2001.0,
        parent_A=10000.0, parent_B=5000.0, parent_C=2000.0,
        max_rel_error=DEFAULT_PRODUCT_B_MAX_ERROR_REL,
    )
    assert res_pass["status"] == "VALID"
    assert res_pass["parent_anchor"]["rel_shift_B"] <= DEFAULT_PRODUCT_B_MAX_ERROR_REL

    # Trial with B = 5005.0 MHz -> rel_error = 5.0 / 5000 = 0.10% > 0.06% (FAIL)
    with pytest.raises(ProductDomainBoundaryViolation) as exc_info:
        validate_product_b_invariants(
            A=10010.0, B=5005.0, C=2002.0,
            parent_A=10000.0, parent_B=5000.0, parent_C=2000.0,
            max_rel_error=DEFAULT_PRODUCT_B_MAX_ERROR_REL,
        )
    assert "Calibrated relative shift" in str(exc_info.value)


def test_mendeleev_dynamic_mass_resolution():
    """Verify that dynamic atomic masses are resolved via mendeleev library (Zero-Mock)."""
    h_mass = get_atomic_mass("H")
    c_mass = get_atomic_mass("C")
    c13_mass = get_atomic_mass("13C")
    d_mass = get_atomic_mass("D")

    assert math.isclose(h_mass, 1.008, rel_tol=1e-2)
    assert math.isclose(c_mass, 12.011, rel_tol=1e-2)
    assert math.isclose(c13_mass, 13.00335, rel_tol=1e-4)
    assert math.isclose(d_mass, 2.0141, rel_tol=1e-4)


# =============================================================================
# 4. Product M Crystal Symmetry & Reciprocal Density Gate Tests (L3.2.3)
# =============================================================================

def test_product_m_unit_cell_volume():
    """Verify scalar triple product volume V_cell = |a_1 . (a_2 x a_3)|."""
    # Orthogonal cell 4 x 5 x 6 = 120 A^3
    lat_ortho = np.array([[4.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 6.0]])
    v_ortho = compute_scalar_triple_product_volume(lat_ortho)
    assert math.isclose(v_ortho, 120.0, rel_tol=1e-9)

    # Triclinic cell
    lat_tri = np.array([[5.0, 0.0, 0.0], [1.0, 4.0, 0.0], [1.0, 1.0, 3.0]])
    v_tri = compute_scalar_triple_product_volume(lat_tri)
    assert math.isclose(v_tri, 60.0, rel_tol=1e-9)


def test_product_m_degenerate_cell_rejection():
    """Verify degenerate (coplanar or zero) unit cell raises InvalidPeriodicCellError."""
    # Coplanar vectors: a_3 = a_1 + a_2
    coplanar_lat = np.array([[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [2.0, 2.0, 0.0]])
    with pytest.raises(InvalidPeriodicCellError):
        validate_product_m_invariants(coplanar_lat, kmesh=(4, 4, 4))

    # Extremely small cell (V <= 1e-6)
    tiny_lat = np.diag([1e-3, 1e-3, 1e-3])  # 1e-9 A^3 <= 1e-6
    with pytest.raises(InvalidPeriodicCellError):
        validate_product_m_invariants(tiny_lat, kmesh=(4, 4, 4))


def test_product_m_reciprocal_lattice_vectors():
    """Verify reciprocal lattice vectors b_i satisfy a_i . b_j = 2*pi*delta_ij."""
    lat = np.array([[4.0, 1.0, 0.0], [0.0, 5.0, 1.0], [1.0, 0.0, 6.0]])
    v_cell = compute_scalar_triple_product_volume(lat)
    b_vecs = compute_reciprocal_lattice_vectors(lat, v_cell)

    two_pi = 2.0 * math.pi
    for i in range(3):
        for j in range(3):
            dot_prod = np.dot(lat[i], b_vecs[j])
            expected = two_pi if i == j else 0.0
            assert math.isclose(dot_prod, expected, abs_tol=1e-7)


def test_product_m_reciprocal_k_density_gate():
    """Verify Monkhorst-Pack reciprocal linear density gate rho_k,i = k_i / |b_i| >= 0.04 A^-1."""
    # Unit cell 5 x 5 x 5: |b_i| = 2*pi / 5.0 ~ 1.2566 A^-1
    # If k_i = 4, rho_k = 4 / 1.2566 = 3.18 A >= 0.04 (PASS)
    lat = np.diag([5.0, 5.0, 5.0])
    res = validate_product_m_invariants(lat, kmesh=(4, 4, 4))
    assert res["status"] == "VALID"
    assert all(rho >= 0.04 for rho in res["k_densities"])

    # If someone uses an unphysically small cell with enormous reciprocal vector and k_i=1
    # e.g., cell length 0.01 A -> |b| ~ 628.3 A^-1 -> rho_k = 1 / 628.3 = 0.00159 < 0.04 (FAIL)
    # To test pure density threshold without triggering degenerate cell (V > 1e-6):
    # Cell: a1 = 0.05 A, a2 = 10.0 A, a3 = 10.0 A -> V = 5.0 A^3 > 1e-6
    # |b_1| = 2*pi / 0.05 = 125.66 A^-1. If k_1 = 1, rho_k,1 = 1 / 125.66 = 0.00796 < 0.04 A^-1
    stretched_lat = np.diag([0.05, 10.0, 10.0])
    with pytest.raises(ReciprocalDensityViolation) as exc_info:
        validate_product_m_invariants(stretched_lat, kmesh=(1, 4, 4))
    assert "Reciprocal linear k-point density" in str(exc_info.value) and "under-resolved" in str(exc_info.value)


def test_product_m_gamma_point_ceiling_restriction():
    """Verify Gamma-point (1, 1, 1) sampling is rejected for V_cell <= 2000 A^3."""
    # V_cell = 10 x 10 x 10 = 1000 A^3 <= 2000.0 A^3
    small_cell = np.diag([10.0, 10.0, 10.0])
    with pytest.raises(ReciprocalDensityViolation) as exc_info:
        validate_product_m_invariants(small_cell, kmesh=(1, 1, 1))
    assert "Gamma-point sampling (1x1x1) is physically unphysical for sub-2000" in str(exc_info.value)

    # Supercell: V_cell = 15 x 15 x 15 = 3375 A^3 > 2000.0 A^3 (PASS)
    large_cell = np.diag([15.0, 15.0, 15.0])
    res = validate_product_m_invariants(large_cell, kmesh=(1, 1, 1))
    assert res["status"] == "VALID"
    assert res["cell_volume_angstrom3"] > 2000.0


def test_product_m_vacuum_padding_invariant():
    """Verify non-periodic directions require >= 15.0 A vacuum separation."""
    # Slab in xy-plane: pbc=(True, True, False)
    # Cell c = 12.0 A (less than 15.0 A vacuum)
    slab_small = np.diag([5.0, 5.0, 12.0])
    with pytest.raises(ProductDomainBoundaryViolation) as exc_info:
        validate_product_m_invariants(slab_small, kmesh=(4, 4, 1), pbc=(True, True, False))
    assert "Vacuum separation" in str(exc_info.value)

    # Slab with c = 25.0 A, atomic coordinates spanning z from 5.0 to 8.0 (thickness 3.0 A)
    # Vacuum separation = 25.0 - 3.0 = 22.0 A >= 15.0 A (PASS)
    slab_ok = np.diag([5.0, 5.0, 25.0])
    coords = np.array([
        [0.0, 0.0, 5.0],
        [1.0, 1.0, 8.0],
    ])
    res = validate_product_m_invariants(slab_ok, kmesh=(4, 4, 1), pbc=(True, True, False), coordinates=coords)
    assert res["status"] == "VALID"
    assert math.isclose(res["vacuum_separation_angstrom"]["axis_3"], 22.0, rel_tol=1e-5)

    # Slab with c = 25.0 A, but atoms spanning z from 2.0 to 18.0 (thickness 16.0 A)
    # Vacuum separation = 25.0 - 16.0 = 9.0 A < 15.0 A (FAIL)
    coords_thick = np.array([
        [0.0, 0.0, 2.0],
        [1.0, 1.0, 18.0],
    ])
    with pytest.raises(ProductDomainBoundaryViolation):
        validate_product_m_invariants(slab_ok, kmesh=(4, 4, 1), pbc=(True, True, False), coordinates=coords_thick)


def test_product_m_crystal_symmetry_detection():
    """Verify authentic crystal system classification from metric tensor."""
    # Cubic
    cubic_lat = np.diag([5.0, 5.0, 5.0])
    sym_cubic = detect_crystal_symmetry(cubic_lat)
    assert sym_cubic["crystal_system"].lower() == "cubic"

    # Tetragonal
    tetragonal_lat = np.diag([5.0, 5.0, 8.0])
    sym_tet = detect_crystal_symmetry(tetragonal_lat)
    assert sym_tet["crystal_system"].lower() == "tetragonal"

    # Orthorhombic
    ortho_lat = np.diag([4.0, 5.0, 6.0])
    sym_ortho = detect_crystal_symmetry(ortho_lat)
    assert sym_ortho["crystal_system"].lower() == "orthorhombic"


# =============================================================================
# 5. Product M Hardened Boundary & Numerical Stability Invariants (L3.2.3)
# =============================================================================

def test_kmesh_density_shape_validation():
    """Verify compute_kmesh_density rejects kmesh not having exactly 3 elements."""
    lat = np.diag([5.0, 5.0, 5.0])
    with pytest.raises(ReciprocalDensityViolation) as exc_info:
        compute_kmesh_density(lat, kmesh=(4, 4))  # type: ignore[arg-type]
    assert "must specify exactly 3 dimensions" in str(exc_info.value)

    with pytest.raises(ReciprocalDensityViolation) as exc_info:
        compute_kmesh_density(lat, kmesh=[4, 4, 4, 4])  # type: ignore[arg-type]
    assert "must specify exactly 3 dimensions" in str(exc_info.value)


def test_kmesh_density_non_integer_type_validation():
    """Verify compute_kmesh_density rejects float values in kmesh."""
    lat = np.diag([5.0, 5.0, 5.0])
    with pytest.raises(ReciprocalDensityViolation) as exc_info:
        compute_kmesh_density(lat, kmesh=(4, 4.5, 4))  # type: ignore[arg-type]
    assert "must be an integer" in str(exc_info.value)


def test_kmesh_density_boolean_type_validation():
    """Verify compute_kmesh_density rejects bool values in kmesh."""
    lat = np.diag([5.0, 5.0, 5.0])
    with pytest.raises(ReciprocalDensityViolation) as exc_info:
        compute_kmesh_density(lat, kmesh=(True, 4, 4))  # type: ignore[arg-type]
    assert "must be an integer" in str(exc_info.value)


def test_kmesh_density_positive_integer_validation():
    """Verify compute_kmesh_density rejects zero and negative values in kmesh."""
    lat = np.diag([5.0, 5.0, 5.0])
    with pytest.raises(ReciprocalDensityViolation) as exc_info:
        compute_kmesh_density(lat, kmesh=(0, 4, 4))
    assert "must be a positive integer" in str(exc_info.value)

    with pytest.raises(ReciprocalDensityViolation) as exc_info:
        compute_kmesh_density(lat, kmesh=(4, -2, 4))
    assert "must be a positive integer" in str(exc_info.value)


def test_vacuum_separation_axis_type_validation_float():
    """Verify compute_vacuum_separation rejects float axis values."""
    lat = np.diag([5.0, 5.0, 20.0])
    with pytest.raises(ProductDomainBoundaryViolation) as exc_info:
        compute_vacuum_separation(lat, coordinates=None, axis=1.0)  # type: ignore[arg-type]
    assert "Axis index must be integer 0, 1, or 2" in str(exc_info.value)


def test_vacuum_separation_axis_type_validation_bool():
    """Verify compute_vacuum_separation rejects boolean axis values."""
    lat = np.diag([5.0, 5.0, 20.0])
    with pytest.raises(ProductDomainBoundaryViolation) as exc_info:
        compute_vacuum_separation(lat, coordinates=None, axis=True)  # type: ignore[arg-type]
    assert "Axis index must be integer 0, 1, or 2" in str(exc_info.value)


def test_vacuum_separation_axis_out_of_bounds():
    """Verify compute_vacuum_separation rejects axis < 0 or > 2."""
    lat = np.diag([5.0, 5.0, 20.0])
    with pytest.raises(ProductDomainBoundaryViolation) as exc_info:
        compute_vacuum_separation(lat, coordinates=None, axis=3)
    assert "Axis index must be integer 0, 1, or 2" in str(exc_info.value)

    with pytest.raises(ProductDomainBoundaryViolation) as exc_info:
        compute_vacuum_separation(lat, coordinates=None, axis=-1)
    assert "Axis index must be integer 0, 1, or 2" in str(exc_info.value)


def test_vacuum_separation_invalid_coords_shape():
    """Verify compute_vacuum_separation rejects coordinates that do not have shape (N, 3)."""
    lat = np.diag([5.0, 5.0, 20.0])
    invalid_coords = np.array([[1.0, 2.0], [3.0, 4.0]])
    with pytest.raises(ProductDomainBoundaryViolation) as exc_info:
        compute_vacuum_separation(lat, coordinates=invalid_coords, axis=2)
    assert "must have shape (N, 3)" in str(exc_info.value)


def test_vacuum_separation_non_finite_coords():
    """Verify compute_vacuum_separation rejects NaN/Inf in coordinates."""
    lat = np.diag([5.0, 5.0, 20.0])
    nan_coords = np.array([[1.0, 2.0, np.nan]])
    with pytest.raises(ProductDomainBoundaryViolation) as exc_info:
        compute_vacuum_separation(lat, coordinates=nan_coords, axis=2)
    assert "non-finite values" in str(exc_info.value)


def test_isotope_resolution_deuterium():
    """Verify deuterium symbols 'D' and '2H' resolve to hydrogen."""
    assert _resolve_element_symbol("D") == "H"
    assert _resolve_element_symbol("2H") == "H"
    assert _resolve_element_symbol("d") == "H"


def test_isotope_resolution_tritium():
    """Verify tritium symbols 'T' and '3H' resolve to hydrogen."""
    assert _resolve_element_symbol("T") == "H"
    assert _resolve_element_symbol("3H") == "H"
    assert _resolve_element_symbol("t") == "H"


def test_isotope_resolution_carbon13_and_numeric_z():
    """Verify numbered isotopes ('13C', '18O') and numeric Z resolve accurately."""
    assert _resolve_element_symbol("13C") == "C"
    assert _resolve_element_symbol("18O") == "O"
    assert _resolve_element_symbol(6) == "C"
    assert _resolve_element_symbol(np.int64(8)) == "O"


def test_detect_crystal_symmetry_with_isotopes():
    """Verify detect_crystal_symmetry executes dynamically with isotopic element symbols."""
    cubic_lat = np.diag([5.0, 5.0, 5.0])
    coords = np.array([[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])
    res = detect_crystal_symmetry(cubic_lat, coordinates=coords, atomic_symbols=["D", "13C"])
    assert res["crystal_system"].lower() == "cubic"


def test_detect_crystal_symmetry_with_atomic_numbers():
    """Verify detect_crystal_symmetry functions with atomic_numbers explicitly provided."""
    ortho_lat = np.diag([4.0, 5.0, 6.0])
    coords = np.array([[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])
    res = detect_crystal_symmetry(ortho_lat, coordinates=coords, atomic_numbers=[1, 6])
    assert res["crystal_system"].lower() == "orthorhombic"


def test_validate_product_m_kmesh_shape_validation():
    """Verify validate_product_m_invariants rejects kmesh with length != 3."""
    lat = np.diag([5.0, 5.0, 5.0])
    with pytest.raises(ReciprocalDensityViolation) as exc_info:
        validate_product_m_invariants(lat, kmesh=(4, 4))  # type: ignore[arg-type]
    assert "k-point mesh must specify exactly 3 dimensions" in str(exc_info.value)


def test_validate_product_m_pbc_shape_validation():
    """Verify validate_product_m_invariants rejects pbc with length != 3."""
    lat = np.diag([5.0, 5.0, 5.0])
    with pytest.raises(ProductDomainBoundaryViolation) as exc_info:
        validate_product_m_invariants(lat, kmesh=(4, 4, 4), pbc=(True, True))  # type: ignore[arg-type]
    assert "Periodic boundary conditions (pbc) must specify exactly 3 axes" in str(exc_info.value)


def test_validate_product_m_kmesh_non_sequence_scalar_fails_closed():
    """Verify validate_product_m_invariants rejects non-sequence scalar kmesh with ReciprocalDensityViolation [M]."""
    lat = np.diag([5.0, 5.0, 5.0])
    for bad_kmesh in [4, 4.0, "444", None, True]:
        with pytest.raises(ReciprocalDensityViolation) as exc_info:
            validate_product_m_invariants(lat, kmesh=bad_kmesh)  # type: ignore[arg-type]
        assert "k-point mesh must be a sequence of 3 integers" in str(exc_info.value)


def test_compute_kmesh_density_non_sequence_scalar_fails_closed():
    """Verify compute_kmesh_density rejects non-sequence scalar kmesh with ReciprocalDensityViolation [M]."""
    lat = np.diag([5.0, 5.0, 5.0])
    for bad_kmesh in [4, 4.5, "444", None]:
        with pytest.raises(ReciprocalDensityViolation) as exc_info:
            compute_kmesh_density(lat, kmesh=bad_kmesh)  # type: ignore[arg-type]
        assert "k-point mesh must be a sequence of 3 integers" in str(exc_info.value)


def test_validate_product_m_pbc_boolean_scalar_and_invalid_scalar_fails_closed():
    """Verify validate_product_m_invariants accepts boolean scalars and rejects invalid non-sequence scalars [M]."""
    lat = np.diag([5.0, 5.0, 5.0])
    # Boolean scalar True broadcasts to (True, True, True)
    res_bool = validate_product_m_invariants(lat, kmesh=(4, 4, 4), pbc=True)
    assert res_bool["status"] == "VALID"
    assert res_bool["pbc"] == [True, True, True]

    # np.bool_ scalar True
    res_np_bool = validate_product_m_invariants(lat, kmesh=(4, 4, 4), pbc=np.bool_(True))
    assert res_np_bool["status"] == "VALID"
    assert res_np_bool["pbc"] == [True, True, True]

    # Non-sequence invalid scalars must raise ProductDomainBoundaryViolation (not TypeError crash)
    for bad_pbc in [123, 1.0, "periodic", None]:
        with pytest.raises(ProductDomainBoundaryViolation) as exc_info:
            validate_product_m_invariants(lat, kmesh=(4, 4, 4), pbc=bad_pbc)  # type: ignore[arg-type]
        assert "Periodic boundary conditions (pbc) must be a 3-element boolean sequence or boolean scalar" in str(exc_info.value)


def test_compute_cell_volume_enforce_non_degenerate():
    """Verify compute_cell_volume with enforce_non_degenerate=True rejects degenerate cells [M]."""
    coplanar_lat = np.array([[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [2.0, 2.0, 0.0]])
    # Without enforce_non_degenerate, returns 0.0
    assert compute_cell_volume(coplanar_lat) == 0.0

    # With enforce_non_degenerate=True, raises InvalidPeriodicCellError
    with pytest.raises(InvalidPeriodicCellError) as exc_info:
        compute_cell_volume(coplanar_lat, enforce_non_degenerate=True)
    assert "degenerate or non-positive" in str(exc_info.value)


def test_detect_crystal_symmetry_degenerate_cell_rejection():
    """Verify detect_crystal_symmetry raises InvalidPeriodicCellError for degenerate unit cells [M]."""
    coplanar_lat = np.array([[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [2.0, 2.0, 0.0]])
    with pytest.raises(InvalidPeriodicCellError) as exc_info:
        detect_crystal_symmetry(coplanar_lat)
    assert "Degenerate unit cell volume" in str(exc_info.value)


def test_preflight_pbc_numpy_boolean_scalar_detection():
    """Verify validate_product_ontology_preflight detects np.bool_ in pbc [M]."""
    payload_b = {
        "product": "PRODUCT_B",
        "parameters": {
            "pbc": np.bool_(True),
        },
    }
    with pytest.raises(OntologicalCollisionError) as exc_info:
        validate_product_ontology_preflight(payload_b)
    assert "prohibited solid-state periodic parameters" in str(exc_info.value)


def test_preflight_pbc_numpy_ndarray_detection():
    """Verify validate_product_ontology_preflight detects np.ndarray in pbc [M]."""
    payload_b = {
        "product": "PRODUCT_B",
        "parameters": {
            "pbc": np.array([True, False, False]),
        },
    }
    with pytest.raises(OntologicalCollisionError) as exc_info:
        validate_product_ontology_preflight(payload_b)
    assert "prohibited solid-state periodic parameters" in str(exc_info.value)


def test_preflight_enum_declared_product_extraction():
    """Verify validate_product_ontology_preflight extracts string from enum objects [M]."""
    from cochem_base.formatters.cochem_inertial_defect_validator import ProductClass
    from cochem_base.executors.hpc_workflow_router import ProductCategory

    # Test ProductClass enum
    payload_b_enum = {
        "product_class": ProductClass.PRODUCT_B_SEMI_EXPERIMENTAL,
        "keywords": {"cutoff_energy": 500.0},
    }
    with pytest.raises(OntologicalCollisionError) as exc_info:
        validate_product_ontology_preflight(payload_b_enum)
    assert "Job declared as Product B" in str(exc_info.value)

    # Test ProductCategory enum
    payload_m_enum = {
        "product_category": ProductCategory.PRODUCT_M,
        "keywords": {"rotational_constants": [1000.0, 500.0, 250.0]},
    }
    with pytest.raises(OntologicalCollisionError) as exc_info:
        validate_product_ontology_preflight(payload_m_enum)
    assert "Job declared as Product M" in str(exc_info.value)


# =============================================================================
# 6. Adversarial Evasion Hardening Tests (L3.2.1 Boundary Invariants)
# =============================================================================

def test_adversarial_pbc_0d_and_multid_numpy_arrays():
    """Verify preflight correctly evaluates 0-D and multi-D NumPy arrays without crashing [M]."""
    # 0-D true
    payload_0d_true = {"product": "PRODUCT_B", "pbc": np.array(True)}
    with pytest.raises(OntologicalCollisionError) as exc_info:
        validate_product_ontology_preflight(payload_0d_true)
    assert "prohibited solid-state periodic parameters" in str(exc_info.value)

    # 0-D false passes for Product B
    payload_0d_false = {"product": "PRODUCT_B", "pbc": np.array(False), "rot_a": 5000.0}
    res = validate_product_ontology_preflight(payload_0d_false)
    assert res["status"] == "VALID"

    # Multi-D array with active boundary
    payload_2d = {"product": "PRODUCT_B", "pbc": np.array([[False, True], [False, False]])}
    with pytest.raises(OntologicalCollisionError):
        validate_product_ontology_preflight(payload_2d)


@pytest.mark.parametrize(
    "pbc_active_val",
    [
        1,
        np.int64(1),
        1.0,
        "True",
        "true",
        "1",
        "yes",
        "active",
        "periodic",
        [0, 1, 0],
        (False, True, False),
    ],
)
def test_adversarial_pbc_scalar_and_string_representations(pbc_active_val):
    """Verify active PBC encoded as integer, float, string, or mixed sequence fails closed [M]."""
    payload = {
        "product": "PRODUCT_B",
        "parameters": {"pbc": pbc_active_val},
    }
    with pytest.raises(OntologicalCollisionError) as exc_info:
        validate_product_ontology_preflight(payload)
    assert "prohibited solid-state periodic parameters" in str(exc_info.value)


def test_adversarial_enum_with_non_string_values():
    """Verify enums with integer or custom values resolve to canonical product identifiers [M]."""
    from enum import Enum, IntEnum

    class CustomIntDomain(IntEnum):
        PRODUCT_B = 101
        PRODUCT_M = 202

    class CustomObjectDomain(Enum):
        B = "domain_b_marker"
        M = "domain_m_marker"

    # IntEnum for Product B
    job_b = {"product": CustomIntDomain.PRODUCT_B, "cutoff_energy": 500.0}
    with pytest.raises(OntologicalCollisionError) as exc_info:
        validate_product_ontology_preflight(job_b)
    assert "Job declared as Product B" in str(exc_info.value)

    # Custom enum for Product M
    job_m = {"product": CustomObjectDomain.M, "rotational_constants": [1000.0, 500.0, 250.0]}
    with pytest.raises(OntologicalCollisionError) as exc_info:
        validate_product_ontology_preflight(job_m)
    assert "Job declared as Product M" in str(exc_info.value)


@pytest.mark.parametrize(
    "declared_key,declared_val",
    [
        ("product", "Product-B"),
        ("product", "Product_B"),
        ("product", "ProductB"),
        ("domain", "gas_phase"),
        ("product_type", "rotational_spectroscopy"),
    ],
)
def test_adversarial_product_b_normalization_evasion(declared_key, declared_val):
    """Verify hyphenated, lowercase, and alias domain representations are caught [M]."""
    job = {declared_key: declared_val, "kmesh": (4, 4, 4)}
    with pytest.raises(OntologicalCollisionError) as exc_info:
        validate_product_ontology_preflight(job)
    assert "Job declared as Product B" in str(exc_info.value)


@pytest.mark.parametrize(
    "declared_key,declared_val",
    [
        ("product", "Product-M"),
        ("product", "Product_M"),
        ("product", "ProductM"),
        ("domain", "materials"),
        ("domain", "solid_state"),
        ("product_class", "crystal"),
    ],
)
def test_adversarial_product_m_normalization_evasion(declared_key, declared_val):
    """Verify Product M aliases and hyphenated strings trigger spectroscopic collision [M]."""
    job = {declared_key: declared_val, "rot_constants": [10000.0, 5000.0, 2000.0]}
    with pytest.raises(OntologicalCollisionError) as exc_info:
        validate_product_ontology_preflight(job)
    assert "Job declared as Product M" in str(exc_info.value)


def test_adversarial_nested_dataclass_and_object_detection():
    """Verify parameters nested within dataclasses or custom class instances are traversed [M]."""
    from dataclasses import dataclass

    @dataclass
    class SolidStateConfig:
        cutoff_energy: float = 600.0
        kpoints: tuple = (6, 6, 6)

    @dataclass
    class SpectroscopicConfig:
        ray_asymmetry: float = -0.45
        rot_a: float = 8500.0

    # Product B job hiding solid-state config inside nested dataclass
    job_b = {
        "product": "PRODUCT_B",
        "settings": {
            "calc_config": SolidStateConfig(),
        },
    }
    with pytest.raises(OntologicalCollisionError) as exc_info:
        validate_product_ontology_preflight(job_b)
    assert "prohibited solid-state periodic parameters" in str(exc_info.value)

    # Product M job hiding spectroscopic config inside nested dataclass
    job_m = {
        "product": "PRODUCT_M",
        "settings": {
            "spectroscopy": SpectroscopicConfig(),
        },
    }
    with pytest.raises(OntologicalCollisionError) as exc_info:
        validate_product_ontology_preflight(job_m)
    assert "prohibited gas-phase microwave spectroscopic parameters" in str(exc_info.value)


def test_adversarial_expanded_prohibited_keywords():
    """Verify expanded periodic keywords in Product B and spectroscopic keywords in Product M [M]."""
    # Periodic keywords in Product B
    periodic_tests = [
        {"kgrid": (4, 4, 4)},
        {"gamma_point": True},
        {"reciprocal_lattice": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]},
        {"supercell": [2, 2, 2]},
        {"spacegroup": 225},
        {"space_group": "Fm-3m"},
        {"brillouin_zone": "monkhorst"},
    ]
    for p_dict in periodic_tests:
        job = {"product": "PRODUCT_B", **p_dict}
        with pytest.raises(OntologicalCollisionError):
            validate_product_ontology_preflight(job)

    # Spectroscopic keywords in Product M
    spectroscopic_tests = [
        {"ray_asymmetry": -0.8},
        {"ray_asymmetry_parameter": -0.5},
        {"ray_kappa": 0.1},
        {"kappa": 0.0},
        {"asymmetry_parameter": 0.2},
        {"dipole_moment_debye": 1.85},
        {"microwave_transitions": [12345.67]},
        {"rotational_spectrum": True},
        {"quadrupole_coupling": [1.2, 3.4]},
        {"spin_rotation": 0.005},
    ]
    for s_dict in spectroscopic_tests:
        job = {"product": "PRODUCT_M", "lattice_vectors": [[5.0, 0, 0], [0, 5.0, 0], [0, 0, 5.0]], **s_dict}
        with pytest.raises(OntologicalCollisionError):
            validate_product_ontology_preflight(job)



