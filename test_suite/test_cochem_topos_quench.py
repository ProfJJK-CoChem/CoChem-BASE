"""Comprehensive Authentic Unit and Integration Test Suite for CoChem-TOPOS Quench Engine.

Module: test_suite/test_cochem_topos_quench.py (CoChem-BASE)
Target Modules:
- mechanics/cochem_topos_quench.py (CoChem-TOPOS)
- cochem_base/interfaces/cochem_topos_quench.py (CoChem-BASE)
- cochem_base/mechanics/cochem_topos_quench.py (CoChem-BASE)

Authoritative References:
1. Method_Matrix.md (Stage 2.1 Lightning PES Quench & Steric Shatter Soft-Quench).
2. CoChem_User_Manual.md (Dynamic Execution Limits & Tripartite Air-Gap).
3. SRS Section 7.1: Lightning PES Quench & Steric Shatter Soft-Quench.
4. 02_06_mechanics_quench.md Prompt Specification.

Test Matrix:
1. Pydantic Configuration Validation & Telemetry Schema Tests.
2. Authentic Analytical Lennard-Jones ASE Calculator & Finite-Difference Gradient Verification.
3. Steric Shatter Soft-Quench Governor Detection & Steepest-Descent Force Relief.
4. Quasi-Newton / LBFGS / BFGS / FIRE Structural Relaxation Convergence.
5. PyTorch CUDA Graph Caching Manager, Module & ASE Calculator Wrapper.
6. Parallel Monomer Quencher Multi-Threaded Batch Execution & Quota Governance.
7. Authentic XYZ Coordinate I/O & Artifact Persistence.
8. CLI Argument Parsing & Headless Pipeline Execution via main().
9. AST Zero-Test-Double & Anti-Spoofing Purity Audit.
10. Air-Gap & File Hygiene Verification (UTF-8, LF, Zero Path Leaks).
"""

from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from pydantic import ValidationError

# Dynamic sys.path configuration
BASE_REPO_ROOT = Path(__file__).resolve().parent.parent
TOPOS_REPO_ROOT = BASE_REPO_ROOT.parent / "CoChem-TOPOS"

