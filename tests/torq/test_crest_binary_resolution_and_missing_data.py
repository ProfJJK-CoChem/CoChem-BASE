"""CoChem-TORQ: Test CREST Binary Discovery and Explicit Dependency Failure Gate.

Compliant with Method Matrix v4 §9B, Anti-Spoofing Protocol v2, and Zero-Mock Mandate.
Verifies Deliverable 1:
1. Purging of synthetic conformer displacements and fabricated energies.
2. Dynamic OS-agnostic binary resolution via BinaryRegistry.resolve("crest").
3. Raising of typed BinaryNotFoundError with tag '[MISSING DATA]' when crest is absent.
"""

import os
import sys
from pathlib import Path

import pytest
from cochem_base.environment import BinaryRegistry
from cochem_base.exceptions import BinaryNotFoundError, EcosystemDependencyError
from Libraries.cochem_torq_crest import CrestRunner, CrestConfig


def test_crest_runner_purges_fallback_methods():
    """Verify CrestRunner contains zero synthetic fallback generation methods."""
    runner = CrestRunner()
    # Confirm complete excision of synthetic fallback routines
    assert not hasattr(runner, "_generate_physical_fallback_ensemble")
    assert not hasattr(runner, "_fallback_conformer_ensemble")
    assert not hasattr(runner, "_generate_synthetic_ensemble")


def test_crest_binary_resolution_missing_data():
    """Verify BinaryRegistry.resolve('crest') raises BinaryNotFoundError with '[MISSING DATA]' when absent."""
    old_env = dict(os.environ)
    try:
        os.environ["PATH"] = ""
        os.environ.pop("COCHEM_CREST_BIN", None)
        os.environ.pop("CREST_BIN", None)
        os.environ.pop("CREST_PATH", None)

        with pytest.raises(BinaryNotFoundError) as exc_info:
            BinaryRegistry.resolve("crest")

        err_msg = str(exc_info.value)
        assert "[MISSING DATA]" in err_msg
        assert "CREST executable not discovered in environment path" in err_msg
        assert issubclass(BinaryNotFoundError, EcosystemDependencyError)
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def test_crest_binary_resolution_custom_override():
    """Verify BinaryRegistry.resolve('crest') resolves via COCHEM_CREST_BIN override."""
    old_env = dict(os.environ)
    try:
        real_binary = Path(sys.executable).resolve()
        os.environ["COCHEM_CREST_BIN"] = str(real_binary)

        resolved = BinaryRegistry.resolve("crest")
        assert resolved == real_binary
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def test_crest_runner_aborts_cleanly_without_executable(tmp_path):
    """Verify CrestRunner.run_crest halts cleanly with BinaryNotFoundError when executable is missing."""
    old_env = dict(os.environ)
    try:
        os.environ["PATH"] = ""
        os.environ.pop("COCHEM_CREST_BIN", None)
        os.environ.pop("CREST_BIN", None)
        os.environ.pop("CREST_PATH", None)

        # Authentic water molecule geometry
        water_xyz = tmp_path / "water.xyz"
        water_xyz.write_text(
            "3\nWater molecule\n"
            "O   0.000000   0.000000   0.117720\n"
            "H   0.000000   0.755453  -0.470880\n"
            "H   0.000000  -0.755453  -0.470880\n",
            encoding="utf-8",
        )

        runner = CrestRunner()
        with pytest.raises(BinaryNotFoundError) as exc_info:
            runner.run_crest(water_xyz, work_dir=tmp_path / "run")

        assert "[MISSING DATA]" in str(exc_info.value)
    finally:
        os.environ.clear()
        os.environ.update(old_env)

