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


def test_explicit_emt_is_an_actual_empirical_calculation_and_cache_identity_is_preserved():
    clear_worker_calculator_cache()
    calculator = get_cached_mlff_calculator("emt")
    assert calculator is get_cached_mlff_calculator("emt")
    fixture = Path(__file__).parents[1] / "data" / "orca_6_1_1_water_hf_sto3g" / "water.xyz"
    rows = fixture.read_text().splitlines()[2:]
    molecule = Atoms([row.split()[0] for row in rows],
                     positions=[[float(v) for v in row.split()[1:4]] for row in rows])
    molecule.calc = calculator
    energy = molecule.get_potential_energy()
    forces = molecule.get_forces()
    assert calculator.name == "emt" and isinstance(energy, float)
    assert forces.shape == (3, 3)
    assert energy == molecule.get_potential_energy()
    # This is EMT on supplied geometry; no electronic-method or accuracy equivalence is claimed.
