"""
Unit test suite for CoChem Setup Phase 7: HPC Environment Variable Injection & Topology Gatekeeper.
Strict Zero-Mock Mandate: Real filesystem operations, real temporary directories, real environment
variable dictionary evaluation, real bracketed nodelist range expansions, real multiplier task
parsing, real cgroup limit hierarchy evaluation, real thread affinity generation, and transactional
atomic state persistence into the Golden Registry (p7.json).

SRS Document 2 Part 2 (Section 3.7), Method Matrix v4, and CoChem User Manual v4.1 Compliant.
"""

from __future__ import annotations

import json
import os
import platform
import stat
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest
from pydantic import ValidationError

from orchestrator.cochem_setup_phase_7 import (
    DependencyManager,
    HPCMemoryParseError,
    HPCMemoryProfile,
    HPCSchedulerType,
    HPCScratchAllocationError,
    HPCScratchProfile,
    HPCThreadAffinityProfile,
    HPCTopologyError,
    HPCTopologyProfile,
    Phase7AuditError,
    Phase7AuditReport,
    PhaseStatus,
    _expand_single_node_spec,
    _split_top_level_commas,
    compute_thread_affinity_profile,
    detect_hpc_scheduler,
    generate_environment_injection_dict,
    get_physical_ram_bytes,
    main,
    parse_cgroup_memory_limit,
    parse_hpc_memory_limit,
    parse_lsf_topology,
    parse_memory_string_to_mb,
    parse_pbs_topology,
    parse_sge_topology,
    parse_slurm_nodelist,
    parse_slurm_tasks_per_node,
    parse_slurm_topology,
    parse_standalone_topology,
    parse_topology,
    resolve_hpc_scratch_directory,
    resolve_p7_registry_path,
    run_phase_7_audit,
)


# Helper for Windows temp directory cleanup resilience
def make_temp_dir() -> tempfile.TemporaryDirectory:
    """Create a temporary directory with Windows cleanup resilience."""
    if hasattr(tempfile.TemporaryDirectory, "_ignore_cleanup_errors") or platform.system() == "Windows":
        try:
            return tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        except TypeError:
            pass
    return tempfile.TemporaryDirectory()


# =============================================================================
# 1. CUSTOM EXCEPTION & ENUM TESTS
# =============================================================================


def test_custom_exception_hierarchy() -> None:
    """Verify custom Phase 7 exception classes inherit from RuntimeError."""
    err1 = Phase7AuditError("Phase 7 fatal error")
    assert isinstance(err1, RuntimeError)
    err2 = HPCTopologyError("HPC topology parsing failed")
    assert isinstance(err2, RuntimeError)
    err3 = HPCMemoryParseError("Memory parsing failed")
    assert isinstance(err3, RuntimeError)
    err4 = HPCScratchAllocationError("Scratch allocation failed")
    assert isinstance(err4, RuntimeError)


def test_phase_status_enum() -> None:
    """Verify PhaseStatus enum values and validation."""
    assert PhaseStatus.PASSED.value == "PASSED"
    assert PhaseStatus.FAILED.value == "FAILED"
    assert PhaseStatus.DEGRADED.value == "DEGRADED"
    assert PhaseStatus.BYPASSED.value == "BYPASSED"
    assert PhaseStatus("PASSED") is PhaseStatus.PASSED

    with pytest.raises(ValueError):
        PhaseStatus("INVALID_STATUS")


def test_hpc_scheduler_type_enum() -> None:
    """Verify HPCSchedulerType enum members and string representations."""
    assert HPCSchedulerType.SLURM.value == "SLURM"
    assert HPCSchedulerType.PBS.value == "PBS"
    assert HPCSchedulerType.LSF.value == "LSF"
    assert HPCSchedulerType.SGE.value == "SGE"
    assert HPCSchedulerType.LOCAL_STANDALONE.value == "LOCAL_STANDALONE"
    assert HPCSchedulerType("SLURM") is HPCSchedulerType.SLURM

    with pytest.raises(ValueError):
        HPCSchedulerType("UNKNOWN_SCHEDULER")


# =============================================================================
# 2. PYDANTIC V2 SCHEMA VALIDATION TESTS
# =============================================================================


def test_hpc_topology_profile_validation() -> None:
    """Test HPCTopologyProfile defaults, constraints, and extra field prohibition."""
    profile = HPCTopologyProfile(
        scheduler=HPCSchedulerType.SLURM,
        job_id="123456",
        num_nodes=2,
        node_list=["node01", "node02"],
        tasks_per_node=[8, 8],
        total_tasks=16,
        cpus_per_task=4,
        cpus_on_node=32,
        is_heterogeneous=False,
    )
    assert profile.scheduler == HPCSchedulerType.SLURM
    assert profile.job_id == "123456"
    assert profile.num_nodes == 2
    assert profile.total_tasks == 16
    assert profile.cpus_per_task == 4
    assert profile.cpus_on_node == 32
    assert profile.is_heterogeneous is False

    # Negative num_nodes constraint
    with pytest.raises(ValidationError):
        HPCTopologyProfile(
            scheduler=HPCSchedulerType.SLURM,
            num_nodes=0,
            total_tasks=1,
        )

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        HPCTopologyProfile(
            scheduler=HPCSchedulerType.SLURM,
            num_nodes=1,
            total_tasks=1,
            unauthorized_field=True,  # type: ignore[call-arg]
        )


