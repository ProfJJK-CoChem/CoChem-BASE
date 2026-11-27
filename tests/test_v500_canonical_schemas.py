"""Unit tests for Pipeline 5.0.0 canonical shared DRAFT schemas (swarm-1126-8efd)."""
from __future__ import annotations

import copy
import json
import math
from typing import Any, Dict

import pytest

from cochem_base.schemas import (
    CANONICAL_SCHEMA_IDS,
    JOB_HANDOFF_SCHEMA_ID,
    PORTAL_DOSSIER_SCHEMA_ID,
    QUANTITIES_SCHEMA_ID,
    SCHEMA_STATUS,
    STATUS_UNTIL_FIRST_PRODUCER,
    JobHandoffV1,
    MissingProvenanceError,
    PortalDossierV11,
    QuantitiesContractV1,
    SilentDefaultRejectedError,
    UnitMismatchError,
    UnknownSchemaError,
    V500SchemaError,
    export_v500_json_schemas,
    list_legacy_handoff_schema_ids,
    load_committed_json_schema,
    load_legacy_handoff_inventory,
    validate_job_handoff_v1,
    validate_portal_dossier_v11,
    validate_quantities_v1,
    validate_v500_payload,
)
from cochem_base.schemas.v500_canonical import (
    GENERIC_FALSIFICATION_TRIGGER,
    VALID_LEGACY_DISPOSITIONS,
)

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64


def _valid_job_handoff_payload() -> Dict[str, Any]:
    return {
        "schema": JOB_HANDOFF_SCHEMA_ID,
        "job_id": "blind.s3.hof.gpu4pyscf.wb97xv.p1",
        "registry_sha256": SHA_A,
        "engine": "gpu4pyscf",
        "method": "wB97X-V",
        "basis": "def2-TZVPP",
        "created_at_utc": "2026-11-27T00:00:00Z",
        "quantities": [
            {
                "name": "electronic_energy",
                "subject": "HOF",
                "value": -175.5545602130257,
                "value_status": "COMPUTED",
                "unit": "hartree",
                "source_file": "hof_wb97xv.log",
                "source_sha256": SHA_B,
            },
            {
                "name": "anharmonic_zpe",
                "subject": "HOF",
                "value": None,
                "value_status": "PENDING",
                "unit": "kcal/mol",
                "source_file": "hof_vpt2_pending.json",
                "source_sha256": SHA_C,
                "notes": "Awaiting VPT2 continuation",
            },
        ],
    }


def _valid_quantities_payload() -> Dict[str, Any]:
    return {
        "schema": QUANTITIES_SCHEMA_ID,
        "job_id": "hcooh_dme_ccsd_cc_pvdz_opt_freq",
        "consumes": [
            {
                "name": "starting_geometry",
                "file": "geometry.xyz",
                "format": "xyz_angstrom",
                "unit": "angstrom",
                "n_atoms": 14,
                "formula": "C3H8O3",
                "charge": 0,
                "multiplicity": 1,
                "source_path": "publication/energetics/revdsd/parsed/isomer-00_revdsd.xyz",
                "source_sha256": SHA_A,
            }
        ],
        "produces": [
            {
                "name": "optimized_geometry_xyz",
                "file": "hcooh_dme_ccsd_cc_pvdz_opt.xyz",
                "format": "xyz_angstrom",
                "unit": "angstrom",
                "required": True,
            },
            {
                "name": "structured_ccsd_result",
                "file": "hcooh_dme_ccsd_cc_pvdz_result.json",
                "format": "json",
                "required": True,
                "gates": {
                    "max_gradient_eh_bohr_le": 1e-5,
                    "n_imaginary_modes_eq": 0,
                    "n_internal_modes_eq": 36,
                },
            },
        ],
    }


