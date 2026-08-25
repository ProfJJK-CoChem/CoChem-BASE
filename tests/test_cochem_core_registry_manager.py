"""
Physical Unit and Integration Test Suite for CoChem Core Registry Manager (cochem_core_registry_manager.py).

Zero-Mock Mandate:
- Tests real physical files on disk via pytest tmp_path.
- Tests real threads and concurrency.
- Tests real cryptographic SHA-256 checksums and corruption detection.
- Tests real environment variable interpolation across Windows/POSIX styles (%VAR%, ${VAR}, $VAR, ~).
- Tests real Stage 0 Guardrails (RegistryMissingError, RegistryCorruptionError, RegistryParseError).
- Tests real lock re-entrancy, contention timeouts, and stale lock auto-reaping.
- Tests real schema migration via RegistryMigrator.
- Tests real active job tracking in cochem_system_config.json.
- Tests real HDF5 state registry, provenance DAGs, basis sets, PRNG seeds, and Mendeleev isotopic queries.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Any, List

import pytest
from pydantic import BaseModel, Field

from cochem_core_registry_manager import (
    AtomicFileLock,
    BasisSetNotFoundError,
    CoChemLockTimeoutError,
    IsotopeStabilityError,
    RecordNotFoundError,
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
    get_active_job,
    interpolate_env_vars,
    is_master_node,
    list_active_jobs,
    load_system_config,
    migrate_schema,
    receive_system_config_broadcast,
    register_active_job,
    remove_active_job,
    save_system_config,
    update_active_job,
    update_system_config,
)
from cochem_core_registry_schema import (
    CoChemSystemConfig,
    HardwareSchema,
    OSTarget,
    QuantumSettings,
)


class PhysicalTestJobModel(BaseModel):
    command: List[str] = Field(default_factory=lambda: ["orca", "input.inp"])
    product_class: str = "Polymer_Alpha"
    atom_count: int = 48
    converged: bool = True


class HardwareProfileModel(BaseModel):
    cpu_cores: int = 16
    ram_gb: float = 64.0
    gpu_profile: str = "RTX_4090"


# =============================================================================
# 1. EXCEPTION HIERARCHY & INVARIANTS
# =============================================================================

def test_custom_exception_hierarchy() -> None:
    """Verify all typed exceptions conform to the CoChem exception hierarchy."""
    assert issubclass(RegistryError, Exception)
    assert issubclass(RegistryLockError, RegistryError)
    assert issubclass(CoChemLockTimeoutError, RegistryLockError)
    assert issubclass(CoChemLockTimeoutError, TimeoutError)
    assert issubclass(RegistryLockTimeoutError, RegistryLockError)
    assert issubclass(RegistryMissingError, RegistryError)
    assert issubclass(RegistryMissingError, FileNotFoundError)
    assert issubclass(RegistryCorruptionError, RegistryError)
    assert issubclass(RegistryCorruptionError, ValueError)
    assert issubclass(RegistryParseError, RegistryError)
    assert issubclass(RegistryParseError, ValueError)
    assert issubclass(RecordNotFoundError, RegistryError)
    assert issubclass(BasisSetNotFoundError, RegistryError)
    assert issubclass(SchemaMigrationError, RegistryError)
    assert issubclass(IsotopeStabilityError, RegistryError)


# =============================================================================
# 2. ATOMIC FILE LOCKING: LIFECYCLE, RE-ENTRANCY, CONTENTION, STALE REAPING
# =============================================================================

def test_atomic_file_lock_clean_lifecycle(tmp_path: Path) -> None:
    """Test standard atomic lock acquisition, context manager entry, and cleanup on exit."""
    lock_file = tmp_path / "resource.lock"

    assert not lock_file.exists()
    with AtomicFileLock(lock_file, timeout=2.0) as lock:
        assert lock_file.exists()
        assert lock._is_locked is True
        # Verify content written inside lock file
        content = lock_file.read_text(encoding="utf-8")
        assert f"{os.getpid()}:" in content

    assert not lock_file.exists()
    assert lock._is_locked is False


def test_atomic_file_lock_reentrancy_same_thread(tmp_path: Path) -> None:
    """Verify thread-local re-entrancy on the same instance and different instances on same thread."""
    lock_file = tmp_path / "reentrant.lock"

    # Same instance nested
    lock = AtomicFileLock(lock_file, timeout=2.0)
    with lock:
        assert lock_file.exists()
        with lock:
            assert lock_file.exists()
            with lock:
                assert lock_file.exists()
            assert lock_file.exists()
        assert lock_file.exists()
    assert not lock_file.exists()

    # Separate instances targeting same path on same thread
    l1 = AtomicFileLock(lock_file, timeout=2.0)
    l2 = AtomicFileLock(lock_file, timeout=2.0)
    with l1:
        assert lock_file.exists()
        with l2:
            assert lock_file.exists()
        assert lock_file.exists()
    assert not lock_file.exists()


def test_atomic_file_lock_contention_and_timeout(tmp_path: Path) -> None:
    """Verify lock contention between different threads raises CoChemLockTimeoutError."""
    lock_file = tmp_path / "contend.lock"

    lock1 = AtomicFileLock(lock_file, timeout=5.0)
    lock1.acquire()
    assert lock_file.exists()

    err_holder: List[Exception] = []

    def thread_target() -> None:
        try:
            lock2 = AtomicFileLock(lock_file, timeout=0.1)
            lock2.acquire()
        except Exception as exc:
            err_holder.append(exc)

    t = threading.Thread(target=thread_target)
    t.start()
    t.join()

    assert len(err_holder) == 1
    assert isinstance(err_holder[0], CoChemLockTimeoutError)
    assert isinstance(err_holder[0], RegistryLockError)

    # Release first lock, new thread should now succeed
    lock1.release()
    assert not lock_file.exists()

    lock3 = AtomicFileLock(lock_file, timeout=1.0)
    assert lock3.acquire() is True
    lock3.release()


def test_atomic_file_lock_stale_lock_auto_reaping(tmp_path: Path) -> None:
    """Verify stale lock files older than stale_timeout are automatically reaped."""
    lock_file = tmp_path / "stale.lock"
    lock_file.write_text("99999:000:0\n", encoding="utf-8")

    # Set mtime to 300 seconds in the past
    past_time = time.time() - 300
    os.utime(lock_file, (past_time, past_time))

    # Acquisition with stale_timeout=1.0 should reap the lock
    lock = AtomicFileLock(lock_file, timeout=2.0, stale_timeout=1.0)
    assert lock.acquire() is True
    assert lock_file.exists()
    lock.release()
    assert not lock_file.exists()


# =============================================================================
# 3. ATOMIC JSON WRITING
# =============================================================================

def test_atomic_write_json_clean_execution(tmp_path: Path) -> None:
    """Verify atomic JSON writing produces clean output and leaves no temporary files behind."""
    out_file = tmp_path / "atomic_test.json"
    payload = {
        "project": "CoChem-BASE",
        "version": "4.0.0",
        "threads": 16,
        "active": True,
    }

    atomic_write_json(out_file, payload)
    assert out_file.exists()

    # Verify no tmp files in directory
    files_in_dir = list(tmp_path.iterdir())
    assert len(files_in_dir) == 1
    assert files_in_dir[0] == out_file

    # Verify JSON content
    read_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert read_data == payload


def test_atomic_write_json_with_pydantic_model(tmp_path: Path) -> None:
    """Verify atomic_write_json directly accepts Pydantic models."""
    out_file = tmp_path / "model_test.json"
    model = PhysicalTestJobModel(product_class="Polymer_Beta", atom_count=96)

    atomic_write_json(out_file, model)
    assert out_file.exists()

    read_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert read_data["product_class"] == "Polymer_Beta"
    assert read_data["atom_count"] == 96
    assert read_data["converged"] is True


# =============================================================================
# 4. ENVIRONMENT VARIABLE INTERPOLATION (${VAR}, $VAR, %VAR%, ~)
# =============================================================================

def test_interpolate_env_vars_all_syntaxes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify interpolation handles ${VAR}, $VAR, %VAR%, and home directory across OSs."""
    monkeypatch.setenv("COCHEM_BIN_DIR", "opt/cochem/bin")
    monkeypatch.setenv("COCHEM_SCRATCH_DIR", "tmp/scratch")
    monkeypatch.setenv("COCHEM_MAX_CORES", "32")

    # String with ${VAR}
    assert interpolate_env_vars("${COCHEM_BIN_DIR}/orca") == "opt/cochem/bin/orca"

    # String with $VAR
    assert interpolate_env_vars("$COCHEM_SCRATCH_DIR/job_1") == "tmp/scratch/job_1"

    # String with %VAR% (Windows style)
    assert interpolate_env_vars("%COCHEM_BIN_DIR%/xtb") == "opt/cochem/bin/xtb"

    # Combined strings
    combined = "${COCHEM_BIN_DIR}/mpirun -n %COCHEM_MAX_CORES% $COCHEM_SCRATCH_DIR"
    assert interpolate_env_vars(combined) == "opt/cochem/bin/mpirun -n 32 tmp/scratch"

    # Unset env vars should remain uncorrupted
    assert interpolate_env_vars("${UNSET_VARIABLE_XYZ}/test") == "${UNSET_VARIABLE_XYZ}/test"
    assert interpolate_env_vars("%UNSET_VARIABLE_XYZ%/test") == "%UNSET_VARIABLE_XYZ%/test"

    # Dictionary input
    dict_payload = {
        "orca_path": "${COCHEM_BIN_DIR}/orca",
        "scratch": "$COCHEM_SCRATCH_DIR",
        "cores": "%COCHEM_MAX_CORES%",
        "nested": {
            "path": "${COCHEM_BIN_DIR}/tools",
            "list_paths": ["${COCHEM_BIN_DIR}/1", "$COCHEM_SCRATCH_DIR/2"],
        },
    }
    interpolated_dict = interpolate_env_vars(dict_payload)
    assert interpolated_dict["orca_path"] == "opt/cochem/bin/orca"
    assert interpolated_dict["scratch"] == "tmp/scratch"
    assert interpolated_dict["cores"] == "32"
    assert interpolated_dict["nested"]["path"] == "opt/cochem/bin/tools"
    assert interpolated_dict["nested"]["list_paths"] == ["opt/cochem/bin/1", "tmp/scratch/2"]


