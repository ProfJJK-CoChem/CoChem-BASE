"""Canonical Pipeline 5.0.0 Shared DRAFT Schema Validators.

Implements fail-closed Pydantic v2 validators for the three cross-ecosystem
Pipeline 5.0.0 exchange contracts hosted in CoChem-BASE per Portal rulings
``swarm-1126-8efd`` and ``sys-1126-a3d4``:

1. ``cochem-job-handoff/1`` (``HANDOFF.json``, OWN-117 quantity & provenance handoff)
2. ``cochem-quantities/1`` (``QUANTITIES.json``, OWN-117 consumes/produces contract)
3. ``cochem-portal-dossier/1.1`` (Unified 6-Stage CoChem-Portal decision dossier)

All three schemas carry ``SCHEMA_STATUS = "DRAFT"`` (``status_until_first_producer``
is ``"DRAFT"``) until first-producer conformance is certified across active repos.
Silent unit conversion and silent provenance defaults are strictly forbidden.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Literal, Mapping, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

SCHEMA_STATUS: Literal["DRAFT"] = "DRAFT"
STATUS_UNTIL_FIRST_PRODUCER: Literal["DRAFT"] = "DRAFT"

JOB_HANDOFF_SCHEMA_ID: Literal["cochem-job-handoff/1"] = "cochem-job-handoff/1"
QUANTITIES_SCHEMA_ID: Literal["cochem-quantities/1"] = "cochem-quantities/1"
PORTAL_DOSSIER_SCHEMA_ID: Literal["cochem-portal-dossier/1.1"] = "cochem-portal-dossier/1.1"

CANONICAL_SCHEMA_IDS: Tuple[str, ...] = (
    JOB_HANDOFF_SCHEMA_ID,
    QUANTITIES_SCHEMA_ID,
    PORTAL_DOSSIER_SCHEMA_ID,
)

# Canonical physical units accepted without silent conversion.
CANONICAL_PHYSICAL_UNITS: frozenset[str] = frozenset(
    {
        "hartree",
        "Eh",
        "kcal/mol",
        "kJ/mol",
        "eV",
        "cm^-1",
        "MHz",
        "GHz",
        "kHz",
        "Hz",
        "angstrom",
        "bohr",
        "degree",
        "radian",
        "Debye",
        "e*bohr",
        "hartree/bohr",
        "hartree/bohr^2",
        "amu",
        "amu*angstrom^2",
        "K",
        "s",
        "dimensionless",
        "count",
    }
)

VALID_DECISION_CATEGORIES: frozenset[str] = frozenset(
    {
        "compchem_calc_pivot",
        "workflow_pivot",
        "governance_own",
        "system_infra",
        "routing_matrix",
        "wiki_knowledge",
    }
)

VALID_CONSEQUENCE_CLASSES: frozenset[str] = frozenset(
    {
        "REVERSIBLE",
        "COSTS_MONEY",
        "IRREVERSIBLE",
        "TOUCHES_STUDENT_DATA",
    }
)

VALID_STAGE3_OUTCOMES: frozenset[str] = frozenset(
    {"MUTATED", "CRITIQUE_OR_AFFIRM", "SKIPPED"}
)

VALID_LEGACY_DISPOSITIONS: frozenset[str] = frozenset(
    {"verified_adapter", "quarantine", "retire_with_evidence"}
)

GENERIC_FALSIFICATION_TRIGGER = (
    "Specify concrete observable or test failure that disproves this ruling."
)

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_HEX64_ANYCASE_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_SINGLE_LETTER_RE = re.compile(r"^[a-z]$")
_SCHEMAS_DIR = Path(__file__).resolve().parent
_INVENTORY_PATH = _SCHEMAS_DIR / "legacy_handoff_inventory.json"
_JSON_SCHEMAS_DIR = _SCHEMAS_DIR / "v500_json_schemas"


class V500SchemaError(ValueError):
    """Base fail-closed validation error carrying a redacted machine-readable code."""

    def __init__(self, error_code: str, redacted_reason: str) -> None:
        self.error_code = error_code
        self.redacted_reason = redacted_reason
        super().__init__(f"[{error_code}] {redacted_reason}")


class UnknownSchemaError(V500SchemaError):
    """Raised when a payload declares an unknown or missing schema identifier."""


class UnitMismatchError(V500SchemaError):
    """Raised when a physical quantity omits a unit, uses an invalid unit, or mismatches an expected unit."""


class MissingProvenanceError(V500SchemaError):
    """Raised when mandatory SHA-256 or source provenance fields are absent or malformed."""


class SilentDefaultRejectedError(V500SchemaError):
    """Raised when a payload attempts to rely on omitted mandatory fields or implicit defaults."""


def _is_finite_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(float(value))


def _reraise_v500_or_wrap(
    exc: ValidationError,
    *,
    fallback_code: str,
    fallback_msg: str,
) -> None:
    for err in exc.errors():
        ctx = err.get("ctx")
        if isinstance(ctx, dict) and isinstance(ctx.get("error"), V500SchemaError):
            raise ctx["error"] from exc
    raise V500SchemaError(
        fallback_code,
        f"{fallback_msg} ({len(exc.errors())} error(s))",
    ) from exc


def _require_mapping(payload: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise V500SchemaError(
            "INVALID_PAYLOAD_TYPE",
            f"{context} requires a JSON object mapping, received {type(payload).__name__}",
        )
    return payload


def _require_hex64(value: Any, *, field_name: str, lowercase_only: bool = True) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MissingProvenanceError(
            "MISSING_PROVENANCE",
            f"Required SHA-256 provenance field '{field_name}' is missing or empty",
        )
    pattern = _HEX64_RE if lowercase_only else _HEX64_ANYCASE_RE
    if not pattern.fullmatch(value):
        raise MissingProvenanceError(
            "INVALID_PROVENANCE_SHA256",
            f"Provenance field '{field_name}' must be a 64-character hex SHA-256 digest",
        )
    return value


def _require_canonical_unit(unit: Any, *, field_name: str) -> str:
    if not isinstance(unit, str) or not unit.strip():
        raise SilentDefaultRejectedError(
            "MISSING_UNIT",
            f"Explicit physical unit is mandatory for '{field_name}'; silent unit defaults are forbidden",
        )
    if unit not in CANONICAL_PHYSICAL_UNITS:
        raise UnitMismatchError(
            "UNSUPPORTED_OR_NONCANONICAL_UNIT",
            f"Unit {unit!r} for '{field_name}' is not in the canonical unit table; silent unit conversion is forbidden",
        )
    return unit


# =====================================================================
# 1. cochem-job-handoff/1 (DRAFT)
# =====================================================================


class HandoffQuantityEntry(BaseModel):
    """Single physical quantity with explicit unit and SHA-256 provenance."""

    SCHEMA_STATUS: ClassVar[Literal["DRAFT"]] = SCHEMA_STATUS
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    value: Optional[Union[float, int]]
    value_status: Literal["MEASURED", "COMPUTED", "PENDING"] = "COMPUTED"
    unit: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    source_sha256: str = Field(min_length=64, max_length=64)
    uncertainty: Optional[float] = None
    notes: Optional[str] = None

    @field_validator("unit")
    @classmethod
    def _validate_unit(cls, v: str) -> str:
        return _require_canonical_unit(v, field_name="quantity.unit")

    @field_validator("source_sha256")
    @classmethod
    def _validate_sha(cls, v: str) -> str:
        return _require_hex64(v, field_name="quantity.source_sha256")

    @field_validator("value", mode="before")
    @classmethod
    def _validate_value(cls, v: Any) -> Optional[Union[float, int]]:
        if v is None:
            return None
        if not _is_finite_number(v):
            raise V500SchemaError(
                "NONFINITE_OR_BOOL_VALUE",
                "Quantity 'value' must be a finite numeric scalar or explicit null when PENDING",
            )
        return v

    @field_validator("uncertainty", mode="before")
    @classmethod
    def _validate_uncertainty(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        if not _is_finite_number(v) or float(v) < 0.0:
            raise V500SchemaError(
                "INVALID_UNCERTAINTY",
                "Quantity 'uncertainty' must be a non-negative finite number or null",
            )
        return float(v)

    @model_validator(mode="after")
    def _check_null_vs_status(self) -> "HandoffQuantityEntry":
        if self.value is None and self.value_status != "PENDING":
            raise V500SchemaError(
                "NULL_VALUE_REQUIRES_PENDING_STATUS",
                f"Quantity {self.name!r} has null value but value_status={self.value_status!r} (must be 'PENDING')",
            )
        if self.value is not None and self.value_status == "PENDING":
            raise V500SchemaError(
                "PENDING_STATUS_REQUIRES_NULL_VALUE",
                f"Quantity {self.name!r} declares value_status='PENDING' but supplied a numeric value",
            )
        return self


class JobHandoffV1(BaseModel):
    """Canonical Pipeline 5.0.0 ``cochem-job-handoff/1`` (HANDOFF.json) DRAFT contract."""

    SCHEMA_STATUS: ClassVar[Literal["DRAFT"]] = SCHEMA_STATUS
    STATUS_UNTIL_FIRST_PRODUCER: ClassVar[Literal["DRAFT"]] = STATUS_UNTIL_FIRST_PRODUCER
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_id: Literal["cochem-job-handoff/1"] = Field(alias="schema")
    schema_status: Literal["DRAFT"] = SCHEMA_STATUS
    job_id: str = Field(min_length=1)
    registry_sha256: str = Field(min_length=64, max_length=64)
    quantities: List[HandoffQuantityEntry] = Field(min_length=1)
    engine: Optional[str] = None
    method: Optional[str] = None
    basis: Optional[str] = None
    created_at_utc: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("registry_sha256")
    @classmethod
    def _validate_registry_sha(cls, v: str) -> str:
        return _require_hex64(v, field_name="registry_sha256")


def validate_job_handoff_v1(
    payload: Mapping[str, Any],
    *,
    expected_units: Optional[Mapping[str, str]] = None,
) -> JobHandoffV1:
    """Strictly validate a ``cochem-job-handoff/1`` payload with zero silent defaults."""
    raw = _require_mapping(payload, context="cochem-job-handoff/1")
    declared = raw.get("schema")
    if declared != JOB_HANDOFF_SCHEMA_ID:
        raise UnknownSchemaError(
            "UNKNOWN_SCHEMA",
            f"Expected schema {JOB_HANDOFF_SCHEMA_ID!r}, got {declared!r}",
        )
    if "registry_sha256" not in raw:
        raise MissingProvenanceError(
            "MISSING_PROVENANCE",
            "Field 'registry_sha256' is required in cochem-job-handoff/1; silent provenance defaults are forbidden",
        )
    quantities = raw.get("quantities")
    if not isinstance(quantities, list) or not quantities:
        raise V500SchemaError(
            "MISSING_QUANTITIES",
            "cochem-job-handoff/1 requires a non-empty 'quantities' list",
        )
    for idx, entry in enumerate(quantities):
        em = _require_mapping(entry, context=f"quantities[{idx}]")
        if "value" not in em:
            raise SilentDefaultRejectedError(
                "MISSING_REQUIRED_VALUE_KEY",
                f"quantities[{idx}] omitted required key 'value' (missing key is distinct from explicit null)",
            )
        if "unit" not in em:
            raise SilentDefaultRejectedError(
                "MISSING_UNIT",
                f"quantities[{idx}] omitted mandatory 'unit'; silent unit defaults are forbidden",
            )
        if "source_file" not in em or "source_sha256" not in em:
            raise MissingProvenanceError(
                "MISSING_PROVENANCE",
                f"quantities[{idx}] requires explicit 'source_file' and 'source_sha256' provenance",
            )
        _require_canonical_unit(em["unit"], field_name=f"quantities[{idx}].unit")
        _require_hex64(em["source_sha256"], field_name=f"quantities[{idx}].source_sha256")

    try:
        model = JobHandoffV1.model_validate(dict(raw))
    except V500SchemaError:
        raise
    except ValidationError as exc:
        _reraise_v500_or_wrap(
            exc,
            fallback_code="JOB_HANDOFF_VALIDATION_FAILED",
            fallback_msg="cochem-job-handoff/1 schema validation failed",
        )
        raise  # pragma: no cover

    if expected_units:
        for item in model.quantities:
            if item.name in expected_units:
                want = _require_canonical_unit(expected_units[item.name], field_name=f"expected_units[{item.name}]")
                if item.unit != want:
                    raise UnitMismatchError(
                        "UNIT_MISMATCH",
                        f"Quantity {item.name!r} declared unit {item.unit!r}, expected {want!r}; "
                        "silent unit conversion is forbidden",
                    )
    return model


# =====================================================================
# 2. cochem-quantities/1 (DRAFT)
# =====================================================================


class QuantityConsumeEntry(BaseModel):
    """Declared upstream artifact consumed by a Pipeline 5.0.0 job."""

    SCHEMA_STATUS: ClassVar[Literal["DRAFT"]] = SCHEMA_STATUS
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    file: str = Field(min_length=1)
    format: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    source_sha256: str = Field(min_length=64, max_length=64)
    unit: Optional[str] = None
    n_atoms: Optional[int] = Field(default=None, ge=1)
    formula: Optional[str] = None
    charge: Optional[int] = None
    multiplicity: Optional[int] = Field(default=None, ge=1)

    @field_validator("source_sha256")
    @classmethod
    def _validate_sha(cls, v: str) -> str:
        return _require_hex64(v, field_name="consumes.source_sha256")

    @field_validator("unit")
    @classmethod
    def _validate_optional_unit(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return _require_canonical_unit(v, field_name="consumes.unit")


class QuantityProduceEntry(BaseModel):
    """Declared downstream artifact or observable produced by a Pipeline 5.0.0 job."""

    SCHEMA_STATUS: ClassVar[Literal["DRAFT"]] = SCHEMA_STATUS
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    file: str = Field(min_length=1)
    format: str = Field(min_length=1)
    required: bool
    unit: Optional[str] = None
    gates: Optional[Dict[str, Union[int, float]]] = None

    @field_validator("unit")
    @classmethod
    def _validate_optional_unit(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return _require_canonical_unit(v, field_name="produces.unit")

    @field_validator("gates", mode="before")
    @classmethod
    def _validate_gates(cls, v: Any) -> Optional[Dict[str, Union[int, float]]]:
        if v is None:
            return None
        if not isinstance(v, dict):
            raise V500SchemaError("INVALID_GATE_BOUND", "produces.gates must be an object mapping")
        for gk, gv in v.items():
            if not _is_finite_number(gv):
                raise V500SchemaError(
                    "INVALID_GATE_BOUND",
                    f"produces.gates[{gk!r}] must be a finite numeric bound",
                )
        return v


class QuantitiesContractV1(BaseModel):
    """Canonical Pipeline 5.0.0 ``cochem-quantities/1`` (QUANTITIES.json) DRAFT contract."""

    SCHEMA_STATUS: ClassVar[Literal["DRAFT"]] = SCHEMA_STATUS
    STATUS_UNTIL_FIRST_PRODUCER: ClassVar[Literal["DRAFT"]] = STATUS_UNTIL_FIRST_PRODUCER
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_id: Literal["cochem-quantities/1"] = Field(alias="schema")
    schema_status: Literal["DRAFT"] = SCHEMA_STATUS
    job_id: str = Field(min_length=1)
    consumes: List[QuantityConsumeEntry]
    produces: List[QuantityProduceEntry] = Field(min_length=1)


def validate_quantities_v1(
    payload: Mapping[str, Any],
    *,
    expected_units: Optional[Mapping[str, str]] = None,
) -> QuantitiesContractV1:
    """Strictly validate a ``cochem-quantities/1`` payload with zero silent defaults."""
    raw = _require_mapping(payload, context="cochem-quantities/1")
    declared = raw.get("schema")
    if declared != QUANTITIES_SCHEMA_ID:
        raise UnknownSchemaError(
            "UNKNOWN_SCHEMA",
            f"Expected schema {QUANTITIES_SCHEMA_ID!r}, got {declared!r}",
        )
    if "consumes" not in raw or not isinstance(raw["consumes"], list):
        raise SilentDefaultRejectedError(
            "MISSING_CONSUMES",
            "cochem-quantities/1 requires explicit 'consumes' list (may be empty only if explicitly [])",
        )
    if "produces" not in raw or not isinstance(raw["produces"], list) or not raw["produces"]:
        raise SilentDefaultRejectedError(
            "MISSING_PRODUCES",
            "cochem-quantities/1 requires a non-empty explicit 'produces' list",
        )
    for idx, entry in enumerate(raw["consumes"]):
        cm = _require_mapping(entry, context=f"consumes[{idx}]")
        if "source_path" not in cm or "source_sha256" not in cm:
            raise MissingProvenanceError(
                "MISSING_PROVENANCE",
                f"consumes[{idx}] requires explicit 'source_path' and 'source_sha256' provenance",
            )
        _require_hex64(cm["source_sha256"], field_name=f"consumes[{idx}].source_sha256")
        if "unit" in cm and cm["unit"] is not None:
            _require_canonical_unit(cm["unit"], field_name=f"consumes[{idx}].unit")
    for idx, entry in enumerate(raw["produces"]):
        pm = _require_mapping(entry, context=f"produces[{idx}]")
        if "required" not in pm or not isinstance(pm["required"], bool):
            raise SilentDefaultRejectedError(
                "MISSING_REQUIRED_FLAG",
                f"produces[{idx}] requires explicit boolean 'required'; silent defaults are forbidden",
            )
        if "unit" in pm and pm["unit"] is not None:
            _require_canonical_unit(pm["unit"], field_name=f"produces[{idx}].unit")

    try:
        model = QuantitiesContractV1.model_validate(dict(raw))
    except V500SchemaError:
        raise
    except ValidationError as exc:
        _reraise_v500_or_wrap(
            exc,
            fallback_code="QUANTITIES_VALIDATION_FAILED",
            fallback_msg="cochem-quantities/1 schema validation failed",
        )
        raise  # pragma: no cover

    if expected_units:
        for item in (*model.consumes, *model.produces):
            if item.name in expected_units:
                want = _require_canonical_unit(expected_units[item.name], field_name=f"expected_units[{item.name}]")
                if item.unit != want:
                    raise UnitMismatchError(
                        "UNIT_MISMATCH",
                        f"Contract entry {item.name!r} declared unit {item.unit!r}, expected {want!r}; "
                        "silent unit conversion is forbidden",
                    )
    return model


# =====================================================================
# 3. cochem-portal-dossier/1.1 (DRAFT)
# =====================================================================


class CouncilSeatV11(BaseModel):
    """Frontier Council seat record for cochem-portal-dossier/1.1."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seat_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    effort: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    omission_rate_pct: Optional[float] = None
    degraded_fallback: bool = False