def _valid_portal_dossier_payload() -> Dict[str, Any]:
    return {
        "schema_version": PORTAL_DOSSIER_SCHEMA_ID,
        "domain_prefix": "sys",
        "job_id": "sys.ecosystem.namespace_dualtree_ghost_cleanup.20261126",
        "attempt": 1,
        "title": "CoChem Ecosystem Namespace & Registry Consolidation",
        "summary_one_line": "Consolidate cochem_base __init__.py and spyfy/orb/dock registry contracts",
        "symptom": "PEP-420 namespace shadowing and spycfit vs spyfy registry mismatch",
        "context_summary": "CoChem-BASE lacked __init__.py and rejected spyfy while listing phantom dock.",
        "consequence_class": "REVERSIBLE",
        "decision_category": "system_infra",
        "complexity_tier": 7,
        "task_category_weights": {"COD-ARCH": 0.6, "AUD-SEC": 0.4},
        "matrix_sha256": SHA_A,
        "council_seats": [
            {
                "seat_id": "seat_anthropic",
                "provider": "anthropic",
                "model_id": "claude-opus-5-5",
                "effort": "high",
                "stage": "stage1_and_stage3_red_team",
                "omission_rate_pct": 0.0,
                "degraded_fallback": False,
            }
        ],
        "degraded_seat": False,
        "stage3_outcome": "MUTATED",
        "stage3_evidence_hash": SHA_B,
        "research_evidence_sha256": SHA_C,
        "research_degraded": False,
        "bootstrap_tag": False,
        "falsification_trigger": "Fail if clean wheel import of cochem_base fails without PYTHONPATH.",
        "rollback_plan": "Revert stacked PR commit using pre-sys-1126-a3d4-base rollback tag.",
        "evidence_refs": [
            {
                "label": "Core 9-repo SRS audit",
                "url_or_path": "scratch/srs_audit_core_9repos.json",
                "source_sha256": SHA_D,
                "entailment_tag": "FULL_TEXT_VERIFIED",
                "excerpt": "Verified PEP-420 collision and module_registry spyfy mismatch.",
            }
        ],
        "options": [
            {
                "key": "a",
                "label": "Consolidate BASE __init__.py and canonicalize spyfy/orb/dock",
                "is_recommended": True,
                "consequence_class": "REVERSIBLE",
                "compute_cost_summary": "$0 compute spend",
                "net_effect_summary": "Establishes single owner for cochem_base and clean registry.",
                "pros": ["Eliminates namespace shadowing"],
                "cons": ["Requires staged migration in downstream SPYFY"],
                "risks": ["Legacy spycfit callers see DeprecationWarning"],
                "reviewer_critique": "Verify clean wheel install without PYTHONPATH.",
                "response_to_critique": "Added isolated venv wheel test gate.",
                "round2_refinement_changes": "Added explicit re-export parity and orb NotImplementedError.",
                "jev_r1": 0.9133,
                "jev_r2": 0.9409,
                "falsification_trigger": "Any consumer fails import after BASE wheel installs.",
                "decision_patch": {"add_init_py": True, "canonical_spyfy": True},
            },
            {
                "key": "b",
                "label": "Hold consolidation and keep PEP-420 namespace layout",
                "is_recommended": False,
                "consequence_class": "REVERSIBLE",
                "compute_cost_summary": "$0 spend",
                "net_effect_summary": "Leaves known P0 namespace shadowing unresolved.",
                "pros": ["Zero immediate diff"],
                "cons": ["Shadowing persists"],
                "risks": ["Silent module override by install order"],
                "reviewer_critique": "Leaves P0 fault active.",
                "response_to_critique": "Retained as safe hold option.",
                "round2_refinement_changes": "None.",
                "jev_r1": 0.9133,
                "jev_r2": 0.9409,
                "falsification_trigger": "Owner approves Option A execution.",
                "decision_patch": {"action": "hold"},
            },
        ],
    }


def test_draft_status_and_committed_json_schemas() -> None:
    assert SCHEMA_STATUS == "DRAFT"
    assert STATUS_UNTIL_FIRST_PRODUCER == "DRAFT"
    assert JobHandoffV1.SCHEMA_STATUS == "DRAFT"
    assert QuantitiesContractV1.SCHEMA_STATUS == "DRAFT"
    assert PortalDossierV11.SCHEMA_STATUS == "DRAFT"

    exported = export_v500_json_schemas()
    assert set(exported.keys()) == set(CANONICAL_SCHEMA_IDS)
    for schema_id in CANONICAL_SCHEMA_IDS:
        committed = load_committed_json_schema(schema_id)
        assert committed["x-cochem-status"] == "DRAFT"
        assert committed["x-status-until-first-producer"] == "DRAFT"
        assert committed["x-cochem-schema-id"] == schema_id
        assert committed == exported[schema_id]


