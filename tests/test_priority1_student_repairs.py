"""Zero-mock regression tests for Priority-1 clean-main student E2E repairs in CoChem-BASE.

Covers:
- FRICTION-312-01 & FRIC-01/FRIC-02: Course no-license isolation in Voila Start_Here GUI
  (CHEM312/CHEM311 strictly hide & block ORCA/CFOUR even when Golden Registry has ORCA;
  formatted HTML execution_stack dict; wider non-truncating course dropdown).
- FRICTION-312-03 & FRICTION-312-04: student/conformers.py CLI parity (--xyz/--output-dir
  plus positional args), non-quick CREST default, and local xTB/CREST resolution without
  KeyError: 'COCHEM_FREE_ROOT'.
- FRICTION-312-08: IsotopologueSpectroscopyEngine accepts small physical FD Hessian
  asymmetry (<= 1e-4 Eh/bohr^2) with explicit symmetrization provenance & warning while
  still failing closed on genuinely asymmetric matrices (> 1e-4).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import warnings

import numpy as np
import pytest

from cochem_base.spectroscopy.isotopologue import (
    FD_HESSIAN_SYMMETRY_ATOL,
    IsotopologueSpectroscopyEngine,
)
from student import conformers

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_isotopologue_symmetrizes_small_fd_asymmetry_and_rejects_large() -> None:
    """FRICTION-312-08: Accept realistic PySCF DFT-D3BJ FD asymmetry (2.6e-6) and reject > 1e-4."""
    coords = np.array(
        [[0.0, 0.0, 0.0], [0.0, 0.757, 0.587], [0.0, -0.757, 0.587]],
        dtype=np.float64,
    )
    base_h = np.eye(9, dtype=np.float64) * 0.4

    # 1. Small physical FD dispersion asymmetry (~2.62e-6 Eh/bohr^2) succeeds with warning & provenance
    fd_h = base_h.copy()
    fd_h[0, 3] += 2.617e-6
    with pytest.warns(RuntimeWarning, match="Symmetrized Cartesian Hessian"):
        eng = IsotopologueSpectroscopyEngine(["O", "H", "H"], coords, fd_h)
    assert eng.hessian_symmetrized is True
    assert eng.raw_hessian_max_asymmetry == pytest.approx(2.617e-6, rel=1e-6)
    assert np.allclose(eng.cartesian_hessian, eng.cartesian_hessian.T, atol=1e-15)
    res = eng.compute_observables()
    assert res.geometry_qualification["hessian_symmetrized"] is True
    assert res.geometry_qualification["raw_hessian_max_asymmetry"] == pytest.approx(2.617e-6, rel=1e-6)

    # 2. Large unphysical asymmetry (> 1e-4) MUST still raise ValueError
    bad_h = base_h.copy()
    bad_h[0, 3] += 5.0 * FD_HESSIAN_SYMMETRY_ATOL
    with pytest.raises(ValueError, match="Cartesian Hessian must be symmetric"):
        IsotopologueSpectroscopyEngine(["O", "H", "H"], coords, bad_h)

    # 3. High-magnitude Hessian entries (~2e6) with asymmetry 1.5e-4 MUST NOT bypass the 1e-4 absolute cap via rtol
    huge_h = np.eye(9, dtype=np.float64) * 2.0e6
    huge_h[0, 1] = 2.0e6
    huge_h[1, 0] = 2.0e6 + 1.5e-4
    with pytest.raises(ValueError, match="exceeds finite-difference tolerance"):
        IsotopologueSpectroscopyEngine(["O", "H", "H"], coords, huge_h)


def test_conformers_cli_flags_default_non_quick_and_local_engine_resolution(
    tmp_path: Path,
) -> None:
    """FRICTION-312-03/04: Named --xyz/--output-dir flags, non-quick CREST default, no COCHEM_FREE_ROOT crash."""
    # Default build_crest_argv does NOT pass --quick unless explicitly requested
    argv_full = conformers.build_crest_argv("/usr/bin/crest", "/usr/bin/xtb")
    assert "--quick" not in argv_full
    assert "--legacy" in argv_full and "--nocross" in argv_full
    argv_quick = conformers.build_crest_argv("/usr/bin/crest", "/usr/bin/xtb", quick=True)
    assert "--quick" in argv_quick

    # Both named flags (CHEM312L guide) and legacy positional args resolve cleanly
    parser = conformers.build_arg_parser()
    ns_named = parser.parse_args(
        [
            "--xyz",
            "examples/student_inputs/hcooh_start.xyz",
            "--output-dir",
            str(tmp_path / "m1_out"),
            "--basis",
            "def2-TZVP",
            "--frequencies",
        ]
    )
    fname, work, out = conformers.resolve_cli_paths(ns_named)
    assert fname == "examples/student_inputs/hcooh_start.xyz"
    assert out == tmp_path / "m1_out"
    assert work == tmp_path / "m1_out" / "_work"
    assert ns_named.quick is False

    ns_pos = parser.parse_args(
        [
            "examples/student_inputs/hcooh_start.xyz",
            str(tmp_path / "w"),
            str(tmp_path / "o"),
        ]
    )
    assert conformers.resolve_cli_paths(ns_pos) == (
        "examples/student_inputs/hcooh_start.xyz",
        tmp_path / "w",
        tmp_path / "o",
    )

    # _resolve_free_engines works cleanly without COCHEM_FREE_ROOT using COCHEM_XTB_BIN/COCHEM_CREST_BIN
    xtb_bin = tmp_path / "xtb_bin"
    crest_bin = tmp_path / "crest_bin"
    xtb_bin.write_bytes(b"#!/bin/sh\necho xtb\n")
    crest_bin.write_bytes(b"#!/bin/sh\necho crest\n")
    env_keys = ("COCHEM_FREE_ROOT", "COCHEM_XTB_BIN", "COCHEM_CREST_BIN")
    saved_env = {k: os.environ.get(k) for k in env_keys}
    try:
        os.environ.pop("COCHEM_FREE_ROOT", None)
        os.environ["COCHEM_XTB_BIN"] = str(xtb_bin)
        os.environ["COCHEM_CREST_BIN"] = str(crest_bin)
        payload = tmp_path / "payload"
        payload.mkdir()
        r_xtb, r_crest, _ = conformers._resolve_free_engines(payload)
        assert Path(r_xtb).resolve() == xtb_bin.resolve()
        assert Path(r_crest).resolve() == crest_bin.resolve()
        manifest_data = json.loads((payload / "engines.json").read_text(encoding="utf-8"))
        assert manifest_data["xtb"]["sha256"] == hashlib.sha256(xtb_bin.read_bytes()).hexdigest()
        assert manifest_data["crest"]["sha256"] == hashlib.sha256(crest_bin.read_bytes()).hexdigest()
        assert "observed_version" in manifest_data["crest"]

        # Tampered COCHEM_FREE_ROOT manifest hash MUST fail closed
        free_root = tmp_path / "free_root"
        (free_root / "xtb/xtb-dist/bin").mkdir(parents=True)
        (free_root / "crest/crest").mkdir(parents=True)
        (free_root / "xtb/xtb-dist/bin/xtb").write_bytes(b"#!/bin/sh\necho xtb 6.7.1\n")
        (free_root / "crest/crest/crest").write_bytes(b"#!/bin/sh\necho crest 3.0.2\n")
        (free_root / "engines.json").write_text(
            json.dumps({"xtb": {"sha256": "0" * 64}, "crest": {"sha256": "0" * 64}}),
            encoding="utf-8",
        )
        os.environ["COCHEM_FREE_ROOT"] = str(free_root)
        with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
            conformers._resolve_free_engines(tmp_path / "payload_bad")
    finally:
        for k, val in saved_env.items():
            if val is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = val


def test_gui_chem312_blocks_orca_and_renders_clean_pathway_html(tmp_path: Path) -> None:
    """FRICTION-312-01 & FRIC-01/02: CHEM312 course mode hides ORCA even with audited Golden Registry."""
    cure_root = REPO_ROOT.parent / "CoChem-CURE"
    if not cure_root.is_dir():
        pytest.skip("CoChem-CURE sibling checkout required")

    # Build a real signed Golden Registry containing an executable binary recorded under 'orca'
    local_orca_bin = tmp_path / ("orca.exe" if os.name == "nt" else "orca")
    local_orca_bin.write_bytes(b"#!/bin/sh\necho orca\n")
    if os.name != "nt":
        local_orca_bin.chmod(0o755)
    digest = hashlib.sha256(local_orca_bin.read_bytes()).hexdigest()

    script = f"""
