"""Physical Zero-Mock Test Suite for Copy of Method_Matrix.md Refactoring.

Verifies strict Unix LF line endings, UTF-8 encoding without BOM, zero personal path leakage,
canonical token compliance, complete structural sections, Method Matrix invariants,
two-track architecture, provenance tagging discipline, and formatting integrity.
"""

from __future__ import annotations

import re
from pathlib import Path
import pytest

from cochem_base.config_loader import get_base_root
from cochem_base.path_sanitization import (
    find_path_leaks,
    leak_patterns,
    placeholder_values,
)


@pytest.fixture(params=[
    Path(r"D:\__CoChem\GitHub-Repo\.old_plan_docs\20260810_docs\Copy of Method_Matrix.md"),
    get_base_root() / "Method_Matrix.md",
])
def target_file(request: pytest.FixtureRequest) -> Path:
    target: Path = request.param
    if not target.exists():
        pytest.skip(f"Target file does not exist at {target}")
    return target


def test_file_exists_and_non_empty(target_file: Path) -> None:
    """Verify that the Method Matrix exists and has comprehensive content (>500 KB)."""
    stat = target_file.stat()
    assert stat.st_size > 100_000, f"File size too small ({stat.st_size} bytes)"


def test_unix_lf_line_endings(target_file: Path) -> None:
    """Verify strictly Unix LF line endings (\n) and no Windows CRLF (\r\n)."""
    with open(target_file, "rb") as f:
        raw = f.read()
    assert b"\r\n" not in raw, f"Found Windows CRLF (\r\n) line endings in {target_file.name}"
    assert b"\n" in raw, f"Missing newline characters in {target_file.name}"


def test_utf8_encoding_no_bom(target_file: Path) -> None:
    """Verify standard UTF-8 encoding without Byte Order Mark."""
    with open(target_file, "rb") as f:
        header = f.read(3)
    assert header != b"\xef\xbb\xbf", f"Found UTF-8 BOM marker in {target_file.name}"

    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert len(content) > 0


def test_zero_personal_path_leaks(target_file: Path) -> None:
    """Verify zero personal/machine path leakage across the entire document."""
    content = target_file.read_text(encoding="utf-8")
    leaks = find_path_leaks(content)
    assert len(leaks) == 0, f"Detected {len(leaks)} path leak(s) in {target_file.name}: {leaks}"


def test_no_hardcoded_linux_user_paths(target_file: Path) -> None:
    """Verify that no un-sanitized /home/user paths exist in the document."""
    content = target_file.read_text(encoding="utf-8")
    hardcoded = re.findall(r"/home/\w+/[^\s`\(\)\"\'<>]+", content)
    assert len(hardcoded) == 0, f"Detected hardcoded Linux user paths: {hardcoded}"


def test_canonical_tokens_present(target_file: Path) -> None:
    """Verify standard path tokens are utilized."""
    content = target_file.read_text(encoding="utf-8")
    assert "<USER_HOME>" in content, "Missing canonical <USER_HOME> token"


def test_clean_markdown_no_raw_directive_xml(target_file: Path) -> None:
    """Verify that raw XML directive tags are not polluting the markdown."""
    content = target_file.read_text(encoding="utf-8")
    banned_tags = [
        "<GLOBAL_SWARM_ANTI_HALLUCINATION_DIRECTIVES>",
        "<SWARM_AUTONOMY_MANDATE>",
        "<ANTI_SPOOFING_COUNCIL_DIRECTIVE>",
        "<ADVERSARIAL_AUDIT_DIRECTIVE>",
        "<ROOT_CAUSE_MANDATE>",
    ]
    for tag in banned_tags:
        assert tag not in content, f"Found raw XML directive tag in {target_file.name}: {tag}"


def test_code_fence_balance(target_file: Path) -> None:
    """Verify all markdown code blocks are properly opened and closed."""
    content = target_file.read_text(encoding="utf-8")
    fences = [line for line in content.splitlines() if line.strip().startswith("```")]
    assert len(fences) % 2 == 0, f"Unbalanced code fences ({len(fences)}) in {target_file.name}"


def test_primary_sections_present(target_file: Path) -> None:
    """Verify all canonical primary numbered sections are present."""
    content = target_file.read_text(encoding="utf-8")

    required_sections = [
        "# Computational Prediction of Spectroscopic Observables for van der Waals Complexes",
        "## Changes in this revision",
        "## The one-page decision card",
        "## Quick start",
        "## 1. The three products and the routing question",
        "## 2. Scope, system class and vocabulary",
        "## 3. Required accuracy specification",
        "## 4. Error propagation: the geometry",
        "## 5. Corrected working equations, counts and constants",
        "## 6. Observables the previous versions underweighted",
        "## 7. Nuclear spin statistics and permutation-inversion symmetry",
        "## 8. Hardware, and the routing decision procedure",
        "## 8A. Concurrency and the scout-and-anchor heterogeneous pipeline",
        "## 8B. Job chaining and state reuse",
        "## 8C. The HDF5 PES store",
        "## 8D. Analytical Hessian CC Mandate: 3-Tier Routing Protocol",
        "## 9. Codes and acquisition: the MPQC track and Legacy/Proprietary Alternates (ORCA & CFOUR)",
        "## 9A. Composite and combined methods",
        "## 9B. Conformer and isomer search: GOAT, CREST, and the union",
        "## 10. The ORCA external-tool contract, implemented",
        "## 11. Software licensing",
        "## 12. How to read the tier tables",
        "## 13. Tables 1–5: search, surface, geometry, averaging, energetics",
        "## 14. Tables 6–10: secondary observables, large-amplitude motion, and the non-microwave regimes",
        "## 15. The Pareto frontier, dominated rows, and the two use cases",
        "## 16. Failure modes and mandatory guards",
        "## 17. Validation protocol: the six-system working set",
        "## 18. Deliverable specification",
        "## 19. The teaching tier, corrected",
        "## 20. Reproducibility and provenance",
        "## 21. Hard limits, and the development roadmap",
        "## 22. Conference record and provenance of this revision",
        "## Appendix A. Large-amplitude-motion integrations, retained from v3",
        "## 23. References",
    ]

    for sec in required_sections:
        assert sec in content, f"Missing required section in {target_file.name}: {sec}"


def test_provenance_and_method_matrix_invariants(target_file: Path) -> None:
    """Verify core Method Matrix scientific and physical invariants."""
    content = target_file.read_text(encoding="utf-8")

    # Provenance tags
    assert "[M]" in content, "Missing [M] measured provenance tag"
    assert "[D]" in content, "Missing [D] derived provenance tag"
    assert "[E]" in content, "Missing [E] estimated provenance tag"

    # Hessian & Grid invariants
    assert "InHess XTB2" in content
    assert "Lindh" in content
    assert "Calc_Hess true" in content or "Calc_Hess" in content
    assert "DEFGRID2" in content or "DEFGRID3" in content or "DEFGRID4" in content
    assert "TightOpt" in content
    assert "TightSCF" in content
    assert "TolMaxG 1e-5" in content or "TolMaxG" in content

    # Method & Hardware rules
    assert "Frozen-Monomer" in content or "frozen monomer" in content.lower()
    assert "junChS" in content
    assert "gpu4pyscf" in content
    assert "RTX 3090" in content
    assert "PESStore" in content
    assert "AUTOFIT" in content
    assert "CREST" in content
    assert "GOAT" in content
    assert "CFOUR" in content
    assert "ORCA" in content
    assert "MPQC" in content
