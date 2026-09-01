#!/usr/bin/env python3
"""
Unit test suite for CoChem-BENCH Verifier & Compliance Engine.
Tests multi-reference diagnostics, Rule 7 provenance discipline, frozen-core bias audits,
dispersion corrections, geometry thresholds, and OpenMPI SHM checksums.

Authoritative Reference:
- Method Matrix v4 (Section 4.4, 4.7, 4.8, 8A.4, 8B.3, 9A.1, 9A.2, 12.5 Rule 4, 12.5 Rule 7, 21.2)
"""
import hashlib
import json
from pathlib import Path
import pytest

from cochem_bench.verifier import (
    ProvenancePayload,
    verify_multireference_gate,
    audit_frozen_core_bias,
    check_spin_contamination,
    check_dispersion_correction,
    verify_geometry_convergence_thresholds,
    verify_frozen_monomer_flag,
    verify_basis_bsse_compliance,
    validate_standing_rule_7,
    get_active_orca_version,
    verify_openmpi_shm_checksum,
    export_provenance_json,
)


def test_verify_multireference_gate_closed_shell():
    orca_out = """
-------------------------------------------------------------------------------
                           ORCA COUPLED CLUSTER RESULTS
-------------------------------------------------------------------------------
  T1 diagnostic                             ...    0.014520
  D1 diagnostic                             ...    0.038200
  E(CORR)                                   ...   -0.214589201
"""
    res = verify_multireference_gate(orca_out, spin_multiplicity=1)
    assert res["passed"] is True
    assert res["t1"] == 0.014520
    assert res["d1"] == 0.038200
    assert res["status"] == "PASSED"


def test_verify_multireference_gate_closed_shell_warning():
    orca_out = """
  T1 diagnostic ... 0.028000
  D1 diagnostic ... 0.058000
"""
    res = verify_multireference_gate(orca_out, spin_multiplicity=1)
    assert res["passed"] is False
    assert res["status"] == "MULTIREFERENCE_WARNING"


def test_verify_multireference_gate_open_shell():
    orca_out = """
  T1 diagnostic ... 0.035000
  D1 diagnostic ... 0.062000
"""
    res = verify_multireference_gate(orca_out, spin_multiplicity=2)
    assert res["passed"] is True
    assert res["status"] == "PASSED"


def test_verify_multireference_gate_missing_t1():
    with pytest.raises(ValueError, match="T1 diagnostic not found"):
        verify_multireference_gate("ORCA output without any CC diagnostics")


def test_audit_frozen_core_bias_mandate():
    res_fail = audit_frozen_core_bias(0.3, has_core_valence=False)
    assert res_fail["passed"] is False
    assert res_fail["status"] == "FROZEN_CORE_BIAS_WARNING"
    assert res_fail["frozen_core_mean_bias_pct"] == -0.81

    res_pass = audit_frozen_core_bias(0.3, has_core_valence=True)
    assert res_pass["passed"] is True
    assert res_pass["status"] == "PASSED"

    res_relaxed = audit_frozen_core_bias(1.2, has_core_valence=False)
    assert res_relaxed["passed"] is True


def test_check_spin_contamination():
    check_spin_contamination(0.75, 0.77)

    with pytest.raises(ValueError, match="Spin contamination exceeds 10%"):
        check_spin_contamination(0.75, 0.88)

    with pytest.raises(ValueError, match="broken-symmetry spin contamination"):
        check_spin_contamination(0.0, 0.15)


def test_check_dispersion_correction():
    check_dispersion_correction("wB97M-V", is_weak_complex=True)
    check_dispersion_correction("wB97X-V", is_weak_complex=True)
    check_dispersion_correction("r2SCAN-3c", is_weak_complex=True)
    check_dispersion_correction("B3LYP-D3BJ", is_weak_complex=True)
    check_dispersion_correction("PBE0-D4", is_weak_complex=True)
    check_dispersion_correction("M06-2X", is_weak_complex=True)

    with pytest.raises(ValueError, match="Dispersion correction"):
        check_dispersion_correction("B3LYP", is_weak_complex=True)

    with pytest.raises(ValueError, match="Dispersion correction"):
        check_dispersion_correction("PBE", is_weak_complex=True)


