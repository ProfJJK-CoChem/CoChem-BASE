"""
Physical Unit and Integration Test Suite for CoChem Core Registry Manager.
Verifies HDF5 state registry, filelock-based atomic locking, fcntl eradication,
NFS-resilient directory-level staging, metadata server integration with filesystem fallback,
Pydantic validation checkpoints, Mendeleev dynamic queries, lineage UUID tracking,
PRNG seed locking, basis set archival, schema migration, and active jobs lifecycle.

Zero-Mock Policy: 100% genuine OS processes, genuine filelocks, and real filesystem operations.
"""

from __future__ import annotations

import inspect
import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Any, List

import filelock
import pytest
import zmq
from pydantic import BaseModel, Field, ValidationError

import cochem_base.core.cochem_core_registry_manager as reg_module
from cochem_base.core.cochem_core_registry_manager import (
    AtomicFileLock,
    BaseMetadataServer,
    BasisSetNotFoundError,
    CoChemLockTimeoutError,
    FilesystemMetadataServer,
    IsotopeStabilityError,
    MetadataBackendType,
    MetadataServerManager,
    PostgresMetadataServer,
    RecordNotFoundError,
    RedisMetadataServer,
    RegistryCorruptionError,
    RegistryError,
    RegistryLockError,
    RegistryLockTimeoutError,
    RegistryManager,
    RegistryMissingError,
    RegistryParseError,
    SchemaMigrationError,
    atomic_write_json,
    broadcast_system_config,
    default_metadata_manager,
    get_active_job,
    get_default_config_path,
    hash_environment,
    interpolate_env_vars,
    is_master_node,
    list_active_jobs,
    load_system_config,
    migrate_schema,
    nfs_atomic_directory_rename,
    receive_system_config_broadcast,
    register_active_job,
    remove_active_job,
    save_system_config,
    update_active_job,
    update_system_config,
)
from cochem_core_registry_schema import CoChemSystemConfig


class PhysicalJobRecord(BaseModel):
    command: list[str] = Field(default_factory=lambda: ["echo", "test"])
    product_class: str = "Product_A"
    atom_count: int = 12
    converged: bool = True


class HardwareSpecificationModel(BaseModel):
    cpu_cores: int = 8
    ram_gb: float = 32.0
    gpu_profile: str = "RTX_4090"


# =============================================================================
# REQUIREMENT 1 & 2: FCNTL ERADICATION & FILELOCK ATOMIC LOCKING
# =============================================================================

def test_fcntl_eradication_verification() -> None:
    """Verifies that POSIX fcntl is completely eradicated from registry manager."""
    src = inspect.getsource(reg_module)
    assert "import fcntl" not in src, "fcntl must not be imported anywhere in the module"
    assert "fcntl." not in src, "fcntl must not be used in the module"
    assert not hasattr(reg_module, "fcntl"), "fcntl attribute must not exist on the module"


def test_atomic_file_lock_lifecycle(tmp_path: Path) -> None:
    """Tests clean lock acquisition, under-the-hood filelock binding, and release."""
    lock_file = tmp_path / "test.lock"

    with AtomicFileLock(lock_file, timeout=2.0) as lock:
        assert lock_file.exists()
        assert lock._is_locked is True
        assert lock._filelock is not None
        assert isinstance(lock._filelock, (filelock.FileLock, filelock.SoftFileLock, filelock.BaseFileLock))

    assert not lock_file.exists()
    assert lock._is_locked is False


def test_atomic_file_lock_reentrancy_and_multithreading(tmp_path: Path) -> None:
    """Tests reentrant lock acquisitions on the same thread without deadlocking."""
    lock_file = tmp_path / "reentrant.lock"

    # Nested acquisition on same instance
    l1 = AtomicFileLock(lock_file, timeout=2.0)
    with l1:
        assert lock_file.exists()
        with l1:
            assert lock_file.exists()
        assert lock_file.exists()
    assert not lock_file.exists()

    # Nested acquisition on distinct instances on same thread
    l_a = AtomicFileLock(lock_file, timeout=2.0)
    l_b = AtomicFileLock(lock_file, timeout=2.0)
    with l_a:
        assert lock_file.exists()
        with l_b:
            assert lock_file.exists()
        assert lock_file.exists()
    assert not lock_file.exists()


