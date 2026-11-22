"""Zero-mock tests for CHEM 312 M2-M4 course tools, workflows, FactLedger, and SCRIBE manifest."""
from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

from scripts import (
    fact_ledger,
    fermi_deperturb,
    gvpt2_shard_runner,
    kk_atr_correct,
    kraitchman_rs,
    manage_modules,
    vdw_titration_diff,
)


# ---------------------------------------------------------------------------
# 1. M2: Kramers-Kronig Diamond ATR-FTIR Physical Lorentzian Verification
# ---------------------------------------------------------------------------


def test_kk_atr_lorentzian_fresnel_forward_and_kk_recovery(tmp_path: Path) -> None:
    """Verify genuine Fresnel ATR redshift & KK phase-retrieval blue-shift recovery (< 2.0 cm^-1)."""
    nu = np.linspace(400.0, 4000.0, 3601)
    # Strong neat ester/carbonate C=O damped Lorentzian oscillator: nu0 = 1745 cm^-1, gamma = 20 cm^-1
    n_complex = kk_atr_correct.damped_lorentzian_refractive_index(
        nu,
        oscillators=[(1745.0, 20.0, 82000.0)],
        n_inf=1.40,
    )
    k_true = n_complex.imag
    nu_true_kappa_peak = float(nu[int(np.argmax(k_true))])

    # Exact Fresnel single-bounce diamond ATR forward model (n1 = 2.417, theta = 45 deg, unpolarized)
    fwd = kk_atr_correct.fresnel_atr_forward(n_complex, n_crystal=2.417, angle_deg=45.0)
    # Verify exact 45-degree identity R_p == R_s^2 to machine precision
    assert float(np.max(np.abs(fwd["R_p"] - fwd["R_s"] ** 2))) < 1e-12

    atr_abs = fwd["atr_absorbance"]
    nu_atr_peak = float(nu[int(np.argmax(atr_abs))])
    true_blue_shift = nu_true_kappa_peak - nu_atr_peak
    # Genuine physical ester/carbonate C=O ATR redshift -> +8 to +13 cm^-1 KK blue-shift
    assert 8.0 <= true_blue_shift <= 13.0, f"Unexpected physical shift: {true_blue_shift}"

    # Write ATR absorbance CSV and invoke scripts/kk_atr_correct.py CLI
    in_csv = tmp_path / "ester_co_atr.csv"
    with in_csv.open("w", encoding="utf-8", newline="\n") as fh:
        w = csv.writer(fh)
        w.writerow(["wavenumber_cm1", "atr_absorbance"])
        for x, y in zip(nu, atr_abs):
            w.writerow([f"{x:.4f}", f"{y:.8f}"])

    out_csv = tmp_path / "ester_co_kk.csv"
    out_json = tmp_path / "ester_co_kk.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "kk_atr_correct.py"),
            "--input",
            str(in_csv),
            "--n-crystal",
            "2.417",
            "--angle-deg",
            "45.0",
            "--n-inf",
            "1.40",
            "--output-csv",
            str(out_csv),
            "--output-json",
            str(out_json),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, f"kk_atr_correct.py failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    summary = json.loads(out_json.read_text(encoding="utf-8"))
    assert summary["collaborator_institution"] == "Tennessee Tech University"
    assert summary["input_mode"] == "absorbance"
    assert abs(summary["nu_max_kappa_cm1"] - nu_true_kappa_peak) < 2.0
    assert 8.0 <= summary["delta_nu_cm1"] <= 13.0
    assert summary["peak_table"] and abs(summary["peak_table"][0]["nu_kappa_cm1"] - nu_true_kappa_peak) < 2.0
    assert out_csv.is_file()
    assert summary["output_csv_sha256"] == kk_atr_correct.sha256_file(out_csv)

    # Cross-check reflectance input + Maclaurin KK quadrature + non-45 deg iterative Fresnel
    res_mac = kk_atr_correct.kk_atr_correct(
        nu,
        fwd["R_unpolarized"],
        input_mode="reflectance",
        n_crystal=2.417,
        angle_deg=45.0,
        n_inf=1.40,
        kk_method="maclaurin",
    )
    assert abs(res_mac["nu_max_kappa_cm1"] - nu_true_kappa_peak) < 2.0
    assert abs(res_mac["delta_nu_cm1"] - summary["delta_nu_cm1"]) < 1.0

    fwd_50 = kk_atr_correct.fresnel_atr_forward(n_complex, n_crystal=2.417, angle_deg=50.0)
    res_50 = kk_atr_correct.kk_atr_correct(
        nu,
        fwd_50["R_unpolarized"],
        input_mode="reflectance",
        n_crystal=2.417,
        angle_deg=50.0,
        n_inf=1.40,
    )
    assert abs(res_50["nu_max_kappa_cm1"] - nu_true_kappa_peak) < 2.0
    assert res_50["max_reflectance_residual"] < 1e-4


# ---------------------------------------------------------------------------
# 2. M3: 1:1 Complexation & Boys-Bernardi Counterpoise BSSE Analysis
# ---------------------------------------------------------------------------