class EvidenceRefV11(BaseModel):
    """Provenance-pinned research or code evidence reference."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1)
    url_or_path: str = Field(min_length=1)
    source_sha256: str = Field(min_length=64, max_length=64)
    entailment_tag: Literal["FULL_TEXT_VERIFIED", "ABSTRACT_ONLY_VERIFIED"]
    excerpt: str = Field(min_length=1)

    @field_validator("source_sha256")
    @classmethod
    def _validate_sha(cls, v: str) -> str:
        return _require_hex64(v, field_name="evidence_refs.source_sha256", lowercase_only=False)


class ImpactScopeRowV11(BaseModel):
    """Blast-radius and scope impact table row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope_item: str = Field(min_length=1)
    before: str = Field(min_length=1)
    after: str = Field(min_length=1)
    blast_radius: str = Field(min_length=1)
    owner_action: str = Field(min_length=1)


class ParameterDiffV11(BaseModel):
    """Round-1 to Round-2 parameter diff entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1)
    r1_value: Any
    r2_value: Any
    changed: bool


class DossierOptionV11(BaseModel):
    """Lettered decision option in cochem-portal-dossier/1.1."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1, max_length=1)
    label: str = Field(min_length=1)
    is_recommended: bool
    consequence_class: Literal[
        "REVERSIBLE",
        "COSTS_MONEY",
        "IRREVERSIBLE",
        "TOUCHES_STUDENT_DATA",
    ]
    compute_cost_summary: str = Field(min_length=1)
    net_effect_summary: str = Field(min_length=1)
    pros: List[str] = Field(min_length=1)
    cons: List[str] = Field(min_length=1)
    risks: List[str] = Field(min_length=1)
    reviewer_critique: str = Field(min_length=1)
    response_to_critique: str = Field(min_length=1)
    round2_refinement_changes: str = Field(min_length=1)
    jev_r1: Optional[float] = None
    jev_r2: Optional[float] = None
    falsification_trigger: str = Field(min_length=1)
    decision_patch: Dict[str, Any]

    @field_validator("key")
    @classmethod
    def _validate_key(cls, v: str) -> str:
        if not _SINGLE_LETTER_RE.fullmatch(v):
            raise V500SchemaError(
                "INVALID_OPTION_KEY",
                "Option key must be a single lowercase ASCII letter (a..z)",
            )
        return v

    @field_validator("falsification_trigger")
    @classmethod
    def _validate_trigger(cls, v: str) -> str:
        if v.strip() == GENERIC_FALSIFICATION_TRIGGER:
            raise V500SchemaError(
                "GENERIC_FALSIFICATION_TRIGGER",
                "Option falsification_trigger must be concrete and non-generic",
            )
        return v


