"""Comprehensive Zero-Mock Physical Unit Test Suite for CoChem Pipeline Components.

Validates all individual pipeline components against real physical execution constraints:
1. Hardware discovery & profiling (HardwareDiscovery, HardwareProfiler, P-core pinning)
2. Configuration schema validation (CoChemConfig, HardwareConfig, QuantumSettings, EnginePaths)
3. State registry & Mendeleev atomic mass resolution & embedded basis sets (RegistryManager)
4. Molecular modeling of Water Dimer (Molecule, Atom, distance matrix, Hill formula, XYZ I/O)
5. Input scaffolding & Method Matrix validation (MoleculeInput, generate_orca_input, SHA-256 header)
6. Execution routing & job manager lifecycle (ExecutionRouter, JobManager, temporal tier assignment)
7. Quantum parser & QCSchema 1.0 & HDF5 state commit (QuantumParser, HDF5OntologyEnforcer, BasinRecord)

Strict Invariants:
- Absolute Zero-Mock Policy: All tests run against authentic physical structures and data models.
- Dynamic path abstraction using pathlib.Path.home() and cochem_base.config_loader.
- Strict Method Matrix compliance.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import stat
import sys
from pathlib import Path
from typing import Any, List, Tuple

import h5py
import numpy as np
import pytest

from calc.cochem_calc_execution_router import ExecutionRouter
from calc.cochem_calc_input_generator import MoleculeInput, generate_orca_input
from calc.cochem_calc_output_parser import (
    QCSchemaMolecule,
    QuantumParser,
)
from cochem_base.core.hardware import (
    GpuDevice,
    GpuProfile,
    HardwareDiscovery,
    HardwareProfile,
)
from cochem_base.io.molecule_definition import Atom, Molecule
from core_engine.cochem_base_hdf5 import HDF5OntologyEnforcer
from core_engine.cochem_core_hardware_profiler import HardwareProfiler
from core_engine.cochem_core_job_manager import JobConfig, JobManager
from core_engine.cochem_core_registry_manager import (
    BasisSetNotFoundError,
    IsotopeStabilityError,
    RegistryManager,
)
from core_engine.cochem_core_registry_schema import (
    CoChemConfig,
    CorePinningConfig,
    EngineInfo,
    EnginePaths,
    HardwareConfig,
    HPCConfig,
    MPSConfig,
    QuantumSettings,
    RoutingPolicy,
    SiloConfig,
    discover_engine,
    discover_host_hardware,
    validate_system_config,
)

# Authentic Cs equilibrium geometry for Water Dimer (H4O2) in Angstroms
WATER_DIMER_ATOMS: List[Tuple[str, float, float, float]] = [
    ("O", -1.472000, -0.076000, 0.000000),   # O1 (donor)
    ("H", -0.528000, -0.086000, 0.000000),   # H1 (H-bonding donor proton)
    ("H", -1.782000,  0.835000, 0.000000),   # H2 (non-bonding proton)
    ("O",  1.442000,  0.111000, 0.000000),   # O2 (acceptor)
    ("H",  1.733000, -0.428000, 0.759000),   # H3 (acceptor proton A)
    ("H",  1.733000, -0.428000, -0.759000),  # H4 (acceptor proton B)
]


# =============================================================================
# 1. Hardware Discovery & Profiling Tests
# =============================================================================

class TestHardwareDiscoveryAndProfiling:
    """Unit tests for physical hardware discovery and hardware profiler."""

    def test_hardware_discovery_cpu_cores(self) -> None:
        cores = HardwareDiscovery.get_cpu_cores()
        assert isinstance(cores, int)
        assert cores > 0

    def test_hardware_discovery_system_ram(self) -> None:
        ram_gb = HardwareDiscovery.get_system_ram_gb()
        assert isinstance(ram_gb, float)
        assert ram_gb > 0.0

    def test_hardware_discovery_core_pinning_spec(self) -> None:
        pinning_str = HardwareDiscovery.get_core_pinning_config()
        assert pinning_str == "KMP_HW_SUBSET=8c:intel_core,1t"

    def test_hardware_discovery_gpu_availability(self) -> None:
        gpu_profile = HardwareDiscovery.get_gpu_availability()
        assert isinstance(gpu_profile, GpuProfile)
        assert isinstance(gpu_profile.available, bool)
        assert isinstance(gpu_profile.fp64_capable, bool)
        assert isinstance(gpu_profile.devices, list)
        for dev in gpu_profile.devices:
            assert isinstance(dev, GpuDevice)
            assert dev.id >= 0
            assert dev.vram_gb >= 0.0

    def test_hardware_discovery_full_profile(self) -> None:
        profile = HardwareDiscovery.get_full_profile()
        assert isinstance(profile, HardwareProfile)
        assert profile.cpu_cores > 0
        assert profile.ram_gb > 0.0
        assert isinstance(profile.gpu, GpuProfile)

    def test_hardware_profiler_system_info(self) -> None:
        profiler = HardwareProfiler()
        sys_info = profiler.get_system_info()
        assert isinstance(sys_info, dict)
        assert "platform" in sys_info
        assert "cpu_count" in sys_info
        assert sys_info["cpu_count"] > 0
        assert "memory_total" in sys_info
        assert sys_info["memory_total"] > 0

    def test_hardware_profiler_capabilities(self) -> None:
        profiler = HardwareProfiler()
        caps = profiler.get_hardware_capabilities()
        assert isinstance(caps, dict)
        assert "cpu_count" in caps
        assert caps["cpu_count"] > 0
        assert "memory_total_gb" in caps
        assert caps["memory_total_gb"] > 0.0
        assert "cpu_tflops" in caps
        assert "hardware_score" in caps
        assert isinstance(caps["hardware_score"], (int, float))

    def test_hardware_profiler_7_phase_init(self) -> None:
        profiler = HardwareProfiler()
        init_results = profiler.execute_7_phase_initialization()
        assert isinstance(init_results, dict)
        assert "phase_1_nvme" in init_results
        assert "phase_4_cpu" in init_results
        assert "phase_5_ram" in init_results
        assert "phase_7_ready" in init_results
        assert init_results["phase_7_ready"] is True

    def test_hardware_profiler_cuda_info(self) -> None:
        profiler = HardwareProfiler()
        cuda_info = profiler.get_cuda_info()
        assert isinstance(cuda_info, dict)
        assert "cuda_available" in cuda_info
        assert isinstance(cuda_info["cuda_available"], bool)
        assert "gpu_count" in cuda_info


# =============================================================================
# 2. Configuration Schema Validation Tests
# =============================================================================

class TestConfigurationSchemaValidation:
    """Unit tests for Golden Registry and Pydantic configuration schemas."""

    def test_hardware_config_validation(self) -> None:
        hw = HardwareConfig(
            physical_cpu_cores=8,
            logical_cpu_cores=16,
            ram_gb=32.0,
            os_target="windows_amd64",
            maxcore_mb=3000,
        )
        assert hw.physical_cpu_cores == 8
        assert hw.logical_cpu_cores == 16
        assert hw.ram_gb == 32.0
        assert hw.ram_mb == 32768
        assert hw.maxcore_mb == 3000

    def test_hardware_config_flex_field_normalization(self) -> None:
        # Test inferring ram_mb from ram_gb and cpu_cores from physical_cpu_cores
        hw = HardwareConfig(
            cpu_cores=4,
            ram_gb=16.0,
            os_target="linux_x86_64",
        )
        assert hw.physical_cpu_cores == 4
        assert hw.logical_cpu_cores == 4
        assert hw.ram_mb == 16384
        assert hw.maxcore_mb is not None
        assert hw.maxcore_mb >= 500

    def test_quantum_settings_validation(self) -> None:
        qs = QuantumSettings(implicit_solvation="CPCM", integration_grid="defgrid2")
        assert qs.implicit_solvation == "CPCM"
        assert qs.integration_grid == "defgrid2"

        qs_smd = QuantumSettings(implicit_solvation="smd", integration_grid="defgrid3")
        assert qs_smd.implicit_solvation == "SMD"
        assert qs_smd.integration_grid == "defgrid3"

        with pytest.raises(ValueError, match="implicit_solvation"):
            QuantumSettings(implicit_solvation="INVALID_SOLV")

        with pytest.raises(ValueError, match="integration_grid"):
            QuantumSettings(integration_grid="invalid_grid")

    def test_cochem_config_default_and_roundtrip(self, tmp_path: Path) -> None:
        config = CoChemConfig.create_default(auto_detect_hardware=False)
        assert config.schema_version == "4.0.0"
        assert config.hardware.physical_cpu_cores == 4
        assert config.hardware.ram_gb == 16.0

        # Test dictionary serialization and deserialization
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        reloaded = CoChemConfig.from_dict(config_dict)
        assert reloaded.hardware.physical_cpu_cores == config.hardware.physical_cpu_cores

        # Test JSON serialization and deserialization
        json_str = config.to_json()
        assert isinstance(json_str, str)
        reloaded_json = CoChemConfig.from_json(json_str)
        assert reloaded_json.hardware.ram_gb == config.hardware.ram_gb

        # Test File I/O
        target_file = tmp_path / "test_config.json"
        config.to_file(target_file)
        assert target_file.exists()
        from_file_config = CoChemConfig.from_file(target_file)
        assert from_file_config.hardware.os_target == config.hardware.os_target

    def test_submodels_instantiation(self) -> None:
        mps = MPSConfig(enabled=True, max_workers=4, thread_percentage=50)
        assert mps.enabled is True
        assert mps.max_workers == 4

        pinning = CorePinningConfig(kmp_hw_subset="8c:intel_core,1t", anchor_p_cores=6, scout_p_cores=2)
        assert pinning.anchor_p_cores == 6

        engine_info = EngineInfo(status="found", path="/usr/bin/orca", version="6.1.1", hash="auto")
        assert engine_info.status == "found"
        assert engine_info.version == "6.1.1"

        engine_paths = EnginePaths(orca=engine_info)
        assert engine_paths.orca is not None

        silo = SiloConfig(torq_silo_active=True, gpu_silo_active=False)
        assert silo.torq_silo_active is True

        routing = RoutingPolicy(max_concurrent_mace_threads=4, max_dft_basis_functions=3000)
        assert routing.max_dft_basis_functions == 3000

        hpc = HPCConfig(scheduler="slurm", default_partition="gpu", max_walltime_hours=48)
        assert hpc.scheduler == "slurm"

    def test_discover_engine_and_hardware(self) -> None:
        py_engine = discover_engine("python")
        assert py_engine.status in ("found", "missing")
        if py_engine.status == "found":
            assert py_engine.path is not None

        hw_discovered = discover_host_hardware()
        assert isinstance(hw_discovered, HardwareConfig)
        assert hw_discovered.physical_cpu_cores > 0
        assert hw_discovered.ram_gb > 0.0

    def test_validate_system_config_gateway(self, tmp_path: Path) -> None:
        valid_dict: dict[str, Any] = {
            "hardware": {
                "physical_cpu_cores": 4,
                "logical_cpu_cores": 8,
                "ram_gb": 16.0,
                "os_target": "windows_amd64",
            }
        }
        cfg = validate_system_config(valid_dict)
        assert isinstance(cfg, CoChemConfig)

        cfg_file = tmp_path / "sys_config.json"
        cfg.to_file(cfg_file)
        cfg_loaded = validate_system_config(cfg_file)
        assert cfg_loaded.hardware.physical_cpu_cores == 4


# =============================================================================
# 3. Registry Manager, Mendeleev Mass Resolution & Embedded Basis Sets
# =============================================================================

class TestRegistryManagerAndAtomicData:
    """Unit tests for dynamic state registry, isotopic masses, and HDF5 archival."""

    def test_mendeleev_dynamic_isotopic_masses(self) -> None:
        # Standard abundant masses for H and O
        mass_h = RegistryManager.get_isotopic_mass("H")
        mass_o = RegistryManager.get_isotopic_mass("O")
        mass_c13 = RegistryManager.get_isotopic_mass("C", 13)

        assert 1.007 <= mass_h <= 1.009
        assert 15.990 <= mass_o <= 16.005
        assert 13.000 <= mass_c13 <= 13.008

    def test_isotope_stability_error_on_invalid_element(self) -> None:
        with pytest.raises(IsotopeStabilityError):
            RegistryManager.get_isotopic_mass("NonExistentElement")

    def test_get_all_isotopes(self) -> None:
        isotopes_o = RegistryManager.get_all_isotopes("O")
        assert isinstance(isotopes_o, list)
        assert len(isotopes_o) >= 3  # 16O, 17O, 18O
        symbols = {iso["symbol"] for iso in isotopes_o}
        assert "O" in symbols

    def test_embedded_basis_set_archival(self, tmp_path: Path) -> None:
        reg_file = str(tmp_path / "registry.h5")
        rm = RegistryManager(registry_path=reg_file)

        basis_content = """! def2-SVP for H, O
