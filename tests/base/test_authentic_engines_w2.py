"""Focused Wave 2 (R-05) unit tests for authentic engine wiring and scientific fixes.

Covers:
1. Authentic NBO 7 adapter (`nbo7_execution.py`) — fail-closed binary resolution,
   ORCA %nbo input construction, banner verification, NPA/Wiberg/E(2) parsing, SHA-256.
2. Authentic Multiwfn adapter (`multiwfn_execution.py`) — fail-closed binary & <80-char
   Fortran path enforcement, QTAIM/Poincare-Hopf/BCP parsing, NCI/RDG grid statistics,
   Mayer bond order parsing, SHA-256 provenance.
3. GPU4PySCF FP64 CUDA adapter (`gpu4pyscf_execution.py` + `calculation_service.py`) —
   VV10 grid & DF auxbasis configuration, fail-closed absence of CUDA/gpu4pyscf (zero
   silent CPU downgrade), CUDA dispatch via `run_calculation(..., device="cuda")`.
4. CFOUR 2.1 spherical basis, frozen-core, open-shell, opt/freq, VPT2, and CFOURBridge
   execution/parsing (`cfour_execution.py` + `cochem_core_cfour_bridge.py`).
5. Dynamic xTB `--uhf` (`xtb_execution.py`) & molecule-agnostic Recipe R2 (`cochem_calc_input_generator.py`).
6. Repaired BibTeX DOIs and metadata in `provenance/citations.py`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from cochem_base.calc.calculation_service import CalculationMatrixConfig, run_calculation
from cochem_base.calc.cfour_execution import (
    is_supported_cfour_basis,
    supported_cfour_request,
    uses_spherical_basis,
    write_cfour_input,
)
from cochem_base.calc.cochem_calc_input_generator import (
    generate_recipe_r2_counterpoise_bracketing_decks,
    generate_recipe_r2_orca_deck,
)
from cochem_base.calc.gpu4pyscf_execution import (
    DEFAULT_AUXBASIS,
    DEFAULT_VV10_NLC_GRID,
    DEFAULT_XC_GRID,
    GPU4PySCFUnavailableError,
    build_gpu4pyscf_script,
    execute_gpu4pyscf,
    normalize_gpu4pyscf_method,
    parse_cuda_device_index,
    resolve_gpu4pyscf_python,
)
from cochem_base.calc.multiwfn_execution import (
    parse_multiwfn_mayer_bond_orders,
    parse_multiwfn_nci_output_txt,
    parse_multiwfn_qtaim,
    resolve_multiwfn_executable,
    resolve_orca_2mkl_executable,
)
from cochem_base.calc.nbo7_execution import (
    build_orca_nbo7_input,
    parse_nbo7_output,
    resolve_gennbo_executable,
    resolve_nbo7_executable,
)
from cochem_base.calc.xtb_execution import validate_xtb_config
from cochem_base.core_engine.cochem_core_cfour_bridge import (
    CFOURAnharmMode,
    CFOURBridge,
    CFOURCalcLevel,
    CFOURInputConfig,
    CFOUROutputParser,
    CFOURReference,
    generate_cfour_zmat,
)
from cochem_base.exceptions import BinaryNotFoundError
from cochem_base.provenance.citations import _AUTHORITATIVE_BIBTEX_CATALOG


# ==============================================================================
# 1. NBO 7 Adapter Contract & Parsers
# ==============================================================================

def test_nbo7_and_gennbo_fail_closed_when_absent(tmp_path: Path) -> None:
    empty_env = {"PATH": str(tmp_path)}
    with pytest.raises(FileNotFoundError):
        resolve_nbo7_executable(executable=tmp_path / "missing_nbo7.i8.exe", env=empty_env)
    with pytest.raises(FileNotFoundError):
        resolve_gennbo_executable(executable=tmp_path / "missing_gennbo.i8.exe", env=empty_env)


def test_build_orca_nbo7_input_contains_nbokeylist_and_coordinates() -> None:
    deck = build_orca_nbo7_input(
        ["O", "H", "H"],
        [(0.0, 0.0, 0.1173), (0.0, 0.7572, -0.4692), (0.0, -0.7572, -0.4692)],
        method="HF",
        basis_set="def2-SVP",
        job_name="water_nbo",
    )
    assert "! HF def2-SVP NBO" in deck
    assert "%nbo" in deck
    assert 'NBOKEYLIST "$NBO BNDIDX ARCHIVE FILE=water_nbo $END"' in deck
    assert "* xyz 0 1" in deck


def test_parse_nbo7_output_verifies_banner_and_extracts_npa_wiberg_e2() -> None:
    # Real output formatting emitted by NBO 7.0.10 (HF/def2-SVP H2O)
    nbo7_log = """
 *********************************** NBO 7.0 ***********************************
             N A T U R A L   A T O M I C   O R B I T A L   A N D
          N A T U R A L   B O N D   O R B I T A L   A N A L Y S I S
 ************************ Cite this program [NBO 7.0.10] ***********************

 Summary of Natural Population Analysis:

                                     Natural Population
             Natural    ---------------------------------------------
  Atom No    Charge        Core      Valence    Rydberg      Total
 --------------------------------------------------------------------
    O  1   -0.91638      1.99990     6.90567    0.01081     8.91638
    H  2    0.45819      0.00000     0.53907    0.00274     0.54181
    H  3    0.45819      0.00000     0.53907    0.00274     0.54181
 ====================================================================
 * Total *  0.00000      1.99990     7.98381    0.01629    10.00000

 Wiberg bond index matrix in the NAO basis:

     Atom    1       2       3
     ---- ------  ------  ------
   1.  O  0.0000  0.7897  0.7897
   2.  H  0.7897  0.0000  0.0002
   3.  H  0.7897  0.0002  0.0000

 Wiberg bond index, Totals by atom:

     Atom   Total
     ----  ------
   1.  O   1.5794
   2.  H   0.7899
   3.  H   0.7899

 SECOND ORDER PERTURBATION THEORY ANALYSIS OF FOCK MATRIX IN NBO BASIS

     Threshold for printing:   0.50 kcal/mol
                                                          E(2)  E(j)-E(i) F(i,j)
     Donor (L) NBO                 Acceptor (NL) NBO    kcal/mol   a.u.    a.u.
 ===============================================================================

 within unit  1
     2. BD ( 1) O 1- H 2          11. RY ( 3) H 3           1.12    2.41   0.047
     3. BD ( 1) O 1- H 3          10. RY ( 3) H 2           1.12    2.41   0.047
     4. LP ( 1) O 1                8. RY ( 1) H 2           0.84    2.15   0.038

 NATURAL BOND ORBITALS (Summary):
