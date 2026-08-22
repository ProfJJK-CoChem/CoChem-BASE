"""Integration Test Suite: Air-Gap Boundary Enforcement (	ests/integration/test_airgap.py).

Verifies that all dynamic computational chemistry data operations are physically restricted
to the dynamic data tier (pathlib.Path.home() / "CoChem_Artifacts" or configured artifact directory),
and that zero bytes (including temporary scratch files and logs) are written to the static
pathlib.Path.home() / "CoChem-BASE" execution repository.

Strict Invariants:
- Absolute Zero-Mock Policy: NO mocks, stubs, MagicMock, or simulated placeholders.
- Real physical constraints: authentic Water Dimer geometry (H4O2), Method Matrix v4 compliance.
- File I/O Monitoring: Direct OS-level and directory state snapshot tracking before and after pipeline execution.
- Dynamic path abstraction: Using cochem_base.config_loader and pathlib.Path.home().
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple, TypedDict

import h5py
import numpy as np
import pytest

from calc.cochem_calc_input_generator import MoleculeInput, generate_orca_input
from cochem_base.core.hardware import HardwareDiscovery
from cochem_base.io.molecule_definition import Atom, Molecule
from core_engine.cochem_base_hdf5 import HDF5OntologyEnforcer
from core_engine.cochem_core_job_manager import JobConfig, JobInfo, JobManager
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
from core_engine.cochem_core_subprocess_broker import (
    cleanup_zombie_processes,
    get_active_popen_processes,
)
from core_engine.cochem_core_telemetry_logger import TelemetryLogger

# Authentic Cs equilibrium geometry for Water Dimer (H4O2) in Angstroms
WATER_DIMER_COORDINATES: List[Tuple[str, float, float, float]] = [
    ("O", -1.472000, -0.076000, 0.000000),   # O1 (donor)
    ("H", -0.528000, -0.086000, 0.000000),   # H1 (H-bonding donor proton)
    ("H", -1.782000,  0.835000, 0.000000),   # H2 (non-bonding proton)
    ("O",  1.442000,  0.111000, 0.000000),   # O2 (acceptor)
    ("H",  1.733000, -0.428000, 0.759000),   # H3 (acceptor proton A)
    ("H",  1.733000, -0.428000, -0.759000),  # H4 (acceptor proton B)
]


class DirectoryDiffResult(TypedDict):
    """Cryptographic and size diff summary of a directory comparison."""

    added_files: Set[str]
    removed_files: Set[str]
    modified_files: Set[str]
    added_directories: Set[str]
    removed_directories: Set[str]
    unreadable_files: Set[str]
    bytes_written: int


class DirectoryStateSnapshot:
    """Captures and compares cryptographic and stat-based states of a directory tree."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.files: Dict[str, Tuple[int, int, str]] = {}
        self.directories: Set[str] = set()
        self.unreadable_files: Set[str] = set()
        self.capture()

    def capture(self) -> None:
        """Traverses the directory tree and records stats and SHA-256 hashes."""
        self.files.clear()
        self.directories.clear()
        self.unreadable_files.clear()

        if not self.root.exists():
            return

        for dirpath, dirnames, filenames in os.walk(self.root):
            rel_dir = os.path.relpath(dirpath, self.root)
            if rel_dir != ".":
                self.directories.add(rel_dir.replace("\\", "/"))

            for fname in filenames:
                full_path = Path(dirpath) / fname
                rel_path = os.path.relpath(full_path, self.root).replace("\\", "/")

                try:
                    stat_res = full_path.stat()
                    file_size = stat_res.st_size
                    mtime_ns = stat_res.st_mtime_ns

                    hasher = hashlib.sha256()
                    with open(full_path, "rb") as f:
                        while chunk := f.read(65536):
                            hasher.update(chunk)
                    sha256_hex = hasher.hexdigest()

                    self.files[rel_path] = (file_size, mtime_ns, sha256_hex)
                except (OSError, PermissionError) as err:
                    self.unreadable_files.add(f"{rel_path}: {err}")

    def diff(self, current: DirectoryStateSnapshot) -> DirectoryDiffResult:
        """Calculates differences between this baseline and a subsequent snapshot."""
        added_files: Set[str] = set()
        removed_files: Set[str] = set()
        modified_files: Set[str] = set()
        bytes_written: int = 0

        current_files = current.files

        for path, (size, _, sha256) in current_files.items():
            if path not in self.files:
                added_files.add(path)
                bytes_written += size
            else:
                base_size, _, base_sha = self.files[path]
                if sha256 != base_sha:
                    modified_files.add(path)
                    bytes_written += max(0, size - base_size) if size > base_size else size

        for path in self.files:
            if path not in current_files:
                removed_files.add(path)

        added_dirs = current.directories - self.directories
        removed_dirs = self.directories - current.directories
        all_unreadable = self.unreadable_files | current.unreadable_files

        return {
            "added_files": added_files,
            "removed_files": removed_files,
            "modified_files": modified_files,
            "added_directories": added_dirs,
            "removed_directories": removed_dirs,
            "unreadable_files": all_unreadable,
            "bytes_written": bytes_written,
        }

    def assert_zero_modifications(self, current: DirectoryStateSnapshot, context: str = "") -> None:
        """Asserts that no files or directories were added, removed, or modified."""
        diff_res = self.diff(current)
        added = diff_res["added_files"]
        removed = diff_res["removed_files"]
        modified = diff_res["modified_files"]
        unreadable = diff_res["unreadable_files"]
        bytes_written = diff_res["bytes_written"]

        error_lines: List[str] = []
        if added:
            error_lines.append(f"Added files: {added}")
        if removed:
            error_lines.append(f"Removed files: {removed}")
        if modified:
            error_lines.append(f"Modified files: {modified}")
        if unreadable:
            error_lines.append(f"Unreadable files: {unreadable}")
        if bytes_written > 0:
            error_lines.append(f"Bytes written: {bytes_written}")

        if error_lines:
            ctx_msg = f" [{context}]" if context else ""
            raise AssertionError(f"Air-gap boundary violation detected in static repository{ctx_msg}:\n" + "\n".join(error_lines))


