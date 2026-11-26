"""Hard CI AST gate prohibiting mocks, indirect mock aliases, monkeypatch, fake_* helpers,
simulation mode, non-empty amnesty, and tracked PNG/PDF mockup leaks."""
from __future__ import annotations

import ast
import concurrent.futures
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _import_root in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_import_root) not in sys.path:
        sys.path.insert(0, str(_import_root))

from ci_tools.anti_spoof_linter import check_file as linter_check_file
from cochem_base.provenance.citations import (
    CitationTracker,
    EngineCitation,
    get_bibtex_catalog,
)

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
    "responses",
    "vcr",
    "vcrpy",
    "requests_mock",
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
    "MockerFixture",
    "MockFixture",
})

BANNED_MOCK_FIXTURES = frozenset({
    "mocker",
    "class_mocker",
    "module_mocker",
    "package_mocker",
    "session_mocker",
    "requests_mock",
})

BANNED_EXACT_IDENTIFIERS = frozenset({
    "generate_deterministic_solver_output",
    "poll_or_simulate_execution",
    "COLAB_WORKER_FAKE_GPU_NAME",
    "simulated_temp",
    "dummy_force",
})

SCIENTIFIC_ENGINE_MODULE_PREFIXES = (
    "cochem_base.",
    "cochem.",
    "pyscf",
    "gpu4pyscf",
    "psi4",
    "ase",
    "rdkit",
    "torch",
    "mace",
    "orca",
    "cfour",
    "xtb",
    "crest",
    "multiwfn",
    "nbo",
    "spcat",
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MOCKUP_METADATA_RE = re.compile(
    r"cochem:mockup\s*(?:=\s*['\"]?true['\"]?|>\s*true\s*</cochem:mockup>)",
    re.IGNORECASE,
)
NOT_SCIENTIFIC_DATA_RE = re.compile(r"NOT\s+SCIENTIFIC\s+DATA", re.IGNORECASE)


def _is_banned_module(module: str) -> bool:
    return any(module == banned or module.startswith(banned + ".") for banned in BANNED_IMPORT_MODULES)


def _is_scientific_engine_module(module: str) -> bool:
    return any(
        module == prefix.rstrip(".") or module.startswith(prefix)
        for prefix in SCIENTIFIC_ENGINE_MODULE_PREFIXES
    )


def _is_test_path(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/")
    parts = Path(normalized).parts
    stem = Path(normalized).stem.lower()
    return (
        "tests" in parts
        or "test_suite" in parts
        or stem.startswith("test_")
        or stem.endswith("_test")
        or "test" in stem
    )


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
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _extract_constant_str(node.left)
        right = _extract_constant_str(node.right)
        if left is not None and right is not None:
            return left + right
    if isinstance(node, ast.JoinedStr):
        parts = [
            _extract_constant_str(part.value if isinstance(part, ast.FormattedValue) else part)
            for part in node.values
        ]
        if all(part is not None for part in parts):
            return "".join(part for part in parts if part is not None)
    return None


class _ZeroMockScanner(ast.NodeVisitor):
    """Alias-aware AST scanner for zero-mock and zero-simulation enforcement."""

    def __init__(self, normalized_path: str) -> None:
        self.normalized = normalized_path
        self.is_test = _is_test_path(normalized_path)
        self.aliases: dict[str, str] = {}
        self.violations: list[str] = []

    def _add(self, node: ast.AST, msg: str) -> None:
        self.violations.append(f"{self.normalized}:{getattr(node, 'lineno', 1)}: {msg}")

    def _qualified(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            base = self._qualified(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return ""

    def _resolve_dynamic_import_target(self, node: ast.Call) -> str | None:
        target = _extract_constant_str(node.args[0]) if node.args else None
        package: str | None = None
        fromlist_items: list[str] = []
        for kw in node.keywords:
            if kw.arg == "name" and target is None:
                target = _extract_constant_str(kw.value)
            elif kw.arg == "package":
                package = _extract_constant_str(kw.value)
            elif kw.arg == "fromlist" and isinstance(kw.value, (ast.List, ast.Tuple, ast.Set)):
                for elt in kw.value.elts:
                    item = _extract_constant_str(elt)
                    if item:
                        fromlist_items.append(item)
        if not fromlist_items and len(node.args) >= 4 and isinstance(node.args[3], (ast.List, ast.Tuple, ast.Set)):
            for elt in node.args[3].elts:
                item = _extract_constant_str(elt)
                if item:
                    fromlist_items.append(item)
        if target and package and target.startswith("."):
            target = f"{package}.{target.lstrip('.')}"
        if target and fromlist_items:
            for item in fromlist_items:
                candidate = f"{target}.{item}"
                if _is_banned_module(candidate):
                    return candidate
        return target

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            bound = alias.asname or alias.name.split(".")[0]
            self.aliases[bound] = alias.name if alias.asname else alias.name.split(".")[0]
            if _is_banned_module(alias.name):
                self._add(node, f"banned import {alias.name!r}")
            if alias.asname and _is_banned_identifier(alias.asname):
                self._add(node, f"banned import alias {alias.asname!r}")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        if _is_banned_module(mod):
            self._add(node, f"banned from-import {mod!r}")
        for alias in node.names:
            full = f"{mod}.{alias.name}" if mod else alias.name
            self.aliases[alias.asname or alias.name] = full
            if _is_banned_module(full):
                self._add(node, f"banned import {full!r}")
            if _is_banned_identifier(alias.name):
                self._add(node, f"banned imported symbol {alias.name!r}")
            if alias.asname and _is_banned_identifier(alias.asname):
                self._add(node, f"banned import alias {alias.asname!r}")

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if _is_banned_identifier(node.name):
            self._add(node, f"banned function name {node.name!r}")
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
                self._add(node, f"banned parameter {arg.arg!r}")
            if arg.arg in BANNED_MOCK_FIXTURES:
                self._add(node, f"banned mock fixture parameter {arg.arg!r}")

        prev_aliases = self.aliases
        self.aliases = dict(prev_aliases)
        for arg in all_args:
            self.aliases.pop(arg.arg, None)
        try:
            self.generic_visit(node)
        finally:
            self.aliases = prev_aliases

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if _is_banned_identifier(node.name):
            self._add(node, f"banned class name {node.name!r}")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if _is_banned_identifier(node.id):
            self._add(node, f"banned symbol reference {node.id!r}")
        if node.id in BANNED_MOCK_FIXTURES:
            self._add(node, f"banned mock fixture reference {node.id!r}")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if _is_banned_identifier(node.attr):
            self._add(node, f"banned attribute reference '.{node.attr}'")
        qualified = self._qualified(node)
        if any(qualified == mod or qualified.startswith(mod + ".") for mod in BANNED_IMPORT_MODULES):
            self._add(node, f"banned mock module attribute reference {qualified!r}")
        self.generic_visit(node)

    def visit_keyword(self, node: ast.keyword) -> None:
        if node.arg and _is_banned_identifier(node.arg):
            self._add(node, f"banned keyword argument {node.arg!r}")
        if node.arg == "mode" and _extract_constant_str(node.value) == "simulation":
            self._add(node, "banned mode='simulation' keyword argument")
        self.generic_visit(node)

    def _record_alias_assign(self, target: ast.AST, value: ast.AST) -> None:
        if isinstance(target, ast.Name):
            if isinstance(value, (ast.Name, ast.Attribute)):
                self.aliases[target.id] = self._qualified(value)
            else:
                self.aliases.pop(target.id, None)
        elif isinstance(target, ast.Subscript) and self._qualified(target.value) == "sys.modules":
            key_str = _extract_constant_str(target.slice)
            if key_str and _is_banned_module(key_str):
                self._add(target, f"banned sys.modules mock injection {key_str!r}")
            elif self.is_test and key_str and _is_scientific_engine_module(key_str):
                rhs_call = self._qualified(value.func) if isinstance(value, ast.Call) else ""
                if not rhs_call.endswith("module_from_spec"):
                    self._add(target, f"banned sys.modules scientific engine injection {key_str!r}")

    def visit_Assign(self, node: ast.Assign) -> None:
        if _extract_constant_str(node.value) == "simulation":
            for target in node.targets:
                if (
                    (isinstance(target, ast.Name) and target.id == "mode")
                    or (isinstance(target, ast.Attribute) and target.attr == "mode")
                ):
                    self._add(node, "banned mode='simulation' assignment")
        for target in node.targets:
            self._record_alias_assign(target, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            if _extract_constant_str(node.value) == "simulation":
                if (
                    (isinstance(node.target, ast.Name) and node.target.id == "mode")
                    or (isinstance(node.target, ast.Attribute) and node.target.attr == "mode")
                ):
                    self._add(node, "banned mode='simulation' annotated assignment")
            self._record_alias_assign(node.target, node.value)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if self._qualified(node.value) == "sys.modules":
            key_str = _extract_constant_str(node.slice)
            if key_str and _is_banned_module(key_str):
                self._add(node, f"banned sys.modules mock access {key_str!r}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        qualified = self._qualified(node.func)
        callee = qualified.rsplit(".", 1)[-1]

        if callee in {"import_module", "__import__"} or qualified in {
            "importlib.import_module",
            "builtins.__import__",
        }:
            target_mod = self._resolve_dynamic_import_target(node)
            if target_mod and _is_banned_module(target_mod):
                self._add(node, f"banned dynamic import {target_mod!r}")

        if qualified in {"getattr", "builtins.getattr"} and len(node.args) >= 2:
            attr_name = _extract_constant_str(node.args[1])
            if attr_name in BANNED_SYMBOL_NAMES or attr_name in {"mock", "__import__", "patch"}:
                self._add(node, f"banned dynamic getattr mock lookup {attr_name!r}")

        if isinstance(node.func, ast.Attribute) and self._qualified(node.func.value) == "sys.modules":
            if callee in {"get", "setdefault", "pop"} and node.args:
                mod_key = _extract_constant_str(node.args[0])
                if mod_key and _is_banned_module(mod_key):
                    self._add(node, f"banned sys.modules.{callee}({mod_key!r})")
                elif self.is_test and callee == "setdefault" and mod_key and _is_scientific_engine_module(mod_key):
                    self._add(node, f"banned sys.modules.setdefault scientific engine injection {mod_key!r}")
            elif callee == "update":
                for arg in node.args:
                    if isinstance(arg, ast.Dict):
                        for k in arg.keys:
                            if k is not None:
                                mod_key = _extract_constant_str(k)
                                if mod_key and _is_banned_module(mod_key):
                                    self._add(node, f"banned sys.modules.update({mod_key!r})")
                                elif self.is_test and mod_key and _is_scientific_engine_module(mod_key):
                                    self._add(node, f"banned sys.modules.update scientific engine injection {mod_key!r}")
                for kw in node.keywords:
                    if kw.arg and _is_banned_module(kw.arg):
                        self._add(node, f"banned sys.modules.update({kw.arg!r})")

        if self.is_test and qualified in {"setattr", "delattr", "builtins.setattr", "builtins.delattr"}:
            if not node.args or not isinstance(node.args[0], ast.Name) or node.args[0].id not in {"self", "cls"}:
                self._add(node, f"banned bare {qualified} targeting foreign/engine object in test")

        self.generic_visit(node)


def scan_source_for_zero_mock_violations(source: str, rel_path: str) -> list[str]:
    """Scan Python source AST for banned mock imports, indirect aliases, monkeypatch, fake_* symbols, or mode='simulation'."""
    normalized = rel_path.replace("\\", "/")
    if normalized in EXCLUDED_RELATIVE_PATHS:
        return []

    try:
        tree = ast.parse(source, filename=normalized)
    except SyntaxError as exc:
        return [f"{normalized}:{exc.lineno or 1}: syntax error while scanning ({exc.msg})"]

    scanner = _ZeroMockScanner(normalized)
    scanner.visit(tree)
    return sorted(set(scanner.violations))


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


def _extract_png_text_payloads(data: bytes) -> list[tuple[str, str]]:
    """Parse PNG tEXt, zTXt, and iTXt metadata chunks without external dependencies."""
    if not data.startswith(PNG_SIGNATURE):
        return []
    payloads: list[tuple[str, str]] = []
    pos = len(PNG_SIGNATURE)
    total = len(data)
    while pos + 12 <= total:
        chunk_len = struct.unpack(">I", data[pos:pos + 4])[0]
        chunk_type = data[pos + 4:pos + 8]
        chunk_data = data[pos + 8:pos + 8 + chunk_len]
        pos += 12 + chunk_len
        if chunk_type == b"tEXt":
            sep = chunk_data.find(b"\x00")
            if sep != -1:
                kw = chunk_data[:sep].decode("latin-1", errors="replace")
                val = chunk_data[sep + 1:].decode("latin-1", errors="replace")
                payloads.append((kw, val))
        elif chunk_type == b"zTXt":
            sep = chunk_data.find(b"\x00")
            if sep != -1 and sep + 2 <= len(chunk_data):
                kw = chunk_data[:sep].decode("latin-1", errors="replace")
                try:
                    val = zlib.decompress(chunk_data[sep + 2:]).decode("latin-1", errors="replace")
                    payloads.append((kw, val))
                except zlib.error:
                    pass
        elif chunk_type == b"iTXt":
            sep = chunk_data.find(b"\x00")
            if sep != -1 and sep + 3 <= len(chunk_data):
                kw = chunk_data[:sep].decode("latin-1", errors="replace")
                comp_flag = chunk_data[sep + 1]
                rest = chunk_data[sep + 3:]
                # Skip language tag and translated keyword NUL-terminated fields
                lang_sep = rest.find(b"\x00")
                if lang_sep != -1:
                    rest = rest[lang_sep + 1:]
                    trans_sep = rest.find(b"\x00")
                    if trans_sep != -1:
                        text_bytes = rest[trans_sep + 1:]
                        if comp_flag == 1:
                            try:
                                text_bytes = zlib.decompress(text_bytes)
                            except zlib.error:
                                text_bytes = b""
                        payloads.append((kw, text_bytes.decode("utf-8", errors="replace")))
        if chunk_type == b"IEND":
            break
    return payloads


def _extract_pdf_text_segments(data: bytes) -> list[str]:
    """Extract raw PDF metadata/XMP text plus decompressed FlateDecode stream bodies."""
    segments: list[str] = [data.decode("latin-1", errors="replace")]
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, flags=re.DOTALL):
        raw_stream = match.group(1)
        try:
            decompressed = zlib.decompress(raw_stream)
            segments.append(decompressed.decode("latin-1", errors="replace"))
        except zlib.error:
            pass
    return segments


def scan_media_bytes_for_mockup_markers(data: bytes, rel_path: str) -> list[str]:
    """Inspect a PNG or PDF byte payload for `cochem:mockup=true` metadata or `NOT SCIENTIFIC DATA` markers."""
    normalized = rel_path.replace("\\", "/")
    suffix = Path(normalized).suffix.lower()
    violations: list[str] = []

    if suffix == ".png":
        for kw, val in _extract_png_text_payloads(data):
            if kw.strip().lower() == "cochem:mockup" and val.strip().lower() == "true":
                violations.append(f"{normalized}: prohibited PNG metadata cochem:mockup=true")
            combined = f"{kw}={val}"
            if MOCKUP_METADATA_RE.search(combined):
                violations.append(f"{normalized}: prohibited PNG metadata cochem:mockup=true ({kw})")
            if NOT_SCIENTIFIC_DATA_RE.search(val) or NOT_SCIENTIFIC_DATA_RE.search(kw):
                violations.append(f"{normalized}: prohibited PNG 'NOT SCIENTIFIC DATA' marker ({kw})")
        raw_text = data.decode("latin-1", errors="replace")
        if MOCKUP_METADATA_RE.search(raw_text):
            violations.append(f"{normalized}: prohibited raw PNG cochem:mockup=true marker")
        if NOT_SCIENTIFIC_DATA_RE.search(raw_text):
            violations.append(f"{normalized}: prohibited raw PNG 'NOT SCIENTIFIC DATA' marker")

    elif suffix == ".pdf":
        for segment in _extract_pdf_text_segments(data):
            if MOCKUP_METADATA_RE.search(segment):
                violations.append(f"{normalized}: prohibited PDF XMP/metadata cochem:mockup=true")
            if NOT_SCIENTIFIC_DATA_RE.search(segment):
                violations.append(f"{normalized}: prohibited PDF 'NOT SCIENTIFIC DATA' marker")

    return sorted(set(violations))


def scan_repository_for_mockup_leaks(root: Path = REPO_ROOT) -> list[str]:
    """Scan all tracked PNG and PDF files in the repository for mockup metadata or disclaimer markers."""
    media_paths: list[Path] = []
    if (root / ".git").exists():
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--", "*.png", "*.PNG", "*.pdf", "*.PDF"],
            capture_output=True,
            check=False,
        )
        if proc.returncode == 0:
            for item in proc.stdout.decode("utf-8", errors="replace").split("\x00"):
                if item:
                    candidate = root / item
                    if candidate.is_file():
                        media_paths.append(candidate)
    else:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
            for filename in sorted(filenames):
                if filename.lower().endswith((".png", ".pdf")):
                    media_paths.append(Path(dirpath) / filename)

    violations: list[str] = []
    for path in sorted(set(media_paths)):
        rel = path.relative_to(root).as_posix()
        violations.extend(scan_media_bytes_for_mockup_markers(path.read_bytes(), rel))
    return violations


def _build_minimal_png(extra_chunks: list[tuple[bytes, bytes]] | None = None) -> bytes:
    """Build a valid 1x1 RGB PNG binary with optional custom metadata chunks."""
    def _chunk(ctype: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(ctype + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + ctype + payload + struct.pack(">I", crc)

    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = _chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
    chunks = [PNG_SIGNATURE, ihdr]
    for ctype, payload in extra_chunks or []:
        chunks.append(_chunk(ctype, payload))
    chunks.append(idat)
    chunks.append(_chunk(b"IEND", b""))
    return b"".join(chunks)


def test_anti_spoof_amnesty_is_empty() -> None:
    """Enforce that `.anti_spoof_amnesty.json` has been burned down to `[]` (0 entries)."""
    assert AMNESTY_FILE.is_file(), ".anti_spoof_amnesty.json must exist at repository root"
    parsed = json.loads(AMNESTY_FILE.read_text(encoding="utf-8"))
    assert parsed == [], f"Expected empty amnesty [], found {len(parsed)} entries: {parsed[:5]}"


def test_zero_mock_and_no_simulation_across_repository() -> None:
    """Enforce zero mocks, indirect mock aliases, monkeypatch, fake_*, or mode='simulation' across all Python files."""
    violations = scan_repository_for_zero_mock(REPO_ROOT)
    assert violations == [], (
        f"Zero-mock / zero-simulation AST gate failed with {len(violations)} violation(s):\n"
        + "\n".join(violations[:50])
    )


def test_no_mockup_leaks_in_tracked_images_and_pdfs() -> None:
    """Reject cochem:mockup=true PNG tEXt/PDF XMP metadata and 'NOT SCIENTIFIC DATA' markers in tracked images/PDFs."""
    violations = scan_repository_for_mockup_leaks(REPO_ROOT)
    assert violations == [], (
        f"Mockup-leak firewall failed with {len(violations)} violation(s):\n"
        + "\n".join(violations[:50])
    )


def test_zero_mock_gate_self_test() -> None:
    """Verify the AST gate reliably detects core prohibited categories and accepts authentic code."""
    banned_mod = "unittest.mock"
    banned_sym = "AsyncMock"
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


def test_seeded_canaries_widened_indirect_mock_aliases(tmp_path: Path) -> None:
    """Seeded-canary verification proving every widened mock alias is caught by BOTH AST scanners."""
    canaries = [
        ("tests/canary_from_unittest_alias.py", "from unittest import mock as m\n"),
        ("tests/canary_import_unittest_alias.py", "import unittest.mock as um\n"),
        ("tests/canary_importlib_unittest_mock.py", "import importlib\nmod = importlib.import_module('unittest.mock')\n"),
        ("tests/canary_importlib_mock.py", "import importlib\nmod = importlib.import_module('mock')\n"),
        ("tests/canary_importlib_pytest_mock.py", "import importlib\nmod = importlib.import_module('pytest_mock')\n"),
        ("tests/canary_importlib_alias_concat.py", "from importlib import import_module as im\nim('unittest.' + 'mock')\n"),
        ("tests/canary_importlib_relative_pkg.py", "import importlib\nimportlib.import_module('.mock', package='unittest')\n"),
        ("tests/canary_sys_modules_read.py", "import sys\nref = sys.modules['unittest.mock']\n"),
        ("tests/canary_sys_modules_inject.py", "import sys\nsys.modules['unittest.mock'] = object()\n"),
        ("tests/canary_sys_modules_alias_get.py", "import sys as s\ns.modules.get('pytest_mock')\n"),
        ("tests/canary_sys_modules_engine_inject.py", "import sys\nsys.modules['cochem_base.calc.cfour_execution'] = object()\n"),
        ("tests/canary_builtins_dunder_import.py", "import builtins\nbuiltins.__import__('unittest.mock')\n"),
        ("tests/canary_builtins_alias_import.py", "from builtins import __import__ as bi\nbi('mock')\n"),
        ("tests/canary_bare_dunder_import.py", "__import__('pytest_mock')\n"),
        ("tests/canary_pytest_mock_import.py", "import pytest_mock\n"),
        ("tests/canary_mocker_fixture.py", "def test_engine(mocker):\n    return mocker.patch('os.system')\n"),
        ("tests/canary_responses_import.py", "import responses\n"),
        ("tests/canary_vcr_import.py", "import vcr\n"),
        ("tests/canary_vcrpy_import.py", "import vcrpy\n"),
        ("tests/canary_requests_mock_import.py", "import requests_mock\n"),
        ("tests/canary_requests_mock_fixture.py", "def test_http(requests_mock):\n    return requests_mock.get('https://example.org')\n"),
        ("tests/canary_bare_setattr_engine.py", "import cochem_base.calc.cfour_execution as eng\nsetattr(eng, 'run', lambda *a: None)\n"),
        ("tests/canary_bare_delattr_engine.py", "import cochem_base.calc.xtb_execution as eng\ndelattr(eng, 'run')\n"),
        ("tests/canary_builtins_setattr_engine.py", "import builtins as b\nimport cochem_base.calc.pyscf_execution as eng\nb.setattr(eng, 'run', lambda *a: None)\n"),
    ]

    for rel_path, source in canaries:
        gate_hits = scan_source_for_zero_mock_violations(source, rel_path)
        assert gate_hits, f"Zero-mock gate missed seeded canary {rel_path}:\n{source}"

        canary_file = tmp_path / rel_path
        canary_file.parent.mkdir(parents=True, exist_ok=True)
        canary_file.write_text(source, encoding="utf-8")
        linter_hits = linter_check_file(canary_file, tmp_path, amnesty_set=set())
        assert linter_hits, f"anti_spoof_linter missed seeded canary {rel_path}:\n{source}"


def test_stdlib_concurrency_modules_permitted_without_amnesty(tmp_path: Path) -> None:
    """Confirm stdlib threading, multiprocessing, and concurrent.futures remain allowed without amnesty."""
    clean_concurrency = (
        "import concurrent.futures\n"
        "import multiprocessing\n"
        "import threading\n\n"
        "def run_pool(items):\n"
        "    lock = threading.Lock()\n"
        "    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:\n"
        "        out = list(pool.map(lambda x: x * x, items))\n"
        "    with lock:\n"
        "        return out, multiprocessing.cpu_count()\n"
    )
    assert scan_source_for_zero_mock_violations(clean_concurrency, "tests/clean_concurrency_sample.py") == []
    sample_file = tmp_path / "tests" / "clean_concurrency_sample.py"
    sample_file.parent.mkdir(parents=True, exist_ok=True)
    sample_file.write_text(clean_concurrency, encoding="utf-8")
    assert linter_check_file(sample_file, tmp_path, amnesty_set=set()) == []


def test_serial_vs_parallel_concurrency_determinism_and_no_swallowed_exceptions() -> None:
    """Verify ThreadPoolExecutor(max_workers=1) vs (max_workers=2) is bit-identical on real BASE hashing and propagates exceptions."""
    catalog = get_bibtex_catalog()
    engine_keys = sorted(catalog.keys())
    assert len(engine_keys) >= 20

    def _compute_deterministic_digest(engine_id: str) -> tuple[str, str]:
        tracker = CitationTracker()
        assert tracker.register_engine(engine_id) is True
        rendered = tracker.generate_bibtex_string(deduplicate=True)
        digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
        return engine_id, digest

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as serial_pool:
        serial_results = list(serial_pool.map(_compute_deterministic_digest, engine_keys))

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as parallel_pool:
        parallel_results = list(parallel_pool.map(_compute_deterministic_digest, engine_keys))

    assert serial_results == parallel_results
    serial_bundle_hash = hashlib.sha256(json.dumps(serial_results).encode("utf-8")).hexdigest()
    parallel_bundle_hash = hashlib.sha256(json.dumps(parallel_results).encode("utf-8")).hexdigest()
    assert serial_bundle_hash == parallel_bundle_hash

    def _register_or_raise(bibtex_body: str) -> str:
        tracker = CitationTracker()
        tracker.register_custom_citation(
            EngineCitation(
                engine_id="custom_check",
                name="Custom Check",
                category="Validation",
                description="Exception propagation verification",
                bibtex=bibtex_body,
            )
        )
        return tracker.generate_bibtex_string()

    valid_entry = catalog[engine_keys[0]]
    invalid_entry = "@article{BrokenEntry, title = {Unbalanced"

    for workers in (1, 2):
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_register_or_raise, payload) for payload in (valid_entry, invalid_entry)]
            assert futures[0].result()
            with pytest.raises(ValueError, match="Invalid BibTeX syntax"):
                futures[1].result()


def test_mockup_leak_firewall_catches_seeded_png_and_pdf_markers(tmp_path: Path) -> None:
    """Verify the mockup-leak firewall rejects seeded PNG tEXt/zTXt and PDF XMP/text markers while accepting clean files."""
    clean_png = _build_minimal_png([(b"tEXt", b"Software\x00CoChem-BASE")])
    assert scan_media_bytes_for_mockup_markers(clean_png, "figures/clean.png") == []

    bad_png_text = _build_minimal_png([(b"tEXt", b"cochem:mockup\x00true")])
    assert scan_media_bytes_for_mockup_markers(bad_png_text, "figures/bad_meta.png")

    bad_png_banner = _build_minimal_png([(b"tEXt", b"Comment\x00NOT SCIENTIFIC DATA - illustrative")])
    assert scan_media_bytes_for_mockup_markers(bad_png_banner, "figures/bad_banner.png")

    bad_png_ztxt = _build_minimal_png([(b"zTXt", b"cochem:mockup\x00\x00" + zlib.compress(b"true"))])
    assert scan_media_bytes_for_mockup_markers(bad_png_ztxt, "figures/bad_ztxt.png")

    clean_pdf = b"%PDF-1.4\n1 0 obj << /Producer (CoChem-BASE) >> endobj\n%%EOF\n"
    assert scan_media_bytes_for_mockup_markers(clean_pdf, "docs/clean.pdf") == []

    bad_pdf_xmp = (
        b"%PDF-1.4\n1 0 obj << /Type /Metadata /Subtype /XML >>\nstream\n"
        b"<x:xmpmeta><rdf:RDF><rdf:Description cochem:mockup=\"true\"/></rdf:RDF></x:xmpmeta>\n"
        b"endstream\nendobj\n%%EOF\n"
    )
    assert scan_media_bytes_for_mockup_markers(bad_pdf_xmp, "docs/bad_xmp.pdf")

    bad_pdf_compressed_marker = (
        b"%PDF-1.4\n1 0 obj << /Filter /FlateDecode >>\nstream\n"
        + zlib.compress(b"BT (NOT SCIENTIFIC DATA) Tj ET")
        + b"\nendstream\nendobj\n%%EOF\n"
    )
    assert scan_media_bytes_for_mockup_markers(bad_pdf_compressed_marker, "docs/bad_flate.pdf")

    # End-to-end directory scan check on tmp_path
    (tmp_path / "clean.png").write_bytes(clean_png)
    assert scan_repository_for_mockup_leaks(tmp_path) == []
    (tmp_path / "leaked.png").write_bytes(bad_png_text)
    leaks = scan_repository_for_mockup_leaks(tmp_path)
    assert any("leaked.png" in hit for hit in leaks)


if __name__ == "__main__":
    found = scan_repository_for_zero_mock(REPO_ROOT) + scan_repository_for_mockup_leaks(REPO_ROOT)
    if found:
        print("Zero-mock & mockup-leak gate FAILED:\n" + "\n".join(found), file=sys.stderr)
        raise SystemExit(1)
    print("Zero-mock & mockup-leak gate PASSED: 0 violations, 0 mockup leaks, and empty .anti_spoof_amnesty.json.")
    raise SystemExit(0)
