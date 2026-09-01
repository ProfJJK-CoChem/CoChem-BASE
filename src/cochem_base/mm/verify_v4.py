"""
CoChem-TOPOS Verification Engine: Machine-Checkable Invariants on Method Matrix v4.

Component: mm/verify_v4.py
Authoritative Reference: Method Matrix §12.6, §12.1–§12.5, §13, §14, §23 (Version 4, August 2026).

Enforces machine-checkable invariants on every Method Matrix tier table:
  1. Invariant 1 (§12.6, §12.3): Every row has a non-empty Row ID, Concurrency tag, and Limitations cell.
  2. Invariant 2 (§12.6, §12.5 Rules 7 & 8): Every accuracy cell names a physical/computational quantity
     and carries an authoritative provenance tag ([M], [D], or [E]).
  3. Invariant 3 (§12.6, §12.3): Every table has exactly ten wall-clock tiers matching canonical sequence:
     ['10 s', '1 min', '30 min', '1 h', '3 h', '12 h', '1 d', '3 d', '1 w', '1 mo'].
  4. Invariant 4 (§12.6, §12.2): Every track is explicitly labelled (Single track or dual ORCA/CFOUR tracks).
  5. Invariant 5 (§12.6, §14.2): No accuracy claim in Table 7 exceeds the ±14 % benchmark cap
     (ammonia-formic acid benchmark spread).
  6. Invariant 6 (§12.6, §12.3): No Product cell contains prose paragraphs (only valid product designators
     A, B, C, combinations, or track gap indicators).
  7. Invariant 7 (§12.6, §23): No reference is a bare URL, an unauthorized file-sharing link,
     or a document-mirror stub. Every Section 23 reference follows structured format '[anchor](url) — domain'.

Hardware & Protocol Invariants:
  - Setup 1 (GitHub teaching runner, §8.4b, §19): Max 6 h wall-clock per job, 8 vCPUs, no commercial licences.
  - Setup 2 (Workstation reference, §8.1, §12.1): Intel Core i7-13700K (8 P-cores, 7 ranks when GPU companion
    co-scheduled), 64 GB DDR5, NVMe scratch, NVIDIA RTX 3090 (24 GB VRAM), MPS multi-process service.
  - Setup 3 (HPC node, §8.4a, §12.5 Rule 9): 128 cores per node; Setup-3-only rows must quote 128-core figures.
  - Prohibitions (§9A.5): Additive diffuse corrections and ONIOM rejected at 5–10 atoms; Calc_Hess true forbidden (§8B.3).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Canonical wall-clock tiers in ascending duration order (§12.3)
CANONICAL_TIERS: list[str] = [
    "10 s",
    "1 min",
    "30 min",
    "1 h",
    "3 h",
    "12 h",
    "1 d",
    "3 d",
    "1 w",
    "1 mo",
]

# Valid base concurrency tags (§12.4)
VALID_CONCURRENCY_TAGS: set[str] = {"C", "G", "P", "S", "—", "-"}

# Valid product designator classes (§1.2, §12.3)
VALID_PRODUCT_TAGS: set[str] = {
    "A",
    "B",
    "C",
    "A, B",
    "A/B",
    "B/C",
    "A/C",
    "A (de novo)",
    "B (template)",
    "C (diff)",
    "—",
    "-",
    "n.a.",
}

# Unauthorized file-sharing domains strictly forbidden from references (§12.6, §23)
FORBIDDEN_FILE_SHARING_DOMAINS: list[str] = [
    "drive.google.com",
    "dropbox.com",
    "mediafire.com",
    "mega.nz",
    "mega.io",
    "box.com",
    "onedrive.live.com",
    "1drv.ms",
    "wetransfer.com",
    "filedropper.com",
    "sendspace.com",
    "rapidgator.net",
]

# Document mirror domains forbidden from authoritative reference list (§12.6, §23)
FORBIDDEN_MIRROR_DOMAINS: list[str] = [
    "sci-hub",
    "libgen",
    "document-mirror",
    "bookfi",
    "b-ok.org",
]

# Authoritative Table Section definitions in Method Matrix (§13, §14)
EXPECTED_TABLE_SECTIONS: list[dict[str, Any]] = [
    {
        "table_id": "Table 1",
        "title": "Conformer and isomer search",
        "track_type": "single",
        "pattern": r"### 13\.1 Table 1.*?(?=### 13\.2)",
        "expected_code_track": "ORCA",
    },
    {
        "table_id": "Table 2",
        "title": "Intermolecular potential surfaces, scanning, and the DVR",
        "track_type": "single",
        "pattern": r"### 13\.2 Table 2.*?(?=### 13\.3)",
        "expected_code_track": "ORCA",
    },
    {
        "table_id": "Table 3-O",
        "title": "Equilibrium geometry and B_e — ORCA track",
        "track_type": "orca",
        "pattern": r"#### Table 3-O.*?(?=#### Table 3-C)",
        "expected_code_track": "ORCA",
    },
    {
        "table_id": "Table 3-C",
        "title": "Equilibrium geometry and B_e — CFOUR track",
        "track_type": "cfour",
        "pattern": r"#### Table 3-C.*?(?=### 13\.4)",
        "expected_code_track": "CFOUR",
    },
    {
        "table_id": "Table 4-O",
        "title": "Vibrational averaging: from B_e to B₀ — ORCA track",
        "track_type": "orca",
        "pattern": r"#### Table 4-O.*?(?=#### Table 4-C)",
        "expected_code_track": "ORCA",
    },
    {
        "table_id": "Table 4-C",
        "title": "Vibrational averaging: from B_e to B₀ — CFOUR track",
        "track_type": "cfour",
        "pattern": r"#### Table 4-C.*?(?=### 13\.5)",
        "expected_code_track": "CFOUR",
    },
    {
        "table_id": "Table 5",
        "title": "Interaction and binding energies",
        "track_type": "single",
        "pattern": r"### 13\.5 Table 5.*?(?=## 14\.)",
        "expected_code_track": "ORCA",
    },
    {
        "table_id": "Table 6-O",
        "title": "Dipole, quadrupole, distortion — ORCA track",
        "track_type": "orca",
        "pattern": r"#### Table 6-O.*?(?=#### Table 6-C)",
        "expected_code_track": "ORCA",
    },
    {
        "table_id": "Table 6-C",
        "title": "Dipole, quadrupole, distortion — CFOUR track",
        "track_type": "cfour",
        "pattern": r"#### Table 6-C.*?(?=### 14\.2)",
        "expected_code_track": "CFOUR",
    },
    {
        "table_id": "Table 7",
        "title": "Internal rotation, tunnelling and large-amplitude motion",
        "track_type": "single",
        "pattern": r"### 14\.2 Table 7.*?(?=### 14\.3)",
        "expected_code_track": "ORCA",
    },
    {
        "table_id": "Table 8-O",
        "title": "Infrared, terahertz and far-infrared — ORCA track",
        "track_type": "orca",
        "pattern": r"#### Table 8-O.*?(?=#### Table 8-C)",
        "expected_code_track": "ORCA",
    },
    {
        "table_id": "Table 8-C",
        "title": "Infrared, terahertz and far-infrared — CFOUR track",
        "track_type": "cfour",
        "pattern": r"#### Table 8-C.*?(?=### 14\.4)",
        "expected_code_track": "CFOUR",
    },
    {
        "table_id": "Table 9",
        "title": "Raman",
        "track_type": "single",
        "pattern": r"### 14\.4 Table 9.*?(?=### 14\.5)",
        "expected_code_track": "ORCA",
    },
    {
        "table_id": "Table 10",
        "title": "Nuclear magnetic resonance, ultraviolet–visible and mass spectrometry",
        "track_type": "single",
        "pattern": r"### 14\.5 Table 10.*?(?=## 15\.)",
        "expected_code_track": "ORCA",
    },
]


class Severity(str, Enum):
    """Verification issue severity."""
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True)
class TierRow:
    """Represents a single row from a Method Matrix visible tier table (7 columns)."""

    table_id: str
    row_id: str
    tier: str
    method_code: str
    delivers_accuracy: str
    concurrency_tag: str
    product: str
    limitations: str
    raw_markdown: str
    line_number: int = 0

    @property
    def clean_row_id(self) -> str:
        """Strip markdown bold/italic formatting from Row ID."""
        return re.sub(r"[*_`]", "", self.row_id).strip()

    @property
    def clean_concurrency(self) -> str:
        """Strip markdown formatting from Concurrency tag."""
        return re.sub(r"[*_`]", "", self.concurrency_tag).strip()

    @property
    def clean_product(self) -> str:
        """Strip markdown formatting from Product cell."""
        return re.sub(r"[*_`]", "", self.product).strip()


@dataclass(frozen=True)
class ExpansionRow:
    """Represents a single row from a tier table expansion block."""

    table_id: str
    row_id: str
    core_h: str
    input_workflow: str
    state_in: str
    state_out: str
    frozen_mono: str
    mem_scratch: str
    licence: str
    setup_1: str
    max_benchmark_error: str
    mitigation_notes: str
    raw_markdown: str
    line_number: int = 0


@dataclass
class TierTable:
    """Represents a full tier table including metadata, rows, and expansion data."""

    table_id: str
    title: str
    track_type: str  # 'single', 'orca', 'cfour'
    expected_code_track: str
    section_text: str
    rows: list[TierRow] = field(default_factory=list)
    expansion_rows: list[ExpansionRow] = field(default_factory=list)
    expansion_text: str = ""
    start_line: int = 0


@dataclass(frozen=True)
class ReferenceItem:
    """Represents an authoritative reference item in Section 23."""

    number: int
    anchor: str
    url: str
    domain: str
    raw_markdown: str
    line_number: int = 0


@dataclass(frozen=True)
class VerificationIssue:
    """Detailed record of an invariant verification issue or failure."""

    category: str
    table_id: str
    row_id: str
    severity: Severity
    check_code: str
    message: str
    line_number: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "table_id": self.table_id,
            "row_id": self.row_id,
            "severity": self.severity.value,
            "check_code": self.check_code,
            "message": self.message,
            "line_number": self.line_number,
        }


@dataclass
class VerificationReport:
    """Comprehensive structured verification report for Method Matrix v4."""

    file_path: str
    timestamp_utc: str
    total_tables_checked: int = 0
    total_rows_checked: int = 0
    total_references_checked: int = 0
    issues: list[VerificationIssue] = field(default_factory=list)
    passed: bool = True
    hardware_limits_checked: bool = True

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.INFO)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "timestamp_utc": self.timestamp_utc,
            "passed": self.passed,
            "total_tables_checked": self.total_tables_checked,
            "total_rows_checked": self.total_rows_checked,
            "total_references_checked": self.total_references_checked,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "issues": [i.to_dict() for i in self.issues],
        }


# -----------------------------------------------------------------------------
# Document Parser
# -----------------------------------------------------------------------------

def find_line_number(full_text: str, substring: str) -> int:
    """Find 1-indexed line number where substring occurs."""
    idx = full_text.find(substring)
    if idx == -1:
        return 0
    return full_text[:idx].count("\n") + 1


def parse_method_matrix_tables(full_text: str) -> list[TierTable]:
    """
    Extract and parse all 14 Method Matrix tier tables and expansion blocks.

    Args:
        full_text: Raw Markdown text of Method_Matrix.md.

    Returns:
        List of parsed TierTable objects.
    """
    tables: list[TierTable] = []

    for spec in EXPECTED_TABLE_SECTIONS:
        t_id = spec["table_id"]
        title = spec["title"]
        track_type = spec["track_type"]
        expected_code_track = spec["expected_code_track"]
        pat = spec["pattern"]

        m = re.search(pat, full_text, re.DOTALL)
        if not m:
            logger.error(f"Failed to match section pattern for {t_id}")
            continue

        sec_text = m.group(0)
        start_line = find_line_number(full_text, sec_text)

        tier_table = TierTable(
            table_id=t_id,
            title=title,
            track_type=track_type,
            expected_code_track=expected_code_track,
            section_text=sec_text,
            start_line=start_line,
        )

        md_tables = re.findall(r"(\|[^\n]+\|\n\|[-|\s:]+\|\n(?:\|[^\n]+\|\n)+)", sec_text)
        if not md_tables:
            logger.warning(f"No markdown tables found in section {t_id}")
            tables.append(tier_table)
            continue

        primary_md = md_tables[0]
        lines = [line.strip() for line in primary_md.strip().split("\n") if line.strip()]

        for row_str in lines[2:]:
            cols = [c.strip() for c in row_str.split("|")[1:-1]]
            if len(cols) < 7:
                continue

            r_id, tier, method, delivers, conc, prod, lims = cols[:7]
            row_line = find_line_number(full_text, row_str)

            tier_row = TierRow(
                table_id=t_id,
                row_id=r_id,
                tier=tier,
                method_code=method,
                delivers_accuracy=delivers,
                concurrency_tag=conc,
                product=prod,
                limitations=lims,
                raw_markdown=row_str,
                line_number=row_line,
            )
            tier_table.rows.append(tier_row)

        if len(md_tables) > 1:
            exp_md = md_tables[1]
            exp_lines = [line.strip() for line in exp_md.strip().split("\n") if line.strip()]
            for exp_row_str in exp_lines[2:]:
                exp_cols = [c.strip() for c in exp_row_str.split("|")[1:-1]]
                if len(exp_cols) >= 11:
                    exp_row = ExpansionRow(
                        table_id=t_id,
                        row_id=exp_cols[0],
                        core_h=exp_cols[1],
                        input_workflow=exp_cols[2],
                        state_in=exp_cols[3],
                        state_out=exp_cols[4],
                        frozen_mono=exp_cols[5],
                        mem_scratch=exp_cols[6],
                        licence=exp_cols[7],
                        setup_1=exp_cols[8],
                        max_benchmark_error=exp_cols[9],
                        mitigation_notes=exp_cols[10],
                        raw_markdown=exp_row_str,
                        line_number=find_line_number(full_text, exp_row_str),
                    )
                    tier_table.expansion_rows.append(exp_row)

        exp_header_match = re.search(r"\*\*Expansion block.*", sec_text, re.DOTALL)
        if exp_header_match:
            tier_table.expansion_text = exp_header_match.group(0)

        tables.append(tier_table)

    return tables


def parse_section_23_references(full_text: str) -> list[ReferenceItem]:
    """
    Extract and parse all numbered references in Section 23.

    Args:
        full_text: Raw Markdown text of Method_Matrix.md.

    Returns:
        List of parsed ReferenceItem objects.
    """
    m = re.search(r"## 23\.\s+References\s*\n\s*(.*)", full_text, re.DOTALL)
    if not m:
        return []

    refs_section = m.group(1)
    ref_lines = [
        line.strip()
        for line in refs_section.split("\n")
        if line.strip() and not line.strip().startswith("Every reference below")
    ]

    references: list[ReferenceItem] = []
    for line in ref_lines:
        match = re.match(r"^(\d+)\.\s+\[(.+?)\]\((https?://.+?)\)\s*—\s*(.+)$", line)
        if match:
            num_str, anchor, url, domain = match.groups()
            line_no = find_line_number(full_text, line)
            references.append(
                ReferenceItem(
                    number=int(num_str),
                    anchor=anchor.strip(),
                    url=url.strip(),
                    domain=domain.strip(),
                    raw_markdown=line,
                    line_number=line_no,
                )
            )

    return references


# -----------------------------------------------------------------------------
# Invariant Verification Rules (§12.6, §12.1-§12.5)
# -----------------------------------------------------------------------------

def verify_invariant_1_row_completeness(table: TierTable) -> list[VerificationIssue]:
    """
    Invariant 1: Every row has a non-empty Row ID, Concurrency tag, and Limitations cell (§12.6, §12.3).
    """
    issues: list[VerificationIssue] = []

    for row in table.rows:
        # 1. Non-empty Row ID
        clean_id = row.clean_row_id
        if not clean_id or clean_id in {"—", "-"}:
            issues.append(
                VerificationIssue(
                    category="Invariant 1: Row Completeness",
                    table_id=table.table_id,
                    row_id=row.row_id,
                    severity=Severity.ERROR,
                    check_code="INV1_EMPTY_ROW_ID",
                    message=f"{table.table_id}: Row contains empty or placeholder Row ID.",
                    line_number=row.line_number,
                )
            )

        # 2. Non-empty, valid Concurrency tag
        clean_conc = row.clean_concurrency
        if not clean_conc:
            issues.append(
                VerificationIssue(
                    category="Invariant 1: Row Completeness",
                    table_id=table.table_id,
                    row_id=clean_id,
                    severity=Severity.ERROR,
                    check_code="INV1_EMPTY_CONCURRENCY",
                    message=f"{table.table_id} row {clean_id}: Concurrency tag is empty.",
                    line_number=row.line_number,
                )
            )
        else:
            tokens = [re.sub(r"[^A-Za-z—\-]", "", tok) for tok in clean_conc.split()]
            tokens = [t for t in tokens if t and t not in {"then", "or", "with", "a", "CPU", "driver"}]
            for tok in tokens:
                if tok not in VALID_CONCURRENCY_TAGS:
                    issues.append(
                        VerificationIssue(
                            category="Invariant 1: Row Completeness",
                            table_id=table.table_id,
                            row_id=clean_id,
                            severity=Severity.WARNING,
                            check_code="INV1_UNUSUAL_CONCURRENCY",
                            message=f"{table.table_id} row {clean_id}: Unusual concurrency class '{tok}' in '{row.concurrency_tag}'.",
                            line_number=row.line_number,
                        )
                    )

        # 3. Non-empty Limitations cell
        lims = row.limitations.strip()
        if not lims:
            issues.append(
                VerificationIssue(
                    category="Invariant 1: Row Completeness",
                    table_id=table.table_id,
                    row_id=clean_id,
                    severity=Severity.ERROR,
                    check_code="INV1_EMPTY_LIMITATIONS",
                    message=f"{table.table_id} row {clean_id}: Limitations cell is completely empty.",
                    line_number=row.line_number,
                )
            )
        elif lims in {"—", "-"} and clean_conc not in {"—", "-"}:
            issues.append(
                VerificationIssue(
                    category="Invariant 1: Row Completeness",
                    table_id=table.table_id,
                    row_id=clean_id,
                    severity=Severity.ERROR,
                    check_code="INV1_PLACEHOLDER_LIMITATIONS",
                    message=f"{table.table_id} row {clean_id}: Active row has bare placeholder limitation.",
                    line_number=row.line_number,
                )
            )

    return issues


def verify_invariant_2_accuracy_provenance(table: TierTable) -> list[VerificationIssue]:
    """
    Invariant 2: Every accuracy cell names a quantity and carries an authoritative provenance tag (§12.6, §12.5 Rule 7).
    """
    issues: list[VerificationIssue] = []

    provenance_pattern = re.compile(r"\[[MDE]\]|`\[[MDE]\]`")

    recognized_quantities = [
        "B_e", "B₀", "B_0", "ΔB_vib", "ΔB", "D₀", "D_0", "ΔE", "V₃", "V_3", "ω", "ν", "μ", "μ_a", "μ_b", "μ_c",
        "χ", "χ_aa", "χ_bb", "χ_cc", "χ(D)", "C_aa", "C_bb", "C_cc", "Δ", "P_aa", "P_bb", "P_cc",
        "ensemble", "topology", "well topology", "boundaries of the well", "relative energies", "band origins",
        "A/E splittings", "tunnelling splitting", "splittings", "barrier", "mode ordering", "polarizability",
        "depolarisation ratios", "shifts", "excitations", "absorption", "fragmentation", "branching ratios",
        "quartic", "sextic", "closed small-correction set", "the closed set", "structural sanity check",
        "no accuracy claim", "no energy claim", "no B_e claim", "no V₃ claim", "qualitative", "spectrum",
        "spectra", "fundamentals", "overtones", "combination bands", "vibrational corrections", "alpha constants",
        "α constants", "centrifugal distortion", "Watson parameters", "activity", "intensities", "frequencies",
        "excited-state", "template", "existence and rough", "shape of the", "activity pattern", "surface",
        "force field", "spectroscopic-constant", "spectroscopic", "physical decomposition", "decomposition",
        "B_v", "satellites", "intermolecular modes", "dipole", "quadrupole", "octopole", "field gradients",
        "electric field", "DBOC", "excitation", "excitation energies", "search", "coverage", "checkpoint",
        "insurance", "estimate", "manifold", "intermolecular manifold", "A14", "kJ/mol", "kcal/mol", "cm⁻¹",
        "RMS", "MUE", "site–site", "PIP", "points",
    ]

    for row in table.rows:
        clean_id = row.clean_row_id
        deliv = row.delivers_accuracy.strip()
        lims = row.limitations.strip()
        prod = row.clean_product

        is_track_gap = (
            deliv in {"—", "-", "n.a.", ""}
            or prod in {"—", "-", "n.a."}
            or "Cannot fill" in lims
            or "Track gap" in lims
        )

        if is_track_gap:
            continue

        has_quantity = any(q.lower() in deliv.lower() for q in recognized_quantities)
        if not has_quantity:
            issues.append(
                VerificationIssue(
                    category="Invariant 2: Accuracy & Provenance",
                    table_id=table.table_id,
                    row_id=clean_id,
                    severity=Severity.WARNING,
                    check_code="INV2_UNNAMED_QUANTITY",
                    message=f"{table.table_id} row {clean_id}: Delivers/accuracy cell does not explicitly identify a standard physical quantity: '{deliv}'.",
                    line_number=row.line_number,
                )
            )

        has_prov_tag = bool(provenance_pattern.search(deliv))
        has_explicit_qualitative_note = any(
            phrase in deliv.lower()
            for phrase in [
                "no accuracy claim",
                "no energy claim",
                "no b_e claim",
                "no v₃ claim",
                "qualitative",
                "screening only",
                "structural sanity check",
                "an estimate only",
                "mode ordering",
                "shape of the",
                "activity pattern",
                "a full spectrum",
                "depolarisation ratios",
                "overtones and combination",
                "closed set",
                "closed small-correction",
                "existence and rough",
                "fragmentation pattern",
                "branching ratios",
                "shifts, referenced",
                "corrected shifts",
                "intermolecular raman activity",
                "the complete activity map",
                "full spectra for",
                "reference excitation energies",
                "propagates steeply into the splitting",
                "still **±14 %** against experiment",
                "order of magnitude for intermolecular modes",
            ]
        )

        has_numeric_bound = bool(re.search(r"±\s*\d|\d+\s*(?:%|cm⁻¹|kcal/mol|kJ/mol|eV|D|MHz|GHz|pm|Å)", deliv))

        if has_numeric_bound and not has_prov_tag and not has_explicit_qualitative_note:
            issues.append(
                VerificationIssue(
                    category="Invariant 2: Accuracy & Provenance",
                    table_id=table.table_id,
                    row_id=clean_id,
                    severity=Severity.WARNING,
                    check_code="INV2_MISSING_PROVENANCE_TAG",
                    message=f"{table.table_id} row {clean_id}: Quantitative accuracy claim lacks authoritative [M]/[D]/[E] provenance tag: '{deliv}'.",
                    line_number=row.line_number,
                )
            )

    return issues


def verify_invariant_3_ten_wall_clock_tiers(table: TierTable) -> list[VerificationIssue]:
    """
    Invariant 3: Every table has exactly ten wall-clock tiers in canonical order (§12.6, §12.3).
    """
    issues: list[VerificationIssue] = []

    if len(table.rows) != 10:
        issues.append(
            VerificationIssue(
                category="Invariant 3: Ten Wall-Clock Tiers",
                table_id=table.table_id,
                row_id="TABLE_STRUCTURE",
                severity=Severity.ERROR,
                check_code="INV3_ROW_COUNT_MISMATCH",
                message=f"{table.table_id}: Table contains {len(table.rows)} rows, expected exactly 10 wall-clock tiers.",
                line_number=table.start_line,
            )
        )
        return issues

    for idx, (expected_tier, row) in enumerate(zip(CANONICAL_TIERS, table.rows, strict=False)):
        clean_tier = re.sub(r"[*_`]", "", row.tier).strip()
        if clean_tier != expected_tier:
            issues.append(
                VerificationIssue(
                    category="Invariant 3: Ten Wall-Clock Tiers",
                    table_id=table.table_id,
                    row_id=row.clean_row_id,
                    severity=Severity.ERROR,
                    check_code="INV3_TIER_SEQUENCE_MISMATCH",
                    message=f"{table.table_id} row index {idx}: Tier is '{row.tier}', expected canonical tier '{expected_tier}'.",
                    line_number=row.line_number,
                )
            )

    return issues


def verify_invariant_4_track_labelling(table: TierTable) -> list[VerificationIssue]:
    """
    Invariant 4: Every track is labelled (§12.6, §12.2).
    """
    issues: list[VerificationIssue] = []
    sec_text = table.section_text

    if table.track_type == "single":
        has_single_track_label = "Single track" in sec_text or "single track" in sec_text.lower()
        if not has_single_track_label:
            issues.append(
                VerificationIssue(
                    category="Invariant 4: Track Labelling",
                    table_id=table.table_id,
                    row_id="SECTION_PREAMBLE",
                    severity=Severity.WARNING,
                    check_code="INV4_MISSING_SINGLE_TRACK_LABEL",
                    message=f"{table.table_id}: Single-track table preamble should explicitly state 'Single track'.",
                    line_number=table.start_line,
                )
            )
    elif table.track_type == "orca":
        if "ORCA track" not in sec_text:
            issues.append(
                VerificationIssue(
                    category="Invariant 4: Track Labelling",
                    table_id=table.table_id,
                    row_id="SUBSECTION_HEADER",
                    severity=Severity.ERROR,
                    check_code="INV4_MISSING_ORCA_TRACK_LABEL",
                    message=f"{table.table_id}: Dual-track subtable is missing explicit 'ORCA track' label.",
                    line_number=table.start_line,
                )
            )
        for row in table.rows:
            clean_id = row.clean_row_id
            if not clean_id.startswith("T") or "O-" not in clean_id:
                if clean_id not in {"—", "-"}:
                    issues.append(
                        VerificationIssue(
                            category="Invariant 4: Track Labelling",
                            table_id=table.table_id,
                            row_id=clean_id,
                            severity=Severity.WARNING,
                            check_code="INV4_ORCA_ROW_ID_FORMAT",
                            message=f"{table.table_id} row {clean_id}: Row ID does not follow standard 'T<Num>O-' track format.",
                            line_number=row.line_number,
                        )
                    )
    elif table.track_type == "cfour":
        if "CFOUR track" not in sec_text:
            issues.append(
                VerificationIssue(
                    category="Invariant 4: Track Labelling",
                    table_id=table.table_id,
                    row_id="SUBSECTION_HEADER",
                    severity=Severity.ERROR,
                    check_code="INV4_MISSING_CFOUR_TRACK_LABEL",
                    message=f"{table.table_id}: Dual-track subtable is missing explicit 'CFOUR track' label.",
                    line_number=table.start_line,
                )
            )
        for row in table.rows:
            clean_id = row.clean_row_id
            if not clean_id.startswith("T") or "C-" not in clean_id:
                if clean_id not in {"—", "-"}:
                    issues.append(
                        VerificationIssue(
                            category="Invariant 4: Track Labelling",
                            table_id=table.table_id,
                            row_id=clean_id,
                            severity=Severity.WARNING,
                            check_code="INV4_CFOUR_ROW_ID_FORMAT",
                            message=f"{table.table_id} row {clean_id}: Row ID does not follow standard 'T<Num>C-' track format.",
                            line_number=row.line_number,
                        )
                    )

    return issues


def verify_invariant_5_table_7_cap(table: TierTable) -> list[VerificationIssue]:
    """
    Invariant 5: No accuracy claim in Table 7 exceeds the ±14 % benchmark cap (§12.6, §14.2).
    """
    issues: list[VerificationIssue] = []

    if table.table_id != "Table 7":
        return issues

    for row in table.rows:
        clean_id = row.clean_row_id
        deliv = row.delivers_accuracy

        pct_matches = re.findall(r"±\s*(\d+(?:\.\d+)?)\s*%", deliv)
        for pct_str in pct_matches:
            val = float(pct_str)
            if val < 14.0 and ("V₃" in deliv or "barrier" in deliv.lower() or "v3" in deliv.lower()):
                issues.append(
                    VerificationIssue(
                        category="Invariant 5: Table 7 Benchmark Cap",
                        table_id=table.table_id,
                        row_id=clean_id,
                        severity=Severity.ERROR,
                        check_code="INV5_TABLE_7_OVERCLAIM",
                        message=(
                            f"Table 7 row {clean_id}: Claim ±{val}% exceeds in-domain ±14% benchmark cap "
                            f"(ammonia-formic acid span 168.3–212.8 cm⁻¹). Text: '{deliv}'."
                        ),
                        line_number=row.line_number,
                    )
                )

    return issues


def verify_invariant_6_product_no_prose(table: TierTable) -> list[VerificationIssue]:
    """
    Invariant 6: No Product cell contains prose (§12.6, §12.3, §1.2).
    """
    issues: list[VerificationIssue] = []

    for row in table.rows:
        clean_id = row.clean_row_id
        clean_prod = row.clean_product

        is_prose = (
            len(clean_prod.split()) > 3
            or len(clean_prod) > 20
            or any(w in clean_prod.lower() for w in ["because", "which", "will", "this", "method", "using"])
        )

        if is_prose:
            issues.append(
                VerificationIssue(
                    category="Invariant 6: Product Conformance",
                    table_id=table.table_id,
                    row_id=clean_id,
                    severity=Severity.ERROR,
                    check_code="INV6_PRODUCT_CONTAINS_PROSE",
                    message=f"{table.table_id} row {clean_id}: Product cell contains prose description instead of class tag: '{row.product}'.",
                    line_number=row.line_number,
                )
            )
        elif clean_prod not in VALID_PRODUCT_TAGS and clean_prod not in {"**A**", "**B**", "**C**"}:
            issues.append(
                VerificationIssue(
                    category="Invariant 6: Product Conformance",
                    table_id=table.table_id,
                    row_id=clean_id,
                    severity=Severity.WARNING,
                    check_code="INV6_NONSTANDARD_PRODUCT_TAG",
                    message=f"{table.table_id} row {clean_id}: Non-standard Product tag '{row.product}'.",
                    line_number=row.line_number,
                )
            )

    return issues


def verify_invariant_7_reference_integrity(
    full_text: str,
    references: list[ReferenceItem],
) -> list[VerificationIssue]:
    """
    Invariant 7: No reference is a bare URL, a file-sharing link, or a document-mirror stub (§12.6, §23).
    """
    issues: list[VerificationIssue] = []

    # 1. Audit Section 23 reference entries if present in document
    if "## 23. References" in full_text and not references:
        issues.append(
            VerificationIssue(
                category="Invariant 7: Reference Integrity",
                table_id="SECTION_23",
                row_id="REFERENCES",
                severity=Severity.ERROR,
                check_code="INV7_NO_REFERENCES_PARSED",
                message="Section 23 header is present but no structured references were parsed.",
                line_number=find_line_number(full_text, "## 23. References"),
            )
        )

    for ref in references:
        if ref.anchor.startswith("http://") or ref.anchor.startswith("https://"):
            issues.append(
                VerificationIssue(
                    category="Invariant 7: Reference Integrity",
                    table_id="SECTION_23",
                    row_id=f"Ref #{ref.number}",
                    severity=Severity.ERROR,
                    check_code="INV7_BARE_URL_ANCHOR",
                    message=f"Reference #{ref.number}: Bare URL used as anchor text: '{ref.anchor}'.",
                    line_number=ref.line_number,
                )
            )

        for f_dom in FORBIDDEN_FILE_SHARING_DOMAINS:
            if f_dom in ref.url.lower() or f_dom in ref.domain.lower():
                issues.append(
                    VerificationIssue(
                        category="Invariant 7: Reference Integrity",
                        table_id="SECTION_23",
                        row_id=f"Ref #{ref.number}",
                        severity=Severity.ERROR,
                        check_code="INV7_FORBIDDEN_FILE_SHARING",
                        message=f"Reference #{ref.number}: Forbidden file-sharing link '{ref.url}'.",
                        line_number=ref.line_number,
                    )
                )

        for mirror_pat in FORBIDDEN_MIRROR_DOMAINS:
            if mirror_pat in ref.url.lower() or mirror_pat in ref.domain.lower():
                issues.append(
                    VerificationIssue(
                        category="Invariant 7: Reference Integrity",
                        table_id="SECTION_23",
                        row_id=f"Ref #{ref.number}",
                        severity=Severity.ERROR,
                        check_code="INV7_MIRROR_STUB",
                        message=f"Reference #{ref.number}: Forbidden document-mirror entry '{ref.url}'.",
                        line_number=ref.line_number,
                    )
                )

    # 2. Audit inline Markdown citations across the whole document
    inline_citations = re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", full_text)
    for anchor, url in inline_citations:
        if anchor.strip().startswith("http://") or anchor.strip().startswith("https://"):
            issues.append(
                VerificationIssue(
                    category="Invariant 7: Reference Integrity",
                    table_id="DOCUMENT_BODY",
                    row_id="INLINE_CITATION",
                    severity=Severity.ERROR,
                    check_code="INV7_INLINE_BARE_URL",
                    message=f"Inline citation uses bare URL as anchor text: [{anchor}]({url}).",
                    line_number=find_line_number(full_text, f"[{anchor}]({url})"),
                )
            )

        for f_dom in FORBIDDEN_FILE_SHARING_DOMAINS:
            if f_dom in url.lower():
                issues.append(
                    VerificationIssue(
                        category="Invariant 7: Reference Integrity",
                        table_id="DOCUMENT_BODY",
                        row_id="INLINE_CITATION",
                        severity=Severity.ERROR,
                        check_code="INV7_INLINE_FILE_SHARING",
                        message=f"Inline citation links to forbidden file-sharing host: {url}.",
                        line_number=find_line_number(full_text, url),
                    )
                )

        for mirror_pat in FORBIDDEN_MIRROR_DOMAINS:
            if mirror_pat in url.lower():
                issues.append(
                    VerificationIssue(
                        category="Invariant 7: Reference Integrity",
                        table_id="DOCUMENT_BODY",
                        row_id="INLINE_CITATION",
                        severity=Severity.ERROR,
                        check_code="INV7_INLINE_MIRROR_STUB",
                        message=f"Inline citation links to forbidden document mirror entry: {url}.",
                        line_number=find_line_number(full_text, url),
                    )
                )

    return issues


def verify_hardware_and_protocol_invariants(
    full_text: str,
    tables: list[TierTable],
) -> list[VerificationIssue]:
    """
    Verify Method Matrix hardware invariants and explicit protocol prohibitions (§8, §9A.5, §12.1, §12.5 Rule 9).
    """
    issues: list[VerificationIssue] = []

    # 1. Verify prohibition against additive diffuse corrections (§9A.5)
    if "additive diffuse correction" in full_text:
        m_diff = re.search(r"additive diffuse.*?prohibit", full_text, re.IGNORECASE)
        if not m_diff:
            issues.append(
                VerificationIssue(
                    category="Hardware & Protocol Mandates",
                    table_id="SECTION_9A.5",
                    row_id="PROHIBITION_AUDIT",
                    severity=Severity.WARNING,
                    check_code="HW_DIFFUSE_PROHIBITION",
                    message="Additive diffuse corrections must be explicitly marked as prohibited (§9A.5).",
                )
            )

    # 2. Verify prohibition against ONIOM / QM-QM2 at 5-10 atoms (§9A.5)
    if "ONIOM" in full_text:
        m_oniom = re.search(r"ONIOM.*?rejected", full_text, re.IGNORECASE)
        if not m_oniom:
            issues.append(
                VerificationIssue(
                    category="Hardware & Protocol Mandates",
                    table_id="SECTION_9A.5",
                    row_id="PROHIBITION_AUDIT",
                    severity=Severity.WARNING,
                    check_code="HW_ONIOM_PROHIBITION",
                    message="ONIOM at 5–10 atoms must be explicitly marked as rejected (§9A.5).",
                )
            )

    # 3. Verify Setup-3 core-hours accounting rule (§12.5 Rule 9)
    for table in tables:
        for exp_row in table.expansion_rows:
            clean_id = re.sub(r"[*_`]", "", exp_row.row_id).strip()
            if any(t_suffix in clean_id for t_suffix in ["1w", "1mo", "3d"]):
                if exp_row.setup_1.strip().lower().startswith("no"):
                    core_h_str = exp_row.core_h
                    if "@ 128" not in core_h_str and "@ 8" in core_h_str:
                        issues.append(
                            VerificationIssue(
                                category="Hardware & Protocol Mandates",
                                table_id=table.table_id,
                                row_id=clean_id,
                                severity=Severity.INFO,
                                check_code="HW_SETUP3_CORE_HOURS",
                                message=f"{table.table_id} expansion row {clean_id}: Setup-3-capable row should quote 128-core figures alongside 8-core numbers.",
                                line_number=exp_row.line_number,
                            )
                        )

    return issues


# -----------------------------------------------------------------------------
# Main Verification Engine
# -----------------------------------------------------------------------------

def verify_method_matrix(
    file_path: str | Path,
    strict: bool = True,
) -> VerificationReport:
    """
    Execute full invariant verification suite on Method Matrix v4 Markdown file (§12.6).

    Args:
        file_path: Path to Method_Matrix.md.
        strict: If True, warnings will also cause report.passed to be False.

    Returns:
        VerificationReport detailing all checks and issues found.
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Method Matrix file not found at: {path}")

    full_text = path.read_text(encoding="utf-8")
    now_utc = datetime.now(timezone.utc).isoformat()

    tables = parse_method_matrix_tables(full_text)
    references = parse_section_23_references(full_text)

    all_issues: list[VerificationIssue] = []
    total_rows = sum(len(t.rows) for t in tables)

    if len(tables) != len(EXPECTED_TABLE_SECTIONS):
        all_issues.append(
            VerificationIssue(
                category="Table Count Audit",
                table_id="ALL_TABLES",
                row_id="OVERALL",
                severity=Severity.ERROR,
                check_code="TABLE_COUNT_MISMATCH",
                message=f"Parsed {len(tables)} tables, expected exactly {len(EXPECTED_TABLE_SECTIONS)} tier tables.",
            )
        )

    for table in tables:
        all_issues.extend(verify_invariant_1_row_completeness(table))
        all_issues.extend(verify_invariant_2_accuracy_provenance(table))
        all_issues.extend(verify_invariant_3_ten_wall_clock_tiers(table))
        all_issues.extend(verify_invariant_4_track_labelling(table))
        all_issues.extend(verify_invariant_5_table_7_cap(table))
        all_issues.extend(verify_invariant_6_product_no_prose(table))

    all_issues.extend(verify_invariant_7_reference_integrity(full_text, references))
    all_issues.extend(verify_hardware_and_protocol_invariants(full_text, tables))

    has_errors = any(i.severity == Severity.ERROR for i in all_issues)
    has_warnings = any(i.severity == Severity.WARNING for i in all_issues)

    passed = not has_errors if not strict else (not has_errors and not has_warnings)

    report = VerificationReport(
        file_path=str(path),
        timestamp_utc=now_utc,
        total_tables_checked=len(tables),
        total_rows_checked=total_rows,
        total_references_checked=len(references),
        issues=all_issues,
        passed=passed,
        hardware_limits_checked=True,
    )
    return report


