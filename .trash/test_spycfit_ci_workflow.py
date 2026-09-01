"""Zero-Mock Production Test Suite for CoChem-SpycFit CI Workflow (cochem_spycfit_ci.yml).

Defends the Execution Tier build system and Tripartite Architecture air-gap by validating:
- Physical existence of cochem_spycfit_ci.yml at CoChem-SpycFit/.github/workflows/cochem_spycfit_ci.yml.
- Strict UTF-8 encoding (no byte order mark) and Unix LF line endings.
- Exact compliance with SRS Document specifications for CI workflow configuration.
- YAML syntax validity and schema parsing using yaml.safe_load.
- Workflow name: "CoChem-SpycFit CI".
- Trigger conditions: push, pull_request.
- Job matrix and runner: air_gap_enforcement on ubuntu-latest.
- Steps structure: actions/checkout@v4 and Tripartite Air-Gap Enforcement Scan.
- Exact shell scan command logic for detecting *.h5, *.parquet, *.fit, *.lin, *.lock while pruning test_fixtures.
- Physical execution and simulation of the air-gap scan logic against real temporary directory structures.
- Strict exclusion of mock/placeholder tokens and AST inspection for zero-mock compliance.
"""

from __future__ import annotations

import ast
import datetime
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Set

import pytest
import yaml

# Repository paths
BASE_REPO_ROOT = Path(__file__).resolve().parent.parent
SPYCFIT_REPO_ROOT = BASE_REPO_ROOT.parent / "CoChem-SpycFit"
SPYCFIT_WORKFLOWS_DIR = SPYCFIT_REPO_ROOT / ".github" / "workflows"
SPYCFIT_CI_WORKFLOW_PATH = SPYCFIT_WORKFLOWS_DIR / "cochem_spycfit_ci.yml"

# Canonical SRS workflow content
CANONICAL_CI_WORKFLOW_CONTENT = (
    "name: CoChem-SpycFit CI\n"
    "on: [push, pull_request]\n"
    "\n"
    "jobs:\n"
    "  air_gap_enforcement:\n"
    "    runs-on: ubuntu-latest\n"
    "    steps:\n"
    "      - uses: actions/checkout@v4\n"
    "      - name: Tripartite Air-Gap Enforcement Scan\n"
    "        run: |\n"
    '          echo "Scanning for Tier 2/Tier 3 artifacts outside tests/ directory..."\n'
    '          matches=$(find . -type d -name "test_fixtures" -prune -o \\( -name "*.h5" -o -name "*.parquet" -o -name "*.fit" -o -name "*.lin" -o -name "*.lock" \\) -print)\n'
    '          if [ ! -z "$matches" ]; then\n'
    '            echo "CRITICAL: Tripartite Air-Gap Breach. State (Tier 3) or Data (Tier 2) artifacts detected in the Immutable Execution Tier (Tier 1)."\n'
    '            echo "$matches"\n'
    "            exit 1\n"
    "          fi\n"
    '          echo "Air-Gap intact."\n'
)

EXPECTED_WORKFLOW_NAME = "CoChem-SpycFit CI"
EXPECTED_ON_TRIGGERS = ["push", "pull_request"]
EXPECTED_JOB_NAME = "air_gap_enforcement"
EXPECTED_RUNS_ON = "ubuntu-latest"
EXPECTED_CHECKOUT_ACTION = "actions/checkout@v4"
EXPECTED_SCAN_STEP_NAME = "Tripartite Air-Gap Enforcement Scan"

RESTRICTED_EXTENSIONS = [".h5", ".parquet", ".fit", ".lin", ".lock"]
ALLOWED_CODE_EXTENSIONS = [".py", ".md", ".toml", ".yml", ".yaml", ".json", ".txt", ".sh", ".rs", ".cpp", ".c", ".h"]
WHITELISTED_FIXTURE_DIRNAME = "test_fixtures"

CRITICAL_BREACH_MESSAGE = (
    "CRITICAL: Tripartite Air-Gap Breach. State (Tier 3) or Data (Tier 2) "
    "artifacts detected in the Immutable Execution Tier (Tier 1)."
)
AIR_GAP_INTACT_MESSAGE = "Air-Gap intact."


def find_bash_executable() -> str | None:
    """Locate a valid bash binary on Windows or Unix for physical script execution."""
    git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    if git_bash.exists():
        return str(git_bash)
    git_usr_bash = Path(r"C:\Program Files\Git\usr\bin\bash.exe")
    if git_usr_bash.exists():
        return str(git_usr_bash)
    which_bash = shutil.which("bash")
    if which_bash:
        return which_bash
    which_sh = shutil.which("sh")
    if which_sh:
        return which_sh
    return None


