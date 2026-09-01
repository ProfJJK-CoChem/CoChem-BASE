"""# zero-stub anti-spoofing engine
Unit tests for orchestrator.cochem_gpu_crossover_bench adhering to Method Matrix v4 §8.3, §8.4, §8A.4, and §20.1.
"""

import json
import math
import tempfile
from pathlib import Path
from typing import List

import numpy as np
import pytest

from orchestrator.cochem_gpu_crossover_bench import (
    BenchmarkSystem,
    BenchmarkTask,
    ComparisonMode,
    EmpiricalCrossoverModel,
    ExecutionEngine,
    FullBenchmarkReport,
    HardwareTelemetry,
    SingleRunResult,
    SystemCrossoverEvaluation,
    build_cli_parser,
    calculate_basis_function_count,
    compute_inertial_tensor_and_constants,
    evaluate_crossover_pair,
    fit_empirical_crossover_surface,
    generate_markdown_report,
    get_dynamic_atomic_mass,
    get_standard_benchmark_systems,
    interrogate_hardware,
    main as crossover_bench_main,
    run_analytical_physics_point,
    run_crossover_benchmark_suite,
    save_calibration_artifacts,
)


def test_mendeleev_dynamic_mass_retrieval():
    """Verify live Mendeleev dynamic mass retrieval adhering to Mendeleev Mass Mandate."""
    # Hydrogen
    h_mass = get_dynamic_atomic_mass("H")
    assert abs(h_mass - 1.008) < 0.01

    # Carbon
    c_mass = get_dynamic_atomic_mass("C")
    assert abs(c_mass - 12.011) < 0.01

    # Oxygen
    o_mass = get_dynamic_atomic_mass("O")
    assert abs(o_mass - 15.999) < 0.01

    # Nitrogen
    n_mass = get_dynamic_atomic_mass("N")
    assert abs(n_mass - 14.007) < 0.01

    # Ensure all return strictly positive values
    for sym in ["H", "C", "N", "O", "F", "P", "S", "Cl"]:
        assert get_dynamic_atomic_mass(sym) > 0.0


def test_inertia_tensor_and_rotational_constants():
    """Verify center-of-mass shifted inertia tensor and rotational constants computation."""
    # Water monomer geometry (Angstrom)
    symbols = ["O", "H", "H"]
    coords = [
        [0.0000, 0.0000, 0.1173],
        [0.0000, 0.7572, -0.4692],
        [0.0000, -0.7572, -0.4692],
    ]
    tensor, (rot_a, rot_b, rot_c) = compute_inertial_tensor_and_constants(symbols, np.array(coords))

    assert tensor.shape == (3, 3)
    assert np.all(np.isfinite(tensor))
    # Rotational constants ordering A >= B >= C
    assert rot_a >= rot_b >= rot_c > 0.0
    # For H2O, A ~ 830-840 GHz (830000-840000 MHz), B ~ 430 GHz, C ~ 280 GHz
    assert rot_a > 100000.0
    assert rot_b > 50000.0
    assert rot_c > 30000.0


def test_standard_benchmark_systems():
    """Verify built-in suite of benchmark systems across the crossover spectrum."""
    systems = get_standard_benchmark_systems()
    assert len(systems) >= 9

    expected_keys = [
        "water_dimer",
        "water_trimer",
        "water_tetramer",
        "water_pentamer",
        "water_decamer",
        "caffeine",
        "formamidinium_formate",
        "ammonia_formic_acid",
        "vitamin_c",
    ]
    for k in expected_keys:
        assert k in systems
        sys_obj = systems[k]
        assert isinstance(sys_obj, BenchmarkSystem)
        assert len(sys_obj.symbols) == len(sys_obj.coordinates_angstrom)
        assert len(sys_obj.symbols) > 0
        for coord in sys_obj.coordinates_angstrom:
            assert len(coord) == 3


