"""
CoChem Zero-Static-Dictionary AST Linter & Anti-Mock Sentinel.
WBS 1.2.3: Zero-Static-Dictionary AST Linter & Anti-Mock Sentinel (ci_tools/mendeleev_ast_linter.py)

Authoritative AST static analyzer enforcing the Mendeleev Library Mandate and
Anti-Spoofing Protocol v4 across the CoChem repository. Scans dictionary literals
(ast.Dict), dictionary constructors (ast.Call), and assignment nodes across
cochem_base/, raising fail-closed errors if keys match chemical element symbols
mapped to floating-point mass constants. Mandates that all atomic/isotopic mass
constants are dynamically fetched via cochem_base.physics.nuclide_resolver or
the mendeleev library.

Distinguishes static atomic mass dictionaries from geometric radius/valence/symmetry
constants (covalent radii, vdW radii, point group orders, atomic number integers).
"""
from __future__ import annotations

import argparse
import ast
import functools
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

logger = logging.getLogger("mendeleev_ast_linter")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

DEFAULT_AMNESTY_FILE = ".anti_spoof_amnesty.json"

# Compatibility name only: source paths can never waive scientific checks.
BUILTIN_LEGACY_AMNESTY_PATHS = frozenset()

EXCLUDED_DIR_NAMES: Set[str] = {
    "build",
    "dist",
    ".venv",
    ".conda",
    "venv",
    "site-packages",
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".vscode",
    ".idea",
    ".trash",
    "node_modules",
}

# Target variable tokens explicitly designating atomic masses, weights, or isotopic tables
SUSPICIOUS_MASS_TARGET_NAMES: Set[str] = {
    "MASS",
    "MASSES",
    "WEIGHT",
    "WEIGHTS",
    "ATOMIC_MASS",
    "ATOMIC_WEIGHT",
    "ISOTOPE_MASS",
    "ISOTOPIC_MASS",
    "NUCLEAR_MASS",
    "MOLAR_MASS",
    "PINNED_STANDARD_ATOMIC_WEIGHTS",
    "PINNED_ISOTOPIC_MASSES",
    "ELEMENT_MASS",
    "ELEMENT_MASSES",
}

# Target variable tokens designating geometric, valence, symmetry, or charge constants
# (Distinguished from static mass dictionaries under Method Matrix v4.1 / WBS 1.2.3)
BENIGN_NON_MASS_TARGET_NAMES: Set[str] = {
    "RADIUS",
    "RADII",
    "VDW",
    "COVALENT",
    "BONDRADII",
    "COV_TABLE",
    "VDW_TABLE",
    "RADII_ANG",
    "RADII_PM",
    "COV_RADII",
    "VALENCE",
    "VALENCES",
    "VALENCY",
    "OXIDATION",
    "ELECTRONEGATIVITY",
    "POINT_GROUP",
    "SYMMETRY",
    "ROTATION",
    "SIGMA",
    "SIGMAS",
    "ORDER",
    "ORDERS",
    "ATOMIC_NUMBER",
    "ATOMIC_NUMBERS",
    "SYMBOL_TO_ATOMIC_NUMBER",
    "Z_NUMBER",
    "ELEMENT_Z",
    "SYMBOL_TO_Z",
    "COLOR",
    "COLOUR",
    "CPK",
    "COORDINATION",
    "CHARGE",
    "CHARGES",
    "FORMAL_CHARGE",
}

# Standard non-element point group symbols to detect symmetry dictionaries
POINT_GROUP_SYMBOLS: Set[str] = {
    "C1", "Cs", "Ci", "C2", "C3", "C4", "C5", "C6", "C7", "C8",
    "C2v", "C3v", "C4v", "C5v", "C6v", "C2h", "C3h", "C4h", "C5h", "C6h",
    "D2", "D3", "D4", "D5", "D6", "D2d", "D3d", "D4d", "D5d", "D2h", "D3h", "D4h", "D5h", "D6h",
    "Td", "Oh", "Ih", "T", "O", "I", "Th", "Cinfv", "Dinfh", "Kh",
}