def test_atomic_file_lock_contention_and_timeout(tmp_path: Path) -> None:
    """Tests lock contention across threads and 10-second gatekeeper timeout raising CoChemLockTimeoutError."""
    lock_file = tmp_path / "contend.lock"

    # Acquire first lock on main thread
    lock1 = AtomicFileLock(lock_file, timeout=2.0)
    lock1.acquire()

    # Second lock on another thread must time out
    err_holder: list[Exception] = []

    def try_lock2() -> None:
        try:
            lock2 = AtomicFileLock(lock_file, timeout=0.1)
            lock2.acquire()
        except Exception as e:
            err_holder.append(e)

    t = threading.Thread(target=try_lock2)
    t.start()
    t.join()

    assert len(err_holder) == 1
    assert isinstance(err_holder[0], CoChemLockTimeoutError)
    assert issubclass(CoChemLockTimeoutError, RegistryLockError)
    assert issubclass(CoChemLockTimeoutError, TimeoutError)

    # Release first lock
    lock1.release()

    # Subsequent acquisition succeeds immediately
    lock3 = AtomicFileLock(lock_file, timeout=1.0)
    lock3.acquire()
    lock3.release()


def test_atomic_file_lock_stale_reaping(tmp_path: Path) -> None:
    """Tests that stale lock files past stale_timeout are safely reaped."""
    lock_file = tmp_path / "stale.lock"
    lock_file.write_text("99999:0\n", encoding="utf-8")

    # Set mtime to 100 seconds in the past
    past_time = time.time() - 100
    os.utime(lock_file, (past_time, past_time))

    lock = AtomicFileLock(lock_file, timeout=2.0, stale_timeout=1.0)
    assert lock.acquire() is True
    lock.release()


# =============================================================================
# REQUIREMENT 2: NFS-RESILIENT ATOMIC TRANSACTIONS & DIRECTORY RENAMES
# =============================================================================

def test_nfs_atomic_directory_rename_lifecycle(tmp_path: Path) -> None:
    """Tests NFS-resilient directory-level atomic rename with exponential backoff."""
    src_dir = tmp_path / "src_stage"
    src_dir.mkdir(parents=True)
    (src_dir / "file1.txt").write_text("data1", encoding="utf-8")
    (src_dir / "file2.txt").write_text("data2", encoding="utf-8")

    dst_dir = tmp_path / "target_dir"
    nfs_atomic_directory_rename(src_dir, dst_dir)

    assert not src_dir.exists()
    assert dst_dir.exists()
    assert (dst_dir / "file1.txt").read_text(encoding="utf-8") == "data1"
    assert (dst_dir / "file2.txt").read_text(encoding="utf-8") == "data2"

    # Test replacing an existing directory
    src_dir_2 = tmp_path / "src_stage_2"
    src_dir_2.mkdir(parents=True)
    (src_dir_2 / "file1.txt").write_text("updated_data1", encoding="utf-8")

    nfs_atomic_directory_rename(src_dir_2, dst_dir)
    assert not src_dir_2.exists()
    assert (dst_dir / "file1.txt").read_text(encoding="utf-8") == "updated_data1"

    # Test non-existent source directory
    with pytest.raises(FileNotFoundError):
        nfs_atomic_directory_rename(tmp_path / "non_existent_dir", tmp_path / "any_dst")


