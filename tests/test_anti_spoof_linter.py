"""Physical unit tests for CoChem Anti-Spoofing Linter (ci_tools/anti_spoof_linter.py).

Zero-Mock Mandate Compliance:
- Real test files created in tmp_path.
- Tests verify AST inspection, banned imports, and stubs.
"""

from __future__ import annotations

from pathlib import Path

from ci_tools.anti_spoof_linter import (
    BANNED_MOCK_MODULES,
    EXCLUDED_DIRS,
    check_file,
    load_amnesty,
    run_linter,
)


def test_excluded_dirs() -> None:
    assert ".git" in EXCLUDED_DIRS
    assert "__pycache__" in EXCLUDED_DIRS
    assert ".pytest_cache" in EXCLUDED_DIRS


def test_runtime_concurrency_imports_are_not_engine_substitution(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_import.py"
    bad_script.write_text("import parsl\nimport dask\n", encoding="utf-8")
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert violations == []


def test_detect_mock_modules(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_mock.py"
    bad_script.write_text("import mock\n", encoding="utf-8")
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any("mock" in v.symbol for v in violations)


def test_detect_pass_stub(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_stub.py"
    bad_script.write_text("def solve():\n    pass\n", encoding="utf-8")
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any("pass" in v.message.lower() for v in violations)


def test_detect_not_implemented_error(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_raise.py"
    bad_script.write_text(
        "def compute():\n    raise NotImplementedError('Not done')\n",
        encoding="utf-8",
    )
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any(v.category == "NOT_IMPLEMENTED_ERROR" for v in violations)


def test_detect_hardcoded_successful_physical_result(tmp_path: Path) -> None:
    bad_script = tmp_path / "bad_ident.py"
    bad_script.write_text("def run():\n    return {'energy': 0.0, 'converged': True}\n", encoding="utf-8")
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any(v.category == "SYNTHETIC_DATA" for v in violations)


def test_clean_script_passes(tmp_path: Path) -> None:
    clean_script = tmp_path / "clean_module.py"
    clean_script.write_text(
        "def compute_energy(x: float) -> float:\n    return x * 2.5\n",
        encoding="utf-8",
    )
    violations = check_file(clean_script, tmp_path, amnesty_set=set())
    assert len(violations) == 0


def test_run_linter_directory(tmp_path: Path) -> None:
    sub_dir = tmp_path / "clean_dir"
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / "clean_mod.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )
    exit_code, violations = run_linter(
        targets=[sub_dir], repo_root=sub_dir, strict_mode=True
    )
    assert exit_code == 0
    assert len(violations) == 0


def test_amnesty_bypass(tmp_path: Path) -> None:
    conc_script = tmp_path / "conc_worker.py"
    conc_script.write_text("import unittest.mock\n", encoding="utf-8")
    # Legacy amnesty entries cannot waive substitution of executing interfaces.
    v_un = check_file(conc_script, tmp_path, amnesty_set=set())
    assert len(v_un) > 0
    # The same violation must remain visible with an old amnesty entry.
    v_am = check_file(conc_script, tmp_path, amnesty_set={"conc_worker.py"})
    assert v_am == v_un


def test_detect_pytest_alias_skip(tmp_path: Path) -> None:
    bad_script = tmp_path / "test_alias_skip.py"
    bad_script.write_text(
        "import pytest as pt\n"
        "def test_one():\n"
        "    pt.skip('skip reason')\n"
        "@pt.mark.skip\n"
        "def test_two():\n"
        "    pass\n",
        encoding="utf-8",
    )
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any(v.category == "PYTEST_SKIP" and "pytest.skip" in v.symbol for v in violations)
    assert any(v.category == "PYTEST_SKIP" and "pytest.mark.skip" in v.symbol for v in violations)


def test_detect_pytest_skipif_and_xfail(tmp_path: Path) -> None:
    bad_script = tmp_path / "test_skipif_xfail.py"
    bad_script.write_text(
        "import pytest\n"
        "from pytest import skipif, xfail\n"
        "@pytest.mark.skipif(True, reason='cond')\n"
        "def test_one():\n"
        "    pass\n"
        "@pytest.mark.xfail\n"
        "def test_two():\n"
        "    pass\n",
        encoding="utf-8",
    )
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any("skipif" in v.symbol for v in violations)
    assert any("xfail" in v.symbol for v in violations)


def test_detect_unittest_skips(tmp_path: Path) -> None:
    bad_script = tmp_path / "test_unittest_skips.py"
    bad_script.write_text(
        "import unittest\n"
        "@unittest.skip('reason')\n"
        "def test_one():\n"
        "    pass\n"
        "class TestSuite(unittest.TestCase):\n"
        "    def test_two(self):\n"
        "        self.skipTest('skip')\n",
        encoding="utf-8",
    )
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any("unittest.skip" in v.symbol for v in violations)
    assert any("skipTest" in v.symbol for v in violations)


def test_detect_monkeypatch_and_setattr_bypass(tmp_path: Path) -> None:
    bad_script = tmp_path / "test_monkeypatch_bypass.py"
    bad_script.write_text(
        "import os\n"
        "def test_mp(mp):\n"
        "    mp.setattr('os.environ', {})\n"
        "def test_setattr_foreign():\n"
        "    setattr(os.path, 'exists', lambda x: True)\n",
        encoding="utf-8",
    )
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any("mp.setattr" in v.symbol for v in violations)
    assert any("setattr" in v.symbol for v in violations)


def test_charge_and_spin_inputs_do_not_claim_observed_results(tmp_path: Path) -> None:
    bad_script = tmp_path / "dummy_dicts.py"
    bad_script.write_text(
        "d1 = {'charge': 0, **{'uhf': 1}}\n"
        "d2 = dict(charge=0, uhf=1)\n",
        encoding="utf-8",
    )
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert violations == []


def test_detect_dynamic_obfuscation_exec_eval(tmp_path: Path) -> None:
    bad_script = tmp_path / "obfuscated.py"
    bad_script.write_text(
        "x = eval('1 + 1')\n"
        "exec('y = 2')\n"
        "getattr(sys, 'mock')\n",
        encoding="utf-8",
    )
    violations = check_file(bad_script, tmp_path, amnesty_set=set())
    assert any(v.category == "OBFUSCATION" and v.symbol == "eval" for v in violations)
    assert any(v.category == "OBFUSCATION" and v.symbol == "exec" for v in violations)
    assert any("mock" in v.symbol for v in violations)



def _inspect_source(tmp_path: Path, source: str):
    target = tmp_path / "engine.py"
    target.write_text(source, encoding="utf-8")
    return check_file(target, tmp_path, amnesty_set=set())


def test_generated_physical_evidence_cannot_hide_behind_import_or_assignment_aliases(tmp_path: Path) -> None:
    variants = [
        "import numpy as numerical\na = numerical.zeros(3)\nb = a\nresult = {'forces': b}\n",
        "from numpy import ones as allocate\na = allocate(3)\nresult = dict(forces=a)\n",
        "import numpy as np\nallocate = np.zeros\nresult = {'forces': allocate(3)}\n",
        "from numpy.random import normal as sample\nresult = {'energy': sample()}\n",
        "import numpy as np\na = np.zeros(3)\na += 1.0\nresult = {'forces': a}\n",
    ]
    for source in variants:
        violations = _inspect_source(tmp_path, source)
        assert any(item.category == "SYNTHETIC_DATA" for item in violations), source


def test_work_arrays_require_real_data_before_becoming_result_values(tmp_path: Path) -> None:
    source = (
        "import numpy as np\n"
        "from concurrent.futures import ThreadPoolExecutor\n"
        "def project(coordinates, masses):\n"
        "    inertia = np.zeros((3, 3))\n"
        "    axes = np.eye(3)\n"
        "    for coordinate, mass in zip(coordinates, masses):\n"
        "        inertia += mass * (np.dot(coordinate, coordinate) * axes - np.outer(coordinate, coordinate))\n"
        "    return {'hessian': inertia}\n"
    )
    assert _inspect_source(tmp_path, source) == []


def test_template_redaction_state_paths_and_inherited_behavior_are_not_stubs(tmp_path: Path) -> None:
    source = (
        "from pathlib import Path\n"
        "class ValidationError(SystemExit):\n    pass\n"
        "class Alias(Path):\n    pass\n"
        "def placeholder_values(root):\n    return {'<PRIVATE>': root / 'swarm_state.json'}\n"
        "failure = dict(status='FAILED', energy=None)\n"
    )
    assert _inspect_source(tmp_path, source) == []


def test_hardcoded_audit_verdict_is_rejected_but_state_serialization_is_allowed(tmp_path: Path) -> None:
    violations = _inspect_source(tmp_path, "result = {'audit_verdict': 'PASSED'}\n")
    assert any(item.category == "STATE_MUTATION_BAN" for item in violations)
    assert _inspect_source(tmp_path, "def state(value):\n    return {'audit_verdict': value}\n") == []


def test_missing_convergence_never_defaults_to_success(tmp_path: Path) -> None:
    for method in ("get", "setdefault"):
        violations = _inspect_source(tmp_path, f"def read(data):\n    return data.{method}('converged', True)\n")
        assert any(item.category == "DEFAULT_CONVERGENCE" for item in violations)
    assert _inspect_source(tmp_path, "def read(data):\n    return data.get('converged', False)\n") == []


def test_mock_aliases_and_environment_intercepts_remain_prohibited(tmp_path: Path) -> None:
    source = "from unittest.mock import patch as replace\nwith replace('subprocess.run'): print('intercepted')\n"
    assert any(item.category == "MOCK_USAGE" for item in _inspect_source(tmp_path, source))


def test_empty_audits_and_amnesty_generation_cannot_report_success(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    code, findings = run_linter([empty], tmp_path)
    assert code == 1
    assert any(item.category == "IO_ERROR" for items in findings.values() for item in items)
    target = tmp_path / "worker.py"
    target.write_text("import unittest.mock\n", encoding="utf-8")
    code, findings = run_linter([target], tmp_path, generate_amnesty=True)
    assert code == 1
    assert findings
    code_again, findings_again = run_linter([target], tmp_path)
    assert code_again == 1
    assert findings_again == findings


def test_rng_object_result_is_evidence_not_a_numerical_workspace(tmp_path: Path) -> None:
    source = (
        "import numpy as np\n"
        "rng = np.random.default_rng(5)\n"
        "result = {'forces': rng.normal(size=(3, 3))}\n"
    )
    assert any(item.category == "SYNTHETIC_DATA" for item in _inspect_source(tmp_path, source))


def test_models_and_function_parameters_require_explicit_convergence(tmp_path: Path) -> None:
    for source in (
        "class Result:\n    converged: bool = True\n",
        "class Result:\n    converged: bool = Field(default=True)\n",
        "def result(*, converged=True):\n    return converged\n",
    ):
        assert any(item.category == "DEFAULT_CONVERGENCE" for item in _inspect_source(tmp_path, source))
    assert _inspect_source(tmp_path, "class Result:\n    converged: bool | None = None\n") == []


def test_circular_interface_reexports_are_rejected_for_absolute_and_relative_imports(tmp_path: Path) -> None:
    target = tmp_path / "src" / "example" / "interfaces" / "bridge.py"
    target.parent.mkdir(parents=True)
    sources = (
        "from example.interfaces.bridge import Bridge\n",
        "from .bridge import Bridge\n",
        "from . import bridge\n",
        "import example.interfaces.bridge as implementation\n",
    )
    for source in sources:
        target.write_text(source, encoding="utf-8")
        assert any(item.category == "SELF_IMPORT" for item in check_file(target, tmp_path, set())), source


def test_real_compatibility_reexport_and_package_child_import_are_allowed(tmp_path: Path) -> None:
    package = tmp_path / "src" / "example"
    package.mkdir(parents=True)
    (package / "implementation.py").write_text("def execute(value):\n    return value * 2\n", encoding="utf-8")
    wrapper = package / "bridge.py"
    wrapper.write_text("from example.implementation import execute\n", encoding="utf-8")
    assert check_file(wrapper, tmp_path, set()) == []
    initializer = package / "__init__.py"
    initializer.write_text("from . import implementation\n", encoding="utf-8")
    assert check_file(initializer, tmp_path, set()) == []


def test_explicit_missing_interface_stays_a_strict_conformance_failure(tmp_path: Path) -> None:
    source = "from cochem_base.interfaces import InterfaceUnavailableError\nraise InterfaceUnavailableError('bridge', 'missing implementation')\n"
    assert any(item.category == "MISSING_CAPABILITY" for item in _inspect_source(tmp_path, source))


def test_runtime_self_inspection_is_not_an_empty_reexport(tmp_path: Path) -> None:
    target = tmp_path / "inspector.py"
    target.write_text(
        "def source_path():\n    import inspector\n    return inspector.__file__\n",
        encoding="utf-8",
    )
    assert check_file(target, tmp_path, set()) == []


def test_computed_matrix_accumulation_does_not_masquerade_as_generated_result(tmp_path: Path) -> None:
    source = '''
import numpy as np
def assemble(coordinates):
    hessian = np.zeros((3, 3))
    displacement = coordinates[1] - coordinates[0]
    contribution = np.outer(displacement, displacement)
    hessian[:3, :3] += contribution
    return diagonalize(hessian=hessian)
'''
    assert _inspect_source(tmp_path, source) == []


def test_literal_matrix_writes_do_not_launder_generated_evidence(tmp_path: Path) -> None:
    for operation in ("forces[0] = 1.0", "forces[0] += 1.0"):
        source = "import numpy as np\nforces = np.zeros((3,3))\n" + operation + "\nresult = {'forces': forces}\n"
        assert any(item.category == "SYNTHETIC_DATA" for item in _inspect_source(tmp_path, source))
