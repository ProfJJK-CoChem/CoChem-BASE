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