class PortalDossierV11(BaseModel):
    """Canonical Pipeline 5.0.0 ``cochem-portal-dossier/1.1`` DRAFT validator."""

    SCHEMA_STATUS: ClassVar[Literal["DRAFT"]] = SCHEMA_STATUS
    STATUS_UNTIL_FIRST_PRODUCER: ClassVar[Literal["DRAFT"]] = STATUS_UNTIL_FIRST_PRODUCER
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["cochem-portal-dossier/1.1"]
    schema_status: Literal["DRAFT"] = SCHEMA_STATUS
    domain_prefix: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    attempt: int = Field(ge=1)
    title: str = Field(min_length=1)
    summary_one_line: str = Field(min_length=1)
    symptom: str = Field(min_length=1)
    tried_summary: Optional[str] = None
    context_summary: str = Field(min_length=1)
    consequence_class: Literal[
        "REVERSIBLE",
        "COSTS_MONEY",
        "IRREVERSIBLE",
        "TOUCHES_STUDENT_DATA",
    ]
    decision_category: Literal[
        "compchem_calc_pivot",
        "workflow_pivot",
        "governance_own",
        "system_infra",
        "routing_matrix",
        "wiki_knowledge",
    ]
    complexity_tier: int = Field(ge=1, le=10)
    task_category_weights: Dict[str, float] = Field(min_length=1)
    matrix_sha256: str = Field(min_length=64, max_length=64)
    council_seats: List[CouncilSeatV11] = Field(min_length=1)
    degraded_seat: bool
    stage3_outcome: Literal["MUTATED", "CRITIQUE_OR_AFFIRM", "SKIPPED"]
    stage3_evidence_hash: str = Field(min_length=64, max_length=64)
    research_evidence_sha256: str = Field(min_length=64, max_length=64)
    research_degraded: bool
    bootstrap_tag: bool
    falsification_trigger: str = Field(min_length=1)
    rollback_plan: str = Field(min_length=1)
    evidence_refs: List[EvidenceRefV11] = Field(min_length=1)
    options: List[DossierOptionV11] = Field(min_length=2)
    created_at: Optional[str] = None
    deadline_at: Optional[str] = None
    jev_version: Optional[str] = None
    jev_tier: Optional[str] = None
    jev_threshold: Optional[float] = None
    jev_r1: Optional[float] = None
    jev_r2: Optional[float] = None
    summit_consensus_vote: Optional[str] = None
    summit_summary: Optional[str] = None
    red_team_critique: Optional[str] = None
    adjudicated_response: Optional[str] = None
    r1_to_r2_param_diffs: Optional[List[ParameterDiffV11]] = None
    prose_only_no_byte_diff: Optional[bool] = None
    impact_scope_rows: Optional[List[ImpactScopeRowV11]] = None

    @field_validator("matrix_sha256", "stage3_evidence_hash", "research_evidence_sha256")
    @classmethod
    def _validate_sha_fields(cls, v: str, info: Any) -> str:
        return _require_hex64(v, field_name=str(info.field_name), lowercase_only=False)

    @field_validator("falsification_trigger")
    @classmethod
    def _validate_dossier_trigger(cls, v: str) -> str:
        if v.strip() == GENERIC_FALSIFICATION_TRIGGER:
            raise V500SchemaError(
                "GENERIC_FALSIFICATION_TRIGGER",
                "Dossier falsification_trigger must be concrete and non-generic",
            )
        return v

    @model_validator(mode="after")
    def _validate_options_and_weights(self) -> "PortalDossierV11":
        keys = [opt.key for opt in self.options]
        if len(set(keys)) != len(keys):
            raise V500SchemaError(
                "DUPLICATE_OPTION_KEYS",
                "Portal dossier option keys must be unique",
            )
        if not any(opt.is_recommended for opt in self.options):
            raise V500SchemaError(
                "MISSING_RECOMMENDED_OPTION",
                "Portal dossier must mark at least one recommended option",
            )
        total_weight = sum(self.task_category_weights.values())
        if not math.isfinite(total_weight) or abs(total_weight - 1.0) > 1e-4:
            raise V500SchemaError(
                "INVALID_TASK_WEIGHTS",
                "task_category_weights must sum to 1.0 within 1e-4",
            )
        return self


