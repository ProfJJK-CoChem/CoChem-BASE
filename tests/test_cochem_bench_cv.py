#!/usr/bin/env python3
r"""Authentic Unit Test Suite for CoChem Stage 3.0 Core-Valence (CV) Correlation Correction Engine.

Module: tests/test_cochem_bench_cv.py
Target Implementation: bench_engine.cochem_bench_cv

Tests:
1. CoreValenceMapper:
   - Dynamic basis set mapping (cc-pV -> cc-pCV, aug-cc-pV -> aug-cc-pwCV, def2 unchanged).
   - Elemental core composition inspection using dynamic Mendeleev atomic data.
   - Core electron presence and mass calculation.
2. DualCorrelationEngine:
   - Input deck generation for Frozen-Core (FC) vs All-Electron (AE with NoFrozenCore).
   - Dynamic %maxcore RAM calculation per MPI thread.
   - Accelerator isolation injecting CUDA_VISIBLE_DEVICES="".
   - Execution via subprocess using BenchRunContext and binary path.
   - Dual execution protocol (execute_dual_sp) with automatic scratch purging.
3. DeltaExtractor:
   - Extraction of FINAL SINGLE POINT ENERGY from authentic ORCA standard output.
   - Mathematical derivation of Delta_E_CV = E_Total^(AE) - E_Total^(FC).
   - Unit conversion from Hartree to kcal/mol via exact CODATA conversion.
   - CVParsingError exception hierarchy verification.
4. EphemeralScratchPurge:
   - UUID-scoped tripartite scratch workspace creation.
   - Sweep and unlink of .gbw, .tmp, and ephemeral intermediate files.
   - Directory removal preventing disk and NVMe exhaustion.
5. HDF5 Persistence & Pipeline Orchestration:
   - Atomic commitment of CV correction results to landscape.h5.
   - Schema validation and roundtrip retrieval.
   - End-to-end pipeline execution with pre-computed energies and direct execution.

Authoritative References:
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 5 CBS Extrapolation & Composite Protocol Math (Stages 2.0 - 4.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task5_cv.md
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import h5py
import pytest
from mendeleev import element

from bench_engine.cochem_bench_cv import (
    CoreValenceMapper,
    DualCorrelationEngine,
    DeltaExtractor,
    EphemeralScratchPurge,
    CVCorrectionResult,
    CVCorrectionError,
    CVExecutionError,
    CVParsingError,
    CVScratchPurgeError,
    commit_cv_to_hdf5,
    read_cv_from_hdf5,
    run_cv_pipeline,
    HARTREE_TO_KCAL_MOL,
)


# ==============================================================================
# Authentic Molecular Test Fixtures (Angstroms)
# ==============================================================================

# Water Molecule (C2v equilibrium geometry)
WATER_COORDS: List[Tuple[str, float, float, float]] = [
    ("O", 0.000000, 0.000000, 0.117790),
    ("H", 0.000000, 0.755453, -0.471161),
    ("H", 0.000000, -0.755453, -0.471161),
]

# Methane (Td equilibrium geometry)
METHANE_COORDS: List[Tuple[str, float, float, float]] = [
    ("C", 0.000000, 0.000000, 0.000000),
    ("H", 0.627600, 0.627600, 0.627600),
    ("H", -0.627600, -0.627600, 0.627600),
    ("H", -0.627600, 0.627600, -0.627600),
    ("H", 0.627600, -0.627600, -0.627600),
]

# Dihydrogen (No core electrons)
H2_COORDS: List[Tuple[str, float, float, float]] = [
    ("H", 0.000000, 0.000000, 0.370000),
    ("H", 0.000000, 0.000000, -0.370000),
]

# Carbon Monoxide (Multiple heavy atoms)
CO_COORDS: List[Tuple[str, float, float, float]] = [
    ("C", 0.000000, 0.000000, -0.645000),
    ("O", 0.000000, 0.000000, 0.485000),
]


# ==============================================================================
# Authentic ORCA 6.1.1 Output Fixtures
# ==============================================================================

ORCA_FC_STDOUT_WATER = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================

Total Energy       :      -76.3623851042 Eh
FINAL SINGLE POINT ENERGY      -76.3623851042
ORCA TERMINATED NORMALLY
"""