import os, sys
from pathlib import Path
from cochem_base.cochem_core_registry_schema import CoChemSystemConfig, EngineInfo
from cochem_base.core.cochem_core_registry_manager import save_system_config
from ui.voila_layout.cochem_gui import CoChemGUI

reg_path = Path({str(tmp_path / 'registry.json')!r})
cfg = CoChemSystemConfig.create_default(auto_detect_hardware=True)
cfg.engines = {{"orca": EngineInfo(status="found", path={str(local_orca_bin.resolve())!r}, hash={digest!r})}}
save_system_config(cfg.model_dump(mode="json"), reg_path)

gui = CoChemGUI()
for name in ("_student_setup_initial_worker", "_research_capability_worker"):
    w = getattr(gui, name, None)
    if w is not None:
        w.join(timeout=15)

# In standalone research mode, audited ORCA is present
assert "ORCA" in [v for _, v in gui.matrix_engine.options]

# Switching to course mode -> CHEM312 MUST immediately remove & block ORCA/CFOUR
gui.course_mode_selector.value = "course"
gui.cure_course_selector.value = "CHEM312"
opts_312 = [v for _, v in gui.matrix_engine.options]
assert "ORCA" not in opts_312, opts_312
assert "CFOUR" not in opts_312, opts_312
assert gui.matrix_engine.value != "ORCA"
assert "Run ORCA" not in gui.btn_execute.description
assert gui._check_local_engine_authority("orca") != ""
# FRIC-01: no raw Python dict repr in pathway HTML
assert "{{'primary':" not in gui.cure_pathway_status.value
assert "Local WSL2 Ubuntu" in gui.cure_pathway_status.value
# FRIC-02: wider non-truncating course dropdown
assert gui.cure_course_selector.layout.width == "100%"

