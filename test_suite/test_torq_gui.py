"""Comprehensive unit and integration test suite for CoChem-TORQ Tab & Optimization Subsystem.

Validates:
- Physical and numerical conversion constants (HARTREE_TO_KCAL, HARTREE_TO_EV, BOHR_TO_ANGSTROM).
- Academic Citation Registry and Didactic Mathematical Formulations completeness.
- Enums for optimization types, Hessian diagonalizers, preconditioners, dispersion, grids, and coordinates.
- ConvergenceCriteria Pydantic v2 validation, weak-complex mode auto-tightening, and convergence checks.
- ScanParameters coordinate scanning and ORCA %geom Scan line generation.
- TorqOptimizationConfig model validation, Method Matrix v4 InHess invariant enforcement, %geom block generation.
- OptimizationStepRecord telemetry schema validation and serialization.
- TorqWorker background trajectory execution, mathematical descent, dynamic grid tightening, and cancellation.
- TorqTab GUI lifecycle, Method Matrix presets, threshold slider color coding, didactic math viewer, live trajectory updates, and multi-format exports (%geom, JSON, CSV).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from PySide6.QtWidgets import QApplication

from cochem_base.core.models import GeomTorqStage
from cochem_base.gui.torq import (
    ACADEMIC_CITATIONS,
    BOHR_TO_ANGSTROM,
    DIDACTIC_MATH_FORMULATIONS,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL,
    ConvergenceCriteria,
    CoordinateType,
    DispersionType,
    GridLevel,
    HessianDiagonalizer,
    HessianPreconditioner,
    OptimizationStepRecord,
    OptimizationType,
    ScanParameters,
    TorqOptimizationConfig,
    TorqTab,
    TorqWorker,
)


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """Ensure a singleton QApplication instance is active for Qt-based Torq tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


# =============================================================================
# 1. Constants, Citations & Mathematical Formulations Tests
# =============================================================================


class TestConstantsAndCitations:
    """Test suite for physical constants, academic citation registry, and didactic formulations."""

    def test_physical_constants_values_and_types(self) -> None:
        """Verify exact physical conversion constants."""
        assert abs(HARTREE_TO_KCAL - 627.5094740631) < 1e-6
        assert abs(HARTREE_TO_EV - 27.211386245988) < 1e-6
        assert abs(BOHR_TO_ANGSTROM - 0.529177210903) < 1e-6

    def test_academic_citations_registry(self) -> None:
        """Verify academic citation registry keys and provenance tags."""
        expected_keys = [
            "MMFF94",
            "B3LYP-D4",
            "wB97X-D4",
            "PBE0-D4",
            "DLPNO-CCSD(T)",
            "CI-NEB",
            "RFO",
            "BFGS",
            "Davidson",
            "Lanczos",
            "Lindh",
            "InHess XTB2",
            "BSSE",
        ]
        for key in expected_keys:
            assert key in ACADEMIC_CITATIONS
            citation = ACADEMIC_CITATIONS[key]
            assert isinstance(citation, str)
            assert citation.startswith("[M]") or citation.startswith("[D]") or citation.startswith("[E]")

    def test_didactic_math_formulations_structure(self) -> None:
        """Verify structure and completeness of all Didactic Math Formulations."""
        expected_topics = [
            "RFO_Augmented_Hessian",
            "BFGS_Secant_Update",
            "CI_NEB_Forces",
            "Krylov_Davidson_Lanczos",
            "InHess_Preconditioning",
            "Dynamic_Grid_Tightening",
            "Weak_Complex_Convergence",
        ]
        for topic in expected_topics:
            assert topic in DIDACTIC_MATH_FORMULATIONS
            data = DIDACTIC_MATH_FORMULATIONS[topic]
            assert "title" in data
            assert "latex" in data
            assert "html" in data
            assert "description" in data
            assert "method_matrix_rule" in data


# =============================================================================
# 2. Enums and Pydantic v2 Models Validation Tests
# =============================================================================


