"""
Zero-Mock Physical Validation Suite: Reconstructed SCRIBE Voila GUI Dashboard.
Method Matrix v4: §3.0, §13, §14, and SRS Chunk 4 Suggestion #36.
"""
import subprocess
import sys
import pytest

from ui.voila_layout.scribe_gui_dashboard import (
    ScribeDashboardGUI,
    ScribeDashboard,
    TargetJournal,
    SISectionConfig,
)


def test_clean_subprocess_import():
    """Validates that ui.voila_layout.scribe_gui_dashboard can be imported

    in an isolated Python process with zero ModuleNotFoundError or circular import crash.
    """
    code = "from ui.voila_layout.scribe_gui_dashboard import ScribeDashboardGUI, ScribeDashboard; print('OK')"
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert res.returncode == 0, f"Import failed with stderr: {res.stderr}"
    assert "OK" in res.stdout


def test_scribe_dashboard_instantiation_and_aliasing():
    """Validates ScribeDashboard instantiation and backward compatibility alias."""
    dashboard = ScribeDashboard()
    assert isinstance(dashboard, ScribeDashboardGUI)
    assert dashboard.target_journal_dropdown.value == TargetJournal.LATEX_GENERIC.value
    assert dashboard.cb_mendeleev.value is True
    assert dashboard.preview_latex.value != ""


def test_scribe_dashboard_authentic_telemetry_compilation():
    """Validates that authentic quantum chemical telemetry (SO2) compiles

    into valid LaTeX and Markdown SI tables with dynamic Mendeleev masses and B_e vs B_0.
    """
    # Authentic physical coordinates and spectroscopic parameters of SO2
    so2_xyz = (
        "S   0.00000000   0.00000000   0.36210000\n"
        "O   0.00000000   1.24070000  -0.36210000\n"
        "O   0.00000000  -1.24070000  -0.36210000\n"
    )
    telemetry = {
        "title": "Equilibrium Structure and Spectroscopic Parameters of SO2",
        "geometry": so2_xyz,
        "a_e": 60778.52,
        "b_e": 10318.06,
        "c_e": 8820.61,
        "delta_a": -452.12,
        "delta_b": -52.34,
        "delta_c": -41.20,
        "a_0": 60326.40,
        "b_0": 10265.72,
        "c_0": 8779.41,
    }

    dashboard = ScribeDashboardGUI(telemetry_data=telemetry)
    compiled = dashboard.compile_si_package()

    latex_doc = compiled["latex"]
    markdown_doc = compiled["markdown"]

    # 1. Rotational Observables & B_e vs B_0 validation
    assert "Equilibrium ($B_e$) and Effective Ground-State ($B_0$)" in latex_doc
    assert "60778.520" in latex_doc
    assert "10318.060" in latex_doc
    assert "60326.400" in latex_doc
    assert "[M, D]" in latex_doc

    # 2. Dynamic Mendeleev Mass Audit Table verification
    assert "Dynamic IUPAC Nuclear Mass Audit (Mendeleev Mandate)" in latex_doc
    assert "Dynamic IUPAC Nuclear Mass Audit (Mendeleev Mandate)" in markdown_doc
    assert "S" in latex_doc
    assert "O" in latex_doc
    # Dynamic mass of S is ~32.06 and O is ~15.999
    assert "32.0" in latex_doc or "31.9" in latex_doc
    assert "15.999" in latex_doc

    # 3. Cartesian Coordinates verification
    assert "Cartesian Geometry Coordinates" in latex_doc
    assert "1.24070000" in latex_doc
    assert "```xyz" in markdown_doc
    assert "1.24070000" in markdown_doc
