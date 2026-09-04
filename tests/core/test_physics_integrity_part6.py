"""Zero-Mock Physics Invariants, Radii, Licensing & Asymmetric Signatures Test Suite (Part 6).

Validates Suggestions #51, #52, #54, #55, #56, #59, and #60.
Adheres strictly to Method Matrix v4 and Zero-Mock Anti-Spoofing Protocol v2.
Real physical execution: authentic dynamic Mendeleev masses/radii, RFC 8032 PureEd25519,
W3C Linked Data Proof did:key signatures, and deterministic UUIDv5 content hashing.
"""

from __future__ import annotations

import copy

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from pydantic import ValidationError

import cochem_base.cochem_core_registry_schema as cochem_core_registry_schema
from cochem_base.cochem_core_registry_schema import get_registry_atomic_mass
from cochem_base.core.cochem_crypto import (
    did_key_to_public_key,
    public_key_to_did_key,
    sign_report_payload,
    verify_report_payload,
)
from cochem_base.core.exceptions import IsotopeStabilityError, RadiusNotFoundError
from cochem_base.core.glossary import CalculationFidelity
from cochem_base.core.metadata import get_covalent_radius, get_isotopic_mass
from cochem_base.core.models import CalculationJobPayload, PESPointRecord, QCResultsRecord
from cochem_base.core_engine.cochem_core_pes_store import QCSchemaMethodRecord, QCSchemaProvenance


def test_mendeleev_isotopic_nuclear_mass_resolution() -> None:
    """Validate dynamic IUPAC/CIAAW isotopic nuclear mass resolution and unphysical fallback removal (Suggestion #51)."""
    # 1. Carbon-14: physical nuclear mass ~14.003242 u [M], strictly not terrestrial average 12.011 u
    c14_mass = get_isotopic_mass("C", 14)
    assert pytest.approx(c14_mass, rel=1e-6) == 14.003241988
    assert abs(c14_mass - 12.011) > 1.9

    # 2. Deuterium (2H): nuclear mass ~2.014102 u [M]
    h2_mass = get_isotopic_mass("H", 2)
    assert pytest.approx(h2_mass, rel=1e-6) == 2.014101778

    # 3. Nitrogen-15: ~15.000109 u [M]
    n15_mass = get_isotopic_mass("N", 15)
    assert pytest.approx(n15_mass, rel=1e-6) == 15.000108899

    # 4. Chlorine-37: ~36.965903 u [M]
    cl37_mass = get_isotopic_mass("Cl", 37)
    assert pytest.approx(cl37_mass, rel=1e-6) == 36.965902602

    # 5. Non-existent isotope must raise IsotopeStabilityError
    with pytest.raises(IsotopeStabilityError):
        get_isotopic_mass("C", 999)

    with pytest.raises(IsotopeStabilityError):
        get_isotopic_mass("H", 10)


def test_hierarchical_empirical_radii_lookup() -> None:
    """Validate hierarchical Pyykkö -> Cordero -> vdW empirical radii resolution (Suggestion #52)."""
    # 1. Argon (Noble Gas): empirical vdW radius ~1.88 Å (or Pyykkö covalent radius ~0.96 Å), strictly not 0.77 Å
    ar_radius = get_covalent_radius("Ar")
    assert abs(ar_radius - 0.77) > 0.15
    assert ar_radius > 0.9

    # 2. Carbon (sp3 single bond covalent radius ~0.75 - 0.77 Å)
    c_radius = get_covalent_radius("C")
    assert 0.70 <= c_radius <= 0.80

    # 3. Xenon: heavy noble gas, empirical radius > 1.3 Å
    xe_radius = get_covalent_radius("Xe")
    assert xe_radius > 1.3

    # 4. Unresolvable / invalid element must raise RadiusNotFoundError
    with pytest.raises(RadiusNotFoundError):
        get_covalent_radius("InvalidElement")


def test_spdx_data_licensing_validation() -> None:
    """Validate machine-readable SPDX data usage licensing enforcement (Suggestion #54)."""
    # 1. Official open-science licenses accepted
    prov_cc4 = QCSchemaProvenance(license="CC-BY-4.0")
    assert prov_cc4.license == "CC-BY-4.0"

    prov_cc0 = QCSchemaProvenance(license="CC0-1.0")
    assert prov_cc0.license == "CC0-1.0"

    prov_mit = QCSchemaProvenance(license="MIT")
    assert prov_mit.license == "MIT"

    # 2. Check QCResultsRecord and QCSchemaMethodRecord license fields
    rec = QCResultsRecord(license="Apache-2.0")
    assert rec.license == "Apache-2.0"

    meth = QCSchemaMethodRecord(method="B3LYP", basis="def2-SVP", license="BSD-3-Clause")
    assert meth.license == "BSD-3-Clause"

    # 3. Invalid or unrecognized license string must raise ValidationError
    with pytest.raises(ValidationError):
        QCSchemaProvenance(license="Proprietary-Unpublished-Invalid")

    with pytest.raises(ValidationError):
        QCResultsRecord(license="Proprietary-Unpublished-Invalid")