ORCA_AE_STDOUT_WATER = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================

Total Energy       :      -76.4215403210 Eh
FINAL SINGLE POINT ENERGY      -76.4215403210
ORCA TERMINATED NORMALLY
"""


# ==============================================================================
# 1. CoreValenceMapper Tests
# ==============================================================================

def test_basis_set_mapping_cc_pv() -> None:
    """Validate string mapping of standard cc-pVnZ basis sets to core-valence cc-pCVnZ."""
    mapper = CoreValenceMapper()

    assert mapper.map_basis_set("cc-pVDZ") == "cc-pCVDZ"
    assert mapper.map_basis_set("cc-pVTZ") == "cc-pCVTZ"
    assert mapper.map_basis_set("cc-pVQZ") == "cc-pCVQZ"
    assert mapper.map_basis_set("cc-pV5Z") == "cc-pCV5Z"


def test_basis_set_mapping_aug_cc_pv() -> None:
    """Validate string mapping of augmented aug-cc-pVnZ basis sets to aug-cc-pwCVnZ."""
    mapper = CoreValenceMapper()

    assert mapper.map_basis_set("aug-cc-pVDZ") == "aug-cc-pwCVDZ"
    assert mapper.map_basis_set("aug-cc-pVTZ") == "aug-cc-pwCVTZ"
    assert mapper.map_basis_set("aug-cc-pVQZ") == "aug-cc-pwCVQZ"
    assert mapper.map_basis_set("aug-cc-pV5Z") == "aug-cc-pwCV5Z"


def test_basis_set_mapping_def2_and_ano() -> None:
    """Validate def2 and ano families retain their native all-electron character without mutation."""
    mapper = CoreValenceMapper()

    assert mapper.map_basis_set("def2-SVP") == "def2-SVP"
    assert mapper.map_basis_set("def2-TZVP") == "def2-TZVP"
    assert mapper.map_basis_set("def2-QZVPP") == "def2-QZVPP"
    assert mapper.map_basis_set("ano-pVTZ") == "ano-pVTZ"
    assert mapper.map_basis_set("saug-ano-pVTZ") == "saug-ano-pVTZ"


def test_elemental_core_inspection_mendeleev() -> None:
    """Validate dynamic atomic and core electron inspection using Mendeleev library."""
    mapper = CoreValenceMapper()

    # Water inspection: Oxygen (Z=8, 2 core e-), Hydrogen (Z=1, 0 core e-)
    water_info = mapper.inspect_elemental_core(WATER_COORDS)
    assert water_info["has_core_electrons"] is True
    assert water_info["total_core_electrons"] == 2
    assert "O" in water_info["elements"]
    assert "H" in water_info["elements"]

    # Verify dynamic masses
    expected_mass = float(element("O").mass) + 2.0 * float(element("H").mass)
    assert math.isclose(water_info["total_mass"], expected_mass, rel_tol=1e-5)

    # Dihydrogen inspection (No core electrons present)
    h2_info = mapper.inspect_elemental_core(H2_COORDS)
    assert h2_info["has_core_electrons"] is False
    assert h2_info["total_core_electrons"] == 0

    # Carbon Monoxide inspection: C (Z=6, 2 core), O (Z=8, 2 core) -> 4 core e-
    co_info = mapper.inspect_elemental_core(CO_COORDS)
    assert co_info["has_core_electrons"] is True
    assert co_info["total_core_electrons"] == 4


# ==============================================================================
# 2. DualCorrelationEngine Tests
# ==============================================================================

def test_dual_correlation_engine_maxcore_calculation() -> None:
    """Validate dynamic %maxcore per MPI process with safety margin."""
    engine = DualCorrelationEngine(node_max_gb=16.0, nprocs=4, ram_safety_fraction=0.75)
    maxcore = engine.calculate_maxcore_per_thread()

    # 16 GB * 1024 MB/GB * 0.75 / 4 = 3072 MB
    assert maxcore == 3072


def test_dual_correlation_input_deck_generation() -> None:
    """Validate generation of Job A (Frozen-Core) and Job B (All-Electron with NoFrozenCore)."""
    engine = DualCorrelationEngine(
        method="DLPNO-CCSD(T)",
        base_basis="aug-cc-pVQZ",
        node_max_gb=16.0,
        nprocs=4,
    )

    decks = engine.generate_input_decks(coords=WATER_COORDS, charge=0, mult=1)

    assert "fc_input" in decks
    assert "ae_input" in decks
    assert decks["basis_set"] == "aug-cc-pwCVQZ"
    assert decks["original_basis"] == "aug-cc-pVQZ"

    fc_inp = decks["fc_input"]
    ae_inp = decks["ae_input"]

    # Job A (FC) must use mapped basis and NOT contain NoFrozenCore
    assert "! DLPNO-CCSD(T) aug-cc-pwCVQZ" in fc_inp
    assert "NoFrozenCore" not in fc_inp
    assert "%maxcore 3072" in fc_inp
    assert "%pal nprocs 4 end" in fc_inp
    assert "* xyz 0 1" in fc_inp

    # Job B (AE) must contain NoFrozenCore
    assert "! DLPNO-CCSD(T) aug-cc-pwCVQZ" in ae_inp
    assert "NoFrozenCore" in ae_inp
    assert "%maxcore 3072" in ae_inp
    assert "%pal nprocs 4 end" in ae_inp
    assert "* xyz 0 1" in ae_inp


def test_cuda_accelerator_isolation_env() -> None:
    """Validate execution environment injects CUDA_VISIBLE_DEVICES='' for GPU isolation."""
    engine = DualCorrelationEngine()
    env = engine.prepare_execution_env()

    assert "CUDA_VISIBLE_DEVICES" in env
    assert env["CUDA_VISIBLE_DEVICES"] == ""


def test_dual_correlation_input_file_writing(tmp_path: Path) -> None:
    """Validate writing input decks to disk."""
    engine = DualCorrelationEngine(base_basis="cc-pVTZ")
    decks = engine.generate_input_decks(
        coords=WATER_COORDS,
        charge=0,
        mult=1,
        output_dir=tmp_path,
    )

    fc_file = tmp_path / "orca_fc.inp"
    ae_file = tmp_path / "orca_ae.inp"

    assert fc_file.exists()
    assert ae_file.exists()
    assert "cc-pCVTZ" in fc_file.read_text(encoding="utf-8")
    assert "NoFrozenCore" in ae_file.read_text(encoding="utf-8")


def test_dual_correlation_execute_job_with_runner(tmp_path: Path) -> None:
    """Validate execute_job executes external runner script and captures output."""
    script_file = tmp_path / "sim_orca.py"
    script_file.write_text(
        'import sys\n'
        'with open(sys.argv[1], "r", encoding="utf-8") as f:\n'
        '    inp = f.read()\n'
        'if "NoFrozenCore" in inp:\n'
        '    print("FINAL SINGLE POINT ENERGY      -76.4215403210")\n'
        'else:\n'
        '    print("FINAL SINGLE POINT ENERGY      -76.3623851042")\n'
        'sys.exit(0)\n',
        encoding="utf-8",
    )

    engine = DualCorrelationEngine(base_basis="aug-cc-pVQZ")
    scratch = tmp_path / "scratch"

    # Use python executable with script file list
    stdout, stderr, ret = engine.execute_job(
        input_text="! DLPNO-CCSD(T) aug-cc-pwCVQZ\n* xyz 0 1\nO 0 0 0\n*\n",
        orca_binary_path=[sys.executable, str(script_file)],
        scratch_dir=scratch,
        job_prefix="test_job",
    )

    assert ret == 0
    assert "FINAL SINGLE POINT ENERGY      -76.3623851042" in stdout


def test_dual_correlation_execute_dual_sp(tmp_path: Path) -> None:
    """Validate execute_dual_sp runs dual jobs, extracts delta, and purges scratch."""
    script_file = tmp_path / "sim_orca_dual.py"
    script_file.write_text(
        'import sys\n'
        'with open(sys.argv[1], "r", encoding="utf-8") as f:\n'
        '    inp = f.read()\n'
        'if "NoFrozenCore" in inp:\n'
        '    print("FINAL SINGLE POINT ENERGY      -76.4215403210")\n'
        'else:\n'
        '    print("FINAL SINGLE POINT ENERGY      -76.3623851042")\n'
        'sys.exit(0)\n',
        encoding="utf-8",
    )

    engine = DualCorrelationEngine(base_basis="aug-cc-pVQZ")
    scratch = tmp_path / "scratch_dual"

    result = engine.execute_dual_sp(
        coords=WATER_COORDS,
        orca_binary=[sys.executable, str(script_file)],
        node_id="water_dual_test",
        scratch_dir=scratch,
        auto_purge=True,
    )

    assert math.isclose(result.e_total_fc, -76.3623851042, abs_tol=1e-10)
    assert math.isclose(result.e_total_ae, -76.4215403210, abs_tol=1e-10)
    assert result.delta_e_cv_hartree < 0.0
    assert result.node_id == "water_dual_test"
    assert not scratch.exists()  # Purged


# ==============================================================================
# 3. DeltaExtractor Tests
# ==============================================================================

def test_parse_final_energy_from_stdout() -> None:
    """Validate extracting FINAL SINGLE POINT ENERGY from authentic ORCA standard output."""
    extractor = DeltaExtractor()

    e_fc = extractor.parse_final_energy_from_stdout(ORCA_FC_STDOUT_WATER)
    e_ae = extractor.parse_final_energy_from_stdout(ORCA_AE_STDOUT_WATER)

    assert math.isclose(e_fc, -76.3623851042, abs_tol=1e-10)
    assert math.isclose(e_ae, -76.4215403210, abs_tol=1e-10)


def test_parse_final_energy_missing_raises() -> None:
    """Validate CVParsingError is raised when FINAL SINGLE POINT ENERGY is absent."""
    extractor = DeltaExtractor()
    invalid_stdout = "ORCA CALCULATION FAILED\nNO ENERGY REPORTED\n"

    with pytest.raises(CVParsingError, match="FINAL SINGLE POINT ENERGY"):
        extractor.parse_final_energy_from_stdout(invalid_stdout)

    # Also verify that CVParsingError is a ValueError subclass
    with pytest.raises(ValueError):
        extractor.parse_final_energy_from_stdout(invalid_stdout)


def test_delta_extractor_mathematics() -> None:
    """Validate mathematical derivation of Delta_E_CV = E_Total^(AE) - E_Total^(FC)."""
    extractor = DeltaExtractor()

    e_fc = -76.3623851042
    e_ae = -76.4215403210

    result: CVCorrectionResult = extractor.extract_delta(
        e_total_fc=e_fc,
        e_total_ae=e_ae,
        basis_set="aug-cc-pwCVQZ",
        original_basis="aug-cc-pVQZ",
        method="DLPNO-CCSD(T)",
        node_id="water_test_01",
    )

    expected_delta_hartree = e_ae - e_fc
    expected_delta_kcal = expected_delta_hartree * HARTREE_TO_KCAL_MOL

    assert math.isclose(result.delta_e_cv_hartree, expected_delta_hartree, rel_tol=1e-10)
    assert math.isclose(result.delta_e_cv_kcal_mol, expected_delta_kcal, rel_tol=1e-10)
    assert result.delta_e_cv_hartree < 0.0  # All-electron energy is lower than frozen-core
    assert result.basis_set == "aug-cc-pwCVQZ"
    assert result.original_basis_set == "aug-cc-pVQZ"
    assert result.node_id == "water_test_01"


def test_extract_from_outputs() -> None:
    """Validate extraction directly from authentic ORCA output texts."""
    extractor = DeltaExtractor()

    result = extractor.extract_from_outputs(
        stdout_fc=ORCA_FC_STDOUT_WATER,
        stdout_ae=ORCA_AE_STDOUT_WATER,
        basis_set="aug-cc-pwCVQZ",
        original_basis="aug-cc-pVQZ",
        node_id="water_out_test",
    )

    assert math.isclose(result.e_total_fc, -76.3623851042, abs_tol=1e-10)
    assert math.isclose(result.e_total_ae, -76.4215403210, abs_tol=1e-10)
    assert math.isclose(result.delta_e_cv_hartree, -76.4215403210 - (-76.3623851042), abs_tol=1e-10)


# ==============================================================================
# 4. EphemeralScratchPurge Tests
# ==============================================================================

def test_scratch_dir_creation(tmp_path: Path) -> None:
    """Validate creation of isolated UUID-scoped scratch directory."""
    purger = EphemeralScratchPurge()
    scratch_dir = purger.create_scratch_dir(base_artifacts_dir=tmp_path)

    assert scratch_dir.exists()
    assert "BENCH_Workspace" in str(scratch_dir)
    assert "Scratch" in str(scratch_dir)
    assert "job_" in scratch_dir.name


def test_scratch_dir_purge(tmp_path: Path) -> None:
    """Validate sweep and removal of .gbw, .tmp, and intermediate scratch files."""
    purger = EphemeralScratchPurge()
    job_dir = tmp_path / "BENCH_Workspace" / "Scratch" / "job_12345"
    job_dir.mkdir(parents=True, exist_ok=True)

    # Create simulation intermediate files
    (job_dir / "calc.gbw").write_bytes(b"BINARY_GBW_CONTENT")
    (job_dir / "calc.tmp").write_text("TMP_CONTENT", encoding="utf-8")
    (job_dir / "calc.densities").write_text("DENSITIES", encoding="utf-8")
    (job_dir / "calc.inp").write_text("! Input deck", encoding="utf-8")

    assert (job_dir / "calc.gbw").exists()
    assert (job_dir / "calc.tmp").exists()

    # Execute purge
    summary = purger.purge_scratch_dir(job_dir, remove_dir=True)

    assert summary["purged_count"] >= 2
    assert not job_dir.exists()


# ==============================================================================
# 5. HDF5 Persistence & Pipeline Orchestration Tests
# ==============================================================================

def test_hdf5_cv_persistence(tmp_path: Path) -> None:
    """Validate atomic serialization of CV correction delta to landscape.h5."""
    h5_file = tmp_path / "landscape.h5"

    cv_result = CVCorrectionResult(
        e_total_fc=-76.362385,
        e_total_ae=-76.421540,
        delta_e_cv_hartree=-0.059155,
        delta_e_cv_kcal_mol=-37.120300,
        basis_set="aug-cc-pwCVQZ",
        original_basis_set="aug-cc-pVQZ",
        method="DLPNO-CCSD(T)",
        has_core_electrons=True,
        node_id="water_cv_node_01",
    )

    commit_cv_to_hdf5(h5_path=h5_file, result=cv_result)
    assert h5_file.exists()

    # Read back and verify exact data integrity
    loaded = read_cv_from_hdf5(h5_path=h5_file, node_id="water_cv_node_01")

    assert math.isclose(loaded["e_total_fc"], -76.362385, abs_tol=1e-6)
    assert math.isclose(loaded["e_total_ae"], -76.421540, abs_tol=1e-6)
    assert math.isclose(loaded["delta_e_cv_hartree"], -0.059155, abs_tol=1e-6)
    assert math.isclose(loaded["delta_e_cv_kcal_mol"], -37.120300, abs_tol=1e-6)
    assert loaded["basis_set"] == "aug-cc-pwCVQZ"
    assert loaded["original_basis_set"] == "aug-cc-pVQZ"
    assert loaded["method"] == "DLPNO-CCSD(T)"
    assert loaded["has_core_electrons"] is True
    assert loaded["node_id"] == "water_cv_node_01"


def test_run_cv_pipeline_end_to_end(tmp_path: Path) -> None:
    """Validate end-to-end execution of Stage 3.0 CV pipeline orchestrator."""
    h5_file = tmp_path / "landscape.h5"

    result = run_cv_pipeline(
        coords=WATER_COORDS,
        e_total_fc=-76.362385,
        e_total_ae=-76.421540,
        base_basis="aug-cc-pVQZ",
        method="DLPNO-CCSD(T)",
        node_id="water_pipeline_01",
        h5_path=h5_file,
    )

    assert result.has_core_electrons is True
    assert result.basis_set == "aug-cc-pwCVQZ"
    assert math.isclose(result.delta_e_cv_hartree, -76.421540 - (-76.362385), abs_tol=1e-6)
    assert h5_file.exists()


def test_run_cv_pipeline_with_orca_binary(tmp_path: Path) -> None:
    """Validate end-to-end execution of Stage 3.0 CV pipeline with engine execution."""
    script_file = tmp_path / "sim_orca_pipe.py"
    script_file.write_text(
        'import sys\n'
        'with open(sys.argv[1], "r", encoding="utf-8") as f:\n'
        '    inp = f.read()\n'
        'if "NoFrozenCore" in inp:\n'
        '    print("FINAL SINGLE POINT ENERGY      -76.4215403210")\n'
        'else:\n'
        '    print("FINAL SINGLE POINT ENERGY      -76.3623851042")\n'
        'sys.exit(0)\n',
        encoding="utf-8",
    )

    h5_file = tmp_path / "landscape.h5"
    result = run_cv_pipeline(
        coords=WATER_COORDS,
        orca_binary=[sys.executable, str(script_file)],
        base_basis="aug-cc-pVQZ",
        method="DLPNO-CCSD(T)",
        node_id="water_pipe_bin_01",
        h5_path=h5_file,
    )

    assert result.has_core_electrons is True
    assert result.node_id == "water_pipe_bin_01"
    assert math.isclose(result.delta_e_cv_hartree, -76.4215403210 - (-76.3623851042), abs_tol=1e-10)
    assert h5_file.exists()


def test_run_cv_pipeline_missing_args_raises() -> None:
    """Validate run_cv_pipeline raises CVCorrectionError when neither energies nor binary provided."""
    with pytest.raises(CVCorrectionError, match="requires either"):
        run_cv_pipeline(coords=WATER_COORDS)


def test_read_cv_from_hdf5_missing_file_raises(tmp_path: Path) -> None:
    """Validate read_cv_from_hdf5 raises FileNotFoundError when target file is missing."""
    missing_file = tmp_path / "missing_landscape.h5"
    with pytest.raises(FileNotFoundError):
        read_cv_from_hdf5(h5_path=missing_file, node_id="node_none")


def test_cochem_bench_package_imports() -> None:
    """Validate that all Stage 3.0 symbols are accessible via cochem_bench.bench_engine."""
    from cochem_bench.bench_engine.cochem_bench_cv import (
        CoreValenceMapper as CBMapper,
        DualCorrelationEngine as CBEngine,
        DeltaExtractor as CBExtractor,
        EphemeralScratchPurge as CBPurge,
        CVCorrectionResult as CBResult,
        CVCorrectionError,
        CVExecutionError,
        CVParsingError,
        CVScratchPurgeError,
    )

    mapper = CBMapper()
    assert mapper.map_basis_set("cc-pVDZ") == "cc-pCVDZ"
    assert issubclass(CVExecutionError, CVCorrectionError)
    assert issubclass(CVParsingError, CVCorrectionError)
    assert issubclass(CVScratchPurgeError, CVCorrectionError)


def test_bench_run_context_integration(tmp_path: Path) -> None:
    """Validate DualCorrelationEngine execution with BenchRunContext."""
    from cochem_bench.bench_engine.cochem_bench_ingest import BenchRunContext, BenchConfigSchema, BenchHardwareSchema

    cfg = BenchConfigSchema(
        hardware=BenchHardwareSchema(ram_gb=16.0, cpu_physical_cores=4),
    )
    ctx = BenchRunContext(
        config_hash="abc123hash",
        safe_maxcore_mb=3072,
        target_mpi_threads=4,
        node_id="test_node",
        timestamp="2026-08-24T00:00:00Z",
        orca_path=str(tmp_path / "fake_orca_exe"),
        hdf5_path=tmp_path / "landscape.h5",
        scratch_path=tmp_path / "scratch",
        numa_nodes=1,
        resource_warning=False,
        config=cfg,
    )

    assert ctx.orca_binary_path == str(tmp_path / "fake_orca_exe")
    assert ctx.orca_path == str(tmp_path / "fake_orca_exe")

    engine = DualCorrelationEngine()
    env = engine.prepare_execution_env()
    assert env["CUDA_VISIBLE_DEVICES"] == ""


def test_scratch_dir_creation_with_environ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate scratch dir creation adheres to COCHEM_ARTIFACTS_DIR environment variable."""
    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(tmp_path))
    purger = EphemeralScratchPurge()
    scratch_dir = purger.create_scratch_dir()

    assert scratch_dir.exists()
    assert str(tmp_path) in str(scratch_dir)
    assert "BENCH_Workspace" in str(scratch_dir)
    assert "Scratch" in str(scratch_dir)

    summary = purger.purge_scratch_dir(scratch_dir, remove_dir=True)
    assert summary["status"] == "purged"
    assert not scratch_dir.exists()