"""
    parsed = parse_nbo7_output(nbo7_log)
    assert parsed["banner_verified"] is True
    assert parsed["nbo_version"] == "NBO 7.0.10"
    assert len(parsed["npa_charges"]) == 3
    assert parsed["npa_charges"][0]["element"] == "O"
    assert parsed["npa_charges"][0]["natural_charge"] == pytest.approx(-0.91638)
    assert parsed["npa_total_charge"] == pytest.approx(0.0)
    assert parsed["npa_total_electrons"] == pytest.approx(10.0)
    assert len(parsed["wiberg_bond_order_matrix"]) == 3
    assert parsed["wiberg_bond_order_matrix"][0][1] == pytest.approx(0.7897)
    assert len(parsed["wiberg_bonds"]) == 2
    assert len(parsed["e2_interactions"]) == 3
    assert parsed["e2_interactions"][0]["donor_label"] == "BD ( 1) O 1- H 2"
    assert parsed["e2_interactions"][0]["e2_kcal_mol"] == pytest.approx(1.12)
    assert parsed["raw_output_sha256"] == hashlib.sha256(nbo7_log.encode("utf-8")).hexdigest()

    # Reject output without authentic NBO 7.x banner
    with pytest.raises(ValueError, match="NBO 7 banner"):
        parse_nbo7_output(nbo7_log.replace("NBO 7.0", "UNKNOWN").replace("NBO 7.0.10", "UNKNOWN"))


# ==============================================================================
# 2. Multiwfn Adapter Contract & Parsers
# ==============================================================================

def test_multiwfn_resolution_fails_closed_and_enforces_fortran_path_limit(tmp_path: Path) -> None:
    empty_env = {"PATH": str(tmp_path)}
    with pytest.raises(FileNotFoundError):
        resolve_multiwfn_executable(executable=tmp_path / "missing_Multiwfn_noGUI", env=empty_env)
    with pytest.raises(FileNotFoundError):
        resolve_orca_2mkl_executable(executable=tmp_path / "missing_orca_2mkl", env=empty_env)

    # Create a real file at a path > 79 chars to verify Fortran path guard triggers
    deep = tmp_path / ("a" * 45) / ("b" * 45)
    deep.mkdir(parents=True)
    bin_file = deep / "Multiwfn_noGUI"
    bin_file.write_text("#!/bin/sh\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Fortran 79-char limit"):
        resolve_multiwfn_executable(executable=bin_file, env=empty_env)


def test_parse_multiwfn_qtaim_nci_and_mayer(tmp_path: Path) -> None:
    stdout_qtaim = """
 Multiwfn -- A Multifunctional Wavefunction Analyzer
 Version 3.8(dev), update date: 2026-Aug-21
 Summary of found CPs:
 (3,-3): 3, (3,-1): 2, (3,+1): 0, (3,+3): 0
 Poincare-Hopf relationship is satisfied! ( 3 - 2 + 0 - 0 = 1 )
