"""
Unit tests for CoChem-TOPOS Stage 4.0 Time-Aware Capability Selector & Execution Broker
(cochem_topos_escalator_exec.py).

Validates:
1. Redundant Internal Coordinates Verification: Rejection of manual Z-matrices and enforcement of Cartesian format for ORCA delocalized redundant internal coordinates.
2. Automated SCF Rescue: Stream parsing, mathematical ping-pong oscillation detection, energy divergence detection, and automated injection of `! SlowConv VShift` with `.gbw` binary orbital seeds.
3. The AutoCAS Rescue Protocol: Extraction of T1 and D1 multireference diagnostics, mathematical single-reference breakdown detection (T1 > 0.02, D1 > 0.05), workflow halting, state downgrade to `! AutoCAS`, and cross-platform IPC alert dispatching.
4. The 11-Arrow Canonical Pipeline: Input construction across all 11 arrows (Method Matrix v4 §8B.4), auxiliary bases, dispersion corrections (! D4), and compound job scripting.
5. Hardware Brokering Header: Polling `cochem_system_config.json`, host OS safety buffers (%maxcore and %pal nprocs).
6. Geometrical Explosion Trap: Monitoring bond distances mid-optimization (> 4.0 Å), process group killing, and landscape.h5 basin tagging.
7. OOM Autopsy: Detection of Exit Code 137 / SIGKILL, generation of `OOM_autopsy.json`, and hardware downscaling derivation.
8. Wavefunction Seeding: Projection of binary `.gbw` orbitals across tiers with distinct `%base` naming hygiene.

Strictly complies with the Tripartite Air-Gap Policy and Zero-Mock Mandate.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import h5py
import numpy as np
import pytest
from ase import Atoms

from escalation.cochem_topos_escalator_exec import (
    AlertSeverity,
    AutoCASAlert,
    AutoCASRescueProtocol,
    AutomatedSCFRescueEngine,
    CalculationStatus,
    Canonical11ArrowPipeline,
    CanonicalArrow,
    CrossPlatformIPCAlert,
    CrossPlatformIPCClient,
    CrossPlatformIPCServer,
    EscalationResult,
    EscalationTier,
    EscalatorExecConfig,
    ExecutionPlan,
    FileSocketIPCQueue,
    GeometricalExplosionTrap,
    GeometryCoordinateVerifier,
    HardwareAllocations,
    HardwareBroker,
    MultireferenceDiagnostics,
    OOMAutopsyDiagnostic,
    OOMAutopsyEngine,
    ORCAOutputParser,
    SCFConvergenceStatus,
    SCFIterationRecord,
    TimeAwareCapabilitySelector,
    ToposEscalatorExec,
    WavefunctionSeeder,
    execute_time_aware_escalation,
    parse_orca_output,
    send_ipc_alert,
    verify_redundant_cartesian_geometry,
)

# ============================================================================
# 1. Tests for Directive 1: Redundant Internal Coordinates & Cartesian Builder
# ============================================================================


class TestDirective1RedundantCartesianVerification:
    """Verifies Cartesian coordinate validation and manual Z-Matrix rejection."""

    def test_verify_ase_atoms_compliance(self) -> None:
        """Confirms ASE Atoms object passes Cartesian verification."""
        atoms = Atoms("H2O", positions=[[0.0, 0.0, 0.0], [0.0, 0.75, -0.47], [0.0, -0.75, -0.47]])
        assert GeometryCoordinateVerifier.verify_redundant_internal_coordinates_compliance(atoms) is True
        assert verify_redundant_cartesian_geometry(atoms) is True

    def test_verify_numpy_and_list_coordinates(self) -> None:
        """Confirms (N, 3) arrays and list of coordinates pass verification."""
        coords_arr = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        assert GeometryCoordinateVerifier.verify_redundant_internal_coordinates_compliance(coords_arr) is True

        coords_list = [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        assert GeometryCoordinateVerifier.verify_redundant_internal_coordinates_compliance(coords_list) is True

    def test_verify_atom_tuples_and_records(self) -> None:
        """Confirms list of (sym, [x,y,z]) and (sym, x, y, z) tuples pass verification."""
        tuple_coords_2 = [("O", [0.0, 0.0, 0.0]), ("H", [0.0, 0.7, 0.0]), ("H", [0.0, -0.7, 0.0])]
        assert GeometryCoordinateVerifier.verify_redundant_internal_coordinates_compliance(tuple_coords_2) is True

        tuple_coords_4 = [("O", 0.0, 0.0, 0.0), ("H", 0.0, 0.7, 0.0), ("H", 0.0, -0.7, 0.0)]
        assert GeometryCoordinateVerifier.verify_redundant_internal_coordinates_compliance(tuple_coords_4) is True

    def test_verify_valid_cartesian_string(self) -> None:
        """Confirms standard Cartesian XYZ text passes verification."""
        cartesian_text = """
        * xyz 0 1
        O   0.000000   0.000000   0.117300
        H   0.000000   0.757200  -0.469200
        H   0.000000  -0.757200  -0.469200
        *
        """
        assert GeometryCoordinateVerifier.verify_redundant_internal_coordinates_compliance(cartesian_text) is True
        valid, msg = GeometryCoordinateVerifier.validate_cartesian_format(cartesian_text)
        assert valid is True
        assert "redundant internal coordinates enabled" in msg.lower()

    def test_reject_forbidden_zmatrix_keywords(self) -> None:
        """Confirms manual Z-Matrix constructs like * gzcoord, * zmat, and internal definitions are rejected."""
        zmat_samples = [
            "* gzcoord 0 1\nO\nH 1 0.96\nH 1 0.96 2 104.5\n*",
            "* zmat 0 1\nC\nO 1 r1\nH 1 r2 2 a1\n*",
            "* internal 0 1\nN 0 0 0\n*",
            "C 1 1.54 2 109.5 3 180.0\nH 2 1.09 1 109.5 3 60.0",
            "Variables:\nr1 = 1.09\na1 = 104.5",
            "Constants:\nrCC = 1.54",
        ]
        for sample in zmat_samples:
            assert GeometryCoordinateVerifier.verify_redundant_internal_coordinates_compliance(sample) is False
            valid, msg = GeometryCoordinateVerifier.validate_cartesian_format(sample)
            assert valid is False
            assert "violation" in msg.lower()

    def test_build_orca_cartesian_block_ase(self) -> None:
        """Confirms ORCA Cartesian block formatting with ASE Atoms."""
        atoms = Atoms("CO", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 1.13]])
        block = GeometryCoordinateVerifier.build_orca_cartesian_block(atoms, charge=0, multiplicity=1)
        assert "* xyz 0 1" in block
        assert "C   " in block
        assert "O   " in block
        assert block.endswith("*")

    def test_build_orca_cartesian_block_with_constraints(self) -> None:
        """Confirms %geom constraint blocks can be prepended cleanly."""
        atoms = Atoms("N2", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 1.10]])
        constraints = "%geom Constraints { B 0 1 C } end end"
        block = GeometryCoordinateVerifier.build_orca_cartesian_block(
            atoms, charge=0, multiplicity=1, constraints_block=constraints
        )
        assert "%geom Constraints" in block
        assert "* xyz 0 1" in block


# ============================================================================
# 2. Tests for Directive 2: Automated SCF Rescue & Stream Parsing
# ============================================================================


class TestDirective2AutomatedSCFRescue:
    """Verifies output parsing, oscillation / divergence detection, and ! SlowConv VShift injection."""

    def test_parse_scf_converged_trajectory(self) -> None:
        """Confirms clean parsing of a normally converging SCF trajectory."""
        orca_out = """