def test_calculate_basis_function_count():
    """Verify basis function counting logic across different basis sets."""
    water_symbols = ["O", "H", "H"]
    # def2-SVP: 14 for O + 2*5 for H = 24 bf
    n_svp = calculate_basis_function_count(water_symbols, "def2-svp")
    assert n_svp == 24

    # def2-TZVPP: 31 for O + 2*14 for H = 59 bf
    n_tzvpp = calculate_basis_function_count(water_symbols, "def2-tzvpp")
    assert n_tzvpp == 59

    # Water dimer in def2-TZVPP: 2 * 59 = 118 bf (Method Matrix §8.3 anchor)
    water_dimer_symbols = ["O", "H", "H", "O", "H", "H"]
    n_dimer_tzvpp = calculate_basis_function_count(water_dimer_symbols, "def2-tzvpp")
    assert n_dimer_tzvpp == 118


def test_interrogate_hardware():
    """Verify host hardware telemetry interrogation."""
    hw = interrogate_hardware()
    assert isinstance(hw, HardwareTelemetry)
    assert hw.physical_cores >= 1
    assert hw.logical_threads >= hw.physical_cores
    assert hw.total_ram_gb > 0.0
    assert isinstance(hw.has_cuda, bool)
    assert isinstance(hw.has_mps, bool)


def test_analytical_physics_point():
    """Verify analytical physics execution engine for CPU and GPU models."""
    systems = get_standard_benchmark_systems()
    sys_obj = systems["water_dimer"]

    # CPU point
    cpu_run = run_analytical_physics_point(
        system=sys_obj, task=BenchmarkTask.ENERGY, mode=ComparisonMode.MATCHED, is_gpu=False
    )
    assert isinstance(cpu_run, SingleRunResult)
    assert cpu_run.engine == ExecutionEngine.PYSCF_CPU
    assert cpu_run.basis_function_count == 118
    assert np.isfinite(cpu_run.energy_hartree)
    assert cpu_run.scf_wall_seconds > 0.0
    assert cpu_run.converged is True

    # GPU point
    gpu_run = run_analytical_physics_point(
        system=sys_obj, task=BenchmarkTask.ENERGY, mode=ComparisonMode.MATCHED, is_gpu=True
    )
    assert isinstance(gpu_run, SingleRunResult)
    assert gpu_run.engine == ExecutionEngine.GPU4PYSCF
    assert gpu_run.basis_function_count == 118
    assert np.isfinite(gpu_run.energy_hartree)
    assert gpu_run.scf_wall_seconds > 0.0
    assert gpu_run.converged is True


def test_evaluate_crossover_pair():
    """Verify pair evaluation between CPU and GPU with acceptance gate verification."""
    systems = get_standard_benchmark_systems()
    sys_obj = systems["water_dimer"]

    cpu_res, gpu_res, eval_res = evaluate_crossover_pair(
        system=sys_obj,
        task=BenchmarkTask.ENERGY,
        mode=ComparisonMode.MATCHED,
        allow_analytical_fallback=True,
    )
    assert isinstance(eval_res, SystemCrossoverEvaluation)
    assert eval_res.system_id == "water_dimer"
    assert eval_res.basis_function_count == 118
    assert eval_res.speedup_ratio > 0.0
    assert eval_res.energy_delta_mha < 1.0
    assert eval_res.passes_accuracy_gate is True
    assert eval_res.crossover_classification in ("GPU_FASTER", "CPU_FASTER", "PARITY")


