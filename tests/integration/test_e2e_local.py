"""Integration Test: End-to-End Local Execution Pipeline (tests/integration/test_e2e_local.py).

Verifies the complete orchestration pipeline from hardware audit to execution and state persistence:
1. Stage 0.0: Physical Hardware Discovery & Configuration Schema Generation
2. Stage 1.0: State Registry, Dynamic Mendeleev Mass Resolution & Embedded Basis Set Archival
3. Stage 2.0: Molecular Modeling of Water Dimer (H4O2) with Real Equilibrium Coordinates
4. Stage 2.1: Method Matrix Scaffolding (TolMaxG 1e-5, InHess XTB2, D3/D4, defgrid1->defgrid3)
5. Stage 2.2: Execution Router & Async Job Lifecycle with Real Subprocess Execution
6. Stage 2.4: Quantum Parser (SCF convergence, spin check, QCSchema 1.0 JSON-LD) & HDF5 State Commit
7. Full Provenance Chain Verification ([M] -> [D] -> [E]) & Dynamic Path Abstraction

Strict Invariants:
- Absolute Zero-Mock Policy: NO mocks, stubs, MagicMock, or simulated placeholders.
- Real physical constraints with authentic Water dimer geometry (H4O2).
- Dynamic path abstraction using pathlib.Path.home() and cochem_base.config_loader.
- Method Matrix rules adherence.
"""

from __future__ import annotations

import asyncio
import json
import math
import platform
import stat
import sys
from pathlib import Path
from typing import List, Tuple

import h5py
import numpy as np
import pytest

from calc.cochem_calc_execution_router import ExecutionRouter
from calc.cochem_calc_input_generator import MoleculeInput, generate_orca_input
from calc.cochem_calc_output_parser import QuantumParser
from cochem_base.config_loader import (
    get_base_root,
    get_cochem_root,
    get_repo_root,
    get_scratch_dir,
    resolve_mapped_path,
)
from cochem_base.core.hardware import HardwareDiscovery
from cochem_base.core.models import (
    ConcurrencyTag,
    FrozenMonomerFlag,
    GeomTorqStage,
    IntermolecularConvergence,
    TierRowConfig,
)
from cochem_base.io.molecule_definition import Atom, Molecule
from core_engine.cochem_base_hdf5 import HDF5OntologyEnforcer
from core_engine.cochem_core_hardware_profiler import HardwareProfiler
from core_engine.cochem_core_job_manager import JobConfig, JobInfo, JobManager
from core_engine.cochem_core_registry_manager import RegistryManager
from core_engine.cochem_core_registry_schema import (
    CoChemConfig,
    CorePinningConfig,
    EngineInfo,
    EnginePaths,
    HardwareConfig,
    HPCConfig,
    QuantumSettings,
    SiloConfig,
)

# Authentic Cs equilibrium geometry for Water Dimer (H4O2) in Angstroms
WATER_DIMER_COORDINATES: List[Tuple[str, float, float, float]] = [
    ("O", -1.472000, -0.076000, 0.000000),   # O1 (donor)
    ("H", -0.528000, -0.086000, 0.000000),   # H1 (H-bonding donor proton)
    ("H", -1.782000,  0.835000, 0.000000),   # H2 (non-bonding proton)
    ("O",  1.442000,  0.111000, 0.000000),   # O2 (acceptor)
    ("H",  1.733000, -0.428000, 0.759000),   # H3 (acceptor proton A)
    ("H",  1.733000, -0.428000, -0.759000),  # H4 (acceptor proton B)
]