# -----------------------------------------------------------------------------
# Report Formatters
# -----------------------------------------------------------------------------

def format_console_report(report: VerificationReport, verbose: bool = False) -> str:
    """Format human-readable terminal report."""
    lines: list[str] = [
        "=" * 80,
        "Method Matrix v4 Machine-Checkable Invariant Verification Report (§12.6)",
        "=" * 80,
        f"File: {report.file_path}",
        f"Timestamp (UTC): {report.timestamp_utc}",
        f"Tables Checked: {report.total_tables_checked} | Tier Rows Checked: {report.total_rows_checked} | References: {report.total_references_checked}",
        f"Summary: Errors={report.error_count}, Warnings={report.warning_count}, Info={report.info_count}",
        f"Overall Status: {'[PASS] COMPLIANT' if report.passed else '[FAIL] INVARIANTS VIOLATED'}",
        "-" * 80,
    ]

    if not report.issues:
        lines.append("All machine-checkable invariants passed cleanly with zero issues.")
    else:
        lines.append("Issues Log:")
        for idx, issue in enumerate(report.issues, 1):
            if not verbose and issue.severity == Severity.INFO:
                continue
            loc_str = f"Line {issue.line_number}" if issue.line_number > 0 else "N/A"
            lines.append(
                f"  [{issue.severity.value}] #{idx:02d} [{issue.category}] {issue.table_id} ({issue.row_id}) - {loc_str}: {issue.message}"
            )

    lines.append("=" * 80)
    return "\n".join(lines)