def test_fit_empirical_crossover_surface():
    """Verify empirical log-linear crossover surface regression."""
    # Create sample evaluations across 3 systems
    evals = [
        SystemCrossoverEvaluation(
            system_id="sys_50",
            system_name="System 50",
            basis_function_count=50,
            task=BenchmarkTask.ENERGY,
            mode=ComparisonMode.MATCHED,
            xc="b3lyp",
            basis="def2-tzvpp",
            cpu_engine=ExecutionEngine.PYSCF_CPU,
            gpu_engine=ExecutionEngine.GPU4PYSCF,
            cpu_scf_wall_seconds=0.05,
            gpu_scf_wall_seconds=0.07,
            speedup_ratio=0.714,
            energy_delta_hartree=0.0,
            energy_delta_mha=0.0,
            passes_accuracy_gate=True,
            crossover_classification="CPU_FASTER",
        ),
        SystemCrossoverEvaluation(
            system_id="sys_100",
            system_name="System 100",
            basis_function_count=100,
            task=BenchmarkTask.ENERGY,
            mode=ComparisonMode.MATCHED,
            xc="b3lyp",
            basis="def2-tzvpp",
            cpu_engine=ExecutionEngine.PYSCF_CPU,
            gpu_engine=ExecutionEngine.GPU4PYSCF,
            cpu_scf_wall_seconds=0.20,
            gpu_scf_wall_seconds=0.10,
            speedup_ratio=2.00,
            energy_delta_hartree=0.0,
            energy_delta_mha=0.0,
            passes_accuracy_gate=True,
            crossover_classification="GPU_FASTER",
        ),
        SystemCrossoverEvaluation(
            system_id="sys_200",
            system_name="System 200",
            basis_function_count=200,
            task=BenchmarkTask.ENERGY,
            mode=ComparisonMode.MATCHED,
            xc="b3lyp",
            basis="def2-tzvpp",
            cpu_engine=ExecutionEngine.PYSCF_CPU,
            gpu_engine=ExecutionEngine.GPU4PYSCF,
            cpu_scf_wall_seconds=0.80,
            gpu_scf_wall_seconds=0.16,
            speedup_ratio=5.00,
            energy_delta_hartree=0.0,
            energy_delta_mha=0.0,
            passes_accuracy_gate=True,
            crossover_classification="GPU_FASTER",
        ),
    ]

    model = fit_empirical_crossover_surface(evals, task=BenchmarkTask.ENERGY, mode=ComparisonMode.MATCHED)
    assert isinstance(model, EmpiricalCrossoverModel)
    assert model.points_measured_count == 3
    assert 50.0 <= model.calibrated_crossover_basis_functions <= 90.0
    assert model.recommended_routing_threshold >= 50
    assert model.r_squared > 0.90
    assert model.provenance_tag == "[M]"


def test_run_crossover_benchmark_suite_and_artifacts():
    """Verify master suite runner and artifact persistence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        json_out = tmp_path / "bench_results.json"
        md_out = tmp_path / "bench_report.md"
        calib_out = tmp_path / "crossover_calib.json"

        report = run_crossover_benchmark_suite(
            system_ids=["water_dimer", "water_trimer"],
            tasks=[BenchmarkTask.ENERGY],
            modes=[ComparisonMode.MATCHED],
            allow_analytical_fallback=True,
        )

        assert isinstance(report, FullBenchmarkReport)
        assert len(report.runs) == 4  # 2 systems * 2 engines (CPU + GPU)
        assert len(report.evaluations) == 2
        assert report.crossover_model is not None
        assert "# CoChem CPU vs GPU Crossover Benchmark Report" in report.summary_markdown

        j_path, m_path, c_path = save_calibration_artifacts(
            report=report,
            output_json_path=json_out,
            output_md_path=md_out,
            calibration_registry_path=calib_out,
        )

        assert j_path.exists()
        assert m_path.exists()
        assert c_path.exists()

        # Validate JSON content
        j_data = json.loads(j_path.read_text(encoding="utf-8"))
        assert "hardware" in j_data
        assert "evaluations" in j_data
        assert len(j_data["evaluations"]) == 2

        # Validate Section 20.1 Calibration registry
        c_data = json.loads(c_path.read_text(encoding="utf-8"))
        assert "calibrated_crossover_basis_threshold" in c_data
        assert "routing_policy_update" in c_data
        assert c_data["routing_policy_update"]["gpu_crossover_basis_threshold"] > 0


def test_cli_parser():
    """Verify command line parser structure."""
    parser = build_cli_parser()
    args = parser.parse_args(["--systems", "water_dimer,water_trimer", "--tasks", "energy", "--modes", "matched"])
    assert args.systems == "water_dimer,water_trimer"
    assert args.tasks == "energy"
    assert args.modes == "matched"
    assert args.cores == 8
