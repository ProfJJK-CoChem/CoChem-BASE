#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Zero-Mock Physical Test Suite for CoChem-BASE Temporal Router Subsystem.
Tests:
1. 10-Tier Temporal Wall Clock Matrix & Slurm Parameter Formatting.
2. Strict EMT Eradication (Zero-Tolerance).
3. Topological & Theoretical Classification Matrix.
4. gpu4pyscf (v1.8.0 FP64) Hardware & Method Crossover Gating.
5. Asyncio Timeout Enforcement & Callback Hooks.
6. Nvidia MPS Ephemeral Directory Provisioning & Parsl Heterogeneous Configs.
7. Resizable, Chunked, Gzip+Fletcher32 HDF5 PESStore Real I/O.
8. Soft Preemption Signal Emission (Windows CTRL_BREAK_EVENT / POSIX SIGUSR1).
9. Thermal Guard Daemon Process Tree Recursive Suspend & Resume.
"""

from __future__ import annotations

import asyncio
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import psutil
import pytest

from core_engine.cochem_temporal_router import (
    TIER_REGISTRY,
    JobSpec,
    PESStore,
    PreemptionTimer,
    TemporalTier,
    ThermalGuardDaemon,
    ThermalState,
    async_execute_with_tier_timeout,
    build_parsl_hetero_config,
    classify_job_tier,
    estimate_basis_count,
    format_slurm_time,
    get_asyncio_timeout,
    provision_mps_environment,
    route_electronic_structure,
    send_soft_preemption_signal,
    validate_theory_cleanliness,
)

# =====================================================================
# 1. 10-Tier Temporal Wall Clock Matrix & Slurm Formatting Tests
# =====================================================================

def test_tier_registry_completeness() -> None:
    """Validates that all 10 discrete tiers are registered with exact timings."""
    expected_tiers = [
        ("10s", 10, "00:00:10"),
        ("1min", 60, "00:01:00"),
        ("30min", 1800, "00:30:00"),
        ("1h", 3600, "01:00:00"),
        ("3h", 10800, "03:00:00"),
        ("12h", 43200, "12:00:00"),
        ("1d", 86400, "1-00:00:00"),
        ("3d", 259200, "3-00:00:00"),
        ("1w", 604800, "7-00:00:00"),
        ("1mo", 2592000, "30-00:00:00"),
    ]

    assert len(TIER_REGISTRY) == 10
    for name, walltime, slurm in expected_tiers:
        tier_enum = TemporalTier(name)
        meta = TIER_REGISTRY[tier_enum]
        assert meta.tier.value == name
        assert meta.walltime_seconds == walltime
        assert meta.slurm_time == slurm
        assert len(meta.recommended_methods) > 0


def test_format_slurm_time_all_variants() -> None:
    """Tests Slurm time string formatting from enums, strings, and integer seconds."""
    assert format_slurm_time(TemporalTier.TIER_1_10S) == "00:00:10"
    assert format_slurm_time(TemporalTier.TIER_2_1MIN) == "00:01:00"
    assert format_slurm_time(TemporalTier.TIER_3_30MIN) == "00:30:00"
    assert format_slurm_time(TemporalTier.TIER_4_1H) == "01:00:00"
    assert format_slurm_time(TemporalTier.TIER_5_3H) == "03:00:00"
    assert format_slurm_time(TemporalTier.TIER_6_12H) == "12:00:00"
    assert format_slurm_time(TemporalTier.TIER_7_1D) == "1-00:00:00"
    assert format_slurm_time(TemporalTier.TIER_8_3D) == "3-00:00:00"
    assert format_slurm_time(TemporalTier.TIER_9_1W) == "7-00:00:00"
    assert format_slurm_time(TemporalTier.TIER_10_1MO) == "30-00:00:00"

    # String parsing
    assert format_slurm_time("10s") == "00:00:10"
    assert format_slurm_time("12h") == "12:00:00"
    assert format_slurm_time("1w") == "7-00:00:00"

    # Numeric seconds
    assert format_slurm_time(15) == "00:00:15"
    assert format_slurm_time(3665) == "01:01:05"
    assert format_slurm_time(90000) == "1-01:00:00"


def test_get_asyncio_timeout() -> None:
    """Verifies floating point timeout extraction across all tiers."""
    assert get_asyncio_timeout(TemporalTier.TIER_1_10S) == 10.0
    assert get_asyncio_timeout(TemporalTier.TIER_3_30MIN) == 1800.0
    assert get_asyncio_timeout("1h") == 3600.0
    assert get_asyncio_timeout(45.5) == 45.5


# =====================================================================
# 2. Strict EMT Eradication (Zero-Tolerance) Tests
# =====================================================================

def test_emt_eradication_in_jobspec_method() -> None:
    """Asserts that EMT in method raises ValueError immediately."""
    with pytest.raises(ValueError, match="CRITICAL METHOD ERROR: EMT"):
        JobSpec(n_atoms=6, method="EMT")

    with pytest.raises(ValueError, match="CRITICAL METHOD ERROR: EMT"):
        JobSpec(n_atoms=6, method="effective_medium_theory")

    with pytest.raises(ValueError, match="CRITICAL METHOD ERROR: EMT"):
        JobSpec(n_atoms=6, method="ASE_EMT")


def test_emt_eradication_in_jobspec_keywords() -> None:
    """Asserts that EMT inside nested keywords raises ValueError."""
    with pytest.raises(ValueError, match="CRITICAL METHOD ERROR: EMT"):
        JobSpec(n_atoms=6, method="GFN2-xTB", keywords={"calc_engine": "EMT"})

    with pytest.raises(ValueError, match="CRITICAL METHOD ERROR: EMT"):
        JobSpec(n_atoms=6, method="GFN2-xTB", keywords={"options": {"fallback": "effective medium theory"}})


def test_validate_theory_cleanliness_direct() -> None:
    """Asserts direct validate_theory_cleanliness raises on EMT in lists, dicts, strings."""
    with pytest.raises(ValueError):
        validate_theory_cleanliness("emt")

    with pytest.raises(ValueError):
        validate_theory_cleanliness(["b3lyp", "emt", "ccsd"])

    with pytest.raises(ValueError):
        validate_theory_cleanliness({"theory": {"level": "effective_medium_theory"}})

    with pytest.raises(ValueError):
        validate_theory_cleanliness("dft+emt")

    with pytest.raises(ValueError):
        validate_theory_cleanliness("emt-scf")

    with pytest.raises(ValueError):
        validate_theory_cleanliness("ase/emt")

    # Valid methods pass cleanly
    validate_theory_cleanliness("wB97M-V")
    validate_theory_cleanliness({"method": "DLPNO-CCSD(T)", "basis": "def2-QZVPP"})
    validate_theory_cleanliness("femtosecond_dynamics")


# =====================================================================
# 3. Temporal Matrix Classification Logic Tests
# =====================================================================

def test_classify_tier_1_sub_10s() -> None:
    """Tests sub-10s classification for fast screening methods."""
    job_screen = JobSpec(n_atoms=10, method="AIMNet2", task_type="screen")
    assert classify_job_tier(job_screen) == TemporalTier.TIER_1_10S

    job_gxtb = JobSpec(n_atoms=8, method="GFN2-xTB", task_type="energy")
    assert classify_job_tier(job_gxtb) == TemporalTier.TIER_1_10S


def test_classify_tier_2_1min() -> None:
    """Tests 1-minute coarse optimization tier."""
    job_opt = JobSpec(n_atoms=12, method="GFN2-xTB", task_type="opt")
    assert classify_job_tier(job_opt) == TemporalTier.TIER_2_1MIN

    job_pm6 = JobSpec(n_atoms=15, method="PM6", task_type="opt")
    assert classify_job_tier(job_pm6) == TemporalTier.TIER_2_1MIN


def test_classify_tier_3_30min() -> None:
    """Tests 30-minute composite DFT & CREST search tier."""
    job_r2scan = JobSpec(n_atoms=14, method="r2SCAN-3c", task_type="opt")
    assert classify_job_tier(job_r2scan) == TemporalTier.TIER_3_30MIN

    job_crest = JobSpec(n_atoms=16, method="GFN2-xTB", task_type="global_search")
    assert classify_job_tier(job_crest) == TemporalTier.TIER_3_30MIN


def test_classify_tier_4_1h() -> None:
    """Tests 1-hour standard DFT geometry optimization."""
    job_dft = JobSpec(n_atoms=10, n_heavy_atoms=6, method="B3LYP", basis="def2-TZVP", task_type="opt")
    assert classify_job_tier(job_dft) == TemporalTier.TIER_4_1H


def test_classify_tier_5_3h() -> None:
    """Tests 3-hour Recipe R2 high-level DFT & VPT2."""
    job_r2 = JobSpec(n_atoms=10, n_heavy_atoms=6, method="wB97M-V", basis="def2-QZVPP", task_type="vpt2")
    assert classify_job_tier(job_r2) == TemporalTier.TIER_5_3H


def test_classify_tier_6_12h() -> None:
    """Tests 12-hour junChS composite and active-learning PES."""
    job_junchs = JobSpec(n_atoms=12, n_heavy_atoms=6, method="junChS", task_type="energy")
    assert classify_job_tier(job_junchs) == TemporalTier.TIER_6_12H


def test_classify_tier_7_1d() -> None:
    """Tests 1-day DLPNO-CCSD(T) optimization."""
    job_dlpno = JobSpec(n_atoms=10, n_heavy_atoms=5, method="DLPNO-CCSD(T)", basis="cc-pVTZ", task_type="opt")
    assert classify_job_tier(job_dlpno) == TemporalTier.TIER_7_1D


def test_classify_tier_8_3d() -> None:
    """Tests 3-day CFOUR analytic 2nd derivatives & 6D variational PES."""
    job_cfour = JobSpec(n_atoms=8, n_heavy_atoms=4, method="CFOUR-CCSD(T)", task_type="freq")
    assert classify_job_tier(job_cfour) == TemporalTier.TIER_8_3D


def test_classify_tier_9_1w() -> None:
    """Tests 1-week full anharmonic coupled-cluster force field."""
    job_anharm = JobSpec(n_atoms=8, n_heavy_atoms=4, method="CCSD(T)", task_type="anharmonic_ff")
    assert classify_job_tier(job_anharm) == TemporalTier.TIER_9_1W


def test_classify_tier_10_1mo() -> None:
    """Tests 1-month campaign-scale Coupled Cluster / CBS extrapolation."""
    job_campaign = JobSpec(n_atoms=30, n_heavy_atoms=18, method="CCSD(T)", task_type="anharmonic_ff")
    assert classify_job_tier(job_campaign) == TemporalTier.TIER_10_1MO


# =====================================================================
# 4. gpu4pyscf Routing & Crossover Tests
# =====================================================================

def test_estimate_basis_count() -> None:
    """Tests basis function count estimation for crossover gate."""
    # Water dimer (H2O)2: 2 oxygen (heavy), 4 hydrogen
    # def2-TZVP: 2 * 28 + 4 * 8 = 56 + 32 = 88 bf
    bf_tz = estimate_basis_count(n_atoms=6, symbols=["O", "H", "H", "O", "H", "H"], basis="def2-tzvp")
    assert bf_tz == 88

    # def2-QZVP: 2 * 55 + 4 * 14 = 110 + 56 = 166 bf
    bf_qz = estimate_basis_count(n_atoms=6, symbols=["O", "H", "H", "O", "H", "H"], basis="def2-qzvpp")
    assert bf_qz == 166


def test_gpu4pyscf_routing_large_system_with_gpu() -> None:
    """Asserts supported DFT on system above crossover routes to gpu4pyscf FP64 on GPU."""
    job = JobSpec(
        n_atoms=12,
        symbols=["C", "C", "O", "O", "H", "H", "H", "H", "H", "H", "H", "H"],
        method="wB97M-V",
        basis="def2-TZVP",
        task_type="opt",
        has_gpu=True,
        density_fitting=True,
    )
    decision = route_electronic_structure(job)
    assert decision.engine == "gpu4pyscf"
    assert decision.device == "gpu"
    assert decision.precision == "FP64"
    assert decision.density_fitting is True


def test_gpu4pyscf_routing_forbidden_methods() -> None:
    """Asserts double hybrids and coupled-cluster are rejected on GPU and route to CPU."""
    job_cc = JobSpec(
        n_atoms=8,
        method="DLPNO-CCSD(T)",
        basis="def2-TZVP",
        task_type="energy",
        has_gpu=True,
    )
    decision_cc = route_electronic_structure(job_cc)
    assert decision_cc.device == "cpu"
    assert decision_cc.engine == "orca"

    job_dh = JobSpec(
        n_atoms=8,
        method="double_hybrid",
        basis="def2-TZVP",
        task_type="energy",
        has_gpu=True,
    )
    decision_dh = route_electronic_structure(job_dh)
    assert decision_dh.device == "cpu"


def test_gpu4pyscf_routing_small_sub_crossover() -> None:
    """Asserts sub-crossover systems (<50 bf) prefer CPU / ORCA."""
    job_small = JobSpec(
        n_atoms=2,
        symbols=["H", "H"],
        method="B3LYP",
        basis="sto-3g",
        task_type="energy",
        has_gpu=True,
    )
    decision = route_electronic_structure(job_small)
    assert decision.device == "cpu"
    assert decision.engine == "orca"


def test_gpu4pyscf_routing_high_angular_momentum() -> None:
    """Asserts basis sets exceeding g-functions (e.g. h/i) route to CPU."""
    job_high_l = JobSpec(
        n_atoms=10,
        symbols=["C", "C", "H", "H", "H", "H", "H", "H", "H", "H"],
        method="B3LYP",
        basis="cc-pV5Z",
        task_type="energy",
        has_gpu=True,
    )
    decision = route_electronic_structure(job_high_l)
    assert decision.device == "cpu"


def test_no_gpu_routing_falls_back_to_cpu() -> None:
    """Asserts that absence of GPU routes DFT calculations to CPU (ORCA)."""
    job = JobSpec(
        n_atoms=12,
        symbols=["C", "C", "O", "O", "H", "H", "H", "H", "H", "H", "H", "H"],
        method="wB97M-V",
        basis="def2-TZVP",
        task_type="opt",
        has_gpu=False,
    )
    decision = route_electronic_structure(job)
    assert decision.engine == "orca"
    assert decision.device == "cpu"
    assert decision.precision == "FP64"


# =====================================================================
# 5. Asyncio Timeout Enforcement Tests
# =====================================================================

def test_async_execute_with_tier_timeout_success() -> None:
    """Asserts successful execution of fast coroutine under tier timeout."""
    async def _runner() -> int:
        async def fast_task() -> int:
            await asyncio.sleep(0.01)
            return 42

        val: int = await async_execute_with_tier_timeout(fast_task(), TemporalTier.TIER_1_10S)
        return val

    res = asyncio.run(_runner())
    assert res == 42


def test_async_execute_with_tier_timeout_breach() -> None:
    """Asserts that exceeding tier timeout raises TimeoutError and calls hook."""
    callback_fired = False

    def on_timeout() -> None:
        nonlocal callback_fired
        callback_fired = True

    async def _runner() -> None:
        async def slow_task() -> None:
            await asyncio.sleep(1.0)

        with pytest.raises(asyncio.TimeoutError):
            await async_execute_with_tier_timeout(slow_task(), tier_or_seconds=0.05, timeout_callback=on_timeout)

    asyncio.run(_runner())
    assert callback_fired is True


# =====================================================================
# 6. Nvidia MPS & Parsl Heterogeneous Configuration Tests
# =====================================================================

def test_provision_mps_environment() -> None:
    """Tests ephemeral MPS directory tree creation and permission lockdown."""
    with tempfile.TemporaryDirectory() as temp_root:
        env = provision_mps_environment(
            ephemeral_root=temp_root,
            active_thread_pct=33,
            pinned_mem_limit="0=6G",
            user="testuser",
        )

        assert "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE" in env
        assert env["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] == "33"
        assert env["CUDA_MPS_PINNED_DEVICE_MEM_LIMIT"] == "0=6G"

        pipe_dir = Path(env["CUDA_MPS_PIPE_DIRECTORY"])
        log_dir = Path(env["CUDA_MPS_LOG_DIRECTORY"])

        assert pipe_dir.exists() and pipe_dir.is_dir()
        assert log_dir.exists() and log_dir.is_dir()


def test_build_parsl_hetero_config() -> None:
    """Tests Parsl two-executor configuration construction."""
    with tempfile.TemporaryDirectory() as temp_root:
        config = build_parsl_hetero_config(
            cpu_workers=1,
            cpu_cores_per_worker=7,
            gpu_workers=3,
            ephemeral_dir=temp_root,
            provider_type="local",
        )

        if hasattr(config, "executors"):
            executor_labels = [e.label for e in config.executors]
            assert "cpu" in executor_labels
            assert "gpu" in executor_labels
        else:
            assert "executors" in config
            assert "cpu" in config["executors"]
            assert "gpu" in config["executors"]


# =====================================================================
# 7. Resizable HDF5 PESStore Real I/O Tests
# =====================================================================

def test_pes_store_lifecycle_and_provenance() -> None:
    """Performs real chunked HDF5 I/O, QCSchema attributes, and delta pairs."""
    with tempfile.TemporaryDirectory() as temp_root:
        h5_path = Path(temp_root) / "pes_campaign.h5"
        store = PESStore(h5_path, complex_name="Ar-HCl", symbols=["Ar", "H", "Cl"])

        # 1. Register methods
        store.register_method(
            "dlpno_avtz",
            method="DLPNO-CCSD(T1)",
            basis="cc-pVDZ-F12",
            program="ORCA",
            driver="energy",
        )
        store.register_method(
            "dft_base",
            method="wB97M-V",
            basis="def2-TZVP",
            program="ORCA",
            driver="energy",
        )

        # 2. Add points
        coords_low = np.random.randn(5, 3, 3)
        energies_low = np.array([-560.1, -560.2, -560.15, -560.18, -560.22])
        point_ids = [f"g2d:{i}" for i in range(5)]

        store.add_points("dft_base", coords_low, energies_low, point_ids=point_ids)

        coords_high = coords_low[:3]
        energies_high = np.array([-560.12, -560.23, -560.17])
        store.add_points("dlpno_avtz", coords_high, energies_high, point_ids=point_ids[:3])

        # 3. Test todo list for refinement
        all_wanted = [f"g2d:{i}" for i in range(5)]
        missing_dlpno = store.todo("dlpno_avtz", all_wanted)
        assert missing_dlpno == ["g2d:3", "g2d:4"]

        # 4. Dataset readback
        coords_read, e_read = store.dataset("dft_base")
        assert len(e_read) == 5
        assert np.allclose(e_read, energies_low)  # type: ignore[attr-defined]

        # 5. Delta pairs
        keys, x_delta, de_delta = store.delta_pairs("dft_base", "dlpno_avtz")
        assert len(keys) == 3
        assert np.allclose(de_delta, energies_high - energies_low[:3])  # type: ignore[attr-defined]

        # 6. Cartesian Hessian storage
        hessian = np.eye(9) * 0.05
        store.add_hessian("min_01", hessian, level="wB97M-V/def2-TZVP", geometry_ref="g2d:0")

        # 7. Checkpoint state serialization and restore
        checkpoint_data = {
            "iteration": 12,
            "fmax": 0.008,
            "converged": True,
            "gradient_norm": 0.0001,
            "last_coords": coords_low[0],
        }
        store.checkpoint_state("opt_cycle_12", checkpoint_data)
        restored = store.read_checkpoint("opt_cycle_12")

        assert restored["iteration"] == 12
        assert restored["converged"] is True
        assert np.allclose(restored["last_coords"], coords_low[0])  # type: ignore[attr-defined]


# =====================================================================
# 8. Graceful Degradation & Preemption Timers Tests
# =====================================================================

def test_soft_preemption_signal_real_process() -> None:
    """Spawns real subprocess and delivers soft preemption signal."""
    # Script that traps SIGBREAK on Windows or SIGUSR1/SIGTERM on POSIX
    worker_script = """
