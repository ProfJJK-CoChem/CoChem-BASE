"""Zero-Mock Production Test Suite for CoChem-SpycFit .gitignore Air-Gap Specifications.

Defends the Tripartite Workspace Air-Gap and repository hygiene by validating:
- Physical existence of .gitignore at CoChem-SpycFit repository root.
- Strict UTF-8 encoding (no byte order mark) and Unix LF line endings.
- Exact compliance with SRS Document specifications across all header and comment sections.
- Comprehensive physical pattern matching covering all blocked and permitted file types.
- Deep nested directory traversal and execution scratch boundary enforcement.
- Verification of zero forbidden testing constructs via AST analysis.
- Live git check-ignore validation using physical git processes within isolated temporary repositories.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

# Repository paths
BASE_REPO_ROOT = Path(__file__).resolve().parent.parent
SPYCFIT_REPO_ROOT = BASE_REPO_ROOT.parent / "CoChem-SpycFit"
SPYCFIT_GITIGNORE_PATH = SPYCFIT_REPO_ROOT / ".gitignore"

# Canonical SRS .gitignore content
CANONICAL_GITIGNORE_CONTENT = (
    "# ==========================================\n"
    "# CoChem Tripartite Air-Gap Enforcements\n"
    "# ==========================================\n"
    "\n"
    "# Block Tier 2: Master Artifacts Data Tier\n"
    "CoChem_Artifacts/\n"
    "*/CoChem_Artifacts/*\n"
    "*.h5\n"
    "*.hdf5\n"
    "*.zarr\n"
    "*.parquet\n"
    "*.arrow\n"
    "*.csv\n"
    "*.xyz\n"
    "*.mol\n"
    "*.lin\n"
    "*.par\n"
    "*.var\n"
    "*.int\n"
    "*.cat\n"
    "*.fit\n"
    "*.tmp\n"
    "*.tex\n"
    "\n"
    "# Block Tier 3: State, Config, & IPC Tier\n"
    "cochem_system_config.json\n"
    "fit_provenance.json\n"
    "spycfit_telemetry.json\n"
    "*.ipc\n"
    "*.lock\n"
    "*.socket\n"
    ".jax_xla_cache/\n"
    "\n"
    "# Standard Python Exclusions\n"
    "__pycache__/\n"
    "*.py[cod]\n"
    "*$py.class\n"
    ".ipynb_checkpoints/\n"
    ".env\n"
)

EXPECTED_HEADERS = [
    "# ==========================================",
    "# CoChem Tripartite Air-Gap Enforcements",
    "# ==========================================",
    "# Block Tier 2: Master Artifacts Data Tier",
    "# Block Tier 3: State, Config, & IPC Tier",
    "# Standard Python Exclusions",
]

TIER_2_PATTERNS = [
    "CoChem_Artifacts/",
    "*/CoChem_Artifacts/*",
    "*.h5",
    "*.hdf5",
    "*.zarr",
    "*.parquet",
    "*.arrow",
    "*.csv",
    "*.xyz",
    "*.mol",
    "*.lin",
    "*.par",
    "*.var",
    "*.int",
    "*.cat",
    "*.fit",
    "*.tmp",
    "*.tex",
]

TIER_3_PATTERNS = [
    "cochem_system_config.json",
    "fit_provenance.json",
    "spycfit_telemetry.json",
    "*.ipc",
    "*.lock",
    "*.socket",
    ".jax_xla_cache/",
]

PYTHON_EXCLUSION_PATTERNS = [
    "__pycache__/",
    "*.py[cod]",
    "*$py.class",
    ".ipynb_checkpoints/",
    ".env",
]

ALL_EXPECTED_PATTERNS = TIER_2_PATTERNS + TIER_3_PATTERNS + PYTHON_EXCLUSION_PATTERNS


@pytest.fixture(scope="module")
def spycfit_gitignore_content() -> str:
    """Fixture providing the decoded text content of CoChem-SpycFit .gitignore."""
    assert SPYCFIT_GITIGNORE_PATH.exists(), f"Missing .gitignore at {SPYCFIT_GITIGNORE_PATH}"
    return SPYCFIT_GITIGNORE_PATH.read_text(encoding="utf-8")


def test_spycfit_gitignore_existence_and_size() -> None:
    """Validate that .gitignore physically exists in CoChem-SpycFit root with valid size bounds."""
    assert SPYCFIT_GITIGNORE_PATH.exists(), f"Target file must exist: {SPYCFIT_GITIGNORE_PATH}"
    assert SPYCFIT_GITIGNORE_PATH.is_file(), f"Target path must be a regular file: {SPYCFIT_GITIGNORE_PATH}"
    size = SPYCFIT_GITIGNORE_PATH.stat().st_size
    assert 100 < size < 5000, f".gitignore size ({size} bytes) outside expected range (100, 5000)"


def test_spycfit_gitignore_encoding_and_lf_line_endings() -> None:
    """Validate strict UTF-8 encoding without BOM and Unix LF line endings."""
    raw_bytes = SPYCFIT_GITIGNORE_PATH.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "Target file must not contain a UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "Target file contains Windows CRLF line endings"
    assert b"\r" not in raw_bytes, "Target file contains carriage return line endings"
    assert b"\n" in raw_bytes, "Target file must contain Unix LF line endings"
    # Ensure byte-level decode succeeds cleanly
    decoded = raw_bytes.decode("utf-8")
    assert len(decoded) > 0, "Target file content cannot be empty"


def test_spycfit_gitignore_exact_headers_and_comments(spycfit_gitignore_content: str) -> None:
    """Validate that exact banner and section comments are present in the correct format."""
    for header in EXPECTED_HEADERS:
        assert header in spycfit_gitignore_content, f"Expected header/comment missing: {header}"


def test_spycfit_gitignore_all_tier_patterns_present(spycfit_gitignore_content: str) -> None:
    """Validate that all Tier 2, Tier 3, and Python exclusion patterns are present."""
    non_comment_lines = [
        line.strip()
        for line in spycfit_gitignore_content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    for pattern in ALL_EXPECTED_PATTERNS:
        assert pattern in non_comment_lines, f"Required pattern '{pattern}' missing from .gitignore"


def test_spycfit_gitignore_exact_canonical_content() -> None:
    """Validate that the .gitignore file strictly matches the exact SRS canonical definition."""
    content = SPYCFIT_GITIGNORE_PATH.read_text(encoding="utf-8")
    assert content == CANONICAL_GITIGNORE_CONTENT, "Content differs from canonical SRS specification"


def test_zero_mock_or_synthetic_directives_ast() -> None:
    """Verify through AST analysis that no forbidden mock libraries are imported in this test file."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "mock" not in alias.name.lower(), f"Forbidden import found: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "mock" not in module.lower(), f"Forbidden import from module: {module}"