def test_vdw_titration_diff_bsse_math_and_pending_experimental(tmp_path: Path) -> None:
    """Verify counterpoise BSSE math, C=O shift, PENDING unmeasured handling, and SHA-256 receipts."""
    mon_json = tmp_path / "monomer_ir.json"
    dim_json = tmp_path / "dimer_ir.json"
    bsse_json = tmp_path / "bsse_counterpoise.json"

    mon_json.write_text(
        json.dumps(
            {
                "ir_modes": [
                    {"wavenumber_cm1": 1150.2, "intensity_km_mol": 45.0},
                    {"wavenumber_cm1": 1785.4, "intensity_km_mol": 320.5},
                    {"wavenumber_cm1": 2980.1, "intensity_km_mol": 18.0},
                ]
            }
        ),
        encoding="utf-8",
    )
    dim_json.write_text(
        json.dumps(
            {
                "ir_modes": [
                    {"wavenumber_cm1": 1154.0, "intensity_km_mol": 48.0},
                    {"wavenumber_cm1": 1768.9, "intensity_km_mol": 355.2},
                    {"wavenumber_cm1": 3585.0, "intensity_km_mol": 140.0},
                ]
            }
        ),
        encoding="utf-8",
    )
    # Realistic wB97X-D3/def2-TZVP Hartree totals (E_A(AB) < E_A(A), E_B(AB) < E_B(B) => BSSE > 0)
    e_ab = -418.732450
    e_a = -342.290100
    e_b = -76.431200
    e_a_dcbs = -342.290950
    e_b_dcbs = -76.431850
    bsse_json.write_text(
        json.dumps(
            {
                "method": "wB97X-D3",
                "basis": "def2-TZVP",
                "solvation": "gas",
                "e_dimer_hartree": e_ab,
                "e_monomer_a_hartree": e_a,
                "e_monomer_b_hartree": e_b,
                "e_monomer_a_dcbs_hartree": e_a_dcbs,
                "e_monomer_b_dcbs_hartree": e_b_dcbs,
            }
        ),
        encoding="utf-8",
    )

    out_csv = tmp_path / "vdw_summary.csv"
    out_md = tmp_path / "vdw_report.md"
    out_json = tmp_path / "vdw_provenance.json"

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "vdw_titration_diff.py"),
            "--complex-label",
            "EC...H2O",
            "--monomer-json",
            str(mon_json),
            "--dimer-json",
            str(dim_json),
            "--bsse-json",
            str(bsse_json),
            "--output-csv",
            str(out_csv),
            "--output-md",
            str(out_md),
            "--output-json",
            str(out_json),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, f"vdw_titration_diff.py failed:\n{proc.stderr}"
    rep = json.loads(out_json.read_text(encoding="utf-8"))

    expected_raw_kcal = (e_ab - (e_a + e_b)) * vdw_titration_diff.HARTREE_TO_KCAL_MOL
    expected_cp_kcal = (e_ab - (e_a_dcbs + e_b_dcbs)) * vdw_titration_diff.HARTREE_TO_KCAL_MOL
    expected_bsse_kcal = expected_cp_kcal - expected_raw_kcal

    assert rep["collaborator_institution"] == "Tennessee Tech University"
    assert rep["counterpoise_bsse"]["delta_e_raw_kcal_mol"] == pytest.approx(expected_raw_kcal, abs=1e-9)
    assert rep["counterpoise_bsse"]["delta_e_cp_kcal_mol"] == pytest.approx(expected_cp_kcal, abs=1e-9)
    assert rep["counterpoise_bsse"]["bsse_kcal_mol"] == pytest.approx(expected_bsse_kcal, abs=1e-9)
    assert rep["counterpoise_bsse"]["bsse_kcal_mol"] > 0.0

    # C=O redshift upon H-bond complexation: 1768.9 - 1785.4 = -16.5 cm^-1
    assert rep["computed_ir_shift"]["delta_nu_co_cm1"] == pytest.approx(-16.5, abs=1e-9)
    assert rep["computed_ir_shift"]["shift_direction"] == "red_shift"

    # Unmeasured experimental spectra must be explicitly PENDING (zero fabrication)
    assert rep["experimental_atr_shift"]["status"] == "PENDING"
    assert rep["experimental_atr_shift"]["delta_nu_co_cm1"] == "PENDING"
    assert "PENDING" in out_md.read_text(encoding="utf-8")
    assert "PENDING" in out_csv.read_text(encoding="utf-8")
    assert rep["inputs_sha256"]["bsse_json"]["sha256"] == vdw_titration_diff.sha256_file(bsse_json)

    # Measured experimental ATR titration path with --kk-correct
    nu = np.linspace(1200.0, 2200.0, 1001)
    n_mon = kk_atr_correct.damped_lorentzian_refractive_index(nu, oscillators=[(1780.0, 18.0, 50000.0)], n_inf=1.40)
    n_cmp = kk_atr_correct.damped_lorentzian_refractive_index(nu, oscillators=[(1765.0, 18.0, 50000.0)], n_inf=1.40)
    atr_mon = kk_atr_correct.fresnel_atr_forward(n_mon)["atr_absorbance"]
    atr_cmp = kk_atr_correct.fresnel_atr_forward(n_cmp)["atr_absorbance"]
    exp_mon_csv = tmp_path / "exp_mon.csv"
    exp_cmp_csv = tmp_path / "exp_cmp.csv"
    for p_csv, y_arr in ((exp_mon_csv, atr_mon), (exp_cmp_csv, atr_cmp)):
        with p_csv.open("w", encoding="utf-8", newline="\n") as fh:
            w = csv.writer(fh)
            w.writerow(["wavenumber_cm1", "atr_absorbance"])
            for x, y in zip(nu, y_arr):
                w.writerow([f"{x:.4f}", f"{y:.8f}"])
    rep_meas = vdw_titration_diff.analyze_vdw_complexation(
        complex_label="EC...H2O",
        monomer_json_path=mon_json,
        dimer_json_path=dim_json,
        bsse_json_path=bsse_json,
        exp_monomer_csv=exp_mon_csv,
        exp_complex_csv=exp_cmp_csv,
        apply_kk=True,
    )
    assert rep_meas["experimental_atr_shift"]["status"] == "MEASURED"
    assert rep_meas["experimental_atr_shift"]["kk_corrected"] is True
    assert rep_meas["experimental_atr_shift"]["delta_nu_co_cm1"] == pytest.approx(-15.0, abs=1.5)