@pytest.fixture(scope="module")
def workflow_raw_bytes() -> bytes:
    """Fixture providing raw bytes of cochem_spycfit_ci.yml."""
    assert SPYCFIT_CI_WORKFLOW_PATH.exists(), (
        f"Missing workflow file at {SPYCFIT_CI_WORKFLOW_PATH}"
    )
    return SPYCFIT_CI_WORKFLOW_PATH.read_bytes()


@pytest.fixture(scope="module")
def workflow_content(workflow_raw_bytes: bytes) -> str:
    """Fixture providing decoded text content of cochem_spycfit_ci.yml."""
    return workflow_raw_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def workflow_data(workflow_content: str) -> Dict[str, Any]:
    """Fixture providing parsed YAML dictionary."""
    data = yaml.safe_load(workflow_content)
    assert isinstance(data, dict), "Parsed YAML root must be a dictionary"
    return data


# ==============================================================================
# 1. Physical File Integrity & Line Endings
# ==============================================================================


def test_spycfit_ci_workflow_directory_exists() -> None:
    """Validate that .github/workflows directory exists in CoChem-SpycFit."""
    assert SPYCFIT_WORKFLOWS_DIR.exists(), f"Workflows directory missing: {SPYCFIT_WORKFLOWS_DIR}"
    assert SPYCFIT_WORKFLOWS_DIR.is_dir(), f"Workflows path must be a directory: {SPYCFIT_WORKFLOWS_DIR}"


def test_spycfit_ci_workflow_existence_and_size() -> None:
    """Validate that cochem_spycfit_ci.yml physically exists with valid size bounds."""
    assert SPYCFIT_CI_WORKFLOW_PATH.exists(), (
        f"Target file must exist: {SPYCFIT_CI_WORKFLOW_PATH}"
    )
    assert SPYCFIT_CI_WORKFLOW_PATH.is_file(), (
        f"Target path must be a regular file: {SPYCFIT_CI_WORKFLOW_PATH}"
    )
    size = SPYCFIT_CI_WORKFLOW_PATH.stat().st_size
    assert 200 < size < 5000, (
        f"cochem_spycfit_ci.yml size ({size} bytes) outside expected range (200, 5000)"
    )


def test_spycfit_ci_workflow_encoding_and_lf_line_endings(workflow_raw_bytes: bytes) -> None:
    """Validate strict UTF-8 encoding without BOM and Unix LF line endings."""
    assert not workflow_raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "Target file must not contain a UTF-8 BOM"
    )
    assert b"\r\n" not in workflow_raw_bytes, "Target file contains Windows CRLF line endings"
    assert b"\r" not in workflow_raw_bytes, "Target file contains carriage return line endings"
    assert b"\n" in workflow_raw_bytes, "Target file must contain Unix LF line endings"
    assert workflow_raw_bytes.endswith(b"\n"), "Target file must terminate with a Unix LF newline"
    decoded = workflow_raw_bytes.decode("utf-8")
    assert len(decoded) > 0, "Target file content cannot be empty"


def test_spycfit_ci_workflow_canonical_content(workflow_content: str) -> None:
    """Validate that cochem_spycfit_ci.yml strictly matches the canonical SRS specification."""
    assert workflow_content == CANONICAL_CI_WORKFLOW_CONTENT, (
        f"cochem_spycfit_ci.yml content differs from canonical SRS specification:\n"
        f"--- Got ---\n{workflow_content}\n"
        f"--- Expected ---\n{CANONICAL_CI_WORKFLOW_CONTENT}"
    )


# ==============================================================================
# 2. YAML Schema & Workflow Structure
# ==============================================================================


def test_spycfit_ci_workflow_name(workflow_data: Dict[str, Any]) -> None:
    """Validate the workflow name is 'CoChem-SpycFit CI'."""
    assert "name" in workflow_data, "Missing 'name' field in workflow YAML"
    assert workflow_data["name"] == EXPECTED_WORKFLOW_NAME, (
        f"Expected workflow name '{EXPECTED_WORKFLOW_NAME}', got '{workflow_data['name']}'"
    )


def test_spycfit_ci_workflow_triggers(workflow_data: Dict[str, Any]) -> None:
    """Validate workflow trigger conditions contain push and pull_request."""
    # YAML parses `on: [push, pull_request]` as either key True/on or "on"
    trigger_key = "on" if "on" in workflow_data else True
    assert trigger_key in workflow_data, "Missing 'on' trigger specification in workflow YAML"
    triggers = workflow_data[trigger_key]
    assert isinstance(triggers, list), "Trigger specification must be a list"
    assert triggers == EXPECTED_ON_TRIGGERS, (
        f"Expected triggers {EXPECTED_ON_TRIGGERS}, got {triggers}"
    )