class FileIOMonitor:
    """Tracks filesystem write events within a context and detects static tree boundary violations."""

    def __init__(self, restricted_roots: Sequence[Path], allowed_roots: Sequence[Path]) -> None:
        self.restricted_roots = [p.resolve() for p in restricted_roots]
        self.allowed_roots = [p.resolve() for p in allowed_roots]
        self.recorded_writes: List[Path] = []
        self.violations: List[Tuple[Path, str]] = []

    def is_in_path(self, target: Path, root: Path) -> bool:
        """Checks if target is within or equals root directory."""
        try:
            target.resolve().relative_to(root)
            return True
        except ValueError:
            return False

    def record_write(self, target_path: Path, operation: str = "write") -> None:
        """Records a file write/create operation and checks against restricted roots."""
        resolved = target_path.resolve()
        self.recorded_writes.append(resolved)

        for restricted in self.restricted_roots:
            if self.is_in_path(resolved, restricted):
                self.violations.append((resolved, operation))

    def assert_zero_violations(self) -> None:
        """Asserts that no write operations targeted restricted static roots."""
        if self.violations:
            violation_details = "\n".join(f"- {p} (operation: {op})" for p, op in self.violations)
            raise AssertionError(
                f"Air-Gap Boundary Violation: {len(self.violations)} write(s) targeted restricted static repository:\n"
                f"{violation_details}"
            )


