"""Unit and integration tests for Deliverable 5: Stage 6.0 Scribe GUI Dashboard
Reconstitution (scribe_gui_dashboard.py) & FAIR Report Bridge (Suggestion #115).

Method Matrix v4 (Stage 6.0) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Authentic manuscript and SI generation.
"""
from __future__ import annotations

import json
from pathlib import Path

from ui.voila_layout.scribe_gui_dashboard import ScribeDashboard, ScribeDashboardGUI

WATER_TELEMETRY = {
    "title": "Rotational Spectrum of H2O Monomer",
    "geometry": "O 0.0000 0.0000 0.1178\nH 0.0000 0.7555 -0.4712\nH 0.0000 -0.7555 -0.4712",
    "a_e": 27858.123,
    "b_e": 14520.456,
    "c_e": 9540.789,
    "delta_a": -120.450,
    "delta_b": -45.210,
    "delta_c": -22.100,
    "a_0": 27737.673,
    "b_0": 14475.246,
    "c_0": 9518.689,
    "total_dipole": 1.8546,
}

def test_scribe_dashboard_clean_import_and_instantiation():
    dashboard = ScribeDashboard(WATER_TELEMETRY)
    assert isinstance(dashboard, ScribeDashboardGUI)
    assert dashboard.title_input.value == "Rotational Spectrum of H2O Monomer"

def test_scribe_dashboard_latex_booktabs_rendering():
    dashboard = ScribeDashboard(WATER_TELEMETRY)
    docs = dashboard.compile_si_package()

    latex = docs["latex"]
    assert "\\begin{table}" in latex
    assert "\\toprule" in latex
    assert "\\bottomrule" in latex
    assert "27858.123" in latex
    assert "14520.456" in latex
    assert "9540.789" in latex
    assert "Dynamic IUPAC Nuclear Mass Audit" in latex

def test_scribe_dashboard_qcschema_export(tmp_path: Path):
    dashboard = ScribeDashboard(WATER_TELEMETRY)
    qcschema_path = tmp_path / "qcschema_record.json"
    dashboard.export_qcschema(qcschema_path)

    assert qcschema_path.exists()
    record = json.loads(qcschema_path.read_text(encoding="utf-8"))
    assert record.get("schema_name") == "qcschema_output" or "properties" in record

def test_scribe_dashboard_bibtex_syncer(tmp_path: Path):
    dashboard = ScribeDashboard(WATER_TELEMETRY)
    bib_path = tmp_path / "cochem_references.bib"
    dashboard.sync_bibtex(bib_path)

    assert bib_path.exists()
    bib_content = bib_path.read_text(encoding="utf-8")
    assert "@article" in bib_content or "@misc" in bib_content