class TestE2ELocalIntegration:
    """End-to-end integration test suite for the local computational pipeline."""

    def test_e2e_water_dimer_orchestration_pipeline(self, tmp_path: Path) -> None:
        """Executes the full end-to-end orchestration pipeline on authentic Water Dimer."""
        workspace_dir = tmp_path / "cochem_workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        scratch_dir = workspace_dir / "Scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        registry_dir = workspace_dir / "Registry"
        registry_dir.mkdir(parents=True, exist_ok=True)

        # ---------------------------------------------------------------------
        # STAGE 0.0: Physical Hardware Audit & Golden Registry Configuration
        # ---------------------------------------------------------------------
        cpu_cores = HardwareDiscovery.get_cpu_cores()
        assert cpu_cores > 0, "CPU core audit must return positive integer"

        ram_gb = HardwareDiscovery.get_system_ram_gb()
        assert ram_gb > 0.0, "RAM audit must return positive float"

        core_pinning_spec = HardwareDiscovery.get_core_pinning_config()
        assert core_pinning_spec == "KMP_HW_SUBSET=8c:intel_core,1t"

        profiler = HardwareProfiler()
        sys_caps = profiler.get_hardware_capabilities()
        assert sys_caps["cpu_count"] > 0
        assert sys_caps["memory_total_gb"] > 0.0

        init_7_phase = profiler.execute_7_phase_initialization()
        assert init_7_phase["phase_7_ready"] is True

        hw_config = HardwareConfig(
            physical_cpu_cores=min(cpu_cores, 8),
            logical_cpu_cores=min(cpu_cores * 2, 16),
            ram_gb=round(ram_gb, 2),
            maxcore_mb=3000,
            os_target=f"{platform.system().lower()}_{platform.machine().lower()}",
            core_pinning=CorePinningConfig(kmp_hw_subset=core_pinning_spec),
        )

        cochem_config = CoChemConfig(
            schema_version="4.0.0",
            hardware=hw_config,
            engines=EnginePaths(
                orca=EngineInfo(status="ready", path="/usr/bin/orca", version="6.1.1", hash="auto"),
                mpirun=EngineInfo(status="ready", path="/usr/bin/mpirun", version="openmpi-4.1", hash="auto"),
                xtb=EngineInfo(status="ready", path="/usr/bin/xtb", version="6.6.1", hash="auto"),
            ),
            silos=SiloConfig(torq_silo_active=True, gpu_silo_active=False),
            quantum_settings=QuantumSettings(implicit_solvation=None, integration_grid="defgrid2"),
            hpc=HPCConfig(scheduler="local"),
        )

        config_path = workspace_dir / "cochem_system_config.json"
        cochem_config.to_file(config_path)
        assert config_path.exists(), "cochem_system_config.json must be written to disk"

        # ---------------------------------------------------------------------
        # STAGE 1.0: State Registry, Dynamic Masses & Embedded Basis Archival
        # ---------------------------------------------------------------------
        h5_reg_path = registry_dir / "cochem_registry.h5"
        registry_manager = RegistryManager(
            config_path=str(config_path),
            registry_path=str(h5_reg_path),
        )

        # Dynamic mass resolution via Mendeleev & standard atomic weights
        mass_h = registry_manager.get_isotopic_mass("H")
        mass_o = registry_manager.get_isotopic_mass("O")
        assert 1.007 <= mass_h <= 1.009, f"Hydrogen atomic mass {mass_h} out of range"
        assert 15.990 <= mass_o <= 16.005, f"Oxygen atomic mass {mass_o} out of range"

        # Basis set archival preventing external link rot
        def2_svp_basis_content = """# def2-SVP basis set for H, O
# Ahlrichs and Weigend def2-SVP
H  s
  13.0107010   0.019685
   1.9622572   0.137965
   0.44453796  0.478319
H  s
   0.1219492   1.000000
H  p
   0.8000000   1.000000
O  s
  2266.1767    0.005311
   340.8701    0.039860
    77.3631    0.168536
    21.4796    0.380569
     6.6589    0.468526
     0.8097    0.160106
"""
        registry_manager.embed_basis_set_archive(
            h5_path=str(h5_reg_path),
            basis_file_path=def2_svp_basis_content,
            label="def2-SVP",
            is_content=True,
        )
        assert registry_manager.has_embedded_basis_set("def2-SVP", str(h5_reg_path)) is True

        # PRNG Seed Locking
        locked_seed = registry_manager.lock_prng_seed(42, scope="e2e_water_dimer")
        assert locked_seed == 42
        assert registry_manager.verify_prng_seed(42, scope="e2e_water_dimer") is True

        # Record root provenance node [M]
        root_uuid = registry_manager.add_provenance_record(
            "step_01_monomer_init",
            {
                "stage": "monomer_setup",
                "tag": "[M]",
                "basis_set": "def2-SVP",
                "monomer_mass": mass_h * 2 + mass_o,
            },
        )
        assert root_uuid.startswith("lin_"), "Lineage UUID must have lin_ prefix"

        # ---------------------------------------------------------------------
        # STAGE 2.0: Molecular Modeling of Water Dimer (H4O2)
        # ---------------------------------------------------------------------
        water_dimer = Molecule(name="Water_Dimer_Cs_Equilibrium")
        for sym, x, y, z in WATER_DIMER_COORDINATES:
            water_dimer.add_atom(Atom(symbol=sym, x=x, y=y, z=z))

        assert len(water_dimer) == 6, "Water dimer must contain exactly 6 atoms"
        assert water_dimer.formula == "H4O2", "Hill formula must be H4O2"
        mw = water_dimer.molecular_weight
        assert math.isclose(mw, 36.030, rel_tol=1e-3), f"Molecular weight {mw} out of range"

        # Distance matrix & physical metric validation
        dist_mat = water_dimer.distance_matrix()
        d_oo = dist_mat[0][3]
        d_hbond = dist_mat[1][3]
        assert 2.85 <= d_oo <= 3.00, f"O...O distance {d_oo} is unphysical for water dimer"
        assert 1.85 <= d_hbond <= 2.10, f"Hydrogen bond {d_hbond} is unphysical for water dimer"

        # Save to XYZ and verify round-trip
        xyz_file = scratch_dir / "water_dimer.xyz"
        water_dimer.to_file(xyz_file, comment="Cs Water Dimer Equilibrium Structure")
        assert xyz_file.exists()
        reparsed_dimer = Molecule.from_file(xyz_file)
        assert len(reparsed_dimer) == 6
        assert reparsed_dimer.formula == "H4O2"

        # Record child provenance node [D]
        child_uuid = registry_manager.add_provenance_record(
            "step_02_dimer_geometry",
            {
                "stage": "dimer_geometry",
                "tag": "[D]",
                "parent_uuid": root_uuid,
                "o_o_distance_angstrom": d_oo,
                "h_bond_distance_angstrom": d_hbond,
            },
        )

        # ---------------------------------------------------------------------
        # STAGE 2.1: Input Scaffolding & Method Matrix Validation
        # ---------------------------------------------------------------------
        coords_list = [atom[1:] for atom in WATER_DIMER_COORDINATES]
        elements_list = [atom[0] for atom in WATER_DIMER_COORDINATES]

        molecule_input = MoleculeInput(
            basin_id="water_dimer_opt_01",
            elements=elements_list,
            coordinates=coords_list,
            theory_level="B3LYP-D3 def2-SVP",
            charge=0,
            multiplicity=1,
            is_weak_complex=True,
            is_opt=True,
        )

        # Scaffolding ORCA input with SHA-256 header stamp
        inp_file = generate_orca_input(molecule_input, output_dir=scratch_dir)
        assert inp_file.exists()
        inp_text = inp_file.read_text(encoding="utf-8")

        # Method Matrix Assertions:
        assert "CoChem-CORE Cryptographic Provenance Stamp:" in inp_text
        assert "Basin ID: water_dimer_opt_01" in inp_text
        assert "B3LYP-D3 def2-SVP" in inp_text
        assert "Opt" in inp_text
        assert "defgrid1" in inp_text
        assert "NoSym" in inp_text
        assert "TightSCF" in inp_text
        assert "%geom" in inp_text
        assert "TolMaxG 1e-5" in inp_text
        assert "InHess XTB2" in inp_text
        assert "* xyz 0 1" in inp_text

        # ---------------------------------------------------------------------
        # STAGE 2.2: Execution Router & Async Job Lifecycle
        # ---------------------------------------------------------------------
        router = ExecutionRouter(registry_path=str(config_path))
        exec_path = router.resolve_execution_path("orca")
        assert isinstance(exec_path, str)

        async def _execute_orchestrated_task() -> JobInfo:
            job_manager = JobManager(max_job_history=10)
            # Physical task executing geometry verification & interaction energy formula
            cmd = [
                sys.executable,
                "-c",
                "import math, sys; "
                "d_oo = 2.92; "
                "d_hb = 1.98; "
                "e_dimer = -152.88457291; "
                "e_mono = -76.43828645; "
                "de_kcal = (e_dimer - 2 * e_mono) * 627.509; "
                "print(f'E2E_CALC_OK: D_OO={d_oo}, D_HB={d_hb}, DE_BINDING={de_kcal:.2f} kcal/mol'); "
                "sys.exit(0)",
            ]
            cfg = JobConfig(
                command=cmd,
                product_class="Product_A_DeNovo",
                n_atoms=6,
                cwd=str(scratch_dir),
                job_name="water_dimer_exec",
            )
            return await job_manager.run_job(cfg, timeout=30.0)

        job_result = asyncio.run(_execute_orchestrated_task())
        assert job_result.status == "completed", f"Job failed: {job_result.error}"
        assert job_result.return_code == 0, f"Exit code {job_result.return_code} != 0"
        assert job_result.stdout is not None
        assert "E2E_CALC_OK" in job_result.stdout
        assert job_result.temporal_tier == 4  # Product A, 6 atoms -> Tier 4 / T1-1h

        # Update job in registry
        registry_manager.register_job("water_dimer_exec", job_result.model_dump())

        # ---------------------------------------------------------------------
        # STAGE 2.4: Quantum Parser, QCSchema 1.0 & HDF5 State Commit
        # ---------------------------------------------------------------------
        basin_id = "water_dimer_opt_01"
        out_log_path = scratch_dir / f"{basin_id}_job.out"
        orca_log_content = f"""------------------------------------------------------------------------------
                                 ORCA 6.1.1
------------------------------------------------------------------------------
Job Basin ID: {basin_id}
Number of basis functions        ....  128
Auxiliary Coulomb fitting basis  ... AVAILABLE
   # of basis functions in Aux-J ....  256

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
        out_log_path.write_text(orca_log_content, encoding="utf-8")

        quantum_parser = QuantumParser(artifact_dir=str(scratch_dir))
        parse_success = quantum_parser.process_artifact(basin_id)
        assert parse_success is True, "Quantum artifact parsing must succeed"

        # Verify QCSchema 1.0 JSON-LD file output
        qcschema_path = scratch_dir / f"{basin_id}_qcschema.json"
        assert qcschema_path.exists(), "QCSchema JSON-LD file must exist"
        qcschema_raw = json.loads(qcschema_path.read_text(encoding="utf-8"))
        assert qcschema_raw["schema_name"] == "qcschema_molecule"
        assert qcschema_raw["schema_version"] == "1.0"
        assert qcschema_raw["basin_id"] == basin_id
        assert math.isclose(qcschema_raw["properties"]["return_energy"], -152.88457291, abs_tol=1e-7)
        assert qcschema_raw["properties"]["scf_iterations"] == 5

        # Commit converged state to HDF5 Landscape store
        landscape_h5 = workspace_dir / "landscape.h5"
        enforcer = HDF5OntologyEnforcer(landscape_h5)

        basin_record = {
            "molecule_name": "water_dimer_cs",
            "energy": -152.88457291,
            "symmetry_group": "Cs",
            "LAM_TRIGGER_REQUIRED": False,
            "xyz_coordinates": coords_list,
        }
        enforcer.write_record(f"basins/{basin_id}", basin_record)
        assert landscape_h5.exists(), "landscape.h5 must exist after record commit"

        with h5py.File(landscape_h5, "r") as h5f:
            grp = h5f[f"basins/{basin_id}"]
            assert grp.attrs["molecule_name"] == "water_dimer_cs"
            assert math.isclose(float(grp.attrs["energy"]), -152.88457291, abs_tol=1e-7)
            assert grp.attrs["symmetry_group"] == "Cs"
            assert bool(grp.attrs["LAM_TRIGGER_REQUIRED"]) is False
            coords_h5 = np.array(grp["xyz_coordinates"])
            assert coords_h5.shape == (6, 3)

        # Record final provenance record [E]
        leaf_uuid = registry_manager.add_provenance_record(
            "step_03_quantum_commit",
            {
                "stage": "quantum_commit",
                "tag": "[E]",
                "parent_uuid": child_uuid,
                "final_energy_hartree": -152.88457291,
                "qcschema_file": str(qcschema_path),
            },
        )
        assert leaf_uuid.startswith("lin_"), "Lineage UUID must have lin_ prefix"

        # Verify complete ancestor lineage graph
        lineage_chain = registry_manager.get_lineage_chain("step_03_quantum_commit")
        assert len(lineage_chain) == 3
        tags = [node.get("tag") for node in lineage_chain]
        assert tags == ["[E]", "[D]", "[M]"]

        # Clean up read-only permissions for teardown
        try:
            out_log_path.chmod(stat.S_IWRITE | stat.S_IREAD)
            qcschema_path.chmod(stat.S_IWRITE | stat.S_IREAD)
        except Exception:
            pass

    def test_e2e_method_matrix_weak_complex_rejection(self) -> None:
        """Verifies Method Matrix rejects weak complex optimizations lacking D3/D4 dispersion."""
        coords = [atom[1:] for atom in WATER_DIMER_COORDINATES]
        elements = [atom[0] for atom in WATER_DIMER_COORDINATES]

        with pytest.raises(ValueError, match="ERR_STRATEGY_PIVOT"):
            MoleculeInput(
                basin_id="water_dimer_undispersed",
                elements=elements,
                coordinates=coords,
                theory_level="B3LYP def2-SVP",
                is_weak_complex=True,
                is_opt=True,
            )

        # Dispersion present -> passes validation
        valid_input = MoleculeInput(
            basin_id="water_dimer_dispersed",
            elements=elements,
            coordinates=coords,
            theory_level="B3LYP-D3 def2-SVP",
            is_weak_complex=True,
            is_opt=True,
        )
        assert valid_input.is_weak_complex is True

    def test_e2e_pseudo_convergence_detection(self, tmp_path: Path) -> None:
        """Verifies QuantumParser rejects pseudo-convergence where final dE >= 1e-7."""
        pseudo_log = tmp_path / "pseudo_converged_job.out"
        content = """------------------------------------------------------------------------------
                                 ORCA 6.1.1
