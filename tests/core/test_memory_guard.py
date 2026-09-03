"""Unit tests for Hybrid Memory & VRAM Profiling Guard.
Strictly adheres to Zero-Mock mandate and physical OS resource sampling.
"""

import time
from typing import List

import numpy as np

from cochem.core.diagnostics.memory_guard import (
    MemoryGuardDaemon,
    MemoryTelemetrySample,
    stimulate_memory_growth,
)


def test_memory_guard_lifecycle() -> None:
    """Verify MemoryGuardDaemon starts, samples, and stops cleanly."""
    daemon = MemoryGuardDaemon(interval_sec=0.1, window_capacity=40)
    assert not daemon.is_running

    with daemon:
        assert daemon.is_running
        time.sleep(0.35)
        stats = daemon.get_stats()
        assert stats["samples_count"] >= 2
        assert stats["latest_rss_bytes"] > 0

    assert not daemon.is_running


def test_stimulate_memory_growth_allocates_authentic_arrays() -> None:
    """Verify stimulate_memory_growth produces genuine contiguous NumPy memory chunks."""
    chunks = stimulate_memory_growth(chunk_mb=0.5, count=10, interval_sec=0.01)
    assert len(chunks) == 10
    total_bytes = sum(c.nbytes for c in chunks)
    assert total_bytes >= 10 * 0.5 * 1024 * 1024 * 0.99
    assert isinstance(chunks[0], np.ndarray)


def test_ols_leak_detection_stable_memory_no_false_positive() -> None:
    """Verify that flat/stable memory series does not trigger false positive leak alert."""
    daemon = MemoryGuardDaemon(interval_sec=0.1, window_capacity=50)

    base_time = 1000.0
    base_bytes = 100 * 1024 * 1024  # 100 MB constant baseline

    # Populate 35 samples with stable jitter (+/- 50 KB)
    for i in range(35):
        jitter = (i % 5 - 2) * 10000
        sample = MemoryTelemetrySample(
            timestamp_sec=base_time + i * 1.0,
            rss_bytes=base_bytes + jitter,
            vram_bytes=0,
            tracemalloc_bytes=base_bytes // 2,
        )
        daemon.record_sample(sample)

    is_leak, slope_mb_min, r2 = daemon.evaluate_leak()
    assert not is_leak
    assert slope_mb_min < 5.0


def test_ols_leak_detection_confirmed_leak_trigger() -> None:
    """Verify that linear sustained growth (>5 MB/min, R^2 > 0.95, N >= 30) triggers leak flag."""
    detected_telemetry: List[dict] = []

    def on_leak(metrics: dict) -> None:
        detected_telemetry.append(metrics)

    daemon = MemoryGuardDaemon(
        interval_sec=0.1,
        window_capacity=50,
        on_leak_detected=on_leak,
    )

    base_time = 1000.0
    base_bytes = 100 * 1024 * 1024
    # Growth rate: 10 MB per minute = 10 * 1e6 / 60 bytes/sec ~= 166,666 bytes/sec
    growth_per_sec = 200_000

    for i in range(35):
        sample = MemoryTelemetrySample(
            timestamp_sec=base_time + i * 1.0,
            rss_bytes=int(base_bytes + i * growth_per_sec),
            vram_bytes=0,
            tracemalloc_bytes=50_000_000,
        )
        daemon.record_sample(sample)

    is_leak, slope_mb_min, r2 = daemon.evaluate_leak()
    assert is_leak
    assert slope_mb_min > 5.0
    assert r2 > 0.95

    # Trigger inspection loop sweep
    daemon.trigger_leak_check()
    assert len(detected_telemetry) == 1
    assert detected_telemetry[0]["slope_mb_min"] > 5.0
    assert detected_telemetry[0]["r_squared"] > 0.95


def test_ols_leak_insufficient_samples_does_not_trigger() -> None:
    """Verify that N < 30 samples will not trigger actionable leak flag."""
    daemon = MemoryGuardDaemon(interval_sec=0.1, window_capacity=50)
    base_time = 1000.0

    for i in range(15):  # only 15 samples < 30
        sample = MemoryTelemetrySample(
            timestamp_sec=base_time + i * 1.0,
            rss_bytes=100_000_000 + i * 500_000,
            vram_bytes=0,
            tracemalloc_bytes=20_000_000,
        )
        daemon.record_sample(sample)

    is_leak, slope_mb_min, r2 = daemon.evaluate_leak()
    assert not is_leak
