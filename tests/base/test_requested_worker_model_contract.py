"""A requested model is never silently replaced with a different potential."""
from pathlib import Path

import pytest
from ase import Atoms

from cochem_base.core_engine.cochem_core_parsl_executors import (
    RequestedModelUnavailableError, WorkerModelCache, _WORKER_CALCULATOR_CACHE,
    clear_worker_calculator_cache, get_cached_mlff_calculator,
)


def test_unavailable_selected_model_is_not_cached_as_emt(tmp_path):
    clear_worker_calculator_cache()
    for model in ("mace", "aimnet2", "unsupported-method"):
        with pytest.raises(RequestedModelUnavailableError):
            get_cached_mlff_calculator(model, model_path=tmp_path / "absent-checkpoint.model")
        assert not _WORKER_CALCULATOR_CACHE
    with pytest.raises(RequestedModelUnavailableError, match="absent"):
        WorkerModelCache.get_model("MACE-OFF24m", tmp_path / "absent-checkpoint.model")


def test_explicit_emt_is_rejected_and_never_cached():
    clear_worker_calculator_cache()
    for token in ("emt", "EMT"):
        with pytest.raises(ValueError, match="permanently retired"):
            get_cached_mlff_calculator(token)
        assert not _WORKER_CALCULATOR_CACHE
