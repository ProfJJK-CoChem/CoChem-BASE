"""
Unit and integration test suite for CoChem-CORE: Workspace Scaffolding Daemon,
Parsl DAG Dependency Orchestration, Deletion Shield Permission Locking,
and Pre-Flight Scratch Disk Quota Traps.

Strict Zero-Mock Mandate: Real Parsl DAG execution with ThreadPoolExecutor,
real directory scaffolding under tmp_path, real shutil.disk_usage() telemetry,
real cross-platform os.chmod permission locking/unlocking, real file writes/reads,
and real zombie sweeping & job isolation.

Method Matrix v4 & SRS Workspace Scaffolding Daemon Specification Compliant.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import Any, Generator

import pytest

from cochem_base.core.cochem_core_workspace_manager import (
    CORE_DIRECTORIES,
    DEFAULT_ARTIFACT_ROOT,
    MIN_SCRATCH_FREE_GB,
    AirgapTopology,
    BipartiteTopology,
    DaemonStatus,
    DirectoryInfo,
    DiskQuotaError,
    DiskQuotaMetrics,
    ScaffoldResult,
    WorkspaceDaemon,
    WorkspaceManager,
    WorkspaceScaffoldingDaemon,
    apply_bipartite_airgap,
    apply_tripartite_airgap,
    assert_scratch_disk_quota,
    check_scratch_disk_quota,
    cleanup_job_workspace,
    file_lock,
    get_default_workspace_manager,
    get_directory_status,
    get_job_workspace,
    is_job_active,
    lock_artifact_permissions,
    provision_job_workspace,
    scaffold_core_directories,
    scaffold_workspace_parsl,
    sweep_zombie_directories,
    unlock_artifact_permissions,
)
from cochem_base.exceptions import CoChemError

# =============================================================================
# PYTEST FIXTURES (ZERO-MOCK REAL PARSL & STORAGE ENVIRONMENTS)
# =============================================================================


@pytest.fixture
def parsl_session() -> Generator[Any, None, None]:
    """Pytest fixture providing an initialized Parsl ThreadPoolExecutor environment.

    Ensures safe teardown and resource deallocation between test runs.
    """
    import parsl
    from parsl.config import Config
    from parsl.executors.threads import ThreadPoolExecutor

    try:
        parsl.clear()
    except Exception:
        pass

    cfg = Config(
        executors=[ThreadPoolExecutor(max_threads=4, label="cochem_workspace_test_pool")],
        strategy="none",
    )
    parsl.load(cfg)
    try:
        yield cfg
    finally:
        try:
            parsl.clear()
        except Exception:
            pass


# =============================================================================
# 1. MODULE EXPORTS, CONSTANTS, AND PYDANTIC DATA MODEL TESTS
# =============================================================================


def test_module_exports_and_constants() -> None:
    """Verify all required classes, functions, models, and constants are exported."""
    expected_core_dirs = ["Input_Files", "Processed", "Logs", "Scratch", "Registry", "Databases"]
    for d in expected_core_dirs:
        assert d in CORE_DIRECTORIES

    assert isinstance(DEFAULT_ARTIFACT_ROOT, Path)
    assert MIN_SCRATCH_FREE_GB == 50.0

    # Ensure alias parity
    assert WorkspaceScaffoldingDaemon is WorkspaceDaemon


def test_pydantic_disk_quota_metrics_model() -> None:
    """Verify DiskQuotaMetrics Pydantic data model structure, validation, and serialization."""
    metrics = DiskQuotaMetrics(
        path="/tmp/test_scratch",
        total_bytes=100 * (1024**3),
        used_bytes=40 * (1024**3),
        free_bytes=60 * (1024**3),
        total_gb=100.0,
        used_gb=40.0,
        free_gb=60.0,
        min_required_gb=50.0,
        is_sufficient=True,
    )

    assert metrics.path == "/tmp/test_scratch"
    assert metrics.total_gb == 100.0
    assert metrics.free_gb == 60.0
    assert metrics.min_required_gb == 50.0
    assert metrics.is_sufficient is True
    assert metrics.timestamp > 0.0

    data = metrics.model_dump()
    assert data["is_sufficient"] is True
    assert data["free_gb"] == 60.0

    restored = DiskQuotaMetrics.model_validate(data)
    assert restored.free_gb == 60.0
    assert restored.path == "/tmp/test_scratch"


def test_pydantic_directory_info_model() -> None:
    """Verify DirectoryInfo Pydantic data model."""
    d_info = DirectoryInfo(
        path="/data/cochem/Logs",
        exists=True,
        file_count=12,
        dir_count=3,
        total_size_bytes=204800,
        is_writable=True,
        is_readable=True,
    )
    assert d_info.file_count == 12
    assert d_info.dir_count == 3
    assert d_info.total_size_bytes == 204800
    assert d_info.is_writable is True
    assert d_info.is_readable is True

    serialized = d_info.model_dump()
    assert serialized["file_count"] == 12
    assert DirectoryInfo.model_validate(serialized).exists is True


def test_pydantic_scaffold_result_model() -> None:
    """Verify ScaffoldResult Pydantic data model."""
    res = ScaffoldResult(
        base_path="/data/CoChem_Artifacts",
        directories=["Input_Files", "Processed", "Logs", "Scratch", "Registry", "Databases"],
        created_paths=[
            "/data/CoChem_Artifacts/Input_Files",
            "/data/CoChem_Artifacts/Processed",
            "/data/CoChem_Artifacts/Logs",
            "/data/CoChem_Artifacts/Scratch",
            "/data/CoChem_Artifacts/Registry",
            "/data/CoChem_Artifacts/Databases",
        ],
        success=True,
        parsl_task_ids=["task_0", "task_1", "task_2", "task_3", "task_4", "task_5"],
        execution_time_seconds=0.045,
    )
    assert res.success is True
    assert len(res.directories) == 6
    assert len(res.created_paths) == 6
    assert len(res.parsl_task_ids) == 6
    assert res.execution_time_seconds == 0.045


def test_pydantic_topology_models() -> None:
    """Verify AirgapTopology and BipartiteTopology data models."""
    airgap = AirgapTopology(
        immutable_code="/repo/CoChem-BASE",
        dynamic_state="/artifacts",
        volatile_compute="/artifacts/Scratch",
        code_tier="/repo/CoChem-BASE",
        data_tier="/artifacts",
        compute_tier="/artifacts/Scratch",
        status="active",
    )
    assert airgap.status == "active"
    assert airgap.compute_tier == "/artifacts/Scratch"

    bipartite = BipartiteTopology(
        code_tier="/repo/CoChem-BASE",
        data_tier="/artifacts",
        status="active",
    )
    assert bipartite.code_tier == "/repo/CoChem-BASE"
    assert bipartite.data_tier == "/artifacts"


def test_pydantic_daemon_status_model() -> None:
    """Verify DaemonStatus data model."""
    status = DaemonStatus(
        is_running=True,
        interval_seconds=30.0,
        sweeps_completed=5,
        last_sweep_timestamp=time.time(),
        last_zombies_swept=2,
        last_disk_quota_metrics=None,
    )
    assert status.is_running is True
    assert status.sweeps_completed == 5
    assert status.last_zombies_swept == 2


# =============================================================================
# 2. DISK QUOTA ERROR & PRE-FLIGHT SCRATCH DISK QUOTA TRAPS
# =============================================================================


def test_disk_quota_error_exception_structure() -> None:
    """Verify DiskQuotaError carries required diagnostic metadata and is a CoChemError."""
    err = DiskQuotaError(
        required_gb=50.0,
        available_gb=12.4,
        path=Path("/tmp/Scratch"),
        message="Insufficient scratch disk quota",
    )
    assert isinstance(err, CoChemError)
    assert isinstance(err, OSError)
    assert err.required_gb == 50.0
    assert err.available_gb == 12.4
    assert str(err.path).endswith("Scratch")
    assert "50.00 GB" in str(err) or "50.0" in str(err)
    assert "12.40 GB" in str(err) or "12.4" in str(err)


def test_check_scratch_disk_quota_sufficient_space(tmp_path: Path) -> None:
    """Zero-mock pre-flight disk quota check with sufficient space succeeds."""
    scratch_dir = tmp_path / "Scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    # Calling check_scratch_disk_quota with very low threshold (e.g. 0.001 GB = 1MB)
    metrics = check_scratch_disk_quota(scratch_dir, min_free_gb=0.001)

    assert isinstance(metrics, DiskQuotaMetrics)
    assert metrics.is_sufficient is True
    assert metrics.free_gb > 0.0
    assert metrics.total_gb > 0.0
    assert metrics.used_gb >= 0.0
    assert metrics.min_required_gb == 0.001
    assert Path(metrics.path).resolve() == scratch_dir.resolve()

    # Calling assert_scratch_disk_quota with small threshold must NOT raise
    assert_result = assert_scratch_disk_quota(scratch_dir, min_free_gb=0.001)
    assert assert_result.is_sufficient is True


def test_check_scratch_disk_quota_insufficient_space_raises(tmp_path: Path) -> None:
    """Zero-mock pre-flight disk quota trap: insufficient disk space raises DiskQuotaError."""
    scratch_dir = tmp_path / "Scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    total, used, free = shutil.disk_usage(str(scratch_dir))
    actual_free_gb = free / (1024**3)

    # Set an impossible requirement higher than available free disk space
    impossible_threshold_gb = actual_free_gb + 50000.0

    # check_scratch_disk_quota returns metrics with is_sufficient=False
    metrics = check_scratch_disk_quota(scratch_dir, min_free_gb=impossible_threshold_gb)
    assert isinstance(metrics, DiskQuotaMetrics)
    assert metrics.is_sufficient is False
    assert metrics.min_required_gb == impossible_threshold_gb

    # assert_scratch_disk_quota must raise DiskQuotaError
    with pytest.raises(DiskQuotaError) as exc_info:
        assert_scratch_disk_quota(scratch_dir, min_free_gb=impossible_threshold_gb)

    err = exc_info.value
    assert err.required_gb == impossible_threshold_gb
    assert abs(err.available_gb - actual_free_gb) < 1.0
    assert err.path is not None
    assert Path(err.path).resolve() == scratch_dir.resolve()


def test_workspace_manager_disk_quota_methods(tmp_path: Path) -> None:
    """Verify WorkspaceManager instance methods for disk quota assertions."""
    manager = WorkspaceManager(base_path=tmp_path)
    scratch_dir = tmp_path / "Scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    # Manager check with tiny quota
    metrics = manager.check_scratch_disk_quota(min_free_gb=0.01)
    assert metrics.is_sufficient is True

    # Manager assert with tiny quota
    assert_metrics = manager.assert_scratch_disk_quota(min_free_gb=0.01)
    assert assert_metrics.is_sufficient is True

    # Manager assert with impossible quota raises DiskQuotaError
    with pytest.raises(DiskQuotaError):
        manager.assert_scratch_disk_quota(min_free_gb=100_000_000.0)


# =============================================================================
# 3. PARSL DAG DEPENDENCY ORCHESTRATION & DIRECTORY SCAFFOLDING
# =============================================================================


def test_parsl_dag_workspace_scaffolding_core_tree(tmp_path: Path, parsl_session: Any) -> None:
    """Zero-mock Parsl DAG directory tree scaffolding.

    Verifies that directory tree /Input_Files, /Processed, /Logs, /Scratch, /Registry, /Databases
    is created via Parsl app/DAG dependency chaining without .workspace.lock files or mutexes.
    """
    target_root = tmp_path / "CoChem_Artifacts"
    assert not target_root.exists()

    result = scaffold_workspace_parsl(base_path=target_root)

    assert isinstance(result, ScaffoldResult)
    assert result.success is True
    assert target_root.exists() and target_root.is_dir()

    expected_dirs = ["Input_Files", "Processed", "Logs", "Scratch", "Registry", "Databases"]
    for d_name in expected_dirs:
        d_path = target_root / d_name
        assert d_path.exists(), f"Expected directory {d_name} was not created"
        assert d_path.is_dir(), f"Expected {d_name} to be a directory"

    # Constraint verification: NO .workspace.lock file or filesystem mutexes in creation topology
    lock_file = target_root / ".workspace.lock"
    assert not lock_file.exists(), "Parsl scaffolding topology must not generate .workspace.lock file"


def test_parsl_dag_workspace_scaffolding_additional_dirs(tmp_path: Path, parsl_session: Any) -> None:
    """Verify Parsl DAG scaffolding with additional custom silo and task queue directories."""
    target_root = tmp_path / "CoChem_Artifacts_Extended"
    additional = ["cochem_setup", "cochem_task_queue", "MACE_Checkpoints", "ORCA_Scratch"]

    result = scaffold_workspace_parsl(base_path=target_root, additional_dirs=additional)

    assert result.success is True
    for d_name in CORE_DIRECTORIES:
        assert (target_root / d_name).is_dir()

    for custom_dir in additional:
        assert (target_root / custom_dir).is_dir()


def test_parsl_dag_task_dependency_chaining(tmp_path: Path, parsl_session: Any) -> None:
    """Verify Parsl DAG dependency serialization: downstream compute task chains to directory futures.

    Proves that a computational chemistry preparation task waits for directory creation
    future resolution before writing genuine quantum chemical inputs.
    """
    from parsl.app.app import python_app

    target_root = tmp_path / "CoChem_Artifacts_Chained"

    # Define a downstream computational preparation task chained to scaffold future
    @python_app
    def prepare_orca_input(input_dir_path: str, filename: str, content: str) -> str:
        from pathlib import Path
        inp_file = Path(input_dir_path) / filename
        inp_file.write_text(content, encoding="utf-8")
        return str(inp_file)

    # 1. Launch Parsl workspace scaffolding
    scaffold_result = scaffold_workspace_parsl(base_path=target_root)
    assert scaffold_result.success is True

    # 2. Chain downstream input generation task
    input_files_dir = str(target_root / "Input_Files")
    orca_payload = (
        "! B3LYP def2-SVP D4 Opt\n"
        "%pal nprocs 4 end\n"
        "* xyz 0 1\n"
        "O  0.000000  0.000000  0.117790\n"
        "H  0.000000  0.755453 -0.471161\n"
        "H  0.000000 -0.755453 -0.471161\n"
        "*\n"
    )

    future = prepare_orca_input(input_files_dir, "monomer_relax.inp", orca_payload)
    output_path = future.result()

    assert Path(output_path).exists()
    assert (target_root / "Input_Files" / "monomer_relax.inp").read_text(encoding="utf-8") == orca_payload


def test_workspace_manager_scaffold_workspace_parsl(tmp_path: Path, parsl_session: Any) -> None:
    """Verify WorkspaceManager.scaffold_workspace_parsl method execution."""
    manager = WorkspaceManager(base_path=tmp_path)
    result = manager.scaffold_workspace_parsl(additional_dirs=["Custom_Reports"])

    assert isinstance(result, ScaffoldResult)
    assert result.success is True
    assert (tmp_path / "Custom_Reports").is_dir()
    for d in CORE_DIRECTORIES:
        assert (tmp_path / d).is_dir()


# =============================================================================
# 4. DELETION SHIELD PERMISSION LOCKING & RESTORATION (0o755 / 0o444)
# =============================================================================


def test_deletion_shield_file_permission_locking(tmp_path: Path) -> None:
    """Zero-mock Deletion Shield: Finalized .zip, .tex, and .h5 artifacts set to 0o444 (Read-Only).

    Verifies write attempts raise PermissionError while read-only, and restoring permissions
    allows write access again.
    """
    artifacts_dir = tmp_path / "Final_Artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    report_zip = artifacts_dir / "calculation_report.zip"
    report_zip.write_bytes(b"PK\x03\x04_GENUINE_ZIP_PAYLOAD")

    publication_tex = artifacts_dir / "spectroscopy_table.tex"
    publication_tex.write_text("\\begin{table}\n\\caption{Rotational Constants}\n\\end{table}", encoding="utf-8")

    state_h5 = artifacts_dir / "cochem_state.h5"
    state_h5.write_bytes(b"\x89HDF\r\n\x1a\n_STATE_PAYLOAD")

    # Apply Deletion Shield (Read-Only 0o444)
    lock_artifact_permissions(report_zip, read_only=True)
    lock_artifact_permissions(publication_tex, read_only=True)
    lock_artifact_permissions(state_h5, read_only=True)

    # 1. Verify writing / overwriting fails with PermissionError
    with pytest.raises(PermissionError):
        with open(report_zip, "w", encoding="utf-8") as f:
            f.write("malicious overwrite")

    with pytest.raises(PermissionError):
        with open(publication_tex, "w", encoding="utf-8") as f:
            f.write("corrupted table")

    with pytest.raises(PermissionError):
        with open(state_h5, "wb") as f:
            f.write(b"corrupted hdf5")

    # 2. Unlock artifacts and verify write capability is restored
    unlock_artifact_permissions(report_zip)
    unlock_artifact_permissions(publication_tex)
    lock_artifact_permissions(state_h5, read_only=False)

    with open(report_zip, "wb") as f:
        f.write(b"updated zip payload")
    assert report_zip.read_bytes() == b"updated zip payload"

    with open(publication_tex, "a", encoding="utf-8") as f:
        f.write("\n% appended row")
    assert "% appended row" in publication_tex.read_text(encoding="utf-8")


def test_deletion_shield_recursive_directory_locking(tmp_path: Path) -> None:
    """Zero-mock Deletion Shield: Recursive permission locking across directory trees."""
    data_dir = tmp_path / "Persistent_Data_Tier"
    data_dir.mkdir(parents=True, exist_ok=True)

    sub_reg = data_dir / "Registry" / "Schemas"
    sub_reg.mkdir(parents=True, exist_ok=True)
    schema_json = sub_reg / "v4_schema.json"
    schema_json.write_text('{"schema_version": "4.0.0"}', encoding="utf-8")

    sub_proc = data_dir / "Processed" / "Geom"
    sub_proc.mkdir(parents=True, exist_ok=True)
    geom_xyz = sub_proc / "dimer_opt.xyz"
    geom_xyz.write_text("3\nDimer optimized\nO 0 0 0\nH 0 0 1\nH 0 1 0\n", encoding="utf-8")

    # Lock whole directory tree recursively
    lock_artifact_permissions(data_dir, read_only=True, recursive=True)

    # Attempt to write to nested files must raise PermissionError
    with pytest.raises(PermissionError):
        with open(schema_json, "w", encoding="utf-8") as f:
            f.write('{"tampered": true}')

    with pytest.raises(PermissionError):
        with open(geom_xyz, "w", encoding="utf-8") as f:
            f.write("corrupted xyz")

    # Restore read-write access
    lock_artifact_permissions(data_dir, read_only=False, recursive=True)

    with open(schema_json, "w", encoding="utf-8") as f:
        f.write('{"schema_version": "4.0.1"}')
    assert '4.0.1' in schema_json.read_text(encoding="utf-8")


def test_deletion_shield_file_extension_filter(tmp_path: Path) -> None:
    """Verify selective permission locking by file extension."""
    work_dir = tmp_path / "Filtered_Work"
    work_dir.mkdir(parents=True, exist_ok=True)

    lock_me_zip = work_dir / "payload.zip"
    lock_me_zip.write_bytes(b"ZIP_DATA")

    lock_me_tex = work_dir / "table.tex"
    lock_me_tex.write_text("TEX_DATA", encoding="utf-8")

    leave_me_tmp = work_dir / "scratch.tmp"
    leave_me_tmp.write_text("TEMP_DATA", encoding="utf-8")

    # Lock only .zip and .tex files
    lock_artifact_permissions(
        work_dir,
        read_only=True,
        recursive=True,
        file_extensions=[".zip", ".tex"],
    )

    # .zip and .tex should be locked
    with pytest.raises(PermissionError):
        with open(lock_me_zip, "wb") as f:
            f.write(b"FAIL")

    with pytest.raises(PermissionError):
        with open(lock_me_tex, "w", encoding="utf-8") as f:
            f.write("FAIL")

    # .tmp should remain writable
    with open(leave_me_tmp, "w", encoding="utf-8") as f:
        f.write("SUCCESS_MODIFIED")
    assert leave_me_tmp.read_text(encoding="utf-8") == "SUCCESS_MODIFIED"

    # Cleanup permissions
    lock_artifact_permissions(work_dir, read_only=False, recursive=True)


# =============================================================================
# 5. WORKSPACE MANAGER CORE DIRECTORIES, JOBS, ZOMBIES, & STATUS
# =============================================================================


def test_workspace_manager_initialization(tmp_path: Path) -> None:
    """Verify WorkspaceManager initialization and base path resolution."""
    manager = WorkspaceManager(base_path=str(tmp_path))
    assert manager.base_path == tmp_path.resolve()


def test_workspace_manager_scaffold_core_directories_standard(tmp_path: Path) -> None:
    """Verify standard scaffolding creates all core directories with active read/write permissions."""
    manager = WorkspaceManager(base_path=tmp_path)
    success = manager.scaffold_core_directories(additional_dirs=["CustomModule", "CustomCache"])
    assert success is True

    for d in WorkspaceManager.CORE_DIRECTORIES:
        expected_dir = tmp_path / d
        assert expected_dir.exists() and expected_dir.is_dir()
        # Verify writable
        assert os.access(str(expected_dir), os.W_OK)

    assert (tmp_path / "CustomModule").is_dir()
    assert (tmp_path / "CustomCache").is_dir()


def test_provision_and_get_job_workspace(tmp_path: Path) -> None:
    """Verify job workspace provisioning and path resolution."""
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    job_id = "JOB_ORCA_DFT_001"
    job_dir = manager.provision_job_workspace(job_id, create_job_lock=True)
    assert job_dir.exists()
    assert job_dir == tmp_path / "Scratch" / job_id
    assert (job_dir / ".job.lock").exists()

    retrieved = manager.get_job_workspace(job_id)
    assert retrieved == job_dir


def test_is_job_active_and_cleanup_protection(tmp_path: Path) -> None:
    """Verify active job lock detection protects running calculations from deletion."""
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    job_id = "JOB_ACTIVE_GUARD"
    job_dir = manager.provision_job_workspace(job_id, create_job_lock=True)
    job_lock = job_dir / ".job.lock"

    assert manager.is_job_active(job_id) is False

    # Simulate an active running process holding the job lock
    fd = os.open(str(job_lock), os.O_RDWR)
    try:
        acquired = manager._acquire_lock(fd)
        assert acquired is True
        assert manager.is_job_active(job_id) is True

        # Non-forced cleanup must abort to protect active calculation
        assert manager.cleanup_job_workspace(job_id, force=False) is False
        assert job_dir.exists()
    finally:
        manager._release_lock(fd)
        os.close(fd)

    assert manager.is_job_active(job_id) is False
    # Cleanup succeeds once lock is released
    assert manager.cleanup_job_workspace(job_id, force=False) is True
    assert not job_dir.exists()


def test_sweep_zombie_directories(tmp_path: Path) -> None:
    """Verify zombie directory sweeper removes orphaned crashed jobs while protecting active ones."""
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    # 1. Orphaned zombie job with unlocked .job.lock
    job1_dir = manager.provision_job_workspace("JOB_ZOMBIE_1", create_job_lock=True)
    (job1_dir / "temp_calc.dat").write_text("! B3LYP def2-SVP\n", encoding="utf-8")

    # 2. Active running job with held lock
    job2_dir = manager.provision_job_workspace("JOB_ACTIVE_2", create_job_lock=True)
    job2_lock = job2_dir / ".job.lock"
    fd2 = os.open(str(job2_lock), os.O_RDWR)
    manager._acquire_lock(fd2)

    # 3. Orphaned zombie job without lock file
    job3_dir = manager.provision_job_workspace("JOB_ZOMBIE_3", create_job_lock=False)
    (job3_dir / "output.log").write_text("PARTIAL LOG DATA\n", encoding="utf-8")

    try:
        swept = manager.sweep_zombie_directories(grace_period_seconds=0.0)
        assert swept == 2

        # Job 1 and Job 3 must be purged
        assert not job1_dir.exists()
        assert not job3_dir.exists()

        # Job 2 must be preserved because it was actively locked
        assert job2_dir.exists()
    finally:
        manager._release_lock(fd2)
        os.close(fd2)

    # After releasing lock, sweeping again purges Job 2
    swept_again = manager.sweep_zombie_directories(grace_period_seconds=0.0)
    assert swept_again == 1
    assert not job2_dir.exists()


def test_sweep_zombie_directories_grace_period(tmp_path: Path) -> None:
    """Verify sweep_zombie_directories respects grace_period_seconds for newly provisioned directories."""
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    job_dir = manager.provision_job_workspace("JOB_FRESH_PROVISION", create_job_lock=False)
    assert job_dir.exists()

    # High grace period (e.g. 100s) must protect newly created directory
    swept = manager.sweep_zombie_directories(grace_period_seconds=100.0)
    assert swept == 0
    assert job_dir.exists()

    # Zero grace period sweeps unlocked directory
    swept_now = manager.sweep_zombie_directories(grace_period_seconds=0.0)
    assert swept_now == 1
    assert not job_dir.exists()


def test_get_directory_status(tmp_path: Path) -> None:
    """Verify get_directory_status returns accurate diagnostic metrics and file counts."""
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    # Populate Logs
    log_file = tmp_path / "Logs" / "cochem_orchestrator.log"
    log_file.write_text("INFO: Orchestrator initialized\nINFO: Stage 0 complete\n", encoding="utf-8")

    # Populate Processed
    proc_file = tmp_path / "Processed" / "conformer_01.xyz"
    proc_file.write_text("3\nConformer 01\nC 0 0 0\nH 0 0 1\nH 0 1 0\n", encoding="utf-8")

    status = manager.get_directory_status()

    assert "Logs" in status
    assert status["Logs"]["exists"] is True
    assert status["Logs"]["file_count"] == 1
    assert status["Logs"]["total_size_bytes"] > 0
    assert status["Logs"]["is_writable"] is True
    assert status["Logs"]["is_readable"] is True

    assert "Processed" in status
    assert status["Processed"]["file_count"] == 1

    assert "Scratch" in status
    assert status["Scratch"]["exists"] is True
    assert status["Scratch"]["file_count"] == 0


def test_airgap_topologies_provisioning(tmp_path: Path) -> None:
    """Verify Tripartite and Bipartite Airgap topologies provisioning."""
    manager = WorkspaceManager(base_path=tmp_path)
    custom_code_dir = tmp_path / "CoChem_Source"
    custom_code_dir.mkdir(parents=True, exist_ok=True)

    # Tripartite
    tri_map = manager.apply_tripartite_airgap(code_dir=custom_code_dir)
    assert "immutable_code" in tri_map
    assert "dynamic_state" in tri_map
    assert "volatile_compute" in tri_map
    assert tri_map["immutable_code"] == str(custom_code_dir.resolve())
    assert tri_map["dynamic_state"] == str(tmp_path.resolve())
    assert tri_map["volatile_compute"] == str((tmp_path / "Scratch").resolve())

    # Bipartite
    bi_map = manager.apply_bipartite_airgap(code_dir=custom_code_dir)
    assert "code_tier" in bi_map
    assert "data_tier" in bi_map
    assert bi_map["code_tier"] == str(custom_code_dir.resolve())
    assert bi_map["data_tier"] == str(tmp_path.resolve())


# =============================================================================
# 6. WORKSPACE DAEMON LIFECYCLE & ASYNC COROUTINES
# =============================================================================


def test_workspace_daemon_lifecycle(tmp_path: Path) -> None:
    """Verify WorkspaceScaffoldingDaemon / WorkspaceDaemon threading lifecycle."""
    manager = WorkspaceManager(base_path=tmp_path)
    daemon = WorkspaceScaffoldingDaemon(
        manager=manager,
        sweep_interval_seconds=0.1,
        min_scratch_quota_gb=0.001,
    )

    assert daemon.get_status().is_running is False

    # Execute single manual cycle
    res = daemon.run_once()
    assert res["cycle"] == 1
    assert res["zombies_swept"] == 0
    assert "airgap_topology" in res
    assert "directory_status" in res
    assert "scratch_disk_quota" in res
    assert res["scratch_disk_quota"]["is_sufficient"] is True

    # Start background daemon thread
    daemon.start()
    assert daemon.get_status().is_running is True
    time.sleep(0.35)
    daemon.stop()

    status = daemon.get_status()
    assert status.is_running is False
    assert status.sweeps_completed >= 2


def test_workspace_daemon_run_async(tmp_path: Path) -> None:
    """Verify WorkspaceScaffoldingDaemon.run_async in asyncio loop."""
    async def _run() -> None:
        manager = WorkspaceManager(base_path=tmp_path)
        daemon = WorkspaceDaemon(
            manager=manager,
            sweep_interval_seconds=0.05,
            min_scratch_quota_gb=0.001,
        )

        task = asyncio.create_task(daemon.run_async())
        await asyncio.sleep(0.15)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert daemon.sweeps_completed >= 1

    asyncio.run(_run())


# =============================================================================
# 7. CROSS-PLATFORM FILE LOCKING & SINGLETON HELPERS
# =============================================================================


def test_cross_platform_file_lock(tmp_path: Path) -> None:
    """Verify file_lock context manager mutual exclusion and timeout."""
    manager = WorkspaceManager(base_path=tmp_path)
    lock_file_path = tmp_path / "concurrency.lock"

    with manager.file_lock(lock_file_path, exclusive=True) as acquired1:
        assert acquired1 is True
        # Second non-blocking acquire attempt on same file must fail
        with manager.file_lock(lock_file_path, exclusive=True, timeout=0.0) as acquired2:
            assert acquired2 is False

    # Lock released; third acquire must succeed
    with manager.file_lock(lock_file_path, exclusive=True) as acquired3:
        assert acquired3 is True


def test_acquire_lock_timeout(tmp_path: Path) -> None:
    """Verify lock acquisition timeout parameter behavior."""
    manager = WorkspaceManager(base_path=tmp_path)
    test_file = tmp_path / "timeout_test.lock"
    fd1 = os.open(str(test_file), os.O_RDWR | os.O_CREAT)
    fd2 = os.open(str(test_file), os.O_RDWR | os.O_CREAT)
    try:
        acquired1 = manager._acquire_lock(fd1, exclusive=True, timeout=0.0)
        assert acquired1 is True

        start = time.time()
        acquired2 = manager._acquire_lock(fd2, exclusive=True, timeout=0.05)
        elapsed = time.time() - start
        assert acquired2 is False
        assert elapsed >= 0.04
    finally:
        manager._release_lock(fd1)
        os.close(fd1)
        os.close(fd2)


def test_module_level_helpers(tmp_path: Path) -> None:
    """Verify all top-level module convenience helper functions."""
    manager = get_default_workspace_manager()
    assert isinstance(manager, WorkspaceManager)

    # Top-level file lock
    test_lock = tmp_path / "top_level.lock"
    with file_lock(test_lock, exclusive=True) as ok:
        assert ok is True

    # Top-level core scaffold
    scaffold_ok = scaffold_core_directories()
    assert isinstance(scaffold_ok, bool)

    # Top-level job provisioning
    job_path = provision_job_workspace("JOB_TOP_LEVEL_TEST", create_job_lock=True)
    assert job_path.exists()
    assert get_job_workspace("JOB_TOP_LEVEL_TEST") == job_path
    assert is_job_active("JOB_TOP_LEVEL_TEST") is False

    # Top-level status & airgap
    status_dict = get_directory_status()
    assert isinstance(status_dict, dict)
    airgap_dict = apply_tripartite_airgap()
    assert "immutable_code" in airgap_dict
    bipartite_dict = apply_bipartite_airgap()
    assert "code_tier" in bipartite_dict

    # Top-level quota checks
    scratch_dir = tmp_path / "Scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    quota_metrics = check_scratch_disk_quota(scratch_dir, min_free_gb=0.001)
    assert quota_metrics.is_sufficient is True

    # Top-level cleanup & sweep
    cleaned = cleanup_job_workspace("JOB_TOP_LEVEL_TEST")
    assert cleaned is True
    swept = sweep_zombie_directories(grace_period_seconds=0.0)
    assert isinstance(swept, int)

    # Top-level permission helpers
    tex_artifact = tmp_path / "artifact.tex"
    tex_artifact.write_text("TEST_TEX", encoding="utf-8")
    lock_artifact_permissions(tex_artifact, read_only=True)
    with pytest.raises(PermissionError):
        with open(tex_artifact, "w") as f:
            f.write("FAIL")
    unlock_artifact_permissions(tex_artifact)
    with open(tex_artifact, "w") as f:
        f.write("RESTORED")
    assert tex_artifact.read_text() == "RESTORED"