def test_hpc_memory_profile_validation() -> None:
    """Test HPCMemoryProfile field validation and serialization."""
    profile = HPCMemoryProfile(
        mem_per_node_mb=64000.0,
        mem_per_cpu_mb=4000.0,
        cgroup_limit_bytes=None,
        physical_ram_bytes=137438953472,
        effective_usable_memory_mb=64000.0,
        source="SLURM_MEM_PER_NODE",
    )
    assert profile.mem_per_node_mb == 64000.0
    assert profile.effective_usable_memory_mb == 64000.0
    assert profile.source == "SLURM_MEM_PER_NODE"

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        HPCMemoryProfile(
            physical_ram_bytes=1000,
            effective_usable_memory_mb=1000.0,
            source="PHYSICAL_RAM",
            forbidden_attr="test",  # type: ignore[call-arg]
        )


def test_hpc_scratch_profile_validation() -> None:
    """Test HPCScratchProfile field validation."""
    profile = HPCScratchProfile(
        scratch_directory="/tmp/slurm_scratch",
        is_accessible=True,
        is_writable=True,
        free_disk_space_gb=250.5,
        source_variable="SLURM_TMPDIR",
    )
    assert profile.scratch_directory == "/tmp/slurm_scratch"
    assert profile.free_disk_space_gb == 250.5
    assert profile.source_variable == "SLURM_TMPDIR"

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        HPCScratchProfile(
            scratch_directory="/tmp",
            source_variable="TEMP",
            invalid_flag=True,  # type: ignore[call-arg]
        )


def test_hpc_thread_affinity_profile_validation() -> None:
    """Test HPCThreadAffinityProfile field validation and defaults."""
    profile = HPCThreadAffinityProfile(
        omp_num_threads=8,
        mkl_num_threads=8,
        openblas_num_threads=8,
        blis_num_threads=8,
        omp_places="cores",
        omp_proc_bind="close",
        kmp_affinity="granularity=fine,compact,1,0",
        kmp_blocktime=0,
        environment_variables={"OMP_NUM_THREADS": "8"},
    )
    assert profile.omp_num_threads == 8
    assert profile.kmp_blocktime == 0
    assert profile.omp_places == "cores"

    # Constraint violation: negative threads
    with pytest.raises(ValidationError):
        HPCThreadAffinityProfile(
            omp_num_threads=0,
            mkl_num_threads=1,
            openblas_num_threads=1,
        )


def test_phase_7_audit_report_roundtrip_serialization() -> None:
    """Test Phase7AuditReport construction and JSON serialization roundtrip."""
    with make_temp_dir() as tmpdir:
        art_path = Path(tmpdir) / "p7.json"
        topology = HPCTopologyProfile(
            scheduler=HPCSchedulerType.SLURM,
            job_id="998877",
            num_nodes=2,
            node_list=["node01", "node02"],
            tasks_per_node=[4, 4],
            total_tasks=8,
            cpus_per_task=2,
            cpus_on_node=8,
            is_heterogeneous=False,
        )
        memory = HPCMemoryProfile(
            mem_per_node_mb=32000.0,
            physical_ram_bytes=68719476736,
            effective_usable_memory_mb=32000.0,
            source="SLURM_MEM_PER_NODE",
        )
        scratch = HPCScratchProfile(
            scratch_directory=str(Path(tmpdir) / "scratch"),
            is_accessible=True,
            is_writable=True,
            free_disk_space_gb=100.0,
            source_variable="SLURM_TMPDIR",
        )
        affinity = HPCThreadAffinityProfile(
            omp_num_threads=2,
            mkl_num_threads=2,
            openblas_num_threads=2,
            blis_num_threads=2,
            omp_places="cores",
            omp_proc_bind="close",
            kmp_affinity="granularity=fine,compact,1,0",
            kmp_blocktime=0,
            environment_variables={"OMP_NUM_THREADS": "2"},
        )
        report = Phase7AuditReport(
            phase_id="cochem_setup_phase_7",
            status=PhaseStatus.PASSED,
            scheduler_detected=HPCSchedulerType.SLURM,
            timestamp_utc="2026-08-21T00:00:00Z",
            artifact_path=str(art_path),
            topology=topology,
            memory=memory,
            scratch=scratch,
            affinity=affinity,
            injected_env_vars={"OMP_NUM_THREADS": "2", "COCHEM_HPC_SCHEDULER": "SLURM"},
            warnings=[],
            errors=[],
        )

        json_str = report.model_dump_json(indent=2)
        parsed_dict = json.loads(json_str)
        assert parsed_dict["phase_id"] == "cochem_setup_phase_7"
        assert parsed_dict["status"] == "PASSED"
        assert parsed_dict["scheduler_detected"] == "SLURM"
        assert parsed_dict["topology"]["total_tasks"] == 8

        # Roundtrip deserialization
        restored = Phase7AuditReport.model_validate(parsed_dict)
        assert restored.status == PhaseStatus.PASSED
        assert restored.topology.num_nodes == 2


# =============================================================================
# 3. HPC SCHEDULER DETECTION ENGINE TESTS
# =============================================================================


def test_detect_hpc_scheduler_explicit_override() -> None:
    """Verify explicit COCHEM_HPC_SCHEDULER override has top priority."""
    assert detect_hpc_scheduler({"COCHEM_HPC_SCHEDULER": "SLURM"}) == HPCSchedulerType.SLURM
    assert detect_hpc_scheduler({"COCHEM_HPC_SCHEDULER": "PBS"}) == HPCSchedulerType.PBS
    assert detect_hpc_scheduler({"COCHEM_HPC_SCHEDULER": "LSF"}) == HPCSchedulerType.LSF
    assert detect_hpc_scheduler({"COCHEM_HPC_SCHEDULER": "SGE"}) == HPCSchedulerType.SGE
    assert (
        detect_hpc_scheduler({"COCHEM_HPC_SCHEDULER": "LOCAL_STANDALONE"})
        == HPCSchedulerType.LOCAL_STANDALONE
    )