def test_spycfit_ci_workflow_jobs_structure(workflow_data: Dict[str, Any]) -> None:
    """Validate jobs dictionary structure and air_gap_enforcement job."""
    assert "jobs" in workflow_data, "Missing 'jobs' section in workflow YAML"
    jobs = workflow_data["jobs"]
    assert isinstance(jobs, dict), "'jobs' section must be a dictionary"
    assert EXPECTED_JOB_NAME in jobs, f"Missing '{EXPECTED_JOB_NAME}' job in jobs"

    job = jobs[EXPECTED_JOB_NAME]
    assert isinstance(job, dict), f"Job '{EXPECTED_JOB_NAME}' must be a dictionary"
    assert "runs-on" in job, f"Missing 'runs-on' in job '{EXPECTED_JOB_NAME}'"
    assert job["runs-on"] == EXPECTED_RUNS_ON, (
        f"Expected runs-on '{EXPECTED_RUNS_ON}', got '{job['runs-on']}'"
    )
    assert "steps" in job, f"Missing 'steps' in job '{EXPECTED_JOB_NAME}'"
    assert isinstance(job["steps"], list), "'steps' must be a list"
    assert len(job["steps"]) == 2, f"Expected exactly 2 steps, found {len(job['steps'])}"


def test_spycfit_ci_workflow_steps_detail(workflow_data: Dict[str, Any]) -> None:
    """Validate individual steps in air_gap_enforcement job."""
    steps = workflow_data["jobs"][EXPECTED_JOB_NAME]["steps"]

    # Step 1: Checkout
    step1 = steps[0]
    assert isinstance(step1, dict), "Step 1 must be a dictionary"
    assert "uses" in step1, "Step 1 must define 'uses'"
    assert step1["uses"] == EXPECTED_CHECKOUT_ACTION, (
        f"Expected Step 1 uses '{EXPECTED_CHECKOUT_ACTION}', got '{step1['uses']}'"
    )

    # Step 2: Tripartite Air-Gap Enforcement Scan
    step2 = steps[1]
    assert isinstance(step2, dict), "Step 2 must be a dictionary"
    assert "name" in step2, "Step 2 must define 'name'"
    assert step2["name"] == EXPECTED_SCAN_STEP_NAME, (
        f"Expected Step 2 name '{EXPECTED_SCAN_STEP_NAME}', got '{step2['name']}'"
    )
    assert "run" in step2, "Step 2 must define 'run' script"
    assert isinstance(step2["run"], str), "Step 2 'run' must be a string"


# ==============================================================================
# 3. Air-Gap Scan Script Logic & Token Verification
# ==============================================================================


def test_spycfit_ci_workflow_scan_script_syntax_and_commands(workflow_data: Dict[str, Any]) -> None:
    """Validate that the scan script contains exact required commands and syntax."""
    run_script = workflow_data["jobs"][EXPECTED_JOB_NAME]["steps"][1]["run"]

    assert "find ." in run_script, "Scan script must invoke 'find .'"
    assert '-type d -name "test_fixtures" -prune' in run_script, (
        "Scan script must prune directories named 'test_fixtures'"
    )

    # Check all 5 restricted extensions in find expression
    for ext in RESTRICTED_EXTENSIONS:
        assert f'"{ext}"' in run_script or f'"*{ext}"' in run_script, (
            f"Scan script missing filter for restricted extension '{ext}'"
        )

    # Check conditional failure and messages
    assert 'if [ ! -z "$matches" ]; then' in run_script, "Scan script missing match non-empty test"
    assert "CRITICAL: Tripartite Air-Gap Breach" in run_script, "Missing air-gap breach alert"
    assert "exit 1" in run_script, "Scan script must exit 1 on air-gap breach"
    assert "Air-Gap intact." in run_script, "Scan script must confirm 'Air-Gap intact.'"


def test_spycfit_ci_workflow_no_forbidden_tokens(workflow_content: str) -> None:
    """Validate that cochem_spycfit_ci.yml contains no mock, dummy, or synthetic tokens."""
    forbidden_tokens = [
        "TODO",
        "FIXME",
        "mock",
        "dummy",
        "fake",
        "synthetic",
        "stub",
        "placeholder",
        "TEMPORARY",
    ]
    for token in forbidden_tokens:
        assert token.lower() not in workflow_content.lower(), (
            f"cochem_spycfit_ci.yml contains forbidden placeholder token '{token}'"
        )


