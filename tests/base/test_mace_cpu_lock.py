"""Verified package lock and immutable destination guards."""
import pytest
from cochem_base.orchestrator.micro_silo_manager import validate_pins
from cochem_base.orchestrator.silo_dependency_pins import DEFAULT_PINS
from cochem_base.orchestrator.ml_silo_manager import TORCH_CPU_WHEEL, provision_mace_silo


def test_actual_mace_lock_uses_available_release_and_pinned_cpu_wheel():
    pins=validate_pins(DEFAULT_PINS['mace'])
    assert pins['mace-torch']=='0.3.16'
    assert pins['torch']=='2.8.0+cpu'
    assert TORCH_CPU_WHEEL.endswith('#sha256=cb9a8ba8137ab24e36bf1742cb79a1294bd374db570f09fc15a5e1318160db4e')
    assert len(pins)==len(DEFAULT_PINS['mace'])


def test_nonempty_destination_is_not_repaired_or_deleted(tmp_path):
    marker=tmp_path/'keep.txt';marker.write_text('preserve')
    with pytest.raises(SystemExit,match='nonempty'):
        provision_mace_silo(tmp_path)
    assert marker.read_text()=='preserve'