# =============================================================================
# 5. STAGE 0 GUARDRAILS: MISSING, CORRUPTED CHECKSUM, AND UNPARSEABLE JSON
# =============================================================================

def test_stage_0_guardrail_missing_registry_raises_registry_missing_error(tmp_path: Path) -> None:
    """Stage 0 Guardrail: load_system_config MUST halt gracefully on non-existent config file."""
    non_existent = tmp_path / "missing_config.json"
    with pytest.raises(RegistryMissingError) as exc_info:
        load_system_config(non_existent)

    assert issubclass(RegistryMissingError, FileNotFoundError)
    assert "Stage 0 Guardrail: Master registry not found" in str(exc_info.value)


def test_stage_0_guardrail_unparseable_json_raises_registry_parse_error(tmp_path: Path) -> None:
    """Stage 0 Guardrail: load_system_config MUST raise RegistryParseError on malformed JSON."""
    bad_json_file = tmp_path / "corrupted.json"
    bad_json_file.write_text("{'invalid_json': True, missing_quotes}", encoding="utf-8")

    with pytest.raises(RegistryParseError) as exc_info:
        load_system_config(bad_json_file)

    assert issubclass(RegistryParseError, ValueError)
    assert "Stage 0 Guardrail: Unparseable registry JSON" in str(exc_info.value)


