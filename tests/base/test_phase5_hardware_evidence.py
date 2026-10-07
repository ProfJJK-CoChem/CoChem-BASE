"""Missing capacity must not become fabricated hardware in the Golden Registry."""

import pytest

from cochem_base.orchestrator.cochem_setup_phase_5 import (
    ConfigLockError, validate_and_build_system_config,
)


@pytest.mark.parametrize("hardware", [None, {}, {"cpu_physical_cores": 2}, {"ram_gb": 8},
                                       {"ram_gb": float("nan"), "cpu_physical_cores": 2}])
def test_disabled_discovery_cannot_invent_hardware(hardware):
    with pytest.raises(ConfigLockError):
        validate_and_build_system_config({"hardware": hardware}, auto_detect_fallback=False)


def test_explicit_capacities_do_not_imply_hyperthreading():
    config = validate_and_build_system_config(
        {"hardware": {"ram_gb": 8, "cpu_physical_cores": 2}}, auto_detect_fallback=False,
    )
    assert config.hardware.cpu_physical_cores == 2
    assert config.hardware.logical_cpu_cores is None
    assert config.hardware.ram_gb == 8
