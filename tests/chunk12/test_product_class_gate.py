"""Unit and integration tests for Deliverable 6: Step 0 Product Class Gate (Classes A, B, C) &
Accuracy-Targeted Spend Governance (Suggestion #116).

Method Matrix v4 (§0, §3.3) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Dynamic UI reconfiguration and spend priority hierarchy.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from cochem_base.theory_matrix import (
    PRODUCT_CLASS_SPECS,
    SPEND_PRIORITY_HIERARCHY,
    ProductClass,
)
from ui.voila_layout.cochem_gui import CoChemGUI


def test_product_class_specifications():
    assert ProductClass.PRODUCT_A in PRODUCT_CLASS_SPECS
    assert ProductClass.PRODUCT_B in PRODUCT_CLASS_SPECS
    assert ProductClass.PRODUCT_C in PRODUCT_CLASS_SPECS

    assert "0.3% - 0.5%" in PRODUCT_CLASS_SPECS[ProductClass.PRODUCT_A]["target_accuracy"]
    assert "0.03% - 0.06%" in PRODUCT_CLASS_SPECS[ProductClass.PRODUCT_B]["target_accuracy"]
    assert "0.02% - 0.1%" in PRODUCT_CLASS_SPECS[ProductClass.PRODUCT_C]["target_accuracy"]

def test_spend_priority_hierarchy():
    assert len(SPEND_PRIORITY_HIERARCHY) >= 7
    assert "Geometry (R)" in SPEND_PRIORITY_HIERARCHY[0]
    assert "Delta B_vib" in SPEND_PRIORITY_HIERARCHY[1]
    assert "Frozen Monomers (A)" in SPEND_PRIORITY_HIERARCHY[2]

def test_gui_product_class_reconfiguration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(tmp_path))
    gui = CoChemGUI()

    gui.product_class_selector.value = ProductClass.PRODUCT_A.value
    assert "Product A" in gui.product_class_card.value

    gui.product_class_selector.value = ProductClass.PRODUCT_B.value
    assert gui.config_tabs.selected_index == 3

    gui.product_class_selector.value = ProductClass.PRODUCT_C.value
    assert gui.state.active_view == "inspector"