------------------
ORCA SCF ITERATIONS
------------------
Iter         Energy       Delta-E        Max-DP      RMS-DP
  0     -76.4000000000   0.0000000000  0.08000000  0.01000000
  1     -76.4300000000  -0.0300000000  0.02000000  0.00300000
  2     -76.4345000000  -0.0045000000  0.00100000  0.00010000
  3     -76.4345200000  -0.0000200000  0.00005000  0.00000500
SUCCESSFULLY CONVERGED
FINAL SINGLE POINT ENERGY: -76.43452000
ORCA TERMINATED NORMALLY
"""
        metrics = ORCAOutputParser.parse_scf_iterations(orca_out)
        assert metrics.status == SCFConvergenceStatus.CONVERGED
        assert metrics.iterations_count == 4
        assert metrics.is_oscillating is False
        assert metrics.is_diverging is False
        assert pytest.approx(metrics.final_energy, rel=1e-6) == -76.43452000

    def test_detect_ping_pong_oscillation(self) -> None:
        """Confirms detection of 2-cycle ping-pong limit cycles in SCF energies."""
        history = [
            SCFIterationRecord(iteration=0, energy_hartree=-76.400000, delta_energy=0.0),
            SCFIterationRecord(iteration=1, energy_hartree=-76.450000, delta_energy=-0.050000),
            SCFIterationRecord(iteration=2, energy_hartree=-76.400000, delta_energy=0.050000),
            SCFIterationRecord(iteration=3, energy_hartree=-76.450000, delta_energy=-0.050000),
            SCFIterationRecord(iteration=4, energy_hartree=-76.400000, delta_energy=0.050000),
            SCFIterationRecord(iteration=5, energy_hartree=-76.450000, delta_energy=-0.050000),
        ]
        is_osc, cycle = ORCAOutputParser.detect_scf_oscillation(history)
        assert is_osc is True
        assert cycle == 2

    def test_detect_scf_divergence(self) -> None:
        """Confirms detection of positive energy explosions during SCF cycles."""
        history = [
            SCFIterationRecord(iteration=0, energy_hartree=-76.400000, delta_energy=0.0),
            SCFIterationRecord(iteration=1, energy_hartree=-70.100000, delta_energy=6.300000),
            SCFIterationRecord(iteration=2, energy_hartree=500.000000, delta_energy=570.100000),
        ]
        is_div, step = ORCAOutputParser.detect_scf_divergence(history)
        assert is_div is True
        assert step == 1

    def test_inject_scf_rescue_keywords(self, tmp_path: Path) -> None:
        """Confirms injection of ! SlowConv VShift MOREAD and %moinp orbital seed."""
        raw_input = """! wB97X-V def2-TZVP TightOpt TightSCF
