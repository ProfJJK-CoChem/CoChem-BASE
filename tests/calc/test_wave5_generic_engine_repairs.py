"""Generic Wave 5 regression tests for CoChem-BASE engine defects (DEF-S1-01, 05, 06, 07, 08).

All assertions are molecule-agnostic and test generic method/solver/protocol contracts
with zero mocks, zero skips, and zero molecule-specific special cases.
"""

from __future__ import annotations

import math
from pathlib import Path
import re
import numpy as np
import pytest

from cochem_base.calc.calculation_service import CalculationMatrixConfig
from cochem_base.calc.cfour_execution import _accept_output, write_cfour_input
from cochem_base.calc.cochem_calc_input_generator import (
    MoleculeInput,
    _orca_requires_numerical_frequency,
    generate_orca_input,
)
from cochem_base.core_engine.cochem_core_cfour_bridge import (
    CFOURAnharmMode,
    CFOURCalcLevel,
    CFOURInputConfig,
    CFOURObservables,
    CFOUROutputParser,
    CFOURVibMode,
    HarmonicForceField,
    QuarticCentrifugalDistortion,
    SexticCentrifugalDistortion,
    WatsonReduction,
    export_cfour_to_spcat_var,
    generate_cfour_zmat,
    get_dynamic_atomic_mass,
)
from cochem_base.exceptions import ConvergenceError
from cochem_base.spectroscopy.spcat_runner import (
    SPCATDeckConfig,
    SPCATRunner,
    parse_cat_file,
    write_pickett_decks,
)


# ==============================================================================
# DEF-S1-01: ORCA 6 DFT-NL / VV10 / MP2 / Double-Hybrid NumFreq Auto-Guard
# ==============================================================================

@pytest.mark.parametrize("theory_level", [
    "wB97M-V def2-TZVP",
    "wB97X-V def2-SVP",
    "B97M-V def2-TZVP",
    "rev-wB97M-V def2-SVP",
    "BP86 NL def2-SVP",
    "PBE SCNL def2-SVP",
    "PBE-NL def2-SVP",
    "PBE VV10 def2-SVP",
    "B2PLYP def2-SVP",
    "B2PLYP-D3 def2-SVP",
    "PWPB95-D4 def2-SVP",
    "revDSD-PBEP86-D4 def2-SVP",
    "revDSD-PBEP86-D4/2021 def2-SVP",
    "B2GP-PLYP def2-SVP",
    "MP2 def2-SVP",
    "RI-MP2 def2-SVP",
    "DLPNO-CCSD(T) def2-TZVP",
])
def test_def_s1_01_orca_nonlocal_and_double_hybrid_emit_numfreq(
    tmp_path: Path, configured_registry, theory_level: str
) -> None:
    """Any ORCA 6 method lacking analytic Hessian must emit '! NumFreq' with provenance comment."""
    needs_num, reason = _orca_requires_numerical_frequency(theory_level)
    assert needs_num is True and reason is not None
    assert _orca_requires_numerical_frequency("B3LYP NL def2-SVP")[0] is True

    mol = MoleculeInput(
        basin_id="generic_numfreq_check",
        elements=["N", "N"],
        coordinates=[(0.0, 0.0, 0.0), (0.0, 0.0, 1.098)],
        theory_level=theory_level,
        is_opt=False,
        is_freq=True,
    )
    deck_path = generate_orca_input(mol, output_dir=tmp_path)
    deck = deck_path.read_text(encoding="utf-8")
    bang_line = next(line for line in deck.splitlines() if line.startswith("!"))
    tokens = {tok.upper() for tok in bang_line.split()}

    assert "NUMFREQ" in tokens
    assert "FREQ" not in tokens
    assert "ANFREQ" not in tokens
    assert "DEFGRID3" in tokens
    assert "# Frequency Auto-Guard: [FREQ_GUARD: ORCA_NUMFREQ]" in deck