# ---------------------------------------------------------------------------
# 3. M3: Exact 2x2 Martin Fermi Resonance Dyad Deperturbation
# ---------------------------------------------------------------------------


def test_fermi_deperturb_team4_ec_and_team6_d4ec_roundtrip(tmp_path: Path) -> None:
    """Verify exact 2x2 deperturbation on Team 4 EC (1774/1803) and Team 6 d4-EC (1792) collapse."""
    # Team 4 ethylene carbonate doublet: nu_- = 1774 cm^-1, nu_+ = 1803 cm^-1
    # At R = I_-/I_+ = 11/18 = 0.611111..., nu_1^0 collapses directly onto Team 6 d4-EC = 1792.0 cm^-1!
    ratio_ec = 11.0 / 18.0
    out_json = tmp_path / "team4_ec_fermi.json"
    out_md = tmp_path / "team4_ec_fermi.md"

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "fermi_deperturb.py"),
            "--nu-plus",
            "1803.0",
            "--nu-minus",
            "1774.0",
            "--intensity-ratio",
            f"{ratio_ec:.12f}",
            "--label",
            "CHEM312_Team4_EC",
            "--isotopologue-nu",
            "1792.0",
            "--output-json",
            str(out_json),
            "--output-md",
            str(out_md),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, f"fermi_deperturb.py failed:\n{proc.stderr}"
    res = json.loads(out_json.read_text(encoding="utf-8"))
    dep = res["deperturbed"]
    ver = res["roundtrip_verification"]

    assert res["collaborator_institution"] == "Tennessee Tech University"
    assert dep["nu_1_unperturbed_cm1"] == pytest.approx(1792.0, abs=1e-6)
    assert dep["two_nu_2_unperturbed_cm1"] == pytest.approx(1785.0, abs=1e-6)
    # Trace invariance: nu_1^0 + 2*nu_2^0 == nu_+ + nu_-
    assert dep["trace_sum_cm1"] == pytest.approx(1803.0 + 1774.0, abs=1e-12)
    # Exact 2x2 eigenvalue round-trip reconstruction < 1e-9 cm^-1
    assert ver["max_eigenvalue_residual_cm1"] < 1e-9
    assert ver["intensity_ratio_residual"] < 1e-9
    assert abs(res["isotopologue_collapse_check"]["nu1_minus_isotopologue_cm1"]) < 1e-6

    # Equal-intensity resonance R = 1.0 => theta = 45 deg, |W| = Delta/2 = 14.5 cm^-1
    res_5050 = fermi_deperturb.deperturb_fermi_dyad(1803.0, 1774.0, 1.0)
    assert res_5050["deperturbed"]["mixing_angle_deg"] == pytest.approx(45.0, abs=1e-12)
    assert res_5050["deperturbed"]["coupling_W_cm1"] == pytest.approx(14.5, abs=1e-12)
    assert res_5050["roundtrip_verification"]["max_eigenvalue_residual_cm1"] < 1e-9

    # Team 6 d4-EC collapsed single-peak limit (R = 0.0)
    res_d4 = fermi_deperturb.deperturb_fermi_dyad(1792.0, 1792.0, 0.0, label="CHEM312_Team6_d4EC")
    assert res_d4["collapsed_uncoupled_limit"] is True
    assert res_d4["deperturbed"]["nu_1_unperturbed_cm1"] == pytest.approx(1792.0, abs=1e-12)
    assert res_d4["deperturbed"]["coupling_W_cm1"] == pytest.approx(0.0, abs=1e-12)
    assert res_d4["roundtrip_verification"]["max_eigenvalue_residual_cm1"] < 1e-9


# ---------------------------------------------------------------------------
# 4. M3: 6-Shard Barone GVPT2 Partitioning, Anharmonic Math & PENDING Guard
# ---------------------------------------------------------------------------


