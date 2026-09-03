"""Physical Unit Verification Suite for Real-Time Mobile System Health Monitor.

Module: tests.mobile.test_system_health
Authoritative Reference: SRS Chunk 02 BASE UI & Web (Part 2), Prompt 4.

Invariants:
- Zero-Mock Protocol: Real psutil hardware metrics, authentic GPU polling.
- Non-blocking async telemetry emission.
- Thermal and memory saturation threshold testing with genuine Pydantic validation.
"""

from __future__ import annotations

import asyncio
import os

from src.cochem.mobile.system_health import (
    AlertSeverity,
    CPUMetrics,
    GPUMetrics,
    HardwareTelemetryFrame,
    MemoryMetrics,
    SystemHealthMonitor,
)


class TestSystemHealthMonitor:
    """Test suite validating workstation and mobile system health monitoring."""

    def test_poll_cpu_metrics(self) -> None:
        """Verify CPU metric polling captures positive core counts and utilization."""
        monitor = SystemHealthMonitor()
        cpu = monitor.poll_cpu_metrics()

        assert isinstance(cpu, CPUMetrics)
        assert cpu.physical_cores >= 1
        assert cpu.logical_cores >= 1
        assert cpu.logical_cores >= cpu.physical_cores
        assert len(cpu.per_core_percent) == cpu.logical_cores
        assert 0.0 <= cpu.overall_percent <= 100.0

    def test_poll_memory_metrics(self) -> None:
        """Verify physical RAM and swap space metrics."""
        monitor = SystemHealthMonitor()
        mem = monitor.poll_memory_metrics()

        assert isinstance(mem, MemoryMetrics)
        assert mem.ram_total_bytes > 0
        assert mem.ram_used_bytes > 0
        assert 0.0 <= mem.ram_percent <= 100.0
        assert mem.ram_total_bytes >= mem.ram_used_bytes

    def test_poll_process_metrics(self) -> None:
        """Verify process resource footprint tracking."""
        monitor = SystemHealthMonitor()
        proc = monitor.poll_process_metrics()

        assert proc.pid == os.getpid()
        assert proc.rss_bytes > 0
        assert proc.rss_mb > 0.0
        assert proc.open_handles_or_fds >= 0

    def test_poll_gpu_metrics_structure(self) -> None:
        """Verify GPU polling returns valid boolean and list of GPUMetrics."""
        monitor = SystemHealthMonitor()
        is_avail, gpus = monitor.poll_gpu_metrics()

        assert isinstance(is_avail, bool)
        assert isinstance(gpus, list)
        for g in gpus:
            assert isinstance(g, GPUMetrics)
            assert g.device_index >= 0
            assert g.vram_total_bytes >= 0
            assert 0.0 <= g.vram_percent <= 100.0

    def test_evaluate_alerts_thermal_and_vram_thresholds(self) -> None:
        """Verify alert generation at warning (80°C / 90%) and critical (85°C / 95%) thresholds."""
        monitor = SystemHealthMonitor()

        cpu_stress_metrics = CPUMetrics(
            physical_cores=8,
            logical_cores=16,
            overall_percent=96.5,  # Exceeds 95% CPU warning
            per_core_percent=[96.5] * 16,
        )
        mem_stress_metrics = MemoryMetrics(
            ram_total_bytes=32 * 1024**3,
            ram_used_bytes=30 * 1024**3,
            ram_free_bytes=2 * 1024**3,
            ram_percent=93.75,  # Exceeds 90% RAM warning
            swap_total_bytes=8 * 1024**3,
            swap_used_bytes=1 * 1024**3,
            swap_free_bytes=7 * 1024**3,
            swap_percent=12.5,
        )
        gpu_hot = GPUMetrics(
            device_index=0,
            device_name="Test-GPU",
            temperature_celsius=86.5,  # Critical (>= 85.0°C)
            vram_total_bytes=16 * 1024**3,
            vram_used_bytes=15 * 1024**3,
            vram_free_bytes=1 * 1024**3,
            vram_percent=93.75,  # Warning (>= 90.0%)
            utilization_percent=98.0,
        )

        alerts = monitor.evaluate_alerts(cpu_stress_metrics, mem_stress_metrics, [gpu_hot])
        assert len(alerts) >= 3

        # Verify critical GPU temperature alert
        crit_temp = [a for a in alerts if "GPU_0_TEMPERATURE" in a.component and a.severity == AlertSeverity.CRITICAL]
        assert len(crit_temp) == 1
        assert crit_temp[0].metric_value == 86.5

        # Verify warning VRAM alert
        warn_vram = [a for a in alerts if "GPU_0_VRAM" in a.component and a.severity == AlertSeverity.WARNING]
        assert len(warn_vram) == 1

        # Verify RAM and CPU alerts
        assert any(a.component == "HOST_RAM" for a in alerts)
        assert any(a.component == "HOST_CPU" for a in alerts)

    def test_poll_telemetry_frame_integrity(self) -> None:
        """Verify synchronous poll_telemetry creates valid, serializable HardwareTelemetryFrame."""
        monitor = SystemHealthMonitor()
        frame = monitor.poll_telemetry()

        assert isinstance(frame, HardwareTelemetryFrame)
        assert len(frame.frame_id) == 36  # UUIDv4 length
        assert frame.status in ("HEALTHY", "WARNING", "CRITICAL")
        # Assert valid JSON serialization
        json_data = frame.model_dump_json()
        assert len(json_data) > 100

    def test_stream_telemetry_async(self) -> None:
        """Verify async telemetry stream yields specified frames non-blockingly."""
        async def _collect() -> list[HardwareTelemetryFrame]:
            monitor = SystemHealthMonitor()
            collected: list[HardwareTelemetryFrame] = []
            async for frame in monitor.stream_telemetry(interval_seconds=0.01, max_frames=3):
                collected.append(frame)
            return collected

        frames = asyncio.run(_collect())
        assert len(frames) == 3
        assert all(isinstance(f, HardwareTelemetryFrame) for f in frames)
        # Frame IDs should be distinct
        assert len(set(f.frame_id for f in frames)) == 3
