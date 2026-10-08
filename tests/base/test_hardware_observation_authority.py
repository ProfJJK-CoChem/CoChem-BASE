"""Real host observation and truthful unavailable-hardware schema boundaries."""

import json
import os
import subprocess
import sys

import psutil
import pytest
from pydantic import ValidationError

from cochem_base.bench_engine import BenchHardwareSchema
from cochem_base.cochem_core_registry_schema import HardwareSchema
from cochem_base.core_engine.environment_detector import detect_environment
from cochem_base.core_engine.hardware_profiler import probe_avx512, profile_hardware
from cochem_base.orchestrator.cochem_system_config import HardwareProfile


def _actual_capacity():
    return {"ram_gb": psutil.virtual_memory().total / 1024**3,
            "physical_cpu_cores": psutil.cpu_count(logical=False),
            "logical_cpu_cores": psutil.cpu_count(logical=True)}


@pytest.mark.parametrize("model", [HardwareSchema, HardwareProfile, BenchHardwareSchema])
@pytest.mark.parametrize("observation", [None, False, True, "false"])
def test_isa_alias_roundtrip_preserves_unknown_and_negative(model, observation):
    record = model(**_actual_capacity(), avx512_support=observation)
    expected = False if observation == "false" else observation
    assert record.avx512_support is expected
    assert record.avx_512_capable is expected
    restored = model.model_validate_json(record.model_dump_json())
    assert restored.avx512_support is expected
    assert restored.avx_512_capable is expected


@pytest.mark.parametrize("model", [HardwareSchema, HardwareProfile, BenchHardwareSchema])
def test_missing_isa_does_not_become_a_negative_measurement(model):
    record = model(**_actual_capacity())
    assert record.avx512_support is None
    assert record.avx_512_capable is None


@pytest.mark.parametrize("model", [HardwareSchema, HardwareProfile, BenchHardwareSchema])
@pytest.mark.parametrize("left,right", [(True, False), (None, False), ("false", True)])
def test_conflicting_isa_aliases_fail_closed(model, left, right):
    with pytest.raises(ValidationError, match="Conflicting AVX-512"):
        model(**_actual_capacity(), avx_512_capable=left, avx512_support=right)


def test_actual_host_probe_and_registry_observation_match():
    from cochem_base.cochem_core_registry_schema import discover_host_hardware
    observed, status = probe_avx512(detect_environment())
    measured = profile_hardware()
    registry = discover_host_hardware()
    assert measured.physical_cores == psutil.cpu_count(logical=False)
    assert measured.avx512 is observed
    assert measured.avx512_probe_status == status
    assert registry.avx_512_capable is observed
    assert registry.avx512_support is observed
    assert 0 < measured.elapsed_seconds <= 1.5


def test_native_stamp_does_not_replace_observation_with_configured_isa(tmp_path):
    from cochem_base.core_engine.cochem_provenance_stamper import _detect_avx512
    observed, status = probe_avx512(detect_environment())
    path = tmp_path / "configuration.json"
    path.write_text(json.dumps({"hardware": {"avx512_support": observed is not True}}))
    stamped, details = _detect_avx512(path)
    assert stamped is observed
    assert details["detection_method"] == status
    assert details["observation_status"] == ("unavailable" if observed is None else "measured")


def test_environment_device_and_isa_labels_cannot_fabricate_hardware():
    # Genuine child uses the actual host. The contrary environment labels are
    # configuration requests, never simulated telemetry or native acceptance.
    code = '''
import json
from cochem_base.core_engine.hardware_profiler import profile_hardware
from cochem_base.core_engine.cochem_core_config_compiler import HardwareProfileSpec, HardwareEnvGenerator
actual=profile_hardware()
compiled=HardwareProfileSpec.from_system()
assert compiled.physical_cores == actual.physical_cores
assert compiled.cpu_count == actual.logical_cores
assert compiled.has_avx512 is actual.avx512
assert compiled.observed_gpu_count == actual.gpu_device_count
assert compiled.gpu_probe_status == actual.gpu_probe_status
assert compiled.gpu_vram_gb == min(actual.gpu_vram_per_device_bytes,default=0)/1024**3
assert compiled.memory_total_gb == actual.allocatable_ram_bytes/1024**3
assert compiled.p_cores == 0 and compiled.e_cores == 0
assert compiled.has_cuda is False and compiled.mps_enabled is False
env=HardwareEnvGenerator.generate_environment(compiled,requested_threads=compiled.cpu_count)
assert int(env['OMP_NUM_THREADS']) <= actual.allocatable_compute_cores
print(json.dumps({'cores':compiled.physical_cores,'slots':actual.allocatable_compute_cores,'avx512':compiled.has_avx512,'gpu_status':compiled.gpu_probe_status}))
'''
    environment = {**os.environ, "CUDA_VISIBLE_DEVICES": "9999", "COCHEM_FORCE_AVX512": "true",
                   "COCHEM_FORCE_AVX2": "false", "CUDA_MPS_PIPE_DIRECTORY": "/unobserved-mps"}
    result = subprocess.run([sys.executable, "-B", "-c", code], env=environment,
                            capture_output=True, text=True, timeout=30, check=True)
    observed = json.loads(result.stdout.splitlines()[-1])
    assert observed["cores"] == psutil.cpu_count(logical=False)
    assert observed["slots"] >= 1


def test_omitted_compiler_hardware_cannot_fabricate_capacity():
    from cochem_base.core_engine.cochem_core_config_compiler import (
        ConfigCompiler,
        HardwareEnvGenerator,
        HardwareProfileSpec,
    )
    with pytest.raises(ValidationError, match="cpu_count"):
        HardwareProfileSpec()
    with pytest.raises(ValidationError, match="memory_total_gb"):
        ConfigCompiler(hardware_profile={})
    with pytest.raises(ValidationError, match="physical_cores"):
        HardwareEnvGenerator.generate_environment({})