for p in [str(BASE_REPO_ROOT), str(TOPOS_REPO_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from cochem_base.interfaces.cochem_topos_quench import (
        DEFAULT_CUDA_GRAPH_WARMUP_STEPS,
        DEFAULT_FMAX,
        DEFAULT_HAZARDOUS_FORCE_THRESHOLD,
        DEFAULT_MAX_STEPS,
        DEFAULT_SOFT_QUENCH_FMAX_TARGET,
        DEFAULT_SOFT_QUENCH_MAX_STEPS,
        DEFAULT_SOFT_QUENCH_STEP_SIZE,
        AnalyticalLJCalculator,
        BatchQuenchReport,
        CUDAGraphASECalculator,
        CUDAGraphManager,
        ParallelMonomerQuencher,
        QuenchConfig,
        QuenchResult,
        SoftQuenchGovernor,
        TorchCUDAGraphWrapper,
        TorchLJModule,
        UniversalFallbackOptimizer,
        build_cli_parser,
        read_xyz_to_atoms,
        write_atoms_to_xyz,
    )
    from cochem_base.interfaces.cochem_topos_quench import (
        main as quench_main,
    )
except ImportError:
    from mechanics.cochem_topos_quench import (  # type: ignore[no-redef,assignment]
        DEFAULT_CUDA_GRAPH_WARMUP_STEPS,
        DEFAULT_FMAX,
        DEFAULT_HAZARDOUS_FORCE_THRESHOLD,
        DEFAULT_MAX_STEPS,
        DEFAULT_SOFT_QUENCH_FMAX_TARGET,
        DEFAULT_SOFT_QUENCH_MAX_STEPS,
        DEFAULT_SOFT_QUENCH_STEP_SIZE,
        AnalyticalLJCalculator,
        BatchQuenchReport,
        CUDAGraphASECalculator,
        CUDAGraphManager,
        ParallelMonomerQuencher,
        QuenchConfig,
        QuenchResult,
        SoftQuenchGovernor,
        TorchCUDAGraphWrapper,
        TorchLJModule,
        UniversalFallbackOptimizer,
        build_cli_parser,
        read_xyz_to_atoms,
        write_atoms_to_xyz,
    )
    from mechanics.cochem_topos_quench import (  # type: ignore[no-redef,assignment]
        main as quench_main,
    )

try:
    from ase import Atoms
    ASE_AVAILABLE = True
except ImportError:
    Atoms = None  # type: ignore[assignment,misc]
    ASE_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore[assignment]
    TORCH_AVAILABLE = False


# ---------------------------------------------------------------------------
# Test Fixtures (100% Authentic Physical Coordinates)
# ---------------------------------------------------------------------------

@pytest.fixture
def water_dimer_structure() -> Any:
    """Authentic unoptimized water dimer coordinate seed."""
    if not ASE_AVAILABLE:
        pytest.skip("ASE is required for Atoms fixture.")
    return Atoms(
        symbols=["O", "H", "H", "O", "H", "H"],
        positions=[
            [0.000, 0.000, 0.000],
            [0.000, 0.000, 0.957],
            [0.903, 0.000, -0.315],
            [2.850, 0.000, 0.000],
            [3.450, 0.700, 0.000],
            [3.450, -0.700, 0.000],
        ],
    )


@pytest.fixture
def clashed_cluster_structure() -> Any:
    """Severely clashed diatomic system with hazardous initial forces (F_max > 50 eV/A)."""
    if not ASE_AVAILABLE:
        pytest.skip("ASE is required for Atoms fixture.")
    # Two oxygen atoms placed at 0.5 Angstrom (severely overlapping)
    return Atoms(
        symbols=["O", "O"],
        positions=[
            [0.000, 0.000, 0.000],
            [0.500, 0.000, 0.000],
        ],
    )


# ---------------------------------------------------------------------------
# 1. Pydantic Configuration Validation & Telemetry Schema Tests
# ---------------------------------------------------------------------------

def test_quench_config_defaults_and_validation() -> None:
    """Verify QuenchConfig default parameterization and validation boundaries."""
    cfg = QuenchConfig()
    assert cfg.fmax == DEFAULT_FMAX
    assert cfg.max_steps == DEFAULT_MAX_STEPS
    assert cfg.hazardous_force_threshold == DEFAULT_HAZARDOUS_FORCE_THRESHOLD
    assert cfg.soft_quench_step_size == DEFAULT_SOFT_QUENCH_STEP_SIZE
    assert cfg.soft_quench_max_steps == DEFAULT_SOFT_QUENCH_MAX_STEPS
    assert cfg.soft_quench_fmax_target == DEFAULT_SOFT_QUENCH_FMAX_TARGET
    assert cfg.cuda_graph_warmup_steps == DEFAULT_CUDA_GRAPH_WARMUP_STEPS
    assert cfg.algorithm == "LBFGS"
    assert cfg.enable_cuda_graphs is True
    assert build_cli_parser() is not None

    # Test invalid force threshold (fmax <= 0)
    with pytest.raises(ValidationError):
        QuenchConfig(fmax=-0.01)

    # Test excessive soft quench step size (> 0.2 A)
    with pytest.raises(ValidationError):
        QuenchConfig(soft_quench_step_size=0.5)

    # Test forbidden extra attributes
    with pytest.raises(ValidationError):
        QuenchConfig(unauthorized_attribute="invalid")  # type: ignore[call-arg]


def test_quench_result_and_report_serialization() -> None:
    """Verify QuenchResult and BatchQuenchReport serialization integrity."""
    res = QuenchResult(
        structure_id="dimer_01",
        converged=True,
        initial_energy_ev=-1.250,
        final_energy_ev=-2.450,
        initial_fmax=1.850,
        final_fmax=0.032,
        soft_quenched=False,
        soft_quench_steps=0,
        optimizer_steps=15,
        total_steps=15,
        calculator_used="Analytical-LJ-Physical",
        cuda_graph_active=False,
        atomic_numbers=[8, 1, 1],
        chemical_symbols=["O", "H", "H"],
        initial_positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]],
        relaxed_positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.96], [0.91, 0.0, -0.3]],
        trajectory_energies=[-1.25, -1.80, -2.45],
        trajectory_fmax=[1.85, 0.50, 0.032],
        wall_time_seconds=0.12,
    )

    report = BatchQuenchReport(
        timestamp="2026-08-22T20:00:00Z",
        total_structures=1,
        converged_count=1,
        failed_count=0,
        soft_quenched_count=0,
        cuda_graph_accelerated_count=0,
        total_wall_time_seconds=0.12,
        results=[res],
    )

    serialized_json = report.model_dump_json(indent=2)
    assert "dimer_01" in serialized_json
    assert "Analytical-LJ-Physical" in serialized_json

    # Round-trip deserialization
    reconstructed = BatchQuenchReport.model_validate_json(serialized_json)
    assert reconstructed.total_structures == 1
    assert reconstructed.results[0].structure_id == "dimer_01"
    assert reconstructed.results[0].converged is True