def test_stage_0_guardrail_non_object_root_raises_registry_parse_error(tmp_path: Path) -> None:
    """Stage 0 Guardrail: load_system_config MUST raise RegistryParseError if JSON root is not an object."""
    array_file = tmp_path / "array.json"
    array_file.write_text(json.dumps(["item1", "item2"]), encoding="utf-8")

    with pytest.raises(RegistryParseError) as exc_info:
        load_system_config(array_file)

    assert "Registry root must be a JSON object" in str(exc_info.value)


def test_stage_0_guardrail_corrupted_checksum_raises_registry_corruption_error(tmp_path: Path) -> None:
    """Stage 0 Guardrail: Tampered payload with mismatched checksum MUST raise RegistryCorruptionError."""
    cfg_file = tmp_path / "tampered_config.json"

    # Create a valid config model
    valid_cfg = CoChemSystemConfig(
        hardware=HardwareSchema(
            physical_cpu_cores=8,
            logical_cpu_cores=16,
            ram_gb=32.0,
            os_target=OSTarget.LOCAL_LINUX,
        ),
        quantum_settings=QuantumSettings(implicit_solvation="CPCM"),
    )
    save_system_config(valid_cfg, cfg_file)
    assert cfg_file.exists()

    # Read the raw JSON and tamper with a value while preserving original checksum
    raw_dict = json.loads(cfg_file.read_text(encoding="utf-8"))
    original_checksum = raw_dict["registry_checksum"]
    raw_dict["hardware"]["ram_gb"] = 128.0  # Tampering with RAM bounds
    raw_dict["registry_checksum"] = original_checksum  # Deliberately stale/spoofed checksum
    cfg_file.write_text(json.dumps(raw_dict, indent=2), encoding="utf-8")

    # Loading with verify_integrity=True MUST raise RegistryCorruptionError
    with pytest.raises(RegistryCorruptionError) as exc_info:
        load_system_config(cfg_file, verify_integrity=True)

    assert issubclass(RegistryCorruptionError, ValueError)
    assert "Stage 0 Guardrail: Registry corruption" in str(exc_info.value)

    # Loading with verify_integrity=False should allow recovery/inspection
    bypassed_cfg = load_system_config(cfg_file, verify_integrity=False)
    assert bypassed_cfg.hardware.ram_gb == 128.0


