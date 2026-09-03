"""Unit tests for high-throughput MMAP telemetry ring buffer.

Verifies 64-byte header alignment, 20-byte slot layout, circular overwrite-oldest
semantics, crash recovery for uncommitted slots, and multi-process concurrency.
"""

import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

from src.cochem.telemetry.mmap_ring_buffer import (
    HEADER_FORMAT,
    HEADER_SIZE,
    SLOT_CORRUPT,
    SLOT_HEADER_FORMAT,
    SLOT_HEADER_SIZE,
    SLOT_WRITING,
    MmapRingBuffer,
)


def test_binary_header_and_slot_layout() -> None:
    """Validate 64-byte L1/L2 aligned binary header and 20-byte slot header specifications."""
    assert struct.calcsize(HEADER_FORMAT) == 64
    assert struct.calcsize(SLOT_HEADER_FORMAT) == 20
    assert HEADER_SIZE == 64
    assert SLOT_HEADER_SIZE == 20


def test_mmap_ring_buffer_write_and_read(tmp_path: Path) -> None:
    """Verify standard write and sequential read operations."""
    buffer_file = tmp_path / "telemetry_stream.bin"
    with MmapRingBuffer(buffer_file, capacity=16, slot_size=128) as ring:
        seq0 = ring.write_record("event_zero")
        seq1 = ring.write_record(json.dumps({"metric": "energy", "val": -40.5}))
        seq2 = ring.write_record(b"\x01\x02\x03\x04")

        assert seq0 == 0
        assert seq1 == 1
        assert seq2 == 2

        # Read with cursor_seq=None to advance tail_seq
        records = ring.read_records(cursor_seq=None, max_records=10)
        assert len(records) == 3
        assert records[0][0] == 0
        assert records[0][3] == b"event_zero"
        assert records[1][0] == 1
        assert json.loads(records[1][3].decode("utf-8")) == {"metric": "energy", "val": -40.5}
        assert records[2][0] == 2
        assert records[2][3] == b"\x01\x02\x03\x04"

        stats = ring.get_header_stats()
        assert stats["head_seq"] == 3
        assert stats["tail_seq"] == 3
        assert stats["dropped_records"] == 0


def test_mmap_ring_buffer_overflow_overwrites_oldest(tmp_path: Path) -> None:
    """Verify circular ring buffer overwrite-oldest semantics when capacity is exceeded."""
    buffer_file = tmp_path / "overflow_stream.bin"
    capacity = 4
    with MmapRingBuffer(buffer_file, capacity=capacity, slot_size=128) as ring:
        for i in range(10):
            ring.write_record(f"record_{i}")

        stats = ring.get_header_stats()
        assert stats["head_seq"] == 10
        assert stats["dropped_records"] == 6

        # Reading from current tail_seq should yield the surviving un-overwritten slots
        records = ring.read_records(cursor_seq=None, max_records=10)
        assert len(records) == 4
        payloads = [r[3].decode("utf-8") for r in records]
        assert payloads == ["record_6", "record_7", "record_8", "record_9"]


def test_mmap_ring_buffer_crash_recovery_corrupt_slot(tmp_path: Path) -> None:
    """Verify consumer detects expired uncommitted WRITING slots, flags them CORRUPT, and continues."""
    buffer_file = tmp_path / "crash_stream.bin"
    with MmapRingBuffer(buffer_file, capacity=8, slot_size=128) as ring:
        ring.write_record("initial_ok")

        # Manually claim slot 1 in WRITING state with expired timestamp
        slot_offset = HEADER_SIZE + (1 * 128)
        expired_ts = time.time_ns() - int(5.0 * 1e9)  # 5 seconds in the past (> 2.0s timeout)
        ring.mm[slot_offset : slot_offset + SLOT_HEADER_SIZE] = struct.pack(
            SLOT_HEADER_FORMAT,
            SLOT_WRITING,
            expired_ts,
            os.getpid(),
            len(b"stale"),
        )
        ring.mm[slot_offset + SLOT_HEADER_SIZE : slot_offset + SLOT_HEADER_SIZE + len(b"stale")] = b"stale"

        # Advance head_seq to 3 and write record at slot 2
        ring.mm[16:24] = struct.pack("<Q", 3)
        ring.mm.flush()

        slot2_offset = HEADER_SIZE + (2 * 128)
        ring.mm[slot2_offset : slot2_offset + SLOT_HEADER_SIZE] = struct.pack(
            SLOT_HEADER_FORMAT,
            0x02,  # COMMITTED
            time.time_ns(),
            os.getpid(),
            len(b"after_crash"),
        )
        ring.mm[slot2_offset + SLOT_HEADER_SIZE : slot2_offset + SLOT_HEADER_SIZE + len(b"after_crash")] = b"after_crash"
        ring.mm.flush()

        # Read records: slot 1 should be flagged CORRUPT and skipped without deadlocking
        records = ring.read_records(cursor_seq=0, max_records=10)
        assert len(records) == 2
        assert records[0][3] == b"initial_ok"
        assert records[1][3] == b"after_crash"

        # Verify slot 1 was marked CORRUPT on disk
        status_flag = struct.unpack("<I", ring.mm[slot_offset : slot_offset + 4])[0]
        assert status_flag == SLOT_CORRUPT


def test_concurrent_multiprocess_write(tmp_path: Path) -> None:
    """Verify concurrent writers across independent OS processes coordinate atomically."""
    buffer_file = tmp_path / "concurrent_stream.bin"
    with MmapRingBuffer(buffer_file, capacity=64, slot_size=128) as ring:
        assert ring.capacity == 64

    repo_dir = str(Path(__file__).resolve().parent.parent.parent)
    src_dir = str(Path(__file__).resolve().parent.parent.parent / "src")
    worker_code = (
        "import sys\n"
        f"sys.path.insert(0, r'{repo_dir}')\n"
        f"sys.path.insert(0, r'{src_dir}')\n"
        "from src.cochem.telemetry.mmap_ring_buffer import MmapRingBuffer\n"
        "buf_path = sys.argv[1]\n"
        "worker_id = sys.argv[2]\n"
        "with MmapRingBuffer(buf_path, capacity=64, slot_size=128) as ring:\n"
        "    for i in range(10):\n"
        "        ring.write_record(f'{worker_id}_event_{i}')\n"
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{repo_dir}{os.pathsep}{env.get('PYTHONPATH', '')}"

    proc1 = subprocess.run(
        [sys.executable, "-c", worker_code, str(buffer_file), "W1"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    proc2 = subprocess.run(
        [sys.executable, "-c", worker_code, str(buffer_file), "W2"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )

    assert proc1.returncode == 0
    assert proc2.returncode == 0

    with MmapRingBuffer(buffer_file, capacity=64, slot_size=128) as ring:
        stats = ring.get_header_stats()
        assert stats["head_seq"] == 20
        records = ring.read_records(cursor_seq=0, max_records=50)
        assert len(records) == 20
        w1_events = [r[3].decode("utf-8") for r in records if "W1" in r[3].decode("utf-8")]
        w2_events = [r[3].decode("utf-8") for r in records if "W2" in r[3].decode("utf-8")]
        assert len(w1_events) == 10
        assert len(w2_events) == 10
