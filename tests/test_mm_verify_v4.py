"""
CoChem Unit and Validation Test Suite: Method Matrix v4 Verification Engine.

Tests mm/verify_v4.py against all machine-checkable invariants and hardware mandates:
  - Invariant 1 (§12.6, §12.3): Row completeness (Row ID, Concurrency tag, Limitations cell).
  - Invariant 2 (§12.6, §12.5 Rules 7 & 8): Standard physical quantities and authoritative provenance tags [M]/[D]/[E].
  - Invariant 3 (§12.6, §12.3): Exactly 10 wall-clock tiers in canonical ascending ladder.
  - Invariant 4 (§12.6, §12.2): Explicit track labelling (Single track or dual ORCA/CFOUR tracks).
  - Invariant 5 (§12.6, §14.2): Table 7 ±14 % benchmark cap enforcement on V3 barrier.
  - Invariant 6 (§12.6, §12.3, §1.2): Product cell prose ban (strictly letter tags A/B/C/combinations).
  - Invariant 7 (§12.6, §23): Reference integrity (no bare URLs, no file-sharing hosts, no mirror stubs).
  - Hardware & Protocol Mandates: Prohibitions on additive diffuse corrections, ONIOM, and Setup-3 core-h tracking.
  - Full parsers, report formatters, CLI entry points, and live validation of Method_Matrix.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mm.verify_v4 import (
    CANONICAL_TIERS,
    EXPECTED_TABLE_SECTIONS,
    FORBIDDEN_FILE_SHARING_DOMAINS,
    FORBIDDEN_MIRROR_DOMAINS,
    VALID_CONCURRENCY_TAGS,
    VALID_PRODUCT_TAGS,
    ExpansionRow,
    ReferenceItem,
    Severity,
    TierRow,
    TierTable,
    VerificationIssue,
    VerificationReport,
    find_line_number,
    format_console_report,
    format_json_report,
    format_markdown_report,
    main,
    parse_method_matrix_tables,
    parse_section_23_references,
    verify_hardware_and_protocol_invariants,
    verify_invariant_1_row_completeness,
    verify_invariant_2_accuracy_provenance,
    verify_invariant_3_ten_wall_clock_tiers,
    verify_invariant_4_track_labelling,
    verify_invariant_5_table_7_cap,
    verify_invariant_6_product_no_prose,
    verify_invariant_7_reference_integrity,
    verify_method_matrix,
)


def get_authoritative_method_matrix_path() -> Path:
    """Locate the authoritative Method_Matrix.md file in the workspace."""
    candidates = [
        Path(r"D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md"),
        Path(__file__).resolve().parent.parent / "Method_Matrix.md",
        Path("Method_Matrix.md"),
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()
    raise FileNotFoundError("Could not find Method_Matrix.md in standard locations.")


# =============================================================================
# 1. Constants & Catalog Invariants
# =============================================================================

def test_canonical_tiers_definition() -> None:
    """Verify canonical tier list definition matching Method Matrix §12.3."""
    expected = ["10 s", "1 min", "30 min", "1 h", "3 h", "12 h", "1 d", "3 d", "1 w", "1 mo"]
    assert CANONICAL_TIERS == expected
    assert len(CANONICAL_TIERS) == 10


def test_valid_concurrency_and_product_tags() -> None:
    """Verify concurrency and product tags recognized by the verification engine."""
    assert "C" in VALID_CONCURRENCY_TAGS
    assert "G" in VALID_CONCURRENCY_TAGS
    assert "P" in VALID_CONCURRENCY_TAGS
    assert "S" in VALID_CONCURRENCY_TAGS
    assert "A" in VALID_PRODUCT_TAGS
    assert "B" in VALID_PRODUCT_TAGS
    assert "C" in VALID_PRODUCT_TAGS
    assert "A, B" in VALID_PRODUCT_TAGS


def test_forbidden_domains_and_mirrors() -> None:
    """Verify forbidden file-sharing hosts and mirror domains lists are populated."""
    assert "drive.google.com" in FORBIDDEN_FILE_SHARING_DOMAINS
    assert "dropbox.com" in FORBIDDEN_FILE_SHARING_DOMAINS
    assert "mega.nz" in FORBIDDEN_FILE_SHARING_DOMAINS
    assert "sci-hub" in FORBIDDEN_MIRROR_DOMAINS
    assert "libgen" in FORBIDDEN_MIRROR_DOMAINS


def test_expected_table_sections_catalog() -> None:
    """Verify all 14 expected table sections are defined with correct track types."""
    assert len(EXPECTED_TABLE_SECTIONS) == 14

    single_track_tables = [t["table_id"] for t in EXPECTED_TABLE_SECTIONS if t["track_type"] == "single"]
    orca_track_tables = [t["table_id"] for t in EXPECTED_TABLE_SECTIONS if t["track_type"] == "orca"]
    cfour_track_tables = [t["table_id"] for t in EXPECTED_TABLE_SECTIONS if t["track_type"] == "cfour"]

    assert single_track_tables == ["Table 1", "Table 2", "Table 5", "Table 7", "Table 9", "Table 10"]
    assert orca_track_tables == ["Table 3-O", "Table 4-O", "Table 6-O", "Table 8-O"]
    assert cfour_track_tables == ["Table 3-C", "Table 4-C", "Table 6-C", "Table 8-C"]


# =============================================================================
# 2. Invariant 1: Row Completeness (§12.6, §12.3)
# =============================================================================

def test_invariant_1_valid_row() -> None:
    """Verify Invariant 1 passes a fully compliant row with non-empty fields."""
    valid_row = TierRow(
        table_id="Table 1",
        row_id="**T1-10s**",
        tier="10 s",
        method_code="GFN2-xTB",
        delivers_accuracy="an ensemble of 3–9 seeds",
        concurrency_tag="C",
        product="A",
        limitations="no search at all; a topology missed by hand is invisible",
        raw_markdown="| **T1-10s** | 10 s | GFN2-xTB | an ensemble of 3–9 seeds | C | A | no search at all |",
        line_number=10,
    )
    table = TierTable(
        table_id="Table 1",
        title="Conformer and isomer search",
        track_type="single",
        expected_code_track="ORCA",
        section_text="",
        rows=[valid_row],
    )
    issues = verify_invariant_1_row_completeness(table)
    error_issues = [i for i in issues if i.severity == Severity.ERROR]
    assert len(error_issues) == 0


def test_invariant_1_empty_row_id() -> None:
    """Verify Invariant 1 flags empty or placeholder Row IDs."""
    bad_row = TierRow(
        table_id="Table 1",
        row_id="",
        tier="10 s",
        method_code="GFN2-xTB",
        delivers_accuracy="ensemble",
        concurrency_tag="C",
        product="A",
        limitations="none",
        raw_markdown="",
    )
    table = TierTable(
        table_id="Table 1",
        title="Test",
        track_type="single",
        expected_code_track="ORCA",
        section_text="",
        rows=[bad_row],
    )
    issues = verify_invariant_1_row_completeness(table)
    assert any(i.check_code == "INV1_EMPTY_ROW_ID" for i in issues)


def test_invariant_1_empty_and_unusual_concurrency() -> None:
    """Verify Invariant 1 flags empty concurrency tags and warns on unusual concurrency."""
    bad_conc_empty = TierRow(
        table_id="Table 1",
        row_id="T1-1min",
        tier="1 min",
        method_code="GFN2-xTB",
        delivers_accuracy="ensemble",
        concurrency_tag="",
        product="A",
        limitations="limited",
        raw_markdown="",
    )
    bad_conc_unusual = TierRow(
        table_id="Table 1",
        row_id="T1-30min",
        tier="30 min",
        method_code="GFN2-xTB",
        delivers_accuracy="ensemble",
        concurrency_tag="XYZ_UNKNOWN",
        product="A",
        limitations="limited",
        raw_markdown="",
    )
    table = TierTable(
        table_id="Table 1",
        title="Test",
        track_type="single",
        expected_code_track="ORCA",
        section_text="",
        rows=[bad_conc_empty, bad_conc_unusual],
    )
    issues = verify_invariant_1_row_completeness(table)
    codes = [i.check_code for i in issues]
    assert "INV1_EMPTY_CONCURRENCY" in codes
    assert "INV1_UNUSUAL_CONCURRENCY" in codes


def test_invariant_1_empty_and_placeholder_limitations() -> None:
    """Verify Invariant 1 flags completely empty limitations or bare dashes on active rows."""
    bad_lim_empty = TierRow(
        table_id="Table 1",
        row_id="T1-1h",
        tier="1 h",
        method_code="GFN2-xTB",
        delivers_accuracy="ensemble",
        concurrency_tag="C",
        product="A",
        limitations="",
        raw_markdown="",
    )
    bad_lim_dash = TierRow(
        table_id="Table 1",
        row_id="T1-3h",
        tier="3 h",
        method_code="GFN2-xTB",
        delivers_accuracy="ensemble",
        concurrency_tag="C",
        product="A",
        limitations="—",
        raw_markdown="",
    )
    table = TierTable(
        table_id="Table 1",
        title="Test",
        track_type="single",
        expected_code_track="ORCA",
        section_text="",
        rows=[bad_lim_empty, bad_lim_dash],
    )
    issues = verify_invariant_1_row_completeness(table)
    codes = [i.check_code for i in issues]
    assert "INV1_EMPTY_LIMITATIONS" in codes
    assert "INV1_PLACEHOLDER_LIMITATIONS" in codes


# =============================================================================
# 3. Invariant 2: Accuracy & Provenance (§12.6, §12.5 Rules 7 & 8)
# =============================================================================

def test_invariant_2_accuracy_provenance_valid() -> None:
    """Verify Invariant 2 passes rows with recognized physical quantities and [M]/[D]/[E] provenance."""
    valid_row = TierRow(
        table_id="Table 3-O",
        row_id="T3O-10s",
        tier="10 s",
        method_code="GFN2-xTB",
        delivers_accuracy="**B_e ±3–15 % `[M]`**",
        concurrency_tag="C",
        product="A",
        limitations="systematic error",
        raw_markdown="",
    )
    table = TierTable(
        table_id="Table 3-O",
        title="Test",
        track_type="orca",
        expected_code_track="ORCA",
        section_text="",
        rows=[valid_row],
    )
    issues = verify_invariant_2_accuracy_provenance(table)
    assert len([i for i in issues if i.severity == Severity.ERROR]) == 0


def test_invariant_2_missing_provenance_on_numeric_bound() -> None:
    """Verify Invariant 2 flags numeric accuracy claims lacking [M]/[D]/[E] tags."""
    bad_prov_row = TierRow(
        table_id="Table 3-O",
        row_id="T3O-1min",
        tier="1 min",
        method_code="r2SCAN-3c",
        delivers_accuracy="**B_e ±1.5 %**",
        concurrency_tag="C",
        product="A",
        limitations="limited",
        raw_markdown="",
    )
    table = TierTable(
        table_id="Table 3-O",
        title="Test",
        track_type="orca",
        expected_code_track="ORCA",
        section_text="",
        rows=[bad_prov_row],
    )
    issues = verify_invariant_2_accuracy_provenance(table)
    assert any(i.check_code == "INV2_MISSING_PROVENANCE_TAG" for i in issues)


def test_invariant_2_track_gap_exemption() -> None:
    """Verify Invariant 2 properly exempts genuine track gap rows."""
    gap_row = TierRow(
        table_id="Table 3-C",
        row_id="T3C-10s",
        tier="10 s",
        method_code="—",
        delivers_accuracy="—",
        concurrency_tag="—",
        product="—",
        limitations="Cannot fill at 10 s: CFOUR binary start-up overhead exceeds 10 s.",
        raw_markdown="",
    )
    table = TierTable(
        table_id="Table 3-C",
        title="Test",
        track_type="cfour",
        expected_code_track="CFOUR",
        section_text="",
        rows=[gap_row],
    )
    issues = verify_invariant_2_accuracy_provenance(table)
    assert len(issues) == 0


def test_invariant_2_unnamed_quantity_warning() -> None:
    """Verify Invariant 2 warns when delivers cell mentions no recognized physical quantity."""
    unnamed_row = TierRow(
        table_id="Table 1",
        row_id="T1-10s",
        tier="10 s",
        method_code="Custom",
        delivers_accuracy="Some completely unrecognized arbitrary claim",
        concurrency_tag="C",
        product="A",
        limitations="limited",
        raw_markdown="",
    )
    table = TierTable(
        table_id="Table 1",
        title="Test",
        track_type="single",
        expected_code_track="ORCA",
        section_text="",
        rows=[unnamed_row],
    )
    issues = verify_invariant_2_accuracy_provenance(table)
    assert any(i.check_code == "INV2_UNNAMED_QUANTITY" for i in issues)


# =============================================================================
# 4. Invariant 3: Ten Wall-Clock Tiers (§12.6, §12.3)
# =============================================================================

def test_invariant_3_ten_wall_clock_tiers_valid() -> None:
    """Verify Invariant 3 passes exactly 10 rows in canonical order."""
    rows = [
        TierRow(
            table_id="Table 1",
            row_id=f"T1-{t.replace(' ', '')}",
            tier=t,
            method_code="M",
            delivers_accuracy="ensemble",
            concurrency_tag="C",
            product="A",
            limitations="L",
            raw_markdown="",
        )
        for t in CANONICAL_TIERS
    ]
    table = TierTable(
        table_id="Table 1",
        title="Test",
        track_type="single",
        expected_code_track="ORCA",
        section_text="",
        rows=rows,
    )
    issues = verify_invariant_3_ten_wall_clock_tiers(table)
    assert len(issues) == 0


def test_invariant_3_row_count_mismatch() -> None:
    """Verify Invariant 3 flags tables with non-10 row count."""
    rows_5 = [
        TierRow(
            table_id="Table 1",
            row_id=f"T1-{t.replace(' ', '')}",
            tier=t,
            method_code="M",
            delivers_accuracy="ensemble",
            concurrency_tag="C",
            product="A",
            limitations="L",
            raw_markdown="",
        )
        for t in CANONICAL_TIERS[:5]
    ]
    table = TierTable(
        table_id="Table 1",
        title="Test",
        track_type="single",
        expected_code_track="ORCA",
        section_text="",
        rows=rows_5,
    )
    issues = verify_invariant_3_ten_wall_clock_tiers(table)
    assert any(i.check_code == "INV3_ROW_COUNT_MISMATCH" for i in issues)


def test_invariant_3_tier_sequence_mismatch() -> None:
    """Verify Invariant 3 flags out-of-order or invalid tier strings."""
    corrupted_tiers = list(CANONICAL_TIERS)
    corrupted_tiers[1] = "2 min"  # Invalid tier, should be 1 min
    rows = [
        TierRow(
            table_id="Table 1",
            row_id=f"T1-{t.replace(' ', '')}",
            tier=t,
            method_code="M",
            delivers_accuracy="ensemble",
            concurrency_tag="C",
            product="A",
            limitations="L",
            raw_markdown="",
        )
        for t in corrupted_tiers
    ]
    table = TierTable(
        table_id="Table 1",
        title="Test",
        track_type="single",
        expected_code_track="ORCA",
        section_text="",
        rows=rows,
    )
    issues = verify_invariant_3_ten_wall_clock_tiers(table)
    assert any(i.check_code == "INV3_TIER_SEQUENCE_MISMATCH" for i in issues)


# =============================================================================
# 5. Invariant 4: Track Labelling (§12.6, §12.2)
# =============================================================================

def test_invariant_4_track_labelling() -> None:
    """Verify Invariant 4 checks track headings and row ID formats."""
    # Missing ORCA track label
    table_orca_bad = TierTable(
        table_id="Table 3-O",
        title="Equilibrium geometry",
        track_type="orca",
        expected_code_track="ORCA",
        section_text="#### Table 3-O — Equilibrium geometry",
        rows=[],
    )
    issues_orca = verify_invariant_4_track_labelling(table_orca_bad)
    assert any(i.check_code == "INV4_MISSING_ORCA_TRACK_LABEL" for i in issues_orca)

    # Missing CFOUR track label
    table_cfour_bad = TierTable(
        table_id="Table 3-C",
        title="Equilibrium geometry",
        track_type="cfour",
        expected_code_track="CFOUR",
        section_text="#### Table 3-C — Equilibrium geometry",
        rows=[],
    )
    issues_cfour = verify_invariant_4_track_labelling(table_cfour_bad)
    assert any(i.check_code == "INV4_MISSING_CFOUR_TRACK_LABEL" for i in issues_cfour)

    # Missing single track label
    table_single_bad = TierTable(
        table_id="Table 1",
        title="Conformer",
        track_type="single",
        expected_code_track="ORCA",
        section_text="### 13.1 Table 1 — Conformer and isomer search",
        rows=[],
    )
    issues_single = verify_invariant_4_track_labelling(table_single_bad)
    assert any(i.check_code == "INV4_MISSING_SINGLE_TRACK_LABEL" for i in issues_single)


# =============================================================================
# 6. Invariant 5: Table 7 ±14 % Benchmark Cap (§12.6, §14.2)
# =============================================================================

def test_invariant_5_table_7_cap() -> None:
    """Verify Invariant 5 enforces the ±14 % cap on Table 7 V3 barrier claims."""
    # Overclaim: claiming ±5 % on V3
    overclaim_row = TierRow(
        table_id="Table 7",
        row_id="T7-30min",
        tier="30 min",
        method_code="r2SCAN-3c",
        delivers_accuracy="**V₃ ±5 % `[M]`**, one-dimensional",
        concurrency_tag="P",
        product="A",
        limitations="limited",
        raw_markdown="",
    )
    table_bad = TierTable(
        table_id="Table 7",
        title="Internal rotation",
        track_type="single",
        expected_code_track="ORCA",
        section_text="",
        rows=[overclaim_row],
    )
    issues_bad = verify_invariant_5_table_7_cap(table_bad)
    assert any(i.check_code == "INV5_TABLE_7_OVERCLAIM" for i in issues_bad)

    # Valid claim: ±14 %
    valid_row = TierRow(
        table_id="Table 7",
        row_id="T7-30min",
        tier="30 min",
        method_code="r2SCAN-3c",
        delivers_accuracy="**V₃ ±14 % `[M]`**, one-dimensional",
        concurrency_tag="P",
        product="A",
        limitations="limited",
        raw_markdown="",
    )
    table_good = TierTable(
        table_id="Table 7",
        title="Internal rotation",
        track_type="single",
        expected_code_track="ORCA",
        section_text="",
        rows=[valid_row],
    )
    issues_good = verify_invariant_5_table_7_cap(table_good)
    assert len(issues_good) == 0


# =============================================================================
# 7. Invariant 6: Product Cell Prose Ban (§12.6, §12.3, §1.2)
# =============================================================================

def test_invariant_6_product_no_prose() -> None:
    """Verify Invariant 6 strictly bans narrative prose paragraphs in Product cells."""
    for tag in ["A", "B", "C", "A, B", "A/B", "B/C", "A/C", "A (de novo)", "B (template)", "C (diff)", "—"]:
        row = TierRow(
            table_id="Table 1",
            row_id="T1-10s",
            tier="10 s",
            method_code="M",
            delivers_accuracy="D",
            concurrency_tag="C",
            product=tag,
            limitations="L",
            raw_markdown="",
        )
        tbl = TierTable(table_id="Table 1", title="", track_type="single", expected_code_track="ORCA", section_text="", rows=[row])
        assert len([i for i in verify_invariant_6_product_no_prose(tbl) if i.severity == Severity.ERROR]) == 0

    prose_row = TierRow(
        table_id="Table 1",
        row_id="T1-10s",
        tier="10 s",
        method_code="M",
        delivers_accuracy="D",
        concurrency_tag="C",
        product="This produces product A because it is generated de novo using heuristic search",
        limitations="L",
        raw_markdown="",
    )
    tbl_prose = TierTable(table_id="Table 1", title="", track_type="single", expected_code_track="ORCA", section_text="", rows=[prose_row])
    issues_prose = verify_invariant_6_product_no_prose(tbl_prose)
    assert any(i.check_code == "INV6_PRODUCT_CONTAINS_PROSE" for i in issues_prose)


# =============================================================================
# 8. Invariant 7: Reference Integrity (§12.6, §23)
# =============================================================================

def test_invariant_7_reference_integrity() -> None:
    """Verify Invariant 7 catches bare URLs, forbidden file-sharing hosts, and mirror stubs."""
    # Bare URL anchor
    ref_bare = ReferenceItem(
        number=1,
        anchor="https://example.com/paper",
        url="https://example.com/paper",
        domain="example.com",
        raw_markdown="1. [https://example.com/paper](https://example.com/paper) — example.com",
        line_number=1,
    )
    issues_bare = verify_invariant_7_reference_integrity("", [ref_bare])
    assert any(i.check_code == "INV7_BARE_URL_ANCHOR" for i in issues_bare)

    # Forbidden file sharing host (Google Drive)
    ref_sharing = ReferenceItem(
        number=2,
        anchor="Dataset Link",
        url="https://drive.google.com/file/d/12345/view",
        domain="drive.google.com",
        raw_markdown="2. [Dataset Link](https://drive.google.com/file/d/12345/view) — drive.google.com",
        line_number=2,
    )
    issues_sharing = verify_invariant_7_reference_integrity("", [ref_sharing])
    assert any(i.check_code == "INV7_FORBIDDEN_FILE_SHARING" for i in issues_sharing)

    # Document mirror stub (Sci-Hub)
    ref_mirror = ReferenceItem(
        number=3,
        anchor="Mirror Paper",
        url="https://sci-hub.se/10.1000/182",
        domain="sci-hub.se",
        raw_markdown="3. [Mirror Paper](https://sci-hub.se/10.1000/182) — sci-hub.se",
        line_number=3,
    )
    issues_mirror = verify_invariant_7_reference_integrity("", [ref_mirror])
    assert any(i.check_code == "INV7_MIRROR_STUB" for i in issues_mirror)

    # Inline citations
    inline_text = (
        "See [https://bad.com](https://bad.com) and "
        "[Dropbox](https://dropbox.com/s/12345) and "
        "[Libgen](https://libgen.is/book/123)."
    )
    issues_inline = verify_invariant_7_reference_integrity(inline_text, [])
    inline_codes = [i.check_code for i in issues_inline]
    assert "INV7_INLINE_BARE_URL" in inline_codes
    assert "INV7_INLINE_FILE_SHARING" in inline_codes
    assert "INV7_INLINE_MIRROR_STUB" in inline_codes


# =============================================================================
# 9. Hardware & Protocol Mandates (§8, §9A.5, §12.1, §12.5 Rule 9)
# =============================================================================

def test_hardware_and_protocol_invariants() -> None:
    """Verify hardware mandate checks for diffuse corrections, ONIOM, and Setup-3 core-hours."""
    text_bad_diffuse = "This tier utilizes additive diffuse corrections for dispersion."
    issues_bad_diff = verify_hardware_and_protocol_invariants(text_bad_diffuse, [])
    assert any(i.check_code == "HW_DIFFUSE_PROHIBITION" for i in issues_bad_diff)

    text_bad_oniom = "This tier implements ONIOM multi-layer partition."
    issues_bad_oniom = verify_hardware_and_protocol_invariants(text_bad_oniom, [])
    assert any(i.check_code == "HW_ONIOM_PROHIBITION" for i in issues_bad_oniom)

    text_clean = (
        "Additive diffuse corrections are strictly prohibited (§9A.5). "
        "ONIOM at 5–10 atoms is rejected (§9A.5)."
    )
    issues_clean = verify_hardware_and_protocol_invariants(text_clean, [])
    assert len([i for i in issues_clean if i.severity in (Severity.ERROR, Severity.WARNING)]) == 0

    table_setup3 = TierTable(
        table_id="Table 1",
        title="Conformer",
        track_type="single",
        expected_code_track="ORCA",
        section_text="",
        expansion_rows=[
            ExpansionRow(
                table_id="Table 1",
                row_id="T1-1w",
                core_h="500 h @ 8 cores",
                input_workflow="",
                state_in="",
                state_out="",
                frozen_mono="",
                mem_scratch="",
                licence="",
                setup_1="No",
                max_benchmark_error="",
                mitigation_notes="",
                raw_markdown="",
            )
        ],
    )
    issues_setup3 = verify_hardware_and_protocol_invariants("", [table_setup3])
    assert any(i.check_code == "HW_SETUP3_CORE_HOURS" for i in issues_setup3)


# =============================================================================
# 10. Document Parsers & Line Number Utilities
# =============================================================================

def test_find_line_number_utility() -> None:
    """Verify 1-indexed line number lookup helper."""
    text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
    assert find_line_number(text, "Line 1") == 1
    assert find_line_number(text, "Line 3") == 3
    assert find_line_number(text, "Line 5") == 5
    assert find_line_number(text, "Nonexistent") == 0


def test_parse_method_matrix_tables_and_references() -> None:
    """Verify table and reference parsers against the authoritative Method_Matrix.md."""
    mm_path = get_authoritative_method_matrix_path()
    full_text = mm_path.read_text(encoding="utf-8")

    tables = parse_method_matrix_tables(full_text)
    assert len(tables) == 14
    total_rows = sum(len(t.rows) for t in tables)
    assert total_rows == 140
    for tbl in tables:
        assert len(tbl.rows) == 10
        assert tbl.table_id in [s["table_id"] for s in EXPECTED_TABLE_SECTIONS]

    references = parse_section_23_references(full_text)
    assert len(references) == 319
    for ref in references:
        assert ref.number >= 1
        assert ref.anchor
        assert ref.url.startswith("http://") or ref.url.startswith("https://")
        assert ref.domain


# =============================================================================
# 11. Dataclass Methods & Report Formatters
# =============================================================================

def test_dataclass_methods_and_serialization() -> None:
    """Verify dataclass property methods and serialization dictionaries."""
    row = TierRow(
        table_id="Table 1",
        row_id="**`T1-10s`**",
        tier="10 s",
        method_code="GFN2-xTB",
        delivers_accuracy="ensemble",
        concurrency_tag="*`C`*",
        product="**A**",
        limitations="none",
        raw_markdown="",
    )
    assert row.clean_row_id == "T1-10s"
    assert row.clean_concurrency == "C"
    assert row.clean_product == "A"

    issue = VerificationIssue(
        category="Test Category",
        table_id="Table 1",
        row_id="T1-10s",
        severity=Severity.ERROR,
        check_code="TEST_CODE",
        message="Test error message",
        line_number=42,
    )
    issue_dict = issue.to_dict()
    assert issue_dict["category"] == "Test Category"
    assert issue_dict["severity"] == "ERROR"
    assert issue_dict["check_code"] == "TEST_CODE"
    assert issue_dict["line_number"] == 42


def test_report_formatters() -> None:
    """Verify Console, Markdown, and JSON report formatters."""
    report = VerificationReport(
        file_path="Method_Matrix.md",
        timestamp_utc="2026-08-28T00:00:00Z",
        total_tables_checked=14,
        total_rows_checked=140,
        total_references_checked=319,
        issues=[
            VerificationIssue(
                category="Invariant 1: Row Completeness",
                table_id="Table 1",
                row_id="T1-10s",
                severity=Severity.INFO,
                check_code="INFO_TEST",
                message="Test info message",
                line_number=100,
            )
        ],
        passed=True,
    )
    assert report.error_count == 0
    assert report.warning_count == 0
    assert report.info_count == 1

    console_out = format_console_report(report, verbose=True)
    assert "Method Matrix v4 Machine-Checkable Invariant Verification Report" in console_out
    assert "[PASS] COMPLIANT" in console_out
    assert "Test info message" in console_out

    md_out = format_markdown_report(report)
    assert "# Method Matrix v4 Verification Report" in md_out
    assert "PASSED" in md_out
    assert "Test info message" in md_out

    json_out = format_json_report(report)
    parsed = json.loads(json_out)
    assert parsed["passed"] is True
    assert parsed["total_tables_checked"] == 14
    assert parsed["total_rows_checked"] == 140
    assert parsed["total_references_checked"] == 319


# =============================================================================
# 12. CLI Execution & Edge Cases
# =============================================================================

def test_verify_method_matrix_nonexistent_file_raises() -> None:
    """Verify verify_method_matrix raises FileNotFoundError on missing file."""
    nonexistent = Path("nonexistent_matrix_file_xyz_123.md")
    with pytest.raises(FileNotFoundError):
        verify_method_matrix(nonexistent)


def test_cli_main_execution(tmp_path: Path) -> None:
    """Verify CLI main entry point with various flags including output file writing."""
    mm_path = get_authoritative_method_matrix_path()

    # Standard run
    exit_code = main(["--file", str(mm_path)])
    assert exit_code == 0

    # JSON mode
    exit_code_json = main(["--file", str(mm_path), "--json"])
    assert exit_code_json == 0

    # Markdown mode
    exit_code_md = main(["--file", str(mm_path), "--markdown"])
    assert exit_code_md == 0

    # Output to file
    out_file = tmp_path / "verification_report.md"
    exit_code_out = main(["--file", str(mm_path), "--markdown", "--output", str(out_file)])
    assert exit_code_out == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "# Method Matrix v4 Verification Report" in content

    # Default discovery and verbose mode
    exit_code_verbose = main(["--verbose"])
    assert exit_code_verbose == 0


def test_invariant_4_row_id_format_warnings() -> None:
    """Verify Invariant 4 warns on unusual Row ID formats in dual tracks."""
    orca_row = TierRow(
        table_id="Table 3-O",
        row_id="BAD_ID",
        tier="10 s",
        method_code="M",
        delivers_accuracy="D",
        concurrency_tag="C",
        product="A",
        limitations="L",
        raw_markdown="",
    )
    tbl_orca = TierTable(
        table_id="Table 3-O",
        title="Equilibrium geometry — ORCA track",
        track_type="orca",
        expected_code_track="ORCA",
        section_text="#### Table 3-O — Equilibrium geometry and B_e — ORCA track",
        rows=[orca_row],
    )
    issues_o = verify_invariant_4_track_labelling(tbl_orca)
    assert any(i.check_code == "INV4_ORCA_ROW_ID_FORMAT" for i in issues_o)

    cfour_row = TierRow(
        table_id="Table 3-C",
        row_id="BAD_ID",
        tier="10 s",
        method_code="M",
        delivers_accuracy="D",
        concurrency_tag="C",
        product="A",
        limitations="L",
        raw_markdown="",
    )
    tbl_cfour = TierTable(
        table_id="Table 3-C",
        title="Equilibrium geometry — CFOUR track",
        track_type="cfour",
        expected_code_track="CFOUR",
        section_text="#### Table 3-C — Equilibrium geometry and B_e — CFOUR track",
        rows=[cfour_row],
    )
    issues_c = verify_invariant_4_track_labelling(tbl_cfour)
    assert any(i.check_code == "INV4_CFOUR_ROW_ID_FORMAT" for i in issues_c)


def test_invariant_6_nonstandard_product_tag() -> None:
    """Verify Invariant 6 warns on non-standard product tags that are not prose."""
    row = TierRow(
        table_id="Table 1",
        row_id="T1-10s",
        tier="10 s",
        method_code="M",
        delivers_accuracy="D",
        concurrency_tag="C",
        product="UNKNOWN_TAG",
        limitations="L",
        raw_markdown="",
    )
    tbl = TierTable(table_id="Table 1", title="", track_type="single", expected_code_track="ORCA", section_text="", rows=[row])
    issues = verify_invariant_6_product_no_prose(tbl)
    assert any(i.check_code == "INV6_NONSTANDARD_PRODUCT_TAG" for i in issues)


def test_invariant_7_section_23_empty_references_error() -> None:
    """Verify Invariant 7 flags an error if Section 23 header exists but no references parsed."""
    issues = verify_invariant_7_reference_integrity("## 23. References\n\nNo formatted references here.", [])
    assert any(i.check_code == "INV7_NO_REFERENCES_PARSED" for i in issues)


def test_report_formatters_no_issues() -> None:
    """Verify report formatting when there are zero issues."""
    report = VerificationReport(
        file_path="Method_Matrix.md",
        timestamp_utc="2026-08-28T00:00:00Z",
        total_tables_checked=14,
        total_rows_checked=140,
        total_references_checked=319,
        issues=[],
        passed=True,
    )
    console_out = format_console_report(report, verbose=False)
    assert "All machine-checkable invariants passed cleanly with zero issues." in console_out

    md_out = format_markdown_report(report)
    assert "All 7 machine-checkable invariants and hardware limits verified with 100 % compliance." in md_out


# =============================================================================
# 13. Full Physical Live Validation
# =============================================================================

def test_method_matrix_live_verification_standard() -> None:
    """Verify that the authoritative Method_Matrix.md passes all invariants (standard mode)."""
    mm_path = get_authoritative_method_matrix_path()
    report = verify_method_matrix(mm_path, strict=False)

    assert report.passed is True
    assert report.error_count == 0
    assert report.total_tables_checked == 14
    assert report.total_rows_checked == 140
    assert report.total_references_checked == 319


def test_method_matrix_live_verification_strict() -> None:
    """Verify that the authoritative Method_Matrix.md passes strict mode with zero errors and zero warnings."""
    mm_path = get_authoritative_method_matrix_path()
    report = verify_method_matrix(mm_path, strict=True)

    assert report.passed is True
    assert report.error_count == 0
    assert report.warning_count == 0

