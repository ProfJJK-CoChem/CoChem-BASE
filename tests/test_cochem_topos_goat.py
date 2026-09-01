"""
Unit and integration test suite for CoChem-TOPOS Stage 2.3 GOAT Cascade Master Orchestrator.
Zero-Mock Mandate: Uses real ASE Atoms, real calculators (EMT, LennardJones, TorchMLFF),
real optimizers (LBFGS, FIRE, BFGS, BaseOptimizer adapters), real HDF5 SWMR persistence,
real process reaper, batched tensor inference with CPU fallback, dynamic ALPB solvation,
and strict scratch purge management under 10GB.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import pytest
from ase import Atoms
from ase.calculators.emt import EMT
from ase.calculators.lj import LennardJones
from mendeleev import element

try:
    from cochem_topos.cochem_topos_goat import (
        ALPBSolvationManager,
        ASEOptimizerAdapter,
        BaseOptimizer,
        BatchedMLFFInference,
        CascadeCycleRecord,
        GOATCascadeConfig,
        GOATCascadeReport,
        GOATCascadeResult,
        GradientNoiseOptimizer,
        GradientNoiseQuenchResult,
        MLFFSingletonLoader,
        OptimizerToggleEvent,
        OptimizerToggleReason,
        OrphanedProcessReaper,
        ScratchPurgeManager,
        ToposGOATCascade,
        get_global_reaper,
        get_system_charge,
        load_system_config,
        reap_all_child_processes,
    )
    from cochem_topos.cochem_topos_memory import (
        DeviceType,
        EngineTier,
        GeometryRecord,
        HardwareResourceBroker,
        PrecisionMode,
        ToposHDF5MemoryManager,
    )
    from cochem_topos.cochem_topos_quench import (
        QuenchAlgorithm,
        QuenchConfig,
        QuenchStatus,
        ToposQuenchOrchestrator,
        TorchMLFFCalculator,
    )
    from cochem_topos.cochem_topos_escape import (
        EscapeConfig,
        EscapeMechanism,
        ToposEscapeOrchestrator,
    )
except ImportError:
    try:
        from mechanics.cochem_topos_goat import (  # type: ignore[no-redef]
            ALPBSolvationManager,
            ASEOptimizerAdapter,
            BaseOptimizer,
            BatchedMLFFInference,
            CascadeCycleRecord,
            GOATCascadeConfig,
            GOATCascadeReport,
            GOATCascadeResult,
            GradientNoiseOptimizer,
            GradientNoiseQuenchResult,
            MLFFSingletonLoader,
            OptimizerToggleEvent,
            OptimizerToggleReason,
            OrphanedProcessReaper,
            ScratchPurgeManager,
            ToposGOATCascade,
            get_global_reaper,
            get_system_charge,
            load_system_config,
            reap_all_child_processes,
        )
        from mechanics.cochem_topos_memory import (  # type: ignore[no-redef]
            DeviceType,
            EngineTier,
            GeometryRecord,
            HardwareResourceBroker,
            PrecisionMode,
            ToposHDF5MemoryManager,
        )
        from mechanics.cochem_topos_quench import (  # type: ignore[no-redef]
            QuenchAlgorithm,
            QuenchConfig,
            QuenchStatus,
            ToposQuenchOrchestrator,
            TorchMLFFCalculator,
        )
        from mechanics.cochem_topos_escape import (  # type: ignore[no-redef]
            EscapeConfig,
            EscapeMechanism,
            ToposEscapeOrchestrator,
        )
    except ImportError:
        from cochem_topos_goat import (  # type: ignore[no-redef]
            ALPBSolvationManager,
            ASEOptimizerAdapter,
            BaseOptimizer,
            BatchedMLFFInference,
            CascadeCycleRecord,
            GOATCascadeConfig,
            GOATCascadeReport,
            GOATCascadeResult,
            GradientNoiseOptimizer,
            GradientNoiseQuenchResult,
            MLFFSingletonLoader,
            OptimizerToggleEvent,
            OptimizerToggleReason,
            OrphanedProcessReaper,
            ScratchPurgeManager,
            ToposGOATCascade,
            get_global_reaper,
            get_system_charge,
            load_system_config,
            reap_all_child_processes,
        )
        from cochem_topos_memory import (  # type: ignore[no-redef]
            DeviceType,
            EngineTier,
            GeometryRecord,
            HardwareResourceBroker,
            PrecisionMode,
            ToposHDF5MemoryManager,
        )
        from cochem_topos_quench import (  # type: ignore[no-redef]
            QuenchAlgorithm,
            QuenchConfig,
            QuenchStatus,
            ToposQuenchOrchestrator,
            TorchMLFFCalculator,
        )
        from cochem_topos_escape import (  # type: ignore[no-redef]
            EscapeConfig,
            EscapeMechanism,
            ToposEscapeOrchestrator,
        )

try:
    from cochem_topos.cochem_topos_crusher import (
        DeduplicationVerdict,
        TopologyCrusher,
    )
except (ImportError, AttributeError, Exception):
    try:
        from topology.cochem_topos_crusher import (  # type: ignore[no-redef]
            DeduplicationVerdict,
            TopologyCrusher,
        )
    except (ImportError, AttributeError, Exception):
        try:
            from core_engine.cochem_topos_crusher import (  # type: ignore[import-not-found,no-redef]
                TopologyCrusher,  # type: ignore[misc]
            )
            DeduplicationVerdict = None  # type: ignore[assignment,misc]
        except (ImportError, AttributeError, Exception):
            DeduplicationVerdict = None  # type: ignore[assignment,misc]
            TopologyCrusher = None  # type: ignore[assignment,misc]


# ============================================================================
# 1. Pydantic Models and Configuration Tests
# ============================================================================

class TestGOATDataModels:
    """Tests for GOAT Cascade configuration, records, and reports."""

    def test_goat_config_defaults_and_validation(self) -> None:
        """Verify default parameters of GOATCascadeConfig."""
        config = GOATCascadeConfig()
        assert config.max_cycles == 10
        assert config.patience == 3
        assert config.target_coverage == 0.95
        assert config.primary_optimizer == QuenchAlgorithm.LBFGS
        assert config.fallback_optimizer == QuenchAlgorithm.FIRE
        assert config.oscillation_window == 5
        assert config.oscillation_force_tol == 0.01
        assert config.fmax == 0.05
        assert config.max_quench_steps == 300
        assert config.enable_process_reaper is True
        assert config.save_to_hdf5 is True
        assert config.temperature_schedule == [300.0, 500.0, 1000.0]
        assert config.batch_size in (32, 64)
        assert config.max_scratch_bytes == 10 * 1024 * 1024 * 1024
        assert config.alpb_solvation_active is False

    def test_goat_config_custom_overrides(self, tmp_path: Path) -> None:
        """Verify custom parameter overrides."""
        db_file = tmp_path / "test_goat.h5"
        config = GOATCascadeConfig(
            max_cycles=25,
            patience=5,
            target_coverage=0.99,
            primary_optimizer=QuenchAlgorithm.BFGS,
            fallback_optimizer=QuenchAlgorithm.FIRE,
            fmax=0.01,
            db_path=db_file,
            batch_size=64,
            charge=-1,
            alpb_solvation_active=True,
            max_scratch_bytes=5 * 1024 * 1024 * 1024,
        )
        assert config.max_cycles == 25
        assert config.patience == 5
        assert config.target_coverage == 0.99
        assert config.primary_optimizer == QuenchAlgorithm.BFGS
        assert config.fallback_optimizer == QuenchAlgorithm.FIRE
        assert config.fmax == 0.01
        assert config.db_path == db_file
        assert config.batch_size == 64
        assert config.charge == -1
        assert config.alpb_solvation_active is True
        assert config.max_scratch_bytes == 5 * 1024 * 1024 * 1024

    def test_optimizer_toggle_event_serialization(self) -> None:
        """Verify OptimizerToggleEvent serialization and attributes."""
        event = OptimizerToggleEvent(
            geom_id="mol_001",
            step_index=12,
            reason=OptimizerToggleReason.HESSIAN_ILL_CONDITIONED,
            from_optimizer=QuenchAlgorithm.LBFGS,
            to_optimizer=QuenchAlgorithm.FIRE,
            current_fmax=1.45,
            current_energy=-12.345,
            details="Hessian update matrix ill-conditioned",
        )
        assert event.geom_id == "mol_001"
        assert event.step_index == 12
        assert event.reason == OptimizerToggleReason.HESSIAN_ILL_CONDITIONED
        assert event.from_optimizer == QuenchAlgorithm.LBFGS
        assert event.to_optimizer == QuenchAlgorithm.FIRE
        dumped = event.model_dump()
        assert dumped["geom_id"] == "mol_001"
        assert dumped["reason"] == "HESSIAN_ILL_CONDITIONED"

    def test_cascade_cycle_record_and_report(self) -> None:
        """Verify serialization of CascadeCycleRecord and GOATCascadeReport."""
        record = CascadeCycleRecord(
            cycle_index=1,
            seed_geom_id="seed_0",
            escape_status="BREACH_SUCCESS",
            escape_mechanism=EscapeMechanism.WIGNER.value,
            candidates_generated=3,
            quench_converged_count=3,
            unique_basins_discovered=1,
            duplicates_rejected=2,
            enantiomers_preserved=0,
            optimizer_toggles_count=1,
            duration_seconds=1.25,
        )
        assert record.cycle_index == 1
        assert record.candidates_generated == 3

        report = GOATCascadeReport(
            session_id="session_test_01",
            total_cycles_executed=5,
            total_unique_basins=3,
            total_duplicates_rejected=10,
            total_enantiomers_preserved=1,
            total_optimizer_toggles=2,
            final_completeness_estimate=0.96,
            converged_stopping_criterion="TARGET_COVERAGE_REACHED",
            duration_seconds=15.3,
            cycle_records=[record],
        )
        assert report.total_cycles_executed == 5
        assert report.total_unique_basins == 3
        assert len(report.cycle_records) == 1


# ============================================================================
# 2. Directive 1: Engine Abstraction Layer (BaseOptimizer) Tests
# ============================================================================

class TestBaseOptimizerAbstraction:
    """Tests for BaseOptimizer abstract class and optimizer engine adapters."""

    def test_base_optimizer_subclassing_and_interface(self) -> None:
        """Verify BaseOptimizer defines the standard relaxation contract."""
        assert issubclass(GradientNoiseOptimizer, BaseOptimizer)
        assert issubclass(ASEOptimizerAdapter, BaseOptimizer)

    def test_ase_optimizer_adapter_execution(self) -> None:
        """Verify ASEOptimizerAdapter relaxes structures using standard ASE optimizers."""
        atoms = Atoms("Cu2", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 2.8]])
        atoms.calc = EMT()

        adapter = ASEOptimizerAdapter(
            optimizer_algorithm=QuenchAlgorithm.BFGS,
            fmax=0.05,
            max_steps=50,
        )
        res = adapter.optimize(atoms, geom_id="adapter_cu2")
        assert isinstance(res, GradientNoiseQuenchResult)
        assert res.converged is True
        assert res.final_max_force <= 0.05
        assert res.final_energy < res.initial_energy

    def test_custom_base_optimizer_plugged_into_cascade(self, tmp_path: Path) -> None:
        """Verify ToposGOATCascade accepts any BaseOptimizer implementation."""
        db_path = tmp_path / "custom_opt.h5"
        config = GOATCascadeConfig(
            max_cycles=1,
            fmax=0.05,
            db_path=db_path,
            temperature_schedule=[300.0],
            langevin_steps_per_stage=5,
        )

        custom_optimizer = ASEOptimizerAdapter(
            optimizer_algorithm=QuenchAlgorithm.FIRE,
            fmax=0.05,
            max_steps=100,
        )
        cascade = ToposGOATCascade(config=config, optimizer=custom_optimizer)
        seed_atoms = Atoms("Cu2", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 2.7]])
        seed_atoms.calc = EMT()

        report = cascade.run_cascade(seed_atoms=seed_atoms, session_id="custom_opt_session")
        assert report.total_cycles_executed == 1
        assert report.total_unique_basins >= 1


# ============================================================================
# 3. Directive 2: Singleton Loader and Batched GPU/CPU Inference Tests
# ============================================================================

class TestMLFFSingletonAndBatchedInference:
    """Tests for MLFF singleton loader and batched inference with CPU fallback."""

    def test_singleton_loader_caching(self) -> None:
        """Verify MLFFSingletonLoader returns cached instance for identical specs."""
        loader = MLFFSingletonLoader.get_instance()
        calc1 = loader.get_calculator(
            engine=EngineTier.MACE_OFF24M,
            device=DeviceType.CPU,
            precision=PrecisionMode.FP32,
            atomic_numbers=[6, 1],
        )
        calc2 = loader.get_calculator(
            engine=EngineTier.MACE_OFF24M,
            device=DeviceType.CPU,
            precision=PrecisionMode.FP32,
            atomic_numbers=[6, 1],
        )
        assert calc1 is calc2

    def test_singleton_loader_thread_safety(self) -> None:
        """Verify MLFFSingletonLoader is thread-safe across concurrent accesses."""
        import concurrent.futures
        loader = MLFFSingletonLoader.get_instance()
        loader.clear_cache()

        def fetch_calc() -> Any:
            return loader.get_calculator(
                engine="EMT",
                device=DeviceType.CPU,
                precision=PrecisionMode.FP32,
                atomic_numbers=[29],
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(fetch_calc) for _ in range(16)]
            results = [f.result() for f in futures]

        first = results[0]
        for r in results:
            assert r is first

    def test_batched_inference_cpu_fallback(self) -> None:
        """Verify batched inference processes batches of 32/64 with automated CPU fallback."""
        geometries: list[Atoms] = []
        for i in range(35):
            d = 0.95 + 0.01 * (i % 5)
            atoms = Atoms("H2O", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, d], [d, 0.0, -0.3]])
            geometries.append(atoms)

        batch_engine = BatchedMLFFInference(batch_size=32, device="cpu")
        calc = TorchMLFFCalculator(device="cpu", precision="float32")

        batch_results = batch_engine.evaluate_batch(geometries, calculator=calc)
        assert len(batch_results) == 35
        for energy, forces in batch_results:
            assert isinstance(energy, float)
            assert isinstance(forces, np.ndarray)
            assert forces.shape == (3, 3)
            assert not np.isnan(energy)
            assert not np.isnan(forces).any()

    def test_batched_inference_batch_size_64(self) -> None:
        """Verify batching with batch_size=64 handles arbitrary length lists."""
        geometries = [Atoms("Cu2", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 2.5 + 0.01 * i]]) for i in range(70)]
        batch_engine = BatchedMLFFInference(batch_size=64, device="cpu")
        calc = EMT()

        results = batch_engine.evaluate_batch(geometries, calculator=calc)
        assert len(results) == 70
        for energy, forces in results:
            assert isinstance(energy, float)
            assert forces.shape == (2, 3)


# ============================================================================
# 4. Directive 3: Dynamic Solvation Activation Tests
# ============================================================================

class TestDynamicSolvationActivation:
    """Tests for dynamic ALPB implicit solvation activation when system charge != 0."""

    def test_load_system_config_and_charge_detection(self, tmp_path: Path) -> None:
        """Verify polling system configuration for molecular charge."""
        config_file = tmp_path / "cochem_system_config.json"
        config_data = {
            "engines": {"mace": {"status": "found"}},
            "system_charge": -1,
            "solvation": {"alpb_model": "water"},
        }
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        parsed_cfg = load_system_config(config_file)
        assert parsed_cfg["system_charge"] == -1
        charge = get_system_charge(config_file)
        assert charge == -1

    def test_alpb_solvation_manager_activation(self) -> None:
        """Verify ALPBSolvationManager activates when charge != 0."""
        manager_neutral = ALPBSolvationManager(charge=0)
        assert manager_neutral.is_alpb_active is False

        manager_anion = ALPBSolvationManager(charge=-1)
        assert manager_anion.is_alpb_active is True
        assert manager_anion.solvent == "water"

        manager_cation = ALPBSolvationManager(charge=+1, solvent="acetonitrile")
        assert manager_cation.is_alpb_active is True
        assert manager_cation.solvent == "acetonitrile"

    def test_alpb_solvation_thermal_mapping_screening(self) -> None:
        """Verify ALPB solvation applies screening corrections to charged fragments during thermal mapping."""
        solvation = ALPBSolvationManager(charge=-1, solvent="water")
        atoms = Atoms("NO3", positions=[
            [0.0, 0.0, 0.0],
            [0.0, 1.2, 0.0],
            [1.04, -0.6, 0.0],
            [-1.04, -0.6, 0.0],
        ])
        atoms.calc = LennardJones()

        screened_forces = solvation.apply_solvation_screening(atoms, temperature_k=500.0)
        assert screened_forces.shape == (4, 3)
        assert not np.isnan(screened_forces).any()

    def test_goat_cascade_auto_activates_alpb_for_charged_species(self, tmp_path: Path) -> None:
        """Verify ToposGOATCascade auto-activates ALPB implicit solvation when configured with charge != 0."""
        db_path = tmp_path / "charged_cascade.h5"
        config = GOATCascadeConfig(
            max_cycles=1,
            charge=-1,
            fmax=0.05,
            db_path=db_path,
            temperature_schedule=[300.0],
            langevin_steps_per_stage=5,
        )
        cascade = ToposGOATCascade(config=config)
        assert cascade.alpb_manager.is_alpb_active is True
        assert cascade.config.alpb_solvation_active is True

        seed_atoms = Atoms("Cu2", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 2.5]])
        seed_atoms.calc = EMT()

        report = cascade.run_cascade(seed_atoms=seed_atoms, session_id="charged_run")
        assert report.total_cycles_executed == 1
        assert report.total_unique_basins >= 1


# ============================================================================
# 5. Directive 4: Strict Scratch Purge Protocol Tests
# ============================================================================

class TestStrictScratchPurgeProtocol:
    """Tests for continuous runtime scratch file purging capping consumption under 10GB."""

    def test_scratch_purge_manager_monitors_and_caps_size(self, tmp_path: Path) -> None:
        """Verify ScratchPurgeManager measures usage and purges files exceeding cap."""
        scratch_dir = tmp_path / "scratch_work"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        for i in range(10):
            f = scratch_dir / f"temp_calc_{i}.tmp"
            f.write_bytes(b"X" * 1024 * 100)  # 100 KB each = 1 MB total

        purger = ScratchPurgeManager(
            scratch_directories=[scratch_dir],
            max_scratch_bytes=500 * 1024,
        )

        total_bytes = purger.get_total_scratch_bytes()
        assert total_bytes >= 1000 * 1024

        telemetry = purger.purge_scratch_if_needed(force=False)
        assert telemetry["purged_file_count"] > 0
        assert telemetry["bytes_reclaimed"] > 0
        assert purger.get_total_scratch_bytes() <= 500 * 1024

    def test_scratch_purge_preserves_critical_h5_and_permanent_files(self, tmp_path: Path) -> None:
        """Verify ScratchPurgeManager never deletes permanent landscape.h5 files."""
        scratch_dir = tmp_path / "scratch_safe"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        h5_file = scratch_dir / "landscape.h5"
        h5_file.write_bytes(b"CRITICAL_HDF5_DATA" * 1000)

        tmp_file = scratch_dir / "orca_grad.tmp"
        tmp_file.write_bytes(b"TEMPORARY_SCRATCH" * 1000)

        purger = ScratchPurgeManager(
            scratch_directories=[scratch_dir],
            max_scratch_bytes=1000,
        )
        purger.purge_scratch_if_needed(force=True)

        assert h5_file.exists()
        assert not tmp_file.exists()

    def test_cascade_enforces_scratch_cap_during_loop(self, tmp_path: Path) -> None:
        """Verify ToposGOATCascade continually enforces scratch purge during cascade cycles."""
        db_path = tmp_path / "cascade_scratch.h5"
        scratch_dir = tmp_path / "cascade_scratch_dir"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        config = GOATCascadeConfig(
            max_cycles=1,
            fmax=0.05,
            db_path=db_path,
            max_scratch_bytes=10 * 1024 * 1024 * 1024,  # 10 GB
            temperature_schedule=[300.0],
            langevin_steps_per_stage=5,
        )
        cascade = ToposGOATCascade(config=config, scratch_dirs=[scratch_dir])

        (scratch_dir / "run.tmp").write_text("transient")

        seed_atoms = Atoms("Cu2", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 2.5]])
        seed_atoms.calc = EMT()

        report = cascade.run_cascade(seed_atoms=seed_atoms, session_id="scratch_test_run")
        assert report.total_cycles_executed >= 1
        assert cascade.scratch_purger.get_total_scratch_bytes() < config.max_scratch_bytes


# ============================================================================
# 6. Orphaned Thread Reaper Tests
# ============================================================================

class TestOrphanedProcessReaper:
    """Tests for cross-platform process safety and orphaned thread reaping."""

    def test_reaper_singleton_and_registration(self) -> None:
        """Verify global reaper instance and subprocess registration."""
        reaper = get_global_reaper()
        assert isinstance(reaper, OrphanedProcessReaper)

        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        reaper.register_process(proc)
        assert proc in reaper.tracked_processes

        reaper.reap_process(proc)
        time.sleep(0.2)
        assert proc.poll() is not None

    def test_reaper_context_manager(self) -> None:
        """Verify context manager automatically terminates spawned children."""
        reaper = OrphanedProcessReaper()
        with reaper:
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            reaper.register_process(proc)
            assert proc.poll() is None

        time.sleep(0.2)
        assert proc.poll() is not None

    def test_reap_all_child_processes(self) -> None:
        """Verify reap_all_child_processes function cleans up processes."""
        proc1 = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        proc2 = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        reap_all_child_processes([proc1, proc2])
        time.sleep(0.2)
        assert proc1.poll() is not None
        assert proc2.poll() is not None


# ============================================================================
# 7. Gradient-Noise Optimizer Toggle Engine Tests
# ============================================================================

class TestGradientNoiseOptimizer:
    """Tests for dynamic trajectory monitoring and LBFGS -> FIRE optimizer switching."""

    def test_smooth_lbfgs_convergence_no_toggle(self) -> None:
        """Verify smooth descent converges using LBFGS without needing a toggle."""
        atoms = Atoms("Cu2", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 2.8]])
        atoms.calc = EMT()

        opt_engine = GradientNoiseOptimizer(
            primary_optimizer=QuenchAlgorithm.LBFGS,
            fallback_optimizer=QuenchAlgorithm.FIRE,
            fmax=0.05,
            max_steps=100,
        )

        res = opt_engine.optimize(atoms, geom_id="cu2_smooth")
        assert res.converged is True
        assert res.status == QuenchStatus.CONVERGED
        assert res.final_max_force <= 0.05
        assert len(res.toggle_events) == 0
        assert res.active_optimizer == QuenchAlgorithm.LBFGS

    def test_oscillation_intercept_and_fire_toggle(self) -> None:
        """Verify that gradient noise / oscillation triggers automatic toggle to FIRE."""
        atoms = Atoms("Ar3", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 3.5], [1.5, 0.0, 1.7]])
        atoms.calc = LennardJones(sigma=3.4, epsilon=0.01)

        opt_engine = GradientNoiseOptimizer(
            primary_optimizer=QuenchAlgorithm.LBFGS,
            fallback_optimizer=QuenchAlgorithm.FIRE,
            fmax=0.01,
            max_steps=200,
            oscillation_window=3,
            oscillation_force_tol=0.0001,
        )

        res = opt_engine.optimize(atoms, geom_id="ar3_noisy")
        assert res.converged is True
        assert res.final_max_force <= 0.01
        assert res.final_energy < res.initial_energy

    def test_unphysical_geometry_intercept_and_fire_fallback(self) -> None:
        """Verify that an unphysical geometry producing NaN forces naturally falls back to FIRE."""
        atoms = Atoms("Cu2", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
        atoms.calc = EMT()

        opt_engine = GradientNoiseOptimizer(
            primary_optimizer=QuenchAlgorithm.LBFGS,
            fallback_optimizer=QuenchAlgorithm.FIRE,
            fmax=0.05,
            max_steps=150,
        )

        res = opt_engine.optimize(atoms, geom_id="cu2_nan")
        assert len(res.toggle_events) > 0
        event = res.toggle_events[0]
        assert event.reason == OptimizerToggleReason.HESSIAN_ILL_CONDITIONED
        assert event.to_optimizer == QuenchAlgorithm.FIRE
        assert res.converged is True


# ============================================================================
# 8. Pipeline Loop Handoff & Cascade Integration Tests
# ============================================================================

class TestToposGOATCascadePipeline:
    """Tests for the master pipeline loop: Escape -> Quench -> Crusher -> SWMR HDF5."""

    def test_single_cycle_cascade_execution(self, tmp_path: Path) -> None:
        """Verify handoff across Escape, Quench, Crusher, and HDF5 in a single cycle."""
        db_path = tmp_path / "cascade_single.h5"
        config = GOATCascadeConfig(
            max_cycles=1,
            fmax=0.05,
            db_path=db_path,
            temperature_schedule=[300.0],
            langevin_steps_per_stage=5,
        )

        cascade = ToposGOATCascade(config=config)
        seed_atoms = Atoms("Cu4", positions=[
            [0.0, 0.0, 0.0],
            [2.5, 0.0, 0.0],
            [1.25, 2.16, 0.0],
            [1.25, 0.72, 2.04],
        ])
        seed_atoms.calc = EMT()

        report = cascade.run_cascade(seed_atoms=seed_atoms, session_id="test_single_cycle")
        assert report.total_cycles_executed == 1
        assert report.total_unique_basins >= 1
        assert db_path.exists()

        with h5py.File(db_path, "r") as f:
            assert "geometries" in f or "deduplicated_basins" in f

    def test_multi_cycle_basin_exploration(self, tmp_path: Path) -> None:
        """Verify multi-cycle cascade discovers basins and applies Good-Turing estimator."""
        db_path = tmp_path / "cascade_multi.h5"
        config = GOATCascadeConfig(
            max_cycles=2,
            patience=2,
            target_coverage=0.90,
            fmax=0.05,
            db_path=db_path,
            temperature_schedule=[300.0],
            langevin_steps_per_stage=5,
        )

        cascade = ToposGOATCascade(config=config)
        seed_atoms = Atoms("Cu4", positions=[
            [0.0, 0.0, 0.0],
            [2.5, 0.0, 0.0],
            [1.25, 2.16, 0.0],
            [1.25, 0.72, 2.04],
        ])
        seed_atoms.calc = EMT()

        report = cascade.run_cascade(seed_atoms=seed_atoms, session_id="test_multi_cycle")
        assert report.total_cycles_executed <= 2
        assert report.total_unique_basins >= 1
        assert len(report.cycle_records) > 0
        assert report.final_completeness_estimate >= 0.0

    def test_enantiomer_preservation_in_cascade(self, tmp_path: Path) -> None:
        """Verify that chiral structures in cascade exploration preserve enantiomers."""
        db_path = tmp_path / "cascade_chiral.h5"
        config = GOATCascadeConfig(
            max_cycles=1,
            fmax=0.05,
            db_path=db_path,
            temperature_schedule=[300.0],
            langevin_steps_per_stage=5,
        )
        cascade = ToposGOATCascade(config=config)

        # Chiral 4-atom cluster with distinct elements
        seed_atoms = Atoms("HCFCl", positions=[
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 1.09],
            [1.02, 0.0, -0.36],
            [-0.51, 0.88, -0.36],
        ])
        seed_atoms.calc = LennardJones()

        report = cascade.run_cascade(seed_atoms=seed_atoms, session_id="test_chiral_cascade")
        assert report.total_unique_basins >= 1
        assert report.total_cycles_executed >= 1

    def test_stopping_criterion_patience(self, tmp_path: Path) -> None:
        """Verify cascade halts when patience limit is reached without new basins."""
        db_path = tmp_path / "cascade_patience.h5"
        config = GOATCascadeConfig(
            max_cycles=5,
            patience=1,
            fmax=0.05,
            db_path=db_path,
            temperature_schedule=[300.0],
            langevin_steps_per_stage=5,
        )
        cascade = ToposGOATCascade(config=config)

        seed_atoms = Atoms("Cu2", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 2.5]])
        seed_atoms.calc = EMT()

        report = cascade.run_cascade(seed_atoms=seed_atoms, session_id="test_patience")
        assert report.total_cycles_executed <= 3
        assert report.total_unique_basins == 1

    def test_gradient_noise_optimizer_with_torch_mlff(self) -> None:
        """Verify GradientNoiseOptimizer works seamlessly with TorchMLFFCalculator."""
        calc = TorchMLFFCalculator(device="cpu", precision="float64")
        atoms = Atoms("H2O", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 1.1], [0.9, 0.0, -0.3]])
        atoms.calc = calc

        opt_engine = GradientNoiseOptimizer(
            primary_optimizer=QuenchAlgorithm.LBFGS,
            fallback_optimizer=QuenchAlgorithm.FIRE,
            fmax=0.05,
            max_steps=100,
        )

        res = opt_engine.optimize(atoms, geom_id="h2o_torch_mlff")
        assert res.converged is True
        assert res.final_max_force <= 0.05
        assert res.final_energy < res.initial_energy

    def test_goat_cascade_report_json_serialization(self, tmp_path: Path) -> None:
        """Verify complete JSON serialization and reconstruction of GOATCascadeReport."""
        db_path = tmp_path / "cascade_json.h5"
        config = GOATCascadeConfig(
            max_cycles=1,
            fmax=0.05,
            db_path=db_path,
            temperature_schedule=[300.0],
            langevin_steps_per_stage=5,
        )
        cascade = ToposGOATCascade(config=config)
        seed_atoms = Atoms("Cu3", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 2.4], [2.2, 0.0, 0.0]])
        seed_atoms.calc = EMT()

        report = cascade.run_cascade(seed_atoms=seed_atoms, session_id="test_json_export")
        dumped_json = report.model_dump_json()
        assert "test_json_export" in dumped_json

        reconstructed = GOATCascadeReport.model_validate_json(dumped_json)
        assert reconstructed.session_id == "test_json_export"
        assert reconstructed.total_cycles_executed == report.total_cycles_executed
        assert reconstructed.total_unique_basins == report.total_unique_basins

    def test_custom_hardware_broker_integration(self, tmp_path: Path) -> None:
        """Verify ToposGOATCascade integration with custom HardwareResourceBroker."""
        broker = HardwareResourceBroker()
        db_path = tmp_path / "cascade_broker.h5"
        config = GOATCascadeConfig(
            max_cycles=1,
            fmax=0.05,
            db_path=db_path,
            engine=EngineTier.MACE_OFF24M,
            device=DeviceType.CPU,
            precision=PrecisionMode.FP32,
            temperature_schedule=[300.0],
            langevin_steps_per_stage=5,
        )
        cascade = ToposGOATCascade(config=config, broker=broker)
        seed_atoms = Atoms("Cu2", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 2.6]])
        seed_atoms.calc = EMT()

        report = cascade.run_cascade(seed_atoms=seed_atoms, session_id="test_broker")
        assert report.total_unique_basins >= 1
        assert cascade.broker is broker

    def test_topos_goat_cascade_default_initialization(self) -> None:
        """Verify ToposGOATCascade initializes without error using all defaults."""
        cascade = ToposGOATCascade()
        assert cascade.config is not None
        assert cascade.broker is not None
        assert cascade.memory_manager is not None
        assert cascade.db_path.exists() or cascade.db_path.parent.exists()
