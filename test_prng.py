import pytest

from cochem_base.core import execute_with_provenance
from cochem_base.core.metadata import default_provenance_tracker


@pytest.fixture(autouse=True)
def clear_tracker():
    default_provenance_tracker.clear()
    yield


def test_execute_with_provenance_success():
    """Verify stochastic function provenance is recorded when valid seed is provided."""
    @execute_with_provenance
    def my_stochastic_func(x, seed=None):
        return x * 2

    res = my_stochastic_func(10, seed=42)
    assert res == 20

    records = default_provenance_tracker.get_records()
    assert len(records) == 1
    assert records[0]['function'] == 'my_stochastic_func'
    assert records[0]['seed'] == 42


def test_execute_with_provenance_missing_seed_kwarg():
    """Verify ValueError is raised if seed kwarg is entirely missing."""
    @execute_with_provenance
    def my_stochastic_func(x, seed=None):
        return x * 2

    with pytest.raises(ValueError, match="requires a 'seed' keyword argument"):
        my_stochastic_func(5)


def test_execute_with_provenance_none_seed():
    """Verify RuntimeError is raised if seed is None."""
    @execute_with_provenance
    def my_stochastic_func(x, seed=None):
        return x * 2

    with pytest.raises(RuntimeError, match="Seed cannot be None"):
        my_stochastic_func(5, seed=None)
