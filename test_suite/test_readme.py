"""Comprehensive Zero-Mock Test Suite for CoChem-BASE README.md Documentation.

Validates:
- Physical file existence, non-empty content, UTF-8 encoding (no BOM), and strict Unix LF line endings.
- PI Authorship and ORCiD provenance (Dr. Joshua John Klaassen, https://orcid.org/0009-0007-1506-4401).
- Ecosystem documentation cross-references (Method_Matrix.md, CoChem_User_Manual.md, Apache-2.0 / LICENSE).
- 4-Tier OS Interaction Model:
  1. Tier 1: Explicit CLI/function args (Explicit Parameters).
  2. Tier 2: Environment variables (COCHEM_CONFIG, COCHEM_ARTIFACT_DIR, COCHEM_SCRATCH).
  3. Tier 3: Central system config (cochem_system_config.json).
  4. Tier 4: Dynamic workspace / discovery fallbacks.
- Tripartite Workspace Air-Gap Architecture:
  1. Static Execution Tier (immutable Git repository, code/schemas/UI, zero runtime writes, airgap_trap.py).
  2. Persistent Data Tier (Git-ignored, POSIX locks, $SCRATCH / $COCHEM_ARTIFACT_DIR / $HOME, SWMR runtime_active.h5, compressed QCSchema archive_pes.h5).
  3. Ephemeral Compute Tier (node-local sterile quarantine /tmp/cochem_exec_<uuid>/, MPS sockets, PySCF checkpoints, ORCA .gbw).
- Architectural Mandate strictly forbidding GitHub Actions (GHA) as a compute runner (CI/CD and AST sweeps only, HPC Slurm/PBS dispatcher required).
- Setup instructions, Stage 0 bootstrapper sequence, and entry point Start_Here.ipynb with cochem_base_silo kernel.
- Markdown syntax validity (balanced code fences, valid links, headings hierarchy).
- Absolute Zero-Mock compliance and absence of placeholder / dummy / stub tokens.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / "README.md"


@pytest.fixture(scope="module")
def readme_raw_bytes() -> bytes:
    """Fixture providing raw bytes of README.md."""
    assert README_PATH.exists(), f"README.md does not exist at {README_PATH}"
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
    stat = README_PATH.stat()
    assert stat.st_size >= 3000, f"README.md size too small ({stat.st_size} bytes); comprehensive documentation expected."


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
    """Validate that PI Dr. Joshua John Klaassen and valid ORCiD are documented."""
    assert "Joshua John Klaassen" in readme_content, "PI Dr. Joshua John Klaassen missing from README.md"
    assert "https://orcid.org/0009-0007-1506-4401" in readme_content, "ORCiD link missing from README.md"
    assert "https://github.com/ProfJJK-CoChem" in readme_content, "GitHub organization link missing from README.md"


def test_readme_core_references_and_licensing(readme_content: str) -> None:
    """Validate cross-references to Method Matrix, User Manual, and License."""
    assert "Method_Matrix.md" in readme_content or "Method Matrix" in readme_content, (
        "Method Matrix reference missing from README.md"
    )
    assert "CoChem_User_Manual.md" in readme_content or "CoChem User Manual" in readme_content, (
        "User Manual reference missing from README.md"
    )
    assert "Apache" in readme_content, "Apache License reference missing from README.md"
    assert "LICENSE" in readme_content, "LICENSE file reference missing from README.md"


# ==============================================================================
# 3. 4-Tier OS Interaction Model
# ==============================================================================


def test_readme_4_tier_os_interaction_model(readme_content: str) -> None:
    """Validate comprehensive documentation of the 4-Tier OS Interaction Model."""
    content_lower = readme_content.lower()
    assert "4-tier" in content_lower or "four-tier" in content_lower, (
        "4-Tier OS interaction model not mentioned in README.md"
    )

    # Tier 1: Explicit Parameters (CLI / function arguments)
    assert "tier 1" in content_lower, "Tier 1 missing from 4-Tier OS Interaction documentation"
    assert "cli" in content_lower or "argument" in content_lower or "parameter" in content_lower, (
        "Tier 1 explicit parameter / CLI description missing from README.md"
    )

    # Tier 2: Environment Variables
    assert "tier 2" in content_lower, "Tier 2 missing from 4-Tier OS Interaction documentation"
    assert "environment variable" in content_lower or "cochem_config" in content_lower, (
        "Tier 2 environment variable description missing from README.md"
    )

    # Tier 3: Central System Configuration
    assert "tier 3" in content_lower, "Tier 3 missing from 4-Tier OS Interaction documentation"
    assert "cochem_system_config.json" in content_lower or "system config" in content_lower, (
        "Tier 3 central system config description missing from README.md"
    )

    # Tier 4: Dynamic Workspace & Discovery Fallbacks
    assert "tier 4" in content_lower, "Tier 4 missing from 4-Tier OS Interaction documentation"
    assert "discovery" in content_lower or "fallback" in content_lower or "workspace" in content_lower, (
        "Tier 4 dynamic discovery / fallback description missing from README.md"
    )


# ==============================================================================
# 4. Tripartite Workspace Air-Gap Architecture
# ==============================================================================


def test_readme_tripartite_airgap_structure(readme_content: str) -> None:
    """Validate comprehensive documentation of the Tripartite Workspace Air-Gap."""
    content_lower = readme_content.lower()
    assert "tripartite" in content_lower, "Tripartite architecture not mentioned in README.md"
    assert "air-gap" in content_lower or "airgap" in content_lower, "Air-gap concept not mentioned in README.md"

    # 1. Static Execution Tier
    assert "static execution tier" in content_lower or "static execution" in content_lower, (
        "Static Execution Tier missing from README.md"
    )

    # 2. Persistent Data Tier
    assert "persistent data tier" in content_lower or "persistent data" in content_lower, (
        "Persistent Data Tier missing from README.md"
    )

    # 3. Ephemeral Compute Tier
    assert "ephemeral compute tier" in content_lower or "ephemeral compute" in content_lower, (
        "Ephemeral Compute Tier missing from README.md"
    )


def test_readme_tripartite_tier_technical_details(readme_content: str) -> None:
    """Validate specific technical artifacts across all three workspace tiers."""
    content_lower = readme_content.lower()

    # Static Execution Tier: Zero runtime writes, monitored code/schemas/UI
    assert "zero runtime write" in content_lower or "read-only" in content_lower, (
        "Zero runtime write policy for Static Execution Tier not stated in README.md"
    )
    assert "airgap_trap.py" in readme_content or "airgap" in content_lower, (
        "airgap_trap.py enforcement script reference missing in README.md"
    )

    # Persistent Data Tier: HDF5 SWMR, runtime_active.h5 / cochem_state.h5, archive_pes.h5, QCSchema
    assert "runtime_active.h5" in readme_content or "cochem_state.h5" in readme_content, (
        "Active HDF5 state store (runtime_active.h5 / cochem_state.h5) missing in README.md"
    )
    assert "archive_pes.h5" in readme_content or "qcschema" in content_lower, (
        "Archival PES store or QCSchema standard missing in README.md"
    )
    assert "swmr" in content_lower or "single-writer" in content_lower, (
        "SWMR (Single-Writer Multiple-Reader) concurrency pattern missing in README.md"
    )

    # Ephemeral Compute Tier: quarantine scratch, MPS sockets, PySCF/ORCA temporary artifacts
    assert "cochem_exec_" in readme_content or "/tmp" in readme_content or "scratch" in content_lower, (
        "Node-local ephemeral scratch quarantine directory missing in README.md"
    )
    assert ".gbw" in readme_content or "wavefunction" in content_lower, (
        "Transient wavefunction (.gbw) or scratch artifact handling missing in README.md"
    )


# ==============================================================================
# 5. GitHub Actions (GHA) Compute Runner Ban & HPC Policy
# ==============================================================================


def test_readme_gha_compute_ban_mandate(readme_content: str) -> None:
    """Validate explicit architectural mandate forbidding GitHub Actions as a compute runner."""
    content_lower = readme_content.lower()
    assert "github actions" in content_lower or "gha" in content_lower, (
        "GitHub Actions / GHA not mentioned in README.md"
    )
    assert "compute runner" in content_lower or "compute" in content_lower, (
        "Compute runner distinction for GHA missing in README.md"
    )
    assert "slurm" in content_lower or "pbs" in content_lower or "hpc" in content_lower, (
        "HPC workload managers (Slurm/PBS/HPC) missing from README.md"
    )
    assert "hpcdispatcher" in content_lower or "dispatcher" in content_lower, (
        "HPCDispatcher reference missing from README.md"
    )


# ==============================================================================
# 6. Setup, Stage 0 Bootstrap & Start_Here.ipynb Entry Point
# ==============================================================================


def test_readme_entry_point_and_stage_0_bootstrap(readme_content: str) -> None:
    """Validate onboarding instructions referencing Start_Here.ipynb and Stage 0."""
    assert "Start_Here.ipynb" in readme_content, "Master entry point Start_Here.ipynb missing from README.md"
    content_lower = readme_content.lower()
    assert "stage 0" in content_lower or "bootstrap" in content_lower or "silo" in content_lower, (
        "Stage 0 bootstrap / Silo setup missing from README.md"
    )
    assert "cochem_base_silo" in readme_content or "kernel" in content_lower, (
        "Silo kernel selection instruction missing from README.md"
    )


def test_readme_prerequisites_and_installation(readme_content: str) -> None:
    """Validate prerequisites and environment installation commands."""
    assert "3.11" in readme_content, "Python 3.11 requirement missing in README.md"
    content_lower = readme_content.lower()
    assert "conda" in content_lower or "mamba" in content_lower or "pip" in content_lower, (
        "Package management instructions missing in README.md"
    )


# ==============================================================================
# 7. Markdown Structural Invariants & Code Blocks
# ==============================================================================


def test_readme_markdown_fences_balanced(readme_content: str) -> None:
    """Validate that all Markdown code fences (```) are strictly closed and balanced."""
    lines = readme_content.splitlines()
    fence_count = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            fence_count += 1
    assert fence_count % 2 == 0, f"Unbalanced code fences in README.md: found {fence_count} fence markers"


def test_readme_markdown_headings_hierarchy(readme_content: str) -> None:
    """Validate that README.md has a valid top-level heading and structured sections."""
    lines = readme_content.splitlines()
    h1_headings = [line for line in lines if line.startswith("# ")]
    h2_headings = [line for line in lines if line.startswith("## ")]

    assert len(h1_headings) >= 1, "README.md must contain at least one H1 heading"
    assert "CoChem-BASE" in h1_headings[0], f"H1 heading must name CoChem-BASE (found: {h1_headings[0]})"
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
# 8. Zero-Mock Policy & Anti-Placeholder Invariants
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