@pytest.mark.parametrize("theory_level", [
    "r2SCAN-3c",
    "B3LYP-D4 def2-SVP",
    "PBE0-D3BJ def2-SVP",
    "wB97X-D4 def2-SVP",
    "M062X def2-SVP",
    "HF def2-SVP",
])
def test_def_s1_01_orca_analytic_hessian_methods_keep_freq(
    tmp_path: Path, configured_registry, theory_level: str
) -> None:
    """Methods with native ORCA 6 analytic Hessians continue to emit '! Freq'."""
    needs_num, reason = _orca_requires_numerical_frequency(theory_level)
    assert needs_num is False and reason is None

    mol = MoleculeInput(
        basin_id="generic_anfreq_check",
        elements=["N", "N"],
        coordinates=[(0.0, 0.0, 0.0), (0.0, 0.0, 1.098)],
        theory_level=theory_level,
        is_opt=False,
        is_freq=True,
    )
    deck_path = generate_orca_input(mol, output_dir=tmp_path)
    deck = deck_path.read_text(encoding="utf-8")
    bang_line = next(line for line in deck.splitlines() if line.startswith("!"))
    tokens = {tok.upper() for tok in bang_line.split()}

    assert "FREQ" in tokens
    assert "NUMFREQ" not in tokens
    assert "[FREQ_GUARD: ORCA_NUMFREQ]" not in deck


def test_def_s1_01_explicit_freq_keyword_upgraded_to_numfreq_for_vv10(
    tmp_path: Path, configured_registry
) -> None:
    """Explicit 'Freq' or 'AnFreq' in theory_level with VV10 functional is upgraded to NumFreq."""
    mol = MoleculeInput(
        basin_id="explicit_freq_vv10",
        elements=["C", "O"],
        coordinates=[(0.0, 0.0, 0.0), (0.0, 0.0, 1.128)],
        theory_level="wB97M-V def2-SVP Freq DEFGRID3",
        is_opt=False,
        is_freq=False,
    )
    deck = generate_orca_input(mol, output_dir=tmp_path).read_text(encoding="utf-8")
    bang_line = next(line for line in deck.splitlines() if line.startswith("!"))
    tokens = {tok.upper() for tok in bang_line.split()}
    assert "NUMFREQ" in tokens and "FREQ" not in tokens
    assert "# Frequency Auto-Guard: [FREQ_GUARD: ORCA_NUMFREQ]" in deck


# ==============================================================================
# DEF-S1-05: CFOUR 2.1 xvcc / xncc / xecc Energy Parser Acceptance
# ==============================================================================

def test_def_s1_05_accept_output_matches_xvcc_ccsdt_and_ccsd_and_xncc() -> None:
    """_accept_output accepts measured energies from xvcc, xncc, xecc, and xintprc formats."""
    xvcc_ccsdt_log = """
--invoking executable--
/opt/cfour/bin/xvscf
SCF has converged.
E(SCF)= -74.962946634519710
--executable xvscf finished with status 0
--invoking executable--
/opt/cfour/bin/xvcc
CCSD(T) energy will be calculated.
Amplitude equations converged in 13iterations.
The CC iterations have converged.
E(CCSD)           =     -75.012242636832
E(CCSD + T(CCSD)) =     -75.012320069191
E(CCSD(T))        =     -75.012310088707
--executable xvcc finished with status 0
The final electronic energy is -75.012310088707338 a.u.
"""
    accepted_vcc_t = _accept_output(xvcc_ccsdt_log, "CCSD(T)", requested_threads=2)
    assert accepted_vcc_t["energy_hartree"] == pytest.approx(-75.012310088707338, abs=1e-12)
    assert accepted_vcc_t["electronic_convergence_verified"] is True

    xvcc_ccsd_log = """
--invoking executable--
/opt/cfour/bin/xvscf
SCF has converged.
E(SCF)= -74.962946634519710
--executable xvscf finished with status 0
--invoking executable--
/opt/cfour/bin/xvcc
CCSD energy will be calculated.
Amplitude equations converged in 13iterations.
The CC iterations have converged.
The reference energy is       -74.96294663451971 a.u.
The correlation energy is      -0.04929600231242 a.u.
The total energy is           -75.01224263683213 a.u.
--executable xvcc finished with status 0
The final electronic energy is -75.012242636832127 a.u.
"""
    accepted_vcc_ccsd = _accept_output(xvcc_ccsd_log, "CCSD", requested_threads=2)
    assert accepted_vcc_ccsd["energy_hartree"] == pytest.approx(-75.012242636832127, abs=1e-12)

    xncc_ccsdt_log = """
--invoking executable--
/opt/cfour/bin/xvscf
SCF has converged.
E(SCF)= -74.962946634519710
--executable xvscf finished with status 0
--invoking executable--
/opt/cfour/bin/xncc
Running with 2 threads/proc
CCSD iterations converged in 13 cycles.
Total MP2 energy: -74.998349738232861
Total CCSD energy: -75.012242636829342
Total CCSD(T) energy: -75.012310088704552
--executable xncc finished with status 0
The final electronic energy is -75.012310088704552 a.u.
"""
    accepted_ncc_t = _accept_output(xncc_ccsdt_log, "CCSD(T)", requested_threads=2)
    assert accepted_ncc_t["energy_hartree"] == pytest.approx(-75.012310088704552, abs=1e-12)

    # Mismatched final energy vs requested CCSD(T) must still fail closed
    mismatched_log = xvcc_ccsdt_log.replace("-75.012310088707338", "-75.012242636832000")
    with pytest.raises(ValueError, match="does not match the explicitly requested method"):
        _accept_output(mismatched_log, "CCSD(T)", requested_threads=2)


