"""Zero-Mock Production Test Suite for Preflight Boundary Invariant Gatekeepers.

Verifies Tasks L3.2.1, L3.2.2, and L3.2.3:
- L3.2.1: Domain Integrity Preflight Guard & Mutual Exclusivity Validator
- L3.2.2: Product B Spectroscopic Boundary & Ray's Asymmetry Parameter Gate
- L3.2.3: Product M Crystal Symmetry & Reciprocal Density Gate

Strictly satisfies:
- Method Matrix v4 Sections 1.2, 2.2, 3.0, and 4.4
- Mendeleev Mandate: dynamic elemental and mass resolution
- Zero-Mock Anti-Spoofing: zero placeholder stubs, zero dummy mocks, real physics.
"""

from __future__ import annotations

import math
from typing import Any, Dict

import numpy as np
import pytest
from mendeleev import element

from cochem_base.calc.materials_preflight import (
    GAMMA_POINT_VOLUME_CEILING_ANG3,
    MIN_RECIPROCAL_K_DENSITY_ANG_INV,
    MIN_UNIT_CELL_VOLUME_ANG3,
    MIN_VACUUM_SEPARATION_ANG,
    compute_cell_volume,
    compute_kmesh_density,
    compute_reciprocal_vectors,
    compute_vacuum_separation,
    detect_crystal_symmetry,
    validate_product_m_invariants,
)
from cochem_base.calc.preflight import validate_product_ontology_preflight
from cochem_base.core.models import CalculationJobPayload
from cochem_base.exceptions import (
    _EXCEPTION_REGISTRY,
    InvalidPeriodicCellError,
    InvalidRotationalAnchorError,
    OntologicalCollisionError,
    ProductDomainBoundaryViolation,
    ReciprocalDensityViolation,
)
from cochem_base.formatters.cochem_inertial_defect_validator import (
    DEFAULT_PRODUCT_B_MAX_ERROR_REL,
    get_atomic_mass,
    validate_product_b_invariants,
)


# =============================================================================
# 1. Exception Hierarchy & Deserialization Tests (L3.2.1)
# =============================================================================

def test_exception_registry_and_polymorphic_deserialization() -> None:
    """Verifies that all L3 exception classes are properly registered and serialize polymorphically."""
    assert "OntologicalCollisionError" in _EXCEPTION_REGISTRY
    assert "ProductDomainBoundaryViolation" in _EXCEPTION_REGISTRY
    assert "ReciprocalDensityViolation" in _EXCEPTION_REGISTRY
    assert "InvalidRotationalAnchorError" in _EXCEPTION_REGISTRY
    assert "InvalidPeriodicCellError" in _EXCEPTION_REGISTRY

    # Check inheritance hierarchy
    assert issubclass(OntologicalCollisionError, _EXCEPTION_REGISTRY["MethodMatrixViolationError"])
    assert issubclass(ProductDomainBoundaryViolation, _EXCEPTION_REGISTRY["MethodMatrixViolationError"])
    assert issubclass(ReciprocalDensityViolation, ProductDomainBoundaryViolation)
    assert issubclass(InvalidRotationalAnchorError, ProductDomainBoundaryViolation)
    assert issubclass(InvalidPeriodicCellError, ProductDomainBoundaryViolation)

    # Test serialization and roundtrip deserialization
    exc = ReciprocalDensityViolation(
        "Density 0.02 is under threshold",
        details={"axis": 1, "k_val": 2},
    )
    json_repr = exc.to_json()
    reconstructed = _EXCEPTION_REGISTRY["ReciprocalDensityViolation"].from_json(json_repr)
    assert isinstance(reconstructed, ReciprocalDensityViolation)
    assert reconstructed.message == exc.message
    assert reconstructed.details == exc.details

    # Verify pedagogical guidance
    guidance = exc.to_pedagogical_guidance()
    assert "k-point mesh density" in guidance or "Brillouin zone" in guidance


# =============================================================================
# 2. Domain Mutual Exclusivity Preflight Guard Tests (L3.2.1)
# =============================================================================

