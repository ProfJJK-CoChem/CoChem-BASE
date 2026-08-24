Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-GEOM\.in-progress\Task_13_eval_metrics_py.md.
Original prompt:
# Task: Create `src/cochem_geom/eval/metrics.py`

## Context
You are an autonomous execution agent coding the new version of CoChem-GEOM based on the approved System Architecture.
Target output directory: `D:\__CoChem\GitHub-Repo\CoChem-GEOM`

## Strict Execution Constraints
1. **Scope:** Generate exactly one coding script file for this prompt (`src/cochem_geom/eval/metrics.py`).
2. **Path:** Output the generated file to the target output directory at `D:\__CoChem\GitHub-Repo\CoChem-GEOM\src/cochem_geom/eval/metrics.py`. Do not execute or run the code, only generate the file.
3. **Geometric Equivariance & Invariance:** The system must strictly separate non-spatial node features from spatial coordinates.
4. **State Immutability:** Geometric transformations are immutable (`data.pos = data.pos + update`, never `data.pos += update`).
5. **No Hardcoded Paths:** Use dynamic lookups (`pathlib.Path.home()`, environment variables).
6. **Provenance Tags:** You MUST tag all qualitative values, bounds, energy metrics, and hardware speedups with explicit provenance tags (`[M]` for Measured, `[D]` for Derived, `[E]` for Expert Estimate).

## File Specific Instructions
TorchMetrics implementations for Conformer Coverage (COV) `[D]`, Average Minimum RMSD (AMR) `[D]`, and Energy MAE `[D]`. Track domain-specific structural metrics.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\harvesters\test_scribe_payload_builder.py ---
#!/usr/bin/env python3
"""Unit Tests for CoChem-SCRIBE Context-Safe Payload Builder & Prompt Synthesizer.

Phase 2, Task 6: Context-Safe Payload Builder & Prompt Synthesis
(harvesters/test_scribe_payload_builder.py).

Adheres strictly to the Anti-Spoofing Protocol.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import os
import tempfile
import pytest
import tiktoken

try:
    from .scribe_payload_builder import (
        DEFAULT_TOKEN_LIMIT,
        PayloadBuilder,
    )
except ImportError:
    from harvesters.scribe_payload_builder import (
        DEFAULT_TOKEN_LIMIT,
        PayloadBuilder,
    )

DRY_RUN_MAX_DURATION: float = 0.05
MAX_ALLOWED_CONFS: int = 3
MAX_ALLOWED_CRITICAL_WARNINGS: int = 2
EXPECTED_INVARIANT_GIBBS: float = -182.1250
EXPECTED_INVARIANT_ZPE: float = 48.9125


@pytest.fixture(autouse=True)
def configure_airgap_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Configures tiktoken to operate strictly with offline local cache."""
    cache_dir = os.environ.get("TIKTOKEN_CACHE_DIR")
    if not cache_dir:
        default_cache = Path(tempfile.gettempdir()) / "data-gym-cache"
        if default_cache.exists():
            cache_dir = str(default_cache)
        else:
            cache_dir = str(tmp_path / "tiktoken_cache")
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", cache_dir)


@pytest.fixture
def authentic_aggregated_data() -> dict[str, Any]:
    """Provides a realistic, authentic aggregated quantum chemistry dataset."""
    return {
        "conformers": [
            {
                "conformer_id": "conf_01",
                "relative_energy_kcal_mol": 0.000,
                "point_group_symmetry": "C2v",
                "dipole_moment_debye": 1.854,
            },
            {
                "conformer_id": "conf_02",
                "relative_energy_kcal_mol": 0.742,
                "point_group_symmetry": "Cs",
                "dipole_moment_debye": 2.110,
            },
            {
                "conformer_id": "conf_03",
                "relative_energy_kcal_mol": 1.385,
                "point_group_symmetry": "C1",
                "dipole_moment_debye": 0.940,
            },
            {
                "conformer_id": "conf_04",
                "relative_energy_kcal_mol": 2.450,
                "point_group_symmetry": "C1",
                "dipole_moment_debye": 1.450,
            },
        ],
        "spectroscopy": {
            "rotational_constants": {
                "A": 10342.15,
                "B": 2451.80,
                "C": 1980.45,
            },
            "dipole_moments": {
                "mu_a": 1.54,
                "mu_b": 0.98,
                "mu_c": 0.00,
                "total": 1.83,
            },
            "centrifugal_distortion": {
                "Delta_J": 0.00142,
                "Delta_JK": -0.00512,
                "Delta_K": 0.02341,
                "delta_J": 0.00031,
                "delta_K": 0.00115,
            },
        },
        "thermodynamics": {
            "zpe_kcal_mol": 45.6782,
            "enthalpy_kcal_mol": -153.2104,
            "gibbs_free_energy_kcal_mol": -154.8912,
            "vpt2_frequencies_cm1": [
                125.4,
                210.8,
                345.2,
                512.6,
                780.1,
                1024.5,
                1250.0,
                1480.2,
                1650.4,
                2980.1,
                3100.5,
                3650.0,
            ],
        },
        "telemetry": {
            "wall_clock_time_seconds": 142.85,
            "peak_gpu_vram_mb": 2450.0,
            "lam_active": False,
            "warnings": [
                "Info: Geometry optimization converged in 14 cycles.",
                "Warning: Low barrier detected along dihedral C1-C2-O3-H4.",
            ],
        },
        "provenance": {
            "engine_versions": {
                "orca": "6.1.1",
                "mace": "0.2.0",
                "xtb": "6.7.1",
                "pyscf": "2.8.0",
            },
            "config_sha256": ("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        },
    }


@pytest.fixture
def maximal_oversized_payload() -> dict[str, Any]:
    """Generates a maximal statistical data payload exceeding ~15,000 tokens."""
    conformers: list[dict[str, Any]] = []
    for i in range(25):
        conformers.append(
            {
                "conformer_id": f"conf_{i + 1:02d}",
                "relative_energy_kcal_mol": float(i * 0.45),
                "point_group_symmetry": "C1" if i > 0 else "C2v",
                "dipole_moment_debye": 1.5 + (i * 0.05),
                "cartesian_coordinates_angstrom": [
                    [float(j * 0.1), float(j * 0.2), float(j * 0.3)] for j in range(30)
                ],
                "rotational_constants_mhz": {
                    "A": 9000.0 - (i * 50),
                    "B": 2500.0 - (i * 20),
                    "C": 1800.0 - (i * 10),
                },
                "internal_coordinate_scan_degrees": [float(deg) for deg in range(0, 360, 5)],
            }
        )

    frequencies = [float(100.0 + k * 1.5) for k in range(3000)]

    warnings = [
        (
            f"Notice: Conformer exploratory step {k} generated "
            "extensive Hessian matrix gradients with potential oscillations."
        )
        for k in range(500)
    ]
    warnings.append("Critical: Memory pressure exceeded 90% threshold during Hessian inversion.")
    warnings.append("Fatal: Node 4 GPU memory bus dropped during parallel batch step.")

    return {
        "conformers": conformers,
        "spectroscopy": {
            "rotational_constants": {
                "A": 8940.12,
                "B": 2410.50,
                "C": 1780.30,
            },
            "dipole_moments": {
                "mu_a": 1.45,
                "mu_b": 0.85,
                "mu_c": 0.12,
                "total": 1.68,
            },
            "centrifugal_distortion": {
                "Delta_J": 0.0012,
                "Delta_JK": -0.0045,
                "Delta_K": 0.0210,
                "delta_J": 0.00028,
                "delta_K": 0.00105,
            },
        },
        "thermodynamics": {
            "zpe_kcal_mol": EXPECTED_INVARIANT_ZPE,
            "enthalpy_kcal_mol": -180.4500,
            "gibbs_free_energy_kcal_mol": EXPECTED_INVARIANT_GIBBS,
            "vpt2_frequencies_cm1": frequencies,
        },
        "telemetry": {
            "wall_clock_time_seconds": 1845.20,
            "peak_gpu_vram_mb": 7890.0,
            "lam_active": True,
            "warnings": warnings,
            "node_architecture": {
                "cpu_cores": 128,
                "gpu_model": "NVIDIA A100-SXM4-80GB",
                "hostname": "hpc-node-042",
            },
        },
        "provenance": {
            "engine_versions": {
                "orca": "6.1.1",
                "mace": "0.2.0",
                "xtb": "6.7.1",
                "spycfit": "1.4.0",
            },
            "config_sha256": ("4a5c68385b45da87a2455b669be3089e103d09c60d135447f982148df555a59e"),
        },
    }


def test_token_count_assertion(
    authentic_aggregated_data: dict[str, Any],
    maximal_oversized_payload: dict[str, Any],
) -> None:
    """Test 1: Asserts that count_tokens measures tokens using tiktoken."""
    builder = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )

    test_text = "CoChem-SCRIBE Mathematical Air-Gap and Token Metrology Engine."
    measured_tokens = builder.count_tokens(test_text)

    enc = tiktoken.get_encoding("cl100k_base")
    expected_tokens = len(enc.encode(test_text))
    assert measured_tokens == expected_tokens
    assert measured_tokens > 0

    json_str = json.dumps(authentic_aggregated_data)
    json_token_count = builder.count_tokens(json_str)
    assert json_token_count == len(enc.encode(json_str))
    assert json_token_count < DEFAULT_TOKEN_LIMIT

    # Assert that oversized physical chemistry data payload exceeds 6,000 token limit
    oversized_str = json.dumps(maximal_oversized_payload)
    oversized_token_count = builder.count_tokens(oversized_str)
    assert oversized_token_count > DEFAULT_TOKEN_LIMIT
    assert oversized_token_count == len(enc.encode(oversized_str))


def test_truncation_trigger_and_tier_invariants(
    maximal_oversized_payload: dict[str, Any],
) -> None:
    """Test 2: Asserts 4-tier context-chunking drops and preserves Tier-4."""
    builder = PayloadBuilder(
        aggregated_data=maximal_oversized_payload,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )

    initial_tokens = builder.count_tokens(json.dumps(maximal_oversized_payload))
    assert initial_tokens > DEFAULT_TOKEN_LIMIT, (
        f"Payload must exceed ceiling (was {initial_tokens})"
    )

    truncated = builder.truncate_payload(maximal_oversized_payload)
    truncated_tokens = builder.count_tokens(json.dumps(truncated))

    assert truncated_tokens <= DEFAULT_TOKEN_LIMIT, (
        f"Truncated payload exceeds ceiling: {truncated_tokens} > 6000"
    )

    # Tier 1 Assertion: Conformers pruned down to top 3 global minima
    assert len(truncated["conformers"]) <= MAX_ALLOWED_CONFS
    assert truncated["conformers"][0]["conformer_id"] == "conf_01"
    assert truncated["conformers"][0]["relative_energy_kcal_mol"] == 0.0

    # Tier 2 Assertion: Vibrational frequencies pruned/reduced
    if "vpt2_frequencies_cm1" in truncated.get("thermodynamics", {}):
        assert len(truncated["thermodynamics"]["vpt2_frequencies_cm1"]) < len(
            maximal_oversized_payload["thermodynamics"]["vpt2_frequencies_cm1"]
        )

    # Tier 3 Assertion: Only Fatal and Critical telemetry warnings retained
    if "warnings" in truncated.get("telemetry", {}):
        assert len(truncated["telemetry"]["warnings"]) <= MAX_ALLOWED_CRITICAL_WARNINGS
        for w in truncated["telemetry"]["warnings"]:
            assert any(tag in w for tag in ["Fatal", "Critical"]), (
                f"Non-critical warning leaked: {w}"
            )

    # Tier 4 Protected Invariants (NEVER Truncate)
    assert truncated["thermodynamics"]["gibbs_free_energy_kcal_mol"] == EXPECTED_INVARIANT_GIBBS
    assert truncated["thermodynamics"]["zpe_kcal_mol"] == EXPECTED_INVARIANT_ZPE
    assert truncated["provenance"]["engine_versions"]["orca"] == "6.1.1"
    assert truncated["provenance"]["engine_versions"]["mace"] == "0.2.0"

    # Asserts that prompt construction completes without unhandled exceptions and respects token budget
    method_prompt = builder.build_methodology_prompt()
    assert builder.count_tokens(method_prompt) <= DEFAULT_TOKEN_LIMIT
    insights_prompt = builder.build_insights_prompt()
    assert builder.count_tokens(insights_prompt) <= DEFAULT_TOKEN_LIMIT


def test_master_system_prompt_regex_and_tags(
    authentic_aggregated_data: dict[str, Any],
) -> None:
    """Test 3: Asserts prompt prepends Master System Prompt with injection tags."""
    builder = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )

    sys_prompt = builder.get_master_system_prompt()
    assert (
        "You are an automated academic writer for the CoChem computational "
        "chemistry pipeline." in sys_prompt
    )
    assert "strictly forbidden" in sys_prompt
    assert "INSERT_THERMO_TABLE_HERE" in sys_prompt

    method_prompt = builder.build_methodology_prompt()
    assert method_prompt.startswith(sys_prompt) or sys_prompt in method_prompt
    assert re.search(r"strictly forbidden", method_prompt) is not None
    assert "INSERT_THERMO_TABLE_HERE" in method_prompt
    assert "INSERT_SPECTROSCOPY_TABLE_HERE" in method_prompt

    insights_prompt = builder.build_insights_prompt()
    assert insights_prompt.startswith(sys_prompt) or sys_prompt in insights_prompt
    assert re.search(r"strictly forbidden", insights_prompt) is not None
    assert "INSERT_THERMO_TABLE_HERE" in insights_prompt
    assert "Boltzmann" in insights_prompt


def test_dry_run_benchmark(authentic_aggregated_data: dict[str, Any]) -> None:
    """Test 4: Asserts dry_run=True returns fallback string in <0.05s."""
    builder = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        token_limit=DEFAULT_TOKEN_LIMIT,
        dry_run=True,
    )

    start_time = time.perf_counter()
    result_method = builder.build_methodology_prompt()
    result_insights = builder.build_insights_prompt()
    result_dry = builder.execute_dry_run()
    elapsed = time.perf_counter() - start_time

    expected_fallback = (
        "Calculations were performed using the methods listed in the appended tables. "
        "[LLM BYPASSED VIA DRY-RUN]"
    )

    assert result_method == expected_fallback
    assert result_insights == expected_fallback
    assert result_dry == expected_fallback
    assert elapsed < DRY_RUN_MAX_DURATION, f"Dry-run took too long: {elapsed:.4f}s >= 0.05s"


def test_lam_trigger_physics_justification(
    authentic_aggregated_data: dict[str, Any],
) -> None:
    """Test 5: Asserts Sinc-DVR justification injection when LAM is active."""
    builder_no_lam = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )
    prompt_no_lam = builder_no_lam.build_methodology_prompt()
    assert "Sinc-DVR" not in prompt_no_lam

    data_with_lam = dict(authentic_aggregated_data)
    data_with_lam["telemetry"] = dict(authentic_aggregated_data["telemetry"])
    data_with_lam["telemetry"]["lam_active"] = True

    builder_with_lam = PayloadBuilder(
        aggregated_data=data_with_lam,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )
    prompt_with_lam = builder_with_lam.build_methodology_prompt()

    expected_lam_phrase = (
        "The telemetry indicates the system utilized a Sinc-DVR for torsional motion. "
        "Generate one paragraph scientifically justifying the use of Sinc-DVR over the "
        "standard rigid-rotor harmonic oscillator (RRHO) approximation for this "
        "highly flexible coordinate."
    )
    assert expected_lam_phrase in prompt_with_lam


def test_synthesize_pipeline_context(
    authentic_aggregated_data: dict[str, Any],
) -> None:
    """Test 6: Asserts pipeline context extracts software stack and provenance."""
    manifest = {
        "version": "2026.2",
        "calculation_environment": "Local-Windows (WSL)",
        "engine_versions": {
            "orca": "6.1.1",
            "mace": "0.2.0",
            "xtb": "6.7.1",
        },
    }
    builder = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        manifest_data=manifest,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )
    context_str = builder.synthesize_pipeline_context()
    assert "ORCA" in context_str
    assert "CODATA 2022 constants" in context_str

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_geom\eval\__init__.py ---
"""CoChem-GEOM: Evaluation, Validation, and Metric Calculation Modules.
======================================================================
Provides physical relaxation oracles, SE(3) alignment algorithms (Kabsch),
conformer ensemble metrics (Coverage, AMR), and validation contracts.
"""

from __future__ import annotations

from cochem_geom.eval.metrics import (
    AverageMinimumRMSD,
    BoltzmannWeightedEnergyMAE,
    ConformerCoverage,
    ConformerEnsembleEvaluator,
    DEFAULT_AMR_THRESHOLD,
    DEFAULT_COV_THRESHOLD,
    DEFAULT_TEMPERATURE_K,
    EnergyMAE,
    ForceCosineSimilarity,
    ForceMAE,
    ForceRMSE,
    InertialDefectMAE,
    InternalCoordinatesMAE,
    RelativeEnergyMAE,
    RotationalConstantsMAE,
    compute_average_minimum_rmsd,
    compute_bond_angles,
    compute_bond_lengths,
    compute_conformer_coverage,
    compute_dihedral_angles,
    compute_inertial_defect,
    compute_moments_of_inertia,
    compute_rmsd,
    convert_energy,
    get_atomic_masses,
    kabsch_align,
    kabsch_rotation,
    pairwise_conformer_rmsd,
)
from cochem_geom.eval.qm_oracle import (
    BOHR_RADIUS_ANGSTROM,
    DEFAULT_FMAX_EV_ANGSTROM,
    DEFAULT_MAX_SPIN_CONTAMINATION_PERCENT,
    DEFAULT_MAX_STEPS,
    DEFAULT_TOL_MAX_G,
    EV_TO_CM_MINUS_ONE,
    EV_TO_HARTREE,
    EV_TO_KCAL_MOL,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    KCAL_MOL_TO_EV,
    KCAL_MOL_TO_HARTREE,
    PLANCK_CONSTANT_J_S,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SPEED_OF_LIGHT_M_S,
    STANDARD_TEMPERATURE_K,
    GridLevel,
    HessianPreconditioner,
    OptimizationMethod,
    ORCAOptimizationInput,
    QMOracle,
    QMOracleConfig,
    RelaxationResult,
    SpinContaminationError,
    SpinContaminationResult,
    compute_expected_s_squared,
    compute_s_squared_deviation_percent,
    evaluate_spin_contamination,
    generate_orca_optimization_block,
    get_atomic_mass,
    get_monoisotopic_mass,
    relax_conformer_xtb,
    validate_conformer_stability,
)

