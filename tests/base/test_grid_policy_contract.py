"""All grid-policy entry points enforce the spectroscopic grid boundary."""

import pytest
from pydantic import ValidationError

from cochem_base.config.grid_policy import GridPolicy, WorkflowPhase


def test_public_phase_constants_and_enum_are_consistent():
    assert GridPolicy.PHASE_PREOPT == "defgrid1"
    assert GridPolicy.PHASE_FINALOPT == GridPolicy.PHASE_NUMFREQ == "defgrid3"
    for phase in WorkflowPhase:
        assert GridPolicy.validate_grid(phase, "defgrid3")
        assert GridPolicy.validate_grid(phase.name, "DEFGRID3")


@pytest.mark.parametrize("phase", ["finalopt", "numfreq"])
@pytest.mark.parametrize("grid", ["defgrid1", "defgrid2", "grid3", "grid5"])
def test_production_and_frequency_grids_cannot_be_coarse(phase, grid):
    assert not GridPolicy.validate_grid(phase, grid)


@pytest.mark.parametrize("phase", ["unknown", "preopt_then_numfreq", "badfinalopt", None])
def test_unknown_phase_is_not_a_permissive_fallback(phase):
    assert not GridPolicy.validate_grid(phase, "defgrid3")


@pytest.mark.parametrize("field", ["finalopt_grid", "freq_grid"])
def test_policy_construction_and_assignment_cannot_bypass_grid_guard(field):
    with pytest.raises(ValidationError):
        GridPolicy(**{field: "defgrid2"})
    policy = GridPolicy()
    with pytest.raises(ValidationError):
        if field == "finalopt_grid":
            policy.finalopt_grid = "defgrid2"
        else:
            policy.freq_grid = "defgrid2"
