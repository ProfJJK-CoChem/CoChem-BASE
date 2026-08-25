"""
Unit and integration tests for CoChem-TOPOS Stage 2.0 Mechanics Memory Subsystem (CoChem-BASE).
Strict Zero-Mock Mandate: Uses real HDF5 files, real psutil metrics, real torch tensors,
real numpy arrays, real elemental definitions, and real concurrent filelock access.
"""

import json
import os
import threading
import time
from pathlib import Path
import pytest
import numpy as np
import psutil
import torch

try:
    from cochem_topos.cochem_topos_memory import (
        ToposHDF5MemoryManager,
        HardwareResourceBroker,
        HardwareSnapshot,
        GPUDeviceInfo,
        UniversalFallbackCascade,
        FallbackCascadeStateMachine,
        EngineTier,
        TheoreticalTier,
        FallbackReason,
        DeviceType,
        PrecisionMode,
        CascadeState,
        PrecisionDowngradeProtocol,
        GeometryRecord,
        TrajectoryStep,
        TelemetryRecord,
        QCSchemaPoint,
        sweep_stale_locks,
        generate_oom_autopsy,
        handle_engine_exit_code,
        EngineOOMError,
        enforce_precision_tier,
        load_system_config,
        get_cochem_workspace,
        get_databases_directory,
        get_registry_directory,
        get_atomic_mass,
        get_element_symbol,
        get_molecular_mass,
        ElementalCascadeRouter,
        HDF5StateManager,
        ToposMemoryBroker,
        ToposMemoryConfig,
    )
except ImportError:
    from mechanics.cochem_topos_memory import (
        ToposHDF5MemoryManager,
        HardwareResourceBroker,
        HardwareSnapshot,
        GPUDeviceInfo,
        UniversalFallbackCascade,
        FallbackCascadeStateMachine,
        EngineTier,
        TheoreticalTier,
        FallbackReason,
        DeviceType,
        PrecisionMode,
        CascadeState,
        PrecisionDowngradeProtocol,
        GeometryRecord,
        TrajectoryStep,
        TelemetryRecord,
        QCSchemaPoint,
        sweep_stale_locks,
        generate_oom_autopsy,
        handle_engine_exit_code,
        EngineOOMError,
        enforce_precision_tier,
        load_system_config,
        get_cochem_workspace,
        get_databases_directory,
        get_registry_directory,
        get_atomic_mass,
        get_element_symbol,
        get_molecular_mass,
        ElementalCascadeRouter,
        HDF5StateManager,
        ToposMemoryBroker,
        ToposMemoryConfig,
    )


# ============================================================================
# 1. Air-Gap Protocol & System Config Tests
# ============================================================================

class TestAirGapProtocolAndConfig:
    """Tests for Air-Gap Protocol, workspace directory resolution, and config loading."""

    def test_workspace_directory_resolution(self, tmp_path: Path):
        """Test strict workspace resolution via COCHEM_WORKSPACE."""
        workspace = tmp_path / "air_gapped_ws"
        workspace.mkdir(parents=True, exist_ok=True)
        old_env = os.environ.get("COCHEM_WORKSPACE")
        try:
            os.environ["COCHEM_WORKSPACE"] = str(workspace)
            assert get_cochem_workspace() == workspace
            assert get_databases_directory() == workspace / "CoChem_Artifacts" / "Databases"
            assert get_registry_directory() == workspace / "CoChem_Artifacts" / "Registry"
            assert get_databases_directory().exists()
            assert get_registry_directory().exists()
        finally:
            if old_env is not None:
                os.environ["COCHEM_WORKSPACE"] = old_env
            else:
                os.environ.pop("COCHEM_WORKSPACE", None)

    def test_load_system_config_air_gap(self, tmp_path: Path):
        """Test reading configuration solely from Registry/cochem_system_config.json."""
        workspace = tmp_path / "custom_airgap_ws"
        reg_dir = workspace / "CoChem_Artifacts" / "Registry"
        reg_dir.mkdir(parents=True, exist_ok=True)
        old_env = os.environ.get("COCHEM_WORKSPACE")
        try:
            os.environ["COCHEM_WORKSPACE"] = str(workspace)
            config_data = {
                "workspace": str(workspace),
                "vram_governor_cap": 0.85,
                "active_thread_percentage": 85,
                "default_precision": "float64",
                "custom_tier": "T1-1min",
            }
            config_path = reg_dir / "cochem_system_config.json"
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f)

            loaded = load_system_config()
            assert loaded["vram_governor_cap"] == 0.85
            assert loaded["active_thread_percentage"] == 85
            assert loaded["default_precision"] == "float64"
            assert loaded["custom_tier"] == "T1-1min"
        finally:
            if old_env is not None:
                os.environ["COCHEM_WORKSPACE"] = old_env
            else:
                os.environ.pop("COCHEM_WORKSPACE", None)


