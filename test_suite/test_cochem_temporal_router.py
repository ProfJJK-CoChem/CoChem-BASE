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
10. Method Matrix v4 §8D CC Analytical Hessian 3-Tier Routing Protocol.
11. Method Matrix v4 §8.5 Authoritative route() Execution across Setup 1/2/3.
12. Method Matrix v4 §8A.5 Integrity Guards G1–G7 & Audit Trail JSONL Logger.
13. Method Matrix v4 §8B.5 Dangerous Reuses Guards D1–D5.
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
    TIER_3_PROMPT_DIALOGUE,
    AuditTrailLogger,
    AuthorityLevel,
    CCTier,
    JobSpec,
    PESStore,
    PreemptionTimer,
    ProductClass,
    ProvenanceEvent,
    RotationalConstantQuantity,
    RoutingDecision,
    SetupEnvironment,
    TemporalTier,
    ThermalGuardDaemon,
    ThermalState,
    Tier3Option,
    Tier3PromptRequired,
    async_execute_with_tier_timeout,
    build_parsl_hetero_config,
    check_guard_g3_basin_identity,
    check_guard_g5_uncertainty,
    classify_job_tier,
    estimate_basis_count,
    evaluate_guard_g4_rank_inversion,
    evaluate_guard_g6_abort_guide,
    format_slurm_time,
    get_asyncio_timeout,
    provision_mps_environment,
    record_guard_g7_determinism,
    route,
    route_cc_analytical_hessian,
    route_electronic_structure,
    send_soft_preemption_signal,
    validate_guard_d1_geometry_stationarity,
    validate_guard_d2_hessian_stationarity,
    validate_guard_d3_scf_stability,
    validate_guard_d4_counterpoise_integrity,
    validate_guard_d5_unique_base_name,
    validate_guard_g1_scout_advisory,
    validate_guard_g2_high_level_hessian,
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
    bf_tz = estimate_basis_count(n_atoms=6, symbols=["O", "H", "H", "O", "H", "H"], basis="def2-tzvp")
    assert bf_tz == 88

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

        coords_low = np.random.randn(5, 3, 3)
        energies_low = np.array([-560.1, -560.2, -560.15, -560.18, -560.22])
        point_ids = [f"g2d:{i}" for i in range(5)]

        store.add_points("dft_base", coords_low, energies_low, point_ids=point_ids)

        coords_high = coords_low[:3]
        energies_high = np.array([-560.12, -560.23, -560.17])
        store.add_points("dlpno_avtz", coords_high, energies_high, point_ids=point_ids[:3])

        all_wanted = [f"g2d:{i}" for i in range(5)]
        missing_dlpno = store.todo("dlpno_avtz", all_wanted)
        assert missing_dlpno == ["g2d:3", "g2d:4"]

        coords_read, e_read = store.dataset("dft_base")
        assert len(e_read) == 5
        assert np.allclose(e_read, energies_low)

        keys, x_delta, de_delta = store.delta_pairs("dft_base", "dlpno_avtz")
        assert len(keys) == 3
        assert np.allclose(de_delta, energies_high - energies_low[:3])

        hessian = np.eye(9) * 0.05
        store.add_hessian("min_01", hessian, level="wB97M-V/def2-TZVP", geometry_ref="g2d:0")

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
        assert np.allclose(restored["last_coords"], coords_low[0])


# =====================================================================
# 8. Graceful Degradation & Preemption Timers Tests
# =====================================================================