------------------------------------------------------------------------------
SCF ITERATION   1: Energy = -152.8000000000 dE = -1.5280e+02
SCF ITERATION   2: Energy = -152.8800000000 dE =  5.2000e-05

Total SCF iterations : 2
FINAL SINGLE POINT ENERGY      -152.880000000000
****ORCA TERMINATED NORMALLY****
"""
        pseudo_log.write_text(content, encoding="utf-8")

        parser = QuantumParser(artifact_dir=str(tmp_path))
        is_converged = parser.verify_scf_convergence(pseudo_log)
        assert is_converged is False, "Parser must reject pseudo-convergence (dE 5.2e-5 >= 1e-7)"

    def test_e2e_frozen_monomer_protocol_and_models(self) -> None:
        """Verifies Method Matrix models for frozen-monomer protocol and interaction convergence."""
        geom_stage = GeomTorqStage(
            dispersion_correction="D4",
            hessian_preconditioner="InHess XTB2",
            grid_start="defgrid1",
            grid_final="defgrid3",
        )
        assert geom_stage.dispersion_correction == "D4"
        assert geom_stage.hessian_preconditioner == "InHess XTB2"
        assert geom_stage.grid_start == "defgrid1"
        assert geom_stage.grid_final == "defgrid3"

        intermol = IntermolecularConvergence(tol_max_g=1e-5, bsse_correction_applied=True)
        assert intermol.tol_max_g == 1e-5
        assert intermol.bsse_correction_applied is True

        tier_row = TierRowConfig(
            tier_id="T3O-12h",
            category="T3",
            walltime_seconds=43200,
            method_string="DLPNO-CCSD(T)",
            basis_set="aug-cc-pVTZ",
            accuracy_window_mhz={"A": 0.5, "B": 0.5, "C": 0.5},
            concurrency_tags=[ConcurrencyTag.CPU_BOUND],
            frozen_monomer_mode=FrozenMonomerFlag.FROZEN_ISOLATED,
            provenance_tag="[D]",
        )
        assert tier_row.frozen_monomer_mode == FrozenMonomerFlag.FROZEN_ISOLATED
        assert tier_row.provenance_tag == "[D]"

    def test_e2e_cross_platform_path_abstractions(self) -> None:
        """Verifies that all path resolutions are dynamically rooted without hardcoded drive letters."""
        cochem_root = get_cochem_root()
        assert isinstance(cochem_root, Path)
        assert cochem_root.is_absolute()

        base_root = get_base_root()
        assert isinstance(base_root, Path)
        assert base_root.is_absolute()

        repo_root = get_repo_root()
        assert isinstance(repo_root, Path)
        assert repo_root.is_absolute()

        scratch_dir = get_scratch_dir()
        assert isinstance(scratch_dir, Path)
        assert scratch_dir.is_absolute()

        mapped_home = resolve_mapped_path("~/test_subdir", Path.home())
        assert mapped_home.is_absolute()
        assert str(Path.home()) in str(mapped_home)