# ---------------------------------------------------------------------------
# 2. Analytical Lennard-Jones Calculator & Finite-Difference Gradients
# ---------------------------------------------------------------------------

def test_analytical_lj_calculator_energy_and_forces() -> None:
    """Verify AnalyticalLJCalculator energy, forces, and finite-difference gradient agreement."""
    if not ASE_AVAILABLE:
        pytest.skip("ASE required for AnalyticalLJCalculator test.")

    calc = AnalyticalLJCalculator(epsilon_ev=0.05, default_sigma_a=1.5)
    atoms = Atoms(
        symbols=["Ar", "Ar"],
        positions=[
            [0.000, 0.000, 0.000],
            [2.500, 0.000, 0.000],
        ],
    )
    atoms.calc = calc

    energy = calc.get_potential_energy(atoms)
    assert np.isfinite(energy)
    forces = calc.get_forces(atoms)

    # Invariants: 1D separation along x-axis -> forces strictly on x-axis, F1 = -F2
    assert forces.shape == (2, 3)
    assert np.isclose(forces[0, 1], 0.0, atol=1e-8)
    assert np.isclose(forces[0, 2], 0.0, atol=1e-8)
    assert np.isclose(forces[0, 0], -forces[1, 0], atol=1e-8)
    assert np.allclose(np.sum(forces, axis=0), 0.0, atol=1e-8)  # Conservation of linear momentum

    # Numerical Central Finite Difference Validation: F = -dE/dx
    delta = 1e-5
    pos_plus = atoms.get_positions().copy()
    pos_plus[1, 0] += delta
    atoms_plus = Atoms(symbols=atoms.get_chemical_symbols(), positions=pos_plus)
    atoms_plus.calc = calc
    e_plus = calc.get_potential_energy(atoms_plus)

    pos_minus = atoms.get_positions().copy()
    pos_minus[1, 0] -= delta
    atoms_minus = Atoms(symbols=atoms.get_chemical_symbols(), positions=pos_minus)
    atoms_minus.calc = calc
    e_minus = calc.get_potential_energy(atoms_minus)

    num_force_x = -(e_plus - e_minus) / (2.0 * delta)
    analytic_force_x = forces[1, 0]

    assert np.isclose(analytic_force_x, num_force_x, atol=1e-4)


# ---------------------------------------------------------------------------
# 3. Steric Shatter Soft-Quench Governor
# ---------------------------------------------------------------------------