def test_detect_hpc_scheduler_slurm() -> None:
    """Verify Slurm scheduler detection from standard environment variables."""
    assert detect_hpc_scheduler({"SLURM_JOB_ID": "12345"}) == HPCSchedulerType.SLURM
    assert detect_hpc_scheduler({"SLURM_JOBID": "12345"}) == HPCSchedulerType.SLURM
    assert detect_hpc_scheduler({"SLURM_NNODES": "4"}) == HPCSchedulerType.SLURM
    assert detect_hpc_scheduler({"SLURM_NODELIST": "node[01-04]"}) == HPCSchedulerType.SLURM
    assert detect_hpc_scheduler({"SLURM_TASKS_PER_NODE": "4(x4)"}) == HPCSchedulerType.SLURM


def test_detect_hpc_scheduler_pbs() -> None:
    """Verify PBS scheduler detection from PBS variables."""
    assert detect_hpc_scheduler({"PBS_JOBID": "pbs123.cluster"}) == HPCSchedulerType.PBS
    assert detect_hpc_scheduler({"PBS_NODEFILE": "/var/spool/pbs/aux/123"}) == HPCSchedulerType.PBS
    assert detect_hpc_scheduler({"PBS_NUM_NODES": "2"}) == HPCSchedulerType.PBS
    assert detect_hpc_scheduler({"PBS_ENVIRONMENT": "PBS_BATCH"}) == HPCSchedulerType.PBS


def test_detect_hpc_scheduler_lsf() -> None:
    """Verify LSF scheduler detection from LSB variables."""
    assert detect_hpc_scheduler({"LSB_JOBID": "lsf9988"}) == HPCSchedulerType.LSF
    assert detect_hpc_scheduler({"LSB_HOSTS": "hostA hostA hostB"}) == HPCSchedulerType.LSF
    assert detect_hpc_scheduler({"LSB_MCPU_HOSTS": "hostA 2 hostB 2"}) == HPCSchedulerType.LSF
    assert detect_hpc_scheduler({"LSB_DJOB_NUMPROC": "4"}) == HPCSchedulerType.LSF


def test_detect_hpc_scheduler_sge() -> None:
    """Verify SGE scheduler detection from SGE variables."""
    assert detect_hpc_scheduler({"PE_HOSTFILE": "/tmp/pe_hosts"}) == HPCSchedulerType.SGE
    assert detect_hpc_scheduler({"SGE_CELL": "default"}) == HPCSchedulerType.SGE
    assert detect_hpc_scheduler({"JOB_ID": "5544", "NSLOTS": "16"}) == HPCSchedulerType.SGE


def test_detect_hpc_scheduler_local_standalone() -> None:
    """Verify Local Standalone fallback when no HPC scheduler variables are present."""
    assert detect_hpc_scheduler({}) == HPCSchedulerType.LOCAL_STANDALONE
    assert detect_hpc_scheduler({"PATH": "/usr/bin", "USER": "test"}) == HPCSchedulerType.LOCAL_STANDALONE


# =============================================================================
# 4. SLURM NODELIST & TASK PARSER TESTS
# =============================================================================


def test_split_top_level_commas() -> None:
    """Test splitting strings by commas outside bracket groups."""
    assert _split_top_level_commas("node01,node02,node03") == ["node01", "node02", "node03"]
    assert _split_top_level_commas("node[01-03,05],gpu[01-02],head01") == [
        "node[01-03,05]",
        "gpu[01-02]",
        "head01",
    ]
    assert _split_top_level_commas("  node[01-02] ,  node03  ") == ["node[01-02]", "node03"]
    assert _split_top_level_commas("") == []


def test_expand_single_node_spec() -> None:
    """Test expanding single bracketed specifications."""
    assert _expand_single_node_spec("node01") == ["node01"]
    assert _expand_single_node_spec("node[01-03]") == ["node01", "node02", "node03"]
    assert _expand_single_node_spec("node[01-03,05]") == ["node01", "node02", "node03", "node05"]
    assert _expand_single_node_spec("gpu[001-002,005-006]") == [
        "gpu001",
        "gpu002",
        "gpu005",
        "gpu006",
    ]
    assert _expand_single_node_spec("c[1-2]n[3-4]") == ["c1n3", "c1n4", "c2n3", "c2n4"]
    assert _expand_single_node_spec("node[01-02]-ib0") == ["node01-ib0", "node02-ib0"]


def test_parse_slurm_nodelist_valid_cases() -> None:
    """Test complete Slurm nodelist parsing across multiple formats."""
    # Single node
    assert parse_slurm_nodelist("node01") == ["node01"]

    # Comma-separated list
    assert parse_slurm_nodelist("node01,node02,node03") == ["node01", "node02", "node03"]

    # Simple range
    assert parse_slurm_nodelist("node[01-04]") == ["node01", "node02", "node03", "node04"]

    # Multiple ranges with single nodes in brackets
    assert parse_slurm_nodelist("node[01-03,05,08-10]") == [
        "node01",
        "node02",
        "node03",
        "node05",
        "node08",
        "node09",
        "node10",
    ]

    # Mixed groups with commas outside brackets
    assert parse_slurm_nodelist("node[01-02],gpu[05-06],head01") == [
        "node01",
        "node02",
        "gpu05",
        "gpu06",
        "head01",
    ]

    # Empty string
    assert parse_slurm_nodelist("") == []
    assert parse_slurm_nodelist("   ") == []


def test_parse_slurm_nodelist_error_handling() -> None:
    """Test error handling on malformed nodelist strings."""
    # Mismatched brackets
    with pytest.raises(HPCTopologyError):
        parse_slurm_nodelist("node[01-03")

    with pytest.raises(HPCTopologyError):
        parse_slurm_nodelist("node01]")

    # Descending range
    with pytest.raises(HPCTopologyError):
        parse_slurm_nodelist("node[05-02]")

    # Non-numeric range
    with pytest.raises(HPCTopologyError):
        parse_slurm_nodelist("node[ab-cd]")


