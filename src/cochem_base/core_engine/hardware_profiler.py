"""Bounded, measured hardware ingress for the Stage 0 authority registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import time

import psutil

from .environment_detector import EnvironmentProfile, detect_environment
from .preflight import PreflightValidationError
from .cpu_allocation import CPUAllocationPolicy, cpu_allocation_policy


@dataclass(frozen=True)
class HardwareProfile:
    environment: EnvironmentProfile
    physical_cores: int
    logical_cores: int
    available_cpu_ids: tuple[int, ...]
    ram_bytes: int
    allocatable_ram_bytes: int
    available_ram_bytes: int
    avx512: bool | None
    vram_bytes: int | None
    gpu_device_count: int | None
    gpu_probe_status: str
    elapsed_seconds: float
    cpu_allocation_policy: CPUAllocationPolicy = CPUAllocationPolicy.PHYSICAL_CORES

    @property
    def allocatable_compute_cores(self) -> int:
        """Audited process slots, with the allocation unit recorded separately."""
        capacity = (self.logical_cores if self.cpu_allocation_policy is CPUAllocationPolicy.GITHUB_HOSTED_VCPUS
                    else self.physical_cores)
        return min(capacity, len(self.available_cpu_ids))


def _memory_budget(total: int, available: int) -> tuple[int, int]:
    """Respect kernel cgroup memory ceilings and actual consumption."""
    for limit_file, usage_name in (
        (Path("/sys/fs/cgroup/memory.max"), "memory.current"),
        (Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"), "memory.usage_in_bytes"),
    ):
        if not limit_file.is_file():
            continue
        value = limit_file.read_text().strip()
        if value == "max":
            continue
        limit = int(value)
        if 0 < limit < total:
            usage_file = limit_file.with_name(usage_name)
            if not usage_file.is_file():
                raise PreflightValidationError("Cgroup memory usage is unavailable")
            remaining = max(0, limit - int(usage_file.read_text().strip()))
            return limit, min(available, remaining)
    return total, available


def _cpu_budget(allowed: tuple[int, ...]) -> tuple[int, ...]:
    """Bound concurrent CPU capacity by the actual kernel scheduling quota."""
    maximum = Path("/sys/fs/cgroup/cpu.max")
    if maximum.is_file():
        quota, period = maximum.read_text().strip().split()
        if quota != "max":
            value = int(quota) / int(period)
            if value <= 0:
                raise PreflightValidationError("No cgroup CPU quota is available")
            return allowed[:max(1, int(value))]
    quota_file = Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
    period_file = quota_file.with_name("cpu.cfs_period_us")
    if quota_file.is_file() and period_file.is_file():
        quota = int(quota_file.read_text())
        if quota > 0:
            return allowed[:max(1, quota // int(period_file.read_text()))]
    return allowed


def profile_hardware(timeout: float = 1.0) -> HardwareProfile:
    """Probe CPU/RAM and bounded GPU telemetry without importing ML frameworks.

    Unavailable optional device observations are represented by ``None``. An
    absent NVIDIA utility does not establish that no other GPU exists.
    """
    if timeout <= 0 or timeout > 1.5:
        raise ValueError("Hardware ingress timeout must be in (0, 1.5] seconds")
    started = time.monotonic()
    allocation_policy = cpu_allocation_policy()
    environment = detect_environment()
    physical = psutil.cpu_count(logical=False)
    logical = psutil.cpu_count(logical=True)
    memory = psutil.virtual_memory()
    if not physical or not logical or physical > logical or memory.total <= 0:
        raise PreflightValidationError("Physical CPU topology or RAM is undefined")
    try:
        allowed = tuple(psutil.Process().cpu_affinity())
    except AttributeError:  # macOS does not expose affinity through psutil.
        allowed = tuple(range(logical))
    if not allowed:
        raise PreflightValidationError("No CPU is available to this process")
    allowed = _cpu_budget(allowed)
    allocatable_ram, available_ram = _memory_budget(memory.total, memory.available)

    avx512: bool | None = None
    if environment.system == "Linux":
        cpuinfo = Path("/proc/cpuinfo")
        if cpuinfo.is_file():
            flags = cpuinfo.read_text(encoding="utf-8")
            avx512 = "avx512f" in flags.split()
    elif environment.system == "Darwin":
        if environment.machine.lower() in {"arm64", "aarch64"}:
            avx512 = False
        else:
            try:
                flags = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.leaf7_features"],
                    capture_output=True, text=True, check=True,
                    timeout=max(0.01, timeout - (time.monotonic() - started)),
                ).stdout
                avx512 = "AVX512F" in flags.upper().split()
            except (OSError, subprocess.SubprocessError):
                avx512 = None

    vram: int | None = None
    gpu_count: int | None = None
    gpu_status = "unavailable"
    nvidia = shutil.which("nvidia-smi")
    remaining = timeout - (time.monotonic() - started)
    if nvidia and remaining > 0:
        try:
            probe = subprocess.run(
                [nvidia, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=remaining, check=True,
            )
            readings = [int(line.strip()) for line in probe.stdout.splitlines() if line.strip()]
            if not readings or any(value < 0 for value in readings):
                raise ValueError("GPU memory telemetry is missing or invalid")
            vram = sum(readings) * 1024**2
            gpu_count = len(readings)
            gpu_status = "measured"
        except (OSError, ValueError, subprocess.SubprocessError):
            gpu_status = "probe_failed"
    elapsed = time.monotonic() - started
    if elapsed > timeout:
        raise PreflightValidationError(f"Hardware ingress exceeded {timeout:g}s deadline")
    return HardwareProfile(
        environment, physical, logical, allowed, memory.total, allocatable_ram, available_ram,
        avx512, vram, gpu_count, gpu_status, elapsed, allocation_policy,
    )
