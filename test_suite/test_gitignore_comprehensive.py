"""Comprehensive Zero-Mock Test Suite for CoChem-BASE .gitignore Air-Gap Specifications.

Defends the Tripartite Workspace Air-Gap and repository hygiene by validating:
- Physical existence of .gitignore at repository root.
- Strict UTF-8 encoding (no byte order mark) and Unix LF line endings.
- Exact compliance with SRS Document 1 specifications across all 6 sections.
- Comprehensive physical pattern matching covering all blocked and allowed file types.
- Deep nested directory traversal and execution scratch boundary enforcement.
- Absence of mock objects, dummy stubs, or synthetic bypass mechanisms.
"""

from __future__ import annotations

import ast
import fnmatch
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GITIGNORE_PATH = REPO_ROOT / ".gitignore"

SECTION_1_PATTERNS = [
    "__pycache__/",
    "*.pyc",
    ".ipynb_checkpoints/",
    ".cochem_env/",
]

SECTION_2_PATTERNS = [
    "CoChem_Artifacts/",
    "*/CoChem_Artifacts/*",
    "cochem_exec_*/",
]

SECTION_3_PATTERNS = [
    "*.h5",
    "*.hdf5",
    "*.parquet",
    "*.npy",
    "*.npz",
    "*.db",
    "*.sqlite",
]

SECTION_4_PATTERNS = [
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
]

SECTION_5_PATTERNS = [
    "*.xyz",
    "*.mol",
    "*.smi",
    "*.pdb",
    "*.cif",
]

SECTION_6_PATTERNS = [
    "*config.json",
    "cochem_system_config.json",
    "cochem_audit_log.json",
    "TOPOS_Runtime_State.json",
]

ALL_EXPECTED_PATTERNS = (
    SECTION_1_PATTERNS
    + SECTION_2_PATTERNS
    + SECTION_3_PATTERNS
    + SECTION_4_PATTERNS
    + SECTION_5_PATTERNS
    + SECTION_6_PATTERNS
)

EXPECTED_SECTION_HEADERS = [
    "# 1. Python Cache & Virtual Environments",
    "# 2. Absolute blocking of the Artifacts Workspace & Local Compute Overlap",
    "# 3. Heavy Databases & Quantum Arrays (Prevents repository bloat)",
    "# 4. Execution Scratch, Telemetry Logs, & HPC Residue",
    "# 5. User Chemical Inputs (Protects proprietary user data)",
    "# 6. Local Registries & States (Prevents cross-machine configuration poisoning)",
]


@pytest.fixture(scope="module")
def gitignore_content() -> str:
    """Fixture providing the text content of .gitignore."""
    assert GITIGNORE_PATH.exists(), f"Missing .gitignore at {GITIGNORE_PATH}"
    return GITIGNORE_PATH.read_text(encoding="utf-8")


def test_gitignore_file_attributes() -> None:
    """Validate .gitignore file existence, type, and size bounds."""
    assert GITIGNORE_PATH.exists(), f".gitignore file must exist at {GITIGNORE_PATH}"
    assert GITIGNORE_PATH.is_file(), f"{GITIGNORE_PATH} must be a regular file"
    size = GITIGNORE_PATH.stat().st_size
    assert size > 200, f".gitignore size too small ({size} bytes)"
    assert size < 10000, f".gitignore size unexpectedly large ({size} bytes)"


def test_gitignore_no_bom_and_strict_lf() -> None:
    """Validate UTF-8 encoding without BOM and strict Unix LF line endings."""
    raw_bytes = GITIGNORE_PATH.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), ".gitignore must not contain UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, ".gitignore contains Windows CRLF line endings"
    assert b"\r" not in raw_bytes, ".gitignore contains CR line endings"
    assert b"\n" in raw_bytes, ".gitignore must contain Unix LF line endings"