def test_parse_slurm_tasks_per_node_valid() -> None:
    """Test parsing of Slurm SLURM_TASKS_PER_NODE with multipliers."""
    # Multipliers
    assert parse_slurm_tasks_per_node("4(x2),2") == [4, 4, 2]
    assert parse_slurm_tasks_per_node("8(x3),4(x2),2") == [8, 8, 8, 4, 4, 2]
    assert parse_slurm_tasks_per_node("4(x2), 2(x2)") == [4, 4, 2, 2]

    # Comma list without multiplier
    assert parse_slurm_tasks_per_node("4,4,2") == [4, 4, 2]

    # Single value with num_nodes expansion
    assert parse_slurm_tasks_per_node("16", num_nodes=3) == [16, 16, 16]
    assert parse_slurm_tasks_per_node("16", num_nodes=1) == [16]
    assert parse_slurm_tasks_per_node("16") == [16]


def test_parse_slurm_tasks_per_node_errors() -> None:
    """Test error handling for invalid tasks-per-node strings."""
    with pytest.raises(HPCTopologyError):
        parse_slurm_tasks_per_node("")

    with pytest.raises(HPCTopologyError):
        parse_slurm_tasks_per_node("   ")

    with pytest.raises(HPCTopologyError):
        parse_slurm_tasks_per_node("invalid_string")

    with pytest.raises(HPCTopologyError):
        parse_slurm_tasks_per_node("4(x)")


# =============================================================================
# 5. SCHEDULER TOPOLOGY PARSERS
# =============================================================================


def test_parse_slurm_topology() -> None:
    """Test full Slurm topology parsing from environment dictionary."""
    env = {
        "SLURM_JOB_ID": "998877",
        "SLURM_NODELIST": "compute[01-02]",
        "SLURM_NNODES": "2",
        "SLURM_TASKS_PER_NODE": "8(x2)",
        "SLURM_CPUS_PER_TASK": "4",
        "SLURM_CPUS_ON_NODE": "32",
    }
    topo = parse_slurm_topology(env)
    assert topo.scheduler == HPCSchedulerType.SLURM
    assert topo.job_id == "998877"
    assert topo.num_nodes == 2
    assert topo.node_list == ["compute01", "compute02"]
    assert topo.tasks_per_node == [8, 8]
    assert topo.total_tasks == 16
    assert topo.cpus_per_task == 4
    assert topo.cpus_on_node == 32
    assert topo.is_heterogeneous is False


def test_parse_slurm_topology_heterogeneous() -> None:
    """Test heterogeneous Slurm topology detection."""
    env = {
        "SLURM_JOB_ID": "112233",
        "SLURM_NODELIST": "node[01-03]",
        "SLURM_TASKS_PER_NODE": "8(x2),4",
        "SLURM_CPUS_PER_TASK": "1",
    }
    topo = parse_slurm_topology(env)
    assert topo.num_nodes == 3
    assert topo.tasks_per_node == [8, 8, 4]
    assert topo.total_tasks == 20
    assert topo.is_heterogeneous is True


def test_parse_pbs_topology_with_nodefile() -> None:
    """Test PBS topology parsing with real filesystem PBS_NODEFILE."""
    with make_temp_dir() as tmpdir:
        nodefile = Path(tmpdir) / "pbs_nodefile"
        nodefile.write_text("pbs_node01\npbs_node01\npbs_node02\npbs_node02\n", encoding="utf-8")

        env = {
            "PBS_JOBID": "12345.pbs_master",
            "PBS_NODEFILE": str(nodefile),
        }
        topo = parse_pbs_topology(env)
        assert topo.scheduler == HPCSchedulerType.PBS
        assert topo.job_id == "12345.pbs_master"
        assert topo.num_nodes == 2
        assert topo.node_list == ["pbs_node01", "pbs_node02"]
        assert topo.tasks_per_node == [2, 2]
        assert topo.total_tasks == 4


def test_parse_pbs_topology_env_fallback() -> None:
    """Test PBS topology parsing with environment variables fallback."""
    env = {
        "PBS_JOBID": "67890.pbs_master",
        "PBS_NUM_NODES": "3",
        "PBS_NUM_PPN": "8",
    }
    topo = parse_pbs_topology(env)
    assert topo.scheduler == HPCSchedulerType.PBS
    assert topo.num_nodes == 3
    assert topo.tasks_per_node == [8, 8, 8]
    assert topo.total_tasks == 24


def test_parse_lsf_topology() -> None:
    """Test LSF topology parsing with LSB_HOSTS."""
    env = {
        "LSB_JOBID": "887766",
        "LSB_HOSTS": "lsf_host1 lsf_host1 lsf_host1 lsf_host1 lsf_host2 lsf_host2",
    }
    topo = parse_lsf_topology(env)
    assert topo.scheduler == HPCSchedulerType.LSF
    assert topo.job_id == "887766"
    assert topo.num_nodes == 2
    assert topo.node_list == ["lsf_host1", "lsf_host2"]
    assert topo.tasks_per_node == [4, 2]
    assert topo.total_tasks == 6
    assert topo.is_heterogeneous is True


def test_parse_sge_topology_with_pe_hostfile() -> None:
    """Test SGE topology parsing with real filesystem PE_HOSTFILE."""
    with make_temp_dir() as tmpdir:
        pe_file = Path(tmpdir) / "pe_hostfile"
        pe_file.write_text(
            "sge_node01 4 all.q lx-amd64\nsge_node02 4 all.q lx-amd64\n",
            encoding="utf-8",
        )

        env = {
            "JOB_ID": "443322",
            "PE_HOSTFILE": str(pe_file),
        }
        topo = parse_sge_topology(env)
        assert topo.scheduler == HPCSchedulerType.SGE
        assert topo.job_id == "443322"
        assert topo.num_nodes == 2
        assert topo.node_list == ["sge_node01", "sge_node02"]
        assert topo.tasks_per_node == [4, 4]
        assert topo.total_tasks == 8


