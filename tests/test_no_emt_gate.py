"""Hard CI AST gate prohibiting ASE EMT() and EMTBaselineEngine across CoChem-BASE."""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_EMT_MODULE = "ase.calculators.emt"
FORBIDDEN_EMT_SYMBOL = "EMT"
FORBIDDEN_EMT_BASELINE = "EMTBaselineEngine"
EXCLUDED_RELATIVE_PATHS = frozenset({"tests/test_no_emt_gate.py"})
ALLOWED_REJECTION_FILES = frozenset({"src/cochem_base/core_engine/cochem_temporal_router.py"})


def _extract_string_arg(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _extract_string_arg(node.left)
        right = _extract_string_arg(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def scan_source_for_emt(source: str, rel_path: str) -> list[str]:
    """Return AST violations if source imports ase.calculators.emt, calls EMT(), or references EMTBaselineEngine."""
    normalized = rel_path.replace("\\", "/")
    if normalized in EXCLUDED_RELATIVE_PATHS:
        return []
    tree = ast.parse(source, filename=normalized)
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == FORBIDDEN_EMT_MODULE or alias.name.startswith(FORBIDDEN_EMT_MODULE + "."):
                    violations.append(f"{normalized}:{node.lineno}: forbidden import {alias.name!r}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == FORBIDDEN_EMT_MODULE or mod.startswith(FORBIDDEN_EMT_MODULE + "."):
                violations.append(f"{normalized}:{node.lineno}: forbidden import from {mod!r}")
            for alias in node.names:
                if alias.name == FORBIDDEN_EMT_BASELINE:
                    violations.append(f"{normalized}:{node.lineno}: forbidden import {FORBIDDEN_EMT_BASELINE}")
                if mod == "ase.calculators" and alias.name == "emt":
                    violations.append(f"{normalized}:{node.lineno}: forbidden import ase.calculators.emt")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in {FORBIDDEN_EMT_SYMBOL, FORBIDDEN_EMT_BASELINE}:
                violations.append(f"{normalized}:{node.lineno}: forbidden call {func.id}()")
            elif isinstance(func, ast.Attribute) and func.attr in {FORBIDDEN_EMT_SYMBOL, FORBIDDEN_EMT_BASELINE}:
                violations.append(f"{normalized}:{node.lineno}: forbidden call .{func.attr}()")
            elif isinstance(func, (ast.Name, ast.Attribute)):
                callee = func.id if isinstance(func, ast.Name) else func.attr
                if callee in {"import_module", "__import__"} and node.args:
                    arg_str = _extract_string_arg(node.args[0])
                    if arg_str and (arg_str == FORBIDDEN_EMT_MODULE or arg_str.startswith(FORBIDDEN_EMT_MODULE + ".")):
                        violations.append(f"{normalized}:{node.lineno}: forbidden dynamic import {arg_str!r}")
        elif isinstance(node, ast.Name) and node.id == FORBIDDEN_EMT_BASELINE:
            violations.append(f"{normalized}:{node.lineno}: forbidden reference {FORBIDDEN_EMT_BASELINE}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if normalized not in ALLOWED_REJECTION_FILES:
                if node.value == FORBIDDEN_EMT_MODULE or node.value == FORBIDDEN_EMT_BASELINE:
                    violations.append(f"{normalized}:{node.lineno}: forbidden literal {node.value!r}")

    return violations


def _tracked_python_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--", "*.py"],
        capture_output=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout:
        paths = []
        for entry in result.stdout.decode("utf-8").split("\0"):
            if entry:
                candidate = root / entry
                if candidate.is_file():
                    paths.append(candidate)
        return sorted(paths)
    return sorted(
        p for p in root.rglob("*.py")
        if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts
    )


def scan_repository_for_emt(root: Path = REPO_ROOT) -> list[str]:
    violations: list[str] = []
    for py_path in _tracked_python_files(root):
        rel_path = py_path.relative_to(root).as_posix()
        source = py_path.read_text(encoding="utf-8-sig")
        violations.extend(scan_source_for_emt(source, rel_path))
    return violations


def test_no_emt_across_tracked_python_files() -> None:
    """Enforce zero ase.calculators.emt imports, EMT() calls, or EMTBaselineEngine across all tracked .py files."""
    violations = scan_repository_for_emt(REPO_ROOT)
    assert violations == [], "Prohibited EMT usage detected:\n" + "\n".join(violations)


def test_no_emt_gate_self_test() -> None:
    """Verify the AST gate detects direct/dynamic EMT imports, EMT() calls, and EMTBaselineEngine."""
    bad_samples = [
        ("sample_import.py", f"from {FORBIDDEN_EMT_MODULE} import {FORBIDDEN_EMT_SYMBOL}\n"),
        ("sample_call.py", f"calc = {FORBIDDEN_EMT_SYMBOL}()\n"),
        ("sample_dynamic.py", f"import importlib\nimportlib.import_module('{FORBIDDEN_EMT_MODULE}')\n"),
        ("sample_baseline.py", f"cls = {FORBIDDEN_EMT_BASELINE}\n"),
    ]
    for name, src in bad_samples:
        hits = scan_source_for_emt(src, name)
        assert hits, f"Expected AST gate to flag {name}"

    clean_sample = (
        "from ase import Atoms\n"
        "from ase.calculators.lj import LennardJones\n"
        "from ase.calculators.morse import MorsePotential\n"
        "atoms = Atoms('H2', positions=[[0, 0, 0], [0, 0, 0.74]])\n"
        "atoms.calc = MorsePotential(epsilon=4.75, r0=0.7414, rho0=1.44)\n"
    )
    assert scan_source_for_emt(clean_sample, "clean_sample.py") == []


if __name__ == "__main__":
    found = scan_repository_for_emt(REPO_ROOT)
    if found:
        print("EMT AST gate FAILED:\n" + "\n".join(found), file=sys.stderr)
        raise SystemExit(1)
    print("EMT AST gate PASSED: 0 prohibited EMT references across tracked Python files.")
    raise SystemExit(0)