# Authentically embedded orbital basis definitions
H: 2s1p -> [2s, 1p]
O: 5s3p1d -> [3s, 2p, 1d]
"""
        rm.embed_basis_set_archive(
            h5_path=reg_file,
            basis_file_path=basis_content,
            label="def2-SVP",
            is_content=True,
        )

        assert rm.has_embedded_basis_set("def2-SVP", h5_path=reg_file) is True
        retrieved = rm.get_embedded_basis_set("def2-SVP", h5_path=reg_file)
        assert "def2-SVP for H, O" in retrieved

        all_bases = rm.list_embedded_basis_sets(h5_path=reg_file)
        assert "def2-SVP" in all_bases

        deleted = rm.delete_embedded_basis_set("def2-SVP", h5_path=reg_file)
        assert deleted is True
        assert rm.has_embedded_basis_set("def2-SVP", h5_path=reg_file) is False

        with pytest.raises(BasisSetNotFoundError):
            rm.get_embedded_basis_set("def2-SVP", h5_path=reg_file)

    def test_lineage_uuid_and_provenance_chain(self, tmp_path: Path) -> None:
        reg_file = str(tmp_path / "registry.h5")
        rm = RegistryManager(registry_path=reg_file)

        # 1. Root node: Setup / Monomer
        root_uuid = rm.add_provenance_record(
            "step_01_monomer",
            {"stage": "monomer_opt", "tag": "[M]", "energy_hartree": -76.4321},
        )
        assert root_uuid.startswith("lin_")

        # 2. Child node: Dimer complex
        child_uuid = rm.add_provenance_record(
            "step_02_dimer",
            {"stage": "dimer_opt", "tag": "[D]", "parent_uuid": root_uuid, "energy_hartree": -152.8845},
        )

        # 3. Leaf node: Interaction energy
        leaf_uuid = rm.add_provenance_record(
            "step_03_energy",
            {"stage": "binding_eval", "tag": "[E]", "parent_uuid": child_uuid, "delta_e_kcal": -5.02},
        )
        assert leaf_uuid.startswith("lin_")

        chain = rm.get_lineage_chain("step_03_energy")
        assert len(chain) == 3
        assert chain[0]["record_id"] == "step_03_energy"
        assert chain[1]["record_id"] == "step_02_dimer"
        assert chain[2]["record_id"] == "step_01_monomer"

    def test_prng_seed_locking_and_verification(self, tmp_path: Path) -> None:
        reg_file = str(tmp_path / "registry.h5")
        rm = RegistryManager(registry_path=reg_file)

        locked = rm.lock_prng_seed(42, scope="global")
        assert locked == 42
        assert rm.get_locked_seed("global") == 42
        assert rm.verify_prng_seed(42, scope="global") is True
        assert rm.verify_prng_seed(999, scope="global") is False

        rm.lock_prng_seed(12345, scope="sampling")
        all_seeds = rm.list_locked_seeds()
        assert all_seeds["global"] == 42
        assert all_seeds["sampling"] == 12345

    def test_job_and_hardware_profile_registry(self, tmp_path: Path) -> None:
        reg_file = str(tmp_path / "registry.h5")
        rm = RegistryManager(registry_path=reg_file)

        job_data = {"job_id": "water_dimer_opt", "status": "submitted", "tier": 4, "n_atoms": 6}
        rm.register_job("water_dimer_opt", job_data)
        fetched_job = rm.get_job("water_dimer_opt")
        assert fetched_job is not None
        assert fetched_job["status"] == "submitted"

        rm.update_job_status("water_dimer_opt", "completed", return_code=0, final_energy=-152.8845)
        updated_job = rm.get_job("water_dimer_opt")
        assert updated_job is not None
        assert updated_job["status"] == "completed"
        assert updated_job["return_code"] == 0

        all_jobs = rm.get_all_jobs()
        assert len(all_jobs) >= 1

        hw_data = {"profile_id": "node_01", "cpu_cores": 8, "ram_gb": 32.0}
        rm.register_hardware_profile("node_01", hw_data)
        fetched_hw = rm.get_hardware_profile("node_01")
        assert fetched_hw is not None
        assert fetched_hw["cpu_cores"] == 8

        stats = rm.get_registry_stats()
        assert stats["jobs_count"] >= 1
        assert stats["hardware_profiles_count"] >= 1

    def test_legacy_schema_migration(self, tmp_path: Path) -> None:
        reg_file = str(tmp_path / "legacy_registry.h5")
        with h5py.File(reg_file, "w") as h5:
            h5.attrs["version"] = "1.0.0"
            h5.create_group("jobs")

        rm = RegistryManager(registry_path=reg_file)
        report = rm.migrate_legacy_schema()
        assert report["current_version"] == "4.0.0"
        assert report["previous_version"] in ("1.0.0", "4.0.0")
        assert Path(report["registry_path"]).exists()


# =============================================================================
# 4. Molecular Modeling of Water Dimer
# =============================================================================

class TestMolecularModelingWaterDimer:
    """Unit tests for Atom, Molecule, and geometric modeling of the Water Dimer."""

    @pytest.fixture
    def water_dimer(self) -> Molecule:
        mol = Molecule(name="Water_Dimer_Cs")
        for sym, x, y, z in WATER_DIMER_ATOMS:
            mol.add_atom(Atom(symbol=sym, x=x, y=y, z=z))
        return mol

    def test_water_dimer_atom_count_and_symbols(self, water_dimer: Molecule) -> None:
        assert len(water_dimer) == 6
        assert water_dimer.num_atoms == 6
        assert water_dimer.composition == {"O": 2, "H": 4}
        assert water_dimer.atomic_numbers == [8, 1, 1, 8, 1, 1]

    def test_water_dimer_hill_formula(self, water_dimer: Molecule) -> None:
        # In Hill system without Carbon: alphabetical order (H4O2)
        assert water_dimer.formula == "H4O2"

    def test_water_dimer_molecular_weight(self, water_dimer: Molecule) -> None:
        # Standard mass: 2 * 15.999 + 4 * 1.008 = 36.030 Da
        mw = water_dimer.molecular_weight
        assert math.isclose(mw, 36.030, rel_tol=1e-3)

    def test_water_dimer_geometric_center_and_center_of_mass(self, water_dimer: Molecule) -> None:
        gc = water_dimer.geometric_center
        com = water_dimer.center_of_mass
        assert len(gc) == 3
        assert len(com) == 3
        # Centroid should be near origin along X and Y
        assert abs(gc[2]) < 1e-4  # Z-symmetry plane
        assert abs(com[2]) < 1e-4

    def test_water_dimer_translation_and_centering(self, water_dimer: Molecule) -> None:
        water_dimer.center_at_origin()
        new_gc = water_dimer.geometric_center
        assert math.isclose(new_gc[0], 0.0, abs_tol=1e-6)
        assert math.isclose(new_gc[1], 0.0, abs_tol=1e-6)
        assert math.isclose(new_gc[2], 0.0, abs_tol=1e-6)

    def test_water_dimer_distance_matrix(self, water_dimer: Molecule) -> None:
        dist_mat = water_dimer.distance_matrix()
        assert len(dist_mat) == 6
        for row in dist_mat:
            assert len(row) == 6

        # Diagonal elements must be 0.0
        for i in range(6):
            assert dist_mat[i][i] == 0.0

        # Matrix must be symmetric
        for i in range(6):
            for j in range(6):
                assert math.isclose(dist_mat[i][j], dist_mat[j][i], abs_tol=1e-6)

        # O1...O2 inter-oxygen distance: ~2.92 Å (standard Cs water dimer)
        d_oo = dist_mat[0][3]
        assert 2.85 <= d_oo <= 3.00, f"O-O distance {d_oo} out of physical range"

        # Covalent O1-H1 bond: ~0.94-0.98 Å
        d_oh_cov = dist_mat[0][1]
        assert 0.90 <= d_oh_cov <= 1.05, f"Covalent O-H distance {d_oh_cov} out of range"

        # Intermolecular H-bond H1...O2: ~1.95-2.05 Å
        d_hbond = dist_mat[1][3]
        assert 1.85 <= d_hbond <= 2.10, f"Hydrogen bond length {d_hbond} out of range"

    def test_water_dimer_xyz_roundtrip(self, water_dimer: Molecule, tmp_path: Path) -> None:
        xyz_str = water_dimer.to_xyz(comment="Cs Water Dimer Equilibrium")
        assert xyz_str.startswith("6\nCs Water Dimer Equilibrium\n")

        reparsed = Molecule.from_xyz(xyz_str)
        assert len(reparsed) == 6
        assert reparsed.formula == "H4O2"
        for orig_atom, rep_atom in zip(water_dimer.atoms, reparsed.atoms, strict=True):
            assert orig_atom.symbol == rep_atom.symbol
            assert math.isclose(orig_atom.x, rep_atom.x, abs_tol=1e-5)
            assert math.isclose(orig_atom.y, rep_atom.y, abs_tol=1e-5)
            assert math.isclose(orig_atom.z, rep_atom.z, abs_tol=1e-5)

        # Test File I/O
        xyz_path = tmp_path / "water_dimer.xyz"
        water_dimer.to_file(xyz_path)
        assert xyz_path.exists()
        from_file = Molecule.from_file(xyz_path)
        assert len(from_file) == 6
        assert from_file.formula == "H4O2"


# =============================================================================
# 5. Input Scaffolding & Method Matrix Validation
# =============================================================================

class TestInputScaffoldingAndMethodMatrix:
    """Unit tests for MoleculeInput validation and ORCA input scaffolding."""

    def test_molecule_input_dispersion_enforcement_weak_complex(self) -> None:
        coords = [atom[1:] for atom in WATER_DIMER_ATOMS]
        elements = [atom[0] for atom in WATER_DIMER_ATOMS]

        # Weak complex without D3/D4 dispersion MUST raise ValueError with [ERR_STRATEGY_PIVOT]
        with pytest.raises(ValueError, match="ERR_STRATEGY_PIVOT"):
            MoleculeInput(
                basin_id="water_dimer_no_disp",
                elements=elements,
                coordinates=coords,
                theory_level="B3LYP def2-SVP",
                is_weak_complex=True,
            )

        # Weak complex with D3 dispersion succeeds
        mol_d3 = MoleculeInput(
            basin_id="water_dimer_d3",
            elements=elements,
            coordinates=coords,
            theory_level="B3LYP-D3 def2-SVP",
            is_weak_complex=True,
        )
        assert mol_d3.is_weak_complex is True

        # Weak complex with D4 dispersion succeeds
        mol_d4 = MoleculeInput(
            basin_id="water_dimer_d4",
            elements=elements,
            coordinates=coords,
            theory_level="wb97x-d4 def2-TZVP",
            is_weak_complex=True,
        )
        assert mol_d4.theory_level == "wb97x-d4 def2-TZVP"

    def test_molecule_input_spin_multiplicity_validation(self) -> None:
        coords = [atom[1:] for atom in WATER_DIMER_ATOMS]
        elements = [atom[0] for atom in WATER_DIMER_ATOMS]

        with pytest.raises(ValueError, match="ERR_MISSING_DATA"):
            MoleculeInput(
                basin_id="invalid_spin",
                elements=elements,
                coordinates=coords,
                multiplicity=0,
            )

    def test_generate_orca_input_water_dimer_weak_complex(self, tmp_path: Path) -> None:
        coords = [atom[1:] for atom in WATER_DIMER_ATOMS]
        elements = [atom[0] for atom in WATER_DIMER_ATOMS]

        inp_data = MoleculeInput(
            basin_id="water_dimer_basin_01",
            elements=elements,
            coordinates=coords,
            theory_level="B3LYP-D3 def2-SVP",
            charge=0,
            multiplicity=1,
            is_weak_complex=True,
            is_opt=True,
        )

        out_path = generate_orca_input(inp_data, output_dir=tmp_path)
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")

        # Verify SHA-256 header provenance stamp
        assert "CoChem-CORE Cryptographic Provenance Stamp:" in content
        assert "Basin ID: water_dimer_basin_01" in content

        # Verify Method Matrix keywords: defgrid1 starting grid, NoSym, TightSCF
        assert "B3LYP-D3 def2-SVP" in content
        assert "Opt" in content
        assert "defgrid1" in content
        assert "NoSym" in content
        assert "TightSCF" in content

        # Verify Method Matrix weak complex geometry block: TolMaxG 1e-5 and InHess XTB2
        assert "%geom" in content
        assert "TolMaxG 1e-5" in content
        assert "InHess XTB2" in content

        # Verify all 6 atoms are in the coordinate block
        assert "* xyz 0 1" in content
        for el in elements:
            assert el in content

    def test_generate_orca_input_single_point(self, tmp_path: Path) -> None:
        coords = [atom[1:] for atom in WATER_DIMER_ATOMS]
        elements = [atom[0] for atom in WATER_DIMER_ATOMS]

        inp_data = MoleculeInput(
            basin_id="water_dimer_sp",
            elements=elements,
            coordinates=coords,
            theory_level="B3LYP-D3 def2-TZVP",
            is_weak_complex=True,
            is_opt=False,
        )

        out_path = generate_orca_input(inp_data, output_dir=tmp_path)
        content = out_path.read_text(encoding="utf-8")
        assert "Opt" not in content.splitlines()[5]  # No Opt on main route
        assert "%geom" not in content


# =============================================================================
# 6. Execution Router & Job Manager Lifecycle Tests
# =============================================================================

class TestExecutionRouterAndJobManagerLifecycle:
    """Unit tests for execution routing, temporal tier assignment, and async execution."""

    def test_execution_router_resolution(self) -> None:
        router = ExecutionRouter()
        resolved = router.resolve_execution_path("orca")
        assert isinstance(resolved, str)
        assert len(resolved) > 0

    def test_job_manager_temporal_tier_assignment(self) -> None:
        jm = JobManager()

        # Product A / De Novo (Water dimer: 6 atoms -> Tier 4 / T1-1h)
        cfg_dimer = JobConfig(product_class="Product_A_DeNovo", n_atoms=6)
        tier_dimer = jm._assign_temporal_tier(cfg_dimer)
        assert tier_dimer == 4

        # Product C / Differences (6 atoms -> Tier 1 / T1-10s)
        cfg_class_c = JobConfig(product_class="Product_C_Differences", n_atoms=6)
        tier_c = jm._assign_temporal_tier(cfg_class_c)
        assert tier_c == 1

        # Product B / SemiExperimental (6 atoms -> Tier 3 / T1-30min)
        cfg_class_b = JobConfig(product_class="Product_B_SemiExperimental", n_atoms=6)
        tier_b = jm._assign_temporal_tier(cfg_class_b)
        assert tier_b == 3

        # Product D / Active Learning (6 atoms -> Tier 9 / T4-1w)
        cfg_class_d = JobConfig(product_class="Product_D_ActiveLearning", n_atoms=6)
        tier_d = jm._assign_temporal_tier(cfg_class_d)
        assert tier_d == 9

        # Explicit override
        cfg_override = JobConfig(temporal_tier_override=2)
        assert jm._assign_temporal_tier(cfg_override) == 2

    def test_job_manager_real_job_execution(self) -> None:
        async def _run() -> None:
            jm = JobManager()
            cmd = [sys.executable, "-c", "import math; print(f'MW_SQRT={math.sqrt(36.03):.4f}')"]
            cfg = JobConfig(command=cmd, product_class="Product_A_DeNovo", n_atoms=6)

            job_info = await jm.run_job(cfg, timeout=15.0)
            assert job_info.status == "completed"
            assert job_info.return_code == 0
            assert job_info.stdout is not None
            assert "MW_SQRT=6.0025" in job_info.stdout
            assert job_info.duration is not None
            assert job_info.duration >= 0.0

        asyncio.run(_run())

    def test_job_manager_cancellation(self) -> None:
        async def _run() -> None:
            jm = JobManager()
            # Command that would sleep for 60 seconds
            cmd = [sys.executable, "-c", "import time; time.sleep(60)"]
            cfg = JobConfig(command=cmd, product_class="Product_A_DeNovo", n_atoms=6)

            job_id = await jm.submit_job(cfg)
            await jm.start_job(job_id)
            await asyncio.sleep(0.1)  # Brief yield to let process spawn

            cancelled = jm.cancel_job(job_id)
            assert cancelled is True
            job_info = jm.get_job(job_id)
            assert job_info is not None
            assert job_info.status == "cancelled"

        asyncio.run(_run())

    def test_job_manager_purge_and_history(self) -> None:
        async def _run() -> None:
            jm = JobManager(max_job_history=5)
            for i in range(4):
                cfg = JobConfig(command=[sys.executable, "-c", f"print({i})"])
                await jm.run_job(cfg, timeout=5.0)

            completed = jm.get_completed_jobs()
            assert len(completed) == 4

            purged = jm.purge_completed_jobs(max_age_seconds=0.0)
            assert purged == 4
            assert len(jm.get_completed_jobs()) == 0

        asyncio.run(_run())


# =============================================================================
# 7. Quantum Parser & QCSchema 1.0 & HDF5 State Commit
# =============================================================================

class TestQuantumParserAndHDF5State:
    """Unit tests for SCF convergence, QCSchema 1.0 JSON-LD, and HDF5 ontology enforcement."""

    @pytest.fixture
    def converged_orca_log(self, tmp_path: Path) -> Path:
        log_file = tmp_path / "water_dimer_job.out"
        content = """---------------------------------