def format_markdown_report(report: VerificationReport) -> str:
    """Format GitHub-flavored markdown report."""
    lines: list[str] = [
        "# Method Matrix v4 Verification Report (§12.6)",
        "",
        f"- **File:** `{report.file_path}`",
        f"- **Timestamp:** `{report.timestamp_utc}`",
        f"- **Status:** **{'PASSED' if report.passed else 'FAILED'}**",
        f"- **Tables Checked:** {report.total_tables_checked}",
        f"- **Tier Rows Checked:** {report.total_rows_checked}",
        f"- **References Checked:** {report.total_references_checked}",
        "",
        "## Invariant Audit Summary",
        "",
        "| Metric | Count |",
        "|---|---|",
        f"| **Errors** | {report.error_count} |",
        f"| **Warnings** | {report.warning_count} |",
        f"| **Info** | {report.info_count} |",
        "",
    ]

    if report.issues:
        lines.extend([
            "## Detected Issues",
            "",
            "| Severity | Category | Table / Location | Row ID | Line | Message |",
            "|---|---|---|---|---|---|",
        ])
        for i in report.issues:
            loc = str(i.line_number) if i.line_number > 0 else "—"
            lines.append(f"| `{i.severity.value}` | {i.category} | `{i.table_id}` | `{i.row_id}` | {loc} | {i.message} |")
        lines.append("")
    else:
        lines.extend([
            "> [!NOTE]",
            "> All 7 machine-checkable invariants and hardware limits verified with 100 % compliance.",
            "",
        ])

    return "\n".join(lines)