def validate_portal_dossier_v11(payload: Mapping[str, Any]) -> PortalDossierV11:
    """Strictly validate a ``cochem-portal-dossier/1.1`` payload with zero silent defaults."""
    raw = _require_mapping(payload, context="cochem-portal-dossier/1.1")
    declared = raw.get("schema_version")
    if declared != PORTAL_DOSSIER_SCHEMA_ID:
        raise UnknownSchemaError(
            "UNKNOWN_SCHEMA",
            f"Expected schema_version {PORTAL_DOSSIER_SCHEMA_ID!r}, got {declared!r}",
        )
    for prov_field in ("matrix_sha256", "stage3_evidence_hash", "research_evidence_sha256"):
        if prov_field not in raw:
            raise MissingProvenanceError(
                "MISSING_PROVENANCE",
                f"Required provenance digest '{prov_field}' missing from cochem-portal-dossier/1.1",
            )
        _require_hex64(raw[prov_field], field_name=prov_field, lowercase_only=False)
    if "evidence_refs" not in raw or not isinstance(raw["evidence_refs"], list) or not raw["evidence_refs"]:
        raise MissingProvenanceError(
            "MISSING_PROVENANCE",
            "cochem-portal-dossier/1.1 requires non-empty 'evidence_refs' with explicit source_sha256",
        )
    for idx, ref in enumerate(raw["evidence_refs"]):
        rm = _require_mapping(ref, context=f"evidence_refs[{idx}]")
        if "source_sha256" not in rm:
            raise MissingProvenanceError(
                "MISSING_PROVENANCE",
                f"evidence_refs[{idx}] missing mandatory 'source_sha256' provenance",
            )
        _require_hex64(rm["source_sha256"], field_name=f"evidence_refs[{idx}].source_sha256", lowercase_only=False)
    if "consequence_class" not in raw:
        raise SilentDefaultRejectedError(
            "MISSING_CONSEQUENCE_CLASS",
            "Field 'consequence_class' is mandatory; silent defaults are forbidden",
        )

    try:
        return PortalDossierV11.model_validate(dict(raw))
    except V500SchemaError:
        raise
    except ValidationError as exc:
        _reraise_v500_or_wrap(
            exc,
            fallback_code="PORTAL_DOSSIER_VALIDATION_FAILED",
            fallback_msg="cochem-portal-dossier/1.1 schema validation failed",
        )
        raise  # pragma: no cover