class TestEnumsAndModels:
    """Test suite for domain enums and Pydantic configuration/telemetry models."""

    def test_enums_members(self) -> None:
        """Verify enum member definitions and string values."""
        assert OptimizationType.MIN == "Min"
        assert OptimizationType.TS == "TS"
        assert OptimizationType.CI_NEB == "CI-NEB"
        assert OptimizationType.IRC == "IRC"
        assert OptimizationType.SCAN == "Scan"

        assert HessianDiagonalizer.DENSE == "Dense"
        assert HessianDiagonalizer.DAVIDSON == "Davidson"
        assert HessianDiagonalizer.LANCZOS == "Lanczos"

        assert HessianPreconditioner.IN_HESS_XTB2 == "InHess XTB2"
        assert HessianPreconditioner.LINDH == "Lindh"

        assert DispersionType.D4 == "D4"
        assert DispersionType.D3 == "D3"
        assert DispersionType.D3BJ == "D3BJ"
        assert DispersionType.D4BJ == "D4BJ"
        assert DispersionType.NONE == "None"

        assert GridLevel.DEFGRID1 == "defgrid1"
        assert GridLevel.DEFGRID2 == "defgrid2"
        assert GridLevel.DEFGRID3 == "defgrid3"

        assert CoordinateType.DIHEDRAL == "Dihedral"
        assert CoordinateType.ANGLE == "Angle"
        assert CoordinateType.DISTANCE == "Distance"

    def test_convergence_criteria_defaults(self) -> None:
        """Verify ConvergenceCriteria default values."""
        conv = ConvergenceCriteria()
        assert conv.tol_e == 1.0e-6
        assert conv.tol_max_g == 3.0e-4
        assert conv.tol_rms_g == 1.0e-4
        assert conv.tol_max_x == 1.8e-3
        assert conv.tol_rms_x == 6.0e-4
        assert conv.max_step == 0.1
        assert conv.max_iter == 300
        assert conv.weak_complex_mode is False
        assert conv.bsse_correction is False

    def test_convergence_criteria_weak_complex_auto_tighten(self) -> None:
        """Verify ConvergenceCriteria auto-tightens when weak_complex_mode is enabled."""
        conv = ConvergenceCriteria(weak_complex_mode=True)
        assert conv.tol_max_g <= 1.0e-5
        assert conv.tol_rms_g <= 5.0e-6
        assert conv.bsse_correction is True

    def test_convergence_criteria_preset_and_evaluation(self) -> None:
        """Verify apply_weak_complex_preset and is_step_converged method."""
        conv = ConvergenceCriteria()
        preset_conv = conv.apply_weak_complex_preset()
        assert preset_conv.weak_complex_mode is True
        assert preset_conv.tol_max_g == 1.0e-5
        assert preset_conv.tol_rms_g == 5.0e-6
        assert preset_conv.bsse_correction is True
        assert preset_conv.max_iter == 500

        # Test is_step_converged
        assert conv.is_step_converged(
            delta_e=5.0e-7,
            max_g=2.0e-4,
            rms_g=8.0e-5,
            max_x=1.0e-3,
            rms_x=4.0e-4,
        ) is True

        assert conv.is_step_converged(
            delta_e=5.0e-7,
            max_g=5.0e-4,  # Exceeds tol_max_g 3.0e-4
            rms_g=8.0e-5,
            max_x=1.0e-3,
            rms_x=4.0e-4,
        ) is False

    def test_scan_parameters_validation_and_step_size(self) -> None:
        """Verify ScanParameters step size calculation and ORCA line generation."""
        scan = ScanParameters(
            coordinate_type="Dihedral",
            atom_indices=[1, 2, 3, 4],
            start_val=0.0,
            end_val=180.0,
            steps=18,
        )
        assert abs(scan.step_size - 10.0) < 1e-6
        scan_line = scan.to_geom_scan_line()
        assert "D 0 1 2 3 = 0.0000, 180.0000, 18" in scan_line

        # Test Angle
        scan_angle = ScanParameters(
            coordinate_type="Angle",
            atom_indices=[1, 2, 3],
            start_val=90.0,
            end_val=120.0,
            steps=6,
        )
        assert "A 0 1 2 = 90.0000, 120.0000, 6" in scan_angle.to_geom_scan_line()

        # Test Distance
        scan_dist = ScanParameters(
            coordinate_type="Distance",
            atom_indices=[1, 2],
            start_val=1.0,
            end_val=3.0,
            steps=20,
        )
        assert "B 0 1 = 1.0000, 3.0000, 20" in scan_dist.to_geom_scan_line()

    def test_scan_parameters_invalid_inputs(self) -> None:
        """Verify ScanParameters validation failures on invalid coordinate types or atom indices."""
        with pytest.raises(ValidationError):
            ScanParameters(coordinate_type="InvalidCoordType")

        with pytest.raises(ValidationError):
            ScanParameters(atom_indices=[])

        with pytest.raises(ValidationError):
            ScanParameters(atom_indices=[-1, 2, 3])

    def test_torq_optimization_config_in_hess_enforcement(self) -> None:
        """Verify TorqOptimizationConfig strictly prohibits 'Calc_Hess true'."""
        with pytest.raises(ValidationError, match="Calc_Hess true"):
            TorqOptimizationConfig(in_hess="Calc_Hess true")

        with pytest.raises(ValidationError, match="Calc_Hess true"):
            TorqOptimizationConfig(in_hess="calc_hess true")

        # Valid InHess values
        cfg = TorqOptimizationConfig(in_hess="InHess XTB2")
        assert cfg.in_hess == "InHess XTB2"

        cfg_lindh = TorqOptimizationConfig(in_hess="Lindh")
        assert cfg_lindh.in_hess == "Lindh"

    def test_torq_optimization_config_to_geom_block(self) -> None:
        """Verify %geom block generation across optimization types (Min, TS, CI-NEB, Scan, IRC)."""
        # 1. Standard Min
        cfg_min = TorqOptimizationConfig(opt_type="Min")
        block_min = cfg_min.to_geom_block()
        assert "%geom" in block_min
        assert "MaxIter 300" in block_min
        assert "InHess InHess_XTB2" in block_min
        assert "Step RFO" in block_min
        assert "TolMaxG 3.0000e-04" in block_min
        assert "end" in block_min

        # 2. Transition State
        cfg_ts = TorqOptimizationConfig(opt_type="TS", hess_diag="Davidson")
        block_ts = cfg_ts.to_geom_block()
        assert "TS true" in block_ts
        assert "HessDiag Davidson" in block_ts
        assert "Calc_Hess false" in block_ts

        # 3. CI-NEB
        cfg_neb = TorqOptimizationConfig(opt_type="CI-NEB")
        block_neb = cfg_neb.to_geom_block()
        assert "NEB" in block_neb
        assert "CI true" in block_neb
        assert "NImages 8" in block_neb

        # 4. Scan
        scan_p = ScanParameters(coordinate_type="Dihedral", atom_indices=[1, 2, 3, 4], start_val=0, end_val=180, steps=18)
        cfg_scan = TorqOptimizationConfig(opt_type="Scan", scan_params=scan_p)
        block_scan = cfg_scan.to_geom_block()
        assert "Scan" in block_scan
        assert "D 0 1 2 3 = 0.0000, 180.0000, 18" in block_scan

        # 5. IRC
        cfg_irc = TorqOptimizationConfig(opt_type="IRC")
        block_irc = cfg_irc.to_geom_block()
        assert "IRC" in block_irc
        assert "Direction Both" in block_irc

    def test_torq_optimization_config_to_geom_torq_stage(self) -> None:
        """Verify bridging TorqOptimizationConfig to core GeomTorqStage model."""
        cfg = TorqOptimizationConfig(
            dispersion_correction="D4",
            in_hess="InHess XTB2",
            grid_start="defgrid1",
            grid_final="defgrid3",
        )
        stage = cfg.to_geom_torq_stage()
        assert isinstance(stage, GeomTorqStage)
        assert stage.dispersion_correction == "D4"
        assert stage.hessian_preconditioner == "InHess XTB2"
        assert stage.grid_start == "defgrid1"
        assert stage.grid_final == "defgrid3"

    def test_optimization_step_record_serialization(self) -> None:
        """Verify OptimizationStepRecord serialization and dictionary conversion."""
        record = OptimizationStepRecord(
            step=1,
            energy_hartree=-154.2850000,
            delta_e_kcal=-1.1923,
            max_gradient=0.002100,
            rms_gradient=0.000880,
            max_displacement=0.003500,
            rms_displacement=0.001330,
            step_type="RFO",
            is_converged=False,
            grid_level="defgrid1",
        )
        data = record.to_dict()
        assert data["step"] == 1
        assert data["energy_hartree"] == -154.2850000
        assert data["step_type"] == "RFO"
        assert data["is_converged"] is False
        assert "timestamp" in data


