"""# zero-stub anti-spoofing engine
CoChem Anti-Spoof Linter (ci_tools/anti_spoof_linter.py)

AST and static analyzer enforcing Zero-Mock & Anti-Spoofing Protocol v2
across repository and Council modules. Verifies zero stub logic, mocks,
synthetic bypasses, and prohibited unconstrained parallel libraries.
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("anti_spoof_linter")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

BANNED_PARALLEL_IMPORTS: Set[str] = {
    "dask",
    "parsl",
    "multiprocessing",
    "concurrent.futures",
}

BANNED_MOCK_IMPORTS: Set[str] = {
    "unittest.mock",
    "pytest_mock",
    "mock",
}

BANNED_KEYWORDS: Set[str] = {
    "mock",
    "example",
    "stub",
    "dummy",
    "placeholder",
    "fake",
    "sample",
}

BANNED_COMMENT_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"#\s*TODO(?::\s*implement)?\b", re.IGNORECASE),
    re.compile(r"#\s*FIXME(?::\s*implement)?\b", re.IGNORECASE),
    re.compile(r"#\s*XXX(?::\s*implement)?\b", re.IGNORECASE),
    re.compile(r"#\s*(?:mock|stub|dummy|placeholder|fake|sample)\b", re.IGNORECASE),
]

EXEMPTION_PHRASES: Set[str] = {
    "zero-stub",
    "mocking forbidden",
    "without mock",
    "anti-spoof",
    "anti_spoof",
    "anti-hallucination",
    "banned terms",
    "prohibited terms",
    "no-shortcut",
    "amnesty",
}

EXCLUDED_DIRS: Set[str] = {
    ".venv",
    ".conda",
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".vscode",
    ".idea",
    "node_modules",
}


def load_amnesty_list(search_path: Path) -> Set[str]:
    """Search for and load .anti_spoof_amnesty.json if available."""
    candidates = [
        search_path / ".anti_spoof_amnesty.json",
        search_path.parent / ".anti_spoof_amnesty.json",
        search_path.parent.parent / ".anti_spoof_amnesty.json",
        search_path.parent.parent / ".agent_artifacts" / ".anti_spoof_amnesty.json",
        Path.cwd() / ".anti_spoof_amnesty.json",
        Path.cwd() / ".agent_artifacts" / ".anti_spoof_amnesty.json",
    ]
    if "COCHEM_ARTIFACTS" in os.environ:
        candidates.append(Path(os.environ["COCHEM_ARTIFACTS"]) / ".anti_spoof_amnesty.json")
    if "COCHEM_ROOT" in os.environ:
        candidates.append(Path(os.environ["COCHEM_ROOT"]) / ".anti_spoof_amnesty.json")
        candidates.append(Path(os.environ["COCHEM_ROOT"]) / ".agent_artifacts" / ".anti_spoof_amnesty.json")

    for c in candidates:
        if c.exists() and c.is_file():
            try:
                data = json.loads(c.read_text(encoding="utf-8-sig"))
                if isinstance(data, list):
                    return set(data)
                elif isinstance(data, dict) and "files" in data:
                    return set(data["files"])
            except Exception as e:
                logger.warning(f"Could not load amnesty file {c}: {e}")
    return set()


def is_file_exempt(filepath: Path, amnesty_set: Set[str]) -> bool:
    """Determine if a file is exempt from anti-spoof checks."""
    posix_str = filepath.as_posix()
    if posix_str in amnesty_set:
        return True
    for entry in amnesty_set:
        if entry in posix_str:
            return True

    # Exemption for proposal docs and anti-spoof tools
    if ".docs" in filepath.parts and "improvements" in filepath.parts and filepath.suffix == ".md":
        return True
    if any(phrase in filepath.name.lower() for phrase in ("anti_spoof", "anti-spoof", "test_anti_spoof")):
        return True
    return False


def check_script(
    filepath: Path,
    strict_mode: bool = False,
    amnesty_set: Optional[Set[str]] = None,
) -> List[str]:
    """Analyze a single Python script for banned imports, stubs, and keywords."""
    if amnesty_set and is_file_exempt(filepath, amnesty_set):
        return []

    try:
        content = filepath.read_text(encoding="utf-8-sig", errors="replace")
    except Exception as e:
        return [f"[LINT ERROR] Cannot read {filepath}: {e}"]

    lines = content.splitlines()
    violations: List[str] = []

    # 1. Regex comment inspection (strict mode)
    if strict_mode:
        for idx, line in enumerate(lines, start=1):
            line_lower = line.lower()
            if any(phrase in line_lower for phrase in EXEMPTION_PHRASES):
                continue
            for pat in BANNED_COMMENT_PATTERNS:
                match = pat.search(line)
                if match:
                    violations.append(
                        f"Line {idx}: Banned comment pattern '{match.group(0)}' in {filepath.name}: {line.strip()}"
                    )

    # 2. AST parsing & inspection
    try:
        tree = ast.parse(content, filename=str(filepath))
    except SyntaxError as e:
        return [f"[LINT ERROR] Syntax error in {filepath} at line {e.lineno}: {e.msg}"]

    banned_imports = BANNED_PARALLEL_IMPORTS | BANNED_MOCK_IMPORTS

    class AntiSpoofVisitor(ast.NodeVisitor):
        def is_line_exempt(self, lineno: int) -> bool:
            if 1 <= lineno <= len(lines):
                s = lines[lineno - 1].lower()
                return any(phrase in s for phrase in EXEMPTION_PHRASES)
            return False

        def check_ident(self, name: str, node: ast.AST, context: str) -> None:
            if not strict_mode:
                return
            lower = name.lower()
            tokens = set(re.findall(r"[a-z]+", re.sub(r"([A-Z])", r" \1", name).lower()))
            for kw in BANNED_KEYWORDS:
                if kw in tokens or kw in lower:
                    lineno = getattr(node, "lineno", 1)
                    if not self.is_line_exempt(lineno):
                        violations.append(
                            f"Line {lineno}: Banned keyword '{kw}' in {context} '{name}'"
                        )

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                base_module = alias.name.split(".")[0]
                if base_module in banned_imports or alias.name in banned_imports:
                    if not self.is_line_exempt(node.lineno):
                        violations.append(
                            f"Line {node.lineno}: Prohibited spoof/parallel import '{alias.name}'"
                        )
                self.check_ident(alias.asname or alias.name, node, "import alias")
            self.generic_visit(node)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if node.module:
                base_module = node.module.split(".")[0]
                if base_module in banned_imports or node.module in banned_imports:
                    if not self.is_line_exempt(node.lineno):
                        violations.append(
                            f"Line {node.lineno}: Prohibited spoof/parallel module 'from {node.module} import ...'"
                        )
            for alias in node.names:
                self.check_ident(alias.name, node, "imported symbol")
            self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.check_ident(node.name, node, "function name")
            if strict_mode:
                self.check_stubs(node)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.check_ident(node.name, node, "async function name")
            if strict_mode:
                self.check_stubs(node)
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.check_ident(node.name, node, "class name")
            self.generic_visit(node)

        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, (ast.Store, ast.Param)):
                self.check_ident(node.id, node, "variable name")
            self.generic_visit(node)

        def check_stubs(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> None:
            body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
            decorators = [d.id for d in node.decorator_list if isinstance(d, ast.Name)]
            decorators += [d.attr for d in node.decorator_list if isinstance(d, ast.Attribute)]
            if "abstractmethod" in decorators or "overload" in decorators:
                return

            if len(body) == 1:
                single = body[0]
                if isinstance(single, ast.Pass):
                    if not self.is_line_exempt(single.lineno):
                        violations.append(
                            f"Line {single.lineno}: Unimplemented 'pass' stub in function '{node.name}'"
                        )
                elif isinstance(single, ast.Raise):
                    exc_name = ""
                    if isinstance(single.exc, ast.Name):
                        exc_name = single.exc.id
                    elif isinstance(single.exc, ast.Call) and isinstance(single.exc.func, ast.Name):
                        exc_name = single.exc.func.id
                    if exc_name in {"NotImplementedError", "RuntimeError"}:
                        if not self.is_line_exempt(single.lineno):
                            violations.append(
                                f"Line {single.lineno}: Stub function raising '{exc_name}' in '{node.name}'"
                            )

    AntiSpoofVisitor().visit(tree)
    return violations


def run_linter(
    target_path: Path,
    strict_mode: bool = False,
    amnesty_set: Optional[Set[str]] = None,
) -> Tuple[bool, Dict[str, List[str]]]:
    """Execute anti-spoof linter across target file or directory tree."""
    if amnesty_set is None:
        amnesty_set = load_amnesty_list(target_path)

    all_violations: Dict[str, List[str]] = {}

    if target_path.is_file():
        if target_path.suffix == ".py":
            v = check_script(target_path, strict_mode=strict_mode, amnesty_set=amnesty_set)
            if v:
                all_violations[str(target_path)] = v
    elif target_path.is_dir():
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]
            for f in files:
                if f.endswith(".py"):
                    p = Path(root) / f
                    v = check_script(p, strict_mode=strict_mode, amnesty_set=amnesty_set)
                    if v:
                        all_violations[str(p)] = v

    passed = len(all_violations) == 0
    return passed, all_violations


def main() -> int:
    parser = argparse.ArgumentParser(description="CoChem Anti-Spoof Static Linter")
    parser.add_argument("target", nargs="?", default=".", help="Path to file or directory to scan")
    parser.add_argument("--strict", action="store_true", help="Enable strict keyword, comment, and stub checks")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    if not target.exists():
        print(f"Error: Path {target} does not exist.")
        return 1

    strict = args.strict or os.environ.get("SPOOF_STRICT_MODE", "false").lower() in {"1", "true", "yes"}
    amnesty = load_amnesty_list(target)
    passed, violations = run_linter(target, strict_mode=strict, amnesty_set=amnesty)

    if not passed:
        print(f"[SPOOFING DETECTED] Violations found in {target}:")
        for f, v_list in violations.items():
            print(f"File: {f}")
            for item in v_list:
                print(f"  - {item}")
        return 1

    mode_label = "strict zero-mock/stub/parallel" if strict else "zero-mock/parallel"
    print(f"[LINT SUCCESS] No violations ({mode_label}) detected in {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
