"""Real small CPU calculations proving both directions of the MLFF fallback."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

from cochem_base.cochem_core_registry_schema import CoChemSystemConfig
from cochem_base.core_engine.cochem_temporal_router import JobSpec, execute_temporal_screening
from cochem_base.core_engine.mlff_fallback import ScreeningFallbackExhausted, execute_screening_with_fallback


SILOS = Path(os.environ.get("COCHEM_SILO_ROOT", "/workspace/cochem-silos"))
MACE_PYTHON = SILOS / "ml/bin/python"
GXTB = SILOS / "gxtb/xtb-6.7.1/bin/xtb"
MODEL = Path(os.environ.get("COCHEM_MACE_OFF24_CHECKPOINT", "/workspace/cochem-runtime/ml-models/mace/MACE-OFF24_medium.model"))
WATER = [[0., 0., 0.], [.7586, 0., .5043], [-.7586, 0., .5043]]


def _registry(directory: Path, backends: dict[str, Path]) -> Path:
    from cochem_base.config_loader import resolve_config_path
    from cochem_base.core_engine.execution_authority import authorize_engine_execution
    source = resolve_config_path(os.environ.get("COCHEM_ACCEPTANCE_REGISTRY"))
    config = CoChemSystemConfig.model_validate_json(source.read_text(encoding="utf-8"))
    for name, binary in backends.items():
        authorize_engine_execution(name, registry_path=source, executable=binary, cores=1)
    # A bounded policy selection retains genuine measured engine/silo evidence;
    # excluded backends exercise absence, never fabricated execution results.
    config.engines = {name: config.engines[name] for name in backends}
    config = CoChemSystemConfig.model_validate(config.model_dump())
    config.update_checksum()
    target = directory / "registry.json"
    target.write_text(config.model_dump_json(), encoding="utf-8")
    return target


@pytest.mark.skipif(not (MACE_PYTHON.is_file() and GXTB.is_file()), reason="Real isolated MACE Python and g-xTB required")
def test_missing_checkpoint_really_executes_gxtb_gradient(tmp_path):
    registry = _registry(tmp_path, {"mace": MACE_PYTHON, "gxtb": GXTB})
    result = execute_temporal_screening(JobSpec(n_atoms=3, symbols=["O", "H", "H"],
        method="MACE-OFF24m", task_type="gradient", n_cores=1), WATER,
        checkpoint=tmp_path / "missing.model", registry_path=registry, workdir=tmp_path)
    assert result["backend"] == "gxtb"
    assert result["attempts"][0]["error_type"] == "ScreeningBackendUnavailable"
    assert result["attempts"][1]["returncode"] == 0
    assert np.isfinite(result["energy_hartree"])
    gradient = np.asarray(result["gradient_hartree_per_bohr"])
    assert gradient.shape == (3, 3) and np.isfinite(gradient).all()
    np.testing.assert_allclose(gradient.sum(axis=0), 0., atol=1e-7)
    assert json.loads(Path(result["evidence_path"]).read_text()) == result["attempts"]


@pytest.mark.skipif(not (MACE_PYTHON.is_file() and MODEL.is_file()), reason="Real isolated OFF24 medium model required")
def test_missing_gxtb_really_executes_off24_medium_gradient(tmp_path):
    registry = _registry(tmp_path, {"mace": MACE_PYTHON})
    result = execute_screening_with_fallback(["O", "H", "H"], WATER, primary="g-xTB",
        checkpoint=MODEL, registry_path=registry, workdir=tmp_path)
    assert result["backend"] == "mace"
    assert result["attempts"][0]["status"] == "REJECTED"
    assert result["attempts"][1]["returncode"] == 0
    assert result["attempts"][1]["versions"]["mace-torch"]
    assert np.isfinite(result["energy_hartree"])
    gradient = np.asarray(result["gradient_hartree_per_bohr"])
    assert gradient.shape == (3, 3) and np.isfinite(gradient).all()
    np.testing.assert_allclose(gradient.sum(axis=0), 0., atol=1e-7)


def test_absent_backends_exhaust_without_any_result(tmp_path):
    registry = _registry(tmp_path, {})
    with pytest.raises(ScreeningFallbackExhausted) as failure:
        execute_screening_with_fallback(["O", "H", "H"], WATER, registry_path=registry, workdir=tmp_path)
    assert len(failure.value.attempts) == 2
    assert all(attempt["status"] == "REJECTED" for attempt in failure.value.attempts)
    assert all("energy_hartree" not in attempt for attempt in failure.value.attempts)


@pytest.mark.skipif(not MACE_PYTHON.is_file(), reason="Real isolated MACE Python required")
def test_corrupt_model_is_aborted_without_masking_integrity_failure(tmp_path):
    registry = _registry(tmp_path, {"mace": MACE_PYTHON})
    model = tmp_path / "damaged.model"
    model.write_bytes(b"invalid checkpoint")
    with pytest.raises(ValueError, match="Checkpoint digest"):
        execute_screening_with_fallback(["O", "H", "H"], WATER, checkpoint=model,
                                       registry_path=registry, workdir=tmp_path)
    evidence = list(tmp_path.glob("screening_*/attempts.json"))
    assert len(evidence) == 1
    attempts = json.loads(evidence[0].read_text())
    assert len(attempts) == 1 and attempts[0]["status"] == "ABORTED"
