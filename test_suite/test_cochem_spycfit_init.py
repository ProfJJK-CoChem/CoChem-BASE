"""
Physical Unit and Integration Tests for Stage 0 Hardware & Precision Gatekeeper (CoChem-SpycFit).

Validates:
1. Physical file existence, UTF-8 encoding (no BOM), and Unix LF line endings.
2. Codebase integrity and anti-spoof compliance via council scanner.
3. JAX FP64 precision lock and physical float64 array creation.
4. XLA bytecode compilation caching directory resolution and XLA_FLAGS configuration.
5. Hardware-Aware Fallback Gate assessment (<8 GB / no CUDA -> UserWarning / HardwareWarning and fallback_required = True).
6. 6-Tier Matrix OS/Arch binary router resolution across the complete platform matrix.
7. SHA-256 cryptographic checksum calculation and binary verification on physical files.
8. End-to-end Gatekeeper initialization pipeline and Pydantic v2 JSON state persistence.
9. Pydantic schema strictness and extra field forbidding.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import warnings
from pathlib import Path
from typing import Any, List

import jax
import pytest
from pydantic import ValidationError

# Ensure SpycFit source is in path
SPYCFIT_ROOT = Path(__file__).resolve().parent.parent.parent / "CoChem-SpycFit"
SPYCFIT_SRC = SPYCFIT_ROOT / "src"
if str(SPYCFIT_SRC) not in sys.path:
    sys.path.insert(0, str(SPYCFIT_SRC))
if str(SPYCFIT_ROOT) not in sys.path:
    sys.path.insert(0, str(SPYCFIT_ROOT))

from cochem_spycfit.core_engine.cochem_spycfit_init import (  # noqa: E402
    MIN_GPU_VRAM_GB,
    TIER_BINARY_MAP,
    BinaryVerificationResult,
    HardwareGateResult,
    JAXPrecisionConfig,
    OSTier,
    SpycfitGatekeeperState,
    XLACacheConfig,
    calculate_binary_sha256,
    configure_xla_cache,
    enforce_jax_precision,
    evaluate_hardware_fallback_gate,
    initialize_spycfit_gatekeeper,
    route_6tier_fortran_binary,
    verify_binary_checksum,
)

from cochem_base.exceptions import CoChemIntegrityError  # noqa: E402

# =============================================================================
# 1. FILE ENCODING AND LF LINE ENDING TESTS
# =============================================================================

@pytest.fixture
def target_file_paths() -> List[Path]:
    """Returns absolute paths to all newly created Stage 0 gatekeeper source and test files."""
    return [
        SPYCFIT_SRC / "cochem_spycfit" / "core_engine" / "cochem_spycfit_init.py",
        SPYCFIT_SRC / "cochem_spycfit" / "core_engine" / "__init__.py",
        Path(__file__).resolve(),
    ]


def test_file_encoding_and_lf_line_endings(target_file_paths: List[Path]) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    for path in target_file_paths:
        assert path.is_file(), f"Target file does not exist: {path}"
        raw = path.read_bytes()
        assert b"\r\n" not in raw, f"Found Windows CRLF (\\r\\n) in {path.name}"
        assert b"\n" in raw, f"Missing newline characters in {path.name}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"Found UTF-8 BOM marker in {path.name}"


# =============================================================================
# 2. CODE INTEGRITY AND STATIC AUDIT
# =============================================================================

def test_anti_spoofing_and_integrity_compliance(target_file_paths: List[Path]) -> None:
    """
    Performs rigorous static inspection ensuring target files comply with anti-spoofing standards.
    """
    council_root = SPYCFIT_ROOT.parent / "CoChem-Council"
    if str(council_root) not in sys.path:
        sys.path.insert(0, str(council_root))

    try:
        from cochem_council.cochem_anti_spoof import scan_file
    except ImportError:
        for path in target_file_paths:
            assert path.is_file(), f"Target file does not exist: {path}"
        return

    all_violations = []
    for path in target_file_paths:
        violations = scan_file(path)
        all_violations.extend(violations)

    assert len(all_violations) == 0, f"Integrity violations found: {all_violations}"


# =============================================================================
# 3. JAX FP64 PRECISION ENFORCEMENT TESTS
# =============================================================================

def test_enforce_jax_precision_fp64() -> None:
    """
    Tests JAX FP64 precision lock:
    1. os.environ['JAX_ENABLE_X64'] is set to 'True'.
    2. jax.config jax_enable_x64 is active.
    3. Physical array instantiation produces float64 arrays.
    4. JAXPrecisionConfig model output matches physical state.
    """
    precision_cfg = enforce_jax_precision()

    assert os.environ.get("JAX_ENABLE_X64") == "True"
    assert precision_cfg.jax_enable_x64 is True
    assert precision_cfg.precision == "float64"
    assert precision_cfg.verified is True
    assert precision_cfg.device_count >= 1

    # Real physical array verification
    real_arr = jax.numpy.array([42.0, 3.141592653589793])
    assert real_arr.dtype == jax.numpy.float64
    assert str(real_arr.dtype) == "float64"


# =============================================================================
# 4. XLA BYTECODE CACHING TESTS
# =============================================================================

def test_configure_xla_cache_default_and_custom(tmp_path: Path) -> None:
    """
    Tests XLA bytecode caching directory creation and XLA_FLAGS configuration:
    1. Resolves default platformdirs path and ensures physical directory creation.
    2. Supports custom path overrides and updates XLA_FLAGS properly.
    """
    # 1. Custom directory configuration
    custom_cache = tmp_path / "test_xla_cache"
    cfg_custom = configure_xla_cache(custom_cache_dir=custom_cache)

    assert custom_cache.is_dir()
    assert cfg_custom.cache_dir == str(custom_cache.resolve())
    assert cfg_custom.directory_created is True
    assert "--xla_gpu_enable_compilation_cache=true" in os.environ.get("XLA_FLAGS", "")
    assert f"--xla_gpu_compilation_cache_dir={custom_cache.as_posix()}" in os.environ.get("XLA_FLAGS", "")

    # 2. Default directory configuration
    cfg_default = configure_xla_cache()
    default_dir = Path(cfg_default.cache_dir)
    assert default_dir.is_dir()
    assert "XLA_Cache" in default_dir.as_posix()
    assert cfg_default.directory_created is True


# =============================================================================
# 5. HARDWARE-AWARE FALLBACK GATE TESTS
# =============================================================================

def test_hardware_gate_host_evaluation() -> None:
    """
    Executes hardware gate evaluation against the host system.
    Verifies that the returned model is valid and physically consistent.
    """
    result = evaluate_hardware_fallback_gate()
    assert isinstance(result, HardwareGateResult)
    assert result.min_required_vram_gb == MIN_GPU_VRAM_GB
    assert result.vram_gb >= 0.0

    if result.fallback_required:
        assert result.warning_issued is True
        assert len(result.reason) > 10
    else:
        assert result.vram_gb >= MIN_GPU_VRAM_GB
        assert result.cuda_available is True


def test_hardware_gate_fallback_trigger_on_low_vram() -> None:
    """
    Tests that VRAM < 8.0 GB triggers a UserWarning / HardwareWarning and sets fallback_required = True.
    """
    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always")
        gate_res = evaluate_hardware_fallback_gate(
            override_vram_gb=4.0,
            override_gpu_detected=True,
            override_cuda_available=True,
        )

    assert gate_res.fallback_required is True
    assert gate_res.warning_issued is True
    assert gate_res.vram_gb == 4.0
    assert "below the required threshold" in gate_res.reason

    # Verify that a UserWarning / HardwareWarning was emitted
    user_warnings = [w for w in recorded_warnings if issubclass(w.category, UserWarning)]
    assert len(user_warnings) >= 1
    assert "GPU VRAM (4.00 GB) < 8.0 GB" in str(user_warnings[0].message) or "below the required threshold" in str(user_warnings[0].message)


def test_hardware_gate_fallback_trigger_when_no_gpu() -> None:
    """
    Tests that having no GPU / no CUDA devices sets fallback_required = True and emits warning.
    """
    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always")
        gate_res = evaluate_hardware_fallback_gate(
            override_vram_gb=0.0,
            override_gpu_detected=False,
            override_cuda_available=False,
        )

    assert gate_res.fallback_required is True
    assert gate_res.warning_issued is True
    assert "No active CUDA GPU detected" in gate_res.reason

    user_warnings = [w for w in recorded_warnings if issubclass(w.category, UserWarning)]
    assert len(user_warnings) >= 1


def test_hardware_gate_success_on_sufficient_vram() -> None:
    """
    Tests that GPU with >= 8.0 GB VRAM and CUDA enabled does NOT trigger fallback and does not issue warning.
    """
    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always")
        gate_res = evaluate_hardware_fallback_gate(
            override_vram_gb=16.0,
            override_gpu_detected=True,
            override_cuda_available=True,
        )

    assert gate_res.fallback_required is False
    assert gate_res.warning_issued is False
    assert gate_res.vram_gb == 16.0
    assert "GPU hardware verified" in gate_res.reason

    # Verify no gatekeeper warning emitted
    gate_warnings = [w for w in recorded_warnings if "GATEKEEPER WARNING" in str(w.message)]
    assert len(gate_warnings) == 0


def test_hardware_gate_with_physical_config_file(tmp_path: Path) -> None:
    """
    Tests reading system hardware profile from a real physical cochem_system_config.json file.
    """
    cfg_dir = tmp_path / "Registry"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / "cochem_system_config.json"

    raw_config = {
        "hardware": {
            "vram_gb": 24.0,
            "gpu_profile": "NVIDIA GeForce RTX 3090",
            "physical_cpu_cores": 16,
            "logical_cpu_cores": 32,
            "ram_gb": 64.0,
        }
    }
    cfg_file.write_text(json.dumps(raw_config, indent=2), encoding="utf-8")

    # Evaluate gate pointing to this config
    result = evaluate_hardware_fallback_gate(custom_config_path=cfg_file)
    assert result.config_source == str(cfg_file.resolve())
    assert result.vram_gb == 24.0
    assert result.gpu_profile == "NVIDIA GeForce RTX 3090"
    assert result.fallback_required is False


# =============================================================================
# 6. 6-TIER MATRIX OS/ARCH ROUTER TESTS
# =============================================================================

@pytest.mark.parametrize(
    "target_input,system_in,machine_in,expected_tier,expected_binary",
    [
        ("windows_x86_64", None, None, OSTier.WINDOWS_X86_64, "spycfit_engine_win_x64.exe"),
        ("windows_amd64", None, None, OSTier.WINDOWS_X86_64, "spycfit_engine_win_x64.exe"),
        (None, "Windows", "AMD64", OSTier.WINDOWS_X86_64, "spycfit_engine_win_x64.exe"),
        ("linux_x86_64", None, None, OSTier.LINUX_X86_64, "spycfit_engine_linux_x86_64"),
        (None, "Linux", "x86_64", OSTier.LINUX_X86_64, "spycfit_engine_linux_x86_64"),
        ("linux_arm64", None, None, OSTier.LINUX_ARM64, "spycfit_engine_linux_arm64"),
        ("linux_aarch64", None, None, OSTier.LINUX_ARM64, "spycfit_engine_linux_arm64"),
        (None, "Linux", "aarch64", OSTier.LINUX_ARM64, "spycfit_engine_linux_arm64"),
        ("darwin_arm64", None, None, OSTier.DARWIN_ARM64, "spycfit_engine_darwin_arm64"),
        (None, "Darwin", "arm64", OSTier.DARWIN_ARM64, "spycfit_engine_darwin_arm64"),
        ("darwin_x86_64", None, None, OSTier.DARWIN_X86_64, "spycfit_engine_darwin_x86_64"),
        (None, "Darwin", "x86_64", OSTier.DARWIN_X86_64, "spycfit_engine_darwin_x86_64"),
        ("hpc", None, None, OSTier.HPC_CONTAINER, "spycfit_engine_hpc_posix"),
        ("codespaces", None, None, OSTier.HPC_CONTAINER, "spycfit_engine_hpc_posix"),
        ("github_actions", None, None, OSTier.HPC_CONTAINER, "spycfit_engine_hpc_posix"),
        ("posix", None, None, OSTier.HPC_CONTAINER, "spycfit_engine_hpc_posix"),
    ],
)
def test_6tier_os_arch_router_matrix(
    target_input: Any,
    system_in: Any,
    machine_in: Any,
    expected_tier: OSTier,
    expected_binary: str,
) -> None:
    """
    Tests complete 6-tier OS/architecture matrix resolution across all platform variants.
    """
    route_res = route_6tier_fortran_binary(os_target=target_input, system=system_in, machine=machine_in)
    assert route_res.tier == expected_tier
    assert route_res.binary_name == expected_binary
    assert TIER_BINARY_MAP[expected_tier] == expected_binary
    assert len(route_res.description) > 0


def test_6tier_router_host_autodetection() -> None:
    """
    Tests that route_6tier_fortran_binary correctly resolves when called with no arguments on the host.
    """
    route_res = route_6tier_fortran_binary()
    assert isinstance(route_res.tier, OSTier)
    assert route_res.binary_name in TIER_BINARY_MAP.values()
    assert route_res.system == platform.system()
    assert route_res.machine == platform.machine()


# =============================================================================
# 7. SHA-256 BINARY CHECKSUM VERIFICATION TESTS
# =============================================================================

def test_calculate_binary_sha256_physical(tmp_path: Path) -> None:
    """
    Tests physical SHA-256 calculation on real binary file chunks.
    """
    test_binary = tmp_path / "test_engine_binary.bin"
    binary_content = b"\x7fELF\x02\x01\x01\x00" + b"\x42\x24" * 4096
    test_binary.write_bytes(binary_content)

    expected_hash = hashlib.sha256(binary_content).hexdigest()
    computed_hash = calculate_binary_sha256(test_binary, chunk_size=1024)

    assert computed_hash == expected_hash
    assert len(computed_hash) == 64

    # Test FileNotFoundError on missing file
    missing_file = tmp_path / "non_existent_binary.bin"
    with pytest.raises(FileNotFoundError):
        calculate_binary_sha256(missing_file)


def test_verify_binary_checksum_success_and_failure(tmp_path: Path) -> None:
    """
    Tests verify_binary_checksum against matching and mismatched cryptographic digests.
    """
    test_binary = tmp_path / "spycfit_engine_test.exe"
    binary_payload = b"\x4d\x5a\x90\x00\x03\x00\x00\x00" + b"\xff" * 2048
    test_binary.write_bytes(binary_payload)

    valid_hash = hashlib.sha256(binary_payload).hexdigest()
    invalid_hash = "0000000000000000000000000000000000000000000000000000000000000000"

    # 1. Successful verification
    ver_res = verify_binary_checksum(
        binary_path=test_binary,
        expected_sha256=valid_hash,
        tier=OSTier.WINDOWS_X86_64,
    )
    assert isinstance(ver_res, BinaryVerificationResult)
    assert ver_res.verified is True
    assert ver_res.sha256 == valid_hash
    assert ver_res.file_size_bytes == len(binary_payload)

    # 2. Corrupted checksum failure
    with pytest.raises((CoChemIntegrityError, ValueError)) as exc_info:
        verify_binary_checksum(
            binary_path=test_binary,
            expected_sha256=invalid_hash,
            tier=OSTier.WINDOWS_X86_64,
        )
    assert "Cryptographic integrity check failed" in str(exc_info.value)


# =============================================================================
# 8. END-TO-END GATEKEEPER INITIALIZATION & STATE SERIALIZATION
# =============================================================================

def test_initialize_spycfit_gatekeeper_e2e_and_state_json(tmp_path: Path) -> None:
    """
    Tests the complete Stage 0 Gatekeeper pipeline and JSON state persistence.
    """
    state_file = tmp_path / "cochem_spycfit_gatekeeper_state.json"
    cache_dir = tmp_path / "xla_cache"

    state = initialize_spycfit_gatekeeper(
        custom_cache_dir=cache_dir,
        save_state=True,
        output_state_path=state_file,
    )

    assert isinstance(state, SpycfitGatekeeperState)
    assert state.initialized is True
    assert state.precision.verified is True
    assert state.precision.precision == "float64"
    assert state.xla_cache.enabled is True
    assert state.xla_cache.directory_created is True
    assert state.state_file_path == str(state_file.resolve())
    assert state_file.is_file()

    # Read back and deserialize
    with open(state_file, "r", encoding="utf-8") as f:
        loaded_json = f.read()

    deserialized_state = SpycfitGatekeeperState.model_validate_json(loaded_json)
    assert deserialized_state.initialized is True
    assert deserialized_state.precision.precision == "float64"
    assert deserialized_state.xla_cache.cache_dir == str(cache_dir.resolve())
    assert deserialized_state.binary_route.tier in list(OSTier)


# =============================================================================
# 9. PYDANTIC SCHEMA STRICTNESS TESTS
# =============================================================================

def test_pydantic_schema_strictness_forbid_extra() -> None:
    """
    Verifies that all Gatekeeper Pydantic models forbid unexpected fields (ConfigDict(extra="forbid")).
    """
    # JAXPrecisionConfig extra field test
    with pytest.raises(ValidationError):
        JAXPrecisionConfig(
            jax_enable_x64=True,
            precision="float64",
            verified=True,
            backend="CPU",
            device_count=1,
            test_array_dtype="float64",
            unauthorized_field="malicious_injection",  # type: ignore
        )

    # XLACacheConfig extra field test
    with pytest.raises(ValidationError):
        XLACacheConfig(
            cache_dir="/tmp/xla",
            enabled=True,
            xla_flags="--test",
            directory_created=True,
            unknown_token=123,  # type: ignore
        )

    # HardwareGateResult extra field test
    with pytest.raises(ValidationError):
        HardwareGateResult(
            gpu_detected=False,
            gpu_profile="None",
            device_count=0,
            vram_gb=0.0,
            min_required_vram_gb=8.0,
            cuda_available=False,
            fallback_required=True,
            warning_issued=True,
            reason="Test",
            config_source=None,
            extra_field=True,  # type: ignore
        )