def test_product_b_clean_payload_passes() -> None:
    """Verifies that a valid Product B payload passes preflight validation."""
    job_spec = {
        "product": "PRODUCT_B",
        "molecule": {"symbols": ["H", "F"], "geometry": [0.0, 0.0, 0.0, 0.0, 0.0, 0.92]},
        "keywords": {
            "rotational_constants": [30000.0, 10000.0, 8000.0],
            "centrifugal_distortion": True,
            "vibrational_rotational_coupling": True,
        },
    }
    telemetry = validate_product_ontology_preflight(job_spec)
    assert telemetry["status"] == "VALID"
    assert telemetry["product_category"] == "PRODUCT_B"
    assert "domain_integrity_guard" in telemetry["checked_invariants"]


@pytest.mark.parametrize(
    "forbidden_key,forbidden_val",
    [
        ("lattice_vectors", [[10.0, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]]),
        ("unit_cell", [10.0, 10.0, 10.0, 90.0, 90.0, 90.0]),
        ("kpoints", [4, 4, 4]),
        ("kmesh", (2, 2, 2)),
        ("pbc", True),
        ("pbc", (True, True, True)),
        ("cutoff_energy", 400.0),
        ("pseudo_potentials", {"C": "C.pbe-n-kjpaw_psl.1.0.0.UPF"}),
    ],
)
def test_product_b_rejects_periodic_parameters(forbidden_key: str, forbidden_val: Any) -> None:
    """Verifies that declaring Product B with solid-state parameters fails closed immediately."""
    job_spec = {
        "product": "PRODUCT_B",
        "keywords": {
            forbidden_key: forbidden_val,
        },
    }
    with pytest.raises(OntologicalCollisionError) as exc_info:
        validate_product_ontology_preflight(job_spec)

    assert "Ontological collision" in str(exc_info.value)
    assert "Product B" in str(exc_info.value)


def test_product_m_clean_payload_passes() -> None:
    """Verifies that a valid Product M payload passes preflight validation."""
    job_spec = {
        "product": "PRODUCT_M",
        "lattice_vectors": [[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 4.0]],
        "kmesh": (6, 6, 6),
        "cutoff_energy": 520.0,
        "pbc": [True, True, True],
    }
    telemetry = validate_product_ontology_preflight(job_spec)
    assert telemetry["status"] == "VALID"
    assert telemetry["product_category"] == "PRODUCT_M"


@pytest.mark.parametrize(
    "spectroscopic_key,spectroscopic_val",
    [
        ("rotational_constants", [12000.0, 6000.0, 4000.0]),
        ("centrifugal_distortion", True),
        ("eckart_frame", True),
        ("vibrational_rotational_coupling", True),
        ("delta_b_vib", -45.2),
        ("inertial_defect", 0.05),
    ],
)
def test_product_m_rejects_spectroscopic_parameters(spectroscopic_key: str, spectroscopic_val: Any) -> None:
    """Verifies that declaring Product M with microwave spectroscopic parameters fails closed immediately."""
    job_spec = {
        "product": "PRODUCT_M",
        "lattice_vectors": [[5.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 5.0]],
        "keywords": {
            spectroscopic_key: spectroscopic_val,
        },
    }
    with pytest.raises(OntologicalCollisionError) as exc_info:
        validate_product_ontology_preflight(job_spec)

    assert "Ontological collision" in str(exc_info.value)
    assert "Product M" in str(exc_info.value)


def test_undeclared_simultaneous_collision_rejected() -> None:
    """Verifies that undeclared payloads mixing periodic and spectroscopic parameters fail closed."""
    job_spec = {
        "lattice_vectors": [[10.0, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]],
        "rotational_constants": [5000.0, 2500.0, 1200.0],
    }
    with pytest.raises(OntologicalCollisionError) as exc_info:
        validate_product_ontology_preflight(job_spec)

    assert "mixes gas-phase microwave spectroscopic parameters" in str(exc_info.value)