def test_parse_standalone_topology() -> None:
    """Test standalone workstation topology parsing."""
    topo = parse_standalone_topology({})
    assert topo.scheduler == HPCSchedulerType.LOCAL_STANDALONE
    assert topo.job_id is None
    assert topo.num_nodes == 1
    assert topo.total_tasks == 1
    assert topo.cpus_per_task == (os.cpu_count() or 1)


def test_parse_topology_dispatcher() -> None:
    """Test parse_topology dispatcher across schedulers."""
    assert parse_topology({"SLURM_JOB_ID": "123"}).scheduler == HPCSchedulerType.SLURM
    assert parse_topology({"PBS_JOBID": "123"}).scheduler == HPCSchedulerType.PBS
    assert parse_topology({"LSB_JOBID": "123"}).scheduler == HPCSchedulerType.LSF
    assert parse_topology({"PE_HOSTFILE": "/tmp/pe"}).scheduler == HPCSchedulerType.SGE
    assert parse_topology({}).scheduler == HPCSchedulerType.LOCAL_STANDALONE


# =============================================================================
# 6. MEMORY ALLOCATION & CGROUP LIMIT TESTS
# =============================================================================


def test_parse_memory_string_to_mb_valid() -> None:
    """Test memory string parsing to Megabytes."""
    # Bare integer (MB default)
    assert parse_memory_string_to_mb("64000") == 64000.0

    # MB
    assert parse_memory_string_to_mb("64000M") == 64000.0
    assert parse_memory_string_to_mb("64000MB") == 64000.0
    assert parse_memory_string_to_mb("64000MiB") == 64000.0

    # GB
    assert parse_memory_string_to_mb("64G") == 65536.0
    assert parse_memory_string_to_mb("64GB") == 65536.0
    assert parse_memory_string_to_mb("128G") == 131072.0

    # TB
    assert parse_memory_string_to_mb("1T") == 1048576.0
    assert parse_memory_string_to_mb("1TB") == 1048576.0

    # KB
    assert parse_memory_string_to_mb("65536K") == 64.0
    assert parse_memory_string_to_mb("65536KB") == 64.0

    # Bytes
    assert parse_memory_string_to_mb("1048576B") == 1.0


def test_parse_memory_string_to_mb_errors() -> None:
    """Test error handling on invalid memory strings."""
    with pytest.raises(HPCMemoryParseError):
        parse_memory_string_to_mb("")

    with pytest.raises(HPCMemoryParseError):
        parse_memory_string_to_mb("invalid")

    with pytest.raises(HPCMemoryParseError):
        parse_memory_string_to_mb("64XYZ")


def test_get_physical_ram_bytes() -> None:
    """Verify physical host RAM probe returns positive byte count."""
    ram = get_physical_ram_bytes()
    assert isinstance(ram, int)
    assert ram > 0


def test_parse_cgroup_memory_limit_v2_and_v1() -> None:
    """Test parsing cgroup v1 and v2 limits using real temporary files."""
    with make_temp_dir() as tmpdir:
        root = Path(tmpdir)

        # Cgroups v2: memory.max
        cgroup_v2_dir = root / "sys" / "fs" / "cgroup"
        cgroup_v2_dir.mkdir(parents=True, exist_ok=True)
        (cgroup_v2_dir / "memory.max").write_text("34359738368\n", encoding="utf-8")  # 32 GB

        limit_v2 = parse_cgroup_memory_limit(root)
        assert limit_v2 == 34359738368

        # When memory.max is "max" (unlimited)
        (cgroup_v2_dir / "memory.max").write_text("max\n", encoding="utf-8")
        assert parse_cgroup_memory_limit(root) is None

        # Cgroups v1: memory.limit_in_bytes
        (cgroup_v2_dir / "memory.max").unlink()
        cgroup_v1_dir = root / "sys" / "fs" / "cgroup" / "memory"
        cgroup_v1_dir.mkdir(parents=True, exist_ok=True)
        (cgroup_v1_dir / "memory.limit_in_bytes").write_text(
            "17179869184\n", encoding="utf-8"
        )  # 16 GB

        limit_v1 = parse_cgroup_memory_limit(root)
        assert limit_v1 == 17179869184


def test_parse_hpc_memory_limit_slurm_per_node() -> None:
    """Test memory limit resolution from SLURM_MEM_PER_NODE."""
    env = {"SLURM_MEM_PER_NODE": "64G"}
    profile = parse_hpc_memory_limit(env=env)
    assert profile.mem_per_node_mb == 65536.0
    assert profile.effective_usable_memory_mb == 65536.0
    assert profile.source == "SLURM_MEM_PER_NODE"


def test_parse_hpc_memory_limit_slurm_per_cpu() -> None:
    """Test memory limit resolution from SLURM_MEM_PER_CPU."""
    env = {"SLURM_MEM_PER_CPU": "4000M"}
    # 8 tasks on node, 2 cpus per task = 16 total cpus -> 64000 MB
    profile = parse_hpc_memory_limit(
        env=env,
        tasks_per_node=[8],
        cpus_per_task=2,
    )
    assert profile.mem_per_cpu_mb == 4000.0
    assert profile.mem_per_node_mb == 64000.0
    assert profile.effective_usable_memory_mb == 64000.0
    assert profile.source == "SLURM_MEM_PER_CPU"