# ==============================================================================
# 4. Physical Simulation & Execution of Air-Gap Scan
# ==============================================================================


def execute_python_airgap_scan(root_dir: Path) -> List[Path]:
    """Pure Python implementation replicating the exact semantics of the find command.

    find . -type d -name "test_fixtures" -prune -o \\( -name "*.h5" -o -name "*.parquet" -o -name "*.fit" -o -name "*.lin" -o -name "*.lock" \\) -print
    """
    matches: List[Path] = []
    restricted_suffixes = {ext.lower() for ext in RESTRICTED_EXTENSIONS}

    for dirpath_str, dirnames, filenames in os.walk(root_dir):
        # Prune test_fixtures directory subtrees
        dirnames[:] = [d for d in dirnames if d != WHITELISTED_FIXTURE_DIRNAME]

        for fname in filenames:
            ext = Path(fname).suffix.lower()
            if ext in restricted_suffixes:
                full_path = Path(dirpath_str) / fname
                rel_path = full_path.relative_to(root_dir)
                matches.append(rel_path)

    return sorted(matches)


def test_python_airgap_scan_clean_workspace(tmp_path: Path) -> None:
    """Test Python airgap scanner on clean workspace with whitelisted fixtures."""
    src_dir = tmp_path / "src" / "cochem_spycfit"
    src_dir.mkdir(parents=True)
    (src_dir / "core.py").write_text("print('core')", encoding="utf-8")
    (src_dir / "pyproject.toml").write_text("[project]", encoding="utf-8")

    fixtures_dir = tmp_path / "tests" / "test_fixtures"
    fixtures_dir.mkdir(parents=True)
    (fixtures_dir / "reference.h5").write_bytes(b"DATA")
    (fixtures_dir / "table.parquet").write_bytes(b"DATA")
    (fixtures_dir / "fit_result.fit").write_bytes(b"DATA")
    (fixtures_dir / "lines.lin").write_bytes(b"DATA")
    (fixtures_dir / "build.lock").write_bytes(b"DATA")

    matches = execute_python_airgap_scan(tmp_path)
    assert len(matches) == 0, f"Expected 0 matches in clean workspace, got {matches}"


@pytest.mark.parametrize("allowed_ext", ALLOWED_CODE_EXTENSIONS)
def test_python_airgap_scan_ignores_allowed_extensions(tmp_path: Path, allowed_ext: str) -> None:
    """Test Python airgap scanner ignores standard source code and config files."""
    code_dir = tmp_path / "allowed_test"
    code_dir.mkdir(parents=True, exist_ok=True)
    (code_dir / f"test_module{allowed_ext}").write_text("allowed content", encoding="utf-8")

    matches = execute_python_airgap_scan(code_dir)
    assert len(matches) == 0, f"Expected 0 matches for allowed file '{allowed_ext}', got {matches}"


@pytest.mark.parametrize("restricted_ext", RESTRICTED_EXTENSIONS)
def test_python_airgap_scan_detects_breach(tmp_path: Path, restricted_ext: str) -> None:
    """Test Python airgap scanner detects each restricted extension outside test_fixtures."""
    test_dir = tmp_path / f"test_{restricted_ext.replace('.', '')}"
    test_dir.mkdir(parents=True, exist_ok=True)

    # Valid file in test_fixtures
    fixtures_dir = test_dir / "test_fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    (fixtures_dir / f"allowed{restricted_ext}").write_bytes(b"ALLOWED")

    # Breach file outside test_fixtures
    breach_file = test_dir / "src" / f"unauthorized{restricted_ext}"
    breach_file.parent.mkdir(parents=True, exist_ok=True)
    breach_file.write_bytes(b"BREACH")

    matches = execute_python_airgap_scan(test_dir)
    assert len(matches) == 1, f"Expected exactly 1 breach match for {restricted_ext}, got {matches}"
    assert matches[0] == Path("src") / f"unauthorized{restricted_ext}"


def test_python_airgap_scan_deeply_nested_fixtures_pruned(tmp_path: Path) -> None:
    """Test nested directories inside test_fixtures are properly pruned."""
    test_dir = tmp_path / "nested_fixtures"
    nested_fixture = test_dir / "tests" / "unit" / "test_fixtures" / "deep_sub" / "data"
    nested_fixture.mkdir(parents=True, exist_ok=True)
    (nested_fixture / "sample.h5").write_bytes(b"H5")
    (nested_fixture / "sample.parquet").write_bytes(b"PARQUET")
    (nested_fixture / "sample.fit").write_bytes(b"FIT")
    (nested_fixture / "sample.lin").write_bytes(b"LIN")
    (nested_fixture / "sample.lock").write_bytes(b"LOCK")

    matches = execute_python_airgap_scan(test_dir)
    assert len(matches) == 0, f"Expected 0 matches in nested test_fixtures, got {matches}"