def test_gitignore_header_and_sections(gitignore_content: str) -> None:
    """Validate top banner and all 6 SRS Document 1 section headers."""
    assert "# ==============================================================================" in gitignore_content
    assert "# CoChem-BASE Strict Air-Gap Constraints" in gitignore_content
    for header in EXPECTED_SECTION_HEADERS:
        assert header in gitignore_content, f"Missing section header in .gitignore: {header}"


def test_gitignore_all_patterns_present(gitignore_content: str) -> None:
    """Validate that every expected pattern is defined in .gitignore."""
    lines = [
        line.strip()
        for line in gitignore_content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    for pattern in ALL_EXPECTED_PATTERNS:
        assert pattern in lines, f"Pattern '{pattern}' missing from .gitignore"


def test_zero_mock_policy_enforcement() -> None:
    """Ensure zero-mock policy across this test file via AST inspection."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "mock" not in alias.name.lower(), f"Forbidden mock import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "mock" not in module.lower(), f"Forbidden mock import: {module}"


# Parameterized test for physical git check-ignore evaluation in a real git environment
@pytest.mark.parametrize(
    "file_rel_path, should_be_ignored, section_label",
    [
        # Section 1
        ("__pycache__/engine.pyc", True, "Sec1: Python Cache"),
        ("src/pkg/__pycache__/sub.pyc", True, "Sec1: Python Cache Nested"),
        ("app.pyc", True, "Sec1: Bytecode"),
        ("deep/pkg/module.pyc", True, "Sec1: Bytecode Nested"),
        (".ipynb_checkpoints/calc-checkpoint.ipynb", True, "Sec1: Notebook Checkpoints"),
        (".cochem_env/pyvenv.cfg", True, "Sec1: Virtual Environment"),
        (".cochem_env/lib/site-packages/test.py", True, "Sec1: Virtual Environment Libs"),
        # Section 2
        ("CoChem_Artifacts/run01/output.txt", True, "Sec2: Artifacts Root"),
        ("nested/dir/CoChem_Artifacts/job1/output.bin", True, "Sec2: Artifacts Subdir"),
        ("cochem_exec_482910/scratch.dat", True, "Sec2: Execution Scratch"),
        ("nested/cochem_exec_gamma/stdout.log", True, "Sec2: Execution Scratch Nested"),
        # Section 3
        ("dataset_01.h5", True, "Sec3: HDF5 (.h5)"),
        ("data/sub/quantum_states.hdf5", True, "Sec3: HDF5 (.hdf5)"),
        ("table.parquet", True, "Sec3: Parquet"),
        ("vectors.npy", True, "Sec3: NumPy Array (.npy)"),
        ("arrays.npz", True, "Sec3: NumPy Archive (.npz)"),
        ("local_cache.db", True, "Sec3: Database (.db)"),
        ("state.sqlite", True, "Sec3: SQLite (.sqlite)"),
        # Section 4
        ("orca_wf.gbw", True, "Sec4: ORCA wavefunction (.gbw)"),
        ("temp_calc.tmp", True, "Sec4: Temp (.tmp)"),
        ("gaussian.chk", True, "Sec4: Checkpoint (.chk)"),
        ("geometry.opt", True, "Sec4: Optimization (.opt)"),
        ("lockfile.lock", True, "Sec4: Lockfile (.lock)"),
        ("server.log", True, "Sec4: Log (.log)"),
        ("output.out", True, "Sec4: Out (.out)"),
        ("stderr.err", True, "Sec4: Err (.err)"),
        ("core.9812", True, "Sec4: Core dump (core.*)"),
        ("slurm-1234567.out", True, "Sec4: Slurm log (slurm-*.out)"),
        ("runinfo/parsl_exec.log", True, "Sec4: Parsl runinfo/"),
        ("pipeline.parsl", True, "Sec4: Parsl state (.parsl)"),
        # Section 5
        ("water_dimer.xyz", True, "Sec5: Chemical XYZ (.xyz)"),
        ("aspirin.mol", True, "Sec5: Chemical MOL (.mol)"),
        ("smiles_library.smi", True, "Sec5: SMILES (.smi)"),
        ("ribosome.pdb", True, "Sec5: Protein PDB (.pdb)"),
        ("zeolite.cif", True, "Sec5: Crystallography CIF (.cif)"),
        ("deep/path/benzene.xyz", True, "Sec5: Chemical XYZ Nested"),
        # Section 6
        ("app_config.json", True, "Sec6: Wildcard config (*config.json)"),
        ("server_config.json", True, "Sec6: Wildcard config (*config.json)"),
        ("cochem_system_config.json", True, "Sec6: Exact cochem_system_config.json"),
        ("cochem_audit_log.json", True, "Sec6: Exact cochem_audit_log.json"),
        ("TOPOS_Runtime_State.json", True, "Sec6: Exact TOPOS_Runtime_State.json"),
        ("sub/folder/local_config.json", True, "Sec6: Nested *config.json"),
        # Standard Allowed Files
        ("main.py", False, "Allowed: Python Main"),
        ("cochem_base/engine.py", False, "Allowed: Python Package"),
        ("tests/test_airgap.py", False, "Allowed: Test File"),
        ("README.md", False, "Allowed: Markdown"),
        ("Method_Matrix.md", False, "Allowed: Method Matrix"),
        ("CoChem_User_Manual.md", False, "Allowed: User Manual"),
        ("pyproject.toml", False, "Allowed: TOML Config"),
        ("pytest.ini", False, "Allowed: Pytest Config"),
        (".pre-commit-config.yaml", False, "Allowed: YAML Config"),
        ("package.json", False, "Allowed: Non-matching JSON"),
        ("manifest.json", False, "Allowed: Non-matching JSON"),
        ("schema.json", False, "Allowed: Non-matching JSON"),
        ("setup.cfg", False, "Allowed: Setup Config"),
        ("Dockerfile", False, "Allowed: Dockerfile"),
    ],
)
def test_git_check_ignore_matrix(
    tmp_path: Path, file_rel_path: str, should_be_ignored: bool, section_label: str
) -> None:
    """Physically test git ignore behavior using git CLI in an isolated sandbox repository."""
    # Copy raw .gitignore directly without mutation
    (tmp_path / ".gitignore").write_bytes(GITIGNORE_PATH.read_bytes())

    # Initialize physical git repository
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Tester"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@domain.com"],
        check=True,
        capture_output=True,
    )

    # Create dummy target file
    target_path = tmp_path / file_rel_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("airgap validation physical file content", encoding="utf-8")

    # Run git check-ignore
    proc = subprocess.run(
        ["git", "-C", str(tmp_path), "check-ignore", "-q", file_rel_path],
        capture_output=True,
    )
    actual_ignored = proc.returncode == 0

    assert actual_ignored == should_be_ignored, (
        f"[{section_label}] Failed for path '{file_rel_path}': "
        f"expected ignored={should_be_ignored}, got {actual_ignored}."
    )


def test_special_characters_and_whitespace_paths(tmp_path: Path) -> None:
    """Validate gitignore rules with spaces, Unicode, and complex path names."""
    # Copy raw .gitignore directly without mutation
    (tmp_path / ".gitignore").write_bytes(GITIGNORE_PATH.read_bytes())
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Tester"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@domain.com"], check=True, capture_output=True)

    test_paths = [
        ("Calculation Folder With Spaces/result.log", True),
        ("Квантовые_Данные/matrix.h5", True),
        ("Chemical Structures (2026)/complex_molecule.xyz", True),
        ("Allowed Code/script_01.py", False),
        ("Documentation & Notes/Architecture.md", False),
    ]

    for rel_p, expect_ign in test_paths:
        p = tmp_path / rel_p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("data", encoding="utf-8")

        proc = subprocess.run(
            ["git", "-C", str(tmp_path), "check-ignore", "-q", rel_p],
            capture_output=True,
        )
        assert (proc.returncode == 0) == expect_ign, f"Failed for path '{rel_p}'"
