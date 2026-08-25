"""Unit tests for CoChem-BENCH Git configuration (.gitignore).

Task: CoChem-BENCH Task 1 - Master Repository Map, Bipartite Topology & Air-Gap Enforcement.
Validates:
- File existence at repository root as a regular file.
- UTF-8 encoding with no BOM and strict Unix LF line endings.
- Exact presence of the CoChem-BENCH Filesystem Air-Gap Policy header and all 6 SRS sections.
- Presence of all required patterns blocking artifact tiers, registries, quantum tensors, logs, bytecode, and silos.
- Exception scoping for CI/CD pipeline fixtures (!tests/**/*.xyz).
- Absence of unverified markers (FIXME, UNIMPLEMENTED, TEMP_HACK, etc.).
- Strict Zero-Mock compliance verified via AST analysis.
- Physical pattern matching and verification using isolated git repositories and git check-ignore.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from typing import List

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GITIGNORE_PATH = REPO_ROOT / ".gitignore"

EXPECTED_HEADER = "# COCHEM-BENCH FILESYSTEM AIR-GAP POLICY"

EXPECTED_SECTIONS: List[str] = [
    "# 1. Permanently ignore the dynamically generated Artifact Tier",
    "# 2. Ignore all localized registries and state locks",
    "# 3. Block all heavy quantum chemistry and database tensors",
    "# 4. Block telemetry and execution logs",
    "# 5. Block Python Bytecode & Environments",
    "# 6. Exception Scoping for CI/CD Pipeline",
]

EXPECTED_PATTERNS: List[str] = [
    # Section 1: Artifact Tier
    "CoChem_Artifacts/",
    "*/CoChem_Artifacts/*",
    # Section 2: Localized Registries & State Locks
    "cochem_system_config.json",
    "*.lock",
    "cochem_bench_run_state.jsonl",
    # Section 3: Quantum Chemistry & Database Tensors
    "*.h5",
    "*.hdf5",
    "*.gbw",
    "*.tmp",
    "*.scf",
    "*.densities",
    "*.cube",
    "*.parquet",
    # Section 4: Telemetry & Execution Logs
    "*.log",
    "*.out",
    "*.err",
    "Logs/",
    # Section 5: Python Bytecode & Environments
    "__pycache__/",
    "*.py[cod]",
    "*$py.class",
    ".env",
    ".venv",
    "cochem_*_silo/",
    # Section 6: Exception Scoping for CI/CD Pipeline
    "!tests/**/*.xyz",
]


@pytest.fixture
def repo_root() -> Path:
    """Return the absolute path to the CoChem repository root."""
    return REPO_ROOT


@pytest.fixture
def gitignore_file() -> Path:
    """Return the absolute path to .gitignore and assert existence."""
    assert GITIGNORE_PATH.exists(), f".gitignore does not exist at {GITIGNORE_PATH}"
    return GITIGNORE_PATH


def test_gitignore_file_exists(repo_root: Path) -> None:
    """Validate that .gitignore exists in the repository root as a regular file."""
    path = repo_root / ".gitignore"
    assert path.exists(), f".gitignore file missing from repository root: {path}"
    assert path.is_file(), f".gitignore at {path} must be a regular file"


def test_gitignore_encoding_and_lf_endings(gitignore_file: Path) -> None:
    """Validate that .gitignore has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = gitignore_file.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), ".gitignore contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, ".gitignore contains Windows CRLF line endings"
    assert b"\r" not in raw_bytes, ".gitignore contains Mac/legacy CR line endings"
    assert b"\n" in raw_bytes, ".gitignore missing Unix LF line endings"
    assert len(raw_bytes.strip()) > 0, ".gitignore file must not be empty"


def test_gitignore_header_present(gitignore_file: Path) -> None:
    """Validate that the CoChem-BENCH Air-Gap Policy header is present."""
    content = gitignore_file.read_text(encoding="utf-8")
    assert EXPECTED_HEADER in content, (
        f"Missing expected policy header '{EXPECTED_HEADER}' in .gitignore"
    )


def test_gitignore_contains_all_six_sections(gitignore_file: Path) -> None:
    """Validate that all 6 SRS Document 1 section headers are present in .gitignore."""
    content = gitignore_file.read_text(encoding="utf-8")
    for section in EXPECTED_SECTIONS:
        assert section in content, f"Missing expected section header: '{section}'"


def test_gitignore_contains_all_patterns(gitignore_file: Path) -> None:
    """Validate that all required patterns from SRS Task 1 are present."""
    content = gitignore_file.read_text(encoding="utf-8")
    lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    for pattern in EXPECTED_PATTERNS:
        assert pattern in lines, f"Required pattern '{pattern}' missing from .gitignore"


def test_no_unverified_placeholder_markers(gitignore_file: Path) -> None:
    """Validate that .gitignore does not contain unverified or placeholder tokens."""
    forbidden_tokens = [
        "FIXME",
        "UNIMPLEMENTED",
        "TEMP_HACK",
        "BROKEN_MARKER",
    ]
    content = gitignore_file.read_text(encoding="utf-8").upper()
    for token in forbidden_tokens:
        assert token not in content, f".gitignore must not contain forbidden token '{token}'"