@pytest.mark.parametrize(
    "relative_target, expected_blocked, category",
    [
        # Tier 2: Master Artifacts Data Tier
        ("CoChem_Artifacts/run01/spectrum.dat", True, "Tier 2: CoChem_Artifacts root directory"),
        ("nested/folder/CoChem_Artifacts/job1/output.txt", True, "Tier 2: Nested CoChem_Artifacts wildcard"),
        ("data/simulation.h5", True, "Tier 2: HDF5 (.h5)"),
        ("quantum_state.hdf5", True, "Tier 2: HDF5 (.hdf5)"),
        ("analysis.zarr/group/0", True, "Tier 2: Zarr store (.zarr)"),
        ("records.parquet", True, "Tier 2: Parquet table (.parquet)"),
        ("dataset.arrow", True, "Tier 2: Apache Arrow (.arrow)"),
        ("spectrum_table.csv", True, "Tier 2: CSV Data (.csv)"),
        ("geometry.xyz", True, "Tier 2: Chemical XYZ (.xyz)"),
        ("complex.mol", True, "Tier 2: Chemical MOL (.mol)"),
        ("input.lin", True, "Tier 2: SPYCFIT / SPCAT input (.lin)"),
        ("parameters.par", True, "Tier 2: Parameter file (.par)"),
        ("variation.var", True, "Tier 2: Variation file (.var)"),
        ("intensity.int", True, "Tier 2: Intensity file (.int)"),
        ("catalog.cat", True, "Tier 2: Catalog file (.cat)"),
        ("spectrum_fit.fit", True, "Tier 2: Fit result (.fit)"),
        ("scratch_eval.tmp", True, "Tier 2: Temporary work file (.tmp)"),
        ("report.tex", True, "Tier 2: LaTeX file (.tex)"),
        # Tier 3: State, Config, & IPC Tier
        ("cochem_system_config.json", True, "Tier 3: System config JSON"),
        ("fit_provenance.json", True, "Tier 3: Provenance JSON"),
        ("spycfit_telemetry.json", True, "Tier 3: Telemetry JSON"),
        ("channel.ipc", True, "Tier 3: IPC socket/pipe (.ipc)"),
        ("execution.lock", True, "Tier 3: Lockfile (.lock)"),
        ("service.socket", True, "Tier 3: Unix domain socket (.socket)"),
        (".jax_xla_cache/compilation_artifact", True, "Tier 3: JAX XLA Cache directory"),
        # Standard Python Exclusions
        ("__pycache__/module.cpython-311.pyc", True, "Python: Bytecode cache"),
        ("src/__pycache__/core.pyc", True, "Python: Nested bytecode cache"),
        ("compiled.pyc", True, "Python: Bytecode (.pyc)"),
        ("optimized.pyo", True, "Python: Bytecode (.pyo)"),
        ("extension.pyd", True, "Python: Dynamic module (.pyd)"),
        ("JavaBridge$py.class", True, "Python: Class exclusion (*$py.class)"),
        (".ipynb_checkpoints/Notebook-checkpoint.ipynb", True, "Python: Jupyter checkpoint"),
        (".env", True, "Python: Environment secret file (.env)"),
        # Permitted Production Source Files
        ("main.py", False, "Permitted: Python root script"),
        ("src/cochem_spycfit/engine.py", False, "Permitted: Package module"),
        ("tests/test_spycfit_engine.py", False, "Permitted: Test module"),
        ("README.md", False, "Permitted: Repository documentation"),
        ("pyproject.toml", False, "Permitted: Package metadata"),
        ("setup.cfg", False, "Permitted: Setuptools configuration"),
        ("LICENSE", False, "Permitted: License file"),
        ("spectral_config.yaml", False, "Permitted: YAML config (not blocked)"),
        ("general_manifest.json", False, "Permitted: General non-blocked JSON"),
    ],
)
def test_git_check_ignore_matrix(
    tmp_path: Path, relative_target: str, expected_blocked: bool, category: str
) -> None:
    """Physically test git ignore rules using live git subprocesses in an isolated sandbox repository."""
    # Write exact .gitignore to sandbox repository
    (tmp_path / ".gitignore").write_bytes(SPYCFIT_GITIGNORE_PATH.read_bytes())

    # Initialize physical git repository
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "CoChem-Tester"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "tester@cochem.org"],
        check=True,
        capture_output=True,
    )

    # Materialize target test file
    target_path = tmp_path / relative_target
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("airgap physical validation payload", encoding="utf-8")

    # Query physical git check-ignore status
    proc = subprocess.run(
        ["git", "-C", str(tmp_path), "check-ignore", "-q", relative_target],
        capture_output=True,
    )
    is_ignored = proc.returncode == 0

    assert is_ignored == expected_blocked, (
        f"[{category}] Mismatch for target '{relative_target}': "
        f"expected blocked={expected_blocked}, but got {is_ignored}."
    )