# ============================================================================
# 2. Hardware Resource Broker & VRAM Governor Tests
# ============================================================================

class TestHardwareResourceBroker:
    """Tests for HardwareResourceBroker with real psutil and pynvml polling."""

    def test_real_psutil_hardware_snapshot(self):
        """Test real system metrics polling with psutil."""
        broker = HardwareResourceBroker()
        snapshot = broker.poll_hardware()

        assert isinstance(snapshot, HardwareSnapshot)
        assert snapshot.timestamp > 0
        assert snapshot.cpu_count_logical > 0
        assert snapshot.cpu_count_physical > 0
        assert snapshot.ram_total_bytes > 0
        assert snapshot.ram_available_bytes > 0
        assert 0.0 <= snapshot.ram_percent <= 100.0
        assert 0.0 <= snapshot.cpu_percent <= 100.0
        assert isinstance(snapshot.cuda_available, bool)
        assert isinstance(snapshot.gpu_devices, list)

    def test_pynvml_safe_handling(self):
        """Test NVML polling executes cleanly without throwing unhandled exceptions."""
        broker = HardwareResourceBroker()
        gpus = broker._poll_gpu_devices()
        assert isinstance(gpus, list)
        for gpu in gpus:
            assert isinstance(gpu, GPUDeviceInfo)
            assert gpu.total_vram_bytes >= 0
            assert gpu.free_vram_bytes >= 0
            assert gpu.used_vram_bytes >= 0

    def test_apply_vram_governor(self):
        """Test VRAM governor sets CUDA MPS memory and thread limits strictly at 85%."""
        broker = HardwareResourceBroker()
        env_updates = broker.apply_vram_governor(max_vram_fraction=0.85, active_thread_percentage=85)

        assert "CUDA_MPS_PINNED_DEVICE_MEM_LIMIT" in env_updates
        assert "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE" in env_updates
        assert env_updates["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] == "85"
        assert os.environ["COCHEM_VRAM_GOVERNOR_ACTIVE"] == "1"

        assert broker.check_vram_cap(max_vram_fraction=0.85) is True

    def test_safe_batch_size_calculation(self):
        """Test dynamic calculation of safe ASE batch size to prevent OOM."""
        broker = HardwareResourceBroker()

        small_batch_mace = broker.calculate_safe_batch_size(num_atoms=10, engine=EngineTier.MACE_OFF24M)
        large_batch_mace = broker.calculate_safe_batch_size(num_atoms=300, engine=EngineTier.MACE_OFF24M)

        assert small_batch_mace >= 1
        assert large_batch_mace >= 1
        assert small_batch_mace >= large_batch_mace

        small_batch_xtb = broker.calculate_safe_batch_size(num_atoms=10, engine=EngineTier.XTB2)
        large_batch_xtb = broker.calculate_safe_batch_size(num_atoms=500, engine=EngineTier.XTB2)
        assert small_batch_xtb >= 1
        assert large_batch_xtb >= 1
        assert small_batch_xtb >= large_batch_xtb

    def test_memory_headroom_check(self):
        """Test available memory headroom checks."""
        broker = HardwareResourceBroker()
        assert broker.check_memory_headroom(required_bytes=1024 * 1024, target_device=DeviceType.CPU) is True
        assert broker.check_memory_headroom(required_bytes=1024**5, target_device=DeviceType.CPU) is False

    def test_get_optimal_device(self):
        """Test optimal device selection based on engine and hardware."""
        broker = HardwareResourceBroker()
        device = broker.get_optimal_device(engine=EngineTier.XTB2)
        assert device == DeviceType.CPU


# ============================================================================
# 3. Universal Fallback Cascade & Precision Enforcement Tests
# ============================================================================

class TestUniversalFallbackCascade:
    """Tests for UniversalFallbackCascade and FallbackCascadeStateMachine."""

    def test_element_support_validation(self):
        """Test element compatibility checking across engine tiers."""
        cascade = UniversalFallbackCascade()

        # Water: H (1), O (8) -> supported by all
        h2o = [1, 1, 8]
        assert cascade.validate_elements(h2o, EngineTier.MACE_OFF24M)[0] is True
        assert cascade.validate_elements(h2o, EngineTier.AIMNET2)[0] is True
        assert cascade.validate_elements(h2o, EngineTier.G_XTB)[0] is True
        assert cascade.validate_elements(h2o, EngineTier.XTB2)[0] is True

        # Boron / Silicon (B=5, Si=14) -> Not in standard MACE-OFF24m, in AIMNet2
        borane = [5, 1, 1, 1]
        assert cascade.validate_elements(borane, EngineTier.MACE_OFF24M)[0] is False
        assert cascade.validate_elements(borane, EngineTier.AIMNET2)[0] is True

        # Platinum / Iron (Pt=78, Fe=26) -> in xTB
        cisplatin = [78, 17, 17, 7, 7, 1, 1, 1, 1, 1, 1]
        assert cascade.validate_elements(cisplatin, EngineTier.MACE_OFF24M)[0] is False
        assert cascade.validate_elements(cisplatin, EngineTier.AIMNET2)[0] is False
        assert cascade.validate_elements(cisplatin, EngineTier.G_XTB)[0] is True
        assert cascade.validate_elements(cisplatin, EngineTier.XTB2)[0] is True

    def test_theoretical_tier_mapping(self):
        """Test theoretical turnaround tier definitions (T1-1min -> T3-3h)."""
        cascade = UniversalFallbackCascade()
        assert cascade.get_theoretical_tier(EngineTier.MACE_OFF24M) == TheoreticalTier.T1_1MIN
        assert cascade.get_theoretical_tier(EngineTier.AIMNET2) == TheoreticalTier.T2_5MIN
        assert cascade.get_theoretical_tier(EngineTier.G_XTB) == TheoreticalTier.T3_30MIN
        assert cascade.get_theoretical_tier(EngineTier.XTB2) == TheoreticalTier.T3_3H

    def test_state_machine_organic_resolution(self):
        """Test resolution for purely organic molecule stays at MACE-OFF24m if hardware allows."""
        sm = FallbackCascadeStateMachine()
        ethanol = [6, 6, 8, 1, 1, 1, 1, 1, 1]
        
        state = sm.resolve_engine(atomic_numbers=ethanol, requested_engine=EngineTier.MACE_OFF24M, require_gpu_for_mlff=False)
        assert state.current_engine == EngineTier.MACE_OFF24M
        assert state.theoretical_tier == TheoreticalTier.T1_1MIN
        assert state.precision_mode == PrecisionMode.FP64
        assert not state.is_downgraded

    def test_state_machine_cascade_on_unsupported_elements(self):
        """Test automatic downgrade cascade when elements are unsupported."""
        sm = FallbackCascadeStateMachine()

        # Silicon -> cascades MACE-OFF24m (T1) -> AIMNet2 (T2)
        silane = [14, 1, 1, 1, 1]
        state_silane = sm.resolve_engine(atomic_numbers=silane, requested_engine=EngineTier.MACE_OFF24M, require_gpu_for_mlff=False)
        assert state_silane.current_engine == EngineTier.AIMNET2
        assert state_silane.theoretical_tier == TheoreticalTier.T2_5MIN
        assert state_silane.is_downgraded
        assert len(state_silane.transitions) == 1
        assert state_silane.transitions[0].reason == FallbackReason.UNSUPPORTED_ELEMENTS

        # Ferrocene (Fe=26) -> cascades MACE-OFF24m -> AIMNet2 -> g-xTB (T3-30min)
        ferrocene = [26, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        state_fe = sm.resolve_engine(atomic_numbers=ferrocene, requested_engine=EngineTier.MACE_OFF24M, require_gpu_for_mlff=False)
        assert state_fe.current_engine in (EngineTier.G_XTB, EngineTier.XTB2)
        assert state_fe.is_downgraded

    def test_manual_step_fallback_sequence(self):
        """Test step-by-step state machine transition down the hierarchy."""
        sm = FallbackCascadeStateMachine()
        state = CascadeState(
            current_engine=EngineTier.MACE_OFF24M,
            initial_engine=EngineTier.MACE_OFF24M,
            target_device=DeviceType.CUDA,
            precision_mode=PrecisionMode.FP64,
            theoretical_tier=TheoreticalTier.T1_1MIN,
        )

        # Step 1: MACE (T1-1min) -> AIMNet2 (T2-5min)
        state = sm.step_fallback(state, FallbackReason.INSUFFICIENT_VRAM, "VRAM below 2GB")
        assert state.current_engine == EngineTier.AIMNET2
        assert state.theoretical_tier == TheoreticalTier.T2_5MIN
        assert state.is_downgraded

        # Step 2: AIMNet2 (T2-5min) -> g-xTB (T3-30min)
        state = sm.step_fallback(state, FallbackReason.NO_CUDA_DEVICE, "Switching to CPU")
        assert state.current_engine == EngineTier.G_XTB
        assert state.theoretical_tier == TheoreticalTier.T3_30MIN
        assert state.target_device == DeviceType.CPU

        # Step 3: g-xTB (T3-30min) -> xTB2 (T3-3h)
        state = sm.step_fallback(state, FallbackReason.EXECUTION_FAILURE, "g-xTB convergence failure")
        assert state.current_engine == EngineTier.XTB2
        assert state.theoretical_tier == TheoreticalTier.T3_3H

        # Step 4: xTB2 is terminal
        terminal_state = sm.step_fallback(state, FallbackReason.EXECUTION_FAILURE, "Terminal failure")
        assert terminal_state.current_engine == EngineTier.XTB2

    def test_precision_mandate_enforcement(self):
        """Test explicit mandate of FP64 precision across execution tiers."""
        orig_jax = os.environ.get("JAX_ENABLE_X64")
        orig_torch = torch.get_default_dtype() if torch is not None else None
        try:
            enforce_precision_tier(PrecisionMode.FP64, set_torch_default=True)
            assert os.environ["JAX_ENABLE_X64"] == "True"
            if torch is not None:
                assert torch.get_default_dtype() == torch.float64
        finally:
            if orig_jax is not None:
                os.environ["JAX_ENABLE_X64"] = orig_jax
            else:
                os.environ.pop("JAX_ENABLE_X64", None)
            if torch is not None and orig_torch is not None:
                torch.set_default_dtype(orig_torch)


# ============================================================================
# 4. HDF5 State Manager & QCSchema Layout Tests
# ============================================================================

class TestToposHDF5MemoryManager:
    """Tests for ToposHDF5MemoryManager with real HDF5 files and file locking."""

    def test_database_initialization_without_swmr(self, tmp_path: Path):
        """Test database creation without SWMR flag, verifying QCSchema layout and root attributes."""
        db_file = tmp_path / "test_landscape.h5"
        manager = ToposHDF5MemoryManager(db_path=db_file)
        
        assert manager.db_path == db_file
        assert manager.lock_path == Path(f"{db_file}.lock")

        # Check groups and root attributes
        with manager.open_reader() as f:
            assert f.attrs["pipeline"] == "CoChem-TOPOS"
            assert f.attrs["precision_mandate"] == "float64"
            assert "meta" in f
            assert "methods" in f
            assert "points" in f
            assert "geometries" in f
            assert "trajectories" in f
            assert "telemetry" in f

    def test_write_and_read_qcschema_point_and_method(self, tmp_path: Path):
        """Test QCSchema point writing with chunking, gzip compression, fletcher32, and atomic flush."""
        db_file = tmp_path / "qcschema_test.h5"
        manager = ToposHDF5MemoryManager(db_path=db_file)

        # Register method
        manager.register_method(
            method_id="mace_off24m_dft_ref",
            engine=EngineTier.MACE_OFF24M,
            basis="def2-TZVP",
            parameters={"cutoff": 5.0, "max_ell": 3},
            precision="float64",
        )
        method_meta = manager.read_method("mace_off24m_dft_ref")
        assert method_meta is not None
        assert method_meta["engine"] == EngineTier.MACE_OFF24M.value
        assert method_meta["precision"] == "float64"
        assert method_meta["parameters"]["cutoff"] == 5.0

        # Real Benzene (C6H6) structure
        atomic_numbers = [6, 6, 6, 6, 6, 6, 1, 1, 1, 1, 1, 1]
        coords = [
            [0.0, 1.397, 0.0],
            [1.210, 0.698, 0.0],
            [1.210, -0.698, 0.0],
            [0.0, -1.397, 0.0],
            [-1.210, -0.698, 0.0],
            [-1.210, 0.698, 0.0],
            [0.0, 2.481, 0.0],
            [2.148, 1.240, 0.0],
            [2.148, -1.240, 0.0],
            [0.0, -2.481, 0.0],
            [-2.148, -1.240, 0.0],
            [-2.148, 1.240, 0.0],
        ]
        energy = -232.2478
        gradient = [
            [0.00012, -0.00008, 0.00003],
            [-0.00015, 0.00011, -0.00004],
            [0.00009, -0.00014, 0.00002],
            [-0.00008, 0.00007, -0.00003],
            [0.00011, -0.00009, 0.00005],
            [-0.00009, 0.00013, -0.00003],
            [0.00004, -0.00005, 0.00001],
            [-0.00003, 0.00004, -0.00002],
            [0.00005, -0.00003, 0.00001],
            [-0.00002, 0.00005, -0.00002],
            [0.00003, -0.00004, 0.00002],
            [-0.00007, 0.00003, -0.00001],
        ]
        hessian = [[0.45 if i == j else (0.02 / (1.0 + abs(i - j))) for j in range(36)] for i in range(36)]

        manager.write_qcschema_point(
            point_id="benzene_ground_state",
            coordinates=coords,
            energy=energy,
            atomic_numbers=atomic_numbers,
            gradient=gradient,
            hessian=hessian,
            method_id="mace_off24m_dft_ref",
            meta={"symmetry": "D6h", "charge": 0},
        )

        with manager.open_reader() as f:
            pt_grp = f["points"]["benzene_ground_state"]
            coords_ds = pt_grp["coordinates"]
            assert coords_ds.chunks is not None
            assert coords_ds.compression == "gzip"
            assert coords_ds.fletcher32 is True
            assert coords_ds.dtype == np.float64

        pt_read = manager.read_qcschema_point("benzene_ground_state")
        assert pt_read is not None
        assert pt_read.point_id == "benzene_ground_state"
        assert pt_read.atomic_numbers == atomic_numbers
        assert np.allclose(pt_read.coordinates, coords)
        assert pytest.approx(pt_read.energy, 1e-6) == energy
        assert pt_read.gradient is not None
        assert np.allclose(pt_read.gradient, gradient)
        assert pt_read.hessian is not None
        assert np.allclose(pt_read.hessian, hessian)
        assert pt_read.method_id == "mace_off24m_dft_ref"
        assert pt_read.meta["symmetry"] == "D6h"

        assert "benzene_ground_state" in manager.list_points()
        assert "mace_off24m_dft_ref" in manager.list_methods()

    def test_write_and_read_geometry_record(self, tmp_path: Path):
        """Test writing and reading a complete geometry record with tensors."""
        db_file = tmp_path / "geom_test.h5"
        manager = ToposHDF5MemoryManager(db_path=db_file)

        # Real water molecule (H2O) data
        atomic_numbers = [8, 1, 1]
        coords = [
            [0.0, 0.0, 0.1173],
            [0.0, 0.7572, -0.4692],
            [0.0, -0.7572, -0.4692],
        ]
        energy = -76.432154
        gradient = [
            [0.0001, -0.0002, 0.0003],
            [-0.0001, 0.0001, -0.0001],
            [0.0000, 0.0001, -0.0002],
        ]
        hessian = [
            [0.612, 0.015, -0.008, -0.301, 0.004, 0.002, -0.311, -0.019, 0.006],
            [0.015, 0.584, 0.011, 0.008, -0.292, -0.005, -0.023, -0.292, -0.006],
            [-0.008, 0.011, 0.630, -0.004, 0.006, -0.315, 0.012, -0.017, -0.315],
            [-0.301, 0.008, -0.004, 0.305, -0.002, 0.001, -0.004, -0.006, 0.003],
            [0.004, -0.292, 0.006, -0.002, 0.295, -0.003, -0.002, -0.003, -0.003],
            [0.002, -0.005, -0.315, 0.001, -0.003, 0.320, -0.003, 0.008, -0.005],
            [-0.311, -0.023, 0.012, -0.004, -0.002, -0.003, 0.315, 0.025, -0.009],
            [-0.019, -0.292, -0.017, -0.006, -0.003, 0.008, 0.025, 0.295, 0.009],
            [0.006, -0.006, -0.315, 0.003, -0.003, -0.005, -0.009, 0.009, 0.320],
        ]
        metadata = {"basis": "def2-TZVP", "charge": 0, "multiplicity": 1}

        record = GeometryRecord(
            geom_id="H2O_opt_01",
            atomic_numbers=atomic_numbers,
            coords=coords,
            energy=energy,
            gradient=gradient,
            hessian=hessian,
            metadata=metadata,
        )

        manager.write_geometry(record)

        read_record = manager.read_geometry("H2O_opt_01")
        assert read_record is not None
        assert read_record.geom_id == "H2O_opt_01"
        assert read_record.atomic_numbers == atomic_numbers
        assert np.allclose(read_record.coords, coords)
        assert pytest.approx(read_record.energy, 1e-6) == energy
        assert read_record.gradient is not None
        assert np.allclose(read_record.gradient, gradient)
        assert read_record.hessian is not None
        assert np.allclose(read_record.hessian, hessian)

    def test_trajectory_append_and_read(self, tmp_path: Path):
        """Test writing and reading time-series trajectory steps."""
        db_file = tmp_path / "traj_test.h5"
        manager = ToposHDF5MemoryManager(db_path=db_file)

        geom_id = "traj_mol_42"
        steps_data = []
        for step in range(5):
            t_step = TrajectoryStep(
                geom_id=geom_id,
                step_index=step,
                coords=[[0.0, 0.0, float(step)], [1.0, 1.0, float(step)]],
                energy=-100.0 - float(step) * 0.1,
                forces=[[0.01 * step, 0.0, -0.02], [-0.01 * step, 0.0, 0.02]],
                timestamp=time.time() + step,
            )
            manager.append_trajectory_step(t_step)
            steps_data.append(t_step)

        read_steps = manager.read_trajectory(geom_id)
        assert len(read_steps) == 5
        for i, s in enumerate(read_steps):
            assert s.step_index == i
            assert pytest.approx(s.energy, 1e-6) == steps_data[i].energy
            assert np.allclose(s.coords, steps_data[i].coords)
            assert np.allclose(s.forces, steps_data[i].forces)

    def test_telemetry_recording_and_retrieval(self, tmp_path: Path):
        """Test recording and reading hardware/engine telemetry."""
        db_file = tmp_path / "telem_test.h5"
        manager = ToposHDF5MemoryManager(db_path=db_file)

        t_rec1 = TelemetryRecord(
            record_id="tel_001",
            timestamp=time.time(),
            engine="MACE-OFF24m",
            device="cuda",
            batch_size=32,
            ram_used_bytes=4294967296,
            vram_used_bytes=2147483648,
            duration_seconds=1.24,
            extra={"temperature_c": 54.0, "status": "nominal"},
        )
        manager.record_telemetry(t_rec1)

        retrieved1 = manager.read_telemetry("tel_001")
        assert retrieved1 is not None
        assert retrieved1.engine == "MACE-OFF24m"
        assert retrieved1.device == "cuda"
        assert retrieved1.batch_size == 32

    def test_concurrent_read_write_safety(self, tmp_path: Path):
        """Test multi-threaded concurrent write and read operations."""
        db_file = tmp_path / "concurrent_test.h5"
        manager = ToposHDF5MemoryManager(db_path=db_file)

        results: list = []
        errors: list = []

        def worker_interleaved(idx: int):
            try:
                record = GeometryRecord(
                    geom_id=f"geom_worker_{idx}",
                    atomic_numbers=[1, 1],
                    coords=[[0.0, 0.0, 0.0], [0.0, 0.0, float(idx) * 0.1]],
                    energy=-1.0 - float(idx),
                    metadata={"worker_idx": idx},
                )
                manager.write_geometry(record)
                read_back = manager.read_geometry(f"geom_worker_{idx}")
                assert read_back is not None
                assert read_back.geom_id == f"geom_worker_{idx}"
                results.append(idx)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker_interleaved, args=(i,)) for i in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 16
        geoms = manager.list_geometries()
        assert len(geoms) == 16


# ============================================================================
# 5. POSIX Stale Lock Sweep & OOM Error Trapping Tests
# ============================================================================

class TestErrorTrappingAndAutopsy:
    """Tests for POSIX stale lock sweep and OOM autopsy generation on SIGKILL / 137."""

    def test_sweep_stale_locks(self, tmp_path: Path):
        """Test startup sweep detects and removes stale/dead-PID lock files."""
        stale_lock = tmp_path / "landscape.h5.lck"
        stale_lock.write_text("999999", encoding="utf-8")

        stale_lock2 = tmp_path / "other.lock"
        stale_lock2.write_text("", encoding="utf-8")
        os.utime(stale_lock2, (time.time() - 120, time.time() - 120))

        deleted = sweep_stale_locks(tmp_path)
        assert stale_lock in deleted
        assert stale_lock2 in deleted
        assert not stale_lock.exists()
        assert not stale_lock2.exists()

    def test_generate_oom_autopsy_and_error_handling(self, tmp_path: Path):
        """Test OOM autopsy generation on SIGKILL (exit code 137)."""
        autopsy_file = tmp_path / "OOM_autopsy.json"

        out_path = generate_oom_autopsy(
            exit_code=137,
            tensor_size_bytes=1024 * 1024 * 512,
            atomic_count=250,
            theoretical_tier=TheoreticalTier.T1_1MIN,
            output_path=autopsy_file,
            extra_context={"engine": "MACE-OFF24m", "stage": "hessian_construction"},
        )
        assert out_path.exists()
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["exit_code"] == 137
        assert data["is_oom"] is True
        assert data["tensor_size_bytes"] == 536870912
        assert data["atomic_count"] == 250
        assert data["theoretical_tier"] == "T1-1min"
        assert data["recommended_fallback_tier"] == "T2-5min"
        assert data["status"] == "OOM_DIAGNOSED"

        with pytest.raises(EngineOOMError) as exc_info:
            handle_engine_exit_code(
                exit_code=137,
                tensor_size_bytes=1024 * 1024 * 100,
                atomic_count=50,
                theoretical_tier=TheoreticalTier.T1_1MIN,
                output_path=tmp_path / "OOM_autopsy_raised.json",
                raise_on_oom=True,
            )
        assert exc_info.value.autopsy_path is not None
        assert exc_info.value.autopsy_path.exists()


# ============================================================================
# 6. Controlled Precision Downgrade Tests
# ============================================================================

class TestPrecisionDowngradeProtocol:
    """Tests for PrecisionDowngradeProtocol casting FP64 to FP32 for memory conservation."""

    def test_torch_tensor_downgrade(self):
        """Test converting PyTorch float64 tensors to float32."""
        proto = PrecisionDowngradeProtocol()
        t_fp64 = torch.tensor([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=torch.float64)
        assert t_fp64.dtype == torch.float64

        t_fp32 = proto.downgrade_tensors(t_fp64)
        assert isinstance(t_fp32, torch.Tensor)
        assert t_fp32.dtype == torch.float32

    def test_numpy_array_downgrade(self):
        """Test converting NumPy float64 arrays to float32."""
        proto = PrecisionDowngradeProtocol()
        arr_fp64 = np.array([1.123456789, 2.987654321], dtype=np.float64)
        assert arr_fp64.dtype == np.float64

        arr_fp32 = proto.downgrade_tensors(arr_fp64)
        assert isinstance(arr_fp32, np.ndarray)
        assert arr_fp32.dtype == np.float32

    def test_nested_collection_downgrade(self):
        """Test recursive conversion across nested dicts, lists, and tuples."""
        proto = PrecisionDowngradeProtocol()
        data = {
            "geom_id": "water_01",
            "coords": np.array([[0.0, 0.0, 0.0]], dtype=np.float64),
            "energy": torch.tensor(-76.4, dtype=torch.float64),
            "nested_list": [
                np.array([1.0, 2.0], dtype=np.float64),
                {"sub_tensor": torch.tensor([3.0, 4.0], dtype=torch.float64)},
                "string_data",
                42,
            ],
        }

        downgraded = proto.downgrade_tensors(data)
        assert downgraded["coords"].dtype == np.float32
        assert downgraded["energy"].dtype == torch.float32
        assert downgraded["nested_list"][0].dtype == np.float32
        assert downgraded["nested_list"][1]["sub_tensor"].dtype == torch.float32


# ============================================================================
# 7. Mendeleev Library Dynamic Mass & Property Tests
# ============================================================================

class TestMendeleevDynamicMassAndProperties:
    """Tests for Mendeleev library integration and dynamic atomic mass retrieval."""

    def test_mendeleev_element_mass_and_symbol_resolution(self):
        """Test dynamic atomic mass and symbol resolution for various elements."""
        c_mass = get_atomic_mass("C")
        c_mass_num = get_atomic_mass(6)
        assert pytest.approx(c_mass, 1e-3) == 12.011
        assert pytest.approx(c_mass_num, 1e-3) == 12.011

        h_mass = get_atomic_mass("H")
        assert pytest.approx(h_mass, 1e-3) == 1.008

        sym_6 = get_element_symbol(6)
        sym_8 = get_element_symbol(8)
        assert sym_6 == "C"
        assert sym_8 == "O"

    def test_molecular_mass_computation(self):
        """Test dynamic molecular mass computation for H2O and Benzene."""
        h2o_mass = get_molecular_mass([8, 1, 1])
        # H2O: 15.999 + 2 * 1.008 ~ 18.015
        assert 18.01 < h2o_mass < 18.02

        benzene_mass = get_molecular_mass([6, 6, 6, 6, 6, 6, 1, 1, 1, 1, 1, 1])
        # C6H6: 6*12.011 + 6*1.008 ~ 78.114
        assert 78.10 < benzene_mass < 78.12

    def test_geometry_record_mendeleev_properties(self):
        """Test dynamic properties on GeometryRecord."""
        record = GeometryRecord(
            geom_id="h2o_test",
            atomic_numbers=[8, 1, 1],
            coords=[[0.0, 0.0, 0.0], [0.0, 0.75, 0.5], [0.0, -0.75, 0.5]],
            energy=-76.4,
        )
        assert record.symbols == ["O", "H", "H"]
        assert 18.01 < record.total_mass < 18.02

    def test_qcschema_point_mendeleev_properties(self):
        """Test dynamic properties on QCSchemaPoint."""
        pt = QCSchemaPoint(
            point_id="pt_test",
            atomic_numbers=[6, 1, 1, 1, 1],
            coordinates=[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 1.0, 1.0]],
            energy=-40.5,
        )
        assert pt.symbols == ["C", "H", "H", "H", "H"]
        assert 16.03 < pt.total_mass < 16.05

    def test_universal_fallback_cascade_mendeleev_helpers(self):
        """Test Mendeleev helpers on UniversalFallbackCascade."""
        symbols = UniversalFallbackCascade.get_element_symbols([1, 6, 7, 8])
        assert symbols == ["H", "C", "N", "O"]
        total_mass = UniversalFallbackCascade.get_total_mass([1, 6, 7, 8])
        assert 43.0 < total_mass < 43.1

    def test_backward_compatibility_aliases(self):
        """Test that cross-module compatibility aliases point to authentic classes."""
        assert ElementalCascadeRouter is UniversalFallbackCascade
        assert HDF5StateManager is ToposHDF5MemoryManager
        assert ToposMemoryBroker is HardwareResourceBroker
