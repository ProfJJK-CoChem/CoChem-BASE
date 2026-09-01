"""Unit tests for CoChem-BASE Git configuration (.gitignore).

Validates:
- File existence, UTF-8 encoding (no BOM), and strict Unix LF line endings.
- Exact presence of all 6 SRS Document 1 sections and patterns.
- Physical pattern matching on all blocked file types and directories.
- Non-ignored status for standard source, configuration, and documentation files.
- Absolute Zero-Mock compliance: direct physical file and subprocess inspection.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GITIGNORE_PATH = REPO_ROOT / ".gitignore"

EXPECTED_SECTIONS = [
    "# 1. Python Cache & Virtual Environments",
    "# 2. Absolute blocking of the Artifacts Workspace & Local Compute Overlap",
    "# 3. Heavy Databases & Quantum Arrays (Prevents repository bloat)",
    "# 4. Execution Scratch, Telemetry Logs, & HPC Residue",
    "# 5. User Chemical Inputs (Protects proprietary user data)",
    "# 6. Local Registries & States (Prevents cross-machine configuration poisoning)",
]

EXPECTED_PATTERNS = [
    # Section 1
    "__pycache__/",
    "*.pyc",
    ".ipynb_checkpoints/",
    ".cochem_env/",
    # Section 2
    "CoChem_Artifacts/",
    "*/CoChem_Artifacts/*",
    "cochem_exec_*/",
    # Section 3
    "*.h5",
    "*.hdf5",
    "*.parquet",
    "*.npy",
    "*.npz",
    "*.db",
    "*.sqlite",
    # Section 4
    "*.gbw",
    "*.tmp",
    "*.chk",
    "*.opt",
    "*.lock",
    "*.log",
    "*.out",
    "*.err",
    "core.*",
    "slurm-*.out",
    "runinfo/",
    "*.parsl",
    # Section 5
    "*.xyz",
    "*.mol",
    "*.smi",
    "*.pdb",
    "*.cif",
    # Section 6
    "*config.json",
    "cochem_system_config.json",
    "cochem_audit_log.json",
    "TOPOS_Runtime_State.json",
]


@pytest.fixture
def repo_root() -> Path:
    """Return the absolute path to the CoChem-BASE repository root."""
    return REPO_ROOT


@pytest.fixture
def gitignore_file() -> Path:
    """Return the absolute path to .gitignore and assert existence."""
    assert GITIGNORE_PATH.exists(), f".gitignore does not exist at {GITIGNORE_PATH}"
    return GITIGNORE_PATH


def test_gitignore_exists(repo_root: Path) -> None:
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


def test_gitignore_contains_all_six_sections(gitignore_file: Path) -> None:
    """Validate that all 6 SRS Document 1 section headers are present in .gitignore."""
    content = gitignore_file.read_text(encoding="utf-8")
    assert "# CoChem-BASE Strict Air-Gap Constraints" in content, (
        "Missing main header '# CoChem-BASE Strict Air-Gap Constraints'"
    )
    for section in EXPECTED_SECTIONS:
        assert section in content, f"Missing expected section header: '{section}'"


def test_gitignore_contains_all_patterns(gitignore_file: Path) -> None:
    """Validate that all required patterns from SRS Document 1 are present."""
    content = gitignore_file.read_text(encoding="utf-8")
    lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    for pattern in EXPECTED_PATTERNS:
        assert pattern in lines, f"Required pattern '{pattern}' missing from .gitignore"


def test_zero_mock_compliance_in_tests() -> None:
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
        # Section 1: Python Cache & Virtual Environments
        ("__pycache__/module.cpython-311.pyc", True),
        ("src/__pycache__/cache.pyc", True),
        ("foo.pyc", True),
        ("nested/sub/bar.pyc", True),
        (".ipynb_checkpoints/analysis-checkpoint.ipynb", True),
        (".cochem_env/bin/activate", True),
        (".cochem_env/pyvenv.cfg", True),
        # Section 2: Artifacts Workspace & Local Compute Overlap
        ("CoChem_Artifacts/run_01/output.txt", True),
        ("nested/CoChem_Artifacts/temp.dat", True),
        ("cochem_exec_12345/results.csv", True),
        ("sub/cochem_exec_abc/trace.log", True),
        # Section 3: Heavy Databases & Quantum Arrays
        ("dataset.h5", True),
        ("sub/deep/matrix.hdf5", True),
        ("records.parquet", True),
        ("weights.npy", True),
        ("tensors.npz", True),
        ("cache.db", True),
        ("local.sqlite", True),
        # Section 4: Execution Scratch, Telemetry Logs, & HPC Residue
        ("orca_calc.gbw", True),
        ("calc_temp.tmp", True),
        ("wavefunction.chk", True),
        ("geometry.opt", True),
        ("process.lock", True),
        ("execution.log", True),
        ("slurm_job.out", True),
        ("error_stream.err", True),
        ("core.12345", True),
        ("slurm-987654.out", True),
        ("runinfo/parsl.log", True),
        ("workflow.parsl", True),
        # Section 5: User Chemical Inputs
        ("benzene.xyz", True),
        ("aspirin.mol", True),
        ("ligands.smi", True),
        ("protein_1ubq.pdb", True),
        ("crystal_structure.cif", True),
        # Section 6: Local Registries & States
        ("app_config.json", True),
        ("cochem_system_config.json", True),
        ("cochem_audit_log.json", True),
        ("TOPOS_Runtime_State.json", True),
        # Allowed files (must NOT be ignored)
        ("main.py", False),
        ("src/cochem/engine.py", False),
        ("README.md", False),
        ("Method_Matrix.md", False),
        ("CoChem_User_Manual.md", False),
        ("pyproject.toml", False),
        ("pytest.ini", False),
        (".pre-commit-config.yaml", False),
        ("package.json", False),
        ("schema.json", False),
        ("environment.yml", False),
    ],
)
def test_git_check_ignore_physical_evaluation(
    tmp_path: Path, relative_path: str, expected_ignored: bool
) -> None:
    """Validate physical gitignore behavior using an isolated temporary git repository."""
    # Copy raw .gitignore directly to test environment without mutation
    (tmp_path / ".gitignore").write_bytes(GITIGNORE_PATH.read_bytes())

    # Initialize a physical git repo in tmp_path
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "CoChem-Tester"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "tester@cochem.local"],
        check=True,
        capture_output=True,
    )

    # Create target file path
    target_file = tmp_path / relative_path
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("test content", encoding="utf-8")

    # Run git check-ignore
    proc = subprocess.run(
        ["git", "-C", str(tmp_path), "check-ignore", "-q", relative_path],
        capture_output=True,
    )

    is_ignored = proc.returncode == 0
    assert is_ignored == expected_ignored, (
        f"Path '{relative_path}' expected ignored={expected_ignored}, but got {is_ignored}. "
        f"git check-ignore exit code: {proc.returncode}"
    )
