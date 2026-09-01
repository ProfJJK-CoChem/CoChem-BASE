"""Comprehensive Zero-Mock Test Suite for CoChem-SCRIBE README.md Documentation.

Governed strictly by:
- Phase 4, Task 11 (Task 98) of the CoChem-SCRIBE Software Requirements Specification (SRS).
- Method Matrix v4, FAIR Data Provenance Standards, and Zero-Mock Anti-Spoofing Directive.
- Mendeleev Library Mandate for dynamic atomic/isotopic properties.

Validates:
1. Physical existence, non-empty content, UTF-8 encoding (no BOM), and strict Unix LF line endings.
2. Metadata, PI Authorship (Dr. Joshua John Klaassen), ORCiD provenance, and GitHub Organization.
3. Ecosystem cross-references (Method_Matrix.md, CoChem_User_Manual.md, LICENSE).
4. 6-Tier Environment Matrix compatibility:
   - Local-Windows (WSL)
   - Local-MacOS (OrbStack)
   - Local-Linux (Debian)
   - GitHub Codespaces
   - GitHub Actions (CI/CD sweeps, AST anti-spoofing only; no compute runner)
   - HPC SLURM/PBS (High-Performance Computing nodes)
5. Tripartite Workspace Air-Gap Architecture & Commit Hygiene:
   - Static Execution Tier (Git-tracked, code/templates, zero runtime writes)
   - Dynamic Data Tier ($HOME/CoChem_Artifacts/Report_Archive/ for .env, POSIX 0o600, generated manuscripts)
   - Volatile Compute Tier ($HOME/cochem_scratch/ / ephemeral node-local quarantine for raw calculations, .gbw, .h5)
   - Strict Air-Gap rule forbidding committing user data .h5, .env, or .pdf artifacts to git.
6. RESOURCE_GUARD Hardware Toggles:
   - Hardware polling via psutil.virtual_memory().total
   - Memory threshold: < 8.0 GB RAM constraint
   - Forced API routing (google-genai) over local LLM (llama-cpp) on resource-constrained systems
   - Audit logging of [SCRIBE-WARNING] to cochem_audit_log.json
   - Strict fail-fast abort on missing credentials (no synthetic dry-run fabrication)
7. Step-by-Step Genuine CLI Execution Instructions:
   - python -m cochem_scribe.master --config-path configs/scribe_config.json --output-dir reports/ --dry-run
   - CLI flags: --dry-run, --config-path, --output-dir, --model-engine
   - 5-step pipeline execution: [1/5] Harvest HDF5, [2/5] Build Payload, [3/5] LLM Inference, [4/5] Template Docs, [5/5] Compile & Zip
   - Headless LaTeX compilation (pdflatex -> bibtex -> pdflatex -> pdflatex with -interaction=nonstopmode)
   - Cryptographic sealing (CoChem_Final_Report_[TIMESTAMP].zip with POSIX 0o444 read-only lock, SHA-256 digest, topological hash in manifest.json)
8. Mendeleev Library Integration (dynamic elemental and isotopic property lookups via mendeleev).
9. Markdown Structural Invariants & Code Block Balance.
10. Zero-Mock Policy & Anti-Placeholder Invariants.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SCRIBE_REPO_ROOT = Path("D:/__CoChem/GitHub-Repo/CoChem-SCRIBE").resolve()
README_PATH = SCRIBE_REPO_ROOT / "README.md"


@pytest.fixture(scope="module")
def readme_raw_bytes() -> bytes:
    """Fixture providing raw bytes of CoChem-SCRIBE README.md."""
    assert README_PATH.exists(), f"CoChem-SCRIBE README.md does not exist at {README_PATH}"
    return README_PATH.read_bytes()


@pytest.fixture(scope="module")
def readme_content(readme_raw_bytes: bytes) -> str:
    """Fixture providing decoded UTF-8 string content of README.md."""
    return readme_raw_bytes.decode("utf-8")


# ==============================================================================
# 1. Physical File Integrity & Line Endings
# ==============================================================================


def test_readme_file_exists_and_is_regular_file() -> None:
    """Validate that README.md exists as a physical regular file in the repository root."""
    assert README_PATH.exists(), f"README.md missing at {README_PATH}"
    assert README_PATH.is_file(), f"README.md at {README_PATH} is not a regular file"
    stat_res = README_PATH.stat()
    assert stat_res.st_size >= 3000, f"README.md size too small ({stat_res.st_size} bytes); comprehensive documentation expected."


def test_readme_encoding_and_lf_line_endings(readme_raw_bytes: bytes) -> None:
    """Validate that README.md has no UTF-8 BOM and strictly uses Unix LF line endings."""
    assert not readme_raw_bytes.startswith(b"\xef\xbb\xbf"), "README.md contains illegal UTF-8 BOM"
    assert b"\r\n" not in readme_raw_bytes, "README.md contains Windows CRLF line endings (strict LF required)"
    assert b"\r" not in readme_raw_bytes, "README.md contains legacy Mac CR line endings"
    assert b"\n" in readme_raw_bytes, "README.md missing newline characters"


# ==============================================================================
# 2. Metadata, Authorship & Academic Provenance
# ==============================================================================


def test_readme_authorship_and_orcid(readme_content: str) -> None:
    """Validate that PI Dr. Joshua John Klaassen, ORCiD, and GitHub Org are documented."""
    assert "Joshua John Klaassen" in readme_content, "PI Dr. Joshua John Klaassen missing from README.md"
    assert "https://orcid.org/0009-0007-1506-4401" in readme_content, "ORCiD link missing from README.md"
    assert "https://github.com/ProfJJK-CoChem" in readme_content, "GitHub organization link missing from README.md"


def test_readme_core_references_and_licensing(readme_content: str) -> None:
    """Validate cross-references to Method Matrix v4, User Manual, and License."""
    assert "Method_Matrix.md" in readme_content or "Method Matrix" in readme_content, (
        "Method Matrix reference missing from README.md"
    )
    assert "CoChem_User_Manual.md" in readme_content or "CoChem User Manual" in readme_content, (
        "User Manual reference missing from README.md"
    )
    assert "LICENSE" in readme_content or "License" in readme_content, (
        "LICENSE file reference missing from README.md"
    )


# ==============================================================================
# 3. 6-Tier Environment Matrix Compatibility (SRS Task 98)
# ==============================================================================


def test_readme_6_tier_environment_matrix(readme_content: str) -> None:
    """Validate comprehensive documentation of the 6-Tier Environment Matrix."""
    content_lower = readme_content.lower()
    assert "6-tier" in content_lower or "six-tier" in content_lower, (
        "6-Tier Environment Matrix not explicitly documented in README.md"
    )

    # Tier 1: WSL (Local-Windows WSL)
    assert "wsl" in content_lower or "windows subsystem for linux" in content_lower, (
        "Tier 1: WSL compatibility missing from README.md"
    )

    # Tier 2: OrbStack (Local-MacOS OrbStack)
    assert "orbstack" in content_lower or "macos" in content_lower, (
        "Tier 2: OrbStack / macOS compatibility missing from README.md"
    )

    # Tier 3: Debian (Local-Linux Debian)
    assert "debian" in content_lower or "linux" in content_lower, (
        "Tier 3: Debian / Linux compatibility missing from README.md"
    )

    # Tier 4: Codespaces (GitHub Codespaces)
    assert "codespaces" in content_lower, (
        "Tier 4: GitHub Codespaces compatibility missing from README.md"
    )

    # Tier 5: GitHub Actions (CI/CD sweeps, AST anti-spoofing only; no compute runner)
    assert "github actions" in content_lower or "gha" in content_lower, (
        "Tier 5: GitHub Actions CI/CD compatibility missing from README.md"
    )

    # Tier 6: HPC SLURM / PBS (High-Performance Computing)
    assert "slurm" in content_lower or "pbs" in content_lower or "hpc" in content_lower, (
        "Tier 6: HPC SLURM/PBS compatibility missing from README.md"
    )


# ==============================================================================
# 4. Strict Tripartite Air-Gap Rule & Commit Hygiene (SRS Task 98)
# ==============================================================================


def test_readme_air_gap_rule_and_commit_hygiene(readme_content: str) -> None:
    """Validate documentation of the strict Air-Gap rule forbidding .h5, .env, and .pdf in commits."""
    content_lower = readme_content.lower()
    assert "air-gap" in content_lower or "airgap" in content_lower, (
        "Air-Gap rule not documented in README.md"
    )

    # Tripartite tiers
    assert "static execution tier" in content_lower or "static execution" in content_lower, (
        "Static Execution Tier missing from README.md"
    )
    assert "dynamic data tier" in content_lower or "report_archive" in content_lower or "data tier" in content_lower, (
        "Dynamic Data Tier ($HOME/CoChem_Artifacts/Report_Archive/) missing from README.md"
    )
    assert "volatile compute tier" in content_lower or "compute tier" in content_lower or "scratch" in content_lower, (
        "Volatile Compute Tier ($HOME/cochem_scratch/) missing from README.md"
    )

    # Forbidden commit artifacts: .h5, .env, .pdf
    assert ".h5" in content_lower, "Banned .h5 user data database commit rule missing in README.md"
    assert ".env" in content_lower, "Banned .env credentials commit rule missing in README.md"
    assert ".pdf" in content_lower, "Banned .pdf generated manuscript commit rule missing in README.md"


# ==============================================================================
# 5. RESOURCE_GUARD Hardware Toggles (SRS Task 98)
# ==============================================================================


def test_readme_resource_guard_hardware_toggles(readme_content: str) -> None:
    """Validate comprehensive documentation of RESOURCE_GUARD hardware toggles."""
    content_lower = readme_content.lower()
    assert "resource_guard" in content_lower or "resource guard" in content_lower, (
        "RESOURCE_GUARD hardware toggle missing from README.md"
    )
    assert "8" in content_lower and ("gb" in content_lower or "gigabyte" in content_lower), (
        "8.0 GB RAM boundary threshold missing from RESOURCE_GUARD documentation"
    )
    assert "psutil" in content_lower, (
        "psutil memory polling reference missing in RESOURCE_GUARD documentation"
    )
    assert "cochem_audit_log.json" in content_lower or "audit_log" in content_lower, (
        "cochem_audit_log.json [SCRIBE-WARNING] logging missing in RESOURCE_GUARD documentation"
    )
    assert "google-genai" in content_lower or "gemini" in content_lower or "api" in content_lower, (
        "Forced API routing fallback missing in RESOURCE_GUARD documentation"
    )


# ==============================================================================
# 6. Step-by-Step Genuine CLI Execution Instructions (SRS Task 98)
# ==============================================================================


def test_readme_cli_execution_instructions(readme_content: str) -> None:
    """Validate step-by-step genuine CLI execution commands and flags."""
    content_lower = readme_content.lower()

    # CLI command syntax
    assert "cochem_scribe.master" in readme_content or "cochem_scribe_master" in readme_content or "cochem-scribe" in content_lower, (
        "Master CLI entry point command missing from README.md"
    )
    assert "--config-path" in readme_content, "--config-path CLI flag missing in README.md"
    assert "--output-dir" in readme_content, "--output-dir CLI flag missing in README.md"
    assert "--dry-run" in readme_content, "--dry-run CLI flag missing in README.md"

    # 5-step pipeline loop
    assert "harvest" in content_lower, "[1/5] Harvest step missing in pipeline documentation"
    assert "payload" in content_lower, "[2/5] Payload step missing in pipeline documentation"
    assert "inference" in content_lower, "[3/5] Inference step missing in pipeline documentation"
    assert "template" in content_lower, "[4/5] Templating step missing in pipeline documentation"
    assert "compile" in content_lower or "zip" in content_lower, "[5/5] Compile/Zip step missing in pipeline documentation"

    # Headless LaTeX compilation
    assert "pdflatex" in content_lower, "pdflatex compilation reference missing in README.md"
    assert "nonstopmode" in content_lower, "-interaction=nonstopmode flag missing in README.md"

    # Cryptographic sealing & POSIX locks
    assert "zip" in content_lower, "ZIP archive packaging missing in README.md"
    assert "0o444" in readme_content or "444" in readme_content or "read-only" in content_lower, (
        "POSIX 0o444 read-only archive locking missing in README.md"
    )
    assert "manifest.json" in readme_content, "manifest.json FAIR provenance manifest missing in README.md"
    assert "sha-256" in content_lower or "sha256" in content_lower, (
        "SHA-256 cryptographic digest verification missing in README.md"
    )


# ==============================================================================
# 7. Mendeleev Library Integration (Mendeleev Mandate)
# ==============================================================================


def test_readme_mendeleev_library_integration(readme_content: str) -> None:
    """Validate documentation of dynamic atomic/isotopic retrieval via mendeleev library."""
    assert "mendeleev" in readme_content.lower(), "mendeleev library integration missing from README.md"


# ==============================================================================
# 8. Markdown Structural Invariants & Code Blocks
# ==============================================================================


def test_readme_markdown_fences_balanced(readme_content: str) -> None:
    """Validate that all Markdown code fences (```) are strictly closed and balanced."""
    lines = readme_content.splitlines()
    fence_count = sum(1 for line in lines if line.strip().startswith("```"))
    assert fence_count > 0, "README.md must contain code examples in fenced code blocks"
    assert fence_count % 2 == 0, f"Unbalanced code fences in README.md: found {fence_count} fence markers"


def test_readme_markdown_headings_hierarchy(readme_content: str) -> None:
    """Validate that README.md has a valid top-level heading and structured sections."""
    lines = readme_content.splitlines()
    h1_headings = [line for line in lines if line.startswith("# ")]
    h2_headings = [line for line in lines if line.startswith("## ")]

    assert len(h1_headings) >= 1, "README.md must contain at least one H1 heading"
    assert "CoChem-SCRIBE" in h1_headings[0], f"H1 heading must name CoChem-SCRIBE (found: {h1_headings[0]})"
    assert len(h2_headings) >= 5, f"README.md must contain structured H2 sections (found {len(h2_headings)})"


def test_readme_markdown_links_non_empty(readme_content: str) -> None:
    """Validate that all markdown links [text](url) have non-empty text and url."""
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    matches = link_pattern.findall(readme_content)
    assert len(matches) >= 3, "README.md must contain substantive markdown links"
    for text, url in matches:
        assert text.strip(), f"Empty link text in markdown link: [{text}]({url})"
        assert url.strip(), f"Empty URL target in markdown link: [{text}]({url})"


# ==============================================================================
# 9. Zero-Mock Policy & Anti-Placeholder Invariants
# ==============================================================================


def test_readme_no_placeholder_tokens(readme_content: str) -> None:
    """Validate absolute absence of placeholder, dummy, or stub tokens in README.md."""
    prohibited_tokens = [
        "TODO",
        "FIXME",
        "TBD",
        "PLACEHOLDER",
        "LOREM IPSUM",
        "DUMMY_TOKEN",
        "MOCK_LOGIC",
        "FOO_BAR",
        "STUB_LOGIC",
        "FAKE_DATA",
    ]
    content_upper = readme_content.upper()
    for token in prohibited_tokens:
        assert token not in content_upper, f"Prohibited placeholder token '{token}' found in README.md"


def test_test_suite_zero_mock_ast_compliance() -> None:
    """Validate that this test file itself contains zero prohibited mock imports."""
    this_file = Path(__file__).resolve()
    tree = ast.parse(this_file.read_text(encoding="utf-8"), filename=str(this_file))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "mock" not in alias.name.lower(), f"Prohibited mock import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "mock" not in mod.lower(), f"Prohibited mock import from: {mod}"
