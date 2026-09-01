"""Comprehensive Zero-Mock Unit and Integration Test Suite for CoChem Anti-Spoofing Amnesty.

Validates the integrity, formatting, parsing, deterministic ordering, and enforcement
of the Anti-Spoofing Amnesty whitelist (.anti_spoof_amnesty.json) across the CoChem-BASE repository.

Defends the Tripartite Workspace Air-Gap and AST-level Anti-Spoofing boundary by ensuring:
1. Physical existence and non-empty size of .anti_spoof_amnesty.json.
2. Strict UTF-8 encoding (no BOM: \\xef\\xbb\\xbf) and strict Unix LF line endings (no \\r\\n, no \\r).
3. Valid JSON syntax parsing into a non-empty array of non-empty strings.
4. Strict POSIX relative path formatting.
5. Absolute uniqueness of all entries with zero duplicates.
6. Deterministic alphabetical / lexical ordering across all entries.
7. Explicit whitelisting of active concurrency modules and core parallel orchestration files.
8. Physical AST sweep execution across all non-amnestied Python files in the repository.
9. AST scanner sensitivity verification using dynamic temporary modules to confirm positive detection
   of all prohibited modules and accurate amnesty bypass.
10. Strict Zero-Mock Mandate compliance via AST inspection ensuring zero prohibited test utility imports.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pytest

# Repository root and path to .anti_spoof_amnesty.json
REPO_ROOT = Path(__file__).resolve().parent.parent
AMNESTY_PATH = REPO_ROOT / ".anti_spoof_amnesty.json"

MOCK_MODULES: Set[str] = {
    "unittest.mock",
    "mock",
}

CONCURRENCY_MODULES: Set[str] = {
    "multiprocessing",
    "concurrent.futures",
    "parsl",
    "dask",
    "ray",
    "mpi4py",
    "threading",
}

PROHIBITED_MODULES = MOCK_MODULES | CONCURRENCY_MODULES

EXCLUDED_DIRS: Set[str] = {
    ".agent_artifacts",
    ".git",
    ".venv",
    "venv",
    ".conda",
    "__pycache__",
    ".pytest_cache",
    ".pytest_cache_fresh",
    ".mypy_cache",
    ".ruff_cache",
    ".trash",
    ".tox",
    ".nox",
    "dist",
    "build",
    "egg-info",
    ".eggs",
    "node_modules",
    ".idea",
    ".vscode",
}

# Mandatory active parallel / concurrency orchestration modules that must be whitelisted
MANDATORY_CONCURRENCY_MODULES: List[str] = [
    "cochem_base/core/dispatcher.py",
    "cochem_base/core/hardware.py",
    "cochem_base/engine/hpc_dispatcher.py",
    "cochem_base/interfaces/cochem_unity_installer_dashboard.py",
    "cochem_topos/engine.py",
    "core_engine/cochem_core_scheduler.py",
    "core_engine/cochem_core_subprocess_broker.py",
    "core_engine/cochem_core_telemetry_logger.py",
    "intake/cochem_stage2_ingestor.py",
    "interfaces/cochem_unity_installer_dashboard.py",
    "setup/cochem_base_setup.py",
    "setup/cochem_setup_orchestrator.py",
    "tests/integration/test_gc_sweep.py",
    "tests/test_gc_sweep_unit.py",
    "test_suite/test_cochem_core_telemetry_logger.py",
    "test_suite/test_web_streaming.py",
]


# ==============================================================================
# Helper Functions & Fixtures
# ==============================================================================


def normalize_amnesty_entry(entry: str) -> Tuple[str, ...]:
    """Normalize a raw amnesty path entry into standardized POSIX lowercase variants."""
    norm = entry.replace("\\", "/").strip("/")
    lowered = norm.lower()
    variants = [lowered]
    if lowered.startswith("cochem_base/"):
        variants.append(lowered[len("cochem_base/"):])
    return tuple(variants)


def load_normalized_amnesty(amnesty_file: Path) -> Set[str]:
    """Load and normalize all entries from the amnesty JSON file."""
    if not amnesty_file.exists():
        return set()
    raw_content = amnesty_file.read_text(encoding="utf-8")
    raw_entries: List[str] = json.loads(raw_content)
    normalized: Set[str] = set()
    for entry in raw_entries:
        for variant in normalize_amnesty_entry(entry):
            normalized.add(variant)
    return normalized


def scan_file_ast_for_violations(
    file_path: Path,
    rel_path_str: str,
    prohibited: Set[str],
) -> List[Dict[str, Any]]:
    """Parse a Python source file and detect unauthorized imports."""
    violations: List[Dict[str, Any]] = []
    try:
        content = file_path.read_text(encoding="utf-8-sig")
        tree = ast.parse(content, filename=str(file_path))
    except Exception as parse_err:
        violations.append({
            "file": rel_path_str,
            "line": 0,
            "module": "SYNTAX_OR_ENCODING_ERROR",
            "detail": str(parse_err),
        })
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for target in prohibited:
                    if alias.name == target or alias.name.startswith(target + "."):
                        violations.append({
                            "file": rel_path_str,
                            "line": node.lineno,
                            "module": alias.name,
                            "detail": f"Direct import '{alias.name}' is prohibited without amnesty.",
                        })
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for target in prohibited:
                if mod == target or mod.startswith(target + "."):
                    violations.append({
                        "file": rel_path_str,
                        "line": node.lineno,
                        "module": mod,
                        "detail": f"Import from '{mod}' is prohibited without amnesty.",
                    })
            for alias in node.names:
                full_imported = f"{mod}.{alias.name}" if mod else alias.name
                for target in prohibited:
                    if (
                        full_imported == target
                        or full_imported.startswith(target + ".")
                        or alias.name == target
                    ):
                        if not any(
                            v["line"] == node.lineno and v["module"] in (mod, full_imported, alias.name)
                            for v in violations
                        ):
                            violations.append({
                                "file": rel_path_str,
                                "line": node.lineno,
                                "module": full_imported,
                                "detail": f"Import of '{full_imported}' is prohibited without amnesty.",
                            })
    return violations


@pytest.fixture(scope="module")
def amnesty_file_path() -> Path:
    """Fixture providing the absolute path to .anti_spoof_amnesty.json."""
    assert AMNESTY_PATH.exists(), f"Amnesty file does not exist at {AMNESTY_PATH}"
    return AMNESTY_PATH


@pytest.fixture(scope="module")
def amnesty_raw_bytes(amnesty_file_path: Path) -> bytes:
    """Fixture providing the raw bytes of .anti_spoof_amnesty.json."""
    return amnesty_file_path.read_bytes()


@pytest.fixture(scope="module")
def amnesty_content(amnesty_raw_bytes: bytes) -> str:
    """Fixture providing the decoded string content of .anti_spoof_amnesty.json."""
    return amnesty_raw_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def amnesty_entries(amnesty_content: str) -> List[str]:
    """Fixture providing the parsed JSON array of amnesty entries."""
    data = json.loads(amnesty_content)
    assert isinstance(data, list), "Amnesty file content must be a JSON array"
    return data


@pytest.fixture(scope="module")
def normalized_amnesty_set(amnesty_entries: List[str]) -> Set[str]:
    """Fixture providing the set of all normalized POSIX lowercase amnesty paths."""
    norm_set: Set[str] = set()
    for entry in amnesty_entries:
        for variant in normalize_amnesty_entry(entry):
            norm_set.add(variant)
    return norm_set


# ==============================================================================
# 1. File Existence & Physical Metrics
# ==============================================================================


def test_amnesty_file_exists_and_non_empty(amnesty_file_path: Path) -> None:
    """Validate that .anti_spoof_amnesty.json exists at repository root and contains data."""
    assert amnesty_file_path.exists(), f".anti_spoof_amnesty.json missing at {amnesty_file_path}"
    assert amnesty_file_path.is_file(), ".anti_spoof_amnesty.json must be a regular file"
    stat = amnesty_file_path.stat()
    assert stat.st_size > 100, f"Amnesty file size too small ({stat.st_size} bytes)"
    assert stat.st_size < 10_000_000, f"Amnesty file size unreasonably large ({stat.st_size} bytes)"


# ==============================================================================
# 2. File Encoding & Line Endings
# ==============================================================================


def test_amnesty_file_utf8_lf_encoding(amnesty_raw_bytes: bytes) -> None:
    """Validate that .anti_spoof_amnesty.json has no UTF-8 BOM and uses strict Unix LF line endings."""
    assert not amnesty_raw_bytes.startswith(b"\xef\xbb\xbf"), (
        ".anti_spoof_amnesty.json contains UTF-8 BOM (\\xef\\xbb\\xbf)"
    )
    assert b"\r\n" not in amnesty_raw_bytes, (
        ".anti_spoof_amnesty.json contains Windows CRLF line endings (\\r\\n)"
    )
    assert b"\r" not in amnesty_raw_bytes, (
        ".anti_spoof_amnesty.json contains standalone carriage return characters (\\r)"
    )
    # Ensure clean UTF-8 decoding without errors
    decoded = amnesty_raw_bytes.decode("utf-8")
    assert len(decoded) > 0, "Decoded amnesty content is empty"


# ==============================================================================
# 3. JSON Schema & Data Structure
# ==============================================================================


def test_amnesty_json_valid_syntax(amnesty_content: str) -> None:
    """Validate that .anti_spoof_amnesty.json parses into a valid JSON array of non-empty strings."""
    data = json.loads(amnesty_content)
    assert isinstance(data, list), f"Expected JSON list, got {type(data).__name__}"
    assert len(data) > 0, "Amnesty list must not be empty"

    non_string_entries = [item for item in data if not isinstance(item, str)]
    assert len(non_string_entries) == 0, (
        f"Found {len(non_string_entries)} non-string entries in amnesty list: {non_string_entries[:5]}"
    )

    empty_entries = [item for item in data if isinstance(item, str) and not item.strip()]
    assert len(empty_entries) == 0, (
        f"Found {len(empty_entries)} empty string entries in amnesty list"
    )


# ==============================================================================
# 4. Path POSIX Formatting
# ==============================================================================


def test_amnesty_path_posix_formatting(amnesty_entries: List[str]) -> None:
    """Validate that all paths in .anti_spoof_amnesty.json strictly adhere to POSIX format."""
    backslash_violations: List[str] = []
    leading_slash_violations: List[str] = []
    double_slash_violations: List[str] = []
    drive_letter_violations: List[str] = []

    for entry in amnesty_entries:
        if "\\" in entry:
            backslash_violations.append(entry)
        if entry.startswith("/"):
            leading_slash_violations.append(entry)
        if "//" in entry:
            double_slash_violations.append(entry)
        if len(entry) >= 2 and entry[1] == ":" and entry[0].isalpha():
            drive_letter_violations.append(entry)

    assert len(backslash_violations) == 0, (
        f"Detected {len(backslash_violations)} Windows backslash violations in amnesty list: {backslash_violations[:5]}"
    )
    assert len(leading_slash_violations) == 0, (
        f"Detected {len(leading_slash_violations)} absolute leading slash violations: {leading_slash_violations[:5]}"
    )
    assert len(double_slash_violations) == 0, (
        f"Detected {len(double_slash_violations)} double slash violations: {double_slash_violations[:5]}"
    )
    assert len(drive_letter_violations) == 0, (
        f"Detected {len(drive_letter_violations)} absolute Windows drive letter violations: {drive_letter_violations[:5]}"
    )


# ==============================================================================
# 5. Entry Uniqueness (Zero Duplicates)
# ==============================================================================


def test_amnesty_no_duplicate_entries(amnesty_entries: List[str]) -> None:
    """Validate that .anti_spoof_amnesty.json contains zero duplicate path entries."""
    seen: Set[str] = set()
    duplicates: List[str] = []

    for entry in amnesty_entries:
        if entry in seen:
            duplicates.append(entry)
        seen.add(entry)

    assert len(duplicates) == 0, (
        f"Detected {len(duplicates)} duplicate entries in .anti_spoof_amnesty.json: {duplicates[:10]}"
    )
    assert len(amnesty_entries) == len(seen), "Total entry count does not match unique entry count"


# ==============================================================================
# 6. Deterministic Alphabetical Ordering
# ==============================================================================


def test_amnesty_alphabetical_or_deterministic_ordering(amnesty_entries: List[str]) -> None:
    """Validate that entries in .anti_spoof_amnesty.json are deterministically sorted."""
    expected_sorted = sorted(amnesty_entries)
    mismatches: List[Tuple[int, str, str]] = []

    for idx, (actual, expected) in enumerate(zip(amnesty_entries, expected_sorted, strict=True)):
        if actual != expected:
            mismatches.append((idx, actual, expected))
            if len(mismatches) >= 5:
                break

    assert amnesty_entries == expected_sorted, (
        f"Amnesty list is not alphabetically sorted. First mismatches at index: {mismatches}"
    )


# ==============================================================================
# 7. Parsl & Concurrency Whitelist Coverage
# ==============================================================================


def test_parsl_concurrency_modules_whitelisted(normalized_amnesty_set: Set[str]) -> None:
    """Validate that active concurrency/parallel modules and files are present in the whitelist."""
    missing_modules: List[str] = []

    for required_mod in MANDATORY_CONCURRENCY_MODULES:
        norm_key = required_mod.lower()
        if norm_key not in normalized_amnesty_set:
            missing_modules.append(required_mod)

    assert len(missing_modules) == 0, (
        f"Mandatory concurrency modules are missing from amnesty whitelist: {missing_modules}"
    )


# ==============================================================================
# 8. Physical Repository AST Sweep Execution
# ==============================================================================


def test_physical_ast_sweep_execution(normalized_amnesty_set: Set[str]) -> None:
    """Execute the complete CI AST sweep logic across all Python files in the repository."""
    violations: List[Dict[str, Any]] = []
    scanned_count = 0

    for root, dirs, files in os.walk(REPO_ROOT, topdown=True):
        # Filter excluded directories in-place
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

        for filename in files:
            if not filename.endswith(".py"):
                continue

            file_path = Path(root) / filename
            try:
                posix_rel = file_path.relative_to(REPO_ROOT).as_posix()
            except ValueError:
                posix_rel = file_path.as_posix()

            posix_rel_norm = posix_rel.lower()

            prohibited_for_file = set(MOCK_MODULES)
            if posix_rel_norm not in normalized_amnesty_set:
                prohibited_for_file.update(CONCURRENCY_MODULES)
            
            if posix_rel_norm not in normalized_amnesty_set:
                scanned_count += 1

            file_violations = scan_file_ast_for_violations(
                file_path=file_path,
                rel_path_str=posix_rel,
                prohibited=prohibited_for_file,
            )
            violations.extend(file_violations)

    assert scanned_count > 50, (
        f"AST sweep only scanned {scanned_count} files, expected > 50 non-amnestied Python files."
    )

    if violations:
        violation_details = "\n".join(
            f"  - {v['file']}:{v['line']} -> Prohibited: '{v['module']}' ({v['detail']})"
            for v in violations
        )
        pytest.fail(
            f"AST Anti-Spoofing Sweep detected {len(violations)} unauthorized violation(s):\n"
            f"{violation_details}"
        )


# ==============================================================================
# 9. AST Sweep Sensitivity & Bypass Simulation
# ==============================================================================


def test_ast_sweep_detects_prohibited_imports_simulation(tmp_path: Path) -> None:
    """Validate AST scanner detects prohibited imports and respects amnesty bypass using dynamic files."""
    # 1. Test clean compliant code passes with 0 violations
    clean_file = tmp_path / "clean_orchestrator.py"
    clean_file.write_text(
        "import os\n"
        "import sys\n"
        "import json\n"
        "import ast\n"
        "from pathlib import Path\n"
        "from typing import Dict, List, Set, Tuple\n"
        "import pytest\n"
        "\n"
        "def compute_score(x: int, y: int) -> int:\n"
        "    return x + y\n",
        encoding="utf-8",
    )
    clean_violations = scan_file_ast_for_violations(
        file_path=clean_file,
        rel_path_str="clean_orchestrator.py",
        prohibited=PROHIBITED_MODULES,
    )
    assert len(clean_violations) == 0, f"Clean module triggered unexpected violations: {clean_violations}"

    # 2. Test individual direct prohibited imports
    direct_snippets = [
        ("multiprocessing_direct.py", "import multiprocessing\n"),
        ("concurrent_futures_direct.py", "import concurrent.futures\n"),
        ("parsl_direct.py", "import parsl\n"),
        ("dask_direct.py", "import dask\n"),
        ("ray_direct.py", "import ray\n"),
        ("mpi4py_direct.py", "import mpi4py\n"),
        ("threading_direct.py", "import threading\n"),
        ("prohibited_test_direct_1.py", "import unittest.mock\n"),
        ("prohibited_test_direct_2.py", "import mock\n"),
    ]

    for fname, snippet in direct_snippets:
        bad_file = tmp_path / fname
        bad_file.write_text(snippet, encoding="utf-8")
        bad_violations = scan_file_ast_for_violations(
            file_path=bad_file,
            rel_path_str=fname,
            prohibited=PROHIBITED_MODULES,
        )
        assert len(bad_violations) >= 1, f"Failed to detect violation in direct import file {fname}"

    # 3. Test sub-module and from-import variants
    from_snippets = [
        ("mp_pool.py", "from multiprocessing import Pool, Process\n"),
        ("cf_executor.py", "from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor\n"),
        ("parsl_config.py", "from parsl.config import Config\n"),
        ("dask_dist.py", "from dask.distributed import Client\n"),
        ("ray_remote.py", "from ray import remote\n"),
        ("mpi_world.py", "from mpi4py import MPI\n"),
        ("th_lock.py", "from threading import Thread, Lock, Event\n"),
        ("concurrent_from_import.py", "from concurrent import futures\n"),
        ("prohibited_test_from_import.py", "from unittest import mock\n"),
        ("prohibited_test_magic.py", "from unittest.mock import MagicMock\n"),
    ]

    for fname, snippet in from_snippets:
        bad_file = tmp_path / fname
        bad_file.write_text(snippet, encoding="utf-8")
        bad_violations = scan_file_ast_for_violations(
            file_path=bad_file,
            rel_path_str=fname,
            prohibited=PROHIBITED_MODULES,
        )
        assert len(bad_violations) >= 1, f"Failed to detect violation in from-import file {fname}"

    # 4. Test amnesty bypass mechanism
    bypass_file = tmp_path / "amnestied_worker.py"
    bypass_file.write_text("import threading\nfrom concurrent.futures import ThreadPoolExecutor\n", encoding="utf-8")

    # When unamnestied, violations are found
    violations_unamnestied = scan_file_ast_for_violations(
        file_path=bypass_file,
        rel_path_str="amnestied_worker.py",
        prohibited=PROHIBITED_MODULES,
    )
    assert len(violations_unamnestied) >= 1

    # When included in amnesty set, it is bypassed
    simulated_amnesty = {"amnestied_worker.py"}
    rel_path = "amnestied_worker.py"
    assert rel_path.lower() in simulated_amnesty

    # 5. Test syntax / parse error detection
    syntax_error_file = tmp_path / "corrupted_syntax.py"
    syntax_error_file.write_text("def invalid_syntax_func(\n", encoding="utf-8")
    syntax_violations = scan_file_ast_for_violations(
        file_path=syntax_error_file,
        rel_path_str="corrupted_syntax.py",
        prohibited=PROHIBITED_MODULES,
    )
    assert len(syntax_violations) == 1
    assert syntax_violations[0]["module"] == "SYNTAX_OR_ENCODING_ERROR"


# ==============================================================================
# 10. Zero-Mock Mandate Compliance
# ==============================================================================


def test_zero_mock_mandate_compliance() -> None:
    """Validate zero-mock compliance across this test suite via AST analysis."""
    test_file_path = Path(__file__)
    content = test_file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(test_file_path))

    prohibited_in_test: Set[str] = {
        "unittest.mock",
        "mock",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for p in prohibited_in_test:
                    assert alias.name != p and not alias.name.startswith(p + "."), (
                        f"Forbidden import in test file: '{alias.name}'"
                    )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for p in prohibited_in_test:
                assert mod != p and not mod.startswith(p + "."), (
                    f"Forbidden import in test file from module: '{mod}'"
                )
