#!/usr/bin/env python3
"""Cryptographic L1-L3 SHA-256 FactLedger Builder & Fail-Closed Verifier.

CHEM 312 Module 4 (Tennessee Tech University) — Builds and verifies `FactLedger.json`
and `FactLedger.md` across the three provenance tiers:
  - L1 (Primary / Raw Evidence): raw QM outputs, XYZ geometries, `handoff.json`,
    Pickett `.var`/`.int`/`.cat` decks, `bsse_counterpoise.json`,
    `gvpt2_shard_manifest.json`, and raw experimental ATR spectra.
  - L2 (Derived Analytics & Tables): `stationary_table.csv`, KK-ATR summaries,
    vdW titration difference JSON/CSV, Fermi deperturbation JSON, comparison
    JSONs, and SPCAT catalog summaries.
  - L3 (Milestone & Claim Synthesis): CHEM 312 M1-M4 milestone ledger and
    scientific claims bound strictly to verified L1/L2 SHA-256 digests.

Security & Integrity Invariants:
  - Every L1/L2 artifact is hashed on disk (SHA-256 + byte size).
  - Embedded `files_sha256` inside `handoff.json` is cross-checked against
    on-disk sibling files; any mismatch raises `FactLedgerIntegrityError`.
  - Missing milestones are explicitly marked `"PENDING"` (never fabricated).
  - Unhashed claims or tampered files fail closed with `FactLedgerIntegrityError`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
FALLBACK_COURSE_IDS: tuple[str, ...] = ("CHEM311", "CHEM312", "CHEM490", "CHEM410", "CHEM411")
_MILESTONE_NUM_RE = re.compile(r"(?:^|[_\-/])(?:mod|m)(\d+)(?:$|[_\-./])", re.IGNORECASE)
_MILESTONE_DIR_RE = re.compile(r"^(?:mod|m)(\d+)(?:$|[_\-])", re.IGNORECASE)
_MILESTONE_PREFIX_RE = re.compile(r"^(M\d+)", re.IGNORECASE)

DEFAULT_MILESTONES: tuple[tuple[str, str], ...] = (
    ("M1_conformers", "M1 Conformer Ensemble & Handoff"),
    ("M2_kk_atr", "M2 Kramers-Kronig ATR-FTIR & Harmonic Comparison"),
    ("M3_nci_gvpt2_fermi", "M3 1:1 NCI/BSSE, 6-Shard GVPT2 & Fermi Deperturbation"),
    ("M4_spcat_8_18ghz", "M4 SPCAT 8-18 GHz Rotational Prediction & Dossier"),
)

EXTRA_MILESTONE_TITLES: dict[str, str] = {
    "M2_geom_comparison": "M2 Geometry Comparison Handoff",
    "M3_nci_bsse": "M3 1:1 NCI Dimer & Counterpoise BSSE Handoff",
    "M3_gvpt2": "M3 6-Shard Barone GVPT2 Anharmonic Handoff",
    "M4_rxn_profile": "M4 AIMNet2 + PySCF/PCM Reaction Profile Handoff",
}

PARENT_MILESTONE_CHILDREN: dict[str, tuple[str, ...]] = {
    "M2_kk_atr": ("M2_geom_comparison",),
    "M3_nci_gvpt2_fermi": ("M3_nci_bsse", "M3_gvpt2"),
}


def _get_allowed_course_ids() -> tuple[str, ...]:
    """Return allowed course IDs from CoChem-CURE via course_loader when available, else fallback."""
    try:
        from cochem_base.course_loader import get_allowed_course_ids as _loader_allowed_course_ids
    except ImportError:
        _loader_allowed_course_ids = None
    if _loader_allowed_course_ids is not None:
        try:
            loaded = tuple(str(cid).strip() for cid in _loader_allowed_course_ids() if str(cid).strip())
            if loaded:
                return loaded
        except Exception:
            pass
    try:
        from cochem_cure import provider as _cure_provider
    except ImportError:
        return FALLBACK_COURSE_IDS
    if (
        getattr(_cure_provider, "SCHEMA_VERSION", None) == "cochem.course-provider/1"
        and callable(getattr(_cure_provider, "get_allowed_course_ids", None))
    ):
        try:
            loaded = tuple(str(cid).strip() for cid in _cure_provider.get_allowed_course_ids() if str(cid).strip())
            if loaded:
                return loaded
        except Exception:
            pass
    return FALLBACK_COURSE_IDS


def _validate_course_id(value: str) -> str:
    """Validate and normalize a course identifier (fail-closed ArgumentTypeError on invalid ID)."""
    raw = str(value or "").strip()
    if not raw:
        raise argparse.ArgumentTypeError("course_id must not be empty.")
    try:
        from cochem_cure import provider as _cure_provider
    except ImportError:
        _cure_provider = None
    if (
        _cure_provider is not None
        and getattr(_cure_provider, "SCHEMA_VERSION", None) == "cochem.course-provider/1"
        and callable(getattr(_cure_provider, "validate_course_id", None))
    ):
        try:
            return str(_cure_provider.validate_course_id(raw))
        except (ValueError, KeyError) as exc:
            raise argparse.ArgumentTypeError(str(exc)) from exc

    allowed = _get_allowed_course_ids()
    normalized = raw.upper().replace(" ", "").replace("-", "").replace("_", "")
    if normalized == "CHEM312L" and "CHEM312" in allowed:
        return "CHEM312"
    for cid in allowed:
        cid_norm = cid.upper().replace(" ", "").replace("-", "").replace("_", "")
        if raw.upper() == cid.upper() or normalized == cid_norm:
            return cid
    raise argparse.ArgumentTypeError(
        f"invalid course_id {value!r} (choose from {', '.join(allowed)})"
    )


def _format_cure_milestones(raw_milestones: Sequence[Mapping[str, Any]]) -> tuple[tuple[str, str], ...]:
    """Convert structured CoChem-CURE milestone dictionaries into (key, title) tuples."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in raw_milestones:
        if not isinstance(item, Mapping):
            continue
        mid = str(item.get("milestone_id") or item.get("id") or item.get("code") or "").strip()
        if not mid or mid in seen:
            continue
        seen.add(mid)
        base_title = str(item.get("title") or item.get("name") or mid).strip()
        weeks = str(item.get("weeks") or "").strip()
        if weeks and weeks not in base_title:
            title = f"{mid} ({weeks}): {base_title}"
        elif not base_title.startswith(mid):
            title = f"{mid}: {base_title}"
        else:
            title = base_title
        out.append((mid, title))
    return tuple(out)