# ==============================================================================
# DEF-S1-06: CFOUR 2.1 CPHF_CONVER=12 & LINEQ_CONV=7 for MP2 & CCSD(T) VPT2
# ==============================================================================

@pytest.mark.parametrize("method,expected_vib", [("MP2", "EXACT"), ("CCSD(T)", "FINDIF")])
def test_def_s1_06_cfour_vpt2_zmat_avoids_cphf_roundoff_stall(
    tmp_path: Path, method: str, expected_vib: str
) -> None:
    """CFOUR VPT2 decks emit LINEQ_CONV=7 and CPHF_CONVER=12 (not LINEQ_CONV=10 / default 10^-16)."""
    cfg = CalculationMatrixConfig(
        geometry="S 0 0 0\nO 0 1.234 0.718\nO 0 -1.234 0.718\n",
        engine="cfour",
        method=method,
        basis_set="cc-pVDZ",
        is_opt=False,
        is_freq=True,
        is_vpt2=True,
    )
    zmat = write_cfour_input(
        tmp_path / method.replace("(", "").replace(")", ""),
        cfg,
        ["S", "O", "O"],
        [(0.0, 0.0, 0.0), (0.0, 1.234, 0.718), (0.0, -1.234, 0.718)],
        anharmonic=True,
    ).read_text(encoding="utf-8")

    assert f"VIB={expected_vib}" in zmat
    assert "ANHARM=VPT2" in zmat
    assert "LINEQ_CONV=7" in zmat
    assert "LINEQ_CONV=10" not in zmat
    assert "CPHF_CONVER=12" in zmat
    assert "CPHF_MAXCYC=128" in zmat


# ==============================================================================
# DEF-S1-07: CFOUR Bridge PROPS=FIRST_ORDER Guard, VPT2 Completeness, SPCAT Codes
# ==============================================================================

