import ctypes

from cochem.core.hardware.topology import (
    GROUP_AFFINITY,
    TopologyDiscoveryEngine,
    get_windows_group_affinity,
    get_windows_processor_group_count,
)


def test_get_windows_group_affinity_arithmetic():
    # Cores 0-63 reside in Group 0
    group0, mask0 = get_windows_group_affinity(0)
    assert group0 == 0
    assert mask0 == 1

    group3, mask3 = get_windows_group_affinity(3)
    assert group3 == 0
    assert mask3 == 8

    group63, mask63 = get_windows_group_affinity(63)
    assert group63 == 0
    assert mask63 == (1 << 63)

    # Core 64 resides in Group 1, core index 0 in group
    group64, mask64 = get_windows_group_affinity(64)
    assert group64 == 1
    assert mask64 == 1

    # Core 65 resides in Group 1, core index 1 in group
    group65, mask65 = get_windows_group_affinity(65)
    assert group65 == 1
    assert mask65 == 2

    # Core 130 resides in Group 2, core index 2 in group
    group130, mask130 = get_windows_group_affinity(130)
    assert group130 == 2
    assert mask130 == 4

def test_group_affinity_struct_layout():
    ga = GROUP_AFFINITY()
    ga.Group = 1
    ga.Mask = 0x00000001
    assert ga.Group == 1
    assert ga.Mask == 1

    # Win64 GROUP_AFFINITY layout: 8 bytes Mask + 2 bytes Group + 6 bytes Reserved = 16 bytes
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        assert ctypes.sizeof(GROUP_AFFINITY) == 16

def test_windows_processor_group_count():
    count = get_windows_processor_group_count()
    assert isinstance(count, int)
    assert count >= 1

def test_pin_scout_affinity():
    engine = TopologyDiscoveryEngine()
    # On Windows or Linux, attempts real OS affinity call on core 0
    result = engine.pin_scout_affinity(core_index=0)
    assert isinstance(result, bool)