import signal, time, sys

def on_signal(signum, frame):
    with open('caught_signal.txt', 'w') as f:
        f.write(f'SIGNAL_{signum}')
    sys.exit(0)

if hasattr(signal, 'SIGBREAK'):
    signal.signal(signal.SIGBREAK, on_signal)
if hasattr(signal, 'SIGUSR1'):
    signal.signal(signal.SIGUSR1, on_signal)
if hasattr(signal, 'SIGTERM'):
    signal.signal(signal.SIGTERM, on_signal)

for _ in range(100):
    time.sleep(0.1)
"""
    with tempfile.TemporaryDirectory() as temp_dir:
        cwd_path = Path(temp_dir)
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if platform.system() == "Windows" else 0
        proc = subprocess.Popen(
            [sys.executable, "-c", worker_script],
            cwd=str(cwd_path),
            creationflags=creationflags,
        )

        time.sleep(0.4)
        sent = send_soft_preemption_signal(proc)
        assert sent is True

        proc.wait(timeout=5.0)
        signal_file = cwd_path / "caught_signal.txt"
        assert signal_file.exists()


def test_preemption_timer_triggers_callback() -> None:
    """Verifies that PreemptionTimer executes registered checkpoint callback on TTL breach."""
    callback_fired = False

    def on_preempt() -> None:
        nonlocal callback_fired
        callback_fired = True

    timer = PreemptionTimer(
        ttl_seconds=0.3,
        lead_time_seconds=0.15,
        on_preempt_callback=on_preempt,
    )
    timer.start()

    time.sleep(0.4)
    assert callback_fired is True
    assert timer.is_preempted() is True


# =====================================================================
# 9. Thermal Guard Daemon Process Tree Suspend & Resume Tests
# =====================================================================

def test_thermal_guard_suspend_and_resume_cycle() -> None:
    """Spawns real child process tree, tests recursive suspend on breach and resume on recovery."""
    parent_script = """
import subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c', 'import time; [time.sleep(0.1) for _ in range(100)]'])
for _ in range(100):
    time.sleep(0.1)
"""
    proc = subprocess.Popen([sys.executable, "-c", parent_script])
    time.sleep(0.5)

    p_parent = psutil.Process(proc.pid)
    daemon = ThermalGuardDaemon(
        high_temp_threshold=85.0,
        recovery_temp_threshold=75.0,
        target_pids=[proc.pid],
    )

    try:
        # 1. Normal state
        state_init = daemon.check_thermal_cycle(simulated_temp=70.0)
        assert state_init == ThermalState.NORMAL

        # 2. Breach threshold (>85°C) -> Suspend process tree
        state_breach = daemon.check_thermal_cycle(simulated_temp=90.0)
        assert state_breach == ThermalState.SUSPENDED
        time.sleep(0.1)

        # Verify parent is suspended / stopped
        assert p_parent.status() in (psutil.STATUS_STOPPED, "stopped")

        # 3. Intermediate temp -> Stays suspended
        state_mid = daemon.check_thermal_cycle(simulated_temp=80.0)
        assert state_mid == ThermalState.SUSPENDED

        # 4. Cooled below recovery threshold (<75°C) -> Resume process tree
        state_recovery = daemon.check_thermal_cycle(simulated_temp=72.0)
        assert state_recovery == ThermalState.NORMAL
        time.sleep(0.1)

        # Verify parent is running again
        assert p_parent.status() in (psutil.STATUS_RUNNING, "running")

    finally:
        daemon.check_thermal_cycle(simulated_temp=60.0)
        for child in p_parent.children(recursive=True):
            try:
                child.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        proc.terminate()
        proc.wait(timeout=3.0)


def test_thermal_guard_async_lifecycle() -> None:
    """Verifies async start, loop monitoring, and clean shutdown of ThermalGuardDaemon."""
    async def _runner() -> None:
        current_temp = 65.0

        def probe() -> float:
            return current_temp

        daemon = ThermalGuardDaemon(
            high_temp_threshold=85.0,
            recovery_temp_threshold=75.0,
            check_interval_seconds=0.05,
            temperature_probe_fn=probe,
        )

        await daemon.start()
        assert daemon._running is True

        await asyncio.sleep(0.1)
        assert daemon.state == ThermalState.NORMAL

        # Simulate spike
        current_temp = 92.0
        await asyncio.sleep(0.15)
        assert daemon.state == ThermalState.SUSPENDED

        # Simulate cooling
        current_temp = 68.0
        await asyncio.sleep(0.15)
        assert daemon.state == ThermalState.NORMAL

        await daemon.stop()
        assert daemon._running is False

    asyncio.run(_runner())