# =============================================================================
# 6. CONFIG SAVE, UPDATE, AND CHECKSUM INJECTION
# =============================================================================

def test_system_config_save_injects_valid_sha256_checksum(tmp_path: Path) -> None:
    """Verify saving a config automatically calculates and writes the SHA-256 checksum."""
    cfg_file = tmp_path / "cochem_system_config.json"

    payload = {
        "schema_version": "4.0.0",
        "hardware": {
            "physical_cpu_cores": 12,
            "logical_cpu_cores": 24,
            "ram_gb": 64.0,
            "os_target": "windows_x86_64",
        },
        "quantum_settings": {
            "implicit_solvation": "CPCM",
            "integration_grid": "defgrid2",
        },
    }

    checksum = save_system_config(payload, cfg_file)
    assert isinstance(checksum, str)
    assert len(checksum) == 64

    # Verify checksum matches disk payload
    loaded = load_system_config(cfg_file, verify_integrity=True)
    assert loaded.registry_checksum == checksum
    assert loaded.verify_checksum() is True
    assert loaded.hardware.physical_cpu_cores == 12


def test_system_config_update_atomically_updates_and_recalculates_checksum(tmp_path: Path) -> None:
    """Verify update_system_config modifies fields and updates checksum atomically."""
    cfg_file = tmp_path / "cochem_system_config.json"

    payload = {
        "schema_version": "4.0.0",
        "rdkit_random_seed": 42,
        "hardware": {
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "ram_gb": 32.0,
            "os_target": "windows_x86_64",
        },
    }
    initial_checksum = save_system_config(payload, cfg_file)

    # Perform atomic update
    updated_cfg = update_system_config(
        config_path=cfg_file,
        rdkit_random_seed=9999,
        orca_version="6.1.2",
    )

    assert updated_cfg.rdkit_random_seed == 9999
    assert updated_cfg.orca_version == "6.1.2"
    assert updated_cfg.registry_checksum != initial_checksum
    assert updated_cfg.verify_checksum() is True

    # Reload from disk to ensure persistence
    reloaded = load_system_config(cfg_file, verify_integrity=True)
    assert reloaded.rdkit_random_seed == 9999
    assert reloaded.orca_version == "6.1.2"


# =============================================================================
# 7. SCHEMA MIGRATION VIA REGISTRY MIGRATOR
# =============================================================================

def test_schema_migration_flat_to_nested_structure(tmp_path: Path) -> None:
    """Verify legacy flat dictionaries are migrated to rigid nested 4.0.0 schemas."""
    orca_abs = str((tmp_path / "orca").resolve())
    xtb_abs = str((tmp_path / "xtb").resolve())
    art_abs = str((tmp_path / "artifacts").resolve())

    legacy_flat_dict = {
        "schema_version": "1.0.0",
        "physical_cpu_cores": 16,
        "logical_cpu_cores": 32,
        "ram_gb": 64.0,
        "os_target": "local-linux",
        "orca_path": orca_abs,
        "xtb_path": xtb_abs,
        "artifacts_dir": art_abs,
    }

    migrated = migrate_schema(legacy_flat_dict)
    assert isinstance(migrated, CoChemSystemConfig)
    assert migrated.schema_version == "4.0.0"
    assert migrated.hardware.physical_cpu_cores == 16
    assert migrated.hardware.logical_cpu_cores == 32
    assert migrated.hardware.ram_gb == 64.0
    assert migrated.hardware.os_target == OSTarget.LOCAL_LINUX
    assert migrated.silo_paths.orca_path == orca_abs
    assert migrated.silo_paths.xtb_path == xtb_abs
    assert migrated.environment.artifacts_dir == art_abs
    assert migrated.quantum_settings is not None
    assert migrated.quantum_settings.integration_grid == "defgrid2"
    assert migrated.hpc.scheduler == "local"