def get_milestone_catalog_for_course(course_id: str) -> tuple[tuple[tuple[str, str], ...], str]:
    """Resolve the (milestones, source) tuple for ``course_id``.

    Preserves exact ``DEFAULT_MILESTONES`` for ``CHEM312``; dynamically loads
    ``CoChem-CURE`` milestones via ``cochem_base.course_loader.get_cure_milestones``
    (or ``cochem_cure.provider``) for all other courses, with a clean generic
    course-aware fallback when standalone.
    """
    cid = str(course_id or "CHEM312").strip() or "CHEM312"
    if cid.upper() == "CHEM312":
        return DEFAULT_MILESTONES, "chem312_default"

    raw_milestones: Sequence[Mapping[str, Any]] | None = None
    try:
        from cochem_base.course_loader import get_cure_milestones as _loader_get_milestones

        raw_milestones = _loader_get_milestones(cid)
    except Exception:
        raw_milestones = None

    if raw_milestones is None:
        try:
            from cochem_cure import provider as _cure_provider

            if (
                getattr(_cure_provider, "SCHEMA_VERSION", None) == "cochem.course-provider/1"
                and callable(getattr(_cure_provider, "get_course_milestones", None))
            ):
                raw_milestones = _cure_provider.get_course_milestones(cid)
        except Exception:
            raw_milestones = None

    if raw_milestones:
        formatted = _format_cure_milestones(raw_milestones)
        if formatted:
            return formatted, "cochem_cure"

    if cid.upper() == "CHEM311":
        return (
            ("CHEM311_M0", "CHEM311 Milestone 0: Local Workspace Setup & Verification"),
            ("CHEM311_M1", "CHEM311 Milestone 1: Constitutional Isomers"),
            ("CHEM311_M2", "CHEM311 Milestone 2: Stereoisomers & Inertial Defect"),
            ("CHEM311_M3", "CHEM311 Milestone 3: Conformational Analysis"),
            ("CHEM311_M4", "CHEM311 Milestone 4: Bonding, Hybridization & Charges"),
            ("CHEM311_M5", "CHEM311 Milestone 5: Vibrational Frequencies & SPCAT Spectrum"),
        ), "standalone_fallback"

    return (
        (f"{cid}_M1", f"{cid} Milestone 1: Setup & Primary Computations"),
        (f"{cid}_M2", f"{cid} Milestone 2: Analysis & Spectroscopy"),
        (f"{cid}_M3", f"{cid} Milestone 3: Advanced Modeling & Verification"),
        (f"{cid}_M4", f"{cid} Milestone 4: Dossier & Cryptographic Handoff"),
    ), "standalone_fallback"