def test_dynamic_registry_schema_isotopic_masses() -> None:
    """Validate dynamic SQLite Mendeleev registry mass resolution and removal of static ISOTOPIC_MASSES (Suggestion #55)."""
    # 1. Dynamic query for Argon-40 and Chlorine-37
    ar40_mass = get_registry_atomic_mass("Ar", 40)
    assert pytest.approx(ar40_mass, rel=1e-6) == 39.962383124

    cl37_mass = get_registry_atomic_mass("Cl", 37)
    assert pytest.approx(cl37_mass, rel=1e-6) == 36.965902602

    # Standard terrestrial average weight query (mass_number=None)
    c_mass = get_registry_atomic_mass("C")
    assert pytest.approx(c_mass, rel=1e-3) == 12.011

    # Non-existent isotope query must raise IsotopeStabilityError
    with pytest.raises(IsotopeStabilityError):
        get_registry_atomic_mass("Ar", 999)

    # 2. Static dictionary eradication verification
    assert not hasattr(cochem_core_registry_schema, "ISOTOPIC_MASSES")


def test_w3c_linked_data_proof_pure_ed25519_did_key() -> None:
    """Validate W3C Linked Data Proof envelopes and offline did:key multicodec resolution (Suggestion #56)."""
    # 1. Generate real Ed25519 key pair
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Verify did:key encoding and decoding
    did_key = public_key_to_did_key(public_key)
    assert did_key.startswith("did:key:z")
    recovered_pub = did_key_to_public_key(did_key)
    assert recovered_pub.public_bytes_raw() == public_key.public_bytes_raw()

    # 2. Sign computational payload
    payload = {
        "job_id": "job_opt_20260904_001",
        "method": "wB97M-V",
        "basis": "def2-TZVP",
        "energy_hartree": -76.42512345,
        "converged": True,
    }

    signed_doc = sign_report_payload(payload, private_key)
    assert "proof" in signed_doc
    proof = signed_doc["proof"]
    assert proof["type"] == "Ed25519Signature2020"
    assert proof["verificationMethod"] == did_key
    assert proof["proofPurpose"] == "assertionMethod"
    assert "proofValue" in proof
    assert "created" in proof

    # 3. Verify valid signature
    assert verify_report_payload(signed_doc) is True

    # 4. Tampering test: perturb energy by 1 micro-Hartree
    tampered_doc = copy.deepcopy(signed_doc)
    tampered_doc["energy_hartree"] = -76.42512445
    assert verify_report_payload(tampered_doc) is False


def test_deterministic_uuid5_pes_point_id() -> None:
    """Validate deterministic UUIDv5 content-addressable PES point identifier generation (Suggestion #59)."""
    geom1 = [0.0, 0.0, 0.0, 0.0, 0.0, 1.128, 2.0, 0.0, 0.0]
    symbols = ["C", "O", "He"]
    method = "DLPNO-CCSD(T)"
    basis = "cc-pVTZ"

    # Instantiate two distinct PESPointRecord objects with identical specifications
    pt1 = PESPointRecord(
        coordinates=geom1,
        symbols=symbols,
        method=method,
        basis=basis,
        energy=-113.25,
    )
    pt2 = PESPointRecord(
        coordinates=geom1,
        symbols=symbols,
        method=method,
        basis=basis,
        energy=-113.25,
    )
    assert pt1.point_id == pt2.point_id
    assert len(pt1.point_id) == 36  # Standard UUID string representation

    # Perturb one coordinate by 0.001 Angstrom
    geom_perturbed = list(geom1)
    geom_perturbed[2] += 0.001
    pt_perturbed = PESPointRecord(
        coordinates=geom_perturbed,
        symbols=symbols,
        method=method,
        basis=basis,
        energy=-113.25,
    )
    assert pt_perturbed.point_id != pt1.point_id


def test_calculation_fidelity_canonical_tiers() -> None:
    """Validate Method Matrix v4 canonical composite fidelity tier definitions (Suggestion #60)."""
    # 1. Verify official canonical composite tiers in CalculationFidelity enum
    assert CalculationFidelity.JUNCHS_F12 == "junChS-F12"
    assert CalculationFidelity.T3_3H == "T3-3h"
    assert CalculationFidelity.R2 == "R2"
    assert CalculationFidelity.CHS == "ChS"

    # 2. Instantiate CalculationJobPayload with string representations of canonical tiers
    job1 = CalculationJobPayload(fidelity="junChS-F12")
    assert job1.fidelity == CalculationFidelity.JUNCHS_F12

    job2 = CalculationJobPayload(fidelity="T3-3h")
    assert job2.fidelity == CalculationFidelity.T3_3H

    job3 = CalculationJobPayload(fidelity="R2")
    assert job3.fidelity == CalculationFidelity.R2

    # 3. Semiempirical and standard wavefunction tiers
    job4 = CalculationJobPayload(fidelity="XTB2")
    assert job4.fidelity == CalculationFidelity.XTB2

    job5 = CalculationJobPayload(fidelity="DLPNO_CCSD_T")
    assert job5.fidelity == CalculationFidelity.DLPNO_CCSD_T