"""
    cpprop = """
 ----------------   CP     4,     Type (3,-1)   ----------------
 Position (Bohr):    0.0000000000    0.7200000000   -0.2500000000
 Position (Angstrom): 0.0000000000    0.3810075919   -0.1322943027
 Connected atoms:     1(O )   --     2(H )
 Density of all electrons:                0.3654120000E+00
 Lagrangian kinetic energy G(r):          0.6123400000E-01
 Potential energy density V(r):          -0.6101200000E+00
 Energy density E(r) or H(r):            -0.5488860000E+00
 Laplacian of electron density:          -0.1950608000E+01
 Electron localization function (ELF):    0.9854100000E+00
 Ellipticity of electron density:         0.0154000000E+00
 Sign(lambda2)*rho:                      -0.3654120000E+00
"""
    qtaim = parse_multiwfn_qtaim(stdout_qtaim, cpprop)
    assert qtaim["banner_verified"] is True
    assert qtaim["n_ncp"] == 3 and qtaim["n_bcp"] == 2
    assert qtaim["poincare_hopf_chi"] == 1
    assert qtaim["poincare_hopf_satisfied"] is True
    assert len(qtaim["bcps"]) == 1
    bcp = qtaim["bcps"][0]
    assert bcp["bonded_atoms"] == [
        {"atom_index": 1, "element": "O"},
        {"atom_index": 2, "element": "H"},
    ]
    assert bcp["rho"] == pytest.approx(0.365412)
    assert bcp["laplacian"] == pytest.approx(-1.950608)
    assert bcp["G"] == pytest.approx(0.061234)
    assert bcp["V"] == pytest.approx(-0.610120)
    assert bcp["H"] == pytest.approx(-0.548886)
    assert bcp["ellipticity"] == pytest.approx(0.0154)
    assert bcp["elf"] == pytest.approx(0.98541)

    with pytest.raises(ValueError, match="Authentic Multiwfn banner"):
        parse_multiwfn_qtaim("no banner here", cpprop)

    # Missing CP-count summary block MUST fail closed with explicit ValueError (never silently return 0,0,0,0 / chi=0)
    stdout_missing_summary = """
 Multiwfn -- A Multifunctional Wavefunction Analyzer
 Version 3.8(dev), update date: 2026-Aug-21
 Atoms:   3,  Basis functions:  24,  GTFs:  42
 Topology analysis aborted before critical point summary.
"""
    with pytest.raises(ValueError, match="Multiwfn QTAIM output missing critical-point summary"):
        parse_multiwfn_qtaim(stdout_missing_summary)
    with pytest.raises(ValueError, match="Multiwfn QTAIM output missing critical-point summary"):
        parse_multiwfn_qtaim(stdout_missing_summary, cpprop)

    # Explicit ncp_matches_atoms check: None when atom count unknown, bool when known from stdout or expected_atoms
    assert qtaim["atom_count"] is None
    assert qtaim["ncp_matches_atoms"] is None

    qtaim_expected_ok = parse_multiwfn_qtaim(stdout_qtaim, cpprop, expected_atoms=3)
    assert qtaim_expected_ok["atom_count"] == 3
    assert qtaim_expected_ok["ncp_matches_atoms"] is True

    qtaim_expected_mismatch = parse_multiwfn_qtaim(stdout_qtaim, cpprop, expected_atoms=2)
    assert qtaim_expected_mismatch["atom_count"] == 2
    assert qtaim_expected_mismatch["ncp_matches_atoms"] is False

    stdout_with_atoms_match = """
 Multiwfn -- A Multifunctional Wavefunction Analyzer
 Version 3.8(dev), update date: 2026-Aug-21
 Atoms:   3,  Basis functions:  24,  GTFs:  42
 Summary of found CPs:
 (3,-3): 3, (3,-1): 2, (3,+1): 0, (3,+3): 0
