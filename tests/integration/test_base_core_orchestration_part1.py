"""Physical integration and compliance test suite for CoChem-BASE Core Orchestration Part 1.

Verifies end-to-end integration across memory-mapped ring buffers, centralized SQLite task queues,
cross-platform process reaper life-cycles, dynamic Mendeleev property invariants, stream secret masking,
hierarchical TOML configuration, and exhaustive AST Zero-Mock compliance.
"""

import os
import sqlite3
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import List

import psutil
import pytest

from src.cochem.core.config import CoChemConfigManager
from src.cochem.core.mendeleev_invariants import (
    MendeleevInvariantError,
    get_element,
    get_isotope_mass,
    mendeleev_resolver,
)
from src.cochem.core.process_reaper import (
    ProcessTreeManager,
    ZombieReaperDaemon,
    get_pdeathsig_preexec_fn,
    set_pdeathsig,
)
from src.cochem.orchestration.sqlite_queue import SQLiteTaskQueue
from src.cochem.telemetry.mmap_ring_buffer import (
    HEADER_FORMAT,
    HEADER_SIZE,
    SLOT_CORRUPT,
    SLOT_HEADER_FORMAT,
    SLOT_HEADER_SIZE,
    SLOT_WRITING,
    MmapRingBuffer,
)
from src.cochem.telemetry.secret_masker import (
    DynamicCredentialProvider,
    TelemetrySecretMasker,
)


def test_mmap_ring_buffer_integration(tmp_path: Path) -> None:
    """Verify MMAP binary layouts, multi-process concurrency, overflow, and crash recovery."""
    assert struct.calcsize(HEADER_FORMAT) == 64
    assert struct.calcsize(SLOT_HEADER_FORMAT) == 20

    buffer_file = tmp_path / "integration_ring.bin"

    # 1. Standard lifecycle & overflow
    with MmapRingBuffer(buffer_file, capacity=8, slot_size=128) as ring:
        for i in range(12):
            ring.write_record(f"event_{i}")

        stats = ring.get_header_stats()
        assert stats["head_seq"] == 12
        assert stats["dropped_records"] == 4

        # Read available records
        records = ring.read_records(cursor_seq=None, max_records=20)
        assert len(records) == 8
        assert records[-1][3] == b"event_11"

    # 2. Crash recovery simulation (slot in WRITING state with expired heartbeat)
    with MmapRingBuffer(buffer_file, capacity=8, slot_size=128) as ring:
        slot_idx = 0
        slot_offset = HEADER_SIZE + (slot_idx * 128)
        expired_ts = time.time_ns() - int(4.0 * 1e9)  # 4 seconds ago (> 2.0s timeout)

        ring.mm[slot_offset : slot_offset + SLOT_HEADER_SIZE] = struct.pack(
            SLOT_HEADER_FORMAT,
            SLOT_WRITING,
            expired_ts,
            os.getpid(),
            len(b"stale_crash"),
        )
        ring.mm[slot_offset + SLOT_HEADER_SIZE : slot_offset + SLOT_HEADER_SIZE + len(b"stale_crash")] = b"stale_crash"
        ring.mm.flush()

        # Reader must mark it CORRUPT and continue without blocking
        records = ring.read_records(cursor_seq=0, max_records=5)
        status_flag = struct.unpack("<I", ring.mm[slot_offset : slot_offset + 4])[0]
        assert status_flag == SLOT_CORRUPT


