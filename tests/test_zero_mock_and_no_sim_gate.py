"""Hard CI AST gate prohibiting mocks, monkeypatch, fake_* helpers, simulation mode, and non-empty amnesty."""
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AMNESTY_FILE = REPO_ROOT / ".anti_spoof_amnesty.json"

EXCLUDED_DIRS = frozenset({
    ".git",
    ".venv",
    "venv",
    "build",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".conda",
    "node_modules",
    "CoChem_BASE.egg-info",
})

EXCLUDED_RELATIVE_PATHS = frozenset({
    "ci_tools/anti_spoof_linter.py",
    "src/cochem_base/core_engine/cochem_core_context_compressor.py",
    "tests/test_zero_mock_and_no_sim_gate.py",
})

BANNED_IMPORT_MODULES = frozenset({
    "unittest.mock",
    "mock",
    "pytest_mock",
})

BANNED_SYMBOL_NAMES = frozenset({
    "MagicMock",
    "Mock",
    "AsyncMock",
    "PropertyMock",
    "create_autospec",
    "NonCallableMock",
    "mock_open",
    "monkeypatch",
    "MonkeyPatch",
})

BANNED_EXACT_IDENTIFIERS = frozenset({
    "generate_deterministic_solver_output",
    "poll_or_simulate_execution",
    "COLAB_WORKER_FAKE_GPU_NAME",
    "simulated_temp",
    "dummy_force",
})


def _is_banned_identifier(name: str) -> bool:
    return (
        name in BANNED_SYMBOL_NAMES
        or name in BANNED_EXACT_IDENTIFIERS
        or name.startswith("fake_")
        or name.startswith("FAKE_")
    )


def _extract_constant_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def scan_source_for_zero_mock_violations(source: str, rel_path: str) -> list[str]:
    """Scan Python source AST for banned mock imports, mock/monkeypatch/fake_* symbols, or mode='simulation'."""
    normalized = rel_path.replace("\\", "/")
    if normalized in EXCLUDED_RELATIVE_PATHS:
        return []

    try:
        tree = ast.parse(source, filename=normalized)
    except SyntaxError as exc:
        return [f"{normalized}:{exc.lineno or 1}: syntax error while scanning ({exc.msg})"]

    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name == mod or alias.name.startswith(mod + ".") for mod in BANNED_IMPORT_MODULES):
                    violations.append(f"{normalized}:{node.lineno}: banned import {alias.name!r}")
                if alias.asname and _is_banned_identifier(alias.asname):
                    violations.append(f"{normalized}:{node.lineno}: banned import alias {alias.asname!r}")

        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if any(mod == banned or mod.startswith(banned + ".") for banned in BANNED_IMPORT_MODULES):
                violations.append(f"{normalized}:{node.lineno}: banned from-import {mod!r}")
            for alias in node.names:
                full = f"{mod}.{alias.name}" if mod else alias.name
                if any(full == banned or full.startswith(banned + ".") for banned in BANNED_IMPORT_MODULES):
                    violations.append(f"{normalized}:{node.lineno}: banned import {full!r}")
                if _is_banned_identifier(alias.name):
                    violations.append(f"{normalized}:{node.lineno}: banned imported symbol {alias.name!r}")
                if alias.asname and _is_banned_identifier(alias.asname):
                    violations.append(f"{normalized}:{node.lineno}: banned import alias {alias.asname!r}")

        elif isinstance(node, ast.Name):
            if _is_banned_identifier(node.id):
                violations.append(f"{normalized}:{node.lineno}: banned symbol reference {node.id!r}")

        elif isinstance(node, ast.Attribute):
            if _is_banned_identifier(node.attr):
                violations.append(f"{normalized}:{node.lineno}: banned attribute reference '.{node.attr}'")

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_banned_identifier(node.name):
                violations.append(f"{normalized}:{node.lineno}: banned function name {node.name!r}")
            all_args = [
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
            ]
            if node.args.vararg is not None:
                all_args.append(node.args.vararg)
            if node.args.kwarg is not None:
                all_args.append(node.args.kwarg)
            for arg in all_args:
                if _is_banned_identifier(arg.arg):
                    violations.append(f"{normalized}:{node.lineno}: banned parameter {arg.arg!r}")

        elif isinstance(node, ast.ClassDef):
            if _is_banned_identifier(node.name):
                violations.append(f"{normalized}:{node.lineno}: banned class name {node.name!r}")

        elif isinstance(node, ast.keyword):
            if node.arg and _is_banned_identifier(node.arg):
                violations.append(f"{normalized}:{node.lineno}: banned keyword argument {node.arg!r}")
            if node.arg == "mode" and _extract_constant_str(node.value) == "simulation":
                violations.append(f"{normalized}:{node.lineno}: banned mode='simulation' keyword argument")

        elif isinstance(node, ast.Assign):
            if _extract_constant_str(node.value) == "simulation":
                for target in node.targets:
                    if (
                        (isinstance(target, ast.Name) and target.id == "mode")
                        or (isinstance(target, ast.Attribute) and target.attr == "mode")
                    ):
                        violations.append(f"{normalized}:{node.lineno}: banned mode='simulation' assignment")

        elif isinstance(node, ast.AnnAssign):
            if node.value is not None and _extract_constant_str(node.value) == "simulation":
                if (
                    (isinstance(node.target, ast.Name) and node.target.id == "mode")
                    or (isinstance(node.target, ast.Attribute) and node.target.attr == "mode")
                ):
                    violations.append(f"{normalized}:{node.lineno}: banned mode='simulation' annotated assignment")

        elif isinstance(node, ast.Call):
            callee = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else ""
            )
            if callee in {"import_module", "__import__"} and node.args:
                target_mod = _extract_constant_str(node.args[0])
                if target_mod and any(
                    target_mod == banned or target_mod.startswith(banned + ".")
                    for banned in BANNED_IMPORT_MODULES
                ):
                    violations.append(f"{normalized}:{node.lineno}: banned dynamic import {target_mod!r}")

    return sorted(set(violations))