"""
    qtaim_auto_atoms = parse_multiwfn_qtaim(stdout_with_atoms_match)
    assert qtaim_auto_atoms["atom_count"] == 3
    assert qtaim_auto_atoms["ncp_matches_atoms"] is True

    stdout_with_nna = stdout_with_atoms_match.replace("(3,-3): 3", "(3,-3): 4")
    qtaim_nna = parse_multiwfn_qtaim(stdout_with_nna)
    assert qtaim_nna["atom_count"] == 3
    assert qtaim_nna["n_ncp"] == 4
    assert qtaim_nna["ncp_matches_atoms"] is False

    with pytest.raises(ValueError, match="expected_atoms"):
        parse_multiwfn_qtaim(stdout_qtaim, expected_atoms=0)
    with pytest.raises(ValueError, match="expected_atoms"):
        parse_multiwfn_qtaim(stdout_qtaim, expected_atoms=True)

    # NCI output.txt grid stats (columns: x y z sign(lambda2)*rho RDG)
    nci_file = tmp_path / "output.txt"
    nci_file.write_text(
        "0.0 0.0 0.0 -0.0250 0.15\n"
        "0.1 0.0 0.0 -0.0040 0.25\n"
        "0.2 0.0 0.0  0.0020 0.30\n"
        "0.3 0.0 0.0  0.0310 0.20\n"
        "0.4 0.0 0.0 -0.0500 1.20\n",
        encoding="utf-8",
    )
    nci = parse_multiwfn_nci_output_txt(nci_file, rdg_cutoff=0.5)
    assert nci["total_grid_points"] == 5
    assert nci["nci_grid_points"] == 4
    assert nci["strong_attraction_count"] == 1
    assert nci["vdw_count"] == 2
    assert nci["steric_count"] == 1
    assert nci["output_txt_sha256"] == hashlib.sha256(nci_file.read_bytes()).hexdigest()

    # Mayer bond orders
    stdout_mayer = """
 Multiwfn -- A Multifunctional Wavefunction Analyzer
 Version 3.8(dev)
   #    1:    1(O )    2(H )   0.95449002
   #    2:    1(O )    3(H )   0.95449002
 Total valences and free valences defined by Mayer:
 Atom    1(O ):   1.90898004   0.00000000
