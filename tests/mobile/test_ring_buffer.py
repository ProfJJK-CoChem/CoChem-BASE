"""
Physical unit tests for Bounded Ring-Buffer Telemetry & OOM Mitigation.

Invariants:
- Zero-Mock Protocol: Real memory and thread-safe assertions.
- FIFO capacity bounding (<= 64 KB and <= 500 records).
- Monotonic sequence gaps and resync_required flag on eviction.
- DOM viewport snapshot rendering and SSE event formatting.
"""

from __future__ import annotations

import json
import threading

import pytest
from mendeleev import element

from cochem.telemetry.buffer import (
    MAX_BUFFER_BYTES,
    MAX_BUFFER_RECORDS,
    BoundedRingBuffer,
)
from cochem.telemetry.exceptions import RingBufferOverflowError
from cochem.telemetry.schemas import TelemetryLogLevel, TelemetryRecord


class TestBoundedRingBuffer:
    """Test suite for BoundedRingBuffer, eviction accounting, and delta streaming."""

    def test_dynamic_mendeleev_invariants(self) -> None:
        """Verify dynamic Mendeleev invariants are operational without hardcoding."""
        hydrogen = element("H")
        assert hydrogen.atomic_number == 1
        assert float(hydrogen.atomic_weight) > 1.0

        helium = element("He")
        assert helium.atomic_number == 2
        assert float(helium.atomic_weight) > 4.0

    def test_default_initialization_and_properties(self) -> None:
        """Verify buffer initializes with correct defaults and zero counts."""
        buf = BoundedRingBuffer()
        assert buf.max_bytes == MAX_BUFFER_BYTES
        assert buf.max_records == MAX_BUFFER_RECORDS
        assert len(buf) == 0
        assert buf.current_bytes == 0
        assert buf.total_bytes_evicted == 0
        assert buf.total_records_evicted == 0
        assert buf.start_seq == 0
        assert buf.next_seq == 0

    def test_record_count_fifo_eviction(self) -> None:
        """Verify FIFO eviction occurs when record count exceeds max_records."""
        buf = BoundedRingBuffer(max_records=5, max_bytes=100000)

        # Append 10 records
        for i in range(10):
            buf.append_record(
                level=TelemetryLogLevel.INFO,
                message=f"Log message {i}",
                module="test_module",
            )

        assert len(buf) == 5
        assert buf.total_records_evicted == 5
        assert buf.total_bytes_evicted > 0
        assert buf.start_seq == 5
        assert buf.next_seq == 10

        # Verify only records 5 to 9 remain
        records, next_seq, resync = buf.get_delta(cursor_seq=buf.start_seq)
        assert len(records) == 5
        assert [r.seq for r in records] == [5, 6, 7, 8, 9]
        assert next_seq == 10
        assert resync is False

    def test_byte_capacity_fifo_eviction(self) -> None:
        """Verify FIFO eviction occurs when total byte size exceeds max_bytes."""
        # Create a small byte limit buffer (e.g. 500 bytes)
        buf = BoundedRingBuffer(max_records=100, max_bytes=500)

        records_added = 0
        for i in range(10):
            rec = buf.append_record(
                level=TelemetryLogLevel.INFO,
                message=f"A moderately sized message with index {i:04d} payload string",
                module="worker",
            )
            assert rec.seq == i
            records_added += 1

        assert buf.current_bytes <= 500
        assert buf.total_bytes_evicted > 0
        assert buf.total_records_evicted > 0
        assert buf.start_seq > 0
        assert len(buf) < 10

    def test_oversized_single_record_raises_overflow(self) -> None:
        """Verify appending a single record exceeding max_bytes raises RingBufferOverflowError."""
        buf = BoundedRingBuffer(max_bytes=200, max_records=10)

        huge_record = TelemetryRecord(
            seq=0,
            timestamp="2026-09-01T00:00:00Z",
            level=TelemetryLogLevel.ERROR,
            module="test",
            message="X" * 300,
            metadata={"huge_key": "Y" * 300},
        )

        with pytest.raises(RingBufferOverflowError) as exc_info:
            buf.append(huge_record)

        assert "exceeds total ring buffer capacity" in str(exc_info.value)

    def test_get_delta_cursor_scenarios(self) -> None:
        """Verify all delta polling branches: up-to-date, incremental, and eviction gap."""
        buf = BoundedRingBuffer(max_records=5, max_bytes=100000)

        # 1. Empty buffer
        records, next_seq, resync = buf.get_delta(cursor_seq=0)
        assert records == []
        assert next_seq == 0
        assert resync is False

        # Add 3 records (seq 0, 1, 2)
        for i in range(3):
            buf.append_record(TelemetryLogLevel.INFO, f"Msg {i}")

        # 2. Client is up to date (cursor_seq == next_seq == 3)
        records, next_seq, resync = buf.get_delta(cursor_seq=3)
        assert records == []
        assert next_seq == 3
        assert resync is False

        # 3. Client cursor is ahead of next_seq (cursor_seq == 5)
        records, next_seq, resync = buf.get_delta(cursor_seq=5)
        assert records == []
        assert next_seq == 3
        assert resync is False

        # 4. Incremental fetch from seq 1
        records, next_seq, resync = buf.get_delta(cursor_seq=1)
        assert len(records) == 2
        assert [r.seq for r in records] == [1, 2]
        assert next_seq == 3
        assert resync is False

        # Now add 5 more records (seq 3, 4, 5, 6, 7) -> total 8 added, max 5 retained (seq 3, 4, 5, 6, 7)
        for i in range(3, 8):
            buf.append_record(TelemetryLogLevel.INFO, f"Msg {i}")

        assert buf.start_seq == 3
        assert buf.next_seq == 8

        # 5. Eviction gap: client asks for cursor_seq = 1 (which was evicted)
        records, next_seq, resync = buf.get_delta(cursor_seq=1)
        assert resync is True
        assert len(records) == 5
        assert [r.seq for r in records] == [3, 4, 5, 6, 7]
        assert next_seq == 8

    def test_viewport_snapshot_rendering(self) -> None:
        """Verify get_viewport_snapshot returns latest records for DOM viewport rendering."""
        buf = BoundedRingBuffer(max_records=20, max_bytes=100000)
        for i in range(15):
            buf.append_record(TelemetryLogLevel.INFO, f"Message {i}")

        snapshot_5 = buf.get_viewport_snapshot(max_lines=5)
        assert len(snapshot_5) == 5
        assert [r.seq for r in snapshot_5] == [10, 11, 12, 13, 14]

        snapshot_all = buf.get_viewport_snapshot(max_lines=50)
        assert len(snapshot_all) == 15

    def test_sse_event_formatting(self) -> None:
        """Verify format_sse_event produces valid SSE formatted data chunk."""
        buf = BoundedRingBuffer()
        rec = buf.append_record(TelemetryLogLevel.INFO, "SSE test record")

        sse_output = buf.format_sse_event(records=[rec], next_seq=1, resync_required=False)
        assert sse_output.startswith("event: telemetry\ndata: ")
        assert sse_output.endswith("\n\n")

        # Parse JSON data
        json_str = sse_output.replace("event: telemetry\ndata: ", "").strip()
        data = json.loads(json_str)
        assert data["next_seq"] == 1
        assert data["resync_required"] is False
        assert len(data["records"]) == 1
        assert data["records"][0]["message"] == "SSE test record"

    def test_clear_buffer(self) -> None:
        """Verify clear resets buffer records and current_bytes while preserving sequence indexing."""
        buf = BoundedRingBuffer()
        for i in range(5):
            buf.append_record(TelemetryLogLevel.INFO, f"Msg {i}")

        assert len(buf) == 5
        buf.clear()

        assert len(buf) == 0
        assert buf.current_bytes == 0
        assert buf.start_seq == 5
        assert buf.next_seq == 5

    def test_thread_safe_concurrent_access(self) -> None:
        """Verify concurrent multi-threaded appends and delta queries run without race conditions."""
        buf = BoundedRingBuffer(max_records=100, max_bytes=65536)
        num_threads = 6
        appends_per_thread = 30
        total_appended = num_threads * appends_per_thread
        appended_records: List[TelemetryRecord] = []
        rec_lock = threading.Lock()

        def _worker_append(tid: int) -> None:
            for i in range(appends_per_thread):
                rec = buf.append_record(
                    level=TelemetryLogLevel.INFO,
                    message=f"Thread {tid} append {i}",
                    module=f"worker_{tid}",
                )
                with rec_lock:
                    appended_records.append(rec)

        def _worker_read() -> int:
            total_read = 0
            for _ in range(50):
                records, _, _ = buf.get_delta(cursor_seq=0)
                total_read += len(records)
            return total_read

        append_threads = [
            threading.Thread(target=_worker_append, args=(tid,)) for tid in range(num_threads)
        ]
        read_threads = [threading.Thread(target=_worker_read) for _ in range(2)]

        for t in append_threads + read_threads:
            t.start()

        for t in append_threads + read_threads:
            t.join()

        assert len(buf) == 100
        assert buf.next_seq == total_appended
        assert len(appended_records) == total_appended
        all_seqs = [r.seq for r in appended_records]
        assert len(set(all_seqs)) == total_appended
        assert sorted(all_seqs) == list(range(total_appended))
