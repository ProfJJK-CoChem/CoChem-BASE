"""Physical Zero-Mock Test Suite for 20360805 Method Matrix .md Refactoring.

Verifies strict Unix LF line endings, UTF-8 encoding without BOM, zero personal path leakage,
canonical token compliance, complete structural sections, Method Matrix v4 invariants,
10 domain tier tables, provenance tagging discipline ([M], [D], [E]), and formatting integrity.
"""

from __future__ import annotations

import re
from pathlib import Path
import pytest

from cochem_base.path_sanitization import (
    find_path_leaks,
)


@pytest.fixture
def method_matrix_file() -> Path:
    """Fixture providing the absolute path to the refactored 20360805 Method Matrix .md."""
    target = Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20360805 Method Matrix .md")
    if not target.exists():
        pytest.skip(f"Target file does not exist at {target}")
    return target


def test_file_exists_and_non_empty(method_matrix_file: Path) -> None:
    """Verify that the Method Matrix exists and has comprehensive content (>50 KB)."""
    stat = method_matrix_file.stat()
    assert stat.st_size > 50_000, f"File size too small ({stat.st_size} bytes)"


def test_unix_lf_line_endings(method_matrix_file: Path) -> None:
    """Verify strictly Unix LF line endings (\n) and no Windows CRLF (\r\n)."""
    with open(method_matrix_file, "rb") as f:
        raw = f.read()
    assert b"\r\n" not in raw, f"Found Windows CRLF (\r\n) line endings in {method_matrix_file.name}"
    assert b"\n" in raw, f"Missing newline characters in {method_matrix_file.name}"


def test_utf8_encoding_no_bom(method_matrix_file: Path) -> None:
    """Verify standard UTF-8 encoding without Byte Order Mark."""
    with open(method_matrix_file, "rb") as f:
        header = f.read(3)
    assert header != b"\xef\xbb\xbf", f"Found UTF-8 BOM marker in {method_matrix_file.name}"

    content = method_matrix_file.read_text(encoding="utf-8")
    assert len(content) > 0


def test_zero_personal_path_leaks(method_matrix_file: Path) -> None:
    """Verify zero personal/machine path leakage across the entire document."""
    content = method_matrix_file.read_text(encoding="utf-8")
    leaks = find_path_leaks(content)
    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s) in {method_matrix_file.name}: {leaks}"


def test_no_hardcoded_linux_user_paths(method_matrix_file: Path) -> None:
    """Verify that no un-sanitized /home/user paths exist in the document."""
    content = method_matrix_file.read_text(encoding="utf-8")
    hardcoded = re.findall(r"/home/\w+/[^\s`\(\)\"\'<>]+", content)
    assert len(hardcoded) == 0, f"Detected hardcoded Linux user paths: {hardcoded}"


def test_canonical_tokens_present(method_matrix_file: Path) -> None:
    """Verify standard path placeholder tokens are utilized."""
    content = method_matrix_file.read_text(encoding="utf-8")
    assert "<USER_HOME>" in content, "Missing canonical <USER_HOME> token"
    assert "<COCHEM_WORKSPACE>" in content, "Missing canonical <COCHEM_WORKSPACE> token"


def test_clean_markdown_no_raw_directive_xml(method_matrix_file: Path) -> None:
    """Verify that raw XML directive tags are not polluting the markdown."""
    content = method_matrix_file.read_text(encoding="utf-8")
    banned_tags = [
        "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>",
        "<SWARM_AUTONOMY_MANDATE>",
        "<ANTI_SPOOFING_COUNCIL_DIRECTIVE>",
        "<ADVERSARIAL_AUDIT_DIRECTIVE>",
        "<ROOT_CAUSE_MANDATE>",
    ]
    for tag in banned_tags:
        assert tag not in content, f"Found raw XML directive tag in {method_matrix_file.name}: {tag}"


def test_code_fence_balance(method_matrix_file: Path) -> None:
    """Verify all markdown code blocks are properly opened and closed."""
    content = method_matrix_file.read_text(encoding="utf-8")
    fences = [line for line in content.splitlines() if line.strip().startswith("```")]
    assert len(fences) % 2 == 0, f"Unbalanced code fences ({len(fences)}) in {method_matrix_file.name}"


