"""Verification tests for Part A (Wave 3 R-08) P2 Chemical-Regime Auto-Guards.

Tests all four authentic physics guards with zero mocks:
1. Anion diffuse-basis auto-guard (charge < 0) across ORCA, CFOUR, PySCF, and GPU4PySCF.
2. Heavy-element scalar-relativistic/ECP (Z > 36) & 3d-TM DEFGRID3 (Z=21..30) across IUPAC Z=1..118.
3. Live coupled-cluster T1/D1 multireference diagnostics parser & warning gate (ORCA + CFOUR).
4. Bounded ORCA SCF retry (SlowConv/KDIIS/MaxIter 300, max 2 attempts) & authentic Hessian
   imaginary-mode eigenvector displacement + re-optimization (max 2 attempts, fail closed).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from cochem_base.calc.calculation_service import (
    CalculationMatrixConfig,
    reoptimize_orca_imaginary_modes,
    run_calculation,
)
from cochem_base.calc.cfour_execution import write_cfour_input
from cochem_base.calc.cochem_calc_input_generator import (
    MoleculeInput,
    generate_orca_input,
    generate_pyscf_input,
)
from cochem_base.calc.cochem_calc_output_parser import QuantumParser
from cochem_base.calc.gpu4pyscf_execution import build_gpu4pyscf_script
from cochem_base.calc.grid_execution import quadrature_execution_plan
from cochem_base.calc.regime_guards import (
    ELEMENT_Z,
    MAX_IMAGINARY_MODE_RETRIES,
    MAX_SCF_RETRIES,
    ImaginaryModePersistenceError,
    _assert_non_downgrading_diffuse_upgrade,
    _basis_family_tags,
    _basis_zeta,
    apply_chemical_regime_guards,
    displace_along_imaginary_mode,
    evaluate_heavy_element_and_tm_guard,
    extract_imaginary_vibrational_modes,
    is_diffuse_basis,
    parse_cc_multireference_diagnostics,
    prepare_orca_scf_retry,
    reoptimize_imaginary_modes,
    resolve_atomic_number,
    upgrade_anion_diffuse_basis,
)


# ==============================================================================
# 1. Anion Diffuse-Basis Auto-Guard (charge < 0)
# ==============================================================================

@pytest.mark.parametrize("engine,requested,expected", [
    ("orca", "def2-SVP", "ma-def2-SVP"),
    ("orca", "def2-TZVP", "ma-def2-TZVP"),
    ("orca", "def2-TZVPP", "def2-TZVPPD"),
    ("orca", "def2-QZVPP", "def2-QZVPPD"),
    ("orca", "cc-pVDZ", "aug-cc-pVDZ"),
    ("orca", "cc-pVTZ", "aug-cc-pVTZ"),
    ("orca", "STO-3G", "ma-def2-SVP"),
    ("orca", "6-31G*", "6-31+G*"),
    ("orca", "6-31G**", "6-31++G**"),
    ("cfour", "def2-SVP", "def2-SVPD"),
    ("cfour", "def2-TZVP", "def2-TZVPD"),
    ("cfour", "def2-TZVPP", "def2-TZVPPD"),
    ("cfour", "cc-pVDZ", "aug-cc-pVDZ"),
    ("cfour", "STO-3G", "aug-cc-pVDZ"),
    ("cfour", "6-31G*", "6-31+G*"),
    ("pyscf", "def2-SVP", "ma-def2-SVP"),
    ("gpu4pyscf", "def2-TZVP", "ma-def2-TZVP"),
])
def test_anion_diffuse_basis_upgrade_mapping_and_warning(engine: str, requested: str, expected: str) -> None:
    dec = upgrade_anion_diffuse_basis(requested, charge=-1, engine=engine)
    assert dec.triggered is True
    assert dec.original_basis == requested
    assert dec.effective_basis == expected
    assert dec.warning is not None and "ANION_DIFFUSE_UPGRADE" in dec.warning
    assert requested in dec.warning and expected in dec.warning

    # Neutral and cationic molecules must NOT be upgraded
    neutral = upgrade_anion_diffuse_basis(requested, charge=0, engine=engine)
    assert neutral.triggered is False
    assert neutral.effective_basis == requested
    assert neutral.warning is None

    cation = upgrade_anion_diffuse_basis(requested, charge=+1, engine=engine)
    assert cation.triggered is False
    assert cation.effective_basis == requested


@pytest.mark.parametrize("diffuse_basis", [
    "ma-def2-SVP", "ma-def2-TZVP", "def2-TZVPPD", "def2-QZVPPD",
    "ma-DKH-def2-TZVP", "ma-DKH-def2-QZVPP", "ma-ZORA-def2-TZVP", "ma-ZORA-def2-QZVPP",
    "aug-cc-pVDZ", "aug-cc-pVTZ", "aug-cc-pVTZ-PP", "aug-cc-pVQZ-PP",
    "aug-cc-pVTZ-DK", "aug-cc-pwCVTZ-DK", "aug-cc-pwCVQZ-PP",
    "6-31+G*", "6-31++G**", "ANO-RCC",
])
def test_already_diffuse_basis_is_not_double_upgraded(diffuse_basis: str) -> None:
    assert is_diffuse_basis(diffuse_basis) is True
    dec = upgrade_anion_diffuse_basis(diffuse_basis, charge=-1, engine="orca")
    assert dec.triggered is False
    assert dec.effective_basis == diffuse_basis


@pytest.mark.parametrize("engine,requested,expected", [
    # Dunning pseudopotential (-PP) family: preserve zeta and -PP
    ("orca", "cc-pVDZ-PP", "aug-cc-pVDZ-PP"),
    ("orca", "cc-pVTZ-PP", "aug-cc-pVTZ-PP"),
    ("orca", "cc-pVQZ-PP", "aug-cc-pVQZ-PP"),
    ("orca", "cc-pV5Z-PP", "aug-cc-pV5Z-PP"),
    ("cfour", "cc-pVQZ-PP", "aug-cc-pVQZ-PP"),
    ("pyscf", "cc-pVTZ-PP", "aug-cc-pVTZ-PP"),
    # Dunning Douglas-Kroll (-DK) family: preserve zeta and -DK
    ("orca", "cc-pVDZ-DK", "aug-cc-pVDZ-DK"),
    ("orca", "cc-pVTZ-DK", "aug-cc-pVTZ-DK"),
    ("orca", "cc-pVQZ-DK", "aug-cc-pVQZ-DK"),
    ("orca", "cc-pV5Z-DK", "aug-cc-pV5Z-DK"),
    # Weighted core-valence Dunning family (standard, -DK, -PP)
    ("orca", "cc-pwCVDZ", "aug-cc-pwCVDZ"),
    ("orca", "cc-pwCVTZ", "aug-cc-pwCVTZ"),
    ("orca", "cc-pwCVTZ-DK", "aug-cc-pwCVTZ-DK"),
    ("orca", "cc-pwCVQZ-DK", "aug-cc-pwCVQZ-DK"),
    ("orca", "cc-pwCVTZ-PP", "aug-cc-pwCVTZ-PP"),
    ("orca", "cc-pwCVQZ-PP", "aug-cc-pwCVQZ-PP"),
    ("orca", "cc-pwCV5Z-PP", "aug-cc-pwCV5Z-PP"),
    # ORCA scalar-relativistic Karlsruhe DKH-def2-* and ZORA-def2-*
    ("orca", "DKH-def2-SVP", "ma-DKH-def2-SVP"),
    ("orca", "DKH-def2-TZVP", "ma-DKH-def2-TZVP"),
    ("orca", "DKH-def2-TZVPP", "ma-DKH-def2-TZVPP"),
    ("orca", "DKH-def2-QZVPP", "ma-DKH-def2-QZVPP"),
    ("orca", "ZORA-def2-SVP", "ma-ZORA-def2-SVP"),
    ("orca", "ZORA-def2-TZVP", "ma-ZORA-def2-TZVP"),
    ("orca", "ZORA-def2-TZVPP", "ma-ZORA-def2-TZVPP"),
    ("orca", "ZORA-def2-QZVPP", "ma-ZORA-def2-QZVPP"),
])
def test_anion_diffuse_preserves_zeta_and_relativistic_pp_families(
    engine: str, requested: str, expected: str
) -> None:
    dec = upgrade_anion_diffuse_basis(requested, charge=-1, engine=engine)
    assert dec.triggered is True
    assert dec.original_basis == requested
    assert dec.effective_basis == expected
    assert is_diffuse_basis(dec.effective_basis) is True
    orig_zeta = _basis_zeta(requested)
    new_zeta = _basis_zeta(dec.effective_basis)
    assert orig_zeta is not None and new_zeta is not None and new_zeta >= orig_zeta
    assert _basis_family_tags(requested).issubset(_basis_family_tags(dec.effective_basis))


@pytest.mark.parametrize("engine,basis", [
    ("orca", "x2c-SVPall"),
    ("orca", "x2c-TZVPall"),
    ("orca", "x2c-TZVPPall"),
    ("orca", "x2c-QZVPall"),
    ("orca", "x2c-QZVPPall"),
    ("orca", "x2c-TZVPall-s"),
    ("orca", "x2c-TZVPall-2c"),
    ("cfour", "x2c-TZVPall"),
    ("cfour", "DKH-def2-QZVPP"),
    ("orca", "Sapporo-DKH3-QZP-2012"),
    ("orca", "ANO-VT-QZ"),
    ("cfour", "exotic-custom-TZ"),
])
def test_anion_diffuse_fails_closed_for_x2c_and_exotic_bases(engine: str, basis: str) -> None:
    # Neutral/cationic runs keep the requested basis untouched
    neutral = upgrade_anion_diffuse_basis(basis, charge=0, engine=engine)
    assert neutral.triggered is False
    assert neutral.effective_basis == basis

    # Anionic runs MUST fail closed with explicit ValueError — never silently downgrade to ma-def2-SVP / aug-cc-pVDZ
    with pytest.raises(ValueError, match="explicit diffuse basis"):
        upgrade_anion_diffuse_basis(basis, charge=-1, engine=engine)


def test_anion_b2_redteam_six_poc_regressions_and_zeta_monotonicity(
    tmp_path: Path, configured_registry
) -> None:
    # Structural zeta ordering & invariant enforcement
    assert _basis_zeta("STO-3G") == 1
    assert _basis_zeta("def2-SVP") == 2
    assert _basis_zeta("ma-def2-SVP") == 2
    assert _basis_zeta("x2c-TZVPall") == 3
    assert _basis_zeta("cc-pVTZ-PP") == 3
    assert _basis_zeta("aug-cc-pVTZ-PP") == 3
    assert _basis_zeta("DKH-def2-QZVPP") == 4
    assert _basis_zeta("ma-DKH-def2-QZVPP") == 4
    assert _basis_zeta("cc-pVQZ-PP") == 4
    assert _basis_zeta("cc-pV5Z-PP") == 5
    assert _basis_zeta("cc-pV6Z") == 6

    with pytest.raises(ValueError, match="zeta downgrade"):
        _assert_non_downgrading_diffuse_upgrade("cc-pVTZ-PP", "aug-cc-pVDZ-PP", engine="orca")
    with pytest.raises(ValueError, match="zeta downgrade"):
        _assert_non_downgrading_diffuse_upgrade("DKH-def2-QZVPP", "ma-DKH-def2-TZVP", engine="orca")
    with pytest.raises(ValueError, match="family stripping"):
        _assert_non_downgrading_diffuse_upgrade("cc-pVTZ-PP", "aug-cc-pVTZ", engine="orca")
    with pytest.raises(ValueError, match="family stripping"):
        _assert_non_downgrading_diffuse_upgrade("DKH-def2-TZVP", "ma-def2-TZVP", engine="orca")

    # PoC 1: orca x2c-TZVPall (charge=-1) -> fail closed ValueError (never ma-def2-SVP)
    with pytest.raises(ValueError, match="x2c"):
        upgrade_anion_diffuse_basis("x2c-TZVPall", charge=-1, engine="orca")

    # PoC 2: orca DKH-def2-QZVPP (charge=-1) -> ma-DKH-def2-QZVPP (QZ DKH preserved)
    poc2 = upgrade_anion_diffuse_basis("DKH-def2-QZVPP", charge=-1, engine="orca")
    assert poc2.effective_basis == "ma-DKH-def2-QZVPP"

    # PoC 3: orca cc-pVTZ-PP (charge=-1) -> aug-cc-pVTZ-PP (TZ PP preserved)
    poc3 = upgrade_anion_diffuse_basis("cc-pVTZ-PP", charge=-1, engine="orca")
    assert poc3.effective_basis == "aug-cc-pVTZ-PP"

    # PoC 4: cfour cc-pVQZ-PP (charge=-1) -> aug-cc-pVQZ-PP (QZ PP preserved)
    poc4 = upgrade_anion_diffuse_basis("cc-pVQZ-PP", charge=-1, engine="cfour")
    assert poc4.effective_basis == "aug-cc-pVQZ-PP"

    # PoC 5: full-guard ['I', 'C', 'H', 'H', 'H'] q=-1 cc-pVTZ-PP -> aug-cc-pVTZ-PP + light-atom NewGTO + DEFGRID3
    poc5 = apply_chemical_regime_guards(
        ["I", "C", "H", "H", "H"],
        charge=-1,
        method_or_theory="B3LYP D3BJ cc-pVTZ-PP",
        engine="orca",
    )
    assert poc5.effective_basis == "aug-cc-pVTZ-PP"
    assert "aug-cc-pVTZ-PP" in poc5.effective_theory_level
    assert "ma-def2-SVP" not in poc5.effective_theory_level
    assert "DKH2" not in poc5.effective_theory_level
    assert poc5.require_defgrid3 is True
    assert '  NewGTO C "aug-cc-pVTZ" end' in poc5.orca_basis_block_lines
    assert '  NewGTO H "aug-cc-pVTZ" end' in poc5.orca_basis_block_lines

    # Also verify full ORCA deck compilation for PoC 5 and PoC 2
    ch3i_mol = MoleculeInput(
        basin_id="ch3i_anion_pp",
        elements=["I", "C", "H", "H", "H"],
        coordinates=[
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 2.14),
            (1.03, 0.0, 2.49),
            (-0.515, 0.892, 2.49),
            (-0.515, -0.892, 2.49),
        ],
        theory_level="B3LYP D3BJ cc-pVTZ-PP",
        charge=-1,
        multiplicity=2,
        is_opt=False,
    )
    ch3i_deck = generate_orca_input(ch3i_mol, output_dir=tmp_path).read_text(encoding="utf-8")
    assert "aug-cc-pVTZ-PP" in ch3i_deck
    assert 'NewGTO C "aug-cc-pVTZ" end' in ch3i_deck
    assert 'NewGTO H "aug-cc-pVTZ" end' in ch3i_deck
    assert "DEFGRID3" in ch3i_deck
    assert "ma-def2-SVP" not in ch3i_deck

    f_dkh_mol = MoleculeInput(
        basin_id="f_anion_dkh_qz",
        elements=["F"],
        coordinates=[(0.0, 0.0, 0.0)],
        theory_level="B3LYP D3BJ DKH2 DKH-def2-QZVPP",
        charge=-1,
        multiplicity=1,
        is_opt=False,
    )
    f_dkh_deck = generate_orca_input(f_dkh_mol, output_dir=tmp_path).read_text(encoding="utf-8")
    assert "ma-DKH-def2-QZVPP" in f_dkh_deck
    assert "DKH2" in f_dkh_deck
    assert "ma-def2-SVP" not in f_dkh_deck

    # PoC 6: full-guard ['Br'] q=-1 x2c-TZVPall -> fail closed ValueError (never ma-def2-SVP)
    with pytest.raises(ValueError, match="x2c"):
        apply_chemical_regime_guards(
            ["Br"],
            charge=-1,
            method_or_theory="B3LYP D3BJ X2C x2c-TZVPall",
            engine="orca",
        )
    with pytest.raises(ValueError, match="x2c"):
        apply_chemical_regime_guards(
            ["Br"],
            charge=-1,
            method_or_theory="B3LYP D3BJ",
            basis="x2c-TZVPall",
            engine="orca",
        )


def test_anion_guard_wired_into_orca_cfour_pyscf_gpu4pyscf_and_service(
    tmp_path: Path, configured_registry
) -> None:
    # 1. ORCA deck generation (OH-, charge=-1, def2-SVP -> ma-def2-SVP)
    mol_orca = MoleculeInput(
        basin_id="oh_anion",
        elements=["O", "H"],
        coordinates=[(0.0, 0.0, 0.0), (0.0, 0.0, 0.96)],
        theory_level="B3LYP D3BJ def2-SVP",
        charge=-1,
        multiplicity=1,
        is_opt=False,
    )
    orca_deck = generate_orca_input(mol_orca, output_dir=tmp_path).read_text(encoding="utf-8")
    assert "ma-def2-SVP" in orca_deck
    assert "Chemical-Regime Auto-Guard" in orca_deck
    assert "ANION_DIFFUSE_UPGRADE" in orca_deck

    # 2. CFOUR ZMAT generation (OH-, charge=-1, cc-pVDZ -> AUG-PVDZ)
    cfg_cfour = CalculationMatrixConfig(
        geometry="O 0 0 0\nH 0 0 0.96\n",
        engine="cfour",
        method="CCSD(T)",
        basis_set="cc-pVDZ",
        charge=-1,
        multiplicity=1,
        is_opt=False,
    )
    zmat = write_cfour_input(
        tmp_path / "cfour_anion",
        cfg_cfour,
        ["O", "H"],
        [(0.0, 0.0, 0.0), (0.0, 0.0, 0.96)],
    ).read_text(encoding="utf-8")
    assert "BASIS=AUG-PVDZ" in zmat
    assert "CHARGE=-1" in zmat

    # 3. PySCF deck generation (OH-, charge=-1, def2-SVP -> ma-def2-SVP)
    mol_pyscf = MoleculeInput(
        basin_id="oh_pyscf",
        elements=["O", "H"],
        coordinates=[(0.0, 0.0, 0.0), (0.0, 0.0, 0.96)],
        theory_level="RHF def2-SVP",
        charge=-1,
        multiplicity=1,
        is_opt=False,
    )
    pyscf_deck = generate_pyscf_input(mol_pyscf, output_dir=tmp_path).read_text(encoding="utf-8")
    assert "ma-def2-SVP" in pyscf_deck
    assert "ANION_DIFFUSE_UPGRADE" in pyscf_deck

    # 4. GPU4PySCF script generation (OH-, charge=-1, def2-TZVP -> ma-def2-TZVP)
    _, gpu_spec = build_gpu4pyscf_script(
        ["O", "H"],
        [(0.0, 0.0, 0.0), (0.0, 0.0, 0.96)],
        method="wB97M-V",
        basis_set="def2-TZVP",
        charge=-1,
        multiplicity=1,
    )
    assert gpu_spec["basis"] == "ma-def2-TZVP"
    assert gpu_spec["requested_basis"] == "def2-TZVP"
    assert gpu_spec["regime_guards"]["anion_diffuse_guard"]["triggered"] is True

    # 5. Service run_calculation dry-run emits explicit warning & provenance
    events: list[dict] = []
    cfg_orca = CalculationMatrixConfig(
        geometry="O 0 0 0\nH 0 0 0.96\n",
        engine="orca",
        method="B3LYP-D3BJ",
        basis_set="def2-SVP",
        charge=-1,
        multiplicity=1,
        is_opt=False,
    )
    cfg_file = tmp_path / "oh_service.json"
    cfg_file.write_text(cfg_orca.model_dump_json(), encoding="utf-8")
    payload = run_calculation(
        cfg_file,
        dry_run=True,
        scratch=tmp_path / "scratch",
        on_event=events.append,
    )
    assert payload["basis_set"] == "ma-def2-SVP"
    assert payload["regime_guards"]["anion_diffuse_guard"]["triggered"] is True
    assert any("ANION_DIFFUSE_UPGRADE" in w for w in payload["warnings"])
    assert any(ev.get("kind") == "warning" and "ANION_DIFFUSE_UPGRADE" in ev.get("message", "") for ev in events)


# ==============================================================================
# 2. Heavy-Element Relativistic / ECP & 3d-TM Grid Auto-Guard (Z=1..118)
# ==============================================================================

def test_complete_iupac_periodic_table_z1_to_z118() -> None:
    assert len(ELEMENT_Z) == 118
    assert set(ELEMENT_Z.values()) == set(range(1, 119))
    assert resolve_atomic_number("H") == 1
    assert resolve_atomic_number("D") == 1
    assert resolve_atomic_number("13C") == 6
    assert resolve_atomic_number("Sc") == 21
    assert resolve_atomic_number("Zn") == 30
    assert resolve_atomic_number("Kr") == 36
    assert resolve_atomic_number("Rb") == 37
    assert resolve_atomic_number("I:") == 53
    assert resolve_atomic_number("197Au") == 79
    assert resolve_atomic_number("U") == 92
    assert resolve_atomic_number("Og") == 118


def test_3d_tm_and_heavy_element_guards_across_all_engines(tmp_path: Path, configured_registry) -> None:
    # 3d transition metal (Fe, Z=26): DEFGRID3 enforced
    tm_dec = evaluate_heavy_element_and_tm_guard(["Fe", "C", "O"], method_or_theory="PBE0 D4 def2-SVP", basis="def2-SVP", engine="orca")
    assert tm_dec.triggered is True
    assert tm_dec.require_defgrid3 is True
    assert tm_dec.transition_metals_3d == ("Fe",)
    assert tm_dec.heavy_elements == ()

    # Heavy element Z=53 (I) on ORCA with def2-SVP -> scalar-relativistic Def2-ECP + DEFGRID3
    hi_ecp = MoleculeInput(
        basin_id="hi_ecp",
        elements=["I", "H"],
        coordinates=[(0.0, 0.0, 0.0), (0.0, 0.0, 1.61)],
        theory_level="B3LYP D3BJ def2-SVP",
        is_opt=False,
    )
    assert quadrature_execution_plan(hi_ecp)["stages"] == [3]
    hi_ecp_deck = generate_orca_input(hi_ecp, output_dir=tmp_path).read_text(encoding="utf-8")
    assert "DEFGRID3" in hi_ecp_deck
    assert "HEAVY_ELEMENT_ECP" in hi_ecp_deck

    # Heavy element Z=53 (I) on ORCA with non-ECP basis (cc-pVDZ) -> injects DKH2 + old-DKH-TZVP + AutoAux + DEFGRID3
    hi_dkh = MoleculeInput(
        basin_id="hi_dkh",
        elements=["I", "H"],
        coordinates=[(0.0, 0.0, 0.0), (0.0, 0.0, 1.61)],
        theory_level="B3LYP D3BJ cc-pVDZ",
        is_opt=False,
    )
    hi_dkh_deck = generate_orca_input(hi_dkh, output_dir=tmp_path).read_text(encoding="utf-8")
    assert "DKH2" in hi_dkh_deck
    assert 'NewGTO I "old-DKH-TZVP" end' in hi_dkh_deck
    assert "AutoAux" in hi_dkh_deck
    assert "DEFGRID3" in hi_dkh_deck

    # Actinide Z=92 (U) on ORCA -> injects DKH2 + SARC-DKH-TZVP + AutoAux + DEFGRID3
    u_guard = apply_chemical_regime_guards(["U", "O", "O"], charge=2, method_or_theory="PBE0 D4 def2-TZVP", engine="orca")
    assert u_guard.require_defgrid3 is True
    assert "DKH2" in u_guard.effective_theory_level
    assert any('SARC-DKH-TZVP' in line for line in u_guard.orca_basis_block_lines)

    # CFOUR Z=53 (I) -> injects RELATIVISTIC=X2C1E
    cfg_cfour_hi = CalculationMatrixConfig(
        geometry="I 0 0 0\nH 0 0 1.61\n",
        engine="cfour",
        method="HF",
        basis_set="def2-SVP",
        is_opt=False,
    )
    zmat_hi = write_cfour_input(
        tmp_path / "cfour_hi",
        cfg_cfour_hi,
        ["I", "H"],
        [(0.0, 0.0, 0.0), (0.0, 0.0, 1.61)],
    ).read_text(encoding="utf-8")
    assert "RELATIVISTIC=X2C1E" in zmat_hi

    # PySCF & GPU4PySCF Z=53 (I) with def2-SVP -> explicit per-element ECP; with cc-pVDZ -> sfx2c1e
    script_ecp, spec_ecp = build_gpu4pyscf_script(
        ["I", "H"], [(0.0, 0.0, 0.0), (0.0, 0.0, 1.61)], method="PBE0", basis_set="def2-SVP"
    )
    assert spec_ecp["ecp"] == {"I": "def2-SVP"}
    assert spec_ecp["use_sfx2c1e"] is False
    assert "mol_kwargs[\"ecp\"]" in script_ecp

    script_x2c, spec_x2c = build_gpu4pyscf_script(
        ["I", "H"], [(0.0, 0.0, 0.0), (0.0, 0.0, 1.61)], method="PBE0", basis_set="cc-pVDZ"
    )
    assert spec_x2c["ecp"] is None
    assert spec_x2c["use_sfx2c1e"] is True
    assert "mf = mf.sfx2c1e()" in script_x2c


# ==============================================================================
# 3. Live Coupled-Cluster T1 / D1 Multireference Diagnostics Gate
# ==============================================================================

def test_parse_cc_t1_d1_diagnostics_orca_and_cfour_thresholds(tmp_path: Path) -> None:
    # Real ORCA 6.1.1 H2O CCSD(T) excerpt (single-reference: T1 = 0.00595, no D1 printed)
    orca_clean = """
    T1 diagnostic                              ...      0.005948366
    FINAL SINGLE POINT ENERGY       -76.174711444961
    ****ORCA TERMINATED NORMALLY****
    """
    res_clean = parse_cc_multireference_diagnostics(orca_clean, engine="orca", method="CCSD(T)", multiplicity=1)
    assert res_clean["t1_diagnostic"] == pytest.approx(0.005948366)
    assert res_clean["d1_diagnostic"] is None  # Never fabricated when absent!
    assert res_clean["t1_exceeded"] is False
    assert res_clean["d1_exceeded"] is False
    assert res_clean["multireference_warning"] is False

    # Closed-shell ozone-like multireference case: T1 = 0.027 (> 0.020), D1 = 0.064 (> 0.050)
    orca_mr = """
    T1 diagnostic                              ...      0.027410000
    D1 diagnostic                              ...      0.064200000
    """
    log_path = tmp_path / "mr.out"
    log_path.write_text(orca_mr, encoding="utf-8")
    res_mr = QuantumParser(str(tmp_path)).parse_cc_diagnostics(log_path, method="DLPNO-CCSD(T)", multiplicity=1)
    assert res_mr["t1_diagnostic"] == pytest.approx(0.02741)
    assert res_mr["d1_diagnostic"] == pytest.approx(0.0642)
    assert res_mr["t1_exceeded"] is True
    assert res_mr["d1_exceeded"] is True
    assert res_mr["multireference_warning"] is True
    assert len(res_mr["warnings"]) == 2

    # Open-shell thresholds (T1 > 0.045, D1 > 0.070): T1=0.030 & D1=0.060 are accepted; T1=0.052 is flagged
    res_open_ok = parse_cc_multireference_diagnostics(
        "T1 diagnostic ... 0.030\nD1 diagnostic ... 0.060\n",
        engine="orca", method="CCSD(T)", multiplicity=2,
    )
    assert res_open_ok["is_open_shell"] is True
    assert res_open_ok["multireference_warning"] is False

    res_open_bad = parse_cc_multireference_diagnostics(
        "T1 diagnostic ... 0.052\nD1 diagnostic ... 0.075\n",
        engine="orca", method="CCSD(T)", multiplicity=2,
    )
    assert res_open_bad["t1_exceeded"] is True
    assert res_open_bad["d1_exceeded"] is True
    assert res_open_bad["multireference_warning"] is True

    # Real CFOUR 2.1 xvcc excerpt: Lee-Taylor T1 = ||T1AA|| / sqrt(N_corr)
    cfour_out = """
    Number of electrons: 10
    dropped core orbitals: 1
    Norm of T1AA vector (       76 symmetry allowed elements):  0.0166564958.
    """
    res_c4 = parse_cc_multireference_diagnostics(cfour_out, engine="cfour", method="CCSD(T)", multiplicity=1)
    assert res_c4["t1_diagnostic"] == pytest.approx(0.0166564958 / math.sqrt(8.0), rel=1e-6)
    assert res_c4["d1_diagnostic"] is None
    assert res_c4["multireference_warning"] is False

    # Live CFOUR 2.1 xscf/xvtran/xvcc exact output format ("total electron number:" + "There is 1 frozen-core orbital.")
    cfour_21_live = """
     There is   1 frozen-core orbital.
     total electron number:   10.000000000000028
      The following   1 MOs will be dropped:
      Norm of T1AA vector (       76 symmetry allowed elements):  0.0166564790.
    """
    res_c4_live = parse_cc_multireference_diagnostics(cfour_21_live, engine="cfour", method="CCSD(T)", multiplicity=1)
    assert res_c4_live["t1_diagnostic"] == pytest.approx(0.0166564790 / math.sqrt(8.0), rel=1e-6)
    assert res_c4_live["t1_source"] == "cfour_t1_amplitude_norm"
    assert res_c4_live["d1_diagnostic"] is None


# ==============================================================================
# 4a. Automatic ORCA SCF Retry (SlowConv / KDIIS / MaxIter 300, max 2 retries)
# ==============================================================================

def test_orca_scf_retry_tiered_remediation_cap_and_collapse_fail_closed() -> None:
    base_deck = (
        "! B3LYP D3BJ def2-TZVP DEFGRID2 NoSym TightSCF\n"
        "%scf\n TolE 1.0e-10\n MaxIter 200\nend\n"
        "* xyz 0 1\nO 0 0 0\nH 0 0.757 0.586\nH 0 -0.757 0.586\n*\n"
    )
    fail_stdout = (
        "* O R C A *\n"
        "Iter 1: Energy= -76.100000 DeltaE=  1.00e-03\n"
        "Iter 2: Energy= -76.101000 DeltaE= -1.00e-03\n"
        "Iter 3: Energy= -76.100000 DeltaE=  1.00e-03\n"
        "Iter 4: Energy= -76.101000 DeltaE= -1.00e-03\n"
        "Iter 5: Energy= -76.100000 DeltaE=  1.00e-03\n"
        "SCF NOT CONVERGED AFTER 200 CYCLES\n"
    )

    # Attempt 1 -> retry 1 injects SlowConv, KDIIS, SOSCF, MaxIter 300
    d1 = prepare_orca_scf_retry(base_deck, fail_stdout, retry_index=0)
    assert d1.should_retry is True
    assert d1.retry_number == 1
    assert d1.max_retries == MAX_SCF_RETRIES == 2
    assert d1.trap_flag == "SCF_PING_PONG_DETECTED"
    assert "SlowConv" in d1.remediated_deck
    assert "KDIIS" in d1.remediated_deck
    assert "SOSCF" in d1.remediated_deck
    assert "MaxIter 300" in d1.remediated_deck

    # Attempt 2 -> retry 2 escalates to VerySlowConv + Shift + DampFac
    d2 = prepare_orca_scf_retry(d1.remediated_deck, fail_stdout, retry_index=1)
    assert d2.should_retry is True
    assert d2.retry_number == 2
    assert "VerySlowConv" in d2.remediated_deck
    assert "Shift 0.25" in d2.remediated_deck
    assert "DampFac 0.7" in d2.remediated_deck

    # Attempt 3 -> hard-capped at 2 retries, must fail closed
    d3 = prepare_orca_scf_retry(d2.remediated_deck, fail_stdout, retry_index=2)
    assert d3.should_retry is False
    assert d3.failure_detected is True
    assert any("SCF_RETRY_EXHAUSTED" in w for w in d3.warnings)

    # Terminal NaN/Inf numerical collapse -> never retried, fails closed immediately
    collapse_out = "* O R C A *\nIter 1: Energy= NaN DeltaE= Inf\nSCF NOT CONVERGED\n"
    d_nan = prepare_orca_scf_retry(base_deck, collapse_out, retry_index=0)
    assert d_nan.should_retry is False
    assert d_nan.terminal_collapse is True
    assert d_nan.trap_flag == "NUMERICAL_COLLAPSE"


# ==============================================================================
# 4b. Authentic Imaginary-Mode Eigenvector Displacement & Re-Optimization
# ==============================================================================

def _build_analytical_planar_saddle_hessian(
    coords: np.ndarray,
    *,
    inversion_curvature: float,
    stretch_k: float = 0.45,
) -> np.ndarray:
    """Build an authentic symmetric translationally/rotationally invariant 3N x 3N Hessian for NH3.

    Uses harmonic N-H bond-stretch force constants (`stretch_k > 0`) plus an out-of-plane
    umbrella coordinate curvature (`inversion_curvature < 0` at planar D3h saddle, `> 0` at C3v minimum).
    """
    n = len(coords)
    hess = np.zeros((3 * n, 3 * n), dtype=np.float64)
    # 1. Harmonic N-H radial stretches (0-1, 0-2, 0-3) and H-H bending coupling
    pairs = [(0, 1, stretch_k), (0, 2, stretch_k), (0, 3, stretch_k),
             (1, 2, 0.12), (2, 3, 0.12), (1, 3, 0.12)]
    for i, j, k_ij in pairs:
        rij = coords[j] - coords[i]
        u = rij / np.linalg.norm(rij)
        block = k_ij * np.outer(u, u)
        hess[3 * i : 3 * i + 3, 3 * i : 3 * i + 3] += block
        hess[3 * j : 3 * j + 3, 3 * j : 3 * j + 3] += block
        hess[3 * i : 3 * i + 3, 3 * j : 3 * j + 3] -= block
        hess[3 * j : 3 * j + 3, 3 * i : 3 * i + 3] -= block

    # 2. Pure out-of-plane umbrella internal coordinate q_umb = z_N - (z_H1 + z_H2 + z_H3)/3
    # (exact zero net force & zero net torque for planar D3h geometry in the xy-plane)
    g = np.zeros(3 * n, dtype=np.float64)
    g[2] = 1.0
    g[5] = -1.0 / 3.0
    g[8] = -1.0 / 3.0
    g[11] = -1.0 / 3.0
    hess += inversion_curvature * np.outer(g, g)
    return 0.5 * (hess + hess.T)


def test_imaginary_mode_displacement_and_bounded_reoptimization() -> None:
    elements = ["N", "H", "H", "H"]
    r_nh = 1.01
    planar_coords = np.array([
        [0.0, 0.0, 0.0],
        [r_nh, 0.0, 0.0],
        [-0.5 * r_nh, 0.5 * math.sqrt(3.0) * r_nh, 0.0],
        [-0.5 * r_nh, -0.5 * math.sqrt(3.0) * r_nh, 0.0],
    ], dtype=np.float64)

    saddle_hess = _build_analytical_planar_saddle_hessian(planar_coords, inversion_curvature=-0.08)
    analysis = extract_imaginary_vibrational_modes(saddle_hess, elements, planar_coords)
    assert analysis["n_imag"] == 1
    assert analysis["rigid_mode_count"] == 6
    assert analysis["imaginary_frequencies_cm1"][0] < -100.0

    # Displacement strictly breaks planar symmetry along z (the umbrella imaginary eigenvector)
    disp = displace_along_imaginary_mode(planar_coords, saddle_hess, elements, step_angstrom=0.05)
    displaced = np.asarray(disp["displaced_coordinates_angstrom"], dtype=np.float64)
    assert disp["max_atomic_displacement_angstrom"] == pytest.approx(0.05, rel=1e-6)
    assert abs(displaced[0, 2] - displaced[1, 2]) > 0.04  # Pyramid broke out of xy-plane!

    # Successful resolution on retry 1 via authentic re-optimization callback
    min_hess = _build_analytical_planar_saddle_hessian(displaced, inversion_curvature=+0.10)
    calls: list[int] = []

    def resolve_runner(next_coords: list[list[float]], attempt: int) -> tuple[dict, np.ndarray]:
        calls.append(attempt)
        return {"coordinates_angstrom": next_coords, "converged": True}, min_hess

    accepted, prov = reoptimize_orca_imaginary_modes(
        elements,
        {"coordinates_angstrom": planar_coords.tolist(), "converged": True},
        initial_hessian=saddle_hess,
        reopt_runner=resolve_runner,
    )
    assert calls == [1]
    assert prov["initial_n_imag"] == 1
    assert prov["retries_used"] == 1
    assert prov["final_n_imag"] == 0
    assert prov["resolved"] is True
    assert abs(accepted["coordinates_angstrom"][0][2] - accepted["coordinates_angstrom"][1][2]) > 0.04

    # Persistent imaginary mode fails closed after hard cap of 2 retries
    fail_calls: list[int] = []

    def persistent_saddle_runner(next_coords: list[list[float]], attempt: int) -> tuple[dict, np.ndarray]:
        fail_calls.append(attempt)
        return {"coordinates_angstrom": next_coords, "converged": True}, saddle_hess

    with pytest.raises(ImaginaryModePersistenceError) as caught:
        reoptimize_imaginary_modes(
            elements,
            {"coordinates_angstrom": planar_coords.tolist(), "converged": True},
            initial_hessian=saddle_hess,
            reopt_runner=persistent_saddle_runner,
            max_retries=5,  # Must still be hard-capped at MAX_IMAGINARY_MODE_RETRIES = 2
        )
    assert fail_calls == [1, 2]
    assert caught.value.details["retries_used"] == MAX_IMAGINARY_MODE_RETRIES == 2
    assert caught.value.details["resolved"] is False
    assert caught.value.details["final_n_imag"] == 1