ORCA 6.1.1 Quantum Chemistry
---------------------------------
Basis Dimension        Dim             ....  128
Auxiliary Coulomb fitting basis             ... AVAILABLE
   # of basis functions in Aux-J            ...  256

SCF ITERATION   1: Energy = -152.8000000000 dE = -1.5280e+02
SCF ITERATION   2: Energy = -152.8800000000 dE = -8.0000e-02
SCF ITERATION   3: Energy = -152.8845000000 dE = -4.5000e-03
SCF ITERATION   4: Energy = -152.8845729100 dE = -7.2910e-05
SCF ITERATION   5: Energy = -152.8845729100 dE =  1.2000e-08

Total SCF iterations : 5
FINAL SINGLE POINT ENERGY      -152.884572910000
Expectation value of <S**2> : 0.000000
Ideal value S*(S+1)         : 0.000000
****ORCA TERMINATED NORMALLY****
"""
        log_file.write_text(content, encoding="utf-8")
        return log_file

    def test_quantum_parser_scf_convergence_success(self, converged_orca_log: Path, tmp_path: Path) -> None:
        parser = QuantumParser(artifact_dir=str(tmp_path))
        is_converged = parser.verify_scf_convergence(converged_orca_log)
        assert is_converged is True

    def test_quantum_parser_scf_convergence_failure(self, tmp_path: Path) -> None:
        log_file = tmp_path / "failed_job.out"
        content = """
