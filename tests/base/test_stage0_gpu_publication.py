"""GPU metadata publication checks, including a real phase 2 audit round trip."""

from __future__ import annotations

import json
import os
import sys

import pytest

from cochem_base.cochem_core_registry_schema import CoChemSystemConfig
from cochem_base.core.cochem_core_registry_manager import save_system_config
from cochem_base.orchestrator.cochem_setup_phase_2 import run_phase_2_audit
from cochem_base.orchestrator.micro_silo_manager import provision_isolated_silo
from cochem_base.orchestrator.silo_dependency_pins import DEFAULT_PINS
from cochem_base.orchestrator.stage0_authority import (
    Stage0AuthorityError,
    _gpu_compute_from_phase2,
    build_stage0_authority,
)


@pytest.fixture
def publication_summary(tmp_path, monkeypatch):
    """Portable publication metadata fixture, not complete Stage 0 acceptance.

    Measure phase 2 and verify a real temporary interpreter. Other phase fields
    are minimal parser inputs, with an explicitly test-local interpreter-only
    lock; no scientific executables or results are substituted.
    """
    phase2 = run_phase_2_audit(output_dir=tmp_path / "observed")
    assert not phase2.errors
    silo = tmp_path / "interpreter"
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    checked = provision_isolated_silo(silo, python_version=version, imports=["json"])
    monkeypatch.setitem(DEFAULT_PINS, "core", [])
    reports = {number: {"status": "PASSED", "errors": []} for number in range(1, 12)}
    reports[2] = phase2.model_dump(mode="json")
    reports[3]["engines"] = {}
    reports[4]["silos"] = {"cochem_core_silo": {
        "is_available": True, "path": str(silo), "python_version": checked["python_version"],
        "python_executable": str(silo / ("Scripts/python.exe" if os.name == "nt" else "bin/python")),
    }}
    reports[6]["swmr_audit"] = {"swmr_supported": True}
    reports[11]["host_memory"] = {"bounded_total_ram_mb": phase2.memory.effective_memory_bytes / 1024**2}
    return {"artifact_dir": str(tmp_path / "published-runtime"), "phases_executed": [
        {"phase_number": number, "status": report["status"], "report": report}
        for number, report in reports.items()
    ]}


def test_actual_phase2_gpu_observations_survive_registry_publication(tmp_path, publication_summary):
    """Exercise the production builder, including its call to GPU publication."""
    phase2 = publication_summary["phases_executed"][1]["report"]
    metrics = _gpu_compute_from_phase2(phase2)
    config = build_stage0_authority(publication_summary)
    path = tmp_path / "published.json"
    save_system_config(config, path)
    restored = CoChemSystemConfig.model_validate_json(path.read_text())
    assert restored.verify_checksum()
    devices = phase2["gpu"]["devices"] if phase2["gpu"]["available"] else []
    assert restored.hardware.gpu_compute_metrics.device_count == len(devices)
    assert restored.hardware.gpu == restored.hardware.gpu_compute_metrics
    assert restored.hardware.gpu_profile == metrics.gpu_profile
    assert restored.hardware.vram_gb == metrics.vram_gb
    if devices:
        assert all(device["name"].strip() in metrics.gpu_profile for device in devices if device["name"].strip())
    raw = json.loads(path.read_text())
    raw["hardware"]["gpu_compute_metrics"]["device_count"] += 1
    assert not CoChemSystemConfig.model_validate(raw).verify_checksum()


def test_production_builder_consumes_phase2_device_metadata_on_cpu_hosts(publication_summary):
    """A parser fixture makes the publication hook regression portable."""
    publication_summary["phases_executed"][1]["report"]["gpu"] = {
        "available": True, "devices": [{"index": 0, "vendor": "NVIDIA", "name": "Metadata fixture A",
                                          "memory_total_bytes": 24 * 1024**3, "compute_capability": "8.6"}],
    }
    config = build_stage0_authority(publication_summary)
    assert config.hardware.gpu_compute_metrics.device_count == 1
    assert config.hardware.gpu_compute_metrics.compute_capability == "8.6"
    assert config.hardware.gpu_profile == "Metadata fixture A"
    assert config.hardware.vram_gb == 24


@pytest.mark.parametrize("devices,expected_capability,expected_vram", [
    ([{"index": 0, "vendor": "NVIDIA", "name": "Observed A", "memory_total_bytes": 24 * 1024**3,
       "compute_capability": "8.6"}], "8.6", 24),
    ([{"index": 0, "vendor": "NVIDIA", "name": "Observed A", "memory_total_bytes": 24 * 1024**3,
       "compute_capability": "8.6"},
      {"index": 1, "vendor": "NVIDIA", "name": "Observed B", "memory_total_bytes": 16 * 1024**3,
       "compute_capability": "8.9"}], None, 40),
    ([{"index": 0, "vendor": "NVIDIA", "name": "Observed A", "memory_total_bytes": 24 * 1024**3,
       "compute_capability": "8.6"},
      {"index": 1, "vendor": "NVIDIA", "name": "Observed B", "memory_total_bytes": None,
       "compute_capability": None}], None, 0),
    ([{"index": 0, "vendor": "NVIDIA", "name": "Observed A", "memory_total_bytes": 24 * 1024**3,
       "compute_capability": "8.6"},
      {"index": 0, "vendor": "AMD", "name": "Observed B", "memory_total_bytes": 16 * 1024**3,
       "compute_capability": "gfx1100"}], None, 40),
    ([{"index": 0, "vendor": "NVIDIA", "name": "Observed A", "memory_total_bytes": -1,
       "compute_capability": "N/A"}], None, 0),
])
def test_gpu_metadata_formats_do_not_invent_homogeneous_capability(devices, expected_capability, expected_vram):
    """These are metadata parser inputs, not scientific or physical acceptance."""
    metrics = _gpu_compute_from_phase2({"gpu": {"available": True, "devices": devices}})
    assert metrics.device_count == len(devices)
    assert metrics.compute_capability == expected_capability
    assert metrics.vram_gb == expected_vram
    assert metrics.gpu_profile == "; ".join(dict.fromkeys(device["name"] for device in devices))
    assert not metrics.fp64_capable and not metrics.mps_enabled
    assert metrics.fp64_tflops is None and metrics.tensor_cores is None


@pytest.mark.parametrize("gpu", [{}, {"available": True, "devices": []}, {"available": False}])
def test_missing_gpu_observations_retain_unavailable_defaults(gpu):
    metrics = _gpu_compute_from_phase2({"gpu": gpu})
    assert metrics.gpu_profile == "Unavailable"
    assert metrics.device_count == 0 and metrics.vram_gb == 0
    assert metrics.compute_capability is None


def test_malformed_device_observation_cannot_publish_gpu_authority():
    with pytest.raises(Stage0AuthorityError, match="GPU observations"):
        _gpu_compute_from_phase2({"gpu": {"available": True, "devices": [{"name": "Incomplete"}]}})
