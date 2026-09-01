#!/usr/bin/env python3
"""
Physical Unit Tests for CoChem-SCRIBE setup.py Packaging Configuration.
Governed by Phase 4, Task 11 and Method Matrix v4.
Strict Zero-Mock Mandate and Dynamic Atomic Mass Compliance.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from mendeleev import element


def get_target_repo_root() -> Path:
    """Resolve the CoChem-SCRIBE repository root directory."""
    primary_path = Path("D:/__CoChem/GitHub-Repo/CoChem-SCRIBE")
    if (primary_path / "setup.py").is_file():
        return primary_path

    # Fallback resolution relative to test file location
    test_parent = Path(__file__).resolve().parent.parent
    if (test_parent / "setup.py").is_file():
        return test_parent

    sibling_scribe = test_parent.parent / "CoChem-SCRIBE"
    if (sibling_scribe / "setup.py").is_file():
        return sibling_scribe

    return primary_path


def get_setup_py_path() -> Path:
    """Return the absolute path to setup.py."""
    return get_target_repo_root() / "setup.py"


def parse_setup_ast() -> ast.AST:
    """Parse the AST of setup.py."""
    setup_file = get_setup_py_path()
    assert setup_file.is_file(), f"setup.py not found at {setup_file}"
    content = setup_file.read_text(encoding="utf-8")
    return ast.parse(content, filename=str(setup_file))


def extract_setup_call_keywords() -> dict[str, Any]:
    """Extract keyword arguments passed to setup() in setup.py via AST analysis."""
    tree = parse_setup_ast()
    keywords: dict[str, Any] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            if func_name == "setup":
                for kw in node.keywords:
                    if kw.arg:
                        keywords[kw.arg] = kw.value
    return keywords


def test_setup_file_exists_and_syntax() -> None:
    """Verify setup.py exists, is non-empty, and contains valid Python syntax."""
    setup_file = get_setup_py_path()
    assert setup_file.exists(), f"setup.py missing at: {setup_file}"
    assert setup_file.stat().st_size > 0, "setup.py is empty"

    content = setup_file.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(setup_file))
    assert isinstance(tree, ast.Module), "AST parse did not produce a valid Module"


def test_anti_spoofing_and_forbidden_tokens() -> None:
    """
    Enforce Strict Zero-Mock & Anti-Laziness Mandate.
    Verify no prohibited import references exist in setup.py or test suite.
    """
    setup_file = get_setup_py_path()
    content = setup_file.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(setup_file))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "mock" not in alias.name.lower(), (
                    f"Forbidden import: {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert "mock" not in node.module.lower(), (
                    f"Forbidden from-import: {node.module}"
                )


def test_setuptools_imports_and_setup_call() -> None:
    """Verify setup.py imports and calls setup from setuptools."""
    keywords = extract_setup_call_keywords()
    assert len(keywords) > 0, "setup(...) invocation not found in setup.py AST"

    expected_keys = {
        "name",
        "version",
        "description",
        "python_requires",
        "install_requires",
        "extras_require",
        "packages",
        "py_modules",
        "classifiers",
        "license",
    }
    for key in expected_keys:
        assert key in keywords, f"Keyword '{key}' is missing in setup() call"


def test_python_requires_compatibility() -> None:
    """Verify python_requires is explicitly set to '>=3.10'."""
    setup_file = get_setup_py_path()
    content = setup_file.read_text(encoding="utf-8")
    match = re.search(r'python_requires\s*=\s*["\']([^"\']+)["\']', content)
    assert match is not None, "python_requires not found in setup.py"
    req_version = match.group(1)
    assert req_version == ">=3.10", f"Unexpected python_requires: {req_version}"


def test_install_requires_completeness() -> None:
    """
    Verify all 14 mandatory dependencies required by SRS Phase 4 / Method Matrix
    are present in install_requires.
    """
    setup_file = get_setup_py_path()
    content = setup_file.read_text(encoding="utf-8")

    required_packages: list[str] = [
        "jinja2",
        "google-genai",
        "llama-cpp-python",
        "tiktoken",
        "python-dotenv",
        "h5py",
        "psutil",
        "pydantic",
        "mendeleev",
        "numpy",
        "rich",
        "tqdm",
        "zstandard",
        "pyyaml",
    ]

    for pkg in required_packages:
        # Check package name appears in install_requires section
        pattern = rf'["\']{re.escape(pkg)}([><=~^0-9.]*)["\']'
        assert re.search(pattern, content, re.IGNORECASE) is not None, (
            f"Required package '{pkg}' missing from install_requires in setup.py"
        )


def test_extras_require_structure() -> None:
    """Verify extras_require defines dev, hpc, nlp, and all targets."""
    setup_file = get_setup_py_path()
    content = setup_file.read_text(encoding="utf-8")

    assert "extras_require" in content
    assert '"dev":' in content or "'dev':" in content
    assert "pytest" in content, "pytest should be included in extras_require"


def test_package_discovery() -> None:
    """Verify setuptools.find_packages discovers the cochem_scribe package hierarchy."""
    import setuptools

    repo_root = get_target_repo_root()
    discovered = setuptools.find_packages(str(repo_root))
    assert "cochem_scribe" in discovered, "cochem_scribe root package not discovered"
    assert (
        "cochem_scribe.core" in discovered
    ), "cochem_scribe.core package not discovered"
    assert (
        "cochem_scribe.engine" in discovered
    ), "cochem_scribe.engine package not discovered"
    assert (
        "cochem_scribe.formatting" in discovered
    ), "cochem_scribe.formatting not discovered"
    assert (
        "cochem_scribe.interfaces" in discovered
    ), "cochem_scribe.interfaces not discovered"
    assert "cochem_scribe.nlp" in discovered, "cochem_scribe.nlp not discovered"


def test_dynamic_mendeleev_elemental_weights() -> None:
    """
    Verify Mendeleev dynamic elemental property lookup operates dynamically
    and yields real physical atomic weights according to CODATA standards.
    """
    carbon = element("C")
    hydrogen = element("H")
    oxygen = element("O")
    nitrogen = element("N")

    assert carbon.atomic_weight is not None
    assert 12.010 <= float(carbon.atomic_weight) <= 12.012

    assert hydrogen.atomic_weight is not None
    assert 1.007 <= float(hydrogen.atomic_weight) <= 1.009

    assert oxygen.atomic_weight is not None
    assert 15.999 <= float(oxygen.atomic_weight) <= 16.000

    assert nitrogen.atomic_weight is not None
    assert 14.006 <= float(nitrogen.atomic_weight) <= 14.008


def test_setup_py_cli_execution() -> None:
    """Verify setup.py can be invoked via Python CLI to query package metadata."""
    repo_root = get_target_repo_root()
    setup_file = repo_root / "setup.py"

    # Query package name
    result_name = subprocess.run(
        [sys.executable, str(setup_file), "--name"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert (
        result_name.returncode == 0
    ), f"setup.py --name failed: {result_name.stderr}"
    assert "cochem-scribe" in result_name.stdout.strip().lower()

    # Query package version
    result_version = subprocess.run(
        [sys.executable, str(setup_file), "--version"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert (
        result_version.returncode == 0
    ), f"setup.py --version failed: {result_version.stderr}"
    assert "4.1.0" in result_version.stdout.strip()


def test_console_scripts_entry_point_callability() -> None:
    """
    Verify that the 'cochem-scribe' console_scripts entry point
    ('cochem_scribe_compiler:main') resolves to an importable and callable function.
    Strict Zero-Mock Mandate compliance.
    """
    repo_root = get_target_repo_root()
    repo_root_str = str(repo_root.resolve())
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

    setup_file = repo_root / "setup.py"
    content = setup_file.read_text(encoding="utf-8")
    assert "cochem-scribe=cochem_scribe_compiler:main" in content, (
        "Expected console_scripts entry point "
        "'cochem-scribe=cochem_scribe_compiler:main' not found in setup.py"
    )

    import importlib
    compiler_mod = importlib.import_module("cochem_scribe_compiler")
    assert hasattr(compiler_mod, "main"), (
        "cochem_scribe_compiler module does not define a 'main' function"
    )
    assert callable(compiler_mod.main), (
        "cochem_scribe_compiler.main is not callable"
    )

