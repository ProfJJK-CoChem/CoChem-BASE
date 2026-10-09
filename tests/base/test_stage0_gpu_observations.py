"""Validate GPU publication from phase observations without intercepting probes."""
import pytest

from cochem_base.orchestrator.stage0_authority import Stage0AuthorityError, _gpu_compute_from_phase2


def device(index=0, *, vendor="NVIDIA", capability="8.6", memory=24 * 1024**3):
    return {"index": index, "vendor": vendor, "name": "RTX 3090", "compute_capability": capability,
            "memory_total_bytes": memory}


def publish(*devices):
    return _gpu_compute_from_phase2({"gpu": {"available": True, "devices": list(devices)}})


def test_observed_device_name_memory_and_common_cuda_capability_are_preserved():
    observed = publish(device(), device(1))
    assert observed.gpu_profile == "RTX 3090"
    assert observed.device_count == 2
    assert observed.vram_gb == 48
    assert observed.compute_capability == "8.6"


@pytest.mark.parametrize("report", [{}, {"gpu": {"available": False}},
                                    {"gpu": {"available": True, "devices": []}}])
def test_absent_observations_remain_unknown(report):
    observed = _gpu_compute_from_phase2(report)
    assert observed.device_count is None
    assert observed.vram_gb is None
    assert observed.compute_capability is None


def test_partial_memory_is_not_mislabeled_as_total_memory():
    observed = publish(device(), device(1, memory=None))
    assert observed.device_count == 2
    assert observed.vram_gb is None


@pytest.mark.parametrize("other", [device(1, capability="9.0"), device(1, capability=None),
                                  device(1, capability="unknown"), device(1, vendor="AMD", capability="8.6")])
def test_heterogeneous_or_unmeasured_devices_have_no_common_cuda_capability(other):
    assert publish(device(), other).compute_capability is None


def test_invalid_memory_and_invalid_device_schema_are_rejected():
    with pytest.raises(Stage0AuthorityError, match="memory"):
        publish(device(memory=-1))
    with pytest.raises(Stage0AuthorityError, match="observations"):
        publish({"vendor": "NVIDIA"})