def test_zero_mock_compliance_in_test_suite() -> None:
    """Verify that test implementation strictly adheres to Zero-Mock rules via AST analysis."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "mock" not in alias.name.lower(), f"Forbidden mock import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "mock" not in module.lower(), f"Forbidden mock import: {module}"


@pytest.mark.parametrize(
    "relative_path, expected_ignored",
    [
        # Section 1: Artifact Tier
        ("CoChem_Artifacts/landscape.h5", True),
        ("CoChem_Artifacts/run_01/output.txt", True),
        ("nested/CoChem_Artifacts/temp.dat", True),
        ("sub/deep/CoChem_Artifacts/scratch.bin", True),
        # Section 2: Localized Registries & State Locks
        ("cochem_system_config.json", True),
        ("Registry/cochem_system_config.json", True),
        ("cochem_system_config.lock", True),
        ("process.lock", True),
        ("cochem_bench_run_state.jsonl", True),
        ("sub/cochem_bench_run_state.jsonl", True),
        # Section 3: Quantum Chemistry & Database Tensors
        ("landscape.h5", True),
        ("matrix.hdf5", True),
        ("orbitals.gbw", True),
        ("scratch.tmp", True),
        ("calc.scf", True),
        ("charge.densities", True),
        ("orbital.cube", True),
        ("records.parquet", True),
        ("sub/deep/matrix.h5", True),
        ("sub/deep/wavefunction.gbw", True),
        # Section 4: Telemetry & Execution Logs
        ("orca_run.log", True),
        ("slurm_job.out", True),
        ("error_stream.err", True),
        ("Logs/bench_telemetry.jsonl", True),
        ("Logs/Crash_Dumps/crash.dmp", True),
        ("sub/Logs/output.log", True),
        # Section 5: Python Bytecode & Environments
        ("__pycache__/module.cpython-311.pyc", True),
        ("src/__pycache__/cache.pyc", True),
        ("engine.pyc", True),
        ("engine.pyo", True),
        ("engine.pyd", True),
        ("Class$py.class", True),
        (".env", True),
        (".venv/bin/activate", True),
        (".venv/pyvenv.cfg", True),
        ("cochem_worker_silo/scratch.dat", True),
        ("cochem_hpc_silo/dump.bin", True),
        # Section 6: CI/CD Exception Scoping (!tests/**/*.xyz)
        ("tests/fixtures/water.xyz", False),
        ("tests/ab_initio_fixtures/ch4.xyz", False),
        ("tests/unit/nested/benzene.xyz", False),
        # Allowed Code, Configuration, and Documentation (MUST NOT be ignored)
        ("README.md", False),
        ("Start_BENCH.ipynb", False),
        ("requirements.txt", False),
        ("pyproject.toml", False),
        ("pytest.ini", False),
        (".pre-commit-config.yaml", False),
        ("bench_engine/__init__.py", False),
        ("bench_engine/cochem_bench_ingest.py", False),
        ("bench_engine/cochem_bench_cbs.py", False),
        ("bench_engine/cochem_bench_cv.py", False),
        ("bench_engine/cochem_bench_rel.py", False),
        ("bench_engine/cochem_bench_export.py", False),
        ("bench_libraries/__init__.py", False),
        ("bench_libraries/swmr_hdf5_manager.py", False),
        ("bench_libraries/subprocess_reaper.py", False),
        ("interfaces/__init__.py", False),
        ("interfaces/voila_bench_dashboard.py", False),
        ("interfaces/cochem_bench_telemetry.py", False),
        ("tests/__init__.py", False),
        ("tests/test_extrapolation_math.py", False),
        (".devcontainer/devcontainer.json", False),
        (".devcontainer/setup_tmpfs.sh", False),
        (".github/workflows/cochem_bench_ci.yml", False),
    ],
)
def test_git_check_ignore_physical_evaluation(
    tmp_path: Path, relative_path: str, expected_ignored: bool
) -> None:
    """Validate physical gitignore behavior using an isolated temporary git repository."""
    # Copy raw .gitignore directly to isolated test environment
    (tmp_path / ".gitignore").write_bytes(GITIGNORE_PATH.read_bytes())

    # Initialize a physical git repo in tmp_path
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "CoChem-BENCH-Tester"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "tester@cochem.bench.local"],
        check=True,
        capture_output=True,
    )

    # Create target file path
    target_file = tmp_path / relative_path
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("physical test payload content", encoding="utf-8")

    # Run physical git check-ignore
    proc = subprocess.run(
        ["git", "-C", str(tmp_path), "check-ignore", "-q", relative_path],
        capture_output=True,
    )

    is_ignored = proc.returncode == 0
    assert is_ignored == expected_ignored, (
        f"Path '{relative_path}' expected ignored={expected_ignored}, but got {is_ignored}. "
        f"git check-ignore exit code: {proc.returncode}"
    )