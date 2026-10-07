"""# zero-stub anti-spoofing engine
CoChem Anti-Spoof Linter (ci_tools/anti_spoof_linter.py)

Authoritative AST and static analyzer enforcing Zero-Mock & Anti-Spoofing Protocol v2
across the CoChem repository, Council modules, and execution pipelines. Verifies zero
stub logic, mocks, and generated data promoted as physical evidence.
Legitimate numerical algorithms and concurrency imports are not substitutions.
"""

from __future__ import annotations

import argparse
import ast
import base64
import binascii
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

logger = logging.getLogger("anti_spoof_linter")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

AMNESTY_FILENAME: str = ".anti_spoof_amnesty.json"


class AntiSpoofLinterError(RuntimeError):
    """Raised by the fail-closed API when an audit detects violations."""

    def __init__(self, violations: Dict[str, List["Violation"]]) -> None:
        self.violations = violations
        super().__init__(f"Anti-spoof audit found {sum(map(len, violations.values()))} violations")

BANNED_MOCK_MODULES: Set[str] = {
    "unittest.mock",
    "mock",
    "pytest_mock",
}

BANNED_MOCK_ATTRIBUTES: Set[str] = {
    "MagicMock",
    "Mock",
    "patch",
    "PropertyMock",
    "AsyncMock",
    "create_autospec",
    "NonCallableMock",
    "call_args",
    "mock_open",
}

# Historical catalog retained for callers which inventory parallel libraries.
# REQ-BASE-016 isolates CI from application imports; it does not ban the real
# Parsl/shared-memory/threading implementations required elsewhere in the SRS.
BANNED_CONCURRENCY_MODULES: Set[str] = {
    "multiprocessing",
    "concurrent.futures",
    "parsl",
    "dask",
    "ray",
    "mpi4py",
    "threading",
    "celery",
}

BANNED_NUMPY_GENERATORS: Set[str] = {
    "linspace",
    "zeros",
    "ones",
    "eye",
    "identity",
    "sin",
    "rand",
    "randn",
    "normal",
    "uniform",
    "choice",
    "randint",
}

BANNED_IDENTIFIER_WORDS: Set[str] = {
    "dummy",
    "fake",
    "placeholder",
    "synthetic",
    "stub",
    "mock",
}

BANNED_OBFUSCATION_TOKENS: Set[str] = {
    "exec",
    "eval",
    "__import__",
}

BANNED_SKIP_SYMBOLS: Set[str] = {
    "skip",
    "skipif",
    "xfail",
    "exit",
    "skipIf",
    "skipUnless",
    "skipTest",
}

BANNED_STATE_TOKENS: Set[str] = {
    "swarm_state",
    "draco_state",
    "audit_verdict",
    "council_verdict",
}

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

EXEMPTION_PHRASES: Set[str] = {
    "zero-stub",
    "mocking forbidden",
    "without mock",
    "anti-spoof",
    "anti_spoof",
    "anti-hallucination",
    "amnesty",
}


@dataclass(frozen=True)
class Violation:
    """Immutable record of an anti-spoof or zero-mock compliance violation."""
    file_path: str
    line: int
    col: int
    category: str
    symbol: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file_path,
            "line": self.line,
            "col": self.col,
            "category": self.category,
            "symbol": self.symbol,
            "message": self.message,
        }


def normalize_path_entry(path_str: str) -> Tuple[str, ...]:
    """Normalize a path entry into unified posix format with sub-path aliases."""
    clean = path_str.replace("\\", "/").strip("/")
    parts = clean.split("/")
    variants = [clean]
    if len(parts) > 1 and parts[0].lower().startswith("cochem"):
        variants.append("/".join(parts[1:]))
    return tuple(dict.fromkeys(variants))


def find_repository_root(start_path: Union[str, Path]) -> Path:
    """Locate the root directory of the repository via indicators, env var, or traversal."""
    if "COCHEM_ROOT" in os.environ and os.environ["COCHEM_ROOT"]:
        return Path(os.environ["COCHEM_ROOT"]).resolve()

    p = Path(start_path).resolve()
    if p.is_file():
        p = p.parent

    current = p
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / AMNESTY_FILENAME).exists() or (current / ".git").exists():
            return current
        current = current.parent

    return p