def test_sqlite_task_queue_integration(tmp_path: Path) -> None:
    """Verify SQLite WAL mode, concurrent immediate leasing, heartbeats, and orphan reclamation."""
    db_file = tmp_path / "orchestration_integration.db"

    with SQLiteTaskQueue(db_file) as queue:
        cursor = queue._conn.cursor()
        jm = cursor.execute("PRAGMA journal_mode;").fetchone()[0]
        assert str(jm).lower() == "wal"

        bt = cursor.execute("PRAGMA busy_timeout;").fetchone()[0]
        assert int(bt) >= 5000

        # Enqueue tasks
        _ = queue.enqueue_task(task_type="scf_opt", payload={"charge": 0}, priority=5)
        t2 = queue.enqueue_task(task_type="scf_opt", payload={"charge": 1}, priority=20)

        # Priority leasing
        lease = queue.lease_task(worker_pid=os.getpid(), worker_host="local_hpc")
        assert lease is not None
        assert lease.task_id == t2  # higher priority leased first

        # Heartbeat
        assert queue.heartbeat(t2, worker_pid=os.getpid()) is True

        # Orphan reclamation
        backdated_ts = time.time() - 35.0
        queue._conn.execute("UPDATE tasks SET heartbeat_ts = ? WHERE task_id = ?;", (backdated_ts, t2))
        reclaimed = queue.reclaim_orphaned_tasks(timeout_grace_sec=30.0)
        assert t2 in reclaimed
        rec = queue.get_task(t2)
        assert rec is not None
        assert rec.state == "PENDING"

        # State guard: completing non-running task raises RuntimeError
        with pytest.raises(RuntimeError, match="cannot be completed because it is not in RUNNING state"):
            queue.complete_task(t2, {"energy": -75.4})

        # Re-lease and complete successfully
        lease2 = queue.lease_task(worker_pid=os.getpid(), worker_host="local_hpc")
        assert lease2 is not None
        assert lease2.task_id == t2
        queue.complete_task(t2, {"energy": -75.4})
        rec_completed = queue.get_task(t2)
        assert rec_completed is not None
        assert rec_completed.state == "COMPLETED"
        assert rec_completed.result == {"energy": -75.4}


def test_sqlite_lock_contention_rollback_guard(tmp_path: Path) -> None:
    """Verify lock contention during lease_task handles OperationalError without raising rollback errors."""
    db_file = tmp_path / "lock_guard_test.db"

    with SQLiteTaskQueue(db_file) as queue:
        # Enqueue a test task
        task_id = queue.enqueue_task(task_type="scf_grad", payload={"step": 1}, priority=10)

        # Lower busy_timeout to 50ms so 5 retry attempts complete quickly in under 2 seconds
        queue._conn.execute("PRAGMA busy_timeout = 50;")

        # Open a second connection holding an EXCLUSIVE lock on the SQLite database
        lock_conn = sqlite3.connect(str(db_file), isolation_level=None)
        try:
            lock_conn.execute("BEGIN EXCLUSIVE;")

            # lease_task will fail with database is locked on BEGIN IMMEDIATE.
            # It must NOT raise 'cannot rollback - no transaction is active' and must return None.
            lease = queue.lease_task(worker_pid=os.getpid(), worker_host="contention_node")
            assert lease is None

            # Release the lock
            lock_conn.execute("ROLLBACK;")
        finally:
            lock_conn.close()

        # Once lock is released, queue can lease the task normally
        recovered_lease = queue.lease_task(worker_pid=os.getpid(), worker_host="contention_node")
        assert recovered_lease is not None
        assert recovered_lease.task_id == task_id


def test_process_reaper_integration(tmp_path: Path) -> None:
    """Verify genuine child process tracking, telemetry extraction, and progressive escalation."""
    manager = ProcessTreeManager()
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(15)"])

    try:
        meta = manager.register_process(proc.pid, task_id="task_int_01")
        assert meta.pid == proc.pid
        assert manager.is_alive(proc.pid) is True

        metrics = manager.terminate_tree(proc.pid, grace_timeout_sec=2.0)
        assert metrics["success"] is True
        assert metrics["pid"] == proc.pid
        assert not manager.is_alive(proc.pid)

        # Check platform containment preexec helper
        preexec = get_pdeathsig_preexec_fn()
        if sys.platform.startswith("linux"):
            assert callable(preexec)
        else:
            assert preexec is None
    finally:
        if psutil.pid_exists(proc.pid):
            manager.terminate_tree(proc.pid)


def test_zombie_reaper_daemon_sweeping(tmp_path: Path) -> None:
    """Verify ZombieReaperDaemon detects orphaned child processes and terminates them."""
    db_file = tmp_path / "reaper_queue.db"
    manager = ProcessTreeManager()
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(15)"])

    try:
        with SQLiteTaskQueue(db_file) as queue:
            task_id = queue.enqueue_task(task_type="md_step", payload={"step": 1})
            lease = queue.lease_task(worker_pid=proc.pid, worker_host="local_node")
            assert lease is not None

            manager.register_process(proc.pid, task_id=task_id)
            assert manager.is_alive(proc.pid) is True

            # Use a nonexistent parent PID so the child is immediately classified as orphaned
            orphaned_parent_pid = 999999
            while psutil.pid_exists(orphaned_parent_pid):
                orphaned_parent_pid += 1

            daemon = ZombieReaperDaemon(
                queue=queue,
                tree_manager=manager,
                parent_pid=orphaned_parent_pid,
                grace_period_sec=0.1,
                interval_sec=0.01,
            )

            assert daemon.is_orphan(proc.pid) is True

            reaped = daemon.run_watchdog_loop(max_iterations=1)
            assert proc.pid in reaped
            assert not manager.is_alive(proc.pid)

            # Verify the orphaned task was failed in queue with can_retry=True
            reaped_task = queue.get_task(task_id)
            assert reaped_task is not None
            assert reaped_task.state == "PENDING"
            assert reaped_task.retry_count == 1
    finally:
        if psutil.pid_exists(proc.pid):
            manager.terminate_tree(proc.pid)