def test_legacy_handoff_inventory_has_at_least_20_verified_entries() -> None:
    inventory = load_legacy_handoff_inventory()
    assert inventory["schema_status"] == "DRAFT"
    assert inventory["status_until_first_producer"] == "DRAFT"
    ids = list_legacy_handoff_schema_ids()
    assert len(ids) >= 20
    assert len(set(ids)) == len(ids)
    for entry in inventory["entries"]:
        assert entry["disposition"] in VALID_LEGACY_DISPOSITIONS
        assert entry["canonical_target"] in CANONICAL_SCHEMA_IDS
        assert entry["producer_repo"]
        assert entry["observed_locations"]


def test_roundtrip_job_handoff_preserves_units_missing_vs_null_and_provenance() -> None:
    payload = _valid_job_handoff_payload()
    model = validate_v500_payload(
        payload,
        expected_units={"electronic_energy": "hartree", "anharmonic_zpe": "kcal/mol"},
    )
    assert isinstance(model, JobHandoffV1)
    assert model.schema_status == "DRAFT"
    assert model.registry_sha256 == SHA_A

    dumped = model.model_dump(mode="json", by_alias=True, exclude_unset=True)
    # Explicit null is preserved, while omitted optional keys (e.g. uncertainty) are not fabricated.
    q0, q1 = dumped["quantities"]
    assert q0["unit"] == "hartree"
    assert q0["source_sha256"] == SHA_B
    assert "uncertainty" not in q0
    assert "notes" not in q0
    assert "value" in q1 and q1["value"] is None
    assert q1["value_status"] == "PENDING"
    assert q1["unit"] == "kcal/mol"
    assert q1["source_sha256"] == SHA_C

    reparsed = validate_job_handoff_v1(json.loads(json.dumps(dumped)))
    assert reparsed == model


def test_roundtrip_quantities_and_portal_dossier_preserve_provenance() -> None:
    q_payload = _valid_quantities_payload()
    q_model = validate_v500_payload(
        q_payload,
        expected_units={"starting_geometry": "angstrom", "optimized_geometry_xyz": "angstrom"},
    )
    assert isinstance(q_model, QuantitiesContractV1)
    q_dumped = q_model.model_dump(mode="json", by_alias=True, exclude_unset=True)
    assert q_dumped["consumes"][0]["source_sha256"] == SHA_A
    assert q_dumped["consumes"][0]["unit"] == "angstrom"
    assert q_dumped["produces"][0]["required"] is True
    assert "unit" not in q_dumped["produces"][1]
    assert validate_quantities_v1(q_dumped) == q_model

    d_payload = _valid_portal_dossier_payload()
    d_model = validate_v500_payload(d_payload)
    assert isinstance(d_model, PortalDossierV11)
    d_dumped = d_model.model_dump(mode="json", exclude_unset=True)
    assert d_dumped["matrix_sha256"] == SHA_A
    assert d_dumped["evidence_refs"][0]["source_sha256"] == SHA_D
    assert "tried_summary" not in d_dumped
    assert validate_portal_dossier_v11(d_dumped) == d_model


def test_negative_unknown_schema_rejected_with_redacted_reason() -> None:
    secret_sentinel = "SENSITIVE_STUDENT_PAYLOAD_TOKEN_999"
    with pytest.raises(UnknownSchemaError) as exc_info:
        validate_v500_payload({"schema": "cochem.unregistered-handoff/99", "secret": secret_sentinel})
    assert exc_info.value.error_code == "UNKNOWN_SCHEMA"
    assert secret_sentinel not in str(exc_info.value)

    with pytest.raises(UnknownSchemaError):
        validate_v500_payload({"job_id": "missing_schema_field"})


def test_negative_lossy_unit_mismatch_and_noncanonical_unit_rejected() -> None:
    # Lossy unit mismatch against expected unit (kcal/mol vs hartree -> no silent conversion!)
    payload = _valid_job_handoff_payload()
    with pytest.raises(UnitMismatchError, match="silent unit conversion is forbidden"):
        validate_job_handoff_v1(payload, expected_units={"electronic_energy": "kcal/mol"})

    # Non-canonical unit string rejected
    bad_unit = copy.deepcopy(payload)
    bad_unit["quantities"][0]["unit"] = "Ha"
    with pytest.raises(UnitMismatchError):
        validate_job_handoff_v1(bad_unit)

    # Quantities contract unit mismatch rejected
    q_payload = _valid_quantities_payload()
    with pytest.raises(UnitMismatchError):
        validate_quantities_v1(q_payload, expected_units={"starting_geometry": "bohr"})


