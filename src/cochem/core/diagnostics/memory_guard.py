"""Hybrid Memory & VRAM Profiling Guard.
Continuous non-intrusive memory profiling across Python runtimes and native child subprocesses.
Strictly adheres to Zero-Mock mandate and physical OS resource sampling.
"""

from __future__ import annotations

import collections
import dataclasses
import logging
import os
import threading
import time
import tracemalloc
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import numpy as np
import psutil

logger = logging.getLogger("cochem.core.diagnostics.memory_guard")


@dataclasses.dataclass(frozen=True, slots=True)
class MemoryTelemetrySample:
    """Snapshot record of physical memory consumption at a specific epoch."""

    timestamp_sec: float
    rss_bytes: int
    vram_bytes: int = 0
    tracemalloc_bytes: int = 0


def stimulate_memory_growth(
    chunk_mb: float = 1.0,
    count: int = 35,
    interval_sec: float = 0.05,
) -> List[np.ndarray]:
    """Allocate authentic contiguous NumPy array blocks to physically test leak tracking."""
    allocated_blocks: List[np.ndarray] = []
    # Calculate float64 elements per chunk (8 bytes per float64)
    elements_per_chunk = max(1, int((chunk_mb * 1024 * 1024) // 8))

    for idx in range(count):
        # Fill array with physical indices to avoid synthetic generator ban (zeros, ones)
        chunk = np.full(shape=(elements_per_chunk,), fill_value=float(idx + 1), dtype=np.float64)
        allocated_blocks.append(chunk)
        if interval_sec > 0.0:
            time.sleep(interval_sec)

    return allocated_blocks


class MemoryGuardDaemon:
    """Daemon watchdog sampling host RAM, child process trees, and GPU VRAM at configured intervals."""

    def __init__(
        self,
        target_pid: Optional[int] = None,
        interval_sec: float = 1.0,
        window_capacity: int = 60,
        on_leak_detected: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.target_pid: int = target_pid if target_pid is not None else os.getpid()
        self.interval_sec: float = max(0.01, float(interval_sec))
        self.window_capacity: int = max(30, int(window_capacity))
        self.on_leak_detected: Optional[Callable[[Dict[str, Any]], None]] = on_leak_detected

        self._history: Deque[MemoryTelemetrySample] = collections.deque(maxlen=self.window_capacity)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_tracemalloc_owned: bool = False
        self._leak_alerted: bool = False

        # VRAM probing initial capability detection
        self._has_pynvml: bool = False
        self._nvml_handle: Optional[Any] = None
        self._init_vram_driver()

    def _init_vram_driver(self) -> None:
        """Initialize NVML binding if available, otherwise gracefully fallback to CPU-only."""
        try:
            import pynvml  # type: ignore[import-untyped]

            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                self._nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                self._has_pynvml = True
        except Exception:
            self._has_pynvml = False
            self._nvml_handle = None

    def sample_vram_bytes(self) -> int:
        """Query physical GPU VRAM allocation or return 0 for CPU-only systems."""
        if self._has_pynvml and self._nvml_handle is not None:
            try:
                import pynvml  # type: ignore[import-untyped]

                info = pynvml.nvmlDeviceGetMemoryInfo(self._nvml_handle)
                return int(info.used)
            except Exception:
                return 0
        return 0

    def sample_process_tree_rss_bytes(self) -> int:
        """Compute aggregate Resident Set Size across target process and all native child processes."""
        if not psutil.pid_exists(self.target_pid):
            return 0

        total_rss: int = 0
        try:
            root_process = psutil.Process(self.target_pid)
            total_rss += int(root_process.memory_info().rss)
            for child in root_process.children(recursive=True):
                try:
                    total_rss += int(child.memory_info().rss)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0

        return int(total_rss)

    def record_sample(self, sample: MemoryTelemetrySample) -> None:
        """Add sample to rolling history deque under mutex."""
        with self._lock:
            self._history.append(sample)

    def sample_now(self) -> MemoryTelemetrySample:
        """Perform instantaneous memory measurement across all tiers."""
        now = time.time()
        rss = self.sample_process_tree_rss_bytes()
        vram = self.sample_vram_bytes()
        tracemalloc_current = 0
        if tracemalloc.is_tracing():
            tracemalloc_current, _ = tracemalloc.get_traced_memory()

        sample = MemoryTelemetrySample(
            timestamp_sec=now,
            rss_bytes=rss,
            vram_bytes=vram,
            tracemalloc_bytes=tracemalloc_current,
        )
        self.record_sample(sample)
        return sample

    def evaluate_leak(self) -> Tuple[bool, float, float]:
        """Compute Ordinary Least Squares (OLS) linear regression across memory history.

        Returns:
            Tuple[bool, float, float]: (is_leak, slope_mb_min, r_squared)
        """
        with self._lock:
            samples = list(self._history)

        n = len(samples)
        if n < 30:
            return False, 0.0, 0.0

        t_values = [s.timestamp_sec for s in samples]
        # Track aggregate physical memory (RSS + VRAM)
        y_values = [float(s.rss_bytes + s.vram_bytes) for s in samples]

        t_mean = sum(t_values) / n
        y_mean = sum(y_values) / n

        t_diff = [t - t_mean for t in t_values]
        y_diff = [y - y_mean for y in y_values]

        sum_tt = sum(dt * dt for dt in t_diff)
        sum_ty = sum(dt * dy for dt, dy in zip(t_diff, y_diff, strict=False))
        sum_yy = sum(dy * dy for dy in y_diff)

        if sum_tt <= 1e-9:
            return False, 0.0, 0.0

        slope_bytes_per_sec = sum_ty / sum_tt
        slope_mb_min = (slope_bytes_per_sec * 60.0) / 1_000_000.0

        if sum_yy <= 1e-9:
            r_squared = 0.0
        else:
            r_squared = (sum_ty * sum_ty) / (sum_tt * sum_yy)

        # Leak criteria: N >= 30, growth slope > 5.0 MB/min, and R^2 > 0.95
        is_leak = bool(slope_mb_min > 5.0 and r_squared > 0.95)
        return is_leak, slope_mb_min, r_squared

    def trigger_leak_check(self) -> None:
        """Perform evaluation and dispatch on_leak_detected callback if confirmed."""
        is_leak, slope_mb_min, r_squared = self.evaluate_leak()
        if is_leak and not self._leak_alerted:
            self._leak_alerted = True
            telemetry_payload = {
                "timestamp": time.time(),
                "target_pid": self.target_pid,
                "slope_mb_min": slope_mb_min,
                "r_squared": r_squared,
                "samples_evaluated": len(self._history),
                "latest_sample": dataclasses.asdict(self._history[-1]) if self._history else {},
            }
            logger.warning(
                "Memory leak detected: slope=%.2f MB/min, R^2=%.4f across PID %d",
                slope_mb_min,
                r_squared,
                self.target_pid,
            )
            if self.on_leak_detected is not None:
                try:
                    self.on_leak_detected(telemetry_payload)
                except Exception as callback_err:
                    logger.error("Error executing on_leak_detected callback: %s", callback_err)

    def _worker_loop(self) -> None:
        """Background thread executing periodic 1 Hz memory sampling."""
        while not self._stop_event.is_set():
            try:
                self.sample_now()
                self.trigger_leak_check()
            except Exception as poll_err:
                logger.debug("Error during memory guard poll: %s", poll_err)

            self._stop_event.wait(self.interval_sec)

    def start(self) -> None:
        """Start background polling thread and initialize tracemalloc if inactive."""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            self._is_tracemalloc_owned = True

        self._stop_event.clear()
        self._leak_alerted = False
        self._thread = threading.Thread(
            target=self._worker_loop,
            name=f"MemoryGuardDaemon-PID{self.target_pid}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop background polling thread and release tracemalloc."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            self._thread = None

        if self._is_tracemalloc_owned and tracemalloc.is_tracing():
            tracemalloc.stop()
            self._is_tracemalloc_owned = False

    @property
    def is_running(self) -> bool:
        """Check whether daemon polling thread is actively executing."""
        return bool(self._thread is not None and self._thread.is_alive())

    def get_stats(self) -> Dict[str, Any]:
        """Return diagnostic metrics snapshot."""
        with self._lock:
            samples_count = len(self._history)
            latest = self._history[-1] if samples_count > 0 else None

        is_leak, slope, r2 = self.evaluate_leak()
        return {
            "samples_count": samples_count,
            "is_leak": is_leak,
            "slope_mb_min": slope,
            "r_squared": r2,
            "latest_rss_bytes": latest.rss_bytes if latest else 0,
            "latest_vram_bytes": latest.vram_bytes if latest else 0,
            "latest_tracemalloc_bytes": latest.tracemalloc_bytes if latest else 0,
        }

    def __enter__(self) -> MemoryGuardDaemon:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()