def _zip_has_handoff_manifest(path: Path) -> bool:
    """Return True only when ``path`` is a valid ZIP archive containing ``handoff.json``."""
    if not path.is_file():
        return False
    try:
        with zipfile.ZipFile(path, "r") as zf:
            return "handoff.json" in zf.namelist()
    except (zipfile.BadZipFile, OSError):
        return False


def _map_milestone_for_course(
    path: Path,
    classified_milestone: str,
    course_id: str,
    catalog_keys: Sequence[str],
    rel_path: str | Path | None = None,
) -> str:
    """Map an artifact's classified milestone onto the target course's milestone catalog."""
    cid_upper = course_id.upper()
    if cid_upper == "CHEM312":
        return classified_milestone
    name_lower = path.name.lower()
    is_zip = name_lower.endswith(".zip")
    has_verified_zip_manifest = is_zip and _zip_has_handoff_manifest(path)
    # Unmanifested plain ZIP archives never verify a course milestone (even inside mN/modN folders).
    if is_zip and not has_verified_zip_manifest:
        return "UNMANIFESTED_ZIP"
    if classified_milestone in catalog_keys:
        return classified_milestone
    key_lookup = {k.upper(): k for k in catalog_keys}

    def _lookup_num(num: str) -> str | None:
        for cand in (f"M{num}", f"{cid_upper}_M{num}"):
            if cand in key_lookup:
                return key_lookup[cand]
        return None

    # 1. Honor explicit modN / mN filename conventions (e.g., mod1_results.json, mod5_isotopologues.json)
    m_name = _MILESTONE_NUM_RE.search(path.name)
    if m_name:
        hit = _lookup_num(m_name.group(1))
        if hit is not None:
            return hit

    # 2. Honor anchored modN / mN directory prefixes within base_dir (innermost parent outward,
    #    e.g., m1_labs/titration_diprotic.json -> M1, m3_kinetics/out/dft_stage.json -> M3, mod3/crest.out -> M3;
    #    never matches arbitrary substrings like archive-m3-backups).
    if rel_path is not None:
        parent_parts = tuple(p for p in Path(rel_path).parts[:-1] if p not in ("", "."))
    else:
        parent_parts = (path.parent.name,) if path.parent.name else ()
    for part in reversed(parent_parts):
        m_dir = _MILESTONE_DIR_RE.match(part)
        if m_dir:
            hit = _lookup_num(m_dir.group(1))
            if hit is not None:
                return hit

    # 3. Course-semantic fallback for verified handoff/provenance dossiers, CHEM410 kinetics, & CHEM311 M5
    parent_lower = {p.lower() for p in parent_parts}
    if is_zip:
        is_provenance_bundle = has_verified_zip_manifest and (
            bool(parent_lower & {"handoff_out", "handoff", "received", "dossier", "capstone"})
            or "factledger" in name_lower
            or "dossier" in name_lower
            or "capstone" in name_lower
        )
    else:
        is_provenance_bundle = (
            name_lower in ("handoff.json", "factledger.json", "factledger.md")
            or "factledger" in name_lower
            or "dossier" in name_lower
            or "capstone" in name_lower
        )
    if is_provenance_bundle and cid_upper in ("CHEM410", "CHEM411", "CHEM490"):
        hit_m4 = _lookup_num("4")
        if hit_m4 is not None:
            return hit_m4
    if cid_upper == "CHEM311" and (
        classified_milestone == "M4_spcat_8_18ghz"
        or (is_provenance_bundle and classified_milestone in ("M4_spcat_8_18ghz", "M1_conformers"))
    ):
        hit_m5 = _lookup_num("5")
        if hit_m5 is not None:
            return hit_m5

    if cid_upper == "CHEM410" and classified_milestone == "M4_rxn_profile":
        hit_m3 = _lookup_num("3")
        if hit_m3 is not None:
            return hit_m3

    # 4. Map classified M1..M4 prefix onto the course's matching milestone key if present
    m_pref = _MILESTONE_PREFIX_RE.match(classified_milestone)
    if m_pref:
        prefix = m_pref.group(1).upper()
        for cand in (prefix, f"{cid_upper}_{prefix}"):
            if cand in key_lookup:
                return key_lookup[cand]
    return classified_milestone