def test_pydantic_calculation_job_payload_support() -> None:
    """Verifies that preflight validation works seamlessly with Pydantic CalculationJobPayload."""
    payload = CalculationJobPayload(
        driver="energy",
        keywords={
            "product": "PRODUCT_B",
            "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        },
    )
    with pytest.raises(OntologicalCollisionError):
        validate_product_ontology_preflight(payload)


# =============================================================================
# 3. Product B Spectroscopic Boundary & Ray's Asymmetry Gate Tests (L3.2.2)
# =============================================================================

def test_validate_product_b_invariants_valid_ordering() -> None:
    """Verifies valid physical rotational constants pass with correct Ray's kappa."""
    # Near-prolate asymmetric top: A=9000, B=3000, C=2500 MHz
    res = validate_product_b_invariants(A=9000.0, B=3000.0, C=2500.0)
    assert res["status"] == "VALID"
    assert res["A"] == 9000.0
    assert res["B"] == 3000.0
    assert res["C"] == 2500.0

    # kappa = (2*3000 - 9000 - 2500) / (9000 - 2500) = (6000 - 11500) / 6500 = -5500 / 6500 = -0.8461538...
    expected_kappa = (2.0 * 3000.0 - 9000.0 - 2500.0) / (9000.0 - 2500.0)
    assert math.isclose(res["kappa"], expected_kappa, rel_tol=1e-6)
    assert -1.0 <= res["kappa"] <= 1.0


@pytest.mark.parametrize(
    "a,b,c",
    [
        (3000.0, 5000.0, 2000.0),  # A <= B
        (5000.0, 2000.0, 3000.0),  # B <= C
        (5000.0, 3000.0, -100.0),  # C <= 0
        (5000.0, 5000.0, 2000.0),  # A == B (strict ordering A > B violated)
        (5000.0, 3000.0, 3000.0),  # B == C (strict ordering B > C violated)
    ],
)
def test_validate_product_b_invariants_ordering_violations(a: float, b: float, c: float) -> None:
    """Verifies that non-strictly ordered rotational constants raise ProductDomainBoundaryViolation."""
    with pytest.raises(ProductDomainBoundaryViolation) as exc_info:
        validate_product_b_invariants(A=a, B=b, C=c)
    assert "strict physical ordering A > B > C > 0" in str(exc_info.value)


def test_validate_product_b_parent_anchor_relative_shift_ok() -> None:
    """Verifies that parent anchor within 0.06% passes."""
    parent_b = 3000.0
    # Trial shift: +0.03% (within 0.06% = 0.0006)
    trial_b = parent_b * (1.0 + 0.0003)  # 3000.9 MHz

    res = validate_product_b_invariants(
        A=9000.0,
        B=trial_b,
        C=2500.0,
        parent_A=9001.0,
        parent_B=parent_b,
        parent_C=2500.5,
        max_rel_error=DEFAULT_PRODUCT_B_MAX_ERROR_REL,
    )
    assert res["status"] == "VALID"
    assert res["rel_error_B"] is not None
    assert res["rel_error_B"] <= DEFAULT_PRODUCT_B_MAX_ERROR_REL


def test_validate_product_b_parent_anchor_relative_shift_exceeded() -> None:
    """Verifies that relative error on B exceeding 0.06% raises ProductDomainBoundaryViolation."""
    parent_b = 3000.0
    # Trial shift: +0.08% (exceeds 0.06% ceiling)
    trial_b = parent_b * (1.0 + 0.0008)  # 3002.4 MHz

    with pytest.raises(ProductDomainBoundaryViolation) as exc_info:
        validate_product_b_invariants(
            A=9000.0,
            B=trial_b,
            C=2500.0,
            parent_A=9000.0,
            parent_B=parent_b,
            parent_C=2500.0,
            max_rel_error=DEFAULT_PRODUCT_B_MAX_ERROR_REL,
        )
    assert "exceeds calibrated uncertainty tolerance" in str(exc_info.value)


def test_validate_product_b_topology_inversion_detected() -> None:
    """Verifies that topology inversion (prolate <-> oblate) between parent and trial raises InvalidRotationalAnchorError."""
    # Trial: near-prolate top (kappa < 0)
    # A=9000, B=3000, C=2500 -> kappa = -0.846
    # Parent: near-oblate top (kappa > 0)
    # A_0=9000, B_0=8000, C_0=2500 -> kappa = (16000 - 11500) / 6500 = +4500 / 6500 = +0.692
    with pytest.raises(InvalidRotationalAnchorError) as exc_info:
        validate_product_b_invariants(
            A=9000.0,
            B=3000.0,
            C=2500.0,
            parent_A=9000.0,
            parent_B=8000.0,
            parent_C=2500.0,
            max_rel_error=1.0,  # loosen relative error to test topology inversion
        )
    assert "Topology inversion detected" in str(exc_info.value)


def test_validate_product_b_asymmetry_drift_exceeded() -> None:
    """Verifies that Ray's asymmetry drift |kappa_trial - kappa_parent| > 0.05 raises InvalidRotationalAnchorError."""
    # Trial: A=9000, B=3000, C=2500 -> kappa = -0.84615
    # Parent: A_0=9000, B_0=3500, C_0=2500 -> kappa = (7000 - 11500) / 6500 = -4500 / 6500 = -0.6923
    # |delta_kappa| = |-0.84615 - (-0.6923)| = 0.1538 > 0.05
    with pytest.raises(InvalidRotationalAnchorError) as exc_info:
        validate_product_b_invariants(
            A=9000.0,
            B=3000.0,
            C=2500.0,
            parent_A=9000.0,
            parent_B=3500.0,
            parent_C=2500.0,
            max_rel_error=1.0,
        )
    assert "Ray's asymmetry parameter drift" in str(exc_info.value)


def test_dynamic_mass_resolution_mendeleev() -> None:
    """Verifies Mendeleev dynamic mass resolution protocol."""
    c_weight = float(element("C").atomic_weight)
    c_retrieved = get_atomic_mass("C")
    assert math.isclose(c_retrieved, c_weight, rel_tol=1e-7)


# =============================================================================
# 4. Product M Crystal Symmetry & Reciprocal Density Gate Tests (L3.2.3)
# =============================================================================

def test_compute_cell_volume_and_reciprocal_orthorhombic() -> None:
    """Verifies analytic scalar triple product volume and reciprocal vectors for an orthogonal cell."""
    # 5 x 4 x 3 A cell
    lattice = np.array([
        [5.0, 0.0, 0.0],
        [0.0, 4.0, 0.0],
        [0.0, 0.0, 3.0],
    ])
    vol = compute_cell_volume(lattice)
    assert math.isclose(vol, 60.0, rel_tol=1e-9)

    recip = compute_reciprocal_vectors(lattice)
    # b_i = 2pi / a_i for orthogonal axes
    assert math.isclose(recip[0, 0], 2.0 * math.pi / 5.0, rel_tol=1e-9)
    assert math.isclose(recip[1, 1], 2.0 * math.pi / 4.0, rel_tol=1e-9)
    assert math.isclose(recip[2, 2], 2.0 * math.pi / 3.0, rel_tol=1e-9)

    # Cross relation: a_i . b_j = 2pi delta_ij
    dot_prod = np.dot(lattice, recip.T)
    expected_dot = np.array([
        [2.0 * math.pi, 0.0, 0.0],
        [0.0, 2.0 * math.pi, 0.0],
        [0.0, 0.0, 2.0 * math.pi],
    ], dtype=np.float64)
    np.testing.assert_allclose(dot_prod, expected_dot, atol=1e-12)


def test_degenerate_cell_volume_raises_invalid_periodic_cell() -> None:
    """Verifies that coplanar or zero-volume lattice vectors raise InvalidPeriodicCellError."""
    # Coplanar lattice vectors: a3 = a1 + a2
    degenerate_lattice = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [1.0, 1.0, 0.0],
    ])
    with pytest.raises(InvalidPeriodicCellError) as exc_info:
        validate_product_m_invariants(degenerate_lattice, kmesh=(4, 4, 4))
    assert "degenerate or non-positive" in str(exc_info.value)


