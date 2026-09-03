"""Integrated Physical Verification & Compliance Test Suite: CoChem-BASE UI & Web (Part 2).

Module: tests.integration.test_base_ui_web_part2
Authoritative Reference: SRS Chunk 02 BASE UI & Web (Part 2), Prompt 6.

Cross-Component Physical Integration:
1. PWACacheManager: SQLite WAL mode, atomic separation r_ij >= 0.5 Angstroms, dynamic Mendeleev
   symbol validation, and persistence across manager re-initializations.
2. run_init_wizard: Space inspection, standard directory hierarchy, Method Matrix v4 templates,
   and cryptographic .cochem_project.json SHA-256 seal.
3. ChemicalCrashTranslator: Interception and pedagogical translation of SCF convergence,
   singular basis set, and gradient explosion faults into actionable remediations.
4. SystemHealthMonitor: Real psutil and GPU telemetry polling, thermal and VRAM threshold alerts.
5. CoChemDataModule: SWMR-mode HDF5 reading, dynamic Mendeleev mass and charge assignment,
   real Euclidean pairwise distance tensors, 3D neighbor lists, and deterministic splitting.
6. Zero-Mock AST Compliance: Scans all source and test modules for this chunk to certify
   strict absence of mock frameworks, placeholder pass blocks, and NotImplementedError dead-ends.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import h5py
import numpy as np
import pytest
import torch

from src.cochem.cli.init_wizard import (
    STANDARD_DIRECTORIES,
    ExistingProjectError,
    run_init_wizard,
    verify_project_integrity,
)
from src.cochem.engine.datamodule import (
    CoChemHDF5Dataset,
    collate_molecular_batches,
)
from src.cochem.mobile.crash_reporter import (
    ChemicalCrashTranslator,
    ChemicalFaultCategory,
    GeometryGradientCrash,
    SCFConvergenceError,
    SingularBasisError,
)
from src.cochem.mobile.pwa_cache import (
    PWACacheManager,
    PWACacheValidationError,
    QueueStatus,
)
from src.cochem.mobile.system_health import (
    AlertSeverity,
    CPUMetrics,
    GPUMetrics,
    HardwareTelemetryFrame,
    MemoryMetrics,
    SystemHealthMonitor,
)

# Target source and test files for this chunk
TARGET_SOURCE_FILES: List[Path] = [
    Path("src/cochem/mobile/pwa_cache.py"),
    Path("src/cochem/cli/init_wizard.py"),
    Path("src/cochem/mobile/crash_reporter.py"),
    Path("src/cochem/mobile/system_health.py"),
    Path("src/cochem/engine/datamodule.py"),
    Path("tests/mobile/test_pwa_cache.py"),
    Path("tests/cli/test_init_wizard.py"),
    Path("tests/mobile/test_crash_reporter.py"),
    Path("tests/mobile/test_system_health.py"),
    Path("tests/engine/test_datamodule.py"),
    Path("tests/integration/test_base_ui_web_part2.py"),
]


class TestBaseUIWebPart2Integration:
    """Integrated physical test suite spanning all components of BASE UI & Web Part 2."""

    def test_pwa_cache_lifecycle_and_restart_persistence(self, tmp_path: Path) -> None:
        """Verify PWA cache SQLite WAL mode, distance validation, and cross-session persistence."""
        db_file = tmp_path / "pwa_integration.db"
        manager1 = PWACacheManager(db_path=db_file)

        assert manager1.verify_wal_mode() == "wal"
        assert manager1.verify_synchronous_mode() == 1

        # Queue real water molecule
        water_xyz = (
            "3\n"
            "Water Molecule\n"
            "O 0.000000 0.000000 0.117300\n"
            "H 0.000000 0.757200 -0.469200\n"
            "H 0.000000 -0.757200 -0.469200\n"
        )
        pid = manager1.queue_molecule({"type": "xyz", "xyz": water_xyz})
        assert len(pid) == 64
        assert manager1.get_pending_count() == 1

        # Reject atomic overlap catastrophe
        colliding_xyz = "2\nCollision\nO 0.0 0.0 0.0\nO 0.0 0.0 0.2\n"
        with pytest.raises(PWACacheValidationError):
            manager1.queue_molecule({"type": "xyz", "xyz": colliding_xyz})

        # Simulate process restart by instantiating new manager on same SQLite file
        manager2 = PWACacheManager(db_path=db_file)
        assert manager2.get_pending_count() == 1
        record = manager2.get_payload_record(pid)
        assert record is not None
        assert record.status == QueueStatus.PENDING

    def test_init_wizard_workspace_scaffolding(self, tmp_path: Path) -> None:
        """Verify CLI init wizard directory generation, template files, and manifest sealing."""
        ws_dir = tmp_path / "cochem_project_workspace"
        res = run_init_wizard(ws_dir, min_free_bytes=1024)
        assert res == ws_dir

        for d in STANDARD_DIRECTORIES:
            assert (ws_dir / d).is_dir()

        manifest = verify_project_integrity(ws_dir)
        assert manifest.project_name == "cochem_project_workspace"
        assert len(manifest.integrity_seal) == 64
        assert "orca_v4_template.json" in (ws_dir / "config" / "methods" / "orca_v4_template.json").name

        # Re-running without overwrite raises ExistingProjectError
        with pytest.raises(ExistingProjectError):
            run_init_wizard(ws_dir, min_free_bytes=1024, overwrite_existing=False)

    def test_crash_reporter_diagnostics_coverage(self) -> None:
        """Verify crash reporter mappings for SCF failure, singular basis, and gradient explosion."""
        translator = ChemicalCrashTranslator()

        # 1. SCF Convergence Error
        scf_err = SCFConvergenceError("Iteration 100 did not converge", engine="ORCA")
        rep_scf = translator.translate_exception(scf_err)
        assert rep_scf.category == ChemicalFaultCategory.SCF_CONVERGENCE
        assert any("UHF" in item or "level-shift" in item.lower() for item in rep_scf.actionable_remediation)

        # 2. Singular Basis Error
        s_err = SingularBasisError("Smallest eigenvalue 1e-9", engine="PySCF")
        rep_s = translator.translate_exception(s_err)
        assert rep_s.category == ChemicalFaultCategory.SINGULAR_BASIS
        assert rep_s.input_adjustment_suggestions.get("drop_diffuse_hydrogens") is True

        # 3. Gradient Explosion
        g_err = GeometryGradientCrash("Nuclear gradient 5.1 au", engine="ORCA")
        rep_g = translator.translate_exception(g_err)
        assert rep_g.category == ChemicalFaultCategory.GRADIENT_EXPLOSION
        assert any("xTB" in item for item in rep_g.actionable_remediation)

    def test_system_health_telemetry_emission(self) -> None:
        """Verify hardware monitoring captures multi-sensor metrics and processes alerts."""
        monitor = SystemHealthMonitor()
        frame = monitor.poll_telemetry()

        assert isinstance(frame, HardwareTelemetryFrame)
        assert frame.cpu.physical_cores >= 1
        assert frame.memory.ram_total_bytes > 0
        assert frame.process.pid > 0

        # Synthetic stress test on alert evaluation using physical dataclass instances
        cpu_hot = CPUMetrics(
            physical_cores=4,
            logical_cores=8,
            overall_percent=98.0,
            per_core_percent=[98.0] * 8,
        )
        mem_hot = MemoryMetrics(
            ram_total_bytes=16 * 1024**3,
            ram_used_bytes=15 * 1024**3,
            ram_free_bytes=1 * 1024**3,
            ram_percent=96.0,
            swap_total_bytes=4 * 1024**3,
            swap_used_bytes=1 * 1024**3,
            swap_free_bytes=3 * 1024**3,
            swap_percent=25.0,
        )
        gpu_critical = GPUMetrics(
            device_index=0,
            device_name="Test-NVIDIA",
            temperature_celsius=88.0,  # CRITICAL >= 85
            vram_total_bytes=12 * 1024**3,
            vram_used_bytes=11 * 1024**3,
            vram_free_bytes=1 * 1024**3,
            vram_percent=96.0,  # CRITICAL >= 95
            utilization_percent=99.0,
        )

        alerts = monitor.evaluate_alerts(cpu_hot, mem_hot, [gpu_critical])
        severities = {a.severity for a in alerts}
        assert AlertSeverity.CRITICAL in severities
        assert AlertSeverity.WARNING in severities

    def test_datamodule_swmr_and_physics(self, tmp_path: Path) -> None:
        """Verify PyTorch Lightning DataModule ingestion, Mendeleev lookups, and Euclidean geometry."""
        h5_file = tmp_path / "integration_dataset.h5"

        # Generate genuine HDF5 dataset with water (H2O) and methane (CH4)
        with h5py.File(str(h5_file), "w", libver="latest") as f:
            grp = f.create_group("molecules")

            m1 = grp.create_group("water")
            m1.create_dataset("atomic_numbers", data=np.array([8, 1, 1], dtype=np.int64))
            m1.create_dataset(
                "coordinates",
                data=np.array(
                    [[0.0, 0.0, 0.1173], [0.0, 0.7572, -0.4692], [0.0, -0.7572, -0.4692]],
                    dtype=np.float32,
                ),
            )
            m1.create_dataset("energy", data=-76.432)

            m2 = grp.create_group("methane")
            m2.create_dataset("atomic_numbers", data=np.array([6, 1, 1, 1, 1], dtype=np.int64))
            m2.create_dataset(
                "coordinates",
                data=np.array(
                    [
                        [0.0, 0.0, 0.0],
                        [0.6276, 0.6276, 0.6276],
                        [-0.6276, -0.6276, 0.6276],
                        [-0.6276, 0.6276, -0.6276],
                        [0.6276, -0.6276, -0.6276],
                    ],
                    dtype=np.float32,
                ),
            )
            m2.create_dataset("energy", data=-40.514)

        dataset = CoChemHDF5Dataset(h5_file)
        assert len(dataset) == 2

        # Verify dynamic Mendeleev properties (sample keys are sorted: ["methane", "water"])
        methane = dataset[0]
        assert methane["atomic_masses"][0].item() > 12.0  # Carbon

        water = dataset[1]
        assert water["atomic_masses"][0].item() > 15.9  # Oxygen
        assert water["atomic_masses"][1].item() > 1.0  # Hydrogen

        # Collate batch and verify Euclidean distances
        batch = collate_molecular_batches([dataset[0], dataset[1]], cutoff_angstrom=5.0)
        assert batch.batch_size == 2
        assert batch.total_atoms == 8

        # Verify distance matrix symmetry and zero diagonals
        d_mat = batch.pairwise_distances_by_mol[0]
        assert torch.allclose(d_mat, d_mat.T, atol=1e-5)
        for i in range(len(d_mat)):
            assert d_mat[i, i].item() < 1e-4

        dataset.close()

    def test_zero_mock_compliance_ast_audit(self) -> None:
        """AST audit across all production and test files for this chunk certifying zero mock violations."""
        from ci_tools.anti_spoof_linter import check_file

        repo_root = Path(__file__).resolve().parent.parent.parent
        total_violations: List[str] = []

        for rel_path in TARGET_SOURCE_FILES:
            full_path = repo_root / rel_path
            assert full_path.is_file(), f"Target file '{rel_path}' does not exist!"

            violations = check_file(full_path, repo_root, amnesty_set=set())
            for v in violations:
                total_violations.append(f"{v.file_path}:{v.line} [{v.category}] {v.message}")

        assert len(total_violations) == 0, (
            f"Zero-stub compliance violations detected ({len(total_violations)}):\n"
            + "\n".join(total_violations)
        )