def test_def_s1_07a_props_first_order_never_emitted_with_vib_or_anharm() -> None:
    """CFOURInputConfig defaults props='OFF' and strips PROPS=FIRST_ORDER whenever VIB/ANHARM is active."""
    default_cfg = CFOURInputConfig(calc_level=CFOURCalcLevel.MP2, basis="cc-pVDZ")
    assert default_cfg.props == "OFF"
    assert default_cfg.lineq_conv == 7
    assert default_cfg.cphf_conver == 12

    coords = np.array([[0.0, 0.0, 0.0], [0.0, 1.234, 0.718], [0.0, -1.234, 0.718]])
    zmat_default = generate_cfour_zmat(["S", "O", "O"], coords, default_cfg)
    assert "PROPS=FIRST_ORDER" not in zmat_default
    assert "VIB=EXACT" in zmat_default
    assert "ANHARM=VPT2" in zmat_default
    assert "CPHF_CONVER=12" in zmat_default

    # Even if caller explicitly passes props="FIRST_ORDER" or extra_keywords={"PROPS": "FIRST_ORDER"}
    # alongside VPT2 or VIB=EXACT/FINDIF, PROPS=FIRST_ORDER MUST NOT be written.
    for vib, anharm in [
        (CFOURVibMode.EXACT, CFOURAnharmMode.VPT2),
        (CFOURVibMode.EXACT, CFOURAnharmMode.NONE),
        (CFOURVibMode.FINDIF, CFOURAnharmMode.NONE),
        (CFOURVibMode.ANALYTIC, CFOURAnharmMode.NONE),
    ]:
        explicit_cfg = CFOURInputConfig(
            calc_level=CFOURCalcLevel.MP2,
            basis="cc-pVDZ",
            vib_mode=vib,
            anharm_mode=anharm,
            props="FIRST_ORDER",
            extra_keywords={"PROPS": "FIRST_ORDER"},
        )
        zmat = generate_cfour_zmat(["S", "O", "O"], coords, explicit_cfg)
        assert "PROPS=FIRST_ORDER" not in zmat

    # Single-point job (VIB=NONE, ANHARM=NONE) with explicit props="FIRST_ORDER" still emits it
    sp_props_cfg = CFOURInputConfig(
        calc_level=CFOURCalcLevel.MP2,
        basis="cc-pVDZ",
        vib_mode=CFOURVibMode.NONE,
        anharm_mode=CFOURAnharmMode.NONE,
        props="FIRST_ORDER",
    )
    zmat_sp = generate_cfour_zmat(["S", "O", "O"], coords, sp_props_cfg)
    assert "PROPS=FIRST_ORDER" in zmat_sp
    assert "VIB=" not in zmat_sp
    assert "ANHARM=" not in zmat_sp


def test_def_s1_07b_vpt2_completeness_gate_fails_closed_on_suppressed_vpt2() -> None:
    """verify_requested_stage_completeness fails closed when VPT2 lacks fundamentals or B0."""
    vpt2_cfg = CFOURInputConfig(
        calc_level=CFOURCalcLevel.MP2,
        basis="cc-pVDZ",
        vib_mode=CFOURVibMode.EXACT,
        anharm_mode=CFOURAnharmMode.VPT2,
    )
    # Silently skipped VPT2 output (energy only, empty fundamentals, B0=None)
    suppressed_obs = CFOURObservables(
        final_energy_hartree=-74.998349738233,
        harmonic_force_field=HarmonicForceField(
            n_atoms=3,
            symbols=["O", "H", "H"],
            masses_u=[get_dynamic_atomic_mass(sym) for sym in ("O", "H", "H")],
            frequencies_cm_inv=[],
        ),
        fundamental_frequencies_cm_inv=[],
        B0_MHz=None,
    )
    with pytest.raises(ConvergenceError, match="EXECUTION_FAILED"):
        CFOUROutputParser.verify_requested_stage_completeness(suppressed_obs, vpt2_cfg)

    # Has fundamentals but missing B0_MHz must also fail closed
    missing_b0_obs = suppressed_obs.model_copy(
        update={
            "fundamental_frequencies_cm_inv": [1595.0, 3657.0, 3756.0],
            "harmonic_force_field": suppressed_obs.harmonic_force_field.model_copy(
                update={"frequencies_cm_inv": [1650.0, 3800.0, 3900.0]}
            ),
            "B0_MHz": None,
        }
    )
    with pytest.raises(ConvergenceError, match="EXECUTION_FAILED"):
        CFOUROutputParser.verify_requested_stage_completeness(missing_b0_obs, vpt2_cfg)

    # Complete VPT2 observables pass cleanly
    complete_obs = missing_b0_obs.model_copy(update={"A0_MHz": 835840.0, "B0_MHz": 435351.0, "C0_MHz": 278139.0})
    CFOUROutputParser.verify_requested_stage_completeness(complete_obs, vpt2_cfg)

    # Linear-molecule 2-column Be/B0 table parses finite B0_MHz cleanly
    linear_vpt2_excerpt = """
    E(SCF)= -111.224342065888
    SCF has converged.
     Be, B0 AND B-B0 SHIFTS FOR SINGLY EXCITED VIBRATIONAL STATES (MHz)
    VIBRATION            X AXIS               Y AXIS                 Z AXIS
    ----------------------------------------------------------------------------
      Be                57910.39178395       57910.39178395
      B0                57739.15406291       57739.15406291
    ----------------------------------------------------------------------------
    HARMONIC AND FUNDAMENTAL FREQUENCIES (cm-1) AND INTENSITIES (km/mol)
    --------------------------------------------------------------------------------
             Harmonic     Fundamental Anharmonic    Harmonic   Fundamental  Anharm
      Mode   Frequency    Frequency   Contribution  Intensity  Intensity    Contrib
        6   2598.9126   2580.5454      -18.3672     38.4899      38.8114      0.3215
    --------------------------------------------------------------------------------
    The final electronic energy is -111.224342065887512 a.u.
    """
    lin_obs = CFOUROutputParser.parse_cfour_stdout(linear_vpt2_excerpt, symbols_fallback=["C", "O"])
    assert lin_obs.B0_MHz == pytest.approx(57739.15406291)
    assert lin_obs.fundamental_frequencies_cm_inv == pytest.approx([2580.5454])
    CFOUROutputParser.verify_requested_stage_completeness(lin_obs, vpt2_cfg)