def test_gvpt2_6shard_partitioning_anharmonic_recovery_and_pending_guard(tmp_path: Path) -> None:
    """Verify deterministic K=6 coverage/non-overlap, exact VPT2 recovery, and incomplete-shard PENDING guard."""
    ethanol_xyz = REPO_ROOT / "examples" / "student_inputs" / "ethanol.xyz"
    assert ethanol_xyz.is_file()

    # Deterministic K=6 partitioning on ethanol (9 atoms -> 27 Cartesian coords -> 54 displacements)
    plan_a = gvpt2_shard_runner.build_gvpt2_plan(
        xyz_path=ethanol_xyz,
        output_dir=tmp_path / "plan_a",
        n_shards=6,
        step_size=0.01,
        write_xyz_files=True,
    )
    plan_b = gvpt2_shard_runner.build_gvpt2_plan(
        xyz_path=ethanol_xyz,
        output_dir=tmp_path / "plan_b",
        n_shards=6,
        step_size=0.01,
        write_xyz_files=False,
    )
    assert plan_a["n_shards"] == 6
    assert plan_a["total_displacements"] == 54
    seen_ids: list[str] = []
    for sid in range(6):
        entries_a = plan_a["shards"][str(sid)]
        entries_b = plan_b["shards"][str(sid)]
        assert len(entries_a) == 9
        assert [e["displacement_id"] for e in entries_a] == [e["displacement_id"] for e in entries_b]
        seen_ids.extend(e["displacement_id"] for e in entries_a)
    # 100% coverage and 0 overlap
    assert len(seen_ids) == 54
    assert len(set(seen_ids)) == 54

    # Analytical 2-mode anharmonic potential V(q0, q1) to verify exact phi3, phi4, x_ij, and GVPT2 fundamentals
    # V = 0.5*w0*q0^2 + 0.5*w1*q1^2 + (1/6)*p000*q0^3 + (1/2)*p001*q0^2*q1 + (1/6)*p111*q1^3
    #     + (1/24)*p0000*q0^4 + (1/4)*p0011*q0^2*q1^2 + (1/24)*p1111*q1^4
    w0, w1 = 1000.0, 1750.0
    p000, p001, p111 = -90.0, 45.0, -140.0
    p0000, p0011, p1111 = 30.0, -18.0, 48.0

    def exact_hessian(q0: float, q1: float) -> np.ndarray:
        h00 = w0 + p000 * q0 + p001 * q1 + 0.5 * p0000 * q0 * q0 + 0.5 * p0011 * q1 * q1
        h01 = p001 * q0 + p0011 * q0 * q1
        h11 = w1 + p111 * q1 + 0.5 * p0011 * q0 * q0 + 0.5 * p1111 * q1 * q1
        return np.array([[h00, h01], [h01, h11]], dtype=np.float64)

    # Build a 6-shard plan with 2 normal modes (4 displacements distributed over shards 0..3; shards 4..5 empty)
    # Use a 3-atom XYZ + 3-mode system so all 6 shards carry exactly 1 displacement each!
    water_xyz = tmp_path / "water_eq.xyz"
    water_xyz.write_text(
        "3\nwater\nO 0.0 0.0 0.117\nH 0.0 0.757 -0.469\nH 0.0 -0.757 -0.469\n",
        encoding="utf-8",
    )
    w2 = 3800.0
    p222, p2222 = -220.0, 75.0
    dq = 0.05

    def exact_hessian_3mode(q0: float, q1: float, q2: float) -> np.ndarray:
        h2 = exact_hessian(q0, q1)
        h3 = np.zeros((3, 3), dtype=np.float64)
        h3[:2, :2] = h2
        h3[2, 2] = w2 + p222 * q2 + 0.5 * p2222 * q2 * q2
        return h3

    nm_json = tmp_path / "nm3.json"
    disp_vecs = np.zeros((3, 3, 3), dtype=np.float64)
    disp_vecs[0, 1, 1] = 1.0
    disp_vecs[1, 2, 1] = 1.0
    disp_vecs[2, 0, 2] = 1.0
    nm_json.write_text(
        json.dumps(
            {
                "harmonic_cm1": [w0, w1, w2],
                "displacement_vectors": disp_vecs.tolist(),
                "eq_hessian_q": exact_hessian_3mode(0.0, 0.0, 0.0).tolist(),
            }
        ),
        encoding="utf-8",
    )
    plan_dir = tmp_path / "gvpt2_3m"
    plan_3m = gvpt2_shard_runner.build_gvpt2_plan(
        xyz_path=water_xyz,
        output_dir=plan_dir,
        n_shards=6,
        step_size=dq,
        normal_modes_json=nm_json,
        write_xyz_files=False,
    )
    shards_dir = tmp_path / "shards_3m"
    shards_dir.mkdir(parents=True, exist_ok=True)
    for sid in range(6):
        disp_out = {}
        for entry in plan_3m["shards"][str(sid)]:
            q = [0.0, 0.0, 0.0]
            q[int(entry["mode_index"])] = int(entry["sign"]) * dq
            disp_out[entry["displacement_id"]] = {
                "mode_index": entry["mode_index"],
                "sign": entry["sign"],
                "hessian": exact_hessian_3mode(*q).tolist(),
            }
        (shards_dir / f"shard_{sid}.json").write_text(
            json.dumps({"shard_id": sid, "displacements": disp_out}),
            encoding="utf-8",
        )

    agg_complete = gvpt2_shard_runner.aggregate_shards(
        plan_path=plan_dir / "gvpt2_plan.json",
        shards_dir=shards_dir,
        output_dir=tmp_path / "agg_complete",
    )
    assert agg_complete["status"] == "COMPLETE"
    assert agg_complete["complete"] is True
    assert agg_complete["completed_shards"] == [0, 1, 2, 3, 4, 5]
    assert agg_complete["missing_shards"] == []

    # Verify exact analytical diagonal x_22 = p2222/16 - (5/48)*p222^2 / w2 for uncoupled mode 2
    expected_x22 = p2222 / 16.0 - (5.0 / 48.0) * (p222 ** 2) / w2
    got_x22 = agg_complete["gvpt2_results"]["x_matrix_cm1"][2][2]
    assert got_x22 == pytest.approx(expected_x22, abs=1e-6)
    expected_nu2 = w2 + 2.0 * expected_x22
    assert agg_complete["gvpt2_results"]["anharmonic_fundamentals_cm1"][2] == pytest.approx(expected_nu2, abs=1e-6)
    # Semi-diagonal quartic exact recovery
    assert agg_complete["gvpt2_results"]["phi4_semi_diagonal_cm1"][0][0] == pytest.approx(p0000, abs=1e-6)
    assert agg_complete["gvpt2_results"]["phi4_semi_diagonal_cm1"][0][1] == pytest.approx(p0011, abs=1e-6)

    # Incomplete-shard PENDING guard: remove shard_4.json -> must refuse fabrication!
    (shards_dir / "shard_4.json").unlink()
    agg_pending = gvpt2_shard_runner.aggregate_shards(
        plan_path=plan_dir / "gvpt2_plan.json",
        shards_dir=shards_dir,
        output_dir=tmp_path / "agg_pending",
    )
    assert agg_pending["status"] == "PENDING"
    assert agg_pending["complete"] is False
    assert agg_pending["missing_shards"] == [4]
    assert agg_pending["gvpt2_results"]["status"] == "PENDING"
    assert agg_pending["gvpt2_results"]["anharmonic_fundamentals_cm1"] == "PENDING"
    assert agg_pending["gvpt2_results"]["x_matrix_cm1"] == "PENDING"


