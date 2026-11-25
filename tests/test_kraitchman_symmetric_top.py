"""Zero-mock regression tests for Series B fixes SB490B-01 and SB490B-02.

- SB490B-01: scripts/install_optional_spyfy.sh installs scikit-learn and verifies
  both ``cochem-spyfy info --check-compat`` and ``cochem_spyfy.instruments.DEFAULT_INSTRUMENT_PROFILE``.
- SB490B-02: scripts/kraitchman_rs.py implements exact Kraitchman (1953) symmetric-top
  equations for oblate (NH3 -> NH2D, NH3 -> 15NH3) and prolate (CH3F -> CH2DF, CH3F -> 13CH3F)
  symmetric tops, plus real experimental NH3 -> NH2D, Costain imaginary handling, and
  100% backward compatibility with asymmetric-top (H2O -> HDO) and planar (H2CO -> HDCO) modes.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from scripts import kraitchman_rs

REPO_ROOT = Path(__file__).resolve().parents[1]


def _rigid_rotor_abc_and_pas(
    masses: np.ndarray,
    coords: np.ndarray,
) -> tuple[tuple[float, float, float], np.ndarray]:
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


def _nh3_rigid_geometry() -> tuple[np.ndarray, np.ndarray]:
    """Return exact C3v rigid-rotor NH3 masses (amu) and coordinates (Angstrom)."""
    r_nh = 1.0124
    theta = math.radians(106.67)
    sin_a = math.sqrt((1.0 - math.cos(theta)) / 1.5)
    cos_a = math.sqrt(1.0 - sin_a * sin_a)
    rho_h = r_nh * sin_a
    z_h = -r_nh * cos_a
    coords = np.array(
        [
            [0.0, 0.0, 0.0],
            [rho_h, 0.0, z_h],
            [-0.5 * rho_h, 0.5 * math.sqrt(3.0) * rho_h, z_h],
            [-0.5 * rho_h, -0.5 * math.sqrt(3.0) * rho_h, z_h],
        ],
        dtype=np.float64,
    )
    masses = np.array([14.00307400443, 1.00782503223, 1.00782503223, 1.00782503223], dtype=np.float64)
    return masses, coords


def _ch3f_rigid_geometry() -> tuple[np.ndarray, np.ndarray]:
    """Return exact C3v rigid-rotor CH3F masses (amu) and coordinates (Angstrom)."""
    r_cf = 1.383
    r_ch = 1.095
    ang_hcf = math.radians(108.9)
    rho_h = r_ch * math.sin(ang_hcf)
    z_h = r_ch * math.cos(ang_hcf)
    coords = np.array(
        [
            [0.0, 0.0, 0.0],
            [0.0, 0.0, r_cf],
            [rho_h, 0.0, z_h],
            [-0.5 * rho_h, 0.5 * math.sqrt(3.0) * rho_h, z_h],
            [-0.5 * rho_h, -0.5 * math.sqrt(3.0) * rho_h, z_h],
        ],
        dtype=np.float64,
    )
    masses = np.array([12.0, 18.99840316273, 1.00782503223, 1.00782503223, 1.00782503223], dtype=np.float64)
    return masses, coords


# ---------------------------------------------------------------------------
# 1. SB490B-02: Exact Rigid-Rotor Oblate Symmetric Top (NH3 -> NH2D, NH3 -> 15NH3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["auto", "symmetric", "nonplanar"])
def test_kraitchman_oblate_rigid_nh3_to_nh2d_exact_recovery(mode: str) -> None:
    """Recover exact |z_s| and rho_s of off-axis H in oblate NH3 -> NH2D to < 1e-10 A."""
    masses, coords = _nh3_rigid_geometry()
    abc0, pas0 = _rigid_rotor_abc_and_pas(masses, coords)
    dm = 1.00627674587  # H -> D
    masses_iso = masses.copy()
    masses_iso[1] += dm
    abc1, _ = _rigid_rotor_abc_and_pas(masses_iso, coords)

    true_z = abs(float(pas0[1, 2]))
    true_rho = math.hypot(float(pas0[1, 0]), float(pas0[1, 1]))
    true_r = math.hypot(true_z, true_rho)

    res = kraitchman_rs.compute_kraitchman_rs(
        parent_abc_mhz=abc0,
        iso_abc_mhz=abc1,
        delta_mass_amu=dm,
        parent_mass_amu=float(np.sum(masses)),
        mode=mode,
        label="NH3_to_NH2D_rigid",
        course_id="CHEM490",
    )
    assert res["mode_used"] == "symmetric_oblate"
    assert res["effective_mode"] == "symmetric_oblate"
    assert res["symmetry_axis"] == "c"
    assert res["any_imaginary_coordinate"] is False
    assert res["abs_z_s_angstrom"] == pytest.approx(true_z, abs=1e-10)
    assert res["rho_s_angstrom"] == pytest.approx(true_rho, abs=1e-10)
    assert res["r_com_angstrom"] == pytest.approx(true_r, abs=1e-10)
    assert res["distance_from_com_angstrom"] == pytest.approx(true_r, abs=1e-10)
    assert res["z_s_costain_uncertainty_angstrom"] == pytest.approx(0.0015 / true_z, rel=1e-9)
    assert res["rho_s_costain_uncertainty_angstrom"] == pytest.approx(0.0015 / true_rho, rel=1e-9)


def test_kraitchman_oblate_on_axis_nh3_to_15nh3_zero_rho() -> None:
    """Recover exact |z_s| and rho_s == 0 for on-axis substitution NH3 -> 15NH3."""
    masses, coords = _nh3_rigid_geometry()
    abc0, pas0 = _rigid_rotor_abc_and_pas(masses, coords)
    dm = 0.997034893  # 14N -> 15N
    masses_iso = masses.copy()
    masses_iso[0] += dm
    abc1, _ = _rigid_rotor_abc_and_pas(masses_iso, coords)

    true_z = abs(float(pas0[0, 2]))
    res = kraitchman_rs.compute_kraitchman_rs(
        parent_abc_mhz=abc0,
        iso_abc_mhz=abc1,
        delta_mass_amu=dm,
        parent_mass_amu=float(np.sum(masses)),
        mode="auto",
        label="NH3_to_15NH3_on_axis",
        course_id="CHEM490",
    )
    assert res["mode_used"] == "symmetric_oblate"
    assert res["symmetry_axis"] == "c"
    assert res["any_imaginary_coordinate"] is False
    assert res["abs_z_s_angstrom"] == pytest.approx(true_z, abs=1e-10)
    assert res["rho_s_angstrom"] == pytest.approx(0.0, abs=1e-10)
    assert res["r_com_angstrom"] == pytest.approx(true_z, abs=1e-10)
    assert res["rho_s_costain_uncertainty_angstrom"] is None


# ---------------------------------------------------------------------------
# 2. SB490B-02: Exact Rigid-Rotor Prolate Symmetric Top (CH3F -> CH2DF, 13CH3F)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["auto", "symmetric", "nonplanar"])
def test_kraitchman_prolate_rigid_ch3f_to_ch2df_exact_recovery(mode: str) -> None:
    """Recover exact |z_s| and rho_s of off-axis H in prolate CH3F -> CH2DF to < 1e-10 A."""
    masses, coords = _ch3f_rigid_geometry()
    abc0, pas0 = _rigid_rotor_abc_and_pas(masses, coords)
    dm = 1.00627674587  # H -> D
    masses_iso = masses.copy()
    masses_iso[2] += dm
    abc1, _ = _rigid_rotor_abc_and_pas(masses_iso, coords)

    true_z = abs(float(pas0[2, 0]))
    true_rho = math.hypot(float(pas0[2, 1]), float(pas0[2, 2]))
    true_r = math.hypot(true_z, true_rho)

    res = kraitchman_rs.compute_kraitchman_rs(
        parent_abc_mhz=abc0,
        iso_abc_mhz=abc1,
        delta_mass_amu=dm,
        parent_mass_amu=float(np.sum(masses)),
        mode=mode,
        label="CH3F_to_CH2DF_rigid",
        course_id="CHEM490",
    )
    assert res["mode_used"] == "symmetric_prolate"
    assert res["effective_mode"] == "symmetric_prolate"
    assert res["symmetry_axis"] == "a"
    assert res["any_imaginary_coordinate"] is False
    assert res["abs_z_s_angstrom"] == pytest.approx(true_z, abs=1e-10)
    assert res["rho_s_angstrom"] == pytest.approx(true_rho, abs=1e-10)
    assert res["r_com_angstrom"] == pytest.approx(true_r, abs=1e-10)
    assert res["z_s_costain_uncertainty_angstrom"] == pytest.approx(0.0015 / true_z, rel=1e-9)
    assert res["rho_s_costain_uncertainty_angstrom"] == pytest.approx(0.0015 / true_rho, rel=1e-9)


def test_kraitchman_prolate_on_axis_and_negative_delta_mass() -> None:
    """Verify prolate on-axis substitution (CH3F -> 13CH3F) and negative Delta_m (CD3F -> CD2HF)."""
    masses, coords = _ch3f_rigid_geometry()
    abc0, pas0 = _rigid_rotor_abc_and_pas(masses, coords)

    # On-axis 12C -> 13C
    dm_c = 1.00335483507
    masses_c13 = masses.copy()
    masses_c13[0] += dm_c
    abc1_c13, _ = _rigid_rotor_abc_and_pas(masses_c13, coords)
    res_c13 = kraitchman_rs.compute_kraitchman_rs(
        parent_abc_mhz=abc0,
        iso_abc_mhz=abc1_c13,
        delta_mass_amu=dm_c,
        parent_mass_amu=float(np.sum(masses)),
        mode="symmetric",
    )
    assert res_c13["mode_used"] == "symmetric_prolate"
    assert res_c13["abs_z_s_angstrom"] == pytest.approx(abs(float(pas0[0, 0])), abs=1e-10)
    assert res_c13["rho_s_angstrom"] == pytest.approx(0.0, abs=1e-10)

    # Lighter isotope (Delta_m < 0): CD3F -> CD2HF
    masses_cd3f = np.array([12.0, 18.99840316273, 2.0141017781, 2.0141017781, 2.0141017781], dtype=np.float64)
    abc0_d, pas0_d = _rigid_rotor_abc_and_pas(masses_cd3f, coords)
    dm_dh = -1.00627674587
    masses_cd2hf = masses_cd3f.copy()
    masses_cd2hf[2] += dm_dh
    abc1_d, _ = _rigid_rotor_abc_and_pas(masses_cd2hf, coords)
    res_dh = kraitchman_rs.compute_kraitchman_rs(
        parent_abc_mhz=abc0_d,
        iso_abc_mhz=abc1_d,
        delta_mass_amu=dm_dh,
        parent_mass_amu=float(np.sum(masses_cd3f)),
        mode="auto",
    )
    assert res_dh["mode_used"] == "symmetric_prolate"
    assert res_dh["abs_z_s_angstrom"] == pytest.approx(abs(float(pas0_d[2, 0])), abs=1e-10)
    assert res_dh["rho_s_angstrom"] == pytest.approx(math.hypot(float(pas0_d[2, 1]), float(pas0_d[2, 2])), abs=1e-10)


# ---------------------------------------------------------------------------
# 3. SB490B-02: Real Experimental NH3 -> NH2D CLI + Imaginary & Error Handling
# ---------------------------------------------------------------------------


def test_kraitchman_real_experimental_nh3_to_nh2d_cli(tmp_path: Path) -> None:
    """Verify CLI on real experimental oblate NH3 -> NH2D (Series B QA regression)."""
    out_json = tmp_path / "nh3_nh2d.json"
    out_md = tmp_path / "nh3_nh2d.md"
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(REPO_ROOT / "scripts" / "kraitchman_rs.py"),
            "--course-id",
            "CHEM490",
            "--parent-abc",
            "298117.0",
            "298117.0",
            "186726.0",
            "--iso-abc",
            "290364.0",
            "192318.0",
            "140903.0",
            "--parent-mass-amu",
            "17.026549",
            "--delta-mass-amu",
            "1.006277",
            "--label",
            "NH3_to_NH2D",
            "--output-json",
            str(out_json),
            "--output-md",
            str(out_md),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert proc.returncode == 0, f"CLI failed on experimental NH3 -> NH2D:\n{proc.stderr}"
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["course_id"] == "CHEM490"
    assert payload["mode_used"] == "symmetric_oblate"
    assert payload["effective_mode"] == "symmetric_oblate"
    assert payload["symmetry_axis"] == "c"
    assert payload["any_imaginary_coordinate"] is False
    # Real NH3 H coordinates relative to COM: |z_s| ~ 0.31 A, rho_s ~ 0.94 A, r_COM ~ 0.99 A
    assert 0.25 < payload["abs_z_s_angstrom"] < 0.42
    assert 0.90 < payload["rho_s_angstrom"] < 0.98
    assert 0.95 < payload["r_com_angstrom"] < 1.03
    assert payload["z_s_costain_uncertainty_angstrom"] == pytest.approx(
        0.0015 / payload["abs_z_s_angstrom"], rel=1e-9
    )
    assert payload["rho_s_costain_uncertainty_angstrom"] == pytest.approx(
        0.0015 / payload["rho_s_angstrom"], rel=1e-9
    )

    md_text = out_md.read_text(encoding="utf-8")
    assert "# CHEM490 Kraitchman Single-Substitution Coordinates" in md_text
    assert "symmetric_oblate" in md_text
    assert "Symmetry Axis:** `c`" in md_text


def test_kraitchman_symmetric_imaginary_and_backward_compatibility() -> None:
    """Verify honest Costain imaginary handling in symmetric mode and asymmetric/planar compatibility."""
    # Imaginary rho_s^2 when vibrational perturbation pushes Delta_P_x < 0 on an on-axis atom
    masses, coords = _nh3_rigid_geometry()
    abc0, _ = _rigid_rotor_abc_and_pas(masses, coords)
    dm = 0.997034893
    masses_iso = masses.copy()
    masses_iso[0] += dm
    abc1, _ = _rigid_rotor_abc_and_pas(masses_iso, coords)
    # Increase C' slightly (smaller I_c' -> negative Delta_I_z -> negative Delta_P_x -> rho_s^2 < 0)
    abc1_vib = (abc1[0], abc1[1], abc1[2] * 1.01)
    res_imag = kraitchman_rs.compute_kraitchman_rs(
        parent_abc_mhz=abc0,
        iso_abc_mhz=abc1_vib,
        delta_mass_amu=dm,
        parent_mass_amu=float(np.sum(masses)),
        mode="symmetric",
    )
    assert res_imag["coordinates"]["rho_s"]["imaginary"] is True
    assert res_imag["coordinates"]["rho_s"]["rs_squared_angstrom2"] < 0.0
    assert res_imag["rho_s_angstrom"] is None
    assert res_imag["rho_s_costain_uncertainty_angstrom"] is None
    assert res_imag["any_imaginary_coordinate"] is True
    assert res_imag["r_com_angstrom"] is None
    assert res_imag["distance_from_com_angstrom"] is None

    # Spherical top must fail closed cleanly
    with pytest.raises(ValueError, match="spherical top"):
        kraitchman_rs.compute_kraitchman_rs(
            parent_abc_mhz=(157000.0, 157000.0, 157000.0),
            iso_abc_mhz=(157000.0, 120000.0, 120000.0),
            delta_mass_amu=1.006277,
            parent_mass_amu=16.0313,
            mode="auto",
        )

    # Explicit --mode symmetric on asymmetric top must fail closed cleanly
    with pytest.raises(ValueError, match="requires a symmetric-top parent"):
        kraitchman_rs.compute_kraitchman_rs(
            parent_abc_mhz=(835840.3, 435351.7, 278139.8),
            iso_abc_mhz=(701931.5, 272912.6, 192055.2),
            delta_mass_amu=1.006277,
            parent_mass_amu=18.010565,
            mode="symmetric",
        )

    # Backward compatibility: planar H2CO -> HDCO in --mode auto selects planar with a, b, c keys
    res_h2co = kraitchman_rs.compute_kraitchman_rs(
        parent_abc_mhz=(281970.57, 38833.99, 34004.24),
        iso_abc_mhz=(198114.6, 34910.4, 29561.7),
        delta_mass_amu=1.006277,
        parent_mass_amu=30.010565,
        mode="auto",
        label="H2CO_HDCO",
    )
    assert res_h2co["effective_mode"] == "planar"
    assert res_h2co["mode_used"] == "planar"
    assert set(res_h2co["coordinates"].keys()) == {"a", "b", "c"}
    assert res_h2co["coordinates"]["c"]["in_plane_fixed"] is True


# ---------------------------------------------------------------------------
# 4. SB490B-01: scripts/install_optional_spyfy.sh scikit-learn + verification
# ---------------------------------------------------------------------------


def test_install_optional_spyfy_includes_scikit_learn_and_instruments_verification() -> None:
    """Verify SB490B-01: install_optional_spyfy.sh installs scikit-learn and checks DEFAULT_INSTRUMENT_PROFILE."""
    script_path = REPO_ROOT / "scripts" / "install_optional_spyfy.sh"
    raw = script_path.read_bytes()
    assert b"\r\n" not in raw, "scripts/install_optional_spyfy.sh must use strict LF line endings"
    text = raw.decode("utf-8")

    assert '"scikit-learn"' in text, "install_optional_spyfy.sh must install scikit-learn for cochem_spyfy_ml_core"
    assert '"jax[cpu]"' in text
    assert 'cochem-spyfy" info --check-compat' in text
    assert (
        "from cochem_spyfy.instruments import DEFAULT_INSTRUMENT_PROFILE; "
        "assert DEFAULT_INSTRUMENT_PROFILE == 'grulab_surf'"
    ) in text