def test_steric_shatter_soft_quench_governor(clashed_cluster_structure: Any) -> None:
    """Verify SoftQuenchGovernor intercepts hazardous clashes and relieves forces."""
    calc = AnalyticalLJCalculator()
    atoms = clashed_cluster_structure

    # Step 1: Detect hazardous forces
    is_haz, initial_fmax = SoftQuenchGovernor.is_hazardous(
        atoms=atoms,
        calculator=calc,
        threshold=DEFAULT_HAZARDOUS_FORCE_THRESHOLD,
    )
    assert is_haz is True
    assert initial_fmax > DEFAULT_HAZARDOUS_FORCE_THRESHOLD

    # Step 2: Execute soft-quench
    rel_atoms, steps, init_f, final_f, e_trace, f_trace = SoftQuenchGovernor.execute_soft_quench(
        atoms=atoms,
        calculator=calc,
        max_steps=50,
        step_size=0.05,
        fmax_target=DEFAULT_SOFT_QUENCH_FMAX_TARGET,
    )

    assert steps > 0
    assert final_f <= DEFAULT_SOFT_QUENCH_FMAX_TARGET
    assert final_f < initial_fmax
    assert len(e_trace) == steps + 1
    # Check that energy decreased significantly during soft quench
    assert e_trace[-1] < e_trace[0]


# ---------------------------------------------------------------------------
# 4. Quasi-Newton / LBFGS Structural Relaxation
# ---------------------------------------------------------------------------

def test_universal_fallback_optimizer_relaxation(water_dimer_structure: Any) -> None:
    """Verify UniversalFallbackOptimizer successfully optimizes a molecular geometry."""
    cfg = QuenchConfig(
        fmax=0.05,
        max_steps=100,
        algorithm="LBFGS",
    )
    optimizer = UniversalFallbackOptimizer(cfg)
    result = optimizer.relax_structure(water_dimer_structure, structure_id="water_dimer_test")

    assert result.structure_id == "water_dimer_test"
    assert result.converged is True
    assert result.final_fmax <= 0.05
    assert result.final_energy_ev is not None
    assert result.initial_energy_ev is not None
    assert result.final_energy_ev <= result.initial_energy_ev
    assert len(result.relaxed_positions) == 6
    assert result.wall_time_seconds > 0.0


def test_optimizer_algorithm_selection() -> None:
    """Verify optimizer algorithm selection for LBFGS, BFGS, FIRE, and QuasiNewton."""
    if not ASE_AVAILABLE:
        pytest.skip("ASE required for optimizer selection test.")

    optimizer = UniversalFallbackOptimizer()
    from ase.optimize import BFGS, FIRE, LBFGS, QuasiNewton

    assert optimizer._get_optimizer_class("LBFGS") is LBFGS
    assert optimizer._get_optimizer_class("BFGS") is BFGS
    assert optimizer._get_optimizer_class("FIRE") is FIRE
    assert optimizer._get_optimizer_class("QuasiNewton") is QuasiNewton
    assert optimizer._get_optimizer_class("QUASI_NEWTON") is QuasiNewton


# ---------------------------------------------------------------------------
# 5. PyTorch CUDA Graph Manager, Module & ASE Calculator Wrapper
# ---------------------------------------------------------------------------

def test_cuda_graph_manager_and_torch_module() -> None:
    """Verify CUDA Graph manager detection, TorchLJModule, and TorchCUDAGraphWrapper."""
    # Test support query
    supported = CUDAGraphManager.is_cuda_graph_supported()
    assert isinstance(supported, bool)

    if not TORCH_AVAILABLE or TorchLJModule is None:
        pytest.skip("PyTorch is required for TorchLJModule test.")

    module = TorchLJModule(epsilon=0.05, sigma=2.0)
    pos_tensor = torch.tensor(
        [[[0.0, 0.0, 0.0], [2.5, 0.0, 0.0]]],
        dtype=torch.float32,
        requires_grad=True,
    )
    energy, forces = module(pos_tensor)
    assert energy.dim() == 1
    assert forces.shape == (1, 2, 3)

    # Test TorchCUDAGraphWrapper in eager/fallback mode
    wrapper = TorchCUDAGraphWrapper(model_callable=module, n_atoms=2, device="cpu")
    pos_np = np.array([[0.0, 0.0, 0.0], [2.5, 0.0, 0.0]], dtype=np.float32)
    e_val, f_val = wrapper.forward(pos_np)
    assert isinstance(e_val, float)
    assert f_val.shape == (2, 3)
    assert np.isclose(f_val[0, 0], -f_val[1, 0], atol=1e-5)

    # Test CUDAGraphASECalculator wrapper
    if ASE_AVAILABLE:
        calc = CUDAGraphASECalculator(wrapper)
        atoms = Atoms(symbols=["Ar", "Ar"], positions=pos_np)
        atoms.calc = calc
        ase_e = calc.get_potential_energy(atoms)
        ase_f = calc.get_forces(atoms)
        assert np.isclose(ase_e, e_val)
        assert np.allclose(ase_f, f_val)


