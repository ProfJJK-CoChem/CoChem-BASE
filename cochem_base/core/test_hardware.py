import pytest

from cochem_base.core.hardware import HardwareDiscovery


def test_hardware_discovery() -> None:
    profile = HardwareDiscovery.get_full_profile()
    profile_dict = profile.model_dump()
    assert "cpu_cores" in profile_dict
    assert "ram_gb" in profile_dict
