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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    monkeypatch.delenv("COCHEM_FREE_ROOT", raising=False)
    monkeypatch.setenv("COCHEM_XTB_BIN", str(xtb_bin))
    monkeypatch.setenv("COCHEM_CREST_BIN", str(crest_bin))
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
    monkeypatch.setenv("COCHEM_FREE_ROOT", str(free_root))
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        conformers._resolve_free_engines(tmp_path / "payload_bad")


def test_gui_chem312_blocks_orca_and_renders_clean_pathway_html(tmp_path: Path) -> None:
    """FRICTION-312-01 & FRIC-01/02: CHEM312 course mode hides ORCA even with audited Golden Registry."""
    cure_root = REPO_ROOT.parent / "CoChem-CURE"
    if not cure_root.is_dir():
        pytest.skip("CoChem-CURE sibling checkout required")

    # Build a real signed Golden Registry containing an executable binary recorded under 'orca'
    fake_orca = tmp_path / ("orca.exe" if os.name == "nt" else "orca")
    fake_orca.write_bytes(b"#!/bin/sh\necho fake\n")
    if os.name != "nt":
        fake_orca.chmod(0o755)
    digest = hashlib.sha256(fake_orca.read_bytes()).hexdigest()

    script = f"""
import os, sys
from pathlib import Path
from cochem_base.cochem_core_registry_schema import CoChemSystemConfig, EngineInfo
from cochem_base.core.cochem_core_registry_manager import save_system_config
from ui.voila_layout.cochem_gui import CoChemGUI

reg_path = Path({str(tmp_path / 'registry.json')!r})
cfg = CoChemSystemConfig.create_default(auto_detect_hardware=True)
cfg.engines = {{"orca": EngineInfo(status="found", path={str(fake_orca.resolve())!r}, hash={digest!r})}}
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