def load_amnesty(root_dir: Union[str, Path]) -> Set[str]:
    """Load authorized zero-mock amnesty whitelist from .anti_spoof_amnesty.json."""
    p = Path(root_dir).resolve()
    target_file = p if p.is_file() and p.name == AMNESTY_FILENAME else None

    if not target_file:
        candidates = [
            p / AMNESTY_FILENAME,
            p.parent / AMNESTY_FILENAME,
            p.parent.parent / AMNESTY_FILENAME,
        ]
        if "COCHEM_ROOT" in os.environ:
            candidates.append(Path(os.environ["COCHEM_ROOT"]) / AMNESTY_FILENAME)
        for c in candidates:
            if c.exists() and c.is_file():
                target_file = c
                break

    if not target_file or not target_file.exists():
        return set()

    amnesty_set: Set[str] = set()
    try:
        content = target_file.read_text(encoding="utf-8-sig")
        data = json.loads(content)
        raw_entries: List[str] = []
        if isinstance(data, list):
            raw_entries = [str(x) for x in data]
        elif isinstance(data, dict):
            files_field = data.get("files", [])
            if isinstance(files_field, list):
                raw_entries = [str(x) for x in files_field]
            elif isinstance(files_field, dict):
                raw_entries = list(files_field.keys())

        for entry in raw_entries:
            for variant in normalize_path_entry(entry):
                amnesty_set.add(variant)
    except Exception as e:
        logger.warning(f"Could not parse amnesty file {target_file}: {e}")

    return amnesty_set


def save_amnesty(root_dir: Path, violations_dict: Dict[str, List[Violation]]) -> Path:
    """Record findings in the legacy report format without authorizing a bypass."""
    target_file = root_dir / AMNESTY_FILENAME
    entries = sorted(violations_dict.keys())
    data = {
        "description": "Strict AST findings for review; these entries do not waive executable integrity checks.",
        "files": entries,
    }
    target_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return target_file