"""
    mayer = parse_multiwfn_mayer_bond_orders(stdout_mayer)
    assert len(mayer["mayer_bonds"]) == 2
    assert mayer["mayer_bonds"][0]["mayer_bond_order"] == pytest.approx(0.95449002)
    assert mayer["mayer_valences"][0]["total_valence"] == pytest.approx(1.90898004)


# ==============================================================================
# 3. GPU4PySCF FP64 CUDA Adapter & Service Dispatch
# ==============================================================================

def test_gpu4pyscf_method_normalization_and_script_generation() -> None:
    assert normalize_gpu4pyscf_method("wB97M-V") == ("wb97m_v", False, True)
    assert normalize_gpu4pyscf_method("wB97X-V") == ("wb97x_v", False, True)
    assert normalize_gpu4pyscf_method("PBE0") == ("pbe0", False, False)
    assert normalize_gpu4pyscf_method("HF") == ("HF", True, False)
    assert parse_cuda_device_index("cuda") == 0
    assert parse_cuda_device_index("cuda:1") == 1
    with pytest.raises(ValueError):
        parse_cuda_device_index("mps")

    script, spec = build_gpu4pyscf_script(
        ["O", "H"],
        [(0.0, 0.0, 0.0), (0.0, 0.0, 0.97)],
        method="wB97X-V",
        basis_set="def2-SVP",
        multiplicity=2,
        is_opt=True,
    )
    assert spec["auxbasis"] == DEFAULT_AUXBASIS == "def2-universal-jkfit"
    assert tuple(spec["xc_grid"]) == DEFAULT_XC_GRID == (99, 590)
    assert tuple(spec["nlc_grid"]) == DEFAULT_VV10_NLC_GRID == (50, 194)
    assert spec["unrestricted"] is True
    assert spec["uses_vv10"] is True
    assert "density_fit(auxbasis=spec[\"auxbasis\"])" in script
    assert "mf.nlcgrids.atom_grid" in script
    assert "FP64" in script


def test_gpu4pyscf_fails_closed_without_cuda_and_service_routes_cuda(tmp_path: Path) -> None:
    # CUDA_VISIBLE_DEVICES="" must fail closed with GPU4PySCFUnavailableError (never CPU fallback)
    with pytest.raises(GPU4PySCFUnavailableError, match="never downgrades to CPU"):
        resolve_gpu4pyscf_python(env={"CUDA_VISIBLE_DEVICES": ""})
    with pytest.raises(GPU4PySCFUnavailableError):
        execute_gpu4pyscf(
            ["H", "H"],
            [(0.0, 0.0, 0.0), (0.0, 0.0, 0.74)],
            directory=tmp_path / "gpu_disabled",
            env={"CUDA_VISIBLE_DEVICES": ""},
        )

    # Service dry-run accepts engine="pyscf" + device="cuda" AND engine="gpu4pyscf"
    cfg_pyscf = CalculationMatrixConfig(
        geometry="O 0 0 0\nH 0 0.757 0.586\nH 0 -0.757 0.586\n",
        engine="pyscf",
        method="wB97M-V",
        basis_set="def2-SVP",
        is_opt=False,
    )
    cfg_path = tmp_path / "pyscf_cuda.json"
    cfg_path.write_text(cfg_pyscf.model_dump_json(), encoding="utf-8")
    res = run_calculation(cfg_path, dry_run=True, device="cuda", scratch=tmp_path / "scratch")
    assert res["status"] == "DECK_GENERATED"
    assert res["engine"] == "gpu4pyscf"
    assert res["device"] == "cuda"
    decks = list(Path(res["scratch_dir"]).glob("*_gpu4pyscf.py"))
    assert len(decks) == 1
    assert "def2-universal-jkfit" in decks[0].read_text(encoding="utf-8")

    # Engine="gpu4pyscf" rejects explicit CPU downgrade
    raw_gpu = cfg_pyscf.model_dump(mode="json")
    raw_gpu["engine"] = "gpu4pyscf"
    gpu_path = tmp_path / "gpu4pyscf_engine.json"
    gpu_path.write_text(json.dumps(raw_gpu), encoding="utf-8")
    with pytest.raises(ValueError, match="refusing CPU downgrade"):
        run_calculation(gpu_path, dry_run=True, device="cpu", scratch=tmp_path / "scratch2")

    # CPU-only engines (orca, xtb) still reject --device cuda
    cfg_orca = cfg_pyscf.model_copy(update={"engine": "orca"})
    orca_path = tmp_path / "orca_cuda.json"
    orca_path.write_text(cfg_orca.model_dump_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="does not support --device cuda"):
        run_calculation(orca_path, dry_run=True, device="cuda", scratch=tmp_path / "scratch3")


# ==============================================================================
# 4. CFOUR 2.1 Spherical Basis, Open-Shell, VPT2 & CFOURBridge
# ==============================================================================

@pytest.mark.parametrize("basis,expected_spherical", [
    ("cc-pVDZ", True),
    ("aug-cc-pVTZ", True),
    ("cc-pCVTZ", True),
    ("ANO1", True),
    ("def2-TZVP", True),
    ("def2-QZVPP", True),
    ("STO-3G", False),
    ("6-31G**", False),
])
def test_cfour_spherical_basis_classification_and_zmat_keywords(
    tmp_path: Path, basis: str, expected_spherical: bool
) -> None:
    assert is_supported_cfour_basis(basis)
    assert uses_spherical_basis(basis) is expected_spherical

    cfg = CalculationMatrixConfig(
        geometry="O 0 0 0\nH 0 0.757 0.586\nH 0 -0.757 0.586\n",
        engine="cfour",
        method="CCSD(T)",
        basis_set=basis,
        is_opt=False,
    )
    assert supported_cfour_request(cfg)
    zmat = write_cfour_input(
        tmp_path / basis.replace("*", "s"),
        cfg,
        ["O", "H", "H"],
        [(0.0, 0.0, 0.0), (0.0, 0.757, 0.586), (0.0, -0.757, 0.586)],
    )
    content = zmat.read_text(encoding="utf-8")
    assert f"SPHERICAL={'ON' if expected_spherical else 'OFF'}" in content
    assert "FROZEN_CORE=ON" in content
    assert "REFERENCE=RHF" in content
    assert "MULTIPLICITY=1" in content


def test_cfour_open_shell_frozen_core_override_and_vpt2_zmat(tmp_path: Path) -> None:
    # Open-shell OH radical with ROHF override and FROZEN_CORE=OFF
    cfg_oh = CalculationMatrixConfig(
        geometry="O 0 0 0\nH 0 0 0.97\n",
        engine="cfour",
        method="CCSD(T)",
        basis_set="cc-pVDZ",
        multiplicity=2,
        is_opt=False,
    )
    assert supported_cfour_request(cfg_oh)
    zmat_oh = write_cfour_input(
        tmp_path / "oh", cfg_oh, ["O", "H"], [(0.0, 0.0, 0.0), (0.0, 0.0, 0.97)],
        reference="ROHF", frozen_core=False,
    )
    txt_oh = zmat_oh.read_text(encoding="utf-8")
    assert "REFERENCE=ROHF" in txt_oh
    assert "MULTIPLICITY=2" in txt_oh
    assert "SPHERICAL=ON" in txt_oh
    assert "FROZEN_CORE=OFF" in txt_oh
    assert "CC_PROG=VCC" in txt_oh

    # VPT2 ZMAT generation
    cfg_vpt2 = CalculationMatrixConfig(
        geometry="O 0 0 0\nH 0 0.757 0.586\nH 0 -0.757 0.586\n",
        engine="cfour",
        method="MP2",
        basis_set="cc-pVDZ",
        is_opt=False,
        is_freq=True,
        is_vpt2=True,
    )
    zmat_vpt2 = write_cfour_input(
        tmp_path / "vpt2", cfg_vpt2, ["O", "H", "H"],
        [(0.0, 0.0, 0.0), (0.0, 0.757, 0.586), (0.0, -0.757, 0.586)],
        anharmonic=True,
    )
    txt_vpt2 = zmat_vpt2.read_text(encoding="utf-8")
    assert "VIB=EXACT" in txt_vpt2
    assert "ANHARM=VPT2" in txt_vpt2
    assert "SPHERICAL=ON" in txt_vpt2

    # Bridge ZMAT open-shell + VPT2 + memory_size_mb
    bridge_cfg = CFOURInputConfig(
        calc_level=CFOURCalcLevel.CCSD_T,
        basis="cc-pVDZ",
        multiplicity=2,
        reference=CFOURReference.RHF,  # Auto-upgraded to UHF for mult > 1
        anharm_mode=CFOURAnharmMode.VPT2,
        memory_size_mb=512,
    )
    zmat_bridge = generate_cfour_zmat(["O", "H"], np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.97]]), bridge_cfg)
    assert "REFERENCE=UHF" in zmat_bridge
    assert "MULTIPLICITY=2" in zmat_bridge
    assert "SPHERICAL=ON" in zmat_bridge
    assert "ANHARM=VPT2" in zmat_bridge
    assert "MEMORY_SIZE=512" in zmat_bridge and "MEM_UNIT=MB" in zmat_bridge


def test_cfour_bridge_parser_extracts_vpt2_rotational_and_quartic_constants() -> None:
    # Real CFOUR 2.1 VPT2 output formatting (HF/STO-3G H2O)
    cfour_vpt2_out = """
    --executable xscf finished with status     0
    E(SCF)=        -74.965876157833
    SCF has converged.

    Equilibrium dipole moment:   0.675123 a.u. (  1.716100 D )

    Parameter                 (MHz)                  (cm-1)
    A-reduced centrifugal distortion parameters (Ir representation)

               DELJ              0.239754E+02           0.799734E-03
               DELK              0.278863E+03           0.930186E-02
               DELJK             -.684614E+02           -.228363E-02
               delJ              0.947278E+01           0.315978E-03
               delK              0.767277E+01           0.255936E-03

    S-reduced centrifugal distortion parameters (Ir representation)

               DJ                0.230450E+02           0.768698E-03
               DK                0.274211E+03           0.914668E-02
               DJK               -.628788E+02           -.209741E-02
               D1                -.947278E+01           -.315978E-03
               D2                -.465213E+00           -.155179E-04
    ------------------------------------------------------------

     Be, B0 AND B-B0 SHIFTS FOR SINGLY EXCITED VIBRATIONAL STATES (MHz)
    VIBRATION            X AXIS               Y AXIS                 Z AXIS
    ----------------------------------------------------------------------------
      Be               268534.14657221      698399.02793489      436285.90067382
      B0               263965.28391538      706998.00206459      434486.02855063
    ----------------------------------------------------------------------------

    HARMONIC AND FUNDAMENTAL FREQUENCIES (cm-1) AND INTENSITIES (km/mol)
    --------------------------------------------------------------------------------
             Harmonic     Fundamental Anharmonic    Harmonic   Fundamental  Anharm
      Mode   Frequency    Frequency   Contribution  Intensity  Intensity    Contrib
        7   2170.0456   2123.6825      -46.3630      7.2378       7.2172     -0.0206
        8   4140.0029   4014.8420     -125.1609     44.2878      38.6632     -5.6247
        9   4391.0679   4265.4877     -125.5801     29.9726      28.9705     -1.0021
    --------------------------------------------------------------------------------
                             ZERO-POINT VIBRATIONAL ENERGIES
    --------------------------------------------------------------------------------
                                kcal/mol      kJ/mol        Hartree        cm-1
    --------------------------------------------------------------------------------
    Harmonic contribution :       15.2980      64.0068      0.02437894      5350.558
    VPT2-correction       :       -0.1610      -0.6737     -0.00025660       -56.317
    --------------------------------------------------------------------------------
    Harm+VPT2             :       15.1370      63.3331      0.02412234      5294.241
    --------------------------------------------------------------------------------
    --executable xcubic finished with status     0
      The final electronic energy is       -74.965876157833421 a.u.