# =============================================================================
# 8. ACTIVE JOBS MANAGEMENT IN SYSTEM CONFIG
# =============================================================================

def test_active_jobs_registration_lifecycle(tmp_path: Path) -> None:
    """Verify register_active_job, get_active_job, list_active_jobs, update_active_job, and remove_active_job."""
    cfg_file = tmp_path / "cochem_system_config.json"
    init_cfg = CoChemSystemConfig.create_default()
    save_system_config(init_cfg, cfg_file)

    # 1. Register active jobs
    job1_payload = {
        "engine": "orca",
        "calc_type": "ts_optimization",
        "status": "running",
        "pid": 12345,
    }
    register_active_job("job_orca_001", job1_payload, config_path=cfg_file)

    job2_model = PhysicalTestJobModel(product_class="Polymer_Gamma", atom_count=32)
    register_active_job("job_orca_002", job2_model, config_path=cfg_file)

    # 2. Get active job
    retrieved_1 = get_active_job("job_orca_001", config_path=cfg_file)
    assert retrieved_1 is not None
    assert retrieved_1["engine"] == "orca"
    assert retrieved_1["status"] == "running"
    assert "registered_at" in retrieved_1

    retrieved_2 = get_active_job("job_orca_002", config_path=cfg_file)
    assert retrieved_2 is not None
    assert retrieved_2["product_class"] == "Polymer_Gamma"

    # Non-existent job
    assert get_active_job("non_existent_job", config_path=cfg_file) is None

    # 3. List active jobs
    all_active = list_active_jobs(config_path=cfg_file)
    assert len(all_active) == 2
    assert "job_orca_001" in all_active
    assert "job_orca_002" in all_active

    # 4. Update active job
    updated_rec = update_active_job(
        "job_orca_001",
        status="completed",
        config_path=cfg_file,
        return_code=0,
        energy=-245.1234,
    )
    assert updated_rec["status"] == "completed"
    assert updated_rec["return_code"] == 0
    assert updated_rec["energy"] == -245.1234
    assert "updated_at" in updated_rec

    # Update non-existent job raises RecordNotFoundError
    with pytest.raises(RecordNotFoundError):
        update_active_job("missing_job", status="failed", config_path=cfg_file)

    # 5. Remove active job
    assert remove_active_job("job_orca_001", config_path=cfg_file) is True
    assert get_active_job("job_orca_001", config_path=cfg_file) is None
    assert remove_active_job("job_orca_001", config_path=cfg_file) is False

    remaining_jobs = list_active_jobs(config_path=cfg_file)
    assert len(remaining_jobs) == 1
    assert "job_orca_002" in remaining_jobs


# =============================================================================
# 9. THREAD SAFETY & CONCURRENT UPDATES
# =============================================================================

