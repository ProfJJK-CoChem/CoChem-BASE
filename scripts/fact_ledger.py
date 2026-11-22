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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

DEFAULT_MILESTONES: tuple[tuple[str, str], ...] = (
    ("M1_conformers", "M1 Conformer Ensemble & Handoff"),
    ("M2_kk_atr", "M2 Kramers-Kronig ATR-FTIR & Harmonic Comparison"),
    ("M3_nci_gvpt2_fermi", "M3 1:1 NCI/BSSE, 6-Shard GVPT2 & Fermi Deperturbation"),
    ("M4_spcat_8_18ghz", "M4 SPCAT 8-18 GHz Rotational Prediction & Dossier"),
)


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


def classify_artifact_tier(path: Path) -> tuple[str, str]:
    """Classify an upstream artifact into (level, milestone_key)."""
    name = path.name.lower()
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
    project_label: str = "CHEM312_Dossier",
    course_id: str = "CHEM312",
    claims: Sequence[Mapping[str, Any]] | None = None,
    explicit_tiers: Mapping[str, tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a cryptographically hashed L1-L3 FactLedger from real files on disk."""
    root = base_dir.resolve() if base_dir is not None else None
    l1_entries: list[dict[str, Any]] = []
    l2_entries: list[dict[str, Any]] = []
    artifacts_by_id: dict[str, dict[str, Any]] = {}
    milestone_evidence: dict[str, list[str]] = {k: [] for k, _ in DEFAULT_MILESTONES}

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
            tier, milestone = classify_artifact_tier(resolved)

        handoff_members_verified: list[str] = []
        if resolved.name.lower() == "handoff.json":
            handoff_members_verified = _verify_embedded_handoff_hashes(resolved)

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
    for key, title in DEFAULT_MILESTONES:
        ev_ids = milestone_evidence.get(key, [])
        l3_milestones.append(
            {
                "milestone": key,
                "title": title,
                "status": "VERIFIED" if ev_ids else "PENDING",
                "evidence_artifact_ids": ev_ids,
                "evidence_sha256": [artifacts_by_id[aid]["sha256"] for aid in ev_ids],
            }
        )

    ledger_body: dict[str, Any] = {
        "schema": "cochem.fact-ledger/1",
        "collaborator_institution": "Tennessee Tech University",
        "course_id": course_id,
        "project_label": project_label,
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
    p.add_argument("--project-label", default="CHEM312_Dossier", help="Project/team label.")
    p.add_argument("--course-id", default="CHEM312", choices=("CHEM312", "CHEM490", "CHEM410", "CHEM411"))
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