def test_negative_missing_provenance_rejected() -> None:
    # Missing registry_sha256 in job handoff
    p1 = _valid_job_handoff_payload()
    del p1["registry_sha256"]
    with pytest.raises(MissingProvenanceError):
        validate_job_handoff_v1(p1)

    # Malformed source_sha256 in quantity
    p2 = _valid_job_handoff_payload()
    p2["quantities"][0]["source_sha256"] = "not-a-sha256"
    with pytest.raises(MissingProvenanceError):
        validate_job_handoff_v1(p2)

    # Missing source_sha256 in consumes
    q1 = _valid_quantities_payload()
    del q1["consumes"][0]["source_sha256"]
    with pytest.raises(MissingProvenanceError):
        validate_quantities_v1(q1)

    # Missing evidence_refs provenance in portal dossier
    d1 = _valid_portal_dossier_payload()
    del d1["evidence_refs"][0]["source_sha256"]
    with pytest.raises(MissingProvenanceError):
        validate_portal_dossier_v11(d1)

    # Missing matrix_sha256 in portal dossier
    d2 = _valid_portal_dossier_payload()
    del d2["matrix_sha256"]
    with pytest.raises(MissingProvenanceError):
        validate_portal_dossier_v11(d2)


def test_negative_silent_defaults_missing_vs_null_and_strict_bounds_rejected() -> None:
    # Omitted 'unit' key -> SilentDefaultRejectedError
    p_no_unit = _valid_job_handoff_payload()
    del p_no_unit["quantities"][0]["unit"]
    with pytest.raises(SilentDefaultRejectedError):
        validate_job_handoff_v1(p_no_unit)

    # Omitted 'value' key (distinct from explicit null) -> SilentDefaultRejectedError
    p_no_val = _valid_job_handoff_payload()
    del p_no_val["quantities"][0]["value"]
    with pytest.raises(SilentDefaultRejectedError):
        validate_job_handoff_v1(p_no_val)

    # Explicit null with value_status='COMPUTED' rejected (null requires PENDING)
    p_bad_null = _valid_job_handoff_payload()
    p_bad_null["quantities"][0]["value"] = None
    with pytest.raises(V500SchemaError, match="NULL_VALUE_REQUIRES_PENDING_STATUS"):
        validate_job_handoff_v1(p_bad_null)

    # NaN / bool values rejected
    p_nan = _valid_job_handoff_payload()
    p_nan["quantities"][0]["value"] = math.nan
    with pytest.raises(V500SchemaError):
        validate_job_handoff_v1(p_nan)

    p_bool = _valid_job_handoff_payload()
    p_bool["quantities"][0]["value"] = True
    with pytest.raises(V500SchemaError):
        validate_job_handoff_v1(p_bool)

    # Omitted required boolean flag in QUANTITIES.json -> SilentDefaultRejectedError
    q_no_req = _valid_quantities_payload()
    del q_no_req["produces"][0]["required"]
    with pytest.raises(SilentDefaultRejectedError):
        validate_quantities_v1(q_no_req)

    # Omitted consequence_class in Portal dossier -> SilentDefaultRejectedError
    d_no_cc = _valid_portal_dossier_payload()
    del d_no_cc["consequence_class"]
    with pytest.raises(SilentDefaultRejectedError):
        validate_portal_dossier_v11(d_no_cc)

    # Generic falsification trigger rejected
    d_gen = _valid_portal_dossier_payload()
    d_gen["falsification_trigger"] = GENERIC_FALSIFICATION_TRIGGER
    with pytest.raises(V500SchemaError, match="GENERIC_FALSIFICATION_TRIGGER"):
        validate_portal_dossier_v11(d_gen)

    # Extra undeclared key rejected (extra='forbid')
    p_extra = _valid_job_handoff_payload()
    p_extra["undeclared_extra"] = 123
    with pytest.raises(V500SchemaError):
        validate_job_handoff_v1(p_extra)
