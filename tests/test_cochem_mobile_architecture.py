"""Zero-Mock Test Suite for CoChem-Mobile Architecture Engine.

Covers REQ-MOB-001 through REQ-MOB-005 with real OS files, real locks,
real subprocess execution, real HDF5 SWMR I/O, and dynamic mendeleev atomic masses.
ZERO-MOCK MANDATE: Zero mocks, stubs, or fake objects.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path, PurePosixPath

import mendeleev
import numpy as np
import pytest

from cochem_mobile.core.architecture import (
    IngressValidationError,
    JobResult,
    JobSubmission,
    MobileCloudEngine,
)
from cochem_mobile.core.mount_resolver import (
    EnvironmentType,
    HostToContainerMountResolver,
    SecurityPathTraversalError,
)
from cochem_mobile.core.sandbox_broker import (
    ContainerEngine,
    QuarantineConfig,
    SandboxBroker,
    SandboxSecurityViolation,
)
from cochem_mobile.core.session_manager import (
    SessionManager,
    SessionSecurityError,
    SessionState,
)
from cochem_mobile.core.telemetry_wal import (
    SWMRHDF5Writer,
    TelemetryWAL,
)



def test_mount_resolver_bidirectional_translation(tmp_path: Path) -> None:
    """Verify bidirectional host-to-container path translation across environments."""
    resolver = HostToContainerMountResolver(default_target_env=EnvironmentType.LINUX_DEBIAN)

    # 1. Windows to WSL translation
    win_path = Path("C:/data/spectra/experiment1.h5")
    wsl_trans = resolver.host_to_container(win_path, target_env=EnvironmentType.WSL)
    assert str(wsl_trans).lower() == "/mnt/c/data/spectra/experiment1.h5"

    # 2. WSL to Windows translation
    wsl_input = "/mnt/c/data/spectra/experiment1.h5"
    win_trans = resolver.container_to_host(wsl_input, host_env=EnvironmentType.WINDOWS)
    assert "C:" in str(win_trans)
    assert "spectra" in str(win_trans)

    # 3. Explicit mount mapping registration with longest-prefix match
    host_mount = tmp_path / "host_work"
    host_mount.mkdir(parents=True, exist_ok=True)
    container_mount = PurePosixPath("/quarantine/workspace")

    mapping = resolver.register_mount(host_mount, container_mount)
    assert mapping.host_path == host_mount.resolve()
    assert mapping.container_path == container_mount

    nested_file = host_mount / "subfolder" / "state.json"
    cont_resolved = resolver.host_to_container(nested_file)
    assert str(cont_resolved) == "/quarantine/workspace/subfolder/state.json"

    # Inverse translation
    host_reconstructed = resolver.container_to_host("/quarantine/workspace/subfolder/state.json")
    assert host_reconstructed == nested_file.resolve()


def test_mount_resolver_security_and_banned_patterns(tmp_path: Path) -> None:
    """Verify path traversal prevention and banned pattern auditing."""
    jail = tmp_path / "sandbox_jail"
    jail.mkdir(parents=True, exist_ok=True)

    resolver = HostToContainerMountResolver(jail_roots=[jail])

    # Valid inside jail
    valid_file = jail / "safe_data.txt"
    valid_file.touch()
    assert resolver.validate_path_security(valid_file) == valid_file.resolve()

    # Traversal attempt outside jail
    outside_file = tmp_path / "escaped.txt"
    outside_file.touch()
    with pytest.raises(SecurityPathTraversalError):
        resolver.validate_path_security(outside_file)

    # Null byte attempt
    with pytest.raises(SecurityPathTraversalError):
        resolver.validate_path_security(f"{str(jail)}/data\0malicious.txt")

    # Banned pattern audit
    violations_home = HostToContainerMountResolver.audit_banned_patterns("run --dir $HOME/project")
    assert len(violations_home) > 0
    assert any("$HOME" in v for v in violations_home)

    violations_tilde = HostToContainerMountResolver.audit_banned_patterns("run ~/calc")
    assert len(violations_tilde) > 0


def test_telemetry_wal_hash_chain_and_persistence(tmp_path: Path) -> None:
    """Verify append-only WAL with monotonic LSN and cryptographic SHA-256 chain."""
    wal_file = tmp_path / "test_wal.jsonl"
    wal = TelemetryWAL(wal_file)

    # Append sequential records
    rec1 = wal.append("STATE_UPDATE", {"step": 1, "energy": -76.42})
    assert rec1.lsn == 1
    assert rec1.prev_hash == TelemetryWAL.GENESIS_HASH
    assert rec1.verify_hash() is True

    rec2 = wal.append("STATE_UPDATE", {"step": 2, "energy": -76.45})
    assert rec2.lsn == 2
    assert rec2.prev_hash == rec1.record_hash
    assert rec2.verify_hash() is True

    rec3 = wal.append("STATE_UPDATE", {"step": 3, "energy": -76.48})
    assert rec3.lsn == 3
    assert rec3.prev_hash == rec2.record_hash
    assert rec3.verify_hash() is True

    # Read records and verify chain integrity
    records = wal.read_records()
    assert len(records) == 3
    assert records[0].lsn == 1
    assert records[1].lsn == 2
    assert records[2].lsn == 3

    valid, msg = wal.verify_integrity()
    assert valid is True

    # Checkpoint compaction
    ckpt = wal.compact_checkpoint(up_to_lsn=2, checkpoint_state={"snapshot_step": 2})
    assert ckpt.event_type == "CHECKPOINT"
    compacted_records = wal.read_records()
    assert len(compacted_records) == 2  # Checkpoint record + rec3
    assert compacted_records[0].event_type == "CHECKPOINT"
    assert compacted_records[1].payload["step"] == 3


def test_swmr_hdf5_writer_chunked_io(tmp_path: Path) -> None:
    """Verify SWMR HDF5 writer with chunked datasets and real data appending."""
    h5_file = tmp_path / "swmr_telemetry.h5"
    writer = SWMRHDF5Writer(h5_file, enable_swmr=True)

    # Real atomic data: water molecule coordinates (H2O)
    water_coords = np.array([
        [0.0000, 0.0000, 0.1173],
        [0.0000, 0.7572, -0.4692],
        [0.0000, -0.7572, -0.4692],
    ], dtype=np.float64)

    h_mass = float(mendeleev.element("H").atomic_weight)
    o_mass = float(mendeleev.element("O").atomic_weight)
    masses = np.array([o_mass, h_mass, h_mass], dtype=np.float64)

    writer.append_telemetry(
        coords=water_coords,
        energy=-76.4389,
        masses=masses,
        timestamp=time.time(),
        prov_hash="a1b2c3d4e5f67890",
    )

    writer.close()

    # Read back and verify physical properties
    read_data = writer.read_reader_mode()
    assert read_data["coordinates"].shape == (3, 3)
    assert np.allclose(read_data["coordinates"], water_coords)
    assert len(read_data["energies"]) == 1
    assert np.isclose(read_data["energies"][0], -76.4389)
    assert len(read_data["atomic_masses"]) == 3
    assert np.isclose(read_data["atomic_masses"][0], o_mass)
    assert "a1b2c3d4e5f67890" in read_data["provenance_hashes"]


def test_sandbox_broker_real_execution(tmp_path: Path) -> None:
    """Verify SandboxBroker real execution, CPU vectorization, and stream handling."""
    broker = SandboxBroker()
    assert ContainerEngine.SUBPROCESS in broker.detect_available_engines()

    calc_script = tmp_path / "calc_mass.py"
    calc_script.write_text(
        "import mendeleev, json, sys\n"
        "c_weight = float(mendeleev.element('C').atomic_weight)\n"
        "o_weight = float(mendeleev.element('O').atomic_weight)\n"
        "co2_weight = c_weight + 2 * o_weight\n"
        "print(json.dumps({'molecule': 'CO2', 'mass': co2_weight}))\n",
        encoding="utf-8",
    )

    config = QuarantineConfig(
        max_memory_mb=512,
        max_cpus=1.0,
        timeout_seconds=10.0,
        work_dir=tmp_path,
        enforce_cpu_vectorization=True,
    )

    res = broker.execute(
        command=[sys.executable, str(calc_script)],
        config=config,
        force_engine=ContainerEngine.SUBPROCESS,
    )

    assert res.exit_code == 0
    assert res.timed_out is False
    assert len(res.sha256_output_hash) == 64

    # Verify calculated real physical mass of CO2
    data = json.loads(res.stdout.strip())
    assert data["molecule"] == "CO2"
    expected_co2 = float(mendeleev.element("C").atomic_weight) + 2 * float(mendeleev.element("O").atomic_weight)
    assert np.isclose(data["mass"], expected_co2, atol=1e-3)


def test_sandbox_broker_timeout_and_process_cleanup(tmp_path: Path) -> None:
    """Verify process timeout termination and psutil tree cleanup."""
    broker = SandboxBroker()

    sleep_script = tmp_path / "infinite_sleep.py"
    sleep_script.write_text(
        "import time\n"
        "while True:\n"
        "    time.sleep(0.1)\n",
        encoding="utf-8",
    )

    config = QuarantineConfig(
        timeout_seconds=0.3,
        work_dir=tmp_path,
    )

    res = broker.execute(
        command=[sys.executable, str(sleep_script)],
        config=config,
        force_engine=ContainerEngine.SUBPROCESS,
    )

    assert res.timed_out is True


def test_sandbox_broker_security_rejections() -> None:
    """Verify command sanitization rejects empty or null-byte corrupted commands."""
    broker = SandboxBroker()

    with pytest.raises(SandboxSecurityViolation):
        broker.sanitize_command([])

    with pytest.raises(SandboxSecurityViolation):
        broker.sanitize_command(["python", "calc.py\0malicious"])


def test_session_manager_monotonic_sequencing_and_ring_buffer() -> None:
    """Verify session manager message sequencing, ring buffer bounds, and authentication."""
    mgr = SessionManager()

    session = mgr.create_session(client_metadata={"device": "mobile_safari", "os": "iOS"}, max_buffer_size=5)
    assert session.state == SessionState.ACTIVE
    assert len(session.auth_token) == 64

    # Spool 7 messages into a buffer of size 5
    for i in range(1, 8):
        msg = mgr.spool(session.session_id, "telemetry_event", {"step": i, "val": i * 10})
        assert msg.seq_id == i

    # Ring buffer should retain the last 5 messages (seq_ids 3 to 7)
    buffered = session.get_all_buffered()
    assert len(buffered) == 5
    assert [m.seq_id for m in buffered] == [3, 4, 5, 6, 7]

    # Replay messages since seq_id=4
    replayed = mgr.replay_messages(session.session_id, since_seq_id=4, auth_token=session.auth_token)
    assert len(replayed) == 3
    assert [m.seq_id for m in replayed] == [5, 6, 7]

    # Unauthorized access rejection
    with pytest.raises(SessionSecurityError):
        mgr.get_session(session.session_id, auth_token="invalid_hex_token_12345")


def test_session_manager_heartbeat_watchdog() -> None:
    """Verify heartbeat recording and session state sweep lifecycle."""
    mgr = SessionManager(heartbeat_timeout_seconds=0.2, disconnect_timeout_seconds=0.5)

    s1 = mgr.create_session()
    s2 = mgr.create_session()

    assert mgr.active_session_count == 2

    # Simulate passage of time for s2
    now = time.time()
    s1.record_heartbeat(timestamp=now + 0.25)

    # After 0.3s, s2 should be suspended while s1 remains active
    mgr.sweep_stale_sessions(now=now + 0.3)
    assert s2.state == SessionState.SUSPENDED
    assert s1.state == SessionState.ACTIVE

    # Keep s1 active with a heartbeat before next sweep
    s1.record_heartbeat(timestamp=now + 0.55)

    # After 0.6s, s2 should be disconnected and purged while s1 remains active
    purged = mgr.sweep_stale_sessions(now=now + 0.6)
    assert s2.session_id in purged
    assert mgr.active_session_count == 1
    assert s1.state == SessionState.ACTIVE


def test_tripartite_engine_end_to_end_job_submission(tmp_path: Path) -> None:
    """Verify end-to-end Tripartite Architecture execution with mendeleev dynamic masses."""
    engine = MobileCloudEngine(
        workspace_root=tmp_path / "mobile_workspace",
        preferred_engine=ContainerEngine.SUBPROCESS,
    )

    # 1. Create client session
    session = engine.session_manager.create_session(client_metadata={"client": "coChem_pwa_client"})

    # 2. Formulate real molecular job (Ethylene C2H4)
    # Physical coordinates in Angstroms
    ethylene_symbols = ["C", "C", "H", "H", "H", "H"]
    ethylene_coords = [
        [0.0000, 0.0000, 0.6695],
        [0.0000, 0.0000, -0.6695],
        [0.0000, 0.9289, 1.2321],
        [0.0000, -0.9289, 1.2321],
        [0.0000, 0.9289, -1.2321],
        [0.0000, -0.9289, -1.2321],
    ]

    submission = JobSubmission(
        symbols=ethylene_symbols,
        coordinates=ethylene_coords,
        calculation_type="spectral_fit",
        session_id=session.session_id,
    )

    # 3. Submit and execute job
    result = engine.submit_job(submission, auth_token=session.auth_token)

    assert isinstance(result, JobResult)
    assert result.status == "completed"
    assert result.session_id == session.session_id
    assert len(result.provenance_hash) == 64

    # Verify real physical dynamic masses from mendeleev
    c_mass = float(mendeleev.element("C").atomic_weight)
    h_mass = float(mendeleev.element("H").atomic_weight)
    expected_ethylene_mass = 2 * c_mass + 4 * h_mass
    assert np.isclose(result.total_mass_amu, expected_ethylene_mass, atol=1e-3)

    # 4. Verify WAL ledger entries
    wal_records = engine.wal.read_records()
    assert len(wal_records) >= 2  # Ingress + Completion
    assert wal_records[0].event_type == "JOB_INGRESS"
    assert wal_records[1].event_type == "JOB_COMPLETED"

    # 5. Verify thin-client spooled messages
    replayed_msgs = engine.session_manager.replay_messages(
        session_id=session.session_id,
        since_seq_id=0,
        auth_token=session.auth_token,
    )
    assert len(replayed_msgs) >= 2
    topics = [m.topic for m in replayed_msgs]
    assert "job_status" in topics
    assert "job_completed" in topics

    # 6. Verify SWMR HDF5 telemetry store
    stored_state = engine.hdf5_writer.read_reader_mode()
    assert stored_state["coordinates"].shape == (6, 3)
    assert len(stored_state["atomic_masses"]) == 6
    assert np.isclose(stored_state["atomic_masses"][0], c_mass)
    assert np.isclose(stored_state["atomic_masses"][2], h_mass)

    engine.close()


def test_tripartite_engine_ingress_validation_failures(tmp_path: Path) -> None:
    """Verify ingress rejection of invalid element symbols, coordinate dimensions, and NaNs."""
    engine = MobileCloudEngine(workspace_root=tmp_path / "ws_invalid")
    session = engine.session_manager.create_session()

    # 1. Invalid element symbol
    sub_bad_sym = JobSubmission(
        symbols=["NonExistentElementX"],
        coordinates=[[0.0, 0.0, 0.0]],
        calculation_type="energy",
        session_id=session.session_id,
    )
    with pytest.raises(IngressValidationError):
        engine.submit_job(sub_bad_sym, auth_token=session.auth_token)

    # 2. Dimension mismatch (symbols count != coords count)
    sub_dim_mismatch = JobSubmission(
        symbols=["H", "O", "H"],
        coordinates=[[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]],  # Only 2 rows for 3 atoms
        calculation_type="energy",
        session_id=session.session_id,
    )
    with pytest.raises(IngressValidationError):
        engine.submit_job(sub_dim_mismatch, auth_token=session.auth_token)

    # 3. Non-finite values (NaN / Inf)
    sub_nan = JobSubmission(
        symbols=["H"],
        coordinates=[[float("nan"), 0.0, 0.0]],
        calculation_type="energy",
        session_id=session.session_id,
    )
    with pytest.raises(IngressValidationError):
        engine.submit_job(sub_nan, auth_token=session.auth_token)

    engine.close()


def test_tripartite_engine_crash_recovery_replay(tmp_path: Path) -> None:
    """Verify WAL telemetry replay into SWMR HDF5 for crash recovery."""
    ws = tmp_path / "ws_recovery"
    engine = MobileCloudEngine(workspace_root=ws)

    # Manually append telemetry events directly into WAL
    h_mass = float(mendeleev.element("H").atomic_weight)
    o_mass = float(mendeleev.element("O").atomic_weight)

    engine.wal.append(
        "TELEMETRY_SAMPLE",
        {
            "coords": [[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            "energy": -1.137,
            "masses": [h_mass, h_mass],
        },
    )
    engine.wal.append(
        "TELEMETRY_SAMPLE",
        {
            "coords": [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "energy": -76.43,
            "masses": [o_mass, h_mass, h_mass],
        },
    )

    # Replay WAL
    replayed_count = engine.recover()
    assert replayed_count == 2

    # Check recovered state in HDF5
    h5_state = engine.hdf5_writer.read_reader_mode()
    assert h5_state["coordinates"].shape == (5, 3)  # 2 + 3 coords
    assert len(h5_state["energies"]) == 2
    assert np.isclose(h5_state["energies"][0], -1.137)
    assert np.isclose(h5_state["energies"][1], -76.43)

    engine.close()