def test_verify_geometry_convergence_thresholds():
    tight_params = {
        "TolE": 1e-8,
        "TolRMSG": 2e-6,
        "TolMaxG": 8e-6,
        "TolRMSD": 4e-5,
        "TolMaxD": 9e-5,
        "InHess": "XTB2",
    }
    res_pass = verify_geometry_convergence_thresholds(tight_params, claimed_accuracy_pct=0.4)
    assert res_pass["passed"] is True

    loose_params = {
        "TolE": 1e-5,
        "TolRMSG": 1e-4,
        "TolMaxG": 1e-3,
        "TolRMSD": 1e-3,
        "TolMaxD": 1e-2,
        "InHess": "Calc_Hess true",
    }
    res_fail = verify_geometry_convergence_thresholds(loose_params, claimed_accuracy_pct=0.4)
    assert res_fail["passed"] is False
    assert len(res_fail["issues"]) >= 2


def test_verify_frozen_monomer_flag():
    assert verify_frozen_monomer_flag("relaxed")["status"] == "PASSED"
    assert verify_frozen_monomer_flag("frozen-inc")["status"] == "PASSED"
    assert verify_frozen_monomer_flag("frozen-iso", is_h_bonded=False)["status"] == "PASSED"

    warn_res = verify_frozen_monomer_flag("frozen-iso", is_h_bonded=True)
    assert warn_res["status"] == "FLAGGED_WARNING"
    assert "deformation" in warn_res["warning"]

    assert verify_frozen_monomer_flag("unknown-flag")["status"] == "INVALID_FLAG"


def test_verify_basis_bsse_compliance():
    res_overclaim = verify_basis_bsse_compliance("def2-TZVP", has_counterpoise=False, claimed_error_pct=0.5)
    assert res_overclaim["passed"] is False
    assert res_overclaim["status"] == "BSSE_ACCURACY_OVERCLAIM"

    res_cp = verify_basis_bsse_compliance("def2-TZVP", has_counterpoise=True, claimed_error_pct=0.5)
    assert res_cp["passed"] is True

    res_aug = verify_basis_bsse_compliance("aug-cc-pVTZ", has_counterpoise=False, claimed_error_pct=0.5)
    assert res_aug["passed"] is True


def test_validate_standing_rule_7():
    compliant_payload = {
        "provenance_tags": {"B_e": "[M]", "A_0": "[D]"},
        "accuracy_claims": [
            {"metric_key": "B_e", "name": "Equilibrium B_e", "has_measured_anchor": True},
            {"metric_key": "A_0", "name": "Ground state A_0", "has_measured_anchor": True},
        ]
    }
    assert validate_standing_rule_7(compliant_payload)["rule_7_compliant"] is True

    violating_payload = {
        "provenance_tags": {"B_e": "[D]"},
        "accuracy_claims": [
            {"metric_key": "B_e", "name": "Derived Constant", "has_measured_anchor": False},
        ]
    }
    res_viol = validate_standing_rule_7(violating_payload)
    assert res_viol["rule_7_compliant"] is False
    assert len(res_viol["violations"]) == 1


def test_get_active_orca_version():
    v = get_active_orca_version()
    assert isinstance(v, str)
    assert "ORCA" in v


def test_verify_openmpi_shm_checksum():
    tensor_bytes = b"COCHEM_MPI_SHM_TENSOR_BUFFER_DENSITY_MATRIX"
    expected_sha = hashlib.sha256(tensor_bytes).hexdigest()
    res = verify_openmpi_shm_checksum(tensor_bytes, expected_sha)
    assert res["passed"] is True
    assert res["bytes_checked"] == len(tensor_bytes)

    res_bad = verify_openmpi_shm_checksum(tensor_bytes, "0000000000000000000000000000000000000000000000000000000000000000")
    assert res_bad["passed"] is False


def test_export_provenance_json(tmp_path: Path):
    out_file = tmp_path / "test_prov.json"
    res = export_provenance_json(
        input_dict={"seed": "H2O_dimer.xyz"},
        results_dict={"B_e": 5824.12},
        provenance_tags={"B_e": "[M]"},
        output_path=out_file,
        accuracy_claims=[
            {"metric_key": "B_e", "claimed_error_pct": 0.2, "has_core_valence": True, "has_measured_anchor": True}
        ]
    )
    assert out_file.exists()
    saved = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved["orca_version"] == res["orca_version"]
    assert saved["rule_7_compliance"]["rule_7_compliant"] is True
    assert len(saved["frozen_core_audit"]) == 1
    assert saved["frozen_core_audit"][0]["passed"] is True