def test_def_s1_07c_export_cfour_to_spcat_var_watson_a_and_s_codes_and_signs() -> None:
    """export_cfour_to_spcat_var emits negated Watson-A quartics in MHz with exact Pickett codes (41000, not 50000)."""
    obs = CFOURObservables(
        final_energy_hartree=-150.0,
        A0_MHz=20245.8,
        B0_MHz=10518.2,
        C0_MHz=6878.3,
        harmonic_force_field=HarmonicForceField(
            n_atoms=3,
            symbols=["S", "O", "O"],
            masses_u=[get_dynamic_atomic_mass(sym) for sym in ("S", "O", "O")],
            frequencies_cm_inv=[500.0, 1150.0, 1360.0],
        ),
        quartic_distortion=QuarticCentrifugalDistortion(
            Delta_J_kHz=7.62,
            Delta_JK_kHz=-63.4,
            Delta_K_kHz=528.0,
            delta_j_kHz=1.64,
            delta_k_kHz=32.0,
            D_J_kHz=7.30,
            D_JK_kHz=-60.0,
            D_K_kHz=520.0,
            d_1_kHz=-1.64,
            d_2_kHz=-0.25,
        ),
        sextic_distortion=SexticCentrifugalDistortion(phi_k_Hz=12.5),
    )

    var_a = export_cfour_to_spcat_var(obs, reduction=WatsonReduction.A)
    var_a_lines = [ln for ln in var_a.splitlines() if ln.strip()]
    # 3-line Pickett header: title, n_params line, option line starting with 'a'
    assert var_a_lines[1].split()[0] == "9"
    assert var_a_lines[2].startswith("a ")
    params_a = {int(ln.split()[0]): float(ln.split()[1]) for ln in var_a_lines[3:]}
    assert params_a[10000] == pytest.approx(20245.8)
    assert params_a[20000] == pytest.approx(10518.2)
    assert params_a[30000] == pytest.approx(6878.3)
    assert params_a[200] == pytest.approx(-0.00762)
    assert params_a[1100] == pytest.approx(+0.0634)
    assert params_a[2000] == pytest.approx(-0.528)
    assert params_a[40100] == pytest.approx(-0.00164)
    assert params_a[41000] == pytest.approx(-0.032)
    assert params_a[42000] == pytest.approx(12.5e-6)
    assert 50000 not in params_a  # 50000 is Watson-S d_2, NEVER Watson-A delta_K

    var_s = export_cfour_to_spcat_var(obs, reduction=WatsonReduction.S)
    var_s_lines = [ln for ln in var_s.splitlines() if ln.strip()]
    assert var_s_lines[2].startswith("s ")
    params_s = {int(ln.split()[0]): float(ln.split()[1]) for ln in var_s_lines[3:]}
    assert params_s[200] == pytest.approx(-0.00730)
    assert params_s[1100] == pytest.approx(+0.0600)
    assert params_s[2000] == pytest.approx(-0.520)
    assert params_s[40100] == pytest.approx(-0.00164)  # +d_1
    assert params_s[50000] == pytest.approx(-0.00025)  # +d_2
    assert 41000 not in params_s


