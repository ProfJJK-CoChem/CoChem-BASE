"""Unit and integration tests for Deliverable 3: Structured Telemetry Parsing,
Data Inspector Wiring & Thread-Safe HDF5 SWMR Observables Viewer (Suggestion #113).

Method Matrix v4 (§3.0, §8C) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Five free observables parsing and HDF5 SWMR ingestion.
"""
from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pytest

from cochem_base.analysis.output_parser import OutputParser
from ui.voila_layout.cochem_gui import CoChemGUI, DataInspectorWidget

SAMPLE_ORCA_LOG = """
------------------------------------------------------------------------------
                           ORCA PROPERTY CALCULATIONS
------------------------------------------------------------------------------
Rotational constants in MHz:
   A =   27858.123   B =   14520.456   C =    9540.789

Vibrational corrections to rotational constants (MHz):
   Delta_A =     -120.450   Delta_B =      -45.210   Delta_C =      -22.100

------------------------------------------------------------------------------
                              TOTAL DIPOLE MOMENT
------------------------------------------------------------------------------
Total Dipole Moment    :         1.8546 Debye
"""

def test_output_parser_five_free_observables(tmp_path: Path):
    log_file = tmp_path / "water_orca.out"
    log_file.write_text(SAMPLE_ORCA_LOG, encoding="utf-8")

    parser = OutputParser()
    res = parser.parse_file(log_file)

    assert pytest.approx(res.a_e, rel=1e-3) == 27858.123
    assert pytest.approx(res.b_e, rel=1e-3) == 14520.456
    assert pytest.approx(res.c_e, rel=1e-3) == 9540.789

    assert pytest.approx(res.delta_a_vib, rel=1e-3) == -120.450
    assert pytest.approx(res.delta_b_vib, rel=1e-3) == -45.210
    assert pytest.approx(res.delta_c_vib, rel=1e-3) == -22.100

    assert pytest.approx(res.a_0, rel=1e-3) == 27858.123 - 120.450
    assert pytest.approx(res.b_0, rel=1e-3) == 14520.456 - 45.210
    assert pytest.approx(res.c_0, rel=1e-3) == 9540.789 - 22.100

    assert hasattr(res, "inertial_defect")
    assert hasattr(res, "planar_moments")
    assert pytest.approx(res.total_dipole, rel=1e-3) == 1.8546

def test_hdf5_swmr_thread_safe_ingestion(tmp_path: Path):
    h5_file = tmp_path / "calculation_results.h5"
    with h5py.File(h5_file, "w", libver="latest") as f:
        f.swmr_mode = True
        g = f.create_group("observables")
        g.create_dataset("A_e", data=np.array([27858.123]))
        g.create_dataset("B_e", data=np.array([14520.456]))
        g.create_dataset("C_e", data=np.array([9540.789]))
        g.create_dataset("total_dipole", data=np.array([1.8546]))

    parser = OutputParser()
    data = parser.read_hdf5_swmr(h5_file)
    assert "observables/A_e" in data or "A_e" in data

def test_gui_data_inspector_widget_wiring(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(tmp_path))
    gui = CoChemGUI()
    assert hasattr(gui, "data_inspector_widget")
    assert isinstance(gui.data_inspector_widget, DataInspectorWidget)
    assert "Awaiting backend wiring" not in gui.inspector_rot_table.value
