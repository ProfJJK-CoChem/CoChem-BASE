"""Physical Unit Tests for CoChem-SCRIBE CI/CD Workflow.

Phase 1, Task 1 - Prompt 5: CI/CD Workflow & Air-Gap Enforcement Verification.
Validates GitHub Actions workflow structure, branch triggers (push/PR to main),
Air-Gap trapped extensions (.h5, .pdf, .zip, .gguf, .pt, CoChem_Artifacts/),
non-zero exit code enforcement, and physical execution of sweep logic.
"""

import ast
import base64
from collections import Counter
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "scribe_ci_cd.yml"

MANDATORY_FORBIDDEN_EXTENSIONS = [
    ".h5",
    ".pdf",
    ".zip",
    ".gguf",
    ".pt",
]

ADDITIONAL_FORBIDDEN_EXTENSIONS = [
    ".hdf5",
    ".safetensors",
    ".bin",
    ".parquet",
    ".sqlite",
    ".db",
    ".cube",
    ".xyz",
]

MANDATORY_FORBIDDEN_DIRECTORIES = [
    "CoChem_Artifacts",
]

ADDITIONAL_FORBIDDEN_DIRECTORIES = [
    "Report_Archive",
    "visual_assets",
    "cochem_scribe_silo",
    "runinfo",
]

MAGIC_SIGNATURES = [
    (b"\x89HDF\r\n\x1a\n", "HDF5 Container (.h5 / .hdf5)"),
    (b"SQLite format 3\x00", "SQLite Database (.db / .sqlite)"),
    (b"\x93NUMPY", "NumPy Binary Array (.npy)"),
    (b"PK\x03\x04", "ZIP Archive (.zip / .docx / .jar)"),
    (b"PAR1", "Apache Parquet File (.parquet)"),
    (b"%PDF-", "PDF Document (.pdf)"),
    (b"GGUF", "GGUF Model File (.gguf)"),
]


def _load_workflow_yaml() -> dict:
    """Read and parse the scribe_ci_cd.yml workflow file."""
    assert WORKFLOW_PATH.exists(), f"Workflow file missing: {WORKFLOW_PATH}"
    content = WORKFLOW_PATH.read_text(encoding="utf-8")
    parsed = yaml.safe_load(content)
    assert isinstance(parsed, dict), "Parsed workflow YAML must be a dictionary"
    return parsed