class FactLedgerIntegrityError(ValueError):
    """Raised when a FactLedger artifact or claim fails cryptographic SHA-256 verification."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_json_sha256(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _classify_handoff_zip(path: Path) -> tuple[str, str]:
    """Read-only inspection of a student handoff `.zip` archive to classify its milestone."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names_lower = [n.lower() for n in zf.namelist()]
            handoff_data: Mapping[str, Any] = {}
            if "handoff.json" in zf.namelist():
                raw = json.loads(zf.read("handoff.json").decode("utf-8"))
                if isinstance(raw, Mapping):
                    handoff_data = raw
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError, OSError):
        return "L1", "M1_conformers"

    workflow_type = str(handoff_data.get("workflow_type", "")).strip().lower()
    metadata = handoff_data.get("metadata") if isinstance(handoff_data.get("metadata"), Mapping) else {}
    dossier_kind = str(metadata.get("dossier_kind", "")).strip().lower()
    has_spcat_member = any(
        "spcat" in n or n.endswith((".cat", ".var", ".int")) for n in names_lower
    )

    if workflow_type == "conformer":
        return "L1", "M1_conformers"
    if workflow_type == "nci_dimer":
        return "L1", "M3_nci_bsse"
    if workflow_type == "vpt2_anharmonic":
        return "L1", "M3_gvpt2"
    if workflow_type == "rxn_profile":
        return "L1", "M4_rxn_profile"
    if workflow_type == "geom_comparison":
        if has_spcat_member or "spcat" in dossier_kind or "rotational_constants_mhz" in metadata:
            return "L1", "M4_spcat_8_18ghz"
        return "L1", "M2_geom_comparison"

    if has_spcat_member:
        return "L1", "M4_spcat_8_18ghz"
    if any("bsse_counterpoise" in n or "vdw_titration" in n for n in names_lower):
        return "L1", "M3_nci_bsse"
    if any("gvpt2" in n or "fermi" in n for n in names_lower):
        return "L1", "M3_gvpt2"
    if any("rxn_profile" in n or "neb_path" in n or "irc_path" in n or "ts_polished" in n for n in names_lower):
        return "L1", "M4_rxn_profile"
    if any("kk_atr" in n or "kramers" in n for n in names_lower):
        return "L2", "M2_kk_atr"
    return "L1", "M1_conformers"


def classify_artifact_tier(path: Path) -> tuple[str, str]:
    """Classify an upstream artifact into (level, milestone_key)."""
    name = path.name.lower()
    if name.endswith(".zip") and path.is_file():
        return _classify_handoff_zip(path)
    if name in ("handoff.json", "input.xyz", "refined.xyz", "crest_conformers.xyz", "ranking.json"):
        return "L1", "M1_conformers"
    if name.endswith((".cat", ".var", ".int", ".parquet")) or "spcat" in name:
        tier = "L2" if (name.endswith(".json") or "summary" in name) else "L1"
        return tier, "M4_spcat_8_18ghz"
    if "kk_atr" in name or "kramers" in name:
        return "L2", "M2_kk_atr"
    if "stationary_table" in name or "comparison" in name:
        return "L2", "M2_kk_atr"
    if "bsse" in name or "vdw_titration" in name or "fermi" in name or "gvpt2" in name:
        tier = "L1" if ("bsse_counterpoise" in name or "shard_" in name) else "L2"
        return tier, "M3_nci_gvpt2_fermi"
    if name.endswith((".xyz", ".out", ".log", ".hess")):
        return "L1", "M1_conformers"
    if name.endswith((".csv", ".json", ".md")):
        return "L2", "M2_kk_atr"
    return "L1", "M1_conformers"