SCF ITERATION   1: Energy = -152.8000000000 dE = -1.5280e+02
SCF ITERATION   2: Energy = -152.8800000000 dE =  5.0000e-05
FINAL SINGLE POINT ENERGY      -152.880000000000
****ORCA TERMINATED NORMALLY****
"""
        log_file.write_text(content, encoding="utf-8")
        parser = QuantumParser(artifact_dir=str(tmp_path))
        is_converged = parser.verify_scf_convergence(log_file)
        assert is_converged is False  # Final dE (5e-5) >= 1e-7

    def test_quantum_parser_spin_contamination(self, converged_orca_log: Path, tmp_path: Path) -> None:
        parser = QuantumParser(artifact_dir=str(tmp_path))
        spin_ok = parser.check_spin_contamination(converged_orca_log)
        assert spin_ok is True

    def test_quantum_parser_qcschema_export(self, converged_orca_log: Path, tmp_path: Path) -> None:
        parser = QuantumParser(artifact_dir=str(tmp_path))
        log_sha = hashlib.sha256(converged_orca_log.read_bytes()).hexdigest()
        schema = parser.parse_to_qcschema(converged_orca_log, "water_dimer", log_sha)

        assert isinstance(schema, QCSchemaMolecule)
        assert schema.schema_name == "qcschema_molecule"
        assert schema.schema_version == "1.0"
        assert schema.basin_id == "water_dimer"
        assert math.isclose(schema.properties.return_energy, -152.88457291, abs_tol=1e-7)
        assert schema.properties.scf_iterations == 5
        assert schema.provenance.creator == "CoChem-CORE"
        assert schema.provenance.engine == "ORCA 6.1.1"

    def test_quantum_parser_process_artifact_and_lock(self, converged_orca_log: Path, tmp_path: Path) -> None:
        # Place artifact in the parser's expected naming scheme
        basin_id = "water_dimer"
        target_log = tmp_path / f"{basin_id}_job.out"
        if target_log != converged_orca_log:
            target_log.write_text(converged_orca_log.read_text(encoding="utf-8"), encoding="utf-8")

        parser = QuantumParser(artifact_dir=str(tmp_path))
        success = parser.process_artifact(basin_id)
        assert success is True

        json_path = tmp_path / f"{basin_id}_qcschema.json"
        assert json_path.exists()
        schema_dict = json.loads(json_path.read_text(encoding="utf-8"))
        assert schema_dict["basin_id"] == basin_id
        assert schema_dict["properties"]["return_energy"] == -152.88457291

        # Clean up read-only permissions for tempdir teardown
        try:
            target_log.chmod(stat.S_IWRITE | stat.S_IREAD)
            json_path.chmod(stat.S_IWRITE | stat.S_IREAD)
        except Exception:
            pass

    def test_hdf5_ontology_enforcer_basin_record(self, tmp_path: Path) -> None:
        h5_path = tmp_path / "landscape.h5"
        enforcer = HDF5OntologyEnforcer(h5_path)

        dimer_coords = [list(atom[1:]) for atom in WATER_DIMER_ATOMS]
        record_data = {
            "molecule_name": "water_dimer",
            "energy": -152.88457291,
            "symmetry_group": "Cs",
            "LAM_TRIGGER_REQUIRED": False,
            "xyz_coordinates": dimer_coords,
        }

        enforcer.write_record("basins/basin_water_dimer", record_data)
        assert h5_path.exists()

        with h5py.File(h5_path, "r") as h5f:
            grp = h5f["basins/basin_water_dimer"]
            assert grp.attrs["molecule_name"] == "water_dimer"
            assert math.isclose(float(grp.attrs["energy"]), -152.88457291, abs_tol=1e-7)
            assert grp.attrs["symmetry_group"] == "Cs"
            assert bool(grp.attrs["LAM_TRIGGER_REQUIRED"]) is False
            assert "xyz_coordinates" in grp
            coords_arr = np.array(grp["xyz_coordinates"])
            assert coords_arr.shape == (6, 3)

    def test_hdf5_ontology_enforcer_dataset_attributes(self, tmp_path: Path) -> None:
        h5_path = tmp_path / "matrix_state.h5"
        enforcer = HDF5OntologyEnforcer(h5_path)

        data_matrix = np.eye(6)
        metadata = {
            "molecule_name": "water_dimer_metric",
            "energy": -152.88457291,
            "symmetry_group": "Cs",
            "LAM_TRIGGER_REQUIRED": False,
        }

        enforcer.write_dataset_with_attributes("metric_tensor", data_matrix, metadata, group_name="method_matrix")

        with h5py.File(h5_path, "r") as h5f:
            dset = h5f["method_matrix/metric_tensor"]
            assert dset.shape == (6, 6)
            assert dset.attrs["symmetry_group"] == "Cs"
            assert bool(dset.attrs["LAM_TRIGGER_REQUIRED"]) is False