# Atomic weight and nuclide resolution symbols requiring authoritative import
ATOMIC_WEIGHT_ATTRIBUTES: Set[str] = {
    "atomic_weight",
    "standard_atomic_weight",
}

ATOMIC_WEIGHT_FUNCTIONS: Set[str] = {
    "resolve_nuclide_mass",
    "disambiguate_mass",
    "get_atomic_weight",
}


@dataclass(frozen=True)
class LinterViolation:
    """Immutable record of an AST static-mass or anti-mock violation."""
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


@functools.lru_cache(maxsize=1)
def load_periodic_table_symbols() -> Set[str]:
    """Dynamically query periodic table element symbols (Z=1..118) via mendeleev.

    Strictly satisfies the Dynamic Mendeleev Mandate: the linter dynamically
    introspects the mendeleev SQLite database without hardcoding static lists.
    Decorated with @functools.lru_cache(maxsize=1) for O(1) amortized reuse.
    """
    try:
        import mendeleev

        # Fast path: bulk attribute retrieval
        if hasattr(mendeleev, "get_attribute_for_all_elements"):
            try:
                syms = mendeleev.get_attribute_for_all_elements("symbol")
                if syms and len(syms) >= 118:
                    return set(syms)
            except Exception as exc:
                logger.debug("Mendeleev get_attribute_for_all_elements query failed: %s", exc)

        # Second fast path: get_all_elements()
        if hasattr(mendeleev, "get_all_elements"):
            try:
                syms = {
                    e.symbol
                    for e in mendeleev.get_all_elements()
                    if hasattr(e, "symbol") and e.symbol
                }
                if syms and len(syms) >= 118:
                    return syms
            except Exception as exc:
                logger.debug("Mendeleev get_all_elements iteration failed: %s", exc)

        # Per-element query fallback
        elements = set()
        for z in range(1, 119):
            try:
                el = mendeleev.element(z)
                if el and el.symbol:
                    elements.add(el.symbol)
            except Exception as exc:
                logger.debug("Mendeleev individual element query failed for Z=%s: %s", z, exc)
        if elements and len(elements) >= 118:
            return elements
    except ImportError as exc:
        logger.debug("Mendeleev package import unavailable: %s", exc)

    # These are element identifiers, never mass values. Keep the sentinel usable
    # with only the standard library, without importing the application it audits.
    return {
        "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
        "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca",
        "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
        "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr",
        "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
        "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd",
        "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb",
        "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
        "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th",
        "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm",
        "Md", "No", "Lr", "Rf", "Db", "Sg", "Bh", "Hs", "Mt", "Ds",
        "Rg", "Cn", "Nh", "Fl", "Mc", "Lv", "Ts", "Og"
    }


def normalize_path_posix(path_str: str) -> str:
    """Normalize file path to POSIX style with forward slashes."""
    return path_str.replace("\\", "/").strip("/")


def load_amnesty_file(amnesty_path=None) -> Set[str]:
    """Legacy API retained to reject attempts to exempt source files."""
    if amnesty_path is not None:
        raise ValueError("Mass-linter amnesty is forbidden; every source file must be checked")
    return set()


# Trust module identities, never an arbitrary import's chosen alias.
AUTHORITATIVE_MODULES = {
    "cochem_base.physics.nuclide_resolver",
    "cochem_base.physics.isotopes",
    "cochem_base.core.mendeleev_invariants",
    "cochem.core.mendeleev_invariants",
    "cochem.mobile.inorganic.models",
}


def _authoritative_module(name: str) -> bool:
    return name == "mendeleev" or name.startswith("mendeleev.") or name in AUTHORITATIVE_MODULES