def test_python_airgap_scan_multiple_breaches(tmp_path: Path) -> None:
    """Test Python airgap scanner detects multiple simultaneous breaches across directories."""
    test_dir = tmp_path / "multi_breach"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "root.h5").write_bytes(b"H5")
    (test_dir / "src").mkdir(parents=True, exist_ok=True)
    (test_dir / "src" / "state.parquet").write_bytes(b"PARQUET")
    (test_dir / "data").mkdir(parents=True, exist_ok=True)
    (test_dir / "data" / "output.fit").write_bytes(b"FIT")
    (test_dir / "data" / "lines.lin").write_bytes(b"LIN")
    (test_dir / "state.lock").write_bytes(b"LOCK")

    matches = execute_python_airgap_scan(test_dir)
    assert len(matches) == 5, f"Expected 5 breach matches, got {len(matches)}: {matches}"


def test_physical_bash_airgap_scan_execution(tmp_path: Path, workflow_data: Dict[str, Any]) -> None:
    """Physical execution of the exact shell script extracted from the YAML workflow."""
    bash_exec = find_bash_executable()
    if bash_exec is None:
        pytest.skip("Bash executable not available on host system for direct shell invocation")

    run_script = workflow_data["jobs"][EXPECTED_JOB_NAME]["steps"][1]["run"]

    # 1. Clean workspace test
    clean_workspace = tmp_path / "clean_ws"
    clean_workspace.mkdir(parents=True)
    (clean_workspace / "main.py").write_text("print('hello')", encoding="utf-8")
    (clean_workspace / "README.md").write_text("# Readme", encoding="utf-8")
    fixtures = clean_workspace / "tests" / "test_fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "allowed.h5").write_bytes(b"HDF5_DATA")
    (fixtures / "allowed.parquet").write_bytes(b"PARQUET_DATA")
    (fixtures / "allowed.fit").write_bytes(b"FIT_DATA")
    (fixtures / "allowed.lin").write_bytes(b"LIN_DATA")
    (fixtures / "allowed.lock").write_bytes(b"LOCK_DATA")

    clean_res = subprocess.run(
        [bash_exec, "-c", run_script],
        cwd=str(clean_workspace),
        capture_output=True,
        text=True,
    )
    assert clean_res.returncode == 0, (
        f"Clean workspace scan failed unexpectedly with exit code {clean_res.returncode}:\n"
        f"stdout: {clean_res.stdout}\nstderr: {clean_res.stderr}"
    )
    assert AIR_GAP_INTACT_MESSAGE in clean_res.stdout
    assert "CRITICAL: Tripartite Air-Gap Breach" not in clean_res.stdout

    # 2. Breach workspace test
    breach_workspace = tmp_path / "breach_ws"
    breach_workspace.mkdir(parents=True)
    (breach_workspace / "module.py").write_text("print('module')", encoding="utf-8")
    (breach_workspace / "rogue_state.h5").write_bytes(b"BREACH_HDF5")
    (breach_workspace / "data.parquet").write_bytes(b"BREACH_PARQUET")

    breach_res = subprocess.run(
        [bash_exec, "-c", run_script],
        cwd=str(breach_workspace),
        capture_output=True,
        text=True,
    )
    assert breach_res.returncode == 1, (
        f"Breached workspace scan should exit 1, got {breach_res.returncode}:\n"
        f"stdout: {breach_res.stdout}\nstderr: {breach_res.stderr}"
    )
    assert "CRITICAL: Tripartite Air-Gap Breach" in breach_res.stdout
    assert "rogue_state.h5" in breach_res.stdout
    assert "data.parquet" in breach_res.stdout
    assert AIR_GAP_INTACT_MESSAGE not in breach_res.stdout


# ==============================================================================
# 5. AST Zero-Mock Audit
# ==============================================================================


def test_test_suite_zero_mock_ast_inspection() -> None:
    """Validate zero-mock compliance across this test suite via AST analysis."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "mock" not in alias.name.lower(), (
                    f"Forbidden mock import in test suite: '{alias.name}'"
                )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "mock" not in mod.lower(), (
                f"Forbidden mock import in test suite from module: '{mod}'"
            )