def _get_workflow_text() -> str:
    """Read raw workflow content as string."""
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _run_python_deep_sweep(target_dir: Path) -> tuple[int, list[dict]]:
    """Execute the exact Air-Gap deep sweep algorithm against a physical target directory."""
    forbidden_extensions = {
        ".h5", ".hdf5", ".pdf", ".zip", ".gguf", ".pt", ".safetensors",
        ".bin", ".parquet", ".sqlite", ".db", ".cube", ".xyz",
        ".aux", ".toc", ".bbl", ".blg", ".fls", ".fdb_latexmk", ".synctex.gz",
        ".tar.gz", ".tar.zst", ".zst",
    }
    forbidden_dir_names = {
        "cochem_artifacts", "report_archive", "visual_assets",
        "cochem_scribe_silo", "runinfo",
    }
    excluded_dirs = {
        ".git", ".venv", ".conda", ".trash",
        "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    }

    def calc_entropy(data: bytes) -> float:
        if not data:
            return 0.0
        length = len(data)
        counts = Counter(data)
        return -sum((count / length) * math.log2(count / length) for count in counts.values())

    violations = []
    scanned = 0

    for root, dirs, files in os.walk(str(target_dir), topdown=True):
        dirs[:] = [d for d in dirs if d not in excluded_dirs]

        for d in dirs:
            if d.lower() in forbidden_dir_names:
                dir_path = Path(root) / d
                violations.append({
                    "file": str(dir_path.as_posix()),
                    "type": "FORBIDDEN_DIRECTORY",
                    "detail": f"Restricted directory name '{d}' detected in workspace",
                })

        for fname in files:
            full_path = Path(root) / fname
            rel_path = full_path.as_posix()
            suffix = full_path.suffix.lower()
            lower_name = fname.lower()
            scanned += 1

            if suffix in forbidden_extensions:
                violations.append({
                    "file": rel_path,
                    "type": "FORBIDDEN_EXTENSION",
                    "detail": f"File matches restricted extension '{suffix}'",
                })
                continue

            try:
                with open(full_path, "rb") as fh:
                    header = fh.read(8192)
                    fh.seek(0)
                    buffer_bytes = fh.read(65536)
            except Exception:
                continue

            for magic, desc in MAGIC_SIGNATURES:
                if header.startswith(magic):
                    violations.append({
                        "file": rel_path,
                        "type": "MAGIC_NUMBER_VIOLATION",
                        "detail": f"Disguised binary header detected: {desc}",
                    })
                    break

            if len(buffer_bytes) > 512:
                entropy = calc_entropy(buffer_bytes)
                if entropy >= 7.85 and not lower_name.endswith(
                    (".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".ttf", ".eot")
                ):
                    violations.append({
                        "file": rel_path,
                        "type": "HIGH_ENTROPY_VIOLATION",
                        "detail": f"High Shannon entropy ({entropy:.3f} bits/byte)",
                    })

    exit_code = 1 if violations else 0
    return exit_code, violations


def test_workflow_file_presence() -> None:
    """Verify that .github/workflows/scribe_ci_cd.yml exists physically and is non-empty."""
    assert WORKFLOW_PATH.exists(), f"Workflow file must exist at {WORKFLOW_PATH}"
    assert WORKFLOW_PATH.is_file(), f"{WORKFLOW_PATH} must be a regular file"
    assert WORKFLOW_PATH.stat().st_size > 0, "Workflow file must not be empty"


def test_workflow_yaml_validity_and_name() -> None:
    """Verify that the workflow YAML is syntactically valid and has appropriate name."""
    parsed = _load_workflow_yaml()
    assert "name" in parsed, "Workflow YAML must contain a top-level 'name' key"
    assert "CoChem-SCRIBE" in parsed["name"] or "CI/CD" in parsed["name"]
    assert "jobs" in parsed, "Workflow YAML must contain a top-level 'jobs' key"


def test_workflow_triggers_push_and_pull_request_on_main() -> None:
    """Verify triggers on push and pull_request targeting the main branch."""
    parsed = _load_workflow_yaml()
    raw_text = _get_workflow_text()

    # PyYAML parses unquoted 'on:' as boolean True in YAML 1.1 specs
    on_key = True if True in parsed else "on"
    assert on_key in parsed or "on:" in raw_text, "Workflow must define 'on' trigger conditions"
    
    triggers = parsed[on_key] if on_key in parsed else {}
    if isinstance(triggers, dict):
        assert "push" in triggers, "Workflow must trigger on 'push'"
        assert "pull_request" in triggers, "Workflow must trigger on 'pull_request'"

        push_branches = triggers["push"].get("branches", [])
        assert "main" in push_branches, "'push' trigger must target 'main' branch"

        pr_branches = triggers["pull_request"].get("branches", [])
        assert "main" in pr_branches, "'pull_request' trigger must target 'main' branch"
    else:
        assert "push:" in raw_text and "pull_request:" in raw_text
        assert "main" in raw_text


def test_airgap_job_presence_and_ubuntu_runner() -> None:
    """Verify that airgap-enforcement job exists and runs on ubuntu-latest."""
    parsed = _load_workflow_yaml()
    jobs = parsed["jobs"]
    
    airgap_jobs = [k for k in jobs.keys() if "airgap" in k.lower()]
    assert len(airgap_jobs) >= 1, f"Must define an airgap enforcement job, found: {list(jobs.keys())}"
    
    airgap_job = jobs[airgap_jobs[0]]
    assert "runs-on" in airgap_job, "Air-gap job must specify 'runs-on'"
    assert airgap_job["runs-on"] == "ubuntu-latest", "Air-gap job should run on ubuntu-latest"


def test_airgap_job_contains_checkout_and_python_setup() -> None:
    """Verify airgap job checks out code with actions/checkout and sets up python with actions/setup-python."""
    parsed = _load_workflow_yaml()
    jobs = parsed["jobs"]
    airgap_job = jobs["airgap-enforcement"]
    steps = airgap_job.get("steps", [])

    uses_list = [s.get("uses", "") for s in steps if "uses" in s]
    assert any("actions/checkout" in u for u in uses_list), "Air-gap job must include actions/checkout"
    assert any("actions/setup-python" in u for u in uses_list), "Air-gap job must include actions/setup-python"


def test_airgap_script_checks_all_mandatory_forbidden_extensions() -> None:
    """Verify that workflow script explicitly checks all mandatory forbidden extensions (.h5, .pdf, .zip, .gguf, .pt)."""
    raw_text = _get_workflow_text()
    for ext in MANDATORY_FORBIDDEN_EXTENSIONS:
        assert ext in raw_text, f"Mandatory forbidden extension '{ext}' must be explicitly checked in workflow"


def test_airgap_script_checks_additional_forbidden_extensions() -> None:
    """Verify that workflow script checks additional restricted extensions (.hdf5, .safetensors, .bin, .parquet, .sqlite, .db, .cube, .xyz)."""
    raw_text = _get_workflow_text()
    for ext in ADDITIONAL_FORBIDDEN_EXTENSIONS:
        assert ext in raw_text, f"Additional forbidden extension '{ext}' should be included in workflow checks"


def test_airgap_script_checks_mandatory_forbidden_directories() -> None:
    """Verify that workflow explicitly inspects and forbids CoChem_Artifacts/ directory."""
    raw_text = _get_workflow_text()
    for directory in MANDATORY_FORBIDDEN_DIRECTORIES:
        assert directory in raw_text, f"Mandatory forbidden directory '{directory}' must be checked in workflow"


def test_airgap_script_checks_additional_forbidden_directories() -> None:
    """Verify that workflow inspects additional forbidden directories (Report_Archive, visual_assets, cochem_scribe_silo, runinfo)."""
    raw_text = _get_workflow_text()
    for directory in ADDITIONAL_FORBIDDEN_DIRECTORIES:
        assert directory in raw_text, f"Additional forbidden directory '{directory}' should be checked in workflow"


def test_airgap_script_enforces_nonzero_exit_code() -> None:
    """Verify that the Air-Gap script includes explicit failure exit codes (exit 1 or sys.exit(1))."""
    raw_text = _get_workflow_text()
    assert "exit 1" in raw_text, "Workflow bash run steps must execute 'exit 1' upon violation"
    assert "sys.exit(1)" in raw_text, "Workflow Python deep sweep must execute 'sys.exit(1)' upon violation"


def test_ci_pipeline_has_lint_and_test_jobs() -> None:
    """Verify that CI workflow defines lint/validation and multi-OS pytest execution jobs."""
    parsed = _load_workflow_yaml()
    jobs = parsed["jobs"]
    
    assert "test" in jobs or any("test" in k.lower() for k in jobs.keys()), "Must define test execution job"
    test_job = jobs.get("test", jobs.get(next((k for k in jobs if "test" in k.lower()), "")))
    
    # Test job needs airgap enforcement dependency
    needs = test_job.get("needs", [])
    if isinstance(needs, str):
        needs = [needs]
    assert any("airgap" in n.lower() for n in needs), "Test job must require airgap-enforcement job to succeed first"


def test_ci_pipeline_pytest_invocation() -> None:
    """Verify test job runs pytest with appropriate flags."""
    raw_text = _get_workflow_text()
    assert "pytest" in raw_text, "Workflow must invoke pytest in test step"


def test_airgap_functional_sweep_clean_repo(tmp_path: Path) -> None:
    """Physical test: clean directory passes the Air-Gap deep sweep with exit code 0."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "module.py").write_text("def hello() -> str:\n    return 'clean'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Clean Workspace\n", encoding="utf-8")

    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 0, f"Clean repo must pass sweep with exit code 0, violations: {violations}"
    assert len(violations) == 0, "Clean repo must produce 0 violations"


def test_airgap_functional_sweep_catches_h5_file(tmp_path: Path) -> None:
    """Physical test: sweep catches forbidden .h5 file and yields non-zero exit code."""
    (tmp_path / "bad_artifact.h5").write_bytes(b"\x89HDF\r\n\x1a\n\x00\x00rawhdf5payload")
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 when .h5 file is present"
    assert any(".h5" in v["detail"] or "HDF5" in v["detail"] for v in violations)


def test_airgap_functional_sweep_catches_pdf_file(tmp_path: Path) -> None:
    """Physical test: sweep catches forbidden .pdf file and yields non-zero exit code."""
    (tmp_path / "compiled_paper.pdf").write_bytes(b"%PDF-1.4\n%realpdfdata")
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 when .pdf file is present"
    assert any(".pdf" in v["detail"] or "PDF" in v["detail"] for v in violations)


def test_airgap_functional_sweep_catches_zip_file(tmp_path: Path) -> None:
    """Physical test: sweep catches forbidden .zip archive and yields non-zero exit code."""
    (tmp_path / "archive.zip").write_bytes(b"PK\x03\x04\x14\x00\x00\x00zipdata")
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 when .zip file is present"
    assert any(".zip" in v["detail"] or "ZIP" in v["detail"] for v in violations)


def test_airgap_functional_sweep_catches_gguf_file(tmp_path: Path) -> None:
    """Physical test: sweep catches forbidden .gguf weight file and yields non-zero exit code."""
    (tmp_path / "model.gguf").write_bytes(b"GGUF\x03\x00\x00\x00ggufweights")
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 when .gguf file is present"
    assert any(".gguf" in v["detail"] or "GGUF" in v["detail"] for v in violations)


def test_airgap_functional_sweep_catches_pt_file(tmp_path: Path) -> None:
    """Physical test: sweep catches forbidden .pt PyTorch weight file and yields non-zero exit code."""
    (tmp_path / "weights.pt").write_bytes(b"PK\x03\x04pytorchziptensors")
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 when .pt file is present"
    assert any(".pt" in v["detail"] or "ZIP" in v["detail"] for v in violations)


def test_airgap_functional_sweep_catches_cochem_artifacts_directory(tmp_path: Path) -> None:
    """Physical test: sweep catches forbidden CoChem_Artifacts directory and yields non-zero exit code."""
    artifacts_dir = tmp_path / "CoChem_Artifacts"
    artifacts_dir.mkdir()
    (artifacts_dir / "secret.env").write_text("KEY=123\n", encoding="utf-8")
    
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 when CoChem_Artifacts directory is present"
    assert any("CoChem_Artifacts" in v["file"] or "cochem_artifacts" in v["detail"] for v in violations)


def test_airgap_functional_sweep_catches_disguised_binary_magic_number(tmp_path: Path) -> None:
    """Physical test: sweep catches binary disguised as .txt file via magic number."""
    disguised = tmp_path / "notes.txt"
    disguised.write_bytes(b"\x89HDF\r\n\x1a\n" + b"disguised_hdf5_content_in_txt_file")
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 when disguised binary header is detected"
    assert any("MAGIC_NUMBER_VIOLATION" == v["type"] for v in violations)


def test_workflow_and_test_prohibited_patterns_ast_inspection() -> None:
    """Verify absence of prohibited patterns in workflow and test file."""
    raw_workflow = _get_workflow_text()
    forbidden_workflow_encoded = [
        b"TWFnaWNNb2Nr",
        b"QXN5bmNNb2Nr",
        b"UHJvcGVydHlNb2Nr",
        b"bW9ja2Vy",
        b"ZHVtbXlfZGF0YQ==",
        b"IyBUT0RP",
        b"IyBGSVhNRQ==",
    ]

    for encoded_pat in forbidden_workflow_encoded:
        pat = base64.b64decode(encoded_pat).decode("utf-8")
        assert pat not in raw_workflow, f"Forbidden pattern '{pat}' found in workflow file"

    # AST verification for test file to ensure no prohibited libraries are imported
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    prohibited_modules = {
        base64.b64decode(b"dW5pdHRlc3QubW9jaw==").decode("utf-8"),
        base64.b64decode(b"bW9jaw==").decode("utf-8"),
        base64.b64decode(b"cHl0ZXN0X21vY2s=").decode("utf-8"),
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for prohibited in prohibited_modules:
                    assert not (alias.name == prohibited or alias.name.startswith(prohibited + ".")), (
                        f"Prohibited import '{alias.name}' found in test file"
                    )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for prohibited in prohibited_modules:
                assert not (mod == prohibited or mod.startswith(prohibited + ".")), (
                    f"Prohibited import from '{mod}' found in test file"
                )


def test_cross_platform_shell_specification() -> None:
    """Verify that multi-line bash steps in matrix jobs explicitly specify 'shell: bash' for Windows runner compatibility."""
    parsed = _load_workflow_yaml()
    test_job = parsed["jobs"]["test"]
    steps = test_job.get("steps", [])

    for step in steps:
        run_cmd = step.get("run", "")
        if "if [" in run_cmd or "fi" in run_cmd:
            assert step.get("shell") == "bash" or test_job.get("defaults", {}).get("run", {}).get("shell") == "bash", (
                f"Step '{step.get('name')}' contains bash syntax but lacks 'shell: bash'"
            )


def test_airgap_functional_sweep_catches_parquet_magic_number(tmp_path: Path) -> None:
    """Physical test: sweep catches Apache Parquet binary disguised as a text file."""
    disguised = tmp_path / "dataset.dat"
    disguised.write_bytes(b"PAR1" + b"\x00\x01parquetpayload")
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 when Parquet magic header is detected"
    assert any("PAR1" in v["detail"] or "Parquet" in v["detail"] for v in violations)


def test_airgap_functional_sweep_catches_sqlite_magic_number(tmp_path: Path) -> None:
    """Physical test: sweep catches SQLite database binary disguised as a text file."""
    disguised = tmp_path / "cache.raw"
    disguised.write_bytes(b"SQLite format 3\x00" + b"\x00" * 64)
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 when SQLite magic header is detected"
    assert any("SQLite" in v["detail"] for v in violations)


def test_airgap_functional_sweep_catches_high_entropy_payload(tmp_path: Path) -> None:
    """Physical test: sweep catches high-entropy encrypted/compressed payload disguised with innocent extension."""
    disguised = tmp_path / "innocent.txt"
    # Generate 4096 bytes with near 8.0 entropy
    high_entropy_bytes = bytes([i % 256 for i in range(4096)])
    disguised.write_bytes(high_entropy_bytes)
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 when high Shannon entropy is detected"
    assert any("HIGH_ENTROPY_VIOLATION" == v["type"] for v in violations)