def test_parse_hpc_memory_limit_cgroup() -> None:
    """Test memory limit resolution constrained by cgroups."""
    with make_temp_dir() as tmpdir:
        root = Path(tmpdir)
        cgroup_dir = root / "sys" / "fs" / "cgroup"
        cgroup_dir.mkdir(parents=True, exist_ok=True)
        (cgroup_dir / "memory.max").write_text("17179869184\n", encoding="utf-8")  # 16 GB

        profile = parse_hpc_memory_limit(env={}, cgroup_root=root)
        assert profile.cgroup_limit_bytes == 17179869184
        assert profile.source == "CGROUP"
        assert abs(profile.effective_usable_memory_mb - 16384.0) < 1.0


def test_parse_hpc_memory_limit_physical_ram_fallback() -> None:
    """Test memory limit fallback to host physical RAM."""
    profile = parse_hpc_memory_limit(env={})
    assert profile.source == "PHYSICAL_RAM"
    assert profile.physical_ram_bytes > 0
    assert profile.effective_usable_memory_mb > 0.0


# =============================================================================
# 7. HIERARCHICAL SCRATCH DIRECTORY MAPPING TESTS
# =============================================================================


def test_resolve_hpc_scratch_directory_override() -> None:
    """Test explicit override parameter for scratch directory."""
    with make_temp_dir() as tmpdir:
        custom_scratch = Path(tmpdir) / "custom_scratch"
        profile = resolve_hpc_scratch_directory(override=custom_scratch)
        assert profile.scratch_directory == str(custom_scratch.resolve())
        assert profile.source_variable == "OVERRIDE"
        assert profile.is_accessible is True
        assert profile.is_writable is True
        assert profile.free_disk_space_gb > 0.0


def test_resolve_hpc_scratch_directory_env_hierarchy() -> None:
    """Test priority order across environment variables."""
    with make_temp_dir() as tmpdir:
        tmp_path = Path(tmpdir)
        dir_cochem = tmp_path / "cochem_scratch"
        dir_slurm = tmp_path / "slurm_scratch"
        dir_tmpdir = tmp_path / "tmpdir_scratch"
        dir_scratch = tmp_path / "scratch_base"
        dir_temp = tmp_path / "temp_scratch"

        # 1. COCHEM_SCRATCH_DIR priority over SLURM_TMPDIR
        env1 = {
            "COCHEM_SCRATCH_DIR": str(dir_cochem),
            "SLURM_TMPDIR": str(dir_slurm),
        }
        prof1 = resolve_hpc_scratch_directory(env=env1)
        assert prof1.source_variable == "COCHEM_SCRATCH_DIR"
        assert prof1.scratch_directory == str(dir_cochem.resolve())

        # 2. SLURM_TMPDIR priority over TMPDIR
        env2 = {
            "SLURM_TMPDIR": str(dir_slurm),
            "TMPDIR": str(dir_tmpdir),
        }
        prof2 = resolve_hpc_scratch_directory(env=env2)
        assert prof2.source_variable == "SLURM_TMPDIR"
        assert prof2.scratch_directory == str(dir_slurm.resolve())

        # 3. TMPDIR priority over SCRATCH
        env3 = {
            "TMPDIR": str(dir_tmpdir),
            "SCRATCH": str(dir_scratch),
        }
        prof3 = resolve_hpc_scratch_directory(env=env3)
        assert prof3.source_variable == "TMPDIR"
        assert prof3.scratch_directory == str(dir_tmpdir.resolve())

        # 4. SCRATCH creates CoChem_Scratch subfolder
        env4 = {
            "SCRATCH": str(dir_scratch),
        }
        prof4 = resolve_hpc_scratch_directory(env=env4)
        assert prof4.source_variable == "SCRATCH"
        assert prof4.scratch_directory == str((dir_scratch / "CoChem_Scratch").resolve())


def test_resolve_hpc_scratch_directory_fallback() -> None:
    """Test default fallback scratch directory resolution."""
    prof = resolve_hpc_scratch_directory(env={})
    assert prof.source_variable in ("FALLBACK", "TEMP", "TMP")
    assert Path(prof.scratch_directory).exists()
    assert prof.is_accessible is True


# =============================================================================
# 8. THREAD AFFINITY & PROCESS CORE BINDINGS TESTS
# =============================================================================


def test_compute_thread_affinity_profile_multithreaded_task() -> None:
    """Test thread affinity calculation when cpus_per_task > 1."""
    topology = HPCTopologyProfile(
        scheduler=HPCSchedulerType.SLURM,
        job_id="123",
        num_nodes=1,
        node_list=["node01"],
        tasks_per_node=[2],
        total_tasks=2,
        cpus_per_task=8,
        cpus_on_node=16,
        is_heterogeneous=False,
    )
    affinity = compute_thread_affinity_profile(topology, places_policy="cores", proc_bind="close")
    assert affinity.omp_num_threads == 8
    assert affinity.mkl_num_threads == 8
    assert affinity.openblas_num_threads == 8
    assert affinity.blis_num_threads == 8
    assert affinity.omp_places == "cores"
    assert affinity.omp_proc_bind == "close"
    assert affinity.kmp_affinity == "granularity=fine,compact,1,0"
    assert affinity.kmp_blocktime == 0
    assert affinity.environment_variables["OMP_NUM_THREADS"] == "8"
    assert affinity.environment_variables["MKL_NUM_THREADS"] == "8"


def test_compute_thread_affinity_profile_spread_policy() -> None:
    """Test thread affinity calculation with spread/scatter binding policy."""
    topology = HPCTopologyProfile(
        scheduler=HPCSchedulerType.SLURM,
        job_id="123",
        num_nodes=1,
        node_list=["node01"],
        tasks_per_node=[1],
        total_tasks=1,
        cpus_per_task=16,
        cpus_on_node=16,
        is_heterogeneous=False,
    )
    affinity = compute_thread_affinity_profile(
        topology, places_policy="threads", proc_bind="spread"
    )
    assert affinity.omp_places == "threads"
    assert affinity.omp_proc_bind == "spread"
    assert affinity.kmp_affinity == "granularity=fine,scatter"