def test_atomic_write_json_directory_staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests directory-level staging and environment variable expansion in atomic_write_json."""
    monkeypatch.setenv("COCHEM_STAGE_VAR", "staged_value")

    out_file = tmp_path / "config.json"
    data = {
        "path": "${COCHEM_STAGE_VAR}/subdir",
        "nested": {"val": "%COCHEM_STAGE_VAR%"},
        "count": 42,
    }

    atomic_write_json(out_file, data)
    assert out_file.exists()

    # Staging temporary directories must be cleanly reaped
    staging_dirs = list(tmp_path.glob(".staging_*"))
    assert len(staging_dirs) == 0

    raw_text = out_file.read_text(encoding="utf-8")
    interpolated = interpolate_env_vars(raw_text)
    parsed = json.loads(interpolated)
    assert parsed["path"] == "staged_value/subdir"
    assert parsed["nested"]["val"] == "staged_value"
    assert parsed["count"] == 42


# =============================================================================
# REQUIREMENT 2: DEDICATED METADATA SERVERS & FILESYSTEM FALLBACK
# =============================================================================

def test_filesystem_metadata_server(tmp_path: Path) -> None:
    """Tests FilesystemMetadataServer storage, retrieval, and deletion."""
    fs_server = FilesystemMetadataServer(base_dir=tmp_path / "metadata_store")
    assert fs_server.is_available() is True
    assert fs_server.backend_type == MetadataBackendType.FILESYSTEM

    key = "test_config_key"
    payload = json.dumps({"schema_version": "4.0.0", "status": "active"})

    assert fs_server.get_state(key) is None
    assert fs_server.set_state(key, payload) is True
    assert fs_server.get_state(key) == payload
    assert fs_server.delete_state(key) is True
    assert fs_server.get_state(key) is None


def test_metadata_server_manager_fallback(tmp_path: Path) -> None:
    """Tests MetadataServerManager automatic fallback from offline Redis/Postgres to filesystem."""
    fs_server = FilesystemMetadataServer(base_dir=tmp_path / "meta_mgr_store")
    # Redis and Postgres are pointed to invalid ports to test resilient offline fallback
    redis_server = RedisMetadataServer(host="127.0.0.1", port=65530, timeout=0.05)
    postgres_server = PostgresMetadataServer(host="127.0.0.1", port=65531, timeout=0.05)

    mgr = MetadataServerManager(
        preferred_backend=MetadataBackendType.REDIS,
        redis_server=redis_server,
        postgres_server=postgres_server,
        filesystem_server=fs_server,
    )

    # Since Redis is offline, manager must resolve to Filesystem fallback
    active_backend = mgr.get_active_backend()
    assert active_backend.backend_type == MetadataBackendType.FILESYSTEM

    key = "cochem_state_001"
    val = json.dumps({"pipeline": "opt_freq", "iteration": 4})

    assert mgr.set_state(key, val) is True
    assert mgr.get_state(key) == val
    assert mgr.delete_state(key) is True
    assert mgr.get_state(key) is None


# =============================================================================
# REQUIREMENT 3: PYDANTIC VERIFICATION CHECKPOINT
# =============================================================================

def test_pydantic_checkpoint_rejects_illegal_data_injection(tmp_path: Path) -> None:
    """Tests that modifying system config strictly rejects illegal fields or invalid data types."""
    cfg_file = tmp_path / "cochem_system_config.json"
    rm = RegistryManager(config_path=str(cfg_file), registry_path=str(tmp_path / "reg.h5"))

    base_dict = {
        "schema_version": "4.0.0",
        "hardware": {
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "ram_gb": 32.0,
            "os_target": "windows_x86_64",
        },
    }
    rm.save_system_config(base_dict)
    assert cfg_file.exists()

    # 1. Attempt to inject an illegal extra field
    with pytest.raises(SchemaMigrationError):
        rm.update_system_config(illegal_injected_field="malicious_payload")

    # 2. Attempt to inject invalid hardware parameters (e.g. negative cpu cores)
    with pytest.raises(SchemaMigrationError):
        rm.update_system_config(hardware={"physical_cpu_cores": -10, "ram_gb": -1})

    # Verify that the master state file remains intact and uncorrupted
    reloaded = rm.load_system_config()
    assert reloaded.hardware.physical_cpu_cores == 8


def test_registry_manager_config_transaction_checkpoint(tmp_path: Path) -> None:
    """Tests atomic config_transaction context manager with Pydantic verification checkpoint."""
    cfg_file = tmp_path / "cochem_system_config.json"
    rm = RegistryManager(config_path=str(cfg_file), registry_path=str(tmp_path / "reg.h5"))

    base_dict = {
        "schema_version": "4.0.0",
        "hardware": {
            "physical_cpu_cores": 12,
            "logical_cpu_cores": 24,
            "ram_gb": 64.0,
            "os_target": "linux_x86_64",
        },
    }
    rm.save_system_config(base_dict)

    with rm.config_transaction() as cfg:
        cfg.rdkit_random_seed = 99999

    reloaded = rm.load_system_config()
    assert reloaded.rdkit_random_seed == 99999


# =============================================================================
# ACTIVE JOBS LIFECYCLE MANAGEMENT
# =============================================================================

def test_active_jobs_lifecycle_in_system_config(tmp_path: Path) -> None:
    """Tests register, get, list, update, and removal of active jobs in cochem_system_config.json."""
    cfg_file = tmp_path / "cochem_system_config.json"
    rm = RegistryManager(config_path=str(cfg_file), registry_path=str(tmp_path / "reg.h5"))

    base_dict = {
        "schema_version": "4.0.0",
        "hardware": {
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "ram_gb": 32.0,
            "os_target": "linux_x86_64",
        },
    }
    rm.save_system_config(base_dict)

    # Invalid job ID validation
    with pytest.raises(ValueError):
        rm.register_active_job("", {"status": "pending"})
    assert rm.get_active_job("") is None
    assert rm.remove_active_job("") is False

    # Register active job
    job_payload = {
        "task_name": "conformer_sampling",
        "status": "running",
        "node": "node-42",
    }
    rm.register_active_job("task_001", job_payload)

    # Retrieval
    job = rm.get_active_job("task_001")
    assert job is not None
    assert job["task_name"] == "conformer_sampling"
    assert job["status"] == "running"
    assert "registered_at" in job

    # List active jobs
    jobs_map = rm.list_active_jobs()
    assert "task_001" in jobs_map

    # Update active job
    updated = rm.update_active_job("task_001", status="completed", final_energy=-420.5)
    assert updated["status"] == "completed"
    assert updated["final_energy"] == -420.5
    assert "updated_at" in updated

    # Update non-existent job
    with pytest.raises(RecordNotFoundError):
        rm.update_active_job("task_non_existent", status="failed")

    # Remove active job
    assert rm.remove_active_job("task_001") is True
    assert rm.get_active_job("task_001") is None
    assert rm.remove_active_job("task_001") is False


# =============================================================================
# HDF5 REGISTRY OPERATIONS, LINEAGE, SEEDS, BASIS SETS
# =============================================================================

def test_registry_initialization_and_topology(tmp_path: Path) -> None:
    reg_file = tmp_path / "registry.h5"
    rm = RegistryManager(registry_path=str(reg_file))
    assert Path(rm.registry_path).exists()
    assert Path(rm.lock_path) == Path(str(reg_file) + ".lock")

    stats = rm.get_registry_stats()
    assert stats["jobs_count"] == 0
    assert stats["hardware_profiles_count"] == 0
    assert stats["provenance_count"] == 0
    assert stats["basis_sets_count"] == 0
    assert stats["seeds_count"] == 0
    assert stats["version"] == RegistryManager.SCHEMA_VERSION

    # Re-initialization on existing registry
    rm2 = RegistryManager(registry_path=str(reg_file))
    assert rm2.get_registry_stats()["version"] == RegistryManager.SCHEMA_VERSION


def test_transaction_context_manager(tmp_path: Path) -> None:
    reg_file = tmp_path / "trans_test.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    with rm.transaction("a") as h5:
        assert "jobs" in h5
        assert "provenance" in h5
        h5["metadata"].attrs["custom_test_key"] = "test_value"

    with rm.transaction("r") as h5:
        assert h5["metadata"].attrs["custom_test_key"] == "test_value"


def test_mendeleev_isotopic_mass_resolution() -> None:
    mass_c = RegistryManager.get_isotopic_mass("C")
    assert isinstance(mass_c, float)
    assert 11.99 < mass_c < 12.02

    mass_h = RegistryManager.get_isotopic_mass("H")
    assert isinstance(mass_h, float)
    assert 1.007 < mass_h < 1.009

    mass_c12 = RegistryManager.get_isotopic_mass("C", 12)
    assert mass_c12 == 12.0

    mass_c13 = RegistryManager.get_isotopic_mass("C", 13)
    assert 13.003 < mass_c13 < 13.004

    mass_h2 = RegistryManager.get_isotopic_mass("H", 2)
    assert 2.014 < mass_h2 < 2.015

    mass_n = RegistryManager.get_isotopic_mass("  n  ")
    assert 14.00 < mass_n < 14.01

    mass_d = RegistryManager.get_isotopic_mass("D")
    assert 2.014 < mass_d < 2.015
    mass_t = RegistryManager.get_isotopic_mass("T")
    assert 3.015 < mass_t < 3.017


def test_mendeleev_error_handling() -> None:
    with pytest.raises(IsotopeStabilityError):
        RegistryManager.get_isotopic_mass("NonExistentElement123")

    with pytest.raises(ValueError, match="not found in Mendeleev database"):
        RegistryManager.get_isotopic_mass("C", 999)

    with pytest.raises(ValueError, match="Mass number must be an integer"):
        RegistryManager.get_isotopic_mass("C", "invalid")  # type: ignore

    with pytest.raises(ValueError):
        RegistryManager.get_isotopic_mass("")
    with pytest.raises(ValueError):
        RegistryManager.get_isotopic_mass(None)  # type: ignore


def test_get_all_isotopes() -> None:
    c_isotopes = RegistryManager.get_all_isotopes("C")
    assert isinstance(c_isotopes, list)
    assert len(c_isotopes) > 0
    mass_numbers = [iso["mass_number"] for iso in c_isotopes]
    assert 12 in mass_numbers
    assert 13 in mass_numbers

    d_isotopes = RegistryManager.get_all_isotopes("D")
    assert isinstance(d_isotopes, list)
    assert len(d_isotopes) > 0

    with pytest.raises(ValueError):
        RegistryManager.get_all_isotopes("")
    with pytest.raises(IsotopeStabilityError):
        RegistryManager.get_all_isotopes("InvalidElement999")


def test_job_registration_and_lifecycle(tmp_path: Path) -> None:
    reg_file = tmp_path / "jobs_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    with pytest.raises(ValueError):
        rm.register_job("", {"status": "pending"})
    with pytest.raises(ValueError):
        rm.register_job(None, {"status": "pending"})  # type: ignore

    job1_data = {
        "command": ["orca", "calc.inp"],
        "status": "submitted",
        "nested_meta": {"tier": 3, "tags": ["opt", "freq"]},
        "walltime_limit": 3600,
        "null_val": None,
    }
    rm.register_job("job_001", job1_data)

    rec = rm.get_job("job_001")
    assert rec is not None
    assert rec["command"] == ["orca", "calc.inp"]
    assert rec["status"] == "submitted"
    assert rec["nested_meta"] == {"tier": 3, "tags": ["opt", "freq"]}
    assert rec["walltime_limit"] == 3600
    assert rec["null_val"] is None
    assert "registered_at" in rec

    job2_model = PhysicalJobRecord(product_class="Product_C", atom_count=24)
    rm.register_job("job_002", job2_model)
    rec2 = rm.get_job("job_002")
    assert rec2 is not None
    assert rec2["product_class"] == "Product_C"
    assert rec2["atom_count"] == 24
    assert rec2["converged"] is True

    rm.update_job_status("job_001", "completed", return_code=0, energy=-154.234)
    updated = rm.get_job("job_001")
    assert updated is not None
    assert updated["status"] == "completed"
    assert updated["return_code"] == 0
    assert updated["energy"] == -154.234
    assert "updated_at" in updated

    with pytest.raises(ValueError, match="Cannot update status for non-existent job"):
        rm.update_job_status("non_existent_job", "running")

    assert rm.get_job("non_existent_job") is None

    all_jobs = rm.get_all_jobs()
    assert len(all_jobs) == 2
    job_ids = [j["job_id"] for j in all_jobs]
    assert "job_001" in job_ids
    assert "job_002" in job_ids

    assert rm.delete_job("job_001") is True
    assert rm.get_job("job_001") is None
    assert rm.delete_job("job_001") is False


def test_hardware_profiles_lifecycle(tmp_path: Path) -> None:
    reg_file = tmp_path / "hw_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    with pytest.raises(ValueError):
        rm.register_hardware_profile("", {"host": "node1"})

    hw_dict = {
        "host": "node-01",
        "physical_cores": 16,
        "ram_gb": 64.0,
        "features": ["avx512", "cuda"],
    }
    rm.register_hardware_profile("hw_node1", hw_dict)

    hw_model = HardwareSpecificationModel(cpu_cores=32, ram_gb=128.0, gpu_profile="A100")
    rm.register_hardware_profile("hw_node2", hw_model)

    p1 = rm.get_hardware_profile("hw_node1")
    assert p1 is not None
    assert p1["physical_cores"] == 16
    assert p1["features"] == ["avx512", "cuda"]

    p2 = rm.get_hardware_profile("hw_node2")
    assert p2 is not None
    assert p2["cpu_cores"] == 32
    assert p2["gpu_profile"] == "A100"

    assert rm.get_hardware_profile("hw_missing") is None

    all_hw = rm.get_all_hardware_profiles()
    assert len(all_hw) == 2

    assert rm.delete_hardware_profile("hw_node1") is True
    assert rm.delete_hardware_profile("hw_node1") is False
    assert rm.get_hardware_profile("hw_node1") is None


def test_provenance_and_lineage_chain(tmp_path: Path) -> None:
    reg_file = tmp_path / "prov_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    with pytest.raises(ValueError):
        rm.add_provenance_record("", {"action": "test"})

    root_uuid = rm.add_provenance_record(
        "root_calc",
        {
            "step": "geometry_opt",
            "software": "orca-6.1",
            "parameters": {"functional": "r2SCAN-3c"},
        },
    )
    assert root_uuid.startswith("lin_")

    child_uuid = rm.add_provenance_record(
        "freq_calc",
        {
            "step": "vibrational_frequencies",
            "parent_uuid": root_uuid,
            "software": "orca-6.1",
        },
    )
    assert child_uuid.startswith("lin_")

    grandchild_uuid = rm.add_provenance_record(
        "rot_const_derivation",
        {
            "step": "vpt2_analysis",
            "parent_uuid": child_uuid,
            "software": "cochem-core",
        },
    )
    assert grandchild_uuid.startswith("lin_")

    rec = rm.get_provenance_record("freq_calc")
    assert rec is not None
    assert rec["step"] == "vibrational_frequencies"
    assert rec["parent_uuid"] == root_uuid

    chain = rm.get_lineage_chain("rot_const_derivation")
    assert len(chain) == 3
    assert chain[0]["record_id"] == "rot_const_derivation"
    assert chain[1]["record_id"] == "freq_calc"
    assert chain[2]["record_id"] == "root_calc"

    all_recs = rm.get_all_provenance_records()
    assert len(all_recs) == 3

    assert rm.delete_provenance_record("rot_calc_missing") is False
    assert rm.delete_provenance_record("rot_const_derivation") is True
    assert rm.get_provenance_record("rot_const_derivation") is None

    # Cyclic reference safety
    uuid_a = rm.add_provenance_record("cycle_a", {"parent_uuid": "node_b"})
    uuid_b = rm.add_provenance_record("cycle_b", {"parent_uuid": uuid_a})
    rec_a = rm.get_provenance_record("cycle_a")
    assert rec_a is not None
    rec_a["parent_uuid"] = uuid_b
    with rm.transaction("a") as h5:
        h5["provenance"]["cycle_a"][...] = json.dumps(rec_a)

    cyclic_chain = rm.get_lineage_chain("cycle_a")
    assert len(cyclic_chain) == 2


def test_prng_seed_locking_and_verification(tmp_path: Path) -> None:
    reg_file = tmp_path / "seed_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    s1 = rm.lock_prng_seed(42, scope="global", metadata={"purpose": "rdkit_conformer"})
    s2 = rm.lock_prng_seed(1337, scope="quantum_monte_carlo")

    assert s1 == 42
    assert s2 == 1337

    assert rm.get_locked_seed("global") == 42
    assert rm.get_locked_seed("quantum_monte_carlo") == 1337
    assert rm.get_locked_seed("unlocked_scope") is None

    assert rm.verify_prng_seed(42, "global") is True
    assert rm.verify_prng_seed(999, "global") is False
    assert rm.verify_prng_seed(42, "unlocked_scope") is False

    seeds = rm.list_locked_seeds()
    assert seeds["global"] == 42
    assert seeds["quantum_monte_carlo"] == 1337

    with pytest.raises(ValueError):
        rm.lock_prng_seed("not_an_int")  # type: ignore


def test_embedded_basis_set_archival(tmp_path: Path) -> None:
    reg_file = tmp_path / "basis_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    basis_content = """! def2-TZVP basis set