def test_primary_sections_present(method_matrix_file: Path) -> None:
    """Verify all canonical primary numbered sections are present."""
    content = method_matrix_file.read_text(encoding="utf-8")

    required_sections = [
        "# Computational Spectroscopy and Property Prediction Regime for van der Waals Complexes",
        "## Metadata and Provenance Classification",
        "## 1. Introduction and Methodological Scope",
        "## 2. Hardware Architecture and Algorithmic Routing",
        "## 3. Fundamental Physical Corrections: Dispersion, BSSE, and Monomer Constraints",
        "## 4. Structural Regimes: PES, Isomers, and Reactions",
        "## 5. Vibrational and Rotational Spectroscopy Regimes",
        "## 6. Electronic, Magnetic, and Mass Spectrometry Regimes",
        "## 7. Overcoming Limitations and Environmental Edge Cases",
        "## 8. Works Cited",
    ]

    for sec in required_sections:
        assert sec in content, f"Missing required section in {method_matrix_file.name}: {sec}"


def test_all_ten_domain_tables_present_and_valid(method_matrix_file: Path) -> None:
    """Verify that all 10 domain tier tables exist and have consistent column counts."""
    content = method_matrix_file.read_text(encoding="utf-8")
    lines = content.splitlines()

    table_titles = [
        "**Table 1: Molecular Structure & Isomer Search**",
        "**Table 2: Potential Energy Surface & Reaction Potential Scans**",
        "**Table 3: Isomer Energy Differences & Point Energy**",
        "**Table 4: Laser-Induced Reactions (Pure Samples & Mixtures)**",
        "**Table 5: Microwave and Rotovibrational Spectroscopy**",
        "**Table 6: Infrared (IR) & THz/Far-infrared Spectroscopy**",
        "**Table 7: Raman Spectroscopy**",
        "**Table 8: Nuclear Magnetic Resonance (NMR) Spectroscopy**",
        "**Table 9: UV-Vis Spectroscopy**",
        "**Table 10: GC-MS / EI-MS Fragmentation**",
    ]

    for title in table_titles:
        assert title in content, f"Missing table title: {title}"

    # Verify column consistency across all tables (ignoring code blocks)
    current_table: list[tuple[int, int, list[str]]] = []
    tables_found = 0
    in_code_block = False

    for idx, line in enumerate(lines, start=1):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        if "|" in line:
            cols = [c.strip() for c in line.split("|")[1:-1]]
            current_table.append((idx, len(cols), cols))
        else:
            if current_table:
                header_cols = current_table[0][1]
                assert header_cols == 11, f"Table at line {current_table[0][0]} expected 11 columns, got {header_cols}"
                for row_line, row_cols, _ in current_table:
                    assert row_cols == header_cols, (
                        f"Column mismatch at line {row_line}: expected {header_cols}, got {row_cols}"
                    )
                tables_found += 1
                current_table = []

    if current_table:
        header_cols = current_table[0][1]
        assert header_cols == 11
        for row_line, row_cols, _ in current_table:
            assert row_cols == header_cols
        tables_found += 1

    assert tables_found == 10, f"Expected 10 tables, found {tables_found}"


def test_provenance_and_method_matrix_invariants(method_matrix_file: Path) -> None:
    """Verify core Method Matrix scientific, computational, and physical invariants."""
    content = method_matrix_file.read_text(encoding="utf-8")

    # Provenance tags
    assert "[M]" in content, "Missing [M] measured provenance tag"
    assert "[D]" in content, "Missing [D] derived provenance tag"
    assert "[E]" in content, "Missing [E] estimated provenance tag"

    # Hessian & Grid invariants
    assert "InHess XTB2" in content
    assert "DefGrid3" in content
    assert "DefGrid4" in content
    assert "TightSCF" in content
    assert "TolMaxG 1e-5" in content

    # Method & Hardware rules
    assert "Frozen-Monomer" in content or "frozen-monomer" in content.lower()
    assert "D4" in content
    assert "Counterpoise" in content
    assert "MACE" in content
    assert "AIMNet2" in content
    assert "g-xTB" in content
    assert "DLPNO-CCSD(T)" in content
    assert "F12-CCSD(T)" in content
    assert "STEOM-CCSD" in content
    assert "QCxMS" in content
    assert "ORCA 6.1" in content


def test_works_cited_citations_hyperlinked(method_matrix_file: Path) -> None:
    """Verify that references in Section 8 are properly formatted as markdown hyperlinks."""
    content = method_matrix_file.read_text(encoding="utf-8")
    assert "## 8. Works Cited" in content
    works_cited_text = content.split("## 8. Works Cited")[1]
    links = re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", works_cited_text)
    assert len(links) >= 40, f"Expected at least 40 hyperlinked references, found {len(links)}"