def test_generate_environment_injection_dict() -> None:
    """Test generation of complete environment variable injection dictionary."""
    topology = HPCTopologyProfile(
        scheduler=HPCSchedulerType.SLURM,
        job_id="998877",
        num_nodes=2,
        node_list=["node01", "node02"],
        tasks_per_node=[8, 8],
        total_tasks=16,
        cpus_per_task=2,
        cpus_on_node=16,
        is_heterogeneous=False,
    )
    memory = HPCMemoryProfile(
        mem_per_node_mb=64000.0,
        physical_ram_bytes=68719476736,
        effective_usable_memory_mb=64000.0,
        source="SLURM_MEM_PER_NODE",
    )
    scratch = HPCScratchProfile(
        scratch_directory="/tmp/slurm_scratch",
        is_accessible=True,
        is_writable=True,
        free_disk_space_gb=100.0,
        source_variable="SLURM_TMPDIR",
    )
    affinity = compute_thread_affinity_profile(topology)

    injected = generate_environment_injection_dict(topology, memory, scratch, affinity)

    assert injected["OMP_NUM_THREADS"] == "2"
    assert injected["MKL_NUM_THREADS"] == "2"
    assert injected["COCHEM_SCRATCH_DIR"] == "/tmp/slurm_scratch"
    assert injected["COCHEM_HPC_SCHEDULER"] == "SLURM"
    assert injected["COCHEM_NUM_NODES"] == "2"
    assert injected["COCHEM_TOTAL_TASKS"] == "16"
    assert injected["COCHEM_CPUS_PER_TASK"] == "2"
    assert injected["COCHEM_CPUS_ON_NODE"] == "16"
    assert injected["COCHEM_MEMORY_PER_NODE_MB"] == "64000.0"
    assert injected["COCHEM_JOB_ID"] == "998877"
    assert injected["SLURM_TMPDIR"] == "/tmp/slurm_scratch"


# =============================================================================
# 9. REGISTRY PATH & TRANSACTIONAL DEPENDENCY MANAGER TESTS
# =============================================================================


def test_resolve_p7_registry_path() -> None:
    """Test Phase 7 Golden Registry path resolution."""
    with make_temp_dir() as tmpdir:
        tmp_path = Path(tmpdir)

        # 1. Custom directory argument
        p1 = resolve_p7_registry_path(tmp_path)
        assert p1 == (tmp_path / "p7.json").resolve()

        # Direct file argument
        p2 = resolve_p7_registry_path(tmp_path / "p7.json")
        assert p2 == (tmp_path / "p7.json").resolve()


def test_dependency_manager_atomic_commit() -> None:
    """Test transactional commit of p7.json payload via DependencyManager."""
    with make_temp_dir() as tmpdir:
        target = Path(tmpdir) / "Registry" / "p7.json"

        with DependencyManager(target) as dm:
            dm.write_payload({"phase_id": "cochem_setup_phase_7", "status": "PASSED"})

        assert target.exists()
        content = json.loads(target.read_text(encoding="utf-8"))
        assert content["phase_id"] == "cochem_setup_phase_7"
        assert content["status"] == "PASSED"


def test_dependency_manager_rollback_on_exception() -> None:
    """Test that DependencyManager cleans up temporary files when an exception occurs."""
    with make_temp_dir() as tmpdir:
        target = Path(tmpdir) / "Registry" / "p7.json"

        with pytest.raises(RuntimeError):
            with DependencyManager(target) as dm:
                dm.write_payload({"status": "CORRUPTED"})
                raise RuntimeError("Simulated calculation crash")

        # Destination must not exist
        assert not target.exists()
        # No orphan temp files left
        assert len(list(target.parent.glob("*.tmp_*"))) == 0


# =============================================================================
# 10. MASTER PHASE 7 AUDIT END-TO-END TESTS
# =============================================================================


def test_run_phase_7_audit_slurm_end_to_end() -> None:
    """Test full Phase 7 audit execution in a Slurm cluster environment."""
    with make_temp_dir() as tmpdir:
        out_dir = Path(tmpdir) / "Registry"
        scratch_dir = Path(tmpdir) / "Scratch"

        env = {
            "SLURM_JOB_ID": "556677",
            "SLURM_NODELIST": "gpu_node[01-02]",
            "SLURM_NNODES": "2",
            "SLURM_TASKS_PER_NODE": "4(x2)",
            "SLURM_CPUS_PER_TASK": "4",
            "SLURM_CPUS_ON_NODE": "16",
            "SLURM_MEM_PER_NODE": "128G",
            "SLURM_TMPDIR": str(scratch_dir),
        }

        report = run_phase_7_audit(
            output_dir=out_dir,
            scratch_dir=scratch_dir,
            env=env,
            places_policy="cores",
            proc_bind="close",
            dry_run=False,
        )

        assert report.status == PhaseStatus.PASSED
        assert report.scheduler_detected == HPCSchedulerType.SLURM
        assert report.topology.job_id == "556677"
        assert report.topology.num_nodes == 2
        assert report.topology.node_list == ["gpu_node01", "gpu_node02"]
        assert report.topology.total_tasks == 8
        assert report.topology.cpus_per_task == 4
        assert report.affinity.omp_num_threads == 4
        assert report.memory.mem_per_node_mb == 131072.0
        assert report.scratch.scratch_directory == str(scratch_dir.resolve())
        assert report.scratch.is_writable is True
        assert len(report.errors) == 0

        # Verify registry artifact persistence
        registry_file = out_dir / "p7.json"
        assert registry_file.exists()
        saved = json.loads(registry_file.read_text(encoding="utf-8"))
        assert saved["scheduler_detected"] == "SLURM"
        assert saved["topology"]["total_tasks"] == 8


