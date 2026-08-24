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
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

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