# ---------------------------------------------------------------------------
# 5. M4: Cryptographic L1-L3 SHA-256 FactLedger & Tamper Rejection
# ---------------------------------------------------------------------------


def test_fact_ledger_l1_l3_sha256_and_tamper_rejection(tmp_path: Path) -> None:
    """Verify L1-L3 SHA-256 FactLedger build, PENDING milestones, and fail-closed tamper rejection."""
    work = tmp_path / "dossier"
    work.mkdir()
    xyz = work / "input.xyz"
    xyz.write_text("3\nwater\nO 0 0 0\nH 0 0.75 0.58\nH 0 -0.75 0.58\n", encoding="utf-8")
    handoff_json = work / "handoff.json"
    handoff_json.write_text(
        json.dumps(
            {
                "schema": "cochem.student-handoff/2",
                "files_sha256": {"input.xyz": fact_ledger.sha256_file(xyz)},
            }
        ),
        encoding="utf-8",
    )
    stat_csv = work / "stationary_table.csv"
    stat_csv.write_text("species,energy_hartree\nwater,-76.431200\n", encoding="utf-8")
    cat_file = work / "spcat_8_18ghz.cat"
    cat_file.write_text("  10456.1234  0.0050  -4.2000 3    0.1200  3  10001\n", encoding="utf-8")

    claims_json = work / "claims.json"
    claims_json.write_text(
        json.dumps(
            [
                {
                    "claim_id": "C-001",
                    "statement": "M4 SPCAT 8-18 GHz prediction sealed from verified catalog.",
                    "artifact_ids": ["L1-003"],
                }
            ]
        ),
        encoding="utf-8",
    )

    out_json = work / "FactLedger.json"
    out_md = work / "FactLedger.md"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "fact_ledger.py"),
            "--artifacts",
            str(xyz),
            str(handoff_json),
            str(cat_file),
            str(stat_csv),
            "--base-dir",
            str(work),
            "--project-label",
            "CHEM312_Team4_Dossier",
            "--claims-json",
            str(claims_json),
            "--output-json",
            str(out_json),
            "--output-md",
            str(out_md),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, f"fact_ledger.py build failed:\n{proc.stderr}"
    ledger = json.loads(out_json.read_text(encoding="utf-8"))
    assert ledger["collaborator_institution"] == "Tennessee Tech University"
    milestones = {m["milestone"]: m["status"] for m in ledger["levels"]["L3_milestones"]}
    assert milestones["M1_conformers"] == "VERIFIED"
    assert milestones["M2_kk_atr"] == "VERIFIED"
    assert milestones["M3_nci_gvpt2_fermi"] == "PENDING"
    assert milestones["M4_spcat_8_18ghz"] == "VERIFIED"
    assert "Tennessee Tech University" in out_md.read_text(encoding="utf-8")

    # Clean verification passes via CLI
    ver_ok = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "fact_ledger.py"),
            "--verify",
            str(out_json),
            "--base-dir",
            str(work),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert ver_ok.returncode == 0
    assert json.loads(ver_ok.stdout)["verified"] is True

    # Unhashed claim must be rejected fail-closed
    with pytest.raises(fact_ledger.FactLedgerIntegrityError, match="Unhashed"):
        fact_ledger.build_fact_ledger(
            artifact_paths=[xyz],
            base_dir=work,
            claims=[{"claim_id": "BAD-1", "statement": "Fabricated claim without evidence", "artifact_ids": []}],
        )

    # Tamper 1 byte of hashed L1 artifact -> must fail closed!
    cat_file.write_text("  10456.9999  0.0050  -4.2000 3    0.1200  3  10001\n", encoding="utf-8")
    with pytest.raises(fact_ledger.FactLedgerIntegrityError, match="Tampered artifact"):
        fact_ledger.verify_fact_ledger(out_json, base_dir=work)

    ver_bad = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "fact_ledger.py"),
            "--verify",
            str(out_json),
            "--base-dir",
            str(work),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert ver_bad.returncode != 0


# ---------------------------------------------------------------------------
# 6. Workflows YAML Validity, Zero Push/Cron, Hygiene & SCRIBE Manifest
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "workflow_name",
    [
        "05_gvpt2_6shard_anharmonic.yml",
        "07_spcat_8_18ghz_prediction.yml",
    ],
)
def test_new_m3_m4_workflows_yaml_zero_push_zero_cron(workflow_name: str) -> None:
    wf_path = REPO_ROOT / ".github" / "workflows" / workflow_name
    assert wf_path.is_file(), f"Missing workflow: {wf_path}"
    raw_text = wf_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw_text)
    assert isinstance(data, dict)
    triggers = data.get("on", data.get(True))
    assert isinstance(triggers, dict)
    assert set(triggers.keys()) == {"workflow_dispatch"}, f"{workflow_name} must be strictly workflow_dispatch-only"
    assert "push" not in triggers
    assert "schedule" not in triggers
    assert "Tennessee Tech University" in raw_text
    assert "texas tech" not in raw_text.lower()
    for leak in ("FarIR_v16", "MRW_Permission"):
        assert leak not in raw_text

    if workflow_name == "05_gvpt2_6shard_anharmonic.yml":
        assert data["jobs"]["gvpt2_shard"]["strategy"]["matrix"]["shard"] == [0, 1, 2, 3, 4, 5]
        assert "vpt2_anharmonic" in raw_text
        inputs = triggers["workflow_dispatch"]["inputs"]
        assert inputs["pre_optimize"]["type"] == "boolean"
        assert inputs["pre_optimize"]["default"] is True
        assert "geometric==1.1.1" in raw_text
        assert "parse_harmonic_frequencies_cm1" in raw_text
        assert "dx_bohr" in raw_text
    if workflow_name == "07_spcat_8_18ghz_prediction.yml":
        assert "2.0" in raw_text
        assert "8.0" in raw_text and "18.0" in raw_text
        assert "FactLedger" in raw_text
        assert "f5af2ff0f1acb1eb11ecffe7ef3b55d457801f7b" in raw_text
        assert "479840d1bd19dc2e45612e49a950aee3b72256ef6748d80117c856ab4084c361" in raw_text
        assert "a    1  1   0   30   0   1   1   1   0   0   0" in raw_text


