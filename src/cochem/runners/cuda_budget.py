"""Dynamic CUDA memory budgeter and asynchronous backpressure manager.

Provides physical hardware introspection across NVML and PyTorch CUDA runtimes
with automatic headless/CPU fallback and exponential backoff polling.
"""

import asyncio
import logging
import os
import time
import warnings
from typing import Dict, Optional

from src.cochem.hpc.models import CudaMemoryExhaustionError, CudaResourceBudget

# Filter legacy pynvml deprecation/future warnings
warnings.filterwarnings("ignore", category=FutureWarning, message=r".*pynvml.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, message=r".*pynvml.*")

logger = logging.getLogger(__name__)


class CudaMemoryManager:
    """Introspects physical GPU VRAM and manages non-blocking allocation budgeting."""

    def __init__(self) -> None:
        self._nvml_initialized: bool = False
        self._nvml_available: bool = False
        self._init_nvml_subsystem()

    def _init_nvml_subsystem(self) -> None:
        """Attempt safe initialization of the NVML physical hardware query driver."""
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning)
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                import pynvml  # type: ignore

                pynvml.nvmlInit()
            self._nvml_initialized = True
            self._nvml_available = True
        except Exception as exc:
            logger.debug("NVML initialization unavailable: %s", exc)
            self._nvml_initialized = False
            self._nvml_available = False

    def get_device_count(self) -> int:
        """Determine total accessible physical CUDA accelerators, defaulting gracefully to 0."""
        if self._nvml_available:
            try:
                import pynvml  # type: ignore

                count = pynvml.nvmlDeviceGetCount()
                return int(count)
            except Exception as exc:
                logger.debug("Failed querying NVML device count: %s", exc)

        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                return int(torch.cuda.device_count())
        except Exception as exc:
            logger.debug("Failed querying PyTorch CUDA device count: %s", exc)

        return 0

    def query_vram_megabytes(self, device_id: int) -> tuple[int, int]:
        """Query physical (total_mb, free_mb) for a specific GPU device index."""
        # 1. Primary NVML introspection
        if self._nvml_available:
            try:
                import pynvml  # type: ignore

                handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                total_mb = int(mem.total // (1024 * 1024))
                free_mb = int(mem.free // (1024 * 1024))
                return total_mb, free_mb
            except Exception as exc:
                logger.debug("Failed NVML query on device %s: %s", device_id, exc)

        # 2. Secondary PyTorch runtime query
        try:
            import torch  # type: ignore

            if torch.cuda.is_available() and device_id < torch.cuda.device_count():
                free_bytes, total_bytes = torch.cuda.mem_get_info(device_id)
                total_mb = int(total_bytes // (1024 * 1024))
                free_mb = int(free_bytes // (1024 * 1024))
                return total_mb, free_mb
        except Exception as exc:
            logger.debug("Failed PyTorch mem_get_info query on device %s: %s", device_id, exc)

        device_count = self.get_device_count()
        raise CudaMemoryExhaustionError(
            f"Physical CUDA device ordinal {device_id} is unavailable or not accessible "
            f"(Total accelerators detected: {device_count})."
        )

    def get_device_budget(
        self,
        device_id: int,
        reserved_headroom_mb: int = 1024,
        fractional_limit: float = 0.85,
    ) -> CudaResourceBudget:
        """Inspect and compute current allocatable resource budget for a GPU device."""
        total_mb, free_mb = self.query_vram_megabytes(device_id)
        return CudaResourceBudget(
            device_id=device_id,
            total_vram_mb=total_mb,
            free_vram_mb=free_mb,
            reserved_headroom_mb=reserved_headroom_mb,
            fractional_limit=fractional_limit,
        )

    def prepare_worker_environment(
        self,
        device_id: int,
        base_env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Generate subprocess environment enforcing GPU affinity and anti-fragmentation."""
        env = dict(os.environ) if base_env is None else dict(base_env)
        env["CUDA_VISIBLE_DEVICES"] = str(device_id)
        env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
        return env

    async def acquire_vram_budget(
        self,
        device_id: int,
        required_mb: int,
        timeout_seconds: float = 30.0,
        poll_interval: float = 0.5,
    ) -> CudaResourceBudget:
        """Asynchronously acquire VRAM budget with non-blocking exponential backpressure."""
        start_time = time.monotonic()
        current_sleep = min(0.05, poll_interval)

        while True:
            try:
                budget = self.get_device_budget(device_id)
                if budget.available_vram_mb >= required_mb:
                    return budget
            except CudaMemoryExhaustionError as exc:
                # Device unavailable or non-existent
                logger.debug("Device %s currently unavailable or constrained: %s", device_id, exc)

            elapsed = time.monotonic() - start_time
            if elapsed >= timeout_seconds:
                raise CudaMemoryExhaustionError(
                    f"CUDA memory acquisition timeout: {required_mb} MB requested on device {device_id} "
                    f"could not be secured within {timeout_seconds:.2f}s."
                )

            sleep_duration = min(current_sleep, timeout_seconds - elapsed)
            if sleep_duration > 0:
                await asyncio.sleep(sleep_duration)
            current_sleep = min(current_sleep * 2.0, poll_interval)
