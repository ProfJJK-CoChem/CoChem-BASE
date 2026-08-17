import pytest

from cochem_base.config_loader import load_system_config_dict
from core_engine.cochem_core_registry_schema import CoChemConfig, HardwareConfig


def test_registry_schema_compilation():
    """Validates that the existing system config is perfectly Pydantic-compliant."""
    config_dict = load_system_config_dict()

    # Assert load_config returned a valid dictionary
    assert isinstance(config_dict, dict)

    # Assert Pydantic can ingest it without ValidationError
    try:
        validated_config = CoChemConfig(**config_dict)
    except Exception as e:
        pytest.fail(f"Config compilation failed Golden Schema validation: {e}")

    assert validated_config.hardware is not None
    assert isinstance(validated_config.hardware.physical_cpu_cores, int)

def test_mock_registry_schema_rejection():
    """Validates that Golden Schema violently rejects malformed data."""
    bad_hardware = {
        "physical_cpu_cores": -5,
        "logical_cpu_cores": 1,
        "ram_gb": 32.0,
        "avx512_support": True,
        "gpu_profile": "NVIDIA RTX",
        "vram_gb": 8.0,
        "os_target": "linux_x86_64"
    }
    with pytest.raises(ValueError):
        HardwareConfig(**bad_hardware)