# ---------------------------------------------------------------------------
# 6. Parallel Monomer Quencher Multi-Threaded Batch Execution
# ---------------------------------------------------------------------------

def test_parallel_monomer_quencher_batch() -> None:
    """Verify ParallelMonomerQuencher concurrent execution of multiple seeds."""
    if not ASE_AVAILABLE:
        pytest.skip("ASE required for ParallelMonomerQuencher test.")

    cfg = QuenchConfig(
        fmax=0.05,
        max_steps=50,
        n_workers=2,
    )
    quencher = ParallelMonomerQuencher(cfg)

    # Create 3 independent monomer test structures
    structs = {
        "mono_01": Atoms(symbols=["Ar", "Ar"], positions=[[0.0, 0.0, 0.0], [2.2, 0.0, 0.0]]),
        "mono_02": Atoms(symbols=["Ne", "Ne"], positions=[[0.0, 0.0, 0.0], [1.8, 0.0, 0.0]]),
        "mono_03": Atoms(symbols=["Kr", "Kr"], positions=[[0.0, 0.0, 0.0], [2.5, 0.0, 0.0]]),
    }

    report = quencher.quench_batch(structs)

    assert report.total_structures == 3
    assert report.converged_count == 3
    assert report.failed_count == 0
    assert len(report.results) == 3
    # Check deterministic ordering by structure_id
    assert [r.structure_id for r in report.results] == ["mono_01", "mono_02", "mono_03"]

    # Test empty structures batch
    empty_report = quencher.quench_batch({})
    assert empty_report.total_structures == 0
    assert empty_report.converged_count == 0


# ---------------------------------------------------------------------------
# 7. Authentic XYZ Coordinate I/O & Artifact Persistence
# ---------------------------------------------------------------------------

def test_xyz_io_and_persistence() -> None:
    """Verify write_atoms_to_xyz and read_xyz_to_atoms round-trip fidelity."""
    if not ASE_AVAILABLE:
        pytest.skip("ASE required for XYZ I/O test.")

    with tempfile.TemporaryDirectory() as tmpdir:
        xyz_file = Path(tmpdir) / "test_molecule.xyz"
        orig_atoms = Atoms(
            symbols=["C", "H", "H", "H", "H"],
            positions=[
                [0.000, 0.000, 0.000],
                [0.629, 0.629, 0.629],
                [-0.629, -0.629, 0.629],
                [-0.629, 0.629, -0.629],
                [0.629, -0.629, -0.629],
            ],
        )

        write_atoms_to_xyz(orig_atoms, xyz_file, comment="Methane Ground State")
        assert xyz_file.exists()

        read_atoms = read_xyz_to_atoms(xyz_file)
        assert read_atoms is not None
        assert read_atoms.get_chemical_symbols() == ["C", "H", "H", "H", "H"]
        assert np.allclose(read_atoms.get_positions(), orig_atoms.get_positions(), atol=1e-6)


# ---------------------------------------------------------------------------
# 8. CLI Argument Parsing & Headless Pipeline Execution
# ---------------------------------------------------------------------------