def test_soft_preemption_signal_real_process() -> None:
    """Spawns real subprocess and delivers soft preemption signal."""
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
        state_init = daemon.check_thermal_cycle(simulated_temp=70.0)
        assert state_init == ThermalState.NORMAL

        state_breach = daemon.check_thermal_cycle(simulated_temp=90.0)
        assert state_breach == ThermalState.SUSPENDED
        time.sleep(0.1)
        assert p_parent.status() in (psutil.STATUS_STOPPED, "stopped")

        state_mid = daemon.check_thermal_cycle(simulated_temp=80.0)
        assert state_mid == ThermalState.SUSPENDED

        state_recovery = daemon.check_thermal_cycle(simulated_temp=72.0)
        assert state_recovery == ThermalState.NORMAL
        time.sleep(0.1)
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

        current_temp = 92.0
        await asyncio.sleep(0.15)
        assert daemon.state == ThermalState.SUSPENDED

        current_temp = 68.0
        await asyncio.sleep(0.15)
        assert daemon.state == ThermalState.NORMAL

        await daemon.stop()
        assert daemon._running is False

    asyncio.run(_runner())


# =====================================================================
# 10. Method Matrix v4 §8D CC Analytical Hessian 3-Tier Routing Tests
# =====================================================================

def test_cc_tier_1_cfour_routing() -> None:
    """Tier 1: CFOUR detected -> routes directly to analytic CCSD(T) second derivatives."""
    decision = route_cc_analytical_hessian(engine="cfour", system_n_atoms=10)
    assert decision.tier == CCTier.TIER_1_CFOUR
    assert decision.analytic_hessian is True
    assert decision.single_points_required == 49
    assert decision.prompt_dialogue is None


def test_cc_tier_2_orca_routing() -> None:
    """Tier 2: ORCA detected -> routes to canonical AUTOCI gradient differences or DFT-VPT2."""
    decision = route_cc_analytical_hessian(engine="orca", system_n_atoms=10)
    assert decision.tier == CCTier.TIER_2_ORCA
    assert decision.analytic_hessian is False
    assert decision.single_points_required == 2940
    assert decision.prompt_dialogue is None


def test_cc_tier_3_mpqc_psi4_prompt_and_options() -> None:
    """Tier 3: MPQC/Psi4 detected -> raises Tier3PromptRequired without option, routes upon option."""
    # 1. Unselected -> raises Tier3PromptRequired with exact dialogue
    with pytest.raises(Tier3PromptRequired) as exc_info:
        route_cc_analytical_hessian(engine="mpqc", system_n_atoms=10)
    assert "176,000" in str(exc_info.value)
    assert "Substituted Hybrid Force Field" in str(exc_info.value)

    # 2. Select Option A (Numerical CCSD(T))
    dec_a = route_cc_analytical_hessian(engine="mpqc", system_n_atoms=10, user_selection="A")
    assert dec_a.tier == CCTier.TIER_3_MPQC_PSI4
    assert dec_a.selected_option == Tier3Option.OPTION_A_NUMERICAL_CCSD_T
    assert dec_a.single_points_required == 176400

    # 3. Select Option B (Substituted Hybrid Force Field)
    dec_b = route_cc_analytical_hessian(engine="psi4", system_n_atoms=10, user_selection="B")
    assert dec_b.tier == CCTier.TIER_3_MPQC_PSI4
    assert dec_b.selected_option == Tier3Option.OPTION_B_SUBSTITUTED_HYBRID
    assert dec_b.single_points_required == 49


# =====================================================================
# 11. Method Matrix v4 §8.5 Authoritative route() Execution Tests
# =====================================================================

def test_route_setup_1_orca_eula_rejection() -> None:
    """Setup 1 (GitHub): Asserts ORCA is strictly rejected due to EULA restrictions."""
    with pytest.raises(PermissionError, match="EULA VIOLATION: ORCA is strictly forbidden"):
        route(
            observable="dft_energy",
            method="B3LYP",
            setup="Setup1_github",
            has_gpu=False,
        )