# =====================================================================
# Universal Dispatcher & Committed Inventory / JSON Schema Helpers
# =====================================================================


def validate_v500_payload(
    payload: Mapping[str, Any],
    *,
    expected_units: Optional[Mapping[str, str]] = None,
) -> Union[JobHandoffV1, QuantitiesContractV1, PortalDossierV11]:
    """Dispatch validation by explicit schema identifier; reject unknown schemas fail-closed."""
    raw = _require_mapping(payload, context="v500 payload")
    schema_id = raw.get("schema") or raw.get("schema_version")
    if schema_id == JOB_HANDOFF_SCHEMA_ID:
        return validate_job_handoff_v1(raw, expected_units=expected_units)
    if schema_id == QUANTITIES_SCHEMA_ID:
        return validate_quantities_v1(raw, expected_units=expected_units)
    if schema_id == PORTAL_DOSSIER_SCHEMA_ID:
        return validate_portal_dossier_v11(raw)
    digest = hashlib.sha256(
        json.dumps(sorted(str(k) for k in raw.keys())).encode("utf-8")
    ).hexdigest()[:16]
    raise UnknownSchemaError(
        "UNKNOWN_SCHEMA",
        f"Unrecognized or missing canonical schema identifier {schema_id!r} "
        f"(key_fingerprint={digest}); payload rejected without processing",
    )