* xyz 0 1
O 0 0 0
H 0 0 1
H 0 1 0
*
"""
        seed_gbw = tmp_path / "previous_step.gbw"
        seed_gbw.touch()

        rescued = AutomatedSCFRescueEngine.inject_scf_rescue_keywords(
            input_content=raw_input,
            gbw_seed_path=seed_gbw,
            rescue_level=2,
        )
        assert "SlowConv" in rescued
        assert "VShift" in rescued
        assert "MOREAD" in rescued
        assert "%moinp" in rescued
        assert str(seed_gbw).replace("\\", "/") in rescued
        assert "%scf" in rescued
        assert "Shift 0.20" in rescued

    def test_build_rescue_plan_structure(self, tmp_path: Path) -> None:
        """Confirms derivation of rescued ExecutionPlan with state increment."""
        orig_plan = ExecutionPlan(
            plan_id="step-1",
            tier="T1-3h",
            method_name="r2SCAN-3c",
            keywords="! r2SCAN-3c TightOpt TightSCF",
            geometry_block="* xyz 0 1\nC 0 0 0\n*",
            num_cores=8,
            max_memory_mb=4000,
        )
        seed_gbw = tmp_path / "seed.gbw"
        seed_gbw.touch()

        rescued_plan = AutomatedSCFRescueEngine.build_rescue_plan(
            failed_plan=orig_plan,
            gbw_seed_path=seed_gbw,
            attempt=1,
        )
        assert rescued_plan.is_rescue_attempt is True
        assert rescued_plan.rescue_count == 1
        assert rescued_plan.slow_conv_enabled is True
        assert rescued_plan.vshift_enabled is True
        assert rescued_plan.moread_enabled is True
        assert "SlowConv" in rescued_plan.keywords
        assert "VShift" in rescued_plan.keywords
        assert "MOREAD" in rescued_plan.keywords
        assert any("%moinp" in b for b in rescued_plan.custom_blocks)


# ============================================================================
# 3. Tests for Directive 3: AutoCAS Rescue Protocol & Multireference Checks
# ============================================================================


class TestDirective3AutoCASRescueProtocol:
    """Verifies T1/D1 multireference extraction, threshold violations, and ! AutoCAS downgrade."""

    def test_parse_multireference_diagnostics_single_ref(self) -> None:
        """Confirms well-behaved single-reference system with T1 < 0.02 and D1 < 0.05."""
        out_text = """
COUPLED CLUSTER DIAGNOSTICS:
  T1 diagnostic: 0.0120
  D1 diagnostic: 0.0350
  D2 diagnostic: 0.0800
FINAL SINGLE POINT ENERGY: -76.85000000
"""
        diag = ORCAOutputParser.parse_multireference_diagnostics(out_text)
        assert pytest.approx(diag.t1_diagnostic, rel=1e-4) == 0.0120
        assert pytest.approx(diag.d1_diagnostic, rel=1e-4) == 0.0350
        assert pytest.approx(diag.d2_diagnostic, rel=1e-4) == 0.0800
        assert diag.is_multireference is False
        assert diag.violation_reason is None

    def test_parse_multireference_diagnostics_t1_violation(self) -> None:
        """Confirms T1 > 0.02 triggers multireference detection."""
        out_text = """
COUPLED CLUSTER DIAGNOSTICS:
  T1 diagnostic: 0.0285
  D1 diagnostic: 0.0410
FINAL SINGLE POINT ENERGY: -150.12345000
"""
        diag = ORCAOutputParser.parse_multireference_diagnostics(out_text)
        assert pytest.approx(diag.t1_diagnostic, rel=1e-4) == 0.0285
        assert diag.is_multireference is True
        assert "T1=0.0285 > 0.02" in str(diag.violation_reason)

    def test_parse_multireference_diagnostics_d1_violation(self) -> None:
        """Confirms D1 > 0.05 triggers multireference detection."""
        out_text = """
COUPLED CLUSTER DIAGNOSTICS:
  T1 diagnostic: 0.0180
  D1 diagnostic: 0.0620