class SpoofVisitor(ast.NodeVisitor):
    """Detect executable substitution and generated values promoted as evidence.

    Array allocation, interpolation grids, locks, state filenames and template
    vocabulary are not evidence. A generator becomes an integrity violation at
    a physical-result sink. Imports are resolved, so aliases cannot conceal the
    prohibited operation. This is a static guard, not a proof of physics: real
    engine acceptance and provenance validation remain separate requirements.
    """

    PHYSICAL_FIELDS = {
        "energy", "energy_hartree", "energy_ev", "forces", "hessian",
        "frequencies", "frequencies_cm1", "dipole", "dipole_moment",
        "elapsed_seconds", "wall_time_seconds", "atomic_masses",
    }
    SUCCESS_FIELDS = {"converged", "success", "passed", "verified"}
    GENERATORS = (BANNED_NUMPY_GENERATORS - {"sin"}) | {"full", "zeros_like", "ones_like", "empty", "empty_like"}

    def __init__(self, filepath: Path, rel_path: str, is_exempt: bool, amnesty_set: Set[str]):
        self.filepath = filepath
        self.rel_path = rel_path
        self.is_exempt = is_exempt
        self.amnesty_set = amnesty_set  # legacy API; never exempts executable violations
        self.violations: List[Violation] = []
        self.is_test_file = "test" in filepath.stem.lower() or "tests" in filepath.parts
        self.aliases: Dict[str, str] = {}
        self.values: Dict[str, ast.AST] = {}
        self.parents: List[ast.AST] = []

    def visit(self, node: ast.AST) -> Any:
        self.parents.append(node)
        try:
            return super().visit(node)
        finally:
            self.parents.pop()

    def _report(self, node: ast.AST, category: str, symbol: str, message: str) -> None:
        if not self.is_exempt:
            self.violations.append(Violation(
                self.rel_path, getattr(node, "lineno", 1), getattr(node, "col_offset", 0),
                category, symbol, message,
            ))

    def _qualified(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return self._qualified(node.value) + "." + node.attr
        return ""

    def _check_import(self, module: str, node: ast.AST) -> None:
        if any(module == item or module.startswith(item + ".") for item in BANNED_MOCK_MODULES):
            self._report(node, "MOCK_IMPORT", module, "Prohibited mock framework import")
        root, _, symbol = module.rpartition(".")
        if root.startswith(("pytest", "unittest")) and symbol in BANNED_SKIP_SYMBOLS:
            self._report(node, "PYTEST_SKIP", module, "Prohibited test suppression import")

    def visit_Import(self, node: ast.Import) -> None:
        for item in node.names:
            self.aliases[item.asname or item.name.split(".")[0]] = item.name if item.asname else item.name.split(".")[0]
            self._check_import(item.name, node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for item in node.names:
            module = ".".join(part for part in (node.module, item.name) if part)
            self.aliases[item.asname or item.name] = module
            self._check_import(module, node)

    @staticmethod
    def _body(node: Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef]) -> List[ast.stmt]:
        return [item for item in node.body if not (
            isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str)
        )]

    @staticmethod
    def _empty(body: Sequence[ast.stmt]) -> bool:
        return not body or all(isinstance(item, ast.Pass) or (
            isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) and item.value.value is ...
        ) for item in body)

    def visit_FunctionDef(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> None:
        decorators = {self._qualified(item).rsplit(".", 1)[-1] for item in node.decorator_list}
        if self._empty(self._body(node)) and not decorators.intersection({"abstractmethod", "overload"}):
            self._report(node, "EMPTY_PASS_STUB", node.name, "Empty pass/ellipsis function implementation")
        arguments = [*node.args.posonlyargs, *node.args.args]
        defaults = list(zip(arguments[len(arguments) - len(node.args.defaults):], node.args.defaults))
        defaults.extend(zip(node.args.kwonlyargs, node.args.kw_defaults))
        for argument, default in defaults:
            if argument.arg == "converged" and isinstance(default, ast.Constant) and default.value is True:
                self._report(default, "DEFAULT_CONVERGENCE", argument.arg,
                             "A result parameter must not assume unreported convergence")
        previous = self.values
        previous_aliases = self.aliases
        self.values = dict(previous)
        self.aliases = dict(previous_aliases)
        # A parameter shadows an outer assignment rather than inheriting its value.
        for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
            self.values.pop(argument.arg, None)
            self.aliases.pop(argument.arg, None)
        try:
            self.generic_visit(node)
        finally:
            self.values = previous
            self.aliases = previous_aliases

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        # A subclass inherits executable behavior (including exception semantics).
        # An empty root class cannot supply an implementation.
        if self._empty(self._body(node)) and not node.bases:
            self._report(node, "EMPTY_PASS_STUB", node.name, "Empty root class implementation")
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> None:
        expression = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
        if expression is not None and self._qualified(expression).rsplit(".", 1)[-1] == "NotImplementedError":
            self._report(node, "NOT_IMPLEMENTED_ERROR", "NotImplementedError", "Unimplemented callable dead-end")
        if expression is not None and self._qualified(expression).rsplit(".", 1)[-1] == "InterfaceUnavailableError":
            self._report(node, "MISSING_CAPABILITY", "InterfaceUnavailableError",
                         "Advertised compatibility interface has no implementation in this checkout")
        self.generic_visit(node)

    def _value_kind(self, expression: ast.AST, seen: Optional[Set[str]] = None) -> str:
        """Classify direct local scalar/array constructions, preserving dependencies.

        Combining an initialized accumulator with data from another operation is
        arithmetic, not invented evidence. Unknown calls never count as verified
        evidence; their provenance is checked by runtime result validation.
        """
        seen = seen or set()
        if isinstance(expression, ast.Name) and expression.id in self.values and expression.id not in seen:
            return self._value_kind(self.values[expression.id], seen | {expression.id})
        if isinstance(expression, ast.Constant) and isinstance(expression.value, (int, float, bool)):
            return "literal"
        if isinstance(expression, ast.UnaryOp):
            return self._value_kind(expression.operand, seen)
        if isinstance(expression, (ast.List, ast.Tuple)):
            kinds = [self._value_kind(item, seen) for item in expression.elts]
            return "literal" if kinds and all(k == "literal" for k in kinds) else ""
        if isinstance(expression, ast.Call):
            name = self._qualified(expression.func)
            parts = name.split(".")
            if parts[0] in {"numpy", "random"} and parts[-1] in self.GENERATORS:
                return "generated"
            if name in {"float", "int", "numpy.array", "numpy.asarray", "numpy.float64"} and expression.args:
                return self._value_kind(expression.args[0], seen)
        if isinstance(expression, ast.BinOp):
            left, right = self._value_kind(expression.left, seen), self._value_kind(expression.right, seen)
            if left and right:
                return "generated" if "generated" in {left, right} else "literal"
        return ""

    def visit_Assign(self, node: ast.Assign) -> None:
        self.generic_visit(node)
        for target in node.targets:
            self._record_assignment(target, node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if (isinstance(node.target, ast.Name) and node.target.id == "converged"
                and len(self.parents) >= 2 and isinstance(self.parents[-2], ast.ClassDef)):
            value = node.value
            if isinstance(value, ast.Call):
                value = next((item.value for item in value.keywords if item.arg == "default"),
                             value.args[0] if value.args else None)
            if isinstance(value, ast.Constant) and value.value is True:
                self._report(node, "DEFAULT_CONVERGENCE", node.target.id,
                             "A result model must not assume unreported convergence")
        self.generic_visit(node)
        if node.value is not None:
            self._record_assignment(node.target, node.value)

    def _record_assignment(self, target: ast.AST, value: ast.AST) -> None:
        if isinstance(target, ast.Name):
            self.values[target.id] = value
            if isinstance(value, (ast.Name, ast.Attribute)):
                self.aliases[target.id] = self._qualified(value)
            elif isinstance(value, ast.Call) and self._qualified(value.func) in {
                "numpy.random.default_rng", "numpy.random.RandomState",
            }:
                self.aliases[target.id] = "numpy.random.Generator"
            else:
                self.aliases.pop(target.id, None)
        elif isinstance(target, ast.Subscript):
            if isinstance(target.value, ast.Name) and not self._value_kind(value):
                # A work array filled from computed inputs is no longer merely
                # its allocation. Literal writes retain generated provenance.
                self.values.pop(target.value.id, None)
            if isinstance(target.slice, ast.Constant) and target.slice.value in self.PHYSICAL_FIELDS:
                self._check_evidence([(str(target.slice.value), value)], target)
        elif isinstance(target, ast.Attribute) and target.attr in self.PHYSICAL_FIELDS:
            # Only direct generated arrays are prohibited here: numeric scalar
            # initialization alone is not a claim that a calculation succeeded.
            self._check_evidence([(target.attr, value)], target)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.generic_visit(node)
        if isinstance(node.target, ast.Name):
            previous = self.values.pop(node.target.id, None)
            if previous is not None and self._value_kind(node.value):
                self.values[node.target.id] = ast.BinOp(previous, node.op, node.value)
        elif isinstance(node.target, ast.Subscript):
            if isinstance(node.target.value, ast.Name) and not self._value_kind(node.value):
                self.values.pop(node.target.value.id, None)

    def _check_evidence(self, pairs: Sequence[Tuple[str, ast.AST]], node: ast.AST) -> None:
        succeeded = any(
            (key in self.SUCCESS_FIELDS and isinstance(value, ast.Constant) and value.value is True)
            or (key == "status" and isinstance(value, ast.Constant) and value.value in {"SUCCESS", "PASSED", "CONVERGED"})
            for key, value in pairs
        )
        for key, value in pairs:
            kind = self._value_kind(value)
            if key in self.PHYSICAL_FIELDS and (kind == "generated" or (succeeded and kind == "literal")):
                self._report(value, "SYNTHETIC_DATA", key,
                             "Generated or literal values promoted directly to physical result evidence")
            if key in BANNED_STATE_TOKENS and isinstance(value, ast.Constant) and value.value in {True, "PASS", "PASSED", "SUCCESS", "VERIFIED"}:
                self._report(value, "STATE_MUTATION_BAN", key, "Hardcoded successful audit verdict without evaluated evidence")

    def visit_Dict(self, node: ast.Dict) -> None:
        pairs: List[Tuple[str, ast.AST]] = []
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                pairs.append((key.value, value))
            elif key is None and isinstance(value, ast.Dict):
                pairs.extend((key.value, val) for key, val in zip(value.keys, value.values)
                             if isinstance(key, ast.Constant) and isinstance(key.value, str))
        self._check_evidence(pairs, node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = self._qualified(node.func)
        symbol = name.rsplit(".", 1)[-1]
        if name in BANNED_OBFUSCATION_TOKENS or name in {"builtins.eval", "builtins.exec", "builtins.__import__"}:
            self._report(node, "OBFUSCATION", name, "Prohibited dynamic code execution")
        if symbol in {"import_module", "__import__"} and node.args:
            target = self._extract_concat_str(node.args[0])
            if target:
                self._check_import(target, node)
        if name.startswith(("unittest.mock.", "mock.", "pytest_mock.")) or symbol in BANNED_MOCK_ATTRIBUTES:
            self._report(node, "MOCK_USAGE", name, "Prohibited mock interface substitution")
        if symbol in BANNED_SKIP_SYMBOLS and (name.startswith(("pytest.", "unittest.")) or symbol == "skipTest"):
            self._report(node, "PYTEST_SKIP", name, "Prohibited test suppression")
        if isinstance(node.func, ast.Attribute) and symbol in {"setattr", "delattr", "setitem", "delitem", "setenv", "delenv", "syspath_prepend", "chdir"}:
            owner = self._qualified(node.func.value).lower()
            if "monkey" in owner or owner in {"mp", "patcher"}:
                self._report(node, "MONKEYPATCH_INTERCEPT", name, "Prohibited replacement of an executing interface/environment")
        if self.is_test_file and name in {"setattr", "delattr"}:
            if not node.args or not isinstance(node.args[0], ast.Name) or node.args[0].id not in {"self", "cls"}:
                self._report(node, "MONKEYPATCH_INTERCEPT", name, "Foreign object modification in test")
        if name in {"getattr", "builtins.getattr"} and len(node.args) > 1:
            attribute = self._extract_concat_str(node.args[1])
            if attribute in BANNED_MOCK_ATTRIBUTES or attribute == "mock":
                self._report(node, "MOCK_USAGE", str(attribute), "Dynamic mock interface access")
        if symbol in {"raises", "assertRaises"} and node.args and self._qualified(node.args[0]) == "NotImplementedError":
            self._report(node, "NOT_IMPLEMENTED_ERROR", symbol, "Test asserts an unimplemented callable")
        if symbol in {"get", "setdefault"} and len(node.args) >= 2:
            if (isinstance(node.args[0], ast.Constant) and node.args[0].value == "converged"
                    and isinstance(node.args[1], ast.Constant) and node.args[1].value is True):
                self._report(node, "DEFAULT_CONVERGENCE", name,
                             "Missing convergence evidence cannot default to successful convergence")
        self._check_evidence([(item.arg, item.value) for item in node.keywords if item.arg], node)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        name = self._qualified(node)
        if node.attr in BANNED_SKIP_SYMBOLS and name.startswith(("pytest.", "unittest.")):
            self._report(node, "PYTEST_SKIP", name, "Prohibited test suppression decorator or reference")
        self.generic_visit(node)

    @staticmethod
    def _extract_concat_str(node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = SpoofVisitor._extract_concat_str(node.left), SpoofVisitor._extract_concat_str(node.right)
            if left is not None and right is not None:
                return left + right
        if isinstance(node, ast.JoinedStr):
            parts = [SpoofVisitor._extract_concat_str(
                part.value if isinstance(part, ast.FormattedValue) else part
            ) for part in node.values]
            if all(part is not None for part in parts):
                return "".join(part for part in parts if part is not None)
        return None

    def visit_BinOp(self, node: ast.BinOp) -> None:
        reconstructed = self._extract_concat_str(node)
        if reconstructed and any(token in reconstructed.lower() for token in ("unittest.mock", "magicmock")):
            self._report(node, "OBFUSCATION", reconstructed, "Obfuscated mock module/symbol")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            value = node.value.strip()
            decoded: List[str] = []
            if len(value) >= 4 and len(value) % 4 == 0 and re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", value):
                try:
                    decoded.append(base64.b64decode(value, validate=True).decode("utf-8"))
                except (binascii.Error, UnicodeDecodeError):
                    decoded.clear()
            if len(value) >= 8 and len(value) % 2 == 0 and re.fullmatch(r"[0-9a-fA-F]+", value):
                try:
                    decoded.append(bytes.fromhex(value).decode("utf-8"))
                except UnicodeDecodeError:
                    decoded.clear()
            if any(token in text.lower() for text in decoded for token in ("mock", "fake")):
                self._report(node, "OBFUSCATION", value, "Encoded mock payload")
        self.generic_visit(node)

def _self_import_violations(tree: ast.AST, file_path: Path, repo_root: Path, rel_path: str) -> List[Violation]:
    """Catch circular re-export shells without importing the application.

    Package initializers may import existing child modules. A module importing
    its own implementation, including relative imports, cannot supply that
    implementation and must remain a visible architectural failure.
    """
    try:
        relative = file_path.relative_to(repo_root).with_suffix("")
    except ValueError:
        return []
    parts = list(relative.parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts.pop()
    variants = [parts]
    if parts and parts[0] == "src":
        variants.append(parts[1:])
    module_names = {".".join(value) for value in variants if value}
    violations: List[Violation] = []
    pending = [tree]
    while pending:
        node = pending.pop()
        # A function can inspect its already initialized module at runtime.
        # Circular compatibility shells execute their imports during module
        # initialization, including conditional imports and class bodies.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        pending.extend(ast.iter_child_nodes(node))
        imported: Set[str] = set()
        if isinstance(node, ast.Import):
            imported.update(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom):
            bases = {node.module or ""}
            if node.level:
                bases = set()
                for variant in variants:
                    package = variant if is_package else variant[:-1]
                    if node.level <= len(package):
                        prefix = package[:len(package) - node.level + 1]
                        bases.add(".".join(prefix + ([node.module] if node.module else [])))
            for base in bases:
                for item in node.names:
                    imported.add(".".join(part for part in (base, item.name) if part))
                if base in module_names:
                    children_exist = is_package and all(
                        (file_path.parent / (item.name + ".py")).is_file()
                        or (file_path.parent / item.name / "__init__.py").is_file()
                        for item in node.names
                    )
                    if not children_exist:
                        imported.add(base)
        for module in sorted(imported & module_names):
            violations.append(Violation(
                rel_path, node.lineno, node.col_offset, "SELF_IMPORT", module,
                "A module cannot re-export its missing implementation by importing itself",
            ))
    return violations


def check_file(
    file_path: Path,
    repo_root: Path,
    amnesty_set: Set[str],
) -> List[Violation]:
    """Analyze a single Python file for AST anti-spoof violations."""
    file_path = file_path.absolute()
    repo_root = repo_root.absolute()
    rel_path = file_path.relative_to(repo_root).as_posix() if repo_root in file_path.parents or file_path == repo_root else file_path.name

    try:
        content = file_path.read_text(encoding="utf-8-sig")
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError as e:
        return [
            Violation(
                file_path=rel_path,
                line=e.lineno or 1,
                col=e.offset or 0,
                category="SYNTAX_ERROR",
                symbol="ast.parse",
                message=f"Syntax error: {e.msg}",
            )
        ]
    except Exception as e:
        return [
            Violation(
                file_path=rel_path,
                line=1,
                col=0,
                category="IO_ERROR",
                symbol="file_read",
                message=f"Could not read file: {e}",
            )
        ]

    visitor = SpoofVisitor(
        filepath=file_path,
        rel_path=rel_path,
        is_exempt=False,
        amnesty_set=amnesty_set,
    )
    visitor.visit(tree)
    visitor.violations.extend(_self_import_violations(tree, file_path, repo_root, rel_path))
    if "ci_tools" in Path(rel_path).parts:
        # This architectural boundary is never waived by concurrency amnesty.
        application_roots = {"src", "cochem", "cochem_base", "cochem_topos", "cochem_geom"}
        source_dir = repo_root / "src"
        if source_dir.is_dir():
            application_roots.update(p.name for p in source_dir.iterdir() if p.is_dir())
        for node in ast.walk(tree):
            imports: List[str] = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imports = [node.module or ""]
            elif isinstance(node, ast.Call) and node.args:
                func = node.func
                qualified = visitor._qualified(func)
                dynamic_import = qualified in {"__import__", "builtins.__import__", "importlib.import_module"}
                if dynamic_import:
                    value = visitor._extract_concat_str(node.args[0])
                    if value is not None:
                        imports = [value]
            for module in imports:
                if module.split(".", 1)[0] in application_roots:
                    visitor.violations.append(Violation(
                        file_path=rel_path,
                        line=node.lineno,
                        col=node.col_offset,
                        category="CI_APPLICATION_IMPORT",
                        symbol=module,
                        message="CI tools must not import the application plane (REQ-BASE-016)",
                    ))
    return visitor.violations


def run_linter(
    targets: Optional[Sequence[Union[str, Path]]] = None,
    repo_root: Optional[Path] = None,
    strict_mode: bool = True,
    generate_amnesty: bool = False,
) -> Tuple[int, Dict[str, List[Violation]]]:
    """Execute anti-spoof static analysis across specified targets or whole repository."""
    if not repo_root:
        repo_root = find_repository_root(targets[0] if targets else Path.cwd())
    repo_root = repo_root.resolve()

    amnesty_set = load_amnesty(repo_root)
    all_violations: Dict[str, List[Violation]] = {}
    inspected: Set[Path] = set()

    target_paths: List[Path] = []
    if targets:
        for t in targets:
            t_str = str(t)
            if "*" in t_str or "?" in t_str:
                pattern = Path(t_str).as_posix()
                matched = list(repo_root.glob(pattern)) if not Path(t_str).is_absolute() else [Path(p) for p in Path(pattern).parent.glob(Path(pattern).name)]
                for m in matched:
                    if m.exists():
                        target_paths.append(m.resolve())
                if not matched:
                    all_violations[t_str] = [Violation(
                        t_str, 1, 0, "IO_ERROR", "target", "Target pattern matched no files"
                    )]
            else:
                tp = Path(t).resolve()
                if tp.exists():
                    target_paths.append(tp)
                else:
                    all_violations[t_str] = [Violation(
                        t_str, 1, 0, "IO_ERROR", "target", "Audit target does not exist"
                    )]
    else:
        target_paths = [repo_root]

    for tp in target_paths:
        if tp.is_file() and tp.suffix == ".py":
            inspected.add(tp)
            v = check_file(tp, repo_root, amnesty_set)
            if v:
                all_violations[str(tp.relative_to(repo_root) if repo_root in tp.parents else tp.name)] = v
        elif tp.is_dir():
            for root, dirs, files in os.walk(tp):
                dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]
                for f in files:
                    if f.endswith(".py"):
                        p = Path(root) / f
                        inspected.add(p)
                        v = check_file(p, repo_root, amnesty_set)
                        if v:
                            all_violations[str(p.relative_to(repo_root) if repo_root in p.parents else p.name)] = v

    if not inspected:
        all_violations["<audit>"] = [Violation(
            "<audit>", 1, 0, "IO_ERROR", "target", "Audit inspected no Python files"
        )]

    if generate_amnesty:
        # Recording findings never changes the strict exit status. Historical
        # concurrency amnesty does not waive executable substitution findings.
        save_amnesty(repo_root, all_violations)

    has_violations = len(all_violations) > 0
    exit_code = 1 if (has_violations and strict_mode) else 0
    return exit_code, all_violations


def assert_compliant(
    targets: Optional[Sequence[Union[str, Path]]] = None,
    repo_root: Optional[Path] = None,
) -> None:
    """Raise AntiSpoofLinterError when the mandatory strict audit fails."""
    exit_code, violations = run_linter(targets=targets, repo_root=repo_root)
    if exit_code:
        raise AntiSpoofLinterError(violations)


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="CoChem Anti-Spoof Linter & Zero-Mock Enforcement Engine")
    parser.add_argument("targets", nargs="*", default=[], help="File(s) or directory paths to audit")
    parser.add_argument("--json", action="store_true", help="Output results in structured JSON format")
    parser.add_argument("--strict", action="store_true", default=True, help="Fail with non-zero exit code if violations found (default)")
    parser.add_argument("--generate-amnesty", action="store_true", help="Record findings in the legacy report format; violations still fail")
    args = parser.parse_args(argv)

    targets = [Path(t) for t in args.targets] if args.targets else [Path.cwd()]
    repo_root = find_repository_root(targets[0])

    exit_code, violations = run_linter(
        targets=targets,
        repo_root=repo_root,
        strict_mode=args.strict,
        generate_amnesty=args.generate_amnesty,
    )

    total_violations = sum(len(v_list) for v_list in violations.values())

    if args.json:
        output_payload = {
            "exit_code": exit_code,
            "violations_count": total_violations,
            "files_count": len(violations),
            "violations": {f: [v.to_dict() for v in v_list] for f, v_list in violations.items()},
        }
        print(json.dumps(output_payload, indent=2))
        return exit_code

    if total_violations == 0:
        print("[LINT SUCCESS] No prohibited AST patterns detected; physical acceptance is a separate gate.")
        return 0

    print(f"[SPOOFING DETECTED] Found {total_violations} violation(s) across {len(violations)} file(s):")
    for f, v_list in violations.items():
        print(f"\nFile: {f}")
        for v in v_list:
            print(f"  - Line {v.line}:{v.col} [{v.category}] ({v.symbol}): {v.message}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
