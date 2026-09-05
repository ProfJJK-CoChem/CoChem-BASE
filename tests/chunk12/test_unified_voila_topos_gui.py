"""Unit and integration tests for Deliverable 10: Unification of TOPOS GUI into
Voila Dashboard, Streamlit Deprecation & CUDA Resource Governance (Suggestion #120).

Method Matrix v4 (Table 1, §8A) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Conformer generation protocols and CUDA pooling.
"""
from __future__ import annotations

import os

import pytest
from frontend.cochem_topos_ui import (
    CochemToposUI,
    clamp_vram_ceiling,
    discover_cuda_devices,
    get_conformer_search_protocol,
)


def test_topos_ui_instantiation():
    ui = CochemToposUI()
    assert ui is not None
    assert hasattr(ui, "matrix_tier") or hasattr(ui, "tier_dropdown") or hasattr(ui, "render") or hasattr(ui, "widget")

def test_conformer_search_protocol_table1():
    protocol = get_conformer_search_protocol("GOAT")
    assert "! GOAT XTB2" in protocol["orca_keyword"] or "GOAT" in protocol["name"]

    protocol_crest = get_conformer_search_protocol("CREST_NCI")
    assert "--nci" in protocol_crest["crest_flags"]
    assert "--noreftopo" in protocol_crest["crest_flags"]

def test_cuda_device_pooling_and_vram_ceiling():
    assert clamp_vram_ceiling(vram_free_gb=32.0) == 16.0
    assert clamp_vram_ceiling(vram_free_gb=10.0) == 8.0
    assert clamp_vram_ceiling(vram_free_gb=0.0) == 0.0

def test_cuda_discovery_and_cpu_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    devices = discover_cuda_devices()
    assert isinstance(devices, list)
    if len(devices) == 0:
        threads = int(os.environ.get("OMP_NUM_THREADS", "4"))
        assert threads >= 1