"""
    obs = CFOUROutputParser.parse_cfour_stdout(
        cfour_vpt2_out,
        symbols_fallback=["O", "H", "H"],
        coordinates_fallback=np.array([[0.0, 0.0, 0.1173], [0.0, 0.7572, -0.4692], [0.0, -0.7572, -0.4692]]),
    )
    assert obs.final_energy_hartree == pytest.approx(-74.965876157833421)
    assert obs.harmonic_force_field.frequencies_cm_inv == pytest.approx([2170.0456, 4140.0029, 4391.0679])
    assert obs.fundamental_frequencies_cm_inv == pytest.approx([2123.6825, 4014.8420, 4265.4877])
    assert obs.anharmonic_contributions_cm_inv == pytest.approx([-46.3630, -125.1609, -125.5801])
    assert obs.Ae_MHz == pytest.approx(698399.02793489)
    assert obs.A0_MHz == pytest.approx(706998.00206459)
    assert obs.B0_MHz == pytest.approx(434486.02855063)
    assert obs.C0_MHz == pytest.approx(263965.28391538)
    assert obs.vpt2_zpe_cm_inv == pytest.approx(5294.241)
    assert obs.quartic_distortion is not None
    # MHz -> kHz conversion (* 1000.0)
    assert obs.quartic_distortion.Delta_J_kHz == pytest.approx(23975.4)
    assert obs.quartic_distortion.D_J_kHz == pytest.approx(23045.0)


# ==============================================================================
# 5. Dynamic xTB --uhf & Molecule-Agnostic Recipe R2
# ==============================================================================

def test_xtb_dynamic_uhf_for_singlet_doublet_and_triplet() -> None:
    cfg_singlet = CalculationMatrixConfig(
        geometry="H 0 0 0\nH 0 0 0.74\n", engine="xtb", method="GFN2-xTB", basis_set=None, multiplicity=1, is_opt=False
    )
    args_s = validate_xtb_config(cfg_singlet, ["H", "H"])
    assert args_s[args_s.index("--uhf") + 1] == "0"

    cfg_doublet = CalculationMatrixConfig(
        geometry="O 0 0 0\nH 0 0 0.97\n", engine="xtb", method="GFN2-xTB", basis_set=None, multiplicity=2, is_opt=False
    )
    args_d = validate_xtb_config(cfg_doublet, ["O", "H"], allow_open_shell=True)
    assert args_d[args_d.index("--uhf") + 1] == "1"

    cfg_triplet = CalculationMatrixConfig(
        geometry="O 0 0 0\nO 0 0 1.21\n", engine="xtb", method="GFN2-xTB", basis_set=None, multiplicity=3, is_opt=False
    )
    args_t = validate_xtb_config(cfg_triplet, ["O", "O"], allow_open_shell=True)
    assert args_t[args_t.index("--uhf") + 1] == "2"

    # Incompatible electron parity must still raise ValueError
    with pytest.raises(ValueError, match="incompatible with the electron count"):
        validate_xtb_config(cfg_doublet, ["H", "H"], allow_open_shell=True)


def test_recipe_r2_rejects_missing_geometry_and_invalid_cp_and_runs_generic_dimer(
    tmp_path: Path, configured_registry
) -> None:
    with pytest.raises(ValueError, match="Explicit symbols and coordinates"):
        generate_recipe_r2_orca_deck(output_dir=tmp_path)

    syms = ["F", "H", "F", "H"]
    coords = np.array([
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 0.92],
        [0.0, 0.0, 2.75],
        [0.0, 0.5, 3.55],
    ], dtype=np.float64)
    with pytest.raises(ValueError, match="CP"):
        generate_recipe_r2_orca_deck(
            basin_id="hf_dimer", symbols=syms, coordinates=coords, counterpoise=True, output_dir=tmp_path
        )
    decks = generate_recipe_r2_counterpoise_bracketing_decks(
        basin_id="hf_dimer", symbols=syms, coordinates=coords,
        monomer_a_indices=(0, 1), monomer_b_indices=(2, 3), output_dir=tmp_path,
    )
    assert set(decks) == {"dimer", "monomer_a_ghosts", "monomer_b_ghosts"}
    leg2 = decks["monomer_a_ghosts"].read_text(encoding="utf-8")
    assert "F:" in leg2 and "H:" in leg2
    assert " CP" not in leg2


# ==============================================================================
# 6. Repaired Citations & DOIs in provenance/citations.py
# ==============================================================================

def test_repaired_five_dois_and_metadata_in_citations_catalog() -> None:
    c_gpu = _AUTHORITATIVE_BIBTEX_CATALOG["gpu4pyscf"]
    assert c_gpu.doi == "10.1021/acs.jpca.4c05876"
    assert "10.1021/acs.jpca.4c05876" in c_gpu.bibtex
    assert "1459" in c_gpu.bibtex and "129" in c_gpu.bibtex and "2025" in c_gpu.bibtex
    assert "10.1063/5.0223707" not in c_gpu.bibtex

    c_gpu_wires = _AUTHORITATIVE_BIBTEX_CATALOG["gpu4pyscf_wires"]
    assert c_gpu_wires.doi == "10.1002/wcms.70008"

    c_aimnet = _AUTHORITATIVE_BIBTEX_CATALOG["aimnet2"]
    assert c_aimnet.doi == "10.1039/d4sc08572h"
    assert "10.1039/d4sc08572h" in c_aimnet.bibtex
    assert "10.1021/acs.jcim.4c00445" not in c_aimnet.bibtex

    c_wb97xv = _AUTHORITATIVE_BIBTEX_CATALOG["wb97x_v"]
    assert c_wb97xv.doi == "10.1039/c3cp54374a"
    assert "10.1039/c3cp54374a" in c_wb97xv.bibtex
    assert "10.1039/C4CP00288E" not in c_wb97xv.bibtex

    c_crest = _AUTHORITATIVE_BIBTEX_CATALOG["crest"]
    assert c_crest.doi == "10.1039/C9CP06869D"
    assert "7169--7192" in c_crest.bibtex
    assert "5169--5181" not in c_crest.bibtex

    c_mace = _AUTHORITATIVE_BIBTEX_CATALOG["mace_off23"]
    assert c_mace.doi == "10.1021/jacs.4c07099"
    assert "147" in c_mace.bibtex and "17598--17611" in c_mace.bibtex and "2025" in c_mace.bibtex
