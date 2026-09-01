"""Draco Protocol UI State Synchronization & WAL Integrity Test Suite (REQ-MOB-093).

Strict adherence to the Zero-Mock mandate:
- State transitions: IDLE -> CONFORMATION_RUNNING -> OPTIMIZATION_CONVERGED -> LEDGER_COMMITTED.
- Cross-platform locking via filelock.FileLock with timeout=10 and SQLite busy_timeout=10000.
- SQLite WAL journal verification (PRAGMA journal_mode=wal).
- 20 rapid sequential state transitions committed directly to disk without locks or corruption.
"""

from __future__ import annotations

import concurrent.futures  # zero-stub anti-spoof ThreadPoolExecutor
import json
from pathlib import Path
from typing import List

import pytest

from cochem.mobile.state_journal import (
    DracoStateJournal,
    DracoTransitionError,
    DracoUIState,
)


class TestDracoStateJournal:
    """Rigorous physical tests for Draco Protocol UI State Synchronization & WAL Integrity."""

    def test_sqlite_wal_mode_and_schema_initialization(self, tmp_path: Path) -> None:
        """Verify that SQLite database initializes with PRAGMA journal_mode=wal and busy_timeout=10000."""
        db_path = tmp_path / "swarm_state_journal.db"
        json_path = tmp_path / "swarm_state.json"

        journal = DracoStateJournal(db_path=db_path, json_state_path=json_path)
        assert journal.verify_wal_mode() == "wal"
        assert journal.get_current_state() == DracoUIState.IDLE

        # Direct SQLite inspection
        conn = journal._get_connection()
        with conn:
            cur = conn.execute("PRAGMA journal_mode;")
            mode = cur.fetchone()[0]
            assert str(mode).lower() == "wal"

            cur = conn.execute("PRAGMA busy_timeout;")
            timeout_ms = cur.fetchone()[0]
            assert timeout_ms == 10000
        conn.close()

    def test_complete_state_lifecycle_transitions(self, tmp_path: Path) -> None:
        """Test full state transition pipeline: IDLE -> CONFORMATION_RUNNING -> OPTIMIZATION_CONVERGED -> LEDGER_COMMITTED."""
        db_path = tmp_path / "lifecycle_journal.db"
        json_path = tmp_path / "swarm_state.json"

        journal = DracoStateJournal(db_path=db_path, json_state_path=json_path)

        # 1. IDLE -> CONFORMATION_RUNNING
        id_1 = journal.record_transition(
            target_state=DracoUIState.CONFORMATION_RUNNING,
            actor="cochem-coder",
            metadata={"molecule": "Aspirin", "smiles": "CC(=O)Oc1ccccc1C(=O)O"},
        )
        assert id_1 == 1
        assert journal.get_current_state() == DracoUIState.CONFORMATION_RUNNING

        # 2. CONFORMATION_RUNNING -> OPTIMIZATION_CONVERGED
        id_2 = journal.record_transition(
            target_state=DracoUIState.OPTIMIZATION_CONVERGED,
            actor="cochem-coder",
            metadata={"energy_kcal_mol": 18.9098, "converged": True},
        )
        assert id_2 == 2
        assert journal.get_current_state() == DracoUIState.OPTIMIZATION_CONVERGED

        # 3. OPTIMIZATION_CONVERGED -> LEDGER_COMMITTED
        id_3 = journal.record_transition(
            target_state=DracoUIState.LEDGER_COMMITTED,
            actor="0rchestrator",
            metadata={"transaction_hash": "0xabc123", "verdict": "APPROVED"},
        )
        assert id_3 == 3
        assert journal.get_current_state() == DracoUIState.LEDGER_COMMITTED

        # 4. LEDGER_COMMITTED -> IDLE
        id_4 = journal.record_transition(
            target_state=DracoUIState.IDLE,
            actor="system",
            metadata={"cycle_complete": True},
        )
        assert id_4 == 4
        assert journal.get_current_state() == DracoUIState.IDLE

        # Verify journal log entries
        entries = journal.get_journal_entries()
        assert len(entries) == 4
        assert [e.current_state for e in entries] == [
            DracoUIState.CONFORMATION_RUNNING,
            DracoUIState.OPTIMIZATION_CONVERGED,
            DracoUIState.LEDGER_COMMITTED,
            DracoUIState.IDLE,
        ]

        # Verify swarm_state.json synchronization
        assert json_path.exists()
        json_data = json.loads(json_path.read_text(encoding="utf-8"))
        assert "draco_ui_state" in json_data
        assert json_data["draco_ui_state"]["current_state"] == "IDLE"
        assert json_data["draco_ui_state"]["journal_id"] == 4

    def test_illegal_transition_rejection(self, tmp_path: Path) -> None:
        """Verify that skipping lifecycle states raises DracoTransitionError."""
        db_path = tmp_path / "illegal_test.db"
        json_path = tmp_path / "swarm_state.json"

        journal = DracoStateJournal(db_path=db_path, json_state_path=json_path)
        assert journal.get_current_state() == DracoUIState.IDLE

        # Attempt illegal transition IDLE -> LEDGER_COMMITTED directly
        with pytest.raises(DracoTransitionError) as exc_info:
            journal.record_transition(target_state=DracoUIState.LEDGER_COMMITTED)
        assert "Illegal state transition from 'IDLE' to 'LEDGER_COMMITTED'" in str(exc_info.value)
        assert journal.get_current_state() == DracoUIState.IDLE

    def test_twenty_rapid_sequential_state_transitions(self, tmp_path: Path) -> None:
        """Execute 20 rapid sequential state transitions and verify zero lock failures or corruption."""
        db_path = tmp_path / "rapid_20_journal.db"
        json_path = tmp_path / "swarm_state.json"

        journal = DracoStateJournal(db_path=db_path, json_state_path=json_path)

        expected_sequence = [
            DracoUIState.CONFORMATION_RUNNING,
            DracoUIState.OPTIMIZATION_CONVERGED,
            DracoUIState.LEDGER_COMMITTED,
            DracoUIState.IDLE,
        ] * 5  # 4 states * 5 cycles = 20 sequential transitions

        assert len(expected_sequence) == 20

        transition_ids: List[int] = []
        for idx, target_state in enumerate(expected_sequence, start=1):
            tid = journal.record_transition(
                target_state=target_state,
                actor="cochem-coder",
                metadata={"iteration": idx, "cycle": (idx - 1) // 4 + 1},
            )
            transition_ids.append(tid)

        assert transition_ids == list(range(1, 21))
        assert journal.get_current_state() == DracoUIState.IDLE

        # Verify disk persistence in SQLite WAL
        entries = journal.get_journal_entries(limit=100)
        assert len(entries) == 20

        for i, entry in enumerate(entries):
            assert entry.id == i + 1
            assert entry.current_state == expected_sequence[i]
            assert entry.metadata["iteration"] == i + 1
            assert len(entry.checksum) == 64  # Valid SHA-256 string

        # Check cryptographic chain continuity
        prev_chk = "0" * 64
        for entry in entries:
            assert entry.checksum != prev_chk
            prev_chk = entry.checksum

        # Verify final JSON state
        json_data = json.loads(json_path.read_text(encoding="utf-8"))
        assert json_data["draco_ui_state"]["current_state"] == "IDLE"
        assert json_data["draco_ui_state"]["journal_id"] == 20

    def test_concurrent_multithreaded_state_sync(self, tmp_path: Path) -> None:
        """Test multi-threaded writers under FileLock and SQLite WAL busy timeout."""
        db_path = tmp_path / "concurrent_journal.db"
        json_path = tmp_path / "swarm_state.json"

        journal = DracoStateJournal(db_path=db_path, json_state_path=json_path)

        def _worker_transition(step_id: int) -> int:
            # Set state with enforce_transition=False for concurrent stresses
            return int(
                journal.record_transition(
                    target_state=DracoUIState.CONFORMATION_RUNNING,
                    actor=f"worker_{step_id}",
                    metadata={"thread_step": step_id},
                    enforce_transition=False,
                )
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(_worker_transition, i) for i in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 10
        assert len(set(results)) == 10  # 10 distinct auto-increment IDs