def _verify_embedded_handoff_zip(zip_path: Path) -> list[str]:
    """Cross-verify `files_sha256` inside an embedded `handoff.json` within a `.zip` archive."""
    try:
        zf_ctx = zipfile.ZipFile(zip_path, "r")
    except zipfile.BadZipFile as exc:
        raise FactLedgerIntegrityError(f"Invalid or corrupted ZIP archive {zip_path.name}: {exc}") from exc

    with zf_ctx as zf:
        members = set(zf.namelist())
        if "handoff.json" not in members:
            return []
        try:
            data = json.loads(zf.read("handoff.json").decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise FactLedgerIntegrityError(
                f"Malformed embedded handoff.json in {zip_path.name}: {exc}"
            ) from exc
        if not isinstance(data, Mapping):
            raise FactLedgerIntegrityError(f"Embedded handoff.json in {zip_path.name} must be a JSON object.")
        files_sha = data.get("files_sha256")
        if files_sha is None:
            return []
        if not isinstance(files_sha, Mapping):
            raise FactLedgerIntegrityError(
                f"Invalid files_sha256 mapping in embedded handoff.json of {zip_path.name}."
            )
        verified: list[str] = []
        for rel_name, expected in files_sha.items():
            if not isinstance(expected, str) or not HEX64_RE.fullmatch(expected):
                raise FactLedgerIntegrityError(
                    f"Invalid SHA-256 in {zip_path.name} handoff.json for member {rel_name!r}: {expected!r}"
                )
            if rel_name not in members:
                raise FactLedgerIntegrityError(
                    f"Handoff member {rel_name!r} listed in {zip_path.name} is missing from ZIP archive."
                )
            h = hashlib.sha256()
            with zf.open(rel_name, "r") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(chunk)
            actual = h.hexdigest()
            if actual != expected:
                raise FactLedgerIntegrityError(
                    f"Tampered ZIP member {rel_name!r} in {zip_path.name}: "
                    f"expected SHA-256 {expected}, got {actual}."
                )
            verified.append(rel_name)
        return verified


def _verify_embedded_handoff_hashes(handoff_path: Path) -> list[str]:
    """Cross-verify `files_sha256` inside a `handoff.json` against sibling files on disk."""
    data = json.loads(handoff_path.read_text(encoding="utf-8"))
    files_sha = data.get("files_sha256")
    if not isinstance(files_sha, Mapping):
        return []
    verified: list[str] = []
    parent = handoff_path.parent
    for rel_name, expected in files_sha.items():
        if not isinstance(expected, str) or not HEX64_RE.fullmatch(expected):
            raise FactLedgerIntegrityError(
                f"Invalid SHA-256 in {handoff_path.name} for member {rel_name!r}: {expected!r}"
            )
        target = parent / rel_name
        if not target.is_file():
            raise FactLedgerIntegrityError(
                f"Handoff member {rel_name!r} listed in {handoff_path} is missing on disk."
            )
        actual = sha256_file(target)
        if actual != expected:
            raise FactLedgerIntegrityError(
                f"SHA-256 mismatch for handoff member {rel_name!r}: expected {expected}, got {actual}."
            )
        verified.append(rel_name)
    return verified


def build_fact_ledger(
    *,
    artifact_paths: Sequence[Path],
    base_dir: Path | None = None,
    project_label: str | None = None,
    course_id: str = "CHEM312",
    claims: Sequence[Mapping[str, Any]] | None = None,
    explicit_tiers: Mapping[str, tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a cryptographically hashed L1-L3 FactLedger from real files on disk."""
    resolved_project_label = project_label if project_label else f"{course_id}_Dossier"
    root = base_dir.resolve() if base_dir is not None else None
    l1_entries: list[dict[str, Any]] = []
    l2_entries: list[dict[str, Any]] = []
    artifacts_by_id: dict[str, dict[str, Any]] = {}
    course_milestones, milestone_source = get_milestone_catalog_for_course(course_id)
    catalog_keys = [k for k, _ in course_milestones]
    milestone_evidence: dict[str, list[str]] = {k: [] for k, _ in course_milestones}

    seen_resolved: set[Path] = set()
    for raw_path in artifact_paths:
        resolved = raw_path.resolve()
        if resolved in seen_resolved:
            continue
        if not resolved.is_file() or resolved.is_symlink():
            raise FactLedgerIntegrityError(f"Artifact must be an existing regular file: {raw_path}")
        seen_resolved.add(resolved)

        rel_str = (
            resolved.relative_to(root).as_posix()
            if (root is not None and resolved.is_relative_to(root))
            else resolved.as_posix()
        )
        digest = sha256_file(resolved)
        size_bytes = resolved.stat().st_size

        if explicit_tiers and rel_str in explicit_tiers:
            tier, milestone = explicit_tiers[rel_str]
        else:
            tier, raw_milestone = classify_artifact_tier(resolved)
            rel_for_map = rel_str if (root is not None and resolved.is_relative_to(root)) else None
            milestone = _map_milestone_for_course(
                resolved,
                raw_milestone,
                course_id,
                catalog_keys,
                rel_path=rel_for_map,
            )

        handoff_members_verified: list[str] = []
        if resolved.name.lower() == "handoff.json":
            handoff_members_verified = _verify_embedded_handoff_hashes(resolved)
        elif resolved.suffix.lower() == ".zip":
            handoff_members_verified = _verify_embedded_handoff_zip(resolved)

        artifact_id = f"{tier}-{len(artifacts_by_id) + 1:03d}"
        entry = {
            "artifact_id": artifact_id,
            "tier": tier,
            "milestone": milestone,
            "path": rel_str,
            "sha256": digest,
            "size_bytes": int(size_bytes),
            "verified_on_disk": True,
        }
        if handoff_members_verified:
            entry["handoff_members_verified"] = handoff_members_verified

        artifacts_by_id[artifact_id] = entry
        if tier == "L1":
            l1_entries.append(entry)
        else:
            l2_entries.append(entry)
        if milestone != "UNMANIFESTED_ZIP":
            milestone_evidence.setdefault(milestone, []).append(artifact_id)

    # Validate L3 claims: refuse unhashed/fabricated claims
    l3_claims: list[dict[str, Any]] = []
    for idx, claim in enumerate(claims or (), start=1):
        claim_id = str(claim.get("claim_id", f"CLAIM-{idx:03d}"))
        statement = str(claim.get("statement", "")).strip()
        if not statement:
            raise FactLedgerIntegrityError(f"Claim {claim_id} has empty statement.")
        status_req = str(claim.get("status", "VERIFIED")).upper()
        cited_ids = claim.get("artifact_ids", [])
        if status_req == "PENDING":
            l3_claims.append(
                {
                    "claim_id": claim_id,
                    "statement": statement,
                    "status": "PENDING",
                    "evidence_artifacts": [],
                }
            )
            continue
        if not isinstance(cited_ids, list) or not cited_ids:
            raise FactLedgerIntegrityError(
                f"Unhashed/unsupported claim {claim_id!r} rejected: must reference verified L1/L2 artifact_ids."
            )
        evidence_refs: list[dict[str, str]] = []
        for aid in cited_ids:
            if aid not in artifacts_by_id:
                raise FactLedgerIntegrityError(
                    f"Claim {claim_id!r} cites unknown or unverified artifact_id {aid!r}."
                )
            art = artifacts_by_id[aid]
            expected_hash = claim.get("expected_sha256", {}).get(aid) if isinstance(claim.get("expected_sha256"), Mapping) else None
            if expected_hash is not None and expected_hash != art["sha256"]:
                raise FactLedgerIntegrityError(
                    f"Claim {claim_id!r} hash mismatch for {aid}: expected {expected_hash}, on-disk {art['sha256']}."
                )
            evidence_refs.append({"artifact_id": aid, "path": art["path"], "sha256": art["sha256"]})
        l3_claims.append(
            {
                "claim_id": claim_id,
                "statement": statement,
                "status": "VERIFIED",
                "evidence_artifacts": evidence_refs,
            }
        )

    # Build L3 milestone table (missing milestones are explicitly PENDING)
    l3_milestones: list[dict[str, Any]] = []
    catalog_key_set = {k for k, _ in course_milestones}
    use_chem312_children = course_id.upper() == "CHEM312"
    for key, title in course_milestones:
        ev_ids = list(milestone_evidence.get(key, []))
        if use_chem312_children:
            for child_key in PARENT_MILESTONE_CHILDREN.get(key, ()):
                for cid in milestone_evidence.get(child_key, []):
                    if cid not in ev_ids:
                        ev_ids.append(cid)
        l3_milestones.append(
            {
                "milestone": key,
                "title": title,
                "status": "VERIFIED" if ev_ids else "PENDING",
                "evidence_artifact_ids": ev_ids,
                "evidence_sha256": [artifacts_by_id[aid]["sha256"] for aid in ev_ids],
            }
        )
    for extra_key, ev_ids in milestone_evidence.items():
        if extra_key in catalog_key_set or not ev_ids:
            continue
        l3_milestones.append(
            {
                "milestone": extra_key,
                "title": EXTRA_MILESTONE_TITLES.get(extra_key, extra_key),
                "status": "VERIFIED",
                "evidence_artifact_ids": ev_ids,
                "evidence_sha256": [artifacts_by_id[aid]["sha256"] for aid in ev_ids],
            }
        )

    ledger_body: dict[str, Any] = {
        "schema": "cochem.fact-ledger/1",
        "collaborator_institution": "Tennessee Tech University",
        "course_id": course_id,
        "milestone_source": milestone_source,
        "project_label": resolved_project_label,
        "created_at_utc": _utc_now(),
        "base_dir": root.as_posix() if root is not None else None,
        "levels": {
            "L1_primary_artifacts": l1_entries,
            "L2_derived_artifacts": l2_entries,
            "L3_milestones": l3_milestones,
            "L3_claims": l3_claims,
        },
    }
    ledger_body["ledger_content_sha256"] = _canonical_json_sha256(ledger_body)
    return ledger_body


def verify_fact_ledger(
    ledger_path: Path,
    *,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Fail-closed verification of FactLedger.json against live disk SHA-256 digests."""
    resolved_ledger = ledger_path.resolve()
    if not resolved_ledger.is_file():
        raise FactLedgerIntegrityError(f"FactLedger file not found: {resolved_ledger}")
    payload = json.loads(resolved_ledger.read_text(encoding="utf-8"))
    if payload.get("schema") != "cochem.fact-ledger/1":
        raise FactLedgerIntegrityError(f"Unsupported FactLedger schema: {payload.get('schema')!r}")
    if payload.get("collaborator_institution") != "Tennessee Tech University":
        raise FactLedgerIntegrityError(
            f"Invalid collaborator_institution: {payload.get('collaborator_institution')!r}"
        )

    recorded_seal = payload.get("ledger_content_sha256")
    if not isinstance(recorded_seal, str) or not HEX64_RE.fullmatch(recorded_seal):
        raise FactLedgerIntegrityError("Missing or malformed ledger_content_sha256 seal.")
    body_copy = {k: v for k, v in payload.items() if k != "ledger_content_sha256"}
    recomputed_seal = _canonical_json_sha256(body_copy)
    if recomputed_seal != recorded_seal:
        raise FactLedgerIntegrityError(
            f"FactLedger seal tampered: recorded {recorded_seal}, recomputed {recomputed_seal}."
        )

    root = base_dir.resolve() if base_dir is not None else (
        Path(payload["base_dir"]).resolve() if payload.get("base_dir") else resolved_ledger.parent
    )
    levels = payload["levels"]
    verified_by_id: dict[str, str] = {}

    for tier_key in ("L1_primary_artifacts", "L2_derived_artifacts"):
        entries = levels.get(tier_key, [])
        for entry in entries:
            aid = entry["artifact_id"]
            expected_sha = entry["sha256"]
            if not isinstance(expected_sha, str) or not HEX64_RE.fullmatch(expected_sha):
                raise FactLedgerIntegrityError(f"Malformed SHA-256 for artifact {aid}: {expected_sha!r}")
            raw_p = Path(entry["path"])
            target = raw_p if raw_p.is_absolute() else (root / raw_p)
            if not target.is_file() or target.is_symlink():
                raise FactLedgerIntegrityError(f"Hashed artifact {aid} missing on disk: {target}")
            actual_sha = sha256_file(target)
            if actual_sha != expected_sha:
                raise FactLedgerIntegrityError(
                    f"Tampered artifact detected for {aid} ({entry['path']}): "
                    f"expected SHA-256 {expected_sha}, actual {actual_sha}."
                )
            if target.stat().st_size != int(entry["size_bytes"]):
                raise FactLedgerIntegrityError(
                    f"Size mismatch for {aid} ({entry['path']}): expected {entry['size_bytes']}, got {target.stat().st_size}."
                )
            if target.name.lower() == "handoff.json":
                _verify_embedded_handoff_hashes(target)
            elif target.suffix.lower() == ".zip":
                _verify_embedded_handoff_zip(target)
            verified_by_id[aid] = actual_sha

    for claim in levels.get("L3_claims", []):
        if claim.get("status") == "PENDING":
            continue
        refs = claim.get("evidence_artifacts", [])
        if not refs:
            raise FactLedgerIntegrityError(f"Unhashed claim {claim.get('claim_id')!r} found in ledger.")
        for ref in refs:
            aid = ref["artifact_id"]
            if aid not in verified_by_id or verified_by_id[aid] != ref["sha256"]:
                raise FactLedgerIntegrityError(
                    f"Claim {claim.get('claim_id')!r} references unverified or mismatched artifact {aid!r}."
                )

    return {
        "verified": True,
        "ledger_path": str(resolved_ledger),
        "ledger_content_sha256": recorded_seal,
        "verified_artifact_count": len(verified_by_id),
        "verified_claim_count": sum(1 for c in levels.get("L3_claims", []) if c.get("status") == "VERIFIED"),
        "pending_milestone_count": sum(1 for m in levels.get("L3_milestones", []) if m.get("status") == "PENDING"),
    }


def render_fact_ledger_markdown(ledger: Mapping[str, Any]) -> str:
    levels = ledger["levels"]
    lines = [
        f"# Cryptographic FactLedger (L1–L3 SHA-256) — `{ledger['project_label']}`",
        "",
        f"- **Institution:** {ledger['collaborator_institution']}",
        f"- **Course:** `{ledger['course_id']}`",
        f"- **Created (UTC):** {ledger['created_at_utc']}",
        f"- **Ledger Seal SHA-256:** `{ledger['ledger_content_sha256']}`",
        "",
        "## L3 Course Milestone Status",
        "",
        "| Milestone | Description | Status | Evidence IDs |",
        "| --- | --- | --- | --- |",
    ]
    for m in levels["L3_milestones"]:
        ev = ", ".join(m["evidence_artifact_ids"]) if m["evidence_artifact_ids"] else "PENDING"
        lines.append(f"| `{m['milestone']}` | {m['title']} | **{m['status']}** | {ev} |")

    lines.extend(
        [
            "",
            "## L1 Primary Computation & Observation Artifacts",
            "",
            "| ID | Milestone | Path | Bytes | SHA-256 |",
            "| --- | --- | --- | ---: | --- |",
        ]
    )
    for item in levels["L1_primary_artifacts"]:
        lines.append(
            f"| `{item['artifact_id']}` | `{item['milestone']}` | `{item['path']}` | {item['size_bytes']} | `{item['sha256']}` |"
        )
    if not levels["L1_primary_artifacts"]:
        lines.append("| *(none)* | — | — | 0 | `PENDING` |")

    lines.extend(
        [
            "",
            "## L2 Derived Tables & Analytics",
            "",
            "| ID | Milestone | Path | Bytes | SHA-256 |",
            "| --- | --- | --- | ---: | --- |",
        ]
    )
    for item in levels["L2_derived_artifacts"]:
        lines.append(
            f"| `{item['artifact_id']}` | `{item['milestone']}` | `{item['path']}` | {item['size_bytes']} | `{item['sha256']}` |"
        )
    if not levels["L2_derived_artifacts"]:
        lines.append("| *(none)* | — | — | 0 | `PENDING` |")

    if levels["L3_claims"]:
        lines.extend(
            [
                "",
                "## L3 Cryptographically Bound Claims",
                "",
                "| Claim ID | Status | Statement | Evidence SHA-256 |",
                "| --- | --- | --- | --- |",
            ]
        )
        for c in levels["L3_claims"]:
            hashes = ", ".join(f"`{r['sha256'][:12]}...`" for r in c["evidence_artifacts"]) or "PENDING"
            lines.append(f"| `{c['claim_id']}` | **{c['status']}** | {c['statement']} | {hashes} |")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Build or verify cryptographic L1-L3 SHA-256 FactLedger.json and FactLedger.md (CHEM 312 M4)."
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--artifacts", nargs="+", type=Path, help="Upstream artifact file paths to hash into FactLedger.")
    mode.add_argument("--verify", type=Path, help="Existing FactLedger.json path to verify fail-closed against disk.")
    p.add_argument("--base-dir", type=Path, default=None, help="Base directory for relative artifact paths.")
    p.add_argument(
        "--project-label",
        default=None,
        help="Project/team label (defaults to '<course_id>_Dossier', e.g., CHEM312_Dossier or CHEM490_Dossier).",
    )
    p.add_argument(
        "--course-id",
        type=_validate_course_id,
        default="CHEM312",
        help=(
            "Course provenance identifier resolved dynamically via CoChem-CURE when installed "
            "(default: CHEM312; fallback: CHEM311, CHEM312, CHEM490, CHEM410, CHEM411)."
        ),
    )
    p.add_argument("--claims-json", type=Path, default=None, help="Optional JSON array of L3 claims referencing artifact_ids.")
    p.add_argument("--output-json", type=Path, default=None, help="Output FactLedger.json path.")
    p.add_argument("--output-md", type=Path, default=None, help="Output FactLedger.md path.")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.verify is not None:
        receipt = verify_fact_ledger(args.verify, base_dir=args.base_dir)
        print(json.dumps(receipt, indent=2))
        return 0

    claims_list = json.loads(args.claims_json.read_text(encoding="utf-8")) if args.claims_json else None
    ledger = build_fact_ledger(
        artifact_paths=args.artifacts,
        base_dir=args.base_dir,
        project_label=args.project_label,
        course_id=args.course_id,
        claims=claims_list,
    )
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    if args.output_md is not None:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_fact_ledger_markdown(ledger), encoding="utf-8")
    print(json.dumps(ledger, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
