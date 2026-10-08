"""AIMNet CPU isolation/pin contracts plus optional actual provisioned acceptance."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from cochem_base.orchestrator.aimnet_silo_manager import provision_aimnet_silo
from cochem_base.orchestrator.cochem_setup_phase_4 import (
    SiloType,
    _silo_import_name,
    filter_silos_by_manifest,
    get_default_silo_configs,
    provision_micro_silo,
)
from cochem_base.orchestrator.micro_silo_manager import validate_pins
from cochem_base.orchestrator.ml_silo_manager import TORCH_CPU_WHEEL
from cochem_base.orchestrator.silo_dependency_pins import DEFAULT_PINS


def test_exact_independent_aimnet_cpu_dependency_closure():
    pins = validate_pins(DEFAULT_PINS["aimnet2"])
    assert pins["aimnet"] == "0.2.0"
    assert pins["torch"] == "2.8.0+cpu"
    assert pins["warp-lang"] == "1.18.0"
    assert pins["nvalchemi-toolkit-ops"] == "0.4.1"
    assert "mace-torch" not in pins and "aimnet2calc" not in pins
    assert len(pins) == len(DEFAULT_PINS["aimnet2"])
    assert TORCH_CPU_WHEEL.endswith("#sha256=cb9a8ba8137ab24e36bf1742cb79a1294bd374db570f09fc15a5e1318160db4e")


def test_aimnet_nonempty_destination_cannot_be_overwritten(tmp_path):
    marker = tmp_path / "existing-work.txt"
    marker.write_text("preserve")
    with pytest.raises(SystemExit, match="nonempty"):
        provision_aimnet_silo(tmp_path)
    assert marker.read_text() == "preserve"


def test_explicit_aimnet_silo_request_has_own_path_and_correct_imports(tmp_path):
    selected = filter_silos_by_manifest({}, requested_silos=[SiloType.AIMNET2.value])
    configs = get_default_silo_configs(tmp_path, selected)
    aimnet = configs[SiloType.AIMNET2.value]
    assert aimnet.is_requested and aimnet.is_heavy
    assert not configs[SiloType.MACE.value].is_requested
    assert aimnet.target_path == str(tmp_path / "cochem_aimnet2_silo")
    assert aimnet.env_vars["CUDA_VISIBLE_DEVICES"] == ""
    assert _silo_import_name("warp-lang") == "warp"
    assert _silo_import_name("nvalchemi-toolkit-ops") == "nvalchemiops"
    assert aimnet.pip_packages == DEFAULT_PINS["aimnet2"]


def test_actual_isolated_aimnet_cpu_installation_and_phase4_audit(tmp_path):
    configured = os.environ.get("COCHEM_TEST_AIMNET_SILO")
    if not configured:
        pytest.skip("Set COCHEM_TEST_AIMNET_SILO to test an actually provisioned native AIMNet CPU installation")
    root = Path(configured).resolve()
    assert (root / "bin/python").is_file(), "A real pre-provisioned interpreter is required"
    selected = filter_silos_by_manifest({}, requested_silos=[SiloType.AIMNET2.value])
    config = get_default_silo_configs(tmp_path, selected)[SiloType.AIMNET2.value]
    config.target_path = str(root)
    audited = provision_micro_silo(config)
    assert audited.is_available, audited.error_detail
    assert audited.python_executable == str(root / "bin/python")
    assert audited.python_version.startswith("3.12.")
    receipt = json.loads((root / "aimnet-provisioning-receipt.json").read_text())
    assert receipt["native_cpu_probe"]["native_cpu_autograd"] is True
    assert receipt["native_cpu_probe"]["model_inference_performed"] is False
    assert receipt["cuda_capability_claimed"] is False
    assert receipt["verification"]["packages"] == validate_pins(DEFAULT_PINS["aimnet2"])
    script = """import importlib.metadata as m,json,sys
for forbidden in ['cochem-topos','mace-torch']:
 try:
  m.distribution(forbidden)
  raise AssertionError('controller/backend isolation failed: '+forbidden)
 except m.PackageNotFoundError:
  pass
print(json.dumps({'prefix':sys.prefix,'aimnet':m.version('aimnet')}))
"""
    process = subprocess.run([str(root / "bin/python"), "-I", "-c", script], check=True,
                             capture_output=True, text=True, timeout=10)
    assert json.loads(process.stdout) == {"prefix": str(root), "aimnet": "0.2.0"}