__all__ = [
    "AverageMinimumRMSD",
    "BOHR_RADIUS_ANGSTROM",
    "BoltzmannWeightedEnergyMAE",
    "ConformerCoverage",
    "ConformerEnsembleEvaluator",
    "DEFAULT_AMR_THRESHOLD",
    "DEFAULT_COV_THRESHOLD",
    "DEFAULT_FMAX_EV_ANGSTROM",
    "DEFAULT_MAX_SPIN_CONTAMINATION_PERCENT",
    "DEFAULT_MAX_STEPS",
    "DEFAULT_TEMPERATURE_K",
    "DEFAULT_TOL_MAX_G",
    "EV_TO_CM_MINUS_ONE",
    "EV_TO_HARTREE",
    "EV_TO_KCAL_MOL",
    "EnergyMAE",
    "ForceCosineSimilarity",
    "ForceMAE",
    "ForceRMSE",
    "GridLevel",
    "HARTREE_TO_EV",
    "HARTREE_TO_KCAL_MOL",
    "HARTREE_TO_KJ_MOL",
    "HessianPreconditioner",
    "InertialDefectMAE",
    "InternalCoordinatesMAE",
    "KCAL_MOL_TO_EV",
    "KCAL_MOL_TO_HARTREE",
    "OptimizationMethod",
    "ORCAOptimizationInput",
    "PLANCK_CONSTANT_J_S",
    "QMOracle",
    "QMOracleConfig",
    "RelativeEnergyMAE",
    "RelaxationResult",
    "RotationalConstantsMAE",
    "ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ",
    "SPEED_OF_LIGHT_M_S",
    "STANDARD_TEMPERATURE_K",
    "SpinContaminationError",
    "SpinContaminationResult",
    "compute_average_minimum_rmsd",
    "compute_bond_angles",
    "compute_bond_lengths",
    "compute_conformer_coverage",
    "compute_dihedral_angles",
    "compute_expected_s_squared",
    "compute_inertial_defect",
    "compute_moments_of_inertia",
    "compute_rmsd",
    "compute_s_squared_deviation_percent",
    "convert_energy",
    "evaluate_spin_contamination",
    "generate_orca_optimization_block",
    "get_atomic_mass",
    "get_atomic_masses",
    "get_monoisotopic_mass",
    "kabsch_align",
    "kabsch_rotation",
    "pairwise_conformer_rmsd",
    "relax_conformer_xtb",
    "validate_conformer_stability",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_scribe_payload_builder.py ---
#!/usr/bin/env python3
"""Unit Tests for CoChem-SCRIBE Context-Safe Payload Builder & Prompt Synthesizer.

Phase 2, Task 6: Context-Safe Payload Builder & Prompt Synthesis
(tests/test_scribe_payload_builder.py).

Adheres strictly to the Anti-Spoofing Protocol.
Executes against authentic data structures, verifying:
1. Token Count Estimation via tiktoken (cl100k_base).
2. 4-Tier Context Chunking, Priority Shedding, and Tier-4 Invariant Preservation.
3. Master System Prompt Regex and Mandatory Injection Tags.
4. Dry-Run Offline Benchmark (< 0.05s execution speed).
5. LAM Trigger Physics Justification Injection.
6. Pipeline Execution Provenance Context Synthesis.
7. Methodology & Insights Dynamic Prompt Targeting.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import os
import tempfile
import pytest
import tiktoken

from harvesters.scribe_payload_builder import (
    DEFAULT_TOKEN_LIMIT,
    PayloadBuilder,
)

DRY_RUN_MAX_DURATION: float = 0.05
MAX_ALLOWED_CONFS: int = 3
MAX_ALLOWED_CRITICAL_WARNINGS: int = 2
EXPECTED_INVARIANT_GIBBS: float = -182.1250
EXPECTED_INVARIANT_ZPE: float = 48.9125


@pytest.fixture(autouse=True)
def configure_airgap_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Configures tiktoken to operate strictly with offline local cache."""
    cache_dir = os.environ.get("TIKTOKEN_CACHE_DIR")
    if not cache_dir or not Path(cache_dir).exists():
        default_dir = Path(tempfile.gettempdir()) / "data-gym-cache"
        if default_dir.exists():
            cache_dir = str(default_dir)
        else:
            cache_dir = str(tmp_path / "tiktoken_cache")
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", cache_dir)


@pytest.fixture
def authentic_aggregated_data() -> dict[str, Any]:
    """Provides a realistic, authentic aggregated quantum chemistry dataset."""
    return {
        "conformers": [
            {
                "conformer_id": "conf_01",
                "relative_energy_kcal_mol": 0.000,
                "point_group_symmetry": "C2v",
                "dipole_moment_debye": 1.854,
            },
            {
                "conformer_id": "conf_02",
                "relative_energy_kcal_mol": 0.742,
                "point_group_symmetry": "Cs",
                "dipole_moment_debye": 2.110,
            },
            {
                "conformer_id": "conf_03",
                "relative_energy_kcal_mol": 1.385,
                "point_group_symmetry": "C1",
                "dipole_moment_debye": 0.940,
            },
            {
                "conformer_id": "conf_04",
                "relative_energy_kcal_mol": 2.450,
                "point_group_symmetry": "C1",
                "dipole_moment_debye": 1.450,
            },
        ],
        "spectroscopy": {
            "rotational_constants": {
                "A": 10342.15,
                "B": 2451.80,
                "C": 1980.45,
            },
            "dipole_moments": {
                "mu_a": 1.54,
                "mu_b": 0.98,
                "mu_c": 0.00,
                "total": 1.83,
            },
            "centrifugal_distortion": {
                "Delta_J": 0.00142,
                "Delta_JK": -0.00512,
                "Delta_K": 0.02341,
                "delta_J": 0.00031,
                "delta_K": 0.00115,
            },
        },
        "thermodynamics": {
            "zpe_kcal_mol": 45.6782,
            "enthalpy_kcal_mol": -153.2104,
            "gibbs_free_energy_kcal_mol": -154.8912,
            "vpt2_frequencies_cm1": [
                125.4,
                210.8,
                345.2,
                512.6,
                780.1,
                1024.5,
                1250.0,
                1480.2,
                1650.4,
                2980.1,
                3100.5,
                3650.0,
            ],
        },
        "telemetry": {
            "wall_clock_time_seconds": 142.85,
            "peak_gpu_vram_mb": 2450.0,
            "lam_active": False,
            "warnings": [
                "Info: Geometry optimization converged in 14 cycles.",
                "Warning: Low barrier detected along dihedral C1-C2-O3-H4.",
            ],
        },
        "provenance": {
            "engine_versions": {
                "orca": "6.1.1",
                "mace": "0.2.0",
                "xtb": "6.7.1",
                "pyscf": "2.8.0",
            },
            "config_sha256": ("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        },
    }


@pytest.fixture
def maximal_oversized_payload() -> dict[str, Any]:
    """Generates a maximal statistical data payload exceeding ~15,000 tokens."""
    conformers: list[dict[str, Any]] = []
    for i in range(25):
        conformers.append(
            {
                "conformer_id": f"conf_{i + 1:02d}",
                "relative_energy_kcal_mol": float(i * 0.45),
                "point_group_symmetry": "C1" if i > 0 else "C2v",
                "dipole_moment_debye": 1.5 + (i * 0.05),
                "cartesian_coordinates_angstrom": [
                    [float(j * 0.1), float(j * 0.2), float(j * 0.3)] for j in range(30)
                ],
                "rotational_constants_mhz": {
                    "A": 9000.0 - (i * 50),
                    "B": 2500.0 - (i * 20),
                    "C": 1800.0 - (i * 10),
                },
                "internal_coordinate_scan_degrees": [float(deg) for deg in range(0, 360, 5)],
            }
        )

    # Generate 3000 vibrational frequency entries to exercise Tier 2
    frequencies = [float(100.0 + k * 1.5) for k in range(3000)]

    # Generate 500 verbose telemetry warning entries for Tier 3
    warnings = [
        (
            f"Notice: Conformer exploratory step {k} generated "
            "extensive Hessian matrix gradients with potential oscillations."
        )
        for k in range(500)
    ]
    warnings.append("Critical: Memory pressure exceeded 90% threshold during Hessian inversion.")
    warnings.append("Fatal: Node 4 GPU memory bus dropped during parallel batch step.")

    return {
        "conformers": conformers,
        "spectroscopy": {
            "rotational_constants": {
                "A": 8940.12,
                "B": 2410.50,
                "C": 1780.30,
            },
            "dipole_moments": {
                "mu_a": 1.45,
                "mu_b": 0.85,
                "mu_c": 0.12,
                "total": 1.68,
            },
            "centrifugal_distortion": {
                "Delta_J": 0.0012,
                "Delta_JK": -0.0045,
                "Delta_K": 0.0210,
                "delta_J": 0.00028,
                "delta_K": 0.00105,
            },
        },
        "thermodynamics": {
            "zpe_kcal_mol": EXPECTED_INVARIANT_ZPE,
            "enthalpy_kcal_mol": -180.4500,
            "gibbs_free_energy_kcal_mol": EXPECTED_INVARIANT_GIBBS,
            "vpt2_frequencies_cm1": frequencies,
        },
        "telemetry": {
            "wall_clock_time_seconds": 1845.20,
            "peak_gpu_vram_mb": 7890.0,
            "lam_active": True,
            "warnings": warnings,
            "node_architecture": {
                "cpu_cores": 128,
                "gpu_model": "NVIDIA A100-SXM4-80GB",
                "hostname": "hpc-node-042",
            },
        },
        "provenance": {
            "engine_versions": {
                "orca": "6.1.1",
                "mace": "0.2.0",
                "xtb": "6.7.1",
                "spycfit": "1.4.0",
            },
            "config_sha256": ("4a5c68385b45da87a2455b669be3089e103d09c60d135447f982148df555a59e"),
        },
    }


def test_token_count_assertion(
    authentic_aggregated_data: dict[str, Any],
    maximal_oversized_payload: dict[str, Any],
) -> None:
    """Test 1: Asserts that count_tokens measures tokens using tiktoken."""
    builder = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )

    test_text = "CoChem-SCRIBE Mathematical Air-Gap and Token Metrology Engine."
    measured_tokens = builder.count_tokens(test_text)

    enc = tiktoken.get_encoding("cl100k_base")
    expected_tokens = len(enc.encode(test_text))
    assert measured_tokens == expected_tokens
    assert measured_tokens > 0

    json_str = json.dumps(authentic_aggregated_data)
    json_token_count = builder.count_tokens(json_str)
    assert json_token_count == len(enc.encode(json_str))
    assert json_token_count < DEFAULT_TOKEN_LIMIT

    # Assert that oversized physical chemistry data payload exceeds 6,000 token limit
    oversized_str = json.dumps(maximal_oversized_payload)
    oversized_token_count = builder.count_tokens(oversized_str)
    assert oversized_token_count > DEFAULT_TOKEN_LIMIT
    assert oversized_token_count == len(enc.encode(oversized_str))


def test_truncation_trigger_and_tier_invariants(
    maximal_oversized_payload: dict[str, Any],
) -> None:
    """Test 2: Asserts 4-tier context-chunking drops and preserves Tier-4."""
    builder = PayloadBuilder(
        aggregated_data=maximal_oversized_payload,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )

    initial_tokens = builder.count_tokens(json.dumps(maximal_oversized_payload))
    assert initial_tokens > DEFAULT_TOKEN_LIMIT, (
        f"Payload must exceed ceiling (was {initial_tokens})"
    )

    truncated = builder.truncate_payload(maximal_oversized_payload)
    truncated_tokens = builder.count_tokens(json.dumps(truncated))

    assert truncated_tokens <= DEFAULT_TOKEN_LIMIT, (
        f"Truncated payload exceeds ceiling: {truncated_tokens} > 6000"
    )

    # Tier 1 Assertion: Conformers pruned down to top 3 global minima
    assert len(truncated["conformers"]) <= MAX_ALLOWED_CONFS
    assert truncated["conformers"][0]["conformer_id"] == "conf_01"
    assert truncated["conformers"][0]["relative_energy_kcal_mol"] == 0.0

    # Tier 2 Assertion: Vibrational frequencies pruned/reduced
    if "vpt2_frequencies_cm1" in truncated.get("thermodynamics", {}):
        assert len(truncated["thermodynamics"]["vpt2_frequencies_cm1"]) < len(
            maximal_oversized_payload["thermodynamics"]["vpt2_frequencies_cm1"]
        )

    # Tier 3 Assertion: Only Fatal and Critical telemetry warnings retained
    if "warnings" in truncated.get("telemetry", {}):
        assert len(truncated["telemetry"]["warnings"]) <= MAX_ALLOWED_CRITICAL_WARNINGS
        for w in truncated["telemetry"]["warnings"]:
            assert any(tag in w for tag in ["Fatal", "Critical"]), (
                f"Non-critical warning leaked: {w}"
            )

    # Tier 4 Protected Invariants (NEVER Truncate)
    assert truncated["thermodynamics"]["gibbs_free_energy_kcal_mol"] == EXPECTED_INVARIANT_GIBBS
    assert truncated["thermodynamics"]["zpe_kcal_mol"] == EXPECTED_INVARIANT_ZPE
    assert truncated["provenance"]["engine_versions"]["orca"] == "6.1.1"
    assert truncated["provenance"]["engine_versions"]["mace"] == "0.2.0"

    # Asserts that prompt construction completes without unhandled exceptions and respects token budget
    method_prompt = builder.build_methodology_prompt()
    assert builder.count_tokens(method_prompt) <= DEFAULT_TOKEN_LIMIT
    insights_prompt = builder.build_insights_prompt()
    assert builder.count_tokens(insights_prompt) <= DEFAULT_TOKEN_LIMIT


def test_master_system_prompt_regex_and_tags(
    authentic_aggregated_data: dict[str, Any],
) -> None:
    """Test 3: Asserts prompt prepends Master System Prompt with injection tags."""
    builder = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )

    sys_prompt = builder.get_master_system_prompt()
    assert (
        "You are an automated academic writer for the CoChem computational "
        "chemistry pipeline." in sys_prompt
    )
    assert "strictly forbidden" in sys_prompt
    assert "INSERT_THERMO_TABLE_HERE" in sys_prompt

    method_prompt = builder.build_methodology_prompt()
    assert method_prompt.startswith(sys_prompt) or sys_prompt in method_prompt
    assert re.search(r"strictly forbidden", method_prompt) is not None
    assert "INSERT_THERMO_TABLE_HERE" in method_prompt
    assert "INSERT_SPECTROSCOPY_TABLE_HERE" in method_prompt

    insights_prompt = builder.build_insights_prompt()
    assert insights_prompt.startswith(sys_prompt) or sys_prompt in insights_prompt
    assert re.search(r"strictly forbidden", insights_prompt) is not None
    assert "INSERT_THERMO_TABLE_HERE" in insights_prompt
    assert "Boltzmann" in insights_prompt


def test_dry_run_benchmark(authentic_aggregated_data: dict[str, Any]) -> None:
    """Test 4: Asserts dry_run=True returns fallback string in <0.05s."""
    builder = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        token_limit=DEFAULT_TOKEN_LIMIT,
        dry_run=True,
    )

    start_time = time.perf_counter()
    result_method = builder.build_methodology_prompt()
    result_insights = builder.build_insights_prompt()
    result_dry = builder.execute_dry_run()
    elapsed = time.perf_counter() - start_time

    expected_fallback = (
        "Calculations were performed using the methods listed in the appended tables. "
        "[LLM BYPASSED VIA DRY-RUN]"
    )

    assert result_method == expected_fallback
    assert result_insights == expected_fallback
    assert result_dry == expected_fallback
    assert elapsed < DRY_RUN_MAX_DURATION, f"Dry-run took too long: {elapsed:.4f}s >= 0.05s"


def test_lam_trigger_physics_justification(
    authentic_aggregated_data: dict[str, Any],
) -> None:
    """Test 5: Asserts Sinc-DVR justification injection when LAM is active."""
    builder_no_lam = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )
    prompt_no_lam = builder_no_lam.build_methodology_prompt()
    assert "Sinc-DVR" not in prompt_no_lam

    data_with_lam = dict(authentic_aggregated_data)
    data_with_lam["telemetry"] = dict(authentic_aggregated_data["telemetry"])
    data_with_lam["telemetry"]["lam_active"] = True

    builder_with_lam = PayloadBuilder(
        aggregated_data=data_with_lam,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )
    prompt_with_lam = builder_with_lam.build_methodology_prompt()

    expected_lam_phrase = (
        "The telemetry indicates the system utilized a Sinc-DVR for torsional motion. "
        "Generate one paragraph scientifically justifying the use of Sinc-DVR over the "
        "standard rigid-rotor harmonic oscillator (RRHO) approximation for this "
        "highly flexible coordinate."
    )
    assert expected_lam_phrase in prompt_with_lam


def test_synthesize_pipeline_context(
    authentic_aggregated_data: dict[str, Any],
) -> None:
    """Test 6: Asserts pipeline context extracts software stack and provenance."""
    manifest = {
        "version": "2026.2",
        "calculation_environment": "Local-Windows (WSL)",
        "engine_versions": {
            "orca": "6.1.1",
            "mace": "0.2.0",
            "xtb": "6.7.1",
        },
    }
    builder = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        manifest_data=manifest,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )
    context_str = builder.synthesize_pipeline_context()
    assert "ORCA" in context_str
    assert "CODATA 2022 constants" in context_str

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_geom\eval\__init__.py ---
"""CoChem-GEOM: Evaluation, Validation, and Metric Calculation Modules.
======================================================================
Provides physical relaxation oracles, SE(3) alignment algorithms (Kabsch),
conformer ensemble metrics (Coverage, AMR), and validation contracts.
"""

from __future__ import annotations

from cochem_geom.eval.metrics import (
    AverageMinimumRMSD,
    BoltzmannWeightedEnergyMAE,
    ConformerCoverage,
    ConformerEnsembleEvaluator,
    DEFAULT_AMR_THRESHOLD,
    DEFAULT_COV_THRESHOLD,
    DEFAULT_TEMPERATURE_K,
    EnergyMAE,
    ForceCosineSimilarity,
    ForceMAE,
    ForceRMSE,
    InertialDefectMAE,
    InternalCoordinatesMAE,
    RelativeEnergyMAE,
    RotationalConstantsMAE,
    compute_average_minimum_rmsd,
    compute_bond_angles,
    compute_bond_lengths,
    compute_conformer_coverage,
    compute_dihedral_angles,
    compute_inertial_defect,
    compute_moments_of_inertia,
    compute_rmsd,
    convert_energy,
    get_atomic_masses,
    kabsch_align,
    kabsch_rotation,
    pairwise_conformer_rmsd,
)
from cochem_geom.eval.qm_oracle import (
    BOHR_RADIUS_ANGSTROM,
    DEFAULT_FMAX_EV_ANGSTROM,
    DEFAULT_MAX_SPIN_CONTAMINATION_PERCENT,
    DEFAULT_MAX_STEPS,
    DEFAULT_TOL_MAX_G,
    EV_TO_CM_MINUS_ONE,
    EV_TO_HARTREE,
    EV_TO_KCAL_MOL,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    KCAL_MOL_TO_EV,
    KCAL_MOL_TO_HARTREE,
    PLANCK_CONSTANT_J_S,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SPEED_OF_LIGHT_M_S,
    STANDARD_TEMPERATURE_K,
    GridLevel,
    HessianPreconditioner,
    OptimizationMethod,
    ORCAOptimizationInput,
    QMOracle,
    QMOracleConfig,
    RelaxationResult,
    SpinContaminationError,
    SpinContaminationResult,
    compute_expected_s_squared,
    compute_s_squared_deviation_percent,
    evaluate_spin_contamination,
    generate_orca_optimization_block,
    get_atomic_mass,
    get_monoisotopic_mass,
    relax_conformer_xtb,
    validate_conformer_stability,
)

