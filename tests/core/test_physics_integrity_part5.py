"""Zero-Mock Physics Invariants, QCSchema, CODATA & Asymmetric Provenance Test Suite (Part 5).

Validates Suggestions #43, #46, #47, #48, #49, and #50.
Adheres strictly to Method Matrix v4 and Zero-Mock Anti-Spoofing Protocol v2.
Real physical execution: authentic Mendeleev dynamic lookup, RFC 8032 Ed25519 keys, MolSSI QCSchema.
"""

from __future__ import annotations

import base64
import math
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from cochem.core.mendeleev_invariants import MendeleevInvariantError, get_element
from cochem_base.core.cochem_crypto import (
    canonicalize_json,
    generate_ed25519_key_pair,
    sign_canonical_bytes,
    verify_canonical_signature,
)
from cochem_base.core.glossary import (
    ANGSTROM_TO_BOHR,
    BOHR_TO_ANGSTROM,
    HARTREE_TO_KCAL_MOL,
    ROTATIONAL_INERTIA_CONVERSION,
    UnitConversionConstants,
)
from cochem_base.core.models import MolecularTopology, QCResultsRecord
from cochem_base.core_engine.cochem_core_pes_store import PESPointRecord, QCSchemaProvenance


def test_mendeleev_element_tokenization_and_isotopes() -> None:
    """Validate IUPAC regex tokenization for oxidation states and isotopic mass lookups (Suggestion #43)."""
    # 1. Iron(II) cation: formal charge +2, standard atomic weight ~55.845 u [M]
    fe = get_element("Fe2+")
    assert fe.symbol == "Fe"
    assert fe.atomic_number == 26
    assert fe.formal_charge == 2
    assert fe.is_isotope is False
    assert pytest.approx(fe.mass, rel=1e-3) == 55.845

    # 2. Carbon-13 isotope: mass_number 13, exact mass ~13.003355 u [M]
    c13 = get_element("13C")
    assert c13.symbol == "C"
    assert c13.atomic_number == 6
    assert c13.mass_number == 13
    assert c13.formal_charge == 0
    assert c13.is_isotope is True
    assert pytest.approx(c13.mass, rel=1e-5) == 13.003355

    # 3. Zinc(II), Deuterium (2H alias), and Nitrogen-15
    zn = get_element("Zn2+")
    assert zn.symbol == "Zn"
    assert zn.atomic_number == 30
    assert zn.formal_charge == 2

    h2 = get_element("2H")
    assert h2.symbol == "H"
    assert h2.atomic_number == 1
    assert h2.mass_number == 2
    assert h2.is_isotope is True
    assert pytest.approx(h2.mass, rel=1e-5) == 2.014101778

    n15 = get_element("15N")
    assert n15.symbol == "N"
    assert n15.atomic_number == 7
    assert n15.mass_number == 15
    assert n15.is_isotope is True

    # 4. Invalid element must raise MendeleevInvariantError
    with pytest.raises(MendeleevInvariantError):
        get_element("InvalidElement999")


def test_qcschema_atomic_result_compliance() -> None:
    """Validate MolSSI QCSchema v1 AtomicResult compliance and backward-compatible accessors (Suggestion #46)."""
    # Water molecule in flat Bohr geometry
    symbols = ["O", "H", "H"]
    flat_bohr_geom = [
        0.0, 0.0, 0.0,
        0.0, 1.4304, 1.1071,
        0.0, -1.4304, 1.1071,
    ]
    flat_grad_bohr = [
        0.0, 0.0, -0.015,
        0.0, 0.012, 0.0075,
        0.0, -0.012, 0.0075,
    ]

    record = QCResultsRecord(
        driver="gradient",
        symbols=symbols,
        geometry=flat_bohr_geom,
        model={"method": "B3LYP", "basis": "def2-SVP"},
        return_result=flat_grad_bohr,
        properties={"return_energy": -76.425},
    )

    data = record.model_dump()
    # MolSSI QCSchema v1 envelope verification
    assert data["schema_name"] == "qcschema_output"
    assert data["schema_version"] == 1
    assert data["driver"] == "gradient"
    assert "molecule" in data
    assert data["molecule"]["symbols"] == ["O", "H", "H"]
    assert len(data["molecule"]["geometry"]) == 9
    assert data["return_result"] == flat_grad_bohr

    # Backward-compatible property accessors
    assert record.energy_hartree == -76.425
    assert record.gradient_bohr == flat_grad_bohr