def test_cli_main_execution() -> None:
    """Verify main() CLI execution with argument parsing and JSON report output."""
    if not ASE_AVAILABLE:
        pytest.skip("ASE required for CLI execution test.")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_xyz = Path(tmpdir) / "input_seed.xyz"
        out_dir = Path(tmpdir) / "output_artifacts"
        atoms = Atoms(symbols=["Ar", "Ar"], positions=[[0.0, 0.0, 0.0], [2.3, 0.0, 0.0]])
        write_atoms_to_xyz(atoms, input_xyz)

        argv = [
            "--input-xyz", str(input_xyz),
            "--output-dir", str(out_dir),
            "--fmax", "0.05",
            "--max-steps", "50",
            "--json",
        ]

        exit_code = quench_main(argv)
        assert exit_code == 0
        assert (out_dir / "quench_batch_report.json").exists()
        assert (out_dir / "input_seed_quenched.xyz").exists()

        # Validate generated report contents
        report_data = json.loads((out_dir / "quench_batch_report.json").read_text(encoding="utf-8"))
        assert report_data["total_structures"] == 1
        assert report_data["converged_count"] == 1


# ---------------------------------------------------------------------------
# 9. AST Zero-Test-Double & Anti-Spoofing Purity Audit
# ---------------------------------------------------------------------------

def test_zero_test_double_ast_audit() -> None:
    """Audit AST of target implementation and test suite for zero-test-double purity."""
    target_files = [
        Path(TOPOS_REPO_ROOT) / "mechanics" / "cochem_topos_quench.py",
        Path(BASE_REPO_ROOT) / "cochem_base" / "interfaces" / "cochem_topos_quench.py",
        Path(BASE_REPO_ROOT) / "cochem_base" / "mechanics" / "cochem_topos_quench.py",
        Path(__file__).resolve(),
    ]

    banned_modules = {
        "unittest.mock",
        "mock",
        "pytest_mock",
    }
    banned_names = {
        "MagicMock",
        "Mock",
        "patch",
        "PropertyMock",
        "create_autospec",
    }

    for file_path in target_files:
        if not file_path.exists():
            continue
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in banned_modules, (
                        f"Anti-Spoof Violation: Prohibited import '{alias.name}' detected in {file_path.name}:L{node.lineno}"
                    )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert mod not in banned_modules, (
                    f"Anti-Spoof Violation: Prohibited from-import '{mod}' detected in {file_path.name}:L{node.lineno}"
                )
                for alias in node.names:
                    assert alias.name not in banned_names, (
                        f"Anti-Spoof Violation: Prohibited name '{alias.name}' imported from '{mod}' in {file_path.name}:L{node.lineno}"
                    )


# ---------------------------------------------------------------------------
# 10. Air-Gap & File Hygiene Verification
# ---------------------------------------------------------------------------

def test_airgap_and_file_hygiene() -> None:
    """Verify strict UTF-8 LF encoding, zero BOM, and zero hardcoded path leaks."""
    target_files = [
        Path(TOPOS_REPO_ROOT) / "mechanics" / "cochem_topos_quench.py",
        Path(BASE_REPO_ROOT) / "cochem_base" / "interfaces" / "cochem_topos_quench.py",
        Path(BASE_REPO_ROOT) / "cochem_base" / "mechanics" / "cochem_topos_quench.py",
        Path(__file__).resolve(),
    ]

    for p in target_files:
        if not p.exists():
            continue
        raw_bytes = p.read_bytes()
        # Assert Zero BOM
        assert not raw_bytes.startswith(b"\xef\xbb\xbf"), f"BOM detected in {p.name}"

        # Assert Unix LF newlines
        assert b"\r\n" not in raw_bytes, f"CRLF detected in {p.name}; must use Unix LF."

        # Assert no hardcoded absolute user home paths
        text = raw_bytes.decode("utf-8")
        assert "C:\\Users\\" not in text or "CoChem_Artifacts" in text, (
            f"Hardcoded path leak in {p.name}"
        )