def test_route_setup_2_heterogeneous_coscheduling() -> None:
    """Setup 2 (Workstation): Heterogeneous companion reserves 1 P-core, sets 7 ranks @ 3400 maxcore with 1.20x slowdown."""
    dec = route(
        observable="opt",
        method="wB97M-V",
        basis="def2-TZVP",
        setup="Setup2_workstation",
        has_gpu=False,
        has_gpu_companion=True,
    )
    assert dec.n_ranks == 7
    assert dec.maxcore_mb == 3400
    assert dec.slowdown_factor == 1.20
    assert dec.heterogeneous_companion is not None
    assert dec.heterogeneous_companion["authority"] == "advisory_only"


def test_route_conformal_windows_product_a_vs_b() -> None:
    """Verifies conformal search windows for Product A (de novo) vs Product B (measured parent)."""
    # Product A
    dec_a = route(
        observable="opt",
        product_class="A",
        has_measured_parent_or_analogue=False,
    )
    assert dec_a.product_class == ProductClass.PRODUCT_A
    assert dec_a.conformal_half_width_mhz == 48.0  # 0.40% of 12 GHz = 48 MHz

    # Product B
    dec_b = route(
        observable="opt",
        product_class="A",
        has_measured_parent_or_analogue=True,
    )
    assert dec_b.product_class == ProductClass.PRODUCT_B
    assert dec_b.conformal_half_width_mhz == 6.0  # 0.05% of 12 GHz = 6 MHz


# =====================================================================
# 12. Integrity Guards G1–G7 & Audit Trail Tests (§8A.5)
# =====================================================================

def test_guard_g1_scout_advisory_enforcement() -> None:
    """Guard G1: Asserts advisory scout output cannot supply reported answers."""
    validate_guard_g1_scout_advisory(stage_name="mlff_preopt", is_reported_value=False, authority=AuthorityLevel.ADVISORY_ONLY)
    with pytest.raises(ValueError, match="GUARD G1 VIOLATION"):
        validate_guard_g1_scout_advisory(stage_name="mlff_preopt", is_reported_value=True, authority=AuthorityLevel.ADVISORY_ONLY)


def test_guard_g2_high_level_hessian() -> None:
    """Guard G2: Checks imaginary frequencies and softest force constant."""
    assert validate_guard_g2_high_level_hessian(imaginary_freq_count=0, softest_force_constant=0.005) is True
    assert validate_guard_g2_high_level_hessian(imaginary_freq_count=1, softest_force_constant=0.005) is False
    assert validate_guard_g2_high_level_hessian(imaginary_freq_count=0, softest_force_constant=-0.001) is False


def test_guard_g3_basin_identity_check() -> None:
    """Guard G3: Identifies basin changes when RMSD > 0.25 Å or ΔR > 0.20 Å."""
    c1 = np.zeros((6, 3))
    c2_close = c1 + 0.05
    c2_far = c1 + 0.50

    ok_close, rmsd_c, dr_c = check_guard_g3_basin_identity(c1, c2_close)
    assert ok_close is True
    assert rmsd_c < 0.25

    ok_far, rmsd_f, dr_f = check_guard_g3_basin_identity(c1, c2_far)
    assert ok_far is False
    assert rmsd_f > 0.25


def test_guard_g4_rank_inversion_audit() -> None:
    """Guard G4: Evaluates Spearman rank correlation on cheap vs expensive energies."""
    cheap_good = [1.0, 2.0, 3.0, 4.0, 5.0]
    exp_good = [1.1, 2.1, 3.2, 3.9, 5.2]
    passes_good, rho_good = evaluate_guard_g4_rank_inversion(cheap_good, exp_good, min_spearman_rho=0.90)
    assert passes_good is True
    assert rho_good >= 0.90

    cheap_bad = [1.0, 2.0, 3.0, 4.0, 5.0]
    exp_bad = [5.0, 4.0, 1.0, 2.0, 3.0]
    passes_bad, rho_bad = evaluate_guard_g4_rank_inversion(cheap_bad, exp_bad, min_spearman_rho=0.90)
    assert passes_bad is False