def test_reciprocal_density_gate_under_resolved_raises() -> None:
    """Verifies that k-mesh density rho_k < 0.04 A^-1 raises ReciprocalDensityViolation."""
    # a = 0.5 A cell -> |b| = 2*pi / 0.5 = 4*pi ~ 12.566 A^-1
    # For k=1: rho_k = 1 / 12.566 ~ 0.0795
    # If a = 0.1 A -> |b| = 20*pi ~ 62.83 A^-1
    # For k=1: rho_k = 1 / 62.83 ~ 0.0159 < 0.04
    lattice = np.diag([0.1, 10.0, 10.0])
    with pytest.raises(ReciprocalDensityViolation) as exc_info:
        validate_product_m_invariants(lattice, kmesh=(1, 4, 4))
    assert "Reciprocal linear k-point density along axis 1 is under-resolved" in str(exc_info.value)


def test_gamma_point_sub_2000_ang3_raises() -> None:
    """Verifies that Gamma-point only sampling (1, 1, 1) on unit cells <= 2000 A^3 is rejected."""
    # 10 x 10 x 10 A cell -> V = 1000 A^3 <= 2000 A^3
    lattice = np.diag([10.0, 10.0, 10.0])
    with pytest.raises(ReciprocalDensityViolation) as exc_info:
        validate_product_m_invariants(lattice, kmesh=(1, 1, 1))
    assert "Gamma-point sampling (1x1x1) is physically unphysical for sub-2000" in str(exc_info.value)