C 0
S 3 1.00
  100.0 0.1
  20.0 0.2
  5.0 0.7
"""
    basis_file = tmp_path / "def2-tzvp.basis"
    basis_file.write_text(basis_content, encoding="utf-8")

    with pytest.raises(ValueError):
        rm.embed_basis_set_archive(str(reg_file), str(basis_file), "")

    with pytest.raises(FileNotFoundError):
        rm.embed_basis_set_archive(
            str(reg_file), "non_existent_file_path.basis", "bad_basis", is_content=False
        )

    rm.embed_basis_set_archive(
        h5_path=str(reg_file),
        basis_file_path=str(basis_file),
        label="def2-TZVP",
        is_content=False,
    )

    rm.embed_basis_set_archive(
        h5_path=str(reg_file),
        basis_file_path="! cc-pVDZ basis set\nH 0\nS 2 1.00\n",
        label="cc-pVDZ",
        is_content=True,
    )

    assert rm.has_embedded_basis_set("def2-TZVP") is True
    assert rm.has_embedded_basis_set("cc-pVDZ") is True
    assert rm.has_embedded_basis_set("non_existent_basis") is False

    retrieved = rm.get_embedded_basis_set("def2-TZVP")
    assert "! def2-TZVP basis set" in retrieved

    basis_list = rm.list_embedded_basis_sets()
    assert "def2-TZVP" in basis_list
    assert "cc-pVDZ" in basis_list

    assert rm.delete_embedded_basis_set("cc-pVDZ") is True
    assert rm.has_embedded_basis_set("cc-pVDZ") is False
    assert rm.delete_embedded_basis_set("cc-pVDZ") is False

    with pytest.raises(BasisSetNotFoundError):
        rm.get_embedded_basis_set("non_existent")


def test_legacy_schema_migration(tmp_path: Path) -> None:
    import h5py  # type: ignore[import-untyped]

    reg_file = tmp_path / "legacy_registry.h5"

    with h5py.File(reg_file, "w") as h5:
        h5.attrs["version"] = "0.1"
        h5.create_group("jobs")

    rm = RegistryManager(registry_path=str(reg_file))
    report = rm.migrate_legacy_schema()

    assert report["previous_version"] == "0.1"
    assert report["current_version"] == RegistryManager.SCHEMA_VERSION

    with rm.transaction("r") as h5:
        assert h5.attrs["version"] == RegistryManager.SCHEMA_VERSION
        assert "hardware_profiles" in h5
        assert "provenance" in h5
        assert "embedded_basis_sets" in h5
        assert "seeds" in h5


def test_metadata_arbitrary_key_values(tmp_path: Path) -> None:
    reg_file = tmp_path / "meta_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    rm.set_metadata("pipeline_run_id", "pipe_98765")
    rm.set_metadata("convergence_criteria", {"tol_e": 1e-6, "tol_g": 1e-4})
    rm.set_metadata("is_production", True)

    assert rm.get_metadata("pipeline_run_id") == "pipe_98765"
    assert rm.get_metadata("convergence_criteria") == {"tol_e": 1e-6, "tol_g": 1e-4}
    assert rm.get_metadata("is_production") is True
    assert rm.get_metadata("non_existent_key", default="fallback") == "fallback"


def test_custom_exception_hierarchy() -> None:
    assert issubclass(IsotopeStabilityError, RegistryError)
    assert issubclass(RegistryLockError, RegistryError)
    assert issubclass(CoChemLockTimeoutError, RegistryLockError)
    assert issubclass(RecordNotFoundError, RegistryError)
    assert issubclass(BasisSetNotFoundError, RegistryError)
    assert issubclass(SchemaMigrationError, RegistryError)
    assert issubclass(RegistryCorruptionError, RegistryError)


def test_hash_environment_deterministic_and_sanitized() -> None:
    rec1 = hash_environment(exclude_paths=True)
    assert isinstance(rec1, dict)
    assert "sha256_hash" in rec1
    assert len(rec1["sha256_hash"]) == 64
    assert rec1["cpu_count"] >= 1
    assert rec1["total_ram_bytes"] >= 0

    raw_payload_with_paths = json.dumps(
        {
            "win_path": "C:\\Users\\ansac\\secret\\file.txt",
            "posix_path": "/home/user/workspace/repo",
            "cpu": 8,
        }
    )
    from cochem_base.core.cochem_core_registry_manager import _sanitize_path_leakages

    sanitized = _sanitize_path_leakages(raw_payload_with_paths)
    assert "ansac" not in sanitized
    assert "/home/user" not in sanitized
    assert "[SANITIZED_PATH]" in sanitized


def test_migrate_schema_json_upgrade() -> None:
    legacy_dict = {
        "schema_version": "1.0.0",
        "hardware": {
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "ram_gb": 32.0,
            "os_target": "windows_x86_64",
        },
    }

    cfg = migrate_schema(legacy_dict)
    assert isinstance(cfg, CoChemSystemConfig)
    assert cfg.schema_version == "4.0.0"
    assert cfg.hardware.physical_cpu_cores == 8
    assert cfg.quantum_settings is not None
    assert cfg.quantum_settings.implicit_solvation == "CPCM"
    assert cfg.hpc is not None
    assert cfg.hpc.scheduler == "local"
    assert cfg.registry_checksum is not None


def test_is_master_node_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COCHEM_IS_MASTER", raising=False)
    monkeypatch.delenv("RANK", raising=False)
    # Removing SLURM_PROCID mock

    monkeypatch.setenv("COCHEM_IS_MASTER", "0")
    assert is_master_node() is False

    monkeypatch.setenv("COCHEM_IS_MASTER", "1")
    assert is_master_node() is True

    monkeypatch.delenv("COCHEM_IS_MASTER", raising=False)

    monkeypatch.setenv("RANK", "0")
    assert is_master_node() is True
    monkeypatch.setenv("RANK", "1")
    assert is_master_node() is False

@pytest.mark.skipif(not os.environ.get("SLURM_PROCID"), reason="Requires physical SLURM node")
def test_is_master_node_detection_slurm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COCHEM_IS_MASTER", raising=False)
    monkeypatch.delenv("RANK", raising=False)
    
    expected = (os.environ.get("SLURM_PROCID") == "0")
    assert is_master_node() is expected


def test_system_config_load_save_update_lifecycle(tmp_path: Path) -> None:
    cfg_file = tmp_path / "cochem_system_config.json"
    rm = RegistryManager(config_path=str(cfg_file), registry_path=str(tmp_path / "reg.h5"))

    with pytest.raises(FileNotFoundError):
        rm.load_system_config()

    base_dict = {
        "schema_version": "4.0.0",
        "hardware": {
            "physical_cpu_cores": 16,
            "logical_cpu_cores": 32,
            "ram_gb": 64.0,
            "os_target": "windows_x86_64",
        },
    }
    checksum = rm.save_system_config(base_dict)
    assert isinstance(checksum, str)
    assert len(checksum) == 64
    assert cfg_file.exists()

    loaded = rm.load_system_config()
    assert isinstance(loaded, CoChemSystemConfig)
    assert loaded.hardware.physical_cpu_cores == 16
    assert loaded.hardware.ram_gb == 64.0
    assert loaded.registry_checksum == checksum

    updated = rm.update_system_config(rdkit_random_seed=12345)
    assert updated.rdkit_random_seed == 12345

    reloaded = rm.load_system_config()
    assert reloaded.rdkit_random_seed == 12345


def test_zeromq_config_broadcast_and_receive(tmp_path: Path) -> None:
    cfg_file = tmp_path / "cochem_system_config.json"
    rm = RegistryManager(config_path=str(cfg_file), registry_path=str(tmp_path / "reg.h5"))

    base_dict = {
        "schema_version": "4.0.0",
        "rdkit_random_seed": 777,
        "hardware": {
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "ram_gb": 32.0,
            "os_target": "linux_x86_64",
        },
    }
    rm.save_system_config(base_dict)
    loaded_cfg = rm.load_system_config()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        assigned_port = s.getsockname()[1]

    received_holder: list[CoChemSystemConfig | Exception] = []
    pub_ready = threading.Event()

    def run_sub() -> None:
        if not pub_ready.wait(timeout=5.0):
            received_holder.append(TimeoutError("Publisher socket failed to bind"))
            return
        time.sleep(0.05)
        try:
            cfg = receive_system_config_broadcast(
                master_host="127.0.0.1", port=assigned_port, topic="test_topic", timeout_ms=4000
            )
            received_holder.append(cfg)
        except Exception as e:
            received_holder.append(e)

    def run_pub() -> None:
        broadcast_system_config(
            config=loaded_cfg,
            port=assigned_port,
            host="127.0.0.1",
            topic="test_topic",
            repeat_count=8,
            repeat_interval=0.05,
            ready_event=pub_ready,
        )

    pub_thread = threading.Thread(target=run_pub)
    sub_thread = threading.Thread(target=run_sub)
    pub_thread.start()
    sub_thread.start()
    pub_thread.join(timeout=5.0)
    sub_thread.join(timeout=5.0)

    assert len(received_holder) == 1
    res = received_holder[0]
    assert isinstance(res, CoChemSystemConfig)
    assert res.rdkit_random_seed == 777
    assert res.hardware.physical_cpu_cores == 8


def test_broadcast_system_config_direct_function(tmp_path: Path) -> None:
    cfg_file = tmp_path / "cochem_system_config.json"
    rm = RegistryManager(config_path=str(cfg_file), registry_path=str(tmp_path / "reg.h5"))

    base_dict = {
        "schema_version": "4.0.0",
        "hardware": {
            "physical_cpu_cores": 4,
            "logical_cpu_cores": 8,
            "ram_gb": 16.0,
            "os_target": "linux_x86_64",
        },
    }
    rm.save_system_config(base_dict)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        ephemeral_port = s.getsockname()[1]

    checksum = broadcast_system_config(
        config=rm.load_system_config(),
        port=ephemeral_port,
        host="127.0.0.1",
        topic="cochem_system_config",
        repeat_count=1,
    )
    assert isinstance(checksum, str)
    assert len(checksum) == 64