def load_legacy_handoff_inventory() -> Dict[str, Any]:
    """Load the committed inventory of legacy ecosystem HANDOFF schema IDs."""
    data = json.loads(_INVENTORY_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise V500SchemaError("INVALID_INVENTORY", "Legacy handoff inventory JSON is malformed")
    return data


def list_legacy_handoff_schema_ids() -> Tuple[str, ...]:
    """Return all inventoried legacy HANDOFF schema IDs across the CoChem ecosystem."""
    inv = load_legacy_handoff_inventory()
    return tuple(str(entry["schema_id"]) for entry in inv["entries"])


def _canonicalize_schema_node(node: Any) -> Any:
    if isinstance(node, dict):
        out: Dict[str, Any] = {}
        for k in sorted(node.keys()):
            v = _canonicalize_schema_node(node[k])
            if k == "anyOf" and isinstance(v, list):
                v = sorted(v, key=lambda item: json.dumps(item, sort_keys=True))
            out[k] = v
        return out
    if isinstance(node, list):
        return [_canonicalize_schema_node(item) for item in node]
    return node


def export_v500_json_schemas() -> Dict[str, Dict[str, Any]]:
    """Return versioned JSON Schema definitions annotated with DRAFT status."""
    models = {
        JOB_HANDOFF_SCHEMA_ID: JobHandoffV1,
        QUANTITIES_SCHEMA_ID: QuantitiesContractV1,
        PORTAL_DOSSIER_SCHEMA_ID: PortalDossierV11,
    }
    exported: Dict[str, Dict[str, Any]] = {}
    for schema_id, model_cls in models.items():
        schema_doc = model_cls.model_json_schema(by_alias=True)
        schema_doc["$id"] = f"urn:cochem:schema:{schema_id}"
        schema_doc["x-cochem-schema-id"] = schema_id
        schema_doc["x-cochem-status"] = SCHEMA_STATUS
        schema_doc["x-status-until-first-producer"] = STATUS_UNTIL_FIRST_PRODUCER
        exported[schema_id] = _canonicalize_schema_node(
            json.loads(json.dumps(schema_doc, sort_keys=True))
        )
    return exported


def load_committed_json_schema(schema_id: str) -> Dict[str, Any]:
    """Load a committed versioned JSON Schema artifact from ``v500_json_schemas/``."""
    filenames = {
        JOB_HANDOFF_SCHEMA_ID: "cochem-job-handoff.v1.schema.json",
        QUANTITIES_SCHEMA_ID: "cochem-quantities.v1.schema.json",
        PORTAL_DOSSIER_SCHEMA_ID: "cochem-portal-dossier.v1.1.schema.json",
    }
    if schema_id not in filenames:
        raise UnknownSchemaError("UNKNOWN_SCHEMA", f"No committed JSON schema for {schema_id!r}")
    target = _JSON_SCHEMAS_DIR / filenames[schema_id]
    return json.loads(target.read_text(encoding="utf-8"))


__all__ = [
    "CANONICAL_PHYSICAL_UNITS",
    "CANONICAL_SCHEMA_IDS",
    "CouncilSeatV11",
    "DossierOptionV11",
    "EvidenceRefV11",
    "HandoffQuantityEntry",
    "ImpactScopeRowV11",
    "JOB_HANDOFF_SCHEMA_ID",
    "JobHandoffV1",
    "MissingProvenanceError",
    "PORTAL_DOSSIER_SCHEMA_ID",
    "ParameterDiffV11",
    "PortalDossierV11",
    "QUANTITIES_SCHEMA_ID",
    "QuantitiesContractV1",
    "QuantityConsumeEntry",
    "QuantityProduceEntry",
    "SCHEMA_STATUS",
    "STATUS_UNTIL_FIRST_PRODUCER",
    "SilentDefaultRejectedError",
    "UnitMismatchError",
    "UnknownSchemaError",
    "V500SchemaError",
    "VALID_CONSEQUENCE_CLASSES",
    "VALID_DECISION_CATEGORIES",
    "VALID_LEGACY_DISPOSITIONS",
    "VALID_STAGE3_OUTCOMES",
    "export_v500_json_schemas",
    "list_legacy_handoff_schema_ids",
    "load_committed_json_schema",
    "load_legacy_handoff_inventory",
    "validate_job_handoff_v1",
    "validate_portal_dossier_v11",
    "validate_quantities_v1",
    "validate_v500_payload",
]