# =============================================================================
# 3. TorqWorker Background Thread Execution Tests
# =============================================================================


class TestTorqWorkerExecution:
    """Test suite for TorqWorker background calculation and trajectory emission."""

    def test_torq_worker_synchronous_run_and_convergence(self) -> None:
        """Verify TorqWorker executes trajectory simulation and emits expected signals."""
        cfg = TorqOptimizationConfig(
            opt_type="Min",
            method_string="B3LYP-D4/def2-TZVP",
            dispersion_correction="D4",
            max_cycles=50,
            convergence=ConvergenceCriteria(tol_max_g=3.0e-4),
        )
        # Use step_delay_ms=0 for fast deterministic unit testing
        worker = TorqWorker(config=cfg, step_delay_ms=0)

        progress_events: list[tuple[int, int, str]] = []
        step_events: list[dict[str, Any]] = []
        finish_events: list[dict[str, Any]] = []
        log_events: list[tuple[str, str]] = []

        worker.progress_updated.connect(lambda s, m, msg: progress_events.append((s, m, msg)))
        worker.step_completed.connect(lambda d: step_events.append(d))
        worker.optimization_finished.connect(lambda s: finish_events.append(s))
        worker.log_emitted.connect(lambda lvl, msg: log_events.append((lvl, msg)))

        # Synchronous execution
        worker.run()

        assert len(step_events) >= 2
        assert len(finish_events) == 1
        summary = finish_events[0]
        assert summary["converged"] is True
        assert summary["total_steps"] >= 1
        assert "final_energy_hartree" in summary
        assert summary["final_grid"] in ["defgrid2", "defgrid3"]
        assert len(worker.step_records) == len(step_events)

    def test_torq_worker_cancellation(self) -> None:
        """Verify TorqWorker handles cancellation cleanly and stops progression."""
        cfg = TorqOptimizationConfig(max_cycles=100)
        worker = TorqWorker(config=cfg, step_delay_ms=0)

        step_events: list[dict[str, Any]] = []
        worker.step_completed.connect(lambda d: step_events.append(d))

        # Request cancellation immediately
        worker.request_stop()
        assert worker.is_cancelled() is True

        worker.run()

        # Step 0 is emitted during initialization, then loop immediately halts on step 1
        assert len(step_events) == 1
        assert step_events[0]["step"] == 0