def test_pes_point_coordinate_unit_enveloping() -> None:
    """Validate explicit coordinate dimensionality and round-trip unit conversion (Suggestion #47)."""
    coords_bohr = [0.0, 0.0, 1.8897261246]
    grad_bohr = [0.0, 0.0, -0.02]

    pt = PESPointRecord(
        point_id="pes_water_001",
        method_id="wb97x_d4",
        coordinates=coords_bohr,
        energy=-76.432,
        gradient=grad_bohr,
        units="bohr",
    )
    assert pt.units == "bohr"

    # Convert to Angstrom
    pt_ang = pt.to_angstrom()
    assert pt_ang.units == "angstrom"
    assert math.isclose(pt_ang.coordinates[2], coords_bohr[2] * BOHR_TO_ANGSTROM, rel_tol=1e-12)

    # Convert back to Bohr
    pt_bohr_rt = pt_ang.to_bohr()
    assert pt_bohr_rt.units == "bohr"
    assert math.isclose(pt_bohr_rt.coordinates[2], coords_bohr[2], rel_tol=1e-12)
    assert math.isclose(pt_bohr_rt.gradient[2], grad_bohr[2], rel_tol=1e-12)

    # Test MolecularTopology coordinate conversions
    topo = MolecularTopology(
        symbols=["O", "H", "H"],
        geometry=[0.0, 0.0, 0.0, 0.0, 1.43, 1.11, 0.0, -1.43, 1.11],
        units="bohr",
    )
    topo_ang = topo.to_angstrom()
    assert topo_ang.units == "angstrom"
    topo_bohr = topo_ang.to_bohr()
    assert topo_bohr.units == "bohr"
    for c1, c2 in zip(topo.geometry, topo_bohr.geometry, strict=True):
        assert math.isclose(c1, c2, rel_tol=1e-12)


def test_codata_constant_precision() -> None:
    """Validate full-precision CODATA 2018/2022 constants and CP-FTMW microwave benchmarks (Suggestion #48)."""
    assert UnitConversionConstants.HARTREE_TO_KCAL_MOL == 627.5094740631
    assert UnitConversionConstants.ROTATIONAL_INERTIA_CONVERSION == 505379.0084350172
    assert UnitConversionConstants.BOHR_TO_ANGSTROM == 0.529177210903
    assert math.isclose(
        UnitConversionConstants.ANGSTROM_TO_BOHR * UnitConversionConstants.BOHR_TO_ANGSTROM,
        1.0,
        rel_tol=1e-15,
    )

    # Physical verification: calculate B rotational constant of reference rigid rotor
    # Moment of inertia I_b in u * A^2
    i_b = 10.0  # u * Angstrom^2
    calculated_b_mhz = UnitConversionConstants.ROTATIONAL_INERTIA_CONVERSION / i_b

    # Exact physical calculation: h / (8 * pi^2 * I) * 1e-6
    h = UnitConversionConstants.PLANCK_CONSTANT
    u_kg = UnitConversionConstants.AMU_TO_KG
    ang_m = 1e-10
    exact_b_mhz = (h / (8.0 * (math.pi ** 2) * (i_b * u_kg * (ang_m ** 2)))) * 1e-6

    discrepancy_mhz = abs(calculated_b_mhz - exact_b_mhz)
    discrepancy_khz = discrepancy_mhz * 1000.0
    # Discrepancy must be sub-kHz (< 0.001 MHz) conforming to CP-FTMW spectroscopy requirements
    assert discrepancy_khz < 1.0, f"Discrepancy {discrepancy_khz:.4f} kHz exceeds 1 kHz limit"


def test_rfc8032_pure_ed25519_provenance_verification() -> None:
    """Validate RFC 8032 PureEd25519 direct raw message signing and provenance verification (Suggestions #49, #50)."""
    priv_key, pub_key = generate_ed25519_key_pair()

    # 1. PureEd25519 raw signing verification
    payload = {
        "engine": "ORCA",
        "method": "DLPNO-CCSD(T1)",
        "basis": "def2-QZVPP",
        "energy_hartree": -76.432891,
    }
    canonical_bytes = canonicalize_json(payload)
    sig_b64, pub_b64, fingerprint = sign_canonical_bytes(canonical_bytes, priv_key)

    # Verify internally with cochem_crypto
    assert verify_canonical_signature(canonical_bytes, sig_b64, pub_b64) is True

    # Verify externally with standard cryptography Ed25519PublicKey over raw bytes
    raw_sig = base64.urlsafe_b64decode(sig_b64 + "===")
    raw_pub = base64.urlsafe_b64decode(pub_b64 + "===")
    std_pub_key = Ed25519PublicKey.from_public_bytes(raw_pub)
    # This proves RFC 8032 PureEd25519: verifying raw canonical_bytes directly without pre-hashing
    std_pub_key.verify(raw_sig, canonical_bytes)

    # 2. QCSchemaProvenance asymmetric signature integration
    prov = QCSchemaProvenance(
        creator="ORCA",
        version="6.1",
        routine="sp",
        host="compute-node-042",
        platform="Linux-6.5.0-generic",
    )
    sig = prov.sign(priv_key)
    assert prov.signature == sig
    assert prov.public_key == pub_b64
    assert prov.fingerprint == fingerprint
    assert prov.verify() is True

    # 3. Tamper resistance verification
    prov.utc = "2026-09-04T00:00:00Z"
    assert prov.verify() is False