def scan_repository_for_zero_mock(root: Path = REPO_ROOT) -> list[str]:
    """Scan all Python files in the repository plus `.anti_spoof_amnesty.json`."""
    violations: list[str] = []

    amnesty_path = root / ".anti_spoof_amnesty.json"
    if not amnesty_path.is_file():
        violations.append(".anti_spoof_amnesty.json: missing zero-amnesty sentinel file")
    else:
        try:
            amnesty_data = json.loads(amnesty_path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            violations.append(f".anti_spoof_amnesty.json: invalid JSON ({exc})")
        else:
            if amnesty_data != []:
                violations.append(
                    f".anti_spoof_amnesty.json: must be empty [] (found {type(amnesty_data).__name__} len={len(amnesty_data) if hasattr(amnesty_data, '__len__') else '?'})"
                )

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            py_path = Path(dirpath) / filename
            rel_path = py_path.relative_to(root).as_posix()
            if rel_path in EXCLUDED_RELATIVE_PATHS:
                continue
            source = py_path.read_text(encoding="utf-8-sig")
            violations.extend(scan_source_for_zero_mock_violations(source, rel_path))

    return violations


def test_anti_spoof_amnesty_is_empty() -> None:
    """Enforce that `.anti_spoof_amnesty.json` has been burned down to `[]` (0 entries)."""
    assert AMNESTY_FILE.is_file(), ".anti_spoof_amnesty.json must exist at repository root"
    parsed = json.loads(AMNESTY_FILE.read_text(encoding="utf-8"))
    assert parsed == [], f"Expected empty amnesty [], found {len(parsed)} entries: {parsed[:5]}"


def test_zero_mock_and_no_simulation_across_repository() -> None:
    """Enforce zero mocks, monkeypatch, fake_*, or mode='simulation' across all Python files."""
    violations = scan_repository_for_zero_mock(REPO_ROOT)
    assert violations == [], (
        f"Zero-mock / zero-simulation AST gate failed with {len(violations)} violation(s):\n"
        + "\n".join(violations[:50])
    )


def test_zero_mock_gate_self_test() -> None:
    """Verify the AST gate reliably detects every prohibited category and accepts authentic code."""
    banned_mod = sorted(BANNED_IMPORT_MODULES)[2]  # unittest.mock
    banned_sym = sorted(BANNED_SYMBOL_NAMES)[0]    # AsyncMock
    banned_exact = sorted(BANNED_EXACT_IDENTIFIERS)[0]

    bad_samples = [
        ("sample_import.py", f"import {banned_mod}\n"),
        ("sample_from.py", f"from {banned_mod} import {banned_sym}\n"),
        ("sample_arg.py", "def test_env(monkeypatch):\n    return monkeypatch\n"),
        ("sample_fake_def.py", "def fake_engine():\n    return 1\n"),
        ("sample_fake_const.py", "FAKE_RESULT = 42\n"),
        ("sample_exact.py", f"def {banned_exact}():\n    return 0\n"),
        ("sample_sim_kw.py", "run_job(mode='simulation')\n"),
        ("sample_sim_assign.py", "mode = 'simulation'\n"),
    ]
    for fname, snippet in bad_samples:
        hits = scan_source_for_zero_mock_violations(snippet, fname)
        assert hits, f"Expected AST gate to flag {fname}"

    clean_sample = (
        "from contextlib import contextmanager\n"
        "import os\n\n"
        "@contextmanager\n"
        "def scoped_env(key: str, value: str):\n"
        "    prev = os.environ.get(key)\n"
        "    os.environ[key] = value\n"
        "    try:\n"
        "        yield\n"
        "    finally:\n"
        "        if prev is None:\n"
        "            os.environ.pop(key, None)\n"
        "        else:\n"
        "            os.environ[key] = prev\n"
    )
    assert scan_source_for_zero_mock_violations(clean_sample, "clean_sample.py") == []


if __name__ == "__main__":
    found = scan_repository_for_zero_mock(REPO_ROOT)
    if found:
        print("Zero-mock AST gate FAILED:\n" + "\n".join(found), file=sys.stderr)
        raise SystemExit(1)
    print("Zero-mock AST gate PASSED: 0 violations and empty .anti_spoof_amnesty.json.")
    raise SystemExit(0)