def test_guard_g5_g6_g7() -> None:
    """Tests committee uncertainty gate G5, abort guide G6, and determinism G7."""
    assert check_guard_g5_uncertainty(committee_sigma=2.0, training_q3=1.0, training_iqr=1.0) is True
    assert check_guard_g5_uncertainty(committee_sigma=5.0, training_q3=1.0, training_iqr=1.0) is False

    assert evaluate_guard_g6_abort_guide(failure_count=3, threshold=5) is False
    assert evaluate_guard_g6_abort_guide(failure_count=5, threshold=5) is True

    key = record_guard_g7_determinism(model_key="aimnet2", checkpoint_bytes=b"sample_checkpoint")
    assert "aimnet2-wb97m-d3_0" in key


def test_audit_trail_logger_provenance() -> None:
    """Tests JSONL structured event recording with AuditTrailLogger."""
    with tempfile.TemporaryDirectory() as temp_dir:
        log_file = Path(temp_dir) / "provenance.jsonl"
        trail = AuditTrailLogger(log_file)

        event = ProvenanceEvent(
            event_id="evt_01",
            timestamp="2026-08-29T21:00:00Z",
            stage="mlff_preopt",
            decision="seed_dft_optimisation",
            guide={"model_key": "MACE-OFF24m"},
            input_data={"seed": "s1.xyz"},
            output_data={"fmax": 0.015},
            gates={"G4_spearman": 0.95},
            consumer={"anchor_job": "s2.inp"},
            authority=AuthorityLevel.ADVISORY_ONLY,
        )
        trail.record_event(event)

        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "advisory_only" in content
        assert "evt_01" in content


# =====================================================================
# 13. Method Matrix v4 §8B.5 Dangerous Reuses Guards D1–D5 Tests
# =====================================================================

def test_guard_d1_geometry_stationarity() -> None:
    """Guard D1: Verifies geometry stationarity tolerance."""
    assert validate_guard_d1_geometry_stationarity(max_gradient=5e-6, max_g_threshold=1e-5) is True
    with pytest.raises(ValueError, match="GUARD D1 VIOLATION"):
        validate_guard_d1_geometry_stationarity(max_gradient=2e-4, max_g_threshold=1e-5, strict=True)


def test_guard_d2_hessian_stationarity() -> None:
    """Guard D2: Verifies Hessian translational/rotational zeros and low-frequency modes."""
    evs_valid = [1e-6, -1e-6, 2e-6, -2e-6, 1e-7, 0.0, 150.0, 200.0, 350.0]
    valid, zero_count, low_modes = validate_guard_d2_hessian_stationarity(evs_valid)
    assert valid is True
    assert zero_count == 6

    evs_floppy = [1e-6, -1e-6, 2e-6, -2e-6, 1e-7, 0.0, 35.0, 200.0, 350.0]
    valid_f, _, low_f = validate_guard_d2_hessian_stationarity(evs_floppy)
    assert valid_f is False
    assert len(low_f) == 1


def test_guard_d3_scf_stability() -> None:
    """Guard D3: Identifies SCF basin bifurcation between reused and fresh guess."""
    assert validate_guard_d3_scf_stability(fresh_energy=-100.50000001, reused_energy=-100.50000002) is True
    with pytest.raises(ValueError, match="GUARD D3 VIOLATION"):
        validate_guard_d3_scf_stability(fresh_energy=-100.50, reused_energy=-100.48)


def test_guard_d4_d5() -> None:
    """Guard D4 (Counterpoise) & Guard D5 (Unique %base)."""
    with pytest.raises(ValueError, match="GUARD D4 VIOLATION"):
        validate_guard_d4_counterpoise_integrity(is_dimer_guess_used_for_monomer=True)

    validate_guard_d5_unique_base_name(["s1", "s2", "s3", "s4"])
    with pytest.raises(ValueError, match="GUARD D5 VIOLATION"):
        validate_guard_d5_unique_base_name(["s1", "s2", "s2", "s3"])