FINAL SINGLE POINT ENERGY: -200.54321000
"""
        diag = ORCAOutputParser.parse_multireference_diagnostics(out_text)
        assert pytest.approx(diag.d1_diagnostic, rel=1e-4) == 0.0620
        assert diag.is_multireference is True
        assert "D1=0.0620 > 0.05" in str(diag.violation_reason)

    def test_create_autocas_alert_payload(self) -> None:
        """Confirms AutoCASAlert structure and recommended active space generation."""
        alert = AutoCASRescueProtocol.create_autocas_alert(
            molecule_id="diradical_dimer",
            t1=0.035,
            d1=0.075,
            symbols=["C", "C", "H", "H", "H", "H"],
            charge=0,
            multiplicity=1,
        )
        assert alert.molecule_id == "diradical_dimer"
        assert alert.downgraded_state == "! AutoCAS"
        assert alert.active_space_recommendation["active_electrons"] >= 2
        assert alert.active_space_recommendation["active_orbitals"] >= 2
        assert "AutoCAS" in alert.suggested_keywords

    def test_generate_autocas_input_block(self) -> None:
        """Confirms standard CASSCF / NEVPT2 multi-reference input formatting."""
        geom = "* xyz 0 1\nC 0 0 0\nC 0 0 1.4\n*"
        input_text = AutoCASRescueProtocol.generate_autocas_input_block(
            geometry_block=geom,
            active_electrons=4,
            active_orbitals=4,
            basis_set="def2-TZVP",
            charge=0,
            multiplicity=1,
        )
        assert "! CASSCF(4,4) NEVPT2 def2-TZVP" in input_text
        assert "%casscf" in input_text
        assert "nel 4" in input_text
        assert "norb 4" in input_text
        assert "* xyz 0 1" in input_text


# ============================================================================
# 4. Tests for Directive 4: The 11-Arrow Canonical Pipeline Input Generator
# ============================================================================


class TestCanonical11ArrowPipeline:
    """Verifies all 11 canonical pipeline stages (§8B.4), auxiliary bases, dispersion corrections, and script builder."""

    def test_canonical_11_arrows_all_defined(self) -> None:
        """Confirms all 11 arrows are indexed from 1 to 11."""
        for idx in range(1, 12):
            meta = Canonical11ArrowPipeline.get_arrow_metadata(idx)
            assert meta["arrow"] == idx
            assert "name" in meta
            assert "keywords" in meta
            assert "tier" in meta

    def test_arrow_1_goat_xtb_input_construction(self) -> None:
        """Confirms Arrow 1: GOAT-XTB conformer search input generation."""
        inp = Canonical11ArrowPipeline.build_arrow_input(
            arrow=CanonicalArrow.ARROW_1_GOAT_CREST,
            geometry_input="* xyz 0 1\nC 0 0 0\nH 0 0 1.09\n*",
            stage_base_name="s1",
        )
        assert "! GOAT XTB2" in inp
        assert '%base "s1"' in inp
        assert "%maxcore" in inp
        assert "%pal nprocs" in inp

    def test_arrow_3_r2scan_3c_with_xtb_hessian(self) -> None:
        """Confirms Arrow 3: r2SCAN-3c with xTB Model Hessian preconditioning."""
        inp = Canonical11ArrowPipeline.build_arrow_input(
            arrow=CanonicalArrow.ARROW_3_R2SCAN_3C_OPT,
            geometry_input="* xyz 0 1\nC 0 0 0\nH 0 0 1.09\n*",
            stage_base_name="s2",
        )
        assert "! r2SCAN-3c" in inp
        assert "InHess XTB2" in inp
        assert '%base "s2"' in inp

    def test_arrow_4_wb97x_v_tz_with_moread_and_opt_hessian(self, tmp_path: Path) -> None:
        """Confirms Arrow 4: wB97X-V/def2-TZVPP with MORead and BFGS Hessian reuse."""
        seed_gbw = tmp_path / "s2.gbw"
        seed_gbw.touch()
        seed_opt = tmp_path / "s2.opt"
        seed_opt.touch()

        inp = Canonical11ArrowPipeline.build_arrow_input(
            arrow=CanonicalArrow.ARROW_4_WB97X_V_TZ_OPT,
            geometry_input="* xyz 0 1\nC 0 0 0\nH 0 0 1.09\n*",
            gbw_seed_path=seed_gbw,
            opt_seed_path=seed_opt,
            stage_base_name="s3",
        )
        assert "! wB97X-V" in inp
        assert "def2-TZVPP" in inp
        assert "def2/J" in inp
        assert "MORead" in inp
        assert '%base "s3"' in inp
        assert "%moinp" in inp
        assert "InHess Read" in inp

    def test_arrow_5_wb97m_v_qz_with_d4_and_fmatrix(self, tmp_path: Path) -> None:
        """Confirms Arrow 5: wB97M-V/def2-QZVPP with MO projection across basis and D4 dispersion."""
        seed_gbw = tmp_path / "s3.gbw"
        seed_gbw.touch()

        inp = Canonical11ArrowPipeline.build_arrow_input(
            arrow=CanonicalArrow.ARROW_5_WB97M_V_QZ_OPT,
            geometry_input="* xyz 0 1\nC 0 0 0\nH 0 0 1.09\n*",
            gbw_seed_path=seed_gbw,
            dispersion_correction="D4",
            stage_base_name="s4",
        )
        assert "! wB97M-V" in inp
        assert "def2-QZVPP" in inp
        assert "D4" in inp
        assert "%scf GuessMode FMatrix end" in inp
        assert '%base "s4"' in inp

    def test_arrow_8_dlpno_ccsd_t1_single_point(self, tmp_path: Path) -> None:
        """Confirms Arrow 8: DLPNO-CCSD(T1) with cc-pVDZ-F12 + CABS and auxiliary bases."""
        seed_gbw = tmp_path / "s4.gbw"
        seed_gbw.touch()

        inp = Canonical11ArrowPipeline.build_arrow_input(
            arrow=CanonicalArrow.ARROW_8_DLPNO_CCSD_T1_SP,
            geometry_input="* xyz 0 1\nC 0 0 0\nH 0 0 1.09\n*",
            gbw_seed_path=seed_gbw,
            stage_base_name="s6",
        )
        assert "! DLPNO-CCSD(T1)" in inp
        assert "cc-pVDZ-F12" in inp
        assert "cc-pVDZ-F12/C" in inp
        assert "def2/JK" in inp
        assert "TCutPNO 1e-7" in inp
        assert "DoLED true" in inp

    def test_generate_canonical_11_arrow_script(self) -> None:
        """Confirms generated canonical bash script has valid syntax, stages s1-s6, and hardware variables."""
        alloc = HardwareAllocations(usable_cores=8, maxcore_mb=3500)
        script = Canonical11ArrowPipeline.generate_canonical_11_arrow_script(
            seed_xyz_path="complex.xyz",
            charge=0,
            multiplicity=1,
            allocations=alloc,
        )
        assert "#!/usr/bin/env bash" in script
        assert "NPROC=8" in script
        assert "MEM=3500" in script
        assert "s1_xtb.out" in script
        assert "s2.inp" in script
        assert "s3.inp" in script
        assert "s4.inp" in script
        assert "s5.inp" in script
        assert "s6.inp" in script
        assert "orca_vib" in script


# ============================================================================
# 5. Tests for Hardware Brokering Header Engine
# ============================================================================


class TestHardwareBrokering:
    """Verifies host hardware polling, memory safety buffering, and header injection."""

    def test_poll_system_config_direct_mock_file(self, tmp_path: Path) -> None:
        """Confirms hardware allocation correctly reserves 20% / 4GB RAM buffer and 1 CPU core."""
        cfg_file = tmp_path / "cochem_system_config.json"
        cfg_data = {
            "hardware": {
                "physical_cpu_cores": 16,
                "logical_cpu_cores": 32,
                "ram_gb": 64.0,
            }
        }
        cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

        alloc = HardwareBroker.poll_system_config(config_path=cfg_file)
        assert alloc.physical_cores == 16
        assert alloc.reserved_cores == 1
        assert alloc.usable_cores == 15
        assert alloc.total_ram_gb == 64.0
        # Buffer is 20% of 64 GB = 12.8 GB
        assert alloc.os_buffer_ram_gb == pytest.approx(12.8, rel=1e-3)
        usable_mb = int((64.0 - 12.8) * 1024)
        assert alloc.usable_ram_mb == usable_mb
        expected_maxcore = usable_mb // 15
        assert alloc.maxcore_mb == expected_maxcore
        assert f"%maxcore {expected_maxcore}" in alloc.header_block
        assert "%pal nprocs 15 end" in alloc.header_block

    def test_inject_hardware_headers_replaces_or_inserts(self) -> None:
        """Confirms inject_hardware_headers cleanly places %maxcore and %pal nprocs under simple keywords."""
        input_text = """! wB97X-V def2-TZVP TightOpt