def test_gvpt2_parse_harmonic_frequencies_preserves_complex_imaginary_modes() -> None:
    """Verify PySCF complex imaginary modes (1j * w) become negative cm^-1 instead of 0.0."""
    raw = [0.0 + 996.856j, 0.0 + 286.411j, 274.259 + 0.0j, 914.828]
    parsed = gvpt2_shard_runner.parse_harmonic_frequencies_cm1(raw)
    assert parsed[0] == pytest.approx(-996.856, abs=1e-6)
    assert parsed[1] == pytest.approx(-286.411, abs=1e-6)
    assert parsed[2] == pytest.approx(274.259, abs=1e-6)
    assert parsed[3] == pytest.approx(914.828, abs=1e-6)
    assert min(parsed) < 0.0


def test_module_distribution_scribe_live_operations_and_zero_texas_tech() -> None:
    manifest = manage_modules.load_manifest()
    scribe = manifest["modules"]["scribe"]
    assert scribe["operations"] == [
        "render_geom_comparison",
        "render_kinetic_rxn_profile",
        "verify_source_register",
        "audit_farir_exclusion",
    ]
    assert "phase_reservation" not in scribe

    new_files = [
        REPO_ROOT / "scripts" / "kk_atr_correct.py",
        REPO_ROOT / "scripts" / "vdw_titration_diff.py",
        REPO_ROOT / "scripts" / "fermi_deperturb.py",
        REPO_ROOT / "scripts" / "gvpt2_shard_runner.py",
        REPO_ROOT / "scripts" / "kraitchman_rs.py",
        REPO_ROOT / "scripts" / "fact_ledger.py",
        REPO_ROOT / "student" / "README.md",
        REPO_ROOT / "student" / "CHEM312L_STEP_BY_STEP_GUIDE.md",
        REPO_ROOT / ".docs" / "GET_STARTED.md",
    ]
    for path in new_files:
        text = path.read_text(encoding="utf-8")
        assert "texas tech" not in text.lower(), f"Forbidden 'Texas Tech' in {path}"
        for leak in ("FarIR_v16", "MRW_Permission"):
            assert leak not in text, f"Forbidden FarIR leak {leak!r} in {path}"


# ---------------------------------------------------------------------------
# 7. QA-R1 Student UX Fixes: Kraitchman |r_s|, KK Aliases, SPCAT CLI & Hygiene
# ---------------------------------------------------------------------------


def _rigid_rotor_abc_and_pas(masses: np.ndarray, coords: np.ndarray) -> tuple[tuple[float, float, float], np.ndarray]:
    """Compute exact rigid-rotor rotational constants (A, B, C in MHz) and principal-axis coordinates."""
    com = np.sum(masses[:, None] * coords, axis=0) / np.sum(masses)
    rc = coords - com
    inertia = np.zeros((3, 3), dtype=np.float64)
    for mi, (x, y, z) in zip(masses, rc):
        inertia[0, 0] += mi * (y * y + z * z)
        inertia[1, 1] += mi * (x * x + z * z)
        inertia[2, 2] += mi * (x * x + y * y)
        inertia[0, 1] -= mi * x * y
        inertia[0, 2] -= mi * x * z
        inertia[1, 2] -= mi * y * z
    inertia[1, 0] = inertia[0, 1]
    inertia[2, 0] = inertia[0, 2]
    inertia[2, 1] = inertia[1, 2]
    evals, evecs = np.linalg.eigh(inertia)
    abc_mhz = tuple(float(kraitchman_rs.ROT_CONST_CONVERSION_MHZ_AMU_A2 / val) for val in evals)
    return abc_mhz, rc @ evecs  # type: ignore[return-value]


