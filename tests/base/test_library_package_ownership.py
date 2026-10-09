"""Actual source and wheel contracts for BASE's independent library ownership."""
from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TORQ_LEGACY_MEMBERS = {
    "Libraries/__init__.py",
    "Libraries/cochem_torq_c2_cutoff.py",
    "Libraries/cochem_torq_committee_ensemble.py",
    "Libraries/cochem_torq_dvr.py",
}


def run_source_probe(code: str) -> None:
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        environment.pop(key, None)
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code, str(ROOT)],
        capture_output=True, text=True, env=environment, timeout=60, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture(scope="module")
def real_base_wheel(tmp_path_factory):
    """Build a genuine wheel from a disposable source copy, leaving ROOT intact."""
    folder = tmp_path_factory.mktemp("base-library-wheel")
    source = folder / "source"
    # A source archive has no Git metadata, and a Windows worktree's Git pointer
    # cannot be interpreted by Linux Git. Neither is needed to build the package.
    shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", ".pytest_cache", ".ruff_cache", "*.egg-info",
        "build", "dist", ".venv", ".conda",
    ))
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-m", "build", "--no-isolation", "--wheel",
         "--outdir", str(folder / "dist"), str(source)],
        capture_output=True, text=True, timeout=180, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wheel = next((folder / "dist").glob("cochem_base-*.whl"))
    # A real negative build proves the hook is necessary. Remove only its
    # declaration; leave the source initializer, packages and numeric code intact.
    control = folder / "control-source"
    shutil.copytree(source, control, ignore=shutil.ignore_patterns("build", "*.egg-info"))
    configuration = control / "pyproject.toml"
    text = configuration.read_text()
    declaration = '[tool.setuptools.cmdclass]\nbuild_py = "scripts.build_namespace.BaseNamespaceBuildPy"\n\n'
    assert declaration in text
    configuration.write_text(text.replace(declaration, "", 1))
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-m", "build", "--no-isolation", "--wheel",
         "--outdir", str(folder / "control-dist"), str(control)],
        capture_output=True, text=True, timeout=180, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with zipfile.ZipFile(next((folder / "control-dist").glob("cochem_base-*.whl"))) as archive:
        assert archive.read("Libraries/__init__.py") == (ROOT / "Libraries/__init__.py").read_bytes()
    return wheel


def test_source_base_namespace_imports_pes_without_optional_torq_bootstrap():
    run_source_probe("""
import pathlib,sys
root=pathlib.Path(sys.argv[1]); sys.path.insert(0,str(root))
import Libraries
from Libraries.cochem_base_pes_store import PESStore
assert pathlib.Path(Libraries.__file__).resolve()==root/'Libraries/__init__.py'
assert PESStore.__module__=='Libraries.cochem_base_pes_store'
assert not any(name.startswith('Libraries.cochem_torq_') for name in sys.modules)
""")


def test_real_base_wheel_keeps_unique_pes_without_torq_ownership(real_base_wheel):
    with zipfile.ZipFile(real_base_wheel) as archive:
        names = set(archive.namelist())
        assert names.isdisjoint(TORQ_LEGACY_MEMBERS)
        assert {n for n in names if n.startswith("Libraries/")} == {"Libraries/cochem_base_pes_store.py"}
        assert archive.read("Libraries/cochem_base_pes_store.py") == (ROOT / "Libraries/cochem_base_pes_store.py").read_bytes()


def test_real_base_wheel_contains_independent_canonical_numeric_helpers(real_base_wheel):
    with zipfile.ZipFile(real_base_wheel) as archive:
        for module in ("__init__", "contracts", "c2_cutoff", "committee_ensemble", "dvr"):
            relative = f"cochem_base/numerics/{module}.py"
            assert archive.read(relative) == (ROOT / "src" / relative).read_bytes()


def test_canonical_numeric_formula_bodies_survive_namespace_migration():
    for module in ("c2_cutoff", "committee_ensemble", "dvr"):
        legacy = ast.parse((ROOT / "Libraries" / f"cochem_torq_{module}.py").read_text())
        canonical = ast.parse((ROOT / "src/cochem_base/numerics" / f"{module}.py").read_text())
        def numeric_nodes(tree):
            # Whitespace normalization of docstrings is not a formula change.
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.body:
                    first = node.body[0]
                    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                        node.body = node.body[1:]
            return {n.name: ast.dump(n) for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        assert numeric_nodes(canonical) == numeric_nodes(legacy)


def test_canonical_contracts_preserve_author_cutoff_and_error_payloads():
    run_source_probe("""
import pathlib,sys
root=pathlib.Path(sys.argv[1]); sys.path.insert(0,str(root/'src'))
from pydantic import ValidationError
from cochem_base.numerics.contracts import C2SmoothCutoffConfig,CutoffContinuityError,EnsembleConsensusError
config=C2SmoothCutoffConfig()
assert config.cutoff_radius_rc==5.0 and config.polynomial_degree==5
for invalid in [{'cutoff_radius_rc':1.0},{'polynomial_degree':4},{'invented':1}]:
 try: C2SmoothCutoffConfig(**invalid)
 except ValidationError: continue
 raise AssertionError(invalid)
for cls,code,component in [(CutoffContinuityError,'TORQ_CUTOFF_ERR','c2_cutoff'),(EnsembleConsensusError,'TORQ_ENSEMBLE_ERR','committee_ensemble')]:
 error=cls('rejected',diagnostics={'observed':1})
 assert error.message=='rejected' and str(error)=='rejected'
 assert error.error_code==code and error.component==component and error.diagnostics=={'observed':1}
""")