# =============================================================================
# 4. TorqTab GUI Widget Unit & Integration Tests
# =============================================================================


@pytest.mark.usefixtures("qapp")
class TestTorqTabWidget:
    """Test suite for TorqTab controls, presets, live table updates, and exports."""

    def test_torq_tab_initialization(self, qapp: QApplication) -> None:
        """Verify TorqTab initializes with proper widgets, default preset, and %geom preview."""
        tab = TorqTab()
        assert tab.cbo_preset.count() == 4
        assert tab.slider_threshold.value() == 50
        assert "Treatment Threshold: 50%" in tab.lbl_value.text()
        assert tab.cbo_opt_type.currentText() == "Min"
        assert tab.cbo_in_hess.currentText() == "InHess XTB2"
        assert tab.cbo_grid_start.currentText() == "defgrid1"
        assert tab.cbo_grid_final.currentText() == "defgrid3"
        assert tab.table_trajectory.columnCount() == 10
        assert tab.table_trajectory.rowCount() == 0
        assert "%geom" in tab.txt_geom_preview.toPlainText()

    def test_torq_tab_didactic_toggle_and_topic_selection(self, qapp: QApplication) -> None:
        """Verify didactic math view visibility toggle and topic change rendering."""
        tab = TorqTab()
        assert tab.lbl_didactic.isHidden() is True

        tab.toggle_didactic()
        assert tab.lbl_didactic.isHidden() is False

        tab.toggle_didactic()
        assert tab.lbl_didactic.isHidden() is True

        # Test selecting different didactic topics
        tab.cbo_didactic_topic.setCurrentText("CI_NEB_Forces")
        assert "Climbing-Image" in tab.txt_didactic_viewer.toHtml()

        tab.cbo_didactic_topic.setCurrentText("Krylov_Davidson_Lanczos")
        assert "Krylov" in tab.txt_didactic_viewer.toHtml()

    def test_torq_tab_threshold_slider_and_citations(self, qapp: QApplication) -> None:
        """Verify threshold slider update updates text, styling, and academic citations."""
        tab = TorqTab()

        # Classical (< 30)
        tab.slider_threshold.setValue(20)
        assert "20%" in tab.lbl_value.text()
        assert "Halgren" in tab.lbl_citation.text()

        # DFT (30 - 70)
        tab.slider_threshold.setValue(50)
        assert "50%" in tab.lbl_value.text()
        assert "Becke" in tab.lbl_citation.text()

        # Ab Initio (> 70)
        tab.slider_threshold.setValue(85)
        assert "85%" in tab.lbl_value.text()
        assert "Riplinger" in tab.lbl_citation.text()

    def test_torq_tab_presets_application(self, qapp: QApplication) -> None:
        """Verify applying all Method Matrix v4 presets."""
        tab = TorqTab()

        # 1. Weak Complex
        tab.apply_preset("Weak Complex (Non-Covalent / TolMaxG 1e-5)")
        assert tab.chk_weak_complex.isChecked() is True
        assert tab.chk_bsse.isChecked() is True
        assert tab.spn_tol_max_g.value() == 1.0e-5
        assert tab.cbo_didactic_topic.currentText() == "Weak_Complex_Convergence"

        # 2. Transition State
        tab.apply_preset("Transition State Search (EVF / CI-NEB)")
        assert tab.cbo_opt_type.currentText() == "TS"
        assert tab.cbo_hess_diag.currentText() == "Davidson"
        assert tab.chk_rfo_damping.isChecked() is True

        # 3. Relaxed PES Scan
        tab.apply_preset("Relaxed PES Scan (Dihedral / Angle / Distance)")
        assert tab.cbo_opt_type.currentText() == "Scan"
        assert tab.scan_group.isHidden() is False

        # 4. Reset Defaults (Standard Min)
        tab.reset_defaults()
        assert tab.cbo_opt_type.currentText() == "Min"
        assert tab.spn_tol_max_g.value() == 3.0e-4
        assert tab.chk_weak_complex.isChecked() is False
        assert tab.scan_group.isHidden() is True

    def test_torq_tab_config_get_and_apply_roundtrip(self, qapp: QApplication) -> None:
        """Verify get_config and apply_config consistency roundtrip."""
        tab = TorqTab()
        tab.cbo_opt_type.setCurrentText("TS")
        tab.cbo_hess_diag.setCurrentText("Davidson")
        tab.cbo_in_hess.setCurrentText("Lindh")
        tab.cbo_dispersion.setCurrentText("D3BJ")
        tab.spn_trust_radius.setValue(0.15)
        tab.spn_max_cycles.setValue(450)
        tab.spn_tol_max_g.setValue(2.0e-4)

        config = tab.get_config()
        assert config.opt_type == "TS"
        assert config.hess_diag == "Davidson"
        assert config.in_hess == "Lindh"
        assert config.dispersion_correction == "D3BJ"
        assert config.trust_radius == 0.15
        assert config.max_cycles == 450
        assert config.convergence.tol_max_g == 2.0e-4

        # Bridge to GeomTorqStage
        stage = tab.to_geom_torq_stage()
        assert stage.dispersion_correction == "D3BJ"
        assert stage.hessian_preconditioner == "Lindh"

        # Reset and apply
        tab.reset_defaults()
        tab.apply_config(config)
        assert tab.cbo_opt_type.currentText() == "TS"
        assert tab.cbo_in_hess.currentText() == "Lindh"
        assert tab.spn_trust_radius.value() == 0.15

    def test_torq_tab_live_step_record_processing(self, qapp: QApplication) -> None:
        """Verify processing worker step telemetry updates KPI cards and trajectory table."""
        tab = TorqTab()
        step_payload = {
            "step": 1,
            "energy_hartree": -154.2901234,
            "delta_e_kcal": -4.4095,
            "max_gradient": 0.005120,
            "rms_gradient": 0.002150,
            "max_displacement": 0.008450,
            "rms_displacement": 0.003210,
            "step_type": "RFO",
            "is_converged": False,
            "grid_level": "defgrid1",
            "timestamp": 1723980000.0,
        }

        tab.on_worker_step(step_payload)
        assert tab.table_trajectory.rowCount() == 1
        assert len(tab.step_records) == 1
        assert "-154.290123" in tab.lbl_kpi_energy.text()
        assert "-4.410" in tab.lbl_kpi_delta_e.text()
        assert "0.005120" in tab.lbl_kpi_max_g.text()
        assert "IN PROGRESS (defgrid1)" in tab.lbl_kpi_status.text()

        # Step 2: Converged
        step_2_payload = dict(step_payload)
        step_2_payload["step"] = 2
        step_2_payload["is_converged"] = True
        step_2_payload["grid_level"] = "defgrid3"

        tab.on_worker_step(step_2_payload)
        assert tab.table_trajectory.rowCount() == 2
        assert tab.table_trajectory.item(1, 9).text() == "YES"

        # Worker finished
        summary = {"converged": True, "total_steps": 2, "final_grid": "defgrid3"}
        tab.on_worker_finished(summary)
        assert "CONVERGED (defgrid3)" in tab.lbl_kpi_status.text()

        # Reset trajectory
        tab.reset_trajectory()
        assert tab.table_trajectory.rowCount() == 0
        assert len(tab.step_records) == 0
        assert "IDLE (defgrid1)" in tab.lbl_kpi_status.text()

    def test_torq_tab_export_functions(self, tmp_path: Path, qapp: QApplication) -> None:
        """Verify export_geom_block, export_config_json, and export_trajectory_csv routines."""
        tab = TorqTab()

        # 1. Export %geom block
        geom_file = tmp_path / "exports" / "test_orca.inp"
        content_geom = tab.export_geom_block(file_path=geom_file)
        assert geom_file.is_file()
        assert "%geom" in geom_file.read_text(encoding="utf-8")
        assert content_geom == geom_file.read_text(encoding="utf-8")

        # 2. Export Config JSON
        json_file = tmp_path / "exports" / "test_config.json"
        content_json = tab.export_config_json(file_path=json_file)
        assert json_file.is_file()
        loaded = json.loads(json_file.read_text(encoding="utf-8"))
        assert loaded["opt_type"] == "Min"
        assert content_json == json_file.read_text(encoding="utf-8")

        # 3. Export Trajectory CSV
        step_payload = {
            "step": 0,
            "energy_hartree": -154.2831000,
            "delta_e_kcal": 0.0,
            "max_gradient": 0.024500,
            "rms_gradient": 0.011200,
            "max_displacement": 0.045000,
            "rms_displacement": 0.021000,
            "step_type": "Initial",
            "is_converged": False,
            "grid_level": "defgrid1",
            "timestamp": 1723980000.0,
        }
        tab.on_worker_step(step_payload)

        csv_file = tmp_path / "exports" / "test_traj.csv"
        content_csv = tab.export_trajectory_csv(file_path=csv_file)
        assert csv_file.is_file()
        lines = csv_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2  # Header + 1 record
        assert "Step,Energy_Hartree" in lines[0]
        assert content_csv == csv_file.read_text(encoding="utf-8")

    def test_torq_tab_close_event_clean_teardown(self, qapp: QApplication) -> None:
        """Verify closeEvent cleanly tears down background worker if running."""
        tab = TorqTab()
        tab.close()