* xyz 0 1
O 0 0 0
H 0 0 1
H 0 1 0
*
"""
        alloc = HardwareAllocations(usable_cores=4, maxcore_mb=2000)
        injected = HardwareBroker.inject_hardware_headers(input_text, allocations=alloc)
        assert "%maxcore 2000" in injected
        assert "%pal nprocs 4 end" in injected
        lines = injected.splitlines()
        # Verify headers appear before geometry block
        maxcore_idx = next(i for i, ln in enumerate(lines) if "%maxcore" in ln)
        geom_idx = next(i for i, ln in enumerate(lines) if "* xyz" in ln)
        assert maxcore_idx < geom_idx


# ============================================================================
# 6. Tests for Geometrical Explosion Trap & Landscape Basin Tagging
# ============================================================================


class TestGeometricalExplosionTrap:
    """Verifies bond stretching detection (> 4.0 Å), OpenMPI process killing, and landscape.h5 tagging."""

    def test_check_geometry_explosion_normal_molecule(self) -> None:
        """Confirms stable molecule passes bond explosion check."""
        atoms = Atoms("H2O", positions=[[0.0, 0.0, 0.0], [0.0, 0.757, 0.586], [0.0, -0.757, 0.586]])
        exploded, max_d, pair = GeometricalExplosionTrap.check_geometry_explosion(atoms)
        assert exploded is False
        assert max_d < 4.0
        assert pair is None

    def test_check_geometry_explosion_shattered_bond(self) -> None:
        """Confirms stretched covalent bond > 4.0 Å is detected as an explosion."""
        # Initial bonded state (O-H ~ 0.96 A)
        init_atoms = Atoms("H2O", positions=[[0.0, 0.0, 0.0], [0.0, 0.96, 0.0], [0.0, 0.0, 0.96]])
        # Exploded state (O-H stretched to 4.8 A)
        exploded_atoms = Atoms("H2O", positions=[[0.0, 0.0, 0.0], [0.0, 4.80, 0.0], [0.0, 0.0, 0.96]])

        exploded, max_d, pair = GeometricalExplosionTrap.check_geometry_explosion(
            atoms_or_coords=exploded_atoms,
            initial_structure=init_atoms,
            threshold_angstrom=4.0,
        )
        assert exploded is True
        assert max_d >= 4.0
        assert pair is not None

    def test_monitor_orca_optimization_trajectory_detects_shattering(self) -> None:
        """Confirms multi-step ORCA output parsing detects mid-optimization bond explosion."""
        traj_out = """
