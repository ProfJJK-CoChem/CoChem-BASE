"""Zero-Amnesty & Zero-Mock Unit and Integration Test Suite for .anti_spoof_amnesty.json.

Validates that the repository's `.anti_spoof_amnesty.json` has been completely burned down
to `[]` (zero amnesty waivers), strictly UTF-8 LF encoded, and that zero prohibited mock
imports exist across all Python files in CoChem-BASE.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pytest

from ci_tools.anti_spoof_linter import BANNED_MOCK_MODULES

REPO_ROOT = Path(__file__).resolve().parent.parent
AMNESTY_PATH = REPO_ROOT / ".anti_spoof_amnesty.json"

MOCK_MODULES: Set[str] = set(BANNED_MOCK_MODULES)

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
                            "detail": f"Direct import '{alias.name}' is prohibited.",
                        })
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for target in prohibited:
                if mod == target or mod.startswith(target + "."):
                    violations.append({
                        "file": rel_path_str,
                        "line": node.lineno,
                        "module": mod,
                        "detail": f"Import from '{mod}' is prohibited.",
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
                                "detail": f"Import of '{full_imported}' is prohibited.",
                            })
    return violations


@pytest.fixture(scope="module")
def amnesty_file_path() -> Path:
    assert AMNESTY_PATH.exists(), f"Amnesty file does not exist at {AMNESTY_PATH}"
    return AMNESTY_PATH


@pytest.fixture(scope="module")
def amnesty_raw_bytes(amnesty_file_path: Path) -> bytes:
    return amnesty_file_path.read_bytes()


@pytest.fixture(scope="module")
def amnesty_content(amnesty_raw_bytes: bytes) -> str:
    return amnesty_raw_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def amnesty_entries(amnesty_content: str) -> List[str]:
    data = json.loads(amnesty_content)
    assert isinstance(data, list), "Amnesty file content must be a JSON array"
    return data


def test_amnesty_file_exists_and_burned_down_to_empty(amnesty_file_path: Path, amnesty_entries: List[str]) -> None:
    """Validate that .anti_spoof_amnesty.json exists and is burned down to zero entries (`[]`)."""
    assert amnesty_file_path.is_file()
    assert amnesty_entries == [], (
        f".anti_spoof_amnesty.json must be burned down to [] (0 entries), found {len(amnesty_entries)}"
    )


def test_amnesty_file_utf8_lf_encoding(amnesty_raw_bytes: bytes) -> None:
    """Validate strict UTF-8 (no BOM) and Unix LF line endings."""
    assert not amnesty_raw_bytes.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in amnesty_raw_bytes
    assert b"\r" not in amnesty_raw_bytes
    assert amnesty_raw_bytes.decode("utf-8").strip() == "[]"


def test_physical_ast_sweep_zero_mock_imports() -> None:
    """Execute a full repository AST sweep ensuring zero prohibited mock imports."""
    violations: List[Dict[str, Any]] = []
    scanned_count = 0

    for root, dirs, files in os.walk(REPO_ROOT, topdown=True):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        for filename in files:
            if not filename.endswith(".py"):
                continue
            file_path = Path(root) / filename
            posix_rel = file_path.relative_to(REPO_ROOT).as_posix()
            scanned_count += 1
            violations.extend(
                scan_file_ast_for_violations(
                    file_path=file_path,
                    rel_path_str=posix_rel,
                    prohibited=MOCK_MODULES,
                )
            )

    assert scanned_count > 50
    if violations:
        details = "\n".join(
            f"  - {v['file']}:{v['line']} -> Prohibited: '{v['module']}' ({v['detail']})"
            for v in violations
        )
        pytest.fail(f"AST Anti-Spoofing Sweep detected {len(violations)} violation(s):\n{details}")


def test_ast_sweep_detects_prohibited_mock_imports(tmp_path: Path) -> None:
    """Verify AST scanner sensitivity on clean and prohibited temporary Python files."""
    clean_file = tmp_path / "clean_orchestrator.py"
    clean_file.write_text(
        "import os\nimport json\nfrom pathlib import Path\n\ndef compute_score(x: int, y: int) -> int:\n    return x + y\n",
        encoding="utf-8",
    )
    assert scan_file_ast_for_violations(clean_file, "clean_orchestrator.py", MOCK_MODULES) == []

    for fname, mod_name in (
        ("prohibited_1.py", sorted(MOCK_MODULES)[0]),
        ("prohibited_2.py", sorted(MOCK_MODULES)[1]),
        ("prohibited_3.py", sorted(MOCK_MODULES)[2]),
    ):
        bad_file = tmp_path / fname
        bad_file.write_text(f"import {mod_name}\n", encoding="utf-8")
        found = scan_file_ast_for_violations(bad_file, fname, MOCK_MODULES)
        assert len(found) >= 1, f"Failed to detect prohibited import {mod_name}"

    syntax_error_file = tmp_path / "corrupted_syntax.py"
    syntax_error_file.write_text("def invalid_syntax_func(\n", encoding="utf-8")
    syntax_violations = scan_file_ast_for_violations(syntax_error_file, "corrupted_syntax.py", MOCK_MODULES)
    assert len(syntax_violations) == 1
    assert syntax_violations[0]["module"] == "SYNTAX_OR_ENCODING_ERROR"