# Switching to CHEM490 (which lists ORCA 6.1.1, not CFOUR) restores audited ORCA while still blocking CFOUR
gui.cure_course_selector.value = "CHEM490"
opts_490 = [v for _, v in gui.matrix_engine.options]
assert "ORCA" in opts_490, opts_490
assert "CFOUR" not in opts_490, opts_490
assert gui._check_local_engine_authority("cfour") != ""

# Exact engine-ID matching MUST reject substring tricks like "not-orca" or "no ORCA"
assert CoChemGUI._authorized_licensed_engines_from_profile({{"engines": ["not-orca", "xTB (no cfour)"]}}) == frozenset()
assert CoChemGUI._authorized_licensed_engines_from_profile({{"engines": ["ORCA 6.1.1"]}}) == frozenset({{"orca"}})
assert CoChemGUI._authorized_licensed_engines_from_profile({{"engines": ["ORCA 6.1.1", "CFOUR 2.1"]}}) == frozenset({{"orca", "cfour"}})
assert CoChemGUI._authorized_licensed_engines_from_profile({{"licensed_engines_allowed": False, "engines": ["ORCA 6.1.1"]}}) == frozenset()
assert CoChemGUI._authorized_licensed_engines_from_profile(None) == frozenset()

# Explicit Free engines toggle in Tab 1 hides ORCA again
gui.license_mode.value = "orca"
gui.license_mode.value = "none"
assert "ORCA" not in [v for _, v in gui.matrix_engine.options]

# Unresolvable/unknown course profile in course mode MUST fail closed (never allow ORCA)
gui.license_mode.value = "orca"
gui._course_mode_updating = True
try:
    gui.cure_course_selector.options = list(gui.cure_course_selector.options) + [("UNKNOWN_COURSE", "UNKNOWN_COURSE")]
    gui.cure_course_selector.value = "UNKNOWN_COURSE"
finally:
    gui._course_mode_updating = False