def test_multithreaded_concurrent_system_config_updates(tmp_path: Path) -> None:
    """Verify thread safety under heavy concurrent multithreaded updates."""
    cfg_file = tmp_path / "cochem_system_config.json"
    init_cfg = CoChemSystemConfig.create_default()
    save_system_config(init_cfg, cfg_file)

    num_threads = 4
    jobs_per_thread = 3
    exceptions: List[Exception] = []

    def worker_task(thread_idx: int) -> None:
        try:
            for j in range(jobs_per_thread):
                job_id = f"t{thread_idx}_j{j}"
                register_active_job(
                    job_id,
                    {"thread": thread_idx, "job": j, "status": "running"},
                    config_path=cfg_file,
                )
                time.sleep(0.01)
                update_active_job(
                    job_id,
                    status="finished",
                    config_path=cfg_file,
                    progress=100.0,
                )
        except Exception as exc:
            exceptions.append(exc)

    threads = [threading.Thread(target=worker_task, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(exceptions) == 0

    # Verify final integrity and that all jobs exist
    final_cfg = load_system_config(cfg_file, verify_integrity=True)
    assert len(final_cfg.active_jobs) == num_threads * jobs_per_thread
    for thread_idx in range(num_threads):
        for j in range(jobs_per_thread):
            job_id = f"t{thread_idx}_j{j}"
            assert job_id in final_cfg.active_jobs
            assert final_cfg.active_jobs[job_id]["status"] == "finished"


# =============================================================================
# 10. HDF5 STATE REGISTRY MANAGER OPERATIONS
# =============================================================================

def test_registry_manager_hdf5_lifecycle(tmp_path: Path) -> None:
    """Verify HDF5 RegistryManager initialization, stats, transactions, and group creation."""
    reg_file = tmp_path / "test_reg.h5"
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

    # Arbitrary metadata
    rm.set_metadata("cluster_env", "hpc_slurm")
    rm.set_metadata("tolerances", {"scf_e": 1e-8, "scf_grad": 1e-6})
    assert rm.get_metadata("cluster_env") == "hpc_slurm"
    assert rm.get_metadata("tolerances") == {"scf_e": 1e-8, "scf_grad": 1e-6}
    assert rm.get_metadata("non_existent", default=42) == 42


def test_registry_manager_hardware_profiles_and_provenance(tmp_path: Path) -> None:
    """Verify hardware profile storage and provenance DAG lineage chain tracing with cycle detection."""
    reg_file = tmp_path / "hw_prov_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    # Hardware profile
    hw_model = HardwareProfileModel(cpu_cores=64, ram_gb=256.0, gpu_profile="A100_80GB")
    rm.register_hardware_profile("node_01", hw_model)
    retrieved_hw = rm.get_hardware_profile("node_01")
    assert retrieved_hw is not None
    assert retrieved_hw["cpu_cores"] == 64
    assert retrieved_hw["gpu_profile"] == "A100_80GB"

    # Provenance DAG
    root_uuid = rm.add_provenance_record("step_1_conformers", {"method": "rdkit_etkdg"})
    step2_uuid = rm.add_provenance_record("step_2_dft_opt", {"method": "r2scan_3c", "parent_uuid": root_uuid})
    step3_uuid = rm.add_provenance_record("step_3_freq", {"method": "num_freq", "parent_uuid": step2_uuid})
    assert step3_uuid.startswith("lin_")

    chain = rm.get_lineage_chain("step_3_freq")
    assert len(chain) == 3
    assert chain[0]["record_id"] == "step_3_freq"
    assert chain[1]["record_id"] == "step_2_dft_opt"
    assert chain[2]["record_id"] == "step_1_conformers"


def test_registry_manager_prng_seeds_and_basis_sets(tmp_path: Path) -> None:
    """Verify PRNG seed locking and embedded basis set archival to prevent link rot."""
    reg_file = tmp_path / "seed_basis_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    # PRNG seed locking
    s = rm.lock_prng_seed(12345, scope="global", metadata={"stage": "docking"})
    assert s == 12345
    assert rm.get_locked_seed("global") == 12345
    assert rm.verify_prng_seed(12345, "global") is True
    assert rm.verify_prng_seed(99999, "global") is False

    # Basis set archival
    basis_raw = "! def2-QZVP\nC 0\nS 4 1.00\n  200.0 0.05\n  40.0 0.15\n"
    rm.embed_basis_set_archive(label="def2-QZVP", basis_file_path=basis_raw, is_content=True)

    assert rm.has_embedded_basis_set("def2-QZVP") is True
    retrieved_basis = rm.get_embedded_basis_set("def2-QZVP")
    assert "! def2-QZVP" in retrieved_basis

    with pytest.raises(BasisSetNotFoundError):
        rm.get_embedded_basis_set("missing_basis_label")


# =============================================================================
# 11. DYNAMIC ISOTOPIC MASS QUERIES (MENDELEEV / QCELEMENTAL)
# =============================================================================

def test_mendeleev_dynamic_isotopic_mass_queries() -> None:
    """Verify isotopic mass resolution for standard elements, explicit isotopes, and aliases."""
    # Standard Carbon and Hydrogen
    mass_c = RegistryManager.get_isotopic_mass("C")
    assert isinstance(mass_c, float)
    assert 12.00 <= mass_c <= 12.02

    mass_h = RegistryManager.get_isotopic_mass("H")
    assert isinstance(mass_h, float)
    assert 1.007 <= mass_h <= 1.009

    # Explicit isotopes
    mass_c13 = RegistryManager.get_isotopic_mass("C", 13)
    assert 13.003 <= mass_c13 <= 13.004

    mass_h2 = RegistryManager.get_isotopic_mass("H", 2)
    assert 2.014 <= mass_h2 <= 2.015

    # Deuterium and Tritium aliases
    mass_d = RegistryManager.get_isotopic_mass("D")
    assert 2.014 <= mass_d <= 2.015
    mass_t = RegistryManager.get_isotopic_mass("T")
    assert 3.015 <= mass_t <= 3.017

    # Error handling
    with pytest.raises(ValueError):
        RegistryManager.get_isotopic_mass("")

    with pytest.raises(IsotopeStabilityError):
        RegistryManager.get_isotopic_mass("NonExistentElementX999")


# =============================================================================
# 12. ENVIRONMENT DETECTION & ZEROMQ BROADCAST
# =============================================================================

def test_is_master_node_multi_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify is_master_node correctly inspects Slurm, MPI, and environment overrides."""
    # Default standalone
    monkeypatch.delenv("COCHEM_IS_MASTER", raising=False)
    monkeypatch.delenv("RANK", raising=False)

    # Explicit override
    monkeypatch.setenv("COCHEM_IS_MASTER", "0")
    assert is_master_node() is False
    monkeypatch.setenv("COCHEM_IS_MASTER", "1")
    assert is_master_node() is True

    monkeypatch.delenv("COCHEM_IS_MASTER", raising=False)
    
    # MPI rank
    monkeypatch.setenv("RANK", "0")
    assert is_master_node() is True
    monkeypatch.setenv("RANK", "1")
    assert is_master_node() is False

@pytest.mark.skipif(not os.environ.get("SLURM_PROCID"), reason="Requires physical SLURM allocation")
def test_is_master_node_slurm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COCHEM_IS_MASTER", raising=False)
    monkeypatch.delenv("RANK", raising=False)
    expected = (os.environ.get("SLURM_PROCID") == "0")
    assert is_master_node() is expected

def test_zeromq_broadcast_and_receive(tmp_path: Path) -> None:
    """Verify master node ZeroMQ broadcast and worker node subscriber reception."""
    cfg_file = tmp_path / "cochem_system_config.json"
    rm = RegistryManager(config_path=str(cfg_file), registry_path=str(tmp_path / "reg.h5"))

    payload = {
        "schema_version": "4.0.0",
        "rdkit_random_seed": 8888,
        "hardware": {
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "ram_gb": 32.0,
            "os_target": "linux_x86_64",
        },
    }
    rm.save_system_config(payload)
    cfg_to_broadcast = rm.load_system_config()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    received_list: List[Any] = []
    pub_ready = threading.Event()

    def subscriber_worker() -> None:
        if not pub_ready.wait(timeout=5.0):
            received_list.append(TimeoutError("Publisher socket failed to bind"))
            return
        time.sleep(0.05)
        try:
            recv_cfg = receive_system_config_broadcast(
                master_host="127.0.0.1", port=port, topic="cochem_system_config", timeout_ms=4000
            )
            received_list.append(recv_cfg)
        except Exception as exc:
            received_list.append(exc)

    def publisher_worker() -> None:
        broadcast_system_config(
            config=cfg_to_broadcast,
            port=port,
            host="127.0.0.1",
            topic="cochem_system_config",
            repeat_count=8,
            repeat_interval=0.05,
            ready_event=pub_ready,
        )

    sub_t = threading.Thread(target=subscriber_worker)
    pub_t = threading.Thread(target=publisher_worker)
    sub_t.start()
    pub_t.start()
    sub_t.join(timeout=5.0)
    pub_t.join(timeout=5.0)

    assert len(received_list) == 1
    received_cfg = received_list[0]
    assert isinstance(received_cfg, CoChemSystemConfig)
    assert received_cfg.rdkit_random_seed == 8888
    assert received_cfg.hardware.physical_cpu_cores == 8