def test_run_phase_7_audit_pbs_end_to_end() -> None:
    """Test full Phase 7 audit execution in a PBS environment."""
    with make_temp_dir() as tmpdir:
        out_dir = Path(tmpdir) / "Registry"
        nodefile = Path(tmpdir) / "pbs_nodes"
        nodefile.write_text("pbs_n1\npbs_n1\npbs_n2\npbs_n2\n", encoding="utf-8")

        env = {
            "PBS_JOBID": "1234.pbs_server",
            "PBS_NODEFILE": str(nodefile),
            "TMPDIR": str(Path(tmpdir) / "pbs_scratch"),
        }

        report = run_phase_7_audit(
            output_dir=out_dir,
            env=env,
            dry_run=False,
        )

        assert report.status == PhaseStatus.PASSED
        assert report.scheduler_detected == HPCSchedulerType.PBS
        assert report.topology.num_nodes == 2
        assert report.topology.total_tasks == 4


def test_run_phase_7_audit_standalone_end_to_end() -> None:
    """Test full Phase 7 audit execution in local standalone workstation mode."""
    with make_temp_dir() as tmpdir:
        out_dir = Path(tmpdir) / "Registry"

        report = run_phase_7_audit(
            output_dir=out_dir,
            env={},
            dry_run=False,
        )

        assert report.status == PhaseStatus.PASSED
        assert report.scheduler_detected == HPCSchedulerType.LOCAL_STANDALONE
        assert report.topology.num_nodes == 1
        assert report.topology.total_tasks == 1
        assert (out_dir / "p7.json").exists()


def test_run_phase_7_audit_dry_run() -> None:
    """Test dry-run mode does not create physical registry file."""
    with make_temp_dir() as tmpdir:
        out_dir = Path(tmpdir) / "Registry"
        report = run_phase_7_audit(
            output_dir=out_dir,
            env={},
            dry_run=True,
        )
        assert report.status == PhaseStatus.PASSED
        assert not (out_dir / "p7.json").exists()


# =============================================================================
# 11. CLI ENTRYPOINT TESTS
# =============================================================================


def test_main_cli_success() -> None:
    """Test main CLI entrypoint with standard dry-run argument."""
    with make_temp_dir() as tmpdir:
        out_dir = str(Path(tmpdir) / "Registry")
        ret = main(["--output-dir", out_dir, "--dry-run"])
        assert ret == 0


def test_main_cli_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    """Test main CLI entrypoint with --json flag."""
    with make_temp_dir() as tmpdir:
        out_dir = str(Path(tmpdir) / "Registry")
        ret = main(["--output-dir", out_dir, "--dry-run", "--json"])
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["phase_id"] == "cochem_setup_phase_7"
        assert "topology" in data
        assert "memory" in data
        assert "affinity" in data


# =============================================================================
# 12. ADVERSARIAL EDGE CASE TESTS
# =============================================================================


def test_resolve_p7_registry_path_from_env() -> None:
    """Test p7 registry path resolution from environment variables."""
    with make_temp_dir() as tmpdir:
        reg_dir = Path(tmpdir) / "custom_reg"
        os.environ["COCHEM_REGISTRY_DIR"] = str(reg_dir)
        try:
            assert resolve_p7_registry_path() == (reg_dir / "p7.json").resolve()
        finally:
            del os.environ["COCHEM_REGISTRY_DIR"]

    with make_temp_dir() as tmpdir:
        art_dir = Path(tmpdir) / "custom_art"
        os.environ["COCHEM_ARTIFACT_DIR"] = str(art_dir)
        try:
            assert resolve_p7_registry_path() == (art_dir / "Registry" / "p7.json").resolve()
        finally:
            del os.environ["COCHEM_ARTIFACT_DIR"]


def test_parse_slurm_topology_ntasks_fallback() -> None:
    """Test Slurm topology parsing when SLURM_TASKS_PER_NODE is absent but SLURM_NTASKS is present."""
    env = {
        "SLURM_JOB_ID": "8877",
        "SLURM_NNODES": "2",
        "SLURM_NTASKS": "8",
    }
    topo = parse_slurm_topology(env)
    assert topo.num_nodes == 2
    assert topo.tasks_per_node == [4, 4]
    assert topo.total_tasks == 8


def test_expand_single_node_spec_triple_dash_error() -> None:
    """Test error handling for node range with multiple dashes."""
    with pytest.raises(HPCTopologyError):
        _expand_single_node_spec("node[01-02-03]")


def test_affinity_profile_compact_and_master_binds() -> None:
    """Test thread affinity calculations with compact and master bindings."""
    topo = parse_standalone_topology({})
    aff_compact = compute_thread_affinity_profile(topo, proc_bind="compact")
    assert aff_compact.omp_proc_bind == "compact"
    assert aff_compact.kmp_affinity == "granularity=fine,compact,1,0"

    aff_master = compute_thread_affinity_profile(topo, proc_bind="master")
    assert aff_master.omp_proc_bind == "master"
    assert aff_master.kmp_affinity == "granularity=fine,compact,1,0"


def test_run_phase_7_audit_with_errors() -> None:
    """Test audit orchestrator gracefully handles invalid memory and topology input."""
    env = {
        "SLURM_JOB_ID": "111",
        "SLURM_NODELIST": "node[05-01]",  # descending range -> triggers error catch
    }
    report = run_phase_7_audit(env=env, dry_run=True)
    assert report.status == PhaseStatus.FAILED
    assert len(report.errors) > 0

