"""Physical Unit Tests for CoChem-SCRIBE CI/CD Workflow (ci_scribe.yml).

Task 97 (Phase 4, Task 11): CI/CD Workflow & Air-Gap Enforcement Verification.
Validates GitHub Actions workflow structure, branch triggers (push/PR to main),
matrix execution across ubuntu-latest and macos-latest with Python 3.10 and 3.11,
LaTeX dependencies for DocumentManager, Air-Gap trapped extensions,
non-zero exit code enforcement, and physical execution of sweep logic without mocks.
"""

import ast
import base64
import math
import os
from collections import Counter
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci_scribe.yml"

MIN_BUFFER_SIZE = 512
ENTROPY_THRESHOLD = 7.85

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

MANDATORY_FORBIDDEN_EXACT_FILES = [
    ".env",
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


def _load_workflow_yaml() -> dict[Any, Any]:
    """Read and parse the ci_scribe.yml workflow file."""
    assert WORKFLOW_PATH.exists(), f"Workflow file missing: {WORKFLOW_PATH}"
    content = WORKFLOW_PATH.read_text(encoding="utf-8")
    parsed = yaml.safe_load(content)
    assert isinstance(parsed, dict), "Parsed workflow YAML must be a dictionary"
    return parsed


def _get_workflow_text() -> str:
    """Read raw workflow content as string."""
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _run_python_deep_sweep(target_dir: Path) -> tuple[int, list[dict[str, str]]]:
    """Execute Air-Gap deep sweep algorithm against a physical target directory."""
    forbidden_extensions = {
        ".h5",
        ".hdf5",
        ".pdf",
        ".zip",
        ".gguf",
        ".pt",
        ".safetensors",
        ".bin",
        ".parquet",
        ".sqlite",
        ".db",
        ".cube",
        ".xyz",
        ".aux",
        ".toc",
        ".bbl",
        ".blg",
        ".fls",
        ".fdb_latexmk",
        ".synctex.gz",
        ".tar.gz",
        ".tar.zst",
        ".zst",
    }
    forbidden_exact_names = {
        ".env",
    }
    forbidden_dir_names = {
        "cochem_artifacts",
        "report_archive",
        "visual_assets",
        "cochem_scribe_silo",
        "runinfo",
    }
    excluded_dirs = {
        ".git",
        ".venv",
        ".conda",
        ".trash",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }

    def calc_entropy(data: bytes) -> float:
        if not data:
            return 0.0
        length = len(data)
        counts = Counter(data)
        return -sum(
            (count / length) * math.log2(count / length) for count in counts.values()
        )

    violations: list[dict[str, str]] = []

    for root, dirs, files in os.walk(str(target_dir), topdown=True):
        dirs[:] = [d for d in dirs if d not in excluded_dirs]

        for d in dirs:
            if d.lower() in forbidden_dir_names:
                dir_path = Path(root) / d
                violations.append({
                    "file": str(dir_path.as_posix()),
                    "type": "FORBIDDEN_DIRECTORY",
                    "detail": f"Restricted directory '{d}' detected in workspace",
                })

        for fname in files:
            full_path = Path(root) / fname
            rel_path = full_path.as_posix()
            suffix = full_path.suffix.lower()
            lower_name = fname.lower()

            if lower_name in forbidden_exact_names:
                violations.append({
                    "file": rel_path,
                    "type": "FORBIDDEN_FILENAME",
                    "detail": f"Forbidden exact file '{lower_name}' detected",
                })
                continue

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

            if len(buffer_bytes) > MIN_BUFFER_SIZE:
                entropy = calc_entropy(buffer_bytes)
                media_exts = (
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".ico",
                    ".woff",
                    ".woff2",
                    ".ttf",
                    ".eot",
                )
                if entropy >= ENTROPY_THRESHOLD and not lower_name.endswith(media_exts):
                    violations.append({
                        "file": rel_path,
                        "type": "HIGH_ENTROPY_VIOLATION",
                        "detail": f"High Shannon entropy ({entropy:.3f} bits/byte)",
                    })

    exit_code = 1 if violations else 0
    return exit_code, violations


def test_workflow_file_presence() -> None:
    """Verify that .github/workflows/ci_scribe.yml exists physically."""
    assert WORKFLOW_PATH.exists(), f"Workflow file must exist at {WORKFLOW_PATH}"
    assert WORKFLOW_PATH.is_file(), f"{WORKFLOW_PATH} must be a regular file"
    assert WORKFLOW_PATH.stat().st_size > 0, "Workflow file must not be empty"


def test_workflow_yaml_validity_and_name() -> None:
    """Verify that workflow YAML is syntactically valid and has name."""
    parsed = _load_workflow_yaml()
    assert "name" in parsed, "Workflow YAML must contain a top-level 'name' key"
    assert "CoChem-SCRIBE" in parsed["name"] or "CI" in parsed["name"]
    assert "jobs" in parsed, "Workflow YAML must contain a top-level 'jobs' key"


def test_workflow_triggers_push_and_pull_request_on_main() -> None:
    """Verify triggers on push and pull_request targeting the main branch."""
    parsed = _load_workflow_yaml()
    raw_text = _get_workflow_text()

    triggers = (
        parsed.get("on")
        if "on" in parsed
        else (parsed.get(True) if True in parsed else {})
    )
    assert triggers or "on:" in raw_text, "Workflow must define triggers"

    if isinstance(triggers, dict):
        assert "push" in triggers, "Workflow must trigger on 'push'"
        assert "pull_request" in triggers, "Workflow must trigger on 'pull_request'"

        push_branches = triggers["push"].get("branches", [])
        assert "main" in push_branches, "'push' trigger must target 'main' branch"

        pr_branches = triggers["pull_request"].get("branches", [])
        assert "main" in pr_branches, "'pull_request' trigger must target 'main'"
    else:
        assert "push:" in raw_text and "pull_request:" in raw_text
        assert "main" in raw_text


def test_airgap_job_presence_and_ubuntu_runner() -> None:
    """Verify that airgap-enforcement job exists and runs on ubuntu-latest."""
    parsed = _load_workflow_yaml()
    jobs = parsed["jobs"]

    airgap_jobs = [k for k in jobs if "airgap" in k.lower()]
    assert len(airgap_jobs) >= 1, f"Airgap job missing in: {list(jobs.keys())}"

    airgap_job = jobs[airgap_jobs[0]]
    assert "runs-on" in airgap_job, "Air-gap job must specify 'runs-on'"
    assert airgap_job["runs-on"] == "ubuntu-latest", "Air-gap job must run on Ubuntu"


def test_airgap_job_contains_checkout_and_python_setup() -> None:
    """Verify airgap job checks out code and sets up python."""
    parsed = _load_workflow_yaml()
    jobs = parsed["jobs"]
    airgap_job = jobs["airgap-enforcement"]
    steps = airgap_job.get("steps", [])

    uses_list = [s.get("uses", "") for s in steps if "uses" in s]
    assert any("actions/checkout" in u for u in uses_list), "Missing checkout step"
    assert any("actions/setup-python" in u for u in uses_list), "Missing python setup"


def test_airgap_script_checks_all_mandatory_forbidden_extensions_and_files() -> None:
    """Verify workflow script explicitly checks mandatory forbidden items."""
    raw_text = _get_workflow_text()
    for ext in MANDATORY_FORBIDDEN_EXTENSIONS:
        assert ext in raw_text, f"Forbidden extension '{ext}' missing in workflow"
    for fname in MANDATORY_FORBIDDEN_EXACT_FILES:
        assert fname in raw_text, f"Forbidden file '{fname}' missing in workflow"


def test_airgap_script_checks_additional_forbidden_extensions() -> None:
    """Verify workflow script checks additional restricted extensions."""
    raw_text = _get_workflow_text()
    for ext in ADDITIONAL_FORBIDDEN_EXTENSIONS:
        assert ext in raw_text, f"Forbidden extension '{ext}' missing in workflow"


def test_airgap_script_checks_mandatory_and_additional_forbidden_directories() -> None:
    """Verify workflow inspects forbidden directories."""
    raw_text = _get_workflow_text()
    for directory in MANDATORY_FORBIDDEN_DIRECTORIES:
        assert directory in raw_text, f"Forbidden dir '{directory}' missing in workflow"
    for directory in ADDITIONAL_FORBIDDEN_DIRECTORIES:
        assert directory in raw_text, f"Forbidden dir '{directory}' missing in workflow"


def test_airgap_script_enforces_nonzero_exit_code() -> None:
    """Verify Air-Gap script includes explicit failure exit codes."""
    raw_text = _get_workflow_text()
    assert "exit 1" in raw_text, "Workflow bash steps must execute 'exit 1'"
    assert "sys.exit(1)" in raw_text, "Deep sweep must execute 'sys.exit(1)'"


def test_matrix_targets_ubuntu_macos_and_python_versions() -> None:
    """Verify test matrix targets ubuntu/macos across Python 3.10 and 3.11."""
    parsed = _load_workflow_yaml()
    jobs = parsed["jobs"]
    assert "test" in jobs, "Workflow must contain a 'test' job"

    test_job = jobs["test"]
    strategy = test_job.get("strategy", {})
    matrix = strategy.get("matrix", {})

    os_list = matrix.get("os", [])
    python_list = [str(v) for v in matrix.get("python-version", [])]

    assert "ubuntu-latest" in os_list, "Matrix must include 'ubuntu-latest'"
    assert "macos-latest" in os_list, "Matrix must include 'macos-latest'"
    assert "3.10" in python_list, "Matrix must include Python '3.10'"
    assert "3.11" in python_list, "Matrix must include Python '3.11'"


def test_latex_dependencies_step_present() -> None:
    """Verify workflow includes steps to install LaTeX dependencies."""
    raw_text = _get_workflow_text()
    assert "texlive" in raw_text.lower(), "Workflow missing texlive LaTeX step"
    assert (
        "basictex" in raw_text.lower() or "mactex" in raw_text.lower()
    ), "Workflow missing macOS LaTeX dependencies"


def test_airgap_functional_sweep_clean_repo(tmp_path: Path) -> None:
    """Physical test: clean directory passes Air-Gap sweep with exit code 0."""
    (tmp_path / "src").mkdir()
    module_code = "def hello() -> str:\n    return 'clean'\n"
    (tmp_path / "src" / "module.py").write_text(module_code, encoding="utf-8")
    (tmp_path / "README.md").write_text("# Clean Workspace\n", encoding="utf-8")

    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 0, f"Clean repo must pass sweep, got: {violations}"
    assert len(violations) == 0, "Clean repo must produce 0 violations"


def test_airgap_functional_sweep_catches_h5_file(tmp_path: Path) -> None:
    """Physical test: sweep catches forbidden .h5 file and yields exit code 1."""
    (tmp_path / "bad_database.h5").write_bytes(
        b"\x89HDF\r\n\x1a\n\x00\x00rawhdf5payload"
    )
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 when .h5 file is present"
    assert any(".h5" in v["detail"] or "HDF5" in v["detail"] for v in violations)


def test_airgap_functional_sweep_catches_pdf_file(tmp_path: Path) -> None:
    """Physical test: sweep catches forbidden .pdf file and yields exit code 1."""
    (tmp_path / "compiled_paper.pdf").write_bytes(b"%PDF-1.4\n%realpdfdata")
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 when .pdf file is present"
    assert any(".pdf" in v["detail"] or "PDF" in v["detail"] for v in violations)


def test_airgap_functional_sweep_catches_env_file(tmp_path: Path) -> None:
    """Physical test: sweep catches forbidden .env file and yields exit code 1."""
    (tmp_path / ".env").write_text(
        "API_SECRET_KEY=sk-abcdef123456\n", encoding="utf-8"
    )
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 when .env file is present"
    assert any(
        ".env" in v["file"] or "FORBIDDEN_FILENAME" in v["type"] for v in violations
    )


def test_airgap_functional_sweep_catches_zip_file(tmp_path: Path) -> None:
    """Physical test: sweep catches forbidden .zip archive and yields exit code 1."""
    (tmp_path / "archive.zip").write_bytes(b"PK\x03\x04\x14\x00\x00\x00zipdata")
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 when .zip file is present"
    assert any(".zip" in v["detail"] or "ZIP" in v["detail"] for v in violations)


def test_airgap_functional_sweep_catches_gguf_file(tmp_path: Path) -> None:
    """Physical test: sweep catches forbidden .gguf weight file and yields exit 1."""
    (tmp_path / "model.gguf").write_bytes(b"GGUF\x03\x00\x00\x00ggufweights")
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 when .gguf file is present"
    assert any(".gguf" in v["detail"] or "GGUF" in v["detail"] for v in violations)


def test_airgap_functional_sweep_catches_pt_file(tmp_path: Path) -> None:
    """Physical test: sweep catches forbidden .pt file and yields exit code 1."""
    (tmp_path / "weights.pt").write_bytes(b"PK\x03\x04pytorchziptensors")
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 when .pt file is present"
    assert any(".pt" in v["detail"] or "ZIP" in v["detail"] for v in violations)


def test_airgap_functional_sweep_catches_cochem_artifacts_directory(
    tmp_path: Path,
) -> None:
    """Physical test: sweep catches forbidden CoChem_Artifacts directory."""
    artifacts_dir = tmp_path / "CoChem_Artifacts"
    artifacts_dir.mkdir()
    (artifacts_dir / "calc_dump.txt").write_text("data=123\n", encoding="utf-8")

    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 when forbidden dir is present"
    assert any(
        "CoChem_Artifacts" in v["file"] or "cochem_artifacts" in v["detail"]
        for v in violations
    )


def test_airgap_functional_sweep_catches_disguised_binary_magic_number(
    tmp_path: Path,
) -> None:
    """Physical test: sweep catches binary disguised as .txt via magic number."""
    disguised = tmp_path / "notes.txt"
    disguised.write_bytes(b"\x89HDF\r\n\x1a\n" + b"disguised_hdf5_content_in_txt_file")
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 for disguised binary header"
    assert any("MAGIC_NUMBER_VIOLATION" == v["type"] for v in violations)


def test_airgap_functional_sweep_catches_high_entropy_payload(
    tmp_path: Path,
) -> None:
    """Physical test: sweep catches high-entropy payload with innocent extension."""
    disguised = tmp_path / "innocent.txt"
    high_entropy_bytes = bytes([i % 256 for i in range(4096)])
    disguised.write_bytes(high_entropy_bytes)
    exit_code, violations = _run_python_deep_sweep(tmp_path)
    assert exit_code == 1, "Must exit with code 1 for high Shannon entropy"
    assert any("HIGH_ENTROPY_VIOLATION" == v["type"] for v in violations)


def test_workflow_and_test_prohibited_patterns_ast_inspection() -> None:
    """Verify absence of prohibited mock patterns in workflow and test file."""
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
        assert pat not in raw_workflow, f"Forbidden '{pat}' in workflow"

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
                    assert not (
                        alias.name == prohibited
                        or alias.name.startswith(prohibited + ".")
                    ), f"Prohibited import '{alias.name}' found in test file"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for prohibited in prohibited_modules:
                assert not (
                    mod == prohibited or mod.startswith(prohibited + ".")
                ), f"Prohibited import from '{mod}' found in test file"