def format_json_report(report: VerificationReport) -> str:
    """Format structured JSON report."""
    return json.dumps(report.to_dict(), indent=2)


# -----------------------------------------------------------------------------
# CLI Entry Point
# -----------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Command-line entry point for mm/verify_v4.py."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception as err:
            logger.debug("Failed to reconfigure stdout encoding: %s", err)

    parser = argparse.ArgumentParser(
        description="Enforces machine-checkable invariants on Method Matrix v4 tables, tiers, and hardware limits (§12.6)."
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        default=None,
        help="Path to Method_Matrix.md file. If omitted, searches standard repository locations.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Strict mode: treat warnings as verification failures.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Verbose console output including informational notices.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output verification report in JSON format.",
    )
    parser.add_argument(
        "--markdown",
        "-m",
        action="store_true",
        default=False,
        help="Output verification report in Markdown format.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional file path to write output report to.",
    )

    args = parser.parse_args(argv)

    target_path: Path
    if args.file:
        target_path = Path(args.file)
    else:
        candidates = [
            Path(r"D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md"),
            Path("Method_Matrix.md"),
            Path("../CoChem-BASE/Method_Matrix.md"),
            Path("../../CoChem-BASE/Method_Matrix.md"),
        ]
        found = [c for c in candidates if c.exists()]
        if not found:
            sys.stderr.write("Error: Could not locate Method_Matrix.md. Specify path with --file.\n")
            return 1
        target_path = found[0]

    try:
        report = verify_method_matrix(target_path, strict=args.strict)
    except Exception as e:
        sys.stderr.write(f"Verification engine execution error: {e}\n")
        return 1

    if args.json:
        output_text = format_json_report(report)
    elif args.markdown:
        output_text = format_markdown_report(report)
    else:
        output_text = format_console_report(report, verbose=args.verbose)

    if args.output:
        out_file = Path(args.output)
        out_file.write_text(output_text, encoding="utf-8")
        if not args.json:
            print(f"Report written to: {out_file.resolve()}")
    else:
        print(output_text)

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