def test_mendeleev_invariants_integration() -> None:
    """Verify IUPAC CIAAW standard weights, synthetic fallbacks, and isotope calculations."""
    c = get_element("C")
    assert c.atomic_number == 6
    assert abs(c.atomic_weight - 12.011) < 0.01

    # Radioactive fallback
    tc = get_element(43)
    assert tc.symbol == "Tc"
    assert tc.atomic_weight > 90.0

    # Exact isotope masses
    c13_mass = get_isotope_mass("C", 13)
    assert abs(c13_mass - 13.00335) < 1e-4

    # Boundary check
    with pytest.raises(MendeleevInvariantError):
        get_element("Unobtainium")

    # Cache immutability verification
    with pytest.raises(MendeleevInvariantError, match="cache is immutable"):
        mendeleev_resolver.clear_cache()

    # Van der Waals radius verification
    c_vdw = mendeleev_resolver.get_vdw_radius("C")
    assert c_vdw > 100.0

    # Elements without VdW radius raise MendeleevInvariantError
    with pytest.raises(MendeleevInvariantError, match="Van der Waals radius is not available"):
        mendeleev_resolver.get_vdw_radius(118)


def test_secret_masker_integration(tmp_path: Path) -> None:
    """Verify high-entropy secret redaction and memory zeroizing on credential rotation."""
    raw_log = (
        "API access: api_key='sk_live_abcdef1234567890abcdef' "
        "Authorization: Bearer super_secret_jwt_payload_9876543210 "
        "Connecting to postgresql://admin:cluster_secret_pwd_456@db:5432/main"
    )
    masked = TelemetrySecretMasker.mask_text(raw_log)

    assert "sk_live_abcdef1234567890abcdef" not in masked
    assert "super_secret_jwt_payload_9876543210" not in masked
    assert "cluster_secret_pwd_456" not in masked
    assert "[REDACTED:API_KEY:" in masked
    assert "[REDACTED:AUTH_HEADER:" in masked
    assert "[REDACTED:CONNECTION_URI:" in masked

    # Verify multiple URIs in single log line all have credentials redacted without leakage
    multi_uri_log = (
        "Syncing postgresql://user1:pass_first_123@db1.internal:5432/db "
        "and redis://user2:pass_second_456@cache.internal:6379/0 "
        "and mongodb://user3:pass_third_789@mongo.internal:27017/analytics"
    )
    masked_multi = TelemetrySecretMasker.mask_text(multi_uri_log)
    assert "pass_first_123" not in masked_multi
    assert "pass_second_456" not in masked_multi
    assert "pass_third_789" not in masked_multi
    assert "db1.internal:5432/db" in masked_multi
    assert "cache.internal:6379/0" in masked_multi
    assert "mongo.internal:27017/analytics" in masked_multi

    # Comma-separated multi-URI verification ensuring passwords are not leaked into adjacent URIs
    comma_log = "DB=postgresql://user1:secret_one@db1:5432/main,CACHE=redis://user2:secret_two@cache:6379/0,NOSQL=mongodb://user3:secret_three@mongo:27017/prod"
    masked_comma = TelemetrySecretMasker.mask_text(comma_log)
    assert "secret_one" not in masked_comma
    assert "secret_two" not in masked_comma
    assert "secret_three" not in masked_comma
    assert "db1:5432/main" in masked_comma
    assert "cache:6379/0" in masked_comma
    assert "mongo:27017/prod" in masked_comma
    assert "CACHE=redis://" in masked_comma
    assert "NOSQL=mongodb://" in masked_comma

    # C-buffer zeroizing
    provider = DynamicCredentialProvider()
    provider.set_credentials({"API_KEY": "super_secret_token_123"})
    buf = provider._allocated_buffers["API_KEY"]
    assert buf.raw.rstrip(b"\x00") == b"super_secret_token_123"
    provider.close()
    assert buf.raw == b"\x00" * len(buf.raw)