# ==============================================================================
# DEF-S1-08: SPCATRunner Zero Cross-Repo Import, Valid Pickett Decks, Fail-Closed
# ==============================================================================

def test_def_s1_08_spcat_runner_decks_mhz_codes_parsing_and_fail_closed(tmp_path: Path) -> None:
    """SPCATRunner writes valid 3-line Pickett decks in MHz, parses fixed-width .cat, and fails closed when binary absent."""
    source_text = (
        Path(__file__).resolve().parents[2]
        / "src" / "cochem_base" / "spectroscopy" / "spcat_runner.py"
    ).read_text(encoding="utf-8")
    assert "cochem_torq_asymmetric_rotor" not in source_text
    assert "AsymmetricTopDiagonalizer" not in source_text

    cfg = SPCATDeckConfig(
        a_mhz=20245.8,
        b_mhz=10518.2,
        c_mhz=6878.3,
        dj_khz=7.62,
        djk_khz=-63.4,
        dk_khz=528.0,
        d1_khz=1.64,
        d2_khz=32.0,
        mu_a=1.41,
        mu_b=0.21,
        mu_c=0.0,
        temperature_k=298.15,
        constant_type="B0",
    )
    var_p, int_p = write_pickett_decks(cfg, tmp_path / "decks", stem="generic_rotor", freq_max_ghz=200.0)
    var_lines = var_p.read_text(encoding="utf-8").splitlines()
    int_lines = int_p.read_text(encoding="utf-8").splitlines()

    # Exact 3-line Pickett .var header with n_params=8 and Watson-A option line
    assert len(var_lines) == 11
    assert var_lines[1].split()[0] == "8"
    assert "1.0000E+04" in var_lines[1]
    assert var_lines[2].startswith("a ")

    # Parameter codes & values strictly in MHz with negated Watson-A quartics
    params = {int(ln.split()[0]): float(ln.split()[1]) for ln in var_lines[3:]}
    assert params[10000] == pytest.approx(20245.8)
    assert params[20000] == pytest.approx(10518.2)
    assert params[30000] == pytest.approx(6878.3)
    assert params[200] == pytest.approx(-0.00762)
    assert params[1100] == pytest.approx(+0.0634)
    assert params[2000] == pytest.approx(-0.528)
    assert params[40100] == pytest.approx(-0.00164)
    assert params[41000] == pytest.approx(-0.032)

    # Valid .int header + dipole lines
    assert len(int_lines) == 5
    assert "200.000" in int_lines[1] and "298.150" in int_lines[1]
    assert re.search(r"^\s*1\s+1\.4100$", int_lines[2])
    assert re.search(r"^\s*2\s+0\.2100$", int_lines[3])

    # Fixed-width .cat parsing handles contiguous J>=10 quantum numbers (e.g. 221210 / 221211)
    cat_file = tmp_path / "sample.cat"
    cat_file.write_text(
        "      13.6249  0.0000 -9.9629 3  204.8709 45     91 303221210      221211       \n"
        "      15.6846  0.0000 -9.6545 3   11.9841  9     91 303 4 4 0       4 4 1       \n",
        encoding="utf-8",
    )
    parsed = parse_cat_file(cat_file, constant_type="B0")
    assert len(parsed) == 2
    assert (parsed[0]["j_upper"], parsed[0]["ka_upper"], parsed[0]["kc_upper"]) == (22, 12, 10)
    assert (parsed[0]["j_lower"], parsed[0]["ka_lower"], parsed[0]["kc_lower"]) == (22, 12, 11)
    assert (parsed[1]["j_upper"], parsed[1]["ka_upper"], parsed[1]["kc_upper"]) == (4, 4, 0)
    assert (parsed[1]["j_lower"], parsed[1]["ka_lower"], parsed[1]["kc_lower"]) == (4, 4, 1)

    # Missing spcat binary fails closed with FileNotFoundError
    runner = SPCATRunner(spcat_bin_path=tmp_path / "absent_spcat_binary")
    with pytest.raises(FileNotFoundError, match="Pickett spcat binary not found"):
        runner.generate_parquet_catalog(cfg, tmp_path / "out.parquet", scratch_dir=tmp_path / "scr")
