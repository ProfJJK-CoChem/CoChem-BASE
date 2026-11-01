"""Real data admission controls; no engines, network, mocks or provider claims."""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from cochem_base.interfaces.course_access import CourseAccessError
from cochem_base.interfaces.student_colab import (
    MonthlyStudentCuQuotaManager,
    _canonical_signing_bytes,
    package_student_colab_request,
    verify_student_colab_request_signature,
)

H2 = "2\nhydrogen\nH 0 0 0\nH 0 0 0.74\n"
KEY = "local-colab-validation-test-key"
ENV = {"COCHEM_COLAB_ACCESS_SECRET": "COLAB_OFFLOAD_DISPATCH_TOKEN",
       "COLAB_OFFLOAD_DISPATCH_TOKEN": KEY}


def inputs(**overrides):
    data = dict(student_id="student-01", job_id="hydrogen-sp", engine="PYSCF",
                method="HF", geometry_xyz=H2, basis_set="sto-3g",
                repository="student-01/CoChem-hydrogen", estimated_cu=2.5,
                charge=0, multiplicity=1, is_opt=False, is_freq=False)
    data.update(overrides)
    return data


def test_plain_element_v1_payload_and_signing_bytes_are_unchanged():
    actual = package_student_colab_request(**inputs(), environ=ENV)
    expected = {
        "schema": "cochem.student-colab-request.v1", "job_id": "hydrogen-sp",
        "student_id": "student-01", "repository": "student-01/CoChem-hydrogen",
        "engine": "PYSCF", "method": "HF", "basis_set": "sto-3g",
        "charge": 0, "multiplicity": 1, "is_opt": False, "is_freq": False,
        "estimated_cu": 2.5, "geometry_xyz": H2.strip(),
        "geometry_sha256": hashlib.sha256(H2.strip().encode()).hexdigest(),
        "dispatch_token_fingerprint": hashlib.sha256(KEY.encode()).hexdigest()[:16],
        "binding_variable": "COCHEM_COLAB_ACCESS_SECRET",
    }
    legacy_bytes = json.dumps(expected, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert _canonical_signing_bytes(actual) == legacy_bytes
    assert actual == {**expected, "hmac_sha256": hmac.new(KEY.encode(), legacy_bytes, hashlib.sha256).hexdigest(), "quota": None}
    assert verify_student_colab_request_signature(actual, KEY)
    assert not verify_student_colab_request_signature(actual, "different-local-key")


@pytest.mark.parametrize("geometry,charge,multiplicity", [
    ("1\nhydrogen atom\nH 0 0 0", 0, 2),
    (H2, 1, 2),
    (H2, 0, 3),  # Permitted spin state; no ground-state/minimum inference.
    ("2\nsalt\nNa 0 0 0\nCl 0 0 2.3", 0, 1),
])
def test_valid_electronic_states_keep_their_explicit_coordinates(geometry, charge, multiplicity):
    result = package_student_colab_request(**inputs(geometry_xyz=geometry, charge=charge,
                                                  multiplicity=multiplicity), environ=ENV)
    assert result["geometry_xyz"] == geometry.strip()
    assert result["geometry_sha256"] == hashlib.sha256(geometry.strip().encode()).hexdigest()
    assert result["charge"] == charge and type(result["charge"]) is int
    assert result["multiplicity"] == multiplicity and type(result["multiplicity"]) is int


# Every malformed request is exercised with absent and valid credentials against
# the real ledger. Validation must precede both token resolution and any write.
INVALID = [
    ({"charge": value}, "charge must") for value in (True, False, "0", 0.0, None)
] + [
    ({"multiplicity": value}, "multiplicity must") for value in (True, False, "1", 1.0, None, 0, -1)
] + [
    ({name: value}, "flags must") for name in ("is_opt", "is_freq") for value in (0, 1, "false", None)
] + [
    ({"estimated_cu": value}, "Estimated CU")
    for value in (True, "2.5", None, -0.01, float("nan"), float("inf"), -float("inf"), 10**1000)
] + [
    ({name: value}, "single-line")
    for name in ("method", "basis_set")
    for value in ("", " ", 1, "HF\n! injected", "HF\rkeyword", "HF\x00keyword", "HF\tkeyword", "HF\x7f", "\x85HF", "HF\x85", "HF\x9f", "\u2028HF", "HF\u2029")
] + [
    ({"method": None}, "single-line"),
    ({"charge": 2}, "incompatible"),  # No electrons.
    ({"charge": 3}, "incompatible"),  # Negative electron count.
    ({"multiplicity": 2}, "incompatible"),  # Wrong parity.
    ({"multiplicity": 5}, "incompatible"),  # More unpaired electrons than electrons.
    ({"student_id": None}, "must be strings"),
    ({"job_id": 7}, "must be strings"),
    ({"engine": None}, "engine must"),
    ({"repository": True}, "Repository must"),
] + [
    ({"geometry_xyz": value}, "XYZ geometry") for value in (None, b"H 0 0 0", "", "  ")
] + [
    ({"geometry_xyz": value}, "Invalid Colab XYZ") for value in (
        "H 0 0 0", "0\nempty", "-1\nnegative\nH 0 0 0",
        "2\nmissing\nH 0 0 0", "1\nextra\nH 0 0 0\nH 0 0 1",
        "1\nmissing coordinate\nH 0 0", "1\nextra coordinate\nH 0 0 0 1",
        "1\nnonfinite\nH nan 0 0", "1\nnonfinite\nH inf 0 0",
        "1\nnonfinite\nH -inf 0 0", "1\noverflow\nH 1e999 0 0",
        "1\ntext coordinate\nH nope 0 0",
        H2 + "2\nsecond frame\nH 0 0 0\nH 0 0 1",
    )
] + [
    ({"geometry_xyz": f"1\nunsupported label\n{label} 0 0 0"}, "canonical plain element")
    for label in ("Qq", "Gh", "X", "D", "T", "13C", "C-13", "h")
]


@pytest.mark.parametrize("changes,message", INVALID)
def test_malformed_input_precedes_token_and_preserves_real_quota_ledger(tmp_path, changes, message):
    ledger = tmp_path / "advisory-cu.json"
    quota = MonthlyStudentCuQuotaManager(ledger, allow_live_gh=False)
    quota.check_student_allowance("student-01", 0.0, month_key="2026-11", n_students_override=20)
    before = ledger.read_bytes()
    for environment in ({}, ENV):
        with pytest.raises(CourseAccessError, match=message):
            package_student_colab_request(**inputs(**changes), environ=environment, quota_manager=quota)
        assert ledger.read_bytes() == before
        assert list(tmp_path.iterdir()) == [ledger]


def test_valid_local_accounting_is_advisory_and_canonical_optional_values_remain():
    result = package_student_colab_request(**inputs(method="  r2SCAN-3c  ", basis_set=None,
                                                   estimated_cu=0), environ=ENV)
    assert result["method"] == "r2SCAN-3c"
    assert result["basis_set"] is None
    assert result["estimated_cu"] == 0.0
    assert result["quota"] is None
    assert "gpu" not in result and "execution_performed" not in result


def test_printable_greek_method_is_not_an_engine_whitelist():
    result = package_student_colab_request(**inputs(method="ωB97X-D", basis_set="def2-TZVP"), environ=ENV)
    assert result["method"] == "ωB97X-D"
    assert result["basis_set"] == "def2-TZVP"
    assert verify_student_colab_request_signature(result, KEY)


# Real standalone CLI controls. The parent can have scientific dependencies;
# these children use one genuinely fresh venv with no pip or third-party stack.
STDLIB_CLI_CHILD = r'''
import importlib.util
import json
import os
import runpy
import site
import sys
from pathlib import Path
from ci_tools import source_quarantine

root, prefix, report = map(Path, sys.argv[1:4])
arguments = json.loads(sys.argv[4])
state = source_quarantine.activate_from_environment()
if os.environ.get("COCHEM_SOURCE_QUARANTINE_ROOT"):
    assert state is not None and state["copied"] == root
assert Path(sys.prefix) == prefix
assert sys.prefix != sys.base_prefix
assert site.ENABLE_USER_SITE is False
assert all(importlib.util.find_spec(name) is None for name in ("pip", "numpy", "pydantic"))
script = root / "scripts/submit_colab_calculation.py"
blocked = []
def no_execution_or_network(event, args):
    if event in {"subprocess.Popen", "os.system", "socket.connect", "socket.getaddrinfo"}:
        blocked.append(event)
        raise AssertionError("Standalone admission must not execute processes or contact a service")
sys.addaudithook(no_execution_or_network)
loaded = runpy.run_path(str(script), run_name="colab_cli_metadata_control")
contract = loaded["contract"]
course = contract._source_local_contract("course_access")
assert loaded["CourseAccessError"] is contract.CourseAccessError is course.CourseAccessError
assert loaded["GitHubAPI"] is contract.GitHubAPI is course.GitHubAPI
assert loaded["repository_name"] is contract.repository_name is course.repository_name
assert contract._source_local_contract("course_access") is course
sys.argv = [str(script), *arguments]
try:
    runpy.run_path(str(script), run_name="__main__")
finally:
    expected = {
        name: root / "src/cochem_base/interfaces" / (name + ".py")
        for name in ("student_colab", "course_access", "student_request", "student_research")
    }
    observed = {}
    for name, path in expected.items():
        matches = [module for key, module in sys.modules.items()
                   if key.startswith("_cochem_colab_source_")
                   and Path(getattr(module, "__file__", "")).resolve() == path]
        assert len(matches) == 1
        observed[name] = str(Path(matches[0].__file__).resolve())
    assert contract is loaded["contract"]
    assert "cochem_base.interfaces" not in sys.modules
    assert all(name not in sys.modules for name in ("numpy", "pydantic", "pip"))
    assert not blocked
    report.write_text(json.dumps({
        "prefix": sys.prefix, "base_prefix": sys.base_prefix,
        "executable": sys.executable, "source_files": observed,
        "source_quarantine_active": state is not None,
        "blocked_execution_or_network": blocked,
        "one_error_and_api_identity": True,
    }, sort_keys=True), encoding="utf-8")
'''


@pytest.fixture(scope="module")
def stdlib_colab_cli(tmp_path_factory):
    import os
    import subprocess
    import sys
    from pathlib import Path
    from ci_tools.source_quarantine import source_child_environment, source_paths

    root = Path(__file__).resolve().parents[2]
    work = tmp_path_factory.mktemp("colab-stdlib-cli")
    prefix = work / "venv"
    environment = dict(os.environ)
    for name in ("GH_TOKEN", "GITHUB_TOKEN", "COCHEM_COLAB_ACCESS_SECRET",
                 "COLAB_OFFLOAD_DISPATCH_TOKEN"):
        environment.pop(name, None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONPATH"] = os.pathsep.join(source_paths(root))
    environment = source_child_environment(environment, selected_source=root)
    subprocess.run([sys.executable, "-B", "-m", "venv", "--without-pip", str(prefix)],
                   env=environment, capture_output=True, text=True, check=True, timeout=45)
    python = prefix / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    assert python.is_file()
    assert "include-system-site-packages = false" in (prefix / "pyvenv.cfg").read_text()
    return root, work, prefix, python, environment


@pytest.mark.parametrize("case", ["help", "invalid_physical_input", "missing_dispatch_credential"])
def test_standalone_colab_cli_in_fresh_stdlib_environment(stdlib_colab_cli, case):
    import os
    import subprocess

    root, work, prefix, python, environment = stdlib_colab_cli
    arguments = ["--help"] if case == "help" else [
        "--student-id", "student-01", "--job-id", "hydrogen-sp", "--engine", "PYSCF",
        "--method", "HF", "--basis-set", "sto-3g", "--xyz", H2,
        "--charge", "0", "--multiplicity", "2" if case == "invalid_physical_input" else "1",
        "--no-opt", "--no-freq", "--repository", "student-01/CoChem-hydrogen",
    ]
    report = work / (case + ".json")
    result = subprocess.run(
        [str(python), "-B", "-c", STDLIB_CLI_CHILD, str(root), str(prefix), str(report),
         json.dumps(arguments)], env=environment, cwd=work, capture_output=True,
        text=True, timeout=20, check=False,
    )
    actual = json.loads(report.read_text())
    assert actual["prefix"] == str(prefix)
    assert actual["executable"] == str(python)
    assert actual["one_error_and_api_identity"]
    assert not actual["blocked_execution_or_network"]
    if os.environ.get("COCHEM_SOURCE_QUARANTINE_ROOT"):
        assert actual["source_quarantine_active"]
    assert set(actual["source_files"]) == {"student_colab", "course_access", "student_request", "student_research"}
    if case == "help":
        assert result.returncode == 0, result.stderr
        assert "--xyz-file" in result.stdout and "--multiplicity" in result.stdout
        assert not result.stderr
    else:
        assert result.returncode != 0
        assert not result.stdout
        assert "ModuleNotFoundError" not in result.stderr
        if case == "invalid_physical_input":
            assert "Molecular charge and spin multiplicity are incompatible" in result.stderr
            assert "dispatch token is not configured" not in result.stderr
        else:
            assert "Google Colab dispatch token is not configured" in result.stderr
            assert "Confirm project enrollment in Connect using an instructor invitation" in result.stderr
            assert "GH_TOKEN or GITHUB_TOKEN is required" not in result.stderr