def _literal_number(node: ast.AST):
    if isinstance(node, ast.Constant) and isinstance(node.value, (float, int)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _literal_number(node.operand)
        return None if value is None else (-value if isinstance(node.op, ast.USub) else value)
    return None


def _target_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _target_name(node.value)
    return ""


class MendeleevASTVisitor(ast.NodeVisitor):
    """Detect static mass tables and mass access without a genuine provider import.

    This is source analysis, not proof that a numerical result is authentic.
    Scientific execution still requires the separate runtime provenance gates.
    """

    def __init__(self, file_path: str, element_symbols: Set[str], source_lines: List[str]):
        self.file_path = file_path
        self.element_symbols = element_symbols
        self.source_lines = source_lines
        self.violations: List[LinterViolation] = []
        self._target = ""
        self.has_authoritative_mass_import = False
        self._atomic_weight_references = []
        self._import_origins = {}
        self._trusted_functions = set()
        self._defined_functions = set()

    def _violation(self, node, category, symbol, message):
        self.violations.append(LinterViolation(self.file_path, getattr(node, "lineno", 1),
                                              getattr(node, "col_offset", 0), category, symbol, message))

    def _expression_origin(self, node):
        if isinstance(node, ast.Name):
            return self._import_origins.get(node.id)
        if isinstance(node, ast.Call):
            return self._expression_origin(node.func)
        if isinstance(node, ast.Attribute):
            origin = self._expression_origin(node.value)
            return f"{origin}.{node.attr}" if origin else origin
        return None

    def visit_Import(self, node):
        for alias in node.names:
            self._import_origins[alias.asname or alias.name.split(".")[0]] = alias.name
            if _authoritative_module(alias.name):
                self.has_authoritative_mass_import = True
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        # A relative import must resolve against its actual package, not a name
        # that merely contains the word mendeleev or nuclide_resolver.
        if node.level:
            parts = Path(self.file_path).resolve().parent.parts
            try:
                package_start = next(i for i, part in enumerate(parts) if part in {"cochem", "cochem_base"})
                package = list(parts[package_start:])
                if node.level > 1:
                    package = package[:-(node.level - 1)]
                module = ".".join([*package, module]).rstrip(".")
            except StopIteration:
                module = ""
        for alias in node.names:
            full = f"{module}.{alias.name}" if module else ""
            self._import_origins[alias.asname or alias.name] = full
            if module and (_authoritative_module(module) or _authoritative_module(full)):
                self.has_authoritative_mass_import = True
                self._trusted_functions.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._defined_functions.add(node.name)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    @staticmethod
    def _mass_target(name):
        upper = name.upper()
        # These denote isotope identifiers or conversion factors, not mass values.
        if any(token in upper for token in ("MASS_NUMBER", "MASS_CONVERSION", "MASS_UNIT")):
            return False
        return any(token in upper for token in SUSPICIOUS_MASS_TARGET_NAMES)

    def _element_key(self, node):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            return None
        import re
        key = node.value.strip()
        if key.capitalize() in self.element_symbols:
            return key.capitalize()
        match = re.fullmatch(r"(?:[0-9]+)?([A-Z][a-z]?)(?:[-_][0-9]+)?", key)
        return match.group(1) if match and match.group(1) in self.element_symbols else None

    def _benign_numeric_mapping(self, target, pairs):
        upper = target.upper()
        if self._mass_target(target):
            return False
        values = [value for _, value in pairs]
        # Nuclear electric quadrupole moments have area units and may be signed;
        # they are a different physical quantity from isotope masses.
        if "QUADRUPOLE_MOMENT" in upper and "MBARN" in upper:
            return True
        if any(token in upper for token in ("RADIUS", "RADII", "VDW", "COVALENT", "COV_TABLE")):
            limit = 400.0 if "PM" in upper else 5.0
            return all(0 < value < limit for value in values)
        if any(token in upper for token in ("VALENCE", "VALENCY", "OXIDATION", "CHARGE", "COORDINATION")):
            return all(isinstance(value, int) and -12 <= value <= 12 for value in values)
        if any(token in upper for token in ("ATOMIC_NUMBER", "ELEMENT_Z", "SYMBOL_TO_Z", "MASS_NUMBER")):
            return all(isinstance(value, int) and 0 < value <= 400 for value in values)
        if "ELECTRONEGATIVITY" in upper:
            return all(0 <= value <= 5 for value in values)
        return False

    def _check_pairs(self, node, pairs, target):
        if not pairs or self._benign_numeric_mapping(target, pairs):
            return
        suspicious = self._mass_target(target)
        mass_values = any(
            isinstance(value, float) and (
                (symbol not in {"H", "He"} and value > 5)
                or (symbol == "H" and 1 < value < 1.015)
                or (symbol == "He" and 3.9 < value < 4.1)
            ) for symbol, value in pairs
        )
        if suspicious or mass_values:
            self._violation(node, "STATIC_MASS_DICTIONARY", target or "dict",
                            "Static atomic/isotopic mass values for " + ", ".join(symbol for symbol, _ in pairs[:5])
                            + " must be resolved through an authoritative dynamic mass provider.")

    def _check_mass_array(self, node, value, target):
        if not self._mass_target(target) or target.upper() in {"WEIGHT", "WEIGHTS"}:
            return
        sequence = value
        if isinstance(value, ast.Call) and isinstance(value.func, (ast.Name, ast.Attribute)):
            function = _target_name(value.func)
            if function not in {"array", "asarray", "tensor", "as_tensor"} or not value.args:
                return
            sequence = value.args[0]
        if isinstance(sequence, (ast.List, ast.Tuple)) and sequence.elts:
            if all(_literal_number(item) is not None for item in sequence.elts):
                self._violation(node, "STATIC_MASS_ARRAY", target,
                                "Literal mass arrays must be populated through a dynamic mass provider.")

    def _assignment(self, node, targets, value):
        value_origin = self._expression_origin(value) if value is not None else None
        for target in targets:
            name = _target_name(target)
            if value is not None:
                self._check_mass_array(node, value, name)
                if isinstance(target, ast.Subscript):
                    symbol, number = self._element_key(target.slice), _literal_number(value)
                    if symbol and number is not None:
                        self._check_pairs(node, [(symbol, number)], name)
            # Rebinding a provider name to another object cannot borrow its import.
            if isinstance(target, ast.Name) and target.id in self._import_origins and value is not None:
                if not (isinstance(value, ast.Constant) and value.value is None):
                    self._import_origins[target.id] = value_origin or ""
                    self._trusted_functions.discard(target.id)
            elif isinstance(target, ast.Name) and value_origin is not None:
                self._import_origins[target.id] = value_origin
        previous = self._target
        self._target = next((_target_name(target) for target in targets if self._mass_target(_target_name(target))),
                            _target_name(targets[0]) if targets else "")
        self.generic_visit(node)
        self._target = previous

    def visit_Assign(self, node):
        self._assignment(node, node.targets, node.value)

    def visit_AnnAssign(self, node):
        self._assignment(node, [node.target], node.value)

    def visit_NamedExpr(self, node):
        self._assignment(node, [node.target], node.value)

    def visit_Dict(self, node):
        pairs = []
        for key, value in zip(node.keys, node.values):
            symbol, number = self._element_key(key), _literal_number(value)
            if symbol and number is not None:
                pairs.append((symbol, number))
        self._check_pairs(node, pairs, self._target)
        self.generic_visit(node)

    def visit_DictComp(self, node):
        symbol, number = self._element_key(node.key), _literal_number(node.value)
        if symbol and number is not None:
            self._check_pairs(node, [(symbol, number)], self._target)
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == "dict":
            pairs = []
            for keyword in node.keywords:
                symbol = self._element_key(ast.Constant(keyword.arg))
                number = _literal_number(keyword.value)
                if symbol and number is not None:
                    pairs.append((symbol, number))
            if node.args and isinstance(node.args[0], (ast.List, ast.Tuple)):
                for pair in node.args[0].elts:
                    if isinstance(pair, (ast.List, ast.Tuple)) and len(pair.elts) == 2:
                        symbol, number = self._element_key(pair.elts[0]), _literal_number(pair.elts[1])
                        if symbol and number is not None:
                            pairs.append((symbol, number))
            self._check_pairs(node, pairs, self._target)
        for keyword in node.keywords:
            if keyword.arg:
                self._check_mass_array(node, keyword.value, keyword.arg)
        function = _target_name(node.func)
        if function in ATOMIC_WEIGHT_FUNCTIONS:
            self._atomic_weight_references.append((node.func, function, self._expression_origin(node.func)))
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if node.attr in ATOMIC_WEIGHT_ATTRIBUTES:
            self._atomic_weight_references.append((node, node.attr, self._expression_origin(node.value)))
        self.generic_visit(node)

    def finalize(self):
        # No filename exemption: the real resolver passes because it imports the
        # real provider, and a lookalike path still receives every check.
        for node, symbol, origin in self._atomic_weight_references:
            valid = self.has_authoritative_mass_import
            if origin is not None:
                valid = _authoritative_module(origin) or any(origin.startswith(module + ".") for module in AUTHORITATIVE_MODULES)
            elif isinstance(node, ast.Name):
                valid = node.id in self._trusted_functions or (node.id in self._defined_functions and valid)
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                root = node.value.id
                if root in self._import_origins:
                    origin = self._import_origins[root]
                    valid = _authoritative_module(origin) or any(origin.startswith(module + ".") for module in AUTHORITATIVE_MODULES)
            if not valid:
                self._violation(node, "UNRESOLVED_ATOMIC_WEIGHT_IMPORT", symbol,
                                "Mass access requires an import from the real mendeleev package or a known dynamic provider; aliases do not establish provenance.")


def _source_error(path, category, error):
    return LinterViolation(str(path), getattr(error, "lineno", 1) or 1,
                           getattr(error, "offset", 0) or 0, category, str(path), str(error))


def scan_file(file_path, element_symbols=None, amnesty_paths=None):
    """Read and parse every source file; failures are violations, never clean scans."""
    import io
    import tokenize
    path = Path(file_path).absolute()
    violations = []
    if amnesty_paths:
        violations.append(_source_error(path, "DISALLOWED_AMNESTY", "Mass-linter path exemptions are forbidden"))
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return [*violations, _source_error(path, "SOURCE_READ_ERROR", error)]
    try:
        tree = ast.parse(content, filename=str(path))
    except (SyntaxError, ValueError, RecursionError) as error:
        return [*violations, _source_error(path, "SOURCE_PARSE_ERROR", error)]
    for token in tokenize.generate_tokens(io.StringIO(content).readline):
        if token.type == tokenize.COMMENT and any(marker in token.string for marker in ("mendeleev-linter: disable", "noqa: mendeleev-ast")):
            violations.append(LinterViolation(str(path), token.start[0], token.start[1], "DISALLOWED_SUPPRESSION", "comment",
                                              "Inline comments cannot waive scientific mass checks"))
    # The optional cache argument may add identifiers, never remove the actual
    # periodic table from the analysis.
    symbols = load_periodic_table_symbols() | set(element_symbols or ())
    visitor = MendeleevASTVisitor(str(path), symbols, content.splitlines())
    visitor.visit(tree)
    visitor.finalize()
    return [*violations, *visitor.violations]


def scan_directory(target_dir, element_symbols=None, amnesty_paths=None):
    """Scan source trees and retain traversal/read/parse failure evidence."""
    path = Path(target_dir).absolute()
    if not path.is_dir():
        return scan_file(path, element_symbols, amnesty_paths)
    symbols = element_symbols if element_symbols is not None else load_periodic_table_symbols()
    violations = []
    def traversal_error(error):
        violations.append(_source_error(error.filename or path, "SOURCE_READ_ERROR", error))
    for root, directories, files in os.walk(path, onerror=traversal_error):
        directories[:] = [name for name in directories if name not in EXCLUDED_DIR_NAMES]
        for name in sorted(files):
            if name.endswith(".py"):
                violations.extend(scan_file(Path(root) / name, symbols, amnesty_paths))
    return violations


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Fail-closed dynamic atomic mass source checks")
    parser.add_argument("paths", nargs="*", default=["src/"])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-on-violation", action="store_true", default=True,
                        help="Compatibility flag; violations always fail")
    args = parser.parse_args(argv)
    symbols = load_periodic_table_symbols()
    violations = []
    for path in args.paths:
        violations.extend(scan_directory(path, symbols))
    if args.json:
        print(json.dumps({"total_violations": len(violations), "status": "FAIL" if violations else "PASS",
                          "violations": [item.to_dict() for item in violations]}, indent=2))
    else:
        for item in violations:
            print(f"{item.file_path}:{item.line}:{item.col} [{item.category}] {item.message}")
        print(f"[{'FAIL' if violations else 'PASS'}] {len(violations)} mass-source violations")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
