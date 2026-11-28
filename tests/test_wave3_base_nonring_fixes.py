"""Zero-mock regression tests for WAVE-3A CoChem-BASE non-hashring fixes.

Covers:
  1. ui/voila_layout/cochem_gui.py: dict execution_stack HTML formatting & 640px course dropdown
  2. student/handoff.py: --help subcommands, init-manifest, missing-manifest exit 2,
     student-side DLPNO_EXCLUDED firewall, and continuation_calc_kind alias validation
  3. student/conformers.py: dual positional/flag CLI, COCHEM_XTB_BIN/COCHEM_CREST_BIN/PATH
     resolution without COCHEM_FREE_ROOT, and COCHEM_AIMNET_PYTHON fallback resolution
  4. student/starter_inputs.py & student/bsse_counterpoise.py: starter XYZ materialization,
     fragment partitioning, and DLPNO rejection
  5. src/cochem_base/spectroscopy/isotopologue.py: <=1e-4 finite-difference Hessian
     symmetrization with metadata recording + >1e-4 fail-closed rejection
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ci_tools.source_quarantine import source_paths
from cochem_base.spectroscopy.isotopologue import (
    MAX_HESSIAN_SYMMETRY_TOLERANCE,
    IsotopologueSpectroscopyEngine,
)
from student import bsse_counterpoise, conformers, handoff, starter_inputs
from ui.voila_layout.cochem_gui import CoChemGUI


_DICT_CURE_PROVIDER = '''"""Test CoChem-CURE provider returning dict execution_stack matching live profiles."""
from __future__ import annotations

SCHEMA_VERSION = "cochem.course-provider/1"

_PROFILE = {
    "course_id": "CHEM490",
    "aliases": ["CHEM 490"],
    "title": "Directed Research in Computational Chemistry (CHEM 490)",
    "institution": "Cumberland University",
    "summary": "Local WSL2 revDSD + VPT2 and canonical CCSD(T) workstation handoff.",
    "execution_stack": {
        "primary": "Local WSL2 Ubuntu",
        "activation_command": "source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh",
        "submission_surface": "Canvas + cochem_workstation_job_runner",
        "auditing_model": "CoChem-ORACLE (zero-LLM Student Data Auditing Model)",
        "local_vpt2_routes": {
            "orca_version": "6.1.1",
            "double_hybrid_keyword": "revDSD-PBEP86-D4/2021",
        },
    },
    "milestones": [{"id": "M1", "title": "Setup", "summary": "Verify local engines."}],
    "modules": [{"id": "W1", "title": "Health Check"}],
    "guide_markdown": "# CHEM 490",
}


def get_allowed_course_ids():
    return ("CHEM490",)


def validate_course_id(cid):
    return "CHEM490"


def list_courses():
    return [dict(_PROFILE)]


def get_course_profile(cid):
    return dict(_PROFILE)


def get_course_milestones(cid):
    return list(_PROFILE["milestones"])


def get_course_pathway(cid):
    return {
        "course_id": "CHEM490",
        "profile": dict(_PROFILE),
        "modules": list(_PROFILE["modules"]),
        "milestones": list(_PROFILE["milestones"]),
        "guide_markdown": _PROFILE["guide_markdown"],
    }
'''


# ---------------------------------------------------------------------------
# 1. Voilà GUI: dict execution_stack HTML formatting & 640px course dropdown
# ---------------------------------------------------------------------------


def test_gui_format_cure_pathway_html_handles_dict_and_escapes_html() -> None:
    stack = {
        "primary": "Local WSL2 Ubuntu",
        "activation_command": "source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh",
        "submission_surface": "Canvas <bundle & PDF>",
        "auditing_model": "CoChem-ORACLE",
        "wet_lab_conventions": {
            "instrument": "Nicolet iS50 diamond ATR-FTIR",
            "resolution_cm1": 0.5,
        },
    }
    rendered = CoChemGUI._format_cure_pathway_html(stack)
    assert "{'primary'" not in rendered
    assert "<b>Primary:</b> Local WSL2 Ubuntu" in rendered
    assert "<code>source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh</code>" in rendered
    assert "Canvas &lt;bundle &amp; PDF&gt;" in rendered
    assert "<bundle" not in rendered
    assert "<b>Wet-lab conventions:</b>" in rendered
    assert "Nicolet iS50 diamond ATR-FTIR" in rendered

    # Plain string and None remain cleanly formatted
    plain = CoChemGUI._format_cure_pathway_html("Local WSL2 & PySCF")
    assert "Local WSL2 &amp; PySCF" in plain
    fallback = CoChemGUI._format_cure_pathway_html(None)
    assert "activate_cochem_wsl.sh" in fallback


def test_gui_course_selector_width_and_dict_execution_stack_rendering(tmp_path: Path) -> None:
    cure_pkg = tmp_path / "cure_src" / "cochem_cure"
    cure_pkg.mkdir(parents=True)
    (cure_pkg / "__init__.py").write_text("from cochem_cure import provider\n", encoding="utf-8")
    (cure_pkg / "provider.py").write_text(_DICT_CURE_PROVIDER, encoding="utf-8")

    probe = (
        "from ui.voila_layout.cochem_gui import CoChemGUI\n"
        "gui = CoChemGUI()\n"
        "for w in ('_student_setup_initial_worker', '_research_capability_worker'):\n"
        "    t = getattr(gui, w, None)\n"
        "    if t is not None:\n"
        "        t.join(timeout=15)\n"
        "assert gui.cure_course_selector.layout.width == '640px', gui.cure_course_selector.layout.width\n"
        "assert gui.cure_course_selector.layout.max_width == '100%'\n"
        "gui.course_mode_selector.value = 'course'\n"
        "html_out = gui.cure_pathway_status.value\n"
        "assert \"{'primary'\" not in html_out, html_out\n"
        "assert '<b>Primary:</b> Local WSL2 Ubuntu' in html_out, html_out\n"
        "assert '<code>source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh</code>' in html_out, html_out\n"
        "assert 'revDSD-PBEP86-D4/2021' in html_out, html_out\n"
        "print('GUI_CURE_DICT_OK')\n"
    )
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join([str(tmp_path / "cure_src"), *source_paths(REPO_ROOT)]),
        PYTHONDONTWRITEBYTECODE="1",
        COCHEM_ARTIFACT_DIR=str(tmp_path / "artifacts"),
        COCHEM_CONFIG=str(tmp_path / "absent.json"),
        COCHEM_STUDENT_AUTO_SETUP="0",
        COCHEM_STUDENT_AUTO_REMOTE_CHECK="0",
    )
    proc = subprocess.run(
        [sys.executable, "-B", "-c", probe],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "GUI_CURE_DICT_OK" in proc.stdout


# ---------------------------------------------------------------------------
# 2. student/handoff.py: --help, init-manifest, missing manifest, DLPNO, calc_kind
# ---------------------------------------------------------------------------


def test_handoff_help_init_manifest_missing_manifest_and_roundtrip(tmp_path: Path) -> None:
    handoff_py = str(REPO_ROOT / "student" / "handoff.py")

    # --help clearly documents seal, init-manifest, and verify
    help_proc = subprocess.run(
        [sys.executable, "-B", handoff_py, "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert help_proc.returncode == 0, help_proc.stderr
    assert "seal" in help_proc.stdout
    assert "init-manifest" in help_proc.stdout
    assert "verify" in help_proc.stdout

    # Missing --manifest exits 2 cleanly with zero Python traceback
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    missing_proc = subprocess.run(
        [
            sys.executable,
            "-B",
            handoff_py,
            "seal",
            "--source-dir",
            str(work_dir),
            "--manifest",
            str(tmp_path / "does_not_exist.json"),
            "--output",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert missing_proc.returncode == 2
    assert "Traceback" not in missing_proc.stderr
    err_payload = json.loads(missing_proc.stderr)
    assert err_payload["ok"] is False
    assert err_payload["code"] == "MANIFEST_MISSING"
    assert "init-manifest" in err_payload["reason"]

    # init-manifest generates a valid CHEM311 manifest with dft_opt_freq alias normalized -> opt_freq
    manifest_path = tmp_path / "chem311_manifest.json"
    init_proc = subprocess.run(
        [
            sys.executable,
            "-B",
            handoff_py,
            "init-manifest",
            "--course-id",
            "CHEM311",
            "--input-name",
            "h2co_start.xyz",
            "--continuation-calc-kind",
            "dft_opt_freq",
            "--output",
            str(manifest_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert init_proc.returncode == 0, init_proc.stderr
    init_out = json.loads(init_proc.stdout)
    assert init_out["ok"] is True
    assert init_out["course_id"] == "CHEM311"
    saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved_manifest["continuation_calc_kind"] == "opt_freq"

    # Seal + verify end-to-end with materialized H2CO geometry
    h2co_text = starter_inputs.get_starter_xyz_text("h2co_start.xyz")
    (work_dir / "input.xyz").write_text(h2co_text, encoding="utf-8", newline="\n")
    (work_dir / "refined.xyz").write_text(h2co_text, encoding="utf-8", newline="\n")

    out_dir = tmp_path / "sealed"
    seal_proc = subprocess.run(
        [
            sys.executable,
            "-B",
            handoff_py,
            "seal",
            "--source-dir",
            str(work_dir),
            "--manifest",
            str(manifest_path),
            "--output",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert seal_proc.returncode == 0, seal_proc.stderr
    seal_res = json.loads(seal_proc.stdout)
    assert seal_res["ok"] is True

    # Verify via direct positional shorthand AND explicit verify subcommand
    for argv_prefix in ([], ["verify"]):
        ver_proc = subprocess.run(
            [
                sys.executable,
                "-B",
                handoff_py,
                *argv_prefix,
                seal_res["zip_path"],
                "--sidecar",
                seal_res["sha256_path"],
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert ver_proc.returncode == 0, ver_proc.stderr
        ver_data = json.loads(ver_proc.stdout)
        assert ver_data["course_id"] == "CHEM311"
        assert ver_data["continuation_calc_kind"] == "opt_freq"


def test_handoff_student_side_dlpno_exclusion_and_continuation_calc_kind(tmp_path: Path) -> None:
    handoff_py = str(REPO_ROOT / "student" / "handoff.py")
    h2co_text = starter_inputs.get_starter_xyz_text("h2co_start.xyz")

    # Supported continuation_calc_kind aliases normalize in lockstep with job_runner
    expected_aliases = {
        "opt_freq": "opt_freq",
        "dft_opt_freq": "opt_freq",
        "single_point": "sp",
        "dft_sp": "sp",
        "ts_opt": "ts_opt",
        "revdsd": "revdsd",
        "revdsd_opt_freq": "revdsd",
        "ccsd": "ccsd",
        "ccsd_t": "ccsd_t",
        "ccsd(t)": "ccsd_t",
    }
    for raw_kind, canonical in expected_aliases.items():
        assert handoff.normalize_continuation_calc_kind(raw_kind) == canonical

    with pytest.raises(handoff.HandoffValidationError) as bad_kind:
        handoff.normalize_continuation_calc_kind("not_a_real_calc_kind")
    assert bad_kind.value.code == "SCHEMA_INVALID"

    with pytest.raises(handoff.HandoffValidationError) as dlpno_kind:
        handoff.normalize_continuation_calc_kind("dlpno_ccsdt")
    assert dlpno_kind.value.code == "DLPNO_EXCLUDED"

    # Case A: DLPNO in manifest method fails fast with exit 2 and DLPNO_EXCLUDED
    src_a = tmp_path / "src_a"
    src_a.mkdir()
    (src_a / "input.xyz").write_text(h2co_text, encoding="utf-8")
    (src_a / "refined.xyz").write_text(h2co_text, encoding="utf-8")
    bad_manifest = handoff.build_starter_manifest("CHEM490", method="B3LYP-D3BJ")
    bad_manifest["method"] = "DLPNO-CCSD(T)"
    m_a = tmp_path / "bad_method.json"
    m_a.write_text(json.dumps(bad_manifest), encoding="utf-8")
    out_a = tmp_path / "out_a"
    proc_a = subprocess.run(
        [sys.executable, "-B", handoff_py, "seal", "--source-dir", str(src_a), "--manifest", str(m_a), "--output", str(out_a)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert proc_a.returncode == 2
    assert json.loads(proc_a.stderr)["code"] == "DLPNO_EXCLUDED"
    assert not list(out_a.glob("*.zip"))

    # Case B: DLPNO inside bundled ORCA .inp file fails fast with exit 2 and DLPNO_EXCLUDED
    src_b = tmp_path / "src_b"
    src_b.mkdir()
    (src_b / "input.xyz").write_text(h2co_text, encoding="utf-8")
    (src_b / "refined.xyz").write_text(h2co_text, encoding="utf-8")
    (src_b / "job.inp").write_text("! DLPNO-CCSD(T) def2-TZVP def2-TZVP/C TightSCF\n", encoding="utf-8")
    ok_manifest = handoff.build_starter_manifest("CHEM490", method="CCSD(T)", continuation_calc_kind="ccsd_t")
    m_b = tmp_path / "ok_manifest.json"
    m_b.write_text(json.dumps(ok_manifest), encoding="utf-8")
    out_b = tmp_path / "out_b"
    proc_b = subprocess.run(
        [sys.executable, "-B", handoff_py, "seal", "--source-dir", str(src_b), "--manifest", str(m_b), "--output", str(out_b)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert proc_b.returncode == 2
    assert json.loads(proc_b.stderr)["code"] == "DLPNO_EXCLUDED"
    assert not list(out_b.glob("*.zip"))


# ---------------------------------------------------------------------------
# 3. student/conformers.py: dual CLI, binary resolution without COCHEM_FREE_ROOT, AIMNet fallback
# ---------------------------------------------------------------------------


def test_conformers_dual_cli_and_wsl2_binary_resolution(tmp_path: Path) -> None:
    parser = conformers.build_arg_parser()

    # Legacy positional mode
    ns_pos = parser.parse_args(["ethanol.xyz", str(tmp_path / "w"), str(tmp_path / "o")])
    assert conformers.resolve_cli_paths(ns_pos) == ("ethanol.xyz", tmp_path / "w", tmp_path / "o")

    # Flag mode (--xyz / --output-dir with automatic _work default)
    ns_flag = parser.parse_args(
        [
            "--xyz",
            "examples/student_inputs/hcooh_start.xyz",
            "--output-dir",
            str(tmp_path / "m1_hcooh"),
            "--frequencies",
            "--course-id",
            "CHEM312",
        ]
    )
    fn, wk, out = conformers.resolve_cli_paths(ns_flag)
    assert fn == "examples/student_inputs/hcooh_start.xyz"
    assert wk == tmp_path / "m1_hcooh" / "_work"
    assert out == tmp_path / "m1_hcooh"

    # Explicit --work-dir
    ns_flag2 = parser.parse_args(
        ["--xyz", "hcooh_start.xyz", "--work-dir", str(tmp_path / "custom_w"), "--output-dir", str(tmp_path / "o2")]
    )
    assert conformers.resolve_cli_paths(ns_flag2) == ("hcooh_start.xyz", tmp_path / "custom_w", tmp_path / "o2")

    # Binary resolution WITHOUT COCHEM_FREE_ROOT via COCHEM_XTB_BIN / COCHEM_CREST_BIN
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    xtb_exe = bin_dir / ("xtb.cmd" if os.name == "nt" else "xtb")
    crest_exe = bin_dir / ("crest.cmd" if os.name == "nt" else "crest")
    xtb_exe.write_text("@echo off\n" if os.name == "nt" else "#!/bin/sh\n", encoding="utf-8")
    crest_exe.write_text("@echo off\n" if os.name == "nt" else "#!/bin/sh\n", encoding="utf-8")
    if os.name != "nt":
        xtb_exe.chmod(xtb_exe.stat().st_mode | stat.S_IXUSR)
        crest_exe.chmod(crest_exe.stat().st_mode | stat.S_IXUSR)

    resolved_env = conformers.resolve_xtb_crest_binaries(
        {"COCHEM_XTB_BIN": str(xtb_exe), "COCHEM_CREST_BIN": str(crest_exe), "PATH": ""}
    )
    assert resolved_env["xtb"] == str(xtb_exe)
    assert resolved_env["crest"] == str(crest_exe)
    assert resolved_env["free_root"] is None

    # Missing binaries raise clear RuntimeError, NEVER KeyError: 'COCHEM_FREE_ROOT'
    with pytest.raises(RuntimeError, match="Unable to locate `xtb`"):
        conformers.resolve_xtb_crest_binaries({"PATH": str(tmp_path / "empty_dir")})

    # COCHEM_AIMNET_PYTHON resolution
    assert conformers.resolve_aimnet_python({"COCHEM_AIMNET_PYTHON": sys.executable}) == sys.executable
    assert conformers.resolve_aimnet_python({}) is None

    # Starter input auto-materialization stays strictly inside materialize_dir
    mat_path = conformers.input_file("examples/student_inputs/hcooh_start.xyz", materialize_dir=tmp_path / "mat")
    assert mat_path.parent == (tmp_path / "mat").resolve()
    parsed = handoff.read_input(mat_path)
    assert parsed["formula"] == "CH2O2"
    assert not (REPO_ROOT / "examples" / "student_inputs" / "hcooh_start.xyz").exists()


# ---------------------------------------------------------------------------
# 4. student/starter_inputs.py & student/bsse_counterpoise.py
# ---------------------------------------------------------------------------


def test_starter_inputs_cli_and_bsse_partitioning(tmp_path: Path) -> None:
    starter_py = str(REPO_ROOT / "student" / "starter_inputs.py")
    list_proc = subprocess.run(
        [sys.executable, "-B", starter_py, "--list", "--json"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert list_proc.returncode == 0, list_proc.stderr
    listed = json.loads(list_proc.stdout)["starter_inputs"]
    names = {item["filename"] for item in listed}
    assert names == {"hcooh_start.xyz", "hcooh_water_dimer.xyz", "ethanol_start.xyz", "h2co_start.xyz"}

    out_dir = tmp_path / "starters"
    write_proc = subprocess.run(
        [sys.executable, "-B", starter_py, "--write-dir", str(out_dir), "--json"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert write_proc.returncode == 0, write_proc.stderr
    expected_formulas = {
        "hcooh_start.xyz": "CH2O2",
        "hcooh_water_dimer.xyz": "CH4O3",
        "ethanol_start.xyz": "C2H6O",
        "h2co_start.xyz": "CH2O",
    }
    for fname, formula in expected_formulas.items():
        path = out_dir / fname
        assert path.is_file()
        assert b"\r\n" not in path.read_bytes()
        parsed = handoff.read_input(path, charge=0, multiplicity=1)
        assert parsed["formula"] == formula

    # BSSE CLI --help and fragment partition validation
    bsse_py = str(REPO_ROOT / "student" / "bsse_counterpoise.py")
    help_proc = subprocess.run(
        [sys.executable, "-B", bsse_py, "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert help_proc.returncode == 0, help_proc.stderr
    assert "--dimer-xyz" in help_proc.stdout
    assert "--frag-a-atoms" in help_proc.stdout
    assert "--frag-b-atoms" in help_proc.stdout

    assert bsse_counterpoise.resolve_fragment_partition(8, frag_a_atoms="1-5", frag_b_atoms="6-8") == (
        [0, 1, 2, 3, 4],
        [5, 6, 7],
    )
    assert bsse_counterpoise.resolve_fragment_partition(8, frag_a_atoms="1-5") == ([0, 1, 2, 3, 4], [5, 6, 7])
    assert bsse_counterpoise.resolve_fragment_partition(6, monomer_a_atoms=3) == ([0, 1, 2], [3, 4, 5])
    with pytest.raises(ValueError, match="overlap"):
        bsse_counterpoise.resolve_fragment_partition(8, frag_a_atoms="1-5", frag_b_atoms="5-8")
    with pytest.raises(ValueError, match="cover all 8 atoms"):
        bsse_counterpoise.resolve_fragment_partition(8, frag_a_atoms="1-4", frag_b_atoms="6-8")
    with pytest.raises(ValueError, match="DLPNO_EXCLUDED"):
        bsse_counterpoise.normalize_bsse_method_and_basis("DLPNO-CCSD(T)", "def2-TZVP")


# ---------------------------------------------------------------------------
# 5. IsotopologueSpectroscopyEngine finite-difference Hessian symmetrization
# ---------------------------------------------------------------------------


def _water_valence_hessian() -> tuple[list[str], np.ndarray, np.ndarray]:
    from ase.units import Bohr

    r0 = 0.9572
    half_angle = np.deg2rad(104.52 / 2.0)
    coords = np.array(
        [
            [0.0, 0.0, 0.0],
            [0.0, r0 * np.sin(half_angle), r0 * np.cos(half_angle)],
            [0.0, -r0 * np.sin(half_angle), r0 * np.cos(half_angle)],
        ],
        dtype=np.float64,
    )
    r0_bohr = r0 / Bohr
    theta0 = np.deg2rad(104.52)

    def _energy(xyz_ang: np.ndarray) -> float:
        c_b = xyz_ang / Bohr
        v1 = c_b[1] - c_b[0]
        v2 = c_b[2] - c_b[0]
        r1 = float(np.linalg.norm(v1))
        r2 = float(np.linalg.norm(v2))
        th = float(np.arccos(np.clip(np.dot(v1, v2) / (r1 * r2), -1.0, 1.0)))
        return 0.5 * 0.54 * ((r1 - r0_bohr) ** 2 + (r2 - r0_bohr) ** 2) + 0.5 * 0.16 * ((th - theta0) ** 2)

    step_b = 1e-4
    step_a = step_b * Bohr
    flat = coords.reshape(-1)
    hess = np.empty((9, 9), dtype=np.float64)
    for i in range(9):
        for j in range(i, 9):
            pp = flat.copy(); pp[i] += step_a; pp[j] += step_a
            pm = flat.copy(); pm[i] += step_a; pm[j] -= step_a
            mp = flat.copy(); mp[i] -= step_a; mp[j] += step_a
            mm = flat.copy(); mm[i] -= step_a; mm[j] -= step_a
            val = (
                _energy(pp.reshape(3, 3))
                - _energy(pm.reshape(3, 3))
                - _energy(mp.reshape(3, 3))
                + _energy(mm.reshape(3, 3))
            ) / (4.0 * step_b * step_b)
            hess[i, j] = val
            hess[j, i] = val
    return ["O", "H", "H"], coords, hess


def test_isotopologue_symmetrizes_tiny_fd_noise_and_rejects_large_asymmetry() -> None:
    symbols, coords, sym_hess = _water_valence_hessian()

    # Exact symmetric baseline
    base_engine = IsotopologueSpectroscopyEngine(symbols, coords, sym_hess)
    base_res = base_engine.compute_observables()
    assert base_engine.hessian_max_asymmetry == pytest.approx(0.0)
    assert base_engine.hessian_symmetrized is False
    assert base_res.hessian_max_asymmetry == pytest.approx(0.0)
    assert base_res.geometry_qualification["hessian_max_asymmetry"] == pytest.approx(0.0)

    # Tiny finite-difference asymmetry (2.02e-5 <= 1e-4 Eh/bohr^2, matching PySCF D3BJ FD noise)
    noisy_hess = sym_hess.copy()
    noisy_hess[0, 3] += 2.02e-5
    noisy_engine = IsotopologueSpectroscopyEngine(symbols, coords, noisy_hess)
    assert noisy_engine.hessian_symmetrized is True
    assert noisy_engine.hessian_max_asymmetry == pytest.approx(2.02e-5, rel=1e-6)
    assert np.allclose(noisy_engine.cartesian_hessian, noisy_engine.cartesian_hessian.T, atol=0.0)
    noisy_res = noisy_engine.compute_observables()
    assert noisy_res.hessian_max_asymmetry == pytest.approx(2.02e-5, rel=1e-6)
    assert noisy_res.geometry_qualification["hessian_max_asymmetry"] == pytest.approx(2.02e-5, rel=1e-6)
    assert noisy_res.geometry_qualification["hessian_symmetrized"] is True
    assert len(noisy_res.harmonic_frequencies_cm1) == 3
    np.testing.assert_allclose(noisy_res.harmonic_frequencies_cm1, base_res.harmonic_frequencies_cm1, rtol=1e-3)

    # Genuinely non-symmetric Hessian (> 1e-4 Eh/bohr^2) remains strictly rejected fail-closed
    bad_hess = sym_hess.copy()
    bad_hess[0, 3] += MAX_HESSIAN_SYMMETRY_TOLERANCE * 2.5
    with pytest.raises(ValueError, match="Cartesian Hessian must be symmetric"):
        IsotopologueSpectroscopyEngine(symbols, coords, bad_hess)