def test_gamma_point_supercell_over_2000_ang3_passes() -> None:
    """Verifies that Gamma-point only sampling (1, 1, 1) on large supercells (> 2000 A^3) passes."""
    # 15 x 15 x 15 A cell -> V = 3375 A^3 > 2000 A^3
    lattice = np.diag([15.0, 15.0, 15.0])
    telemetry = validate_product_m_invariants(lattice, kmesh=(1, 1, 1))
    assert telemetry["status"] == "VALID"
    assert telemetry["cell_volume_ang3"] == 3375.0
    assert any("gamma_point_supercell_volume_valid" in c for c in telemetry["checked_invariants"])


def test_vacuum_padding_slab_boundary_check() -> None:
    """Verifies that non-periodic directions enforce >= 15.0 A vacuum separation."""
    # Slab along z-axis: pbc = (True, True, False)
    # Cell height z = 30.0 A
    # Atoms span z from 5.0 to 10.0 A (thickness = 5.0 A) -> vacuum = 30 - 5 = 25 A >= 15 A (PASS)
    lattice = np.diag([4.0, 4.0, 30.0])
    coords_valid = np.array([
        [0.0, 0.0, 5.0],
        [1.0, 1.0, 10.0],
    ])
    telemetry = validate_product_m_invariants(
        lattice_vectors=lattice,
        kmesh=(6, 6, 1),
        pbc=(True, True, False),
        coordinates=coords_valid,
    )
    assert telemetry["status"] == "VALID"
    assert telemetry["vacuum_separations_ang"]["axis_3"] == 25.0

    # Insufficient vacuum: atoms span z from 2.0 to 20.0 A (thickness = 18.0 A) -> vacuum = 30 - 18 = 12 A < 15 A (FAIL)
    coords_insufficient = np.array([
        [0.0, 0.0, 2.0],
        [1.0, 1.0, 20.0],
    ])
    with pytest.raises(ProductDomainBoundaryViolation) as exc_info:
        validate_product_m_invariants(
            lattice_vectors=lattice,
            kmesh=(6, 6, 1),
            pbc=(True, True, False),
            coordinates=coords_insufficient,
        )
    assert "Vacuum separation along non-periodic axis 3 is 12.000 A" in str(exc_info.value)


def test_crystal_symmetry_detection_metric_tensor() -> None:
    """Verifies that pure numpy metric tensor analysis accurately classifies crystal systems."""
    # Cubic: a = b = c, all 90
    cubic_lat = np.diag([5.0, 5.0, 5.0])
    sym_cubic = detect_crystal_symmetry(cubic_lat)
    assert sym_cubic["crystal_system"] == "Cubic"

    # Tetragonal: a = b != c, all 90
    tet_lat = np.diag([5.0, 5.0, 8.0])
    sym_tet = detect_crystal_symmetry(tet_lat)
    assert sym_tet["crystal_system"] == "Tetragonal"

    # Orthorhombic: a != b != c, all 90
    ortho_lat = np.diag([5.0, 6.0, 7.0])
    sym_ortho = detect_crystal_symmetry(ortho_lat)
    assert sym_ortho["crystal_system"] == "Orthorhombic"

    # Hexagonal: a = b != c, alpha=beta=90, gamma=120
    hex_lat = np.array([
        [5.0, 0.0, 0.0],
        [-2.5, 5.0 * math.sqrt(3) / 2.0, 0.0],
        [0.0, 0.0, 10.0],
    ])
    sym_hex = detect_crystal_symmetry(hex_lat)
    assert sym_hex["crystal_system"] == "Hexagonal"