__all__ = [
    "AverageMinimumRMSD",
    "BOHR_RADIUS_ANGSTROM",
    "BoltzmannWeightedEnergyMAE",
    "ConformerCoverage",
    "ConformerEnsembleEvaluator",
    "DEFAULT_AMR_THRESHOLD",
    "DEFAULT_COV_THRESHOLD",
    "DEFAULT_FMAX_EV_ANGSTROM",
    "DEFAULT_MAX_SPIN_CONTAMINATION_PERCENT",
    "DEFAULT_MAX_STEPS",
    "DEFAULT_TEMPERATURE_K",
    "DEFAULT_TOL_MAX_G",
    "EV_TO_CM_MINUS_ONE",
    "EV_TO_HARTREE",
    "EV_TO_KCAL_MOL",
    "EnergyMAE",
    "ForceCosineSimilarity",
    "ForceMAE",
    "ForceRMSE",
    "GridLevel",
    "HARTREE_TO_EV",
    "HARTREE_TO_KCAL_MOL",
    "HARTREE_TO_KJ_MOL",
    "HessianPreconditioner",
    "InertialDefectMAE",
    "InternalCoordinatesMAE",
    "KCAL_MOL_TO_EV",
    "KCAL_MOL_TO_HARTREE",
    "OptimizationMethod",
    "ORCAOptimizationInput",
    "PLANCK_CONSTANT_J_S",
    "QMOracle",
    "QMOracleConfig",
    "RelativeEnergyMAE",
    "RelaxationResult",
    "RotationalConstantsMAE",
    "ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ",
    "SPEED_OF_LIGHT_M_S",
    "STANDARD_TEMPERATURE_K",
    "SpinContaminationError",
    "SpinContaminationResult",
    "compute_average_minimum_rmsd",
    "compute_bond_angles",
    "compute_bond_lengths",
    "compute_conformer_coverage",
    "compute_dihedral_angles",
    "compute_expected_s_squared",
    "compute_inertial_defect",
    "compute_moments_of_inertia",
    "compute_rmsd",
    "compute_s_squared_deviation_percent",
    "convert_energy",
    "evaluate_spin_contamination",
    "generate_orca_optimization_block",
    "get_atomic_mass",
    "get_atomic_masses",
    "get_monoisotopic_mass",
    "kabsch_align",
    "kabsch_rotation",
    "pairwise_conformer_rmsd",
    "relax_conformer_xtb",
    "validate_conformer_stability",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_geom\eval\metrics.py ---
"""CoChem-GEOM: Precision Geometric Evaluation and Structural Metric Suite.
========================================================================
Implements TorchMetrics-compliant evaluation metrics, pure functional SE(3)
invariant alignment (Kabsch algorithm), Conformer Coverage (COV), Average
Minimum RMSD (AMR), Energy MAE/RMSE, Relative Energy Ranking, Boltzmann-Weighted
Energies, Force Error Metrics, Spectroscopic Rotational Constants (A, B, C),
Inertial Defects, and Internal Molecular Coordinates (Bonds, Angles, Dihedrals).

Authoritative Standards & Directives:
- Method Matrix v4.1: Conformer Ensemble Metrics & Physical Observables
- TorchMetrics v1.0+: Modular Metric Interface with DDP State Reduction & Pure Tensor Ops
- Mendeleev Library Mandate: All atomic/isotopic masses dynamically resolved via `mendeleev`
- SE(3) Equivariance & Invariance: Strict separation of spatial pos [N, 3] from invariant features
- State Immutability: Pure functional geometric transformations (pos_new = pos + shift, never in-place)
- Dynamic Path Resolution: Cross-platform dynamic pathing via `pathlib` and environment variables
- Provenance Tags: [M] Measured/Theoretical, [D] Derived/Calculated, [E] Expert Estimate
- Strict Zero-Mock Policy: 100% authentic physical tensor mathematics and real execution
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from mendeleev import element
import numpy as np
import torch
import torch.nn as nn
from torchmetrics import Metric

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. Fundamental Physical Constants & Conversion Factors (CODATA 2018/2022)
# ==============================================================================

SPEED_OF_LIGHT_M_S: float = 299792458.0
"""Speed of light in vacuum in meters per second (exact) [M]."""

PLANCK_CONSTANT_J_S: float = 6.62607015e-34
"""Planck constant in Joule seconds (exact) [M]."""

BOLTZMANN_CONSTANT_J_K: float = 1.380649e-23
"""Boltzmann constant in Joules per Kelvin (exact) [M]."""

BOLTZMANN_CONSTANT_EV_K: float = 8.617333262145e-5
"""Boltzmann constant in electron-volts per Kelvin [D]."""

ELEMENTARY_CHARGE_C: float = 1.602176634e-19
"""Elementary charge in Coulombs (exact) [M]."""

AVOGADRO_CONSTANT_MOL: float = 6.02214076e23
"""Avogadro constant per mole (exact) [M]."""

ATOMIC_MASS_UNIT_KG: float = 1.66053906660e-27
"""Unified atomic mass unit / Dalton in kilograms [M]."""

BOHR_RADIUS_ANGSTROM: float = 0.529177210903
"""Bohr radius in Angstroms [M]."""

HARTREE_TO_EV: float = 27.211386245988
"""Conversion factor from Hartree to electron-volts [D]."""

EV_TO_HARTREE: float = 1.0 / HARTREE_TO_EV
"""Conversion factor from electron-volts to Hartree [D]."""

HARTREE_TO_KCAL_MOL: float = 627.5094740631
"""Conversion factor from Hartree to kilocalories per mole [D]."""

KCAL_MOL_TO_HARTREE: float = 1.0 / HARTREE_TO_KCAL_MOL
"""Conversion factor from kilocalories per mole to Hartree [D]."""

KCAL_MOL_TO_EV: float = 0.04336411530877
"""Conversion factor from kilocalories per mole to electron-volts [D]."""

EV_TO_KCAL_MOL: float = 1.0 / KCAL_MOL_TO_EV
"""Conversion factor from electron-volts to kilocalories per mole [D]."""

HARTREE_TO_KJ_MOL: float = 2625.4996394799
"""Conversion factor from Hartree to kilojoules per mole [D]."""

EV_TO_KJ_MOL: float = HARTREE_TO_KJ_MOL / HARTREE_TO_EV
"""Conversion factor from electron-volts to kilojoules per mole [D]."""

EV_TO_CM_MINUS_ONE: float = 8065.54429
"""Conversion factor from electron-volts to wavenumbers (cm^-1) [D]."""

ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ: float = 505379.008784
"""Spectroscopic rotational constant conversion factor in MHz * u * Angstrom^2 [D]."""

STANDARD_TEMPERATURE_K: float = 298.15
"""Standard ambient reference temperature in Kelvin (25 deg C) [M]."""

DEFAULT_TEMPERATURE_K: float = 298.15
"""Default thermodynamic temperature in Kelvin for Boltzmann weighting [M]."""

DEFAULT_COV_THRESHOLD: float = 0.5
"""Default RMSD coverage threshold in Angstroms for conformer ensemble matching [E]."""

DEFAULT_AMR_THRESHOLD: float = 0.5
"""Default RMSD tolerance in Angstroms for average minimum RMSD evaluation [E]."""


def convert_energy(
    value: Union[float, torch.Tensor],
    from_unit: str = "ev",
    to_unit: str = "ev",
) -> Union[float, torch.Tensor]:
    """Convert energy values between supported physical units [D].

    Supported units: 'ev', 'hartree', 'kcal_mol', 'kj_mol'.
    """
    from_u = from_unit.lower().replace("/", "_").replace("-", "_")
    to_u = to_unit.lower().replace("/", "_").replace("-", "_")

    if from_u == to_u:
        return value

    # Direct conversion dictionary for exact numerical precision
    conversion_factors = {
        ("ev", "hartree"): EV_TO_HARTREE,
        ("hartree", "ev"): HARTREE_TO_EV,
        ("hartree", "kcal_mol"): HARTREE_TO_KCAL_MOL,
        ("kcal_mol", "hartree"): KCAL_MOL_TO_HARTREE,
        ("hartree", "kj_mol"): HARTREE_TO_KJ_MOL,
        ("kj_mol", "hartree"): 1.0 / HARTREE_TO_KJ_MOL,
        ("ev", "kcal_mol"): EV_TO_KCAL_MOL,
        ("kcal_mol", "ev"): KCAL_MOL_TO_EV,
        ("ev", "kj_mol"): EV_TO_KJ_MOL,
        ("kj_mol", "ev"): 1.0 / EV_TO_KJ_MOL,
        ("kcal_mol", "kj_mol"): 4.184,
        ("kj_mol", "kcal_mol"): 1.0 / 4.184,
    }

    if (from_u, to_u) in conversion_factors:
        return value * conversion_factors[(from_u, to_u)]

    # Fallback via eV
    if from_u == "ev":
        ev_val = value
    elif from_u == "hartree":
        ev_val = value * HARTREE_TO_EV
    elif from_u == "kcal_mol":
        ev_val = value * KCAL_MOL_TO_EV
    elif from_u == "kj_mol":
        ev_val = value * (1.0 / EV_TO_KJ_MOL)
    else:
        raise ValueError(f"Unsupported input energy unit: '{from_unit}'")

    if to_u == "ev":
        return ev_val
    elif to_u == "hartree":
        return ev_val * EV_TO_HARTREE
    elif to_u == "kcal_mol":
        return ev_val * EV_TO_KCAL_MOL
    elif to_u == "kj_mol":
        return ev_val * EV_TO_KJ_MOL
    else:
        raise ValueError(f"Unsupported target energy unit: '{to_unit}'")


# ==============================================================================
# 2. Dynamic Mendeleev Mass and Property Resolution Functions
# ==============================================================================

def get_atomic_mass(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query standard atomic weight from mendeleev [M]."""
    el = element(symbol_or_z)
    if el.atomic_weight is not None:
        return float(el.atomic_weight)
    if el.isotopes:
        return float(el.isotopes[0].mass)
    if el.mass is not None:
        return float(el.mass)
    raise ValueError(f"Standard atomic mass not found for element '{symbol_or_z}'")


def get_monoisotopic_mass(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query exact mass of most abundant natural isotope from mendeleev [M]."""
    el = element(symbol_or_z)
    if el.isotopes:
        most_abundant = max(
            el.isotopes,
            key=lambda iso: (iso.abundance if iso.abundance is not None else 0.0),
        )
        if most_abundant.mass is not None:
            return float(most_abundant.mass)
    if el.atomic_weight is not None:
        return float(el.atomic_weight)
    raise ValueError(f"Monoisotopic mass not found for element '{symbol_or_z}'")


def get_atomic_masses(atomic_numbers: torch.Tensor) -> torch.Tensor:
    """Dynamically query atomic masses for a tensor of atomic numbers [M]."""
    masses: List[float] = []
    for z_val in atomic_numbers.view(-1).tolist():
        masses.append(get_atomic_mass(int(z_val)))
    return torch.tensor(masses, dtype=torch.float32, device=atomic_numbers.device).view(atomic_numbers.shape)


# ==============================================================================
# 3. Pure Functional Kabsch Algorithm & SE(3) Invariant Operations
# ==============================================================================

def kabsch_rotation(
    p_centered: torch.Tensor,
    q_centered: torch.Tensor,
    weights: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """Compute optimal 3D orthogonal rotation matrix R (SO(3)) minimizing weighted RMSD [D].

    Parameters
    ----------
    p_centered : torch.Tensor
        Centered reference coordinate tensor of shape (..., N, 3).
    q_centered : torch.Tensor
        Centered target coordinate tensor of shape (..., N, 3).
    weights : Optional[torch.Tensor]
        Optional per-atom positive weights of shape (..., N) or (N,).

    Returns
    -------
    torch.Tensor
        Optimal rotation matrix R of shape (..., 3, 3) such that q @ R.mT aligns to p.
    """
    if weights is not None:
        w = weights.unsqueeze(-1) if weights.dim() == p_centered.dim() - 1 else weights
        w = w / torch.sum(w, dim=-2, keepdim=True)
        h = torch.matmul(q_centered.transpose(-1, -2), w * p_centered)
    else:
        h = torch.matmul(q_centered.transpose(-1, -2), p_centered)

    u, s, vt = torch.linalg.svd(h)
    v = vt.transpose(-1, -2)

    # Reflection correction: ensure det(R) = +1 (proper rotation in SO(3))
    det = torch.det(torch.matmul(v, u.transpose(-1, -2)))
    diag = torch.ones_like(det).unsqueeze(-1).repeat_interleave(3, dim=-1)
    diag[..., 2] = torch.where(det < 0.0, -1.0, 1.0)

    r = torch.matmul(torch.matmul(v, torch.diag_embed(diag)), u.transpose(-1, -2))
    return r


def kabsch_align(
    p_ref: torch.Tensor,
    q_target: torch.Tensor,
    weights: Optional[torch.Tensor] = None,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Align target coordinates q to reference coordinates p via Kabsch algorithm [D].

    Pure functional and state-immutable: never mutates input tensors.

    Parameters
    ----------
    p_ref : torch.Tensor
        Reference Cartesian coordinate tensor of shape (..., N, 3).
    q_target : torch.Tensor
        Target Cartesian coordinate tensor of shape (..., N, 3).
    weights : Optional[torch.Tensor]
        Optional per-atom weights of shape (..., N) or (N,).

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]
        - q_aligned: Aligned target coordinates (..., N, 3)
        - R: Optimal rotation matrix (..., 3, 3)
        - t: Translation vector (..., 3)
        - rmsd: Root-mean-square deviation (...,) in Angstroms [D]
    """
    if weights is not None:
        w = weights.unsqueeze(-1) if weights.dim() == p_ref.dim() - 1 else weights
        w_sum = torch.sum(w, dim=-2, keepdim=True) + 1e-12
        p_centroid = torch.sum(p_ref * w, dim=-2, keepdim=True) / w_sum
        q_centroid = torch.sum(q_target * w, dim=-2, keepdim=True) / w_sum
    else:
        p_centroid = torch.mean(p_ref, dim=-2, keepdim=True)
        q_centroid = torch.mean(q_target, dim=-2, keepdim=True)

    p_c = p_ref - p_centroid
    q_c = q_target - q_centroid

    r = kabsch_rotation(p_c, q_c, weights=weights)

    # Pure immutable transformation: q_aligned = q_c @ R.mT + p_centroid
    q_aligned = torch.matmul(q_c, r.transpose(-1, -2)) + p_centroid
    t = p_centroid.squeeze(-2) - torch.matmul(q_centroid.squeeze(-2), r.transpose(-1, -2))

    diff = p_ref - q_aligned
    if weights is not None:
        w_norm = weights / torch.sum(weights, dim=-1, keepdim=True)
        sq_dist = torch.sum(diff**2, dim=-1)
        mean_sq = torch.sum(sq_dist * w_norm, dim=-1)
    else:
        mean_sq = torch.mean(torch.sum(diff**2, dim=-1), dim=-1)

    rmsd = torch.sqrt(torch.clamp(mean_sq, min=0.0))
    return q_aligned, r, t, rmsd


def compute_rmsd(
    p_ref: torch.Tensor,
    q_target: torch.Tensor,
    align: bool = True,
    weights: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """Compute Root-Mean-Square Deviation (RMSD) between coordinates [D].

    Parameters
    ----------
    p_ref : torch.Tensor
        Reference Cartesian coordinates of shape (..., N, 3).
    q_target : torch.Tensor
        Target Cartesian coordinates of shape (..., N, 3).
    align : bool
        If True, applies Kabsch optimal SE(3) superposition prior to RMSD calculation.
    weights : Optional[torch.Tensor]
        Optional atom weights (e.g., atomic masses for mass-weighted RMSD).

    Returns
    -------
    torch.Tensor
        RMSD tensor of shape (...,) in Angstroms [D].
    """
    if align:
        _, _, _, rmsd = kabsch_align(p_ref, q_target, weights=weights)
        return rmsd

    diff = p_ref - q_target
    if weights is not None:
        w_norm = weights / torch.sum(weights, dim=-1, keepdim=True)
        sq_dist = torch.sum(diff**2, dim=-1)
        mean_sq = torch.sum(sq_dist * w_norm, dim=-1)
    else:
        mean_sq = torch.mean(torch.sum(diff**2, dim=-1), dim=-1)
    return torch.sqrt(torch.clamp(mean_sq, min=0.0))


def pairwise_conformer_rmsd(
    ref_conformers: torch.Tensor,
    pred_conformers: torch.Tensor,
    align: bool = True,
) -> torch.Tensor:
    """Compute all-pairs RMSD matrix between reference and predicted conformer ensembles [D].

    Parameters
    ----------
    ref_conformers : torch.Tensor
        Reference conformers tensor of shape (M, N, 3).
    pred_conformers : torch.Tensor
        Predicted conformers tensor of shape (K, N, 3).
    align : bool
        Whether to perform Kabsch alignment for each pair.

    Returns
    -------
    torch.Tensor
        Pairwise RMSD matrix of shape (M, K) in Angstroms [D].
    """
    m = ref_conformers.shape[0]
    k = pred_conformers.shape[0]
    rmsd_matrix = torch.empty((m, k), dtype=torch.float32, device=ref_conformers.device)

    for i in range(m):
        ref_i = ref_conformers[i]  # (N, 3)
        for j in range(k):
            pred_j = pred_conformers[j]  # (N, 3)
            rmsd_matrix[i, j] = compute_rmsd(ref_i, pred_j, align=align)

    return rmsd_matrix


def compute_conformer_coverage(
    ref_conformers: torch.Tensor,
    pred_conformers: torch.Tensor,
    threshold: float = DEFAULT_COV_THRESHOLD,
    align: bool = True,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Compute Conformer Coverage Recall (COV-R) and Precision (COV-P) [D].

    - COV-R: Percentage of reference conformers matched by at least one prediction within threshold.
    - COV-P: Percentage of predicted conformers matched by at least one reference within threshold.

    Parameters
    ----------
    ref_conformers : torch.Tensor
        Reference conformer ensemble of shape (M, N, 3).
    pred_conformers : torch.Tensor
        Predicted conformer ensemble of shape (K, N, 3).
    threshold : float
        RMSD cutoff threshold in Angstroms [E].
    align : bool
        Whether to apply Kabsch alignment.

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor]
        (cov_recall_percent, cov_precision_percent)
    """
    dist_matrix = pairwise_conformer_rmsd(ref_conformers, pred_conformers, align=align)

    min_rmsd_ref = torch.min(dist_matrix, dim=1).values  # (M,)
    min_rmsd_pred = torch.min(dist_matrix, dim=0).values  # (K,)

    cov_recall = (torch.sum(min_rmsd_ref <= threshold).float() / float(dist_matrix.shape[0])) * 100.0
    cov_precision = (torch.sum(min_rmsd_pred <= threshold).float() / float(dist_matrix.shape[1])) * 100.0

    return cov_recall, cov_precision


def compute_average_minimum_rmsd(
    ref_conformers: torch.Tensor,
    pred_conformers: torch.Tensor,
    align: bool = True,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Compute Average Minimum RMSD Recall (AMR-R) and Precision (AMR-P) [D].

    - AMR-R: Mean minimum RMSD over all reference conformers to the prediction ensemble.
    - AMR-P: Mean minimum RMSD over all predicted conformers to the reference ensemble.

    Parameters
    ----------
    ref_conformers : torch.Tensor
        Reference conformer ensemble of shape (M, N, 3).
    pred_conformers : torch.Tensor
        Predicted conformer ensemble of shape (K, N, 3).
    align : bool
        Whether to apply Kabsch alignment.

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor]
        (amr_recall_angstrom, amr_precision_angstrom)
    """
    dist_matrix = pairwise_conformer_rmsd(ref_conformers, pred_conformers, align=align)

    min_rmsd_ref = torch.min(dist_matrix, dim=1).values  # (M,)
    min_rmsd_pred = torch.min(dist_matrix, dim=0).values  # (K,)

    amr_recall = torch.mean(min_rmsd_ref)
    amr_precision = torch.mean(min_rmsd_pred)

    return amr_recall, amr_precision


# ==============================================================================
# 4. Spectroscopic Observables: Moments of Inertia & Rotational Constants
# ==============================================================================

def compute_moments_of_inertia(
    positions: torch.Tensor,
    atomic_numbers: torch.Tensor,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Compute principal moments of inertia and rotational constants (A >= B >= C) [D].

    Calculates center of mass using dynamic Mendeleev atomic masses, forms the
    moment of inertia tensor, diagonalizes to obtain I_a <= I_b <= I_c in u*A^2,
    and derives spectroscopic rotational constants A >= B >= C in MHz.

    Parameters
    ----------
    positions : torch.Tensor
        Cartesian coordinate tensor of shape (..., N, 3) in Angstroms.
    atomic_numbers : torch.Tensor
        Atomic numbers Z of shape (..., N) or (N,).

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor]
        - principal_moments: (..., 3) sorted (I_a, I_b, I_c) in u * Angstrom^2 [D]
        - rotational_constants_mhz: (..., 3) sorted (A, B, C) in MHz [D]
    """
    masses = get_atomic_masses(atomic_numbers)  # (..., N)
    w_mass = masses.unsqueeze(-1)  # (..., N, 1)
    total_mass = torch.sum(w_mass, dim=-2, keepdim=True) + 1e-12

    # Center of mass
    com = torch.sum(positions * w_mass, dim=-2, keepdim=True) / total_mass
    r_com = positions - com  # (..., N, 3)

    x = r_com[..., 0]
    y = r_com[..., 1]
    z = r_com[..., 2]

    # Inertia tensor components
    i_xx = torch.sum(masses * (y**2 + z**2), dim=-1)
    i_yy = torch.sum(masses * (x**2 + z**2), dim=-1)
    i_zz = torch.sum(masses * (x**2 + y**2), dim=-1)
    i_xy = -torch.sum(masses * x * y, dim=-1)
    i_xz = -torch.sum(masses * x * z, dim=-1)
    i_yz = -torch.sum(masses * y * z, dim=-1)

    # Assemble 3x3 inertia tensor
    row1 = torch.stack([i_xx, i_xy, i_xz], dim=-1)
    row2 = torch.stack([i_xy, i_yy, i_yz], dim=-1)
    row3 = torch.stack([i_xz, i_yz, i_zz], dim=-1)
    inertia_tensor = torch.stack([row1, row2, row3], dim=-2)  # (..., 3, 3)

    # Eigenvalues (principal moments of inertia)
    eigvals = torch.linalg.eigvalsh(inertia_tensor)  # (..., 3) sorted ascending
    principal_moments = torch.clamp(eigvals, min=1e-8)

    # Rotational constants: B_rot = 505379.008784 / I_p in MHz
    rotational_constants = ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / principal_moments
    # Principal moments I_a <= I_b <= I_c -> Rotational constants A >= B >= C

    return principal_moments, rotational_constants


def compute_inertial_defect(
    positions: torch.Tensor,
    atomic_numbers: torch.Tensor,
) -> torch.Tensor:
    """Compute the planar inertial defect Delta I = I_c - I_a - I_b [D].

    For strictly planar molecules, Delta I ~ 0.0 in the rigid rotor limit [M].

    Parameters
    ----------
    positions : torch.Tensor
        Cartesian coordinates (..., N, 3) in Angstroms.
    atomic_numbers : torch.Tensor
        Atomic numbers Z (..., N) or (N,).

    Returns
    -------
    torch.Tensor
        Planar inertial defect tensor (...,) in u * Angstrom^2 [D].
    """
    moments, _ = compute_moments_of_inertia(positions, atomic_numbers)
    i_a = moments[..., 0]
    i_b = moments[..., 1]
    i_c = moments[..., 2]
    return i_c - i_a - i_b


# ==============================================================================
# 5. Internal Molecular Coordinates: Bonds, Angles, and Dihedrals
# ==============================================================================

def compute_bond_lengths(
    positions: torch.Tensor,
    bonds: torch.Tensor,
) -> torch.Tensor:
    """Compute bond lengths for specified atom pairs [D].

    Parameters
    ----------
    positions : torch.Tensor
        Cartesian coordinates (N, 3) or (B, N, 3).
    bonds : torch.Tensor
        Bond index pairs tensor (E, 2).

    Returns
    -------
    torch.Tensor
        Bond lengths (E,) or (B, E) in Angstroms [D].
    """
    idx_i = bonds[:, 0]
    idx_j = bonds[:, 1]
    pos_i = positions[..., idx_i, :]
    pos_j = positions[..., idx_j, :]
    return torch.sqrt(torch.clamp(torch.sum((pos_i - pos_j) ** 2, dim=-1), min=0.0))


def compute_bond_angles(
    positions: torch.Tensor,
    angles: torch.Tensor,
) -> torch.Tensor:
    """Compute valence bond angles (i - j - k) in degrees [D].

    Parameters
    ----------
    positions : torch.Tensor
        Cartesian coordinates (N, 3) or (B, N, 3).
    angles : torch.Tensor
        Angle triplets index tensor (A, 3) where j is the central vertex atom.

    Returns
    -------
    torch.Tensor
        Valence bond angles in degrees (A,) or (B, A) [D].
    """
    idx_i = angles[:, 0]
    idx_j = angles[:, 1]  # Central vertex
    idx_k = angles[:, 2]

    pos_i = positions[..., idx_i, :]
    pos_j = positions[..., idx_j, :]
    pos_k = positions[..., idx_k, :]

    v_ji = pos_i - pos_j
    v_jk = pos_k - pos_j

    v_ji_u = v_ji / (torch.norm(v_ji, dim=-1, keepdim=True) + 1e-12)
    v_jk_u = v_jk / (torch.norm(v_jk, dim=-1, keepdim=True) + 1e-12)

    dot_prod = torch.sum(v_ji_u * v_jk_u, dim=-1)
    cos_theta = torch.clamp(dot_prod, -1.0 + 1e-7, 1.0 - 1e-7)
    return torch.rad2deg(torch.acos(cos_theta))


def compute_dihedral_angles(
    positions: torch.Tensor,
    dihedrals: torch.Tensor,
) -> torch.Tensor:
    """Compute dihedral / torsion angles (i - j - k - l) in degrees [D].

    Parameters
    ----------
    positions : torch.Tensor
        Cartesian coordinates (N, 3) or (B, N, 3).
    dihedrals : torch.Tensor
        Dihedral quadruplet index tensor (D, 4).

    Returns
    -------
    torch.Tensor
        Dihedral angles in degrees (D,) or (B, D) in range [-180, 180] [D].
    """
    p0 = positions[..., dihedrals[:, 0], :]
    p1 = positions[..., dihedrals[:, 1], :]
    p2 = positions[..., dihedrals[:, 2], :]
    p3 = positions[..., dihedrals[:, 3], :]

    b0 = -1.0 * (p1 - p0)
    b1 = p2 - p1
    b2 = p3 - p2

    b1_norm = b1 / (torch.norm(b1, dim=-1, keepdim=True) + 1e-12)

    v = b0 - torch.sum(b0 * b1_norm, dim=-1, keepdim=True) * b1_norm
    w = b2 - torch.sum(b2 * b1_norm, dim=-1, keepdim=True) * b1_norm

    x = torch.sum(v * w, dim=-1)
    y = torch.sum(torch.cross(b1_norm, v, dim=-1) * w, dim=-1)

    return torch.rad2deg(torch.atan2(y, x))


# ==============================================================================
# 6. TorchMetrics Base Metric Implementations
# ==============================================================================

class ConformerCoverage(Metric):
    """TorchMetrics implementation for Conformer Coverage (COV-R and COV-P) [D].

    Computes percentage of reference conformers covered by generated samples (Recall)
    and percentage of generated conformers matching true references (Precision)
    within a defined RMSD threshold.
    """

    full_state_update: bool = False

    def __init__(
        self,
        threshold: float = DEFAULT_COV_THRESHOLD,
        align: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.threshold = threshold
        self.align = align

        self.add_state("total_ref_covered", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_ref_count", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_pred_covered", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_pred_count", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        ref_conformers: Union[torch.Tensor, Sequence[torch.Tensor]],
        pred_conformers: Union[torch.Tensor, Sequence[torch.Tensor]],
    ) -> None:
        """Update coverage statistics with conformer ensembles.

        Parameters
        ----------
        ref_conformers : Union[torch.Tensor, Sequence[torch.Tensor]]
            Tensor of shape (M, N, 3) or list of ensemble tensors.
        pred_conformers : Union[torch.Tensor, Sequence[torch.Tensor]]
            Tensor of shape (K, N, 3) or list of ensemble tensors.
        """
        if isinstance(ref_conformers, torch.Tensor) and ref_conformers.dim() == 3:
            ref_list = [ref_conformers]
            pred_list = [pred_conformers]  # type: ignore
        else:
            ref_list = list(ref_conformers)  # type: ignore
            pred_list = list(pred_conformers)  # type: ignore

        for refs, preds in zip(ref_list, pred_list):
            dist_mat = pairwise_conformer_rmsd(refs, preds, align=self.align)
            min_ref = torch.min(dist_mat, dim=1).values
            min_pred = torch.min(dist_mat, dim=0).values

            self.total_ref_covered += torch.sum(min_ref <= self.threshold).float()
            self.total_ref_count += float(dist_mat.shape[0])
            self.total_pred_covered += torch.sum(min_pred <= self.threshold).float()
            self.total_pred_count += float(dist_mat.shape[1])

    def compute(self) -> Dict[str, torch.Tensor]:
        """Compute Conformer Coverage Recall and Precision percentages [D]."""
        cov_recall = (
            (self.total_ref_covered / (self.total_ref_count + 1e-12)) * 100.0
            if self.total_ref_count > 0
            else torch.tensor(0.0)
        )
        cov_precision = (
            (self.total_pred_covered / (self.total_pred_count + 1e-12)) * 100.0
            if self.total_pred_count > 0
            else torch.tensor(0.0)
        )
        return {
            "cov_recall": cov_recall,
            "cov_precision": cov_precision,
        }


class AverageMinimumRMSD(Metric):
    """TorchMetrics implementation for Average Minimum RMSD (AMR-R and AMR-P) [D]."""

    full_state_update: bool = False

    def __init__(
        self,
        align: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.align = align

        self.add_state("sum_min_rmsd_ref", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_ref_count", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("sum_min_rmsd_pred", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_pred_count", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        ref_conformers: Union[torch.Tensor, Sequence[torch.Tensor]],
        pred_conformers: Union[torch.Tensor, Sequence[torch.Tensor]],
    ) -> None:
        """Update AMR statistics with conformer ensembles."""
        if isinstance(ref_conformers, torch.Tensor) and ref_conformers.dim() == 3:
            ref_list = [ref_conformers]
            pred_list = [pred_conformers]  # type: ignore
        else:
            ref_list = list(ref_conformers)  # type: ignore
            pred_list = list(pred_conformers)  # type: ignore

        for refs, preds in zip(ref_list, pred_list):
            dist_mat = pairwise_conformer_rmsd(refs, preds, align=self.align)
            min_ref = torch.min(dist_mat, dim=1).values
            min_pred = torch.min(dist_mat, dim=0).values

            self.sum_min_rmsd_ref += torch.sum(min_ref)
            self.total_ref_count += float(dist_mat.shape[0])
            self.sum_min_rmsd_pred += torch.sum(min_pred)
            self.total_pred_count += float(dist_mat.shape[1])

    def compute(self) -> Dict[str, torch.Tensor]:
        """Compute AMR Recall and Precision in Angstroms [D]."""
        amr_recall = (
            self.sum_min_rmsd_ref / (self.total_ref_count + 1e-12)
            if self.total_ref_count > 0
            else torch.tensor(0.0)
        )
        amr_precision = (
            self.sum_min_rmsd_pred / (self.total_pred_count + 1e-12)
            if self.total_pred_count > 0
            else torch.tensor(0.0)
        )
        return {
            "amr_recall": amr_recall,
            "amr_precision": amr_precision,
        }


class EnergyMAE(Metric):
    """TorchMetrics implementation for Mean Absolute Error in molecular energies [D]."""

    full_state_update: bool = False

    def __init__(
        self,
        target_unit: str = "ev",
        input_unit: str = "ev",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.target_unit = target_unit
        self.input_unit = input_unit

        self.add_state("sum_abs_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_samples", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_energies: torch.Tensor,
        target_energies: torch.Tensor,
    ) -> None:
        """Update energy MAE accumulator."""
        pred = convert_energy(pred_energies.view(-1), from_unit=self.input_unit, to_unit=self.target_unit)
        target = convert_energy(target_energies.view(-1), from_unit=self.input_unit, to_unit=self.target_unit)
        error = torch.abs(pred - target)
        self.sum_abs_error += torch.sum(error)
        self.total_samples += float(error.numel())

    def compute(self) -> torch.Tensor:
        """Compute energy MAE in target units [D]."""
        return self.sum_abs_error / (self.total_samples + 1e-12)


class RelativeEnergyMAE(Metric):
    """TorchMetrics implementation for relative conformer energy ranking MAE [D].

    Computes MAE of relative energy differences (Delta E = E - min(E)) for conformer ensembles.
    """

    full_state_update: bool = False

    def __init__(
        self,
        target_unit: str = "ev",
        input_unit: str = "ev",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.target_unit = target_unit
        self.input_unit = input_unit

        self.add_state("sum_rel_abs_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_samples", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_energies: torch.Tensor,
        target_energies: torch.Tensor,
    ) -> None:
        """Update relative energy MAE."""
        pred = convert_energy(pred_energies.view(-1), from_unit=self.input_unit, to_unit=self.target_unit)
        target = convert_energy(target_energies.view(-1), from_unit=self.input_unit, to_unit=self.target_unit)

        rel_pred = pred - torch.min(pred)
        rel_target = target - torch.min(target)

        error = torch.abs(rel_pred - rel_target)
        self.sum_rel_abs_error += torch.sum(error)
        self.total_samples += float(error.numel())

    def compute(self) -> torch.Tensor:
        """Compute relative energy MAE [D]."""
        return self.sum_rel_abs_error / (self.total_samples + 1e-12)


class BoltzmannWeightedEnergyMAE(Metric):
    """TorchMetrics implementation for Boltzmann-weighted energy MAE [D].

    Weights conformers by their equilibrium Boltzmann distribution at temperature T.
    """

    full_state_update: bool = False

    def __init__(
        self,
        temperature_k: float = DEFAULT_TEMPERATURE_K,
        target_unit: str = "ev",
        input_unit: str = "ev",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.temperature_k = temperature_k
        self.target_unit = target_unit
        self.input_unit = input_unit

        self.add_state("sum_weighted_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_ensembles", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_energies: torch.Tensor,
        target_energies: torch.Tensor,
    ) -> None:
        """Update Boltzmann-weighted energy error."""
        # Convert target and pred to eV for Boltzmann factor calculation (kB * T in eV)
        pred_ev = convert_energy(pred_energies.view(-1), from_unit=self.input_unit, to_unit="ev")
        target_ev = convert_energy(target_energies.view(-1), from_unit=self.input_unit, to_unit="ev")

        kb_t_ev = BOLTZMANN_CONSTANT_EV_K * self.temperature_k
        rel_target_ev = target_ev - torch.min(target_ev)
        boltzmann_weights = torch.softmax(-rel_target_ev / kb_t_ev, dim=0)

        # Evaluate absolute error in target units
        pred_target_u = convert_energy(pred_ev, from_unit="ev", to_unit=self.target_unit)
        target_target_u = convert_energy(target_ev, from_unit="ev", to_unit=self.target_unit)
        abs_err = torch.abs(pred_target_u - target_target_u)

        weighted_err = torch.sum(boltzmann_weights * abs_err)
        self.sum_weighted_error += weighted_err
        self.total_ensembles += 1.0

    def compute(self) -> torch.Tensor:
        """Compute average Boltzmann-weighted energy error [D]."""
        return self.sum_weighted_error / (self.total_ensembles + 1e-12)


class ForceMAE(Metric):
    """TorchMetrics implementation for component-wise and vector force MAE [D]."""

    full_state_update: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.add_state("sum_abs_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_components", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(self, pred_forces: torch.Tensor, true_forces: torch.Tensor) -> None:
        """Update force MAE."""
        diff = torch.abs(pred_forces - true_forces)
        self.sum_abs_error += torch.sum(diff)
        self.total_components += float(diff.numel())

    def compute(self) -> torch.Tensor:
        """Compute force MAE in eV/Angstrom [D]."""
        return self.sum_abs_error / (self.total_components + 1e-12)


class ForceRMSE(Metric):
    """TorchMetrics implementation for force Root-Mean-Square Error [D]."""

    full_state_update: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.add_state("sum_sq_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_components", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(self, pred_forces: torch.Tensor, true_forces: torch.Tensor) -> None:
        """Update force RMSE."""
        sq_diff = (pred_forces - true_forces) ** 2
        self.sum_sq_error += torch.sum(sq_diff)
        self.total_components += float(sq_diff.numel())

    def compute(self) -> torch.Tensor:
        """Compute force RMSE in eV/Angstrom [D]."""
        return torch.sqrt(self.sum_sq_error / (self.total_components + 1e-12))


class ForceCosineSimilarity(Metric):
    """TorchMetrics implementation for force vector cosine similarity [D]."""

    full_state_update: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.add_state("sum_cosine_sim", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_vectors", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(self, pred_forces: torch.Tensor, true_forces: torch.Tensor) -> None:
        """Update force cosine similarity."""
        p_norm = torch.norm(pred_forces, dim=-1, keepdim=True) + 1e-12
        t_norm = torch.norm(true_forces, dim=-1, keepdim=True) + 1e-12
        cos_sim = torch.sum((pred_forces / p_norm) * (true_forces / t_norm), dim=-1)
        self.sum_cosine_sim += torch.sum(cos_sim)
        self.total_vectors += float(cos_sim.numel())

    def compute(self) -> torch.Tensor:
        """Compute mean force direction cosine similarity in [-1, 1] [D]."""
        return self.sum_cosine_sim / (self.total_vectors + 1e-12)


class RotationalConstantsMAE(Metric):
    """TorchMetrics implementation for spectroscopic rotational constants MAE (A, B, C) [D]."""

    full_state_update: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.add_state("sum_abs_a", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("sum_abs_b", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("sum_abs_c", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_molecules", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_positions: torch.Tensor,
        target_positions: torch.Tensor,
        atomic_numbers: torch.Tensor,
    ) -> None:
        """Update rotational constants MAE."""
        _, pred_rot = compute_moments_of_inertia(pred_positions, atomic_numbers)
        _, target_rot = compute_moments_of_inertia(target_positions, atomic_numbers)

        err_a = torch.abs(pred_rot[..., 0] - target_rot[..., 0])
        err_b = torch.abs(pred_rot[..., 1] - target_rot[..., 1])
        err_c = torch.abs(pred_rot[..., 2] - target_rot[..., 2])

        self.sum_abs_a += torch.sum(err_a)
        self.sum_abs_b += torch.sum(err_b)
        self.sum_abs_c += torch.sum(err_c)
        self.total_molecules += float(err_a.numel())

    def compute(self) -> Dict[str, torch.Tensor]:
        """Compute rotational constants MAE in MHz [D]."""
        count = self.total_molecules + 1e-12
        mae_a = self.sum_abs_a / count
        mae_b = self.sum_abs_b / count
        mae_c = self.sum_abs_c / count
        mae_mean = (mae_a + mae_b + mae_c) / 3.0
        return {
            "mae_a_mhz": mae_a,
            "mae_b_mhz": mae_b,
            "mae_c_mhz": mae_c,
            "mae_mean_mhz": mae_mean,
        }


class InertialDefectMAE(Metric):
    """TorchMetrics implementation for planar inertial defect MAE [D]."""

    full_state_update: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.add_state("sum_abs_defect_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_molecules", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_positions: torch.Tensor,
        target_positions: torch.Tensor,
        atomic_numbers: torch.Tensor,
    ) -> None:
        """Update planar inertial defect error."""
        pred_defect = compute_inertial_defect(pred_positions, atomic_numbers)
        target_defect = compute_inertial_defect(target_positions, atomic_numbers)
        err = torch.abs(pred_defect - target_defect)
        self.sum_abs_defect_error += torch.sum(err)
        self.total_molecules += float(err.numel())

    def compute(self) -> torch.Tensor:
        """Compute inertial defect MAE in u * Angstrom^2 [D]."""
        return self.sum_abs_defect_error / (self.total_molecules + 1e-12)


class InternalCoordinatesMAE(Metric):
    """TorchMetrics implementation for bond lengths, bond angles, and dihedrals MAE [D]."""

    full_state_update: bool = False

    def __init__(
        self,
        bonds: Optional[torch.Tensor] = None,
        angles: Optional[torch.Tensor] = None,
        dihedrals: Optional[torch.Tensor] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.bonds = bonds
        self.angles = angles
        self.dihedrals = dihedrals

        self.add_state("sum_bond_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_bonds", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("sum_angle_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_angles", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("sum_dihedral_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_dihedrals", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_positions: torch.Tensor,
        target_positions: torch.Tensor,
        bonds: Optional[torch.Tensor] = None,
        angles: Optional[torch.Tensor] = None,
        dihedrals: Optional[torch.Tensor] = None,
    ) -> None:
        """Update internal coordinate errors."""
        active_bonds = bonds if bonds is not None else self.bonds
        active_angles = angles if angles is not None else self.angles
        active_dihedrals = dihedrals if dihedrals is not None else self.dihedrals

        if active_bonds is not None and active_bonds.numel() > 0:
            pred_b = compute_bond_lengths(pred_positions, active_bonds)
            true_b = compute_bond_lengths(target_positions, active_bonds)
            err_b = torch.abs(pred_b - true_b)
            self.sum_bond_error += torch.sum(err_b)
            self.total_bonds += float(err_b.numel())

        if active_angles is not None and active_angles.numel() > 0:
            pred_a = compute_bond_angles(pred_positions, active_angles)
            true_a = compute_bond_angles(target_positions, active_angles)
            err_a = torch.abs(pred_a - true_a)
            self.sum_angle_error += torch.sum(err_a)
            self.total_angles += float(err_a.numel())

        if active_dihedrals is not None and active_dihedrals.numel() > 0:
            pred_d = compute_dihedral_angles(pred_positions, active_dihedrals)
            true_d = compute_dihedral_angles(target_positions, active_dihedrals)
            # Periodic angular difference in [-180, 180]
            diff_d = torch.remainder(pred_d - true_d + 180.0, 360.0) - 180.0
            err_d = torch.abs(diff_d)
            self.sum_dihedral_error += torch.sum(err_d)
            self.total_dihedrals += float(err_d.numel())

    def compute(self) -> Dict[str, torch.Tensor]:
        """Compute internal coordinates MAE dictionary [D]."""
        res: Dict[str, torch.Tensor] = {}
        if self.total_bonds > 0:
            res["mae_bonds_angstrom"] = self.sum_bond_error / self.total_bonds
        if self.total_angles > 0:
            res["mae_angles_deg"] = self.sum_angle_error / self.total_angles
        if self.total_dihedrals > 0:
            res["mae_dihedrals_deg"] = self.sum_dihedral_error / self.total_dihedrals
        return res


class ConformerEnsembleEvaluator(Metric):
    """Comprehensive multi-metric evaluator for conformer generation models.

    Integrates COV-R, COV-P, AMR-R, AMR-P, Energy MAE, Relative Energy MAE,
    and Rotational Constants tracking into a unified evaluation harness.
    """

    full_state_update: bool = False

    def __init__(
        self,
        thresholds: Sequence[float] = (0.5, 1.25),
        temperature_k: float = DEFAULT_TEMPERATURE_K,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.thresholds = list(thresholds)
        self.temperature_k = temperature_k

        # Safe keys without dots for nn.ModuleDict
        self.cov_metrics = nn.ModuleDict(
            {f"cov_{t:.2f}".replace(".", "_"): ConformerCoverage(threshold=t) for t in self.thresholds}
        )
        self.amr_metric = AverageMinimumRMSD()
        self.energy_mae = EnergyMAE(target_unit="ev")
        self.rel_energy_mae = RelativeEnergyMAE(target_unit="ev")
        self.rotational_mae = RotationalConstantsMAE()

    def update(
        self,
        ref_positions: torch.Tensor,
        pred_positions: torch.Tensor,
        ref_energies: Optional[torch.Tensor] = None,
        pred_energies: Optional[torch.Tensor] = None,
        atomic_numbers: Optional[torch.Tensor] = None,
    ) -> None:
        """Update all component metrics with evaluation batch."""
        for metric in self.cov_metrics.values():
            metric.update(ref_positions, pred_positions)

        self.amr_metric.update(ref_positions, pred_positions)

        if ref_energies is not None and pred_energies is not None:
            self.energy_mae.update(pred_energies, ref_energies)
            self.rel_energy_mae.update(pred_energies, ref_energies)

        if atomic_numbers is not None and ref_positions.dim() >= 2 and pred_positions.dim() >= 2:
            self.rotational_mae.update(pred_positions, ref_positions, atomic_numbers)

    def compute(self) -> Dict[str, torch.Tensor]:
        """Compute unified summary dictionary across all evaluated metrics [D]."""
        results: Dict[str, torch.Tensor] = {}

        for name, metric in self.cov_metrics.items():
            cov_res = metric.compute()
            t_str = name.split("cov_")[-1].replace("_", ".")
            results[f"cov_recall_{t_str}"] = cov_res["cov_recall"]
            results[f"cov_precision_{t_str}"] = cov_res["cov_precision"]

        amr_res = self.amr_metric.compute()
        results["amr_recall"] = amr_res["amr_recall"]
        results["amr_precision"] = amr_res["amr_precision"]

        if self.energy_mae.total_samples > 0:
            results["energy_mae_ev"] = self.energy_mae.compute()
            results["rel_energy_mae_ev"] = self.rel_energy_mae.compute()

        if self.rotational_mae.total_molecules > 0:
            rot_res = self.rotational_mae.compute()
            results["rotational_mae_mhz"] = rot_res["mae_mean_mhz"]
            results["rotational_mae_a_mhz"] = rot_res["mae_a_mhz"]
            results["rotational_mae_b_mhz"] = rot_res["mae_b_mhz"]
            results["rotational_mae_c_mhz"] = rot_res["mae_c_mhz"]

        return results

    def reset(self) -> None:
        """Reset all child metrics."""
        super().reset()
        for metric in self.cov_metrics.values():
            metric.reset()
        self.amr_metric.reset()
        self.energy_mae.reset()
        self.rel_energy_mae.reset()
        self.rotational_mae.reset()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\src\cochem_geom\eval\metrics.py ---
"""CoChem-GEOM: Precision Geometric Evaluation and Structural Metric Suite.
========================================================================
Implements TorchMetrics-compliant evaluation metrics, pure functional SE(3)
invariant alignment (Kabsch algorithm), Conformer Coverage (COV), Average
Minimum RMSD (AMR), Energy MAE/RMSE, Relative Energy Ranking, Boltzmann-Weighted
Energies, Force Error Metrics, Spectroscopic Rotational Constants (A, B, C),
Inertial Defects, and Internal Molecular Coordinates (Bonds, Angles, Dihedrals).

Authoritative Standards & Directives:
- Method Matrix v4.1: Conformer Ensemble Metrics & Physical Observables
- TorchMetrics v1.0+: Modular Metric Interface with DDP State Reduction & Pure Tensor Ops
- Mendeleev Library Mandate: All atomic/isotopic masses dynamically resolved via `mendeleev`
- SE(3) Equivariance & Invariance: Strict separation of spatial pos [N, 3] from invariant features
- State Immutability: Pure functional geometric transformations (pos_new = pos + shift, never in-place)
- Dynamic Path Resolution: Cross-platform dynamic pathing via `pathlib` and environment variables
- Provenance Tags: [M] Measured/Theoretical, [D] Derived/Calculated, [E] Expert Estimate
- Strict Zero-Mock Policy: 100% authentic physical tensor mathematics and real execution
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from mendeleev import element
import numpy as np
import torch
import torch.nn as nn
from torchmetrics import Metric

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. Fundamental Physical Constants & Conversion Factors (CODATA 2018/2022)
# ==============================================================================

SPEED_OF_LIGHT_M_S: float = 299792458.0
"""Speed of light in vacuum in meters per second (exact) [M]."""

PLANCK_CONSTANT_J_S: float = 6.62607015e-34
"""Planck constant in Joule seconds (exact) [M]."""

BOLTZMANN_CONSTANT_J_K: float = 1.380649e-23
"""Boltzmann constant in Joules per Kelvin (exact) [M]."""

BOLTZMANN_CONSTANT_EV_K: float = 8.617333262145e-5
"""Boltzmann constant in electron-volts per Kelvin [D]."""

ELEMENTARY_CHARGE_C: float = 1.602176634e-19
"""Elementary charge in Coulombs (exact) [M]."""

AVOGADRO_CONSTANT_MOL: float = 6.02214076e23
"""Avogadro constant per mole (exact) [M]."""

ATOMIC_MASS_UNIT_KG: float = 1.66053906660e-27
"""Unified atomic mass unit / Dalton in kilograms [M]."""

BOHR_RADIUS_ANGSTROM: float = 0.529177210903
"""Bohr radius in Angstroms [M]."""

HARTREE_TO_EV: float = 27.211386245988
"""Conversion factor from Hartree to electron-volts [D]."""

EV_TO_HARTREE: float = 1.0 / HARTREE_TO_EV
"""Conversion factor from electron-volts to Hartree [D]."""

HARTREE_TO_KCAL_MOL: float = 627.5094740631
"""Conversion factor from Hartree to kilocalories per mole [D]."""

KCAL_MOL_TO_HARTREE: float = 1.0 / HARTREE_TO_KCAL_MOL
"""Conversion factor from kilocalories per mole to Hartree [D]."""

KCAL_MOL_TO_EV: float = 0.04336411530877
"""Conversion factor from kilocalories per mole to electron-volts [D]."""

EV_TO_KCAL_MOL: float = 1.0 / KCAL_MOL_TO_EV
"""Conversion factor from electron-volts to kilocalories per mole [D]."""

HARTREE_TO_KJ_MOL: float = 2625.4996394799
"""Conversion factor from Hartree to kilojoules per mole [D]."""

EV_TO_KJ_MOL: float = HARTREE_TO_KJ_MOL / HARTREE_TO_EV
"""Conversion factor from electron-volts to kilojoules per mole [D]."""

EV_TO_CM_MINUS_ONE: float = 8065.54429
"""Conversion factor from electron-volts to wavenumbers (cm^-1) [D]."""

ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ: float = 505379.008784
"""Spectroscopic rotational constant conversion factor in MHz * u * Angstrom^2 [D]."""

STANDARD_TEMPERATURE_K: float = 298.15
"""Standard ambient reference temperature in Kelvin (25 deg C) [M]."""

DEFAULT_TEMPERATURE_K: float = 298.15
"""Default thermodynamic temperature in Kelvin for Boltzmann weighting [M]."""

DEFAULT_COV_THRESHOLD: float = 0.5
"""Default RMSD coverage threshold in Angstroms for conformer ensemble matching [E]."""

DEFAULT_AMR_THRESHOLD: float = 0.5
"""Default RMSD tolerance in Angstroms for average minimum RMSD evaluation [E]."""


def convert_energy(
    value: Union[float, torch.Tensor],
    from_unit: str = "ev",
    to_unit: str = "ev",
) -> Union[float, torch.Tensor]:
    """Convert energy values between supported physical units [D].

    Supported units: 'ev', 'hartree', 'kcal_mol', 'kj_mol'.
    """
    from_u = from_unit.lower().replace("/", "_").replace("-", "_")
    to_u = to_unit.lower().replace("/", "_").replace("-", "_")

    if from_u == to_u:
        return value

    # Direct conversion dictionary for exact numerical precision
    conversion_factors = {
        ("ev", "hartree"): EV_TO_HARTREE,
        ("hartree", "ev"): HARTREE_TO_EV,
        ("hartree", "kcal_mol"): HARTREE_TO_KCAL_MOL,
        ("kcal_mol", "hartree"): KCAL_MOL_TO_HARTREE,
        ("hartree", "kj_mol"): HARTREE_TO_KJ_MOL,
        ("kj_mol", "hartree"): 1.0 / HARTREE_TO_KJ_MOL,
        ("ev", "kcal_mol"): EV_TO_KCAL_MOL,
        ("kcal_mol", "ev"): KCAL_MOL_TO_EV,
        ("ev", "kj_mol"): EV_TO_KJ_MOL,
        ("kj_mol", "ev"): 1.0 / EV_TO_KJ_MOL,
        ("kcal_mol", "kj_mol"): 4.184,
        ("kj_mol", "kcal_mol"): 1.0 / 4.184,
    }

    if (from_u, to_u) in conversion_factors:
        return value * conversion_factors[(from_u, to_u)]

    # Fallback via eV
    if from_u == "ev":
        ev_val = value
    elif from_u == "hartree":
        ev_val = value * HARTREE_TO_EV
    elif from_u == "kcal_mol":
        ev_val = value * KCAL_MOL_TO_EV
    elif from_u == "kj_mol":
        ev_val = value * (1.0 / EV_TO_KJ_MOL)
    else:
        raise ValueError(f"Unsupported input energy unit: '{from_unit}'")

    if to_u == "ev":
        return ev_val
    elif to_u == "hartree":
        return ev_val * EV_TO_HARTREE
    elif to_u == "kcal_mol":
        return ev_val * EV_TO_KCAL_MOL
    elif to_u == "kj_mol":
        return ev_val * EV_TO_KJ_MOL
    else:
        raise ValueError(f"Unsupported target energy unit: '{to_unit}'")


# ==============================================================================
# 2. Dynamic Mendeleev Mass and Property Resolution Functions
# ==============================================================================

def get_atomic_mass(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query standard atomic weight from mendeleev [M]."""
    el = element(symbol_or_z)
    if el.atomic_weight is not None:
        return float(el.atomic_weight)
    if el.isotopes:
        return float(el.isotopes[0].mass)
    if el.mass is not None:
        return float(el.mass)
    raise ValueError(f"Standard atomic mass not found for element '{symbol_or_z}'")


def get_monoisotopic_mass(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query exact mass of most abundant natural isotope from mendeleev [M]."""
    el = element(symbol_or_z)
    if el.isotopes:
        most_abundant = max(
            el.isotopes,
            key=lambda iso: (iso.abundance if iso.abundance is not None else 0.0),
        )
        if most_abundant.mass is not None:
            return float(most_abundant.mass)
    if el.atomic_weight is not None:
        return float(el.atomic_weight)
    raise ValueError(f"Monoisotopic mass not found for element '{symbol_or_z}'")


def get_atomic_masses(atomic_numbers: torch.Tensor) -> torch.Tensor:
    """Dynamically query atomic masses for a tensor of atomic numbers [M]."""
    masses: List[float] = []
    for z_val in atomic_numbers.view(-1).tolist():
        masses.append(get_atomic_mass(int(z_val)))
    return torch.tensor(masses, dtype=torch.float32, device=atomic_numbers.device).view(atomic_numbers.shape)


# ==============================================================================
# 3. Pure Functional Kabsch Algorithm & SE(3) Invariant Operations
# ==============================================================================

def kabsch_rotation(
    p_centered: torch.Tensor,
    q_centered: torch.Tensor,
    weights: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """Compute optimal 3D orthogonal rotation matrix R (SO(3)) minimizing weighted RMSD [D].

    Parameters
    ----------
    p_centered : torch.Tensor
        Centered reference coordinate tensor of shape (..., N, 3).
    q_centered : torch.Tensor
        Centered target coordinate tensor of shape (..., N, 3).
    weights : Optional[torch.Tensor]
        Optional per-atom positive weights of shape (..., N) or (N,).

    Returns
    -------
    torch.Tensor
        Optimal rotation matrix R of shape (..., 3, 3) such that q @ R.mT aligns to p.
    """
    if weights is not None:
        w = weights.unsqueeze(-1) if weights.dim() == p_centered.dim() - 1 else weights
        w = w / torch.sum(w, dim=-2, keepdim=True)
        h = torch.matmul(q_centered.transpose(-1, -2), w * p_centered)
    else:
        h = torch.matmul(q_centered.transpose(-1, -2), p_centered)

    u, s, vt = torch.linalg.svd(h)
    v = vt.transpose(-1, -2)

    # Reflection correction: ensure det(R) = +1 (proper rotation in SO(3))
    det = torch.det(torch.matmul(v, u.transpose(-1, -2)))
    diag = torch.ones_like(det).unsqueeze(-1).repeat_interleave(3, dim=-1)
    diag[..., 2] = torch.where(det < 0.0, -1.0, 1.0)

    r = torch.matmul(torch.matmul(v, torch.diag_embed(diag)), u.transpose(-1, -2))
    return r


def kabsch_align(
    p_ref: torch.Tensor,
    q_target: torch.Tensor,
    weights: Optional[torch.Tensor] = None,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Align target coordinates q to reference coordinates p via Kabsch algorithm [D].

    Pure functional and state-immutable: never mutates input tensors.

    Parameters
    ----------
    p_ref : torch.Tensor
        Reference Cartesian coordinate tensor of shape (..., N, 3).
    q_target : torch.Tensor
        Target Cartesian coordinate tensor of shape (..., N, 3).
    weights : Optional[torch.Tensor]
        Optional per-atom weights of shape (..., N) or (N,).

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]
        - q_aligned: Aligned target coordinates (..., N, 3)
        - R: Optimal rotation matrix (..., 3, 3)
        - t: Translation vector (..., 3)
        - rmsd: Root-mean-square deviation (...,) in Angstroms [D]
    """
    if weights is not None:
        w = weights.unsqueeze(-1) if weights.dim() == p_ref.dim() - 1 else weights
        w_sum = torch.sum(w, dim=-2, keepdim=True) + 1e-12
        p_centroid = torch.sum(p_ref * w, dim=-2, keepdim=True) / w_sum
        q_centroid = torch.sum(q_target * w, dim=-2, keepdim=True) / w_sum
    else:
        p_centroid = torch.mean(p_ref, dim=-2, keepdim=True)
        q_centroid = torch.mean(q_target, dim=-2, keepdim=True)

    p_c = p_ref - p_centroid
    q_c = q_target - q_centroid

    r = kabsch_rotation(p_c, q_c, weights=weights)

    # Pure immutable transformation: q_aligned = q_c @ R.mT + p_centroid
    q_aligned = torch.matmul(q_c, r.transpose(-1, -2)) + p_centroid
    t = p_centroid.squeeze(-2) - torch.matmul(q_centroid.squeeze(-2), r.transpose(-1, -2))

    diff = p_ref - q_aligned
    if weights is not None:
        w_norm = weights / torch.sum(weights, dim=-1, keepdim=True)
        sq_dist = torch.sum(diff**2, dim=-1)
        mean_sq = torch.sum(sq_dist * w_norm, dim=-1)
    else:
        mean_sq = torch.mean(torch.sum(diff**2, dim=-1), dim=-1)

    rmsd = torch.sqrt(torch.clamp(mean_sq, min=0.0))
    return q_aligned, r, t, rmsd


def compute_rmsd(
    p_ref: torch.Tensor,
    q_target: torch.Tensor,
    align: bool = True,
    weights: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """Compute Root-Mean-Square Deviation (RMSD) between coordinates [D].

    Parameters
    ----------
    p_ref : torch.Tensor
        Reference Cartesian coordinates of shape (..., N, 3).
    q_target : torch.Tensor
        Target Cartesian coordinates of shape (..., N, 3).
    align : bool
        If True, applies Kabsch optimal SE(3) superposition prior to RMSD calculation.
    weights : Optional[torch.Tensor]
        Optional atom weights (e.g., atomic masses for mass-weighted RMSD).

    Returns
    -------
    torch.Tensor
        RMSD tensor of shape (...,) in Angstroms [D].
    """
    if align:
        _, _, _, rmsd = kabsch_align(p_ref, q_target, weights=weights)
        return rmsd

    diff = p_ref - q_target
    if weights is not None:
        w_norm = weights / torch.sum(weights, dim=-1, keepdim=True)
        sq_dist = torch.sum(diff**2, dim=-1)
        mean_sq = torch.sum(sq_dist * w_norm, dim=-1)
    else:
        mean_sq = torch.mean(torch.sum(diff**2, dim=-1), dim=-1)
    return torch.sqrt(torch.clamp(mean_sq, min=0.0))


def pairwise_conformer_rmsd(
    ref_conformers: torch.Tensor,
    pred_conformers: torch.Tensor,
    align: bool = True,
) -> torch.Tensor:
    """Compute all-pairs RMSD matrix between reference and predicted conformer ensembles [D].

    Parameters
    ----------
    ref_conformers : torch.Tensor
        Reference conformers tensor of shape (M, N, 3).
    pred_conformers : torch.Tensor
        Predicted conformers tensor of shape (K, N, 3).
    align : bool
        Whether to perform Kabsch alignment for each pair.

    Returns
    -------
    torch.Tensor
        Pairwise RMSD matrix of shape (M, K) in Angstroms [D].
    """
    m = ref_conformers.shape[0]
    k = pred_conformers.shape[0]
    rmsd_matrix = torch.empty((m, k), dtype=torch.float32, device=ref_conformers.device)

    for i in range(m):
        ref_i = ref_conformers[i]  # (N, 3)
        for j in range(k):
            pred_j = pred_conformers[j]  # (N, 3)
            rmsd_matrix[i, j] = compute_rmsd(ref_i, pred_j, align=align)

    return rmsd_matrix


def compute_conformer_coverage(
    ref_conformers: torch.Tensor,
    pred_conformers: torch.Tensor,
    threshold: float = DEFAULT_COV_THRESHOLD,
    align: bool = True,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Compute Conformer Coverage Recall (COV-R) and Precision (COV-P) [D].

    - COV-R: Percentage of reference conformers matched by at least one prediction within threshold.
    - COV-P: Percentage of predicted conformers matched by at least one reference within threshold.

    Parameters
    ----------
    ref_conformers : torch.Tensor
        Reference conformer ensemble of shape (M, N, 3).
    pred_conformers : torch.Tensor
        Predicted conformer ensemble of shape (K, N, 3).
    threshold : float
        RMSD cutoff threshold in Angstroms [E].
    align : bool
        Whether to apply Kabsch alignment.

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor]
        (cov_recall_percent, cov_precision_percent)
    """
    dist_matrix = pairwise_conformer_rmsd(ref_conformers, pred_conformers, align=align)

    min_rmsd_ref = torch.min(dist_matrix, dim=1).values  # (M,)
    min_rmsd_pred = torch.min(dist_matrix, dim=0).values  # (K,)

    cov_recall = (torch.sum(min_rmsd_ref <= threshold).float() / float(dist_matrix.shape[0])) * 100.0
    cov_precision = (torch.sum(min_rmsd_pred <= threshold).float() / float(dist_matrix.shape[1])) * 100.0

    return cov_recall, cov_precision


def compute_average_minimum_rmsd(
    ref_conformers: torch.Tensor,
    pred_conformers: torch.Tensor,
    align: bool = True,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Compute Average Minimum RMSD Recall (AMR-R) and Precision (AMR-P) [D].

    - AMR-R: Mean minimum RMSD over all reference conformers to the prediction ensemble.
    - AMR-P: Mean minimum RMSD over all predicted conformers to the reference ensemble.

    Parameters
    ----------
    ref_conformers : torch.Tensor
        Reference conformer ensemble of shape (M, N, 3).
    pred_conformers : torch.Tensor
        Predicted conformer ensemble of shape (K, N, 3).
    align : bool
        Whether to apply Kabsch alignment.

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor]
        (amr_recall_angstrom, amr_precision_angstrom)
    """
    dist_matrix = pairwise_conformer_rmsd(ref_conformers, pred_conformers, align=align)

    min_rmsd_ref = torch.min(dist_matrix, dim=1).values  # (M,)
    min_rmsd_pred = torch.min(dist_matrix, dim=0).values  # (K,)

    amr_recall = torch.mean(min_rmsd_ref)
    amr_precision = torch.mean(min_rmsd_pred)

    return amr_recall, amr_precision


# ==============================================================================
# 4. Spectroscopic Observables: Moments of Inertia & Rotational Constants
# ==============================================================================

def compute_moments_of_inertia(
    positions: torch.Tensor,
    atomic_numbers: torch.Tensor,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Compute principal moments of inertia and rotational constants (A >= B >= C) [D].

    Calculates center of mass using dynamic Mendeleev atomic masses, forms the
    moment of inertia tensor, diagonalizes to obtain I_a <= I_b <= I_c in u*A^2,
    and derives spectroscopic rotational constants A >= B >= C in MHz.

    Parameters
    ----------
    positions : torch.Tensor
        Cartesian coordinate tensor of shape (..., N, 3) in Angstroms.
    atomic_numbers : torch.Tensor
        Atomic numbers Z of shape (..., N) or (N,).

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor]
        - principal_moments: (..., 3) sorted (I_a, I_b, I_c) in u * Angstrom^2 [D]
        - rotational_constants_mhz: (..., 3) sorted (A, B, C) in MHz [D]
    """
    masses = get_atomic_masses(atomic_numbers)  # (..., N)
    w_mass = masses.unsqueeze(-1)  # (..., N, 1)
    total_mass = torch.sum(w_mass, dim=-2, keepdim=True) + 1e-12

    # Center of mass
    com = torch.sum(positions * w_mass, dim=-2, keepdim=True) / total_mass
    r_com = positions - com  # (..., N, 3)

    x = r_com[..., 0]
    y = r_com[..., 1]
    z = r_com[..., 2]

    # Inertia tensor components
    i_xx = torch.sum(masses * (y**2 + z**2), dim=-1)
    i_yy = torch.sum(masses * (x**2 + z**2), dim=-1)
    i_zz = torch.sum(masses * (x**2 + y**2), dim=-1)
    i_xy = -torch.sum(masses * x * y, dim=-1)
    i_xz = -torch.sum(masses * x * z, dim=-1)
    i_yz = -torch.sum(masses * y * z, dim=-1)

    # Assemble 3x3 inertia tensor
    row1 = torch.stack([i_xx, i_xy, i_xz], dim=-1)
    row2 = torch.stack([i_xy, i_yy, i_yz], dim=-1)
    row3 = torch.stack([i_xz, i_yz, i_zz], dim=-1)
    inertia_tensor = torch.stack([row1, row2, row3], dim=-2)  # (..., 3, 3)

    # Eigenvalues (principal moments of inertia)
    eigvals = torch.linalg.eigvalsh(inertia_tensor)  # (..., 3) sorted ascending
    principal_moments = torch.clamp(eigvals, min=1e-8)

    # Rotational constants: B_rot = 505379.008784 / I_p in MHz
    rotational_constants = ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / principal_moments
    # Principal moments I_a <= I_b <= I_c -> Rotational constants A >= B >= C

    return principal_moments, rotational_constants


def compute_inertial_defect(
    positions: torch.Tensor,
    atomic_numbers: torch.Tensor,
) -> torch.Tensor:
    """Compute the planar inertial defect Delta I = I_c - I_a - I_b [D].

    For strictly planar molecules, Delta I ~ 0.0 in the rigid rotor limit [M].

    Parameters
    ----------
    positions : torch.Tensor
        Cartesian coordinates (..., N, 3) in Angstroms.
    atomic_numbers : torch.Tensor
        Atomic numbers Z (..., N) or (N,).

    Returns
    -------
    torch.Tensor
        Planar inertial defect tensor (...,) in u * Angstrom^2 [D].
    """
    moments, _ = compute_moments_of_inertia(positions, atomic_numbers)
    i_a = moments[..., 0]
    i_b = moments[..., 1]
    i_c = moments[..., 2]
    return i_c - i_a - i_b


# ==============================================================================
# 5. Internal Molecular Coordinates: Bonds, Angles, and Dihedrals
# ==============================================================================

def compute_bond_lengths(
    positions: torch.Tensor,
    bonds: torch.Tensor,
) -> torch.Tensor:
    """Compute bond lengths for specified atom pairs [D].

    Parameters
    ----------
    positions : torch.Tensor
        Cartesian coordinates (N, 3) or (B, N, 3).
    bonds : torch.Tensor
        Bond index pairs tensor (E, 2).

    Returns
    -------
    torch.Tensor
        Bond lengths (E,) or (B, E) in Angstroms [D].
    """
    idx_i = bonds[:, 0]
    idx_j = bonds[:, 1]
    pos_i = positions[..., idx_i, :]
    pos_j = positions[..., idx_j, :]
    return torch.sqrt(torch.clamp(torch.sum((pos_i - pos_j) ** 2, dim=-1), min=0.0))


def compute_bond_angles(
    positions: torch.Tensor,
    angles: torch.Tensor,
) -> torch.Tensor:
    """Compute valence bond angles (i - j - k) in degrees [D].

    Parameters
    ----------
    positions : torch.Tensor
        Cartesian coordinates (N, 3) or (B, N, 3).
    angles : torch.Tensor
        Angle triplets index tensor (A, 3) where j is the central vertex atom.

    Returns
    -------
    torch.Tensor
        Valence bond angles in degrees (A,) or (B, A) [D].
    """
    idx_i = angles[:, 0]
    idx_j = angles[:, 1]  # Central vertex
    idx_k = angles[:, 2]

    pos_i = positions[..., idx_i, :]
    pos_j = positions[..., idx_j, :]
    pos_k = positions[..., idx_k, :]

    v_ji = pos_i - pos_j
    v_jk = pos_k - pos_j

    v_ji_u = v_ji / (torch.norm(v_ji, dim=-1, keepdim=True) + 1e-12)
    v_jk_u = v_jk / (torch.norm(v_jk, dim=-1, keepdim=True) + 1e-12)

    dot_prod = torch.sum(v_ji_u * v_jk_u, dim=-1)
    cos_theta = torch.clamp(dot_prod, -1.0 + 1e-7, 1.0 - 1e-7)
    return torch.rad2deg(torch.acos(cos_theta))


def compute_dihedral_angles(
    positions: torch.Tensor,
    dihedrals: torch.Tensor,
) -> torch.Tensor:
    """Compute dihedral / torsion angles (i - j - k - l) in degrees [D].

    Parameters
    ----------
    positions : torch.Tensor
        Cartesian coordinates (N, 3) or (B, N, 3).
    dihedrals : torch.Tensor
        Dihedral quadruplet index tensor (D, 4).

    Returns
    -------
    torch.Tensor
        Dihedral angles in degrees (D,) or (B, D) in range [-180, 180] [D].
    """
    p0 = positions[..., dihedrals[:, 0], :]
    p1 = positions[..., dihedrals[:, 1], :]
    p2 = positions[..., dihedrals[:, 2], :]
    p3 = positions[..., dihedrals[:, 3], :]

    b0 = -1.0 * (p1 - p0)
    b1 = p2 - p1
    b2 = p3 - p2

    b1_norm = b1 / (torch.norm(b1, dim=-1, keepdim=True) + 1e-12)

    v = b0 - torch.sum(b0 * b1_norm, dim=-1, keepdim=True) * b1_norm
    w = b2 - torch.sum(b2 * b1_norm, dim=-1, keepdim=True) * b1_norm

    x = torch.sum(v * w, dim=-1)
    y = torch.sum(torch.cross(b1_norm, v, dim=-1) * w, dim=-1)

    return torch.rad2deg(torch.atan2(y, x))


# ==============================================================================
# 6. TorchMetrics Base Metric Implementations
# ==============================================================================

class ConformerCoverage(Metric):
    """TorchMetrics implementation for Conformer Coverage (COV-R and COV-P) [D].

    Computes percentage of reference conformers covered by generated samples (Recall)
    and percentage of generated conformers matching true references (Precision)
    within a defined RMSD threshold.
    """

    full_state_update: bool = False

    def __init__(
        self,
        threshold: float = DEFAULT_COV_THRESHOLD,
        align: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.threshold = threshold
        self.align = align

        self.add_state("total_ref_covered", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_ref_count", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_pred_covered", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_pred_count", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        ref_conformers: Union[torch.Tensor, Sequence[torch.Tensor]],
        pred_conformers: Union[torch.Tensor, Sequence[torch.Tensor]],
    ) -> None:
        """Update coverage statistics with conformer ensembles.

        Parameters
        ----------
        ref_conformers : Union[torch.Tensor, Sequence[torch.Tensor]]
            Tensor of shape (M, N, 3) or list of ensemble tensors.
        pred_conformers : Union[torch.Tensor, Sequence[torch.Tensor]]
            Tensor of shape (K, N, 3) or list of ensemble tensors.
        """
        if isinstance(ref_conformers, torch.Tensor) and ref_conformers.dim() == 3:
            ref_list = [ref_conformers]
            pred_list = [pred_conformers]  # type: ignore
        else:
            ref_list = list(ref_conformers)  # type: ignore
            pred_list = list(pred_conformers)  # type: ignore

        for refs, preds in zip(ref_list, pred_list):
            dist_mat = pairwise_conformer_rmsd(refs, preds, align=self.align)
            min_ref = torch.min(dist_mat, dim=1).values
            min_pred = torch.min(dist_mat, dim=0).values

            self.total_ref_covered += torch.sum(min_ref <= self.threshold).float()
            self.total_ref_count += float(dist_mat.shape[0])
            self.total_pred_covered += torch.sum(min_pred <= self.threshold).float()
            self.total_pred_count += float(dist_mat.shape[1])

    def compute(self) -> Dict[str, torch.Tensor]:
        """Compute Conformer Coverage Recall and Precision percentages [D]."""
        cov_recall = (
            (self.total_ref_covered / (self.total_ref_count + 1e-12)) * 100.0
            if self.total_ref_count > 0
            else torch.tensor(0.0)
        )
        cov_precision = (
            (self.total_pred_covered / (self.total_pred_count + 1e-12)) * 100.0
            if self.total_pred_count > 0
            else torch.tensor(0.0)
        )
        return {
            "cov_recall": cov_recall,
            "cov_precision": cov_precision,
        }


class AverageMinimumRMSD(Metric):
    """TorchMetrics implementation for Average Minimum RMSD (AMR-R and AMR-P) [D]."""

    full_state_update: bool = False

    def __init__(
        self,
        align: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.align = align

        self.add_state("sum_min_rmsd_ref", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_ref_count", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("sum_min_rmsd_pred", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_pred_count", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        ref_conformers: Union[torch.Tensor, Sequence[torch.Tensor]],
        pred_conformers: Union[torch.Tensor, Sequence[torch.Tensor]],
    ) -> None:
        """Update AMR statistics with conformer ensembles."""
        if isinstance(ref_conformers, torch.Tensor) and ref_conformers.dim() == 3:
            ref_list = [ref_conformers]
            pred_list = [pred_conformers]  # type: ignore
        else:
            ref_list = list(ref_conformers)  # type: ignore
            pred_list = list(pred_conformers)  # type: ignore

        for refs, preds in zip(ref_list, pred_list):
            dist_mat = pairwise_conformer_rmsd(refs, preds, align=self.align)
            min_ref = torch.min(dist_mat, dim=1).values
            min_pred = torch.min(dist_mat, dim=0).values

            self.sum_min_rmsd_ref += torch.sum(min_ref)
            self.total_ref_count += float(dist_mat.shape[0])
            self.sum_min_rmsd_pred += torch.sum(min_pred)
            self.total_pred_count += float(dist_mat.shape[1])

    def compute(self) -> Dict[str, torch.Tensor]:
        """Compute AMR Recall and Precision in Angstroms [D]."""
        amr_recall = (
            self.sum_min_rmsd_ref / (self.total_ref_count + 1e-12)
            if self.total_ref_count > 0
            else torch.tensor(0.0)
        )
        amr_precision = (
            self.sum_min_rmsd_pred / (self.total_pred_count + 1e-12)
            if self.total_pred_count > 0
            else torch.tensor(0.0)
        )
        return {
            "amr_recall": amr_recall,
            "amr_precision": amr_precision,
        }


class EnergyMAE(Metric):
    """TorchMetrics implementation for Mean Absolute Error in molecular energies [D]."""

    full_state_update: bool = False

    def __init__(
        self,
        target_unit: str = "ev",
        input_unit: str = "ev",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.target_unit = target_unit
        self.input_unit = input_unit

        self.add_state("sum_abs_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_samples", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_energies: torch.Tensor,
        target_energies: torch.Tensor,
    ) -> None:
        """Update energy MAE accumulator."""
        pred = convert_energy(pred_energies.view(-1), from_unit=self.input_unit, to_unit=self.target_unit)
        target = convert_energy(target_energies.view(-1), from_unit=self.input_unit, to_unit=self.target_unit)
        error = torch.abs(pred - target)
        self.sum_abs_error += torch.sum(error)
        self.total_samples += float(error.numel())

    def compute(self) -> torch.Tensor:
        """Compute energy MAE in target units [D]."""
        return self.sum_abs_error / (self.total_samples + 1e-12)


class RelativeEnergyMAE(Metric):
    """TorchMetrics implementation for relative conformer energy ranking MAE [D].

    Computes MAE of relative energy differences (Delta E = E - min(E)) for conformer ensembles.
    """

    full_state_update: bool = False

    def __init__(
        self,
        target_unit: str = "ev",
        input_unit: str = "ev",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.target_unit = target_unit
        self.input_unit = input_unit

        self.add_state("sum_rel_abs_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_samples", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_energies: torch.Tensor,
        target_energies: torch.Tensor,
    ) -> None:
        """Update relative energy MAE."""
        pred = convert_energy(pred_energies.view(-1), from_unit=self.input_unit, to_unit=self.target_unit)
        target = convert_energy(target_energies.view(-1), from_unit=self.input_unit, to_unit=self.target_unit)

        rel_pred = pred - torch.min(pred)
        rel_target = target - torch.min(target)

        error = torch.abs(rel_pred - rel_target)
        self.sum_rel_abs_error += torch.sum(error)
        self.total_samples += float(error.numel())

    def compute(self) -> torch.Tensor:
        """Compute relative energy MAE [D]."""
        return self.sum_rel_abs_error / (self.total_samples + 1e-12)


class BoltzmannWeightedEnergyMAE(Metric):
    """TorchMetrics implementation for Boltzmann-weighted energy MAE [D].

    Weights conformers by their equilibrium Boltzmann distribution at temperature T.
    """

    full_state_update: bool = False

    def __init__(
        self,
        temperature_k: float = DEFAULT_TEMPERATURE_K,
        target_unit: str = "ev",
        input_unit: str = "ev",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.temperature_k = temperature_k
        self.target_unit = target_unit
        self.input_unit = input_unit

        self.add_state("sum_weighted_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_ensembles", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_energies: torch.Tensor,
        target_energies: torch.Tensor,
    ) -> None:
        """Update Boltzmann-weighted energy error."""
        # Convert target and pred to eV for Boltzmann factor calculation (kB * T in eV)
        pred_ev = convert_energy(pred_energies.view(-1), from_unit=self.input_unit, to_unit="ev")
        target_ev = convert_energy(target_energies.view(-1), from_unit=self.input_unit, to_unit="ev")

        kb_t_ev = BOLTZMANN_CONSTANT_EV_K * self.temperature_k
        rel_target_ev = target_ev - torch.min(target_ev)
        boltzmann_weights = torch.softmax(-rel_target_ev / kb_t_ev, dim=0)

        # Evaluate absolute error in target units
        pred_target_u = convert_energy(pred_ev, from_unit="ev", to_unit=self.target_unit)
        target_target_u = convert_energy(target_ev, from_unit="ev", to_unit=self.target_unit)
        abs_err = torch.abs(pred_target_u - target_target_u)

        weighted_err = torch.sum(boltzmann_weights * abs_err)
        self.sum_weighted_error += weighted_err
        self.total_ensembles += 1.0

    def compute(self) -> torch.Tensor:
        """Compute average Boltzmann-weighted energy error [D]."""
        return self.sum_weighted_error / (self.total_ensembles + 1e-12)


class ForceMAE(Metric):
    """TorchMetrics implementation for component-wise and vector force MAE [D]."""

    full_state_update: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.add_state("sum_abs_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_components", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(self, pred_forces: torch.Tensor, true_forces: torch.Tensor) -> None:
        """Update force MAE."""
        diff = torch.abs(pred_forces - true_forces)
        self.sum_abs_error += torch.sum(diff)
        self.total_components += float(diff.numel())

    def compute(self) -> torch.Tensor:
        """Compute force MAE in eV/Angstrom [D]."""
        return self.sum_abs_error / (self.total_components + 1e-12)


class ForceRMSE(Metric):
    """TorchMetrics implementation for force Root-Mean-Square Error [D]."""

    full_state_update: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.add_state("sum_sq_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_components", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(self, pred_forces: torch.Tensor, true_forces: torch.Tensor) -> None:
        """Update force RMSE."""
        sq_diff = (pred_forces - true_forces) ** 2
        self.sum_sq_error += torch.sum(sq_diff)
        self.total_components += float(sq_diff.numel())

    def compute(self) -> torch.Tensor:
        """Compute force RMSE in eV/Angstrom [D]."""
        return torch.sqrt(self.sum_sq_error / (self.total_components + 1e-12))


class ForceCosineSimilarity(Metric):
    """TorchMetrics implementation for force vector cosine similarity [D]."""

    full_state_update: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.add_state("sum_cosine_sim", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_vectors", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(self, pred_forces: torch.Tensor, true_forces: torch.Tensor) -> None:
        """Update force cosine similarity."""
        p_norm = torch.norm(pred_forces, dim=-1, keepdim=True) + 1e-12
        t_norm = torch.norm(true_forces, dim=-1, keepdim=True) + 1e-12
        cos_sim = torch.sum((pred_forces / p_norm) * (true_forces / t_norm), dim=-1)
        self.sum_cosine_sim += torch.sum(cos_sim)
        self.total_vectors += float(cos_sim.numel())

    def compute(self) -> torch.Tensor:
        """Compute mean force direction cosine similarity in [-1, 1] [D]."""
        return self.sum_cosine_sim / (self.total_vectors + 1e-12)


class RotationalConstantsMAE(Metric):
    """TorchMetrics implementation for spectroscopic rotational constants MAE (A, B, C) [D]."""

    full_state_update: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.add_state("sum_abs_a", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("sum_abs_b", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("sum_abs_c", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_molecules", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_positions: torch.Tensor,
        target_positions: torch.Tensor,
        atomic_numbers: torch.Tensor,
    ) -> None:
        """Update rotational constants MAE."""
        _, pred_rot = compute_moments_of_inertia(pred_positions, atomic_numbers)
        _, target_rot = compute_moments_of_inertia(target_positions, atomic_numbers)

        err_a = torch.abs(pred_rot[..., 0] - target_rot[..., 0])
        err_b = torch.abs(pred_rot[..., 1] - target_rot[..., 1])
        err_c = torch.abs(pred_rot[..., 2] - target_rot[..., 2])

        self.sum_abs_a += torch.sum(err_a)
        self.sum_abs_b += torch.sum(err_b)
        self.sum_abs_c += torch.sum(err_c)
        self.total_molecules += float(err_a.numel())

    def compute(self) -> Dict[str, torch.Tensor]:
        """Compute rotational constants MAE in MHz [D]."""
        count = self.total_molecules + 1e-12
        mae_a = self.sum_abs_a / count
        mae_b = self.sum_abs_b / count
        mae_c = self.sum_abs_c / count
        mae_mean = (mae_a + mae_b + mae_c) / 3.0
        return {
            "mae_a_mhz": mae_a,
            "mae_b_mhz": mae_b,
            "mae_c_mhz": mae_c,
            "mae_mean_mhz": mae_mean,
        }


class InertialDefectMAE(Metric):
    """TorchMetrics implementation for planar inertial defect MAE [D]."""

    full_state_update: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.add_state("sum_abs_defect_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_molecules", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_positions: torch.Tensor,
        target_positions: torch.Tensor,
        atomic_numbers: torch.Tensor,
    ) -> None:
        """Update planar inertial defect error."""
        pred_defect = compute_inertial_defect(pred_positions, atomic_numbers)
        target_defect = compute_inertial_defect(target_positions, atomic_numbers)
        err = torch.abs(pred_defect - target_defect)
        self.sum_abs_defect_error += torch.sum(err)
        self.total_molecules += float(err.numel())

    def compute(self) -> torch.Tensor:
        """Compute inertial defect MAE in u * Angstrom^2 [D]."""
        return self.sum_abs_defect_error / (self.total_molecules + 1e-12)


class InternalCoordinatesMAE(Metric):
    """TorchMetrics implementation for bond lengths, bond angles, and dihedrals MAE [D]."""

    full_state_update: bool = False

    def __init__(
        self,
        bonds: Optional[torch.Tensor] = None,
        angles: Optional[torch.Tensor] = None,
        dihedrals: Optional[torch.Tensor] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.bonds = bonds
        self.angles = angles
        self.dihedrals = dihedrals

        self.add_state("sum_bond_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_bonds", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("sum_angle_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_angles", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("sum_dihedral_error", default=torch.tensor(0.0), dist_reduce_fx="sum")
        self.add_state("total_dihedrals", default=torch.tensor(0.0), dist_reduce_fx="sum")

    def update(
        self,
        pred_positions: torch.Tensor,
        target_positions: torch.Tensor,
        bonds: Optional[torch.Tensor] = None,
        angles: Optional[torch.Tensor] = None,
        dihedrals: Optional[torch.Tensor] = None,
    ) -> None:
        """Update internal coordinate errors."""
        active_bonds = bonds if bonds is not None else self.bonds
        active_angles = angles if angles is not None else self.angles
        active_dihedrals = dihedrals if dihedrals is not None else self.dihedrals

        if active_bonds is not None and active_bonds.numel() > 0:
            pred_b = compute_bond_lengths(pred_positions, active_bonds)
            true_b = compute_bond_lengths(target_positions, active_bonds)
            err_b = torch.abs(pred_b - true_b)
            self.sum_bond_error += torch.sum(err_b)
            self.total_bonds += float(err_b.numel())

        if active_angles is not None and active_angles.numel() > 0:
            pred_a = compute_bond_angles(pred_positions, active_angles)
            true_a = compute_bond_angles(target_positions, active_angles)
            err_a = torch.abs(pred_a - true_a)
            self.sum_angle_error += torch.sum(err_a)
            self.total_angles += float(err_a.numel())

        if active_dihedrals is not None and active_dihedrals.numel() > 0:
            pred_d = compute_dihedral_angles(pred_positions, active_dihedrals)
            true_d = compute_dihedral_angles(target_positions, active_dihedrals)
            # Periodic angular difference in [-180, 180]
            diff_d = torch.remainder(pred_d - true_d + 180.0, 360.0) - 180.0
            err_d = torch.abs(diff_d)
            self.sum_dihedral_error += torch.sum(err_d)
            self.total_dihedrals += float(err_d.numel())

    def compute(self) -> Dict[str, torch.Tensor]:
        """Compute internal coordinates MAE dictionary [D]."""
        res: Dict[str, torch.Tensor] = {}
        if self.total_bonds > 0:
            res["mae_bonds_angstrom"] = self.sum_bond_error / self.total_bonds
        if self.total_angles > 0:
            res["mae_angles_deg"] = self.sum_angle_error / self.total_angles
        if self.total_dihedrals > 0:
            res["mae_dihedrals_deg"] = self.sum_dihedral_error / self.total_dihedrals
        return res


class ConformerEnsembleEvaluator(Metric):
    """Comprehensive multi-metric evaluator for conformer generation models.

    Integrates COV-R, COV-P, AMR-R, AMR-P, Energy MAE, Relative Energy MAE,
    and Rotational Constants tracking into a unified evaluation harness.
    """

    full_state_update: bool = False

    def __init__(
        self,
        thresholds: Sequence[float] = (0.5, 1.25),
        temperature_k: float = DEFAULT_TEMPERATURE_K,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.thresholds = list(thresholds)
        self.temperature_k = temperature_k

        # Safe keys without dots for nn.ModuleDict
        self.cov_metrics = nn.ModuleDict(
            {f"cov_{t:.2f}".replace(".", "_"): ConformerCoverage(threshold=t) for t in self.thresholds}
        )
        self.amr_metric = AverageMinimumRMSD()
        self.energy_mae = EnergyMAE(target_unit="ev")
        self.rel_energy_mae = RelativeEnergyMAE(target_unit="ev")
        self.rotational_mae = RotationalConstantsMAE()

    def update(
        self,
        ref_positions: torch.Tensor,
        pred_positions: torch.Tensor,
        ref_energies: Optional[torch.Tensor] = None,
        pred_energies: Optional[torch.Tensor] = None,
        atomic_numbers: Optional[torch.Tensor] = None,
    ) -> None:
        """Update all component metrics with evaluation batch."""
        for metric in self.cov_metrics.values():
            metric.update(ref_positions, pred_positions)

        self.amr_metric.update(ref_positions, pred_positions)

        if ref_energies is not None and pred_energies is not None:
            self.energy_mae.update(pred_energies, ref_energies)
            self.rel_energy_mae.update(pred_energies, ref_energies)

        if atomic_numbers is not None and ref_positions.dim() >= 2 and pred_positions.dim() >= 2:
            self.rotational_mae.update(pred_positions, ref_positions, atomic_numbers)

    def compute(self) -> Dict[str, torch.Tensor]:
        """Compute unified summary dictionary across all evaluated metrics [D]."""
        results: Dict[str, torch.Tensor] = {}

        for name, metric in self.cov_metrics.items():
            cov_res = metric.compute()
            t_str = name.split("cov_")[-1].replace("_", ".")
            results[f"cov_recall_{t_str}"] = cov_res["cov_recall"]
            results[f"cov_precision_{t_str}"] = cov_res["cov_precision"]

        amr_res = self.amr_metric.compute()
        results["amr_recall"] = amr_res["amr_recall"]
        results["amr_precision"] = amr_res["amr_precision"]

        if self.energy_mae.total_samples > 0:
            results["energy_mae_ev"] = self.energy_mae.compute()
            results["rel_energy_mae_ev"] = self.rel_energy_mae.compute()

        if self.rotational_mae.total_molecules > 0:
            rot_res = self.rotational_mae.compute()
            results["rotational_mae_mhz"] = rot_res["mae_mean_mhz"]
            results["rotational_mae_a_mhz"] = rot_res["mae_a_mhz"]
            results["rotational_mae_b_mhz"] = rot_res["mae_b_mhz"]
            results["rotational_mae_c_mhz"] = rot_res["mae_c_mhz"]

        return results

    def reset(self) -> None:
        """Reset all child metrics."""
        super().reset()
        for metric in self.cov_metrics.values():
            metric.reset()
        self.amr_metric.reset()
        self.energy_mae.reset()
        self.rel_energy_mae.reset()
        self.rotational_mae.reset()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_eval_metrics.py ---
"""Exhaustive Zero-Mock Unit and Integration Test Suite for CoChem-GEOM Metrics.
================================================================================
Authoritative Standards:
- Method Matrix v4.1: Conformer Ensemble Metrics, Kabsch Alignment, Energy & Force Tracking
- TorchMetrics v1.0+: Modular Metric Interface with DDP State Reduction & Pure Tensor Ops
- Mendeleev Library Mandate: Dynamic atomic and monoisotopic mass validation (No hardcoding)
- SE(3) Equivariance & Invariance: Rigorous spatial transformation invariance & coordinate immutability
- State Immutability: Pure functional geometric transformations (pos_new = pos + shift)
- Provenance Tags: [M] Measured/Theoretical, [D] Derived/Calculated, [E] Expert Estimate
- Strict Zero-Mock Policy: 100% authentic physical tensor mathematics and real execution
"""

from __future__ import annotations

import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

from mendeleev import element
import numpy as np
import pytest
import torch
import torchmetrics

# ------------------------------------------------------------------------------
# Dynamic Path Configuration (Ensuring CoChem-BASE/src or CoChem-GEOM/src in sys.path)
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
GEOM_DIR_ENV = os.environ.get("COCHEM_GEOM_DIR")
if GEOM_DIR_ENV:
    GEOM_ROOT = Path(GEOM_DIR_ENV).resolve()
else:
    if (BASE_DIR / "src" / "cochem_geom").exists():
        GEOM_ROOT = BASE_DIR
    else:
        GEOM_ROOT = BASE_DIR.parent / "CoChem-GEOM"

GEOM_SRC = GEOM_ROOT / "src"
if str(GEOM_SRC) not in sys.path:
    sys.path.insert(0, str(GEOM_SRC))
if str(GEOM_ROOT) not in sys.path:
    sys.path.insert(0, str(GEOM_ROOT))

import cochem_geom.eval.metrics as metrics_mod
from cochem_geom.eval.metrics import (
    ATOMIC_MASS_UNIT_KG,
    BOLTZMANN_CONSTANT_EV_K,
    BOLTZMANN_CONSTANT_J_K,
    DEFAULT_AMR_THRESHOLD,
    DEFAULT_COV_THRESHOLD,
    DEFAULT_TEMPERATURE_K,
    EV_TO_CM_MINUS_ONE,
    EV_TO_HARTREE,
    EV_TO_KCAL_MOL,
    EV_TO_KJ_MOL,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    KCAL_MOL_TO_EV,
    KCAL_MOL_TO_HARTREE,
    PLANCK_CONSTANT_J_S,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SPEED_OF_LIGHT_M_S,
    STANDARD_TEMPERATURE_K,
    AverageMinimumRMSD,
    BoltzmannWeightedEnergyMAE,
    ConformerCoverage,
    ConformerEnsembleEvaluator,
    EnergyMAE,
    ForceCosineSimilarity,
    ForceMAE,
    ForceRMSE,
    InertialDefectMAE,
    InternalCoordinatesMAE,
    RelativeEnergyMAE,
    RotationalConstantsMAE,
    compute_average_minimum_rmsd,
    compute_bond_angles,
    compute_bond_lengths,
    compute_conformer_coverage,
    compute_dihedral_angles,
    compute_inertial_defect,
    compute_moments_of_inertia,
    compute_rmsd,
    convert_energy,
    get_atomic_mass,
    get_atomic_masses,
    get_monoisotopic_mass,
    kabsch_align,
    kabsch_rotation,
    pairwise_conformer_rmsd,
)


# ==============================================================================
# Fixtures: Real Molecular Coordinates & Structures
# ==============================================================================

@pytest.fixture
def water_molecule() -> Tuple[List[str], torch.Tensor, torch.Tensor]:
    """Real water (H2O) equilibrium geometry from spectroscopic benchmarks [M]."""
    symbols = ["O", "H", "H"]
    z = torch.tensor([8, 1, 1], dtype=torch.long)
    # C2v equilibrium structure in Angstroms: r_OH = 0.9575 A, angle HOH = 104.51 deg
    theta = math.radians(104.51 / 2.0)
    r_oh = 0.9575
    pos = torch.tensor(
        [
            [0.0, 0.0, 0.0],
            [r_oh * math.sin(theta), 0.0, r_oh * math.cos(theta)],
            [-r_oh * math.sin(theta), 0.0, r_oh * math.cos(theta)],
        ],
        dtype=torch.float32,
    )
    return symbols, z, pos


@pytest.fixture
def methane_molecule() -> Tuple[List[str], torch.Tensor, torch.Tensor]:
    """Real methane (CH4) tetrahedral equilibrium geometry [M]."""
    symbols = ["C", "H", "H", "H", "H"]
    z = torch.tensor([6, 1, 1, 1, 1], dtype=torch.long)
    r_ch = 1.087
    a = r_ch / math.sqrt(3.0)
    pos = torch.tensor(
        [
            [0.0, 0.0, 0.0],
            [a, a, a],
            [a, -a, -a],
            [-a, a, -a],
            [-a, -a, a],
        ],
        dtype=torch.float32,
    )
    return symbols, z, pos


@pytest.fixture
def ethanol_conformers() -> Tuple[torch.Tensor, torch.Tensor]:
    """Real ethanol (C2H5OH) trans and gauche conformer geometries [M]."""
    # 9 atoms: C, C, O, H, H, H, H, H, H
    # Trans conformer
    trans_pos = torch.tensor(
        [
            [0.000, 0.000, 0.000],  # C1
            [1.500, 0.000, 0.000],  # C2
            [2.050, 1.300, 0.000],  # O
            [3.010, 1.250, 0.000],  # H (hydroxyl)
            [-0.370, 0.510, 0.890],  # H
            [-0.370, 0.510, -0.890],  # H
            [-0.370, -1.030, 0.000],  # H
            [1.870, -0.510, 0.890],  # H
            [1.870, -0.510, -0.890],  # H
        ],
        dtype=torch.float32,
    )
    # Gauche conformer (rotated hydroxyl dihedral by ~120 degrees)
    gauche_pos = trans_pos.clone()
    gauche_pos[3] = torch.tensor([2.050 + 0.96 * math.cos(math.radians(105)), 1.300 + 0.96 * math.sin(math.radians(105)) * math.cos(math.radians(120)), 0.96 * math.sin(math.radians(105)) * math.sin(math.radians(120))], dtype=torch.float32)
    return trans_pos, gauche_pos


# ==============================================================================
# 1. Fundamental Physical Constants & Conversion Factors Tests
# ==============================================================================

class TestFundamentalPhysicalConstants:
    """Validates CODATA 2018/2022 constants and energy conversion precision."""

    def test_codata_constants_and_provenance(self) -> None:
        """Validate CODATA exact and measured constants."""
        assert SPEED_OF_LIGHT_M_S == 299792458.0  # [M]
        assert math.isclose(PLANCK_CONSTANT_J_S, 6.62607015e-34, rel_tol=1e-12)  # [M]
        assert math.isclose(BOLTZMANN_CONSTANT_J_K, 1.380649e-23, rel_tol=1e-12)  # [M]
        assert math.isclose(STANDARD_TEMPERATURE_K, 298.15, rel_tol=1e-12)  # [M]
        assert math.isclose(DEFAULT_TEMPERATURE_K, 298.15, rel_tol=1e-12)  # [M]
        assert math.isclose(BOLTZMANN_CONSTANT_EV_K, 8.617333262145e-5, rel_tol=1e-9)  # [D]
        assert math.isclose(ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ, 505379.008784, rel_tol=1e-6)  # [D]
        assert DEFAULT_COV_THRESHOLD == 0.5  # [E]
        assert DEFAULT_AMR_THRESHOLD == 0.5  # [E]

    def test_energy_conversions(self) -> None:
        """Validate precision and invertibility of energy unit conversions."""
        val_ev = 1.5
        val_hartree = convert_energy(val_ev, from_unit="ev", to_unit="hartree")
        assert math.isclose(val_hartree, val_ev * EV_TO_HARTREE, rel_tol=1e-9)

        val_kcal = convert_energy(val_hartree, from_unit="hartree", to_unit="kcal_mol")
        assert math.isclose(val_kcal, val_hartree * HARTREE_TO_KCAL_MOL, rel_tol=1e-9)

        val_kj = convert_energy(val_hartree, from_unit="hartree", to_unit="kj_mol")
        assert math.isclose(val_kj, val_hartree * HARTREE_TO_KJ_MOL, rel_tol=1e-9)

        # Invertibility back to eV
        val_ev_rec = convert_energy(val_kcal, from_unit="kcal_mol", to_unit="ev")
        assert math.isclose(val_ev, val_ev_rec, rel_tol=1e-6)


# ==============================================================================
# 2. Dynamic Mendeleev Mass Resolution Tests
# ==============================================================================

class TestDynamicMendeleevMasses:
    """Enforces the Mendeleev Library Mandate: dynamic property lookup without hardcoding."""

    def test_dynamic_atomic_masses_lookup(self) -> None:
        """Verify dynamic mass lookup via Mendeleev."""
        for sym in ["H", "C", "N", "O", "F", "P", "S", "Cl"]:
            m_expected = float(element(sym).atomic_weight)
            assert math.isclose(get_atomic_mass(sym), m_expected, rel_tol=1e-9)
            z = int(element(sym).atomic_number)
            assert math.isclose(get_atomic_mass(z), m_expected, rel_tol=1e-9)

    def test_tensor_masses_resolution(self) -> None:
        """Verify dynamic mass resolution for a 1D tensor of atomic numbers."""
        z_tensor = torch.tensor([1, 6, 7, 8, 16], dtype=torch.long)
        masses = get_atomic_masses(z_tensor)
        assert masses.shape == (5,)
        assert math.isclose(masses[0].item(), float(element("H").atomic_weight), rel_tol=1e-6)
        assert math.isclose(masses[1].item(), float(element("C").atomic_weight), rel_tol=1e-6)
        assert math.isclose(masses[2].item(), float(element("N").atomic_weight), rel_tol=1e-6)
        assert math.isclose(masses[3].item(), float(element("O").atomic_weight), rel_tol=1e-6)
        assert math.isclose(masses[4].item(), float(element("S").atomic_weight), rel_tol=1e-6)


# ==============================================================================
# 3. Pure Functional Kabsch Algorithm & SE(3) Invariance Tests
# ==============================================================================

class TestKabschAlgorithmAndRMSD:
    """Tests for pure functional Kabsch alignment and RMSD calculations."""

    def test_identical_structures_rmsd_zero(self, water_molecule: Any) -> None:
        """Identical coordinates must yield exact zero RMSD and identity rotation."""
        _, _, pos = water_molecule
        rmsd = compute_rmsd(pos, pos, align=True)
        assert math.isclose(rmsd.item(), 0.0, abs_tol=1e-6)

        aligned_pos, R, t, aligned_rmsd = kabsch_align(pos, pos)
        assert math.isclose(aligned_rmsd.item(), 0.0, abs_tol=1e-6)
        assert torch.allclose(R, torch.eye(3), atol=1e-5)
        assert torch.allclose(aligned_pos, pos, atol=1e-5)

    def test_translation_and_rotation_invariance(self, methane_molecule: Any) -> None:
        """Kabsch alignment must recover exact zero RMSD under arbitrary SE(3) translation and rotation."""
        _, _, pos = methane_molecule

        # Arbitrary rotation matrix via Rodrigues rotation around axis [1, 1, 1] by 45 deg
        axis = torch.tensor([1.0, 1.0, 1.0])
        axis = axis / torch.norm(axis)
        angle = math.radians(45.0)
        K = torch.tensor(
            [
                [0.0, -axis[2], axis[1]],
                [axis[2], 0.0, -axis[0]],
                [-axis[1], axis[0], 0.0],
            ],
            dtype=torch.float32,
        )
        R_true = torch.eye(3) + math.sin(angle) * K + (1.0 - math.cos(angle)) * (K @ K)
        t_true = torch.tensor([12.5, -8.3, 4.1], dtype=torch.float32)

        # Transformed coordinates (pure immutable operation)
        pos_transformed = (pos @ R_true.T) + t_true.view(1, 3)

        # Unaligned RMSD must be large
        unaligned_rmsd = compute_rmsd(pos, pos_transformed, align=False)
        assert unaligned_rmsd.item() > 5.0

        # Aligned RMSD must be 0.0
        aligned_rmsd = compute_rmsd(pos, pos_transformed, align=True)
        assert math.isclose(aligned_rmsd.item(), 0.0, abs_tol=1e-5)

        # Reconstructed aligned position must match reference
        aligned_pos, R_est, t_est, r_val = kabsch_align(pos, pos_transformed)
        assert math.isclose(r_val.item(), 0.0, abs_tol=1e-5)
        assert torch.allclose(aligned_pos, pos, atol=1e-4)

    def test_state_immutability(self, water_molecule: Any) -> None:
        """Verify inputs are never mutated in place during alignment."""
        _, _, pos = water_molecule
        pos_orig = pos.clone()
        shift = torch.tensor([1.0, 2.0, 3.0])
        pos_shifted = pos + shift

        _ = kabsch_align(pos, pos_shifted)
        assert torch.equal(pos, pos_orig), "Original tensor was mutated in place!"

    def test_reflection_correction(self) -> None:
        """Ensure Kabsch handles reflection and does not return improper rotations (det(R) must be +1)."""
        pos = torch.tensor(
            [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
                [0.5, 0.5, 0.5],
            ],
            dtype=torch.float32,
        )
        # Reflected coordinate system (inversion)
        pos_reflected = -pos

        aligned_pos, R, t, rmsd = kabsch_align(pos, pos_reflected)
        det_R = torch.det(R).item()
        assert math.isclose(det_R, 1.0, abs_tol=1e-5), f"Rotation matrix has improper determinant: {det_R}"


# ==============================================================================
# 4. Pairwise Conformer Ensemble & Coverage Metrics
# ==============================================================================

class TestConformerEnsembleMetrics:
    """Tests for Conformer Coverage (COV) and Average Minimum RMSD (AMR)."""

    def test_pairwise_rmsd_matrix(self, ethanol_conformers: Any) -> None:
        """Verify pairwise RMSD matrix shape and values."""
        trans_pos, gauche_pos = ethanol_conformers
        refs = torch.stack([trans_pos, gauche_pos], dim=0)  # Shape [2, 9, 3]
        preds = torch.stack([trans_pos, gauche_pos], dim=0)  # Shape [2, 9, 3]

        rmsd_mat = pairwise_conformer_rmsd(refs, preds, align=True)
        assert rmsd_mat.shape == (2, 2)
        assert math.isclose(rmsd_mat[0, 0].item(), 0.0, abs_tol=1e-5)
        assert math.isclose(rmsd_mat[1, 1].item(), 0.0, abs_tol=1e-5)
        assert rmsd_mat[0, 1].item() > 0.1  # Trans vs gauche difference

    def test_conformer_coverage_functional(self, ethanol_conformers: Any) -> None:
        """Verify functional compute_conformer_coverage."""
        trans_pos, gauche_pos = ethanol_conformers
        refs = torch.stack([trans_pos, gauche_pos], dim=0)  # [2, 9, 3]
        # Only trans is predicted
        preds = trans_pos.unsqueeze(0)  # [1, 9, 3]

        # At tight threshold 0.1 A, only 1 of 2 refs is covered (50% recall, 100% precision)
        cov_r, cov_p = compute_conformer_coverage(refs, preds, threshold=0.1, align=True)
        assert math.isclose(cov_r.item(), 50.0, abs_tol=1e-4)
        assert math.isclose(cov_p.item(), 100.0, abs_tol=1e-4)

    def test_average_minimum_rmsd_functional(self, ethanol_conformers: Any) -> None:
        """Verify functional compute_average_minimum_rmsd."""
        trans_pos, gauche_pos = ethanol_conformers
        refs = torch.stack([trans_pos, gauche_pos], dim=0)
        preds = torch.stack([trans_pos, gauche_pos], dim=0)

        amr_r, amr_p = compute_average_minimum_rmsd(refs, preds, align=True)
        assert math.isclose(amr_r.item(), 0.0, abs_tol=1e-5)
        assert math.isclose(amr_p.item(), 0.0, abs_tol=1e-5)


# ==============================================================================
# 5. TorchMetrics Class Implementations & DDP Lifecycles
# ==============================================================================

class TestTorchMetricsClasses:
    """Validates TorchMetrics Metric subclasses for conformer generation."""

    def test_conformer_coverage_metric(self, ethanol_conformers: Any) -> None:
        """Test ConformerCoverage TorchMetrics lifecycle (update, compute, reset)."""
        trans_pos, gauche_pos = ethanol_conformers
        refs = torch.stack([trans_pos, gauche_pos], dim=0)
        preds = torch.stack([trans_pos, gauche_pos], dim=0)

        metric = ConformerCoverage(threshold=0.5)
        metric.update(refs, preds)
        res = metric.compute()

        assert "cov_recall" in res
        assert "cov_precision" in res
        assert math.isclose(res["cov_recall"].item(), 100.0, abs_tol=1e-4)
        assert math.isclose(res["cov_precision"].item(), 100.0, abs_tol=1e-4)

        # Reset verification
        metric.reset()
        assert metric.total_ref_count == 0
        assert metric.total_pred_count == 0

    def test_average_minimum_rmsd_metric(self, ethanol_conformers: Any) -> None:
        """Test AverageMinimumRMSD TorchMetrics lifecycle."""
        trans_pos, gauche_pos = ethanol_conformers
        refs = torch.stack([trans_pos, gauche_pos], dim=0)
        preds = torch.stack([trans_pos, gauche_pos], dim=0)

        metric = AverageMinimumRMSD()
        metric.update(refs, preds)
        res = metric.compute()

        assert "amr_recall" in res
        assert "amr_precision" in res
        assert math.isclose(res["amr_recall"].item(), 0.0, abs_tol=1e-5)
        assert math.isclose(res["amr_precision"].item(), 0.0, abs_tol=1e-5)

    def test_energy_mae_metric(self) -> None:
        """Test EnergyMAE metric with unit conversion."""
        pred_e = torch.tensor([10.0, 20.0, 30.0], dtype=torch.float32)  # in eV
        true_e = torch.tensor([10.5, 19.5, 31.0], dtype=torch.float32)  # in eV
        # Errors in eV: [0.5, 0.5, 1.0] -> Mean = 0.666667 eV

        metric = EnergyMAE(target_unit="ev", input_unit="ev")
        metric.update(pred_e, true_e)
        mae_ev = metric.compute()
        assert math.isclose(mae_ev.item(), 2.0 / 3.0, rel_tol=1e-5)

        # Unit conversion to kcal/mol
        metric_kcal = EnergyMAE(target_unit="kcal_mol", input_unit="ev")
        metric_kcal.update(pred_e, true_e)
        mae_kcal = metric_kcal.compute()
        assert math.isclose(mae_kcal.item(), (2.0 / 3.0) * EV_TO_KCAL_MOL, rel_tol=1e-5)

    def test_relative_energy_mae_metric(self) -> None:
        """Test RelativeEnergyMAE for conformer energy ranking."""
        # 3 conformers: True = [0.0, 2.0, 5.0] eV, Pred = [0.1, 2.2, 4.8] eV
        # Relative True = [0.0, 2.0, 5.0] eV
        # Relative Pred = [0.0, 2.1, 4.7] eV
        # Rel Errors = [0.0, 0.1, 0.3] -> Mean = 0.4 / 3 = 0.133333 eV
        pred_e = torch.tensor([0.1, 2.2, 4.8], dtype=torch.float32)
        true_e = torch.tensor([0.0, 2.0, 5.0], dtype=torch.float32)

        metric = RelativeEnergyMAE(target_unit="ev")
        metric.update(pred_e, true_e)
        rel_mae = metric.compute()
        assert math.isclose(rel_mae.item(), 0.4 / 3.0, rel_tol=1e-5)

    def test_boltzmann_weighted_energy_mae(self) -> None:
        """Test Boltzmann-weighted energy error at 298.15 K."""
        pred_e = torch.tensor([0.0, 1.0], dtype=torch.float32)  # eV
        true_e = torch.tensor([0.0, 1.0], dtype=torch.float32)  # eV
        metric = BoltzmannWeightedEnergyMAE(temperature_k=298.15)
        metric.update(pred_e, true_e)
        assert math.isclose(metric.compute().item(), 0.0, abs_tol=1e-6)

    def test_force_metrics(self) -> None:
        """Test ForceMAE, ForceRMSE, and ForceCosineSimilarity."""
        pred_f = torch.tensor([[1.0, 0.0, 0.0], [0.0, 2.0, 0.0]], dtype=torch.float32)
        true_f = torch.tensor([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=torch.float32)

        mae_metric = ForceMAE()
        mae_metric.update(pred_f, true_f)
        # Component errors: [0, 0, 0] and [0, 1, 0] -> sum = 1.0 / 6 = 0.166667
        assert math.isclose(mae_metric.compute().item(), 1.0 / 6.0, rel_tol=1e-5)

        cos_metric = ForceCosineSimilarity()
        cos_metric.update(pred_f, true_f)
        # Cosine sims: 1.0 and 1.0 -> Mean = 1.0
        assert math.isclose(cos_metric.compute().item(), 1.0, rel_tol=1e-5)


# ==============================================================================
# 6. Rotational Constants & Spectroscopic Observables
# ==============================================================================

class TestRotationalObservables:
    """Validates principal moments of inertia and rotational constants (A, B, C)."""

    def test_water_moments_and_rotational_constants(self, water_molecule: Any) -> None:
        """Validate moments of inertia and rotational constants for H2O."""
        _, z, pos = water_molecule
        moments, rot_consts = compute_moments_of_inertia(pos, z)
        # Check sorting: I_a <= I_b <= I_c and A >= B >= C
        assert moments[0] <= moments[1] <= moments[2]
        assert rot_consts[0] >= rot_consts[1] >= rot_consts[2]

        # For planar molecule, planar inertial defect Delta I = I_c - I_a - I_b ~ 0.0 (rigid rotor)
        defect = compute_inertial_defect(pos, z)
        assert math.isclose(defect.item(), 0.0, abs_tol=1e-4)

    def test_rotational_constants_mae_metric(self, water_molecule: Any) -> None:
        """Validate RotationalConstantsMAE and InertialDefectMAE."""
        _, z, pos = water_molecule
        metric = RotationalConstantsMAE()
        metric.update(pos, pos, z)
        res = metric.compute()
        assert math.isclose(res["mae_a_mhz"].item(), 0.0, abs_tol=1e-4)
        assert math.isclose(res["mae_b_mhz"].item(), 0.0, abs_tol=1e-4)
        assert math.isclose(res["mae_c_mhz"].item(), 0.0, abs_tol=1e-4)

        defect_metric = InertialDefectMAE()
        defect_metric.update(pos, pos, z)
        assert math.isclose(defect_metric.compute().item(), 0.0, abs_tol=1e-5)


# ==============================================================================
# 7. Internal Coordinates (Bonds, Angles, Dihedrals)
# ==============================================================================

class TestInternalCoordinates:
    """Validates bond lengths, bond angles, and dihedral angles calculation."""

    def test_water_bond_length_and_angle(self, water_molecule: Any) -> None:
        """Verify bond lengths and bond angle for H2O."""
        _, _, pos = water_molecule
        bonds = torch.tensor([[0, 1], [0, 2]], dtype=torch.long)
        angles = torch.tensor([[1, 0, 2]], dtype=torch.long)

        lengths = compute_bond_lengths(pos, bonds)
        assert math.isclose(lengths[0].item(), 0.9575, rel_tol=1e-4)
        assert math.isclose(lengths[1].item(), 0.9575, rel_tol=1e-4)

        deg = compute_bond_angles(pos, angles)
        assert math.isclose(deg[0].item(), 104.51, rel_tol=1e-3)

    def test_internal_coordinates_mae_metric(self, water_molecule: Any) -> None:
        """Verify InternalCoordinatesMAE metric lifecycle."""
        _, _, pos = water_molecule
        bonds = torch.tensor([[0, 1], [0, 2]], dtype=torch.long)
        angles = torch.tensor([[1, 0, 2]], dtype=torch.long)

        metric = InternalCoordinatesMAE(bonds=bonds, angles=angles)
        metric.update(pos, pos)
        res = metric.compute()

        assert math.isclose(res["mae_bonds_angstrom"].item(), 0.0, abs_tol=1e-5)
        assert math.isclose(res["mae_angles_deg"].item(), 0.0, abs_tol=1e-4)


# ==============================================================================
# 8. Composite Conformer Ensemble Evaluator
# ==============================================================================

class TestCompositeConformerEnsembleEvaluator:
    """Tests the unified ConformerEnsembleEvaluator multi-metric suite."""

    def test_evaluator_lifecycle(self, ethanol_conformers: Any) -> None:
        """Verify multi-metric update and unified summary generation."""
        trans_pos, gauche_pos = ethanol_conformers
        refs = torch.stack([trans_pos, gauche_pos], dim=0)
        preds = torch.stack([trans_pos, gauche_pos], dim=0)
        ref_e = torch.tensor([0.0, 0.043], dtype=torch.float32)  # in eV
        pred_e = torch.tensor([0.0, 0.043], dtype=torch.float32)  # in eV
        z = torch.tensor([6, 6, 8, 1, 1, 1, 1, 1, 1], dtype=torch.long)

        evaluator = ConformerEnsembleEvaluator(thresholds=(0.5, 1.25))
        evaluator.update(
            ref_positions=refs,
            pred_positions=preds,
            ref_energies=ref_e,
            pred_energies=pred_e,
            atomic_numbers=z,
        )
        summary = evaluator.compute()

        assert "cov_recall_0.50" in summary
        assert "cov_precision_0.50" in summary
        assert "amr_recall" in summary
        assert "amr_precision" in summary
        assert "energy_mae_ev" in summary
        assert "rel_energy_mae_ev" in summary
        assert "rotational_mae_mhz" in summary

        assert math.isclose(summary["cov_recall_0.50"].item(), 100.0, abs_tol=1e-4)
        assert math.isclose(summary["amr_recall"].item(), 0.0, abs_tol=1e-5)
        assert math.isclose(summary["energy_mae_ev"].item(), 0.0, abs_tol=1e-5)

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.