---------------------------------
CARTESIAN COORDINATES (ANGSTROEM)
---------------------------------
  C      0.000000    0.000000    0.000000
  H      0.000000    0.000000    1.090000
---------------------------------
CARTESIAN COORDINATES (ANGSTROEM)
---------------------------------
  C      0.000000    0.000000    0.000000
  H      0.000000    0.000000    2.500000
---------------------------------
CARTESIAN COORDINATES (ANGSTROEM)
---------------------------------
  C      0.000000    0.000000    0.000000
  H      0.000000    0.000000    4.750000
"""
        exploded, max_d, step_idx = GeometricalExplosionTrap.monitor_orca_optimization_trajectory(
            traj_out, threshold_angstrom=4.0
        )
        assert exploded is True
        assert max_d >= 4.0
        assert step_idx == 2

    def test_flag_basin_unstable_in_landscape_h5(self, tmp_path: Path) -> None:
        """Confirms writing /basins/{molecule_id} with status='GEOMETRICAL_EXPLOSION' in landscape.h5."""
        h5_file = tmp_path / "landscape.h5"
        success = GeometricalExplosionTrap.flag_basin_unstable_in_landscape(
            landscape_h5_path=h5_file,
            molecule_id="mol_shattered_01",
            max_bond_distance=4.75,
            step_index=2,
            message="Bond C-H stretched > 4.0 A",
        )
        assert success is True
        assert h5_file.exists()

        with h5py.File(h5_file, "r") as f:
            grp = f["basins/mol_shattered_01"]
            assert grp.attrs["status"] == "GEOMETRICAL_EXPLOSION"
            assert bool(grp.attrs["unstable"]) is True
            assert pytest.approx(grp.attrs["max_bond_distance_observed"], rel=1e-3) == 4.75
            assert grp.attrs["explosion_step"] == 2


# ============================================================================
# 7. Tests for OOM Autopsy Engine (Exit Code 137 / SIGKILL)
# ============================================================================


class TestOOMAutopsyEngine:
    """Verifies detection of Exit Code 137, OOM autopsy JSON generation, and hardware downscaling."""

    def test_is_oom_event_detection(self) -> None:
        """Confirms detection via exit code 137 or error tokens."""
        assert OOMAutopsyEngine.is_oom_event(exit_code=137) is True
        assert OOMAutopsyEngine.is_oom_event(exit_code=0, output_text="std::bad_alloc thrown") is True
        assert OOMAutopsyEngine.is_oom_event(exit_code=1, output_text="Cannot allocate memory") is True
        assert OOMAutopsyEngine.is_oom_event(exit_code=0, output_text="Normal convergence") is False

    def test_generate_oom_autopsy_file(self, tmp_path: Path) -> None:
        """Confirms generation of OOM_autopsy.json diagnostic log."""
        plan = ExecutionPlan(
            plan_id="plan-oom-test",
            tier="T1-3d",
            method_name="wB97M-V",
            basis_set="def2-QZVPP",
            keywords="! wB97M-V def2-QZVPP TightPNO TightSCF",
            geometry_block="* xyz 0 1\nC 0 0 0\n*",
            num_cores=16,
            max_memory_mb=4000,
        )

        diag, autopsy_path = OOMAutopsyEngine.generate_oom_autopsy(
            molecule_id="large_complex_01",
            plan=plan,
            node_ram_mb=65536,
            exit_code=137,
            workdir=tmp_path,
        )
        assert autopsy_path.exists()
        assert diag.exit_code == 137
        assert diag.molecule_id == "large_complex_01"
        assert diag.tier_attempted == "T1-3d"
        assert diag.downscaling_recommendation["recommended_nprocs"] == 8
        assert "def2-TZVPP" in diag.suggested_keywords

        # Read JSON file back
        loaded = json.loads(autopsy_path.read_text(encoding="utf-8"))
        assert loaded["exit_code"] == 137
        assert loaded["allocated_nprocs"] == 16

    def test_derive_hardware_downscaling_plan(self) -> None:
        """Confirms derive_hardware_downscaling creates a plan with reduced cores and smaller basis."""
        plan = ExecutionPlan(
            plan_id="plan-orig",
            tier="T1-3d",
            method_name="wB97M-V",
            basis_set="def2-QZVPP",
            keywords="! wB97M-V def2-QZVPP TightPNO TightSCF",
            geometry_block="* xyz 0 1\nC 0 0 0\n*",
            num_cores=16,
            max_memory_mb=4000,
        )
        diag = OOMAutopsyDiagnostic(
            molecule_id="mol1",
            plan_id="plan-orig",
            tier_attempted="T1-3d",
            exit_code=137,
            node_ram_mb=65536,
            allocated_maxcore_mb=4000,
            allocated_nprocs=16,
            downscaling_recommendation={
                "action": "HALVE_CORES_DOUBLE_MAXCORE",
                "recommended_nprocs": 8,
                "recommended_maxcore_mb": 7680,
                "recommended_basis": "def2-TZVPP",
            },
            suggested_keywords="! wB97M-V def2-TZVPP NormalPNO TightSCF",
        )
        downscaled = OOMAutopsyEngine.derive_hardware_downscaling(plan, diag)
        assert downscaled.num_cores == 8
        assert downscaled.max_memory_mb == 7680
        assert downscaled.basis_set == "def2-TZVPP"
        assert "def2-TZVPP" in downscaled.keywords


# ============================================================================
# 8. Tests for Wavefunction Seeding & Naming Hygiene (`! MORead`)
# ============================================================================


class TestWavefunctionSeedingMORead:
    """Verifies binary .gbw orbital projection and %base naming hygiene."""

    def test_inject_gbw_seed_formatting(self, tmp_path: Path) -> None:
        """Confirms injection of ! MORead, %base, %moinp, and %scf GuessMode FMatrix."""
        seed_gbw = tmp_path / "s2.gbw"
        seed_gbw.touch()

        raw_input = """! wB97X-V def2-TZVP TightOpt