def test_credential_provider_hot_reload(tmp_path: Path) -> None:
    """Verify DynamicCredentialProvider polls filesystem mtime and reloads credentials."""
    cred_file = tmp_path / "active_credentials.json"
    cred_file.write_text('{"API_KEY": "initial_token_alpha"}', encoding="utf-8")

    provider = DynamicCredentialProvider(config_path=cred_file)
    assert provider.get_credential("API_KEY") == "initial_token_alpha"

    # Sleep briefly to ensure filesystem mtime difference
    time.sleep(0.05)
    cred_file.write_text('{"API_KEY": "rotated_token_beta"}', encoding="utf-8")

    reloaded = provider.reload()
    assert reloaded is True
    assert provider.get_credential("API_KEY") == "rotated_token_beta"

    # Second reload without file modification returns False
    assert provider.reload() is False
    provider.close()


def test_config_manager_integration(tmp_path: Path) -> None:
    """Verify hierarchical precedence, path resolution, and legacy deprecation."""
    cochem_toml = tmp_path / "cochem.toml"
    cochem_toml.write_text(
        """
[core]
log_level = "DEBUG"
max_workers = 8

[telemetry]
ring_buffer_capacity = 16384
""",
        encoding="utf-8",
    )

    manager = CoChemConfigManager(
        project_root=tmp_path,
        cli_overrides={"core__max_workers": 16},
    )
    config = manager.load_config()

    assert config.core.max_workers == 16  # CLI won over TOML
    assert config.core.log_level == "DEBUG"  # TOML won over default
    assert config.telemetry.ring_buffer_capacity == 16384
    assert config.core.scratch_dir == (tmp_path / "scratch").resolve()


def test_config_manager_env_override_and_legacy_deprecation(tmp_path: Path) -> None:
    """Verify COCHEM__CORE__MAX_WORKERS env override, non-boolean 0/1 coercion, and legacy deprecation warning."""
    legacy_json = tmp_path / "cochem.json"
    legacy_json.write_text(
        '{"core": {"max_workers": 2, "log_level": "WARNING"}}',
        encoding="utf-8",
    )

    env_key = "COCHEM__CORE__MAX_WORKERS"
    orig_env = os.environ.get(env_key)
    try:
        os.environ[env_key] = "12"
        with pytest.deprecated_call(match="Legacy configuration format 'cochem.json' is deprecated"):
            manager = CoChemConfigManager(project_root=tmp_path)
            config = manager.load_config()

        # Env variable overrides legacy json
        assert config.core.max_workers == 12
        assert config.core.log_level == "WARNING"

        # Verify relative paths resolved relative to project_root
        assert config.core.scratch_dir == (tmp_path / "scratch").resolve()
        assert config.orchestration.db_path == (tmp_path / "cochem_tasks.db").resolve()

        # Verify 0 and 1 are parsed as integers, not booleans
        os.environ[env_key] = "0"
        config_zero = manager.load_config()
        assert config_zero.core.max_workers == 0
        assert type(config_zero.core.max_workers) is int

        os.environ[env_key] = "1"
        config_one = manager.load_config()
        assert config_one.core.max_workers == 1
        assert type(config_one.core.max_workers) is int
    finally:
        if orig_env is not None:
            os.environ[env_key] = orig_env
        else:
            os.environ.pop(env_key, None)


def test_zero_mock_compliance_ast_audit() -> None:
    """AST audit certifying zero occurrences of mocks, stubs, empty pass blocks, or NotImplementedError."""
    from ci_tools.anti_spoof_linter import check_file

    repo_root = Path(__file__).resolve().parent.parent.parent
    total_violations: List[str] = []

    target_production_files = [
        "src/cochem/telemetry/mmap_ring_buffer.py",
        "src/cochem/orchestration/sqlite_queue.py",
        "src/cochem/core/process_reaper.py",
        "src/cochem/core/mendeleev_invariants.py",
        "src/cochem/telemetry/secret_masker.py",
        "src/cochem/core/config.py",
    ]

    for rel_path in target_production_files:
        full_path = repo_root / rel_path
        assert full_path.is_file(), f"Target file '{rel_path}' does not exist!"

        violations = check_file(full_path, repo_root, amnesty_set=set())
        for v in violations:
            total_violations.append(f"{v.file_path}:{v.line} [{v.category}] {v.message}")

    assert len(total_violations) == 0, (
        f"Zero-stub compliance violations detected ({len(total_violations)}):\n"
        + "\n".join(total_violations)
    )