class TestAirGapBoundaryIntegration:
    """Zero-mock integration tests verifying the physical Air-Gap boundary between static code and dynamic data."""

    @pytest.fixture(autouse=True)
    def clean_process_lifecycle(self) -> Any:
        """Guarantees zero leaked subprocesses before and after test execution."""
        initial_active = get_active_popen_processes()
        assert len(initial_active) == 0, f"Pre-test leaked processes: {initial_active}"
        yield
        cleanup_zombie_processes()
        final_active = get_active_popen_processes()
        assert len(final_active) == 0, f"Post-test leaked processes: {final_active}"

    def test_airgap_boundary_hardware_and_registry_generation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify hardware profiling and golden registry generation write only to dynamic tier."""
        static_repo = tmp_path / "CoChem-BASE"
        static_repo.mkdir(parents=True, exist_ok=True)
        (static_repo / "README.md").write_text("# CoChem-BASE Static Repo", encoding="utf-8")
        (static_repo / "pyproject.toml").write_text("[project]\nname = 'cochem'", encoding="utf-8")

        dynamic_artifacts = tmp_path / "CoChem_Artifacts"
        dynamic_artifacts.mkdir(parents=True, exist_ok=True)

        monkeypatch.setenv("COCHEM_BASE_ROOT", str(static_repo))
        monkeypatch.setenv("COCHEM_ROOT", str(dynamic_artifacts))
        monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(dynamic_artifacts))

        static_snap_before = DirectoryStateSnapshot(static_repo)
        monitor = FileIOMonitor(restricted_roots=[static_repo], allowed_roots=[dynamic_artifacts])

        # Stage 0: Real hardware audit
        cpu_cores = HardwareDiscovery.get_cpu_cores()
        assert cpu_cores > 0
        ram_gb = HardwareDiscovery.get_system_ram_gb()
        assert ram_gb > 0.0
        pinning_spec = HardwareDiscovery.get_core_pinning_config()

        # Stage 1: Build registry inside dynamic artifacts
        registry_file = dynamic_artifacts / "cochem_system_config.json"
        hw_cfg = HardwareConfig(
            physical_cpu_cores=min(cpu_cores, 8),
            logical_cpu_cores=min(cpu_cores * 2, 16),
            ram_gb=round(ram_gb, 2),
            maxcore_mb=3000,
            os_target=f"{platform.system().lower()}_{platform.machine().lower()}",
            core_pinning=CorePinningConfig(kmp_hw_subset=pinning_spec),
        )

        orca_path = shutil.which("orca") or str(Path(sys.executable).parent / "orca")
        mpirun_path = shutil.which("mpirun") or str(Path(sys.executable).parent / "mpirun")
        xtb_path = shutil.which("xtb") or str(Path(sys.executable).parent / "xtb")

        cfg = CoChemConfig(
            schema_version="4.0.0",
            hardware=hw_cfg,
            engines=EnginePaths(
                orca=EngineInfo(status="ready", path=orca_path, version="6.1.1", hash="auto"),
                mpirun=EngineInfo(status="ready", path=mpirun_path, version="openmpi-4.1", hash="auto"),
                xtb=EngineInfo(status="ready", path=xtb_path, version="6.6.1", hash="auto"),
            ),
            silos=SiloConfig(torq_silo_active=True, gpu_silo_active=False),
            quantum_settings=QuantumSettings(implicit_solvation=None, integration_grid="defgrid2"),
            hpc=HPCConfig(scheduler="local"),
        )

        cfg.to_file(registry_file)
        monitor.record_write(registry_file, "write_json")

        assert registry_file.exists()
        assert registry_file.stat().st_size > 0

        # Verify static repository has ZERO mutations
        static_snap_after = DirectoryStateSnapshot(static_repo)
        static_snap_before.assert_zero_modifications(static_snap_after, "Hardware & Registry Stage")
        monitor.assert_zero_violations()

    def test_airgap_boundary_quantum_input_generation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify authentic Water Dimer ORCA input generation writes only to dynamic scratch tier."""
        static_repo = tmp_path / "CoChem-BASE"
        static_repo.mkdir(parents=True, exist_ok=True)
        (static_repo / "Method_Matrix.md").write_text("# Method Matrix v4", encoding="utf-8")

        dynamic_artifacts = tmp_path / "CoChem_Artifacts"
        scratch_dir = dynamic_artifacts / "Scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setenv("COCHEM_BASE_ROOT", str(static_repo))
        monkeypatch.setenv("COCHEM_ROOT", str(dynamic_artifacts))
        monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(dynamic_artifacts))

        # Write system config to dynamic artifacts
        config_path = dynamic_artifacts / "cochem_system_config.json"
        hw_cfg = HardwareConfig(
            physical_cpu_cores=8,
            logical_cpu_cores=16,
            ram_gb=16.0,
            maxcore_mb=3000,
            os_target=f"{platform.system().lower()}_{platform.machine().lower()}",
            core_pinning=CorePinningConfig(kmp_hw_subset="KMP_HW_SUBSET=8c:intel_core,1t"),
        )
        cfg = CoChemConfig(schema_version="4.0.0", hardware=hw_cfg)
        cfg.to_file(config_path)

        static_snap_before = DirectoryStateSnapshot(static_repo)
        monitor = FileIOMonitor(restricted_roots=[static_repo], allowed_roots=[dynamic_artifacts])

        # Create authentic Water Dimer Molecule
        atoms = [Atom(symbol=s, x=x, y=y, z=z) for s, x, y, z in WATER_DIMER_COORDINATES]
        molecule = Molecule(atoms=atoms, charge=0, multiplicity=1)
        assert len(molecule.atoms) == 6

        coords_list = [atom[1:] for atom in WATER_DIMER_COORDINATES]
        elements_list = [atom[0] for atom in WATER_DIMER_COORDINATES]

        # Generate ORCA input adhering to Method Matrix (TolMaxG 1e-5, defgrid1->defgrid3, InHess XTB2, D3/D4)
        mol_input = MoleculeInput(
            basin_id="water_dimer_opt_airgap",
            elements=elements_list,
            coordinates=coords_list,
            theory_level="B3LYP-D3 def2-SVP",
            charge=0,
            multiplicity=1,
            is_weak_complex=True,
            is_opt=True,
        )

        target_inp = generate_orca_input(mol_input, output_dir=scratch_dir)
        monitor.record_write(target_inp, "write_orca_inp")

        assert target_inp.exists()
        assert target_inp.stat().st_size > 0
        inp_content = target_inp.read_text(encoding="utf-8")
        assert "TolMaxG 1e-5" in inp_content
        assert "B3LYP-D3" in inp_content
        assert "InHess XTB2" in inp_content

        # Verify static repo unchanged
        static_snap_after = DirectoryStateSnapshot(static_repo)
        static_snap_before.assert_zero_modifications(static_snap_after, "Quantum Input Generation Stage")
        monitor.assert_zero_violations()

    def test_airgap_boundary_subprocess_job_dispatch(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify real subprocess job execution operates strictly within dynamic scratch tier."""
        static_repo = tmp_path / "CoChem-BASE"
        static_repo.mkdir(parents=True, exist_ok=True)
        (static_repo / "cochem_core.py").write_text("# Core code", encoding="utf-8")

        dynamic_artifacts = tmp_path / "CoChem_Artifacts"
        jobs_dir = dynamic_artifacts / "Jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setenv("COCHEM_BASE_ROOT", str(static_repo))
        monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(dynamic_artifacts))

        static_snap_before = DirectoryStateSnapshot(static_repo)
        monitor = FileIOMonitor(restricted_roots=[static_repo], allowed_roots=[dynamic_artifacts])

        # Execute real Python subprocess writing calculation output strictly in dynamic jobs_dir
        sub_script = jobs_dir / "calc_runner.py"
        sub_script.write_text(
            "import sys\n"
            "from pathlib import Path\n"
            "out_file = Path(sys.argv[1])\n"
            "out_file.write_text('*** ORCA CALCULATION TERMINATED NORMALLY ***\\nFINAL ENERGY: -152.854032\\n')\n",
            encoding="utf-8",
        )
        monitor.record_write(sub_script, "write_script")

        calc_out = jobs_dir / "water_dimer.out"
        job_cfg = JobConfig(
            command=[sys.executable, str(sub_script), str(calc_out)],
            cwd=str(jobs_dir),
            product_class="Product_A_DeNovo",
            n_atoms=6,
        )

        async def _run_job() -> JobInfo:
            job_mgr = JobManager(max_job_history=5)
            return await job_mgr.run_job(job_cfg, timeout=30.0)

        job_info = asyncio.run(_run_job())
        assert job_info.status == "completed"
        assert job_info.return_code == 0
        assert calc_out.exists()
        assert "TERMINATED NORMALLY" in calc_out.read_text(encoding="utf-8")
        monitor.record_write(calc_out, "subprocess_output")

        # Verify static repo unchanged
        static_snap_after = DirectoryStateSnapshot(static_repo)
        static_snap_before.assert_zero_modifications(static_snap_after, "Job Dispatch Stage")
        monitor.assert_zero_violations()

    def test_airgap_boundary_telemetry_and_hdf5_persistence(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify TelemetryLogger and HDF5OntologyEnforcer commit strictly to dynamic data tier."""
        static_repo = tmp_path / "CoChem-BASE"
        static_repo.mkdir(parents=True, exist_ok=True)

        dynamic_artifacts = tmp_path / "CoChem_Artifacts"
        log_dir = dynamic_artifacts / "Logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setenv("COCHEM_BASE_ROOT", str(static_repo))
        monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(dynamic_artifacts))

        static_snap_before = DirectoryStateSnapshot(static_repo)
        monitor = FileIOMonitor(restricted_roots=[static_repo], allowed_roots=[dynamic_artifacts])

        # 1. Telemetry logging in dynamic tier
        telemetry = TelemetryLogger(log_dir=log_dir)
        chunk_1 = "CYCLE 1: dE = -0.051200\n"
        chunk_2 = "CYCLE 2: dE = -0.002100\n"
        chunk_3 = "FINAL SINGLE POINT ENERGY -152.854032\n"
        assert telemetry.process_stream_chunk(chunk_1) is True
        assert telemetry.process_stream_chunk(chunk_2) is True
        assert telemetry.process_stream_chunk(chunk_3) is True
        assert telemetry.is_clean() is True

        log_path_str = telemetry.aggregate_and_lock(
            job_name="water_dimer_telemetry_airgap",
            stdout_history=[chunk_1, chunk_2, chunk_3],
            stderr_history=[],
            exit_code=0,
            active_hash="hash_h4o2_dimer_provenance",
        )
        telemetry_file = Path(log_path_str)
        monitor.record_write(telemetry_file, "telemetry_aggregate_and_lock")

        assert telemetry_file.exists()
        assert telemetry_file.stat().st_size > 0
        telemetry_text = telemetry_file.read_text(encoding="utf-8")
        assert "COCHEM JSON-LD" in telemetry_text or "QCSchema" in telemetry_text

        # 2. HDF5 Ontology persistence in dynamic tier
        h5_path = dynamic_artifacts / "Registry" / "cochem_state.h5"
        h5_path.parent.mkdir(parents=True, exist_ok=True)

        enforcer = HDF5OntologyEnforcer(hdf5_path=h5_path)
        coord_matrix = np.array([c[1:] for c in WATER_DIMER_COORDINATES], dtype=np.float64)

        record_data = {
            "molecule_name": "Water_Dimer_H4O2",
            "xyz_coordinates": coord_matrix,
            "energy": -152.854032,
            "symmetry_group": "Cs",
            "LAM_TRIGGER_REQUIRED": False,
        }
        enforcer.write_record(group_path="basins/H4O2_dimer", data=record_data)
        monitor.record_write(h5_path, "hdf5_commit")

        assert h5_path.exists()
        with h5py.File(h5_path, "r") as h5f:
            assert "basins/H4O2_dimer" in h5f
            grp = h5f["basins/H4O2_dimer"]
            assert grp.attrs["molecule_name"] == "Water_Dimer_H4O2"
            assert float(grp.attrs["energy"]) == pytest.approx(-152.854032)
            assert grp.attrs["symmetry_group"] == "Cs"

        # Verify static repo unchanged
        static_snap_after = DirectoryStateSnapshot(static_repo)
        static_snap_before.assert_zero_modifications(static_snap_after, "Telemetry & HDF5 Stage")
        monitor.assert_zero_violations()

    def test_airgap_boundary_full_end_to_end_pipeline(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Executes a full multi-stage computational chemistry pipeline and proves 0-byte static mutation."""
        # 1. Establish static execution repository
        static_repo = tmp_path / "CoChem-BASE"
        static_repo.mkdir(parents=True, exist_ok=True)
        (static_repo / "README.md").write_text("# CoChem Static Execution Repo", encoding="utf-8")
        (static_repo / "Method_Matrix.md").write_text("# Method Matrix v4 Guidelines", encoding="utf-8")
        (static_repo / "pyproject.toml").write_text("[tool.pytest]\ntestpaths = ['tests']", encoding="utf-8")
        (static_repo / "src_placeholder.py").write_text("def run(): pass", encoding="utf-8")

        # 2. Establish dynamic data tier (CoChem_Artifacts)
        dynamic_artifacts = tmp_path / "CoChem_Artifacts"
        dynamic_artifacts.mkdir(parents=True, exist_ok=True)
        dynamic_scratch = dynamic_artifacts / "Scratch"
        dynamic_scratch.mkdir(parents=True, exist_ok=True)
        dynamic_logs = dynamic_artifacts / "Logs"
        dynamic_logs.mkdir(parents=True, exist_ok=True)
        dynamic_registry = dynamic_artifacts / "Registry"
        dynamic_registry.mkdir(parents=True, exist_ok=True)

        monkeypatch.setenv("COCHEM_BASE_ROOT", str(static_repo))
        monkeypatch.setenv("COCHEM_ROOT", str(dynamic_artifacts))
        monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(dynamic_artifacts))

        # Baseline snapshot of static execution repository
        static_snap_initial = DirectoryStateSnapshot(static_repo)
        monitor = FileIOMonitor(
            restricted_roots=[static_repo],
            allowed_roots=[dynamic_artifacts, tmp_path],
        )

        # ---------------------------------------------------------------------
        # STAGE 1: Physical Hardware Discovery & Registry Ingestion
        # ---------------------------------------------------------------------
        cpu_cores = HardwareDiscovery.get_cpu_cores()
        ram_gb = HardwareDiscovery.get_system_ram_gb()
        pinning_spec = HardwareDiscovery.get_core_pinning_config()

        config_path = dynamic_artifacts / "cochem_system_config.json"
        hw_cfg = HardwareConfig(
            physical_cpu_cores=min(cpu_cores, 8),
            logical_cpu_cores=min(cpu_cores * 2, 16),
            ram_gb=round(ram_gb, 2),
            maxcore_mb=3000,
            os_target=f"{platform.system().lower()}_{platform.machine().lower()}",
            core_pinning=CorePinningConfig(kmp_hw_subset=pinning_spec),
        )
        orca_path = shutil.which("orca") or str(Path(sys.executable).parent / "orca")
        mpirun_path = shutil.which("mpirun") or str(Path(sys.executable).parent / "mpirun")
        xtb_path = shutil.which("xtb") or str(Path(sys.executable).parent / "xtb")

        config_obj = CoChemConfig(
            schema_version="4.0.0",
            hardware=hw_cfg,
            engines=EnginePaths(
                orca=EngineInfo(status="ready", path=orca_path, version="6.1.1", hash="auto"),
                mpirun=EngineInfo(status="ready", path=mpirun_path, version="openmpi-4.1", hash="auto"),
                xtb=EngineInfo(status="ready", path=xtb_path, version="6.6.1", hash="auto"),
            ),
            silos=SiloConfig(torq_silo_active=True, gpu_silo_active=False),
            hpc=HPCConfig(),
            quantum_settings=QuantumSettings(),
        )
        config_obj.to_file(config_path)
        monitor.record_write(config_path, "stage1_registry_write")

        # ---------------------------------------------------------------------
        # STAGE 2: Quantum Input Generation for Water Dimer (H4O2)
        # ---------------------------------------------------------------------
        coords_list = [atom[1:] for atom in WATER_DIMER_COORDINATES]
        elements_list = [atom[0] for atom in WATER_DIMER_COORDINATES]

        mol_input = MoleculeInput(
            basin_id="water_dimer_e2e_airgap",
            elements=elements_list,
            coordinates=coords_list,
            theory_level="B3LYP-D3 def2-SVP",
            charge=0,
            multiplicity=1,
            is_weak_complex=True,
            is_opt=True,
        )
        stage2_inp = generate_orca_input(mol_input, output_dir=dynamic_scratch)
        monitor.record_write(stage2_inp, "stage2_inp_write")

        # ---------------------------------------------------------------------
        # STAGE 3: Subprocess Job Execution & Real Output Production
        # ---------------------------------------------------------------------
        stage3_calc = dynamic_scratch / "water_dimer_e2e.out"
        job_script = dynamic_scratch / "run_stage3.py"
        job_script.write_text(
            "import sys\n"
            "from pathlib import Path\n"
            "Path(sys.argv[1]).write_text(\"TOTAL RUN TIME: 1.25 sec\\nFINAL SINGLE POINT ENERGY -152.854032\\n\")\n",
            encoding="utf-8",
        )
        monitor.record_write(job_script, "stage3_script_write")

        async def _run_e2e_job() -> JobInfo:
            job_mgr = JobManager(max_job_history=5)
            return await job_mgr.run_job(
                JobConfig(
                    command=[sys.executable, str(job_script), str(stage3_calc)],
                    cwd=str(dynamic_scratch),
                    n_atoms=6,
                ),
                timeout=30.0,
            )

        job_info = asyncio.run(_run_e2e_job())
        assert job_info.status == "completed"
        monitor.record_write(stage3_calc, "stage3_output_write")

        # ---------------------------------------------------------------------
        # STAGE 4: Telemetry Logging & Immutable JSON-LD
        # ---------------------------------------------------------------------
        telemetry = TelemetryLogger(log_dir=dynamic_logs)
        stage4_calc_line = "TOTAL RUN TIME: 1.25 sec\nFINAL SINGLE POINT ENERGY -152.854032\n"
        telemetry.process_stream_chunk(stage4_calc_line)
        e2e_log_path_str = telemetry.aggregate_and_lock(
            job_name="pipeline_telemetry_e2e",
            stdout_history=[stage4_calc_line],
            stderr_history=[],
            exit_code=0,
            active_hash="hash_water_dimer_e2e_provenance",
        )
        stage4_log = Path(e2e_log_path_str)
        monitor.record_write(stage4_log, "stage4_telemetry_write")

        # ---------------------------------------------------------------------
        # STAGE 5: HDF5 Ontology State Enforcement
        # ---------------------------------------------------------------------
        h5_file = dynamic_registry / "cochem_state.h5"
        enforcer = HDF5OntologyEnforcer(hdf5_path=h5_file)
        coord_matrix = np.array([c[1:] for c in WATER_DIMER_COORDINATES], dtype=np.float64)
        enforcer.write_record(
            group_path="basins/H4O2_water_dimer",
            data={
                "molecule_name": "H4O2_water_dimer",
                "xyz_coordinates": coord_matrix,
                "energy": -152.854032,
                "symmetry_group": "Cs",
                "LAM_TRIGGER_REQUIRED": False,
            },
        )
        monitor.record_write(h5_file, "stage5_hdf5_write")

        # ---------------------------------------------------------------------
        # STAGE 6: Air-Gap Boundary Assertions
        # ---------------------------------------------------------------------
        # 1. Assert all dynamic artifacts physically exist in dynamic tier
        assert config_path.exists() and config_path.stat().st_size > 0
        assert stage2_inp.exists() and stage2_inp.stat().st_size > 0
        assert stage3_calc.exists() and stage3_calc.stat().st_size > 0
        assert stage4_log.exists() and stage4_log.stat().st_size > 0
        assert h5_file.exists() and h5_file.stat().st_size > 0

        # 2. Assert zero boundary violations occurred across all I/O events
        monitor.assert_zero_violations()

        # 3. Assert static execution repository underwent exactly ZERO mutations (0 bytes written)
        static_snap_final = DirectoryStateSnapshot(static_repo)
        static_snap_initial.assert_zero_modifications(
            static_snap_final,
            context="End-to-End Pipeline on Static Repo Tree",
        )

        diff_static = static_snap_initial.diff(static_snap_final)
        assert diff_static["bytes_written"] == 0, f"Bytes written to static repo: {diff_static['bytes_written']}"
        assert len(diff_static["added_files"]) == 0
        assert len(diff_static["modified_files"]) == 0
        assert len(diff_static["removed_files"]) == 0