def test_kraitchman_rs_3d_planar_and_honest_costain_imaginary(tmp_path: Path) -> None:
    """Verify exact 3D & planar Kraitchman |r_s| recovery plus honest r_s^2 < 0 imaginary flagging."""
    # Case A: Non-planar 3D rigid asymmetric rotor -> exact recovery to < 1e-10 A
    masses_3d = np.array([12.0, 15.994915, 15.994915, 1.007825, 1.007825, 18.998403], dtype=np.float64)
    coords_3d = np.array(
        [
            [0.00, 0.10, 0.05],
            [1.20, 0.20, -0.10],
            [-0.80, -0.90, 0.30],
            [-0.30, 1.15, 0.40],
            [-1.60, -0.60, -0.25],
            [0.50, -0.40, -1.10],
        ],
        dtype=np.float64,
    )
    abc0_3d, pas0_3d = _rigid_rotor_abc_and_pas(masses_3d, coords_3d)
    dm = 1.006277
    masses_3d_iso = masses_3d.copy()
    masses_3d_iso[3] += dm
    abc1_3d, _ = _rigid_rotor_abc_and_pas(masses_3d_iso, coords_3d)

    res_3d = kraitchman_rs.compute_kraitchman_rs(
        parent_abc_mhz=abc0_3d,
        iso_abc_mhz=abc1_3d,
        delta_mass_amu=dm,
        parent_mass_amu=float(np.sum(masses_3d)),
        mode="nonplanar",
        label="test_3d_atom3",
    )
    assert res_3d["course_institution"] == "Cumberland University"
    assert res_3d["collaborator_institution"] == "Tennessee Tech University"
    assert res_3d["any_imaginary_coordinate"] is False
    for idx, ax in enumerate(("a", "b", "c")):
        assert res_3d["coordinates"][ax]["imaginary"] is False
        assert res_3d["coordinates"][ax]["abs_rs_angstrom"] == pytest.approx(abs(float(pas0_3d[3, idx])), abs=1e-9)

    # Case B: Planar rigid asymmetric rotor (z = 0, trans-HCOOH-like) via CLI with JSON inputs
    masses_pl = np.array([12.0, 15.994915, 15.994915, 1.007825, 1.007825], dtype=np.float64)
    coords_pl = np.array(
        [
            [0.00, 0.00, 0.0],
            [1.20, 0.05, 0.0],
            [-0.65, 1.15, 0.0],
            [-0.55, -0.95, 0.0],
            [-1.60, 0.98, 0.0],
        ],
        dtype=np.float64,
    )
    abc0_pl, pas0_pl = _rigid_rotor_abc_and_pas(masses_pl, coords_pl)
    masses_pl_iso = masses_pl.copy()
    masses_pl_iso[4] += dm
    abc1_pl, _ = _rigid_rotor_abc_and_pas(masses_pl_iso, coords_pl)

    parent_json = tmp_path / "parent.json"
    iso_json = tmp_path / "iso.json"
    out_json = tmp_path / "rs.json"
    out_md = tmp_path / "rs.md"
    parent_json.write_text(
        json.dumps(
            {
                "a_mhz": abc0_pl[0],
                "b_mhz": abc0_pl[1],
                "c_mhz": abc0_pl[2],
                "molecular_mass_amu": float(np.sum(masses_pl)),
            }
        ),
        encoding="utf-8",
    )
    iso_json.write_text(
        json.dumps(
            {
                "a_mhz": abc1_pl[0],
                "b_mhz": abc1_pl[1],
                "c_mhz": abc1_pl[2],
                "molecular_mass_amu": float(np.sum(masses_pl_iso)),
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(REPO_ROOT / "scripts" / "kraitchman_rs.py"),
            "--parent",
            str(parent_json),
            "--iso",
            str(iso_json),
            "--delta-mass-amu",
            str(dm),
            "--mode",
            "planar",
            "--output-json",
            str(out_json),
            "--output-md",
            str(out_md),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, f"kraitchman_rs.py CLI failed:\n{proc.stderr}"
    cli_res = json.loads(out_json.read_text(encoding="utf-8"))
    assert cli_res["effective_mode"] == "planar"
    assert cli_res["coordinates"]["a"]["abs_rs_angstrom"] == pytest.approx(abs(float(pas0_pl[4, 0])), abs=1e-9)
    assert cli_res["coordinates"]["b"]["abs_rs_angstrom"] == pytest.approx(abs(float(pas0_pl[4, 1])), abs=1e-9)
    assert cli_res["coordinates"]["c"]["in_plane_fixed"] is True
    assert "Cumberland University" in out_md.read_text(encoding="utf-8")
    assert "Tennessee Tech University" in out_md.read_text(encoding="utf-8")

    # Case C: Costain imaginary coordinate (r_s^2 < 0) due to positive inertial defect on a planar atom
    # Slightly larger I_c' (lower C') -> positive inertial defect Delta_0' > 0 -> Delta_P_c < 0 -> c^2 < 0
    abc1_vib = (abc1_pl[0], abc1_pl[1], abc1_pl[2] * 0.998)
    res_imag = kraitchman_rs.compute_kraitchman_rs(
        parent_abc_mhz=abc0_pl,
        iso_abc_mhz=abc1_vib,
        delta_mass_amu=dm,
        parent_mass_amu=float(np.sum(masses_pl)),
        mode="nonplanar",
    )
    assert res_imag["coordinates"]["c"]["rs_squared_angstrom2"] < 0.0
    assert res_imag["coordinates"]["c"]["imaginary"] is True
    assert res_imag["coordinates"]["c"]["abs_rs_angstrom"] is None
    assert res_imag["coordinates"]["c"]["costain_uncertainty_angstrom"] is None
    assert res_imag["any_imaginary_coordinate"] is True
    assert res_imag["distance_from_com_angstrom"] is None


def test_kk_atr_correct_backward_compatible_cli_aliases(tmp_path: Path) -> None:
    """Verify --csv, --out, --angle, and --crystal diamond/znse/ge match canonical flags identically."""
    nu = np.linspace(400.0, 4000.0, 3601)
    n_complex = kk_atr_correct.damped_lorentzian_refractive_index(
        nu, oscillators=[(1725.0, 18.0, 62000.0)], n_inf=1.3714
    )
    atr_abs = kk_atr_correct.fresnel_atr_forward(n_complex, n_crystal=2.417, angle_deg=45.0)["atr_absorbance"]
    in_csv = tmp_path / "hcooh_atr.csv"
    with in_csv.open("w", encoding="utf-8", newline="\n") as fh:
        w = csv.writer(fh)
        w.writerow(["wavenumber_cm-1", "absorbance"])
        for x, y in zip(nu, atr_abs):
            w.writerow([f"{x:.4f}", f"{y:.8f}"])

    canon_csv = tmp_path / "canon.csv"
    canon_json = tmp_path / "canon.json"
    alias_csv = tmp_path / "alias.csv"
    alias_json = tmp_path / "alias.json"

    p_canon = subprocess.run(
        [
            sys.executable,
            "-B",
            str(REPO_ROOT / "scripts" / "kk_atr_correct.py"),
            "--input",
            str(in_csv),
            "--n-inf",
            "1.3714",
            "--angle-deg",
            "45.0",
            "--n-crystal",
            "2.417",
            "--output-csv",
            str(canon_csv),
            "--output-json",
            str(canon_json),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert p_canon.returncode == 0, p_canon.stderr

    p_alias = subprocess.run(
        [
            sys.executable,
            "-B",
            str(REPO_ROOT / "scripts" / "kk_atr_correct.py"),
            "--csv",
            str(in_csv),
            "--n-inf",
            "1.3714",
            "--angle",
            "45.0",
            "--crystal",
            "diamond",
            "--out",
            str(alias_csv),
            "--output-json",
            str(alias_json),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert p_alias.returncode == 0, f"Alias CLI failed:\n{p_alias.stderr}"

    j_canon = json.loads(canon_json.read_text(encoding="utf-8"))
    j_alias = json.loads(alias_json.read_text(encoding="utf-8"))
    assert j_alias["n_crystal"] == pytest.approx(2.417)
    assert j_alias["angle_deg"] == pytest.approx(45.0)
    assert j_alias["nu_max_atr_cm1"] == j_canon["nu_max_atr_cm1"]
    assert j_alias["nu_max_kappa_cm1"] == j_canon["nu_max_kappa_cm1"]
    assert j_alias["delta_nu_cm1"] == j_canon["delta_nu_cm1"]
    assert alias_csv.is_file()
    assert kk_atr_correct.parse_crystal_refractive_index("znse") == pytest.approx(2.40)
    assert kk_atr_correct.parse_crystal_refractive_index("ge") == pytest.approx(4.00)
    assert kk_atr_correct.parse_crystal_refractive_index("2.417") == pytest.approx(2.417)


def test_spcat_runner_help_succeeds_without_pyarrow() -> None:
    """Verify scripts/spcat_runner.py --help exits 0 even when pyarrow and pandas are absent."""
    probe = (
        "import sys, runpy; "
        "sys.modules['pyarrow'] = None; "
        "sys.modules['pyarrow.parquet'] = None; "
        "sys.modules['pandas'] = None; "
        "sys.argv = ['scripts/spcat_runner.py', '--help']; "
        "runpy.run_path('scripts/spcat_runner.py', run_name='__main__')"
    )
    proc = subprocess.run(
        [sys.executable, "-B", "-c", probe],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert proc.returncode == 0, f"spcat_runner.py --help failed without pyarrow:\n{proc.stderr}"
    assert "--a-mhz" in proc.stdout
    assert "--output-csv" in proc.stdout


def test_student_guides_hygiene_devcontainer_path_and_starter_templates() -> None:
    """Verify SB-01..SB-10 student docs hygiene, devcontainer PATH wiring, and starter templates."""
    required_workflows = (
        "student_conformers.yml",
        "04_crest_nci_dimer_bsse.yml",
        "05_gvpt2_6shard_anharmonic.yml",
        "06_aimnet2_neb_pyscf_rxn_profile.yml",
        "07_spcat_8_18ghz_prediction.yml",
    )
    for guide_rel in ("student/CHEM312L_STEP_BY_STEP_GUIDE.md", "student/README.md"):
        guide_path = REPO_ROOT / guide_rel
        assert guide_path.is_file(), f"Missing student guide: {guide_rel}"
        text = guide_path.read_text(encoding="utf-8")
        assert "Google Colab" not in text, f"Forbidden 'Google Colab' in {guide_rel}"
        assert "Classroom50" not in text, f"Forbidden 'Classroom50' in {guide_rel}"
        assert "texas tech" not in text.lower(), f"Forbidden 'Texas Tech' in {guide_rel}"
        assert "Cumberland University" in text
        assert "Tennessee Tech University" in text
        for wf in required_workflows:
            assert wf in text, f"Missing canonical workflow {wf} in {guide_rel}"

    # Verify devcontainer remoteEnv.PATH and setup_devcontainer.sh profile.d + bashrc wiring (SB-02)
    dev_cfg = json.loads((REPO_ROOT / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8"))
    assert dev_cfg["remoteEnv"]["PATH"].startswith("/home/vscode/CoChem_Artifacts/ui-env/bin:")
    setup_sh = (REPO_ROOT / "scripts" / "setup_devcontainer.sh").read_text(encoding="utf-8")
    assert "/etc/profile.d/cochem-ui-env.sh" in setup_sh
    assert "/home/vscode/.bashrc" in setup_sh

    # Verify honest Codespace setup wait time & starter templates (SB-05)
    hosted_text = (REPO_ROOT / "scripts" / "hosted_dashboard.py").read_text(encoding="utf-8")
    assert "5–10 minutes on a fresh Codespace" in hosted_text
    assert "2–4 minutes" not in hosted_text
    for starter in ("AI_Usage_Log.md", "targets/team_card.yaml", "data/.gitkeep", "results/.gitkeep"):
        assert (REPO_ROOT / starter).is_file(), f"Missing student starter template: {starter}"
    assert "!examples/student_inputs/**/*.xyz" in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