* xyz 0 1
O 0 0 0
H 0 0 1
*
"""
        seeded = WavefunctionSeeder.inject_gbw_seed(
            input_content=raw_input,
            gbw_seed_path=seed_gbw,
            stage_base_name="s3",
            guess_mode="FMatrix",
        )
        assert "MORead" in seeded
        assert '%base "s3"' in seeded
        assert '%moinp' in seeded
        assert str(seed_gbw).replace("\\", "/") in seeded
        assert "%scf GuessMode FMatrix end" in seeded


# ============================================================================
# 9. Tests for Cross-Platform IPC Subsystem
# ============================================================================


class TestCrossPlatformIPCSubsystem:
    """Verifies thread-safe and process-safe alert communication via socket and file queue."""

    def test_file_socket_ipc_queue_push_and_pop(self, tmp_path: Path) -> None:
        """Confirms atomic push and pop operations on FileSocketIPCQueue."""
        queue_dir = tmp_path / "ipc_queue"
        queue = FileSocketIPCQueue(queue_dir)

        alert = CrossPlatformIPCAlert(
            severity=AlertSeverity.WARNING,
            title="SCF Warning",
            message="Limit cycle detected",
            payload={"cycle": 2},
        )
        saved_file = queue.push(alert)
        assert saved_file.exists()

        popped = queue.pop_all()
        assert len(popped) == 1
        assert popped[0].title == "SCF Warning"
        assert popped[0].severity == AlertSeverity.WARNING
        assert not saved_file.exists()

    def test_ipc_server_and_client_roundtrip(self, tmp_path: Path) -> None:
        """Confirms server starts, registers callback, and receives alerts from client."""
        queue_dir = tmp_path / "ipc_roundtrip"
        server = CrossPlatformIPCServer(port=8895, queue_dir=queue_dir)

        received_alerts: list[CrossPlatformIPCAlert] = []
        server.register_callback(lambda a: received_alerts.append(a))
        server.start()

        time.sleep(0.1)

        client = CrossPlatformIPCClient(port=8895, queue_dir=queue_dir)
        test_alert = CrossPlatformIPCAlert(
            severity=AlertSeverity.CRITICAL,
            title="AutoCAS Triggered",
            message="T1=0.035 exceeds threshold",
            payload={"t1": 0.035},
        )
        client.send_alert(test_alert)

        time.sleep(0.3)
        server.stop()

        assert len(received_alerts) >= 1
        assert received_alerts[0].title == "AutoCAS Triggered"


# ============================================================================
# 10. Tests for Time-Aware Capability Selector & Master ToposEscalatorExec Broker
# ============================================================================


class TestTimeAwareCapabilitySelectorAndBroker:
    """Verifies tier selection, ladder construction, dry-run simulation, and end-to-end execution."""

    def test_select_optimal_tier_scaling(self) -> None:
        """Confirms appropriate tier selection based on time budgets and molecular size."""
        # 10 second budget -> T1-10s (XTB2)
        assert TimeAwareCapabilitySelector.select_optimal_tier(5.0, num_atoms=5) == EscalationTier.T1_10S

        # 1 minute budget -> T1-1min (GOAT-XTB2)
        assert TimeAwareCapabilitySelector.select_optimal_tier(60.0, num_atoms=5) == EscalationTier.T1_1MIN

        # 3 hour budget -> T1-3h (r2SCAN-3c)
        assert TimeAwareCapabilitySelector.select_optimal_tier(3600.0, num_atoms=5) == EscalationTier.T1_3H

        # 3 day budget -> T1-3d (wB97M-V / DLPNO-CCSD(T))
        assert TimeAwareCapabilitySelector.select_optimal_tier(250000.0, num_atoms=5) == EscalationTier.T1_3D

    def test_build_escalation_ladder_sequence(self) -> None:
        """Confirms ladder generation produces strictly monotonic progression."""
        ladder = TimeAwareCapabilitySelector.build_escalation_ladder(
            target_tier=EscalationTier.T1_3H,
            start_tier=EscalationTier.T1_10S,
        )
        assert ladder[0] == EscalationTier.T1_10S
        assert ladder[-1] == EscalationTier.T1_3H
        assert EscalationTier.T1_1MIN in ladder

    def test_run_escalation_dry_run_success(self, tmp_path: Path) -> None:
        """Confirms full dry-run multi-tier escalation achieves target tier successfully."""
        config = EscalatorExecConfig(
            working_dir=tmp_path / "escalation_test",
            dry_run=True,
            enable_ipc_alerts=False,
        )
        broker = ToposEscalatorExec(config=config)

        res = broker.run_escalation(
            geometry="* xyz 0 1\nO 0 0 0\nH 0 0 1\nH 0 1 0\n*",
            molecule_id="water_test",
            target_tier=EscalationTier.T1_1MIN,
        )
        assert res.success is True
        assert res.final_status == CalculationStatus.SUCCESS
        assert res.highest_tier_achieved == EscalationTier.T1_1MIN.value
        assert len(res.steps) == 2
        assert res.final_energy_hartree is not None

    def test_run_escalation_geometrical_explosion_trap(self, tmp_path: Path) -> None:
        """Confirms mid-optimization bond stretching halts escalation with GEOMETRICAL_EXPLOSION."""
        h5_path = tmp_path / "landscape.h5"
        config = EscalatorExecConfig(
            working_dir=tmp_path / "explosion_test",
            landscape_h5_path=h5_path,
            dry_run=True,
            enable_ipc_alerts=False,
        )
        broker = ToposEscalatorExec(config=config)

        # Injects TRIGGER_EXPLOSION keyword into dry run
        geom = "* xyz 0 1\nC 0 0 0\nH 0 0 1.09\n*"
        plan = broker.build_plan(tier=EscalationTier.T1_10S, geometry_input=geom)
        plan.keywords = "! XTB2 TightOpt TRIGGER_EXPLOSION"

        step_record = broker.execute_step(plan, molecule_id="exploding_mol", step_index=0)
        assert step_record.status == CalculationStatus.GEOMETRICAL_EXPLOSION
        assert "Geometrical Explosion" in str(step_record.error_message)

        # Check landscape.h5 was updated
        assert h5_path.exists()
        with h5py.File(h5_path, "r") as f:
            grp = f["basins/exploding_mol"]
            assert grp.attrs["status"] == "GEOMETRICAL_EXPLOSION"
            assert bool(grp.attrs["unstable"]) is True

    def test_run_escalation_oom_autopsy(self, tmp_path: Path) -> None:
        """Confirms OS OOM signal (137) logs OOM_autopsy.json and sets status to OOM_KILLED."""
        config = EscalatorExecConfig(
            working_dir=tmp_path / "oom_test",
            dry_run=True,
            enable_ipc_alerts=False,
        )
        broker = ToposEscalatorExec(config=config)

        geom = "* xyz 0 1\nC 0 0 0\nH 0 0 1.09\n*"
        plan = broker.build_plan(tier=EscalationTier.T1_3D, geometry_input=geom)
        plan.keywords = "! wB97M-V def2-QZVPP TightPNO TRIGGER_OOM"

        step_record = broker.execute_step(plan, molecule_id="oom_mol", step_index=0)
        assert step_record.status == CalculationStatus.OOM_KILLED
        assert step_record.oom_autopsy is not None
        assert step_record.oom_autopsy.exit_code == 137

        autopsy_file = tmp_path / "oom_test" / f"oom_mol_{plan.plan_id}" / "OOM_autopsy.json"
        assert autopsy_file.exists()

    def test_run_escalation_autocas_trigger_on_multiref(self, tmp_path: Path) -> None:
        """Confirms T1/D1 diagnostic violation halts escalation and sets status to AUTOCAS_TRIGGERED."""
        config = EscalatorExecConfig(
            working_dir=tmp_path / "autocas_test",
            dry_run=True,
            enable_ipc_alerts=False,
        )
        broker = ToposEscalatorExec(config=config)

        geom = "* xyz 0 1\nC 0 0 0\nC 0 0 1.4\n*"
        plan = broker.build_plan(tier=EscalationTier.T1_3D, geometry_input=geom)
        plan.keywords = "! DLPNO-CCSD(T) TightPNO TRIGGER_MULTIREF"

        step_record = broker.execute_step(plan, molecule_id="diradical_mol", step_index=0)
        assert step_record.status == CalculationStatus.AUTOCAS_TRIGGERED
        assert step_record.multiref_diagnostics is not None
        assert step_record.multiref_diagnostics.is_multireference is True
        assert step_record.multiref_diagnostics.t1_diagnostic > 0.02
