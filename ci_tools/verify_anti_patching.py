"""# zero-stub anti-spoofing engine
CoChem Anti-Patching & Root Cause Standards Verifier (ci_tools/verify_anti_patching.py)

AST and static analyzer enforcing [Infra-03] Root Cause Verification & Anti-Patching Standards:
1. Absence of symptom-level patching and 'If-Statements of Shame' across all pipelines.
2. Complete ban on broad exception swallowing (except: pass, except Exception: pass, except BaseException: pass)
   across all core engines and execution pipelines.
"""

from __future__ import annotations

import argparse
import ast
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger("verify_anti_patching")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

EXCLUDED_DIRS: Set[str] = {
    "build",
    "dist",
    ".venv",
    ".conda",
    "venv",
    "site-packages",
    "artifacts",
    "datasets",
    "data",
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".vscode",
    ".idea",
    ".trash",
    "Report_Archive",
    "scratch",
    "node_modules",
}

# Core engine directories subject to strict anti-swallow rules
CORE_ENGINE_DIRS: Set[str] = {
    "ci_tools",
    "core",
    "cochem_dock",
    "CoChem-BASE",
    "CoChem-TOPOS",
    "CoChem-TORQ",
    "CoChem-GEOM",
    "CoChem-CATALYST",
    "CoChem-SCRIBE",
    "CoChem-BENCH",
    "CoChem-KINETIC",
    "CoChem-LUMOS",
    "CoChem-MAGE",
    "CoChem-NODE",
    "CoChem-ORACLE",
    "CoChem-PULSE",
    "CoChem-SCAN",
    "CoChem-SHIFT",
    "CoChem-SpycFit",
    "CoChem-Council",
}


def _extract_exception_names(node: Optional[ast.AST]) -> Set[str]:
    """Extract exception names from an AST exception handler type node."""
    if node is None:
        return set()
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.Attribute):
        return {node.attr}
    if isinstance(node, ast.Tuple):
        result: Set[str] = set()
        for elt in node.elts:
            result.update(_extract_exception_names(elt))
        return result
    return set()


def _is_noop_stmt(stmt: ast.AST) -> bool:
    """Check if an AST statement is a no-op (pass, ..., docstring)."""
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr):
        if isinstance(stmt.value, ast.Constant):
            if stmt.value.value is ...:
                return True
            if isinstance(stmt.value.value, str):
                return True
    return False


class AntiPatchingVisitor(ast.NodeVisitor):
    def __init__(
        self,
        filepath: Optional[Path] = None,
        rel_path: str = "",
        is_core: bool = True,
    ):
        self.filepath = filepath
        self.rel_path = rel_path
        self.is_core = is_core
        self.violations: List[str] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        # 1. Ban bare except:
        if node.type is None:
            self.violations.append(
                f"Line {node.lineno}: Banned bare 'except:' clause (must catch specific exceptions)"
            )
            self.generic_visit(node)
            return

        # 2. Check for broad Exception / BaseException swallowing
        exc_names = _extract_exception_names(node.type)
        broad_caught = exc_names.intersection({"Exception", "BaseException"})
        if broad_caught:
            has_pass = any(isinstance(stmt, ast.Pass) for stmt in node.body)
            has_ellipsis = any(
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and stmt.value.value is ...
                for stmt in node.body
            )
            has_docstring_only = len(node.body) == 1 and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str)

            if has_pass:
                self.violations.append(
                    f"Line {node.lineno}: Banned broad exception swallowing 'except {', '.join(sorted(broad_caught))}:' with 'pass'"
                )
            elif has_ellipsis:
                self.violations.append(
                    f"Line {node.lineno}: Banned broad exception swallowing 'except {', '.join(sorted(broad_caught))}:' with '...'"
                )
            elif has_docstring_only or all(_is_noop_stmt(s) for s in node.body):
                self.violations.append(
                    f"Line {node.lineno}: Banned broad exception swallowing 'except {', '.join(sorted(broad_caught))}:' with docstring/no-op body"
                )

        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        if isinstance(node.test, ast.Constant):
            val = node.test.value
            if val is True:
                self.violations.append(
                    f"Line {node.lineno}: Banned hardcoded constant condition 'if True:' (symptom-level patch)"
                )
            elif val is False:
                self.violations.append(
                    f"Line {node.lineno}: Banned hardcoded constant condition 'if False:' (symptom-level patch)"
                )
            elif isinstance(val, int) and val in (0, 1):
                self.violations.append(
                    f"Line {node.lineno}: Banned hardcoded constant condition 'if {val}:' (symptom-level patch)"
                )
        self.generic_visit(node)


def audit_file(filepath: Path, repo_root: Path) -> List[str]:
    """Audit a single Python file for root cause and anti-patching violations."""
    try:
        content = filepath.read_text(encoding="utf-8-sig", errors="replace")
        tree = ast.parse(content, filename=str(filepath))
    except SyntaxError as e:
        return [f"Line {e.lineno}: Syntax error: {e.msg}"]
    except Exception as e:
        return [f"File read error: {e}"]

    rel = filepath.relative_to(repo_root)
    is_core = any(part in CORE_ENGINE_DIRS for part in rel.parts) or filepath.parent == repo_root

    visitor = AntiPatchingVisitor(filepath, str(rel), is_core)
    visitor.visit(tree)
    return visitor.violations


def audit_repository(
    repo_root: Path,
    target_dirs: Optional[List[str]] = None,
) -> Tuple[bool, Dict[str, List[str]]]:
    """Audit repository files for anti-patching violations."""
    all_violations: Dict[str, List[str]] = {}

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]
        rel_root = Path(root).relative_to(repo_root)

        if any(part in EXCLUDED_DIRS for part in rel_root.parts):
            continue

        if target_dirs is not None:
            if rel_root == Path("."):
                continue
            if rel_root.parts[0] not in target_dirs:
                continue

        for f in files:
            if f.endswith(".py"):
                p = Path(root) / f
                if any(part in EXCLUDED_DIRS for part in p.relative_to(repo_root).parts):
                    continue
                v = audit_file(p, repo_root)
                if v:
                    all_violations[str(p.relative_to(repo_root))] = v

    passed = len(all_violations) == 0
    return passed, all_violations


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CoChem Root Cause & Anti-Patching Standards Verifier")
    parser.add_argument("target", nargs="?", default=".", help="Root path to scan")
    parser.add_argument("--core-only", action="store_true", help="Audit only core engines")
    args = parser.parse_args(argv)

    repo_root = Path(args.target).resolve()
    if not repo_root.exists():
        print(f"Error: Target path {repo_root} does not exist.")
        return 1

    target_dirs = list(CORE_ENGINE_DIRS) if args.core_only else None
    passed, violations = audit_repository(repo_root, target_dirs=target_dirs)

    print("=== [Infra-03] ROOT CAUSE VERIFICATION & ANTI-PATCHING AUDIT ===")
    if not passed:
        print(f"[VIOLATIONS DETECTED] Found {len(violations)} files with anti-patching / exception swallowing violations:")
        for f, v_list in violations.items():
            print(f"\nFile: {f}")
            for v in v_list:
                print(f"  - {v}")
        return 1

    print("[SUCCESS] 100% compliance with [Infra-03] Root Cause & Anti-Patching Standards.")
    print("  - Zero symptom-level patches / If-Statements of Shame detected.")
    print("  - Zero broad exception swallowing (except: pass, except Exception: pass).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
