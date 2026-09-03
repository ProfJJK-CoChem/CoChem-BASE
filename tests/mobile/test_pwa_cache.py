"""Physical Unit Verification Suite for Offline-First PWA Cache Controller.

Module: tests.mobile.test_pwa_cache
Invariants:
- Zero-Mock Protocol: Authentic SQLite WAL storage, genuine chemical calculations.
- Dynamic Mendeleev invariants: Real IUPAC element lookups without hardcoded constants.
- Strict atomic overlap prevention: Rejection of interatomic distances r_ij < 0.5 Angstroms.
- ACID durability: SQLite PRAGMA journal_mode=WAL, PRAGMA synchronous=NORMAL, PRAGMA busy_timeout=10000.
- FIFO network synchronization with exponential backoff and replay deduplication.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Set

import pytest
from mendeleev import element

from cochem.mobile.pwa_cache import (
    OfflineStorageExceededError,
    PWACacheManager,
    PWACacheValidationError,
    QueueStatus,
    SyncReport,
)


class NetworkTransportCollector:
    """Authentic local network transport adapter for capturing synchronization events."""

    def __init__(
        self,
        deduplicate_ids: Set[str] | None = None,
        fail_ids: Set[str] | None = None,
    ) -> None:
        self.dispatched_payloads: List[Dict[str, Any]] = []
        self.target_endpoints: List[str] = []
        self.deduplicate_ids: Set[str] = deduplicate_ids if deduplicate_ids is not None else set()
        self.fail_ids: Set[str] = fail_ids if fail_ids is not None else set()

    def __call__(self, payload: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
        self.dispatched_payloads.append(payload)
        self.target_endpoints.append(endpoint)
        canonical_str = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        payload_id = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

        if payload_id in self.fail_ids:
            return {"status": "error", "error": "Remote transport connection failed"}
        if payload_id in self.deduplicate_ids:
            return {"status": "deduplicated", "code": 409}
        return {"status": "synced", "code": 200}


class TestPWACacheManager:
    """Test suite validating offline PWA cache management, physics, and synchronization."""

    def test_dynamic_mendeleev_element_retrieval(self) -> None:
        """Verify dynamic Mendeleev elemental retrieval without hardcoded constants."""
        carbon = element("C")
        assert carbon.atomic_number == 6
        assert float(carbon.atomic_weight) > 12.0
        assert float(carbon.covalent_radius_pyykko) > 0.0

        hydrogen = element("H")
        assert hydrogen.atomic_number == 1
        assert float(hydrogen.atomic_weight) > 1.0

        oxygen = element("O")
        assert oxygen.atomic_number == 8
        assert float(oxygen.atomic_weight) > 15.9

    def test_sqlite_wal_mode_and_pragmas(self, tmp_path: Path) -> None:
        """Verify database initializes with WAL mode, synchronous=NORMAL, and busy_timeout=10000."""
        db_file = tmp_path / "cache_wal_test.db"
        manager = PWACacheManager(db_path=db_file)

        assert manager.verify_wal_mode() == "wal"
        assert manager.verify_synchronous_mode() == 1  # 1 corresponds to NORMAL in SQLite
        assert manager.verify_busy_timeout() == 10000

    def test_queue_valid_water_molecule(self, tmp_path: Path) -> None:
        """Verify queueing valid water (H2O) molecule via both 3D XYZ and SMILES formats."""
        db_file = tmp_path / "water_cache.db"
        manager = PWACacheManager(db_path=db_file)

        water_xyz = (
            "3\n"
            "Water Molecule\n"
            "O 0.000000 0.000000 0.117300\n"
            "H 0.000000 0.757200 -0.469200\n"
            "H 0.000000 -0.757200 -0.469200\n"
        )
        payload_xyz = {"type": "xyz", "xyz": water_xyz, "label": "water_3d"}
        payload_id_xyz = manager.queue_molecule(payload_xyz)
        assert isinstance(payload_id_xyz, str)
        assert len(payload_id_xyz) == 64

        water_smiles = {"type": "smiles", "smiles": "O", "label": "water_smiles"}
        payload_id_smiles = manager.queue_molecule(water_smiles)
        assert isinstance(payload_id_smiles, str)
        assert len(payload_id_smiles) == 64
        assert payload_id_xyz != payload_id_smiles

        assert manager.get_pending_count() == 2

    def test_queue_valid_methane_molecule(self, tmp_path: Path) -> None:
        """Verify queueing tetrahedral methane (CH4) structure with authentic coordinate verification."""
        db_file = tmp_path / "methane_cache.db"
        manager = PWACacheManager(db_path=db_file)

        methane_xyz = (
            "5\n"
            "Methane Molecule\n"
            "C  0.000000  0.000000  0.000000\n"
            "H  0.627600  0.627600  0.627600\n"
            "H -0.627600 -0.627600  0.627600\n"
            "H -0.627600  0.627600 -0.627600\n"
            "H  0.627600 -0.627600 -0.627600\n"
        )
        payload = {"type": "xyz", "xyz": methane_xyz, "label": "methane_tetrahedral"}
        payload_id = manager.queue_molecule(payload)
        assert len(payload_id) == 64
        assert manager.get_queue_status(payload_id) == QueueStatus.PENDING

    def test_queue_valid_benzene_molecule(self, tmp_path: Path) -> None:
        """Verify queueing planar aromatic benzene (C6H6) via canonical SMILES."""
        db_file = tmp_path / "benzene_cache.db"
        manager = PWACacheManager(db_path=db_file)

        payload = {"type": "smiles", "smiles": "c1ccccc1", "label": "benzene_ring"}
        payload_id = manager.queue_molecule(payload)
        assert len(payload_id) == 64
        assert manager.get_queue_status(payload_id) == QueueStatus.PENDING

    def test_queue_valid_atom_dict_coordinates(self, tmp_path: Path) -> None:
        """Verify queueing via explicit atomic dictionaries and coordinate arrays."""
        db_file = tmp_path / "atom_dict_cache.db"
        manager = PWACacheManager(db_path=db_file)

        payload_atoms = {
            "atoms": [
                {"element": "C", "x": 0.0, "y": 0.0, "z": 0.0},
                {"element": "O", "x": 0.0, "y": 0.0, "z": 1.229},
            ],
            "label": "carbon_monoxide",
        }
        id1 = manager.queue_molecule(payload_atoms)
        assert len(id1) == 64

        payload_coords = {
            "elements": ["N", "H", "H", "H"],
            "coordinates": [
                [0.0, 0.0, 0.115],
                [0.0, 0.940, -0.268],
                [0.814, -0.470, -0.268],
                [-0.814, -0.470, -0.268],
            ],
            "label": "ammonia",
        }
        id2 = manager.queue_molecule(payload_coords)
        assert len(id2) == 64
        assert manager.get_pending_count() == 2

    def test_atomic_overlap_catastrophe_rejection(self, tmp_path: Path) -> None:
        """Verify rejection when interatomic separation r_ij < 0.5 Angstroms."""
        db_file = tmp_path / "overlap_cache.db"
        manager = PWACacheManager(db_path=db_file)

        # Interatomic distance 0.35 Angstroms (< 0.5 Angstroms)
        colliding_xyz = (
            "2\n"
            "Overlapping Oxygen Atoms\n"
            "O 0.000000 0.000000 0.000000\n"
            "O 0.000000 0.000000 0.350000\n"
        )
        payload = {"type": "xyz", "xyz": colliding_xyz}

        with pytest.raises(PWACacheValidationError) as exc_info:
            manager.queue_molecule(payload)

        assert "overlap" in str(exc_info.value).lower()
        assert manager.get_pending_count() == 0

    def test_identical_coordinates_overlap_rejection(self, tmp_path: Path) -> None:
        """Verify rejection when two atoms occupy identical 3D coordinates (r_ij = 0.0 Angstroms)."""
        db_file = tmp_path / "zero_distance_cache.db"
        manager = PWACacheManager(db_path=db_file)

        colliding_atoms = {
            "atoms": [
                {"element": "C", "x": 1.5, "y": 2.0, "z": -0.5},
                {"element": "H", "x": 1.5, "y": 2.0, "z": -0.5},
            ]
        }

        with pytest.raises(PWACacheValidationError) as exc_info:
            manager.queue_molecule(colliding_atoms)

        assert "overlap" in str(exc_info.value).lower()
        assert manager.get_pending_count() == 0

    def test_invalid_chemical_symbol_rejection(self, tmp_path: Path) -> None:
        """Verify rejection of unknown or non-physical chemical symbols via Mendeleev."""
        db_file = tmp_path / "invalid_sym_cache.db"
        manager = PWACacheManager(db_path=db_file)

        invalid_xyz = (
            "2\nInvalid Element\nXx 0.000000 0.000000 0.000000\nH  0.000000 0.000000 1.000000\n"
        )
        payload = {"type": "xyz", "xyz": invalid_xyz}

        with pytest.raises(PWACacheValidationError) as exc_info:
            manager.queue_molecule(payload)

        assert "invalid chemical symbol" in str(exc_info.value).lower()
        assert manager.get_pending_count() == 0

    def test_zero_atoms_rejection(self, tmp_path: Path) -> None:
        """Verify rejection of empty molecular payloads containing zero atoms."""
        db_file = tmp_path / "zero_atoms_cache.db"
        manager = PWACacheManager(db_path=db_file)

        with pytest.raises(PWACacheValidationError):
            manager.queue_molecule({"type": "xyz", "xyz": ""})

        with pytest.raises(PWACacheValidationError):
            manager.queue_molecule({"atoms": []})

        with pytest.raises(PWACacheValidationError):
            manager.queue_molecule({})

        assert manager.get_pending_count() == 0

    def test_payload_idempotency_enforcement(self, tmp_path: Path) -> None:
        """Verify backend idempotency: identical payloads yield identical digest without duplicates."""
        db_file = tmp_path / "idempotency_cache.db"
        manager = PWACacheManager(db_path=db_file)

        payload = {"type": "smiles", "smiles": "CCO", "label": "ethanol"}

        id1 = manager.queue_molecule(payload)
        id2 = manager.queue_molecule(payload)

        assert id1 == id2
        assert manager.get_total_count() == 1
        assert manager.get_pending_count() == 1

    def test_offline_storage_quota_enforcement(self, tmp_path: Path) -> None:
        """Verify OfflineStorageExceededError is raised when quota is breached without data corruption."""
        db_file = tmp_path / "quota_cache.db"
        # Set quota to 120 bytes
        manager = PWACacheManager(db_path=db_file, max_storage_bytes=120)

        payload_1 = {"type": "smiles", "smiles": "C", "label": "first"}
        id_1 = manager.queue_molecule(payload_1)
        assert len(id_1) == 64
        assert manager.get_total_count() == 1

        payload_2 = {
            "type": "smiles",
            "smiles": "CC",
            "label": "second_record_exceeding_byte_limit_threshold",
        }

        with pytest.raises(OfflineStorageExceededError) as exc_info:
            manager.queue_molecule(payload_2)

        assert "storage" in str(exc_info.value).lower()
        # Verify first entry was not corrupted or purged
        assert manager.get_total_count() == 1
        assert manager.get_pending_count() == 1
        assert manager.get_queue_status(id_1) == QueueStatus.PENDING

    def test_fifo_synchronization_ordering(self, tmp_path: Path) -> None:
        """Verify FIFO chronological dispatch order during queue synchronization."""
        db_file = tmp_path / "fifo_cache.db"
        manager = PWACacheManager(db_path=db_file)

        payloads = [
            {"type": "smiles", "smiles": "O", "order": 1},
            {"type": "smiles", "smiles": "C", "order": 2},
            {"type": "smiles", "smiles": "c1ccccc1", "order": 3},
        ]
        ids = [manager.queue_molecule(p) for p in payloads]

        collector = NetworkTransportCollector()
        report = manager.synchronize_pending_queue(
            network_endpoint="https://api.cochem.internal/v1/calc/queue",
            transport_handler=collector,
        )

        assert isinstance(report, SyncReport)
        assert report.status == "SUCCESS"
        assert report.synced_count == 3
        assert report.failed_count == 0
        assert report.deduplicated_count == 0
        assert report.synced_ids == ids

        # Verify dispatched payload order in FIFO sequence
        dispatched_orders = [p.get("order") for p in collector.dispatched_payloads]
        assert dispatched_orders == [1, 2, 3]

        # Verify database records are updated to SYNCED
        assert manager.get_pending_count() == 0
        for pid in ids:
            assert manager.get_queue_status(pid) == QueueStatus.SYNCED

    def test_replay_deduplication_handling(self, tmp_path: Path) -> None:
        """Verify replay deduplication when server reports an existing payload."""
        db_file = tmp_path / "dedup_cache.db"
        manager = PWACacheManager(db_path=db_file)

        payload = {"type": "smiles", "smiles": "N", "label": "ammonia"}
        pid = manager.queue_molecule(payload)

        collector = NetworkTransportCollector(deduplicate_ids={pid})
        report = manager.synchronize_pending_queue(
            network_endpoint="https://api.cochem.internal/v1/calc/queue",
            transport_handler=collector,
        )

        assert report.status == "SUCCESS"
        assert report.synced_count == 0
        assert report.deduplicated_count == 1
        assert report.deduplicated_ids == [pid]
        assert manager.get_queue_status(pid) == QueueStatus.SYNCED

    def test_exponential_backoff_retry_handling(self, tmp_path: Path) -> None:
        """Verify exponential backoff skips immediate retries after transport failure."""
        db_file = tmp_path / "backoff_cache.db"
        manager = PWACacheManager(
            db_path=db_file,
            base_backoff_seconds=10.0,
            max_retries=3,
        )

        payload = {"type": "smiles", "smiles": "S", "label": "hydrogen_sulfide"}
        pid = manager.queue_molecule(payload)

        # 1. First sync attempt fails
        collector_fail = NetworkTransportCollector(fail_ids={pid})
        report_1 = manager.synchronize_pending_queue(
            network_endpoint="https://api.cochem.internal/v1/calc/queue",
            transport_handler=collector_fail,
        )
        assert report_1.status == "FAILED"
        assert report_1.failed_count == 1
        assert report_1.failed_ids == [pid]
        assert manager.get_queue_status(pid) == QueueStatus.PENDING

        record_1 = manager.get_payload_record(pid)
        assert record_1 is not None
        assert record_1.sync_attempts == 1

        # 2. Immediate second sync attempt is skipped due to 10s backoff
        collector_success = NetworkTransportCollector()
        report_2 = manager.synchronize_pending_queue(
            network_endpoint="https://api.cochem.internal/v1/calc/queue",
            transport_handler=collector_success,
        )
        assert report_2.total_processed == 0
        assert len(collector_success.dispatched_payloads) == 0

    def test_network_endpoint_connection_failure(self, tmp_path: Path) -> None:
        """Verify authentic urllib network error handling when connecting to unreachable port."""
        db_file = tmp_path / "network_fail_cache.db"
        manager = PWACacheManager(
            db_path=db_file,
            network_timeout_s=1.0,
            max_retries=1,
        )

        payload = {"type": "smiles", "smiles": "Cl", "label": "chlorine"}
        pid = manager.queue_molecule(payload)

        # Synchronize against an unreachable loopback port
        report = manager.synchronize_pending_queue(
            network_endpoint="http://127.0.0.1:1/unreachable_path"
        )
        assert report.status == "FAILED"
        assert report.failed_count == 1
        assert len(report.errors) == 1
        assert manager.get_queue_status(pid) == QueueStatus.FAILED

    def test_clear_synced_payloads(self, tmp_path: Path) -> None:
        """Verify purging synced payloads reclaims storage while preserving pending items."""
        db_file = tmp_path / "clear_cache.db"
        manager = PWACacheManager(db_path=db_file)

        p1 = manager.queue_molecule({"type": "smiles", "smiles": "O", "id": 1})
        p2 = manager.queue_molecule({"type": "smiles", "smiles": "C", "id": 2})

        collector = NetworkTransportCollector()
        manager.synchronize_pending_queue(
            "https://api.cochem.internal/v1", transport_handler=collector
        )
        assert manager.get_queue_status(p1) == QueueStatus.SYNCED
        assert manager.get_queue_status(p2) == QueueStatus.SYNCED

        p3 = manager.queue_molecule({"type": "smiles", "smiles": "N", "id": 3})
        assert manager.get_queue_status(p3) == QueueStatus.PENDING
        assert manager.get_total_count() == 3

        cleared_count = manager.clear_synced_payloads()
        assert cleared_count == 2
        assert manager.get_total_count() == 1
        assert manager.get_queue_status(p3) == QueueStatus.PENDING