gui._refresh_engine_choices()
assert "ORCA" not in [v for _, v in gui.matrix_engine.options]
assert gui._check_local_engine_authority("orca") != ""
print("GUI_LICENSE_ISOLATION_OK")
"""
    env = dict(
        os.environ,
        COCHEM_CONFIG=str(tmp_path / "registry.json"),
        COCHEM_ARTIFACT_DIR=str(tmp_path / "artifacts"),
        COCHEM_STUDENT_AUTO_SETUP="0",
        COCHEM_STUDENT_AUTO_REMOTE_CHECK="0",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=os.pathsep.join([str(REPO_ROOT), str(REPO_ROOT / "src"), str(cure_root)]),
    )
    proc = subprocess.run(
        [sys.executable, "-B", "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "GUI_LICENSE_ISOLATION_OK" in proc.stdout


def test_fact_ledger_maps_chem410_and_chem311_milestone_directories(tmp_path: Path) -> None:
    """FRICTION-410-02: CHEM410 M1-M4 & CHEM311 M0-M5 map from relative directories and handoff ZIPs."""
    from scripts import fact_ledger
    from student import handoff

    work = tmp_path / "chem410_run"
    (work / "m1_labs").mkdir(parents=True)
    (work / "m2_statmech").mkdir(parents=True)
    (work / "m3_kinetics" / "out").mkdir(parents=True)
    (work / "handoff_out").mkdir(parents=True)

    m1_file = work / "m1_labs" / "titration_diprotic.json"
    m1_file.write_text(json.dumps({"pka": [2.0, 6.0]}), encoding="utf-8")
    m2_file = work / "m2_statmech" / "boltzmann_ethanol.json"
    m2_file.write_text(json.dumps({"n_conformers": 2}), encoding="utf-8")
    m3_file = work / "m3_kinetics" / "out" / "dft_stage.json"
    m3_file.write_text(json.dumps({"stationary_points": ["R", "TS", "P"]}), encoding="utf-8")

    h2o_xyz = "3\nwater\nO 0.0 0.0 0.117\nH 0.0 0.757 -0.469\nH 0.0 -0.757 -0.469\n"
    manifest = handoff.StudentHandoffV2Manifest(
        workflow_type="conformer",
        input_name="ethanol_start.xyz",
        charge=0,
        multiplicity=1,
        method="GFN2-xTB",
        basis="built-in",
        solvation="gas",
        solvent_name=None,
        hessian_calculated=True,
        n_imaginary_modes=0,
        course_id="CHEM410",
        collaborator_institution="Tennessee Tech University",
        target_continuation="workstation",
        starting_xyz="input.xyz",
        primary_xyz="refined.xyz",
        ensemble_xyz="crest_conformers.xyz",
        candidate_count=1,
        selected="refined.xyz",
        student_id="chem410_e2e",
        repository="ProfJJK-CoChem/CoChem-BASE",
        commit="a" * 40,
        run_id="chem410-test",
        attempt="1",
        metadata={"course": "CHEM410"},
    )
    zpath, _, _, _ = handoff.build_student_handoff_v2_zip(
        {"input.xyz": h2o_xyz, "refined.xyz": h2o_xyz, "crest_conformers.xyz": h2o_xyz},
        manifest,
        work / "handoff_out",
    )

    ledger = fact_ledger.build_fact_ledger(
        artifact_paths=[m1_file, m2_file, m3_file, zpath],
        base_dir=work,
        course_id="CHEM410",
    )
    by_path = {
        item["path"]: item["milestone"]
        for tier in ("L1_primary_artifacts", "L2_derived_artifacts")
        for item in ledger["levels"][tier]
    }
    assert by_path["m1_labs/titration_diprotic.json"] in ("M1", "CHEM410_M1")
    assert by_path["m2_statmech/boltzmann_ethanol.json"] in ("M2", "CHEM410_M2")
    assert by_path["m3_kinetics/out/dft_stage.json"] in ("M3", "CHEM410_M3")
    assert by_path[f"handoff_out/{zpath.name}"] in ("M4", "CHEM410_M4")
    ms_statuses = [m["status"] for m in ledger["levels"]["L3_milestones"]]
    assert ms_statuses and all(s == "VERIFIED" for s in ms_statuses), ledger["levels"]["L3_milestones"]

    # Round-trip fail-closed verification
    out_json = work / "FactLedger.json"
    out_json.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    receipt = fact_ledger.verify_fact_ledger(out_json, base_dir=work)
    assert receipt["verified"] is True
    assert receipt["pending_milestone_count"] == 0

    # Negative checks: non-anchored 'archive-m3-backups' must NOT verify M3, and a plain ZIP without
    # handoff.json in handoff_out/ must NOT verify M4.
    import zipfile

    neg_work = tmp_path / "chem410_neg"
    (neg_work / "archive-m3-backups").mkdir(parents=True)
    (neg_work / "handoff_out").mkdir(parents=True)
    stray = neg_work / "archive-m3-backups" / "notes.json"
    stray.write_text(json.dumps({"note": "backup"}), encoding="utf-8")
    plain_zip = neg_work / "handoff_out" / "ordinary.zip"
    with zipfile.ZipFile(plain_zip, "w") as zf:
        zf.writestr("readme.txt", "not a handoff manifest")
    capstone_zip = neg_work / "capstone.zip"
    with zipfile.ZipFile(capstone_zip, "w") as zf:
        zf.writestr("notes.txt", "unmanifested capstone zip")
    neg_ledger = fact_ledger.build_fact_ledger(
        artifact_paths=[stray, plain_zip, capstone_zip],
        base_dir=neg_work,
        course_id="CHEM410",
    )
    neg_ms = {m["milestone"]: m["status"] for m in neg_ledger["levels"]["L3_milestones"]}
    assert neg_ms.get("M3", neg_ms.get("CHEM410_M3")) == "PENDING"
    assert neg_ms.get("M4", neg_ms.get("CHEM410_M4")) == "PENDING"
    assert "UNMANIFESTED_ZIP" not in neg_ms

    # CHEM311 M0-M5 directory + SPCAT M5 mapping (and plain .cat ZIP without handoff.json stays PENDING)
    w311 = tmp_path / "chem311_run"
    for folder, fname, content in (
        ("mod0", "env.txt", "ok\n"),
        ("mod1", "acetone.out", "ok\n"),
        ("mod2", "cis.out", "ok\n"),
        ("mod3", "crest_butane.out", "ok\n"),
        ("mod4", "pyscf.json", json.dumps({"ok": True})),
        ("mod5", "spcat_h2co.cat", " 10000.0\n"),
    ):
        (w311 / folder).mkdir(parents=True, exist_ok=True)
        (w311 / folder / fname).write_text(content, encoding="utf-8")
    l311 = fact_ledger.build_fact_ledger(
        artifact_paths=sorted(w311.rglob("*.*")),
        base_dir=w311,
        course_id="CHEM311",
    )
    p311 = {
        item["path"]: item["milestone"]
        for tier in ("L1_primary_artifacts", "L2_derived_artifacts")
        for item in l311["levels"][tier]
    }
    assert p311["mod0/env.txt"] in ("M0", "CHEM311_M0")
    assert p311["mod1/acetone.out"] in ("M1", "CHEM311_M1")
    assert p311["mod3/crest_butane.out"] in ("M3", "CHEM311_M3")
    assert p311["mod5/spcat_h2co.cat"] in ("M5", "CHEM311_M5")

    w311_neg = tmp_path / "chem311_neg"
    (w311_neg / "mod5").mkdir(parents=True)
    spcat_plain_zip = w311_neg / "spcat_unmanifested.zip"
    with zipfile.ZipFile(spcat_plain_zip, "w") as zf:
        zf.writestr("h2co.cat", " 10000.0\n")
    mod5_plain_zip = w311_neg / "mod5" / "results.zip"
    with zipfile.ZipFile(mod5_plain_zip, "w") as zf:
        zf.writestr("notes.txt", "unmanifested zip inside mod5")
    l311_neg = fact_ledger.build_fact_ledger(
        artifact_paths=[spcat_plain_zip, mod5_plain_zip],
        base_dir=w311_neg,
        course_id="CHEM311",
    )
    ms311_neg = {m["milestone"]: m["status"] for m in l311_neg["levels"]["L3_milestones"]}
    assert ms311_neg.get("M5", ms311_neg.get("CHEM311_M5")) == "PENDING"
    assert "UNMANIFESTED_ZIP" not in ms311_neg
